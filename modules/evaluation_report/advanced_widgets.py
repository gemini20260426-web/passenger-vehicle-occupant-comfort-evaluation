#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级UI组件集 (U7-U10)

包含:
- U7: 置信度可视化 (ConfidenceVisualizer)
- U8: 脊柱传递路径图 (SpinePathDiagram)
- U9: 历史对比模式 (HistoryComparison)
- U10: 实时数据流监控 (StreamMonitor)
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QProgressBar, QFrame, QScrollArea,
                               QSizePolicy)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QPainterPath,
                           QLinearGradient, QRadialGradient)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# U7: 置信度可视化
# ══════════════════════════════════════════════════════════════════════════════

class ConfidenceVisualizer(QWidget):
    """置信度可视化 (U7)

    每个检测结果旁显示置信度进度条:
    - 绿色 >95%
    - 黄色 >85%
    - 红色 <85%
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[Dict[str, Any]] = []
        self.setMinimumWidth(200)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        title = QLabel("置信度")
        title.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        self.content_layout.addStretch()

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        self.setStyleSheet("background: #16213e;")

    def set_items(self, items: List[Dict[str, Any]]):
        """设置置信度项目

        Args:
            items: [{'label': str, 'confidence': float, 'level': str}, ...]
        """
        self._items = items
        self._rebuild()

    def _rebuild(self):
        # 清空
        for i in reversed(range(self.content_layout.count())):
            w = self.content_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        for item in self._items:
            bar = ConfidenceBar(item.get('label', ''), item.get('confidence', 0))
            self.content_layout.insertWidget(self.content_layout.count() - 1, bar)

        self.content_layout.addStretch()


class ConfidenceBar(QWidget):
    """单条置信度进度条"""

    def __init__(self, label: str, confidence: float, parent=None):
        super().__init__(parent)
        self.label = label
        self.confidence = confidence
        self.setFixedHeight(24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 标签
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        painter.setPen(QColor('#aaa'))
        painter.drawText(5, 14, self.label)

        # 进度条背景
        bar_x = 100
        bar_w = w - bar_x - 60
        bar_h = 12
        bar_y = (h - bar_h) / 2

        painter.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor('#333'))

        # 进度条填充
        if self.confidence >= 0.95:
            color = QColor('#4CAF50')
        elif self.confidence >= 0.85:
            color = QColor('#FFC107')
        elif self.confidence >= 0.70:
            color = QColor('#FF9800')
        else:
            color = QColor('#F44336')

        fill_w = bar_w * max(0, min(1, self.confidence))
        painter.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), QBrush(color))

        # 百分比文字
        painter.setPen(QColor('#e0e0e0'))
        painter.drawText(bar_x + bar_w + 5, 14, f"{self.confidence:.0%}")


# ══════════════════════════════════════════════════════════════════════════════
# U8: 脊柱传递路径图
# ══════════════════════════════════════════════════════════════════════════════

class SpinePathDiagram(QWidget):
    """脊柱传递路径图 (U8)

    5位置连线图:
    底板 → 座垫 → 胸骨 → 头部
    箭头标注传递率% + 颜色编码
    """

    POSITIONS = [
        {'id': 'floor', 'name': '底板', 'x': 0.5, 'y': 0.85},
        {'id': 'seat', 'name': '座垫', 'x': 0.5, 'y': 0.65},
        {'id': 'sternum', 'name': '胸骨', 'x': 0.5, 'y': 0.40},
        {'id': 'head', 'name': '头部', 'x': 0.5, 'y': 0.15},
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._transfer_rates: Dict[str, float] = {}  # {from_id: rate_pct}
        self.setMinimumSize(250, 350)

    def set_transfer_rates(self, rates: Dict[str, float]):
        """设置传递率

        Args:
            rates: {'floor_to_seat': 80.4, 'seat_to_sternum': 65.2, 'sternum_to_head': 45.1}
        """
        self._transfer_rates = rates
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 背景
        painter.fillRect(0, 0, w, h, QColor('#1a1a2e'))

        # 计算位置
        margin = 40
        plot_w = w - 2 * margin
        plot_h = h - 2 * margin

        positions = {}
        for pos in self.POSITIONS:
            px = margin + pos['x'] * plot_w
            py = margin + pos['y'] * plot_h
            positions[pos['id']] = (px, py)

        # 绘制连接线
        connections = [
            ('floor', 'seat', 'floor_to_seat'),
            ('seat', 'sternum', 'seat_to_sternum'),
            ('sternum', 'head', 'sternum_to_head'),
        ]

        for from_id, to_id, rate_key in connections:
            if from_id not in positions or to_id not in positions:
                continue

            x1, y1 = positions[from_id]
            x2, y2 = positions[to_id]

            rate = self._transfer_rates.get(rate_key, 0)

            # 线宽根据传递率
            line_w = 2 + abs(rate) / 50
            if rate > 80:
                color = QColor('#4CAF50')
            elif rate > 50:
                color = QColor('#FFC107')
            elif rate > 30:
                color = QColor('#FF9800')
            else:
                color = QColor('#F44336')

            pen = QPen(color, line_w)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # 箭头
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            self._draw_arrow(painter, QPointF(x1, y1), QPointF(x2, y2), color)

            # 传递率标注
            font = QFont('Segoe UI', 9, QFont.Bold)
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(QRectF(mid_x - 40, mid_y - 15, 80, 20),
                             Qt.AlignCenter, f"{rate:.1f}%")

        # 绘制节点
        for pos_info in self.POSITIONS:
            pid = pos_info['id']
            if pid not in positions:
                continue
            px, py = positions[pid]

            # 节点圆圈
            gradient = QRadialGradient(px - 3, py - 3, 25)
            gradient.setColorAt(0, QColor('#2196F3'))
            gradient.setColorAt(0.7, QColor('#1565C0'))
            gradient.setColorAt(1, QColor('#0D47A1'))

            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor('#64B5F6'), 2))
            painter.drawEllipse(QPointF(px, py), 18, 18)

            # 标签
            font = QFont('Segoe UI', 10, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QColor('#fff'))
            painter.drawText(QRectF(px - 30, py - 8, 60, 20),
                             Qt.AlignCenter, pos_info['name'])

    def _draw_arrow(self, painter, p1: QPointF, p2: QPointF, color: QColor):
        """绘制箭头"""
        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        arrow_len = 10
        arrow_angle = math.pi / 6

        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2

        x1 = mid_x - arrow_len * math.cos(angle - arrow_angle)
        y1 = mid_y - arrow_len * math.sin(angle - arrow_angle)
        x2 = mid_x - arrow_len * math.cos(angle + arrow_angle)
        y2 = mid_y - arrow_len * math.sin(angle + arrow_angle)

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(mid_x, mid_y)
        path.lineTo(x1, y1)
        path.lineTo(x2, y2)
        path.closeSubpath()
        painter.drawPath(path)


# ══════════════════════════════════════════════════════════════════════════════
# U9: 历史对比模式
# ══════════════════════════════════════════════════════════════════════════════

class HistoryComparison(QWidget):
    """历史对比模式 (U9)

    选择历史记录作为Baseline，当前值显示改善/退化 + 颜色箭头
    """

    history_selected = Signal(str)  # 选择的基线ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._baselines: List[Dict[str, Any]] = []
        self._comparison_results: Dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("历史对比")
        title.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)
        self.setStyleSheet("background: #16213e;")

    def set_comparison(self, results: Dict[str, Any]):
        """设置对比结果

        Args:
            results: {metric_id: ComparisonResult}
        """
        self._comparison_results = results
        self._rebuild()

    def _rebuild(self):
        # 清空
        for i in reversed(range(self.content_layout.count())):
            w = self.content_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        for metric_id, result in self._comparison_results.items():
            row = ComparisonRow(metric_id, result)
            self.content_layout.insertWidget(self.content_layout.count() - 1, row)

        self.content_layout.addStretch()


class ComparisonRow(QWidget):
    """单行对比结果"""

    def __init__(self, metric_id: str, result, parent=None):
        super().__init__(parent)
        self.metric_id = metric_id
        self.result = result
        self.setFixedHeight(28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = self.result

        # 指标名
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        painter.setPen(QColor('#aaa'))
        short_name = self.metric_id[:20]
        painter.drawText(5, 16, short_name)

        # 变化百分比
        change_pct = getattr(r, 'change_pct', 0) if hasattr(r, 'change_pct') else 0
        direction = getattr(r, 'direction', 'stable') if hasattr(r, 'direction') else 'stable'

        if direction == 'improved':
            color = QColor('#4CAF50')
            arrow = '↓'
        elif direction == 'degraded':
            color = QColor('#F44336')
            arrow = '↑'
        else:
            color = QColor('#9E9E9E')
            arrow = '→'

        painter.setPen(color)
        font = QFont('Segoe UI', 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(120, 16, f"{arrow} {change_pct:+.1f}%")

        # 迷你进度条
        bar_x = 200
        bar_w = w - bar_x - 10
        bar_h = 8
        bar_y = (h - bar_h) / 2

        painter.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor('#333'))

        abs_change = min(abs(change_pct), 100)
        fill_w = bar_w * abs_change / 100
        painter.fillRect(QRectF(bar_x, bar_y, fill_w, bar_h), QBrush(color))


# ══════════════════════════════════════════════════════════════════════════════
# U10: 实时数据流监控
# ══════════════════════════════════════════════════════════════════════════════

class StreamMonitor(QWidget):
    """实时数据流监控 (U10)

    波形滚动显示 (最后10s加速度) + 事件标记竖线
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_buffers = {
            'Ax': deque(maxlen=1000),
            'Ay': deque(maxlen=1000),
            'Az': deque(maxlen=1000),
        }
        self._events: List[Dict[str, Any]] = []
        self._sample_rate = 100
        self.setMinimumHeight(200)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("实时数据流监控")
        title.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        self.canvas = StreamCanvas(self._data_buffers, self._events)
        layout.addWidget(self.canvas)

        self.setStyleSheet("background: #16213e;")

        # 刷新定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.canvas.update)
        self._timer.start(50)  # 20fps

    def feed_data(self, ax: float, ay: float, az: float):
        """输入数据点"""
        self._data_buffers['Ax'].append(ax)
        self._data_buffers['Ay'].append(ay)
        self._data_buffers['Az'].append(az)

    def feed_batch(self, data: np.ndarray, sample_rate: float = 100):
        """批量输入"""
        self._sample_rate = sample_rate
        for i in range(min(len(data), 3)):
            if i < data.shape[1] if len(data.shape) > 1 else False:
                continue
            axis = ['Ax', 'Ay', 'Az'][i]
            values = data[:, i] if len(data.shape) > 1 else data
            self._data_buffers[axis].extend(values[:1000])

    def set_events(self, events: List[Dict[str, Any]]):
        """设置事件标记"""
        self._events = events


class StreamCanvas(QWidget):
    """流监控画布"""

    AXIS_COLORS = {
        'Ax': QColor('#2196F3'),
        'Ay': QColor('#4CAF50'),
        'Az': QColor('#FF9800'),
    }

    def __init__(self, data_buffers: Dict[str, deque], events: List[Dict], parent=None):
        super().__init__(parent)
        self._data_buffers = data_buffers
        self._events = events
        self.setMinimumHeight(180)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 背景
        painter.fillRect(0, 0, w, h, QColor('#0a0a1a'))

        margin = {'left': 50, 'right': 10, 'top': 10, 'bottom': 20}
        plot_w = w - margin['left'] - margin['right']
        plot_h = (h - margin['top'] - margin['bottom']) / 3

        # 网格
        painter.setPen(QPen(QColor('#1a1a3a'), 0.5))
        for i in range(4):
            y = margin['top'] + i * plot_h
            painter.drawLine(QPointF(margin['left'], y), QPointF(w - margin['right'], y))

        # 绘制三轴波形
        for axis_idx, (axis, buffer) in enumerate(self._data_buffers.items()):
            if not buffer:
                continue

            y_offset = margin['top'] + axis_idx * plot_h
            values = list(buffer)
            if len(values) < 2:
                continue

            max_val = max(abs(min(values)), abs(max(values)), 0.1)
            color = self.AXIS_COLORS.get(axis, QColor('#fff'))

            path = QPainterPath()
            x_step = plot_w / (len(values) - 1)

            for i, v in enumerate(values):
                x = margin['left'] + i * x_step
                y = y_offset + plot_h / 2 - (v / max_val) * (plot_h / 2)
                y = max(y_offset, min(y_offset + plot_h, y))
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            pen = QPen(color, 1)
            painter.setPen(pen)
            painter.drawPath(path)

            # 轴标签
            font = QFont('Segoe UI', 8)
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(5, y_offset + plot_h / 2 + 4, axis)

        # 事件标记竖线
        total_duration = len(self._data_buffers['Ax']) / 100 if self._data_buffers['Ax'] else 10
        for evt in self._events:
            t = evt.get('start_time', 0)
            x = margin['left'] + (t / total_duration) * plot_w if total_duration > 0 else margin['left']
            if margin['left'] <= x <= w - margin['right']:
                pen = QPen(QColor('#FFD700'), 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(x, margin['top']), QPointF(x, h - margin['bottom']))