#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
InfluxDB处理器
处理与InfluxDB的连接和数据操作
"""

import logging
import json
import os
import subprocess
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from PySide6.QtCore import Signal, QObject

# 尝试导入InfluxDB客户端
try:
    from influxdb_client import InfluxDBClient, Point, WriteOptions
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    logging.warning("未安装influxdb-client库，InfluxDB功能将不可用")


class InfluxDBHandler(QObject):
    """InfluxDB处理器，封装所有InfluxDB操作"""
    connection_status_changed = Signal(str, bool)  # component_name, connected

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.logger = logging.getLogger("InfluxDBHandler")
        self.client = None
        self.write_api = None
        self.query_api = None
        self.url = "http://localhost:8086"
        self.token = ""
        self.bucket = "imu-data"
        self.org = "my-org"
        self._connected = False
        
        # InfluxDB服务路径 - 从项目根目录开始计算
        current_file = __file__
        # 从 core/core/storage/influxdb_handler.py 到项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        self.influxdb_path = os.path.join(project_root, "influxdb", "influxd.exe")
        
        # 如果路径不存在，尝试其他可能的路径
        if not os.path.exists(self.influxdb_path):
            # 尝试相对于当前工作目录的路径
            alt_path = os.path.join("influxdb", "influxd.exe")
            if os.path.exists(alt_path):
                self.influxdb_path = os.path.abspath(alt_path)
                self.logger.info(f"使用替代路径: {self.influxdb_path}")
            else:
                self.logger.warning(f"InfluxDB可执行文件未找到，尝试的路径: {self.influxdb_path}")
                self.logger.warning(f"替代路径: {alt_path}")
        
        # 尝试自动启动InfluxDB服务
        self._ensure_influxdb_service_running()

    def _ensure_influxdb_service_running(self):
        """确保InfluxDB服务正在运行"""
        try:
            # 检查InfluxDB服务是否已经在运行
            if self._is_influxdb_running():
                self.logger.info("InfluxDB服务已在运行")
                return
            
            # 检查InfluxDB可执行文件是否存在
            if not os.path.exists(self.influxdb_path):
                self.logger.warning(f"InfluxDB可执行文件不存在: {self.influxdb_path}")
                return
            
            # 启动InfluxDB服务
            self.logger.info("正在启动InfluxDB服务...")
            self._start_influxdb_service()
            
        except Exception as e:
            self.logger.error(f"检查InfluxDB服务状态时出错: {e}")

    def _is_influxdb_running(self) -> bool:
        """检查InfluxDB服务是否正在运行"""
        try:
            # 检查8086端口是否被占用
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    # 检查是否有influxd进程
                    if 'influxd' in proc_name:
                        self.logger.info(f"发现InfluxDB进程: PID {proc_info['pid']}")
                        return True
                    
                    # 检查进程的网络连接
                    try:
                        connections = proc.connections()
                        for conn in connections:
                            if hasattr(conn, 'laddr') and hasattr(conn.laddr, 'port'):
                                if conn.laddr.port == 8086:
                                    self.logger.info(f"发现占用8086端口的进程: PID {proc_info['pid']}, 名称: {proc_name}")
                                    return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            return False
        except Exception as e:
            self.logger.error(f"检查InfluxDB进程时出错: {e}")
            return False

    def _start_influxdb_service(self):
        """启动InfluxDB服务"""
        try:
            # 创建数据目录
            data_dir = os.path.join(os.path.dirname(self.influxdb_path), "data")
            os.makedirs(data_dir, exist_ok=True)
            
            # 启动InfluxDB服务
            startup_cmd = [
                self.influxdb_path,
                "--engine-path", data_dir,
                "--http-bind-address", "localhost:8086",
                "--log-level", "info"
            ]
            
            # 在后台启动服务
            process = subprocess.Popen(
                startup_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            self.logger.info(f"InfluxDB服务启动命令: {' '.join(startup_cmd)}")
            self.logger.info(f"InfluxDB服务进程ID: {process.pid}")
            
            # 等待服务启动
            time.sleep(3)
            
            # 检查服务是否成功启动
            if self._is_influxdb_running():
                self.logger.info("InfluxDB服务启动成功")
            else:
                self.logger.warning("InfluxDB服务可能启动失败，请检查日志")
                
        except Exception as e:
            self.logger.error(f"启动InfluxDB服务失败: {e}")

    def get_influxdb_config(self) -> Dict[str, Any]:
        """
        获取InfluxDB配置
        
        Returns:
            Dict[str, Any]: InfluxDB配置字典
        """
        # 首先尝试从配置管理器获取
        if self.config_manager:
            try:
                influxdb_config = self.config_manager.get_section("InfluxDBConfig")
                if influxdb_config:
                    return influxdb_config
            except Exception as e:
                self.logger.warning(f"从配置管理器获取InfluxDB配置失败: {e}")

        # 然后尝试从本地配置文件获取
        config_file = "config/influxdb_config.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载InfluxDB配置文件 {config_file} 失败: {e}")

        # 返回默认配置
        return {
            "url": self.url,
            "token": self.token,
            "org": self.org,
            "bucket": self.bucket
        }

    def connect(self) -> bool:
        """
        连接到InfluxDB
        
        Returns:
            bool: 连接是否成功
        """
        if not INFLUXDB_AVAILABLE:
            self.logger.error("InfluxDB客户端库未安装")
            return False

        try:
            # 获取配置
            config = self.get_influxdb_config()
            
            # 创建客户端
            self.client = InfluxDBClient(
                url=config["url"],
                token=config["token"],
                org=config["org"],
                timeout=config.get("timeout", 30) * 1000,  # 转换为毫秒
                verify_ssl=config.get("verify_ssl", True)
            )
            
            # 检查连接
            health = self.client.health()
            if health.status == "pass":
                self._connected = True
                self.bucket = config.get("bucket", "imu-data")
                self.org = config.get("org", "my-org")
                
                # 初始化API
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
                self.query_api = self.client.query_api()
                
                self.logger.info(f"InfluxDB连接成功: {config['url']}")
                self.connection_status_changed.emit("InfluxDB", True)
                return True
            else:
                self.logger.error(f"InfluxDB健康检查失败: {health.message}")
                return False
                
        except Exception as e:
            self.logger.error(f"InfluxDB连接失败: {e}")
            self._connected = False
            self.connection_status_changed.emit("InfluxDB", False)
            return False

    def disconnect(self):
        """断开InfluxDB连接"""
        try:
            if self.client:
                self.client.close()
                self.client = None
                self.write_api = None
                self.query_api = None
            self._connected = False
            self.logger.info("InfluxDB连接已断开")
            self.connection_status_changed.emit("InfluxDB", False)
        except Exception as e:
            self.logger.error(f"断开InfluxDB连接时出错: {e}")
    
    def close(self):
        """关闭InfluxDB连接（兼容性方法）"""
        self.disconnect()

    def is_connected(self) -> bool:
        """
        检查InfluxDB连接状态
        
        Returns:
            bool: 是否已连接
        """
        if not self._connected or not self.client:
            return False
            
        try:
            health = self.client.health()
            return health.status == "pass"
        except Exception as e:
            self.logger.error(f"检查InfluxDB连接状态时出错: {e}")
            return False

    def write_data(self, measurement: str, fields: Dict[str, Any], tags: Optional[Dict[str, str]] = None, 
                   timestamp: Optional[datetime] = None) -> bool:
        """
        写入数据到InfluxDB
        
        Args:
            measurement: 测量名称
            fields: 字段数据
            tags: 标签数据
            timestamp: 时间戳
            
        Returns:
            bool: 写入是否成功
        """
        if not self.is_connected() and not self.connect():
            return False
            
        try:
            # 创建数据点
            point = Point(measurement)
            
            # 添加字段
            for field_name, field_value in fields.items():
                point.field(field_name, field_value)
                
            # 添加标签
            if tags:
                for tag_name, tag_value in tags.items():
                    point.tag(tag_name, tag_value)
                    
            # 添加时间戳
            if timestamp:
                point.time(timestamp)
            else:
                point.time(datetime.now(timezone.utc))
                
            # 写入数据
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True
        except Exception as e:
            self.logger.error(f"写入InfluxDB数据时出错: {e}")
            return False

    def test_connection(self) -> bool:
        """
        测试InfluxDB连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 尝试连接
            success = self.connect()
            if success:
                # 执行简单查询测试
                try:
                    query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -1m)
                        |> limit(n: 1)
                    '''
                    tables = self.query_api.query(query, org=self.org)
                    self.disconnect()
                    return True
                except Exception as e:
                    self.logger.warning(f"查询测试失败: {e}")
                    # 即使查询失败，连接成功也算测试通过
                    self.disconnect()
                    return True
            return False
        except Exception as e:
            self.logger.error(f"测试InfluxDB连接失败: {e}")
            return False

    def query_imu_data(self, start_time: str = "-1h", limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询IMU数据
        
        Args:
            start_time: 开始时间，例如 "-1h", "-30m"
            limit: 限制返回的数据条数
            
        Returns:
            List[Dict[str, Any]]: IMU数据列表
        """
        if not self.is_connected() and not self.connect():
            return []
            
        try:
            # 构建查询语句
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_time})
                |> limit(n: {limit})
            '''
            
            # 执行查询
            tables = self.query_api.query(query, org=self.org)
            
            # 解析结果
            data_list = []
            for table in tables:
                for record in table.records:
                    # 将记录转换为字典
                    data = {
                        "timestamp": record.get_time().timestamp(),
                        "measurement": record.get_measurement(),
                        "_field": record.get_field(),
                        "_value": record.get_value()
                    }
                    
                    # 添加标签
                    for key, value in record.values.items():
                        if key not in ["_time", "_measurement", "_field", "_value"]:
                            data[key] = value
                            
                    data_list.append(data)
                    
            return data_list
        except Exception as e:
            self.logger.error(f"查询IMU数据时出错: {e}")
            return []

    def get_data_count(self, time_range: str = "-30d") -> int:
        """
        获取指定时间范围内的数据记录总数
        
        Args:
            time_range: 时间范围，例如 "-30d"
            
        Returns:
            int: 数据记录总数
        """
        if not self.is_connected() and not self.connect():
            return 0
            
        try:
            # 构建计数查询语句
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {time_range})
                |> count()
            '''
            
            # 执行查询
            tables = self.query_api.query(query, org=self.org)
            
            # 解析结果
            count = 0
            for table in tables:
                for record in table.records:
                    count += record.get_value() if record.get_value() else 0
                    
            return count
        except Exception as e:
            self.logger.error(f"获取数据总数时出错: {e}")
            return 0
