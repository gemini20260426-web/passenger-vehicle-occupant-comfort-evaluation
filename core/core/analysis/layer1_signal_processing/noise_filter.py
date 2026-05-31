#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应噪声滤波器 + 野值检测器
"""

import numpy as np
from collections import deque
from typing import Optional


class AdaptiveLowPass:
    def __init__(self, cutoff: float = 5.0, fs: float = 30.0, min_cutoff: float = 1.0, max_cutoff: float = 15.0):
        self._base_cutoff = cutoff
        self._fs = fs
        self._min_cutoff = min_cutoff
        self._max_cutoff = max_cutoff
        self._prev = None
        self._alpha = self._calc_alpha(cutoff)
        self._signal_var = 0.0
        self._noise_var = 0.0
        self._adapt_rate = 0.05

    def _calc_alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2.0 * np.pi * max(cutoff, 0.01))
        dt = 1.0 / self._fs
        return dt / (tau + dt)

    def update(self, value: float) -> float:
        if value is None:
            return self._prev if self._prev is not None else 0.0

        if self._prev is not None:
            innovation = value - self._prev
            self._signal_var = (1.0 - self._adapt_rate) * self._signal_var + self._adapt_rate * innovation ** 2
            noise_est = abs(innovation) * 0.1
            self._noise_var = (1.0 - self._adapt_rate) * self._noise_var + self._adapt_rate * noise_est ** 2

            if self._noise_var > 1e-9:
                snr = self._signal_var / self._noise_var
                adaptive_cutoff = self._base_cutoff * min(max(snr * 0.5, 0.3), 3.0)
                adaptive_cutoff = np.clip(adaptive_cutoff, self._min_cutoff, self._max_cutoff)
                self._alpha = self._calc_alpha(adaptive_cutoff)

        filtered = self._alpha * value + (1.0 - self._alpha) * (self._prev if self._prev is not None else value)
        self._prev = filtered
        return filtered

    def reset(self):
        self._prev = None
        self._signal_var = 0.0
        self._noise_var = 0.0


class MADOutlierDetector:
    def __init__(self, threshold: float = 3.5, window_size: int = 50):
        self._threshold = threshold
        self._buffer = deque(maxlen=window_size)

    def assess(self, value: float) -> bool:
        self._buffer.append(value)
        if len(self._buffer) < 10:
            return True
        arr = np.array(self._buffer)
        median = np.median(arr)
        mad = np.median(np.abs(arr - median))
        if mad < 1e-9:
            return True
        z_score = 0.6745 * (value - median) / mad
        return abs(z_score) < self._threshold

    def reset(self):
        self._buffer.clear()
