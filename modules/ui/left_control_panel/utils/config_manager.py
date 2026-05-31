"""
配置管理器 - 管理数据融合流水线配置
提供配置的加载、保存、验证功能
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class SyncStrategy(Enum):
    """同步策略枚举"""
    TIME_PRIORITY = "time_priority"
    QUALITY_PRIORITY = "quality_priority"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"

class FusionAlgorithm(Enum):
    """融合算法枚举"""
    WEIGHTED_AVERAGE = "weighted_average"
    KALMAN_FILTER = "kalman_filter"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"

@dataclass
class DataSourceConfig:
    """数据源配置"""
    id: str
    name: str
    type: str  # 'imu', 'cnap', 'mqtt', 'file'
    enabled: bool = True
    
    # 连接配置
    connection: Dict[str, Any] = None
    
    # 解析配置
    parsing: Dict[str, Any] = None
    
    # 质量阈值
    quality_thresholds: Dict[str, float] = None
    
    # 信号滤波配置
    signal_filter: Dict[str, Any] = None
    
    # 坐标轴校正配置
    axis_correction: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.connection is None:
            self.connection = {}
        if self.parsing is None:
            self.parsing = {}
        if self.quality_thresholds is None:
            self.quality_thresholds = {
                'completeness': 0.95,
                'timeliness': 0.98,
                'accuracy': 0.90
            }
        if self.axis_correction is None:
            self.axis_correction = {'enabled': False, 'channels': {}}

@dataclass
class SyncConfig:
    """同步配置"""
    strategy: str = SyncStrategy.ADAPTIVE.value
    sync_frequency: float = 100.0  # Hz
    max_latency: float = 50.0  # ms
    buffer_size: int = 100

@dataclass
class FusionConfig:
    """融合配置"""
    algorithm: str = FusionAlgorithm.KALMAN_FILTER.value
    weights: Dict[str, float] = None
    kalman_params: Dict[str, float] = None
    
    def __post_init__(self):
        if self.weights is None:
            self.weights = {}
        if self.kalman_params is None:
            self.kalman_params = {
                'process_noise': 0.1,
                'measurement_noise': 0.5
            }

class PipelineConfigManager:
    """流水线配置管理器"""
    
    def __init__(self, config_dir: str = None):
        """初始化配置管理器"""
        if config_dir is None:
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config'
            )
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, 'fusion_pipeline_config.json')
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 配置数据
        self.data_sources: Dict[str, DataSourceConfig] = {}
        self.sync_config: SyncConfig = SyncConfig()
        self.fusion_config: FusionConfig = FusionConfig()
        
        # 尝试加载现有配置
        self.load_config()
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            config_data = {
                'version': '1.0',
                'timestamp': datetime.now().timestamp(),
                'data_sources': {
                    source_id: asdict(source_config)
                    for source_id, source_config in self.data_sources.items()
                },
                'sync_config': asdict(self.sync_config),
                'fusion_config': asdict(self.fusion_config)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def load_config(self) -> bool:
        """从文件加载配置"""
        try:
            if not os.path.exists(self.config_file):
                logger.info("配置文件不存在，使用默认配置")
                self._create_default_config()
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 加载数据源配置
            self.data_sources = {}
            for source_id, source_dict in config_data.get('data_sources', {}).items():
                self.data_sources[source_id] = DataSourceConfig(**source_dict)
            
            # 加载同步配置
            sync_dict = config_data.get('sync_config', {})
            self.sync_config = SyncConfig(**sync_dict)
            
            # 加载融合配置
            fusion_dict = config_data.get('fusion_config', {})
            self.fusion_config = FusionConfig(**fusion_dict)
            
            logger.info(f"配置已从 {self.config_file} 加载")
            return True
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self._create_default_config()
            return False
    
    def _create_default_config(self):
        """创建默认配置"""
        self.data_sources = {}
        self.sync_config = SyncConfig()
        self.fusion_config = FusionConfig()
        logger.info("已创建默认配置")
    
    def add_data_source(self, source_config: DataSourceConfig) -> bool:
        """添加数据源配置"""
        try:
            self.data_sources[source_config.id] = source_config
            logger.info(f"已添加数据源: {source_config.id}")
            return True
        except Exception as e:
            logger.error(f"添加数据源失败: {e}")
            return False
    
    def remove_data_source(self, source_id: str) -> bool:
        """移除数据源配置"""
        if source_id in self.data_sources:
            del self.data_sources[source_id]
            logger.info(f"已移除数据源: {source_id}")
            return True
        return False
    
    def get_data_source(self, source_id: str) -> Optional[DataSourceConfig]:
        """获取数据源配置"""
        return self.data_sources.get(source_id)
    
    def update_sync_config(self, **kwargs):
        """更新同步配置"""
        for key, value in kwargs.items():
            if hasattr(self.sync_config, key):
                setattr(self.sync_config, key, value)
        logger.info("同步配置已更新")
    
    def update_fusion_config(self, **kwargs):
        """更新融合配置"""
        for key, value in kwargs.items():
            if hasattr(self.fusion_config, key):
                setattr(self.fusion_config, key, value)
        logger.info("融合配置已更新")
    
    def export_config(self, export_path: str) -> bool:
        """导出配置"""
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'data_sources': {k: asdict(v) for k, v in self.data_sources.items()},
                    'sync_config': asdict(self.sync_config),
                    'fusion_config': asdict(self.fusion_config)
                }, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """导入配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.data_sources = {
                k: DataSourceConfig(**v) 
                for k, v in config_data.get('data_sources', {}).items()
            }
            self.sync_config = SyncConfig(**config_data.get('sync_config', {}))
            self.fusion_config = FusionConfig(**config_data.get('fusion_config', {}))
            
            return True
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False


# 全局配置管理器实例
_config_manager_instance: Optional[PipelineConfigManager] = None

def get_config_manager() -> PipelineConfigManager:
    """获取配置管理器单例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = PipelineConfigManager()
    return _config_manager_instance
