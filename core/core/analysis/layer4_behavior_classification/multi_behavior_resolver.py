#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多行为共存消解器 — 加权投票融合 (Phase 2)

候选源 (来自 HybridBehaviorClassifier):
  1. PhysicsRuleEngine    — 权重 0.25
  2. StatisticalClassifier — 权重 0.10
  3. LightGBMClassifier    — 权重 0.40 (ML 主力, Phase 2 校准)
  4. ContextWindow         — 权重 0.15 (Phase 2 新增)
  5. ContextAwareThresholds — 权重 0.10

融合策略:
  当候选源 ≥ 3 时: 加权投票 (按事件类型聚合置信度 × 权重)
  当候选源 < 3 时: 优先级排序 (回退兼容)
"""

from typing import Dict, List, Tuple
from collections import defaultdict
from ..core_types import ManeuverEvent, BehaviorCategory


class MultiBehaviorResolver:
    """多行为共存消解器 — 加权投票融合"""

    # 事件优先级 (用于回退模式: 候选源 < 3 时)
    PRIORITY = {
        "emergency_braking": 100,
        "severe_bump": 97,
        "skid_risk": 95,
        "rollover_risk": 94,
        "u_turn": 90,
        "rapid_direction_change": 85,
        "aggressive_acceleration": 80,
        "aggressive_deceleration": 80,
        "weaving": 75,
        "cornering_braking": 70,
        "cornering_acceleration": 65,
        "cornering_deceleration": 65,
        "lane_change": 60,
        "tight_turn": 55,
        "wide_turn": 50,
        "normal_acceleration": 40,
        "normal_deceleration": 40,
        "launch": 35,
        "lane_keeping": 30,
        "straight_driving": 30,
        "constant_speed": 30,
        "stopped": 20,
        "sensor_fault": 10,
        "normal": 0,
    }

    # 候选源权重 (按位置索引: 0=规则, 1=统计, 2=ML, 3=上下文窗口, 4=速度上下文)
    # Phase 2 调整: ML 0.45→0.40, 新增上下文窗口 0.15
    SOURCE_WEIGHTS = [0.25, 0.10, 0.40, 0.15, 0.10]

    def __init__(self):
        pass

    def resolve(self, candidates: List[Tuple[str, BehaviorCategory, float]]) -> Tuple[str, BehaviorCategory, float]:
        """多候选源融合

        Args:
            candidates: [(事件类型, 行为类别, 置信度), ...]
                       按顺序: [规则, 统计, ML?, 上下文]

        Returns:
            (最终事件类型, 行为类别, 融合置信度)
        """
        if not candidates:
            return ("normal", BehaviorCategory.NORMAL, 0.5)

        if len(candidates) == 1:
            return candidates[0]

        # ── 候选源 ≥ 3: 加权投票 ──
        if len(candidates) >= 3:
            return self._weighted_vote(candidates)

        # ── 回退: 优先级排序 (候选源 < 3, 无 ML 模型时) ──
        return self._priority_resolve(candidates)

    def _weighted_vote(
        self, candidates: List[Tuple[str, BehaviorCategory, float]]
    ) -> Tuple[str, BehaviorCategory, float]:
        """加权投票融合

        对每个候选源，将其置信度乘以权重，按事件类型聚合。
        选择加权总分最高的事件类型。

        Args:
            candidates: 候选结果列表

        Returns:
            融合后的 (事件类型, 行为类别, 置信度)
        """
        # 聚合: {事件类型: 加权总分}
        score_map: Dict[str, float] = defaultdict(float)
        type_to_category: Dict[str, BehaviorCategory] = {}

        for i, (event_type, category, confidence) in enumerate(candidates):
            w = self.SOURCE_WEIGHTS[i] if i < len(self.SOURCE_WEIGHTS) else 0.05
            score_map[event_type] += confidence * w
            type_to_category[event_type] = category

        if not score_map:
            return ("normal", BehaviorCategory.NORMAL, 0.5)

        # 选出加权总分最高的类型
        best_type = max(score_map, key=score_map.get)
        best_score = score_map[best_type]
        best_category = type_to_category.get(best_type, BehaviorCategory.NORMAL)

        # 归一化置信度到 [0, 1]
        total_weight = sum(
            self.SOURCE_WEIGHTS[i] if i < len(self.SOURCE_WEIGHTS) else 0.05
            for i in range(len(candidates))
        )
        normalized_confidence = min(best_score / max(total_weight, 0.01), 1.0)

        return best_type, best_category, normalized_confidence

    def _priority_resolve(
        self, candidates: List[Tuple[str, BehaviorCategory, float]]
    ) -> Tuple[str, BehaviorCategory, float]:
        """优先级排序回退 (原有逻辑，候选源 < 3 时使用)"""
        sorted_candidates = sorted(
            candidates,
            key=lambda x: self.PRIORITY.get(x[0], 0),
            reverse=True,
        )
        return sorted_candidates[0]

    def reset(self):
        pass
