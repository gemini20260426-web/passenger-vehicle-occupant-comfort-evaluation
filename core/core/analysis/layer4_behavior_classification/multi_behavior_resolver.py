#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多行为共存消解器
"""

from typing import Dict, List, Tuple
from ..core_types import ManeuverEvent, BehaviorCategory


class MultiBehaviorResolver:
    PRIORITY = {
        "emergency_braking": 100,
        "severe_bump": 97,
        "skid_risk": 95,
        "rollover_risk": 94,
        "u_turn": 90,
        "rapid_direction_change": 85,
        "aggressive_acceleration": 80,
        "aggressive_deceleration": 80,
        "weaving": 75,
        "cornering_braking": 70,
        "cornering_acceleration": 65,
        "cornering_deceleration": 65,
        "lane_change": 60,
        "tight_turn": 55,
        "wide_turn": 50,
        "normal_acceleration": 40,
        "normal_deceleration": 40,
        "launch": 35,
        "constant_speed": 30,
        "stopped": 20,
        "normal": 0,
    }

    def __init__(self):
        pass

    def resolve(self, candidates: List[Tuple[str, BehaviorCategory, float]]) -> Tuple[str, BehaviorCategory, float]:
        if not candidates:
            return ("normal", BehaviorCategory.NORMAL, 0.5)

        if len(candidates) == 1:
            return candidates[0]

        sorted_candidates = sorted(candidates, key=lambda x: self.PRIORITY.get(x[0], 0), reverse=True)
        primary = sorted_candidates[0]

        return primary

    def reset(self):
        pass
