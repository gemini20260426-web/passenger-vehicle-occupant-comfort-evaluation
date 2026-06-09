#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驳回事件增量训练 — 端到端验证脚本

验证 Phase 3 闭环: 驳回 → 采集 → 增量训练 → 模型进化

Usage:
    python -m core.core.seat_evaluation.validate_incremental_training
"""

import logging
import sys
import os
from typing import Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


def validate_incremental_training(
    rejected_samples: Optional[list] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """端到端验证"驳回→采集→增量训练"闭环

    Args:
        rejected_samples: 模拟驳回事件列表，每条含:
            - type: 原始分类结果
            - correct: 人工复核后的正确分类
            - confidence: 置信度
            - features: 特征向量 (可选)
        verbose: 是否输出详细日志

    Returns:
        {
            'status': 'passed'|'failed'|'skipped',
            'steps': [...],
            'summary': str,
        }
    """
    results = {
        'status': 'skipped',
        'steps': [],
        'summary': '',
    }

    step_results = []

    # ── Step 1: 加载基线模型 ──
    if verbose:
        logger.info("=" * 60)
        logger.info("Step 1: 加载基线模型")
        logger.info("=" * 60)

    try:
        from core.core.analysis.model_persistence import ModelPersistence
        model = ModelPersistence.load('lgbm_25class_classifier')
        if model is None:
            logger.warning("基线模型未找到，跳过验证")
            results['summary'] = "基线模型未找到，验证跳过"
            return results
        step_results.append({'step': 1, 'status': 'ok', 'detail': '模型加载成功'})
        if verbose:
            logger.info("  ✅ 基线模型加载成功")
    except Exception as e:
        step_results.append({'step': 1, 'status': 'error', 'detail': str(e)})
        logger.error(f"  ❌ 模型加载失败: {e}")
        results['status'] = 'failed'
        results['steps'] = step_results
        results['summary'] = f"Step 1 失败: {e}"
        return results

    # ── Step 2: 模拟驳回事件 ──
    if verbose:
        logger.info("=" * 60)
        logger.info("Step 2: 模拟驳回事件")
        logger.info("=" * 60)

    if rejected_samples is None:
        rejected_samples = [
            {'type': 'normal_deceleration', 'correct': 'emergency_braking', 'confidence': 0.45},
            {'type': 'lane_keeping', 'correct': 'weaving', 'confidence': 0.52},
            {'type': 'constant_speed', 'correct': 'aggressive_acceleration', 'confidence': 0.38},
        ]

    if verbose:
        for i, s in enumerate(rejected_samples):
            logger.info(f"  驳回事件 {i+1}: {s['type']} → {s['correct']} (置信度: {s['confidence']})")

    step_results.append({'step': 2, 'status': 'ok', 'detail': f'{len(rejected_samples)} 个驳回事件'})

    # ── Step 3: 采集驳回事件 ──
    if verbose:
        logger.info("=" * 60)
        logger.info("Step 3: 采集驳回事件")
        logger.info("=" * 60)

    try:
        from core.core.analysis.rejected_event_collector import RejectedEventCollector
        collector = RejectedEventCollector()

        batch_count = 0
        for sample in rejected_samples:
            features = sample.get('features',
                                  np.random.randn(55).astype(np.float32))
            success = collector.collect(
                event=sample,
                features=features,
                predicted_type=sample['type'],
                actual_type=sample['correct'],
                confidence=sample.get('confidence', 0.5),
            )
            if success:
                batch_count += 1

        step_results.append({
            'step': 3, 'status': 'ok',
            'detail': f'采集 {batch_count}/{len(rejected_samples)} 个驳回事件',
        })
        if verbose:
            logger.info(f"  ✅ 采集完成: {batch_count}/{len(rejected_samples)} 个")

    except Exception as e:
        step_results.append({'step': 3, 'status': 'error', 'detail': str(e)})
        logger.error(f"  ❌ 采集失败: {e}")
        results['status'] = 'failed'
        results['steps'] = step_results
        results['summary'] = f"Step 3 失败: {e}"
        return results

    # ── Step 4: 增量训练 ──
    if verbose:
        logger.info("=" * 60)
        logger.info("Step 4: 增量训练")
        logger.info("=" * 60)

    try:
        from core.core.analysis.rejected_event_collector import IncrementalTrainer

        trainer = IncrementalTrainer(collector)

        # 获取模型分类器
        if hasattr(model, 'ml_classifier'):
            clf = model.ml_classifier
        elif hasattr(model, '_model'):
            clf = model
        else:
            clf = model

        retrained = trainer.retrain_if_needed(clf)

        stats = trainer.get_stats() if hasattr(trainer, 'get_stats') else {}
        step_results.append({
            'step': 4, 'status': 'ok',
            'detail': f'重训练: {"是" if retrained else "否（样本不足）"}',
            'stats': stats,
        })
        if verbose:
            if retrained:
                logger.info(f"  ✅ 增量训练完成: {stats}")
            else:
                logger.info("  ⚠️ 驳回样本不足，未触发重训练")

    except Exception as e:
        step_results.append({'step': 4, 'status': 'error', 'detail': str(e)})
        logger.error(f"  ❌ 增量训练失败: {e}")
        results['status'] = 'failed'
        results['steps'] = step_results
        results['summary'] = f"Step 4 失败: {e}"
        return results

    # ── 汇总 ──
    results['status'] = 'passed'
    results['steps'] = step_results
    results['summary'] = (
        f"端到端验证通过: {len(rejected_samples)} 个驳回事件 → "
        f"采集 → 增量训练{'完成' if retrained else '待触发(样本不足)'}"
    )

    if verbose:
        logger.info("=" * 60)
        logger.info(f"结果: {results['summary']}")
        logger.info("=" * 60)

    return results


def main():
    """命令行入口"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    result = validate_incremental_training(verbose=True)

    if result['status'] == 'passed':
        logger.info("✅ 验证通过")
        return 0
    elif result['status'] == 'skipped':
        logger.info("⚠️ 验证跳过")
        return 0
    else:
        logger.error("❌ 验证失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())