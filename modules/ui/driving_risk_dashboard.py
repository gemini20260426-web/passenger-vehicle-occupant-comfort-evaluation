#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶评估仪表盘 — 综合仪表盘 + 风险评估 拼合模块（卡片式布局）
数据化驾驶概览 + 五维评估 + 行为统计 + 风险详情卡片 + 事件摘要
"""

import logging
import time
from collections import deque
from typing import Dict, Any

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QFrame, QGridLayout,
                               QScrollArea, QTableWidget,
                               QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.core.analysis.core_types import (
    RiskLevel, RiskReport, ManeuverEvent, FrameResult,
    DrivingState, BehaviorCategory, BEHAVIOR_LABELS_CN
)

try:
    from core.core.seat_evaluation.metadata_registry import get_global_registry
    _registry_available = True
except ImportError:
    _registry_available = False

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

CAT_LABELS_CN = {
    BehaviorCategory.NORMAL: "正常",
    BehaviorCategory.LONGITUDINAL: "纵向",
    BehaviorCategory.LATERAL: "横向",
    BehaviorCategory.COMPOSITE: "复合",
    BehaviorCategory.ANOMALY: "异常",
}

CAT_COLORS = {
    BehaviorCategory.NORMAL: "#27ae60",
    BehaviorCategory.LONGITUDINAL: "#f39c12",
    BehaviorCategory.LATERAL: "#3498db",
    BehaviorCategory.COMPOSITE: "#e67e22",
    BehaviorCategory.ANOMALY: "#e74c3c",
}

DIM_LABELS = ["稳定性", "安全性", "舒适性", "经济性", "合规性"]
DIM_KEYS = ["stability", "safety", "comfort", "economy", "compliance"]


class DataCard(QFrame):
    """数据化指标卡片"""

    _COLOR_STYLES = {}

    def __init__(self, title: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("dataCard")
        self.setMinimumSize(100, 60)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "DataCard { border: 1px solid #e0e0e0; border-radius: 6px; "
            "background-color: #fafbfc; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 10px; }")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)

        self.unit_label = QLabel(unit)
        self.unit_label.setStyleSheet("QLabel { color: #95a5a6; font-size: 9px; }")
        self.unit_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.unit_label)

        self._last_color = None

    def set_value(self, value: str, color: str = "#2c3e50"):
        if self.value_label.text() == value and self._last_color == color:
            return
        self.value_label.setText(value)
        if self._last_color != color:
            self._last_color = color
            if color not in DataCard._COLOR_STYLES:
                DataCard._COLOR_STYLES[color] = (
                    f"QLabel {{ font-weight: bold; font-size: 16px; color: {color}; }}"
                )
            self.value_label.setStyleSheet(DataCard._COLOR_STYLES[color])


class DrivingRiskDashboard(QWidget):
    """驾驶评估仪表盘 — 卡片式布局"""

    # ── 默认显示阈值 (可通过 config_manager 覆盖) ──
    _DEFAULT_THRESHOLDS = {
        # 维度评分等级
        'dim_excellent': 80,   # >= 80 → 优秀
        'dim_good': 60,        # >= 60 → 良好
        'dim_fair': 40,        # >= 40 → 一般 (否则 较差)
        # 碰撞风险等级
        'collision_low': 20,   # <= 20 → 低风险
        'collision_medium': 50, # <= 50 → 中等风险 (否则 高风险)
        # 舒适度等级
        'comfort_good': 70,    # >= 70 → 良好
        'comfort_fair': 40,    # >= 40 → 一般 (否则 较差)
        # Jerk 阈值 (m/s³)
        'jerk_comfortable': 3.0,
        'jerk_acceptable': 6.0,
        # VDV 阈值 (m/s^1.75)
        'vdv_comfortable': 1.0,
        'vdv_acceptable': 2.0,
        # TTC 安全阈值 (秒)
        'ttc_safe': 3.0,
        'ttc_caution': 1.5,
        # 制动距离裕度 (米)
        'brake_margin_min': 20.0,
        # 因素贡献等级
        'factor_high': 50,
        'factor_medium': 20,
        # 默认回退值
        'default_ttc': 5.0,
        'default_brake': 45.0,
        'default_economy': 0.5,
        'default_compliance': 0.5,
    }

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None

        self._latest_report = None
        self._latest_event = None
        self._event_history = deque(maxlen=100)
        self._category_counts = {cat: 0 for cat in BehaviorCategory}
        self._dim_values = {k: 0.5 for k in DIM_KEYS}

        # 加载可配置阈值
        self._thresholds = dict(self._DEFAULT_THRESHOLDS)
        self._load_thresholds()

        self._init_ui()

    def _load_thresholds(self):
        """从 config_manager 加载 Dashboard 显示阈值, 回退到默认值"""
        if self.config_manager is None:
            return
        try:
            section = self.config_manager.get_section("DashboardThresholds")
            if section:
                for key in self._DEFAULT_THRESHOLDS:
                    if key in section:
                        self._thresholds[key] = float(section[key])
                self.logger.debug("Dashboard 显示阈值已从配置加载")
        except Exception as e:
            self.logger.debug(f"加载 Dashboard 阈值失败, 使用默认值: {e}")

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
        content.setObjectName("dashboardContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(self._build_overview_card())

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._build_dimension_table())
        row1.addWidget(self._build_category_table())
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self._build_stability_card())
        row2.addWidget(self._build_collision_card())
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(self._build_comfort_card())
        row3.addWidget(self._build_factor_card())
        layout.addLayout(row3)

        layout.addWidget(self._build_event_table())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _make_card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setFlat(False)
        card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 11px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        return card

    def _make_table(self, headers: list, rows: int = 0) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setStyleSheet(
            "QTableWidget { border: 1px solid #e0e0e0; gridline-color: #ecf0f1; "
            "alternate-background-color: #f8f9fa; font-size: 10px; }"
            "QHeaderView::section { background-color: #f5f6fa; border: 1px solid #e0e0e0; "
            "padding: 3px; font-weight: bold; font-size: 9px; }"
        )
        if rows > 0:
            table.setRowCount(rows)
            self._fit_table_height(table, rows)
        return table

    def _fit_table_height(self, table: QTableWidget, row_count: int):
        h = table.horizontalHeader().height() + 2
        for r in range(row_count):
            h += table.rowHeight(r) if table.rowHeight(r) > 0 else 26
        table.setMinimumHeight(h)
        table.setMaximumHeight(h)

    def _set_cell(self, table, row: int, col: int, text: str,
                   color: str = "#2c3e50", bold: bool = False):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        font = QFont("Microsoft YaHei", 9, QFont.Bold if bold else QFont.Normal)
        item.setFont(font)
        item.setForeground(QColor(color))
        table.setItem(row, col, item)

    # ================================================================
    # 区块1: 驾驶状态概览（数据卡片）
    # ================================================================
    def _build_overview_card(self) -> QGroupBox:
        card = self._make_card("📊 驾驶状态概览")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(4)

        cards_def = [
            ("state", "驾驶状态", "", 0, 0),
            ("risk", "风险等级", "", 0, 1),
            ("score", "驾驶评分", "", 0, 2),
            ("speed", "当前车速", "km/h", 0, 3),
            ("ax", "纵加速度", "m/s²", 1, 0),
            ("ay", "横加速度", "m/s²", 1, 1),
            ("gz", "横摆角速度", "rad/s", 1, 2),
            ("wheel", "方向盘角", "deg", 1, 3),
        ]

        self._data_cards = {}
        for key, title, unit, row, col in cards_def:
            card_w = DataCard(title, unit)
            grid.addWidget(card_w, row, col)
            self._data_cards[key] = card_w

        layout.addLayout(grid)
        return card

    # ================================================================
    # 区块2: 五维驾驶评估（QTableWidget）
    # ================================================================
    def _build_dimension_table(self) -> QGroupBox:
        card = self._make_card("📐 五维驾驶评估")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["维度", "评分", "等级", "说明"]
        self._dim_table = self._make_table(headers, len(DIM_LABELS))

        for i, label in enumerate(DIM_LABELS):
            self._set_cell(self._dim_table, i, 0, label)
            self._set_cell(self._dim_table, i, 1, "--", "#95a5a6")
            self._set_cell(self._dim_table, i, 2, "--", "#95a5a6")
            self._set_cell(self._dim_table, i, 3, "等待数据...", "#95a5a6")

        layout.addWidget(self._dim_table)
        return card

    # ================================================================
    # 区块3: 行为分类统计（QTableWidget）
    # ================================================================
    def _build_category_table(self) -> QGroupBox:
        card = self._make_card("📈 行为分类统计")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["行为类别", "事件数", "占比", "趋势"]
        self._cat_table = self._make_table(headers, 5)

        cats = [
            BehaviorCategory.NORMAL,
            BehaviorCategory.LONGITUDINAL,
            BehaviorCategory.LATERAL,
            BehaviorCategory.COMPOSITE,
            BehaviorCategory.ANOMALY,
        ]
        for i, cat in enumerate(cats):
            label = CAT_LABELS_CN.get(cat, cat.value)
            color = CAT_COLORS.get(cat, "#95a5a6")
            self._set_cell(self._cat_table, i, 0, label, color, True)
            self._set_cell(self._cat_table, i, 1, "0", "#95a5a6")
            self._set_cell(self._cat_table, i, 2, "0%", "#95a5a6")
            self._set_cell(self._cat_table, i, 3, "--", "#95a5a6")

        layout.addWidget(self._cat_table)
        return card

    # ================================================================
    # 区块4: 稳定性裕度（卡片式表格）
    # ================================================================
    def _build_stability_card(self) -> QGroupBox:
        card = self._make_card("🛡️ 稳定性裕度")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["指标", "数值", "评估"]
        self._stability_table = self._make_table(headers, 4)

        rows = [
            ("综合裕度", "--", "--"),
            ("侧向加速度裕度", "--", "--"),
            ("横摆角速度裕度", "--", "--"),
            ("侧倾稳定性", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(rows):
            self._set_cell(self._stability_table, i, 0, label)
            self._set_cell(self._stability_table, i, 1, val, "#95a5a6")
            self._set_cell(self._stability_table, i, 2, status, "#95a5a6")

        layout.addWidget(self._stability_table)
        return card

    # ================================================================
    # 区块5: 碰撞风险评估（卡片式表格）
    # ================================================================
    def _build_collision_card(self) -> QGroupBox:
        card = self._make_card("💥 碰撞风险评估")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["指标", "数值", "评估"]
        self._collision_table = self._make_table(headers, 3)

        rows = [
            ("碰撞风险", "--", "--"),
            ("TTC (碰撞时间)", "--", "--"),
            ("制动距离裕度", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(rows):
            self._set_cell(self._collision_table, i, 0, label)
            self._set_cell(self._collision_table, i, 1, val, "#95a5a6")
            self._set_cell(self._collision_table, i, 2, status, "#95a5a6")

        layout.addWidget(self._collision_table)
        return card

    # ================================================================
    # 区块6: 舒适性指标（卡片式表格）
    # ================================================================
    def _build_comfort_card(self) -> QGroupBox:
        card = self._make_card("🪑 舒适性指标 (ISO 2631)")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["指标", "数值", "评估"]
        self._comfort_table = self._make_table(headers, 3)

        rows = [
            ("舒适度", "--", "--"),
            ("加加速度 (Jerk)", "--", "--"),
            ("振动剂量 (VDV)", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(rows):
            self._set_cell(self._comfort_table, i, 0, label)
            self._set_cell(self._comfort_table, i, 1, val, "#95a5a6")
            self._set_cell(self._comfort_table, i, 2, status, "#95a5a6")

        layout.addWidget(self._comfort_table)
        return card

    # ================================================================
    # 区块7: 风险因素分解（卡片式表格）
    # ================================================================
    def _build_factor_card(self) -> QGroupBox:
        card = self._make_card("📊 风险因素分解")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["风险因素", "贡献度 (%)", "等级"]
        self._factor_table = self._make_table(headers, 6)

        factor_labels = [
            "激进加速", "急转弯", "紧急制动",
            "频繁变道", "蛇形驾驶", "其他因素",
        ]
        for i, label in enumerate(factor_labels):
            self._set_cell(self._factor_table, i, 0, label)
            self._set_cell(self._factor_table, i, 1, "0", "#95a5a6")
            self._set_cell(self._factor_table, i, 2, "--", "#95a5a6")

        layout.addWidget(self._factor_table)
        return card

    # ================================================================
    # 区块8: 最近事件摘要（QTableWidget）
    # ================================================================
    def _build_event_table(self) -> QGroupBox:
        card = self._make_card("📋 最近事件摘要")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["时间", "行为", "风险等级", "评分", "持续(s)", "置信度"]
        self._event_table = self._make_table(headers, 0)

        layout.addWidget(self._event_table)
        return card

    # ================================================================
    # 数据更新入口
    # ================================================================
    def update_sensor_data(self, data):
        """接收传感器原始数据（回放模式），驾驶评估面板暂不处理原始传感器数据"""
        pass

    def update_frame_result(self, result):
        if result is None:
            return

        now = time.time()
        if now - getattr(self, '_last_update', 0) < 0.1:
            return
        self._last_update = now

        if not hasattr(self, '_dr_update_count'):
            self._dr_update_count = 0
        self._dr_update_count += 1

        state = result.state
        raw = result.raw_data or {}
        event = result.event

        if self._dr_update_count <= 3 or self._dr_update_count % 50 == 0:
            has_event = bool(event)
            has_risk = bool(getattr(result, 'risk', None))
            rr = event.metadata.get('risk_report') if event else None
            rr_type = type(rr).__name__ if rr else 'None'
            self.logger.debug(
                f"[驾驶评估] #{self._dr_update_count} state={state} "
                f"has_event={has_event} has_risk={has_risk} risk_report_type={rr_type}"
            )

        self._update_overview(state, raw, event)

        if event:
            self._event_history.append(event)
            cat = event.category
            self._category_counts[cat] = self._category_counts.get(cat, 0) + 1

            risk_report = event.metadata.get('risk_report')
            if not isinstance(risk_report, RiskReport):
                risk_report = getattr(result, 'risk', None)
            if isinstance(risk_report, RiskReport):
                self._latest_report = risk_report
                self._update_dimensions(risk_report)
                self._update_stability(risk_report)
                self._update_collision(risk_report)
                self._update_comfort(risk_report)
                self._update_factors(risk_report, event)

            self._update_category_table()
            self._update_event_table()

    def _update_overview(self, state, raw, event):
        state_label = STATE_LABELS_CN.get(state, "未知")
        if state_label == "未知" and _registry_available:
            registry = get_global_registry()
            state_label = registry.get_driving_state_cn_label(state.name.lower())

        state_color = "#27ae60" if state in (DrivingState.STRAIGHT_CRUISE,) else \
                      "#f1c40f" if state in (DrivingState.ACCELERATING, DrivingState.BRAKING) else \
                      "#3498db" if state in (DrivingState.TURNING_LEFT, DrivingState.TURNING_RIGHT,
                                             DrivingState.LANE_CHANGING) else \
                      "#9b59b6" if state == DrivingState.STOPPED else "#95a5a6"

        if state_color == "#95a5a6" and _registry_available:
            registry = get_global_registry()
            for meta in registry.driving_states.values():
                if meta.display_name_cn == state_label:
                    state_color = meta.color_hex
                    break

        self._data_cards["state"].set_value(state_label, state_color)

        if event:
            risk_label = RISK_LABELS_CN.get(event.risk_level, "未知")
            risk_color = RISK_COLORS_HEX.get(event.risk_level, "#95a5a6")
            self._data_cards["risk"].set_value(risk_label, risk_color)
            self._data_cards["score"].set_value(f"{max(0, min(100, 100 - event.risk_score)):.0f}")
            self._last_risk_label = risk_label
            self._last_risk_color = risk_color
            self._last_score = f"{max(0, min(100, 100 - event.risk_score)):.0f}"
        elif hasattr(self, '_last_risk_label'):
            self._data_cards["risk"].set_value(self._last_risk_label, self._last_risk_color)
            self._data_cards["score"].set_value(self._last_score)

        # 优先使用 speed_kmh (UI显示单位)
        speed_kmh = raw.get('speed_kmh')
        if speed_kmh is not None:
            speed = float(speed_kmh)
        else:
            # 如果没有 speed_kmh，从 m/s 转换
            speed_ms = raw.get('speed', raw.get('车速', 0.0))
            speed = float(speed_ms) * 3.6 if speed_ms else 0.0
        
        ax = raw.get('ax', raw.get('accel_x', 0.0))
        ay = raw.get('ay', raw.get('accel_y', 0.0))
        gz = raw.get('gz', raw.get('gyro_z', 0.0))
        wheel = raw.get('wheel', raw.get('steering', 0.0))

        self._data_cards["speed"].set_value(f"{speed:.1f}" if speed is not None else "--")
        self._data_cards["ax"].set_value(f"{float(ax):.2f}" if ax else "--")
        self._data_cards["ay"].set_value(f"{float(ay):.2f}" if ay else "--")
        self._data_cards["gz"].set_value(f"{float(gz):.2f}" if gz else "--")
        self._data_cards["wheel"].set_value(f"{float(wheel):.1f}" if wheel else "--")

    def _update_dimensions(self, report: RiskReport):
        t = self._thresholds
        default_eco = t['default_economy']
        default_comp = t['default_compliance']

        dim_data = {
            "stability": (int(report.stability_margin * 100), report.stability_margin),
            "safety": (int((1 - report.collision_risk) * 100), 1 - report.collision_risk),
            "comfort": (int((1 - report.comfort_index) * 100), 1 - report.comfort_index),
            "economy": (int(default_eco * 100), default_eco),
            "compliance": (int(default_comp * 100), default_comp),
        }
        
        factors = report.factors
        eco_val = factors.get('fuel_efficiency', default_eco)
        comp_val = factors.get('compliance_score', default_comp)
        dim_data["economy"] = (int(eco_val * 100), eco_val)
        dim_data["compliance"] = (int(comp_val * 100), comp_val)

        self._dim_table.setUpdatesEnabled(False)
        for i, key in enumerate(DIM_KEYS):
            score, raw_val = dim_data.get(key, (50, 0.5))
            self._dim_values[key] = raw_val

            if score >= t['dim_excellent']:
                grade, color = "优秀", "#27ae60"
            elif score >= t['dim_good']:
                grade, color = "良好", "#2980b9"
            elif score >= t['dim_fair']:
                grade, color = "一般", "#f1c40f"
            else:
                grade, color = "较差", "#e74c3c"

            desc_map = {
                "stability": "侧向/横摆裕度充足" if score >= 70 else "裕度偏低，需关注",
                "safety": "TTC>3s, 制动充足" if score >= 70 else "碰撞风险偏高",
                "comfort": "Jerk/VDV 可接受" if score >= 70 else "舒适性偏低",
                "economy": "加减速平顺" if score >= 70 else "能耗偏高",
                "compliance": "无违规变道/超速" if score >= 70 else "存在违规行为",
            }

            self._set_cell(self._dim_table, i, 1, str(score), color, True)
            self._set_cell(self._dim_table, i, 2, grade, color)
            self._set_cell(self._dim_table, i, 3, desc_map.get(key, "--"), "#7f8c8d")
        self._dim_table.setUpdatesEnabled(True)

    def _update_category_table(self):
        total = sum(self._category_counts.values()) or 1
        cats = [
            BehaviorCategory.NORMAL,
            BehaviorCategory.LONGITUDINAL,
            BehaviorCategory.LATERAL,
            BehaviorCategory.COMPOSITE,
            BehaviorCategory.ANOMALY,
        ]

        state_key = tuple(self._category_counts.get(c, 0) for c in cats)
        if state_key == getattr(self, '_last_cat_state', None):
            return
        self._last_cat_state = state_key

        self._cat_table.setUpdatesEnabled(False)
        for i, cat in enumerate(cats):
            cnt = self._category_counts.get(cat, 0)
            pct = cnt / total * 100
            self._set_cell(self._cat_table, i, 1, str(cnt))
            self._set_cell(self._cat_table, i, 2, f"{pct:.0f}%")

            bar_len = int(pct / 10)
            trend = "█" * min(bar_len, 10) + "░" * max(0, 10 - bar_len)
            if cnt == 0:
                trend_label = "--"
            elif pct > 50:
                trend_label = f"{trend} 偏高"
            else:
                trend_label = f"{trend} 正常"
            self._set_cell(self._cat_table, i, 3, trend_label, "#7f8c8d")
        self._cat_table.setUpdatesEnabled(True)

    def _update_event_table(self):
        recent = list(self._event_history)[-20:]
        new_count = len(recent)
        old_count = getattr(self, '_last_event_table_count', 0)

        if new_count == old_count:
            return

        self._event_table.setUpdatesEnabled(False)
        self._event_table.setRowCount(new_count)
        if new_count:
            self._fit_table_height(self._event_table, new_count)

        for i, ev in enumerate(reversed(recent)):
            t = time.strftime('%H:%M:%S', time.localtime(ev.end_time))
            ms = int((ev.end_time - int(ev.end_time)) * 1000)
            t = f"{t}.{ms:03d}"
            risk_label = RISK_LABELS_CN.get(ev.risk_level, "?")
            risk_color = RISK_COLORS_HEX.get(ev.risk_level, "#95a5a6")

            self._set_cell(self._event_table, i, 0, t, "#7f8c8d")
            self._set_cell(self._event_table, i, 1, ev.label_cn)
            self._set_cell(self._event_table, i, 2, risk_label, risk_color, True)
            self._set_cell(self._event_table, i, 3, f"{ev.risk_score:.0f}")
            self._set_cell(self._event_table, i, 4, f"{ev.duration:.1f}")
            self._set_cell(self._event_table, i, 5, f"{ev.confidence:.2f}")

        self._event_table.setUpdatesEnabled(True)
        self._last_event_table_count = new_count

    # ================================================================
    # 风险评估更新方法（卡片式表格）
    # ================================================================
    def _update_stability(self, report: RiskReport):
        margin_pct = int(max(0, min(100, report.stability_margin * 100)))

        if margin_pct >= 70:
            color, status = "#27ae60", "良好"
        elif margin_pct >= 40:
            color, status = "#f1c40f", "一般"
        else:
            color, status = "#e74c3c", "较差"

        self._stability_table.setUpdatesEnabled(False)
        self._set_cell(self._stability_table, 0, 1, f"{margin_pct}%", color, True)
        self._set_cell(self._stability_table, 0, 2, status, color, True)

        factors = report.factors
        lat_val = factors.get('lateral_accel_margin', 2.5)
        lat_rem = factors.get('lateral_remaining_pct', 60)
        lat_color = "#27ae60" if lat_rem > 40 else "#e74c3c"
        self._set_cell(self._stability_table, 1, 1, f"{lat_val:.2f} m/s²")
        self._set_cell(self._stability_table, 1, 2, f"剩余 {lat_rem:.0f}%", lat_color)

        yaw_val = factors.get('yaw_rate_margin', 0.8)
        yaw_rem = factors.get('yaw_remaining_pct', 70)
        yaw_color = "#27ae60" if yaw_rem > 40 else "#e74c3c"
        self._set_cell(self._stability_table, 2, 1, f"{yaw_val:.2f} rad/s")
        self._set_cell(self._stability_table, 2, 2, f"剩余 {yaw_rem:.0f}%", yaw_color)

        roll_val = factors.get('roll_stability', 0.9)
        roll_status = "稳定" if roll_val > 0.7 else "注意"
        roll_color = "#27ae60" if roll_val > 0.7 else "#e67e22"
        self._set_cell(self._stability_table, 3, 1, f"{roll_val:.2f}")
        self._set_cell(self._stability_table, 3, 2, roll_status, roll_color)
        self._stability_table.setUpdatesEnabled(True)

    def _update_collision(self, report: RiskReport):
        t = self._thresholds
        risk_pct = int(max(0, min(100, report.collision_risk * 100)))

        if risk_pct <= t['collision_low']:
            color, status = "#27ae60", "低风险"
        elif risk_pct <= t['collision_medium']:
            color, status = "#f1c40f", "中等风险"
        else:
            color, status = "#e74c3c", "高风险"

        self._collision_table.setUpdatesEnabled(False)
        self._set_cell(self._collision_table, 0, 1, f"{risk_pct}%", color, True)
        self._set_cell(self._collision_table, 0, 2, status, color, True)

        factors = report.factors
        ttc = factors.get('ttc', t['default_ttc'])
        ttc_status = "安全" if ttc > t['ttc_safe'] else "注意" if ttc > t['ttc_caution'] else "危险"
        ttc_color = "#27ae60" if ttc > t['ttc_safe'] else "#f1c40f" if ttc > t['ttc_caution'] else "#e74c3c"
        self._set_cell(self._collision_table, 1, 1, f"{ttc:.1f} s")
        self._set_cell(self._collision_table, 1, 2, ttc_status, ttc_color)

        brake = factors.get('brake_distance_margin', t['default_brake'])
        brake_status = "充足" if brake > t['brake_margin_min'] else "不足"
        brake_color = "#27ae60" if brake > t['brake_margin_min'] else "#e74c3c"
        self._set_cell(self._collision_table, 2, 1, f"{brake:.1f} m")
        self._set_cell(self._collision_table, 2, 2, brake_status, brake_color)
        self._collision_table.setUpdatesEnabled(True)

    def _update_comfort(self, report: RiskReport):
        t = self._thresholds
        comfort_pct = int(max(0, min(100, (1 - report.comfort_index) * 100)))

        if comfort_pct >= t['comfort_good']:
            color, status = "#27ae60", "良好"
        elif comfort_pct >= t['comfort_fair']:
            color, status = "#f1c40f", "一般"
        else:
            color, status = "#e74c3c", "较差"

        self._comfort_table.setUpdatesEnabled(False)
        self._set_cell(self._comfort_table, 0, 1, f"{comfort_pct}%", color, True)
        self._set_cell(self._comfort_table, 0, 2, status, color, True)

        factors = report.factors
        jerk = factors.get('jerk', 2.0)
        jerk_status = "舒适" if jerk < t['jerk_comfortable'] else "可接受" if jerk < t['jerk_acceptable'] else "不适"
        jerk_color = "#27ae60" if jerk < t['jerk_comfortable'] else "#f1c40f" if jerk < t['jerk_acceptable'] else "#e74c3c"
        self._set_cell(self._comfort_table, 1, 1, f"{jerk:.2f} m/s³")
        self._set_cell(self._comfort_table, 1, 2, jerk_status, jerk_color)

        vdv = factors.get('vdv', 0.8)
        vdv_status = "舒适" if vdv < t['vdv_comfortable'] else "可接受" if vdv < t['vdv_acceptable'] else "不适"
        vdv_color = "#27ae60" if vdv < t['vdv_comfortable'] else "#f1c40f" if vdv < t['vdv_acceptable'] else "#e74c3c"
        self._set_cell(self._comfort_table, 2, 1, f"{vdv:.2f} m/s^1.75")
        self._set_cell(self._comfort_table, 2, 2, vdv_status, vdv_color)
        self._comfort_table.setUpdatesEnabled(True)

    def _update_factors(self, report: RiskReport, event: ManeuverEvent):
        t = self._thresholds
        factors = report.factors
        factor_contrib = factors.get('factor_contributions', {})

        if not factor_contrib:
            behavior = event.type
            if 'aggressive' in behavior or 'emergency' in behavior:
                factor_contrib = {event.label_cn: 60, "其他因素": 40}
            else:
                factor_contrib = {event.label_cn: 40, "其他因素": 60}

        factor_labels = [
            "激进加速", "急转弯", "紧急制动",
            "频繁变道", "蛇形驾驶", "其他因素",
        ]
        self._factor_table.setUpdatesEnabled(False)
        for i, label in enumerate(factor_labels):
            val = factor_contrib.get(label, 0)
            self._set_cell(self._factor_table, i, 1, f"{val:.0f}")

            if val >= t['factor_high']:
                lvl, lvl_color = "高", "#e74c3c"
            elif val >= t['factor_medium']:
                lvl, lvl_color = "中", "#f1c40f"
            elif val > 0:
                lvl, lvl_color = "低", "#27ae60"
            else:
                lvl, lvl_color = "--", "#95a5a6"

            self._set_cell(self._factor_table, i, 2, lvl, lvl_color, True)
        self._factor_table.setUpdatesEnabled(True)

    def reset(self):
        self._latest_report = None
        self._latest_event = None
        self._event_history.clear()
        self._category_counts = {cat: 0 for cat in BehaviorCategory}
        self._dim_values = {k: 0.5 for k in DIM_KEYS}

        for card in self._data_cards.values():
            card.set_value("--", "#95a5a6")

        for i, label in enumerate(DIM_LABELS):
            self._set_cell(self._dim_table, i, 1, "--", "#95a5a6")
            self._set_cell(self._dim_table, i, 2, "--", "#95a5a6")
            self._set_cell(self._dim_table, i, 3, "等待数据...", "#95a5a6")

        cats = [
            BehaviorCategory.NORMAL, BehaviorCategory.LONGITUDINAL,
            BehaviorCategory.LATERAL, BehaviorCategory.COMPOSITE,
            BehaviorCategory.ANOMALY,
        ]
        for i, cat in enumerate(cats):
            self._set_cell(self._cat_table, i, 1, "0", "#95a5a6")
            self._set_cell(self._cat_table, i, 2, "0%", "#95a5a6")
            self._set_cell(self._cat_table, i, 3, "--", "#95a5a6")

        self._event_table.setRowCount(0)

        stability_rows = [
            ("综合裕度", "--", "--"),
            ("侧向加速度裕度", "--", "--"),
            ("横摆角速度裕度", "--", "--"),
            ("侧倾稳定性", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(stability_rows):
            self._set_cell(self._stability_table, i, 0, label)
            self._set_cell(self._stability_table, i, 1, val, "#95a5a6")
            self._set_cell(self._stability_table, i, 2, status, "#95a5a6")

        collision_rows = [
            ("碰撞风险", "--", "--"),
            ("TTC (碰撞时间)", "--", "--"),
            ("制动距离裕度", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(collision_rows):
            self._set_cell(self._collision_table, i, 0, label)
            self._set_cell(self._collision_table, i, 1, val, "#95a5a6")
            self._set_cell(self._collision_table, i, 2, status, "#95a5a6")

        comfort_rows = [
            ("舒适度", "--", "--"),
            ("加加速度 (Jerk)", "--", "--"),
            ("振动剂量 (VDV)", "--", "--"),
        ]
        for i, (label, val, status) in enumerate(comfort_rows):
            self._set_cell(self._comfort_table, i, 0, label)
            self._set_cell(self._comfort_table, i, 1, val, "#95a5a6")
            self._set_cell(self._comfort_table, i, 2, status, "#95a5a6")

        factor_labels = [
            "激进加速", "急转弯", "紧急制动",
            "频繁变道", "蛇形驾驶", "其他因素",
        ]
        for i, label in enumerate(factor_labels):
            self._set_cell(self._factor_table, i, 0, label)
            self._set_cell(self._factor_table, i, 1, "0", "#95a5a6")
            self._set_cell(self._factor_table, i, 2, "--", "#95a5a6")
