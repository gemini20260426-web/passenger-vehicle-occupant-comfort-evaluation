#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
碰撞风险评估器
"""

import numpy as np
from typing import Dict, Optional
from ..core_types import ManeuverEvent, FrameFeatures


class CollisionRiskEstimator:
    def __init__(self):
        pass

    def estimate(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> float:
        # 从事件元数据获取值，或者使用默认值
        meta = event.metadata
        ax_mean = meta.get('ax_mean', 0.0)
        speed_range = event.speed_range
        speed_ms = (speed_range[0] + speed_range[1]) / 2 if speed_range else 0.0
        
        # 如果有特征数据，使用特征数据覆盖
        if features:
            feats = features.as_dict()
            speed_ms = feats.get('speed_ms', speed_ms)
            ax_mean = feats.get('ax_mean', ax_mean)

        risk = 0.0
        
        # 基于平均减速度评估风险
        if ax_mean < -1.5:
            risk += 0.25
        if ax_mean < -2.5:
            risk += 0.3
        if ax_mean < -3.5:
            risk += 0.25

        # 基于速度评估额外风险
        if speed_ms > 15 and ax_mean < -1.0:
            risk += 0.2

        return float(np.clip(risk, 0.0, 1.0))

    def reset(self):
        pass
