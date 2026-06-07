#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渐进式训练策略: 合成数据 + 真实数据 混合训练

5 阶段渐进式:
  Phase 0: 100% 合成数据 (基准)
  Phase 1: 90% 合成 + 10% 真实
  Phase 2: 50% 合成 + 50% 真实
  Phase 3: 10% 合成 + 90% 真实
  Phase 4: 100% 真实数据

用法:
    from core.core.analysis.progressive_trainer import ProgressiveTrainingStrategy
    trainer = ProgressiveTrainingStrategy()
    results = trainer.train_progressive(X_synth, y_synth, X_real, y_real, train_fn)
"""

import logging
import time
import numpy as np
from typing import Dict, List, Callable, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class ProgressiveTrainingStrategy:
    """渐进式训练策略: 合成 → 真实 平滑迁移"""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)

        self.phases = [
            {'name': 'Phase 0 (基准)', 'synth_weight': 1.0, 'real_weight': 0.0,
             'desc': '纯合成数据基准模型'},
            {'name': 'Phase 1 (注入)', 'synth_weight': 0.9, 'real_weight': 0.1,
             'desc': '真实数据注入 10%'},
            {'name': 'Phase 2 (半混合)', 'synth_weight': 0.5, 'real_weight': 0.5,
             'desc': '合成/真实 50/50 混合'},
            {'name': 'Phase 3 (主导)', 'synth_weight': 0.1, 'real_weight': 0.9,
             'desc': '真实数据主导 90%'},
            {'name': 'Phase 4 (纯真实)', 'synth_weight': 0.0, 'real_weight': 1.0,
             'desc': '纯真实数据模型'},
        ]

    def prepare_mixed_data(
        self,
        X_synth: np.ndarray,
        y_synth: np.ndarray,
        X_real: np.ndarray,
        y_real: np.ndarray,
        phase: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """按阶段混合合成与真实数据

        Args:
            X_synth, y_synth: 合成数据
            X_real, y_real: 真实数据
            phase: 阶段编号 (0-4)

        Returns:
            (X_mixed, y_mixed)
        """
        if phase < 0 or phase >= len(self.phases):
            raise ValueError(f"阶段编号 {phase} 超出范围 [0, {len(self.phases)-1}]")

        p = self.phases[phase]
        n_synth = int(len(X_synth) * p['synth_weight'])
        n_real = int(len(X_real) * p['real_weight'])

        X_parts = []
        y_parts = []
        sources = []

        if n_synth > 0:
            indices = self._rng.choice(len(X_synth), n_synth, replace=False)
            X_parts.append(X_synth[indices])
            y_parts.append(y_synth[indices])
            sources.append(f"合成:{n_synth}")

        if n_real > 0:
            indices = self._rng.choice(len(X_real), n_real, replace=False)
            X_parts.append(X_real[indices])
            y_parts.append(y_real[indices])
            sources.append(f"真实:{n_real}")

        X_mixed = np.vstack(X_parts)
        y_mixed = np.concatenate(y_parts)

        # 打乱
        perm = self._rng.permutation(len(X_mixed))
        X_mixed = X_mixed[perm]
        y_mixed = y_mixed[perm]

        logger.info(f"{p['name']}: {', '.join(sources)} → {len(X_mixed)} 样本, "
                     f"{len(set(y_mixed))} 类")

        return X_mixed, y_mixed

    def train_progressive(
        self,
        X_synth: np.ndarray,
        y_synth: np.ndarray,
        X_real: np.ndarray,
        y_real: np.ndarray,
        train_fn: Callable[[np.ndarray, np.ndarray], dict],
        eval_fn: Optional[Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], dict]] = None,
        class_names: Optional[List[str]] = None,
    ) -> List[Dict]:
        """渐进式训练, 记录每阶段指标

        Args:
            X_synth, y_synth: 合成训练数据
            X_real, y_real: 真实训练数据
            train_fn: 训练函数, 签名 (X, y) → {'model': ..., 'metrics': {...}}
            eval_fn: 评估函数, 签名 (model, X_real_test, y_real_test) → {...}
            class_names: 类别名称列表

        Returns:
            [phase_result, ...] — 每阶段的结果
        """
        results = []
        overall_best = {'phase': -1, 'accuracy': 0.0, 'f1_macro': 0.0}

        for i, phase in enumerate(self.phases):
            logger.info(f"\n{'='*60}")
            logger.info(f"  {phase['name']}: {phase['desc']}")
            logger.info(f"{'='*60}")

            # 混合数据
            X_train, y_train = self.prepare_mixed_data(
                X_synth, y_synth, X_real, y_real, i,
            )

            # 类别分布
            if class_names:
                id_to_name = {idx: name for idx, name in enumerate(class_names)}
                dist = Counter(y_train)
                logger.info(f"类别分布: {len(dist)} 类")
                for cls_id, cnt in dist.most_common(5):
                    name = id_to_name.get(cls_id, f'id_{cls_id}')
                    logger.info(f"  {name}: {cnt}")

            # 训练
            t0 = time.time()
            train_result = train_fn(X_train, y_train)
            train_time = time.time() - t0

            phase_result = {
                'phase': i,
                'name': phase['name'],
                'desc': phase['desc'],
                'synth_weight': phase['synth_weight'],
                'real_weight': phase['real_weight'],
                'n_samples': len(X_train),
                'n_classes': len(set(y_train)),
                'train_time_s': train_time,
                **train_result.get('metrics', {}),
            }

            # 评估
            if eval_fn is not None and 'model' in train_result:
                eval_metrics = eval_fn(
                    train_result['model'], X_real, y_real
                )
                phase_result.update({
                    'eval_accuracy': eval_metrics.get('accuracy', 0),
                    'eval_f1_macro': eval_metrics.get('f1_macro', 0),
                    'eval_f1_weighted': eval_metrics.get('f1_weighted', 0),
                })

            # 追踪最佳
            acc = phase_result.get('accuracy', phase_result.get('eval_accuracy', 0))
            f1 = phase_result.get('f1_macro', phase_result.get('eval_f1_macro', 0))
            if acc > overall_best['accuracy']:
                overall_best = {'phase': i, 'accuracy': acc, 'f1_macro': f1}

            phase_result['is_best'] = (i == overall_best['phase'])
            results.append(phase_result)

            logger.info(f"  准确率: {acc:.4f} ({acc*100:.1f}%)")
            logger.info(f"  F1 Macro: {f1:.4f}")
            logger.info(f"  训练用时: {train_time:.1f}s")

        # 打印汇总
        self._print_summary(results, overall_best)
        return results

    def _print_summary(self, results: List[Dict], best: Dict):
        """打印渐进式训练汇总"""
        print("\n" + "=" * 70)
        print("  渐进式训练汇总")
        print("=" * 70)
        print(f"{'阶段':<20s} {'合成%':>6s} {'真实%':>6s} {'样本':>7s} {'准确率':>8s} {'F1':>8s} {'最佳':>4s}")
        print("-" * 70)

        for r in results:
            best_mark = '*' if r.get('is_best') else ''
            acc = r.get('accuracy', r.get('eval_accuracy', 0))
            f1 = r.get('f1_macro', r.get('eval_f1_macro', 0))
            print(f"{r['name']:<20s} {r['synth_weight']*100:>5.0f}% "
                  f"{r['real_weight']*100:>5.0f}% {r['n_samples']:>7d} "
                  f"{acc:>7.3f} {f1:>7.3f} {best_mark:>4s}")

        print("-" * 70)
        print(f"最佳: Phase {best['phase']} (acc={best['accuracy']:.3f}, f1={best['f1_macro']:.3f})")
        print("=" * 70)


def create_eval_fn(X_test, y_test, class_names):
    """创建评估函数 (闭包)"""
    def eval_fn(model, X_eval, y_eval):
        from sklearn.metrics import accuracy_score, f1_score
        import pandas as pd
        from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter
        adapter = FeatureAdapter()
        X_test_df = pd.DataFrame(X_test, columns=adapter.feature_names)
        y_pred = model.predict(X_test_df)
        return {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'f1_macro': float(f1_score(y_test, y_pred, average='macro', zero_division=0)),
            'f1_weighted': float(f1_score(y_test, y_pred, average='weighted', zero_division=0)),
        }
    return eval_fn


def main():
    """独立测试"""
    import argparse
    import pandas as pd
    parser = argparse.ArgumentParser(description='渐进式训练')
    parser.add_argument('--synth_data', type=str, default='training_data.npz',
                        help='合成数据 .npz')
    parser.add_argument('--real_data', type=str, required=True,
                        help='真实数据 .npz')
    parser.add_argument('--output', type=str, default='training_data_progressive.npz')

    args = parser.parse_args()

    synth = np.load(args.synth_data, allow_pickle=True)
    real = np.load(args.real_data, allow_pickle=True)

    X_synth, y_synth = synth['X'], synth['y']
    X_real, y_real = real['X'], real['y']

    from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
    from core.core.analysis.train_lgbm_model import train_model

    def train_fn(X, y):
        return train_model(X, y, test_size=0.2)

    trainer = ProgressiveTrainingStrategy()
    results = trainer.train_progressive(
        X_synth, y_synth, X_real, y_real,
        train_fn=train_fn,
        class_names=BEHAVIOR_TYPES_V2,
    )

    print(f"\n完成: {len(results)} 个阶段")


if __name__ == '__main__':
    main()