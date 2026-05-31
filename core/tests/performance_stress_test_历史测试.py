import logging
import time
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.core.unified_data_flow_manager import UnifiedDataFlowManager
from core.core.performance_monitor import PerformanceMonitor
from core.core.memory_optimizer import MemoryOptimizer
from PySide6.QtCore import QEventLoop, QCoreApplication
from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine

logger = logging.getLogger(__name__)

class PerformanceStressTest:
    """性能压力测试"""
    
    app = QCoreApplication([])  # 类级单例

    def __init__(self, num_threads: int = 10, duration: int = 30):
        self.loop = QEventLoop()
        self.loop.processEvents()  # Simulate event loop
        self.manager = UnifiedDataFlowManager()
        self.manager.performance_monitor = PerformanceMonitor(is_test=True) # Disable timers
        self.manager.memory_optimizer = MemoryOptimizer(is_test=True) # Disable timers
        self.sync_engine = MultiSourceSyncEngine()
        self.manager.register_core_engine('sync_engine', self.sync_engine)
        self.num_threads = num_threads
        self.duration = duration  # seconds
        
        # 模拟右侧模块初始化
        self._init_mock_right_panel()
    
    def run_test(self):
        """运行压力测试"""
        logger.info(f"启动压力测试: {self.num_threads} 线程, 持续 {self.duration} 秒")
        
        threads = []
        for i in range(self.num_threads):
            t = threading.Thread(target=self._simulate_load, args=(i,))
            threads.append(t)
            t.start()
        
        time.sleep(self.duration)
        
        for t in threads:
            t.join()
        
        logger.info("压力测试完成")
        self._report_metrics()
    
    def _simulate_load(self, thread_id: int):
        """模拟负载"""
        start_time = time.time()
        while time.time() - start_time < self.duration:
            try:
                # 模拟UI动作
                self.manager.ui_responder.handle_user_action('simulate_action', {'thread': thread_id})
                # 模拟数据处理
                data_streams = {
                    f'source_{thread_id}_{i}': {'data': [1, 2, 3], 'timestamp': time.time()}
                    for i in range(2)
                }
                for source_id, data in data_streams.items():
                    self.sync_engine.add_data_source(source_id, {'type': 'test'})
                self.sync_engine.start_sync(list(data_streams.keys()))
                time.sleep(0.1)  # 短暂等待
                self.sync_engine.stop_sync()
                time.sleep(0.01)  # 模拟高频操作
            except Exception as e:
                logger.error(f"线程 {thread_id} 负载模拟失败: {e}")

    def _init_mock_right_panel(self):
        """初始化模拟的右侧模块"""
        try:
            from unittest.mock import MagicMock
            # 创建模拟的右侧模块
            self.mock_right_panel = MagicMock()
            self.mock_right_panel.sources_table = MagicMock()
            self.mock_right_panel.sources_table.rowCount.return_value = 5
            self.mock_right_panel.sources_table.item.side_effect = lambda row, col: MagicMock(text=lambda: f"状态 {row}" if col == 3 else f"数据源 {row}")
            # 注册到管理器
            self.manager.register_right_panel(self.mock_right_panel)
            logger.info("✅ 模拟右侧模块初始化成功")
        except Exception as e:
            logger.error(f"❌ 模拟右侧模块初始化失败: {e}")

    def _report_metrics(self):
        """报告性能指标"""
        try:
            # 手动触发一次性能数据收集
            self.manager.performance_monitor._collect_metrics()
            # 获取最新的性能指标
            if self.manager.performance_monitor.metrics_history:
                metrics = self.manager.performance_monitor.metrics_history[-1]  # 最后一次指标
                logger.info(f"最终性能指标: CPU使用率: {metrics.get('cpu_usage', 0):.1f}%, "
                           f"内存使用率: {metrics.get('memory_usage', 0):.1f}%, "
                           f"数据吞吐量: {metrics.get('data_throughput', 0):.1f}")
            else:
                logger.warning("没有可用的性能指标数据")
        except Exception as e:
            logger.error(f"报告性能指标失败: {e}")

if __name__ == '__main__':
    test = PerformanceStressTest()
    test.run_test()
