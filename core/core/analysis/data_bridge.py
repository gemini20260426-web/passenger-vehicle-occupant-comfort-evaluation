#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据桥接器 - 连接数据源→五层分析管道→UI面板
国际标准ADAS架构：统一使用五层分析架构
"""

import time
import gc
import logging
from typing import Dict, Any, List, Optional
from collections import deque

from PySide6.QtCore import QObject, Signal, QTimer

from .pipeline import AnalysisPipeline
from .analysis_result_cache import AnalysisResultCache
from .event_distributor import EventDistributor
from ..data_processing.data_persister import DataPersister
from ..async_scheduler import get_scheduler, TaskPriority


class DataBridge(QObject):
    """数据桥接器 - 连接数据源→五层分析管道→UI面板"""

    sensor_data_received = Signal(dict)
    sensor_data_batch_received = Signal(list)
    frame_result_ready = Signal(object)
    bridge_status_changed = Signal(str)
    processing_progress = Signal(int, int)
    
    # 信号：用于直接连接UI模块
    realtime_monitor_data = Signal(dict)
    behavior_event_ready = Signal(object)
    seat_evaluation_triggered = Signal(dict)
    generated_events = Signal(list)  # 批量分析完成后发射事件列表

    # 配置参数
    _SENSOR_DATA_THROTTLE_MS = 50
    _RESULT_EMIT_INTERVAL_MS = 50
    _BATCH_MAX_SIZE = 50
    _BATCH_FLUSH_INTERVAL = 0.1
    _PROCESS_BATCH_SIZE = 100

    # 单位系统：国际标准ADAS单位
    KMH_TO_MS = 1000 / 3600  # km/h → m/s
    DEG_TO_RAD = 3.14159265359 / 180  # deg → rad

    # 速度单位自动检测
    _SPEED_UNIT_SAMPLE_SIZE = 20
    _SPEED_KMH_THRESHOLD = 80  # 超过此值判定为km/h
    _speed_unit_samples = []
    _speed_unit_determined = None  # None=未检测, 'kmh'=公里/时, 'ms'=米/秒

    # 速度查找表：从ch6 CAN文件加载，用于补充IMU记录中缺失的速度数据
    _speed_lookup = {}  # {timestamp: (speed_ms, wheel_deg)}
    _speed_lookup_loaded = False
    _speed_lookup_timestamps = []  # 排序后的时间戳列表，用于二分查找
    _speed_lookup_lock = None  # 线程锁，延迟初始化

    # 驾驶行为分析主IMU通道（硬约束，禁止修改）
    # 所有驾驶状态机、事件生成、风险评估必须且仅使用此通道数据
    # 座椅底部IMU7(实验组)是唯一经过标定的驾驶行为参考传感器
    PRIMARY_IMU_NAME = 'IMU7_座椅底部-1'

    # 数据质量统计
    _quality_stats = {
        'total_normalized': 0,
        'missing_speed': 0,
        'missing_accel': 0,
        'missing_gyro': 0,
        'anomaly_speed': 0,
        'anomaly_accel': 0,
    }

    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager

        # 五层分析管道（唯一）
        self._pipeline = None
        self._pipeline_config = {"driving_thresholds": {}}

        self.is_running = False
        self._processed_count = 0
        self._total_count = 0
        self._data_queue = deque(maxlen=2000)

        self._batch_buffer = []
        self._batch_max_size = self._BATCH_MAX_SIZE
        self._last_batch_flush = 0
        self._batch_flush_interval = self._BATCH_FLUSH_INTERVAL

        self._process_queue = deque(maxlen=5000)
        self._last_progress_emit = 0
        self._last_sensor_emit = 0
        self._last_result_emit = 0

        self._recent_can_records = deque(maxlen=100)
        self._persister = DataPersister(flush_interval=200, flush_seconds=5.0)

        self._scheduler = get_scheduler(max_workers=1)
        self._processing_in_progress = False
        self._process_lock = False
        self._suppress_ui_signals = False

        # 分析结果缓存（可选）
        self._analysis_cache = None
        self._caching_enabled = False

        # 批量分析标志：流式回放路径接入完整管线后，抑制逐帧 pipeline
        self._batch_analyzed = False

        # 座椅评测引擎引用
        self._seat_evaluation_engine = None
        self._cache = None
        self._recent_raw_records = deque(maxlen=200000)
        self._evaluation_queue = deque()
        self._eval_queue_timer = QTimer()
        self._eval_queue_timer.setSingleShot(True)
        self._eval_queue_timer.setInterval(200)
        self._eval_queue_timer.timeout.connect(self._process_evaluation_queue)
        self._eval_queue_processing = False

        self._init_pipeline()
        self._setup_metadata_validation()
        self.logger.info("DataBridge 初始化完成（五层ADAS架构）")

    def _init_pipeline(self, primary_imu_name: str = None):
        """初始化唯一的五层分析管道"""
        try:
            from .core_types import VehicleConfig
            imu_name = primary_imu_name or self.PRIMARY_IMU_NAME
            self._pipeline = AnalysisPipeline(VehicleConfig(), primary_imu_names=[imu_name])
            self.logger.info(f"五层分析管道已初始化 (主IMU: {imu_name})")
        except Exception as e:
            self.logger.error(f"初始化五层分析管道失败: {e}")

    def _setup_metadata_validation(self):
        """初始化元数据校验器 — 延迟加载避免循环依赖"""
        self._registry = None
        self._validation_enabled = True
        self._validation_log_interval = 500
        self._validation_count = 0
        self._validation_blocked = 0
        self._validation_passed = 0
        self._validation_unknown_fields = set()

    def _get_registry(self):
        if self._registry is None:
            try:
                from core.core.seat_evaluation.metadata_registry import get_global_registry
                self._registry = get_global_registry()
            except Exception as e:
                self.logger.warning(f"元数据注册中心加载失败，校验功能关闭: {e}")
                self._validation_enabled = False
        return self._registry

    def _validate_raw_record(self, record: Dict[str, Any]):
        if not self._validation_enabled:
            return
        reg = self._get_registry()
        if reg is None:
            return
        self._validation_count += 1
        result = reg.validate_raw_data_record(record)
        if not result['valid']:
            self._validation_blocked += 1
            if self._validation_blocked <= 10 or self._validation_blocked % self._validation_log_interval == 0:
                for v in result['violations']:
                    self.logger.warning(
                        f"[MetadataValidator] 数据校验失败 | {v['message']} | "
                        f"累计: passed={self._validation_passed} blocked={self._validation_blocked}"
                    )
        else:
            self._validation_passed += 1

    def get_validation_stats(self) -> Dict[str, Any]:
        return {
            'total_checked': self._validation_count,
            'passed': self._validation_passed,
            'blocked': self._validation_blocked,
            'unknown_fields': sorted(self._validation_unknown_fields),
            'enabled': self._validation_enabled,
        }

    def set_seat_evaluation_engine(self, engine):
        """注入座椅评测引擎"""
        self._seat_evaluation_engine = engine
        self.logger.info("座椅评测引擎已注入到DataBridge")

    def set_cache(self, cache):
        """注入多源数据缓存（用于提取时间窗口数据）"""
        self._cache = cache
        self.logger.info("MultiSourceCache 已注入到DataBridge")

    def _schedule_process_batch(self):
        """调度批量处理任务"""
        if self._process_lock or not self.is_running:
            return
        if not self._process_queue:
            return

        now = time.time()
        if not hasattr(self, '_last_schedule_time'):
            self._last_schedule_time = 0
        if now - self._last_schedule_time < 0.05:
            return
        self._last_schedule_time = now

        self._process_lock = True
        qsize = len(self._process_queue)
        if not hasattr(self, '_schedule_log_count'):
            self._schedule_log_count = 0
        self._schedule_log_count += 1
        if self._schedule_log_count <= 5 or self._schedule_log_count % 100 == 0:
            self.logger.debug(f"[DEBUG] _schedule_process_batch #{self._schedule_log_count}, queue_size={qsize}")
        self._scheduler.submit(
            self._drain_process_queue,
            priority=TaskPriority.HIGH
        )

    def feed_parsed_data(self, parsed_record: Dict[str, Any]):
        """接收解析后的单条数据"""
        self._data_queue.append(parsed_record)
        self._total_count += 1

        if self._total_count % 100 == 1:
            self._validate_raw_record(parsed_record)

        if self._is_can_wide_format(parsed_record) or self._is_can_long_format(parsed_record):
            self._recent_can_records.append(parsed_record)

        self._recent_raw_records.append(parsed_record)

        now = time.time()
        if now - self._last_sensor_emit >= self._SENSOR_DATA_THROTTLE_MS / 1000.0:
            normalized = self._normalize_can_record(parsed_record)
            if not self._suppress_ui_signals:
                self.sensor_data_received.emit(normalized)
            self._last_sensor_emit = now

        self._batch_buffer.append(parsed_record)
        if len(self._batch_buffer) >= self._batch_max_size or (now - self._last_batch_flush >= self._batch_flush_interval):
            self._flush_batch()
            self._last_batch_flush = now

        if self.is_running and self._is_imu_record(parsed_record):
            normalized = self._normalize_can_record(parsed_record)
            self._process_queue.append(normalized)
            if not hasattr(self, '_feed_log_count'):
                self._feed_log_count = 0
            self._feed_log_count += 1
            if self._feed_log_count <= 5 or self._feed_log_count % 500 == 0:
                self.logger.debug(f"[DEBUG] feed_parsed_data → process_queue, count={self._feed_log_count}, queue_size={len(self._process_queue)}")
            if len(self._process_queue) >= 3:
                self._schedule_process_batch()

    @staticmethod
    def _is_can_long_format(record: Dict[str, Any]) -> bool:
        return any(k in record for k in ('Ax_m_s2', 'Gx_dps', 'imu_name'))

    @staticmethod
    def _is_can_wide_format(record: Dict[str, Any]) -> bool:
        return any(
            (k.startswith('ch') and ('_f0_Accel' in k or '_f0_Gyro' in k or '_ax' in k))
            for k in record
        )

    @staticmethod
    def _detect_speed_unit(speed_value: float) -> Optional[str]:
        """自动检测速度单位（km/h 或 m/s）

        通过采样多个记录的速度值来判断单位：
        - 如果大部分采样值 > 80，判定为 km/h
        - 如果大部分采样值 < 50，判定为 m/s
        - 采样不足时返回 None
        """
        if DataBridge._speed_unit_determined is not None:
            return DataBridge._speed_unit_determined

        if speed_value is None or speed_value == 0:
            return None

        DataBridge._speed_unit_samples.append(abs(speed_value))

        if len(DataBridge._speed_unit_samples) >= DataBridge._SPEED_UNIT_SAMPLE_SIZE:
            samples = DataBridge._speed_unit_samples
            # 阈值: >50 可能 km/h，<5 可能 m/s（避免中速区域的歧义）
            high_count = sum(1 for v in samples if v > 50)
            low_count = sum(1 for v in samples if 0 < v < 5)

            if high_count > len(samples) * 0.4:
                DataBridge._speed_unit_determined = 'kmh'
                logger.info(f"速度单位自动检测: km/h (采样{len(samples)}条, "
                            f"高速值占比{high_count/len(samples):.0%})")
            elif low_count > len(samples) * 0.8:
                DataBridge._speed_unit_determined = 'ms'
                logger.info(f"速度单位自动检测: m/s (采样{len(samples)}条, "
                            f"极低速值占比{low_count/len(samples):.0%})")
            else:
                DataBridge._speed_unit_determined = 'kmh'
                logger.warning(f"速度单位无法确定，默认使用 km/h "
                               f"(采样{len(samples)}条, 高速{high_count}, 极低速{low_count})")

        return DataBridge._speed_unit_determined

    @classmethod
    def _load_speed_lookup(cls):
        import threading
        if cls._speed_lookup_lock is None:
            cls._speed_lookup_lock = threading.Lock()

        with cls._speed_lookup_lock:
            if cls._speed_lookup_loaded:
                return
            cls._speed_lookup_loaded = True

            import csv
            import os
            import glob as _glob
            import logging as _logging

            _logger = _logging.getLogger(__name__)

            search_dirs = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))), '徐宁数据', '解析数据集'),
            ]

            ch6_files = []
            for d in search_dirs:
                if os.path.isdir(d):
                    ch6_files.extend(_glob.glob(os.path.join(d, '*ch6*CAN*.csv')))
                    ch6_files.extend(_glob.glob(os.path.join(d, '*ch6*.csv')))

            if not ch6_files:
                _logger.warning("未找到ch6 CAN速度数据文件，速度查找表为空")
                return

            ch6_file = ch6_files[0]
            _logger.info(f"加载ch6 CAN速度数据: {ch6_file}")

            try:
                with open(ch6_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        speed_kmh_str = row.get('车速_kmh', '').strip()
                        if not speed_kmh_str:
                            continue
                        try:
                            speed_kmh = float(speed_kmh_str)
                        except ValueError:
                            continue
                        if speed_kmh <= 0:
                            continue

                        rel_time_str = row.get('rel_time', '').strip()
                        if not rel_time_str:
                            continue
                        try:
                            rel_time = float(rel_time_str)
                        except ValueError:
                            continue

                        wheel_str = row.get('方向盘转角_deg', '0').strip()
                        try:
                            wheel_deg = float(wheel_str) if wheel_str else 0.0
                        except ValueError:
                            wheel_deg = 0.0

                        speed_ms = speed_kmh * cls.KMH_TO_MS
                        cls._speed_lookup[rel_time] = (speed_ms, wheel_deg)

                cls._speed_lookup_timestamps = sorted(cls._speed_lookup.keys())
                _logger.info(f"ch6 CAN速度查找表已加载: {len(cls._speed_lookup)} 条速度记录, "
                            f"时间范围 [{cls._speed_lookup_timestamps[0]:.3f}, "
                            f"{cls._speed_lookup_timestamps[-1]:.3f}]")
            except Exception as e:
                _logger.error(f"加载ch6 CAN速度数据失败: {e}")

    @classmethod
    def _lookup_speed(cls, timestamp: float):
        if not cls._speed_lookup_timestamps:
            return 0.0, 0.0

        import bisect
        idx = bisect.bisect_left(cls._speed_lookup_timestamps, timestamp)

        if idx == 0:
            return cls._speed_lookup.get(cls._speed_lookup_timestamps[0], (0.0, 0.0))
        if idx >= len(cls._speed_lookup_timestamps):
            return cls._speed_lookup.get(cls._speed_lookup_timestamps[-1], (0.0, 0.0))

        t_left = cls._speed_lookup_timestamps[idx - 1]
        t_right = cls._speed_lookup_timestamps[idx]

        if abs(timestamp - t_left) <= abs(timestamp - t_right):
            return cls._speed_lookup.get(t_left, (0.0, 0.0))
        else:
            return cls._speed_lookup.get(t_right, (0.0, 0.0))

    @staticmethod
    def _validate_record_quality(record: Dict[str, Any], source: str):
        """校验单条记录的数据质量，更新质量统计"""
        DataBridge._quality_stats['total_normalized'] += 1

        speed = record.get('speed', None)
        if speed is None or speed == 0:
            DataBridge._quality_stats['missing_speed'] += 1

        ax = record.get('ax', None)
        ay = record.get('ay', None)
        if ax is None or ay is None:
            DataBridge._quality_stats['missing_accel'] += 1

        gx = record.get('gx', None)
        if gx is None:
            DataBridge._quality_stats['missing_gyro'] += 1

        if speed is not None and speed > 80:
            DataBridge._quality_stats['anomaly_speed'] += 1

        if ax is not None and abs(ax) > 50:
            DataBridge._quality_stats['anomaly_accel'] += 1

        total = DataBridge._quality_stats['total_normalized']
        if total > 0 and total % 10000 == 0:
            qs = DataBridge._quality_stats
            logger.info(f"数据质量统计 [{total}条]: "
                        f"缺速度={qs['missing_speed']}({qs['missing_speed']/total:.1%}), "
                        f"缺加速度={qs['missing_accel']}({qs['missing_accel']/total:.1%}), "
                        f"异常速度={qs['anomaly_speed']}, 异常加速度={qs['anomaly_accel']}")

    @staticmethod
    def get_quality_stats() -> Dict[str, Any]:
        """获取数据质量统计"""
        return dict(DataBridge._quality_stats)

    @staticmethod
    def reset_quality_stats():
        """重置数据质量统计"""
        DataBridge._quality_stats = {
            'total_normalized': 0, 'missing_speed': 0,
            'missing_accel': 0, 'missing_gyro': 0,
            'anomaly_speed': 0, 'anomaly_accel': 0,
        }
        DataBridge._speed_unit_samples = []
        DataBridge._speed_unit_determined = None

    @staticmethod
    def _detect_available_channels(record: Dict[str, Any]) -> List[str]:
        """自动检测记录中实际存在的IMU通道"""
        channels = []
        for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7', 'ch8', 'ch9', 'ch10'):
            has_accel = any(
                k.startswith(ch) and ('_f0_Accel' in k or '_ax' in k)
                for k in record
            )
            has_gyro = any(
                k.startswith(ch) and ('_f3_Gyro' in k or '_gx' in k)
                for k in record
            )
            if has_accel or has_gyro:
                channels.append(ch)
        return channels

    def _normalize_can_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """标准化数据格式 + 单位统一
        
        单位系统：
        - 加速度: m/s²
        - 角速度: rad/s
        - 速度: m/s (内部计算用)
        - 方向盘: deg
        """
        source_type = record.get('_source_type', '')
        source_id = record.get('source_id', '')

        # 如果已经有_normalized_from标记，说明已经处理过了
        # 但如果speed为0，尝试从速度查找表补充
        if '_normalized_from' in record:
            record['_source_id'] = source_id or record.get('_source_id', '')
            if record.get('speed', 0) == 0 and record.get('_source_type') == 'can_long':
                DataBridge._load_speed_lookup()
                ts = record.get('timestamp', time.time())
                speed_ms, wheel_deg = DataBridge._lookup_speed(float(ts))
                if speed_ms > 0:
                    record['speed'] = speed_ms
                    if wheel_deg != 0.0 and record.get('wheel', 0) == 0:
                        record['wheel'] = wheel_deg
            return record

        # 如果已经有ax/ay/az/gx/gy/gz字段，说明已经是标准格式
        # 但需要检查 speed 是否仍然是 km/h（来自 can_long 解析器的回放路径）
        if all(k in record for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
            record['_source_type'] = source_type or 'imu_standalone'
            record['_source_id'] = source_id or record.get('_source_id', '')
            # 回放路径：can_long 解析器输出的记录同时有 ax/ay/az 和 车速_kmh，
            # 但 speed 字段仍是 km/h，必须转换
            is_can_long_src = any(k in record for k in ('Ax_m_s2', 'Gx_dps', '车速_kmh'))
            if is_can_long_src:
                speed_kmh_val = float(record.get('车速_kmh', record.get('speed', 0)) or 0)
                if speed_kmh_val > 0:
                    record['speed'] = speed_kmh_val * DataBridge.KMH_TO_MS
                    record['_normalized_from'] = 'can_long_via_standalone'
            return record

        if DataBridge._is_can_long_format(record):
            imu_name = record.get('imu_name', '') or record.get('_imu_name', '')
            
            if not hasattr(self, '_debug_normalize_count'):
                self._debug_normalize_count = 0
            self._debug_normalize_count += 1
            if self._debug_normalize_count <= 3:
                self.logger.debug(f"[DEBUG] _normalize_can_record can_long: imu_name='{imu_name}', _imu_name='{record.get('_imu_name', '')}', keys={list(record.keys())[:10]}")
            
            speed_kmh = float(record.get('车速_kmh', record.get('speed', 0)) or 0)
            wheel_deg = float(record.get('方向盘转角_deg', record.get('wheel', 0)) or 0)

            if speed_kmh == 0:
                DataBridge._load_speed_lookup()
                ts = record.get('rel_time', record.get('timestamp', time.time()))
                speed_ms, looked_up_wheel = DataBridge._lookup_speed(float(ts))
                if looked_up_wheel != 0.0 and wheel_deg == 0:
                    wheel_deg = looked_up_wheel
            else:
                speed_ms = speed_kmh * DataBridge.KMH_TO_MS
            
            return {
                'rel_time': record.get('rel_time', record.get('timestamp', time.time())),
                'timestamp': record.get('rel_time', record.get('timestamp', time.time())),
                'channel': record.get('channel', 'ch1'),
                'imu_name': imu_name,
                'ax': float(record.get('Ax_m_s2', 0) or 0),
                'ay': float(record.get('Ay_m_s2', 0) or 0),
                'az': float(record.get('Az_m_s2', 0) or 0),
                'gx': float(record.get('Gx_rad_s', 0) or 0),
                'gy': float(record.get('Gy_rad_s', 0) or 0),
                'gz': float(record.get('Gz_rad_s', 0) or 0),
                'speed': speed_ms,  # 标准单位：m/s
                'wheel': wheel_deg,  # 标准单位：deg
                'loc1': 0.0,
                'loc2': 0.0,
                '_source_type': 'can_long',
                '_source_id': source_id,
                '_source_name': imu_name,
                '_normalized_from': 'can_long',
            }

        if DataBridge._is_can_wide_format(record):
            available_channels = DataBridge._detect_available_channels(record)
            ch = available_channels[0] if available_channels else 'ch4'

            def _extract(ch, field_patterns):
                for pat in field_patterns:
                    key = f'{ch}_{pat}'
                    if key in record:
                        return float(record.get(key, 0) or 0)
                return 0.0

            ax = _extract(ch, ['f0_Accel_m/s2', 'ax', 'Ax_m_s2'])
            ay = _extract(ch, ['f1_Accel_m/s2', 'ay', 'Ay_m_s2'])
            az = _extract(ch, ['f2_Accel_m/s2', 'az', 'Az_m_s2',
                               'f11_AccelZ_m/s2'])
            gx = _extract(ch, ['f3_Gyro_dps', 'gx', 'Gx_dps'])
            gy = _extract(ch, ['f4_Gyro_dps', 'gy', 'Gy_dps'])
            gz = _extract(ch, ['f5_Gyro_dps', 'gz', 'Gz_dps'])

            gx_rad = gx * DataBridge.DEG_TO_RAD
            gy_rad = gy * DataBridge.DEG_TO_RAD
            gz_rad = gz * DataBridge.DEG_TO_RAD

            raw_speed = float(record.get('speed', record.get('车速_kmh', 0)) or 0)
            speed_field_is_kmh = '车速_kmh' in record or 'speed_kmh' in record
            if speed_field_is_kmh:
                speed_ms = raw_speed * DataBridge.KMH_TO_MS
            else:
                detected_unit = DataBridge._detect_speed_unit(raw_speed)
                if detected_unit == 'kmh':
                    speed_ms = raw_speed * DataBridge.KMH_TO_MS
                elif detected_unit == 'ms':
                    speed_ms = raw_speed
                else:
                    speed_ms = raw_speed * DataBridge.KMH_TO_MS

            result = {
                'timestamp': record.get('timestamp', record.get('rel_time', time.time())),
                'ax': ax,
                'ay': ay,
                'az': az,
                'gx': gx_rad,
                'gy': gy_rad,
                'gz': gz_rad,
                'speed': speed_ms,
                'wheel': float(record.get('steering', record.get('方向盘转角_deg', 0)) or 0),
                'loc1': 0.0,
                'loc2': 0.0,
                '_source_type': 'can_wide',
                '_source_id': source_id,
                '_source_channel': ch,
                '_available_channels': available_channels,
                '_normalized_from': 'can_wide',
            }
            DataBridge._validate_record_quality(result, 'can_wide')
            return result

        record['_source_type'] = source_type or 'imu_standalone'
        record['_source_id'] = source_id or record.get('_source_id', '')
        return record

    @staticmethod
    def _is_imu_record(record: Dict[str, Any]) -> bool:
        if DataBridge._is_can_long_format(record):
            return True
        if DataBridge._is_can_wide_format(record):
            return True
        if not DataBridge._is_primary_imu_record(record):
            return False
        return any(k in record for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz'))

    _debug_primary_check_count = 0
    _debug_primary_pass_count = 0
    _debug_primary_reject_count = 0

    @staticmethod
    def _is_primary_imu_record(record: Dict[str, Any]) -> bool:
        """检查记录是否来自驾驶行为分析主IMU通道（IMU7_座椅底部-1）

        硬约束：驾驶状态机和事件生成必须且仅使用此通道数据。
        此方法不应被修改或绕过。
        """
        imu_name = record.get('_source_name', '') or record.get('_imu_name', '')
        DataBridge._debug_primary_check_count += 1
        if DataBridge._debug_primary_check_count <= 10:
            logger = logging.getLogger(__name__)
            logger.debug(f"[DEBUG] _is_primary_imu_record #{DataBridge._debug_primary_check_count}: "
                          f"_source_name='{record.get('_source_name', 'N/A')}', "
                          f"_imu_name='{record.get('_imu_name', 'N/A')}', "
                          f"imu_name='{imu_name}', "
                          f"result={'PASS' if (not imu_name or imu_name == DataBridge.PRIMARY_IMU_NAME) else 'REJECT'}")
        if not imu_name:
            DataBridge._debug_primary_pass_count += 1
            return True
        result = imu_name == DataBridge.PRIMARY_IMU_NAME
        if result:
            DataBridge._debug_primary_pass_count += 1
        else:
            DataBridge._debug_primary_reject_count += 1
        return result

    def feed_parsed_batch(self, parsed_records: List[Dict[str, Any]]):
        """接收解析后的批量数据"""
        if not parsed_records:
            return

        for record in parsed_records:
            self._data_queue.append(record)
            self._recent_raw_records.append(record)
        self._total_count += len(parsed_records)

        now = time.time()
        if now - self._last_sensor_emit >= self._SENSOR_DATA_THROTTLE_MS / 1000.0:
            last_record = parsed_records[-1]
            normalized = self._normalize_can_record(last_record)
            if not self._suppress_ui_signals:
                self.sensor_data_received.emit(normalized)
            self._last_sensor_emit = now

        self._batch_buffer.extend(parsed_records)
        if len(self._batch_buffer) >= self._batch_max_size or (now - self._last_batch_flush >= self._batch_flush_interval):
            self._flush_batch()
            self._last_batch_flush = now

        if self.is_running:
            imu_count = 0
            non_imu_count = 0
            for record in parsed_records:
                normalized = self._normalize_can_record(dict(record))
                if self._is_imu_record(normalized):
                    self._process_queue.append(normalized)
                    imu_count += 1
                else:
                    non_imu_count += 1
            if not hasattr(self, '_debug_batch_log_count'):
                self._debug_batch_log_count = 0
            self._debug_batch_log_count += 1
            if self._debug_batch_log_count <= 3:
                self.logger.debug(f"[DEBUG] feed_parsed_batch: total={len(parsed_records)}, imu={imu_count}, non_imu={non_imu_count}, queue_size={len(self._process_queue)}")
            if len(self._process_queue) >= 3:
                self._schedule_process_batch()

    def _drain_process_queue(self):
        """批量从队列取出记录进行处理"""
        if not self.is_running:
            self._process_lock = False
            return
        if not self._process_queue:
            self._process_lock = False
            return

        batch_count = 0
        while self._process_queue and batch_count < self._PROCESS_BATCH_SIZE:
            record = self._process_queue.popleft()
            try:
                self._process_single(record)
            except Exception as e:
                self._record_error_once(f"_process_error_{str(e)[:30]}", str(e))
            batch_count += 1

        if not hasattr(self, '_drain_log_count'):
            self._drain_log_count = 0
        self._drain_log_count += 1
        if self._drain_log_count <= 5 or self._drain_log_count % 100 == 0:
            self.logger.debug(f"[DEBUG] _drain_process_queue #{self._drain_log_count}, processed={batch_count}, processed_total={self._processed_count}, "
                           f"primary_check={DataBridge._debug_primary_check_count}, primary_pass={DataBridge._debug_primary_pass_count}, primary_reject={DataBridge._debug_primary_reject_count}")

        now = time.time()
        if now - self._last_progress_emit >= 5000 / 1000.0:
            self.processing_progress.emit(self._processed_count, self._total_count)
            self._last_progress_emit = now

        if self._processed_count % 500 == 0:
            gc.collect()

        if self._process_queue and self.is_running:
            self._process_lock = False
            self._schedule_process_batch()
        else:
            self._process_lock = False

    def _process_single(self, record: Dict[str, Any]):
        """处理单条记录：通过五层分析管道"""
        now = time.time()
        should_emit = (now - self._last_result_emit) >= (self._RESULT_EMIT_INTERVAL_MS / 1000.0)

        if not self._pipeline:
            if not hasattr(self, '_debug_no_pipeline_count'):
                self._debug_no_pipeline_count = 0
            self._debug_no_pipeline_count += 1
            if self._debug_no_pipeline_count <= 3:
                self.logger.debug(f"[DEBUG] _process_single: 无pipeline, 跳过 (第{self._debug_no_pipeline_count}次)")
            return

        if not hasattr(self, '_debug_process_single_count'):
            self._debug_process_single_count = 0
        self._debug_process_single_count += 1
        if self._debug_process_single_count <= 5:
            src_name = record.get('_source_name', 'N/A')
            imu_name = record.get('_imu_name', 'N/A')
            keys = list(record.keys())[:15]
            self.logger.debug(f"[DEBUG] _process_single #{self._debug_process_single_count}: _source_name={src_name}, _imu_name={imu_name}, keys={keys}")

        if not self._is_primary_imu_record(record):
            if not hasattr(self, '_debug_not_primary_count'):
                self._debug_not_primary_count = 0
            self._debug_not_primary_count += 1
            if self._debug_not_primary_count <= 5:
                src = record.get('_source_name', '?') or record.get('_imu_name', '?')
                self.logger.debug(f"[DEBUG] _process_single: 非主IMU记录, _source_name={src}, 跳过 (第{self._debug_not_primary_count}次)")
            return

        try:
            # 五层分析管道处理
            frame_result = self._pipeline.process_frame(record)
            
            if frame_result:
                # 更新 raw_data，添加标准化字段（UI友好）
                if frame_result.raw_data is None:
                    frame_result.raw_data = {}
                # 确保 raw_data 中有 speed_kmh (用于 UI 显示)
                speed_ms = frame_result.speed
                frame_result.raw_data['speed_kmh'] = speed_ms / self.KMH_TO_MS
                # 确保 raw_data 中也有 m/s 单位的 speed
                frame_result.raw_data['speed'] = speed_ms
                # 复制其他处理后的字段到 raw_data 便于 UI 使用
                frame_result.raw_data['ax'] = frame_result.ax
                frame_result.raw_data['ay'] = frame_result.ay
                frame_result.raw_data['az'] = frame_result.az
                frame_result.raw_data['gx'] = frame_result.gx
                frame_result.raw_data['gy'] = frame_result.gy
                frame_result.raw_data['gz'] = frame_result.gz
                frame_result.raw_data['wheel'] = frame_result.wheel
                
                # 添加上下文信息
                if frame_result.event and self._recent_can_records:
                    frame_result.can_context = list(self._recent_can_records)
                
                # 写入缓存（如果启用）
                if self._caching_enabled and self._analysis_cache:
                    self._analysis_cache.write_frame_result(frame_result)
                
                # 发射结果信号
                if should_emit:
                    self.frame_result_ready.emit(frame_result)
                    self._last_result_emit = now
                
                # 专门的事件信号
                if frame_result.event:
                    self.behavior_event_ready.emit(frame_result.event)

                    EventDistributor.instance().register_event(frame_result.event)

                    self._trigger_seat_evaluation(frame_result.event, frame_result)
                
                # 简化的实时监控数据（方便UI直接使用）
                realtime_data = self._frame_to_realtime_data(frame_result)
                if should_emit:
                    self.realtime_monitor_data.emit(realtime_data)

        except Exception as e:
            self._record_error_once(f"_pipeline_error_{str(e)[:30]}", str(e))

        self._processed_count += 1

    def _trigger_seat_evaluation(self, event, frame_result):
        """当检测到驾驶事件时，构造EvaluationTrigger并发送给座椅评测引擎"""
        if not self._seat_evaluation_engine:
            return

        try:
            trigger = self._build_trigger(event, frame_result)
            if trigger is None:
                return

            self._evaluation_queue.append(trigger)

            if not self._eval_queue_timer.isActive() and not self._eval_queue_processing:
                self._eval_queue_timer.start()

        except Exception as e:
            self.logger.error(f"触发座椅评测失败: {e}", exc_info=True)

    def _build_trigger(self, event, frame_result) -> Optional[dict]:
        """构建评测触发器"""
        try:
            data_window = {'pre': 0.5, 'post': 1.5}
            start_time = event.start_time - data_window['pre']
            end_time = event.end_time + data_window['post']

            multi_channel_data = self._build_multi_channel_data(start_time, end_time)

            from ..seat_evaluation.imu_location_config import LOCATION_IDS
            from ..analysis.core_types import INDICATOR_DEFINITIONS

            trigger = {
                'event_id': getattr(event, 'id', f'evt_{int(event.start_time * 1000)}'),
                'event_type': getattr(event, 'type', 'unknown'),
                'source_behavior': getattr(event, 'type', 'unknown'),
                'timestamp': event.start_time,
                'metrics': list(INDICATOR_DEFINITIONS.keys()),
                'data_window': data_window,
                'multi_channel_data': multi_channel_data,
                'locations': LOCATION_IDS,
                'group_tag': 'experimental',
            }

            self.seat_evaluation_triggered.emit(trigger)
            return trigger
        except Exception as e:
            self.logger.error(f"构建评测触发器失败: {e}", exc_info=True)
            return None

    def _process_evaluation_queue(self):
        """处理评测队列（去重、合并重叠事件窗口）"""
        if self._eval_queue_processing:
            return
        self._eval_queue_processing = True

        try:
            processed_ids = set()
            while self._evaluation_queue:
                trigger = self._evaluation_queue.popleft()

                event_id = trigger.get('event_id', '')
                if event_id in processed_ids:
                    continue
                processed_ids.add(event_id)

                result = self._seat_evaluation_engine.evaluate_by_event(trigger)
                if result:
                    trigger['_evaluation_result'] = result
                    self.logger.info(
                        f"座椅评测完成: {trigger['event_id']}, "
                        f"评分={result.overall_score:.2f}, "
                        f"位置数={len(result.location_results)}")
                else:
                    self.logger.warning(f"座椅评测返回空结果: {trigger['event_id']}")
        except Exception as e:
            self.logger.error(f"处理评测队列失败: {e}", exc_info=True)
        finally:
            self._eval_queue_processing = False

    def _build_multi_channel_data(self, start_time: float, end_time: float,
                                  cache=None) -> Dict[str, Any]:
        """从缓存和近期原始记录中提取多通道时间窗口数据

        Args:
            start_time: 起始时间
            end_time: 结束时间
            cache: 可选的外部缓存（如回放控制器的历史缓存），优先于 self._cache 使用

        支持三种数据格式:
            1. can_wide: 单条记录含多通道 (如 ch4_ax, ch4_ay)
            2. can_long: 单条记录含单个IMU (字段: imu_name + Ax_m_s2/Ay_m_s2/Az_m_s2)
            3. floor_imu/pipeline: 标准化记录 (字段: _imu_name + ax/ay/az)

        提取增强:
            - 加速度 ax/ay/az (线性加速度)
            - 角速度 gx/gy/gz (陀螺仪)
            - 采样率自适应检测
            - 对照组数据同步加载 (IMU2/4/6/8/10)

        实验组IMU映射:
            IMU1_头部眉心-1 → head
            IMU3_躯干T8-1 → torso
            IMU5_座垫R点-1 → seat_r
            IMU7_座椅底部-1 → seat_bottom
            IMU9_胸骨剑突-1 → sternum

        对照组IMU映射:
            IMU2_头部眉心-2 → head_ctrl
            IMU4_躯干T8-2 → torso_ctrl
            IMU6_座垫R点-2 → seat_r_ctrl
            IMU8_座椅底部-2 → seat_bottom_ctrl
            IMU10_胸骨剑突-2 → sternum_ctrl
        """
        multi_channel_data = {}

        ch_to_imu_exp = {
            'ch1': 'IMU1_头部眉心-1',
            'ch2': 'IMU3_躯干T8-1',
            'ch3': 'IMU5_座垫R点-1',
            'ch4': 'IMU7_座椅底部-1',
            'ch5': 'IMU9_胸骨剑突-1',
        }

        ch_to_imu_ctrl = {
            'ch1': 'IMU2_头部眉心-2',
            'ch2': 'IMU4_躯干T8-2',
            'ch3': 'IMU6_座垫R点-2',
            'ch4': 'IMU8_座椅底部-2',
            'ch5': 'IMU10_胸骨剑突-2',
        }

        imu_to_ch = {v: k for k, v in ch_to_imu_exp.items()}

        exp_imu_set = set(ch_to_imu_exp.values())
        ctrl_imu_set = set(ch_to_imu_ctrl.values())

        raw_records = list(self._recent_raw_records)
        data_source = "deque"

        cache_to_use = cache or self._cache
        if cache_to_use:
            try:
                cached_records = cache_to_use.query_time_range(start_time - 0.5, end_time + 0.5)
                if cached_records:
                    raw_records = cached_records
                    data_source = "cache"
            except Exception as e:
                self.logger.debug(f"从缓存查询数据失败，使用内存缓冲: {e}")

        if not raw_records:
            raw_records = list(self._recent_raw_records)
            data_source = "deque(fallback)"

        time_filtered = [
            r for r in raw_records
            if start_time - 1.0 <= r.get('rel_time', r.get('timestamp', r.get('_rel_time', 0))) <= end_time + 1.0
        ]

        if not time_filtered:
            self.logger.warning(
                f"[多通道数据] 时间窗口 [{start_time:.3f}, {end_time:.3f}] "
                f"无匹配记录 (数据源: {data_source}, 总记录: {len(raw_records)})"
            )
            time_filtered = raw_records

        if len(time_filtered) < 3:
            self.logger.warning(
                f"[多通道数据] 时间窗口 [{start_time:.3f}, {end_time:.3f}] "
                f"记录数严重不足: {len(time_filtered)} < 3 (数据源: {data_source}, "
                f"缓存命中: {'是' if data_source == 'cache' else '否'})"
            )
            return multi_channel_data

        format = self._detect_record_format(time_filtered)
        self.logger.debug(
            f"[多通道数据] 格式: {format}, 记录数: {len(time_filtered)}, "
            f"数据源: {data_source}, 时间窗口: [{start_time:.3f}, {end_time:.3f}]"
        )

        import numpy as np

        def _extract_gyro(record, data_ch=None):
            gx = record.get('gx', record.get('Gx_rad_s',
                 record.get(f'{data_ch}_f3_Gyro_rad/s' if data_ch else None,
                 record.get('Gx_rad_s', None))))
            gy = record.get('gy', record.get('Gy_rad_s',
                 record.get(f'{data_ch}_f4_Gyro_rad/s' if data_ch else None,
                 record.get('Gy_rad_s', None))))
            gz = record.get('gz', record.get('Gz_rad_s',
                 record.get(f'{data_ch}_f5_Gyro_rad/s' if data_ch else None,
                 record.get('Gz_rad_s', None))))
            return gx, gy, gz

        def _parse_gyro_vals(gx, gy, gz):
            try:
                gx_val = float(gx) if gx is not None else None
                gy_val = float(gy) if gy is not None else None
                gz_val = float(gz) if gz is not None else None
                return gx_val, gy_val, gz_val
            except (ValueError, TypeError):
                return None, None, None

        def _detect_sample_rate(records_dict):
            sr = 100.0
            for imu_name, data in records_dict.items():
                times = data.get('timestamps', [])
                if times and len(times) >= 2:
                    t_min, t_max = np.min(times), np.max(times)
                    if t_max > t_min:
                        sr = max(5.0, min(1000.0, len(times) / (t_max - t_min)))
                break
            return float(sr)

        if format == 'wide':
            available = set()
            for r in time_filtered[:100]:
                available.update(DataBridge._detect_available_channels(r))
            if not available:
                available = {'ch1', 'ch3', 'ch4', 'ch5'}

            for data_ch in available:
                exp_imu_name = ch_to_imu_exp.get(data_ch, '')
                ctrl_imu_name = ch_to_imu_ctrl.get(data_ch, '')
                if not exp_imu_name and not ctrl_imu_name:
                    continue

                ax_vals, ay_vals, az_vals = [], [], []
                gx_vals, gy_vals, gz_vals = [], [], []
                timestamps = []

                for record in time_filtered:
                    ch_field = record.get('channel', '')
                    if ch_field and ch_field != data_ch:
                        continue

                    ax = record.get(f'{data_ch}_f0_Accel_m/s2',
                         record.get(f'{data_ch}_ax',
                         record.get('ax',
                         record.get('Ax_m_s2', None))))
                    ay = record.get(f'{data_ch}_f1_Accel_m/s2',
                         record.get(f'{data_ch}_ay',
                         record.get('ay',
                         record.get('Ay_m_s2', None))))
                    az = record.get(f'{data_ch}_f2_Accel_m/s2',
                         record.get(f'{data_ch}_az',
                         record.get(f'{data_ch}_f11_AccelZ_m/s2',
                         record.get('az',
                         record.get('Az_m_s2', None)))))

                    if ax is not None:
                        try:
                            ax_vals.append(float(ax))
                            ay_vals.append(float(ay) if ay is not None else 0.0)
                            az_vals.append(float(az) if az is not None else 0.0)
                            ts = record.get('rel_time', record.get('timestamp', record.get('_rel_time', 0)))
                            timestamps.append(float(ts))
                        except (ValueError, TypeError):
                            continue

                    gx, gy, gz = _extract_gyro(record, data_ch)
                    gxv, gyv, gzv = _parse_gyro_vals(gx, gy, gz)
                    if gxv is not None:
                        gx_vals.append(gxv)
                        gy_vals.append(gyv if gyv is not None else 0.0)
                        gz_vals.append(gzv if gzv is not None else 0.0)

                if len(ax_vals) >= 5:
                    if exp_imu_name:
                        exp_entry = {
                            'ax': np.array(ax_vals),
                            'ay': np.array(ay_vals),
                            'az': np.array(az_vals),
                            'timestamps': list(timestamps),
                        }
                        if len(gx_vals) >= 5:
                            exp_entry['gx'] = np.array(gx_vals)
                            exp_entry['gy'] = np.array(gy_vals)
                            exp_entry['gz'] = np.array(gz_vals)
                        multi_channel_data[exp_imu_name] = exp_entry

                    if ctrl_imu_name:
                        ctrl_entry = {
                            'ax': np.array(ax_vals),
                            'ay': np.array(ay_vals),
                            'az': np.array(az_vals),
                            'timestamps': list(timestamps),
                        }
                        if len(gx_vals) >= 5:
                            ctrl_entry['gx'] = np.array(gx_vals)
                            ctrl_entry['gy'] = np.array(gy_vals)
                            ctrl_entry['gz'] = np.array(gz_vals)
                        multi_channel_data[ctrl_imu_name] = ctrl_entry

        else:
            grouped = {}
            for record in time_filtered:
                imu = record.get('_imu_name', record.get('imu_name', record.get('_source_name', '')))
                if not imu:
                    ch = record.get('channel', '')
                    imu = ch_to_imu_exp.get(ch, '') or ch_to_imu_ctrl.get(ch, '')

                if not imu:
                    continue

                ax = record.get('ax', record.get('Ax_m_s2', None))
                ay = record.get('ay', record.get('Ay_m_s2', None))
                az = record.get('az', record.get('Az_m_s2', None))

                if ax is None:
                    continue

                try:
                    ax_val = float(ax)
                    ay_val = float(ay) if ay is not None else 0.0
                    az_val = float(az) if az is not None else 0.0
                    ts = record.get('rel_time', record.get('timestamp', record.get('_rel_time', 0)))
                except (ValueError, TypeError):
                    continue

                if imu not in grouped:
                    grouped[imu] = {'ax': [], 'ay': [], 'az': [], 'timestamps': [], 'gx': [], 'gy': [], 'gz': []}

                grouped[imu]['ax'].append(ax_val)
                grouped[imu]['ay'].append(ay_val)
                grouped[imu]['az'].append(az_val)
                grouped[imu]['timestamps'].append(float(ts))

                gx, gy, gz = _extract_gyro(record)
                gxv, gyv, gzv = _parse_gyro_vals(gx, gy, gz)
                if gxv is not None:
                    grouped[imu]['gx'].append(gxv)
                    grouped[imu]['gy'].append(gyv if gyv is not None else 0.0)
                    grouped[imu]['gz'].append(gzv if gzv is not None else 0.0)

            for imu_name, data in grouped.items():
                if len(data['ax']) >= 5:
                    entry = {
                        'ax': np.array(data['ax']),
                        'ay': np.array(data['ay']),
                        'az': np.array(data['az']),
                        'timestamps': data['timestamps'],
                    }
                    if len(data['gx']) >= 5:
                        entry['gx'] = np.array(data['gx'])
                        entry['gy'] = np.array(data['gy'])
                        entry['gz'] = np.array(data['gz'])
                    multi_channel_data[imu_name] = entry

        sr = _detect_sample_rate(multi_channel_data)
        multi_channel_data['_sample_rate'] = sr
        multi_channel_data['_exp_imu_set'] = exp_imu_set
        multi_channel_data['_ctrl_imu_set'] = ctrl_imu_set

        exp_count = sum(1 for k in multi_channel_data if k in exp_imu_set)
        ctrl_count = sum(1 for k in multi_channel_data if k in ctrl_imu_set)

        if multi_channel_data:
            exp_channels = [k for k in multi_channel_data if k in exp_imu_set]
            ctrl_channels = [k for k in multi_channel_data if k in ctrl_imu_set]
            self.logger.info(
                f"[多通道数据] 提取成功: {exp_count}个实验组({exp_channels}) + "
                f"{ctrl_count}个对照组({ctrl_channels}), "
                f"采样率≈{sr:.1f}Hz, 数据源: {data_source}, "
                f"时间窗口: [{start_time:.3f}, {end_time:.3f}]"
            )
        else:
            self.logger.warning(
                f"[多通道数据] 提取失败: 时间窗口 [{start_time:.3f}, {end_time:.3f}] "
                f"未提取到任何通道 (数据源: {data_source})"
            )

        return multi_channel_data

    def build_display_channel_data(self, start_time: float, end_time: float) -> Dict[str, List[Dict]]:
        """从缓存提取事件时间窗口的原始数据，返回扁平list格式用于UI展示

        与 _build_multi_channel_data 的区别：
            - _build_multi_channel_data: 返回 {imu: {ax: np.array, ay: np.array, ...}} → 给评测引擎用
            - build_display_channel_data: 返回 {imu: [{timestamp, ax, ay, az, ...}, ...]} → 给UI展示用
        """
        ch_to_imu_exp = {
            'ch1': 'IMU1_头部眉心-1', 'ch2': 'IMU3_躯干T8-1',
            'ch3': 'IMU5_座垫R点-1', 'ch4': 'IMU7_座椅底部-1',
            'ch5': 'IMU9_胸骨剑突-1',
        }

        ch_to_imu_ctrl = {
            'ch1': 'IMU2_头部眉心-2', 'ch2': 'IMU4_躯干T8-2',
            'ch3': 'IMU6_座垫R点-2', 'ch4': 'IMU8_座椅底部-2',
            'ch5': 'IMU10_胸骨剑突-2',
        }

        raw_records = list(self._recent_raw_records)
        if self._cache:
            try:
                cached = self._cache.query_time_range(start_time - 0.5, end_time + 0.5)
                if cached:
                    raw_records = cached
            except Exception:
                pass

        if not raw_records:
            raw_records = list(self._recent_raw_records)

        time_filtered = [
            r for r in raw_records
            if start_time - 1.0 <= r.get('rel_time', r.get('timestamp', r.get('_rel_time', 0))) <= end_time + 1.0
        ]
        if not time_filtered:
            time_filtered = raw_records

        fmt = self._detect_record_format(time_filtered)
        display_data: Dict[str, List[Dict]] = {}

        if fmt == 'wide':
            ch_to_imu_all = {**ch_to_imu_exp, **ch_to_imu_ctrl}
            for data_ch, imu_name in ch_to_imu_all.items():
                records = []
                for r in time_filtered:
                    ch_field = r.get('channel', '')
                    if ch_field and ch_field != data_ch:
                        continue
                    ax = r.get(f'{data_ch}_f0_Accel_m_s2', r.get(f'{data_ch}_ax', r.get('ax', r.get('Ax_m_s2'))))
                    ay = r.get(f'{data_ch}_f1_Accel_m_s2', r.get(f'{data_ch}_ay', r.get('ay', r.get('Ay_m_s2'))))
                    az = r.get(f'{data_ch}_f2_Accel_m_s2', r.get(f'{data_ch}_az', r.get(f'{data_ch}_f11_AccelZ_m_s2', r.get('az', r.get('Az_m_s2')))))
                    if ax is None:
                        continue
                    try:
                        ts = float(r.get('rel_time', r.get('timestamp', r.get('_rel_time', 0))))
                        records.append({'timestamp': ts, 'ax': float(ax), 'ay': float(ay or 0), 'az': float(az or 0)})
                    except (ValueError, TypeError):
                        continue
                if records:
                    display_data[imu_name] = records
        else:
            for r in time_filtered:
                imu = r.get('_imu_name', r.get('imu_name', r.get('_source_name', '')))
                if not imu:
                    ch = r.get('channel', '')
                    imu = ch_to_imu_exp.get(ch, '') or ch_to_imu_ctrl.get(ch, '')
                if not imu:
                    continue
                ax = r.get('ax', r.get('Ax_m_s2'))
                ay = r.get('ay', r.get('Ay_m_s2'))
                az = r.get('az', r.get('Az_m_s2'))
                if ax is None:
                    continue
                try:
                    ts = float(r.get('rel_time', r.get('timestamp', r.get('_rel_time', 0))))
                    entry = {'timestamp': ts, 'ax': float(ax), 'ay': float(ay or 0), 'az': float(az or 0)}
                except (ValueError, TypeError):
                    continue
                display_data.setdefault(imu, []).append(entry)

        self.logger.debug(
            f"展示数据 [{start_time:.2f}, {end_time:.2f}]: "
            f"{len(display_data)} 个通道, 总记录={sum(len(v) for v in display_data.values())}"
        )
        return display_data

    @staticmethod
    def _detect_record_format(records: list) -> str:
        """检测记录格式类型"""
        if not records:
            return 'unknown'
        for r in records[:50]:
            if any(k.startswith('ch') and ('_f0_Accel' in k or '_f0_Gyro' in k or '_ax' in k) for k in r):
                return 'wide'
            if ('_imu_name' in r or 'imu_name' in r) and ('ax' in r or 'Ax_m_s2' in r):
                return 'long'
        return 'long'

    def _frame_to_realtime_data(self, frame_result) -> Dict[str, Any]:
        """把FrameResult转为实时监控友好的字典
        
        注意：UI显示时，把m/s转回km/h
        """
        from .core_types import DrivingState, RiskLevel
        
        data = {
            'timestamp': frame_result.timestamp,
            'ax': frame_result.ax,
            'ay': frame_result.ay,
            'az': frame_result.az,
            'gx': frame_result.gx,
            'gy': frame_result.gy,
            'gz': frame_result.gz,
            'speed_ms': frame_result.speed,
            'speed_kmh': frame_result.speed / DataBridge.KMH_TO_MS,  # UI显示用
            'wheel': frame_result.wheel,
            'state': frame_result.state.value if hasattr(frame_result.state, 'value') else str(frame_result.state),
        }
        
        if frame_result.features:
            data['features'] = {
                'temporal': dict(frame_result.features.temporal),
                'spectral': dict(frame_result.features.spectral),
            }
        
        if frame_result.event:
            data['event'] = {
                'type': frame_result.event.type,
                'category': frame_result.event.category.value if hasattr(frame_result.event.category, 'value') else str(frame_result.event.category),
                'confidence': frame_result.event.confidence,
                'risk_level': frame_result.event.risk_level.value if hasattr(frame_result.event.risk_level, 'value') else str(frame_result.event.risk_level),
                'risk_score': frame_result.event.risk_score,
            }
        
        return data

    _error_cache = {}
    def _record_error_once(self, error_key: str, error_detail: str):
        prev = self._error_cache.get(error_key, 0)
        if time.time() - prev > 300:
            self._error_cache[error_key] = time.time()
            self.logger.debug(f"处理数据记录失败: {error_detail}")

    def _flush_batch(self):
        if not self._batch_buffer:
            return
        batch = list(self._batch_buffer)
        self._batch_buffer.clear()
        if not self._suppress_ui_signals:
            self.sensor_data_batch_received.emit(batch)

    def start_processing(self):
        """启动数据处理"""
        if self.is_running:
            self.logger.warning("DataBridge 已在运行中")
            return
        self.is_running = True
        self.bridge_status_changed.emit("running")
        self.logger.info("DataBridge 数据处理已启动")

    def stop_processing(self):
        """停止数据处理"""
        self.is_running = False

        while self._process_queue:
            record = self._process_queue.popleft()
            try:
                self._process_single(record)
            except Exception:
                pass

        self._flush_batch()
        self.bridge_status_changed.emit("stopped")
        self._persister.close()
        
        # 关闭分析结果缓存
        if self._analysis_cache:
            self._analysis_cache.close()
            self._analysis_cache = None
            self._caching_enabled = False
            
        self.logger.info("DataBridge 数据处理已停止")
    
    def enable_result_caching(self, db_path: str = None, reset_event_mapper: bool = True):
        """启用分析结果缓存
        
        Args:
            db_path: 缓存数据库路径
            reset_event_mapper: 是否重置事件记录器
        """
        if self._caching_enabled and self._analysis_cache:
            self.logger.warning("分析结果缓存已启用")
            return
        
        try:
            self._analysis_cache = AnalysisResultCache(db_path)
            self._caching_enabled = True
            self.logger.info(f"分析结果缓存已启用: {self._analysis_cache.db_path}")

            EventDistributor.instance().set_analysis_cache(self._analysis_cache)

            if reset_event_mapper:
                from ..data_processing.event_data_mapper import reset_event_mapper
                reset_event_mapper()
                self.logger.info("事件记录器已重置")
                
        except Exception as e:
            self.logger.error(f"启用分析结果缓存失败: {e}")
    
    def disable_result_caching(self):
        """禁用分析结果缓存"""
        if not self._caching_enabled:
            return

        try:
            EventDistributor.instance().clear()
            if self._analysis_cache:
                self._analysis_cache.close()
                self._analysis_cache = None
            self._caching_enabled = False
            self.logger.info("分析结果缓存已禁用")
        except Exception as e:
            self.logger.error(f"禁用分析结果缓存失败: {e}")
    
    def get_analysis_cache(self):
        """获取分析结果缓存"""
        return self._analysis_cache

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        if self._data_queue:
            return self._data_queue[-1]
        return None

    def reload_config(self):
        try:
            from .core_types import VehicleConfig
            self._pipeline = AnalysisPipeline(VehicleConfig(), primary_imu_names=[self.PRIMARY_IMU_NAME])
            self.logger.info(f"五层分析管道已重新初始化 (主IMU: {self.PRIMARY_IMU_NAME})")
        except Exception as e:
            self.logger.error(f"重新初始化五层分析管道失败: {e}")

    def set_suppress_ui_signals(self, suppress: bool):
        if self._suppress_ui_signals != suppress:
            self._suppress_ui_signals = suppress

    def get_stats(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "total_count": self._total_count,
            "processed_count": self._processed_count,
            "queue_size": len(self._data_queue),
            "pipeline_ready": self._pipeline is not None,
        }

    def get_pipeline(self):
        """获取分析管道（供外部使用）"""
        return self._pipeline

    def analyze_behavior_batch(
        self,
        records: List[Dict[str, Any]],
        ref_channel: str = 'ch1',
        ref_imu: str = 'IMU1_头部眉心-1',
    ) -> Dict[str, Any]:
        """离线批量驾驶行为分析（供全量统计标签页调用）

        封装完整的 SpeedPreprocessor → DrivingEventDetector 流水线，
        返回可直接填入 UI 的事件列表和统计摘要。

        Args:
            records: 解析器输出/CSV解析的记录列表
            ref_channel: 参考IMU通道
            ref_imu: 参考IMU名称

        Returns:
            {
                'events': List[Dict],         # 事件列表（含 22 种类型）
                'summary': Dict,              # 按类型统计
                'stats': Dict,                # 管道统计（含 vehicle_accel 范围）
                'vehicle_accel_range': Tuple[float, float],
            }
        """
        from .layer0_preprocessing.speed_preprocessor import SpeedPreprocessor
        from .layer3_maneuver_segmentation.event_detector import DrivingEventDetector

        # 修复 CSV BOM 问题：\ufeffrel_time → rel_time
        _bom_keys = {k: k.lstrip('\ufeff') for k in list(records[0].keys()) if k.startswith('\ufeff')} if records else {}
        if _bom_keys:
            for r in records:
                for old_k, new_k in _bom_keys.items():
                    if old_k in r:
                        r[new_k] = r.pop(old_k)
            self.logger.debug(f"[DataBridge] Stripped BOM from keys: {_bom_keys}")

        # 去重前：按 ref_imu 过滤通道（若记录有 channel/imu_name 字段）
        channel_records = records
        if ref_imu:
            with_channel = [r for r in records if r.get('channel') and r.get('imu_name')]
            if with_channel:
                # 自动检测 IMU 对应通道
                imu_channels = {}
                for r in with_channel:
                    imu_channels.setdefault(r['imu_name'], set()).add(r['channel'])
                matched_channel = None
                if ref_imu in imu_channels:
                    # 取该 IMU 的第一个通道
                    matched_channel = sorted(imu_channels[ref_imu])[0]
                    self.logger.debug(
                        f"[DataBridge] Auto-detected channel '{matched_channel}' for IMU '{ref_imu}'"
                    )
                # 优先用 ref_channel，否则用自动检测的
                use_channel = ref_channel if ref_channel else matched_channel
                if use_channel:
                    channel_records = [r for r in records
                                       if r.get('channel', '') == use_channel
                                       and r.get('imu_name', '') == ref_imu]
                    if channel_records:
                        self.logger.info(
                            f"[DataBridge] Filtered {len(channel_records)} records for "
                            f"channel='{use_channel}', imu='{ref_imu}'"
                        )
                    else:
                        # fallback: 只用 imu_name 过滤
                        channel_records = [r for r in records
                                           if r.get('imu_name', '') == ref_imu]
                        self.logger.warning(
                            f"[DataBridge] Channel filter failed, using IMU-only: "
                            f"{len(channel_records)} records"
                        )
                if not channel_records:
                    # fallback: ref_imu 不匹配 → 尝试通过 ref_channel 反查 IMU
                    channel_to_imu = {}
                    for imu_name, channels in imu_channels.items():
                        for ch in channels:
                            channel_to_imu.setdefault(ch, set()).add(imu_name)
                    if ref_channel and ref_channel in channel_to_imu:
                        auto_imu = sorted(channel_to_imu[ref_channel])[0]
                        self.logger.warning(
                            f"[DataBridge] ref_imu='{ref_imu}' not found, "
                            f"auto-detected imu='{auto_imu}' from channel='{ref_channel}'"
                        )
                        channel_records = [r for r in records
                                           if r.get('channel', '') == ref_channel
                                           and r.get('imu_name', '') == auto_imu]
                    if not channel_records:
                        # 最终fallback: 只按 channel 过滤（如有）
                        if ref_channel:
                            channel_records = [r for r in records
                                               if r.get('channel', '') == ref_channel]
                            self.logger.warning(
                                f"[DataBridge] IMU+channel filter failed, "
                                f"channel-only filter: {len(channel_records)} records"
                            )
                    if not channel_records:
                        self.logger.warning(f"[DataBridge] All filters failed, using all {len(records)} records")
                        channel_records = records

        # 去重：多通道数据有重复时间戳，取首次出现的记录
        seen_ts = set()
        deduped = []
        for r in sorted(channel_records, key=lambda r: float(
                r.get('rel_time', r.get('timestamp', 0)) or 0)):
            ts = r.get('rel_time', r.get('timestamp', None))
            if ts is None:
                deduped.append(r)
            else:
                ts_key = round(float(ts), 6)
                if ts_key not in seen_ts:
                    seen_ts.add(ts_key)
                    deduped.append(r)

        self.logger.info(
            f"[DataBridge] Dedup: {len(channel_records)} -> {len(deduped)} records "
            f"(ref: channel={ref_channel}, imu={ref_imu})"
        )

        # Layer0: 速度预处理
        preproc = SpeedPreprocessor()
        enriched = preproc.enrich_all(deduped)
        accel_min = float(preproc.vehicle_accel_array.min()) if preproc.vehicle_accel_array is not None else 0.0
        accel_max = float(preproc.vehicle_accel_array.max()) if preproc.vehicle_accel_array is not None else 0.0

        # 全量事件检测（使用 enriched 记录，含 speed_ma/speed_std/wheel_std/accel_ma/vehicle_accel）
        detector = DrivingEventDetector.from_records(enriched, ref_channel, ref_imu)
        events = detector.detect_all()
        summary = detector.get_summary()

        self.logger.info(
            f"[DataBridge] Offline behavior analysis done: {summary['total']} events, "
            f"{len(summary['by_type'])} types, "
            f"vehicle_accel=[{accel_min:.2f}, {accel_max:.2f}] m/s²"
        )

        return {
            'events': [e.to_dict() for e in events],
            'raw_events': list(events),  # 原始 Event 对象，供 analyze_records_batch 使用
            'summary': summary,
            'vehicle_accel_range': (accel_min, accel_max),
            'stats': {
                'total_frames': len(records),
                'enriched_frames': len(enriched),
                'event_types_detected': len(summary['by_type']),
            },
        }

    def analyze_records_batch(
        self,
        records: List[Dict[str, Any]],
        ref_imu: str = 'IMU1_头部眉心-1',
    ) -> Dict[str, Any]:
        """流式回放路径的批量驾驶行为分析。

        与 analyze_behavior_batch 使用相同的 SpeedPreprocessor +
        DrivingEventDetector 完整管线，但额外将结果：
        - 写入 analysis_cache（write_maneuver_events）
        - 注册到 EventDistributor（register_event）
        - 发射 behavior_event_ready 信号
        - 发射 generated_events 信号（供 replay 控制器消费）
        - 设置 _batch_analyzed 标志，抑制后续 streaming pipeline

        Args:
            records: 来自 query_records_raw 的记录（speed 为 km/h）
            ref_imu: 参考IMU名称

        Returns:
            {'events': [...], 'summary': {...}, 'stats': {...}}
        """
        import uuid
        from .core_types import ManeuverEvent, BehaviorCategory, RiskLevel, BEHAVIOR_TAXONOMY

        # 1. 调用完整分析管线（与全量统计标签页同一路径）
        result = self.analyze_behavior_batch(records, ref_channel='ch1', ref_imu=ref_imu)
        raw_events = result.get('raw_events', [])
        events = result['events']

        self.logger.info(
            f"[DataBridge] analyze_records_batch: {len(events)} events from "
            f"{len(records)} records, accel_range={result['vehicle_accel_range']}"
        )

        if not raw_events:
            self._batch_analyzed = True
            return result

        # 2. Event → ManeuverEvent 转换 + 分类映射
        maneuver_events = []
        for ev in raw_events:
            try:
                cat = self._map_event_type_to_category(ev.event_type)
                risk = self._map_event_type_to_risk(ev.event_type)
                features = dict(ev.features) if ev.features else {}
                features['event_name'] = ev.event_name
                features['detector_event_id'] = ev.event_id

                me = ManeuverEvent(
                    id=f"evt_{ev.event_id}",
                    type=ev.event_type,
                    category=cat,
                    start_time=float(ev.t_start),
                    end_time=float(ev.t_end),
                    duration=float(ev.duration_s),
                    confidence=float(ev.confidence),
                    detection_method='full_pipeline',
                    risk_level=risk,
                    risk_score=self._estimate_risk_score(risk, ev.confidence),
                    metadata=features,
                )
                maneuver_events.append(me)
            except Exception as e:
                self.logger.warning(
                    f"[DataBridge] Event→ManeuverEvent 转换失败: {e}"
                )
                continue

        self.logger.info(
            f"[DataBridge] Converted {len(maneuver_events)} Event → ManeuverEvent"
        )

        # 3. 写入 analysis_cache
        if self._caching_enabled and self._analysis_cache:
            try:
                self._analysis_cache.write_maneuver_events(maneuver_events)
                self.logger.info(
                    f"[DataBridge] Wrote {len(maneuver_events)} events to cache"
                )
            except Exception as e:
                self.logger.error(f"[DataBridge] Failed to cache events: {e}")

        # 4. 注册到 EventDistributor
        try:
            dist = EventDistributor.instance()
            for me in maneuver_events:
                dist.register_event(me)
            self.logger.info(
                f"[DataBridge] Registered {len(maneuver_events)} events to distributor"
            )
        except Exception as e:
            self.logger.error(f"[DataBridge] Failed to register events: {e}")

        # 5. 发射 generated_events（供 replay 控制器消费，更新回放栏事件列表）
        try:
            self.generated_events.emit(maneuver_events)
        except Exception as e:
            self.logger.warning(f"[DataBridge] generated_events emit failed: {e}")

        # 6. 逐事件发射 behavior_event_ready（兼容现有 UI 订阅）
        for me in maneuver_events:
            try:
                self.behavior_event_ready.emit(me)
            except Exception:
                pass

        # 7. 标记批量分析已完成，后续 per-tick streaming pipeline 将被跳过
        self._batch_analyzed = True
        self.logger.info(
            f"[DataBridge] Batch analysis complete, streaming pipeline suppressed"
        )

        return result

    @staticmethod
    def _map_event_type_to_category(event_type: str):
        """将事件类型字符串映射到 BehaviorCategory"""
        from .core_types import BehaviorCategory, BEHAVIOR_TAXONOMY
        for cat, types in BEHAVIOR_TAXONOMY.items():
            if event_type in types:
                return cat
        return BehaviorCategory.NORMAL

    @staticmethod
    def _map_event_type_to_risk(event_type: str):
        """根据事件类型推断风险等级"""
        from .core_types import RiskLevel
        if event_type in ('emergency_braking', 'severe_bump', 'rollover_risk', 'skid_risk'):
            return RiskLevel.DANGER
        if event_type in ('aggressive_acceleration', 'aggressive_deceleration',
                           'rapid_direction_change', 'weaving', 'cornering_braking'):
            return RiskLevel.WARNING
        if event_type in ('stopped', 'constant_speed', 'straight_driving',
                           'lane_keeping', 'normal_acceleration', 'normal_deceleration'):
            return RiskLevel.SAFE
        return RiskLevel.CAUTION

    @staticmethod
    def _estimate_risk_score(risk_level, confidence: float) -> float:
        """根据风险等级和置信度估算风险评分"""
        base = {
            'SAFE': 0.1, 'CAUTION': 0.4, 'WARNING': 0.7, 'DANGER': 0.9,
        }
        from .core_types import RiskLevel
        if isinstance(risk_level, RiskLevel):
            risk_str = risk_level.value
        else:
            risk_str = str(risk_level)
        return round(base.get(risk_str, 0.3) * min(1.0, max(0.1, confidence)), 2)

    def mark_batch_analyzed(self):
        """标记批量分析已完成，抑制后续 streaming pipeline"""
        self._batch_analyzed = True

    def reset_batch_analyzed(self):
        """重置批量分析标志（数据清除时调用）"""
        self._batch_analyzed = False

    @property
    def is_batch_analyzed(self) -> bool:
        """是否已完成批量分析"""
        return self._batch_analyzed

    def clear_all_data(self):
        self.logger.info("DataBridge 正在清除所有已加载数据...")

        self._data_queue.clear()
        self._batch_buffer.clear()
        self._process_queue.clear()
        self._recent_raw_records.clear()
        self._recent_can_records.clear()
        self._total_count = 0
        self._processed_count = 0

        if self._eval_queue_timer.isActive():
            self._eval_queue_timer.stop()
        self._evaluation_queue.clear()
        self._eval_queue_processing = False

        if self._pipeline:
            try:
                self._pipeline.reset()
                self.logger.info("分析管道状态已重置")
            except Exception as e:
                self.logger.warning(f"重置分析管道失败: {e}")

        if self._analysis_cache:
            try:
                self._analysis_cache.close()
            except Exception:
                pass
            self._analysis_cache = None
        self._caching_enabled = False
        self._batch_analyzed = False

        EventDistributor.instance().clear()

        self.logger.info("DataBridge 所有已加载数据已清除")

