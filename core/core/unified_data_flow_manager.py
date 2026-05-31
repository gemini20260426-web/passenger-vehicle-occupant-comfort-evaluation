# ============================================================
# 历史版本备注: py
# 优化日期: 2026-05-03
# 优化内容: 集成完整 CommunicationBus, 启用信号连接
# ============================================================
import logging
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import asyncio
from collections import deque
from PySide6.QtCore import QObject, Signal, QTimer
from typing import Dict, Any, overload

from .unified_error_handler import UnifiedErrorHandler
from .performance_monitor import PerformanceMonitor
from .memory_optimizer import MemoryOptimizer
from .intelligent_ui_responder import IntelligentUIResponder
from .ui_response_optimizer import UIResponseOptimizer
from .state_synchronizer import StateSynchronizer
from .communication_bus import CommunicationBus

logger = logging.getLogger(__name__)

class UnifiedDataFlowManager:
    """统一数据流管理器 - 系统核心协调器"""
    
    def __init__(self):
        # 面板管理
        self.left_panels = {}
        self.right_panel = None
        
        # 核心引擎管理
        self.sync_engine = None
        self.analysis_engine = None
        self.processing_engine = None
        
        # 通信管理
        self.communication_bus = CommunicationBus()
        print("CommunicationBus attributes in manager:", dir(self.communication_bus))  # 调试
        # 初始化状态同步器（传递面板引用）
        self.state_synchronizer = StateSynchronizer(self.left_panels, self.right_panel)
        
        # 集成错误处理、性能监控和内存优化
        self.error_handler = UnifiedErrorHandler()
        self.performance_monitor = PerformanceMonitor(auto_start=False)  # 禁用自动启动
        self.memory_optimizer = MemoryOptimizer(auto_start=False)  # 禁用自动启动
        
        # UI交互优化
        self.ui_responder = IntelligentUIResponder()
        self.ui_optimizer = UIResponseOptimizer()
        
        # 启动监控 - 只启动核心监控器
        # self.performance_monitor.start_monitoring()  # 已禁用，由上层统一管理
        # self.memory_optimizer.start_optimizing()  # 已禁用，由上层统一管理
        
        # 初始化
        self._setup_communication_signals()
        # 延迟初始化StateSynchronizer，确保left_panels和right_panel已被注册
        # self.state_synchronizer = StateSynchronizer(self.left_panels, self.right_panel)
        self._setup_error_handling()
        self._setup_performance_monitoring()
    
    def register_left_panel(self, panel_name: str, panel_instance):
        """注册左侧面板"""
        self.left_panels[panel_name] = panel_instance
        self._setup_panel_signals(panel_name, panel_instance)
    
    def register_right_panel(self, panel_instance):
        """注册右侧配置中心"""
        self.right_panel = panel_instance
        self._setup_right_panel_signals(panel_instance)
    
    def register_core_engine(self, engine_name: str, engine_instance):
        """注册核心引擎"""
        if engine_name == 'sync_engine':
            self.sync_engine = engine_instance
            self._connect_engine_signals(engine_instance)
        elif engine_name == 'analysis_engine':
            self.analysis_engine = engine_instance
            self._connect_engine_signals(engine_instance)
        elif engine_name == 'processing_engine':
            self.processing_engine = engine_instance
            self._connect_engine_signals(engine_instance)
    
    def _connect_engine_signals(self, engine_instance):
        """连接引擎信号到通信总线"""
        # 假设引擎有 status_changed 信号
        if hasattr(engine_instance, 'status_changed'):
            engine_instance.status_changed.connect(self.communication_bus.publish_status_change)
        # 添加更多信号连接根据需要
    
    def _setup_communication_signals(self):
        """设置通信信号"""
        logger.info("正在设置通信信号连接...")
        try:
            data_source_signal = getattr(self.communication_bus, 'data_source_updated', None)
            if data_source_signal:
                data_source_signal.connect(self._handle_data_source_update)
                logger.info("已连接 data_source_updated 信号")
            else:
                logger.warning("未找到 data_source_updated 信号")

            sync_status_signal = getattr(self.communication_bus, 'sync_status_changed', None)
            if sync_status_signal:
                sync_status_signal.connect(self._handle_sync_status_change)
                logger.info("已连接 sync_status_changed 信号")
            else:
                logger.warning("未找到 sync_status_changed 信号")

            analysis_result_signal = getattr(self.communication_bus, 'analysis_result_ready', None)
            if analysis_result_signal:
                analysis_result_signal.connect(self._handle_analysis_result)
                logger.info("已连接 analysis_result_ready 信号")
            else:
                logger.warning("未找到 analysis_result_ready 信号")

            error_signal = getattr(self.communication_bus, 'error_occurred', None)
            if error_signal:
                error_signal.connect(self._handle_error)
                logger.info("已连接 error_occurred 信号")
            else:
                logger.warning("未找到 error_occurred 信号")

            performance_signal = getattr(self.communication_bus, 'performance_updated', None)
            if performance_signal:
                performance_signal.connect(self._handle_performance_update)
                logger.info("已连接 performance_updated 信号")
            else:
                logger.warning("未找到 performance_updated 信号")
        except Exception as e:
            logger.error(f"设置通信信号失败: {e}")
    
    def _handle_data_source_update(self, source_id: str, data: dict) -> None:
        """处理数据源更新"""
        logger.info(f"数据源更新: {source_id}")
        # 更新状态同步器或面板
    
    def _handle_sync_status_change(self, status: str, details: dict) -> None:
        """处理同步状态变化"""
        logger.info(f"同步状态变化: {status}")
    
    def _handle_analysis_result(self, result_id: str, result: dict) -> None:
        """处理分析结果"""
        logger.info(f"分析结果就绪: {result_id}")
    
    def _handle_error(self, error_type: str, details: dict) -> None:
        """处理错误"""
        self.error_handler.handle_error(error_type, details)
    
    @overload
    def _handle_performance_update(self, metrics: dict) -> None:
        logger.info(f"性能更新: {metrics}")
    
    def _setup_error_handling(self):
        """设置错误处理"""
        pass  # 实现错误处理逻辑
    
    def _setup_performance_monitoring(self):
        """设置性能监控"""
        pass  # 实现性能监控逻辑
    
    def _setup_panel_signals(self, panel_name, panel_instance):
        """设置面板信号"""
        pass  # 实现面板信号连接
    
    def _setup_right_panel_signals(self, panel_instance):
        """设置右侧面板信号"""
        pass  # 实现右侧面板信号连接

    def handle_ui_action(self, action: str, data: Dict[str, Any]):
        """处理UI动作，通过响应器和优化器"""
        optimized_func = self.ui_optimizer.optimize_response(self.ui_responder.handle_user_action)
        return optimized_func(action, data)

    def get_data_sources(self):
        # 从配置或数据库获取真实数据源
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager(config_dir='config/').get_config('data_sources')
            return config or {}  # 返回配置中的数据源字典
        except Exception as e:
            logger.error(f"获取数据源失败: {e}")
            return {}  # 空字典作为 fallback
