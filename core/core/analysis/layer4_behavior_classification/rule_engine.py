#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物理规则引擎 — 基于车辆动力学原理的可解释规则
"""

import numpy as np
from typing import Dict, Optional, Tuple
from collections import deque
from ..core_types import ManeuverEvent, FrameFeatures, BehaviorCategory


class PhysicsRuleEngine:
    EMERGENCY_BRAKE_AX = -2.5
    AGGRESSIVE_ACCEL_AX = 1.8
    AGGRESSIVE_DECEL_AX = -1.8
    AGGRESSIVE_JERK = 2.0
    U_TURN_WHEEL = 15.0
    U_TURN_DURATION_MIN = 2.0
    WEAVING_DIRECTION_CHANGES = 3
    WEAVING_WINDOW = 30
    RAPID_DIR_CHANGE_RATE = 30.0
    SKID_LATERAL_RATIO = 0.7
    SEVERE_BUMP_AZ_THRESHOLD = 2.5
    SEVERE_BUMP_JERK_THRESHOLD = 15.0
    LANE_CHANGE_WHEEL = 3.0

    def __init__(self):
        self._wheel_history = deque(maxlen=100)
        self._wheel_sign_changes = 0
        self._wheel_change_times = deque(maxlen=50)
        self._wheel_sign_changes_in_window = 0

    def classify(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> Tuple[str, BehaviorCategory, float]:
        behavior = event.type
        category = event.category
        confidence = event.confidence

        meta = event.metadata
        ax_mean = meta.get('ax_mean', 0.0)
        wheel_max = meta.get('wheel_max', 0.0)

        all_feats = {}
        if features:
            all_feats = features.as_dict()

        all_feats.setdefault('ax_mean', ax_mean)
        all_feats.setdefault('wheel_max', wheel_max)

        refined = self._refine_longitudinal(event, all_feats)
        if refined:
            composite = self._check_composite_for_non_lateral(refined, event, all_feats)
            return composite if composite else refined

        refined = self._refine_lateral(event, all_feats)
        if refined:
            composite = self._check_composite_for_lateral(refined, event, all_feats)
            return composite if composite else refined

        refined = self._detect_composite(event, all_feats)
        if refined:
            return refined

        refined = self._detect_anomaly(event, all_feats)
        if refined:
            return refined

        return behavior, category, confidence

    def _refine_longitudinal(self, event: ManeuverEvent, feats: Dict[str, float]) -> Optional[Tuple[str, BehaviorCategory, float]]:
        peak_ax = event.peak_ax
        peak_jerk = event.peak_jerk

        if event.type in ("normal_deceleration", "braking"):
            if abs(peak_ax) >= abs(self.EMERGENCY_BRAKE_AX):
                return ("emergency_braking", BehaviorCategory.LONGITUDINAL, 0.95)
            if abs(peak_ax) >= abs(self.AGGRESSIVE_DECEL_AX):
                return ("aggressive_deceleration", BehaviorCategory.LONGITUDINAL, 0.85)
            return ("normal_deceleration", BehaviorCategory.LONGITUDINAL, 0.80)

        if event.type in ("normal_acceleration", "accelerating"):
            if peak_ax >= self.AGGRESSIVE_ACCEL_AX:
                return ("aggressive_acceleration", BehaviorCategory.LONGITUDINAL, 0.85)
            return ("normal_acceleration", BehaviorCategory.LONGITUDINAL, 0.80)

        if event.type == "stopped":
            return ("stopped", BehaviorCategory.LONGITUDINAL, 0.90)

        if event.type == "constant_speed":
            return ("constant_speed", BehaviorCategory.LONGITUDINAL, 0.80)

        return None

    def _refine_lateral(self, event: ManeuverEvent, feats: Dict[str, float]) -> Optional[Tuple[str, BehaviorCategory, float]]:
        if event.type == "tight_turn":
            wheel_max = feats.get('wheel_max', 0) or event.metadata.get('wheel_max', 0)
            if abs(wheel_max) > self.U_TURN_WHEEL and event.duration > self.U_TURN_DURATION_MIN:
                return ("u_turn", BehaviorCategory.LATERAL, 0.90)
            turn_radius = feats.get('turn_radius', 999)
            if abs(turn_radius) < 20 or abs(wheel_max) > 5.0:
                return ("tight_turn", BehaviorCategory.LATERAL, 0.85)
            return ("wide_turn", BehaviorCategory.LATERAL, 0.80)

        if event.type == "lane_change":
            return self._detect_weaving(event, feats)

        return None

    def _detect_weaving(self, event: ManeuverEvent, feats: Dict[str, float]) -> Tuple[str, BehaviorCategory, float]:
        direction_changes = self._count_direction_changes(event)

        if direction_changes >= self.WEAVING_DIRECTION_CHANGES:
            return ("weaving", BehaviorCategory.LATERAL, 0.88)
        elif direction_changes >= 2:
            return ("weaving", BehaviorCategory.LATERAL, 0.75)
        else:
            return ("lane_change", BehaviorCategory.LATERAL, 0.78)

    def _count_direction_changes(self, event: ManeuverEvent) -> int:
        wheel_list = event.metadata.get('wheel_list', [])
        if not wheel_list:
            return 0

        changes = 0
        prev_sign = 0

        for v in wheel_list:
            s = 1 if v > self.LANE_CHANGE_WHEEL else (-1 if v < -self.LANE_CHANGE_WHEEL else 0)
            if s != 0 and s != prev_sign:
                changes += 1
                prev_sign = s

        return max(0, changes - 1)

    def _check_composite_for_lateral(
        self,
        lateral_result: Tuple[str, BehaviorCategory, float],
        event: ManeuverEvent,
        feats: Dict[str, float]
    ) -> Optional[Tuple[str, BehaviorCategory, float]]:
        """检查横向事件是否实际为复合事件（弯道加速/减速）"""
        ax_mean = feats.get('ax_mean', 0)

        if ax_mean > 0.15:
            return ("cornering_acceleration", BehaviorCategory.COMPOSITE, 0.82)
        if ax_mean < -0.15:
            return ("cornering_deceleration", BehaviorCategory.COMPOSITE, 0.82)

        wheel_rate = feats.get('wheel_jerk', 0)
        if abs(wheel_rate) > self.RAPID_DIR_CHANGE_RATE:
            return ("rapid_direction_change", BehaviorCategory.COMPOSITE, 0.85)

        return None

    def _check_composite_for_non_lateral(
        self,
        longitudinal_result: Tuple[str, BehaviorCategory, float],
        event: ManeuverEvent,
        feats: Dict[str, float]
    ) -> Optional[Tuple[str, BehaviorCategory, float]]:
        """检查纵向事件是否实际为复合事件"""
        wheel_range = feats.get('wheel_range', 0)

        if abs(wheel_range) > 5.0:
            behavior = longitudinal_result[0]
            if behavior in ("aggressive_acceleration", "normal_acceleration"):
                return ("cornering_acceleration", BehaviorCategory.COMPOSITE, 0.80)
            if behavior in ("aggressive_deceleration", "emergency_braking", "normal_deceleration"):
                return ("cornering_deceleration", BehaviorCategory.COMPOSITE, 0.80)

        return None

    def _detect_composite(self, event: ManeuverEvent, feats: Dict[str, float]) -> Optional[Tuple[str, BehaviorCategory, float]]:
        wheel_range = feats.get('wheel_range', 0)
        ax_mean = feats.get('ax_mean', 0)

        if abs(wheel_range) > 5.0:
            if ax_mean > 0.15:
                return ("cornering_acceleration", BehaviorCategory.COMPOSITE, 0.78)
            if ax_mean < -0.15:
                return ("cornering_deceleration", BehaviorCategory.COMPOSITE, 0.78)

        wheel_rate = feats.get('wheel_jerk', 0)
        if abs(wheel_rate) > self.RAPID_DIR_CHANGE_RATE:
            return ("rapid_direction_change", BehaviorCategory.COMPOSITE, 0.85)

        return None

    def _detect_anomaly(self, event: ManeuverEvent, feats: Dict[str, float]) -> Optional[Tuple[str, BehaviorCategory, float]]:
        lateral_ratio = feats.get('lateral_accel_ratio', 0)
        slip_angle = feats.get('slip_angle_est', 0)

        if abs(lateral_ratio) > self.SKID_LATERAL_RATIO and abs(slip_angle) > 5.0:
            return ("skid_risk", BehaviorCategory.ANOMALY, 0.80)

        ay_peak = event.peak_ay
        if ay_peak > 4.0:
            return ("rollover_risk", BehaviorCategory.ANOMALY, 0.75)

        refined = self._detect_severe_bump(event, feats)
        if refined:
            return refined

        return None

    def _detect_severe_bump(self, event: ManeuverEvent, feats: Dict[str, float]) -> Optional[Tuple[str, BehaviorCategory, float]]:
        az_peak = feats.get('az_peak', 0)
        az_mean = feats.get('az_mean', 0)
        az_std = feats.get('az_std', 0)
        jerk_z = feats.get('jerk_z', 0)
        peak_jerk = event.peak_jerk

        if abs(az_peak) > self.SEVERE_BUMP_AZ_THRESHOLD:
            return ("severe_bump", BehaviorCategory.ANOMALY, 0.82)

        if peak_jerk > self.SEVERE_BUMP_JERK_THRESHOLD and abs(az_std) > 0.8:
            return ("severe_bump", BehaviorCategory.ANOMALY, 0.78)

        if abs(az_mean) > 1.5 and abs(jerk_z) > 10.0:
            return ("severe_bump", BehaviorCategory.ANOMALY, 0.75)

        return None

    def reset(self):
        self._wheel_history = deque(maxlen=100)
        self._wheel_sign_changes = 0
        self._wheel_change_times = deque(maxlen=50)
        self._wheel_sign_changes_in_window = 0