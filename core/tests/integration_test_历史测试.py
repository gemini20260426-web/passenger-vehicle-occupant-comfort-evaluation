import unittest
import time
from typing import Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.core.unified_data_flow_manager import UnifiedDataFlowManager
from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine
from core.core.performance_monitor import PerformanceMonitor
from core.core.memory_optimizer import MemoryOptimizer
from PySide6.QtCore import QEventLoop, QCoreApplication

class IntegrationTest(unittest.TestCase):
    """系统集成测试"""
    app = QCoreApplication([])  # 类级单例

    def setUp(self):
        self.loop = QEventLoop()
        self.loop.processEvents()  # 模拟事件循环
        self.manager = UnifiedDataFlowManager()
        self.manager.performance_monitor = PerformanceMonitor(is_test=True)  # 禁用定时器
        self.manager.memory_optimizer = MemoryOptimizer(is_test=True)  # 禁用定时器
        self.sync_engine = MultiSourceSyncEngine()
        self.manager.register_core_engine('sync_engine', self.sync_engine)

    def test_data_sync_integration(self):
        """测试数据同步集成"""
        # 准备测试数据
        data_streams = {
            'source1': {'data': [1, 2, 3], 'timestamp': time.time()},
            'source2': {'data': [4, 5, 6], 'timestamp': time.time()}
        }
        
        # 添加数据源到引擎
        self.sync_engine.add_data_source('source1', {'type': 'test'})
        self.sync_engine.add_data_source('source2', {'type': 'test'})
        
        # 启动同步
        result = self.sync_engine.start_sync(['source1', 'source2'])
        self.assertTrue(result)
        
        # 等待一段时间以模拟同步
        time.sleep(1)
        
        # 停止同步
        result = self.sync_engine.stop_sync()
        self.assertTrue(result)

    def test_performance_monitor(self):
        """测试性能监控"""
        # 手动触发一次性能数据收集
        self.manager.performance_monitor._collect_metrics()
        # 检查是否有性能数据
        self.assertTrue(len(self.manager.performance_monitor.metrics_history) > 0)

    def test_ui_action_handling(self):
        """测试UI动作处理"""
        # 准备测试数据
        action = "test_action"
        data = {"key": "value"}
        
        # 测试UI动作处理 - 传递正确的参数
        # 由于handle_ui_action调用的是optimize_response，我们需要直接调用ui_responder
        result = self.manager.ui_responder.handle_user_action(action, data)
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))  # 预期在测试环境中返回成功为True

if __name__ == '__main__':
    unittest.main()
