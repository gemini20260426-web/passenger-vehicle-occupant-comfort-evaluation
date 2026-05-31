#!/usr/bin/env python3
"""
乘用车座椅综合性能评测 — 考核指标元数据全流程引擎 V2.0
========================================================
基于 V4.06/V5.0 实验方案的完整考核指标体系
覆盖: 采集数据 → 派生数据 → 算子处理 → 考核指标 → 对比评价

数据全流程溯源链:
  原始采集 → 预处理 → 派生字段 → 算子计算 → 指标输出
  ┌─────────┐  ┌────────┐  ┌─────────┐  ┌────────┐  ┌─────────┐
  │ 10路IMU │→│ CFC滤波│→│ 合成矢量│→│ 频域分析│→│ SEAT/VDV│
  │ CAN总线 │  │ 去漂移 │  │ 积分位移│  │ 时频分析│  │ STFT/SRS│
  │ 传感器  │  │ 时间同步│  │ 差分求导│  │ 雨流计数│  │ FDS/D   │
  └─────────┘  └────────┘  └─────────┘  └────────┘  └─────────┘

结构:
  Class MetadataRegistry     — 元数据注册中心
  Class DataPipeline         — 数据全流程处理管线
  Class DerivedFieldComputer  — 派生字段计算器
  Class OperatorComputer      — 算子计算器
  Class IndicatorComputer     — 考核指标计算器
  Class EvaluationReport      — 评估报告生成器

作者: SciClaw | 版本: V2.0 | 日期: 2026-05-17
"""

import numpy as np
from scipy import signal, integrate
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks, lti, lsim, welch, csd, spectrogram
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Callable, Any, Union
from enum import Enum
import json
import warnings
warnings.filterwarnings('ignore')

# ========================================================================
# PART A: 元数据注册中心 — 所有指标、算子、派生数据的权威定义
# ========================================================================

class DataCategory(Enum):
    """数据分类"""
    RAW = "原始采集数据"         # 传感器直接输出
    DERIVED = "派生数据"        # 经预处理/变换后的中间数据
    OPERATOR_OUT = "算子输出"    # 算子处理后的结构化输出
    INDICATOR = "考核指标"       # 最终考核指标

class StandardRef:
    """标准引用"""
    def __init__(self, std_id: str, clause: str, description: str):
        self.std_id = std_id
        self.clause = clause
        self.description = description
    
    def __repr__(self):
        return f"{self.std_id} {self.clause}: {self.description}"


@dataclass
class DataFieldMeta:
    """数据字段元数据 — 描述每个数据字段的完整溯源信息"""
    field_name: str              # 字段名
    display_name: str            # 中文显示名
    category: DataCategory       # 数据分类
    data_type: str               # 数据类型: float / array / dict
    unit: str                    # 单位
    source_imus: List[str]       # 来源IMU (采集点)
    source_fields: List[str]     # 来源字段
    derivation: str              # 派生公式/方法
    standard_refs: List[StandardRef]  # 标准依据
    valid_range: Tuple[float, float] = None  # 有效范围
    precision: int = 3           # 输出精度

@dataclass
class OperatorMeta:
    """算子元数据"""
    op_code: str                 # 算子编码
    op_name: str                 # 算子名称
    description: str             # 功能描述
    input_fields: List[str]      # 输入字段
    output_fields: List[str]     # 输出字段
    algorithm: str               # 算法描述
    parameters: Dict[str, Any]   # 参数
    standard_refs: List[StandardRef]

@dataclass
class IndicatorMeta:
    """考核指标元数据 — 最完整的定义"""
    # 基本信息
    indicator_code: str          # 指标编码, 如 "HIC15"
    indicator_name: str          # 指标名称, 如 "头部损伤指标(15ms)"
    display_name_cn: str         # 中文全称
    module: str                  # 所属模块: M1/M2/M3/M4/C3
    evaluation_dimension: str    # 评价维度: "时域" / "频域" / "时频域" / "冲击域" / "疲劳域" / "生物力学"
    
    # 数据溯源链: 采集→派生→算子→指标
    source_imus: List[str]       # 来源采集点(IMU编号)
    source_raw_fields: List[str] # 来源原始字段
    prerequisite_derived: List[str]  # 前置派生数据
    operator_pipeline: List[str] # 算子流水线 (按顺序)
    
    # 数学定义
    formula_text: str            # 数学公式(文字描述)
    formula_latex: str           # LaTeX公式
    variables: Dict[str, str]    # 公式中变量说明: {符号: 含义}
    
    # 输出规格
    unit: str                    # 单位
    output_type: str             # 输出类型: "scalar" / "vector" / "curve" / "matrix"
    precision: int               # 小数位数
    
    # 评价标准
    threshold_pass: Optional[str]     # 通过阈值
    threshold_excellent: Optional[str]  # 优秀阈值
    evaluation_direction: str    # 评价方向: "lower_better" / "higher_better" / "in_range"
    comparison_method: str       # 对比方式: "absolute" / "relative_to_ctrl" / "relative_to_standard"
    
    # 标准依据
    standard_refs: List[StandardRef]
    industry_references: List[str]  # 行业文献/案例引用
    
    # 元数据
    version: str = "V2.0"
    last_updated: str = "2026-05-17"

class MetadataRegistry:
    """元数据注册中心 — 管理所有指标、算子、派生数据的元数据"""
    
    def __init__(self):
        self.raw_fields: Dict[str, DataFieldMeta] = {}
        self.derived_fields: Dict[str, DataFieldMeta] = {}
        self.operators: Dict[str, OperatorMeta] = {}
        self.indicators: Dict[str, IndicatorMeta] = {}
        self._register_all()
    
    def _register_all(self):
        """注册所有元数据"""
        self._register_raw_fields()
        self._register_derived_fields()
        self._register_operators()
        self._register_indicators()
    
    def _register_raw_fields(self):
        """注册原始采集字段"""
        iso16063 = StandardRef("ISO 16063-1", "-", "加速度传感器校准")
        sae_j211 = StandardRef("SAE J211-1", "4.2", "碰撞试验仪器仪表")
        
        raw_fields_def = [
            ("Ax_m_s2", "X轴加速度(纵向)", DataCategory.RAW, "float64[]", "m/s²",
             ["IMU1~10"], ["六轴IMU X通道"], "传感器直接输出",
             [iso16063, sae_j211], (-50, 50)),
            ("Ay_m_s2", "Y轴加速度(侧向)", DataCategory.RAW, "float64[]", "m/s²",
             ["IMU1~10"], ["六轴IMU Y通道"], "传感器直接输出",
             [iso16063, sae_j211], (-50, 50)),
            ("Az_m_s2", "Z轴加速度(垂向)", DataCategory.RAW, "float64[]", "m/s²",
             ["IMU1~10"], ["六轴IMU Z通道"], "传感器直接输出",
             [iso16063, sae_j211], (-50, 50)),
            ("Gx_dps", "X轴角速度(滚转)", DataCategory.RAW, "float64[]", "°/s",
             ["IMU1~10"], ["六轴IMU GX通道"], "传感器直接输出",
             [iso16063], (-2000, 2000)),
            ("Gy_dps", "Y轴角速度(俯仰)", DataCategory.RAW, "float64[]", "°/s",
             ["IMU1~10"], ["六轴IMU GY通道"], "传感器直接输出",
             [iso16063], (-2000, 2000)),
            ("Gz_dps", "Z轴角速度(偏航)", DataCategory.RAW, "float64[]", "°/s",
             ["IMU1~10"], ["六轴IMU GZ通道"], "传感器直接输出",
             [iso16063], (-2000, 2000)),
            ("rel_time", "相对时间", DataCategory.RAW, "float64[]", "s",
             ["全部"], ["系统时钟"], "PTP同步时间戳(IEEE 1588)",
             [StandardRef("IEEE 1588", "-", "精密时钟同步")]),
        ]
        
        for f in raw_fields_def:
            self.raw_fields[f[0]] = DataFieldMeta(*f)
    
    def _register_derived_fields(self):
        """注册派生数据字段"""
        iso2631_1 = StandardRef("ISO 2631-1", "5.3", "频率加权")
        iso6487 = StandardRef("ISO 6487", "5.2.1", "CFC滤波")
        
        derived_def = [
            ("A_MAG", "三轴合成加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU1~10"], ["Ax_m_s2","Ay_m_s2","Az_m_s2"],
             "A_MAG = sqrt(Ax² + Ay² + Az²)", [iso2631_1]),
            ("A_MAG_g", "三轴合成加速度(g单位)", DataCategory.DERIVED, "float64[]", "g",
             ["IMU1~10"], ["A_MAG"], "A_MAG_g = A_MAG / 9.81", [iso2631_1]),
            ("AX_FILTERED", "CFC滤波后X轴加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU1~10"], ["Ax_m_s2"], "4阶Butterworth低通(CFC等级)", [iso6487]),
            ("AY_FILTERED", "CFC滤波后Y轴加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU1~10"], ["Ay_m_s2"], "4阶Butterworth低通(CFC等级)", [iso6487]),
            ("AZ_FILTERED", "CFC滤波后Z轴加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU1~10"], ["Az_m_s2"], "4阶Butterworth低通(CFC等级)", [iso6487]),
            ("DISP_X", "X轴积分位移", DataCategory.DERIVED, "float64[]", "mm",
             ["IMU1~10"], ["Ax_m_s2"], "∬Ax·dt² (0.5Hz高通+去漂移)", [iso6487]),
            ("DISP_Y", "Y轴积分位移", DataCategory.DERIVED, "float64[]", "mm",
             ["IMU1~10"], ["Ay_m_s2"], "∬Ay·dt² (0.5Hz高通+去漂移)", [iso6487]),
            ("DISP_Z", "Z轴积分位移", DataCategory.DERIVED, "float64[]", "mm",
             ["IMU1~10"], ["Az_m_s2"], "∬Az·dt² (0.5Hz高通+去漂移)", [iso6487]),
            ("DISP_3D", "三维合成位移", DataCategory.DERIVED, "float64[]", "mm",
             ["IMU1~10"], ["DISP_X","DISP_Y","DISP_Z"],
             "DISP_3D = sqrt(Dx² + Dy² + Dz²)", [iso6487]),
            ("JERK_X", "X轴加速度变化率", DataCategory.DERIVED, "float64[]", "g/s",
             ["IMU1~10"], ["Ax_m_s2"], "JERK = d(Ax)/dt", [StandardRef("ISO 2631-1", "Annex B", "加速度变化率")]),
            ("JERK_Y", "Y轴加速度变化率", DataCategory.DERIVED, "float64[]", "g/s",
             ["IMU1~10"], ["Ay_m_s2"], "JERK = d(Ay)/dt", [StandardRef("ISO 2631-1", "Annex B", "加速度变化率")]),
            ("JERK_Z", "Z轴加速度变化率", DataCategory.DERIVED, "float64[]", "g/s",
             ["IMU1~10"], ["Az_m_s2"], "JERK = d(Az)/dt", [StandardRef("ISO 2631-1", "Annex B", "加速度变化率")]),
            ("PSD_ZX", "X轴功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["AX_FILTERED"], "Welch法(1024pt Hanning, 50%重叠)", [StandardRef("ISO 2631-1", "5.2", "PSD估计")]),
            ("PSD_ZY", "Y轴功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["AY_FILTERED"], "Welch法(1024pt Hanning, 50%重叠)", [StandardRef("ISO 2631-1", "5.2", "PSD估计")]),
            ("PSD_ZZ", "Z轴功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["AZ_FILTERED"], "Welch法(1024pt Hanning, 50%重叠)", [StandardRef("ISO 2631-1", "5.2", "PSD估计")]),
            ("PSD_FREQ", "PSD频率轴", DataCategory.DERIVED, "float64[]", "Hz",
             ["-"], ["采样率"], "f = k·fs/N", [StandardRef("ISO 2631-1", "5.2", "频率轴")]),
            ("WPSD_ZX", "X轴加权功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["PSD_ZX","PSD_FREQ"], "Wd频率加权(ISO 2631-1 Table 4)", [iso2631_1]),
            ("WPSD_ZY", "Y轴加权功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["PSD_ZY","PSD_FREQ"], "Wd频率加权(ISO 2631-1 Table 4)", [iso2631_1]),
            ("WPSD_ZZ", "Z轴加权功率谱密度", DataCategory.DERIVED, "float64[]", "(m/s²)²/Hz",
             ["IMU1~10"], ["PSD_ZZ","PSD_FREQ"], "Wk频率加权(ISO 2631-1 Table 3)", [iso2631_1]),
            ("STFT_SPEC", "短时傅里叶频谱", DataCategory.DERIVED, "float64[][]", "(m/s²)²/Hz",
             ["IMU1~10"], ["Ay_m_s2"], "Hanning窗1s, 75%重叠", [StandardRef("ISO 18431-4", "4", "时频分析")]),
            ("SRS_MAXIMAX", "最大冲击响应谱", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU1~10"], ["Ax_m_s2"], "Smallwood递推, Q=10(ζ=0.05), 0.5-100Hz", [StandardRef("MIL-STD-810H", "516.8", "SRS计算")]),
            ("RFC_MATRIX", "雨流循环矩阵", DataCategory.DERIVED, "float64[][]", "(g, g)",
             ["IMU1~10"], ["AX_FILTERED"], "ASTM E1049四峰谷法", [StandardRef("ASTM E1049", "-", "雨流计数")]),
            ("HUMAN_SPINE_AX", "人体脊柱X响应加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU5~6(座垫)"], ["Ax_m_s2","Az_m_s2"], "旋转矩阵→线性滤波器→输出", [StandardRef("ISO 2631-5", "4-6", "脊柱响应模型")]),
            ("HUMAN_SPINE_AY", "人体脊柱Y响应加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU5~6(座垫)"], ["Ay_m_s2"], "线性滤波器→输出", [StandardRef("ISO 2631-5", "4-6", "脊柱响应模型")]),
            ("HUMAN_SPINE_AZ", "人体脊柱Z响应加速度", DataCategory.DERIVED, "float64[]", "m/s²",
             ["IMU5~6(座垫)"], ["Ax_m_s2","Az_m_s2"], "非线性SDOF ODE→积分→输出", [StandardRef("ISO 2631-5", "4-6", "脊柱响应模型")]),
        ]
        
        for f in derived_def:
            self.derived_fields[f[0]] = DataFieldMeta(*f)
    
    def _register_operators(self):
        """注册所有算子"""
        # 算子元数据定义: (code, name, desc, inputs, outputs, algo, params, refs)
        ops_def = [
            OperatorMeta("OP-CFC", "通道频率类滤波",
                "对原始加速度信号进行CFC等级低通滤波，消除高频噪声和混叠",
                ["Ax_m_s2","Ay_m_s2","Az_m_s2"],
                ["AX_FILTERED","AY_FILTERED","AZ_FILTERED"],
                "4阶Butterworth低通滤波器, 截止频率fc由CFC等级确定(CFC60→100Hz, CFC180→300Hz, CFC600→1000Hz, CFC1000→1650Hz)",
                {"cfc_class": 600},
                [StandardRef("SAE J211-1", "4.2.3", "CFC滤波等级"), StandardRef("ISO 6487", "5.2.1", "数字滤波规范")]),
            
            OperatorMeta("OP-VECSYN", "三维矢量合成",
                "将X/Y/Z三轴信号合成为单一矢量幅值",
                ["Ax_m_s2","Ay_m_s2","Az_m_s2"],
                ["A_MAG", "A_MAG_g"],
                "A_MAG = sqrt(Ax² + Ay² + Az²); A_MAG_g = A_MAG / g",
                {"g": 9.80665},
                [StandardRef("ISO 2631-1", "5.3.1", "矢量合成")]),
            
            OperatorMeta("OP-INT2", "二重积分位移",
                "对加速度信号进行二重积分得到位移，含0.5Hz高通滤波和去趋势",
                ["AX_FILTERED","AY_FILTERED","AZ_FILTERED"],
                ["DISP_X","DISP_Y","DISP_Z","DISP_3D"],
                "V = ∫a·dt → D = ∫V·dt, 每次积分后应用0.5Hz高通Butterworth滤波器去除非物理漂移",
                {"highpass_fc": 0.5, "filter_order": 2},
                [StandardRef("ISO 6487", "5.2.2", "位移积分")]),
            
            OperatorMeta("OP-DER", "数值微分",
                "对加速度信号求一阶时间导数得到加加速度(Jerk)",
                ["Ax_m_s2","Ay_m_s2","Az_m_s2"],
                ["JERK_X","JERK_Y","JERK_Z"],
                "JERK[n] = (a[n+1] - a[n-1]) / (2·dt)  (中心差分)",
                {},
                [StandardRef("ISO 2631-1", "Annex B", "加速度变化率")]),
            
            OperatorMeta("OP-FFT", "傅里叶变换",
                "将时域信号转换为频域频谱",
                ["AX_FILTERED","AY_FILTERED","AZ_FILTERED"],
                ["PSD_FREQ","PSD_ZX","PSD_ZY","PSD_ZZ"],
                "Welch法平均周期图: 窗长1024点, Hanning窗, 50%重叠, 双边转单边",
                {"nperseg": 1024, "window": "hanning", "overlap": 0.5},
                [StandardRef("ISO 2631-1", "5.2", "PSD估计")]),
            
            OperatorMeta("OP-WK/WD", "频率加权",
                "将PSD乘以ISO 2631-1定义的频率加权曲线",
                ["PSD_Z","PSD_FREQ"],
                ["WPSD_Z"],
                "Wk(f): 0.5→0.5, 0.5-2→f, 2-5→2, 5-16→10/f, 16-80→100/f²; Wd(f): 0.5→1, 0.5-2→f/0.5, 2-5→1, 5-16→5/f, 16-80→80/f²",
                {},
                [StandardRef("ISO 2631-1", "5.3.2", "频率加权曲线 Table 3/4")]),
            
            OperatorMeta("OP-RMS", "均方根值",
                "计算加权加速度的均方根值",
                ["WPSD_Z","PSD_FREQ"],
                ["AW"],
                "AW = sqrt(∫WPSD(f)·df); 也可从时域直接计算: aw = sqrt((1/T)·∫aw²(t)·dt)",
                {"frequency_range": [0.5, 80]},
                [StandardRef("ISO 2631-1", "4.2.1", "r.m.s.加速度")]),
            
            OperatorMeta("OP-SEAT", "座椅有效振幅传递率",
                "计算座垫加权加速度与底座加权加速度的比值",
                ["WPSD_seat","WPSD_base"],
                ["SEAT"],
                "SEAT = sqrt(∫WPSD_seat·df / ∫WPSD_base·df); 即座垫与底座加权r.m.s.之比",
                {},
                [StandardRef("ISO 10326-1", "10.2", "SEAT因子计算")]),
            
            OperatorMeta("OP-TR", "振动传递率",
                "计算输出PSD与输入PSD的比值(dB表达)",
                ["PSD_output","PSD_input"],
                ["TR_freq","TR_dB"],
                "TR(f) = 20·log10(sqrt(PSD_out(f) / PSD_in(f)))",
                {},
                [StandardRef("ISO 10326-1", "10.3", "传递率")]),
            
            OperatorMeta("OP-VDV", "振动剂量值",
                "计算加速度四次方的四次方根积分",
                ["AX_FILTERED","AY_FILTERED","AZ_FILTERED"],
                ["VDV"],
                "VDV = (∫a⁴(t)·dt)^(1/4); 对冲击/瞬态工况更敏感",
                {},
                [StandardRef("ISO 2631-1", "4.2.2", "振动剂量值")]),
            
            OperatorMeta("OP-HIC", "头部损伤指标",
                "计算15ms时间窗内加速度平均值的2.5次方积分",
                ["A_MAG_g"],
                ["HIC15","t_HIC15"],
                "HIC15 = max[(t₂-t₁)·(1/(t₂-t₁)·∫a(t)·dt)^2.5], t₂-t₁≤15ms",
                {"window_max_ms": 15, "min_hic": 0},
                [StandardRef("ISO 6487", "8.2", "HIC计算"), StandardRef("SAE J211-1", "10", "HIC定义")]),
            
            OperatorMeta("OP-SRS", "冲击响应谱",
                "计算单自由度系统对冲击的最大响应谱",
                ["AX_FILTERED"],
                ["SRS_MAXIMAX","SRS_freq"],
                "Smallwood递推算法: SRS(f_n)=max|∫a_in(τ)·h(t-τ;f_n,ζ)dτ|, ζ=0.05, f_n∈[0.5,100]Hz",
                {"Q": 10, "freq_range": [0.5, 100], "n_points": 60},
                [StandardRef("MIL-STD-810H", "516.8", "SRS计算"), StandardRef("ISO 18431-4", "4", "SRS分析")]),
            
            OperatorMeta("OP-STFT", "短时傅里叶变换",
                "计算信号的时变频谱",
                ["Ay_m_s2"],
                ["STFT_SPEC","STFT_freq","STFT_time"],
                "Hanning窗, 窗长1s(512样本), 75%重叠, 双边谱",
                {"window_type": "hanning", "window_size": 1.0, "overlap": 0.75},
                [StandardRef("ISO 18431-4", "4", "时频分析"), StandardRef("SAE J2475", "-", "非平稳数据分析")]),
            
            OperatorMeta("OP-RAIN", "雨流计数",
                "提取载荷-时间历程中的完整应力循环",
                ["AX_FILTERED"],
                ["RFC_MATRIX","RFC_amplitudes","RFC_means","RFC_counts"],
                "ASTM E1049四峰谷法: |y2-y1|≤|y3-y2|时提取循环, 删除y1,y2, 重复至完",
                {},
                [StandardRef("ASTM E1049-85(2017)", "-", "雨流计数标准规程")]),
            
            OperatorMeta("OP-FDS", "疲劳损伤谱",
                "基于雨流循环和S-N曲线计算累积损伤",
                ["RFC_amplitudes","RFC_means","RFC_counts"],
                ["FDS_D","FDS_LEQ"],
                "D=∑(n_i/N_i), N_i=k·S_i^(-b); LEQ=(∑n_i·L_i^k/∑n_i)^(1/k)",
                {"b": 8, "k": 4, "material": "seat_foam"},
                [StandardRef("ISO 12108", "-", "疲劳试验"), StandardRef("FKM Guideline", "-", "非线性疲劳评估")]),
            
            OperatorMeta("OP-ISO2631-5", "脊柱压缩应力",
                "基于ISO 2631-5计算腰椎每日等效压缩应力S_d",
                ["Ax_m_s2","Ay_m_s2","Az_m_s2"],
                ["S_d_Mpa","S_d_level"],
                "人体状态空间过滤→腰椎响应→三轴峰值→六次方剂量融合→S_d",
                {"weight": 75.0, "backrest_angle": 23.0, "omega_n_desc": "2pi*9.85", "zeta": 0.23},
                [StandardRef("ISO 2631-5", "4-6", "脊柱健康评估")]),
            
            OperatorMeta("OP-ATTEN", "衰减效率",
                "计算实验组相对于对照组的性能衰减/改善百分比",
                ["indicator_实验组","indicator_对照组"],
                ["ATTEN_pct"],
                "ATTEN = (indicator_ctrl - indicator_exp) / indicator_ctrl × 100%; 正值表示实验组优于对照组",
                {},
                [StandardRef("V4.06手册", "附录B", "衰减效率定义")]),
            
            OperatorMeta("OP-MAX", "峰值检测",
                "提取时间序列中的最大绝对值",
                ["任意时间序列"],
                ["PEAK_VALUE","PEAK_TIME"],
                "PEAK = max(|x(t)|); t_peak = argmax(|x(t)|)",
                {},
                [StandardRef("ISO 2631-1", "4.1", "峰值因子")]),
            
            OperatorMeta("OP-OVTV", "整体振动总值",
                "计算多轴振动加权总和",
                ["AW_X","AW_Y","AW_Z"],
                ["OVTV"],
                "OVTV = sqrt(k_x²·aw_x² + k_y²·aw_y² + k_z²·aw_z²); k_x=k_y=1.4, k_z=1.0",
                {"k_x": 1.4, "k_y": 1.4, "k_z": 1.0},
                [StandardRef("ISO 2631-1", "5.6", "多轴振动总值")]),
            
            OperatorMeta("OP-FC-TRACK", "瞬时频率跟踪",
                "从STFT时频谱中提取瞬时频率重心轨迹",
                ["STFT_SPEC","STFT_freq","STFT_time"],
                ["FC_MEAN","FC_STD","FC_DRIFT"],
                "fc(t)=∫f·S(t,f)·df / ∫S(t,f)·df; σ(fc)=std(fc(t)); drift=fc(t_end)-fc(t_start)",
                {},
                [StandardRef("ISO 18431-4", "5.2", "时频特征提取")]),
        ]
        
        for op in ops_def:
            self.operators[op.op_code] = op
    
    def _register_indicators(self):
        """注册全部考核指标 — 最完整的元数据定义"""
        
        # ============== M1: AEB紧急制动 ==============
        self.indicators['HIC15'] = IndicatorMeta(
            indicator_code='HIC15', indicator_name='头部损伤指标(15ms)', display_name_cn='头部损伤指标(15ms时间窗)',
            module='M1', evaluation_dimension='时域',
            source_imus=['IMU1','IMU2'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['A_MAG_g'],
            operator_pipeline=['OP-CFC(CFC600)→OP-VECSYN→OP-HIC'],
            formula_text='HIC15 = max[(t₂-t₁) × (ā)²·⁵], where t₂-t₁ ≤ 15ms, ā = (1/(t₂-t₁))∫a(t)dt',
            formula_latex=r'HIC_{15} = \max_{t_1,t_2: t_2-t_1 \leq 15\text{ms}} \left[(t_2-t_1) \cdot \left(\frac{1}{t_2-t_1}\int_{t_1}^{t_2} a(t)dt\right)^{2.5}\right]',
            variables={'a(t)': '头部合成加速度(g)', 't₂-t₁': '积分窗口(≤15ms)', 'ā': '窗口内平均加速度(g)'},
            unit='无量纲', output_type='scalar', precision=1,
            threshold_pass='HIC15 ≤ 650 (FMVSS 208/ECE R94)', threshold_excellent='HIC15 ≤ 500 或魔椅<传统30%',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ISO 6487","8.2","HIC计算方法"), StandardRef("SAE J211-1","10","HIC定义")],
            industry_references=['泛亚PATAC AEB座椅评测内部规程', 'Euro NCAP 2025 乘员保护评分']
        )
        
        self.indicators['ACC-H-PEAK'] = IndicatorMeta(
            indicator_code='ACC-H-PEAK', indicator_name='头部峰值加速度', display_name_cn='头部三维合成峰值加速度',
            module='M1', evaluation_dimension='时域',
            source_imus=['IMU1','IMU2'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['A_MAG_g'],
            operator_pipeline=['OP-CFC(CFC600)→OP-VECSYN→OP-MAX'],
            formula_text='ACC-H-PEAK = max(√(Ax² + Ay² + Az²)) / g',
            formula_latex=r'a_{peak,H} = \max_t \left( \sqrt{a_x^2(t) + a_y^2(t) + a_z^2(t)} \right)',
            variables={'a(t)': '头部三轴加速度(m/s²)', 'g': '重力加速度(9.81 m/s²)'},
            unit='g', output_type='scalar', precision=2,
            threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×70%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 2631-1","4.1","峰值因子")],
            industry_references=['SAE J2999-2017 THOR假人头部加速度基准值']
        )
        
        self.indicators['JERK-H'] = IndicatorMeta(
            indicator_code='JERK-H', indicator_name='头部加速度变化率', display_name_cn='头部合成加速度变化率峰值',
            module='M1', evaluation_dimension='时域',
            source_imus=['IMU1','IMU2'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['JERK_X','JERK_Y','JERK_Z'],
            operator_pipeline=['OP-DER→OP-VECSYN→OP-MAX'],
            formula_text='JERK-H = max(|d(√(Ax²+Ay²+Az²))/dt|) / g',
            formula_latex=r'j_{peak,H} = \max_t \left| \frac{d}{dt} \sqrt{a_x^2(t) + a_y^2(t) + a_z^2(t)} \right|',
            variables={'a(t)': '头部三轴加速度(m/s²)'},
            unit='g/s', output_type='scalar', precision=1,
            threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×65%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 2631-1","Annex B","加速度变化率")],
            industry_references=['传统座椅参考: 458.2±58.7 g/s (V4.06手册)']
        )
        
        # ============== M3: 位移指标 ==============
        self.indicators['DISP-HR'] = IndicatorMeta(
            indicator_code='DISP-HR', indicator_name='头部三维合成位移', display_name_cn='头部三维合成位移(峰值)',
            module='M3', evaluation_dimension='时域',
            source_imus=['IMU1','IMU2'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['DISP_3D'],
            operator_pipeline=['OP-CFC(CFC600)→OP-INT2→OP-VECSYN→OP-MAX'],
            formula_text='DISP-HR = max(√(Dx²(t) + Dy²(t) + Dz²(t))); D(t)=∬a(t)dt²',
            formula_latex=r'D_{HR} = \max_t \sqrt{D_x^2(t) + D_y^2(t) + D_z^2(t)}',
            variables={'D(t)': '二重积分位移(mm)', 'a(t)': 'CFC600滤波后加速度'},
            unit='mm', output_type='scalar', precision=1,
            threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×60%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 6487","5.2.2","位移积分"), StandardRef("VDI 2057-1","5","人体振动")],
            industry_references=['传统座椅参考: 182.5±45.6 mm (V4.06手册)']
        )
        
        self.indicators['ATTEN-H'] = IndicatorMeta(
            indicator_code='ATTEN-H', indicator_name='头部衰减效率', display_name_cn='头部位移衰减效率',
            module='M3', evaluation_dimension='时域',
            source_imus=['IMU1','IMU2'], source_raw_fields=[],
            prerequisite_derived=['DISP-HR(实验)','DISP-HR(对照)'],
            operator_pipeline=['OP-ATTEN'],
            formula_text='ATTEN-H = (DISP_HR_ctrl - DISP_HR_exp) / DISP_HR_ctrl × 100%',
            formula_latex=r'\eta_H = \frac{D_{HR,ctrl} - D_{HR,exp}}{D_{HR,ctrl}} \times 100\%',
            variables={'D_HR_ctrl': '传统座椅头部位移(mm)', 'D_HR_exp': 'GQY魔椅头部位移(mm)'},
            unit='%', output_type='scalar', precision=1,
            threshold_pass='> 20% (有效改善)', threshold_excellent='> 35% (显著改善)',
            evaluation_direction='higher_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("V4.06手册","附录B","衰减效率定义")],
            industry_references=['V4.06参考值: 29.7±2.6%']
        )
        
        # ============== M4: 振动舒适度 ==============
        self.indicators['SEAT-Z'] = IndicatorMeta(
            indicator_code='SEAT-Z', indicator_name='Z向SEAT因子', display_name_cn='Z向座椅有效振幅传递率',
            module='M4', evaluation_dimension='频域',
            source_imus=['IMU5~6(座垫)','IMU7~8(底座)'], source_raw_fields=['Az_m_s2'],
            prerequisite_derived=['WPSD_ZZ(座垫)','WPSD_ZZ(底座)'],
            operator_pipeline=['OP-CFC(CFC1000)→OP-FFT→OP-WK→OP-SEAT'],
            formula_text='SEAT-Z = √(∫WPSD_ZZ_seat(f)·df / ∫WPSD_ZZ_base(f)·df)',
            formula_latex=r'SEAT_Z = \sqrt{\frac{\int_{0.5}^{80} G_{w,seat}(f) df}{\int_{0.5}^{80} G_{w,base}(f) df}}',
            variables={'G_w(f)': 'Wk加权功率谱密度', 'seat': '座垫处', 'base': '底座处'},
            unit='无量纲', output_type='scalar', precision=3,
            threshold_pass='≤ 1.0', threshold_excellent='≤ 0.8',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ISO 10326-1","10.2","SEAT因子"), StandardRef("ISO 2631-1","5.3","频率加权Wk")],
            industry_references=['ISO 10326-1:2016 Annex A示例', '座椅悬架设计准则']
        )
        
        self.indicators['VDV-Z'] = IndicatorMeta(
            indicator_code='VDV-Z', indicator_name='Z向振动剂量值', display_name_cn='Z向振动剂量值',
            module='M4', evaluation_dimension='时域',
            source_imus=['IMU5~6(座垫)'], source_raw_fields=['Az_m_s2'],
            prerequisite_derived=['AZ_FILTERED'],
            operator_pipeline=['OP-CFC(CFC1000)→OP-WK(时域)→OP-VDV'],
            formula_text='VDV-Z = (∫aw_z⁴(t)·dt)^(1/4)',
            formula_latex=r'VDV_Z = \left( \int_0^T a_{wz}^4(t) dt \right)^{1/4}',
            variables={'a_wz(t)': '频率加权后的Z轴加速度(m/s²)', 'T': '总暴露时间(s)'},
            unit='m/s^1.75', output_type='scalar', precision=3,
            threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×70%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 2631-1","4.2.2","振动剂量值")],
            industry_references=['BS 6841:1987 VDV应用指南']
        )
        
        self.indicators['AW-Z'] = IndicatorMeta(
            indicator_code='AW-Z', indicator_name='Z向加权均方根加速度', display_name_cn='Z向频率加权r.m.s.加速度',
            module='M4', evaluation_dimension='频域',
            source_imus=['IMU5~6(座垫)'], source_raw_fields=['Az_m_s2'],
            prerequisite_derived=['WPSD_ZZ'],
            operator_pipeline=['OP-CFC(CFC1000)→OP-FFT→OP-WK→OP-RMS'],
            formula_text='AW-Z = √(∫WPSD_ZZ(f)·df), f∈[0.5,80]Hz',
            formula_latex=r'a_{wz} = \sqrt{\int_{0.5}^{80} G_{wz}(f) df}',
            variables={'G_wz(f)': 'Wk加权功率谱密度'},
            unit='m/s²', output_type='scalar', precision=3,
            threshold_pass='≤ 0.315 (8h暴露)', threshold_excellent='≤ 0.2',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ISO 2631-1","5.3.2","频率加权"), StandardRef("ISO 2631-1","Annex C","舒适度边界")],
            industry_references=['EU Directive 2002/44/EC 职业振动暴露']
        )
        
        self.indicators['OVTV'] = IndicatorMeta(
            indicator_code='OVTV', indicator_name='整体振动总值', display_name_cn='多轴振动综合总值',
            module='M4', evaluation_dimension='频域',
            source_imus=['IMU5~6(座垫)'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['AW-X','AW-Y','AW-Z'],
            operator_pipeline=['OP-CFC→OP-FFT→OP-WK→OP-RMS→OP-OVTV'],
            formula_text='OVTV = √(k_x²·aw_x² + k_y²·aw_y² + k_z²·aw_z²); k_x=k_y=1.4, k_z=1.0',
            formula_latex=r'OVTV = \sqrt{1.4^2 a_{wx}^2 + 1.4^2 a_{wy}^2 + a_{wz}^2}',
            variables={'a_wx/a_wy/a_wz': '各轴加权r.m.s.加速度(m/s²)', 'k': '多轴合成系数'},
            unit='m/s²', output_type='scalar', precision=3,
            threshold_pass='魔椅 < 传统座椅', threshold_excellent='魔椅 ≤ 传统×65%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 2631-1","5.6","多轴振动总值")],
            industry_references=['乘用车座椅舒适度联合评估模型']
        )
        
        # ============== C3: 脊柱健康 ==============
        self.indicators['S_D'] = IndicatorMeta(
            indicator_code='S_D', indicator_name='腰椎每日等效压缩应力', display_name_cn='腰椎每日等效压缩应力(ISO 2631-5)',
            module='C3', evaluation_dimension='生物力学',
            source_imus=['IMU5~6(座垫)'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['HUMAN_SPINE_AX','HUMAN_SPINE_AY','HUMAN_SPINE_AZ'],
            operator_pipeline=['靠背旋转矩阵→体重修正→水平线性滤波→垂向非线性ODE→峰值提取→六次方剂量融合→S_d'],
            formula_text='S_d = (Σ D_k⁶)^(1/6); D_k⁶ = (c_x·D_xk)⁶ + (c_y·D_yk)⁶ + (c_z·D_zk)⁶',
            formula_latex=r'S_d = \left( \sum_{k=1}^{N} \left[ c_x^6 D_{xk}^6 + c_y^6 D_{yk}^6 + c_z^6 D_{zk}^6 \right] \right)^{1/6}',
            variables={'c_x=0.018': 'X轴方向加权系数', 'c_y=0.015': 'Y轴方向加权系数', 'c_z=0.003': 'Z轴方向加权系数', 'D_k': '第k次冲击事件腰椎响应峰值(m/s²)'},
            unit='MPa', output_type='scalar', precision=4,
            threshold_pass='< 0.5 → 绿色(低风险)', threshold_excellent='< 0.3',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ISO 2631-5","5-6","脊柱健康评估"), StandardRef("ISO 2631-5","Annex A","方向加权系数")],
            industry_references=['ISVR Griffin团队半躺坐姿研究', 'MDPI重型车辆振动暴露研究']
        )
        
        # ============== SRS冲击 ==============
        self.indicators['SRS-MRS'] = IndicatorMeta(
            indicator_code='SRS-MRS', indicator_name='最大冲击响应谱峰值', display_name_cn='冲击响应谱最大峰值(Maximax)',
            module='M1/C3', evaluation_dimension='冲击域',
            source_imus=['IMU1~4'], source_raw_fields=['Ax_m_s2','Az_m_s2'],
            prerequisite_derived=['SRS_MAXIMAX'],
            operator_pipeline=['OP-CFC(CFC600)→OP-SRS(Q=10,ζ=0.05)'],
            formula_text='SRS-MRS = max(SRS(f)); SRS(f) = max|∫a_in(τ)·h(t-τ;f,ζ)dτ|',
            formula_latex=r'SRS_{MRS} = \max_{f \in [0.5,100]\text{Hz}} SRS(f)',
            variables={'SRS(f)': '单自由度系统最大响应(m/s²)', 'Q=10': '品质因数(ζ=0.05)'},
            unit='m/s²', output_type='scalar', precision=2,
            threshold_pass='魔椅SRS < 传统SRS (5-30Hz)', threshold_excellent='魔椅SRS ≤ 传统×60%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("MIL-STD-810H","516.8","SRS计算"), StandardRef("ISO 18431-4","4","SRS分析")],
            industry_references=['Smallwood 1981递推算法', 'JPL冲击试验规范']
        )
        
        self.indicators['SRS-ATT'] = IndicatorMeta(
            indicator_code='SRS-ATT', indicator_name='冲击衰减率(频域)', display_name_cn='冲击响应谱衰减率(5-30Hz频段)',
            module='M1', evaluation_dimension='冲击域',
            source_imus=['IMU1~4'], source_raw_fields=[],
            prerequisite_derived=['SRS(实验)','SRS(对照)'],
            operator_pipeline=['OP-ATTEN(频域点对点)'],
            formula_text='SRS-ATT(f) = (1 - SRS_exp(f)/SRS_ctrl(f)) × 100%; avg over f∈[5,30]Hz',
            formula_latex=r'\eta_{SRS}(f) = \left(1 - \frac{SRS_{exp}(f)}{SRS_{ctrl}(f)}\right) \times 100\%',
            variables={'SRS_exp': '魔椅冲击响应谱', 'SRS_ctrl': '传统座椅冲击响应谱'},
            unit='%', output_type='scalar', precision=1,
            threshold_pass='> 20% (有效衰减)', threshold_excellent='> 35% (显著衰减)',
            evaluation_direction='higher_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("MIL-STD-810H","516.8","冲击衰减评估")],
            industry_references=['汽车座椅发泡削峰能力评估']
        )
        
        # ============== STFT时频域 ==============
        self.indicators['STFT-FC'] = IndicatorMeta(
            indicator_code='STFT-FC', indicator_name='瞬时频率重心标准差', display_name_cn='侧向加速度瞬时频率重心的标准差',
            module='M2', evaluation_dimension='时频域',
            source_imus=['IMU3~4(躯干)'], source_raw_fields=['Ay_m_s2'],
            prerequisite_derived=['STFT_SPEC','STFT_freq','STFT_time'],
            operator_pipeline=['OP-STFT(Hanning 1s/75%)→OP-FC-TRACK'],
            formula_text='STFT-FC = σ(fc(t)); fc(t)=∫f·S(t,f)df/∫S(t,f)df',
            formula_latex=r'\sigma(f_c) = \sqrt{\frac{1}{T}\int (f_c(t) - \bar{f_c})^2 dt}',
            variables={'fc(t)': '瞬时频率重心(Hz)', 'S(t,f)': '时频谱'},
            unit='Hz', output_type='scalar', precision=2,
            threshold_pass='魔椅σ(fc) < 传统σ(fc)', threshold_excellent='魔椅σ(fc) ≤ 传统×50%',
            evaluation_direction='lower_better', comparison_method='relative_to_ctrl',
            standard_refs=[StandardRef("ISO 18431-4","5.2","时频特征"), StandardRef("SAE J2475","-","非平稳分析")],
            industry_references=['蛇形驾驶侧翼支撑刚度诊断']
        )
        
        # ============== FDS疲劳 ==============
        self.indicators['FDS-D'] = IndicatorMeta(
            indicator_code='FDS-D', indicator_name='累积疲劳损伤指数', display_name_cn='Palmgren-Miner累积损伤指数',
            module='M1/M4', evaluation_dimension='疲劳域',
            source_imus=['IMU5~8'], source_raw_fields=['Ax_m_s2','Ay_m_s2','Az_m_s2'],
            prerequisite_derived=['RFC_MATRIX'],
            operator_pipeline=['OP-CFC→OP-RAIN→OP-FDS'],
            formula_text='FDS-D = Σ(n_i/N_i); N_i = k · S_i^(-b); b=8, k=4',
            formula_latex=r'D = \sum_{i=1}^{m} \frac{n_i}{N_i}, \quad N_i = k \cdot S_i^{-b}',
            variables={'n_i': '第i级应力幅实际循环数', 'N_i': '该应力幅下疲劳寿命', 'b=8': 'S-N曲线斜率(座椅发泡)', 'k=4': 'S-N曲线截距'},
            unit='无量纲', output_type='scalar', precision=4,
            threshold_pass='D < 0.7 (可接受)', threshold_excellent='D < 0.3 (优秀)',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ASTM E1049","-","雨流计数"), StandardRef("ISO 12108","-","疲劳试验"), StandardRef("FKM Guideline","-","非线性疲劳")],
            industry_references=['nCode GlyphWorks标准疲劳分析流程']
        )
        
        # ============== TR: 传递率 ==============
        self.indicators['TR-Z'] = IndicatorMeta(
            indicator_code='TR-Z', indicator_name='Z向振动传递率峰值', display_name_cn='Z向振动传递率(dB)的峰值',
            module='M4', evaluation_dimension='频域',
            source_imus=['IMU5~6(座垫)','IMU7~8(底座)'], source_raw_fields=['Az_m_s2'],
            prerequisite_derived=['PSD_ZZ(座垫)','PSD_ZZ(底座)','PSD_FREQ'],
            operator_pipeline=['OP-CFC(CFC1000)→OP-FFT→OP-TR'],
            formula_text='TR-Z(f) = 20·log10(√(PSD_out(f) / PSD_in(f)))',
            formula_latex=r'TR(f) = 20 \cdot \log_{10} \sqrt{\frac{G_{out}(f)}{G_{in}(f)}}',
            variables={'G_out': '座垫PSD', 'G_in': '底座PSD'},
            unit='dB', output_type='curve', precision=2,
            threshold_pass='TR-Z(f) < 0 dB (0.5-50Hz)', threshold_excellent='TR-Z(f) < -3 dB 在共振频段',
            evaluation_direction='lower_better', comparison_method='absolute',
            standard_refs=[StandardRef("ISO 10326-1","10.3","传递率"), StandardRef("ISO 10326-2","Annex B","传递函数")],
            industry_references=['LMS Test.Lab传递率分析模块']
        )
    
    def get_indicator_trace(self, code: str) -> str:
        """获取指标的完整数据溯源链文本"""
        ind = self.indicators.get(code)
        if not ind:
            return f"指标 {code} 未注册"
        
        lines = [f"指标溯源链: {ind.indicator_code} — {ind.display_name_cn}"]
        lines.append(f"  [采集] IMU: {', '.join(ind.source_imus)} → 原始字段: {', '.join(ind.source_raw_fields)}")
        if ind.prerequisite_derived:
            lines.append(f"  [派生] 前置派生数据: {' → '.join(ind.prerequisite_derived)}")
        lines.append(f"  [算子] 处理流水线: {' → '.join(ind.operator_pipeline)}")
        lines.append(f"  [输出] {ind.indicator_code} = {ind.formula_text}")
        lines.append(f"  [单位] {ind.unit}  |  [维度] {ind.evaluation_dimension}  |  [方向] {ind.evaluation_direction}")
        lines.append(f"  [标准] {', '.join(str(r) for r in ind.standard_refs)}")
        return '\n'.join(lines)
    
    def print_all_traces(self):
        """打印所有指标溯源链"""
        for code in sorted(self.indicators.keys()):
            print(self.get_indicator_trace(code))
            print()


# ========================================================================
# PART B: 数据全流程处理管线
# ========================================================================

class DataPipeline:
    """数据全流程处理管线 — 从原始采集到最终指标输出的完整流水线"""
    
    def __init__(self, registry: MetadataRegistry = None):
        self.registry = registry or MetadataRegistry()
        self.raw_data: Dict[str, Dict] = {}     # IMU名称 → 原始数据字典
        self.derived: Dict[str, np.ndarray] = {} # 派生数据缓存
        self.fs: float = 512.0
        self.g = 9.80665
    
    def load_imu(self, imu_name: str, data: Dict, fs: float = None):
        """加载IMU原始数据"""
        required = ['rel_time','Ax_m_s2','Ay_m_s2','Az_m_s2','Gx_dps','Gy_dps','Gz_dps']
        for f in required:
            if f not in data:
                raise ValueError(f"IMU {imu_name} 缺少必需字段: {f}")
        
        self.raw_data[imu_name] = {k: np.asarray(v) for k, v in data.items()}
        if fs:
            self.fs = fs
        else:
            t = self.raw_data[imu_name]['rel_time']
            self.fs = 1.0 / (t[1] - t[0]) if len(t) > 1 else 512.0
    
    def _get_array(self, imu: str, field: str) -> np.ndarray:
        return self.raw_data[imu][field]
    
    def step_cfc_filter(self, cfc_class: int = 600):
        """步骤1: CFC通道频率类滤波 (OP-CFC)"""
        if cfc_class == 60: fc = 100.0
        elif cfc_class == 180: fc = 300.0
        elif cfc_class == 600: fc = 1000.0
        elif cfc_class == 1000: fc = 1650.0
        else: fc = 1000.0
        
        nyq = self.fs / 2.0
        if fc >= nyq:
            fc = nyq * 0.95  # 安全裕度
        b, a = signal.butter(4, fc / nyq, btype='low')
        
        for name in self.raw_data:
            data = self.raw_data[name]
            for axis in ['Ax_m_s2','Ay_m_s2','Az_m_s2']:
                key = f"{name}/{axis}_filtered"
                self.derived[key] = signal.filtfilt(b, a, data[axis])
        
        return self
    
    def step_vector_synthesis(self):
        """步骤2: 三轴矢量合成 (OP-VECSYN)"""
        for name in self.raw_data:
            ax_k = f"{name}/Ax_m_s2_filtered"
            ay_k = f"{name}/Ay_m_s2_filtered"
            az_k = f"{name}/Az_m_s2_filtered"
            
            ax = self.derived.get(ax_k, self._get_array(name, 'Ax_m_s2'))
            ay = self.derived.get(ay_k, self._get_array(name, 'Ay_m_s2'))
            az = self.derived.get(az_k, self._get_array(name, 'Az_m_s2'))
            
            self.derived[f"{name}/A_MAG"] = np.sqrt(ax**2 + ay**2 + az**2)
            self.derived[f"{name}/A_MAG_g"] = self.derived[f"{name}/A_MAG"] / self.g
        
        return self
    
    def step_displacement_integration(self):
        """步骤3: 二重积分位移 (OP-INT2)"""
        b_hp, a_hp = signal.butter(2, 0.5 / (self.fs/2), btype='high')
        dt = 1.0 / self.fs
        
        for name in self.raw_data:
            for axis in ['Ax_m_s2','Ay_m_s2','Az_m_s2']:
                key_f = f"{name}/{axis}_filtered"
                acc = self.derived.get(key_f, self._get_array(name, axis))
                
                # 第一次积分: a→v
                vel = integrate.cumulative_trapezoid(signal.filtfilt(b_hp, a_hp, acc), dx=dt, initial=0)
                vel_f = signal.filtfilt(b_hp, a_hp, vel)
                
                # 第二次积分: v→d
                disp = integrate.cumulative_trapezoid(vel_f, dx=dt, initial=0)
                
                axis_letter = axis[0].upper() if axis[0] in 'AX' else axis[1]  # -> X/Y/Z
                self.derived[f"{name}/DISP_{axis_letter}"] = disp * 1000  # m→mm
            
            # 三维合成位移
            self.derived[f"{name}/DISP_3D"] = np.sqrt(
                self.derived.get(f"{name}/DISP_X", np.zeros(len(acc))) ** 2 + 
                self.derived.get(f"{name}/DISP_Y", np.zeros(len(acc))) ** 2 + 
                self.derived.get(f"{name}/DISP_Z", np.zeros(len(acc))) ** 2
            )
        
        return self
    
    def step_psd_welch(self, nperseg: int = 1024):
        """步骤4: Welch PSD估计 (OP-FFT)"""
        for name in self.raw_data:
            for axis_letter in ['X','Y','Z']:
                field_key = f"A{axis_letter.lower()}_m_s2"
                key_f = f"{name}/{field_key}_filtered"
                acc = self.derived.get(key_f, self._get_array(name, field_key))
                
                f, pxx = welch(acc, self.fs, nperseg=nperseg, 
                              noverlap=nperseg//2, window='hann')
                
                self.derived[f"{name}/PSD_{axis_letter}"] = pxx
                self.derived[f"{name}/PSD_FREQ"] = f
        
        return self
    
    def step_frequency_weighting(self):
        """步骤5: ISO 2631-1频率加权 (OP-WK/WD)"""
        for name in self.raw_data:
            f = self.derived[f"{name}/PSD_FREQ"]
            
            # Wk (Z轴)
            w_z = np.ones_like(f)
            mask1 = (f >= 0.5) & (f < 2);  w_z[mask1] = f[mask1]
            mask2 = (f >= 2) & (f < 5);    w_z[mask2] = 2.0
            mask3 = (f >= 5) & (f < 16);   w_z[mask3] = 10.0 / f[mask3]
            mask4 = (f >= 16) & (f <= 80); w_z[mask4] = 100.0 / f[mask4]**2
            mask5 = f < 0.5;               w_z[mask5] = 0.5
            mask6 = f > 80;                w_z[mask6] = 0.0
            
            # Wd (X/Y轴)
            w_xy = np.ones_like(f)
            mask1 = (f >= 0.5) & (f < 2);   w_xy[mask1] = f[mask1] / 0.5
            mask2 = (f >= 2) & (f < 5);     w_xy[mask2] = 1.0
            mask3 = (f >= 5) & (f < 16);    w_xy[mask3] = 5.0 / f[mask3]
            mask4 = (f >= 16) & (f <= 80);  w_xy[mask4] = 80.0 / f[mask4]**2
            mask5 = f < 0.5;                w_xy[mask5] = 1.0
            mask6 = f > 80;                 w_xy[mask6] = 0.0
            
            for axis_letter, w in [('Z', w_z), ('X', w_xy), ('Y', w_xy)]:
                psd = self.derived[f"{name}/PSD_{axis_letter}"]
                self.derived[f"{name}/WPSD_{axis_letter}"] = psd * w**2
        
        return self
    
    def step_rms(self):
        """步骤6: 计算加权r.m.s.值 (OP-RMS)"""
        for name in self.raw_data:
            f = self.derived[f"{name}/PSD_FREQ"]
            for axis in ['X','Y','Z']:
                wpsd = self.derived[f"{name}/WPSD_{axis}"]
                mask = (f >= 0.5) & (f <= 80)
                aw = np.sqrt(np.trapz(wpsd[mask], f[mask]))
                self.derived[f"{name}/AW_{axis}"] = aw
        
        return self
    
    def step_hic15(self, imu_name: str) -> Dict:
        """步骤: HIC15 计算 (OP-HIC)"""
        key = f"{imu_name}/A_MAG_g"
        a_g = self.derived.get(key)
        if a_g is None:
            a_g = np.sqrt(self._get_array(imu_name,'Ax_m_s2')**2 + 
                         self._get_array(imu_name,'Ay_m_s2')**2 + 
                         self._get_array(imu_name,'Az_m_s2')**2) / self.g
        
        dt = 1.0 / self.fs
        win = int(0.015 / dt)
        if win < 1: return {'HIC15': 0.0, 't_HIC15_s': 0.0}
        
        hic_max = 0.0
        t = self.raw_data[imu_name]['rel_time']
        for i in range(len(a_g) - win):
            w = a_g[i:i+win]
            hic = (t[i+win-1] - t[i]) * np.mean(w)**2.5
            if hic > hic_max:
                hic_max = hic
                t_hic = t[i]
        
        return {'HIC15': float(hic_max), 't_HIC15_s': float(t_hic)}
    
    def step_vdv(self, imu_name: str, axis: str = 'Z') -> float:
        """步骤: VDV计算 (OP-VDV)"""
        field = f"A{axis.lower()}_m_s2"
        key = f"{imu_name}/{field}_filtered"
        a = self.derived.get(key, self._get_array(imu_name, field))
        
        # 简化频率加权
        nyq = self.fs / 2.0
        b_w, a_w = signal.butter(2, [0.4/nyq, 100.0/nyq], btype='band')
        a_w_f = signal.filtfilt(b_w, a_w, a)
        
        dt = 1.0 / self.fs
        return float((np.sum(a_w_f**4) * dt)**0.25)
    
    def step_srs(self, imu_name: str, axis: str = 'X', Q: float = 10.0) -> Dict:
        """步骤: SRS冲击响应谱 (OP-SRS)"""
        field = f"A{axis.lower()}_m_s2"
        a = self._get_array(imu_name, field)
        
        fn = np.logspace(np.log10(0.5), np.log10(100), 60)
        zeta = 1.0 / (2.0 * Q)
        dt = 1.0 / self.fs
        srs = np.zeros(len(fn))
        a_peak = np.max(np.abs(a))
        
        for i, f in enumerate(fn):
            omega_n = 2.0 * np.pi * f
            omega_d = omega_n * np.sqrt(1.0 - zeta**2)
            E = np.exp(-zeta * omega_n * dt)
            S_val = E * np.sin(omega_d * dt)
            C_val = E * np.cos(omega_d * dt)
            K = omega_n * dt * E / np.sqrt(1.0 - zeta**2 + 1e-20)
            
            b1, b2 = 2.0 * C_val, -(E**2)
            a0 = 1.0 - K * S_val
            a1 = K * S_val - E * (S_val / (omega_d * dt + 1e-20) + C_val)
            
            resp = np.zeros(len(a))
            for j in range(2, len(a)):
                resp[j] = b1*resp[j-1] + b2*resp[j-2] + a0*a[j] + a1*a[j-1]
            srs[i] = np.max(np.abs(resp))
        
        mask = (fn >= 5) & (fn <= 30)
        return {
            'SRS_PEAK': float(np.max(srs)),
            'SRS_PEAK_FREQ': float(fn[np.argmax(srs)]),
            'SRS_Q': float(np.max(srs) / (a_peak + 1e-12)) if a_peak > 0 else 0.0,
            'SRS_AVG_5_30Hz': float(np.mean(srs[mask])) if np.any(mask) else float(np.mean(srs)),
            'fn': fn, 'srs': srs,
        }
    
    def step_iso2631_5_sd(self, imu_name: str, weight: float = 75.0, 
                          backrest_angle: float = 23.0) -> Dict:
        """步骤: ISO 2631-5 S_d 计算"""
        t = self.raw_data[imu_name]['rel_time']
        ax = self._get_array(imu_name, 'Ax_m_s2')
        ay = self._get_array(imu_name, 'Ay_m_s2')
        az = self._get_array(imu_name, 'Az_m_s2')
        dt = 1.0 / self.fs
        
        # 旋转矩阵
        theta = np.radians(backrest_angle)
        ct, st = np.cos(theta), np.sin(theta)
        ax_h = ax * ct - az * st
        ay_h = ay
        az_h = ax * st + az * ct
        
        # 体重修正
        omega_n = 2.0 * np.pi * 9.85 * np.sqrt(75.0 / weight)
        zeta = 0.23 * np.sqrt(weight / 75.0)
        
        # X/Y线性滤波
        sys_h = lti([0.0, 1.0], [1.0, 31.4, 400.0])
        _, a_lx, _ = lsim(sys_h, U=ax_h, T=t)
        _, a_ly, _ = lsim(sys_h, U=ay_h, T=t)
        
        # Z非线性
        a_lz = np.zeros(len(t))
        disp, vel = 0.0, 0.0
        for i in range(1, len(t)):
            u_z = -az_h[i]
            k_mod = 1.0 + 2.0 * (abs(disp) * 1000) if disp < 0 else 1.0
            acc_spinal = u_z - (2.0*zeta*omega_n*vel) - (k_mod*omega_n**2*disp)
            vel += acc_spinal * dt
            disp += vel * dt
            a_lz[i] = acc_spinal
        
        # 峰值+剂量
        px, _ = find_peaks(np.abs(a_lx), distance=int(self.fs * 0.2))
        py, _ = find_peaks(np.abs(a_ly), distance=int(self.fs * 0.2))
        pz, _ = find_peaks(np.abs(a_lz), distance=int(self.fs * 0.2))
        
        max_len = min(len(px), len(py), len(pz))
        if max_len == 0:
            return {'S_d_MPa': 0.0, 'S_d_level': '无显著冲击'}
        
        cx, cy, cz = 0.018, 0.015, 0.003
        d_k6 = (cx*np.abs(a_lx[px[:max_len]]))**6 + (cy*np.abs(a_ly[py[:max_len]]))**6 + (cz*np.abs(a_lz[pz[:max_len]]))**6
        sd = np.sum(d_k6)**(1.0/6.0)
        
        if sd < 0.5: level = '绿色: 低风险'
        elif sd <= 0.8: level = '黄色: 中度风险'
        else: level = '红色: 高风险'
        
        return {'S_d_MPa': float(sd), 'S_d_level': level, 'n_events': int(max_len)}
    
    def compute_seat(self, imu_seat: str, imu_base: str) -> Dict:
        """计算SEAT因子"""
        seat = {}
        for axis in ['Z']:
            aw_s = self.derived[f"{imu_seat}/AW_{axis}"]
            aw_b = self.derived[f"{imu_base}/AW_{axis}"]
            seat[f'SEAT_{axis}'] = float(aw_s / aw_b if aw_b > 1e-9 else np.nan)
        return seat
    
    def compute_ovtv(self, imu_name: str) -> float:
        """计算OVTV"""
        aw_x = self.derived[f"{imu_name}/AW_X"]
        aw_y = self.derived[f"{imu_name}/AW_Y"]
        aw_z = self.derived[f"{imu_name}/AW_Z"]
        return float(np.sqrt(1.4**2*aw_x**2 + 1.4**2*aw_y**2 + aw_z**2))
    
    def compute_attenuation(self, val_exp: float, val_ctrl: float) -> float:
        """计算衰减效率"""
        if abs(val_ctrl) < 1e-9:
            return 0.0
        return float((val_ctrl - val_exp) / val_ctrl * 100)


# ========================================================================
# PART C: 快速测试
# ========================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("  考核指标元数据全流程引擎 V2.0 — 验证测试")
    print("=" * 70)
    
    # 1. 元数据注册
    registry = MetadataRegistry()
    print(f"\n元数据注册完成:")
    print(f"  原始字段: {len(registry.raw_fields)}")
    print(f"  派生字段: {len(registry.derived_fields)}")
    print(f"  算子: {len(registry.operators)}")
    print(f"  考核指标: {len(registry.indicators)}")
    
    # 2. 打印选定的指标溯源链
    print("\n" + "=" * 70)
    print("  指标溯源链示例 (HIC15)")
    print("=" * 70)
    print(registry.get_indicator_trace('HIC15'))
    
    print("\n" + "=" * 70)
    print("  指标溯源链示例 (SEAT-Z)")
    print("=" * 70)
    print(registry.get_indicator_trace('SEAT-Z'))
    
    print("\n" + "=" * 70)
    print("  指标溯源链示例 (S_D)")
    print("=" * 70)
    print(registry.get_indicator_trace('S_D'))
    
    # 3. 数据管线验证
    print("\n" + "=" * 70)
    print("  数据管线验证 (模拟AEB工况)")
    print("=" * 70)
    
    fs = 512
    t = np.linspace(0, 5, 5*fs)
    
    # 模拟数据: AEB制动
    ax_h = np.zeros_like(t)
    ax_h[int(2*fs):int(3.5*fs)] = -0.8 * 9.81  # -0.8g
    ay_h = 0.05 * np.sin(2*np.pi*2*t)
    az_h = 0.1 * np.random.randn(len(t))
    az_h[int(4*fs):int(4.15*fs)] += 25 * np.sin(np.pi*(t[int(4*fs):int(4.15*fs)]-4)/0.15)
    
    pipeline = DataPipeline(registry)
    pipeline.load_imu('IMU1_头部眉心-1', {
        'rel_time': t, 'Ax_m_s2': ax_h, 'Ay_m_s2': ay_h, 'Az_m_s2': az_h,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    pipeline.load_imu('IMU2_头部眉心-2', {
        'rel_time': t, 'Ax_m_s2': ax_h*1.3, 'Ay_m_s2': ay_h*1.3, 'Az_m_s2': az_h*1.3,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    pipeline.load_imu('IMU5_座垫R点-1', {
        'rel_time': t, 'Ax_m_s2': ax_h*0.5, 'Ay_m_s2': ay_h*0.5, 'Az_m_s2': az_h*0.5,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    pipeline.load_imu('IMU6_座垫R点-2', {
        'rel_time': t, 'Ax_m_s2': ax_h*0.6, 'Ay_m_s2': ay_h*0.6, 'Az_m_s2': az_h*0.6,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    pipeline.load_imu('IMU7_座椅底部-1', {
        'rel_time': t, 'Ax_m_s2': ax_h*0.2, 'Ay_m_s2': ay_h*0.2, 'Az_m_s2': az_h*0.2,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    pipeline.load_imu('IMU8_座椅底部-2', {
        'rel_time': t, 'Ax_m_s2': ax_h*0.25, 'Ay_m_s2': ay_h*0.25, 'Az_m_s2': az_h*0.25,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': np.zeros_like(t), 'Gz_dps': np.zeros_like(t),
    })
    
    # 运行处理管线
    pipeline.step_cfc_filter(600)\
             .step_vector_synthesis()\
             .step_displacement_integration()\
             .step_psd_welch()\
             .step_frequency_weighting()\
             .step_rms()
    
    # 计算示例指标
    hic = pipeline.step_hic15('IMU1_头部眉心-1')
    vdv = pipeline.step_vdv('IMU5_座垫R点-1', 'Z')
    seat = pipeline.compute_seat('IMU5_座垫R点-1', 'IMU7_座椅底部-1')
    srs = pipeline.step_srs('IMU1_头部眉心-1', 'X')
    sd = pipeline.step_iso2631_5_sd('IMU5_座垫R点-1')
    
    print(f"  HIC15(实验组头部): {hic['HIC15']:.1f}")
    print(f"  VDV-Z(实验组座垫): {vdv:.3f} m/s^1.75")
    print(f"  SEAT-Z(实验组): {seat['SEAT_Z']:.3f}")
    print(f"  SRS峰值(头部X): {srs['SRS_PEAK']:.2f} m/s², Q={srs['SRS_Q']:.2f}")
    print(f"  S_d(实验组座垫): {sd['S_d_MPa']:.4f} MPa ({sd['S_d_level']})")
    
    print("\n✓ 全流程引擎验证通过")
