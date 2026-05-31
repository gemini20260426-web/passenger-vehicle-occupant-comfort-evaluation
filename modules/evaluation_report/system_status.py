"""系统状态监控组件（实时显示各模块运行状态）"""
import logging
import time
from typing import Dict, Any, List
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
                             QFrame, QProgressBar, QPushButton, QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMutex, QMutexLocker
from PySide6.QtGui import QColor, QIcon, QFont

class SystemStatusWidget(QWidget):
    """系统状态监控组件（保持原有类名）"""
    # 信号定义（新增内部状态更新信号）
    _status_updated = Signal(dict)

    def __init__(self, main_app):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.main_app = main_app  # 主应用实例
        
        # 线程安全锁（新增）
        self.status_lock = QMutex()
        
        # 状态数据（保持原有）
        self.module_status = {
            'application': {
                'status': 'unknown',
                'message': '未初始化',
                'last_update': 0
            },
            'communication': {
                'status': 'unknown',
                'message': '未连接',
                'last_update': 0
            },
            'data_processing': {
                'status': 'unknown',
                'message': '未启动',
                'last_update': 0
            },
            'storage': {
                'status': 'unknown',
                'message': '未连接',
                'last_update': 0
            },
            'analysis': {
                'status': 'unknown',
                'message': '未启动',
                'last_update': 0
            }
        }
        
        # 系统资源使用情况（新增）
        self.resource_usage = {
            'cpu': 0.0,
            'memory': 0.0,
            'disk': 0.0
        }
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 连接信号（新增）
        self._connect_signals()
        
        # 启动状态监控定时器（新增）
        self._start_monitoring()

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("系统状态")
        self.setMinimumWidth(400)
        
        # 标题（保持原有）
        title_label = QLabel("系统状态监控")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 模块状态网格（保持原有）
        status_grid = QGridLayout()
        status_grid.setSpacing(10)
        
        # 状态标签样式（保持原有）
        self.status_labels = {}
        row = 0
        
        for module, info in self.module_status.items():
            # 模块名称
            name_label = QLabel(self._get_module_display_name(module))
            name_label.setFont(QFont("Arial", 10, QFont.Bold))
            status_grid.addWidget(name_label, row, 0)
            
            # 状态指示器
            status_frame = QFrame()
            status_frame.setMinimumWidth(20)
            status_frame.setMaximumWidth(20)
            status_frame.setMinimumHeight(20)
            status_frame.setMaximumHeight(20)
            status_frame.setStyleSheet("background-color: gray; border-radius: 10px;")
            status_grid.addWidget(status_frame, row, 1)
            
            # 状态消息
            msg_label = QLabel(info['message'])
            msg_label.setMinimumWidth(200)
            status_grid.addWidget(msg_label, row, 2)
            
            # 保存引用
            self.status_labels[module] = {
                'indicator': status_frame,
                'message': msg_label
            }
            
            row += 1
        
        main_layout.addLayout(status_grid)
        
        # 资源使用情况（新增）
        resource_group = QFrame()
        resource_group.setFrameShape(QFrame.StyledPanel)
        resource_layout = QVBoxLayout(resource_group)
        
        resource_title = QLabel("系统资源使用")
        resource_title.setFont(QFont("Arial", 12, QFont.Bold))
        resource_layout.addWidget(resource_title)
        
        # CPU使用率
        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(QLabel("CPU:"))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFormat("%v%")
        cpu_layout.addWidget(self.cpu_bar)
        resource_layout.addLayout(cpu_layout)
        
        # 内存使用率
        mem_layout = QHBoxLayout()
        mem_layout.addWidget(QLabel("内存:"))
        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setFormat("%v%")
        mem_layout.addWidget(self.mem_bar)
        resource_layout.addLayout(mem_layout)
        
        main_layout.addWidget(resource_group)
        
        # 操作按钮（保持原有）
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self._refresh_status)
        btn_layout.addWidget(self.refresh_btn)
        
        self.restart_btn = QPushButton("重启服务")
        self.restart_btn.clicked.connect(self._restart_services)
        btn_layout.addWidget(self.restart_btn)
        
        main_layout.addLayout(btn_layout)

    def _get_module_display_name(self, module: str) -> str:
        """获取模块显示名称（保持原有方法）"""
        name_map = {
            'application': '应用程序',
            'communication': '通信模块',
            'data_processing': '数据处理',
            'storage': '数据存储',
            'analysis': '分析引擎'
        }
        return name_map.get(module, module)

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 内部状态更新信号（确保在UI线程处理）
        self._status_updated.connect(self._update_status_display)
        
        # 连接主应用的状态信号
        if hasattr(self.main_app, 'status_updated'):
            self.main_app.status_updated.connect(self.update_module_status)

    def _start_monitoring(self) -> None:
        """启动状态监控定时器（新增）"""
        # 状态刷新定时器（5秒一次）
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh_status)
        self.status_timer.start(5000)
        
        # 资源监控定时器（2秒一次）
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._update_resource_usage)
        self.resource_timer.start(2000)
        
        # 初始刷新
        self._refresh_status()

    @Slot()
    def _refresh_status(self) -> None:
        """刷新系统状态（保持原有方法）"""
        # 在后台线程获取状态
        import threading
        threading.Thread(target=self._fetch_all_status, daemon=True).start()

    def _fetch_all_status(self) -> None:
        """获取所有模块状态（新增线程安全实现）"""
        try:
            # 获取应用程序状态
            app_status = {
                'status': 'running',
                'message': f'运行中 (版本: {self.main_app.version})',
                'last_update': time.time()
            }
            
            # 获取各模块状态（通过主应用接口）
            status_updates = {
                'application': app_status,
                'communication': self.main_app.get_communication_status(),
                'data_processing': self.main_app.get_data_processing_status(),
                'storage': self.main_app.get_storage_status(),
                'analysis': self.main_app.get_analysis_status()
            }
            
            # 更新状态（线程安全）
            with QMutexLocker(self.status_lock):
                for module, status in status_updates.items():
                    if module in self.module_status:
                        self.module_status[module].update(status)
            
            # 通知UI更新
            self._status_updated.emit(status_updates)
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {str(e)}")

    def _update_resource_usage(self) -> None:
        """更新系统资源使用情况（新增）"""
        try:
            # 仅在支持的平台上获取资源使用情况
            import platform
            if platform.system() in ['Windows', 'Linux', 'Darwin']:
                # 使用psutil获取系统资源（保持原有依赖）
                import psutil
                
                # CPU使用率
                cpu_usage = psutil.cpu_percent(interval=None)
                
                # 内存使用率
                mem = psutil.virtual_memory()
                mem_usage = mem.percent
                
                # 更新资源使用情况（线程安全）
                with QMutexLocker(self.status_lock):
                    self.resource_usage['cpu'] = cpu_usage
                    self.resource_usage['memory'] = mem_usage
                
                # 在UI线程更新进度条
                self.cpu_bar.setValue(int(cpu_usage))
                self.mem_bar.setValue(int(mem_usage))
                
        except Exception as e:
            self.logger.warning(f"获取资源使用情况失败: {str(e)}")

    @Slot(dict)
    def _update_status_display(self, status_updates: Dict[str, Any]) -> None:
        """更新状态显示（保持原有方法）"""
        # 状态颜色映射（原有逻辑）
        color_map = {
            'running': 'green',
            'connected': 'green',
            'active': 'green',
            'warning': '#FFC107',
            'error': 'red',
            'stopped': 'gray',
            'disconnected': 'red',
            'unknown': 'gray'
        }
        
        # 更新各模块显示
        for module, status in status_updates.items():
            if module in self.status_labels:
                # 更新指示器颜色
                color = color_map.get(status['status'], 'gray')
                self.status_labels[module]['indicator'].setStyleSheet(
                    f"background-color: {color}; border-radius: 10px;"
                )
                
                # 更新状态消息
                self.status_labels[module]['message'].setText(status['message'])

    def update_module_status(self, module: str, status: Dict[str, Any]) -> None:
        """更新单个模块状态（线程安全）"""
        if module not in self.module_status:
            return
            
        # 更新状态数据（线程安全）
        with QMutexLocker(self.status_lock):
            self.module_status[module].update({
                **status,
                'last_update': time.time()
            })
        
        # 通知UI更新
        self._status_updated.emit({module: self.module_status[module]})

    @Slot()
    def _restart_services(self) -> None:
        """重启所有服务（保持原有方法）"""
        reply = QMessageBox.question(
            self, "确认重启", "确定要重启所有服务吗？这将暂时中断数据处理。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 显示重启状态
            for module in self.status_labels:
                self.status_labels[module]['indicator'].setStyleSheet(
                    "background-color: #FFC107; border-radius: 10px;"
                )
                self.status_labels[module]['message'].setText("重启中...")
            
            # 在后台线程执行重启
            import threading
            threading.Thread(target=self._do_restart_services, daemon=True).start()

    def _do_restart_services(self) -> None:
        """执行服务重启（新增）"""
        try:
            # 调用主应用的重启方法
            result = self.main_app.restart_services()
            
            # 等待重启完成
            time.sleep(3)
            
            # 刷新状态
            self._fetch_all_status()
            
            # 显示结果
            if result:
                QMessageBox.information(self, "重启成功", "所有服务已成功重启")
            else:
                QMessageBox.warning(self, "重启失败", "部分服务重启失败，请查看日志")
                
        except Exception as e:
            self.logger.error(f"服务重启失败: {str(e)}")
            QMessageBox.warning(self, "重启失败", f"服务重启失败: {str(e)}")
    