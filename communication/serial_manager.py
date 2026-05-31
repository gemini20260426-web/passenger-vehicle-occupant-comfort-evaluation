#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
串口管理器适配器
将ProtoSerialDataReader适配为与旧SerialManager兼容的接口
"""

import logging
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class SerialManager(QObject):
    """
    串口管理器适配器
    适配ProtoSerialDataReader以兼容旧的SerialManager接口
    """
    
    # 定义信号
    data_received = Signal(object)  # 数据接收信号 - 使用object类型避免类型解析问题
    error_occurred = Signal(str)  # 错误发生信号
    connected = Signal()  # 连接成功信号
    disconnected = Signal(str)  # 断开连接信号
    connection_status_changed = Signal(bool)
    
    def __init__(self, config_manager=None):
        super().__init__()
        self.proto_reader = None
        self.data_callback = None
        self.log_callback = None
        self.connection_callback = None
        self.config_manager = config_manager
        
        try:
            # 尝试导入ProtoSerialDataReader
            from core.core.data_processing.proto_serial_reader import ProtoSerialDataReader
            
            if config_manager:
                # 如果有配置管理器，使用配置初始化
                try:
                    serial_config = config_manager.get_serial_config()
                    if serial_config:
                        port = serial_config.get("port", "COM9")
                        baudrate = serial_config.get("baudrate", 921600)
                        flow_control = serial_config.get("flow_control", "none")
                        auto_reconnect = serial_config.get("auto_reconnect", True)
                        reconnect_interval = serial_config.get("reconnect_interval", 3)
                        
                        # 创建ProtoSerialDataReader实例
                        self.proto_reader = ProtoSerialDataReader(
                            port=port,
                            baudrate=baudrate,
                            flow_control=flow_control,
                            auto_reconnect=auto_reconnect,
                            reconnect_interval=reconnect_interval
                        )
                        
                        # 设置流控制参数
                        if 'xonxoff' in serial_config or 'rtscts' in serial_config or 'dsrdtr' in serial_config:
                            flow_params = {
                                'xonxoff': serial_config.get('xonxoff', False),
                                'rtscts': serial_config.get('rtscts', False),
                                'dsrdtr': serial_config.get('dsrdtr', False)
                            }
                            self.proto_reader.set_flow_control(flow_params)
                        
                        # 连接信号
                        self._connect_signals()
                        
                        logger.info("ProtoSerialDataReader初始化成功")
                    else:
                        logger.warning("未找到串口配置，使用默认配置")
                        self.proto_reader = ProtoSerialDataReader()
                        self._connect_signals()
                except Exception as e:
                    logger.error(f"使用配置初始化ProtoSerialDataReader失败: {e}")
                    # 使用默认配置
                    self.proto_reader = ProtoSerialDataReader()
                    self._connect_signals()
            else:
                # 没有配置管理器，使用默认配置
                logger.info("使用默认配置初始化ProtoSerialDataReader")
                self.proto_reader = ProtoSerialDataReader()
                self._connect_signals()
                
        except ImportError as e:
            logger.error(f"导入ProtoSerialDataReader失败: {e}")
            self.proto_reader = None
        except Exception as e:
            logger.error(f"初始化ProtoSerialDataReader时发生未知错误: {e}")
            self.proto_reader = None
    
    def _connect_signals(self):
        """连接所有信号"""
        if not self.proto_reader:
            logger.warning("proto_reader未初始化，无法连接信号")
            return
            
        logger.info("开始连接信号")
        
        try:
            # 确保proto_reader有正确的信号属性
            if hasattr(self.proto_reader, 'data_received_signal'):
                # 使用正确的信号连接语法
                self.proto_reader.data_received_signal.connect(self._on_data_received)
                logger.info("data_received_signal信号连接成功")
            else:
                logger.warning("proto_reader没有data_received_signal信号")
        except Exception as e:
            logger.warning(f"data_received_signal信号连接失败: {e}")
            
        try:
            if hasattr(self.proto_reader, 'error_occurred_signal'):
                # 使用正确的信号连接语法
                self.proto_reader.error_occurred_signal.connect(self._on_error)
                logger.info("error_occurred_signal信号连接成功")
            else:
                logger.warning("proto_reader没有error_occurred_signal信号")
        except Exception as e:
            logger.warning(f"error_occurred_signal信号连接失败: {e}")
            
        try:
            if hasattr(self.proto_reader, 'connected_signal'):
                # 使用正确的信号连接语法
                self.proto_reader.connected_signal.connect(self._on_connected)
                logger.info("connected_signal信号连接成功")
            else:
                logger.warning("proto_reader没有connected_signal信号")
        except Exception as e:
            logger.warning(f"connected_signal信号连接失败: {e}")
            
        try:
            if hasattr(self.proto_reader, 'disconnected_signal'):
                # 使用正确的信号连接语法
                self.proto_reader.disconnected_signal.connect(self._on_disconnected)
                logger.info("disconnected_signal信号连接成功")
            else:
                logger.warning("proto_reader没有disconnected_signal信号")
        except Exception as e:
            logger.warning(f"disconnected_signal信号连接失败: {e}")
            
        try:
            if hasattr(self.proto_reader, 'connection_status_changed_signal'):
                # 使用正确的信号连接语法
                self.proto_reader.connection_status_changed_signal.connect(self._on_connection_status_changed)
                logger.info("connection_status_changed_signal信号连接成功")
            else:
                logger.warning("proto_reader没有connection_status_changed_signal信号")
        except Exception as e:
            logger.warning(f"connection_status_changed_signal信号连接失败: {e}")
        
        logger.info("信号连接完成")

    def _on_data_received(self, data):
        """处理数据接收信号"""
        # 转发数据接收信号
        self.data_received.emit(data)
        # 调用回调函数（如果存在）
        if self.data_callback:
            try:
                self.data_callback(data)
            except Exception as e:
                logger.error(f"调用数据回调函数时出错: {e}")

    def _on_error(self, error_msg):
        """处理错误信号"""
        # 转发错误信号
        self.error_occurred.emit(error_msg)
        # 调用日志回调函数（如果存在）
        if self.log_callback:
            try:
                self.log_callback(f"错误: {error_msg}")
            except Exception as e:
                logger.error(f"调用日志回调函数时出错: {e}")

    def _on_connected(self):
        """处理连接成功信号"""
        logger.info("串口连接成功")
        # 转发连接成功信号
        self.connected.emit()
        # 转发连接状态变化信号
        self.connection_status_changed.emit(True)
        if self.connection_callback:
            self.connection_callback(True, "串口连接成功")

    def _on_disconnected(self, reason):
        """处理断开连接信号"""
        logger.info(f"串口断开: {reason}")
        # 转发断开连接信号
        self.disconnected.emit(reason)
        # 转发连接状态变化信号
        self.connection_status_changed.emit(False)
        if self.connection_callback:
            self.connection_callback(False, reason)

    def _on_connection_status_changed(self, connected):
        """处理连接状态变化信号"""
        logger.info(f"串口连接状态变化: {connected}")
        # 转发连接状态变化信号
        self.connection_status_changed.emit(connected)

    def set_data_callback(self, callback):
        """
        设置数据接收回调函数
        
        Args:
            callback: 数据接收回调函数
        """
        self.data_callback = callback

    def set_logger(self, logger_func):
        """
        设置日志回调函数
        
        Args:
            logger_func: 日志回调函数
        """
        self.log_callback = logger_func
    
    def set_connection_callback(self, callback):
        """
        设置连接状态回调函数
        
        Args:
            callback: 连接状态回调函数
        """
        self.connection_callback = callback
    
    def is_connected(self):
        """
        检查串口是否连接
        
        Returns:
            bool: 是否连接
        """
        return self.proto_reader.is_connected if self.proto_reader else False
    
    def start(self, data_callback=None):
        """
        启动串口数据读取
        
        Args:
            data_callback: 数据回调函数
            
        Returns:
            bool: 是否启动成功
        """
        if data_callback:
            self.data_callback = data_callback
            
        if not self.proto_reader:
            logger.error("ProtoSerialDataReader未初始化")
            return False
            
        try:
            # 启动数据读取
            result = self.proto_reader.start(self._on_data_received)
            if result:
                logger.info("串口数据读取启动成功")
            else:
                logger.error("串口数据读取启动失败")
            return result
        except Exception as e:
            logger.error(f"启动串口数据读取时出错: {e}")
            return False
    
    def stop(self):
        """停止串口数据读取"""
        if self.proto_reader:
            try:
                self.proto_reader.stop()
                logger.info("串口数据读取已停止")
                return True
            except Exception as e:
                logger.error(f"停止串口数据读取时出错: {e}")
                return False
        return False
    
    def connect_serial(self, port=None, baudrate=None, timeout=None):
        """
        连接串口（兼容旧接口）
        重命名方法以避免与信号连接方法冲突
        
        Args:
            port: 串口端口
            baudrate: 波特率
            timeout: 超时时间
            
        Returns:
            bool: 是否连接成功
        """
        if not self.proto_reader:
            logger.error("ProtoSerialDataReader未初始化")
            return False
        
        # 验证参数类型 - 允许更灵活的类型
        if port is not None:
            # 如果port是SerialManager实例，尝试获取其端口信息
            if hasattr(port, 'port'):
                port = port.port
            elif not isinstance(port, str):
                logger.warning(f"端口参数类型警告: 期望str，实际{type(port).__name__}，尝试转换")
                port = str(port)
            
        if baudrate is not None and not isinstance(baudrate, (int, str)):
            logger.warning(f"波特率参数类型警告: 期望int或str，实际{type(baudrate).__name__}，尝试转换")
            try:
                baudrate = int(baudrate)
            except (ValueError, TypeError):
                logger.error(f"无法转换波特率参数: {baudrate}")
                return False
            
        try:
            # 连接串口
            result = self.proto_reader.connect_to_serial_port(port, baudrate)
            if result:
                logger.info(f"串口连接成功: {port or self.proto_reader.port}")
            else:
                logger.error("串口连接失败")
            return result
        except Exception as e:
            logger.error(f"连接串口时出错: {e}")
            return False
    
    # 保持向后兼容性 - 重命名避免与Qt信号连接方法冲突
    def connect_serial_port(self, port=None, baudrate=None, timeout=None):
        """连接到串口（兼容性方法）
        
        Args:
            port: 串口端口
            baudrate: 波特率
            timeout: 超时时间（兼容性参数，实际未使用）
            
        Returns:
            bool: 是否连接成功
        """
        return self.connect_serial(port, baudrate, timeout)
    
    # 完全移除connect方法以避免与Qt信号连接方法冲突
    # 使用connect_serial_port方法代替
    
    def disconnect(self):
        """断开串口连接"""
        if self.proto_reader:
            try:
                self.proto_reader.disconnect()
                logger.info("串口连接已断开")
                return True
            except Exception as e:
                logger.error(f"断开串口连接时出错: {e}")
                return False
        return False
    
    def close(self):
        """关闭串口管理器（兼容性方法）"""
        try:
            if self.proto_reader:
                self.proto_reader.stop()
                self.proto_reader.disconnect()
                logger.info("串口管理器已关闭")
            return True
        except Exception as e:
            logger.error(f"关闭串口管理器时出错: {e}")
            return False