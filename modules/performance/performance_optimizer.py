# ⚠️ DEPRECATED: 此组件已废弃
# 此文件保留仅为了向后兼容，将在未来版本中移除。
# 请使用 core.core.performance_monitor.PerformanceMonitor 作为统一的性能监控器。

import sys
import logging
import time
import gc
from datetime import datetime
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox

class PerformanceMonitor(QObject):
    """⚠️ DEPRECATED: 系统性能监控器，请使用 core.core.performance_monitor.PerformanceMonitor"""
    metrics_updated = Signal(dict)  # 发送性能指标更新信号
    alert_triggered = Signal(str, str)  # 发送警报(类型, 消息)
    
    def __init__(self, interval=1000):
        super().__init__()
        self.logger = logging.getLogger("PerformanceMonitor")
        self.interval = interval  # 监控间隔(毫秒)
        self.running = False
        self.metrics_history = {
            "cpu_usage": [],
            "memory_usage": [],
            "data_rate": [],
            "db_query_time": []
        }
        self.max_history = 100  # 最大历史记录数
        self.thresholds = {
            "high_cpu": 80.0,    # CPU使用率警报阈值(%)
            "high_memory": 80.0, # 内存使用率警报阈值(%)
            "slow_query": 500    # 慢查询警报阈值(毫秒)
        }
        
        # 初始化定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._collect_metrics)
        
    def start_monitoring(self):
        """开始性能监控"""
        self.running = True
        self.timer.start(self.interval)
        self.logger.info("性能监控已启动")
        
    def stop_monitoring(self):
        """停止性能监控"""
        self.running = False
        self.timer.stop()
        self.logger.info("性能监控已停止")
        
    def _collect_metrics(self):
        """收集系统性能指标"""
        if not self.running:
            return
            
        metrics = {}
        
        try:
            # 收集CPU使用率
            import psutil
            metrics["cpu_usage"] = psutil.cpu_percent(interval=None)
            
            # 收集内存使用率
            process = psutil.Process()
            mem_info = process.memory_percent()
            metrics["memory_usage"] = mem_info
            
            # 记录历史数据
            self._record_history(metrics)
            
            # 检查阈值并触发警报
            self._check_thresholds(metrics)
            
            # 发送指标更新信号
            self.metrics_updated.emit(metrics)
            
        except Exception as e:
            self.logger.error(f"性能指标收集失败: {str(e)}")
    
    def _record_history(self, metrics):
        """记录性能指标历史"""
        for key, value in metrics.items():
            if key in self.metrics_history:
                self.metrics_history[key].append((datetime.now(), value))
                # 限制历史记录数量
                if len(self.metrics_history[key]) > self.max_history:
                    self.metrics_history[key].pop(0)
    
    def _check_thresholds(self, metrics):
        """检查性能阈值"""
        if metrics.get("cpu_usage", 0) > self.thresholds["high_cpu"]:
            self.alert_triggered.emit(
                "high_cpu", 
                f"CPU使用率过高: {metrics['cpu_usage']:.1f}%"
            )
            
        if metrics.get("memory_usage", 0) > self.thresholds["high_memory"]:
            self.alert_triggered.emit(
                "high_memory", 
                f"内存使用率过高: {metrics['memory_usage']:.1f}%"
            )
    
    def record_query_time(self, query_time):
        """记录数据库查询时间"""
        self.metrics_history["db_query_time"].append((datetime.now(), query_time))
        if len(self.metrics_history["db_query_time"]) > self.max_history:
            self.metrics_history["db_query_time"].pop(0)
            
        # 检查慢查询
        if query_time > self.thresholds["slow_query"]:
            self.alert_triggered.emit(
                "slow_query", 
                f"数据库查询缓慢: {query_time}ms"
            )
    
    def record_data_rate(self, data_size):
        """记录数据传输速率"""
        self.metrics_history["data_rate"].append((datetime.now(), data_size))
        if len(self.metrics_history["data_rate"]) > self.max_history:
            self.metrics_history["data_rate"].pop(0)


class DataOptimizer(QObject):
    """数据优化器，负责数据处理和存储优化"""
    optimization_complete = Signal(str, float)  # 优化完成(类型, 耗时)
    status_updated = Signal(str)                # 状态更新
    
    def __init__(self, data_storage):
        super().__init__()
        self.logger = logging.getLogger("DataOptimizer")
        self.data_storage = data_storage
        self.running = False
        self.batch_size = 1000  # 批量处理大小
        self.compress_old_data = True  # 是否压缩旧数据
        self.purge_threshold_days = 30  # 数据保留阈值(天)
    
    def set_batch_size(self, size):
        """设置批量处理大小"""
        if size > 0 and size <= 10000:
            self.batch_size = size
            self.logger.info(f"批量处理大小已设置为: {size}")
    
    def optimize_database(self):
        """优化数据库性能"""
        if self.running:
            self.logger.warning("优化操作已在运行中")
            return
            
        self.running = True
        self.status_updated.emit("开始数据库优化...")
        
        try:
            start_time = time.time()
            
            # 执行数据库优化操作
            self._optimize_tables()
            
            # 压缩旧数据
            if self.compress_old_data:
                self.status_updated.emit("压缩旧数据...")
                self._compress_old_data()
            
            # 清理过期数据
            self.status_updated.emit("清理过期数据...")
            self._purge_old_data()
            
            # 优化索引
            self.status_updated.emit("优化索引...")
            self._optimize_indexes()
            
            elapsed = time.time() - start_time
            self.logger.info(f"数据库优化完成，耗时: {elapsed:.2f}秒")
            self.optimization_complete.emit("database", elapsed)
            self.status_updated.emit(f"数据库优化完成，耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            self.logger.error(f"数据库优化失败: {str(e)}")
            self.status_updated.emit(f"优化失败: {str(e)}")
        finally:
            self.running = False
    
    def _optimize_tables(self):
        """优化数据库表"""
        if hasattr(self.data_storage, 'mysql_handler') and self.data_storage.mysql_handler.connection:
            try:
                with self.data_storage.mysql_handler.connection.cursor() as cursor:
                    cursor.execute("OPTIMIZE TABLE driving_data, behavior_events")
                    self.data_storage.mysql_handler.connection.commit()
                    self.logger.info("数据库表优化完成")
            except Exception as e:
                self.logger.error(f"表优化失败: {str(e)}")
                self.data_storage.mysql_handler.connection.rollback()
    
    def _compress_old_data(self):
        """压缩旧数据"""
        # 实际实现应根据需求压缩历史数据
        # 例如将原始数据聚合为统计数据，保留详细数据的时间范围可配置
        pass
    
    def _purge_old_data(self):
        """清理过期数据"""
        if hasattr(self.data_storage, 'mysql_handler') and self.data_storage.mysql_handler.connection:
            try:
                import datetime as dt
                threshold_date = datetime.now() - dt.timedelta(days=self.purge_threshold_days)
                
                with self.data_storage.mysql_handler.connection.cursor() as cursor:
                    # 删除驾驶数据表过期数据
                    cursor.execute(
                        "DELETE FROM driving_data WHERE timestamp < %s",
                        (threshold_date,)
                    )
                    
                    # 删除行为事件表过期数据
                    cursor.execute(
                        "DELETE FROM behavior_events WHERE timestamp < %s",
                        (threshold_date,)
                    )
                    
                    self.data_storage.mysql_handler.connection.commit()
                    self.logger.info(f"已清理{self.purge_threshold_days}天前的过期数据")
                    
            except Exception as e:
                self.logger.error(f"清理过期数据失败: {str(e)}")
                self.data_storage.mysql_handler.connection.rollback()
    
    def _optimize_indexes(self):
        """优化数据库索引"""
        # 实际实现应分析并优化索引使用情况
        pass
    
    def optimize_memory_usage(self):
        """优化内存使用"""
        start_time = time.time()
        self.status_updated.emit("开始内存优化...")
        
        # 强制垃圾回收
        collected = gc.collect()
        self.logger.info(f"垃圾回收完成，回收对象: {collected}个")
        
        # 通知其他组件释放不必要的资源
        self.status_updated.emit("通知组件释放资源...")
        
        elapsed = time.time() - start_time
        self.optimization_complete.emit("memory", elapsed)
        self.status_updated.emit(f"内存优化完成，耗时: {elapsed:.2f}秒")


class PerformanceOptimizationWidget(QWidget):
    """性能优化UI组件"""
    start_optimization = Signal(str)  # 开始优化(类型)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("PerformanceOptimizationWidget")
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建性能监控区域
        monitor_group = QGroupBox("系统性能监控")
        monitor_layout = QFormLayout()
        
        # 性能指标显示
        self.cpu_label = QLabel("0%")
        self.memory_label = QLabel("0%")
        self.data_rate_label = QLabel("0 KB/s")
        self.query_time_label = QLabel("0 ms")
        
        monitor_layout.addRow("CPU使用率:", self.cpu_label)
        monitor_layout.addRow("内存使用率:", self.memory_label)
        monitor_layout.addRow("数据传输率:", self.data_rate_label)
        monitor_layout.addRow("平均查询时间:", self.query_time_label)
        
        monitor_group.setLayout(monitor_layout)
        
        # 创建性能警报区域
        alerts_group = QGroupBox("性能警报")
        alerts_layout = QVBoxLayout()
        
        self.alerts_table = QTableWidget(0, 3)
        self.alerts_table.setHorizontalHeaderLabels(["时间", "类型", "消息"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        alerts_layout.addWidget(self.alerts_table)
        alerts_group.setLayout(alerts_layout)
        
        # 创建优化控制区域
        optimization_group = QGroupBox("性能优化")
        optimization_layout = QVBoxLayout()
        
        # 优化选项
        options_layout = QFormLayout()
        
        self.batch_size_input = QSpinBox()
        self.batch_size_input.setRange(100, 10000)
        self.batch_size_input.setValue(1000)
        self.batch_size_input.setSuffix(" 条/批")
        
        self.purge_threshold_input = QSpinBox()
        self.purge_threshold_input.setRange(1, 365)
        self.purge_threshold_input.setValue(30)
        self.purge_threshold_input.setSuffix(" 天")
        
        self.compress_data_checkbox = QCheckBox("自动压缩旧数据")
        self.compress_data_checkbox.setChecked(True)
        
        options_layout.addRow("批量处理大小:", self.batch_size_input)
        options_layout.addRow("数据保留期限:", self.purge_threshold_input)
        options_layout.addRow(self.compress_data_checkbox)
        
        # 优化按钮
        buttons_layout = QHBoxLayout()
        
        self.db_optimize_btn = QPushButton("优化数据库")
        self.memory_optimize_btn = QPushButton("优化内存")
        self.full_optimize_btn = QPushButton("全面优化")
        
        self.db_optimize_btn.clicked.connect(lambda: self.start_optimization.emit("database"))
        self.memory_optimize_btn.clicked.connect(lambda: self.start_optimization.emit("memory"))
        self.full_optimize_btn.clicked.connect(lambda: self.start_optimization.emit("full"))
        
        buttons_layout.addWidget(self.db_optimize_btn)
        buttons_layout.addWidget(self.memory_optimize_btn)
        buttons_layout.addWidget(self.full_optimize_btn)
        
        # 优化状态
        self.optimization_status = QLabel("就绪")
        self.optimization_progress = QProgressBar()
        self.optimization_progress.setRange(0, 100)
        self.optimization_progress.setValue(0)
        self.optimization_progress.setVisible(False)
        
        # 添加到优化布局
        optimization_layout.addLayout(options_layout)
        optimization_layout.addLayout(buttons_layout)
        optimization_layout.addWidget(QLabel("优化状态:"))
        optimization_layout.addWidget(self.optimization_status)
        optimization_layout.addWidget(self.optimization_progress)
        
        optimization_group.setLayout(optimization_layout)
        
        # 添加到主布局
        main_layout.addWidget(monitor_group)
        main_layout.addWidget(alerts_group)
        main_layout.addWidget(optimization_group)
        
        # 设置初始大小
        self.setMinimumWidth(600)
    
    def update_performance_metrics(self, metrics):
        """更新性能指标显示"""
        if "cpu_usage" in metrics:
            self.cpu_label.setText(f"{metrics['cpu_usage']:.1f}%")
            # 根据CPU使用率设置颜色
            if metrics["cpu_usage"] > 80:
                self.cpu_label.setStyleSheet("color: red; font-weight: bold;")
            elif metrics["cpu_usage"] > 50:
                self.cpu_label.setStyleSheet("color: orange;")
            else:
                self.cpu_label.setStyleSheet("")
                
        if "memory_usage" in metrics:
            self.memory_label.setText(f"{metrics['memory_usage']:.1f}%")
            # 根据内存使用率设置颜色
            if metrics["memory_usage"] > 80:
                self.memory_label.setStyleSheet("color: red; font-weight: bold;")
            elif metrics["memory_usage"] > 50:
                self.memory_label.setStyleSheet("color: orange;")
            else:
                self.memory_label.setStyleSheet("")
    
    def add_alert(self, alert_type, message):
        """添加性能警报"""
        row = self.alerts_table.rowCount()
        self.alerts_table.insertRow(row)
        
        # 时间
        time_item = QTableWidgetItem(datetime.now().strftime("%H:%M:%S"))
        time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
        
        # 类型
        type_item = QTableWidgetItem(alert_type.replace("_", " ").title())
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        
        # 消息
        message_item = QTableWidgetItem(message)
        message_item.setFlags(message_item.flags() & ~Qt.ItemIsEditable)
        
        # 设置行颜色
        if alert_type in ["high_cpu", "high_memory", "slow_query"]:
            for item in [time_item, type_item, message_item]:
                item.setBackground(QColor(255, 240, 240))
        
        self.alerts_table.setItem(row, 0, time_item)
        self.alerts_table.setItem(row, 1, type_item)
        self.alerts_table.setItem(row, 2, message_item)
        
        # 保持最新的在上面
        self.alerts_table.scrollToTop()
    
    def update_optimization_status(self, message, progress=None):
        """更新优化状态"""
        self.optimization_status.setText(message)
        
        if progress is not None:
            self.optimization_progress.setVisible(True)
            self.optimization_progress.setValue(progress)
        else:
            self.optimization_progress.setVisible(False)
    
    def get_optimization_settings(self):
        """获取优化设置"""
        return {
            "batch_size": self.batch_size_input.value(),
            "purge_threshold_days": self.purge_threshold_input.value(),
            "compress_old_data": self.compress_data_checkbox.isChecked()
        }


class OptimizationController(QObject):
    """优化控制器，协调性能监控和优化操作"""
    status_updated = Signal(str, int)  # 状态消息, 进度(0-100, None表示隐藏)
    
    def __init__(self, data_storage):
        super().__init__()
        self.logger = logging.getLogger("OptimizationController")
        
        # 创建性能监控器
        self.performance_monitor = PerformanceMonitor()
        self.performance_monitor.metrics_updated.connect(self._on_metrics_updated)
        self.performance_monitor.alert_triggered.connect(self._on_alert_triggered)
        
        # 创建数据优化器
        self.data_optimizer = DataOptimizer(data_storage)
        self.data_optimizer.status_updated.connect(self._on_optimization_status)
        self.data_optimizer.optimization_complete.connect(self._on_optimization_complete)
        
        # 创建UI组件
        self.optimization_widget = PerformanceOptimizationWidget()
        self.optimization_widget.start_optimization.connect(self._start_optimization)
        
        # 自动优化定时器
        self.auto_optimize_timer = QTimer()
        self.auto_optimize_timer.timeout.connect(self._auto_optimize)
        self.auto_optimize_enabled = False
        self.auto_optimize_interval = 8 * 3600 * 1000  # 8小时(毫秒)
    
    def start_monitoring(self):
        """开始性能监控"""
        self.performance_monitor.start_monitoring()
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.performance_monitor.stop_monitoring()
    
    def set_auto_optimization(self, enabled, interval=None):
        """设置自动优化"""
        self.auto_optimize_enabled = enabled
        
        if interval:
            self.auto_optimize_interval = interval
            
        if enabled:
            self.auto_optimize_timer.start(self.auto_optimize_interval)
            self.logger.info(f"自动优化已启用，间隔: {self.auto_optimize_interval/3600000:.1f}小时")
        else:
            self.auto_optimize_timer.stop()
            self.logger.info("自动优化已禁用")
    
    def _auto_optimize(self):
        """执行自动优化"""
        self.logger.info("执行自动优化...")
        self._start_optimization("full")
    
    def _start_optimization(self, optimization_type):
        """开始优化操作"""
        # 获取优化设置
        settings = self.optimization_widget.get_optimization_settings()
        self.data_optimizer.set_batch_size(settings["batch_size"])
        self.data_optimizer.purge_threshold_days = settings["purge_threshold_days"]
        self.data_optimizer.compress_old_data = settings["compress_old_data"]
        
        # 执行优化
        if optimization_type in ["database", "full"]:
            self.data_optimizer.optimize_database()
            
        if optimization_type in ["memory", "full"] and not self.data_optimizer.running:
            # 如果数据库优化在运行，等待它完成
            if optimization_type == "full":
                QTimer.singleShot(1000, self.data_optimizer.optimize_memory_usage)
            else:
                self.data_optimizer.optimize_memory_usage()
    
    @Slot(dict)
    def _on_metrics_updated(self, metrics):
        """处理性能指标更新"""
        self.optimization_widget.update_performance_metrics(metrics)
    
    @Slot(str, str)
    def _on_alert_triggered(self, alert_type, message):
        """处理性能警报"""
        self.optimization_widget.add_alert(alert_type, message)
        self.logger.warning(f"性能警报: {message}")
    
    @Slot(str)
    def _on_optimization_status(self, message):
        """处理优化状态更新"""
        self.status_updated.emit(message, None)
        self.optimization_widget.update_optimization_status(message)
    
    @Slot(str, float)
    def _on_optimization_complete(self, optimization_type, elapsed):
        """处理优化完成事件"""
        self.logger.info(f"{optimization_type}优化完成，耗时: {elapsed:.2f}秒")
    
    def record_query_time(self, query_time):
        """记录数据库查询时间"""
        self.performance_monitor.record_query_time(query_time)
    
    def record_data_rate(self, data_size):
        """记录数据传输速率"""
        self.performance_monitor.record_data_rate(data_size)
    
    def get_widget(self):
        """获取UI组件"""
        return self.optimization_widget
