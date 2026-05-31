#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成左侧面板管理器 - 优化版本
将新的多源异构数据流式处理UI架构集成到主程序中
采用与右侧面板一致的专业UI风格
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QLabel, QFrame, QPushButton, QGroupBox, QGridLayout,
    QProgressBar, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from .task_progress_manager import TaskProgressManager

class IntegratedLeftPanel(QWidget):
    """
    集成左侧面板管理器 - 优化版
    - 数据源管理
    - 多源同步配置
    - 实时监控
    采用与右侧面板一致的专业风格
    """
    
    # 信号定义
    data_source_connected = Signal(str)
    data_source_disconnected = Signal(str)
    sync_started = Signal(dict)
    sync_stopped = Signal()
    performance_updated = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.logger = logging.getLogger(__name__)
        
        self._progress_manager = TaskProgressManager()
        
        self.data_source_panel = None
        self.monitor_panel = None
        self.quality_panel = None
        self.performance_panel = None
        self.system_status_panel = None
        self.fusion_panel = None
        
        self._tab_initialized = {}
        
        self._init_ui()
        self._apply_professional_style()
        self._init_all_tabs()
        self._connect_tab_switching()
        
        self.logger.info("✅ 集成左侧面板已初始化（立即加载模式）")
    
    def _init_ui(self):
        """初始化UI布局 - 优化版本"""
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self.tab_widget, 1)

        self._create_task_progress(main_layout)

    def _init_all_tabs(self):
        """异步初始化所有标签页（不阻塞UI）"""
        from PySide6.QtWidgets import QApplication
        self.logger.warning("🔧 开始异步初始化所有左侧面板标签页...")
        
        # 使用 QTimer 分步加载，避免阻塞UI线程
        QTimer.singleShot(50, self._load_data_source_panel)
        QTimer.singleShot(150, self._load_fusion_panel)
        QTimer.singleShot(250, self._load_system_status_panel)
        
        self.logger.warning("✅ 左侧面板异步加载任务已启动")
    
    def _load_data_source_panel(self):
        """加载数据源面板"""
        try:
            from .data_source_config.data_source_list_panel import DataSourceListPanel
            self.data_source_panel = DataSourceListPanel()
            self.tab_widget.insertTab(0, self.data_source_panel, "📊 数据源")
            self.tab_widget.removeTab(1)
            
            self.data_source_panel.data_source_connected.connect(self._on_data_source_connected)
            self.data_source_panel.data_source_disconnected.connect(self._on_data_source_disconnected)
            
            if hasattr(self.data_source_panel, 'data_source_added'):
                self.data_source_panel.data_source_added.connect(self._on_data_source_changed)
            if hasattr(self.data_source_panel, 'data_source_deleted'):
                self.data_source_panel.data_source_deleted.connect(self._on_data_source_changed)
            
            if hasattr(self.data_source_panel, 'extraction_started'):
                self.data_source_panel.extraction_started.connect(self._on_extraction_started)
            if hasattr(self.data_source_panel, 'extraction_stopped'):
                self.data_source_panel.extraction_stopped.connect(self._on_extraction_stopped)
            
            self.logger.warning("✅ 数据源面板已加载")
        except Exception as e:
            self.logger.error(f"❌ 数据源面板加载失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _load_fusion_panel(self):
        """加载数据融合面板"""
        try:
            from .data_fusion_panel import DataFusionPanel
            self.fusion_panel = DataFusionPanel()
            self.tab_widget.insertTab(1, self.fusion_panel, "🔄 数据融合")
            self.tab_widget.removeTab(2)
            
            self.fusion_panel.pipeline_started.connect(self._on_sync_started)
            self.fusion_panel.pipeline_stopped.connect(self._on_sync_stopped)
            self.fusion_panel.fusion_log_added.connect(lambda msg: self.update_task_progress(detail=msg))
            self.fusion_panel.data_source_completed.connect(self._on_source_task_completed)
            
            self.logger.warning("✅ 数据融合面板已加载")
        except Exception as e:
            self.logger.error(f" 数据融合面板加载失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _load_system_status_panel(self):
        """加载系统状态面板"""
        try:
            from .system_status_tab import SystemStatusTab
            self.system_status_panel = SystemStatusTab()
            self.tab_widget.insertTab(2, self.system_status_panel, "📋 系统状态")
            self.tab_widget.removeTab(3)
            self.logger.warning("✅ 系统状态面板已加载")
        except Exception as e:
            self.logger.error(f"❌ 系统状态面板加载失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _create_data_source_tab(self):
        QApplication.processEvents()
        try:
            from .data_source_config.data_source_list_panel import DataSourceListPanel
            self.data_source_panel = DataSourceListPanel()
            QApplication.processEvents()
            self.tab_widget.insertTab(0, self.data_source_panel, "📊 数据源")
            self.tab_widget.removeTab(1)
            
            self.data_source_panel.data_source_connected.connect(self._on_data_source_connected)
            self.data_source_panel.data_source_disconnected.connect(self._on_data_source_disconnected)
            
            if hasattr(self.data_source_panel, 'data_source_added'):
                self.data_source_panel.data_source_added.connect(self._on_data_source_changed)
            if hasattr(self.data_source_panel, 'data_source_deleted'):
                self.data_source_panel.data_source_deleted.connect(self._on_data_source_changed)
            
            if hasattr(self.data_source_panel, 'extraction_started'):
                self.data_source_panel.extraction_started.connect(self._on_extraction_started)
            if hasattr(self.data_source_panel, 'extraction_stopped'):
                self.data_source_panel.extraction_stopped.connect(self._on_extraction_stopped)
            
            self.logger.info("✅ 数据源管理面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 数据源管理面板加载失败: {e}")
            self._create_placeholder_tab_at_index(0, "数据源", str(e))

    def _on_extraction_started(self):
        if self.fusion_panel and hasattr(self.fusion_panel, '_start_pipeline'):
            self.fusion_panel._start_pipeline()

    def _on_extraction_stopped(self):
        if self.fusion_panel and hasattr(self.fusion_panel, '_stop_pipeline'):
            self.fusion_panel._stop_pipeline()

    def _create_fusion_tab(self):
        QApplication.processEvents()
        try:
            from .data_fusion_panel import DataFusionPanel
            self.fusion_panel = DataFusionPanel()
            QApplication.processEvents()
            self.tab_widget.insertTab(1, self.fusion_panel, "🔄 数据融合")
            self.tab_widget.removeTab(2)
            
            self.fusion_panel.pipeline_started.connect(self._on_sync_started)
            self.fusion_panel.pipeline_stopped.connect(self._on_sync_stopped)
            self.fusion_panel.fusion_log_added.connect(lambda msg: self.update_task_progress(detail=msg))
            self.fusion_panel.data_source_completed.connect(self._on_source_task_completed)
            
            self.logger.info("✅ 数据融合面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 数据融合面板加载失败: {e}")
            self._create_placeholder_tab_at_index(1, "数据融合", str(e))

    def _create_system_status_tab(self):
        QApplication.processEvents()
        try:
            from .system_status_tab import SystemStatusTab
            self.system_status_panel = SystemStatusTab()
            QApplication.processEvents()
            self.tab_widget.insertTab(2, self.system_status_panel, "📋 系统状态")
            self.tab_widget.removeTab(3)
            self.logger.info("✅ 系统状态面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 系统状态面板加载失败: {e}")
            self._create_placeholder_tab_at_index(2, "系统状态", str(e))

    def _create_placeholder_tab_at_index(self, index, name, error_msg):
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        error_label = QLabel(f"❌ {name} 模块加载失败")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: red; font-size: 12px;")
        layout.addWidget(error_label)
        detail_label = QLabel(str(error_msg))
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(detail_label)
        self.tab_widget.insertTab(index, placeholder, name)
        self.tab_widget.removeTab(index + 1)
    
    def _apply_professional_style(self):
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
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover {
                background-color: #D0D0D0;
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
            QFrame {
                background-color: white;
            }
        """)
    
    def _init_components(self):
        """初始化各个组件面板"""
        try:
            # 1. 数据源管理面板
            from .data_source_config.data_source_list_panel import DataSourceListPanel
            self.data_source_panel = DataSourceListPanel()
            self.tab_widget.addTab(self.data_source_panel, "📊 数据源")
            
            # 连接数据源相关信号
            self.data_source_panel.data_source_connected.connect(self._on_data_source_connected)
            self.data_source_panel.data_source_disconnected.connect(self._on_data_source_disconnected)
            
            # 连接数据源添加/删除信号到融合面板刷新
            if hasattr(self.data_source_panel, 'data_source_added'):
                self.data_source_panel.data_source_added.connect(self._on_data_source_changed)
            if hasattr(self.data_source_panel, 'data_source_deleted'):
                self.data_source_panel.data_source_deleted.connect(self._on_data_source_changed)
            if hasattr(self.data_source_panel, 'data_source_toggled'):
                self.data_source_panel.data_source_toggled.connect(self._on_data_source_toggled)
            
            self.logger.info("✅ 数据源管理面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 数据源管理面板加载失败: {e}")
            self._create_placeholder_tab("数据源", str(e))
        
        try:
            # 2. 数据融合面板（包含配置和监控）
            from .data_fusion_panel import DataFusionPanel
            self.fusion_panel = DataFusionPanel()
            self.tab_widget.addTab(self.fusion_panel, "🔄 数据融合")
            
            # 连接融合相关信号
            self.fusion_panel.pipeline_started.connect(self._on_sync_started)
            self.fusion_panel.pipeline_stopped.connect(self._on_sync_stopped)
            self.fusion_panel.fusion_log_added.connect(lambda msg: self.update_task_progress(detail=msg))
            self.fusion_panel.data_source_completed.connect(self._on_source_task_completed)

            if hasattr(self.data_source_panel, 'extraction_started'):
                self.data_source_panel.extraction_started.connect(self.fusion_panel._start_pipeline)
            if hasattr(self.data_source_panel, 'extraction_stopped'):
                self.data_source_panel.extraction_stopped.connect(self.fusion_panel._stop_pipeline)
            
            self.logger.info("✅ 数据融合面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 数据融合面板加载失败: {e}")
            self._create_placeholder_tab("数据融合", str(e))

        try:
            from .system_status_tab import SystemStatusTab
            self.system_status_panel = SystemStatusTab()
            self.tab_widget.addTab(self.system_status_panel, "📋 系统状态")
            self.logger.info("✅ 系统状态面板加载成功")
        except Exception as e:
            self.logger.error(f"❌ 系统状态面板加载失败: {e}")
            self._create_placeholder_tab("系统状态", str(e))
    
    def _create_placeholder_tab(self, name, error_msg):
        """创建占位标签页用于显示加载失败"""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        
        error_group = QGroupBox("加载失败")
        error_layout = QVBoxLayout(error_group)
        
        error_label = QLabel(f"无法加载 {name} 面板：\n\n{error_msg}")
        error_label.setWordWrap(True)
        error_label.setStyleSheet("color: #CC0000;")
        
        retry_btn = QPushButton("重试")
        retry_btn.clicked.connect(lambda: self._retry_init_component(name))
        
        error_layout.addWidget(error_label)
        error_layout.addWidget(retry_btn)
        layout.addWidget(error_group)
        layout.addStretch()
        
        self.tab_widget.addTab(placeholder, f"⚠️ {name}")
    
    def _retry_init_component(self, name):
        """重试初始化组件"""
        self.logger.info(f"重试加载 {name} 面板...")
        self._init_components()

    def _create_task_progress(self, parent_layout):
        """创建任务进度条 - 悬浮于左侧面板底部"""
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

        self._progress_manager.set_ui_updater(self._apply_progress_to_ui)

    def _apply_progress_to_ui(self, task_name: str, progress: int, detail: str):
        """将进度状态应用到UI控件"""
        self.task_name_label.setText(f"当前任务: {task_name}")
        self.task_progress_bar.setValue(progress)
        self.task_detail_label.setText(detail)

    def _connect_tab_switching(self):
        """连接标签页切换信号"""
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        """标签页切换时更新任务进度"""
        tab_text = self.tab_widget.tabText(index)
        module_map = {
            "📊 数据源": "data_source",
            "🔄 数据融合": "data_fusion",
            "📋 系统状态": "system_status"
        }
        module_name = module_map.get(tab_text, "")
        if module_name:
            self._progress_manager.set_active_module(module_name)

    def update_task_progress(self, task_name=None, progress=None, detail=None):
        """更新任务进度（兼容旧接口，委托给全局管理器）"""
        self._progress_manager.set_active_module("data_fusion")
        self._progress_manager.update_progress("data_fusion", task_name=task_name, progress=progress, detail=detail)

    def on_right_tab_changed(self, tab_name: str):
        """右侧面板标签页切换时更新任务进度"""
        tab_module_map = {
            "CNAP可视化": "data_fusion",
            "IMU可视化": "data_fusion",
            "实时行为监控": "data_fusion",
        }
        module_name = tab_module_map.get(tab_name, "data_fusion")
        self._progress_manager.set_active_module(module_name)
        self._progress_manager.update_progress(
            module_name,
            task_name=f"{tab_name}监控中",
            progress=0,
            detail="等待数据..."
        )
        self.logger.info(f"任务进度已切换至右侧标签页: {tab_name} → {module_name}")

    def reset_task_progress(self):
        """重置任务进度（兼容旧接口，委托给全局管理器）"""
        active = self._progress_manager.get_active_module() or "data_fusion"
        self._progress_manager.reset_module(active)

    # ==================== 信号处理 ====================
    
    def _on_data_source_connected(self, source_id):
        """数据源连接成功"""
        self.logger.info(f"✅ 数据源 {source_id} 已连接")
        self.data_source_connected.emit(source_id)
    
    def _on_data_source_disconnected(self, source_id):
        """数据源断开连接"""
        self.logger.info(f"❌ 数据源 {source_id} 已断开")
        self.data_source_disconnected.emit(source_id)
    
    def _on_data_source_changed(self, source_id=None):
        """数据源变化处理"""
        self.logger.info(f"数据源已变化，刷新融合面板")
        if hasattr(self, 'fusion_panel') and hasattr(self.fusion_panel, 'refresh_source_table'):
            self.fusion_panel.refresh_source_table()

        if source_id and hasattr(self, 'fusion_panel') and hasattr(self.fusion_panel, 'reader_manager'):
            rm = self.fusion_panel.reader_manager
            if rm and getattr(rm, 'is_active', False):
                try:
                    rm.start_reader(source_id)
                    self.logger.info(f"流水线运行中，已自动启动新数据源读取器: {source_id}")
                except Exception as e:
                    self.logger.error(f"自动启动新数据源读取器失败 ({source_id}): {e}")
    
    def _on_data_source_toggled(self, source_id, checked):
        """数据源复选框切换 - 刷新融合面板并更新向导"""
        self.logger.info(f"数据源 [{source_id}] 切换为 {'启用' if checked else '禁用'}，刷新融合面板")
        if hasattr(self, 'fusion_panel') and hasattr(self.fusion_panel, 'refresh_source_table'):
            self.fusion_panel.refresh_source_table()
    
    def _on_sync_started(self, config):
        """同步启动"""
        self.logger.info("✅ 数据同步与融合已启动")
        self.sync_started.emit(config)
        self._progress_manager.update_progress("data_fusion", task_name="数据融合采集中", progress=0, detail="正在初始化数据管道...")

        if hasattr(self, 'fusion_panel') and hasattr(self.fusion_panel, 'start_monitoring'):
            self.fusion_panel.start_monitoring()
    
    def _on_sync_stopped(self):
        """同步停止"""
        self.logger.info("❌ 数据同步与融合已停止")
        self.sync_stopped.emit()
        self._progress_manager.reset_module("data_fusion")

        if hasattr(self, 'fusion_panel') and hasattr(self.fusion_panel, 'stop_monitoring'):
            self.fusion_panel.stop_monitoring()

    def _on_source_task_completed(self, source_name, data_count):
        """数据源任务完成"""
        self._progress_manager.update_progress(
            "data_fusion",
            task_name=f"数据源完成: {source_name}",
            progress=100,
            detail=f"已处理 {data_count} 条数据"
        )
    
    # ==================== 公共方法 ====================

    def get_progress_manager(self):
        """获取全局任务进度管理器"""
        return self._progress_manager

    def set_data_bridge(self, data_bridge):
        """设置数据桥接器"""
        self._data_bridge = data_bridge
        if hasattr(self, 'data_source_panel') and self.data_source_panel:
            if hasattr(self.data_source_panel, 'set_data_bridge'):
                self.data_source_panel.set_data_bridge(data_bridge)
        if hasattr(self, 'fusion_panel') and self.fusion_panel:
            if hasattr(self.fusion_panel, 'set_data_bridge'):
                self.fusion_panel.set_data_bridge(data_bridge)
        self.logger.info("DataBridge 已注入到集成左侧面板")

    def refresh_data_sources(self):
        """刷新数据源列表"""
        if self.data_source_panel and hasattr(self.data_source_panel, 'refresh_data_source_list'):
            self.data_source_panel.refresh_data_source_list()
    
    def get_active_sources(self):
        """获取活动的数据源列表"""
        if self.data_source_panel and hasattr(self.data_source_panel, 'get_active_sources'):
            return self.data_source_panel.get_active_sources()
        return []
    
    def get_current_config(self):
        config = {}
        if self.fusion_panel and hasattr(self.fusion_panel, 'config_manager'):
            config['fusion'] = self.fusion_panel.config_manager.fusion_config
            config['sync'] = self.fusion_panel.config_manager.sync_config
        return config if config else None
