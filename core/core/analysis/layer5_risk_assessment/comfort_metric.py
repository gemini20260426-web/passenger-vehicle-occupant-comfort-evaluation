#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舒适性指标计算器 — 基于 ISO 2631 振动剂量值
"""

import numpy as np
from typing import Dict, Optional
from ..core_types import ManeuverEvent, FrameFeatures


class ComfortMetricCalculator:
    def __init__(self):
        pass

    def calculate(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> float:
        # 从事件数据中获取jerk值
        jerk_rms = event.peak_jerk
        
        # 如果有特征数据，使用特征数据
        if features:
            feats = features.as_dict()
            feature_jerk = max(
                feats.get('ax_jerk_rms', 0),
                feats.get('ay_jerk_rms', 0),
            )
            if feature_jerk > 0:
                jerk_rms = max(jerk_rms, feature_jerk)

        comfort = 0.0
        if jerk_rms > 0.8:
            comfort += 0.2
        if jerk_rms > 1.5:
            comfort += 0.3
        if jerk_rms > 3.0:
            comfort += 0.3
            
        # 额外考虑加速度峰值
        if event.peak_ax > 2.0:
            comfort += 0.2
            
        # 额外考虑侧向加速度（针对转向事件）
        if event.peak_ay > 1.5:
            comfort += 0.15
        if event.peak_ay > 2.5:
            comfort += 0.2

        return float(np.clip(comfort, 0.0, 1.0))

    def reset(self):
        pass
