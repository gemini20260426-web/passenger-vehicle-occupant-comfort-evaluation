#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础行为分析模块 v2.0 — 五层智能驾驶分析架构
基于物理信息增强的分层状态推理系统

架构：
  Layer 1: 信号处理（滤波/校准/重力补偿/质量评估）
  Layer 2: 特征工程（时域/频域/运动学/物理特征）
  Layer 3: 机动分割（状态机/机动检测/时序一致性）
  Layer 4: 行为分类（规则引擎/统计分类/上下文自适应）
  Layer 5: 风险评估（稳定性/碰撞/舒适性/综合评分）

兼容性：保持与旧版 base_analyzer.py 完全相同的 API 接口
"""

import numpy as np
import logging
import time
from typing import Dict, List, Any, Optional
from collections import deque
import gc
from datetime import datetime

try:
    from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker, QObject
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from .core_types import (
    VehicleConfig, BEHAVIOR_LABELS_CN, BEHAVIOR_TYPES_V2,
    BehaviorCategory, RiskLevel, DrivingState,
)
from .pipeline import AnalysisPipeline as V2Pipeline

BEHAVIOR_TYPES = [
    "normal",
    "急刹车",
    "左转",
    "右转",
    "加速",
    "减速",
    "匀速直线",
    "停车",
    "U型转弯",
    "蛇形驾驶",
    "急速变向",
    "大半径转弯",
    "正常加速",
    "激进加速",
    "正常刹车",
    "激进刹车",
    "变道",
]


class VehicleParameters:
    VEHICLE_MASS = 3500
    VEHICLE_Iz = 5500
    WHEELBASE = 3.5
    CG_TO_FRONT = 1.8
    CG_TO_REAR = 1.7
    Cf = 180000
    Cr = 180000
    STEERING_RATIO = 15


class DrivingThresholds:
    KEY_MAP = {
        'small_steering_angle_threshold': 'SMALL_STEERING_ANGLE_THRESHOLD',
        'acceleration_positive_threshold': 'ACCELERATION_POSITIVE_THRESHOLD',
        'acceleration_negative_threshold': 'ACCELERATION_NEGATIVE_THRESHOLD',
        'steering_angle_turn_threshold': 'STEERING_ANGLE_TURN_THRESHOLD',
        'z_angular_velocity_turn_threshold': 'Z_ANGULAR_VELOCITY_TURN_THRESHOLD',
        'skid_acceleration_change_rate_threshold': 'SKID_ACCELERATION_CHANGE_RATE_THRESHOLD',
        'skid_z_angular_velocity_threshold': 'SKID_Z_ANGULAR_VELOCITY_THRESHOLD',
        'emergency_brake_acceleration_threshold': 'EMERGENCY_BRAKE_ACCELERATION_THRESHOLD',
        'emergency_brake_speed_drop_threshold': 'EMERGENCY_BRAKE_SPEED_DROP_THRESHOLD',
        'curve_steering_angle_threshold': 'CURVE_STEERING_ANGLE_THRESHOLD',
        'curve_acceleration_positive_threshold': 'CURVE_ACCELERATION_POSITIVE_THRESHOLD',
        'curve_acceleration_negative_threshold': 'CURVE_ACCELERATION_NEGATIVE_THRESHOLD',
        'curve_z_angular_velocity_speed_ratio_low': 'CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_LOW',
        'curve_z_angular_velocity_speed_ratio_high': 'CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_HIGH',
        'snake_steering_angle_change_threshold': 'SNAKE_STEERING_ANGLE_CHANGE_THRESHOLD',
        'rapid_direction_change_steering_angle_threshold': 'RAPID_DIRECTION_CHANGE_STEERING_ANGLE_THRESHOLD',
        'steering_angle_lane_change_threshold': 'STEERING_ANGLE_LANE_CHANGE_THRESHOLD',
        'x_acceleration_lane_change_threshold': 'X_ACCELERATION_LANE_CHANGE_THRESHOLD',
        'large_radius_turn_steering_angle_low': 'LARGE_RADIUS_TURN_STEERING_ANGLE_LOW',
        'large_radius_turn_steering_angle_high': 'LARGE_RADIUS_TURN_STEERING_ANGLE_HIGH',
        'large_radius_turn_z_angular_velocity_low': 'LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_LOW',
        'large_radius_turn_z_angular_velocity_high': 'LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_HIGH',
        'u_turn_steering_angle_threshold': 'U_TURN_STEERING_ANGLE_THRESHOLD',
        'u_turn_z_angular_velocity_threshold': 'U_TURN_Z_ANGULAR_VELOCITY_THRESHOLD',
        'acc_speed_range': 'ACC_SPEED_RANGE',
        'acc_acceleration_range': 'ACC_ACCELERATION_RANGE',
        'a_acc_acceleration_threshold': 'A_ACC_ACCELERATION_THRESHOLD',
        'a_acc_speed_range': 'A_ACC_SPEED_RANGE',
        'brake_acceleration_low': 'BRAKE_ACCELERATION_LOW',
        'brake_acceleration_high': 'BRAKE_ACCELERATION_HIGH',
        'a_brake_acceleration_threshold': 'A_BRAKE_ACCELERATION_THRESHOLD',
        'a_brake_speed_drop_threshold': 'A_BRAKE_SPEED_DROP_THRESHOLD',
        'constant_speed_std_threshold': 'CONSTANT_SPEED_STD_THRESHOLD',
        'constant_speed_accel_threshold': 'CONSTANT_SPEED_ACCEL_THRESHOLD',
        'parking_speed_threshold': 'PARKING_SPEED_THRESHOLD',
        'parking_accel_threshold': 'PARKING_ACCEL_THRESHOLD',
    }

    def __init__(self, config=None):
        self.SMALL_STEERING_ANGLE_THRESHOLD = 1.0
        self.ACCELERATION_POSITIVE_THRESHOLD = 0.02
        self.ACCELERATION_NEGATIVE_THRESHOLD = -0.02
        self.STEERING_ANGLE_TURN_THRESHOLD = 2.0
        self.Z_ANGULAR_VELOCITY_TURN_THRESHOLD = 0.01
        self.SKID_ACCELERATION_CHANGE_RATE_THRESHOLD = 0.2
        self.SKID_Z_ANGULAR_VELOCITY_THRESHOLD = 0.05
        self.EMERGENCY_BRAKE_ACCELERATION_THRESHOLD = -2.0
        self.EMERGENCY_BRAKE_SPEED_DROP_THRESHOLD = 0.05
        self.CURVE_STEERING_ANGLE_THRESHOLD = 3.0
        self.CURVE_ACCELERATION_POSITIVE_THRESHOLD = 0.02
        self.CURVE_ACCELERATION_NEGATIVE_THRESHOLD = -0.02
        self.CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_LOW = 0.0002
        self.CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_HIGH = 0.002
        self.SNAKE_STEERING_ANGLE_CHANGE_THRESHOLD = 3.0
        self.RAPID_DIRECTION_CHANGE_STEERING_ANGLE_THRESHOLD = 3.0
        self.STEERING_ANGLE_LANE_CHANGE_THRESHOLD = 2.0
        self.X_ACCELERATION_LANE_CHANGE_THRESHOLD = 0.02
        self.LARGE_RADIUS_TURN_STEERING_ANGLE_LOW = 2.0
        self.LARGE_RADIUS_TURN_STEERING_ANGLE_HIGH = 10.0
        self.LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_LOW = 0.01
        self.LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_HIGH = 0.05
        self.U_TURN_STEERING_ANGLE_THRESHOLD = 15.0
        self.U_TURN_Z_ANGULAR_VELOCITY_THRESHOLD = 0.08
        self.ACC_SPEED_RANGE = 5.0
        self.ACC_ACCELERATION_RANGE = 0.1
        self.A_ACC_ACCELERATION_THRESHOLD = 0.3
        self.A_ACC_SPEED_RANGE = 10.0
        self.BRAKE_ACCELERATION_LOW = -0.3
        self.BRAKE_ACCELERATION_HIGH = -0.1
        self.A_BRAKE_ACCELERATION_THRESHOLD = -0.5
        self.A_BRAKE_SPEED_DROP_THRESHOLD = 1.5
        self.CONSTANT_SPEED_STD_THRESHOLD = 0.5
        self.CONSTANT_SPEED_ACCEL_THRESHOLD = 0.02
        self.PARKING_SPEED_THRESHOLD = 2.0
        self.PARKING_ACCEL_THRESHOLD = 0.05

        if config:
            self.update_from_config(config)

    def update_from_config(self, config):
        for key, value in config.items():
            if key in self.KEY_MAP:
                attr_name = self.KEY_MAP[key]
                try:
                    setattr(self, attr_name, float(value))
                except (ValueError, TypeError):
                    pass

    @classmethod
    def from_config_manager(cls, config_manager):
        if config_manager:
            thresholds = config_manager.get_section("BasicAnalysisThresholds")
            return cls(thresholds)
        return cls()


def get_smooth_window_size(speed):
    if speed < 20:
        return 15
    elif speed < 60:
        return 10
    else:
        return 8


class RollingWindow:
    def __init__(self, size):
        self.size = size
        self.data = deque(maxlen=size)
        self._cached_df = None
        self._cache_valid = False
        self._field_cache = {}
        self._field_cache_timestamp = 0

    def add(self, item):
        self.data.append(item)
        self._cache_valid = False
        self._field_cache = {}

    def get_df(self):
        if not self._cache_valid or self._cached_df is None:
            if not self.data:
                self._cached_df = {}
                self._cache_valid = True
                return self._cached_df
            keys = list(self.data[0].keys()) if self.data else []
            self._cached_df = {key: [d[key] for d in self.data] for key in keys}
            self._cache_valid = True
        return self._cached_df

    def get_field(self, field_name):
        if field_name not in self._field_cache or not self._field_cache:
            if not self.data:
                self._field_cache[field_name] = []
                return self._field_cache[field_name]
            self._field_cache[field_name] = [d.get(field_name, 0) for d in self.data]
        return self._field_cache[field_name]

    def get_recent_data(self, count):
        if len(self.data) <= count:
            return list(self.data)
        return list(self.data)[-count:]

    def is_full(self):
        return len(self.data) == self.size

    def count(self):
        return len(self.data)

    def clear(self):
        self.data.clear()
        self._cached_df = None
        self._cache_valid = False
        self._field_cache = {}


class BehaviorFunctionParameters:
    KEY_MAP = {
        'parking_window': 'parking_window',
        'constant_speed_straight_window': 'constant_speed_straight_window',
        'accelerating_window': 'accelerating_window',
        'decelerating_window': 'decelerating_window',
        'turning_window': 'turning_window',
        'emergency_brake_window': 'emergency_brake_window',
        'u_turn_window': 'u_turn_window',
        'snake_driving_window': 'snake_driving_window',
        'rapid_direction_change_window': 'rapid_direction_change_window',
        'large_radius_turning_window': 'large_radius_turning_window',
        'normal_acc_window': 'normal_acc_window',
        'aggressive_acc_window': 'aggressive_acc_window',
        'normal_brake_window': 'normal_brake_window',
        'aggressive_brake_window': 'aggressive_brake_window',
        'lane_changing_window': 'lane_changing_window',
    }

    def __init__(self, config=None):
        self.parking_window = 15
        self.constant_speed_straight_window = 10
        self.accelerating_window = 5
        self.decelerating_window = 5
        self.turning_window = 15
        self.emergency_brake_window = 5
        self.u_turn_window = 20
        self.snake_driving_window = 30
        self.rapid_direction_change_window = 5
        self.large_radius_turning_window = 20
        self.normal_acc_window = 10
        self.aggressive_acc_window = 5
        self.normal_brake_window = 10
        self.aggressive_brake_window = 5
        self.lane_changing_window = 15

        if config:
            self.update_from_config(config)

    def update_from_config(self, config):
        for key, value in config.items():
            if key in self.KEY_MAP:
                attr_name = self.KEY_MAP[key]
                try:
                    setattr(self, attr_name, int(value))
                except (ValueError, TypeError):
                    pass

    @classmethod
    def from_config_manager(cls, config_manager):
        if config_manager:
            windows = config_manager.get_section("BasicAnalysisWindowSizes")
            return cls(windows)
        return cls()


class BasicDrivingAnalyzer:
    """
    基础驾驶行为分析器 v2.0
    内部使用五层智能驾驶分析管道，对外保持完全兼容的 API
    """

    _FIELD_MAP = {
        'accel_x': 'ax', 'accel_y': 'ay', 'accel_z': 'az',
        'gyro_x': 'gx', 'gyro_y': 'gy', 'gyro_z': 'gz',
    }

    def __init__(self, thresholds: Dict[str, Any] = None, config_manager=None):
        self.logger = logging.getLogger(__name__)

        if config_manager:
            self.thresholds = DrivingThresholds.from_config_manager(config_manager)
            self.window_params = BehaviorFunctionParameters.from_config_manager(config_manager)
            self.config_manager = config_manager
        else:
            self.thresholds = thresholds or DrivingThresholds()
            self.window_params = BehaviorFunctionParameters()
            self.config_manager = None

        vehicle_config = VehicleConfig(
            mass=VehicleParameters.VEHICLE_MASS,
            iz=VehicleParameters.VEHICLE_Iz,
            wheelbase=VehicleParameters.WHEELBASE,
            cg_to_front=VehicleParameters.CG_TO_FRONT,
            cg_to_rear=VehicleParameters.CG_TO_REAR,
            cf=VehicleParameters.Cf,
            cr=VehicleParameters.Cr,
            steering_ratio=VehicleParameters.STEERING_RATIO,
        )
        self._pipeline = V2Pipeline(vehicle_config)

        self.data_buffer = RollingWindow(size=1000)
        self.stream_processor = StreamProcessor()
        self.analysis_pipeline = OldAnalysisPipeline()

        self.last_behavior_end_id = -1
        self._global_id_counter = 0

        self.batch_analysis_enabled = True
        self.batch_size = 10
        self.analysis_buffer = []
        self.last_analysis_time = 0
        self.min_analysis_interval = 0.1
        self.analysis_count = 0
        self.gc_threshold = 1000

        self.is_streaming = False
        self.stream_start_time = 0
        self.processed_data_count = 0

        self.recent_results = deque(maxlen=100)
        self.result_cache = {}

        self._current_speed = 0.0
        self._last_speed_time = None

        self.logger.info("基础行为分析器 v2.0 初始化完成（五层智能驾驶分析架构）")

    def _normalize_fields(self, data):
        normalized = dict(data)
        for old_key, new_key in self._FIELD_MAP.items():
            if old_key in normalized and new_key not in normalized:
                normalized[new_key] = normalized[old_key]
        return normalized

    def _integrate_speed(self, data):
        ax = data.get('ax', 0)
        if ax is None:
            ax = 0.0
        ts = data.get('timestamp', time.time())
        if self._last_speed_time is not None:
            dt = ts - self._last_speed_time
            if 0 < dt < 5.0:
                self._current_speed += ax * dt
        self._current_speed = max(0.0, self._current_speed)
        self._last_speed_time = ts
        return self._current_speed

    def reload_config(self):
        if self.config_manager:
            self.thresholds = DrivingThresholds.from_config_manager(self.config_manager)
            self.window_params = BehaviorFunctionParameters.from_config_manager(self.config_manager)
            self.logger.info("分析器配置已重新加载")

    def start_streaming(self):
        self.is_streaming = True
        self.stream_start_time = time.time()
        self.processed_data_count = 0
        self._pipeline.start_streaming()
        self.logger.info("流式处理模式已启动")

    def stop_streaming(self):
        self.is_streaming = False
        self._pipeline.stop_streaming()
        self.logger.info(f"流式处理模式已停止，共处理 {self.processed_data_count} 条数据")

    def add_data(self, data: Dict[str, Any]) -> None:
        try:
            data = self._normalize_fields(data)

            _NUMERIC_DEFAULTS = {
                'ax': 0.0, 'ay': 0.0, 'az': 0.0,
                'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
                'speed': 0.0, 'wheel': 0.0,
                'loc1': 0.0, 'loc2': 0.0,
            }
            for field, default in _NUMERIC_DEFAULTS.items():
                if data.get(field) is None:
                    data[field] = default

            speed = data.get('speed', 0)
            if speed is None or speed <= 0:
                data['speed'] = self._integrate_speed(data)

            self.data_buffer.add(data)
            self.stream_processor.add_data(data)
            self.processed_data_count += 1

        except Exception as e:
            self.logger.error(f"添加数据时出错: {e}")

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.add_data(data)
        self.analysis_count += 1

        try:
            result = self._pipeline.process_frame(data)
            legacy = result.to_legacy_dict()

            if result.event:
                self.recent_results.append(legacy)

            self.last_analysis_time = time.time()
            return legacy

        except Exception as e:
            self.logger.error(f"V2管道分析出错，回退到简化分析: {e}")
            return self._fallback_analyze(data)

    def _fallback_analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = self._normalize_fields(data)
        speed = data.get('speed', 0) or 0
        ax = data.get('ax', 0) or 0
        wheel = data.get('wheel', 0) or 0

        detected = []
        confidence = 0.5

        if abs(wheel) > 2.0:
            detected.append("右转" if wheel > 0 else "左转")
            confidence = 0.80

        if ax > 0.15:
            detected.append("加速")
            confidence = max(confidence, 0.75)
        elif ax < -0.15:
            detected.append("减速")
            confidence = max(confidence, 0.75)

        if ax < -3.0:
            detected = ["急刹车"]
            confidence = 0.95

        if speed < 2.0 and abs(ax) < 0.1:
            detected.append("停车")
            confidence = max(confidence, 0.85)

        if not detected:
            detected.append("normal")
            confidence = 0.90

        return {
            "timestamp": data.get("timestamp", time.time()),
            "behavior": detected[0],
            "confidence": confidence,
            "detected_all": detected,
            "raw_data": {k: v for k, v in data.items() if k != "raw_bytes"},
            "analysis_type": "fallback",
        }

    def analyze_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.analyze(data)

    def detect_behavior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            analysis_result = self.analyze_data(data)

            if 'behavior' in analysis_result:
                behavior_type = analysis_result['behavior']
                confidence = analysis_result.get('confidence', 0.0)

                return {
                    'behavior_type': behavior_type,
                    'confidence': confidence,
                    'timestamp': analysis_result.get('timestamp', time.time()),
                    'raw_data': data,
                    'analysis_data': analysis_result,
                    'detection_method': 'v2_pipeline',
                    'status': 'detected',
                }
            else:
                return {
                    'behavior_type': 'normal',
                    'confidence': 0.8,
                    'timestamp': time.time(),
                    'raw_data': data,
                    'analysis_data': analysis_result,
                    'detection_method': 'v2_pipeline',
                    'status': 'normal',
                }

        except Exception as e:
            self.logger.error(f"行为检测失败: {e}")
            return {
                'behavior_type': 'unknown',
                'confidence': 0.0,
                'timestamp': time.time(),
                'raw_data': data,
                'error': str(e),
                'status': 'error',
            }

    def get_streaming_stats(self) -> Dict[str, Any]:
        pipeline_stats = self._pipeline.get_stats()
        return {
            "is_streaming": self.is_streaming,
            "stream_start_time": self.stream_start_time,
            "processed_data_count": self.processed_data_count,
            "recent_results_count": len(self.recent_results),
            "buffer_size": self.data_buffer.count(),
            "analysis_count": self.analysis_count,
            "pipeline_state": pipeline_stats.get("current_state", "unknown"),
            "pipeline_events": pipeline_stats.get("recent_events_count", 0),
        }

    def update_config(self, thresholds: Dict[str, Any] = None):
        if thresholds:
            self.thresholds = thresholds
            self.logger.info("分析器配置已更新")

    def reset_analysis(self):
        self.data_buffer.clear()
        self.analysis_buffer.clear()
        self.recent_results.clear()
        self.result_cache.clear()
        self.last_analysis_time = 0
        self.analysis_count = 0
        self.processed_data_count = 0
        self.is_streaming = False
        self._pipeline.reset()
        self.logger.info("分析状态已重置")


class StreamProcessor(QThread if PYSIDE6_AVAILABLE else object):
    if PYSIDE6_AVAILABLE:
        data_processed = Signal(dict)
        processing_error = Signal(str)

    def __init__(self, analyzer=None):
        if PYSIDE6_AVAILABLE:
            QThread.__init__(self)
        else:
            super().__init__()
        self.data_queue = deque(maxlen=5000)
        self.analyzer = analyzer
        self._mutex = QMutex() if PYSIDE6_AVAILABLE else None
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0

    def add_data(self, data: Dict[str, Any]):
        if PYSIDE6_AVAILABLE and self._mutex:
            locker = QMutexLocker(self._mutex)
            self.data_queue.append(data)
        else:
            self.data_queue.append(data)

    def run(self):
        self.is_running = True
        while self.is_running and not (PYSIDE6_AVAILABLE and self.isInterruptionRequested()):
            try:
                data = None
                if PYSIDE6_AVAILABLE and self._mutex:
                    locker = QMutexLocker(self._mutex)
                    if self.data_queue:
                        data = self.data_queue.popleft()
                else:
                    if self.data_queue:
                        data = self.data_queue.popleft()

                if data and self.analyzer:
                    result = self.analyzer.analyze(data)
                    self.processed_count += 1
                    if PYSIDE6_AVAILABLE:
                        self.data_processed.emit(result)
                else:
                    if PYSIDE6_AVAILABLE:
                        self.msleep(10)
                    else:
                        time.sleep(0.01)

            except Exception as e:
                self.error_count += 1
                if PYSIDE6_AVAILABLE:
                    self.processing_error.emit(str(e))
                logging.error(f"流式处理出错: {e}")

    def start_processing(self):
        if PYSIDE6_AVAILABLE:
            self.start()
        else:
            self.is_running = True

    def stop_processing(self):
        self.is_running = False
        if PYSIDE6_AVAILABLE:
            self.requestInterruption()
            self.wait(3000)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queue_size": len(self.data_queue),
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "is_running": self.is_running,
        }


class OldAnalysisPipeline:
    def __init__(self):
        self.pipeline_stages = []
        self.current_stage = 0

    def add_stage(self, stage_func):
        self.pipeline_stages.append(stage_func)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = data
        for stage in self.pipeline_stages:
            try:
                result = stage(result)
            except Exception as e:
                logging.error(f"分析管道阶段执行失败: {e}")
                break
        return result


AnalysisPipeline = OldAnalysisPipeline
