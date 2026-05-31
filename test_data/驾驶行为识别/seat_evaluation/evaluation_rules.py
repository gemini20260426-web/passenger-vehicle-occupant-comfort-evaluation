#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测规则引擎
基于事件类型动态调整评测阈值、位置权重和指标权重
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

from .imu_location_config import LOCATION_IDS

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRule:
    """评测规则配置"""
    event_type: str
    description: str = ""
    threshold_multipliers: Dict[str, float] = field(default_factory=dict)
    metric_weights: Dict[str, float] = field(default_factory=dict)
    location_weights: Dict[str, float] = field(default_factory=dict)
    min_confidence: float = 0.3
    priority_metrics: List[str] = field(default_factory=list)


class EvaluationRulesEngine:
    """座椅评测规则引擎"""

    # 事件类型到规则的映射
    EVENT_RULES: Dict[str, EvaluationRule] = {
        'emergency_braking': EvaluationRule(
            event_type='emergency_braking',
            description='紧急制动 - 重点评测头部冲击和纵向传递',
            threshold_multipliers={
                'HIC15': 0.7,
                'ACC_H_PEAK': 0.8,
                'JERK_H': 0.8,
                'SRS_MRS': 0.8,
                'TR_Z': 0.9,
                'AW_Z': 0.9,
                'VDV_Z': 0.9,
            },
            metric_weights={
                'HIC15': 0.25,
                'ACC_H_PEAK': 0.15,
                'JERK_H': 0.10,
                'SRS_MRS': 0.10,
                'TR_Z': 0.10,
                'VDV_Z': 0.10,
                'AW_Z': 0.08,
                'SEAT_Z': 0.07,
                'DISP_TR': 0.05,
            },
            location_weights={
                'head': 0.35,
                'torso': 0.20,
                'seat_r': 0.15,
                'seat_bottom': 0.20,
                'sternum': 0.10,
            },
            priority_metrics=['HIC15', 'ACC_H_PEAK', 'TR_Z', 'VDV_Z'],
        ),

        'weaving': EvaluationRule(
            event_type='weaving',
            description='蛇形驾驶 - 重点评测侧向振动和传递',
            threshold_multipliers={
                'SEAT_XY': 0.8,
                'AW_XY': 0.8,
                'R_FACTOR': 0.8,
                'DISP_TR': 0.9,
                'STFT_FC': 0.9,
                'STFT_KT': 0.9,
                'STFT_CE': 0.9,
            },
            metric_weights={
                'SEAT_XY': 0.20,
                'AW_XY': 0.15,
                'R_FACTOR': 0.10,
                'STFT_FC': 0.12,
                'STFT_KT': 0.12,
                'STFT_CE': 0.10,
                'TR_Z': 0.08,
                'DISP_TR': 0.08,
                'VDV_Z': 0.05,
            },
            location_weights={
                'head': 0.10,
                'torso': 0.15,
                'seat_r': 0.20,
                'seat_bottom': 0.15,
                'sternum': 0.40,
            },
            priority_metrics=['SEAT_XY', 'AW_XY', 'STFT_KT'],
        ),

        'aggressive_acceleration': EvaluationRule(
            event_type='aggressive_acceleration',
            description='激进加速 - 重点评测背部支撑和纵向传递',
            threshold_multipliers={
                'SEAT_XY': 0.9,
                'AW_XY': 0.9,
                'TR_Z': 0.9,
                'DISP_TR': 0.9,
                'VDV_Z': 0.9,
            },
            metric_weights={
                'SEAT_XY': 0.20,
                'AW_XY': 0.15,
                'DISP_TR': 0.15,
                'TR_Z': 0.12,
                'VDV_Z': 0.10,
                'R_FACTOR': 0.10,
                'SEAT_Z': 0.08,
                'AW_Z': 0.05,
                'HIC15': 0.05,
            },
            location_weights={
                'head': 0.10,
                'torso': 0.35,
                'seat_r': 0.20,
                'seat_bottom': 0.20,
                'sternum': 0.15,
            },
            priority_metrics=['SEAT_XY', 'DISP_TR', 'TR_Z'],
        ),

        'aggressive_deceleration': EvaluationRule(
            event_type='aggressive_deceleration',
            description='激进减速 - 重点评测头部冲击和座位振动',
            threshold_multipliers={
                'HIC15': 0.8,
                'ACC_H_PEAK': 0.8,
                'JERK_H': 0.9,
                'TR_Z': 0.9,
                'AW_Z': 0.9,
                'VDV_Z': 0.9,
                'SRS_MRS': 0.9,
            },
            metric_weights={
                'HIC15': 0.20,
                'ACC_H_PEAK': 0.12,
                'JERK_H': 0.10,
                'SRS_MRS': 0.10,
                'TR_Z': 0.10,
                'VDV_Z': 0.12,
                'AW_Z': 0.08,
                'SEAT_Z': 0.08,
                'DISP_TR': 0.05,
                'R_FACTOR': 0.05,
            },
            location_weights={
                'head': 0.30,
                'torso': 0.15,
                'seat_r': 0.25,
                'seat_bottom': 0.20,
                'sternum': 0.10,
            },
            priority_metrics=['HIC15', 'ACC_H_PEAK', 'VDV_Z', 'TR_Z'],
        ),

        'straight_cruise': EvaluationRule(
            event_type='straight_cruise',
            description='直线巡航 - 标准评测，侧重舒适度指标',
            threshold_multipliers={
                'AW_Z': 1.0,
                'AW_XY': 1.0,
                'VDV_Z': 1.0,
                'SEAT_Z': 1.0,
                'SEAT_XY': 1.0,
                'OVTV': 1.0,
            },
            metric_weights={
                'AW_Z': 0.15,
                'VDV_Z': 0.15,
                'SEAT_Z': 0.12,
                'SEAT_XY': 0.12,
                'AW_XY': 0.12,
                'OVTV': 0.10,
                'R_FACTOR': 0.08,
                'TR_Z': 0.08,
                'DISP_TR': 0.08,
            },
            location_weights={
                'head': 0.15,
                'torso': 0.20,
                'seat_r': 0.30,
                'seat_bottom': 0.20,
                'sternum': 0.15,
            },
            priority_metrics=['AW_Z', 'VDV_Z', 'SEAT_Z'],
        ),

        'cornering_acceleration': EvaluationRule(
            event_type='cornering_acceleration',
            description='弯道加速 - 重点评测侧向和纵向复合传递',
            threshold_multipliers={
                'SEAT_XY': 0.85,
                'AW_XY': 0.85,
                'R_FACTOR': 0.85,
                'TR_Z': 0.9,
                'STFT_FC': 0.9,
                'STFT_KT': 0.9,
            },
            metric_weights={
                'SEAT_XY': 0.18,
                'AW_XY': 0.15,
                'R_FACTOR': 0.12,
                'STFT_FC': 0.10,
                'STFT_KT': 0.10,
                'TR_Z': 0.08,
                'SEAT_Z': 0.08,
                'VDV_Z': 0.07,
                'DISP_TR': 0.07,
                'HIC15': 0.05,
            },
            location_weights={
                'head': 0.15,
                'torso': 0.20,
                'seat_r': 0.25,
                'seat_bottom': 0.20,
                'sternum': 0.20,
            },
            priority_metrics=['SEAT_XY', 'AW_XY', 'R_FACTOR', 'STFT_KT'],
        ),

        'cornering_deceleration': EvaluationRule(
            event_type='cornering_deceleration',
            description='弯道减速 - 重点评测复合冲击和侧向振动',
            threshold_multipliers={
                'SEAT_XY': 0.85,
                'AW_XY': 0.85,
                'R_FACTOR': 0.85,
                'TR_Z': 0.9,
                'SRS_MRS': 0.9,
                'HIC15': 0.9,
            },
            metric_weights={
                'SEAT_XY': 0.16,
                'AW_XY': 0.14,
                'R_FACTOR': 0.12,
                'SRS_MRS': 0.10,
                'HIC15': 0.10,
                'TR_Z': 0.08,
                'VDV_Z': 0.08,
                'SEAT_Z': 0.08,
                'DISP_TR': 0.07,
                'ACC_H_PEAK': 0.07,
            },
            location_weights={
                'head': 0.20,
                'torso': 0.20,
                'seat_r': 0.25,
                'seat_bottom': 0.20,
                'sternum': 0.15,
            },
            priority_metrics=['SEAT_XY', 'AW_XY', 'SRS_MRS', 'HIC15'],
        ),

        'severe_bump': EvaluationRule(
            event_type='severe_bump',
            description='剧烈颠簸 - 重点评测瞬态冲击和振动剂量',
            threshold_multipliers={
                'SRS_MRS': 0.7,
                'SRS_Q': 0.7,
                'SRS_PV': 0.7,
                'SRS_ATT': 0.7,
                'HIC15': 0.8,
                'ACC_H_PEAK': 0.8,
                'JERK_H': 0.8,
                'VDV_Z': 0.8,
                'AW_Z': 0.8,
                'OVTV': 0.8,
            },
            metric_weights={
                'SRS_MRS': 0.15,
                'SRS_PV': 0.10,
                'SRS_ATT': 0.08,
                'HIC15': 0.12,
                'ACC_H_PEAK': 0.10,
                'JERK_H': 0.08,
                'VDV_Z': 0.12,
                'AW_Z': 0.08,
                'OVTV': 0.07,
                'DISP_TR': 0.05,
                'TR_Z': 0.05,
            },
            location_weights={
                'head': 0.30,
                'torso': 0.15,
                'seat_r': 0.25,
                'seat_bottom': 0.20,
                'sternum': 0.10,
            },
            priority_metrics=['SRS_MRS', 'HIC15', 'VDV_Z', 'OVTV'],
        ),

        'rapid_direction_change': EvaluationRule(
            event_type='rapid_direction_change',
            description='急速变向 - 重点评测瞬态侧向冲击',
            threshold_multipliers={
                'SRS_MRS': 0.8,
                'SRS_ATT': 0.8,
                'SEAT_XY': 0.8,
                'AW_XY': 0.8,
                'R_FACTOR': 0.8,
                'STFT_KT': 0.85,
            },
            metric_weights={
                'SRS_MRS': 0.15,
                'SRS_ATT': 0.10,
                'SEAT_XY': 0.15,
                'AW_XY': 0.12,
                'R_FACTOR': 0.12,
                'STFT_KT': 0.10,
                'STFT_FC': 0.08,
                'DISP_TR': 0.08,
                'TR_Z': 0.05,
                'HIC15': 0.05,
            },
            location_weights={
                'head': 0.15,
                'torso': 0.20,
                'seat_r': 0.20,
                'seat_bottom': 0.15,
                'sternum': 0.30,
            },
            priority_metrics=['SRS_MRS', 'SEAT_XY', 'AW_XY', 'R_FACTOR'],
        ),
    }

    # 默认规则（用于未匹配的事件类型）
    DEFAULT_RULE = EvaluationRule(
        event_type='default',
        description='默认评测规则',
        threshold_multipliers={},
        metric_weights={},
        location_weights={
            'head': 0.30,
            'torso': 0.20,
            'seat_r': 0.30,
            'seat_bottom': 0.10,
            'sternum': 0.10,
        },
        min_confidence=0.3,
        priority_metrics=['HIC15', 'VDV_Z', 'SEAT_Z', 'AW_Z'],
    )

    def __init__(self):
        self._matched_event_types: Dict[str, str] = {}

    def get_rule(self, event_type: str) -> EvaluationRule:
        """根据事件类型获取规则"""

        def _normalize(et: str) -> str:
            return et.lower().replace(' ', '_').replace('-', '_')

        normalized = _normalize(event_type)

        if normalized in self.EVENT_RULES:
            self._matched_event_types[normalized] = event_type
            return self.EVENT_RULES[normalized]

        aliases = {
            # 管道直接产出的事件 (来自 rule_engine.py)
            'braking': 'aggressive_deceleration',
            'hard_braking': 'emergency_braking',
            'deceleration': 'aggressive_deceleration',
            'acceleration': 'aggressive_acceleration',
            'turning': 'cornering_acceleration',
            'turning_left': 'cornering_acceleration',
            'turning_right': 'cornering_acceleration',
            'lane_change': 'weaving',
            'lane_changing': 'weaving',
            'bump': 'severe_bump',
            'cornering_braking': 'cornering_deceleration',
            'stopped': 'straight_cruise',
            'launch': 'aggressive_acceleration',
            'constant_speed': 'straight_cruise',
            'straight_driving': 'straight_cruise',
            'tight_turn': 'cornering_acceleration',
            'wide_turn': 'cornering_acceleration',
            'u_turn': 'cornering_acceleration',
            'skid_risk': 'rapid_direction_change',
            'rollover_risk': 'rapid_direction_change',
            'normal_acceleration': 'straight_cruise',
            'normal_deceleration': 'straight_cruise',
            # 中文标签映射 (兼容 BehaviorAnalyzer 旧代码)
            '急刹车': 'emergency_braking',
            '加速': 'aggressive_acceleration',
            '减速': 'aggressive_deceleration',
            '左转': 'cornering_acceleration',
            '右转': 'cornering_acceleration',
            '蛇形驾驶': 'weaving',
            '急速变向': 'rapid_direction_change',
            '变道': 'weaving',
            '匀速直线': 'straight_cruise',
            '停车': 'straight_cruise',
            '激进加速': 'aggressive_acceleration',
            '激进刹车': 'aggressive_deceleration',
            '正常加速': 'straight_cruise',
            '正常刹车': 'straight_cruise',
            'U型转弯': 'cornering_acceleration',
            '大半径转弯': 'cornering_acceleration',
        }

        mapped = aliases.get(normalized)
        if mapped and mapped in self.EVENT_RULES:
            self._matched_event_types[normalized] = mapped
            return self.EVENT_RULES[mapped]

        return self.DEFAULT_RULE

    def get_threshold_multipliers(self, event_type: str) -> Dict[str, float]:
        """获取事件类型对应的阈值乘数"""
        rule = self.get_rule(event_type)
        return rule.threshold_multipliers

    def get_location_weights(self, event_type: str) -> Dict[str, float]:
        """获取事件类型对应的位置权重"""
        rule = self.get_rule(event_type)
        return rule.location_weights

    def get_metric_weights(self, event_type: str) -> Dict[str, float]:
        """获取事件类型对应的指标权重"""
        rule = self.get_rule(event_type)
        return rule.metric_weights

    def get_priority_metrics(self, event_type: str) -> List[str]:
        """获取事件类型对应的优先级指标"""
        rule = self.get_rule(event_type)
        return rule.priority_metrics

    def apply_threshold_adjustments(self, base_thresholds: Dict[str, Dict[str, float]],
                                    event_type: str) -> Dict[str, Dict[str, float]]:
        """对基础阈值应用事件类型调整"""
        multipliers = self.get_threshold_multipliers(event_type)
        if not multipliers:
            return base_thresholds

        adjusted = {}
        for metric_id, thresholds in base_thresholds.items():
            mult = multipliers.get(metric_id, 1.0)
            adjusted[metric_id] = {
                k: v * mult for k, v in thresholds.items()
            }
        return adjusted

    def get_composite_score(self, metrics: Dict[str, float],
                            event_type: str,
                            location_results: Dict[str, Any] = None) -> Tuple[float, float]:
        """计算加权复合评分和置信度"""
        rule = self.get_rule(event_type)
        metric_weights = rule.metric_weights
        location_weights = rule.location_weights

        score = 50.0
        confidence = 1.0

        if metric_weights and metrics:
            weighted_sum = 0.0
            total_weight = 0.0
            for metric_id, value in metrics.items():
                w = metric_weights.get(metric_id, 0.02)
                weighted_sum += value * w
                total_weight += w
            if total_weight > 0:
                score = weighted_sum / total_weight

        if location_results:
            loc_weighted_sum = 0.0
            loc_total = 0.0
            for loc_id, result in location_results.items():
                score_val = getattr(result, 'location_score', 0)
                w = location_weights.get(loc_id, 0.1)
                loc_weighted_sum += score_val * w
                loc_total += w
            if loc_total > 0:
                score = (score + loc_weighted_sum / loc_total) / 2.0

        priority_count = sum(1 for m in rule.priority_metrics if m in metrics)
        if rule.priority_metrics:
            confidence = min(1.0, max(rule.min_confidence,
                                priority_count / len(rule.priority_metrics)))

        return score, confidence

    def get_rules_summary(self) -> List[Dict[str, Any]]:
        """获取所有规则的摘要"""
        summary = []
        for et, rule in self.EVENT_RULES.items():
            summary.append({
                'event_type': et,
                'description': rule.description,
                'priority_metrics': rule.priority_metrics,
                'location_count': len(rule.location_weights),
                'metric_count': len(rule.metric_weights),
            })
        return summary