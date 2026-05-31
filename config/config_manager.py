#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理器
负责管理系统的所有配置项
"""

import os
import json
import logging
import time
import configparser
from typing import Dict, Any, Optional, List
from configparser import ConfigParser

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                               QComboBox, QFormLayout, QGroupBox, QFileDialog,
                               QSpinBox, QDoubleSpinBox, QLineEdit, QTableWidget, QTableWidgetItem,
                               QFrame, QSplitter, QProgressBar, QStackedWidget, QTabWidget,
                               QScrollArea, QCheckBox, QMessageBox, QHeaderView)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject

# 添加MQTTConfigManager导入
from config.mqtt_config_manager import MQTTConfigManager

# 尝试导入数据处理相关模块，如果失败则设置为None
try:
    from core.core.data_processing.data_reader import FileDataReader
except ImportError as e:
    FileDataReader = None
    print(f"警告: 无法导入FileDataReader模块: {e}")

try:
    from communication.mqtt_client import MQTTClient
except ImportError as e:
    MQTTClient = None
    print(f"警告: 无法导入MQTTClient模块: {e}")

try:
    from core.core.data_processing.data_parser import IMUDataParser
except ImportError as e:
    IMUDataParser = None
    print(f"警告: 无法导入IMUDataParser模块: {e}")

try:
    from core.core.analysis.base_analyzer import BasicDrivingAnalyzer
except ImportError as e:
    BasicDrivingAnalyzer = None
    print(f"警告: 无法导入BasicDrivingAnalyzer模块: {e}")

try:
    from core.core.storage.data_storage import DataStorage
except ImportError as e:
    DataStorage = None
    print(f"警告: 无法导入DataStorage模块: {e}")

try:
    from core.core.data_processing.buffer_manager import BufferManager
except ImportError as e:
    BufferManager = None
    print(f"警告: 无法导入BufferManager模块: {e}")

try:
    from core.core.data_processing.proto_serial_reader import ProtoSerialDataReader
except ImportError as e:
    ProtoSerialDataReader = None
    print(f"警告: 无法导入ProtoSerialDataReader模块: {e}")

# 尝试导入配置管理器，如果不存在则跳过
try:
    from config.evaluation_config_manager import RedisConfig, MySQLConfig
except ImportError:
    RedisConfig = None
    MySQLConfig = None

# 修复security_manager导入路径
try:
    from modules.security.security_manager import SecurityManager
except ImportError as e:
    SecurityManager = None
    print(f"警告: 无法导入SecurityManager模块: {e}")

# 配置日志
from config.logging_setup import get_logger
logger = get_logger(__name__)

class ConfigManager(QObject):
    """统一配置管理器"""
    _instance = None  # 单例实例

    @staticmethod
    def instance(config_dir='config/', security_manager=None):
        if ConfigManager._instance is None:
            ConfigManager._instance = ConfigManager(config_dir, security_manager)
        return ConfigManager._instance

    config_updated = Signal(str, dict)  # 配置更新信号 (配置名, 配置数据)
    config_error = Signal(str, str)     # 配置项名称, 错误信息
    
    # 默认配置
    DEFAULT_CONFIGS = {
        "GeneralConfig": {
            "app_name": "车辆智能监控系统",
            "version": "1.0.0",
            "auto_connect": True,
            "log_level": "INFO",
            "data_refresh_interval": 1000,
            "backup_interval": 24,
            "max_backup_count": 30
        },
        "MySQLConfig": {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "62215587",
            "database": "driving_data",
            "connect_timeout": 5,
            "pool_size": 5,
            "charset": "utf8mb4"
        },
        "RedisConfig": {
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0,
            "timeout": 10,
            "max_connections": 10
        },
        "MQTTConfig": {
            "host": "localhost",
            "port": 1883,
            "username": "admin",
            "password": "public",
            "client_id": "vehicle_monitor",
            "keepalive": 60,
            "topic": "vehicle/data",
            "qos": 1,
            "reconnect_interval": 5000
        },
        "SerialConfig": {
            "port": "COM4",
            "baudrate": 921600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1
        },
        "UIConfig": {
            "theme": "default",
            "language": "zh_CN",
            "window_width": 1200,
            "window_height": 800
        },
        "AnalysisConfig": {
            "anomaly_sensitivity": 0.8,
            "window_size": 20,
            "smoothing_window": 10,
            "speed_window": 10
        },
        "InfluxDBConfig": {
            "url": "http://localhost:8086",
            "token": "5dOXj9__rRfZ0PSkKCbwyOdXxF_AdGS5iwAJMHTW0HaYJvrkSxxU9fsklEpuw6MPX-RT_gXOKHJhns2-ZlDTbw==",
            "org": "my-org",
            "bucket": "imu-data"
        },
        "CNAPConfig": {
            "file_path": "data/cnap/physiological_data.csv",
            "sync_with": "imu_source",
            "sample_rate": 100,
            "buffer_size": 1000
        },
        "MultiSourceSyncConfig": {
            "enabled": True,
            "sources": [
                {
                    "type": "mqtt",
                    "config": {
                        "host": "localhost",
                        "port": 1883,
                        "topics": ["vehicle/data"]
                    }
                },
                {
                    "type": "serial",
                    "config": {
                        "port": "COM4",
                        "baudrate": 921600
                    }
                }
            ],
            "sync_interval": 5,
            "anomaly_detection": True,
            "anomaly_threshold": 0.1,
            "anomaly_window": 100,
            "time_alignment": True,
            "data_fusion": True,
            "quality_assessment": True
        }
    }
    
    def __init__(self, config_dir='config/', security_manager=None):
        """
        初始化统一配置管理器
        
        Args:
            config_dir: 配置文件目录
            security_manager: 安全管理器实例
        """
        # 只有在首次初始化时才执行主要逻辑
        if ConfigManager._instance is None:
            super().__init__()
            self.logger = logging.getLogger("ConfigManager")
            # 记录配置管理器实例ID以便追踪
            self.instance_id = id(self)
            self.logger.info(f"创建ConfigManager实例: {self.instance_id}")
            
            # 确保配置目录是绝对路径
            self.config_dir = os.path.abspath(config_dir) if not os.path.isabs(config_dir) else config_dir
            self.logger.info(f"配置目录: {self.config_dir}")
            
            # 确保配置目录存在
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
                
            self.configs = {} # 确保configs在任何情况下都已初始化
            self._load_all_configs()
            
            # 初始化安全管理器
            self.security_manager = security_manager
            if security_manager is None:
                # 延迟导入SecurityManager以避免循环依赖
                try:
                    from modules.security.security_manager import SecurityManager
                    self.security_manager = SecurityManager(config_manager=self)
                except ImportError:
                    self.logger.warning("无法导入SecurityManager，安全性功能可能受限")
                    self.security_manager = None
            ConfigManager._instance = self # 将当前实例设置为单例
        else:
            # 如果不是首次初始化，但仍通过__init__调用（不推荐），则确保基本属性存在
            if not hasattr(self, 'configs'):
                self.configs = {}
            if not hasattr(self, 'logger'):
                self.logger = logging.getLogger("ConfigManager")
            # print("ConfigManager 尝试重复初始化，跳过主要逻辑") # Debug print

    def _load_all_configs(self):
        """加载所有配置，优先使用config.ini中的配置"""
        # 首先加载config.ini（如果存在）
        ini_path = os.path.join(self.config_dir, "config.ini")
        if os.path.exists(ini_path):
            self._load_ini_config(ini_path)
            self.logger.info("成功加载config.ini配置文件")
        else:
            self.logger.info("config.ini不存在，将使用默认配置")
        
        # 加载真实数据模式配置
        real_data_config_path = os.path.join(self.config_dir, "real_data_mode.json")
        if os.path.exists(real_data_config_path):
            try:
                with open(real_data_config_path, 'r', encoding='utf-8') as f:
                    real_data_config = json.load(f)
                
                # 将真实数据配置合并到主配置中
                if "data_sources" in real_data_config:
                    for source_name, source_config in real_data_config["data_sources"].items():
                        config_key = f"{source_name.upper()}Config"
                        self.configs[config_key] = source_config
                        self.logger.info(f"从real_data_mode.json加载{config_key}配置")
                
                # 设置系统模式
                if "system_mode" in real_data_config:
                    self.configs["SystemMode"] = real_data_config["system_mode"]
                    self.logger.info(f"系统模式设置为: {real_data_config['system_mode']}")
                    
            except Exception as e:
                self.logger.error(f"加载real_data_mode.json失败: {e}")
        
        # 加载文件数据源配置
        file_data_config_path = os.path.join(self.config_dir, "file_data_source_config.json")
        if os.path.exists(file_data_config_path):
            try:
                with open(file_data_config_path, 'r', encoding='utf-8') as f:
                    file_data_config = json.load(f)
                
                # 将文件数据源配置合并到主配置中
                if "data_sources" in file_data_config:
                    for source_name, source_config in file_data_config["data_sources"].items():
                        config_key = f"{source_name.upper()}Config"
                        self.configs[config_key] = source_config
                        self.logger.info(f"从file_data_source_config.json加载{config_key}配置")
                
                # 设置系统模式
                if "system_mode" in file_data_config:
                    self.configs["SystemMode"] = file_data_config["system_mode"]
                    self.logger.info(f"系统模式设置为: {file_data_config['system_mode']}")
                    
            except Exception as e:
                self.logger.error(f"加载file_data_source_config.json失败: {e}")
        
        # 然后加载system_config.json（如果config.ini中没有对应配置）
        system_config_path = os.path.join(self.config_dir, "system_config.json")
        if os.path.exists(system_config_path):
            try:
                with open(system_config_path, 'r', encoding='utf-8') as f:
                    system_configs = json.load(f)
                
                # 只有当config.ini中没有对应配置时才使用system_config.json中的配置
                for config_name, config_data in system_configs.items():
                    if config_name not in self.configs:
                        self.configs[config_name] = config_data
                        self.logger.info(f"从system_config.json加载{config_name}配置")
            except Exception as e:
                self.logger.error(f"加载system_config.json失败: {e}")
        # 注意：不再显示system_config.json文件不存在的警告，因为这是正常情况
        
        # 填充缺失的默认配置
        for config_name, default_config in self.DEFAULT_CONFIGS.items():
            if config_name not in self.configs:
                self.configs[config_name] = default_config.copy()
                self.logger.info(f"使用默认配置: {config_name}")
    
    def _load_ini_config(self, ini_path: str):
        """从INI文件加载配置"""
        try:
            config = configparser.ConfigParser()
            config.read(ini_path, encoding='utf-8')
            
            # 将INI配置转换为JSON结构
            for section_name in config.sections():
                section = {}
                for key, value in config.items(section_name):
                    # 尝试转换为数字或布尔值
                    try:
                        if '.' in value:
                            # 浮点数
                            section[key] = float(value)
                        elif value.isdigit():
                            # 整数
                            section[key] = int(value)
                        elif value.lower() in ('true', 'false'):
                            # 布尔值
                            section[key] = value.lower() == 'true'
                        else:
                            section[key] = value
                    except ValueError:
                        section[key] = value
                
                self.configs[section_name] = section
            
            self.logger.info(f"从INI文件 {ini_path} 加载配置成功")
        except Exception as e:
            self.logger.error(f"从INI文件加载配置失败: {e}")

    def get_config(self, config_name: str) -> Dict[str, Any]:
        """
        获取配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            配置字典
        """
        return self.configs.get(config_name, {})
    
    def set_config(self, config_name: str, config_data: Dict[str, Any]):
        """
        设置配置
        
        Args:
            config_name: 配置名称
            config_data: 配置数据
        """
        self.configs[config_name] = config_data
        self.config_updated.emit(config_name, config_data)
        self.logger.info(f"配置已更新: {config_name}")
    
    def save_config(self, config_name: str = None):
        """
        保存配置到config.ini文件（使用防抖机制，避免主线程阻塞）
        
        Args:
            config_name: 要保存的配置名称，如果为None则保存所有配置
        """
        if not hasattr(self, '_pending_save_config_name'):
            self._pending_save_config_name = None
        if not hasattr(self, '_save_debounce_timer'):
            self._save_debounce_timer = QTimer(self)
            self._save_debounce_timer.setSingleShot(True)
            self._save_debounce_timer.timeout.connect(self._do_save_config)

        if config_name:
            if self._pending_save_config_name is None:
                self._pending_save_config_name = config_name
        else:
            self._pending_save_config_name = None

        if not self._save_debounce_timer.isActive():
            self._save_debounce_timer.start(150)

    def _do_save_config(self):
        """实际执行配置保存（由防抖定时器触发）"""
        _t0 = time.perf_counter()
        config_name = self._pending_save_config_name
        self._pending_save_config_name = None

        ini_path = os.path.join(self.config_dir, "config.ini")

        config = configparser.ConfigParser()

        if config_name:
            if os.path.exists(ini_path):
                try:
                    config.read(ini_path, encoding='utf-8')
                except Exception as e:
                    self.logger.error(f"读取现有config.ini失败: {e}")
            configs_to_save = {config_name: self.configs.get(config_name, {})}
        else:
            configs_to_save = self.configs

        if not isinstance(configs_to_save, dict):
            self.logger.error(f"configs_to_save 类型错误: {type(configs_to_save)}, 跳过保存")
            return

        for section_name, section_data in configs_to_save.items():
            if not isinstance(section_data, dict):
                continue
            if not config.has_section(section_name):
                config.add_section(section_name)
            for key, value in section_data.items():
                config.set(section_name, key, str(value))

        try:
            with open(ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
            self.logger.info(f"配置已保存到config.ini (耗时: {(time.perf_counter() - _t0)*1000:.1f}ms)")
        except Exception as e:
            self.logger.error(f"保存配置到config.ini失败: {e}")
    
    def save_all_configs_to_ini(self):
        """
        将所有当前配置保存到config.ini文件中
        这个方法确保所有模块的缺省配置都被保存
        """
        self.save_config()

    def get_serial_config(self):
        """获取串口配置"""
        serial_config = self.get_config("SerialConfig")
        if not serial_config:
            # 默认串口配置
            serial_config = {
                "port": "COM9",
                "baudrate": 921600,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "flow_control": "none",
                "timeout": 1
            }
        return serial_config
    
    def get_section(self, section_name):
        """
        获取指定section的配置
        
        Args:
            section_name: section名称
            
        Returns:
            dict: 配置字典
        """
        return self.get_config(section_name)
    
    def set_value(self, section: str, key: str, value: str) -> bool:
        """
        设置单个配置值
        
        Args:
            section: section名称
            key: 配置键名
            value: 配置值
            
        Returns:
            bool: 是否成功
        """
        try:
            if section not in self.configs:
                self.configs[section] = {}
            try:
                if '.' in str(value):
                    self.configs[section][key] = float(value)
                elif str(value).lstrip('-').isdigit():
                    self.configs[section][key] = int(value)
                elif str(value).lower() in ('true', 'false'):
                    self.configs[section][key] = str(value).lower() == 'true'
                else:
                    self.configs[section][key] = value
            except (ValueError, TypeError):
                self.configs[section][key] = value
            return True
        except Exception as e:
            self.logger.error(f"设置配置值失败: {e}")
            return False

    def set_values_batch(self, section: str, values: dict) -> bool:
        """
        批量设置配置值（不逐条写日志，避免主线程I/O阻塞）
        
        Args:
            section: section名称
            values: {key: value} 字典
            
        Returns:
            bool: 是否成功
        """
        try:
            if section not in self.configs:
                self.configs[section] = {}
            for key, value in values.items():
                try:
                    if '.' in str(value):
                        self.configs[section][key] = float(value)
                    elif str(value).lstrip('-').isdigit():
                        self.configs[section][key] = int(value)
                    elif str(value).lower() in ('true', 'false'):
                        self.configs[section][key] = str(value).lower() == 'true'
                    else:
                        self.configs[section][key] = value
                except (ValueError, TypeError):
                    self.configs[section][key] = value
            self.logger.debug(f"批量设置 [{section}] {len(values)} 个配置值")
            return True
        except Exception as e:
            self.logger.error(f"批量设置配置值失败: {e}")
            return False

    def get_value(self, section: str, key: str, default=None):
        """获取单个配置值"""
        return self.get(section, key, default)

    def create_default_config(self):
        """创建默认的分析配置（BasicAnalysisThresholds + BasicAnalysisWindowSizes）"""
        default_thresholds = {
            "small_steering_angle_threshold": 1.0,
            "acceleration_positive_threshold": 0.02,
            "acceleration_negative_threshold": -0.02,
            "steering_angle_turn_threshold": 2.0,
            "z_angular_velocity_turn_threshold": 0.01,
            "skid_acceleration_change_rate_threshold": 0.2,
            "skid_z_angular_velocity_threshold": 0.05,
            "emergency_brake_acceleration_threshold": -2.0,
            "emergency_brake_speed_drop_threshold": 0.05,
            "curve_steering_angle_threshold": 3.0,
            "curve_acceleration_positive_threshold": 0.02,
            "curve_acceleration_negative_threshold": -0.02,
            "curve_z_angular_velocity_speed_ratio_low": 0.0002,
            "curve_z_angular_velocity_speed_ratio_high": 0.002,
            "snake_steering_angle_change_threshold": 3.0,
            "rapid_direction_change_steering_angle_threshold": 3.0,
            "steering_angle_lane_change_threshold": 2.0,
            "x_acceleration_lane_change_threshold": 0.02,
            "large_radius_turn_steering_angle_low": 2.0,
            "large_radius_turn_steering_angle_high": 10.0,
            "large_radius_turn_z_angular_velocity_low": 0.01,
            "large_radius_turn_z_angular_velocity_high": 0.05,
            "u_turn_steering_angle_threshold": 15.0,
            "u_turn_z_angular_velocity_threshold": 0.5,
            "speed_drop_threshold": 0.15,
            "acceleration_change_rate_threshold": 0.1,
            "acc_speed_range": 5.0,
            "acc_acceleration_range": 0.1,
            "a_acc_acceleration_threshold": 0.3,
            "a_acc_speed_range": 10.0,
            "brake_acceleration_low": -0.3,
            "brake_acceleration_high": -0.1,
            "a_brake_acceleration_threshold": -0.5,
            "a_brake_speed_drop_threshold": 0.3,
            "constant_speed_std_threshold": 2.0,
            "constant_speed_accel_threshold": 0.05,
            "parking_speed_threshold": 2.0,
            "parking_accel_threshold": 0.05
        }
        default_windows = {
            "parking_window": 50,
            "constant_speed_straight_window": 10,
            "accelerating_window": 5,
            "decelerating_window": 5,
            "turning_window": 10,
            "emergency_brake_window": 5,
            "u_turn_window": 20,
            "snake_driving_window": 10,
            "rapid_direction_change_window": 5,
            "large_radius_turning_window": 15,
            "normal_acc_window": 10,
            "aggressive_acc_window": 10,
            "normal_brake_window": 10,
            "aggressive_brake_window": 10,
            "lane_changing_window": 15
        }
        self.configs["BasicAnalysisThresholds"] = default_thresholds
        self.configs["BasicAnalysisWindowSizes"] = default_windows
        self.save_config("BasicAnalysisThresholds")
        self.save_config("BasicAnalysisWindowSizes")
        self.logger.info("默认分析配置已创建")
    
    def get(self, section_name, key=None, default=None):
        """
        获取配置值
        
        Args:
            section_name: section名称
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值或配置字典
        """
        section = self.get_config(section_name)
        if key is None:
            return section
        return section.get(key, default)
    
    # 下面是原来ConfigManager类的方法，为了保持兼容性保留
    def _get_default_configs(self):
        """获取默认配置"""
        return self.DEFAULT_CONFIGS
    
    def get_config_file_path(self, config_name):
        """获取配置文件路径"""
        # 保持兼容性，但实际不再使用JSON文件
        return os.path.join(self.config_dir, f"{config_name.lower()}.json")
    
    def get_mysql_config(self):
        """获取MySQL配置"""
        return self.get_config("MySQLConfig")
    
    def get_redis_config(self):
        """获取Redis配置"""
        return self.get_config("RedisConfig")
    
    def get_mqtt_config(self):
        """获取MQTT配置"""
        return self.get_config("MQTTConfig")
    
    def get_ui_config(self):
        """获取UI配置"""
        return self.get_config("UIConfig")
    
    def get_analysis_config(self):
        """获取分析配置"""
        return self.get_config("AnalysisConfig")
    
    def get_pipeline_config(self):
        """获取管道配置"""
        return self.get_config("PipelineConfig")
    
    def get_multi_source_sync_config(self):
        """获取多源异构数据同步配置"""
        return self.get_config("MultiSourceSyncConfig")
    
    def get_all_configs(self):
        """
        获取所有配置
        
        Returns:
            dict: 所有配置的字典
        """
        return self.configs.copy()
    
    def get_influxdb_config(self):
        """获取InfluxDB配置"""
        return self.get_config("InfluxDBConfig")
    
    def load_config_from_file(self, config_name):
        """从文件加载配置（保持兼容性）"""
        return self.get_config(config_name)
    
    def save_config_to_file(self, config_name, config_data):
        """保存配置到文件（保持兼容性）"""
        self.set_config(config_name, config_data)
        self.save_config(config_name)
    
    def update_config(self, config_name, updates):
        """更新配置（保持兼容性）"""
        current_config = self.get_config(config_name)
        current_config.update(updates)
        self.set_config(config_name, current_config)

class DataProcessingPipeline(QObject):
    """数据处理流水线，与配置管理器深度集成"""
    data_processed = Signal(dict)  # 处理后的数据信号
    pipeline_status = Signal(str, bool)  # 流水线状态信号(状态描述, 是否正常)
    error_occurred = Signal(str)  # 错误信号
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.logger = logging.getLogger("DataProcessingPipeline")
        self.config_manager = config_manager
        self.mutex = QMutex()
        
        # 模块实例
        self.buffer_manager = None
        self.data_storage = None
        self.analyzer = None
        self.data_reader = None
        self.parser = IMUDataParser()
        
        # 状态标志
        self.is_running = False
        self.processing_thread = None
        
        # 初始化配置
        self._init_from_config()
        
        # 连接配置更新信号
        self.config_manager.config_updated.connect(self._on_config_updated)
        
        self.logger.info("数据处理流水线初始化完成")

    def _init_from_config(self) -> None:
        """从配置初始化流水线组件"""
        with QMutexLocker(self.mutex):
            # 获取相关配置
            pipeline_config = self.config_manager.get_config("PipelineConfig")
            analysis_config = self.config_manager.get_config("AnalysisConfig")
            redis_config = self.config_manager.get_config("RedisConfig")
            mysql_config = self.config_manager.get_config("MySQLConfig")
            
            # 初始化缓冲区管理器
            self.buffer_manager = BufferManager(
                buffer_size=pipeline_config.get("buffer_size", 50000),
                persist_threshold=pipeline_config.get("persist_threshold", 10000)
            )
            
            # 初始化数据存储
            self.data_storage = DataStorage(
                RedisConfig(**redis_config),
                MySQLConfig(**mysql_config)
            )
            
            # 初始化驾驶行为分析器
            self.analyzer = BasicDrivingAnalyzer(
                thresholds={
                    "max_acceleration": analysis_config.get("hard_acceleration_threshold", 5.0),
                    "max_deceleration": analysis_config.get("hard_brake_threshold", -8.0),
                    "speeding_threshold": analysis_config.get("overspeed_threshold", 120.0),
                    "sharp_turn_threshold": analysis_config.get("sharp_turn_threshold", 3.0)
                },
                vehicle_config={}
            )
            
            # 同步分析器与存储的阈值配置
            self._sync_thresholds()

    def _sync_thresholds(self) -> None:
        """同步分析器与存储的阈值配置"""
        with QMutexLocker(self.mutex):
            storage_thresholds = self.data_storage.get_all_thresholds()
            if storage_thresholds:
                self.analyzer.update_config(thresholds=storage_thresholds)
                self.logger.info("已同步驾驶行为阈值配置")

    @Slot(str, dict)
    def _on_config_updated(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """处理配置更新"""
        with QMutexLocker(self.mutex):
            # 根据更新的配置类型执行相应操作
            if config_name == "PipelineConfig":
                self.logger.info("流水线配置已更新，重新初始化核心组件")
                self._init_from_config()
                
                # 如果正在运行，重启流水线以应用新配置
                if self.is_running:
                    self.stop()
                    QTimer.singleShot(1000, self.start)
                    
            elif config_name == "AnalysisConfig":
                self.logger.info("分析配置已更新，同步阈值")
                new_thresholds = {
                    "max_acceleration": config_data.get("hard_acceleration_threshold", 5.0),
                    "max_deceleration": config_data.get("hard_brake_threshold", -8.0),
                    "speeding_threshold": config_data.get("overspeed_threshold", 120.0),
                    "sharp_turn_threshold": config_data.get("sharp_turn_threshold", 3.0)
                }
                self.analyzer.update_config(thresholds=new_thresholds)
                
            elif config_name in ["MySQLConfig", "RedisConfig"]:
                self.logger.info(f"存储配置({config_name})已更新，重新初始化数据存储")
                redis_config = self.config_manager.get_config("RedisConfig")
                mysql_config = self.config_manager.get_config("MySQLConfig")
                self.data_storage = DataStorage(
                    RedisConfig(**redis_config),
                    MySQLConfig(**mysql_config)
                )
                
            elif config_name in ["SerialConfig", "MQTTConfig"]:
                self.logger.info(f"数据源配置({config_name})已更新，重新初始化读取器")
                if self.data_reader:
                    reader_type = "serial" if config_name == "SerialConfig" else "mqtt"
                    self.setup_reader(reader_type)

    def setup_reader(self, reader_type: str) -> bool:
        """根据配置设置数据读取器"""
        with QMutexLocker(self.mutex):
            try:
                # 停止现有读取器
                if self.data_reader:
                    self.data_reader.stop()
                    
                # 根据类型获取配置
                if reader_type == "serial":
                    config = self.config_manager.get_config("SerialConfig")
                    # 使用ProtoSerialDataReader
                    self.data_reader = ProtoSerialDataReader(
                        port=config.get("port", "COM4"),
                        baudrate=config.get("baudrate", 921600),
                        flow_control=config.get("flow_control", "none")
                    )
                elif reader_type == "mqtt":
                    config = self.config_manager.get_config("MQTTConfig")
                    self.data_reader = MQTTManager()
                    # 设置连接参数
                    self.data_reader.host = config.get("host", "localhost")
                    self.data_reader.port = config.get("port", 1883)
                    self.data_reader.username = config.get("username", "")
                    self.data_reader.password = config.get("password", "")
                    self.data_reader.topic = config.get("topic", "vehicle/data")
                elif reader_type == "file":
                    # 文件读取器不需要特定配置，通过参数指定文件路径
                    self.data_reader = FileDataReader()
                else:
                    raise ValueError(f"不支持的数据读取类型: {reader_type}")
                    
                self.data_reader.set_logger(self.logger.info)
                self.logger.info(f"已设置{reader_type}数据读取器")
                return True
            except Exception as e:
                self.logger.error(f"设置数据读取器失败: {str(e)}")
                self.error_occurred.emit(f"设置数据读取器失败: {str(e)}")
                return False

    def start(self) -> bool:
        """启动数据处理流水线"""
        with QMutexLocker(self.mutex):
            if self.is_running:
                self.logger.warning("流水线已在运行中")
                return False
                
            if not self.data_reader:
                self.logger.error("请先设置数据读取器")
                self.error_occurred.emit("请先设置数据读取器")
                return False
                
            try:
                # 启动读取器并设置数据处理回调
                self.data_reader.start(callback=self._process_data)
                self.is_running = True
                self.pipeline_status.emit("流水线已启动", True)
                self.logger.info("数据处理流水线已启动")
                return True
            except Exception as e:
                self.logger.error(f"启动流水线失败: {str(e)}")
                self.error_occurred.emit(f"启动流水线失败: {str(e)}")
                return False

    def stop(self) -> bool:
        """停止数据处理流水线"""
        with QMutexLocker(self.mutex):
            if not self.is_running:
                self.logger.warning("流水线已停止")
                return False
                
            try:
                if self.data_reader:
                    self.data_reader.stop()
                    
                self.data_storage.close_connections()
                self.buffer_manager.clear_all()
                self.is_running = False
                self.pipeline_status.emit("流水线已停止", False)
                self.logger.info("数据处理流水线已停止")
                return True
            except Exception as e:
                self.logger.error(f"停止流水线失败: {str(e)}")
                self.error_occurred.emit(f"停止流水线失败: {str(e)}")
                return False

    def _process_data(self, raw_data: str) -> None:
        """处理单条数据的完整流程"""
        try:
            # 1. 数据解析
            parsed_data = self.parser.parse_line(raw_data)
            if not parsed_data:
                self.logger.warning("数据解析失败")
                return
                
            # 2. 添加到缓冲区
            self.buffer_manager.add_data(parsed_data)
            
            # 3. 驾驶行为分析
            analysis_result = self.analyzer.analyze_data(parsed_data)
            
            # 4. 数据存储
            self.data_storage.store_driving_data(analysis_result)
            
            # 5. 如果有检测到行为事件，触发事件处理
            if analysis_result.get("behaviors"):
                self._handle_behavior_event(analysis_result)
                
            # 发送处理后的数据信号
            self.data_processed.emit(analysis_result)
                
        except Exception as e:
            error_msg = f"数据处理出错: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _handle_behavior_event(self, event_data: dict) -> None:
        """处理检测到的驾驶行为事件"""
        # 存储行为事件
        self.data_storage.store_behavior_event(event_data)
        
        # 可以在这里添加其他事件处理逻辑，如实时告警等
        self.logger.info(f"检测到驾驶行为事件: {event_data['behaviors']}")

    def get_recent_analysis(self, count: int = 100) -> List[dict]:
        """获取最近的分析结果"""
        with QMutexLocker(self.mutex):
            recent_data = self.buffer_manager.get_recent_data(count)
            return [self.analyzer.analyze_data(data) for data in recent_data]


class SystemIntegrator(QObject):
    """系统集成器，协调配置管理器和数据处理流水线"""
    system_status = Signal(str)  # 系统状态信号
    optimization_complete = Signal(list)  # 优化完成信号
    
    def __init__(self, config_dir: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.logger = logging.getLogger("SystemIntegrator")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager.instance(config_dir)
        
        # 初始化数据处理流水线
        self.data_pipeline = DataProcessingPipeline(self.config_manager)
        
        # 连接信号
        self._connect_signals()
        
        self.logger.info("系统集成器初始化完成")

    def _connect_signals(self) -> None:
        """连接系统组件信号"""
        # 配置更新信号
        self.config_manager.config_updated.connect(
            lambda name, data: self.system_status.emit(f"配置 {name} 已更新")
        )
        self.config_manager.config_error.connect(
            lambda name, err: self.system_status.emit(f"配置 {name} 错误: {err}")
        )
        
        # 流水线信号
        self.data_pipeline.pipeline_status.connect(
            lambda status, ok: self.system_status.emit(f"流水线状态: {status}")
        )
        self.data_pipeline.error_occurred.connect(
            lambda err: self.system_status.emit(f"流水线错误: {err}")
        )

    def start_system(self) -> bool:
        """启动整个系统"""
        self.system_status.emit("正在启动系统...")
        
        # 检查并应用系统优化
        optimizations = self.optimize_system()
        self.optimization_complete.emit(optimizations)
        
        # 启动数据处理流水线
        # 默认使用配置中的首选数据源
        general_config = self.config_manager.get_config("GeneralConfig")
        preferred_reader = general_config.get("preferred_data_source", "serial")
        
        if self.data_pipeline.setup_reader(preferred_reader):
            return self.data_pipeline.start()
        return False

    def stop_system(self) -> bool:
        """停止整个系统"""
        self.system_status.emit("正在停止系统...")
        return self.data_pipeline.stop()

    def optimize_system(self) -> List[str]:
        """系统级优化函数"""
        self.logger.info("开始系统优化...")
        optimizations = []
        
        # 1. 配置优化
        general_config = self.config_manager.get_config("GeneralConfig")
        
        # 调整日志级别以提高性能（生产环境）
        if general_config.get("log_level", "INFO") == "DEBUG":
            self.config_manager.update_config("GeneralConfig", {"log_level": "INFO"})
            optimizations.append("将日志级别从DEBUG调整为INFO以提高性能")
            logging.getLogger().setLevel(logging.INFO)
        
        # 调整数据采集频率（如果设置过高）
        pipeline_config = self.config_manager.get_config("PipelineConfig")
        if pipeline_config.get("batch_size", 100) < 50:
            self.config_manager.update_config("PipelineConfig", {"batch_size": 100})
            optimizations.append("将批处理大小从<50调整为100以减少系统负载")
        
        # 2. 缓冲区优化
        if pipeline_config.get("buffer_size", 50000) > 100000:
            self.config_manager.update_config("PipelineConfig", {"buffer_size": 80000})
            optimizations.append("将缓冲区大小从>100000调整为80000以节省内存")
        
        self.logger.info("系统优化完成，已应用以下优化:")
        for i, opt in enumerate(optimizations, 1):
            self.logger.info(f"{i}. {opt}")
        
        return optimizations


class ConfigWidget(QWidget):
    """配置管理UI组件，增加流水线配置页面"""
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger("ConfigWidget")
        self._init_ui()
        
        # 连接配置更新信号
        self.config_manager.config_updated.connect(self._on_config_updated)
        self.config_manager.config_error.connect(self._on_config_error)
        
        # 加载当前配置
        self._load_all_configs_to_ui()

    def _init_ui(self) -> None:
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 创建各配置页面
        self.general_tab = self._create_general_config_tab()
        self.mysql_tab = self._create_mysql_config_tab()
        self.redis_tab = self._create_redis_config_tab()
        self.influxdb_tab = self._create_influxdb_config_tab()  # 新增InfluxDB配置页面
        self.serial_tab = self._create_serial_config_tab()
        self.mqtt_tab = self._create_mqtt_config_tab()
        self.ui_tab = self._create_ui_config_tab()
        self.pipeline_tab = self._create_pipeline_config_tab()  # 新增流水线配置页
        
        # 添加标签页
        self.tabs.addTab(self.general_tab, "通用配置")
        self.tabs.addTab(self.mysql_tab, "MySQL配置")
        self.tabs.addTab(self.redis_tab, "Redis配置")
        self.tabs.addTab(self.influxdb_tab, "InfluxDB配置")  # 新增InfluxDB配置标签页
        self.tabs.addTab(self.serial_tab, "串口配置")
        self.tabs.addTab(self.mqtt_tab, "MQTT配置")
        self.tabs.addTab(self.ui_tab, "界面配置")
        self.tabs.addTab(self.pipeline_tab, "流水线配置")
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存配置")
        self.restore_btn = QPushButton("恢复默认")
        self.export_btn = QPushButton("导出配置")
        self.import_btn = QPushButton("导入配置")
        
        self.save_btn.clicked.connect(self._on_save_config)
        self.restore_btn.clicked.connect(self._on_restore_default)
        self.export_btn.clicked.connect(self._on_export_config)
        self.import_btn.clicked.connect(self._on_import_config)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.restore_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.import_btn)
        
        # 添加到主布局
        main_layout.addWidget(self.tabs)
        main_layout.addLayout(btn_layout)

    def _create_general_config_tab(self) -> QScrollArea:
        """创建通用配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 应用名称
        self.app_name_input = QLineEdit()
        
        # 首选数据源
        self.preferred_source_combo = QComboBox()
        self.preferred_source_combo.addItems(["serial", "mqtt", "file"])
        
        # 日志级别
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        
        # 自动连接
        self.auto_connect_checkbox = QCheckBox()
        
        # 数据刷新间隔
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(100, 10000)
        self.refresh_interval_spin.setSuffix(" ms")
        
        # 备份间隔
        self.backup_interval_spin = QSpinBox()
        self.backup_interval_spin.setRange(1, 72)
        self.backup_interval_spin.setSuffix(" 小时")
        
        # 最大备份数量
        self.max_backup_spin = QSpinBox()
        self.max_backup_spin.setRange(1, 100)
        self.max_backup_spin.setSuffix(" 个")
        
        # 添加到布局
        layout.addRow("应用名称:", self.app_name_input)
        layout.addRow("首选数据源:", self.preferred_source_combo)
        layout.addRow("日志级别:", self.log_level_combo)
        layout.addRow("启动时自动连接:", self.auto_connect_checkbox)
        layout.addRow("数据刷新间隔:", self.refresh_interval_spin)
        layout.addRow("自动备份间隔:", self.backup_interval_spin)
        layout.addRow("最大备份数量:", self.max_backup_spin)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_redis_config_tab(self) -> QScrollArea:
        """创建Redis配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 主机地址
        self.redis_host_input = QLineEdit()
        
        # 端口
        self.redis_port_spin = QSpinBox()
        self.redis_port_spin.setRange(1, 65535)
        self.redis_port_spin.setValue(6379)
        
        # 密码
        self.redis_password_input = QLineEdit()
        self.redis_password_input.setEchoMode(QLineEdit.Password)
        
        # 数据库编号
        self.redis_db_spin = QSpinBox()
        self.redis_db_spin.setRange(0, 15)
        self.redis_db_spin.setValue(0)
        
        # 超时时间
        self.redis_timeout_spin = QSpinBox()
        self.redis_timeout_spin.setRange(1, 60)
        self.redis_timeout_spin.setSuffix(" 秒")
        
        # 添加到布局
        layout.addRow("主机地址:", self.redis_host_input)
        layout.addRow("端口:", self.redis_port_spin)
        layout.addRow("密码:", self.redis_password_input)
        layout.addRow("数据库编号:", self.redis_db_spin)
        layout.addRow("连接超时:", self.redis_timeout_spin)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_mysql_config_tab(self) -> QScrollArea:
        """创建数据库配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 主机地址
        self.mysql_host_input = QLineEdit()
        
        # 端口
        self.mysql_port_spin = QSpinBox()
        self.mysql_port_spin.setRange(1, 65535)
        self.mysql_port_spin.setValue(3306)
        
        # 用户名
        self.mysql_user_input = QLineEdit()
        
        # 密码
        self.mysql_password_input = QLineEdit()
        self.mysql_password_input.setEchoMode(QLineEdit.Password)
        
        # 数据库名
        self.mysql_db_input = QLineEdit()
        
        # 连接超时
        self.mysql_timeout_spin = QSpinBox()
        self.mysql_timeout_spin.setRange(1, 60)
        self.mysql_timeout_spin.setSuffix(" 秒")
        
        # 连接池大小
        self.mysql_pool_spin = QSpinBox()
        self.mysql_pool_spin.setRange(1, 20)
        self.mysql_pool_spin.setSuffix(" 个连接")
        
        # 添加到布局
        layout.addRow("主机地址:", self.mysql_host_input)
        layout.addRow("端口:", self.mysql_port_spin)
        layout.addRow("用户名:", self.mysql_user_input)
        layout.addRow("密码:", self.mysql_password_input)
        layout.addRow("数据库名:", self.mysql_db_input)
        layout.addRow("连接超时:", self.mysql_timeout_spin)
        layout.addRow("连接池大小:", self.mysql_pool_spin)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_influxdb_config_tab(self) -> QScrollArea:  # 新增InfluxDB配置页面
        """创建InfluxDB配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # URL地址
        self.influxdb_url_input = QLineEdit()
        
        # Token
        self.influxdb_token_input = QLineEdit()
        self.influxdb_token_input.setEchoMode(QLineEdit.Password)
        
        # 组织
        self.influxdb_org_input = QLineEdit()
        
        # Bucket
        self.influxdb_bucket_input = QLineEdit()
        
        # 添加到布局
        layout.addRow("URL地址:", self.influxdb_url_input)
        layout.addRow("Token:", self.influxdb_token_input)
        layout.addRow("组织:", self.influxdb_org_input)
        layout.addRow("Bucket:", self.influxdb_bucket_input)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_pipeline_config_tab(self) -> QScrollArea:
        """创建流水线配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 缓冲区大小
        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(1000, 200000)
        self.buffer_size_spin.setSuffix(" 条记录")
        
        # 持久化阈值
        self.persist_threshold_spin = QSpinBox()
        self.persist_threshold_spin.setRange(1000, 50000)
        self.persist_threshold_spin.setSuffix(" 条记录")
        
        # 处理线程数
        self.processing_threads_spin = QSpinBox()
        self.processing_threads_spin.setRange(1, 8)
        self.processing_threads_spin.setSuffix(" 个线程")
        
        # 批处理大小
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 1000)
        self.batch_size_spin.setSuffix(" 条/批")
        
        # 实时分析开关
        self.real_time_analysis_checkbox = QCheckBox()
        
        # 数据缓存开关
        self.data_caching_checkbox = QCheckBox()
        
        # 缓存过期时间
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(60, 86400)
        self.cache_ttl_spin.setSuffix(" 秒")
        
        # 添加到布局
        layout.addRow("缓冲区大小:", self.buffer_size_spin)
        layout.addRow("持久化阈值:", self.persist_threshold_spin)
        layout.addRow("处理线程数:", self.processing_threads_spin)
        layout.addRow("批处理大小:", self.batch_size_spin)
        layout.addRow("启用实时分析:", self.real_time_analysis_checkbox)
        layout.addRow("启用数据缓存:", self.data_caching_checkbox)
        layout.addRow("缓存过期时间:", self.cache_ttl_spin)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_serial_config_tab(self) -> QScrollArea:
        """创建串口配置页面"""
        # 实现串口配置UI（省略具体实现，与其他配置页类似）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        widget = QWidget()
        layout = QFormLayout(widget)
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_mqtt_config_tab(self) -> QScrollArea:
        """创建MQTT配置页面"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 主机地址
        self.mqtt_host_input = QLineEdit()
        self.mqtt_host_input.setPlaceholderText("例如: localhost 或 192.168.1.100")
        layout.addRow("主机地址:", self.mqtt_host_input)
        
        # 端口
        self.mqtt_port_spin = QSpinBox()
        self.mqtt_port_spin.setRange(1, 65535)
        self.mqtt_port_spin.setValue(1883)
        layout.addRow("端口:", self.mqtt_port_spin)
        
        # 用户名
        self.mqtt_username_input = QLineEdit()
        layout.addRow("用户名:", self.mqtt_username_input)
        
        # 密码
        self.mqtt_password_input = QLineEdit()
        self.mqtt_password_input.setEchoMode(QLineEdit.Password)
        layout.addRow("密码:", self.mqtt_password_input)
        
        # 客户端ID
        self.mqtt_client_id_input = QLineEdit()
        self.mqtt_client_id_input.setPlaceholderText("例如: vehicle_monitor")
        layout.addRow("客户端ID:", self.mqtt_client_id_input)
        
        # 保持连接时间
        self.mqtt_keepalive_spin = QSpinBox()
        self.mqtt_keepalive_spin.setRange(0, 3600)
        self.mqtt_keepalive_spin.setValue(60)
        self.mqtt_keepalive_spin.setSuffix(" 秒")
        layout.addRow("保持连接时间:", self.mqtt_keepalive_spin)
        
        # 主题
        self.mqtt_topic_input = QLineEdit()
        self.mqtt_topic_input.setPlaceholderText("例如: vehicle/data")
        layout.addRow("主题:", self.mqtt_topic_input)
        
        # QoS
        self.mqtt_qos_combo = QComboBox()
        self.mqtt_qos_combo.addItems(["0 (最多一次)", "1 (至少一次)", "2 (恰好一次)"])
        self.mqtt_qos_combo.setCurrentIndex(1)
        layout.addRow("QoS:", self.mqtt_qos_combo)
        
        # 重连间隔
        self.mqtt_reconnect_interval_spin = QSpinBox()
        self.mqtt_reconnect_interval_spin.setRange(0, 60000)
        self.mqtt_reconnect_interval_spin.setValue(5000)
        self.mqtt_reconnect_interval_spin.setSuffix(" 毫秒")
        layout.addRow("重连间隔:", self.mqtt_reconnect_interval_spin)
        
        # 数据主题
        self.mqtt_data_topic_input = QLineEdit()
        self.mqtt_data_topic_input.setPlaceholderText("例如: driving/data")
        layout.addRow("数据主题:", self.mqtt_data_topic_input)
        
        # 控制主题
        self.mqtt_control_topic_input = QLineEdit()
        self.mqtt_control_topic_input.setPlaceholderText("例如: vehicle/control")
        layout.addRow("控制主题:", self.mqtt_control_topic_input)
        
        # 阈值主题
        self.mqtt_threshold_topic_input = QLineEdit()
        self.mqtt_threshold_topic_input.setPlaceholderText("例如: alarm/threshold")
        layout.addRow("阈值主题:", self.mqtt_threshold_topic_input)
        
        # 自动重连
        self.mqtt_auto_reconnect_checkbox = QCheckBox("启用自动重连")
        self.mqtt_auto_reconnect_checkbox.setChecked(True)
        layout.addRow("自动重连:", self.mqtt_auto_reconnect_checkbox)
        
        # 最大重连尝试次数
        self.mqtt_max_reconnect_attempts_spin = QSpinBox()
        self.mqtt_max_reconnect_attempts_spin.setRange(0, 1000)
        self.mqtt_max_reconnect_attempts_spin.setValue(0)
        self.mqtt_max_reconnect_attempts_spin.setSpecialValueText("无限次")
        layout.addRow("最大重连尝试次数:", self.mqtt_max_reconnect_attempts_spin)
        
        scroll_area.setWidget(widget)
        return scroll_area

    def _create_ui_config_tab(self) -> QScrollArea:
        """创建界面配置页面"""
        # 实现界面配置UI（省略具体实现，与其他配置页类似）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        widget = QWidget()
        layout = QFormLayout(widget)
        scroll_area.setWidget(widget)
        return scroll_area

    def _load_all_configs_to_ui(self) -> None:
        """加载所有配置到UI控件"""
        # 加载通用配置
        general_config = self.config_manager.get_config("GeneralConfig")
        self.app_name_input.setText(general_config.get("app_name", ""))
        self.log_level_combo.setCurrentText(general_config.get("log_level", "INFO"))
        self.auto_connect_checkbox.setChecked(general_config.get("auto_connect", True))
        self.refresh_interval_spin.setValue(general_config.get("data_refresh_interval", 1000))
        self.backup_interval_spin.setValue(general_config.get("backup_interval", 24))
        self.max_backup_spin.setValue(general_config.get("max_backup_count", 30))
        
        # 加载MySQL配置
        mysql_config = self.config_manager.get_config("MySQLConfig")
        self.mysql_host_input.setText(mysql_config.get("host", ""))
        self.mysql_port_spin.setValue(mysql_config.get("port", 3306))
        self.mysql_user_input.setText(mysql_config.get("username", ""))
        self.mysql_password_input.setText(str(mysql_config.get("password", "")))
        self.mysql_db_input.setText(mysql_config.get("database", ""))
        self.mysql_timeout_spin.setValue(mysql_config.get("connect_timeout", 5))
        self.mysql_pool_spin.setValue(mysql_config.get("pool_size", 5))
        
        # 加载Redis配置
        redis_config = self.config_manager.get_config("RedisConfig")
        self.redis_host_input.setText(redis_config.get("host", ""))
        self.redis_port_spin.setValue(redis_config.get("port", 6379))
        self.redis_password_input.setText(redis_config.get("password", ""))
        self.redis_db_spin.setValue(redis_config.get("db", 0))
        self.redis_timeout_spin.setValue(redis_config.get("timeout", 10))
        
        # 加载InfluxDB配置
        influxdb_config = self.config_manager.get_config("InfluxDBConfig")
        self.influxdb_url_input.setText(influxdb_config.get("url", ""))
        self.influxdb_token_input.setText(influxdb_config.get("token", ""))
        self.influxdb_org_input.setText(influxdb_config.get("org", ""))
        self.influxdb_bucket_input.setText(influxdb_config.get("bucket", ""))
        
        # 加载MQTT配置
        mqtt_config = self.config_manager.get_config("MQTTConfig")
        self.mqtt_host_input.setText(mqtt_config.get("host", "localhost"))
        self.mqtt_port_spin.setValue(mqtt_config.get("port", 1883))
        self.mqtt_username_input.setText(mqtt_config.get("username", ""))
        self.mqtt_password_input.setText(mqtt_config.get("password", ""))
        self.mqtt_client_id_input.setText(mqtt_config.get("client_id", "vehicle_monitor"))
        self.mqtt_keepalive_spin.setValue(mqtt_config.get("keepalive", 60))
        self.mqtt_topic_input.setText(mqtt_config.get("topic", "vehicle/data"))
        
        # 设置QoS值
        qos = mqtt_config.get("qos", 1)
        if qos == 0:
            self.mqtt_qos_combo.setCurrentIndex(0)
        elif qos == 1:
            self.mqtt_qos_combo.setCurrentIndex(1)
        elif qos == 2:
            self.mqtt_qos_combo.setCurrentIndex(2)
            
        self.mqtt_reconnect_interval_spin.setValue(mqtt_config.get("reconnect_interval", 5000))
        self.mqtt_data_topic_input.setText(mqtt_config.get("data_topic", "driving/data"))
        self.mqtt_control_topic_input.setText(mqtt_config.get("control_topic", "vehicle/control"))
        self.mqtt_threshold_topic_input.setText(mqtt_config.get("threshold_topic", "alarm/threshold"))
        self.mqtt_auto_reconnect_checkbox.setChecked(mqtt_config.get("auto_reconnect", True))
        self.mqtt_max_reconnect_attempts_spin.setValue(mqtt_config.get("max_reconnect_attempts", 0))
        
        # 加载流水线配置
        pipeline_config = self.config_manager.get_config("PipelineConfig")
        self.buffer_size_spin.setValue(pipeline_config.get("buffer_size", 50000))
        self.persist_threshold_spin.setValue(pipeline_config.get("persist_threshold", 10000))
        self.processing_threads_spin.setValue(pipeline_config.get("processing_threads", 2))
        self.batch_size_spin.setValue(pipeline_config.get("batch_size", 100))
        self.real_time_analysis_checkbox.setChecked(pipeline_config.get("enable_real_time_analysis", True))
        self.data_caching_checkbox.setChecked(pipeline_config.get("enable_data_caching", True))
        self.cache_ttl_spin.setValue(pipeline_config.get("cache_ttl", 3600))
        
        # 加载其他配置...

    def _on_save_config(self) -> None:
        """保存配置"""
        current_tab = self.tabs.currentWidget()
        tab_index = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(tab_index)
        
        try:
            if tab_name == "通用配置":
                config_data = {
                    "app_name": self.app_name_input.text(),
                    "log_level": self.log_level_combo.currentText(),
                    "auto_connect": self.auto_connect_checkbox.isChecked(),
                    "data_refresh_interval": self.refresh_interval_spin.value(),
                    "backup_interval": self.backup_interval_spin.value(),
                    "max_backup_count": self.max_backup_spin.value(),
                    "preferred_data_source": self.preferred_source_combo.currentText()
                }
                self.config_manager.update_config("GeneralConfig", config_data)
                
            elif tab_name == "MySQL配置":
                config_data = {
                    "host": self.mysql_host_input.text(),
                    "port": self.mysql_port_spin.value(),
                    "username": self.mysql_user_input.text(),
                    "password": self.mysql_password_input.text(),
                    "database": self.mysql_db_input.text(),
                    "connect_timeout": self.mysql_timeout_spin.value(),
                    "pool_size": self.mysql_pool_spin.value()
                }
                self.config_manager.update_config("MySQLConfig", config_data)
                
            elif tab_name == "Redis配置":
                config_data = {
                    "host": self.redis_host_input.text(),
                    "port": self.redis_port_spin.value(),
                    "password": self.redis_password_input.text(),
                    "db": self.redis_db_spin.value(),
                    "timeout": self.redis_timeout_spin.value()
                }
                self.config_manager.update_config("RedisConfig", config_data)
                
            elif tab_name == "InfluxDB配置":  # 新增InfluxDB配置保存
                config_data = {
                    "url": self.influxdb_url_input.text(),
                    "token": self.influxdb_token_input.text(),
                    "org": self.influxdb_org_input.text(),
                    "bucket": self.influxdb_bucket_input.text()
                }
                self.config_manager.update_config("InfluxDBConfig", config_data)
                
            elif tab_name == "MQTT配置":
                # 解析QoS值
                qos_text = self.mqtt_qos_combo.currentText()
                if "0" in qos_text:
                    qos = 0
                elif "1" in qos_text:
                    qos = 1
                else:  # "2" in qos_text
                    qos = 2
                    
                config_data = {
                    "host": self.mqtt_host_input.text(),
                    "port": self.mqtt_port_spin.value(),
                    "username": self.mqtt_username_input.text(),
                    "password": self.mqtt_password_input.text(),
                    "client_id": self.mqtt_client_id_input.text(),
                    "keepalive": self.mqtt_keepalive_spin.value(),
                    "topic": self.mqtt_topic_input.text(),
                    "qos": qos,
                    "reconnect_interval": self.mqtt_reconnect_interval_spin.value(),
                    "data_topic": self.mqtt_data_topic_input.text(),
                    "control_topic": self.mqtt_control_topic_input.text(),
                    "threshold_topic": self.mqtt_threshold_topic_input.text(),
                    "auto_reconnect": self.mqtt_auto_reconnect_checkbox.isChecked(),
                    "max_reconnect_attempts": self.mqtt_max_reconnect_attempts_spin.value()
                }
                self.config_manager.update_config("MQTTConfig", config_data)
                
            elif tab_name == "流水线配置":
                config_data = {
                    "buffer_size": self.buffer_size_spin.value(),
                    "persist_threshold": self.persist_threshold_spin.value(),
                    "processing_threads": self.processing_threads_spin.value(),
                    "batch_size": self.batch_size_spin.value(),
                    "enable_real_time_analysis": self.real_time_analysis_checkbox.isChecked(),
                    "enable_data_caching": self.data_caching_checkbox.isChecked(),
                    "cache_ttl": self.cache_ttl_spin.value()
                }
                self.config_manager.update_config("PipelineConfig", config_data)
                
            # 处理其他配置页...
            
            QMessageBox.information(self, "成功", f"{tab_name}保存成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def _on_restore_default(self) -> None:
        """恢复默认配置"""
        tab_index = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(tab_index)
        
        config_map = {
            "通用配置": "GeneralConfig",
            "MySQL配置": "MySQLConfig",
            "Redis配置": "RedisConfig",
            "InfluxDB配置": "InfluxDBConfig",
            "流水线配置": "PipelineConfig",
            "MQTT配置": "MQTTConfig",  # 添加MQTT配置映射
            "界面配置": "UIConfig"
        }
        
        config_section = config_map.get(tab_name)
        if not config_section:
            QMessageBox.warning(self, "警告", "无法识别的配置类型")
            return
            
        if QMessageBox.question(self, "确认", f"确定要恢复{tab_name}为默认值吗?") == QMessageBox.Yes:
            if self.config_manager.restore_default_config(config_section):
                self._load_all_configs_to_ui()
                QMessageBox.information(self, "成功", f"{tab_name}已恢复默认配置")
            else:
                QMessageBox.error(self, "错误", f"恢复{tab_name}默认值失败")

    def _on_export_config(self) -> None:
        """导出配置"""
        tab_index = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(tab_index)
        
        config_map = {
            "通用配置": "GeneralConfig",
            "MySQL配置": "MySQLConfig",
            "Redis配置": "RedisConfig",
            "InfluxDB配置": "InfluxDBConfig",  # 新增InfluxDB配置
            "串口配置": "SerialConfig",
            "MQTT配置": "MQTTConfig",
            "界面配置": "UIConfig",
            "流水线配置": "PipelineConfig"
        }
        
        config_name = config_map.get(tab_name) if tab_index != -1 else None
        success, msg = self.config_manager.export_config(config_name)
        
        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.error(self, "错误", msg)

    def _on_import_config(self) -> None:
        """导入配置"""
        success, msg = self.config_manager.import_config()
        if success:
            self._load_all_configs_to_ui()
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.error(self, "错误", msg)

    @Slot(str, dict)
    def _on_config_updated(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """配置更新时刷新UI"""
        self._load_all_configs_to_ui()
        self.logger.info(f"UI已更新配置: {config_name}")

    @Slot(str, str)
    def _on_config_error(self, config_name: str, error_msg: str) -> None:
        """显示配置错误"""
        QMessageBox.error(self, f"配置错误 ({config_name})", error_msg)


# 使用示例
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 初始化系统集成器
    config_dir = os.path.join(os.path.expanduser("~"), ".vehicle_monitor", "config")
    system = SystemIntegrator(config_dir)
    
    # 显示配置界面
    config_window = ConfigWidget(system.config_manager)
    config_window.setWindowTitle("系统配置")
    config_window.resize(800, 600)
    config_window.show()
    
    # 启动系统
    system.start_system()
    
    sys.exit(app.exec())
