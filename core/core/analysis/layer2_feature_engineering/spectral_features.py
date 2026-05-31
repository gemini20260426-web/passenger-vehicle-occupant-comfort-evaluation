#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
频域特征提取器
"""

import numpy as np
from collections import deque
from typing import Dict


class SpectralFeatureExtractor:
    def __init__(self, window_size: int = 64, fs: float = 30.0):
        self._window_size = window_size
        self._fs = fs
        self._buffers = {}

    def _init_channel(self, channel: str):
        if channel not in self._buffers:
            self._buffers[channel] = deque(maxlen=self._window_size)

    def update(self, channel: str, value: float) -> Dict[str, float]:
        self._init_channel(channel)
        self._buffers[channel].append(value)
        buf = self._buffers[channel]

        if len(buf) < self._window_size // 2:
            return {}

        arr = np.array(buf)
        n = len(arr)
        fft_vals = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(n, d=1.0 / self._fs)

        if len(fft_vals) == 0:
            return {}

        total_power = np.sum(fft_vals ** 2)
        if total_power < 1e-9:
            return {
                f'{channel}_dominant_freq': 0.0,
                f'{channel}_spectral_centroid': 0.0,
                f'{channel}_spectral_entropy': 0.0,
            }

        dominant_idx = np.argmax(fft_vals)
        dominant_freq = freqs[dominant_idx] if dominant_idx < len(freqs) else 0.0

        spectral_centroid = np.sum(freqs * fft_vals) / max(np.sum(fft_vals), 1e-9)

        psd_norm = fft_vals ** 2 / total_power
        psd_norm = psd_norm[psd_norm > 1e-12]
        spectral_entropy = -np.sum(psd_norm * np.log2(psd_norm))

        return {
            f'{channel}_dominant_freq': float(dominant_freq),
            f'{channel}_spectral_centroid': float(spectral_centroid),
            f'{channel}_spectral_entropy': float(spectral_entropy),
        }

    def reset(self):
        self._buffers.clear()
