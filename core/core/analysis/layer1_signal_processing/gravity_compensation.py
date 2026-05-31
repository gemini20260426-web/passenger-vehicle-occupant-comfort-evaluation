#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重力补偿 — 利用陀螺仪估计姿态，从加速度中分离重力分量
"""

import numpy as np


class GravityCompensator:
    GRAVITY = 9.8

    def __init__(self):
        self._roll = 0.0
        self._pitch = 0.0
        self._last_time = None
        self._initialized = False

    def compensate(self, data: dict) -> dict:
        gx = data.get('gx', 0.0) or 0.0
        gy = data.get('gy', 0.0) or 0.0
        gz = data.get('gz', 0.0) or 0.0
        ts = data.get('timestamp', 0.0)

        if self._last_time is not None:
            dt = ts - self._last_time
            if 0 < dt < 1.0:
                self._roll += gx * dt
                self._pitch += gy * dt

        self._last_time = ts
        self._initialized = True

        cr = np.cos(self._roll)
        sr = np.sin(self._roll)
        cp = np.cos(self._pitch)
        sp = np.sin(self._pitch)

        gx_body = -self.GRAVITY * sp
        gy_body = self.GRAVITY * cp * sr
        gz_body = self.GRAVITY * cp * cr

        result = dict(data)
        result['ax'] = (data.get('ax', 0.0) or 0.0) - gx_body
        result['ay'] = (data.get('ay', 0.0) or 0.0) - gy_body
        result['az'] = (data.get('az', 0.0) or 0.0) - gz_body
        return result

    def reset(self):
        self._roll = 0.0
        self._pitch = 0.0
        self._last_time = None
        self._initialized = False
