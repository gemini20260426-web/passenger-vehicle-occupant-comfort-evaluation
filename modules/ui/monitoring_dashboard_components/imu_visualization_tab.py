#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 专业可视化组件 v2.0 — 车辆动力学监控级别
优化升级版本，包含:
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
                               QCheckBox, QScrollArea)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import (QFont, QColor, QPainter, QPen, QBrush,
                           QPainterPath, QLinearGradient, QPolygon)

logger = logging.getLogger(__name__)

# ============================================================
# 设计系统 & 配置
# ============================================================
FONT_FAMILY = "Microsoft YaHei"
FONT_MONO = "Consolas"

CLR_BG = "#010508"
CLR_PANEL = "#0c1218"
CLR_BORDER = "#1a2530"
CLR_GRID_MAJOR = "#1a2838"
CLR_GRID_MINOR = "#0f1a25"
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
CLR_OK = "#4caf50"

MATLAB_BLUE = "#0072BD"
MATLAB_RED = "#D95319"
MATLAB_YELLOW = "#EDB120"
MATLAB_PURPLE = "#7E2F8E"
MATLAB_GREEN = "#77AC30"
MATLAB_CYAN = "#4DBEEE"
MATLAB_BURGUNDY = "#A2142F"
MATLAB_BG = "#FFFFFF"
MATLAB_GRID = "#E0E0E0"
MATLAB_AXIS = "#404040"

ALARM_ACCEL_HI = 8.0
ALARM_ACCEL_LO = -8.0
ALARM_GYRO_HI = 5.0
ALARM_GYRO_LO = -5.0
ALARM_SPEED_HI = 120
ALARM_SPEED_LO = 0
ALARM_WHEEL_HI = 450
ALARM_WHEEL_LO = -450

# 默认固定Y轴范围 — 标准模式
DEFAULT_AX_RANGE = (-4, 4)
DEFAULT_GYRO_RANGE = (-2, 2)
DEFAULT_SPEED_RANGE = (0, 150)
DEFAULT_WHEEL_RANGE = (-720, 720)

# 精密模式Y轴范围 — 参考脚本建议（座椅振动分析专用，适合已校准数据）
PRECISION_AX_RANGE = (-1.0, 1.0)
PRECISION_GYRO_RANGE = (-0.5, 0.5)

# 视窗时长选项
TIME_WINDOW_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]


class _RealtimeButterworth:
    """实时巴特沃斯低通滤波器 — 参考imu可视化数据曲线优化参考.py

    SAE J211-1 建议座椅振动分析使用 CFC 60 (截止频率 ~100Hz)，
    人体振动感知关注 0-10Hz，此处默认10Hz截止频率 + 2阶滤波。
    使用 sosfilt (因果) + SOS 二阶节实现实时流式处理，数值稳定性优于 ba 形式。
    """

    def __init__(self, cutoff=10.0, fs=100.0, order=2):
        self._cutoff = cutoff
        self._fs = fs
        self._order = order
        self._sos = None
        self._zi = None
        self._state = None
        self._init_filter()

    def _init_filter(self):
        from scipy.signal import butter, sosfilt_zi
        nyq = 0.5 * self._fs
        normal_cutoff = min(max(self._cutoff / nyq, 0.01), 0.99)
        self._sos = butter(self._order, normal_cutoff, btype='low', output='sos')
        self._zi = sosfilt_zi(self._sos)
        self._state = self._zi.copy()

    def filter(self, value):
        from scipy.signal import sosfilt
        filtered, self._state = sosfilt(self._sos, [float(value)], zi=self._state)
        return float(filtered[0])

    def reset(self):
        if self._zi is not None:
            self._state = self._zi.copy()

    def is_ready(self):
        return self._b is not None


def _filter_low_pass(value, prev, alpha=0.3):
    """简易EMA低通（保留兼容，推荐使用 _RealtimeButterworth）"""
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


class DownsampleMode(Enum):
    EXTREMA = "极值采样 (保留峰谷)"
    AVERAGE = "平均采样"
    MAX_POINTS = "最大点采样"


class SmoothMode(Enum):
    NONE = "无滤波"
    LOW_PASS = "低通滤波 (EMA)"
    BUTTERWORTH = "巴特沃斯低通"
    MOVING_AVG = "移动平均"
    SAVGOL = "Savitzky-Golay"


# S-G 系数缓存 — 避免重复计算 pinv
_sg_coeffs_cache: Dict[Tuple[int, int], List[float]] = {}


def _sg_coefficients(window_size=5, order=2):
    cache_key = (window_size, order)
    if cache_key in _sg_coeffs_cache:
        return _sg_coeffs_cache[cache_key]
    half = window_size // 2
    A = [[i ** j for j in range(order + 1)] for i in range(-half, half + 1)]
    import numpy as np
    A = np.array(A, dtype=float)
    coeffs = np.linalg.pinv(A)
    result = coeffs[0].tolist()
    _sg_coeffs_cache[cache_key] = result
    return result


def _apply_savgol(values, window_size=5, order=2):
    if len(values) < window_size:
        return values
    half = window_size // 2
    coeffs = _sg_coefficients(window_size, order)
    result = []
    for i in range(len(values)):
        if i < half:
            result.append(values[i])
        elif i >= len(values) - half:
            result.append(values[i])
        else:
            window = values[i - half:i + half + 1]
            smoothed = sum(c * w for c, w in zip(coeffs, window))
            result.append(smoothed)
    return result


def _apply_moving_avg(values, window_size=5):
    if len(values) < window_size:
        return values
    half = window_size // 2
    result = []
    for i in range(len(values)):
        if i < half:
            result.append(values[i])
        elif i >= len(values) - half:
            result.append(values[i])
        else:
            window = values[i - half:i + half + 1]
            result.append(sum(window) / window_size)
    return result


# ============================================================
# 专业数据点类
# ============================================================
class DataPoint:
    def __init__(self, t, v):
        self.t = t
        self.v = v


# ============================================================
# 分段极值采样核心算法
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
class IMUValueTile(QFrame):
    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._color = color
        self._value = 0
        self._history = deque(maxlen=10)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(56)
        self.setMinimumWidth(110)
        self.setStyleSheet(f"""
            IMUValueTile {{
                background-color: {CLR_PANEL};
                border: 1px solid {CLR_BORDER};
                border-radius: 5px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(1)

        header = QHBoxLayout()
        header.setSpacing(4)
        self._title_label = QLabel(self._title)
        self._title_label.setFont(QFont(FONT_FAMILY, 7, QFont.Bold))
        self._title_label.setStyleSheet(f"color: {self._color}; border: none; background: transparent;")
        header.addWidget(self._title_label)
        header.addStretch()
        self._trend_label = QLabel("")
        self._trend_label.setFont(QFont(FONT_FAMILY, 7))
        self._trend_label.setStyleSheet("border: none; background: transparent;")
        header.addWidget(self._trend_label)
        layout.addLayout(header)

        self._value_label = QLabel("---")
        self._value_label.setFont(QFont(FONT_MONO, 13, QFont.Bold))
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._value_label)

        self._unit_label = QLabel(self._unit)
        self._unit_label.setFont(QFont(FONT_FAMILY, 7))
        self._unit_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._unit_label)

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
            return "▲"
        if diff_pct < -5:
            return "▼"
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
            self._value_label.setText(f"{value:.2f}")
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


class IMUParameterTile(QFrame):
    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._color = color
        self._value = 0
        self._history = deque(maxlen=10)
        self._trend_data = deque(maxlen=120)
        self._trend_min = 0.0
        self._trend_max = 1.0
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(80)
        self.setMinimumWidth(110)
        self.setStyleSheet(f"""
            IMUParameterTile {{
                background-color: {CLR_PANEL};
                border: 1px solid {CLR_BORDER};
                border-radius: 5px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(1)

        header = QHBoxLayout()
        header.setSpacing(4)
        self._title_label = QLabel(self._title)
        self._title_label.setFont(QFont(FONT_FAMILY, 7, QFont.Bold))
        self._title_label.setStyleSheet(f"color: {self._color}; border: none; background: transparent;")
        header.addWidget(self._title_label)
        header.addStretch()
        self._trend_label = QLabel("")
        self._trend_label.setFont(QFont(FONT_FAMILY, 7))
        self._trend_label.setStyleSheet("border: none; background: transparent;")
        header.addWidget(self._trend_label)
        layout.addLayout(header)

        self._value_label = QLabel("---")
        self._value_label.setFont(QFont(FONT_MONO, 12, QFont.Bold))
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._value_label)

        self._unit_label = QLabel(self._unit)
        self._unit_label.setFont(QFont(FONT_FAMILY, 7))
        self._unit_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._unit_label)

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
            return "▲"
        if diff_pct < -5:
            return "▼"
        return ""

    def set_value(self, value, lo=None, hi=None):
        self._value = value
        if value is None or math.isnan(value) or math.isinf(value):
            self._value_label.setText("---")
            self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
            self._trend_label.setText("")
            return

        self._history.append(value)
        self._trend_data.append(value)
        arrow = self._trend_arrow(value)

        clr = self._alarm_color(value, lo, hi, self._color) if lo is not None and hi is not None else self._color

        if abs(value) < 10:
            self._value_label.setText(f"{value:.2f}")
        elif abs(value) < 100:
            self._value_label.setText(f"{value:.1f}")
        else:
            self._value_label.setText(f"{value:.0f}")

        self._value_label.setStyleSheet(f"color: {clr}; border: none; background: transparent;")
        self._trend_label.setText(arrow)
        self._trend_label.setStyleSheet(f"color: {clr}; border: none; background: transparent;")

        if len(self._trend_data) >= 2:
            vals = list(self._trend_data)
            self._trend_min = min(vals)
            self._trend_max = max(vals)
            if self._trend_max - self._trend_min < 1e-9:
                self._trend_max = self._trend_min + 1.0
        self.update()

    def reset(self):
        self._value = 0
        self._history.clear()
        self._trend_data.clear()
        self._value_label.setText("---")
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._trend_label.setText("")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if len(self._trend_data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        vals = list(self._trend_data)
        rng = self._trend_max - self._trend_min
        if rng < 1e-9:
            rng = 1.0

        margin_l = 4
        margin_r = 4
        plot_y_top = 20
        plot_y_bot = h - 16
        plot_w = w - margin_l - margin_r
        plot_h = plot_y_bot - plot_y_top

        path = QPainterPath()
        first = True
        for i, v in enumerate(vals):
            x = margin_l + plot_w * i / (len(vals) - 1)
            norm = (v - self._trend_min) / rng
            y = plot_y_bot - plot_h * norm
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(QColor(self._color), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if vals:
            last_x = margin_l + plot_w
            last_y = plot_y_bot - plot_h * ((vals[-1] - self._trend_min) / rng)
            painter.setBrush(QColor(self._color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(last_x, last_y), 2.5, 2.5)

        painter.end()


# ============================================================
# 专业波形通道组件 (含降采样核心)
# ============================================================
class IMUWaveformChannel(QWidget):
    def __init__(self, title, unit, y_range, series_config, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._fixed_y_lo, self._fixed_y_hi = y_range
        self._series_config = series_config
        self._buffers: Dict[str, deque] = {}
        self._filtered_buffers: Dict[str, deque] = {}
        self._raw_buffers: Dict[str, deque] = {}
        self._prev_filtered: Dict[str, float] = {}
        self._bw_filters: Dict[str, _RealtimeButterworth] = {}

        self._bias_offsets: Dict[str, float] = {}
        self._bias_samples: Dict[str, list] = {}
        self._bias_calibrated: Dict[str, bool] = {}
        self._bias_sample_count = 100
        self._calibration_enabled = False

        self._max_points = 2000
        self._render_points = 100
        self._frozen = False
        self._time_window = None  # None = 显示全部，非None = 只显示最近N秒
        self._event_range: Optional[Tuple[float, float]] = None  # 事件高亮区间

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
        self._smooth_mode = SmoothMode.LOW_PASS
        self._sg_window = 7
        self._ma_window = 5
        self._bw_cutoff = 10.0
        self._bw_fs = 100.0

        self._mouse_x = -1
        self._mouse_y = -1
        self._cursor_data = {}
        self.setMouseTracking(True)

        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def feed(self, series_name, value, t):
        if self._frozen:
            return
        if value is None:
            return
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return

        if (series_name not in self._buffers or
                series_name not in self._bias_offsets or
                series_name not in self._bias_samples or
                series_name not in self._bias_calibrated):
            self._buffers[series_name] = deque()  # 无maxlen，全量累积不释放
            self._filtered_buffers[series_name] = deque()
            self._raw_buffers[series_name] = deque(maxlen=self._sg_window * 2)
            self._prev_filtered[series_name] = None
            self._bias_samples[series_name] = []
            self._bias_calibrated[series_name] = False
            self._bias_offsets[series_name] = 0.0
            if self._smooth_mode == SmoothMode.BUTTERWORTH:
                self._bw_filters[series_name] = _RealtimeButterworth(
                    cutoff=self._bw_cutoff, fs=self._bw_fs)

        self._buffers[series_name].append(DataPoint(t, value))

        if self._calibration_enabled and not self._bias_calibrated[series_name]:
            self._bias_samples[series_name].append(value)
            if len(self._bias_samples[series_name]) >= self._bias_sample_count:
                self._bias_offsets[series_name] = sum(
                    self._bias_samples[series_name]) / len(self._bias_samples[series_name])
                self._bias_calibrated[series_name] = True
                self._bias_samples[series_name].clear()

        calibrated = value - self._bias_offsets[series_name]

        if self._smooth_mode == SmoothMode.NONE:
            filtered = calibrated
        elif self._smooth_mode == SmoothMode.BUTTERWORTH:
            bw = self._bw_filters.get(series_name)
            if bw and bw.is_ready():
                filtered = bw.filter(calibrated)
            else:
                filtered = calibrated
        elif self._smooth_mode == SmoothMode.LOW_PASS:
            filtered = _filter_low_pass(calibrated, self._prev_filtered[series_name], alpha=0.2)
        elif self._smooth_mode == SmoothMode.MOVING_AVG:
            self._raw_buffers[series_name].append(calibrated)
            window = list(self._raw_buffers[series_name])[-self._ma_window:]
            filtered = sum(window) / len(window)
        elif self._smooth_mode == SmoothMode.SAVGOL:
            self._raw_buffers[series_name].append(calibrated)
            window = list(self._raw_buffers[series_name])[-self._sg_window:]
            if len(window) >= self._sg_window:
                coeffs = _sg_coefficients(self._sg_window, 2)
                filtered = sum(c * w for c, w in zip(coeffs, window))
            else:
                filtered = calibrated
        else:
            filtered = calibrated

        self._filtered_buffers[series_name].append(DataPoint(t, filtered))
        self._prev_filtered[series_name] = filtered

    def feed_many(self, series_name, t_arr, v_arr):
        """批量喂入数据（numpy 数组），用于 SQLite 直读高速加载。
        t_arr: 1D numpy array of timestamps
        v_arr: 1D numpy array of values (same length as t_arr)
        """
        if self._frozen or t_arr is None or v_arr is None or len(t_arr) == 0:
            return

        # 初始化系列
        if (series_name not in self._buffers or
                series_name not in self._bias_offsets or
                series_name not in self._bias_samples or
                series_name not in self._bias_calibrated):
            self._buffers[series_name] = deque()  # 无maxlen，全量累积不释放
            self._filtered_buffers[series_name] = deque()
            self._raw_buffers[series_name] = deque(maxlen=self._sg_window * 2)
            self._prev_filtered[series_name] = None
            self._bias_samples[series_name] = []
            self._bias_calibrated[series_name] = False
            self._bias_offsets[series_name] = 0.0
            if self._smooth_mode == SmoothMode.BUTTERWORTH:
                self._bw_filters[series_name] = _RealtimeButterworth(
                    cutoff=self._bw_cutoff, fs=self._bw_fs)

        # 降采样：如果数据量超过显示容量，按步长抽取
        step = 1
        n = len(t_arr)
        if n > self._max_points:
            step = max(1, n // self._max_points)

        offset = self._bias_offsets[series_name]

        for i in range(0, n, step):
            t_val = float(t_arr[i])
            v_raw = float(v_arr[i])
            if math.isnan(v_raw) or math.isinf(v_raw):
                continue

            v_calib = v_raw - offset
            dp_raw = DataPoint(t_val, v_raw)

            # 简化滤波：批量加载用 low-pass，避免逐点 BW/SG 开销
            if self._smooth_mode == SmoothMode.NONE:
                filtered = v_calib
            elif self._smooth_mode == SmoothMode.LOW_PASS:
                filtered = _filter_low_pass(v_calib, self._prev_filtered[series_name], alpha=0.2)
            elif self._smooth_mode == SmoothMode.BUTTERWORTH:
                bw = self._bw_filters.get(series_name)
                if bw and bw.is_ready():
                    filtered = bw.filter(v_calib)
                else:
                    filtered = v_calib
            elif self._smooth_mode == SmoothMode.MOVING_AVG:
                self._raw_buffers[series_name].append(v_calib)
                window = list(self._raw_buffers[series_name])[-self._ma_window:]
                filtered = sum(window) / len(window)
            elif self._smooth_mode == SmoothMode.SAVGOL:
                self._raw_buffers[series_name].append(v_calib)
                window = list(self._raw_buffers[series_name])[-self._sg_window:]
                if len(window) >= self._sg_window:
                    coeffs = _sg_coefficients(self._sg_window, 2)
                    filtered = sum(c * w for c, w in zip(coeffs, window))
                else:
                    filtered = v_calib
            else:
                filtered = v_calib

            self._buffers[series_name].append(dp_raw)
            self._filtered_buffers[series_name].append(DataPoint(t_val, filtered))
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

    def set_time_window(self, seconds: Optional[float]):
        """设置 X 轴视窗时长（秒），None 表示显示全部"""
        self._time_window = seconds

    def set_event_range(self, start: Optional[float], end: Optional[float]):
        """设置事件高亮区间"""
        if start is not None and end is not None:
            self._event_range = (start, end)
        else:
            self._event_range = None

    def clear(self):
        self._buffers.clear()
        self._filtered_buffers.clear()
        self._raw_buffers.clear()
        self._prev_filtered.clear()
        self._bias_samples.clear()
        self._bias_calibrated.clear()
        self._bias_offsets.clear()
        for bw in self._bw_filters.values():
            bw.reset()
        self._bw_filters.clear()
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

    def set_smooth_mode(self, mode):
        self._smooth_mode = mode
        self._bw_filters.clear()

    def set_bw_cutoff(self, cutoff):
        self._bw_cutoff = cutoff
        self._bw_filters.clear()

    def set_bw_fs(self, fs):
        self._bw_fs = fs
        self._bw_filters.clear()

    def set_calibration_enabled(self, enabled):
        self._calibration_enabled = enabled
        if not enabled:
            # 不要完全清空字典，而是重置每个序列的偏移量为 0.0
            for series_name in self._bias_offsets:
                self._bias_offsets[series_name] = 0.0
            for series_name in self._bias_calibrated:
                self._bias_calibrated[series_name] = False
            self._bias_samples.clear()

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

    def mouseMoveEvent(self, event):
        self._mouse_x = event.position().x()
        self._mouse_y = event.position().y()
        self._compute_cursor_data()
        self.update()

    def leaveEvent(self, event):
        self._mouse_x = -1
        self._mouse_y = -1
        self._cursor_data.clear()
        self.update()

    def _compute_cursor_data(self):
        self._cursor_data.clear()
        ml, mt, mb, mr = 70, 22, 28, 12
        w, h = self.width(), self.height()
        pw = w - ml - mr
        ph = h - mt - mb

        if self._mouse_x < ml or self._mouse_x > ml + pw:
            return

        y_lo = self._y_lo
        y_hi = self._y_hi
        if abs(y_hi - y_lo) < 1e-9:
            return

        t_norm = (self._mouse_x - ml) / pw
        y_norm = 1.0 - (self._mouse_y - mt) / ph
        cursor_val = y_lo + y_norm * (y_hi - y_lo)

        for name in self._series_config:
            buf = self._filtered_buffers.get(name, deque())
            if len(buf) < 2:
                continue
            vals = list(buf)
            t_min = vals[0].t
            t_max = vals[-1].t
            if t_max - t_min < 1e-9:
                continue
            cursor_t = t_min + t_norm * (t_max - t_min)
            nearest = min(vals, key=lambda dp: abs(dp.t - cursor_t))
            self._cursor_data[name] = (nearest.t, nearest.v)

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
        self._draw_cursor(painter, ml, mt, pw, ph)
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

        # 计算全局时间范围（用于事件高亮和视窗裁剪）
        all_t_min = None
        all_t_max = None
        for name, cfg in self._series_config.items():
            buf = self._filtered_buffers.get(name, deque())
            if len(buf) >= 2:
                vals = list(buf)
                if all_t_min is None or vals[0].t < all_t_min:
                    all_t_min = vals[0].t
                if all_t_max is None or vals[-1].t > all_t_max:
                    all_t_max = vals[-1].t

        if all_t_min is None or all_t_max is None:
            return

        if all_t_max - all_t_min < 1e-9:
            all_t_max = all_t_min + 1.0

        # 视窗裁剪：左边界 = 最新时间 - 视窗时长
        if self._time_window and self._time_window > 0:
            view_t_min = all_t_max - self._time_window
        else:
            view_t_min = all_t_min

        view_t_max = all_t_max

        # ── 事件高亮区间 ──
        if self._event_range:
            ev_start, ev_end = self._event_range
            if ev_end > view_t_min and ev_start < view_t_max:
                x1 = ml + pw * max(0, (ev_start - view_t_min) / (view_t_max - view_t_min))
                x2 = ml + pw * min(1, (ev_end - view_t_min) / (view_t_max - view_t_min))
                highlight = QColor("#00b8d4")
                highlight.setAlpha(20)
                painter.fillRect(QRectF(x1, mt, x2 - x1, ph), highlight)

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

            # 过滤视窗内数据
            viewport = [dp for dp in downsampled if dp.t >= view_t_min]
            if len(viewport) < 2:
                continue

            path = QPainterPath()
            fill_path = QPainterPath()
            first = True
            peak_points = []

            for i, dp in enumerate(viewport):
                t_norm = (dp.t - view_t_min) / (view_t_max - view_t_min)
                x = ml + pw * t_norm
                y_norm = (dp.v - y_lo) / (y_hi - y_lo)
                y_norm = max(0.0, min(1.0, y_norm))
                y = mt + ph * (1.0 - y_norm)

                if first:
                    path.moveTo(x, y)
                    fill_path.moveTo(x, mt + ph)
                    fill_path.lineTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
                    fill_path.lineTo(x, y)

                if self._show_peaks and (i % 20 == 0 or i == len(viewport) - 1 or i == 0):
                    peak_points.append((x, y))

            last_x = ml + pw
            fill_path.lineTo(last_x, mt + ph)
            fill_path.closeSubpath()

            fill_color = QColor(color)
            fill_color.setAlpha(30)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_color)
            painter.drawPath(fill_path)

            painter.setPen(QPen(color, width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
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
        painter.setFont(QFont(FONT_FAMILY, 7))
        for i in range(5):
            y = mt + int(ph * i / 4)
            val = y_hi - (y_hi - y_lo) * i / 4
            painter.drawText(QRectF(2, y - 8, ml - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{val:.1f}")

        painter.setPen(QColor(CLR_ACCENT))
        painter.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
        mode_tag = " [AUTO]" if self._auto_range else ""
        painter.drawText(QRectF(ml + 4, mt - 2, 200, 16), Qt.AlignLeft | Qt.AlignVCenter, self._title + mode_tag)

        legend_x = ml + pw - 120
        legend_y = mt + 2
        for name, cfg in self._series_config.items():
            color = QColor(cfg.get('color', CLR_TEXT))
            painter.setPen(color)
            painter.setBrush(color)
            painter.drawRect(int(legend_x), int(legend_y + 2), 10, 4)
            painter.drawText(QRectF(legend_x + 16, legend_y, 60, 12), Qt.AlignLeft, name)
            legend_x += 40

        if self._buffers:
            first_name = list(self._buffers.keys())[0]
            buf = self._buffers.get(first_name, deque())
            if len(buf) > 1:
                data_points = len(buf)
                ds_points = min(self._render_points, data_points)
                painter.setPen(QColor(CLR_TEXT_DIM))
                painter.drawText(QRectF(ml + 4, mt + ph + 4, 200, 20), Qt.AlignLeft,
                               f"{data_points} pts → {ds_points} pts  |  {self._downsample_mode.value}")

    def _draw_cursor(self, painter, ml, mt, pw, ph):
        if self._mouse_x < 0 or not self._cursor_data:
            return
        if self._mouse_x < ml or self._mouse_x > ml + pw:
            return

        mx = int(self._mouse_x)
        my = int(self._mouse_y)

        painter.setPen(QPen(QColor("#80ffffff"), 1, Qt.DashLine))
        painter.drawLine(mx, mt, mx, mt + ph)
        painter.drawLine(ml, my, ml + pw, my)

        y_lo = self._y_lo
        y_hi = self._y_hi
        if abs(y_hi - y_lo) < 1e-9:
            return

        y_norm = 1.0 - (my - mt) / ph
        cursor_y_val = y_lo + y_norm * (y_hi - y_lo)

        lines = []
        for name, (t_val, v_val) in self._cursor_data.items():
            cfg = self._series_config.get(name, {})
            color = cfg.get('color', CLR_TEXT)
            lines.append((name, t_val, v_val, color))

        if not lines:
            return

        font = QFont(FONT_MONO, 8)
        painter.setFont(font)
        line_h = 16
        padding = 6
        max_w = 0
        for name, t_val, v_val, _ in lines:
            text = f"{name}: {v_val:.3f} {self._unit}"
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text)
            if tw > max_w:
                max_w = tw
        box_w = max_w + padding * 2
        box_h = len(lines) * line_h + padding * 2 + 4

        box_x = mx + 14
        box_y = my - box_h - 8
        if box_x + box_w > self.width():
            box_x = mx - box_w - 14
        if box_y < 0:
            box_y = my + 14

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 24, 32, 220))
        painter.drawRoundedRect(int(box_x), int(box_y), int(box_w), int(box_h), 4, 4)
        painter.setPen(QColor(CLR_BORDER))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(int(box_x), int(box_y), int(box_w), int(box_h), 4, 4)

        for i, (name, t_val, v_val, color) in enumerate(lines):
            ty = box_y + padding + i * line_h
            painter.setPen(QColor(color))
            painter.drawText(QRectF(box_x + padding, ty, box_w - padding * 2, line_h),
                           Qt.AlignLeft, f"{name}: {v_val:.3f}")

        t_text = f"t={lines[0][1]:.3f}s"
        painter.setPen(QColor(CLR_TEXT_DIM))
        painter.drawText(QRectF(box_x + padding, box_y + padding + len(lines) * line_h,
                               box_w - padding * 2, line_h), Qt.AlignLeft, t_text)


# ============================================================
# 主专业IMU可视化Tab
# ============================================================
class IMUVisualizationTab(QWidget):
    data_received = Signal(dict)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._init_data()
        self._init_ui()
        self._init_timers()
        self.logger.info("IMU 专业可视化 v2.0 初始化完成")

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
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        top_bar = QWidget()
        top_bar.setStyleSheet(f"background-color: {CLR_BG};")
        top_ctrl = QHBoxLayout(top_bar)
        top_ctrl.setContentsMargins(10, 8, 10, 4)

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont(FONT_FAMILY, 10))
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")
        top_ctrl.addWidget(self.status_label)

        top_ctrl.addStretch()

        top_ctrl.addWidget(QLabel(" 视窗时长:"))
        self.time_window_combo = QComboBox()
        for t in TIME_WINDOW_OPTIONS:
            self.time_window_combo.addItem(f"{t:.1f} s", t)
        self.time_window_combo.setCurrentIndex(3)
        self.time_window_combo.setStyleSheet(self._combo_style())
        self.time_window_combo.currentIndexChanged.connect(self._on_time_window_changed)
        top_ctrl.addWidget(self.time_window_combo)

        top_ctrl.addWidget(QLabel(" 播放速度:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x", "20x", "50x"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.setStyleSheet(self._combo_style())
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        top_ctrl.addWidget(self.speed_combo)

        top_ctrl.addWidget(QLabel(" 滤波:"))
        self.smooth_combo = QComboBox()
        for mode in SmoothMode:
            self.smooth_combo.addItem(mode.value, mode)
        self.smooth_combo.setCurrentIndex(1)
        self.smooth_combo.setStyleSheet(self._combo_style())
        self.smooth_combo.currentIndexChanged.connect(self._on_smooth_changed)
        top_ctrl.addWidget(self.smooth_combo)

        top_ctrl.addStretch()

        self.calib_btn = QPushButton("🎯 零偏校准: OFF")
        self.calib_btn.setCheckable(True)
        self.calib_btn.setChecked(False)
        self.calib_btn.setStyleSheet(self._btn_style())
        self.calib_btn.clicked.connect(self._toggle_calibration)
        top_ctrl.addWidget(self.calib_btn)

        self.precision_btn = QPushButton("🔬 精密Y轴: OFF")
        self.precision_btn.setCheckable(True)
        self.precision_btn.setChecked(False)
        self.precision_btn.setStyleSheet(self._btn_style())
        self.precision_btn.clicked.connect(self._toggle_precision)
        top_ctrl.addWidget(self.precision_btn)

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

        root.addWidget(top_bar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(f"QScrollArea {{ background-color: {CLR_BG}; border: none; }}")

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {CLR_BG};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 8, 10, 4)
        content_layout.setSpacing(6)

        value_grid = QHBoxLayout()
        value_grid.setSpacing(4)
        value_params = [
            ("AX 纵向加速", "m/s²", CLR_AX, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("AY 横向加速", "m/s²", CLR_AY, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("AZ 垂向加速", "m/s²", CLR_AZ, ALARM_ACCEL_LO, ALARM_ACCEL_HI),
            ("Speed 车速", "km/h", CLR_SPEED, ALARM_SPEED_LO, ALARM_SPEED_HI),
            ("Wheel 转向角", "°", CLR_WHEEL, ALARM_WHEEL_LO, ALARM_WHEEL_HI),
            ("GX 横滚角速", "rad/s", CLR_GX, ALARM_GYRO_LO, ALARM_GYRO_HI),
            ("GY 俯仰角速", "rad/s", CLR_GY, ALARM_GYRO_LO, ALARM_GYRO_HI),
            ("GZ 偏航角速", "rad/s", CLR_GZ, ALARM_GYRO_LO, ALARM_GYRO_HI),
        ]
        self.value_tiles = {}
        for title, unit, color, lo, hi in value_params:
            key = title.split()[0]
            tile = IMUValueTile(title, unit, color)
            self.value_tiles[key] = (tile, lo, hi)
            value_grid.addWidget(tile)
        content_layout.addLayout(value_grid)

        self.channel_accel = IMUWaveformChannel(
            "加速度", "m/s²", DEFAULT_AX_RANGE,
            {"AX": {"color": CLR_AX, "width": 1.5},
             "AY": {"color": CLR_AY, "width": 1.5},
             "AZ": {"color": CLR_AZ, "width": 1.5}}
        )
        self.channel_accel._downsample_mode = DownsampleMode.EXTREMA
        self.channel_accel.setMinimumHeight(150)
        content_layout.addWidget(self.channel_accel)

        self.channel_gyro = IMUWaveformChannel(
            "角速度", "rad/s", DEFAULT_GYRO_RANGE,
            {"GX": {"color": CLR_GX, "width": 1.5},
             "GY": {"color": CLR_GY, "width": 1.5},
             "GZ": {"color": CLR_GZ, "width": 1.5}}
        )
        self.channel_gyro._downsample_mode = DownsampleMode.EXTREMA
        self.channel_gyro.setMinimumHeight(150)
        content_layout.addWidget(self.channel_gyro)

        self.channel_vehicle = IMUWaveformChannel(
            "车速", "km/h", DEFAULT_SPEED_RANGE,
            {"Speed": {"color": CLR_SPEED, "width": 1.8}}
        )
        self.channel_vehicle._downsample_mode = DownsampleMode.EXTREMA
        self.channel_vehicle.setMinimumHeight(150)
        content_layout.addWidget(self.channel_vehicle)

        self.channel_wheel = IMUWaveformChannel(
            "方向盘转向角", "°", DEFAULT_WHEEL_RANGE,
            {"Wheel": {"color": CLR_WHEEL, "width": 1.8}}
        )
        self.channel_wheel._downsample_mode = DownsampleMode.EXTREMA
        self.channel_wheel.setMinimumHeight(150)
        content_layout.addWidget(self.channel_wheel)

        content_layout.addStretch()

        # ── 趋势通道：每个参数单独一行，视窗固定60秒 ──
        self.trend_channel_ax = IMUWaveformChannel(
            "AX 纵向加速度", "m/s²", DEFAULT_AX_RANGE,
            {"AX": {"color": CLR_AX, "width": 1.5}}
        )
        self.trend_channel_ax.set_time_window(60.0)
        self.trend_channel_ax.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_ax)

        self.trend_channel_ay = IMUWaveformChannel(
            "AY 横向加速度", "m/s²", DEFAULT_AX_RANGE,
            {"AY": {"color": CLR_AY, "width": 1.5}}
        )
        self.trend_channel_ay.set_time_window(60.0)
        self.trend_channel_ay.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_ay)

        self.trend_channel_az = IMUWaveformChannel(
            "AZ 垂向加速度", "m/s²", DEFAULT_AX_RANGE,
            {"AZ": {"color": CLR_AZ, "width": 1.5}}
        )
        self.trend_channel_az.set_time_window(60.0)
        self.trend_channel_az.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_az)

        self.trend_channel_speed = IMUWaveformChannel(
            "车速", "km/h", DEFAULT_SPEED_RANGE,
            {"Speed": {"color": CLR_SPEED, "width": 1.8}}
        )
        self.trend_channel_speed.set_time_window(60.0)
        self.trend_channel_speed.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_speed)

        self.trend_channel_wheel = IMUWaveformChannel(
            "方向盘转向角", "°", DEFAULT_WHEEL_RANGE,
            {"Wheel": {"color": CLR_WHEEL, "width": 1.8}}
        )
        self.trend_channel_wheel.set_time_window(60.0)
        self.trend_channel_wheel.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_wheel)

        self.trend_channel_gx = IMUWaveformChannel(
            "GX 横滚角速度", "rad/s", DEFAULT_GYRO_RANGE,
            {"GX": {"color": CLR_GX, "width": 1.5}}
        )
        self.trend_channel_gx.set_time_window(60.0)
        self.trend_channel_gx.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_gx)

        self.trend_channel_gy = IMUWaveformChannel(
            "GY 俯仰角速度", "rad/s", DEFAULT_GYRO_RANGE,
            {"GY": {"color": CLR_GY, "width": 1.5}}
        )
        self.trend_channel_gy.set_time_window(60.0)
        self.trend_channel_gy.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_gy)

        self.trend_channel_gz = IMUWaveformChannel(
            "GZ 偏航角速度", "rad/s", DEFAULT_GYRO_RANGE,
            {"GZ": {"color": CLR_GZ, "width": 1.5}}
        )
        self.trend_channel_gz.set_time_window(60.0)
        self.trend_channel_gz.setMinimumHeight(100)
        content_layout.addWidget(self.trend_channel_gz)

        scroll_area.setWidget(content_widget)
        root.addWidget(scroll_area, stretch=1)

        info_bar_widget = QWidget()
        info_bar_widget.setStyleSheet(f"background-color: {CLR_BG};")
        info_bar = QHBoxLayout(info_bar_widget)
        info_bar.setContentsMargins(10, 4, 10, 6)
        info_bar.setSpacing(16)
        self.lbl_samples = QLabel("样本: 0")
        self.lbl_fps = QLabel("FPS: 0")
        self.lbl_time = QLabel("时间窗口: 5.0 s")
        for lbl in [self.lbl_samples, self.lbl_fps, self.lbl_time]:
            lbl.setFont(QFont(FONT_FAMILY, 8))
            lbl.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")
            info_bar.addWidget(lbl)
        info_bar.addStretch()
        root.addWidget(info_bar_widget)

    def _btn_style(self):
        return f"""
            QPushButton {{
                background-color: {CLR_PANEL};
                color: {CLR_ACCENT};
                border: 1px solid {CLR_BORDER};
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #1a2a38; }}
            QPushButton:checked {{ background-color: #ffc107; color: #000; }}
        """

    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {CLR_PANEL};
                color: {CLR_ACCENT};
                border: 1px solid {CLR_BORDER};
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 9pt;
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
        if not getattr(self, 'value_tiles', None):
            return
        if self.freeze_btn.isChecked():
            return
        
        # 检查是否有数据要处理
        if not self._ring_buffer:
            return
        
        # 如果缓冲区有数据但 is_running 是 False，自动启动
        if not self.is_running:
            self.start()
        
        # 处理一批数据
        batch = []
        for _ in range(min(len(self._ring_buffer), 100)):
            batch.append(self._ring_buffer.popleft())
        
        # 应用每一条记录
        for record in batch:
            self._apply_record(record)
        
        # 总是 flush 所有通道，确保曲线刷新
        self.channel_accel.flush()
        self.channel_gyro.flush()
        self.channel_vehicle.flush()
        self.channel_wheel.flush()
        # 趋势通道
        if hasattr(self, 'trend_channel_ax'):
            self.trend_channel_ax.flush()
            self.trend_channel_ay.flush()
            self.trend_channel_az.flush()
            self.trend_channel_speed.flush()
            self.trend_channel_wheel.flush()
            self.trend_channel_gx.flush()
            self.trend_channel_gy.flush()
            self.trend_channel_gz.flush()
        
        self._fps_counter += 1

    def _apply_record(self, record):
        if not isinstance(record, dict):
            return
        if not getattr(self, 'value_tiles', None):
            return

        t = record.get('t', record.get('timestamp', 0.0))
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

        t_rel = t  # 使用记录中的真实时间戳，支持"右进左停"视窗裁剪

        self._sample_count += 1

        tile_ax, lo_ax, hi_ax = self.value_tiles['AX']
        tile_ax.set_value(ax, lo_ax, hi_ax)
        tile_ay, lo_ay, hi_ay = self.value_tiles['AY']
        tile_ay.set_value(ay, lo_ay, hi_ay)
        tile_az, lo_az, hi_az = self.value_tiles['AZ']
        tile_az.set_value(az, lo_az, hi_az)

        tile_speed, lo_sp, hi_sp = self.value_tiles['Speed']
        tile_speed.set_value(speed, lo_sp, hi_sp)
        tile_wheel, lo_wh, hi_wh = self.value_tiles['Wheel']
        tile_wheel.set_value(wheel, lo_wh, hi_wh)

        tile_gx, lo_gx, hi_gx = self.value_tiles['GX']
        tile_gx.set_value(gx, lo_gx, hi_gx)
        tile_gy, lo_gy, hi_gy = self.value_tiles['GY']
        tile_gy.set_value(gy, lo_gy, hi_gy)
        tile_gz, lo_gz, hi_gz = self.value_tiles['GZ']
        tile_gz.set_value(gz, lo_gz, hi_gz)

        # 趋势通道（每参数独立一行，60秒视窗）
        if hasattr(self, 'trend_channel_ax'):
            if ax is not None:
                self.trend_channel_ax.feed("AX", ax, t_rel)
            if ay is not None:
                self.trend_channel_ay.feed("AY", ay, t_rel)
            if az is not None:
                self.trend_channel_az.feed("AZ", az, t_rel)
            if speed is not None:
                self.trend_channel_speed.feed("Speed", speed, t_rel)
            if wheel is not None:
                self.trend_channel_wheel.feed("Wheel", wheel, t_rel)
            if gx is not None:
                self.trend_channel_gx.feed("GX", gx, t_rel)
            if gy is not None:
                self.trend_channel_gy.feed("GY", gy, t_rel)
            if gz is not None:
                self.trend_channel_gz.feed("GZ", gz, t_rel)

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
        self.status_label.setStyleSheet(f"color: {CLR_OK}; background: transparent;")
        self._start_time = None

    def stop(self):
        self.is_running = False
        self._loaded_from_cache = False  # 重置标记，下次可重新加载
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")

    def set_data_bridge(self, data_bridge):
        self.data_bridge = data_bridge
        self.logger.info("IMU 已连接 DataBridge")

    def receive_imu_data(self, sensor_data):
        """接收逐条 IMU 数据（实时模式）。若已从 SQLite 直读加载，则跳过。"""
        if getattr(self, '_loaded_from_cache', False):
            return

        # 确保数据同时有 t 和 timestamp 字段
        sensor_data = dict(sensor_data)
        if 't' not in sensor_data and 'timestamp' in sensor_data:
            sensor_data['t'] = sensor_data['timestamp']
        if 'timestamp' not in sensor_data and 't' in sensor_data:
            sensor_data['timestamp'] = sensor_data['t']
        
        # 总是往缓冲区里加数据，不管 is_running（render_loop自己会检查）
        self._ring_buffer.append(sensor_data)
        
        # 如果 is_running 是 False，但我们收到了数据，自动启动
        if not self.is_running:
            self.start()

    # ─────────── SQLite 直读：一键加载全量数据（替代逐条信号）───────────

    def load_from_cache(self, multi_source_cache, start: float = None, end: float = None):
        """从 MultiSourceCache SQLite 直读全量 IMU 数据，一次性加载到通道。
        替代逐条 receive_imu_data → ring_buffer → _apply_record 的低效路径。
        106k 记录从 30 分钟 → 2-5 秒。
        """
        if multi_source_cache is None:
            self.logger.warning("load_from_cache: multi_source_cache is None")
            return

        t0 = time.time()

        # 1. SQLite 直读 → numpy 数组（绕过 json.loads × N）
        t_arr, ax_arr, ay_arr, az_arr, gx_arr, gy_arr, gz_arr, speed_arr, wheel_arr = \
            multi_source_cache.query_imu_numpy(start, end)

        n = len(t_arr)
        if n == 0:
            self.logger.warning("load_from_cache: 查询结果为空")
            return

        self.logger.info(f"load_from_cache: 查询到 {n} 条记录，开始批量喂入...")

        # 2. 清空旧数据
        self.channel_accel.clear()
        self.channel_gyro.clear()
        self.channel_vehicle.clear()
        self.channel_wheel.clear()
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.clear()
        self._sample_count = n

        # 3. 批量喂入各通道（feed_many 内部有降采样）
        self.channel_accel.feed_many("AX", t_arr, ax_arr)
        self.channel_accel.feed_many("AY", t_arr, ay_arr)
        self.channel_accel.feed_many("AZ", t_arr, az_arr)

        self.channel_gyro.feed_many("GX", t_arr, gx_arr)
        self.channel_gyro.feed_many("GY", t_arr, gy_arr)
        self.channel_gyro.feed_many("GZ", t_arr, gz_arr)

        self.channel_vehicle.feed_many("Speed", t_arr, speed_arr)

        self.channel_wheel.feed_many("Wheel", t_arr, wheel_arr)

        # 趋势通道（每参数独立一行）
        if hasattr(self, 'trend_channel_ax'):
            self.trend_channel_ax.feed_many("AX", t_arr, ax_arr)
            self.trend_channel_ay.feed_many("AY", t_arr, ay_arr)
            self.trend_channel_az.feed_many("AZ", t_arr, az_arr)
            self.trend_channel_speed.feed_many("Speed", t_arr, speed_arr)
            self.trend_channel_wheel.feed_many("Wheel", t_arr, wheel_arr)
            self.trend_channel_gx.feed_many("GX", t_arr, gx_arr)
            self.trend_channel_gy.feed_many("GY", t_arr, gy_arr)
            self.trend_channel_gz.feed_many("GZ", t_arr, gz_arr)

        # 4. 一次性 flush
        self.channel_accel.flush()
        self.channel_gyro.flush()
        self.channel_vehicle.flush()
        self.channel_wheel.flush()
        # 趋势通道
        if hasattr(self, 'trend_channel_ax'):
            self.trend_channel_ax.flush()
            self.trend_channel_ay.flush()
            self.trend_channel_az.flush()
            self.trend_channel_speed.flush()
            self.trend_channel_wheel.flush()
            self.trend_channel_gx.flush()
            self.trend_channel_gy.flush()
            self.trend_channel_gz.flush()

        elapsed = time.time() - t0
        self._start_time = t_arr[0]
        self.is_running = True
        self._loaded_from_cache = True  # 标记已加载，阻止 receive_imu_data 重复加载
        self.status_label.setText(f"已加载 {n} 条 ({elapsed:.1f}s)")
        self.status_label.setStyleSheet(f"color: {CLR_OK}; background: transparent;")
        self.logger.info(f"load_from_cache 完成: {n} 条记录, 耗时 {elapsed:.2f}s")

    def _toggle_freeze(self, checked):
        self.channel_accel.set_frozen(checked)
        self.channel_gyro.set_frozen(checked)
        self.channel_vehicle.set_frozen(checked)
        self.channel_wheel.set_frozen(checked)
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_frozen(checked)
        self.status_label.setText("已冻结" if checked else "运行中")

    def _toggle_auto_range(self, checked):
        self.channel_accel.set_auto_range(checked)
        self.channel_gyro.set_auto_range(checked)
        self.channel_vehicle.set_auto_range(checked)
        self.channel_wheel.set_auto_range(checked)
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_auto_range(checked)
        self.auto_range_btn.setText("📐 自适应Y轴: ON" if checked else "📐 自适应Y轴: OFF")
        self.logger.info(f"IMU 自适应Y轴: {'启用' if checked else '禁用'}")

    def _toggle_peaks(self, checked):
        self.channel_accel.set_show_peaks(checked)
        self.channel_gyro.set_show_peaks(checked)
        self.channel_vehicle.set_show_peaks(checked)
        self.channel_wheel.set_show_peaks(checked)
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_show_peaks(checked)
        self.peaks_btn.setText("⚡ 显示峰值: ON" if checked else "⚡ 显示峰值: OFF")
        self.logger.info(f"IMU 峰值显示: {'启用' if checked else '禁用'}")

    def _toggle_calibration(self, checked):
        self.channel_accel.set_calibration_enabled(checked)
        self.channel_gyro.set_calibration_enabled(checked)
        self.channel_vehicle.set_calibration_enabled(checked)
        self.channel_wheel.set_calibration_enabled(checked)
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_calibration_enabled(checked)
        self.calib_btn.setText("🎯 零偏校准: ON" if checked else "🎯 零偏校准: OFF")
        self.logger.info(f"IMU 零偏校准: {'启用' if checked else '禁用'} (采集{self.channel_accel._bias_sample_count}样本计算均值)")

    def _toggle_precision(self, checked):
        if checked:
            self.channel_accel.set_y_range(*PRECISION_AX_RANGE)
            self.channel_gyro.set_y_range(*PRECISION_GYRO_RANGE)
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az]:
                ch.set_y_range(*PRECISION_AX_RANGE)
            for ch in [self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_y_range(*PRECISION_GYRO_RANGE)
        else:
            self.channel_accel.set_y_range(*DEFAULT_AX_RANGE)
            self.channel_gyro.set_y_range(*DEFAULT_GYRO_RANGE)
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az]:
                ch.set_y_range(*DEFAULT_AX_RANGE)
            for ch in [self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_y_range(*DEFAULT_GYRO_RANGE)
        self.precision_btn.setText("🔬 精密Y轴: ON" if checked else "🔬 精密Y轴: OFF")
        self.logger.info(f"IMU 精密Y轴: {'启用 AX=±1.0 GYRO=±0.5' if checked else '禁用 (恢复默认)'}")

    def _on_clear(self):
        self._sample_count = 0
        self._start_time = None
        self._ring_buffer.clear()
        self.channel_accel.clear()
        self.channel_gyro.clear()
        self.channel_vehicle.clear()
        self.channel_wheel.clear()
        self.calib_btn.setChecked(False)
        self.calib_btn.setText("🎯 零偏校准: OFF")
        self.precision_btn.setChecked(False)
        self.precision_btn.setText("🔬 精密Y轴: OFF")
        if hasattr(self, 'value_tiles') and self.value_tiles:
            for key in self.value_tiles:
                tile, _, _ = self.value_tiles[key]
                tile.reset()
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.clear()
        self.lbl_samples.setText("样本: 0")
        self.lbl_fps.setText("FPS: 0")
        self.logger.info("IMU 可视化已清除")

    def _on_time_window_changed(self, idx):
        t = self.time_window_combo.itemData(idx)
        self._time_window = t
        self.lbl_time.setText(f"时间窗口: {t:.1f} s")
        # 同步视窗到所有波形通道，实现"右进左停"
        for ch in [self.channel_accel, self.channel_gyro, self.channel_vehicle, self.channel_wheel]:
            ch.set_time_window(t)
        self.logger.info(f"IMU 时间窗口切换为: {t:.1f} s")

    def _on_speed_changed(self, text):
        multiplier = float(text.replace("x", ""))
        self.logger.info(f"IMU 播放速度切换为: {multiplier}x")
        if self.data_bridge:
            try:
                from modules.ui.left_control_panel.utils.data_reader_manager import get_data_reader_manager
                mgr = get_data_reader_manager()
                if mgr:
                    mgr.set_playback_speed(multiplier)
            except Exception as e:
                self.logger.warning(f"设置速度倍率失败: {e}")

    def _on_smooth_changed(self, idx):
        mode = self.smooth_combo.itemData(idx)
        self.channel_accel.set_smooth_mode(mode)
        self.channel_gyro.set_smooth_mode(mode)
        self.channel_vehicle.set_smooth_mode(mode)
        self.channel_wheel.set_smooth_mode(mode)
        if hasattr(self, 'trend_channel_ax'):
            for ch in [self.trend_channel_ax, self.trend_channel_ay, self.trend_channel_az,
                        self.trend_channel_speed, self.trend_channel_wheel,
                        self.trend_channel_gx, self.trend_channel_gy, self.trend_channel_gz]:
                ch.set_smooth_mode(mode)
        self.logger.info(f"IMU 滤波模式切换为: {mode.value}")

    def set_replay_mode(self, enabled):
        """设置回放模式，确保所有控件保持可用状态"""
        self.logger.info(f"IMU 可视化: 已切换到{'回放' if enabled else '实时'}模式")
        # 确保所有控件不被禁用，保持可交互状态
        if hasattr(self, 'time_window_combo'):
            self.time_window_combo.setEnabled(True)
        if hasattr(self, 'speed_combo'):
            self.speed_combo.setEnabled(True)
        if hasattr(self, 'smooth_combo'):
            self.smooth_combo.setEnabled(True)
        if hasattr(self, 'calib_btn'):
            self.calib_btn.setEnabled(True)
        if hasattr(self, 'precision_btn'):
            self.precision_btn.setEnabled(True)
        if hasattr(self, 'auto_range_btn'):
            self.auto_range_btn.setEnabled(True)
        if hasattr(self, 'peaks_btn'):
            self.peaks_btn.setEnabled(True)
        if hasattr(self, 'freeze_btn'):
            self.freeze_btn.setEnabled(True)
        if hasattr(self, 'clear_btn'):
            self.clear_btn.setEnabled(True)
