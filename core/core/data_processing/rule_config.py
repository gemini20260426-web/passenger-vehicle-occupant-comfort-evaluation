#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于实际专用解析器的数据类型规则配置表
支持IMU和CNAP两种数据类型的配置管理
"""

import logging
from typing import Dict, Any, List, Optional
import time

class DataTypeRuleConfig:
    """基于实际专用解析器的数据类型规则配置"""
    
    def __init__(self):
        # 基于 IMUDataParser 的实际字段结构
        self.imu_rules = {
            'name': 'IMU惯性测量单元',
            'description': '加速度计、陀螺仪、车速、方向盘、位置数据',
            'parser_class': 'IMUDataParser',
            'data_structure': {
                'cnt': 'int',           # 计数器
                'ax': 'float',          # 加速度X轴 (m/s²)
                'ay': 'float',          # 加速度Y轴 (m/s²) 
                'az': 'float',          # 加速度Z轴 (m/s²)
                'gx': 'float',          # 陀螺仪X轴 (rad/s)
                'gy': 'float',          # 陀螺仪Y轴 (rad/s) - 注意：有负号转换
                'gz': 'float',          # 陀螺仪Z轴 (rad/s)
                'speed': 'float',       # 车速 (km/h)
                'wheel': 'float',       # 方向盘角度 (degree)
                'loc1': 'float',        # 位置1
                'loc2': 'float',        # 位置2
                'crc': 'str',           # CRC校验
                'timestamp': 'float'    # Unix时间戳
            },
            'data_format': {
                'packet_start': 'AA',   # 数据包起始标识
                'packet_end': 'BB',     # 数据包结束标识
                'separator': ',',       # 数据分隔符
                'timestamp_format': r'\[?(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{2}[:]\d{2}[:]\d{2}[.,-]?\d{3})]?'
            },
            'processing_rules': {
                'gy': {'conversion': lambda x: -x, 'unit': 'rad/s'},  # Y轴陀螺仪需要取反
                'default_conversion': lambda x: x
            },
            'validation_rules': {
                'frame_drop_threshold': 5,
                'garbage_data_threshold': 0.3
            }
        }
        
        # 基于 CNAPDataParser 的实际字段结构
        self.cnap_rules = {
            'name': 'CNAP连续无创血压',
            'description': '心血管生理参数监测数据',
            'parser_class': 'CNAPDataParser',
            'data_structure': {
                # BEATS格式数据
                'Type': 'str',                    # 数据类型 (BEATS/WAVE/EVENT)
                'Sequence': 'float',              # 序列号/时间戳
                'Beat_Marker': 'float',           # 节拍标识
                'Systolic_BP': 'float',           # 收缩压 (mmHg)
                'Diastolic_BP': 'float',          # 舒张压 (mmHg)
                'Heart_Rate': 'float',            # 心率 (bpm)
                'Mean_Arterial_Pressure': 'float', # 平均动脉压 (mmHg)
                'Pulse_Pressure': 'float',        # 脉压 (mmHg)
                'Heart_Rate_Variability': 'float', # 心率变异性
                'Mean_Pulse_Pressure': 'float',   # 平均脉压
                'Stroke_Volume': 'float',         # 每搏输出量
                'Vascular_Resistance': 'float',   # 血管阻力
                'PPV': 'float',                   # 脉压变异
                'SVV': 'float',                   # 每搏输出量变异
                'Ejection_Fraction': 'float',     # 射血分数
                
                # WAVE格式数据
                'Value': 'float',                 # 波形值
                
                # EVENT格式数据
                'Event': 'str'                    # 事件描述
            },
            'data_format': {
                'timestamp_format': r'Timestamp:\s*(\d+\.\d+)',
                'data_pattern': r'Data:\s*b\'%[A-Z]+%(\d+\.\d+)',
                'beats_pattern': r'%BEATS%(\d+\.\d+): (.*?)(?:\n|$)',
                'wave_pattern': r'%WAVE%(\d+\.\d+):\s*([\d.]+)',
                'event_pattern': r'(\d+\.\d+):\s*Event:\s*(.+)'
            },
            'validation_rules': {
                'Systolic_BP': (50, 200),      # 收缩压范围 (mmHg)
                'Diastolic_BP': (30, 120),     # 舒张压范围 (mmHg)
                'Heart_Rate': (30, 180),       # 心率范围 (bpm)
                'Mean_Arterial_Pressure': (40, 150),  # 平均动脉压范围 (mmHg)
                'Value': (0, 300)              # 波形值范围
            }
        }
        
        self.logger = logging.getLogger(__name__)
    
    def get_data_type_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据类型规则"""
        return {
            'imu': self.imu_rules,
            'cnap': self.cnap_rules
        }
    
    def get_data_type_rule(self, data_type: str) -> Optional[Dict[str, Any]]:
        """获取指定数据类型的规则"""
        if data_type == 'imu':
            return self.imu_rules
        elif data_type == 'cnap':
            return self.cnap_rules
        else:
            self.logger.warning(f"未知的数据类型: {data_type}")
            return None
    
    def validate_data_structure(self, data_type: str, data: Dict[str, Any]) -> bool:
        """验证数据是否符合指定类型的结构"""
        rule = self.get_data_type_rule(data_type)
        if not rule:
            return False
        
        required_fields = rule['data_structure'].keys()
        data_fields = data.keys()
        
        # 检查必要字段
        for field in required_fields:
            if field not in data_fields:
                self.logger.warning(f"缺少必要字段: {field}")
                return False
        
        return True


class TransmissionTypeConfig:
    """传输类型配置"""
    
    def __init__(self):
        self.transmission_types = {
            'mqtt': {
                'name': 'MQTT消息队列',
                'description': '基于主题的发布订阅模式',
                'config_fields': ['broker_host', 'broker_port', 'topic', 'qos', 'username', 'password'],
                'parser_type': 'json_structured',  # 结构化JSON解析
                'parser_class': 'JSONStructuredParser'
            },
            'tcp': {
                'name': 'TCP套接字',
                'description': '可靠的面向连接传输',
                'config_fields': ['host', 'port', 'timeout', 'buffer_size'],
                'parser_type': 'binary_data',     # 二进制数据解析
                'parser_class': 'BinaryDataParser'
            },
            'udp': {
                'name': 'UDP数据报',
                'description': '快速无连接传输',
                'config_fields': ['host', 'port', 'buffer_size'],
                'parser_type': 'binary_data',     # 二进制数据解析
                'parser_class': 'BinaryDataParser'
            },
            'serial': {
                'name': '串口通信',
                'description': 'RS232/RS485串行通信',
                'config_fields': ['port', 'baudrate', 'bytesize', 'parity', 'stopbits'],
                'parser_type': 'dedicated',       # 专用解析器
                'parser_class': 'IMUDataParser'   # 默认使用IMU解析器
            },
            'file': {
                'name': '文件加载',
                'description': '离线数据文件读取',
                'config_fields': ['file_path', 'encoding', 'chunk_size'],
                'parser_type': 'dedicated',       # 专用解析器
                'parser_class': 'auto_detect'     # 自动检测
            }
        }
        
        self.logger = logging.getLogger(__name__)
    
    def get_transmission_types(self) -> Dict[str, Dict[str, Any]]:
        """获取所有传输类型配置"""
        return self.transmission_types
    
    def get_transmission_type(self, trans_type: str) -> Optional[Dict[str, Any]]:
        """获取指定传输类型的配置"""
        return self.transmission_types.get(trans_type.lower())
    
    def validate_transmission_config(self, trans_type: str, config: Dict[str, Any]) -> bool:
        """验证传输类型配置"""
        trans_config = self.get_transmission_type(trans_type)
        if not trans_config:
            return False
        
        required_fields = trans_config['config_fields']
        config_fields = config.keys()
        
        # 检查必要配置字段
        for field in required_fields:
            if field not in config_fields:
                self.logger.warning(f"缺少必要配置字段: {field}")
                return False
        
        return True


class RuleConfigurationManager:
    """规则配置管理器"""
    
    def __init__(self):
        self.data_type_config = DataTypeRuleConfig()
        self.transmission_config = TransmissionTypeConfig()
        self.logger = logging.getLogger(__name__)
    
    def get_complete_config(self) -> Dict[str, Any]:
        """获取完整的规则配置"""
        return {
            'data_types': self.data_type_config.get_data_type_rules(),
            'transmission_types': self.transmission_config.get_transmission_types()
        }
    
    def create_source_config(self, data_types: List[str], transmission_type: str, 
                           parser_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """创建数据源配置"""
        try:
            # 验证数据类型
            for data_type in data_types:
                if not self.data_type_config.get_data_type_rule(data_type):
                    raise ValueError(f"不支持的数据类型: {data_type}")
            
            # 验证传输类型
            if not self.transmission_config.get_transmission_type(transmission_type):
                raise ValueError(f"不支持的传输类型: {transmission_type}")
            
            # 验证配置
            if not self.transmission_config.validate_transmission_config(transmission_type, config):
                raise ValueError(f"传输类型配置验证失败: {transmission_type}")
            
            source_config = {
                'data_types': data_types,
                'transmission_type': transmission_type,
                'parser_type': parser_type,
                'config': config,
                'created_at': time.time()
            }
            
            self.logger.info(f"成功创建数据源配置: {data_types} + {transmission_type}")
            return source_config
            
        except Exception as e:
            self.logger.error(f"创建数据源配置失败: {e}")
            raise
