#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis管理器
处理与Redis的连接和数据操作
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

# 尝试导入Redis客户端
try:
    import redis
    from redis import ConnectionPool, Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("未安装redis库，Redis功能将不可用")
    # 创建假的类以避免导入错误
    class ConnectionPool:
        pass
    class Redis:
        pass

from PySide6.QtCore import QObject, Signal


class RedisConfig:
    """Redis连接配置"""
    HOST = 'localhost'
    PORT = 6379
    DB = 0


class RedisManager(QObject):
    """Redis消息管理与数据存储（适配630main.py）"""
    connection_status_changed = Signal(str, bool)  # component_name, connected
    error_occurred = Signal(str)                   # 错误信息
    
    def __init__(self, host: str = RedisConfig.HOST, port: int = RedisConfig.PORT, db: int = RedisConfig.DB, password: str = None):
        super().__init__()
        self.logger = logging.getLogger("RedisManager")
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.pool = None
        self._connected = False
        self._init_connection()

    def _init_connection(self):
        """初始化Redis连接池"""
        try:
            connection_kwargs = {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'decode_responses': False  # 保持二进制存储，避免编码问题
            }
            
            # 如果有密码，添加到连接参数
            if self.password:
                connection_kwargs['password'] = self.password
            
            self.pool = ConnectionPool(**connection_kwargs)
            
            # 测试连接
            with Redis(connection_pool=self.pool) as r:
                r.ping()
            
            self._connected = True
            self.connection_status_changed.emit("Redis", True)
            self._init_redis_keys()  # 初始化必要的Redis键
            self.logger.info(f"Redis连接成功: {self.host}:{self.port}")
        except redis.RedisError as e:
            self.logger.error(f"Redis连接失败: {e}")
            self._connected = False
            self.connection_status_changed.emit("Redis", False)
            self.error_occurred.emit(f"Redis连接失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"Redis连接初始化异常: {e}")
            self._connected = False
            self.connection_status_changed.emit("Redis", False)
            self.error_occurred.emit(f"Redis连接初始化异常: {str(e)}")

    def _init_redis_keys(self):
        """初始化Redis键（确保原始数据和行为数据的哈希表存在）"""
        try:
            with Redis(connection_pool=self.pool) as r:
                r.hsetnx('imu_raw_data', 'init', '0')  # 原始IMU数据
                r.hsetnx('behavior_events', 'init', '0')  # 行为事件数据
        except redis.RedisError as e:
            self.logger.error(f"Redis初始化失败: {e}")
            self.error_occurred.emit(f"Redis初始化失败: {str(e)}")

    def store_raw_data(self, data: dict):
        """存储原始IMU数据到Redis（键：时间戳，值：JSON字符串）"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法存储原始数据")
            return
            
        try:
            with Redis(connection_pool=self.pool) as r:
                key = str(round(data['timestamp'] * 1000))
                r.hset('imu_raw_data', key, json.dumps(data))
        except Exception as e:
            self.logger.error(f"原始数据存储失败: {e}")
            self.error_occurred.emit(f"原始数据存储失败: {str(e)}")

    def store_behavior_event(self, event: dict):
        """存储行为事件数据到Redis（键：时间戳，值：JSON字符串）"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法存储行为事件")
            return
            
        try:
            with Redis(connection_pool=self.pool) as r:
                key = str(round(event['timestamp'] * 1000))
                r.hset('behavior_events', key, json.dumps(event))
        except Exception as e:
            self.logger.error(f"行为事件存储失败: {e}")
            self.error_occurred.emit(f"行为事件存储失败: {str(e)}")

    def store_analysis_result(self, result: dict):
        """存储解析后的驾驶行为分析结果到Redis"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法存储分析结果")
            return
            
        try:
            with Redis(connection_pool=self.pool) as r:
                key = str(round(result['timestamp'] * 1000))  # 使用结果时间戳作为键
                r.hset('analysis_results', key, json.dumps(result))
        except Exception as e:
            self.logger.error(f"分析结果存储失败: {e}")
            self.error_occurred.emit(f"分析结果存储失败: {str(e)}")
            
    def get_raw_data(self, timestamp):
        """根据时间戳获取原始数据"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法获取原始数据")
            return None
            
        try:
            with Redis(connection_pool=self.pool) as r:
                data = r.hget('imu_raw_data', str(int(timestamp * 1000)))
                return json.loads(data) if data else None
        except Exception as e:
            self.logger.error(f"原始数据获取失败: {e}")
            self.error_occurred.emit(f"原始数据获取失败: {str(e)}")
            return None
            
    def get_behavior_event(self, timestamp):
        """根据时间戳获取行为事件"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法获取行为事件")
            return None
            
        try:
            with Redis(connection_pool=self.pool) as r:
                event = r.hget('behavior_events', str(int(timestamp * 1000)))
                return json.loads(event) if event else None
        except Exception as e:
            self.logger.error(f"行为事件获取失败: {e}")
            self.error_occurred.emit(f"行为事件获取失败: {str(e)}")
            return None
            
    def get_analysis_result(self, timestamp):
        """根据时间戳获取分析结果"""
        if not self._connected:
            self.logger.warning("Redis未连接，无法获取分析结果")
            return None
            
        try:
            with Redis(connection_pool=self.pool) as r:
                result = r.hget('analysis_results', str(int(timestamp * 1000)))
                return json.loads(result) if result else None
        except Exception as e:
            self.logger.error(f"分析结果获取失败: {e}")
            self.error_occurred.emit(f"分析结果获取失败: {str(e)}")
            return None

    def is_connected(self):
        """检查Redis连接状态"""
        return self._connected
    
    def disconnect(self):
        """断开Redis连接"""
        try:
            if self.pool:
                self.pool.disconnect()
                self._connected = False
                self.connection_status_changed.emit("Redis", False)
                self.logger.info("Redis连接已断开")
        except Exception as e:
            self.logger.error(f"断开Redis连接时出错: {e}")
    
    def close(self):
        """关闭Redis连接（兼容性方法）"""
        self.disconnect()

    def get_data_statistics(self) -> Dict[str, Any]:
        """
        获取Redis中存储的数据统计信息
        
        Returns:
            Dict[str, Any]: 数据统计信息
        """
        try:
            if not self.is_connected():
                self.logger.error("Redis未连接，无法获取数据统计信息")
                return {}
                
            # 获取最新的数据时间戳
            latest_timestamp = self.redis_client.get("latest_data_timestamp")
            
            # 获取数据计数器
            data_count = self.redis_client.get("data_count")
            
            stats = {
                "latest_timestamp": latest_timestamp.decode('utf-8') if latest_timestamp else None,
                "data_count": int(data_count) if data_count else 0
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"获取Redis数据统计信息时出错: {e}")
            return {}
