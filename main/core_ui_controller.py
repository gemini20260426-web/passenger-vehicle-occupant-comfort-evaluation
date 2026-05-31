#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 状态: 【当前使用 ACTIVE】- 主控制器
# 调用链: main.py -> 本文件 -> modules/ui/core_ui_refactored/
# ============================================================
"""
Core UI Controller - 重构版本
主控制器，负责业务逻辑和协调，与UI主窗口建立水平关系

作者: Core System Technologies
版本: 2.0.0
重构日期: 2025-08-15
"""

import sys
import os
import logging
import time
import traceback
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, 
        QHBoxLayout, QLabel, QPushButton, QFrame, QSplitter,
        QMessageBox, QStatusBar, QMenuBar, QToolBar
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
    from PySide6.QtGui import QAction, QIcon, QFont, QPalette, QColor
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请安装 PySide6: pip install PySide6")
    sys.exit(1)

# 导入日志配置模块
try:
    from config.logging_setup import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class CoreUIController(QObject):
    """
    重构后的主控制器
    - 不再嵌套UI窗口，而是建立水平关系
    - 通过信号槽与UI主窗口通信
    - 负责业务逻辑、数据协调和系统管理
    - 包含完整的基础模块初始化
    """
    
    # 定义信号
    ui_ready = Signal()                    # UI准备就绪信号
    data_source_connected = Signal(str)    # 数据源连接信号
    analysis_requested = Signal(dict)      # 分析请求信号
    system_status_changed = Signal(str)    # 系统状态变化信号
    sync_started = Signal(dict)            # 同步开始信号
    sync_stopped = Signal()                # 同步停止信号
    performance_updated = Signal(dict)     # 性能更新信号
    
    # 多源异构数据同步相关信号
    multi_source_sync_started = Signal(dict)      # 多源同步开始信号
    multi_source_sync_stopped = Signal()          # 多源同步停止信号
    multi_source_sync_paused = Signal()           # 多源同步暂停信号
    multi_source_sync_resumed = Signal()          # 多源同步恢复信号
    multi_source_sync_status_updated = Signal(dict)  # 多源同步状态更新信号
    multi_source_sync_error = Signal(str, str)    # 多源同步错误信号 (错误类型, 错误信息)
    
    # 座椅评测相关信号
    seat_evaluation_started = Signal(dict)        # 座椅评测开始信号
    seat_evaluation_completed = Signal(dict)      # 座椅评测完成信号
    seat_evaluation_metric = Signal(dict)         # 座椅评测指标信号
    comparison_started = Signal(dict)             # 对照分析开始信号
    comparison_completed = Signal(dict)           # 对照分析完成信号
    comparison_metric = Signal(dict)              # 对照分析指标信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_logger()

        self.logger.info("开始初始化控制器组件")
        self.ui_main_window = None
        
        self.config_manager = None
        self.data_storage = None
        self.db_handler = None
        self.mqtt_manager = None
        self.mqtt_config_manager = None
        self.serial_manager = None
        self.basic_analyzer = None
        self.performance_manager = None
        self.data_source_manager = None
        self.data_bridge = None
        
        self.multi_source_sync_engine = None
        self.multi_source_sync_config_manager = None
        self.multi_source_sync_performance_monitor = None
        self.multi_source_sync_anomaly_detector = None
        
        # 座椅评测相关组件
        self.seat_evaluation_engine = None
        self.comparative_evaluation_engine = None
        self.multi_channel_data_synchronizer = None
        self.behavior_event_dispatcher = None
        
        self.system_status = "初始化中"
        
        self._init_config_manager()
        self._init_basic_analyzer()
        self._init_connections()
        
        self._init_timers = []
        
        logger.info("CoreUIController 核心初始化完成，后台初始化已启动")
        
        QTimer.singleShot(100, self._init_remaining_components_async)
    
    def _init_remaining_components_async(self):
        """异步初始化剩余组件（不阻塞UI，单步失败不影响后续）"""
        self.logger.info("开始异步初始化剩余组件...")
        self._async_init_step('data_storage', self._init_data_storage, 150, self._init_mqtt_components_async)

    def _init_mqtt_components_async(self):
        self.logger.info("开始异步初始化MQTT组件...")
        self._async_init_step('mqtt_config', self._init_mqtt_config_manager, 150, self._init_serial_and_performance_async)

    def _init_serial_and_performance_async(self):
        self.logger.info("开始异步初始化串口和性能组件...")
        self._async_init_step('serial', self._init_serial_manager, 0, None)
        self._async_init_step('performance', self._init_performance_manager, 150, self._init_data_bridge_async)

    def _init_data_bridge_async(self):
        self.logger.info("开始异步初始化数据桥接器...")
        self._async_init_step('data_bridge', self._init_data_bridge, 150, self._init_multi_source_sync_async)

    def _init_multi_source_sync_async(self):
        self.logger.info("开始异步初始化多源同步组件...")
        self._async_init_step('multi_source_sync', self._init_multi_source_sync_components, 150, self._init_seat_evaluation_async)

    def _init_seat_evaluation_async(self):
        self.logger.info("开始异步初始化座椅评测组件...")
        try:
            self._init_seat_evaluation_components()
        except Exception as e:
            self.logger.error(f"异步初始化座椅评测组件失败: {e}")
        self._register_services()
        self.logger.info("所有组件异步初始化完成")
        self.system_status = "就绪"

    def _async_init_step(self, name: str, init_func, next_delay_ms: int, next_func):
        """执行单个异步初始化步骤，失败时记录错误并继续下一步"""
        try:
            from PySide6.QtWidgets import QApplication
            for _ in range(3):
                QApplication.processEvents()
            init_func()
        except Exception as e:
            self.logger.error(f"异步初始化 [{name}] 失败: {e}")
        if next_func and next_delay_ms > 0:
            QTimer.singleShot(next_delay_ms, next_func)
        elif next_func:
            next_func()
    
    def _init_seat_evaluation_components(self):
        """初始化座椅评测组件"""
        try:
            # 初始化座椅评测引擎 (V2版本 - 多通道支持)
            from core.core.seat_evaluation.engine_v2 import MultiChannelSeatEvaluationEngine
            self.seat_evaluation_engine = MultiChannelSeatEvaluationEngine(
                config_manager=self.config_manager,
                data_storage=self.data_storage
            )
            # 连接评测引擎信号
            self.seat_evaluation_engine.evaluation_started.connect(self._on_seat_evaluation_started)
            self.seat_evaluation_engine.evaluation_completed.connect(self._on_seat_evaluation_completed)
            self.seat_evaluation_engine.metric_calculated.connect(self._on_seat_evaluation_metric)
            self.seat_evaluation_engine.location_result_ready.connect(self._on_location_result_ready)
            logger.info("座椅评测引擎(V2)初始化成功")
            
            # 初始化对照分析引擎 (V2版本 - 多通道支持)
            from core.core.seat_evaluation.comparative_engine_v2 import MultiChannelComparativeEngine
            self.comparative_evaluation_engine = MultiChannelComparativeEngine(
                config_manager=self.config_manager,
                data_storage=self.data_storage
            )
            # 连接对照分析引擎信号
            self.comparative_evaluation_engine.comparison_started.connect(self._on_comparison_started)
            self.comparative_evaluation_engine.comparison_completed.connect(self._on_comparison_completed)
            self.comparative_evaluation_engine.metric_comparison_updated.connect(self._on_comparison_metric)
            self.comparative_evaluation_engine.location_comparison_ready.connect(self._on_location_comparison_ready)
            logger.info("对照分析引擎(V2)初始化成功")
            
            # 初始化多通道数据同步器
            from core.core.seat_evaluation.data_sync import MultiChannelDataSynchronizer
            self.multi_channel_data_synchronizer = MultiChannelDataSynchronizer()
            logger.info("多通道数据同步器初始化成功")
            
            # 初始化行为事件分发器
            from core.core.analysis.BehaviorAnalyzer import BehaviorEventDispatcher
            self.behavior_event_dispatcher = BehaviorEventDispatcher(analyzer=self.basic_analyzer)
            # 连接事件分发器信号
            self.behavior_event_dispatcher.evaluation_triggered.connect(self._on_evaluation_triggered)
            logger.info("行为事件分发器初始化成功")
            
            # 设置评测指标和位置
            from core.core.seat_evaluation.metadata_registry import INDICATOR_DEFINITIONS
            from core.core.seat_evaluation.imu_location_config import LOCATION_IDS
            all_metrics = list(INDICATOR_DEFINITIONS.keys())
            self.behavior_event_dispatcher.set_evaluation_metrics(all_metrics)
            self.behavior_event_dispatcher.set_evaluation_locations(LOCATION_IDS)

            # 将座椅评测引擎注入到DataBridge（实现Pipeline→座椅评测数据桥接）
            if self.data_bridge and self.seat_evaluation_engine:
                self.data_bridge.set_seat_evaluation_engine(self.seat_evaluation_engine)
                logger.info("座椅评测引擎已注入到DataBridge")
            
        except Exception as e:
            logger.error(f"座椅评测组件初始化失败: {e}")
            self.seat_evaluation_engine = None
            self.comparative_evaluation_engine = None
            self.multi_channel_data_synchronizer = None
            self.behavior_event_dispatcher = None
    
    # 座椅评测相关回调函数
    def _on_seat_evaluation_started(self, trigger: dict) -> None:
        """座椅评测开始回调"""
        self.seat_evaluation_started.emit(trigger)
        logger.info(f"座椅评测开始: {trigger.get('event_type', '')}")
    
    def _on_seat_evaluation_completed(self, result: dict) -> None:
        """座椅评测完成回调"""
        self.seat_evaluation_completed.emit(result)
        logger.info(f"座椅评测完成: {result.get('overall_score', 0)}")
    
    def _on_seat_evaluation_metric(self, metric: dict) -> None:
        """座椅评测指标回调"""
        self.seat_evaluation_metric.emit(metric)
    
    def _on_location_result_ready(self, location_result: dict) -> None:
        """位置评测结果回调"""
        logger.debug(f"位置评测结果: {location_result.get('location_id', '')}")
    
    def _on_location_comparison_ready(self, location_comparison: dict) -> None:
        """位置对照结果回调"""
        logger.debug(f"位置对照结果: {location_comparison.get('location_id', '')}")
    
    def _on_comparison_started(self, trigger: dict) -> None:
        """对照分析开始回调"""
        self.comparison_started.emit(trigger)
        logger.info(f"对照分析开始: {trigger.get('comparison_id', '')}")
    
    def _on_comparison_completed(self, result: dict) -> None:
        """对照分析完成回调"""
        self.comparison_completed.emit(result)
        logger.info(f"对照分析完成: {result.get('overall_score', {}).get('improvement', 0)}")
    
    def _on_comparison_metric(self, metric: dict) -> None:
        """对照分析指标回调"""
        self.comparison_metric.emit(metric)
    
    def _on_evaluation_triggered(self, trigger: dict) -> None:
        """评测触发回调"""
        group_tag = trigger.get('group_tag', 'experimental')
        
        if group_tag == 'both' and self.comparative_evaluation_engine:
            # 同时评测两组
            self.comparative_evaluation_engine.compare_groups(trigger)
        elif self.seat_evaluation_engine:
            # 只评测指定组
            self.seat_evaluation_engine.evaluate_by_event(trigger)
    
    def _init_controller(self):
        """初始化控制器组件"""
        try:
            logger.info("开始初始化控制器组件")
            
            # 初始化配置管理器
            self._init_config_manager()
            
            # 初始化数据存储
            self._init_data_storage()
            
            # 初始化MQTT配置管理器
            self._init_mqtt_config_manager()
            
            # 初始化MQTT管理器
            self._init_mqtt_manager()
            
            # 初始化串口管理器
            self._init_serial_manager()
            
            # 初始化基础分析器
            self._init_basic_analyzer()
            
            # 初始化性能管理器
            self._init_performance_manager()
            
            # 初始化数据源管理器
            self._init_data_source_manager()
            
            # 初始化多源异构数据同步组件
            self._init_multi_source_sync_components()
            
            # 初始化数据桥接器
            self._init_data_bridge()

            # 注册所有核心服务到 ServiceLocator
            self._register_services()

            logger.info("控制器组件初始化完成")
        except Exception as e:
            logger.error(f"控制器组件初始化失败: {e}")
            logger.exception("详细错误信息:")
            self.system_status = "初始化失败"
    
    def _init_config_manager(self):
        """初始化配置管理器"""
        try:
            from config.config_manager import ConfigManager
            # 获取项目根目录下的config目录
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
            self.config_manager = ConfigManager.instance(config_dir)
            logger.info("配置管理器初始化成功")
        except Exception as e:
            logger.error(f"配置管理器初始化失败: {e}")
            self.config_manager = None
    
    def _init_data_storage(self):
        """初始化数据存储"""
        try:
            from core.core.storage.data_storage import DataStorage
            from core.core.storage.db_handler import MySQLHandler
            
            # 初始化MySQL数据库处理器
            if self.config_manager:
                self.db_handler = MySQLHandler(self.config_manager)
                # 尝试连接MySQL
                try:
                    if self.db_handler.connect():
                        logger.info("MySQL数据库连接成功")
                    else:
                        logger.warning("MySQL数据库连接失败，但系统将继续运行")
                except Exception as e:
                    logger.warning(f"MySQL数据库连接异常: {e}，但系统将继续运行")
            else:
                logger.warning("配置管理器未初始化，跳过MySQL数据库处理器")
                self.db_handler = None
            
            # 初始化数据存储，传入MySQL处理器
            self.data_storage = DataStorage(
                mysql_handler=self.db_handler,
                redis_config=self.config_manager.get_section("RedisConfig") if self.config_manager else None,
                influxdb_config=self.config_manager.get_section("InfluxDBConfig") if self.config_manager else None
            )
            logger.info("数据存储初始化成功")
        except Exception as e:
            logger.error(f"数据存储初始化失败: {e}")
            self.data_storage = None
    
    def _init_mqtt_config_manager(self):
        """初始化MQTT配置管理器"""
        try:
            from config.mqtt_config_manager import MQTTConfigManager
            if self.config_manager:
                self.mqtt_config_manager = MQTTConfigManager(self.config_manager)
                # 连接配置更新信号
                if hasattr(self.mqtt_config_manager, 'config_updated'):
                    self.mqtt_config_manager.config_updated.connect(self._on_mqtt_config_updated)
                logger.info("MQTT配置管理器初始化成功")
            else:
                logger.warning("配置管理器未初始化，跳过MQTT配置管理器")
                self.mqtt_config_manager = None
        except Exception as e:
            logger.error(f"MQTT配置管理器初始化失败: {e}")
            self.mqtt_config_manager = None
    
    def _init_mqtt_manager(self):
        """初始化MQTT管理器"""
        try:
            from communication.mqtt_manager import MQTTManager
            
            # 获取MQTT配置
            mqtt_config = {}
            if self.mqtt_config_manager:
                mqtt_config = self.mqtt_config_manager.get_config()
            elif self.config_manager:
                mqtt_config = self.config_manager.get_mqtt_config()
            
            if not mqtt_config:
                mqtt_config = {
                    'host': 'localhost',
                    'port': 1883,
                    'client_id': f'core_ui_client_{int(time.time())}',
                    'topics': ['vehicle/data']
                }
                logger.warning("使用默认MQTT配置")
            
            # 创建MQTT管理器
            self.mqtt_manager = MQTTManager(
                client_id=mqtt_config.get('client_id', f'core_ui_client_{int(time.time())}'),
                broker=mqtt_config.get('host', 'localhost'),
                port=mqtt_config.get('port', 1883),
                topics=mqtt_config.get('topics', ['vehicle/data']),
                username=mqtt_config.get('username'),
                password=mqtt_config.get('password'),
                tls=mqtt_config.get('tls', False)
            )
            
            # 配置重连参数
            if hasattr(self.mqtt_manager, 'auto_reconnect'):
                self.mqtt_manager.auto_reconnect = mqtt_config.get('auto_reconnect', True)
            if hasattr(self.mqtt_manager, 'reconnect_interval'):
                self.mqtt_manager.reconnect_interval = mqtt_config.get('reconnect_interval', 5)
            if hasattr(self.mqtt_manager, 'max_reconnect_attempts'):
                self.mqtt_manager.max_reconnect_attempts = mqtt_config.get('max_reconnect_attempts', 0)
            
            logger.info("MQTT管理器初始化成功")
        except Exception as e:
            logger.error(f"MQTT管理器初始化失败: {e}")
            self.mqtt_manager = None
    
    def _init_serial_manager(self):
        """初始化串口管理器"""
        try:
            from communication.serial_manager import SerialManager
            if self.config_manager:
                self.serial_manager = SerialManager(self.config_manager)
                logger.info("串口管理器初始化成功")
            else:
                logger.warning("配置管理器未初始化，跳过串口管理器")
                self.serial_manager = None
        except Exception as e:
            logger.error(f"串口管理器初始化失败: {e}")
            self.serial_manager = None
    
    def _init_basic_analyzer(self):
        """初始化基础分析器"""
        try:
            from core.core.analysis.base_analyzer import BasicDrivingAnalyzer
            self.basic_analyzer = BasicDrivingAnalyzer()
            logger.info("基础分析器初始化成功")
        except Exception as e:
            logger.error(f"基础分析器初始化失败: {e}")
            self.basic_analyzer = None
    
    def _init_performance_manager(self):
        """初始化性能管理器"""
        try:
            from core.core.performance.performance_manager import VisualizationPerformanceManager
            self.performance_manager = VisualizationPerformanceManager()
            
            # 连接性能管理器的信号
            if hasattr(self.performance_manager, 'performance_updated'):
                self.performance_manager.performance_updated.connect(self._on_performance_updated)
            if hasattr(self.performance_manager, 'performance_adjusted'):
                self.performance_manager.performance_adjusted.connect(self._on_performance_adjusted)
            if hasattr(self.performance_manager, 'resource_cleanup_completed'):
                self.performance_manager.resource_cleanup_completed.connect(self._on_resource_cleanup_completed)
            
            logger.info("性能管理器初始化成功")
        except Exception as e:
            logger.error(f"性能管理器初始化失败: {e}")
            self.performance_manager = None
    
    def _init_data_source_manager(self):
        """初始化数据源管理器"""
        try:
            from core.core.unified_data_flow_manager import UnifiedDataFlowManager
            if self.config_manager:
                self.data_source_manager = UnifiedDataFlowManager()
                logger.info("数据源管理器初始化成功")
            else:
                logger.warning("配置管理器未初始化，跳过数据源管理器")
                self.data_source_manager = None
        except Exception as e:
            logger.error(f"数据源管理器初始化失败: {e}")
            self.data_source_manager = None
    
    def _init_multi_source_sync_components(self):
        """初始化多源异构数据同步组件"""
        try:
            from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine
            from core.core.multi_source_sync.config_manager import MultiSourceSyncConfigManager
            from core.core.multi_source_sync.performance_monitor import RealTimePerformanceMonitor
            from core.core.multi_source_sync.anomaly_detector import IntelligentAnomalyDetector

            # 获取配置
            sync_config = {}
            if self.config_manager:
                sync_config = self.config_manager.get_multi_source_sync_config()
            
            if not sync_config:
                logger.warning("未找到多源同步配置，使用默认配置")
                sync_config = {
                    'enabled': True,
                    'sources': [
                        {'type': 'mqtt', 'config': {'host': 'localhost', 'port': 1883, 'topics': ['vehicle/data']}},
                        {'type': 'serial', 'config': {'port': '/dev/ttyUSB0', 'baudrate': 9600}}
                    ],
                    'sync_interval': 5,
                    'anomaly_detection': True,
                    'anomaly_threshold': 0.1,
                    'anomaly_window': 100
                }
            
            # 创建配置管理器 - 传入配置文件路径而不是配置字典
            config_file_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'multi_source_sync_config.json')
            self.multi_source_sync_config_manager = MultiSourceSyncConfigManager(config_file_path)
            
            # 如果配置管理器支持更新配置，则更新配置
            if hasattr(self.multi_source_sync_config_manager, 'update_config'):
                # 更新各个配置节
                for section_name, section_config in sync_config.items():
                    if hasattr(self.multi_source_sync_config_manager, f'update_{section_name}_config'):
                        getattr(self.multi_source_sync_config_manager, f'update_{section_name}_config')(section_config)
            # 连接配置更新信号
            if hasattr(self.multi_source_sync_config_manager, 'config_updated'):
                self.multi_source_sync_config_manager.config_updated.connect(self._on_multi_source_sync_config_updated)
            
            # 创建性能监控器
            self.multi_source_sync_performance_monitor = RealTimePerformanceMonitor()
            # 连接性能更新信号
            if hasattr(self.multi_source_sync_performance_monitor, 'performance_updated'):
                self.multi_source_sync_performance_monitor.performance_updated.connect(self._on_multi_source_sync_performance_updated)
            
            # 创建异常检测器
            self.multi_source_sync_anomaly_detector = IntelligentAnomalyDetector()
            # 连接异常信号
            if hasattr(self.multi_source_sync_anomaly_detector, 'anomaly_detected'):
                self.multi_source_sync_anomaly_detector.anomaly_detected.connect(self._on_multi_source_sync_anomaly_detected)
            
            # 创建同步引擎 - 只传递配置参数
            sync_engine_config = {
                'config_manager': self.multi_source_sync_config_manager,
                'performance_monitor': self.multi_source_sync_performance_monitor,
                'anomaly_detector': self.multi_source_sync_anomaly_detector,
                'max_workers': 4,
                'sync_interval': 0.01,  # 100Hz
                'max_latency': 0.05,    # 50ms
                'quality_threshold': 0.8,
                'auto_recovery': True
            }
            
            self.multi_source_sync_engine = MultiSourceSyncEngine(config=sync_engine_config)
            # 连接同步引擎的信号
            if hasattr(self.multi_source_sync_engine, 'sync_started'):
                self.multi_source_sync_engine.sync_started.connect(self._on_multi_source_sync_started)
            if hasattr(self.multi_source_sync_engine, 'sync_stopped'):
                self.multi_source_sync_engine.sync_stopped.connect(self._on_multi_source_sync_stopped)
            if hasattr(self.multi_source_sync_engine, 'sync_paused'):
                self.multi_source_sync_engine.sync_paused.connect(self._on_multi_source_sync_paused)
            if hasattr(self.multi_source_sync_engine, 'sync_resumed'):
                self.multi_source_sync_engine.sync_resumed.connect(self._on_multi_source_sync_resumed)
            if hasattr(self.multi_source_sync_engine, 'sync_status_updated'):
                self.multi_source_sync_engine.sync_status_updated.connect(self._on_multi_source_sync_status_updated)
            if hasattr(self.multi_source_sync_engine, 'sync_error'):
                self.multi_source_sync_engine.sync_error.connect(self._on_multi_source_sync_error)
            
            logger.info("多源异构数据同步组件初始化成功")
        except Exception as e:
            logger.error(f"多源异构数据同步组件初始化失败: {e}")
            self.multi_source_sync_engine = None

    def _init_data_bridge(self):
        """初始化数据桥接器"""
        try:
            from core.core.analysis.data_bridge import DataBridge
            self.data_bridge = DataBridge(config_manager=self.config_manager)
            logger.info("DataBridge 数据桥接器初始化成功")
        except Exception as e:
            logger.error(f"DataBridge 初始化失败: {e}")
            self.data_bridge = None

    def _register_services(self):
        """将所有核心服务注册到 ServiceLocator"""
        try:
            from core.core.service_locator import ServiceLocator
            locator = ServiceLocator()

            locator.register('controller', self)
            locator.register('config_manager', self.config_manager)
            locator.register('data_storage', self.data_storage)
            locator.register('db_handler', self.db_handler)
            locator.register('mqtt_manager', self.mqtt_manager)
            locator.register('mqtt_config_manager', self.mqtt_config_manager)
            locator.register('serial_manager', self.serial_manager)
            locator.register('basic_analyzer', self.basic_analyzer)
            locator.register('performance_manager', self.performance_manager)
            locator.register('data_source_manager', self.data_source_manager)
            locator.register('data_bridge', self.data_bridge)
            locator.register('multi_source_sync_engine', self.multi_source_sync_engine)
            locator.register('multi_source_sync_config_manager', self.multi_source_sync_config_manager)
            locator.register('multi_source_sync_performance_monitor', self.multi_source_sync_performance_monitor)
            locator.register('multi_source_sync_anomaly_detector', self.multi_source_sync_anomaly_detector)
            
            # 注册座椅评测相关服务
            locator.register('seat_evaluation_engine', self.seat_evaluation_engine)
            locator.register('comparative_evaluation_engine', self.comparative_evaluation_engine)
            locator.register('multi_channel_data_synchronizer', self.multi_channel_data_synchronizer)
            locator.register('behavior_event_dispatcher', self.behavior_event_dispatcher)

            logger.info("所有核心服务已注册到 ServiceLocator: %s", locator.list_services())
        except Exception as e:
            logger.error("服务注册失败: %s", e)
    
    def _init_connections(self):
        """初始化信号连接"""
        try:
            # 连接UI就绪信号
            self.ui_ready.connect(self._on_ui_ready)
            
            # 连接数据源连接信号
            self.data_source_connected.connect(self._on_data_source_connected)
            
            # 连接分析请求信号
            self.analysis_requested.connect(self._on_analysis_requested)
            
            # 连接系统状态变化信号
            self.system_status_changed.connect(self._on_system_status_changed)
            
            # 连接MQTT信号
            self._connect_mqtt_signals()
            
            # 连接串口信号
            self._connect_serial_signals()
            
            # 连接多源同步信号
            self._connect_multi_source_sync_signals()
            
            logger.info("信号连接初始化完成")
        except Exception as e:
            logger.error(f"信号连接初始化失败: {e}")
    
    def _on_ui_ready(self):
        """处理UI准备就绪信号"""
        self.logger.info("UI已完全加载并准备就绪")
        # 可以在这里添加UI加载完成后的逻辑
        if self.ui_main_window:
            self.ui_main_window.on_ui_ready()
    
    def _on_data_source_connected(self, data_source_info):
        """处理数据源连接信号"""
        try:
            self.logger.info(f"数据源已连接: {data_source_info}")
            # 通知UI主窗口数据源已连接
            if self.ui_main_window:
                self.ui_main_window.on_data_source_connected(data_source_info)
        except Exception as e:
            self.logger.error(f"处理数据源连接信号失败: {e}")
    
    def _on_analysis_requested(self, analysis_params):
        """处理分析请求信号"""
        try:
            self.logger.info(f"收到分析请求: {analysis_params}")
            # 执行分析逻辑
            if self.ui_main_window:
                self.ui_main_window.on_analysis_requested(analysis_params)
        except Exception as e:
            self.logger.error(f"处理分析请求信号失败: {e}")
    
    def _on_system_status_changed(self, status_info):
        """处理系统状态变化信号"""
        try:
            self.logger.info(f"系统状态变化: {status_info}")
            # 更新系统状态
            if self.ui_main_window:
                self.ui_main_window.on_system_status_changed(status_info)
        except Exception as e:
            self.logger.error(f"处理系统状态变化信号失败: {e}")

    def _connect_mqtt_signals(self):
        """连接MQTT信号"""
        try:
            if self.mqtt_manager:
                # 连接MQTT数据接收信号
                if hasattr(self.mqtt_manager, 'data_received'):
                    self.mqtt_manager.data_received.connect(self._on_mqtt_data_received)
                    logger.info("MQTT数据接收信号连接成功")
                
                # 连接MQTT连接状态信号
                if hasattr(self.mqtt_manager, 'sig_connection_status_changed'):
                    self.mqtt_manager.sig_connection_status_changed.connect(self._on_mqtt_connection_status_changed)
                    logger.info("MQTT连接状态信号连接成功")
                
                # 连接MQTT消息接收信号
                if hasattr(self.mqtt_manager, 'sig_message_received'):
                    self.mqtt_manager.sig_message_received.connect(self._on_mqtt_message_received)
                    logger.info("MQTT消息接收信号连接成功")
                
                # 连接MQTT错误信号
                if hasattr(self.mqtt_manager, 'sig_error_occurred'):
                    self.mqtt_manager.sig_error_occurred.connect(self._on_mqtt_error_occurred)
                    logger.info("MQTT错误信号连接成功")
        except Exception as e:
            logger.error(f"连接MQTT信号失败: {e}")
    
    def _connect_serial_signals(self):
        """连接串口信号"""
        try:
            if self.serial_manager:
                # 连接串口数据接收信号
                if hasattr(self.serial_manager, 'data_received'):
                    self.serial_manager.data_received.connect(self._on_serial_data_received)
                    logger.info("串口数据接收信号连接成功")
        except Exception as e:
            logger.error(f"连接串口信号失败: {e}")
    
    def _connect_multi_source_sync_signals(self):
        """连接多源异构数据同步信号"""
        try:
            if self.multi_source_sync_engine:
                # 连接同步开始信号
                if hasattr(self.multi_source_sync_engine, 'sync_started'):
                    self.multi_source_sync_engine.sync_started.connect(self._on_multi_source_sync_started)
                
                # 连接同步停止信号
                if hasattr(self.multi_source_sync_engine, 'sync_stopped'):
                    self.multi_source_sync_engine.sync_stopped.connect(self._on_multi_source_sync_stopped)
                
                # 连接同步暂停信号
                if hasattr(self.multi_source_sync_engine, 'sync_paused'):
                    self.multi_source_sync_engine.sync_paused.connect(self._on_multi_source_sync_paused)
                
                # 连接同步恢复信号
                if hasattr(self.multi_source_sync_engine, 'sync_resumed'):
                    self.multi_source_sync_engine.sync_resumed.connect(self._on_multi_source_sync_resumed)
                
                # 连接同步状态更新信号
                if hasattr(self.multi_source_sync_engine, 'sync_status_updated'):
                    self.multi_source_sync_engine.sync_status_updated.connect(self._on_multi_source_sync_status_updated)
                
                # 连接同步错误信号
                if hasattr(self.multi_source_sync_engine, 'sync_error'):
                    self.multi_source_sync_engine.sync_error.connect(self._on_multi_source_sync_error)
        except Exception as e:
            logger.error(f"连接多源异构数据同步信号失败: {e}")
    
    def _launch_main_ui_directly(self):
        try:
            from modules.ui.core_ui_refactored import CoreUIMainWindow

            self.ui_main_window = CoreUIMainWindow()

            self._connect_ui_signals()

            self.ui_main_window.show()
            self.ui_main_window.raise_()
            self.ui_main_window.activateWindow()

            self.ui_ready.emit()

            self.system_status = "主UI已启动"

            logger.info("主UI直接启动成功")
            
        except Exception as e:
            logger.error(f"启动主UI失败: {e}")
            logger.exception("详细错误信息:")
            # 如果启动失败，显示错误信息
            QMessageBox.critical(None, "错误", f"启动主UI失败:\n{e}")
    
    def _connect_ui_signals(self):
        """连接与主UI的信号（水平关系通信）"""
        if self.ui_main_window:
            try:
                # 连接UI的数据源连接信号
                if hasattr(self.ui_main_window, 'data_source_connected'):
                    self.ui_main_window.data_source_connected.connect(
                        self._on_ui_data_source_connected
                    )
                
                # 连接UI的分析请求信号
                if hasattr(self.ui_main_window, 'analysis_requested'):
                    self.ui_main_window.analysis_requested.connect(
                        self._on_ui_analysis_requested
                    )
                
                # 连接UI的关闭信号
                self.ui_main_window.destroyed.connect(self._on_ui_closed)
                
                logger.info("UI信号连接成功")
            except Exception as e:
                logger.error(f"UI信号连接失败: {e}")
    
    def _update_system_status(self):
        """更新系统状态"""
        try:
            # 这里可以添加实际的系统状态检查逻辑
            if self.ui_main_window and self.ui_main_window.isVisible():
                self.system_status = "运行中"
            else:
                self.system_status = "待机中"
            
        except Exception as e:
            logger.error(f"系统状态更新失败: {e}")
    
    # MQTT配置更新处理
    def _on_mqtt_config_updated(self, config: dict):
        """处理MQTT配置更新"""
        try:
            logger.info("MQTT配置已更新，重新初始化MQTT客户端")
            
            # 断开现有连接
            if self.mqtt_manager:
                try:
                    self.mqtt_manager.disconnect_all()
                except Exception as e:
                    logger.warning(f"断开MQTT连接时出错: {e}")
            
            # 重新初始化MQTT客户端
            self._init_mqtt_manager()
            
            # 重新连接信号
            self._connect_mqtt_signals()
            
            logger.info("MQTT客户端重新初始化完成")
        except Exception as e:
            logger.error(f"处理MQTT配置更新时出错: {e}")
    
    # 数据接收处理
    def _on_mqtt_data_received(self, data_type: str, data: dict):
        """处理MQTT数据接收"""
        try:
            logger.debug(f"接收到MQTT数据: 类型={data_type}, 数据长度={len(data) if isinstance(data, dict) else 'unknown'}")
            
            # 更新UI仪表盘数据
            if self.ui_main_window and hasattr(self.ui_main_window, '_on_mqtt_data_received'):
                self.ui_main_window._on_mqtt_data_received(data_type, data)
                logger.debug(f"成功更新UI仪表盘数据: {data_type}")
            else:
                logger.debug("UI仪表盘数据更新方法不存在")
                
        except Exception as e:
            logger.error(f"处理MQTT数据时出错: {e}")
    
    def _on_mqtt_connection_status_changed(self, connected: bool, message: str):
        """处理MQTT连接状态变更"""
        logger.info(f"MQTT连接状态变更: {message}")
    
    def _on_mqtt_message_received(self, topic: str, payload: str):
        """处理MQTT消息接收"""
        logger.debug(f"收到MQTT消息 - 主题: {topic}, 内容: {payload[:50]}...")
    
    def _on_mqtt_error_occurred(self, client_id: str, error_message: str):
        """处理MQTT错误"""
        logger.error(f"MQTT客户端 {client_id} 发生错误: {error_message}")
    
    def _on_serial_data_received(self, data: dict):
        """处理串口数据接收"""
        try:
            logger.debug(f"接收到串口数据: {len(data) if isinstance(data, dict) else 'unknown'}")
            
            # 更新UI仪表盘数据
            if self.ui_main_window and hasattr(self.ui_main_window, '_on_serial_data_received'):
                self.ui_main_window._on_serial_data_received(data)
                logger.debug("成功更新UI仪表盘串口数据")
            else:
                logger.debug("UI仪表盘串口数据更新方法不存在")
                
        except Exception as e:
            logger.error(f"处理串口数据时出错: {e}")
    
    # 性能管理信号处理
    def _on_performance_updated(self, performance_data: dict):
        """处理性能更新信号"""
        try:
            logger.debug(f"性能数据更新: {performance_data}")
            self.performance_updated.emit(performance_data)
        except Exception as e:
            logger.error(f"处理性能更新信号时出错: {e}")
    
    def _on_performance_adjusted(self, adjustment_data: dict):
        """处理性能调整信号"""
        try:
            logger.debug(f"性能参数调整: {adjustment_data}")
        except Exception as e:
            logger.error(f"处理性能调整信号时出错: {e}")
    
    def _on_resource_cleanup_completed(self):
        """处理资源清理完成事件"""
        try:
            logger.info("系统资源清理完成")
        except Exception as e:
            logger.error(f"处理资源清理完成事件时出错: {e}")
    
    # 多源异构数据同步信号处理
    def _on_multi_source_sync_started(self, sync_info: dict):
        """处理多源同步开始信号"""
        logger.info(f"多源同步开始: {sync_info}")
        self.sync_started.emit(sync_info)
    
    def _on_multi_source_sync_stopped(self):
        """处理多源同步停止信号"""
        logger.info("多源同步停止")
        self.sync_stopped.emit()
    
    def _on_multi_source_sync_paused(self):
        """处理多源同步暂停信号"""
        logger.info("多源同步暂停")
        self.multi_source_sync_paused.emit()
    
    def _on_multi_source_sync_resumed(self):
        """处理多源同步恢复信号"""
        logger.info("多源同步恢复")
        self.multi_source_sync_resumed.emit()
    
    def _on_multi_source_sync_status_updated(self, status_info: dict):
        """处理多源同步状态更新信号"""
        logger.debug(f"多源同步状态更新: {status_info}")
        self.multi_source_sync_status_updated.emit(status_info)
    
    def _on_multi_source_sync_error(self, error_type: str, error_message: str):
        """处理多源同步错误信号"""
        logger.error(f"多源同步错误: {error_type} - {error_message}")
        self.multi_source_sync_error.emit(error_type, error_message)
    
    def _init_logger(self):
        self.logger = logging.getLogger(__name__)

    def start_ui(self, app):
        self.logger.info("启动UI...")
        from PySide6.QtWidgets import QApplication
        
        self._app = app
        
        # 在异步启动UI期间禁止自动退出
        app.setQuitOnLastWindowClosed(False)
        
        QTimer.singleShot(50, self._launch_main_ui_async)
        
        app.aboutToQuit.connect(self.shutdown)
        
        return app.exec()
    
    def _launch_main_ui_async(self):
        """异步启动主UI（分步加载避免阻塞）"""
        try:
            from PySide6.QtWidgets import QApplication
            from modules.ui.core_ui_refactored import CoreUIMainWindow
            from core.core.service_locator import ServiceLocator
            
            for _ in range(5):
                QApplication.processEvents()
            
            self.logger.info("步骤1/4: 创建主窗口实例...")
            self.main_window = CoreUIMainWindow()
            
            for _ in range(5):
                QApplication.processEvents()
            
            ServiceLocator().register('main_window', self.main_window)
            
            for _ in range(5):
                QApplication.processEvents()
            
            self.logger.info("步骤2/4: 注入DataBridge...")
            if self.data_bridge:
                self.main_window.data_bridge = self.data_bridge
                self.logger.info("DataBridge 已注入到主窗口")
            
            for _ in range(5):
                QApplication.processEvents()
            
            self.logger.info("步骤3/4: 显示主窗口...")
            self.main_window.show()
            
            # 主窗口已显示，恢复自动退出功能
            self._app.setQuitOnLastWindowClosed(True)
            
            for _ in range(5):
                QApplication.processEvents()
            
            if hasattr(self.main_window, 'ui_components'):
                self.main_window.ui_components._inject_data_bridge()
                self.logger.info("DataBridge 注入已调度（支持延迟重试）")
                QTimer.singleShot(2000, lambda: self.main_window.ui_components._setup_cache_and_replay(None))
            
            for _ in range(5):
                QApplication.processEvents()
            
            self.logger.info("步骤4/4: 连接信号...")
            self._connect_integrated_panel_signals()
            
            for _ in range(5):
                QApplication.processEvents()
            
            self.logger.info("✅ 主UI异步启动完成")
            
        except Exception as e:
            self.logger.error(f"异步启动主UI失败: {e}")
            self.logger.exception("详细错误信息:")

    def shutdown(self):
        """安全关闭所有子系统并清除所有已加载数据"""
        try:
            self.logger.info("正在安全关闭系统并清除所有已加载数据...")

            if self.data_bridge:
                self.data_bridge.stop_processing()
                if self.data_bridge._pipeline:
                    try:
                        self.data_bridge._pipeline.reset()
                    except Exception:
                        pass
                self.data_bridge._suppress_ui_signals = True
                self.data_bridge.clear_all_data()
                self.logger.info("DataBridge 已停止并清除数据")

            if self.data_source_manager:
                try:
                    self.data_source_manager.stop_all_sources()
                    self.data_source_manager.stop_monitoring()
                    self._clear_all_reader_data()
                except Exception as e:
                    self.logger.warning(f"数据源管理器关闭失败: {e}")

            from core.core.analysis.event_distributor import EventDistributor
            try:
                EventDistributor.instance().clear()
                self.logger.info("EventDistributor 事件已清空")
            except Exception as e:
                self.logger.warning(f"EventDistributor 清除失败: {e}")

            if hasattr(self, 'main_window') and self.main_window:
                try:
                    self.main_window._stop_all_timers()
                    self._clear_main_window_tabs(self.main_window)
                    if hasattr(self.main_window, 'replay_control_bar'):
                        try:
                            self.main_window.replay_control_bar.reset_state()
                        except Exception:
                            pass
                except Exception as e:
                    self.logger.warning(f"主窗口数据清除失败: {e}")

            multi_source_cache = None
            if hasattr(self, 'main_window') and self.main_window:
                multi_source_cache = getattr(self.main_window, '_multi_source_cache', None)
            if multi_source_cache:
                try:
                    multi_source_cache.close()
                    multi_source_cache._clear_db()
                except Exception as e:
                    self.logger.warning(f"MultiSourceCache 清除失败: {e}")

            self.logger.info("系统安全关闭完成，所有数据已清除")
        except Exception as e:
            self.logger.error(f"系统关闭过程中出错: {e}")

    def _clear_main_window_tabs(self, main_window):
        try:
            if hasattr(main_window, 'right_tab') and main_window.right_tab:
                right_tab = main_window.right_tab
                for tab_attr in ['can_full_tab', 'cnap_visualization_tab',
                                   'imu_visualization_tab', 'seat_evaluation_tab',
                                   'comparative_evaluation_tab', 'real_time_monitoring_tab']:
                    tab = getattr(right_tab, tab_attr, None)
                    if tab is None:
                        continue
                    if hasattr(tab, 'clear_data'):
                        try:
                            tab.clear_data()
                            self.logger.info(f"{tab_attr} 数据已清除")
                        except Exception as e:
                            self.logger.warning(f"清除 {tab_attr} clear_data 失败: {e}")
                    elif hasattr(tab, 'cleanup'):
                        try:
                            tab.cleanup()
                            self.logger.info(f"{tab_attr} 已清理")
                        except Exception as e:
                            self.logger.warning(f"清理 {tab_attr} 失败: {e}")

                if hasattr(right_tab, '_replay_events'):
                    right_tab._replay_events.clear()
                if hasattr(right_tab, '_replay_controller') and right_tab._replay_controller:
                    right_tab._replay_controller = None
        except Exception as e:
            self.logger.warning(f"清除标签页数据失败: {e}")

    def _clear_all_reader_data(self):
        try:
            from modules.ui.left_control_panel.utils.data_reader_manager import get_data_reader_manager
            mgr = get_data_reader_manager()
            if mgr:
                mgr.clear_all_reader_data()
        except Exception as e:
            self.logger.warning(f"清除读取器数据失败: {e}")
    
    def _connect_integrated_panel_signals(self):
        """连接集成面板的信号"""
        try:
            if hasattr(self.main_window, 'left_panel') and self.main_window.left_panel:
                left_panel = self.main_window.left_panel
                
                # 检查是否是新的集成面板
                from modules.ui.left_control_panel.integrated_left_panel import IntegratedLeftPanel
                if isinstance(left_panel, IntegratedLeftPanel):
                    # 连接数据源相关信号
                    left_panel.data_source_connected.connect(self._on_integrated_panel_source_connected)
                    left_panel.data_source_disconnected.connect(self._on_integrated_panel_source_disconnected)
                    
                    # 连接同步相关信号
                    left_panel.sync_started.connect(self._on_integrated_panel_sync_started)
                    left_panel.sync_stopped.connect(self._on_integrated_panel_sync_stopped)
                    
                    self.logger.info("集成面板信号连接成功")
        except Exception as e:
            self.logger.warning(f"集成面板信号连接失败: {e}")
    
    def _on_integrated_panel_source_connected(self, source_id):
        """集成面板 - 数据源连接"""
        self.logger.info(f"数据源 {source_id} 已连接")
        self.data_source_connected.emit(source_id)
    
    def _on_integrated_panel_source_disconnected(self, source_id):
        """集成面板 - 数据源断开"""
        self.logger.info(f"数据源 {source_id} 已断开")
    
    def _on_integrated_panel_sync_started(self, config):
        """集成面板 - 同步启动"""
        self.logger.info("数据同步与融合已启动")
        self.sync_started.emit(config)
    
    def _on_integrated_panel_sync_stopped(self):
        """集成面板 - 同步停止"""
        self.logger.info("数据同步与融合已停止")
        self.sync_stopped.emit()

def main():
    """主函数 - 独立启动入口"""
    try:
        # 创建QApplication实例
        app = QApplication(sys.argv)
        app.setApplicationName("Core System Controller")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("Core System Technologies")
        
        # 创建并显示主控制器
        controller = CoreUIController()
        
        print("Core System Controller 启动成功!")
        print("版本: 2.0.0")
        print("功能: 重构后的主控制器，包含完整的基础模块初始化")
        print("提示: 主UI将自动启动")
        print("=" * 60)
        
        return controller.start_ui(app)
            
    except Exception as e:
        print(f"启动失败: {e}")
        return 1

if __name__ == "__main__":
    main()
