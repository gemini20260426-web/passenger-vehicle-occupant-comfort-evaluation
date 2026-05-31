#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合驾驶仪表盘视图 — Phase 1
提供一屏全貌的驾驶行为监控仪表盘
"""

import logging
import time
from collections import deque
from typing import Dict, Any, Optional

import numpy as np

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QGridLayout, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QBrush,
                           QPainterPath, QRadialGradient, QLinearGradient,
                           QFontMetrics)

try:
    import matplotlib
    matplotlib.use('qtagg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from core.core.analysis.core_types import (
    DrivingState, RiskLevel, BehaviorCategory, BEHAVIOR_LABELS_CN,
    ManeuverEvent, RiskReport, FrameResult
)

try:
    from core.core.seat_evaluation.metadata_registry import get_global_registry
    _registry_available = True
except ImportError:
    _registry_available = False


def _get_state_cn_label_legacy(state: DrivingState) -> str:
    """通过 DrivingState 枚举获取中文标签，优先使用注册中心"""
    if _registry_available:
        registry = get_global_registry()
        label = registry.get_driving_state_cn_label(state.name.lower())
        if label != state.name.lower():
            return label
    return STATE_LABELS_CN.get(state, "未知")


RISK_COLORS = {
    RiskLevel.SAFE: QColor(39, 174, 96),
    RiskLevel.CAUTION: QColor(241, 196, 15),
    RiskLevel.WARNING: QColor(230, 126, 34),
    RiskLevel.DANGER: QColor(231, 76, 60),
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

STATE_LABELS_CN = {
    DrivingState.STOPPED: "停车",
    DrivingState.STRAIGHT_CRUISE: "匀速直行",
    DrivingState.ACCELERATING: "加速中",
    DrivingState.BRAKING: "减速中",
    DrivingState.TURNING_LEFT: "左转中",
    DrivingState.TURNING_RIGHT: "右转中",
    DrivingState.LANE_CHANGING: "变道中",
    DrivingState.UNKNOWN: "未知",
}


class RiskIndicator(QWidget):
    """风险等级指示器 — 大尺寸圆形指示灯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = RiskLevel.SAFE
        self._score = 0.0
        self.setMinimumSize(120, 120)
        self.setMaximumSize(160, 160)

    def update_risk(self, level: RiskLevel, score: float):
        self._level = level
        self._score = score
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 8

        color = RISK_COLORS.get(self._level, QColor(149, 165, 166))

        glow = QRadialGradient(cx, cy, r * 1.3)
        glow.setColorAt(0, color.lighter(160))
        glow.setColorAt(0.6, color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r * 1.3, r * 1.3)

        inner_glow = QRadialGradient(cx, cy - r * 0.15, r)
        inner_glow.setColorAt(0, color.lighter(180))
        inner_glow.setColorAt(0.7, color)
        inner_glow.setColorAt(1, color.darker(130))
        painter.setBrush(QBrush(inner_glow))
        painter.setPen(QPen(color.darker(150), 2))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(QPen(Qt.white, 2))
        font = QFont("Microsoft YaHei", 11, QFont.Bold)
        painter.setFont(font)
        label = RISK_LABELS_CN.get(self._level, "未知")
        painter.drawText(QRectF(0, cy - r * 0.5, w, r * 0.5), Qt.AlignHCenter | Qt.AlignBottom, label)

        font2 = QFont("Microsoft YaHei", 16, QFont.Bold)
        painter.setFont(font2)
        painter.drawText(QRectF(0, cy - r * 0.05, w, r * 0.6), Qt.AlignHCenter | Qt.AlignTop, f"{int(self._score)}")


class ScoreGauge(QWidget):
    """驾驶评分仪表 — 半圆弧形仪表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 0
        self.setMinimumSize(140, 100)
        self.setMaximumSize(200, 140)

    def update_score(self, score: float):
        self._score = int(max(0, min(100, score)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h * 0.85
        r = min(w, h) * 0.7

        painter.setPen(QPen(QColor(220, 220, 220), 10, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 180 * 16, 180 * 16)

        ratio = self._score / 100.0
        span = int(180 * ratio * 16)

        if ratio < 0.4:
            color = QColor(231, 76, 60)
        elif ratio < 0.7:
            color = QColor(241, 196, 15)
        else:
            color = QColor(39, 174, 96)

        painter.setPen(QPen(color, 10, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 180 * 16, -span)

        font = QFont("Microsoft YaHei", 22, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(44, 62, 80)))
        painter.drawText(QRectF(cx - r * 0.6, cy - r * 0.5, r * 1.2, r * 0.6),
                         Qt.AlignHCenter | Qt.AlignBottom, str(self._score))

        font2 = QFont("Microsoft YaHei", 9)
        painter.setFont(font2)
        painter.setPen(QPen(QColor(127, 140, 141)))
        painter.drawText(QRectF(cx - r * 0.6, cy - r * 0.1, r * 1.2, r * 0.3),
                         Qt.AlignHCenter | Qt.AlignTop, "驾驶评分")


class StateBadge(QWidget):
    """当前驾驶状态徽章"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = DrivingState.UNKNOWN
        self._duration = 0.0
        self.setMinimumHeight(50)

    def update_state(self, state: DrivingState, duration: float = 0.0):
        self._state = state
        self._duration = duration
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        state_colors = {
            DrivingState.STOPPED: QColor(155, 89, 182),
            DrivingState.STRAIGHT_CRUISE: QColor(39, 174, 96),
            DrivingState.ACCELERATING: QColor(241, 196, 15),
            DrivingState.BRAKING: QColor(230, 126, 34),
            DrivingState.TURNING_LEFT: QColor(52, 152, 219),
            DrivingState.TURNING_RIGHT: QColor(52, 152, 219),
            DrivingState.LANE_CHANGING: QColor(52, 152, 219),
            DrivingState.UNKNOWN: QColor(149, 165, 166),
        }
        color = state_colors.get(self._state, QColor(149, 165, 166))

        if _registry_available and self._state not in state_colors:
            registry = get_global_registry()
            for code, meta in registry.driving_states.items():
                if meta.display_name_cn == STATE_LABELS_CN.get(self._state, ''):
                    try:
                        color = QColor(meta.color_hex)
                    except Exception:
                        pass
                    break

        path = QPainterPath()
        path.addRoundedRect(QRectF(4, 4, w - 8, h - 8), 12, 12)
        painter.setBrush(QBrush(color.lighter(170)))
        painter.setPen(QPen(color, 2))
        painter.drawPath(path)

        label = _get_state_cn_label_legacy(self._state)
        font = QFont("Microsoft YaHei", 13, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(color.darker(130)))
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, label)


class MiniGauge(QWidget):
    """迷你仪表 — 用于车速/加速度等"""

    def __init__(self, title: str, unit: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._value = 0.0
        self.setMinimumSize(90, 70)

    def set_value(self, value: float):
        self._value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        font1 = QFont("Microsoft YaHei", 8)
        painter.setFont(font1)
        painter.setPen(QPen(QColor(127, 140, 141)))
        painter.drawText(QRectF(0, 2, w, 16), Qt.AlignHCenter, self._title)

        font2 = QFont("Microsoft YaHei", 16, QFont.Bold)
        painter.setFont(font2)
        painter.setPen(QPen(QColor(44, 62, 80)))
        painter.drawText(QRectF(0, 18, w, 28), Qt.AlignHCenter, f"{self._value:.1f}")

        font3 = QFont("Microsoft YaHei", 8)
        painter.setFont(font3)
        painter.setPen(QPen(QColor(149, 165, 166)))
        painter.drawText(QRectF(0, 44, w, 16), Qt.AlignHCenter, self._unit)


class RadarChart(QWidget):
    """五维雷达图 — 使用 matplotlib"""

    DIMENSIONS = ["稳定性", "安全性", "舒适性", "经济性", "合规性"]
    DIM_KEYS = ["stability", "safety", "comfort", "economy", "compliance"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = {k: 0.5 for k in self.DIM_KEYS}
        self.setMinimumSize(220, 220)
        if MATPLOTLIB_AVAILABLE:
            self._fig = Figure(figsize=(2.8, 2.8), dpi=80)
            self._canvas = FigureCanvas(self._fig)
            self._canvas.setParent(self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._canvas)
            self._init_chart()

    def _init_chart(self):
        self._ax = self._fig.add_subplot(111, polar=True)
        self._fig.patch.set_facecolor('none')
        self._ax.set_facecolor('none')
        self._update_draw()

    def _update_draw(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        self._ax.clear()

        N = len(self.DIMENSIONS)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]

        values = [self._values.get(k, 0.5) for k in self.DIM_KEYS]
        values += values[:1]

        self._ax.fill(angles, values, alpha=0.15, color='#2980b9')
        self._ax.plot(angles, values, 'o-', color='#2980b9', linewidth=1.5, markersize=4)

        self._ax.fill(angles, [0.8] * len(angles), alpha=0.05, color='#27ae60')
        self._ax.plot(angles, [0.8] * len(angles), '--', color='#bdc3c7', linewidth=0.5)

        self._ax.set_xticks(angles[:-1])
        self._ax.set_xticklabels(self.DIMENSIONS, fontsize=8)
        self._ax.set_ylim(0, 1)
        self._ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        self._ax.set_yticklabels([])
        self._ax.spines['polar'].set_visible(False)
        self._ax.grid(True, alpha=0.2, linestyle='--')

        self._canvas.draw_idle()

    def update_values(self, risk_report=None, features=None):
        if risk_report:
            self._values["stability"] = max(0, min(1, risk_report.stability_margin))
            self._values["safety"] = max(0, min(1, 1 - risk_report.collision_risk))
            self._values["comfort"] = max(0, min(1, 1 - risk_report.comfort_index))
            self._values["economy"] = 0.7
            self._values["compliance"] = 0.75
        if MATPLOTLIB_AVAILABLE:
            self._update_draw()


class DonutChart(QWidget):
    """行为分类环形图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {cat: 0 for cat in BehaviorCategory}
        self.setMinimumSize(200, 200)
        if MATPLOTLIB_AVAILABLE:
            self._fig = Figure(figsize=(2.5, 2.5), dpi=80)
            self._canvas = FigureCanvas(self._fig)
            self._canvas.setParent(self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._canvas)
            self._init_chart()

    def _init_chart(self):
        self._ax = self._fig.add_subplot(111)
        self._fig.patch.set_facecolor('none')
        self._ax.set_facecolor('none')
        self._update_draw()

    def _update_draw(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        self._ax.clear()

        cat_colors = {
            BehaviorCategory.NORMAL: '#27ae60',
            BehaviorCategory.LONGITUDINAL: '#f39c12',
            BehaviorCategory.LATERAL: '#3498db',
            BehaviorCategory.COMPOSITE: '#e67e22',
            BehaviorCategory.ANOMALY: '#e74c3c',
        }
        cat_labels = {
            BehaviorCategory.NORMAL: "正常",
            BehaviorCategory.LONGITUDINAL: "纵向",
            BehaviorCategory.LATERAL: "横向",
            BehaviorCategory.COMPOSITE: "复合",
            BehaviorCategory.ANOMALY: "异常",
        }

        data = []
        colors = []
        labels = []
        for cat in BehaviorCategory:
            cnt = self._counts.get(cat, 0)
            if cnt > 0:
                data.append(cnt)
                colors.append(cat_colors.get(cat, '#95a5a6'))
                labels.append(cat_labels.get(cat, cat.value))

        if not data:
            data = [1]
            colors = ['#ecf0f1']
            labels = ['无数据']

        wedges, texts = self._ax.pie(
            data, labels=None, colors=colors,
            startangle=90, pctdistance=0.75,
            wedgeprops=dict(width=0.35, edgecolor='white', linewidth=1)
        )

        total = sum(data)
        self._ax.text(0, 0, str(total), ha='center', va='center',
                      fontsize=16, fontweight='bold', color='#2c3e50')
        self._ax.text(0, -0.15, '事件总数', ha='center', va='center',
                      fontsize=8, color='#7f8c8d')

        legend_labels = [f"{l} ({d})" for l, d in zip(labels, data)]
        self._ax.legend(wedges, legend_labels, loc='lower center',
                        bbox_to_anchor=(0.5, -0.15), ncol=3,
                        fontsize=7, frameon=False)

        self._canvas.draw_idle()

    def update_counts(self, counts: Dict[BehaviorCategory, int]):
        self._counts = counts
        if MATPLOTLIB_AVAILABLE:
            self._update_draw()


class DrivingDashboardView(QWidget):
    """综合驾驶仪表盘视图"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None

        self._current_risk = RiskLevel.SAFE
        self._current_score = 85.0
        self._current_state = DrivingState.UNKNOWN
        self._category_counts = {cat: 0 for cat in BehaviorCategory}
        self._event_history = deque(maxlen=100)

        self._init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def _init_ui(self):
        scroll = QVBoxLayout(self)
        scroll.setContentsMargins(0, 0, 0, 0)

        scroll_area = self._make_scroll_area()
        content = QWidget()
        content.setObjectName("dashboardContent")
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        left_top = QVBoxLayout()
        left_top.setSpacing(6)
        self.risk_indicator = RiskIndicator()
        left_top.addWidget(self.risk_indicator, 0, Qt.AlignCenter)
        self.state_badge = StateBadge()
        left_top.addWidget(self.state_badge)
        top_row.addLayout(left_top)

        self.score_gauge = ScoreGauge()
        top_row.addWidget(self.score_gauge)

        gauges_widget = QWidget()
        gauges_layout = QGridLayout(gauges_widget)
        gauges_layout.setSpacing(4)
        self.speed_gauge = MiniGauge("车速", "km/h")
        self.ax_gauge = MiniGauge("纵加速度", "m/s²")
        self.ay_gauge = MiniGauge("横加速度", "m/s²")
        self.gz_gauge = MiniGauge("横摆角速度", "rad/s")
        gauges_layout.addWidget(self.speed_gauge, 0, 0)
        gauges_layout.addWidget(self.ax_gauge, 0, 1)
        gauges_layout.addWidget(self.ay_gauge, 1, 0)
        gauges_layout.addWidget(self.gz_gauge, 1, 1)
        top_row.addWidget(gauges_widget)

        main_layout.addLayout(top_row)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)

        radar_card = self._make_card("五维驾驶评估")
        radar_layout = QVBoxLayout(radar_card)
        radar_layout.setContentsMargins(4, 4, 4, 4)
        self.radar_chart = RadarChart()
        radar_layout.addWidget(self.radar_chart)
        charts_row.addWidget(radar_card)

        donut_card = self._make_card("行为分类统计")
        donut_layout = QVBoxLayout(donut_card)
        donut_layout.setContentsMargins(4, 4, 4, 4)
        self.donut_chart = DonutChart()
        donut_layout.addWidget(self.donut_chart)
        charts_row.addWidget(donut_card)

        main_layout.addLayout(charts_row)

        summary_card = self._make_card("最近事件摘要")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(10, 6, 10, 6)
        self.summary_label = QLabel("等待分析数据...")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "QLabel { color: #2c3e50; font-size: 12px; font-family: 'Microsoft YaHei'; "
            "background-color: #f8f9fa; border-radius: 4px; padding: 8px; }"
        )
        self.summary_label.setMinimumHeight(60)
        summary_layout.addWidget(self.summary_label)
        main_layout.addWidget(summary_card)

        main_layout.addStretch()

        scroll_area.setWidget(content)
        scroll.addWidget(scroll_area)

    def _make_scroll_area(self):
        from PySide6.QtWidgets import QScrollArea
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return sa

    def _make_card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setFlat(False)
        card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        return card

    def update_frame_result(self, result):
        """接收 FrameResult 并更新所有仪表盘组件（节流200ms）"""
        if result is None:
            return

        now = time.time()
        if now - getattr(self, '_last_update', 0) < 0.2:
            return
        self._last_update = now

        state = result.state
        features = result.features
        event = result.event
        raw = result.raw_data or {}

        self._current_state = state
        self.state_badge.update_state(state)

        speed = raw.get('speed', raw.get('车速', 0.0))
        ax = raw.get('ax', raw.get('accel_x', 0.0))
        ay = raw.get('ay', raw.get('accel_y', 0.0))
        gz = raw.get('gz', raw.get('gyro_z', 0.0))

        self.speed_gauge.set_value(float(speed) if speed else 0.0)
        self.ax_gauge.set_value(float(ax) if ax else 0.0)
        self.ay_gauge.set_value(float(ay) if ay else 0.0)
        self.gz_gauge.set_value(float(gz) if gz else 0.0)

        if event:
            self._event_history.append(event)
            self._current_risk = event.risk_level
            self._current_score = max(0, min(100, 100 - event.risk_score))

            cat = event.category
            self._category_counts[cat] = self._category_counts.get(cat, 0) + 1

            self.risk_indicator.update_risk(event.risk_level, event.risk_score)
            self.score_gauge.update_score(self._current_score)

            risk_report = event.metadata.get('risk_report')
            if not isinstance(risk_report, RiskReport):
                risk_report = getattr(result, 'risk', None)
            self.radar_chart.update_values(risk_report=risk_report)

            self.donut_chart.update_counts(self._category_counts)

            self._update_summary(event)

    def _update_summary(self, event: ManeuverEvent):
        lines = []
        lines.append(f"🕐 {time.strftime('%H:%M:%S', time.localtime(event.end_time))}.{int((event.end_time - int(event.end_time)) * 1000):03d}")
        lines.append(f"📋 行为: {event.label_cn}  |  分类: {event.category.value}")
        lines.append(f"⚠️ 风险: {RISK_LABELS_CN.get(event.risk_level, '未知')}  |  评分: {event.risk_score:.1f}")
        lines.append(f"📏 持续: {event.duration:.2f}s  |  置信度: {event.confidence:.2f}")
        lines.append(f"📐 峰值加速度: ax={event.peak_ax:.2f}  ay={event.peak_ay:.2f}  jerk={event.peak_jerk:.2f}")

        if self._event_history:
            recent = list(self._event_history)[-5:]
            lines.append("")
            lines.append("── 最近5个事件 ──")
            for e in reversed(recent):
                t = time.strftime('%H:%M:%S', time.localtime(e.end_time))
                ms = int((e.end_time - int(e.end_time)) * 1000)
                lines.append(f"  {t}.{ms:03d}  {e.label_cn}  [{RISK_LABELS_CN.get(e.risk_level, '?')}]")

        self.summary_label.setText("\n".join(lines))

    def reset(self):
        self._current_risk = RiskLevel.SAFE
        self._current_score = 85.0
        self._current_state = DrivingState.UNKNOWN
        self._category_counts = {cat: 0 for cat in BehaviorCategory}
        self._event_history.clear()
        self.risk_indicator.update_risk(RiskLevel.SAFE, 0)
        self.score_gauge.update_score(85)
        self.state_badge.update_state(DrivingState.UNKNOWN)
        self.speed_gauge.set_value(0)
        self.ax_gauge.set_value(0)
        self.ay_gauge.set_value(0)
        self.gz_gauge.set_value(0)
        self.donut_chart.update_counts(self._category_counts)
        self.summary_label.setText("等待分析数据...")
