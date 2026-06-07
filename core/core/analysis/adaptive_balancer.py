#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶梯式类别均衡策略 — 超越单纯 SMOTE

处理真实数据中严重的类别不平衡问题:
  - Level 0: 样本 < 3 → 从合成数据补充 (或跳过)
  - Level 1: 样本 < min_samples → SMOTE 过采样
  - Level 2: 样本 > 90分位 → 欠采样
  - Level 3: 其他 → 保持

用法:
    from core.core.analysis.adaptive_balancer import AdaptiveBalancingStrategy
    balancer = AdaptiveBalancingStrategy(min_samples_per_class=10)
    X_bal, y_bal = balancer.balance(X, y, class_names)
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class AdaptiveBalancingStrategy:
    """阶梯式类别均衡策略 — 超越单纯 SMOTE"""

    def __init__(
        self,
        min_samples_per_class: int = 10,
        undersample_threshold_percentile: int = 90,
        random_state: int = 42,
    ):
        self.min_samples = min_samples_per_class
        self.undersample_percentile = undersample_threshold_percentile
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)

    def analyze(self, y: np.ndarray, class_names: List[str]) -> Dict:
        """分析类别分布，返回平衡策略建议

        Returns:
            {
                'class_distribution': {class_name: count},
                'strategies': {class_name: (method, target, reason)},
                'rare_classes': [...],
                'majority_classes': [...],
            }
        """
        counts = Counter(y)
        n_total = len(y)
        id_to_name = {i: name for i, name in enumerate(class_names)}

        # 计算阈值
        counts_list = list(counts.values())
        undersample_threshold = int(np.percentile(counts_list, self.undersample_percentile))

        strategies = {}
        rare_classes = []
        majority_classes = []

        for cls_idx, count in counts.items():
            cls_name = id_to_name.get(cls_idx, f'class_{cls_idx}')

            if count < 3:
                # Level 0: 样本极少 → 从合成数据补充
                strategies[cls_name] = {
                    'method': 'synthetic_fallback',
                    'current': count,
                    'target': max(self.min_samples, int(np.median(counts_list))),
                    'reason': f'样本极少 ({count} < 3), 需合成数据补充',
                }
                rare_classes.append(cls_name)

            elif count < self.min_samples:
                # Level 1: SMOTE 增强
                target = max(self.min_samples, int(np.median(counts_list)))
                strategies[cls_name] = {
                    'method': 'smote',
                    'current': count,
                    'target': target,
                    'k_neighbors': min(5, count - 1),
                    'reason': f'样本不足 ({count} < {self.min_samples}), SMOTE 增强至 {target}',
                }
                rare_classes.append(cls_name)

            elif count > undersample_threshold:
                # Level 2: 欠采样
                target = int(np.percentile(counts_list, 75))
                strategies[cls_name] = {
                    'method': 'undersample',
                    'current': count,
                    'target': target,
                    'reason': f'多数类 ({count} > {undersample_threshold}), 欠采样至 {target}',
                }
                majority_classes.append(cls_name)

            else:
                # Level 3: 保持
                strategies[cls_name] = {
                    'method': 'keep',
                    'current': count,
                    'target': count,
                    'reason': f'样本适中 ({count}), 保持不变',
                }

        return {
            'n_total': n_total,
            'n_classes': len(counts),
            'undersample_threshold': undersample_threshold,
            'class_distribution': {id_to_name.get(k, f'class_{k}'): v for k, v in counts.items()},
            'strategies': strategies,
            'rare_classes': rare_classes,
            'majority_classes': majority_classes,
        }

    def balance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        class_names: List[str],
        synthetic_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """自适应均衡

        Args:
            X: 特征矩阵 (N, 55)
            y: 标签数组 (N,)
            class_names: 类别名称列表
            synthetic_data: 可选的 (X_syn, y_syn) 合成数据, 用于补充罕见类

        Returns:
            (X_balanced, y_balanced, balance_report)
        """
        from imblearn.over_sampling import SMOTE

        analysis = self.analyze(y, class_names)
        strategies = analysis['strategies']
        name_to_id = {name: i for i, name in enumerate(class_names)}

        X_balanced_parts = []
        y_balanced_parts = []
        report_parts = []

        for cls_name, strat in strategies.items():
            if cls_name not in name_to_id:
                continue
            cls_idx = name_to_id[cls_name]
            mask = y == cls_idx
            X_cls = X[mask]
            y_cls = y[mask]

            method = strat['method']

            if method == 'synthetic_fallback':
                # Level 0: 从合成数据补充
                if synthetic_data is not None:
                    X_syn, y_syn = synthetic_data
                    syn_mask = y_syn == cls_idx
                    X_syn_cls = X_syn[syn_mask]
                    y_syn_cls = y_syn[syn_mask]
                    if len(X_syn_cls) > 0:
                        n_needed = strat['target'] - strat['current']
                        n_take = min(n_needed, len(X_syn_cls))
                        if n_take > 0:
                            X_balanced_parts.append(np.vstack([X_cls, X_syn_cls[:n_take]]))
                            y_balanced_parts.append(np.concatenate([y_cls, y_syn_cls[:n_take]]))
                            report_parts.append(
                                f"  {cls_name}: {strat['current']} → "
                                f"{strat['current'] + n_take} (合成补充 {n_take})"
                            )
                            continue

                # 无合成数据或不足, 保留原样本
                X_balanced_parts.append(X_cls)
                y_balanced_parts.append(y_cls)
                report_parts.append(
                    f"  {cls_name}: {strat['current']} (保留, 无合成数据补充)"
                )
                logger.warning(f"罕见类 {cls_name}: {strat['current']} 样本, 需合成数据补充")

            elif method == 'smote':
                # Level 1: SMOTE 过采样
                k_neighbors = strat.get('k_neighbors', 5)
                if k_neighbors < 1:
                    k_neighbors = 1
                try:
                    smote = SMOTE(
                        sampling_strategy='auto',
                        k_neighbors=k_neighbors,
                        random_state=self.random_state,
                    )
                    X_res, y_res = smote.fit_resample(X, y)
                    mask_res = y_res == cls_idx
                    X_cls_res = X_res[mask_res]
                    y_cls_res = y_res[mask_res]

                    target = strat['target']
                    if len(X_cls_res) > target:
                        indices = self._rng.choice(len(X_cls_res), target, replace=False)
                        X_cls_res = X_cls_res[indices]
                        y_cls_res = y_cls_res[indices]

                    X_balanced_parts.append(X_cls_res)
                    y_balanced_parts.append(y_cls_res)
                    report_parts.append(
                        f"  {cls_name}: {strat['current']} → {len(X_cls_res)} (SMOTE)"
                    )
                except Exception as e:
                    logger.warning(f"SMOTE 失败 ({cls_name}): {e}, 保留原样本")
                    X_balanced_parts.append(X_cls)
                    y_balanced_parts.append(y_cls)
                    report_parts.append(f"  {cls_name}: {strat['current']} (SMOTE失败, 保留)")

            elif method == 'undersample':
                # Level 2: 欠采样
                target = strat['target']
                indices = self._rng.choice(len(X_cls), target, replace=False)
                X_balanced_parts.append(X_cls[indices])
                y_balanced_parts.append(y_cls[indices])
                report_parts.append(
                    f"  {cls_name}: {strat['current']} → {target} (欠采样)"
                )

            else:  # keep
                X_balanced_parts.append(X_cls)
                y_balanced_parts.append(y_cls)
                report_parts.append(f"  {cls_name}: {strat['current']} (保持)")

        X_balanced = np.vstack(X_balanced_parts)
        y_balanced = np.concatenate(y_balanced_parts)

        # 打乱
        perm = self._rng.permutation(len(X_balanced))
        X_balanced = X_balanced[perm]
        y_balanced = y_balanced[perm]

        balance_report = {
            'before': {'n_samples': len(X), 'n_classes': analysis['n_classes']},
            'after': {'n_samples': len(X_balanced), 'n_classes': len(set(y_balanced))},
            'details': report_parts,
            'analysis': analysis,
        }

        logger.info(f"类别均衡完成: {len(X)} → {len(X_balanced)} 样本")
        for line in report_parts:
            logger.info(line)

        return X_balanced, y_balanced, balance_report


def main():
    """独立测试"""
    import argparse
    parser = argparse.ArgumentParser(description='阶梯式类别均衡')
    parser.add_argument('--data', type=str, required=True, help='.npz 训练数据')
    parser.add_argument('--min_samples', type=int, default=10)
    parser.add_argument('--output', type=str, default='training_data_balanced.npz')

    args = parser.parse_args()

    data = np.load(args.data, allow_pickle=True)
    X, y = data['X'], data['y']

    from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
    balancer = AdaptiveBalancingStrategy(min_samples_per_class=args.min_samples)
    X_bal, y_bal, report = balancer.balance(X, y, BEHAVIOR_TYPES_V2)

    np.savez_compressed(args.output, X=X_bal, y=y_bal)
    print(f"\n均衡数据已保存: {args.output}")
    print(f"  前: {report['before']['n_samples']} 样本, {report['before']['n_classes']} 类")
    print(f"  后: {report['after']['n_samples']} 样本, {report['after']['n_classes']} 类")


if __name__ == '__main__':
    main()