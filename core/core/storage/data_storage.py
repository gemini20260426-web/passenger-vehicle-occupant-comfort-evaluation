#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版数据存储类，支持多种存储后端和驾驶行为阈值配置管理
"""

import json
import time
import logging
import os
from datetime import datetime
from collections import deque
import tempfile
from typing import Dict, Any, Optional, List
# 尝试导入redis，若失败则设置为None
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
from PySide6.QtCore import Signal, QObject

# 不再使用配置模型类，直接使用字典配置


class DataStorage(QObject):
    """增强版数据存储类，支持多种存储后端和驾驶行为阈值配置管理"""
    
    # 定义信号：传递处理后的数据给UI线程
    data_updated_signal = Signal(dict)  # 普通数据更新
    behavior_event_signal = Signal(dict)  # 行为事件更新
    config_updated_signal = Signal()  # 配置更新信号

    def __init__(self, mysql_handler=None, redis_config: dict = None, influxdb_config: dict = None, data_path: str = 'data/'):
        """
        初始化数据存储
        
        Args:
            mysql_handler: MySQL处理器实例（可选）
            redis_config: Redis连接配置字典
            influxdb_config: InfluxDB连接配置字典
            data_path: 本地数据存储路径
        """
        super().__init__()
        self.logger = logging.getLogger("DataStorage")
        self.data_path = data_path
        self.export_dir = os.path.join(data_path, 'exports')
        self._active_connections = True
        
        # 初始化阈值配置（使用字典）
        self.thresholds = {
            "max_acceleration": 4.0,
            "max_deceleration": -8.0,
            "high_speed_limit": 120.0,
            "low_speed_limit": 20.0
        }

        # 初始化车辆配置（使用字典）
        self.vehicle_config = {
            "vehicle_id": "default",
            "vehicle_type": "car",
            "max_speed": 180.0
        }
        
        # 初始化数据库连接
        self.redis_client = None
        self.mysql_handler = mysql_handler  # 保存MySQLHandler实例
        self.influxdb_client = None
        self._active_connections = True
        self.data_buffer = deque(maxlen=1000)  # 添加数据缓冲区
        
        # 初始化Redis连接
        if redis_config:
            try:
                # 使用RedisManager来管理Redis连接
                from .redis_manager import RedisManager
                self.redis_manager = RedisManager(
                    host=redis_config.get('host', 'localhost'),
                    port=redis_config.get('port', 6379),
                    db=redis_config.get('db', 0)
                )
                if redis_config.get('password'):
                    self.redis_manager.password = redis_config.get('password')
                
                # 尝试连接Redis
                if self.redis_manager.is_connected():
                    self.redis_client = self.redis_manager
                    self.logger.info("Redis连接初始化成功")
                else:
                    self.logger.warning("Redis连接失败，但系统将继续运行")
                    self.redis_client = None
            except Exception as e:
                self.logger.error(f"Redis连接初始化失败: {e}")
                self.redis_client = None
        else:
            self.logger.info("Redis配置不存在，跳过Redis连接初始化")
                
        # 初始化InfluxDB连接
        if influxdb_config:
            try:
                # 使用InfluxDBHandler来管理InfluxDB连接
                from .influxdb_handler import InfluxDBHandler
                self.influxdb_handler = InfluxDBHandler()
                
                # 设置配置
                if influxdb_config.get('url'):
                    self.influxdb_handler.url = influxdb_config.get('url')
                if influxdb_config.get('token'):
                    self.influxdb_handler.token = influxdb_config.get('token')
                if influxdb_config.get('org'):
                    self.influxdb_handler.org = influxdb_config.get('org')
                if influxdb_config.get('bucket'):
                    self.influxdb_handler.bucket = influxdb_config.get('bucket')
                
                # 尝试连接InfluxDB
                if self.influxdb_handler.connect():
                    self.influxdb_client = self.influxdb_handler
                    self.logger.info("InfluxDB连接初始化成功")
                else:
                    self.logger.warning("InfluxDB连接失败，但系统将继续运行")
                    self.influxdb_client = None
            except ImportError:
                self.logger.warning("未安装influxdb-client库，无法初始化InfluxDB连接")
                self.influxdb_client = None
            except Exception as e:
                self.logger.error(f"InfluxDB连接初始化失败: {e}")
                self.influxdb_client = None
        else:
            self.logger.info("InfluxDB配置不存在，跳过InfluxDB连接初始化")

    def close_all_connections(self):
        """关闭所有数据库连接"""
        if not self._active_connections:
            self.logger.info("连接已经关闭，无需操作")
            return

        try:
            # 关闭MySQL连接
            if self.mysql_handler and hasattr(self.mysql_handler, 'disconnect'):
                self.mysql_handler.disconnect()
                self.logger.info("MySQL连接已关闭")
            
            # 关闭Redis连接
            if self.redis_client:
                if hasattr(self.redis_client, 'close'):
                    self.redis_client.close()
                    self.logger.info("Redis连接已关闭")
                elif hasattr(self.redis_client, 'disconnect'):
                    self.redis_client.disconnect()
                    self.logger.info("Redis连接已断开")
                else:
                    self.logger.info("Redis连接关闭方法不可用")
            
            # 关闭InfluxDB连接
            if self.influxdb_client:
                if hasattr(self.influxdb_client, 'close'):
                    self.influxdb_client.close()
                    self.logger.info("InfluxDB连接已关闭")
                elif hasattr(self.influxdb_client, 'disconnect'):
                    self.influxdb_client.disconnect()
                    self.logger.info("InfluxDB连接已断开")
                else:
                    self.logger.info("InfluxDB连接关闭方法不可用")
            
            self._active_connections = False
        except Exception as e:
            self.logger.error(f"关闭数据库连接时发生错误: {e}")
            
        # 确保本地数据存储路径存在
        try:
            os.makedirs(self.data_path, exist_ok=True)
            os.makedirs(self.export_dir, exist_ok=True)
            self.logger.info(f"本地数据存储路径准备就绪: {self.data_path}")
        except Exception as e:
            self.logger.error(f"创建本地数据存储路径失败: {e}")

        # 从存储加载配置
        self.load_config_from_storage()

        self.logger.info("数据存储模块初始化完成")

    def test_connection(self) -> bool:
        """测试数据库连接有效性"""
        try:
            if self.redis_client:
                if not self.redis_client.ping():
                    return False
            if self.mysql_handler:
                return self.mysql_handler.is_connected()
            return True
        except Exception as e:
            self.logger.error(f"连接测试失败: {str(e)}")
            return False

    def update_thresholds(self, new_thresholds: Dict[str, Any]) -> bool:
        """
        更新驾驶行为阈值配置
        
        Args:
            new_thresholds: 新的阈值配置字典
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 更新阈值配置
            updated_config = self.thresholds.copy()
            updated_config.update(new_thresholds)
            self.thresholds = updated_config
            
            # 保存到Redis
            if self.redis_client:
                try:
                    thresholds_json = json.dumps(updated_config)
                    self.redis_client.set("driving_thresholds", thresholds_json)
                except Exception as e:
                    self.logger.warning(f"保存阈值配置到Redis失败: {e}")
            
            # 保存到MySQL
            if self.mysql_handler and self.mysql_handler.is_connected():
                try:
                    query = """
                    INSERT INTO driving_config (config_key, config_value) 
                    VALUES (%s, %s) 
                    ON DUPLICATE KEY UPDATE 
                    config_value = VALUES(config_value), 
                    updated_at = CURRENT_TIMESTAMP
                    """
                    self.mysql_handler.execute_update(query, ("thresholds", json.dumps(updated_config)))
                except Exception as e:
                    self.logger.warning(f"保存阈值配置到MySQL失败: {e}")
            
            # 发射配置更新信号
            self.config_updated_signal.emit()
            self.logger.info("驾驶行为阈值配置更新成功")
            return True
        except Exception as e:
            self.logger.error(f"更新驾驶行为阈值配置失败: {e}")
            return False

    def get_threshold(self, threshold_name: str) -> Optional[Any]:
        """
        获取特定阈值
        
        Args:
            threshold_name: 阈值名称
            
        Returns:
            Optional[Any]: 阈值，如果不存在返回None
        """
        return getattr(self.thresholds, threshold_name, None)

    def get_all_thresholds(self) -> Dict[str, Any]:
        """
        获取所有阈值配置
        
        Returns:
            Dict[str, Any]: 所有阈值配置
        """
        return self.thresholds.copy()

    def update_vehicle_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新车辆配置
        
        Args:
            new_config: 新的车辆配置字典
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 更新车辆配置
            updated_config = self.vehicle_config.copy()
            updated_config.update(new_config)
            self.vehicle_config = updated_config
            
            # 保存到Redis
            if self.redis_client:
                try:
                    config_json = json.dumps(updated_config)
                    self.redis_client.set("vehicle_config", config_json)
                except Exception as e:
                    self.logger.warning(f"保存车辆配置到Redis失败: {e}")
            
            # 保存到MySQL
            if self.mysql_handler and self.mysql_handler.is_connected():
                try:
                    query = """
                    INSERT INTO driving_config (config_key, config_value) 
                    VALUES (%s, %s) 
                    ON DUPLICATE KEY UPDATE 
                    config_value = VALUES(config_value), 
                    updated_at = CURRENT_TIMESTAMP
                    """
                    self.mysql_handler.execute_update(query, ("vehicle", json.dumps(updated_config)))
                except Exception as e:
                    self.logger.warning(f"保存车辆配置到MySQL失败: {e}")
            
            # 发射配置更新信号
            self.config_updated_signal.emit()
            self.logger.info("车辆配置更新成功")
            return True
        except Exception as e:
            self.logger.error(f"更新车辆配置失败: {e}")
            return False

    def load_config_from_storage(self) -> bool:
        """
        从存储中加载配置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            success = False
            # 从Redis加载
            if self.redis_client:
                try:
                    thresholds_json = self.redis_client.get("driving_thresholds")
                    if thresholds_json:
                        thresholds_data = json.loads(thresholds_json)
                        self.thresholds = thresholds_data
                        self.logger.info("从Redis加载阈值配置成功")
                        success = True
                        
                    vehicle_json = self.redis_client.get("vehicle_config")
                    if vehicle_json:
                        vehicle_data = json.loads(vehicle_json)
                        self.vehicle_config = vehicle_data
                        self.logger.info("从Redis加载车辆配置成功")
                        success = True
                except Exception as e:
                    self.logger.warning(f"从Redis加载配置失败: {e}")
            
            # 从MySQL加载
            if self.mysql_handler and self.mysql_handler.is_connected() and not success:
                try:
                    query = "SELECT config_key, config_value FROM driving_config WHERE config_key IN ('thresholds', 'vehicle')"
                    results = self.mysql_handler.execute_query(query)
                    
                    for row in results:
                        config_key = row['config_key']
                        config_value = json.loads(row['config_value'])
                        
                        if config_key == 'thresholds':
                            self.thresholds = config_value
                            self.logger.info("从MySQL加载阈值配置成功")
                            success = True
                        elif config_key == 'vehicle':
                            self.vehicle_config = config_value
                            self.logger.info("从MySQL加载车辆配置成功")
                            success = True
                except Exception as e:
                    self.logger.warning(f"从MySQL加载配置失败: {e}")
            
            return success
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return False

    def store_data(self, data: Dict[str, Any]) -> bool:
        """
        存储数据的统一接口方法
        
        Args:
            data: 要存储的数据字典
            
        Returns:
            bool: 存储是否成功
        """
        # 调用现有的store_driving_data方法来处理数据存储
        return self.store_driving_data(data)
        
    def store_driving_data(self, data: Dict[str, Any]) -> bool:
        """
        存储驾驶数据到Redis和MySQL
        
        Args:
            data: 驾驶数据字典
            
        Returns:
            bool: 存储是否成功
        """
        try:
            # 检查对象是否还存在
            if not hasattr(self, 'logger'):
                self.logger = logging.getLogger(__name__)
                
            # 添加到数据缓冲区
            self.data_buffer.append(data)
            
            # 存储到Redis
            if self.redis_client:
                try:
                    redis_key = "driving_data"
                    self.redis_client.zadd(redis_key, {json.dumps(data): data["timestamp"]})
                    # 限制集合大小，只保留最近的数据
                    self.redis_client.zremrangebyrank(redis_key, 0, -50001)
                except Exception as e:
                    self.logger.warning(f"存储驾驶数据到Redis失败: {e}")
            
            # 存储到MySQL
            if self.mysql_handler and self.mysql_handler.is_connected():
                try:
                    query = """
                    INSERT INTO driving_data (
                        timestamp, speed, acceleration_x, acceleration_y, acceleration_z,
                        gyro_x, gyro_y, gyro_z, wheel_angle, latitude, longitude, behaviors
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    mysql_timestamp = datetime.fromtimestamp(data["timestamp"])
                    behaviors = json.dumps(data.get("behaviors", []))
                    
                    self.mysql_handler.execute_update(
                        query,
                        (
                            mysql_timestamp,
                            data.get("speed", 0),
                            data.get("ax", 0),
                            data.get("ay", 0),
                            data.get("az", 0),
                            data.get("gx", 0),
                            data.get("gy", 0),
                            data.get("gz", 0),
                            data.get("wheel", 0),
                            data.get("latitude", 0),
                            data.get("longitude", 0),
                            behaviors,
                        ),
                    )
                except Exception as e:
                    self.logger.warning(f"存储驾驶数据到MySQL失败: {e}")
            
            # 发射数据更新信号
            try:
                self.data_updated_signal.emit(data)
            except RuntimeError as e:
                if "Internal C++ object" in str(e):
                    self.logger.warning("无法发射信号，DataStorage对象可能已被删除")
                else:
                    raise
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"存储驾驶数据失败: {e}")
            return False

    def store_behavior_event(self, event: Dict[str, Any]) -> bool:
        """
        存储行为事件到MySQL
        
        Args:
            event: 行为事件数据字典
            
        Returns:
            bool: 存储是否成功
        """
        try:
            if self.mysql_handler and self.mysql_handler.is_connected():
                try:
                    query = """
                    INSERT INTO behavior_events (
                        timestamp, speed, behaviors
                    ) VALUES (%s, %s, %s)
                    """

                    behaviors = json.dumps(event["behaviors"])
                    mysql_timestamp = datetime.fromtimestamp(event["timestamp"])

                    self.mysql_handler.execute_update(query, (mysql_timestamp, event["speed"], behaviors))
                    
                    # 发射行为事件信号
                    self.behavior_event_signal.emit(event)
                    return True
                except Exception as e:
                    self.logger.error(f"存储行为事件到MySQL失败: {e}")
                    return False
            return False
        except Exception as e:
            self.logger.error(f"存储行为事件失败: {e}")
            return False

    def close_connections(self):
        """显式关闭所有数据库连接"""
        if hasattr(self, '_active_connections') and self._active_connections:
            try:
                if self.redis_client:
                    self.redis_client.close()
                    self.logger.info('Redis连接已关闭')
                # 不再需要关闭MySQL连接，因为它由MySQLHandler管理
                self._active_connections = False
                self.logger.info('所有数据库连接已关闭')
            except Exception as e:
                self.logger.error(f'连接关闭异常: {str(e)}', exc_info=True)
            finally:
                # 确保资源释放
                self.redis_client = None
                # 不再设置mysql_conn为None，因为不再直接管理它

    def __del__(self):
        self.close_connections()

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的驾驶数据
        
        Returns:
            Optional[Dict[str, Any]]: 最新的驾驶数据，如果没有数据返回None
        """
        try:
            if self.redis_client:
                redis_key = "driving_data"
                latest_data = self.redis_client.zrange(redis_key, -1, -1)
                if latest_data:
                    return json.loads(latest_data[0])
            return None
        except Exception as e:
            self.logger.error(f"获取最新驾驶数据失败: {e}")
            return None

    def export_data(self, start_time: float = None, end_time: float = None) -> Optional[str]:
        """
        导出数据到CSV文件
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            Optional[str]: 导出文件路径，如果导出失败返回None
        """
        try:
            # 获取数据
            data_list = []
            if self.redis_client:
                redis_key = "driving_data"
                if start_time and end_time:
                    # 获取指定时间范围的数据
                    data_list = self.redis_client.zrangebyscore(
                        redis_key, start_time, end_time
                    )
                else:
                    # 获取所有数据
                    data_list = self.redis_client.zrange(redis_key, 0, -1)
            
            if not data_list:
                self.logger.info("没有可导出的数据")
                return None
            
            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(
                self.export_dir, f"driving_data_{timestamp}.json"
            )
            
            # 解析数据
            parsed_data = [json.loads(data) for data in data_list]
            
            # 保存到JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"数据导出成功: {file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"数据导出失败: {e}")
            return None