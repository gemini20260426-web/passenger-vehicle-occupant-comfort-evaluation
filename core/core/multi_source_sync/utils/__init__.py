#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源同步工具模块
提供异步处理、内存优化、数据验证等核心工具

版本: 1.0
创建时间: 2025年8月16日
"""

from .async_processor import AsyncDataProcessor
from .memory_optimizer import MemoryOptimizedBuffer
from .data_validator import DataValidator

__version__ = "1.0.0"
__all__ = [
    'AsyncDataProcessor',
    'MemoryOptimizedBuffer', 
    'DataValidator'
]

# 模块初始化日志
import logging
logger = logging.getLogger(__name__)
logger.info(f"多源同步工具模块 v{__version__} 已加载")
