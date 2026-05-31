#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物理衍生特征提取器 — 基于车辆动力学模型
"""

import numpy as np
from collections import deque
from typing import Dict, Optional
from ..core_types import VehicleConfig


class PhysicsFeatureExtractor:
    def __init__(self, vehicle_config: Optional[VehicleConfig] = None, window_size: int = 50):
        self._config = vehicle_config or VehicleConfig()
        self._window_size = window_size
        self._buffers = {}

    def _init_channel(self, channel: str):
        if channel not in self._buffers:
            self._buffers[channel] = deque(maxlen=self._window_size)

    def update(self, channel: str, value: float) -> None:
        self._init_channel(channel)
        self._buffers[channel].append(value)

    def extract(self) -> Dict[str, float]:
        features = {}

        speed_buf = self._buffers.get('speed', deque(maxlen=1))
        wheel_buf = self._buffers.get('wheel', deque(maxlen=1))
        gz_buf = self._buffers.get('gz', deque(maxlen=1))
        ay_buf = self._buffers.get('ay', deque(maxlen=1))
        ax_buf = self._buffers.get('ax', deque(maxlen=1))

        speed = float(np.mean(speed_buf)) if speed_buf else 0.0
        wheel = float(np.mean(wheel_buf)) if wheel_buf else 0.0
        gz = float(np.mean(gz_buf)) if gz_buf else 0.0
        ay = float(np.mean(ay_buf)) if ay_buf else 0.0
        ax = float(np.mean(ax_buf)) if ax_buf else 0.0

        speed_ms = speed / 3.6 if speed > 0.1 else 0.0

        if abs(wheel) > 0.5 and speed_ms > 0.5:
            steer_rad = np.radians(wheel) / self._config.steering_ratio
            tan_steer = np.tan(steer_rad)
            if abs(tan_steer) > 1e-6:
                turn_radius = self._config.wheelbase / tan_steer
                features['turn_radius'] = float(turn_radius)
                expected_yaw = speed_ms / turn_radius
                features['expected_yaw_rate'] = float(expected_yaw)
                features['yaw_rate_error'] = float(gz - expected_yaw)

        if speed_ms > 0.5:
            features['lateral_accel_ratio'] = float(ay / (speed_ms * max(abs(gz), 0.01)))
            features['speed_ms'] = float(speed_ms)

        if abs(ay) > 0.1 and speed_ms > 0.5:
            slip_angle = np.arctan2(ay, speed_ms * max(abs(gz), 0.01))
            features['slip_angle_est'] = float(np.degrees(slip_angle))

        if speed > 0.1:
            features['accel_speed_ratio'] = float(ax / speed)

        return features

    def reset(self):
        self._buffers.clear()
