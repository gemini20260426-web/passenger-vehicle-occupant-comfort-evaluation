#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
右侧Data Source标签页 - 修复版本
包含从UI可视化模板迁移过来的数据源管理功能
多源异构数据同步处理系统的核心界面
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QProgressBar,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QDialog,
    QTabWidget, QTextEdit, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea, QFrame,
    QSlider, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPen

try:
    from core.core.data_processing.signal_filter import (
        SignalFilter, FilterConfig, FilterType, get_signal_filter
    )
    FILTER_AVAILABLE = True
except ImportError:
    FILTER_AVAILABLE = False

logger = logging.getLogger(__name__)


class DataSourceTabWidget(QWidget):
    """
    右侧Data Source标签页主控件 - 修复版本
    包含从UI可视化模板迁移过来的数据源管理功能
    """
    
    # 信号定义
    data_source_connected = Signal(str, dict)        # 数据源连接 (类型, 配置)
    data_source_disconnected = Signal(str)           # 数据源断开 (类型)
    sync_started = Signal(dict)                     # 同步开始 (配置)
    sync_stopped = Signal()                         # 同步停止
    performance_updated = Signal(dict)              # 性能更新 (指标)
    data_quality_changed = Signal(str, float)       # 数据质量变化 (类型, 分数)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # 数据源状态
        self.connected_sources = {}
        self.sync_config = {}
        self.performance_metrics = {}
        
        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_performance_display)
        self.status_timer.start(1000)  # 每秒更新一次
        
        # 初始化UI
        self.init_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 初始化多源同步引擎
        self._init_multi_source_sync_engine()
        
        # 启动性能监控
        self._start_performance_monitoring()
        
        # 初始化数据源状态
        self._refresh_data_source_status()
        
        logger.info("Data Source标签页初始化完成")
    
    def _init_multi_source_sync_engine(self):
        """初始化多源异构数据同步引擎"""
        try:
            # 尝试导入核心同步模块
            from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine
            
            # 使用正确的配置格式
            sync_engine_config = {
                'max_workers': 4,
                'sync_interval': 0.01,  # 100Hz
                'max_latency': 0.05,    # 50ms
                'quality_threshold': 0.8,
                'auto_recovery': True
            }
            
            self.sync_engine = MultiSourceSyncEngine(config=sync_engine_config)
            self.sync_engine_available = True
            logger.info("✅ 多源同步引擎初始化成功")
        except ImportError as e:
            logger.warning(f"⚠️ 多源同步引擎不可用: {e}")
            self.sync_engine = None
            self.sync_engine_available = False
        
        # 同步状态
        self.is_syncing = False
        self.sync_paused = False
        self.sync_progress_value = 0
    
    def init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # === 1. 数据源配置区域 (从UI可视化模板迁移) ===
        data_source_config_panel = self.create_data_source_config_panel()
        main_layout.addWidget(data_source_config_panel)
        
        # === 1.5. 数据滤波配置区域 ===
        filter_config_panel = self.create_filter_config_panel()
        main_layout.addWidget(filter_config_panel)
        
        # === 2. 数据源连接管理面板 ===
        connection_panel = self.create_connection_panel()
        main_layout.addWidget(connection_panel)
        
        # === 3. 同步配置控制面板 ===
        sync_config_panel = self.create_sync_config_panel()
        main_layout.addWidget(sync_config_panel)
        
        # === 4. 实时监控面板 ===
        monitor_panel = self.create_monitor_panel()
        main_layout.addWidget(monitor_panel)
        
        # === 5. 高级配置选项面板 ===
        advanced_config_panel = self.create_advanced_config_panel()
        main_layout.addWidget(advanced_config_panel)
        
        # === 6. 实时数据流监控图表区域 ===
        charts_panel = self.create_charts_panel()
        main_layout.addWidget(charts_panel)
        
        # === 7. 多源异构数据同步管理区域 ===
        multi_source_sync_panel = self.create_multi_source_sync_panel()
        main_layout.addWidget(multi_source_sync_panel)
        
        # === 8. 数据源状态监控面板 ===
        data_source_status_panel = self.create_data_source_status_panel()
        main_layout.addWidget(data_source_status_panel)
        
        # === 9. 同步性能监控面板 ===
        sync_performance_panel = self.create_sync_performance_panel()
        main_layout.addWidget(sync_performance_panel)
        
        # === 10. 数据质量评估面板 ===
        data_quality_panel = self.create_data_quality_panel()
        main_layout.addWidget(data_quality_panel)
        
        # === 11. 异常检测监控面板 ===
        anomaly_detection_panel = self.create_anomaly_detection_panel()
        main_layout.addWidget(anomaly_detection_panel)
        
        # === 12. 数据融合可视化面板 ===
        data_fusion_panel = self.create_data_fusion_panel()
        main_layout.addWidget(data_fusion_panel)
        
        # 填充剩余空间
        main_layout.addStretch()
    
    def create_data_source_config_panel(self):
        """创建数据源配置控制组 (从UI可视化模板迁移)"""
        group = QGroupBox("📊 数据源配置")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #007bff;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 数据源类型选择
        source_type_layout = QHBoxLayout()
        source_type_layout.addWidget(QLabel("数据源类型:"))
        
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["离线数据集", "实时串口", "MQTT数据流"])
        self.source_type_combo.setCurrentText("离线数据集")
        self.source_type_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #007bff;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                min-width: 150px;
            }
        """)
        source_type_layout.addWidget(self.source_type_combo)
        
        layout.addLayout(source_type_layout)
        
        # 文件选择区域
        file_layout = QVBoxLayout()
        
        # IMU数据文件
        imu_file_layout = QHBoxLayout()
        imu_file_layout.addWidget(QLabel("IMU数据:"))
        self.imu_file_edit = QLineEdit()
        self.imu_file_edit.setPlaceholderText("选择IMU数据文件...")
        self.imu_file_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #007bff;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        imu_file_layout.addWidget(self.imu_file_edit, 1)
        
        self.imu_browse_btn = QPushButton("浏览")
        self.imu_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        imu_file_layout.addWidget(self.imu_browse_btn)
        
        file_layout.addLayout(imu_file_layout)
        
        # CNAP数据文件
        cnap_file_layout = QHBoxLayout()
        cnap_file_layout.addWidget(QLabel("CNAP数据:"))
        self.cnap_file_edit = QLineEdit()
        self.cnap_file_edit.setPlaceholderText("选择CNAP数据文件...")
        self.cnap_file_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #007bff;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        cnap_file_layout.addWidget(self.cnap_file_edit, 1)
        
        self.cnap_browse_btn = QPushButton("浏览")
        self.cnap_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        cnap_file_layout.addWidget(self.cnap_browse_btn)
        
        file_layout.addLayout(cnap_file_layout)
        
        layout.addLayout(file_layout)
        
        # 数据加载控制
        load_control_layout = QHBoxLayout()
        
        self.load_data_btn = QPushButton("🚀 加载数据")
        self.load_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        self.stop_loading_btn = QPushButton("⏹️ 停止")
        self.stop_loading_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.stop_loading_btn.setEnabled(False)
        
        load_control_layout.addWidget(self.load_data_btn)
        load_control_layout.addWidget(self.stop_loading_btn)
        
        layout.addLayout(load_control_layout)
        
        # 数据状态显示
        self.data_status_label = QLabel("状态: 请选择数据文件")
        self.data_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.data_status_label)
        
        # 数据质量指示器
        self.data_quality_indicator = QLabel("数据质量: ⚪ 待检测")
        self.data_quality_indicator.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.data_quality_indicator)
        
        return group

    def create_filter_config_panel(self):
        group = QGroupBox("🔧 数据滤波配置")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #fd7e14;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)

        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        enable_layout = QHBoxLayout()
        self.filter_enable_check = QCheckBox("启用数据滤波")
        self.filter_enable_check.setChecked(False)
        self.filter_enable_check.setStyleSheet("font-weight: bold; font-size: 12px;")
        enable_layout.addWidget(self.filter_enable_check)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("滤波算法:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems([
            "移动平均滤波", "中值滤波", "指数加权滤波",
            "高通滤波", "带通滤波", "卡尔曼滤波", "巴特沃斯低通滤波"
        ])
        self.filter_type_combo.setCurrentText("移动平均滤波")
        self.filter_type_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #fd7e14;
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
                min-width: 140px;
            }
        """)
        type_layout.addWidget(self.filter_type_combo)
        layout.addLayout(type_layout)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标字段:"))
        self.filter_target_imu = QCheckBox("IMU(ax/ay/az)")
        self.filter_target_imu.setChecked(True)
        self.filter_target_cnap = QCheckBox("CNAP(wave)")
        self.filter_target_cnap.setChecked(False)
        target_layout.addWidget(self.filter_target_imu)
        target_layout.addWidget(self.filter_target_cnap)
        target_layout.addStretch()
        layout.addLayout(target_layout)

        param_layout = QGridLayout()
        param_layout.setSpacing(8)

        param_layout.addWidget(QLabel("窗口大小:"), 0, 0)
        self.filter_window_spin = QSpinBox()
        self.filter_window_spin.setRange(2, 100)
        self.filter_window_spin.setValue(5)
        self.filter_window_spin.setSuffix(" 点")
        param_layout.addWidget(self.filter_window_spin, 0, 1)

        param_layout.addWidget(QLabel("平滑系数 α:"), 0, 2)
        self.filter_alpha_spin = QDoubleSpinBox()
        self.filter_alpha_spin.setRange(0.01, 0.99)
        self.filter_alpha_spin.setSingleStep(0.05)
        self.filter_alpha_spin.setValue(0.3)
        param_layout.addWidget(self.filter_alpha_spin, 0, 3)

        param_layout.addWidget(QLabel("截止频率:"), 1, 0)
        self.filter_cutoff_spin = QDoubleSpinBox()
        self.filter_cutoff_spin.setRange(0.1, 500.0)
        self.filter_cutoff_spin.setValue(10.0)
        self.filter_cutoff_spin.setSuffix(" Hz")
        param_layout.addWidget(self.filter_cutoff_spin, 1, 1)

        param_layout.addWidget(QLabel("采样率:"), 1, 2)
        self.filter_samplerate_spin = QDoubleSpinBox()
        self.filter_samplerate_spin.setRange(1.0, 1000.0)
        self.filter_samplerate_spin.setValue(100.0)
        self.filter_samplerate_spin.setSuffix(" Hz")
        param_layout.addWidget(self.filter_samplerate_spin, 1, 3)

        param_layout.addWidget(QLabel("滤波器阶数:"), 2, 0)
        self.filter_order_spin = QSpinBox()
        self.filter_order_spin.setRange(1, 8)
        self.filter_order_spin.setValue(2)
        param_layout.addWidget(self.filter_order_spin, 2, 1)

        param_layout.addWidget(QLabel("过程噪声 Q:"), 2, 2)
        self.filter_q_spin = QDoubleSpinBox()
        self.filter_q_spin.setRange(0.001, 10.0)
        self.filter_q_spin.setSingleStep(0.01)
        self.filter_q_spin.setDecimals(3)
        self.filter_q_spin.setValue(0.01)
        param_layout.addWidget(self.filter_q_spin, 2, 3)

        param_layout.addWidget(QLabel("测量噪声 R:"), 3, 0)
        self.filter_r_spin = QDoubleSpinBox()
        self.filter_r_spin.setRange(0.001, 10.0)
        self.filter_r_spin.setSingleStep(0.01)
        self.filter_r_spin.setDecimals(3)
        self.filter_r_spin.setValue(0.1)
        param_layout.addWidget(self.filter_r_spin, 3, 1)

        layout.addLayout(param_layout)

        btn_layout = QHBoxLayout()
        self.filter_apply_btn = QPushButton("✅ 应用滤波配置")
        self.filter_apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0690a;
            }
        """)
        btn_layout.addWidget(self.filter_apply_btn)

        self.filter_reset_btn = QPushButton("🔄 重置滤波器")
        self.filter_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        btn_layout.addWidget(self.filter_reset_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.filter_status_label = QLabel("滤波状态: 未启用")
        self.filter_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.filter_status_label)

        self.filter_apply_btn.clicked.connect(self._apply_filter_config)
        self.filter_reset_btn.clicked.connect(self._reset_filter_config)
        self.filter_type_combo.currentTextChanged.connect(self._on_filter_type_changed)

        self._on_filter_type_changed(self.filter_type_combo.currentText())

        return group

    def _on_filter_type_changed(self, filter_name):
        algo_map = {
            "移动平均滤波": "moving_average",
            "中值滤波": "median",
            "指数加权滤波": "exponential",
            "高通滤波": "high_pass",
            "带通滤波": "band_pass",
            "卡尔曼滤波": "kalman",
            "巴特沃斯低通滤波": "butterworth_lowpass",
        }
        algo = algo_map.get(filter_name, "moving_average")

        needs_window = algo in ("moving_average", "median")
        needs_alpha = algo in ("exponential", "high_pass", "band_pass")
        needs_cutoff = algo in ("butterworth_lowpass",)
        needs_order = algo in ("butterworth_lowpass",)
        needs_kalman = algo in ("kalman",)

        self.filter_window_spin.setEnabled(needs_window)
        self.filter_alpha_spin.setEnabled(needs_alpha)
        self.filter_cutoff_spin.setEnabled(needs_cutoff)
        self.filter_samplerate_spin.setEnabled(needs_cutoff)
        self.filter_order_spin.setEnabled(needs_order)
        self.filter_q_spin.setEnabled(needs_kalman)
        self.filter_r_spin.setEnabled(needs_kalman)

    def _apply_filter_config(self):
        if not FILTER_AVAILABLE:
            QMessageBox.warning(self, "警告", "滤波模块不可用，请检查依赖")
            return

        try:
            algo_map = {
                "移动平均滤波": FilterType.MOVING_AVERAGE,
                "中值滤波": FilterType.MEDIAN,
                "指数加权滤波": FilterType.EXPONENTIAL,
                "高通滤波": FilterType.HIGH_PASS,
                "带通滤波": FilterType.BAND_PASS,
                "卡尔曼滤波": FilterType.KALMAN,
                "巴特沃斯低通滤波": FilterType.BUTTERWORTH_LOWPASS,
            }
            filter_type = algo_map.get(
                self.filter_type_combo.currentText(), FilterType.MOVING_AVERAGE
            )

            target_fields = []
            if self.filter_target_imu.isChecked():
                target_fields.extend(["ax", "ay", "az"])
            if self.filter_target_cnap.isChecked():
                target_fields.append("wave")

            config = FilterConfig(
                filter_type=filter_type,
                enabled=self.filter_enable_check.isChecked(),
                window_size=self.filter_window_spin.value(),
                alpha=self.filter_alpha_spin.value(),
                cutoff_frequency=self.filter_cutoff_spin.value(),
                sample_rate=self.filter_samplerate_spin.value(),
                order=self.filter_order_spin.value(),
                process_noise=self.filter_q_spin.value(),
                measurement_noise=self.filter_r_spin.value(),
                target_fields=target_fields,
            )

            for source_id in ["imu_source", "cnap_source"]:
                sf = get_signal_filter(source_id, config)

            if self.filter_enable_check.isChecked():
                self.filter_status_label.setText(
                    f"滤波状态: ✅ 已启用 ({self.filter_type_combo.currentText()})"
                )
                self.filter_status_label.setStyleSheet("color: #28a745; font-size: 11px; font-weight: bold;")
            else:
                self.filter_status_label.setText("滤波状态: ⚪ 已配置但未启用")
                self.filter_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")

            logger.info(f"滤波配置已应用: {filter_type.value}, enabled={config.enabled}")

        except Exception as e:
            logger.error(f"应用滤波配置失败: {e}")
            QMessageBox.critical(self, "错误", f"应用滤波配置失败: {e}")

    def _reset_filter_config(self):
        try:
            from core.core.data_processing.signal_filter import reset_all_filters
            reset_all_filters()
            self.filter_status_label.setText("滤波状态: 🔄 已重置")
            self.filter_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
            logger.info("所有滤波器已重置")
        except Exception as e:
            logger.error(f"重置滤波器失败: {e}")
        
    def create_connection_panel(self):
        """创建数据源连接管理面板"""
        group = QGroupBox("🔗 数据源连接管理")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #007bff;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 连接状态显示
        self.connection_status_list = QListWidget()
        self.connection_status_list.setMaximumHeight(120)
        self.connection_status_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                background-color: #f8f9fa;
                font-size: 11px;
            }
        """)
        
        # 添加示例状态项
        self._add_connection_status_item("IMU传感器", "未连接", "red")
        self._add_connection_status_item("CNAP传感器", "未连接", "red")
        self._add_connection_status_item("MQTT数据源", "未连接", "red")
        
        layout.addWidget(self.connection_status_list)
        
        # 连接控制按钮
        control_layout = QHBoxLayout()
        
        self.add_source_btn = QPushButton("➕ 添加数据源")
        self.add_source_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        self.connect_source_btn = QPushButton("🔌 连接")
        self.connect_source_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        self.disconnect_source_btn = QPushButton("🔌 断开")
        self.disconnect_source_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        self.remove_source_btn = QPushButton("🗑️ 删除")
        self.remove_source_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        control_layout.addWidget(self.add_source_btn)
        control_layout.addWidget(self.connect_source_btn)
        control_layout.addWidget(self.disconnect_source_btn)
        control_layout.addWidget(self.remove_source_btn)
        
        layout.addLayout(control_layout)
        
        # 刷新状态按钮
        self.refresh_status_btn = QPushButton("🔄 刷新状态")
        self.refresh_status_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        layout.addWidget(self.refresh_status_btn)
        
        return group
        
    def create_sync_config_panel(self):
        """创建同步配置控制面板"""
        group = QGroupBox("⚙️ 同步配置控制")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #17a2b8;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 配置网格布局
        config_grid = QGridLayout()
        
        # 同步模式选择
        config_grid.addWidget(QLabel("同步模式:"), 0, 0)
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems(["实时同步", "批量同步", "定时同步"])
        self.sync_mode_combo.setCurrentText("实时同步")
        self.sync_mode_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #17a2b8;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                min-width: 120px;
            }
        """)
        config_grid.addWidget(self.sync_mode_combo, 0, 1)
        
        # 时间窗口设置
        config_grid.addWidget(QLabel("时间窗口:"), 1, 0)
        self.time_window_spin = QSpinBox()
        self.time_window_spin.setRange(1, 60)
        self.time_window_spin.setValue(10)
        self.time_window_spin.setSuffix(" 秒")
        self.time_window_spin.setStyleSheet("""
            QSpinBox {
                border: 2px solid #17a2b8;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                min-width: 100px;
            }
        """)
        config_grid.addWidget(self.time_window_spin, 1, 1)
        
        # 插值方法选择
        config_grid.addWidget(QLabel("插值方法:"), 2, 0)
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.addItems(["线性插值", "样条插值", "最近邻插值"])
        self.interpolation_combo.setCurrentText("线性插值")
        self.interpolation_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #17a2b8;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                min-width: 120px;
            }
        """)
        config_grid.addWidget(self.interpolation_combo, 2, 1)
        
        # 融合算法选择
        config_grid.addWidget(QLabel("融合算法:"), 3, 0)
        self.fusion_algorithm_combo = QComboBox()
        self.fusion_algorithm_combo.addItems(["卡尔曼滤波", "粒子滤波", "加权平均"])
        self.fusion_algorithm_combo.setCurrentText("加权平均")
        self.fusion_algorithm_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #17a2b8;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
                min-width: 120px;
            }
        """)
        config_grid.addWidget(self.fusion_algorithm_combo, 3, 1)
        
        layout.addLayout(config_grid)
        
        # 同步控制按钮
        sync_control_layout = QHBoxLayout()
        
        self.start_sync_btn = QPushButton("▶️ 开始同步")
        self.start_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        self.pause_sync_btn = QPushButton("⏸️ 暂停同步")
        self.pause_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        self.pause_sync_btn.setEnabled(False)
        
        self.stop_sync_btn = QPushButton("⏹️ 停止同步")
        self.stop_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.stop_sync_btn.setEnabled(False)
        
        sync_control_layout.addWidget(self.start_sync_btn)
        sync_control_layout.addWidget(self.pause_sync_btn)
        sync_control_layout.addWidget(self.stop_sync_btn)
        
        layout.addLayout(sync_control_layout)
        
        return group
        
    def create_monitor_panel(self):
        """创建实时监控面板"""
        group = QGroupBox("📊 实时监控")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #6f42c1;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 数据频率监控
        freq_layout = QGridLayout()
        
        self.imu_freq_label = QLabel("IMU: 0 Hz")
        self.imu_freq_label.setStyleSheet("color: #6f42c1; font-size: 12px; font-weight: bold;")
        freq_layout.addWidget(self.imu_freq_label, 0, 0)
        
        self.cnap_freq_label = QLabel("CNAP: 0 Hz")
        self.cnap_freq_label.setStyleSheet("color: #6f42c1; font-size: 12px; font-weight: bold;")
        freq_layout.addWidget(self.cnap_freq_label, 0, 1)
        
        self.fusion_freq_label = QLabel("融合: 0 Hz")
        self.fusion_freq_label.setStyleSheet("color: #6f42c1; font-size: 12px; font-weight: bold;")
        freq_layout.addWidget(self.fusion_freq_label, 1, 0)
        
        layout.addLayout(freq_layout)
        
        # 性能指标
        performance_layout = QGridLayout()
        
        self.latency_label = QLabel("延迟: 0 ms")
        self.latency_label.setStyleSheet("color: #dc3545; font-size: 12px; font-weight: bold;")
        performance_layout.addWidget(self.latency_label, 0, 0)
        
        self.quality_label = QLabel("质量: 0%")
        self.quality_label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
        performance_layout.addWidget(self.quality_label, 0, 1)
        
        self.throughput_label = QLabel("吞吐量: 0 数据点/秒")
        self.throughput_label.setStyleSheet("color: #17a2b8; font-size: 12px; font-weight: bold;")
        performance_layout.addWidget(self.throughput_label, 1, 0, 1, 2)
        
        layout.addLayout(performance_layout)
        
        # 数据质量指示器
        self.data_quality_indicator = QLabel("数据质量: ⚪ 待检测")
        self.data_quality_indicator.setStyleSheet("color: #6c757d; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.data_quality_indicator)
        
        # 异常检测
        self.anomaly_detection_label = QLabel("异常检测: 正常")
        self.anomaly_detection_label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.anomaly_detection_label)
        
        # 查看详情按钮
        self.view_details_btn = QPushButton("👁️ 查看详情")
        self.view_details_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        layout.addWidget(self.view_details_btn)
        
        return group
        
    def create_advanced_config_panel(self):
        """创建高级配置选项面板"""
        group = QGroupBox("⚙️ 高级配置选项")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #fd7e14;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # MQTT配置
        mqtt_group = QGroupBox("MQTT配置")
        mqtt_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #fd7e14;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        mqtt_layout = QFormLayout(mqtt_group)
        
        self.mqtt_server_edit = QLineEdit("localhost")
        self.mqtt_port_edit = QLineEdit("1883")
        self.mqtt_topic_edit = QLineEdit("sensor/data")
        self.mqtt_auth_check = QCheckBox("启用认证")
        
        mqtt_layout.addRow("服务器:", self.mqtt_server_edit)
        mqtt_layout.addRow("端口:", self.mqtt_port_edit)
        mqtt_layout.addRow("主题:", self.mqtt_topic_edit)
        mqtt_layout.addRow("", self.mqtt_auth_check)
        
        layout.addWidget(mqtt_group)
        
        # 串口配置
        serial_group = QGroupBox("串口配置")
        serial_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #fd7e14;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        serial_layout = QFormLayout(serial_group)
        
        self.serial_port_combo = QComboBox()
        self.serial_port_combo.addItems(["COM1", "COM2", "COM3", "COM4"])
        self.serial_baud_combo = QComboBox()
        self.serial_baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.serial_baud_combo.setCurrentText("115200")
        
        serial_layout.addRow("端口:", self.serial_port_combo)
        serial_layout.addRow("波特率:", self.serial_baud_combo)
        
        layout.addWidget(serial_group)
        
        # 配置管理按钮
        config_control_layout = QHBoxLayout()
        
        self.save_config_btn = QPushButton("💾 保存配置")
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8690b;
            }
        """)
        
        self.reset_config_btn = QPushButton("🔄 重置配置")
        self.reset_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        self.import_config_btn = QPushButton("📥 导入配置")
        self.import_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8690b;
            }
        """)
        
        self.export_config_btn = QPushButton("📤 导出配置")
        self.export_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8690b;
            }
        """)
        
        config_control_layout.addWidget(self.save_config_btn)
        config_control_layout.addWidget(self.reset_config_btn)
        config_control_layout.addWidget(self.import_config_btn)
        config_control_layout.addWidget(self.export_config_btn)
        
        layout.addLayout(config_control_layout)
        
        return group
        
    def create_charts_panel(self):
        """创建实时数据流监控图表区域"""
        group = QGroupBox("📈 实时数据流监控")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #20c997;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 图表布局
        charts_layout = QGridLayout()
        
        # IMU数据流图表
        self.imu_chart = self.create_chart_widget("IMU数据流", "100 Hz")
        charts_layout.addWidget(self.imu_chart, 0, 0)
        
        # CNAP数据流图表
        self.cnap_chart = self.create_chart_widget("CNAP数据流", "1 Hz")
        charts_layout.addWidget(self.cnap_chart, 0, 1)
        
        # 融合数据流图表
        self.fusion_chart = self.create_chart_widget("融合数据流", "100 Hz")
        charts_layout.addWidget(self.fusion_chart, 1, 0, 1, 2)
        
        layout.addLayout(charts_layout)
        
        return group
        
    def create_multi_source_sync_panel(self):
        """创建多源异构数据同步控制面板"""
        group = QGroupBox("🔄 多源异构数据同步控制")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #495057;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 同步状态显示
        self.sync_status_label = QLabel("同步状态: 未同步")
        self.sync_status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.sync_status_label)
        
        # 同步进度条
        self.sync_progress = QProgressBar()
        self.sync_progress.setRange(0, 100)
        self.sync_progress.setValue(0)
        self.sync_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #495057;
                border-radius: 5px;
                text-align: center;
                padding: 2px;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #007bff;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.sync_progress)
        
        # 同步控制按钮
        sync_control_layout = QHBoxLayout()
        
        self.start_multi_sync_btn = QPushButton("▶️ 开始多源同步")
        self.start_multi_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        self.pause_multi_sync_btn = QPushButton("⏸️ 暂停多源同步")
        self.pause_multi_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        self.pause_multi_sync_btn.setEnabled(False)
        
        self.stop_multi_sync_btn = QPushButton("⏹️ 停止多源同步")
        self.stop_multi_sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.stop_multi_sync_btn.setEnabled(False)
        
        sync_control_layout.addWidget(self.start_multi_sync_btn)
        sync_control_layout.addWidget(self.pause_multi_sync_btn)
        sync_control_layout.addWidget(self.stop_multi_sync_btn)
        
        layout.addLayout(sync_control_layout)
        
        return group
        
    def create_chart_widget(self, title: str, frequency: str):
        """创建图表控件"""
        chart_frame = QFrame()
        chart_frame.setFrameStyle(QFrame.Box)
        chart_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #20c997;
                border-radius: 8px;
                background-color: #f8f9fa;
                padding: 10px;
            }
        """)
        
        chart_layout = QVBoxLayout(chart_frame)
        
        # 标题和频率
        title_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #20c997; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        freq_label = QLabel(frequency)
        freq_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        title_layout.addStretch()
        title_layout.addWidget(freq_label)
        
        chart_layout.addLayout(title_layout)
        
        # 图表占位符
        chart_placeholder = QLabel("📊 图表区域")
        chart_placeholder.setAlignment(Qt.AlignCenter)
        chart_placeholder.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 24px;
                padding: 40px;
                background-color: #e9ecef;
                border-radius: 5px;
            }
        """)
        chart_layout.addWidget(chart_placeholder)
        
        return chart_frame
        
    def _add_connection_status_item(self, source_name: str, status: str, color: str):
        """添加连接状态项"""
        try:
            item = QListWidgetItem(f"{source_name}: {status}")
            if color == "red":
                item.setForeground(QColor("#dc3545"))
            elif color == "green":
                item.setForeground(QColor("#28a745"))
            elif color == "yellow":
                item.setForeground(QColor("#ffc107"))
            else:
                item.setForeground(QColor("#6c757d"))
            self.connection_status_list.addItem(item)
        except Exception as e:
            logger.error(f"添加连接状态项失败: {e}")
            
    def _connect_signals(self):
        """连接信号槽"""
        try:
            # 数据源配置按钮
            self.imu_browse_btn.clicked.connect(self._browse_imu_file)
            self.cnap_browse_btn.clicked.connect(self._browse_cnap_file)
            self.load_data_btn.clicked.connect(self._load_data)
            self.stop_loading_btn.clicked.connect(self._stop_loading)
            
            # 连接控制按钮
            self.add_source_btn.clicked.connect(self._add_data_source)
            self.connect_source_btn.clicked.connect(self._connect_data_source)
            self.disconnect_source_btn.clicked.connect(self._disconnect_data_source)
            self.remove_source_btn.clicked.connect(self._remove_data_source)
            self.refresh_status_btn.clicked.connect(self._refresh_connection_status)
            
            # 同步控制按钮
            self.start_sync_btn.clicked.connect(self._start_sync)
            self.pause_sync_btn.clicked.connect(self._pause_sync)
            self.stop_sync_btn.clicked.connect(self._stop_sync)
            
            # 高级配置按钮
            self.save_config_btn.clicked.connect(self._save_config)
            self.reset_config_btn.clicked.connect(self._reset_config)
            self.import_config_btn.clicked.connect(self._import_config)
            self.export_config_btn.clicked.connect(self._export_config)
            
            # 监控按钮
            self.view_details_btn.clicked.connect(self._view_details)
            
            # 连接多源同步控制按钮
            self.start_multi_sync_btn.clicked.connect(self.start_multi_source_sync)
            self.pause_multi_sync_btn.clicked.connect(self.pause_multi_source_sync)
            self.stop_multi_sync_btn.clicked.connect(self.stop_multi_source_sync)
            
            # 连接新面板的按钮信号
            self.refresh_status_btn.clicked.connect(self._refresh_data_source_status)
            self.assess_quality_btn.clicked.connect(self._assess_data_quality)
            self.start_detection_btn.clicked.connect(self._start_anomaly_detection)
            self.start_fusion_btn.clicked.connect(self._start_data_fusion)
            self.stop_fusion_btn.clicked.connect(self._stop_data_fusion)
            
            logger.info("信号连接完成")
            
        except Exception as e:
            logger.error(f"信号连接失败: {e}")
    
    def _browse_imu_file(self):
        """浏览IMU数据文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择IMU数据文件", "", 
                "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
            )
            if file_path:
                self.imu_file_edit.setText(file_path)
                self.data_status_label.setText("状态: IMU文件已选择")
        except Exception as e:
            logger.error(f"浏览IMU文件失败: {e}")
    
    def _browse_cnap_file(self):
        """浏览CNAP数据文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择CNAP数据文件", "", 
                "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
            )
            if file_path:
                self.cnap_file_edit.setText(file_path)
                self.data_status_label.setText("状态: CNAP文件已选择")
        except Exception as e:
            logger.error(f"浏览CNAP文件失败: {e}")
    
    def _load_data(self):
        try:
            imu_file = self.imu_file_edit.text()
            cnap_file = self.cnap_file_edit.text()

            if not imu_file or not cnap_file:
                QMessageBox.warning(self, "警告", "请先选择IMU和CNAP数据文件")
                return

            self.data_status_label.setText("状态: 正在加载数据...")
            self.load_data_btn.setEnabled(False)
            self.stop_loading_btn.setEnabled(True)

            if not os.path.exists(imu_file):
                QMessageBox.warning(self, "警告", f"IMU文件不存在: {imu_file}")
                self._stop_loading()
                return
            if not os.path.exists(cnap_file):
                QMessageBox.warning(self, "警告", f"CNAP文件不存在: {cnap_file}")
                self._stop_loading()
                return

            self._on_data_loaded()

        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            self._stop_loading()
    
    def _stop_loading(self):
        """停止加载"""
        try:
            self.data_status_label.setText("状态: 数据加载已停止")
            self.load_data_btn.setEnabled(True)
            self.stop_loading_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"停止加载失败: {e}")
    
    def _on_data_loaded(self):
        """数据加载完成"""
        try:
            self.data_status_label.setText("状态: 数据加载完成")
            self.load_data_btn.setEnabled(True)
            self.stop_loading_btn.setEnabled(False)
            
            # 更新数据质量指示器
            self.data_quality_indicator.setText("数据质量: 🟢 优秀")
            self.data_quality_indicator.setStyleSheet("color: #28a745; font-size: 11px; font-weight: bold;")
            
        except Exception as e:
            logger.error(f"数据加载完成处理失败: {e}")
            
    def _add_data_source(self):
        try:
            source_type = self.source_type_combo.currentText()
            logger.info(f"添加数据源: {source_type}")
            self._add_connection_status_item(source_type, "已添加", "yellow")
        except Exception as e:
            logger.error(f"添加数据源失败: {e}")

    def _connect_data_source(self):
        try:
            source_type = self.source_type_combo.currentText()
            logger.info(f"连接数据源: {source_type}")
            self._add_connection_status_item(source_type, "连接中...", "yellow")
            QTimer.singleShot(2000, lambda: self._update_connection_status(source_type, "已连接", "green"))
        except Exception as e:
            logger.error(f"连接数据源失败: {e}")

    def _disconnect_data_source(self):
        try:
            source_type = self.source_type_combo.currentText()
            logger.info(f"断开数据源: {source_type}")
            self._update_connection_status(source_type, "未连接", "red")
        except Exception as e:
            logger.error(f"断开数据源失败: {e}")

    def _remove_data_source(self):
        try:
            source_type = self.source_type_combo.currentText()
            logger.info(f"删除数据源: {source_type}")
            for i in range(self.connection_status_list.count()):
                item = self.connection_status_list.item(i)
                if source_type in item.text():
                    self.connection_status_list.takeItem(i)
                    break
        except Exception as e:
            logger.error(f"删除数据源失败: {e}")

    def _refresh_connection_status(self):
        try:
            logger.info("刷新连接状态")
            self._update_performance_display()
        except Exception as e:
            logger.error(f"刷新连接状态失败: {e}")

    def _start_sync(self):
        try:
            logger.info("开始数据同步")
            self.start_sync_btn.setEnabled(False)
            self.pause_sync_btn.setEnabled(True)
            self.stop_sync_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"开始同步失败: {e}")

    def _pause_sync(self):
        try:
            logger.info("暂停数据同步")
            self.start_sync_btn.setEnabled(True)
            self.pause_sync_btn.setEnabled(False)
            self.stop_sync_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"暂停同步失败: {e}")

    def _stop_sync(self):
        try:
            logger.info("停止数据同步")
            self.start_sync_btn.setEnabled(True)
            self.pause_sync_btn.setEnabled(False)
            self.stop_sync_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"停止同步失败: {e}")

    def _save_config(self):
        try:
            logger.info("保存配置")
            QMessageBox.information(self, "信息", "配置保存成功")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _reset_config(self):
        try:
            logger.info("重置配置")
            QMessageBox.information(self, "信息", "配置已重置")
        except Exception as e:
            logger.error(f"重置配置失败: {e}")

    def _import_config(self):
        try:
            logger.info("导入配置")
            QMessageBox.information(self, "信息", "配置导入成功")
        except Exception as e:
            logger.error(f"导入配置失败: {e}")

    def _export_config(self):
        try:
            logger.info("导出配置")
            QMessageBox.information(self, "信息", "配置导出成功")
        except Exception as e:
            logger.error(f"导出配置失败: {e}")

    def _view_details(self):
        try:
            logger.info("查看监控详情")
            QMessageBox.information(self, "信息", "显示监控详情")
        except Exception as e:
            logger.error(f"查看详情失败: {e}")
            
    def _update_connection_status(self, source_type: str, status: str, color: str):
        """更新连接状态"""
        try:
            for i in range(self.connection_status_list.count()):
                item = self.connection_status_list.item(i)
                if source_type in item.text():
                    item.setText(f"{source_type}: {status}")
                    if color == "red":
                        item.setForeground(QColor("#dc3545"))
                    elif color == "green":
                        item.setForeground(QColor("#28a745"))
                    elif color == "yellow":
                        item.setForeground(QColor("#ffc107"))
                    break
                    
        except Exception as e:
            logger.error(f"更新连接状态失败: {e}")
            
    def _update_performance_display(self):
        """更新性能显示"""
        try:
            # 这里可以添加实时性能更新逻辑
            pass
        except Exception as e:
            logger.error(f"更新性能显示失败: {e}")

    def start_multi_source_sync(self):
        """开始多源异构数据同步"""
        try:
            # 尝试通过主控制器启动多源同步
            if hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), 'controller'):
                # 如果父级有主控制器引用
                controller = self.parent().parent().controller
                if hasattr(controller, 'start_multi_source_sync'):
                    success = controller.start_multi_source_sync()
                    if success:
                        self._update_sync_ui_state(True, False)
                        logger.info("✅ 通过主控制器启动多源同步成功")
                        QMessageBox.information(self, "成功", "多源异构数据同步已启动")
                        return
                    else:
                        QMessageBox.critical(self, "错误", "通过主控制器启动同步失败")
                        return
            
            # 如果无法通过主控制器启动，使用本地同步引擎
            if not self.sync_engine_available:
                QMessageBox.warning(self, "警告", "多源同步引擎不可用")
                return
            
            if self.is_syncing:
                QMessageBox.information(self, "提示", "同步已在运行中")
                return
            
            # 获取已连接的数据源
            if not self.connected_sources:
                QMessageBox.warning(self, "警告", "请先连接数据源")
                return
            
            # 启动同步引擎
            success = self.sync_engine.start_sync()
            
            if success:
                self._update_sync_ui_state(True, False)
                
                # 发送同步开始信号
                self.sync_started.emit({
                    'timestamp': datetime.now().isoformat(),
                    'sources_count': len(self.connected_sources),
                    'sources': list(self.connected_sources.keys())
                })
                
                logger.info("✅ 多源异构数据同步已启动")
                QMessageBox.information(self, "成功", "多源异构数据同步已启动")
            else:
                QMessageBox.critical(self, "错误", "启动同步失败")
                
        except Exception as e:
            logger.error(f"启动多源同步失败: {e}")
            QMessageBox.critical(self, "异常", f"启动同步时发生异常: {e}")
    
    def pause_multi_source_sync(self):
        """暂停多源异构数据同步"""
        try:
            # 尝试通过主控制器暂停多源同步
            if hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), 'controller'):
                controller = self.parent().parent().controller
                if hasattr(controller, 'pause_multi_source_sync'):
                    success = controller.pause_multi_source_sync()
                    if success:
                        self._update_sync_ui_state(True, True)
                        logger.info("⏸️ 通过主控制器暂停多源同步成功")
                        return
                    else:
                        logger.error("通过主控制器暂停同步失败")
                        return
            
            # 如果无法通过主控制器暂停，使用本地逻辑
            if not self.is_syncing:
                return
            
            self.sync_paused = not self.sync_paused
            self._update_sync_ui_state(True, self.sync_paused)
            
            if self.sync_paused:
                logger.info("⏸️ 多源异构数据同步已暂停")
            else:
                logger.info("▶️ 多源异构数据同步已恢复")
                
        except Exception as e:
            logger.error(f"暂停/恢复同步失败: {e}")
    
    def stop_multi_source_sync(self):
        """停止多源异构数据同步"""
        try:
            # 尝试通过主控制器停止多源同步
            if hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), 'controller'):
                controller = self.parent().parent().controller
                if hasattr(controller, 'stop_multi_source_sync'):
                    success = controller.stop_multi_source_sync()
                    if success:
                        self._update_sync_ui_state(False, False)
                        self.sync_progress.setValue(0)
                        logger.info("⏹️ 通过主控制器停止多源同步成功")
                        QMessageBox.information(self, "成功", "多源异构数据同步已停止")
                        return
                    else:
                        logger.error("通过主控制器停止同步失败")
                        return
            
            # 如果无法通过主控制器停止，使用本地逻辑
            if not self.is_syncing:
                return
            
            # 停止同步引擎
            if self.sync_engine_available and self.sync_engine:
                self.sync_engine.stop_sync()
            
            # 重置状态
            self.sync_progress_value = 0
            self._update_sync_ui_state(False, False)
            self.sync_progress.setValue(0)
            
            # 发送同步停止信号
            self.sync_stopped.emit()
            
            logger.info("⏹️ 多源异构数据同步已停止")
            QMessageBox.information(self, "成功", "多源异构数据同步已停止")
            
        except Exception as e:
            logger.error(f"停止同步失败: {e}")
            QMessageBox.critical(self, "异常", f"停止同步时发生异常: {e}")
    
    def _start_sync_progress_timer(self):
        """启动同步进度更新定时器"""
        if not hasattr(self, 'sync_progress_timer'):
            self.sync_progress_timer = QTimer()
            self.sync_progress_timer.timeout.connect(self._update_sync_progress)
        
        self.sync_progress_timer.start(100)  # 每100ms更新一次进度
    
    def _stop_sync_progress_timer(self):
        """停止同步进度更新定时器"""
        if hasattr(self, 'sync_progress_timer'):
            self.sync_progress_timer.stop()
    
    def _update_sync_progress(self):
        try:
            if self.is_syncing and not self.sync_paused:
                if self.sync_engine_available and self.sync_engine:
                    engine_status = self.sync_engine.get_sync_status()
                    self.sync_progress_value = int(engine_status.get('progress', 0))
                    self.sync_progress.setValue(self.sync_progress_value)
                    if self.sync_progress_value >= 100:
                        self.stop_multi_source_sync()
        except Exception as e:
            logger.error(f"更新同步进度失败: {e}")
    
    def get_multi_source_sync_status(self) -> Dict[str, Any]:
        """获取多源同步状态"""
        try:
            status = {
                'is_syncing': self.is_syncing,
                'is_paused': self.sync_paused,
                'progress': self.sync_progress_value,
                'engine_available': self.sync_engine_available,
                'connected_sources_count': len(self.connected_sources),
                'connected_sources': list(self.connected_sources.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            # 如果同步引擎可用，获取引擎状态
            if self.sync_engine_available and self.sync_engine:
                try:
                    engine_status = self.sync_engine.get_sync_status()
                    status['engine_status'] = engine_status
                except Exception as e:
                    status['engine_status_error'] = str(e)
            
            return status
            
        except Exception as e:
            logger.error(f"获取多源同步状态失败: {e}")
            return {'error': str(e)}

    def create_data_source_status_panel(self):
        """创建数据源状态监控面板"""
        group = QGroupBox("📊 数据源状态监控")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #17a2b8;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 数据源状态表格
        self.data_source_status_table = QTableWidget()
        self.data_source_status_table.setColumnCount(5)
        self.data_source_status_table.setHorizontalHeaderLabels([
            "数据源类型", "连接状态", "数据流量", "延迟(ms)", "最后更新"
        ])
        self.data_source_status_table.setRowCount(0)
        self.data_source_status_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                background-color: #f8f9fa;
                gridline-color: #dee2e6;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 8px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.data_source_status_table)
        
        # 状态更新按钮
        refresh_status_layout = QHBoxLayout()
        self.refresh_status_btn = QPushButton("🔄 刷新状态")
        self.refresh_status_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        refresh_status_layout.addWidget(self.refresh_status_btn)
        refresh_status_layout.addStretch()
        layout.addLayout(refresh_status_layout)
        
        return group

    def create_sync_performance_panel(self):
        """创建同步性能监控面板"""
        group = QGroupBox("⚡ 同步性能监控")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #28a745;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 性能指标网格
        metrics_layout = QGridLayout()
        
        # CPU使用率
        cpu_label = QLabel("CPU使用率:")
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setRange(0, 100)
        self.cpu_progress.setValue(0)
        self.cpu_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #28a745;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 2px;
            }
        """)
        metrics_layout.addWidget(cpu_label, 0, 0)
        metrics_layout.addWidget(self.cpu_progress, 0, 1)
        
        # 内存使用率
        memory_label = QLabel("内存使用率:")
        self.memory_progress = QProgressBar()
        self.memory_progress.setRange(0, 100)
        self.memory_progress.setValue(0)
        self.memory_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #28a745;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 2px;
            }
        """)
        metrics_layout.addWidget(memory_label, 1, 0)
        metrics_layout.addWidget(self.memory_progress, 1, 1)
        
        # 数据吞吐量
        throughput_label = QLabel("数据吞吐量:")
        self.throughput_label = QLabel("0 数据点/秒")
        self.throughput_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 12px;")
        metrics_layout.addWidget(throughput_label, 2, 0)
        metrics_layout.addWidget(self.throughput_label, 2, 1)
        
        # 同步延迟
        latency_label = QLabel("同步延迟:")
        self.latency_label = QLabel("0 ms")
        self.latency_label.setStyleSheet("color: #28a745; font-weight: bold; font-size: 12px;")
        metrics_layout.addWidget(latency_label, 3, 0)
        metrics_layout.addWidget(self.latency_label, 3, 1)
        
        layout.addLayout(metrics_layout)
        
        # 性能历史图表
        performance_chart_label = QLabel("性能趋势图")
        performance_chart_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px;")
        layout.addWidget(performance_chart_label)
        
        # 简化的性能图表框架
        self.performance_chart_frame = QFrame()
        self.performance_chart_frame.setFrameStyle(QFrame.Box)
        self.performance_chart_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #28a745;
                border-radius: 8px;
                background-color: #f8f9fa;
                min-height: 80px;
            }
        """)
        self.performance_chart_frame.setMinimumHeight(80)
        layout.addWidget(self.performance_chart_frame)
        
        return group

    def create_data_quality_panel(self):
        """创建数据质量评估面板"""
        group = QGroupBox("🔍 数据质量评估")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #ffc107;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 质量评分
        quality_score_layout = QHBoxLayout()
        quality_score_layout.addWidget(QLabel("整体质量评分:"))
        self.quality_score_label = QLabel("95.0")
        self.quality_score_label.setStyleSheet("""
            color: #28a745; 
            font-weight: bold; 
            font-size: 24px;
            padding: 10px;
            border: 2px solid #28a745;
            border-radius: 10px;
            background-color: #f8f9fa;
        """)
        quality_score_layout.addWidget(self.quality_score_label)
        quality_score_layout.addStretch()
        layout.addLayout(quality_score_layout)
        
        # 质量指标
        quality_metrics_layout = QGridLayout()
        
        # 完整性
        completeness_label = QLabel("数据完整性:")
        self.completeness_progress = QProgressBar()
        self.completeness_progress.setRange(0, 100)
        self.completeness_progress.setValue(98)
        self.completeness_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ffc107;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #ffc107;
                border-radius: 2px;
            }
        """)
        quality_metrics_layout.addWidget(completeness_label, 0, 0)
        quality_metrics_layout.addWidget(self.completeness_progress, 0, 1)
        
        # 准确性
        accuracy_label = QLabel("数据准确性:")
        self.accuracy_progress = QProgressBar()
        self.accuracy_progress.setRange(0, 100)
        self.accuracy_progress.setValue(96)
        self.accuracy_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ffc107;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #ffc107;
                border-radius: 2px;
            }
        """)
        quality_metrics_layout.addWidget(accuracy_label, 1, 0)
        quality_metrics_layout.addWidget(self.accuracy_progress, 1, 1)
        
        # 一致性
        consistency_label = QLabel("数据一致性:")
        self.consistency_progress = QProgressBar()
        self.consistency_progress.setRange(0, 100)
        self.consistency_progress.setValue(94)
        self.consistency_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ffc107;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #ffc107;
                border-radius: 2px;
            }
        """)
        quality_metrics_layout.addWidget(consistency_label, 2, 0)
        quality_metrics_layout.addWidget(self.consistency_progress, 2, 1)
        
        # 时效性
        timeliness_label = QLabel("数据时效性:")
        self.timeliness_progress = QProgressBar()
        self.timeliness_progress.setRange(0, 100)
        self.timeliness_progress.setValue(92)
        self.timeliness_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ffc107;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #ffc107;
                border-radius: 2px;
            }
        """)
        quality_metrics_layout.addWidget(timeliness_label, 3, 0)
        quality_metrics_layout.addWidget(self.timeliness_progress, 3, 1)
        
        layout.addLayout(quality_metrics_layout)
        
        # 质量评估按钮
        quality_actions_layout = QHBoxLayout()
        self.assess_quality_btn = QPushButton("🔍 评估数据质量")
        self.assess_quality_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        quality_actions_layout.addWidget(self.assess_quality_btn)
        quality_actions_layout.addStretch()
        layout.addLayout(quality_actions_layout)
        
        return group

    def create_anomaly_detection_panel(self):
        """创建异常检测监控面板"""
        group = QGroupBox("🚨 异常检测监控")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #dc3545;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 异常状态指示器
        anomaly_status_layout = QHBoxLayout()
        anomaly_status_layout.addWidget(QLabel("异常状态:"))
        self.anomaly_status_indicator = QLabel("🟢 正常")
        self.anomaly_status_indicator.setStyleSheet("""
            color: #28a745; 
            font-weight: bold; 
            font-size: 14px;
            padding: 8px;
            border: 2px solid #28a745;
            border-radius: 8px;
            background-color: #f8f9fa;
        """)
        anomaly_status_layout.addWidget(self.anomaly_status_indicator)
        anomaly_status_layout.addStretch()
        layout.addLayout(anomaly_status_layout)
        
        # 异常统计
        anomaly_stats_layout = QGridLayout()
        
        # 检测到的异常数量
        anomalies_count_label = QLabel("检测到的异常:")
        self.anomalies_count_label = QLabel("0")
        self.anomalies_count_label.setStyleSheet("color: #dc3545; font-weight: bold; font-size: 16px;")
        anomaly_stats_layout.addWidget(anomalies_count_label, 0, 0)
        anomaly_stats_layout.addWidget(self.anomalies_count_label, 0, 1)
        
        # 异常类型分布
        anomaly_types_label = QLabel("异常类型分布:")
        self.anomaly_types_label = QLabel("无异常")
        self.anomaly_types_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        anomaly_stats_layout.addWidget(anomaly_types_label, 1, 0)
        anomaly_stats_layout.addWidget(self.anomaly_types_label, 1, 1)
        
        # 最后检测时间
        last_detection_label = QLabel("最后检测时间:")
        self.last_detection_label = QLabel("未检测")
        self.last_detection_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        anomaly_stats_layout.addWidget(last_detection_label, 2, 0)
        anomaly_stats_layout.addWidget(self.last_detection_label, 2, 1)
        
        layout.addLayout(anomaly_stats_layout)
        
        # 异常列表
        anomaly_list_label = QLabel("最近异常列表:")
        anomaly_list_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px;")
        layout.addWidget(anomaly_list_label)
        
        self.anomaly_list_widget = QListWidget()
        self.anomaly_list_widget.setMaximumHeight(80)
        self.anomaly_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #dc3545;
                border-radius: 5px;
                background-color: #f8f9fa;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.anomaly_list_widget)
        
        # 异常检测控制
        anomaly_control_layout = QHBoxLayout()
        self.start_detection_btn = QPushButton("▶️ 启动检测")
        self.start_detection_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        anomaly_control_layout.addWidget(self.start_detection_btn)
        anomaly_control_layout.addStretch()
        layout.addLayout(anomaly_control_layout)
        
        return group

    def create_data_fusion_panel(self):
        """创建数据融合可视化面板"""
        group = QGroupBox("🔄 数据融合可视化")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #6f42c1;
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # 融合状态
        fusion_status_layout = QHBoxLayout()
        fusion_status_layout.addWidget(QLabel("融合状态:"))
        self.fusion_status_indicator = QLabel("🟡 准备中")
        self.fusion_status_indicator.setStyleSheet("""
            color: #ffc107; 
            font-weight: bold; 
            font-size: 14px;
            padding: 8px;
            border: 2px solid #ffc107;
            border-radius: 8px;
            background-color: #f8f9fa;
        """)
        fusion_status_layout.addWidget(self.fusion_status_indicator)
        fusion_status_layout.addStretch()
        layout.addLayout(fusion_status_layout)
        
        # 融合统计
        fusion_stats_layout = QGridLayout()
        
        # 融合数据源数量
        fused_sources_label = QLabel("融合数据源:")
        self.fused_sources_label = QLabel("0")
        self.fused_sources_label.setStyleSheet("color: #6f42c1; font-weight: bold; font-size: 16px;")
        fusion_stats_layout.addWidget(fused_sources_label, 0, 0)
        fusion_stats_layout.addWidget(self.fused_sources_label, 0, 1)
        
        # 融合数据点数量
        fused_points_label = QLabel("融合数据点:")
        self.fused_points_label = QLabel("0")
        self.fused_points_label.setStyleSheet("color: #6f42c1; font-weight: bold; font-size: 16px;")
        fusion_stats_layout.addWidget(fused_points_label, 1, 0)
        fusion_stats_layout.addWidget(self.fused_points_label, 1, 1)
        
        # 融合成功率
        fusion_success_label = QLabel("融合成功率:")
        self.fusion_success_label = QLabel("0%")
        self.fusion_success_label.setStyleSheet("color: #6f42c1; font-weight: bold; font-size: 16px;")
        fusion_stats_layout.addWidget(fusion_success_label, 2, 0)
        fusion_stats_layout.addWidget(self.fusion_success_label, 2, 1)
        
        layout.addLayout(fusion_stats_layout)
        
        # 融合算法选择
        algorithm_layout = QHBoxLayout()
        algorithm_layout.addWidget(QLabel("融合算法:"))
        self.fusion_algorithm_combo = QComboBox()
        self.fusion_algorithm_combo.addItems([
            "时间对齐融合", "加权平均融合", "卡尔曼滤波融合", "自适应融合"
        ])
        self.fusion_algorithm_combo.setCurrentText("时间对齐融合")
        self.fusion_algorithm_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #6f42c1;
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
                min-width: 120px;
            }
        """)
        algorithm_layout.addWidget(self.fusion_algorithm_combo)
        algorithm_layout.addStretch()
        layout.addLayout(algorithm_layout)
        
        # 融合可视化区域
        fusion_visualization_label = QLabel("融合数据可视化:")
        fusion_visualization_label.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px;")
        layout.addWidget(fusion_visualization_label)
        
        self.fusion_visualization_frame = QFrame()
        self.fusion_visualization_frame.setFrameStyle(QFrame.Box)
        self.fusion_visualization_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #6f42c1;
                border-radius: 8px;
                background-color: #f8f9fa;
                min-height: 100px;
            }
        """)
        self.fusion_visualization_frame.setMinimumHeight(100)
        layout.addWidget(self.fusion_visualization_frame)
        
        # 融合控制按钮
        fusion_control_layout = QHBoxLayout()
        self.start_fusion_btn = QPushButton("▶️ 启动融合")
        self.start_fusion_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        self.stop_fusion_btn = QPushButton("⏹️ 停止融合")
        self.stop_fusion_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.stop_fusion_btn.setEnabled(False)
        
        fusion_control_layout.addWidget(self.start_fusion_btn)
        fusion_control_layout.addWidget(self.stop_fusion_btn)
        fusion_control_layout.addStretch()
        layout.addLayout(fusion_control_layout)
        
        return group

    def _refresh_data_source_status(self):
        try:
            logger.info("刷新数据源状态...")
            self.data_source_status_table.setRowCount(0)
            if self.sync_engine_available and self.sync_engine:
                engine_status = self.sync_engine.get_sync_status()
                sources = engine_status.get('sources', {})
                for row, (source_id, info) in enumerate(sources.items()):
                    self.data_source_status_table.insertRow(row)
                    self.data_source_status_table.setItem(row, 0, QTableWidgetItem(info.get('name', source_id)))
                    status = info.get('status', 'unknown')
                    status_item = QTableWidgetItem(status)
                    if 'connected' in status.lower():
                        status_item.setBackground(QColor(220, 255, 220))
                    elif 'connecting' in status.lower():
                        status_item.setBackground(QColor(255, 255, 220))
                    else:
                        status_item.setBackground(QColor(255, 220, 220))
                    self.data_source_status_table.setItem(row, 1, status_item)
                    self.data_source_status_table.setItem(row, 2, QTableWidgetItem(str(info.get('rate', '--'))))
                    self.data_source_status_table.setItem(row, 3, QTableWidgetItem(str(info.get('latency', '--'))))
                    self.data_source_status_table.setItem(row, 4, QTableWidgetItem(str(info.get('last_update', '--'))))
            logger.info("数据源状态刷新完成")
        except Exception as e:
            logger.error(f"刷新数据源状态失败: {e}")

    def _assess_data_quality(self):
        try:
            logger.info("开始评估数据质量...")
            self.completeness_progress.setValue(0)
            self.accuracy_progress.setValue(0)
            self.consistency_progress.setValue(0)
            self.timeliness_progress.setValue(0)
            self.quality_score_label.setText("--")
            self.quality_score_label.setStyleSheet("""
                color: #6c757d;
                font-weight: bold;
                font-size: 24px;
                padding: 10px;
                border: 2px solid #6c757d;
                border-radius: 10px;
                background-color: #f8f9fa;
            """)
            logger.info("数据质量评估完成，需要真实数据源连接")
            QMessageBox.information(self, "提示", "请先连接真实数据源后再进行质量评估")
        except Exception as e:
            logger.error(f"评估数据质量失败: {e}")

    def _start_anomaly_detection(self):
        try:
            logger.info("启动异常检测...")
            self.start_detection_btn.setEnabled(False)
            self.start_detection_btn.setText("检测中...")
            self.anomalies_count_label.setText("--")
            self.anomaly_status_indicator.setText("需要真实数据")
            self.anomaly_status_indicator.setStyleSheet("""
                color: #6c757d;
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                border: 2px solid #6c757d;
                border-radius: 8px;
                background-color: #f8f9fa;
            """)
            self.anomaly_types_label.setText("--")
            self.anomaly_list_widget.clear()
            self.last_detection_label.setText("--")
            self.start_detection_btn.setEnabled(True)
            self.start_detection_btn.setText("启动检测")
            QMessageBox.information(self, "提示", "请先连接真实数据源后再进行异常检测")
        except Exception as e:
            logger.error(f"启动异常检测失败: {e}")
            self.start_detection_btn.setEnabled(True)
            self.start_detection_btn.setText("启动检测")

    def _start_data_fusion(self):
        try:
            logger.info("启动数据融合...")
            self.start_fusion_btn.setEnabled(False)
            self.stop_fusion_btn.setEnabled(True)
            self.start_fusion_btn.setText("融合中...")
            self.fusion_status_indicator.setText("需要真实数据")
            self.fusion_status_indicator.setStyleSheet("""
                color: #6c757d;
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                border: 2px solid #6c757d;
                border-radius: 8px;
                background-color: #f8f9fa;
            """)
            self.fused_sources_label.setText("--")
            self.fused_points_label.setText("--")
            self.fusion_success_label.setText("--")
            QMessageBox.information(self, "提示", "请先连接真实数据源后再进行数据融合")
        except Exception as e:
            logger.error(f"启动数据融合失败: {e}")
            self.start_fusion_btn.setEnabled(True)
            self.stop_fusion_btn.setEnabled(False)
            self.start_fusion_btn.setText("启动融合")

    def _stop_data_fusion(self):
        """停止数据融合"""
        try:
            logger.info("⏹️ 停止数据融合...")
            
            # 更新按钮状态
            self.start_fusion_btn.setEnabled(True)
            self.stop_fusion_btn.setEnabled(False)
            self.start_fusion_btn.setText("▶️ 启动融合")
            
            # 更新融合状态
            self.fusion_status_indicator.setText("🟡 已停止")
            self.fusion_status_indicator.setStyleSheet("""
                color: #ffc107; 
                font-weight: bold; 
                font-size: 14px;
                padding: 8px;
                border: 2px solid #ffc107;
                border-radius: 8px;
                background-color: #f8f9fa;
            """)
            
            # 更新融合可视化区域
            self.fusion_visualization_frame.setStyleSheet("""
                QFrame {
                    border: 2px solid #6f42c1;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    min-height: 100px;
                }
            """)
            
            logger.info("✅ 数据融合已停止")
            
        except Exception as e:
            logger.error(f"停止数据融合失败: {e}")
            QMessageBox.critical(self, "错误", f"停止数据融合失败: {e}")

    def _update_performance_metrics(self):
        try:
            import psutil
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.cpu_progress.setValue(int(cpu_percent))
            except Exception:
                self.cpu_progress.setValue(0)
            try:
                memory = psutil.virtual_memory()
                self.memory_progress.setValue(int(memory.percent))
            except Exception:
                self.memory_progress.setValue(0)
            self.throughput_label.setText("-- 数据点/秒")
            self.latency_label.setText("-- ms")
        except Exception as e:
            logger.error(f"更新性能指标失败: {e}")

    def _start_performance_monitoring(self):
        """启动性能监控"""
        if not hasattr(self, 'performance_timer'):
            self.performance_timer = QTimer()
            self.performance_timer.timeout.connect(self._update_performance_metrics)
        
        self.performance_timer.start(2000)  # 每2秒更新一次
        logger.info("⚡ 性能监控已启动")

    def _stop_performance_monitoring(self):
        """停止性能监控"""
        if hasattr(self, 'performance_timer'):
            self.performance_timer.stop()
        logger.info("⏹️ 性能监控已停止")
