#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源异构数据同步管理器
支持同时加载IMU和CNAP两种数据类型，实现依次加载处理模式
"""

import logging
import threading
import time
import queue
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import traceback

from .rule_config import RuleConfigurationManager
from .data_parser import IMUDataParser
from .cnap_parser import CNAPDataParser


class DataSource:
    """数据源基类"""
    
    def __init__(self, source_id: str, config: dict):
        self.source_id = source_id
        self.config = config
        self.is_active = False
        self.last_data = None
        self.last_timestamp = None
        self.data_count = 0
        self.error_count = 0
        self.logger = logging.getLogger(f"{__name__}.{source_id}")
        
        # 创建解析器
        self.parser = self._create_parser()
        
    def _create_parser(self):
        """创建数据解析器"""
        try:
            data_types = self.config.get('data_types', [])
            parser_type = self.config.get('parser_type', 'auto_detect')
            
            if parser_type == 'dedicated':
                # 专用解析器
                if 'imu' in data_types:
                    return IMUDataParser()
                elif 'cnap' in data_types:
                    return CNAPDataParser()
                else:
                    # 自动检测
                    return self._auto_detect_parser()
            else:
                # 通用解析器
                return self._create_generic_parser(parser_type)
                
        except Exception as e:
            self.logger.error(f"创建解析器失败: {e}")
            return None
    
    def _auto_detect_parser(self):
        """自动检测解析器类型"""
        # 这里可以实现自动检测逻辑
        # 暂时返回IMU解析器作为默认
        return IMUDataParser()
    
    def _create_generic_parser(self, parser_type: str):
        """创建通用解析器"""
        # 这里可以实现通用解析器的创建
        # 暂时返回None
        return None
    
    def start(self):
        """启动数据源"""
        try:
            self.is_active = True
            self.logger.info(f"数据源 {self.source_id} 已启动")
            return True
        except Exception as e:
            self.logger.error(f"启动数据源失败: {e}")
            return False
    
    def stop(self):
        """停止数据源"""
        try:
            self.is_active = False
            self.logger.info(f"数据源 {self.source_id} 已停止")
            return True
        except Exception as e:
            self.logger.error(f"停止数据源失败: {e}")
            return False
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """获取最新数据"""
        return self.last_data
    
    def get_status(self) -> Dict[str, Any]:
        """获取数据源状态"""
        return {
            'source_id': self.source_id,
            'is_active': self.is_active,
            'data_count': self.data_count,
            'error_count': self.error_count,
            'last_timestamp': self.last_timestamp,
            'config': self.config
        }


class FileDataSource(DataSource):
    """文件数据源"""
    
    def __init__(self, source_id: str, config: dict):
        super().__init__(source_id, config)
        self.file_path = config.get('config', {}).get('file_path', '')
        self.encoding = config.get('config', {}).get('encoding', 'utf-8')
        self.chunk_size = config.get('config', {}).get('chunk_size', 10000)  # 修复: 增加默认chunk_size
        self.read_interval = config.get('config', {}).get('read_interval', 0.00001)  # 修复: 进一步减少读取间隔到0.01ms
        self.max_lines = config.get('config', {}).get('max_lines', 0)  # 修复: 添加最大行数限制
        self.file_reader = None
        
    def start(self):
        """启动文件数据源"""
        try:
            if not self.file_path:
                raise ValueError("文件路径未配置")
            
            # 创建文件读取线程
            self.file_reader = threading.Thread(
                target=self._file_reading_worker,
                daemon=True
            )
            self.file_reader.start()
            
            return super().start()
            
        except Exception as e:
            self.logger.error(f"启动文件数据源失败: {e}")
            return False
    
    def _file_reading_worker(self):
        """修复后的文件读取工作线程 - 批量处理版本"""
        try:
            self.logger.info(f"🚀 开始读取文件: {self.file_path}")
            
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                line_number = 0
                batch_data = []  # 批量数据缓存
                batch_size = min(self.chunk_size, 1000)  # 批量大小
                
                for line in f:
                    if not self.is_active:
                        self.logger.info(f"🛑 数据源已停止，停止读取")
                        break
                    
                    line_number += 1
                    
                    # 解析数据
                    if self.parser:
                        parsed_data = self.parser.parse_line(line)
                        if parsed_data:
                            # 添加数据源标识
                            parsed_data['source_id'] = self.source_id
                            parsed_data['data_type'] = self.config.get('data_types', [])
                            
                            # 添加到批量缓存
                            batch_data.append(parsed_data)
                            
                            # 当批量缓存满时，批量更新
                            if len(batch_data) >= batch_size:
                                self._process_batch_data(batch_data)
                                batch_data = []  # 清空缓存
                    
                    # 修复: 减少读取间隔，提高读取速度
                    if self.read_interval > 0 and line_number % 100 == 0:  # 每100行才sleep一次
                        time.sleep(self.read_interval)
                    
                    # 每1000行输出一次进度
                    if line_number % 1000 == 0:
                        self.logger.info(f"📊 已读取 {line_number} 行，成功解析 {self.data_count} 条数据")
                    
                    # 检查是否达到最大行数限制
                    if self.max_lines > 0 and line_number >= self.max_lines:
                        self.logger.info(f"🎯 已达到最大行数限制: {self.max_lines}")
                        break
                
                # 处理剩余的批量数据
                if batch_data:
                    self._process_batch_data(batch_data)
                
                self.logger.info(f"🎉 文件读取完成！总行数: {line_number}，成功解析: {self.data_count}")
                
        except Exception as e:
            self.logger.error(f"❌ 文件读取失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_batch_data(self, batch_data):
        """批量处理数据"""
        try:
            for parsed_data in batch_data:
                self.last_data = parsed_data
                self.last_timestamp = time.time()
                self.data_count += 1
                
                # 这里可以添加批量数据处理的逻辑
                # 比如批量写入数据库、批量发送等
                
        except Exception as e:
            self.logger.error(f"❌ 批量数据处理失败: {e}")


class MQTTDataSource(DataSource):
    """MQTT数据源"""
    
    def __init__(self, source_id: str, config: dict):
        super().__init__(source_id, config)
        self.broker_host = config.get('config', {}).get('broker_host', 'localhost')
        self.broker_port = config.get('config', {}).get('broker_port', 1883)
        self.topic = config.get('config', {}).get('topic', '')
        self.qos = config.get('config', {}).get('qos', 0)
        self.username = config.get('config', {}).get('username', '')
        self.password = config.get('config', {}).get('password', '')
        self.mqtt_client = None
        
    def start(self):
        """启动MQTT数据源"""
        try:
            # 这里应该创建MQTT客户端
            # 暂时使用模拟数据
            self.logger.info(f"✅ MQTT数据源 {self.source_id} 启动成功")
            return super().start()
            
        except Exception as e:
            self.logger.error(f"启动MQTT数据源失败: {e}")
            return False


class MultiSourceDataSyncManager:
    """多源异构数据同步管理器"""
    
    def __init__(self):
        self.data_sources = {}           # 数据源配置
        self.active_sources = {}         # 活跃的数据源
        self.data_buffers = {}           # 数据缓冲区
        self.sync_timestamps = {}        # 同步时间戳
        self.rule_config = RuleConfigurationManager()
        
        # 同步控制
        self.is_syncing = False
        self.sync_thread = None
        self.sync_interval = 0.01  # 10ms同步周期
        
        # 回调函数
        self.data_callback = None
        self.status_callback = None
        
        # 数据融合配置
        self.fusion_config = {
            'enable_timestamp_sync': True,
            'timestamp_tolerance': 0.1,  # 100ms时间容差
            'enable_health_scoring': True,
            'enable_anomaly_detection': True
        }
        
        self.logger = logging.getLogger(__name__)
        
    def add_data_source(self, source_id: str, config: dict) -> bool:
        """添加数据源"""
        try:
            # 验证配置
            if not self._validate_source_config(config):
                raise ValueError(f"数据源配置验证失败: {source_id}")
            
            # 创建数据源实例
            source = self._create_data_source(source_id, config)
            if not source:
                raise ValueError(f"创建数据源失败: {source_id}")
            
            self.data_sources[source_id] = config
            self.active_sources[source_id] = source
            self.data_buffers[source_id] = queue.Queue(maxsize=1000)
            
            self.logger.info(f"成功添加数据源: {source_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加数据源失败 {source_id}: {e}")
            return False
    
    def _validate_source_config(self, config: dict) -> bool:
        """验证数据源配置"""
        try:
            required_fields = ['data_types', 'transmission_type', 'parser_type', 'config']
            for field in required_fields:
                if field not in config:
                    self.logger.error(f"缺少必要字段: {field}")
                    return False
            
            # 验证数据类型
            data_types = config.get('data_types', [])
            if not data_types:
                self.logger.error("数据类型列表不能为空")
                return False
            
            for data_type in data_types:
                if not self.rule_config.data_type_config.get_data_type_rule(data_type):
                    self.logger.error(f"不支持的数据类型: {data_type}")
                    return False
            
            # 验证传输类型
            transmission_type = config.get('transmission_type', '')
            if not self.rule_config.transmission_config.get_transmission_type(transmission_type):
                self.logger.error(f"不支持的传输类型: {transmission_type}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证异常: {e}")
            return False
    
    def _create_data_source(self, source_id: str, config: dict) -> Optional[DataSource]:
        """创建数据源实例"""
        try:
            transmission_type = config.get('transmission_type', '').lower()
            
            if transmission_type == 'file':
                return FileDataSource(source_id, config)
            elif transmission_type == 'mqtt':
                return MQTTDataSource(source_id, config)
            elif transmission_type in ['tcp', 'udp', 'serial']:
                # 暂时返回基础数据源
                return DataSource(source_id, config)
            else:
                self.logger.error(f"不支持的传输类型: {transmission_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"创建数据源实例失败: {e}")
            return None
    
    def start_sync_loading(self, source_ids: List[str] = None) -> bool:
        """启动多源同步加载"""
        try:
            if self.is_syncing:
                self.logger.warning("同步加载已在运行中")
                return True
            
            # 如果没有指定数据源，使用所有活跃的数据源
            if source_ids is None:
                source_ids = list(self.active_sources.keys())
            
            # 验证所有数据源都已就绪
            for source_id in source_ids:
                if source_id not in self.active_sources:
                    raise ValueError(f"数据源未就绪: {source_id}")
            
            # 启动所有数据源
            for source_id in source_ids:
                if not self.active_sources[source_id].start():
                    raise ValueError(f"启动数据源失败: {source_id}")
            
            # 启动同步加载线程
            self.sync_thread = threading.Thread(
                target=self._sync_loading_worker,
                args=(source_ids,),
                daemon=True
            )
            self.sync_thread.start()
            
            self.is_syncing = True
            self.logger.info(f"启动多源同步加载: {source_ids}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动同步加载失败: {e}")
            return False
    
    def stop_sync_loading(self) -> bool:
        """停止多源同步加载"""
        try:
            if not self.is_syncing:
                return True
            
            # 停止所有数据源
            for source in self.active_sources.values():
                source.stop()
            
            # 等待同步线程结束
            if self.sync_thread and self.sync_thread.is_alive():
                self.is_syncing = False
                self.sync_thread.join(timeout=2.0)
            
            self.is_syncing = False
            self.logger.info("多源同步加载已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止同步加载失败: {e}")
            return False
    
    def _sync_loading_worker(self, source_ids: List[str]):
        """同步加载工作线程"""
        try:
            self.logger.info(f"同步加载工作线程启动: {source_ids}")
            
            while self.is_syncing:
                # 收集所有数据源的最新数据
                latest_data = {}
                for source_id in source_ids:
                    if source_id in self.active_sources:
                        source = self.active_sources[source_id]
                        if source.is_active:
                            data = source.get_latest_data()
                            if data:
                                latest_data[source_id] = data
                
                # 时间同步检查
                if self._check_timestamp_sync(latest_data):
                    # 执行数据融合
                    fused_data = self._fuse_multi_source_data(latest_data)
                    
                    # 发送到回调函数
                    if self.data_callback:
                        try:
                            self.data_callback(fused_data)
                        except Exception as e:
                            self.logger.error(f"数据回调执行失败: {e}")
                
                time.sleep(self.sync_interval)
                
        except Exception as e:
            self.logger.error(f"同步加载工作线程异常: {e}")
            traceback.print_exc()
    
    def _check_timestamp_sync(self, latest_data: Dict[str, Any]) -> bool:
        """检查时间戳同步"""
        if not self.fusion_config['enable_timestamp_sync']:
            return True
        
        if len(latest_data) < 2:
            return True
        
        timestamps = []
        for source_id, data in latest_data.items():
            if 'timestamp' in data:
                timestamps.append(data['timestamp'])
        
        if len(timestamps) < 2:
            return True
        
        # 检查时间戳差异
        max_diff = max(timestamps) - min(timestamps)
        tolerance = self.fusion_config['timestamp_tolerance']
        
        if max_diff > tolerance:
            self.logger.debug(f"时间戳不同步: 最大差异 {max_diff:.3f}s > {tolerance}s")
            return False
        
        return True
    
    def _fuse_multi_source_data(self, latest_data: Dict[str, Any]) -> Dict[str, Any]:
        """融合多源数据"""
        try:
            fused_data = {
                'timestamp': time.time(),
                'fusion_timestamp': datetime.now().isoformat(),
                'sources': {},
                'fused_metrics': {},
                'sync_status': 'success'
            }
            
            # 添加各源数据
            for source_id, data in latest_data.items():
                fused_data['sources'][source_id] = data
            
            # 计算融合指标
            if self.fusion_config['enable_health_scoring']:
                fused_data['fused_metrics'] = self._calculate_health_score(latest_data)
            
            # 异常检测
            if self.fusion_config['enable_anomaly_detection']:
                fused_data['anomaly_flags'] = self._detect_anomalies(latest_data)
            
            return fused_data
            
        except Exception as e:
            self.logger.error(f"数据融合失败: {e}")
            return {
                'timestamp': time.time(),
                'fusion_timestamp': datetime.now().isoformat(),
                'sources': latest_data,
                'fused_metrics': {},
                'sync_status': 'error',
                'error_message': str(e)
            }
    
    def _calculate_health_score(self, latest_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算健康评分（IMU+CNAP综合评分）"""
        try:
            health_score = {
                'overall_score': 0.0,
                'imu_score': 0.0,
                'cnap_score': 0.0,
                'details': {}
            }
            
            # IMU健康评分
            if any('imu' in source.get('data_type', []) for source in latest_data.values()):
                imu_score = self._calculate_imu_health_score(latest_data)
                health_score['imu_score'] = imu_score
                health_score['details']['imu'] = imu_score
            
            # CNAP健康评分
            if any('cnap' in source.get('data_type', []) for source in latest_data.values()):
                cnap_score = self._calculate_cnap_health_score(latest_data)
                health_score['cnap_score'] = cnap_score
                health_score['details']['cnap'] = cnap_score
            
            # 综合评分
            if health_score['imu_score'] > 0 and health_score['cnap_score'] > 0:
                health_score['overall_score'] = (imu_score + cnap_score) / 2
            else:
                health_score['overall_score'] = max(health_score['imu_score'], health_score['cnap_score'])
            
            return health_score
            
        except Exception as e:
            self.logger.error(f"计算健康评分失败: {e}")
            return {'overall_score': 0.0, 'error': str(e)}
    
    def _calculate_imu_health_score(self, latest_data: Dict[str, Any]) -> float:
        """计算IMU健康评分"""
        try:
            # 这里实现IMU健康评分算法
            # 暂时返回模拟值
            return 85.5
            
        except Exception as e:
            self.logger.error(f"计算IMU健康评分失败: {e}")
            return 0.0
    
    def _calculate_cnap_health_score(self, latest_data: Dict[str, Any]) -> float:
        """计算CNAP健康评分"""
        try:
            # 这里实现CNAP健康评分算法
            # 暂时返回模拟值
            return 92.3
            
        except Exception as e:
            self.logger.error(f"计算CNAP健康评分失败: {e}")
            return 0.0
    
    def _detect_anomalies(self, latest_data: Dict[str, Any]) -> Dict[str, Any]:
        """异常检测"""
        try:
            anomalies = {
                'has_anomaly': False,
                'anomaly_types': [],
                'anomaly_details': {}
            }
            
            # 这里实现异常检测逻辑
            # 暂时返回无异常
            
            return anomalies
            
        except Exception as e:
            self.logger.error(f"异常检测失败: {e}")
            return {'has_anomaly': False, 'error': str(e)}
    
    def set_data_callback(self, callback: Callable):
        """设置数据回调函数"""
        self.data_callback = callback
        self.logger.info("数据回调函数已设置")
    
    def set_status_callback(self, callback: Callable):
        """设置状态回调函数"""
        self.status_callback = callback
        self.logger.info("状态回调函数已设置")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            'is_syncing': self.is_syncing,
            'active_sources': len(self.active_sources),
            'total_sources': len(self.data_sources),
            'sync_interval': self.sync_interval,
            'fusion_config': self.fusion_config
        }
    
    def get_source_status(self) -> Dict[str, Any]:
        """获取所有数据源状态"""
        status = {}
        for source_id, source in self.active_sources.items():
            status[source_id] = source.get_status()
        return status
