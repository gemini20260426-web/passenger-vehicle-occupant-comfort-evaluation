#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
频段衰减雷达图 Widget (U3: BandRadarChart)

五频段雷达图 (Ax/Ay/Az 三色重叠):
- 五频段: 0.1-0.5Hz, 0.5-1Hz, 1-5Hz, 5-20Hz, 20-80Hz
- 三轴重叠显示 (Ax蓝色 / Ay绿色 / Az橙色)
- 点击频段展开详细PSD
- 衰减率%标注
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QToolTip, QFrame)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QPainterPath,
                           QRadialGradient, QLinearGradient)

logger = logging.getLogger(__name__)


class BandRadarChart(QWidget):
    """频段衰减雷达图 (U3)

    五频段雷达图，三轴数据重叠显示
    """

    BAND_LABELS = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
    AXIS_COLORS = {
        'Ax': QColor(33, 150, 243, 180),
        'Ay': QColor(76, 175, 80, 180),
        'Az': QColor(255, 152, 0, 180),
    }
    AXIS_LINE_COLORS = {
        'Ax': QColor(33, 150, 243),
        'Ay': QColor(76, 175, 80),
        'Az': QColor(255, 152, 0),
    }

    band_clicked = Signal(str)  # 点击频段名称

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: Dict[str, Dict[str, float]] = {}  # {axis: {band: pct}}
        self._selected_band: Optional[str] = None
        self.setMinimumSize(300, 300)
        self.setMouseTracking(True)

    def set_data(self, axis_data: Dict[str, Dict[str, float]]):
        """设置数据

        Args:
            axis_data: {'Ax': {'0.1-0.5Hz': 80.4, ...}, 'Ay': {...}, 'Az': {...}}
        """
        self._data = axis_data
        self.update()

    def mouseMoveEvent(self, event):
        """鼠标悬停显示tooltip"""
        pos = event.position()
        band = self._hit_test_band(pos)
        if band:
            self._selected_band = band
            self.update()

            # Tooltip
            tip_parts = []
            for axis, data in self._data.items():
                if band in data:
                    tip_parts.append(f"{axis}: {data[band]:.1f}%")
            QToolTip.showText(event.globalPos(), '\n'.join(tip_parts), self)
        else:
            self._selected_band = None
            self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        band = self._hit_test_band(pos)
        if band:
            self.band_clicked.emit(band)

    def _hit_test_band(self, pos: QPointF) -> Optional[str]:
        """检测点击的频段"""
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 * 0.55
        n = len(self.BAND_LABELS)

        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 20 or dist > radius + 30:
            return None

        angle = math.atan2(-dy, dx)
        if angle < 0:
            angle += 2 * math.pi

        sector = 2 * math.pi / n
        idx = int((angle + sector / 2) % (2 * math.pi) / sector)
        idx = idx % n

        if dist > 20:
            return self.BAND_LABELS[idx]
        return None

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)
        radius = min(w, h) / 2 * 0.55

        # 背景
        painter.fillRect(0, 0, w, h, QColor('#1a1a2e'))

        # 绘制同心圆网格
        for level in range(1, 6):
            r = radius * level / 5
            pen = QPen(QColor('#333'), 0.5)
            painter.setPen(pen)
            painter.drawEllipse(center, r, r)

            # 标注
            if level == 5:
                font = QFont('Segoe UI', 8)
                painter.setFont(font)
                painter.setPen(QColor('#666'))
                painter.drawText(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r),
                                 Qt.AlignTop | Qt.AlignHCenter, '100%')
            if level == 3:
                painter.drawText(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r),
                                 Qt.AlignTop | Qt.AlignHCenter, '60%')

        # 绘制轴线和标签
        n = len(self.BAND_LABELS)
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)

            pen = QPen(QColor('#555'), 1)
            painter.setPen(pen)
            painter.drawLine(center, QPointF(x, y))

            # 标签
            label_x = center.x() + (radius + 25) * math.cos(angle)
            label_y = center.y() + (radius + 25) * math.sin(angle)
            font = QFont('Segoe UI', 8)
            painter.setFont(font)
            painter.setPen(QColor('#aaa'))
            rect = QRectF(label_x - 40, label_y - 10, 80, 20)
            painter.drawText(rect, Qt.AlignCenter, self.BAND_LABELS[i])

        # 绘制数据多边形
        for axis, data in self._data.items():
            if not data:
                continue

            points = []
            for i, band in enumerate(self.BAND_LABELS):
                val = data.get(band, 0)
                r = radius * max(0, min(100, val)) / 100
                angle = 2 * math.pi * i / n - math.pi / 2
                x = center.x() + r * math.cos(angle)
                y = center.y() + r * math.sin(angle)
                points.append(QPointF(x, y))

            if len(points) < 3:
                continue

            # 填充
            path = QPainterPath()
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
            path.closeSubpath()

            fill_color = self.AXIS_COLORS.get(axis, QColor(128, 128, 128, 100))
            painter.fillPath(path, QBrush(fill_color))

            # 边框
            pen = QPen(self.AXIS_LINE_COLORS.get(axis, QColor('#fff')), 2)
            painter.setPen(pen)
            painter.drawPath(path)

            # 数据点
            for p in points:
                painter.setBrush(QBrush(self.AXIS_LINE_COLORS.get(axis, QColor('#fff'))))
                painter.drawEllipse(p, 3, 3)

        # 图例
        legend_x = 10
        legend_y = h - 70
        for axis, color in self.AXIS_LINE_COLORS.items():
            painter.fillRect(QRectF(legend_x, legend_y, 12, 12), QBrush(color))
            painter.setPen(QColor('#aaa'))
            font = QFont('Segoe UI', 9)
            painter.setFont(font)
            painter.drawText(legend_x + 18, legend_y + 11, axis)
            legend_y += 18

        # 选中高亮
        if self._selected_band:
            idx = self.BAND_LABELS.index(self._selected_band)
            angle = 2 * math.pi * idx / n - math.pi / 2
            x = center.x() + (radius + 15) * math.cos(angle)
            y = center.y() + (radius + 15) * math.sin(angle)
            painter.setPen(QPen(QColor('#FFD700'), 2))
            painter.drawEllipse(QPointF(x, y), 15, 15)