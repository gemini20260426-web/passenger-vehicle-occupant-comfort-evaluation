"""
多源同步配置模块
提供同步策略配置、融合算法配置等功能
"""

from .sync_strategy_config import SyncStrategyConfigPanel
from .fusion_algorithm_config import FusionAlgorithmConfigPanel
from .multi_source_sync_config_panel import MultiSourceSyncConfigTab
from .integrated_sync_panel import IntegratedSyncPanel

__all__ = [
    'SyncStrategyConfigPanel',
    'FusionAlgorithmConfigPanel',
    'MultiSourceSyncConfigTab',
    'IntegratedSyncPanel',
]
