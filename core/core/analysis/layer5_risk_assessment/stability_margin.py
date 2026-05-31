#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稳定性裕度计算器
"""

import numpy as np
from typing import Dict, Optional
from ..core_types import ManeuverEvent, FrameFeatures, VehicleConfig


class StabilityMarginCalculator:
    def __init__(self, vehicle_config: Optional[VehicleConfig] = None):
        self._config = vehicle_config or VehicleConfig()

    def calculate(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> float:
        # 首先从事件元数据和峰值数据计算稳定性
        # 即使没有特征数据，也应该能计算基础稳定性
        
        # 基于侧向加速度峰值计算稳定性（调整为更合理的阈值）
        max_lateral = self._config.max_lateral_accel if hasattr(self._config, 'max_lateral_accel') else 3.5
        # 使用更平滑的衰减曲线
        normalized_ay = min(event.peak_ay / max_lateral, 1.0)
        lateral_margin = max(0.0, 1.0 - (normalized_ay ** 0.7))

        # 如果有特征数据，进一步优化
        if features:
            feats = features.as_dict()
            slip_angle = abs(feats.get('slip_angle_est', 0))
            slip_margin = max(0.0, 1.0 - slip_angle / 10.0)
            margin = min(slip_margin, lateral_margin)
        else:
            margin = lateral_margin

        return float(np.clip(margin, 0.0, 1.0))

    def reset(self):
        pass
