#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合行为分类器 — Layer 4 编排器
"""

import logging
from typing import Optional, Tuple
from ..core_types import ManeuverEvent, FrameFeatures, BehaviorCategory
from .rule_engine import PhysicsRuleEngine
from .statistical_classifier import StatisticalClassifier
from .context_aware_thresholds import ContextAwareThresholds
from .multi_behavior_resolver import MultiBehaviorResolver


class HybridBehaviorClassifier:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._rule_engine = PhysicsRuleEngine()
        self._statistical = StatisticalClassifier()
        self._context = ContextAwareThresholds()
        self._resolver = MultiBehaviorResolver()

    def classify(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> ManeuverEvent:
        candidates = []

        rule_result = self._rule_engine.classify(event, features)
        candidates.append(rule_result)

        stat_result = self._statistical.classify(event, features)
        candidates.append(stat_result)

        ctx_result = self._context.adjust(event)
        candidates.append(ctx_result)

        final_behavior, final_category, final_confidence = self._resolver.resolve(candidates)

        event.type = final_behavior
        event.category = final_category
        event.confidence = final_confidence
        event.detection_method = "hybrid"

        return event

    def reset(self):
        self._rule_engine.reset()
        self._statistical.reset()
        self._context.reset()
        self._resolver.reset()
