#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号处理器 — Layer 1 编排器
"""

import time
from typing import Dict, Any, Optional
from ..core_types import ProcessedFrame, SignalQuality, VehicleConfig
from .noise_filter import AdaptiveLowPass, MADOutlierDetector
from .calibration import SensorCalibrator
from .gravity_compensation import GravityCompensator
from .quality_assessor import SignalQualityAssessor


class SignalProcessor:
    IMU_CHANNELS = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
    SCALAR_CHANNELS = ['speed', 'wheel', 'loc1', 'loc2']

    def __init__(self, vehicle_config: Optional[VehicleConfig] = None):
        self._vehicle_config = vehicle_config or VehicleConfig()

        self._filters = {
            ch: AdaptiveLowPass(cutoff=5.0) for ch in self.IMU_CHANNELS[:3]
        }
        self._filters.update({
            ch: AdaptiveLowPass(cutoff=10.0) for ch in self.IMU_CHANNELS[3:]
        })

        self._calibrator = SensorCalibrator(warmup_samples=100)
        self._gravity = GravityCompensator()
        self._quality = SignalQualityAssessor()
        self._outlier_detectors = {
            ch: MADOutlierDetector(threshold=3.5) for ch in self.IMU_CHANNELS
        }

    def process(self, raw_data: Dict[str, Any]) -> ProcessedFrame:
        ts = raw_data.get('timestamp', time.time())

        cleaned = {}
        for ch in self.IMU_CHANNELS:
            val = raw_data.get(ch, 0.0)
            if val is None:
                val = 0.0
            cleaned[ch] = val

        cleaned = self._gravity.compensate(cleaned)

        for ch in self.IMU_CHANNELS:
            cleaned[ch] = self._calibrator.update(ch, cleaned[ch])
            cleaned[ch] = self._filters[ch].update(cleaned[ch])

        quality_map = {}
        for ch in self.IMU_CHANNELS:
            is_ok = self._outlier_detectors[ch].assess(cleaned[ch])
            q = self._quality.assess(ch, cleaned[ch])
            if not is_ok:
                q.is_valid = False
                q.flags.append("outlier")
            quality_map[ch] = q

        frame = ProcessedFrame(
            timestamp=ts,
            ax=cleaned.get('ax', 0.0),
            ay=cleaned.get('ay', 0.0),
            az=cleaned.get('az', 0.0),
            gx=cleaned.get('gx', 0.0),
            gy=cleaned.get('gy', 0.0),
            gz=cleaned.get('gz', 0.0),
            speed=raw_data.get('speed', 0.0) or 0.0,
            wheel=raw_data.get('wheel', 0.0) or 0.0,
            vehicle_accel=raw_data.get('vehicle_accel', 0.0) or 0.0,
            steer_rate=raw_data.get('steer_rate', 0.0) or 0.0,
            loc1=raw_data.get('loc1', 0.0) or 0.0,
            loc2=raw_data.get('loc2', 0.0) or 0.0,
            quality=quality_map,
            raw=raw_data,
        )
        return frame

    def reset(self):
        for f in self._filters.values():
            f.reset()
        self._calibrator.reset()
        self._gravity.reset()
        for d in self._outlier_detectors.values():
            d.reset()
