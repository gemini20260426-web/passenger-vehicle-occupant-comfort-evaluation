#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文窗口模块 — Phase 2 核心组件

基于滑动窗口的事件序列上下文增强分类:

功能:
  1. 滑动窗口事件历史 (最近 N 个事件)
  2. 事件转移概率矩阵 (基于驾驶行为领域知识)
  3. 序列一致性校验 (不合理的序列降低置信度)
  4. 时间衰减加权 (越近的事件影响越大)
  5. 模式检测 (如: 减速→停车→起步 序列)

集成:
  替换 ContextAwareThresholds 的位置，作为 HybridBehaviorClassifier 的
  第 4 候选源，权重从 0.10 提升至 0.15。
"""

import logging
import time
from typing import Dict, List, Tuple, Optional
from collections import deque, defaultdict
from ..core_types import ManeuverEvent, BehaviorCategory, BEHAVIOR_TYPES_V2

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  事件转移概率矩阵 — 基于驾驶行为领域知识
#  值: 0.0 (不可能) ~ 1.0 (必然)
# ═══════════════════════════════════════════════════════════

# 高概率转移对 (prev → next)
_HIGH_TRANSITIONS = {
    # 纵向序列
    ('stopped', 'launch'): 0.95,
    ('launch', 'normal_acceleration'): 0.80,
    ('normal_acceleration', 'constant_speed'): 0.75,
    ('constant_speed', 'normal_deceleration'): 0.70,
    ('normal_deceleration', 'stopped'): 0.80,
    ('constant_speed', 'constant_speed'): 0.85,
    ('normal_acceleration', 'aggressive_acceleration'): 0.30,
    ('aggressive_acceleration', 'constant_speed'): 0.60,
    ('normal_deceleration', 'aggressive_deceleration'): 0.25,
    ('aggressive_deceleration', 'stopped'): 0.50,
    ('aggressive_deceleration', 'emergency_braking'): 0.35,
    ('emergency_braking', 'stopped'): 0.70,

    # 横向序列
    ('straight_driving', 'straight_driving'): 0.90,
    ('straight_driving', 'lane_change'): 0.40,
    ('straight_driving', 'wide_turn'): 0.35,
    ('straight_driving', 'tight_turn'): 0.20,
    ('lane_change', 'straight_driving'): 0.60,
    ('lane_change', 'wide_turn'): 0.25,
    ('lane_change', 'cornering_acceleration'): 0.20,
    ('lane_change', 'cornering_deceleration'): 0.20,
    ('wide_turn', 'straight_driving'): 0.70,
    ('tight_turn', 'straight_driving'): 0.65,
    ('tight_turn', 'u_turn'): 0.20,
    ('lane_keeping', 'lane_keeping'): 0.90,
    ('lane_keeping', 'lane_change'): 0.35,
    ('weaving', 'straight_driving'): 0.50,
    ('weaving', 'lane_change'): 0.30,

    # 复合事件
    ('cornering_acceleration', 'straight_driving'): 0.55,
    ('cornering_acceleration', 'constant_speed'): 0.30,
    ('cornering_deceleration', 'straight_driving'): 0.55,
    ('cornering_deceleration', 'stopped'): 0.30,
    ('cornering_braking', 'stopped'): 0.50,
    ('cornering_braking', 'straight_driving'): 0.35,
    ('rapid_direction_change', 'straight_driving'): 0.40,
    ('rapid_direction_change', 'lane_change'): 0.30,

    # 异常事件
    ('skid_risk', 'straight_driving'): 0.30,
    ('skid_risk', 'constant_speed'): 0.25,
    ('rollover_risk', 'stopped'): 0.60,
    ('severe_bump', 'constant_speed'): 0.40,
    ('severe_bump', 'straight_driving'): 0.40,
    ('sensor_fault', 'sensor_fault'): 0.80,
}

# 低概率/不可能转移 (专门用于惩罚)
_LOW_TRANSITIONS = {
    ('stopped', 'emergency_braking'): 0.01,
    ('stopped', 'u_turn'): 0.01,
    ('stopped', 'weaving'): 0.01,
    ('emergency_braking', 'launch'): 0.02,
    ('u_turn', 'constant_speed'): 0.05,
    ('u_turn', 'u_turn'): 0.05,
}

# 默认转移概率 (未见过的转移对)
_DEFAULT_TRANSITION_PROB = 0.15

# 序列模式检测
_SEQUENCE_PATTERNS = {
    'stop_start': {
        'sequence': ['normal_deceleration', 'stopped', 'launch'],
        'boost': 0.10,  # 匹配时提升置信度
        'description': '减速→停车→起步',
    },
    'lane_change_turn': {
        'sequence': ['lane_change', 'cornering_acceleration'],
        'boost': 0.08,
        'description': '变道→弯道加速',
    },
    'approach_intersection': {
        'sequence': ['constant_speed', 'normal_deceleration', 'stopped'],
        'boost': 0.08,
        'description': '匀速→减速→停车',
    },
    'highway_entry': {
        'sequence': ['normal_acceleration', 'aggressive_acceleration', 'constant_speed'],
        'boost': 0.08,
        'description': '加速→急加速→匀速',
    },
    'emergency_stop': {
        'sequence': ['constant_speed', 'emergency_braking', 'stopped'],
        'boost': 0.12,
        'description': '匀速→急刹→停车',
    },
}


class ContextWindow:
    """上下文滑动窗口 — 事件序列增强

    用法:
        ctx = ContextWindow(window_size=10)
        adjusted_type, adjusted_conf = ctx.adjust(event_type, category, confidence)
        ctx.push(event_type, category, confidence, timestamp)
    """

    def __init__(self, window_size: int = 10, decay_half_life: float = 5.0):
        """
        Args:
            window_size: 滑动窗口大小 (事件数)
            decay_half_life: 时间衰减半衰期 (秒)
        """
        self._window_size = window_size
        self._decay_half_life = decay_half_life
        self._history: deque = deque(maxlen=window_size)
        self._total_events = 0

    def push(self, event_type: str, category: BehaviorCategory, confidence: float):
        """将事件推入滑动窗口

        Args:
            event_type: 事件类型
            category: 行为类别
            confidence: 置信度
        """
        self._history.append({
            'type': event_type,
            'category': category,
            'confidence': confidence,
            'timestamp': time.time(),
        })
        self._total_events += 1

    def get_history(self) -> List[Tuple[str, str, float]]:
        """F3: 获取上下文历史 (供 confidence_refiner 使用)

        Returns:
            [(event_type, category, confidence), ...] 按时间顺序排列
        """
        return [
            (h['type'], str(h['category']), h['confidence'])
            for h in self._history
        ]

    def adjust(
        self,
        event_type: str,
        category: BehaviorCategory,
        confidence: float,
    ) -> Tuple[str, float]:
        """基于上下文窗口调整置信度

        Args:
            event_type: 当前候选事件类型
            category: 行为类别
            confidence: 原始置信度

        Returns:
            (调整后的事件类型, 调整后的置信度)
        """
        if len(self._history) < 2:
            # 窗口不足，不做调整
            return event_type, confidence

        adjusted_conf = confidence

        # 1. 转移概率调整
        trans_boost = self._compute_transition_boost(event_type)
        adjusted_conf = self._apply_boost(adjusted_conf, trans_boost)

        # 2. 序列一致性调整
        seq_boost = self._check_sequence_patterns(event_type)
        adjusted_conf = self._apply_boost(adjusted_conf, seq_boost)

        # 3. 类别一致性 (同类事件连续出现更可信)
        cat_boost = self._compute_category_consistency(event_type, category)
        adjusted_conf = self._apply_boost(adjusted_conf, cat_boost)

        # 4. 异常检测: 短时间剧烈变化降低置信度
        if self._is_rapid_change(event_type):
            adjusted_conf = self._apply_boost(adjusted_conf, -0.10)

        return event_type, max(0.1, min(adjusted_conf, 0.99))

    def _compute_transition_boost(self, current_type: str) -> float:
        """计算基于转移概率的置信度调整量"""
        if not self._history:
            return 0.0

        prev_type = self._history[-1]['type']
        pair = (prev_type, current_type)

        # 检查高概率转移
        if pair in _HIGH_TRANSITIONS:
            prob = _HIGH_TRANSITIONS[pair]
            return (prob - 0.5) * 0.20  # 高概率转移提升置信度

        # 检查低概率转移
        if pair in _LOW_TRANSITIONS:
            prob = _LOW_TRANSITIONS[pair]
            return (prob - 0.3) * 0.25  # 低概率转移降低置信度

        # 默认
        return (_DEFAULT_TRANSITION_PROB - 0.3) * 0.15

    def _check_sequence_patterns(self, current_type: str) -> float:
        """检测已知序列模式"""
        if len(self._history) < 2:
            return 0.0

        # 取最近 N-1 个历史 + 当前事件，检查是否匹配已知序列
        recent_types = [h['type'] for h in list(self._history)[-3:]]
        candidate = recent_types + [current_type]

        for pattern_name, pattern_info in _SEQUENCE_PATTERNS.items():
            pattern = pattern_info['sequence']
            if len(candidate) >= len(pattern):
                # 检查后缀匹配
                tail = candidate[-len(pattern):]
                if tail == pattern:
                    logger.debug(f"序列模式匹配: {pattern_name} ({pattern_info['description']})")
                    return pattern_info['boost']

        return 0.0

    def _compute_category_consistency(
        self, event_type: str, category: BehaviorCategory
    ) -> float:
        """计算类别一致性 boost"""
        if len(self._history) < 2:
            return 0.0

        # 检查最近 3 个事件中同类别的比例
        recent = list(self._history)[-3:]
        same_category = sum(1 for h in recent if h['category'] == category)
        ratio = same_category / len(recent)

        if ratio >= 0.67:
            return 0.05  # 类别一致，小幅提升
        return 0.0

    def _is_rapid_change(self, current_type: str) -> bool:
        """检测短时间内事件类型剧烈变化"""
        if len(self._history) < 3:
            return False

        recent = list(self._history)[-3:]
        types = {h['type'] for h in recent}
        types.add(current_type)

        # 3 个历史事件 + 当前事件，类型数 >= 3 且时间差 < 2s
        if len(types) >= 3:
            time_span = time.time() - recent[0]['timestamp']
            if time_span < 2.0:
                return True
        return False

    def _apply_boost(self, confidence: float, boost: float) -> float:
        """应用 boost 到置信度，限制变化幅度"""
        return confidence + boost

    def get_transition_matrix(self) -> Dict[str, Dict[str, float]]:
        """获取实际观察到的转移频率矩阵 (用于调试)"""
        matrix = defaultdict(lambda: defaultdict(float))
        hist_list = list(self._history)
        for i in range(1, len(hist_list)):
            prev = hist_list[i - 1]['type']
            curr = hist_list[i]['type']
            matrix[prev][curr] += 1.0

        # 归一化
        for prev_type, transitions in matrix.items():
            total = sum(transitions.values())
            if total > 0:
                for curr_type in transitions:
                    transitions[curr_type] /= total

        return dict(matrix)

    def get_statistics(self) -> Dict:
        """获取上下文窗口统计信息"""
        return {
            'window_size': self._window_size,
            'current_count': len(self._history),
            'total_events': self._total_events,
            'decay_half_life': self._decay_half_life,
        }

    def reset(self):
        """重置上下文窗口"""
        self._history.clear()
        self._total_events = 0

    # ═══════════════════════════════════════════════════════════
    #  静态方法: 转移概率查询 (供 ContextReviewEngine 复用)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def get_transition_prob(prev_type: str, curr_type: str) -> float:
        """查询 (prev_type → curr_type) 的转移概率

        优先级:
          1. _HIGH_TRANSITIONS (精确匹配)
          2. _LOW_TRANSITIONS (精确匹配)
          3. _DEFAULT_TRANSITION_PROB (默认)

        Args:
            prev_type: 前一个事件类型
            curr_type: 当前事件类型

        Returns:
            转移概率 (0.0 ~ 1.0)
        """
        pair = (prev_type, curr_type)
        if pair in _HIGH_TRANSITIONS:
            return _HIGH_TRANSITIONS[pair]
        if pair in _LOW_TRANSITIONS:
            return _LOW_TRANSITIONS[pair]
        return _DEFAULT_TRANSITION_PROB

    @staticmethod
    def get_all_high_transitions() -> Dict:
        """获取所有高概率转移对 (供调试和UI展示)"""
        return dict(_HIGH_TRANSITIONS)

    @staticmethod
    def get_all_low_transitions() -> Dict:
        """获取所有低概率转移对 (供调试和UI展示)"""
        return dict(_LOW_TRANSITIONS)

    @staticmethod
    def get_all_sequence_patterns() -> Dict:
        """获取所有序列模式 (供调试和UI展示)"""
        return dict(_SEQUENCE_PATTERNS)