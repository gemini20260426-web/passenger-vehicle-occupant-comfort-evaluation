#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件管理面板 — 表格形式
包含类型筛选标签栏、事件表格、批量操作工具栏
"""

import logging
from typing import Dict, List, Optional, Any
from collections import OrderedDict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QCheckBox, QSizePolicy, QGridLayout,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QStyleOptionButton, QStyle
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter

LC = {
    'bg_primary': '#FFFFFF', 'bg_card': '#FFFFFF', 'bg_input': '#F5F6F8',
    'bg_header': '#EBEDF0', 'bg_hover': '#E8F0FE', 'bg_tag': '#F0F4F8',
    'accent': '#4A90D9', 'accent_hover': '#357ABD', 'accent_light': 'rgba(74,144,217,0.10)',
    'text_primary': '#333333', 'text_secondary': '#666666', 'text_muted': '#999999',
    'text_accent': '#4A90D9', 'border_default': '#D0D0D0', 'border_light': '#E0E0E0',
    'success': '#27AE60', 'warning': '#F39C12', 'danger': '#E74C3C',
    'info': '#4A90D9', 'orange_dark': '#E67E22',
    'exp_color': '#4A90D9', 'ctrl_color': '#E67E22',
}

CARD_STYLE = """
    QFrame#proCard {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 6px;
    }
"""

TABLE_STYLE = """
    QTableWidget {
        background-color: #F5F6F8;
        border: 1px solid #D0D0D0;
        border-radius: 4px;
        gridline-color: #E0E0E0;
        font-size: 10px;
    }
    QTableWidget::item {
        padding: 4px 6px;
        color: #333333;
    }
    QHeaderView::section {
        background-color: #EBEDF0;
        color: #666666;
        border: none;
        border-bottom: 1px solid #D0D0D0;
        padding: 6px 8px;
        font-size: 9px;
        font-weight: 600;
    }
"""

from core.core.seat_evaluation.eval_queue import TYPE_COLORS

logger = logging.getLogger(__name__)


class CheckBoxDelegate(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
        self.layout.addWidget(self.checkbox)


class EventTypeTagBar(QWidget):
    """事件类型筛选标签栏"""
    type_selected = Signal(str)
    type_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._type_labels: Dict[str, str] = {}
        self._type_colors: Dict[str, str] = {}
        self._type_counts: Dict[str, int] = {}
        self._type_eval_counts: Dict[str, int] = {}
        self._tag_buttons: Dict[str, QPushButton] = {}
        self._selected_type: Optional[str] = None
        self._all_count = 0
        self._all_eval_count = 0
        self._init_ui()

    def _init_ui(self):
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(42)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollBar:horizontal { height: 8px; background: transparent; }"
            "QScrollBar::handle:horizontal { background: #C0C4CC; border-radius: 4px; min-width: 20px; }"
            "QScrollBar::handle:horizontal:hover { background: #909399; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        )

        self._scroll_content = QWidget()
        self._scroll_layout = QHBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)
        self._scroll_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._main_layout.addWidget(self._scroll)

    def set_type_info(self, type_labels: Dict[str, str], type_colors: Dict[str, str]):
        self._type_labels = type_labels
        self._type_colors = type_colors

    def update_counts(self, type_counts: Dict[str, int], type_eval_counts: Dict[str, int]):
        self._type_counts = type_counts
        self._type_eval_counts = type_eval_counts
        self._all_count = sum(type_counts.values())
        self._all_eval_count = sum(type_eval_counts.values())
        self._rebuild_tags()

    def _rebuild_tags(self):
        for btn in self._tag_buttons.values():
            btn.deleteLater()
        self._tag_buttons.clear()

        while self._scroll_layout.count() > 1:
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_eval = self._all_eval_count
        all_total = self._all_count
        all_dot = '●' if all_eval > 0 else '○'
        all_color = '#27AE60' if all_eval > 0 else '#999999'
        all_btn = self._make_tag_button(
            f"{all_dot} 全部 {all_total}", 'all',
            all_color, self._selected_type is None
        )
        all_btn.clicked.connect(lambda: self._on_tag_click('all'))
        self._scroll_layout.insertWidget(0, all_btn)
        self._tag_buttons['all'] = all_btn

        if not self._type_counts:
            return

        sorted_types = sorted(self._type_counts.items(), key=lambda x: x[1], reverse=True)
        for etype, count in sorted_types:
            label = self._type_labels.get(etype, etype)
            color = self._type_colors.get(etype, '#95A5A6')
            eval_count = self._type_eval_counts.get(etype, 0)

            dot = '●' if eval_count > 0 else '○'
            text = f"{dot} {label} {count}"

            btn = self._make_tag_button(
                text, etype, color, self._selected_type == etype
            )
            btn.clicked.connect(lambda checked=False, t=etype: self._on_tag_click(t))
            idx = self._scroll_layout.count() - 1
            self._scroll_layout.insertWidget(idx, btn)
            self._tag_buttons[etype] = btn

    def _make_tag_button(self, text: str, tag_id: str, color: str, selected: bool) -> QPushButton:
        btn = QPushButton(text)
        font = QFont()
        font.setPointSize(9)
        btn.setFont(font)
        btn.setFixedHeight(26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if selected:
            bg = color
            fg = '#FFFFFF'
            border = color
        else:
            bg = '#F5F6F8'
            fg = color
            border = '#D0D0D0'

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
                border-color: {color};
            }}
        """)
        return btn

    def _on_tag_click(self, tag_id: str):
        if self._selected_type == tag_id and tag_id != 'all':
            self._selected_type = None
            self._rebuild_tags()
            self.type_selected.emit('')
        elif tag_id == 'all':
            self._selected_type = None
            self._rebuild_tags()
            self.type_selected.emit('')
        else:
            self._selected_type = tag_id
            self._rebuild_tags()
            self.type_selected.emit(tag_id)


class EventManagerPanel(QWidget):
    """事件管理子Tab - 表格形式"""
    event_selected = Signal(str)
    events_checked_changed = Signal(list)
    evaluate_requested = Signal(list)
    evaluate_all_requested = Signal()
    evaluate_type_requested = Signal(str)
    refresh_requested = Signal()
    clear_results_requested = Signal()
    group_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue_engine = None
        self._records: Dict[str, Any] = {}
        self._filter_type: Optional[str] = None
        self._checked_ids: set = set()
        self._type_labels: Dict[str, str] = {}
        self._type_colors: Dict[str, str] = {}
        self._active_group_tags: List[str] = ['experimental', 'control']
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(6)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        header_card = QFrame()
        header_card.setObjectName("proCard")
        header_card.setStyleSheet(CARD_STYLE)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("驾驶事件评测管理")
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};"
            f"padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px;"
        )
        title_row.addWidget(self._count_label)
        header_layout.addLayout(title_row)

        self._tag_bar = EventTypeTagBar()
        self._tag_bar.type_selected.connect(self._on_type_filter)
        header_layout.addWidget(self._tag_bar)

        outer_layout.addWidget(header_card)

        table_card = QFrame()
        table_card.setObjectName("proCard")
        table_card.setStyleSheet(CARD_STYLE)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(6, 6, 6, 6)
        table_layout.setSpacing(0)

        self._table = QTableWidget()
        self._table.setColumnCount(12)
        self._table.setHorizontalHeaderLabels([
            "", "状态", "事件类型", "组别", "时间窗口", "置信度",
            "匹配规则", "实验组分", "对照组分", "等级", "查看", "评测"
        ])
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Stretch)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        hdr.setSectionResizeMode(10, QHeaderView.Fixed)
        hdr.setSectionResizeMode(11, QHeaderView.Fixed)

        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(1, 40)
        self._table.setColumnWidth(3, 70)
        self._table.setColumnWidth(5, 60)
        self._table.setColumnWidth(7, 70)
        self._table.setColumnWidth(8, 70)
        self._table.setColumnWidth(9, 60)
        self._table.setColumnWidth(10, 60)
        self._table.setColumnWidth(11, 60)

        self._table.cellClicked.connect(self._on_cell_clicked)
        table_layout.addWidget(self._table)

        outer_layout.addWidget(table_card, 1)

        toolbar = QFrame()
        toolbar.setObjectName("proCard")
        toolbar.setStyleSheet(CARD_STYLE)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(6)

        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.setFixedSize(50, 28)
        self._set_btn_outline_style(self._select_all_btn)
        self._select_all_btn.clicked.connect(self._on_select_all)
        tb_layout.addWidget(self._select_all_btn)

        self._invert_btn = QPushButton("反选")
        self._invert_btn.setFixedSize(50, 28)
        self._set_btn_outline_style(self._invert_btn)
        self._invert_btn.clicked.connect(self._on_invert_selection)
        tb_layout.addWidget(self._invert_btn)

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setFixedSize(50, 28)
        self._set_btn_outline_style(self._refresh_btn)
        self._refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        tb_layout.addWidget(self._refresh_btn)

        tb_layout.addSpacing(12)

        group_label = QLabel("评测分组:")
        group_label.setStyleSheet(
            f"color: {LC['text_secondary']}; font-size: 11px; font-weight: 600;"
        )
        tb_layout.addWidget(group_label)

        self._exp_check = QCheckBox("🔬 实验组")
        self._exp_check.setChecked(True)
        self._exp_check.setStyleSheet(f"""
            QCheckBox {{
                color: {LC['exp_color']};
                font-size: 11px;
                font-weight: 600;
                spacing: 4px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        self._exp_check.toggled.connect(self._on_group_changed)
        tb_layout.addWidget(self._exp_check)

        self._ctrl_check = QCheckBox("📊 对照组")
        self._ctrl_check.setChecked(True)
        self._ctrl_check.setStyleSheet(f"""
            QCheckBox {{
                color: {LC['ctrl_color']};
                font-size: 11px;
                font-weight: 600;
                spacing: 4px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        self._ctrl_check.toggled.connect(self._on_group_changed)
        tb_layout.addWidget(self._ctrl_check)

        tb_layout.addStretch()

        self._selected_count_label = QLabel("已选: 0")
        self._selected_count_label.setStyleSheet(
            f"color: {LC['accent']}; font-size: 11px; font-weight: 600;"
        )
        tb_layout.addWidget(self._selected_count_label)

        self._evaluate_selected_btn = self._make_primary_btn("评测所选")
        self._evaluate_selected_btn.clicked.connect(self._on_evaluate_selected)
        tb_layout.addWidget(self._evaluate_selected_btn)

        self._evaluate_all_btn = QPushButton("评测全部")
        self._evaluate_all_btn.setFixedHeight(28)
        self._evaluate_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #27AE60;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #219A52; }}
            QPushButton:disabled {{
                background-color: #D0D0D0;
                color: {LC['text_muted']};
            }}
        """)
        self._evaluate_all_btn.clicked.connect(lambda: self.evaluate_all_requested.emit())
        tb_layout.addWidget(self._evaluate_all_btn)

        self._clear_btn = QPushButton("清除结果")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {LC['danger']};
                border: 1px solid {LC['danger']};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: rgba(231,76,60,0.10);
            }}
        """)
        self._clear_btn.clicked.connect(lambda: self.clear_results_requested.emit())
        tb_layout.addWidget(self._clear_btn)

        outer_layout.addWidget(toolbar)

    def _make_primary_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LC['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {LC['accent_hover']}; }}
            QPushButton:disabled {{
                background-color: #D0D0D0;
                color: {LC['text_muted']};
            }}
        """)
        return btn

    def _set_btn_outline_style(self, btn: QPushButton):
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {LC['text_secondary']};
                border: 1px solid {LC['border_default']};
                border-radius: 4px;
                font-size: 10px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {LC['text_accent']};
                border-color: {LC['accent']};
                background-color: {LC['accent_light']};
            }}
        """)

    def set_queue_engine(self, engine):
        self._queue_engine = engine

    def rebuild(self, records: List[Any], type_labels: Dict[str, str] = None,
                type_colors: Dict[str, str] = None):
        self._records = {}
        for r in records:
            self._records[r.event_id] = r

        self._type_labels = type_labels or {}
        self._type_colors = type_colors or {}

        self._update_tag_bar()
        self._rebuild_table()

    def _update_tag_bar(self):
        type_counts = {}
        type_eval_counts = {}
        for r in self._records.values():
            type_counts[r.event_type] = type_counts.get(r.event_type, 0) + 1
            if r.is_evaluated:
                type_eval_counts[r.event_type] = type_eval_counts.get(r.event_type, 0) + 1

        self._tag_bar.set_type_info(self._type_labels, self._type_colors)
        self._tag_bar.update_counts(type_counts, type_eval_counts)

    def _get_visible_records(self) -> List:
        records = list(self._records.values())
        records.sort(key=lambda r: r.start_ts)

        if self._filter_type:
            records = [r for r in records if r.event_type == self._filter_type]
        return records

    def _rebuild_table(self):
        visible = self._get_visible_records()
        self._table.setRowCount(len(visible))

        total = len(self._records)
        evaluated = sum(1 for r in self._records.values() if r.is_evaluated)
        pending = total - evaluated
        self._count_label.setText(
            f"总计 {total} 个事件 | 已评测 {evaluated} | 待评测 {pending}"
        )

        for row_idx, r in enumerate(visible):
            # 复选框
            checkbox = QCheckBox()
            checkbox.setStyleSheet("QCheckBox::indicator { width: 16px; height: 16px; }")
            checkbox.setChecked(r.event_id in self._checked_ids)
            checkbox.setProperty('event_id', r.event_id)
            checkbox.stateChanged.connect(lambda state, eid=r.event_id: self._on_checkbox_changed(state, eid))
            self._table.setCellWidget(row_idx, 0, checkbox)

            # 状态
            status_item = QTableWidgetItem(r.status_icon)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor(r.status_color))
            status_font = status_item.font()
            status_font.setPointSize(14)
            status_font.setBold(True)
            status_item.setFont(status_font)
            status_item.setToolTip({
                'pending': '待评测', 'evaluating': '评测中', 'evaluated': '已评测',
                'stale': '可能过期', 'failed': '失败',
            }.get(r.status, r.status))
            self._table.setItem(row_idx, 1, status_item)

            # 事件类型
            type_cn = r.event_type_cn or r.event_type
            type_color = TYPE_COLORS.get(r.event_type, '#95A5A6')
            type_item = QTableWidgetItem(type_cn)
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setForeground(QColor(type_color))
            type_font = type_item.font()
            type_font.setBold(True)
            type_item.setFont(type_font)
            self._table.setItem(row_idx, 2, type_item)

            # 组别
            active_groups = getattr(r, 'active_groups', [])
            group_text = ""
            if 'experimental' in active_groups and 'control' in active_groups:
                group_text = "实验+对照"
            elif 'experimental' in active_groups:
                group_text = "实验组"
            elif 'control' in active_groups:
                group_text = "对照组"
            else:
                group_text = ""
            group_item = QTableWidgetItem(group_text)
            group_item.setTextAlignment(Qt.AlignCenter)
            if 'experimental' in active_groups:
                group_item.setForeground(QColor(LC['exp_color']))
            elif 'control' in active_groups:
                group_item.setForeground(QColor(LC['ctrl_color']))
            self._table.setItem(row_idx, 3, group_item)

            # 时间窗口
            time_text = f"{r.start_ts:.1f}s → {r.end_ts:.1f}s ({r.duration:.1f}s)"
            time_item = QTableWidgetItem(time_text)
            time_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 4, time_item)

            # 置信度
            conf_text = f"{r.confidence:.0%}" if r.confidence > 0 else ""
            conf_item = QTableWidgetItem(conf_text)
            conf_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 5, conf_item)

            # 匹配规则
            rule_text = r.rule_applied or "自动匹配"
            if r.threshold_multipliers:
                key_mults = list(r.threshold_multipliers.items())[:3]
                mults_text = ', '.join(f"{k}×{v}" for k, v in key_mults)
                rule_text += f" | 阈值: {mults_text}"
            rule_item = QTableWidgetItem(rule_text)
            self._table.setItem(row_idx, 6, rule_item)

            # 分数
            if r.is_evaluated:
                exp_score = r.overall_score
                ctrl_score = r.overall_score_ctrl

                if exp_score is not None:
                    exp_score_text = f"{exp_score:.1f}"
                    exp_color = r.grade_color
                else:
                    exp_score_text = ""
                    exp_color = LC['text_muted']
                exp_score_item = QTableWidgetItem(exp_score_text)
                exp_score_item.setTextAlignment(Qt.AlignCenter)
                exp_score_item.setForeground(QColor(exp_color))
                exp_score_font = exp_score_item.font()
                exp_score_font.setBold(True)
                exp_score_item.setFont(exp_score_font)
                self._table.setItem(row_idx, 7, exp_score_item)

                if ctrl_score is not None:
                    ctrl_score_text = f"{ctrl_score:.1f}"
                    ctrl_color = r.grade_color_ctrl
                else:
                    ctrl_score_text = ""
                    ctrl_color = LC['text_muted']
                ctrl_score_item = QTableWidgetItem(ctrl_score_text)
                ctrl_score_item.setTextAlignment(Qt.AlignCenter)
                ctrl_score_item.setForeground(QColor(ctrl_color))
                ctrl_score_font = ctrl_score_item.font()
                ctrl_score_font.setBold(True)
                ctrl_score_item.setFont(ctrl_score_font)
                self._table.setItem(row_idx, 8, ctrl_score_item)

                grade_text = r.score_grade or ""
                grade_item = QTableWidgetItem(grade_text)
                grade_item.setTextAlignment(Qt.AlignCenter)
                grade_item.setForeground(QColor(r.grade_color))
                grade_font = grade_item.font()
                grade_font.setBold(True)
                grade_item.setFont(grade_font)
                self._table.setItem(row_idx, 9, grade_item)
            else:
                for col in [7, 8, 9]:
                    self._table.setItem(row_idx, col, QTableWidgetItem(""))

            # 查看按钮
            view_btn = QPushButton("查看")
            view_btn.setFixedSize(50, 24)
            view_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {LC['text_accent']};
                    border: 1px solid {LC['border_default']};
                    border-radius: 3px;
                    font-size: 10px;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{
                    background-color: {LC['accent_light']};
                    border-color: {LC['accent']};
                }}
            """)
            view_btn.setProperty('event_id', r.event_id)
            view_btn.clicked.connect(lambda checked, eid=r.event_id: self.event_selected.emit(eid))
            self._table.setCellWidget(row_idx, 10, view_btn)

            # 评测按钮
            eval_btn = QPushButton("评测")
            eval_btn.setFixedSize(50, 24)
            eval_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {LC['accent']};
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-size: 10px;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{
                    background-color: {LC['accent_hover']};
                }}
            """)
            eval_btn.setProperty('event_id', r.event_id)
            eval_btn.clicked.connect(lambda checked, eid=r.event_id: self.evaluate_requested.emit([eid]))
            self._table.setCellWidget(row_idx, 11, eval_btn)

            # 设置行高
            self._table.setRowHeight(row_idx, 36)

        self._update_selection_count()

    def update_record(self, record):
        self._records[record.event_id] = record
        self._update_tag_bar()
        self._rebuild_table()

    def _on_type_filter(self, event_type: str):
        self._filter_type = event_type if event_type else None
        self._rebuild_table()

    def _on_checkbox_changed(self, state, event_id):
        if state == Qt.CheckState.Checked.value:
            self._checked_ids.add(event_id)
        else:
            self._checked_ids.discard(event_id)
        self._update_selection_count()
        self.events_checked_changed.emit(list(self._checked_ids))

    def _on_cell_clicked(self, row, col):
        pass

    def _on_select_all(self):
        visible = self._get_visible_records()
        visible_ids = {r.event_id for r in visible}
        if len(self._checked_ids) == len(visible) and self._checked_ids:
            self._checked_ids.clear()
        else:
            self._checked_ids = visible_ids.copy()
        self._rebuild_table()

    def _on_invert_selection(self):
        visible = self._get_visible_records()
        visible_ids = {r.event_id for r in visible}
        new_checked = set()
        for eid in visible_ids:
            if eid not in self._checked_ids:
                new_checked.add(eid)
        self._checked_ids = new_checked
        self._rebuild_table()

    def _on_evaluate_selected(self):
        if self._checked_ids:
            self.evaluate_requested.emit(list(self._checked_ids))

    def _on_group_changed(self):
        tags = []
        if self._exp_check.isChecked():
            tags.append('experimental')
        if self._ctrl_check.isChecked():
            tags.append('control')
        if not tags:
            self._exp_check.setChecked(True)
            tags = ['experimental']
        self._active_group_tags = tags
        self.group_changed.emit(tags)

    def set_active_group(self, group_tags: list):
        self._exp_check.setChecked('experimental' in group_tags)
        self._ctrl_check.setChecked('control' in group_tags)

    @property
    def active_group_tags(self) -> list:
        return self._active_group_tags

    def _update_selection_count(self):
        total = len(self._get_visible_records())
        selected = len(self._checked_ids)
        self._selected_count_label.setText(f"已选: {selected}/{total}")

    def get_checked_ids(self) -> List[str]:
        return list(self._checked_ids)

    def get_visible_ids(self) -> List[str]:
        return [r.event_id for r in self._get_visible_records()]

    def get_all_records(self) -> list:
        """获取全部事件记录列表"""
        return list(self._records.values())
