#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时域特征提取器
"""

import numpy as np
from collections import deque
from typing import Dict
import warnings


class TemporalFeatureExtractor:
    def __init__(self, window_size: int = 50):
        self._window_size = window_size
        self._buffers = {}

    def _init_channel(self, channel: str):
        if channel not in self._buffers:
            self._buffers[channel] = deque(maxlen=self._window_size)

    def update(self, channel: str, value: float) -> Dict[str, float]:
        self._init_channel(channel)
        self._buffers[channel].append(value)
        buf = self._buffers[channel]

        if len(buf) < 5:
            return {}

        arr = np.array(buf)
        features = {
            f'{channel}_mean': float(np.mean(arr)),
            f'{channel}_std': float(np.std(arr)),
            f'{channel}_min': float(np.min(arr)),
            f'{channel}_max': float(np.max(arr)),
            f'{channel}_range': float(np.ptp(arr)),
            f'{channel}_rms': float(np.sqrt(np.mean(arr ** 2))),
        }

        if len(buf) >= 10:
            from scipy.stats import skew, kurtosis as scipy_kurtosis
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    features[f'{channel}_skewness'] = float(skew(arr))
                    features[f'{channel}_kurtosis'] = float(scipy_kurtosis(arr))
            except Exception:
                features[f'{channel}_skewness'] = 0.0
                features[f'{channel}_kurtosis'] = 0.0

        return features

    def reset(self):
        self._buffers.clear()
