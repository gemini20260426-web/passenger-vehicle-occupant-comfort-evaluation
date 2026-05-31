#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试配置文件
用于配置数据解析和串口通信的调试选项
"""

import logging
import os
from typing import Dict, Any

class DebugConfig:
    """调试配置类"""
    
    def __init__(self):
        """初始化调试配置"""
        self.config = {
            # 数据解析调试选项
            "data_parsing": {
                "enable_debug_logging": True,
                "log_raw_data": True,
                "log_parsed_data": True,
                "log_validation_errors": True,
                "log_pattern_matching": True,
                "max_raw_data_length": 200,
                "enable_statistics": True
            },
            
            # 串口通信调试选项
            "serial_communication": {
                "enable_debug_logging": True,
                "log_received_data": True,
                "log_connection_status": True,
                "log_errors": True,
                "enable_auto_reconnect_debug": True
            },
            
            # 性能监控选项
            "performance_monitoring": {
                "enable_timing": True,
                "log_processing_time": True,
                "enable_memory_monitoring": True,
                "log_buffer_status": True
            },
            
            # 错误处理选项
            "error_handling": {
                "log_full_stack_traces": True,
                "enable_error_recovery": True,
                "max_error_log_length": 1000,
                "log_error_context": True
            }
        }
        
        # 从环境变量加载配置
        self._load_from_environment()
    
    def _load_from_environment(self):
        """从环境变量加载配置"""
        env_mapping = {
            "DEBUG_DATA_PARSING": ("data_parsing", "enable_debug_logging"),
            "DEBUG_SERIAL": ("serial_communication", "enable_debug_logging"),
            "DEBUG_PERFORMANCE": ("performance_monitoring", "enable_timing"),
            "DEBUG_ERRORS": ("error_handling", "log_full_stack_traces")
        }
        
        for env_var, (section, key) in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    self.config[section][key] = env_value.lower() in ('true', '1', 'yes', 'on')
                except (ValueError, KeyError):
                    pass
    
    def get_config(self, section: str = None) -> Dict[str, Any]:
        """
        获取配置
        
        Args:
            section: 配置节名称，如果为None则返回全部配置
            
        Returns:
            配置字典
        """
        if section is None:
            return self.config.copy()
        return self.config.get(section, {}).copy()
    
    def is_enabled(self, section: str, key: str) -> bool:
        """
        检查特定配置项是否启用
        
        Args:
            section: 配置节名称
            key: 配置项名称
            
        Returns:
            是否启用
        """
        return self.config.get(section, {}).get(key, False)
    
    def set_config(self, section: str, key: str, value: Any):
        """
        设置配置项
        
        Args:
            section: 配置节名称
            key: 配置项名称
            value: 配置值
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def setup_logging(self, logger_name: str = None) -> logging.Logger:
        """
        根据配置设置日志记录器
        
        Args:
            logger_name: 日志记录器名称
            
        Returns:
            配置好的日志记录器
        """
        if logger_name is None:
            logger_name = __name__
            
        logger = logging.getLogger(logger_name)
        
        # 根据配置设置日志级别
        if self.is_enabled("data_parsing", "enable_debug_logging"):
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        
        # 如果没有处理器，添加一个
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        获取调试信息摘要
        
        Returns:
            调试信息字典
        """
        debug_info = {}
        
        for section, options in self.config.items():
            enabled_count = sum(1 for enabled in options.values() if isinstance(enabled, bool) and enabled)
            total_count = sum(1 for option in options.values() if isinstance(option, bool))
            
            debug_info[section] = {
                "enabled_options": enabled_count,
                "total_options": total_count,
                "enabled_percentage": round(enabled_count / total_count * 100, 1) if total_count > 0 else 0
            }
        
        return debug_info

# 全局调试配置实例
debug_config = DebugConfig()

def get_debug_config() -> DebugConfig:
    """获取全局调试配置实例"""
    return debug_config

def is_debug_enabled(section: str, key: str) -> bool:
    """检查调试选项是否启用"""
    return debug_config.is_enabled(section, key)

def setup_debug_logging(logger_name: str = None) -> logging.Logger:
    """设置调试日志记录器"""
    return debug_config.setup_logging(logger_name)
