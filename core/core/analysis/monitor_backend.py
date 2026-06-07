"""
系统监控后端实体

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 13.4 节。
为监控面板提供后端数据采集，跟踪事件检测性能、数据质量和模型健康状态。
"""

import time
import numpy as np
from collections import deque
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class EventDetectionRecord:
    """单次事件检测记录"""
    timestamp: float
    event_type: str
    confidence: float
    latency_ms: float
    window_size: int


class SystemMonitorBackend:
    """系统监控后端 — 事件引擎配套

    跟踪三类指标:
    1. 处理性能: 事件检测延迟、帧处理速率、管道队列深度
    2. 数据质量: IMU掉线、信号饱和、同步偏移
    3. 模型健康: 置信度分布、模型漂移、事件类型分布
    """

    def __init__(self, buffer_size: int = 1000):
        self.buffer_size = buffer_size

        # ── 处理性能指标 ──
        self._event_detect_latency: deque = deque(maxlen=buffer_size)
        self._frame_process_times: deque = deque(maxlen=buffer_size)
        self._pipeline_queue_depth: int = 0
        self._total_frames_processed: int = 0
        self._total_events_detected: int = 0

        # ── 数据质量指标 ──
        self._imu_dropout_count: Dict[str, int] = {}
        self._signal_saturation_count: Dict[str, int] = {}
        self._sync_offset_ms: deque = deque(maxlen=buffer_size)
        self._data_gap_count: int = 0

        # ── 模型健康指标 ──
        self._model_confidence_history: deque = deque(maxlen=buffer_size)
        self._event_type_histogram: Dict[str, int] = {}
        self._model_drift_score: float = 0.0
        self._recent_results: deque = deque(maxlen=100)

        # ── 启动时间 ──
        self._start_time: float = time.time()
        self._last_report_time: float = self._start_time

    # ── 记录接口 ──

    def record_detection(self, event_type: str, confidence: float,
                         latency_ms: float, window_size: int = 0) -> None:
        """记录每次事件检测结果"""
        record = EventDetectionRecord(
            timestamp=time.time(),
            event_type=event_type,
            confidence=confidence,
            latency_ms=latency_ms,
            window_size=window_size,
        )
        self._recent_results.append(record)
        self._event_detect_latency.append(latency_ms)
        self._model_confidence_history.append(confidence)
        self._total_events_detected += 1

        # 更新事件类型直方图
        self._event_type_histogram[event_type] = \
            self._event_type_histogram.get(event_type, 0) + 1

    def record_frame_processed(self, process_time_ms: float) -> None:
        """记录帧处理时间"""
        self._frame_process_times.append(process_time_ms)
        self._total_frames_processed += 1

    def record_imu_dropout(self, imu_id: str) -> None:
        """记录IMU掉线"""
        self._imu_dropout_count[imu_id] = \
            self._imu_dropout_count.get(imu_id, 0) + 1

    def record_signal_saturation(self, imu_id: str) -> None:
        """记录信号饱和"""
        self._signal_saturation_count[imu_id] = \
            self._signal_saturation_count.get(imu_id, 0) + 1

    def record_sync_offset(self, offset_ms: float) -> None:
        """记录同步偏移"""
        self._sync_offset_ms.append(offset_ms)

    def record_data_gap(self) -> None:
        """记录数据间隙"""
        self._data_gap_count += 1

    def update_pipeline_depth(self, depth: int) -> None:
        """更新管道队列深度"""
        self._pipeline_queue_depth = depth

    def update_model_drift(self, drift_score: float) -> None:
        """更新模型漂移分数"""
        self._model_drift_score = drift_score

    # ── 健康检查 ──

    def check_health(self) -> dict:
        """系统健康检查 (供UI面板调用)"""
        now = time.time()
        elapsed = now - self._start_time

        # 近期延迟
        recent_latencies = list(self._event_detect_latency)[-50:]
        avg_latency = float(np.mean(recent_latencies)) if recent_latencies else 0.0
        max_latency = float(np.max(recent_latencies)) if recent_latencies else 0.0

        # 近期置信度
        recent_confs = list(self._model_confidence_history)[-50:]
        avg_confidence = float(np.mean(recent_confs)) if recent_confs else 0.0

        # 帧处理速率
        fps = self._total_frames_processed / max(elapsed, 1.0)

        # 状态判定
        if avg_latency < 50 and avg_confidence > 0.90:
            status = 'healthy'
            status_text = '健康'
        elif avg_latency < 100 and avg_confidence > 0.70:
            status = 'degraded'
            status_text = '降级'
        else:
            status = 'unhealthy'
            status_text = '异常'

        return {
            'status': status,
            'status_text': status_text,
            'uptime_seconds': round(elapsed, 1),
            'avg_latency_ms': round(avg_latency, 1),
            'max_latency_ms': round(max_latency, 1),
            'avg_confidence': round(avg_confidence, 3),
            'total_events': self._total_events_detected,
            'total_frames': self._total_frames_processed,
            'event_types': len(self._event_type_histogram),
            'fps': round(fps, 1),
            'pipeline_depth': self._pipeline_queue_depth,
            'data_gaps': self._data_gap_count,
            'model_drift': round(self._model_drift_score, 4),
        }

    def get_event_distribution(self) -> dict:
        """获取事件类型分布"""
        total = sum(self._event_type_histogram.values())
        if total == 0:
            return {}
        return {
            etype: {'count': count, 'ratio': round(count / total, 3)}
            for etype, count in sorted(
                self._event_type_histogram.items(),
                key=lambda x: x[1], reverse=True
            )
        }

    def get_imu_quality_report(self) -> dict:
        """获取IMU数据质量报告"""
        return {
            'dropouts': dict(self._imu_dropout_count),
            'saturations': dict(self._signal_saturation_count),
            'total_dropouts': sum(self._imu_dropout_count.values()),
            'total_saturations': sum(self._signal_saturation_count.values()),
        }

    def get_performance_summary(self) -> dict:
        """获取性能摘要"""
        latencies = list(self._event_detect_latency)
        if not latencies:
            return {'p50_ms': 0, 'p95_ms': 0, 'p99_ms': 0, 'avg_ms': 0}

        latencies_sorted = sorted(latencies)
        return {
            'p50_ms': round(float(np.percentile(latencies_sorted, 50)), 1),
            'p95_ms': round(float(np.percentile(latencies_sorted, 95)), 1),
            'p99_ms': round(float(np.percentile(latencies_sorted, 99)), 1),
            'avg_ms': round(float(np.mean(latencies_sorted)), 1),
            'min_ms': round(float(np.min(latencies_sorted)), 1),
            'max_ms': round(float(np.max(latencies_sorted)), 1),
        }

    def get_health_report(self) -> dict:
        """F4: 获取综合健康报告 (供 UI 面板和日志使用)"""
        health = self.check_health()
        perf = self.get_performance_summary()
        dist = self.get_event_distribution()
        imu = self.get_imu_quality_report()

        return {
            'health': health,
            'performance': perf,
            'event_distribution': dist,
            'imu_quality': imu,
            'summary': (
                f"状态: {health['status_text']}, "
                f"事件: {health['total_events']}, "
                f"延迟: {health['avg_latency_ms']:.1f}ms, "
                f"置信度均值: {health['avg_confidence']:.3f}, "
                f"数据间隙: {health['data_gaps']}"
            ),
        }

    def record_pipeline_event(self, event_type: str, confidence: float,
                              latency_ms: float = 0.0) -> None:
        """F4: 便捷记录接口 — 供 pipeline 一步调用

        同时记录检测事件和置信度，自动计算近似的处理延迟。
        """
        self.record_detection(
            event_type=event_type,
            confidence=confidence,
            latency_ms=latency_ms,
        )

    def reset(self) -> None:
        """重置所有指标"""
        self._event_detect_latency.clear()
        self._frame_process_times.clear()
        self._pipeline_queue_depth = 0
        self._total_frames_processed = 0
        self._total_events_detected = 0
        self._imu_dropout_count.clear()
        self._signal_saturation_count.clear()
        self._sync_offset_ms.clear()
        self._data_gap_count = 0
        self._model_confidence_history.clear()
        self._event_type_histogram.clear()
        self._model_drift_score = 0.0
        self._recent_results.clear()
        self._start_time = time.time()


# ── 全局单例 ──
_monitor_instance: Optional[SystemMonitorBackend] = None


def get_system_monitor() -> SystemMonitorBackend:
    """获取系统监控单例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SystemMonitorBackend()
    return _monitor_instance