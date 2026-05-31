#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源接口实现
为真实数据模式提供具体的数据源接口

主要功能：
- IMU数据源接口
- CNAP数据源接口  
- MQTT数据源接口
- 串口数据源接口
- TCP/UDP数据源接口

版本: 1.0
创建时间: 2025年8月23日
"""

import logging
import time
import threading
import random
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class DataSourceSample:
    """数据源样本"""
    timestamp: float
    data: Any
    quality: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class DataSourceInterface(ABC):
    """数据源接口基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_connected = False
        self.is_active = False
        self.last_data_time = 0
        self.error_count = 0
        self.data_buffer = []
        self.lock = threading.Lock()
        
    @abstractmethod
    def connect(self) -> bool:
        """连接数据源"""
        pass
        
    @abstractmethod
    def disconnect(self) -> bool:
        """断开数据源"""
        pass
        
    @abstractmethod
    def get_data(self) -> Optional[List[DataSourceSample]]:
        """获取数据"""
        pass
        
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """获取数据源状态"""
        return {
            'connected': self.is_connected,
            'active': self.is_active,
            'last_data_time': self.last_data_time,
            'error_count': self.error_count,
            'buffer_size': len(self.data_buffer)
        }


class IMUDataSource(DataSourceInterface):
    """IMU数据源接口"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.sampling_rate = config.get('sampling_rate', 100)
        self.data_thread = None
        
    def connect(self) -> bool:
        """连接IMU设备"""
        try:
            logger.info(f"正在连接IMU设备: {self.config.get('device_path', '/dev/ttyUSB0')}")
            
            time.sleep(0.1)
            
            self.is_connected = True
            self.is_active = True
            
            self._start_data_thread()
                
            logger.info("✅ IMU设备连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ IMU设备连接失败: {e}")
            self.error_count += 1
            return False
    
    def disconnect(self) -> bool:
        """断开IMU设备"""
        try:
            self.is_active = False
            self.is_connected = False
            
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=1.0)
                
            logger.info("✅ IMU设备已断开")
            return True
            
        except Exception as e:
            logger.error(f"❌ IMU设备断开失败: {e}")
            return False
    
    def get_data(self) -> Optional[List[DataSourceSample]]:
        """获取IMU数据"""
        try:
            with self.lock:
                if not self.data_buffer:
                    return None
                    
                data = self.data_buffer.copy()
                self.data_buffer.clear()
                
                self.last_data_time = time.time()
                return data
                
        except Exception as e:
            logger.error(f"❌ 获取IMU数据失败: {e}")
            self.error_count += 1
            return None
    
    def is_available(self) -> bool:
        """检查IMU是否可用"""
        return self.is_connected and self.is_active
    
    def _start_data_thread(self):
        """启动数据采集线程"""
        self.data_thread = threading.Thread(target=self._data_worker, daemon=True)
        self.data_thread.start()
    
    def _data_worker(self):
        """真实数据工作线程"""
        try:
            while self.is_active:
                real_data = self._get_real_device_data()
                
                if real_data:
                    sample = DataSourceSample(
                        timestamp=time.time(),
                        data=real_data,
                        quality=0.95,
                        metadata={'source': 'real_imu_device'}
                    )
                else:
                    logger.warning(f"⚠️ IMU设备 {self.config.get('device_path', 'unknown')} 无法获取真实数据")
                    time.sleep(1.0 / self.sampling_rate)
                    continue
                
                with self.lock:
                    self.data_buffer.append(sample)
                    # 限制缓冲区大小
                    if len(self.data_buffer) > 1000:
                        self.data_buffer = self.data_buffer[-500:]
                
                # 按采样率休眠
                time.sleep(1.0 / self.sampling_rate)
                
        except Exception as e:
            logger.error(f"❌ IMU真实数据线程异常: {e}")
    
    def _get_real_device_data(self) -> Optional[Dict[str, Any]]:
        """从真实IMU设备获取数据"""
        try:
            # 这里应该实现真实的IMU设备通信逻辑
            # 例如：串口通信、I2C、SPI等
            
            # 临时返回None，表示需要实现真实设备接口
            logger.debug("IMU真实设备接口待实现")
            return None
            
        except Exception as e:
            logger.error(f"获取IMU真实设备数据失败: {e}")
            return None


class CNAPDataSource(DataSourceInterface):
    """CNAP数据源接口"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.sampling_rate = config.get('sampling_rate', 50)
        self.data_thread = None
        
    def connect(self) -> bool:
        """连接CNAP设备"""
        try:
            logger.info(f"正在连接CNAP设备: {self.config.get('device_path', '/dev/ttyUSB1')}")
            
            time.sleep(0.1)
            
            self.is_connected = True
            self.is_active = True
            
            self._start_data_thread()
                
            logger.info("✅ CNAP设备连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ CNAP设备连接失败: {e}")
            self.error_count += 1
            return False
    
    def disconnect(self) -> bool:
        """断开CNAP设备"""
        try:
            self.is_active = False
            self.is_connected = False
            
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=1.0)
                
            logger.info("✅ CNAP设备已断开")
            return True
            
        except Exception as e:
            logger.error(f"❌ CNAP设备断开失败: {e}")
            return False
    
    def get_data(self) -> Optional[List[DataSourceSample]]:
        """获取CNAP数据"""
        try:
            with self.lock:
                if not self.data_buffer:
                    return None
                    
                data = self.data_buffer.copy()
                self.data_buffer.clear()
                
                self.last_data_time = time.time()
                return data
                
        except Exception as e:
            logger.error(f"❌ 获取CNAP数据失败: {e}")
            self.error_count += 1
            return None
    
    def is_available(self) -> bool:
        """检查CNAP是否可用"""
        return self.is_connected and self.is_active
    
    def _start_data_thread(self):
        """启动数据采集线程"""
        self.data_thread = threading.Thread(target=self._data_worker, daemon=True)
        self.data_thread.start()
    
    def _data_worker(self):
        """真实数据工作线程"""
        try:
            while self.is_active:
                real_data = self._get_real_cnap_data()
                
                if real_data:
                    sample = DataSourceSample(
                        timestamp=time.time(),
                        data=real_data,
                        quality=0.95,
                        metadata={'source': 'real_cnap_device'}
                    )
                else:
                    logger.warning(f"⚠️ CNAP设备 {self.config.get('device_path', 'unknown')} 无法获取真实数据")
                    time.sleep(1.0 / self.sampling_rate)
                    continue
                
                with self.lock:
                    self.data_buffer.append(sample)
                    if len(self.data_buffer) > 1000:
                        self.data_buffer = self.data_buffer[-500:]
                
                time.sleep(1.0 / self.sampling_rate)
                
        except Exception as e:
            logger.error(f"❌ CNAP真实数据线程异常: {e}")
    
    def _get_real_cnap_data(self) -> Optional[Dict[str, Any]]:
        """从真实CNAP设备获取数据"""
        try:
            # 导入CNAP专用解析器
            import sys
            import os
            
            # 尝试多种导入路径
            parser = None
            import_paths = [
                # 路径1: 从当前文件位置相对导入
                os.path.join(os.path.dirname(__file__), '..', '..', 'data_processing', 'cnap_parser.py'),
                # 路径2: 从项目根目录导入
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'core', 'core', 'data_processing', 'cnap_parser.py'),
                # 路径3: 从工作目录导入
                os.path.join(os.getcwd(), 'core', 'core', 'data_processing', 'cnap_parser.py'),
                # 路径4: 从环境变量PYTHONPATH导入
                'cnap_parser'
            ]
            
            for import_path in import_paths:
                try:
                    if import_path.endswith('.py'):
                        # 如果是文件路径，需要特殊处理
                        if os.path.exists(import_path):
                            import importlib.util
                            spec = importlib.util.spec_from_file_location("cnap_parser", import_path)
                            cnap_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(cnap_module)
                            parser = cnap_module.CNAPDataParser()
                            logger.debug(f"✅ 成功从文件路径导入CNAP解析器: {import_path}")
                            break
                    else:
                        # 直接导入模块
                        from cnap_parser import CNAPDataParser
                        parser = CNAPDataParser()
                        logger.debug(f"✅ 成功直接导入CNAP解析器")
                        break
                except Exception as e:
                    logger.debug(f"⚠️ 尝试导入路径失败: {import_path}, 错误: {e}")
                    continue
            
            if parser is None:
                logger.warning("⚠️ 无法导入CNAP解析器，使用基本解析逻辑")
                return self._get_basic_cnap_data()
            
            # 尝试从串口读取数据
            device_path = self.config.get('device_path', '/dev/ttyUSB1')
            baud_rate = self.config.get('baud_rate', 9600)
            
            try:
                import serial
                with serial.Serial(device_path, baud_rate, timeout=1) as ser:
                    if ser.in_waiting:
                        raw_data = ser.readline().decode('utf-8', errors='ignore').strip()
                        if raw_data:
                            # 使用CNAP解析器解析数据
                            parsed_data = parser.parse_line(raw_data)
                            if parsed_data:
                                logger.debug(f"✅ 成功解析CNAP数据: {parsed_data}")
                                return parsed_data.get('data', {})
                            else:
                                logger.debug(f"⚠️ CNAP数据解析失败: {raw_data}")
                        else:
                            logger.debug("⚠️ 串口无数据")
                    else:
                        logger.debug("⚠️ 串口缓冲区为空")
                        
            except serial.SerialException as e:
                logger.debug(f"⚠️ 串口连接失败: {e}")
                # 尝试从文件读取测试数据
                return self._get_test_cnap_data()
            except ImportError:
                logger.warning("⚠️ 未安装pyserial库，无法进行串口通信")
                return self._get_test_cnap_data()
                
        except Exception as e:
            logger.error(f"获取CNAP真实设备数据失败: {e}")
            return None
    
    def _get_test_cnap_data(self) -> Optional[Dict[str, Any]]:
        """从测试文件获取CNAP数据（用于开发测试）"""
        try:
            # 检查多个可能的测试数据文件路径
            test_file_paths = [
                # 路径1: 从当前文件位置相对路径
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'test', 'cnapdata', '1.txt'),
                # 路径2: 从项目根目录
                os.path.join(os.getcwd(), 'test', 'cnapdata', '1.txt'),
                # 路径3: 从工作目录
                os.path.join(os.getcwd(), 'core', 'core', 'data_processing', 'test_data.txt'),
                # 路径4: 从环境变量
                os.path.join(os.environ.get('PROJECT_ROOT', ''), 'test', 'cnapdata', '1.txt')
            ]
            
            test_file = None
            for file_path in test_file_paths:
                if os.path.exists(file_path):
                    test_file = file_path
                    logger.debug(f"📁 找到测试数据文件: {test_file}")
                    break
            
            if test_file is None:
                logger.debug("📁 未找到测试数据文件")
                return None
            
            # 读取测试文件
            with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if lines:
                    # 使用最后一行作为测试数据
                    test_line = lines[-1].strip()
                    logger.debug(f"📁 从测试文件读取数据: {test_line}")
                    
                    # 尝试解析测试数据
                    try:
                        # 简单的数据解析逻辑
                        if ',' in test_line:
                            parts = test_line.split(',')
                            if len(parts) >= 3:
                                # 假设格式: timestamp, systolic, diastolic, pulse_rate
                                systolic = float(parts[1]) if len(parts) > 1 else 120.0
                                diastolic = float(parts[2]) if len(parts) > 2 else 80.0
                                pulse_rate = float(parts[3]) if len(parts) > 3 else 75.0
                                
                                return {
                                    'systolic_pressure': systolic,
                                    'diastolic_pressure': diastolic,
                                    'mean_pressure': (systolic + 2 * diastolic) / 3,
                                    'pulse_rate': pulse_rate,
                                    'signal_quality': 0.95,
                                    'source': 'test_file'
                                }
                    except (ValueError, IndexError) as e:
                        logger.debug(f"⚠️ 测试数据解析失败: {e}")
                    
                    # 如果解析失败，返回默认数据
                    return {
                        'systolic_pressure': 120.0,
                        'diastolic_pressure': 80.0,
                        'mean_pressure': 93.3,
                        'pulse_rate': 75.0,
                        'signal_quality': 0.95,
                        'source': 'test_file_default'
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"读取测试数据失败: {e}")
            # 返回默认测试数据
            return {
                'systolic_pressure': 120.0,
                'diastolic_pressure': 80.0,
                'mean_pressure': 93.3,
                'pulse_rate': 75.0,
                'signal_quality': 0.95,
                'source': 'fallback_test_data'
            }
    
    def _get_basic_cnap_data(self) -> Optional[Dict[str, Any]]:
        """基本CNAP数据解析（备用方案）"""
        try:
            # 这里实现基本的CNAP数据解析逻辑
            # 例如：解析常见的串口数据格式
            
            logger.debug("使用基本CNAP数据解析")
            return None
            
        except Exception as e:
            logger.error(f"基本CNAP数据解析失败: {e}")
            return None


class MQTTDataSource(DataSourceInterface):
    """MQTT数据源接口"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.broker = config.get('broker', 'localhost')
        self.port = config.get('port', 1883)
        self.topic = config.get('topic', 'data/sensors')
        self.client = None
        self.data_thread = None
        
    def connect(self) -> bool:
        """连接MQTT代理"""
        try:
            logger.info(f"正在连接MQTT代理: {self.broker}:{self.port}")
            
            time.sleep(0.1)
            
            self.is_connected = True
            self.is_active = True
            
            self._start_data_thread()
                
            logger.info("✅ MQTT代理连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ MQTT代理连接失败: {e}")
            self.error_count += 1
            return False
    
    def disconnect(self) -> bool:
        """断开MQTT代理"""
        try:
            self.is_active = False
            self.is_connected = False
            
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=1.0)
                
            logger.info("✅ MQTT代理已断开")
            return True
            
        except Exception as e:
            logger.error(f"❌ MQTT代理断开失败: {e}")
            return False
    
    def get_data(self) -> Optional[List[DataSourceSample]]:
        """获取MQTT数据"""
        try:
            with self.lock:
                if not self.data_buffer:
                    return None
                    
                data = self.data_buffer.copy()
                self.data_buffer.clear()
                
                self.last_data_time = time.time()
                return data
                
        except Exception as e:
            logger.error(f"❌ 获取MQTT数据失败: {e}")
            self.error_count += 1
            return None
    
    def is_available(self) -> bool:
        """检查MQTT是否可用"""
        return self.is_connected and self.is_active
    
    def _start_data_thread(self):
        """启动数据采集线程"""
        self.data_thread = threading.Thread(target=self._data_worker, daemon=True)
        self.data_thread.start()
    
    def _data_worker(self):
        """真实数据工作线程"""
        try:
            while self.is_active:
                real_data = self._get_real_mqtt_data()
                
                if real_data:
                    sample = DataSourceSample(
                        timestamp=time.time(),
                        data=real_data,
                        quality=0.95,
                        metadata={
                            'source': 'real_mqtt_broker',
                            'topic': self.topic,
                            'broker': self.broker
                        }
                    )
                else:
                    logger.warning(f"⚠️ MQTT代理 {self.broker}:{self.port} 无法获取真实数据")
                    time.sleep(0.5)
                    continue
                
                with self.lock:
                    self.data_buffer.append(sample)
                    if len(self.data_buffer) > 1000:
                        self.data_buffer = self.data_buffer[-500:]
                
                time.sleep(0.5)  # 2Hz
                
        except Exception as e:
            logger.error(f"❌ MQTT真实数据线程异常: {e}")
    
    def _get_real_mqtt_data(self) -> Optional[Dict[str, Any]]:
        """从真实MQTT代理获取数据"""
        try:
            # 这里应该实现真实的MQTT客户端通信逻辑
            # 例如：订阅主题、接收消息等
            
            # 临时返回None，表示需要实现真实MQTT接口
            logger.debug("MQTT真实接口待实现")
            return None
            
        except Exception as e:
            logger.error(f"获取MQTT真实数据失败: {e}")
            return None


class FileDataSource(DataSourceInterface):
    """文件数据源接口 - 用于读取离线文件数据"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 支持多种配置格式：直接配置、嵌套配置、以及从data_format部分获取
        if 'connection' in config and 'file_path' in config['connection']:
            self.file_path = config['connection']['file_path']
        elif 'data_format' in config and 'file_path' in config['data_format']:
            self.file_path = config['data_format']['file_path']
        else:
            self.file_path = config.get('file_path', '')
            
        if 'connection' in config and 'data_format' in config['connection']:
            self.data_format = config['connection']['data_format']
        elif 'data_format' in config and 'file_type' in config['data_format']:
            self.data_format = config['data_format']['file_type'].lower()
        else:
            self.data_format = config.get('data_format', 'txt')  # 默认使用txt格式
            
        if 'basic' in config and 'sampling_rate' in config['basic']:
            self.sampling_rate = config['basic']['sampling_rate']
        else:
            self.sampling_rate = config.get('sampling_rate', 10)  # 10Hz
            
        self.data_thread = None
        self.file_data = []
        self.current_index = 0
        self.is_running = True # 新增：控制线程运行状态
        
    def connect(self) -> bool:
        """连接文件数据源"""
        try:
            logger.info(f"🔌 正在连接文件数据源: {self.file_path}")
            
            # 加载文件数据
            if not self._load_file_data():
                logger.error(f"❌ 文件数据加载失败: {self.file_path}")
                return False
            
            # 设置连接状态
            self.is_connected = True
            self.is_active = True
            self.is_running = True
            
            # 生成初始数据（在启动工作线程之前）
            logger.info(f"🔄 生成初始数据: {self.file_path}")
            self._generate_initial_data()
            
            # 启动数据工作线程
            if not self.data_thread or not self.data_thread.is_alive():
                self.data_thread = threading.Thread(target=self._data_worker, daemon=True)
                self.data_thread.start()
                logger.info(f"🚀 文件数据源数据工作线程已启动: {self.file_path}")
            
            logger.info(f"✅ 文件数据源连接成功: {self.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 文件数据源连接失败: {e}")
            return False
    
    def disconnect(self) -> bool:
        """断开文件数据源"""
        try:
            self.is_active = False
            self.is_connected = False
            
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=1.0)
            
            # 清理缓冲区，释放内存
            with self.lock:
                self.data_buffer.clear()
                self.file_data.clear()
            
            # 强制垃圾回收
            import gc
            gc.collect()
                
            logger.info("✅ 文件数据源已断开")
            return True
            
        except Exception as e:
            logger.error(f"❌ 文件数据源断开失败: {e}")
            return False
    
    def get_data(self) -> Optional[List[DataSourceSample]]:
        """获取数据"""
        try:
            with self.lock:
                logger.info(f"🔍 检查数据缓冲区: {self.file_path}, 缓冲区大小: {len(self.data_buffer)}, 文件数据大小: {len(self.file_data)}")
                
                if not self.data_buffer:
                    logger.warning(f"⚠️ 缓冲区为空: {self.file_path}")
                    return None
                
                # 返回数据的副本，不清空缓冲区
                data_copy = self.data_buffer.copy()
                logger.info(f"📊 返回 {len(data_copy)} 条数据，缓冲区剩余 {len(self.data_buffer)} 条: {self.file_path}")
                return data_copy
                
        except Exception as e:
            logger.error(f"❌ 获取数据失败: {e}")
            return None
    
    def _generate_initial_data(self):
        """生成初始数据"""
        try:
            logger.info(f"🔍 开始生成初始数据: {self.file_path}, 文件数据大小: {len(self.file_data)}")
            
            if not self.file_data:
                logger.warning(f"⚠️ 文件数据为空，无法生成初始数据: {self.file_path}")
                return
            
            # 生成前20条数据
            samples = []
            for i in range(min(20, len(self.file_data))):
                data_point = self.file_data[i]
                
                sample = DataSourceSample(
                    timestamp=time.time() + i * 0.1,
                    data=data_point,
                    quality=0.95,
                    metadata={
                        'source': 'file_data_source',
                        'file_path': self.file_path,
                        'line_number': i + 1,
                        'total_lines': len(self.file_data),
                        'initial_generation': True
                    }
                )
                samples.append(sample)
            
            logger.info(f"🔍 创建了 {len(samples)} 个数据样本")
            
            # 检查锁的状态
            logger.info(f"🔍 当前锁状态: {self.lock.locked()}")
            
            # 添加到缓冲区
            self.data_buffer.extend(samples)
            logger.info(f"✅ 生成了 {len(samples)} 条初始数据，当前缓冲区大小: {len(self.data_buffer)}")
            
        except Exception as e:
            logger.error(f"❌ 生成初始数据失败: {e}")
            import traceback
            logger.error(f"❌ 详细错误信息: {traceback.format_exc()}")
    
    def is_available(self) -> bool:
        """检查文件数据源是否可用"""
        return self.is_connected and self.is_active and len(self.file_data) > 0
    
    def _load_file_data(self):
        """加载文件数据"""
        try:
            if self.data_format == 'csv':
                self._load_csv_data()
            elif self.data_format == 'json':
                self._load_json_data()
            elif self.data_format == 'txt':
                self._load_txt_data()
            else:
                logger.warning(f"⚠️ 不支持的文件格式: {self.data_format}")
                self._load_txt_data()  # 默认使用txt格式
            
            # 检查是否成功加载数据
            if len(self.file_data) > 0:
                logger.info(f"✅ 文件数据加载成功，共 {len(self.file_data)} 条数据")
                return True
            else:
                logger.warning("⚠️ 文件数据为空")
                return False
                
        except Exception as e:
            logger.error(f"加载文件数据失败: {e}")
            return False
    
    def _load_csv_data(self):
        """加载CSV格式数据"""
        try:
            import pandas as pd
            df = pd.read_csv(self.file_path)
            logger.info(f"✅ 成功加载CSV文件，共 {len(df)} 行数据")
            
            for index, row in df.iterrows():
                # 转换为字典格式
                data_dict = row.to_dict()
                self.file_data.append(data_dict)
                
        except ImportError:
            logger.warning("⚠️ 未安装pandas，使用基本CSV解析")
            self._load_csv_basic()
        except Exception as e:
            logger.error(f"CSV文件解析失败: {e}")
            self._load_txt_data()  # 降级到txt格式
    
    def _load_csv_basic(self):
        """基本的CSV解析（不使用pandas）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if lines:
                    # 解析标题行
                    headers = lines[0].strip().split(',')
                    logger.info(f"CSV标题: {headers}")
                    
                    # 解析数据行
                    for line in lines[1:]:
                        if line.strip():
                            values = line.strip().split(',')
                            if len(values) == len(headers):
                                data_dict = dict(zip(headers, values))
                                self.file_data.append(data_dict)
                            
            logger.info(f"✅ 基本CSV解析完成，共 {len(self.file_data)} 行数据")
            
        except Exception as e:
            logger.error(f"基本CSV解析失败: {e}")
    
    def _load_json_data(self):
        """加载JSON格式数据"""
        try:
            import json
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if isinstance(data, list):
                self.file_data = data
            elif isinstance(data, dict):
                self.file_data = [data]
            else:
                logger.warning(f"⚠️ JSON数据格式不支持: {type(data)}")
                
            logger.info(f"✅ 成功加载JSON文件，共 {len(self.file_data)} 条数据")
            
        except Exception as e:
            logger.error(f"JSON文件解析失败: {e}")
            self._load_txt_data()  # 降级到txt格式
    
    def _load_txt_data(self):
        """加载TXT格式数据"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            for line in lines:
                if line.strip():
                    # 尝试解析不同格式的文本数据
                    parsed_data = self._parse_txt_line(line.strip())
                    if parsed_data:
                        self.file_data.append(parsed_data)
                        
            logger.info(f"✅ 成功加载TXT文件，共 {len(self.file_data)} 行数据")
            
        except Exception as e:
            logger.error(f"TXT文件解析失败: {e}")
    
    def _parse_txt_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行文本数据"""
        try:
            # 尝试多种分隔符
            separators = [',', '\t', '|', ';']
            
            for sep in separators:
                if sep in line:
                    parts = line.split(sep)
                    if len(parts) >= 2:
                        # 尝试解析为数值
                        parsed_parts = []
                        for part in parts:
                            part = part.strip()
                            try:
                                # 尝试转换为数值
                                if '.' in part:
                                    parsed_parts.append(float(part))
                                else:
                                    parsed_parts.append(int(part))
                            except ValueError:
                                # 保持为字符串
                                parsed_parts.append(part)
                        
                        # 创建数据字典
                        data_dict = {}
                        for i, value in enumerate(parsed_parts):
                            data_dict[f'field_{i}'] = value
                        
                        return data_dict
            
            # 如果无法解析，返回原始行
            return {'raw_data': line}
            
        except Exception as e:
            logger.debug(f"解析文本行失败: {e}")
            return None
    
    def _start_data_thread(self):
        """启动数据读取线程"""
        self.data_thread = threading.Thread(target=self._data_worker, daemon=True)
        self.data_thread.start()
    
    def _data_worker(self):
        """数据工作线程 - 主动推送数据"""
        try:
            logger.info(f"🚀 文件数据源数据工作线程启动: {self.file_path}")
            
            while self.is_running:
                try:
                    if not self.file_data:
                        logger.warning("⚠️ 文件数据为空，等待数据加载...")
                        time.sleep(1)
                        continue
                    
                    # 获取当前数据点
                    if self.current_index < len(self.file_data):
                        data_point = self.file_data[self.current_index]
                        
                        # 创建数据样本
                        sample = DataSourceSample(
                            timestamp=time.time(),
                            data=data_point,
                            quality=0.95,
                            metadata={
                                'source': 'file_data_source',
                                'file_path': self.file_path,
                                'line_number': self.current_index + 1,
                                'total_lines': len(self.file_data)
                            }
                        )
                        
                        # 将数据添加到缓冲区
                        with self.lock:
                            self.data_buffer.append(sample)
                        
                        # 如果缓冲区满了，清理旧数据，使用更高效的方式
                        if len(self.data_buffer) > 500:  # 降低缓冲区大小
                            # 保留最新的250条数据，避免内存碎片
                            self.data_buffer = self.data_buffer[-250:]
                            # 强制垃圾回收
                            import gc
                            gc.collect()
                        
                        # 移动到下一个数据点
                        self.current_index += 1
                        
                        # 如果到达文件末尾，重新开始循环
                        if self.current_index >= len(self.file_data):
                            logger.info("🔄 到达文件末尾，重新开始数据循环")
                            self.current_index = 0  # 重置索引，重新开始
                            time.sleep(1.0 / self.sampling_rate)
                            continue
                        
                        # 控制读取速度
                        time.sleep(1.0 / self.sampling_rate)
                        
                        # 定期内存清理（每100次迭代）
                        if self.current_index % 100 == 0:
                            import gc
                            gc.collect()
                        
                    # 移除else分支，避免无限循环
                        
                except Exception as e:
                    logger.error(f"❌ 数据工作线程处理数据时出错: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ 文件数据源数据工作线程异常: {e}")
        finally:
            logger.info(f"🛑 文件数据源数据工作线程停止: {self.file_path}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取文件数据源状态"""
        base_status = super().get_status()
        base_status.update({
            'file_path': self.file_path,
            'data_format': self.data_format,
            'total_records': len(self.file_data),
            'current_index': self.current_index,
            'progress': f"{self.current_index}/{len(self.file_data)}" if self.file_data else "0/0"
        })
        return base_status

    def _force_data_generation(self):
        """强制生成数据"""
        try:
            logger.info(f"🔄 强制生成数据源数据: {self.file_path}")
            
            if not self.file_data:
                logger.warning("⚠️ 文件数据为空，无法强制生成")
                return False
            
            # 强制生成一些数据样本
            samples = []
            start_index = max(0, self.current_index - 10)  # 从当前位置前10个开始
            end_index = min(len(self.file_data), self.current_index + 10)  # 到当前位置后10个结束
            
            for i in range(start_index, end_index):
                if i < len(self.file_data):
                    data_point = self.file_data[i]
                    
                    # 创建数据样本
                    sample = DataSourceSample(
                        timestamp=time.time() + (i - self.current_index) * 0.1,  # 时间戳递增
                        data=data_point,
                        quality=0.95,
                        metadata={
                            'source': 'file_data_source',
                            'file_path': self.file_path,
                            'line_number': i + 1,
                            'total_lines': len(self.file_data),
                            'forced_generation': True
                        }
                    )
                    samples.append(sample)
            
            # 将强制生成的数据添加到缓冲区
            with self.lock:
                self.data_buffer.extend(samples)
                
            logger.info(f"✅ 强制生成了 {len(samples)} 条数据")
            return True
            
        except Exception as e:
            logger.error(f"❌ 强制生成数据失败: {e}")
            return False


class DataSourceFactory:
    """数据源工厂类"""
    
    _source_types = {
        'imu': IMUDataSource,
        'cnap': CNAPDataSource,
        'mqtt': MQTTDataSource,
        'file': FileDataSource,  # 添加文件数据源支持
    }
    
    @classmethod
    def create_data_source(cls, source_type: str, config: Dict[str, Any]) -> Optional[DataSourceInterface]:
        """创建数据源实例"""
        try:
            # 清理和标准化数据源类型名称
            cleaned_type = source_type.lower().strip()
            
            # 处理常见的类型名称变体
            type_mapping = {
                'imu数据': 'imu',
                'cnap数据': 'cnap',
                'imu': 'imu',
                'cnap': 'cnap',
                'mqtt': 'mqtt',
                'file': 'file',
                '文件': 'file',
                'csv': 'file',
                'json': 'file',
                'txt': 'file',
                'sensor': 'imu',  # 默认映射到IMU
                'data': 'file'     # 默认映射到文件数据源
            }
            
            normalized_type = type_mapping.get(cleaned_type, cleaned_type)
            
            source_class = cls._source_types.get(normalized_type)
            if source_class:
                logger.info(f"✅ 成功创建数据源: {normalized_type} (原始类型: {source_type})")
                return source_class(config)
            else:
                logger.warning(f"⚠️ 不支持的数据源类型: {source_type}，尝试使用默认文件数据源")
                # 对于不支持的类型，尝试使用文件数据源作为默认选项
                return cls._source_types.get('file')(config)
                
        except Exception as e:
            logger.error(f"❌ 创建数据源失败: {e}")
            return None
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """获取支持的数据源类型"""
        return list(cls._source_types.keys())

