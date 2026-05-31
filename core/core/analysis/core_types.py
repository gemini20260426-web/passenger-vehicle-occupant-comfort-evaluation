#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶行为分析系统 —核心数据类型定义
统一所有层之间的数据交换格式"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
import time


class BehaviorCategory(Enum):
    LONGITUDINAL = "longitudinal"
    LATERAL = "lateral"
    COMPOSITE = "composite"
    ANOMALY = "anomaly"
    NORMAL = "normal"


class RiskLevel(Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    DANGER = "DANGER"


class DrivingState(Enum):
    STOPPED = "stopped"
    STRAIGHT_CRUISE = "straight_cruise"
    ACCELERATING = "accelerating"
    BRAKING = "braking"
    TURNING_LEFT = "turning_left"
    TURNING_RIGHT = "turning_right"
    LANE_CHANGING = "lane_changing"
    UNKNOWN = "unknown"


BEHAVIOR_TAXONOMY = {
    BehaviorCategory.LONGITUDINAL: [
        "stopped",
        "launch",
        "normal_acceleration",
        "aggressive_acceleration",
        "constant_speed",
        "normal_deceleration",
        "aggressive_deceleration",
        "emergency_braking",
    ],
    BehaviorCategory.LATERAL: [
        "straight_driving",
        "lane_keeping",
        "tight_turn",
        "wide_turn",
        "u_turn",
        "lane_change",
        "weaving",
    ],
    BehaviorCategory.COMPOSITE: [
        "cornering_acceleration",
        "cornering_deceleration",
        "cornering_braking",
        "rapid_direction_change",
    ],
    BehaviorCategory.ANOMALY: [
        "skid_risk",
        "rollover_risk",
        "severe_bump",
        "sensor_fault",
    ],
}

BEHAVIOR_TYPES_V2 = []
for cat_behaviors in BEHAVIOR_TAXONOMY.values():
    BEHAVIOR_TYPES_V2.extend(cat_behaviors)

BEHAVIOR_LABELS_CN = {
    # ── 对齐 MetadataRegistry._register_driving_states ──
    "stopped": "停车",
    "launch": "起步",
    "normal_acceleration": "正常加速",
    "aggressive_acceleration": "激进加速",
    "constant_speed": "匀速直行",
    "normal_deceleration": "正常减速",
    "aggressive_deceleration": "激进减速",
    "emergency_braking": "急刹车",
    "straight_driving": "直线行驶",
    "straight_cruise": "直线巡航",
    "lane_keeping": "车道保持",
    "tight_turn": "小半径转弯",
    "wide_turn": "大半径转弯",
    "u_turn": "U型转弯",
    "lane_change": "变道",
    "weaving": "蛇形驾驶",
    "cornering_acceleration": "弯道加速",
    "cornering_deceleration": "弯道减速",
    "cornering_braking": "弯道制动",
    "rapid_direction_change": "急速变向",
    "skid_risk": "侧滑风险",
    "rollover_risk": "侧翻风险",
    "severe_bump": "剧烈颠簸",
    "sensor_fault": "传感器异常",
    "normal": "正常驾驶",
    # ── 新增：来自DrivingEventDetector 的事件类型──
    "cruising": "恒速行驶",
    "parked": "驻车",
    "left_turn": "左转",
    "right_turn": "右转",
}


@dataclass
class VehicleConfig:
    mass: float = 3500.0
    iz: float = 5500.0
    wheelbase: float = 3.5
    cg_to_front: float = 1.8
    cg_to_rear: float = 1.7
    cf: float = 180000.0
    cr: float = 180000.0
    steering_ratio: float = 15.0
    max_accel: float = 5.0
    max_decel: float = -8.0
    max_lateral_accel: float = 4.0
    friction_coefficient: float = 0.8


@dataclass
class SignalQuality:
    channel: str
    snr: float = 0.0
    is_valid: bool = True
    outlier_count: int = 0
    saturation_count: int = 0
    dropout_count: int = 0
    flags: List[str] = field(default_factory=list)


@dataclass
class ProcessedFrame:
    timestamp: float
    ax: float = 0.0           # IMU惯性加速度 X轴(m/s²) —含重力分量传感器坐标系
    ay: float = 0.0           # IMU惯性加速度 Y轴(m/s²) —含重力分量传感器坐标系
    az: float = 0.0           # IMU惯性加速度 Z轴(m/s²) —含重力分量传感器坐标系
    gx: float = 0.0           # IMU X轴角速度 (rad/s)
    gy: float = 0.0           # IMU Y轴角速度 (rad/s)
    gz: float = 0.0           # IMU Z轴角速度 (rad/s)
    speed: float = 0.0        # CAN车速(km/h), 来自CAN总线
    wheel: float = 0.0        # CAN方向盘角 (deg), 来自CAN总线
    vehicle_accel: float = 0.0  # CAN车速微分加速度 (m/s²), 来自SpeedPreprocessor. 注意: 与IMU ax/ay/az物理意义不同(CAN为车速变化率, IMU为惯性加速度)
    steer_rate: float = 0.0   # 方向盘角速率绝对值(deg/s), 来自SpeedPreprocessor
    loc1: float = 0.0
    loc2: float = 0.0
    quality: Dict[str, SignalQuality] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None


@dataclass
class FrameFeatures:
    timestamp: float
    temporal: Dict[str, float] = field(default_factory=dict)
    spectral: Dict[str, float] = field(default_factory=dict)
    kinematic: Dict[str, float] = field(default_factory=dict)
    physics: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, float]:
        result = {}
        result.update(self.temporal)
        result.update(self.spectral)
        result.update(self.kinematic)
        result.update(self.physics)
        return result


@dataclass
class ManeuverEvent:
    id: str
    type: str
    category: BehaviorCategory = BehaviorCategory.NORMAL
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    peak_ax: float = 0.0
    peak_ay: float = 0.0
    peak_jerk: float = 0.0
    speed_range: Tuple[float, float] = (0.0, 0.0)
    confidence: float = 0.0
    detection_method: str = "rule_based"
    risk_level: RiskLevel = RiskLevel.SAFE
    risk_score: float = 0.0
    data_indices: Tuple[int, int] = (0, 0)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def label_cn(self) -> str:
        return BEHAVIOR_LABELS_CN.get(self.type, self.type)


@dataclass
class RiskReport:
    level: RiskLevel = RiskLevel.SAFE
    score: float = 0.0
    stability_margin: float = 1.0
    comfort_index: float = 0.0
    collision_risk: float = 0.0
    factors: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameResult:
    timestamp: float = 0.0
    state: DrivingState = DrivingState.UNKNOWN
    features: Optional[FrameFeatures] = None
    event: Optional[ManeuverEvent] = None
    risk: Optional[RiskReport] = None
    raw_data: Optional[Dict[str, Any]] = None
    # ProcessedFrame 字段
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0
    speed: float = 0.0
    wheel: float = 0.0
    loc1: float = 0.0
    loc2: float = 0.0
    quality: Dict[str, SignalQuality] = field(default_factory=dict)

    def to_legacy_dict(self) -> Dict[str, Any]:
        result = {
            "timestamp": self.timestamp,
            "behavior": "normal",
            "confidence": 0.5,
            "detected_all": ["normal"],
            "raw_data": self.raw_data or {},
            "analysis_type": "v2_pipeline",
        }
        if self.event:
            result["behavior"] = self.event.label_cn
            result["confidence"] = self.event.confidence
            result["detected_all"] = [self.event.label_cn]
            result["risk_level"] = self.event.risk_level.value
            result["risk_score"] = self.event.risk_score
        return result


# ===========================================
# 座椅评测系统数据类型
# ===========================================

@dataclass
class MultiChannelIMUData:
    """多通道IMU数据"""
    timestamp: float
    channel_data: Dict[str, Dict[str, Any]]  # channel_id -> data
    group_tag: str  # 'experimental' or 'control'


@dataclass
class EvaluationTrigger:
    """座椅评测触发器"""
    trigger_id: str
    event_type: str
    source_behavior: str  # 原始ManeuverEvent.type
    timestamp: float
    metrics: List[str]
    data_window: Dict[str, float]  # pre, post
    # 多通道数据支持
    multi_channel_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 格式: {
    #   'channel_id': {
    #       'ax': [...],
    #       'ay': [...],
    #       'az': [...],
    #       'timestamps': [...]
    #   }
    # }
    locations: List[str] = field(default_factory=list)  # 要评测的位置列表
    group_tag: str = 'experimental'  # 'experimental' or 'control' or 'both'


@dataclass
class ComparativeEvaluationTrigger(EvaluationTrigger):
    """对照评测触发器"""
    experimental_channels: List[str] = field(default_factory=list)  # imu1-imu5
    control_channels: List[str] = field(default_factory=list)  # imu6-imu10
    enable_comparative: bool = True
    # 按位置配置    location_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """座椅评测结果"""
    trigger_id: str
    event_type: str
    timestamp: float
    metrics: Dict[str, float]  # 总体指标
    overall_score: float = 0.0  # v3.0以后由profile替代
    risk_level: RiskLevel = RiskLevel.SAFE
    metadata: Dict[str, Any] = field(default_factory=dict)
    profile: Optional[Dict[str, Any]] = None  # v3.0: 多维振动剖面数据
    location_results: Dict[str, 'LocationEvaluationResult'] = field(default_factory=dict)


@dataclass
class LocationEvaluationResult:
    """位置级评测结果"""
    location_id: str
    location_name: str
    channel_id: str
    metrics: Dict[str, float]  # 指标ID -> 值    location_score: float = 0.0  # 该位置的综合评分（v3.0以后由profile替代）    risk_level: RiskLevel = RiskLevel.SAFE
    metadata: Dict[str, Any] = field(default_factory=dict)
    profile: Optional[Dict[str, Any]] = None  # v3.0: 多维振动剖面数据


@dataclass
class ComparativeEvaluationResult:
    """对照评测结果"""
    trigger_id: str
    event_type: str
    timestamp: float
    
    # 实验组结果    experimental_results: EvaluationResult
    
    # 对照组结果    control_results: EvaluationResult
    
    # 对比分析
    comparisons: Dict[str, Dict[str, Any]]
    # 格式: {
    #   'metric_id': {
    #       'diff': float,          # 差异值    #       'improvement_pct': float, # 改善百分比    #       'stat_sig': bool,        # 统计显著性    #       'p_value': float,        # p值    #       'effect_size': float     # 效应量    #   }
    # }
    
    # 位置级对比    location_comparisons: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 格式: {
    #   'location_id': {
    #       'experimental_score': float,
    #       'control_score': float,
    #       'improvement_pct': float,
    #       'metrics': {...}
    #   }
    # }
    
    # 总体评分
    overall_score: Dict[str, float] = field(default_factory=dict)  # experimental_score, control_score, improvement


@dataclass
class TestGroupReport:
    """试验组对照报告"""
    report_id: str
    test_name: str
    start_time: float
    end_time: float
    
    # 事件级结果汇总    event_results: List[ComparativeEvaluationResult]
    
    # 综合统计
    summary_statistics: Dict[str, Dict[str, Any]]
    # 格式: {
    #   'metric_id': {
    #       'exp_mean': float,
    #       'exp_std': float,
    #       'ctrl_mean': float,
    #       'ctrl_std': float,
    #       'improvement_pct': float,
    #       'p_value': float
    #   }
    # }


# ===== Backward Compatibility Bridge =====
# The following re-exports exist for backward compatibility with code
# that imports these symbols from core_types instead of their canonical locations.
# New code should import directly from:
#   - core.seat_evaluation.metadata_registry
#   - core.seat_evaluation.diagnosis_engine
import warnings as _warnings
_warnings.warn("Importing metadata/diagnosis from core_types is deprecated. "
              "Use seat_evaluation.metadata_registry and seat_evaluation.diagnosis_engine directly.",
              DeprecationWarning, stacklevel=2)

from ..seat_evaluation.metadata_registry import (
    INDICATOR_DEFINITIONS,
    INDICATOR_DETAIL,
    DIAGNOSIS_THRESHOLDS,
    DIAGNOSIS_STATE_ICONS,
    STANDARD_REFERENCES,
    COMPARISON_DIMENSIONS,
)
from ..seat_evaluation.diagnosis_engine import (
    _diagnosis_state,
    _diagnosis_comment,
    DiagnosisItem,
    SingleGroupDiagnosis,
    generate_single_group_diagnosis,
)
