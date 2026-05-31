#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块包
提供完整的系统配置管理功能
"""

from .configuration_manager import ConfigManager, ConfigurationDialog, RemoteConfigUpdater

__all__ = [
    'ConfigManager',
    'ConfigurationDialog', 
    'RemoteConfigUpdater'
]

__version__ = '1.0.0'
__author__ = 'Core System Team'
