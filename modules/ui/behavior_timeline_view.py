#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行为时间轴视图 — Phase 2
以时间轴形式展示驾驶全过程：车速曲线、行为标注带、风险指数、事件列表
"""

import logging
import time
from collections import deque
from typing import Dict, Any, Optional, List

import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QFrame, QTableWidget, QTableWidgetItem,
                               QHeaderView, QSplitter, QPushButton)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPen, QBrush, QPainter

import pyqtgraph as pg
from pyqtgraph import PlotWidget

from core.core.analysis.core_types import (
    DrivingState, RiskLevel, BehaviorCategory, BEHAVIOR_LABELS_CN,
    ManeuverEvent, FrameResult
)


RISK_COLORS_PG = {
    RiskLevel.SAFE: (39, 174, 96),
    RiskLevel.CAUTION: (241, 196, 15),
    RiskLevel.WARNING: (230, 126, 34),
    RiskLevel.DANGER: (231, 76, 60),
}

RISK_COLORS_HEX = {
    RiskLevel.SAFE: "#27ae60",
    RiskLevel.CAUTION: "#f1c40f",
    RiskLevel.WARNING: "#e67e22",
    RiskLevel.DANGER: "#e74c3c",
}

RISK_LABELS_CN = {
    RiskLevel.SAFE: "安全",
    RiskLevel.CAUTION: "注意",
    RiskLevel.WARNING: "警告",
    RiskLevel.DANGER: "危险",
}


class TimelinePlotWidget(QWidget):
    """时间轴图表容器 — 包含车速曲线、行为标注带、风险指数"""

    MAX_POINTS = 600

    def __init__(self, parent=None):
        super().__init__(parent)
        self._speed_data = deque(maxlen=self.MAX_POINTS)
        self._risk_data = deque(maxlen=self.MAX_POINTS)
        self._event_regions = []
        self._start_time = None
        self._last_timestamp = 0.0

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        pg.setConfigOptions(antialias=True)

        self.speed_plot = PlotWidget()
        self.speed_plot.setBackground('w')
        self.speed_plot.setLabel('left', '车速', units='km/h')
        self.speed_plot.showGrid(x=True, y=True, alpha=0.2)
        self.speed_curve = self.speed_plot.plot(pen=pg.mkPen(color=(41, 128, 185), width=2))
        layout.addWidget(self.speed_plot)

        self.behavior_plot = PlotWidget()
        self.behavior_plot.setBackground('w')
        self.behavior_plot.setLabel('left', '行为')
        self.behavior_plot.showGrid(x=True, y=True, alpha=0.2)
        self.behavior_plot.getAxis('left').setTicks([])
        self.behavior_plot.setYRange(0, 1)
        layout.addWidget(self.behavior_plot)

        self.risk_plot = PlotWidget()
        self.risk_plot.setBackground('w')
        self.risk_plot.setLabel('left', '风险指数')
        self.risk_plot.setLabel('bottom', '时间', units='s')
        self.risk_plot.showGrid(x=True, y=True, alpha=0.2)
        self.risk_plot.setYRange(0, 100)
        self.risk_curve = self.risk_plot.plot(pen=pg.mkPen(color=(231, 76, 60), width=2))
        layout.addWidget(self.risk_plot)

        self.speed_plot.setXLink(self.risk_plot)
        self.behavior_plot.setXLink(self.risk_plot)

    def add_data_point(self, timestamp: float, speed: float, risk_score: float,
                       state: DrivingState = None, event: ManeuverEvent = None):
        if timestamp <= self._last_timestamp:
            return
        self._last_timestamp = timestamp

        if self._start_time is None:
            self._start_time = timestamp

        rel_time = timestamp - self._start_time
        self._speed_data.append((rel_time, speed))
        self._risk_data.append((rel_time, risk_score))

        if len(self._speed_data) > 1:
            sx = [p[0] for p in self._speed_data]
            sy = [p[1] for p in self._speed_data]
            self.speed_curve.setData(sx, sy)

        if len(self._risk_data) > 1:
            rx = [p[0] for p in self._risk_data]
            ry = [p[1] for p in self._risk_data]
            self.risk_curve.setData(rx, ry)

        if event:
            self._add_event_region(event)

    def _add_event_region(self, event: ManeuverEvent):
        if self._start_time is None:
            return
        rel_start = event.start_time - self._start_time
        rel_end = event.end_time - self._start_time
        if rel_end <= rel_start:
            rel_end = rel_start + 0.5

        color = RISK_COLORS_PG.get(event.risk_level, (149, 165, 166))

        for plot in [self.speed_plot, self.behavior_plot, self.risk_plot]:
            region = pg.LinearRegionItem(
                values=(rel_start, rel_end),
                orientation='vertical',
                brush=pg.mkBrush(color[0], color[1], color[2], 40),
                pen=pg.mkPen(color[0], color[1], color[2], 80),
                movable=False,
            )
            plot.addItem(region)
            self._event_regions.append(region)

        label_item = pg.TextItem(
            text=event.label_cn,
            color=(color[0], color[1], color[2]),
            anchor=(0.5, 0),
        )
        font = QFont("Microsoft YaHei", 8)
        label_item.setFont(font)
        self.behavior_plot.addItem(label_item)
        label_item.setPos((rel_start + rel_end) / 2, 0.5)

    def clear(self):
        self._speed_data.clear()
        self._risk_data.clear()
        self._start_time = None
        self._last_timestamp = 0.0
        self.speed_curve.clear()
        self.risk_curve.clear()
        for region in self._event_regions:
            for plot in [self.speed_plot, self.behavior_plot, self.risk_plot]:
                try:
                    plot.removeItem(region)
                except Exception:
                    pass
        self._event_regions.clear()
        self.behavior_plot.clear()


class EventTable(QTableWidget):
    """事件列表表格"""

    event_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "时间", "行为类型", "分类", "持续时长", "置信度", "风险等级", "风险评分"
        ])
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setDefaultSectionSize(26)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self._events = []

    def add_event(self, event: ManeuverEvent):
        self._events.append(event)
        row = self.rowCount()
        self.insertRow(row)

        t = time.strftime('%H:%M:%S', time.localtime(event.end_time))
        ms = int((event.end_time - int(event.end_time)) * 1000)
        self.setItem(row, 0, QTableWidgetItem(f"{t}.{ms:03d}"))
        self.setItem(row, 1, QTableWidgetItem(event.label_cn))
        self.setItem(row, 2, QTableWidgetItem(event.category.value))
        self.setItem(row, 3, QTableWidgetItem(f"{event.duration:.2f}s"))
        self.setItem(row, 4, QTableWidgetItem(f"{event.confidence:.2f}"))

        risk_item = QTableWidgetItem(RISK_LABELS_CN.get(event.risk_level, "未知"))
        risk_color = QColor(RISK_COLORS_HEX.get(event.risk_level, "#95a5a6"))
        risk_item.setForeground(risk_color)
        self.setItem(row, 5, risk_item)

        score_item = QTableWidgetItem(f"{event.risk_score:.1f}")
        self.setItem(row, 6, score_item)

        if event.risk_level in (RiskLevel.WARNING, RiskLevel.DANGER):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QColor(255, 235, 238))

        self.scrollToBottom()

    def clear_events(self):
        self._events.clear()
        self.setRowCount(0)


class BehaviorTimelineView(QWidget):
    """行为时间轴视图"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None

        self._events = deque(maxlen=200)
        self._speed_history = deque(maxlen=600)
        self._risk_history = deque(maxlen=600)

        self._init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.clear_btn = QPushButton("清空时间轴")
        self.clear_btn.setMinimumHeight(28)
        self.clear_btn.clicked.connect(self._clear_timeline)
        toolbar.addWidget(self.clear_btn)

        self.export_btn = QPushButton("导出事件")
        self.export_btn.setMinimumHeight(28)
        self.export_btn.clicked.connect(self._export_events)
        toolbar.addWidget(self.export_btn)

        toolbar.addStretch()

        self.event_count_label = QLabel("事件: 0")
        self.event_count_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 12px; }")
        toolbar.addWidget(self.event_count_label)

        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        self.timeline_plot = TimelinePlotWidget()
        splitter.addWidget(self.timeline_plot)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        table_card = QGroupBox("事件列表")
        table_card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 4, 8, 8)
        self.event_table = EventTable()
        self.event_table.setMinimumHeight(100)
        table_layout.addWidget(self.event_table)
        bottom_layout.addWidget(table_card)

        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def update_frame_result(self, result):
        if result is None:
            return

        raw = result.raw_data or {}
        speed_ms = float(raw.get('speed', raw.get('车速', 0.0)) or 0.0)
        speed_kmh = speed_ms * 3.6
        timestamp = result.timestamp

        risk_score = 0.0
        if result.event:
            risk_score = result.event.risk_score

        self.timeline_plot.add_data_point(
            timestamp=timestamp,
            speed=speed_kmh,
            risk_score=risk_score,
            state=result.state,
            event=result.event,
        )

        if result.event:
            self._events.append(result.event)
            self.event_table.add_event(result.event)
            self.event_count_label.setText(f"事件: {len(self._events)}")

    def _clear_timeline(self):
        self._events.clear()
        self.timeline_plot.clear()
        self.event_table.clear_events()
        self.event_count_label.setText("事件: 0")

    def sync_from_distributor(self):
        """从 EventDistributor 同步 22 种 DrivingEventDetector 事件到时间轴"""
        try:
            from core.core.analysis.event_distributor import EventDistributor
            distributor = EventDistributor.instance()
            distributor_events = distributor.get_events()

            if not distributor_events:
                self.logger.debug("[BehaviorTimeline] EventDistributor 无事件，跳过同步")
                return

            # 清除旧的流式状态机事件，替换为22种精确事件
            self._clear_timeline()
            for event in distributor_events:
                self._events.append(event)
                self.event_table.add_event(event)
                self.timeline_plot.add_data_point(
                    timestamp=event.end_time if hasattr(event, 'end_time') else 0,
                    speed=0,
                    risk_score=getattr(event, 'risk_score', 0),
                    state='',
                    event=event,
                )
            self.event_count_label.setText(f"事件: {len(self._events)}")
            self.logger.info(
                f"[BehaviorTimeline] 从 EventDistributor 同步了 {len(distributor_events)} 个事件 "
                f"(22种 DrivingEventDetector)"
            )
        except Exception as e:
            self.logger.error(f"[BehaviorTimeline] 从 EventDistributor 同步失败: {e}")

    def _export_events(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import csv
        import os

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出事件数据", "events_export.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "行为类型", "分类", "持续时长(s)", "置信度",
                                 "风险等级", "风险评分", "峰值ax", "峰值ay", "峰值jerk"])
                for event in self._events:
                    t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.end_time))
                    ms = int((event.end_time - int(event.end_time)) * 1000)
                    t = f"{t}.{ms:03d}"
                    writer.writerow([
                        t, event.label_cn, event.category.value,
                        f"{event.duration:.2f}", f"{event.confidence:.2f}",
                        RISK_LABELS_CN.get(event.risk_level, "未知"),
                        f"{event.risk_score:.1f}",
                        f"{event.peak_ax:.3f}", f"{event.peak_ay:.3f}",
                        f"{event.peak_jerk:.3f}",
                    ])
            QMessageBox.information(self, "导出成功", f"事件数据已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def reset(self):
        self._clear_timeline()
