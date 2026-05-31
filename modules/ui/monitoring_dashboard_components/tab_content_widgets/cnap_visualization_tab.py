#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CNAP 专业可视化组件 v4.0 — 医用监护仪级别
仿飞利浦 IntelliVue / 迈瑞 BeneVision 监护仪风格

特性:
- 医用监护仪参数瓦片 (大字体 + 单位 + 报警界限 + 趋势箭头)
- 专业波形区域 (ECG 风格网格, mmHg 标尺, 收缩/舒张标注)
- 实时逐拍检测与统计
- 颜色编码报警 (绿/黄/红)
- 生命体征趋势图
- DataBridge 实时数据接入
"""

import logging
import time
import math
from collections import deque

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QGridLayout, QFrame,
                               QSplitter, QSizePolicy, QComboBox)
from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import (QFont, QColor, QPainter, QPen, QBrush,
                           QPainterPath, QLinearGradient, QFontDatabase)

# ============================================================
# 设计系统
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

CLR_SBP = "#ff3d3d"
CLR_DBP = "#3d8bff"
CLR_MAP = "#ff9800"
CLR_HR = "#00e676"

CLR_WAVE = "#00e5ff"
CLR_WAVE_FILL = (0, 30, 60, 40)

CLR_ALARM_RED = "#ff1744"
CLR_ALARM_YELLOW = "#ffc107"
CLR_OK = "#4caf50"

# 报警阈值 (mmHg, bpm)
ALARM_SBP_HI = 180
ALARM_SBP_LO = 80
ALARM_DBP_HI = 110
ALARM_DBP_LO = 50
ALARM_MAP_HI = 130
ALARM_MAP_LO = 60
ALARM_HR_HI = 120
ALARM_HR_LO = 40


def _alarm_color(value, lo, hi, ok_color=CLR_TEXT):
    if value <= 0:
        return CLR_TEXT_DIM
    if value > hi:
        return CLR_ALARM_RED
    if value < lo:
        return CLR_ALARM_YELLOW
    return ok_color


def _trend_arrow(current, history):
    if len(history) < 2 or current <= 0:
        return ""
    avg_prev = sum(list(history)[-3:]) / min(3, len(history))
    diff_pct = (current - avg_prev) / avg_prev * 100 if avg_prev else 0
    if diff_pct > 2:
        return " ▲"
    if diff_pct < -2:
        return " ▼"
    return ""


# ============================================================
# 参数瓦片 — 单个生命体征显示
# ============================================================
class ParameterTile(QFrame):
    """医用监护仪参数瓦片：参数名 + 大字体数值 + 单位 + 报警色彩"""

    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._color = color
        self._value = 0
        self._history = deque(maxlen=10)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(58)
        self.setMinimumWidth(120)
        self.setStyleSheet(f"""
            ParameterTile {{
                background-color: {CLR_PANEL};
                border: 1px solid {CLR_BORDER};
                border-radius: 4px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(0)

        self._title_label = QLabel(self._title)
        self._title_label.setFont(QFont(FONT_FAMILY, 7))
        self._title_label.setStyleSheet(f"color: {self._color}; border: none; background: transparent;")
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._title_label)

        self._value_label = QLabel("---")
        self._value_label.setFont(QFont(FONT_MONO, 22, QFont.Bold))
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._value_label)

        bot = QHBoxLayout()
        bot.setSpacing(2)
        self._trend_label = QLabel("")
        self._trend_label.setFont(QFont(FONT_FAMILY, 7))
        self._trend_label.setStyleSheet("border: none; background: transparent;")
        bot.addWidget(self._trend_label)
        bot.addStretch()
        self._unit_label = QLabel(self._unit)
        self._unit_label.setFont(QFont(FONT_FAMILY, 7))
        self._unit_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bot.addWidget(self._unit_label)
        layout.addLayout(bot)

    def set_value(self, value, lo, hi):
        self._value = value
        if value is None or value <= 0:
            self._value_label.setText("---")
            self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
            self._trend_label.setText("")
            return
        self._history.append(value)
        arrow = _trend_arrow(value, self._history)
        alarm_clr = _alarm_color(value, lo, hi, self._color)
        self._value_label.setText(f"{value:.0f}")
        self._value_label.setStyleSheet(f"color: {alarm_clr}; border: none; background: transparent;")
        self._trend_label.setText(arrow)
        self._trend_label.setStyleSheet(f"color: {alarm_clr}; border: none; background: transparent;")


# ============================================================
# 紧凑参数瓦片 — 次级血流动力学参数显示
# ============================================================
class CompactParameterTile(QFrame):
    """紧凑型参数瓦片：参数名 + 小字体数值 + 单位 + 报警色彩"""

    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._color = color
        self._value = 0
        self._history = deque(maxlen=10)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(44)
        self.setMinimumWidth(95)
        self.setStyleSheet(f"""
            CompactParameterTile {{
                background-color: {CLR_PANEL};
                border: 1px solid {CLR_BORDER};
                border-radius: 3px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 1, 5, 1)
        layout.setSpacing(0)

        self._title_label = QLabel(self._title)
        self._title_label.setFont(QFont(FONT_FAMILY, 6))
        self._title_label.setStyleSheet(f"color: {self._color}; border: none; background: transparent;")
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._title_label)

        val_row = QHBoxLayout()
        val_row.setSpacing(1)
        self._value_label = QLabel("---")
        self._value_label.setFont(QFont(FONT_MONO, 14, QFont.Bold))
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        val_row.addWidget(self._value_label)
        val_row.addStretch()
        self._unit_label = QLabel(self._unit)
        self._unit_label.setFont(QFont(FONT_FAMILY, 6))
        self._unit_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
        self._unit_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        val_row.addWidget(self._unit_label)
        layout.addLayout(val_row)

    def set_value(self, value, lo=None, hi=None):
        self._value = value
        if value is None or (isinstance(value, (int, float)) and value <= 0):
            self._value_label.setText("---")
            self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")
            return
        self._history.append(value)
        clr = _alarm_color(value, lo, hi, self._color) if lo is not None and hi is not None else self._color
        display = f"{value:.1f}" if abs(value) < 10 else f"{value:.0f}"
        self._value_label.setText(display)
        self._value_label.setStyleSheet(f"color: {clr}; border: none; background: transparent;")

    def reset(self):
        self._value = 0
        self._history.clear()
        self._value_label.setText("---")
        self._value_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; border: none; background: transparent;")


# ============================================================
# 专业波形组件 — ECG 风格网格 + 动脉压波形
# ============================================================
class MedicalWaveform(QWidget):
    """专业医用波形显示器 — 支持波形估算与 BEATS 数据双源逐拍标注"""

    BEAT_SRC_WAVEFORM = 'waveform'
    BEAT_SRC_BEATS = 'beats'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.data_buffer = deque(maxlen=625)
        self.beat_markers = []
        self.display_secs = 5.0
        self.y_lo = 40.0
        self.y_hi = 180.0
        self._last_val = None
        self._sample_rate = 125.0
        self._frozen = False
        self._dirty = False
        self._repaint_timer = QTimer(self)
        self._repaint_timer.timeout.connect(self._do_repaint)
        self._repaint_timer.setInterval(33)
        self._repaint_timer.setSingleShot(True)

    def set_frozen(self, frozen):
        if frozen != self._frozen:
            self._frozen = frozen
            if not frozen:
                self._mark_dirty()

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._repaint_timer.start()

    def _do_repaint(self):
        if self.isVisible():
            self._dirty = False
            self.update()

    def feed(self, value):
        if self._frozen:
            return
        if value is not None and value > 0:
            self.data_buffer.append(value)
            self._last_val = value
        elif self._last_val is not None:
            self.data_buffer.append(self._last_val)
        else:
            return
        self._mark_dirty()

    def mark_beat(self, sbp, dbp, source=BEAT_SRC_WAVEFORM):
        n = len(self.data_buffer)
        if n > 0 and sbp is not None and dbp is not None:
            self.beat_markers.append({'idx': n - 1, 'sbp': sbp, 'dbp': dbp, 'source': source})
            if len(self.beat_markers) > 30:
                self.beat_markers.pop(0)
            self._mark_dirty()

    def clear(self):
        self.data_buffer.clear()
        self.beat_markers.clear()
        self._dirty = False
        self._repaint_timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        ml, mr = 48, 12
        mt, mb = 16, 28
        pw = w - ml - mr
        ph = h - mt - mb

        painter.fillRect(self.rect(), QColor(CLR_BG))
        painter.fillRect(ml, mt, pw, ph, QColor(CLR_PANEL))

        self._draw_grid(painter, ml, mt, pw, ph)

        if len(self.data_buffer) >= 2:
            self._draw_wave(painter, ml, mt, pw, ph)
            self._draw_beat_annotations(painter, ml, mt, pw, ph)

        self._draw_labels(painter, ml, mt, pw, ph)

        painter.setPen(QColor(CLR_BORDER))
        painter.drawRect(ml, mt, pw, ph)

        painter.end()

    def _draw_grid(self, painter, ml, mt, pw, ph):
        painter.setPen(QPen(QColor(CLR_GRID_MINOR), 1, Qt.DotLine))
        for i in range(21):
            x = ml + int(pw * i / 20)
            painter.drawLine(x, mt, x, mt + ph)
        for i in range(9):
            y = mt + int(ph * i / 8)
            painter.drawLine(ml, y, ml + pw, y)

        painter.setPen(QPen(QColor(CLR_GRID_MAJOR), 1, Qt.DashLine))
        for i in range(5):
            x = ml + int(pw * i / 4)
            painter.drawLine(x, mt, x, mt + ph)
        for i in range(3):
            y = mt + int(ph * i / 2)
            painter.drawLine(ml, y, ml + pw, y)

    def _draw_wave(self, painter, ml, mt, pw, ph):
        total = len(self.data_buffer)
        visible = min(total, int(self.display_secs * self._sample_rate))
        start = max(0, total - visible)

        path = QPainterPath()
        first = True
        for i in range(start, total):
            val = self.data_buffer[i]
            rel = i - start
            x = ml + int(pw * rel / max(1, visible - 1))
            clamped = max(self.y_lo, min(self.y_hi, val))
            norm = (clamped - self.y_lo) / (self.y_hi - self.y_lo) if self.y_hi != self.y_lo else 0.5
            y = mt + int(ph * (1.0 - norm))
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        grad = QLinearGradient(0, mt, 0, mt + ph)
        grad.setColorAt(0.0, QColor(0, 229, 255))
        grad.setColorAt(0.4, QColor(0, 190, 220))
        grad.setColorAt(1.0, QColor(0, 100, 150))

        pen = QPen(QBrush(grad), 2.2)
        painter.setPen(pen)
        painter.drawPath(path)

    def _draw_beat_annotations(self, painter, ml, mt, pw, ph):
        total = len(self.data_buffer)
        visible = min(total, int(self.display_secs * self._sample_rate))
        start = max(0, total - visible)

        for m in self.beat_markers:
            if m['idx'] < start:
                continue
            rel = m['idx'] - start
            xm = ml + int(pw * rel / max(1, visible - 1))
            if self.y_hi != self.y_lo:
                sy = mt + int(ph * (1.0 - (m['sbp'] - self.y_lo) / (self.y_hi - self.y_lo)))
                dy = mt + int(ph * (1.0 - (m['dbp'] - self.y_lo) / (self.y_hi - self.y_lo)))
            else:
                sy = mt
                dy = mt + ph

            is_beats = m.get('source') == self.BEAT_SRC_BEATS
            line_style = Qt.SolidLine if is_beats else Qt.DashLine
            line_width = 2.0 if is_beats else 1.0
            annot_color = QColor(CLR_SBP) if is_beats else QColor(0, 180, 200)

            painter.setPen(QPen(annot_color, line_width, line_style))
            painter.drawLine(xm, sy, xm, dy)
            painter.setPen(annot_color)
            painter.setFont(QFont(FONT_FAMILY, 8, QFont.Bold if is_beats else QFont.Normal))
            label = f"S{m['sbp']:.0f}" if is_beats else f"s{m['sbp']:.0f}"
            painter.drawText(QRectF(xm - 18, sy - 18, 36, 16), Qt.AlignCenter, label)

            if is_beats:
                painter.setPen(QColor(CLR_DBP))
                painter.drawText(QRectF(xm - 18, dy + 2, 36, 16), Qt.AlignCenter, f"D{m['dbp']:.0f}")

    def _draw_labels(self, painter, ml, mt, pw, ph):
        painter.setPen(QColor(CLR_TEXT_DIM))
        painter.setFont(QFont(FONT_FAMILY, 8))
        for i in range(5):
            y = mt + int(ph * i / 4)
            val = self.y_hi - (self.y_hi - self.y_lo) * i / 4
            painter.drawText(QRectF(2, y - 10, ml - 6, 20), Qt.AlignRight | Qt.AlignVCenter, f"{val:.0f}")

        painter.setPen(QColor(CLR_ACCENT))
        painter.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        painter.drawText(QRectF(ml + 4, mt - 2, 60, 18), Qt.AlignLeft | Qt.AlignVCenter, "mmHg")

        painter.setPen(QColor(CLR_TEXT_DIM))
        painter.setFont(QFont(FONT_FAMILY, 8))
        speed = self.display_secs
        painter.drawText(QRectF(ml, mt + ph + 2, pw, 24), Qt.AlignCenter,
                         f"扫描速度: {speed}s  |  采样率: {self._sample_rate:.0f}Hz")


# ============================================================
# 趋势小图 — 生命体征历史趋势
# ============================================================
class VitalTrendPanel(QWidget):
    """SBP/DBP/MAP/HR 迷你趋势图"""

    def __init__(self, title, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._color = color
        self._history = deque(maxlen=120)
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push(self, value):
        if value is not None and value > 0:
            self._history.append(value)
            self.update()

    def clear(self):
        self._history.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(CLR_PANEL))
        painter.setPen(QColor(CLR_BORDER))
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.setPen(QColor(self._color))
        painter.setFont(QFont(FONT_FAMILY, 8, QFont.Bold))
        painter.drawText(QRectF(4, 2, w - 8, 14), Qt.AlignLeft, self._title)

        if len(self._history) < 2:
            painter.end()
            return

        vals = list(self._history)
        lo = min(vals) * 0.9 if min(vals) > 0 else 0
        hi = max(vals) * 1.1 if max(vals) > 0 else 100
        if hi - lo < 1:
            hi = lo + 10

        path = QPainterPath()
        first = True
        for i, v in enumerate(vals):
            x = 4 + (w - 8) * i / (len(vals) - 1)
            norm = (v - lo) / (hi - lo) if hi != lo else 0.5
            y = h - 4 - (h - 20) * norm
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(QColor(self._color), 1.5))
        painter.drawPath(path)

        painter.setPen(QColor(CLR_TEXT_DIM))
        if vals:
            painter.drawText(QRectF(4, h - 16, 60, 14), Qt.AlignLeft, f"{vals[-1]:.0f}")
        painter.end()


# ============================================================
# 主 CNAP 可视化 Tab
# ============================================================
class CNAPVisualizationTab(QWidget):
    """CNAP 专业可视化 — 医用监护仪风格"""

    data_received = Signal(dict)
    analysis_completed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._init_data()
        self._init_ui()
        self._init_timers()
        self.logger.info("CNAP 医用监护仪可视化初始化完成")

    def _init_data(self):
        self.data_bridge = None
        self.is_running = False
        self.sample_rate = 125
        self._sample_count = 0
        self._beat_sbps = deque(maxlen=20)
        self._beat_dbps = deque(maxlen=20)
        self._beat_hrs = deque(maxlen=20)
        self._peak_buf = deque(maxlen=200)
        self._last_beat_ts = 0
        self._curr_hr = 0
        self._min_beat_gap = 0.3
        self._detecting = False

    def _init_ui(self):
        self.setFont(QFont(FONT_FAMILY, 9))
        self.setStyleSheet(f"background-color: {CLR_BG}; color: {CLR_TEXT};")

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # — 参数瓦片（2行×6列统一网格） —
        tiles_grid = QGridLayout()
        tiles_grid.setSpacing(4)
        all_params = [
            ("SBP 收缩压", "mmHg", CLR_SBP), ("DBP 舒张压", "mmHg", CLR_DBP),
            ("MAP 平均压", "mmHg", CLR_MAP), ("HR 心率", "bpm", CLR_HR),
            ("PP 脉压差", "mmHg", "#ff8a65"), ("HRV 心率变异", "ms", "#81d4fa"),
            ("MPP 平均脉压", "mmHg", "#fff176"), ("SV 每搏量", "ml", "#b39ddb"),
            ("SVR 血管阻力", "dyn·s", "#80cbc4"), ("PPV 脉压变异", "%", "#f48fb1"),
            ("SVV 每搏变异", "%", "#a5d6a7"), ("EF 射血分数", "%", "#ef9a9a"),
        ]
        self.all_tiles = {}
        for i, (title, unit, color) in enumerate(all_params):
            key = title.split()[0]
            tile = CompactParameterTile(title, unit, color)
            self.all_tiles[key] = tile
            row, col = divmod(i, 6)
            tiles_grid.addWidget(tile, row, col)
        root.addLayout(tiles_grid)

        # — 波形区域 —
        self.waveform = MedicalWaveform()
        root.addWidget(self.waveform, 6)

        # — 控制栏 —
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont(FONT_FAMILY, 10))
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")
        ctrl.addWidget(self.status_label)

        ctrl.addWidget(QLabel(" 速度:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "5x", "10x", "20x", "50x"])
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background: #1a2530; color: #00e5ff; border: 1px solid #2a3a4a;
                padding: 2px 8px; border-radius: 3px; font-size: 9pt;
            }
            QComboBox:hover { border-color: #00e5ff; }
            QComboBox QAbstractItemView {
                background: #1a2530; color: #ccc; selection-background-color: #00e5ff;
                selection-color: #000;
            }
        """)
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        ctrl.addWidget(self.speed_combo)

        ctrl.addStretch()
        self.freeze_btn = QPushButton("⏸ 冻结")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.setStyleSheet(self._btn_style())
        self.freeze_btn.clicked.connect(self._toggle_freeze)
        ctrl.addWidget(self.freeze_btn)
        self.clear_btn = QPushButton("🗑 清除")
        self.clear_btn.setStyleSheet(self._btn_style())
        self.clear_btn.clicked.connect(self._on_clear)
        ctrl.addWidget(self.clear_btn)
        root.addLayout(ctrl)

        # — 底部: 趋势图（第一行：主要生命体征） —
        trends = QHBoxLayout()
        trends.setSpacing(6)
        self.trend_sbp = VitalTrendPanel("SBP 趋势", CLR_SBP)
        self.trend_dbp = VitalTrendPanel("DBP 趋势", CLR_DBP)
        self.trend_map = VitalTrendPanel("MAP 趋势", CLR_MAP)
        self.trend_hr = VitalTrendPanel("HR 趋势", CLR_HR)
        for tr in [self.trend_sbp, self.trend_dbp, self.trend_map, self.trend_hr]:
            trends.addWidget(tr)
        root.addLayout(trends)

        # — 底部第二行: 血流动力学趋势 —
        trends2 = QHBoxLayout()
        trends2.setSpacing(6)
        self.trend_sv = VitalTrendPanel("SV 每搏量", "#81d4fa")
        self.trend_ppv = VitalTrendPanel("PPV 脉压变异", "#b39ddb")
        self.trend_svv = VitalTrendPanel("SVV 每搏变异", "#80cbc4")
        for tr in [self.trend_sv, self.trend_ppv, self.trend_svv]:
            trends2.addWidget(tr)
        root.addLayout(trends2)

        # — 状态信息条 —
        info_bar = QHBoxLayout()
        info_bar.setSpacing(16)
        self.lbl_samples = QLabel("样本: 0")
        self.lbl_beats = QLabel("心跳: 0")
        self.lbl_alarms = QLabel("报警: 无")
        for lbl in [self.lbl_samples, self.lbl_beats, self.lbl_alarms]:
            lbl.setFont(QFont(FONT_FAMILY, 8))
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
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #1a2a38; }}
            QPushButton:checked {{ background-color: {CLR_ALARM_YELLOW}; color: #000; }}
        """

    def _init_timers(self):
        pass

    # — 公开接口 —
    def start(self):
        self.is_running = True
        self.status_label.setText("运行中")
        self.status_label.setStyleSheet(f"color: {CLR_OK}; background: transparent;")

    def stop(self):
        self.is_running = False
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; background: transparent;")

    def set_data_bridge(self, data_bridge):
        self.data_bridge = data_bridge
        self.logger.info("CNAP 已连接 DataBridge")

    def update_vitals(self, sbp=None, dbp=None, map_val=None, hr=None,
                      pulse_pressure=None, heart_rate_variability=None,
                      mean_pulse_pressure=None, stroke_volume=None,
                      vascular_resistance=None, ppv=None, svv=None,
                      ejection_fraction=None):
        self._last_vitals = {
            'SBP': sbp, 'DBP': dbp, 'MAP': map_val, 'HR': hr,
            'PP': pulse_pressure, 'HRV': heart_rate_variability,
            'MPP': mean_pulse_pressure, 'SV': stroke_volume,
            'SVR': vascular_resistance, 'PPV': ppv,
            'SVV': svv, 'EF': ejection_fraction,
        }
        if sbp is not None:
            self.all_tiles['SBP'].set_value(int(sbp), ALARM_SBP_LO, ALARM_SBP_HI)
            self.trend_sbp.push(sbp)
        if dbp is not None:
            self.all_tiles['DBP'].set_value(int(dbp), ALARM_DBP_LO, ALARM_DBP_HI)
            self.trend_dbp.push(dbp)
        if map_val is not None:
            self.all_tiles['MAP'].set_value(int(map_val), ALARM_MAP_LO, ALARM_MAP_HI)
            self.trend_map.push(map_val)
        if hr is not None:
            self.all_tiles['HR'].set_value(int(hr), ALARM_HR_LO, ALARM_HR_HI)
            self.trend_hr.push(hr)

        if pulse_pressure is not None:
            self.all_tiles.get('PP', None) and self.all_tiles['PP'].set_value(pulse_pressure)
        if heart_rate_variability is not None:
            self.all_tiles.get('HRV', None) and self.all_tiles['HRV'].set_value(heart_rate_variability)
        if mean_pulse_pressure is not None:
            self.all_tiles.get('MPP', None) and self.all_tiles['MPP'].set_value(mean_pulse_pressure)
        if stroke_volume is not None:
            self.all_tiles.get('SV', None) and self.all_tiles['SV'].set_value(stroke_volume)
            self.trend_sv.push(stroke_volume)
        if vascular_resistance is not None:
            self.all_tiles.get('SVR', None) and self.all_tiles['SVR'].set_value(vascular_resistance)
        if ppv is not None:
            self.all_tiles.get('PPV', None) and self.all_tiles['PPV'].set_value(ppv)
            self.trend_ppv.push(ppv)
        if svv is not None:
            self.all_tiles.get('SVV', None) and self.all_tiles['SVV'].set_value(svv)
            self.trend_svv.push(svv)
        if ejection_fraction is not None:
            self.all_tiles.get('EF', None) and self.all_tiles['EF'].set_value(ejection_fraction)

        if sbp is not None and dbp is not None:
            self.waveform.mark_beat(sbp, dbp, source=MedicalWaveform.BEAT_SRC_BEATS)

    def feed_sample(self, pressure_value):
        if not self.is_running or self.freeze_btn.isChecked():
            return
        self._sample_count += 1

        if pressure_value is None or pressure_value <= 0:
            self.waveform.feed(self.waveform._last_val)
            return

        self.waveform.feed(pressure_value)

        if not self._detecting:
            self._peak_buf.append(pressure_value)
            self._detecting = True
            return

        self._peak_buf.append(pressure_value)
        if len(self._peak_buf) < 5:
            return

        near_peak = (pressure_value > self._peak_buf[-2] * 0.95 and
                     self._peak_buf[-2] < self._peak_buf[-1] >= pressure_value)
        if near_peak:
            now = time.time()
            gap = now - self._last_beat_ts
            if self._last_beat_ts > 0 and gap > self._min_beat_gap:
                sbp = max(self._peak_buf)
                dbp = min(self._peak_buf)
                if gap < 2.0:
                    self._curr_hr = 60.0 / gap
                self._last_beat_ts = now

                map_val = dbp + (sbp - dbp) / 3.0
                self._beat_sbps.append(sbp)
                self._beat_dbps.append(dbp)
                self._beat_hrs.append(self._curr_hr)

                lv = getattr(self, '_last_vitals', None)
                if not lv or lv.get('SBP') is None:
                    avg_sbp = sum(self._beat_sbps) / len(self._beat_sbps)
                    avg_dbp = sum(self._beat_dbps) / len(self._beat_dbps)
                    avg_map = avg_dbp + (avg_sbp - avg_dbp) / 3.0
                    avg_hr = sum(self._beat_hrs) / len(self._beat_hrs) if self._beat_hrs else 0
                    self.all_tiles['SBP'].set_value(avg_sbp, ALARM_SBP_LO, ALARM_SBP_HI)
                    self.all_tiles['DBP'].set_value(avg_dbp, ALARM_DBP_LO, ALARM_DBP_HI)
                    self.all_tiles['MAP'].set_value(avg_map, ALARM_MAP_LO, ALARM_MAP_HI)
                    self.all_tiles['HR'].set_value(avg_hr, ALARM_HR_LO, ALARM_HR_HI)
                    self.trend_sbp.push(avg_sbp)
                    self.trend_dbp.push(avg_dbp)
                    self.trend_map.push(avg_map)
                    self.trend_hr.push(avg_hr)

                self.waveform.mark_beat(sbp, dbp)
                self.lbl_beats.setText(f"心跳: {len(self._beat_sbps)}")

                self._peak_buf.clear()
                self._detecting = False

        if len(self._peak_buf) > 200:
            lv = getattr(self, '_last_vitals', None)
            if not lv or lv.get('SBP') is None:
                vals = list(self._peak_buf)
                sbp_est = max(vals)
                dbp_est = min(vals)
                map_est = dbp_est + (sbp_est - dbp_est) / 3.0
                self.all_tiles['SBP'].set_value(sbp_est, ALARM_SBP_LO, ALARM_SBP_HI)
                self.all_tiles['DBP'].set_value(dbp_est, ALARM_DBP_LO, ALARM_DBP_HI)
                self.all_tiles['MAP'].set_value(map_est, ALARM_MAP_LO, ALARM_MAP_HI)
            self._peak_buf.clear()
            self._detecting = False

        if self._sample_count % 50 == 0:
            self.lbl_samples.setText(f"样本: {self._sample_count}")

    def feed_batch(self, samples: list):
        for sample in samples:
            if isinstance(sample, (int, float)):
                self.feed_sample(sample)
            elif isinstance(sample, dict):
                val = sample.get('pressure') or sample.get('value') or sample.get('cnap')
                if val is not None:
                    self.feed_sample(val)

    def _toggle_freeze(self, checked):
        self.waveform.set_frozen(checked)
        self.status_label.setText("已冻结" if checked else "运行中")
        color = CLR_ALARM_YELLOW if checked else CLR_OK
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")

    def _on_speed_changed(self, text):
        speed = float(text.replace("x", ""))
        try:
            from modules.ui.left_control_panel.utils.data_reader_manager import get_data_reader_manager
            mgr = get_data_reader_manager()
            if mgr:
                mgr.set_playback_speed(speed)
                self.status_label.setText(f"运行中 ({speed}x)")
                self.status_label.setStyleSheet(f"color: #00e5ff; background: transparent;")
        except Exception as e:
            self.logger.warning(f"设置播放速度失败: {e}")

    def _on_clear(self):
        self.waveform.clear()
        self._sample_count = 0
        self._beat_sbps.clear()
        self._beat_dbps.clear()
        self._beat_hrs.clear()
        self._peak_buf.clear()
        self._detecting = False
        self._last_vitals = {}
        for key in self.all_tiles:
            self.all_tiles[key].reset()
        for trend in [self.trend_sbp, self.trend_dbp, self.trend_map, self.trend_hr,
                       self.trend_sv, self.trend_ppv, self.trend_svv]:
            trend.clear()
        self.lbl_samples.setText("样本: 0")
        self.lbl_beats.setText("心跳: 0")
        self.lbl_alarms.setText("报警: 无")

    def cleanup(self):
        self.is_running = False
        self.logger.info("CNAP 可视化已清理")
