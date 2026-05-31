#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测事件驱动数据模型
定义 EventEvaluationRecord / TypeAggregationResult / TripSummary
"""

import time
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class EventEvaluationRecord:
    """单个事件实例的评测记录

    一个事件对应一次评测，可同时产出实验组和对照组两套指标。
    不再按组分裂为多条记录。
    """
    event_id: str
    event_type: str
    event_type_cn: str = ""
    start_ts: float = 0.0
    end_ts: float = 0.0
    duration: float = 0.0
    confidence: float = 0.0
    behavior_category: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    status: str = "pending"
    evaluation_result_exp: Any = None
    evaluation_result_ctrl: Any = None
    evaluated_at: Optional[float] = None
    active_groups: List[str] = field(default_factory=lambda: ['experimental'])
    group_tag: Optional[str] = None
    control_record_id: Optional[str] = None

    rule_applied: Optional[str] = None
    threshold_multipliers: Dict[str, float] = field(default_factory=dict)
    data_window_range: Optional[Tuple[float, float]] = None
    location_data: Dict[str, Any] = field(default_factory=dict)

    RISK_LABELS = {'low': '低', 'medium': '中', 'high': '高'}

    @property
    def is_evaluated(self) -> bool:
        return self.evaluation_result_exp is not None or self.evaluation_result_ctrl is not None

    @property
    def is_fully_evaluated(self) -> bool:
        if 'experimental' in self.active_groups and self.evaluation_result_exp is None:
            return False
        if 'control' in self.active_groups and self.evaluation_result_ctrl is None:
            return False
        return True

    @property
    def has_exp_result(self) -> bool:
        return self.evaluation_result_exp is not None

    @property
    def has_ctrl_result(self) -> bool:
        return self.evaluation_result_ctrl is not None

    @property
    def overall_score(self) -> Optional[float]:
        if self.evaluation_result_exp:
            return getattr(self.evaluation_result_exp, 'overall_score', None)
        return None

    @property
    def overall_score_ctrl(self) -> Optional[float]:
        if self.evaluation_result_ctrl:
            return getattr(self.evaluation_result_ctrl, 'overall_score', None)
        return None

    @property
    def improvement_pct(self) -> Optional[float]:
        return self.compute_improvement(self.overall_score, self.overall_score_ctrl)

    @property
    def risk_level(self) -> str:
        if self.evaluation_result_exp:
            raw = getattr(self.evaluation_result_exp, 'risk_level', None)
            if raw is None:
                return '未评测'
            if hasattr(raw, 'value'):
                raw_val = raw.value
            else:
                raw_val = str(raw)
            label_map = {'SAFE': '低', 'CAUTION': '中', 'WARNING': '高', 'DANGER': '高'}
            return label_map.get(raw_val, str(raw_val))
        return '未评测'

    @property
    def score_grade(self) -> str:
        s = self.overall_score
        if s is None:
            return '--'
        if s >= 90:
            return 'A'
        elif s >= 70:
            return 'B'
        elif s >= 50:
            return 'C'
        return 'D'

    @property
    def grade_color(self) -> str:
        g = self.score_grade
        return {'A': '#27AE60', 'B': '#4A90D9', 'C': '#F39C12', 'D': '#E74C3C'}.get(g, '#999999')

    @property
    def score_grade_ctrl(self) -> str:
        s = self.overall_score_ctrl
        if s is None:
            return '--'
        if s >= 90:
            return 'A'
        elif s >= 70:
            return 'B'
        elif s >= 50:
            return 'C'
        return 'D'

    @property
    def grade_color_ctrl(self) -> str:
        g = self.score_grade_ctrl
        return {'A': '#27AE60', 'B': '#4A90D9', 'C': '#F39C12', 'D': '#E74C3C'}.get(g, '#999999')

    @property
    def status_icon(self) -> str:
        return {
            'pending': '○',
            'evaluating': '⟳',
            'evaluated': '✓',
            'stale': '⚡',
            'failed': '✗',
        }.get(self.status, '?')

    @property
    def status_color(self) -> str:
        return {
            'pending': '#999999',
            'evaluating': '#4A90D9',
            'evaluated': '#27AE60',
            'stale': '#F39C12',
            'failed': '#E74C3C',
        }.get(self.status, '#999999')

    @property
    def location_scores(self) -> Dict[str, float]:
        if not self.evaluation_result_exp:
            return {}
        lr = getattr(self.evaluation_result_exp, 'location_results', {})
        return {
            loc_id: getattr(r, 'location_score', 0)
            for loc_id, r in lr.items()
        }

    @property
    def weakest_location(self) -> str:
        scores = self.location_scores
        if not scores:
            return '--'
        return min(scores, key=scores.get)

    @property
    def strongest_location(self) -> str:
        scores = self.location_scores
        if not scores:
            return '--'
        return max(scores, key=scores.get)

    @property
    def location_metrics(self) -> Dict[str, Dict[str, float]]:
        if not self.evaluation_result_exp:
            return {}
        lr = getattr(self.evaluation_result_exp, 'location_results', {})
        result: Dict[str, Dict[str, float]] = {}
        for loc_id, r in lr.items():
            metrics = getattr(r, 'metrics', None)
            if metrics:
                result[loc_id] = dict(metrics)
        return result

    @property
    def location_metrics_ctrl(self) -> Dict[str, Dict[str, float]]:
        if not self.evaluation_result_ctrl:
            return {}
        lr = getattr(self.evaluation_result_ctrl, 'location_results', {})
        result: Dict[str, Dict[str, float]] = {}
        for loc_id, r in lr.items():
            metrics = getattr(r, 'metrics', None)
            if metrics:
                result[loc_id] = dict(metrics)
        return result

    @property
    def location_scores_ctrl(self) -> Dict[str, float]:
        if not self.evaluation_result_ctrl:
            return {}
        lr = getattr(self.evaluation_result_ctrl, 'location_results', {})
        return {
            loc_id: getattr(r, 'location_score', 0)
            for loc_id, r in lr.items()
        }

    @staticmethod
    def compute_improvement(exp_val: Optional[float], ctrl_val: Optional[float]) -> Optional[float]:
        if exp_val is None or ctrl_val is None:
            return None
        if ctrl_val == 0:
            return None
        return ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0

    @property
    def evaluation_result(self):
        return self.evaluation_result_exp

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'event_type_cn': self.event_type_cn,
            'start_ts': self.start_ts,
            'end_ts': self.end_ts,
            'duration': self.duration,
            'confidence': self.confidence,
            'status': self.status,
            'overall_score': self.overall_score,
            'overall_score_ctrl': self.overall_score_ctrl,
            'improvement_pct': self.improvement_pct,
            'score_grade': self.score_grade,
            'risk_level': self.risk_level,
            'location_scores': self.location_scores,
            'active_groups': self.active_groups,
        }


@dataclass
class TypeAggregationResult:
    """同类型事件聚合统计结果"""
    event_type: str
    event_type_cn: str = ""
    instance_indices: List[int] = field(default_factory=list)
    records: List[EventEvaluationRecord] = field(default_factory=list)

    @property
    def instance_count(self) -> int:
        return len(self.records)

    @property
    def evaluated_count(self) -> int:
        return sum(1 for r in self.records if r.is_evaluated)

    @property
    def pending_count(self) -> int:
        return sum(1 for r in self.records if r.status == 'pending')

    @property
    def scores(self) -> List[float]:
        return [r.overall_score for r in self.records
                if r.is_evaluated and r.overall_score is not None]

    @property
    def avg_score(self) -> Optional[float]:
        s = self.scores
        if not s:
            return None
        return sum(s) / len(s)

    @property
    def worst_score(self) -> Optional[float]:
        s = self.scores
        return min(s) if s else None

    @property
    def best_score(self) -> Optional[float]:
        s = self.scores
        return max(s) if s else None

    @property
    def std_dev(self) -> Optional[float]:
        s = self.scores
        if not s or len(s) < 2:
            return None
        mean = sum(s) / len(s)
        return math.sqrt(sum((x - mean) ** 2 for x in s) / len(s))

    @property
    def score_grade(self) -> str:
        a = self.avg_score
        if a is None:
            return '--'
        if a >= 90:
            return 'A'
        elif a >= 70:
            return 'B'
        elif a >= 50:
            return 'C'
        return 'D'

    @property
    def trend(self) -> str:
        s = self.scores
        if len(s) < 2:
            return 'insufficient'
        first_half = s[:len(s) // 2]
        second_half = s[len(s) // 2:]
        diff = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
        if diff > 3:
            return 'improving'
        elif diff < -3:
            return 'degrading'
        return 'stable'

    @property
    def location_avg(self) -> Dict[str, float]:
        loc_scores: Dict[str, List[float]] = {}
        for r in self.records:
            for loc_id, score in r.location_scores.items():
                loc_scores.setdefault(loc_id, []).append(score)
        return {k: sum(v) / len(v) for k, v in loc_scores.items() if v}

    @property
    def worst_record(self) -> Optional[EventEvaluationRecord]:
        s = [(r.overall_score or 0, r) for r in self.records if r.is_evaluated]
        if not s:
            return None
        return min(s, key=lambda x: x[0])[1]

    @property
    def best_record(self) -> Optional[EventEvaluationRecord]:
        s = [(r.overall_score or 0, r) for r in self.records if r.is_evaluated]
        if not s:
            return None
        return max(s, key=lambda x: x[0])[1]


@dataclass
class TripSummary:
    """行程总览聚合结果"""
    data_source_id: str = ""
    total_duration: float = 0.0
    total_events: int = 0
    evaluated_events: int = 0
    group_tag: str = "experimental"

    type_summaries: Dict[str, TypeAggregationResult] = field(default_factory=dict)
    all_records: List[EventEvaluationRecord] = field(default_factory=list)

    @property
    def overall_score(self) -> Optional[float]:
        evaluated = [r for r in self.all_records if r.is_evaluated]
        if not evaluated:
            return None
        return sum(r.overall_score or 0 for r in evaluated) / len(evaluated)

    @property
    def score_grade(self) -> str:
        s = self.overall_score
        if s is None:
            return '--'
        if s >= 90:
            return 'A'
        elif s >= 70:
            return 'B'
        elif s >= 50:
            return 'C'
        return 'D'

    @property
    def evaluation_coverage(self) -> float:
        if self.total_events == 0:
            return 0.0
        return self.evaluated_events / self.total_events

    @property
    def risk_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for r in self.all_records:
            if r.is_evaluated:
                rl = r.risk_level
                dist[rl] = dist.get(rl, 0) + 1
        return dist

    @property
    def highest_risk_type(self) -> str:
        type_scores = {}
        for t, aggr in self.type_summaries.items():
            score = aggr.avg_score
            if score is not None:
                type_scores[t] = score
        if not type_scores:
            return '--'
        return min(type_scores, key=type_scores.get)

    @property
    def weakest_location(self) -> str:
        loc_all: Dict[str, List[float]] = {}
        for r in self.all_records:
            if r.is_evaluated:
                for loc_id, score in r.location_scores.items():
                    loc_all.setdefault(loc_id, []).append(score)
        if not loc_all:
            return '--'
        loc_avg = {k: sum(v) / len(v) for k, v in loc_all.items()}
        return min(loc_avg, key=loc_avg.get)

    @property
    def best_location(self) -> str:
        loc_all: Dict[str, List[float]] = {}
        for r in self.all_records:
            if r.is_evaluated:
                for loc_id, score in r.location_scores.items():
                    loc_all.setdefault(loc_id, []).append(score)
        if not loc_all:
            return '--'
        loc_avg = {k: sum(v) / len(v) for k, v in loc_all.items()}
        return max(loc_avg, key=loc_avg.get)

    def generate_timeline_heatmap(self) -> Dict[str, List[Tuple[float, float, Optional[float]]]]:
        """生成时间轴热力图数据: type -> [(start, end, score), ...]"""
        heatmap: Dict[str, List[Tuple[float, float, Optional[float]]]] = {}
        for r in self.all_records:
            heatmap.setdefault(r.event_type, []).append(
                (r.start_ts, r.end_ts, r.overall_score)
            )
        return heatmap

    def compute(self):
        """根据 all_records 重新计算聚合统计"""
        self.total_events = len(self.all_records)
        self.evaluated_events = sum(1 for r in self.all_records if r.is_evaluated)

        type_groups: Dict[str, List[EventEvaluationRecord]] = {}
        for idx, r in enumerate(self.all_records):
            type_groups.setdefault(r.event_type, []).append(r)

        self.type_summaries = {}
        for etype, records in type_groups.items():
            agg = TypeAggregationResult(
                event_type=etype,
                event_type_cn=records[0].event_type_cn if records else "",
                records=records,
                instance_indices=list(range(1, len(records) + 1)),
            )
            self.type_summaries[etype] = agg


def create_event_record(
    event_id: str,
    event_type: str,
    start_ts: float,
    end_ts: float,
    confidence: float = 0.0,
    event_type_cn: str = "",
    behavior_category: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> EventEvaluationRecord:
    """工厂方法"""
    return EventEvaluationRecord(
        event_id=event_id,
        event_type=event_type,
        event_type_cn=event_type_cn or event_type,
        start_ts=start_ts,
        end_ts=end_ts,
        duration=end_ts - start_ts,
        confidence=confidence,
        behavior_category=behavior_category,
        metadata=metadata or {},
        status='pending',
        evaluated_at=None,
    )


def create_event_records_from_distributor(
    events: List[Any],
    event_type_labels: Optional[Dict[str, str]] = None,
) -> List[EventEvaluationRecord]:
    """从EventDistributor的BehaviorEventView列表创建记录列表"""
    records = []
    if event_type_labels is None:
        event_type_labels = {}

    for evt in events:
        etype = getattr(evt, 'behavior_type', '') or getattr(evt, 'type', '') or getattr(evt, 'behavior', 'unknown')
        eid = getattr(evt, 'event_id', f'evt_{int(getattr(evt, "start_ts", 0) * 1000)}')
        cat = getattr(evt, 'category', '')
        conf = getattr(evt, 'confidence', 0.0)
        meta = getattr(evt, 'metadata', None) or {}

        records.append(create_event_record(
            event_id=str(eid),
            event_type=etype,
            event_type_cn=event_type_labels.get(etype, etype),
            start_ts=getattr(evt, 'start_ts', 0),
            end_ts=getattr(evt, 'end_ts', 0),
            confidence=conf,
            behavior_category=str(cat),
            metadata=meta,
        ))

    records.sort(key=lambda r: r.start_ts)
    for i, r in enumerate(records):
        idx = sum(1 for prev in records[:i] if prev.event_type == r.event_type) + 1
        r.metadata['instance_index'] = idx

    return records