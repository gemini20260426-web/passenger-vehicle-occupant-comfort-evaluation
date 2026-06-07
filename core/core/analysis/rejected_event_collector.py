#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驳回事件采集器 — RejectedEventCollector
═══════════════════════════════════════════════

功能:
  1. 驳回事件特征采集 — 保存被驳回事件的 55 维特征向量
  2. 驳回原因分类 — 物理违规 / 上下文违规 / 互斥事件 / 低转移概率
  3. 增量训练数据生成 — 将驳回事件作为 hard negative 样本
  4. 反馈数据集管理 — 与原始训练数据合并用于 ML 模型重训练

数据流:
  EventConfidenceRefiner → RejectedEventCollector → feedback_dataset.jsonl
                                                        ↓
                                                      FeedbackDataset
                                                        ↓
                                              IncrementalTrainer → LightGBM refit

文件格式:
  feedback_dataset.jsonl 每行一条 JSON:
  {
    "event_type": "emergency_braking",
    "reject_reason": "physics_violation",
    "reject_source": "physics_filter",
    "confidence": 0.85,
    "context_score": 0.51,
    "speed": 0.0,
    "t_start": 1.5,
    "t_end": 2.5,
    "features": [0.1, 0.2, ...],  // 55 维特征向量
    "timestamp": "2026-06-07T13:32:40",
    "dataset_id": "parsed_data_20260607_131304"
  }

阈值:
  - 最小驳回事件数触发重训练: 50
  - 驳回事件在训练集中的权重倍数: 3.0x
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  默认配置
# ═══════════════════════════════════════════════════════════

DEFAULT_FEEDBACK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'data_output',
    'feedback',
)

DEFAULT_FEEDBACK_FILE = 'feedback_dataset.jsonl'
MIN_SAMPLES_FOR_RETRAIN = 50  # 最少驳回样本数才触发重训练
HARD_NEGATIVE_WEIGHT = 3.0    # 驳回样本在训练中的权重倍数


class RejectedEventCollector:
    """驳回事件采集器

    用法:
        collector = RejectedEventCollector()
        collector.collect(rejected_event, features, dataset_id)
        collector.export_for_training()  # 生成 (X, y, sample_weight)
    """

    def __init__(self, feedback_dir: Optional[str] = None):
        self._feedback_dir = feedback_dir or DEFAULT_FEEDBACK_DIR
        os.makedirs(self._feedback_dir, exist_ok=True)
        self._feedback_path = os.path.join(self._feedback_dir, DEFAULT_FEEDBACK_FILE)
        self._buffer: List[Dict] = []
        self._reject_reason_counter = Counter()
        self._reject_source_counter = Counter()

    # ══════════════════════════════════════════════════════
    #  采集
    # ══════════════════════════════════════════════════════

    def collect(self, event: Any, features: np.ndarray,
                dataset_id: str = "") -> Optional[Dict]:
        """采集一个驳回事件

        Args:
            event: RefinedEvent 对象 (verdict='rejected')
            features: 55 维特征向量 (来自 FeatureAdapter)
            dataset_id: 数据集标识 (如文件名)

        Returns:
            采集的记录字典，失败返回 None
        """
        if event.verdict != 'rejected':
            return None

        if features is None or len(features) == 0:
            logger.warning("跳过无特征向量的驳回事件")
            return None

        # 判断驳回来源
        if event.auto_verdict == 'auto_reject':
            reject_source = 'context_review'
        elif not event.physics_pass:
            reject_source = 'physics_filter'
        else:
            reject_source = 'manual'

        record = {
            'event_type': event.event_type,
            'reject_reason': event.review_reason or 'unknown',
            'reject_source': reject_source,
            'confidence': float(event.confidence),
            'context_score': float(getattr(event, 'context_score', 0.0)),
            'speed': float(getattr(event, 'speed', 0.0)),
            't_start': float(event.t_start),
            't_end': float(event.t_end),
            'features': features.tolist() if isinstance(features, np.ndarray) else list(features),
            'timestamp': datetime.now().isoformat(),
            'dataset_id': dataset_id or 'unknown',
        }

        self._buffer.append(record)
        self._reject_reason_counter[event.review_reason or 'unknown'] += 1
        self._reject_source_counter[reject_source] += 1

        return record

    def collect_batch(self, events: List[Any],
                      features_list: Optional[List[np.ndarray]] = None,
                      dataset_id: str = "") -> int:
        """批量采集驳回事件

        Args:
            events: RefinedEvent 列表
            features_list: 对应的特征向量列表 (可选, 与events同序)
            dataset_id: 数据集标识

        Returns:
            采集的驳回事件数
        """
        count = 0

        for i, ev in enumerate(events):
            if ev.verdict != 'rejected':
                continue

            # 优先从事件自身获取特征, 其次从 features_list 按索引获取
            feats = getattr(ev, '_features', None)
            if feats is None and features_list and i < len(features_list):
                feats = features_list[i]

            if feats is not None:
                self.collect(ev, feats, dataset_id)
                count += 1

        logger.info(f"[Collector] 批量采集 {count}/{sum(1 for e in events if e.verdict == 'rejected')} 个驳回事件")
        return count

    # ══════════════════════════════════════════════════════
    #  持久化
    # ══════════════════════════════════════════════════════

    def flush(self) -> int:
        """将缓冲区中的驳回事件写入 JSONL 文件

        Returns:
            写入的记录数
        """
        if not self._buffer:
            return 0

        try:
            with open(self._feedback_path, 'a', encoding='utf-8') as f:
                for record in self._buffer:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

            count = len(self._buffer)
            logger.info(f"[Collector] 持久化 {count} 条驳回事件到 {self._feedback_path}")
            self._buffer.clear()
            return count

        except Exception as e:
            logger.error(f"[Collector] 持久化失败: {e}")
            return 0

    def load_all(self) -> List[Dict]:
        """加载所有已采集的驳回事件

        Returns:
            驳回事件记录列表
        """
        records = []
        if not os.path.exists(self._feedback_path):
            return records

        try:
            with open(self._feedback_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"[Collector] 加载失败: {e}")

        return records

    # ══════════════════════════════════════════════════════
    #  训练数据导出
    # ══════════════════════════════════════════════════════

    def export_for_training(self) -> Optional[Dict[str, Any]]:
        """导出驳回事件为训练数据 (X, y, sample_weight)

        Returns:
            {
                'X': np.ndarray shape=(N, 55),
                'y': np.ndarray shape=(N,),
                'sample_weight': np.ndarray shape=(N,),
                'event_types': List[str],
                'reject_sources': Dict[str, int],
            }
            如果数据不足返回 None
        """
        records = self.load_all()
        if len(records) < MIN_SAMPLES_FOR_RETRAIN:
            logger.info(
                f"[Collector] 驳回样本不足: {len(records)}/{MIN_SAMPLES_FOR_RETRAIN}，跳过"
            )
            return None

        # 构建事件类型到索引的映射
        from ..core_types import BEHAVIOR_TYPES_V2
        event_type_to_idx = {et: i for i, et in enumerate(BEHAVIOR_TYPES_V2)}

        X_list = []
        y_list = []
        w_list = []
        skipped = 0

        for record in records:
            features = record.get('features', [])
            event_type = record.get('event_type', 'normal')

            if len(features) != 55:
                skipped += 1
                continue

            if event_type not in event_type_to_idx:
                skipped += 1
                continue

            X_list.append(features)
            y_list.append(event_type_to_idx[event_type])
            # 硬负样本: 权重 = HARD_NEGATIVE_WEIGHT
            w_list.append(HARD_NEGATIVE_WEIGHT)

        if skipped > 0:
            logger.warning(f"[Collector] 跳过 {skipped} 条无效记录")

        if len(X_list) < MIN_SAMPLES_FOR_RETRAIN:
            logger.info(f"[Collector] 有效驳回样本不足: {len(X_list)}/{MIN_SAMPLES_FOR_RETRAIN}")
            return None

        reject_sources = dict(self._reject_source_counter)

        logger.info(
            f"[Collector] 导出训练数据: {len(X_list)} 条, "
            f"权重={HARD_NEGATIVE_WEIGHT}x, 来源={reject_sources}"
        )

        return {
            'X': np.array(X_list, dtype=np.float32),
            'y': np.array(y_list, dtype=np.int32),
            'sample_weight': np.array(w_list, dtype=np.float32),
            'event_types': list(BEHAVIOR_TYPES_V2),
            'reject_sources': reject_sources,
        }

    # ══════════════════════════════════════════════════════
    #  统计与清理
    # ══════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """获取采集统计"""
        total = len(self.load_all())
        return {
            'total_rejected': total,
            'ready_for_retrain': total >= MIN_SAMPLES_FOR_RETRAIN,
            'min_for_retrain': MIN_SAMPLES_FOR_RETRAIN,
            'hard_negative_weight': HARD_NEGATIVE_WEIGHT,
            'reject_reasons': dict(self._reject_reason_counter.most_common(10)),
            'reject_sources': dict(self._reject_source_counter),
            'buffer_size': len(self._buffer),
            'feedback_file': self._feedback_path,
        }

    def clear(self):
        """清空反馈数据集"""
        if os.path.exists(self._feedback_path):
            os.remove(self._feedback_path)
            logger.info("[Collector] 反馈数据集已清空")
        self._buffer.clear()
        self._reject_reason_counter.clear()
        self._reject_source_counter.clear()

    def get_reject_reasons_summary(self) -> str:
        """获取驳回原因摘要 (供 UI 展示)"""
        total = self._reject_reason_counter.total()
        if total == 0:
            return "暂无驳回事件"

        lines = [f"驳回事件总数: {total}"]
        for reason, count in self._reject_reason_counter.most_common(5):
            pct = count / total * 100
            lines.append(f"  - {reason[:50]}: {count} ({pct:.0f}%)")
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
#  FeedbackDataset — 反馈数据集管理
# ═══════════════════════════════════════════════════════════

class FeedbackDataset:
    """反馈数据集管理器

    管理原始训练数据 + 驳回事件的合并数据集，
    用于 ML 模型增量重训练。

    用法:
        fds = FeedbackDataset()
        X, y, sample_weight = fds.merge(original_X, original_y, rejected_data)
        fds.save_merged(X, y, sample_weight)
    """

    def __init__(self, feedback_dir: Optional[str] = None):
        self._feedback_dir = feedback_dir or DEFAULT_FEEDBACK_DIR
        os.makedirs(self._feedback_dir, exist_ok=True)
        self._merged_path = os.path.join(self._feedback_dir, 'merged_training_data.npz')

    def merge(self, original_X: np.ndarray, original_y: np.ndarray,
              rejected_data: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """合并原始训练数据和驳回事件

        Args:
            original_X: 原始训练特征 shape=(N, 55)
            original_y: 原始训练标签 shape=(N,)
            rejected_data: RejectedEventCollector.export_for_training() 的输出

        Returns:
            {'X': merged_X, 'y': merged_y, 'sample_weight': merged_weights}
        """
        N_orig = len(original_X)
        N_rej = len(rejected_data['X'])

        # 合并特征和标签
        merged_X = np.vstack([original_X, rejected_data['X']])
        merged_y = np.concatenate([original_y, rejected_data['y']])

        # 权重: 原始数据 = 1.0, 驳回数据 = HARD_NEGATIVE_WEIGHT
        merged_weights = np.ones(N_orig + N_rej, dtype=np.float32)
        merged_weights[N_orig:] = HARD_NEGATIVE_WEIGHT

        logger.info(
            f"[FeedbackDataset] 合并数据集: {N_orig} 原始 + {N_rej} 驳回 = "
            f"{N_orig + N_rej} 总样本, 硬负样本权重={HARD_NEGATIVE_WEIGHT}x"
        )

        return {
            'X': merged_X,
            'y': merged_y,
            'sample_weight': merged_weights,
        }

    def save_merged(self, X: np.ndarray, y: np.ndarray,
                    sample_weight: np.ndarray, metadata: Optional[Dict] = None):
        """保存合并后的数据集"""
        save_data = {
            'X': X,
            'y': y,
            'sample_weight': sample_weight,
        }
        if metadata:
            save_data['metadata'] = metadata

        np.savez_compressed(self._merged_path, **save_data)
        logger.info(f"[FeedbackDataset] 合并数据集已保存: {self._merged_path}")

    def load_merged(self) -> Optional[Dict[str, np.ndarray]]:
        """加载合并后的数据集"""
        if not os.path.exists(self._merged_path):
            return None

        data = np.load(self._merged_path, allow_pickle=True)
        return {
            'X': data['X'],
            'y': data['y'],
            'sample_weight': data['sample_weight'],
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取数据集统计"""
        data = self.load_merged()
        if data is None:
            return {'status': 'empty', 'total_samples': 0}

        N = len(data['y'])
        hard_neg = int(np.sum(data['sample_weight'] > 1.0))
        orig = N - hard_neg

        return {
            'status': 'ready',
            'total_samples': N,
            'original_samples': orig,
            'hard_negative_samples': hard_neg,
            'hard_negative_weight': HARD_NEGATIVE_WEIGHT,
            'file': self._merged_path,
        }


# ═══════════════════════════════════════════════════════════
#  IncrementalTrainer — 增量训练器
# ═══════════════════════════════════════════════════════════

class IncrementalTrainer:
    """增量训练器

    使用驳回事件触发 LightGBM 模型重训练。

    用法:
        trainer = IncrementalTrainer(collector, feedback_dataset)
        success = trainer.retrain_if_needed(clf)  # 满足条件则重训练
        stats = trainer.get_stats()
    """

    def __init__(self, collector: Optional[RejectedEventCollector] = None,
                 feedback_dataset: Optional[FeedbackDataset] = None):
        self._collector = collector or RejectedEventCollector()
        self._feedback_dataset = feedback_dataset or FeedbackDataset()
        self._retrain_count = 0
        self._last_retrain_time: Optional[float] = None
        self._improvement_log: List[Dict] = []

    def retrain_if_needed(self, clf: Any,
                          original_X: Optional[np.ndarray] = None,
                          original_y: Optional[np.ndarray] = None) -> bool:
        """如果驳回事件足够多，执行增量重训练

        Args:
            clf: LightGBMClassifier 实例
            original_X: 原始训练特征 (可选)
            original_y: 原始训练标签 (可选)

        Returns:
            True 如果执行了重训练
        """
        # 1. 导出驳回事件数据
        rejected_data = self._collector.export_for_training()
        if rejected_data is None:
            return False

        # 2. 获取原始训练数据
        if original_X is None or original_y is None:
            merged = self._feedback_dataset.load_merged()
            if merged is None:
                logger.warning("[IncrementalTrainer] 无原始训练数据，仅使用驳回样本训练")
                original_X = np.empty((0, 55), dtype=np.float32)
                original_y = np.empty((0,), dtype=np.int32)
            else:
                original_X = merged['X']
                original_y = merged['y']

        # 3. 合并数据集
        merged = self._feedback_dataset.merge(original_X, original_y, rejected_data)
        X = merged['X']
        y = merged['y']
        sample_weight = merged['sample_weight']

        # 4. 记录重训练前准确率
        if hasattr(clf, '_model') and clf._model is not None and clf._is_trained:
            try:
                old_pred = clf._model.predict(X)
                from sklearn.metrics import accuracy_score
                old_acc = float(accuracy_score(y, old_pred, sample_weight=sample_weight))
            except Exception:
                old_acc = 0.0
        else:
            old_acc = 0.0

        # 5. 重训练
        logger.info(
            f"[IncrementalTrainer] 开始重训练: {len(X)} 样本, "
            f"驳回={len(rejected_data['X'])}, 权重={HARD_NEGATIVE_WEIGHT}x"
        )

        try:
            clf.train(X, y, sample_weight=sample_weight)

            # 6. 记录重训练后准确率
            new_pred = clf._model.predict(X)
            from sklearn.metrics import accuracy_score
            new_acc = float(accuracy_score(y, new_pred, sample_weight=sample_weight))

            improvement = new_acc - old_acc
            logger.info(
                f"[IncrementalTrainer] 重训练完成: acc {old_acc:.4f} → {new_acc:.4f} "
                f"({improvement:+.4f})"
            )

            # 7. 保存合并数据集
            self._feedback_dataset.save_merged(X, y, sample_weight, {
                'retrain_count': self._retrain_count + 1,
                'old_accuracy': old_acc,
                'new_accuracy': new_acc,
                'improvement': improvement,
                'rejected_count': len(rejected_data['X']),
                'timestamp': datetime.now().isoformat(),
            })

            # 8. 保存新模型
            from .layer4_behavior_classification.model_persistence import ModelPersistence
            persistence = ModelPersistence()
            persistence.save(
                clf._model,
                clf.EVENT_TYPES,
                clf._feature_adapter.get_feature_names(),
                {
                    'accuracy': new_acc,
                    'retrain_count': self._retrain_count + 1,
                    'rejected_samples': len(rejected_data['X']),
                    'training_data_source': 'mixed',
                },
            )

            # 9. 更新统计
            self._retrain_count += 1
            self._last_retrain_time = time.time()
            self._improvement_log.append({
                'retrain': self._retrain_count,
                'old_acc': old_acc,
                'new_acc': new_acc,
                'improvement': improvement,
                'rejected_samples': len(rejected_data['X']),
                'total_samples': len(X),
                'timestamp': datetime.now().isoformat(),
            })

            # 10. 清空驳回事件缓存
            self._collector.clear()

            return True

        except Exception as e:
            logger.error(f"[IncrementalTrainer] 重训练失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取训练统计"""
        collector_stats = self._collector.get_stats()
        dataset_stats = self._feedback_dataset.get_stats()

        return {
            'retrain_count': self._retrain_count,
            'last_retrain': (
                datetime.fromtimestamp(self._last_retrain_time).isoformat()
                if self._last_retrain_time else 'never'
            ),
            'collector': collector_stats,
            'dataset': dataset_stats,
            'recent_improvements': self._improvement_log[-5:],
        }

    def get_improvement_summary(self) -> str:
        """获取训练改进摘要 (供 UI 展示)"""
        if not self._improvement_log:
            return "暂无增量训练记录"

        latest = self._improvement_log[-1]
        lines = [
            f"增量训练 #{latest['retrain']}",
            f"  准确率: {latest['old_acc']:.4f} → {latest['new_acc']:.4f} "
            f"({latest['improvement']:+.4f})",
            f"  驳回样本: {latest['rejected_samples']}",
            f"  总样本: {latest['total_samples']}",
        ]
        return '\n'.join(lines)