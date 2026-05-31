"""
左侧控制面板模块
多源异构数据流式处理的UI组件集合

架构:
- utils/          工具模块（样式、配置、流水线管理）
- data_source_config/  数据源配置模块
"""

# 导入工具模块
from .utils import (
    style_manager,
    PRO_COLORS,
    SPACING,
    SIZES,
    StyleManager,
    ProfessionalColors,
    Spacing,
    Sizes,
    get_config_manager,
    PipelineConfigManager,
    DataSourceConfig,
    SyncConfig,
    FusionConfig,
    SyncStrategy,
    FusionAlgorithm,
    get_pipeline_manager,
    DataPipelineManager,
    PipelineStatus,
    PipelineMetrics,
    DataSourceSample,
)

# 导入数据源配置模块
from .data_source_config import (
    DataSourceConfigDialog,
    DataSourceListPanel,
    StatusIndicator,
)

__all__ = [
    # 工具模块
    'style_manager',
    'PRO_COLORS',
    'SPACING',
    'SIZES',
    'StyleManager',
    'ProfessionalColors',
    'Spacing',
    'Sizes',
    'get_config_manager',
    'PipelineConfigManager',
    'DataSourceConfig',
    'SyncConfig',
    'FusionConfig',
    'SyncStrategy',
    'FusionAlgorithm',
    'get_pipeline_manager',
    'DataPipelineManager',
    'PipelineStatus',
    'PipelineMetrics',
    'DataSourceSample',
    
    # 数据源配置
    'DataSourceConfigDialog',
    'DataSourceListPanel',
    'StatusIndicator',
]
