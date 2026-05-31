import logging
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import time
from PySide6.QtCore import QTimer
from typing import Dict

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """性能监控器"""
    
    _global_alert_cooldown = {}
    
    def __init__(self, monitor_interval: int = 60000, is_test: bool = False, auto_start: bool = False):
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_metrics)
        self.monitor_interval = monitor_interval
        self.metrics_history = []
        self._max_history_size = 30  # 减少历史记录大小
        self._last_data_count = 0
        self._last_check_time = time.time()
        self.thresholds = {
            'cpu_usage': 90.0,
            'memory_usage': 92.0,
            'data_throughput': 800
        }
        if auto_start and not is_test:
            self.start_monitoring()
    
    def start_monitoring(self):
        """启动监控"""
        if psutil is None:
            logger.warning("psutil不可用，跳过性能监控启动")
            return
        self.monitor_timer.start(self.monitor_interval)
        logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitor_timer.stop()
        logger.info("性能监控已停止")
    
    def _collect_metrics(self):
        """收集性能指标"""
        try:
            metrics = {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'data_throughput': self._calculate_throughput(),
                'timestamp': time.time()
            }
            
            self.metrics_history.append(metrics)
            
            # 限制历史记录大小
            if len(self.metrics_history) > self._max_history_size:
                self.metrics_history = self.metrics_history[-self._max_history_size:]
            
            # 检查阈值
            self._check_thresholds(metrics)
            
        except Exception as e:
            logger.error(f"性能指标收集失败: {e}")
    
    def _calculate_throughput(self):
        """计算数据吞吐量"""
        current_time = time.time()
        elapsed = current_time - self._last_check_time
        if elapsed <= 0:
            return 0
        throughput = self._last_data_count / elapsed
        self._last_data_count = 0
        self._last_check_time = current_time
        return throughput

    def record_data_point(self, count: int = 1):
        """记录数据点"""
        self._last_data_count += count
    
    def _check_thresholds(self, metrics: Dict[str, float]):
        """检查阈值"""
        current_time = time.time()
        for key, value in metrics.items():
            if key in self.thresholds:
                if key == 'data_throughput' and value == 0:
                    continue
                if value > self.thresholds[key]:
                    last_alert = PerformanceMonitor._global_alert_cooldown.get(key, 0)
                    if current_time - last_alert > 60:
                        PerformanceMonitor._global_alert_cooldown[key] = current_time
                        logger.warning(f"性能警报: {key} 超过阈值 ({value} > {self.thresholds[key]})")
