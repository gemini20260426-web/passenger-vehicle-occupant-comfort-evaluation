#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机动检测器 — 识别 maneuver 的起止边界
"""

import time
import uuid
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque
from ..core_types import (
    ManeuverEvent, ProcessedFrame, FrameFeatures,
    DrivingState, BehaviorCategory, RiskLevel
)


class ManeuverDetector:
    MIN_MANEUVER_DURATION = 0.03
    MAX_MANEUVER_DURATION = 60.0

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._active_maneuver = None
        self._maneuver_buffer = deque(maxlen=500)
        self._feature_buffer = deque(maxlen=500)
        self._maneuver_start_time = 0.0
        self._maneuver_start_idx = 0
        self._frame_idx = 0
        self._peak_ax = 0.0
        self._peak_ay = 0.0
        self._peak_jerk = 0.0
        self._speed_min = 999.0
        self._speed_max = 0.0
        self._ax_list = []
        self._ay_list = []
        self._wheel_list = []
        self._speed_list = []
        self._completed_maneuvers = deque(maxlen=200)

    def begin_maneuver(self, state: DrivingState, frame: ProcessedFrame):
        self._active_maneuver = state
        self._maneuver_start_time = frame.timestamp
        self._maneuver_start_idx = self._frame_idx
        self._maneuver_buffer.clear()
        self._feature_buffer.clear()
        self._peak_ax = 0.0
        self._peak_ay = 0.0
        self._peak_jerk = 0.0
        self._speed_min = frame.speed
        self._speed_max = frame.speed
        self._ax_list = []
        self._ay_list = []
        self._wheel_list = []
        self._speed_list = []

    def update(self, frame: ProcessedFrame, features: Optional[FrameFeatures] = None):
        self._frame_idx += 1
        if self._active_maneuver is None:
            return

        self._maneuver_buffer.append(frame)
        if features:
            self._feature_buffer.append(features)

        self._peak_ax = max(self._peak_ax, abs(frame.vehicle_accel))
        self._peak_ay = max(self._peak_ay, abs(frame.ay))
        self._speed_min = min(self._speed_min, frame.speed)
        self._speed_max = max(self._speed_max, frame.speed)
        
        self._ax_list.append(frame.vehicle_accel)
        self._ay_list.append(frame.ay)
        self._wheel_list.append(frame.wheel)
        self._speed_list.append(frame.speed)

        if features and features.kinematic:
            for key in ('ax_jerk_rms', 'ay_jerk_rms'):
                if key in features.kinematic:
                    self._peak_jerk = max(self._peak_jerk, features.kinematic[key])

    def end_maneuver(self, end_frame: ProcessedFrame) -> Optional[ManeuverEvent]:
        if self._active_maneuver is None:
            return None

        duration = end_frame.timestamp - self._maneuver_start_time
        if duration < self.MIN_MANEUVER_DURATION:
            self._active_maneuver = None
            self._maneuver_buffer.clear()
            self._feature_buffer.clear()
            return None

        # 计算机动过程中的统计特征
        import numpy as np
        ax_mean = np.mean(self._ax_list) if self._ax_list else 0.0
        wheel_max = max(map(abs, self._wheel_list)) if self._wheel_list else 0.0
        
        event = ManeuverEvent(
            id=str(uuid.uuid4())[:8],
            type=self._state_to_behavior(self._active_maneuver),
            category=self._state_to_category(self._active_maneuver),
            start_time=self._maneuver_start_time,
            end_time=end_frame.timestamp,
            duration=duration,
            peak_ax=self._peak_ax,
            peak_ay=self._peak_ay,
            peak_jerk=self._peak_jerk,
            speed_range=(self._speed_min, self._speed_max),
            confidence=0.85,
            detection_method="fsm_based",
            risk_level=RiskLevel.SAFE,
            risk_score=0.0,
            data_indices=(self._maneuver_start_idx, self._frame_idx),
        )
        
        # 保存机动过程的统计数据
        event.metadata.update({
            'ax_mean': ax_mean,
            'wheel_max': wheel_max,
            'ax_list': self._ax_list.copy(),
            'wheel_list': self._wheel_list.copy(),
            'feature_count': len(self._feature_buffer),
        })

        self._completed_maneuvers.append(event)
        self._active_maneuver = None
        self._maneuver_buffer.clear()
        self._feature_buffer.clear()
        return event

    def _state_to_behavior(self, state: DrivingState) -> str:
        mapping = {
            DrivingState.STOPPED: "stopped",
            DrivingState.STRAIGHT_CRUISE: "constant_speed",
            DrivingState.ACCELERATING: "normal_acceleration",
            DrivingState.BRAKING: "normal_deceleration",
            DrivingState.TURNING_LEFT: "tight_turn",
            DrivingState.TURNING_RIGHT: "tight_turn",
            DrivingState.LANE_CHANGING: "lane_change",
        }
        return mapping.get(state, "normal")

    def _state_to_category(self, state: DrivingState) -> BehaviorCategory:
        if state in (DrivingState.STOPPED, DrivingState.ACCELERATING, DrivingState.BRAKING, DrivingState.STRAIGHT_CRUISE):
            return BehaviorCategory.LONGITUDINAL
        if state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT, DrivingState.LANE_CHANGING):
            return BehaviorCategory.LATERAL
        return BehaviorCategory.NORMAL

    @property
    def is_active(self) -> bool:
        return self._active_maneuver is not None

    @property
    def active_state(self) -> Optional[DrivingState]:
        return self._active_maneuver

    def get_recent_maneuvers(self, count: int = 10) -> List[ManeuverEvent]:
        items = list(self._completed_maneuvers)
        return items[-count:]

    def reset(self):
        self._active_maneuver = None
        self._maneuver_buffer.clear()
        self._maneuver_start_time = 0.0
        self._maneuver_start_idx = 0
        self._frame_idx = 0
        self._peak_ax = 0.0
        self._peak_ay = 0.0
        self._peak_jerk = 0.0
        self._speed_min = 999.0
        self._speed_max = 0.0
        self._completed_maneuvers.clear()
