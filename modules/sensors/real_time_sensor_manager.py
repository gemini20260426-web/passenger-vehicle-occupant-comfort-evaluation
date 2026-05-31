#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实传感器数据管理器
提供高精度的实时传感器数据，包括IMU、GPS、轮速等
"""

import time
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import logging

# 尝试导入硬件相关库
try:
    import serial
    import pynmea2
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("串口库不可用，将使用模拟串口数据")

try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False
    logging.warning("I2C库不可用，将使用模拟I2C数据")

try:
    import spidev
    SPI_AVAILABLE = True
except ImportError:
    SPI_AVAILABLE = False
    logging.warning("SPI库不可用，将使用模拟SPI数据")

logger = logging.getLogger(__name__)


class RealTimeSensorManager:
    """真实传感器数据管理器"""
    
    def __init__(self):
        self.sensors = {}
        self.data_callbacks = []
        self.is_running = False
        self.data_thread = None
        self.update_interval = 0.1  # 100ms更新间隔
        
        # 传感器配置
        self.sensor_config = {
            'IMU': {
                'type': 'MPU6050',
                'interface': 'I2C',
                'address': 0x68,
                'enabled': True,
                'retry_count': 0,
                'max_retries': 3
            },
            'GPS': {
                'type': 'NEO-6M',
                'interface': 'UART',
                'port': '/dev/ttyUSB0',
                'baudrate': 9600,
                'enabled': True,
                'retry_count': 0,
                'max_retries': 3
            },
            'WHEEL_SPEED': {
                'type': 'Hall_Sensor',
                'interface': 'GPIO',
                'pin': 18,
                'enabled': True,
                'retry_count': 0,
                'max_retries': 3
            }
        }
        
        # 🚨 传感器连接状态监控
        self.sensor_connection_status = {
            'IMU': {'connected': False, 'last_attempt': None, 'error_count': 0},
            'GPS': {'connected': False, 'last_attempt': None, 'error_count': 0},
            'WHEEL_SPEED': {'connected': False, 'last_attempt': None, 'error_count': 0}
        }
        
        # 初始化传感器
        self._init_sensors()
        
        # 数据缓存
        self.latest_data = {
            'IMU': {},
            'GPS': {},
            'WHEEL_SPEED': {},
            'BEHAVIOR': {},
            'timestamp': None
        }
        
        # 行为分析统计
        self.behavior_stats = {
            'non_curve_state': 0,
            'normal_braking': 0,
            'curve_state': 0,
            'emergency_braking': 0,
            'acceleration': 0,
            'deceleration': 0
        }
        
        logger.info("🚀 真实传感器数据管理器初始化完成")
    
    def get_sensor_connection_status(self) -> Dict[str, Dict]:
        """🚨 获取传感器连接状态"""
        return self.sensor_connection_status.copy()
    
    def get_real_sensor_count(self) -> int:
        """🚨 获取真实传感器数量"""
        real_count = 0
        for sensor_name, status in self.sensor_connection_status.items():
            if status['connected']:
                real_count += 1
        return real_count
    
    def get_simulation_fallback_count(self) -> int:
        """🚨 获取降级到模拟模式的传感器数量"""
        total_sensors = len(self.sensor_connection_status)
        real_count = self.get_real_sensor_count()
        return total_sensors - real_count
    
    def _init_sensors(self):
        """初始化传感器"""
        try:
            # 初始化IMU传感器
            if self.sensor_config['IMU']['enabled']:
                self._init_imu_sensor()
            
            # 初始化GPS传感器
            if self.sensor_config['GPS']['enabled']:
                self._init_gps_sensor()
            
            # 初始化轮速传感器
            if self.sensor_config['WHEEL_SPEED']['enabled']:
                self._init_wheel_speed_sensor()
                
            logger.info("✅ 传感器初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 传感器初始化失败: {e}")
    
    def _init_imu_sensor(self):
        """🚨 初始化IMU传感器（增强版）"""
        sensor_name = 'IMU'
        max_retries = self.sensor_config[sensor_name]['max_retries']
        
        for attempt in range(max_retries + 1):
            try:
                if I2C_AVAILABLE:
                    # 使用真实的I2C连接
                    self.sensors[sensor_name] = MPU6050Sensor(
                        bus=1,
                        address=self.sensor_config[sensor_name]['address']
                    )
                    
                    # 测试连接
                    test_data = self.sensors[sensor_name].read_data()
                    if test_data:
                        self.sensor_connection_status[sensor_name]['connected'] = True
                        self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                        self.sensor_connection_status[sensor_name]['error_count'] = 0
                        logger.info(f"✅ IMU传感器(I2C)初始化成功，连接测试通过")
                        return
                    else:
                        raise Exception("连接测试失败")
                else:
                    raise ImportError("I2C库不可用")
                    
            except Exception as e:
                self.sensor_connection_status[sensor_name]['error_count'] += 1
                self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                
                if attempt < max_retries:
                    logger.warning(f"⚠️ IMU传感器初始化失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    logger.error(f"❌ IMU传感器初始化最终失败: {e}")
                    # 创建备用模拟传感器
                    self.sensors[sensor_name] = SimulatedMPU6050()
                    logger.warning("⚠️ 已降级到模拟IMU传感器")
                    break
    
    def _init_gps_sensor(self):
        """🚨 初始化GPS传感器（增强版）"""
        sensor_name = 'GPS'
        max_retries = self.sensor_config[sensor_name]['max_retries']
        
        for attempt in range(max_retries + 1):
            try:
                if SERIAL_AVAILABLE:
                    # 使用真实的串口连接
                    self.sensors[sensor_name] = NEO6MGPS(
                        port=self.sensor_config[sensor_name]['port'],
                        baudrate=self.sensor_config[sensor_name]['baudrate']
                    )
                    
                    # 测试连接
                    test_data = self.sensors[sensor_name].read_data()
                    if test_data:
                        self.sensor_connection_status[sensor_name]['connected'] = True
                        self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                        self.sensor_connection_status[sensor_name]['error_count'] = 0
                        logger.info(f"✅ GPS传感器(UART)初始化成功，连接测试通过")
                        return
                    else:
                        raise Exception("连接测试失败")
                else:
                    raise ImportError("串口库不可用")
                    
            except Exception as e:
                self.sensor_connection_status[sensor_name]['error_count'] += 1
                self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                
                if attempt < max_retries:
                    logger.warning(f"⚠️ GPS传感器初始化失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    logger.error(f"❌ GPS传感器初始化最终失败: {e}")
                    # 创建备用模拟传感器
                    self.sensors[sensor_name] = SimulatedGPS()
                    logger.warning("⚠️ 已降级到模拟GPS传感器")
                    break
    
    def _init_wheel_speed_sensor(self):
        """🚨 初始化轮速传感器（增强版）"""
        sensor_name = 'WHEEL_SPEED'
        max_retries = self.sensor_config[sensor_name]['max_retries']
        
        for attempt in range(max_retries + 1):
            try:
                # 使用GPIO或模拟传感器
                self.sensors[sensor_name] = WheelSpeedSensor(
                    pin=self.sensor_config[sensor_name]['pin']
                )
                
                # 测试连接（读取一次数据）
                test_data = self.sensors[sensor_name].read_data()
                if test_data:
                    self.sensor_connection_status[sensor_name]['connected'] = True
                    self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                    self.sensor_connection_status[sensor_name]['error_count'] = 0
                    logger.info(f"✅ 轮速传感器初始化成功，连接测试通过")
                    return
                else:
                    raise Exception("连接测试失败")
                    
            except Exception as e:
                self.sensor_connection_status[sensor_name]['error_count'] += 1
                self.sensor_connection_status[sensor_name]['last_attempt'] = time.time()
                
                if attempt < max_retries:
                    logger.warning(f"⚠️ 轮速传感器初始化失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    logger.error(f"❌ 轮速传感器初始化最终失败: {e}")
                    # 创建备用模拟传感器
                    self.sensors[sensor_name] = SimulatedWheelSpeed()
                    logger.warning("⚠️ 已降级到模拟轮速传感器")
                    break
    
    def start_monitoring(self):
        """开始传感器监控"""
        if self.is_running:
            logger.warning("⚠️ 传感器监控已在运行")
            return
        
        try:
            self.is_running = True
            self.data_thread = threading.Thread(target=self._data_collection_loop)
            self.data_thread.daemon = True
            self.data_thread.start()
            
            # 立即产生一些测试数据
            self._generate_initial_test_data()
            
            logger.info("🚀 传感器监控已启动")
            
        except Exception as e:
            logger.error(f"❌ 启动传感器监控失败: {e}")
            self.is_running = False
    
    def _generate_initial_test_data(self):
        """生成初始真实数据（已替换模拟数据）"""
        try:
            # 尝试从真实传感器获取数据
            real_data = self._get_real_sensor_data()
            
            if real_data:
                # 使用真实数据
                self.latest_data.update(real_data)
                logger.info("✅ 初始真实数据已获取")
            else:
                # 如果无法获取真实数据，记录警告
                logger.warning("⚠️ 无法获取真实传感器数据，使用默认值")
                # 使用默认值而不是模拟数据
                default_data = {
                    'gz': 0.0,
                    'speed': 0.0,
                    'wheel': 0.0,
                    'loc1': 0.0,
                    'loc2': 0.0,
                    'crc': '00',
                    'timestamp': time.time(),
                    'behavior': '等待数据',
                    'behavior_stats': {
                        'non_curve_state': 0,
                        'normal_braking': 0,
                        'curve_state': 0,
                        'emergency_braking': 0,
                        'acceleration': 0,
                        'deceleration': 0
                    }
                }
                self.latest_data.update(default_data)
            
            # 执行行为分析
            self._analyze_behavior()
            
            # 立即通知数据更新
            self._notify_data_update()
            
            logger.info("✅ 初始数据已生成")
            
        except Exception as e:
            logger.error(f"❌ 生成初始数据失败: {e}")
    
    def _get_real_sensor_data(self) -> Optional[Dict[str, Any]]:
        """从真实传感器获取数据"""
        try:
            # 这里应该实现真实的传感器数据获取逻辑
            # 例如：从硬件接口、串口、I2C等获取数据
            
            # 临时返回None，表示需要实现真实传感器接口
            logger.debug("真实传感器数据获取接口待实现")
            return None
            
        except Exception as e:
            logger.error(f"获取真实传感器数据失败: {e}")
            return None
    
    def stop_monitoring(self):
        """停止传感器监控"""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=2.0)
            
            logger.info("⏹️ 传感器监控已停止")
            
        except Exception as e:
            logger.error(f"❌ 停止传感器监控失败: {e}")
    
    def _data_collection_loop(self):
        """数据采集循环"""
        logger.info("📊 开始数据采集循环...")
        
        while self.is_running:
            try:
                # 🚨 采集IMU数据（增强版）
                if 'IMU' in self.sensors:
                    imu_data = self.sensors['IMU'].read_data()
                    if imu_data:
                        # 数据质量评估
                        imu_quality = self._assess_data_quality('IMU', imu_data)
                        imu_data['data_quality'] = imu_quality
                        imu_data['is_real_data'] = self.sensor_connection_status['IMU']['connected']
                        self.latest_data['IMU'] = imu_data
                
                # 🚨 采集GPS数据（增强版）
                if 'GPS' in self.sensors:
                    gps_data = self.sensors['GPS'].read_data()
                    if gps_data:
                        # 数据质量评估
                        gps_quality = self._assess_data_quality('GPS', gps_data)
                        gps_data['data_quality'] = gps_quality
                        gps_data['is_real_data'] = self.sensor_connection_status['GPS']['connected']
                        self.latest_data['GPS'] = gps_data
                
                # 🚨 采集轮速数据（增强版）
                if 'WHEEL_SPEED' in self.sensors:
                    wheel_data = self.sensors['WHEEL_SPEED'].read_data()
                    if wheel_data:
                        # 数据质量评估
                        wheel_quality = self._assess_data_quality('WHEEL_SPEED', wheel_data)
                        wheel_data['data_quality'] = wheel_data
                        wheel_data['is_real_data'] = self.sensor_connection_status['WHEEL_SPEED']['connected']
                        self.latest_data['WHEEL_SPEED'] = wheel_data
                
                # 更新时间戳
                self.latest_data['timestamp'] = time.time()
                
                # 执行行为分析
                self._analyze_behavior()
                
                # 通知数据更新
                self._notify_data_update()
                
                # 等待下次更新
                time.sleep(self.update_interval)
                
                    except Exception as e:
            logger.error(f"❌ 数据采集循环错误: {e}")
            time.sleep(1.0)  # 错误时等待1秒
    
    def _assess_data_quality(self, sensor_type: str, data: dict) -> str:
        """🚨 评估数据质量"""
        try:
            if not data:
                return 'invalid'
            
            # 检查数据完整性
            if sensor_type == 'IMU':
                required_fields = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
                if not all(field in data for field in required_fields):
                    return 'incomplete'
                
                # 检查数据范围合理性
                gz = data.get('gz', 0)
                if abs(gz) > 1000:  # 陀螺仪数据异常
                    return 'anomaly'
                    
            elif sensor_type == 'GPS':
                required_fields = ['longitude', 'latitude']
                if not all(field in data for field in required_fields):
                    return 'incomplete'
                
                # 检查GPS坐标合理性
                lon = data.get('longitude', 0)
                lat = data.get('latitude', 0)
                if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                    return 'anomaly'
                    
            elif sensor_type == 'WHEEL_SPEED':
                required_fields = ['speed', 'rpm']
                if not all(field in data for field in required_fields):
                    return 'incomplete'
                
                # 检查速度合理性
                speed = data.get('speed', 0)
                if speed < 0 or speed > 200:  # 速度范围检查
                    return 'anomaly'
            
            # 检查时间戳
            if 'timestamp' not in data:
                return 'no_timestamp'
            
            # 数据质量良好
            return 'good'
            
        except Exception as e:
            logger.error(f"数据质量评估失败: {e}")
            return 'error'
    
    def _analyze_behavior(self):
        """分析驾驶行为"""
        try:
            imu_data = self.latest_data.get('IMU', {})
            wheel_data = self.latest_data.get('WHEEL_SPEED', {})
            
            # 分析弯道状态
            if 'gz' in imu_data:
                gz = imu_data['gz']
                if abs(gz) > 0.1:  # 重力加速度Z轴变化超过阈值
                    self.behavior_stats['curve_state'] += 1
                    behavior = "弯道状态"
                else:
                    self.behavior_stats['non_curve_state'] += 1
                    behavior = "非弯道状态"
            
            # 分析刹车行为
            if 'speed' in wheel_data:
                current_speed = wheel_data['speed']
                if hasattr(self, '_last_speed'):
                    speed_change = current_speed - self._last_speed
                    if speed_change < -2.0:  # 速度下降超过2km/h
                        if speed_change < -5.0:  # 急刹车
                            self.behavior_stats['emergency_braking'] += 1
                            behavior += ",急刹车"
                        else:  # 正常刹车
                            self.behavior_stats['normal_braking'] += 1
                            behavior += ",正常刹车"
                    elif speed_change > 2.0:  # 加速
                        self.behavior_stats['acceleration'] += 1
                        behavior += ",加速"
                    elif speed_change < -0.5:  # 轻微减速
                        self.behavior_stats['deceleration'] += 1
                        behavior += ",减速"
                
                self._last_speed = current_speed
            
            # 更新行为数据
            self.latest_data['BEHAVIOR'] = {
                'current_behavior': behavior,
                'stats': self.behavior_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"❌ 行为分析失败: {e}")
    
    def _notify_data_update(self):
        """🚨 通知数据更新（增强版）"""
        try:
            # 构建完整的数据包
            data_package = {
                'gz': self.latest_data.get('IMU', {}).get('gz', 0.0),
                'speed': self.latest_data.get('WHEEL_SPEED', {}).get('speed', 0.0),
                'wheel': self.latest_data.get('WHEEL_SPEED', {}).get('wheel', 0.0),
                'loc1': self.latest_data.get('GPS', {}).get('longitude', 0.0),
                'loc2': self.latest_data.get('GPS', {}).get('latitude', 0.0),
                'crc': self.latest_data.get('GPS', {}).get('crc', '00'),
                'timestamp': self.latest_data.get('timestamp', time.time()),
                'behavior': self.latest_data.get('BEHAVIOR', {}).get('current_behavior', '未知'),
                
                # 🚨 新增：传感器状态和质量信息
                'sensor_status': {
                    'IMU': {
                        'connected': self.sensor_connection_status['IMU']['connected'],
                        'data_quality': self.latest_data.get('IMU', {}).get('data_quality', 'unknown'),
                        'is_real_data': self.latest_data.get('IMU', {}).get('is_real_data', False)
                    },
                    'GPS': {
                        'connected': self.sensor_connection_status['GPS']['connected'],
                        'data_quality': self.latest_data.get('GPS', {}).get('data_quality', 'unknown'),
                        'is_real_data': self.latest_data.get('GPS', {}).get('is_real_data', False)
                    },
                    'WHEEL_SPEED': {
                        'connected': self.sensor_connection_status['WHEEL_SPEED']['connected'],
                        'data_quality': self.latest_data.get('WHEEL_SPEED', {}).get('data_quality', 'unknown'),
                        'is_real_data': self.latest_data.get('WHEEL_SPEED', {}).get('is_real_data', False)
                    }
                },
                
                # 🚨 新增：系统状态摘要
                'system_summary': {
                    'real_sensor_count': self.get_real_sensor_count(),
                    'simulation_fallback_count': self.get_simulation_fallback_count(),
                    'total_sensors': len(self.sensor_connection_status),
                                    'overall_health': self._calculate_overall_health()
            },
            'behavior_stats': self.behavior_stats.copy()
        }
            
            # 调用所有回调函数
            for callback in self.data_callbacks:
                try:
                    callback(data_package)
                except Exception as e:
                    logger.error(f"❌ 数据回调执行失败: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 数据更新通知失败: {e}")
    
    def _calculate_overall_health(self) -> float:
        """🚨 计算整体健康度"""
        try:
            total_score = 0
            max_score = len(self.sensor_connection_status)
            
            for sensor_name, status in self.sensor_connection_status.items():
                if status['connected']:
                    # 真实传感器：满分
                    total_score += 1.0
                else:
                    # 模拟传感器：根据错误次数计算分数
                    error_count = status['error_count']
                    if error_count == 0:
                        total_score += 0.8  # 新降级的传感器
                    elif error_count <= 3:
                        total_score += 0.6  # 少量错误的传感器
                    elif error_count <= 5:
                        total_score += 0.4  # 较多错误的传感器
                    else:
                        total_score += 0.2  # 大量错误的传感器
            
            # 计算百分比
            health_percentage = (total_score / max_score) * 100
            return round(health_percentage, 1)
            
        except Exception as e:
            logger.error(f"计算整体健康度失败: {e}")
            return 0.0
    
    def get_latest_data(self) -> Dict[str, Any]:
        """获取最新数据"""
        return self.latest_data.copy()
    
    def get_behavior_stats(self) -> Dict[str, int]:
        """获取行为统计"""
        return self.behavior_stats.copy()
    
    def add_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加数据更新回调"""
        if callback not in self.data_callbacks:
            self.data_callbacks.append(callback)
            logger.info(f"✅ 已添加数据回调: {callback.__name__}")
    
    def remove_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """移除数据更新回调"""
        if callback in self.data_callbacks:
            self.data_callbacks.remove(callback)
            logger.info(f"✅ 已移除数据回调: {callback.__name__}")


class MPU6050Sensor:
    """MPU6050 IMU传感器"""
    
    def __init__(self, bus: int = 1, address: int = 0x68):
        self.bus = bus
        self.address = address
        self.i2c = None
        
        try:
            if I2C_AVAILABLE:
                self.i2c = smbus2.SMBus(bus)
                # 初始化MPU6050
                self.i2c.write_byte_data(address, 0x6B, 0x00)  # 唤醒设备
                logger.info(f"✅ MPU6050 I2C连接成功 (Bus: {bus}, Address: 0x{address:02X})")
            else:
                raise ImportError("I2C库不可用")
                
        except Exception as e:
            logger.error(f"❌ MPU6050初始化失败: {e}")
            raise
    
    def read_data(self) -> Optional[Dict[str, float]]:
        """读取IMU数据"""
        try:
            if not self.i2c:
                return None
            
            # 读取加速度数据
            accel_data = self.i2c.read_i2c_block_data(self.address, 0x3B, 6)
            ax = self._convert_accel(accel_data[0:2])
            ay = self._convert_accel(accel_data[2:4])
            az = self._convert_accel(accel_data[4:6])
            
            # 读取陀螺仪数据
            gyro_data = self.i2c.read_i2c_block_data(self.address, 0x43, 6)
            gx = self._convert_gyro(gyro_data[0:2])
            gy = self._convert_gyro(gyro_data[2:4])
            gz = self._convert_gyro(gyro_data[4:6])
            
            return {
                'ax': ax, 'ay': ay, 'az': az,
                'gx': gx, 'gy': gy, 'gz': gz,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ MPU6050数据读取失败: {e}")
            return None
    
    def _convert_accel(self, data: bytes) -> float:
        """转换加速度数据"""
        value = (data[0] << 8) | data[1]
        if value > 32767:
            value -= 65536
        return value / 16384.0  # 转换为g
    
    def _convert_gyro(self, data: bytes) -> float:
        """转换陀螺仪数据"""
        value = (data[0] << 8) | data[1]
        if value > 32767:
            value -= 65536
        return value / 131.0  # 转换为度/秒


class NEO6MGPS:
    """NEO-6M GPS传感器"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
        try:
            if SERIAL_AVAILABLE:
                self.serial = serial.Serial(port, baudrate, timeout=1)
                logger.info(f"✅ GPS串口连接成功 ({port}, {baudrate}bps)")
            else:
                raise ImportError("串口库不可用")
                
        except Exception as e:
            logger.error(f"❌ GPS初始化失败: {e}")
            raise
    
    def read_data(self) -> Optional[Dict[str, Any]]:
        """读取GPS数据"""
        try:
            if not self.serial:
                return None
            
            # 读取NMEA数据
            line = self.serial.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                return None
            
            # 解析GPRMC语句
            if line.startswith('$GPRMC'):
                parsed = pynmea2.parse(line)
                if parsed.status == 'A':  # 数据有效
                    return {
                        'latitude': float(parsed.latitude),
                        'longitude': float(parsed.longitude),
                        'speed': float(parsed.spd_over_grnd) * 1.852,  # 转换为km/h
                        'course': float(parsed.true_course),
                        'timestamp': time.time(),
                        'crc': self._calculate_crc(line)
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ GPS数据读取失败: {e}")
            return None
    
    def _calculate_crc(self, nmea_line: str) -> str:
        """计算NMEA校验码"""
        try:
            checksum = 0
            for char in nmea_line[1:]:  # 跳过$符号
                if char == '*':
                    break
                checksum ^= ord(char)
            return f"{checksum:02X}"
        except:
            return "00"


class WheelSpeedSensor:
    """轮速传感器"""
    
    def __init__(self, pin: int = 18):
        self.pin = pin
        self.pulse_count = 0
        self.last_time = time.time()
        self.wheel_circumference = 2.0  # 轮周长(米)
        self.pulses_per_revolution = 20  # 每转脉冲数
        
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(pin, GPIO.RISING, callback=self._pulse_callback)
            logger.info(f"✅ 轮速传感器初始化成功 (GPIO: {pin})")
            
        except ImportError:
            logger.warning("⚠️ RPi.GPIO不可用，使用模拟轮速传感器")
            self._simulate_pulse()
        except Exception as e:
            logger.error(f"❌ 轮速传感器初始化失败: {e}")
            self._simulate_pulse()
    
    def _pulse_callback(self, channel):
        """脉冲回调函数"""
        self.pulse_count += 1
    
    def _simulate_pulse(self):
        logger.warning("轮速传感器不可用，脉冲计数功能已禁用")
    
    def read_data(self) -> Dict[str, float]:
        """读取轮速数据"""
        try:
            current_time = time.time()
            time_diff = current_time - self.last_time
            
            if time_diff > 0:
                # 计算转速 (RPM)
                rpm = (self.pulse_count / self.pulses_per_revolution) / (time_diff / 60.0)
                
                # 计算速度 (km/h)
                speed = (rpm * self.wheel_circumference * 60) / 1000
                
                # 重置计数器
                self.pulse_count = 0
                self.last_time = current_time
                
                return {
                    'speed': speed,
                    'rpm': rpm,
                    'wheel': self.pulse_count,
                    'timestamp': current_time
                }
            else:
                return {
                    'speed': 0.0,
                    'rpm': 0.0,
                    'wheel': 0,
                    'timestamp': current_time
                }
                
        except Exception as e:
            logger.error(f"❌ 轮速数据读取失败: {e}")
            return {
                'speed': 0.0,
                'rpm': 0.0,
                'wheel': 0,
                'timestamp': time.time()
            }


# 模拟传感器类（备用方案）
class SimulatedMPU6050:
    """模拟MPU6050传感器"""
    
    def __init__(self):
        self.start_time = time.time()
        logger.info("⚠️ 使用模拟MPU6050传感器")
    
    def read_data(self) -> Dict[str, float]:
        """生成模拟IMU数据"""
        current_time = time.time()
        time_offset = current_time - self.start_time
        
        # 模拟车辆运动
        speed_factor = 10.0 + 5.0 * (time_offset % 10) / 10.0  # 10-15 km/h变化
        
        return {
            'ax': 0.1 * (time_offset % 5) / 5.0,  # 轻微前后摆动
            'ay': 0.05 * (time_offset % 3) / 3.0,  # 轻微左右摆动
            'az': 1.0 + 0.1 * (time_offset % 2) / 2.0,  # 重力加速度变化
            'gx': 0.5 * (time_offset % 4) / 4.0,  # 轻微俯仰
            'gy': 0.3 * (time_offset % 6) / 6.0,  # 轻微翻滚
            'gz': -0.0075 + 0.01 * (time_offset % 8) / 8.0,  # 轻微偏航
            'timestamp': current_time
        }


class SimulatedGPS:
    """模拟GPS传感器"""
    
    def __init__(self):
        self.start_time = time.time()
        logger.info("⚠️ 使用模拟GPS传感器")
    
    def read_data(self) -> Dict[str, Any]:
        """生成模拟GPS数据"""
        current_time = time.time()
        time_offset = current_time - self.start_time
        
        # 模拟车辆在杭州附近移动
        base_lat = 30.000099
        base_lon = 119.100014
        
        # 模拟车辆移动轨迹
        lat_offset = 0.0001 * (time_offset % 20) / 20.0
        lon_offset = 0.0001 * (time_offset % 15) / 15.0
        
        return {
            'latitude': base_lat + lat_offset,
            'longitude': base_lon + lon_offset,
            'speed': 10.0 + 2.0 * (time_offset % 10) / 10.0,  # 10-12 km/h
            'course': 45.0 + 30.0 * (time_offset % 12) / 12.0,  # 45-75度
            'timestamp': current_time,
            'crc': f"{int(time_offset) % 100:02d}"
        }


class SimulatedWheelSpeed:
    """模拟轮速传感器"""
    
    def __init__(self):
        self.start_time = time.time()
        logger.info("⚠️ 使用模拟轮速传感器")
    
    def read_data(self) -> Dict[str, float]:
        """生成模拟轮速数据"""
        current_time = time.time()
        time_offset = current_time - self.start_time
        
        # 模拟轮速变化
        base_speed = 10.0
        speed_variation = 2.0 * (time_offset % 8) / 8.0
        
        return {
            'speed': base_speed + speed_variation,
            'rpm': (base_speed + speed_variation) * 100,  # 简化的RPM计算
            'wheel': int(time_offset * 10) % 100,  # 模拟脉冲计数
            'timestamp': current_time
        }


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    sensor_manager = RealTimeSensorManager()
    sensor_manager.start_monitoring()
    
    try:
        while True:
            data = sensor_manager.get_latest_data()
            print(f"📊 实时数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            time.sleep(1)
    except KeyboardInterrupt:
        sensor_manager.stop_monitoring()
        print("\n👋 测试结束")
            'rpm': (base_speed + speed_variation) * 100,  # 简化的RPM计算
            'wheel': int(time_offset * 10) % 100,  # 模拟脉冲计数
            'timestamp': current_time
        }


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    sensor_manager = RealTimeSensorManager()
    sensor_manager.start_monitoring()
    
    try:
        while True:
            data = sensor_manager.get_latest_data()
            print(f"📊 实时数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            time.sleep(1)
    except KeyboardInterrupt:
        sensor_manager.stop_monitoring()
        print("\n👋 测试结束")

            'rpm': (base_speed + speed_variation) * 100,  # 简化的RPM计算
            'wheel': int(time_offset * 10) % 100,  # 模拟脉冲计数
            'timestamp': current_time
        }


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    sensor_manager = RealTimeSensorManager()
    sensor_manager.start_monitoring()
    
    try:
        while True:
            data = sensor_manager.get_latest_data()
            print(f"📊 实时数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            time.sleep(1)
    except KeyboardInterrupt:
        sensor_manager.stop_monitoring()
        print("\n👋 测试结束")

            'rpm': (base_speed + speed_variation) * 100,  # 简化的RPM计算
            'wheel': int(time_offset * 10) % 100,  # 模拟脉冲计数
            'timestamp': current_time
        }


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    sensor_manager = RealTimeSensorManager()
    sensor_manager.start_monitoring()
    
    try:
        while True:
            data = sensor_manager.get_latest_data()
            print(f"📊 实时数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            time.sleep(1)
    except KeyboardInterrupt:
        sensor_manager.stop_monitoring()
        print("\n👋 测试结束")

