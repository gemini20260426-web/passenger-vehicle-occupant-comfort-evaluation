"""
数据源列表面板 - 优化版本
提供数据源的添加、编辑、删除、启用/禁用功能
采用与右侧面板一致的专业风格
"""

import logging
import json
import os
import time
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QFrame, QMessageBox,
    QMenu, QFileDialog, QGroupBox, QToolButton, QCheckBox, QProgressBar,
    QScrollArea
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QIcon, QAction

# 导入工具模块
from ..utils import (
    style_manager,
    get_config_manager,
    get_pipeline_manager,
    DataSourceConfig,
    PipelineStatus
)

import csv
import io

logger = logging.getLogger(__name__)

class StatusIndicator(QLabel):
    """状态指示器 - 优化版本"""
    
    def __init__(self, status: str = "disconnected", parent=None):
        super().__init__(parent)
        self.set_status(status)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(14, 14)
    
    def set_status(self, status: str):
        """设置状态"""
        color_map = {
            "connected": "#27AE60",
            "disconnected": "#7F8C8D",
            "connecting": "#F39C12",
            "error": "#E74C3C",
            "enabled": "#27AE60",
            "disabled": "#7F8C8D"
        }
        color = color_map.get(status, "#7F8C8D")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 7px;
                border: 1px solid #CCCCCC;
            }}
        """)

class DataSourceListPanel(QWidget):
    """数据源列表面板 - 优化版本"""
    
    # 信号定义
    data_source_connected = Signal(str)  # 数据源ID
    data_source_disconnected = Signal(str)  # 数据源ID
    data_source_selected = Signal(str)  # 数据源ID
    data_source_added = Signal(str)  # 数据源ID
    data_source_edited = Signal(str)  # 数据源ID
    data_source_deleted = Signal(str)  # 数据源ID
    data_source_toggled = Signal(str, bool)  # 数据源ID, 是否启用
    extraction_started = Signal()  # 抽取开始
    extraction_stopped = Signal()  # 抽取停止
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.pipeline_manager = get_pipeline_manager(self.config_manager)
        
        self.setup_ui()
        self.apply_professional_style()
        try:
            self.refresh_data_source_list()
        except Exception as e:
            logger.warning(f"刷新数据源列表失败: {e}")
        self.connect_signals()
        
        logger.info("✅ 数据源列表面板已初始化")
    
    def setup_ui(self):
        """设置UI - 紧凑布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        
        # 工具栏区域 - 紧凑风格
        tool_group = QGroupBox("数据源操作")
        tool_layout = QHBoxLayout(tool_group)
        tool_layout.setContentsMargins(8, 6, 8, 6)
        tool_layout.setSpacing(6)
        
        # 操作按钮
        self.btn_add = QPushButton("添加")
        self.btn_add.setMinimumWidth(70)
        tool_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setMinimumWidth(70)
        self.btn_edit.setEnabled(False)
        tool_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setMinimumWidth(70)
        self.btn_delete.setEnabled(False)
        tool_layout.addWidget(self.btn_delete)
        
        tool_layout.addSpacing(10)
        
        self._monitor_visible = False
        self.btn_monitor = QPushButton("监控")
        self.btn_monitor.setMinimumWidth(70)
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.setToolTip("展开/收起数据源实时监控面板")
        tool_layout.addWidget(self.btn_monitor)

        self.btn_export = QPushButton("导出")
        self.btn_export.setMinimumWidth(70)
        self.btn_export.setToolTip("导出解析后的数据源")
        tool_layout.addWidget(self.btn_export)

        self.btn_import = QPushButton("导入")
        self.btn_import.setMinimumWidth(70)
        self.btn_import.setToolTip("全量导入已解析的数据源文件")
        tool_layout.addWidget(self.btn_import)

        tool_layout.addStretch()
        
        self._is_extracting = False
        self.btn_extract = QPushButton("开始")
        self.btn_extract.setMinimumWidth(80)
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-weight: bold; font-size: 9pt; }"
            "QPushButton:hover { background-color: #219A52; }"
        )
        tool_layout.addWidget(self.btn_extract)
        
        layout.addWidget(tool_group)
        
        # 数据源表格区域
        table_group = QGroupBox("数据源列表")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(6, 4, 6, 4)
        
        self.data_source_table = self._create_data_source_table()
        table_layout.addWidget(self.data_source_table)
        
        layout.addWidget(table_group, 1)
        
        self._create_monitor_panel(layout)
        
        # 底部统计信息
        status_group = QGroupBox("统计信息")
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(8, 4, 8, 4)
        
        self.label_total = QLabel("总计: 0")
        status_layout.addWidget(self.label_total)
        
        status_layout.addSpacing(15)
        
        self.label_enabled = QLabel("已启用: 0")
        self.label_enabled.setStyleSheet("color: #27AE60; font-weight: bold;")
        status_layout.addWidget(self.label_enabled)
        
        status_layout.addSpacing(15)
        
        self.label_disabled = QLabel("已禁用: 0")
        self.label_disabled.setStyleSheet("color: #7F8C8D; font-weight: bold;")
        status_layout.addWidget(self.label_disabled)
        
        status_layout.addStretch()
        
        self.label_pipeline_status = QLabel("流水线: 空闲")
        status_layout.addWidget(self.label_pipeline_status)
        
        layout.addWidget(status_group)
    
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
                padding: 4px 8px 4px 5px;
                font-size: 9pt;
                min-height: 28px;
                font-family: "Microsoft YaHei";
                text-align: left;
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
    
    def _create_data_source_table(self) -> QTableWidget:
        """创建数据源表格 - 优化版本"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["选择", "状态", "名称", "类型", "连接信息", "质量"])
        
        # 设置表头
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setMinimumHeight(150)
        
        # 右键菜单
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        
        return table
    
    def _create_monitor_panel(self, parent_layout):
        """创建数据源实时监控面板"""
        self.monitor_panel = QGroupBox("数据源实时监控")
        self.monitor_panel.setVisible(False)
        monitor_outer = QVBoxLayout(self.monitor_panel)
        monitor_outer.setContentsMargins(6, 4, 6, 6)
        monitor_outer.setSpacing(6)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(280)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.monitor_container = QWidget()
        self.monitor_container.setStyleSheet("background: transparent;")
        self.monitor_layout = QVBoxLayout(self.monitor_container)
        self.monitor_layout.setContentsMargins(0, 0, 0, 0)
        self.monitor_layout.setSpacing(6)
        
        self._overall_card = self._create_monitor_card("总体状态", [
            ("status", "状态", "等待启动"),
            ("total_read", "已读取", "0 条"),
            ("total_rate", "总速率", "0 条/秒"),
            ("total_errors", "错误", "0"),
        ])
        self.monitor_layout.addWidget(self._overall_card)
        
        self._source_cards_container = QWidget()
        self._source_cards_layout = QVBoxLayout(self._source_cards_container)
        self._source_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._source_cards_layout.setSpacing(4)
        self.monitor_layout.addWidget(self._source_cards_container)
        
        self._stats_card = self._create_monitor_card("解析统计", [
            ("valid_data", "有效数据", "0"),
            ("discarded", "丢弃", "0"),
            ("cache_size", "缓存", "0 条"),
        ])
        self.monitor_layout.addWidget(self._stats_card)
        
        self.monitor_layout.addStretch()
        
        scroll.setWidget(self.monitor_container)
        monitor_outer.addWidget(scroll)
        
        parent_layout.addWidget(self.monitor_panel)
        
        self._source_cards = {}
    
    def _create_monitor_card(self, title, fields):
        """创建单个监控卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                background: #FAFAFA;
                padding: 4px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: #333; border: none; background: transparent;")
        card_layout.addWidget(title_label)
        
        field_widgets = {}
        for key, label, default in fields:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("font-size: 8pt; color: #666; border: none; background: transparent;")
            lbl.setFixedWidth(55)
            row.addWidget(lbl)
            val = QLabel(default)
            val.setStyleSheet("font-size: 8pt; color: #333; font-weight: bold; border: none; background: transparent;")
            val.setObjectName(f"monitor_{key}")
            row.addWidget(val)
            row.addStretch()
            card_layout.addLayout(row)
            field_widgets[key] = val
        
        card.field_widgets = field_widgets
        return card
    
    def _create_source_monitor_card(self, source_id, source_name, source_type):
        """创建单个数据源的监控卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #BBDEFB;
                border-radius: 4px;
                background: #F5F9FF;
                padding: 4px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(2)
        
        header = QHBoxLayout()
        header.setSpacing(6)
        
        status_dot = QLabel("⚪")
        status_dot.setFixedSize(16, 16)
        status_dot.setAlignment(Qt.AlignCenter)
        status_dot.setStyleSheet("font-size: 10pt; border: none; background: transparent;")
        header.addWidget(status_dot)
        
        name_label = QLabel(f"{source_id[:8]} · {source_type}")
        name_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: #1565C0; border: none; background: transparent;")
        header.addWidget(name_label)
        header.addStretch()
        
        count_label = QLabel("0 条")
        count_label.setStyleSheet("font-size: 8pt; color: #666; border: none; background: transparent;")
        header.addWidget(count_label)
        
        card_layout.addLayout(header)
        
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.setFormat("%v%")
        progress.setMaximumHeight(12)
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #BBDEFB;
                border-radius: 3px;
                background: #E3F2FD;
                text-align: center;
                font-size: 7pt;
            }
            QProgressBar::chunk {
                background: #42A5F5;
                border-radius: 2px;
            }
        """)
        card_layout.addWidget(progress)
        
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        rate_label = QLabel("速率: --")
        rate_label.setStyleSheet("font-size: 7pt; color: #888; border: none; background: transparent;")
        info_row.addWidget(rate_label)
        err_label = QLabel("错误: 0")
        err_label.setStyleSheet("font-size: 7pt; color: #888; border: none; background: transparent;")
        info_row.addWidget(err_label)
        info_row.addStretch()
        card_layout.addLayout(info_row)
        
        card.status_dot = status_dot
        card.count_label = count_label
        card.progress_bar = progress
        card.rate_label = rate_label
        card.err_label = err_label
        card.source_id = source_id
        
        return card
    
    def _toggle_monitor_panel(self):
        """切换监控面板显示"""
        self._monitor_visible = not self._monitor_visible
        self.monitor_panel.setVisible(self._monitor_visible)
        self.btn_monitor.setChecked(self._monitor_visible)
        
        if self._monitor_visible:
            self.btn_monitor.setStyleSheet(
                "QPushButton { background-color: #1565C0; color: white; font-weight: bold; }"
                "QPushButton:hover { background-color: #1976D2; }"
            )
            self._rebuild_source_cards()
            self._monitor_timer.start()
            self._refresh_monitor_panel()
            logger.info("📊 数据源监控面板已展开")
        else:
            self.btn_monitor.setStyleSheet("")
            self._monitor_timer.stop()
            logger.info("📊 数据源监控面板已收起")
    
    def _rebuild_source_cards(self):
        """重建数据源卡片"""
        for card in self._source_cards.values():
            self._source_cards_layout.removeWidget(card)
            card.deleteLater()
        self._source_cards.clear()
        
        sources = self.config_manager.data_sources
        for source_id, config in sources.items():
            source_type = getattr(config, 'source_type', getattr(config, 'type', 'unknown'))
            card = self._create_source_monitor_card(source_id, config.name, source_type)
            self._source_cards_layout.addWidget(card)
            self._source_cards[source_id] = card
    
    def _refresh_monitor_panel(self):
        """刷新监控面板数据"""
        if not self._monitor_visible:
            return
        
        reader_statuses = {}
        reader_manager = None
        try:
            from ..utils.data_reader_manager import get_data_reader_manager
            reader_manager = get_data_reader_manager(self.config_manager, self.pipeline_manager)
            if reader_manager:
                reader_statuses = reader_manager.get_all_statuses()

                if not reader_statuses and hasattr(reader_manager, 'readers'):
                    for sid, reader in reader_manager.readers.items():
                        reader_statuses[sid] = reader.get_status()
        except Exception as e:
            logger.warning(f"获取 reader 状态失败: {e}")
        
        total_read = 0
        total_errors = 0
        active_count = 0
        
        for source_id, card in self._source_cards.items():
            status = reader_statuses.get(source_id, {})
            data_count = status.get('data_count', 0)
            is_running = status.get('is_running', False)
            error_count = status.get('error_count', 0)
            reader_status = status.get('status', 'stopped')
            
            total_read += data_count
            total_errors += error_count
            if is_running:
                active_count += 1
            
            total_records = status.get('total_records', 0)
            
            if reader_status == 'running':
                card.status_dot.setText("🟢")
                card.count_label.setText(f"{data_count} 条")
                card.count_label.setStyleSheet("font-size: 8pt; color: #27AE60; border: none; background: transparent;")
            elif reader_status == 'error':
                card.status_dot.setText("🔴")
                card.count_label.setStyleSheet("font-size: 8pt; color: #E74C3C; border: none; background: transparent;")
            elif data_count > 0 and reader_status == 'stopped':
                card.status_dot.setText("✅")
                card.count_label.setText(f"{data_count} 条")
                card.count_label.setStyleSheet("font-size: 8pt; color: #1565C0; border: none; background: transparent;")
            else:
                card.status_dot.setText("⏸")
                card.count_label.setStyleSheet("font-size: 8pt; color: #999; border: none; background: transparent;")
            
            if total_records > 0:
                pct = int(data_count / total_records * 100)
                card.progress_bar.setValue(min(pct, 100))
                card.progress_bar.setFormat(f"{data_count}/{total_records} ({pct}%)")
            else:
                card.progress_bar.setValue(0)
                card.progress_bar.setFormat("等待加载...")
            
            if is_running and total_records > 0:
                card.rate_label.setText(f"速率: {data_count}/{total_records}")
            elif is_running:
                card.rate_label.setText("速率: 运行中")
            else:
                card.rate_label.setText("速率: 已停止")
            card.err_label.setText(f"错误: {error_count}")
        
        overall = self._overall_card.field_widgets
        if active_count > 0:
            overall['status'].setText("🟢 采集中")
            overall['status'].setStyleSheet("font-size: 8pt; color: #27AE60; font-weight: bold; border: none; background: transparent;")
        elif total_read > 0:
            overall['status'].setText("✅ 已完成")
            overall['status'].setStyleSheet("font-size: 8pt; color: #1565C0; font-weight: bold; border: none; background: transparent;")
        else:
            overall['status'].setText("⏳ 等待启动")
            overall['status'].setStyleSheet("font-size: 8pt; color: #F39C12; font-weight: bold; border: none; background: transparent;")
        
        overall['total_read'].setText(f"{total_read} 条")
        overall['total_errors'].setText(str(total_errors))
        
        stats = self._stats_card.field_widgets
        stats['valid_data'].setText(f"{total_read}")
        stats['discarded'].setText(str(total_errors))
        
        try:
            if reader_manager and hasattr(reader_manager, 'cache') and reader_manager.cache:
                cache_stats = reader_manager.cache.get_stats()
                stats['cache_size'].setText(f"{cache_stats.get('total_records', 0)} 条")
        except Exception as e:
            logger.debug(f"获取缓存统计失败: {e}")
    
    def connect_signals(self):
        """连接信号"""
        self._data_bridge = None
        
        self.btn_add.clicked.connect(self._add_data_source)
        self.btn_edit.clicked.connect(self._edit_data_source)
        self.btn_delete.clicked.connect(self._delete_data_source)
        self.btn_monitor.clicked.connect(self._toggle_monitor_panel)
        self.btn_extract.clicked.connect(self._toggle_extraction)
        self.btn_export.clicked.connect(self._export_parsed_data)
        self.btn_import.clicked.connect(self._import_parsed_data)
        
        self.data_source_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.data_source_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        
        self.pipeline_manager.on_status_changed = self._on_pipeline_status_changed
        
        self._monitor_timer = QTimer()
        self._monitor_timer.timeout.connect(self._refresh_monitor_panel)
        self._monitor_timer.setInterval(500)

    def set_data_bridge(self, data_bridge):
        """设置数据桥接器"""
        self._data_bridge = data_bridge

    def refresh_data_source_list(self):
        """刷新数据源列表"""
        self.data_source_table.setRowCount(0)
        
        # 兼容两种配置管理器
        if hasattr(self.config_manager, 'data_source_configs'):
            configs = self.config_manager.data_source_configs
        elif hasattr(self.config_manager, 'data_sources'):
            configs = self.config_manager.data_sources
        else:
            configs = {}
        enabled_count = 0
        disabled_count = 0
        
        for source_id, config in configs.items():
            row = self.data_source_table.rowCount()
            self.data_source_table.insertRow(row)
            
            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(getattr(config, 'enabled', True))
            checkbox.setProperty("source_id", source_id)
            checkbox.toggled.connect(lambda checked, sid=source_id: self._on_source_checkbox_toggled(sid, checked))
            self.data_source_table.setCellWidget(row, 0, checkbox)
            
            # 状态指示器
            status_indicator = StatusIndicator("enabled" if config.enabled else "disabled")
            self.data_source_table.setCellWidget(row, 1, status_indicator)
            
            # 名称
            name_item = QTableWidgetItem(config.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.data_source_table.setItem(row, 2, name_item)
            
            # 类型 (兼容 type 和 source_type)
            source_type = getattr(config, 'source_type', getattr(config, 'type', 'unknown'))
            type_item = QTableWidgetItem(source_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.data_source_table.setItem(row, 3, type_item)
            
            # 连接信息
            conn_info = self._get_connection_info(config)
            conn_item = QTableWidgetItem(conn_info)
            conn_item.setFlags(conn_item.flags() & ~Qt.ItemIsEditable)
            self.data_source_table.setItem(row, 4, conn_item)
            
            # 数据质量
            quality_item = QTableWidgetItem("良好")
            quality_item.setFlags(quality_item.flags() & ~Qt.ItemIsEditable)
            self.data_source_table.setItem(row, 5, quality_item)
            
            # 存储数据源ID (兼容 id 和 source_id)
            actual_source_id = getattr(config, 'source_id', getattr(config, 'id', source_id))
            self.data_source_table.item(row, 2).setData(Qt.UserRole, actual_source_id)
            
            if config.enabled:
                enabled_count += 1
            else:
                disabled_count += 1
        
        # 更新统计信息
        self.label_total.setText(f"总计: {len(configs)}")
        self.label_enabled.setText(f"已启用: {enabled_count}")
        self.label_disabled.setText(f"已禁用: {disabled_count}")
    
    def _get_connection_info(self, config) -> str:
        """获取连接信息摘要"""
        # 获取数据源类型
        source_type = getattr(config, 'source_type', getattr(config, 'type', 'unknown'))
        
        # 获取连接参数 (兼容不同的配置格式)
        connection = getattr(config, 'connection', {})
        connection_params = getattr(config, 'connection_params', connection)
        
        if source_type == "file":
            path = connection_params.get("file_path", "")
            return path.split("/")[-1] if path else ""
        elif source_type == "mysql":
            return f"{connection_params.get('host', '')}"
        elif source_type == "mqtt":
            return connection_params.get("broker", "")
        elif source_type in ["imu", "gps"]:
            return connection_params.get("port", "")
        elif source_type == "canbus":
            return connection_params.get("interface", "")
        else:
            return "N/A"
    
    def _on_selection_changed(self):
        """选择变化处理"""
        has_selection = self.data_source_table.selectedItems()
        enabled = len(has_selection) > 0
        
        self.btn_edit.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        
        if enabled:
            selected_row = self.data_source_table.currentRow()
            item = self.data_source_table.item(selected_row, 2)
            if item:
                source_id = item.data(Qt.UserRole)
                self.data_source_selected.emit(source_id)
    
    def _on_source_checkbox_toggled(self, source_id, checked):
        """数据源复选框切换 - 同步 enabled 状态并通知融合面板刷新"""
        try:
            config = self.config_manager.data_sources.get(source_id)
            if config:
                config.enabled = checked
                self.config_manager.save_config()
                self.data_source_toggled.emit(source_id, checked)
                logger.info(f"数据源 [{source_id}] enabled={checked}, 已同步到融合面板")
        except Exception as e:
            logger.error(f"同步数据源复选框状态失败: {e}")
    
    def _on_cell_double_clicked(self, row: int, column: int):
        """单元格双击处理"""
        self._edit_data_source()
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        if not self.data_source_table.selectedItems():
            return
        
        menu = QMenu(self)
        
        edit_action = QAction("编辑...", self)
        edit_action.triggered.connect(self._edit_data_source)
        menu.addAction(edit_action)
        
        toggle_action = QAction("启用/禁用", self)
        toggle_action.triggered.connect(self._toggle_data_source)
        menu.addAction(toggle_action)
        
        menu.addSeparator()
        
        delete_action = QAction("删除...", self)
        delete_action.triggered.connect(self._delete_data_source)
        menu.addAction(delete_action)
        
        menu.exec(self.data_source_table.mapToGlobal(pos))
    
    def _add_data_source(self):
        """添加数据源"""
        try:
            from .data_source_config_dialog import DataSourceConfigDialog
            dialog = DataSourceConfigDialog(self)
            if self._data_bridge:
                dialog.set_data_bridge(self._data_bridge)
            if dialog.exec():
                # 获取配置数据
                config_data = dialog.get_config_data()
                if config_data:
                    from ..utils.config_manager import DataSourceConfig
                    import uuid
                    
                    # 创建 DataSourceConfig 对象
                    basic = config_data.get("basic", {})
                    conn = config_data.get("connection", {})
                    
                    source_id = str(uuid.uuid4())[:8]
                    new_config = DataSourceConfig(
                        id=source_id,
                        name=basic.get("name", "未命名"),
                        type=basic.get("type", "file"),
                        enabled=True,
                        connection=conn,
                        parsing=config_data.get("parser", {}),
                        quality_thresholds=config_data.get("quality", {}),
                        signal_filter=config_data.get("signal_filter", {}),
                        axis_correction=config_data.get("axis_correction", {})
                    )
                    
                    # 保存配置
                    self.config_manager.data_sources[source_id] = new_config
                    self.config_manager.save_config()
                    self.refresh_data_source_list()
                    self.data_source_added.emit(source_id)
                    logger.info(f"✅ 已添加数据源: {new_config.name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加数据源失败: {str(e)}")
            logger.error(f"❌ 添加数据源失败: {e}")
    
    def _edit_data_source(self):
        """编辑数据源"""
        selected_row = self.data_source_table.currentRow()
        if selected_row < 0:
            return
        
        item = self.data_source_table.item(selected_row, 2)
        source_id = item.data(Qt.UserRole)
        
        try:
            config = self.config_manager.data_sources.get(source_id)
            if not config:
                QMessageBox.warning(self, "警告", "找不到该数据源配置")
                return
            
            # 转换为字典格式供对话框使用
            config_dict = {
                "basic": {
                    "name": config.name,
                    "description": "",
                    "category": "file",
                    "type": config.type
                },
                "connection": config.connection,
                "parser": config.parsing,
                "quality": config.quality_thresholds,
                "signal_filter": config.signal_filter or {},
                "sync": {},
                "axis_correction": config.axis_correction or {},
            }
            
            from .data_source_config_dialog import DataSourceConfigDialog
            dialog = DataSourceConfigDialog(self)
            if self._data_bridge:
                dialog.set_data_bridge(self._data_bridge)
            dialog.load_existing_config(source_id, config_dict)
            if dialog.exec():
                updated_data = dialog.get_config_data()
                if updated_data:
                    # 更新配置
                    basic = updated_data.get("basic", {})
                    config.name = basic.get("name", config.name)
                    config.type = basic.get("type", config.type)
                    config.connection = updated_data.get("connection", config.connection)
                    config.parsing = updated_data.get("parser", config.parsing)
                    config.quality_thresholds = updated_data.get("quality", config.quality_thresholds)
                    config.signal_filter = updated_data.get("signal_filter", config.signal_filter)
                    config.axis_correction = updated_data.get("axis_correction", config.axis_correction)
                    
                    self.config_manager.save_config()
                    self.refresh_data_source_list()
                    self.data_source_edited.emit(source_id)
                    logger.info(f"✅ 已更新数据源: {config.name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"编辑数据源失败: {str(e)}")
            logger.error(f"❌ 编辑数据源失败: {e}")
    
    def _delete_data_source(self):
        """删除数据源"""
        selected_row = self.data_source_table.currentRow()
        if selected_row < 0:
            return
        
        item = self.data_source_table.item(selected_row, 2)
        source_id = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除该数据源配置吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if source_id in self.config_manager.data_sources:
                    del self.config_manager.data_sources[source_id]
                    self.config_manager.save_config()
                    self.refresh_data_source_list()
                    self.data_source_deleted.emit(source_id)
                    logger.info(f"✅ 已删除数据源: {source_id}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除数据源失败: {str(e)}")
                logger.error(f"❌ 删除数据源失败: {e}")
    
    def _toggle_data_source(self):
        """切换数据源状态"""
        selected_row = self.data_source_table.currentRow()
        if selected_row < 0:
            return
        
        item = self.data_source_table.item(selected_row, 2)
        source_id = item.data(Qt.UserRole)
        
        try:
            config = self.config_manager.data_sources.get(source_id)
            if config:
                config.enabled = not config.enabled
                self.config_manager.save_config()
                self.refresh_data_source_list()
                self.data_source_toggled.emit(source_id, config.enabled)
                logger.info(f"✅ 数据源状态已切换: {source_id} -> {'启用' if config.enabled else '禁用'}")
                
                # 发送连接/断开信号
                if config.enabled:
                    self.data_source_connected.emit(source_id)
                else:
                    self.data_source_disconnected.emit(source_id)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换状态失败: {str(e)}")
            logger.error(f"❌ 切换数据源状态失败: {e}")
    
    def _toggle_extraction(self):
        """切换数据抽取状态"""
        if self._is_extracting:
            self._stop_extraction()
        else:
            self._start_extraction()

    def _start_extraction(self):
        """开始数据抽取"""
        self._is_extracting = True
        self.btn_extract.setText("停止")
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #E74C3C; color: white; font-weight: bold; font-size: 9pt; }"
            "QPushButton:hover { background-color: #C0392B; }"
        )
        self.label_pipeline_status.setText("流水线: 抽取中")
        logger.info("数据抽取已启动")
        self.extraction_started.emit()
        
        if not self._monitor_visible:
            self._toggle_monitor_panel()

        if self._data_bridge:
            try:
                self._data_bridge.start_processing()
                logger.info("DataBridge 分析处理已启动")
            except Exception as e:
                logger.error(f"启动 DataBridge 处理失败: {e}")

        try:
            from ..utils.data_reader_manager import get_data_reader_manager
            reader_manager = get_data_reader_manager(self.config_manager, self.pipeline_manager)
            if reader_manager:
                if self._data_bridge and hasattr(reader_manager, 'set_data_bridge'):
                    reader_manager.set_data_bridge(self._data_bridge)
                enabled_ids = [
                    sid for sid, cfg in self.config_manager.data_sources.items()
                    if getattr(cfg, 'enabled', False)
                ]
                if enabled_ids and hasattr(reader_manager, 'start_selected_readers'):
                    reader_manager.start_selected_readers(enabled_ids)
                    logger.info(f"直接启动了 {len(enabled_ids)} 个数据读取器: {enabled_ids}")
        except Exception as e:
            logger.error(f"直接启动读取器失败: {e}")

        try:
            from ..task_progress_manager import TaskProgressManager
            mgr = TaskProgressManager()
            mgr.update_progress("data_source", task_name="数据源抽取中", progress=10, detail="正在初始化数据读取器...")
        except Exception as e:
            logger.warning(f"更新任务进度失败: {e}")

    def _stop_extraction(self):
        """停止数据抽取"""
        self._is_extracting = False
        self.btn_extract.setText("开始")
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-weight: bold; font-size: 9pt; }"
            "QPushButton:hover { background-color: #219A52; }"
        )
        self.label_pipeline_status.setText("流水线: 空闲")
        logger.info("数据抽取已停止")
        self.extraction_stopped.emit()
        
        self._monitor_timer.stop()

        try:
            from ..utils.data_reader_manager import get_data_reader_manager
            reader_manager = get_data_reader_manager(self.config_manager, self.pipeline_manager)
            if reader_manager and hasattr(reader_manager, 'stop_all_readers'):
                reader_manager.stop_all_readers()
                logger.info("所有数据读取器已停止")
        except Exception as e:
            logger.warning(f"停止读取器失败: {e}")

        if self._data_bridge:
            try:
                self._data_bridge.stop_processing()
                logger.info("DataBridge 分析处理已停止")
            except Exception as e:
                logger.error(f"停止 DataBridge 处理失败: {e}")

        try:
            from ..task_progress_manager import TaskProgressManager
            mgr = TaskProgressManager()
            mgr.reset_module("data_source")
        except Exception as e:
            logger.warning(f"重置任务进度失败: {e}")

    def _on_pipeline_status_changed(self, status: PipelineStatus):
        """流水线状态变化处理"""
        status_text = {
            PipelineStatus.IDLE: "空闲",
            PipelineStatus.RUNNING: "运行中",
            PipelineStatus.PAUSED: "暂停",
            PipelineStatus.ERROR: "错误",
            PipelineStatus.STOPPING: "停止中"
        }.get(status, "未知")
        
        self.label_pipeline_status.setText(f"流水线: {status_text}")
        
        if status == PipelineStatus.RUNNING:
            self.label_pipeline_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        elif status == PipelineStatus.ERROR:
            self.label_pipeline_status.setStyleSheet("color: #E74C3C; font-weight: bold;")
        else:
            self.label_pipeline_status.setStyleSheet("")
    
    def get_active_sources(self):
        """获取活动的数据源列表"""
        active_sources = []
        configs = self.config_manager.data_source_configs
        for source_id, config in configs.items():
            if config.enabled:
                active_sources.append(source_id)
        return active_sources

    def _export_parsed_data(self):
        try:
            records = []
            has_data = False

            try:
                from ..utils.data_reader_manager import get_data_reader_manager
                reader_manager = get_data_reader_manager(self.config_manager, self.pipeline_manager)
                if reader_manager:
                    for source_id, reader in reader_manager.readers.items():
                        cache = getattr(reader, '_file_data_cache', [])
                        if not cache:
                            continue

                        first = cache[0] if cache else {}

                        if 'imu_name' in first and 'Ax_m_s2' in first:
                            for rec in cache:
                                out = {
                                    'rel_time': rec.get('rel_time', rec.get('timestamp', 0)),
                                    'channel': rec.get('channel', ''),
                                    'imu_name': rec.get('imu_name', ''),
                                    'Ax_m_s2': rec.get('Ax_m_s2', ''),
                                    'Ay_m_s2': rec.get('Ay_m_s2', ''),
                                    'Az_m_s2': rec.get('Az_m_s2', ''),
                                    'Gx_dps': rec.get('Gx_dps', ''),
                                    'Gy_dps': rec.get('Gy_dps', ''),
                                    'Gz_dps': rec.get('Gz_dps', ''),
                                    'Gx_rad_s': rec.get('Gx_rad_s', ''),
                                    'Gy_rad_s': rec.get('Gy_rad_s', ''),
                                    'Gz_rad_s': rec.get('Gz_rad_s', ''),
                                    'speed': rec.get('车速_kmh', rec.get('speed', '')),
                                    'wheel': rec.get('方向盘转角_deg', rec.get('wheel', '')),
                                }
                                records.append(out)
                            has_data = True

                        elif '_imu_name' in first and 'ax' in first:
                            for rec in cache:
                                out = {
                                    'rel_time': rec.get('timestamp', rec.get('rel_time', 0)),
                                    'channel': rec.get('channel', ''),
                                    'imu_name': rec.get('_imu_name', rec.get('imu_name', '')),
                                    'Ax_m_s2': rec.get('ax', ''),
                                    'Ay_m_s2': rec.get('ay', ''),
                                    'Az_m_s2': rec.get('az', ''),
                                    'Gx_dps': rec.get('gx', ''),
                                    'Gy_dps': rec.get('gy', ''),
                                    'Gz_dps': rec.get('gz', ''),
                                    'Gx_rad_s': rec.get('gx_rad', rec.get('gx', '')),
                                    'Gy_rad_s': rec.get('gy_rad', rec.get('gy', '')),
                                    'Gz_rad_s': rec.get('gz_rad', rec.get('gz', '')),
                                    'speed': rec.get('speed', ''),
                                    'wheel': rec.get('wheel', ''),
                                }
                                records.append(out)
                            has_data = True

                        elif any(k.startswith('ch') and '_ax' in k for k in first):
                            ch_prefixes = sorted(set(
                                '_'.join(k.split('_')[:1])
                                for k in first if k.startswith('ch') and '_ax' in k
                            ))
                            imu_map = {
                                'ch1': 'IMU1_头部眉心-1', 'ch3': 'IMU5_座垫R点-1',
                                'ch4': 'IMU7_座椅底部-1', 'ch5': 'IMU9_胸骨剑突-1',
                            }
                            for rec in cache:
                                for ch in ch_prefixes:
                                    out = {
                                        'rel_time': rec.get('timestamp', rec.get('rel_time', 0)),
                                        'channel': ch,
                                        'imu_name': imu_map.get(ch, ch),
                                        'Ax_m_s2': rec.get(f'{ch}_ax', ''),
                                        'Ay_m_s2': rec.get(f'{ch}_ay', ''),
                                        'Az_m_s2': rec.get(f'{ch}_az', ''),
                                        'Gx_dps': rec.get(f'{ch}_gx', ''),
                                        'Gy_dps': rec.get(f'{ch}_gy', ''),
                                        'Gz_dps': rec.get(f'{ch}_gz', ''),
                                        'Gx_rad_s': rec.get(f'{ch}_gx', ''),
                                        'Gy_rad_s': rec.get(f'{ch}_gy', ''),
                                        'Gz_rad_s': rec.get(f'{ch}_gz', ''),
                                        'speed': rec.get('speed', ''),
                                        'wheel': rec.get('wheel', rec.get('steering', '')),
                                    }
                                    records.append(out)
                            has_data = True

                        else:
                            for rec in cache:
                                records.append(rec)
                            has_data = True
            except Exception as e:
                logger.warning(f"从读取器获取数据失败: {e}")

            if not has_data:
                QMessageBox.warning(self, "无数据",
                    "当前没有已加载的解析数据。\n请先添加数据源并点击[开始]加载数据后再导出。")
                return

            data_output_dir = "data_output"
            if not os.path.exists(data_output_dir):
                os.makedirs(data_output_dir)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            default_filename = f"parsed_data_{timestamp}.csv"
            default_path = os.path.join(data_output_dir, default_filename)

            path, _ = QFileDialog.getSaveFileName(
                self, "导出解析数据", default_path, "CSV文件 (*.csv);;所有文件 (*)"
            )
            if not path:
                return

            fieldnames = ['rel_time', 'channel', 'imu_name',
                          'Ax_m_s2', 'Ay_m_s2', 'Az_m_s2',
                          'Gx_dps', 'Gy_dps', 'Gz_dps',
                          'Gx_rad_s', 'Gy_rad_s', 'Gz_rad_s',
                          'speed', 'wheel']
            existing = set(fieldnames)
            for r in records:
                for k in r:
                    if k not in existing:
                        fieldnames.append(k)
                        existing.add(k)

            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(records)

            logger.info(f"解析数据已导出: {path} ({len(records)} 条记录)")
            QMessageBox.information(self, "导出完成",
                f"已成功导出 {len(records)} 条解析数据\n保存路径:\n{path}")

        except Exception as e:
            logger.error(f"导出失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出解析数据时发生错误:\n{str(e)}")

    def _import_parsed_data(self):
        try:
            default_dir = "data_output"
            if not os.path.exists(default_dir):
                default_dir = ""

            path, _ = QFileDialog.getOpenFileName(
                self, "导入解析数据", default_dir,
                "CSV文件 (*.csv);;所有文件 (*)"
            )
            if not path:
                return

            with open(path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                QMessageBox.warning(self, "格式错误", "CSV文件中没有数据行")
                return

            required_fields = ['source_id', 'name', 'type']
            fieldnames = rows[0].keys()
            missing = [f for f in required_fields if f not in fieldnames]
            if missing:
                QMessageBox.warning(self, "格式错误",
                    f"CSV文件缺少必要字段: {', '.join(missing)}")
                return

            reply = QMessageBox.question(
                self, "导入选项",
                f"发现 {len(rows)} 个数据源配置\n\n"
                "选择[是]：替换所有数据源\n选择[否]：追加数据源",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                return

            if reply == QMessageBox.Yes:
                if hasattr(self.config_manager, 'clear_all'):
                    self.config_manager.clear_all()

            existing_ids = set()
            if hasattr(self.config_manager, 'data_sources'):
                existing_ids = set(self.config_manager.data_sources.keys())
            elif hasattr(self.config_manager, 'data_source_configs'):
                existing_ids = set(self.config_manager.data_source_configs.keys())

            imported_count = 0
            for row in rows:
                source_id = row.get('source_id', '').strip()
                if not source_id:
                    continue

                if reply == QMessageBox.No:
                    new_sid = source_id
                    counter = 1
                    while new_sid in existing_ids:
                        new_sid = f"{source_id}_imported_{counter}"
                        counter += 1
                    source_id = new_sid
                    existing_ids.add(source_id)

                config_data = {
                    'name': row.get('name', source_id),
                    'type': row.get('type', 'file'),
                    'enabled': row.get('enabled', 'True').strip().lower() in ('true', '1', 'yes'),
                    'file_path': row.get('file_path', ''),
                    'source_type': row.get('source_type', row.get('type', 'file')),
                }

                for field in ['connection', 'parsing', 'quality_thresholds',
                              'axis_correction', 'signal_filter']:
                    val = row.get(field, '').strip()
                    if val:
                        try:
                            config_data[field] = json.loads(val)
                        except json.JSONDecodeError:
                            config_data[field] = {}

                self._add_config_from_data(source_id, config_data)
                imported_count += 1

            self.refresh_data_source_list()
            logger.info(f"解析数据已导入: {path} ({imported_count} 个)")
            QMessageBox.information(self, "导入完成",
                f"已成功导入 {imported_count} 个数据源配置\n来源:\n{path}")

        except Exception as e:
            logger.error(f"导入失败: {e}")
            QMessageBox.critical(self, "导入失败", f"导入解析数据时发生错误:\n{str(e)}")

    def _add_config_from_data(self, source_id, config_data):
        """从导入数据添加配置"""
        try:
            from ..utils.config_manager import DataSourceConfig
            config = DataSourceConfig(
                name=config_data.get("name", source_id),
                source_type=config_data.get("type", config_data.get("source_type", "file")),
                file_path=config_data.get("file_path", ""),
                enabled=config_data.get("enabled", True),
                data_rate=config_data.get("data_rate", 0)
            )
            self.config_manager.add_data_source(source_id, config)
        except Exception as e:
            logger.warning(f"添加配置失败 {source_id}: {e}")
    
    def get_selected_sources(self):
        """获取选中的数据源列表"""
        selected_sources = []
        for row in range(self.data_source_table.rowCount()):
            checkbox = self.data_source_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = self.data_source_table.item(row, 2)
                if item:
                    source_id = item.data(Qt.UserRole)
                    selected_sources.append(source_id)
        return selected_sources
