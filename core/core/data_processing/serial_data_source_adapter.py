#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口数据源适配器
用于处理串口数据的接入和转换
"""
import logging
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from PySide6.QtCore import Slot
from .data_source_adapter import DataSourceAdapter
from communication.serial_manager import SerialManager
from utils.utils import get_timestamp


class SerialDataSourceAdapter(DataSourceAdapter):
    """串口数据源适配器"""
    def __init__(self, config=None):
        """初始化串口数据源适配器

        Args:
            config (dict, optional): 数据源配置. Defaults to None.
        """
        super().__init__(config)
        self.serial_manager = None
        self.data_type = self.config.get('data_type', 'IMU')  # 默认为IMU数据
        self._init_serial_manager()
        self.logger.info(f"串口数据源适配器初始化完成，数据类型: {self.data_type}")

    def _init_serial_manager(self):
        """初始化串口管理器"""
        try:
            self.serial_manager = SerialManager()
            # 连接信号槽
            self.serial_manager.data_received.connect(self._on_serial_data_received)
            self.serial_manager.connection_status_changed.connect(self._on_connection_status_changed)
            self.serial_manager.error_occurred.connect(self._on_error_occurred)
            self.logger.info("初始化串口管理器成功")
        except Exception as e:
            self.logger.error(f"初始化串口管理器失败: {str(e)}")
            self._emit_error(f"初始化串口管理器失败: {str(e)}")

    @Slot(dict)
    def _on_serial_data_received(self, data):
        """串口数据接收回调

        Args:
            data (dict): 接收到的数据字典
        """
        try:
            self.logger.debug(f"接收到串口数据: {data}")

            # 处理接收到的数据
            processed_data = {
                'raw_data': data,
                'data_type': self.data_type,
                'source': 'serial',
                'timestamp': get_timestamp()
            }

            # 发送数据信号
            self._emit_data(processed_data)
        except Exception as e:
            self.logger.error(f"处理串口数据失败: {str(e)}")
            self._emit_error(f"处理串口数据失败: {str(e)}")

    @Slot(bool)
    def _on_connection_status_changed(self, status):
        """连接状态变化回调

        Args:
            status (bool): 连接状态
        """
        self._emit_connection_status(status)

    @Slot(str)
    def _on_error_occurred(self, error_msg):
        """错误发生回调

        Args:
            error_msg (str): 错误消息
        """
        self._emit_error(error_msg)

    def connect(self):
        """连接串口数据源

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            if not self.serial_manager:
                self._init_serial_manager()
                if not self.serial_manager:
                    return False

            # 配置串口参数
            port = self.config.get('port', 'COM1')
            baudrate = self.config.get('baudrate', 9600)
            timeout = self.config.get('timeout', 1)

            # 连接串口
            result = self.serial_manager.connect(port, baudrate, timeout)
            if result:
                self.logger.info(f"成功连接串口: {port}, 波特率: {baudrate}")
            else:
                self.logger.error(f"连接串口{port}失败")
            return result
        except Exception as e:
            self.logger.error(f"连接串口数据源失败: {str(e)}")
            self._emit_error(f"连接串口数据源失败: {str(e)}")
            return False

    def disconnect(self):
        """断开串口数据源连接"""
        try:
            if self.serial_manager and self.serial_manager.is_connected():
                self.serial_manager.disconnect()
            self._emit_connection_status(False)
            self.logger.info("已断开串口数据源连接")
        except Exception as e:
            self.logger.error(f"断开串口数据源连接失败: {str(e)}")
            self._emit_error(f"断开串口数据源连接失败: {str(e)}")

    def start(self):
        """开始从串口读取数据"""
        if not self.is_connected():
            self.logger.error("未连接数据源，无法开始读取")
            self._emit_error("未连接数据源，无法开始读取")
            return

        if self.running:
            self.logger.warning("数据读取已在运行中")
            return

        try:
            self.serial_manager.start()
            self.running = True
            self.logger.info("开始读取串口数据")
        except Exception as e:
            self.logger.error(f"启动串口数据读取失败: {str(e)}")
            self._emit_error(f"启动串口数据读取失败: {str(e)}")

    def stop(self):
        """停止从串口读取数据"""
        if not self.running:
            return

        try:
            if self.serial_manager:
                self.serial_manager.stop()
            self.running = False
            self.logger.info("已停止读取串口数据")
        except Exception as e:
            self.logger.error(f"停止串口数据读取失败: {str(e)}")
            self._emit_error(f"停止串口数据读取失败: {str(e)}")

    def get_data(self):
        """获取数据(串口数据源不直接支持此方法)

        Returns:
            dict: 空字典
        """
        self.logger.warning("串口数据源不支持直接获取数据，请使用data_received信号")
        return {}

    def set_config(self, config):
        """设置配置

        Args:
            config (dict): 配置字典
        """
        super().set_config(config)
        # 更新数据类型
        new_data_type = config.get('data_type', self.data_type)
        if new_data_type != self.data_type:
            self.data_type = new_data_type
            self.logger.info(f"更新数据类型为: {self.data_type}")
        # 如果已连接，重新连接
        if self.is_connected():
            self.disconnect()
            self.connect()