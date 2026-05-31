#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源异构数据同步系统分析模块 v2.0
提供数据分析和行为分析功能

主要组件：
- 基础分析器 (v2.0 五层架构)
- 高级分析器
- 行为分析器
- 分析流水线
- 分析器适配器

版本: 2.0
创建时间: 2025年8月16日
更新时间: 2026年5月6日 (五层架构重构)
"""

try:
    from .base_analyzer import BasicDrivingAnalyzer, BEHAVIOR_TYPES
    from .BehaviorAnalyzer import BehaviorEventDispatcher
    from .advanced_analyzer import AdvancedBehaviorAnalyzer
    from .analysis_pipeline import AnalysisPipeline
    from .analyzer_adapter import AnalyzerAdapter
    from .data_bridge import DataBridge
    from .pipeline import AnalysisPipeline as V2AnalysisPipeline

    __all__ = [
        'BasicDrivingAnalyzer',
        'BEHAVIOR_TYPES',
        'BehaviorEventDispatcher',
        'AdvancedBehaviorAnalyzer',
        'AnalysisPipeline',
        'V2AnalysisPipeline',
        'AnalyzerAdapter',
        'DataBridge',
    ]

except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"分析模块导入失败: {e}")

    __all__ = []

__version__ = "2.0.0"
__author__ = "UI重构项目组"
__description__ = "多源异构数据同步系统分析模块（五层智能驾驶分析架构）"
