#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
振动台架实验数据模型 (ISO 10326-1)

定义台架实验的数据结构: 三组三轴加速度传感器 + 元数据
通道映射: 123-靠背(T8), 456-臀部(R-point), 789-六轴平台(Platform)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import numpy as np


@dataclass
class TriaxialChannels:
    """三轴加速度通道"""
    x: np.ndarray = field(default_factory=lambda: np.array([]))
    y: np.ndarray = field(default_factory=lambda: np.array([]))
    z: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def n_samples(self) -> int:
        return len(self.x)

    @property
    def all_valid(self) -> bool:
        return len(self.x) > 0 and len(self.x) == len(self.y) == len(self.z)


@dataclass
class QualityIssue:
    """数据质量问题"""
    issue_type: str          # missing_values / constant_channel / irregular_sampling / spikes
    description: str
    severity: str = 'warning'  # warning / error


@dataclass
class DataQuality:
    """数据质量评估结果"""
    score: float                         # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return self.score >= 80

    @property
    def has_errors(self) -> bool:
        return any(i.severity == 'error' for i in self.issues)


@dataclass
class ShakerData:
    """振动台架实验数据结构"""
    filepath: str
    time: np.ndarray                      # 时间轴 (s)
    platform: TriaxialChannels = field(default_factory=TriaxialChannels)   # 六轴平台 (基准)
    r_point: TriaxialChannels = field(default_factory=TriaxialChannels)    # 臀部 R-point (座垫)
    t8: TriaxialChannels = field(default_factory=TriaxialChannels)         # 靠背 T8
    fs: float = 1000.0                    # 采样率 (Hz)
    condition_label: str = ''             # 工况标签
    quality: Optional[DataQuality] = None # 数据质量
    metadata: Dict = field(default_factory=dict)  # 额外元数据

    @property
    def duration(self) -> float:
        return float(self.time[-1] - self.time[0]) if len(self.time) > 1 else 0.0

    @property
    def n_channels(self) -> int:
        return 9  # 3 locations x 3 axes

    @property
    def n_samples(self) -> int:
        return len(self.time)


@dataclass
class FrequencyWeightingConfig:
    """频率加权滤波器配置"""
    fs: float = 1000.0
    highpass_cutoff: float = 0.4         # 高通截止 (Hz)
    lowpass_cutoff: float = 100.0        # 低通截止 (Hz)
    filter_order: int = 4                # 滤波器阶数


@dataclass
class WeightedTriaxial:
    """频率加权后的三轴信号"""
    x: np.ndarray = field(default_factory=lambda: np.array([]))
    y: np.ndarray = field(default_factory=lambda: np.array([]))
    z: np.ndarray = field(default_factory=lambda: np.array([]))
    weighting_type: str = ''             # Wk / Wd / Wc


@dataclass
class ProcessedShakerData:
    """预处理后的台架数据 (含加权信号)"""
    source: ShakerData
    time: np.ndarray

    # 原始 (去直流 + 去异常值)
    platform_raw: TriaxialChannels = field(default_factory=TriaxialChannels)
    r_point_raw: TriaxialChannels = field(default_factory=TriaxialChannels)
    t8_raw: TriaxialChannels = field(default_factory=TriaxialChannels)

    # 频率加权后
    platform_weighted: Dict[str, WeightedTriaxial] = field(default_factory=dict)
    r_point_weighted: Dict[str, WeightedTriaxial] = field(default_factory=dict)
    t8_weighted: Dict[str, WeightedTriaxial] = field(default_factory=dict)

    # 通道→加权类型映射
    channel_weighting: Dict[str, str] = field(default_factory=lambda: {
        'platform_x': 'Wd', 'platform_y': 'Wd', 'platform_z': 'Wk',
        'r_x': 'Wd', 'r_y': 'Wd', 'r_z': 'Wk',
        't8_x': 'Wc', 't8_y': 'Wd', 't8_z': 'Wk',
    })

    def get_weighted(self, location: str, axis: str) -> np.ndarray:
        """获取指定位置和轴的加权信号"""
        loc_map = {'platform': self.platform_weighted, 'r_point': self.r_point_weighted, 't8': self.t8_weighted}
        wtype = self.channel_weighting.get(f"{location}_{axis}", 'Wk')
        return loc_map[location][wtype].__getattribute__(axis)


@dataclass
class TransferResult:
    """H1 传递函数结果"""
    frequencies: np.ndarray
    magnitude: np.ndarray
    coherence: np.ndarray
    peak_freqs: List[float] = field(default_factory=list)
    peak_gains: List[float] = field(default_factory=list)
    peak_coherences: List[float] = field(default_factory=list)

    def find_peaks(self, coh_threshold: float = 0.5, min_distance_hz: float = 1.0):
        """在 γ² > coh_threshold 区域搜索峰值"""
        from scipy import signal as scipy_signal
        valid = self.coherence >= coh_threshold
        if not valid.any():
            return
        valid_mag = self.magnitude.copy()
        valid_mag[~valid] = 0
        df = float(self.frequencies[1] - self.frequencies[0])
        min_dist = int(min_distance_hz / df)
        peaks, props = scipy_signal.find_peaks(valid_mag, distance=max(1, min_dist))
        # 按增益降序排列
        order = sorted(peaks, key=lambda i: valid_mag[i], reverse=True)
        self.peak_freqs = [float(self.frequencies[i]) for i in order]
        self.peak_gains = [float(self.magnitude[i]) for i in order]
        self.peak_coherences = [float(self.coherence[i]) for i in order]


@dataclass
class PSDResult:
    """PSD 计算结果"""
    frequencies: np.ndarray
    psd: np.ndarray
    resolution: float = 0.0


@dataclass
class TimeDomainMetrics:
    """时域指标"""
    rms: float = 0.0
    vdv: float = 0.0
    peak: float = 0.0
    crest_factor: float = 0.0
    mtvv: float = 0.0    # 最大瞬态振动值 (ISO 2631-1)


@dataclass
class SEATMetrics:
    """SEAT 因子集合"""
    seat_values: Dict[str, float] = field(default_factory=dict)  # 通道名 → SEAT%
    overall: float = 0.0
    grade: str = 'N/A'
    resonance_channels: List[str] = field(default_factory=list)  # SEAT > 300% 的通道


@dataclass
class AnalysisResult:
    """单工况分析结果"""
    condition_name: str = ''
    filepath: str = ''

    # 基本信息
    fs: float = 1000.0
    duration: float = 0.0

    # SEAT 因子
    seat: SEATMetrics = field(default_factory=SEATMetrics)

    # 时域指标 (每个通道)
    time_domain: Dict[str, TimeDomainMetrics] = field(default_factory=dict)

    # 传递函数 (每个路径)
    transfer_functions: Dict[str, TransferResult] = field(default_factory=dict)

    # PSD
    psd: Dict[str, PSDResult] = field(default_factory=dict)

    # 共振汇总
    resonance_summary: Dict[str, Dict] = field(default_factory=dict)

    # 加权 RMS 矩阵
    weighted_rms: Dict[str, float] = field(default_factory=dict)

    # 数据质量
    quality: Optional[DataQuality] = None

    # 低激励通道 (平台信号 std < 0.1 → SEAT 不可靠)
    low_excitation_channels: List[str] = field(default_factory=list)

    # 专家图表 (ShakerChartGenerator 生成)
    chart_paths: Dict[str, str] = field(default_factory=dict)  # {chart_id: file_path}


@dataclass
class CrossConditionReport:
    """多工况对比分析报告"""
    conditions: List[str] = field(default_factory=list)
    seat_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)  # condition → {channel: SEAT%}
    rms_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    vdv_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    resonance_summary: Dict[str, Dict] = field(default_factory=dict)
    ranking: Dict[str, List[str]] = field(default_factory=dict)
    best_condition: str = ''
    worst_condition: str = ''
    stability: Dict[str, float] = field(default_factory=dict)  # channel → CV
    recommendations: List[str] = field(default_factory=list)