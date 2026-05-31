from .base_control_panel import BaseControlPanel
from .multi_select_combobox import MultiSelectComboBox
from PySide6.QtWidgets import (
    QPushButton, QLabel, QComboBox, QFormLayout, QVBoxLayout, QHBoxLayout,
    QGroupBox, QListWidget, QFileDialog, QLineEdit, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGridLayout, QDoubleSpinBox,
    QWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from typing import Dict, Any
import logging
from core.core.unified_data_flow_manager import UnifiedDataFlowManager

logger = logging.getLogger(__name__)

class DataSourceControlPanel(BaseControlPanel):
    #  unified_data_source_manager 
    data_source_updated = Signal(dict)
    data_sources_updated = Signal(dict)
    right_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(" ", parent)  # 
        
        # 
        self.data_sources = {}
        self.active_source_id = None
        self.data_source_counter = 0
        
        # 
        self._create_sample_data()
        
        # 
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._safe_update_status)
        self.status_timer.start(5000)
        
        #  ()
        self.manager = UnifiedDataFlowManager()
        self.manager.register_left_panel('data_source', self)
        self.right_updated.connect(self.update_from_right)

        # UI
        self._init_ui()
        self.connect_signals()
    
    def _create_sample_data(self):
        """"""
        self.data_sources = {
            'source_001': {
                'basic': {
                    'name': 'IMU',
                    'type': 'IMU',
                    'description': ''
                },
                'status': 'connected',
                'data_rate': 100,
                'last_update': '2025-09-03 19:40:00'
            },
            'source_002': {
                'basic': {
                    'name': 'CNAP',
                    'type': 'CNAP',
                    'description': ''
                },
                'status': 'connected',
                'data_rate': 50,
                'last_update': '2025-09-03 19:40:05'
            },
            'source_003': {
                'basic': {
                    'name': 'ECG',
                    'type': 'ECG',
                    'description': ''
                },
                'status': 'disconnected',
                'data_rate': 0,
                'last_update': '2025-09-03 19:35:00'
            }
        }
        print(" ")

    def init_ui(self):
        if not hasattr(self, 'inner_layout') or self.inner_layout is None:
            self.inner_layout = QVBoxLayout()

        self._create_link_health_card()
        self._create_source_table_card()
        self._create_batch_operation_bar()
        self._create_connection_config_card()
        self._create_status_monitor_card()

    def _create_link_health_card(self):
        group = QGroupBox("链接健康度")
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(10)

        self.total_sources_label = QLabel("总数: 0")
        self.connected_sources_label = QLabel("已链接: 0")
        self.disconnected_sources_label = QLabel("未链接: 0")
        self.link_error_label = QLabel("异常: 0")
        self.link_rate_label = QLabel("链接率: 0%")
        self.sync_status_label = QLabel("同步: 待机")

        grid.addWidget(self.total_sources_label, 0, 0)
        grid.addWidget(self.connected_sources_label, 0, 1)
        grid.addWidget(self.disconnected_sources_label, 0, 2)
        grid.addWidget(self.link_error_label, 1, 0)
        grid.addWidget(self.link_rate_label, 1, 1)
        grid.addWidget(self.sync_status_label, 1, 2)

        self.inner_layout.addWidget(group)

    def _create_source_table_card(self):
        group = QGroupBox("数据源列表")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(6)
        self.sources_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "状态", "采样率(Hz)", "延迟"])
        header = self.sources_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.sources_table.setAlternatingRowColors(True)
        self.sources_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sources_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sources_table.verticalHeader().setVisible(False)
        layout.addWidget(self.sources_table)

        self.inner_layout.addWidget(group)

    def _create_batch_operation_bar(self):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 2, 0, 2)
        bar_layout.setSpacing(6)

        self.link_all_btn = QPushButton("全部链接")
        self.link_all_btn.clicked.connect(self._link_all_sources)
        bar_layout.addWidget(self.link_all_btn)

        self.unlink_all_btn = QPushButton("全部断开")
        self.unlink_all_btn.clicked.connect(self._unlink_all_sources)
        bar_layout.addWidget(self.unlink_all_btn)

        bar_layout.addStretch()

        self.add_source_btn = QPushButton("添加数据源")
        self.add_source_btn.clicked.connect(self._add_data_source)
        bar_layout.addWidget(self.add_source_btn)

        self.import_config_btn = QPushButton("导入配置")
        self.import_config_btn.clicked.connect(self._import_config)
        bar_layout.addWidget(self.import_config_btn)

        self._is_extracting = False
        self.extract_btn = QPushButton("▶ 开始抽取")
        self.extract_btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #219A52; }"
        )
        self.extract_btn.clicked.connect(self._toggle_extraction)
        bar_layout.addWidget(self.extract_btn)

        self.inner_layout.addWidget(bar)

    def _create_connection_config_card(self):
        group = QGroupBox("连接配置")
        form = QFormLayout(group)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(6)

        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems(["串口 (Serial)", "TCP/IP 网络", "UDP 数据报", "文件读取", "WebSocket", "MQTT 消息"])
        form.addRow("连接方式:", self.conn_type_combo)

        self.conn_address_edit = QLineEdit()
        self.conn_address_edit.setPlaceholderText("如 COM3 或 192.168.1.100:8080")
        form.addRow("连接地址:", self.conn_address_edit)

        self.conn_baud_combo = QComboBox()
        self.conn_baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.conn_baud_combo.setCurrentText("115200")
        form.addRow("波特率:", self.conn_baud_combo)

        self.conn_timeout_spin = QDoubleSpinBox()
        self.conn_timeout_spin.setRange(0.5, 60.0)
        self.conn_timeout_spin.setValue(5.0)
        self.conn_timeout_spin.setSuffix(" 秒")
        form.addRow("超时时间:", self.conn_timeout_spin)

        self.auto_reconnect_check = QCheckBox("断线自动重连")
        self.auto_reconnect_check.setChecked(True)
        form.addRow("", self.auto_reconnect_check)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.test_conn_btn = QPushButton("测试连接")
        self.test_conn_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self.test_conn_btn)

        self.apply_conn_btn = QPushButton("应用连接")
        self.apply_conn_btn.clicked.connect(self._apply_connection)
        btn_row.addWidget(self.apply_conn_btn)

        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.clicked.connect(self._disconnect_source)
        btn_row.addWidget(self.disconnect_btn)

        btn_row.addStretch()
        form.addRow("", QWidget())  # spacer
        group.layout().addLayout(btn_row, group.layout().rowCount(), 0, 1, 2)

        self.inner_layout.addWidget(group)

    def _create_status_monitor_card(self):
        group = QGroupBox("状态监控")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 6, 8, 6)

        self.status_info_label = QLabel("🟢 系统运行正常")
        layout.addWidget(self.status_info_label)

        self.inner_layout.addWidget(group)
        
    def connect_signals(self):
        pass

    def _link_all_sources(self):
        for i in range(self.sources_table.rowCount()):
            self.sources_table.setItem(i, 3, QTableWidgetItem("已链接"))
        self._update_link_health()
        self.status_info_label.setText("🟢 全部数据源已链接")

    def _unlink_all_sources(self):
        for i in range(self.sources_table.rowCount()):
            self.sources_table.setItem(i, 3, QTableWidgetItem("未链接"))
        self._update_link_health()
        self.status_info_label.setText("⚪ 全部数据源已断开")

    def _add_data_source(self):
        self.status_info_label.setText("📋 添加数据源功能待实现")

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON文件 (*.json);;所有文件 (*)")
        if path:
            self.status_info_label.setText(f"📥 已导入配置: {path}")

    def _test_connection(self):
        addr = self.conn_address_edit.text() or "未指定"
        conn_type = self.conn_type_combo.currentText()
        self.status_info_label.setText(f"🔍 正在测试 {conn_type} → {addr} ...")

    def _apply_connection(self):
        addr = self.conn_address_edit.text() or "未指定"
        self.status_info_label.setText(f"🔗 已应用连接: {addr}")

    def _disconnect_source(self):
        self.status_info_label.setText("⏹ 连接已断开")

    def _toggle_extraction(self):
        """切换数据抽取状态"""
        if self._is_extracting:
            self._stop_extraction()
        else:
            self._start_extraction()

    def _start_extraction(self):
        """开始数据抽取"""
        self._is_extracting = True
        self.extract_btn.setText("⏹ 停止抽取")
        self.extract_btn.setStyleSheet(
            "QPushButton { background-color: #E74C3C; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #C0392B; }"
        )
        self.sync_status_label.setText("同步: 抽取中")
        self.status_info_label.setText("🟢 数据抽取已启动")

        self._start_data_pipeline()

        if hasattr(self, 'manager') and self.manager:
            try:
                if hasattr(self.manager, 'communication_bus'):
                    self.manager.communication_bus.publish_status_change(
                        "extraction_started",
                        {"source": "data_source_panel", "timestamp": __import__('time').time()}
                    )
            except Exception as e:
                logger.warning(f"通知抽取启动失败: {e}")

        logger.info("数据抽取已启动")

    def _start_data_pipeline(self):
        """实际启动数据流水线"""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return

            from .data_fusion_panel import DataFusionPanel
            fusion_panel = app.findChild(DataFusionPanel)
            if fusion_panel and hasattr(fusion_panel, '_start_pipeline'):
                fusion_panel._start_pipeline()
                logger.info("通过 DataFusionPanel 启动流水线成功")
                return

            from .data_source_config.data_source_list_panel import DataSourceListPanel
            list_panel = app.findChild(DataSourceListPanel)
            if list_panel and hasattr(list_panel, 'extraction_started'):
                list_panel.extraction_started.emit()
                logger.info("通过 DataSourceListPanel 信号启动流水线成功")
                return

            logger.warning("未找到可启动的数据流水线组件")
        except Exception as e:
            logger.error(f"启动数据流水线失败: {e}")

    def _stop_extraction(self):
        """停止数据抽取"""
        self._is_extracting = False
        self.extract_btn.setText("▶ 开始抽取")
        self.extract_btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #219A52; }"
        )
        self.sync_status_label.setText("同步: 待机")
        self.status_info_label.setText("⚪ 数据抽取已停止")

        self._stop_data_pipeline()

        if hasattr(self, 'manager') and self.manager:
            try:
                if hasattr(self.manager, 'communication_bus'):
                    self.manager.communication_bus.publish_status_change(
                        "extraction_stopped",
                        {"source": "data_source_panel", "timestamp": __import__('time').time()}
                    )
            except Exception as e:
                logger.warning(f"通知抽取停止失败: {e}")

        logger.info("数据抽取已停止")

    def _stop_data_pipeline(self):
        """实际停止数据流水线"""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                return

            from .data_fusion_panel import DataFusionPanel
            fusion_panel = app.findChild(DataFusionPanel)
            if fusion_panel and hasattr(fusion_panel, '_stop_pipeline'):
                fusion_panel._stop_pipeline()
                logger.info("通过 DataFusionPanel 停止流水线成功")
                return

            from .data_source_config.data_source_list_panel import DataSourceListPanel
            list_panel = app.findChild(DataSourceListPanel)
            if list_panel and hasattr(list_panel, 'extraction_stopped'):
                list_panel.extraction_stopped.emit()
                logger.info("通过 DataSourceListPanel 信号停止流水线成功")
                return

            if hasattr(self, 'manager') and self.manager:
                if hasattr(self.manager, 'sync_engine') and self.manager.sync_engine:
                    if hasattr(self.manager.sync_engine, 'stop'):
                        self.manager.sync_engine.stop()
                if hasattr(self.manager, 'processing_engine') and self.manager.processing_engine:
                    if hasattr(self.manager.processing_engine, 'stop'):
                        self.manager.processing_engine.stop()

            logger.warning("未找到可停止的数据流水线组件")
        except Exception as e:
            logger.error(f"停止数据流水线失败: {e}")
    
    def _safe_update_status(self):
        """"""
        try:
            if hasattr(self, 'status_info_label') and self.status_info_label:
                # 
                if not self.status_info_label.isVisible():
                    return
                self.status_info_label.setText("🟢 ...")
        except Exception as e:
            logger.error(f": {e}")
            # 
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
    
    def update_status(self, message):
        """"""
        try:
            if hasattr(self, 'status_info_label') and self.status_info_label:
                self.status_info_label.setText(message)
        except Exception as e:
            logger.error(f": {e}")

    def _update_link_health(self):
        try:
            total = self.sources_table.rowCount()
            linked = 0
            unlinked = 0
            error_count = 0
            for row in range(total):
                status_item = self.sources_table.item(row, 3)
                if status_item:
                    text = status_item.text()
                    if "已链接" in text:
                        linked += 1
                    elif "异常" in text or "错误" in text:
                        error_count += 1
                    else:
                        unlinked += 1
                else:
                    unlinked += 1

            self.total_sources_label.setText(f"总数: {total}")
            self.connected_sources_label.setText(f"已链接: {linked}")
            self.disconnected_sources_label.setText(f"未链接: {unlinked}")
            self.link_error_label.setText(f"异常: {error_count}")
            rate = f"{int(linked / total * 100)}%" if total > 0 else "0%"
            self.link_rate_label.setText(f"链接率: {rate}")
            self.sync_status_label.setText("同步: 运行中" if linked > 0 else "同步: 待机")
        except Exception as e:
            logger.error(f"更新链接健康度失败: {e}")
        
    # 
        
    def _refresh_status(self):
        """"""
        self.action_triggered.emit("REFRESH_STATUS", {})
        
    # 
        
    def update_status(self):
        """"""
        try:
            self.data_sources = self.manager.get_data_sources()
            self._update_overview()
            self._populate_table()
            self.data_sources_updated.emit(self.data_sources)
        except Exception as e:
            logger.error(f": {e}")

    def _update_overview(self):
        self._update_link_health()

    def _populate_table(self):
        self.sources_table.setRowCount(len(self.data_sources))
        for i, (sid, source) in enumerate(self.data_sources.items()):
            self.sources_table.setItem(i, 0, QTableWidgetItem(sid))
            self.sources_table.setItem(i, 1, QTableWidgetItem(source.get('basic', {}).get('name', source.get('name', ''))))
            self.sources_table.setItem(i, 2, QTableWidgetItem(source.get('basic', {}).get('type', source.get('type', ''))))
            status = source.get('status', 'disconnected')
            self.sources_table.setItem(i, 3, QTableWidgetItem("已链接" if status == 'connected' else "未链接"))
            self.sources_table.setItem(i, 4, QTableWidgetItem(str(source.get('data_rate', 0))))
            self.sources_table.setItem(i, 5, QTableWidgetItem(source.get('last_update', '')))
        self._update_link_health()

    def refresh_data(self):
        try:
            self.logger.info("刷新数据源列表")
            if hasattr(self, 'manager') and self.manager:
                if hasattr(self.manager, 'get_all_data_sources'):
                    self.data_sources = self.manager.get_all_data_sources()
                    self.logger.info(f"获取到 {len(self.data_sources)} 个数据源")
                self._populate_table()
                self.data_sources_updated.emit(self.data_sources)
                self.status_info_label.setText("🟢 数据源列表已刷新")
            else:
                self._populate_table()
                self.status_info_label.setText("🟢 数据源列表已刷新（本地）")
        except Exception as e:
            self.logger.error(f"刷新数据源失败: {e}")
            self.status_info_label.setText(f"⚠ 刷新失败: {str(e)}")

    #  _handle_sync_update
    def _handle_sync_update(self, data_sources):
        self.data_sources = data_sources
        logger.info("")

    def update_from_right(self, data):
        self.data_sources = data
        self._update_overview()
        self._populate_table()
        logger.info("")