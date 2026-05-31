#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统状态标签页 - 左侧控制面板版本
风格与数据融合/数据源标签页保持一致
"""

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QGridLayout, QScrollArea, QFrame,
    QSpinBox, QDoubleSpinBox, QCheckBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class SystemStatusTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = datetime.now()
        self._setup_ui()
        self._apply_style()
        logger.info("系统状态标签页已初始化")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(8)

        self._create_overview_card(content_layout)
        self._create_performance_card(content_layout)
        self._create_monitoring_config_card(content_layout)
        self._create_anomaly_detection_card(content_layout)
        self._create_resource_threshold_card(content_layout)
        self._create_operation_card(content_layout)
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_overview_card(self, parent_layout):
        group = QGroupBox("系统概览")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)

        items = [
            ("系统版本", "v2.0.0"),
            ("运行时间", "0天 0小时 0分钟"),
            ("最后启动", "未知"),
            ("系统状态", "正常"),
            ("用户数量", "0"),
            ("数据总量", "0 MB"),
        ]

        self._overview_labels = {}
        for i, (label_text, value_text) in enumerate(items):
            row = i // 2
            col = i % 2 * 2

            lbl = QLabel(f"{label_text}:")
            lbl.setFont(QFont("Microsoft YaHei", 9))
            grid.addWidget(lbl, row, col)

            val = QLabel(value_text)
            val.setStyleSheet("font-weight: bold; color: #2E7D32;")
            grid.addWidget(val, row, col + 1)
            self._overview_labels[label_text] = val

        parent_layout.addWidget(group)

    def _create_performance_card(self, parent_layout):
        group = QGroupBox("性能指标")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)

        metrics = [
            ("响应时间", "0 ms"),
            ("吞吐量", "0 req/s"),
            ("错误率", "0%"),
            ("资源使用率", "0%"),
        ]

        self._perf_labels = {}
        for i, (name, default_value) in enumerate(metrics):
            row = i // 2
            col = i % 2 * 2

            lbl = QLabel(f"{name}:")
            lbl.setFont(QFont("Microsoft YaHei", 9))
            grid.addWidget(lbl, row, col)

            val = QLabel(default_value)
            val.setStyleSheet("font-family: Consolas; font-size: 10pt; color: #1976D2;")
            grid.addWidget(val, row, col + 1)
            self._perf_labels[name] = val

        parent_layout.addWidget(group)

    def _create_monitoring_config_card(self, parent_layout):
        group = QGroupBox("监控配置")
        form = QFormLayout(group)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(6)

        self.monitor_interval_spin = QDoubleSpinBox()
        self.monitor_interval_spin.setRange(0.1, 60.0)
        self.monitor_interval_spin.setValue(1.0)
        self.monitor_interval_spin.setSuffix(" 秒")
        form.addRow("监控间隔:", self.monitor_interval_spin)

        self.performance_threshold_spin = QDoubleSpinBox()
        self.performance_threshold_spin.setRange(0.1, 1.0)
        self.performance_threshold_spin.setValue(0.8)
        self.performance_threshold_spin.setDecimals(2)
        form.addRow("性能阈值:", self.performance_threshold_spin)

        self.auto_optimize_check = QCheckBox("启用自动性能优化")
        self.auto_optimize_check.setChecked(True)
        form.addRow("", self.auto_optimize_check)

        parent_layout.addWidget(group)

    def _create_anomaly_detection_card(self, parent_layout):
        group = QGroupBox("异常检测")
        form = QFormLayout(group)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(6)

        self.anomaly_detection_check = QCheckBox("启用异常自动检测")
        self.anomaly_detection_check.setChecked(True)
        form.addRow("", self.anomaly_detection_check)

        self.anomaly_threshold_spin = QSpinBox()
        self.anomaly_threshold_spin.setRange(50, 95)
        self.anomaly_threshold_spin.setValue(80)
        self.anomaly_threshold_spin.setSuffix("%")
        form.addRow("异常阈值:", self.anomaly_threshold_spin)

        parent_layout.addWidget(group)

    def _create_resource_threshold_card(self, parent_layout):
        group = QGroupBox("资源阈值")
        form = QFormLayout(group)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(6)

        self.cpu_threshold_spin = QSpinBox()
        self.cpu_threshold_spin.setRange(50, 100)
        self.cpu_threshold_spin.setValue(80)
        self.cpu_threshold_spin.setSuffix("%")
        form.addRow("CPU 阈值:", self.cpu_threshold_spin)

        self.memory_threshold_spin = QSpinBox()
        self.memory_threshold_spin.setRange(50, 100)
        self.memory_threshold_spin.setValue(85)
        self.memory_threshold_spin.setSuffix("%")
        form.addRow("内存阈值:", self.memory_threshold_spin)

        self.sync_rate_threshold_spin = QSpinBox()
        self.sync_rate_threshold_spin.setRange(10, 500)
        self.sync_rate_threshold_spin.setValue(100)
        self.sync_rate_threshold_spin.setSuffix(" Hz")
        form.addRow("同步速率阈值:", self.sync_rate_threshold_spin)

        parent_layout.addWidget(group)

    def _create_operation_card(self, parent_layout):
        group = QGroupBox("系统操作")
        op_layout = QHBoxLayout(group)
        op_layout.setContentsMargins(8, 6, 8, 6)
        op_layout.setSpacing(8)

        self.restart_btn = QPushButton("重启系统")
        self.restart_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )
        self.restart_btn.clicked.connect(self._on_restart)
        op_layout.addWidget(self.restart_btn)

        self.backup_btn = QPushButton("备份数据")
        self.backup_btn.clicked.connect(self._on_backup)
        op_layout.addWidget(self.backup_btn)

        self.export_log_btn = QPushButton("导出日志")
        self.export_log_btn.clicked.connect(self._on_export_logs)
        op_layout.addWidget(self.export_log_btn)

        op_layout.addStretch()
        parent_layout.addWidget(group)

    def _apply_style(self):
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
                font-weight: bold;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 9pt;
                min-height: 24px;
                font-family: "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
            QLabel {
                color: #333333;
                font-family: "Microsoft YaHei";
                font-size: 9pt;
            }
        """)

    def update_overview(self, **kwargs):
        for key, value in kwargs.items():
            if key in self._overview_labels:
                self._overview_labels[key].setText(str(value))

    def update_performance(self, **kwargs):
        for key, value in kwargs.items():
            if key in self._perf_labels:
                self._perf_labels[key].setText(str(value))

    def update_uptime(self):
        delta = datetime.now() - self._start_time
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, _ = divmod(rem, 60)
        text = f"{days}天 {hours}小时 {minutes}分钟"
        if "运行时间" in self._overview_labels:
            self._overview_labels["运行时间"].setText(text)

    def _on_restart(self):
        logger.info("系统重启请求")

    def _on_backup(self):
        logger.info("数据备份请求")

    def _on_export_logs(self):
        logger.info("导出日志请求")
