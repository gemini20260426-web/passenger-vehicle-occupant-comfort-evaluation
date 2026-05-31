#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
InfluxDB数据读取器
从InfluxDB读取IMU数据
"""

import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta

# 使用相对导入方式
from .data_reader import DataReader
from ..storage.influxdb_handler import InfluxDBHandler
from .data_parser import IMUDataParser


class InfluxDBDataReader(DataReader):
    """InfluxDB数据读取器，用于从InfluxDB读取IMU数据"""
    
    def __init__(self, config_manager=None):
        """
        初始化InfluxDB数据读取器
        
        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.influxdb_handler = InfluxDBHandler(config_manager)
        self._is_reading = False
        self._read_thread = None
        self._last_query_time = None
        self.imu_parser = IMUDataParser()  # 添加IMU数据解析器
        
    def set_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        设置数据回调函数
        
        Args:
            callback: 数据回调函数
        """
        self.data_callback = callback
        # 设置IMU解析器的回调
        self.imu_parser.set_callback(callback)
        
    def set_logger(self, logger_callback: Callable[[str], None]) -> None:
        """
        设置日志回调函数
        
        Args:
            logger_callback: 日志回调函数
        """
        self.logger_callback = logger_callback
        
    def start(self) -> bool:
        """
        开始读取数据
        
        Returns:
            bool: 启动是否成功
        """
        try:
            if not self.influxdb_handler.connect():
                self.logger.error("无法连接到InfluxDB")
                if self.logger_callback:
                    self.logger_callback("无法连接到InfluxDB")
                return False
                
            self._is_reading = True
            # 使用线程方式读取数据
            self._read_thread = threading.Thread(target=self._read_data_loop, daemon=True)
            self._read_thread.start()
            self.logger.info("InfluxDB数据读取器启动成功")
            if self.logger_callback:
                self.logger_callback("InfluxDB数据读取器启动成功")
            return True
        except Exception as e:
            self.logger.error(f"启动InfluxDB数据读取器时出错: {e}")
            if self.logger_callback:
                self.logger_callback(f"启动InfluxDB数据读取器时出错: {e}")
            return False
            
    def _read_data_loop(self):
        """读取数据循环"""
        try:
            self._last_query_time = datetime.utcnow() - timedelta(hours=1)  # 初始查询最近1小时的数据
            
            while self._is_reading:
                try:
                    # 查询新数据（查询最近5分钟的数据）
                    data_list = self.influxdb_handler.query_imu_data(start_time="-5m")
                    
                    if data_list:
                        # 使用IMU解析器处理数据
                        self.imu_parser.parse_and_send(data_list)
                            
                    # 等待一段时间再查询
                    time.sleep(2)  # 每2秒查询一次
                except Exception as e:
                    self.logger.error(f"读取InfluxDB数据时出错: {e}")
                    if self.logger_callback:
                        self.logger_callback(f"读取InfluxDB数据时出错: {e}")
                    time.sleep(5)  # 出错时等待更长时间
                    
        except Exception as e:
            self.logger.error(f"InfluxDB数据读取循环出错: {e}")
            if self.logger_callback:
                self.logger_callback(f"InfluxDB数据读取循环出错: {e}")
                
    def stop(self) -> bool:
        """
        停止读取数据
        
        Returns:
            bool: 停止是否成功
        """
        try:
            self._is_reading = False
            
            if self._read_thread and self._read_thread.is_alive():
                self._read_thread.join(timeout=5)  # 等待线程结束，最多等待5秒
                
            self.influxdb_handler.disconnect()
            self.logger.info("InfluxDB数据读取器已停止")
            if self.logger_callback:
                self.logger_callback("InfluxDB数据读取器已停止")
            return True
        except Exception as e:
            self.logger.error(f"停止InfluxDB数据读取器时出错: {e}")
            if self.logger_callback:
                self.logger_callback(f"停止InfluxDB数据读取器时出错: {e}")
            return False
            
    def is_running(self) -> bool:
        """
        检查读取器是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._is_reading and (self._read_thread is None or self._read_thread.is_alive())

    def get_data_count(self, time_range: str = "-30d") -> int:
        """
        获取数据记录总数
        
        Args:
            time_range: 时间范围，例如 "-30d"
            
        Returns:
            int: 数据记录总数
        """
        try:
            return self.influxdb_handler.get_data_count(time_range)
        except Exception as e:
            self.logger.error(f"获取InfluxDB数据总数时出错: {e}")
            return 0