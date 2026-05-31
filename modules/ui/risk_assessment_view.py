#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险评估详情视图 — Phase 3
展示 Layer 5 的完整风险评估结果：稳定性裕度、碰撞风险、舒适性指标、风险因素分解
"""

import logging
import time
from collections import deque
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QFrame, QProgressBar, QGridLayout,
                               QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient

from core.core.analysis.core_types import (
    RiskLevel, RiskReport, ManeuverEvent, FrameResult
)


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


class ColoredProgressBar(QProgressBar):
    """带颜色渐变的进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(39, 174, 96)
        self.setTextVisible(False)
        self.setMaximumHeight(18)
        self.setMinimumHeight(14)

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        ratio = max(0, min(1, self.value() / max(1, self.maximum())))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(236, 240, 241)))
        painter.drawRoundedRect(0, 0, w, h, 4, 4)

        if ratio > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, self._color.lighter(140))
            grad.setColorAt(1, self._color)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(0, 0, int(w * ratio), h, 4, 4)


class MetricRow(QWidget):
    """单行指标显示"""

    def __init__(self, label: str, value_fmt: str = "{:.1f}", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; min-width: 100px; }")
        layout.addWidget(self.label)

        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; }")
        layout.addWidget(self.value_label, 1)

        self._value_fmt = value_fmt

    def set_value(self, value, color: str = "#2c3e50"):
        if isinstance(value, (int, float)):
            self.value_label.setText(self._value_fmt.format(value))
        else:
            self.value_label.setText(str(value))
        self.value_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; font-size: 12px; color: {color}; }}"
        )


class RiskFactorBar(QWidget):
    """风险因素贡献条"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = 0
        self._color = QColor(231, 76, 60)
        self.setMinimumHeight(22)
        self.setMaximumHeight(28)

    def set_value(self, value: float, color: QColor = None):
        self._value = max(0, min(100, value))
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(236, 240, 241)))
        painter.drawRoundedRect(0, 0, w, h, 3, 3)

        ratio = self._value / 100.0
        if ratio > 0:
            painter.setBrush(QBrush(self._color))
            painter.drawRoundedRect(0, 0, int(w * ratio), h, 3, 3)

        painter.setPen(QPen(QColor(44, 62, 80)))
        font = QFont("Microsoft YaHei", 9)
        painter.setFont(font)
        painter.drawText(8, 0, w - 16, h, Qt.AlignVCenter | Qt.AlignLeft, self._label)

        painter.setPen(QPen(QColor(127, 140, 141)))
        painter.drawText(0, 0, w - 8, h, Qt.AlignVCenter | Qt.AlignRight, f"{self._value:.0f}%")


class RiskAssessmentView(QWidget):
    """风险评估详情视图"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None

        self._latest_report = None
        self._latest_event = None
        self._event_history = deque(maxlen=50)

        self._init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("riskContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_stability_card())
        layout.addWidget(self._build_collision_card())
        layout.addWidget(self._build_comfort_card())
        layout.addWidget(self._build_factor_card())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _make_card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setFlat(False)
        card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        return card

    def _build_stability_card(self) -> QGroupBox:
        card = self._make_card("🛡️ 稳定性裕度")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        self.stability_bar = ColoredProgressBar()
        self.stability_bar.setRange(0, 100)
        self.stability_bar.setValue(85)
        self.stability_bar.set_color(QColor(39, 174, 96))
        layout.addWidget(self.stability_bar)

        self.stability_pct = QLabel("85%")
        self.stability_pct.setAlignment(Qt.AlignCenter)
        self.stability_pct.setStyleSheet("QLabel { font-size: 18px; font-weight: bold; color: #27ae60; }")
        layout.addWidget(self.stability_pct)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)

        self.lat_margin = MetricRow("侧向加速度裕度:", "{:.2f} m/s²")
        grid.addWidget(self.lat_margin, 0, 0)
        self.lat_remaining = MetricRow("剩余:", "{:.0f}%")
        grid.addWidget(self.lat_remaining, 0, 1)

        self.yaw_margin = MetricRow("横摆角速度裕度:", "{:.2f} rad/s")
        grid.addWidget(self.yaw_margin, 1, 0)
        self.yaw_remaining = MetricRow("剩余:", "{:.0f}%")
        grid.addWidget(self.yaw_remaining, 1, 1)

        self.roll_margin = MetricRow("侧倾稳定性:", "{:.2f}")
        grid.addWidget(self.roll_margin, 2, 0)
        self.roll_status = MetricRow("状态:", "{}")
        grid.addWidget(self.roll_status, 2, 1)

        layout.addLayout(grid)
        return card

    def _build_collision_card(self) -> QGroupBox:
        card = self._make_card("💥 碰撞风险评估")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        self.collision_bar = ColoredProgressBar()
        self.collision_bar.setRange(0, 100)
        self.collision_bar.setValue(10)
        self.collision_bar.set_color(QColor(39, 174, 96))
        layout.addWidget(self.collision_bar)

        self.collision_pct = QLabel("低风险")
        self.collision_pct.setAlignment(Qt.AlignCenter)
        self.collision_pct.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #27ae60; }")
        layout.addWidget(self.collision_pct)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)

        self.ttc_metric = MetricRow("TTC (碰撞时间):", "{:.1f} s")
        grid.addWidget(self.ttc_metric, 0, 0)
        self.ttc_status = MetricRow("评估:", "{}")
        grid.addWidget(self.ttc_status, 0, 1)

        self.brake_dist = MetricRow("制动距离裕度:", "{:.1f} m")
        grid.addWidget(self.brake_dist, 1, 0)
        self.brake_status = MetricRow("评估:", "{}")
        grid.addWidget(self.brake_status, 1, 1)

        layout.addLayout(grid)
        return card

    def _build_comfort_card(self) -> QGroupBox:
        card = self._make_card("🪑 舒适性指标 (ISO 2631)")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        self.comfort_bar = ColoredProgressBar()
        self.comfort_bar.setRange(0, 100)
        self.comfort_bar.setValue(75)
        self.comfort_bar.set_color(QColor(39, 174, 96))
        layout.addWidget(self.comfort_bar)

        self.comfort_pct = QLabel("良好")
        self.comfort_pct.setAlignment(Qt.AlignCenter)
        self.comfort_pct.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #27ae60; }")
        layout.addWidget(self.comfort_pct)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)

        self.jerk_metric = MetricRow("加加速度 (Jerk):", "{:.2f} m/s³")
        grid.addWidget(self.jerk_metric, 0, 0)
        self.jerk_status = MetricRow("评估:", "{}")
        grid.addWidget(self.jerk_status, 0, 1)

        self.vdv_metric = MetricRow("振动剂量 (VDV):", "{:.2f} m/s^1.75")
        grid.addWidget(self.vdv_metric, 1, 0)
        self.vdv_status = MetricRow("评估:", "{}")
        grid.addWidget(self.vdv_status, 1, 1)

        layout.addLayout(grid)
        return card

    def _build_factor_card(self) -> QGroupBox:
        card = self._make_card("📊 风险因素分解")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        self.factor_bars = {}
        factor_labels = [
            ("激进加速", QColor(230, 126, 34)),
            ("急转弯", QColor(52, 152, 219)),
            ("紧急制动", QColor(231, 76, 60)),
            ("频繁变道", QColor(241, 196, 15)),
            ("蛇形驾驶", QColor(231, 76, 60)),
            ("其他因素", QColor(149, 165, 166)),
        ]
        for label, color in factor_labels:
            bar = RiskFactorBar(label)
            bar.set_value(0, color)
            layout.addWidget(bar)
            self.factor_bars[label] = bar

        return card

    def update_frame_result(self, result):
        if result is None:
            return

        event = result.event
        if event is None:
            return

        self._latest_event = event
        self._event_history.append(event)

        risk_report = event.metadata.get('risk_report')
        if risk_report is None:
            return

        self._latest_report = risk_report
        self._update_stability(risk_report)
        self._update_collision(risk_report)
        self._update_comfort(risk_report)
        self._update_factors(risk_report, event)

    def _update_stability(self, report: RiskReport):
        margin_pct = int(max(0, min(100, report.stability_margin * 100)))
        self.stability_bar.setValue(margin_pct)
        self.stability_pct.setText(f"{margin_pct}%")

        if margin_pct >= 70:
            color = "#27ae60"
            bar_color = QColor(39, 174, 96)
        elif margin_pct >= 40:
            color = "#f1c40f"
            bar_color = QColor(241, 196, 15)
        else:
            color = "#e74c3c"
            bar_color = QColor(231, 76, 60)

        self.stability_pct.setStyleSheet(
            f"QLabel {{ font-size: 18px; font-weight: bold; color: {color}; }}"
        )
        self.stability_bar.set_color(bar_color)

        factors = report.factors
        lat_margin_val = factors.get('lateral_accel_margin', 2.5)
        self.lat_margin.set_value(lat_margin_val)
        lat_rem = factors.get('lateral_remaining_pct', 60)
        self.lat_remaining.set_value(lat_rem, "#27ae60" if lat_rem > 40 else "#e74c3c")

        yaw_margin_val = factors.get('yaw_rate_margin', 0.8)
        self.yaw_margin.set_value(yaw_margin_val)
        yaw_rem = factors.get('yaw_remaining_pct', 70)
        self.yaw_remaining.set_value(yaw_rem, "#27ae60" if yaw_rem > 40 else "#e74c3c")

        roll_val = factors.get('roll_stability', 0.9)
        self.roll_margin.set_value(roll_val)
        self.roll_status.set_value("稳定" if roll_val > 0.7 else "注意",
                                   "#27ae60" if roll_val > 0.7 else "#e67e22")

    def _update_collision(self, report: RiskReport):
        risk_pct = int(max(0, min(100, report.collision_risk * 100)))
        self.collision_bar.setValue(risk_pct)

        if risk_pct <= 20:
            color = "#27ae60"
            bar_color = QColor(39, 174, 96)
            label = "低风险"
        elif risk_pct <= 50:
            color = "#f1c40f"
            bar_color = QColor(241, 196, 15)
            label = "中等风险"
        else:
            color = "#e74c3c"
            bar_color = QColor(231, 76, 60)
            label = "高风险"

        self.collision_pct.setText(label)
        self.collision_pct.setStyleSheet(
            f"QLabel {{ font-size: 14px; font-weight: bold; color: {color}; }}"
        )
        self.collision_bar.set_color(bar_color)

        factors = report.factors
        ttc = factors.get('ttc', 5.0)
        self.ttc_metric.set_value(ttc)
        self.ttc_status.set_value(
            "安全" if ttc > 3 else "注意" if ttc > 1.5 else "危险",
            "#27ae60" if ttc > 3 else "#f1c40f" if ttc > 1.5 else "#e74c3c"
        )

        brake = factors.get('brake_distance_margin', 45)
        self.brake_dist.set_value(brake)
        self.brake_status.set_value(
            "充足" if brake > 20 else "不足",
            "#27ae60" if brake > 20 else "#e74c3c"
        )

    def _update_comfort(self, report: RiskReport):
        comfort_pct = int(max(0, min(100, (1 - report.comfort_index) * 100)))
        self.comfort_bar.setValue(comfort_pct)

        if comfort_pct >= 70:
            color = "#27ae60"
            bar_color = QColor(39, 174, 96)
            label = "良好"
        elif comfort_pct >= 40:
            color = "#f1c40f"
            bar_color = QColor(241, 196, 15)
            label = "一般"
        else:
            color = "#e74c3c"
            bar_color = QColor(231, 76, 60)
            label = "较差"

        self.comfort_pct.setText(label)
        self.comfort_pct.setStyleSheet(
            f"QLabel {{ font-size: 14px; font-weight: bold; color: {color}; }}"
        )
        self.comfort_bar.set_color(bar_color)

        factors = report.factors
        jerk = factors.get('jerk', 2.0)
        self.jerk_metric.set_value(jerk)
        self.jerk_status.set_value(
            "舒适" if jerk < 3 else "可接受" if jerk < 6 else "不适",
            "#27ae60" if jerk < 3 else "#f1c40f" if jerk < 6 else "#e74c3c"
        )

        vdv = factors.get('vdv', 0.8)
        self.vdv_metric.set_value(vdv)
        self.vdv_status.set_value(
            "舒适" if vdv < 1.0 else "可接受" if vdv < 2.0 else "不适",
            "#27ae60" if vdv < 1.0 else "#f1c40f" if vdv < 2.0 else "#e74c3c"
        )

    def _update_factors(self, report: RiskReport, event: ManeuverEvent):
        factors = report.factors
        factor_contrib = factors.get('factor_contributions', {})

        if not factor_contrib:
            behavior = event.type
            if 'aggressive' in behavior or 'emergency' in behavior:
                factor_contrib = {event.label_cn: 60, "其他因素": 40}
            else:
                factor_contrib = {event.label_cn: 40, "其他因素": 60}

        for label, bar in self.factor_bars.items():
            val = factor_contrib.get(label, 0)
            bar.set_value(val)

    def reset(self):
        self._latest_report = None
        self._latest_event = None
        self._event_history.clear()
        self.stability_bar.setValue(85)
        self.stability_pct.setText("85%")
        self.collision_bar.setValue(10)
        self.collision_pct.setText("低风险")
        self.comfort_bar.setValue(75)
        self.comfort_pct.setText("良好")
        for bar in self.factor_bars.values():
            bar.set_value(0)
