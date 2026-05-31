#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 专业可视化组件 v2.0 — 车辆动力学监控级别
优化升级版本，包含：
1. 视窗内动态降采样 (分段极值采样)
2. 固定Y轴范围，可配置视窗时长
3. 多通道独立显示，避免波形重叠
4. 峰值标记、数据点显示
5. 数据预处理 (低通滤波)
6. 高性能渲染优化
"""

import logging
import time
import math
from collections import deque
from enum import Enum
from typing import List, Tuple, Dict, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGridLayout, QFrame,
                               QSizePolicy, QComboBox, QSplitter,
                               QCheckBox)
from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import (QFont, QColor, QPainter, QPen, QBrush,
                           QPainterPath, QLinearGradient, QPolygon)

logger = logging.getLogger(__name__)

# ============================================================
# 设计系统 & 配置
# ============================================================
FONT_FAMILY = "Microsoft YaHei"
FONT_MONO = "Consolas"

CLR_BG = "#0a0e14"
CLR_PANEL = "#111823"
CLR_BORDER = "#1a2a3a"
CLR_GRID_MAJOR = "#182838"
CLR_GRID_MINOR = "#0f1820"
CLR_TEXT = "#d0d8e0"
CLR_TEXT_DIM = "#506070"
CLR_ACCENT = "#00b8d4"

CLR_AX = "#ff5252"
CLR_AY = "#69f0ae"
CLR_AZ = "#448aff"
CLR_GX = "#00e5ff"
CLR_GY = "#ea80fc"
CLR_GZ = "#ffd740"
CLR_SPEED = "#ffffff"
CLR_WHEEL = "#ff9800"

ALARM_ACCEL_HI = 10.0
ALARM_ACCEL_LO = -10.0
ALARM_GYRO_HI = 6.0
ALARM_GYRO_LO = -6.0
ALARM_SPEED_HI = 150
ALARM_SPEED_LO = 0
ALARM_WHEEL_HI = 540
ALARM_WHEEL_LO = -540

# 默认固定Y轴范围
DEFAULT_AX_RANGE = (-16, 16)
DEFAULT_GYRO_RANGE = (-10, 10)
DEFAULT_SPEED_RANGE = (0, 150)
DEFAULT_WHEEL_RANGE = (-720, 720)

# 视窗时长选项
TIME_WINDOW_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]


def _filter_low_pass(value, prev, alpha=0.3):
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


class DownsampleMode(Enum):
    EXTREMA = "极值采样 (保留峰谷)"
    AVERAGE = "平均采样"
    MAX_POINTS = "最大点采样"


# ============================================================
# 专业数据点类
# ============================================================
class DataPoint:
    def __init__(self, t, v):
        self.t = t
        self.v = v


# ============================================================
# 分段极值降采样核心算法
# ============================================================
class ExtremaDownsampler:
    @staticmethod
    def downsample(data: List[DataPoint], target_points: int,
                   mode: DownsampleMode = DownsampleMode.EXTREMA) -> List[DataPoint]:
        if len(data) <= target_points:
            return data.copy()

        if mode == DownsampleMode.EXTREMA:
            return ExtremaDownsampler._downsample_extrema(data, target_points)
        elif mode == DownsampleMode.AVERAGE:
            return ExtremaDownsampler._downsample_average(data, target_points)
        else:
            return ExtremaDownsampler._downsample_max_points(data, target_points)

    @staticmethod
    def _downsample_extrema(data: List[DataPoint], target_points: int) -> List[DataPoint]:
        if len(data) <= target_points:
            return data.copy()

        result = []
        window_size = len(data) / target_points

        for i in range(target_points):
            start = int(i * window_size)
            end = min(int((i + 1) * window_size), len(data) - 1)

            if start >= len(data):
                break

            window = data[start:end + 1]
            min_val = min(window, key=lambda x: x.v)
            max_val = max(window, key=lambda x: x.v)

            if min_val.t < max_val.t:
                result.append(min_val)
                if min_val != max_val:
                    result.append(max_val)
            else:
                result.append(max_val)
                if min_val != max_val:
                    result.append(min_val)

        return result

    @staticmethod
    def _downsample_average(data: List[DataPoint], target_points: int) -> List[DataPoint]:
        if len(data) <= target_points:
            return data.copy()

        result = []
        window_size = len(data) / target_points

        for i in range(target_points):
            start = int(i * window_size)
            end = min(int((i + 1) * window_size), len(data) - 1)

            if start >= len(data):
                break

            window = data[start:end + 1]
            avg_t = sum(d.t for d in window) / len(window)
            avg_v = sum(d.v for d in window) / len(window)

            result.append(DataPoint(avg_t, avg_v))

        return result

    @staticmethod
    def _downsample_max_points(data: List[DataPoint], target_points: int) -> List[DataPoint]:
        if len(data) <= target_points:
            return data.copy()

        step = len(data) / target_points
        result = []
        for i in range(target_points):
            idx = int(i * step)
            if idx < len(data):
                result.append(data[idx])

        return result


# ============================================================
# 参数瓦片组件 (增强版)
# ============================================================
class IMUParameterTile(QFrame):
    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._color = color
        self._value = 0
        self._history = deque(maxlen=10)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(50)
        self.setMinimumWidth(120)
        self.setStyleSheet(f"""
            IMUParameterTile {{
                background-color: {CLR_PANEL};
                border: 1px solid {CLR_BORDER};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._title_label = QLabel(self._title)
        self._title_label.setFont(QFont(FONT_FAMILY, 8))
        self._title_label.setStyleSheet(f"color: {self._color}; border: none; background: transparent;")
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._title_label)

        self._value_label = QLabel("---")
        self._value_label.setFont(QFont(FONT_MONO, 16, QFont.Bold))
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._value_label)

        bot = QHBoxLayout()
        bot.setSpacing(4)
        self._trend_label = QLabel("")
        self._trend_label.setFont(QFont(FONT_FAMILY, 7))
        self._trend_label.setStyleSheet("border: none; background: transparent;")
        bot.addWidget(self._trend_label)
        bot.addStretch()
        self._unit_label = QLabel(self._unit)
        self._unit_label.setFont(QFont(FONT_FAMILY, 8))
        self._unit_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bot.addWidget(self._unit_label)
        layout.addLayout(bot)

    def _alarm_color(self, value, lo, hi, ok_color):
        if value is None:
            return CLR_TEXT_DIM
        if value > hi:
            return "#ff1744"
        if value < lo:
            return "#ffc107"
        return ok_color

    def _trend_arrow(self, current):
        if len(self._history) < 2:
            return ""
        if current is None or math.isnan(current) or math.isinf(current):
            return ""
        avg_prev = sum(list(self._history)[-3:-1]) / min(2, len(self._history)-1)
        if abs(avg_prev) < 1e-9:
            return ""
        diff_pct = (current - avg_prev) / abs(avg_prev) * 100
        if diff_pct > 5:
            return " ▲"
        if diff_pct < -5:
            return " ▼"
        return ""

    def set_value(self, value, lo=None, hi=None):
        self._value = value
        if value is None or math.isnan(value) or math.isinf(value):
            self._value_label.setText("---")
            self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
            self._trend_label.setText("")
            return

        self._history.append(value)
        arrow = self._trend_arrow(value)

        clr = self._alarm_color(value, lo, hi, self._color) if lo is not None and hi is not None else self._color

        if abs(value) < 10:
            self._value_label.setText(f"{value:.3f}")
        elif abs(value) < 100:
            self._value_label.setText(f"{value:.1f}")
        else:
            self._value_label.setText(f"{value:.0f}")

        self._value_label.setStyleSheet(f"color: {clr}; border: none; background: transparent;")
        self._trend_label.setText(arrow)
        self._trend_label.setStyleSheet(f"color: {clr}; border: none; background: transparent;")

    def reset(self):
        self._value = 0
        self._history.clear()
        self._value_label.setText("---")
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._trend_label.setText("")


# ============================================================
# 专业波形通道组件 (含降采样核心)
# ============================================================
class IMUProWaveformChannel(QWidget):
    def __init__(self, title, unit, y_range, series_config, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._fixed_y_lo, self._fixed_y_hi = y_range
        self._series_config = series_config
        self._buffers: Dict[str, deque] = {}
        self._filtered_buffers: Dict[str, deque] = {}
        self._prev_filtered: Dict[str, float] = {}

        self._max_points = 2000
        self._render_points = 500
        self._frozen = False

        self._auto_range = False
        self._y_lo = float(self._fixed_y_lo)
        self._y_hi = float(self._fixed_y_hi)
        self._target_y_lo = self._y_lo
        self._target_y_hi = self._y_hi
        self._smooth_factor = 0.30
        self._padding_ratio = 0.10
        self._range_update_counter = 0
        self._range_update_interval = 10

        self._show_peaks = True
        self._line_width = 1.5

        self._first_update = True
        self._downsample_mode = DownsampleMode.EXTREMA

        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def feed(self, series_name, value, t):
        if self._frozen:
            return
        if value is None:
            return
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return

        if series_name not in self._buffers:
            self._buffers[series_name] = deque(maxlen=self._max_points)
            self._filtered_buffers[series_name] = deque(maxlen=self._max_points)
            self._prev_filtered[series_name] = None

        self._buffers[series_name].append(DataPoint(t, value))

        filtered = _filter_low_pass(value, self._prev_filtered[series_name], alpha=0.2)
        self._filtered_buffers[series_name].append(DataPoint(t, filtered))
        self._prev_filtered[series_name] = filtered

    def flush(self):
        if self._auto_range:
            if self._first_update:
                self._first_update = False
                self._update_auto_range()
                self._y_lo = self._target_y_lo
                self._y_hi = self._target_y_hi
                self._range_update_counter = 0
            else:
                self._range_update_counter += 1
                if self._range_update_counter >= self._range_update_interval:
                    self._range_update_counter = 0
                    self._update_auto_range()

        self._apply_smooth_range()
        self.update()

    def set_frozen(self, frozen):
        self._frozen = frozen

    def clear(self):
        for buf in self._buffers.values():
            buf.clear()
        for buf in self._filtered_buffers.values():
            buf.clear()
        self._prev_filtered.clear()
        if self._auto_range:
            self._y_lo = float(self._fixed_y_lo)
            self._y_hi = float(self._fixed_y_hi)
            self._target_y_lo = self._y_lo
            self._target_y_hi = self._y_hi
            self._first_update = True
        self.update()

    def set_auto_range(self, enabled):
        self._auto_range = enabled
        if not enabled:
            self._target_y_lo = float(self._fixed_y_lo)
            self._target_y_hi = float(self._fixed_y_hi)
        else:
            self._first_update = True
        self._range_update_counter = 0

    def toggle_auto_range(self):
        self.set_auto_range(not self._auto_range)
        return self._auto_range

    def is_auto_range(self):
        return self._auto_range

    def set_show_peaks(self, show):
        self._show_peaks = show

    def set_y_range(self, lo, hi):
        self._fixed_y_lo = lo
        self._fixed_y_hi = hi
        if not self._auto_range:
            self._target_y_lo = float(lo)
            self._target_y_hi = float(hi)

    def _update_auto_range(self):
        all_vals = []
        for buf in self._filtered_buffers.values():
            if len(buf) > 0:
                all_vals.extend([d.v for d in buf])

        if not all_vals:
            return

        data_min = min(all_vals)
        data_max = max(all_vals)

        if data_max - data_min < 1e-9:
            data_min -= 0.5
            data_max += 0.5

        padding = (data_max - data_min) * self._padding_ratio
        new_lo = data_min - padding
        new_hi = data_max + padding

        self._target_y_lo = new_lo
        self._target_y_hi = new_hi

    def _apply_smooth_range(self):
        self._y_lo += (self._target_y_lo - self._y_lo) * self._smooth_factor
        self._y_hi += (self._target_y_hi - self._y_hi) * self._smooth_factor

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor(CLR_PANEL))
        painter.setPen(QColor(CLR_BORDER))
        painter.drawRect(0, 0, w - 1, h - 1)

        ml = 70
        mt = 22
        mb = 28
        mr = 12
        pw = w - ml - mr
        ph = h - mt - mb

        self._draw_grid(painter, ml, mt, pw, ph)
        self._draw_series(painter, ml, mt, pw, ph)
        self._draw_labels(painter, ml, mt, pw, ph)
        painter.end()

    def _draw_grid(self, painter, ml, mt, pw, ph):
        for i in range(5):
            y = mt + int(ph * i / 4)
            painter.setPen(QPen(QColor(CLR_GRID_MAJOR), 1))
            painter.drawLine(ml, y, ml + pw, y)

        for i in range(11):
            x = ml + int(pw * i / 10)
            painter.setPen(QPen(QColor(CLR_GRID_MINOR), 0.5))
            painter.drawLine(x, mt, x, mt + ph)

        y_zero = mt + ph * 0.5
        if self._y_lo <= 0 <= self._y_hi:
            y_norm = 1.0 - (0 - self._y_lo) / (self._y_hi - self._y_lo)
            y_zero = mt + ph * y_norm

        painter.setPen(QPen(QColor("#305060"), 1.5, Qt.DashLine))
        painter.drawLine(ml, int(y_zero), ml + pw, int(y_zero))

    def _draw_series(self, painter, ml, mt, pw, ph):
        y_lo = self._y_lo
        y_hi = self._y_hi
        if abs(y_hi - y_lo) < 1e-9:
            y_hi = y_lo + 1.0

        for name, cfg in self._series_config.items():
            buf = self._filtered_buffers.get(name, deque())
            if len(buf) < 2:
                continue

            vals = list(buf)
            color = QColor(cfg.get('color', CLR_TEXT))
            width = cfg.get('width', self._line_width)

            downsampled = ExtremaDownsampler.downsample(
                vals, self._render_points, self._downsample_mode)

            if len(downsampled) < 2:
                continue

            t_min = downsampled[0].t
            t_max = downsampled[-1].t
            if t_max - t_min < 1e-9:
                t_max = t_min + 1.0

            path = QPainterPath()
            first = True
            peak_points = []

            for i, dp in enumerate(downsampled):
                t_norm = (dp.t - t_min) / (t_max - t_min)
                x = ml + pw * t_norm
                y_norm = (dp.v - y_lo) / (y_hi - y_lo)
                y_norm = max(0.0, min(1.0, y_norm))
                y = mt + ph * (1.0 - y_norm)

                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)

                if self._show_peaks and (i % 20 == 0 or i == len(downsampled) - 1 or i == 0):
                    peak_points.append((x, y))

            painter.setPen(QPen(color, width))
            painter.drawPath(path)

            if self._show_peaks:
                for (x, y) in peak_points:
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(int(x), int(y), 4, 4)

    def _draw_labels(self, painter, ml, mt, pw, ph):
        y_lo = self._y_lo
        y_hi = self._y_hi

        painter.setPen(QColor(CLR_TEXT_DIM))
        painter.setFont(QFont(FONT_FAMILY, 8))
        for i in range(5):
            y = mt + int(ph * i / 4)
            val = y_hi - (y_hi - y_lo) * i / 4
            painter.drawText(QRectF(2, y - 10, ml - 6, 20), Qt.AlignRight | Qt.AlignVCenter, f"{val:.1f}")

        painter.setPen(QColor(CLR_ACCENT))
        painter.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        mode_tag = " [AUTO]" if self._auto_range else ""
        painter.drawText(QRectF(ml + 6, mt - 4, 200, 20), Qt.AlignLeft | Qt.AlignVCenter, self._title + mode_tag)

        legend_x = ml + pw - 200
        legend_y = mt + 4
        for name, cfg in self._series_config.items():
            color = QColor(cfg.get('color', CLR_TEXT))
            painter.setPen(color)
            painter.setBrush(color)
            painter.drawRect(int(legend_x), int(legend_y + 2), 10, 4)
            painter.drawText(QRectF(legend_x + 16, legend_y, 100, 16), Qt.AlignLeft, name)
            legend_x += 80

        if self._buffers:
            first_name = list(self._buffers.keys())[0]
            buf = self._buffers.get(first_name, deque())
            if len(buf) > 1:
                data_points = len(buf)
                ds_points = min(self._render_points, data_points)
                painter.setPen(QColor(CLR_TEXT_DIM))
                painter.drawText(QRectF(ml + 6, mt + ph + 4, 200, 20), Qt.AlignLeft,
                               f"{data_points} pts → {ds_points} pts  |  降采样: {self._downsample_mode.value}")


# ============================================================
# 主专业IMU可视化组件
# ============================================================
class IMUProVisualizer(QWidget):
    data_received = Signal(dict)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._init_data()
        self._init_ui()
        self._init_timers()
        self.logger.info("IMU 专业可视化初始化完成")

    def _init_data(self):
        self.data_bridge = None
        self.is_running = False
        self._sample_count = 0
        self._ring_buffer = deque(maxlen=5000)
        self._last_render_ts = 0
        self._render_interval = 0.033
        self._time_window = 5.0
        self._start_time = None

    def _init_ui(self):
        self.setFont(QFont(FONT_FAMILY, 9))
        self.setStyleSheet(f"background-color: {CLR_BG}; color: {CLR_TEXT};")

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # 顶部控制面板
        top_ctrl = QHBoxLayout()

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont(FONT_FAMILY, 10))
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")
        top_ctrl.addWidget(self.status_label)

        top_ctrl.addStretch()

        # 视窗时长控制
        top_ctrl.addWidget(QLabel(" 视窗时长:"))
        self.time_window_combo = QComboBox()
        for t in TIME_WINDOW_OPTIONS:
            self.time_window_combo.addItem(f"{t:.1f} s", t)
        self.time_window_combo.setCurrentIndex(3)
        self.time_window_combo.setStyleSheet(self._combo_style())
        self.time_window_combo.currentIndexChanged.connect(self._on_time_window_changed)
        top_ctrl.addWidget(self.time_window_combo)

        # 播放速度
        top_ctrl.addWidget(QLabel(" 播放速度:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x", "20x", "50x"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.setStyleSheet(self._combo_style())
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        top_ctrl.addWidget(self.speed_combo)

        top_ctrl.addStretch()

        # 功能按钮
        self.auto_range_btn = QPushButton("📐 自适应Y轴: OFF")
        self.auto_range_btn.setCheckable(True)
        self.auto_range_btn.setChecked(False)
        self.auto_range_btn.setStyleSheet(self._btn_style())
        self.auto_range_btn.clicked.connect(self._toggle_auto_range)
        top_ctrl.addWidget(self.auto_range_btn)

        self.peaks_btn = QPushButton("⚡ 显示峰值: ON")
        self.peaks_btn.setCheckable(True)
        self.peaks_btn.setChecked(True)
        self.peaks_btn.setStyleSheet(self._btn_style())
        self.peaks_btn.clicked.connect(self._toggle_peaks)
        top_ctrl.addWidget(self.peaks_btn)

        self.freeze_btn = QPushButton("⏸ 冻结")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.setStyleSheet(self._btn_style())
        self.freeze_btn.clicked.connect(self._toggle_freeze)
        top_ctrl.addWidget(self.freeze_btn)

        self.clear_btn = QPushButton("🗑 清除")
        self.clear_btn.setStyleSheet(self._btn_style())
        self.clear_btn.clicked.connect(self._on_clear)
        top_ctrl.addWidget(self.clear_btn)

        root.addLayout(top_ctrl)

        # 参数瓦片
        tiles_grid = QGridLayout()
        tiles_grid.setSpacing(5)
        all_params = [
            ("AX 纵向加速", "m/s²", CLR_AX, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("AY 横向加速", "m/s²", CLR_AY, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("AZ 垂向加速", "m/s²", CLR_AZ, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("GX 横滚角速", "rad/s", CLR_GX, ALARM_GYRO_LO, ALARM_GYRO_HI),
            ("GY 俯仰角速", "rad/s", CLR_GY, ALARM_GYRO_LO, ALARM_GYRO_HI),
            ("GZ 偏航角速", "rad/s", CLR_GZ, ALARM_GYRO_LO, ALARM_GYRO_HI),
            ("Speed 车速", "km/h", CLR_SPEED, ALARM_SPEED_LO, ALARM_SPEED_HI),
            ("Wheel 转向角", "°", CLR_WHEEL, ALARM_WHEEL_LO, ALARM_WHEEL_HI),
        ]
        self.all_tiles = {}
        for i, (title, unit, color, lo, hi) in enumerate(all_params):
            key = title.split()[0]
            tile = IMUParameterTile(title, unit, color)
            self.all_tiles[key] = (tile, lo, hi)
            row, col = divmod(i, 4)
            tiles_grid.addWidget(tile, row, col)
        root.addLayout(tiles_grid)

        # 波形区域 - 使用分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {CLR_BORDER}; }}")

        self.channel_accel = IMUProWaveformChannel(
            "加速度", "m/s²", DEFAULT_AX_RANGE,
            {"AX": {"color": CLR_AX, "width": 1.5},
             "AY": {"color": CLR_AY, "width": 1.5},
             "AZ": {"color": CLR_AZ, "width": 1.5}}
        )
        self.channel_accel._downsample_mode = DownsampleMode.EXTREMA
        splitter.addWidget(self.channel_accel)

        self.channel_gyro = IMUProWaveformChannel(
            "角速度", "rad/s", DEFAULT_GYRO_RANGE,
            {"GX": {"color": CLR_GX, "width": 1.5},
             "GY": {"color": CLR_GY, "width": 1.5},
             "GZ": {"color": CLR_GZ, "width": 1.5}}
        )
        self.channel_gyro._downsample_mode = DownsampleMode.EXTREMA
        splitter.addWidget(self.channel_gyro)

        self.channel_vehicle = IMUProWaveformChannel(
            "车速", "km/h", DEFAULT_SPEED_RANGE,
            {"Speed": {"color": CLR_SPEED, "width": 2.0}}
        )
        self.channel_vehicle._downsample_mode = DownsampleMode.EXTREMA
        splitter.addWidget(self.channel_vehicle)

        self.channel_wheel = IMUProWaveformChannel(
            "方向盘转向角", "°", DEFAULT_WHEEL_RANGE,
            {"Wheel": {"color": CLR_WHEEL, "width": 1.5}}
        )
        self.channel_wheel._downsample_mode = DownsampleMode.EXTREMA
        splitter.addWidget(self.channel_wheel)

        root.addWidget(splitter, 10)

        # 底部信息栏
        info_bar = QHBoxLayout()
        info_bar.setSpacing(16)
        self.lbl_samples = QLabel("样本: 0")
        self.lbl_fps = QLabel("FPS: 0")
        self.lbl_time = QLabel("时间窗口: 5.0 s")
        for lbl in [self.lbl_samples, self.lbl_fps, self.lbl_time]:
            lbl.setFont(QFont(FONT_FAMILY, 9))
            lbl.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")
            info_bar.addWidget(lbl)
        info_bar.addStretch()
        root.addLayout(info_bar)

    def _btn_style(self):
        return f"""
            QPushButton {{
                background-color: {CLR_PANEL};
                color: {CLR_ACCENT};
                border: 1px solid {CLR_BORDER};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #182838; }}
            QPushButton:checked {{ background-color: #ffc107; color: #000; }}
        """

    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {CLR_PANEL};
                color: {CLR_ACCENT};
                border: 1px solid {CLR_BORDER};
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 10pt;
            }}
            QComboBox:hover {{ border-color: {CLR_ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {CLR_PANEL};
                color: {CLR_TEXT};
                selection-background-color: {CLR_ACCENT};
                selection-color: #000;
            }}
        """

    def _init_timers(self):
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._render_loop)
        self._render_timer.start(33)

        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)
        self._fps_counter = 0

    def _render_loop(self):
        if not getattr(self, 'all_tiles', None):
            return
        if not self.is_running or self.freeze_btn.isChecked():
            return
        if not self._ring_buffer:
            return

        batch = []
        for _ in range(min(len(self._ring_buffer), 200)):
            batch.append(self._ring_buffer.popleft())

        for record in batch:
            self._apply_record(record)

        self.channel_accel.flush()
        self.channel_gyro.flush()
        self.channel_vehicle.flush()
        self.channel_wheel.flush()

        self._fps_counter += 1

    def _apply_record(self, record):
        if not isinstance(record, dict):
            return
        if not getattr(self, 'all_tiles', None):
            return

        t = record.get('t', 0.0)
        ax = record.get('ax')
        ay = record.get('ay')
        az = record.get('az')
        gx = record.get('gx')
        gy = record.get('gy')
        gz = record.get('gz')
        speed = record.get('speed')
        wheel = record.get('wheel')

        if self._start_time is None:
            self._start_time = t

        t_rel = t - self._start_time

        self._sample_count += 1

        tile_ax, lo_ax, hi_ax = self.all_tiles['AX']
        tile_ax.set_value(ax, lo_ax, hi_ax)
        tile_ay, lo_ay, hi_ay = self.all_tiles['AY']
        tile_ay.set_value(ay, lo_ay, hi_ay)
        tile_az, lo_az, hi_az = self.all_tiles['AZ']
        tile_az.set_value(az, lo_az, hi_az)

        tile_speed, lo_sp, hi_sp = self.all_tiles['Speed']
        tile_speed.set_value(speed, lo_sp, hi_sp)
        tile_wheel, lo_wh, hi_wh = self.all_tiles['Wheel']
        tile_wheel.set_value(wheel, lo_wh, hi_wh)

        tile_gx, lo_gx, hi_gx = self.all_tiles['GX']
        tile_gx.set_value(gx, lo_gx, hi_gx)
        tile_gy, lo_gy, hi_gy = self.all_tiles['GY']
        tile_gy.set_value(gy, lo_gy, hi_gy)
        tile_gz, lo_gz, hi_gz = self.all_tiles['GZ']
        tile_gz.set_value(gz, lo_gz, hi_gz)

        if ax is not None:
            self.channel_accel.feed("AX", ax, t_rel)
        if ay is not None:
            self.channel_accel.feed("AY", ay, t_rel)
        if az is not None:
            self.channel_accel.feed("AZ", az, t_rel)

        if gx is not None:
            self.channel_gyro.feed("GX", gx, t_rel)
        if gy is not None:
            self.channel_gyro.feed("GY", gy, t_rel)
        if gz is not None:
            self.channel_gyro.feed("GZ", gz, t_rel)

        if speed is not None:
            self.channel_vehicle.feed("Speed", speed, t_rel)

        if wheel is not None:
            self.channel_wheel.feed("Wheel", wheel, t_rel)

        if self._sample_count % 100 == 0:
            self.lbl_samples.setText(f"样本: {self._sample_count}")

    def _update_fps(self):
        self.lbl_fps.setText(f"FPS: {self._fps_counter}")
        self._fps_counter = 0

    def start(self):
        self.is_running = True
        self.status_label.setText("运行中")
        self.status_label.setStyleSheet(f"color: #4caf50; background: transparent;")
        self._start_time = None

    def stop(self):
        self.is_running = False
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")

    def set_data_bridge(self, data_bridge):
        self.data_bridge = data_bridge
        self.logger.info("IMU Pro 已连接 DataBridge")

    def receive_imu_data(self, sensor_data):
        if not self.is_running:
            return
        self._ring_buffer.append(sensor_data)

    def _toggle_freeze(self, checked):
        self.channel_accel.set_frozen(checked)
        self.channel_gyro.set_frozen(checked)
        self.channel_vehicle.set_frozen(checked)
        self.channel_wheel.set_frozen(checked)
        self.status_label.setText("已冻结" if checked else "运行中")

    def _toggle_auto_range(self, checked):
        self.channel_accel.set_auto_range(checked)
        self.channel_gyro.set_auto_range(checked)
        self.channel_vehicle.set_auto_range(checked)
        self.channel_wheel.set_auto_range(checked)
        self.auto_range_btn.setText("📐 自适应Y轴: ON" if checked else "📐 自适应Y轴: OFF")
        self.logger.info(f"IMU Pro 自适应Y轴: {'启用' if checked else '禁用'}")

    def _toggle_peaks(self, checked):
        self.channel_accel.set_show_peaks(checked)
        self.channel_gyro.set_show_peaks(checked)
        self.channel_vehicle.set_show_peaks(checked)
        self.channel_wheel.set_show_peaks(checked)
        self.peaks_btn.setText("⚡ 显示峰值: ON" if checked else "⚡ 显示峰值: OFF")
        self.logger.info(f"IMU Pro 峰值显示: {'启用' if checked else '禁用'}")

    def _on_clear(self):
        self._sample_count = 0
        self._start_time = None
        self._ring_buffer.clear()
        self.channel_accel.clear()
        self.channel_gyro.clear()
        self.channel_vehicle.clear()
        self.channel_wheel.clear()
        if hasattr(self, 'all_tiles') and self.all_tiles:
            for key in self.all_tiles:
                tile, _, _ = self.all_tiles[key]
                tile.reset()
        self.lbl_samples.setText("样本: 0")
        self.lbl_fps.setText("FPS: 0")
        self.logger.info("IMU Pro 可视化已清除")

    def _on_time_window_changed(self, idx):
        t = self.time_window_combo.itemData(idx)
        self._time_window = t
        self.lbl_time.setText(f"时间窗口: {t:.1f} s")
        self.logger.info(f"IMU Pro 时间窗口切换为: {t:.1f} s")

    def _on_speed_changed(self, text):
        multiplier = float(text.replace("x", ""))
        self.logger.info(f"IMU Pro 播放速度切换为: {multiplier}x")
        if self.data_bridge:
            try:
                from modules.ui.left_control_panel.utils.data_reader_manager import get_data_reader_manager
                mgr = get_data_reader_manager()
                if mgr:
                    mgr.set_playback_speed(multiplier)
            except Exception as e:
                self.logger.warning(f"设置速度倍率失败: {e}")
