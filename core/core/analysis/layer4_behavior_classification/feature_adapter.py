#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
特征适配器 — 从 FrameFeatures 135维特征中提取 55维 ML 特征向量

将 FeatureExtractor (L2) 输出的 FrameFeatures 转换为 LightGBM 所需
的固定维度特征向量，用于 L4 行为分类。

设计原则:
  - 55 维特征覆盖时域(20) + 频域(15) + 运动学(12) + 物理(8)
  - 缺失特征填充 0.0，确保推理不中断
  - 惰性特征名解析，兼容不同版本的特征提取器输出
"""

import numpy as np
from typing import Dict, Optional, List
from ..core_types import FrameFeatures


# ═══════════════════════════════════════════════════════════
#  55 维特征选择 — 按领域分组
# ═══════════════════════════════════════════════════════════

TEMPORAL_FEATURES = [
    # ax (纵向加速度) — 7 维
    'ax_mean', 'ax_std', 'ax_min', 'ax_max', 'ax_rms',
    'ax_skewness', 'ax_kurtosis',
    # ay (侧向加速度) — 4 维
    'ay_mean', 'ay_std', 'ay_rms', 'ay_skewness',
    # az (垂向加速度) — 3 维
    'az_mean', 'az_std', 'az_rms',
    # speed — 3 维
    'speed_mean', 'speed_std', 'speed_range',
    # wheel — 3 维
    'wheel_std', 'wheel_range', 'wheel_rms',
]

SPECTRAL_FEATURES = [
    # ax 频域 — 3 维
    'ax_dominant_freq', 'ax_spectral_centroid', 'ax_spectral_entropy',
    # ay 频域 — 3 维
    'ay_dominant_freq', 'ay_spectral_centroid', 'ay_spectral_entropy',
    # az 频域 — 3 维
    'az_dominant_freq', 'az_spectral_centroid', 'az_spectral_entropy',
    # speed 频域 — 2 维
    'speed_dominant_freq', 'speed_spectral_centroid',
    # wheel 频域 — 2 维
    'wheel_dominant_freq', 'wheel_spectral_centroid',
    # gz 频域 — 2 维
    'gz_dominant_freq', 'gz_spectral_centroid',
]

KINEMATIC_FEATURES = [
    # ax 运动学 — 2 维
    'ax_jerk', 'ax_snap',
    # ay 运动学 — 2 维
    'ay_jerk', 'ay_snap',
    # az 运动学 — 2 维
    'az_jerk', 'az_snap',
    # speed 运动学 — 2 维
    'speed_jerk', 'speed_snap',
    # wheel 运动学 — 2 维
    'wheel_jerk', 'wheel_snap',
    # gz 运动学 — 2 维
    'gz_jerk', 'gz_snap',
]

PHYSICS_FEATURES = [
    'turn_radius',
    'expected_yaw_rate',
    'yaw_rate_error',
    'lateral_accel_ratio',
    'speed_ms',
    'slip_angle_est',
    'accel_speed_ratio',
    'roll_est',
]

# 合并: 20 + 15 + 12 + 8 = 55
ALL_55_FEATURES = (
    TEMPORAL_FEATURES
    + SPECTRAL_FEATURES
    + KINEMATIC_FEATURES
    + PHYSICS_FEATURES
)

assert len(ALL_55_FEATURES) == 55, f"特征维度应为55，实际为{len(ALL_55_FEATURES)}"


class FeatureAdapter:
    """将 FrameFeatures 转换为 55 维 ML 特征向量。

    用法:
        adapter = FeatureAdapter()
        X = adapter.transform(frame_features)  # → np.ndarray shape=(55,)
        X_batch = adapter.transform_batch(list_of_features)  # → np.ndarray shape=(N, 55)
    """

    def __init__(self):
        self._feature_names: List[str] = list(ALL_55_FEATURES)
        self._dim = len(self._feature_names)

    @property
    def feature_names(self) -> List[str]:
        """返回 55 维特征的名称列表"""
        return self._feature_names

    @property
    def n_features(self) -> int:
        return self._dim

    def transform(self, features: Optional[FrameFeatures]) -> np.ndarray:
        """单帧特征转换

        Args:
            features: L2 FeatureExtractor 输出的 FrameFeatures，可为 None

        Returns:
            shape=(55,) 的 float32 数组，缺失特征填充 0.0
        """
        vec = np.zeros(self._dim, dtype=np.float32)

        if features is None:
            return vec

        all_feats = features.as_dict()

        for i, name in enumerate(self._feature_names):
            val = all_feats.get(name, 0.0)
            if val is None:
                val = 0.0
            vec[i] = float(val)

        return vec

    def transform_batch(self, features_list: List[Optional[FrameFeatures]]) -> np.ndarray:
        """批量特征转换

        Args:
            features_list: FrameFeatures 列表

        Returns:
            shape=(N, 55) 的 float32 数组
        """
        N = len(features_list)
        X = np.zeros((N, self._dim), dtype=np.float32)
        for i, feats in enumerate(features_list):
            X[i] = self.transform(feats)
        return X

    def get_feature_vector(self, all_feats: Dict[str, float]) -> np.ndarray:
        """从特征字典直接构建向量 (绕过 FrameFeatures)

        Args:
            all_feats: 特征名 → 值的字典

        Returns:
            shape=(55,) 的 float32 数组
        """
        vec = np.zeros(self._dim, dtype=np.float32)
        for i, name in enumerate(self._feature_names):
            val = all_feats.get(name, 0.0)
            if val is None:
                val = 0.0
            vec[i] = float(val)
        return vec

    def get_feature_importance(self, model) -> Dict[str, float]:
        """获取特征重要性排序 (模型训练后调用)

        Args:
            model: 已训练的 LightGBM 模型 (有 feature_importances_ 属性)

        Returns:
            {特征名: 重要性} 字典，按重要性降序排列
        """
        if not hasattr(model, 'feature_importances_'):
            return {}
        importances = model.feature_importances_
        pairs = sorted(
            zip(self._feature_names, importances),
            key=lambda x: x[1],
            reverse=True,
        )
        return dict(pairs)