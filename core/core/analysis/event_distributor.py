#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一事件分发中心 (EventDistributor) — 驾驶行为事件的唯一内存真相源

设计原则（硬约束，禁止修改）：
1. 单例模式：全局只有一个 EventDistributor 实例
2. 唯一写入入口：所有事件必须通过 register_event() 或 sync_from_cache() 写入
3. 统一事件类型：内部存储 ManeuverEvent，对外提供 ManeuverEvent 和 BehaviorEvent 两种视图
4. SQLite 同步：与 AnalysisResultCache 的 behavior_events 表保持双向同步
5. 变更通知：事件变更时通过 Qt 信号统一通知所有消费者
6. 主IMU通道约束：仅接受 IMU7_座椅底部-1 通道产生的事件
"""

import logging
import threading
from typing import Dict, List, Tuple, Optional, Any
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal

from .core_types import ManeuverEvent, BehaviorCategory, RiskLevel, BEHAVIOR_LABELS_CN

logger = logging.getLogger(__name__)

PRIMARY_IMU_NAME = 'IMU7_座椅底部-1'


class BehaviorEventView:
    """BehaviorEvent 视图 — 兼容旧 EventDataMapper 的 BehaviorEvent 接口"""

    __slots__ = (
        'event_id', 'behavior', 'start_ts', 'end_ts', 'behavior_type',
        'duration', 'severity', 'risk_level', 'risk_score', 'confidence',
        'peak_ax', 'peak_ay', 'peak_jerk', 'speed_range', 'maneuver_id',
    )

    def __init__(self, maneuver: ManeuverEvent, seq_id: int):
        self.event_id = seq_id
        self.behavior = BEHAVIOR_LABELS_CN.get(maneuver.type, maneuver.type)
        self.start_ts = maneuver.start_time
        self.end_ts = maneuver.end_time
        self.behavior_type = maneuver.type
        self.duration = maneuver.duration
        self.severity = min(1.0, max(0.0, maneuver.risk_score))
        self.risk_level = _risk_level_to_str(maneuver.risk_level)
        self.risk_score = maneuver.risk_score
        self.confidence = maneuver.confidence
        self.peak_ax = maneuver.peak_ax
        self.peak_ay = maneuver.peak_ay
        self.peak_jerk = maneuver.peak_jerk
        self.speed_range = maneuver.speed_range
        self.maneuver_id = maneuver.id


def _risk_level_to_str(risk_level) -> str:
    if hasattr(risk_level, 'value'):
        level = risk_level.value
    else:
        level = str(risk_level)
    level_map = {
        'SAFE': 'low', 'safe': 'low',
        'CAUTION': 'medium', 'caution': 'medium',
        'WARNING': 'high', 'warning': 'high',
        'DANGER': 'high', 'danger': 'high',
    }
    return level_map.get(level, 'low')


class EventDistributor(QObject):
    """统一事件分发中心 — 驾驶行为事件的唯一内存真相源

    所有模块必须通过此中心获取事件，禁止绕过直接访问 SQLite 或自行缓存。
    """

    events_changed = Signal(list)
    event_added = Signal(object)

    _instance: Optional['EventDistributor'] = None
    _instance_lock = threading.Lock()

    def __init__(self, parent=None):
        if getattr(self, '_initialized', False):
            return
        super().__init__(parent)
        self._initialized = True

        self._lock = threading.RLock()
        self._events: Dict[str, ManeuverEvent] = OrderedDict()
        self._seq_counter: int = 0
        self._analysis_cache = None

        logger.info("[EventDistributor] 统一事件分发中心已初始化")

    @classmethod
    def instance(cls) -> 'EventDistributor':
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_analysis_cache(self, cache) -> None:
        """绑定 AnalysisResultCache，用于 SQLite 同步"""
        self._analysis_cache = cache

    def sync_from_cache(self) -> int:
        """从 SQLite 同步事件到内存（全量替换）

        Returns:
            同步的事件数量
        """
        if not self._analysis_cache:
            logger.warning("[EventDistributor] 无法同步：AnalysisResultCache 未绑定")
            return 0

        with self._lock:
            try:
                # 先清理重复事件
                self._analysis_cache.clean_duplicate_events()
                
                db_events = self._analysis_cache.get_all_maneuver_events()
            except Exception as e:
                logger.error(f"[EventDistributor] 从缓存读取事件失败: {e}")
                return 0

            self._events.clear()
            self._seq_counter = 0
            for event in db_events:
                eid = getattr(event, 'event_id', '') or getattr(event, 'id', '')
                if eid:
                    self._seq_counter += 1
                    self._events[eid] = event

            logger.info(f"[EventDistributor] 从SQLite同步了 {len(self._events)} 个事件")
            self._notify_changed()
            return len(self._events)

    def register_event(self, event: ManeuverEvent) -> int:
        """注册单个事件（唯一写入入口）

        Args:
            event: ManeuverEvent 对象

        Returns:
            顺序ID（从1开始），-1表示拒绝
        """
        if event is None:
            return -1

        eid = getattr(event, 'event_id', None)
        if eid is None:
            eid = getattr(event, 'id', None)
        if eid is None or eid == '':
            logger.warning("[EventDistributor] 拒绝注册：事件缺少ID")
            return -1

        with self._lock:
            if eid in self._events:
                return self._get_seq_id(eid)

            self._seq_counter += 1
            self._events[eid] = event
            logger.info(
                f"[EventDistributor] 注册事件 #{self._seq_counter}: "
                f"{event.label_cn} ({event.start_time:.2f}s-{event.end_time:.2f}s)"
            )
            self.event_added.emit(event)
            self._notify_changed()
            return self._seq_counter

    def register_events(self, events: List[ManeuverEvent]) -> int:
        """批量注册事件

        Returns:
            新注册的事件数量
        """
        count = 0
        for event in events:
            if self.register_event(event) > 0:
                count += 1
        return count

    def get_events(
        self,
        time_range: Optional[Tuple[float, float]] = None,
        category: Optional[BehaviorCategory] = None,
    ) -> List[ManeuverEvent]:
        """获取事件列表（ManeuverEvent 视图）

        Args:
            time_range: 时间范围筛选 (start, end)
            category: 行为分类筛选

        Returns:
            按时间排序的事件列表
        """
        with self._lock:
            events = list(self._events.values())
            events.sort(key=lambda e: e.start_time)

            if time_range:
                t_start, t_end = time_range
                events = [e for e in events if not (e.end_time < t_start or e.start_time > t_end)]

            if category:
                events = [e for e in events if e.category == category]

            return events

    def get_behavior_events(
        self,
        time_range: Optional[Tuple[float, float]] = None,
        behavior_filter: Optional[str] = None,
    ) -> List[BehaviorEventView]:
        """获取事件列表（BehaviorEvent 视图，兼容旧接口）

        Args:
            time_range: 时间范围筛选
            behavior_filter: 行为类型筛选

        Returns:
            BehaviorEventView 列表
        """
        with self._lock:
            events = list(self._events.items())
            events.sort(key=lambda item: item[1].start_time)

            result = []
            for seq_idx, (eid, event) in enumerate(events, 1):
                view = BehaviorEventView(event, seq_idx)
                if behavior_filter and view.behavior != behavior_filter:
                    continue
                if time_range:
                    t_start, t_end = time_range
                    if view.end_ts < t_start or view.start_ts > t_end:
                        continue
                result.append(view)

            return result

    def get_event_by_id(self, event_id: str) -> Optional[ManeuverEvent]:
        """按事件ID获取 ManeuverEvent"""
        with self._lock:
            return self._events.get(event_id)

    def get_event_by_seq_id(self, seq_id: int) -> Optional[ManeuverEvent]:
        """按顺序ID获取 ManeuverEvent"""
        with self._lock:
            if seq_id < 1 or seq_id > len(self._events):
                return None
            return list(self._events.values())[seq_id - 1]

    def get_event_count(self) -> int:
        """获取事件总数"""
        with self._lock:
            return len(self._events)

    def get_time_range(self) -> Tuple[float, float]:
        """获取事件的时间范围"""
        with self._lock:
            if not self._events:
                return (0.0, 0.0)
            events = list(self._events.values())
            t_min = min(e.start_time for e in events)
            t_max = max(e.end_time for e in events)
            return (t_min, t_max)

    def get_stats(self) -> Dict[str, Any]:
        """获取事件统计信息"""
        with self._lock:
            events = list(self._events.values())
            if not events:
                return {
                    'total_count': 0,
                    'behavior_counts': {},
                    'time_range': (0.0, 0.0),
                }

            behavior_counts: Dict[str, int] = {}
            for e in events:
                label = e.label_cn
                behavior_counts[label] = behavior_counts.get(label, 0) + 1

            t_min = min(e.start_time for e in events)
            t_max = max(e.end_time for e in events)

            return {
                'total_count': len(events),
                'behavior_counts': behavior_counts,
                'time_range': (t_min, t_max),
            }

    def clear(self) -> int:
        """清空所有事件

        Returns:
            清空的事件数量
        """
        with self._lock:
            count = len(self._events)
            self._events.clear()
            self._seq_counter = 0
            logger.info(f"[EventDistributor] 已清空 {count} 个事件")
            self._notify_changed()
            return count

    def _get_seq_id(self, event_id: str) -> int:
        """获取事件的顺序ID"""
        for idx, eid in enumerate(self._events.keys(), 1):
            if eid == event_id:
                return idx
        return -1

    def _notify_changed(self):
        """通知所有消费者事件列表已变更"""
        events = list(self._events.values())
        events.sort(key=lambda e: e.start_time)
        self.events_changed.emit(events)