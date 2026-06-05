#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件时间线 Widget (U4: EventTimeline)

水平时间轴标注检测到的驾驶事件:
- 时间轴可视化 (0-48s)
- 事件标记点 (不同颜色表示不同类别)
- 悬停显示指标卡片
- 事件筛选
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QComboBox, QScrollArea, QFrame,
                               QToolTip, QSizePolicy)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QPainterPath,
                           QLinearGradient)

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """时间线事件"""
    event_id: str
    event_type: str
    category: str  # longitudinal / lateral / composite / anomaly / state
    start_time: float
    end_time: float
    confidence: float
    priority: int  # 0-3
    description: str = ''
    metrics: Dict[str, float] = None


class EventTimeline(QWidget):
    """事件时间线 (U4)

    功能:
    - 水平时间轴
    - 事件标记点 (按类别着色)
    - 悬停显示详情卡片
    - 事件筛选
    - 优先级高亮
    """

    CATEGORY_COLORS = {
        'longitudinal': QColor('#2196F3'),  # 蓝色
        'lateral': QColor('#4CAF50'),       # 绿色
        'composite': QColor('#FF9800'),     # 橙色
        'anomaly': QColor('#F44336'),       # 红色
        'state': QColor('#9C27B0'),         # 紫色
    }

    CATEGORY_NAMES = {
        'longitudinal': '纵向事件',
        'lateral': '侧向事件',
        'composite': '复合事件',
        'anomaly': '异常事件',
        'state': '状态事件',
    }

    event_clicked = Signal(dict)  # 点击事件详情
    event_hovered = Signal(dict)  # 悬停事件

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: List[TimelineEvent] = []
        self._time_range: Tuple[float, float] = (0, 50)
        self._hovered_event: Optional[TimelineEvent] = None
        self._show_all = True
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("事件时间线")
        title_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        title_label.setStyleSheet("color: #e0e0e0;")
        title_layout.addWidget(title_label)

        # 事件计数
        self.count_label = QLabel("0 个事件")
        self.count_label.setStyleSheet("color: #aaa;")
        title_layout.addWidget(self.count_label)
        title_layout.addStretch()

        # 筛选
        self.category_filter = QComboBox()
        self.category_filter.addItem("全部类别", "all")
        for cat, name in self.CATEGORY_NAMES.items():
            self.category_filter.addItem(name, cat)
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        title_layout.addWidget(QLabel("筛选:"))
        title_layout.addWidget(self.category_filter)
        main_layout.addLayout(title_layout)

        # 图例
        legend_layout = QHBoxLayout()
        for cat, color in self.CATEGORY_COLORS.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color.name()}; font-size: 12px;")
            legend_layout.addWidget(dot)
            label = QLabel(self.CATEGORY_NAMES.get(cat, cat))
            label.setStyleSheet("color: #aaa; font-size: 10px;")
            legend_layout.addWidget(label)
        legend_layout.addStretch()
        main_layout.addLayout(legend_layout)

        # 时间轴画布
        self.canvas = TimelineCanvas(self)
        self.canvas.event_clicked.connect(self._on_event_clicked)
        self.canvas.event_hovered.connect(self._on_event_hovered)
        main_layout.addWidget(self.canvas)

        # 详情区域
        self.detail_widget = QLabel("悬停事件查看详情")
        self.detail_widget.setStyleSheet("""
            color: #aaa; background: #1a1a2e; border: 1px solid #333; 
            border-radius: 4px; padding: 8px; font-size: 11px;
        """)
        self.detail_widget.setMinimumHeight(60)
        main_layout.addWidget(self.detail_widget)

        self.setStyleSheet("background: #16213e;")

    def set_events(self, events: List[TimelineEvent]):
        """设置事件列表"""
        self._events = sorted(events, key=lambda e: e.start_time)
        self._update_time_range()
        self.canvas.set_events(self._get_filtered_events(), self._time_range)
        self.count_label.setText(f"{len(events)} 个事件")

    def add_event(self, event: TimelineEvent):
        """添加单个事件"""
        self._events.append(event)
        self._events.sort(key=lambda e: e.start_time)
        self._update_time_range()
        self.canvas.set_events(self._get_filtered_events(), self._time_range)
        self.count_label.setText(f"{len(self._events)} 个事件")

    def _get_filtered_events(self) -> List[TimelineEvent]:
        """获取筛选后的事件"""
        filter_cat = self.category_filter.currentData()
        if filter_cat == 'all':
            return self._events
        return [e for e in self._events if e.category == filter_cat]

    def _update_time_range(self):
        if self._events:
            t_min = min(e.start_time for e in self._events)
            t_max = max(e.end_time for e in self._events)
            margin = (t_max - t_min) * 0.05 or 1.0
            self._time_range = (t_min - margin, t_max + margin)
        else:
            self._time_range = (0, 50)

    def _on_filter_changed(self):
        self.canvas.set_events(self._get_filtered_events(), self._time_range)

    def _on_event_clicked(self, event_data: dict):
        self.event_clicked.emit(event_data)

    def _on_event_hovered(self, event_data: dict):
        """显示悬停详情"""
        if event_data:
            e = event_data
            detail = (
                f"事件: {e.get('type', '')} | "
                f"时间: {e.get('start', 0):.1f}s - {e.get('end', 0):.1f}s | "
                f"置信度: {e.get('confidence', 0):.1%} | "
                f"优先级: P{e.get('priority', 3)} | "
                f"类别: {self.CATEGORY_NAMES.get(e.get('category', ''), '')}"
            )
            self.detail_widget.setText(detail)
            self.detail_widget.setStyleSheet(self.detail_widget.styleSheet().replace(
                'color: #aaa;', 'color: #e0e0e0;'))
        else:
            self.detail_widget.setText("悬停事件查看详情")
            self.detail_widget.setStyleSheet(self.detail_widget.styleSheet().replace(
                'color: #e0e0e0;', 'color: #aaa;'))

        self.event_hovered.emit(event_data or {})


class TimelineCanvas(QWidget):
    """时间轴画布"""

    event_clicked = Signal(dict)
    event_hovered = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: List[TimelineEvent] = []
        self._time_range: Tuple[float, float] = (0, 50)
        self._hovered_idx: int = -1
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

    def set_events(self, events: List[TimelineEvent], time_range: Tuple[float, float]):
        self._events = events
        self._time_range = time_range
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        idx = self._hit_test_event(pos)
        if idx != self._hovered_idx:
            self._hovered_idx = idx
            self.update()
            if idx >= 0:
                e = self._events[idx]
                self.event_hovered.emit({
                    'type': e.event_type,
                    'start': e.start_time,
                    'end': e.end_time,
                    'confidence': e.confidence,
                    'priority': e.priority,
                    'category': e.category,
                    'description': e.description
                })
            else:
                self.event_hovered.emit({})

    def leaveEvent(self, event):
        self._hovered_idx = -1
        self.update()
        self.event_hovered.emit({})

    def mousePressEvent(self, event):
        pos = event.position()
        idx = self._hit_test_event(pos)
        if idx >= 0:
            e = self._events[idx]
            self.event_clicked.emit({
                'type': e.event_type,
                'start': e.start_time,
                'end': e.end_time,
                'confidence': e.confidence,
                'priority': e.priority,
                'category': e.category,
                'description': e.description,
                'metrics': e.metrics or {}
            })

    def _hit_test_event(self, pos: QPointF) -> int:
        """检测鼠标位置对应的事件"""
        w, h = self.width(), self.height()
        margin = {'left': 50, 'right': 20, 'top': 20, 'bottom': 30}
        plot_w = w - margin['left'] - margin['right']
        t_min, t_max = self._time_range
        time_span = t_max - t_min or 1

        for i, event in enumerate(self._events):
            x_start = margin['left'] + (event.start_time - t_min) / time_span * plot_w
            x_end = margin['left'] + (event.end_time - t_min) / time_span * plot_w
            if x_start - 5 <= pos.x() <= x_end + 5 and margin['top'] <= pos.y() <= h - margin['bottom']:
                return i
        return -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 背景
        painter.fillRect(0, 0, w, h, QColor('#1a1a2e'))

        margin = {'left': 50, 'right': 20, 'top': 20, 'bottom': 30}
        plot_w = w - margin['left'] - margin['right']

        t_min, t_max = self._time_range
        time_span = t_max - t_min or 1

        # 主时间轴
        axis_y = h - margin['bottom']
        pen = QPen(QColor('#555'), 2)
        painter.setPen(pen)
        painter.drawLine(QPointF(margin['left'], axis_y),
                         QPointF(w - margin['right'], axis_y))

        # 时间刻度
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        n_ticks = min(10, int(time_span))
        for i in range(n_ticks + 1):
            t = t_min + i * time_span / n_ticks
            x = margin['left'] + i * plot_w / n_ticks
            painter.setPen(QColor('#555'))
            painter.drawLine(QPointF(x, axis_y - 5), QPointF(x, axis_y + 5))
            painter.setPen(QColor('#aaa'))
            painter.drawText(QRectF(x - 20, axis_y + 8, 40, 15),
                             Qt.AlignCenter, f"{t:.1f}s")

        # 事件标记
        row_height = 25
        n_rows = max(1, (h - margin['top'] - margin['bottom']) // row_height)

        for i, event in enumerate(self._events):
            x_start = margin['left'] + (event.start_time - t_min) / time_span * plot_w
            x_end = margin['left'] + (event.end_time - t_min) / time_span * plot_w
            event_w = max(8, x_end - x_start)

            row = i % n_rows
            y = margin['top'] + row * row_height + 5

            color = self._get_event_color(event)
            is_hovered = (i == self._hovered_idx)

            if is_hovered:
                # 高亮效果
                glow = QColor(color.red(), color.green(), color.blue(), 60)
                painter.fillRect(QRectF(x_start - 3, y - 2, event_w + 6, 18), QBrush(glow))
                painter.setPen(QPen(QColor('#FFD700'), 2))
            else:
                painter.setPen(Qt.NoPen)

            # 事件条
            painter.setBrush(QBrush(color))
            rect = QRectF(x_start, y, event_w, 14)
            painter.drawRoundedRect(rect, 3, 3)

            # 事件类型缩写
            if event_w > 30:
                font = QFont('Segoe UI', 7)
                painter.setFont(font)
                painter.setPen(QColor('#fff'))
                short_name = self._shorten_name(event.event_type, int(event_w / 5))
                painter.drawText(rect, Qt.AlignCenter, short_name)

            # 优先级标记
            if event.priority <= 1:
                painter.setPen(QPen(QColor('#FFD700'), 1.5))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(QRectF(x_start - 1, y - 1, event_w + 2, 16), 4, 4)

    def _get_event_color(self, event: TimelineEvent) -> QColor:
        """获取事件颜色"""
        base = EventTimeline.CATEGORY_COLORS.get(event.category, QColor('#888'))
        alpha = max(100, int(255 * event.confidence))
        return QColor(base.red(), base.green(), base.blue(), alpha)

    @staticmethod
    def _shorten_name(name: str, max_chars: int) -> str:
        """缩短事件名称"""
        name_map = {
            'emergency_braking': '急刹',
            'hard_acceleration': '急加速',
            'sharp_turn': '急转弯',
            'lane_change': '变道',
            'speed_bump': '减速带',
            'pothole_impact': '坑洞',
            'sudden_stop': '骤停',
            'rapid_lane_change': '快速变道',
            'combined_braking_turn': '制动+转向',
            'combined_accel_turn': '加速+转向',
        }
        short = name_map.get(name, name[:max_chars])
        return short[:max_chars]