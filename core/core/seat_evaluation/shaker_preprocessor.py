#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
振动台架数据预处理器

实现 ISO 10326-1 §5.2.1 要求的数据调理:
  1. Hampel 异常值剔除
  2. 高通滤波去直流 (0.4 Hz)
  3. 低通抗混叠滤波 (100 Hz 或 fs/5)
  4. 频率加权 (Wk/Wd/Wc)
"""

import numpy as np
from scipy import signal
import logging

from .shaker_models import (
    ShakerData, ProcessedShakerData, TriaxialChannels,
    WeightedTriaxial, FrequencyWeightingConfig
)
from .frequency_weighting import ISO2631WeightingFilter, get_filter

logger = logging.getLogger(__name__)


class ShakerPreprocessor:
    """
    台架数据预处理器。

    管线顺序:
      原始信号 → Hampel去异常 → 高通0.4Hz → 低通100Hz → 频率加权
    """

    def __init__(self, config: FrequencyWeightingConfig = None):
        self.config = config or FrequencyWeightingConfig()
        self._filt = None

    @property
    def weighting_filter(self) -> ISO2631WeightingFilter:
        if self._filt is None:
            self._filt = get_filter(self.config.fs)
        return self._filt

    def process(self, data: ShakerData) -> ProcessedShakerData:
        """
        完整预处理管线。

        Returns:
            ProcessedShakerData: 含原始(去直流后) + 频率加权后的数据
        """
        fs = data.fs
        result = ProcessedShakerData(source=data, time=data.time.copy())

        # ═══════════════════════════════════════════
        # 对每组三轴传感器执行预处理
        # ═══════════════════════════════════════════
        for loc_name, loc_data in [('platform', data.platform),
                                     ('r_point', data.r_point),
                                     ('t8', data.t8)]:
            raw_cleaned = TriaxialChannels()
            weighted_all = {}

            for ax in ['x', 'y', 'z']:
                raw = getattr(loc_data, ax).copy()

                # Step 1: Hampel 异常值剔除
                clean = self._hampel_filter(raw, window=100, n_sigma=3)

                # Step 2: 高通滤波去直流 (4阶 @ 0.4 Hz)
                sos_hp = signal.butter(
                    self.config.filter_order,
                    self.config.highpass_cutoff,
                    'highpass',
                    fs=fs,
                    output='sos'
                )
                clean = signal.sosfiltfilt(sos_hp, clean)

                # Step 3: 低通抗混叠
                lp_cut = min(self.config.lowpass_cutoff, fs / 5.0)
                sos_lp = signal.butter(
                    self.config.filter_order,
                    lp_cut,
                    'lowpass',
                    fs=fs,
                    output='sos'
                )
                clean = signal.sosfiltfilt(sos_lp, clean)

                setattr(raw_cleaned, ax, clean)

            # 更新清理后的原始数据
            setattr(result, f'{loc_name}_raw', raw_cleaned)

            # Step 4: 频率加权 (按各轴的标准加权类型)
            for wtype in ['Wk', 'Wd', 'Wc']:
                wt = WeightedTriaxial(weighting_type=wtype)
                for ax in ['x', 'y', 'z']:
                    expected_wt = self.weighting_filter.get_weighting_for_channel(loc_name, ax)
                    if expected_wt == wtype:
                        wt_ax_data = self.weighting_filter.filter(
                            getattr(raw_cleaned, ax), wtype
                        )
                        setattr(wt, ax, wt_ax_data)
                weighted_all[wtype] = wt

            setattr(result, f'{loc_name}_weighted', weighted_all)

        return result

    def process_quick(self, data: ShakerData) -> ProcessedShakerData:
        """快速预处理: 跳过高通滤波（适用于已去直流的数据）"""
        fs = data.fs
        result = ProcessedShakerData(source=data, time=data.time.copy())

        for loc_name, loc_data in [('platform', data.platform),
                                     ('r_point', data.r_point),
                                     ('t8', data.t8)]:
            raw_cleaned = TriaxialChannels()
            weighted_all = {}

            for ax in ['x', 'y', 'z']:
                raw = getattr(loc_data, ax).copy()

                # 仅去均值和异常值
                clean = self._hampel_filter(raw, window=100, n_sigma=3)
                clean = clean - np.mean(clean)

                # 低通
                lp_cut = min(self.config.lowpass_cutoff, fs / 5.0)
                sos_lp = signal.butter(self.config.filter_order, lp_cut, 'lowpass',
                                       fs=fs, output='sos')
                clean = signal.sosfiltfilt(sos_lp, clean)

                setattr(raw_cleaned, ax, clean)

            setattr(result, f'{loc_name}_raw', raw_cleaned)

            for wtype in ['Wk', 'Wd', 'Wc']:
                wt = WeightedTriaxial(weighting_type=wtype)
                for ax in ['x', 'y', 'z']:
                    expected_wt = self.weighting_filter.get_weighting_for_channel(loc_name, ax)
                    if expected_wt == wtype:
                        wt_ax_data = self.weighting_filter.filter(
                            getattr(raw_cleaned, ax), wtype
                        )
                        setattr(wt, ax, wt_ax_data)
                weighted_all[wtype] = wt

            setattr(result, f'{loc_name}_weighted', weighted_all)

        return result

    # ══════════════════════════════════════════════════
    # 静态工具方法
    # ══════════════════════════════════════════════════

    @staticmethod
    def _hampel_filter(x: np.ndarray, window: int = 100,
                       n_sigma: float = 3.0) -> np.ndarray:
        """
        Hampel 滤波器: 将偏离局部中位数超过 n_sigma*MAD 的值替换为中位数。

        参考: Pearson, 2002, "Outliers in process modeling and identification"
        """
        y = x.copy()
        half = window // 2
        n = len(x)
        if n <= window:
            return y

        for i in range(half, n - half):
            local = x[i - half:i + half + 1]
            median = np.median(local)
            mad = np.median(np.abs(local - median))
            if mad > 0 and abs(x[i] - median) > n_sigma * 1.4826 * mad:
                y[i] = median
        return y

    @staticmethod
    def detrend_polyfit(x: np.ndarray, order: int = 1) -> np.ndarray:
        """多项式去趋势"""
        t = np.arange(len(x))
        coeffs = np.polyfit(t, x, order)
        trend = np.polyval(coeffs, t)
        return x - trend

    @staticmethod
    def detrend_highpass(x: np.ndarray, fs: float,
                         cutoff: float = 0.4, order: int = 4) -> np.ndarray:
        """高通滤波去直流"""
        sos = signal.butter(order, cutoff, 'highpass', fs=fs, output='sos')
        return signal.sosfiltfilt(sos, x)