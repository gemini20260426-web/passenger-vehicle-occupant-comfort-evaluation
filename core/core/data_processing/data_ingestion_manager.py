#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据接入管理器
统一管理多源数据接入并转发到MQTT
"""
import logging
from PySide6.QtCore import QObject, Slot
from communication.mqtt_client import MQTTClient
from .data_source_adapter import DataSourceAdapter
from .file_data_source_adapter import FileDataSourceAdapter
from .serial_data_source_adapter import SerialDataSourceAdapter
# from core.data_processing.data_source_manager import TimestampSynchronizer  # 已删除


class DataIngestionManager(QObject):
    """数据接入管理器"""
    def __init__(self, mqtt_config=None):
        """初始化数据接入管理器

        Args:
            mqtt_config (dict, optional): MQTT配置. Defaults to None.
        """
        super().__init__()
        self.adapters = {}  # 数据源适配器字典 {adapter_id: adapter_instance}
        self.mqtt_client = None
        # self.timestamp_synchronizer = TimestampSynchronizer()  # 已删除，暂时注释
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_mqtt_client(mqtt_config)
        self.logger.info("数据接入管理器初始化完成")

    def _init_mqtt_client(self, mqtt_config):
        """初始化MQTT客户端

        Args:
            mqtt_config (dict): MQTT配置
        """
        try:
            self.mqtt_client = MQTTClient(mqtt_config)
            self.mqtt_client.connect()
            self.logger.info("MQTT客户端初始化成功")
        except Exception as e:
            self.logger.error(f"MQTT客户端初始化失败: {str(e)}")
            # 不抛出异常，允许在运行时重新连接

    def add_data_source(self, adapter_id, source_type, config):
        """添加数据源

        Args:
            adapter_id (str): 适配器ID
            source_type (str): 数据源类型 (file/serial)
            config (dict): 数据源配置

        Returns:
            bool: 添加成功返回True，否则返回False
        """
        try:
            if adapter_id in self.adapters:
                self.logger.warning(f"适配器ID已存在: {adapter_id}")
                return False

            # 创建适配器实例
            if source_type.lower() == 'file':
                adapter = FileDataSourceAdapter(config)
            elif source_type.lower() == 'serial':
                adapter = SerialDataSourceAdapter(config)
            else:
                self.logger.error(f"不支持的数据源类型: {source_type}")
                return False

            # 连接信号槽
            adapter.data_received.connect(self._on_data_received)
            adapter.connection_status_changed.connect(self._on_adapter_connection_status_changed)
            adapter.error_occurred.connect(self._on_adapter_error_occurred)

            self.adapters[adapter_id] = adapter
            self.logger.info(f"添加数据源成功: {adapter_id}, 类型: {source_type}")
            return True
        except Exception as e:
            self.logger.error(f"添加数据源失败: {str(e)}")
            return False

    def remove_data_source(self, adapter_id):
        """移除数据源

        Args:
            adapter_id (str): 适配器ID

        Returns:
            bool: 移除成功返回True，否则返回False
        """
        try:
            if adapter_id not in self.adapters:
                self.logger.warning(f"适配器ID不存在: {adapter_id}")
                return False

            adapter = self.adapters[adapter_id]
            adapter.stop()
            adapter.disconnect()

            # 断开信号槽连接
            adapter.data_received.disconnect(self._on_data_received)
            adapter.connection_status_changed.disconnect(self._on_adapter_connection_status_changed)
            adapter.error_occurred.disconnect(self._on_adapter_error_occurred)

            del self.adapters[adapter_id]
            self.logger.info(f"移除数据源成功: {adapter_id}")
            return True
        except Exception as e:
            self.logger.error(f"移除数据源失败: {str(e)}")
            return False

    def start_data_source(self, adapter_id):
        """启动数据源

        Args:
            adapter_id (str): 适配器ID

        Returns:
            bool: 启动成功返回True，否则返回False
        """
        try:
            if adapter_id not in self.adapters:
                self.logger.warning(f"适配器ID不存在: {adapter_id}")
                return False

            adapter = self.adapters[adapter_id]
            if not adapter.is_connected():
                if not adapter.connect():
                    self.logger.error(f"连接数据源失败: {adapter_id}")
                    return False

            adapter.start()
            self.logger.info(f"启动数据源成功: {adapter_id}")
            return True
        except Exception as e:
            self.logger.error(f"启动数据源失败: {str(e)}")
            return False

    def stop_data_source(self, adapter_id):
        """停止数据源

        Args:
            adapter_id (str): 适配器ID

        Returns:
            bool: 停止成功返回True，否则返回False
        """
        try:
            if adapter_id not in self.adapters:
                self.logger.warning(f"适配器ID不存在: {adapter_id}")
                return False

            adapter = self.adapters[adapter_id]
            adapter.stop()
            self.logger.info(f"停止数据源成功: {adapter_id}")
            return True
        except Exception as e:
            self.logger.error(f"停止数据源失败: {str(e)}")
            return False

    def start_all_data_sources(self):
        """启动所有数据源

        Returns:
            bool: 所有数据源启动成功返回True，否则返回False
        """
        all_success = True
        for adapter_id in self.adapters:
            if not self.start_data_source(adapter_id):
                all_success = False
        return all_success

    def stop_all_data_sources(self):
        """停止所有数据源"""
        for adapter_id in self.adapters:
            self.stop_data_source(adapter_id)

    @Slot(dict)
    def _on_data_received(self, data):
        """数据接收回调

        Args:
            data (dict): 接收到的数据
        """
        try:
            if not self.mqtt_client or not self.mqtt_client.is_connected():
                self.logger.error("MQTT客户端未连接，无法发送数据")
                return

            # 同步时间戳
            synchronized_data = self.timestamp_synchronizer.sync_timestamp(data)

            # 发布到MQTT
            data_type = synchronized_data.get('data_type', 'unknown')
            source = synchronized_data.get('source', 'unknown')
            topic = f"data/{source}/{data_type}"

            self.mqtt_client.send_data(topic, synchronized_data)
            self.logger.debug(f"发送数据到MQTT主题: {topic}, 数据: {synchronized_data}")
        except Exception as e:
            self.logger.error(f"处理接收到的数据失败: {str(e)}")

    @Slot(str, bool)
    def _on_adapter_connection_status_changed(self, adapter_id, status):
        """适配器连接状态变化回调

        Args:
            adapter_id (str): 适配器ID
            status (bool): 连接状态
        """
        self.logger.info(f"适配器{adapter_id}连接状态变更为: {'已连接' if status else '已断开'}")

    @Slot(str, str)
    def _on_adapter_error_occurred(self, adapter_id, error_msg):
        """适配器错误发生回调

        Args:
            adapter_id (str): 适配器ID
            error_msg (str): 错误消息
        """
        self.logger.error(f"适配器{adapter_id}发生错误: {error_msg}")

    def connect_mqtt(self, config=None):
        """连接MQTT服务器

        Args:
            config (dict, optional): MQTT配置. Defaults to None.

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                self.logger.warning("MQTT客户端已连接")
                return True

            if config:
                self._init_mqtt_client(config)
            elif self.mqtt_client:
                self.mqtt_client.connect()
            else:
                self.logger.error("MQTT客户端未初始化")
                return False

            return self.mqtt_client.is_connected()
        except Exception as e:
            self.logger.error(f"连接MQTT服务器失败: {str(e)}")
            return False

    def disconnect_mqtt(self):
        """断开MQTT服务器连接"""
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                self.mqtt_client.disconnect()
                self.logger.info("已断开MQTT服务器连接")
        except Exception as e:
            self.logger.error(f"断开MQTT服务器连接失败: {str(e)}")

    def is_mqtt_connected(self):
        """检查MQTT连接状态

        Returns:
            bool: 已连接返回True，否则返回False
        """
        return self.mqtt_client and self.mqtt_client.is_connected()

    def get_adapter_status(self, adapter_id):
        """获取适配器状态

        Args:
            adapter_id (str): 适配器ID

        Returns:
            dict: 适配器状态字典
        """
        if adapter_id not in self.adapters:
            self.logger.warning(f"适配器ID不存在: {adapter_id}")
            return None

        adapter = self.adapters[adapter_id]
        return {
            'connected': adapter.is_connected(),
            'running': adapter.is_running(),
            'data_type': adapter.data_type
        }

    def get_all_adapters_status(self):
        """获取所有适配器状态

        Returns:
            dict: 所有适配器状态字典
        """
        status = {}
        for adapter_id, adapter in self.adapters.items():
            status[adapter_id] = self.get_adapter_status(adapter_id)
        return status