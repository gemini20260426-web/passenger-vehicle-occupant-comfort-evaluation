"""
双模式处理器 — 流式实时识别 + 离线批处理

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 8.1-8.4 节。
提供统一的流式/离线双模式事件检测，共享同一模型和特征提取器。
"""

from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional, TYPE_CHECKING
import numpy as np
import pandas as pd
from collections import deque
from pathlib import Path
import logging
import time

from .tri_stage_detector import UnifiedEventDetector, EventResult
from .event_registry import METADATA_EVENT_REGISTRY, validate_event_type

if TYPE_CHECKING:
    from .model_trainer import AdaptiveModelUpdater

logger = logging.getLogger(__name__)


# ── 共享模型注册表 (单例) ──
class SharedModelRegistry:
    """共享模型注册表 (流式+离线共用)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.models = {}
            cls._instance.feature_config = None
            cls._instance.thresholds = None
            cls._instance.fs = 100.0
        return cls._instance

    def register(self, name: str, model, feature_config: dict = None,
                 thresholds: dict = None, fs: float = 100.0):
        self.models[name] = model
        self.feature_config = feature_config or {}
        self.thresholds = thresholds or {}
        self.fs = fs

    def get_model(self, name: str):
        return self.models.get(name)

    def get_config(self):
        return self.feature_config, self.thresholds, self.fs


# ── 抽象处理器基类 ──
class AbstractProcessor(ABC):
    """抽象处理器基类"""

    def __init__(self, fs: float = 100.0,
                 model_updater: 'AdaptiveModelUpdater' = None):
        self.registry = SharedModelRegistry()
        self.fs = fs
        self.detector = UnifiedEventDetector(
            fs, model_updater=model_updater
        )
        self.model_updater = model_updater
        self._total_processed = 0
        self._total_events = 0

    @abstractmethod
    def process(self, data_source) -> Generator:
        """统一处理接口"""
        pass

    def _extract_and_detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        """特征提取 → 事件检测 (流式+离线共用)"""
        return self.detector.detect_all(window)

    def _extract_and_detect_with_ml(self, window: Dict[str, np.ndarray],
                                     features: np.ndarray = None) -> List[EventResult]:
        """特征提取 → 事件检测 + ML后验 (流式+离线共用)"""
        if self.model_updater is not None:
            return self.detector.detect_all_with_ml(window, features)
        return self.detector.detect_all(window)

    def provide_feedback(self, features: np.ndarray, event_type: str,
                         true_label: bool, source: str = 'manual') -> None:
        """人工标注反馈"""
        self.detector.provide_feedback(features, event_type, true_label, source)

    def get_drift_status(self) -> dict:
        """获取ML模型漂移状态"""
        return self.detector.get_drift_status()

    def _validate_results(self, results: List[EventResult]) -> List[EventResult]:
        """验证检测结果 (Phase 5: 事件注册校验)"""
        validated = []
        for r in results:
            if validate_event_type(r.event_type):
                validated.append(r)
            else:
                logger.debug(f"未注册事件类型: {r.event_type}, 已过滤")
        return validated

    @property
    def stats(self) -> dict:
        return {
            'total_processed': self._total_processed,
            'total_events': self._total_events,
        }


# ── 流式处理器 ──
class StreamingProcessor(AbstractProcessor):
    """流式实时识别处理器

    使用环形缓冲区逐帧处理，适用于实车在线评测。
    延迟: <50ms (目标)

    支持在线自适应更新:
    - model_updater: AdaptiveModelUpdater 实例 (可选)
    - 启用后, 低置信度检测结果会触发漂移检测
    - 通过 provide_feedback() 提供人工标注后触发增量学习
    """

    def __init__(self, window_size: int = 500, step_size: int = 50,
                 fs: float = 100.0,
                 model_updater: 'AdaptiveModelUpdater' = None):
        super().__init__(fs, model_updater=model_updater)
        self.window_size = window_size
        self.step_size = step_size
        self.circular_buffer: deque = deque(maxlen=window_size * 2)
        self.frame_count = 0
        self.last_processed_idx = 0
        self._field_names = ['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az']

    def process(self, data_source) -> Generator[EventResult, None, None]:
        """流式逐帧处理 (Generator模式)"""
        for frame in data_source:
            self.circular_buffer.append(frame)
            self.frame_count += 1

            if self.frame_count - self.last_processed_idx >= self.step_size:
                self._total_processed += 1
                window = self._get_current_window()

                if len(window.get('speed', [])) >= self.window_size * 0.5:
                    t0 = time.perf_counter()
                    results = self._extract_and_detect(window)
                    latency_ms = (time.perf_counter() - t0) * 1000

                    for r in results:
                        r.latency_ms = round(latency_ms, 2)
                        self._total_events += 1
                        yield r

                self.last_processed_idx = self.frame_count

    def _get_current_window(self) -> Dict[str, np.ndarray]:
        """取出环形缓冲区当前窗口"""
        buf = list(self.circular_buffer)
        start = max(0, len(buf) - self.window_size)
        window_data = buf[start:]

        result = {}
        for i, name in enumerate(self._field_names):
            if window_data and i < len(window_data[0]):
                result[name] = np.array([f[i] for f in window_data], dtype=np.float64)
        return result

    def feed_frame(self, frame: dict) -> Optional[List[EventResult]]:
        """逐帧喂入 (非Generator接口)"""
        values = [frame.get(name, 0.0) for name in self._field_names]
        self.circular_buffer.append(tuple(values))
        self.frame_count += 1

        if self.frame_count - self.last_processed_idx >= self.step_size:
            self._total_processed += 1
            window = self._get_current_window()

            if len(window.get('speed', [])) >= self.window_size * 0.5:
                t0 = time.perf_counter()
                results = self._extract_and_detect(window)
                latency_ms = (time.perf_counter() - t0) * 1000

                for r in results:
                    r.latency_ms = round(latency_ms, 2)
                    self._total_events += 1

                self.last_processed_idx = self.frame_count
                return results

        return None


# ── 离线批处理器 ──
class BatchProcessor(AbstractProcessor):
    """离线CSV/文件批处理处理器

    分块滑动窗口处理全量数据，适用于事后数据分析。
    延迟: 秒级 (可接受)
    """

    def __init__(self, window_size: int = 500, step_size: int = 50,
                 fs: float = 100.0,
                 model_updater: 'AdaptiveModelUpdater' = None):
        super().__init__(fs, model_updater=model_updater)
        self.window_size = window_size
        self.step_size = step_size
        self._field_names = ['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az']

    def process(self, data_source: np.ndarray) -> Generator[EventResult, None, None]:
        """分块批处理 (滑动窗口)"""
        total = len(data_source)

        for start in range(0, total - self.window_size, self.step_size):
            self._total_processed += 1
            end = start + self.window_size
            window_raw = data_source[start:end]

            window = {}
            for i, name in enumerate(self._field_names):
                if i < window_raw.shape[1]:
                    window[name] = window_raw[:, i].astype(np.float64)

            t0 = time.perf_counter()
            results = self._extract_and_detect(window)
            latency_ms = (time.perf_counter() - t0) * 1000

            for r in results:
                r.latency_ms = round(latency_ms, 2)
                self._total_events += 1
                yield r

    def process_csv(self, csv_path: str) -> pd.DataFrame:
        """CSV 文件入口

        Returns:
            DataFrame with columns: timestamp, event_type, category, confidence
        """
        df = pd.read_csv(csv_path)

        # 提取所需列
        available_cols = []
        for name in self._field_names:
            if name in df.columns:
                available_cols.append(name)
            else:
                # 尝试模糊匹配
                for col in df.columns:
                    if name.lower() in col.lower():
                        available_cols.append(col)
                        break
                else:
                    available_cols.append(None)

        valid_cols = [c for c in available_cols if c is not None]
        if not valid_cols:
            raise ValueError(f"CSV中未找到所需字段: {self._field_names}")

        data = df[valid_cols].values
        results = list(self.process(data))

        # 转换为DataFrame
        result_df = pd.DataFrame([
            {
                'timestamp': r.timestamp,
                'event_type': r.event_type,
                'category': r.category,
                'confidence': r.confidence,
                'latency_ms': r.latency_ms,
                'event_name_cn': METADATA_EVENT_REGISTRY.get(r.event_type, {}).name_cn
                if hasattr(METADATA_EVENT_REGISTRY.get(r.event_type, {}), 'name_cn')
                else r.event_type,
            }
            for r in results
        ])

        logger.info(f"批处理完成: {len(results)} 个事件, {len(df)} 行数据")
        return result_df


# ── 一致性验证 ──
def verify_streaming_vs_batch(data_path: str, n_frames: int = 5000,
                               fs: float = 100.0) -> dict:
    """流式 vs 离线 一致性验证"""
    df = pd.read_csv(data_path)
    data = df[['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az']].values[:n_frames]

    # 离线批处理
    batch_processor = BatchProcessor(fs=fs)
    batch_results = list(batch_processor.process(data))

    # 流式模拟
    stream_processor = StreamingProcessor(fs=fs)
    stream_results = []
    for row in data:
        frame = {
            'rel_time': row[0], 'speed': row[1], 'wheel': row[2],
            'Ax': row[3], 'Ay': row[4], 'Az': row[5],
        }
        result = stream_processor.feed_frame(frame)
        if result:
            stream_results.extend(result)

    # 对比
    report = {
        'batch_count': len(batch_results),
        'stream_count': len(stream_results),
        'count_match': len(batch_results) == len(stream_results),
    }

    if report['count_match']:
        type_mismatches = 0
        conf_diffs = []
        for i, (sr, br) in enumerate(zip(stream_results, batch_results)):
            if sr.event_type != br.event_type:
                type_mismatches += 1
            conf_diffs.append(abs(sr.confidence - br.confidence))

        report['type_mismatches'] = type_mismatches
        report['max_conf_diff'] = round(float(max(conf_diffs)), 6) if conf_diffs else 0.0
        report['consistent'] = type_mismatches == 0 and report['max_conf_diff'] < 0.01
    else:
        report['consistent'] = False

    logger.info(
        f"一致性验证: {'通过' if report.get('consistent') else '未通过'} "
        f"(batch={report['batch_count']}, stream={report['stream_count']})"
    )
    return report