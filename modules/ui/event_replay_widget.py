#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件回放模式 — 拖动时间轴回放历史事件
═══════════════════════════════════════════════════════════════
功能:
  - 底部时间轴 (标注事件位置)
  - 拖动滑块回放任意时间点
  - 显示回放时的仪表盘 + 事件检测结果
  - 支持 1x/2x/4x 回放速度
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QSlider, QComboBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QGridLayout, QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class EventReplayWidget(QWidget):
    """事件回放模式

    用法:
        widget = EventReplayWidget()
        widget.load_events(events_list)
        widget.load_frames(frames_list)
        widget.start_replay()
    """

    event_highlighted = Signal(dict)     # 事件高亮
    replay_position = Signal(float)      # 回放位置 (秒)
    replay_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self._events: List[Dict] = []
        self._frames: List[Dict] = []
        self._current_pos = 0.0
        self._is_playing = False
        self._speed = 1.0
        self._duration = 0.0
        self._frame_index = 0

        # 定时器控制回放
        self._replay_timer = QTimer(self)
        self._replay_timer.timeout.connect(self._step_replay)
        self._replay_timer.setInterval(100)  # 100ms per step

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ——— 顶栏 ———
        title = QLabel("事件回放")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #2F5496;")
        layout.addWidget(title)

        # ——— 回放控制 ———
        ctrl_group = QGroupBox("🎮 回放控制")
        ctrl_layout = QHBoxLayout(ctrl_group)

        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setStyleSheet(
            "QPushButton { background: #27ae60; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 3px; } "
            "QPushButton:hover { background: #219a52; }"
        )
        ctrl_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.clicked.connect(self.stop)
        ctrl_layout.addWidget(self.btn_stop)

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setMaximumWidth(40)
        self.btn_prev.clicked.connect(self._prev_event)
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setMaximumWidth(40)
        self.btn_next.clicked.connect(self._next_event)
        ctrl_layout.addWidget(self.btn_next)

        ctrl_layout.addWidget(QLabel("速度:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "4x", "8x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        ctrl_layout.addWidget(self.speed_combo)

        ctrl_layout.addStretch()

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont("Consolas", 12))
        self.time_label.setStyleSheet("color: #333; font-weight: bold;")
        ctrl_layout.addWidget(self.time_label)

        layout.addWidget(ctrl_group)

        # ——— 时间轴 ———
        timeline_group = QGroupBox("⏱ 时间轴")
        timeline_layout = QVBoxLayout(timeline_group)

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        self.timeline_slider.sliderReleased.connect(self._on_slider_released)
        timeline_layout.addWidget(self.timeline_slider)

        # 事件标记行
        self.event_marker_label = QLabel("")
        self.event_marker_label.setMaximumHeight(20)
        self.event_marker_label.setStyleSheet("font-size: 9px; color: #666;")
        timeline_layout.addWidget(self.event_marker_label)

        layout.addWidget(timeline_group)

        # ——— 事件列表 ———
        event_group = QGroupBox("📋 事件列表")
        event_layout = QVBoxLayout(event_group)

        self.event_table = QTableWidget(0, 5)
        self.event_table.setHorizontalHeaderLabels([
            "时间", "类型", "置信度", "来源", "回放"
        ])
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.event_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.event_table.setMaximumHeight(200)
        self.event_table.cellClicked.connect(self._on_event_clicked)
        event_layout.addWidget(self.event_table)

        layout.addWidget(event_group)

        # ——— 回放状态 ———
        self.status_label = QLabel("就绪 — 请加载事件数据")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        layout.addWidget(self.status_label)

    def load_events(self, events: List[Dict]):
        """加载事件列表
        events: [{'timestamp': float, 'type': str, 'confidence': float, 'source': str}, ...]
        """
        self._events = sorted(events, key=lambda e: e.get('timestamp', 0))
        if self._events:
            self._duration = self._events[-1]['timestamp']
        self._update_event_table()
        self._update_event_markers()
        self.status_label.setText(f"已加载 {len(self._events)} 个事件, 总时长: {self._duration:.1f}s")

    def load_frames(self, frames: List[Dict]):
        """加载帧数据"""
        self._frames = frames
        if frames:
            self._duration = max(self._duration, frames[-1].get('timestamp', 0))

    def toggle_play(self):
        """播放/暂停"""
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """开始播放"""
        if not self._events:
            self.status_label.setText("无事件数据，无法回放")
            return
        self._is_playing = True
        self.btn_play.setText("⏸ 暂停")
        self._replay_timer.start()
        self.status_label.setText(f"播放中... ({self._speed}x)")

    def pause(self):
        """暂停"""
        self._is_playing = False
        self.btn_play.setText("▶ 播放")
        self._replay_timer.stop()
        self.status_label.setText("已暂停")

    def stop(self):
        """停止"""
        self.pause()
        self._current_pos = 0.0
        self._frame_index = 0
        self.timeline_slider.setValue(0)
        self._update_time_label()
        self.status_label.setText("已停止")
        self.replay_finished.emit()

    def _step_replay(self):
        """回放步进"""
        if not self._events:
            self.stop()
            return

        self._current_pos += 0.1 * self._speed

        if self._current_pos >= self._duration:
            self.stop()
            return

        # 更新滑块
        slider_pos = int(self._current_pos / max(self._duration, 0.001) * 1000)
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(slider_pos)
        self.timeline_slider.blockSignals(False)

        self._update_time_label()
        self.replay_position.emit(self._current_pos)

        # 检查是否有事件
        self._check_events_at_position()

    def _check_events_at_position(self):
        """检查当前位置是否有事件"""
        for evt in self._events:
            ts = evt.get('timestamp', 0)
            if abs(ts - self._current_pos) < 0.15:
                self.event_highlighted.emit(evt)
                self.status_label.setText(
                    f"  {evt['type']} (置信度: {evt.get('confidence', 0)*100:.0f}%)"
                )

    def _on_slider_changed(self, value):
        """滑块拖动"""
        self._current_pos = value / 1000.0 * self._duration
        self._update_time_label()

    def _on_slider_released(self):
        """滑块松手"""
        self.replay_position.emit(self._current_pos)

    def _on_speed_changed(self, text):
        """速度改变"""
        self._speed = float(text.replace('x', ''))

    def _prev_event(self):
        """跳转到上一个事件"""
        if not self._events:
            return
        # 找到当前时间之前最近的事件
        prev = None
        for evt in reversed(self._events):
            if evt['timestamp'] < self._current_pos - 0.1:
                prev = evt
                break
        if prev is None and self._events:
            prev = self._events[0]

        if prev:
            self._current_pos = prev['timestamp']
            pos = int(self._current_pos / self._duration * 1000)
            self.timeline_slider.setValue(pos)
            self.replay_position.emit(self._current_pos)

    def _next_event(self):
        """跳转到下一个事件"""
        if not self._events:
            return
        for evt in self._events:
            if evt['timestamp'] > self._current_pos + 0.1:
                self._current_pos = evt['timestamp']
                pos = int(self._current_pos / self._duration * 1000)
                self.timeline_slider.setValue(pos)
                self.replay_position.emit(self._current_pos)
                return

    def _update_time_label(self):
        """更新时间标签"""
        def fmt(sec):
            m = int(sec // 60)
            s = sec % 60
            return f"{m:02d}:{s:04.1f}"
        self.time_label.setText(f"{fmt(self._current_pos)} / {fmt(self._duration)}")

    def _update_event_table(self):
        """更新事件表格"""
        self.event_table.setRowCount(0)
        for i, evt in enumerate(self._events):
            self.event_table.insertRow(i)
            self.event_table.setItem(i, 0, QTableWidgetItem(f"{evt.get('timestamp', 0):.1f}s"))
            self.event_table.setItem(i, 1, QTableWidgetItem(str(evt.get('type', '??'))))
            conf = evt.get('confidence', 0) * 100
            self.event_table.setItem(i, 2, QTableWidgetItem(f"{conf:.0f}%"))
            self.event_table.setItem(i, 3, QTableWidgetItem(str(evt.get('source', 'ML'))))

            btn = QPushButton("▶")
            btn.setMaximumWidth(30)
            btn.clicked.connect(lambda checked, ts=evt.get('timestamp', 0): self._jump_to(ts))
            self.event_table.setCellWidget(i, 4, btn)

    def _update_event_markers(self):
        """更新事件标记行"""
        if not self._events:
            return
        markers = []
        for evt in self._events:
            ts = evt.get('timestamp', 0)
            pct = ts / max(self._duration, 0.001)
            markers.append(f"│{evt.get('type', '?')[:4]}@{ts:.1f}s")
        self.event_marker_label.setText("  ".join(markers[:10]))

    def _on_event_clicked(self, row, col):
        """点击事件行"""
        if row < len(self._events):
            ts = self._events[row].get('timestamp', 0)
            self._jump_to(ts)

    def _jump_to(self, timestamp: float):
        """跳转到指定时间"""
        self._current_pos = timestamp
        pos = int(timestamp / max(self._duration, 0.001) * 1000)
        self.timeline_slider.setValue(pos)
        self.replay_position.emit(timestamp)
        self.status_label.setText(f"跳转到: {timestamp:.1f}s")

    def clear(self):
        """清除数据"""
        self.stop()
        self._events.clear()
        self._frames.clear()
        self._duration = 0.0
        self._current_pos = 0.0
        self.event_table.setRowCount(0)
        self.event_marker_label.setText("")
        self.status_label.setText("就绪 — 请加载事件数据")