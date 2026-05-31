#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文自适应阈值 — 速度/场景感知的动态阈值
"""

from typing import Dict, Tuple
from ..core_types import ManeuverEvent, BehaviorCategory


class ContextAwareThresholds:
    SPEED_BANDS = [
        (0, 20, "low"),
        (20, 60, "medium"),
        (60, 200, "high"),
    ]

    AGGRESSIVE_ACCEL_BY_SPEED = {
        "low": 1.5,
        "medium": 2.5,
        "high": 3.5,
    }

    AGGRESSIVE_DECEL_BY_SPEED = {
        "low": -1.5,
        "medium": -2.5,
        "high": -3.5,
    }

    EMERGENCY_BRAKE_BY_SPEED = {
        "low": -2.0,
        "medium": -3.0,
        "high": -4.0,
    }

    TURN_THRESHOLD_BY_SPEED = {
        "low": 3.0,
        "medium": 5.0,
        "high": 8.0,
    }

    def __init__(self):
        pass

    def get_speed_band(self, speed: float) -> str:
        for lo, hi, band in self.SPEED_BANDS:
            if lo <= speed < hi:
                return band
        return "medium"

    def adjust(self, event: ManeuverEvent) -> Tuple[str, BehaviorCategory, float]:
        avg_speed = (event.speed_range[0] + event.speed_range[1]) / 2.0
        band = self.get_speed_band(avg_speed)

        behavior = event.type
        category = event.category
        confidence = event.confidence

        if category == BehaviorCategory.LONGITUDINAL:
            if event.peak_ax > self.AGGRESSIVE_ACCEL_BY_SPEED.get(band, 2.5):
                behavior = "aggressive_acceleration"
                confidence = max(confidence, 0.85)
            if event.peak_ax < self.EMERGENCY_BRAKE_BY_SPEED.get(band, -3.0):
                behavior = "emergency_braking"
                confidence = max(confidence, 0.95)

        return behavior, category, confidence

    def reset(self):
        pass
