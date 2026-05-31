#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测队列引擎
负责事件驱动的评测任务调度、执行和状态管理
"""

import logging
import time as _time
from typing import Dict, Any, Optional, Callable, List, Set
from collections import deque

from PySide6.QtCore import QObject, Signal, QTimer

from .eval_data_models import EventEvaluationRecord, TripSummary
from .evaluation_rules import EvaluationRulesEngine
from .imu_location_config import LOCATION_NAMES, LOCATION_IDS

logger = logging.getLogger(__name__)

# ── 从 event_detector 同步事件类型键，确保与全量解析一致 ──
_EVENT_DETECTOR_TYPES = {}
try:
    from core.core.analysis.layer3_maneuver_segmentation.event_detector import EVENT_TYPES as _DETECTOR_EVENT_TYPES
    _EVENT_DETECTOR_TYPES = dict(_DETECTOR_EVENT_TYPES)
except ImportError:
    pass

EVENT_TYPE_KEYS = list(_EVENT_DETECTOR_TYPES.keys()) if _EVENT_DETECTOR_TYPES else [
    'emergency_braking', 'weaving', 'aggressive_acceleration', 'aggressive_deceleration',
    'straight_cruise', 'cornering_acceleration', 'cornering_deceleration',
    'rapid_direction_change', 'severe_bump', 'normal_acceleration', 'normal_deceleration',
    'constant_speed', 'stopped', 'tight_turn', 'wide_turn', 'lane_change', 'u_turn',
    'skid_risk', 'rollover_risk', 'cruising', 'parked', 'lane_keeping', 'left_turn', 'right_turn',
]

try:
    from core.core.analysis.core_types import BEHAVIOR_LABELS_CN as _CORE_BEHAVIOR_LABELS_CN
except ImportError:
    _CORE_BEHAVIOR_LABELS_CN = {}

EVENT_TYPE_CN_LABELS = {
    k: _EVENT_DETECTOR_TYPES.get(k, _CORE_BEHAVIOR_LABELS_CN.get(k, k))
    for k in EVENT_TYPE_KEYS
}

TYPE_COLORS = {
    'emergency_braking': '#E74C3C',
    'weaving': '#F39C12',
    'aggressive_acceleration': '#F39C12',
    'aggressive_deceleration': '#F39C12',
    'straight_cruise': '#27AE60',
    'cornering_acceleration': '#4A90D9',
    'cornering_deceleration': '#4A90D9',
    'rapid_direction_change': '#E67E22',
    'severe_bump': '#E74C3C',
    'normal_acceleration': '#27AE60',
    'normal_deceleration': '#27AE60',
    'constant_speed': '#27AE60',
    'stopped': '#95A5A6',
    'tight_turn': '#4A90D9',
    'wide_turn': '#4A90D9',
    'lane_change': '#F39C12',
    'u_turn': '#4A90D9',
    'skid_risk': '#E74C3C',
    'rollover_risk': '#E74C3C',
    # ── 对齐 event_detector.EVENT_TYPES ──
    'cruising': '#27AE60',
    'parked': '#95A5A6',
    'lane_keeping': '#3498DB',
    'left_turn': '#4A90D9',
    'right_turn': '#4A90D9',
}


class EvaluationQueue(QObject):
    """评测队列引擎

    管理事件评测生命周期:
    1. 从EventDistributor接收事件
    2. 创建EventEvaluationRecord
    3. 匹配评测规则
    4. 调度评测执行
    5. 聚合结果到TypeAggregation / TripSummary
    """

    record_status_changed = Signal(str, str)
    evaluation_started = Signal(str)
    evaluation_completed = Signal(str, object)
    evaluation_failed = Signal(str, str)
    queue_progress = Signal(int, int)
    trip_summary_ready = Signal(object)
    type_summary_ready = Signal(str, object)
    batch_finished = Signal()
    eval_result_ready = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: Dict[str, EventEvaluationRecord] = {}
        self._type_labels: Dict[str, str] = dict(EVENT_TYPE_CN_LABELS)
        self._rules_engine = EvaluationRulesEngine()
        self._trip_summary: Optional[TripSummary] = None
        self._evaluation_engine = None
        self._data_bridge = None
        self._comparative_engine = None
        self._auto_evaluate = False
        self._processing = False
        self._cancel_flag = False
        self._queue: deque = deque()
        self._completed_ids: Set[str] = set()
        self._active_group_tags: List[str] = ['experimental', 'control']
        self._evaluated_windows: Set[tuple] = set()
        logger.info("评测队列引擎初始化完成")

    def set_active_groups(self, group_tags: List[str]):
        self._active_group_tags = group_tags
        logger.info(f"切换评测分组: {group_tags}")

    def get_type_label(self, event_type: str) -> str:
        return self._type_labels.get(event_type, event_type)

    def get_type_color(self, event_type: str) -> str:
        return TYPE_COLORS.get(event_type, '#95A5A6')

    def set_evaluation_engine(self, engine):
        self._evaluation_engine = engine

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def set_comparative_engine(self, engine):
        self._comparative_engine = engine

    def update_result(self, event_id: str, result: Dict[str, Any]):
        """更新增量评测结果到对应事件记录"""
        if event_id not in self._records:
            return
        record = self._records[event_id]
        # 将评测结果同步到记录中
        if hasattr(record, 'scores'):
            record.scores = result.get('scores', {})
        if hasattr(record, 'metrics'):
            record.metrics = result.get('metrics', [])
        if hasattr(record, 'status'):
            record.status = result.get('status', record.status)
        self.eval_result_ready.emit(event_id, record)

    @property
    def records(self) -> Dict[str, EventEvaluationRecord]:
        return self._records

    @property
    def trip_summary(self) -> Optional[TripSummary]:
        return self._trip_summary

    def sync_from_distributor(self, events: List[Any]):
        """从EventDistributor同步事件到评测队列

        一个事件 = 一条记录，不再按组分裂。
        active_groups 决定评测时计算哪些组的指标。
        """
        existing_ids = set(self._records.keys())
        new_ids = set()

        for evt in events:
            etype = getattr(evt, 'behavior_type', '') or getattr(evt, 'type', '') or getattr(evt, 'behavior', 'unknown')
            eid = getattr(evt, 'event_id', '')
            if not eid:
                eid = f'evt_{int(getattr(evt, "start_ts", 0) * 1000)}_{etype}'
            eid = str(eid)

            new_ids.add(eid)

            rule = self._rules_engine.get_rule(etype)
            thresholds = dict(rule.threshold_multipliers) if rule and rule.threshold_multipliers else {}

            if eid in self._records:
                existing = self._records[eid]
                existing.active_groups = list(self._active_group_tags)
                continue

            record_meta = dict(getattr(evt, 'metadata', None) or {})
            record_meta['original_event_id'] = eid

            record = EventEvaluationRecord(
                event_id=eid,
                event_type=etype,
                event_type_cn=self.get_type_label(etype),
                start_ts=getattr(evt, 'start_ts', 0),
                end_ts=getattr(evt, 'end_ts', 0),
                duration=getattr(evt, 'duration', 0) or (
                    getattr(evt, 'end_ts', 0) - getattr(evt, 'start_ts', 0)),
                confidence=getattr(evt, 'confidence', 0.0),
                behavior_category=str(getattr(evt, 'category', '')),
                metadata=record_meta,
                status='pending',
                active_groups=list(self._active_group_tags),
            )

            if rule:
                record.rule_applied = rule.event_type
                record.threshold_multipliers = thresholds

            self._records[eid] = record
            logger.debug(f"新增评测记录: {eid} ({self.get_type_label(etype)}) "
                         f"活动组: {record.active_groups}")

        removed_ids = existing_ids - new_ids
        for rid in removed_ids:
            del self._records[rid]

        self._resort_and_index()
        self._rebuild_trip_summary()
        logger.info(f"同步完成: {len(events)}个事件, {len(self._records)}条记录, "
                     f"新增{len(new_ids - existing_ids)}, 移除{len(removed_ids)}")

    def _resort_and_index(self):
        sorted_records = sorted(self._records.values(), key=lambda r: r.start_ts)
        type_counters: Dict[str, int] = {}
        for r in sorted_records:
            type_counters.setdefault(r.event_type, 0)
            type_counters[r.event_type] += 1
            r.metadata['instance_index'] = type_counters[r.event_type]

    def _rebuild_trip_summary(self):
        self._trip_summary = TripSummary(all_records=list(self._records.values()))
        self._trip_summary.group_tag = ', '.join(self._active_group_tags) if self._active_group_tags else 'experimental'
        self._trip_summary.compute()
        self.trip_summary_ready.emit(self._trip_summary)

    def _has_overlap(self, start_ts: float, end_ts: float) -> bool:
        threshold = 0.5
        for window in self._evaluated_windows:
            ws, we = window
            overlap_start = max(start_ts, ws)
            overlap_end = min(end_ts, we)
            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                this_duration = end_ts - start_ts
                if this_duration > 0 and overlap_duration / this_duration > threshold:
                    return True
        return False

    def _mark_evaluated(self, start_ts: float, end_ts: float):
        self._evaluated_windows.add((start_ts, end_ts))

    def clear_dedup_cache(self):
        self._evaluated_windows.clear()

    def get_records_by_type(self, event_type: str) -> List[EventEvaluationRecord]:
        return [r for r in self._records.values() if r.event_type == event_type]

    def get_record(self, record_id: str) -> Optional[EventEvaluationRecord]:
        return self._records.get(record_id)

    def get_unique_event_types(self) -> List[str]:
        seen: Dict[str, int] = {}
        for r in self._records.values():
            seen[r.event_type] = seen.get(r.event_type, 0) + 1
        return sorted(seen.keys(), key=lambda t: seen[t], reverse=True)

    def get_type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._records.values():
            counts[r.event_type] = counts.get(r.event_type, 0) + 1
        return counts

    def get_type_evaluated_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._records.values():
            if r.is_evaluated:
                counts[r.event_type] = counts.get(r.event_type, 0) + 1
        return counts

    def select_records(self, event_ids: Optional[List[str]] = None,
                       event_type: Optional[str] = None) -> List[EventEvaluationRecord]:
        if event_ids:
            return [self._records[eid] for eid in event_ids if eid in self._records]
        if event_type:
            return self.get_records_by_type(event_type)
        return list(self._records.values())

    def evaluate_selected(self, record_ids: List[str]):
        records = [self._records[eid] for eid in record_ids if eid in self._records]
        self._enqueue_records(records)

    def evaluate_by_type(self, event_type: str):
        records = self.get_records_by_type(event_type)
        self._enqueue_records(records)

    def evaluate_all(self):
        self._enqueue_records(list(self._records.values()))

    def evaluate_all_pending(self):
        records = [r for r in self._records.values() if r.status == 'pending']
        self._enqueue_records(records)

    def _enqueue_records(self, records: List[EventEvaluationRecord]):
        added = 0
        for r in records:
            if r.status not in ('evaluating',) and r.event_id not in self._queue:
                if not r.is_evaluated and self._has_overlap(r.start_ts, r.end_ts):
                    logger.debug(f"跳过重叠窗口记录: {r.event_id} "
                                 f"({r.start_ts:.3f}-{r.end_ts:.3f})")
                    continue
                self._queue.append(r.event_id)
                added += 1
        if added == 0:
            return
        self.queue_progress.emit(0, len(self._queue))
        self._process_queue()

    def _process_queue(self):
        if self._processing:
            return
        self._processing = True
        self._cancel_flag = False
        self._batch_start_time = _time.time()
        self._batch_completed = 0
        self._process_next()

    def _process_next(self):
        if not self._queue or self._cancel_flag:
            self._finish_batch()
            return

        eid = self._queue.popleft()
        record = self._records.get(eid)
        if not record:
            QTimer.singleShot(10, self._process_next)
            return

        self._evaluate_single(record)
        if record.status == 'evaluated':
            self._mark_evaluated(record.start_ts, record.end_ts)
        self._batch_completed += 1

        total = len(self._queue) + len(self._completed_ids)
        done = len(self._completed_ids)
        self.queue_progress.emit(done, total)

        QTimer.singleShot(30, self._process_next)

    def _finish_batch(self):
        self._rebuild_trip_summary()
        self.batch_finished.emit()
        self._processing = False
        elapsed = _time.time() - self._batch_start_time
        logger.info(f"评测批次完成: {self._batch_completed}个事件, 耗时{elapsed:.1f}s")

    def _evaluate_single(self, record: EventEvaluationRecord):
        if not self._evaluation_engine:
            logger.error("评测引擎未设置，无法执行评测")
            record.status = 'failed'
            self.record_status_changed.emit(record.event_id, 'failed')
            return

        record.status = 'evaluating'
        record.evaluated_at = _time.time()
        self.record_status_changed.emit(record.event_id, 'evaluating')
        self.evaluation_started.emit(record.event_id)

        try:
            data_window = {'pre': 0.5, 'post': 1.5}
            eval_start = record.start_ts - data_window['pre']
            eval_end = record.end_ts + data_window['post']
            record.data_window_range = (eval_start, eval_end)

            rule = self._rules_engine.get_rule(record.event_type)
            if rule:
                record.rule_applied = rule.event_type
                record.threshold_multipliers = dict(rule.threshold_multipliers)

            multi_channel_data = {}
            if self._data_bridge and hasattr(self._data_bridge, '_build_multi_channel_data'):
                multi_channel_data = self._data_bridge._build_multi_channel_data(
                    eval_start, eval_end
                )

            if not multi_channel_data:
                logger.warning(f"事件 {record.event_id} 没有多通道数据，标记为失败")
                record.status = 'failed'
                self.record_status_changed.emit(record.event_id, 'failed')
                self.evaluation_failed.emit(record.event_id, '没有多通道数据')
                return

            exp_imus = multi_channel_data.get('_exp_imu_set', set())
            ctrl_imus = multi_channel_data.get('_ctrl_imu_set', set())
            exp_channels = [k for k in multi_channel_data if k in exp_imus]
            ctrl_channels = [k for k in multi_channel_data if k in ctrl_imus]
            logger.info(
                f"[评测] {record.event_id}: 多通道数据已就绪, "
                f"实验组={exp_channels}, 对照组={ctrl_channels}, "
                f"时间窗口=[{eval_start:.3f}, {eval_end:.3f}]"
            )

            any_success = False
            fail_errors = []

            if 'experimental' in record.active_groups:
                try:
                    exp_trigger = {
                        'event_id': record.event_id,
                        'event_type': record.event_type,
                        'source_behavior': record.event_type,
                        'timestamp': record.start_ts,
                        'metrics': [],
                        'data_window': data_window,
                        'multi_channel_data': multi_channel_data,
                        'group_tag': 'experimental',
                    }
                    if record.threshold_multipliers:
                        exp_trigger['threshold_multipliers'] = record.threshold_multipliers
                    record.evaluation_result_exp = self._evaluation_engine.evaluate_by_event(exp_trigger)
                    if record.evaluation_result_exp is not None:
                        any_success = True
                except Exception as e:
                    fail_errors.append(f"实验组: {e}")
                    logger.warning(f"实验组评测异常: {record.event_id}, {e}")

            if 'control' in record.active_groups:
                try:
                    ctrl_trigger = {
                        'event_id': record.event_id,
                        'event_type': record.event_type,
                        'source_behavior': record.event_type,
                        'timestamp': record.start_ts,
                        'metrics': [],
                        'data_window': data_window,
                        'multi_channel_data': multi_channel_data,
                        'group_tag': 'control',
                    }
                    if record.threshold_multipliers:
                        ctrl_trigger['threshold_multipliers'] = record.threshold_multipliers
                    record.evaluation_result_ctrl = self._evaluation_engine.evaluate_by_event(ctrl_trigger)
                    if record.evaluation_result_ctrl is not None:
                        any_success = True
                except Exception as e:
                    fail_errors.append(f"对照组: {e}")
                    logger.warning(f"对照组评测异常: {record.event_id}, {e}")

            if any_success:
                record.status = 'evaluated'
                self._completed_ids.add(record.event_id)
                self.record_status_changed.emit(record.event_id, 'evaluated')
                combined_result = record.evaluation_result_exp or record.evaluation_result_ctrl
                self.evaluation_completed.emit(record.event_id, combined_result)
                self.eval_result_ready.emit(record.event_id, combined_result)
                exp_score = getattr(record.evaluation_result_exp, 'overall_score', 'N/A') if record.evaluation_result_exp else 'N/A'
                ctrl_score = getattr(record.evaluation_result_ctrl, 'overall_score', 'N/A') if record.evaluation_result_ctrl else 'N/A'
                logger.info(
                    f"评测完成: {record.event_id} ({self.get_type_label(record.event_type)}), "
                    f"实验组={exp_score}, 对照组={ctrl_score}")
            else:
                record.status = 'failed'
                self.record_status_changed.emit(record.event_id, 'failed')
                self.evaluation_failed.emit(record.event_id, '; '.join(fail_errors) or '评测引擎返回空结果')

        except Exception as e:
            record.status = 'failed'
            self.record_status_changed.emit(record.event_id, 'failed')
            self.evaluation_failed.emit(record.event_id, str(e))
            logger.error(f"评测失败: {record.event_id}, 错误: {e}", exc_info=True)

    def reevaluate_record(self, event_id: str):
        record = self._records.get(event_id)
        if record:
            record.status = 'pending'
            self._evaluate_single(record)

    def reevaluate_type(self, event_type: str):
        for r in self.get_records_by_type(event_type):
            r.status = 'pending'
            r.evaluation_result_exp = None
            r.evaluation_result_ctrl = None
        self.evaluate_by_type(event_type)

    def clear_results(self):
        for r in self._records.values():
            r.status = 'pending'
            r.evaluation_result_exp = None
            r.evaluation_result_ctrl = None
            r.evaluated_at = None
        self._completed_ids.clear()
        self._rebuild_trip_summary()

    def cancel(self):
        self._cancel_flag = True
        self._queue.clear()

    def get_event_cn_label(self, event_type: str) -> str:
        return self._type_labels.get(event_type, event_type)

    @property
    def is_processing(self) -> bool:
        return self._processing

    @property
    def pending_count(self) -> int:
        return sum(1 for r in self._records.values() if r.status == 'pending')

    @property
    def evaluated_count(self) -> int:
        return sum(1 for r in self._records.values() if r.is_evaluated)

    @property
    def total_count(self) -> int:
        return len(self._records)