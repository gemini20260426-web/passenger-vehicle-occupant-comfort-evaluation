#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传感器故障数据增强器 — 从真实数据生成传感器故障样本

sensor_fault 是 25 种事件类型中唯一在真实采集中不太可能大量标注的类。
通过数据增强从真实数据生成 4 种故障模式:
  - signal_stuck: 信号卡滞 (重复同一值)
  - signal_dropout: 信号丢包 (随机置零)
  - signal_saturation: 饱和削波 (截断)
  - signal_noise_burst: 噪声爆发 (加高斯噪声)

用法:
    from core.core.analysis.sensor_fault_augmenter import SensorFaultAugmenter
    aug = SensorFaultAugmenter()
    X_fault, y_fault = aug.generate(X_real, y_real, n_samples=50)
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# 故障类型定义
FAULT_TYPES = {
    'signal_stuck': {
        'desc': '信号卡滞 — 重复同一值',
        'severity': 'medium',
    },
    'signal_dropout': {
        'desc': '信号丢包 — 随机置零',
        'severity': 'high',
    },
    'signal_saturation': {
        'desc': '饱和削波 — 截断到限幅值',
        'severity': 'medium',
    },
    'signal_noise_burst': {
        'desc': '噪声爆发 — 加高斯噪声',
        'severity': 'low',
    },
}


class SensorFaultAugmenter:
    """传感器故障数据增强器"""

    def __init__(
        self,
        fault_axes: Optional[List[int]] = None,
        random_state: int = 42,
    ):
        """
        Args:
            fault_axes: 施加故障的轴索引列表 (对应 55 维特征向量中的位置)
                        默认选取 ax, ay, az 相关特征的索引
            random_state: 随机种子
        """
        self._rng = np.random.RandomState(random_state)

        if fault_axes is None:
            # 默认: ax(0-6), ay(7-10), az(11-13) 的特征索引
            self.fault_axes = list(range(0, 14))  # ax + ay + az 特征
        else:
            self.fault_axes = fault_axes

    def generate(
        self,
        X_real: np.ndarray,
        y_real: np.ndarray,
        n_samples: int = 50,
        fault_probs: Optional[Dict[str, float]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """从真实数据生成传感器故障样本

        Args:
            X_real: 真实特征矩阵 (N, 55)
            y_real: 真实标签数组 (N,)
            n_samples: 生成的故障样本数
            fault_probs: 各故障类型概率, 默认均匀分布

        Returns:
            (X_fault, y_fault) — 故障样本和标签 (sensor_fault)
        """
        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2

        sensor_fault_id = BEHAVIOR_TYPES_V2.index('sensor_fault')

        if fault_probs is None:
            fault_types = list(FAULT_TYPES.keys())
            fault_probs = {ft: 1.0 / len(fault_types) for ft in fault_types}

        X_fault_list = []
        y_fault_list = []

        for i in range(n_samples):
            # 随机选择真实样本
            idx = self._rng.randint(0, len(X_real))
            sample = X_real[idx].copy()

            # 随机选择故障类型
            fault_type = self._rng.choice(
                list(fault_probs.keys()),
                p=list(fault_probs.values()),
            )

            # 施加故障
            if fault_type == 'signal_stuck':
                sample = self._apply_stuck(sample)
            elif fault_type == 'signal_dropout':
                sample = self._apply_dropout(sample)
            elif fault_type == 'signal_saturation':
                sample = self._apply_saturation(sample)
            elif fault_type == 'signal_noise_burst':
                sample = self._apply_noise_burst(sample)

            X_fault_list.append(sample)
            y_fault_list.append(sensor_fault_id)

        X_fault = np.array(X_fault_list, dtype=np.float32)
        y_fault = np.array(y_fault_list, dtype=np.int32)

        logger.info(f"传感器故障样本生成: {n_samples} 个, "
                     f"故障类型: {list(fault_probs.keys())}")

        return X_fault, y_fault

    def _apply_stuck(self, sample: np.ndarray) -> np.ndarray:
        """信号卡滞: 将某个轴的所有特征设置为同一值"""
        axis_start = self._rng.choice(self.fault_axes)
        stuck_value = sample[axis_start]
        sample[axis_start] = stuck_value
        # 邻近特征也卡滞
        for offset in range(1, min(3, len(self.fault_axes) - axis_start)):
            sample[axis_start + offset] = stuck_value
        return sample

    def _apply_dropout(self, sample: np.ndarray) -> np.ndarray:
        """信号丢包: 随机将 10-30% 的特征置零"""
        dropout_rate = self._rng.uniform(0.1, 0.3)
        mask = self._rng.random(len(self.fault_axes)) < dropout_rate
        for i, ax_idx in enumerate(self.fault_axes):
            if mask[i]:
                sample[ax_idx] = 0.0
        return sample

    def _apply_saturation(self, sample: np.ndarray) -> np.ndarray:
        """饱和削波: 将特征值截断到 ±2σ 范围内"""
        for ax_idx in self.fault_axes:
            val = sample[ax_idx]
            limit = 2.0  # 任意限幅值
            if abs(val) > limit:
                sample[ax_idx] = np.sign(val) * limit
        return sample

    def _apply_noise_burst(self, sample: np.ndarray) -> np.ndarray:
        """噪声爆发: 对部分特征加高斯噪声"""
        noise_scale = self._rng.uniform(1.0, 5.0)
        n_affected = self._rng.randint(1, max(2, len(self.fault_axes) // 3))
        affected_indices = self._rng.choice(self.fault_axes, n_affected, replace=False)
        for idx in affected_indices:
            sample[idx] += self._rng.normal(0, noise_scale)
        return sample

    def generate_and_merge(
        self,
        X_real: np.ndarray,
        y_real: np.ndarray,
        n_samples: int = 50,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """生成故障样本并合并到真实数据中

        Returns:
            (X_merged, y_merged) — 含 sensor_fault 类的合并数据
        """
        X_fault, y_fault = self.generate(X_real, y_real, n_samples)
        X_merged = np.vstack([X_real, X_fault])
        y_merged = np.concatenate([y_real, y_fault])
        logger.info(f"合并后: {len(X_merged)} 样本 (含 {n_samples} 传感器故障)")
        return X_merged, y_merged


def main():
    """独立测试"""
    import argparse
    parser = argparse.ArgumentParser(description='传感器故障数据增强')
    parser.add_argument('--data', type=str, required=True, help='.npz 训练数据')
    parser.add_argument('--n_samples', type=int, default=50, help='生成故障样本数')
    parser.add_argument('--output', type=str, default='training_data_with_fault.npz')

    args = parser.parse_args()

    data = np.load(args.data, allow_pickle=True)
    X, y = data['X'], data['y']

    aug = SensorFaultAugmenter()
    X_merged, y_merged = aug.generate_and_merge(X, y, n_samples=args.n_samples)

    np.savez_compressed(args.output, X=X_merged, y=y_merged)
    print(f"已保存: {args.output} ({len(X_merged)} 样本)")


if __name__ == '__main__':
    main()