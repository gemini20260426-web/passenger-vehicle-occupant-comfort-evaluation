#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 坐标轴校正引擎
==================
对安装方向错误的 IMU 传感器进行软件层旋转补偿。

支持的校正模式:
  - none:      不校正
  - swap_xy:   绕Z轴旋转-90° (X↔Y互换)
  - y_to_z:    绕X轴旋转-90° (Y轴→Z轴, 用于重力轴错位)
  - x_to_z:    绕Y轴旋转+90° (X轴→Z轴, 用于重力轴错位)
  - custom:    自定义欧拉角 (roll, pitch, yaw)
"""

import math
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


PRESET_CORRECTIONS = {
    'none': {
        'description': '不校正',
        'matrix': (1, 0, 0, 0, 1, 0, 0, 0, 1),
    },
    'swap_xy': {
        'description': '绕Z轴旋转-90° (X↔Y互换, 用于XY轴装反)',
        'matrix': (0, 1, 0, -1, 0, 0, 0, 0, 1),
    },
    'y_to_z': {
        'description': '绕X轴旋转-90° (Y→Z, 用于重力轴在Y的情况)',
        'matrix': (1, 0, 0, 0, 0, 1, 0, -1, 0),
    },
    'x_to_z': {
        'description': '绕Y轴旋转+90° (X→Z, 用于重力轴在X的情况)',
        'matrix': (0, 0, -1, 0, 1, 0, 1, 0, 0),
    },
}


def apply_rotation(ax: float, ay: float, az: float,
                   m00: float, m01: float, m02: float,
                   m10: float, m11: float, m12: float,
                   m20: float, m21: float, m22: float) -> Tuple[float, float, float]:
    ax_new = m00 * ax + m01 * ay + m02 * az
    ay_new = m10 * ax + m11 * ay + m12 * az
    az_new = m20 * ax + m21 * ay + m22 * az
    return ax_new, ay_new, az_new


def build_rotation_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float
                          ) -> Tuple[float, ...]:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)

    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    m00 = cy * cp
    m01 = cy * sp * sr - sy * cr
    m02 = cy * sp * cr + sy * sr
    m10 = sy * cp
    m11 = sy * sp * sr + cy * cr
    m12 = sy * sp * cr - cy * sr
    m20 = -sp
    m21 = cp * sr
    m22 = cp * cr

    return (m00, m01, m02, m10, m11, m12, m20, m21, m22)


class AxisCorrectionEngine:

    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        self._enabled = self._config.get('enabled', False)
        self._channel_matrices: Dict[str, Tuple[float, ...]] = {}
        self._build_matrices()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _build_matrices(self):
        channels = self._config.get('channels', {})
        for ch, ch_cfg in channels.items():
            preset = ch_cfg.get('preset', 'none')
            if preset == 'custom':
                roll = ch_cfg.get('roll', 0)
                pitch = ch_cfg.get('pitch', 0)
                yaw = ch_cfg.get('yaw', 0)
                self._channel_matrices[ch] = build_rotation_matrix(roll, pitch, yaw)
            elif preset in PRESET_CORRECTIONS:
                self._channel_matrices[ch] = PRESET_CORRECTIONS[preset]['matrix']
            else:
                self._channel_matrices[ch] = PRESET_CORRECTIONS['none']['matrix']

    def correct(self, channel: str, ax: float, ay: float, az: float
                ) -> Tuple[float, float, float]:
        if not self._enabled:
            return ax, ay, az

        matrix = self._channel_matrices.get(channel)
        if matrix is None or matrix == PRESET_CORRECTIONS['none']['matrix']:
            return ax, ay, az

        return apply_rotation(ax, ay, az, *matrix)

    def correct_record(self, record: Dict) -> Dict:
        if not self._enabled:
            return record

        channel = record.get('channel', '')
        matrix = self._channel_matrices.get(channel)
        if matrix is None or matrix == PRESET_CORRECTIONS['none']['matrix']:
            return record

        ax = record.get('Ax_m_s2', 0)
        ay = record.get('Ay_m_s2', 0)
        az = record.get('Az_m_s2', 0)
        gx = record.get('Gx_dps', 0)
        gy = record.get('Gy_dps', 0)
        gz = record.get('Gz_dps', 0)

        ax_new, ay_new, az_new = apply_rotation(ax, ay, az, *matrix)
        gx_new, gy_new, gz_new = apply_rotation(gx, gy, gz, *matrix)

        record['Ax_m_s2'] = round(ax_new, 4)
        record['Ay_m_s2'] = round(ay_new, 4)
        record['Az_m_s2'] = round(az_new, 4)
        record['Gx_dps'] = round(gx_new, 4)
        record['Gy_dps'] = round(gy_new, 4)
        record['Gz_dps'] = round(gz_new, 4)

        return record

    @staticmethod
    def from_config(config: Optional[Dict]) -> 'AxisCorrectionEngine':
        return AxisCorrectionEngine(config)

    @staticmethod
    def get_preset_info() -> Dict[str, str]:
        return {k: v['description'] for k, v in PRESET_CORRECTIONS.items()}