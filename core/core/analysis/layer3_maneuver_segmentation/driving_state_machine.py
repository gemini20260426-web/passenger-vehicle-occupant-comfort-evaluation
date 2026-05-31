#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶状态机 — 基于物理约束的有限状态机
"""

import time
import logging
from typing import Dict, Optional, Tuple
from ..core_types import DrivingState, ProcessedFrame, FrameFeatures


class DrivingStateMachine:
    MIN_STATE_FRAMES = 3
    MAX_STATE_DURATION = 30.0
    HYSTERESIS_TURN_ENTER = 5.0
    HYSTERESIS_TURN_EXIT = 2.0
    # 车辆加速度阈值 (m/s²) — 对齐参考算法 detector 0.5/-0.5 m/s²
    HYSTERESIS_ACCEL_ENTER = 0.5
    HYSTERESIS_ACCEL_EXIT = 0.25
    HYSTERESIS_BRAKE_ENTER = -0.5
    HYSTERESIS_BRAKE_EXIT = -0.25
    PARKING_SPEED = 0.555         # ≈ 2 km/h
    LANE_CHANGE_WHEEL = 3.0
    WHEEL_DEAD_ZONE = 2.0

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._current_state = DrivingState.UNKNOWN
        self._state_start_time = 0.0
        self._last_frame_time = 0.0
        self._state_start_index = 0
        self._frame_index = 0
        self._frames_in_current_state = 0
        self._prev_wheel = 0.0
        self._wheel_sign = 0
        self._lane_change_phase = 0
        self._dead_zone_frames = 0

    @property
    def current_state(self) -> DrivingState:
        return self._current_state

    @property
    def state_duration(self) -> float:
        if self._state_start_time == 0:
            return 0.0
        return self._last_frame_time - self._state_start_time

    def update(self, frame: ProcessedFrame, features: Optional[FrameFeatures] = None) -> Tuple[DrivingState, bool, bool]:
        self._frame_index += 1
        self._last_frame_time = frame.timestamp
        self._frames_in_current_state += 1
        speed = frame.speed
        wheel = frame.wheel
        ax = frame.vehicle_accel  # 用车辆加速度替代IMU ax

        state_changed = False
        maneuver_ended = False

        new_state = self._determine_state(speed, wheel, ax)

        if new_state != self._current_state:
            if self._frames_in_current_state >= self.MIN_STATE_FRAMES or self._current_state == DrivingState.UNKNOWN:
                if self._current_state not in (DrivingState.UNKNOWN, DrivingState.STOPPED):
                    maneuver_ended = True
                self._current_state = new_state
                self._state_start_time = frame.timestamp
                self._state_start_index = self._frame_index
                self._frames_in_current_state = 0
                state_changed = True

        self._prev_wheel = wheel
        return self._current_state, state_changed, maneuver_ended

    def _determine_state(self, speed: float, wheel: float, ax: float) -> DrivingState:
        _dbg = self._frame_index <= 20

        _reporting = (_dbg or
            self._current_state not in (
                DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT))

        if self._current_state == DrivingState.STOPPED:
            if speed >= self.PARKING_SPEED:
                pass
            else:
                if _reporting:
                    self._logger.debug(
                        f"[SM] #{self._frame_index} STOPPED: "
                        f"speed={speed:.2f}<{self.PARKING_SPEED}"
                    )
                return DrivingState.STOPPED

        if speed < self.PARKING_SPEED and abs(ax) < 0.1 and self._current_state != DrivingState.STOPPED:
            if _reporting:
                self._logger.debug(
                    f"[SM] #{self._frame_index} {self._current_state.value}→STOPPED "
                    f"low_speed speed={speed:.2f}"
                )
            return DrivingState.STOPPED

        if self._current_state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT):
            if self.state_duration >= self.MAX_STATE_DURATION:
                self._logger.info(
                    f"[SM] #{self._frame_index} 转向状态超时: {self._current_state.value} "
                    f"持续{self.state_duration:.1f}s, 强制退出→STRAIGHT_CRUISE"
                )
                return DrivingState.STRAIGHT_CRUISE

        is_turning = abs(wheel) > self.HYSTERESIS_TURN_ENTER
        was_turning = abs(self._prev_wheel) > self.HYSTERESIS_TURN_EXIT

        if self._current_state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT):
            is_turning = abs(wheel) > self.HYSTERESIS_TURN_EXIT

        in_dead_zone = abs(wheel) <= self.WHEEL_DEAD_ZONE
        if in_dead_zone:
            self._dead_zone_frames += 1
        else:
            self._dead_zone_frames = 0

        if self._current_state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT):
            if _reporting and self._frame_index % 300 == 0:
                self._logger.debug(
                    f"[SM] #{self._frame_index} cur={self._current_state.value} "
                    f"wheel={wheel:.1f} dur={self.state_duration:.1f}s"
                )

        if is_turning:
            if _reporting:
                self._logger.debug(
                    f"[SM] #{self._frame_index} →TURNING "
                    f"wheel={wheel:.1f}>{self.HYSTERESIS_TURN_EXIT}"
                )
            if wheel > 0:
                return DrivingState.TURNING_RIGHT
            else:
                return DrivingState.TURNING_LEFT

        if self._current_state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT):
            if was_turning and not in_dead_zone:
                if is_turning:
                    if wheel > 0:
                        return DrivingState.TURNING_RIGHT
                    else:
                        return DrivingState.TURNING_LEFT
                else:
                    if _reporting:
                        self._logger.info(
                            f"[SM] #{self._frame_index} was_turning exit→STRAIGHT_CRUISE"
                        )
                    return DrivingState.STRAIGHT_CRUISE
            if self._dead_zone_frames >= 3:
                if _reporting:
                    self._logger.info(
                        f"[SM] #{self._frame_index} dead_zone exit→STRAIGHT_CRUISE "
                        f"dead_frames={self._dead_zone_frames}"
                    )
                return DrivingState.STRAIGHT_CRUISE

        lc = self._detect_lane_change(speed, wheel)
        if lc is not None:
            return lc

        is_accel = ax > self.HYSTERESIS_ACCEL_ENTER
        is_brake = ax < self.HYSTERESIS_BRAKE_ENTER

        if self._current_state == DrivingState.ACCELERATING:
            is_accel = ax > self.HYSTERESIS_ACCEL_EXIT
        if self._current_state == DrivingState.BRAKING:
            is_brake = ax < self.HYSTERESIS_BRAKE_EXIT

        if is_brake:
            if _reporting:
                self._logger.debug(
                    f"[SM] #{self._frame_index} →BRAKING ax={ax:.3f}"
                )
            return DrivingState.BRAKING
        if is_accel:
            if _reporting:
                self._logger.debug(
                    f"[SM] #{self._frame_index} →ACCELERATING ax={ax:.3f}"
                )
            return DrivingState.ACCELERATING

        if _reporting and self._current_state != DrivingState.STRAIGHT_CRUISE:
            self._logger.debug(
                f"[SM] #{self._frame_index} {self._current_state.value}→STRAIGHT_CRUISE "
                f"(default) wheel={wheel:.1f} ax={ax:.3f}"
            )
        return DrivingState.STRAIGHT_CRUISE

    def _detect_lane_change(self, speed: float, wheel: float) -> Optional[DrivingState]:
        if self._current_state == DrivingState.LANE_CHANGING:
            if abs(wheel) > self.WHEEL_DEAD_ZONE:
                return DrivingState.LANE_CHANGING
            else:
                self._lane_change_phase = 0
                self._wheel_sign = 0
                return None

        if speed < self.PARKING_SPEED:
            self._lane_change_phase = 0
            self._wheel_sign = 0
            return None

        if abs(wheel) > self.LANE_CHANGE_WHEEL:
            current_sign = 1 if wheel > 0 else -1
            if self._wheel_sign != 0 and current_sign != self._wheel_sign:
                self._lane_change_phase = 2
            elif self._lane_change_phase == 0:
                self._lane_change_phase = 1
            self._wheel_sign = current_sign
        elif abs(wheel) <= self.WHEEL_DEAD_ZONE:
            self._lane_change_phase = 0
            self._wheel_sign = 0

        if self._lane_change_phase == 2:
            return DrivingState.LANE_CHANGING
        return None

    def reset(self):
        self._current_state = DrivingState.UNKNOWN
        self._state_start_time = 0.0
        self._last_frame_time = 0.0
        self._state_start_index = 0
        self._frame_index = 0
        self._frames_in_current_state = 0
        self._prev_wheel = 0.0
        self._wheel_sign = 0
        self._lane_change_phase = 0
        self._dead_zone_frames = 0
