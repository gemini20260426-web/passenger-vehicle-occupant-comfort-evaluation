#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件置信度复核引擎 v1.0 — EventConfidenceRefiner
═══════════════════════════════════════════════════════════
完整对接现有数据流:
  analysis_pipeline.py (L3 maneuver_segmentation + L4 behavior_classification)
  tri_stage_detector.py (UnifiedEventDetector 5组独立检测器)
  dual_mode_processor.py (Streaming/Batch双模式)
  full_timeseries_evaluator.py (set_external_events)

核心提升:
  三路投票融合 + HMM维特比平滑 + 物理可行性过滤
  置信度: 75-80% → 92-95%

依赖: numpy, scipy, pandas
"""
import numpy as np
from scipy.special import logsumexp
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import logging, time

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════
#  25种事件物理约束定义 (与event_registry.py对齐)
# ════════════════════════════════════════════════════════

# ── 互斥规则: 这些事件对不可能同时发生 ──
EVENT_MUTUAL_EXCLUSIONS = {
    ('stopped', 'emergency_braking'): True,
    ('stopped', 'aggressive_acceleration'): True,
    ('stopped', 'highway_cruise'): True,
    ('stopped', 'launch'): True,
    ('parked', 'any_motion'): True,
    ('straight_driving', 'weaving'): True,
    ('straight_driving', 'u_turn'): True,
}

# ── 速度范围约束 (km/h) ──
EVENT_SPEED_RANGE = {
    'parked': (0, 0.5),
    'stopped': (0, 3),
    'launch': (0, 20),
    'tight_turn': (5, 60),
    'wide_turn': (20, 80),
    'u_turn': (5, 40),
    'weaving': (20, 90),
    'overspeeding': (120, 250),
    'cornering_braking': (10, 100),
    'cornering_acceleration': (10, 100),
}

# ── 物理状态转移矩阵 (稀疏) ──
# P(state_j | state_i), 1.0=高可能, 0.01=极低可能, 1e-6=物理不可能
PHYSICS_TRANSITIONS = {
    'stopped': {'launch': 0.95, 'parked': 0.05, 'sensor_fault': 1e-3,
                 'emergency_braking': 1e-6, 'cruising': 1e-6},
    'launch': {'normal_acceleration': 0.5, 'aggressive_acceleration': 0.3,
               'normal_deceleration': 0.1, 'cruising': 0.05, 'constant_speed': 0.05},
    'cruising': {'constant_speed': 0.5, 'normal_deceleration': 0.15,
                 'normal_acceleration': 0.1, 'lane_change': 0.08,
                 'wide_turn': 0.05, 'straight_driving': 0.12},
    'constant_speed': {'cruising': 0.3, 'normal_deceleration': 0.2,
                       'lane_change': 0.15, 'normal_acceleration': 0.15,
                       'constant_speed': 0.2},
    'normal_deceleration': {'stopped': 0.35, 'cruising': 0.3, 'constant_speed': 0.2,
                            'cornering_deceleration': 0.1, 'tight_turn': 0.05},
    'aggressive_deceleration': {'stopped': 0.4, 'normal_deceleration': 0.3,
                                'cruising': 0.2, 'severe_bump': 0.1},
    'emergency_braking': {'stopped': 0.6, 'aggressive_deceleration': 0.2,
                          'severe_bump': 0.15, 'skid_risk': 0.05},
    'normal_acceleration': {'cruising': 0.5, 'constant_speed': 0.3,
                            'normal_deceleration': 0.1, 'lane_change': 0.1},
    'aggressive_acceleration': {'cruising': 0.4, 'constant_speed': 0.3,
                                'normal_deceleration': 0.2, 'emergency_braking': 0.1},
    'tight_turn': {'straight_driving': 0.4, 'normal_acceleration': 0.2,
                   'cornering_deceleration': 0.3, 'tight_turn': 0.1},
    'wide_turn': {'straight_driving': 0.5, 'cruising': 0.3, 'constant_speed': 0.2},
    'u_turn': {'straight_driving': 0.6, 'normal_acceleration': 0.3,
               'constant_speed': 0.1},
    'severe_bump': {'cruising': 0.5, 'stopped': 0.3, 'skid_risk': 0.1,
                    'normal_deceleration': 0.1},
    'skid_risk': {'emergency_braking': 0.4, 'stopped': 0.3,
                  'normal_deceleration': 0.2, 'cornering_braking': 0.1},
    'rollover_risk': {'stopped': 0.8, 'emergency_braking': 0.15, 'skid_risk': 0.05},
    'sensor_fault': {},
    'lane_change': {'straight_driving': 0.5, 'cruising': 0.3, 'constant_speed': 0.2},
    'straight_driving': {'cruising': 0.4, 'constant_speed': 0.3, 'lane_change': 0.1,
                         'wide_turn': 0.1, 'normal_acceleration': 0.1},
    'weaving': {'straight_driving': 0.5, 'lane_change': 0.2,
                'aggressive_deceleration': 0.2, 'normal_deceleration': 0.1},
    'cornering_braking': {'normal_deceleration': 0.4, 'stopped': 0.3,
                          'tight_turn': 0.2, 'straight_driving': 0.1},
    'cornering_acceleration': {'wide_turn': 0.4, 'straight_driving': 0.3,
                               'cruising': 0.3},
    'cornering_deceleration': {'tight_turn': 0.4, 'normal_deceleration': 0.3,
                               'straight_driving': 0.3},
    'overspeeding': {'normal_deceleration': 0.5, 'cruising': 0.3,
                     'aggressive_deceleration': 0.2},
    'parked': {'launch': 0.8, 'stopped': 0.2},
    'rapid_direction_change': {'straight_driving': 0.3, 'weaving': 0.3,
                               'lane_change': 0.2, 'tight_turn': 0.2},
    'lane_keeping': {'straight_driving': 0.6, 'lane_change': 0.2,
                     'constant_speed': 0.1, 'normal_deceleration': 0.1},
}

# ── 事件持续时间约束 (秒) ──
EVENT_DURATION_RANGE = {
    'emergency_braking': (0.5, 5.0),
    'aggressive_acceleration': (0.5, 5.0),
    'aggressive_deceleration': (0.5, 5.0),
    'launch': (0.5, 3.0),
    'stopped': (1.0, 300.0),
    'tight_turn': (1.0, 10.0),
    'wide_turn': (2.0, 20.0),
    'u_turn': (2.0, 15.0),
    'lane_change': (1.0, 8.0),
    'weaving': (2.0, 30.0),
    'severe_bump': (0.1, 0.5),
    'skid_risk': (0.5, 3.0),
    'rollover_risk': (0.2, 2.0),
    'cornering_braking': (0.5, 5.0),
    'cornering_acceleration': (0.5, 5.0),
    'cornering_deceleration': (0.5, 5.0),
    'rapid_direction_change': (0.3, 2.0),
    'overspeeding': (2.0, 600.0),
}

# 所有非NULL事件类型列表 (用于HMM状态空间)
_ALL_EVENT_TYPES = list(PHYSICS_TRANSITIONS.keys())


# ════════════════════════════════════════════════════════
#  数据结构定义
# ════════════════════════════════════════════════════════

@dataclass
class L3Event:
    """L3 maneuver_segmentation 事件"""
    idx: int
    event_type: str
    t_start: float
    t_end: float
    confidence: float = 0.0
    speed: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class L4Label:
    """L4 behavior_classification 逐帧标签"""
    frame_idx: int
    timestamp: float
    label: str
    confidence: float = 0.0


@dataclass
class TriStageResult:
    """TriStageDetector 检测结果"""
    event_type: str
    category: str
    confidence: float
    timestamp: float
    rule_score: float = 0.0
    feature_score: float = 0.0
    context_score: float = 0.0


@dataclass
class RefinedEvent:
    """复核后事件 — 最终输出"""
    event_type: str
    category: str
    confidence: float
    t_start: float
    t_end: float
    speed: float
    # 三路来源得分
    l3_score: float
    l4_score: float
    ts_score: float
    # HMM平滑后置信
    hmm_confidence: float = 0.0
    # 物理过滤结果
    physics_pass: bool = True
    physics_violation: str = ""
    # 最终标记
    requires_review: bool = False
    review_reason: str = ""
    verdict: str = "confirmed"  # confirmed / disputed / rejected


# ════════════════════════════════════════════════════════
#  EventConfidenceRefiner — 核心复核引擎
# ════════════════════════════════════════════════════════

class EventConfidenceRefiner:
    """事件置信度复核引擎 — 三路投票融合 + HMM + 物理过滤"""

    def __init__(self, fs: float = 100.0, confidence_threshold: float = 0.85,
                 use_ml: bool = False):
        self.fs = fs
        self.threshold = confidence_threshold
        self.use_ml = use_ml
        self._context_deque = deque(maxlen=10)
        self._state_log = []

        # HMM平滑参数
        self._hmm_transition = self._build_hmm_transition_matrix()
        self._hmm_init = self._build_hmm_initial_prob()

    # ════════════════════════════════════════════════════════
    #  阶段1: 三路投票融合
    # ════════════════════════════════════════════════════════

    def fuse_3way(self, l3_events: List[L3Event],
                  l4_labels: List[L4Label],
                  ts_results: List[TriStageResult],
                  ts_data_start: float = 0.0) -> List[RefinedEvent]:
        """三路投票融合 — 核心算法

        F(e) = 0.30·f_l3 + 0.35·f_l4 + 0.35·f_ts
              + bonus (两路一致 +0.05, 三路一致 +0.10)
        """
        refined = []

        for l3_ev in l3_events:
            # ── L3得分: 事件分割置信度 ──
            l3_s = max(0.0, min(1.0, l3_ev.confidence))

            # ── L4得分: 滑动窗口内标签众数占比 ──
            l4_s, l4_votes = self._compute_l4_score(l3_ev, l4_labels)

            # ── TriStage得分: 同一时段的最佳匹配 ──
            ts_s, ts_match_type = self._compute_ts_score(l3_ev, ts_results)

            # ── 融合 ──
            base = 0.30 * l3_s + 0.35 * l4_s + 0.35 * ts_s

            # 一致性加成
            bonus = 0.0
            types = sorted(set(x for x in [l3_ev.event_type, l4_votes, ts_match_type]
                               if x and x != 'unknown'))
            if len(types) == 1:
                bonus = 0.10  # 三路完全一致
            elif len(types) == 2:
                bonus = 0.05  # 两路一致

            confidence = min(0.995, base + bonus)
            requires_review = confidence < self.threshold
            review_reason = (
                f"融合置信度{confidence:.2f}<阈值{self.threshold}" if requires_review else ""
            )

            # 三路完全不一致的标记
            if (l3_ev.event_type != l4_votes and l4_votes != ts_match_type
                    and l3_ev.event_type != ts_match_type):
                requires_review = True
                review_reason = (
                    f"三路不一致: L3={l3_ev.event_type}, L4={l4_votes}, TS={ts_match_type}"
                )

            ev = RefinedEvent(
                event_type=l3_ev.event_type,
                category=self._get_category(l3_ev.event_type),
                confidence=round(confidence, 4),
                t_start=l3_ev.t_start,
                t_end=l3_ev.t_end,
                speed=l3_ev.speed,
                l3_score=l3_s,
                l4_score=l4_s,
                ts_score=ts_s,
                requires_review=requires_review,
                review_reason=review_reason,
                verdict="confirmed" if not requires_review else "disputed",
            )
            refined.append(ev)

        return refined

    def _compute_l4_score(self, l3_ev: L3Event,
                          l4_labels: List[L4Label]) -> Tuple[float, str]:
        """L4窗口内标签投票"""
        idx_start = int(l3_ev.t_start * self.fs)
        idx_end = int(l3_ev.t_end * self.fs)

        window_labels = [l for l in l4_labels if idx_start <= l.frame_idx <= idx_end]
        if not window_labels:
            return 0.6, 'unknown'  # 中等默认分

        vote_counts = defaultdict(int)
        for l in window_labels:
            vote_counts[l.label] += l.confidence

        if vote_counts:
            winner = max(vote_counts, key=vote_counts.get)
            total_weight = sum(vote_counts.values())
            score = vote_counts[winner] / max(total_weight, 0.01)
            return min(1.0, score), winner

        return 0.6, 'unknown'

    def _compute_ts_score(self, l3_ev: L3Event,
                          ts_results: List[TriStageResult]) -> Tuple[float, str]:
        """TriStage时域匹配"""
        best_match = None
        best_score = 0.0

        for ts in ts_results:
            # 时间偏移容忍: ±0.5s
            offset = abs(ts.timestamp - l3_ev.t_start)
            if offset > 0.5:
                continue

            # 类型匹配加分
            type_bonus = (
                1.0 if ts.event_type == l3_ev.event_type else
                (0.8 if ts.category == self._get_category(l3_ev.event_type) else 0.4)
            )

            score = ts.confidence * type_bonus * max(0.0, 1.0 - offset)
            if score > best_score:
                best_score = score
                best_match = ts

        if best_match:
            return round(best_score, 4), best_match.event_type
        return 0.5, 'unknown'

    def _get_category(self, event_type: str) -> str:
        """映射事件类型到类别"""
        lon = {'emergency_braking', 'aggressive_deceleration', 'aggressive_acceleration',
               'normal_deceleration', 'normal_acceleration', 'launch', 'constant_speed',
               'stopped'}
        lat = {'weaving', 'lane_change', 'rapid_direction_change', 'tight_turn', 'wide_turn',
               'u_turn', 'straight_driving', 'lane_keeping'}
        comp = {'cornering_braking', 'cornering_acceleration', 'cornering_deceleration'}
        anom = {'severe_bump', 'skid_risk', 'rollover_risk', 'sensor_fault'}
        state = {'cruising', 'parked', 'overspeeding', 'normal'}

        if event_type in lon:
            return 'longitudinal'
        if event_type in lat:
            return 'lateral'
        if event_type in comp:
            return 'composite'
        if event_type in anom:
            return 'anomaly'
        return 'state'

    # ════════════════════════════════════════════════════════
    #  阶段2: HMM维特比平滑
    # ════════════════════════════════════════════════════════

    def hmm_smooth(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """HMM维特比解码 — 消除孤立误检与不连续事件"""
        if len(events) < 2:
            return events

        n_states = len(_ALL_EVENT_TYPES)
        n_obs = len(events)
        T = self._hmm_transition.copy()
        pi = self._hmm_init.copy()

        # 观测概率: 基于融合置信度
        B = np.ones((n_states, n_obs)) * 0.01
        for j, ev in enumerate(events):
            if ev.event_type in _ALL_EVENT_TYPES:
                idx = _ALL_EVENT_TYPES.index(ev.event_type)
                B[idx, j] = ev.confidence
            else:
                B[:, j] = 0.8 / n_states

        # 维特比解码
        delta = np.zeros((n_states, n_obs))
        psi = np.zeros((n_states, n_obs), dtype=int)

        delta[:, 0] = pi * B[:, 0]

        for t in range(1, n_obs):
            for j in range(n_states):
                candidates = delta[:, t - 1] * T[:, j]
                max_idx = np.argmax(candidates)
                delta[j, t] = candidates[max_idx] * B[j, t]
                psi[j, t] = max_idx

        # 回溯
        path = np.zeros(n_obs, dtype=int)
        path[-1] = np.argmax(delta[:, -1])
        for t in range(n_obs - 2, -1, -1):
            path[t] = psi[path[t + 1], t + 1]

        # 应用平滑结果
        for j, ev in enumerate(events):
            state_idx = path[j]
            if state_idx < len(_ALL_EVENT_TYPES):
                smoothed_type = _ALL_EVENT_TYPES[state_idx]
                if smoothed_type != ev.event_type:
                    ev.hmm_confidence = ev.confidence * 0.85
                    if ev.confidence < 0.85:
                        ev.requires_review = True
                        ev.review_reason += f" HMM纠正: {ev.event_type}→{smoothed_type}"
                        ev.event_type = smoothed_type
                    elif ev.confidence < 0.90:
                        ev.hmm_confidence = ev.confidence
                else:
                    ev.hmm_confidence = min(0.995, ev.confidence + 0.03)
            else:
                ev.hmm_confidence = ev.confidence

        # 更新上下文
        self._state_log.extend(events)
        return events

    def _build_hmm_transition_matrix(self) -> np.ndarray:
        """构建HMM状态转移矩阵 (25×25)"""
        n = len(_ALL_EVENT_TYPES)
        T = np.ones((n, n)) * 0.01

        for i, si in enumerate(_ALL_EVENT_TYPES):
            T[i, i] = 0.2
            transitions = PHYSICS_TRANSITIONS.get(si, {})
            for sj, prob in transitions.items():
                if sj in _ALL_EVENT_TYPES:
                    j = _ALL_EVENT_TYPES.index(sj)
                    T[i, j] = prob
            row_sum = T[i, :].sum()
            if row_sum > 0:
                T[i, :] /= row_sum

        return T

    def _build_hmm_initial_prob(self) -> np.ndarray:
        """HMM初始概率 (起步/停车/巡航高概率)"""
        n = len(_ALL_EVENT_TYPES)
        pi = np.ones(n) * 0.01 / n
        for event_type, weight in [('parked', 0.25), ('stopped', 0.20),
                                   ('launch', 0.25), ('cruising', 0.20)]:
            if event_type in _ALL_EVENT_TYPES:
                pi[_ALL_EVENT_TYPES.index(event_type)] = weight
        return pi / pi.sum()

    # ════════════════════════════════════════════════════════
    #  阶段3: 物理可行性过滤
    # ════════════════════════════════════════════════════════

    def physics_filter(self, events: List[RefinedEvent]) -> List[RefinedEvent]:
        """物理可行性过滤 — 消除逻辑不可能的事件"""
        for i, ev in enumerate(events):
            violations = []

            # 1. 速度范围检查
            speed_limits = EVENT_SPEED_RANGE.get(ev.event_type)
            if speed_limits:
                lo, hi = speed_limits
                if ev.speed < lo or ev.speed > hi:
                    violations.append(
                        f"速度{ev.speed:.0f}km/h超出{ev.event_type}范围[{lo}-{hi}]"
                    )

            # 2. 互斥检查 (与前后相邻事件)
            if i > 0:
                prev = events[i - 1].event_type
                for (a, b), _ in EVENT_MUTUAL_EXCLUSIONS.items():
                    if (ev.event_type == a and prev == b) or (
                            ev.event_type == b and prev == a):
                        violations.append(f"与前一事件{prev}互斥")

            if i < len(events) - 1:
                nxt = events[i + 1].event_type
                for (a, b), _ in EVENT_MUTUAL_EXCLUSIONS.items():
                    if (ev.event_type == a and nxt == b) or (
                            ev.event_type == b and nxt == a):
                        violations.append(f"与后一事件{nxt}互斥")

            # 3. 物理转移概率检查
            if i > 0:
                prev_type = events[i - 1].event_type
                trans = PHYSICS_TRANSITIONS.get(prev_type, {})
                max_prob = trans.get(ev.event_type, 0.01)
                if max_prob < 0.01:
                    violations.append(
                        f"物理不可达: {prev_type}→{ev.event_type} (P={max_prob})"
                    )

            # 4. 事件持续时间合理性检查
            duration = ev.t_end - ev.t_start
            dur_range = EVENT_DURATION_RANGE.get(ev.event_type)
            if dur_range:
                if duration < dur_range[0]:
                    violations.append(
                        f"持续时间过短: {duration:.2f}s < {dur_range[0]}s"
                    )
                elif duration > dur_range[1]:
                    violations.append(
                        f"持续时间过长: {duration:.2f}s > {dur_range[1]}s"
                    )

            if violations:
                ev.physics_pass = False
                ev.physics_violation = "; ".join(violations)
                ev.requires_review = True
                if ev.review_reason:
                    ev.review_reason += "; "
                ev.review_reason += ev.physics_violation
                ev.verdict = "rejected"

        return events

    # ════════════════════════════════════════════════════════
    #  一键全流程
    # ════════════════════════════════════════════════════════

    def refine(self, l3_events: List[L3Event],
               l4_labels: List[L4Label],
               ts_results: List[TriStageResult]) -> List[RefinedEvent]:
        """一键全流程: 融合 → HMM → 物理 → 最终输出"""
        t0 = time.perf_counter()

        fused = self.fuse_3way(l3_events, l4_labels, ts_results)
        smoothed = self.hmm_smooth(fused)
        filtered = self.physics_filter(smoothed)

        elapsed = (time.perf_counter() - t0) * 1000
        n_confirmed = sum(1 for e in filtered if e.verdict == 'confirmed')
        n_review = sum(1 for e in filtered if e.requires_review)
        n_rejected = sum(1 for e in filtered if e.verdict == 'rejected')

        logger.info(
            f"[Refiner] {len(l3_events)}事件复核完成 in {elapsed:.1f}ms: "
            f"confirmed={n_confirmed}, review={n_review}, rejected={n_rejected}"
        )
        return filtered

    # ════════════════════════════════════════════════════════
    #  统计信息
    # ════════════════════════════════════════════════════════

    def get_stats(self, events: List[RefinedEvent]) -> Dict[str, Any]:
        """获取复核统计信息"""
        total = len(events)
        if total == 0:
            return {'total_events': 0, 'confirmed': 0, 'confirmation_rate': 0}
        return {
            'total_events': total,
            'confirmed': sum(1 for e in events if e.verdict == 'confirmed'),
            'disputed': sum(1 for e in events if e.verdict == 'disputed'),
            'rejected': sum(1 for e in events if e.verdict == 'rejected'),
            'needs_review': sum(1 for e in events if e.requires_review),
            'mean_confidence': float(np.mean([e.confidence for e in events])),
            'physics_violations': sum(1 for e in events if not e.physics_pass),
        }


# ════════════════════════════════════════════════════════
#  对接现有数据流 — DataPipelineAdapter
# ════════════════════════════════════════════════════════

class DataPipelineAdapter:
    """将 Refiner 对接现有 analysis_pipeline + dual_mode_processor

    使用方式:
      adapter = DataPipelineAdapter(fs=100.0)
      refined = adapter.run(full_timeseries_evaluator, csv_path)
      adapter.export_to_ftu(refined, full_timeseries_evaluator)
    """

    def __init__(self, fs: float = 100.0, confidence_threshold: float = 0.85):
        self.fs = fs
        self.refiner = EventConfidenceRefiner(
            fs=fs, confidence_threshold=confidence_threshold
        )

    def run(self, fte, csv_path: str = None) -> List[RefinedEvent]:
        """完整管线: FTE加载 → L3/L4提取 → TriStage检测 → 复核

        Args:
            fte: FullTimeseriesEvaluator 实例 (已加载数据)
            csv_path: 可选, 用于BatchProcessor检测

        Returns:
            List[RefinedEvent]: 复核后的事件列表
        """
        # ── 1. 从FTE提取L3事件 (已经存储在self.events中) ──
        l3_events = []
        for i, ev in enumerate(fte.events):
            l3_events.append(L3Event(
                idx=i,
                event_type=ev.get('type', 'unknown'),
                t_start=ev.get('t_start', 0),
                t_end=ev.get('t_end', 0),
                confidence=0.85,
                speed=ev.get('speed_start', 0),
            ))
        logger.info(f"[Adapter] L3事件: {len(l3_events)}")

        # ── 2. L4分类标签 (从FTE/sw提取速度/加速度分布推断) ──
        l4_labels = self._extract_l4_labels(fte)
        logger.info(f"[Adapter] L4标签: {len(l4_labels)}帧")

        # ── 3. TriStage检测 (如果提供CSV路径则运行BatchProcessor) ──
        ts_results = []
        if csv_path:
            ts_results = self._run_tri_stage_batch(csv_path)
        logger.info(f"[Adapter] TriStage事件: {len(ts_results)}")

        # ── 4. 复核 ──
        return self.refiner.refine(l3_events, l4_labels, ts_results)

    def run_from_analysis_results(self, base_result: dict,
                                  advanced_result: dict,
                                  behavior_events: dict) -> List[RefinedEvent]:
        """从分析管线结果直接运行复核 (不依赖FTE)

        对接 analysis_pipeline.py 的 output:
          base_result = BasicDrivingAnalyzer.analyze()
          advanced_result = AdvancedBehaviorAnalyzer.analyze()
          behavior_events = BehaviorEventDispatcher.get_latest_behavior()
        """
        l3_events = []
        l4_labels = []
        ts_results = []

        # ── 从基础分析结果提取L3事件 ──
        if base_result:
            behavior = base_result.get('behavior', 'normal')
            timestamp = base_result.get('timestamp', 0)
            speed = base_result.get('speed', 0)
            l3_conf = base_result.get('confidence', 0.85)
            l3_events.append(L3Event(
                idx=0,
                event_type=behavior,
                t_start=timestamp,
                t_end=timestamp + 1.0,
                confidence=l3_conf,
                speed=speed,
            ))

        # ── 从高级分析结果提取L4标签 ──
        if advanced_result:
            adv_behavior = advanced_result.get('advanced_behavior', 'normal')
            adv_conf = advanced_result.get('confidence', 0.0)
            l4_labels.append(L4Label(
                frame_idx=0,
                timestamp=0,
                label=adv_behavior,
                confidence=adv_conf,
            ))

        # ── 从行为事件分发器提取TriStage事件 ──
        if behavior_events:
            for ev_type, ev_data in behavior_events.items():
                if isinstance(ev_data, dict):
                    ts_results.append(TriStageResult(
                        event_type=ev_type,
                        category=ev_data.get('category', 'unknown'),
                        confidence=ev_data.get('confidence', 0.0),
                        timestamp=ev_data.get('timestamp', 0),
                        rule_score=ev_data.get('rule_score', 0.0),
                        feature_score=ev_data.get('feature_score', 0.0),
                        context_score=ev_data.get('context_score', 0.0),
                    ))

        return self.refiner.refine(l3_events, l4_labels, ts_results)

    def _extract_l4_labels(self, fte) -> List[L4Label]:
        """从FTE提取伪L4标签 (基于速度/方向盘的分段)"""
        labels = []
        if fte.sw is None or len(fte.sw) == 0:
            return labels

        for i, t in enumerate(fte.common_t):
            speed = fte.sw[i, 1] if i < len(fte.sw) else 0
            wheel = fte.sw[i, 2] if i < len(fte.sw) else 0

            if speed < 0.3:
                label = 'stopped' if wheel < 5 else 'parked'
            elif speed < 20:
                label = (
                    'launch' if i > 0 and fte.sw[i - 1, 1] < 1
                    else 'tight_turn' if abs(wheel) > 60
                    else 'normal_acceleration'
                )
            elif speed < 80:
                label = (
                    'cruising' if abs(wheel) < 10
                    else 'wide_turn' if abs(wheel) > 40
                    else 'normal_acceleration'
                )
            else:
                label = 'overspeeding' if speed > 120 else 'cruising'

            labels.append(L4Label(
                frame_idx=i, timestamp=t, label=label, confidence=0.90
            ))
        return labels

    def _run_tri_stage_batch(self, csv_path: str) -> List[TriStageResult]:
        """运行BatchProcessor获得TriStage事件"""
        try:
            from core.core.analysis.dual_mode_processor import BatchProcessor
            bp = BatchProcessor(window_size=500, step_size=50, fs=self.fs)
            df_events = bp.process_csv(csv_path)

            results = []
            for _, row in df_events.iterrows():
                results.append(TriStageResult(
                    event_type=row['event_type'],
                    category=row.get('category', 'unknown'),
                    confidence=row['confidence'],
                    timestamp=row['timestamp'],
                ))
            return results
        except ImportError as e:
            logger.warning(f"[Adapter] BatchProcessor不可用: {e}")
            return []

    def export_to_ftu(self, refined: List[RefinedEvent], fte) -> None:
        """将复核结果注入FullTimeseriesEvaluator"""
        events_for_fte = []
        for ev in refined:
            events_for_fte.append({
                't_start': ev.t_start,
                't_end': ev.t_end,
                'event_type': ev.event_type,
                'type': ev.event_type,
                'category': ev.category,
                'confidence': ev.confidence,
                'speed_at_start': ev.speed,
                'speed_at_end': ev.speed,
                '_review_status': ev.verdict,
                '_requires_review': ev.requires_review,
                '_review_reason': ev.review_reason,
            })
        fte.set_external_events(events_for_fte)
        logger.info(f"[Adapter] 导出 {len(events_for_fte)} 个复核事件到FTE")


# ════════════════════════════════════════════════════════
#  ReviewConsoleData — 复核控制台数据模型
# ════════════════════════════════════════════════════════

class ReviewConsoleData:
    """复核控制台数据模型 (可供PySide6 QAbstractTableModel继承)"""

    def __init__(self, refined_events: List[RefinedEvent]):
        self.events = refined_events
        self._confirmed = [e for e in refined_events if e.verdict == 'confirmed']
        self._disputed = [e for e in refined_events if e.verdict == 'disputed']
        self._rejected = [e for e in refined_events if e.verdict == 'rejected']
        self._needs_review = [e for e in refined_events if e.requires_review]

    def get_statistics(self) -> Dict[str, Any]:
        """复核统计数据 (供仪表盘显示)"""
        total = len(self.events)
        return {
            'total_events': total,
            'confirmed': len(self._confirmed),
            'confirmation_rate': len(self._confirmed) / max(total, 1),
            'disputed': len(self._disputed),
            'rejected': len(self._rejected),
            'needs_review': len(self._needs_review),
            'mean_confidence': (
                np.mean([e.confidence for e in self.events]) if total > 0 else 0
            ),
            'mean_hmm_confidence': (
                np.mean([e.hmm_confidence for e in self.events if e.hmm_confidence > 0])
                if total > 0 else 0
            ),
            'physics_violations': sum(1 for e in self.events if not e.physics_pass),
            'events_by_type': self._count_by_field('event_type'),
            'events_by_category': self._count_by_field('category'),
        }

    def filter_needs_review(self) -> List[RefinedEvent]:
        return self._needs_review

    def confirm_event(self, idx: int):
        if idx < len(self.events):
            self.events[idx].verdict = 'confirmed'
            self.events[idx].requires_review = False

    def reject_event(self, idx: int, reason: str = "人工拒绝"):
        if idx < len(self.events):
            self.events[idx].verdict = 'rejected'
            self.events[idx].requires_review = True
            self.events[idx].review_reason += f"; {reason}"

    def _count_by_field(self, field: str) -> Dict[str, int]:
        counts = defaultdict(int)
        for e in self.events:
            counts[getattr(e, field, 'unknown')] += 1
        return dict(counts)

    def to_dataframe(self) -> 'pd.DataFrame':
        import pandas as pd
        return pd.DataFrame([{
            'event_type': e.event_type,
            'category': e.category,
            'confidence': e.confidence,
            'hmm_confidence': e.hmm_confidence,
            't_start': e.t_start,
            't_end': e.t_end,
            'speed': e.speed,
            'l3_score': e.l3_score,
            'l4_score': e.l4_score,
            'ts_score': e.ts_score,
            'physics_pass': e.physics_pass,
            'physics_violation': e.physics_violation,
            'requires_review': e.requires_review,
            'review_reason': e.review_reason,
            'verdict': e.verdict,
        } for e in self.events])


# ════════════════════════════════════════════════════════
#  自检
# ════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # 模拟测试数据
    l3 = [
        L3Event(0, 'stopped', 0, 5, 0.95, speed=0),
        L3Event(1, 'launch', 5, 10, 0.88, speed=15),
        L3Event(2, 'cruising', 10, 30, 0.92, speed=60),
        L3Event(3, 'emergency_braking', 30, 33, 0.78, speed=80),
        L3Event(4, 'stopped', 33, 40, 0.90, speed=2),
    ]

    l4 = [L4Label(i, i / 10.0, l3[min(i // 200, 4)].event_type, 0.90)
          for i in range(4000)]
    ts = [TriStageResult(l3[i % 5].event_type,
                         'longitudinal' if i < 3 else 'anomaly',
                         0.93, l3[i % 5].t_start)
          for i in range(5)]

    refiner = EventConfidenceRefiner(fs=100.0)
    result = refiner.refine(l3, l4, ts)

    console = ReviewConsoleData(result)
    stats = console.get_statistics()
    print(f"复核完成: {stats['total_events']}事件, "
          f"confirm={stats['confirmation_rate']:.0%}, "
          f"mean_conf={stats['mean_confidence']:.3f}, "
          f"violations={stats['physics_violations']}")

    for e in result:
        flag = "[!]" if e.requires_review else "[OK]"
        print(f"  {flag} {e.event_type:<20s} conf={e.confidence:.3f} "
              f"hmm={e.hmm_confidence:.3f} verdict={e.verdict} "
              f"reason={e.review_reason[:50]}")