#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 整合日期: 2026-05-03
# 整合内容: 合并 analysis_control, sync_control, parsing_control,
#           system_control, module_coordinator, unified_workflow_panel,
#           parsing_control_simple, performance_visualization 功能
# ============================================================
"""
左侧控制面板 - 统一整合版本
整合了数据源管理、同步控制、解析控制、分析控制、系统控制五大功能模块
"""

import logging
import time
import os
import json
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QFrame, QProgressBar,
    QCheckBox, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QScrollArea, QTabWidget, QStackedWidget, QSlider, QLineEdit,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont


class IntegratedControlPanel(QWidget):
    """统一左侧控制面板 - 整合所有功能模块"""

    action_triggered = Signal(str, dict)
    module_status_changed = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.panel_name = "控制面板"

        self.sub_modules = {}
        self._setup_state()

        self._init_ui()
        self._connect_all_signals()
        self._start_monitors()

        self.logger.info("统一控制面板初始化完成")

    def _setup_state(self):
        self.sync_running = False
        self.sync_paused = False
        self.parsing_running = False
        self.parsing_paused = False
        self.basic_analysis_running = False
        self.advanced_analysis_running = False
        self.training_running = False
        self.analysis_count = 0
        self.parsed_count = 0
        self.error_count = 0

    def _init_ui(self):
        self.setMaximumWidth(380)
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        title_label = QLabel("控制面板")
        title_label.setObjectName("panelTitle")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.global_status_badge = QLabel("就绪")
        self.global_status_badge.setObjectName("statusBadge")
        header_layout.addWidget(self.global_status_badge)

        layout.addWidget(header)

        self._create_dashboard_metrics(layout)

        separator = QFrame()
        separator.setObjectName("separatorH")
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)

        self._create_data_source_group(content_layout)
        self._create_sync_group(content_layout)
        self._create_parsing_group(content_layout)
        self._create_analysis_group(content_layout)
        self._create_system_group(content_layout)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _create_dashboard_metrics(self, parent_layout):
        dashboard = QWidget()
        dashboard_layout = QHBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(8)

        metrics_data = [
            ("ds_total", "数据源", "0", "miniCardValueAccent"),
            ("ds_connected", "已连接", "0", "miniCardValueSuccess"),
            ("sync_freq", "同步频率", "0 Hz", "miniCardValue"),
            ("cpu_usage", "CPU", "0%", "miniCardValueWarning"),
        ]

        for obj_name, title, value, style_class in metrics_data:
            card = QFrame()
            card.setObjectName("miniCard")
            card.setMinimumSize(70, 50)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(1)

            title_label = QLabel(title)
            title_label.setObjectName("miniCardTitle")
            card_layout.addWidget(title_label)

            value_label = QLabel(value)
            value_label.setObjectName(style_class)
            setattr(self, f"{obj_name}_metric_label", value_label)
            card_layout.addWidget(value_label)

            dashboard_layout.addWidget(card)

        parent_layout.addWidget(dashboard)

    def _create_data_source_group(self, parent_layout):
        group = QGroupBox("数据源管理")
        group.setObjectName("panelGroup")
        group.setMaximumWidth(360)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.data_source_status_label = QLabel("状态: 就绪")
        self.data_source_status_label.setObjectName("statValueSuccess")
        layout.addWidget(self.data_source_status_label)

        overview_layout = QGridLayout()
        overview_layout.setSpacing(4)
        self.total_sources_label = QLabel("总数: 0")
        self.total_sources_label.setObjectName("statLabel")
        self.connected_sources_label = QLabel("已连接: 0")
        self.connected_sources_label.setObjectName("statLabel")
        self.disconnected_sources_label = QLabel("未连接: 0")
        self.disconnected_sources_label.setObjectName("statLabel")
        self.sync_status_label = QLabel("同步: 待机")
        self.sync_status_label.setObjectName("statLabel")
        overview_layout.addWidget(self.total_sources_label, 0, 0)
        overview_layout.addWidget(self.connected_sources_label, 0, 1)
        overview_layout.addWidget(self.disconnected_sources_label, 1, 0)
        overview_layout.addWidget(self.sync_status_label, 1, 1)
        layout.addLayout(overview_layout)

        btn_layout = QHBoxLayout()
        self.refresh_sources_btn = QPushButton("刷新")
        self.refresh_sources_btn.setObjectName("btnSmallOutline")
        self.refresh_sources_btn.setMaximumWidth(60)
        self.refresh_sources_btn.clicked.connect(self._refresh_data_sources)
        btn_layout.addWidget(self.refresh_sources_btn)

        self.connect_sources_btn = QPushButton("连接")
        self.connect_sources_btn.setObjectName("btnSmall")
        self.connect_sources_btn.setMaximumWidth(60)
        self.connect_sources_btn.clicked.connect(self._connect_data_sources)
        btn_layout.addWidget(self.connect_sources_btn)

        self.add_source_btn = QPushButton("添加")
        self.add_source_btn.setObjectName("btnSmallOutline")
        self.add_source_btn.setMaximumWidth(60)
        self.add_source_btn.clicked.connect(self._add_data_source)
        btn_layout.addWidget(self.add_source_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        parent_layout.addWidget(group)

    def _create_sync_group(self, parent_layout):
        group = QGroupBox("同步控制")
        group.setObjectName("panelGroup")
        group.setMaximumWidth(360)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        config_layout = QFormLayout()
        config_layout.setSpacing(6)

        self.sync_precision_combo = QComboBox()
        self.sync_precision_combo.addItems(["0.001ms", "0.01ms", "0.1ms", "1ms"])
        self.sync_precision_combo.setCurrentText("0.001ms")
        config_layout.addRow("同步精度:", self.sync_precision_combo)

        self.fusion_algorithm_combo = QComboBox()
        self.fusion_algorithm_combo.addItems(["加权平均", "卡尔曼滤波", "神经网络", "自适应融合"])
        self.fusion_algorithm_combo.setCurrentText("卡尔曼滤波")
        config_layout.addRow("融合算法:", self.fusion_algorithm_combo)

        self.anomaly_threshold_spin = QSpinBox()
        self.anomaly_threshold_spin.setRange(50, 95)
        self.anomaly_threshold_spin.setValue(80)
        self.anomaly_threshold_spin.setSuffix("%")
        config_layout.addRow("异常阈值:", self.anomaly_threshold_spin)

        layout.addLayout(config_layout)

        self.sync_status_display = QLabel("状态: 未启动")
        self.sync_status_display.setObjectName("statValue")
        layout.addWidget(self.sync_status_display)

        metrics_layout = QFormLayout()
        metrics_layout.setSpacing(4)
        self.time_sync_precision_label = QLabel("--")
        self.time_sync_precision_label.setObjectName("formValue")
        self.fusion_quality_label = QLabel("--")
        self.fusion_quality_label.setObjectName("formValue")
        self.anomaly_status_label = QLabel("正常")
        self.anomaly_status_label.setObjectName("formValue")
        metrics_layout.addRow("时间精度:", self.time_sync_precision_label)
        metrics_layout.addRow("融合质量:", self.fusion_quality_label)
        metrics_layout.addRow("异常状态:", self.anomaly_status_label)
        layout.addLayout(metrics_layout)

        btn_layout = QHBoxLayout()
        self.one_click_sync_btn = QPushButton("一键同步")
        self.one_click_sync_btn.setObjectName("btnSmall")
        self.one_click_sync_btn.clicked.connect(self._one_click_sync)
        btn_layout.addWidget(self.one_click_sync_btn)

        self.start_sync_btn = QPushButton("启动")
        self.start_sync_btn.setObjectName("btnSmallOutline")
        self.start_sync_btn.clicked.connect(self._start_sync)
        btn_layout.addWidget(self.start_sync_btn)

        self.pause_sync_btn = QPushButton("暂停")
        self.pause_sync_btn.setObjectName("btnSmallOutline")
        self.pause_sync_btn.setEnabled(False)
        self.pause_sync_btn.clicked.connect(self._pause_sync)
        btn_layout.addWidget(self.pause_sync_btn)

        self.stop_sync_btn = QPushButton("停止")
        self.stop_sync_btn.setObjectName("btnSmallOutline")
        self.stop_sync_btn.setEnabled(False)
        self.stop_sync_btn.clicked.connect(self._stop_sync)
        btn_layout.addWidget(self.stop_sync_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        parent_layout.addWidget(group)

    def _create_parsing_group(self, parent_layout):
        group = QGroupBox("解析控制")
        group.setObjectName("panelGroup")
        group.setMaximumWidth(360)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        parser_layout = QHBoxLayout()
        self.imu_parser_checkbox = QCheckBox("IMU")
        self.imu_parser_checkbox.setChecked(True)
        parser_layout.addWidget(self.imu_parser_checkbox)

        self.cnap_parser_checkbox = QCheckBox("CNAP")
        self.cnap_parser_checkbox.setChecked(True)
        parser_layout.addWidget(self.cnap_parser_checkbox)

        self.cv_parser_checkbox = QCheckBox("心血管")
        self.cv_parser_checkbox.setChecked(False)
        parser_layout.addWidget(self.cv_parser_checkbox)
        layout.addLayout(parser_layout)

        config_layout = QFormLayout()
        config_layout.setSpacing(6)

        self.parsing_mode_combo = QComboBox()
        self.parsing_mode_combo.addItems(["实时模式", "批量模式", "增量模式"])
        config_layout.addRow("解析模式:", self.parsing_mode_combo)

        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(1, 10000)
        self.buffer_size_spin.setValue(1000)
        self.buffer_size_spin.setSuffix(" 条")
        config_layout.addRow("缓冲区:", self.buffer_size_spin)

        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setRange(1, 16)
        self.thread_count_spin.setValue(4)
        config_layout.addRow("线程数:", self.thread_count_spin)

        layout.addLayout(config_layout)

        self.parsing_status_label = QLabel("状态: 未启动")
        self.parsing_status_label.setObjectName("statValue")
        layout.addWidget(self.parsing_status_label)

        self.parsing_progress = QProgressBar()
        self.parsing_progress.setObjectName("miniProgress")
        self.parsing_progress.setValue(0)
        layout.addWidget(self.parsing_progress)

        stats_layout = QFormLayout()
        stats_layout.setSpacing(4)
        self.parsed_count_label = QLabel("0")
        self.parsed_count_label.setObjectName("formValue")
        self.error_count_label = QLabel("0")
        self.error_count_label.setObjectName("formValue")
        self.speed_label = QLabel("0 条/秒")
        self.speed_label.setObjectName("formValue")
        stats_layout.addRow("已解析:", self.parsed_count_label)
        stats_layout.addRow("错误数:", self.error_count_label)
        stats_layout.addRow("速度:", self.speed_label)
        layout.addLayout(stats_layout)

        btn_layout = QHBoxLayout()
        self.start_parsing_btn = QPushButton("启动")
        self.start_parsing_btn.setObjectName("btnSmallOutline")
        self.start_parsing_btn.clicked.connect(self._start_parsing)
        btn_layout.addWidget(self.start_parsing_btn)

        self.pause_parsing_btn = QPushButton("暂停")
        self.pause_parsing_btn.setObjectName("btnSmallOutline")
        self.pause_parsing_btn.setEnabled(False)
        self.pause_parsing_btn.clicked.connect(self._pause_parsing)
        btn_layout.addWidget(self.pause_parsing_btn)

        self.stop_parsing_btn = QPushButton("停止")
        self.stop_parsing_btn.setObjectName("btnSmallOutline")
        self.stop_parsing_btn.setEnabled(False)
        self.stop_parsing_btn.clicked.connect(self._stop_parsing)
        btn_layout.addWidget(self.stop_parsing_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.parsing_log = QTextEdit()
        self.parsing_log.setMaximumHeight(80)
        self.parsing_log.setReadOnly(True)
        layout.addWidget(self.parsing_log)

        log_btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setObjectName("btnGhost")
        self.clear_log_btn.clicked.connect(lambda: self.parsing_log.clear())
        log_btn_layout.addWidget(self.clear_log_btn)
        log_btn_layout.addStretch()
        layout.addLayout(log_btn_layout)

        parent_layout.addWidget(group)

    def _create_analysis_group(self, parent_layout):
        group = QGroupBox("分析控制")
        group.setObjectName("panelGroup")
        group.setMaximumWidth(360)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        basic_group = QGroupBox("基础分析")
        basic_group.setObjectName("compactGroup")
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setSpacing(4)

        self.basic_analysis_status_label = QLabel("状态: 未启动")
        self.basic_analysis_status_label.setObjectName("statValue")
        basic_layout.addWidget(self.basic_analysis_status_label)

        basic_btn_layout = QHBoxLayout()
        self.start_basic_analysis_btn = QPushButton("启动")
        self.start_basic_analysis_btn.setObjectName("btnSmallOutline")
        self.start_basic_analysis_btn.clicked.connect(self._start_basic_analysis)
        basic_btn_layout.addWidget(self.start_basic_analysis_btn)

        self.pause_basic_analysis_btn = QPushButton("暂停")
        self.pause_basic_analysis_btn.setObjectName("btnSmallOutline")
        self.pause_basic_analysis_btn.setEnabled(False)
        self.pause_basic_analysis_btn.clicked.connect(self._pause_basic_analysis)
        basic_btn_layout.addWidget(self.pause_basic_analysis_btn)

        self.stop_basic_analysis_btn = QPushButton("停止")
        self.stop_basic_analysis_btn.setObjectName("btnSmallOutline")
        self.stop_basic_analysis_btn.setEnabled(False)
        self.stop_basic_analysis_btn.clicked.connect(self._stop_basic_analysis)
        basic_btn_layout.addWidget(self.stop_basic_analysis_btn)

        basic_btn_layout.addStretch()
        basic_layout.addLayout(basic_btn_layout)

        basic_stats = QFormLayout()
        basic_stats.setSpacing(4)
        self.analysis_count_label = QLabel("0")
        self.analysis_count_label.setObjectName("formValue")
        self.last_analysis_time_label = QLabel("--")
        self.last_analysis_time_label.setObjectName("formValue")
        basic_stats.addRow("分析次数:", self.analysis_count_label)
        basic_stats.addRow("上次分析:", self.last_analysis_time_label)
        basic_layout.addLayout(basic_stats)

        layout.addWidget(basic_group)

        advanced_group = QGroupBox("高级分析")
        advanced_group.setObjectName("compactGroup")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(4)

        self.advanced_analysis_status_label = QLabel("状态: 未启动")
        self.advanced_analysis_status_label.setObjectName("statValue")
        advanced_layout.addWidget(self.advanced_analysis_status_label)

        adv_btn_layout = QHBoxLayout()
        self.start_advanced_analysis_btn = QPushButton("启动")
        self.start_advanced_analysis_btn.setObjectName("btnSmallOutline")
        self.start_advanced_analysis_btn.clicked.connect(self._start_advanced_analysis)
        adv_btn_layout.addWidget(self.start_advanced_analysis_btn)

        self.pause_advanced_analysis_btn = QPushButton("暂停")
        self.pause_advanced_analysis_btn.setObjectName("btnSmallOutline")
        self.pause_advanced_analysis_btn.setEnabled(False)
        self.pause_advanced_analysis_btn.clicked.connect(self._pause_advanced_analysis)
        adv_btn_layout.addWidget(self.pause_advanced_analysis_btn)

        self.stop_advanced_analysis_btn = QPushButton("停止")
        self.stop_advanced_analysis_btn.setObjectName("btnSmallOutline")
        self.stop_advanced_analysis_btn.setEnabled(False)
        self.stop_advanced_analysis_btn.clicked.connect(self._stop_advanced_analysis)
        adv_btn_layout.addWidget(self.stop_advanced_analysis_btn)

        adv_btn_layout.addStretch()
        advanced_layout.addLayout(adv_btn_layout)

        model_layout = QHBoxLayout()
        self.load_model_btn = QPushButton("加载模型")
        self.load_model_btn.setObjectName("btnSmallOutline")
        self.load_model_btn.clicked.connect(self._load_model)
        model_layout.addWidget(self.load_model_btn)

        self.unload_model_btn = QPushButton("卸载模型")
        self.unload_model_btn.setObjectName("btnSmallOutline")
        self.unload_model_btn.setEnabled(False)
        self.unload_model_btn.clicked.connect(self._unload_model)
        model_layout.addWidget(self.unload_model_btn)
        model_layout.addStretch()
        advanced_layout.addLayout(model_layout)

        training_layout = QHBoxLayout()
        self.start_training_btn = QPushButton("开始训练")
        self.start_training_btn.setObjectName("btnSmallOutline")
        self.start_training_btn.clicked.connect(self._start_training)
        training_layout.addWidget(self.start_training_btn)

        self.stop_training_btn = QPushButton("停止训练")
        self.stop_training_btn.setObjectName("btnSmallOutline")
        self.stop_training_btn.setEnabled(False)
        self.stop_training_btn.clicked.connect(self._stop_training)
        training_layout.addWidget(self.stop_training_btn)
        training_layout.addStretch()
        advanced_layout.addLayout(training_layout)

        model_info = QFormLayout()
        model_info.setSpacing(4)
        self.model_status_label = QLabel("未加载")
        self.model_status_label.setObjectName("formValue")
        self.model_accuracy_label = QLabel("0%")
        self.model_accuracy_label.setObjectName("formValue")
        self.model_algorithm_label = QLabel("--")
        self.model_algorithm_label.setObjectName("formValue")
        model_info.addRow("模型状态:", self.model_status_label)
        model_info.addRow("准确率:", self.model_accuracy_label)
        model_info.addRow("算法:", self.model_algorithm_label)
        advanced_layout.addLayout(model_info)

        layout.addWidget(advanced_group)
        parent_layout.addWidget(group)

    def _create_system_group(self, parent_layout):
        group = QGroupBox("系统控制")
        group.setObjectName("panelGroup")
        group.setMaximumWidth(360)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        config_layout = QFormLayout()
        config_layout.setSpacing(6)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色主题", "浅色主题"])
        config_layout.addRow("主题:", self.theme_combo)

        self.auto_save_check = QCheckBox("自动保存配置")
        self.auto_save_check.setChecked(True)
        config_layout.addRow("", self.auto_save_check)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        config_layout.addRow("日志级别:", self.log_level_combo)

        self.auto_optimization_spin = QSpinBox()
        self.auto_optimization_spin.setRange(1, 60)
        self.auto_optimization_spin.setValue(10)
        self.auto_optimization_spin.setSuffix(" 分钟")
        config_layout.addRow("自动优化:", self.auto_optimization_spin)

        layout.addLayout(config_layout)

        status_layout = QFormLayout()
        status_layout.setSpacing(4)
        self.system_status_label = QLabel("运行中")
        self.system_status_label.setObjectName("formValue")
        self.memory_usage_label = QLabel("0 MB")
        self.memory_usage_label.setObjectName("formValue")
        self.cpu_usage_label = QLabel("0%")
        self.cpu_usage_label.setObjectName("formValue")
        self.disk_space_label = QLabel("0 GB")
        self.disk_space_label.setObjectName("formValue")
        status_layout.addRow("系统状态:", self.system_status_label)
        status_layout.addRow("内存使用:", self.memory_usage_label)
        status_layout.addRow("CPU使用:", self.cpu_usage_label)
        status_layout.addRow("磁盘空间:", self.disk_space_label)
        layout.addLayout(status_layout)

        op_layout = QHBoxLayout()
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setObjectName("btnSmallOutline")
        self.save_config_btn.clicked.connect(self._save_config)
        op_layout.addWidget(self.save_config_btn)

        self.load_config_btn = QPushButton("加载配置")
        self.load_config_btn.setObjectName("btnSmallOutline")
        self.load_config_btn.clicked.connect(self._load_config)
        op_layout.addWidget(self.load_config_btn)

        self.export_data_btn = QPushButton("导出数据")
        self.export_data_btn.setObjectName("btnSmall")
        self.export_data_btn.clicked.connect(self._export_data)
        op_layout.addWidget(self.export_data_btn)
        layout.addLayout(op_layout)

        adv_op_layout = QHBoxLayout()
        self.system_optimization_btn = QPushButton("系统优化")
        self.system_optimization_btn.setObjectName("btnSmallOutline")
        self.system_optimization_btn.clicked.connect(self._system_optimization)
        adv_op_layout.addWidget(self.system_optimization_btn)

        self.clear_cache_btn = QPushButton("清理缓存")
        self.clear_cache_btn.setObjectName("btnSmallOutline")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        adv_op_layout.addWidget(self.clear_cache_btn)

        self.restart_system_btn = QPushButton("重启系统")
        self.restart_system_btn.setObjectName("btnDanger")
        self.restart_system_btn.clicked.connect(self._restart_system)
        adv_op_layout.addWidget(self.restart_system_btn)
        layout.addLayout(adv_op_layout)

        parent_layout.addWidget(group)

    def _connect_all_signals(self):
        self.sync_precision_combo.currentTextChanged.connect(self._sync_config_changed)
        self.fusion_algorithm_combo.currentTextChanged.connect(self._sync_config_changed)
        self.anomaly_threshold_spin.valueChanged.connect(self._sync_config_changed)

        self.parsing_mode_combo.currentTextChanged.connect(self._parsing_config_changed)
        self.buffer_size_spin.valueChanged.connect(self._parsing_config_changed)
        self.thread_count_spin.valueChanged.connect(self._parsing_config_changed)

        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        self.log_level_combo.currentTextChanged.connect(self._log_level_changed)
        self.auto_save_check.stateChanged.connect(self._auto_save_changed)
        self.auto_optimization_spin.valueChanged.connect(self._auto_optimization_changed)

    def _start_monitors(self):
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_system_metrics)
        self.status_timer.start(5000)

        self.sync_monitor_timer = QTimer()
        self.sync_monitor_timer.timeout.connect(self._update_sync_metrics)
        self.sync_monitor_timer.start(3000)

    def _refresh_data_sources(self):
        self.logger.info("刷新数据源")
        self.action_triggered.emit("REFRESH_DATA_SOURCES", {})

    def _connect_data_sources(self):
        self.logger.info("连接数据源")
        self.action_triggered.emit("CONNECT_DATA_SOURCES", {})

    def _add_data_source(self):
        self.logger.info("添加数据源")
        self.action_triggered.emit("ADD_DATA_SOURCE", {})

    def _one_click_sync(self):
        self.logger.info("一键同步")
        self.action_triggered.emit("ONE_CLICK_SYNC", {
            "precision": self.sync_precision_combo.currentText(),
            "algorithm": self.fusion_algorithm_combo.currentText(),
            "threshold": self.anomaly_threshold_spin.value()
        })

    def _start_sync(self):
        self.sync_running = True
        self.sync_paused = False
        self.sync_status_display.setText("状态: 运行中")
        self.start_sync_btn.setEnabled(False)
        self.pause_sync_btn.setEnabled(True)
        self.stop_sync_btn.setEnabled(True)
        self.action_triggered.emit("START_SYNC", {
            "precision": self.sync_precision_combo.currentText(),
            "algorithm": self.fusion_algorithm_combo.currentText(),
            "threshold": self.anomaly_threshold_spin.value()
        })

    def _pause_sync(self):
        self.sync_paused = not self.sync_paused
        if self.sync_paused:
            self.sync_status_display.setText("状态: 已暂停")
            self.pause_sync_btn.setText("继续")
            self.action_triggered.emit("PAUSE_SYNC", {})
        else:
            self.sync_status_display.setText("状态: 运行中")
            self.pause_sync_btn.setText("暂停")
            self.action_triggered.emit("RESUME_SYNC", {})

    def _stop_sync(self):
        self.sync_running = False
        self.sync_paused = False
        self.sync_status_display.setText("状态: 已停止")
        self.start_sync_btn.setEnabled(True)
        self.pause_sync_btn.setEnabled(False)
        self.pause_sync_btn.setText("暂停")
        self.stop_sync_btn.setEnabled(False)
        self.action_triggered.emit("STOP_SYNC", {})

    def _sync_config_changed(self):
        config = {
            "precision": self.sync_precision_combo.currentText(),
            "algorithm": self.fusion_algorithm_combo.currentText(),
            "threshold": self.anomaly_threshold_spin.value()
        }
        self.action_triggered.emit("SYNC_CONFIG_CHANGED", config)

    def _start_parsing(self):
        self.parsing_running = True
        self.parsing_paused = False
        self.parsing_status_label.setText("状态: 解析中")
        self.start_parsing_btn.setEnabled(False)
        self.pause_parsing_btn.setEnabled(True)
        self.stop_parsing_btn.setEnabled(True)
        self.action_triggered.emit("START_PARSING", {
            "mode": self.parsing_mode_combo.currentText(),
            "buffer_size": self.buffer_size_spin.value(),
            "thread_count": self.thread_count_spin.value(),
            "parsers": {
                "imu": self.imu_parser_checkbox.isChecked(),
                "cnap": self.cnap_parser_checkbox.isChecked(),
                "cardiovascular": self.cv_parser_checkbox.isChecked()
            }
        })

    def _pause_parsing(self):
        self.parsing_paused = not self.parsing_paused
        if self.parsing_paused:
            self.parsing_status_label.setText("状态: 已暂停")
            self.pause_parsing_btn.setText("继续")
            self.action_triggered.emit("PAUSE_PARSING", {})
        else:
            self.parsing_status_label.setText("状态: 解析中")
            self.pause_parsing_btn.setText("暂停")
            self.action_triggered.emit("RESUME_PARSING", {})

    def _stop_parsing(self):
        self.parsing_running = False
        self.parsing_paused = False
        self.parsing_status_label.setText("状态: 已停止")
        self.start_parsing_btn.setEnabled(True)
        self.pause_parsing_btn.setEnabled(False)
        self.pause_parsing_btn.setText("暂停")
        self.stop_parsing_btn.setEnabled(False)
        self.action_triggered.emit("STOP_PARSING", {})

    def _parsing_config_changed(self):
        config = {
            "mode": self.parsing_mode_combo.currentText(),
            "buffer_size": self.buffer_size_spin.value(),
            "thread_count": self.thread_count_spin.value()
        }
        self.action_triggered.emit("PARSING_CONFIG_CHANGED", config)

    def _start_basic_analysis(self):
        self.basic_analysis_running = True
        self.basic_analysis_status_label.setText("状态: 分析中")
        self.start_basic_analysis_btn.setEnabled(False)
        self.pause_basic_analysis_btn.setEnabled(True)
        self.stop_basic_analysis_btn.setEnabled(True)
        self.action_triggered.emit("START_BASIC_ANALYSIS", {})

    def _pause_basic_analysis(self):
        self.basic_analysis_running = False
        self.basic_analysis_status_label.setText("状态: 已暂停")
        self.start_basic_analysis_btn.setEnabled(True)
        self.pause_basic_analysis_btn.setEnabled(False)
        self.stop_basic_analysis_btn.setEnabled(True)
        self.action_triggered.emit("PAUSE_BASIC_ANALYSIS", {})

    def _stop_basic_analysis(self):
        self.basic_analysis_running = False
        self.basic_analysis_status_label.setText("状态: 已停止")
        self.start_basic_analysis_btn.setEnabled(True)
        self.pause_basic_analysis_btn.setEnabled(False)
        self.stop_basic_analysis_btn.setEnabled(False)
        self.action_triggered.emit("STOP_BASIC_ANALYSIS", {})

    def _start_advanced_analysis(self):
        self.advanced_analysis_running = True
        self.advanced_analysis_status_label.setText("状态: 分析中")
        self.start_advanced_analysis_btn.setEnabled(False)
        self.pause_advanced_analysis_btn.setEnabled(True)
        self.stop_advanced_analysis_btn.setEnabled(True)
        self.action_triggered.emit("START_ADVANCED_ANALYSIS", {})

    def _pause_advanced_analysis(self):
        self.advanced_analysis_running = False
        self.advanced_analysis_status_label.setText("状态: 已暂停")
        self.start_advanced_analysis_btn.setEnabled(True)
        self.pause_advanced_analysis_btn.setEnabled(False)
        self.stop_advanced_analysis_btn.setEnabled(True)
        self.action_triggered.emit("PAUSE_ADVANCED_ANALYSIS", {})

    def _stop_advanced_analysis(self):
        self.advanced_analysis_running = False
        self.advanced_analysis_status_label.setText("状态: 已停止")
        self.start_advanced_analysis_btn.setEnabled(True)
        self.pause_advanced_analysis_btn.setEnabled(False)
        self.stop_advanced_analysis_btn.setEnabled(False)
        self.action_triggered.emit("STOP_ADVANCED_ANALYSIS", {})

    def _load_model(self):
        self.load_model_btn.setEnabled(False)
        self.unload_model_btn.setEnabled(True)
        self.model_status_label.setText("已加载")
        self.action_triggered.emit("LOAD_MODEL", {})

    def _unload_model(self):
        self.load_model_btn.setEnabled(True)
        self.unload_model_btn.setEnabled(False)
        self.model_status_label.setText("未加载")
        self.action_triggered.emit("UNLOAD_MODEL", {})

    def _start_training(self):
        self.training_running = True
        self.start_training_btn.setEnabled(False)
        self.stop_training_btn.setEnabled(True)
        self.action_triggered.emit("START_TRAINING", {})

    def _stop_training(self):
        self.training_running = False
        self.start_training_btn.setEnabled(True)
        self.stop_training_btn.setEnabled(False)
        self.action_triggered.emit("STOP_TRAINING", {})

    def _theme_changed(self, theme):
        theme_map = {"深色主题": "dark", "浅色主题": "light"}
        self.action_triggered.emit("THEME_CHANGED", {"theme": theme_map.get(theme, "dark")})

    def _log_level_changed(self, level):
        self.action_triggered.emit("LOG_LEVEL_CHANGED", {"level": level})

    def _auto_save_changed(self, state):
        self.action_triggered.emit("AUTO_SAVE_CHANGED", {"enabled": state == Qt.Checked.value})

    def _auto_optimization_changed(self, value):
        self.action_triggered.emit("AUTO_OPTIMIZATION_CHANGED", {"interval": value})

    def _save_config(self):
        self.action_triggered.emit("SAVE_CONFIG", {})

    def _load_config(self):
        self.action_triggered.emit("LOAD_CONFIG", {})

    def _export_data(self):
        self.action_triggered.emit("EXPORT_DATA", {})

    def _system_optimization(self):
        self.action_triggered.emit("SYSTEM_OPTIMIZATION", {})

    def _clear_cache(self):
        self.action_triggered.emit("CLEAR_CACHE", {})

    def _restart_system(self):
        reply = QMessageBox.question(
            self, "确认重启", "确定要重启系统吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.action_triggered.emit("RESTART_SYSTEM", {})

    def _update_system_metrics(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/')
            self.memory_usage_label.setText(f"{mem.used / (1024**2):.0f} MB")
            self.cpu_usage_label.setText(f"{cpu:.1f}%")
            self.disk_space_label.setText(f"{disk.free / (1024**3):.1f} GB")
        except ImportError:
            pass

    def _update_sync_metrics(self):
        if self.sync_running:
            self.time_sync_precision_label.setText("-- ms")
            self.fusion_quality_label.setText("--%")

    def update_module_status(self, module_id, status):
        if module_id in self.sub_modules:
            self.logger.info(f"模块 {module_id} 状态更新: {status}")
            self.module_status_changed.emit(module_id, status)

    def register_module(self, module_name, module_instance):
        try:
            self.sub_modules[module_name] = module_instance
            self.logger.info(f"注册子模块: {module_name}")
            return True
        except Exception as e:
            self.logger.error(f"注册子模块 {module_name} 失败: {e}")
            return False

    def update_data_source_info(self, total=0, connected=0, disconnected=0):
        self.total_sources_label.setText(f"总数: {total}")
        self.connected_sources_label.setText(f"已连接: {connected}")
        self.disconnected_sources_label.setText(f"未连接: {disconnected}")

    def update_parsing_stats(self, parsed=0, errors=0, speed=0):
        self.parsed_count_label.setText(str(parsed))
        self.error_count_label.setText(str(errors))
        self.speed_label.setText(f"{speed} 条/秒")

    def append_parsing_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.parsing_log.append(f"[{timestamp}] {message}")

    def update_analysis_stats(self, count=0, last_time=None):
        self.analysis_count_label.setText(str(count))
        if last_time:
            self.last_analysis_time_label.setText(last_time)

    def update_model_info(self, status="", accuracy="", algorithm=""):
        if status:
            self.model_status_label.setText(status)
        if accuracy:
            self.model_accuracy_label.setText(accuracy)
        if algorithm:
            self.model_algorithm_label.setText(algorithm)
