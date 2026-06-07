#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMOTE 类别均衡器 — 处理 25 类驾驶行为事件的不平衡分布

问题: 罕见事件 (severe_bump, skid_risk, rollover_risk, sensor_fault)
      在训练数据中占比不足 1%，导致分类器忽略这些类别。

方案: SMOTE (Synthetic Minority Over-sampling Technique)
      + 自定义采样策略，确保每类至少有 min_samples 个样本。

依赖: imbalanced-learn (SMOTE), numpy, sklearn
"""

import numpy as np
import logging
from typing import Any, Dict, Optional, Tuple, List
from collections import Counter

logger = logging.getLogger(__name__)


class SmoteBalancer:
    """SMOTE 类别均衡器

    用法:
        balancer = SmoteBalancer(min_samples_per_class=50, random_state=42)
        X_resampled, y_resampled = balancer.fit_resample(X, y)
    """

    def __init__(
        self,
        min_samples_per_class: int = 50,
        k_neighbors: int = 5,
        random_state: int = 42,
    ):
        """
        Args:
            min_samples_per_class: 每类最少样本数 (SMOTE 合成目标)
            k_neighbors: SMOTE 近邻数
            random_state: 随机种子
        """
        self._min_samples = min_samples_per_class
        self._k_neighbors = k_neighbors
        self._random_state = random_state
        self._sampling_strategy: Optional[Dict[int, int]] = None
        self._original_counts: Dict[int, int] = {}
        self._resampled_counts: Dict[int, int] = {}

    def fit_resample(
        self, X: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """对训练数据执行 SMOTE 过采样

        Args:
            X: 特征矩阵 shape=(N, 55)
            y: 标签数组 shape=(N,), 整数编码 [0, 24]

        Returns:
            (X_resampled, y_resampled) — 均衡后的数据
        """
        from imblearn.over_sampling import SMOTE

        self._original_counts = dict(Counter(y))
        class_counts = self._original_counts

        # 构建采样策略: 每类至少 min_samples 个
        self._sampling_strategy = {}
        for cls_id, count in class_counts.items():
            if count < self._min_samples:
                self._sampling_strategy[cls_id] = self._min_samples

        if not self._sampling_strategy:
            logger.info("所有类别样本数已达标，无需 SMOTE 过采样")
            return X, y

        # 检查 k_neighbors 是否合法
        min_class_count = min(class_counts.values())
        actual_k = min(self._k_neighbors, min_class_count - 1, 5)
        if actual_k < 1:
            actual_k = 1

        logger.info(
            f"SMOTE 过采样: {len(self._sampling_strategy)} 个少数类 "
            f"需要合成, k_neighbors={actual_k}"
        )

        try:
            smote = SMOTE(
                sampling_strategy=self._sampling_strategy,
                k_neighbors=actual_k,
                random_state=self._random_state,
            )
            X_res, y_res = smote.fit_resample(X, y)
        except Exception as e:
            logger.error(f"SMOTE 过采样失败: {e}，回退到原始数据")
            return X, y

        self._resampled_counts = dict(Counter(y_res))

        logger.info(
            f"SMOTE 完成: {len(X)} → {len(X_res)} 样本 "
            f"(+{len(X_res) - len(X)} 合成)"
        )
        return X_res, y_res

    def get_statistics(self) -> Dict[str, Any]:
        """返回过采样前后的类别分布统计"""
        return {
            'original_counts': self._original_counts,
            'resampled_counts': self._resampled_counts,
            'original_total': sum(self._original_counts.values()),
            'resampled_total': sum(self._resampled_counts.values()),
            'classes_oversampled': len(self._sampling_strategy or {}),
        }

    def get_class_weights(self, n_classes: int = 25) -> Dict[int, float]:
        """计算类别权重 (用于 LightGBM class_weight 参数)

        基于原始分布计算逆频率权重，使少数类获得更高权重。

        Args:
            n_classes: 类别总数

        Returns:
            {class_id: weight} 字典
        """
        if not self._original_counts:
            return {i: 1.0 for i in range(n_classes)}

        total = sum(self._original_counts.values())
        weights = {}
        for cls_id in range(n_classes):
            count = self._original_counts.get(cls_id, 0)
            if count > 0:
                weights[cls_id] = total / (n_classes * count)
            else:
                weights[cls_id] = 1.0  # 未见过的类别使用默认权重

        # 裁剪权重范围，避免极端值
        max_weight = 10.0
        for cls_id in weights:
            weights[cls_id] = min(weights[cls_id], max_weight)

        return weights