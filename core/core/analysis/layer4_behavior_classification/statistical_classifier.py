#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分类器 — 基于特征分布的模糊边界分类
"""

import numpy as np
from typing import Dict, Optional, Tuple
from ..core_types import ManeuverEvent, FrameFeatures, BehaviorCategory


class StatisticalClassifier:
    def __init__(self):
        pass

    def classify(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> Tuple[str, BehaviorCategory, float]:
        if features is None:
            return event.type, event.category, event.confidence

        all_feats = features.as_dict()

        ax_std = all_feats.get('ax_std', 0)
        ax_skew = all_feats.get('ax_skewness', 0)
        ax_kurt = all_feats.get('ax_kurtosis', 0)
        wheel_std = all_feats.get('wheel_std', 0)

        if event.category == BehaviorCategory.LONGITUDINAL:
            confidence = self._longitudinal_confidence(ax_std, ax_skew, ax_kurt)
            return event.type, event.category, confidence

        if event.category == BehaviorCategory.LATERAL:
            confidence = self._lateral_confidence(wheel_std)
            return event.type, event.category, confidence

        return event.type, event.category, event.confidence

    def _longitudinal_confidence(self, ax_std: float, ax_skew: float, ax_kurt: float) -> float:
        base = 0.75
        if ax_std > 0.5:
            base += 0.10
        if abs(ax_skew) > 0.5:
            base += 0.05
        if ax_kurt > 3.0:
            base += 0.05
        return min(base, 0.95)

    def _lateral_confidence(self, wheel_std: float) -> float:
        base = 0.75
        if wheel_std > 3.0:
            base += 0.10
        if wheel_std > 8.0:
            base += 0.05
        return min(base, 0.95)

    def reset(self):
        pass
