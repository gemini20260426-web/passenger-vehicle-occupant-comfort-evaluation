#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件数据映射器：管理实时行为监控事件与全量数据的映射关系
用于事件-数据联动分析
"""
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)

# 导入核心类型
try:
    from core.core.analysis.core_types import ManeuverEvent, RiskLevel, BEHAVIOR_LABELS_CN
except ImportError:
    # 如果导入失败，定义简化版
    BEHAVIOR_LABELS_CN = {}
    ManeuverEvent = None


@dataclass
class BehaviorEvent:
    """行为事件数据结构"""
    event_id: int
    behavior: str           # 行为类型（如'急加速', '急刹车'等）
    start_ts: float         # 起始时间戳
    end_ts: float           # 结束时间戳
    behavior_type: str = "" # 原始行为类型
    duration: float = 0.0   # 持续时间
    severity: float = 0.0   # 严重程度
    risk_level: str = 'low' # 风险等级
    risk_score: float = 0.0 # 风险分数
    confidence: float = 0.0 # 置信度
    peak_ax: float = 0.0    # 峰值纵向加速度
    peak_ay: float = 0.0    # 峰值横向加速度
    peak_jerk: float = 0.0  # 峰值加加速度
    speed_range: Tuple[float, float] = (0.0, 0.0) # 速度范围
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.duration <= 0 and self.end_ts > self.start_ts:
            self.duration = self.end_ts - self.start_ts


class EventDataMapper:
    """事件数据映射器
    
    功能：
    - 管理实时行为监控事件列表
    - 支持事件注册与查询
    - 支持按时间区间查询全量数据
    - 支持事件与数据的双向联动
    - 支持从 ManeuverEvent 转换
    """
    
    def __init__(self):
        self._events: Dict[int, BehaviorEvent] = {}
        self._next_id: int = 1
        self._lock = threading.RLock()
    
    def _risk_level_to_str(self, risk_level) -> str:
        """转换 RiskLevel 枚举为字符串"""
        if hasattr(risk_level, 'value'):
            level = risk_level.value
        else:
            level = str(risk_level)
        
        level_map = {
            'SAFE': 'low',
            'safe': 'low',
            'CAUTION': 'medium',
            'caution': 'medium',
            'WARNING': 'high',
            'warning': 'high',
            'DANGER': 'high',
            'danger': 'high'
        }
        return level_map.get(level, 'low')
    
    def register_maneuver_event(self, maneuver_event) -> int:
        """从 ManeuverEvent 注册事件
        
        Args:
            maneuver_event: ManeuverEvent 对象
        
        Returns:
            event_id: 事件ID，如果已存在则返回已有ID
        """
        if maneuver_event is None:
            return -1
        
        with self._lock:
            maneuver_id = getattr(maneuver_event, 'id', '') or getattr(maneuver_event, 'event_id', '')
            if maneuver_id:
                for eid, existing in self._events.items():
                    existing_mid = getattr(existing, 'maneuver_id', '')
                    if existing_mid == maneuver_id:
                        return eid
            
            behavior_cn = BEHAVIOR_LABELS_CN.get(maneuver_event.type, maneuver_event.type)
            
            risk_str = self._risk_level_to_str(maneuver_event.risk_level)
            
            severity = min(1.0, max(0.0, maneuver_event.risk_score))
            
            event_id = self._next_id
            event = BehaviorEvent(
                event_id=event_id,
                behavior=behavior_cn,
                behavior_type=maneuver_event.type,
                start_ts=maneuver_event.start_time,
                end_ts=maneuver_event.end_time,
                duration=maneuver_event.duration,
                severity=severity,
                risk_level=risk_str,
                risk_score=maneuver_event.risk_score,
                confidence=maneuver_event.confidence,
                peak_ax=maneuver_event.peak_ax,
                peak_ay=maneuver_event.peak_ay,
                peak_jerk=maneuver_event.peak_jerk,
                speed_range=maneuver_event.speed_range
            )
            event.maneuver_id = maneuver_id
            self._events[event_id] = event
            self._next_id += 1
            logger.info(f"注册事件: [{event_id}] {behavior_cn} ({maneuver_event.start_time:.2f}-{maneuver_event.end_time:.2f})")
            return event_id
        
    def register_event(
        self,
        behavior: str,
        start_ts: float,
        end_ts: float,
        severity: float = 0.0,
        risk_level: str = 'low'
    ) -> int:
        """注册一个新事件
        
        Args:
            behavior: 行为类型
            start_ts: 起始时间戳
            end_ts: 结束时间戳
            severity: 严重程度 (0.0-1.0)
            risk_level: 风险等级 ('low', 'medium', 'high')
        
        Returns:
            event_id: 事件ID
        """
        with self._lock:
            event_id = self._next_id
            self._events[event_id] = BehaviorEvent(
                event_id=event_id,
                behavior=behavior,
                start_ts=start_ts,
                end_ts=end_ts,
                severity=severity,
                risk_level=risk_level
            )
            self._next_id += 1
            return event_id
    
    def get_event(self, event_id: int) -> Optional[BehaviorEvent]:
        """获取指定ID的事件
        
        Args:
            event_id: 事件ID
        
        Returns:
            BehaviorEvent 对象或 None
        """
        with self._lock:
            return self._events.get(event_id)
    
    def delete_event(self, event_id: int) -> bool:
        """删除指定ID的事件
        
        Args:
            event_id: 事件ID
        
        Returns:
            是否删除成功
        """
        with self._lock:
            if event_id in self._events:
                del self._events[event_id]
                return True
            return False
    
    def list_events(
        self,
        time_range: Optional[Tuple[float, float]] = None,
        behavior_filter: Optional[str] = None
    ) -> List[BehaviorEvent]:
        """获取事件列表（可筛选）
        
        Args:
            time_range: 时间范围筛选 (start, end)
            behavior_filter: 行为类型筛选
        
        Returns:
            符合条件的事件列表（按时间排序）
        """
        with self._lock:
            events = list(self._events.values())
            
            # 按时间排序
            events.sort(key=lambda e: e.start_ts)
            
            # 应用筛选
            filtered = []
            for e in events:
                if behavior_filter and e.behavior != behavior_filter:
                    continue
                if time_range:
                    t_start, t_end = time_range
                    if e.end_ts < t_start or e.start_ts > t_end:
                        continue
                filtered.append(e)
            
            return filtered
    
    def get_events_in_time_range(
        self,
        start_ts: float,
        end_ts: float
    ) -> List[BehaviorEvent]:
        """获取指定时间区间内的所有事件
        
        Args:
            start_ts: 起始时间
            end_ts: 结束时间
        
        Returns:
            事件列表
        """
        return self.list_events(time_range=(start_ts, end_ts))
    
    def get_event_time_range(self, event_id: int) -> Optional[Tuple[float, float]]:
        """获取事件的时间区间
        
        Args:
            event_id: 事件ID
        
        Returns:
            (start_ts, end_ts) 或 None
        """
        event = self.get_event(event_id)
        if event:
            return (event.start_ts, event.end_ts)
        return None
    
    def clear_all_events(self) -> int:
        """清空所有事件
        
        Returns:
            清空的事件数量
        """
        with self._lock:
            count = len(self._events)
            self._events.clear()
            self._next_id = 1
            return count
    
    def get_event_count(self) -> int:
        """获取当前事件总数（线程安全）"""
        with self._lock:
            return len(self._events)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取事件统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            events = list(self._events.values())
            
            if not events:
                return {
                    'total_count': 0,
                    'behavior_counts': {},
                    'severity_range': (0.0, 0.0),
                    'time_range': (None, None)
                }
            
            # 统计行为类型
            behavior_counts = {}
            for e in events:
                behavior_counts[e.behavior] = behavior_counts.get(e.behavior, 0) + 1
            
            # 严重程度范围
            severities = [e.severity for e in events]
            
            # 时间范围
            t_min = min(e.start_ts for e in events)
            t_max = max(e.end_ts for e in events)
            
            return {
                'total_count': len(events),
                'behavior_counts': behavior_counts,
                'severity_range': (min(severities), max(severities)),
                'time_range': (t_min, t_max)
            }
    
    def export_events(self, file_path: str, format_type: str = 'json') -> bool:
        """导出事件列表（完整版）
        
        Args:
            file_path: 导出文件路径
            format_type: 格式类型 ('json' 或 'csv')
        
        Returns:
            是否导出成功
        """
        import json
        import csv
        
        events = self.list_events()
        
        if format_type == 'json':
            data = []
            for e in events:
                data.append({
                    'event_id': e.event_id,
                    'behavior': e.behavior,
                    'behavior_type': e.behavior_type,
                    'start_ts': e.start_ts,
                    'end_ts': e.end_ts,
                    'duration': e.duration,
                    'severity': e.severity,
                    'risk_level': e.risk_level,
                    'risk_score': e.risk_score,
                    'confidence': e.confidence,
                    'peak_ax': e.peak_ax,
                    'peak_ay': e.peak_ay,
                    'peak_jerk': e.peak_jerk,
                    'speed_min': e.speed_range[0] if e.speed_range else 0.0,
                    'speed_max': e.speed_range[1] if e.speed_range else 0.0,
                    'created_at': e.created_at.isoformat()
                })
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"导出 {len(events)} 个事件到 {file_path}")
            return True
        
        elif format_type == 'csv':
            fieldnames = [
                'event_id', 'behavior', 'behavior_type', 'start_ts', 'end_ts',
                'duration', 'severity', 'risk_level', 'risk_score',
                'confidence', 'peak_ax', 'peak_ay', 'peak_jerk',
                'speed_min', 'speed_max', 'created_at'
            ]
            
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for e in events:
                    writer.writerow({
                        'event_id': e.event_id,
                        'behavior': e.behavior,
                        'behavior_type': e.behavior_type,
                        'start_ts': e.start_ts,
                        'end_ts': e.end_ts,
                        'duration': e.duration,
                        'severity': e.severity,
                        'risk_level': e.risk_level,
                        'risk_score': e.risk_score,
                        'confidence': e.confidence,
                        'peak_ax': e.peak_ax,
                        'peak_ay': e.peak_ay,
                        'peak_jerk': e.peak_jerk,
                        'speed_min': e.speed_range[0] if e.speed_range else 0.0,
                        'speed_max': e.speed_range[1] if e.speed_range else 0.0,
                        'created_at': e.created_at.isoformat()
                    })
            logger.info(f"导出 {len(events)} 个事件到 {file_path}")
            return True
        
        return False
    
    def get_all_events(self) -> List[BehaviorEvent]:
        """获取所有事件"""
        return self.list_events()
    
    def batch_register_maneuver_events(self, maneuver_events: List) -> int:
        """批量注册 ManeuverEvent
        
        Args:
            maneuver_events: ManeuverEvent 列表
        
        Returns:
            注册的事件数
        """
        count = 0
        for event in maneuver_events:
            if event is not None:
                event_id = self.register_maneuver_event(event)
                if event_id > 0:
                    count += 1
        return count


# 全局单例实例
_g_mapper: Optional[EventDataMapper] = None


def get_event_mapper() -> EventDataMapper:
    """获取全局事件数据映射器实例"""
    global _g_mapper
    if _g_mapper is None:
        _g_mapper = EventDataMapper()
    return _g_mapper


def reset_event_mapper() -> None:
    """重置全局事件数据映射器"""
    global _g_mapper
    _g_mapper = None


def main():
    """命令行测试"""
    print("=" * 80)
    print("事件数据映射器测试")
    print("=" * 80)
    
    mapper = EventDataMapper()
    
    # 注册测试事件
    print("\n--- 注册测试事件 ---")
    event_ids = [
        mapper.register_event("急加速", 10.0, 12.0, 0.8, "high"),
        mapper.register_event("急刹车", 15.0, 17.0, 0.9, "high"),
        mapper.register_event("急转弯", 20.0, 22.0, 0.6, "medium"),
        mapper.register_event("急加速", 25.0, 27.0, 0.7, "medium"),
    ]
    print(f"注册了 {len(event_ids)} 个事件")
    
    # 获取事件列表
    print("\n--- 事件列表 ---")
    events = mapper.list_events()
    for e in events:
        print(f"  [{e.event_id}] {e.behavior} ({e.start_ts:.1f} - {e.end_ts:.1f})")
    
    # 获取统计信息
    print("\n--- 统计信息 ---")
    stats = mapper.get_stats()
    print(f"  总事件数: {stats['total_count']}")
    print(f"  行为统计: {stats['behavior_counts']}")
    print(f"  时间范围: {stats['time_range']}")
    
    # 测试按时间区间查询
    print("\n--- 时间区间查询 (14.0-24.0) ---")
    events_in_range = mapper.get_events_in_time_range(14.0, 24.0)
    for e in events_in_range:
        print(f"  [{e.event_id}] {e.behavior}")
    
    # 测试单个事件获取
    print("\n--- 获取单个事件 (ID: 2) ---")
    event = mapper.get_event(2)
    if event:
        print(f"  行为: {event.behavior}")
        print(f"  时间: {event.start_ts:.1f} - {event.end_ts:.1f}")
        print(f"  风险等级: {event.risk_level}")
    
    # 测试删除事件
    print("\n--- 删除事件 (ID: 1) ---")
    deleted = mapper.delete_event(1)
    print(f"  删除成功: {deleted}")
    print(f"  剩余事件数: {len(mapper.list_events())}")
    
    # 测试清空
    print("\n--- 清空所有事件 ---")
    cleared = mapper.clear_all_events()
    print(f"  清空了 {cleared} 个事件")


if __name__ == '__main__':
    main()
