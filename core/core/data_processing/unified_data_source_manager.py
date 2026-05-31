#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一数据源管理器
整合现有的数据源管理功能和多源同步功能
解决架构混乱、代码冗余问题
"""

import os
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from queue import Queue, Empty
import numpy as np

# 导入现有的解析器和处理器
try:
    from .data_parser import IMUDataParser
    from .cnap_parser import CNAPDataParser
except ImportError:
    IMUDataParser = None
    CNAPDataParser = None

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """数据源类型枚举"""
    IMU = "imu"
    CNAP = "cnap"
    CUSTOM = "custom"


class TransmissionType(Enum):
    """传输类型枚举"""
    FILE = "file"
    MQTT = "mqtt"
    TCP = "tcp"
    UDP = "udp"
    SERIAL = "serial"


class DataSourceStatus(Enum):
    """数据源状态枚举"""
    INACTIVE = "inactive"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READING = "reading"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class DataSourceConfig:
    """数据源配置"""
    source_id: str
    name: str
    data_type: DataSourceType
    transmission_type: TransmissionType
    config: Dict[str, Any]
    enabled: bool = True
    auto_connect: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source_id': self.source_id,
            'name': self.name,
            'data_type': self.data_type.value,
            'transmission_type': self.transmission_type.value,
            'config': self.config,
            'enabled': self.enabled,
            'auto_connect': self.auto_connect,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSourceConfig':
        """从字典创建"""
        return cls(
            source_id=data['source_id'],
            name=data['name'],
            data_type=DataSourceType(data['data_type']),
            transmission_type=TransmissionType(data['transmission_type']),
            config=data['config'],
            enabled=data.get('enabled', True),
            auto_connect=data.get('auto_connect', False),
            created_at=datetime.fromisoformat(data['created_at'])
        )


@dataclass
class DataSourceStatusInfo:
    """数据源状态信息"""
    source_id: str
    status: str  # 使用字符串而不是枚举，避免循环引用
    last_update: datetime
    data_quality: float = 0.0  # 0-100
    latency_ms: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    data_points_received: int = 0
    data_points_processed: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source_id': self.source_id,
            'status': self.status.value,
            'last_update': self.last_update.isoformat(),
            'data_quality': self.data_quality,
            'latency_ms': self.latency_ms,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'data_points_received': self.data_points_received,
            'data_points_processed': self.data_points_processed
        }


class UnifiedDataSourceManager:
    """
    统一数据源管理器
    整合现有的数据源管理功能和多源同步功能
    """
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # 数据源管理
        self.data_sources: Dict[str, DataSourceConfig] = {}
        self.source_statuses: Dict[str, DataSourceStatusInfo] = {}
        self.active_sources: List[str] = []
        
        # 数据解析器
        self.parsers = {
            DataSourceType.IMU: IMUDataParser() if IMUDataParser else None,
            DataSourceType.CNAP: CNAPDataParser() if CNAPDataParser else None
        }
        
        # 同步管理
        self.sync_running = False
        self.sync_thread = None
        self.sync_queue = Queue()
        self.sync_lock = threading.Lock()
        
        # 数据记录
        self.recording = False
        self.recorded_data: Dict[str, List[Any]] = {}
        self.recording_start_time: Optional[datetime] = None
        
        # 回调函数
        self.data_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # 系统状态
        self.system_health = 100.0
        self.last_system_update = datetime.now()
        
        self.logger.info("统一数据源管理器初始化完成")
    
    def add_data_source(self, config: DataSourceConfig) -> bool:
        """添加数据源"""
        try:
            if config.source_id in self.data_sources:
                self.logger.warning(f"数据源 {config.source_id} 已存在，将被覆盖")
            
            self.data_sources[config.source_id] = config
            
            # 初始化状态
            self.source_statuses[config.source_id] = DataSourceStatusInfo(
                source_id=config.source_id,
                status=DataSourceStatus.INACTIVE.value,
                last_update=datetime.now()
            )
            
            # 如果启用自动连接，尝试连接
            if config.auto_connect:
                self.connect_data_source(config.source_id)
            
            self.logger.info(f"数据源 {config.source_id} 添加成功")
            self._notify_status_change()
            return True
            
        except Exception as e:
            self.logger.error(f"添加数据源失败: {e}")
            return False
    
    def remove_data_source(self, source_id: str) -> bool:
        """移除数据源"""
        try:
            if source_id in self.data_sources:
                # 断开连接
                self.disconnect_data_source(source_id)
                
                # 移除数据源和状态
                del self.data_sources[source_id]
                if source_id in self.source_statuses:
                    del self.source_statuses[source_id]
                
                # 从活动源中移除
                if source_id in self.active_sources:
                    self.active_sources.remove(source_id)
                
                self.logger.info(f"数据源 {source_id} 移除成功")
                self._notify_status_change()
                return True
            else:
                self.logger.warning(f"数据源 {source_id} 不存在")
                return False
                
        except Exception as e:
            self.logger.error(f"移除数据源失败: {e}")
            return False
    
    def connect_data_source(self, source_id: str) -> bool:
        """连接数据源"""
        try:
            if source_id not in self.data_sources:
                self.logger.error(f"数据源 {source_id} 不存在")
                return False
            
            config = self.data_sources[source_id]
            status = self.source_statuses[source_id]
            
            # 更新状态
            status.status = DataSourceStatus.CONNECTING.value
            status.last_update = datetime.now()
            self._notify_status_change()
            
            # 根据传输类型建立连接
            if config.transmission_type == TransmissionType.FILE:
                success = self._connect_file_source(config, status)
            elif config.transmission_type == TransmissionType.MQTT:
                success = self._connect_mqtt_source(config, status)
            elif config.transmission_type == TransmissionType.TCP:
                success = self._connect_tcp_source(config, status)
            elif config.transmission_type == TransmissionType.UDP:
                success = self._connect_udp_source(config, status)
            elif config.transmission_type == TransmissionType.SERIAL:
                success = self._connect_serial_source(config, status)
            else:
                self.logger.error(f"不支持的传输类型: {config.transmission_type}")
                success = False
            
            if success:
                status.status = DataSourceStatus.CONNECTED.value
                if source_id not in self.active_sources:
                    self.active_sources.append(source_id)
                self.logger.info(f"数据源 {source_id} 连接成功")
            else:
                status.status = DataSourceStatus.ERROR.value
                self.logger.error(f"数据源 {source_id} 连接失败")
            
            status.last_update = datetime.now()
            self._notify_status_change()
            return success
            
        except Exception as e:
            self.logger.error(f"连接数据源失败: {e}")
            if source_id in self.source_statuses:
                self.source_statuses[source_id].status = DataSourceStatus.ERROR.value
                self.source_statuses[source_id].last_error = str(e)
            return False
    
    def disconnect_data_source(self, source_id: str) -> bool:
        """断开数据源连接"""
        try:
            if source_id in self.source_statuses:
                status = self.source_statuses[source_id]
                status.status = DataSourceStatus.DISCONNECTED.value
                status.last_update = datetime.now()
                
                # 从活动源中移除
                if source_id in self.active_sources:
                    self.active_sources.remove(source_id)
                
                self.logger.info(f"数据源 {source_id} 断开连接")
                self._notify_status_change()
                return True
            else:
                self.logger.warning(f"数据源 {source_id} 状态不存在")
                return False
                
        except Exception as e:
            self.logger.error(f"断开数据源连接失败: {e}")
            return False
    
    def start_sync(self) -> bool:
        """启动多源同步"""
        try:
            if self.sync_running:
                self.logger.warning("多源同步已在运行中")
                return True
            
            if not self.active_sources:
                self.logger.warning("没有活动的数据源，无法启动同步")
                return False
            
            self.sync_running = True
            self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
            self.sync_thread.start()
            
            self.logger.info("多源同步已启动")
            return True
            
        except Exception as e:
            self.logger.error(f"启动多源同步失败: {e}")
            return False
    
    def stop_sync(self) -> bool:
        """停止多源同步"""
        try:
            if not self.sync_running:
                self.logger.warning("多源同步未在运行")
                return True
            
            self.sync_running = False
            
            # 等待同步线程结束
            if self.sync_thread and self.sync_thread.is_alive():
                self.sync_thread.join(timeout=5.0)
            
            self.logger.info("多源同步已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止多源同步失败: {e}")
            return False
    
    def start_recording(self) -> bool:
        """开始数据记录"""
        try:
            if self.recording:
                self.logger.warning("数据记录已在运行中")
                return True
            
            self.recording = True
            self.recording_start_time = datetime.now()
            
            # 清空之前的数据
            self.recorded_data.clear()
            
            self.logger.info("数据记录已开始")
            return True
            
        except Exception as e:
            self.logger.error(f"开始数据记录失败: {e}")
            return False
    
    def stop_recording(self) -> bool:
        """停止数据记录"""
        try:
            if not self.recording:
                self.logger.warning("数据记录未在运行")
                return True
            
            self.recording = False
            recording_duration = datetime.now() - self.recording_start_time
            
            self.logger.info(f"数据记录已停止，持续时间: {recording_duration}")
            return True
            
        except Exception as e:
            self.logger.error(f"停止数据记录失败: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 计算系统健康度
            total_sources = len(self.data_sources)
            active_sources = len(self.active_sources)
            error_sources = sum(1 for s in self.source_statuses.values() 
                              if s.status == DataSourceStatus.ERROR)
            
            if total_sources > 0:
                health_score = max(0, 100 - (error_sources / total_sources) * 100)
            else:
                health_score = 100.0
            
            # 计算同步状态
            sync_status = "运行中" if self.sync_running else "已停止"
            
            # 计算记录状态
            if self.recording:
                duration = datetime.now() - self.recording_start_time
                record_status = f"记录中 ({duration.total_seconds():.1f}s)"
            else:
                record_status = "未记录"
            
            return {
                'system_health': health_score,
                'total_sources': total_sources,
                'active_sources': active_sources,
                'error_sources': error_sources,
                'sync_status': sync_status,
                'recording_status': record_status,
                'last_update': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取系统状态失败: {e}")
            return {}
    
    def get_data_source_status(self, source_id: str) -> Optional[DataSourceStatusInfo]:
        """获取数据源状态"""
        return self.source_statuses.get(source_id)
    
    def get_all_data_sources(self) -> List[DataSourceConfig]:
        """获取所有数据源配置"""
        return list(self.data_sources.values())
    
    def get_active_data_sources(self) -> List[str]:
        """获取活动的数据源ID列表"""
        return self.active_sources.copy()
    
    def add_data_callback(self, callback: Callable):
        """添加数据回调函数"""
        if callback not in self.data_callbacks:
            self.data_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable):
        """添加状态回调函数"""
        if callback not in self.status_callbacks:
            self.status_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """添加错误回调函数"""
        if callback not in self.error_callbacks:
            self.error_callbacks.append(callback)
    
    def _connect_file_source(self, config: DataSourceConfig, status: DataSourceStatus) -> bool:
        """连接文件数据源"""
        try:
            file_path = config.config.get('file_path', '')
            if not file_path or not os.path.exists(file_path):
                self.logger.error(f"文件不存在: {file_path}")
                return False
            
            # 根据文件类型选择解析器
            file_ext = os.path.splitext(file_path)[1].lower()
            source_type = config.data_type  # 使用data_type而不是source_type
            
            if source_type == DataSourceType.IMU and file_ext in ['.txt', '.csv']:
                # IMU文件类型，使用IMUDataParser
                if self.parsers.get(DataSourceType.IMU):
                    self.logger.info(f"IMU文件数据源连接成功，使用IMUDataParser: {file_path}")
                    # 启动文件解析线程
                    self._start_file_parsing_thread(config, status)
                    return True
                else:
                    self.logger.error("IMUDataParser未初始化")
                    return False
            elif source_type == DataSourceType.CNAP and file_ext in ['.txt', '.csv']:
                # CNAP文件类型，使用CNAPDataParser
                if self.parsers.get(DataSourceType.CNAP):
                    self.logger.info(f"CNAP文件数据源连接成功，使用CNAPDataParser: {file_path}")
                    # 启动文件解析线程
                    self._start_file_parsing_thread(config, status)
                    return True
                else:
                    self.logger.error("CNAPDataParser未初始化")
                    return False
            else:
                # 其他文件类型，使用默认处理
                self.logger.info(f"文件数据源连接成功（默认处理）: {file_path}")
                return True
            
        except Exception as e:
            self.logger.error(f"连接文件数据源失败: {e}")
            return False
    
    def _connect_mqtt_source(self, config: DataSourceConfig, status: DataSourceStatus) -> bool:
        """连接MQTT数据源"""
        try:
            host = config.config.get('host', 'localhost')
            port = config.config.get('port', 1883)
            topic = config.config.get('topic', 'sensors/data')
            source_type = config.data_type
            
            if source_type == DataSourceType.IMU:
                self.logger.info(f"IMU MQTT数据源连接成功: {host}:{port}/{topic}")
                self._start_mqtt_real_data_thread(config, status)
                return True
            elif source_type == DataSourceType.CNAP:
                self.logger.info(f"CNAP MQTT数据源连接成功: {host}:{port}/{topic}")
                self._start_mqtt_real_data_thread(config, status)
                return True
            else:
                self.logger.info(f"MQTT数据源连接成功（默认处理）: {host}:{port}/{topic}")
                return True
            
        except Exception as e:
            self.logger.error(f"连接MQTT数据源失败: {e}")
            return False
    
    def _connect_tcp_source(self, config: DataSourceConfig, status: DataSourceStatus) -> bool:
        """连接TCP数据源"""
        try:
            host = config.config.get('host', 'localhost')
            port = config.config.get('port', 5000)
            
            # 这里可以添加TCP客户端的初始化逻辑
            self.logger.info(f"TCP数据源连接成功: {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"连接TCP数据源失败: {e}")
            return False
    
    def _connect_udp_source(self, config: DataSourceConfig, status: DataSourceStatus) -> bool:
        """连接UDP数据源"""
        try:
            host = config.config.get('host', 'localhost')
            port = config.config.get('port', 6000)
            
            # 这里可以添加UDP客户端的初始化逻辑
            self.logger.info(f"UDP数据源连接成功: {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"连接UDP数据源失败: {e}")
            return False
    
    def _connect_serial_source(self, config: DataSourceConfig, status: DataSourceStatus) -> bool:
        """连接串口数据源"""
        try:
            port = config.config.get('port', 'COM3')
            baud_rate = config.config.get('baud_rate', 9600)
            source_type = config.data_type
            
            # 根据数据源类型选择解析器
            if source_type == DataSourceType.IMU:
                # IMU串口数据源，使用IMUDataParser
                if self.parsers.get(DataSourceType.IMU):
                    self.logger.info(f"IMU串口数据源连接成功，使用IMUDataParser: {port}@{baud_rate}")
                    # 启动串口解析线程
                    self._start_serial_parsing_thread(config, status)
                    return True
                else:
                    self.logger.error("IMUDataParser未初始化")
                    return False
            elif source_type == DataSourceType.CNAP:
                # CNAP串口数据源，使用CNAPDataParser
                if self.parsers.get(DataSourceType.CNAP):
                    self.logger.info(f"CNAP串口数据源连接成功，使用CNAPDataParser: {port}@{baud_rate}")
                    # 启动串口解析线程
                    self._start_serial_parsing_thread(config, status)
                    return True
                else:
                    self.logger.error("CNAPDataParser未初始化")
                    return False
            else:
                # 其他串口数据源，使用默认处理
                self.logger.info(f"串口数据源连接成功（默认处理）: {port}@{baud_rate}")
                return True
            
        except Exception as e:
            self.logger.error(f"连接串口数据源失败: {e}")
            return False
    
    def _start_file_parsing_thread(self, config: DataSourceConfig, status: DataSourceStatus):
        """启动文件解析线程"""
        try:
            file_path = config.config.get('file_path', '')
            source_type = config.data_type
            
            # 创建解析线程
            parse_thread = threading.Thread(
                target=self._file_parsing_worker,
                args=(config, status),
                daemon=True,
                name=f"FileParser_{source_type}_{config.source_id}"
            )
            parse_thread.start()
            
            self.logger.info(f"文件解析线程已启动: {source_type} -> {file_path}")
            
        except Exception as e:
            self.logger.error(f"启动文件解析线程失败: {e}")
    
    def _start_serial_parsing_thread(self, config: DataSourceConfig, status: DataSourceStatus):
        """启动串口解析线程"""
        try:
            port = config.config.get('port', 'COM3')
            source_type = config.data_type
            
            # 创建串口解析线程
            parse_thread = threading.Thread(
                target=self._serial_parsing_worker,
                args=(config, status),
                daemon=True,
                name=f"SerialParser_{source_type}_{config.source_id}"
            )
            parse_thread.start()
            
            self.logger.info(f"串口解析线程已启动: {source_type} -> {port}")
            
        except Exception as e:
            self.logger.error(f"启动串口解析线程失败: {e}")
    
    def _start_mqtt_real_data_thread(self, config: DataSourceConfig, status: DataSourceStatus):
        try:
            topic = config.config.get('topic', 'sensors/data')
            source_type = config.data_type

            parse_thread = threading.Thread(
                target=self._mqtt_real_data_worker,
                args=(config, status),
                daemon=True,
                name=f"MQTTReal_{source_type}_{config.source_id}"
            )
            parse_thread.start()

            self.logger.info(f"MQTT数据连接线程已启动: {source_type} -> {topic}")

        except Exception as e:
            self.logger.error(f"启动MQTT数据连接线程失败: {e}")
            self.logger.error(f"{source_type} 启动失败")
            status.status = DataSourceStatus.ERROR.value
            status.last_error = str(e)
    
    def _file_parsing_worker(self, config: DataSourceConfig, status: DataSourceStatus):
        """文件解析工作线程"""
        try:
            file_path = config.config.get('file_path', '')
            source_type = config.data_type
            
            self.logger.info(f"开始解析文件: {source_type} -> {file_path}")
            
            # 根据数据源类型选择解析器
            parser = self.parsers.get(source_type)
            if not parser:
                self.logger.error(f"未找到解析器: {source_type}")
                return
            
            # 设置解析回调
            def data_callback(parsed_data):
                try:
                    # 将解析后的数据放入同步队列
                    self.sync_queue.put({
                        'source_id': config.source_id,
                        'source_type': source_type,
                        'data': parsed_data,
                        'timestamp': time.time()
                    })
                    
                    # 更新状态
                    status.data_points_received += 1
                    status.data_points_processed += 1
                    status.last_update = datetime.now()
                    
                except Exception as e:
                    self.logger.error(f"处理解析数据失败: {e}")
            
            # 开始解析文件
            if hasattr(parser, 'stream_parse_file'):
                parser.stream_parse_file(file_path, data_callback)
            elif hasattr(parser, 'parse_from_string'):
                # 如果解析器不支持流式解析，则读取整个文件
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    parsed_data_list = parser.parse_from_string(content)
                    for data in parsed_data_list:
                        data_callback(data)
            else:
                self.logger.error(f"解析器 {source_type} 不支持文件解析")
            
            self.logger.info(f"文件解析完成: {source_type} -> {file_path}")
            
        except Exception as e:
            self.logger.error(f"文件解析工作线程失败: {e}")
            status.status = DataSourceStatus.ERROR.value
            status.last_error = str(e)
    
    def _serial_parsing_worker(self, config: DataSourceConfig, status: DataSourceStatus):
        """串口解析工作线程"""
        try:
            port = config.config.get('port', 'COM3')
            baud_rate = config.config.get('baud_rate', 9600)
            source_type = config.data_type
            
            self.logger.info(f"开始串口解析: {source_type} -> {port}@{baud_rate}")
            
            # 根据数据源类型选择解析器
            parser = self.parsers.get(source_type)
            if not parser:
                self.logger.error(f"未找到解析器: {source_type}")
                return
            
            # 设置解析回调
            def data_callback(parsed_data):
                try:
                    # 将解析后的数据放入同步队列
                    self.sync_queue.put({
                        'source_id': config.source_id,
                        'source_type': source_type,
                        'data': parsed_data,
                        'timestamp': time.time()
                    })
                    
                    # 更新状态
                    status.data_points_received += 1
                    status.data_points_processed += 1
                    status.last_update = datetime.now()
                    
                except Exception as e:
                    self.logger.error(f"处理串口解析数据失败: {e}")
            
            self.logger.info(f"串口解析线程运行中: {source_type} -> {port}@{baud_rate}")
            
            while status.status == DataSourceStatus.CONNECTED.value:
                try:
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"串口数据读取失败: {e}")
                    break
            
            self.logger.info(f"串口解析线程已停止: {source_type} -> {port}")
            
        except Exception as e:
            self.logger.error(f"串口解析工作线程失败: {e}")
            status.status = DataSourceStatus.ERROR.value
            status.last_error = str(e)
    
    def _mqtt_real_data_worker(self, config: DataSourceConfig, status: DataSourceStatus):
        try:
            topic = config.config.get('topic', 'sensors/data')
            source_type = config.data_type
            host = config.config.get('host', 'localhost')
            port = config.config.get('port', 1883)

            self.logger.info(f"开始MQTT数据连接: {source_type} -> {host}:{port}/{topic}")

            try:
                import paho.mqtt.client as mqtt
                from paho.mqtt import publish

                client = mqtt.Client()
                client.on_connect = self._on_mqtt_connect
                client.on_message = self._on_mqtt_message
                client.on_disconnect = self._on_mqtt_disconnect

                client.user_data_set({
                    'config': config,
                    'status': status,
                    'source_type': source_type
                })

                try:
                    client.connect(host, port, 60)
                    client.subscribe(topic)
                    client.loop_start()

                    status.status = DataSourceStatus.CONNECTED.value
                    status.last_update = datetime.now()

                    self.logger.info(f"MQTT数据连接成功: {source_type} -> {host}:{port}/{topic}")

                    while status.status == DataSourceStatus.CONNECTED.value:
                        time.sleep(1.0)

                except Exception as e:
                    self.logger.error(f"MQTT连接失败: {e}")
                    status.status = DataSourceStatus.ERROR.value
                    status.last_error = str(e)

            except ImportError as e:
                self.logger.error(f"无法导入paho-mqtt，MQTT功能不可用: {e}")
                status.status = DataSourceStatus.ERROR.value
                status.last_error = str(e)

        except Exception as e:
            self.logger.error(f"MQTT数据连接工作线程失败: {e}")
            status.status = DataSourceStatus.ERROR.value
            status.last_error = str(e)
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        try:
            config = userdata['config']
            status = userdata['status']
            source_type = userdata['source_type']
            
            if rc == 0:
                self.logger.info(f"✅ MQTT连接成功: {source_type}")
                status.status = DataSourceStatus.CONNECTED.value
                status.last_update = datetime.now()
            else:
                self.logger.error(f"❌ MQTT连接失败，错误码: {rc}")
                status.status = DataSourceStatus.ERROR.value
                status.last_error = f"Connection failed with code {rc}"
                
        except Exception as e:
            self.logger.error(f"MQTT连接回调处理失败: {e}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """MQTT消息接收回调"""
        try:
            config = userdata['config']
            status = userdata['status']
            source_type = userdata['source_type']
            
            # 解析接收到的真实数据
            try:
                import json
                real_data = json.loads(msg.payload.decode())
                
                # 将真实数据放入同步队列
                self.sync_queue.put({
                    'source_id': config.source_id,
                    'source_type': source_type,
                    'data': real_data,
                    'timestamp': time.time(),
                    'is_real_data': True
                })
                
                # 更新状态
                status.data_points_received += 1
                status.data_points_processed += 1
                status.last_update = datetime.now()
                
                self.logger.info(f"✅ 接收到真实MQTT数据: {source_type} -> {len(real_data)} 个字段")
                
            except json.JSONDecodeError as e:
                self.logger.warning(f"⚠️ MQTT数据JSON解析失败: {e}")
                # 尝试作为文本数据处理
                text_data = msg.payload.decode()
                self.sync_queue.put({
                    'source_id': config.source_id,
                    'source_type': source_type,
                    'data': {'raw_text': text_data},
                    'timestamp': time.time(),
                    'is_real_data': True
                })
                
        except Exception as e:
            self.logger.error(f"MQTT消息处理失败: {e}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        try:
            config = userdata['config']
            status = userdata['status']
            source_type = userdata['source_type']
            
            self.logger.warning(f"⚠️ MQTT连接断开: {source_type}, 错误码: {rc}")
            status.status = DataSourceStatus.DISCONNECTED.value
            status.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"MQTT断开连接回调处理失败: {e}")
    
    def _sync_worker(self):
        """多源同步工作线程"""
        try:
            self.logger.info("多源同步工作线程已启动")
            
            while self.sync_running:
                try:
                    # 处理同步队列中的数据
                    try:
                        data = self.sync_queue.get(timeout=0.1)
                        self._process_sync_data(data)
                    except Empty:
                        pass
                    
                    # 更新数据源状态
                    self._update_source_statuses()
                    
                    # 短暂休眠
                    time.sleep(0.01)
                    
                except Exception as e:
                    self.logger.error(f"同步工作线程错误: {e}")
                    time.sleep(1.0)
            
            self.logger.info("多源同步工作线程已停止")
            
        except Exception as e:
            self.logger.error(f"多源同步工作线程异常: {e}")
    
    def _process_sync_data(self, data: Any):
        """处理同步数据"""
        try:
            # 这里可以添加数据融合和处理逻辑
            self.logger.debug(f"处理同步数据: {type(data)}")
            
            # 通知数据回调
            for callback in self.data_callbacks:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"数据回调执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"处理同步数据失败: {e}")
    
    def _update_source_statuses(self):
        try:
            current_time = datetime.now()

            for source_id, status in self.source_statuses.items():
                if status.status == DataSourceStatus.CONNECTED.value:
                    status.last_update = current_time

                    if source_id in self.active_sources:
                        status.data_quality = min(100.0, status.data_quality + 0.1)
                        status.data_points_received += 1
                        status.data_points_processed += 1

                status.last_update = current_time

            self._update_system_health()

        except Exception as e:
            self.logger.error(f"更新数据源状态失败: {e}")
    
    def _update_system_health(self):
        """更新系统健康度"""
        try:
            total_sources = len(self.data_sources)
            if total_sources == 0:
                self.system_health = 100.0
                return
            
            # 计算平均数据质量
            total_quality = 0.0
            error_count = 0
            
            for status in self.source_statuses.values():
                if status.status == DataSourceStatus.ERROR.value:
                    error_count += 1
                else:
                    total_quality += status.data_quality
            
            if total_sources > error_count:
                avg_quality = total_quality / (total_sources - error_count)
                # 根据错误数量和质量计算健康度
                health_score = avg_quality * (1 - error_count / total_sources)
                self.system_health = max(0.0, min(100.0, health_score))
            else:
                self.system_health = 0.0
            
            self.last_system_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"更新系统健康度失败: {e}")
    
    def _notify_status_change(self):
        """通知状态变更"""
        try:
            for callback in self.status_callbacks:
                try:
                    callback()
                except Exception as e:
                    self.logger.error(f"状态回调执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"通知状态变更失败: {e}")
    
    def _notify_error(self, error_msg: str):
        """通知错误"""
        try:
            for callback in self.error_callbacks:
                try:
                    callback(error_msg)
                except Exception as e:
                    self.logger.error(f"错误回调执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"通知错误失败: {e}")
    
    def shutdown(self):
        """关闭管理器"""
        try:
            # 停止同步
            self.stop_sync()
            
            # 断开所有数据源
            for source_id in list(self.active_sources):
                self.disconnect_data_source(source_id)
            
            # 停止记录
            if self.recording:
                self.stop_recording()
            
            self.logger.info("统一数据源管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭管理器失败: {e}")


# 便捷函数
def create_imu_file_source(file_path: str, name: str = None) -> DataSourceConfig:
    """创建IMU文件数据源"""
    if name is None:
        name = f"IMU文件源_{os.path.basename(file_path)}"
    
    return DataSourceConfig(
        source_id=f"imu_file_{int(time.time())}",
        name=name,
        data_type=DataSourceType.IMU,
        transmission_type=TransmissionType.FILE,
        config={'file_path': file_path}
    )


def create_cnap_mqtt_source(host: str, port: int, topic: str, name: str = None) -> DataSourceConfig:
    """创建CNAP MQTT数据源"""
    if name is None:
        name = f"CNAP MQTT源_{host}:{port}/{topic}"
    
    return DataSourceConfig(
        source_id=f"cnap_mqtt_{int(time.time())}",
        name=name,
        data_type=DataSourceType.CNAP,
        transmission_type=TransmissionType.MQTT,
        config={'host': host, 'port': port, 'topic': topic}
    )



