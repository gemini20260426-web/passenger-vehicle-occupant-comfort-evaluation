#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一指标元数据注册中心 V3.0
================================
融合三套指标体系的完整元数据:

  来源1: indicator_metadata_engine.py     — 15个核心指标 + 完整溯源链
  来源2: core_types.py (InstanceViewPanel) — INDICATOR_DETAIL + 24指标定义
  来源3: 座椅评测系统深度优化方案 V3.0       — 系统架构与模块划分

标准引用:
  ISO 2631-1/5, SAE J211-1, ISO 6487, ISO 10326-1/2,
  MIL-STD-810H, ASTM E1049, ISO 12108, GB/T 4970-2009,
  FMVSS 208, ECE R94, BS 6841, BS 7608

指标体系 (27个核心指标):

  瞬态冲击 (7): HIC15, ACC_H_PEAK, JERK_H, SRS_MRS, SRS_Q, SRS_PV, SRS_ATT
  稳态舒适度 (6): SEAT_Z, SEAT_XY, AW_Z, AW_XY, OVTV, R_FACTOR
  动态舒适度 (2): VDV_Z, TR_Z
  位移与衰减 (3): DISP_HR, DISP_TR, ATTEN_H
  疲劳损伤 (3): RFC_CC, FDS_D, FDS_R
  时频分析 (3): STFT_FC, STFT_KT, STFT_CE
  脊柱健康 (1): S_D
  通用基础 (2): ACC_RMS, ACC_PEAK
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum, auto


# ═══════════════════════════════════════════════════════════════
# 枚举类型
# ═══════════════════════════════════════════════════════════════

class DataCategory(Enum):
    RAW = auto()
    DERIVED = auto()
    INDICATOR = auto()


class ComparisonMethod(Enum):
    ABSOLUTE = auto()
    RELATIVE = auto()
    BOTH = auto()


class EvaluationDirection(Enum):
    LOWER_BETTER = auto()
    HIGHER_BETTER = auto()
    NOMINAL = auto()


class OutputType(Enum):
    SCALAR = auto()
    CURVE = auto()
    MATRIX = auto()
    SPECTRUM = auto()


class DataSourceType(Enum):
    CAN_FILE = auto()
    SERIAL_IMU = auto()
    CNAP = auto()
    MQTT = auto()
    FILE_OFFLINE = auto()


class RiskCategory(Enum):
    NORMAL = auto()
    WARNING = auto()
    DANGER = auto()
    CRITICAL = auto()


# ═══════════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class StandardRef:
    standard_name: str
    clause: str
    description: str
    source_url: str = ''

    def __str__(self):
        return f"{self.standard_name} §{self.clause}: {self.description}"


@dataclass
class RawFieldMeta:
    field_code: str
    display_name_cn: str
    display_name_en: str
    physical_unit: str
    data_type: str
    range_min: float
    range_max: float
    sample_rate_hz: float = 1000.0
    source_device: str = 'IMU'
    calibration_required: bool = True
    description: str = ''
    field_category: str = 'imu'


@dataclass
class DerivedFieldMeta:
    field_code: str
    display_name_cn: str
    display_name_en: str
    physical_unit: str
    source_raw_fields: List[str]
    derivation_formula: str
    derivation_formula_latex: str
    output_type: OutputType = OutputType.SCALAR
    description: str = ''


@dataclass
class OperatorMeta:
    operator_code: str
    display_name_cn: str
    display_name_en: str
    input_type: str
    output_type: str
    algorithm: str
    parameters: Dict[str, any]
    standard_refs: List[StandardRef] = field(default_factory=list)
    description: str = ''


@dataclass
class IndicatorMeta:
    indicator_code: str
    display_name_cn: str
    display_name_en: str
    evaluation_dimension: str
    applicable_locations: List[str]
    source_imus: List[str]
    source_raw_fields: List[str]
    prerequisite_derived: List[str]
    operator_pipeline: List[str]
    formula_text: str
    formula_latex: str
    variables: Dict[str, str]
    unit: str
    output_type: OutputType = OutputType.SCALAR
    precision: int = 2
    threshold_pass: str = ''
    threshold_excellent: str = ''
    evaluation_direction: EvaluationDirection = EvaluationDirection.LOWER_BETTER
    comparison_method: ComparisonMethod = ComparisonMethod.ABSOLUTE
    standard_refs: List[StandardRef] = field(default_factory=list)
    industry_references: List[str] = field(default_factory=list)
    description: str = ''


@dataclass
class IndicatorDetail:
    indicator_code: str
    category: str = ''
    location_dependency: str = ''
    location_dependency_label: str = ''
    required_locations: List[str] = field(default_factory=list)
    primary_imu: str = ''
    reference_imu: str = ''
    data_fields: str = ''
    operator_pipeline_detail: str = ''
    formula_detail: str = ''
    calculation_logic: str = ''
    single_point_description: str = ''
    two_point_description: str = ''
    three_point_description: str = ''


@dataclass
class EvaluationModuleMeta:
    module_code: str
    display_name_cn: str
    display_name_en: str
    scenario_description: str
    applicable_indicators: List[str]
    evaluation_method: str
    standard_refs: List[StandardRef] = field(default_factory=list)


@dataclass
class DataSourceMeta:
    source_code: str
    display_name_cn: str
    display_name_en: str
    source_type: DataSourceType
    protocol: str = ''
    physical_channel: str = ''
    can_ids: List[str] = field(default_factory=list)
    imu_labels: Dict[str, str] = field(default_factory=dict)
    sampling_rate_hz: float = 100.0
    sensor_model: str = ''
    sensor_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    raw_fields: List[str] = field(default_factory=list)
    vehicle_signal_fields: List[str] = field(default_factory=list)
    description: str = ''


@dataclass
class DrivingStateMeta:
    state_code: str
    display_name_cn: str
    display_name_en: str = ''
    risk_category: RiskCategory = RiskCategory.NORMAL
    risk_level_cn: str = '低'
    color_hex: str = '#27AE60'
    description: str = ''


# ═══════════════════════════════════════════════════════════════
# 主注册中心
# ═══════════════════════════════════════════════════════════════

class MetadataRegistry:

    def __init__(self):
        self.raw_fields: Dict[str, RawFieldMeta] = {}
        self.derived_fields: Dict[str, DerivedFieldMeta] = {}
        self.operators: Dict[str, OperatorMeta] = {}
        self.indicators: Dict[str, IndicatorMeta] = {}
        self.indicator_details: Dict[str, IndicatorDetail] = {}
        self.evaluation_modules: Dict[str, EvaluationModuleMeta] = {}
        self.data_sources: Dict[str, DataSourceMeta] = {}
        self.driving_states: Dict[str, DrivingStateMeta] = {}

        self.standard_references: Dict[str, Dict] = {}
        self.comparison_dimensions: List[Dict] = []
        self.diagnosis_thresholds: Dict[str, Dict] = {}
        self.metric_thresholds_4level: Dict[str, Dict] = {}

        self._register_raw_fields()
        self._register_derived_fields()
        self._register_operators()
        self._register_indicators()
        self._register_indicator_details()
        self._register_evaluation_modules()
        self._register_standard_references()
        self._register_comparison_dimensions()
        self._register_diagnosis_thresholds()
        self._register_data_sources()
        self._register_driving_states()

    # ──────────────────────────────────────────────
    # 原始采集字段
    # ──────────────────────────────────────────────

    def _register_raw_fields(self):
        fields = [
            RawFieldMeta('Ax_m_s2', 'X轴加速度', 'Accel X', 'm/s²', 'float32', -160, 160,
                         description='IMU X轴线性加速度'),
            RawFieldMeta('Ay_m_s2', 'Y轴加速度', 'Accel Y', 'm/s²', 'float32', -160, 160,
                         description='IMU Y轴线性加速度'),
            RawFieldMeta('Az_m_s2', 'Z轴加速度', 'Accel Z', 'm/s²', 'float32', -160, 160,
                         description='IMU Z轴线性加速度'),
            RawFieldMeta('Gx_dps', 'X轴角速度', 'Gyro X', '°/s', 'float32', -500, 500,
                         description='IMU X轴角速度'),
            RawFieldMeta('Gy_dps', 'Y轴角速度', 'Gyro Y', '°/s', 'float32', -500, 500,
                         description='IMU Y轴角速度'),
            RawFieldMeta('Gz_dps', 'Z轴角速度', 'Gyro Z', '°/s', 'float32', -500, 500,
                         description='IMU Z轴角速度'),

            RawFieldMeta('VEH_SPEED', '车速', 'Vehicle Speed', 'm/s', 'float32', 0, 50,
                         sample_rate_hz=10.0, source_device='CAN_CH6', calibration_required=False,
                         description='CAN总线车速信号(ch6 0x100)', field_category='vehicle'),
            RawFieldMeta('WHEEL_ANGLE', '方向盘转角', 'Steering Angle', 'deg', 'float32', -540, 540,
                         sample_rate_hz=10.0, source_device='CAN_CH6', calibration_required=False,
                         description='CAN总线方向盘转角(ch6 0x101)', field_category='vehicle'),
            RawFieldMeta('BRAKE_PRESSURE', '制动压力', 'Brake Pressure', 'kPa', 'float32', 0, 1000,
                         sample_rate_hz=10.0, source_device='CAN_CH6', calibration_required=False,
                         description='CAN总线制动压力(ch6 0x102)', field_category='vehicle'),
            RawFieldMeta('EMERGENCY_BRAKE', '紧急制动标志', 'Emergency Brake', 'bool', 'uint8', 0, 1,
                         sample_rate_hz=10.0, source_device='CAN_CH6', calibration_required=False,
                         description='CAN总线紧急制动标志(ch6 0x102)', field_category='vehicle'),
        ]
        for f in fields:
            self.raw_fields[f.field_code] = f

    # ──────────────────────────────────────────────
    # 派生数据字段
    # ──────────────────────────────────────────────

    def _register_derived_fields(self):
        fields = [
            DerivedFieldMeta('A_MAG', '三轴合加速度', 'Vector Magnitude', 'm/s²',
                             ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
                             '|A| = sqrt(Ax² + Ay² + Az²)',
                             r'|A| = \sqrt{A_x^2 + A_y^2 + A_z^2}'),
            DerivedFieldMeta('A_MAG_g', '三轴合加速度(g)', 'Vector Magnitude (g)', 'g',
                             ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
                             '|A|/g = sqrt(Ax²+Ay²+Az²)/9.80665',
                             r'|A|_g = \sqrt{A_x^2+A_y^2+A_z^2}/9.80665'),
            DerivedFieldMeta('DISP_X', 'X轴位移', 'Displacement X', 'mm',
                             ['Ax_m_s2'], '∬Ax·dt²', r'\iint A_x dt^2',
                             OutputType.CURVE),
            DerivedFieldMeta('DISP_Y', 'Y轴位移', 'Displacement Y', 'mm',
                             ['Ay_m_s2'], '∬Ay·dt²', r'\iint A_y dt^2',
                             OutputType.CURVE),
            DerivedFieldMeta('DISP_Z', 'Z轴位移', 'Displacement Z', 'mm',
                             ['Az_m_s2'], '∬Az·dt²', r'\iint A_z dt^2',
                             OutputType.CURVE),
            DerivedFieldMeta('DISP_3D', '三维合位移', '3D Displacement', 'mm',
                             ['DISP_X', 'DISP_Y', 'DISP_Z'],
                             'sqrt(DX²+DY²+DZ²)',
                             r'\sqrt{D_X^2+D_Y^2+D_Z^2}',
                             OutputType.CURVE),
            DerivedFieldMeta('PSD_X', 'X轴功率谱密度', 'PSD X', '(m/s²)²/Hz',
                             ['Ax_m_s2'], 'Welch PSD', r'G_x(f)', OutputType.SPECTRUM),
            DerivedFieldMeta('PSD_Y', 'Y轴功率谱密度', 'PSD Y', '(m/s²)²/Hz',
                             ['Ay_m_s2'], 'Welch PSD', r'G_y(f)', OutputType.SPECTRUM),
            DerivedFieldMeta('PSD_Z', 'Z轴功率谱密度', 'PSD Z', '(m/s²)²/Hz',
                             ['Az_m_s2'], 'Welch PSD', r'G_z(f)', OutputType.SPECTRUM),
            DerivedFieldMeta('WPSD_X', 'X轴加权PSD', 'Weighted PSD X', '(m/s²)²/Hz',
                             ['PSD_X'], 'PSD × Wd²', r'G_x(f) \cdot W_d^2(f)',
                             OutputType.SPECTRUM),
            DerivedFieldMeta('WPSD_Y', 'Y轴加权PSD', 'Weighted PSD Y', '(m/s²)²/Hz',
                             ['PSD_Y'], 'PSD × Wd²', r'G_y(f) \cdot W_d^2(f)',
                             OutputType.SPECTRUM),
            DerivedFieldMeta('WPSD_Z', 'Z轴加权PSD', 'Weighted PSD Z', '(m/s²)²/Hz',
                             ['PSD_Z'], 'PSD × Wk²', r'G_z(f) \cdot W_k^2(f)',
                             OutputType.SPECTRUM),
            DerivedFieldMeta('AW_X', 'X轴频率加权加速度', 'Weighted Accel X', 'm/s²',
                             ['WPSD_X'], 'sqrt(∫WPSD·df)', r'\sqrt{\int G_{wx} df}'),
            DerivedFieldMeta('AW_Y', 'Y轴频率加权加速度', 'Weighted Accel Y', 'm/s²',
                             ['WPSD_Y'], 'sqrt(∫WPSD·df)', r'\sqrt{\int G_{wy} df}'),
            DerivedFieldMeta('AW_Z', 'Z轴频率加权加速度', 'Weighted Accel Z', 'm/s²',
                             ['WPSD_Z'], 'sqrt(∫WPSD·df)', r'\sqrt{\int G_{wz} df}'),
            DerivedFieldMeta('JERK_X', 'X轴急动度', 'Jerk X', 'm/s³',
                             ['Ax_m_s2'], 'd(Ax)/dt', r'\frac{d A_x}{dt}',
                             OutputType.CURVE),
            DerivedFieldMeta('JERK_Y', 'Y轴急动度', 'Jerk Y', 'm/s³',
                             ['Ay_m_s2'], 'd(Ay)/dt', r'\frac{d A_y}{dt}',
                             OutputType.CURVE),
            DerivedFieldMeta('JERK_Z', 'Z轴急动度', 'Jerk Z', 'm/s³',
                             ['Az_m_s2'], 'd(Az)/dt', r'\frac{d A_z}{dt}',
                             OutputType.CURVE),
            DerivedFieldMeta('STFT_SPEC', 'STFT时频谱', 'STFT Spectrogram', '|mag|²',
                             ['Az_m_s2'], 'STFT | Hanning 1s/75%', r'S(t,f)',
                             OutputType.SPECTRUM),
            DerivedFieldMeta('SRS_MAXIMAX', '冲击响应谱Maximax', 'SRS Maximax', 'm/s²',
                             ['Az_m_s2'], 'Smallwood(Q=10,ζ=0.05)', r'SRS(f)',
                             OutputType.SPECTRUM),
            DerivedFieldMeta('RFC_MATRIX', '雨流矩阵', 'Rainflow Matrix', '-',
                             ['Az_m_s2'], 'ASTM E1049 四点法', r'RF(ampl,mean)',
                             OutputType.MATRIX),
        ]
        for f in fields:
            self.derived_fields[f.field_code] = f

    # ──────────────────────────────────────────────
    # 算子定义
    # ──────────────────────────────────────────────

    def _register_operators(self):
        ops = [
            OperatorMeta('OP-CFC', 'CFC通道频率类滤波', 'CFC Filter',
                         'raw_signal', 'filtered_signal', '4阶Butterworth低通',
                         {'cfc_class': [60, 180, 600, 1000], 'order': 4},
                         [StandardRef('SAE J211-1', '4', 'CFC滤波标准'),
                          StandardRef('ISO 6487', '5.3', '通道频率等级')]),
            OperatorMeta('OP-VECSYN', '三轴矢量合成', 'Vector Synthesis',
                         '3-axis_accel', 'A_MAG', 'A_MAG = sqrt(Ax²+Ay²+Az²)',
                         {},
                         [StandardRef('ISO 2631-1', '5.6', '矢量评估')]),
            OperatorMeta('OP-INT2', '二重积分位移', 'Double Integration',
                         'filtered_accel', 'displacement', 'cumtrapz×2 + 0.5Hz高通',
                         {'hp_cutoff': 0.5, 'order': 2}, []),
            OperatorMeta('OP-DER', '一阶微分', 'Derivative',
                         'signal', 'derivative', 'np.diff × sr', {}, []),
            OperatorMeta('OP-FFT', 'Welch PSD估计', 'Welch PSD',
                         'signal', 'psd', 'Welch法 | Hanning窗 | 50%重叠',
                         {'nperseg': 1024, 'window': 'hann', 'overlap': 0.5},
                         [StandardRef('ASTM E1049', '6', 'PSD计算'),
                          StandardRef('ISO 2631-1', 'Annex A', '频率分析')]),
            OperatorMeta('OP-WK', 'Wk频率加权(Z轴)', 'Wk Weighting',
                         'PSD_Z', 'WPSD_Z', 'ISO 2631-1 Table 3 Wk曲线',
                         {'weighting_type': 'Wk'},
                         [StandardRef('ISO 2631-1', 'Table 3', 'Wk加权')]),
            OperatorMeta('OP-WD', 'Wd频率加权(X/Y轴)', 'Wd Weighting',
                         'PSD_X/PSD_Y', 'WPSD_X/WPSD_Y', 'ISO 2631-1 Table 4 Wd曲线',
                         {'weighting_type': 'Wd'},
                         [StandardRef('ISO 2631-1', 'Table 4', 'Wd加权')]),
            OperatorMeta('OP-RMS', '加权RMS值', 'Weighted RMS',
                         'WPSD', 'AW', 'aw = sqrt(∫WPSD·df) (0.5-80Hz)',
                         {'freq_range': [0.5, 80]},
                         [StandardRef('ISO 2631-1', '6.2', 'RMS评估')]),
            OperatorMeta('OP-HIC', 'HIC15头部损伤准则', 'HIC15',
                         'A_MAG_g', 'HIC15',
                         'HIC = max[(t2-t1)·(1/(t2-t1)·∫a·dt)^2.5]',
                         {'window_ms': 15, 'max_ms': 36},
                         [StandardRef('SAE J211-1', '5', 'HIC计算'),
                          StandardRef('FMVSS 208', '', '头部损伤标准')]),
            OperatorMeta('OP-VDV', '振动剂量值', 'VDV',
                         'filtered_accel', 'VDV',
                         'VDV = (∫a⁴(t)·dt)^(1/4)',
                         {'freq_range': [0.5, 80]},
                         [StandardRef('ISO 2631-1', '6.3', 'VDV评估')]),
            OperatorMeta('OP-SRS', '冲击响应谱', 'SRS',
                         'accel_signal', 'SRS',
                         'Smallwood递推 Q=10 | 0.5-100Hz',
                         {'Q': 10, 'freq_range': [0.5, 100], 'n_points': 60},
                         [StandardRef('MIL-STD-810H', '516.8', 'SRS冲击谱')]),
            OperatorMeta('OP-SRS_ATT', 'SRS衰减率', 'SRS Attenuation',
                         'SRS_exp/SRS_ctrl', 'SRS_ATT',
                         'η_SRS = (SRS_ctrl - SRS_exp)/SRS_ctrl × 100%', {}, []),
            OperatorMeta('OP-TR', '振动传递率', 'Transmissibility',
                         'PSD_out, PSD_in', 'TR',
                         'TR(f)=20·log10(sqrt(PSD_out/PSD_in))', {},
                         [StandardRef('ISO 10326-1', '10.3', '传递率')]),
            OperatorMeta('OP-RFC', '雨流计数', 'Rainflow Counting',
                         'stress_signal', 'cycle_ranges',
                         'ASTM E1049 四点法雨流计数', {},
                         [StandardRef('ASTM E1049', '5.4.4', '雨流计数'),
                          StandardRef('ISO 12108', '6', '疲劳载荷循环')]),
            OperatorMeta('OP-FDS', '疲劳损伤谱', 'Fatigue Damage Spectrum',
                         'rainflow_ranges', 'damage',
                         'Miner线性累积: D = Σ(ni/Ni) | b=8(Wöhler座椅发泡)',
                         {'b': 8, 'k': 4},
                         [StandardRef('ISO 12108', '7', '疲劳损伤累积')]),
            OperatorMeta('OP-STFT', '短时傅里叶变换', 'STFT',
                         'signal', 'spectrogram', 'STFT | Hanning窗',
                         {'nperseg': 256, 'overlap': 0.75},
                         [StandardRef('ISO 18431-4', '4', '时频分析')]),
            OperatorMeta('OP-FC-TRACK', '瞬时频率跟踪', 'Frequency Center Track',
                         'STFT_SPEC', 'FC_MEAN/FC_STD/FC_DRIFT',
                         'fc(t)=∫f·S(t,f)df/∫S(t,f)df; σ(fc)', {},
                         [StandardRef('ISO 18431-4', '5.2', '时频特征提取')]),
            OperatorMeta('OP-SD', 'ISO 2631-5 脊柱压缩应力', 'ISO 2631-5 S_d',
                         'seat_accel_3axis', 'S_d_MPa',
                         'S_d = (Σ D_k⁶)^(1/6) | SEAT→H→非线性→峰值提取→剂量融合',
                         {'weight_kg': 75.0, 'backrest_angle_deg': 23.0,
                          'c_x': 0.018, 'c_y': 0.015, 'c_z': 0.003},
                         [StandardRef('ISO 2631-5', '5', '腰椎响应计算'),
                          StandardRef('ISO 2631-5', '7', 'Sd评级')]),
            OperatorMeta('OP-SEAT', 'SEAT因子计算', 'SEAT Factor',
                         'AW_seat, AW_base', 'SEAT', 'SEAT = AW(seat)/AW(base)', {},
                         [StandardRef('ISO 10326-1', '10.2', 'SEAT因子')]),
            OperatorMeta('OP-OVTV', '整体振动总值', 'OVTV',
                         'AW_X/AW_Y/AW_Z', 'OVTV',
                         'OVTV = sqrt(kx²·aw_x² + ky²·aw_y² + kz²·aw_z²)',
                         {'k_x': 1.4, 'k_y': 1.4, 'k_z': 1.0},
                         [StandardRef('ISO 2631-1', '5.6', '多轴振动总值')]),
            OperatorMeta('OP-MAX', '峰值检测', 'Max Detection',
                         'time_series', 'peak_value/peak_time',
                         'PEAK = max(|x(t)|); t_peak = argmax(|x(t)|)', {},
                         [StandardRef('ISO 2631-1', '4.1', '峰值因子')]),
            OperatorMeta('OP-ATTEN', '衰减效率', 'Attenuation Efficiency',
                         'exp_value, ctrl_value', 'ATTEN_%',
                         'η = (ctrl - exp) / ctrl × 100%', {}, []),
            OperatorMeta('OP-BP-FILTER', 'Butterworth低通', 'Butterworth LPF',
                         'raw_signal', 'filtered', '2阶 Butterworth | fc=10Hz',
                         {'order': 2, 'cutoff': 10.0}, []),
        ]
        for o in ops:
            self.operators[o.operator_code] = o

    # ──────────────────────────────────────────────
    # 考核指标 — 完整 27 个指标 (三源融合)
    # ──────────────────────────────────────────────

    def _register_indicators(self):

        def _reg(code, cn, en, dim, locs, imus, fields, preq, pipe, fml, fml_latex, vars_,
                 unit, **kw):
            pipe_list = [pipe] if isinstance(pipe, str) else pipe
            self.indicators[code] = IndicatorMeta(
                indicator_code=code, display_name_cn=cn, display_name_en=en,
                evaluation_dimension=dim, applicable_locations=locs,
                source_imus=imus, source_raw_fields=fields,
                prerequisite_derived=preq, operator_pipeline=pipe_list,
                formula_text=fml, formula_latex=fml_latex, variables=vars_, unit=unit, **kw)

        _reg('HIC15', '头部损伤准则(15ms)', 'HIC15',
             '时域-冲击', ['head'],
             ['IMU1~2(头部眉心)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['A_MAG_g'], 'OP-CFC(CFC600)→OP-VECSYN→OP-HIC',
             'HIC15 = max[(t2-t1)·(avg(a))^2.5] | t2-t1≤15ms',
             r'HIC_{15} = \max_{t_2-t_1 \leq 15ms} \left[ (t_2-t_1) \cdot \left( \frac{1}{t_2-t_1} \int_{t_1}^{t_2} a(t) dt \right)^{2.5} \right]',
             {'a': '合加速度(g)', 't₂-t₁': '积分窗口(≤15ms)', 'ā': '窗口内平均加速度(g)'},
             '-', precision=1,
             threshold_pass='HIC15 ≤ 700 (FMVSS 208/ECE R94)',
             threshold_excellent='HIC15 ≤ 500 或魔椅<传统30%',
             standard_refs=[StandardRef('ISO 6487', '8.2', 'HIC计算方法'),
                            StandardRef('SAE J211-1', '5', 'HIC15计算'),
                            StandardRef('FMVSS 208', '', '乘员保护'),
                            StandardRef('ECE R94', '', '正面碰撞')],
             industry_references=['泛亚PATAC AEB座椅评测内部规程', 'Euro NCAP 2025 乘员保护评分'])

        _reg('ACC_H_PEAK', '头部峰值加速度', 'Head Acceleration Peak',
             '时域-冲击', ['head'],
             ['IMU1~2(头部眉心)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['A_MAG_g'], 'OP-CFC(CFC600)→OP-VECSYN→OP-MAX',
             'ACC_H_PEAK = max(|A_MAG_g(t)|)',
             r'a_{h,peak} = \max |A_{mag}(t)|_g',
             {'A_MAG_g': '合加速度(g)'}, 'g', precision=2,
             threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×70%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('SAE J211-1', '4', '加速度测量'),
                            StandardRef('ISO 2631-1', '4.1', '峰值因子')],
             industry_references=['SAE J2999-2017 THOR假人头部加速度基准值'])

        _reg('JERK_H', '头部加速度变化率', 'Head Jerk Peak',
             '时域-冲击', ['head'],
             ['IMU1~2(头部眉心)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['JERK_X', 'JERK_Y', 'JERK_Z'], 'OP-DER→OP-VECSYN→OP-MAX',
             'JERK_H = max(|d√(Ax²+Ay²+Az²)/dt|) / g',
             r'j_{peak,H} = \max_t \left| \frac{d}{dt} \sqrt{a_x^2(t) + a_y^2(t) + a_z^2(t)} \right|',
             {'a(t)': '头部三轴加速度(m/s²)'}, 'g/s', precision=1,
             threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×65%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('ISO 2631-1', 'Annex B', '加速度变化率')],
             industry_references=['传统座椅参考: 458.2±58.7 g/s (V4.06手册)'])

        _reg('SRS_MRS', '最大冲击响应谱峰值', 'SRS Maximum Response',
             '冲击域-结构响应', ['head', 'torso', 'seat_r'],
             ['IMU1~4'], ['Ax_m_s2', 'Az_m_s2'],
             ['SRS_MAXIMAX'], 'OP-CFC(CFC600)→OP-SRS(Q=10,ζ=0.05)',
             'SRS_MRS = max(SRS(f)) | f∈[5,30]Hz',
             r'SRS_{MRS} = \max_{f \in [5,30] Hz} SRS(f)',
             {'SRS(f)': '单自由度系统最大响应(m/s²)', 'Q=10': '品质因数(ζ=0.05)'},
             'm/s²', precision=2,
             threshold_pass='魔椅SRS < 传统SRS (5-30Hz)', threshold_excellent='魔椅SRS ≤ 传统×60%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('MIL-STD-810H', '516.8', 'SRS计算'),
                            StandardRef('ISO 18431-4', '4', 'SRS分析')],
             industry_references=['Smallwood 1981递推算法', 'JPL冲击试验规范'])

        _reg('SRS_Q', '冲击响应谱品质因数', 'SRS Quality Factor',
             '冲击域-参数', ['head'],
             ['IMU1~2(头部眉心)'], ['Az_m_s2'], [],
             'OP-SRS(Q=10)', 'Q = 10.0 (MIL-STD-810H标准), ζ=1/(2Q)=0.05',
             r'Q=10.0, \zeta = \frac{1}{2Q} = 0.05',
             {'Q': '品质因数', 'ζ': '阻尼比'}, '-', precision=1,
             threshold_pass='Q=10 (标准)', threshold_excellent='-',
             evaluation_direction=EvaluationDirection.NOMINAL,
             standard_refs=[StandardRef('MIL-STD-810H', '516.8', 'SRS参数设定')],
             description='属标准编制计算参数, 非直接测量指标')

        _reg('SRS_PV', '冲击响应谱伪速度', 'SRS Pseudo Velocity',
             '冲击域-响应', ['head'],
             ['IMU1~2(头部眉心)'], ['Az_m_s2'],
             ['SRS_MAXIMAX'], 'OP-SRS→(MRS→PV=MRS/(2πf_peak))',
             'PV = MRS / (2π × f_peak)',
             r'PV = \frac{MRS}{2\pi \cdot f_{peak}}',
             {'MRS': '最大响应谱值(m/s²)', 'f_peak': 'SRS峰值对应频率(Hz)'},
             'm/s', precision=1,
             threshold_pass='≤ 5 m/s', threshold_excellent='≤ 2 m/s',
             standard_refs=[StandardRef('MIL-STD-810H', '516.8', '伪速度')],
             description='结构需吸收的冲击能量需求')

        _reg('SRS_ATT', '冲击衰减率(频域)', 'SRS Attenuation Rate',
             '冲击域-隔振效率', ['head', 'torso', 'seat_r'],
             ['IMU1~10(全量)'], [],
             ['SRS(实验)', 'SRS(对照)'], 'OP-SRS_ATT(频域点对点)',
             'η_SRS(f) = (1 - SRS_exp(f)/SRS_ctrl(f)) × 100%; avg f∈[5,30]Hz',
             r'\eta_{SRS}(f) = \left(1 - \frac{SRS_{exp}(f)}{SRS_{ctrl}(f)}\right) \times 100\%',
             {'SRS_exp': '魔椅冲击响应谱', 'SRS_ctrl': '传统座椅冲击响应谱'},
             '%', precision=1,
             threshold_pass='η_SRS > 20% (有效衰减)', threshold_excellent='η_SRS > 35% (显著衰减)',
             evaluation_direction=EvaluationDirection.HIGHER_BETTER,
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('MIL-STD-810H', '516.8', '冲击衰减评估')],
             industry_references=['汽车座椅发泡削峰能力评估'])

        # ── 稳态舒适度 ──

        _reg('SEAT_Z', '座椅垂直传递率', 'SEAT Z-axis Factor',
             '频域-传递特性', ['seat_r'],
             ['IMU5~6(座垫)', 'IMU7~8(底座)'], ['Az_m_s2'],
             ['WPSD_Z(座垫)', 'WPSD_Z(底座)'],
             'OP-CFC(CFC1000)→OP-FFT→OP-WK→OP-SEAT',
             'SEAT_Z = √(∫WPSD_Z_seat(f)·df / ∫WPSD_Z_base(f)·df)',
             r'SEAT_Z = \sqrt{\frac{\int_{0.5}^{80} G_{w,seat}(f) df}{\int_{0.5}^{80} G_{w,base}(f) df}}',
             {'G_w(f)': 'Wk加权功率谱密度', 'seat': '座垫处', 'base': '底座处'},
             '-', precision=3,
             threshold_pass='SEAT_Z ≤ 1.0', threshold_excellent='SEAT_Z ≤ 0.8',
             standard_refs=[StandardRef('ISO 10326-1', '10.2', 'SEAT因子'),
                            StandardRef('ISO 2631-1', '5.3', 'Wk频率加权')],
             industry_references=['ISO 10326-1:2016 Annex A示例', '座椅悬架设计准则'])

        _reg('SEAT_XY', '座椅水平传递率', 'SEAT X/Y-axis Factor',
             '频域-传递特性', ['seat_r'],
             ['IMU5~6(座垫)', 'IMU7~8(底座)'], ['Ax_m_s2', 'Ay_m_s2'],
             ['WPSD_X(座垫)', 'WPSD_Y(座垫)', 'WPSD_X(底座)', 'WPSD_Y(底座)'],
             'OP-CFC(CFC600)→OP-VECSYN→OP-FFT→OP-WD→OP-SEAT',
             'SEAT_XY = max(AW_XY_seat/AW_XY_base_X, AW_XY_seat/AW_XY_base_Y)',
             r'SEAT_{XY} = \max(\frac{a_{w,xy}^{seat}}{a_{w,xy}^{base,X}}, \frac{a_{w,xy}^{seat}}{a_{w,xy}^{base,Y}})',
             {}, '-', precision=3,
             threshold_pass='SEAT_XY ≤ 1.0', threshold_excellent='SEAT_XY ≤ 0.8',
             standard_refs=[StandardRef('ISO 10326-1', '10.3', 'SEAT'),
                            StandardRef('ISO 10326-2', 'Annex B', 'CSD')],
             description='座垫X/Y方向振动传递率, Wd加权')

        _reg('AW_Z', 'Z向频率加权RMS加速度', 'Weighted RMS Accel Z',
             '频域-舒适度', ['head', 'torso', 'seat_r', 'sternum'],
             ['IMU5~6(座垫)/IMU3~4(躯干)/IMU9~10(胸骨)'], ['Az_m_s2'],
             ['PSD_Z', 'WPSD_Z'], 'OP-CFC(CFC1000)→OP-FFT→OP-WK→OP-RMS',
             'aw_z = sqrt(∫WPSD_Z(f)·df) | f∈[0.5,80]Hz',
             r'a_{wz} = \sqrt{\int_{0.5}^{80} G_{wz}(f) df}',
             {'G_wz': 'Wk加权PSD'}, 'm/s²', precision=3,
             threshold_pass='aw_z ≤ 0.315 (8h暴露)', threshold_excellent='aw_z ≤ 0.2',
             standard_refs=[StandardRef('ISO 2631-1', '5.3.2', '频率加权'),
                            StandardRef('ISO 2631-1', 'Annex C', '舒适度边界')],
             industry_references=['EU Directive 2002/44/EC 职业振动暴露'])

        _reg('AW_XY', '水平频率加权RMS加速度', 'Weighted RMS Accel XY',
             '频域-舒适度', ['head', 'torso', 'seat_r', 'sternum'],
             ['IMU5~6(座垫)/IMU3~4(躯干)'], ['Ax_m_s2', 'Ay_m_s2'],
             ['PSD_X', 'PSD_Y', 'WPSD_X', 'WPSD_Y'],
             'OP-CFC→OP-VECSYN→OP-FFT→OP-WD→OP-RMS',
             'aw_xy = sqrt(∫WPSD_XY(f)·df) | f∈[0.5,80]Hz, Wd加权',
             r'a_{w,xy} = \sqrt{\int_{0.5}^{80} G_{w,xy}(f) df}',
             {'G_w,xy': 'Wd加权PSD(XY合成)'}, 'm/s²', precision=3,
             threshold_pass='aw_xy < 0.5', threshold_excellent='aw_xy < 0.3',
             standard_refs=[StandardRef('ISO 2631-1', 'Table 4', 'Wd加权')],
             description='水平方向Wd加权RMS, 各位置对比评价侧向振动传递梯度')

        _reg('OVTV', '多轴振动综合总值', 'Overall Vibration Total Value',
             '频域-综合', ['seat_r'],
             ['IMU5~6(座垫)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['AW_X', 'AW_Y', 'AW_Z'], 'OP-CFC→OP-FFT→OP-WK/WD→OP-RMS→OP-OVTV',
             'OVTV = sqrt(kx²·AW_X² + ky²·AW_Y² + kz²·AW_Z²) | kx=ky=1.4,kz=1.0',
             r'OVTV = \sqrt{k_x^2 a_{wx}^2 + k_y^2 a_{wy}^2 + k_z^2 a_{wz}^2}',
             {'kx': '1.4', 'ky': '1.4', 'kz': '1.0'}, 'm/s²', precision=3,
             threshold_pass='OVTV < 0.5', threshold_excellent='OVTV < 0.3',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('ISO 2631-1', '5.6', '多轴振动总值'),
                            StandardRef('ISO 2631-1', 'Table 5', '乘员舒适度')],
             industry_references=['乘用车座椅舒适度联合评估模型'])

        _reg('R_FACTOR', '侧向/垂向振动比率', 'R Factor',
             '频域-方向性', ['seat_r'],
             ['IMU5~6(座垫)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             [], 'OP-VECSYN→STD_RATIO',
             'R_FACTOR = σ(ax+ay) / (σ(az) + 1e-9)',
             r'R = \frac{\sigma(a_x + a_y)}{\sigma(a_z) + \epsilon}',
             {'σ()': '信号标准偏差'}, '-', precision=2,
             threshold_pass='R < 1.0 (垂向主导)', threshold_excellent='R < 0.5',
             description='R<1→垂向主宰, R≈1→均衡, R>1→侧向主宰(curves)')

        # ── 动态舒适度 ──

        _reg('VDV_Z', 'Z向振动剂量值', 'VDV Z-axis',
             '时域-剂量', ['seat_r'],
             ['IMU5~6(座垫)'], ['Az_m_s2'],
             ['AZ_FILTERED'], 'OP-CFC(CFC1000)→OP-WK(时域)→OP-VDV',
             'VDV_Z = (∫aw_z⁴(t)·dt)^(1/4)',
             r'VDV_z = \left( \int_0^T a_{wz}^4(t) dt \right)^{1/4}',
             {'a_wz(t)': '频率加权后的Z轴加速度(m/s²)', 'T': '总暴露时间(s)'},
             'm/s^1.75', precision=2,
             threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×70%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('ISO 2631-1', '4.2.2', 'VDV评估'),
                            StandardRef('GB/T 4970-2009', '5.3', 'VDV')],
             industry_references=['BS 6841:1987 VDV应用指南'])

        _reg('TR_Z', 'Z轴振动传递率峰值(dB)', 'Transmissibility Z Peak',
             '频域-传递特性', ['seat_r'],
             ['IMU5~6(座垫)', 'IMU7~8(底座)'], ['Az_m_s2'],
             ['PSD_Z(座垫)', 'PSD_Z(底座)', 'PSD_FREQ'],
             'OP-CFC(CFC1000)→OP-FFT→OP-CSD→OP-TR',
             'TR_Z(f) = 20·log10(√(PSD_out(f)/PSD_in(f)))',
             r'TR(f) = 20 \cdot \log_{10} \sqrt{\frac{G_{out}(f)}{G_{in}(f)}}',
             {'G_out': '座垫PSD', 'G_in': '底座PSD'},
             'dB', precision=2, output_type=OutputType.CURVE,
             threshold_pass='TR(f) < 0 dB (0.5-50Hz)', threshold_excellent='TR(f) < -3 dB (共振频段)',
             standard_refs=[StandardRef('ISO 10326-1', '10.3', '传递率'),
                            StandardRef('ISO 10326-2', 'Annex B', '传递函数')],
             industry_references=['LMS Test.Lab传递率分析模块'])

        # ── 位移与衰减效率 ──

        _reg('DISP_HR', '头部三维合成位移峰值', 'Head 3D Displacement Peak',
             '时域-位移', ['head'],
             ['IMU1~2(头部眉心)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['DISP_3D'], 'OP-CFC(CFC600)→OP-INT2→OP-VECSYN→OP-MAX',
             'DISP_HR = max(√(Dx²(t) + Dy²(t) + Dz²(t)))',
             r'D_{HR} = \max_t \sqrt{D_x^2(t) + D_y^2(t) + D_z^2(t)}',
             {'D(t)': '二重积分位移(mm)', 'a(t)': 'CFC600滤波后加速度'},
             'mm', precision=1,
             threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×60%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('ISO 2631-5', 'Annex B', '相对位移'),
                            StandardRef('VDI 2057-1', '5', '人体振动')],
             industry_references=['传统座椅参考: 182.5±45.6 mm (V4.06手册)'])

        _reg('DISP_TR', '位移轨迹峰值', 'Displacement Trajectory Peak',
             '时域-位移', ['torso'],
             ['IMU3~4(躯干T8)'], ['Az_m_s2'],
             [], 'OP-CFC→OP-INT2→MAX',
             'DISP_TR = max(|d_z(t)|) | d_z = ∬az·dt² + HP(0.5Hz)去漂',
             r'd_{TR} = \max_t |d_z(t)|',
             {'d_z': 'Z轴积分位移(mm)', 'HP': '0.5Hz高通滤波'},
             'mm', precision=1,
             threshold_pass='d_TR < 200mm', threshold_excellent='d_TR < 100mm',
             description='躯干Z轴绝对位移 — 评价座椅靠背约束效果')

        _reg('ATTEN_H', '头部衰减效率', 'Head Attenuation Efficiency',
             '隔振-综合', ['head'],
             ['IMU1~2(头部), IMU7~8(底座)'], [],
             ['DISP_HR(实验)', 'DISP_HR(对照)'], 'OP-ATTEN',
             'η_H = (DISP_HR_ctrl - DISP_HR_exp) / DISP_HR_ctrl × 100%',
             r'\eta_H = \frac{D_{HR,ctrl} - D_{HR,exp}}{D_{HR,ctrl}} \times 100\%',
             {'D_HR_ctrl': '传统座椅头部位移(mm)', 'D_HR_exp': 'GQY魔椅头部位移(mm)'},
             '%', precision=1, output_type=OutputType.SCALAR,
             threshold_pass='η > 20% (有效改善)', threshold_excellent='η > 35% (显著改善)',
             evaluation_direction=EvaluationDirection.HIGHER_BETTER,
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('V4.06手册', '附录B', '衰减效率定义')],
             industry_references=['V4.06参考值: 29.7±2.6%'])

        # ── 疲劳损伤 ──

        _reg('RFC_CC', '雨流循环计数', 'Rainflow Cycle Count',
             '疲劳-计数', ['seat_r'],
             ['IMU5~6(座垫)'], ['Az_m_s2'],
             [], 'OP-RFC',
             'RFC_CC = 有效循环总数 (ASTM E1049四点法)',
             r'N_{cycles} = \sum valid\_cycles',
             {'cycles': '雨流计数配对循环(振幅>1e-9)'}, '-', precision=0,
             threshold_pass='N < 20 (轻载)', threshold_excellent='N < 10',
             standard_refs=[StandardRef('ASTM E1049', '5.4.4', '雨流计数'),
                            StandardRef('ISO 12108', '6', '疲劳载荷循环')],
             description='各部位承受的交变振动载荷循环总次数')

        _reg('FDS_D', '累积疲劳损伤指数', 'Fatigue Damage Spectrum D',
             '疲劳-累积损伤', ['seat_r'],
             ['IMU5~8'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['RFC_MATRIX'], 'OP-CFC→OP-RFC→OP-FDS',
             'D = Σ(n_i/N_i) | N_i = k·S_i^(-b), b=8(座椅发泡), k=4',
             r'D = \sum \frac{n_i}{N_i}, N_i = k \cdot S_i^{-b}',
             {'ni': '第i级应力幅循环数', 'Ni': '疲劳寿命', 'b=8': 'S-N曲线斜率(发泡)', 'k=4': 'S-N截距'},
             '-', precision=4,
             threshold_pass='D < 0.7 (可接受)', threshold_excellent='D < 0.3 (优秀)',
             standard_refs=[StandardRef('ASTM E1049', '', '雨流计数'),
                            StandardRef('ISO 12108', '7', '疲劳损伤累积'),
                            StandardRef('FKM Guideline', '', '非线性疲劳')],
             industry_references=['nCode GlyphWorks标准疲劳分析流程'])

        _reg('FDS_R', '疲劳剩余寿命', 'Fatigue Remaining Life',
             '疲劳-剩余寿命', ['seat_r'],
             ['IMU5~6(座垫)'], [],
             ['FDS_D'], '(派生)',
             'FDS_R = max(0, 1.0 - FDS_D)',
             r'R = \max(0, 1 - D)',
             {'D': 'FDS_D累积损伤度'}, '-', precision=3,
             threshold_pass='R > 0.7', threshold_excellent='R > 0.9',
             evaluation_direction=EvaluationDirection.HIGHER_BETTER,
             standard_refs=[StandardRef("Miner's Rule / BS 7608", '', '剩余寿命')],
             description='由FDS_D派生, 0→寿命耗尽; 1→寿命完全剩余')

        # ── 时频分析 ──

        _reg('STFT_FC', '瞬时频率重心标准差', 'STFT Frequency Center Std',
             '时频域-频率', ['torso', 'sternum'],
             ['IMU3~4(躯干), IMU9~10(胸骨)'], ['Ay_m_s2'],
             ['STFT_SPEC', 'STFT_FREQ', 'STFT_TIME'],
             'OP-STFT(Hanning 1s/75%)→OP-FC-TRACK',
             'STFT_FC = σ(fc(t)) | fc(t)=∫f·S(t,f)df/∫S(t,f)df',
             r'\sigma(f_c) = \sqrt{\frac{1}{T}\int (f_c(t) - \bar{f_c})^2 dt}',
             {'fc(t)': '瞬时频率重心(Hz)', 'S(t,f)': '时频谱'}, 'Hz', precision=2,
             threshold_pass='魔椅σ(fc) < 传统σ(fc)', threshold_excellent='魔椅σ(fc) ≤ 传统×50%',
             comparison_method=ComparisonMethod.RELATIVE,
             standard_refs=[StandardRef('ISO 18431-4', '5.2', '时频特征'),
                            StandardRef('SAE J2475', '', '非平稳分析')],
             industry_references=['蛇形驾驶侧翼支撑刚度诊断'])

        _reg('STFT_KT', '时频频率扩展', 'STFT Frequency Kurtosis',
             '时频域-扩展', ['torso', 'sternum'],
             ['IMU9~10(胸骨)'], ['Az_m_s2'],
             ['STFT_SPEC', 'fc'], 'OP-STFT→EXTRACT_KT',
             'STFT_KT = √(Σ(f - fc)²×P_f / ΣP_f) — 频率标准差',
             r'\sigma_f = \sqrt{\frac{\sum (f-f_c)^2 P_f}{\sum P_f}}',
             {'P_f': '功率谱(f)', 'fc': '频率重心(Hz)'}, 'Hz', precision=2,
             threshold_pass='KT < 3 (窄带)或>10 (过度宽带)', threshold_excellent='3 < KT < 8 (合理分布)',
             description='KT<3→纯频率共振风险; KT>10→宽带振动浑沌')

        _reg('STFT_CE', '时频能量集中度', 'STFT Energy Concentration',
             '时频域-集中度', ['torso', 'sternum'],
             ['IMU9~10(胸骨)'], ['Az_m_s2'],
             ['STFT_SPEC'], 'OP-STFT→EXTRACT_CE',
             'STFT_CE = max(P_f) / mean(P_f) — ≥1.0',
             r'CE = \frac{\max_f P(f)}{\frac{1}{|F|}\sum_f P(f)}',
             {'P_max': '最大频率功率', 'P_avg': '平均频率功率'}, '-', precision=2,
             threshold_pass='CE < 5 (能量分散)', threshold_excellent='CE < 3 (均匀分布)',
             description='CE≈1→均匀宽带; CE≥5→能量在共振频率集中; CE≥10→尖锐共振峰')

        # ── 脊柱健康 ──

        _reg('S_D', '腰椎每日等效压缩应力', 'Daily Equivalent Static Compressive Stress',
             '生物力学-脊柱', ['seat_r'],
             ['IMU5~6(座垫)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['HUMAN_SPINE_AX', 'HUMAN_SPINE_AY', 'HUMAN_SPINE_AZ'],
             'OP-SD',
             'S_d = (Σ D_k⁶)^(1/6) | D_k⁶ = (cx·Dxk)⁶+(cy·Dyk)⁶+(cz·Dzk)⁶',
             r'S_d = \left[ \sum_k (0.018 D_{xk})^6 + (0.015 D_{yk})^6 + (0.003 D_{zk})^6 \right]^{1/6}',
             {'cx=0.018': 'X轴方向加权系数', 'cy=0.015': 'Y轴方向加权系数',
              'cz=0.003': 'Z轴方向加权系数', 'D_k': '第k次冲击事件腰椎响应峰值(m/s²)'},
             'MPa', precision=4,
             threshold_pass='S_d < 0.5 MPa (绿色)', threshold_excellent='S_d < 0.3 MPa',
             standard_refs=[StandardRef('ISO 2631-5', '5', '腰椎响应计算'),
                            StandardRef('ISO 2631-5', '7', 'S_d评级'),
                            StandardRef('ISO 2631-5', 'Annex A', '方向加权系数')],
             industry_references=['ISVR Griffin团队半躺坐姿研究', 'MDPI重型车辆振动暴露研究',
                                  'Seidel (2005) LSTM脊柱模型'])

        # ── 通用基础指标 ──

        _reg('ACC_RMS', '三轴合成加速度RMS', 'Accel Resultant RMS',
             '通用-振动能量', ['head', 'torso', 'seat_r', 'seat_bottom', 'sternum'],
             ['IMU1~10(全量)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['A_MAG'], 'OP-VECSYN→RMS',
             'ACC_RMS = sqrt(mean(A_MAG²))',
             r'a_{rms} = \sqrt{\frac{1}{N}\sum A_{mag}^2}',
             {'A_MAG': '合加速度(m/s²)'}, 'm/s²', precision=3,
             threshold_pass='a_rms < 1.0', threshold_excellent='a_rms < 0.5',
             standard_refs=[StandardRef('ISO 2631-1', '5.2', 'RMS评估')],
             description='反映指定位置的总体振动能量水平, 全位置通用')

        _reg('ACC_PEAK', '三轴合成加速度峰值', 'Accel Resultant Peak',
             '通用-冲击强度', ['head', 'torso', 'seat_r', 'seat_bottom', 'sternum'],
             ['IMU1~10(全量)'], ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2'],
             ['A_MAG'], 'OP-VECSYN→MAX',
             'ACC_PEAK = max(A_MAG)',
             r'a_{peak} = \max A_{mag}',
             {'A_MAG': '合加速度(m/s²)'}, 'm/s²', precision=2,
             threshold_pass='a_peak < 5.0', threshold_excellent='a_peak < 3.0',
             standard_refs=[StandardRef('ISO 2631-1', '4.1', '峰值')],
             description='该位置在事件窗口内的瞬时最大冲击, 全位置通用')

    # ──────────────────────────────────────────────
    # 指标详情 (INDICATOR_DETAIL — 来源: core_types.py 实例视图)
    # ──────────────────────────────────────────────

    def _register_indicator_details(self):

        def _add(code, **kw):
            self.indicator_details[code] = IndicatorDetail(indicator_code=code, **kw)

        # --- 稳态舒适度 ---

        _add('SEAT_Z',
            category='steady_state', location_dependency='two_positions',
            location_dependency_label='需要 2 个位置',
            required_locations=['seat_r', 'seat_bottom'],
            primary_imu='座椅 IMU5_座垫R点-1', reference_imu='座椅 IMU7_座椅底部-1',
            data_fields='az[点数N]@seat_bottom(地板激励) + az[点数N]@seat_r(座椅响应)',
            operator_pipeline_detail=(
                '① PSD算子(Welch法, nperseg≤1024): az_seat→(f_seat, PSD_seat), az_floor→(f_floor, PSD_floor)\n'
                '② Weighting算子(freq Wk): PSD→PSD_w = PSD×Wk(f)²\n'
                '    Wk(f): f<0.5→0.5; 0.5-2→f; 2-5→2; 5-16→10/f; 16-80→10/f; f≥80→0 (ISO 2631-1 Table 3)\n'
                '③ numpy梯形积分: I_seat=∫PSD_seat_w df, I_floor=∫PSD_floor_w df\n'
                '④ SEAT_Z = √(I_seat/I_floor)'
            ),
            formula_detail=(
                'SEAT_Z = √( ∫₀^{fs/2} PSD_seat(f)×[Wk(f)]² df / ∫₀^{fs/2} PSD_floor(f)×[Wk(f)]² df )\n'
                '☑ Coherence验证: 计算CSD→mean(coh), coh<0.5时Warning'
            ),
            calculation_logic=(
                'SEAT因子 — 座椅有效振幅传递率 (ISO 10326-2)\n'
                '衡量座椅对0.5-80Hz垂直振动的衰减效率\n'
                'SEAT_Z < 1: 座椅主动隔振(优秀)\n'
                'SEAT_Z = 1: 座椅无衰减(中性)\n'
                'SEAT_Z > 1: 座椅放大振动(不良)'
            ),
            single_point_description='单点不可用: 降级为RMS×1后恒≈自比值1.0',
            two_point_description='✅ 必须: seat_r(AZ) vs seat_bottom(AZ) 频率域PSD比值',
            three_point_description='不适用')

        _add('SEAT_XY',
            category='steady_state', location_dependency='two_positions',
            location_dependency_label='需要 2 个位置',
            required_locations=['seat_r', 'seat_bottom'],
            primary_imu='IMU5_座垫R点-1', reference_imu='IMU7_座椅底部-1',
            data_fields='ax[点数N]+ay[点数N]@seat_bottom, ax[点数N]+ay[点数N]@seat_r',
            operator_pipeline_detail=(
                '① Vector算子.synthesize_xy(ax,ay): xy_seat=√(ax²+ay²)@seat_r, xy_floor=√(ax²+ay²)@seat_bottom\n'
                '② PSD算子(Welch): xy_seat→(f, PSD_seat), xy_floor→(f, PSD_floor)\n'
                '③ Weighting算子(freq Wd): PSD_w=PSD×Wd(f)²\n'
                '    Wd(f): f<0.5→1; 0.5-2→f/0.5; 2-5→1; 5-16→5/f; 16-80→80/f²; f≥80→0\n'
                '④ 梯形积分 + √(int_seat/int_floor) = SEAT_XY'
            ),
            formula_detail='SEAT_XY = √( ∫₀^{fs/2} PSD(xy_seat)×[Wd(f)]² df / ∫₀^{fs/2} PSD(xy_floor)×[Wd(f)]² df )',
            calculation_logic='SEAT_XY — 座椅水平振幅传递率 (ISO 10326-2)，Wd加权',
            single_point_description='单点不可用',
            two_point_description='✅ 必须: seat_r(XY合成) vs seat_bottom(XY合成) 频率域PSD比值',
            three_point_description='不适用')

        _add('AW_Z',
            category='steady_state', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① Weighting算子.apply_weighting_z_via_freq(az, sr): 频域Wk加权\n'
                '    FFT(az)→Wk(f)→IFFT\n'
                '② RMS: AW_Z = √[ (1/N)×Σ(az_weighted_i²) ]'
            ),
            formula_detail='az → FFT→Wk(f)→IFFT → aw[0..N-1]\nAW_Z = √( Σᵢ aw_i² / N )',
            calculation_logic='ISO 2631-1 Wk加权垂直加速度RMS。head/torso/seat_r三位置对比构成振动传递梯度',
            single_point_description='✅ 单IMU: az_raw → Wk时域卷积 → √mean(weighted²)',
            two_point_description='🔶 seat_r vs head AW_z比值 反映 人头对臀点振动的隔振效率',
            three_point_description='🔶 head/torso/seat_r 三个AW_z构成完整的Z轴振动传递梯度曲线')

        _add('AW_XY',
            category='steady_state', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='ax[点数N]+ay[点数N]@指定位置',
            operator_pipeline_detail=(
                '① VectorOperator.synthesize_xy(ax,ay): xy=√(ax_i²+ay_i²) for i=0..N-1\n'
                '② WeightingOperator.apply_weighting_xy_via_freq(xy, sr): 频域Wd加权'
            ),
            formula_detail='xy_i = √(ax_i²+ay_i²)\nAW_XY = √( Σᵢ xyw_i² / N )',
            calculation_logic='ISO 2631-1 Wd加权水平加速度RMS。多位置对比可评价侧向振动沿人体的传递路径',
            single_point_description='✅ 单IMU: (ax,ay)→√合成→Wd滤波→RMS',
            two_point_description='🔶 两位置 AW_xy 对比可评价侧向振动衰减效率',
            three_point_description='🔶 head/torso/seat_r 三位置构成水平振动传递梯度')

        _add('OVTV',
            category='steady_state', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① VectorOperator.synthesize(ax,ay,az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
                '② 四次方累计: D = mean(a_total_i⁴) × N/sr\n'
                '③ OVTV = D^(0.25) = (∫a_total⁴ dt)^(1/4)'
            ),
            formula_detail='a_total_i = √(ax_i²+ay_i²+az_i²)\nOVTV = (Σ a_total_i⁴ × dt)^(1/4)',
            calculation_logic='BS 6841 四次方振动剂量\n四次方积分比RMS(²)更敏感于振动峰值因子',
            single_point_description='✅ 单IMU三轴合成, 四次方积分, 4th-root',
            two_point_description='🔶 seat_r vs head OVTV差值 反映全身振动剂量衰减率',
            three_point_description='不适用')

        _add('R_FACTOR',
            category='steady_state', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① Vector: lateral_strength = ax + ay (横向求和)\n'
                '② σ(ax+ay) = np.std(ax+ay), σ(az) = np.std(az)\n'
                '③ R_FACTOR = σ(ax+ay)/(σ(az)+1e-9)'
            ),
            formula_detail='R_FACTOR = σ(ax+ay) / [ σ(az) + 0.001 ]',
            calculation_logic='R因子 — 侧向/垂向振动方向性比率。head vs seat_r差值反映人体对方向振动的选择性衰减',
            single_point_description='✅ 单IMU: 标准差比值(标量)',
            two_point_description='🔶 head vs seat_r R_FACTOR差异 反映 人体对水平/垂直振动的衰减不对称性',
            three_point_description='不适用')

        # --- 动态舒适度 ---

        _add('VDV_Z',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① WeightingOp.apply_weighting_z_via_freq(az, sr): 频域Wk加权\n'
                '    FFT→Wk(f)→IFFT\n'
                '② dt = 1.0/sr\n'
                '③ VDV_Z = [ Σᵢ azw_i⁴ × dt ] ^ (1/4)'
            ),
            formula_detail='az_raw[N] → Wk时域滤波 → azw[N]\nVDV_Z = ( Σᵢ azw_i⁴ × dt )^(1/4)',
            calculation_logic='BS 6841 累积振动剂量值\nWk加权+四次方积分 → 对高冲击事件的剂量累积极为敏感',
            single_point_description='✅ 单IMU: az→Wk时域滤波→四次方积分→4th-root',
            two_point_description='🔶 head VDV / seat_r VDV 比值 = 座椅对振动剂量的隔振效率',
            three_point_description='🔶 head→torso→seat_r VDV梯度 沿脊柱下行')

        _add('TR_Z',
            category='dynamic', location_dependency='two_positions',
            location_dependency_label='需要 2 个位置',
            required_locations=['seat_r', 'seat_bottom'],
            primary_imu='IMU5_座垫R点-1(响应y) + IMU7_座椅底部-1(输入x)',
            data_fields='az[点数N]@seat_bottom, az[点数N]@seat_r, 两通道需同步采样',
            operator_pipeline_detail=(
                '① CSDOperator.compute(az_floor, az_seat, sr, nperseg≤256):\n'
                '    - welch(floor) → Pxx\n'
                '    - welch(seat)  → Pyy\n'
                '    - csd(floor,seat) → Pxy\n'
                '    - H(f)=Pxy(f)/(Pxx(f)+1e-12)\n'
                '    - coherence(f) = |Pxy|²/(Pxx·Pyy+1e-12)\n'
                '② CSD.transfer_function_db: |H(f)|→20log10→dB谱\n'
                '    - mask 0.5-50Hz找峰值\n'
                '    - TR_Z = peak_dB(0.5-50Hz)'
            ),
            formula_detail='CSD(Floor→Seat): H(f)=CSD(floor,seat,f)/PSD(floor,f)\n'
                          'TR_Z = max[ H_dB(f) for f∈(0.5,50)Hz ]',
            calculation_logic='TR_Z — 频率域跨位置振动传递函数峰值dB\n>0dB: 振动被放大(共振峰值)\n<0dB: 振动衰减',
            single_point_description='单点不可用: 自CSD→H≈1→0dB',
            two_point_description='✅ 必须: seat_r vs seat_bottom CSD 传递函数 峰值dB',
            three_point_description='🔴 完整TR链: seat_bottom→seat_r→torso→head 构成三级传递率CSD链')

        # --- 位移 ---

        _add('DISP_TR',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU3_躯干T8-1 (torso)',
            data_fields='az[点数N]@torso',
            operator_pipeline_detail=(
                '① IntegrationOperator.integrate_to_displacement(az, sr):\n'
                '    - scipy signal.butter(2, 0.5/sr·2, HP): 消除积分漂移\n'
                '    - acc_f = signal.filtfilt(b,a,az)\n'
                '    - vel   = cumsum(acc_f)/sr          (一次积分 → 速度)\n'
                '    - vel_f = filtfilt(b,a,vel)          (HP二次滤波)\n'
                '    - disp  = cumsum(vel_f)/sr × 1000   (二次积分→位移[mm])\n'
                '② DISP_TR = max(|disp|)'
            ),
            formula_detail=(
                'Step1: az → Butterworth HP(0.5Hz,2nd) → az_f[N]\n'
                'Step2: v(tᵢ) = Σⱼ[0→i] az_f(j)×Δt , v_f=HP_filter(v)\n'
                'Step3: d(tᵢ) = Σⱼ[0→i] v_f(j)×Δt × 1000.0  [mm]\n'
                'Step4: DISP_TR = max(|d_i|,∀i)  [峰值位移, mm]\n'
                'Δt = 1/sr, HP双通已消DC, 无需额外-mean(d)'
            ),
            calculation_logic='振动引起相对空间的绝对位移轨迹(mm)。0.5Hz HP消除低频漂移。seat_r vs torso DISP对比: 评价座椅靠背对人体的约束效果',
            single_point_description='✅ 单IMU: az→HP→1次积分→HP→2次积分→max_abs(×1000)',
            two_point_description='🔶 seat_r vs torso DISP_TR对比: 臀部(座) vs 躯干(背)相对位移差异',
            three_point_description='不适用')

        # --- 疲劳 ---

        _add('RFC_CC',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='az[点数N]@seat_r',
            operator_pipeline_detail=(
                '① 提取az信号的局部极值序列 (peak/valley检测)\n'
                '② RainflowOperator.count(az): 四峰谷雨流计数法(ASTM E1049-85)\n'
                '    - 4-point 分组规则(S0,S1,S2,S3): 配对Δ₁=Δ₂循环\n'
                '    - 生成amplitude_ₖ, mean_ₖ 值对\n'
                '③ RFC_CC = len(valid_cycles) (过滤出 amplitude>1e-9 的有效循环数)'
            ),
            formula_detail=(
                'Peaks[] = {ai if ai>ai-1 and ai>ai+1}\n'
                'Valleys[] = {ai if ai<ai-1 and ai+1 and ai<ai+1}\n'
                'Rainflow(S0,S1,S2,S3, peaks/valleys):\n'
                '   Δ₁ = |S1-S0|, Δ₂ = |S2-S1|\n'
                '   if Δ₁≤Δ₂: 生成cycle(amplitude=Δ₁/2, mean=(S0+S1)/2)\n'
                '     pop(S0,S1) from list\n'
                '   else: i+=1 (跳过)\n'
                'RFC_CC = Σ valid_cycles (amp_i>1e-9)'
            ),
            calculation_logic='应力/振动循环计数。统计独立振动负载循环的总次数。多位置循环数对比判断各部位承受的交变振动载荷差异',
            single_point_description='✅ 单IMU: az→极值提取→四峰谷pairing→cycle count',
            two_point_description='🔶 多位置 RFC_CC 对比 判断 各部位的交变载荷次数差异',
            three_point_description='不适用')

        _add('FDS_D',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='az[点数N]@seat_r → rainflow cycles[]',
            operator_pipeline_detail=(
                '① RainflowOperator.count(az) → RF_result {cycles, amplitudes, means}\n'
                '② FDSOperator.compute(RF_result):\n'
                '    S-N曲线: Nᵢ = k × Sᵢ^(-b)  [Sᵢ=amplitude]\n'
                '    默认 b=8 (S-N曲线的Basquin指数,座椅发泡)\n'
                '    total_damage D = Σᵢ (1/(Nᵢ+1e-12))\n'
                '③ FDS_D = D'
            ),
            formula_detail=(
                'Rainflow(az)→{amp_i,∀i}\n'
                'N_i = k × amp_i^(-b) = 1.0 × amp_i^(-8)  [S-N curve]\n'
                'FDS_D = Σᵢ amp_i^8   [Miner累积, 如果>1.0 ⇒ 预计疲劳失效]\n'
                '同时: LEQ = (Σᵢ (amp_i/9.81)^4 / (#cycles))^0.25'
            ),
            calculation_logic='Miner线性累积疲劳损伤度 (BS 7608 / ASTM E1049)。b=8: 座椅发泡Basquin指数。总损伤D的累计, D≥1.0时表明到达疲劳寿命极限',
            single_point_description='✅ 单IMU: az→Rainflow→S-N curve(b=8)→ΣMiner累积损伤',
            two_point_description='🔶 seat_r vs torso FDS_D对比 揭示 座垫 vs 靠背的疲劳风险分布',
            three_point_description='不适用')

        _add('FDS_R',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='az[点数N]@seat_r → FDS_D派生',
            operator_pipeline_detail=(
                '① 先计算 FDS_D (rainflow → Miner 累积损伤度)\n'
                '② FDS_R = max(0.0, 1.0 - FDS_D)\n'
                '    0≤FDS_R≤1: 比例剩余疲劳寿命\n'
                '    0: 寿命已耗尽; 1: 寿命完全剩余'
            ),
            formula_detail='FDS_R = max(0, 1.0 - FDS_D)\nFDS_D = total Miner损伤度\n   0.0: 未损伤\n   0.1: 寿命用去10%\n   1.0: 寿命用去100%, FDS_R=0',
            calculation_logic='疲劳剩余寿命(由FDS_D派生, 0-1区间)',
            single_point_description='✅ 从FDS_D派生: R = max(0, 1-D)',
            two_point_description='不适用',
            three_point_description='不适用')

        # --- 时频分析 ---

        _add('STFT_FC',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU9_胸骨剑突-1 (sternum)',
            data_fields='az[点数N]@sternum',
            operator_pipeline_detail=(
                '① STFTOperator.compute(az, sr): scipy signal.stft\n'
                '    → spectrogram[S(freq)×T(time)]\n'
                '② extract_features:\n'
                '    Power per freq: P_f = Σⱼ spectrum[f,j]\n'
                '    Total power:  T = Σ_f P_f\n'
                '    if T>0: STFT_FC = Σ_f freqs·P_f / T  [频率重心, Hz]'
            ),
            formula_detail=(
                'STFT(az) → spectra_of dimensions [F×T]\n'
                'P(f) = Σ_j spectra[f,j] for all time indices j\n'
                'fc = Σ_f (freq[f] × P(f)) / Σ_f P(f)  [Hz: 功率加权平均主导频率]\n'
                'Human-sensitive range: 2-8 Hz (internal organ resonance)'
            ),
            calculation_logic='时频谱功率加权平均频率。反映该位置的"主导振动频率"。Benz 4-5Hz: 人体内脏共振区→高风险。12-20Hz: 脊柱轴向共振。>20Hz: 高频抖颤',
            single_point_description='✅ 单IMU: az→STFT→功率加权平均频率',
            two_point_description='🔶 seat_r(Wk weighted) vs sternum fc差异 辅助判断共振源位置',
            three_point_description='不适用')

        _add('STFT_KT',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU9_胸骨剑突-1 (sternum)',
            data_fields='az[点数N]@sternum',
            operator_pipeline_detail=(
                '① STFT.compute → spectrum, freqs\n'
                '② extract P(f) and fc as in STFT_FC above\n'
                '③ STFT_KT = √[ Σ_f (freq[f]-fc)² × P(f) / Σ_f P(f) ]'
            ),
            formula_detail=(
                'fc = 频率重心(from STFT_FC)\n'
                'σ² = Σ_f (f-fc)² × P_f / Σ_f P_f\n'
                'STFT_KT = √σ²  [Hz: 频率分布的"宽度/频谱扩散度"]\n'
                '   Narrow: KT<3Hz → 纯频率(共振危险)\n'
                '   Wide:   KT>10Hz → 宽带振动(浑沌)'
            ),
            calculation_logic='振动频率分布的"厚度/集中度"。低KT: 振动集中窄带→共振风险。高KT: 宽带振动→含多频率组分混乱感',
            single_point_description='✅ 从STFT结果: 频率标准差(二阶矩)',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('STFT_CE',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU9_胸骨剑突-1 (sternum)',
            data_fields='az[点数N]@sternum',
            operator_pipeline_detail=(
                '① STFT→spectrogram→P_f per freq\n'
                '② STFT_CE = max(P_f) / mean(P_f)  [无量纲, ≥1.0]'
            ),
            formula_detail=(
                'P_max = max_f {P(f)}\n'
                'P_avg = (1/F)×Σ_f P(f)  (F: #frequencies)\n'
                'STFT_CE = P_max / P_avg  [≥1.0, ≥5→强烈能量集中]\n'
                '  CE≈1: 均匀宽带\n'
                '  CE≈5: 能量集中在1个特定频率(共振)\n'
                '  CE>10: 极尖锐共振峰'
            ),
            calculation_logic='谱能量集中度 — 功率峰值/平均功率。CE越大=共振越尖锐(危险性高)。CE接近1=体系无固有频率(宽带随机振动)',
            single_point_description='✅ 峰/均比值, 从STFT频谱获取',
            two_point_description='不适用',
            three_point_description='不适用')

        # --- 瞬态冲击 ---

        _add('HIC15',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可 (head专用)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@head',
            operator_pipeline_detail=(
                '① Vector合成: a_total_i = √(ax_i²+ay_i²+az_i²) / 9.81  (→ g units)\n'
                '② 15ms window: n₁₅ = max(1, ceil(0.015·sr))\n'
                '    ☑ sr<200Hz: np.interp自动升采样至≥200Hz (≥3样本/15ms)\n'
                '    滑动窗口 i = 0..(N-n₁₅):\n'
                '    - segment = a_total[i:i+n₁₅], a_avg = mean(segment)\n'
                '    - dt_window = t(i+n₁₅-1)-t(i) ≈ 0.015s\n'
                '    - hic_candidate = dt_window × (a_avg)^(2.5)\n'
                '③ HIC15 = maxᵢ(hic_candidate_i)  (SAE J211, FMVSS 208)'
            ),
            formula_detail=(
                'aᵢ(g) = (1/9.81)×√(axᵢ²+ayᵢ²+azᵢ²)  for i=0..N-1\n'
                'n₁₅ = ⌈0.015·sr⌉, dt=1/sr (sr<200→自动升采样至200)\n'
                'for idx=0..N-n₁₅:\n'
                '   ā(input_window idx..idx+n15-1)\n'
                '   HIC_candidate(idx) = (t_n15-t_0) × ā^(2.5)\n'
                'HIC15 = argmax candidate(HIC_candidate)\n'
                'Limits (FMVSS 208): ≤700, >1000 fatal risk\n'
                '⚠️ 仅在头部眉心IMU1位置有意义,其他位置计算无物理损伤意义'
            ),
            calculation_logic='SAE J211 / FMVSS 208 头部损伤准则。15ms时间窗口内合成加速度的2.5次方增幅 — 损伤概率: HIC15∞, 全时域取max。紧急制动/碰撞/过颠簸事件出现高强度HIC15',
            single_point_description='✅ 单IMU(head): 三轴合成g + 15ms滑动窗max[dt×avg²⁵]',
            two_point_description='不适用 (仅在head有意义)',
            three_point_description='不适用')

        _add('ACC_H_PEAK',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可 (head专用)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@head',
            operator_pipeline_detail=(
                '① VectorOperator.synthesize(ax, ay, az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
                '② ACC_H_PEAK = max_i(|a_total_i|) — 合加速度绝对值的全程峰值 (g单位)'
            ),
            formula_detail='head_accel_i(g) = √(ax_i²+ay_i²+az_i²)\nACC_H_PEAK = max_i{head_accel_i}  [g]\nSAE J211: >20g extreme, >10g moderate, >5g low\n⚠️ 仅在头部眉心IMU1位置有意义',
            calculation_logic='头部承受的最大合加速度(peak of resultant) — SAE J211标准',
            single_point_description='✅ 单IMU(head): 三轴合成→max|output|',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('JERK_H',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可 (head专用)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='az[点数N]@head',
            operator_pipeline_detail=(
                '① np.diff(az) × sr: 一阶前向差分×采样率 = da/dt  [g/s]\n'
                '② JERK_H = max_i(|jerk_i|×1.0)'
            ),
            formula_detail='For i=0..N-2:\n   da_i = (az_{i+1}-az_i) · sr\njerk_i = |da_i|  [g/s: 加速度变化率=急动度]\nJERK_H = max_i(jerk_i)  [单位: g/s]\nHigh-jerk = "sharp impact" → 冲击锋利',
            calculation_logic='头部加速度变化率(急动度/jerk), 反映冲击的"锋利程度" — 高Jerk值指示硬撞击/突发冲击事件',
            single_point_description='✅ 单IMU Z轴差分: jerk←np.diff(az)×sr→max abs',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('SRS_MRS',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='az[点数N]@head(时域数组)',
            operator_pipeline_detail=(
                '① SRS Operator (MIL-STD-810H Method 516.8 Smallwood Recursion):\n'
                '    - Q=10 → ζ=1/(2Q)=0.05\n'
                '    - f_group = 60 SDOF, 0.5-100Hz logspace\n'
                '    - For each f: damping = 0.05, Smallwood递推{a₀,a₁,b₁,b₂}\n'
                '        SDOF=Tₙ,Q=10→abs(response peak) for this freq→svalues[f]\n'
                '② SRS_MRS = max(svalues across full freq group)  [单位: g]'
            ),
            formula_detail=(
                'For each SDOF system π (0.5Hz<π<100Hz):\n'
                '   ωn=2πF₀; Δt=1/sr; ζ=0.05; compute constants:\n'
                '     E = e^(-ζωnΔt); K = ωnΔtE/√(1-ζ²)\n'
                '     C = E·cos(ωnΔt√(1-ζ²)); S=E·sin(ωnΔt√1-ζ²)\n'
                '     b₁=2C, b₂=-E², a₀=1-K·S, a₁=K·S-E·[S/(ωdΔt)+C]\n'
                '   For all j=2..N-1:\n'
                '     resp[j]=b₁·resp[j-1]+b₂·resp[j-2]+a₀·az[j]+a₁·az[j-1]\n'
                '   svalue(π) = max_j(|resp_j|)\n'
                'SRS_MRS = max_π svalues_all(π)'
            ),
            calculation_logic='MIL-STD-810H 冲击响应谱分析 — 最大响应谱(加速度)。在0.5-100Hz频率范围内,定义60个SDOF系统。Q=10系统 Smallwood高效递推→SRS(f)的包络→SRS_MRS=包络峰值',
            single_point_description='✅ 单IMU Z轴→SRS Smallwood recursion(60 SDOF从0.5→100Hz)',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('SRS_Q',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可 (固定参数)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='az[点数N]@head → SRS分析固定参数',
            operator_pipeline_detail=(
                '① SRS类定义时固定 Q = 10.0 (MIL-STD-810H标准)\n'
                '② SRS_Q = 10.0'
            ),
            formula_detail='Q = 10.0 (固定值)\nζ = 1/(2Q) = 0.05 (5% critical damping)\n用于 Shock Response Spectrum analysis\n属计算参数,非直接测量指标',
            calculation_logic='品质因数(属MIL-STD-810H标准编制参数), 非直接测量指标',
            single_point_description='✅ 计算系统的默认参数,非传感器映射,恒等Q=10',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('SRS_PV',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='az[点数N]@head → SRS+derivation',
            operator_pipeline_detail=(
                '① SRS compute获取: svalues, frequencies[]  → MRS, peak_freq index\n'
                '② PV = MRS / (2π·peak_freq)  (in m/s)'
            ),
            formula_detail='MRS = maxᵢ svaluesᵢ\npeak_f = frequencies[argmax svalues]\nSRS_PV = MRS / (2π·peak_f + 1e-12)  [m/s]\nPseudo-velocity = 从SRS频率 & MRS推算的结构特定速度',
            calculation_logic='SRS峰值频率所对应的伪速度(位移率)。MIL-STD-810H冲击分析中,从SRS输出MRS&peakF→推算伪速度 — 表示结构需吸收的冲击能量需求',
            single_point_description='✅ 从SRS峰值加速度x频率→伪速度派生, 单IMU即可',
            two_point_description='不适用',
            three_point_description='不适用')

        _add('SRS_ATT',
            category='transient', location_dependency='single_point',
            location_dependency_label='单点即可 (固定参数)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='az[点数N]@head → SRS固定参数',
            operator_pipeline_detail=(
                '① SRS衰减 τ = 1/Q = 0.1s (from the same Q system)\n'
                '② SRS_ATT = 1/Q = 0.1'
            ),
            formula_detail='τ = 1/Q = 0.1 (秒)  [system impulse decay time]\n— SDOF振子在初始激励后自由振动,持续约0.1s参数\n属标准参数, 非实测值',
            calculation_logic='SRS冲击响应衰减时长(固定值1/Q = 0.1s), 属标准编制参数',
            single_point_description='✅ 固定计算参数, 非测量指标, τ = 0.1s',
            two_point_description='不适用',
            three_point_description='不适用')

        # --- 通用基础 ---

        _add('ACC_RMS',
            category='general', location_dependency='single_point',
            location_dependency_label='单点即可 (通用)',
            primary_imu='全部IMU通道通用',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
                '② RMS: ACC_RMS = √[ (1/N)×Σᵢ a_total_i² ]'
            ),
            formula_detail='a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\nACC_RMS = √( Σᵢ₌₀ᴺ⁻¹ a_total_i² / N )  [g]\n物理意义: 该位置的总体振动能量水平\nexcellent<0.3, good<0.6, fair<1.0',
            calculation_logic='ISO 2631-1 基础时域指标。三轴合成加速度均方根 → 反映指定位置的总体振动能量。acc_rms_{pos}对比构成 全身→臀部→头部 的振动能量传递梯度',
            single_point_description='✅ 单IMU: 三轴合成 → RMS, 适用于所有位置',
            two_point_description='🔶 seat_r vs head ACC_RMS 比值 反映 座椅对总振动能量的隔振率',
            three_point_description='🔶 head→torso→seat_r ACC_RMS梯度 揭示振动能量沿脊柱的衰减路径')

        _add('ACC_PEAK',
            category='general', location_dependency='single_point',
            location_dependency_label='单点即可 (通用)',
            primary_imu='全部IMU通道通用',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@指定位置',
            operator_pipeline_detail=(
                '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
                '② Peak: ACC_PEAK = max(a_total_i)'
            ),
            formula_detail='a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\nACC_PEAK = max( a_total_i )  [g]\n物理意义: 该位置在事件窗口内的瞬时最大冲击\nexcellent<1.0, good<2.0, fair<4.0',
            calculation_logic='ISO 2631-1 / BS 6841 瞬态峰值检测。三轴合成瞬时加速度最大值 → 反映该位置的冲击强度。peak_{pos}对比构成全身→臀部→头部 的冲击传递画像',
            single_point_description='✅ 单IMU: 三轴合成 → max, 适用于所有位置',
            two_point_description='🔶 head vs seat_r PEAK衰减 = 座椅对冲击峰值的隔振效果',
            three_point_description='🔶 head→torso→seat_r 峰值梯度 揭示冲击沿脊柱衰减的传递路径')

        # --- 位移与衰减(仅在 indicator_metadata_engine.py 中定义) ---

        _add('DISP_HR',
            category='dynamic', location_dependency='single_point',
            location_dependency_label='单点即可 (head专用)',
            primary_imu='IMU1_头部眉心-1 (head)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@head',
            operator_pipeline_detail=(
                '① CFC600滤波: 4阶Butterworth低通, fc=1000Hz\n'
                '② OP-INT2二重积分: a→v→d, 每次积分后0.5Hz高通去漂移\n'
                '③ OP-VECSYN三维合成: D_3D = √(Dx²+Dy²+Dz²)\n'
                '④ OP-MAX峰值: DISP_HR = max(D_3D(t))'
            ),
            formula_detail=(
                'D(t) = ∬a_CFC600(t) dt² → 高通0.5Hz → mm单位(×1000)\n'
                'DISP_HR = max_t √(Dx²(t) + Dy²(t) + Dz²(t))\n'
                'V4.06参考值: 传统座椅 182.5±45.6 mm'
            ),
            calculation_logic='头部三维合成位移峰值 — 反映紧急制动时头部向前冲的幅度。魔椅vs传统对比: 评价座椅头部约束能力。ISO 2631-5/VDI 2057-1 人体振动位移评估',
            single_point_description='✅ 单IMU(head): 三轴CFC滤波→二重积分→三维合成→峰值',
            two_point_description='不适用 (仅在head有意义)',
            three_point_description='不适用')

        _add('ATTEN_H',
            category='isolation', location_dependency='two_sets',
            location_dependency_label='需要实验+对照两组数据',
            required_locations=['head'],
            primary_imu='IMU1~2(头部, 实验/对照)',
            data_fields='DISP_HR(实验组) + DISP_HR(对照组)',
            operator_pipeline_detail=(
                '① 分别计算实验组和对照组的 DISP_HR\n'
                '② OP-ATTEN: η = (DISP_HR_ctrl - DISP_HR_exp) / DISP_HR_ctrl × 100%\n'
                '   正值表示魔椅优于传统(位移更小)'
            ),
            formula_detail=(
                'η_H = (D_HR,ctrl - D_HR,exp) / D_HR,ctrl × 100%\n'
                'D_HR,ctrl: 传统座椅头部位移(mm)\n'
                'D_HR,exp: GQY魔椅头部位移(mm)\n'
                'V4.06参考值: 29.7±2.6%'
            ),
            calculation_logic='头部衰减效率 — 魔椅相对于传统座椅的头部位移改善百分比。η>20%: 有效改善; η>35%: 显著改善。V4.06手册附录B衰减效率定义',
            single_point_description='❌ 需要实验+对照两组数据',
            two_point_description='✅ 实验组DISP_HR vs 对照组DISP_HR → 衰减百分比')

        _add('S_D',
            category='biomechanics', location_dependency='single_point',
            location_dependency_label='单点即可 (座垫)',
            primary_imu='IMU5_座垫R点-1 (seat_r)',
            data_fields='ax[点数N]+ay[点数N]+az[点数N]@seat_r',
            operator_pipeline_detail=(
                '① 靠背角度旋转矩阵 (θ=23°默认) → 人体坐姿坐标系变换\n'
                '② 体重修正: ω_n = 2π×9.85×√(75/w), ζ = 0.23×√(w/75)\n'
                '③ 水平方向线性滤波: X/Y轴二阶低通 H(s) = s/(s²+31.4s+400)\n'
                '④ 垂向非线性SDOF ODE: z¨+2ζω_nż+ω_n²z = a_z(t)\n'
                '⑤ 峰值提取: 提取各次冲击事件的腰椎响应峰值D_xk, D_yk, D_zk\n'
                '⑥ 六次方剂量融合: D_k⁶ = (0.018·D_xk)⁶+(0.015·D_yk)⁶+(0.003·D_zk)⁶\n'
                '⑦ S_d = (Σ D_k⁶)^(1/6)'
            ),
            formula_detail=(
                'S_d = [ Σ (0.018 D_xk)⁶ + (0.015 D_yk)⁶ + (0.003 D_zk)⁶ ]^(1/6)\n'
                'cx=0.018: X轴方向加权系数\n'
                'cy=0.015: Y轴方向加权系数\n'
                'cz=0.003: Z轴方向加权系数\n'
                'D_k: 第k次冲击事件腰椎响应峰值(m/s²)\n'
                'S_d<0.5 MPa→绿色(低风险); S_d<0.3→优秀'
            ),
            calculation_logic='ISO 2631-5 腰椎每日等效压缩应力。人类腰椎对长期振动暴露的累积损伤评估指标。基于人体坐姿生物力学模型(75kg, 靠背23°)的六次方剂量融合。S_d<0.5 MPa=低风险, S_d<0.8 MPa=中风险, S_d≥0.8 MPa=高风险',
            single_point_description='✅ 单IMU(座垫): 三轴加速度→人体模型响应→脊柱压缩应力',
            two_point_description='不适用',
            three_point_description='不适用')

    # ──────────────────────────────────────────────
    # 评测模块
    # ──────────────────────────────────────────────

    def _register_evaluation_modules(self):
        self.evaluation_modules = {
            'transient_shock': EvaluationModuleMeta(
                module_code='transient_shock',
                display_name_cn='瞬态冲击评测',
                display_name_en='Transient Shock Evaluation',
                applicable_indicators=['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT'],
                scenario_description='紧急制动/碰撞/过颠簸等瞬态事件',
                evaluation_method='SAE J211 / MIL-STD-810H 冲击响应谱分析'
            ),
            'steady_comfort': EvaluationModuleMeta(
                module_code='steady_comfort',
                display_name_cn='稳态舒适度评测',
                display_name_en='Steady-State Comfort Evaluation',
                applicable_indicators=['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'OVTV', 'R_FACTOR'],
                scenario_description='稳态工况乘坐舒适性',
                evaluation_method='ISO 2631-1 频率加权RMS/VDV'
            ),
            'dynamic_response': EvaluationModuleMeta(
                module_code='dynamic_response',
                display_name_cn='动态响应评测',
                display_name_en='Dynamic Response Evaluation',
                applicable_indicators=['VDV_Z', 'TR_Z', 'DISP_TR', 'DISP_HR', 'ATTEN_H'],
                scenario_description='动态振动位移传递和衰减',
                evaluation_method='ISO 2631-5 / VDI 2057-1'
            ),
            'fatigue_durability': EvaluationModuleMeta(
                module_code='fatigue_durability',
                display_name_cn='疲劳耐久评测',
                display_name_en='Fatigue Durability Evaluation',
                applicable_indicators=['RFC_CC', 'FDS_D', 'FDS_R'],
                scenario_description='长期振动暴露座椅结构疲劳',
                evaluation_method='ASTM E1049 雨流计数 + BS 7608 Miner累积损伤'
            ),
            'frequency_analysis': EvaluationModuleMeta(
                module_code='frequency_analysis',
                display_name_cn='频域特性评测',
                display_name_en='Frequency Domain Evaluation',
                applicable_indicators=['STFT_FC', 'STFT_KT', 'STFT_CE'],
                scenario_description='振动频谱分析和共振识别',
                evaluation_method='STFT 时频谱功率分析'
            ),
            'biomechanics': EvaluationModuleMeta(
                module_code='biomechanics',
                display_name_cn='生物力学评测',
                display_name_en='Biomechanics Evaluation',
                applicable_indicators=['S_D'],
                scenario_description='长期振动暴露脊柱健康风险评估',
                evaluation_method='ISO 2631-5 腰椎等效压缩应力'
            ),
        }

    # ──────────────────────────────────────────────
    # 标准引用
    # ──────────────────────────────────────────────

    def _register_standard_references(self):
        self.standard_references = {
            'ISO_2631_1': {
                'name': 'ISO 2631-1:1997/Amd 1:2010',
                'title': '机械振动与冲击 — 人体暴露于全身振动的评估 — 第1部分：一般要求',
                'scope': '定义频率加权曲线(Wk/Wd)、基本评价方法(RMS/VDV)、健康指南区间',
                'indicators': ['AW_Z', 'AW_XY', 'OVTV', 'R_FACTOR', 'ACC_RMS', 'ACC_PEAK'],
                'url': 'https://www.iso.org/standard/45604.html'
            },
            'ISO_2631_5': {
                'name': 'ISO 2631-5:2018',
                'title': '机械振动与冲击 — 人体暴露于全身振动的评估 — 第5部分：包含多次冲击的振动评价',
                'scope': '多次冲击的腰椎每日等效压缩应力S_d评估方法',
                'indicators': ['S_D', 'DISP_HR', 'DISP_TR'],
                'url': 'https://www.iso.org/standard/69109.html'
            },
            'BS_6841': {
                'name': 'BS 6841:1987',
                'title': '人体暴露于机械振动与反复冲击的测量与评估指南',
                'scope': 'VDV振动剂量值定义、SEAT传递率计算、健康警戒区间',
                'indicators': ['VDV_Z', 'SEAT_Z', 'SEAT_XY', 'TR_Z'],
            },
            'BS_7608': {
                'name': 'BS 7608:2014+A1:2015',
                'title': '钢结构疲劳设计与评定指南',
                'scope': 'Miner累积损伤和S-N曲线的疲劳寿命评估框架',
                'indicators': ['FDS_D', 'FDS_R', 'RFC_CC'],
            },
            'ASTM_E1049': {
                'name': 'ASTM E1049-85(2017)',
                'title': '疲劳分析中雨流循环计数的标准实践',
                'scope': '四峰谷雨流计数法，循环提取和振幅-均值配对',
                'indicators': ['RFC_CC', 'FDS_D'],
            },
            'SAE_J211': {
                'name': 'SAE J211-1:2014',
                'title': '碰撞测试设备 — 第1部分：电子仪表',
                'scope': 'CFC滤波等级定义(CFC600/CFC1000)、HIC计算通道要求',
                'indicators': ['HIC15', 'ACC_H_PEAK', 'JERK_H'],
            },
            'FMVSS_208': {
                'name': 'FMVSS 208',
                'title': '乘员碰撞保护标准',
                'scope': 'HIC15阈值定义(HIC≤700合格, >1000高风险)',
                'indicators': ['HIC15'],
            },
            'ECE_R94': {
                'name': 'ECE R94',
                'title': '正面碰撞乘员保护',
                'scope': '正面碰撞HIC保护要求(HIC<1000)',
                'indicators': ['HIC15'],
            },
            'MIL_STD_810H': {
                'name': 'MIL-STD-810H Method 516.8',
                'title': '环境工程考虑与实验室测试 — 冲击',
                'scope': '冲击响应谱(SRS)Smallwood递推算法、Q=10系统定义',
                'indicators': ['SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT'],
            },
            'VDI_2057': {
                'name': 'VDI 2057-1:2017',
                'title': '人体暴露于机械振动的评估 — 全身振动',
                'scope': '德国工程师协会标准，频率分析方法和人体模型',
                'indicators': ['STFT_FC', 'STFT_KT', 'STFT_CE', 'DISP_HR'],
            },
            'ISO_6487': {
                'name': 'ISO 6487:2015',
                'title': '道路车辆 — 碰撞试验中测量技术 — 仪器',
                'scope': 'CFC等级定义和HIC计算的数据处理方法',
                'indicators': ['HIC15'],
            },
            'PATAC': {
                'name': '泛亚PATAC AEB座椅评测内部规程',
                'title': 'AEB座椅舒适性及安全性评测内部规程(内部参考)',
                'scope': 'AEB刹停工况下座椅人体响应评测的内部标准',
                'indicators': ['HIC15', 'ACC_H_PEAK', 'DISP_HR', 'ATTEN_H'],
            },
        }

    # ──────────────────────────────────────────────
    # 对比维度
    # ──────────────────────────────────────────────

    def _register_comparison_dimensions(self):
        self.comparison_dimensions = [
            {
                'dimension': '魔椅vs传统',
                'code': 'gqy_vs_traditional',
                'description': 'GQY魔椅与同级别传统座椅的全面对比',
                'include_indicators': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'OVTV', 'R_FACTOR',
                                       'VDV_Z', 'TR_Z', 'DISP_TR', 'DISP_HR', 'ATTEN_H',
                                       'RFC_CC', 'FDS_D', 'FDS_R',
                                       'STFT_FC', 'STFT_KT', 'STFT_CE',
                                       'HIC15', 'ACC_H_PEAK', 'JERK_H',
                                       'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT',
                                       'ACC_RMS', 'ACC_PEAK', 'S_D'],
                'default_visible': True,
            },
            {
                'dimension': 'AEB刹停对比',
                'code': 'aeb_braking',
                'description': '不同AEB刹停工况魔椅vs传统人体响应对比',
                'include_indicators': ['HIC15', 'DISP_HR', 'ATTEN_H',
                                       'JERK_H', 'ACC_H_PEAK',
                                       'SRS_MRS', 'SRS_PV'],
                'default_visible': False,
            },
        ]

    # ──────────────────────────────────────────────
    # 诊断阈值
    # ──────────────────────────────────────────────

    def _register_diagnosis_thresholds(self):
        self.diagnosis_thresholds = {
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
            'TR_Z':    {'pass': 0.50, 'warn': 1.00, 'desc': 'Z向传递率', 'loc': 'seat_r'},
            'DISP_TR': {'pass': 15.0, 'warn': 30.0, 'desc': '躯干位移[mm]', 'loc': 'torso'},
            'DISP_HR': {'pass': 150.0,'warn': 250.0,'desc': '头部位移[mm]', 'loc': 'head'},
            'ATTEN_H': {'pass': 20.0, 'warn': 10.0, 'desc': '头部衰减效率[%]', 'loc': 'head'},
            'STFT_FC': {'pass': 8.0,  'warn': 15.0, 'desc': '频率重心[Hz]', 'loc': 'sternum'},
            'STFT_KT': {'pass': 5.0,  'warn': 12.0, 'desc': '频率扩散度[Hz]', 'loc': 'sternum'},
            'STFT_CE': {'pass': 5.0,  'warn': 10.0, 'desc': '能量集中度', 'loc': 'sternum'},
            'ACC_RMS': {'pass': 0.30, 'warn': 0.60, 'desc': '加速度RMS[g]', 'loc': 'seat_r'},
            'ACC_PEAK':{'pass': 1.0,  'warn': 2.0,  'desc': '加速度峰值[g]', 'loc': 'seat_r'},
            'S_D':     {'pass': 0.50, 'warn': 0.80, 'desc': '腰椎压缩应力[MPa]', 'loc': 'seat_r'},
        }
        self._register_metric_thresholds_4level()

    def _register_metric_thresholds_4level(self):
        self.metric_thresholds_4level = {
            'HIC15':    {'excellent': 100,   'good': 300,  'fair': 700,  'poor': float('inf')},
            'ACC_H_PEAK': {'excellent': 5,    'good': 10,   'fair': 20,   'poor': float('inf')},
            'JERK_H':   {'excellent': 5,    'good': 15,   'fair': 30,   'poor': float('inf')},
            'SRS_MRS':  {'excellent': 5,    'good': 15,   'fair': 30,   'poor': float('inf')},
            'SRS_Q':    {'excellent': 10,   'good': 30,   'fair': 50,   'poor': float('inf')},
            'SRS_PV':   {'excellent': 5,    'good': 15,   'fair': 30,   'poor': float('inf')},
            'SRS_ATT':  {'excellent': 35,   'good': 20,   'fair': 10,   'poor': 0},
            'SEAT_Z':   {'excellent': 0.3,  'good': 0.6,  'fair': 1.0,  'poor': float('inf')},
            'SEAT_XY':  {'excellent': 0.3,  'good': 0.6,  'fair': 1.0,  'poor': float('inf')},
            'AW_Z':     {'excellent': 0.3,  'good': 0.6,  'fair': 1.0,  'poor': float('inf')},
            'AW_XY':    {'excellent': 0.3,  'good': 0.6,  'fair': 1.0,  'poor': float('inf')},
            'OVTV':     {'excellent': 0.5,  'good': 1.0,  'fair': 1.7,  'poor': float('inf')},
            'R_FACTOR': {'excellent': 0.5,  'good': 1.0,  'fair': 2.0,  'poor': float('inf')},
            'VDV_Z':    {'excellent': 0.5,  'good': 1.5,  'fair': 3.0,  'poor': float('inf')},
            'TR_Z':     {'excellent': 0.5,  'good': 0.8,  'fair': 1.2,  'poor': float('inf')},
            'DISP_HR':  {'excellent': 100,  'good': 200,  'fair': 400,  'poor': float('inf')},
            'DISP_TR':  {'excellent': 100,  'good': 200,  'fair': 400,  'poor': float('inf')},
            'ATTEN_H':  {'excellent': 35,   'good': 20,   'fair': 10,   'poor': 0},
            'RFC_CC':   {'excellent': 30,   'good': 50,   'fair': 100,  'poor': float('inf')},
            'FDS_D':    {'excellent': 0.05, 'good': 0.2,  'fair': 0.5,  'poor': float('inf')},
            'FDS_R':    {'excellent': 0.8,  'good': 0.5,  'fair': 0.2,  'poor': 0.0},
            'STFT_FC':  {'excellent': 5,    'good': 10,   'fair': 20,   'poor': float('inf')},
            'STFT_KT':  {'excellent': 3,    'good': 8,    'fair': 15,   'poor': float('inf')},
            'STFT_CE':  {'excellent': 3,    'good': 8,    'fair': 15,   'poor': float('inf')},
            'S_D':      {'excellent': 0.3,  'good': 0.5,  'fair': 0.8,  'poor': float('inf')},
            'ACC_RMS':  {'excellent': 0.3,  'good': 0.6,  'fair': 1.0,  'poor': float('inf')},
            'ACC_PEAK': {'excellent': 1.0,  'good': 2.0,  'fair': 4.0,  'poor': float('inf')},
        }

    # ──────────────────────────────────────────────
    # 数据源注册
    # ──────────────────────────────────────────────

    def _register_data_sources(self):
        sources = [
            DataSourceMeta(
                source_code='CAN_CH1_HEAD',
                display_name_cn='CAN通道1 — 头部眉心IMU',
                display_name_en='CAN Ch1 Head IMU',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch1',
                can_ids=['0x1FFF0051', '0x1FFF0052'],
                imu_labels={
                    '0x1FFF0051': 'IMU1_头部眉心-1(实验组)',
                    '0x1FFF0052': 'IMU2_头部眉心-2(对照组)',
                },
                sampling_rate_hz=1000.0,
                sensor_model='ASM3301HH',
                sensor_ranges={'gyro': (-500, 500), 'accel': (-16, 16)},
                raw_fields=['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps'],
                description='头部眉心位置，10路IMU中最重要的冲击评估通道',
            ),
            DataSourceMeta(
                source_code='CAN_CH2_TORSO',
                display_name_cn='CAN通道2 — 躯干T8 IMU',
                display_name_en='CAN Ch2 Torso T8 IMU',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch2',
                can_ids=['0x1FFF0051', '0x1FFF0052'],
                imu_labels={
                    '0x1FFF0051': 'IMU3_躯干T8-1(实验组)',
                    '0x1FFF0052': 'IMU4_躯干T8-2(对照组)',
                },
                sampling_rate_hz=1000.0,
                sensor_model='ASM3301HH',
                sensor_ranges={'gyro': (-500, 500), 'accel': (-16, 16)},
                raw_fields=['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps'],
                description='躯干T8位置，已标记为废弃(deprecated)',
            ),
            DataSourceMeta(
                source_code='CAN_CH3_SEATR',
                display_name_cn='CAN通道3 — 座垫R点IMU',
                display_name_en='CAN Ch3 Seat R-point IMU',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch3',
                can_ids=['0x1FFF0051', '0x1FFF0052'],
                imu_labels={
                    '0x1FFF0051': 'IMU5_座垫R点-1(实验组)',
                    '0x1FFF0052': 'IMU6_座垫R点-2(对照组)',
                },
                sampling_rate_hz=1000.0,
                sensor_model='ASM3301HH',
                sensor_ranges={'gyro': (-500, 500), 'accel': (-16, 16)},
                raw_fields=['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps'],
                description='座垫R点位置，稳态舒适度评估的核心通道(SEAT_Z/VDV_Z等)',
            ),
            DataSourceMeta(
                source_code='CAN_CH4_BOTTOM',
                display_name_cn='CAN通道4 — 座椅底部IMU',
                display_name_en='CAN Ch4 Seat Bottom IMU',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch4',
                can_ids=['0x1FFF0053', '0x1FFF0054'],
                imu_labels={
                    '0x1FFF0053': 'IMU7_座椅底部-1(实验组)',
                    '0x1FFF0054': 'IMU8_座椅底部-2(对照组)',
                },
                sampling_rate_hz=1000.0,
                sensor_model='ASM3301HH',
                sensor_ranges={'gyro': (-500, 500), 'accel': (-16, 16)},
                raw_fields=['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps'],
                description='座椅底部基准位置，SEAT传递率计算的对照基准(drive_behavior主IMU)',
            ),
            DataSourceMeta(
                source_code='CAN_CH5_STERNUM',
                display_name_cn='CAN通道5 — 胸骨剑突IMU(备选)',
                display_name_en='CAN Ch5 Sternum IMU',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch5',
                can_ids=['0x1FFF0053', '0x1FFF0054'],
                imu_labels={
                    '0x1FFF0053': 'IMU9_胸骨剑突-1(实验组)',
                    '0x1FFF0054': 'IMU10_胸骨剑突-2(对照组)',
                },
                sampling_rate_hz=1000.0,
                sensor_model='ASM3301HH',
                sensor_ranges={'gyro': (-500, 500), 'accel': (-16, 16)},
                raw_fields=['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps'],
                description='胸骨剑突备选位置，时频分析(STFT)的主要通道',
            ),
            DataSourceMeta(
                source_code='CAN_CH6_VEHICLE',
                display_name_cn='CAN通道6 — 车机信号',
                display_name_en='CAN Ch6 Vehicle Signals',
                source_type=DataSourceType.CAN_FILE,
                protocol='CAN 2.0B',
                physical_channel='ch6',
                can_ids=['0x100', '0x101', '0x102'],
                sampling_rate_hz=10.0,
                sensor_model='CAN Gateway',
                raw_fields=[],
                vehicle_signal_fields=['VEH_SPEED', 'WHEEL_ANGLE', 'BRAKE_PRESSURE', 'EMERGENCY_BRAKE'],
                description='车机CAN总线信号: 0x100车速+倒挡, 0x101方向盘转角, 0x102紧急制动+制动压力',
            ),
        ]
        for s in sources:
            self.data_sources[s.source_code] = s

    # ──────────────────────────────────────────────
    # 驾驶行为状态注册
    # ──────────────────────────────────────────────

    def _register_driving_states(self):
        states = [
            DrivingStateMeta('straight_cruise', '匀速直行', 'Straight Cruise',
                             RiskCategory.NORMAL, '低', '#27AE60', '直线稳定行驶'),
            DrivingStateMeta('normal_acceleration', '正常加速', 'Normal Accel',
                             RiskCategory.NORMAL, '低', '#27AE60', '温和油门加速'),
            DrivingStateMeta('normal_deceleration', '正常减速', 'Normal Decel',
                             RiskCategory.NORMAL, '低', '#27AE60', '温和制动减速'),
            DrivingStateMeta('constant_speed', '恒速行驶', 'Constant Speed',
                             RiskCategory.NORMAL, '低', '#27AE60', '速度保持稳定'),
            DrivingStateMeta('stopped', '停车', 'Stopped',
                             RiskCategory.NORMAL, '低', '#95A5A6', '车辆静止'),
            DrivingStateMeta('parking', '驻车', 'Parking',
                             RiskCategory.NORMAL, '低', '#95A5A6', '停车状态'),
            DrivingStateMeta('lane_keep', '车道保持', 'Lane Keeping',
                             RiskCategory.NORMAL, '低', '#27AE60', '车道保持正常'),
            DrivingStateMeta('turning_left', '左转', 'Turning Left',
                             RiskCategory.WARNING, '中', '#f39c12', '方向盘左打'),
            DrivingStateMeta('turning_right', '右转', 'Turning Right',
                             RiskCategory.WARNING, '中', '#f39c12', '方向盘右打'),
            DrivingStateMeta('tight_turn', '小半径转弯', 'Tight Turn',
                             RiskCategory.WARNING, '中', '#4A90D9', '小半径弯道'),
            DrivingStateMeta('wide_turn', '大半径转弯', 'Wide Turn',
                             RiskCategory.WARNING, '中', '#4A90D9', '大半径弯道'),
            DrivingStateMeta('lane_change', '变道', 'Lane Change',
                             RiskCategory.WARNING, '中', '#f39c12', '车道变更'),
            DrivingStateMeta('cornering_acceleration', '弯道加速', 'Cornering Accel',
                             RiskCategory.WARNING, '中', '#f39c12', '弯道中加速'),
            DrivingStateMeta('cornering_deceleration', '弯道减速', 'Cornering Decel',
                             RiskCategory.WARNING, '中', '#f39c12', '弯道中减速'),
            DrivingStateMeta('u_turn', 'U型转弯', 'U-Turn',
                             RiskCategory.DANGER, '极高', '#e74c3c', 'U型调头'),
            DrivingStateMeta('aggressive_acceleration', '激进加速', 'Aggressive Accel',
                             RiskCategory.WARNING, '高', '#e67e22', '突然猛踩油门'),
            DrivingStateMeta('aggressive_deceleration', '激进减速', 'Aggressive Decel',
                             RiskCategory.WARNING, '高', '#e67e22', '突然猛踩刹车'),
            DrivingStateMeta('emergency_braking', '急刹车', 'Emergency Braking',
                             RiskCategory.DANGER, '极高', '#e74c3c', '紧急制动事件'),
            DrivingStateMeta('weaving', '蛇形驾驶', 'Weaving',
                             RiskCategory.DANGER, '极高', '#e74c3c', '连续变道/蛇形'),
            DrivingStateMeta('rapid_direction_change', '急速变向', 'Rapid Direction Change',
                             RiskCategory.DANGER, '极高', '#e74c3c', '快速转向'),
            DrivingStateMeta('severe_bump', '剧烈颠簸', 'Severe Bump',
                             RiskCategory.DANGER, '极高', '#e74c3c', '路面剧烈冲击'),
            DrivingStateMeta('skid_risk', '侧滑风险', 'Skid Risk',
                             RiskCategory.CRITICAL, '极高', '#e74c3c', '侧滑/失控风险'),
            DrivingStateMeta('rollover_risk', '侧翻风险', 'Rollover Risk',
                             RiskCategory.CRITICAL, '极高', '#e74c3c', '侧翻风险预警'),
        ]
        for s in states:
            self.driving_states[s.state_code] = s

    # ═══════════════════════════════════════════════════════════════
    # 查询方法
    # ═══════════════════════════════════════════════════════════════

    def get_indicator_meta(self, code: str) -> 'Optional[IndicatorMeta]':
        return self.indicators.get(code)

    def get_indicator_detail(self, code: str) -> 'Optional[IndicatorDetail]':
        return self.indicator_details.get(code)

    def get_indicators_by_module(self, module_code: str) -> list:
        module = self.evaluation_modules.get(module_code)
        if module:
            return module.applicable_indicators
        return []

    def get_indicators_by_dimension(self, dimension: str) -> list:
        for comp in self.comparison_dimensions:
            if comp['code'] == dimension:
                return comp['include_indicators']
        return []

    def get_threshold(self, indicator_code: str) -> dict:
        return self.diagnosis_thresholds.get(indicator_code, {})

    def get_standard_refs(self, indicator_code: str) -> list:
        refs = []
        for code, ref in self.standard_references.items():
            if indicator_code in ref.get('indicators', []):
                refs.append(ref)
        return refs

    def list_all_indicator_codes(self) -> list:
        return list(self.indicators.keys())

    def get_4level_threshold(self, indicator_code: str) -> dict:
        return self.metric_thresholds_4level.get(indicator_code, {})

    def get_4level_grade(self, indicator_code: str, value: float) -> str:
        thresholds = self.metric_thresholds_4level.get(indicator_code, {})
        if not thresholds:
            return 'unknown'
        indicator = self.indicators.get(indicator_code)
        direction = EvaluationDirection.LOWER_BETTER
        if indicator:
            direction = indicator.evaluation_direction
        if direction == EvaluationDirection.HIGHER_BETTER:
            if value >= thresholds.get('excellent', 0):
                return 'excellent'
            elif value >= thresholds.get('good', 0):
                return 'good'
            elif value >= thresholds.get('fair', 0):
                return 'fair'
            else:
                return 'poor'
        else:
            if value <= thresholds.get('excellent', float('inf')):
                return 'excellent'
            elif value <= thresholds.get('good', float('inf')):
                return 'good'
            elif value <= thresholds.get('fair', float('inf')):
                return 'fair'
            else:
                return 'poor'

    def get_vehicle_fields(self) -> Dict[str, RawFieldMeta]:
        return {k: v for k, v in self.raw_fields.items() if v.field_category == 'vehicle'}

    def get_imu_fields(self) -> Dict[str, RawFieldMeta]:
        return {k: v for k, v in self.raw_fields.items() if v.field_category == 'imu'}

    def get_data_source(self, code: str) -> 'Optional[DataSourceMeta]':
        return self.data_sources.get(code)

    def get_all_data_sources(self) -> Dict[str, 'DataSourceMeta']:
        return dict(self.data_sources)

    def get_driving_state(self, code: str) -> 'Optional[DrivingStateMeta]':
        return self.driving_states.get(code)

    def get_all_driving_states(self) -> Dict[str, 'DrivingStateMeta']:
        return dict(self.driving_states)

    def get_driving_state_cn_label(self, code: str) -> str:
        state = self.driving_states.get(code)
        return state.display_name_cn if state else code

    def generate_result_schema(self) -> str:
        lines = [
            "CREATE TABLE IF NOT EXISTS evaluation_results (",
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,",
            "    session_id TEXT NOT NULL,",
            "    event_id TEXT NOT NULL,",
            "    indicator_code TEXT NOT NULL,",
            "    location TEXT NOT NULL,",
            "    group_tag TEXT NOT NULL DEFAULT 'experimental',",
            "    value REAL,",
            "    unit TEXT,",
            "    grade TEXT,",
            "    pass_status TEXT,",
            "    raw_data TEXT,",
            "    evaluated_at REAL NOT NULL,",
            "    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_result_session ON evaluation_results(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_result_event ON evaluation_results(event_id);",
            "CREATE INDEX IF NOT EXISTS idx_result_indicator ON evaluation_results(indicator_code);",
            "CREATE TABLE IF NOT EXISTS evaluation_sessions (",
            "    session_id TEXT PRIMARY KEY,",
            "    session_name TEXT,",
            "    data_source TEXT,",
            "    total_events INTEGER DEFAULT 0,",
            "    total_indicators INTEGER DEFAULT 0,",
            "    started_at REAL,",
            "    completed_at REAL,",
            "    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))",
            ");",
        ]
        return '\n'.join(lines)

    # ═══════════════════════════════════════════════════════════════
    # 向后兼容方法 — 返回旧格式 dict，兼容现有消费者
    # ═══════════════════════════════════════════════════════════════

    def get_indicator_definitions_legacy(self) -> dict:
        """返回兼容旧版 INDICATOR_DEFINITIONS 格式的 dict"""
        result = {}
        for code, meta in self.indicators.items():
            result[code] = {
                'name': meta.display_name_cn,
                'unit': meta.unit if meta.unit != '-' else '',
                'type': self._map_dimension_to_type(meta.evaluation_dimension),
                'dimension': meta.evaluation_dimension,
                'locations': meta.applicable_locations,
                'threshold_good': meta.threshold_pass or '',
                'threshold_bad': meta.threshold_excellent or '',
                'description': meta.description or '',
                'formula': meta.formula_text or '',
                'formula_latex': meta.formula_latex or '',
                'weighting': '',
                'category': meta.evaluation_dimension,
                'is_required': True,
                'applicable_scenarios': [],
                'output_type': meta.output_type.value if hasattr(meta.output_type, 'value') else str(meta.output_type),
                'precision': meta.precision,
                'standard_refs': meta.standard_refs if hasattr(meta, 'standard_refs') else [],
            }
        return result

    @staticmethod
    def _map_dimension_to_type(dimension: str) -> str:
        mapping = {
            '瞬态-冲击': 'shock',
            '稳态-隔振': 'frequency',
            '稳态-舒适度': 'frequency',
            '动态-响应': 'frequency',
            '疲劳-损伤': 'fatigue',
            '时频-分析': 'time_frequency',
            '频域-特性': 'time_frequency',
            '生物力学': 'structure',
            '通用-基础': 'basic',
            '位移-衰减': 'structure',
        }
        for key, val in mapping.items():
            if key in dimension or dimension in key:
                return val
        return 'basic'

    def get_indicator_detail_legacy(self) -> dict:
        """返回兼容旧版 INDICATOR_DETAIL 格式的 dict"""
        result = {}
        for code, detail in self.indicator_details.items():
            result[code] = {
                'category': detail.category,
                'location_dependency': detail.location_dependency,
                'location_dependency_label': detail.location_dependency_label,
                'required_locations': detail.required_locations,
                'primary_imu': detail.primary_imu,
                'reference_imu': getattr(detail, 'reference_imu', ''),
                'data_fields': detail.data_fields,
                'operator_pipeline': detail.operator_pipeline_detail,
                'formula': detail.formula_detail,
                'calculation_logic': detail.calculation_logic,
                'single_point_description': detail.single_point_description,
                'two_point_description': detail.two_point_description,
                'three_point_description': detail.three_point_description,
            }
        return result

    def get_standard_references_legacy(self) -> dict:
        """返回兼容旧版 STANDARD_REFERENCES 格式的 dict (per-indicator key)"""
        per_indicator = {}
        for std_code, std in self.standard_references.items():
            indicators = std.get('indicators', [])
            for ind in indicators:
                if ind not in per_indicator:
                    per_indicator[ind] = {
                        'standard': std.get('name', ''),
                        'limit': std.get('scope', ''),
                        'source_url': std.get('url', ''),
                    }
        for code in self.indicators:
            if code not in per_indicator:
                per_indicator[code] = {'standard': '', 'limit': '', 'source_url': ''}
        return per_indicator

    def get_comparison_dimensions_legacy(self) -> list:
        """返回兼容旧版 COMPARISON_DIMENSIONS 格式的评测维度列表"""
        colors = {
            'transient_shock': '#E74C3C',
            'steady_comfort': '#4A90D9',
            'dynamic_response': '#27AE60',
            'fatigue_durability': '#F39C12',
            'frequency_analysis': '#9B59B6',
            'biomechanics': '#2ECC71',
        }
        result = []
        for code, module in self.evaluation_modules.items():
            result.append({
                'id': code,
                'name': module.display_name_cn,
                'description': module.scenario_description,
                'color': colors.get(code, '#4A90D9'),
                'metrics': module.applicable_indicators,
            })
        return result


_global_registry: Optional[MetadataRegistry] = None


def get_global_registry() -> MetadataRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = MetadataRegistry()
    return _global_registry


# ═══════════════════════════════════════════════════════════════
# 模块级向后兼容导出 — 可直接 import 使用
# ═══════════════════════════════════════════════════════════════

_registry = get_global_registry()

INDICATOR_DEFINITIONS = _registry.get_indicator_definitions_legacy()
DIAGNOSIS_THRESHOLDS = _registry.diagnosis_thresholds
STANDARD_REFERENCES = _registry.get_standard_references_legacy()
COMPARISON_DIMENSIONS = _registry.get_comparison_dimensions_legacy()
INDICATOR_DETAIL = _registry.get_indicator_detail_legacy()
METRIC_THRESHOLDS = _registry.metric_thresholds_4level
DATA_SOURCES = _registry.data_sources
DRIVING_STATES = _registry.driving_states
RESULT_SCHEMA = _registry.generate_result_schema()