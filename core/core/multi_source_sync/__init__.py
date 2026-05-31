#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源异构数据同步核心模块
世界级多源异构数据同步系统的核心引擎

主要功能：
- 智能时间同步引擎（毫秒级精度）
- 自适应数据融合算法
- 智能异常检测系统
- 高性能异步处理架构
- 实时性能监控
- 内存优化管理

版本: 1.0
创建时间: 2025年8月16日
"""

from .sync_engine import MultiSourceSyncEngine
from .data_fusion import AdaptiveDataFusion
from .quality_assessor import DataQualityAssessor
from .time_aligner import IntelligentTimeAligner
from .performance_monitor import RealTimePerformanceMonitor
from .config_manager import MultiSourceSyncConfigManager
from .anomaly_detector import IntelligentAnomalyDetector
from .utils.async_processor import AsyncDataProcessor
from .utils.memory_optimizer import MemoryOptimizedBuffer
from .utils.data_validator import DataValidator

__version__ = "1.0.0"
__author__ = "UI重构项目组"
__description__ = "世界级多源异构数据同步系统核心模块"

__all__ = [
    'MultiSourceSyncEngine',
    'AdaptiveDataFusion', 
    'DataQualityAssessor',
    'IntelligentTimeAligner',
    'RealTimePerformanceMonitor',
    'MultiSourceSyncConfigManager',
    'IntelligentAnomalyDetector',
    'AsyncDataProcessor',
    'MemoryOptimizedBuffer',
    'DataValidator'
]

# 模块初始化日志
import logging
logger = logging.getLogger(__name__)
logger.info(f"多源同步核心模块 v{__version__} 已加载")
