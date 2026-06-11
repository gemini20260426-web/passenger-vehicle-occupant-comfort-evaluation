#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
波形滚动显示组件 — 实时加速度波形 + 事件标记
═══════════════════════════════════════════════════════════
基于 pyqtgraph 实现：

功能:
  - 最近10s加速度波形 (Ax蓝/Ay红/Az绿)
  - 事件检测时自动画竖线标记
  - 点击竖线跳转到事件详情
  - 鼠标滚轮缩放时间轴
  - 右键菜单: 重置视图/导出截图
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
import time

import numpy as np

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QPushButton, QFrame, QMenu,
)
from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QAction

logger = logging.getLogger(__name__)

# 曲线颜色
COLOR_AX = (52, 152, 219)   # 蓝
COLOR_AY = (231, 76, 60)    # 红
COLOR_AZ = (46, 204, 113)   # 绿
COLOR_EVENT = (255, 215, 0)  # 金
COLOR_BG = (30, 30, 30)     # 深色背景
COLOR_GRID = (60, 60, 60)   # 网格线


class WaveformScrollWidget(QWidget):
    """pyqtgraph 波形滚动显示

    用法:
        widget = WaveformScrollWidget()
        widget.add_data(ax, ay, az, timestamp)
        widget.add_event(event_type, timestamp, confidence)
    """

    event_clicked = Signal(str, float, float)  # event_type, timestamp, confidence

    def __init__(self, parent=None, window_seconds: float = 10.0):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self._window_seconds = window_seconds
        self._max_samples = int(window_seconds * 100)  # 假设 100Hz

        # 数据缓冲
        self._timestamps: deque = deque(maxlen=self._max_samples)
        self._ax_data: deque = deque(maxlen=self._max_samples)
        self._ay_data: deque = deque(maxlen=self._max_samples)
        self._az_data: deque = deque(maxlen=self._max_samples)

        # 事件标记
        self._events: List[Tuple[str, float, float]] = []  # (type, ts, confidence)
        self._event_lines: List[pg.InfiniteLine] = []
        self._event_labels: List[pg.TextItem] = []

        # 显示控制
        self._show_ax = True
        self._show_ay = True
        self._show_az = True
        self._auto_scroll = True

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ——— 控制栏 ———
        ctrl_layout = QHBoxLayout()

        title = QLabel("加速度波形")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        title.setStyleSheet("color: #2F5496;")
        ctrl_layout.addWidget(title)

        self.cb_ax = QCheckBox("Ax")
        self.cb_ax.setChecked(True)
        self.cb_ax.setStyleSheet("color: #3498db; font-weight: bold;")
        self.cb_ax.toggled.connect(lambda v: self._toggle_channel('ax', v))
        ctrl_layout.addWidget(self.cb_ax)

        self.cb_ay = QCheckBox("Ay")
        self.cb_ay.setChecked(True)
        self.cb_ay.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.cb_ay.toggled.connect(lambda v: self._toggle_channel('ay', v))
        ctrl_layout.addWidget(self.cb_ay)

        self.cb_az = QCheckBox("Az")
        self.cb_az.setChecked(True)
        self.cb_az.setStyleSheet("color: #2ecc71; font-weight: bold;")
        self.cb_az.toggled.connect(lambda v: self._toggle_channel('az', v))
        ctrl_layout.addWidget(self.cb_az)

        ctrl_layout.addStretch()

        self.cb_auto = QCheckBox("自动滚动")
        self.cb_auto.setChecked(True)
        self.cb_auto.toggled.connect(lambda v: setattr(self, '_auto_scroll', v))
        ctrl_layout.addWidget(self.cb_auto)

        btn_reset = QPushButton("重置")
        btn_reset.setMaximumWidth(50)
        btn_reset.clicked.connect(self.reset_view)
        ctrl_layout.addWidget(btn_reset)

        layout.addLayout(ctrl_layout)

        # ——— 波形图 ———
        if not HAS_PYQTGRAPH:
            self._plot_widget = QLabel("pyqtgraph 未安装\n请运行: pip install pyqtgraph")
            self._plot_widget.setAlignment(Qt.AlignCenter)
            self._plot_widget.setStyleSheet("color: #e74c3c; font-size: 14px;")
            layout.addWidget(self._plot_widget)
            return

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground(QColor(*COLOR_BG))
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.setLabel('left', '加速度', units='m/s²')
        self._plot_widget.setLabel('bottom', '时间', units='s')
        self._plot_widget.getAxis('left').setPen(QColor(200, 200, 200))
        self._plot_widget.getAxis('bottom').setPen(QColor(200, 200, 200))

        # 禁用默认右键菜单，使用自定义菜单
        self._plot_widget.scene().contextMenu = [self._context_menu]

        # 曲线
        self._curve_ax = self._plot_widget.plot(pen=pg.mkPen(QColor(*COLOR_AX), width=2), name='Ax')
        self._curve_ay = self._plot_widget.plot(pen=pg.mkPen(QColor(*COLOR_AY), width=2), name='Ay')
        self._curve_az = self._plot_widget.plot(pen=pg.mkPen(QColor(*COLOR_AZ), width=2), name='Az')

        # 安装事件过滤器处理点击
        self._plot_widget.scene().sigMouseClicked.connect(self._on_plot_clicked)

        layout.addWidget(self._plot_widget)

        # ——— 图例 ———
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(self._legend_label("Ax (纵向)", "#3498db"))
        legend_layout.addWidget(self._legend_label("Ay (侧向)", "#e74c3c"))
        legend_layout.addWidget(self._legend_label("Az (垂向)", "#2ecc71"))
        legend_layout.addWidget(self._legend_label("│ 事件", "#f39c12"))
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

    def _legend_label(self, text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-size: 10px; padding: 0 8px;")
        return label

    def _context_menu(self, event):
        menu = QMenu(self)
        reset_action = QAction("重置视图", self)
        reset_action.triggered.connect(self.reset_view)
        menu.addAction(reset_action)

        export_action = QAction("导出截图", self)
        export_action.triggered.connect(self._export_screenshot)
        menu.addAction(export_action)

        menu.addSeparator()

        for ts, etype, conf in self._events[-20:]:
            label = f"{etype} ({conf:.0%}) @ {ts:.1f}s"
            action = QAction(label, self)
            action.triggered.connect(lambda checked, t=ts, e=etype, c=conf: self.event_clicked.emit(e, t, c))
            menu.addAction(action)

        menu.exec(event.screenPos())

    def add_data(self, ax: float, ay: float, az: float, timestamp: float):
        """添加一帧数据"""
        if not HAS_PYQTGRAPH:
            return

        self._timestamps.append(timestamp)
        self._ax_data.append(ax)
        self._ay_data.append(ay)
        self._az_data.append(az)

        if len(self._timestamps) > 1:
            ts = np.array(self._timestamps)
            if self._show_ax:
                self._curve_ax.setData(ts, np.array(self._ax_data))
            if self._show_ay:
                self._curve_ay.setData(ts, np.array(self._ay_data))
            if self._show_az:
                self._curve_az.setData(ts, np.array(self._az_data))

            # 自动调整 Y轴范围: 排除极端离群点，使用 P1-P99 百分位
            all_vals = []
            if self._show_ax and len(self._ax_data) > 10:
                all_vals.extend(self._ax_data)
            if self._show_ay and len(self._ay_data) > 10:
                all_vals.extend(self._ay_data)
            if self._show_az and len(self._az_data) > 10:
                all_vals.extend(self._az_data)
            if len(all_vals) > 10:
                all_arr = np.array(all_vals)
                y_lo = float(np.percentile(all_arr, 1))
                y_hi = float(np.percentile(all_arr, 99))
                y_pad = max(0.1, (y_hi - y_lo) * 0.15)
                self._plot_widget.setYRange(y_lo - y_pad, y_hi + y_pad, padding=0)

            if self._auto_scroll and len(ts) > 1:
                self._plot_widget.setXRange(
                    ts[-1] - self._window_seconds, ts[-1] + 0.5,
                    padding=0
                )

    def add_event(self, event_type: str, timestamp: float, confidence: float):
        """添加事件标记竖线"""
        if not HAS_PYQTGRAPH:
            return

        self._events.append((event_type, timestamp, confidence))

        # 限制事件数量
        if len(self._events) > 100:
            self._events = self._events[-100:]

        # 画竖线
        line = pg.InfiniteLine(
            pos=timestamp,
            angle=90,
            pen=pg.mkPen(QColor(*COLOR_EVENT), width=2, style=Qt.DashLine),
        )
        self._plot_widget.addItem(line)
        self._event_lines.append(line)

        # 添加标签
        label = pg.TextItem(
            text=event_type[:6],
            color=QColor(*COLOR_EVENT),
            anchor=(0.5, 0),
        )
        label.setPos(timestamp, 0)
        self._plot_widget.addItem(label)
        self._event_labels.append(label)

        # 清理过期的事件标记
        cutoff = timestamp - self._window_seconds * 2
        while self._event_lines and self._events[0][1] < cutoff:
            self._plot_widget.removeItem(self._event_lines.pop(0))
            self._plot_widget.removeItem(self._event_labels.pop(0))
            self._events.pop(0)

    def _on_plot_clicked(self, event):
        """点击事件标记跳转到事件详情"""
        if not HAS_PYQTGRAPH:
            return
        if event.button() != Qt.LeftButton:
            return

        pos = self._plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
        click_ts = pos.x()

        # 找到最近的事件
        closest = None
        min_dist = 0.5  # 0.5s 以内
        for etype, ts, conf in self._events:
            dist = abs(ts - click_ts)
            if dist < min_dist:
                min_dist = dist
                closest = (etype, ts, conf)

        if closest:
            self.event_clicked.emit(*closest)

    def _toggle_channel(self, channel: str, visible: bool):
        if channel == 'ax':
            self._show_ax = visible
            self._curve_ax.setVisible(visible)
        elif channel == 'ay':
            self._show_ay = visible
            self._curve_ay.setVisible(visible)
        elif channel == 'az':
            self._show_az = visible
            self._curve_az.setVisible(visible)

    def reset_view(self):
        """重置视图"""
        if not HAS_PYQTGRAPH:
            return
        if self._timestamps:
            self._plot_widget.autoRange()
            if self._auto_scroll and len(self._timestamps) > 1:
                ts = list(self._timestamps)
                self._plot_widget.setXRange(ts[-1] - self._window_seconds, ts[-1] + 0.5)

    def _export_screenshot(self):
        """导出截图"""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出波形截图", "", "PNG Files (*.png);;All Files (*)"
        )
        if path:
            grab = self._plot_widget.grab()
            grab.save(path)
            self.logger.info(f"波形截图已保存: {path}")

    def clear(self):
        """清除所有数据"""
        self._timestamps.clear()
        self._ax_data.clear()
        self._ay_data.clear()
        self._az_data.clear()

        if HAS_PYQTGRAPH:
            self._curve_ax.clear()
            self._curve_ay.clear()
            self._curve_az.clear()

            for line in self._event_lines:
                self._plot_widget.removeItem(line)
            self._event_lines.clear()

            for label in self._event_labels:
                self._plot_widget.removeItem(label)
            self._event_labels.clear()

        self._events.clear()

    def set_data_bridge(self, data_bridge):
        """连接 DataBridge 实时数据"""
        self._data_bridge = data_bridge
        if data_bridge:
            try:
                data_bridge.frame_result_ready.connect(self._on_frame_ready)
                data_bridge.behavior_event_ready.connect(self._on_event_detected)
                self.logger.info("波形滚动组件已连接 DataBridge (frame_result_ready + behavior_event_ready)")
            except Exception as e:
                self.logger.error(f"连接 DataBridge 失败: {e}", exc_info=True)

    def _on_frame_ready(self, frame_data):
        """处理实时帧数据"""
        try:
            ax = getattr(frame_data, 'ax', 0.0) or 0.0
            ay = getattr(frame_data, 'ay', 0.0) or 0.0
            az = getattr(frame_data, 'az', 0.0) or 0.0
            ts = getattr(frame_data, 'timestamp', time.time()) or time.time()
            self.add_data(float(ax), float(ay), float(az), float(ts))
        except Exception as e:
            self.logger.warning(f"处理帧数据失败: {e}", exc_info=True)

    def _on_event_detected(self, event):
        """处理检测到的事件"""
        try:
            etype = str(getattr(event, 'event_type', getattr(event, 'type', '??')))
            ts = float(getattr(event, 'timestamp', 0))
            conf = float(getattr(event, 'confidence', 0))
            self.add_event(etype, ts, conf)
        except Exception as e:
            self.logger.warning(f"处理事件数据失败: {e}", exc_info=True)