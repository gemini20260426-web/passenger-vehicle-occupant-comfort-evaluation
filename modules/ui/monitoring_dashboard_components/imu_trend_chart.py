#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 页脚趋势图组件 — 全量显示，左滚不释放，回放完成后展示事件全量曲线

功能：
- 回放过程中：接收IMU数据，全量累积显示，X轴从左到右滚动不释放旧数据
- 回放完成后：加载事件全量数据，展示完整趋势曲线并高亮事件区间
- 8通道：AX/AY/AZ/GX/GY/GZ/Speed/Wheel
"""

import logging
import math
from collections import deque
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QFont, QColor, QPainter, QPen, QBrush, QPainterPath)

from .imu_visualization_tab import (
    DataPoint, ExtremaDownsampler, DownsampleMode,
    FONT_FAMILY, FONT_MONO,
    CLR_BG, CLR_PANEL, CLR_BORDER, CLR_GRID_MAJOR, CLR_GRID_MINOR,
    CLR_TEXT, CLR_TEXT_DIM, CLR_ACCENT,
    CLR_AX, CLR_AY, CLR_AZ, CLR_GX, CLR_GY, CLR_GZ, CLR_SPEED, CLR_WHEEL,
)

logger = logging.getLogger(__name__)

# ── 趋势图通道配置 ──
TREND_CHANNELS = [
    ("AX",  "m/s²",  CLR_AX),
    ("AY",  "m/s²",  CLR_AY),
    ("AZ",  "m/s²",  CLR_AZ),
    ("GX",  "rad/s", CLR_GX),
    ("GY",  "rad/s", CLR_GY),
    ("GZ",  "rad/s", CLR_GZ),
    ("Spd", "km/h",  CLR_SPEED),
    ("Whl", "°",     CLR_WHEEL),
]

# 默认Y轴范围
DEFAULT_Y_RANGES = {
    "AX":  (-4, 4), "AY":  (-4, 4), "AZ":  (-4, 4),
    "GX":  (-2, 2), "GY":  (-2, 2), "GZ":  (-2, 2),
    "Spd": (0, 150), "Whl": (-720, 720),
}


class IMUTrendChart(QWidget):
    """IMU 页脚趋势图 — 全量累积显示，8通道独立Y轴"""

    # 单通道最小高度
    ROW_HEIGHT = 72
    # 左侧Y轴标签宽度
    LABEL_WIDTH = 48
    # 右侧边距
    RIGHT_MARGIN = 8
    # 顶部边距
    TOP_MARGIN = 4
    # 底部边距（X轴时间标签）
    BOTTOM_MARGIN = 18
    # 渲染降采样目标点数
    RENDER_POINTS = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # 数据缓冲区：无maxlen，全量累积
        self._buffers: Dict[str, deque] = {}
        for name, _, _ in TREND_CHANNELS:
            self._buffers[name] = deque()

        # 事件高亮区间
        self._event_range: Optional[Tuple[float, float]] = None

        # Y轴自适应范围
        self._auto_y_ranges: Dict[str, Tuple[float, float]] = {}
        for name, _, _ in TREND_CHANNELS:
            lo, hi = DEFAULT_Y_RANGES.get(name, (-4, 4))
            self._auto_y_ranges[name] = [lo, hi]

        self._auto_range_enabled = True
        self._frozen = False
        self._sample_count = 0

        self.setMinimumHeight(self.ROW_HEIGHT * len(TREND_CHANNELS) + self.TOP_MARGIN + self.BOTTOM_MARGIN)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ─── 公共接口 ─────────────────────────────────────────────

    def feed(self, channel: str, t: float, v: float):
        """喂入单条数据"""
        if self._frozen:
            return
        if channel not in self._buffers:
            return
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return

        self._buffers[channel].append(DataPoint(t, v))
        self._sample_count += 1

    def feed_batch(self, t_arr, ax_arr, ay_arr, az_arr,
                   gx_arr, gy_arr, gz_arr, speed_arr, wheel_arr):
        """批量喂入数据（numpy数组），用于SQLite直读高速加载"""
        import numpy as np
        n = len(t_arr)
        if n == 0:
            return

        # 降采样步长：如果数据量超过20000，按步长抽取
        step = 1
        if n > 20000:
            step = max(1, n // 20000)

        channels_map = {
            "AX": ax_arr, "AY": ay_arr, "AZ": az_arr,
            "GX": gx_arr, "GY": gy_arr, "GZ": gz_arr,
            "Spd": speed_arr, "Whl": wheel_arr,
        }

        for name, arr in channels_map.items():
            if arr is None:
                continue
            buf = self._buffers[name]
            buf.clear()
            for i in range(0, n, step):
                v = float(arr[i])
                if math.isnan(v) or math.isinf(v):
                    continue
                buf.append(DataPoint(float(t_arr[i]), v))

        self._sample_count = n
        self._update_auto_ranges()

    def set_event_range(self, start: float, end: float):
        """设置事件高亮区间"""
        self._event_range = (start, end)
        self.update()

    def clear_event_range(self):
        """清除事件高亮"""
        self._event_range = None
        self.update()

    def set_frozen(self, frozen: bool):
        """冻结/解冻图表"""
        self._frozen = frozen

    def set_auto_range(self, enabled: bool):
        """启用/禁用自适应Y轴"""
        self._auto_range_enabled = enabled
        if enabled:
            self._update_auto_ranges()

    def clear(self):
        """清空所有数据"""
        for buf in self._buffers.values():
            buf.clear()
        self._event_range = None
        self._sample_count = 0
        for name in self._auto_y_ranges:
            lo, hi = DEFAULT_Y_RANGES.get(name, (-4, 4))
            self._auto_y_ranges[name] = [lo, hi]
        self.update()

    def has_data(self) -> bool:
        """是否有数据"""
        return any(len(buf) > 0 for buf in self._buffers.values())

    # ─── 内部方法 ─────────────────────────────────────────────

    def _update_auto_ranges(self):
        """更新各通道的自适应Y轴范围"""
        if not self._auto_range_enabled:
            return
        for name, buf in self._buffers.items():
            if len(buf) < 2:
                continue
            vals = [d.v for d in buf]
            data_min = min(vals)
            data_max = max(vals)
            if data_max - data_min < 1e-9:
                data_min -= 0.5
                data_max += 0.5
            padding = (data_max - data_min) * 0.1
            self._auto_y_ranges[name] = [data_min - padding, data_max + padding]

    # ─── 渲染 ─────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        painter.fillRect(self.rect(), QColor(CLR_BG))
        painter.setPen(QColor(CLR_BORDER))
        painter.drawRect(0, 0, w - 1, h - 1)

        if not self.has_data():
            painter.setPen(QColor(CLR_TEXT_DIM))
            painter.setFont(QFont(FONT_FAMILY, 10))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无趋势数据")
            painter.end()
            return

        # 计算每个通道的绘图区域
        n_channels = len(TREND_CHANNELS)
        plot_area_h = h - self.TOP_MARGIN - self.BOTTOM_MARGIN
        row_h = plot_area_h / n_channels

        for i, (name, unit, color) in enumerate(TREND_CHANNELS):
            y_top = self.TOP_MARGIN + i * row_h
            y_bottom = y_top + row_h
            self._draw_channel_row(painter, name, unit, color, i, y_top, y_bottom, w)

        painter.end()

    def _draw_channel_row(self, painter, name, unit, color, idx, y_top, y_bottom, w):
        """绘制单个通道行"""
        buf = self._buffers.get(name)
        if not buf or len(buf) < 2:
            return

        ml = self.LABEL_WIDTH
        mr = self.RIGHT_MARGIN
        pw = w - ml - mr
        ph = y_bottom - y_top
        if pw < 10 or ph < 10:
            return

        y_lo, y_hi = self._auto_y_ranges.get(name, DEFAULT_Y_RANGES.get(name, (-4, 4)))
        if abs(y_hi - y_lo) < 1e-9:
            y_hi = y_lo + 1.0

        # 降采样
        vals = list(buf)
        downsampled = ExtremaDownsampler.downsample(vals, self.RENDER_POINTS, DownsampleMode.EXTREMA)
        if len(downsampled) < 2:
            return

        t_min = downsampled[0].t
        t_max = downsampled[-1].t
        if t_max - t_min < 1e-9:
            t_max = t_min + 1.0

        # ── 背景网格 ──
        painter.setPen(QPen(QColor(CLR_GRID_MINOR), 0.5))
        for j in range(3):
            gy = y_top + ph * (j + 1) / 4
            painter.drawLine(int(ml), int(gy), int(ml + pw), int(gy))

        # 零线
        if y_lo < 0 < y_hi:
            y_zero_norm = 1.0 - (0 - y_lo) / (y_hi - y_lo)
            y_zero = y_top + ph * y_zero_norm
            painter.setPen(QPen(QColor("#305060"), 1, Qt.DashLine))
            painter.drawLine(int(ml), int(y_zero), int(ml + pw), int(y_zero))

        # ── 事件高亮区间 ──
        if self._event_range:
            ev_start, ev_end = self._event_range
            if ev_end > t_min and ev_start < t_max:
                x1 = ml + pw * max(0, (ev_start - t_min) / (t_max - t_min))
                x2 = ml + pw * min(1, (ev_end - t_min) / (t_max - t_min))
                highlight = QColor("#00b8d4")
                highlight.setAlpha(20)
                painter.fillRect(QRectF(x1, y_top, x2 - x1, ph), highlight)

        # ── 绘制曲线 ──
        path = QPainterPath()
        first = True
        for dp in downsampled:
            t_norm = (dp.t - t_min) / (t_max - t_min)
            x = ml + pw * t_norm
            y_norm = (dp.v - y_lo) / (y_hi - y_lo)
            y_norm = max(0.0, min(1.0, y_norm))
            y = y_top + ph * (1.0 - y_norm)

            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        curve_color = QColor(color)
        painter.setPen(QPen(curve_color, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # ── Y轴标签 ──
        painter.setPen(QColor(CLR_TEXT_DIM))
        painter.setFont(QFont(FONT_MONO, 7))
        label_y = y_top + ph / 2
        painter.drawText(2, int(label_y) - 4, ml - 4, 14, Qt.AlignRight | Qt.AlignVCenter, name)

        # Y轴上下限
        painter.drawText(2, int(y_top) + 2, ml - 4, 10, Qt.AlignRight | Qt.AlignTop, f"{y_hi:.1f}")
        painter.drawText(2, int(y_bottom) - 12, ml - 4, 10, Qt.AlignRight | Qt.AlignBottom, f"{y_lo:.1f}")

        # ── 通道分隔线（非最后一个） ──
        if idx < len(TREND_CHANNELS) - 1:
            painter.setPen(QPen(QColor(CLR_GRID_MAJOR), 1))
            painter.drawLine(int(ml), int(y_bottom), int(ml + pw), int(y_bottom))

    # ─── 尺寸提示 ─────────────────────────────────────────────

    def sizeHint(self):
        return self.minimumSize()