#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MQTT配置管理器
负责处理MQTT配置的加载、验证和管理
"""

import logging
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

class MQTTConfigManager(QObject):
    """MQTT配置管理器"""
    
    # 配置更新信号
    config_updated = Signal(dict)
    
    def __init__(self, config_manager=None):
        """
        初始化MQTT配置管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._config = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """加载MQTT配置"""
        try:
            if self.config_manager:
                self._config = self.config_manager.get_mqtt_config() or {}
                self.logger.info("MQTT配置加载成功")
            else:
                # 使用默认配置
                self._config = self._get_default_config()
                self.logger.warning("未提供配置管理器，使用默认MQTT配置")
        except Exception as e:
            self.logger.error(f"加载MQTT配置时出错: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认MQTT配置"""
        return {
            "host": "localhost",
            "port": 1883,
            "username": "",
            "password": "",
            "client_id": "vehicle_monitor",
            "keepalive": 60,
            "topic": "vehicle/data",
            "qos": 1,
            "reconnect_interval": 5000,
            "data_topic": "driving/data",
            "control_topic": "vehicle/control",
            "threshold_topic": "alarm/threshold",
            "auto_reconnect": True,
            "max_reconnect_attempts": 0
        }
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取MQTT配置
        
        Returns:
            Dict[str, Any]: MQTT配置字典
        """
        return self._config.copy()
    
    def get(self, key: str, default=None) -> Any:
        """
        获取配置项的值
        
        Args:
            key: 配置项键名
            default: 默认值
            
        Returns:
            配置项的值或默认值
        """
        return self._config.get(key, default)
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """
        更新MQTT配置
        
        Args:
            config: 新的配置字典
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 验证配置
            validated_config = self._validate_config(config)
            
            # 更新配置
            self._config.update(validated_config)
            
            # 保存到配置管理器
            if self.config_manager:
                self.config_manager.update_config("MQTTConfig", validated_config)
            
            # 发送配置更新信号
            self.config_updated.emit(validated_config)
            
            self.logger.info("MQTT配置更新成功")
            return True
        except Exception as e:
            self.logger.error(f"更新MQTT配置时出错: {e}")
            return False
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证MQTT配置
        
        Args:
            config: 配置字典
            
        Returns:
            Dict[str, Any]: 验证后的配置字典
            
        Raises:
            ValueError: 配置验证失败
        """
        validated_config = {}
        
        # 验证主机地址
        host = config.get('host', 'localhost')
        if not isinstance(host, str) or not host:
            raise ValueError("主机地址必须是非空字符串")
        validated_config['host'] = host
        
        # 验证端口
        port = config.get('port', 1883)
        try:
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError("端口号必须在1-65535范围内")
        except (ValueError, TypeError):
            raise ValueError("端口号必须是有效的整数")
        validated_config['port'] = port
        
        # 验证用户名和密码
        username = config.get('username', '')
        password = config.get('password', '')
        validated_config['username'] = str(username) if username else ''
        validated_config['password'] = str(password) if password else ''
        
        # 验证客户端ID
        client_id = config.get('client_id', 'vehicle_monitor')
        if not isinstance(client_id, str) or not client_id:
            raise ValueError("客户端ID必须是非空字符串")
        validated_config['client_id'] = client_id
        
        # 验证保持连接时间
        keepalive = config.get('keepalive', 60)
        try:
            keepalive = int(keepalive)
            if keepalive < 0:
                raise ValueError("保持连接时间不能为负数")
        except (ValueError, TypeError):
            raise ValueError("保持连接时间必须是有效的整数")
        validated_config['keepalive'] = keepalive
        
        # 验证主题
        topic = config.get('topic', 'vehicle/data')
        if not isinstance(topic, str) or not topic:
            raise ValueError("主题必须是非空字符串")
        validated_config['topic'] = topic
        
        # 验证QoS
        qos = config.get('qos', 1)
        try:
            qos = int(qos)
            if qos not in [0, 1, 2]:
                raise ValueError("QoS必须是0、1或2")
        except (ValueError, TypeError):
            raise ValueError("QoS必须是有效的整数")
        validated_config['qos'] = qos
        
        # 验证重连间隔
        reconnect_interval = config.get('reconnect_interval', 5000)
        try:
            reconnect_interval = int(reconnect_interval)
            if reconnect_interval < 0:
                raise ValueError("重连间隔不能为负数")
        except (ValueError, TypeError):
            raise ValueError("重连间隔必须是有效的整数")
        validated_config['reconnect_interval'] = reconnect_interval
        
        # 验证其他主题
        validated_config['data_topic'] = config.get('data_topic', 'driving/data')
        validated_config['control_topic'] = config.get('control_topic', 'vehicle/control')
        validated_config['threshold_topic'] = config.get('threshold_topic', 'alarm/threshold')
        
        # 验证自动重连
        auto_reconnect = config.get('auto_reconnect', True)
        validated_config['auto_reconnect'] = bool(auto_reconnect)
        
        # 验证最大重连尝试次数
        max_reconnect_attempts = config.get('max_reconnect_attempts', 0)
        try:
            max_reconnect_attempts = int(max_reconnect_attempts)
            if max_reconnect_attempts < 0:
                raise ValueError("最大重连尝试次数不能为负数")
        except (ValueError, TypeError):
            raise ValueError("最大重连尝试次数必须是有效的整数")
        validated_config['max_reconnect_attempts'] = max_reconnect_attempts
        
        return validated_config
    
    def reload_config(self) -> None:
        """重新加载配置"""
        self._load_config()
        self.logger.info("MQTT配置重新加载完成")
    
    def reset_to_default(self) -> bool:
        """
        重置为默认配置
        
        Returns:
            bool: 重置是否成功
        """
        default_config = self._get_default_config()
        return self.update_config(default_config)