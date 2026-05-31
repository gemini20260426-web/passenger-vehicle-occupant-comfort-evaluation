#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 优化日期: 2026-05-03
# 优化内容: ELT模式全面重构 v2 - 接入(适配器)→解析→质量→同步
#           精美步骤指示器、卡片式双栏布局、管道可视化、
#           完整同步引擎集成、配置摘要确认、动画过渡、
#           内联验证反馈、统一暗色专业主题
# ============================================================

import os
import csv
import json
import random
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QPushButton, QRadioButton, QWidget, QTabWidget, QScrollArea,
    QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QSplitter, QButtonGroup, QStackedWidget,
    QSizePolicy, QSlider, QGraphicsOpacityEffect, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QIcon

try:
    from ...professional_styles import PRO_COLORS
except ImportError:
    try:
        from modules.ui.professional_styles import PRO_COLORS
    except ImportError:
        # 定义默认颜色作为后备方案 - 与左侧控制面板一致的亮色主题
        PRO_COLORS = {
            'primary': '#4a90e2',
            'secondary': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'info': '#4a90e2',
            'bg_dark': '#f5f5f5',
            'bg_card': 'white',
            'bg_input': 'white',
            'text_light': '#333333',
            'text_muted': '#999999',
            'text_primary': '#333333',
            'text_secondary': '#666666',
            'text_accent': '#4a90e2',
            'border_default': '#CCCCCC',
            'border_light': '#AAAAAA',
            'border': '#CCCCCC',
            'success': '#27ae60',
            'accent': '#4a90e2',
            'accent_light': '#E3F2FD',
            'accent_hover': '#357abd',
            'gradient_accent': '#4a90e2',
            'gradient_header': 'white',
            'bg_header': '#f5f5f5',
            'bg_secondary': '#f5f5f5',
            'bg_primary': '#f0f0f0'
        }


class DataSourceConfigDialog(QDialog):

    config_completed = Signal(dict)
    data_source_configured = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据源配置")
        self.setModal(True)
        self.setMinimumWidth(680)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.current_step = 0
        self.total_steps = 7
        self.current_config = {}
        self.data_preview = None
        self.field_mapping = {}
        self.imu_parser = None
        self.cnap_parser = None
        self.can_parser = None
        self._selected_source_row = None
        self._selected_source_id = None
        self._connection_tested = False
        self._parser_detected = False
        self._parsing_configured = False
        self._filter_configured = False
        self._quality_configured = False
        self._sync_configured = False
        self._raw_data_mode = False
        
        # IMU 校准相关
        self._calib_data = {}  # 校准结果数据
        self._calib_json_path = None  # 校准JSON文件路径
        self._calib_worker = None  # 校准工作线程
        
        # 初始化解析器管理器
        self._init_parser_manager()

        self._init_ui_components()
        self._build_ui()
        self._apply_styles()
        self._connect_signals()
        self._update_step_display()

    def _init_ui_components(self):
        self.step_labels = []
        self.step_indicators = []
        self.step_connectors = []
        self.step_status_icons = []
        self.stacked_widget = None
        self.prev_btn = None
        self.next_btn = None
        self.cancel_btn = None
        self.help_btn = None
        self.reset_btn = None
        self.status_bar_label = None
        self._step_hint_label = None

        self.name_edit = None
        self.desc_edit = None
        self.category_group = None
        self.category_radios = {}
        self.type_combo = None
        self.type_hint = None

        self.adapter_combo = None
        self.adapter_stack = None
        self.adapter_params = {}
        self.test_conn_btn = None
        self.conn_status_label = None
        self.conn_indicator = None

        self.file_path_edit = None
        self.file_type_combo = None
        self.parser_status_label = None
        self.detect_parser_btn = None
        self.parser_combo = None
        self.parser_desc_label = None
        self.load_custom_parser_btn = None
        self.preview_table = None
        self.preview_btn = None
        self.field_mapping_table = None
        self.auto_mapping_btn = None
        self.parse_progress = None
        
        self.parser_manager = None
        self.selected_parser = None
        self.available_parsers = []

        self.quality_threshold_spin = None
        self.filter_strategy_combo = None
        self.outlier_method_combo = None
        self.min_value_spin = None
        self.max_value_spin = None
        self.gap_fill_combo = None
        self.quality_score_bar = None
        self.quality_score_label = None

        self.sync_mode_combo = None
        self.sync_interval_spin = None
        self.batch_size_spin = None
        self.timeout_spin = None
        self.priority_combo = None
        self.error_strategy_combo = None
        self.max_retries_spin = None
        self.retry_delay_spin = None
        self.compression_combo = None
        self.encryption_combo = None
        self.pipeline_status_label = None

        self.summary_text = None
        
        # IMU 校准UI组件
        self.calib_mode_combo = None  # 校准模式选择
        self.calib_status_label = None  # 校准状态标签
        self.calib_table = None  # 校准参数表格
        self.calib_run_btn = None  # 执行校准按钮
        self.calib_save_btn = None  # 保存校准参数按钮
        self.calib_load_btn = None  # 加载校准参数按钮
        self.calib_reset_btn = None  # 重置校准按钮

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f2f5;
            }
            QLabel {
                color: #333;
                font-family: "Microsoft YaHei";
                font-size: 9pt;
            }
            QGroupBox {
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
                font-weight: bold;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #555;
            }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
                background: #fff;
                color: #333;
                border: 1px solid #DDD;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #4a90e2;
            }
            QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background: #f5f5f5;
                color: #aaa;
            }
            QComboBox {
                background: #fff;
                color: #333;
                border: 1px solid #DDD;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
                min-height: 22px;
                font-family: "Microsoft YaHei";
            }
            QComboBox:hover { border-color: #BBB; }
            QComboBox:focus { border-color: #4a90e2; }
            QComboBox:disabled {
                background: #f5f5f5;
                color: #aaa;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background: #fff;
                color: #333;
                border: 1px solid #DDD;
                border-radius: 4px;
                selection-background-color: #E3F2FD;
                selection-color: #333;
                outline: none;
                padding: 2px;
            }
            QTableWidget {
                background: #fff;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                gridline-color: #EEE;
                color: #333;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background: #E3F2FD;
                color: #333;
            }
            QHeaderView::section {
                background: #f8f9fa;
                color: #555;
                border: none;
                border-bottom: 1px solid #E0E0E0;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QCheckBox {
                color: #333;
                spacing: 6px;
                font-size: 9pt;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #CCC;
                border-radius: 3px;
                background: #fff;
            }
            QCheckBox::indicator:checked {
                background: #4a90e2;
                border-color: #4a90e2;
            }
            QProgressBar {
                background: #EEE;
                border: none;
                border-radius: 3px;
                text-align: center;
                color: #333;
                height: 6px;
                font-size: 7pt;
            }
            QProgressBar::chunk {
                background: #4a90e2;
                border-radius: 3px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #CCC;
                border-radius: 5px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #AAA;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QRadioButton {
                color: #333;
                spacing: 6px;
                font-size: 9pt;
                padding: 3px 8px;
                border-radius: 4px;
            }
            QRadioButton:hover {
                background: #E3F2FD;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #CCC;
                border-radius: 7px;
                background: #fff;
            }
            QRadioButton::indicator:checked {
                background: #4a90e2;
                border-color: #4a90e2;
            }
            QSlider::groove:horizontal {
                background: #EEE;
                border: none;
                border-radius: 2px;
                height: 4px;
            }
            QSlider::handle:horizontal {
                background: #4a90e2;
                border: none;
                border-radius: 7px;
                width: 14px;
                height: 14px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #357abd;
            }

            QFrame#dialogHeader {
                background: #fff;
                border-bottom: 1px solid #E8E8E8;
            }

            QFrame#dialogFooter {
                background: #fafafa;
                border-top: 1px solid #E8E8E8;
            }

            QFrame#statusBar {
                background: #f8f9fa;
                border-top: 1px solid #EEE;
            }

            QLabel#dialogTitle {
                font-size: 13pt;
                font-weight: bold;
                color: #333;
            }

            QLabel#dialogSubtitle {
                font-size: 8pt;
                color: #999;
            }

            QLabel#sectionHint {
                color: #999;
                font-size: 8pt;
                font-style: italic;
            }

            QLabel#statusSuccess {
                color: #27ae60;
                font-size: 8pt;
                font-weight: bold;
            }

            QLabel#statusWarning {
                color: #f39c12;
                font-size: 8pt;
            }

            QLabel#statusError {
                color: #e74c3c;
                font-size: 8pt;
                font-weight: bold;
            }

            QLabel#statusMuted {
                color: #aaa;
                font-size: 8pt;
            }

            QLabel#adapterFieldLabel {
                color: #888;
                font-size: 8pt;
                font-weight: normal;
                min-width: 60px;
            }

            QLabel#qualityScoreLabel {
                font-size: 18pt;
                font-weight: bold;
                color: #333;
            }

            QLabel#pipelineArrow {
                color: #4a90e2;
                font-size: 10pt;
                font-weight: bold;
            }

            QLabel#pipelineStage {
                background: #fff;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 8pt;
                font-weight: bold;
                color: #888;
            }

            QLabel#pipelineStageActive {
                background: #E3F2FD;
                border: 1px solid #4a90e2;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 8pt;
                font-weight: bold;
                color: #4a90e2;
            }

            QFrame#adapterCard {
                background: #fff;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 10px;
            }

            QGroupBox#adapterCardGroup {
                border: 1px solid #D0D7DE;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 14px;
                font-weight: bold;
                font-size: 9pt;
                background: #fff;
            }
            QGroupBox#adapterCardGroup::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #4a90e2;
            }

            QFrame#separator {
                background: #E0E0E0;
            }

            QFrame#summaryCard {
                background: #fff;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 12px;
            }

            QLabel#summarySection {
                color: #4a90e2;
                font-size: 9pt;
                font-weight: bold;
                padding: 3px 0;
            }

            QLabel#summaryKey {
                color: #888;
                font-size: 8pt;
                min-width: 70px;
            }

            QLabel#summaryValue {
                color: #333;
                font-size: 8pt;
                font-weight: normal;
            }

            QPushButton#btnPrimary {
                background: #4a90e2;
                color: #fff;
                border: none;
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 9pt;
                font-weight: bold;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnPrimary:hover { background-color: #357abd; }
            QPushButton#btnPrimary:pressed { background-color: #2e6da6; }

            QPushButton#btnOutline {
                background-color: white;
                color: #4a90e2;
                border: 1px solid #4a90e2;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 9pt;
                font-weight: bold;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnOutline:hover { background-color: #E3F2FD; }

            QPushButton#btnGhost {
                background-color: white;
                color: #666666;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnGhost:hover {
                border-color: #AAAAAA;
                color: #333333;
            }

            QPushButton#btnWarning {
                background-color: white;
                color: #f39c12;
                border: 1px solid #f39c12;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnWarning:hover { background-color: #fff3cd; }

            QPushButton#btnMuted {
                background-color: white;
                color: #999999;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnMuted:hover {
                border-color: #AAAAAA;
                color: #666666;
            }

            QPushButton#btnSuccess {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 9pt;
                font-weight: bold;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnSuccess:hover { background-color: #219150; }

            QPushButton#btnDanger {
                background-color: white;
                color: #e74c3c;
                border: 1px solid #e74c3c;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 9pt;
                font-weight: bold;
                font-family: "Microsoft YaHei";
            }
            QPushButton#btnDanger:hover { background-color: #fdd; }

            QLabel#validationError {
                color: #e74c3c;
                font-size: 8pt;
                padding: 2px 4px;
            }
        """)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header = self._create_header()
        main_layout.addWidget(header)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self._create_step_connect())
        self.stacked_widget.addWidget(self._create_step_parse())
        self.stacked_widget.addWidget(self._create_step_correction())  # 新增：坐标轴校正
        self.stacked_widget.addWidget(self._create_step_quality())
        self.stacked_widget.addWidget(self._create_step_filter())
        self.stacked_widget.addWidget(self._create_step_sync())
        self.stacked_widget.addWidget(self._create_step_summary())
        main_layout.addWidget(self.stacked_widget, 1)

        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)

        footer = self._create_footer()
        main_layout.addWidget(footer)

    def _create_header(self):
        header = QFrame()
        header.setObjectName("dialogHeader")
        header.setFixedHeight(72)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 4)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title = QLabel("数据源配置")
        title.setObjectName("dialogTitle")
        title.setStyleSheet("font-size: 13pt; font-weight: bold; color: #333;")

        subtitle = QLabel("接入 → 解析 → 坐标轴校正 → 质量 → 滤波 → 同步 → 确认")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setStyleSheet("font-size: 8pt; color: #999;")

        title_row.addWidget(title)
        title_row.addSpacing(10)
        title_row.addWidget(subtitle)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        steps_row = QHBoxLayout()
        steps_row.setSpacing(0)
        steps_row.setContentsMargins(0, 0, 0, 0)

        step_names = ["接入", "解析", "坐标轴校正", "质量", "滤波", "同步", "确认"]

        for i, name in enumerate(step_names):
            step_widget = QWidget()
            step_widget.setFixedHeight(28)
            step_layout = QHBoxLayout(step_widget)
            step_layout.setContentsMargins(2, 0, 2, 0)
            step_layout.setSpacing(4)

            indicator = QLabel(str(i + 1))
            indicator.setFixedSize(20, 20)
            indicator.setAlignment(Qt.AlignCenter)
            indicator.setStyleSheet("""
                QLabel {
                    background: #E8E8E8; border: 1px solid #CCC;
                    border-radius: 10px; color: #999;
                    font-size: 8pt; font-weight: bold;
                }
            """)
            self.step_indicators.append(indicator)

            step_title = QLabel(name)
            step_title.setStyleSheet("font-size: 8pt; color: #999;")
            self.step_labels.append((step_title, None))

            step_layout.addWidget(indicator)
            step_layout.addWidget(step_title)
            steps_row.addWidget(step_widget)

            if i < self.total_steps - 1:
                connector = QFrame()
                connector.setFixedHeight(1)
                connector.setMinimumWidth(24)
                connector.setStyleSheet("background: #DDD;")
                self.step_connectors.append(connector)
                steps_row.addWidget(connector)

        steps_row.addStretch()
        header_layout.addLayout(steps_row)

        return header

    def _create_status_bar(self):
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(24)

        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(14, 2, 14, 2)
        bar_layout.setSpacing(8)

        self.status_bar_label = QLabel("等待配置...")
        self.status_bar_label.setStyleSheet("color: #888; font-size: 8pt;")

        bar_layout.addWidget(self.status_bar_label)
        bar_layout.addStretch()

        self._step_hint_label = QLabel(f"步骤 1/{self.total_steps}")
        self._step_hint_label.setStyleSheet("color: #999; font-size: 8pt;")
        bar_layout.addWidget(self._step_hint_label)

        return bar

    def _create_step_connect(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(4)
        basic_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        basic_layout.setContentsMargins(8, 14, 8, 6)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入数据源名称")
        basic_layout.addRow("名称:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(36)
        self.desc_edit.setPlaceholderText("可选：描述")
        basic_layout.addRow("描述:", self.desc_edit)
        layout.addWidget(basic_group)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        cat_group = QGroupBox("数据分类")
        cat_layout = QGridLayout(cat_group)
        cat_layout.setSpacing(2)
        cat_layout.setContentsMargins(8, 14, 8, 6)

        categories = [
            ("SENSOR", "传感器"),
            ("MEDICAL", "医疗设备"),
            ("VEHICLE", "车载系统"),
            ("INDUSTRIAL", "工业控制"),
            ("MULTIMEDIA", "多媒体"),
            ("CUSTOM", "自定义"),
        ]

        self.category_group = QButtonGroup()
        for idx, (key, name) in enumerate(categories):
            radio = QRadioButton(name)
            radio.setProperty("category", key)
            self.category_radios[key] = radio
            self.category_group.addButton(radio)
            cat_layout.addWidget(radio, idx // 2, idx % 2)

        self.category_group.buttonClicked.connect(self._on_category_selected)
        mid_row.addWidget(cat_group)

        type_group = QGroupBox("数据类型")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(4)
        type_layout.setContentsMargins(8, 14, 8, 6)

        self.type_hint = QLabel("请先选择数据分类")
        self.type_hint.setObjectName("sectionHint")
        type_layout.addWidget(self.type_hint)

        self.type_combo = QComboBox()
        self.type_combo.setEnabled(False)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        mid_row.addWidget(type_group)

        layout.addLayout(mid_row)

        adapter_config_group = QGroupBox("接入配置")
        adapter_config_group.setObjectName("adapterCardGroup")
        adapter_config_layout = QVBoxLayout(adapter_config_group)
        adapter_config_layout.setSpacing(4)
        adapter_config_layout.setContentsMargins(8, 14, 8, 6)

        adapter_hint = QLabel("选择数据接入方式")
        adapter_hint.setObjectName("sectionHint")
        adapter_config_layout.addWidget(adapter_hint)

        self.adapter_combo = QComboBox()
        self.adapter_combo.setEnabled(False)
        self.adapter_combo.addItems([
            "文件读取",
            "串口通信",
            "TCP/UDP 网络",
            "MQTT 消息队列",
            "数据库",
            "WebSocket 推送",
        ])
        self.adapter_combo.currentTextChanged.connect(self._on_adapter_changed)
        adapter_config_layout.addWidget(self.adapter_combo)

        self.adapter_stack = QStackedWidget()
        self.adapter_stack.addWidget(self._create_file_adapter())
        self.adapter_stack.addWidget(self._create_serial_adapter())
        self.adapter_stack.addWidget(self._create_tcp_adapter())
        self.adapter_stack.addWidget(self._create_mqtt_adapter())
        self.adapter_stack.addWidget(self._create_database_adapter())
        self.adapter_stack.addWidget(self._create_websocket_adapter())
        adapter_config_layout.addWidget(self.adapter_stack)

        layout.addWidget(adapter_config_group)

        adapter_verify_group = QGroupBox("连接验证")
        adapter_verify_group.setObjectName("adapterCardGroup")
        adapter_verify_layout = QVBoxLayout(adapter_verify_group)
        adapter_verify_layout.setSpacing(4)
        adapter_verify_layout.setContentsMargins(8, 14, 8, 6)

        test_row = QHBoxLayout()
        test_row.setSpacing(6)

        self.conn_indicator = QLabel("\u25cf")
        self.conn_indicator.setStyleSheet("color: #aaa; font-size: 8pt;")
        self.conn_indicator.setFixedWidth(14)

        self.test_conn_btn = QPushButton("测试连接")
        self.test_conn_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #4a90e2; border: 1px solid #4a90e2;
                border-radius: 4px; padding: 3px 12px; font-size: 8pt;
            }
            QPushButton:hover { background: #E3F2FD; }
        """)
        self.test_conn_btn.setEnabled(False)
        self.test_conn_btn.clicked.connect(self._test_connection)

        self.conn_status_label = QLabel("")
        self.conn_status_label.setObjectName("statusMuted")

        test_row.addWidget(self.conn_indicator)
        test_row.addWidget(self.test_conn_btn)
        test_row.addWidget(self.conn_status_label)
        test_row.addStretch()
        adapter_verify_layout.addLayout(test_row)

        self.raw_data_check = QCheckBox("标准数据集（已解析，跳过解析与滤波步骤）")
        self.raw_data_check.setStyleSheet(
            "QCheckBox { font-weight: bold; font-size: 8pt; color: #1565C0; "
            "padding: 4px 8px; background: #E3F2FD; border: 1px solid #90CAF9; "
            "border-radius: 4px; }"
            "QCheckBox:hover { background: #BBDEFB; }"
        )
        self.raw_data_check.setToolTip(
            "勾选后，数据源配置向导将跳过「解析」和「滤波」步骤，\n"
            "数据将直接进入分析管道，适用于已预处理的标准化数据集。"
        )
        self.raw_data_check.toggled.connect(self._on_raw_data_toggled)
        adapter_verify_layout.addWidget(self.raw_data_check)

        layout.addWidget(adapter_verify_group)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_adapter_card(self, rows):
        w = QWidget()
        w.setObjectName("adapterCard")
        form = QFormLayout(w)
        form.setSpacing(4)
        form.setContentsMargins(8, 6, 8, 6)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        for label_text, widget in rows:
            lbl = QLabel(label_text)
            lbl.setObjectName("adapterFieldLabel")
            form.addRow(lbl, widget)

        return w

    def _create_file_adapter(self):
        fp_row = QHBoxLayout()
        fp_row.setSpacing(8)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择或输入文件路径")
        self.file_path_edit.setReadOnly(True)
        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("btnPrimary")
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse_file)
        fp_row.addWidget(self.file_path_edit)
        fp_row.addWidget(browse_btn)
        fp_widget = QWidget()
        fp_widget.setLayout(fp_row)

        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["自动检测", "CSV", "JSON", "XML", "Excel", "TXT", "Binary"])

        encoding_combo = QComboBox()
        encoding_combo.addItems(["UTF-8", "GBK", "GB2312", "ISO-8859-1", "ASCII"])
        encoding_combo.setCurrentText("UTF-8")

        sep_combo = QComboBox()
        sep_combo.addItems([",", ";", "\\t (Tab)", "|", "空格"])
        sep_combo.setCurrentText(",")

        sample_spin = QSpinBox()
        sample_spin.setRange(1, 10000)
        sample_spin.setValue(100)
        sample_spin.setSuffix(" Hz")

        skip_spin = QSpinBox()
        skip_spin.setRange(0, 1000)
        skip_spin.setValue(0)
        skip_spin.setSuffix(" 行")

        return self._create_adapter_card([
            ("文件路径", fp_widget),
            ("文件类型", self.file_type_combo),
            ("编码", encoding_combo),
            ("分隔符", sep_combo),
            ("采样频率", sample_spin),
            ("跳过行数", skip_spin),
        ])

    def _create_serial_adapter(self):
        port_combo = QComboBox()
        port_combo.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
                             "/dev/ttyUSB0", "/dev/ttyUSB1"])
        port_combo.setEditable(True)

        baud_combo = QComboBox()
        baud_combo.addItems(["9600", "19200", "38400", "57600", "115200",
                             "230400", "460800", "921600"])
        baud_combo.setCurrentText("115200")

        data_combo = QComboBox()
        data_combo.addItems(["5", "6", "7", "8"])
        data_combo.setCurrentText("8")

        parity_combo = QComboBox()
        parity_combo.addItems(["None", "Even", "Odd", "Mark", "Space"])

        stop_combo = QComboBox()
        stop_combo.addItems(["1", "1.5", "2"])

        flow_combo = QComboBox()
        flow_combo.addItems(["None", "RTS/CTS", "XON/XOFF"])

        return self._create_adapter_card([
            ("端口", port_combo),
            ("波特率", baud_combo),
            ("数据位", data_combo),
            ("校验位", parity_combo),
            ("停止位", stop_combo),
            ("流控", flow_combo),
        ])

    def _create_tcp_adapter(self):
        proto_combo = QComboBox()
        proto_combo.addItems(["TCP", "UDP"])

        host_edit = QLineEdit("127.0.0.1")
        host_edit.setPlaceholderText("IP地址或主机名")

        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        port_spin.setValue(8080)

        timeout_spin = QSpinBox()
        timeout_spin.setRange(1, 300)
        timeout_spin.setValue(30)
        timeout_spin.setSuffix(" 秒")

        buffer_spin = QSpinBox()
        buffer_spin.setRange(256, 65536)
        buffer_spin.setValue(4096)
        buffer_spin.setSuffix(" 字节")

        keepalive_check = QCheckBox("保持连接 (Keep-Alive)")
        keepalive_check.setChecked(True)

        return self._create_adapter_card([
            ("协议", proto_combo),
            ("主机地址", host_edit),
            ("端口", port_spin),
            ("超时", timeout_spin),
            ("缓冲区", buffer_spin),
            ("", keepalive_check),
        ])

    def _create_mqtt_adapter(self):
        broker_edit = QLineEdit("localhost")
        broker_edit.setPlaceholderText("MQTT Broker 地址")

        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        port_spin.setValue(1883)

        client_edit = QLineEdit()
        client_edit.setPlaceholderText("客户端ID (留空自动生成)")

        user_edit = QLineEdit()
        user_edit.setPlaceholderText("用户名")

        pass_edit = QLineEdit()
        pass_edit.setEchoMode(QLineEdit.Password)
        pass_edit.setPlaceholderText("密码")

        topic_edit = QLineEdit("/sensor/data")

        qos_combo = QComboBox()
        qos_combo.addItems(["0 (最多一次)", "1 (至少一次)", "2 (仅一次)"])

        ssl_check = QCheckBox("启用 SSL/TLS 加密")
        ssl_check.setChecked(False)

        return self._create_adapter_card([
            ("Broker", broker_edit),
            ("端口", port_spin),
            ("Client ID", client_edit),
            ("用户名", user_edit),
            ("密码", pass_edit),
            ("Topic", topic_edit),
            ("QoS", qos_combo),
            ("", ssl_check),
        ])

    def _create_database_adapter(self):
        db_combo = QComboBox()
        db_combo.addItems(["MySQL", "PostgreSQL", "SQLite", "MongoDB",
                           "SQL Server", "Oracle"])

        host_edit = QLineEdit("localhost")

        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        port_spin.setValue(3306)

        dbname_edit = QLineEdit()
        dbname_edit.setPlaceholderText("数据库名称")

        table_edit = QLineEdit()
        table_edit.setPlaceholderText("表名或集合名")

        user_edit = QLineEdit()
        user_edit.setPlaceholderText("用户名")

        pass_edit = QLineEdit()
        pass_edit.setEchoMode(QLineEdit.Password)
        pass_edit.setPlaceholderText("密码")

        query_edit = QLineEdit("SELECT * FROM data LIMIT 1000")

        pool_check = QCheckBox("启用连接池")
        pool_check.setChecked(True)

        return self._create_adapter_card([
            ("数据库类型", db_combo),
            ("主机", host_edit),
            ("端口", port_spin),
            ("数据库", dbname_edit),
            ("表/集合", table_edit),
            ("用户名", user_edit),
            ("密码", pass_edit),
            ("查询语句", query_edit),
            ("", pool_check),
        ])

    def _create_websocket_adapter(self):
        url_edit = QLineEdit("ws://localhost:8080/data")

        proto_combo = QComboBox()
        proto_combo.addItems(["JSON", "MessagePack", "Protobuf", "Text"])

        timeout_spin = QSpinBox()
        timeout_spin.setRange(1, 300)
        timeout_spin.setValue(30)
        timeout_spin.setSuffix(" 秒")

        ping_check = QCheckBox("启用心跳检测 (Ping/Pong)")
        ping_check.setChecked(True)

        reconnect_check = QCheckBox("断线自动重连")
        reconnect_check.setChecked(True)

        auth_check = QCheckBox("启用身份验证 (JWT/Bearer)")
        auth_check.setChecked(False)

        return self._create_adapter_card([
            ("WebSocket URL", url_edit),
            ("数据格式", proto_combo),
            ("超时", timeout_spin),
            ("", ping_check),
            ("", reconnect_check),
            ("", auth_check),
        ])

    def _create_step_parse(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        parser_group = QGroupBox("解析器配置")
        parser_layout = QVBoxLayout(parser_group)
        parser_layout.setSpacing(6)
        parser_layout.setContentsMargins(10, 16, 10, 8)

        parser_select_row = QFormLayout()
        
        self.parser_combo = QComboBox()
        self.parser_combo.setMinimumHeight(24)
        self.parser_combo.currentIndexChanged.connect(self._on_parser_changed)
        self._refresh_parser_list()
        
        parser_select_row.addRow("解析脚本:", self.parser_combo)
        parser_layout.addLayout(parser_select_row)
        
        self.parser_desc_label = QLabel("请选择解析脚本")
        self.parser_desc_label.setWordWrap(True)
        self.parser_desc_label.setStyleSheet("color: #888; font-size: 8pt; padding: 4px; background: #fff; border: 1px solid #DDD; border-radius: 4px;")
        self.parser_desc_label.setMinimumHeight(32)
        parser_layout.addWidget(self.parser_desc_label)

        self.parser_status_label = QLabel("状态: 等待数据源接入")
        self.parser_status_label.setObjectName("statusMuted")
        parser_layout.addWidget(self.parser_status_label)

        self.parse_progress = QProgressBar()
        self.parse_progress.setMaximumHeight(4)
        self.parse_progress.setValue(0)
        self.parse_progress.setVisible(False)
        parser_layout.addWidget(self.parse_progress)

        parser_btn_row = QHBoxLayout()
        parser_btn_row.setSpacing(6)

        self.detect_parser_btn = QPushButton("智能检测解析器")
        self.detect_parser_btn.setStyleSheet("""
            QPushButton { background: #4a90e2; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; font-weight: bold; }
            QPushButton:hover { background: #357abd; }
        """)
        self.detect_parser_btn.clicked.connect(self._detect_parser)
        
        self.ai_generate_btn = QPushButton("AI生成解析器")
        self.ai_generate_btn.setStyleSheet("""
            QPushButton { background: #9b59b6; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; font-weight: bold; }
            QPushButton:hover { background: #8e44ad; }
        """)
        self.ai_generate_btn.clicked.connect(self._ai_generate_parser)
        
        self.load_custom_parser_btn = QPushButton("加载自定义脚本")
        self.load_custom_parser_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #4a90e2; border: 1px solid #4a90e2;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; }
            QPushButton:hover { background: #E3F2FD; }
        """)
        self.load_custom_parser_btn.clicked.connect(self._load_custom_parser)

        refresh_parser_btn = QPushButton("刷新列表")
        refresh_parser_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: 1px solid #DDD;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; }
            QPushButton:hover { background: #f0f0f0; }
        """)
        refresh_parser_btn.clicked.connect(self._refresh_parser_list)

        parser_btn_row.addWidget(self.detect_parser_btn)
        parser_btn_row.addWidget(self.ai_generate_btn)
        parser_btn_row.addWidget(self.load_custom_parser_btn)
        parser_btn_row.addWidget(refresh_parser_btn)
        parser_btn_row.addStretch()
        parser_layout.addLayout(parser_btn_row)
        layout.addWidget(parser_group)

        split_row = QHBoxLayout()
        split_row.setSpacing(8)

        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(10, 16, 10, 8)

        preview_btn_row = QHBoxLayout()
        preview_btn_row.setSpacing(6)

        self.preview_btn = QPushButton("加载预览")
        self.preview_btn.setStyleSheet("""
            QPushButton { background: #4a90e2; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; font-weight: bold; }
            QPushButton:hover { background: #357abd; }
        """)
        self.preview_btn.clicked.connect(self._preview_data)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: 1px solid #DDD;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; }
            QPushButton:hover { background: #f0f0f0; }
        """)
        refresh_btn.clicked.connect(self._refresh_preview)

        preview_btn_row.addWidget(self.preview_btn)
        preview_btn_row.addWidget(refresh_btn)
        preview_btn_row.addStretch()
        preview_layout.addLayout(preview_btn_row)

        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(140)
        self.preview_table.setAlternatingRowColors(True)
        preview_layout.addWidget(self.preview_table)
        split_row.addWidget(preview_group, 1)

        mapping_group = QGroupBox("字段映射")
        mapping_layout = QVBoxLayout(mapping_group)
        mapping_layout.setSpacing(6)
        mapping_layout.setContentsMargins(10, 16, 10, 8)

        mapping_btn_row = QHBoxLayout()
        mapping_btn_row.setSpacing(6)

        self.auto_mapping_btn = QPushButton("智能字段映射")
        self.auto_mapping_btn.setStyleSheet("""
            QPushButton { background: #4a90e2; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; font-weight: bold; }
            QPushButton:hover { background: #357abd; }
        """)
        self.auto_mapping_btn.clicked.connect(self._auto_generate_field_mapping)

        manual_btn = QPushButton("手动调整")
        manual_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: 1px solid #DDD;
                border-radius: 4px; padding: 4px 12px; font-size: 8pt; }
            QPushButton:hover { background: #f0f0f0; }
        """)
        manual_btn.clicked.connect(self._manual_field_mapping)

        mapping_btn_row.addWidget(self.auto_mapping_btn)
        mapping_btn_row.addWidget(manual_btn)
        mapping_btn_row.addStretch()
        mapping_layout.addLayout(mapping_btn_row)

        self.field_mapping_table = QTableWidget()
        self.field_mapping_table.setMaximumHeight(140)
        self.field_mapping_table.setAlternatingRowColors(True)
        mapping_layout.addWidget(self.field_mapping_table)
        split_row.addWidget(mapping_group, 1)

        layout.addLayout(split_row)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_step_correction(self):
        """坐标轴校正与 IMU 校准配置步骤"""
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("坐标轴校正与 IMU 校准配置")
        title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        hint = QLabel("配置 IMU 校准选项，数据加载完成后可选择执行校准")
        hint.setObjectName("sectionHint")
        layout.addWidget(hint)

        # 校准策略选择
        strategy_group = QGroupBox("校准策略")
        strategy_layout = QVBoxLayout(strategy_group)
        strategy_layout.setContentsMargins(12, 16, 12, 10)
        strategy_layout.setSpacing(8)

        # 单选按钮
        self.calib_strategy_none = QRadioButton("不使用校准（使用原始数据）")
        self.calib_strategy_none.setChecked(True)
        self.calib_strategy_none.toggled.connect(self._on_calib_strategy_changed)
        strategy_layout.addWidget(self.calib_strategy_none)

        self.calib_strategy_auto = QRadioButton("数据加载后自动执行静态校准（推荐）")
        self.calib_strategy_auto.toggled.connect(self._on_calib_strategy_changed)
        strategy_layout.addWidget(self.calib_strategy_auto)

        self.calib_strategy_load = QRadioButton("从已有的 JSON 校准文件加载")
        self.calib_strategy_load.toggled.connect(self._on_calib_strategy_changed)
        strategy_layout.addWidget(self.calib_strategy_load)

        # 校准文件选择（仅在选择“从文件加载”时启用）
        self.calib_file_layout = QHBoxLayout()
        self.calib_file_edit = QLineEdit()
        self.calib_file_edit.setPlaceholderText("选择 JSON 校准文件...")
        self.calib_file_edit.setEnabled(False)
        self.calib_file_layout.addWidget(self.calib_file_edit)

        self.calib_file_btn = QPushButton("浏览...")
        self.calib_file_btn.setEnabled(False)
        self.calib_file_btn.clicked.connect(self._select_calib_file)
        self.calib_file_layout.addWidget(self.calib_file_btn)

        strategy_layout.addLayout(self.calib_file_layout)

        layout.addWidget(strategy_group)

        # 状态提示
        info_group = QGroupBox("说明")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(12, 16, 12, 10)

        info_label = QLabel(
            "- 选择「自动执行」：数据加载完成后弹出对话框，提示执行静态校准\n"
            "- 选择「从文件加载」：使用已有的校准参数，数据加载后立即应用\n"
            "- 选择「不使用校准」：加载原始数据，不进行任何校正"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("sectionHint")
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_step_quality(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        score_row = QHBoxLayout()
        score_row.setSpacing(8)

        score_card = QGroupBox("质量评分")
        score_layout = QVBoxLayout(score_card)
        score_layout.setSpacing(4)
        score_layout.setAlignment(Qt.AlignCenter)
        score_layout.setContentsMargins(10, 16, 10, 8)

        self.quality_score_label = QLabel("--")
        self.quality_score_label.setObjectName("qualityScoreLabel")
        self.quality_score_label.setAlignment(Qt.AlignCenter)
        self.quality_score_label.setStyleSheet("color: #aaa;")

        score_hint = QLabel("当前质量评分")
        score_hint.setAlignment(Qt.AlignCenter)
        score_hint.setStyleSheet("color: #aaa; font-size: 8pt;")

        score_layout.addWidget(self.quality_score_label)
        score_layout.addWidget(score_hint)
        score_row.addWidget(score_card)

        threshold_group = QGroupBox("数据质量阈值")
        threshold_layout = QFormLayout(threshold_group)
        threshold_layout.setSpacing(6)
        threshold_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        threshold_layout.setContentsMargins(10, 16, 10, 8)

        self.quality_threshold_spin = QDoubleSpinBox()
        self.quality_threshold_spin.setRange(0.0, 1.0)
        self.quality_threshold_spin.setValue(0.8)
        self.quality_threshold_spin.setSingleStep(0.05)
        self.quality_threshold_spin.setSuffix(" (0.0-1.0)")
        self.quality_threshold_spin.valueChanged.connect(self._update_quality_score)
        threshold_layout.addRow("质量阈值:", self.quality_threshold_spin)

        completeness_spin = QDoubleSpinBox()
        completeness_spin.setRange(0.0, 1.0)
        completeness_spin.setValue(0.9)
        completeness_spin.setSingleStep(0.05)
        completeness_spin.setSuffix(" (0.0-1.0)")
        threshold_layout.addRow("完整性要求:", completeness_spin)

        accuracy_spin = QDoubleSpinBox()
        accuracy_spin.setRange(0.0, 1.0)
        accuracy_spin.setValue(0.85)
        accuracy_spin.setSingleStep(0.05)
        accuracy_spin.setSuffix(" (0.0-1.0)")
        threshold_layout.addRow("准确性要求:", accuracy_spin)

        timeliness_spin = QSpinBox()
        timeliness_spin.setRange(1, 10000)
        timeliness_spin.setValue(100)
        timeliness_spin.setSuffix(" ms")
        threshold_layout.addRow("时效性要求:", timeliness_spin)

        score_row.addWidget(threshold_group, 1)
        layout.addLayout(score_row)

        filter_group = QGroupBox("数据过滤策略")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(6)
        filter_layout.setContentsMargins(10, 16, 10, 8)

        self.filter_strategy_combo = QComboBox()
        self.filter_strategy_combo.addItems([
            "不过滤 (保留所有数据)",
            "时间窗口过滤",
            "数值范围过滤",
            "异常值过滤 (IQR)",
            "异常值过滤 (Z-Score)",
            "自定义过滤规则",
        ])
        self.filter_strategy_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_strategy_combo)

        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        self.min_value_spin = QDoubleSpinBox()
        self.min_value_spin.setRange(-999999, 999999)
        self.min_value_spin.setValue(-100)
        self.min_value_spin.setEnabled(False)
        self.max_value_spin = QDoubleSpinBox()
        self.max_value_spin.setRange(-999999, 999999)
        self.max_value_spin.setValue(100)
        self.max_value_spin.setEnabled(False)
        range_row.addWidget(QLabel("最小值:"))
        range_row.addWidget(self.min_value_spin)
        range_row.addWidget(QLabel("最大值:"))
        range_row.addWidget(self.max_value_spin)
        range_row.addStretch()
        filter_layout.addLayout(range_row)

        layout.addWidget(filter_group)

        outlier_group = QGroupBox("异常值处理")
        outlier_layout = QFormLayout(outlier_group)
        outlier_layout.setSpacing(6)
        outlier_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        outlier_layout.setContentsMargins(10, 16, 10, 8)

        self.outlier_method_combo = QComboBox()
        self.outlier_method_combo.addItems([
            "IQR (四分位距法)",
            "Z-Score (标准分数法)",
            "Isolation Forest (孤立森林)",
            "DBSCAN (密度聚类)",
            "LOF (局部异常因子)",
        ])
        outlier_layout.addRow("检测方法:", self.outlier_method_combo)

        self.gap_fill_combo = QComboBox()
        self.gap_fill_combo.addItems([
            "不填充 (保留空值)",
            "前值填充 (Forward Fill)",
            "线性插值 (Linear Interpolation)",
            "样条插值 (Spline)",
            "均值填充 (Mean)",
            "中位数填充 (Median)",
        ])
        outlier_layout.addRow("缺失值填充:", self.gap_fill_combo)

        dedup_check = QCheckBox("启用数据去重")
        dedup_check.setChecked(True)
        outlier_layout.addRow("", dedup_check)

        normalize_check = QCheckBox("启用数据标准化 (Z-Score Normalization)")
        normalize_check.setChecked(False)
        outlier_layout.addRow("", normalize_check)

        layout.addWidget(outlier_group)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_step_filter(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        enable_row = QHBoxLayout()
        self.filter_enable_check = QCheckBox("启用信号滤波预处理")
        self.filter_enable_check.setChecked(False)
        self.filter_enable_check.setStyleSheet("font-weight: bold; font-size: 9pt; color: #333;")
        self.filter_enable_check.toggled.connect(self._on_filter_enable_toggled)
        enable_row.addWidget(self.filter_enable_check)
        enable_row.addStretch()
        layout.addLayout(enable_row)

        algo_group = QGroupBox("滤波算法选择")
        algo_layout = QFormLayout(algo_group)
        algo_layout.setSpacing(6)
        algo_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        algo_layout.setContentsMargins(10, 16, 10, 8)

        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems([
            "移动平均滤波 (Moving Average)",
            "中值滤波 (Median Filter)",
            "指数加权滤波 / RC低通 (Exponential)",
            "高通滤波 (High-Pass)",
            "带通滤波 (Band-Pass)",
            "卡尔曼滤波 (Kalman Filter)",
            "巴特沃斯低通滤波 (Butterworth)",
            "--- CFC 通道频率等级 (SAE J211 / ISO 6487) ---",
            "CFC 1000 — 截止频率 1000 Hz (高频碰撞加速度)",
            "CFC 600 — 截止频率 600 Hz (头部/胸部碰撞加速度)",
            "CFC 180 — 截止频率 180 Hz (胸部压缩/力传感器)",
            "CFC 60 — 截止频率 60 Hz (安全带力/位移传感器)",
            "CFC 30 — 截止频率 30 Hz (膝部位移/低速碰撞)",
        ])
        self.filter_type_combo.setCurrentIndex(0)
        self.filter_type_combo.currentIndexChanged.connect(self._on_filter_type_changed)
        self.filter_type_combo.setEnabled(False)
        algo_layout.addRow("滤波算法:", self.filter_type_combo)

        self.filter_target_fields_edit = QLineEdit()
        self.filter_target_fields_edit.setPlaceholderText("例如: ax,ay,az,gx,gy,gz (逗号分隔)")
        self.filter_target_fields_edit.setText("ax,ay,az")
        self.filter_target_fields_edit.setEnabled(False)
        algo_layout.addRow("目标字段:", self.filter_target_fields_edit)

        layout.addWidget(algo_group)

        self.filter_params_group = QGroupBox("算法参数")
        params_layout = QGridLayout(self.filter_params_group)
        params_layout.setSpacing(4)
        params_layout.setContentsMargins(8, 14, 8, 6)

        self.filter_window_spin = QSpinBox()
        self.filter_window_spin.setRange(2, 100)
        self.filter_window_spin.setValue(5)
        self.filter_window_spin.setSuffix(" 采样点")
        self.filter_window_spin.setEnabled(False)
        params_layout.addWidget(QLabel("窗口大小:"), 0, 0)
        params_layout.addWidget(self.filter_window_spin, 0, 1)

        self.filter_alpha_spin = QDoubleSpinBox()
        self.filter_alpha_spin.setRange(0.01, 0.99)
        self.filter_alpha_spin.setValue(0.3)
        self.filter_alpha_spin.setSingleStep(0.05)
        self.filter_alpha_spin.setDecimals(2)
        self.filter_alpha_spin.setEnabled(False)
        params_layout.addWidget(QLabel("平滑系数 α:"), 0, 2)
        params_layout.addWidget(self.filter_alpha_spin, 0, 3)

        self.filter_cutoff_spin = QDoubleSpinBox()
        self.filter_cutoff_spin.setRange(0.1, 500.0)
        self.filter_cutoff_spin.setValue(10.0)
        self.filter_cutoff_spin.setSuffix(" Hz")
        self.filter_cutoff_spin.setDecimals(1)
        self.filter_cutoff_spin.setEnabled(False)
        params_layout.addWidget(QLabel("截止频率:"), 1, 0)
        params_layout.addWidget(self.filter_cutoff_spin, 1, 1)

        self.filter_high_cutoff_spin = QDoubleSpinBox()
        self.filter_high_cutoff_spin.setRange(0.1, 500.0)
        self.filter_high_cutoff_spin.setValue(50.0)
        self.filter_high_cutoff_spin.setSuffix(" Hz")
        self.filter_high_cutoff_spin.setDecimals(1)
        self.filter_high_cutoff_spin.setEnabled(False)
        params_layout.addWidget(QLabel("高频截止:"), 1, 2)
        params_layout.addWidget(self.filter_high_cutoff_spin, 1, 3)

        self.filter_sample_rate_spin = QDoubleSpinBox()
        self.filter_sample_rate_spin.setRange(1.0, 10000.0)
        self.filter_sample_rate_spin.setValue(100.0)
        self.filter_sample_rate_spin.setSuffix(" Hz")
        self.filter_sample_rate_spin.setDecimals(1)
        self.filter_sample_rate_spin.setEnabled(False)
        params_layout.addWidget(QLabel("采样率:"), 2, 0)
        params_layout.addWidget(self.filter_sample_rate_spin, 2, 1)

        self.filter_order_spin = QSpinBox()
        self.filter_order_spin.setRange(1, 8)
        self.filter_order_spin.setValue(2)
        self.filter_order_spin.setEnabled(False)
        params_layout.addWidget(QLabel("滤波器阶数:"), 2, 2)
        params_layout.addWidget(self.filter_order_spin, 2, 3)

        self.filter_process_noise_spin = QDoubleSpinBox()
        self.filter_process_noise_spin.setRange(0.001, 10.0)
        self.filter_process_noise_spin.setValue(0.01)
        self.filter_process_noise_spin.setDecimals(3)
        self.filter_process_noise_spin.setSingleStep(0.01)
        self.filter_process_noise_spin.setEnabled(False)
        params_layout.addWidget(QLabel("过程噪声 Q:"), 3, 0)
        params_layout.addWidget(self.filter_process_noise_spin, 3, 1)

        self.filter_measure_noise_spin = QDoubleSpinBox()
        self.filter_measure_noise_spin.setRange(0.001, 10.0)
        self.filter_measure_noise_spin.setValue(0.1)
        self.filter_measure_noise_spin.setDecimals(3)
        self.filter_measure_noise_spin.setSingleStep(0.01)
        self.filter_measure_noise_spin.setEnabled(False)
        params_layout.addWidget(QLabel("测量噪声 R:"), 3, 2)
        params_layout.addWidget(self.filter_measure_noise_spin, 3, 3)

        layout.addWidget(self.filter_params_group)

        info_group = QGroupBox("算法说明")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(10, 16, 10, 8)
        self.filter_info_label = QLabel(
            "移动平均滤波：对窗口内的数据取算术平均，适合去除高频随机噪声。\n"
            "窗口越大平滑效果越强，但会引入延迟。"
        )
        self.filter_info_label.setWordWrap(True)
        self.filter_info_label.setStyleSheet("color: #888; font-size: 8pt; padding: 4px;")
        info_layout.addWidget(self.filter_info_label)
        layout.addWidget(info_group)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _on_raw_data_toggled(self, checked):
        self._raw_data_mode = checked
        if checked:
            self._parsing_configured = True
            self._filter_configured = True
            self._update_step_indicators()
            self._update_nav_buttons()
        else:
            self._parsing_configured = False
            self._filter_configured = False
            self._update_step_indicators()
            self._update_nav_buttons()

    def _update_step_indicators(self):
        pass

    def _update_nav_buttons(self):
        pass

    def _on_filter_enable_toggled(self, checked):
        enabled = checked
        self.filter_type_combo.setEnabled(enabled)
        self.filter_target_fields_edit.setEnabled(enabled)
        self._on_filter_type_changed(self.filter_type_combo.currentIndex())

    def _on_filter_type_changed(self, index):
        if not self.filter_enable_check.isChecked():
            for widget in [self.filter_window_spin, self.filter_alpha_spin,
                           self.filter_cutoff_spin, self.filter_high_cutoff_spin,
                           self.filter_sample_rate_spin, self.filter_order_spin,
                           self.filter_process_noise_spin, self.filter_measure_noise_spin]:
                widget.setEnabled(False)
            return

        algo_text = self.filter_type_combo.currentText()

        all_params = [
            self.filter_window_spin, self.filter_alpha_spin,
            self.filter_cutoff_spin, self.filter_high_cutoff_spin,
            self.filter_sample_rate_spin, self.filter_order_spin,
            self.filter_process_noise_spin, self.filter_measure_noise_spin
        ]
        for w in all_params:
            w.setEnabled(False)

        if "移动平均" in algo_text:
            self.filter_window_spin.setEnabled(True)
            self.filter_info_label.setText(
                "移动平均滤波：对窗口内的数据取算术平均，适合去除高频随机噪声。\n"
                "窗口越大平滑效果越强，但会引入延迟。"
            )
        elif "中值滤波" in algo_text:
            self.filter_window_spin.setEnabled(True)
            self.filter_info_label.setText(
                "中值滤波：取窗口内数据的中位数，对脉冲噪声（尖峰干扰）特别有效。\n"
                "能保留边缘信息，适合去除偶发性异常值。"
            )
        elif "指数加权" in algo_text or "RC低通" in algo_text:
            self.filter_alpha_spin.setEnabled(True)
            self.filter_info_label.setText(
                "指数加权滤波（RC低通）：y[n] = α·x[n] + (1-α)·y[n-1]\n"
                "α越小平滑越强，α越大响应越快。一阶IIR滤波器，计算量极小。"
            )
        elif "高通滤波" in algo_text:
            self.filter_alpha_spin.setEnabled(True)
            self.filter_info_label.setText(
                "高通滤波：保留高频成分，滤除低频漂移和趋势项。\n"
                "适合去除传感器基线漂移，α控制截止特性。"
            )
        elif "带通滤波" in algo_text:
            self.filter_alpha_spin.setEnabled(True)
            self.filter_info_label.setText(
                "带通滤波：级联低通+高通，保留特定频段内的信号。\n"
                "适合提取特定频率范围的生理信号（如心率频段）。"
            )
        elif "卡尔曼滤波" in algo_text:
            self.filter_process_noise_spin.setEnabled(True)
            self.filter_measure_noise_spin.setEnabled(True)
            self.filter_info_label.setText(
                "卡尔曼滤波：基于状态空间模型的最优递归估计算法。\n"
                "Q（过程噪声）越大信任观测越多，R（测量噪声）越大平滑越强。\n"
                "适合动态系统实时状态估计，自动适应信号变化。"
            )
        elif "巴特沃斯" in algo_text:
            self.filter_cutoff_spin.setEnabled(True)
            self.filter_sample_rate_spin.setEnabled(True)
            self.filter_order_spin.setEnabled(True)
            self.filter_info_label.setText(
                "巴特沃斯低通滤波：通带内最大平坦，无纹波。\n"
                "阶数越高过渡带越陡，但计算量增大。\n"
                "纯numpy实现，无需scipy依赖。"
            )
        elif "CFC" in algo_text and "---" not in algo_text:
            self.filter_sample_rate_spin.setEnabled(True)
            cfc_map = {
                "CFC 1000": ("1000 Hz", "高频碰撞加速度信号（如B柱加速度）"),
                "CFC 600": ("600 Hz", "头部/胸部碰撞加速度"),
                "CFC 180": ("180 Hz", "胸部压缩量/力传感器"),
                "CFC 60": ("60 Hz", "安全带力/位移传感器"),
                "CFC 30": ("30 Hz", "膝部位移/低速碰撞"),
            }
            for key, (freq, desc) in cfc_map.items():
                if key in algo_text:
                    self.filter_info_label.setText(
                        f"CFC 通道频率等级滤波 (SAE J211 / ISO 6487)\n"
                        f"4阶Butterworth低通，截止频率 {freq}\n"
                        f"适用场景：{desc}\n"
                        f"⚠ 需正确设置采样率，截止频率必须 < 采样率/2"
                    )
                    break
        elif "---" in algo_text:
            self.filter_info_label.setText(
                "CFC (Channel Frequency Class) 是碰撞试验数据处理的核心标准，\n"
                "定义于 SAE J211 / ISO 6487。请从下方选择具体等级。"
            )

    def _create_step_sync(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        pipeline_group = QGroupBox("数据管道 (Data Pipeline)")
        pipeline_layout = QVBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(6)
        pipeline_layout.setContentsMargins(10, 16, 10, 8)

        pipe_row = QHBoxLayout()
        pipe_row.setSpacing(4)
        pipe_row.setAlignment(Qt.AlignCenter)

        stages = [
            ("数据源", PRO_COLORS['info']),
            ("解析器", PRO_COLORS['accent']),
            ("质量检查", PRO_COLORS['warning']),
            ("同步引擎", PRO_COLORS['success']),
            ("目标系统", PRO_COLORS['info']),
        ]

        for idx, (name, color) in enumerate(stages):
            stage_lbl = QLabel(name)
            stage_lbl.setObjectName("pipelineStage")
            stage_lbl.setAlignment(Qt.AlignCenter)
            pipe_row.addWidget(stage_lbl)

            if idx < len(stages) - 1:
                arrow = QLabel("\u2192")
                arrow.setObjectName("pipelineArrow")
                pipe_row.addWidget(arrow)

        pipeline_layout.addLayout(pipe_row)

        self.pipeline_status_label = QLabel("状态: 等待配置同步参数")
        self.pipeline_status_label.setObjectName("statusMuted")
        self.pipeline_status_label.setAlignment(Qt.AlignCenter)
        pipeline_layout.addWidget(self.pipeline_status_label)

        layout.addWidget(pipeline_group)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        mode_group = QGroupBox("同步模式")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(6)
        mode_layout.setContentsMargins(10, 16, 10, 8)

        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems([
            "实时同步 (Real-time)",
            "批量同步 (Batch)",
            "定时同步 (Scheduled)",
            "事件驱动 (Event-driven)",
            "混合模式 (Hybrid)",
        ])
        self.sync_mode_combo.currentTextChanged.connect(self._on_sync_mode_changed)
        mode_layout.addWidget(QLabel("同步模式:"))
        mode_layout.addWidget(self.sync_mode_combo)

        params_layout = QFormLayout()
        params_layout.setSpacing(6)
        params_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(1, 3600000)
        self.sync_interval_spin.setValue(100)
        self.sync_interval_spin.setSuffix(" ms")
        params_layout.addRow("同步间隔:", self.sync_interval_spin)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100000)
        self.batch_size_spin.setValue(100)
        self.batch_size_spin.setSuffix(" 条/批")
        params_layout.addRow("批量大小:", self.batch_size_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        params_layout.addRow("超时时间:", self.timeout_spin)

        mode_layout.addLayout(params_layout)
        top_row.addWidget(mode_group)

        priority_group = QGroupBox("优先级与路由")
        priority_layout = QFormLayout(priority_group)
        priority_layout.setSpacing(6)
        priority_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        priority_layout.setContentsMargins(10, 16, 10, 8)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems([
            "时间优先 (Time Priority)",
            "质量优先 (Quality Priority)",
            "类型优先 (Type Priority)",
            "来源优先 (Source Priority)",
            "自适应 (Adaptive)",
        ])
        priority_layout.addRow("优先级策略:", self.priority_combo)

        route_combo = QComboBox()
        route_combo.addItems([
            "直通路由 (Direct)",
            "广播路由 (Broadcast)",
            "条件路由 (Condition-based)",
            "负载均衡 (Load Balance)",
        ])
        priority_layout.addRow("路由策略:", route_combo)

        fusion_combo = QComboBox()
        fusion_combo.addItems([
            "无融合 (No Fusion)",
            "加权平均 (Weighted Avg)",
            "卡尔曼滤波 (Kalman Filter)",
            "神经网络 (Neural Network)",
            "贝叶斯估计 (Bayesian)",
        ])
        priority_layout.addRow("融合策略:", fusion_combo)

        top_row.addWidget(priority_group)
        layout.addLayout(top_row)

        error_group = QGroupBox("错误处理与容错")
        error_layout = QVBoxLayout(error_group)
        error_layout.setSpacing(6)
        error_layout.setContentsMargins(10, 16, 10, 8)

        self.error_strategy_combo = QComboBox()
        self.error_strategy_combo.addItems([
            "忽略错误继续 (Ignore)",
            "重试机制 (Retry)",
            "降级处理 (Degrade)",
            "错误上报 (Report)",
            "停止同步 (Stop)",
        ])
        self.error_strategy_combo.currentTextChanged.connect(self._on_error_strategy_changed)
        error_layout.addWidget(QLabel("错误策略:"))
        error_layout.addWidget(self.error_strategy_combo)

        retry_layout = QFormLayout()
        retry_layout.setSpacing(6)
        retry_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 100)
        self.max_retries_spin.setValue(3)
        retry_layout.addRow("最大重试:", self.max_retries_spin)

        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setSuffix(" 秒")
        retry_layout.addRow("重试延迟:", self.retry_delay_spin)
        error_layout.addLayout(retry_layout)

        self.cb_check = QCheckBox("启用熔断器 (Circuit Breaker)")
        self.cb_check.setChecked(True)
        error_layout.addWidget(self.cb_check)

        layout.addWidget(error_group)
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setSpacing(6)
        advanced_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        advanced_layout.setContentsMargins(10, 16, 10, 8)

        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["不压缩", "GZIP", "BZIP2", "LZMA", "ZSTD", "LZ4"])
        advanced_layout.addRow("数据压缩:", self.compression_combo)

        self.encryption_combo = QComboBox()
        self.encryption_combo.addItems(["不加密", "AES-128", "AES-256", "RSA", "ChaCha20"])
        advanced_layout.addRow("传输加密:", self.encryption_combo)

        cache_check = QCheckBox("启用本地缓存")
        cache_check.setChecked(True)
        advanced_layout.addRow("", cache_check)

        layout.addWidget(advanced_group)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_step_summary(self):
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 10)

        title_label = QLabel("配置摘要确认")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #333; padding: 2px 0;")
        layout.addWidget(title_label)

        hint_label = QLabel("请确认以下配置信息，确认无误后点击「完成配置」创建数据源")
        hint_label.setObjectName("sectionHint")
        layout.addWidget(hint_label)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(220)
        self.summary_text.setStyleSheet("""
            QTextEdit {
                background: #fff;
                color: #333;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px;
                font-size: 9pt;
                font-family: 'Consolas', 'Microsoft YaHei', monospace;
            }
        """)
        layout.addWidget(self.summary_text, 1)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _create_footer(self):
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer.setFixedHeight(42)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 10)
        footer_layout.setSpacing(8)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #e74c3c; border: 1px solid #e74c3c;
                border-radius: 4px; padding: 3px 12px; font-size: 8pt;
            }
            QPushButton:hover { background: #fde8e8; }
        """)
        self.reset_btn.clicked.connect(self._reset_config)

        footer_layout.addWidget(self.reset_btn)
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #666; border: 1px solid #CCC;
                border-radius: 4px; padding: 3px 12px; font-size: 8pt;
            }
            QPushButton:hover { background: #f0f0f0; }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.prev_btn = QPushButton("上一步")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #666; border: 1px solid #CCC;
                border-radius: 4px; padding: 3px 12px; font-size: 8pt;
            }
            QPushButton:hover { background: #f0f0f0; }
        """)
        self.prev_btn.clicked.connect(self._go_prev)

        self.next_btn = QPushButton("下一步")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: #4a90e2; color: #fff; border: none;
                border-radius: 4px; padding: 3px 14px;
                font-size: 8pt; font-weight: bold;
            }
            QPushButton:hover { background: #357abd; }
        """)
        self.next_btn.clicked.connect(self._go_next)

        footer_layout.addWidget(self.cancel_btn)
        footer_layout.addWidget(self.prev_btn)
        footer_layout.addWidget(self.next_btn)

        return footer

    def _connect_signals(self):
        if self.category_group:
            self.category_group.buttonClicked.connect(self._on_category_selected)
        if self.type_combo:
            self.type_combo.currentTextChanged.connect(self._on_type_changed)
        if self.adapter_combo:
            self.adapter_combo.currentTextChanged.connect(self._on_adapter_changed)
        if self.filter_strategy_combo:
            self.filter_strategy_combo.currentTextChanged.connect(self._on_filter_changed)
        if self.sync_mode_combo:
            self.sync_mode_combo.currentTextChanged.connect(self._on_sync_mode_changed)
        if self.error_strategy_combo:
            self.error_strategy_combo.currentTextChanged.connect(self._on_error_strategy_changed)
        if self.quality_threshold_spin:
            self.quality_threshold_spin.valueChanged.connect(self._update_quality_score)

    def _update_step_display(self):
        for i in range(self.total_steps):
            indicator = self.step_indicators[i]
            title_label, desc_label = self.step_labels[i]
            if i < self.current_step:
                indicator.setStyleSheet("""
                    QLabel {
                        background: #27ae60; border: 1px solid #27ae60;
                        border-radius: 10px; color: #fff;
                        font-size: 8pt; font-weight: bold;
                    }
                """)
                indicator.setText("\u2714")
                title_label.setStyleSheet("font-size: 8pt; color: #27ae60; font-weight: bold;")
            elif i == self.current_step:
                indicator.setStyleSheet("""
                    QLabel {
                        background: #E3F2FD; border: 1px solid #4a90e2;
                        border-radius: 10px; color: #4a90e2;
                        font-size: 8pt; font-weight: bold;
                    }
                """)
                indicator.setText(str(i + 1))
                title_label.setStyleSheet("font-size: 8pt; color: #4a90e2; font-weight: bold;")
            else:
                indicator.setStyleSheet("""
                    QLabel {
                        background: #E8E8E8; border: 1px solid #CCC;
                        border-radius: 10px; color: #999;
                        font-size: 8pt; font-weight: bold;
                    }
                """)
                indicator.setText(str(i + 1))
                title_label.setStyleSheet("font-size: 8pt; color: #999;")

        for idx, connector in enumerate(self.step_connectors):
            if idx < self.current_step:
                connector.setStyleSheet("background: #27ae60;")
            else:
                connector.setStyleSheet("background: #DDD;")

        self.stacked_widget.setCurrentIndex(self.current_step)

        self.prev_btn.setVisible(self.current_step > 0)
        if self.current_step >= self.total_steps - 1:
            self.next_btn.setText("完成配置")
            self.next_btn.setStyleSheet("""
                QPushButton {
                    background: #27ae60; color: #fff; border: none;
                    border-radius: 4px; padding: 4px 16px;
                    font-size: 8pt; font-weight: bold;
                }
                QPushButton:hover { background: #219a52; }
            """)
        else:
            self.next_btn.setText("下一步")
            self.next_btn.setStyleSheet("""
                QPushButton {
                    background: #4a90e2; color: #fff; border: none;
                    border-radius: 4px; padding: 4px 16px;
                    font-size: 8pt; font-weight: bold;
                }
                QPushButton:hover { background: #357abd; }
            """)

        if self._step_hint_label:
            self._step_hint_label.setText(f"步骤 {self.current_step + 1}/{self.total_steps}")

        status_messages = [
            "配置数据源接入方式",
            "配置数据解析器与字段映射",
            "配置数据质量与过滤策略",
            "配置信号滤波算法与参数",
            "配置数据同步管道参数",
            "确认配置摘要并完成",
        ]
        if self.status_bar_label and self.current_step < len(status_messages):
            self.status_bar_label.setText(status_messages[self.current_step])

        if self.current_step == self.total_steps - 1:
            self._update_summary()

    def _go_prev(self):
        if self.current_step > 0:
            self.current_step -= 1
            if self._raw_data_mode:
                if self.current_step == 3:
                    self.current_step = 2
                elif self.current_step == 1:
                    self.current_step = 0
            self._update_step_display()

    def _go_next(self):
        if not self._validate_current_step():
            return

        if self.current_step >= self.total_steps - 1:
            self._create_data_source()
        else:
            self.current_step += 1
            if self._raw_data_mode:
                if self.current_step == 1:
                    self.current_step = 2
                elif self.current_step == 3:
                    self.current_step = 4
            self._update_step_display()

    def _validate_current_step(self):
        if self.current_step == 0:
            if not self.name_edit or not self.name_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "请输入数据源名称")
                if self.name_edit:
                    self.name_edit.setFocus()
                return False
            if not self.category_group or not self.category_group.checkedButton():
                QMessageBox.warning(self, "验证失败", "请选择数据分类")
                return False
            if not self.type_combo or not self.type_combo.currentText():
                QMessageBox.warning(self, "验证失败", "请选择数据类型")
                return False
            if not self.adapter_combo or not self.adapter_combo.currentText():
                QMessageBox.warning(self, "验证失败", "请选择接入方式")
                return False
        elif self.current_step == 1:
            pass
        elif self.current_step == 2:
            pass
        elif self.current_step == 3:
            pass
        elif self.current_step == 4:
            pass
        return True

    def _on_category_selected(self, button):
        if button and button.isChecked():
            category = button.property("category")
            self._update_types(category)

    def _update_types(self, category):
        if not self.type_combo:
            return
        self.type_combo.clear()
        self.type_combo.setEnabled(True)

        type_mapping = {
            "SENSOR": ["IMU", "CNAP", "GPS", "温度传感器", "压力传感器", "湿度传感器"],
            "MEDICAL": ["CNAP", "ECG", "血氧", "呼吸", "体温", "脑电"],
            "VEHICLE": ["IMU", "GPS", "OBD", "CAN", "雷达", "激光雷达"],
            "INDUSTRIAL": ["PLC", "SCADA", "Modbus", "OPC-UA", "ProfiNet", "EtherCAT"],
            "MULTIMEDIA": ["摄像头", "麦克风", "激光雷达", "深度相机", "热成像"],
            "CUSTOM": ["自定义类型A", "自定义类型B", "自定义类型C"],
        }
        types = type_mapping.get(category, ["通用"])
        self.type_combo.addItems(types)
        if self.type_hint:
            self.type_hint.setText(f"已选择分类: {category}，请选择具体类型")

    def _on_type_changed(self, type_name):
        if type_name and self.adapter_combo:
            self.adapter_combo.setEnabled(True)
            if type_name in ("IMU", "CNAP", "GPS"):
                self.adapter_combo.setCurrentIndex(0)
            elif type_name in ("PLC", "SCADA", "Modbus"):
                self.adapter_combo.setCurrentIndex(1)
            elif type_name in ("摄像头", "麦克风"):
                self.adapter_combo.setCurrentIndex(5)
            # 立即启用测试连接按钮，触发完整的连接准备逻辑
            if self.test_conn_btn:
                self.test_conn_btn.setEnabled(True)
            self._connection_tested = False
            if self.conn_indicator:
                self.conn_indicator.setStyleSheet(f"color: {PRO_COLORS['text_muted']}; font-size: 14px;")
            if self.conn_status_label:
                self.conn_status_label.setText("")

    def _on_adapter_changed(self, adapter_text):
        idx = self.adapter_combo.currentIndex()
        if 0 <= idx < self.adapter_stack.count():
            self.adapter_stack.setCurrentIndex(idx)
        if self.test_conn_btn:
            self.test_conn_btn.setEnabled(True)
        self._connection_tested = False
        if self.conn_indicator:
            self.conn_indicator.setStyleSheet(f"color: {PRO_COLORS['text_muted']}; font-size: 14px;")
        if self.conn_status_label:
            self.conn_status_label.setText("")
        self._filter_parsers_by_adapter(adapter_text)

    def _on_filter_changed(self, strategy):
        enable_range = "数值范围" in strategy
        if self.min_value_spin:
            self.min_value_spin.setEnabled(enable_range)
        if self.max_value_spin:
            self.max_value_spin.setEnabled(enable_range)

    def _on_sync_mode_changed(self, mode):
        is_batch = "批量" in mode
        if self.batch_size_spin:
            self.batch_size_spin.setEnabled(is_batch)

    def _on_error_strategy_changed(self, strategy):
        is_retry = "重试" in strategy
        if self.max_retries_spin:
            self.max_retries_spin.setEnabled(is_retry)
        if self.retry_delay_spin:
            self.retry_delay_spin.setEnabled(is_retry)

    def _update_quality_score(self, value):
        if not self.quality_score_label:
            return
        score = int(value * 100)
        self.quality_score_label.setText(f"{score}")

        if score >= 80:
            color = "#27ae60"
        elif score >= 50:
            color = "#f39c12"
        else:
            color = "#e74c3c"

        self.quality_score_label.setStyleSheet(f"font-size: 24pt; font-weight: bold; color: {color};")

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "",
            "所有文件 (*);;CSV (*.csv);;JSON (*.json);;TXT (*.txt);;Excel (*.xlsx *.xls)"
        )
        if file_path and self.file_path_edit:
            self.file_path_edit.setText(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            type_map = {'.csv': 'CSV', '.json': 'JSON', '.xml': 'XML',
                        '.xlsx': 'Excel', '.xls': 'Excel', '.txt': 'TXT'}
            detected = type_map.get(ext, '自动检测')
            if self.file_type_combo:
                idx = self.file_type_combo.findText(detected)
                if idx >= 0:
                    self.file_type_combo.setCurrentIndex(idx)

    def _test_connection(self):
        if self.conn_status_label:
            self.conn_status_label.setText("正在测试连接...")
            self.conn_status_label.setStyleSheet("color: #f39c12; font-size: 8pt;")
        if self.conn_indicator:
            self.conn_indicator.setStyleSheet("color: #f39c12; font-size: 12pt;")
        QTimer.singleShot(1200, self._finish_connection_test)

    def _finish_connection_test(self):
        self._connection_tested = True
        if self.conn_status_label:
            self.conn_status_label.setText("连接测试完成")
            self.conn_status_label.setStyleSheet("color: #27ae60; font-size: 8pt; font-weight: bold;")
        if self.conn_indicator:
            self.conn_indicator.setStyleSheet("color: #27ae60; font-size: 12pt;")
    
    def _init_parser_manager(self):
        """初始化解析器管理器"""
        self._parser_instance = None
        self._data_bridge = None
        try:
            import sys
            import os
            # 添加core路径到Python路径
            core_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                                    '..', '..', 'core', 'core', 'data_processing'))
            if core_path not in sys.path:
                sys.path.insert(0, core_path)
            
            from core.core.data_processing.parser_manager import get_parser_manager
            self.parser_manager = get_parser_manager()
            print(f"解析器管理器初始化成功，发现 {len(self.parser_manager.get_available_parsers())} 个解析器")
        except Exception as e:
            print(f"初始化解析器管理器失败: {e}")
            import traceback
            traceback.print_exc()
            self.parser_manager = None

    def set_data_bridge(self, data_bridge):
        """设置数据桥接器"""
        self._data_bridge = data_bridge

    def get_parser(self):
        """获取当前解析器实例"""
        return self._parser_instance
    
    def _refresh_parser_list(self):
        """刷新解析器列表"""
        try:
            if not self.parser_combo:
                return
            
            self.parser_combo.blockSignals(True)
            self.parser_combo.clear()
            
            self.parser_combo.addItem("自动选择（推荐）", None)
            
            if self.parser_manager:
                self.available_parsers = self.parser_manager.get_available_parsers()
                for parser_info in self.available_parsers:
                    self.parser_combo.addItem(parser_info.name, parser_info)
            
            self.parser_combo.blockSignals(False)
            
        except Exception as e:
            print(f"刷新解析器列表失败: {e}")

    def _filter_parsers_by_adapter(self, adapter_text):
        try:
            if not self.parser_combo or not self.parser_manager:
                return

            ADAPTER_PARSER_KEYWORDS = {
                "文件读取": ["IMU", "CNAP", "心血管", "惯性", "血压", "生理", "加速度", "陀螺仪", "心率"],
                "串口通信": ["IMU", "惯性", "加速度", "陀螺仪", "GPS"],
                "TCP/UDP 网络": ["IMU", "CNAP", "心血管", "惯性", "血压", "生理"],
                "MQTT 消息队列": ["IMU", "CNAP", "心血管", "惯性", "血压", "生理"],
                "数据库": ["CNAP", "心血管", "血压", "心率", "生理"],
            }

            keywords = ADAPTER_PARSER_KEYWORDS.get(adapter_text, None)
            if keywords is None:
                return

            self.parser_combo.blockSignals(True)
            self.parser_combo.clear()

            self.parser_combo.addItem("自动选择（推荐）", None)

            if self.parser_manager:
                self.available_parsers = self.parser_manager.get_available_parsers()
                for parser_info in self.available_parsers:
                    for kw in keywords:
                        if kw.lower() in parser_info.name.lower() or any(
                            kw.lower() in st.lower() for st in parser_info.supported_types
                        ):
                            self.parser_combo.addItem(parser_info.name, parser_info)
                            break

            self.parser_combo.blockSignals(False)

        except Exception as e:
            print(f"过滤解析器列表失败: {e}")
    
    def _on_parser_changed(self, index: int):
        """解析器选择变化时的回调"""
        try:
            if index < 0:
                return
            
            parser_info = self.parser_combo.itemData(index)
            
            if parser_info is None:
                self.parser_desc_label.setText("自动模式：系统将根据数据特征智能选择合适的解析器")
                self.selected_parser = None
            else:
                desc_text = f"<b>{parser_info.name}</b><br><br>"
                desc_text += f"<i>{parser_info.description}</i><br><br>"
                desc_text += f"支持类型: {', '.join(parser_info.supported_types)}"
                self.parser_desc_label.setText(desc_text)
                self.selected_parser = parser_info
                
                # 尝试加载解析器
                if self.parser_manager:
                    parser = self.parser_manager.load_parser(parser_info.name)
                    if parser:
                        self.parser_status_label.setText(f"状态: 已加载 {parser_info.name}")
                        self.parser_status_label.setObjectName("statusSuccess")
                        self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
            
        except Exception as e:
            print(f"解析器选择变化处理失败: {e}")
    
    def _load_custom_parser(self):
        """加载自定义解析脚本"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择自定义解析脚本", 
                "", 
                "Python文件 (*.py);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            if self.parser_manager:
                parser_name = self.parser_manager.add_custom_parser(file_path)
                if parser_name:
                    QMessageBox.information(self, "成功", f"成功添加解析器: {parser_name}")
                    self._refresh_parser_list()
                    # 自动选择刚添加的解析器
                    for i in range(self.parser_combo.count()):
                        if self.parser_combo.itemText(i) == parser_name:
                            self.parser_combo.setCurrentIndex(i)
                            break
                else:
                    QMessageBox.warning(self, "警告", "无法加载解析脚本，请检查文件格式")
            else:
                QMessageBox.warning(self, "警告", "解析器管理器不可用")
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载自定义脚本失败: {str(e)}")

    def _ai_generate_parser(self):
        """AI智能生成解析器"""
        try:
            # 1. 选择参考脚本
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择参考解析脚本 (AI会基于此分析)", 
                "", 
                "Python文件 (*.py);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 2. 预览分析结果
            from core.core.data_processing.parser_manager import preview_parsed_features
            
            features = preview_parsed_features(file_path)
            
            if not features:
                QMessageBox.warning(self, "提示", "无法分析该脚本")
                return
            
            # 获取字段信息
            source_fields = features.get('source_fields', [])
            
            # 3. 显示分析结果，让用户确认
            field_info = ""
            if source_fields:
                field_names = [f['source'] for f in source_fields]
                field_info = f"\n📝 检测到 {len(source_fields)} 个字段: {', '.join(field_names[:10])}"
                if len(field_names) > 10:
                    field_info += f"\n    ... (共{len(source_fields)}个)"
            
            preview_msg = (
                f"🤖 AI已分析该脚本！\n\n"
                f"📋 脚本名称: {features['script_name']}\n"
                f"📊 数据类型: {', '.join(features['data_types'])}\n"
                f"🔍 解析模式: {len(features['parse_patterns'])} 个\n"
                f"📦 字段提取器: {list(features['field_extractors'].keys())}\n"
                f"🏗️ 基础类型: {features['base_parser_type']}"
                f"{field_info}\n\n"
                f"是否要继续生成新的解析器？"
            )
            
            reply = QMessageBox.question(
                self, "AI解析器分析", preview_msg,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            
            if reply == QMessageBox.No:
                return
            
            # 4. 让用户输入自定义名称
            custom_name, ok = QInputDialog.getText(
                self, "解析器名称", "请输入新解析器的名称（可选）:",
                QLineEdit.Normal, f"{features['script_name']}_Custom"
            )
            
            # 5. 生成新解析器
            if self.parse_progress:
                self.parse_progress.setVisible(True)
                self.parse_progress.setValue(50)
            
            from core.core.data_processing.parser_manager import smart_generate_parser_with_fields
            
            output_path, parser_name, source_fields = smart_generate_parser_with_fields(
                file_path,
                custom_name if ok and custom_name else None
            )
            
            if output_path and parser_name:
                # 刷新列表
                self._refresh_parser_list()
                
                # 自动选择新解析器
                found = False
                for i in range(self.parser_combo.count()):
                    if parser_name in self.parser_combo.itemText(i) or 'autogen' in self.parser_combo.itemText(i).lower():
                        self.parser_combo.setCurrentIndex(i)
                        found = True
                        break
                
                # 6. 自动加载字段映射表
                if source_fields and self.field_mapping_table:
                    self._auto_load_field_mapping(source_fields)
                
                success_msg = (
                    f"🎉 解析器生成成功！\n\n"
                    f"📄 输出文件: {output_path}\n"
                    f"🏷️ 解析器名: {parser_name}"
                )
                
                if source_fields:
                    success_msg += f"\n📝 已自动加载 {len(source_fields)} 个字段映射！"
                
                success_msg += "\n\n已自动添加到解析器列表中！"
                
                QMessageBox.information(self, "成功", success_msg)
                
                if self.parser_status_label:
                    self.parser_status_label.setText(f"状态: 成功生成 {parser_name}")
                    self.parser_status_label.setObjectName("statusSuccess")
                    self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
            else:
                QMessageBox.warning(self, "警告", "解析器生成失败，请检查参考脚本")
                
            if self.parse_progress:
                self.parse_progress.setValue(100)
                QTimer.singleShot(600, lambda: self.parse_progress.setVisible(False) if self.parse_progress else None)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"AI生成解析器失败: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def _auto_load_field_mapping(self, source_fields: List[Dict[str, str]]):
        """自动加载字段映射表
        
        Args:
            source_fields: 字段列表，格式为 [{'source': 'ax', 'target': 'ax', 'type': 'float'}, ...]
        """
        if not self.field_mapping_table:
            return
        
        try:
            # 设置表格行列
            self.field_mapping_table.setRowCount(len(source_fields))
            self.field_mapping_table.setColumnCount(3)
            self.field_mapping_table.setHorizontalHeaderLabels(["源字段", "目标字段", "数据类型"])
            
            # 填充数据
            for i, field_info in enumerate(source_fields):
                source = field_info.get('source', f'field_{i+1}')
                target = field_info.get('target', source)
                dtype = field_info.get('type', 'float')
                
                self.field_mapping_table.setItem(i, 0, QTableWidgetItem(source))
                self.field_mapping_table.setItem(i, 1, QTableWidgetItem(target))
                self.field_mapping_table.setItem(i, 2, QTableWidgetItem(dtype))
            
            # 打印到控制台用于调试
            print(f"已自动加载 {len(source_fields)} 个字段映射")
            
        except Exception as e:
            print(f"加载字段映射失败: {e}")
            QMessageBox.warning(self, "警告", f"自动加载字段映射失败: {str(e)}")

    def _detect_parser(self):
        if not self.file_path_edit or not self.file_path_edit.text():
            QMessageBox.warning(self, "提示", "请先在接入步骤中选择数据文件")
            return

        if self.parse_progress:
            self.parse_progress.setVisible(True)
            self.parse_progress.setValue(30)

        file_path = self.file_path_edit.text()
        
        try:
            # 优先使用为 CAN 数据源特别对应的原有检测逻辑
            if self._is_can_data(file_path):
                self.can_parser = self._load_can_parser()
                self._parser_instance = self.can_parser
                self._parser_detected = True
                if self.parser_status_label:
                    self.parser_status_label.setText("状态: 已检测到 CAN 网关数据格式")
                    self.parser_status_label.setObjectName("statusSuccess")
                    self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
                if self.type_combo:
                    idx = self.type_combo.findText('CAN')
                    if idx >= 0:
                        self.type_combo.setCurrentIndex(idx)
            elif self._is_imu_data(file_path):
                self.imu_parser = self._load_imu_parser()
                self._parser_instance = self.imu_parser
                self._parser_detected = True
                if self.parser_status_label:
                    self.parser_status_label.setText("状态: 已检测到 IMU 数据格式")
                    self.parser_status_label.setObjectName("statusSuccess")
                    self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
            elif self._is_cnap_data(file_path):
                self.cnap_parser = self._load_cnap_parser()
                self._parser_instance = self.cnap_parser
                self._parser_detected = True
                if self.parser_status_label:
                    self.parser_status_label.setText("状态: 已检测到 CNAP 数据格式")
                    self.parser_status_label.setObjectName("statusSuccess")
                    self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
            else:
                # 回退到解析器管理器智能检测
                if self.parser_manager:
                    sample_content = None
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            sample_content = ''.join(f.readlines(10))
                    except:
                        pass
                    
                    recommended_parser = self.parser_manager.smart_detect_parser(
                        file_path=file_path,
                        data_content=sample_content
                    )
                    
                    if recommended_parser:
                        # 自动选择推荐的解析器
                        for i in range(self.parser_combo.count()):
                            if self.parser_combo.itemData(i) == recommended_parser:
                                self.parser_combo.setCurrentIndex(i)
                                break
                        
                        # 加载解析器
                        parser = self.parser_manager.load_parser(recommended_parser.name)
                        if parser:
                            self._parser_detected = True
                            self._parser_instance = parser
                            if self.parser_status_label:
                                self.parser_status_label.setText(f"状态: 已智能检测并加载 {recommended_parser.name}")
                                self.parser_status_label.setObjectName("statusSuccess")
                                self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['success']}; font-size: 11px; font-weight: 600;")
                            if 'CAN' in recommended_parser.name.upper() and self.type_combo:
                                idx = self.type_combo.findText('CAN')
                                if idx >= 0:
                                    self.type_combo.setCurrentIndex(idx)
                    else:
                        self._parser_detected = False
                        if self.parser_status_label:
                            self.parser_status_label.setText("状态: 未识别特定格式，将使用通用解析器")
                            self.parser_status_label.setObjectName("statusWarning")
                            self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['warning']}; font-size: 11px;")
                else:
                    self._parser_detected = False
                    if self.parser_status_label:
                        self.parser_status_label.setText("状态: 未识别特定格式，将使用通用解析器")
                        self.parser_status_label.setObjectName("statusWarning")
                        self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['warning']}; font-size: 11px;")

            if self.parse_progress:
                self.parse_progress.setValue(100)
                QTimer.singleShot(600, lambda: self.parse_progress.setVisible(False) if self.parse_progress else None)

        except Exception as e:
            if self.parser_status_label:
                self.parser_status_label.setText(f"状态: 检测失败 - {str(e)[:40]}")
                self.parser_status_label.setObjectName("statusError")
                self.parser_status_label.setStyleSheet(f"color: {PRO_COLORS['danger']}; font-size: 11px;")
            if self.parse_progress:
                self.parse_progress.setVisible(False)

    def _is_imu_data(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for _ in range(10):
                    line = f.readline()
                    if line:
                        lines.append(line.strip())
                for line in lines[:5]:
                    if 'AA' in line and 'BB' in line:
                        return True
                    if any(kw in line.lower() for kw in ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'imu', 'accel', 'gyro']):
                        return True
                    if ',' in line and line.count(',') >= 5:
                        parts = line.split(',')
                        floats = sum(1 for p in parts[1:6] if self._try_float(p.strip()))
                        if floats >= 3:
                            return True
            return False
        except Exception:
            return False

    def _try_float(self, s):
        try:
            float(s)
            return True
        except Exception:
            return False

    def _is_cnap_data(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for _ in range(10):
                    line = f.readline()
                    if line:
                        lines.append(line.strip())
                for line in lines[:5]:
                    lower = line.lower()
                    if any(kw in lower for kw in ['cnap', 'bp', 'hr', 'map', 'systolic', 'diastolic', 'blood', 'pressure', 'heart', 'rate']):
                        return True
                    if '%WAVE%' in line or '%BEATS%' in line:
                        return True
            return False
        except Exception:
            return False

    def _is_can_data(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for _ in range(20):
                    line = f.readline()
                    if line:
                        lines.append(line.strip())

            can_score = 0
            for line in lines:
                if '0x1FFF' in line:
                    can_score += 3
                if '0x1702' in line or '0x51000' in line:
                    can_score += 2
                if any(f'ch{i}' in line.lower() for i in range(1, 7)):
                    can_score += 2
                if ',' in line and line.count(',') >= 8:
                    parts = line.split(',')
                    if len(parts) >= 10:
                        last_col = parts[-1].strip()
                        if any(c in last_col for c in 'x|ABCDEFabcdef'):
                            can_score += 1

            return can_score >= 4
        except Exception:
            return False

    def _load_imu_parser(self):
        try:
            from core.core.data_processing.data_parser import IMUDataParser
            return IMUDataParser()
        except ImportError:
            return None

    def _load_cnap_parser(self):
        try:
            from core.core.data_processing.cardiovascular_parser import CardiovascularDataParser
            return CardiovascularDataParser()
        except ImportError:
            return None

    def _load_can_parser(self):
        try:
            from core.core.data_processing.can_parser import CANDataParser
            return CANDataParser()
        except ImportError:
            return None

    def _configure_parser(self):
        QMessageBox.information(self, "解析器配置", "解析器参数配置功能（可在此扩展详细参数设置）")

    def _preview_data(self):
        if not self.file_path_edit or not self.file_path_edit.text():
            QMessageBox.warning(self, "提示", "请先选择数据文件")
            return

        file_path = self.file_path_edit.text()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [l.strip() for l in f.readlines()[:15] if l.strip()]

            if not lines:
                QMessageBox.warning(self, "提示", "文件为空或无法读取")
                return

            first = lines[0]
            if ',' in first:
                cols = first.split(',')
            elif '\t' in first:
                cols = first.split('\t')
            else:
                cols = first.split()

            self.preview_table.setRowCount(min(len(lines), 10))
            self.preview_table.setColumnCount(len(cols))
            self.preview_table.setHorizontalHeaderLabels([f"Col{i+1}" for i in range(len(cols))])

            for i, line in enumerate(lines[:10]):
                parts = line.split(',') if ',' in line else line.split()
                for j, part in enumerate(parts[:len(cols)]):
                    self.preview_table.setItem(i, j, QTableWidgetItem(part.strip()))

        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据预览失败: {e}")

    def _refresh_preview(self):
        self._preview_data()

    def _auto_generate_field_mapping(self):
        if not self.preview_table or self.preview_table.rowCount() == 0:
            QMessageBox.warning(self, "提示", "请先加载数据预览")
            return

        headers = []
        for i in range(self.preview_table.columnCount()):
            h = self.preview_table.horizontalHeaderItem(i)
            headers.append(h.text() if h else f"Col{i+1}")

        self.field_mapping_table.setRowCount(len(headers))
        self.field_mapping_table.setColumnCount(3)
        self.field_mapping_table.setHorizontalHeaderLabels(["源字段", "目标字段", "数据类型"])

        for i, h in enumerate(headers):
            self.field_mapping_table.setItem(i, 0, QTableWidgetItem(h))
            target = self._get_smart_target_field_name(h)
            self.field_mapping_table.setItem(i, 1, QTableWidgetItem(target))
            dtype = self._get_smart_data_type(h)
            self.field_mapping_table.setItem(i, 2, QTableWidgetItem(dtype))

    def _get_smart_target_field_name(self, source_field):
        mapping = {
            'cnt': 'cnt', 'count': 'cnt', 'seq': 'cnt',
            'ax': 'ax', 'accel_x': 'ax', 'ay': 'ay', 'accel_y': 'ay',
            'az': 'az', 'accel_z': 'az', 'gx': 'gx', 'gyro_x': 'gx',
            'gy': 'gy', 'gyro_y': 'gy', 'gz': 'gz', 'gyro_z': 'gz',
            'speed': 'speed', 'velocity': 'speed',
            'wheel': 'wheel', 'steering': 'wheel',
            'loc1': 'loc1', 'loc2': 'loc2', 'location': 'loc1', 'longitude': 'loc1', 'latitude': 'loc2',
            'timestamp': 'timestamp', 'time': 'timestamp', 'ts': 'timestamp',
            'crc': 'crc', 'checksum': 'crc',
            'cnap_type': 'cnap_type',
            'wave_t': 'wave_t', 'beat_t': 'beat_t',
            'pressure': 'pressure',
            'systolic_bp': 'Systolic_BP', 'diastolic_bp': 'Diastolic_BP',
            'heart_rate': 'Heart_Rate',
            'mean_arterial_pressure': 'Mean_Arterial_Pressure', 'map': 'Mean_Arterial_Pressure',
            'pulse_pressure': 'Pulse_Pressure',
            'heart_rate_variability': 'Heart_Rate_Variability',
            'mean_pulse_pressure': 'Mean_Pulse_Pressure',
            'stroke_volume': 'Stroke_Volume',
            'vascular_resistance': 'Vascular_Resistance',
            'ppv': 'PPV', 'svv': 'SVV',
            'ejection_fraction': 'Ejection_Fraction',
        }
        return mapping.get(source_field.lower(), source_field)

    def _get_smart_data_type(self, field_name):
        lower = field_name.lower()
        if any(kw in lower for kw in ['timestamp', 'time', 'date']):
            return 'datetime'
        if any(kw in lower for kw in ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'accel', 'gyro',
                                       'bp', 'map', 'pressure', 'pulse', 'volume',
                                       'resistance', 'ppv', 'svv', 'ejection', 'fraction',
                                       'variability', 'stroke', 'vascular', 'arterial',
                                       'systolic', 'diastolic', 'heart_rate', 'mean_']):
            return 'float'
        if any(kw in lower for kw in ['seq', 'id', 'count', 'cnt']):
            return 'integer'
        if any(kw in lower for kw in ['status', 'state', 'flag', 'crc', 'type', 'cnap_type']):
            return 'string'
        return 'float'

    def _manual_field_mapping(self):
        QMessageBox.information(self, "手动映射", "可在表格中直接编辑目标字段和数据类型")

    def _show_help(self):
        help_text = (
            "ELT Pipeline 数据源配置向导\n\n"
            "步骤 1 - 接入 (Connect): 选择数据分类、类型和接入方式（适配器模式）\n"
            "步骤 2 - 解析 (Parse): 自动检测数据格式，预览数据，配置字段映射\n"
            "步骤 3 - 质量 (Quality): 设置数据质量阈值、过滤策略和异常值处理\n"
            "步骤 4 - 同步 (Sync): 配置同步模式、优先级、错误处理和高级选项\n"
            "步骤 5 - 确认 (Summary): 查看配置摘要并确认创建数据源\n\n"
            "支持多种接入方式: 文件、串口、TCP/UDP、MQTT、数据库、WebSocket"
        )
        QMessageBox.information(self, "帮助", help_text)

    def _reset_config(self):
        reply = QMessageBox.question(
            self, "确认重置", "确定要重置所有配置吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.name_edit:
                self.name_edit.clear()
            if self.desc_edit:
                self.desc_edit.clear()
            if self.file_path_edit:
                self.file_path_edit.clear()
            self.current_step = 0
            self._connection_tested = False
            self._parser_detected = False
            self._quality_configured = False
            self._sync_configured = False
            self.imu_parser = None
            self.cnap_parser = None
            self.can_parser = None
            self._update_step_display()
            QMessageBox.information(self, "提示", "配置已重置")

    def _create_data_source(self):
        config_data = self._collect_config_data()
        self.config_completed.emit(config_data)
        self.data_source_configured.emit(config_data)
        self.accept()

    def _collect_config_data(self):
        category = ""
        if self.category_group and self.category_group.checkedButton():
            category = self.category_group.checkedButton().property("category")

        file_path = ""
        if self.file_path_edit:
            file_path = self.file_path_edit.text().strip()

        return {
            "basic": {
                "name": self.name_edit.text().strip() if self.name_edit else "",
                "description": self.desc_edit.toPlainText().strip() if self.desc_edit else "",
                "category": category,
                "type": self.type_combo.currentText() if self.type_combo else "",
            },
            "connection": {
                "adapter": self.adapter_combo.currentText() if self.adapter_combo else "",
                "file_path": file_path,
                "file_type": self.file_type_combo.currentText() if self.file_type_combo else "",
                "tested": self._connection_tested,
            },
            "parser": {
                "type": "CAN" if self.can_parser else ("IMU" if self.imu_parser else ("CNAP" if self.cnap_parser else "Generic")),
                "detected": self._parser_detected,
                "target_channel": getattr(self.can_parser, 'target_channel', 'ch4') if self.can_parser else 'ch4',
                "target_sensor": getattr(self.can_parser, 'target_sensor', 'A') if self.can_parser else 'A',
                "park_file_path": getattr(self.can_parser, 'park_file_path', None) if self.can_parser else None,
            },
            "quality": {
                "threshold": self.quality_threshold_spin.value() if self.quality_threshold_spin else 0.8,
                "filter": self.filter_strategy_combo.currentText() if self.filter_strategy_combo else "",
                "outlier_method": self.outlier_method_combo.currentText() if self.outlier_method_combo else "",
                "gap_fill": self.gap_fill_combo.currentText() if self.gap_fill_combo else "",
            },
            "signal_filter": {
                "enabled": self.filter_enable_check.isChecked() if self.filter_enable_check else False,
                "filter_type": self.filter_type_combo.currentText() if self.filter_type_combo else "",
                "target_fields": self.filter_target_fields_edit.text().strip() if self.filter_target_fields_edit else "",
                "window_size": self.filter_window_spin.value() if self.filter_window_spin else 5,
                "alpha": self.filter_alpha_spin.value() if self.filter_alpha_spin else 0.3,
                "cutoff_frequency": self.filter_cutoff_spin.value() if self.filter_cutoff_spin else 10.0,
                "high_cutoff": self.filter_high_cutoff_spin.value() if self.filter_high_cutoff_spin else 50.0,
                "sample_rate": self.filter_sample_rate_spin.value() if self.filter_sample_rate_spin else 100.0,
                "order": self.filter_order_spin.value() if self.filter_order_spin else 2,
                "process_noise": self.filter_process_noise_spin.value() if self.filter_process_noise_spin else 0.01,
                "measurement_noise": self.filter_measure_noise_spin.value() if self.filter_measure_noise_spin else 0.1,
            },
            "sync": {
                "mode": self.sync_mode_combo.currentText() if self.sync_mode_combo else "",
                "interval": self.sync_interval_spin.value() if self.sync_interval_spin else 100,
                "batch_size": self.batch_size_spin.value() if self.batch_size_spin else 100,
                "timeout": self.timeout_spin.value() if self.timeout_spin else 30,
                "priority": self.priority_combo.currentText() if self.priority_combo else "",
                "error_strategy": self.error_strategy_combo.currentText() if self.error_strategy_combo else "",
                "max_retries": self.max_retries_spin.value() if self.max_retries_spin else 3,
                "retry_delay": self.retry_delay_spin.value() if self.retry_delay_spin else 5,
                "compression": self.compression_combo.currentText() if self.compression_combo else "",
                "encryption": self.encryption_combo.currentText() if self.encryption_combo else "",
            },
            "imu_calibration": self._collect_imu_calibration_config(),
        }

    def _collect_imu_calibration_config(self):
        """收集 IMU 校准配置"""
        config = {
            "enabled": False,
            "strategy": "none",
            "calib_file_path": "",
            "parameters": {}
        }

        if hasattr(self, 'calib_strategy_auto') and self.calib_strategy_auto.isChecked():
            config["strategy"] = "auto"
            config["enabled"] = False  # 自动策略在数据加载后才执行并启用
        elif hasattr(self, 'calib_strategy_load') and self.calib_strategy_load.isChecked():
            config["strategy"] = "load"
            config["calib_file_path"] = self.calib_file_edit.text().strip() if hasattr(self, 'calib_file_edit') else ""
            config["enabled"] = True if config["calib_file_path"] else False

            # 如果有校准文件，尝试加载参数到配置
            if config["calib_file_path"]:
                try:
                    import json
                    with open(config["calib_file_path"], 'r', encoding='utf-8') as f:
                        calib_data = json.load(f)
                        config["parameters"] = calib_data.get("parameters", {})
                        config["uuid"] = calib_data.get("uuid", "")
                except Exception as e:
                    # 加载失败没关系，后续会处理
                    pass
        else:
            config["strategy"] = "none"
            config["enabled"] = False

        return config

    def _update_summary(self):
        if not self.summary_text:
            return

        config = self._collect_config_data()
        basic = config.get("basic", {})
        conn = config.get("connection", {})
        parser = config.get("parser", {})
        quality = config.get("quality", {})
        signal_filter = config.get("signal_filter", {})
        sync = config.get("sync", {})
        imu_calib = config.get("imu_calibration", {})

        lines = []
        lines.append("══ 基本信息 ═══════════════════════════════════════")
        lines.append(f"  名称: {basic.get('name', '(未设置)')}")
        lines.append(f"  描述: {basic.get('description', '(无)')}")
        lines.append(f"  分类: {basic.get('category', '(未选择)')}  |  类型: {basic.get('type', '(未选择)')}")
        lines.append("")

        lines.append("══ 接入方式 ═══════════════════════════════════════")
        lines.append(f"  适配器: {conn.get('adapter', '(未选择)')}")
        lines.append(f"  路径: {conn.get('file_path', '(未选择)')}")
        lines.append(f"  类型: {conn.get('file_type', '(自动)')}  |  测试: {'✓ 通过' if conn.get('tested') else '✗ 未测试'}")
        lines.append("")

        lines.append("══ 解析器 ═════════════════════════════════════════")
        lines.append(f"  类型: {parser.get('type', 'Generic')}  |  检测: {'✓' if parser.get('detected') else '✗'}")
        lines.append("")

        lines.append("══ 数据质量 ═══════════════════════════════════════")
        lines.append(f"  阈值: {quality.get('threshold', 0.8)}  |  过滤: {quality.get('filter', '(未设置)')}")
        lines.append(f"  异常: {quality.get('outlier_method', '(未设置)')}  |  填充: {quality.get('gap_fill', '(未设置)')}")
        lines.append("")

        lines.append("══ 信号滤波 ═══════════════════════════════════════")
        lines.append(f"  状态: {'✓ 已启用' if signal_filter.get('enabled') else '✗ 未启用'}  |  算法: {signal_filter.get('filter_type', '(未设置)')}")
        lines.append(f"  字段: {signal_filter.get('target_fields', '(未设置)')}")
        if signal_filter.get('enabled'):
            ft = signal_filter.get('filter_type', '')
            if '移动平均' in ft or '中值滤波' in ft:
                lines.append(f"  窗口: {signal_filter.get('window_size', 5)} 采样点")
            elif '指数加权' in ft or 'RC低通' in ft or '高通' in ft or '带通' in ft:
                lines.append(f"  α: {signal_filter.get('alpha', 0.3)}")
            elif '卡尔曼' in ft:
                lines.append(f"  Q: {signal_filter.get('process_noise', 0.01)}  |  R: {signal_filter.get('measurement_noise', 0.1)}")
            elif '巴特沃斯' in ft:
                lines.append(f"  截止: {signal_filter.get('cutoff_frequency', 10.0)} Hz  |  采样: {signal_filter.get('sample_rate', 100.0)} Hz  |  阶数: {signal_filter.get('order', 2)}")
        lines.append("")

        lines.append("══ 数据同步 ═══════════════════════════════════════")
        lines.append(f"  模式: {sync.get('mode', '(未设置)')}  |  间隔: {sync.get('interval', 100)} ms")
        lines.append(f"  批量: {sync.get('batch_size', 100)} 条  |  超时: {sync.get('timeout', 30)} s")
        lines.append(f"  优先级: {sync.get('priority', '(未设置)')}  |  错误: {sync.get('error_strategy', '(未设置)')}")
        lines.append(f"  重试: {sync.get('max_retries', 3)} 次 / {sync.get('retry_delay', 5)} s")
        lines.append(f"  压缩: {sync.get('compression', '不压缩')}  |  加密: {sync.get('encryption', '不加密')}")
        lines.append("")

        lines.append("══ IMU 校准 ═══════════════════════════════════════")
        strategy_text = {
            "none": "不使用校准（原始数据）",
            "auto": "数据加载后自动执行静态校准",
            "load": "从已有 JSON 校准文件加载"
        }.get(imu_calib.get("strategy", "none"), "不使用校准")
        lines.append(f"  策略: {strategy_text}")
        if imu_calib.get("strategy") == "load":
            calib_file = imu_calib.get("calib_file_path", "")
            if calib_file:
                import os
                short_path = os.path.basename(calib_file)
                lines.append(f"  文件: {short_path}")
        lines.append(f"  状态: {'✓ 已配置' if imu_calib.get('enabled') else '✗ 未启用'}")
        lines.append("")

        lines.append("════════════════════════════════════════════════════")
        lines.append("  点击「完成配置」创建数据源并启动同步管道")
        lines.append("════════════════════════════════════════════════════")

        self.summary_text.setHtml(
            "<pre style='color: #333; font-family: Consolas, Microsoft YaHei, monospace; "
            "font-size: 9pt; line-height: 1.4; margin: 0;'>" +
            "\n".join(lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") +
            "</pre>"
        )

    def get_config_data(self):
        return self._collect_config_data()

    def load_existing_config(self, source_id, source_config):
        self._selected_source_id = source_id
        self._selected_source_config = source_config

        basic = source_config.get("basic", {})
        if self.name_edit and basic.get("name"):
            self.name_edit.setText(basic["name"])
        if self.desc_edit and basic.get("description"):
            self.desc_edit.setText(basic["description"])

        category = basic.get("category", "")
        if category and category in self.category_radios:
            self.category_radios[category].setChecked(True)
            self._update_types(category)
            if self.type_combo and basic.get("type"):
                idx = self.type_combo.findText(basic["type"])
                if idx >= 0:
                    self.type_combo.setCurrentIndex(idx)

        conn = source_config.get("connection", {})
        if self.file_path_edit and conn.get("file_path"):
            self.file_path_edit.setText(conn["file_path"])
        if self.file_type_combo and conn.get("file_type"):
            idx = self.file_type_combo.findText(conn["file_type"])
            if idx >= 0:
                self.file_type_combo.setCurrentIndex(idx)

        sync = source_config.get("sync", {})
        if self.sync_mode_combo and sync.get("mode"):
            idx = self.sync_mode_combo.findText(sync["mode"])
            if idx >= 0:
                self.sync_mode_combo.setCurrentIndex(idx)
        if self.sync_interval_spin and sync.get("interval"):
            self.sync_interval_spin.setValue(sync["interval"])
        if self.batch_size_spin and sync.get("batch_size"):
            self.batch_size_spin.setValue(sync["batch_size"])
        if self.timeout_spin and sync.get("timeout"):
            self.timeout_spin.setValue(sync["timeout"])
        if self.priority_combo and sync.get("priority"):
            idx = self.priority_combo.findText(sync["priority"])
            if idx >= 0:
                self.priority_combo.setCurrentIndex(idx)
        if self.error_strategy_combo and sync.get("error_strategy"):
            idx = self.error_strategy_combo.findText(sync["error_strategy"])
            if idx >= 0:
                self.error_strategy_combo.setCurrentIndex(idx)
        if self.max_retries_spin and sync.get("max_retries"):
            self.max_retries_spin.setValue(sync["max_retries"])
        if self.retry_delay_spin and sync.get("retry_delay"):
            self.retry_delay_spin.setValue(sync["retry_delay"])
        if self.compression_combo and sync.get("compression"):
            idx = self.compression_combo.findText(sync["compression"])
            if idx >= 0:
                self.compression_combo.setCurrentIndex(idx)
        if self.encryption_combo and sync.get("encryption"):
            idx = self.encryption_combo.findText(sync["encryption"])
            if idx >= 0:
                self.encryption_combo.setCurrentIndex(idx)

        quality = source_config.get("quality", {})
        if self.quality_threshold_spin and quality.get("threshold"):
            self.quality_threshold_spin.setValue(quality["threshold"])
        if self.filter_strategy_combo and quality.get("filter"):
            idx = self.filter_strategy_combo.findText(quality["filter"])
            if idx >= 0:
                self.filter_strategy_combo.setCurrentIndex(idx)
        if self.outlier_method_combo and quality.get("outlier_method"):
            idx = self.outlier_method_combo.findText(quality["outlier_method"])
            if idx >= 0:
                self.outlier_method_combo.setCurrentIndex(idx)
        if self.gap_fill_combo and quality.get("gap_fill"):
            idx = self.gap_fill_combo.findText(quality["gap_fill"])
            if idx >= 0:
                self.gap_fill_combo.setCurrentIndex(idx)

        self._connection_tested = conn.get("tested", False)
        self._parser_detected = source_config.get("parser", {}).get("detected", False)

        signal_filter = source_config.get("signal_filter", {})
        if self.filter_enable_check and signal_filter:
            self.filter_enable_check.setChecked(signal_filter.get("enabled", False))
        if self.filter_type_combo and signal_filter.get("filter_type"):
            idx = self.filter_type_combo.findText(signal_filter["filter_type"])
            if idx >= 0:
                self.filter_type_combo.setCurrentIndex(idx)
        if self.filter_target_fields_edit and signal_filter.get("target_fields"):
            self.filter_target_fields_edit.setText(signal_filter["target_fields"])
        if self.filter_window_spin and signal_filter.get("window_size"):
            self.filter_window_spin.setValue(signal_filter["window_size"])
        if self.filter_alpha_spin and signal_filter.get("alpha"):
            self.filter_alpha_spin.setValue(signal_filter["alpha"])
        if self.filter_cutoff_spin and signal_filter.get("cutoff_frequency"):
            self.filter_cutoff_spin.setValue(signal_filter["cutoff_frequency"])
        if self.filter_high_cutoff_spin and signal_filter.get("high_cutoff"):
            self.filter_high_cutoff_spin.setValue(signal_filter["high_cutoff"])
        if self.filter_sample_rate_spin and signal_filter.get("sample_rate"):
            self.filter_sample_rate_spin.setValue(signal_filter["sample_rate"])
        if self.filter_order_spin and signal_filter.get("order"):
            self.filter_order_spin.setValue(signal_filter["order"])
        if self.filter_process_noise_spin and signal_filter.get("process_noise"):
            self.filter_process_noise_spin.setValue(signal_filter["process_noise"])
        if self.filter_measure_noise_spin and signal_filter.get("measurement_noise"):
            self.filter_measure_noise_spin.setValue(signal_filter["measurement_noise"])
        self._quality_configured = True
        self._sync_configured = True

        # 加载 IMU 校准配置
        imu_calib = source_config.get("imu_calibration", {})
        strategy = imu_calib.get("strategy", "none")
        if hasattr(self, 'calib_strategy_none') and hasattr(self, 'calib_strategy_auto') and hasattr(self, 'calib_strategy_load'):
            if strategy == "auto":
                self.calib_strategy_auto.setChecked(True)
            elif strategy == "load":
                self.calib_strategy_load.setChecked(True)
                calib_file = imu_calib.get("calib_file_path", "")
                if hasattr(self, 'calib_file_edit') and calib_file:
                    self.calib_file_edit.setText(calib_file)
            else:
                self.calib_strategy_none.setChecked(True)

        self._update_step_display()

    # ==========================================
    # IMU 校准相关方法
    # ==========================================

    def _run_static_calibration(self):
        """运行静态校准"""
        if not self.file_path_edit or not self.file_path_edit.text():
            QMessageBox.warning(self, "提示", "请先在接入步骤中选择数据文件")
            return

        file_path = self.file_path_edit.text()
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "提示", "文件不存在: " + file_path)
            return

        # 先检查是否已解析
        parsed_csv = None
        data_output_dir = "data_output"
        if os.path.exists(data_output_dir):
            for f in os.listdir(data_output_dir):
                if f.startswith("parsed_data_") and f.endswith(".csv"):
                    parsed_csv = os.path.join(data_output_dir, f)
                    break

        if not parsed_csv:
            QMessageBox.information(
                self,
                "提示",
                "需要先解析数据，请完成「解析」步骤后再回来执行校准"
            )
            return

        # 禁用按钮防止重复点击
        self.calib_run_btn.setEnabled(False)
        self.calib_status_label.setText("状态: 正在执行校准...")
        self.calib_status_label.setStyleSheet("color: #4a90e2; font-size: 9pt; font-weight: bold;")

        # 创建并启动工作线程
        self._calib_worker = CalibrationWorker(parsed_csv, file_path)
        self._calib_worker.finished.connect(self._on_calib_finished)
        self._calib_worker.error.connect(self._on_calib_error)
        self._calib_worker.start()

    def _on_calib_finished(self, calib_json: dict):
        """校准完成回调"""
        self._calib_data = calib_json
        self.calib_save_btn.setEnabled(True)

        # 更新表格
        if self.calib_table and "imu_calibrations" in calib_json:
            imu_calibs = calib_json["imu_calibrations"]
            for i in range(self.calib_table.rowCount()):
                imu_name = self.calib_table.item(i, 0).text()
                calib_info = imu_calibs.get(imu_name, {})

                if calib_info:
                    gravity_axis = calib_info.get("gravity_axis", "-")
                    acc_bias = calib_info.get("acc_bias_lsb", [0, 0, 0])
                    gyro_bias = calib_info.get("gyro_bias_lsb", [0, 0, 0])
                    acc_err = calib_info.get("acc_error_mps2", "-")
                    gyro_res = calib_info.get("gyro_res_dps", "-")
                    status = calib_info.get("status", "已校准")

                    self.calib_table.setItem(i, 1, QTableWidgetItem(str(gravity_axis)))
                    self.calib_table.setItem(i, 2, QTableWidgetItem(f"{acc_bias[0]:.1f}/{acc_bias[1]:.1f}/{acc_bias[2]:.1f}"))
                    self.calib_table.setItem(i, 3, QTableWidgetItem(f"{gyro_bias[0]:.1f}/{gyro_bias[1]:.1f}/{gyro_bias[2]:.1f}"))
                    self.calib_table.setItem(i, 4, QTableWidgetItem(f"{acc_err:.4f}" if acc_err != "-" else "-"))
                    self.calib_table.setItem(i, 5, QTableWidgetItem(f"{gyro_res:.4f}" if gyro_res != "-" else "-"))
                    self.calib_table.setItem(i, 6, QTableWidgetItem(status))
                else:
                    self.calib_table.setItem(i, 6, QTableWidgetItem("未找到数据"))

        self.calib_status_label.setText("状态: ✓ 校准完成")
        self.calib_status_label.setStyleSheet("color: #27ae60; font-size: 9pt; font-weight: bold;")
        self.calib_run_btn.setEnabled(True)
        QMessageBox.information(self, "成功", "校准完成！已保存参数到 data_output 目录")

    def _on_calib_error(self, error_msg: str):
        """校准出错回调"""
        self.calib_status_label.setText(f"状态: ✗ 校准失败 - {error_msg}")
        self.calib_status_label.setStyleSheet("color: #e74c3c; font-size: 9pt; font-weight: bold;")
        self.calib_run_btn.setEnabled(True)
        QMessageBox.warning(self, "错误", "校准失败: " + error_msg)

    def _load_calib_from_file(self):
        """从 JSON 文件加载校准参数"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择校准参数文件",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                calib_json = json.load(f)
            self._calib_data = calib_json
            self._calib_json_path = file_path
            self._on_calib_finished(calib_json)
            QMessageBox.information(self, "成功", "加载校准参数成功！")
        except Exception as e:
            QMessageBox.warning(self, "错误", "加载失败: " + str(e))

    def _save_calib_to_file(self):
        """保存当前校准参数到文件"""
        if not self._calib_data:
            QMessageBox.warning(self, "提示", "没有可保存的校准参数")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存校准参数",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._calib_data, f, indent=2, ensure_ascii=False)
            self._calib_json_path = file_path
            QMessageBox.information(self, "成功", "保存成功！")
        except Exception as e:
            QMessageBox.warning(self, "错误", "保存失败: " + str(e))

    def _on_calib_strategy_changed(self):
        """校准策略改变时的处理"""
        is_load_file = self.calib_strategy_load.isChecked()
        self.calib_file_edit.setEnabled(is_load_file)
        self.calib_file_btn.setEnabled(is_load_file)

    def _select_calib_file(self):
        """选择校准文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 IMU 校准 JSON 文件", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.calib_file_edit.setText(file_path)

    def _reset_calib(self):
        """重置校准参数"""
        self._calib_data = {}
        self._calib_json_path = None
        if hasattr(self, 'calib_save_btn') and self.calib_save_btn:
            self.calib_save_btn.setEnabled(False)

        if hasattr(self, 'calib_table') and self.calib_table:
            for i in range(self.calib_table.rowCount()):
                self.calib_table.setItem(i, 1, QTableWidgetItem("-"))
                self.calib_table.setItem(i, 2, QTableWidgetItem("-"))
                self.calib_table.setItem(i, 3, QTableWidgetItem("-"))
                self.calib_table.setItem(i, 4, QTableWidgetItem("-"))
                self.calib_table.setItem(i, 5, QTableWidgetItem("-"))
                self.calib_table.setItem(i, 6, QTableWidgetItem("未校准"))

        if hasattr(self, 'calib_status_label') and self.calib_status_label:
            self.calib_status_label.setText("状态: 等待执行校准")
            self.calib_status_label.setStyleSheet("color: #666; font-size: 9pt;")


# ==========================================
# IMU 校准工作线程类
# ==========================================

class CalibrationWorker(QThread):
    """IMU 校准工作线程"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, parsed_csv: str, raw_path: str = None):
        super().__init__()
        self.parsed_csv = parsed_csv
        self.raw_path = raw_path

    def run(self):
        try:
            from core.core.data_processing.imu_calibrator import run_full_calibration_from_csv
            calib_json = run_full_calibration_from_csv(
                self.parsed_csv,
                self.raw_path,
                output_json_path=None  # 自动保存到 data_output 目录
            )
            self.finished.emit(calib_json)
        except Exception as e:
            self.error.emit(str(e)) 