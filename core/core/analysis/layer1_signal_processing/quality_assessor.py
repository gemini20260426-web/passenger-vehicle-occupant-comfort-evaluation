#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号质量评估器
"""

import numpy as np
from collections import deque
from ..core_types import SignalQuality


class SignalQualityAssessor:
    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._buffers = {}
        self._dropout_counters = {}
        self._saturation_counters = {}
        self._saturation_limits = {
            'ax': 16.0, 'ay': 16.0, 'az': 16.0,
            'gx': 2000.0, 'gy': 2000.0, 'gz': 2000.0,
        }

    def _init_channel(self, channel: str):
        if channel not in self._buffers:
            self._buffers[channel] = deque(maxlen=self._window_size)
            self._dropout_counters[channel] = 0
            self._saturation_counters[channel] = 0

    def assess(self, channel: str, value: float) -> SignalQuality:
        self._init_channel(channel)
        quality = SignalQuality(channel=channel, is_valid=True)

        if value is None:
            quality.is_valid = False
            quality.flags.append("null_value")
            self._dropout_counters[channel] += 1
            quality.dropout_count = self._dropout_counters[channel]
            return quality

        sat_limit = self._saturation_limits.get(channel, 100.0)
        if abs(value) >= sat_limit * 0.95:
            quality.is_valid = False
            quality.flags.append("saturation")
            self._saturation_counters[channel] += 1
            quality.saturation_count = self._saturation_counters[channel]

        self._buffers[channel].append(value)
        buf = self._buffers[channel]

        if len(buf) >= 10:
            arr = np.array(buf)
            signal_power = np.var(arr)
            if signal_power > 1e-9:
                diff = np.diff(arr)
                noise_power = np.var(diff) / 2.0
                quality.snr = signal_power / max(noise_power, 1e-9)

        return quality
