#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合成训练数据生成器 — 为 23 类驾驶行为生成带标签的 55 维特征样本

设计原则:
  - 每类 300-500 个样本，总计 ~8000-10000 样本
  - 基于驾驶行为领域知识设定特征分布参数
  - 每类内加入高斯噪声，确保类内多样性
  - 类间特征分布有明显区分度，便于 LightGBM 学习

用法:
    python -m core.core.analysis.generate_synthetic_data
"""

import numpy as np
import logging
from typing import Dict, List, Tuple
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('synth_data')

# ── 从 core_types 导入完整类型定义 ──
from core.core.analysis.core_types import BEHAVIOR_TYPES_V2, BEHAVIOR_TAXONOMY

# ── 55 维特征名 (与 FeatureAdapter 一致) ──
FEATURE_NAMES = [
    # 时域 (20)
    'ax_mean', 'ax_std', 'ax_min', 'ax_max', 'ax_rms',
    'ax_skewness', 'ax_kurtosis',
    'ay_mean', 'ay_std', 'ay_rms', 'ay_skewness',
    'az_mean', 'az_std', 'az_rms',
    'speed_mean', 'speed_std', 'speed_range',
    'wheel_std', 'wheel_range', 'wheel_rms',
    # 频域 (15)
    'ax_dominant_freq', 'ax_spectral_centroid', 'ax_spectral_entropy',
    'ay_dominant_freq', 'ay_spectral_centroid', 'ay_spectral_entropy',
    'az_dominant_freq', 'az_spectral_centroid', 'az_spectral_entropy',
    'speed_dominant_freq', 'speed_spectral_centroid',
    'wheel_dominant_freq', 'wheel_spectral_centroid',
    'gz_dominant_freq', 'gz_spectral_centroid',
    # 运动学 (12)
    'ax_jerk', 'ax_snap', 'ay_jerk', 'ay_snap',
    'az_jerk', 'az_snap', 'speed_jerk', 'speed_snap',
    'wheel_jerk', 'wheel_snap', 'gz_jerk', 'gz_snap',
    # 物理 (8)
    'turn_radius', 'expected_yaw_rate', 'yaw_rate_error',
    'lateral_accel_ratio', 'speed_ms', 'slip_angle_est',
    'accel_speed_ratio', 'roll_est',
]

assert len(FEATURE_NAMES) == 55, f"特征维度应为55，实际{len(FEATURE_NAMES)}"


# ═══════════════════════════════════════════════════════════
#  每类行为的特征分布参数 (mean, std) — 基于领域知识
# ═══════════════════════════════════════════════════════════

def _base_vector() -> Dict[str, float]:
    """正常行驶的基线特征值"""
    return {
        'ax_mean': 0.0, 'ax_std': 0.1, 'ax_min': -0.3, 'ax_max': 0.3,
        'ax_rms': 0.12, 'ax_skewness': 0.0, 'ax_kurtosis': 0.0,
        'ay_mean': 0.0, 'ay_std': 0.08, 'ay_rms': 0.1, 'ay_skewness': 0.0,
        'az_mean': -1.0, 'az_std': 0.15, 'az_rms': 1.02,
        'speed_mean': 60.0, 'speed_std': 2.0, 'speed_range': 5.0,
        'wheel_std': 0.5, 'wheel_range': 1.5, 'wheel_rms': 0.6,
        'ax_dominant_freq': 0.5, 'ax_spectral_centroid': 1.0, 'ax_spectral_entropy': 2.0,
        'ay_dominant_freq': 0.3, 'ay_spectral_centroid': 0.8, 'ay_spectral_entropy': 1.8,
        'az_dominant_freq': 0.2, 'az_spectral_centroid': 0.5, 'az_spectral_entropy': 1.5,
        'speed_dominant_freq': 0.1, 'speed_spectral_centroid': 0.3,
        'wheel_dominant_freq': 0.1, 'wheel_spectral_centroid': 0.2,
        'gz_dominant_freq': 0.05, 'gz_spectral_centroid': 0.15,
        'ax_jerk': 0.5, 'ax_snap': 2.0, 'ay_jerk': 0.3, 'ay_snap': 1.5,
        'az_jerk': 0.4, 'az_snap': 1.8, 'speed_jerk': 0.2, 'speed_snap': 1.0,
        'wheel_jerk': 0.1, 'wheel_snap': 0.5, 'gz_jerk': 0.05, 'gz_snap': 0.3,
        'turn_radius': 500.0, 'expected_yaw_rate': 0.5, 'yaw_rate_error': 0.1,
        'lateral_accel_ratio': 0.3, 'speed_ms': 16.7, 'slip_angle_est': 0.01,
        'accel_speed_ratio': 0.005, 'roll_est': 0.2,
    }


# 每类行为的特征参数覆盖 (只覆盖区别于基线的关键特征)
BEHAVIOR_PARAMS = {
    # ── LONGITUDINAL ──
    'stopped': {
        'speed_mean': (0.0, 0.3), 'speed_std': (0.0, 0.1), 'speed_range': (0.0, 0.5),
        'ax_mean': (0.0, 0.02), 'ax_std': (0.02, 0.01), 'ax_rms': (0.03, 0.01),
        'ax_min': (-0.05, 0.02), 'ax_max': (0.05, 0.02),
        'ay_mean': (0.0, 0.01), 'ay_std': (0.02, 0.01),
        'speed_ms': (0.0, 0.1), 'accel_speed_ratio': (0.0, 0.001),
        'ax_jerk': (0.05, 0.02), 'speed_jerk': (0.01, 0.005),
    },
    'launch': {
        'speed_mean': (5.0, 3.0), 'speed_std': (3.0, 1.5), 'speed_range': (8.0, 3.0),
        'ax_mean': (0.15, 0.05), 'ax_std': (0.15, 0.05), 'ax_rms': (0.2, 0.05),
        'ax_max': (0.4, 0.1), 'ax_min': (0.0, 0.05),
        'speed_ms': (1.5, 0.8), 'ax_jerk': (2.0, 0.5), 'speed_jerk': (1.5, 0.5),
        'accel_speed_ratio': (0.1, 0.03),
    },
    'normal_acceleration': {
        'ax_mean': (0.08, 0.03), 'ax_std': (0.08, 0.03), 'ax_rms': (0.12, 0.03),
        'ax_max': (0.25, 0.08), 'ax_min': (-0.05, 0.03),
        'speed_mean': (40.0, 10.0), 'speed_std': (3.0, 1.0), 'speed_range': (8.0, 3.0),
        'ax_jerk': (1.0, 0.3), 'speed_jerk': (0.8, 0.3),
        'accel_speed_ratio': (0.02, 0.01), 'speed_ms': (12.0, 3.0),
    },
    'aggressive_acceleration': {
        'ax_mean': (0.25, 0.08), 'ax_std': (0.2, 0.06), 'ax_rms': (0.3, 0.08),
        'ax_max': (0.6, 0.15), 'ax_min': (-0.05, 0.05),
        'ax_skewness': (0.5, 0.2), 'ax_kurtosis': (1.0, 0.5),
        'speed_mean': (35.0, 10.0), 'speed_std': (5.0, 2.0), 'speed_range': (15.0, 5.0),
        'ax_jerk': (3.0, 1.0), 'speed_jerk': (2.5, 0.8),
        'accel_speed_ratio': (0.08, 0.03), 'speed_ms': (10.0, 3.0),
        'ax_dominant_freq': (2.0, 0.5), 'ax_spectral_centroid': (3.0, 0.8),
    },
    'constant_speed': {
        'speed_mean': (70.0, 15.0), 'speed_std': (0.5, 0.2), 'speed_range': (1.5, 0.5),
        'ax_mean': (0.0, 0.02), 'ax_std': (0.03, 0.01), 'ax_rms': (0.04, 0.01),
        'ax_max': (0.08, 0.03), 'ax_min': (-0.08, 0.03),
        'speed_ms': (20.0, 4.0), 'ax_jerk': (0.1, 0.05), 'speed_jerk': (0.05, 0.02),
        'accel_speed_ratio': (0.001, 0.0005),
    },
    'normal_deceleration': {
        'ax_mean': (-0.1, 0.03), 'ax_std': (0.1, 0.03), 'ax_rms': (0.15, 0.04),
        'ax_max': (0.05, 0.03), 'ax_min': (-0.3, 0.08),
        'ax_skewness': (-0.5, 0.2),
        'speed_mean': (45.0, 10.0), 'speed_std': (3.0, 1.0), 'speed_range': (10.0, 3.0),
        'ax_jerk': (1.5, 0.5), 'speed_jerk': (1.0, 0.3),
        'accel_speed_ratio': (0.02, 0.01), 'speed_ms': (13.0, 3.0),
    },
    'aggressive_deceleration': {
        'ax_mean': (-0.3, 0.08), 'ax_std': (0.25, 0.07), 'ax_rms': (0.35, 0.08),
        'ax_max': (0.0, 0.05), 'ax_min': (-0.7, 0.15),
        'ax_skewness': (-0.8, 0.3), 'ax_kurtosis': (1.5, 0.5),
        'speed_mean': (40.0, 10.0), 'speed_std': (5.0, 2.0), 'speed_range': (18.0, 5.0),
        'ax_jerk': (4.0, 1.2), 'speed_jerk': (3.0, 1.0),
        'accel_speed_ratio': (0.06, 0.02), 'speed_ms': (12.0, 3.0),
        'ax_dominant_freq': (2.5, 0.7), 'ax_spectral_centroid': (3.5, 1.0),
    },
    'emergency_braking': {
        'ax_mean': (-0.6, 0.15), 'ax_std': (0.4, 0.1), 'ax_rms': (0.6, 0.12),
        'ax_max': (-0.1, 0.05), 'ax_min': (-1.2, 0.2),
        'ax_skewness': (-1.2, 0.3), 'ax_kurtosis': (2.5, 0.8),
        'speed_mean': (30.0, 10.0), 'speed_std': (8.0, 2.5), 'speed_range': (25.0, 6.0),
        'ax_jerk': (8.0, 2.0), 'speed_jerk': (6.0, 1.5),
        'accel_speed_ratio': (0.15, 0.04), 'speed_ms': (9.0, 3.0),
        'ax_dominant_freq': (4.0, 1.0), 'ax_spectral_centroid': (5.0, 1.2),
        'ax_spectral_entropy': (3.5, 0.5),
    },

    # ── LATERAL ──
    'straight_driving': {
        'ay_mean': (0.0, 0.03), 'ay_std': (0.05, 0.02), 'ay_rms': (0.06, 0.02),
        'ay_skewness': (0.0, 0.1),
        'wheel_std': (0.3, 0.1), 'wheel_range': (1.0, 0.3), 'wheel_rms': (0.4, 0.1),
        'speed_mean': (70.0, 15.0), 'turn_radius': (800.0, 200.0),
        'lateral_accel_ratio': (0.15, 0.05), 'expected_yaw_rate': (0.2, 0.08),
    },
    'lane_keeping': {
        'ay_mean': (0.0, 0.04), 'ay_std': (0.06, 0.02), 'ay_rms': (0.07, 0.02),
        'wheel_std': (0.4, 0.15), 'wheel_range': (1.2, 0.4), 'wheel_rms': (0.5, 0.15),
        'speed_mean': (65.0, 15.0), 'turn_radius': (700.0, 200.0),
        'lateral_accel_ratio': (0.2, 0.05), 'wheel_jerk': (0.2, 0.08),
    },
    'tight_turn': {
        'ay_mean': (0.15, 0.05), 'ay_std': (0.15, 0.05), 'ay_rms': (0.2, 0.05),
        'ay_skewness': (0.3, 0.15),
        'wheel_std': (5.0, 1.5), 'wheel_range': (15.0, 4.0), 'wheel_rms': (5.5, 1.5),
        'speed_mean': (15.0, 5.0), 'turn_radius': (30.0, 10.0),
        'lateral_accel_ratio': (1.5, 0.3), 'expected_yaw_rate': (8.0, 2.0),
        'wheel_jerk': (2.0, 0.5), 'gz_dominant_freq': (0.5, 0.15),
        'gz_spectral_centroid': (1.0, 0.3), 'wheel_dominant_freq': (0.5, 0.15),
        'roll_est': (3.0, 1.0),
    },
    'wide_turn': {
        'ay_mean': (0.08, 0.03), 'ay_std': (0.08, 0.03), 'ay_rms': (0.1, 0.03),
        'wheel_std': (2.5, 0.8), 'wheel_range': (8.0, 2.0), 'wheel_rms': (2.8, 0.8),
        'speed_mean': (25.0, 8.0), 'turn_radius': (80.0, 25.0),
        'lateral_accel_ratio': (0.8, 0.2), 'expected_yaw_rate': (3.0, 1.0),
        'wheel_jerk': (1.0, 0.3), 'gz_dominant_freq': (0.25, 0.08),
        'roll_est': (1.5, 0.5),
    },
    'u_turn': {
        'ay_mean': (0.2, 0.06), 'ay_std': (0.2, 0.06), 'ay_rms': (0.25, 0.06),
        'wheel_std': (8.0, 2.0), 'wheel_range': (25.0, 6.0), 'wheel_rms': (8.5, 2.0),
        'speed_mean': (8.0, 3.0), 'turn_radius': (10.0, 3.0),
        'lateral_accel_ratio': (2.0, 0.4), 'expected_yaw_rate': (15.0, 3.0),
        'wheel_jerk': (3.0, 1.0), 'gz_dominant_freq': (0.8, 0.2),
        'roll_est': (5.0, 1.5), 'speed_ms': (2.5, 0.8),
    },
    'lane_change': {
        'ay_mean': (0.0, 0.08), 'ay_std': (0.12, 0.04), 'ay_rms': (0.14, 0.04),
        'ay_skewness': (0.0, 0.3),
        'wheel_std': (1.5, 0.5), 'wheel_range': (5.0, 1.5), 'wheel_rms': (1.8, 0.5),
        'speed_mean': (55.0, 12.0), 'turn_radius': (200.0, 60.0),
        'lateral_accel_ratio': (0.6, 0.15), 'expected_yaw_rate': (1.5, 0.5),
        'wheel_jerk': (0.8, 0.25), 'gz_jerk': (0.3, 0.1),
    },
    'weaving': {
        'ay_mean': (0.0, 0.1), 'ay_std': (0.18, 0.05), 'ay_rms': (0.2, 0.05),
        'ay_skewness': (0.0, 0.4),
        'wheel_std': (3.0, 1.0), 'wheel_range': (10.0, 3.0), 'wheel_rms': (3.3, 1.0),
        'speed_mean': (40.0, 12.0), 'turn_radius': (100.0, 30.0),
        'lateral_accel_ratio': (0.9, 0.2), 'expected_yaw_rate': (2.5, 0.8),
        'wheel_jerk': (1.5, 0.5), 'gz_jerk': (0.5, 0.15),
        'gz_dominant_freq': (0.4, 0.12), 'wheel_dominant_freq': (0.3, 0.1),
        'ay_dominant_freq': (0.5, 0.15), 'ay_spectral_centroid': (1.2, 0.3),
    },

    # ── COMPOSITE ──
    'cornering_acceleration': {
        'ax_mean': (0.1, 0.04), 'ax_std': (0.1, 0.04), 'ax_rms': (0.15, 0.04),
        'ax_max': (0.3, 0.08),
        'ay_mean': (0.1, 0.04), 'ay_std': (0.12, 0.04), 'ay_rms': (0.15, 0.04),
        'wheel_std': (3.0, 1.0), 'wheel_range': (10.0, 3.0), 'wheel_rms': (3.3, 1.0),
        'speed_mean': (30.0, 8.0), 'turn_radius': (50.0, 15.0),
        'lateral_accel_ratio': (1.0, 0.25), 'expected_yaw_rate': (4.0, 1.2),
        'ax_jerk': (1.5, 0.5), 'wheel_jerk': (1.2, 0.4),
        'accel_speed_ratio': (0.03, 0.01), 'speed_ms': (9.0, 2.5),
    },
    'cornering_deceleration': {
        'ax_mean': (-0.12, 0.04), 'ax_std': (0.12, 0.04), 'ax_rms': (0.18, 0.05),
        'ax_min': (-0.4, 0.1), 'ax_skewness': (-0.5, 0.2),
        'ay_mean': (0.1, 0.04), 'ay_std': (0.12, 0.04), 'ay_rms': (0.15, 0.04),
        'wheel_std': (3.0, 1.0), 'wheel_range': (10.0, 3.0), 'wheel_rms': (3.3, 1.0),
        'speed_mean': (30.0, 8.0), 'turn_radius': (50.0, 15.0),
        'lateral_accel_ratio': (1.0, 0.25), 'expected_yaw_rate': (4.0, 1.2),
        'ax_jerk': (2.0, 0.6), 'wheel_jerk': (1.2, 0.4),
        'accel_speed_ratio': (0.04, 0.01), 'speed_ms': (9.0, 2.5),
    },
    'cornering_braking': {
        'ax_mean': (-0.35, 0.1), 'ax_std': (0.3, 0.08), 'ax_rms': (0.4, 0.1),
        'ax_min': (-0.8, 0.2), 'ax_skewness': (-1.0, 0.3), 'ax_kurtosis': (1.5, 0.5),
        'ay_mean': (0.12, 0.04), 'ay_std': (0.15, 0.05), 'ay_rms': (0.18, 0.05),
        'wheel_std': (3.5, 1.0), 'wheel_range': (12.0, 3.0), 'wheel_rms': (3.8, 1.0),
        'speed_mean': (25.0, 8.0), 'turn_radius': (40.0, 12.0),
        'lateral_accel_ratio': (0.8, 0.2), 'expected_yaw_rate': (5.0, 1.5),
        'ax_jerk': (5.0, 1.5), 'wheel_jerk': (1.5, 0.5),
        'accel_speed_ratio': (0.1, 0.03), 'speed_ms': (7.5, 2.5),
        'ax_dominant_freq': (3.0, 0.8), 'ax_spectral_centroid': (4.0, 1.0),
    },
    'rapid_direction_change': {
        'ax_mean': (0.0, 0.15), 'ax_std': (0.25, 0.08), 'ax_rms': (0.3, 0.08),
        'ay_mean': (0.0, 0.2), 'ay_std': (0.3, 0.08), 'ay_rms': (0.35, 0.08),
        'ay_skewness': (0.0, 0.5),
        'wheel_std': (6.0, 2.0), 'wheel_range': (20.0, 5.0), 'wheel_rms': (6.5, 2.0),
        'speed_mean': (35.0, 10.0), 'turn_radius': (60.0, 20.0),
        'lateral_accel_ratio': (1.2, 0.3), 'expected_yaw_rate': (6.0, 2.0),
        'ax_jerk': (3.0, 1.0), 'ay_jerk': (3.0, 1.0),
        'wheel_jerk': (2.5, 0.8), 'gz_jerk': (1.0, 0.3),
        'gz_dominant_freq': (0.6, 0.2), 'wheel_dominant_freq': (0.5, 0.15),
        'ay_dominant_freq': (0.6, 0.2), 'ax_dominant_freq': (1.5, 0.5),
    },

    # ── ANOMALY ──
    'skid_risk': {
        'ay_mean': (0.0, 0.1), 'ay_std': (0.25, 0.08), 'ay_rms': (0.28, 0.08),
        'gx': (0.0, 0.1), 'gy': (0.0, 0.1),
        'wheel_std': (4.0, 1.2), 'wheel_range': (15.0, 4.0), 'wheel_rms': (4.5, 1.2),
        'speed_mean': (30.0, 10.0), 'lateral_accel_ratio': (1.5, 0.4),
        'expected_yaw_rate': (5.0, 1.5), 'yaw_rate_error': (2.0, 0.5),
        'slip_angle_est': (0.15, 0.05), 'turn_radius': (30.0, 10.0),
        'ay_jerk': (2.5, 0.8), 'gz_jerk': (0.8, 0.25),
        'roll_est': (3.0, 1.0),
    },
    'rollover_risk': {
        'ay_mean': (0.0, 0.1), 'ay_std': (0.3, 0.1), 'ay_rms': (0.35, 0.1),
        'roll_est': (8.0, 2.0), 'lateral_accel_ratio': (2.5, 0.5),
        'wheel_std': (5.0, 1.5), 'wheel_range': (18.0, 5.0), 'wheel_rms': (5.5, 1.5),
        'speed_mean': (25.0, 8.0), 'turn_radius': (15.0, 5.0),
        'expected_yaw_rate': (8.0, 2.0), 'yaw_rate_error': (3.0, 0.8),
        'slip_angle_est': (0.2, 0.06),
        'ay_jerk': (3.5, 1.0), 'gz_jerk': (1.2, 0.3),
        'ay_dominant_freq': (0.8, 0.2),
    },
    'severe_bump': {
        'az_mean': (-1.0, 0.5), 'az_std': (0.5, 0.15), 'az_rms': (1.5, 0.3),
        'az_jerk': (5.0, 1.5), 'az_snap': (20.0, 5.0),
        'az_dominant_freq': (3.0, 0.8), 'az_spectral_centroid': (4.0, 1.0),
        'az_spectral_entropy': (3.0, 0.5),
        'ax_mean': (0.0, 0.15), 'ax_std': (0.15, 0.05), 'ax_rms': (0.2, 0.05),
        'ax_jerk': (3.0, 1.0), 'ax_snap': (12.0, 3.0),
        'speed_mean': (20.0, 8.0),
    },
    'sensor_fault': {
        'ax_mean': (0.0, 0.5), 'ax_std': (0.5, 0.2), 'ax_rms': (0.6, 0.2),
        'ax_min': (-1.5, 0.5), 'ax_max': (1.5, 0.5),
        'ax_skewness': (0.0, 0.8), 'ax_kurtosis': (5.0, 2.0),
        'ay_mean': (0.0, 0.5), 'ay_std': (0.5, 0.2), 'ay_rms': (0.6, 0.2),
        'az_mean': (-1.0, 0.5), 'az_std': (0.5, 0.2), 'az_rms': (1.5, 0.3),
        'ax_jerk': (10.0, 3.0), 'ax_snap': (50.0, 15.0),
        'ay_jerk': (10.0, 3.0), 'az_jerk': (10.0, 3.0),
        'ax_dominant_freq': (10.0, 3.0), 'ax_spectral_entropy': (5.0, 1.0),
        'ay_dominant_freq': (10.0, 3.0), 'az_dominant_freq': (10.0, 3.0),
        'speed_mean': (0.0, 30.0), 'speed_std': (0.0, 15.0), 'speed_range': (0.0, 30.0),
        'wheel_std': (0.0, 5.0), 'wheel_range': (0.0, 15.0),
        'accel_speed_ratio': (0.0, 0.5), 'speed_ms': (0.0, 15.0),
    },
}


def generate_synthetic_data(
    samples_per_class: int = 400,
    noise_scale: float = 0.15,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """生成合成训练数据

    Args:
        samples_per_class: 每类样本数
        noise_scale: 类内噪声比例 (相对于特征 std)
        random_state: 随机种子

    Returns:
        (X, y) — X shape=(N, 55), y shape=(N,)
    """
    rng = np.random.RandomState(random_state)
    n_classes = len(BEHAVIOR_TYPES_V2)
    total_samples = samples_per_class * n_classes

    X = np.zeros((total_samples, 55), dtype=np.float32)
    y = np.zeros(total_samples, dtype=np.int32)

    base = _base_vector()

    for cls_idx, event_type in enumerate(BEHAVIOR_TYPES_V2):
        start = cls_idx * samples_per_class
        end = start + samples_per_class

        params = BEHAVIOR_PARAMS.get(event_type, {})
        y[start:end] = cls_idx

        for feat_idx, feat_name in enumerate(FEATURE_NAMES):
            if feat_name in params:
                mean_val, std_val = params[feat_name]
            else:
                # 使用基线值
                mean_val = base.get(feat_name, 0.0)
                std_val = 0.1  # 默认噪声

            # 生成带噪声的样本
            samples = rng.normal(mean_val, std_val * noise_scale, samples_per_class)
            X[start:end, feat_idx] = samples.astype(np.float32)

    # 打乱数据
    perm = rng.permutation(total_samples)
    X, y = X[perm], y[perm]

    logger.info(f"合成数据: {total_samples} 样本, {n_classes} 类, 55 特征")
    return X, y


def main():
    import argparse
    parser = argparse.ArgumentParser(description='生成合成训练数据')
    parser.add_argument('--samples', type=int, default=400, help='每类样本数')
    parser.add_argument('--noise', type=float, default=0.15, help='类内噪声比例')
    parser.add_argument('--output', type=str, default='training_data.npz')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    X, y = generate_synthetic_data(
        samples_per_class=args.samples,
        noise_scale=args.noise,
        random_state=args.seed,
    )

    # 保存
    np.savez_compressed(args.output, X=X, y=y)
    logger.info(f"训练数据已保存: {args.output} ({X.shape[0]} 样本)")

    # 打印类别分布
    from collections import Counter
    label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}
    id_to_label = {i: name for name, i in label_to_id.items()}
    for lid, cnt in sorted(Counter(y).items()):
        name = id_to_label.get(lid, f'id_{lid}')
        print(f"  {name:30s}: {cnt}")


if __name__ == '__main__':
    main()