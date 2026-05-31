#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
特征提取器 — Layer 2 编排器
"""

from typing import Dict, Optional
from ..core_types import ProcessedFrame, FrameFeatures, VehicleConfig
from .temporal_features import TemporalFeatureExtractor
from .spectral_features import SpectralFeatureExtractor
from .kinematic_features import KinematicFeatureExtractor
from .physics_features import PhysicsFeatureExtractor


class FeatureExtractor:
    IMU_CHANNELS = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
    SCALAR_CHANNELS = ['speed', 'wheel']

    def __init__(self, vehicle_config: Optional[VehicleConfig] = None):
        self._temporal = TemporalFeatureExtractor(window_size=50)
        self._spectral = SpectralFeatureExtractor(window_size=64)
        self._kinematic = KinematicFeatureExtractor(window_size=50)
        self._physics = PhysicsFeatureExtractor(vehicle_config=vehicle_config, window_size=50)

    def extract(self, frame: ProcessedFrame) -> FrameFeatures:
        temporal_feats = {}
        spectral_feats = {}
        kinematic_feats = {}

        for ch in self.IMU_CHANNELS:
            val = getattr(frame, ch, 0.0)
            temporal_feats.update(self._temporal.update(ch, val))
            spectral_feats.update(self._spectral.update(ch, val))
            kinematic_feats.update(self._kinematic.update(ch, val, frame.timestamp))

        for ch in self.SCALAR_CHANNELS:
            val = getattr(frame, ch, 0.0)
            temporal_feats.update(self._temporal.update(ch, val))
            self._physics.update(ch, val)

        for ch in self.IMU_CHANNELS:
            val = getattr(frame, ch, 0.0)
            self._physics.update(ch, val)

        physics_feats = self._physics.extract()

        return FrameFeatures(
            timestamp=frame.timestamp,
            temporal=temporal_feats,
            spectral=spectral_feats,
            kinematic=kinematic_feats,
            physics=physics_feats,
        )

    def reset(self):
        self._temporal.reset()
        self._spectral.reset()
        self._kinematic.reset()
        self._physics.reset()
