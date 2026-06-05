#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标缓存与发布中心 (MetricStore) — 发布-订阅数据总线

供多个Widget订阅式更新，解耦算子计算与UI渲染。

架构:
  算子计算 → MetricStore (缓存) → 多个Widget订阅式更新
      ├── MetricDashboard     ← 订阅 RMS/VDV/Peak
      ├── ComparisonView      ← 订阅 Exp vs Ctrl
      ├── BandRadarChart      ← 订阅 五频段衰减
      ├── EventTimeline       ← 订阅 事件列表
      └── ReportExporter      ← 订阅 全量指标
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """指标快照"""
    metric_id: str
    value: float
    quality: str = 'normal'  # normal, low_confidence, unreliable
    timestamp: float = 0.0
    unit: str = ''
    location: str = ''
    group: str = ''  # experimental, control
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricStore(QObject):
    """指标缓存与发布中心 — 供多个Widget订阅"""

    metric_updated = Signal(str, dict)   # metric_id, {value, quality, timestamp, ...}
    batch_updated = Signal(list)          # [(metric_id, {value, ...}), ...]
    store_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store: Dict[str, MetricSnapshot] = {}
        self._subscribers: Dict[str, List[str]] = defaultdict(list)
        self._history: List[Dict[str, Any]] = []

    def publish(self, metric_id: str, value: float, **kwargs):
        """发布单个指标结果

        Args:
            metric_id: 指标ID
            value: 指标值
            **kwargs: quality, timestamp, unit, location, group, metadata
        """
        snapshot = MetricSnapshot(
            metric_id=metric_id,
            value=value,
            quality=kwargs.get('quality', 'normal'),
            timestamp=kwargs.get('timestamp', 0.0),
            unit=kwargs.get('unit', ''),
            location=kwargs.get('location', ''),
            group=kwargs.get('group', ''),
            metadata=kwargs.get('metadata', {})
        )
        self._store[metric_id] = snapshot

        self.metric_updated.emit(metric_id, {
            'value': value,
            'quality': snapshot.quality,
            'timestamp': snapshot.timestamp,
            'unit': snapshot.unit,
            'location': snapshot.location,
            'group': snapshot.group
        })

    def publish_batch(self, metrics: Dict[str, float], **kwargs):
        """批量发布指标结果"""
        updates = []
        for metric_id, value in metrics.items():
            self.publish(metric_id, value, **kwargs)
            updates.append((metric_id, {
                'value': value,
                'quality': kwargs.get('quality', 'normal'),
                'timestamp': kwargs.get('timestamp', 0.0)
            }))
        self.batch_updated.emit(updates)

    def subscribe(self, widget_id: str, metric_ids: List[str]):
        """Widget订阅指标

        Args:
            widget_id: Widget标识
            metric_ids: 关注的指标ID列表
        """
        self._subscribers[widget_id] = list(set(metric_ids))
        logger.debug(f"Widget '{widget_id}' subscribed to {len(metric_ids)} metrics")

    def unsubscribe(self, widget_id: str):
        """取消订阅"""
        self._subscribers.pop(widget_id, None)

    def get_snapshot(self, metric_ids: List[str] = None) -> Dict[str, MetricSnapshot]:
        """获取指标快照"""
        if metric_ids is None:
            return dict(self._store)
        return {mid: self._store[mid] for mid in metric_ids if mid in self._store}

    def get_value(self, metric_id: str, default: float = 0.0) -> float:
        """获取单个指标值"""
        snapshot = self._store.get(metric_id)
        return snapshot.value if snapshot else default

    def get_subscribers_for(self, metric_id: str) -> List[str]:
        """获取关注某指标的Widget列表"""
        return [wid for wid, mids in self._subscribers.items() if metric_id in mids]

    def save_baseline(self, label: str = ''):
        """保存当前指标快照为基线"""
        baseline = {
            'label': label or f'baseline_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'timestamp': datetime.now().timestamp(),
            'metrics': {k: v.value for k, v in self._store.items()}
        }
        self._history.append(baseline)
        logger.info(f"基线已保存: {baseline['label']} ({len(self._store)} metrics)")
        return baseline

    def compare_with_baseline(self, baseline_index: int = -1) -> Dict[str, float]:
        """与基线对比，返回变化百分比 (F4: 实时vs历史对比)"""
        if not self._history:
            return {}

        baseline = self._history[baseline_index]
        baseline_metrics = baseline['metrics']

        changes = {}
        for metric_id, snapshot in self._store.items():
            if metric_id in baseline_metrics:
                base_val = baseline_metrics[metric_id]
                curr_val = snapshot.value
                if abs(base_val) > 1e-6:
                    changes[metric_id] = round((curr_val - base_val) / abs(base_val) * 100, 2)
                else:
                    changes[metric_id] = 0.0

        return changes

    def clear(self):
        """清空Store"""
        self._store.clear()
        self._subscribers.clear()
        self.store_cleared.emit()

    @property
    def metric_count(self) -> int:
        return len(self._store)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)