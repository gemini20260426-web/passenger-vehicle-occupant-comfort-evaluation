#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运动学特征提取器 — jerk, snap 等
"""

import numpy as np
from collections import deque
from typing import Dict


class KinematicFeatureExtractor:
    def __init__(self, window_size: int = 50):
        self._window_size = window_size
        self._buffers = {}
        self._prev_values = {}
        self._prev_jerk = {}
        self._timestamps = {}

    def _init_channel(self, channel: str):
        if channel not in self._buffers:
            self._buffers[channel] = deque(maxlen=self._window_size)
            self._prev_values[channel] = None
            self._prev_jerk[channel] = None
            self._timestamps[channel] = deque(maxlen=self._window_size)

    def update(self, channel: str, value: float, timestamp: float) -> Dict[str, float]:
        self._init_channel(channel)
        self._buffers[channel].append(value)
        self._timestamps[channel].append(timestamp)

        features = {}

        if self._prev_values[channel] is not None:
            dt = timestamp - self._timestamps[channel][-2] if len(self._timestamps[channel]) >= 2 else 0.033
            # 当 dt 太小时，使用合理的默认值
            if dt <= 0:
                dt = 0.001
            if dt < 0.0001:
                dt = 0.001
            
            jerk = (value - self._prev_values[channel]) / dt
            features[f'{channel}_jerk'] = jerk

            if self._prev_jerk[channel] is not None:
                snap = (jerk - self._prev_jerk[channel]) / dt
                features[f'{channel}_snap'] = snap

            self._prev_jerk[channel] = jerk

        self._prev_values[channel] = value

        buf = self._buffers[channel]
        if len(buf) >= 5:
            arr = np.array(buf)
            if len(self._timestamps[channel]) >= 2:
                t_arr = np.array(self._timestamps[channel])
                dt_arr = np.diff(t_arr)
                # 处理 dt 太小或为零的情况
                dt_arr = np.maximum(dt_arr, 1e-6)  # 至少 1 微秒
                jerk_arr = np.diff(arr) / dt_arr
                features[f'{channel}_jerk_rms'] = float(np.sqrt(np.mean(jerk_arr ** 2)))
                features[f'{channel}_jerk_peak'] = float(np.max(np.abs(jerk_arr)))

                if len(jerk_arr) >= 2:
                    dt2 = dt_arr[1:]
                    snap_arr = np.diff(jerk_arr) / dt2
                    features[f'{channel}_snap_rms'] = float(np.sqrt(np.mean(snap_arr ** 2)))

        return features

    def reset(self):
        self._buffers.clear()
        self._prev_values.clear()
        self._prev_jerk.clear()
        self._timestamps.clear()
