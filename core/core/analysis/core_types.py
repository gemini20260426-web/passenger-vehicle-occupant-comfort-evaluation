#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶行为分析系统 — 核心数据类型定义
统一所有层之间的数据交换格式
"""

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
    # ── 新增：来自 DrivingEventDetector 的事件类型 ──
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
    ax: float = 0.0           # IMU X轴加速度 (m/s²) — 含重力分量/振动/倾角
    ay: float = 0.0           # IMU Y轴加速度 (m/s²)
    az: float = 0.0           # IMU Z轴加速度 (m/s²)
    gx: float = 0.0           # IMU X轴角速度 (rad/s)
    gy: float = 0.0           # IMU Y轴角速度 (rad/s)
    gz: float = 0.0           # IMU Z轴角速度 (rad/s)
    speed: float = 0.0        # CAN车速 (km/h)
    wheel: float = 0.0        # CAN方向盘角 (deg)
    vehicle_accel: float = 0.0  # 车辆纵向加速度 (m/s²), 来自SpeedPreprocessor
    steer_rate: float = 0.0   # 方向盘角速率绝对值 (deg/s), 来自SpeedPreprocessor
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
    # 按位置配置
    location_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


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
    metrics: Dict[str, float]  # 指标ID -> 值
    location_score: float = 0.0  # 该位置的综合评分（v3.0以后由profile替代）
    risk_level: RiskLevel = RiskLevel.SAFE
    metadata: Dict[str, Any] = field(default_factory=dict)
    profile: Optional[Dict[str, Any]] = None  # v3.0: 多维振动剖面数据


@dataclass
class ComparativeEvaluationResult:
    """对照评测结果"""
    trigger_id: str
    event_type: str
    timestamp: float
    
    # 实验组结果
    experimental_results: EvaluationResult
    
    # 对照组结果
    control_results: EvaluationResult
    
    # 对比分析
    comparisons: Dict[str, Dict[str, Any]]
    # 格式: {
    #   'metric_id': {
    #       'diff': float,          # 差异值
    #       'improvement_pct': float, # 改善百分比
    #       'stat_sig': bool,        # 统计显著性
    #       'p_value': float,        # p值
    #       'effect_size': float     # 效应量
    #   }
    # }
    
    # 位置级对比
    location_comparisons: Dict[str, Dict[str, Any]] = field(default_factory=dict)
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
    
    # 事件级结果汇总
    event_results: List[ComparativeEvaluationResult]
    
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


# 指标定义
INDICATOR_DEFINITIONS = {
    # 原有频域指标 (8个)
    'SEAT_Z': {'name': '座椅垂直传递率', 'unit': '', 'type': 'frequency'},
    'SEAT_XY': {'name': '座椅水平传递率', 'unit': '', 'type': 'frequency'},
    'VDV_Z': {'name': '垂直振动剂量值', 'unit': 'm/s^1.75', 'type': 'frequency'},
    'TR_Z': {'name': '垂直传递率(dB)', 'unit': 'dB', 'type': 'frequency'},
    'AW_Z': {'name': '垂直加权加速度', 'unit': 'g', 'type': 'frequency'},
    'AW_XY': {'name': '水平加权加速度', 'unit': 'g', 'type': 'frequency'},
    'OVTV': {'name': '总体振动值', 'unit': 'm/s^1.75', 'type': 'frequency'},
    'R_FACTOR': {'name': 'R因子', 'unit': '', 'type': 'frequency'},
    
    # 新增瞬态指标 (15个)
    'HIC15': {'name': '头部损伤准则', 'unit': '', 'type': 'shock'},
    'ACC_H_PEAK': {'name': '头部加速度峰值', 'unit': 'g', 'type': 'shock'},
    'JERK_H': {'name': '头部冲击度', 'unit': 'g/s', 'type': 'shock'},
    'SRS_MRS': {'name': '最大响应谱', 'unit': 'g', 'type': 'shock'},
    'SRS_Q': {'name': '品质因数', 'unit': '', 'type': 'shock'},
    'SRS_PV': {'name': '峰值速度', 'unit': 'g·s', 'type': 'shock'},
    'SRS_ATT': {'name': '衰减时间', 'unit': 's', 'type': 'shock'},
    'RFC_CC': {'name': '循环计数', 'unit': '', 'type': 'fatigue'},
    'FDS_D': {'name': '疲劳损伤度', 'unit': '', 'type': 'fatigue'},
    'FDS_R': {'name': '剩余寿命', 'unit': '', 'type': 'fatigue'},
    'STFT_FC': {'name': '频率中心', 'unit': 'Hz', 'type': 'time_frequency'},
    'STFT_KT': {'name': '频率扩展', 'unit': 'Hz', 'type': 'time_frequency'},
    'STFT_CE': {'name': '能量集中度', 'unit': '', 'type': 'time_frequency'},
    'DISP_TR': {'name': '位移轨迹', 'unit': 'mm', 'type': 'structure'},

    'ACC_RMS': {'name': '加速度均方根', 'unit': 'g', 'type': 'basic'},
    'ACC_PEAK': {'name': '峰值加速度', 'unit': 'g', 'type': 'basic'},
}

INDICATOR_DETAIL = {
    # ═══════════════════════════════════════════════════════════
    #                稳态舒适度 (Steady-state Comfort)
    # ═══════════════════════════════════════════════════════════

    'SEAT_Z': {
        'category': 'steady_state',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': '座椅 IMU5_座垫R点-1',
        'reference_imu': '座椅 IMU7_座椅底部-1',
        'data_fields': 'az[点数N]@seat_bottom(地板激励) + az[点数N]@seat_r(座椅响应)',
        'operator_pipeline': (
            '① PSD算子(Welch法, nperseg≤1024): az_seat→(f_seat, PSD_seat), az_floor→(f_floor, PSD_floor)\n'
            '② Weighting算子(freq Wk): PSD→PSD_w = PSD×Wk(f)², f∈[0→fs/2]\n'
            '    Wk(f): f<0.5→0.5; 0.5-2→f; 2-5→2; 5-16→10/f; 16-80→10/f; f≥80→0 (ISO 2631-1 Table 3)\n'
            '③ numpy梯形积分: I_seat=∫PSD_seat_w df, I_floor=∫PSD_floor_w df\n'
            '④ SEAT_Z = √(I_seat/I_floor)'
        ),
        'formula': (
            'SEAT_Z = √( ∫₀^{fs/2} PSD_seat(f)×[Wk(f)]² df / ∫₀^{fs/2} PSD_floor(f)×[Wk(f)]² df )\n'
            '☑ Coherence验证: 计算CSD→mean(coh), coh<0.5时Warning\n'
            'Fallback(floor缺失时): SEAT_Z ≈ RMS(FFT→Wk(f)→IFFT(az_seat)), 失去传递率物理意义'
        ),
        'calculation_logic': (
            'SEAT因子 — 座椅有效振幅传递率 (ISO 10326-2)\n'
            '衡量座椅对0.5-80Hz垂直振动的衰减效率\n'
            'SEAT_Z < 1: 座椅主动隔振(优秀)\n'
            'SEAT_Z = 1: 座椅无衰减(中性)\n'
            'SEAT_Z > 1: 座椅放大振动(不良)'
        ),
        'single_point_description': (
            '单点不可用: 降级为RMS×1后恒≈自比值1.0，完全失去传递率物理含义\n'
            '必须获得seat_r与seat_bottom的同步采样AZ数据'
        ),
        'two_point_description': '✅ 必须: seat_r(AZ) vs seat_bottom(AZ) 频率域PSD比值',
        'three_point_description': '不适用',
    },

    'SEAT_XY': {
        'category': 'steady_state',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': 'IMU5_座垫R点-1',
        'reference_imu': 'IMU7_座椅底部-1',
        'data_fields': 'ax[点数N]+ay[点数N]@seat_bottom(地板), ax[点数N]+ay[点数N]@seat_r(座椅表面)',
        'operator_pipeline': (
            '① Vector算子.synthesize_xy(ax,ay): xy_seat=√(ax²+ay²)@seat_r, xy_floor=√(ax²+ay²)@seat_bottom\n'
            '② PSD算子(Welch): xy_seat→(f, PSD_seat), xy_floor→(f, PSD_floor)\n'
            '③ Weighting算子(freq Wd): PSD_w=PSD×Wd(f)²\n'
            '    Wd(f): f<0.5→1; 0.5-2→f/0.5; 2-5→1; 5-16→5/f; 16-80→5/16×16/f; f≥80→0\n'
            '④ 梯形积分 + √(int_seat/int_floor) = SEAT_XY'
        ),
        'formula': (
            'SEAT_XY = √( ∫₀^{fs/2} PSD(xy_seat)×[Wd(f)]² df / ∫₀^{fs/2} PSD(xy_floor)×[Wd(f)]² df )\n'
            '☑ Coherence验证: 计算CSD→mean(coh), coh<0.5时Warning\n'
            'Fallback: 单点RMS(FFT→Wd(f)→IFFT(xy_seat))'
        ),
        'calculation_logic': 'SEAT_XY — 座椅水平振幅传递率 (ISO 10326-2)，Wk→Wd加权，衡量水平方向振动衰减',
        'single_point_description': '单点不可用(same as SEAT_Z)',
        'two_point_description': '✅ 必须: seat_r(XY合成) vs seat_bottom(XY合成) 频率域PSD比值',
        'three_point_description': '不适用',
    },

    'AW_Z': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@指定位置',
        'operator_pipeline': (
            '① Weighting算子.apply_weighting_z_via_freq(az, sr): 频域Wk加权\n'
            '    FFT(az)→Wk(f)→IFFT, 与SEAT_Z共用同一Wk(f)函数 (ISO 2631-1 Table 3)\n'
            '② RMS: AW_Z = √[ (1/N)×Σ(az_weighted_i²) ]'
        ),
        'formula': (
            'az → FFT→Wk(f)→IFFT → aw[0..N-1]\n'
            'AW_Z = √( Σᵢ aw_i² / N )  [单位: g]'
        ),
        'calculation_logic': 'ISO 2631-1 Wk加权垂直加速度RMS。head/torso/seat_r三位置对比构成振动传递梯度',
        'single_point_description': '✅ 单IMU: az_raw → Wk时域卷积 → √mean(weighted²)',
        'two_point_description': '🔶 seat_r vs head AW_z比值 反映 人头对臀点振动的隔振效率',
        'three_point_description': '🔶 head/torso/seat_r 三个AW_z构成完整的Z轴振动传递梯度曲线',
    },

    'AW_XY': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]@指定位置',
        'operator_pipeline': (
            '① VectorOperator.synthesize_xy(ax,ay): xy=√(ax_i²+ay_i²) for i=0..N-1\n'
            '② WeightingOperator.apply_weighting_xy_via_freq(xy, sr): 频域Wd加权\n'
            '    FFT(xy)→Wd(f)→IFFT, 与SEAT_XY共用同一Wd(f)函数 (ISO 2631-1 Table 4)\n'
            '③ AW_XY = RMS(xy_weighted)'
        ),
        'formula': (
            'xy_i = √(ax_i²+ay_i²), i=0..N-1\n'
            'xy → FFT→Wd(f)→IFFT → xyw[0..N-1]\n'
            'AW_XY = √( Σᵢ xyw_i² / N )  [单位: g]'
        ),
        'calculation_logic': 'ISO 2631-1 Wd加权水平加速度RMS。多位置对比可评价侧向振动沿人体的传递路径',
        'single_point_description': '✅ 单IMU: (ax,ay)→√合成→Wd滤波→RMS',
        'two_point_description': '🔶 两位置 AW_xy 对比可评价侧向振动衰减效率',
        'three_point_description': '🔶 head/torso/seat_r 三位置构成水平振动传递梯度',
    },

    'OVTV': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① VectorOperator.synthesize(ax,ay,az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
            '② 四次方累计: D = mean(a_total_i⁴) × N/sr\n'
            '③ OVTV = D^(0.25) = (∫a_total⁴ dt)^(1/4)'
        ),
        'formula': (
            'a_total_i = √(ax_i²+ay_i²+az_i²)  [3-axis resultant]\n'
            'OVTV = [ (1/N)×Σᵢ a_total_i⁴ … × (N/f_s) ] ^ (1/4)  [单位: m/s^1.75]\n'
            '等价: OVTV = (∫₀^T a_total(t)⁴ dt)^(1/4)'
        ),
        'calculation_logic': (
            'BS 6841 四次方振动剂量\n'
            '四次方积分比RMS(²)更敏感于振动峰值因子\n'
            'excellent<0.5, good<1.0, fair<1.7'
        ),
        'single_point_description': '✅ 单IMU三轴合成, 四次方积分, 4th-root, 独立计算',
        'two_point_description': '🔶 seat_r vs head OVTV差值 反映全身振动剂量衰减率',
        'three_point_description': '不适用',
    },

    'R_FACTOR': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector: lateral_strength = ax + ay (横向求和)\n'
            '② σ(ax+ay) = np.std(ax+ay), σ(az) = np.std(az)\n'
            '③ R_FACTOR = σ(ax+ay)/(σ(az)+1e-9)'
        ),
        'formula': (
            'R_FACTOR = σ(ax+ay) / [ σ(az) + 0.001 ]\n'
            'σ = 标准差 = √( (1/N)×Σ(x_i-x̄)² )\n'
            'R<1→垂向主宰; R≈1→均衡; R>1→侧向主宰(curves)'
        ),
        'calculation_logic': 'R因子 — 侧向/垂向振动方向性比率。head vs seat_r差值反映人体对方向振动的选择性衰减',
        'single_point_description': '✅ 单IMU: 标准差比值(标量)',
        'two_point_description': '🔶 head vs seat_r R_FACTOR差异 反映 人体对水平/垂直振动的衰减不对称性',
        'three_point_description': '不适用',
    },

    # ═══════════════════════════════════════════════════════════
    #                动态舒适度 (Dynamic Comfort)
    # ═══════════════════════════════════════════════════════════

    'VDV_Z': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@指定位置',
        'operator_pipeline': (
            '① WeightingOp.apply_weighting_z_via_freq(az, sr): 频域Wk加权→azw[0..N-1]\n'
            '    FFT→Wk(f)→IFFT, 与SEAT_Z共用同一Wk(f)函数\n'
            '② dt = 1.0/sr (采样间隔)\n'
            '③ VDV_Z = [ Σᵢ azw_i⁴  × dt ] ^ (1/4)'
        ),
        'formula': (
            'az_raw[N] → Wk时域滤波 → azw[N]\n'
            'VDV_Z = ( Σᵢ₌₀ᴺ⁻¹ azw_i⁴ × (1/sr) ) ^ (1/4)  [单位: g·s^0.25 或 m/s^1.75]\n'
            'BS 6841: VDV>1.5 ⇒ "可能不适"'
        ),
        'calculation_logic': (
            'BS 6841 累积振动剂量值\n'
            'Wk加权+四次方积分 → 对高冲击事件(peak)的剂量累积极为敏感\n'
            'head/torso/seat_r三位置VDV梯度 = 全身振动剂量传输画像'
        ),
        'single_point_description': '✅ 单IMU: az→Wk时域滤波→四次方积分→4th-root',
        'two_point_description': '🔶 head VDV / seat_r VDV 比值 = 座椅对振动剂量的隔振效率',
        'three_point_description': '🔶 head→torso→seat_r VDV梯度 沿脊柱下行, 揭示振动剂量从小(臀)→大(头)的传递规律',
    },

    'TR_Z': {
        'category': 'dynamic',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': 'IMU5_座垫R点-1(响应y) + IMU7_座椅底部-1(输入x)',
        'data_fields': 'az[点数N]@seat_bottom, az[点数N]@seat_r, 两通道需同步采样长度一致',
        'operator_pipeline': (
            '① CSDOperator.compute(az_floor, az_seat, sr, nperseg≤256):\n'
            '    - welch(floor) → Pxx\n'
            '    - welch(seat)  → Pyy\n'
            '    - csd(floor,seat) → Pxy\n'
            '    - H(f)=Pxy(f)/(Pxx(f)+1e-12)\n'
            '    - coherence(f) = |Pxy|²/(Pxx·Pyy+1e-12)\n'
            '② CSD.transfer_function_db: |H(f)|→20log10→dB谱\n'
            '    - mask 0.5-50Hz找峰值\n'
            '    - TR_Z = peak_dB(0.5-50Hz)\n'
            '☑ Coherence验证: mean(coh)<0.5→Warning\n'
            '③ Fallback(floor数据缺失): TR_Z = σ(az_seat)/σ(az_floor) ≈1.0 无意义'
        ),
        'formula': (
            'CSD(Floor→Seat): H(f)=CSD(floor,seat,f)/PSD(floor,f)\n'
            'H_dB(f) = 20×log₁₀(|H(f)|)\n'
            'TR_Z = max[ H_dB(f) for f∈(0.5,50)Hz ], 0dB等价(输出=输入)\n'
            'TR_Z_image: 需4位置全TR链\n'
            '   seat_bottom→seat_r (TR_SEAT): 座椅垂向传递率\n'
            '   seat_r→torso      (TR_TORSO):人体脊椎下段传递率\n'
            '   torso→head        (TR_HEAD): 人体脊椎上段传递率'
        ),
        'calculation_logic': (
            'TR_Z — 频率域跨位置振动传递函数峰值dB\n'
            '>0dB: 振动在特定频段被放大(共振峰值)\n'
            '<0dB: 振动衰减\n'
            '含coherence验证函数确保传递率可靠性'
        ),
        'single_point_description': '单点不可用: 自CSD→H≈1→0dB, 完全无意义, 必须两个位置同步数据',
        'two_point_description': '✅ 必须: seat_r vs seat_bottom CSD 传递函数 峰值dB',
        'three_point_description': '🔴 完整TR链需要4个位置: seat_bottom→seat_r→torso→head 构成三级传递率CSD链',
    },

    'DISP_TR': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU3_躯干T8-1 (torso)',
        'data_fields': 'az[点数N]@torso',
        'operator_pipeline': (
            '① IntegrationOperator.integrate_to_displacement(az, sr):\n'
            '    - scipy signal.butter(2, 0.5/sr·2, HP): 消除积分漂移\n'
            '    - acc_f = signal.filtfilt(b,a,az)\n'
            '    - vel   = cumsum(acc_f)/sr          (一次积分 → 速度)\n'
            '    - vel_f = filtfilt(b,a,vel)          (HP二次滤波)\n'
            '    - disp  = cumsum(vel_f)/sr × 1000   (二次积分→位移[mm])\n'
            '    注: HP滤波已消除DC漂移, 异常路径额外有 disp-mean(disp)\n'
            '② DISP_TR = max(|disp|)'
        ),
        'formula': (
            'Step1: az → Butterworth HP(0.5Hz,2nd) → az_f[N]\n'
            'Step2: v(tᵢ) = Σⱼ[0→i] az_f(j)×Δt , v_f=HP_filter(v)\n'
            'Step3: d(tᵢ) = Σⱼ[0→i] v_f(j)×Δt × 1000.0  [mm]\n'
            'Step4: DISP_TR = max(|d_i|,∀i)  [峰值位移, mm]\n'
            'Δt = 1/sr, HP双通已消DC, 无需额外-mean(d)'
        ),
        'calculation_logic': (
            '振动引起相对空间的绝对位移轨迹(mm)\n'
            '0.5Hz HP = 消除加速度计中低频直流漂移\n'
            '1000 coeff = g→mm/s² 单位转换\n'
            'seat_r vs torso DISP对比: 评价座椅靠背对人体的约束效果'
        ),
        'single_point_description': '✅ 单IMU: az→HP→1次积分→HP→2次积分→max_abs(×1000)',
        'two_point_description': '🔶 seat_r vs torso DISP_TR对比: 臀部(座) vs 躯干(背)相对位移差异',
        'three_point_description': '不适用',
    },

    'RFC_CC': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r',
        'operator_pipeline': (
            '① 提取az信号的局部极值序列 (peak/valley检测)\n'
            '② RainflowOperator.count(az): 四峰谷雨流计数法(ASTM E1049-85)\n'
            '    - 4-point 分组规则(S0,S1,S2,S3): 配对Δ₁=Δ₂循环\n'
            '    - 生成amplitude_ₖ, mean_ₖ 值对\n'
            '③ RFC_CC = len(valid_cycles) (过滤出 amplitude>1e-9 的有效循环数)'
        ),
        'formula': (
            'Peaks[] = {ai if ai>ai-1 and ai>ai+1}\n'
            'Valleys[] = {ai if ai<ai-1 and ai+1 and ai<ai+1}\n'
            'Rainflow(S0,S1,S2,S3, peaks/valleys):\n'
            '   Δ₁ = |S1-S0|, Δ₂ = |S2-S1|\n'
            '   if Δ₁≤Δ₂: 生成cycle(amplitude=Δ₁/2, mean=(S0+S1)/2)\n'
            '     pop(S0,S1) from list\n'
            '   else: i+=1 (跳过)\n'
            'RFC_CC = Σ valid_cycles (amp_i>1e-9)'
        ),
        'calculation_logic': (
            '应力/振动循环计数\n'
            '统计独立振动负载循环的总次数\n'
            '多位置循环数对比 → 判断各部位承受的交变振动载荷差异'
        ),
        'single_point_description': '✅ 单IMU: az→极值提取→四峰谷pairing→cycle count',
        'two_point_description': '🔶 多位置 RFC_CC 对比 判断 各部位的交变载荷次数差异',
        'three_point_description': '不适用',
    },

    'FDS_D': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r → rainflow cycles[]',
        'operator_pipeline': (
            '① RainflowOperator.count(az) → RF_result {cycles, amplitudes, means}\n'
            '② FDSOperator.compute(RF_result):\n'
            '    S-N曲线: Nᵢ = k × Sᵢ^(-b)  [Sᵢ=amplitude]\n'
            '    默认 b=8 (S-N曲线的Basquin指数,金属/结构疲劳高灵敏度)\n'
            '    total_damage D = Σᵢ (1/(Nᵢ+1e-12)) = Σᵢ (1/(k×amp_i^(-8)))\n'
            '    = Σᵢ (amp_i^8)  (k=1近似)\n'
            '③ FDS_D = D'
        ),
        'formula': (
            'Rainflow(az)→{amp_i,∀i}\n'
            'N_i = k × amp_i^(-b) = 1.0 × amp_i^(-8)  [S-N curve, Miner materials]\n'
            'FDS_D = Σᵢ amp_i^8   [Miner累积, 如果>1.0 ⇒ 预计疲劳失效]\n'
            '同时: LEQ = (Σᵢ (amp_i/9.81)^4 / (#cycles))^0.25'
        ),
        'calculation_logic': (
            'Miner线性累积疲劳损伤度 (BS 7608 / ASTM E1049)\n'
            'b=8: 标准钢结构Basquin指数\n'
            '总损伤D的累计, D≥1.0时表明到达疲劳寿命极限\n'
            '本指标是对S-N曲线与Miner法则的科学实现'
        ),
        'single_point_description': '✅ 单IMU: az→Rainflow→S-N curve(b=8)→ΣMiner累积损伤',
        'two_point_description': '🔶 seat_r vs torso FDS_D对比 揭示 座垫 vs 靠背的疲劳风险分布',
        'three_point_description': '不适用',
    },

    'FDS_R': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r → FDS_D派生',
        'operator_pipeline': (
            '① 先计算 FDS_D (rainflow → Miner 累积损伤度)\n'
            '② FDS_R = max(0.0, 1.0 - FDS_D)\n'
            '    0≤FDS_R≤1: 比例剩余疲劳寿命\n'
            '    0: 寿命已耗尽; 1: 寿命完全剩余'
        ),
        'formula': (
            'FDS_R = max(0, 1.0 - FDS_D)\n'
            'FDS_D = total Miner损伤度\n'
            '   0.0: 未损伤\n'
            '   0.1: 寿命用去10%\n'
            '   1.0: 寿命用去100%, FDS_R=0\n'
            '   2.0: 寿命用去200%, FDS_R=0'
        ),
        'calculation_logic': '疲劳剩余寿命(由FDS_D派生, 0-1区间)',
        'single_point_description': '✅ 从FDS_D派生: R = max(0, 1-D)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'STFT_FC': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFTOperator.compute(az, sr): scipy signal.stft\n'
            '    → spectrogram[S(freq)×T(time)]\n'
            '② extract_features:\n'
            '    Power per freq: P_f = Σⱼ spectrum[f,j]\n'
            '    Total power:  T = Σ_f P_f\n'
            '    if T>0: STFT_FC = Σ_f freqs·P_f / T  [频率重心, Hz]'
        ),
        'formula': (
            'STFT(az) → spectra_of dimensions [F×T]\n'
            'P(f) = Σ_j spectra[f,j] for all time indices j\n'
            'fc = Σ_f (freq[f] × P(f)) / Σ_f P(f)  [Hz: 功率加权平均主导频率]\n'
            'Human-sensitive range: 2-8 Hz (internal organ resonance)'
        ),
        'calculation_logic': (
            '时频谱功率加权平均频率\n'
            '反映该位置的\"主导振动频率\"\n'
            'Benz 4-5Hz: 人体内脏共振区 → 高风险\n'
            '12-20Hz: 脊柱轴向共振\n'
            '>20Hz: 高频抖颤, 不适感为主'
        ),
        'single_point_description': '✅ 单IMU: az→STFT→功率加权平均频率',
        'two_point_description': '🔶 seat_r(Wk weighted) vs sternum fc差异 辅助判断共振源位置',
        'three_point_description': '不适用',
    },

    'STFT_KT': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFT.compute → spectrum, freqs\n'
            '② extract P(f) and fc as in STFT_FC above\n'
            '③ STFT_KT = √[ Σ_f (freq[f]-fc)² × P(f) / Σ_f P(f) ]'
        ),
        'formula': (
            'fc = 频率重心(from STFT_FC)\n'
            'σ² = Σ_f (f-fc)² × P_f / Σ_f P_f\n'
            'STFT_KT = √σ²  [Hz: 频率分布的\"宽度/频谱扩散度\"]\n'
            '   Narrow: KT<3Hz → 纯频率(共振危险)\n'
            '   Wide:   KT>10Hz → 宽带振动(浑沌)'
        ),
        'calculation_logic': (
            '振动频率分布的\"厚度/集中度\"\n'
            '低KT: 振动集中窄带(如\"在4.3Hz尖峰\") → 共振风险\n'
            '高KT: 宽带振动 → 含多频率组分混乱感'
        ),
        'single_point_description': '✅ 从STFT结果: 频率标准差(二阶矩)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'STFT_CE': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFT→spectrogram→P_f per freq\n'
            '② STFT_CE = max(P_f) / mean(P_f)  [无量纲, ≥1.0]'
        ),
        'formula': (
            'P_max = max_f {P(f)}\n'
            'P_avg = (1/F)×Σ_f P(f)  (F: #frequencies)\n'
            'STFT_CE = P_max / P_avg  [≥1.0, ≥5→强烈能量集中]\n'
            '  CE≈1: 均匀宽带\n'
            '  CE≈5: 能量集中在1个特定频率(共振)\n'
            '  CE>10: 极尖锐共振峰'
        ),
        'calculation_logic': (
            '谱能量集中度 — 功率峰值 / 平均功率\n'
            '→ CE越大 = 共振越尖锐(危险性高)\n'
            '→ CE接近1 = 体系无固有频率(宽带随机振动)\n'
            '联合fc & kt 构成完整的[重心,扩散,集中度]振动画像'
        ),
        'single_point_description': '✅ 峰/均比值, 从STFT频谱获取',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    # ═══════════════════════════════════════════════════════════
    #              瞬态感受评价 (Transient Sensation)
    # ═══════════════════════════════════════════════════════════

    'HIC15': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@head',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i²+ay_i²+az_i²) / 9.81  (→ g units)\n'
            '② 15ms window: n₍₁₅₎ = max(1, ceil(0.015·sr))\n'
            '    ☑ sr<200Hz: np.interp自动升采样至≥200Hz (≥3样本/15ms)\n'
            '    滑动窗口 i = 0..(N-n₁₅):\n'
            '    - segment = a_total[i:i+n₁₅], a_avg = mean(segment)\n'
            '    - dt_window = t(i+n₁₅-1)-t(i) ≈ 0.015s\n'
            '    - hic_candidate = dt_window × (a_avg)^(2.5)\n'
            '③ HIC15 = maxᵢ(hic_candidate_i)  (SAE J211, FMVSS 208)'
        ),
        'formula': (
            'aᵢ(g) = (1/9.81)×√(axᵢ²+ayᵢ²+azᵢ²)  for i=0..N-1\n'
            'n₁₅ = ⌈0.015·sr⌉, dt=1/sr (sr<200→自动升采样至200)\n'
            'for idx=0..N-n₁₅:\n'
            '   ā(input_window idx..idx+n15-1)\n'
            '   HIC_candidate(idx) = (t_n15-t_0) × ā^(2.5)\n'
            'HIC15 = argmax candidate(HIC_candidate)\n'
            'Limits (FMVSS 208): ≤700, >1000 fatal risk\n'
            '⚠️ **仅在头部眉心IMU1位置有意义**,其他位置计算无物理损伤意义'
        ),
        'calculation_logic': (
            'SAE J211 / FMVSS 208 头部损伤准则\n'
            '15ms时间窗口内合成加速度的2.5次方增幅\n'
            '—— 损伤概率: HIC15∞, 全时域取max\n'
            '→ 公式来自实验数据fit, 2.5次方代表加速度\"敏感性\"超过线性损伤\n'
            '→ 紧急制动/碰撞/过颠簸事件出现高强度HIC15'
        ),
        'single_point_description': '✅ 单IMU(head): 三轴合成g + 15ms滑动窗max[dt×avg²⁵]',
        'two_point_description': '不适用 (仅在head有意义)',
        'three_point_description': '不适用',
    },

    'ACC_H_PEAK': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@head',
        'operator_pipeline': (
            '① VectorOperator.synthesize(ax, ay, az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
            '② ACC_H_PEAK = max_i(|a_total_i|) — 合加速度绝对值的全程峰值 (g单位)'
        ),
        'formula': (
            'head_accel_i(g) = √(ax_i²+ay_i²+az_i²)\n'
            'ACC_H_PEAK = max_i{head_accel_i}  [g]\n'
            'SAE J211: >20g extreme, >10g moderate, >5g low\n'
            '⚠️ **仅在头部眉心IMU1位置有意义**'
        ),
        'calculation_logic': '头部承受的最大合加速度(peak of resultant) — SAE J211标准',
        'single_point_description': '✅ 单IMU(head): 三轴合成→max|output|',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'JERK_H': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head',
        'operator_pipeline': (
            '① np.diff(az) × sr: 一阶前向差分×采样率 = da/dt  [g/s]\n'
            '② JERK_H = max_i(|jerk_i|×1.0)'
        ),
        'formula': (
            'For i=0..N-2:\n'
            '   da_i = (az_{i+1}-az_i) · sr\n'
            'jerk_i = |da_i|  [g/s: 加速度变化率=急动度]\n'
            'JERK_H = max_i(jerk_i)  [单位: g/s]\n'
            'High-jerk = \"sharp impact\" → 冲击锋利'
        ),
        'calculation_logic': '头部加速度变化率(急动度/jerk), 反映冲击的\"锋利程度\" — 高Jerk值指示硬撞击/突发冲击事件',
        'single_point_description': '✅ 单IMU Z轴差分: jerk←np.diff(az)×sr→max abs',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_MRS': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head(时域数组)',
        'operator_pipeline': (
            '① SRS Operator (MIL-STD-810H Method 516.8 Smallwood Recursion):\n'
            '    - Q=10 → ζ=1/(2Q)=0.05\n'
            '    - f_group = 60 SDOF, 0.5-100Hz logspace\n'
            '    - For each f: damping = 0.05, Smallwood递推\{a₀,a₁,b₁,b₂\}\n'
            '        SDOF=Tₙ,Q=10→abs(response peak) for this freq→svalues[f]\n'
            '② SRS_MRS = max(svalues across full freq group)  [单位: g]'
        ),
        'formula': (
            'For each SDOF system π (0.5Hz<π<100Hz):\n'
            '   ωn=2πF₀; Δt=1/sr; ζ=0.05; compute constants:\n'
            '     E = e^(-ζωnΔt)\n'
            '     K = ωnΔtE/√(1-ζ²)\n'
            '     C = E·cos(ωnΔt√(1-ζ²)); S=E·sin(ωnΔt√1-ζ²)\n'
            '     b₁=2C, b₂=-E², a₀=1-K·S, a₁=K·S-E·[S/(ωdΔt)+C]\n'
            '   For all j=2..N-1:\n'
            '     resp[j]=b₁·resp[j-1]+b₂·resp[j-2]+a₀·az[j]+a₁·az[j-1]\n'
            '   svalue(π) = max_j(|resp_j|)\n'
            '   svalues_all(π) = envel; MRS = max_π sprom peak → SRS_MRS\n'
            'PV: from peak_freq displace; ATT: A=1/Q=0.1 temporal'
        ),
        'calculation_logic': (
            'MIL-STD-810H 冲击响应谱分析 — 最大响应谱(加速度)\n'
            '在0.5-100Hz频率范围内,定义60个SDOF系统\n'
            'Q=10系统 Smallwood高效递推 → SRS(f)的包络 → SRS_MRS = 包络峰值\n'
            'MRS数值对应\"理想支持结构\"在冲击中的最大承受加速度'
        ),
        'single_point_description': '✅ 单IMU Z轴→SRS Smallwood recursion(60 SDOF从0.5→100Hz)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_Q': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (固定参数)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS分析固定参数',
        'operator_pipeline': (
            '① SRS类定义时固定 Q = 10.0 (MIL-STD-810H标准)\n'
            '② SRS_Q = 10.0'
        ),
        'formula': (
            'Q = 10.0 (固定值)\n'
            'ζ = 1/(2Q) = 0.05 (5% critical damping)\n'
            '用于 Shock Response Spectrum analysis\n'
            '**属计算参数,非直接测量指标**'
        ),
        'calculation_logic': '品质因数(属MIL-STD-810H标准编制参数)',
        'single_point_description': '✅ 计算系统的默认参数,非传感器映射,恒等Q=10',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_PV': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS+derivation',
        'operator_pipeline': (
            '① SRS compute获取: svalues, frequencies[]  → MRS, peak_freq index\n'
            '② PV = MRS / (2π·peak_freq)  (in m/s)'
        ),
        'formula': (
            'MRS = maxᵢ svaluesᵢ\n'
            'peak_f = frequencies[argmax svalues]\n'
            'SRS_PV = MRS / (2π·peak_f + 1e-12)  [m/s]\n'
            'Pseudo-velocity = 从SRS频率 & MRS推算的结构特定速度'
        ),
        'calculation_logic': (
            'SRS峰值频率所对应的伪速度(位移率)\n'
            'MIL-STD-810H冲击分析中, 从SRS输出MRS & peakF → 推算伪速度\n'
            '— 表示结构需吸收的冲击能量需求'
        ),
        'single_point_description': '✅ 从SRS峰值加速度x频率→伪速度派生, 单IMU即可',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_ATT': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (固定参数)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS固定参数',
        'operator_pipeline': (
            '① SRS衰减 τ = 1/Q = 0.1s (from the same Q system)\n'
            '② SRS_ATT = 1/Q = 0.1'
        ),
        'formula': (
            'τ = 1/Q = 0.1 (秒)  [system impulse decay tim]\n'
            '— SDOF振子在初始激励后自由振动,持续约0.1s参数\n'
            '**属标准参数, 非实测值**'
        ),
        'calculation_logic': 'SRS冲击响应衰减时长(固定值1/Q = 0.1s)',
        'single_point_description': '✅ 固定计算参数, 非测量指标, τ = 0.1s',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'ACC_RMS': {
        'category': 'general',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (通用)',
        'primary_imu': '全部IMU通道通用',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
            '② RMS: ACC_RMS = √[ (1/N)×Σᵢ a_total_i² ]'
        ),
        'formula': (
            'a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\n'
            'ACC_RMS = √( Σᵢ₌₀ᴺ⁻¹ a_total_i² / N )  [g]\n'
            '物理意义: 该位置的总体振动能量水平\n'
            'excellent<0.3, good<0.6, fair<1.0'
        ),
        'calculation_logic': (
            'ISO 2631-1 基础时域指标\n'
            '三轴合成加速度均方根 → 反映指定位置的总体振动能量\n'
            'acc_rms_{pos}对比构成 全身→臀部→头部 的振动能量传递梯度'
        ),
        'single_point_description': '✅ 单IMU: 三轴合成 → RMS, 适用于所有位置',
        'two_point_description': '🔶 seat_r vs head ACC_RMS 比值 反映 座椅对总振动能量的隔振率',
        'three_point_description': '🔶 head→torso→seat_r ACC_RMS梯度 揭示振动能量沿脊柱的衰减路径',
    },

    'ACC_PEAK': {
        'category': 'general',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (通用)',
        'primary_imu': '全部IMU通道通用',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
            '② Peak: ACC_PEAK = max(a_total_i)'
        ),
        'formula': (
            'a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\n'
            'ACC_PEAK = max( a_total_i )  [g]\n'
            '物理意义: 该位置在事件窗口内的瞬时最大冲击\n'
            'excellent<1.0, good<2.0, fair<4.0'
        ),
        'calculation_logic': (
            'ISO 2631-1 / BS 6841 瞬态峰值检测\n'
            '三轴合成瞬时加速度最大值 → 反映该位置的冲击强度\n'
            'peak_{pos}对比 构成 全身→臀部→头部 的冲击传递画像'
        ),
        'single_point_description': '✅ 单IMU: 三轴合成 → max, 适用于所有位置',
        'two_point_description': '🔶 head vs seat_r PEAK衰减 = 座椅对冲击峰值的隔振效果',
        'three_point_description': '🔶 head→torso→seat_r 峰值梯度 揭示冲击沿脊柱衰减的传递路径',
    },
}


# ═══════════════════════════════════════════════════════════════
# 方案C — 单组诊断 (Transfer Path + Weakest Link)
# ═══════════════════════════════════════════════════════════════

DIAGNOSIS_THRESHOLDS = {
    'SEAT_Z':  {'pass': 0.80, 'warn': 1.00, 'desc': '座椅垂直传递率', 'loc': 'seat_r'},
    'SEAT_XY': {'pass': 0.80, 'warn': 1.00, 'desc': '座椅水平传递率', 'loc': 'seat_r'},
    'HIC15':   {'pass': 700,  'warn': 1000, 'desc': '头部损伤准则', 'loc': 'head'},
    'SRS_MRS': {'pass': 15.0, 'warn': 30.0, 'desc': '冲击响应谱峰值', 'loc': 'head'},
    'SRS_Q':   {'pass': 10.0, 'warn': 15.0, 'desc': '品质因数', 'loc': 'head'},
    'SRS_PV':  {'pass': 5.0,  'warn': 10.0, 'desc': '峰值速度[m/s]', 'loc': 'head'},
    'SRS_ATT': {'pass': 0.10, 'warn': 0.20, 'desc': '衰减时间[s]', 'loc': 'head'},
    'ACC_H_PEAK': {'pass': 5.0, 'warn': 10.0, 'desc': '头部峰值加速度', 'loc': 'head'},
    'JERK_H':  {'pass': 5.0, 'warn': 15.0, 'desc': '头部冲击急动度', 'loc': 'head'},
    'FDS_D':   {'pass': 0.30, 'warn': 0.70, 'desc': '疲劳累积损伤', 'loc': 'seat_r'},
    'FDS_R':   {'pass': 0.70, 'warn': 0.30, 'desc': '剩余寿命', 'loc': 'seat_r'},
    'RFC_CC':  {'pass': 20,   'warn': 50,   'desc': '雨流循环计数', 'loc': 'seat_r'},
    'AW_Z':    {'pass': 0.30, 'warn': 0.60, 'desc': 'Wk加权加速度RMS', 'loc': 'seat_r'},
    'AW_XY':   {'pass': 0.30, 'warn': 0.60, 'desc': 'Wd加权加速度RMS', 'loc': 'seat_r'},
    'VDV_Z':   {'pass': 2.0,  'warn': 5.0,  'desc': '振动剂量值', 'loc': 'seat_r'},
    'OVTV':    {'pass': 0.50, 'warn': 1.70, 'desc': '总体振动值', 'loc': 'seat_r'},
    'R_FACTOR': {'pass': 0.50, 'warn': 1.00, 'desc': 'R因子(侧向/垂向)', 'loc': 'seat_r'},
    'TR_Z':    {'pass': 0.0,  'warn': 5.0,  'desc': '垂直传递率[dB]', 'loc': 'seat_r'},
    'DISP_TR': {'pass': 200,  'warn': 500,  'desc': '峰值相对位移[mm]', 'loc': 'seat_r'},
    'STFT_FC': {'pass': 8.0,  'warn': 12.0, 'desc': '频率中心[Hz]', 'loc': 'torso'},
    'STFT_KT': {'pass': 3.0,  'warn': 10.0, 'desc': '频率扩展[Hz]', 'loc': 'torso'},
    'STFT_CE': {'pass': 5.0,  'warn': 10.0, 'desc': '能量集中度', 'loc': 'torso'},
    'ACC_RMS': {'pass': 0.3, 'warn': 1.0, 'desc': '加速度均方根[g]', 'loc': 'seat_r'},
    'ACC_PEAK': {'pass': 1.0, 'warn': 4.0, 'desc': '峰值加速度[g]', 'loc': 'seat_r'},
}

DIAGNOSIS_STATE_ICONS = {
    'pass': '✅',
    'warn': '⚠️',
    'fail': '❌',
    'na':   '—',
}

STANDARD_REFERENCES = {
    'HIC15':      {'standard': 'SAE J211 / FMVSS 208', 'limit': '≤700 (pass), >1000 (fail)', 'source_url': ''},
    'ACC_H_PEAK': {'standard': 'SAE J211',             'limit': '≤5g (excellent), ≤10g (good)', 'source_url': ''},
    'JERK_H':     {'standard': 'SAE J211 (derived)',    'limit': '≤5 g/s (excellent), ≤15 g/s (good)', 'source_url': ''},
    'SRS_MRS':    {'standard': 'MIL-STD-810H Method 516.8', 'limit': '≤15g (recommended)', 'source_url': ''},
    'SRS_Q':      {'standard': 'MIL-STD-810H',          'limit': 'Q=10 (standard parameter)', 'source_url': ''},
    'SRS_PV':     {'standard': 'MIL-STD-810H (derived)','limit': '≤5 m/s (recommended)', 'source_url': ''},
    'SRS_ATT':    {'standard': 'MIL-STD-810H',          'limit': 'τ=0.1s (standard parameter)', 'source_url': ''},
    'SEAT_Z':     {'standard': 'ISO 2631-1:1997',       'limit': '≤0.80 (pass), >1.0 (amplify)', 'source_url': ''},
    'SEAT_XY':    {'standard': 'ISO 2631-1:1997',       'limit': '≤0.80 (pass), >1.0 (amplify)', 'source_url': ''},
    'AW_Z':       {'standard': 'ISO 2631-1:1997',       'limit': '≤0.315 m/s² (comfortable)', 'source_url': ''},
    'AW_XY':      {'standard': 'ISO 2631-1:1997',       'limit': '≤0.315 m/s² (comfortable)', 'source_url': ''},
    'VDV_Z':      {'standard': 'BS 6841 / ISO 2631-1',  'limit': '≤8.5 (low), ≤17 (high)', 'source_url': ''},
    'OVTV':       {'standard': 'ISO 2631-1:1997',       'limit': '≤0.5 (comfortable), ≤1.7 (very uncomfortable)', 'source_url': ''},
    'R_FACTOR':   {'standard': 'ISO 2631-1 (derived)',  'limit': '≤1.0 (recommended)', 'source_url': ''},
    'DISP_TR':    {'standard': 'Engineering guideline',   'limit': '≤200mm (pass), ≤500mm (warn)', 'source_url': ''},
    'TR_Z':       {'standard': 'ISO 2631-1 (derived)',  'limit': '≤0 dB (no amplification)', 'source_url': ''},
    'FDS_D':      {'standard': 'Miner\'s Rule / BS 7608','limit': '≤0.20 (pass), ≤0.50 (warn)', 'source_url': ''},
    'FDS_R':      {'standard': 'Miner\'s Rule / BS 7608','limit': '≤0.20 (pass), ≤0.50 (warn)', 'source_url': ''},
    'RFC_CC':     {'standard': 'ASTM E1049-85',         'limit': '≤20 (pass), ≤50 (warn)', 'source_url': ''},
    'STFT_FC':    {'standard': 'Engineering guideline',   'limit': '2-8 Hz (内脏共振危险区)', 'source_url': ''},
    'STFT_KT':    {'standard': 'Engineering guideline',   'limit': '≤3 Hz (窄带共振), ≥10 Hz (宽带)', 'source_url': ''},
    'STFT_CE':    {'standard': 'Engineering guideline',   'limit': '≤5 (低集中度), ≥10 (尖锐共振)', 'source_url': ''},
}

COMPARISON_DIMENSIONS = [
    {
        'id': 'isolation',
        'name': '隔振能力',
        'description': '座椅系统对振动的衰减/放大效应',
        'color': '#4A90D9',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_TR', 'TR_Z', 'ACC_RMS', 'ACC_PEAK', 'OVTV', 'R_FACTOR'],
    },
    {
        'id': 'head_safety',
        'name': '终端安全',
        'description': '乘员头部冲击风险与损伤概率',
        'color': '#E74C3C',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT'],
    },
    {
        'id': 'fatigue',
        'name': '累积疲劳',
        'description': '长期振动暴露引起的疲劳损伤累积',
        'color': '#F39C12',
        'metrics': ['FDS_D', 'FDS_R', 'RFC_CC', 'VDV_Z'],
    },
    {
        'id': 'time_frequency',
        'name': '时频分析',
        'description': '振动的频率分布与能量集中度',
        'color': '#9B59B6',
        'metrics': ['STFT_FC', 'STFT_KT', 'STFT_CE'],
    },
]


def _diagnosis_state(value, thresholds):
    if value is None:
        return 'na'
    if value <= thresholds['pass']:
        return 'pass'
    if value <= thresholds['warn']:
        return 'warn'
    return 'fail'


def _diagnosis_comment(metric_id, value, state, threshold_def):
    t = threshold_def
    if state == 'na':
        return '数据缺失'
    if state == 'pass':
        if metric_id in ('SEAT_Z', 'SEAT_XY'):
            pct = (1 - value) * 100 if value <= 1.0 else (value - 1) * 100
            return f'隔振率 {pct:.0f}%'
        elif metric_id == 'HIC15':
            return f'远低于限值 {t["pass"]}'
        elif metric_id == 'FDS_D':
            return f'剩余寿命 {((1-value)*100):.0f}%'
        return '良好'
    if state == 'warn':
        if metric_id in ('SEAT_Z', 'SEAT_XY'):
            return f'隔振率仅 {(1-value)*100:.0f}%，接近临界'
        return f'接近限值 {t["warn"]}'
    if metric_id in ('SEAT_Z', 'SEAT_XY') and value > 1.0:
        pct = (value - 1) * 100
        return f'振动放大 {pct:.0f}%（不良）'
    return f'超过安全限值 {t["warn"]}'


@dataclass
class DiagnosisItem:
    label: str
    metric_id: str
    value: Optional[float]
    state: str = 'na'
    comment: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'metric_id': self.metric_id,
            'value': self.value,
            'state': self.state,
            'comment': self.comment,
        }


@dataclass
class SingleGroupDiagnosis:
    group_tag: str = 'experimental'
    isolation: List[DiagnosisItem] = field(default_factory=list)
    head_safety: List[DiagnosisItem] = field(default_factory=list)
    fatigue: List[DiagnosisItem] = field(default_factory=list)
    conclusion: str = ''
    weakest_link: str = ''
    overall_verdict: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'group_tag': self.group_tag,
            'isolation': [i.to_dict() for i in self.isolation],
            'head_safety': [i.to_dict() for i in self.head_safety],
            'fatigue': [i.to_dict() for i in self.fatigue],
            'conclusion': self.conclusion,
            'weakest_link': self.weakest_link,
            'overall_verdict': self.overall_verdict,
        }


def generate_single_group_diagnosis(
    location_results: Dict[str, Any],
    group_tag: str = 'experimental',
) -> SingleGroupDiagnosis:
    diag = SingleGroupDiagnosis(group_tag=group_tag)

    def _get_metric(loc_id: str, metric_id: str) -> Optional[float]:
        lr = location_results.get(loc_id)
        if lr is None:
            return None
        metrics = getattr(lr, 'metrics', {}) or {}
        val = metrics.get(metric_id)
        if val is not None and isinstance(val, (int, float)) and val == -1.0:
            return None
        return val

    def _build_section(metric_ids):
        items = []
        for mid in metric_ids:
            td = DIAGNOSIS_THRESHOLDS[mid]
            val = _get_metric(td['loc'], mid)
            state = _diagnosis_state(val, td)
            comment = _diagnosis_comment(mid, val, state, td)
            items.append(DiagnosisItem(
                label=td['desc'],
                metric_id=mid,
                value=val,
                state=state,
                comment=comment,
            ))
        return items

    diag.isolation = _build_section(['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_TR', 'ACC_RMS', 'ACC_PEAK'])
    diag.head_safety = _build_section(['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS'])
    diag.fatigue = _build_section(['FDS_D', 'RFC_CC', 'VDV_Z'])

    all_states = []
    for item in diag.isolation + diag.head_safety + diag.fatigue:
        if item.state != 'na':
            all_states.append(item.state)

    fail_count = all_states.count('fail')
    warn_count = all_states.count('warn')

    fails = [it for it in diag.isolation + diag.head_safety + diag.fatigue if it.state == 'fail']
    warns = [it for it in diag.isolation + diag.head_safety + diag.fatigue if it.state == 'warn']

    if fail_count > 0:
        diag.overall_verdict = f'存在 {fail_count} 项不合格'
        diag.weakest_link = ' / '.join(f.label for f in fails[:3])
        diag.conclusion = f'❌ 单组诊断：{diag.overall_verdict}\n最薄弱环节：{diag.weakest_link}'
    elif warn_count > 0:
        diag.overall_verdict = f'基本合格，{warn_count} 项需关注'
        diag.weakest_link = ' / '.join(w.label for w in warns[:3])
        diag.conclusion = f'⚠️ 单组诊断：{diag.overall_verdict}\n需关注：{diag.weakest_link}'
    else:
        diag.overall_verdict = '各项指标正常'
        diag.weakest_link = '无'
        diag.conclusion = '✅ 单组诊断：各项指标均在安全范围内'

    return diag
