#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源同步配置管理器模块
提供配置管理、验证和持久化功能

主要功能：
- 配置文件的加载和保存
- 配置验证和默认值管理
- 配置热更新支持
- 配置版本管理
- 配置备份和恢复
- 配置模板管理

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import json
import os
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy

logger = logging.getLogger(__name__)


class ConfigSection(Enum):
    """配置节"""
    GENERAL = "general"                    # 通用配置
    SYNC_ENGINE = "sync_engine"            # 同步引擎配置
    DATA_SOURCES = "data_sources"          # 数据源配置
    TIME_ALIGNMENT = "time_alignment"      # 时间同步配置
    DATA_FUSION = "data_fusion"            # 数据融合配置
    PERFORMANCE = "performance"             # 性能配置
    MONITORING = "monitoring"              # 监控配置
    SECURITY = "security"                  # 安全配置


@dataclass
class GeneralConfig:
    """通用配置"""
    system_name: str = "多源异构数据同步系统"
    version: str = "1.0.0"
    debug_mode: bool = False
    log_level: str = "INFO"
    max_log_files: int = 10
    log_rotation_size: int = 100  # MB


@dataclass
class SyncEngineConfig:
    """同步引擎配置"""
    sync_interval: float = 0.01  # 同步间隔（秒），100Hz
    max_concurrent_sources: int = 10
    enable_auto_recovery: bool = True
    recovery_timeout: float = 30.0  # 恢复超时（秒）
    enable_adaptive_sync: bool = True
    adaptive_threshold: float = 0.8


@dataclass
class DataSourceConfig:
    """数据源配置"""
    source_id: str = ""
    source_type: str = "unknown"  # mqtt, serial, file, database
    connection_string: str = ""
    enabled: bool = True
    priority: int = 1
    timeout: float = 5.0
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class TimeAlignmentConfig:
    """时间同步配置"""
    sync_strategy: str = "adaptive"  # time_priority, quality_priority, hybrid, adaptive
    max_time_offset: float = 0.1  # 最大时间偏移（秒）
    quality_threshold: float = 0.8
    enable_ntp_sync: bool = True
    ntp_servers: List[str] = field(default_factory=lambda: ["pool.ntp.org"])
    sync_interval: float = 1.0  # 时间同步间隔（秒）


@dataclass
class DataFusionConfig:
    """数据融合配置"""
    fusion_algorithm: str = "weighted_average"  # weighted_average, kalman_filter, neural_network, ensemble
    quality_weight: float = 0.7
    time_weight: float = 0.3
    enable_adaptive_fusion: bool = True
    fusion_threshold: float = 0.6
    max_fusion_delay: float = 0.5  # 最大融合延迟（秒）


@dataclass
class PerformanceConfig:
    """性能配置"""
    max_memory_usage: int = 1024  # MB
    enable_memory_optimization: bool = True
    gc_threshold: float = 0.8
    enable_async_processing: bool = True
    max_worker_threads: int = 8
    queue_size: int = 1000


@dataclass
class MonitoringConfig:
    """监控配置"""
    enable_performance_monitoring: bool = True
    monitoring_interval: float = 1.0  # 监控间隔（秒）
    enable_alerting: bool = True
    alert_thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)
    enable_metrics_storage: bool = True
    metrics_retention_days: int = 30


@dataclass
class SecurityConfig:
    """安全配置"""
    enable_authentication: bool = False
    enable_encryption: bool = False
    encryption_algorithm: str = "AES-256"
    enable_audit_log: bool = True
    max_login_attempts: int = 5
    session_timeout: float = 3600.0  # 会话超时（秒）


@dataclass
class MultiSourceSyncConfig:
    """多源同步系统配置"""
    general: GeneralConfig = field(default_factory=GeneralConfig)
    sync_engine: SyncEngineConfig = field(default_factory=SyncEngineConfig)
    data_sources: List[DataSourceConfig] = field(default_factory=list)
    time_alignment: TimeAlignmentConfig = field(default_factory=TimeAlignmentConfig)
    data_fusion: DataFusionConfig = field(default_factory=DataFusionConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiSourceSyncConfigManager:
    """多源同步配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file or "multi_source_sync_config.json"
        self.config = MultiSourceSyncConfig()
        self.config_version = "1.0.0"
        self.last_modified = 0.0
        self.config_watchers = []
        
        # 加载默认配置
        self._load_default_config()
        
        # 尝试从文件加载配置
        if os.path.exists(self.config_file):
            self.load_config()
        else:
            # 创建默认配置文件
            self.save_config()
        
        logger.info("多源同步配置管理器初始化完成")
    
    def _load_default_config(self):
        """加载默认配置"""
        try:
            # 设置默认数据源
            default_data_sources = [
                DataSourceConfig(
                    source_id="mqtt_source_1",
                    source_type="mqtt",
                    connection_string="mqtt://localhost:1883/topic1",
                    enabled=True,
                    priority=1
                ),
                DataSourceConfig(
                    source_id="serial_source_1",
                    source_type="serial",
                    connection_string="COM1:9600",
                    enabled=True,
                    priority=2
                ),
                DataSourceConfig(
                    source_id="file_source_1",
                    source_type="file",
                    connection_string="/data/source1.txt",
                    enabled=True,
                    priority=3
                )
            ]
            
            self.config.data_sources = default_data_sources
            
            # 设置默认告警阈值
            self.config.monitoring.alert_thresholds = {
                "cpu_usage": {"warning": 70.0, "critical": 90.0},
                "memory_usage": {"warning": 80.0, "critical": 95.0},
                "response_time": {"warning": 100.0, "critical": 500.0},
                "sync_latency": {"warning": 50.0, "critical": 200.0}
            }
            
            # 设置元数据
            self.config.metadata = {
                "created_at": time.time(),
                "created_by": "system",
                "description": "多源异构数据同步系统默认配置"
            }
            
        except Exception as e:
            logger.error(f"加载默认配置失败: {e}")
    
    def load_config(self, config_file: Optional[str] = None) -> bool:
        """
        从文件加载配置
        
        Args:
            config_file: 配置文件路径（可选）
            
        Returns:
            bool: 是否加载成功
        """
        try:
            file_path = config_file or self.config_file
            
            if not os.path.exists(file_path):
                logger.warning(f"配置文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 验证配置文件版本
            if "config_version" in config_data:
                file_version = config_data["config_version"]
                if file_version != self.config_version:
                    logger.warning(f"配置文件版本不匹配: 期望 {self.config_version}, 实际 {file_version}")
            
            # 更新配置
            self._update_config_from_dict(config_data)
            
            # 更新文件信息
            self.config_file = file_path
            self.last_modified = os.path.getmtime(file_path)
            
            logger.info(f"配置已从文件加载: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config_file: 配置文件路径（可选）
            
        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = config_file or self.config_file
            
            # 准备保存数据
            save_data = {
                "config_version": self.config_version,
                "last_modified": time.time(),
                "general": asdict(self.config.general),
                "sync_engine": asdict(self.config.sync_engine),
                "data_sources": [asdict(ds) for ds in self.config.data_sources],
                "time_alignment": asdict(self.config.time_alignment),
                "data_fusion": asdict(self.config.data_fusion),
                "performance": asdict(self.config.performance),
                "monitoring": asdict(self.config.monitoring),
                "security": asdict(self.config.security),
                "metadata": self.config.metadata
            }
            
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            # 更新文件信息
            self.config_file = file_path
            self.last_modified = time.time()
            
            logger.info(f"配置已保存到文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]):
        """从字典更新配置"""
        try:
            # 更新通用配置
            if "general" in config_data:
                for key, value in config_data["general"].items():
                    if hasattr(self.config.general, key):
                        setattr(self.config.general, key, value)
            
            # 更新同步引擎配置
            if "sync_engine" in config_data:
                for key, value in config_data["sync_engine"].items():
                    if hasattr(self.config.sync_engine, key):
                        setattr(self.config.sync_engine, key, value)
            
            # 更新数据源配置
            if "data_sources" in config_data:
                self.config.data_sources = []
                for ds_data in config_data["data_sources"]:
                    ds_config = DataSourceConfig()
                    for key, value in ds_data.items():
                        if hasattr(ds_config, key):
                            setattr(ds_config, key, value)
                    self.config.data_sources.append(ds_config)
            
            # 更新时间同步配置
            if "time_alignment" in config_data:
                for key, value in config_data["time_alignment"].items():
                    if hasattr(self.config.time_alignment, key):
                        setattr(self.config.time_alignment, key, value)
            
            # 更新数据融合配置
            if "data_fusion" in config_data:
                for key, value in config_data["data_fusion"].items():
                    if hasattr(self.config.data_fusion, key):
                        setattr(self.config.data_fusion, key, value)
            
            # 更新性能配置
            if "performance" in config_data:
                for key, value in config_data["performance"].items():
                    if hasattr(self.config.performance, key):
                        setattr(self.config.performance, key, value)
            
            # 更新监控配置
            if "monitoring" in config_data:
                for key, value in config_data["monitoring"].items():
                    if hasattr(self.config.monitoring, key):
                        setattr(self.config.monitoring, key, value)
            
            # 更新安全配置
            if "security" in config_data:
                for key, value in config_data["security"].items():
                    if hasattr(self.config.security, key):
                        setattr(self.config.security, key, value)
            
            # 更新元数据
            if "metadata" in config_data:
                self.config.metadata.update(config_data["metadata"])
                
        except Exception as e:
            logger.error(f"从字典更新配置失败: {e}")
    
    def get_config(self) -> MultiSourceSyncConfig:
        """获取当前配置"""
        return copy.deepcopy(self.config)
    
    def update_config(self, section: ConfigSection, key: str, value: Any) -> bool:
        """
        更新配置项
        
        Args:
            section: 配置节
            key: 配置键
            value: 配置值
            
        Returns:
            bool: 是否更新成功
        """
        try:
            if section == ConfigSection.GENERAL:
                if hasattr(self.config.general, key):
                    setattr(self.config.general, key, value)
                else:
                    logger.warning(f"通用配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.SYNC_ENGINE:
                if hasattr(self.config.sync_engine, key):
                    setattr(self.config.sync_engine, key, value)
                else:
                    logger.warning(f"同步引擎配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.DATA_SOURCES:
                # 数据源配置需要特殊处理
                logger.warning("数据源配置更新请使用专门的方法")
                return False
                
            elif section == ConfigSection.TIME_ALIGNMENT:
                if hasattr(self.config.time_alignment, key):
                    setattr(self.config.time_alignment, key, value)
                else:
                    logger.warning(f"时间同步配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.DATA_FUSION:
                if hasattr(self.config.data_fusion, key):
                    setattr(self.config.data_fusion, key, value)
                else:
                    logger.warning(f"数据融合配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.PERFORMANCE:
                if hasattr(self.config.performance, key):
                    setattr(self.config.performance, key, value)
                else:
                    logger.warning(f"性能配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.MONITORING:
                if hasattr(self.config.monitoring, key):
                    setattr(self.config.monitoring, key, value)
                else:
                    logger.warning(f"监控配置中不存在键: {key}")
                    return False
                    
            elif section == ConfigSection.SECURITY:
                if hasattr(self.config.security, key):
                    setattr(self.config.security, key, value)
                else:
                    logger.warning(f"安全配置中不存在键: {key}")
                    return False
                    
            else:
                logger.warning(f"未知的配置节: {section}")
                return False
            
            # 通知配置观察者
            self._notify_config_watchers(section, key, value)
            
            logger.info(f"配置已更新: {section.value}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def add_data_source(self, data_source_config: DataSourceConfig) -> bool:
        """
        添加数据源配置
        
        Args:
            data_source_config: 数据源配置
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 检查数据源ID是否已存在
            for existing_ds in self.config.data_sources:
                if existing_ds.source_id == data_source_config.source_id:
                    logger.warning(f"数据源ID已存在: {data_source_config.source_id}")
                    return False
            
            self.config.data_sources.append(data_source_config)
            
            # 通知配置观察者
            self._notify_config_watchers(ConfigSection.DATA_SOURCES, "add", data_source_config)
            
            logger.info(f"数据源配置已添加: {data_source_config.source_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加数据源配置失败: {e}")
            return False
    
    def remove_data_source(self, source_id: str) -> bool:
        """
        移除数据源配置
        
        Args:
            source_id: 数据源ID
            
        Returns:
            bool: 是否移除成功
        """
        try:
            for i, ds in enumerate(self.config.data_sources):
                if ds.source_id == source_id:
                    removed_ds = self.config.data_sources.pop(i)
                    
                    # 通知配置观察者
                    self._notify_config_watchers(ConfigSection.DATA_SOURCES, "remove", removed_ds)
                    
                    logger.info(f"数据源配置已移除: {source_id}")
                    return True
            
            logger.warning(f"数据源ID不存在: {source_id}")
            return False
            
        except Exception as e:
            logger.error(f"移除数据源配置失败: {e}")
            return False
    
    def get_data_source(self, source_id: str) -> Optional[DataSourceConfig]:
        """
        获取数据源配置
        
        Args:
            source_id: 数据源ID
            
        Returns:
            Optional[DataSourceConfig]: 数据源配置
        """
        try:
            for ds in self.config.data_sources:
                if ds.source_id == source_id:
                    return copy.deepcopy(ds)
            return None
            
        except Exception as e:
            logger.error(f"获取数据源配置失败: {e}")
            return None
    
    def update_data_source(self, source_id: str, **kwargs) -> bool:
        """
        更新数据源配置
        
        Args:
            source_id: 数据源ID
            **kwargs: 要更新的配置项
            
        Returns:
            bool: 是否更新成功
        """
        try:
            for ds in self.config.data_sources:
                if ds.source_id == source_id:
                    # 更新配置项
                    for key, value in kwargs.items():
                        if hasattr(ds, key):
                            setattr(ds, key, value)
                        else:
                            logger.warning(f"数据源配置中不存在键: {key}")
                    
                    # 通知配置观察者
                    self._notify_config_watchers(ConfigSection.DATA_SOURCES, "update", ds)
                    
                    logger.info(f"数据源配置已更新: {source_id}")
                    return True
            
            logger.warning(f"数据源ID不存在: {source_id}")
            return False
            
        except Exception as e:
            logger.error(f"更新数据源配置失败: {e}")
            return False
    
    def add_config_watcher(self, callback):
        """添加配置观察者"""
        if callback not in self.config_watchers:
            self.config_watchers.append(callback)
            logger.info("配置观察者已添加")
    
    def remove_config_watcher(self, callback):
        """移除配置观察者"""
        if callback in self.config_watchers:
            self.config_watchers.remove(callback)
            logger.info("配置观察者已移除")
    
    def _notify_config_watchers(self, section: ConfigSection, key: str, value: Any):
        """通知配置观察者"""
        try:
            for callback in self.config_watchers:
                try:
                    callback(section, key, value)
                except Exception as e:
                    logger.error(f"配置观察者回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知配置观察者失败: {e}")
    
    def validate_config(self) -> Dict[str, List[str]]:
        """
        验证配置
        
        Returns:
            Dict[str, List[str]]: 验证结果，键为配置节，值为错误列表
        """
        errors = {}
        
        try:
            # 验证通用配置
            general_errors = []
            if not self.config.general.system_name:
                general_errors.append("系统名称不能为空")
            if self.config.general.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                general_errors.append("日志级别无效")
            if general_errors:
                errors["general"] = general_errors
            
            # 验证同步引擎配置
            sync_engine_errors = []
            if self.config.sync_engine.sync_interval <= 0:
                sync_engine_errors.append("同步间隔必须大于0")
            if self.config.sync_engine.max_concurrent_sources <= 0:
                sync_engine_errors.append("最大并发数据源数必须大于0")
            if sync_engine_errors:
                errors["sync_engine"] = sync_engine_errors
            
            # 验证数据源配置
            data_sources_errors = []
            source_ids = set()
            for ds in self.config.data_sources:
                if not ds.source_id:
                    data_sources_errors.append("数据源ID不能为空")
                elif ds.source_id in source_ids:
                    data_sources_errors.append(f"数据源ID重复: {ds.source_id}")
                else:
                    source_ids.add(ds.source_id)
                
                if not ds.connection_string:
                    data_sources_errors.append(f"数据源 {ds.source_id} 连接字符串不能为空")
                
                if ds.priority < 1:
                    data_sources_errors.append(f"数据源 {ds.source_id} 优先级必须大于0")
            
            if data_sources_errors:
                errors["data_sources"] = data_sources_errors
            
            # 验证时间同步配置
            time_alignment_errors = []
            if self.config.time_alignment.max_time_offset <= 0:
                time_alignment_errors.append("最大时间偏移必须大于0")
            if self.config.time_alignment.quality_threshold < 0 or self.config.time_alignment.quality_threshold > 1:
                time_alignment_errors.append("质量阈值必须在0-1之间")
            if time_alignment_errors:
                errors["time_alignment"] = time_alignment_errors
            
            # 验证数据融合配置
            data_fusion_errors = []
            if self.config.data_fusion.quality_weight < 0 or self.config.data_fusion.quality_weight > 1:
                data_fusion_errors.append("质量权重必须在0-1之间")
            if self.config.data_fusion.time_weight < 0 or self.config.data_fusion.time_weight > 1:
                data_fusion_errors.append("时间权重必须在0-1之间")
            if data_fusion_errors:
                errors["data_fusion"] = data_fusion_errors
            
            # 验证性能配置
            performance_errors = []
            if self.config.performance.max_memory_usage <= 0:
                performance_errors.append("最大内存使用量必须大于0")
            if self.config.performance.max_worker_threads <= 0:
                performance_errors.append("最大工作线程数必须大于0")
            if performance_errors:
                errors["performance"] = performance_errors
            
            # 验证监控配置
            monitoring_errors = []
            if self.config.monitoring.monitoring_interval <= 0:
                monitoring_errors.append("监控间隔必须大于0")
            if self.config.monitoring.metrics_retention_days <= 0:
                monitoring_errors.append("指标保留天数必须大于0")
            if monitoring_errors:
                errors["monitoring"] = monitoring_errors
            
            # 验证安全配置
            security_errors = []
            if self.config.security.max_login_attempts <= 0:
                security_errors.append("最大登录尝试次数必须大于0")
            if self.config.security.session_timeout <= 0:
                security_errors.append("会话超时必须大于0")
            if security_errors:
                errors["security"] = security_errors
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            errors["system"] = [f"配置验证过程中发生错误: {str(e)}"]
        
        return errors
    
    def export_config_template(self) -> Dict[str, Any]:
        """导出配置模板"""
        try:
            template = {
                "config_version": self.config_version,
                "description": "多源异构数据同步系统配置模板",
                "general": asdict(GeneralConfig()),
                "sync_engine": asdict(SyncEngineConfig()),
                "data_sources": [
                    asdict(DataSourceConfig(
                        source_id="template_source",
                        source_type="template",
                        connection_string="template_connection_string"
                    ))
                ],
                "time_alignment": asdict(TimeAlignmentConfig()),
                "data_fusion": asdict(DataFusionConfig()),
                "performance": asdict(PerformanceConfig()),
                "monitoring": asdict(MonitoringConfig()),
                "security": asdict(SecurityConfig()),
                "metadata": {
                    "template": True,
                    "created_at": time.time(),
                    "description": "配置模板"
                }
            }
            
            return template
            
        except Exception as e:
            logger.error(f"导出配置模板失败: {e}")
            return {}
    
    def backup_config(self, backup_file: str) -> bool:
        """
        备份配置
        
        Args:
            backup_file: 备份文件路径
            
        Returns:
            bool: 是否备份成功
        """
        try:
            return self.save_config(backup_file)
        except Exception as e:
            logger.error(f"备份配置失败: {e}")
            return False
    
    def restore_config(self, backup_file: str) -> bool:
        """
        恢复配置
        
        Args:
            backup_file: 备份文件路径
            
        Returns:
            bool: 是否恢复成功
        """
        try:
            return self.load_config(backup_file)
        except Exception as e:
            logger.error(f"恢复配置失败: {e}")
            return False
