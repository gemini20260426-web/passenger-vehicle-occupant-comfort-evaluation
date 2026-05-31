#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合风险评分器
"""

import numpy as np
from typing import Dict, Optional
from ..core_types import ManeuverEvent, FrameFeatures, RiskLevel, RiskReport


class CompositeRiskScorer:
    WEIGHTS = {
        'stability': 0.40,
        'collision': 0.35,
        'comfort': 0.25,
    }

    def __init__(self):
        self._speed_history = []
        self._jerk_history = []
        self._event_count = 0
        self._aggressive_event_count = 0

    def score(self, stability_margin: float, collision_risk: float, comfort_index: float, 
              features: Optional[FrameFeatures] = None) -> RiskReport:
        stability_risk = 1.0 - stability_margin

        composite = (
            self.WEIGHTS['stability'] * stability_risk +
            self.WEIGHTS['collision'] * collision_risk +
            self.WEIGHTS['comfort'] * comfort_index
        )

        score = float(np.clip(composite * 100.0, 0.0, 100.0))

        if score < 30:
            level = RiskLevel.SAFE
        elif score < 55:
            level = RiskLevel.CAUTION
        elif score < 80:
            level = RiskLevel.WARNING
        else:
            level = RiskLevel.DANGER

        # 计算燃油经济性（基于平稳驾驶）
        fuel_efficiency = self._calculate_fuel_efficiency(stability_margin, comfort_index, features)
        
        # 计算合规性评分（基于激进行为计数）
        compliance_score = self._calculate_compliance(collision_risk, comfort_index)

        return RiskReport(
            level=level,
            score=score,
            stability_margin=stability_margin,
            comfort_index=comfort_index,
            collision_risk=collision_risk,
            factors={
                'stability_risk': stability_risk,
                'collision_risk': collision_risk,
                'comfort_index': comfort_index,
                'fuel_efficiency': fuel_efficiency,
                'compliance_score': compliance_score,
            }
        )

    def _calculate_fuel_efficiency(self, stability_margin: float, comfort_index: float, 
                                    features: Optional[FrameFeatures]) -> float:
        """
        计算燃油经济性评分 (0-1)
        - 基于稳定性、舒适度和平稳驾驶
        """
        eco_base = (stability_margin + (1.0 - comfort_index)) / 2.0
        
        # 如果有特征数据，进一步优化
        if features and features.physics:
            speed_ms = features.physics.get('speed_ms', 0.0)
            accel_speed_ratio = features.physics.get('accel_speed_ratio', 0.0)
            
            # 中速行驶更省油（假设 15-25 m/s = 54-90 km/h）
            speed_factor = 1.0
            if 15.0 < speed_ms < 25.0:
                speed_factor = 1.0
            elif speed_ms < 10.0 or speed_ms > 30.0:
                speed_factor = 0.7
            
            # 加速度比率越低越省油
            accel_factor = max(0.5, 1.0 - abs(accel_speed_ratio))
            
            eco_base = eco_base * speed_factor * accel_factor
        
        return float(np.clip(eco_base, 0.0, 1.0))

    def _calculate_compliance(self, collision_risk: float, comfort_index: float) -> float:
        """
        计算合规性评分 (0-1)
        - 基于碰撞风险和舒适度
        """
        comp_base = (1.0 - collision_risk) * (1.0 - comfort_index * 0.5)
        return float(np.clip(comp_base, 0.0, 1.0))

    def reset(self):
        self._speed_history = []
        self._jerk_history = []
        self._event_count = 0
        self._aggressive_event_count = 0
