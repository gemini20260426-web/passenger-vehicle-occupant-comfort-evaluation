#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源同步核心引擎
整合时间对齐和数据融合功能，提供完整的同步解决方案

主要功能：
- 智能时间同步
- 自适应数据融合
- 实时性能监控
- 异常检测和处理

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
import threading
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# 导入核心组件
from .time_aligner import IntelligentTimeAligner, SyncStrategy
from .data_fusion import AdaptiveDataFusion, FusionAlgorithm
from .utils.async_processor import AsyncDataProcessor
from .data_source_interfaces import DataSourceSample # Added for _collect_real_source_data
from ..parallel_data_processor import ParallelDataProcessor
from ..intelligent_data_router import IntelligentDataRouter

logger = logging.getLogger(__name__)


class SyncEngineStatus(Enum):
    """同步引擎状态枚举"""
    IDLE = "idle"                    # 空闲状态
    INITIALIZING = "initializing"     # 初始化中
    RUNNING = "running"              # 运行中
    PAUSED = "paused"                # 暂停状态
    ERROR = "error"                   # 错误状态
    SHUTDOWN = "shutdown"             # 关闭状态


@dataclass
class SyncEngineMetrics:
    """同步引擎性能指标"""
    total_sources: int = 0           # 总数据源数量
    active_sources: int = 0          # 活跃数据源数量
    sync_frequency: float = 0.0      # 同步频率 (Hz)
    avg_latency: float = 0.0         # 平均延迟 (ms)
    sync_quality: float = 0.0        # 同步质量 (0-1)
    fusion_quality: float = 0.0      # 融合质量 (0-1)
    error_rate: float = 0.0          # 错误率
    timestamp: float = 0.0           # 时间戳


class MultiSourceSyncEngine:
    """多源同步核心引擎"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 配置参数
        self.config = config or self._get_default_config()
        
        # 从配置中获取组件实例
        self.config_manager = self.config.get('config_manager')
        self.performance_monitor = self.config.get('performance_monitor')
        self.anomaly_detector = self.config.get('anomaly_detector')
        
        # 核心组件
        self.time_aligner = IntelligentTimeAligner()
        self.data_fusion = AdaptiveDataFusion()
        self.async_processor = AsyncDataProcessor(
            max_workers=self.config.get('max_workers', 4),
            auto_start_monitor=False  # 禁用自动启动性能监控
        )
        self.data_processor = ParallelDataProcessor()
        self.data_router = IntelligentDataRouter()
        
        # 状态管理
        self.status = SyncEngineStatus.IDLE
        self.status_lock = threading.Lock()
        
        # 数据源管理
        self.data_sources = {}
        self.source_status = {}
        
        # 性能监控
        self.metrics = SyncEngineMetrics()
        self.metrics_history = []
        self.monitoring_enabled = True
        self.monitoring_thread = None
        
        # 同步控制
        self.sync_interval = self.config.get('sync_interval', 0.05)  # 调整为20Hz
        self.sync_thread = None
        self.is_syncing = False
        
        # 启动性能监控
        self.start_performance_monitoring()
        
        logger.info("多源同步核心引擎已初始化")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'max_workers': 4,
            'sync_interval': 0.01,  # 100Hz
            'max_latency': 0.05,    # 50ms
            'quality_threshold': 0.8,
            'auto_recovery': True,
            'performance_monitoring': True
        }
    
    def add_data_source(self, source_id: str, source_config: Dict[str, Any]) -> bool:
        """添加数据源"""
        try:
            with self.status_lock:
                if source_id in self.data_sources:
                    logger.warning(f"数据源 {source_id} 已存在，将被覆盖")
                
                self.data_sources[source_id] = source_config
                self.source_status[source_id] = {
                    'is_active': True,
                    'last_update': time.time(),
                    'error_count': 0,
                    'quality_score': 0.5
                }
                
                logger.info(f"数据源 {source_id} 已添加")
                return True
                
        except Exception as e:
            logger.error(f"添加数据源 {source_id} 失败: {e}")
            return False
    
    def remove_data_source(self, source_id: str) -> bool:
        """移除数据源"""
        try:
            with self.status_lock:
                if source_id in self.data_sources:
                    del self.data_sources[source_id]
                    del self.source_status[source_id]
                    logger.info(f"数据源 {source_id} 已移除")
                    return True
                else:
                    logger.warning(f"数据源 {source_id} 不存在")
                    return False
                    
        except Exception as e:
            logger.error(f"移除数据源 {source_id} 失败: {e}")
            return False
    
    def start_sync(self, source_ids: Optional[List[str]] = None) -> bool:
        """启动同步
        
        Args:
            source_ids: 要启动的数据源ID列表，如果为None则启动所有数据源
        """
        try:
            with self.status_lock:
                if self.status == SyncEngineStatus.RUNNING:
                    logger.warning("同步引擎已在运行中")
                    return False
                
                # 如果没有指定数据源，使用所有可用的数据源
                if source_ids is None:
                    source_ids = list(self.data_sources.keys())
                
                if not source_ids:
                    logger.error("没有可用的数据源")
                    return False
                
                # 验证数据源是否存在
                valid_sources = [sid for sid in source_ids if sid in self.data_sources]
                if not valid_sources:
                    logger.error(f"指定的数据源不存在: {source_ids}")
                    return False
                
                # 更新状态
                self.status = SyncEngineStatus.INITIALIZING
                
                # 启动同步线程
                self.is_syncing = True
                self.sync_thread = threading.Thread(
                    target=self._sync_worker,
                    daemon=True
                )
                self.sync_thread.start()
                
                # 更新状态
                self.status = SyncEngineStatus.RUNNING
                
                logger.info(f"同步引擎已启动，数据源: {valid_sources}")
                return True
                
        except Exception as e:
            logger.error(f"启动同步失败: {e}")
            self.status = SyncEngineStatus.ERROR
            return False
    
    def stop_sync(self) -> bool:
        """停止同步"""
        try:
            with self.status_lock:
                if self.status != SyncEngineStatus.RUNNING:
                    logger.warning("同步引擎未在运行")
                    return False
                
                # 更新状态
                self.status = SyncEngineStatus.SHUTDOWN
                
                # 停止同步线程
                self.is_syncing = False
                if self.sync_thread:
                    self.sync_thread.join(timeout=2.0)
                
                # 更新状态
                self.status = SyncEngineStatus.IDLE
                
                logger.info("同步引擎已停止")
                return True
                
        except Exception as e:
            logger.error(f"停止同步失败: {e}")
            return False
    
    def pause_sync(self) -> bool:
        """暂停同步"""
        try:
            with self.status_lock:
                if self.status != SyncEngineStatus.RUNNING:
                    logger.warning("同步引擎未在运行")
                    return False
                
                self.status = SyncEngineStatus.PAUSED
                logger.info("同步引擎已暂停")
                return True
                
        except Exception as e:
            logger.error(f"暂停同步失败: {e}")
            return False
    
    def resume_sync(self) -> bool:
        """恢复同步"""
        try:
            with self.status_lock:
                if self.status != SyncEngineStatus.PAUSED:
                    logger.warning("同步引擎未处于暂停状态")
                    return False
                
                self.status = SyncEngineStatus.RUNNING
                logger.info("同步引擎已恢复")
                return True
                
        except Exception as e:
            logger.error(f"恢复同步失败: {e}")
            return False
    
    def _sync_worker(self):
        """同步工作线程"""
        try:
            while self.is_syncing:
                # 检查状态
                with self.status_lock:
                    if self.status == SyncEngineStatus.PAUSED:
                        time.sleep(0.1)
                        continue
                    elif self.status == SyncEngineStatus.SHUTDOWN:
                        break
                
                # 执行同步周期
                self._sync_cycle()
                
                # 等待下一个同步周期
                time.sleep(self.sync_interval)
                
        except Exception as e:
            logger.error(f"同步工作线程错误: {e}")
            with self.status_lock:
                self.status = SyncEngineStatus.ERROR
    
    def _sync_cycle(self):
        """执行同步周期"""
        try:
            start_time = time.time()
            
            # 1. 收集数据源数据
            source_data = self._collect_source_data()
            
            if not source_data:
                logger.warning("未收集到数据源数据")
                return
            
            # 2. 时间同步 - 转换数据格式
            formatted_source_data = self._format_data_for_time_alignment(source_data)
            # 确保执行时间对齐
            aligned_data = self.time_aligner.align_data(formatted_source_data)
            
            if not aligned_data:
                logger.warning("时间同步失败")
                return
            
            # 3. 数据融合
            fused_data = self.data_fusion.fuse_data(aligned_data)
            
            if not fused_data:
                logger.warning("数据融合失败")
                return
            
            # 4. 异步处理（使用同步方式）
            processed_data = self.async_processor.process_data_stream_sync(fused_data)
            
            # 5. 更新性能指标
            sync_time = time.time() - start_time
            self._update_sync_metrics(sync_time, len(source_data))
            
            # 6. 检查数据质量
            self._check_data_quality(aligned_data, fused_data)
            
        except Exception as e:
            logger.error(f"同步周期执行失败: {e}")
            self._handle_sync_error(e)
    
    def _collect_source_data(self) -> Dict[str, Any]:
        """收集数据源数据"""
        source_data = {}
        current_time = time.time()
        
        for source_id, source_config in self.data_sources.items():
            try:
                # 检查数据源状态
                if not self.source_status[source_id]['is_active']:
                    continue
                
                # 🚨 真实数据收集（替换模拟模块）
                data = self._collect_real_source_data(source_id, source_config)
                
                if data:
                    # 将DataSourceSample列表包装成正确的格式
                    source_data[source_id] = {
                        'data': data,
                        'type': source_config.get('type', 'unknown'),
                        'quality_score': 0.9
                    }
                    
                    # 更新状态
                    self.source_status[source_id]['last_update'] = current_time
                    self.source_status[source_id]['error_count'] = 0
                
            except Exception as e:
                logger.error(f"收集数据源 {source_id} 数据失败: {e}")
                self._handle_source_error(source_id, e)
        
        return source_data
    
    def _format_data_for_time_alignment(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化数据用于时间同步"""
        formatted_data = {}
        
        for source_id, data in source_data.items():
            try:
                # 提取时间戳和数据值
                if isinstance(data, dict) and 'data' in data:
                    # 从真实数据源获取的数据
                    real_data = data['data']
                    if isinstance(real_data, list) and len(real_data) > 0:
                        # 提取时间戳和值
                        timestamps = []
                        values = []
                        
                        for item in real_data:
                            if hasattr(item, 'timestamp'):
                                timestamps.append(item.timestamp)
                                values.append(item.data)
                            elif isinstance(item, dict):
                                timestamps.append(item.get('timestamp', time.time()))
                                values.append(item.get('data', item.get('value', 0)))
                            else:
                                # 如果没有时间戳，使用当前时间
                                timestamps.append(time.time())
                                values.append(item)
                        
                        formatted_data[source_id] = {
                            'id': source_id,
                            'type': data.get('type', 'unknown'),
                            'timestamps': timestamps,
                            'values': values,
                            'quality': data.get('quality_score', 0.9)
                        }
                    else:
                        # 单个数据点
                        timestamp = data.get('timestamp', time.time())
                        value = real_data if not isinstance(real_data, (list, dict)) else 0
                        
                        formatted_data[source_id] = {
                            'id': source_id,
                            'type': data.get('type', 'unknown'),
                            'timestamps': [timestamp],
                            'values': [value],
                            'quality': data.get('quality_score', 0.9)
                        }
                elif isinstance(data, dict) and 'timestamps' in data and 'values' in data:
                    # 已经是正确格式的数据
                    formatted_data[source_id] = {
                        'id': source_id,
                        'type': data.get('type', 'unknown'),
                        'timestamps': data['timestamps'],
                        'values': data['values'],
                        'quality': data.get('quality_score', 0.9)
                    }
                else:
                    formatted_data[source_id] = {
                        'id': source_id,
                        'type': 'unknown',
                        'timestamps': [time.time()],
                        'values': [0],
                        'quality': 0.5
                    }
                    
            except Exception as e:
                logger.warning(f"格式化数据源 {source_id} 数据失败: {e}")
                # 添加默认格式
                formatted_data[source_id] = {
                    'id': source_id,
                    'type': 'unknown',
                    'timestamps': [time.time()],
                    'values': [0],
                    'quality': 0.5
                }
        
        return formatted_data
    
    def _collect_real_source_data(self, source_id: str, source_config: dict) -> Optional[List[DataSourceSample]]:
        """收集真实数据源数据"""
        try:
            # 减少不必要的日志记录以提升性能
            if self.config.get('debug', False):
                logger.info(f"🔍 开始收集数据源 {source_id} 的数据...")
                logger.info(f"🔍 数据源配置: {source_config}")
            
            interface = source_config.get('interface')
            if not interface:
                logger.warning(f"⚠️ 数据源 {source_id} 没有接口对象")
                return None
            
            if self.config.get('debug', False):
                logger.info(f"🔍 数据源 {source_id} 接口类型: {type(interface)}")
                logger.info(f"🔍 数据源 {source_id} 接口状态: {getattr(interface, 'is_connected', 'N/A')}")
            
            # 强制获取数据
            if hasattr(interface, 'get_data'):
                if self.config.get('debug', False):
                    logger.info(f"🔍 数据源 {source_id} 接口支持get_data方法")
                    logger.info(f"🔍 调用数据源 {source_id} 的get_data方法...")
                data = interface.get_data()
                if self.config.get('debug', False):
                    logger.info(f"🔍 数据源 {source_id} get_data返回: {type(data)}, 长度: {len(data) if data else 0}")
                
                if data:
                    if self.config.get('debug', False):
                        logger.info(f"✅ 数据源 {source_id} 成功获取 {len(data)} 条数据")
                    return data
                else:
                    logger.warning(f"⚠️ 数据源 {source_id} 没有返回数据")
                    
                    # 对于FileDataSource，尝试强制启动数据流
                    if hasattr(interface, '_force_data_generation'):
                        if self.config.get('debug', False):
                            logger.info(f"🔄 尝试强制启动数据源 {source_id} 的数据流...")
                        interface._force_data_generation()
                        
                        # 再次尝试获取数据
                        time.sleep(0.1)  # 等待数据生成
                        data = interface.get_data()
                        if data:
                            if self.config.get('debug', False):
                                logger.info(f"✅ 强制启动后，数据源 {source_id} 成功获取 {len(data)} 条数据")
                            return data
                    
                    return None
            else:
                logger.warning(f"⚠️ 数据源 {source_id} 接口不支持get_data方法")
                if self.config.get('debug', False):
                    logger.info(f"🔍 接口对象的方法: {[method for method in dir(interface) if not method.startswith('_')]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 收集数据源 {source_id} 数据时出错: {e}")
            if self.config.get('debug', False):
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    def _process_real_data(self, raw_data: List[DataSourceSample], source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理真实数据格式"""
        try:
            if not raw_data:
                return None
            
            # 提取时间戳和数值
            timestamps = []
            values = []
            
            for sample in raw_data:
                if hasattr(sample, 'timestamp') and hasattr(sample, 'data'):
                    timestamps.append(sample.timestamp)
                    # 根据数据类型提取相应的数值
                    data_type = source_config.get('type', 'unknown')
                    if data_type == 'imu':
                        # IMU数据：提取加速度或角速度的模长
                        if 'accelerometer' in sample.data:
                            accel = sample.data['accelerometer']
                            if isinstance(accel, (list, tuple)) and len(accel) >= 3:
                                # 计算加速度模长
                                value = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
                                values.append(value)
                            else:
                                values.append(0.0)
                        elif 'gyroscope' in sample.data:
                            gyro = sample.data['gyroscope']
                            if isinstance(gyro, (list, tuple)) and len(gyro) >= 3:
                                # 计算角速度模长
                                value = (gyro[0]**2 + gyro[1]**2 + gyro[2]**2)**0.5
                                values.append(value)
                            else:
                                values.append(0.0)
                        else:
                            values.append(0.0)
                    elif data_type == 'cnap':
                        # CNAP数据：提取血压或心率
                        if 'systolic_pressure' in sample.data:
                            values.append(sample.data['systolic_pressure'])
                        elif 'pulse_rate' in sample.data:
                            values.append(sample.data['pulse_rate'])
                        else:
                            values.append(0.0)
                    else:
                        # 其他类型：尝试提取第一个数值
                        for key, value in sample.data.items():
                            if isinstance(value, (int, float)):
                                values.append(value)
                                break
                        else:
                            values.append(0.0)
                else:
                    # 如果数据格式不标准，跳过
                    continue
            
            if not timestamps or not values:
                return None
            
            return {
                'id': source_config.get('id', 'unknown'),
                'type': source_config.get('type', 'unknown'),
                'timestamps': timestamps,
                'values': values,
                'quality_score': getattr(raw_data[0], 'quality', 0.8) if raw_data else 0.8,
                'is_real_data': True,
                'data_count': len(raw_data)
            }
            
        except Exception as e:
            logger.error(f"处理真实数据格式失败: {e}")
            return None

    def _simulate_source_data(self, source_id: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        logger.warning(f"数据源 {source_id} 无可用真实数据，已跳过")
        return None
    
    def _create_dynamic_interface(self, source_id: str, source_config: Dict[str, Any]) -> Optional[Any]:
        """动态创建数据源接口"""
        try:
            # 导入数据源接口工厂
            from .data_source_interfaces import DataSourceFactory
            
            # 根据数据源ID推断类型
            interface_type = None
            if source_id == 'DS_001':
                interface_type = 'imu'
            elif source_id == 'DS_002':
                interface_type = 'cnap'
            else:
                # 尝试从配置中推断类型
                data_type = source_config.get('type', '').lower()
                if 'imu' in data_type:
                    interface_type = 'imu'
                elif 'cnap' in data_type:
                    interface_type = 'cnap'
                elif 'mqtt' in data_type:
                    interface_type = 'mqtt'
            
            if not interface_type:
                logger.warning(f"⚠️ 无法推断数据源 {source_id} 的接口类型")
                return None
            
            # 创建接口配置
            interface_config = {
                'source_id': source_id,
                'sampling_rate': 100 if interface_type == 'imu' else 50
            }
            
            # 根据类型添加特定配置
            if interface_type == "imu":
                interface_config.update({
                    'device_path': '/dev/ttyUSB0',
                    'baud_rate': 115200
                })
            elif interface_type == "cnap":
                interface_config.update({
                    'device_path': '/dev/ttyUSB1',
                    'baud_rate': 9600
                })
            elif interface_type == "mqtt":
                interface_config.update({
                    'broker': 'localhost',
                    'port': 1883,
                    'topic': 'data/sensors'
                })
            
            # 创建数据源接口实例
            interface = DataSourceFactory.create_data_source(interface_type, interface_config)
            
            if interface:
                # 连接接口
                if hasattr(interface, 'connect'):
                    interface.connect()
                logger.info(f"✅ 为数据源 {source_id} 动态创建了 {interface_type} 接口")
                return interface
            else:
                logger.error(f"❌ 数据源接口工厂创建 {interface_type} 接口失败")
                return None
                
        except ImportError as e:
            logger.error(f"❌ 导入数据源接口失败: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 动态创建接口失败: {e}")
            return None
    
    def _fallback_to_simulation(self, source_id: str, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        logger.warning(f"数据源 {source_id} 无可用真实数据，已跳过")
        return None
    
    def _handle_source_error(self, source_id: str, error: Exception):
        """处理数据源错误"""
        try:
            # 增加错误计数
            self.source_status[source_id]['error_count'] += 1
            
            # 检查是否需要停用数据源
            max_errors = self.config.get('max_errors', 5)
            if self.source_status[source_id]['error_count'] >= max_errors:
                self.source_status[source_id]['is_active'] = False
                logger.warning(f"数据源 {source_id} 错误过多，已停用")
            
            # 自动恢复（如果启用）
            if self.config.get('auto_recovery', True):
                self._schedule_source_recovery(source_id)
                
        except Exception as e:
            logger.error(f"处理数据源 {source_id} 错误失败: {e}")
    
    def _schedule_source_recovery(self, source_id: str):
        """调度数据源恢复"""
        try:
            # 延迟恢复，避免频繁重试
            recovery_delay = self.config.get('recovery_delay', 30)
            
            def delayed_recovery():
                time.sleep(recovery_delay)
                try:
                    self.source_status[source_id]['is_active'] = True
                    self.source_status[source_id]['error_count'] = 0
                    logger.info(f"数据源 {source_id} 已自动恢复")
                except Exception as e:
                    logger.error(f"数据源 {source_id} 自动恢复失败: {e}")
            
            recovery_thread = threading.Thread(target=delayed_recovery, daemon=True)
            recovery_thread.start()
            
        except Exception as e:
            logger.error(f"调度数据源 {source_id} 恢复失败: {e}")
    
    def _handle_sync_error(self, error: Exception):
        """处理同步错误"""
        try:
            # 记录错误
            logger.error(f"同步错误: {error}")
            
            # 检查是否需要自动恢复
            if self.config.get('auto_recovery', True):
                # 尝试重新初始化组件
                self._reinitialize_components()
            
        except Exception as e:
            logger.error(f"处理同步错误失败: {e}")
    
    def _reinitialize_components(self):
        """重新初始化组件"""
        try:
            logger.info("正在重新初始化组件...")
            
            # 重新初始化时间对齐器
            self.time_aligner = IntelligentTimeAligner()
            
            # 重新初始化数据融合器
            self.data_fusion = AdaptiveDataFusion()
            
            # 重新初始化异步处理器
            self.async_processor = AsyncDataProcessor(
                max_workers=self.config.get('max_workers', 4),
                auto_start_monitor=False  # 禁用自动启动性能监控
            )
            
            logger.info("组件重新初始化完成")
            
        except Exception as e:
            logger.error(f"组件重新初始化失败: {e}")
    
    def _check_data_quality(self, aligned_data: Dict[str, Any], fused_data: Dict[str, Any]):
        """检查数据质量"""
        try:
            # 检查时间同步质量
            if hasattr(self.time_aligner, 'get_performance_summary'):
                time_sync_performance = self.time_aligner.get_performance_summary()
                # 可以基于性能指标调整参数
            
            # 检查数据融合质量
            if hasattr(self.data_fusion, 'get_performance_summary'):
                fusion_performance = self.data_fusion.get_performance_summary()
                # 可以基于性能指标调整参数
            
            # 检查整体质量
            quality_threshold = self.config.get('quality_threshold', 0.8)
            current_quality = self.metrics.sync_quality
            
            if current_quality < quality_threshold:
                logger.warning(f"数据质量低于阈值: {current_quality:.2f} < {quality_threshold}")
                
        except Exception as e:
            logger.error(f"检查数据质量失败: {e}")
    
    def _update_sync_metrics(self, sync_time: float, source_count: int):
        """更新同步性能指标"""
        try:
            # 更新指标
            self.metrics.total_sources = len(self.data_sources)
            self.metrics.active_sources = len([s for s in self.source_status.values() if s['is_active']])
            self.metrics.sync_frequency = 1.0 / max(0.001, sync_time)
            self.metrics.avg_latency = sync_time * 1000  # 转换为毫秒
            self.metrics.timestamp = time.time()
            
            # 计算同步质量（基于活跃数据源比例和延迟）
            active_ratio = self.metrics.active_sources / max(1, self.metrics.total_sources)
            latency_score = max(0, 1 - self.metrics.avg_latency / (self.config.get('max_latency', 0.05) * 1000))
            self.metrics.sync_quality = (active_ratio + latency_score) / 2
            
            # 记录历史
            self.metrics_history.append(self.metrics.__dict__.copy())
            
            # 保持历史记录在合理大小
            if len(self.metrics_history) > 1000:
                self.metrics_history.pop(0)
                
        except Exception as e:
            logger.error(f"更新同步指标失败: {e}")
    
    def start_performance_monitoring(self):
        """启动性能监控"""
        if self.monitoring_enabled and not self.monitoring_thread:
            self.monitoring_thread = threading.Thread(
                target=self._performance_monitoring_worker,
                daemon=True
            )
            self.monitoring_thread.start()
            logger.info("同步引擎性能监控已启动")
    
    def _performance_monitoring_worker(self):
        """性能监控工作线程"""
        while self.monitoring_enabled:
            try:
                # 分析性能指标
                self._analyze_performance_metrics()
                
                # 每30秒分析一次
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                time.sleep(60)
    
    def _analyze_performance_metrics(self):
        """分析性能指标"""
        try:
            if not self.metrics_history:
                return
            
            # 计算平均性能
            recent_metrics = self.metrics_history[-30:]  # 最近30个指标
            
            avg_sync_quality = np.mean([m['sync_quality'] for m in recent_metrics])
            avg_latency = np.mean([m['avg_latency'] for m in recent_metrics])
            avg_error_rate = np.mean([m['error_rate'] for m in recent_metrics])
            
            # 记录性能分析结果
            logger.info(f"性能分析 - 平均同步质量: {avg_sync_quality:.3f}, "
                       f"平均延迟: {avg_latency:.2f}ms, "
                       f"平均错误率: {avg_error_rate:.3f}")
            
            # 检查性能阈值
            if avg_sync_quality < 0.7:
                logger.warning("同步质量持续偏低，建议检查数据源状态")
            
            if avg_latency > 50:
                logger.warning("同步延迟持续偏高，建议优化配置")
                
        except Exception as e:
            logger.error(f"分析性能指标失败: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        with self.status_lock:
            return {
                'status': self.status.value,
                'total_sources': len(self.data_sources),
                'active_sources': len([s for s in self.source_status.values() if s['is_active']]),
                'is_syncing': self.is_syncing,
                'sync_interval': self.sync_interval,
                'config': self.config.copy()
            }
    
    def get_performance_metrics(self) -> SyncEngineMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_performance_history(self, count: int = None) -> List[Dict[str, Any]]:
        """获取性能历史"""
        if count is None:
            return self.metrics_history.copy()
        else:
            return self.metrics_history[-count:]
    
    def get_data_source_status(self) -> Dict[str, Any]:
        """获取数据源状态"""
        return self.source_status.copy()
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 更新配置
            self.config.update(new_config)
            
            # 应用新配置
            if 'max_workers' in new_config:
                self.async_processor = AsyncDataProcessor(
                    max_workers=new_config['max_workers'],
                    auto_start_monitor=False  # 禁用自动启动性能监控
                )
            
            if 'sync_interval' in new_config:
                self.sync_interval = new_config['sync_interval']
            
            logger.info("配置已更新")
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def shutdown(self):
        """关闭同步引擎"""
        try:
            # 停止同步
            if self.status == SyncEngineStatus.RUNNING:
                self.stop_sync()
            
            # 停止性能监控
            self.monitoring_enabled = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            
            # 关闭组件
            self.time_aligner.shutdown()
            self.data_fusion.shutdown()
            self.async_processor.shutdown()
            
            # 更新状态
            with self.status_lock:
                self.status = SyncEngineStatus.SHUTDOWN
            
            logger.info("同步引擎已关闭")
            
        except Exception as e:
            logger.error(f"关闭同步引擎失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建同步引擎
    engine = MultiSourceSyncEngine()
    
    # 添加数据源
    engine.add_data_source('imu_source', {
        'type': 'imu',
        'sampling_rate': 100,
        'quality_score': 0.9
    })
    
    engine.add_data_source('cnap_source', {
        'type': 'cnap',
        'sampling_rate': 1,
        'quality_score': 0.85
    })
    
    # 启动同步
    engine.start_sync()
    
    try:
        # 运行10秒
        import time
        time.sleep(10)
        
        # 获取状态
        status = engine.get_sync_status()


        logger.info(f"同步状态: {status}")
        
        # 获取性能指标
        metrics = engine.get_performance_metrics()
        logger.info(f"性能指标: {metrics}")
        
        # 停止同步
        engine.stop_sync()
        
    except KeyboardInterrupt:
        engine.stop_sync()
    
    # 关闭引擎
    engine.shutdown()
