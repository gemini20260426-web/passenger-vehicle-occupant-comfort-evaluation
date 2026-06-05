#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回放控制栏 UI 组件
提供播放/暂停、快进/快退、速度调节、进度条等回放控制
"""

import logging
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
                               QSlider, QComboBox, QFrame, QSizePolicy, QDoubleSpinBox,
                               QListWidget, QListWidgetItem, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QPainter, QColor, QPen

from core.core.analysis.clearable_registry import ClearableResource, ClearableRegistry

logger = logging.getLogger(__name__)

SPEED_OPTIONS = ['0.25x', '0.5x', '1x', '2x', '5x', '10x']
SPEED_VALUES = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]

REPLAY_MODE_OPTIONS = ['⚡ 快速', '🔄 重新分析']
REPLAY_MODE_VALUES = ['fast', 'reanalyze']

STYLE_CACHE_SELECTOR = """
    QComboBox {
        font-size: 9pt;
        padding: 2px 6px;
        border: 1px solid #74c0fc;
        border-radius: 4px;
        background: #e7f5ff;
        color: #1864ab;
        min-width: 240px;
    }
    QComboBox:hover {
        border-color: #339af0;
        background: #d0ebff;
    }
    QComboBox:disabled {
        background: #f1f3f5;
        color: #adb5bd;
        border-color: #e9ecef;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid #a5d8ff;
    }
    QComboBox QAbstractItemView {
        border: 1px solid #ced4da;
        background: #ffffff;
        selection-background-color: #e7f5ff;
        selection-color: #1971c2;
        font-size: 9pt;
    }
"""

STYLE_BAR = """
    ReplayControlBar {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #f8f9fa, stop:1 #e9ecef);
        border-bottom: 1px solid #dee2e6;
    }
"""

STYLE_BTN_CONTROL = """
    QPushButton {
        font-size: 11pt;
        border: 1px solid #ced4da;
        border-radius: 5px;
        background: #ffffff;
        color: #495057;
        min-width: 30px;
        min-height: 26px;
        padding: 2px 6px;
    }
    QPushButton:hover {
        background: #e2e6ea;
        border-color: #adb5bd;
    }
    QPushButton:pressed {
        background: #dae0e5;
    }
    QPushButton:disabled {
        background: #f1f3f5;
        color: #adb5bd;
        border-color: #e9ecef;
    }
"""

STYLE_BTN_PLAY = """
    QPushButton {
        font-size: 11pt;
        font-weight: bold;
        border: 1px solid #339af0;
        border-radius: 5px;
        background: #339af0;
        color: #ffffff;
        min-width: 36px;
        min-height: 26px;
        padding: 2px 8px;
    }
    QPushButton:hover {
        background: #228be6;
        border-color: #1c7ed6;
    }
    QPushButton:pressed {
        background: #1c7ed6;
    }
    QPushButton:disabled {
        background: #d0ebff;
        color: #74c0fc;
        border-color: #a5d8ff;
    }
"""

STYLE_SPEED = """
    QComboBox {
        font-size: 9pt;
        padding: 2px 6px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        background: #ffffff;
        color: #495057;
        min-width: 62px;
    }
    QComboBox:hover {
        border-color: #adb5bd;
    }
    QComboBox:disabled {
        background: #f1f3f5;
        color: #adb5bd;
        border-color: #e9ecef;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid #e9ecef;
    }
    QComboBox QAbstractItemView {
        border: 1px solid #ced4da;
        background: #ffffff;
        selection-background-color: #e7f5ff;
        selection-color: #1971c2;
    }
"""

STYLE_SLIDER = """
    QSlider::groove:horizontal {
        height: 5px;
        background: #dee2e6;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        width: 13px;
        height: 13px;
        margin: -4px 0;
        background: #339af0;
        border: 2px solid #ffffff;
        border-radius: 7px;
    }
    QSlider::handle:horizontal:hover {
        background: #228be6;
        width: 15px;
        height: 15px;
        margin: -5px 0;
        border-radius: 8px;
    }
    QSlider::sub-page:horizontal {
        background: #339af0;
        border-radius: 2px;
    }
    QSlider::handle:horizontal:disabled {
        background: #adb5bd;
    }
    QSlider::sub-page:horizontal:disabled {
        background: #ced4da;
    }
"""

STYLE_TIME = """
    QLabel {
        font-size: 9pt;
        color: #6c757d;
        font-family: 'Consolas', 'Courier New', monospace;
    }
"""

STYLE_STATUS = """
    QLabel {
        font-size: 8.5pt;
        color: #868e96;
        font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    }
"""

STYLE_SOURCE_INFO = """
    QLabel {
        font-size: 8pt;
        color: #495057;
        font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
        padding: 1px 8px;
        background: #e7f5ff;
        border: 1px solid #a5d8ff;
        border-radius: 3px;
    }
"""

STYLE_SOURCE_CHIP_SELECTED = """
    QPushButton {
        font-size: 8pt;
        color: #ffffff;
        font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
        padding: 2px 10px;
        background: #339af0;
        border: 1px solid #1c7ed6;
        border-radius: 10px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #228be6;
    }
"""

STYLE_SOURCE_CHIP_UNSELECTED = """
    QPushButton {
        font-size: 8pt;
        color: #868e96;
        font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
        padding: 2px 10px;
        background: #f1f3f5;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #e9ecef;
        color: #495057;
    }
"""

STYLE_SPIN = """
    QDoubleSpinBox {
        font-size: 9pt;
        padding: 2px 6px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        background: #ffffff;
        color: #495057;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    QDoubleSpinBox:hover {
        border-color: #adb5bd;
    }
    QDoubleSpinBox:focus {
        border-color: #339af0;
    }
    QDoubleSpinBox:disabled {
        background: #f1f3f5;
        color: #adb5bd;
        border-color: #e9ecef;
    }
"""

SOURCE_DISPLAY_MAP = {
    'imu_standalone': '独立IMU',
    'can_wide': 'CAN全量',
    'can_long': 'CAN长格式',
    'cnap_wave': 'CNAP波形',
    'cnap_beats': 'CNAP逐拍',
    'cnap': 'CNAP',
    'pipeline': 'Pipeline',
}


class SourceSelectorWidget(QWidget):
    """数据源芯片选择器 — 单击循环切换数据源"""

    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_types = []
        self._current_index = 0
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()

        self._chip = QPushButton()
        self._chip.setStyleSheet(STYLE_SOURCE_CHIP_SELECTED)
        self._chip.clicked.connect(self._on_chip_clicked)
        self._layout.insertWidget(self._layout.count() - 1, self._chip)

    def set_sources(self, source_types: list):
        self._source_types = source_types
        self._current_index = 0
        self._update_chip()
        self.setVisible(len(source_types) > 0)

    def _on_chip_clicked(self):
        if len(self._source_types) <= 1:
            return
        self._current_index = (self._current_index + 1) % len(self._source_types)
        self._update_chip()
        active = [self._source_types[self._current_index]]
        self.selection_changed.emit(active)

    def _update_chip(self):
        if not self._source_types:
            return
        st = self._source_types[self._current_index]
        display = SOURCE_DISPLAY_MAP.get(st, st)
        total = len(self._source_types)
        if total > 1:
            self._chip.setText(f'{display} ({self._current_index + 1}/{total})')
            self._chip.setToolTip(f'点击切换到下一个数据源 ({self._current_index + 1}/{total})')
            self._chip.setEnabled(True)
        else:
            self._chip.setText(display)
            self._chip.setToolTip(display)
            self._chip.setEnabled(False)

    def get_selected(self) -> list:
        if not self._source_types:
            return []
        return [self._source_types[self._current_index]]


class CheckableComboBox(QWidget):
    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._checked = set()
        self._popup = None
        self._list_widget = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._button = QPushButton('🎯 事件跳转...')
        self._button.setFixedHeight(24)
        self._button.setStyleSheet("""
            QPushButton {
                font-size: 10pt;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background: #ffffff;
                color: #495057;
                padding: 2px 8px;
                text-align: left;
            }
            QPushButton:hover {
                background: #e2e6ea;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background: #dae0e5;
            }
        """)
        self._button.clicked.connect(self._toggle_popup)
        layout.addWidget(self._button)

    def add_item(self, label: str, data):
        self._items.append((label, data))

    def clear_items(self):
        self._items.clear()
        self._checked.clear()
        self._button.setText('🎯 事件跳转...')
        self._close_popup()

    def set_items(self, items: list):
        self._items = list(items)
        self._checked.clear()
        self._update_button_text()

    def get_checked_data(self) -> list:
        return [self._items[i][1] for i in sorted(self._checked)]

    def _update_button_text(self):
        count = len(self._checked)
        total = len(self._items)
        if total == 0:
            self._button.setText('🎯 事件跳转...')
        elif count == 0:
            self._button.setText(f'🎯 事件跳转 ({total}个)')
        elif count == total:
            self._button.setText(f'☑ 全部事件 ({count})')
        else:
            self._button.setText(f'☑ 已选 {count}/{total} 个事件')

    def _toggle_popup(self):
        if self._popup and self._popup.isVisible():
            self._close_popup()
        else:
            self._show_popup()

    def _show_popup(self):
        self._close_popup()

        self._popup = QFrame(self.window(), Qt.Popup)
        self._popup.setFrameStyle(QFrame.Box | QFrame.Plain)
        self._popup.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #adb5bd;
                border-radius: 4px;
            }
        """)

        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        popup_layout.setSpacing(4)

        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                font-size: 10pt;
            }
            QListWidget::item {
                padding: 3px 6px;
            }
            QListWidget::item:hover {
                background: #e9ecef;
            }
        """)
        self._list_widget.itemChanged.connect(self._on_item_changed)

        for i, (label, data) in enumerate(self._items):
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if i in self._checked else Qt.Unchecked)
            item.setData(Qt.UserRole, i)
            self._list_widget.addItem(item)

        popup_layout.addWidget(self._list_widget)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        btn_all = QPushButton('全选')
        btn_all.setFixedHeight(22)
        btn_all.setStyleSheet("""
            QPushButton {
                font-size: 9pt;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background: #f8f9fa;
                padding: 2px 8px;
            }
            QPushButton:hover { background: #e2e6ea; }
        """)
        btn_all.clicked.connect(self._select_all)
        btn_row.addWidget(btn_all)

        btn_none = QPushButton('取消')
        btn_none.setFixedHeight(22)
        btn_none.setStyleSheet("""
            QPushButton {
                font-size: 9pt;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background: #f8f9fa;
                padding: 2px 8px;
            }
            QPushButton:hover { background: #e2e6ea; }
        """)
        btn_none.clicked.connect(self._select_none)
        btn_row.addWidget(btn_none)

        btn_row.addStretch()
        popup_layout.addLayout(btn_row)

        btn_pos = self._button.mapToGlobal(QPoint(0, self._button.height()))
        self._popup.move(btn_pos)
        self._popup.setMinimumWidth(max(220, self._button.width()))
        self._popup.setMaximumHeight(400)
        self._popup.show()

    def _close_popup(self):
        if self._popup:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None
            self._list_widget = None

    def _on_item_changed(self, item):
        idx = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._checked.add(idx)
        else:
            self._checked.discard(idx)
        self._update_button_text()
        self.selection_changed.emit(self.get_checked_data())

    def _select_all(self):
        if self._list_widget:
            self._list_widget.blockSignals(True)
            for i in range(self._list_widget.count()):
                self._list_widget.item(i).setCheckState(Qt.Checked)
                self._checked.add(i)
            self._list_widget.blockSignals(False)
            self._update_button_text()
            self.selection_changed.emit(self.get_checked_data())

    def _select_none(self):
        if self._list_widget:
            self._list_widget.blockSignals(True)
            for i in range(self._list_widget.count()):
                self._list_widget.item(i).setCheckState(Qt.Unchecked)
            self._checked.clear()
            self._list_widget.blockSignals(False)
            self._update_button_text()
            self.selection_changed.emit(self.get_checked_data())


class ReplayControlBar(QWidget, ClearableResource):
    """回放控制栏"""

    play_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()
    seek_forward_clicked = Signal()
    seek_backward_clicked = Signal()
    speed_changed = Signal(float)
    progress_seek = Signal(float)
    source_selection_changed = Signal(list)
    replay_mode_changed = Signal(str)
    time_range_changed = Signal(float, float)
    event_jump_requested = Signal(list)
    cache_selection_changed = Signal(str)  # 缓存选择变化，携带 cache_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing = False
        self._time_min = 0.0
        self._time_max = 0.0
        self.setObjectName('ReplayControlBar')
        self.setStyleSheet(STYLE_BAR)
        self._init_ui()
        self.set_status('正在解析数据...')
        self._set_controls_enabled(False)
        # 注册到统一清除中心
        ClearableRegistry.instance().register("回放控制栏", self)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(10, 5, 10, 5)
        bar.setSpacing(8)

        self.btn_backward = QPushButton('\u23EE')
        self.btn_backward.setToolTip('快退 5 秒')
        self.btn_backward.setFixedSize(30, 26)
        self.btn_backward.clicked.connect(self.seek_backward_clicked.emit)
        self.btn_backward.setStyleSheet(STYLE_BTN_CONTROL)

        # ── 缓存选择器 ──
        self._cache_combo = QComboBox()
        self._cache_combo.setToolTip('选择回放数据集')
        self._cache_combo.setStyleSheet(STYLE_CACHE_SELECTOR)
        self._cache_combo.setMinimumWidth(240)
        self._cache_combo.currentIndexChanged.connect(self._on_cache_selected)
        self._cache_combo.setEnabled(False)

        self.btn_play = QPushButton('\u25B6  播放')
        self.btn_play.setToolTip('播放 / 暂停')
        self.btn_play.setFixedHeight(26)
        self.btn_play.clicked.connect(self._on_play_clicked)
        self.btn_play.setStyleSheet(STYLE_BTN_PLAY)

        self.btn_stop = QPushButton('\u25A0')
        self.btn_stop.setToolTip('停止')
        self.btn_stop.setFixedSize(30, 26)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        self.btn_stop.setStyleSheet(STYLE_BTN_CONTROL)

        self.btn_forward = QPushButton('\u23ED')
        self.btn_forward.setToolTip('快进 5 秒')
        self.btn_forward.setFixedSize(30, 26)
        self.btn_forward.clicked.connect(self.seek_forward_clicked.emit)
        self.btn_forward.setStyleSheet(STYLE_BTN_CONTROL)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet('background: #dee2e6; max-width: 1px;')
        sep1.setFixedHeight(20)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(SPEED_OPTIONS)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setFixedWidth(64)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        self.speed_combo.setStyleSheet(STYLE_SPEED)

        self.replay_mode_combo = QComboBox()
        self.replay_mode_combo.addItems(REPLAY_MODE_OPTIONS)
        self.replay_mode_combo.setCurrentIndex(0)
        self.replay_mode_combo.setFixedWidth(110)
        self.replay_mode_combo.currentIndexChanged.connect(self._on_replay_mode_changed)
        self.replay_mode_combo.setStyleSheet(STYLE_SPEED)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet('background: #dee2e6; max-width: 1px;')
        sep2.setFixedHeight(20)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.setStyleSheet(STYLE_SLIDER)
        self.progress_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.time_label = QLabel('00:00 / 00:00')
        self.time_label.setStyleSheet(STYLE_TIME)
        self.time_label.setFixedWidth(120)
        self.time_label.setAlignment(Qt.AlignCenter)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet('background: #dee2e6; max-width: 1px;')
        sep3.setFixedHeight(20)

        self.status_label = QLabel('')
        self.status_label.setStyleSheet(STYLE_STATUS)

        self.source_selector = SourceSelectorWidget()
        self.source_selector.selection_changed.connect(self.source_selection_changed.emit)
        self.source_selector.setVisible(False)

        bar.addWidget(self.btn_backward)
        bar.addWidget(self.btn_play)
        bar.addWidget(self.btn_stop)
        bar.addWidget(self.btn_forward)
        bar.addWidget(sep1)
        bar.addWidget(self.speed_combo)
        bar.addWidget(self.replay_mode_combo)
        bar.addWidget(sep2)
        bar.addWidget(self.progress_slider)
        bar.addWidget(self.time_label)
        bar.addWidget(sep3)
        bar.addWidget(self.status_label)
        bar.addWidget(self.source_selector)
        bar.addStretch()

        # ── 缓存选择器独立行 ──
        cache_row = QHBoxLayout()
        cache_row.setContentsMargins(10, 4, 10, 0)
        cache_row.setSpacing(6)
        cache_label = QLabel('数据集:')
        cache_label.setStyleSheet('font-size: 9pt; color: #495057;')
        cache_row.addWidget(cache_label)
        self._cache_combo.setMinimumWidth(300)
        cache_row.addWidget(self._cache_combo, 1)
        cache_row.addStretch()

        time_row = QHBoxLayout()
        time_row.setContentsMargins(10, 2, 10, 2)
        time_row.setSpacing(6)

        time_row.addStretch()

        start_label = QLabel('起始')
        start_label.setStyleSheet(STYLE_TIME)
        time_row.addWidget(start_label)

        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setDecimals(1)
        self.start_time_spin.setSuffix(' s')
        self.start_time_spin.setRange(0, 99999)
        self.start_time_spin.setFixedWidth(90)
        self.start_time_spin.setStyleSheet(STYLE_SPIN)
        self.start_time_spin.setToolTip('设置回放起始时间（秒）')
        self.start_time_spin.valueChanged.connect(self._on_time_range_changed)
        time_row.addWidget(self.start_time_spin)

        end_label = QLabel('~ 结束')
        end_label.setStyleSheet(STYLE_TIME)
        time_row.addWidget(end_label)

        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setDecimals(1)
        self.end_time_spin.setSuffix(' s')
        self.end_time_spin.setRange(0, 99999)
        self.end_time_spin.setFixedWidth(90)
        self.end_time_spin.setSpecialValueText('末尾')
        self.end_time_spin.setStyleSheet(STYLE_SPIN)
        self.end_time_spin.setToolTip('设置回放结束时间（0=到末尾）')
        self.end_time_spin.valueChanged.connect(self._on_time_range_changed)
        time_row.addWidget(self.end_time_spin)

        sep_time = QFrame()
        sep_time.setFrameShape(QFrame.VLine)
        sep_time.setStyleSheet('background: #dee2e6; max-width: 1px;')
        sep_time.setFixedHeight(20)
        time_row.addWidget(sep_time)

        self.event_jump_combo = CheckableComboBox()
        self.event_jump_combo.setFixedWidth(200)
        self.event_jump_combo.setToolTip('勾选驾驶事件后点击跳转按钮')
        time_row.addWidget(self.event_jump_combo)

        self.btn_event_jump = QPushButton('跳转')
        self.btn_event_jump.setToolTip('跳转到勾选的事件区间')
        self.btn_event_jump.setFixedHeight(24)
        self.btn_event_jump.setStyleSheet(STYLE_BTN_CONTROL)
        self.btn_event_jump.clicked.connect(self._on_event_jump)
        self.btn_event_jump.setEnabled(False)
        self.event_jump_combo.selection_changed.connect(
            lambda ids: self.btn_event_jump.setEnabled(len(ids) > 0)
        )
        time_row.addWidget(self.btn_event_jump)

        self.btn_clear_range = QPushButton('↺ 全时段')
        self.btn_clear_range.setToolTip('清除时间区间，恢复全时段回放')
        self.btn_clear_range.setFixedHeight(24)
        self.btn_clear_range.setStyleSheet(STYLE_BTN_CONTROL)
        self.btn_clear_range.clicked.connect(self._on_clear_range)
        time_row.addWidget(self.btn_clear_range)

        time_row.addStretch()

        bottom_line = QFrame()
        bottom_line.setFrameShape(QFrame.HLine)
        bottom_line.setStyleSheet('background: #dee2e6; max-height: 1px;')

        outer.addLayout(cache_row)
        outer.addLayout(bar)
        outer.addLayout(time_row)
        outer.addWidget(bottom_line)

    def _on_play_clicked(self):
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()

    def _on_stop_clicked(self):
        self.stop_clicked.emit()

    def _on_speed_changed(self, index):
        if 0 <= index < len(SPEED_VALUES):
            self.speed_changed.emit(SPEED_VALUES[index])

    def _on_replay_mode_changed(self, index):
        if 0 <= index < len(REPLAY_MODE_VALUES):
            self.replay_mode_changed.emit(REPLAY_MODE_VALUES[index])

    def set_replay_mode(self, mode: str):
        """设置回放模式"""
        try:
            index = REPLAY_MODE_VALUES.index(mode)
            self.replay_mode_combo.blockSignals(True)
            self.replay_mode_combo.setCurrentIndex(index)
            self.replay_mode_combo.blockSignals(False)
        except ValueError:
            logger.warning(f'未知的回放模式: {mode}')

    def reset_state(self):
        self._is_playing = False
        self.btn_play.setText('\u25B6  播放')
        if hasattr(self, 'progress_slider'):
            self.progress_slider.setValue(0)
        if hasattr(self, 'time_edit_start'):
            self.time_edit_start.setTime(QTime(0, 0, 0))
        if hasattr(self, 'time_edit_end'):
            self.time_edit_end.setTime(QTime(0, 0, 0))
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(0)
        self._time_min = 0.0
        self._time_max = 0.0

    def clear_all(self):
        """清除所有回放控制栏数据（实现 ClearableResource 协议）"""
        self.reset_state()
        self.set_play_enabled(False)
        self.set_events([])
        self._update_time_label(0.0)
        if hasattr(self, 'event_jump_combo') and self.event_jump_combo:
            self.event_jump_combo.clear_items()
        if hasattr(self, 'time_label') and self.time_label:
            self.time_label.setText("00:00 / 00:00")

    def _on_slider_released(self):
        if self._time_max > self._time_min:
            ratio = self.progress_slider.value() / 1000.0
            seek_time = self._time_min + ratio * (self._time_max - self._time_min)
            self.progress_seek.emit(seek_time)

    def set_playing(self, playing: bool):
        self._is_playing = playing
        if playing:
            self.btn_play.setText('\u23F8  暂停')
            self.btn_play.setToolTip('暂停')
        else:
            self.btn_play.setText('\u25B6  播放')
            self.btn_play.setToolTip('播放')

    def set_time_range(self, t_min: float, t_max: float):
        self._time_min = t_min
        self._time_max = t_max
        self.start_time_spin.blockSignals(True)
        self.end_time_spin.blockSignals(True)
        self.start_time_spin.setRange(t_min, t_max)
        self.end_time_spin.setRange(0, t_max)
        self.start_time_spin.setValue(t_min)
        self.end_time_spin.setValue(0)
        self.start_time_spin.blockSignals(False)
        self.end_time_spin.blockSignals(False)
        self._update_time_label(0.0)

    def update_progress(self, progress: float):
        progress = max(0.0, min(1.0, progress))
        if self._time_max > self._time_min:
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(progress * 1000))
            self.progress_slider.blockSignals(False)
        cursor = self._time_min + progress * (self._time_max - self._time_min)
        self._update_time_label(cursor)

    def _update_time_label(self, cursor: float):
        current = max(0, cursor - self._time_min)
        total = self._time_max - self._time_min
        self.time_label.setText(
            f'{self._fmt_time(current)} / {self._fmt_time(total)}'
        )

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f'{m:02d}:{s:02d}'

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_source_info(self, source_types: list):
        if not source_types:
            self.source_selector.setVisible(False)
            return
        self.source_selector.set_sources(source_types)
        self.source_selector.setVisible(True)

    def get_selected_sources(self) -> list:
        return self.source_selector.get_selected()

    def show_bar(self):
        self.setVisible(True)
        self._set_controls_enabled(True)
        self.btn_play.setEnabled(False)
        self.btn_play.setToolTip('数据采集中，请等待完成后播放')

    def hide_bar(self):
        self.setVisible(False)

    def set_play_enabled(self, enabled: bool):
        self.btn_play.setEnabled(enabled)
        if enabled:
            self.btn_play.setToolTip('播放 / 暂停')
        else:
            self.btn_play.setToolTip('数据采集中，请等待完成后播放')

    def _set_controls_enabled(self, enabled: bool):
        self.btn_backward.setEnabled(enabled)
        self.btn_play.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)
        self.btn_forward.setEnabled(enabled)
        self.speed_combo.setEnabled(enabled)
        self.replay_mode_combo.setEnabled(enabled)
        self.progress_slider.setEnabled(enabled)
        self.start_time_spin.setEnabled(enabled)
        self.end_time_spin.setEnabled(enabled)
        self.event_jump_combo.setEnabled(enabled)
        self.btn_event_jump.setEnabled(enabled)
        self.btn_clear_range.setEnabled(enabled)

    # ── 缓存选择器方法 ──

    def set_cache_list(self, entries: list):
        """
        设置缓存选择器的下拉列表。
        entries: CacheEntry 对象列表
        """
        self._cache_combo.blockSignals(True)
        self._cache_combo.clear()
        self._cache_entries = {}  # index → entry
        if entries:
            self._cache_combo.setEnabled(True)
            for entry in entries:
                self._cache_entries[self._cache_combo.count()] = entry
                self._cache_combo.addItem(entry.display_label)
            # 默认选中最新（索引0）
            self._cache_combo.setCurrentIndex(0)
        else:
            self._cache_combo.addItem('(无可用缓存)')
            self._cache_combo.setEnabled(False)
        self._cache_combo.blockSignals(False)

    def _on_cache_selected(self, index: int):
        """缓存选择器变更回调"""
        entry = self._cache_entries.get(index) if hasattr(self, '_cache_entries') else None
        if entry:
            self.cache_selection_changed.emit(entry.id)

    def get_selected_cache_id(self) -> str:
        """获取当前选中的缓存 id"""
        index = self._cache_combo.currentIndex()
        entry = self._cache_entries.get(index) if hasattr(self, '_cache_entries') else None
        return entry.id if entry else ''

    def set_events(self, events: list):
        items = []
        if events:
            try:
                from core.core.analysis.core_types import BEHAVIOR_LABELS_CN
            except ImportError:
                BEHAVIOR_LABELS_CN = {}
            for evt in events:
                eid = getattr(evt, 'id', '') or getattr(evt, 'event_id', '')
                etype = getattr(evt, 'type', '') or getattr(evt, 'event_type', 'unknown')
                start_t = getattr(evt, 'start_time', 0)
                label_cn = BEHAVIOR_LABELS_CN.get(etype, etype)
                label = f'{label_cn} @ {start_t:.1f}s'
                items.append((label, str(eid)))
        self.event_jump_combo.set_items(items)

    def sync_events_from_distributor(self):
        """从 EventDistributor 统一同步事件到回放栏（唯一事件源）"""
        from core.core.analysis.event_distributor import EventDistributor
        events = EventDistributor.instance().get_events()
        self.set_events(events)

    def _on_time_range_changed(self):
        start_val = self.start_time_spin.value()
        end_val = self.end_time_spin.value()
        self.time_range_changed.emit(start_val, end_val)

    def _on_event_jump(self):
        event_ids = self.event_jump_combo.get_checked_data()
        if event_ids:
            self.event_jump_requested.emit(event_ids)

    def _on_clear_range(self):
        self.start_time_spin.blockSignals(True)
        self.end_time_spin.blockSignals(True)
        self.start_time_spin.setValue(0)
        self.end_time_spin.setValue(0)
        self.start_time_spin.blockSignals(False)
        self.end_time_spin.blockSignals(False)
        self.time_range_changed.emit(0, 0)

    def update_time_range_display(self, start_time: float, end_time: float):
        """更新回放区间显示（时间标签 + SpinBox），同步 _time_min/_time_max 确保进度条正确"""
        self._time_min = start_time
        if end_time > 0:
            self._time_max = end_time
        self.start_time_spin.blockSignals(True)
        self.end_time_spin.blockSignals(True)
        self.start_time_spin.setRange(self._time_min, self._time_max)
        self.end_time_spin.setRange(0, self._time_max)
        self.start_time_spin.setValue(start_time)
        self.end_time_spin.setValue(end_time)
        self.start_time_spin.blockSignals(False)
        self.end_time_spin.blockSignals(False)
        self._update_time_label(start_time)