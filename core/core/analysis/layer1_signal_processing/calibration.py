#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传感器校准与偏置补偿
"""

import numpy as np
from collections import deque


class SensorCalibrator:
    def __init__(self, warmup_samples: int = 100):
        self._warmup_samples = warmup_samples
        self._bias = {}
        self._scale = {}
        self._warmup_buffers = {}
        self._calibrated = False

    def _init_channel(self, channel: str):
        if channel not in self._warmup_buffers:
            self._warmup_buffers[channel] = deque(maxlen=self._warmup_samples)
            self._bias[channel] = 0.0
            self._scale[channel] = 1.0

    def update(self, channel: str, value: float) -> float:
        self._init_channel(channel)

        if not self._calibrated:
            self._warmup_buffers[channel].append(value)
            if all(len(buf) >= self._warmup_samples for buf in self._warmup_buffers.values()):
                self._finish_calibration()
            return value

        return (value - self._bias.get(channel, 0.0)) * self._scale.get(channel, 1.0)

    def _finish_calibration(self):
        for channel, buf in self._warmup_buffers.items():
            arr = np.array(buf)
            self._bias[channel] = float(np.mean(arr))
            std = float(np.std(arr))
            if std > 1e-6:
                self._scale[channel] = 1.0
        self._calibrated = True
        self._warmup_buffers.clear()

    def is_calibrated(self) -> bool:
        return self._calibrated

    def reset(self):
        self._bias = {}
        self._scale = {}
        self._warmup_buffers = {}
        self._calibrated = False
