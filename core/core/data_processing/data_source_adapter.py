#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源适配器基类
定义所有数据源适配器需要实现的接口
"""
from abc import ABCMeta, abstractmethod
import logging
from PySide6.QtCore import QObject, Signal


# 获取QObject的元类
QObjectMeta = type(QObject)

# 自定义元类，解决QObject和ABCMeta的元类冲突
class QABCMeta(QObjectMeta, ABCMeta):
    pass


class DataSourceAdapter(QObject, metaclass=QABCMeta):
    """数据源适配器抽象基类"""
    # 信号定义
    data_received = Signal(dict)  # 数据接收信号
    connection_status_changed = Signal(bool)  # 连接状态变化信号
    error_occurred = Signal(str)  # 错误发生信号

    def __init__(self, config=None):
        """初始化数据源适配器

        Args:
            config (dict, optional): 数据源配置. Defaults to None.
        """
        super().__init__()
        self.config = config or {}
        self.connected = False
        self.running = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"初始化{self.__class__.__name__}")

    @abstractmethod
    def connect(self):
        """连接数据源

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        pass

    @abstractmethod
    def disconnect(self):
        """断开数据源连接"""
        pass

    @abstractmethod
    def start(self):
        """开始从数据源读取数据"""
        pass

    @abstractmethod
    def stop(self):
        """停止从数据源读取数据"""
        pass

    @abstractmethod
    def get_data(self):
        """获取数据

        Returns:
            dict: 数据字典
        """
        pass

    def is_connected(self):
        """检查是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        return self.connected

    def is_running(self):
        """检查是否正在运行

        Returns:
            bool: 正在运行返回True，否则返回False
        """
        return self.running

    def set_config(self, config):
        """设置配置

        Args:
            config (dict): 配置字典
        """
        self.config = config
        self.logger.info(f"更新配置: {config}")

    def _emit_data(self, data):
        """发送数据信号

        Args:
            data (dict): 数据字典
        """
        if data:
            self.data_received.emit(data)
            self.logger.debug(f"发送数据: {data}")

    def _emit_connection_status(self, status):
        """发送连接状态信号

        Args:
            status (bool): 连接状态
        """
        self.connected = status
        self.connection_status_changed.emit(status)
        self.logger.info(f"连接状态变更为: {'已连接' if status else '已断开'}")

    def _emit_error(self, error_msg):
        """发送错误信号

        Args:
            error_msg (str): 错误消息
        """
        self.error_occurred.emit(error_msg)
        self.logger.error(f"错误发生: {error_msg}")