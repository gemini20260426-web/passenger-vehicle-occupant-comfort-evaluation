#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合行为分类器 — Layer 4 编排器 (Phase 2 增强版)

候选源:
  1. PhysicsRuleEngine    — 硬阈值规则 (Stage1 预检, 可解释)
  2. StatisticalClassifier — 统计置信度调整 (保留作回退)
  3. LightGBMClassifier    — ML 多分类器 (Phase 1 主力, Phase 2 校准)
  4. ContextWindow         — 上下文序列增强 (Phase 2 新增)
  5. ContextAwareThresholds — 速度/场景自适应调整 (保留)

Phase 2 增强:
  - 概率校准: Platt Scaling + 温度缩放 (ML 输出)
  - 上下文窗口: 滑动窗口 + 转移概率 + 序列模式
  - 权重调整: ML 权重 0.45→0.40, 上下文窗口 0.15

融合策略: MultiBehaviorResolver 加权投票
"""

import logging
from typing import Optional, Tuple
from ..core_types import ManeuverEvent, FrameFeatures, BehaviorCategory
from .rule_engine import PhysicsRuleEngine
from .statistical_classifier import StatisticalClassifier
from .context_aware_thresholds import ContextAwareThresholds
from .multi_behavior_resolver import MultiBehaviorResolver
from .ml_classifier import LightGBMClassifier
from .context_window import ContextWindow


class HybridBehaviorClassifier:
    """L4 混合行为分类器 — 规则 + 统计 + ML + 上下文 (Phase 2)

    用法:
        clf = HybridBehaviorClassifier()
        clf.load_ml_model()  # 可选: 加载预训练 LightGBM 模型
        event = clf.classify(event, features)
    """

    def __init__(self, context_window_size: int = 10):
        self._logger = logging.getLogger(__name__)
        self._rule_engine = PhysicsRuleEngine()
        self._statistical = StatisticalClassifier()
        self._ml_classifier = LightGBMClassifier()
        self._context = ContextAwareThresholds()
        self._context_window = ContextWindow(window_size=context_window_size)
        self._resolver = MultiBehaviorResolver()

        # 尝试加载预训练模型 (静默失败)
        try:
            self._ml_classifier.load_or_train()
            if self._ml_classifier.is_ready():
                self._logger.info("LightGBM 模型已加载，ML 分类就绪")
                if self._ml_classifier.calibrator.is_fitted():
                    self._logger.info("概率校准器已就绪 (Phase 2)")
            else:
                self._logger.info("LightGBM 模型未训练，将使用规则+统计模式")
        except Exception as e:
            self._logger.warning(f"LightGBM 模型加载失败，使用规则+统计模式: {e}")

    def classify(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> ManeuverEvent:
        """分类入口 — 五源融合 (Phase 2)

        Args:
            event: L3 检测到的候选事件
            features: L2 提取的 FrameFeatures

        Returns:
            分类后的 ManeuverEvent (type/category/confidence 已更新)
        """
        candidates = []

        # 候选源 1: 规则引擎 (Stage1 预检, 权重 0.25)
        rule_result = self._rule_engine.classify(event, features)
        candidates.append(rule_result)

        # 候选源 2: 统计分类器 (保留回退, 权重 0.10)
        stat_result = self._statistical.classify(event, features)
        candidates.append(stat_result)

        # 候选源 3: LightGBM ML 分类器 (主力, 权重 0.40)
        if self._ml_classifier.is_ready():
            ml_result = self._ml_classifier.classify(event, features)
            candidates.append(ml_result)

        # 候选源 4: 上下文窗口 (Phase 2 新增, 权重 0.15)
        ctx_win_type, ctx_win_conf = self._context_window.adjust(
            event.type, event.category, event.confidence
        )
        candidates.append((ctx_win_type, event.category, ctx_win_conf))

        # 候选源 5: 速度/场景自适应 (权重 0.10)
        ctx_result = self._context.adjust(event)
        candidates.append(ctx_result)

        final_behavior, final_category, final_confidence = self._resolver.resolve(candidates)

        event.type = final_behavior
        event.category = final_category
        event.confidence = final_confidence
        event.detection_method = "hybrid_ml_v2" if self._ml_classifier.is_ready() else "hybrid"

        # Phase 2: 将分类结果推入上下文窗口
        self._context_window.push(final_behavior, final_category, final_confidence)

        return event

    def load_ml_model(self, X=None, y=None) -> bool:
        """显式加载或训练 ML 模型

        Args:
            X: 训练特征矩阵 (可选)
            y: 训练标签 (可选)

        Returns:
            True 如果 ML 模型已就绪
        """
        return self._ml_classifier.load_or_train(X, y)

    def train_ml_model(self, X, y, X_val=None, y_val=None, fit_calibrator: bool = True):
        """训练 ML 模型 (Phase 2: 自动拟合校准器)

        Args:
            X: 训练特征 shape=(N, 55)
            y: 训练标签 shape=(N,)
            X_val: 验证特征 (可选)
            y_val: 验证标签 (可选)
            fit_calibrator: 是否同时拟合概率校准器 (Phase 2)

        Returns:
            训练指标字典
        """
        metrics = self._ml_classifier.train(X, y, X_val, y_val)

        # Phase 2: 在验证集上拟合概率校准器
        if fit_calibrator and X_val is not None and y_val is not None:
            cal_metrics = self._ml_classifier.fit_calibrator(X_val, y_val, method='both')
            metrics['calibration'] = cal_metrics

        return metrics

    def fit_ml_calibrator(self, X_val, y_val, method: str = 'both'):
        """Phase 2: 显式拟合 ML 概率校准器"""
        return self._ml_classifier.fit_calibrator(X_val, y_val, method=method)

    @property
    def context_window(self) -> ContextWindow:
        """获取上下文窗口 (Phase 2, 用于调试)"""
        return self._context_window

    @property
    def ml_classifier(self) -> LightGBMClassifier:
        """获取 ML 分类器实例 (用于外部访问特征重要性等)"""
        return self._ml_classifier

    def get_ml_feature_importance(self):
        """获取 ML 模型特征重要性"""
        return self._ml_classifier.get_feature_importance()

    def reset(self):
        self._rule_engine.reset()
        self._statistical.reset()
        self._ml_classifier.reset()
        self._context.reset()
        self._context_window.reset()
        self._resolver.reset()
