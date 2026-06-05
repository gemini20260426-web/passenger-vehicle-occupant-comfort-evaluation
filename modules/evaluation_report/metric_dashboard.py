#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标仪表盘 Widget (U1: Metric Dashboard)

仿照 Grafana Dashboard 风格:
- 三轴RMS/VDV/Peak趋势线
- 频段衰减柱状图
- 风险等级指示灯
- 实时指标数值显示
"""

import logging
from typing import Dict, List, Any, Optional
from collections import deque
import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QGroupBox, QFrame, QSizePolicy, QScrollArea)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QLinearGradient,
                           QPainterPath, QFontMetrics)

logger = logging.getLogger(__name__)


class TrendMiniChart(QWidget):
    """迷你趋势图 (单指标)"""

    def __init__(self, title: str, unit: str = '', color: QColor = None, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.color = color or QColor('#2196F3')
        self._values = deque(maxlen=60)
        self._threshold_warn: Optional[float] = None
        self._threshold_crit: Optional[float] = None
        self.setMinimumSize(150, 80)
        self.setMaximumHeight(100)

    def add_value(self, value: float):
        self._values.append(value)
        self.update()

    def set_thresholds(self, warn: float = None, crit: float = None):
        self._threshold_warn = warn
        self._threshold_crit = crit

    def paintEvent(self, event):
        if not self._values:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        margin = {'left': 40, 'right': 10, 'top': 20, 'bottom': 20}

        # 背景
        painter.fillRect(0, 0, w, h, QColor('#1a1a2e'))

        # 标题
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        painter.setPen(QColor('#aaa'))
        painter.drawText(5, 12, self.title)

        # 当前值
        current = self._values[-1]
        val_font = QFont('Segoe UI', 9, QFont.Bold)
        painter.setFont(val_font)
        if self._threshold_crit and abs(current) > self._threshold_crit:
            painter.setPen(QColor('#F44336'))
        elif self._threshold_warn and abs(current) > self._threshold_warn:
            painter.setPen(QColor('#FF9800'))
        else:
            painter.setPen(QColor('#4CAF50'))
        painter.drawText(5, 30, f"{current:.2f} {self.unit}")

        # 绘图区域
        plot_rect = QRectF(margin['left'], margin['top'],
                           w - margin['left'] - margin['right'],
                           h - margin['top'] - margin['bottom'])

        values = list(self._values)
        if len(values) < 2:
            return

        # 警告/临界线
        pen = QPen(QColor('#FF9800'), 1, Qt.DashLine)
        painter.setPen(pen)
        if self._threshold_warn:
            y = plot_rect.bottom() - (self._threshold_warn / max(abs(min(values)), abs(max(values)), 1)) * plot_rect.height()
            painter.drawLine(QPointF(plot_rect.left(), max(plot_rect.top(), y)),
                             QPointF(plot_rect.right(), max(plot_rect.top(), y)))

        pen = QPen(QColor('#F44336'), 1, Qt.DashLine)
        painter.setPen(pen)
        if self._threshold_crit:
            y = plot_rect.bottom() - (self._threshold_crit / max(abs(min(values)), abs(max(values)), 1)) * plot_rect.height()
            painter.drawLine(QPointF(plot_rect.left(), max(plot_rect.top(), y)),
                             QPointF(plot_rect.right(), max(plot_rect.top(), y)))

        # 折线
        max_val = max(abs(min(values)), abs(max(values)), 1)
        path = QPainterPath()
        x_step = plot_rect.width() / (len(values) - 1) if len(values) > 1 else 1

        for i, v in enumerate(values):
            x = plot_rect.left() + i * x_step
            y = plot_rect.bottom() - (v / max_val) * plot_rect.height()
            y = max(plot_rect.top(), min(plot_rect.bottom(), y))
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # 渐变填充
        fill_path = QPainterPath(path)
        fill_path.lineTo(plot_rect.right(), plot_rect.bottom())
        fill_path.lineTo(plot_rect.left(), plot_rect.bottom())
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, plot_rect.top(), 0, plot_rect.bottom())
        c = self.color
        gradient.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 60))
        gradient.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 10))
        painter.fillPath(fill_path, QBrush(gradient))

        pen = QPen(self.color, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)


class RiskIndicator(QWidget):
    """风险等级指示灯"""

    COLORS = {
        'normal': QColor('#4CAF50'),
        'low': QColor('#8BC34A'),
        'medium': QColor('#FF9800'),
        'high': QColor('#F44336'),
        'critical': QColor('#D32F2F'),
    }

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._level = 'normal'
        self.setFixedSize(120, 60)

    def set_level(self, level: str):
        self._level = level
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 标题
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        painter.setPen(QColor('#aaa'))
        painter.drawText(0, 12, self.title)

        # 指示灯
        color = self.COLORS.get(self._level, QColor('#4CAF50'))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(15, 20, 20, 20)

        # 外发光
        glow = QColor(color.red(), color.green(), color.blue(), 40)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(10, 15, 30, 30)

        # 等级文字
        level_names = {
            'normal': '正常', 'low': '注意', 'medium': '警告',
            'high': '危险', 'critical': '严重'
        }
        font = QFont('Segoe UI', 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(45, 35, level_names.get(self._level, self._level))


class MetricDashboard(QWidget):
    """指标仪表盘 (U1)

    仿照 Grafana Dashboard 布局:
    - 顶部: 风险指示灯行
    - 中部: 6个迷你趋势图 (三轴RMS + 三轴VDV)
    - 底部: 频段衰减柱状图
    """

    METRIC_GROUPS = {
        'rms': {
            'Ax': {'id': 'RMS_Ax_E', 'title': 'RMS Ax', 'unit': 'g', 'color': QColor('#2196F3'),
                   'warn': 3.0, 'crit': 8.0},
            'Ay': {'id': 'RMS_Ay_E', 'title': 'RMS Ay', 'unit': 'g', 'color': QColor('#4CAF50'),
                   'warn': 3.0, 'crit': 6.0},
            'Az': {'id': 'RMS_Az_E', 'title': 'RMS Az', 'unit': 'g', 'color': QColor('#FF9800'),
                   'warn': 2.0, 'crit': 5.0},
        },
        'vdv': {
            'Ax': {'id': 'VDV_Ax_E', 'title': 'VDV Ax', 'unit': 'm/s^1.75', 'color': QColor('#9C27B0'),
                   'warn': 15.0, 'crit': 30.0},
            'Ay': {'id': 'VDV_Ay_E', 'title': 'VDV Ay', 'unit': 'm/s^1.75', 'color': QColor('#00BCD4'),
                   'warn': 12.0, 'crit': 25.0},
            'Az': {'id': 'VDV_Az_E', 'title': 'VDV Az', 'unit': 'm/s^1.75', 'color': QColor('#FF5722'),
                   'warn': 18.0, 'crit': 35.0},
        }
    }

    def __init__(self, metric_store=None, parent=None):
        super().__init__(parent)
        self.metric_store = metric_store
        self._trend_charts: Dict[str, TrendMiniChart] = {}
        self._risk_indicators: Dict[str, RiskIndicator] = {}
        self._current_values: Dict[str, float] = {}
        self._init_ui()

        # 订阅MetricStore
        if self.metric_store:
            all_ids = []
            for group in self.METRIC_GROUPS.values():
                for cfg in group.values():
                    all_ids.append(cfg['id'])
            self.metric_store.subscribe('dashboard', all_ids)
            self.metric_store.metric_updated.connect(self._on_metric_updated)

        # 刷新定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_timer.start(1000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("指标仪表盘")
        title_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        title_label.setStyleSheet("color: #e0e0e0;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 风险指示灯行
        risk_group = QGroupBox("系统状态")
        risk_group.setStyleSheet("""
            QGroupBox { color: #aaa; border: 1px solid #333; border-radius: 4px; 
                       margin-top: 8px; padding-top: 12px; background: #1a1a2e; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        risk_layout = QHBoxLayout()
        for key in ['overall', 'vibration', 'impact', 'fatigue', 'attenuation']:
            indicator = RiskIndicator({'overall': '综合', 'vibration': '振动', 'impact': '冲击',
                                       'fatigue': '疲劳', 'attenuation': '衰减'}.get(key, key))
            self._risk_indicators[key] = indicator
            risk_layout.addWidget(indicator)
        risk_layout.addStretch()
        risk_group.setLayout(risk_layout)
        main_layout.addWidget(risk_group)

        # RMS趋势图行
        rms_group = QGroupBox("加速度RMS (三轴)")
        rms_group.setStyleSheet("""
            QGroupBox { color: #aaa; border: 1px solid #333; border-radius: 4px; 
                       margin-top: 8px; padding-top: 12px; background: #1a1a2e; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        rms_layout = QHBoxLayout()
        for axis, cfg in self.METRIC_GROUPS['rms'].items():
            chart = TrendMiniChart(cfg['title'], cfg['unit'], cfg['color'])
            chart.set_thresholds(cfg['warn'], cfg['crit'])
            self._trend_charts[cfg['id']] = chart
            rms_layout.addWidget(chart)
        rms_group.setLayout(rms_layout)
        main_layout.addWidget(rms_group)

        # VDV趋势图行
        vdv_group = QGroupBox("振动剂量值 VDV (三轴)")
        vdv_group.setStyleSheet("""
            QGroupBox { color: #aaa; border: 1px solid #333; border-radius: 4px; 
                       margin-top: 8px; padding-top: 12px; background: #1a1a2e; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        vdv_layout = QHBoxLayout()
        for axis, cfg in self.METRIC_GROUPS['vdv'].items():
            chart = TrendMiniChart(cfg['title'], cfg['unit'], cfg['color'])
            chart.set_thresholds(cfg['warn'], cfg['crit'])
            self._trend_charts[cfg['id']] = chart
            vdv_layout.addWidget(chart)
        vdv_group.setLayout(vdv_layout)
        main_layout.addWidget(vdv_group)

        # 频段衰减柱状图占位
        band_group = QGroupBox("频段衰减率")
        band_group.setStyleSheet("""
            QGroupBox { color: #aaa; border: 1px solid #333; border-radius: 4px; 
                       margin-top: 8px; padding-top: 12px; background: #1a1a2e; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        band_layout = QHBoxLayout()
        self.band_bars: Dict[str, QFrame] = {}
        for band in ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']:
            bar_container = QVBoxLayout()
            label = QLabel(band)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #aaa; font-size: 8px;")
            bar = QFrame()
            bar.setFixedWidth(40)
            bar.setMinimumHeight(10)
            bar.setStyleSheet("background: #2196F3; border-radius: 2px;")
            self.band_bars[band] = bar
            bar_container.addWidget(bar)
            bar_container.addWidget(label)
            band_layout.addLayout(bar_container)
        band_layout.addStretch()
        band_group.setLayout(band_layout)
        main_layout.addWidget(band_group)

        main_layout.addStretch()
        self.setStyleSheet("background: #16213e;")

    def update_metric(self, metric_id: str, value: float):
        """更新单个指标值"""
        self._current_values[metric_id] = value
        if metric_id in self._trend_charts:
            self._trend_charts[metric_id].add_value(value)

    def update_batch(self, metrics: Dict[str, float]):
        """批量更新指标"""
        for mid, val in metrics.items():
            self.update_metric(mid, val)

    def _on_metric_updated(self, metric_id: str, data: dict):
        """MetricStore回调"""
        self.update_metric(metric_id, data.get('value', 0.0))

    def _refresh_display(self):
        """定时刷新显示"""
        self._update_risk_levels()

    def _update_risk_levels(self):
        """更新风险等级"""
        # 综合评估
        rms_values = [self._current_values.get(cfg['id'], 0)
                      for cfg in self.METRIC_GROUPS['rms'].values()]
        vdv_values = [self._current_values.get(cfg['id'], 0)
                      for cfg in self.METRIC_GROUPS['vdv'].values()]

        def _assess(values, warn_factor=1.0):
            if not values:
                return 'normal'
            max_val = max(abs(v) for v in values)
            if max_val > 8.0 * warn_factor:
                return 'critical'
            elif max_val > 5.0 * warn_factor:
                return 'high'
            elif max_val > 3.0 * warn_factor:
                return 'medium'
            elif max_val > 1.0 * warn_factor:
                return 'low'
            return 'normal'

        self._risk_indicators.get('vibration', None) and \
            self._risk_indicators['vibration'].set_level(_assess(rms_values, 1.0))
        self._risk_indicators.get('impact', None) and \
            self._risk_indicators['impact'].set_level(_assess(vdv_values, 0.5))

        # 综合
        all_levels = [_assess(rms_values, 1.0), _assess(vdv_values, 0.5)]
        severity_order = ['normal', 'low', 'medium', 'high', 'critical']
        overall = max(all_levels, key=lambda x: severity_order.index(x))
        if 'overall' in self._risk_indicators:
            self._risk_indicators['overall'].set_level(overall)

    def update_band_attenuation(self, band_data: Dict[str, float]):
        """更新频段衰减柱状图"""
        for band_name, pct in band_data.items():
            if band_name in self.band_bars:
                bar = self.band_bars[band_name]
                h = max(10, min(80, abs(pct) * 1.5))
                bar.setFixedHeight(int(h))
                if pct > 20:
                    bar.setStyleSheet("background: #4CAF50; border-radius: 2px;")
                elif pct > 0:
                    bar.setStyleSheet("background: #FF9800; border-radius: 2px;")
                else:
                    bar.setStyleSheet("background: #F44336; border-radius: 2px;")