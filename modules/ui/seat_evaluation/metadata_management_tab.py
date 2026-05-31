#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
元数据管理中心 — 统一管理指标/阈值/数据源/驾驶行为/字段/算子
提供可视化编辑、快速测试、Schema预览等一站式操作界面
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QGridLayout, QSplitter, QFormLayout,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QTextEdit,
    QMessageBox, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QDialog, QDialogButtonBox, QCheckBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QBrush, QIcon

from core.core.seat_evaluation.metadata_registry import (
    get_global_registry, EvaluationDirection, DataSourceType
)

logger = logging.getLogger(__name__)

STYLE_SHEET = """
QTableWidget {
    font-family: "Microsoft YaHei";
    font-size: 12px;
    gridline-color: #d0d0d0;
    selection-background-color: #d4e6f9;
    selection-color: #333;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background-color: #f0f0f0;
    padding: 6px 8px;
    border: 1px solid #d0d0d0;
    font-weight: bold;
    font-size: 12px;
}
QGroupBox {
    font-family: "Microsoft YaHei";
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    font-family: "Microsoft YaHei";
    font-size: 12px;
    padding: 6px 16px;
    border: 1px solid #bbb;
    border-radius: 4px;
    background-color: #f5f5f5;
}
QPushButton:hover { background-color: #e8f0fe; border-color: #4A90D9; }
QPushButton#btnSave {
    background-color: #4A90D9;
    color: white;
    border: none;
}
QPushButton#btnSave:hover { background-color: #357ABD; }
QPushButton#btnTest {
    background-color: #27AE60;
    color: white;
    border: none;
}
QPushButton#btnTest:hover { background-color: #1E8449; }
QPushButton#btnExport {
    background-color: #F39C12;
    color: white;
    border: none;
}
QPushButton#btnExport:hover { background-color: #D68910; }
QTreeWidget {
    font-family: "Microsoft YaHei";
    font-size: 12px;
}
QTextEdit {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}
"""

GRADE_COLORS = {
    'excellent': '#27AE60',
    'good': '#4A90D9',
    'fair': '#F39C12',
    'poor': '#E74C3C',
    'unknown': '#95A5A6',
}

GRADE_LABELS_CN = {
    'excellent': '优秀',
    'good': '良好',
    'fair': '一般',
    'poor': '差',
    'unknown': '未知',
}

RISK_COLORS = {
    'NORMAL': '#27AE60',
    'WARNING': '#F39C12',
    'DANGER': '#E74C3C',
    'CRITICAL': '#E74C3C',
}


class MetadataManagementTab(QWidget):
    """元数据管理中心 — 全链路元数据可视化编辑界面"""

    thresholds_changed = Signal(str, dict)
    states_changed = Signal()

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._registry = get_global_registry()
        self._edited_thresholds: Dict[str, Dict] = {}
        self._edited_states: Dict[str, Dict] = {}

        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sub_tab = QTabWidget()
        self.sub_tab.setTabPosition(QTabWidget.North)
        self.sub_tab.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #c0c0c0; }
            QTabBar::tab {
                padding: 8px 20px;
                font-family: "Microsoft YaHei";
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #4A90D9;
                color: white;
            }
        """)

        self._build_indicator_threshold_tab()
        self._build_data_source_tab()
        self._build_driving_behavior_tab()
        self._build_field_operator_tab()
        self._build_schema_preview_tab()

        main_layout.addWidget(self.sub_tab)

    def _build_indicator_threshold_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_row = QHBoxLayout()

        search_label = QLabel("搜索:")
        search_label.setFont(QFont("Microsoft YaHei", 11))
        top_row.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入指标代码或中文名过滤...")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._filter_indicator_table)
        top_row.addWidget(self.search_input)

        top_row.addStretch()

        btn_save = QPushButton("保存所有阈值修改")
        btn_save.setObjectName("btnSave")
        btn_save.clicked.connect(self._save_all_thresholds)
        top_row.addWidget(btn_save)

        btn_export = QPushButton("导出阈值 CSV")
        btn_export.setObjectName("btnExport")
        btn_export.clicked.connect(self._export_thresholds_csv)
        top_row.addWidget(btn_export)

        layout.addLayout(top_row)

        self.indicator_table = QTableWidget()
        self.indicator_table.setColumnCount(9)
        self.indicator_table.setHorizontalHeaderLabels([
            "指标代码", "中文名", "维度", "优秀 ≤", "良好 ≤", "一般 ≤", "差 >", "方向", "操作"
        ])
        self.indicator_table.horizontalHeader().setStretchLastSection(True)
        self.indicator_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.indicator_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.indicator_table.setAlternatingRowColors(True)
        self.indicator_table.verticalHeader().setVisible(False)
        layout.addWidget(self.indicator_table)

        quick_test_group = QGroupBox("快速评级测试")
        quick_layout = QHBoxLayout(quick_test_group)

        quick_layout.addWidget(QLabel("指标:"))
        self.quick_indicator_combo = QComboBox()
        codes = sorted(self._registry.metric_thresholds_4level.keys())
        self.quick_indicator_combo.addItems(codes)
        self.quick_indicator_combo.setMinimumWidth(120)
        quick_layout.addWidget(self.quick_indicator_combo)

        quick_layout.addWidget(QLabel("数值:"))
        self.quick_value_spin = QDoubleSpinBox()
        self.quick_value_spin.setRange(-999999, 999999)
        self.quick_value_spin.setDecimals(4)
        self.quick_value_spin.setMinimumWidth(120)
        quick_layout.addWidget(self.quick_value_spin)

        btn_test = QPushButton("测试")
        btn_test.setObjectName("btnTest")
        btn_test.clicked.connect(self._quick_test_threshold)
        quick_layout.addWidget(btn_test)

        self.quick_result_label = QLabel("")
        self.quick_result_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.quick_result_label.setMinimumWidth(200)
        quick_layout.addWidget(self.quick_result_label)

        quick_layout.addStretch()
        layout.addWidget(quick_test_group)

        self._populate_indicator_table()
        self.sub_tab.addTab(tab, "指标与阈值")

    def _populate_indicator_table(self, filter_text: str = ""):
        self.indicator_table.setRowCount(0)
        reg = self._registry
        all_codes = sorted(reg.metric_thresholds_4level.keys())
        filtered = [
            code for code in all_codes
            if filter_text.lower() in code.lower()
            or filter_text in (reg.indicators.get(code, None) and reg.indicators[code].display_name_cn or '')
        ]

        self.indicator_table.setRowCount(len(filtered))
        for row, code in enumerate(filtered):
            meta = reg.indicators.get(code)
            display_name = meta.display_name_cn if meta else code
            dimension = meta.evaluation_dimension if meta else ''

            edited = self._edited_thresholds.get(code, {})
            base = reg.metric_thresholds_4level.get(code, {})
            t = {**base, **edited}

            exc = t.get('excellent', '')
            good = t.get('good', '')
            fair = t.get('fair', '')
            poor = t.get('poor', float('inf'))

            direction = meta.evaluation_direction if meta else EvaluationDirection.LOWER_BETTER
            dir_str = '越低越好' if direction == EvaluationDirection.LOWER_BETTER else '越高越好'

            def fmt_val(v):
                if isinstance(v, float) and v == float('inf'):
                    return ''
                if isinstance(v, (int, float)):
                    return f"{v:.4g}" if isinstance(v, float) and abs(v) < 100000 else str(v)
                return str(v) if v else ''

            items = [
                QTableWidgetItem(code),
                QTableWidgetItem(display_name),
                QTableWidgetItem(dimension),
                QTableWidgetItem(fmt_val(exc)),
                QTableWidgetItem(fmt_val(good)),
                QTableWidgetItem(fmt_val(fair)),
                QTableWidgetItem(fmt_val(poor)),
                QTableWidgetItem(dir_str),
            ]
            for col, item in enumerate(items[:8]):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignCenter)
                self.indicator_table.setItem(row, col, item)

            btn_edit = QPushButton("编辑")
            btn_edit.clicked.connect(lambda _, c=code: self._edit_threshold_dialog(c))
            self.indicator_table.setCellWidget(row, 8, btn_edit)

        self.indicator_table.resizeColumnsToContents()
        self.indicator_table.setColumnWidth(0, 110)
        self.indicator_table.setColumnWidth(1, 160)
        self.indicator_table.setColumnWidth(2, 100)
        for c in (3, 4, 5, 6):
            self.indicator_table.setColumnWidth(c, 80)
        self.indicator_table.setColumnWidth(7, 80)

    def _filter_indicator_table(self, text):
        self._populate_indicator_table(text)

    def _edit_threshold_dialog(self, code: str):
        reg = self._registry
        meta = reg.indicators.get(code)
        base = reg.metric_thresholds_4level.get(code, {})
        edited = self._edited_thresholds.get(code, {})
        t = {**base, **edited}

        dlg = QDialog(self)
        dlg.setWindowTitle(f"编辑阈值 — {code} ({meta.display_name_cn if meta else code})")
        dlg.setMinimumWidth(400)
        layout = QFormLayout(dlg)

        def v_from(val):
            if isinstance(val, float) and val == float('inf'):
                return None
            return val

        exc_spin = QDoubleSpinBox()
        exc_spin.setRange(0, 999999)
        exc_spin.setDecimals(4)
        exc_val = v_from(t.get('excellent'))
        if exc_val is not None:
            exc_spin.setValue(exc_val)
        layout.addRow("优秀 (excellent) ≤:", exc_spin)

        good_spin = QDoubleSpinBox()
        good_spin.setRange(0, 999999)
        good_spin.setDecimals(4)
        good_val = v_from(t.get('good'))
        if good_val is not None:
            good_spin.setValue(good_val)
        layout.addRow("良好 (good) ≤:", good_spin)

        fair_spin = QDoubleSpinBox()
        fair_spin.setRange(0, 999999)
        fair_spin.setDecimals(4)
        fair_val = v_from(t.get('fair'))
        if fair_val is not None:
            fair_spin.setValue(fair_val)
        layout.addRow("一般 (fair) ≤:", fair_spin)

        poor_check = QCheckBox("无上限")
        poor_check.setChecked(t.get('poor') == float('inf'))
        poor_spin = QDoubleSpinBox()
        poor_spin.setRange(0, 999999)
        poor_spin.setDecimals(4)
        poor_val = v_from(t.get('poor'))
        if poor_val is not None:
            poor_spin.setValue(poor_val)
        poor_spin.setEnabled(not poor_check.isChecked())
        poor_check.toggled.connect(lambda c: poor_spin.setEnabled(not c))
        layout.addRow("差 (poor) ≤:", poor_spin)
        layout.addRow("无上限:", poor_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(
            lambda: self._edited_thresholds.pop(code, None) or dlg.reject()
        )
        layout.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            new_t = {
                'excellent': exc_spin.value(),
                'good': good_spin.value(),
                'fair': fair_spin.value(),
                'poor': float('inf') if poor_check.isChecked() else poor_spin.value(),
            }
            self._edited_thresholds[code] = new_t
            self._populate_indicator_table(self.search_input.text())

    def _save_all_thresholds(self):
        if not self._edited_thresholds:
            QMessageBox.information(self, "提示", "没有待保存的修改。")
            return
        count = len(self._edited_thresholds)
        reply = QMessageBox.question(
            self, "确认保存",
            f"将保存 {count} 个指标的阈值修改到注册中心（仅内存生效，下次启动恢复默认）\n确认继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for code, t in self._edited_thresholds.items():
                self._registry.metric_thresholds_4level[code] = t
                self.thresholds_changed.emit(code, t)
            self._edited_thresholds.clear()
            self._populate_indicator_table(self.search_input.text())
            QMessageBox.information(self, "成功", f"已保存 {count} 个指标的阈值修改。")

    def _export_thresholds_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出阈值配置", "thresholds_export.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write("指标代码,中文名,优秀≤,良好≤,一般≤,差>\n")
                for code, t in self._registry.metric_thresholds_4level.items():
                    meta = self._registry.indicators.get(code)
                    name = meta.display_name_cn if meta else code
                    keys = ('excellent', 'good', 'fair', 'poor')
                    vals = [str(t.get(k, '')) if t.get(k, float('inf')) != float('inf') else '' for k in keys]
                    f.write(f"{code},{name},{','.join(vals)}\n")
            QMessageBox.information(self, "成功", f"已导出到 {path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出失败: {e}")

    def _quick_test_threshold(self):
        code = self.quick_indicator_combo.currentText()
        value = self.quick_value_spin.value()
        try:
            grade = self._registry.get_4level_grade(code, value)
        except Exception:
            grade = 'unknown'
        cn_label = GRADE_LABELS_CN.get(grade, grade)
        color = GRADE_COLORS.get(grade, GRADE_COLORS['unknown'])
        self.quick_result_label.setText(f"{cn_label} ({grade})")
        self.quick_result_label.setStyleSheet(
            f"color: {color}; font-family: 'Microsoft YaHei'; font-size: 15px; font-weight: bold;"
        )

    def _build_data_source_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.source_table = QTableWidget()
        self.source_table.setColumnCount(6)
        self.source_table.setHorizontalHeaderLabels([
            "通道代码", "名称", "协议", "采样率(Hz)", "传感器型号", "IMU标签"
        ])
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.source_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.source_table.setAlternatingRowColors(True)
        self.source_table.verticalHeader().setVisible(False)
        self.source_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.source_table)

        self._populate_source_table()
        self.sub_tab.addTab(tab, "数据源管理")

    def _populate_source_table(self):
        sources = self._registry.data_sources
        self.source_table.setRowCount(len(sources))
        for row, (code, src) in enumerate(sources.items()):
            imu_labels = ', '.join(src.imu_labels.values()) if src.imu_labels else (
                ', '.join(src.vehicle_signal_fields) if src.vehicle_signal_fields else '无'
            )
            items = [
                QTableWidgetItem(code),
                QTableWidgetItem(src.display_name_cn),
                QTableWidgetItem(f"{src.protocol} ({src.physical_channel})"),
                QTableWidgetItem(str(src.sampling_rate_hz)),
                QTableWidgetItem(src.sensor_model),
                QTableWidgetItem(imu_labels),
            ]
            for col, item in enumerate(items):
                self.source_table.setItem(row, col, item)
        self.source_table.resizeColumnsToContents()
        self.source_table.setColumnWidth(0, 140)
        self.source_table.setColumnWidth(1, 200)
        self.source_table.setColumnWidth(5, 300)

    def _build_driving_behavior_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_row = QHBoxLayout()

        self.state_filter_combo = QComboBox()
        self.state_filter_combo.addItems(["全部", "NORMAL", "WARNING", "DANGER", "CRITICAL"])
        self.state_filter_combo.currentTextChanged.connect(self._populate_state_table)
        top_row.addWidget(QLabel("风险过滤:"))
        top_row.addWidget(self.state_filter_combo)

        top_row.addStretch()

        btn_state_save = QPushButton("保存状态修改")
        btn_state_save.setObjectName("btnSave")
        btn_state_save.clicked.connect(self._save_all_states)
        top_row.addWidget(btn_state_save)

        layout.addLayout(top_row)

        self.state_table = QTableWidget()
        self.state_table.setColumnCount(7)
        self.state_table.setHorizontalHeaderLabels([
            "状态代码", "中文名", "英文名", "风险等级", "风险标签", "颜色", "描述"
        ])
        self.state_table.horizontalHeader().setStretchLastSection(True)
        self.state_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.state_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.state_table.setAlternatingRowColors(True)
        self.state_table.verticalHeader().setVisible(False)
        layout.addWidget(self.state_table)

        self._populate_state_table()
        self.sub_tab.addTab(tab, "驾驶行为管理")

    def _populate_state_table(self, filter_risk: str = "全部"):
        states = self._registry.driving_states
        filtered = {
            k: v for k, v in states.items()
            if filter_risk == "全部" or v.risk_category.name == filter_risk
        }
        self.state_table.setRowCount(len(filtered))
        for row, (code, state) in enumerate(filtered.items()):
            items = [
                QTableWidgetItem(code),
                QTableWidgetItem(state.display_name_cn),
                QTableWidgetItem(state.display_name_en),
                QTableWidgetItem(state.risk_category.name),
                QTableWidgetItem(state.risk_level_cn),
            ]

            risk_color = RISK_COLORS.get(state.risk_category.name, '#95A5A6')
            items[3].setForeground(QColor(risk_color))
            items[4].setForeground(QColor(risk_color))

            color_item = QTableWidgetItem(state.color_hex)
            color_item.setBackground(QColor(state.color_hex))
            color_item.setForeground(
                QColor('#fff') if state.color_hex > '#888888' else QColor('#333')
            )
            items.append(color_item)

            items.append(QTableWidgetItem(state.description))

            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.state_table.setItem(row, col, item)

            btn_edit = QPushButton("编辑风险")
            btn_edit.clicked.connect(lambda _, c=code: self._edit_state_dialog(c))
            self.state_table.setCellWidget(row, 6 if len(items) > 6 else 6, btn_edit)

        self.state_table.resizeColumnsToContents()
        self.state_table.setColumnWidth(0, 180)
        self.state_table.setColumnWidth(1, 120)

    def _edit_state_dialog(self, code: str):
        state = self._registry.driving_states.get(code)
        if not state:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"编辑驾驶行为 — {state.display_name_cn}")
        dlg.setMinimumWidth(350)
        layout = QFormLayout(dlg)

        risk_combo = QComboBox()
        risk_combo.addItems(["NORMAL", "WARNING", "DANGER", "CRITICAL"])
        risk_combo.setCurrentText(state.risk_category.name)
        layout.addRow("风险等级:", risk_combo)

        label_spin = QLineEdit(state.risk_level_cn)
        layout.addRow("风险标签:", label_spin)

        color_spin = QLineEdit(state.color_hex)
        layout.addRow("颜色代码:", color_spin)

        desc_spin = QLineEdit(state.description)
        layout.addRow("描述:", desc_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            from core.core.seat_evaluation.metadata_registry import RiskCategory
            risk_map = {
                'NORMAL': RiskCategory.NORMAL,
                'WARNING': RiskCategory.WARNING,
                'DANGER': RiskCategory.DANGER,
                'CRITICAL': RiskCategory.CRITICAL,
            }
            state.risk_category = risk_map.get(risk_combo.currentText(), state.risk_category)
            state.risk_level_cn = label_spin.text()
            state.color_hex = color_spin.text()
            state.description = desc_spin.text()
            self._populate_state_table(self.state_filter_combo.currentText())
            self.states_changed.emit()

    def _save_all_states(self):
        QMessageBox.information(self, "提示", "驾驶行为状态修改已即时生效（内存修改）。")
        self.states_changed.emit()

    def _build_field_operator_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        field_group = QGroupBox("原始字段 (Raw Fields)")
        field_layout = QVBoxLayout(field_group)

        self.field_table = QTableWidget()
        self.field_table.setColumnCount(8)
        self.field_table.setHorizontalHeaderLabels([
            "字段代码", "中文名", "单位", "数据类型", "量程", "采样率(Hz)", "设备", "类别"
        ])
        self.field_table.horizontalHeader().setStretchLastSection(True)
        self.field_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.field_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.field_table.setAlternatingRowColors(True)
        self.field_table.verticalHeader().setVisible(False)
        self.field_table.setEditTriggers(QTableWidget.NoEditTriggers)
        field_layout.addWidget(self.field_table)

        self._populate_field_table()
        layout.addWidget(field_group)

        op_group = QGroupBox("算子 (Operators)")
        op_layout = QVBoxLayout(op_group)

        self.op_table = QTableWidget()
        self.op_table.setColumnCount(5)
        self.op_table.setHorizontalHeaderLabels([
            "算子代码", "中文名", "输入类型", "输出类型", "描述"
        ])
        self.op_table.horizontalHeader().setStretchLastSection(True)
        self.op_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.op_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.op_table.setAlternatingRowColors(True)
        self.op_table.verticalHeader().setVisible(False)
        self.op_table.setEditTriggers(QTableWidget.NoEditTriggers)
        op_layout.addWidget(self.op_table)

        self._populate_op_table()
        layout.addWidget(op_group)

        indicator_group = QGroupBox("指标详情 (Indicator Details)")
        indicator_layout = QVBoxLayout(indicator_group)

        self.detail_tree = QTreeWidget()
        self.detail_tree.setHeaderLabels(["指标代码", "中文名", "公式/算子流水线", "适用位置"])
        self.detail_tree.setAlternatingRowColors(True)
        self._populate_indicator_detail_tree()
        indicator_layout.addWidget(self.detail_tree)
        layout.addWidget(indicator_group)

        self.sub_tab.addTab(tab, "字段与算子")

    def _populate_field_table(self):
        fields = self._registry.raw_fields
        self.field_table.setRowCount(len(fields))
        for row, (code, f) in enumerate(fields.items()):
            items = [
                QTableWidgetItem(code),
                QTableWidgetItem(f.display_name_cn),
                QTableWidgetItem(f.physical_unit),
                QTableWidgetItem(f.data_type),
                QTableWidgetItem(f"[{f.range_min}, {f.range_max}]"),
                QTableWidgetItem(str(f.sample_rate_hz)),
                QTableWidgetItem(f.source_device),
                QTableWidgetItem(f.field_category),
            ]
            for col, item in enumerate(items):
                self.field_table.setItem(row, col, item)
        self.field_table.resizeColumnsToContents()
        self.field_table.setColumnWidth(0, 120)
        self.field_table.setColumnWidth(1, 140)
        self.field_table.setColumnWidth(4, 120)

    def _populate_op_table(self):
        ops = self._registry.operators
        self.op_table.setRowCount(len(ops))
        for row, (code, op) in enumerate(ops.items()):
            items = [
                QTableWidgetItem(code),
                QTableWidgetItem(op.display_name_cn),
                QTableWidgetItem(op.input_type.value if hasattr(op.input_type, 'value') else str(op.input_type)),
                QTableWidgetItem(op.output_type.value if hasattr(op.output_type, 'value') else str(op.output_type)),
                QTableWidgetItem(op.description),
            ]
            for col, item in enumerate(items):
                self.op_table.setItem(row, col, item)
        self.op_table.resizeColumnsToContents()
        self.op_table.setColumnWidth(0, 140)
        self.op_table.setColumnWidth(1, 160)

    def _populate_indicator_detail_tree(self):
        reg = self._registry
        self.detail_tree.clear()
        for module_code, module in reg.evaluation_modules.items():
            module_item = QTreeWidgetItem([module_code, module.display_name_cn, '', ''])
            module_item.setBackground(0, QColor('#e8f0fe'))
            font = QFont("Microsoft YaHei", 11, QFont.Bold)
            module_item.setFont(0, font)

            for ind_code in module.applicable_indicators:
                meta = reg.indicators.get(ind_code)
                detail = reg.indicator_details.get(ind_code)
                name = meta.display_name_cn if meta else ind_code
                locations = ', '.join(meta.applicable_locations[:3]) if meta else ''
                pipeline = ' → '.join(meta.operator_pipeline[:4]) if meta and meta.operator_pipeline else (
                    detail.operator_pipeline_detail.split('\n')[0] if detail else '')
                child = QTreeWidgetItem([ind_code, name, pipeline, locations])
                module_item.addChild(child)

            self.detail_tree.addTopLevelItem(module_item)
        self.detail_tree.expandAll()
        for i in range(4):
            self.detail_tree.resizeColumnToContents(i)
        self.detail_tree.setColumnWidth(1, 200)

    def _build_schema_preview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        ddl_group = QGroupBox("自动生成 DDL (为注册中心生成)")
        ddl_layout = QVBoxLayout(ddl_group)

        self.ddl_text = QTextEdit()
        self.ddl_text.setReadOnly(True)
        self.ddl_text.setPlainText(self._registry.generate_result_schema())
        ddl_layout.addWidget(self.ddl_text)

        btn_copy = QPushButton("复制 DDL 到剪贴板")
        btn_copy.clicked.connect(lambda: self._copy_text(self.ddl_text.toPlainText()))
        ddl_layout.addWidget(btn_copy)

        layout.addWidget(ddl_group)

        stats_group = QGroupBox("注册中心统计")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(10)

        stats_items = [
            ("指标数:", str(len(self._registry.indicators))),
            ("四级阈值数:", str(len(self._registry.metric_thresholds_4level))),
            ("诊断阈值数:", str(len(self._registry.diagnosis_thresholds))),
            ("数据源数:", str(len(self._registry.data_sources))),
            ("驾驶行为状态数:", str(len(self._registry.driving_states))),
            ("原始字段数:", str(len(self._registry.raw_fields))),
            ("派生字段数:", str(len(self._registry.derived_fields))),
            ("算子数:", str(len(self._registry.operators))),
            ("评测模块数:", str(len(self._registry.evaluation_modules))),
            ("标准引用数:", str(len(self._registry.standard_references))),
            ("编辑中的阈值:", str(len(self._edited_thresholds))),
        ]

        for i, (label, value) in enumerate(stats_items):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(label)
            lbl.setFont(QFont("Microsoft YaHei", 11))
            stats_layout.addWidget(lbl, row, col)

            val = QLabel(value)
            val.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
            val.setStyleSheet("color: #4A90D9;")
            stats_layout.addWidget(val, row, col + 1)

        layout.addWidget(stats_group)
        layout.addStretch()
        self.sub_tab.addTab(tab, "Schema与统计")

    def _copy_text(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "提示", "已复制到剪贴板。")

    def refresh_all(self):
        self._populate_indicator_table(self.search_input.text())
        self._populate_source_table()
        self._populate_state_table(self.state_filter_combo.currentText())
        self._populate_field_table()
        self._populate_op_table()
        self._populate_indicator_detail_tree()
        self.ddl_text.setPlainText(self._registry.generate_result_schema())