import sys
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                               QGroupBox, QFormLayout, QLineEdit, QPushButton, 
                               QCheckBox, QSpinBox, QLabel, QTableWidget, 
                               QTableWidgetItem, QMessageBox, QTextEdit, 
                               QHeaderView, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont

class ExtensionIntegrationWidget(QWidget):
    """扩展与集成功能的UI组件"""
    save_config = Signal(str, dict)  # 服务ID, 配置
    connect_service = Signal(str)    # 服务ID
    disconnect_service = Signal(str) # 服务ID
    sync_data = Signal(str)          # 服务ID
    start_api_server = Signal(int)   # 端口
    stop_api_server = Signal()

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ExtensionIntegrationWidget")
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 创建各功能页面
        self.api_tab = self._create_api_tab()
        self.plugins_tab = self._create_plugins_tab()
        self.services_tab = self._create_services_tab()
        
        # 添加标签页
        self.tabs.addTab(self.api_tab, "API接口")
        self.tabs.addTab(self.plugins_tab, "插件管理")
        self.tabs.addTab(self.services_tab, "第三方服务")
        
        # 添加到主布局
        main_layout.addWidget(self.tabs)

    def _create_api_tab(self):
        """创建API接口配置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # API服务器状态
        status_group = QGroupBox("API服务器状态")
        status_layout = QFormLayout()
        
        self.api_status_label = QLabel("未运行")
        self.api_status_label.setStyleSheet("color: #888;")
        
        self.api_port_input = QSpinBox()
        self.api_port_input.setRange(1024, 65535)
        self.api_port_input.setValue(5000)
        
        status_layout.addRow("当前状态:", self.api_status_label)
        status_layout.addRow("端口号:", self.api_port_input)
        status_group.setLayout(status_layout)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_api_btn = QPushButton("启动API服务器")
        self.stop_api_btn = QPushButton("停止API服务器")
        self.stop_api_btn.setEnabled(False)
        
        self.start_api_btn.clicked.connect(self._on_start_api)
        self.stop_api_btn.clicked.connect(self._on_stop_api)
        
        btn_layout.addWidget(self.start_api_btn)
        btn_layout.addWidget(self.stop_api_btn)
        
        # API文档
        doc_group = QGroupBox("API文档")
        doc_layout = QVBoxLayout()
        
        self.api_doc_view = QTextEdit()
        self.api_doc_view.setReadOnly(True)
        self.api_doc_view.setHtml("""
        <h3>车辆监控系统API接口</h3>
        <p>基础URL: http://localhost:端口/api/v1</p>
        
        <h4>系统状态</h4>
        <p>GET /status - 获取系统运行状态</p>
        
        <h4>数据查询</h4>
        <p>GET /driving-data - 获取驾驶数据</p>
        <p>GET /behavior-events - 获取行为事件</p>
        
        <h4>控制接口</h4>
        <p>POST /recording - 控制数据记录</p>
        <p>POST /connection - 控制设备连接</p>
        
        <h4>配置接口</h4>
        <p>GET /config - 获取系统配置</p>
        <p>PUT /config - 更新系统配置</p>
        """)
        
        doc_layout.addWidget(self.api_doc_view)
        doc_group.setLayout(doc_layout)
        
        # 添加到布局
        layout.addWidget(status_group)
        layout.addLayout(btn_layout)
        layout.addWidget(doc_group)
        
        return widget

    def _create_plugins_tab(self):
        """创建插件管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 插件列表
        list_group = QGroupBox("已安装插件")
        list_layout = QVBoxLayout()
        
        self.plugins_list = QListWidget()
        
        # 插件信息
        self.plugin_info = QTextEdit()
        self.plugin_info.setReadOnly(True)
        self.plugin_info.setMaximumHeight(100)
        
        list_layout.addWidget(self.plugins_list)
        list_layout.addWidget(QLabel("插件信息:"))
        list_layout.addWidget(self.plugin_info)
        list_group.setLayout(list_layout)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.load_plugin_btn = QPushButton("加载插件")
        self.unload_plugin_btn = QPushButton("卸载插件")
        self.reload_plugins_btn = QPushButton("重新加载所有")
        self.install_plugin_btn = QPushButton("安装新插件...")
        
        self.unload_plugin_btn.setEnabled(False)
        
        # 连接按钮信号
        self.plugins_list.itemSelectionChanged.connect(self._on_plugin_selected)
        self.load_plugin_btn.clicked.connect(self._on_load_plugin)
        self.unload_plugin_btn.clicked.connect(self._on_unload_plugin)
        self.reload_plugins_btn.clicked.connect(self._on_reload_plugins)
        self.install_plugin_btn.clicked.connect(self._on_install_plugin)
        
        btn_layout.addWidget(self.load_plugin_btn)
        btn_layout.addWidget(self.unload_plugin_btn)
        btn_layout.addWidget(self.reload_plugins_btn)
        btn_layout.addWidget(self.install_plugin_btn)
        
        # 添加到布局
        layout.addWidget(list_group)
        layout.addLayout(btn_layout)
        
        return widget

    def _create_services_tab(self):
        """创建第三方服务页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 服务列表
        self.services_table = QTableWidget(0, 5)
        self.services_table.setHorizontalHeaderLabels(
            ["服务名称", "状态", "启用", "配置", "操作"]
        )
        self.services_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        
        # 添加服务行
        self._add_service_row(
            "gps_tracking", "GPS轨迹服务", False, False
        )
        self._add_service_row(
            "driver_analytics", "驾驶分析服务", False, False
        )
        self._add_service_row(
            "notification_service", "通知推送服务", False, False
        )
        
        # 添加到布局
        layout.addWidget(QLabel("<b>第三方服务集成</b>"))
        layout.addWidget(self.services_table)
        
        return widget

    def _add_service_row(self, service_id, name, connected, enabled):
        """添加服务行到表格"""
        row = self.services_table.rowCount()
        self.services_table.insertRow(row)
        
        # 服务名称
        self.services_table.setItem(row, 0, QTableWidgetItem(name))
        self.services_table.item(row, 0).setData(Qt.UserRole, service_id)
        
        # 状态
        status_item = QTableWidgetItem("已连接" if connected else "未连接")
        status_item.setForeground(
            QColor("green") if connected else QColor("#888")
        )
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        self.services_table.setItem(row, 1, status_item)
        
        # 启用复选框
        enable_widget = QWidget()
        enable_layout = QHBoxLayout(enable_widget)
        enable_layout.setContentsMargins(0, 0, 0, 0)
        
        enable_checkbox = QCheckBox()
        enable_checkbox.setChecked(enabled)
        # enable_checkbox.setAlignment(Qt.AlignCenter)  # QCheckBox 不支持 setAlignment
        enable_checkbox.service_id = service_id
        enable_checkbox.toggled.connect(self._on_service_toggled)
        
        enable_layout.addWidget(enable_checkbox)
        self.services_table.setCellWidget(row, 2, enable_widget)
        
        # 配置按钮
        config_btn = QPushButton("配置")
        config_btn.service_id = service_id
        config_btn.clicked.connect(self._on_config_service)
        self.services_table.setCellWidget(row, 3, config_btn)
        
        # 操作按钮
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        
        connect_btn = QPushButton("连接" if not connected else "断开")
        connect_btn.service_id = service_id
        connect_btn.connected = connected
        connect_btn.clicked.connect(self._on_toggle_service)
        
        sync_btn = QPushButton("同步")
        sync_btn.service_id = service_id
        sync_btn.clicked.connect(self._on_sync_service)
        sync_btn.setEnabled(connected)
        
        action_layout.addWidget(connect_btn)
        action_layout.addWidget(sync_btn)
        self.services_table.setCellWidget(row, 4, action_widget)

    def update_service_status(self, service_name, connected):
        """更新服务状态"""
        for row in range(self.services_table.rowCount()):
            item = self.services_table.item(row, 0)
            if item.text() == service_name:
                # 更新状态文本
                status_item = self.services_table.item(row, 1)
                status_item.setText("已连接" if connected else "未连接")
                status_item.setForeground(
                    QColor("green") if connected else QColor("#888")
                )
                
                # 更新操作按钮
                action_widget = self.services_table.cellWidget(row, 4)
                connect_btn = action_widget.findChild(QPushButton)
                sync_btn = action_widget.findChildren(QPushButton)[1]
                
                connect_btn.setText("断开" if connected else "连接")
                connect_btn.connected = connected
                sync_btn.setEnabled(connected)
                break

    def update_api_status(self, running, port=None):
        """更新API服务器状态"""
        if running:
            self.api_status_label.setText(f"运行中 (端口: {port})")
            self.api_status_label.setStyleSheet("color: green;")
            self.start_api_btn.setEnabled(False)
            self.stop_api_btn.setEnabled(True)
            self.api_port_input.setEnabled(False)
        else:
            self.api_status_label.setText("未运行")
            self.api_status_label.setStyleSheet("color: #888;")
            self.start_api_btn.setEnabled(True)
            self.stop_api_btn.setEnabled(False)
            self.api_port_input.setEnabled(True)

    def update_plugins_list(self, plugins, available_plugins):
        """更新插件列表"""
        self.plugins_list.clear()
        
        for name, info in available_plugins.items():
            item = QListWidgetItem(f"{name} - {info.get('description', '无描述')}")
            item.setData(Qt.UserRole, name)
            
            # 如果插件已加载，设置不同的颜色
            if name in plugins:
                item.setForeground(QColor("green"))
                item.setToolTip("已加载")
                
            self.plugins_list.addItem(item)

    def _on_start_api(self):
        """启动API服务器"""
        port = self.api_port_input.value()
        self.start_api_server.emit(port)

    def _on_stop_api(self):
        """停止API服务器"""
        self.stop_api_server.emit()

    def _on_service_toggled(self, checked):
        """服务启用状态变化"""
        service_id = self.sender().service_id
        self.logger.info(f"服务 {service_id} 启用状态: {checked}")
        
        # 更新配置中的启用状态
        for row in range(self.services_table.rowCount()):
            item = self.services_table.item(row, 0)
            if item.data(Qt.UserRole) == service_id:
                config_btn = self.services_table.cellWidget(row, 3)
                config_btn.setEnabled(checked)
                break

    def _on_config_service(self):
        """配置服务"""
        service_id = self.sender().service_id
        service_name = ""
        
        # 获取服务名称
        for row in range(self.services_table.rowCount()):
            item = self.services_table.item(row, 0)
            if item.data(Qt.UserRole) == service_id:
                service_name = item.text()
                break
                
        # 创建配置对话框
        from PySide6.QtWidgets import QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"配置 {service_name}")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 根据服务类型添加不同的配置项
        config_widget = QWidget()
        config_layout = QFormLayout(config_widget)
        
        # 通用配置
        self.api_url_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        config_layout.addRow("API地址:", self.api_url_input)
        config_layout.addRow("API密钥:", self.api_key_input)
        
        # 同步间隔(对不需要定时器的服务隐藏)
        if service_id != "notification_service":
            self.sync_interval_input = QSpinBox()
            self.sync_interval_input.setRange(10, 3600)
            self.sync_interval_input.setSuffix(" 秒")
            self.sync_interval_input.setValue(60)
            config_layout.addRow("同步间隔:", self.sync_interval_input)
        
        layout.addWidget(config_widget)
        
        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        
        save_btn.clicked.connect(lambda: self._save_service_config(dialog, service_id))
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _save_service_config(self, dialog, service_id):
        """保存服务配置"""
        # 构建配置数据
        config = {
            "enabled": True,
            "api_url": self.api_url_input.text(),
            "api_key": self.api_key_input.text()
        }
        
        # 添加同步间隔(如适用)
        if service_id != "notification_service" and hasattr(self, 'sync_interval_input'):
            config["sync_interval"] = self.sync_interval_input.value() * 1000  # 转为毫秒
            
        # 发送保存信号
        self.save_config.emit(service_id, config)
        dialog.accept()
        
        QMessageBox.information(self, "保存成功", "服务配置已保存")

    def _on_toggle_service(self):
        """切换服务连接状态"""
        sender = self.sender()
        service_id = sender.service_id
        
        if sender.connected:
            self.disconnect_service.emit(service_id)
        else:
            self.connect_service.emit(service_id)

    def _on_sync_service(self):
        """同步服务数据"""
        service_id = self.sender().service_id
        self.sync_data.emit(service_id)

    def _on_plugin_selected(self):
        """插件被选中"""
        selected_items = self.plugins_list.selectedItems()
        if selected_items:
            self.unload_plugin_btn.setEnabled(True)
            # 显示插件信息
            plugin_name = selected_items[0].data(Qt.UserRole)
            self.plugin_info.setText(f"插件名称: {plugin_name}\n"
                                    f"状态: {'已加载' if selected_items[0].foreground().color() == QColor('green') else '未加载'}")
        else:
            self.unload_plugin_btn.setEnabled(False)
            self.plugin_info.clear()

    def _on_load_plugin(self):
        """加载插件"""
        selected_items = self.plugins_list.selectedItems()
        if selected_items:
            plugin_name = selected_items[0].data(Qt.UserRole)
            # 通知主控制器加载插件
            if hasattr(self, 'load_plugin'):
                self.load_plugin.emit(plugin_name)

    def _on_unload_plugin(self):
        """卸载插件"""
        selected_items = self.plugins_list.selectedItems()
        if selected_items:
            plugin_name = selected_items[0].data(Qt.UserRole)
            # 通知主控制器卸载插件
            if hasattr(self, 'unload_plugin'):
                self.unload_plugin.emit(plugin_name)

    def _on_reload_plugins(self):
        """重新加载所有插件"""
        if hasattr(self, 'reload_plugins'):
            self.reload_plugins.emit()

    def _on_install_plugin(self):
        """安装新插件"""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择插件文件", "", "Python插件 (*.py)"
        )
        
        if file_path:
            try:
                # 复制插件文件到插件目录
                import shutil
                # from ui.extension.plugin_manager import PluginManager
                # 暂时注释掉，避免导入错误
                
                # 使用默认插件目录
                import os
                plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
                if not os.path.exists(plugin_dir):
                    os.makedirs(plugin_dir)
                shutil.copy2(file_path, plugin_dir)
                
                # 刷新插件列表
                if hasattr(self, 'reload_plugins'):
                    self.reload_plugins.emit()
                    
                QMessageBox.information(self, "安装成功", "插件已安装，请加载使用")
            except Exception as e:
                QMessageBox.warning(self, "安装失败", f"插件安装出错: {str(e)}")
