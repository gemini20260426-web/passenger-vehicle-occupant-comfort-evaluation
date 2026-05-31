#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 优化日期: 2026-05-03
# 优化内容: 修复 memory.percent 引用错误, 初始化 current_data, 统一 logger
# ============================================================
"""

UI
"""

import logging
import json
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import functools # 

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QCheckBox, QTextEdit, QTabWidget, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QProgressBar, QSlider, QFrame, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QDialog, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap


class MockSyncEngine(QObject):
    sync_status_updated = Signal(dict)
    sync_error = Signal(str, str)
    data_processed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.data_sources = {}
        self.status = "STOPPED"

    def add_data_source(self, source_id, config):
        self.data_sources[source_id] = config
        return True

    def remove_data_source(self, source_id):
        if source_id in self.data_sources:
            del self.data_sources[source_id]
            return True
        return False

    def connect_data_source(self, source_id, config):
        self.data_sources[source_id] = config
        return True

    def disconnect_data_source(self, source_id):
        return True

    def start_sync(self, sources=None):
        self.status = "RUNNING"
        return True

    def stop_sync(self):
        self.status = "STOPPED"
        return True

    def start_data_processing(self, source_id):
        return True

    def get_data_rate(self, source_id):
        return 0.0

    def get_sync_status(self):
        return {"status": self.status, "sources": len(self.data_sources)}


class MockSyncManager:
    def __init__(self):
        pass

# 
try:
    from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine
    from core.core.data_processing.multi_source_sync_manager import MultiSourceDataSyncManager
    from core.core.unified_data_flow_manager import UnifiedDataFlowManager
    CORE_ENGINE_AVAILABLE = True
    print(" ")
except ImportError as e:
    print(f" : {e}")
    logging.error(f": {e}")
    CORE_ENGINE_AVAILABLE = False

#  ( parent)
try:
    from ..data_source_control import DataSourceControlPanel
except ImportError:
    try:
        from modules.ui.left_control_panel.data_source_control import DataSourceControlPanel
    except ImportError:
        DataSourceControlPanel = None
from config.config_manager import ConfigManager # ConfigManager

class MultiSourceSyncConfigTab(QWidget):
    """ - """
    
    # 
    config_changed = Signal(dict)  # 
    sync_status_updated = Signal(dict)  # 
    data_source_updated = Signal(str, dict)  # 
    fusion_algorithm_changed = Signal(str)  # 
    data_sources_updated = Signal(dict)  # 
    
    def __init__(self, parent=None, external_sync_engine=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.logger.info("MultiSourceSyncConfigTab __init__ ") # 
        self.config_manager = ConfigManager() # 
        self.external_sync_engine = external_sync_engine
        if CORE_ENGINE_AVAILABLE:
            self.data_flow_manager = UnifiedDataFlowManager()
        else:
            self.data_flow_manager = None 
        
        # 
        self.current_config = {}
        self.data_sources = {}
        self.sync_status = {}
        self.current_data = {}
        
        # 
        if external_sync_engine:
            self.sync_engine = external_sync_engine
            self.logger.info(" ")
            # 
            self._use_external_engine = True
        else:
            self._use_external_engine = False
            # 
            self._init_core_engines()
        
        # UI
        self.quick_status_label = QLabel(" : ")
        
        self.init_ui()
        
        # 
        self.connect_left_sync()
        
        # 
        if hasattr(self, '_use_external_engine') and self._use_external_engine:
            self.logger.info(" ...")
            self.logger.info(f" : {self._use_external_engine}")
            self.logger.info(f" : {type(self.sync_engine).__name__ if self.sync_engine else 'None'}")
            self._ensure_sample_data_sources()
        else:
            self.logger.info(f" : _use_external_engine={getattr(self, '_use_external_engine', 'not_set')}")
        
        # 
        self.connect_signals()
        
        # 
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_sync_status)
        # 未同步数据时无需轮询，按需启动

        # 
        self.performance_timer = QTimer()
        self.performance_timer.timeout.connect(self.update_performance_metrics)
        # 未同步数据时无需轮询，按需启动

        # 
        self.resource_timer = QTimer()
        self.resource_timer.timeout.connect(self.update_resource_usage)
        # 未同步数据时无需轮询，按需启动
        
        self.logger.info(" ")
        
        # 
        self.logger.info(" ...")
        self._refresh_data_sources_display()
        
        #  ()
        # self.unified_manager = UnifiedDataSourceManager(self)
        # self.unified_manager.data_source_updated.connect(self._update_tab_from_unified)
    
    def _init_core_engines(self):
        """"""
        try:
            # 
            if hasattr(self, '_use_external_engine') and self._use_external_engine:
                self.logger.info(" ")
                return
                
            if CORE_ENGINE_AVAILABLE:
                # 
                real_data_config = self._load_real_data_config()
                
                # 
                self.sync_engine = MultiSourceSyncEngine(real_data_config)
                self.logger.info(" ")
                
                # 
                self.sync_manager = MultiSourceDataSyncManager()
                self.logger.info(" ")
                
                # 
                # self.data_source_manager = UnifiedDataSourceManager()
                self.logger.info(" ")
                
                # 
                self._connect_engine_signals()
                
                # 
                self._create_sample_data_sources()
                
            else:
                self.logger.warning(" ")
                self.sync_engine = MockSyncEngine()
                self.sync_manager = MockSyncManager()
                # self.data_source_manager = MockDataSourceManager()
                self.logger.info(" ")
                # 
                self._create_sample_data_sources()
        except Exception as e:
            self.logger.error(f": {e}")
            # 
    
    def _load_real_data_config(self):
        """"""
        try:
            config_path = "config/real_data_mode.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(" ")
                return config
            else:
                # 
                default_config = {
                    "system_mode": "real_data_only",
                    "disable_simulation": True,
                    "force_real_data": True
                }
                self.logger.info(" ")
                return default_config
        except Exception as e:
            self.logger.error(f" : {e}")
            # 
            return {"system_mode": "real_data_only", "disable_simulation": True}
    
    def _connect_engine_signals(self):
        """"""
        try:
            if self.sync_engine:
                # 
                if hasattr(self.sync_engine, 'sync_status_updated'):
                    self.sync_engine.sync_status_updated.connect(self._on_sync_status_updated)
                if hasattr(self.sync_engine, 'sync_error'):
                    self.sync_engine.sync_error.connect(self._on_sync_error)
                if hasattr(self.sync_engine, 'data_processed'):
                    self.sync_engine.data_processed.connect(self._on_data_processed)
                    
                self.logger.info(" ")
        except Exception as e:
            self.logger.error(f" : {e}")
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        self._create_dashboard_header(main_layout)

        separator = QFrame()
        separator.setObjectName("separatorH")
        separator.setFrameShape(QFrame.HLine)
        main_layout.addWidget(separator)

        config_widget = self._create_config_widget()
        main_layout.addWidget(config_widget, 1)

        self._create_quick_bar(main_layout)

    def _create_dashboard_header(self, parent_layout):
        dashboard = QWidget()
        dashboard_layout = QHBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(12)

        cards_data = [
            ("sync_rate", "同步速率", "0 Hz", "metricValueAccent", "实时同步频率"),
            ("sync_quality", "同步质量", "0%", "metricValueSuccess", "数据融合质量"),
            ("active_sources", "活跃数据源", "0/0", "metricValue", "已连接/总数据源"),
            ("sync_latency", "同步延迟", "0 ms", "metricValueWarning", "端到端延迟"),
            ("anomaly_status", "异常状态", "正常", "metricValueSuccess", "实时检测状态"),
        ]

        for obj_name, title, value, value_style, sub_text in cards_data:
            card = QFrame()
            card.setObjectName("dashboardCard")
            card.setMinimumSize(150, 90)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(4)

            title_label = QLabel(title)
            title_label.setObjectName("metricTitle")
            card_layout.addWidget(title_label)

            value_label = QLabel(value)
            value_label.setObjectName(value_style)
            setattr(self, f"{obj_name}_card_label", value_label)
            card_layout.addWidget(value_label)

            sub_label = QLabel(sub_text)
            sub_label.setObjectName("metricSub")
            card_layout.addWidget(sub_label)

            dashboard_layout.addWidget(card)

        dashboard_layout.addStretch()
        parent_layout.addWidget(dashboard)

    def _create_quick_bar(self, parent_layout):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 4, 0, 0)
        bar_layout.setSpacing(8)

        self.quick_status_label = QLabel("状态: 待机")
        self.quick_status_label.setObjectName("statusBadgeMuted")
        bar_layout.addWidget(self.quick_status_label)

        bar_layout.addStretch()

        start_btn = QPushButton("启动同步")
        start_btn.setObjectName("btnSuccess")
        start_btn.clicked.connect(self.start_synchronization)
        bar_layout.addWidget(start_btn)

        stop_btn = QPushButton("停止同步")
        stop_btn.setObjectName("btnDanger")
        stop_btn.clicked.connect(self.stop_synchronization)
        bar_layout.addWidget(stop_btn)

        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("btnOutline")
        test_btn.clicked.connect(self.test_connections)
        bar_layout.addWidget(test_btn)

        parent_layout.addWidget(bar)
    # 
    
    def _create_sync_engine_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(12)

        basic_group = QGroupBox("基础配置")
        basic_group.setObjectName("panelGroup")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(8)

        self.sync_frequency_spin = QDoubleSpinBox()
        self.sync_frequency_spin.setRange(0.001, 1000.0)
        self.sync_frequency_spin.setValue(100.0)
        self.sync_frequency_spin.setSuffix(" Hz")
        self.sync_frequency_spin.setDecimals(3)
        basic_layout.addRow("同步频率:", self.sync_frequency_spin)

        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 100)
        self.max_concurrent_spin.setValue(10)
        basic_layout.addRow("最大并发:", self.max_concurrent_spin)

        self.sync_strategy_combo = QComboBox()
        self.sync_strategy_combo.addItems(["时间优先", "质量优先", "混合策略", "自适应"])
        basic_layout.addRow("同步策略:", self.sync_strategy_combo)

        self.auto_recovery_check = QCheckBox("启用自动恢复")
        self.auto_recovery_check.setChecked(True)
        basic_layout.addRow("", self.auto_recovery_check)

        self.recovery_timeout_spin = QDoubleSpinBox()
        self.recovery_timeout_spin.setRange(1.0, 300.0)
        self.recovery_timeout_spin.setValue(30.0)
        self.recovery_timeout_spin.setSuffix(" 秒")
        basic_layout.addRow("恢复超时:", self.recovery_timeout_spin)

        layout.addWidget(basic_group)

        time_group = QGroupBox("时间对齐")
        time_group.setObjectName("panelGroup")
        time_layout = QFormLayout(time_group)
        time_layout.setSpacing(8)

        self.time_sync_strategy_combo = QComboBox()
        self.time_sync_strategy_combo.addItems(["NTP同步", "PTP精确同步", "线性插值", "最近邻匹配"])
        time_layout.addRow("对齐策略:", self.time_sync_strategy_combo)

        self.max_time_offset_spin = QDoubleSpinBox()
        self.max_time_offset_spin.setRange(0.001, 10.0)
        self.max_time_offset_spin.setValue(0.1)
        self.max_time_offset_spin.setSuffix(" 秒")
        self.max_time_offset_spin.setDecimals(3)
        time_layout.addRow("最大偏移:", self.max_time_offset_spin)

        self.ntp_sync_check = QCheckBox("启用NTP时间同步")
        self.ntp_sync_check.setChecked(True)
        time_layout.addRow("", self.ntp_sync_check)

        self.ntp_servers_edit = QLineEdit()
        self.ntp_servers_edit.setText("pool.ntp.org,time.windows.com")
        self.ntp_servers_edit.setPlaceholderText("输入NTP服务器地址，逗号分隔")
        time_layout.addRow("NTP服务器:", self.ntp_servers_edit)

        layout.addWidget(time_group)

        adaptive_group = QGroupBox("自适应调节")
        adaptive_group.setObjectName("panelGroup")
        adaptive_layout = QFormLayout(adaptive_group)
        adaptive_layout.setSpacing(8)

        self.adaptive_sync_check = QCheckBox("启用自适应同步")
        self.adaptive_sync_check.setChecked(True)
        adaptive_layout.addRow("", self.adaptive_sync_check)

        self.adaptive_threshold_spin = QDoubleSpinBox()
        self.adaptive_threshold_spin.setRange(0.1, 1.0)
        self.adaptive_threshold_spin.setValue(0.8)
        self.adaptive_threshold_spin.setDecimals(2)
        adaptive_layout.addRow("自适应阈值:", self.adaptive_threshold_spin)

        self.quality_threshold_spin = QDoubleSpinBox()
        self.quality_threshold_spin.setRange(0.1, 1.0)
        self.quality_threshold_spin.setValue(0.8)
        self.quality_threshold_spin.setDecimals(2)
        adaptive_layout.addRow("质量阈值:", self.quality_threshold_spin)

        layout.addWidget(adaptive_group)

        layout.addStretch()
        scroll.setWidget(scroll_widget)

        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        return tab
    
    def _create_time_alignment_tab(self):
        """"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 
        strategy_group = QGroupBox("")
        strategy_layout = QFormLayout(strategy_group)
        
        # 
        self.time_sync_strategy_combo = QComboBox()
        self.time_sync_strategy_combo.addItems([
            "", "", "", ""
        ])
        strategy_layout.addRow(":", self.time_sync_strategy_combo)
        
        # 
        self.max_time_offset_spin = QDoubleSpinBox()
        self.max_time_offset_spin.setRange(0.001, 10.0)
        self.max_time_offset_spin.setValue(0.1)
        self.max_time_offset_spin.setSuffix(" ")
        self.max_time_offset_spin.setDecimals(3)
        strategy_layout.addRow(":", self.max_time_offset_spin)
        
        # 
        self.quality_threshold_spin = QDoubleSpinBox()
        self.quality_threshold_spin.setRange(0.1, 1.0)
        self.quality_threshold_spin.setValue(0.8)
        self.quality_threshold_spin.setDecimals(2)
        strategy_layout.addRow(":", self.quality_threshold_spin)
        
        layout.addWidget(strategy_group)
        
        # NTP
        ntp_group = QGroupBox("NTP")
        ntp_layout = QFormLayout(ntp_group)
        
        # NTP
        self.ntp_sync_check = QCheckBox("NTP")
        self.ntp_sync_check.setChecked(True)
        ntp_layout.addRow("", self.ntp_sync_check)
        
        # NTP
        self.ntp_servers_edit = QLineEdit()
        self.ntp_servers_edit.setText("pool.ntp.org,time.windows.com,time.apple.com")
        self.ntp_servers_edit.setPlaceholderText("")
        ntp_layout.addRow("NTP:", self.ntp_servers_edit)
        
        # 
        self.ntp_sync_interval_spin = QDoubleSpinBox()
        self.ntp_sync_interval_spin.setRange(1.0, 3600.0)
        self.ntp_sync_interval_spin.setValue(60.0)
        self.ntp_sync_interval_spin.setSuffix(" ")
        ntp_layout.addRow(":", self.ntp_sync_interval_spin)
        
        layout.addWidget(ntp_group)
        
        return tab
    
    def _create_data_fusion_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(12)

        algorithm_group = QGroupBox("融合算法")
        algorithm_group.setObjectName("panelGroup")
        algorithm_layout = QFormLayout(algorithm_group)
        algorithm_layout.setSpacing(8)

        self.fusion_algorithm_combo = QComboBox()
        self.fusion_algorithm_combo.addItems([
            "加权平均", "卡尔曼滤波", "贝叶斯融合", "D-S证据理论", "神经网络", "自适应融合"
        ])
        algorithm_layout.addRow("融合算法:", self.fusion_algorithm_combo)

        self.quality_weight_spin = QDoubleSpinBox()
        self.quality_weight_spin.setRange(0.0, 1.0)
        self.quality_weight_spin.setValue(0.7)
        self.quality_weight_spin.setDecimals(2)
        algorithm_layout.addRow("质量权重:", self.quality_weight_spin)

        self.time_weight_spin = QDoubleSpinBox()
        self.time_weight_spin.setRange(0.0, 1.0)
        self.time_weight_spin.setValue(0.3)
        self.time_weight_spin.setDecimals(2)
        algorithm_layout.addRow("时间权重:", self.time_weight_spin)

        layout.addWidget(algorithm_group)

        advanced_fusion_group = QGroupBox("高级融合参数")
        advanced_fusion_group.setObjectName("panelGroup")
        advanced_fusion_layout = QFormLayout(advanced_fusion_group)
        advanced_fusion_layout.setSpacing(8)

        self.adaptive_fusion_check = QCheckBox("启用自适应融合")
        self.adaptive_fusion_check.setChecked(True)
        advanced_fusion_layout.addRow("", self.adaptive_fusion_check)

        self.fusion_threshold_spin = QDoubleSpinBox()
        self.fusion_threshold_spin.setRange(0.1, 1.0)
        self.fusion_threshold_spin.setValue(0.6)
        self.fusion_threshold_spin.setDecimals(2)
        advanced_fusion_layout.addRow("融合阈值:", self.fusion_threshold_spin)

        self.max_fusion_delay_spin = QDoubleSpinBox()
        self.max_fusion_delay_spin.setRange(0.001, 10.0)
        self.max_fusion_delay_spin.setValue(0.5)
        self.max_fusion_delay_spin.setSuffix(" 秒")
        self.max_fusion_delay_spin.setDecimals(3)
        advanced_fusion_layout.addRow("最大延迟:", self.max_fusion_delay_spin)

        layout.addWidget(advanced_fusion_group)
        layout.addStretch()
        scroll.setWidget(scroll_widget)

        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        return tab
    
    def _create_performance_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(12)

        monitoring_group = QGroupBox("监控配置")
        monitoring_group.setObjectName("panelGroup")
        monitoring_layout = QFormLayout(monitoring_group)
        monitoring_layout.setSpacing(8)

        self.monitor_interval_spin = QDoubleSpinBox()
        self.monitor_interval_spin.setRange(0.1, 60.0)
        self.monitor_interval_spin.setValue(1.0)
        self.monitor_interval_spin.setSuffix(" 秒")
        monitoring_layout.addRow("监控间隔:", self.monitor_interval_spin)

        self.performance_threshold_spin = QDoubleSpinBox()
        self.performance_threshold_spin.setRange(0.1, 1.0)
        self.performance_threshold_spin.setValue(0.8)
        self.performance_threshold_spin.setDecimals(2)
        monitoring_layout.addRow("性能阈值:", self.performance_threshold_spin)

        self.performance_optimization_check = QCheckBox("启用自动性能优化")
        self.performance_optimization_check.setChecked(True)
        monitoring_layout.addRow("", self.performance_optimization_check)

        layout.addWidget(monitoring_group)

        anomaly_group = QGroupBox("异常检测")
        anomaly_group.setObjectName("panelGroup")
        anomaly_layout = QFormLayout(anomaly_group)
        anomaly_layout.setSpacing(8)

        self.anomaly_threshold_spin = QSpinBox()
        self.anomaly_threshold_spin.setRange(50, 95)
        self.anomaly_threshold_spin.setValue(80)
        self.anomaly_threshold_spin.setSuffix("%")
        anomaly_layout.addRow("异常阈值:", self.anomaly_threshold_spin)

        self.anomaly_detection_check = QCheckBox("启用异常自动检测")
        self.anomaly_detection_check.setChecked(True)
        anomaly_layout.addRow("", self.anomaly_detection_check)

        layout.addWidget(anomaly_group)

        resource_group = QGroupBox("资源阈值")
        resource_group.setObjectName("panelGroup")
        resource_layout = QFormLayout(resource_group)
        resource_layout.setSpacing(8)

        self.cpu_threshold_spin = QSpinBox()
        self.cpu_threshold_spin.setRange(50, 100)
        self.cpu_threshold_spin.setValue(80)
        self.cpu_threshold_spin.setSuffix("%")
        resource_layout.addRow("CPU阈值:", self.cpu_threshold_spin)

        self.memory_threshold_spin = QSpinBox()
        self.memory_threshold_spin.setRange(50, 100)
        self.memory_threshold_spin.setValue(85)
        self.memory_threshold_spin.setSuffix("%")
        resource_layout.addRow("内存阈值:", self.memory_threshold_spin)

        self.sync_rate_threshold_spin = QSpinBox()
        self.sync_rate_threshold_spin.setRange(10, 500)
        self.sync_rate_threshold_spin.setValue(100)
        self.sync_rate_threshold_spin.setSuffix(" Hz")
        resource_layout.addRow("同步速率阈值:", self.sync_rate_threshold_spin)

        layout.addWidget(resource_group)
        layout.addStretch()
        scroll.setWidget(scroll_widget)

        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        return tab
    
    def _create_status_widget(self):
        """"""
        # 
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        
        # 
        realtime_group = QGroupBox(" ")
        realtime_layout = QVBoxLayout(realtime_group)
        
        # 
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(3)
        self.status_table.setHorizontalHeaderLabels(["", "", ""])
        self.status_table.setRowCount(8)
        
        # 
        status_rows = [
            ("", "0", ""),
            ("", "0 Hz", ""),
            ("", "0 ms", ""),
            ("", "0%", ""),
            ("", "", ""),
            ("", "0%", ""),
            ("", "0 MB", ""),
            ("", "0 ms", "")
        ]
        
        for i, (metric, value, status) in enumerate(status_rows):
            self.status_table.setItem(i, 0, QTableWidgetItem(metric))
            self.status_table.setItem(i, 1, QTableWidgetItem(value))
            self.status_table.setItem(i, 2, QTableWidgetItem(status))
        
        # 
        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        realtime_layout.addWidget(self.status_table)
        status_layout.addWidget(realtime_group)
        
        # 
        performance_group = QGroupBox(" ")
        performance_layout = QVBoxLayout(performance_group)
        
        # 
        self.performance_display = QLabel("...")
        performance_layout.addWidget(self.performance_display)
        
        # 
        performance_controls = QHBoxLayout()
        
        refresh_btn = QPushButton(" ")
        refresh_btn.clicked.connect(self.update_performance_metrics)
        performance_controls.addWidget(refresh_btn)
        
        auto_refresh_check = QCheckBox("")
        auto_refresh_check.setChecked(True)
        auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        performance_controls.addWidget(auto_refresh_check)
        
        performance_layout.addLayout(performance_controls)
        status_layout.addWidget(performance_group)
        
        # 
        custom_metrics_group = QGroupBox(" ")
        custom_metrics_layout = QVBoxLayout(custom_metrics_group)
        
        # 
        threshold_layout = QFormLayout()
        
        self.cpu_threshold_spin = QSpinBox()
        self.cpu_threshold_spin.setRange(50, 100)
        self.cpu_threshold_spin.setValue(80)
        self.cpu_threshold_spin.setSuffix("%")
        threshold_layout.addRow("CPU:", self.cpu_threshold_spin)
        
        self.memory_threshold_spin = QSpinBox()
        self.memory_threshold_spin.setRange(50, 100)
        self.memory_threshold_spin.setValue(85)
        self.memory_threshold_spin.setSuffix("%")
        threshold_layout.addRow(":", self.memory_threshold_spin)
        
        self.sync_rate_threshold_spin = QSpinBox()
        self.sync_rate_threshold_spin.setRange(10, 500)
        self.sync_rate_threshold_spin.setValue(100)
        self.sync_rate_threshold_spin.setSuffix(" Hz")
        threshold_layout.addRow(":", self.sync_rate_threshold_spin)
        
        custom_metrics_layout.addLayout(threshold_layout)
        
        # 
        custom_controls = QHBoxLayout()
        
        save_thresholds_btn = QPushButton(" ")
        save_thresholds_btn.clicked.connect(self.save_custom_thresholds)
        custom_controls.addWidget(save_thresholds_btn)
        
        load_thresholds_btn = QPushButton(" ")
        load_thresholds_btn.clicked.connect(self.load_custom_thresholds)
        custom_controls.addWidget(load_thresholds_btn)
        
        reset_thresholds_btn = QPushButton(" ")
        reset_thresholds_btn.clicked.connect(self.reset_custom_thresholds)
        custom_controls.addWidget(reset_thresholds_btn)
        
        custom_metrics_layout.addLayout(custom_controls)
        status_layout.addWidget(custom_metrics_group)
        
        # 
        scroll_area.setWidget(status_widget)
        
        return scroll_area
    
    def _create_quick_operations_widget(self):
        """"""
        quick_widget = QWidget()
        quick_layout = QHBoxLayout(quick_widget)
        
        # 
        config_btn = QPushButton(" ")
        config_btn.clicked.connect(self.save_config)
        quick_layout.addWidget(config_btn)
        
        load_btn = QPushButton(" ")
        load_btn.clicked.connect(self.load_config)
        quick_layout.addWidget(load_btn)
        
        export_btn = QPushButton(" ")
        export_btn.clicked.connect(self.export_config)
        quick_layout.addWidget(export_btn)
        
        import_btn = QPushButton(" ")
        import_btn.clicked.connect(self.import_config)
        quick_layout.addWidget(import_btn)
        
        validate_btn = QPushButton(" ")
        validate_btn.clicked.connect(self.validate_config)
        quick_layout.addWidget(validate_btn)
        
        # 
        backup_btn = QPushButton(" ")
        backup_btn.clicked.connect(self.create_config_backup)
        quick_layout.addWidget(backup_btn)
        
        history_btn = QPushButton(" ")
        history_btn.clicked.connect(self.record_performance_history)
        quick_layout.addWidget(history_btn)
        
        trends_btn = QPushButton(" ")
        trends_btn.clicked.connect(self._show_trends_analysis)
        quick_layout.addWidget(trends_btn)
        
        reset_btn = QPushButton(" ")
        reset_btn.clicked.connect(self.reset_configuration)
        quick_layout.addWidget(reset_btn)
        
        quick_layout.addStretch()
        
        # 
        start_sync_btn = QPushButton(" ")
        start_sync_btn.clicked.connect(self.start_synchronization)
        quick_layout.addWidget(start_sync_btn)
        
        stop_sync_btn = QPushButton("⏹ ")
        stop_sync_btn.clicked.connect(self.stop_synchronization)
        quick_layout.addWidget(stop_sync_btn)
        
        test_btn = QPushButton(" ")
        test_btn.clicked.connect(self.test_connections)
        quick_layout.addWidget(test_btn)
        
        return quick_widget
    
    # 
    
    def _on_config_changed(self):
        """"""
        config = self.get_current_config()
        self.config_changed.emit(config)
        self.logger.info("")
    
    def _on_fusion_algorithm_changed(self, algorithm: str):
        """"""
        self.fusion_algorithm_changed.emit(algorithm)
        self.logger.info(f": {algorithm}")
    
    def _on_source_type_changed(self, source_type: str):
        """"""
        self.logger.info(f": {source_type}")
    
    def add_data_source(self):
        """"""
        try:
            # 
            from ..data_source_config.data_source_config_dialog import DataSourceConfigDialog
            
            # 
            dialog = DataSourceConfigDialog(self)
            #  - config_completeddata_source_configured
            dialog.config_completed.connect(self._on_new_data_source_configured)
            
            if dialog.exec() == QDialog.Accepted:
                self.logger.info("")
            else:
                self.logger.info("")
                
        except ImportError as e:
            QMessageBox.warning(self, "", f": {e}")
            self.logger.error(f": {e}")
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")
    
    def _create_enhanced_config(self, source_id: str, config_data: dict) -> dict:
        """"""
        try:
            # 
            from core.core.multi_source_sync.data_source_interfaces import DataSourceFactory
            
            # 
            enhanced_config = config_data.copy()
            
            # 
            basic_info = config_data.get("basic", {})
            source_type = basic_info.get("type", "").lower()
            
            # UI
            type_mapping = {
                "imu": "imu",
                "cnap": "cnap", 
                "mqtt": "mqtt",
                "": "serial",
                "": "network",
                "file": "file",  # 
                # UI - 
                "IMU": "file",  # IMU
                "imu": "file",  # 
                "CNAP": "file",  # CNAP
                "cnap": "file",  # 
                "GPS": "file",   # GPS
                "gps": "file",   # 
                "": "file", # 
                "": "file", # 
                "": "file"  # 
            }
            
            interface_type = type_mapping.get(source_type, source_type)
            
            # 
            interface_config = {
                'source_id': source_id,
                'sampling_rate': basic_info.get('sampling_rate', 100)
            }
            
            # 
            if interface_type == "imu":
                interface_config.update({
                    'device_path': config_data.get('connection', {}).get('device_path', '/dev/ttyUSB0'),
                    'baud_rate': config_data.get('connection', {}).get('baud_rate', 115200)
                })
            elif interface_type == "cnap":
                interface_config.update({
                    'device_path': config_data.get('connection', {}).get('device_path', '/dev/ttyUSB1'),
                    'baud_rate': config_data.get('connection', {}).get('baud_rate', 9600)
                })
            elif interface_type == "mqtt":
                interface_config.update({
                    'broker': config_data.get('connection', {}).get('broker', 'localhost'),
                    'port': config_data.get('connection', {}).get('port', 1883),
                    'topic': config_data.get('connection', {}).get('topic', 'data/sensors')
                })
            elif interface_type == "file":
                interface_config.update({
                    'file_path': config_data.get('connection', {}).get('file_path', ''),
                    'data_format': config_data.get('connection', {}).get('data_format', 'txt')
                })
                # CNAP
                if config_data.get('connection', {}).get('use_cnap_parser', False):
                    interface_config['use_cnap_parser'] = True
            
            # 
            interface = DataSourceFactory.create_data_source(interface_type, interface_config)
            
            if interface:
                # 
                enhanced_config['interface'] = interface
                enhanced_config['interface_type'] = interface_type
                enhanced_config['has_real_interface'] = True
                
                self.logger.info(f"  {source_id}  {interface_type} ")
            else:
                self.logger.warning(f"  {source_id} : {interface_type}")
                enhanced_config['has_real_interface'] = False
            
            return enhanced_config
            
        except ImportError as e:
            self.logger.error(f" : {e}")
            config_data['has_real_interface'] = False
            return config_data
        except Exception as e:
            self.logger.error(f" : {e}")
            config_data['has_real_interface'] = False
            return config_data
    
    def _create_sample_data_sources(self):
        """"""
        try:
            self.logger.info(" ...")
            
            if not self.sync_engine:
                self.logger.error(" ")
                return False
                
            self.logger.info(" ")
            
            # 
            try:
                from core.core.multi_source_sync.data_source_config_manager import DataSourceConfigManager
                config_manager = DataSourceConfigManager()
            except ImportError as e:
                self.logger.error(f" : {e}")
                return self._create_fallback_data_sources()
            
            # 
            errors = config_manager.validate_config()
            if errors:
                self.logger.warning(f"  {len(errors)} ")
                for error in errors:
                    self.logger.warning(f"  - {error}")
            
            # 
            all_sources = config_manager.get_all_data_sources()
            if not all_sources:
                self.logger.warning(" ")
                return self._create_fallback_data_sources()
            
            self.logger.info(f"  {len(all_sources)} ")
            
            # 
            summary = config_manager.get_config_summary()
            self.logger.info(f" : {summary}")
            
            # 
            success_count = 0
            total_count = len(all_sources)
            
            for source_id, config in all_sources.items():
                try:
                    self.logger.info(f"  {source_id}...")
                    
                    # 
                    enhanced_config = self._create_enhanced_config(source_id, config)
                    if not enhanced_config:
                        self.logger.error(f"  {source_id} ")
                        continue
                    
                    # 
                    success = self.sync_engine.add_data_source(source_id, enhanced_config)
                    if success:
                        self.logger.info(f"  {source_id} ")
                        
                        # 
                        try:
                            if enhanced_config.get('interface'):
                                auto_start = config.get('metadata', {}).get('auto_start', False)
                                if auto_start:
                                    enhanced_config['interface'].connect()
                                    self.logger.info(f"  {source_id} 已自动连接")
                                else:
                                    self.logger.info(f"  {source_id} 未自动连接(auto_start=false)，按需手动启动")
                            else:
                                self.logger.warning(f"  {source_id} 缺少interface")
                        except Exception as e:
                            self.logger.error(f"  {source_id} : {e}")
                        
                        success_count += 1
                    else:
                        self.logger.error(f"  {source_id} ")
                        
                except Exception as e:
                    self.logger.error(f"  {source_id} : {e}")
                    continue
            
            if success_count > 0:
                self.logger.info(f"  {success_count}/{total_count} ")
                
                # 
                self.logger.info(" ")
                
                # 
                self.logger.info(" ")
                
                # 
                self._refresh_data_sources_display()
                
                return True
            else:
                self.logger.error(" ")
                return self._create_fallback_data_sources()
                
        except Exception as e:
            self.logger.error(f" : {e}")
            import traceback
            self.logger.error(f": {traceback.format_exc()}")
            return self._create_fallback_data_sources()
    
    def _create_fallback_data_sources(self):
        """"""
        try:
            self.logger.info(" ...")
            
            # DataSourceFactory
            from core.core.multi_source_sync.data_source_interfaces import DataSourceFactory
            
            # IMU
            imu_config = {
                "file_path": "test/cnapdata/1.txt",
                "data_format": "txt",
                "sampling_rate": 10
            }
            
            imu_source = DataSourceFactory.create_data_source("file", imu_config)
            if imu_source:
                self.logger.info("IMU数据源配置完成，未自动连接（auto_start=false）")
                if hasattr(self.sync_engine, 'add_data_source'):
                    self.sync_engine.add_data_source("DS_001", {"interface": imu_source})
            else:
                self.logger.error("IMU数据源创建失败")
            
            cnap_source = DataSourceFactory.create_data_source("file", cnap_config)
            if cnap_source:
                self.logger.info("CNAP数据源配置完成，未自动连接（auto_start=false）")
                if hasattr(self.sync_engine, 'add_data_source'):
                    self.sync_engine.add_data_source("DS_002", {"interface": cnap_source})
            else:
                self.logger.error("CNAP数据源创建失败")
                
        except Exception as e:
            self.logger.error(f" : {e}")
            import traceback
            self.logger.error(f": {traceback.format_exc()}")
    
    def _force_start_data_flow(self):
        """"""
        try:
            self.logger.info(" ...")
            
            if not self.sync_engine:
                self.logger.error(" ")
                return False
            
            # 
            if hasattr(self.sync_engine, 'data_sources'):
                for source_id, source_config in self.sync_engine.data_sources.items():
                    if source_id in ['DS_001', 'DS_002']:
                        interface = source_config.get('interface')
                        if interface:
                            self.logger.info(f"  {source_id} ...")
                            
                            # 
                            try:
                                data = interface.get_data()
                                if data:
                                    self.logger.info(f"  {source_id}  {len(data)} ")
                                else:
                                    self.logger.warning(f"  {source_id} ")
                            except Exception as e:
                                self.logger.error(f"  {source_id} : {e}")
                            
                            # 
                            if hasattr(interface, 'get_status'):
                                try:
                                    status = interface.get_status()
                                    self.logger.info(f"  {source_id} : {status}")
                                except Exception as e:
                                    self.logger.error(f"  {source_id} : {e}")
                        else:
                            self.logger.warning(f"  {source_id} ")
            
            # 
            if hasattr(self.sync_engine, 'start_sync'):
                try:
                    self.logger.info(" ...")
                    success = self.sync_engine.start_sync()
                    if success:
                        self.logger.info(" ")
                        return True
                    else:
                        self.logger.error(" ")
                        return False
                except Exception as e:
                    self.logger.error(f" : {e}")
                    return False
            else:
                self.logger.error(" start_sync")
                return False
                
        except Exception as e:
            self.logger.error(f" : {e}")
            import traceback
            self.logger.error(f": {traceback.format_exc()}")
            return False
    
    def _auto_start_sync(self):
        """"""
        try:
            if not self.sync_engine:
                self.logger.error(" ")
                return False
                
            # 
            connected_sources = []
            if hasattr(self.sync_engine, 'data_sources'):
                for source_id, source_config in self.sync_engine.data_sources.items():
                    interface = source_config.get('interface')
                    if interface:
                        # is_connected
                        if hasattr(interface, 'is_connected') and callable(interface.is_connected):
                            if interface.is_connected():
                                connected_sources.append(source_id)
                                self.logger.info(f"  {source_id} ")
                        else:
                            # is_connected
                            connected_sources.append(source_id)
                            self.logger.info(f"  {source_id} ")
                    else:
                        self.logger.warning(f"  {source_id} ")
            
            if not connected_sources:
                self.logger.warning(" ")
                return False
            
            # 
            if hasattr(self.sync_engine, 'start_sync'):
                success = self.sync_engine.start_sync(connected_sources)
                if success:
                    self.logger.info(f"  {len(connected_sources)} ")
                    # UI
                    if hasattr(self, 'quick_status_label'):
                        self.quick_status_label.setText(" : ")
                    return True
                else:
                    self.logger.error(" ")
                    return False
            else:
                self.logger.error(" start_sync")
                return False
                
        except Exception as e:
            self.logger.error(f" : {e}")
            import traceback
            self.logger.error(f": {traceback.format_exc()}")
            return False
    
    def _ensure_sample_data_sources(self):
        """"""
        try:
            self.logger.info(" ...")
            
            if not self.sync_engine:
                self.logger.error(" sync_engineNone")
                return
                
            self.logger.info(f" sync_engine: {type(self.sync_engine).__name__}")
            
            # 
            existing_sources = getattr(self.sync_engine, 'data_sources', {})
            self.logger.info(f" : {list(existing_sources.keys())}")
            
            if 'DS_001' in existing_sources and 'DS_002' in existing_sources:
                self.logger.info(" ")
                # 
                for source_id, source_config in existing_sources.items():
                    if source_id in ['DS_001', 'DS_002']:
                        has_interface = 'interface' in source_config
                        self.logger.info(f"  {source_id} : {'' if has_interface else ''}")
                return
                
            # 
            self.logger.info(" ...")
            self._create_sample_data_sources()
            
            # 
            updated_sources = getattr(self.sync_engine, 'data_sources', {})
            self.logger.info(f" : {list(updated_sources.keys())}")
            
        except Exception as e:
            self.logger.error(f" : {e}")
            import traceback
            self.logger.error(f": {traceback.format_exc()}")
    
    def _on_data_source_configured(self, config_data: dict):
        """"""
        try:
            # 
            current_row = self.sources_table.rowCount()
            self.sources_table.insertRow(current_row)
            
            # 
            basic_info = config_data.get("basic", {})
            
            # ID
            source_id = f"DS_{current_row + 1:03d}"
            self.sources_table.setItem(current_row, 0, QTableWidgetItem(source_id))
            
            # 
            source_name = basic_info.get("name", "")
            self.sources_table.setItem(current_row, 1, QTableWidgetItem(source_name))
            
            # 
            source_type = basic_info.get("type", "")
            self.sources_table.setItem(current_row, 2, QTableWidgetItem(source_type))
            
            # 
            self.sources_table.setItem(current_row, 3, QTableWidgetItem(""))
            
            # 
            data_rate = "0 Hz"
            self.sources_table.setItem(current_row, 4, QTableWidgetItem(data_rate))
            
            #  - /
            operation_widget = None #  operation_widget 
            operation_widget = QWidget()
            operation_layout = QHBoxLayout(operation_widget)
            operation_layout.setContentsMargins(2, 2, 2, 2)
            
            # 
            btn = QPushButton("")
            btn.clicked.connect(partial(self._connect_data_source, current_row))
            
            btn.setMaximumWidth(60)
            operation_layout.addWidget(btn)
            operation_layout.addStretch()
            
            self.sources_table.setCellWidget(current_row, 5, operation_widget)
            
            # 
            self.data_sources[source_id] = config_data
            
            # 
            if self.sync_engine and hasattr(self.sync_engine, 'add_data_source'):
                try:
                    # 
                    enhanced_config = self._create_enhanced_config(source_id, config_data)
                    
                    success = self.sync_engine.add_data_source(source_id, enhanced_config)
                    if success:
                        self.logger.info(f"  {source_id} ")
                        self._add_event(f" {source_id} ")
                        
                        # 
                        if enhanced_config.get('interface'):
                            try:
                                interface = enhanced_config['interface']
                                if interface.connect():
                                    self.logger.info(f"  {source_id} ")
                                    self._add_event(f": {source_name}")
                                else:
                                    self.logger.warning(f"  {source_id} ")
                            except Exception as e:
                                self.logger.error(f"  {source_id} : {e}")
                    else:
                        self.logger.warning(f"  {source_id} ")
                except Exception as e:
                    self.logger.error(f" : {e}")
            
            # 
            self._update_source_count()
            
            # 
            self.update_overview_statistics()
            
            # 
            self._add_event(f": {basic_info.get('name', '')}")
            
            QMessageBox.information(self, "", f" '{basic_info.get('name', '')}' ")
            
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")
    
    def _connect_data_source(self, row: int):
        """ - """
        try:
            # ID
            source_id = self.sources_table.item(row, 0).text()
            
            # 
            self.sources_table.setItem(row, 3, QTableWidgetItem("🟡 "))
            
            # 
            if self.sync_engine and hasattr(self.sync_engine, 'connect_data_source'):
                try:
                    # 
                    source_config = self.data_sources.get(source_id, {})
                    
                    # 
                    success = self.sync_engine.connect_data_source(source_id, source_config)
                    
                    if success:
                        # 
                        self._start_data_processing(row, source_id, source_config)
                        
                        # 
                        self._notify_parsing_control_status_update()
                        
                    else:
                        # 
                        self.sources_table.setItem(row, 3, QTableWidgetItem(" "))
                        self._add_event(f" {source_id} ")
                        
                except Exception as e:
                    self.logger.error(f": {e}")
                    # 
                    QTimer.singleShot(1000, lambda: self._complete_connection(row))
            else:
                # 
                QTimer.singleShot(1000, lambda: self._complete_connection(row))
            
            self._add_event(f" {source_id}")
            
        except Exception as e:
            self.logger.error(f": {e}")
            self.sources_table.setItem(row, 4, QTableWidgetItem(" "))
    
    def _notify_parsing_control_status_update(self):
        """"""
        try:
            # 
            connected_sources = 0
            for row in range(self.sources_table.rowCount()):
                status_item = self.sources_table.item(row, 3)
                if status_item and "" in status_item.text():
                    connected_sources += 1
            
            # 
            sync_running = False
            if self.sync_engine and hasattr(self.sync_engine, 'status'):
                sync_running = self.sync_engine.status in ['RUNNING', 'INITIALIZING']
            
            # 
            status_info = {
                'sync_running': sync_running,
                'connected_sources': connected_sources,
                'total_sources': self.sources_table.rowCount()
            }
            
            # 
            self.sync_status_updated.emit(status_info)
            
            # 
            if hasattr(self.parent(), 'parsing_control_panel'):
                parsing_panel = self.parent().parsing_control_panel
                if hasattr(parsing_panel, 'update_sync_status'):
                    parsing_panel.update_sync_status(status_info)
            
            self.logger.info(f": {status_info}")
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _start_data_processing(self, row: int, source_id: str, source_config: dict):
        """"""
        try:
            # 
            self.sources_table.setItem(row, 3, QTableWidgetItem("🟢 "))
            
            # 
            self._update_operation_button(row, True)
            
            # 
            if self.sync_engine and hasattr(self.sync_engine, 'start_data_processing'):
                try:
                    # 
                    success = self.sync_engine.start_data_processing(source_id)
                    
                    if success:
                        # 
                        data_rate = self._get_data_rate(source_id)
                        self.sources_table.setItem(row, 4, QTableWidgetItem(data_rate))
                        
                        self._add_event(f" {source_id} ")
                        self.logger.info(f"  {source_id} ")
                    else:
                        self._add_event(f" {source_id} ")
                        self.logger.warning(f"  {source_id} ")
                        
                except Exception as e:
                    self.logger.error(f": {e}")
                    # 
                    self._complete_connection(row)
            else:
                # 
                self._complete_connection(row)
                
        except Exception as e:
            self.logger.error(f": {e}")
            self._complete_connection(row)
    
    def _get_data_rate(self, source_id: str) -> str:
        try:
            if self.sync_engine and hasattr(self.sync_engine, 'get_data_rate'):
                rate = self.sync_engine.get_data_rate(source_id)
                return f"{rate} Hz" if rate else "0 Hz"
            else:
                return "0 Hz"
        except:
            return "0 Hz"
    
    def _complete_connection(self, row: int):
        try:
            self.sources_table.setItem(row, 3, QTableWidgetItem("🟢 已连接"))
            self.sources_table.setItem(row, 4, QTableWidgetItem("-- Hz"))
            
            self._update_operation_button(row, True)
            self._add_event(f"数据源 {row + 1} 连接成功")
        except Exception as e:
            self.sources_table.setItem(row, 3, QTableWidgetItem("🔴 失败"))
            self.sources_table.setItem(row, 4, QTableWidgetItem("-- Hz"))
            self._add_event(f"数据源 {row + 1} 连接失败: {e}")
        
        self._update_source_count()
        self.update_overview_statistics()
    
    def _disconnect_data_source(self, row: int):
        """"""
        try:
            # ID
            source_id = self.sources_table.item(row, 0).text()
            
            # 
            self.sources_table.setItem(row, 3, QTableWidgetItem(" "))
            self.sources_table.setItem(row, 4, QTableWidgetItem("0 Hz"))
            
            # 
            if self.sync_engine and hasattr(self.sync_engine, 'disconnect_data_source'):
                try:
                    # 
                    success = self.sync_engine.disconnect_data_source(source_id)
                    
                    if success:
                        self._add_event(f" {source_id} ")
                        self.logger.info(f"  {source_id} ")
                    else:
                        self._add_event(f" {source_id} ")
                        self.logger.warning(f"  {source_id} ")
                        
                except Exception as e:
                    self.logger.error(f": {e}")
                    # 
                    self._add_event(f" {source_id} ")
            else:
                # 
                self._add_event(f" {source_id} ")
            
            # 
            self._update_source_count()
            
            # 
            self.update_overview_statistics()
            
            # 
            self._update_operation_button(row, False)
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    # _update_operation_button
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _configure_data_source_legacy(self, row: int):
        """"""
        try:
            QMessageBox.information(self, "", f" {row + 1} ")
            self._add_event(f" {row + 1}")
        except Exception as e:
            self.logger.error(f": {e}")
    
    def save_configuration(self):
        """"""
        config = self.get_current_config()
        try:
            # 
            config_file = Path("config/multi_source_sync_config.json")
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "", "")
            self.logger.info("")
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")
    
    def load_configuration(self):
        """"""
        try:
            config_file = Path("config/multi_source_sync_config.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.apply_configuration(config)
                QMessageBox.information(self, "", "")
                self.logger.info("")
            else:
                QMessageBox.warning(self, "", "")
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")
    
    def reset_configuration(self):
        """"""
        reply = QMessageBox.question(
            self, "", "",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.apply_default_configuration()
            QMessageBox.information(self, "", "")
            self.logger.info("")
    
    def start_synchronization(self):
        """"""
        try:
            if self.sync_engine and hasattr(self.sync_engine, 'start_sync'):
                # 
                connected_sources = []
                for row in range(self.sources_table.rowCount()):
                    status = self.sources_table.item(row, 4).text()
                    if "" in status:
                        source_id = self.sources_table.item(row, 0).text()
                        connected_sources.append(source_id)
                
                if connected_sources:
                    # 
                    success = self.sync_engine.start_sync(connected_sources)
                    
                    if success:
                        self.quick_status_label.setText(" : ")
                        
                        self.update_overview_statistics()
                        
                        # 
                        self.update_sync_status()
                        
                        QMessageBox.information(self, "", f" {len(connected_sources)} ")
                        self.logger.info(f" : {connected_sources}")
                        self._add_event("")
                    else:
                        QMessageBox.warning(self, "", "")
                        self.logger.error(" ")
                else:
                    QMessageBox.warning(self, "", "")
            else:
                # 
                QMessageBox.warning(self, "", "")
                self.logger.error(" ")
                
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f" : {e}")
    
    def stop_synchronization(self):
        """"""
        try:
            if self.sync_engine and hasattr(self.sync_engine, 'stop_sync'):
                # 
                success = self.sync_engine.stop_sync()
                
                if success:
                    self.quick_status_label.setText(" : ")
                    
                    self.update_overview_statistics()
                    
                    # 
                    self.update_sync_status()
                    
                    QMessageBox.information(self, "", "")
                    self.logger.info(" ")
                    self._add_event("")
                else:
                    QMessageBox.warning(self, "", "")
                    self.logger.error(" ")
            else:
                # 
                QMessageBox.warning(self, "", "")
                self.logger.error(" ")
                
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f" : {e}")
    
    def _on_sync_status_updated(self, status_data: dict):
        """"""
        try:
            # 
            self.sync_status.update(status_data)
            
            # UI
            if 'overall_status' in status_data:
                status = status_data['overall_status']
                if status == 'running':
                    self.quick_status_label.setText(" : ")
                elif status == 'stopped':
                    self.quick_status_label.setText(" : ")
                elif status == 'error':
                    self.quick_status_label.setText(" : ")
            
            # 
            if 'message' in status_data:
                self._add_event(f": {status_data['message']}")
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _on_sync_error(self, error_data: dict):
        """"""
        try:
            # 
            error_msg = error_data.get('message', '')
            source_id = error_data.get('source_id', '')
            error_code = error_data.get('error_code', 'UNKNOWN')
            error_timestamp = error_data.get('timestamp', time.time())
            error_details = error_data.get('details', {})
            
            # 
            formatted_error = self._format_error_message(error_code, error_msg, error_details)
            
            # 
            QMessageBox.warning(self, "", f" {source_id}:\n{formatted_error}")
            
            # 
            self._add_event(f": {source_id} - {error_code}: {error_msg}")
            
            # 
            self.quick_status_label.setText(" : ")
            
            self.logger.error(f" - : {source_id}, : {error_code}, : {error_msg}")
            
            # 
            self._update_error_statistics(error_code, source_id)
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _format_error_message(self, error_code: str, error_msg: str, error_details: dict) -> str:
        """"""
        error_descriptions = {
            'CONNECTION_FAILED': '',
            'DATA_PARSE_ERROR': '',
            'SYNC_TIMEOUT': '',
            'INVALID_CONFIG': '',
            'RESOURCE_UNAVAILABLE': '',
            'NETWORK_ERROR': '',
            'PERMISSION_DENIED': '',
            'UNKNOWN': ''
        }
        
        description = error_descriptions.get(error_code, '')
        formatted_msg = f"{description}\n{error_msg}"
        
        # 
        if error_details:
            if 'retry_count' in error_details:
                formatted_msg += f"\n: {error_details['retry_count']}"
            if 'suggested_action' in error_details:
                formatted_msg += f"\n: {error_details['suggested_action']}"
        
        return formatted_msg
    
    def _update_error_statistics(self, error_code: str, source_id: str):
        """"""
        try:
            if not hasattr(self, 'error_statistics'):
                self.error_statistics = {}
            
            if error_code not in self.error_statistics:
                self.error_statistics[error_code] = {
                    'count': 0,
                    'sources': set(),
                    'last_occurrence': time.time()
                }
            
            self.error_statistics[error_code]['count'] += 1
            self.error_statistics[error_code]['sources'].add(source_id)
            self.error_statistics[error_code]['last_occurrence'] = time.time()
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _on_data_processed(self, data_info: dict):
        """"""
        try:
            # 
            source_id = data_info.get('source_id', '')
            data_count = data_info.get('count', 0)
            data_type = data_info.get('type', '')
            processing_time = data_info.get('processing_time', 0)
            data_size = data_info.get('data_size', 0)
            quality_score = data_info.get('quality_score', 0)
            timestamp = data_info.get('timestamp', time.time())
            
            # 
            real_rate = self._calculate_real_data_rate(source_id, data_count, processing_time)
            
            # 
            for row in range(self.sources_table.rowCount()):
                if self.sources_table.item(row, 0).text() == source_id:
                    # 
                    rate_text = f"{real_rate} Hz"
                    self.sources_table.setItem(row, 5, QTableWidgetItem(rate_text))
                    
                    # 
                    self._update_data_quality_indicator(row, quality_score)
                    break
            
            # 
            self._update_data_processing_statistics(source_id, data_count, data_type, processing_time, data_size, quality_score)
            
            # 
            log_msg = f": {source_id} - {data_count}  {data_type} "
            if processing_time > 0:
                log_msg += f", : {processing_time:.2f}ms"
            if data_size > 0:
                log_msg += f", : {data_size} bytes"
            if quality_score > 0:
                log_msg += f", : {quality_score}%"
            
            self._add_event(log_msg)
            
            # 
            self.update_overview_statistics()
            
            # 
            self._check_performance_metrics(source_id, processing_time, quality_score)
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _calculate_real_data_rate(self, source_id: str, data_count: int, processing_time: float) -> int:
        """"""
        try:
            if processing_time <= 0:
                return 0
            
            # 
            rate = int((data_count / processing_time) * 1000)  # Hz
            
            # 
            if hasattr(self, 'data_rate_history'):
                if source_id not in self.data_rate_history:
                    self.data_rate_history[source_id] = []
                
                history = self.data_rate_history[source_id]
                history.append(rate)
                
                # 10
                if len(history) > 10:
                    history.pop(0)
                
                # 
                if len(history) >= 3:
                    # 
                    weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # 1
                    weighted_sum = 0
                    for i, (h, w) in enumerate(zip(history[-5:], weights)):
                        weighted_sum += h * w
                    rate = int(weighted_sum)
            
            return max(0, rate)
            
        except Exception as e:
            self.logger.error(f": {e}")
            return 0
    
    def _update_data_quality_indicator(self, row: int, quality_score: float):
        """"""
        try:
            # 
            if quality_score >= 90:
                color = "#28a745"  # 
                status = ""
            elif quality_score >= 70:
                color = "#ffc107"  # 
                status = ""
            elif quality_score >= 50:
                color = "#fd7e14"  # 
                status = ""
            else:
                color = "#dc3545"  # 
                status = ""
            
            # 
            status_item = self.sources_table.item(row, 4)
            if status_item:
                status_item.setBackground(QColor(color))
                status_item.setForeground(QColor("#e8eaed"))
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _update_data_processing_statistics(self, source_id: str, data_count: int, data_type: str, 
                                         processing_time: float, data_size: int, quality_score: float):
        """"""
        try:
            if not hasattr(self, 'data_processing_stats'):
                self.data_processing_stats = {}
            
            if source_id not in self.data_processing_stats:
                self.data_processing_stats[source_id] = {
                    'total_count': 0,
                    'total_time': 0,
                    'total_size': 0,
                    'quality_scores': [],
                    'data_types': set(),
                    'last_update': time.time()
                }
            
            stats = self.data_processing_stats[source_id]
            stats['total_count'] += data_count
            stats['total_time'] += processing_time
            stats['total_size'] += data_size
            stats['quality_scores'].append(quality_score)
            stats['data_types'].add(data_type)
            stats['last_update'] = time.time()
            
            # 100
            if len(stats['quality_scores']) > 100:
                stats['quality_scores'] = stats['quality_scores'][-100:]
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _check_performance_metrics(self, source_id: str, processing_time: float, quality_score: float):
        """"""
        try:
            # 
            if processing_time > 1000:  # 1
                self.logger.warning(f" {source_id} : {processing_time:.2f}ms")
                self._add_event(f": {source_id} ")
            
            # 
            if quality_score < 50:
                self.logger.warning(f" {source_id} : {quality_score}%")
                self._add_event(f": {source_id} ")
            
            # 
            if processing_time > 500 and quality_score < 70:
                self.logger.warning(f" {source_id} ")
                self._add_event(f": {source_id} ")
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def update_performance_metrics(self):
        """"""
        try:
            if not hasattr(self, 'data_processing_stats'):
                return
            
            # 
            total_throughput = 0
            total_quality = 0
            active_sources = 0
            
            for source_id, stats in self.data_processing_stats.items():
                if stats['total_count'] > 0:
                    # 
                    throughput = stats['total_count'] / max(1, (time.time() - stats['last_update']))
                    total_throughput += throughput
                    
                    # 
                    if stats['quality_scores']:
                        avg_quality = sum(stats['quality_scores']) / len(stats['quality_scores'])
                        total_quality += avg_quality
                        active_sources += 1
            
            # 
            if active_sources > 0:
                avg_throughput = total_throughput / active_sources
                avg_quality = total_quality / active_sources
                
                # 
                if hasattr(self, 'performance_indicator'):
                    self.performance_indicator.setText(f": {avg_throughput:.1f} /")
                
                # 
                if avg_throughput < 10:
                    self.logger.warning("")
                    self._add_event(": ")
                
                if avg_quality < 70:
                    self.logger.warning("")
                    self._add_event(": ")
                    
        except Exception as e:
            self.logger.error(f": {e}")
    
    def update_resource_usage(self):
        """"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            current_process = psutil.Process()
            process_memory = current_process.memory_info().rss / (1024 * 1024)  # MB
            process_cpu = current_process.cpu_percent()
            
            if hasattr(self, 'resource_indicator'):
                self.resource_indicator.setText(f"CPU: {cpu_percent:.1f}% | : {process_memory:.0f}MB")
            
            current_time = time.time()
            if not hasattr(self, '_last_resource_alert_time'):
                self._last_resource_alert_time = {}
            
            if cpu_percent > 95:
                last = self._last_resource_alert_time.get('cpu', 0)
                if current_time - last > 60:
                    self._last_resource_alert_time['cpu'] = current_time
                    self.logger.warning(f"CPU: {cpu_percent:.1f}%")
                    self._add_event(f": CPU ({cpu_percent:.1f}%)")
            
            if memory_info.percent > 90:
                last = self._last_resource_alert_time.get('memory', 0)
                if current_time - last > 60:
                    self._last_resource_alert_time['memory'] = current_time
                    self.logger.warning(f": {memory_info.percent:.1f}%")
                    self._add_event(f":  ({memory_info.percent:.1f}%)")
                    self._add_event(" ...")
                    self._optimize_memory_usage()
            elif memory_info.percent > 80:
                self.logger.debug(f": {memory_info.percent:.1f}%")
                self._light_memory_optimization()
            else:
                self.logger.debug(f": {memory_info.percent:.1f}%")
            
            if disk.percent > 90:
                last = self._last_resource_alert_time.get('disk', 0)
                if current_time - last > 60:
                    self._last_resource_alert_time['disk'] = current_time
                    self.logger.warning(f": {disk.percent:.1f}%")
                self._add_event(f":  ({disk.percent:.1f}%)")
            
            # 
            self.logger.debug(f" - CPU: {cpu_percent:.1f}%, : {process_memory:.0f}MB, : {disk.percent:.1f}%")
            
        except ImportError as e:
            self.logger.error(f"psutil: {e}")
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _optimize_memory_usage(self):
        """"""
        try:
            self.logger.info(" ...")
            
            # 
            if hasattr(self, 'data_cache') and self.data_cache:
                cache_size = len(self.data_cache)
                self.data_cache.clear()
                self.logger.info(f" : {cache_size} ")
            
            # 
            if hasattr(self, 'event_history') and len(self.event_history) > 100:
                # 100
                self.event_history = self.event_history[-100:]
                self.logger.info(" 100")
            
            # 不调用 gc.collect() — 它会阻塞 GIL 全局冻结 UI
            # Python 自动分代 GC 已足够，内存优化只清理缓存
            self.logger.info("跳过手动GC（避免STW卡顿），依赖Python自动GC")
            
            # 
            try:
                import psutil
                memory_info = psutil.virtual_memory()
                self.logger.info(f" : {memory_info.percent:.1f}%")
            except:
                pass
                
        except Exception as e:
            self.logger.error(f": {e}")

    def _light_memory_optimization(self):
        """"""
        try:
            self.logger.debug("轻量内存优化...")
            
            # 
            if hasattr(self, 'event_history') and len(self.event_history) > 200:
                # 200
                self.event_history = self.event_history[-200:]
                self.logger.debug("历史事件裁剪至200条")
                
        except Exception as e:
            self.logger.debug(f"轻量内存优化失败: {e}")
    
    def get_performance_report(self) -> dict:
        """"""
        try:
            report = {
                'timestamp': time.time(),
                'overall_performance': {},
                'data_sources': {},
                'system_resources': {},
                'recommendations': []
            }
            
            # 
            if hasattr(self, 'data_processing_stats'):
                total_sources = len(self.data_processing_stats)
                active_sources = sum(1 for stats in self.data_processing_stats.values() if stats['total_count'] > 0)
                
                report['overall_performance'] = {
                    'total_sources': total_sources,
                    'active_sources': active_sources,
                    'activation_rate': (active_sources / total_sources * 100) if total_sources > 0 else 0
                }
            
            # 
            for source_id, stats in self.data_processing_stats.items():
                if stats['total_count'] > 0:
                    avg_quality = sum(stats['quality_scores']) / len(stats['quality_scores']) if stats['quality_scores'] else 0
                    throughput = stats['total_count'] / max(1, (time.time() - stats['last_update']))
                    
                    report['data_sources'][source_id] = {
                        'total_processed': stats['total_count'],
                        'average_quality': avg_quality,
                        'throughput': throughput,
                        'data_types': list(stats['data_types'])
                    }
            
            # 
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=None)
                memory_info = psutil.virtual_memory()
                
                report['system_resources'] = {
                    'cpu_usage': cpu_percent,
                    'memory_usage': memory_info.percent,
                    'memory_available': memory_info.available / (1024 * 1024 * 1024)  # GB
                }
            except:
                report['system_resources'] = {'error': ''}
            
            # 
            if hasattr(self, 'data_processing_stats'):
                for source_id, stats in self.data_processing_stats.items():
                    if stats['quality_scores']:
                        avg_quality = sum(stats['quality_scores']) / len(stats['quality_scores'])
                        if avg_quality < 70:
                            report['recommendations'].append(f" {source_id} ")
            
            return report
            
        except Exception as e:
            self.logger.error(f": {e}")
            return {'error': str(e)}
    
    def check_data_source_health(self, source_id: str) -> dict:
        """"""
        try:
            health_report = {
                'source_id': source_id,
                'timestamp': time.time(),
                'status': 'unknown',
                'health_score': 0,
                'issues': [],
                'recommendations': []
            }
            
            # 
            if source_id not in self.data_sources:
                health_report['status'] = 'not_found'
                health_report['issues'].append('')
                return health_report
            
            # 
            connection_status = self._get_connection_status(source_id)
            if connection_status == 'connected':
                health_report['status'] = 'healthy'
                health_report['health_score'] += 30
            else:
                health_report['status'] = 'unhealthy'
                health_report['issues'].append('')
                health_report['health_score'] += 0
            
            # 
            if hasattr(self, 'data_processing_stats') and source_id in self.data_processing_stats:
                stats = self.data_processing_stats[source_id]
                
                # 
                if stats['total_count'] > 0:
                    health_report['health_score'] += 25
                    
                    # 
                    if stats['quality_scores']:
                        avg_quality = sum(stats['quality_scores']) / len(stats['quality_scores'])
                        if avg_quality >= 90:
                            health_report['health_score'] += 25
                        elif avg_quality >= 70:
                            health_report['health_score'] += 15
                        elif avg_quality >= 50:
                            health_report['health_score'] += 5
                        else:
                            health_report['issues'].append(f': {avg_quality:.1f}%')
                            health_report['recommendations'].append('')
                    
                    # 
                    if stats['total_time'] > 0:
                        avg_processing_time = stats['total_time'] / stats['total_count']
                        if avg_processing_time < 100:  # 100ms
                            health_report['health_score'] += 20
                        elif avg_processing_time < 500:  # 500ms
                            health_report['health_score'] += 10
                        else:
                            health_report['issues'].append(f': {avg_processing_time:.1f}ms/')
                            health_report['recommendations'].append('')
                else:
                    health_report['issues'].append('')
                    health_report['health_score'] += 0
            
            # 
            config = self.data_sources.get(source_id, {})
            if config.get('basic', {}).get('name'):
                health_report['health_score'] += 5
            if config.get('connection', {}).get('type'):
                health_report['health_score'] += 5
            if config.get('data_format', {}).get('format'):
                health_report['health_score'] += 5
            if config.get('data_format', {}).get('data_types'):
                health_report['health_score'] += 5
            
            # 
            if health_report['health_score'] < 50:
                health_report['recommendations'].append('')
            elif health_report['health_score'] < 80:
                health_report['recommendations'].append('')
            else:
                health_report['recommendations'].append('')
            
            return health_report
            
        except Exception as e:
            self.logger.error(f": {e}")
            return {
                'source_id': source_id,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_connection_status(self, source_id: str) -> str:
        """"""
        try:
            for row in range(self.sources_table.rowCount()):
                if row < self.sources_table.rowCount():
                    row_source_id = self.sources_table.item(row, 0).text()
                    if row_source_id == source_id:
                        status_item = self.sources_table.item(row, 4)
                        if status_item:
                            status_text = status_item.text()
                            if "" in status_text:
                                return "connected"
                            elif "" in status_text:
                                return "connecting"
                            elif "" in status_text:
                                return "failed"
                            else:
                                return "disconnected"
            return "unknown"
        except Exception as e:
            self.logger.error(f": {e}")
            return "unknown"
    
    def get_all_data_sources_health(self) -> dict:
        """"""
        try:
            health_report = {
                'timestamp': time.time(),
                'overall_health': 0,
                'data_sources': {},
                'summary': {
                    'total': 0,
                    'healthy': 0,
                    'unhealthy': 0,
                    'unknown': 0
                }
            }
            
            total_health = 0
            source_count = 0
            
            for source_id in self.data_sources.keys():
                health = self.check_data_source_health(source_id)
                health_report['data_sources'][source_id] = health
                
                if health['status'] == 'healthy':
                    health_report['summary']['healthy'] += 1
                elif health['status'] == 'unhealthy':
                    health_report['summary']['unhealthy'] += 1
                else:
                    health_report['summary']['unknown'] += 1
                
                total_health += health.get('health_score', 0)
                source_count += 1
            
            health_report['summary']['total'] = source_count
            
            if source_count > 0:
                health_report['overall_health'] = total_health / source_count
            
            return health_report
            
        except Exception as e:
            self.logger.error(f": {e}")
            return {'error': str(e)}
    
    def test_connections(self):
        """"""
        QMessageBox.information(self, "", "")
        self.logger.info("")
    
    def get_current_config(self) -> Dict[str, Any]:
        """"""
        config = {
            "sync_engine": {
                "sync_frequency": self.sync_frequency_spin.value(),
                "max_concurrent_sources": self.max_concurrent_spin.value(),
                "auto_recovery": self.auto_recovery_check.isChecked(),
                "recovery_timeout": self.recovery_timeout_spin.value(),
                "adaptive_sync": self.adaptive_sync_check.isChecked(),
                "adaptive_threshold": self.adaptive_threshold_spin.value(),
                "sync_strategy": self.sync_strategy_combo.currentText()
            },
            "time_alignment": {
                "sync_strategy": self.time_sync_strategy_combo.currentText(),
                "max_time_offset": self.max_time_offset_spin.value(),
                "quality_threshold": self.quality_threshold_spin.value(),
                "ntp_sync": self.ntp_sync_check.isChecked(),
                "ntp_servers": self.ntp_servers_edit.text().split(','),
                "ntp_sync_interval": self.ntp_sync_interval_spin.value()
            },
            "data_fusion": {
                "fusion_algorithm": self.fusion_algorithm_combo.currentText(),
                "quality_weight": self.quality_weight_spin.value(),
                "time_weight": self.time_weight_spin.value(),
                "adaptive_fusion": self.adaptive_fusion_check.isChecked(),
                "fusion_threshold": self.fusion_threshold_spin.value(),
                "max_fusion_delay": self.max_fusion_delay_spin.value()
            },
            "performance": {
                "monitor_interval": self.monitor_interval_spin.value(),
                "performance_threshold": self.performance_threshold_spin.value(),
                "performance_optimization": self.performance_optimization_check.isChecked(),
                "anomaly_threshold": self.anomaly_threshold_spin.value(),
                "anomaly_detection": self.anomaly_detection_check.isChecked()
            }
        }
        
        return config
    
    def apply_configuration(self, config: Dict[str, Any]):
        """"""
        try:
            # 
            if "sync_engine" in config:
                sync_engine = config["sync_engine"]
                self.sync_frequency_spin.setValue(sync_engine.get("sync_frequency", 100.0))
                self.max_concurrent_spin.setValue(sync_engine.get("max_concurrent_sources", 10))
                self.auto_recovery_check.setChecked(sync_engine.get("auto_recovery", True))
                self.recovery_timeout_spin.setValue(sync_engine.get("recovery_timeout", 30.0))
                self.adaptive_sync_check.setChecked(sync_engine.get("adaptive_sync", True))
                self.adaptive_threshold_spin.setValue(sync_engine.get("adaptive_threshold", 0.8))
                
                strategy = sync_engine.get("sync_strategy", "")
                index = self.sync_strategy_combo.findText(strategy)
                if index >= 0:
                    self.sync_strategy_combo.setCurrentIndex(index)
            
            # 
            if "time_alignment" in config:
                time_alignment = config["time_alignment"]
                strategy = time_alignment.get("sync_strategy", "")
                index = self.time_sync_strategy_combo.findText(strategy)
                if index >= 0:
                    self.time_sync_strategy_combo.setCurrentIndex(index)
                
                self.max_time_offset_spin.setValue(time_alignment.get("max_time_offset", 0.1))
                self.quality_threshold_spin.setValue(time_alignment.get("quality_threshold", 0.8))
                self.ntp_sync_check.setChecked(time_alignment.get("ntp_sync", True))
                self.ntp_servers_edit.setText(",".join(time_alignment.get("ntp_servers", ["pool.ntp.org"])))
                self.ntp_sync_interval_spin.setValue(time_alignment.get("ntp_sync_interval", 60.0))
            
            # 
            if "data_fusion" in config:
                data_fusion = config["data_fusion"]
                algorithm = data_fusion.get("fusion_algorithm", "")
                index = self.fusion_algorithm_combo.findText(algorithm)
                if index >= 0:
                    self.fusion_algorithm_combo.setCurrentIndex(index)
                
                self.quality_weight_spin.setValue(data_fusion.get("quality_weight", 0.7))
                self.time_weight_spin.setValue(data_fusion.get("time_weight", 0.3))
                self.adaptive_fusion_check.setChecked(data_fusion.get("adaptive_fusion", True))
                self.fusion_threshold_spin.setValue(data_fusion.get("fusion_threshold", 0.6))
                self.max_fusion_delay_spin.setValue(data_fusion.get("max_fusion_delay", 0.5))
            
            # 
            if "performance" in config:
                performance = config["performance"]
                self.monitor_interval_spin.setValue(performance.get("monitor_interval", 1.0))
                self.performance_threshold_spin.setValue(performance.get("performance_threshold", 0.8))
                self.performance_optimization_check.setChecked(performance.get("performance_optimization", True))
                self.anomaly_threshold_spin.setValue(performance.get("anomaly_threshold", 80))
                self.anomaly_detection_check.setChecked(performance.get("anomaly_detection", True))
            
            self.logger.info("")
        except Exception as e:
            self.logger.error(f": {e}")
    
    def apply_default_configuration(self):
        """"""
        default_config = {
            "sync_engine": {
                "sync_frequency": 100.0,
                "max_concurrent_sources": 10,
                "auto_recovery": True,
                "recovery_timeout": 30.0,
                "adaptive_sync": True,
                "adaptive_threshold": 0.8,
                "sync_strategy": ""
            },
            "time_alignment": {
                "sync_strategy": "",
                "max_time_offset": 0.1,
                "quality_threshold": 0.8,
                "ntp_sync": True,
                "ntp_servers": ["pool.ntp.org"],
                "ntp_sync_interval": 60.0
            },
            "data_fusion": {
                "fusion_algorithm": "",
                "quality_weight": 0.7,
                "time_weight": 0.3,
                "adaptive_fusion": True,
                "fusion_threshold": 0.6,
                "max_fusion_delay": 0.5
            },
            "performance": {
                "monitor_interval": 1.0,
                "performance_threshold": 0.8,
                "performance_optimization": True,
                "anomaly_threshold": 80,
                "anomaly_detection": True
            }
        }
        
        self.apply_configuration(default_config)
    
    # 
    
    def get_tab_name(self) -> str:
        """"""
        return ""
    
    def remove_data_source(self):
        """"""
        current_row = self.sources_table.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "", "",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.sources_table.removeRow(current_row)
                self._update_source_count()
                self.logger.info("")
        else:
            QMessageBox.warning(self, "", "")
    
    def refresh_sources(self):
        """"""
        try:
            # 
            if hasattr(self, 'sync_engine') and self.sync_engine:
                # ID
                current_source_ids = set(self.sync_engine.data_sources.keys())
                
                # 
                for row in range(self.sources_table.rowCount() - 1, -1, -1):
                    source_id_item = self.sources_table.item(row, 0)
                    if source_id_item:
                        source_id = source_id_item.text()
                        
                        # 
                        if source_id not in current_source_ids:
                            self.sources_table.removeRow(row)
                            self.logger.info(f": {source_id}")
                            continue
                        
                        # 
                        source_config = self.sync_engine.data_sources[source_id]
                        interface = source_config.get('interface')
                        
                        if interface:
                            # 
                            if hasattr(interface, 'is_connected'):
                                if callable(interface.is_connected):
                                    is_connected = interface.is_connected()
                                else:
                                    is_connected = interface.is_connected
                            else:
                                is_connected = False
                            
                            status = "" if is_connected else ""
                            self.sources_table.setItem(row, 3, QTableWidgetItem(status))
                            
                            # 
                            if hasattr(interface, 'get_sampling_rate'):
                                if callable(interface.get_sampling_rate):
                                    rate = interface.get_sampling_rate()
                                else:
                                    rate = interface.get_sampling_rate
                            else:
                                rate = 0
                            
                            data_rate = f"{rate} Hz" if rate > 0 else "0 Hz"
                            self.sources_table.setItem(row, 4, QTableWidgetItem(data_rate))
            
            # 
            self._update_source_count()
            self.update_overview_statistics()
            self.update_sync_status()
            
            self.logger.info("")
            
        except Exception as e:
            self.logger.error(f": {e}")
            # 
            self._update_source_count()
    
    def _update_source_count(self):
        """"""
        total_count = self.sources_table.rowCount()
        active_count = 0
        
        for row in range(total_count):
            status_item = self.sources_table.item(row, 4)  # 4
            if status_item and status_item.text() == "":
                active_count += 1
        
        # 
        if hasattr(self, 'total_sources_mini_label'):
            self.total_sources_mini_label.setText(str(total_count))
        if hasattr(self, 'connected_mini_label'):
            self.connected_mini_label.setText(str(active_count))
        if hasattr(self, 'disconnected_mini_label'):
            self.disconnected_mini_label.setText(str(total_count - active_count))

        if hasattr(self, 'sync_status_mini_label'):
            if active_count == 0:
                self.sync_status_mini_label.setText("离线")
            elif active_count == total_count:
                self.sync_status_mini_label.setText("全部在线")
            else:
                self.sync_status_mini_label.setText(f"{active_count}/{total_count}")
    
    def _update_operation_button(self, row, is_connected):
        """"""
        try:
            operation_widget = self.sources_table.cellWidget(row, 5)
            if operation_widget:
                # 
                for i in reversed(range(operation_widget.layout().count())):
                    child = operation_widget.layout().itemAt(i).widget()
                    if child:
                        child.deleteLater()
                
                # 
                if is_connected:
                    btn = QPushButton("")
                    btn.clicked.connect(partial(self._disconnect_data_source, row))
                else:
                    btn = QPushButton("")
                    btn.clicked.connect(partial(self._connect_data_source, row))
                
                btn.setMaximumWidth(60)
                operation_widget.layout().addWidget(btn)
                operation_widget.layout().addStretch()
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _add_event(self, message: str):
        """"""
        if hasattr(self, 'event_log'):
            timestamp = time.strftime("%H:%M:%S")
            self.event_log.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """"""
        # 
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        
        # 
        try:
            self.save_configuration()
        except:
            pass
        
        self.logger.info("")
        event.accept()
    
    def _create_event_log_tab(self):
        """"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 
        log_group = QGroupBox(" ")
        log_layout = QVBoxLayout(log_group)
        
        # 
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumHeight(200)
        log_layout.addWidget(self.event_log)
        
        # 
        log_btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton(" ")
        export_log_btn = QPushButton(" ")
        
        clear_log_btn.clicked.connect(self.clear_event_log)
        export_log_btn.clicked.connect(self.export_event_log)
        
        log_btn_layout.addWidget(clear_log_btn)
        log_btn_layout.addWidget(export_log_btn)
        log_btn_layout.addStretch()
        
        log_layout.addLayout(log_btn_layout)
        layout.addWidget(log_group)
        
        # 
        self._add_event("")
        self._add_event("")
        self._add_event("...")
        
        return tab
    
    def clear_event_log(self):
        """"""
        reply = QMessageBox.question(
            self, "", "",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.event_log.clear()
            self._add_event("")
            self.logger.info("")
    
    def export_event_log(self):
        """"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "", 
                f"event_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                " (*.txt);; (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.event_log.toPlainText())
                
                QMessageBox.information(self, "", f": {file_path}")
                self.logger.info(f": {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")
    
    def _create_advanced_config_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(12)

        batch_group = QGroupBox("批量同步")
        batch_group.setObjectName("panelGroup")
        batch_layout = QFormLayout(batch_group)
        batch_layout.setSpacing(8)

        self.batch_sync_check = QCheckBox("启用批量同步模式")
        self.batch_sync_check.setChecked(False)
        batch_layout.addRow("", self.batch_sync_check)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 10000)
        self.batch_size_spin.setValue(1000)
        self.batch_size_spin.setSuffix(" 条")
        batch_layout.addRow("批量大小:", self.batch_size_spin)

        self.batch_timeout_spin = QDoubleSpinBox()
        self.batch_timeout_spin.setRange(1.0, 300.0)
        self.batch_timeout_spin.setValue(30.0)
        self.batch_timeout_spin.setSuffix(" 秒")
        batch_layout.addRow("批量超时:", self.batch_timeout_spin)

        layout.addWidget(batch_group)

        fault_group = QGroupBox("容错机制")
        fault_group.setObjectName("panelGroup")
        fault_layout = QFormLayout(fault_group)
        fault_layout.setSpacing(8)

        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setValue(3)
        fault_layout.addRow("重试次数:", self.retry_count_spin)

        self.retry_delay_spin = QDoubleSpinBox()
        self.retry_delay_spin.setRange(0.1, 60.0)
        self.retry_delay_spin.setValue(1.0)
        self.retry_delay_spin.setSuffix(" 秒")
        fault_layout.addRow("重试延迟:", self.retry_delay_spin)

        self.circuit_breaker_check = QCheckBox("启用熔断保护机制")
        self.circuit_breaker_check.setChecked(True)
        fault_layout.addRow("", self.circuit_breaker_check)

        layout.addWidget(fault_group)

        perf_group = QGroupBox("性能调优")
        perf_group.setObjectName("panelGroup")
        perf_layout = QFormLayout(perf_group)
        perf_layout.setSpacing(8)

        self.thread_pool_size_spin = QSpinBox()
        self.thread_pool_size_spin.setRange(1, 32)
        self.thread_pool_size_spin.setValue(8)
        perf_layout.addRow("线程池大小:", self.thread_pool_size_spin)

        self.queue_size_spin = QSpinBox()
        self.queue_size_spin.setRange(100, 100000)
        self.queue_size_spin.setValue(10000)
        perf_layout.addRow("队列容量:", self.queue_size_spin)

        self.memory_limit_spin = QSpinBox()
        self.memory_limit_spin.setRange(100, 10000)
        self.memory_limit_spin.setValue(1000)
        self.memory_limit_spin.setSuffix(" MB")
        perf_layout.addRow("内存限制:", self.memory_limit_spin)

        layout.addWidget(perf_group)
        layout.addStretch()
        scroll.setWidget(scroll_widget)

        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        return tab
    
    def _create_monitoring_dashboard_tab(self):
        """"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 
        realtime_monitor_group = QGroupBox(" ")
        realtime_monitor_layout = QGridLayout(realtime_monitor_group)
        
        # 
        self.sync_rate_display_label = QLabel(": 0 Hz")
        self.sync_rate_display_label.setAlignment(Qt.AlignCenter)
        
        self.quality_display_label = QLabel(": 0%")
        self.quality_display_label.setAlignment(Qt.AlignCenter)
        
        self.latency_display_label = QLabel(": 0 ms")
        self.latency_display_label.setAlignment(Qt.AlignCenter)
        
        realtime_monitor_layout.addWidget(self.sync_rate_display_label, 0, 0)
        realtime_monitor_layout.addWidget(self.quality_display_label, 0, 1)
        realtime_monitor_layout.addWidget(self.latency_display_label, 0, 2)
        
        layout.addWidget(realtime_monitor_group)
        
        # 
        
        return tab
    
    def _create_help_documentation_tab(self):
        """"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 
        help_group = QGroupBox(" ")
        help_layout = QVBoxLayout(help_group)
        
        # 
        help_content = QTextEdit()
        help_content.setReadOnly(True)
        help_content.setHtml("""
        <h2></h2>
        
        <h3> </h3>
        <p>• MQTTSerialTCP/UDPFileDatabase</p>
        <p>• </p>
        <p>• </p>
        
        <h3> </h3>
        <p>• 0.001-1000 Hz</p>
        <p>• </p>
        <p>• </p>
        
        <h3>⏰ </h3>
        <p>• </p>
        <p>• NTP</p>
        <p>• </p>
        
        <h3> </h3>
        <p>• </p>
        <p>• </p>
        <p>• </p>
        
        <h3> </h3>
        <p>• </p>
        <p>• </p>
        <p>• </p>
        
        <h3> </h3>
        <p>• </p>
        <p>• </p>
        <p>• </p>
        """)
        
        help_layout.addWidget(help_content)
        layout.addWidget(help_group)
        
        return tab
    
    def _create_data_sources_tab(self):
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(12)

        link_summary = QFrame()
        link_summary.setObjectName("linkSummaryCard")
        link_summary_layout = QVBoxLayout(link_summary)
        link_summary_layout.setSpacing(10)

        title_row = QHBoxLayout()
        summary_title = QLabel("数据源链接状态")
        summary_title.setObjectName("linkSummaryTitle")
        title_row.addWidget(summary_title)
        title_row.addStretch()

        self.link_health_label = QLabel("未检测")
        self.link_health_label.setObjectName("linkHealthLabel")
        title_row.addWidget(self.link_health_label)
        link_summary_layout.addLayout(title_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)

        stat_items = [
            ("total_linked", "已链接", "0", "linkStatValueGreen"),
            ("total_unlinked", "未链接", "0", "linkStatValueGray"),
            ("total_error", "链接异常", "0", "linkStatValueRed"),
            ("link_rate", "链接率", "0%", "linkStatValue"),
        ]

        for obj_name, label_text, value, style_class in stat_items:
            stat_col = QVBoxLayout()
            stat_col.setSpacing(2)
            stat_val = QLabel(value)
            stat_val.setObjectName(style_class)
            setattr(self, f"{obj_name}_stat_label", stat_val)
            stat_col.addWidget(stat_val)
            stat_lbl = QLabel(label_text)
            stat_lbl.setObjectName("linkStatLabel")
            stat_col.addWidget(stat_lbl)
            stats_row.addLayout(stat_col)

        stats_row.addStretch()
        link_summary_layout.addLayout(stats_row)
        layout.addWidget(link_summary)

        sources_group = QGroupBox("数据源列表")
        sources_group.setObjectName("panelGroup")
        sources_layout = QVBoxLayout(sources_group)
        sources_layout.setSpacing(8)

        self.sources_table = QTableWidget()
        self.sources_table.setObjectName("syncSourcesTable")
        self.sources_table.setColumnCount(8)
        self.sources_table.setHorizontalHeaderLabels([
            "", "ID", "名称", "类型", "链接状态", "采样率", "延迟", "操作"
        ])

        header = self.sources_table.horizontalHeader()
        header.setObjectName("syncSourcesHeader")
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Fixed)

        self.sources_table.setColumnWidth(0, 36)
        self.sources_table.setColumnWidth(7, 200)

        self.sources_table.setAlternatingRowColors(True)
        self.sources_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sources_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sources_table.verticalHeader().setVisible(False)
        self.sources_table.itemSelectionChanged.connect(self._on_source_selection_changed)

        sources_layout.addWidget(self.sources_table)

        sources_btn_layout = QHBoxLayout()
        sources_btn_layout.setSpacing(8)

        link_all_btn = QPushButton("全部链接")
        link_all_btn.setObjectName("linkBtn")
        link_all_btn.clicked.connect(self._link_all_sources)
        sources_btn_layout.addWidget(link_all_btn)

        unlink_all_btn = QPushButton("全部断开")
        unlink_all_btn.setObjectName("unlinkBtn")
        unlink_all_btn.clicked.connect(self._unlink_all_sources)
        sources_btn_layout.addWidget(unlink_all_btn)

        sources_btn_layout.addStretch()

        add_source_btn = QPushButton("添加数据源")
        add_source_btn.setObjectName("btnOutline")
        add_source_btn.clicked.connect(self.add_data_source)
        sources_btn_layout.addWidget(add_source_btn)

        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setObjectName("btnGhost")
        refresh_btn.clicked.connect(self.refresh_sources)
        sources_btn_layout.addWidget(refresh_btn)

        import_btn = QPushButton("导入配置")
        import_btn.setObjectName("btnGhost")
        import_btn.clicked.connect(self.import_config)
        sources_btn_layout.addWidget(import_btn)

        sources_layout.addLayout(sources_btn_layout)
        layout.addWidget(sources_group)

        self.connection_config_card = QFrame()
        self.connection_config_card.setObjectName("connectionConfigCard")
        self.connection_config_card.setVisible(False)
        config_card_layout = QVBoxLayout(self.connection_config_card)
        config_card_layout.setSpacing(8)

        config_title_row = QHBoxLayout()
        config_title = QLabel("链接配置")
        config_title.setObjectName("connectionConfigTitle")
        config_title_row.addWidget(config_title)
        config_title_row.addStretch()

        self.config_source_name_label = QLabel("")
        self.config_source_name_label.setObjectName("tagLabelAccent")
        config_title_row.addWidget(self.config_source_name_label)
        config_card_layout.addLayout(config_title_row)

        config_form = QFormLayout()
        config_form.setSpacing(6)

        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems(["串口 (Serial)", "TCP/IP 网络", "UDP 数据报", "文件读取", "WebSocket", "MQTT 消息"])
        config_form.addRow("连接方式:", self.conn_type_combo)

        self.conn_address_edit = QLineEdit()
        self.conn_address_edit.setPlaceholderText("输入地址，如 COM3 或 192.168.1.100:8080")
        config_form.addRow("连接地址:", self.conn_address_edit)

        self.conn_baud_combo = QComboBox()
        self.conn_baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.conn_baud_combo.setCurrentText("115200")
        config_form.addRow("波特率:", self.conn_baud_combo)

        self.conn_timeout_spin = QDoubleSpinBox()
        self.conn_timeout_spin.setRange(0.5, 60.0)
        self.conn_timeout_spin.setValue(5.0)
        self.conn_timeout_spin.setSuffix(" 秒")
        config_form.addRow("超时时间:", self.conn_timeout_spin)

        self.auto_reconnect_check = QCheckBox("断线自动重连")
        self.auto_reconnect_check.setChecked(True)
        config_form.addRow("", self.auto_reconnect_check)

        config_card_layout.addLayout(config_form)

        config_btn_row = QHBoxLayout()
        config_btn_row.setSpacing(8)

        test_conn_btn = QPushButton("测试链接")
        test_conn_btn.setObjectName("testLinkBtn")
        test_conn_btn.clicked.connect(self._test_selected_connection)
        config_btn_row.addWidget(test_conn_btn)

        apply_conn_btn = QPushButton("应用链接")
        apply_conn_btn.setObjectName("linkBtn")
        apply_conn_btn.clicked.connect(self._apply_selected_connection)
        config_btn_row.addWidget(apply_conn_btn)

        disconnect_btn = QPushButton("断开链接")
        disconnect_btn.setObjectName("unlinkBtn")
        disconnect_btn.clicked.connect(self._disconnect_selected_source)
        config_btn_row.addWidget(disconnect_btn)

        config_btn_row.addStretch()
        config_card_layout.addLayout(config_btn_row)

        layout.addWidget(self.connection_config_card)

        layout.addStretch()
        scroll.setWidget(scroll_widget)

        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        return tab
    
    def _update_tab_from_unified(self, data_sources):
        # 
        self._update_overview_labels(data_sources)
        self._populate_sources_table(data_sources)
        self.logger.info("")
        
    def _update_overview_labels(self, data_sources):
        try:
            total = len(data_sources)
            linked = sum(1 for s in data_sources.values() if s.get('link_status') == 'linked')
            unlinked = sum(1 for s in data_sources.values() if s.get('link_status') in ('unlinked', None, ''))
            error_count = sum(1 for s in data_sources.values() if s.get('link_status') == 'error')
            link_rate = f"{int(linked / total * 100)}%" if total > 0 else "0%"

            if hasattr(self, 'total_linked_stat_label'):
                self.total_linked_stat_label.setText(str(linked))
            if hasattr(self, 'total_unlinked_stat_label'):
                self.total_unlinked_stat_label.setText(str(unlinked))
            if hasattr(self, 'total_error_stat_label'):
                self.total_error_stat_label.setText(str(error_count))
            if hasattr(self, 'link_rate_stat_label'):
                self.link_rate_stat_label.setText(link_rate)

            if error_count > 0:
                self.link_health_label.setText("异常")
                self.link_health_label.setObjectName("linkHealthBad")
                self.link_health_label.style().unpolish(self.link_health_label)
                self.link_health_label.style().polish(self.link_health_label)
            elif linked == total and total > 0:
                self.link_health_label.setText("良好")
                self.link_health_label.setObjectName("linkHealthGood")
                self.link_health_label.style().unpolish(self.link_health_label)
                self.link_health_label.style().polish(self.link_health_label)
            elif linked > 0:
                self.link_health_label.setText("部分链接")
                self.link_health_label.setObjectName("linkHealthWarning")
                self.link_health_label.style().unpolish(self.link_health_label)
                self.link_health_label.style().polish(self.link_health_label)
            else:
                self.link_health_label.setText("未链接")
                self.link_health_label.setObjectName("linkHealthLabel")
                self.link_health_label.style().unpolish(self.link_health_label)
                self.link_health_label.style().polish(self.link_health_label)

        except Exception as e:
            self.logger.error(f"更新概览标签失败: {e}")
    
    def _populate_sources_table(self, data_sources=None):
        try:
            if not hasattr(self, 'sources_table'):
                self.logger.warning("sources_table 未初始化")
                return

            self.sources_table.setRowCount(0)

            if not data_sources or len(data_sources) == 0:
                self.logger.info("无数据源，使用示例数据")
                sample_sources = {
                    'DS_001': {
                        'basic': {'name': 'IMU传感器', 'type': 'IMU', 'sampling_rate': 100},
                        'link_status': 'linked',
                        'connection': {'device_path': '/dev/ttyUSB0', 'baud_rate': 115200},
                        'latency': '2.3ms'
                    },
                    'DS_002': {
                        'basic': {'name': 'CNAP血压', 'type': 'CNAP', 'sampling_rate': 50},
                        'link_status': 'unlinked',
                        'connection': {'device_path': '/dev/ttyUSB1', 'baud_rate': 9600},
                        'latency': '--'
                    },
                    'DS_003': {
                        'basic': {'name': '心电采集', 'type': 'ECG', 'sampling_rate': 200},
                        'link_status': 'linked',
                        'connection': {'device_path': '/dev/ttyUSB2', 'baud_rate': 115200},
                        'latency': '1.8ms'
                    },
                    'DS_004': {
                        'basic': {'name': '文件数据源', 'type': 'File', 'sampling_rate': 10},
                        'link_status': 'error',
                        'connection': {'file_path': 'test/data/sample.txt', 'data_format': 'txt'},
                        'latency': '--'
                    },
                }
                data_sources = sample_sources

            for source_id, config in data_sources.items():
                row = self.sources_table.rowCount()
                self.sources_table.insertRow(row)

                name = config.get('basic', {}).get('name', source_id)
                source_type = config.get('basic', {}).get('type', 'Unknown')
                link_status = config.get('link_status', 'unlinked')
                sampling_rate = config.get('basic', {}).get('sampling_rate', 'N/A')
                latency = config.get('latency', '--')

                indicator_widget = QWidget()
                indicator_layout = QHBoxLayout(indicator_widget)
                indicator_layout.setContentsMargins(10, 0, 0, 0)
                indicator_layout.setAlignment(Qt.AlignCenter)
                indicator_dot = QFrame()
                if link_status == 'linked':
                    indicator_dot.setObjectName("linkIndicatorGreen")
                elif link_status == 'error':
                    indicator_dot.setObjectName("linkIndicatorRed")
                elif link_status == 'connecting':
                    indicator_dot.setObjectName("linkIndicatorYellow")
                else:
                    indicator_dot.setObjectName("linkIndicatorGray")
                indicator_layout.addWidget(indicator_dot)
                self.sources_table.setCellWidget(row, 0, indicator_widget)

                self.sources_table.setItem(row, 1, QTableWidgetItem(source_id))
                self.sources_table.setItem(row, 2, QTableWidgetItem(name))
                self.sources_table.setItem(row, 3, QTableWidgetItem(source_type))

                link_status_item = QTableWidgetItem(link_status)
                if link_status == 'linked':
                    link_status_item.setText("已链接")
                    link_status_item.setForeground(QColor(52, 211, 153))
                elif link_status == 'error':
                    link_status_item.setText("链接异常")
                    link_status_item.setForeground(QColor(248, 113, 113))
                elif link_status == 'connecting':
                    link_status_item.setText("链接中...")
                    link_status_item.setForeground(QColor(251, 191, 36))
                else:
                    link_status_item.setText("未链接")
                    link_status_item.setForeground(QColor(95, 101, 112))
                self.sources_table.setItem(row, 4, link_status_item)

                rate_text = f"{sampling_rate} Hz" if sampling_rate != 'N/A' else 'N/A'
                self.sources_table.setItem(row, 5, QTableWidgetItem(rate_text))
                self.sources_table.setItem(row, 6, QTableWidgetItem(latency))

                operation_widget = QWidget()
                operation_layout = QHBoxLayout(operation_widget)
                operation_layout.setContentsMargins(4, 2, 4, 2)
                operation_layout.setSpacing(4)

                if link_status == 'linked':
                    unlink_btn = QPushButton("断开")
                    unlink_btn.setObjectName("unlinkBtn")
                    unlink_btn.clicked.connect(lambda checked, r=row: self._disconnect_source_at_row(r))
                    operation_layout.addWidget(unlink_btn)
                else:
                    link_btn = QPushButton("链接")
                    link_btn.setObjectName("linkBtn")
                    link_btn.clicked.connect(lambda checked, r=row: self._connect_source_at_row(r))
                    operation_layout.addWidget(link_btn)

                test_btn = QPushButton("测试")
                test_btn.setObjectName("testLinkBtn")
                test_btn.clicked.connect(lambda checked, r=row: self._test_source_at_row(r))
                operation_layout.addWidget(test_btn)

                self.sources_table.setCellWidget(row, 7, operation_widget)

            self.logger.info(f"已填充 {len(data_sources)} 个数据源")
            self._update_overview_labels(data_sources)

        except Exception as e:
            self.logger.error(f"填充数据源表格失败: {e}")
    
    def _on_source_selection_changed(self):
        selected_rows = set()
        for item in self.sources_table.selectedItems():
            selected_rows.add(item.row())
        if len(selected_rows) == 1:
            row = list(selected_rows)[0]
            source_id = self.sources_table.item(row, 1).text() if self.sources_table.item(row, 1) else ""
            source_name = self.sources_table.item(row, 2).text() if self.sources_table.item(row, 2) else ""
            self.config_source_name_label.setText(source_name)
            self.connection_config_card.setVisible(True)
            self._selected_source_row = row
            self._selected_source_id = source_id
        else:
            self.connection_config_card.setVisible(False)
            self._selected_source_row = None
            self._selected_source_id = None

    def _link_all_sources(self):
        self.logger.info("全部链接数据源")
        for row in range(self.sources_table.rowCount()):
            self._update_source_link_status(row, 'linked')
        self._refresh_data_sources_display()

    def _unlink_all_sources(self):
        self.logger.info("全部断开数据源")
        for row in range(self.sources_table.rowCount()):
            self._update_source_link_status(row, 'unlinked')
        self._refresh_data_sources_display()

    def _connect_source_at_row(self, row):
        self.logger.info(f"链接第 {row} 行数据源")
        self._update_source_link_status(row, 'linked')
        self._refresh_data_sources_display()

    def _disconnect_source_at_row(self, row):
        self.logger.info(f"断开第 {row} 行数据源")
        self._update_source_link_status(row, 'unlinked')
        self._refresh_data_sources_display()

    def _test_source_at_row(self, row):
        source_id = self.sources_table.item(row, 1).text() if self.sources_table.item(row, 1) else f"Row{row}"
        self.logger.info(f"测试第 {row} 行数据源链接: {source_id}")
        self._update_source_link_status(row, 'connecting')
        QTimer.singleShot(1500, lambda r=row: self._finish_test_source(r))

    def _finish_test_source(self, row):
        new_status = 'linked'
        self._update_source_link_status(row, new_status)
        self._refresh_data_sources_display()

    def _update_source_link_status(self, row, status):
        source_id = self.sources_table.item(row, 1).text() if self.sources_table.item(row, 1) else f"DS_{row}"
        if source_id in self.data_sources:
            self.data_sources[source_id]['link_status'] = status
        self.logger.info(f"数据源 {source_id} 链接状态更新为: {status}")

    def _test_selected_connection(self):
        if hasattr(self, '_selected_source_row') and self._selected_source_row is not None:
            self._test_source_at_row(self._selected_source_row)

    def _apply_selected_connection(self):
        if hasattr(self, '_selected_source_row') and self._selected_source_row is not None:
            self._connect_source_at_row(self._selected_source_row)

    def _disconnect_selected_source(self):
        if hasattr(self, '_selected_source_row') and self._selected_source_row is not None:
            self._disconnect_source_at_row(self._selected_source_row)

    def _add_data_type_association(self):
        """"""
        try:
            # 
            selected_types = []
            for internal_name, checkbox in self.data_type_checkboxes.items():
                if checkbox.isChecked():
                    selected_types.append(internal_name)
            
            if not selected_types:
                QMessageBox.warning(self, "", "")
                return
            
            # 
            current_row = self.association_table.rowCount()
            self.association_table.insertRow(current_row)
            
            # 
            data_type_combo = QComboBox()
            data_type_combo.addItems(selected_types)
            self.association_table.setCellWidget(current_row, 0, data_type_combo)
            
            # 
            source_combo = QComboBox()
            source_combo.addItems(["COM3", "TCP:8080", "MQTT:1883", ""])
            self.association_table.setCellWidget(current_row, 1, source_combo)
            
            # 
            sample_rate_spin = QSpinBox()
            sample_rate_spin.setRange(1, 10000)
            sample_rate_spin.setValue(100)
            sample_rate_spin.setSuffix(" Hz")
            self.association_table.setCellWidget(current_row, 2, sample_rate_spin)
            
            # 
            operation_widget = None #  operation_widget 
            operation_widget = QWidget()
            operation_layout = QHBoxLayout(operation_widget)
            operation_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_btn = QPushButton("")
            edit_btn.setMaximumWidth(30)
            from functools import partial
            edit_btn.clicked.connect(partial(self._edit_data_type_association, current_row))
            
            delete_btn = QPushButton("")
            delete_btn.setMaximumWidth(30)
            delete_btn.clicked.connect(partial(self._delete_data_type_association, current_row))
            
            operation_layout.addWidget(edit_btn)
            operation_layout.addWidget(delete_btn)
            operation_layout.addStretch()
            
            self.association_table.setCellWidget(current_row, 3, operation_widget)
            
            self.logger.info(f":  {current_row}")
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _edit_data_type_association(self, row):
        """"""
        try:
            QMessageBox.information(self, "", f" {row + 1} ")
            self.logger.info(f":  {row}")
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _delete_data_type_association(self, row):
        """"""
        try:
            reply = QMessageBox.question(
                self, "", 
                f" {row + 1} ",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.association_table.removeRow(row)
                self.logger.info(f":  {row}")
        except Exception as e:
            self.logger.error(f": {e}")
    
    def update_overview_statistics(self):
        """"""
        try:
            # 
            total_sources = self.sources_table.rowCount()
            connected_sources = 0
            disconnected_sources = 0
            
            for row in range(total_sources):
                status_item = self.sources_table.item(row, 3)  # 4
                if status_item:
                    status_text = status_item.text()
                    if "" in status_text or "" in status_text:
                        connected_sources += 1
                    else:
                        disconnected_sources += 1
            
            # 
            if hasattr(self, 'total_sources_mini_label'):
                self.total_sources_mini_label.setText(str(total_sources))
            if hasattr(self, 'connected_mini_label'):
                self.connected_mini_label.setText(str(connected_sources))
            if hasattr(self, 'disconnected_mini_label'):
                self.disconnected_mini_label.setText(str(disconnected_sources))

            if hasattr(self, 'sync_status_mini_label'):
                if connected_sources == 0:
                    self.sync_status_mini_label.setText("离线")
                elif connected_sources == total_sources:
                    self.sync_status_mini_label.setText("全部在线")
                else:
                    self.sync_status_mini_label.setText(f"{connected_sources}/{total_sources}")

            if hasattr(self, 'data_quality_mini_label'):
                if total_sources == 0:
                    self.data_quality_mini_label.setText("0%")
                else:
                    quality_percent = int((connected_sources / total_sources) * 100)
                    self.data_quality_mini_label.setText(f"{quality_percent}%")

            if hasattr(self, 'avg_latency_mini_label'):
                if connected_sources > 0:
                    base_latency = 5
                    source_latency = connected_sources * 2
                    total_latency = base_latency + source_latency
                    self.avg_latency_mini_label.setText(f"{total_latency}ms")
                else:
                    self.avg_latency_mini_label.setText("0ms")
            
            # 
            self._update_status_info(total_sources, connected_sources)
            
            self.logger.info(f": ={total_sources}, ={connected_sources}, ={disconnected_sources}")
            
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _update_status_info(self, total_sources: int, connected_sources: int):
        """"""
        try:
            if hasattr(self, 'status_info_label'):
                if total_sources == 0:
                    status_text = " "
                elif connected_sources == total_sources:
                    status_text = f"🟢  - {connected_sources}/{total_sources}"
                elif connected_sources > 0:
                    status_text = f"🟡  - {connected_sources}/{total_sources}"
                else:
                    status_text = " "
                
                self.status_info_label.setText(status_text)
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _create_config_widget(self):
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)

        self.config_tabs = QTabWidget()
        config_layout.addWidget(self.config_tabs)

        data_sources_tab = self._create_data_sources_tab()
        self.config_tabs.addTab(data_sources_tab, "数据源管理")

        sync_engine_tab = self._create_sync_engine_tab()
        self.config_tabs.addTab(sync_engine_tab, "同步引擎")

        data_fusion_tab = self._create_data_fusion_tab()
        self.config_tabs.addTab(data_fusion_tab, "数据融合")

        performance_tab = self._create_performance_tab()
        self.config_tabs.addTab(performance_tab, "性能监控")

        advanced_tab = self._create_advanced_config_tab()
        self.config_tabs.addTab(advanced_tab, "高级配置")

        return config_widget
    
    def connect_signals(self):
        """"""
        # 
        if hasattr(self, 'sync_frequency_spin'):
            self.sync_frequency_spin.valueChanged.connect(self._on_config_changed)
        if hasattr(self, 'max_concurrent_spin'):
            self.max_concurrent_spin.valueChanged.connect(self._on_config_changed)
        if hasattr(self, 'auto_recovery_check'):
            self.auto_recovery_check.toggled.connect(self._on_config_changed)
        if hasattr(self, 'adaptive_sync_check'):
            self.adaptive_sync_check.toggled.connect(self._on_config_changed)
        if hasattr(self, 'fusion_algorithm_combo'):
            self.fusion_algorithm_combo.currentTextChanged.connect(self._on_fusion_algorithm_changed)
        
        # 
        # 
        
        # 
        if hasattr(self, 'batch_sync_check'):
            self.batch_sync_check.toggled.connect(self._on_config_changed)
        if hasattr(self, 'batch_size_spin'):
            self.batch_size_spin.valueChanged.connect(self._on_config_changed)
        if hasattr(self, 'circuit_breaker_check'):
            self.circuit_breaker_check.toggled.connect(self._on_config_changed)
    
    def update_sync_status(self):
        """100%"""
        try:
            if self.sync_engine and hasattr(self.sync_engine, 'get_sync_status'):
                sync_status = self.sync_engine.get_sync_status()
                if not sync_status:  # 
                    self._update_ui_with_default_status()  # 
                else:
                    self._update_ui_with_real_status(sync_status)
            else:
                self._update_ui_with_data_source_status()
        except Exception as e:
            self.logger.error(f": {e}")
            self._update_ui_with_fallback_status()
    
    def _update_ui_with_real_status(self, sync_status: dict):
        try:
            overall_status = sync_status.get('overall_status', 'unknown')
            sync_rate = sync_status.get('sync_rate', 0)
            quality = sync_status.get('quality', 0)
            latency = sync_status.get('latency', 0)
            active_sources = sync_status.get('active_sources', 0)
            total_sources = sync_status.get('total_sources', 0)

            if hasattr(self, 'sync_rate_card_label'):
                self.sync_rate_card_label.setText(f"{sync_rate} Hz")
            if hasattr(self, 'sync_quality_card_label'):
                self.sync_quality_card_label.setText(f"{quality}%")
            if hasattr(self, 'active_sources_card_label'):
                self.active_sources_card_label.setText(f"{active_sources}/{total_sources}")
            if hasattr(self, 'sync_latency_card_label'):
                self.sync_latency_card_label.setText(f"{latency} ms")

            if hasattr(self, 'quick_status_label'):
                status_map = {
                    "running": ("运行中", "statusBadge"),
                    "stopped": ("已停止", "statusBadgeMuted"),
                    "paused": ("已暂停", "statusBadgeWarning"),
                    "error": ("异常", "statusBadgeDanger"),
                    "unknown": ("待机", "statusBadgeMuted")
                }
                text, style = status_map.get(overall_status, ("待机", "statusBadgeMuted"))
                self.quick_status_label.setText(f"状态: {text}")
                self.quick_status_label.setObjectName(style)
                self.quick_status_label.style().unpolish(self.quick_status_label)
                self.quick_status_label.style().polish(self.quick_status_label)

            self.sync_status_updated.emit({
                "status": overall_status,
                "timestamp": time.time(),
                "sync_rate": sync_rate,
                "quality": quality,
                "active_sources": active_sources,
                "total_sources": total_sources
            })

        except Exception as e:
            self.logger.error(f"UI: {e}")
            self._update_ui_with_fallback_status()
    
    def _update_ui_with_data_source_status(self):
        try:
            total_sources = self.sources_table.rowCount()
            connected_sources = 0
            active_sources = 0

            for row in range(total_sources):
                if row < self.sources_table.rowCount():
                    status_item = self.sources_table.item(row, 4)
                    if status_item and "已连接" in status_item.text():
                        connected_sources += 1
                        rate_item = self.sources_table.item(row, 5)
                        if rate_item and rate_item.text() != "0 Hz":
                            active_sources += 1

            sync_rate = self._calculate_real_sync_rate()
            quality = self._calculate_real_quality(connected_sources, total_sources)
            latency = self._calculate_real_latency()

            if hasattr(self, 'sync_rate_card_label'):
                self.sync_rate_card_label.setText(f"{sync_rate} Hz")
            if hasattr(self, 'sync_quality_card_label'):
                self.sync_quality_card_label.setText(f"{quality}%")
            if hasattr(self, 'active_sources_card_label'):
                self.active_sources_card_label.setText(f"{connected_sources}/{total_sources}")
            if hasattr(self, 'sync_latency_card_label'):
                self.sync_latency_card_label.setText(f"{latency} ms")

            if hasattr(self, 'quick_status_label'):
                if connected_sources == 0:
                    text, style = "无连接", "statusBadgeDanger"
                elif active_sources > 0:
                    text, style = "运行中", "statusBadge"
                else:
                    text, style = "待机", "statusBadgeWarning"
                self.quick_status_label.setText(f"状态: {text}")
                self.quick_status_label.setObjectName(style)
                self.quick_status_label.style().unpolish(self.quick_status_label)
                self.quick_status_label.style().polish(self.quick_status_label)

        except Exception as e:
            self.logger.error(f"UI: {e}")
            self._update_ui_with_fallback_status()
    
    def _update_ui_with_fallback_status(self):
        """UI"""
        try:
            if hasattr(self, 'quick_status_label'):
                self.quick_status_label.setText(" : ")
                
        except Exception as e:
            self.logger.error(f": {e}")
    
    def _get_quick_status_text(self, status: str) -> str:
        """"""
        status_mapping = {
            "running": "",
            "stopped": "",
            "paused": "",
            "error": "",
            "unknown": ""
        }
        return status_mapping.get(status, "")
    
    def _calculate_real_sync_rate(self) -> int:
        """"""
        try:
            total_rate = 0
            count = 0
            
            for row in range(self.sources_table.rowCount()):
                if row < self.sources_table.rowCount():
                    rate_item = self.sources_table.item(row, 5)
                    if rate_item and rate_item.text() != "0 Hz":
                        try:
                            rate_text = rate_item.text()
                            rate_value = int(rate_text.replace(" Hz", ""))
                            total_rate += rate_value
                            count += 1
                        except:
                            pass
            
            return total_rate if count > 0 else 0
            
        except Exception as e:
            self.logger.error(f": {e}")
            return 0
    
    def _calculate_real_quality(self, connected_sources: int, total_sources: int) -> int:
        """"""
        try:
            if total_sources == 0:
                return 0
            
            # 
            base_quality = (connected_sources / total_sources) * 100
            
            # 
            health_bonus = 0
            for row in range(self.sources_table.rowCount()):
                if row < self.sources_table.rowCount():
                    status_item = self.sources_table.item(row, 4)
                    if status_item and "" in status_item.text():
                        health_bonus += 5  # 5%
            
            final_quality = min(100, base_quality + health_bonus)
            return int(final_quality)
            
        except Exception as e:
            self.logger.error(f": {e}")
            return 0
    
    def _calculate_real_latency(self) -> int:
        """"""
        try:
            # 
            total_sources = len(self.data_sources)
            connected_sources = 0
            
            for row in range(self.sources_table.rowCount()):
                if row < self.sources_table.rowCount():
                    status_item = self.sources_table.item(row, 4)
                    if status_item and "" in status_item.text():
                        connected_sources += 1
            
            #  + 
            base_latency = 5  # 5ms
            source_latency = connected_sources * 2  # 2ms
            
            return base_latency + source_latency
            
        except Exception as e:
            self.logger.error(f": {e}")
            return 10
    
    def _update_status_table_with_real_data(self, sync_status: dict):
        """"""
        try:
            if not hasattr(self, 'status_table'):
                return
            
            # 
            import psutil
            import os
            
            # 
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)
            
            # 
            network_latency = self._calculate_real_latency()
            
            # 
            total_sources = self.sources_table.rowCount()
            active_sources = 0
            for row in range(total_sources):
                status_item = self.sources_table.item(row, 4)
                if status_item and "" in status_item.text():
                    rate_item = self.sources_table.item(row, 5)
                    if rate_item and rate_item.text() != "0 Hz":
                        active_sources += 1
            
            status_data = [
                ("", str(total_sources), ""),
                ("", str(active_sources), ""),
                ("", f"{sync_status.get('sync_rate', 0)} Hz", ""),
                ("", "0.001 ms", ""),  # 
                ("", f"{sync_status.get('quality', 0)}%", ""),
                ("", "", ""),
                ("", f"{cpu_percent:.1f}%", "" if cpu_percent < 80 else ""),
                ("", f"{memory_mb:.0f} MB", "" if memory_mb < 1000 else ""),
                ("", f"{network_latency} ms", "" if network_latency < 50 else "")
            ]
            
            # 
            for i, (metric, value, status) in enumerate(status_data):
                if i < self.status_table.rowCount():
                    self.status_table.setItem(i, 1, QTableWidgetItem(value))
                    
                    # 
                    status_item = QTableWidgetItem(status)
                    if status == "":
                        status_item.setBackground(QColor("#3d3520"))
                        status_item.setForeground(QColor("#fbbf24"))
                    else:
                        status_item.setBackground(QColor("#1a3a2a"))
                        status_item.setForeground(QColor("#34d399"))
                    
                    self.status_table.setItem(i, 2, status_item)
                    
        except Exception as e:
            self.logger.error(f": {e}")
    
    def save_config(self):
        """"""
        try:
            config_data = self._collect_current_config()
            
            # 
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "", 
                "multi_source_sync_config.json",
                "JSON (*.json)"
            )
            
            if file_path:
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                
                self._add_event(f": {file_path}")
                self.config_changed.emit(config_data)
                return True
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def load_config(self):
        """"""
        try:
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "", 
                "",
                "JSON (*.json)"
            )
            
            if file_path:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                self._apply_config(config_data)
                self._add_event(f": {file_path}")
                self.config_changed.emit(config_data)
                return True
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def export_config(self):
        """"""
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            
            # 
            format_choice, ok = QMessageBox.question(
                self,
                "",
                ":\n\nJSON - \nYAML - \nXML - ",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if format_choice == QMessageBox.StandardButton.Cancel:
                return False
            
            config_data = self._collect_current_config()
            
            if format_choice == QMessageBox.StandardButton.Yes:  # JSON
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "JSON", "config.json", "JSON (*.json)"
                )
                if file_path:
                    import json
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
            else:  # YAML
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "YAML", "config.yaml", "YAML (*.yaml)"
                )
                if file_path:
                    try:
                        import yaml
                        with open(file_path, 'w', encoding='utf-8') as f:
                            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                    except ImportError:
                        # yamlJSON
                        import json
                        with open(file_path.replace('.yaml', '.json'), 'w', encoding='utf-8') as f:
                            json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            if file_path:
                self._add_event(f": {file_path}")
                return True
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def import_config(self):
        """"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "", 
                "",
                " (*.json *.yaml *.xml);;JSON (*.json);;YAML (*.yaml);;XML (*.xml)"
            )
            
            if file_path:
                config_data = None
                
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    try:
                        import yaml
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = yaml.safe_load(f)
                    except ImportError:
                        self._add_event("YAMLYAML")
                        return False
                elif file_path.endswith('.xml'):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(file_path)
                        root = tree.getroot()
                        config_data = self._xml_to_dict(root)
                    except Exception as e:
                        self._add_event(f"XML: {str(e)}")
                        return False
                
                if config_data:
                    self._apply_config(config_data)
                    self._add_event(f": {file_path}")
                    self.config_changed.emit(config_data)
                    return True
                
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def _collect_current_config(self):
        """"""
        try:
            # 
            from core.core.multi_source_sync.data_source_config_manager import DataSourceConfigManager
            config_manager = DataSourceConfigManager()
            
            config = {
                'data_sources': config_manager.get_all_data_sources(),
                'global_settings': config_manager.get_global_settings(),
                'file_paths': config_manager.config_data.get('file_paths', {}),
                'timestamp': time.time(),
                'version': '1.0'
            }
            
            self.logger.info(" ")
            return config
            
        except Exception as e:
            self.logger.error(f" : {e}")
            # 
            return {
                'data_sources': {},
                'global_settings': {},
                'file_paths': {},
                'timestamp': time.time(),
                'version': '1.0',
                'error': str(e)
            }
    
    def _apply_config(self, config_data):
        """UI"""
        try:
            if not config_data:
                self.logger.warning(" ")
                return False
            
            # 
            if 'data_sources' not in config_data:
                self.logger.error(" data_sources")
                return False
            
            # 
            try:
                from core.core.multi_source_sync.data_source_config_manager import DataSourceConfigManager
                config_manager = DataSourceConfigManager()
                
                # 
                if 'data_sources' in config_data:
                    config_manager.config_data['data_sources'] = config_data['data_sources']
                
                if 'global_settings' in config_data:
                    config_manager.config_data['global_settings'] = config_data['global_settings']
                
                if 'file_paths' in config_data:
                    config_manager.config_data['file_paths'] = config_data['file_paths']
                
                # 
                config_manager._save_config()
                
                # UI
                if hasattr(self, '_refresh_data_sources_display'):
                    self._refresh_data_sources_display()
                
                self.logger.info(" ")
                return True
                
            except Exception as e:
                self.logger.error(f" : {e}")
                return False
                    
        except Exception as e:
            self.logger.error(f" : {e}")
            return False
    
    def _xml_to_dict(self, element):
        """XML"""
        result = {}
        for child in element:
            if len(child) == 0:
                result[child.tag] = child.text
            else:
                result[child.tag] = self._xml_to_dict(child)
        return result
    
    def _refresh_data_sources_display(self):
        """"""
        try:
            # 
            try:
                from core.core.multi_source_sync.data_source_config_manager import DataSourceConfigManager
                config_manager = DataSourceConfigManager()
                all_sources = config_manager.get_all_data_sources()
                
                self.logger.info(f": {all_sources}, : {len(all_sources)}")
                
            except Exception as inner_e:
                self.logger.warning(f": {inner_e}")
                # UI
                all_sources = {
                    'demo_source_1': {
                        'basic': {
                            'name': '1',
                            'type': 'IMU',
                            'sampling_rate': 100
                        },
                        'status': ''
                    },
                    'demo_source_2': {
                        'basic': {
                            'name': '2',
                            'type': 'GPS',
                            'sampling_rate': 50
                        },
                        'status': ''
                    }
                }
            
            # 
            self.logger.info(f" sources_table : {hasattr(self, 'sources_table')}")
            if hasattr(self, 'sources_table'):
                self.logger.info(" _update_sources_table ...")
                self._update_sources_table(all_sources)
            
            # 
            if hasattr(self, 'quick_status_label'):
                if all_sources:
                    self.quick_status_label.setText(f" :  {len(all_sources)} ")
                else:
                    self.quick_status_label.setText(" : ")
            
            self.logger.info(f" ")
            
        except Exception as e:
            self.logger.error(f" : {e}")
    
    def _update_sources_table(self, data_sources):
        """"""
        try:
            self.logger.info(f": {len(data_sources) if data_sources else 0}")
            self.logger.info(f": {data_sources}")
            operation_widget = None # for operation_widget
            if not hasattr(self, 'sources_table'):
                return
            
            # 
            self.sources_table.setRowCount(0)

            if not data_sources:
                self._update_ui_with_default_status()
                self.logger.warning("")
                return
            
            # 
            for source_id, config in data_sources.items():
                row = self.sources_table.rowCount()
                self.sources_table.insertRow(row)
                
                # 
                self.sources_table.setItem(row, 0, QTableWidgetItem(source_id))
                self.sources_table.setItem(row, 1, QTableWidgetItem(config.get('basic', {}).get('name', 'N/A')))
                self.sources_table.setItem(row, 2, QTableWidgetItem(config.get('basic', {}).get('type', 'N/A')))
                self.sources_table.setItem(row, 3, QTableWidgetItem(str(config.get('basic', {}).get('sampling_rate', 'N/A'))))
                self.sources_table.setItem(row, 4, QTableWidgetItem(""))
                self.sources_table.setItem(row, 5, QTableWidgetItem(""))
                
                #  ( config )
                status = config.get('status', '')
                self.sources_table.setItem(row, 4, QTableWidgetItem(status))

                # 
                self.sources_table.setItem(row, 5, QTableWidgetItem(""))

                #  - 
                operation_widget = None #  operation_widget 
                operation_widget = QWidget()
                operation_layout = QHBoxLayout(operation_widget)
                operation_layout.setContentsMargins(2, 2, 2, 2)

                # /
                connect_btn = QPushButton("" if status == "" else "")
                connect_btn.setMaximumWidth(60)
                connect_btn.clicked.connect(functools.partial(self._toggle_data_source_connection, source_id)) #  functools.partial

                # 
                config_btn = QPushButton("")
                config_btn.setMaximumWidth(60)
                config_btn.clicked.connect(functools.partial(self._configure_data_source, source_id))

                # 
                delete_btn = QPushButton("")
                delete_btn.setMaximumWidth(60)
                delete_btn.clicked.connect(functools.partial(self._delete_data_source, source_id))

                operation_layout.addWidget(connect_btn)
                operation_layout.addWidget(config_btn)
                operation_layout.addWidget(delete_btn)
                operation_layout.addStretch()

                self.sources_table.setCellWidget(row, 5, operation_widget) # 5

            self.logger.info(f" ")
            
        except Exception as e:
            self.logger.error(f" : {e}")
    
    def validate_config(self):
        """"""
        try:
            config_data = self._collect_current_config()
            errors = []
            
            # 
            if 'sync_settings' in config_data and 'frequency' in config_data['sync_settings']:
                freq = config_data['sync_settings']['frequency']
                if freq < 1 or freq > 1000:
                    errors.append(f" {freq} Hz  (1-1000 Hz)")
            
            # 
            if 'sync_settings' in config_data and 'max_concurrent' in config_data['sync_settings']:
                max_conc = config_data['sync_settings']['max_concurrent']
                if max_conc < 1 or max_conc > 100:
                    errors.append(f" {max_conc}  (1-100)")
            
            # 
            if 'performance_settings' in config_data and 'batch_size' in config_data['performance_settings']:
                batch_size = config_data['performance_settings']['batch_size']
                if batch_size < 1 or batch_size > 10000:
                    errors.append(f" {batch_size}  (1-10000)")
            
            if errors:
                self._add_event(f": {'; '.join(errors)}")
                return False, errors
            else:
                self._add_event("")
                return True, []
                
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False, [str(e)]
    
    def _toggle_data_source_connection(self, source_id: str):
        """"""
        try:
            if not hasattr(self, 'sync_engine') or not self.sync_engine:
                QMessageBox.warning(self, "", "")
                return
            
            # 
            if source_id not in self.sync_engine.data_sources:
                QMessageBox.warning(self, "", f" {source_id} ")
                return
            
            source_config = self.sync_engine.data_sources[source_id]
            if not source_config.get('interface'):
                QMessageBox.warning(self, "", f" {source_id} ")
                return
            
            interface = source_config['interface']
            
            # 
            if hasattr(interface, 'is_connected'):
                if callable(interface.is_connected):
                    is_connected = interface.is_connected()
                else:
                    is_connected = interface.is_connected
            else:
                is_connected = False
                
            if is_connected:
                # 
                if interface.disconnect():
                    QMessageBox.information(self, "", f" {source_id} ")
                else:
                    QMessageBox.warning(self, "", f" {source_id} ")
            else:
                # 
                if interface.connect():
                    QMessageBox.information(self, "", f" {source_id} ")
                else:
                    QMessageBox.warning(self, "", f" {source_id} ")
            
            # 
            self.refresh_sources()
            
            # 
            self.update_overview_statistics()
            
            # 
            self.update_sync_status()
            
        except Exception as e:
            QMessageBox.critical(self, "", f": {str(e)}")
            self.logger.error(f" : {e}")
    
    def _configure_data_source(self, source_id: str):
        """"""
        try:
            if not hasattr(self, 'sync_engine') or not self.sync_engine:
                QMessageBox.warning(self, "", "")
                return
            
            # 
            if source_id not in self.sync_engine.data_sources:
                QMessageBox.warning(self, "", f" {source_id} ")
                return
            
            source_config = self.sync_engine.data_sources[source_id]
            
            # 
            try:
                from .data_source_config_dialog import DataSourceConfigDialog
                
                dialog = DataSourceConfigDialog(self)
                
                # 
                dialog.data_source_configured.connect(self._on_data_source_configured)
                
                # 
                dialog.load_existing_config(source_id, source_config)
                
                if dialog.exec() == QDialog.Accepted:
                    # 
                    self.refresh_sources()
                    self.update_overview_statistics()
                    self.update_sync_status()
                
            except ImportError as e:
                QMessageBox.warning(self, "", f": {e}")
                self.logger.error(f" : {e}")
                return
            except Exception as e:
                QMessageBox.critical(self, "", f": {str(e)}")
                self.logger.error(f" : {e}")
                return
            
        except Exception as e:
            QMessageBox.critical(self, "", f": {str(e)}")
            self.logger.error(f" : {e}")
    
    def _on_new_data_source_configured(self, config_data: dict):
        """"""
        try:
            # ID
            current_row = self.sources_table.rowCount()
            source_id = f"DS_{current_row + 1:03d}"
            
            # 
            self.sources_table.insertRow(current_row)
            
            # 
            basic_info = config_data.get("basic", {})
            
            # ID
            self.sources_table.setItem(current_row, 0, QTableWidgetItem(source_id))
            
            # 
            source_name = basic_info.get("name", "")
            self.sources_table.setItem(current_row, 1, QTableWidgetItem(source_name))
            
            # 
            source_type = basic_info.get("type", "")
            self.sources_table.setItem(current_row, 2, QTableWidgetItem(source_type))
            
            # 
            self.sources_table.setItem(current_row, 3, QTableWidgetItem(""))
            
            # 
            data_rate = "0 Hz"
            self.sources_table.setItem(current_row, 4, QTableWidgetItem(data_rate))
            
            # 
            operation_widget = QWidget()
            operation_layout = QHBoxLayout(operation_widget)
            operation_layout.setContentsMargins(2, 2, 2, 2)
            
            connect_btn = QPushButton("")
            connect_btn.setMaximumWidth(60)
            from functools import partial
            connect_btn.clicked.connect(partial(self._toggle_data_source_connection, source_id))
            
            config_btn = QPushButton("")
            config_btn.setMaximumWidth(60)
            config_btn.clicked.connect(partial(self._configure_data_source, source_id))
            
            delete_btn = QPushButton("")
            delete_btn.setMaximumWidth(60)
            delete_btn.clicked.connect(partial(self._delete_data_source, source_id))
            
            operation_layout.addWidget(connect_btn)
            operation_layout.addWidget(config_btn)
            operation_layout.addWidget(delete_btn)
            operation_layout.addStretch()
            
            self.sources_table.setCellWidget(current_row, 5, operation_widget)
            
            # 
            self.data_sources[source_id] = config_data
            
            # 
            if self.sync_engine and hasattr(self.sync_engine, 'add_data_source'):
                try:
                    # 
                    enhanced_config = self._create_enhanced_config(source_id, config_data)
                    
                    success = self.sync_engine.add_data_source(source_id, enhanced_config)
                    if success:
                        self.logger.info(f"  {source_id} ")
                        self._add_event(f" {source_id} ")
                        
                        # 
                        if enhanced_config.get('interface'):
                            try:
                                interface = enhanced_config['interface']
                                if interface.connect():
                                    self.logger.info(f"  {source_id} ")
                                    self._add_event(f": {source_name}")
                                else:
                                    self.logger.warning(f"  {source_id} ")
                            except Exception as e:
                                self.logger.error(f"  {source_id} : {e}")
                    else:
                        self.logger.warning(f"  {source_id} ")
                except Exception as e:
                    self.logger.error(f" : {e}")
            
            # 
            self._update_source_count()
            
            # 
            self.update_overview_statistics()
            
            # 
            self._add_event(f": {basic_info.get('name', '')}")
            
            self.logger.info(f"  {source_id} ")
            
        except Exception as e:
            QMessageBox.critical(self, "", f": {e}")
            self.logger.error(f": {e}")

    def _on_data_source_configured(self, config_data: dict):
        """"""
        try:
            source_id = config_data.get('source_id')
            config = config_data.get('config')
            
            if not source_id or not config:
                self.logger.error(" ")
                return
            
            # 
            if hasattr(self, 'sync_engine') and self.sync_engine:
                if source_id in self.sync_engine.data_sources:
                    # 
                    existing_config = self.sync_engine.data_sources[source_id]
                    existing_config['basic'] = config['basic']
                    existing_config['connection'] = config['connection']
                    existing_config['metadata'] = config['metadata']
                    
                    # 
                    if existing_config.get('interface'):
                        try:
                            # 
                            interface = existing_config['interface']
                            if hasattr(interface, 'disconnect'):
                                interface.disconnect()
                            
                            # 
                            from core.core.multi_source_sync.data_source_factory import DataSourceFactory
                            factory = DataSourceFactory()
                            new_interface = factory.create_data_source(config['basic']['type'], config)
                            existing_config['interface'] = new_interface
                            
                            self.logger.info(f"  {source_id} ")
                            
                        except Exception as e:
                            self.logger.error(f" : {e}")
                    
                    self.logger.info(f"  {source_id} ")
                else:
                    self.logger.warning(f"  {source_id} ")
            
        except Exception as e:
            self.logger.error(f" : {e}")
    
    def _delete_data_source(self, source_id: str):
        """"""
        try:
            reply = QMessageBox.question(
                self, 
                "", 
                f" {source_id} ",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if not hasattr(self, 'sync_engine') or not self.sync_engine:
                    QMessageBox.warning(self, "", "")
                    return
                
                # 
                if hasattr(self.sync_engine, 'remove_data_source'):
                    if self.sync_engine.remove_data_source(source_id):
                        QMessageBox.information(self, "", f" {source_id} ")
                        # 
                        self.refresh_sources()
                    else:
                        QMessageBox.warning(self, "", f" {source_id} ")
                else:
                    QMessageBox.warning(self, "", "")
            
        except Exception as e:
            QMessageBox.critical(self, "", f": {str(e)}")
            self.logger.error(f" : {e}")
    
    def check_config_integrity(self):
        """"""
        try:
            config_data = self._collect_current_config()
            required_fields = [
                'sync_settings.frequency',
                'sync_settings.max_concurrent',
                'data_sources.source_type',
                'fusion_algorithm.algorithm'
            ]
            
            missing_fields = []
            for field_path in required_fields:
                keys = field_path.split('.')
                current = config_data
                for key in keys:
                    if key in current:
                        current = current[key]
                    else:
                        missing_fields.append(field_path)
                        break
            
            if missing_fields:
                self._add_event(f": {', '.join(missing_fields)}")
                return False, missing_fields
            else:
                self._add_event("")
                return True, []
                
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False, [str(e)]
    
    def create_config_backup(self):
        """"""
        try:
            config_data = self._collect_current_config()
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_data = {
                'backup_id': f"backup_{timestamp}",
                'timestamp': timestamp,
                'description': '',
                'config': config_data,
                'version': '1.0'
            }
            
            # 
            backup_dir = Path("config_backups")
            backup_dir.mkdir(exist_ok=True)
            
            backup_file = backup_dir / f"config_backup_{timestamp}.json"
            import json
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # 
            if not hasattr(self, 'config_backups'):
                self.config_backups = []
            
            self.config_backups.append(backup_data)
            
            self._add_event(f": {backup_file}")
            return backup_data
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return None
    
    def list_config_backups(self):
        """"""
        try:
            if not hasattr(self, 'config_backups'):
                self.config_backups = []
            
            # 
            backup_dir = Path("config_backups")
            if backup_dir.exists():
                for backup_file in backup_dir.glob("config_backup_*.json"):
                    try:
                        import json
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            backup_data = json.load(f)
                        self.config_backups.append(backup_data)
                    except Exception as e:
                        self._add_event(f": {backup_file}, : {e}")
            
            return self.config_backups
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return []
    
    def restore_config_backup(self, backup_id):
        """"""
        try:
            if not hasattr(self, 'config_backups'):
                self._add_event("")
                return False
            
            # 
            backup_data = None
            for backup in self.config_backups:
                if backup.get('backup_id') == backup_id:
                    backup_data = backup
                    break
            
            if not backup_data:
                self._add_event(f"ID: {backup_id}")
                return False
            
            # 
            config_data = backup_data.get('config', {})
            self._apply_config(config_data)
            
            self._add_event(f": {backup_id}")
            self.config_changed.emit(config_data)
            return True
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def delete_config_backup(self, backup_id):
        """"""
        try:
            if not hasattr(self, 'config_backups'):
                self._add_event("")
                return False
            
            # 
            for i, backup in enumerate(self.config_backups):
                if backup.get('backup_id') == backup_id:
                    # 
                    del self.config_backups[i]
                    
                    # 
                    backup_dir = Path("config_backups")
                    backup_file = backup_dir / f"config_backup_{backup_id.split('_', 1)[1]}.json"
                    if backup_file.exists():
                        backup_file.unlink()
                    
                    self._add_event(f": {backup_id}")
                    return True
            
            self._add_event(f"ID: {backup_id}")
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def update_performance_metrics(self):
        """"""
        import time
        try:
            import random
            try:
                import psutil
            except ImportError:
                raise ImportError("psutil")
            
            # 
            memory_percent = 0
            memory_optimized = False
            try:
                import sys
                import os
                core_path = os.path.join(os.path.dirname(__file__), '../../../core')
                if core_path not in sys.path:
                    sys.path.insert(0, core_path)
                from memory_optimizer import memory_optimizer
                
                # 
                memory_summary = memory_optimizer.get_memory_summary()
                memory_percent = memory_summary['current']['percent']
                
                # 
                if memory_percent > 85:
                    self._add_event(" ...")
                    gc_result = memory_optimizer.smart_garbage_collection()
                    if gc_result and gc_result.get('collected', 0) > 0:
                        self._add_event(f" :  {gc_result.get('collected', 0)} ")
                        memory_optimized = True
                        # 
                        memory_summary = memory_optimizer.get_memory_summary()
                        memory_percent = memory_summary['current']['percent']
                        self._add_event(f" : {memory_percent:.1f}%")
                
            except Exception as e:
                # 
                memory_info = psutil.virtual_memory()
                memory_percent = memory_info.percent
                self._add_event(f" : {str(e)[:50]}")
            
            # 
            cpu_percent = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/')
            
            # memory
            if 'memory_percent' not in locals():
                memory_info = psutil.virtual_memory()
                memory_percent = memory_info.percent
            
            # 
            real_throughput = 0.0
            throughput_optimized = False
            try:
                from data_throughput_optimizer import throughput_optimizer
                
                # 
                throughput_summary = throughput_optimizer.get_performance_summary()
                real_throughput = throughput_summary['current_throughput']
                
                # 
                if real_throughput == 0.0 and not throughput_optimizer.is_running:
                    self._add_event(" ...")
                    throughput_optimizer.start_processing()
                    
                    # 
                    from data_throughput_optimizer import imu_data_processor, cnap_data_processor
                    throughput_optimizer.add_data_processor(imu_data_processor)
                    throughput_optimizer.add_data_processor(cnap_data_processor)
                    
                    # 
                    for i in range(100):
                        test_data = {
                            'id': i,
                            'timestamp': time.time(),
                            'value': i * 1.5,
                            'type': 'imu' if i % 2 == 0 else 'cnap'
                        }
                        throughput_optimizer.add_data(test_data)
                    
                    self._add_event(" ...")
                    throughput_optimized = True
                
                # 
                elif real_throughput < 50 and throughput_optimizer.is_running:
                    self._add_event(" ...")
                    throughput_optimizer.optimize_performance()
                    throughput_optimized = True
                
            except Exception as e:
                self._add_event(f" : {str(e)[:50]}")
            
            # 
            if memory_optimized and throughput_optimized:
                # 
                sync_rate = max(50, real_throughput // 2)  # 
                data_quality = min(99, max(70, int(100 - cpu_percent * 0.3)))  # CPU
                latency = max(1, int(cpu_percent * 0.5))  # CPU
                throughput = max(real_throughput, 100.0)  # 
            elif memory_optimized or throughput_optimized:
                # 
                sync_rate = max(30, real_throughput // 3)  # 
                data_quality = min(95, max(65, int(100 - cpu_percent * 0.4)))  # CPU
                latency = max(1, int(cpu_percent * 0.8))  # CPU
                throughput = max(real_throughput, 50.0)  # 
            else:
                # 
                sync_rate = max(20, real_throughput // 5)  # 
                data_quality = min(90, max(60, int(100 - cpu_percent * 0.5)))  # CPU
                latency = max(1, int(cpu_percent * 1.0))  # CPU
                throughput = max(real_throughput, 25.0)  # 
            
            # 
            if hasattr(self, 'performance_display'):
                performance_text = f"""
:
CPU: {cpu_percent:.1f}%
: {memory_percent:.1f}%
: {disk.percent:.1f}%
: {sync_rate} Hz
: {data_quality}%
: {latency} ms
: {throughput:.1f} /
                """
                self.performance_display.setText(performance_text)
            
            # 
            if hasattr(self, 'metrics_widget'):
                # 
                pass
            
            # 
            performance_data = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk.percent,
                'sync_rate': sync_rate,
                'data_quality': data_quality,
                'latency': latency,
                'throughput': throughput,
                'timestamp': time.time()
            }
            
            # 
            # self.performance_updated.emit(performance_data)
            
            return performance_data
            
        except ImportError:
            # psutil
            current_time = time.time()
            time_factor = (current_time % 60) / 60.0  # 
            
            performance_data = {
                'cpu_percent': 20.0 + time_factor * 40.0,  # 20-60%
                'memory_percent': 50.0 + time_factor * 30.0,  # 50-80%
                'disk_percent': 20.0 + time_factor * 40.0,  # 20-60%
                'sync_rate': 50.0 + time_factor * 100.0,  # 50-150
                'data_quality': 70.0 + time_factor * 20.0,  # 70-90%
                'latency': 1.0 + time_factor * 30.0,  # 1-31ms
                'throughput': 100.0 + time_factor * 400.0,  # 100-500
                'timestamp': current_time
            }
            return performance_data
        except Exception as e:
            self._add_event(f": {str(e)}")
            return {}
    
    def get_performance_data(self):
        """"""
        try:
            return self.update_performance_metrics()
        except Exception as e:
            self._add_event(f": {str(e)}")
            return {}
    
    def _toggle_auto_refresh(self, enabled: bool):
        """"""
        try:
            if enabled:
                # 
                if not hasattr(self, 'performance_timer'):
                    self.performance_timer = QTimer()
                    self.performance_timer.timeout.connect(self.update_performance_metrics)
                
                self.performance_timer.start(20000)  # 20秒
                self._add_event("")
            else:
                # 
                if hasattr(self, 'performance_timer'):
                    self.performance_timer.stop()
                self._add_event("")
                
        except Exception as e:
            self._add_event(f": {str(e)}")
    
    def record_performance_history(self):
        """"""
        try:
            if not hasattr(self, 'performance_history'):
                self.performance_history = []
            
            # 
            current_data = self.update_performance_metrics()
            if current_data:
                # 
                current_data['recorded_at'] = time.time()
                current_data['recorded_date'] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # 
                self.performance_history.append(current_data)
                
                # 1000
                if len(self.performance_history) > 1000:
                    self.performance_history = self.performance_history[-1000:]
                
                self._add_event("")
                return True
            
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def get_performance_history(self, limit=100):
        """"""
        try:
            if not hasattr(self, 'performance_history'):
                self.performance_history = []
            
            # 
            return self.performance_history[-limit:] if self.performance_history else []
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return []
    
    def analyze_performance_trends(self, metric_name, time_range='1h'):
        """"""
        try:
            if not hasattr(self, 'performance_history'):
                self._add_event("")
                return {}
            
            # 
            current_time = time.time()
            if time_range == '1h':
                start_time = current_time - 3600
            elif time_range == '6h':
                start_time = current_time - 21600
            elif time_range == '24h':
                start_time = current_time - 86400
            else:
                start_time = current_time - 3600  # 1
            
            # 
            filtered_data = [
                record for record in self.performance_history
                if record.get('recorded_at', 0) >= start_time
            ]
            
            if not filtered_data:
                return {'error': ''}
            
            # 
            metric_values = []
            timestamps = []
            
            for record in filtered_data:
                if metric_name in record:
                    metric_values.append(record[metric_name])
                    timestamps.append(record.get('recorded_at', 0))
            
            if not metric_values:
                return {'error': f' {metric_name} '}
            
            # 
            import statistics
            analysis_result = {
                'metric_name': metric_name,
                'time_range': time_range,
                'data_points': len(metric_values),
                'min_value': min(metric_values),
                'max_value': max(metric_values),
                'avg_value': sum(metric_values) / len(metric_values),
                'median_value': statistics.median(metric_values) if len(metric_values) > 0 else 0,
                'trend': 'stable'
            }
            
            # 
            if len(metric_values) > 1:
                x_values = list(range(len(metric_values)))
                y_values = metric_values
                
                # 
                n = len(x_values)
                sum_x = sum(x_values)
                sum_y = sum(y_values)
                sum_xy = sum(x * y for x, y in zip(x_values, y_values))
                sum_x2 = sum(x * x for x in x_values)
                
                if n * sum_x2 - sum_x * sum_x != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                    
                    if slope > 0.01:
                        analysis_result['trend'] = 'increasing'
                    elif slope < -0.01:
                        analysis_result['trend'] = 'decreasing'
                    else:
                        analysis_result['trend'] = 'stable'
                    
                    analysis_result['slope'] = slope
            
            return analysis_result
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return {'error': str(e)}
    
    def export_performance_history(self, file_path=None):
        """"""
        try:
            if not hasattr(self, 'performance_history'):
                self._add_event("")
                return False
            
            if not file_path:
                from PySide6.QtWidgets import QFileDialog
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "", "performance_history.json", "JSON (*.json)"
                )
            
            if file_path:
                import json
                export_data = {
                    'export_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'total_records': len(self.performance_history),
                    'history': self.performance_history
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                self._add_event(f": {file_path}")
                return True
            
            return False
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def save_custom_thresholds(self):
        """"""
        try:
            thresholds = {
                'cpu_threshold': self.cpu_threshold_spin.value(),
                'memory_threshold': self.memory_threshold_spin.value(),
                'sync_rate_threshold': self.sync_rate_threshold_spin.value(),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            threshold_file = config_dir / "custom_thresholds.json"
            import json
            with open(threshold_file, 'w', encoding='utf-8') as f:
                json.dump(thresholds, f, ensure_ascii=False, indent=2)
            
            self._add_event("")
            return True
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def load_custom_thresholds(self):
        """"""
        try:
            threshold_file = Path("config") / "custom_thresholds.json"
            
            if threshold_file.exists():
                import json
                with open(threshold_file, 'r', encoding='utf-8') as f:
                    thresholds = json.load(f)
                
                # 
                if 'cpu_threshold' in thresholds:
                    self.cpu_threshold_spin.setValue(thresholds['cpu_threshold'])
                if 'memory_threshold' in thresholds:
                    self.memory_threshold_spin.setValue(thresholds['memory_threshold'])
                if 'sync_rate_threshold' in thresholds:
                    self.sync_rate_threshold_spin.setValue(thresholds['sync_rate_threshold'])
                
                self._add_event("")
                return True
            else:
                self._add_event("")
                return False
                
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def reset_custom_thresholds(self):
        """"""
        try:
            self.cpu_threshold_spin.setValue(80)
            self.memory_threshold_spin.setValue(85)
            self.sync_rate_threshold_spin.setValue(100)
            
            self._add_event("")
            return True
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return False
    
    def check_custom_thresholds(self, performance_data):
        """"""
        try:
            warnings = []
            
            # CPU
            if 'cpu_percent' in performance_data:
                cpu_value = performance_data['cpu_percent']
                cpu_threshold = self.cpu_threshold_spin.value()
                if cpu_value > cpu_threshold:
                    warnings.append(f"CPU: {cpu_value:.1f}% > {cpu_threshold}%")
            
            # 
            if 'memory_percent' in performance_data:
                memory_value = performance_data['memory_percent']
                memory_threshold = self.memory_threshold_spin.value()
                if memory_value > memory_threshold:
                    warnings.append(f": {memory_value:.1f}% > {memory_threshold}%")
            
            # 
            if 'sync_rate' in performance_data:
                sync_value = performance_data['sync_rate']
                sync_threshold = self.sync_rate_threshold_spin.value()
                if sync_value < sync_threshold:
                    warnings.append(f": {sync_value} Hz < {sync_threshold} Hz")
            
            return warnings
            
        except Exception as e:
            self._add_event(f": {str(e)}")
            return []
    
    def _show_trends_analysis(self):
        """"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QTextEdit, QGroupBox
            
            # 
            dialog = QDialog(self)
            dialog.setWindowTitle(" ")
            dialog.resize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            # 
            params_group = QGroupBox("")
            params_layout = QHBoxLayout(params_group)
            
            # 
            metric_label = QLabel(":")
            metric_combo = QComboBox()
            metric_combo.addItems([
                'cpu_percent', 'memory_percent', 'disk_percent',
                'sync_rate', 'data_quality', 'latency', 'throughput'
            ])
            params_layout.addWidget(metric_label)
            params_layout.addWidget(metric_combo)
            
            # 
            time_label = QLabel(":")
            time_combo = QComboBox()
            time_combo.addItems(['1h', '6h', '24h'])
            params_layout.addWidget(time_label)
            params_layout.addWidget(time_combo)
            
            # 
            analyze_btn = QPushButton(" ")
            params_layout.addWidget(analyze_btn)
            
            layout.addWidget(params_group)
            
            # 
            results_group = QGroupBox("")
            results_layout = QVBoxLayout(results_group)
            
            results_display = QTextEdit()
            results_display.setReadOnly(True)
            results_layout.addWidget(results_display)
            
            layout.addWidget(results_group)
            
            # 
            button_layout = QHBoxLayout()
            
            export_btn = QPushButton(" ")
            close_btn = QPushButton("")
            
            button_layout.addWidget(export_btn)
            button_layout.addStretch()
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            # 
            def analyze_trends():
                metric = metric_combo.currentText()
                time_range = time_combo.currentText()
                
                results = self.analyze_performance_trends(metric, time_range)
                
                if 'error' in results:
                    results_display.setText(f": {results['error']}")
                else:
                    result_text = f""":
                    
: {results.get('metric_name', 'N/A')}
: {results.get('time_range', 'N/A')}
: {results.get('data_points', 0)}

:
  : {results.get('min_value', 0):.2f}
  : {results.get('max_value', 0):.2f}
  : {results.get('avg_value', 0):.2f}
  : {results.get('median_value', 0):.2f}

:
  : {results.get('trend', 'stable')}
  : {results.get('slope', 0):.4f}

: {time.strftime("%Y-%m-%d %H:%M:%S")}
                    """
                    results_display.setText(result_text)
            
            analyze_btn.clicked.connect(analyze_trends)
            close_btn.clicked.connect(dialog.accept)
            
            # 
            dialog.exec()
            
        except Exception as e:
            self._add_event(f": {str(e)}")

    def connect_left_sync(self):
        left_panel = None
        if self.parent() and hasattr(self.parent(), 'findChild'):
            left_panel = self.parent().findChild(DataSourceControlPanel)
        if not left_panel:
            from PySide6.QtWidgets import QApplication  #  QApplication 
            left_panel = QApplication.instance().findChild(DataSourceControlPanel)  #  fallback
        if left_panel:
            left_panel.data_sources_updated.connect(self.update_from_left)
            self.logger.info(" ")
        else:
            self.logger.warning(" ")
            # 
            self._refresh_data_sources_display()

    def update_from_left(self, data_sources):
        self.sources_table.setRowCount(0) # 
        self.logger.info(f"🟢 : {data_sources}")

        if not data_sources:
            self._update_ui_with_default_status()
            self.logger.warning("")
            return

        for row, (source_id, config) in enumerate(data_sources.items()):  #  id  config
            current_row = self.sources_table.rowCount()
            self.sources_table.insertRow(current_row)

            # 
            self.sources_table.setItem(current_row, 0, QTableWidgetItem(source_id))  # ID
            self.sources_table.setItem(current_row, 1, QTableWidgetItem(config.get('basic', {}).get('name', 'N/A'))) # 
            self.sources_table.setItem(current_row, 2, QTableWidgetItem(config.get('basic', {}).get('type', 'N/A'))) # 
            self.sources_table.setItem(current_row, 3, QTableWidgetItem(str(config.get('basic', {}).get('sampling_rate', 'N/A')))) # 

        # 
        try:
            # 
            right_panel = None
            if self.parent() and hasattr(self.parent(), 'findChild'):
                from modules.ui.core_ui.components.right_content_panel import RightContentPanel
                right_panel = self.parent().findChild(RightContentPanel)
                
            if not right_panel:
                #  fallback
                from PySide6.QtWidgets import QApplication
                for widget in QApplication.allWidgets():
                    if isinstance(widget, RightContentPanel):
                        right_panel = widget
                        break
            
            if right_panel:
                # 
                monitoring_data = {}
                for source_id, config in data_sources.items():
                    source_name = config.get('basic', {}).get('name', source_id)
                    monitoring_data[f"{source_name} "] = config.get('status', '')
                    monitoring_data[f"{source_name} "] = config.get('basic', {}).get('sampling_rate', 'N/A')
                
                # 
                if data_sources:
                    monitoring_data[""] = ""
                else:
                    monitoring_data[""] = ""
                
                # 
                right_panel.update_monitoring_data(monitoring_data)
                # 
                right_panel.refresh_all_tabs()
                self.logger.info(" ")
            else:
                self.logger.warning(" ")
        except Exception as e:
            self.logger.error(f" : {str(e)}")

            #  ( config )
            status = config.get('status', '')
            self.sources_table.setItem(current_row, 4, QTableWidgetItem(status))

            # 
            self.sources_table.setItem(current_row, 5, QTableWidgetItem(""))

            #  - 
            operation_widget = None #  operation_widget 
            operation_widget = QWidget()
            operation_layout = QHBoxLayout(operation_widget)
            operation_layout.setContentsMargins(2, 2, 2, 2)

            # /
            connect_btn = QPushButton("" if status == "" else "")
            connect_btn.setMaximumWidth(60)
            connect_btn.clicked.connect(functools.partial(self._toggle_data_source_connection, source_id)) #  functools.partial

            # 
            config_btn = QPushButton("")
            config_btn.setMaximumWidth(60)
            config_btn.clicked.connect(functools.partial(self._configure_data_source, source_id))

            # 
            delete_btn = QPushButton("")
            delete_btn.setMaximumWidth(60)
            delete_btn.clicked.connect(functools.partial(self._delete_data_source, source_id))

            operation_layout.addWidget(connect_btn)
            operation_layout.addWidget(config_btn)
            operation_layout.addWidget(delete_btn)
            operation_layout.addStretch()

            self.sources_table.setCellWidget(current_row, 5, operation_widget) # 5

        self.logger.info(f" ")

    def connect_right_sync(self):
        # 
        left_panel = None
        if self.parent() and hasattr(self.parent(), 'findChild'):
            left_panel = self.parent().findChild(DataSourceControlPanel)
        if left_panel:
            self.data_sources_updated.connect(left_panel.update_from_right)
        else:
            self.logger.warning("未找到左侧面板用于同步")

    def update_table(self):  # 
        # ...  ...
        self.data_sources_updated.emit(self.current_data)  # emit 

    def _update_ui_with_default_status(self):
        self.quick_status_label.setText(" : ...")  # 
        self.sources_table.setRowCount(1)  # 
        self.sources_table.setItem(0, 0, QTableWidgetItem(""))
        self.sources_table.setItem(0, 1, QTableWidgetItem(""))
        self.sources_table.setItem(0, 2, QTableWidgetItem(""))
        self.logger.info("UI已更新为默认状态")
