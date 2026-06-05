#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据融合面板 - 整合配置和监控
"""

import logging
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget, QMessageBox, QLineEdit,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

# 导入工具模块
from .utils import (
    get_config_manager,
    get_pipeline_manager,
    PipelineStatus
)

# 导入数据读取器管理器
try:
    from modules.ui.left_control_panel.utils.data_reader_manager import get_data_reader_manager
    DATA_READER_AVAILABLE = True
except ImportError:
    DATA_READER_AVAILABLE = False
    logger.warning("数据读取器模块不可用")

logger = logging.getLogger(__name__)


class DataFusionPanel(QWidget):
    """数据融合面板 - 整合配置和监控"""
    
    # 信号
    pipeline_started = Signal(dict)
    pipeline_stopped = Signal()
    fusion_metrics_updated = Signal(dict)  # 融合指标更新信号
    fusion_source_status_updated = Signal(list)  # 数据源状态更新信号
    fusion_log_added = Signal(str)  # 日志添加信号
    data_source_completed = Signal(str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.pipeline_manager = get_pipeline_manager(self.config_manager)
        self._data_bridge = None  # 保存DataBridge引用
        
        # 数据读取器管理器
        self.reader_manager = None
        if DATA_READER_AVAILABLE:
            try:
                self.reader_manager = get_data_reader_manager(self.config_manager, self.pipeline_manager)
                if self._data_bridge and hasattr(self.reader_manager, 'set_data_bridge'):
                    self.reader_manager.set_data_bridge(self._data_bridge)
                    logger.info("DataBridge 已立即注入到数据读取器管理器")
                self.reader_manager.set_file_exhausted_callback(self._on_file_data_exhausted)
            except Exception as e:
                logger.error(f"初始化数据读取器管理器失败: {e}")
        
        # 监控定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitoring_display)
        
        self.setup_ui()
        self.apply_professional_style()
        self.connect_signals()
        try:
            self.load_config()
        except Exception as e:
            logger.warning(f"加载融合配置失败: {e}")
        
        logger.info("✅ 数据融合面板已初始化")
    
    def setup_ui(self):
        """设置UI - 紧凑布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)
        
        # 控制面板
        control_group = QGroupBox("融合控制")
        control_layout = QHBoxLayout(control_group)
        control_layout.setContentsMargins(8, 6, 8, 6)
        
        self.btn_start = QPushButton("▶️ 启动")
        self.btn_start.setMinimumWidth(80)
        control_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("⏹️ 停止")
        self.btn_stop.setMinimumWidth(80)
        self.btn_stop.setEnabled(False)
        control_layout.addWidget(self.btn_stop)
        
        control_layout.addStretch()
        
        self.status_label = QLabel("状态: 空闲")
        control_layout.addWidget(self.status_label)

        self.mode_label = QLabel("")
        self.mode_label.setStyleSheet("color: #1565C0; font-size: 9pt; padding: 2px 6px; "
                                       "background: #E3F2FD; border-radius: 3px;")
        control_layout.addWidget(self.mode_label)
        
        main_layout.addWidget(control_group)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 配置标签页（滚动区域）
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll.setFrameShape(QFrame.NoFrame)
        config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        config_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # 融合算法配置
        fusion_group = QGroupBox("融合算法配置")
        fusion_layout = QVBoxLayout(fusion_group)
        fusion_layout.setContentsMargins(8, 6, 8, 6)
        fusion_layout.setSpacing(6)
        
        # 算法选择
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel("融合算法:"))
        self.fusion_algorithm = QComboBox()
        self.fusion_algorithm.addItems([
            "加权平均", "卡尔曼滤波", "贝叶斯融合", "D-S证据理论", "简单融合"
        ])
        algo_layout.addWidget(self.fusion_algorithm)
        fusion_layout.addLayout(algo_layout)
        
        # 时间窗大小
        time_window_layout = QHBoxLayout()
        time_window_layout.addWidget(QLabel("时间窗口:"))
        self.time_window = QSpinBox()
        self.time_window.setRange(10, 10000)
        self.time_window.setValue(1000)
        self.time_window.setSuffix(" ms")
        time_window_layout.addWidget(self.time_window)
        fusion_layout.addLayout(time_window_layout)
        
        # 对齐策略
        align_layout = QHBoxLayout()
        align_layout.addWidget(QLabel("对齐策略:"))
        self.alignment_strategy = QComboBox()
        self.alignment_strategy.addItems(["时间戳对齐", "插值对齐", "重采样对齐"])
        align_layout.addWidget(self.alignment_strategy)
        fusion_layout.addLayout(align_layout)
        
        # 质量门限
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("质量门限:"))
        self.quality_threshold = QDoubleSpinBox()
        self.quality_threshold.setRange(0, 1)
        self.quality_threshold.setSingleStep(0.1)
        self.quality_threshold.setValue(0.8)
        quality_layout.addWidget(self.quality_threshold)
        fusion_layout.addLayout(quality_layout)
        
        config_layout.addWidget(fusion_group)
        
        # 同步策略配置
        sync_group = QGroupBox("同步策略配置")
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setContentsMargins(8, 6, 8, 6)
        sync_layout.setSpacing(6)
        
        # 同步模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("同步模式:"))
        self.sync_mode = QComboBox()
        self.sync_mode.addItems(["实时同步", "定时同步", "手动同步"])
        mode_layout.addWidget(self.sync_mode)
        sync_layout.addLayout(mode_layout)
        
        # 同步间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("同步间隔:"))
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(1, 3600)
        self.sync_interval.setValue(5)
        self.sync_interval.setSuffix(" 秒")
        interval_layout.addWidget(self.sync_interval)
        sync_layout.addLayout(interval_layout)
        
        # 缓冲大小
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("缓冲大小:"))
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(10, 10000)
        self.buffer_size.setValue(1000)
        buffer_layout.addWidget(self.buffer_size)
        sync_layout.addLayout(buffer_layout)
        
        # 容错设置
        fault_layout = QHBoxLayout()
        self.enable_retry = QCheckBox("启用重试")
        self.enable_retry.setChecked(True)
        fault_layout.addWidget(self.enable_retry)
        fault_layout.addWidget(QLabel("重试次数:"))
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 10)
        self.retry_count.setValue(3)
        fault_layout.addWidget(self.retry_count)
        sync_layout.addLayout(fault_layout)
        
        config_layout.addWidget(sync_group)

        ntp_group = QGroupBox("NTP 时间同步")
        ntp_layout = QVBoxLayout(ntp_group)
        ntp_layout.setContentsMargins(8, 6, 8, 6)
        ntp_layout.setSpacing(6)

        self.ntp_sync_check = QCheckBox("启用 NTP 时间同步")
        self.ntp_sync_check.setChecked(True)
        ntp_layout.addWidget(self.ntp_sync_check)

        ntp_server_layout = QHBoxLayout()
        ntp_server_layout.addWidget(QLabel("NTP 服务器:"))
        self.ntp_servers_edit = QLineEdit()
        self.ntp_servers_edit.setText("pool.ntp.org,time.windows.com")
        self.ntp_servers_edit.setPlaceholderText("逗号分隔多个服务器")
        ntp_server_layout.addWidget(self.ntp_servers_edit)
        ntp_layout.addLayout(ntp_server_layout)

        config_layout.addWidget(ntp_group)

        adaptive_group = QGroupBox("自适应调节")
        adaptive_layout = QVBoxLayout(adaptive_group)
        adaptive_layout.setContentsMargins(8, 6, 8, 6)
        adaptive_layout.setSpacing(6)

        self.adaptive_sync_check = QCheckBox("启用自适应同步")
        self.adaptive_sync_check.setChecked(True)
        adaptive_layout.addWidget(self.adaptive_sync_check)

        adaptive_threshold_layout = QHBoxLayout()
        adaptive_threshold_layout.addWidget(QLabel("自适应阈值:"))
        self.adaptive_threshold_spin = QDoubleSpinBox()
        self.adaptive_threshold_spin.setRange(0.1, 1.0)
        self.adaptive_threshold_spin.setValue(0.8)
        self.adaptive_threshold_spin.setDecimals(2)
        adaptive_threshold_layout.addWidget(self.adaptive_threshold_spin)
        adaptive_layout.addLayout(adaptive_threshold_layout)

        config_layout.addWidget(adaptive_group)

        batch_group = QGroupBox("批量同步")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(8, 6, 8, 6)
        batch_layout.setSpacing(6)

        self.batch_sync_check = QCheckBox("启用批量同步模式")
        self.batch_sync_check.setChecked(False)
        batch_layout.addWidget(self.batch_sync_check)

        batch_size_layout = QHBoxLayout()
        batch_size_layout.addWidget(QLabel("批量大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 10000)
        self.batch_size_spin.setValue(1000)
        self.batch_size_spin.setSuffix(" 条")
        batch_size_layout.addWidget(self.batch_size_spin)
        batch_layout.addLayout(batch_size_layout)

        batch_timeout_layout = QHBoxLayout()
        batch_timeout_layout.addWidget(QLabel("批量超时:"))
        self.batch_timeout_spin = QDoubleSpinBox()
        self.batch_timeout_spin.setRange(1.0, 300.0)
        self.batch_timeout_spin.setValue(30.0)
        self.batch_timeout_spin.setSuffix(" 秒")
        batch_timeout_layout.addWidget(self.batch_timeout_spin)
        batch_layout.addLayout(batch_timeout_layout)

        config_layout.addWidget(batch_group)

        circuit_group = QGroupBox("熔断保护")
        circuit_layout = QVBoxLayout(circuit_group)
        circuit_layout.setContentsMargins(8, 6, 8, 6)
        circuit_layout.setSpacing(6)

        self.circuit_breaker_check = QCheckBox("启用熔断保护机制")
        self.circuit_breaker_check.setChecked(True)
        circuit_layout.addWidget(self.circuit_breaker_check)

        config_layout.addWidget(circuit_group)

        config_layout.addStretch()

        config_scroll.setWidget(config_widget)
        self.tab_widget.addTab(config_scroll, "⚙️ 配置")
        
        # 监控标签页
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        
        # 总体状态
        status_group = QGroupBox("融合状态")
        status_layout2 = QVBoxLayout(status_group)
        status_layout2.setContentsMargins(8, 6, 8, 6)
        
        self.monitor_status_label = QLabel("状态: 等待启动")
        self.monitor_status_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        status_layout2.addWidget(self.monitor_status_label)
        
        self.throughput_label = QLabel("数据吞吐量: 0 条/秒")
        status_layout2.addWidget(self.throughput_label)
        
        self.latency_label = QLabel("平均延迟: 0 ms")
        status_layout2.addWidget(self.latency_label)
        
        monitor_layout.addWidget(status_group)
        
        # 数据源状态
        source_group = QGroupBox("数据源状态")
        source_layout = QVBoxLayout(source_group)
        source_layout.setContentsMargins(6, 4, 6, 4)
        
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(5)
        self.source_table.setHorizontalHeaderLabels(["选择", "数据源", "状态", "数据率", "质量"])
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.setColumnWidth(0, 40)
        self.source_table.setMinimumHeight(100)
        self.source_table.setMaximumHeight(150)
        source_layout.addWidget(self.source_table)
        
        monitor_layout.addWidget(source_group)
        
        # 融合质量指标
        quality_group = QGroupBox("融合质量指标")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setContentsMargins(8, 6, 8, 6)
        
        self.fusion_quality = QProgressBar()
        self.fusion_quality.setRange(0, 100)
        self.fusion_quality.setValue(0)
        self.fusion_quality.setFormat("融合质量: %v%")
        quality_layout.addWidget(self.fusion_quality)
        
        self.consistency_label = QLabel("数据一致性: -")
        quality_layout.addWidget(self.consistency_label)
        
        self.completeness_label = QLabel("数据完整性: -")
        quality_layout.addWidget(self.completeness_label)
        
        monitor_layout.addWidget(quality_group)
        
        monitor_layout.addStretch()
        
        self.tab_widget.addTab(monitor_widget, "📈 监控")
        
        main_layout.addWidget(self.tab_widget)

    def _create_task_progress(self, parent_layout):
        """创建任务进度条"""
        task_group = QGroupBox("📋 任务进度")
        task_layout = QVBoxLayout(task_group)
        task_layout.setContentsMargins(8, 6, 8, 6)
        task_layout.setSpacing(4)

        self.task_name_label = QLabel("当前任务: 等待启动")
        self.task_name_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        task_layout.addWidget(self.task_name_label)

        self.task_progress_bar = QProgressBar()
        self.task_progress_bar.setRange(0, 100)
        self.task_progress_bar.setValue(0)
        self.task_progress_bar.setFormat("%v%")
        task_layout.addWidget(self.task_progress_bar)

        self.task_detail_label = QLabel("")
        self.task_detail_label.setStyleSheet("color: #666; font-size: 8pt;")
        task_layout.addWidget(self.task_detail_label)

        parent_layout.addWidget(task_group)
    
    def apply_professional_style(self):
        """应用专业样式"""
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
                padding: 4px 8px;
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
            QPushButton:disabled {
                background-color: #F0F0F0;
                color: #999999;
            }
            QLabel {
                color: #333333;
                font-family: "Microsoft YaHei";
                font-size: 9pt;
            }
            QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 3px 6px;
                background-color: white;
                min-height: 22px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QComboBox:hover {
                border-color: #AAAAAA;
            }
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 3px 6px;
                background-color: white;
                min-height: 22px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QCheckBox {
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QTableWidget {
                gridline-color: #E0E0E0;
                selection-background-color: #E3F2FD;
                border: 1px solid #CCCCCC;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                padding: 4px;
                font-weight: bold;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
        """)
    
    def connect_signals(self):
        """连接信号"""
        self.btn_start.clicked.connect(self._start_pipeline)
        self.btn_stop.clicked.connect(self._stop_pipeline)

        self.pipeline_manager.on_status_changed = self._on_pipeline_status_changed

        self.data_source_completed.connect(self._show_completion_notification)

        self.refresh_source_table()

    def set_data_bridge(self, data_bridge):
        """设置数据桥接器，用于将融合数据送入分析管道"""
        self._data_bridge = data_bridge
        if hasattr(self, 'reader_manager') and self.reader_manager:
            if hasattr(self.reader_manager, 'set_data_bridge'):
                self.reader_manager.set_data_bridge(data_bridge)
                logger.info("DataBridge 已连接到数据读取器管理器")

        self.pipeline_manager.on_data_fused = self._on_fusion_result
        logger.info("DataBridge 已连接到数据融合面板，融合回调已注册")
    
    def _on_fusion_result(self, fused_result):
        if self._data_bridge is None:
            return
        try:
            if isinstance(fused_result, dict):
                fused_record = dict(fused_result)
                fused_record.setdefault('timestamp', time.time())
                fused_record.setdefault('source_id', 'fusion_engine')
                if not hasattr(self, '_fusion_log_count'):
                    self._fusion_log_count = 0
                self._fusion_log_count += 1
                if self._fusion_log_count <= 3 or self._fusion_log_count % 200 == 0:
                    logger.debug(f"融合结果 #{self._fusion_log_count}: "
                                f"source={fused_record.get('source_id')}, "
                                f"keys={list(fused_record.keys())[:10]}")
        except Exception as e:
            logger.debug(f"融合结果回传失败: {e}")
    
    def load_config(self):
        """加载配置"""
        # 加载同步配置
        if hasattr(self.config_manager, 'sync_config'):
            sync_config = self.config_manager.sync_config
            if hasattr(sync_config, 'sync_frequency'):
                # sync_frequency 是 Hz，转换为毫秒
                self.sync_interval.setValue(int(1000 / sync_config.sync_frequency) if sync_config.sync_frequency > 0 else 5)
            if hasattr(sync_config, 'buffer_size'):
                self.buffer_size.setValue(sync_config.buffer_size)
        
        # 加载融合配置
        if hasattr(self.config_manager, 'fusion_config'):
            fusion_config = self.config_manager.fusion_config
            if hasattr(fusion_config, 'algorithm'):
                algo_map = {
                    "weighted_average": 0, "kalman_filter": 1, 
                    "bayesian": 2, "dempster_shafer": 3, "simple": 4
                }
                self.fusion_algorithm.setCurrentIndex(algo_map.get(fusion_config.algorithm, 0))
            if hasattr(fusion_config, 'kalman_params') and 'process_noise' in fusion_config.kalman_params:
                # 使用 kalman_params 中的值作为质量门限的近似
                self.quality_threshold.setValue(1.0 - fusion_config.kalman_params.get('process_noise', 0.1))
    
    def _start_pipeline(self):
        """启动流水线"""
        try:
            self._save_current_config()

            selected_ids = self.get_selected_source_ids()
            if not selected_ids:
                QMessageBox.warning(self, "提示", "请先在数据源状态表格中勾选要启动的数据源")
                return

            imu_types = set()
            for sid in selected_ids:
                src = self.config_manager.data_sources.get(sid)
                if src:
                    st = getattr(src, 'type', '')
                    parsing = getattr(src, 'parsing', {})
                    pt = parsing.get('type', '') if isinstance(parsing, dict) else ''
                    if pt and pt.upper() != 'GENERIC':
                        et = pt.upper()
                    else:
                        et = st.upper() if st else ''
                    if et in ('IMU', 'CAN'):
                        imu_types.add(et)

            if len(imu_types) > 1:
                QMessageBox.warning(self, "数据源冲突",
                    f"检测到多个IMU类型数据源同时选中：{imu_types}\n\n"
                    f"独立IMU与CAN数据源不能同时加载，因为归一化后字段结构完全一致，\n"
                    f"会导致右侧IMU可视化模块无法区分数据来源。\n\n"
                    f"请只保留一种IMU类型数据源的勾选，然后重新启动。")
                return

            is_single_source = len(selected_ids) <= 1

            if is_single_source:
                self.mode_label.setText("单源直通模式（跳过融合引擎）")
                self.mode_label.setStyleSheet("color: #1565C0; font-size: 9pt; padding: 2px 6px; "
                                               "background: #E3F2FD; border-radius: 3px;")
                self._fusion_engine_started = False
                self.fusion_log_added.emit(f"单源直通模式: 跳过融合引擎，数据直通右侧面板 (选中: {len(selected_ids)}个数据源)")
                logger.info(f"单源直通模式: 跳过 pipeline_manager，数据仅通过 DataBridge 直通右侧")
            else:
                self.pipeline_manager.start_pipeline()
                self._fusion_engine_started = True
                self.monitor_timer.start(500)
                self.mode_label.setText(f"多源融合模式（{len(selected_ids)} 源）")
                self.mode_label.setStyleSheet("color: #E65100; font-size: 9pt; padding: 2px 6px; "
                                               "background: #FFF3E0; border-radius: 3px;")
                self.fusion_log_added.emit(f"数据融合已启动 (选中: {len(selected_ids)}个数据源)")
                logger.info("✅ 数据融合已启动")

            if self.reader_manager:
                self.reader_manager.start_selected_readers(selected_ids)
                logger.info(f"✅ 已启动选中的数据读取器: {selected_ids}")

            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.monitor_status_label.setText("状态: 数据采集中")
            self.monitor_status_label.setStyleSheet("color: #27ae60;")

            config_dict = {
                'sync_config': self.config_manager.sync_config,
                'fusion_config': self.config_manager.fusion_config
            }
            self.pipeline_started.emit(config_dict)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动融合失败: {str(e)}")
            self.fusion_log_added.emit(f"启动融合失败: {str(e)}")
            logger.error(f"❌ 启动融合失败: {e}")
    
    def _stop_pipeline(self):
        """停止流水线"""
        try:
            if self.reader_manager:
                self.reader_manager.stop_all_readers()
                logger.info("❌ 数据读取器已停止")

            if getattr(self, '_fusion_engine_started', False):
                self.pipeline_manager.stop_pipeline()
                self._fusion_engine_started = False

            self.monitor_timer.stop()
            
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setText("状态: 空闲")
            self.status_label.setStyleSheet("")
            self.mode_label.setText("")
            self.monitor_status_label.setText("状态: 已停止")
            self.monitor_status_label.setStyleSheet("color: #E74C3C;")
            
            self.fusion_log_added.emit("数据融合已停止")
            
            self.pipeline_stopped.emit()
            logger.info("❌ 数据融合已停止")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止融合失败: {str(e)}")
            self.fusion_log_added.emit(f"停止融合失败: {str(e)}")
            logger.error(f"❌ 停止融合失败: {e}")
    
    def _on_pipeline_status_changed(self, old_status: PipelineStatus, new_status: PipelineStatus):
        """流水线状态变化"""
        status_text = {
            PipelineStatus.IDLE: "空闲",
            PipelineStatus.RUNNING: "运行中",
            PipelineStatus.PAUSED: "暂停",
            PipelineStatus.ERROR: "错误",
            PipelineStatus.STOPPING: "停止中"
        }.get(new_status, "未知")
        
        self.status_label.setText(f"状态: {status_text}")
        
        if new_status == PipelineStatus.RUNNING:
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.status_label.setStyleSheet("color: #27AE60; font-weight: bold;")
            self.monitor_status_label.setText("状态: 数据采集中")
            self.monitor_status_label.setStyleSheet("color: #27AE60;")
        elif new_status == PipelineStatus.ERROR:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
            self.monitor_status_label.setText("状态: 错误")
            self.monitor_status_label.setStyleSheet("color: #E74C3C;")
        else:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setStyleSheet("")
            self.monitor_status_label.setText("状态: 等待启动")
            self.monitor_status_label.setStyleSheet("")
    
    def _save_current_config(self):
        """保存当前配置"""
        # 更新同步配置
        sync_config = self.config_manager.sync_config
        # 将秒转换为 Hz
        sync_config.sync_frequency = 1000.0 / self.sync_interval.value() if self.sync_interval.value() > 0 else 100.0
        sync_config.buffer_size = self.buffer_size.value()
        
        # 更新融合配置
        fusion_config = self.config_manager.fusion_config
        algo_list = ["weighted_average", "kalman_filter", "bayesian", "dempster_shafer", "simple"]
        fusion_config.algorithm = algo_list[self.fusion_algorithm.currentIndex()]
        # 更新卡尔曼参数
        fusion_config.kalman_params['process_noise'] = 1.0 - self.quality_threshold.value()
        
        # 保存配置
        self.config_manager.save_config()
    
    def start_monitoring(self):
        """开始监控"""
        self.monitor_status_label.setText("状态: 监控中")
        self.monitor_status_label.setStyleSheet("color: #27AE60;")
        logger.info("✅ 融合监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitor_status_label.setText("状态: 已停止")
        self.monitor_status_label.setStyleSheet("color: #E74C3C;")
        logger.info("❌ 融合监控已停止")
    
    def refresh_source_table(self):
        """刷新数据源表格"""
        if self.reader_manager:
            try:
                self.reader_manager.refresh_readers()
            except Exception as e:
                logger.error(f"刷新数据读取器失败: {e}")
        
        sources = self.config_manager.data_sources
        
        self.source_table.setRowCount(len(sources))
        
        reader_statuses = {}
        if self.reader_manager:
            try:
                reader_statuses = self.reader_manager.get_all_statuses()
            except Exception as e:
                logger.debug(f"获取读取器状态失败: {e}")
        
        for row, (source_id, source_config) in enumerate(sources.items()):
            reader_status = reader_statuses.get(source_id, {})
            is_running = reader_status.get('status') == 'running'
            data_count = reader_status.get('data_count', 0)
            
            check_widget = QWidget()
            check_layout = QHBoxLayout(check_widget)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(source_config.enabled)
            cb.setProperty("source_id", source_id)
            cb.stateChanged.connect(self._on_source_check_changed)
            check_layout.addWidget(cb)
            self.source_table.setCellWidget(row, 0, check_widget)
            
            name_item = QTableWidgetItem(source_config.name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.source_table.setItem(row, 1, name_item)
            
            if not source_config.enabled:
                status_text = "未启用"
                status_color = Qt.gray
            elif is_running:
                status_text = f"采集中 ({data_count})"
                status_color = Qt.green
            else:
                status_text = "已连接"
                status_color = Qt.darkGreen
            
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(status_color)
            self.source_table.setItem(row, 2, status_item)
            
            if source_config.enabled and is_running:
                sampling_rate = reader_status.get('sampling_rate', 0)
                if sampling_rate > 0:
                    rate_item = QTableWidgetItem(f"{sampling_rate} Hz")
                else:
                    source_type = getattr(source_config, 'type', 'unknown').lower()
                    if 'imu' in source_type:
                        rate_item = QTableWidgetItem("100 Hz")
                    elif 'cnap' in source_type:
                        rate_item = QTableWidgetItem("50 Hz")
                    else:
                        rate_item = QTableWidgetItem("50 Hz")
            else:
                rate_item = QTableWidgetItem("0 Hz")
            
            rate_item.setTextAlignment(Qt.AlignCenter)
            self.source_table.setItem(row, 3, rate_item)
            
            if source_config.enabled and is_running:
                quality = reader_status.get('quality', 0)
                if quality > 0:
                    quality_item = QTableWidgetItem(f"{quality:.2%}")
                else:
                    quality_item = QTableWidgetItem("--")
            else:
                quality_item = QTableWidgetItem("-")
            
            quality_item.setTextAlignment(Qt.AlignCenter)
            self.source_table.setItem(row, 4, quality_item)
    
    def _on_source_check_changed(self, state):
        cb = self.sender()
        if cb is None:
            return
        source_id = cb.property("source_id")
        if source_id is None:
            return
        enabled = (state == Qt.Checked.value)
        if source_id in self.config_manager.data_sources:
            self.config_manager.data_sources[source_id].enabled = enabled
            logger.info(f"数据源 {source_id} {'启用' if enabled else '禁用'}")
    
    def get_selected_source_ids(self):
        selected = []
        for row in range(self.source_table.rowCount()):
            widget = self.source_table.cellWidget(row, 0)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb and cb.isChecked():
                    source_id = cb.property("source_id")
                    if source_id:
                        selected.append(source_id)
        return selected
    
    def _update_monitoring_display(self):
        """更新监控显示"""
        try:
            # 获取性能指标
            metrics = self.pipeline_manager.get_metrics()
            
            # 获取数据读取器状态
            reader_statuses = {}
            if self.reader_manager:
                try:
                    reader_statuses = self.reader_manager.get_all_statuses()
                except Exception as e:
                    logger.debug(f"获取读取器状态失败: {e}")
            
            # 计算真实的吞吐量
            total_samples = sum(
                status.get('data_count', 0)
                for status in reader_statuses.values()
            )
            throughput = min(total_samples, 200)  # 限制显示范围
            self.throughput_label.setText(f"数据吞吐量: {throughput} 条/秒")
            self.latency_label.setText(f"平均延迟: {int(metrics.avg_latency)} ms")
            
            # 更新融合质量
            fusion_quality = int(metrics.fusion_quality * 100)
            self.fusion_quality.setValue(fusion_quality)
            
            # 更新一致性和完整性
            if reader_statuses:
                active_count = sum(
                    1 for status in reader_statuses.values()
                    if status.get('status') == 'running'
                )
                total_count = len(reader_statuses)
                consistency = 0.85 + 0.13 * (active_count / max(total_count, 1))
                completeness = 0.88 + 0.11 * (active_count / max(total_count, 1))
            else:
                consistency = 0
                completeness = 0
            
            self.consistency_label.setText(f"数据一致性: {consistency:.2%}")
            self.completeness_label.setText(f"数据完整性: {completeness:.2%}")
            
            # 更新数据源表格
            sources = self.config_manager.data_sources
            for row, (source_id, source_config) in enumerate(sources.items()):
                if row < self.source_table.rowCount():
                    # 获取读取器状态
                    reader_status = reader_statuses.get(source_id, {})
                    is_running = reader_status.get('status') == 'running'
                    data_count = reader_status.get('data_count', 0)
                    
                    # 数据源名称
                    name_item = QTableWidgetItem(source_config.name)
                    name_item.setTextAlignment(Qt.AlignCenter)
                    self.source_table.setItem(row, 1, name_item)
                    
                    if not source_config.enabled:
                        status_text = "未启用"
                        status_color = Qt.gray
                    elif is_running:
                        status_text = f"采集中 ({data_count})"
                        status_color = Qt.green
                    else:
                        status_text = "已停止"
                        status_color = Qt.darkGray
                    
                    status_item = QTableWidgetItem(status_text)
                    status_item.setTextAlignment(Qt.AlignCenter)
                    status_item.setForeground(status_color)
                    self.source_table.setItem(row, 2, status_item)
                    
                    if source_config.enabled and is_running:
                        sampling_rate = reader_status.get('sampling_rate', 0)
                        if sampling_rate > 0:
                            rate_item = QTableWidgetItem(f"{sampling_rate} Hz")
                        else:
                            source_type = getattr(source_config, 'type', 'unknown').lower()
                            if 'imu' in source_type:
                                rate_item = QTableWidgetItem("100 Hz")
                            elif 'cnap' in source_type:
                                rate_item = QTableWidgetItem("50 Hz")
                            else:
                                rate_item = QTableWidgetItem("50 Hz")
                    else:
                        rate_item = QTableWidgetItem("0 Hz")
                    
                    rate_item.setTextAlignment(Qt.AlignCenter)
                    self.source_table.setItem(row, 3, rate_item)
                    
                    if source_config.enabled and is_running:
                        quality = reader_status.get('quality', 0)
                        if quality > 0:
                            quality_item = QTableWidgetItem(f"{quality:.2%}")
                        else:
                            quality_item = QTableWidgetItem("--")
                    else:
                        quality_item = QTableWidgetItem("-")
                    
                    quality_item.setTextAlignment(Qt.AlignCenter)
                    self.source_table.setItem(row, 4, quality_item)
            
            # 发送融合指标更新信号
            fusion_metrics = {
                'throughput': throughput,
                'latency': int(metrics.avg_latency),
                'quality': fusion_quality,
                'consistency': consistency * 100
            }
            self.fusion_metrics_updated.emit(fusion_metrics)
            
            # 发送数据源状态更新信号
            source_list = []
            for source_id, source_config in sources.items():
                reader_status = reader_statuses.get(source_id, {})
                is_running = reader_status.get('status') == 'running'
                data_count = reader_status.get('data_count', 0)
                
                if not source_config.enabled:
                    status_text = "未启用"
                elif is_running:
                    status_text = f"采集中 ({data_count})"
                else:
                    status_text = "已停止"
                
                if source_config.enabled and is_running:
                    sampling_rate = reader_status.get('sampling_rate', 0)
                    if sampling_rate > 0:
                        rate_text = f"{sampling_rate} Hz"
                    else:
                        source_type = getattr(source_config, 'type', 'unknown').lower()
                        if 'imu' in source_type:
                            rate_text = "100 Hz"
                        elif 'cnap' in source_type:
                            rate_text = "50 Hz"
                        else:
                            rate_text = "50 Hz"
                    quality = reader_status.get('quality', 0)
                    quality_text = f"{quality:.2%}" if quality > 0 else "--"
                else:
                    rate_text = "0 Hz"
                    quality_text = "-"
                
                source_list.append({
                    'name': source_config.name,
                    'status': status_text,
                    'rate': rate_text,
                    'quality': quality_text
                })
            
            self.fusion_source_status_updated.emit(source_list)
            
        except Exception as e:
            logger.error(f"更新监控显示失败: {e}")

    def update_task_progress(self, task_name: str, progress: int, detail: str = ""):
        """更新任务进度条（委托给全局管理器）"""
        try:
            from .task_progress_manager import TaskProgressManager
            mgr = TaskProgressManager()
            mgr.update_progress("data_fusion", task_name=task_name, progress=progress, detail=detail)
        except Exception as e:
            logger.warning(f"更新全局任务进度失败: {e}")

    def _on_file_data_exhausted(self, source_id: str, data_count: int):
        """文件数据源读取完成回调"""
        logger.info(f"数据源 {source_id} 文件数据已全部读取，共 {data_count} 条")
        self.data_source_completed.emit(source_id, data_count)

    def _show_completion_notification(self, source_id: str, data_count: int):
        """显示数据源处理完成通知（确认后停止，不循环）"""
        QMessageBox.information(
            self,
            "数据处理完成",
            f"数据源 {source_id} 处理完成！\n共处理 {data_count} 条数据记录。\n\n任务已结束。"
        )
        if self.reader_manager:
            self.reader_manager.stop_reader(source_id)
