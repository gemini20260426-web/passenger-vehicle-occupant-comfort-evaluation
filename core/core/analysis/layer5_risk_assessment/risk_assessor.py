#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险评估器 — Layer 5 编排器
"""

import logging
from typing import Optional
from ..core_types import ManeuverEvent, FrameFeatures, RiskReport, VehicleConfig
from .stability_margin import StabilityMarginCalculator
from .collision_risk import CollisionRiskEstimator
from .comfort_metric import ComfortMetricCalculator
from .composite_scorer import CompositeRiskScorer


class RiskAssessor:
    def __init__(self, vehicle_config: Optional[VehicleConfig] = None):
        self._logger = logging.getLogger(__name__)
        self._stability = StabilityMarginCalculator(vehicle_config)
        self._collision = CollisionRiskEstimator()
        self._comfort = ComfortMetricCalculator()
        self._scorer = CompositeRiskScorer()

    def assess(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> ManeuverEvent:
        stability_margin = self._stability.calculate(event, features)
        collision_risk = self._collision.estimate(event, features)
        comfort_index = self._comfort.calculate(event, features)

        report = self._scorer.score(stability_margin, collision_risk, comfort_index, features)

        event.risk_level = report.level
        event.risk_score = report.score
        event.metadata['risk_report'] = report

        return event

    def reset(self):
        self._stability.reset()
        self._collision.reset()
        self._comfort.reset()
        self._scorer.reset()
