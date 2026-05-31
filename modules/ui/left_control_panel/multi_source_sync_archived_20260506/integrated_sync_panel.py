#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合的多源同步面板 - 优化版本
为左侧面板提供紧凑的同步配置界面
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QPushButton, QFrame, QMessageBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# 导入新模块
from ..utils import (
    get_config_manager,
    get_pipeline_manager,
    PipelineStatus
)

logger = logging.getLogger(__name__)


class IntegratedSyncPanel(QWidget):
    """整合的多源同步面板 - 紧凑版本"""
    
    # 信号
    pipeline_started = Signal(dict)
    pipeline_stopped = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.pipeline_manager = get_pipeline_manager(self.config_manager)
        
        self.setup_ui()
        self.apply_professional_style()
        self.connect_signals()
        try:
            self.load_config()
        except Exception as e:
            logger.warning(f"加载同步配置失败: {e}")
        
        logger.info("✅ 整合多源同步面板已初始化")
    
    def setup_ui(self):
        """设置UI - 紧凑布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)
        
        # 控制面板
        control_group = QGroupBox("同步控制")
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
        
        main_layout.addWidget(control_group)
        
        # 配置面板
        config_group = QGroupBox("同步策略配置")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(8, 6, 8, 6)
        config_layout.setSpacing(6)
        
        # 同步模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("同步模式:"))
        self.sync_mode = QComboBox()
        self.sync_mode.addItems(["实时同步", "定时同步", "手动同步"])
        mode_layout.addWidget(self.sync_mode)
        config_layout.addLayout(mode_layout)
        
        # 同步间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("同步间隔:"))
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(1, 3600)
        self.sync_interval.setValue(5)
        self.sync_interval.setSuffix(" 秒")
        interval_layout.addWidget(self.sync_interval)
        config_layout.addLayout(interval_layout)
        
        # 缓冲大小
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("缓冲大小:"))
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(10, 10000)
        self.buffer_size.setValue(1000)
        buffer_layout.addWidget(self.buffer_size)
        config_layout.addLayout(buffer_layout)
        
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
        config_layout.addLayout(fault_layout)
        
        main_layout.addWidget(config_group)
        
        # 融合算法
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
        
        main_layout.addWidget(fusion_group)
        
        main_layout.addStretch()
    
    def apply_professional_style(self):
        """应用专业样式 - 与右侧面板一致"""
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
        """)
    
    def connect_signals(self):
        """连接信号"""
        self.btn_start.clicked.connect(self._start_pipeline)
        self.btn_stop.clicked.connect(self._stop_pipeline)
        
        # 连接流水线状态变化
        self.pipeline_manager.on_status_changed = self._on_pipeline_status_changed
    
    def load_config(self):
        """加载配置"""
        # 兼容两种配置管理器
        if hasattr(self.config_manager, 'multi_source_sync_config'):
            sync_config = self.config_manager.multi_source_sync_config
        elif hasattr(self.config_manager, 'sync_config'):
            sync_config = self.config_manager.sync_config
        else:
            sync_config = None
        
        if sync_config:
            if hasattr(sync_config, 'sync_mode'):
                mode_map = {
                    "real_time": 0, "scheduled": 1, "manual": 2
                }
                self.sync_mode.setCurrentIndex(mode_map.get(sync_config.sync_mode, 0))
            if hasattr(sync_config, 'sync_interval'):
                self.sync_interval.setValue(sync_config.sync_interval)
            if hasattr(sync_config, 'buffer_size'):
                self.buffer_size.setValue(sync_config.buffer_size)
            if hasattr(sync_config, 'enable_retry'):
                self.enable_retry.setChecked(sync_config.enable_retry)
            if hasattr(sync_config, 'retry_count'):
                self.retry_count.setValue(sync_config.retry_count)
            
            if hasattr(sync_config, 'fusion_algorithm'):
                algo_map = {
                    "weighted_average": 0, "kalman_filter": 1, 
                    "bayesian": 2, "dempster_shafer": 3, "simple": 4
                }
                self.fusion_algorithm.setCurrentIndex(algo_map.get(sync_config.fusion_algorithm, 0))
            if hasattr(sync_config, 'time_window'):
                self.time_window.setValue(sync_config.time_window)
            if hasattr(sync_config, 'alignment_strategy'):
                align_map = {
                    "timestamp": 0, "interpolation": 1, "resampling": 2
                }
                self.alignment_strategy.setCurrentIndex(align_map.get(sync_config.alignment_strategy, 0))
            if hasattr(sync_config, 'quality_threshold'):
                self.quality_threshold.setValue(sync_config.quality_threshold)
    
    def _start_pipeline(self):
        """启动流水线"""
        try:
            # 保存当前配置
            config = self.get_current_config()
            self.config_manager.multi_source_sync_config = config
            self.config_manager.save_config()
            
            # 启动流水线
            self.pipeline_manager.start_pipeline()
            
            # 更新UI状态
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("color: #27AE60; font-weight: bold;")
            
            self.pipeline_started.emit(config)
            logger.info("✅ 数据同步与融合已启动")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动流水线失败: {str(e)}")
            logger.error(f"❌ 启动流水线失败: {e}")
    
    def _stop_pipeline(self):
        """停止流水线"""
        try:
            self.pipeline_manager.stop_pipeline()
            
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setText("状态: 空闲")
            self.status_label.setStyleSheet("")
            
            self.pipeline_stopped.emit()
            logger.info("❌ 数据同步与融合已停止")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止流水线失败: {str(e)}")
            logger.error(f"❌ 停止流水线失败: {e}")
    
    def _on_pipeline_status_changed(self, status: PipelineStatus):
        """流水线状态变化"""
        status_text = {
            PipelineStatus.IDLE: "空闲",
            PipelineStatus.RUNNING: "运行中",
            PipelineStatus.PAUSED: "暂停",
            PipelineStatus.ERROR: "错误",
            PipelineStatus.STOPPING: "停止中"
        }.get(status, "未知")
        
        self.status_label.setText(f"状态: {status_text}")
        
        if status == PipelineStatus.RUNNING:
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.status_label.setStyleSheet("color: #27AE60; font-weight: bold;")
        elif status == PipelineStatus.ERROR:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
        else:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setStyleSheet("")
    
    def get_current_config(self):
        """获取当前配置"""
        config = self.config_manager.multi_source_sync_config
        
        if not config:
            # 创建默认配置
            from ..utils import MultiSourceSyncConfig
            config = MultiSourceSyncConfig()
        
        # 更新配置
        mode_list = ["real_time", "scheduled", "manual"]
        config.sync_mode = mode_list[self.sync_mode.currentIndex()]
        config.sync_interval = self.sync_interval.value()
        config.buffer_size = self.buffer_size.value()
        config.enable_retry = self.enable_retry.isChecked()
        config.retry_count = self.retry_count.value()
        
        algo_list = ["weighted_average", "kalman_filter", "bayesian", "dempster_shafer", "simple"]
        config.fusion_algorithm = algo_list[self.fusion_algorithm.currentIndex()]
        config.time_window = self.time_window.value()
        align_list = ["timestamp", "interpolation", "resampling"]
        config.alignment_strategy = align_list[self.alignment_strategy.currentIndex()]
        config.quality_threshold = self.quality_threshold.value()
        
        return config
