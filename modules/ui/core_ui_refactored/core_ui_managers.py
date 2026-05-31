#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 管理器模块
负责各种业务管理器的初始化和管理
"""

import logging


class CoreUIManagers:
    """业务管理器初始化"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

    def init_config_manager(self):
        """初始化配置管理器"""
        main = self.main_window
        try:
            from config.config_manager import ConfigManager
            main.config_manager = ConfigManager.instance()
            self.logger.info("配置管理器初始化成功（统一ConfigManager）")
        except Exception as e:
            self.logger.warning(f"配置管理器初始化失败: {e}")
            main.config_manager = None

    def init_data_storage(self):
        """初始化数据存储"""
        main = self.main_window
        try:
            from core.core.storage.data_storage_manager import DataStorageManager
            main.data_storage = DataStorageManager()
            self.logger.info("数据存储初始化成功")
        except ImportError:
            self.logger.warning("数据存储模块不可用")
            main.data_storage = None

    def init_mqtt_config_manager(self):
        """初始化MQTT配置管理器"""
        main = self.main_window
        try:
            from modules.ui.core_ui.services.mqtt_config_manager import MQTTConfigManager
            main.mqtt_config_manager = MQTTConfigManager()
            self.logger.info("MQTT配置管理器初始化成功")
        except ImportError:
            self.logger.warning("MQTT配置管理器不可用")
            main.mqtt_config_manager = None

    def init_mqtt_manager(self):
        """初始化MQTT管理器"""
        main = self.main_window
        try:
            from modules.ui.core_ui.services.mqtt_manager import MQTTManager
            main.mqtt_manager = MQTTManager()
            self.logger.info("MQTT管理器初始化成功")
        except ImportError:
            self.logger.warning("MQTT管理器不可用")
            main.mqtt_manager = None

    def init_serial_manager(self):
        """初始化串口管理器"""
        main = self.main_window
        try:
            from modules.ui.core_ui.services.serial_manager import SerialManager
            main.serial_manager = SerialManager()
            self.logger.info("串口管理器初始化成功")
        except ImportError:
            self.logger.warning("串口管理器不可用")
            main.serial_manager = None

    def init_basic_analyzer(self):
        """初始化基础分析器"""
        main = self.main_window
        try:
            from core.core.analysis.base_analyzer import BasicDrivingAnalyzer
            main.basic_analyzer = BasicDrivingAnalyzer()
            self.logger.info("基础分析器初始化成功")
        except ImportError:
            self.logger.warning("基础分析器不可用")
            main.basic_analyzer = None

    def init_performance_manager(self):
        """初始化性能管理器"""
        main = self.main_window
        try:
            from core.core.performance.performance_manager import PerformanceManager
            main.performance_manager = PerformanceManager()
            self.logger.info("性能管理器初始化成功")
        except ImportError:
            self.logger.warning("性能管理器不可用")
            main.performance_manager = None

    def init_data_source_manager(self):
        """初始化数据源管理器"""
        main = self.main_window
        try:
            from core.core.data_processing.multi_source_sync_manager import MultiSourceDataSyncManager
            main.data_source_manager = MultiSourceDataSyncManager()
            self.logger.info("数据源管理器初始化成功")
        except ImportError:
            self.logger.warning("数据源管理器不可用")
            main.data_source_manager = None

    def init_multi_source_sync_components(self):
        """初始化多源同步组件"""
        main = self.main_window
        try:
            from core.core.multi_source_sync.sync_engine import MultiSourceSyncEngine
            main.sync_engine = MultiSourceSyncEngine()
            self.logger.info("多源同步引擎初始化成功")
        except ImportError:
            self.logger.warning("多源同步引擎不可用")
            main.sync_engine = None

    def init_all(self):
        """初始化所有管理器"""
        self.init_config_manager()
        self.init_data_storage()
        self.init_mqtt_config_manager()
        self.init_mqtt_manager()
        self.init_serial_manager()
        self.init_basic_analyzer()
        self.init_performance_manager()
        self.init_data_source_manager()
        self.init_multi_source_sync_components()
        self.logger.info("所有管理器初始化完成")
