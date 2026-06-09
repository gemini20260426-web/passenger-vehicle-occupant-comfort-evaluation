#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文驱动的自动复核引擎 — ContextReviewEngine
═══════════════════════════════════════════════════════════

基于现有 ContextWindow 的转移概率矩阵和序列模式，
在事件复核阶段自动判定事件，减少人工复核工作量。

核心逻辑:
  1. 转移概率评分: 高概率转移 → auto_confirm, 低概率 → auto_reject
  2. 序列模式匹配: 匹配已知驾驶模式 → auto_confirm
  3. 互斥事件检测: 互斥事件对 → auto_reject
  4. 类别一致性: 连续同类事件 → 提升置信度

集成:
  EventConfidenceRefiner.refine() → ContextReviewEngine.review_sequence()
  → auto_confirm / auto_reject / needs_review

预期效果:
  自动确认率: ~40% → ~65%
  需人工复核率: ~55% → ~25%
  自动驳回率: ~5% → ~10%
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

# 复用 context_window 的转移概率矩阵和序列模式
from .layer4_behavior_classification.context_window import (
    _HIGH_TRANSITIONS,
    _LOW_TRANSITIONS,
    _SEQUENCE_PATTERNS,
    _DEFAULT_TRANSITION_PROB,
)

# 复用 event_confidence_refiner 的互斥规则和物理转移矩阵
from .event_confidence_refiner import (
    EVENT_MUTUAL_EXCLUSIONS,
    PHYSICS_TRANSITIONS,
    RefinedEvent,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  自动复核阈值配置
# ═══════════════════════════════════════════════════════════

# 自动确认: 转移概率 ≥ 此值 且 置信度 ≥ 置信度下限
AUTO_CONFIRM_TRANSITION_PROB = 0.30
AUTO_CONFIRM_MIN_CONFIDENCE = 0.70

# 自动驳回: 转移概率 ≤ 此值 (或互斥)
AUTO_REJECT_TRANSITION_PROB = 0.05

# 序列模式匹配加成
SEQUENCE_MATCH_BOOST = 0.08

# 类别一致性加成
CATEGORY_CONSISTENCY_BOOST = 0.05

# 自动驳回时置信度惩罚系数
AUTO_REJECT_CONFIDENCE_PENALTY = 0.55

# ═══════════════════════════════════════════════════════════
#  事件类别映射 (与 _get_category 对齐)
# ═══════════════════════════════════════════════════════════

_LONGITUDINAL = {
    'emergency_braking', 'aggressive_deceleration', 'aggressive_acceleration',
    'normal_deceleration', 'normal_acceleration', 'launch', 'constant_speed',
    'stopped', 'cruising', 'overspeeding',
}

_LATERAL = {
    'weaving', 'lane_change', 'rapid_direction_change', 'tight_turn',
    'wide_turn', 'u_turn', 'straight_driving', 'lane_keeping',
}

_COMPOSITE = {
    'cornering_braking', 'cornering_acceleration', 'cornering_deceleration',
}

_ANOMALY = {
    'severe_bump', 'skid_risk', 'rollover_risk', 'sensor_fault',
}

_STATE = {
    'parked', 'normal',
}


def _get_category(event_type: str) -> str:
    """获取事件类别"""
    if event_type in _LONGITUDINAL:
        return 'longitudinal'
    if event_type in _LATERAL:
        return 'lateral'
    if event_type in _COMPOSITE:
        return 'composite'
    if event_type in _ANOMALY:
        return 'anomaly'
    if event_type in _STATE:
        return 'state'
    return 'unknown'


# ═══════════════════════════════════════════════════════════
#  ContextReviewEngine
# ═══════════════════════════════════════════════════════════

class ContextReviewEngine:
    """上下文驱动的自动复核引擎

    用法:
        engine = ContextReviewEngine()
        reviewed = engine.review_sequence(refined_events)
        stats = engine.get_stats()
    """

    def __init__(
        self,
        confirm_transition_prob: float = AUTO_CONFIRM_TRANSITION_PROB,
        confirm_min_confidence: float = AUTO_CONFIRM_MIN_CONFIDENCE,
        reject_transition_prob: float = AUTO_REJECT_TRANSITION_PROB,
    ):
        self._confirm_transition_prob = confirm_transition_prob
        self._confirm_min_confidence = confirm_min_confidence
        self._reject_transition_prob = reject_transition_prob

        # 统计
        self._stats = {
            'auto_confirm': 0,
            'auto_reject': 0,
            'sequence_match': 0,
            'category_consistency': 0,
            'mutual_exclusion': 0,
            'low_transition': 0,
            'needs_review': 0,
        }

    # ══════════════════════════════════════════════════════
    #  主入口: 序列级自动复核
    # ══════════════════════════════════════════════════════

    def review_sequence(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """对事件序列进行上下文驱动的自动复核

        对每个事件依次:
          1. 跳过已物理驳回的 (verdict == 'rejected')
          2. 转移概率评分 → auto_confirm / auto_reject
          3. 序列模式匹配 → auto_confirm
          4. 互斥事件检测 → auto_reject
          5. 类别一致性 → 提升置信度
          6. 综合判定

        Args:
            events: 三路融合 + HMM + 物理过滤后的 RefinedEvent 列表

        Returns:
            更新了 verdict / auto_verdict / context_score 的事件列表
        """
        if not events:
            return events

        self._reset_stats()

        for i, ev in enumerate(events):
            # 跳过已物理驳回的
            if ev.verdict == 'rejected':
                ev.auto_verdict = 'rejected'
                ev.context_score = ev.confidence
                continue

            ev.auto_verdict = ''
            ev.context_score = ev.confidence

            prev_ev = events[i - 1] if i > 0 else None

            # ── 1. 转移概率评分 ──
            if prev_ev and prev_ev.verdict != 'rejected':
                self._apply_transition_review(ev, prev_ev)

            # ── 2. 序列模式匹配 ──
            if not ev.auto_verdict:
                self._apply_sequence_pattern(events, i)

            # ── 3. 互斥事件检测 ──
            if prev_ev and not ev.auto_verdict:
                self._apply_mutual_exclusion(ev, prev_ev)

            # ── 4. 类别一致性 ──
            if not ev.auto_verdict:
                self._apply_category_consistency(ev, events, i)

            # ── 5. 综合判定 ──
            self._finalize_verdict(ev)

        self._log_summary(events)
        return events

    # ══════════════════════════════════════════════════════
    #  各判定步骤
    # ══════════════════════════════════════════════════════

    def _apply_transition_review(self, ev: RefinedEvent, prev_ev: RefinedEvent):
        """基于转移概率自动判定"""
        prev_type = prev_ev.event_type
        curr_type = ev.event_type

        trans_prob = self._get_transition_prob(prev_type, curr_type)

        if trans_prob >= self._confirm_transition_prob and ev.confidence >= self._confirm_min_confidence:
            # 高概率转移 + 高置信度 → 自动确认
            ev.auto_verdict = 'auto_confirm'
            ev.context_score = min(0.995, ev.confidence + 0.05)
            ev.review_reason = (
                f"上下文支持: {prev_type}→{curr_type} (P={trans_prob:.2f})"
            )
            self._stats['auto_confirm'] += 1

        elif trans_prob <= self._reject_transition_prob:
            # 极低概率转移 → 自动驳回
            ev.auto_verdict = 'auto_reject'
            ev.context_score = ev.confidence * AUTO_REJECT_CONFIDENCE_PENALTY
            ev.review_reason = (
                f"上下文反对: {prev_type}→{curr_type} (P={trans_prob:.3f})"
            )
            self._stats['auto_reject'] += 1
            self._stats['low_transition'] += 1

    def _apply_sequence_pattern(self, events: List[RefinedEvent], idx: int):
        """检测已知序列模式"""
        ev = events[idx]

        for pattern_name, pattern_info in _SEQUENCE_PATTERNS.items():
            pattern = pattern_info['sequence']
            pattern_len = len(pattern)

            if idx + 1 >= pattern_len:
                # 取最近 pattern_len 个事件 (含当前)
                tail = [events[idx - pattern_len + 1 + k].event_type for k in range(pattern_len)]
                if tail == pattern:
                    ev.auto_verdict = 'auto_confirm'
                    ev.context_score = min(0.995, ev.confidence + pattern_info['boost'])
                    ev.review_reason = (
                        f"序列模式匹配: {pattern_info['description']} (+{pattern_info['boost']:.2f})"
                    )
                    self._stats['auto_confirm'] += 1
                    self._stats['sequence_match'] += 1
                    return

    def _apply_mutual_exclusion(self, ev: RefinedEvent, prev_ev: RefinedEvent):
        """互斥事件检测"""
        prev_type = prev_ev.event_type
        curr_type = ev.event_type

        is_mutual = (
            (prev_type, curr_type) in EVENT_MUTUAL_EXCLUSIONS
            or (curr_type, prev_type) in EVENT_MUTUAL_EXCLUSIONS
        )

        if is_mutual:
            ev.auto_verdict = 'auto_reject'
            ev.context_score = ev.confidence * 0.45
            ev.review_reason = f"互斥事件: {prev_type}→{curr_type}"
            self._stats['auto_reject'] += 1
            self._stats['mutual_exclusion'] += 1

    def _apply_category_consistency(self, ev: RefinedEvent, events: List[RefinedEvent], idx: int):
        """类别一致性检查"""
        if idx < 2:
            return

        current_cat = _get_category(ev.event_type)
        recent = events[idx - 2:idx]  # 前2个事件

        same_cat_count = sum(1 for e in recent if _get_category(e.event_type) == current_cat)

        if same_cat_count >= 2:
            # 连续同类事件，小幅提升 → 可能促成自动确认
            ev.context_score = min(0.995, ev.confidence + CATEGORY_CONSISTENCY_BOOST)
            if ev.context_score >= self._confirm_min_confidence + 0.05:
                ev.auto_verdict = 'auto_confirm'
                ev.review_reason = f"类别一致性: 连续{current_cat}事件"
                self._stats['auto_confirm'] += 1
                self._stats['category_consistency'] += 1

    def _finalize_verdict(self, ev: RefinedEvent):
        """综合判定: 将 auto_verdict 写入 verdict"""
        if ev.auto_verdict == 'auto_confirm':
            ev.verdict = 'confirmed'
            ev.requires_review = False
        elif ev.auto_verdict == 'auto_reject':
            ev.verdict = 'rejected'
            ev.requires_review = False
        else:
            # 保持 disputed → 仍需人工复核
            ev.auto_verdict = ''
            self._stats['needs_review'] += 1

    # ══════════════════════════════════════════════════════
    #  转移概率查询
    # ══════════════════════════════════════════════════════

    def _get_transition_prob(self, prev_type: str, curr_type: str) -> float:
        """获取 (prev_type → curr_type) 的转移概率

        优先级:
          1. _HIGH_TRANSITIONS (精确匹配)
          2. _LOW_TRANSITIONS (精确匹配)
          3. PHYSICS_TRANSITIONS (稀疏矩阵)
          4. _DEFAULT_TRANSITION_PROB (默认)
        """
        pair = (prev_type, curr_type)

        # 1. 高概率转移
        if pair in _HIGH_TRANSITIONS:
            return _HIGH_TRANSITIONS[pair]

        # 2. 低概率转移
        if pair in _LOW_TRANSITIONS:
            return _LOW_TRANSITIONS[pair]

        # 3. 物理转移矩阵
        if prev_type in PHYSICS_TRANSITIONS:
            trans = PHYSICS_TRANSITIONS[prev_type]
            if curr_type in trans:
                return trans[curr_type]

        # 4. 默认
        return _DEFAULT_TRANSITION_PROB

    # ══════════════════════════════════════════════════════
    #  统计与调试
    # ══════════════════════════════════════════════════════

    def _reset_stats(self):
        self._stats = {
            'auto_confirm': 0,
            'auto_reject': 0,
            'sequence_match': 0,
            'category_consistency': 0,
            'mutual_exclusion': 0,
            'low_transition': 0,
            'needs_review': 0,
        }

    def get_stats(self) -> Dict:
        """获取最近一次复核的统计信息"""
        return dict(self._stats)

    def _log_summary(self, events: List[RefinedEvent]):
        total = len(events)
        n_confirmed = sum(1 for e in events if e.verdict == 'confirmed')
        n_rejected = sum(1 for e in events if e.verdict == 'rejected')
        n_review = sum(1 for e in events if e.requires_review)
        n_auto_confirm = self._stats['auto_confirm']
        n_auto_reject = self._stats['auto_reject']

        pct_auto = (n_auto_confirm + n_auto_reject) / max(total, 1) * 100
        pct_review = n_review / max(total, 1) * 100

        logger.info(
            f"[ContextReview] {total}事件复核完成: "
            f"auto_confirm={n_auto_confirm}, auto_reject={n_auto_reject}, "
            f"needs_review={n_review} | "
            f"自动处理率={pct_auto:.0%}, 仍需人工={pct_review:.0%} | "
            f"最终: confirmed={n_confirmed}, rejected={n_rejected}"
        )

    def get_review_summary(self, events: List[RefinedEvent]) -> Dict:
        """获取复核摘要 (供 UI 展示)"""
        total = max(len(events), 1)
        return {
            'total': total,
            'auto_confirm': self._stats['auto_confirm'],
            'auto_reject': self._stats['auto_reject'],
            'needs_review': self._stats['needs_review'],
            'auto_rate': (self._stats['auto_confirm'] + self._stats['auto_reject']) / total,
            'manual_rate': self._stats['needs_review'] / total,
            'sequence_matches': self._stats['sequence_match'],
            'mutual_exclusions': self._stats['mutual_exclusion'],
            'low_transitions': self._stats['low_transition'],
            'category_consistency': self._stats['category_consistency'],
        }

    def get_auto_confirmed(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """获取自动确认的事件列表"""
        return [e for e in events if e.auto_verdict == 'auto_confirm']

    def get_auto_rejected(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """获取自动驳回的事件列表"""
        return [e for e in events if e.auto_verdict == 'auto_reject']

    def get_needs_review(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """获取仍需人工复核的事件列表"""
        return [e for e in events if e.requires_review]