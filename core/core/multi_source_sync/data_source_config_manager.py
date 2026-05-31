#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源配置管理器
负责动态加载、管理和验证数据源配置
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class DataSourceConfigManager:
    """数据源配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "data_sources_config.json"
        self.config_data = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """加载数据源配置文件"""
        try:
            if not self.config_file.exists():
                logger.warning(f"配置文件不存在: {self.config_file}")
                self._create_default_config()
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            logger.info(f"✅ 成功加载数据源配置文件: {self.config_file}")
            logger.info(f"📊 配置了 {len(self.config_data.get('data_sources', {}))} 个数据源")
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败: {e}")
            self._create_default_config()
            return False
    
    def _create_default_config(self):
        """创建默认配置文件"""
        try:
            default_config = {
                "data_sources": {
                    "DS_001": {
                        "basic": {
                            "name": "IMU文件数据源",
                            "type": "file",
                            "data_types": ["加速度", "角速度"],
                            "sampling_rate": 10,
                            "description": "IMU传感器数据文件数据源"
                        },
                        "connection": {
                            "file_path": "test/cnapdata/1.txt",
                            "data_format": "txt"
                        },
                        "metadata": {
                            "source_category": "sensor",
                            "priority": "high",
                            "auto_start": False
                        }
                    }
                },
                "global_settings": {
                    "default_sampling_rate": 10,
                    "auto_connect_on_startup": False,
                    "enable_data_validation": True,
                    "max_buffer_size": 1000,
                    "data_quality_threshold": 0.8
                }
            }
            
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            self.config_data = default_config
            logger.info(f"✅ 已创建默认配置文件: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ 创建默认配置文件失败: {e}")
    
    def get_data_source_config(self, source_id: str) -> Optional[Dict[str, Any]]:
        """获取指定数据源的配置"""
        return self.config_data.get('data_sources', {}).get(source_id)
    
    def get_all_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源配置"""
        return self.config_data.get('data_sources', {})
    
    def get_auto_start_sources(self) -> List[str]:
        """获取自动启动的数据源ID列表"""
        auto_start_sources = []
        for source_id, config in self.config_data.get('data_sources', {}).items():
            if config.get('metadata', {}).get('auto_start', False):
                auto_start_sources.append(source_id)
        return auto_start_sources
    
    def get_global_settings(self) -> Dict[str, Any]:
        """获取全局设置"""
        return self.config_data.get('global_settings', {})
    
    def add_data_source(self, source_id: str, config: Dict[str, Any]) -> bool:
        """添加新的数据源配置"""
        try:
            if source_id in self.config_data.get('data_sources', {}):
                logger.warning(f"⚠️ 数据源 {source_id} 已存在，将被覆盖")
            
            if 'data_sources' not in self.config_data:
                self.config_data['data_sources'] = {}
            
            self.config_data['data_sources'][source_id] = config
            self._save_config()
            logger.info(f"✅ 成功添加数据源配置: {source_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加数据源配置失败: {e}")
            return False
    
    def update_data_source(self, source_id: str, config: Dict[str, Any]) -> bool:
        """更新数据源配置"""
        try:
            if source_id not in self.config_data.get('data_sources', {}):
                logger.error(f"❌ 数据源 {source_id} 不存在，无法更新")
                return False
            
            # 合并配置
            existing_config = self.config_data['data_sources'][source_id]
            updated_config = {**existing_config, **config}
            self.config_data['data_sources'][source_id] = updated_config
            
            self._save_config()
            logger.info(f"✅ 成功更新数据源配置: {source_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新数据源配置失败: {e}")
            return False
    
    def remove_data_source(self, source_id: str) -> bool:
        """删除数据源配置"""
        try:
            if source_id not in self.config_data.get('data_sources', {}):
                logger.warning(f"⚠️ 数据源 {source_id} 不存在，无需删除")
                return True
            
            del self.config_data['data_sources'][source_id]
            self._save_config()
            logger.info(f"✅ 成功删除数据源配置: {source_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除数据源配置失败: {e}")
            return False
    
    def validate_config(self) -> List[str]:
        """验证配置文件的有效性"""
        errors = []
        
        try:
            # 检查必需字段
            for source_id, config in self.config_data.get('data_sources', {}).items():
                if 'basic' not in config:
                    errors.append(f"数据源 {source_id}: 缺少basic配置")
                    continue
                
                basic = config['basic']
                if 'name' not in basic:
                    errors.append(f"数据源 {source_id}: 缺少名称")
                if 'type' not in basic:
                    errors.append(f"数据源 {source_id}: 缺少类型")
                
                # 检查连接配置
                if 'connection' in config:
                    conn = config['connection']
                    if config['basic']['type'] == 'file':
                        if 'file_path' not in conn:
                            errors.append(f"数据源 {source_id}: 文件数据源缺少文件路径")
                        if 'data_format' not in conn:
                            errors.append(f"数据源 {source_id}: 文件数据源缺少数据格式")
            
            # 检查文件路径是否存在
            for source_id, config in self.config_data.get('data_sources', {}).items():
                if config.get('basic', {}).get('type') == 'file':
                    file_path = config.get('connection', {}).get('file_path')
                    if file_path and not os.path.exists(file_path):
                        errors.append(f"数据源 {source_id}: 文件不存在: {file_path}")
            
        except Exception as e:
            errors.append(f"配置验证过程中发生错误: {e}")
        
        if not errors:
            logger.info("✅ 配置文件验证通过")
        else:
            logger.warning(f"⚠️ 配置文件验证发现 {len(errors)} 个问题")
            for error in errors:
                logger.warning(f"  - {error}")
        
        return errors
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"✅ 配置文件已保存: {self.config_file}")
        except Exception as e:
            logger.error(f"❌ 保存配置文件失败: {e}")
    
    def reload_config(self) -> bool:
        """重新加载配置文件"""
        logger.info("🔄 重新加载配置文件...")
        return self.load_config()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息"""
        data_sources = self.config_data.get('data_sources', {})
        
        summary = {
            "total_sources": len(data_sources),
            "source_types": {},
            "categories": {},
            "auto_start_count": 0,
            "file_sources": 0,
            "hardware_sources": 0
        }
        
        for source_id, config in data_sources.items():
            source_type = config.get('basic', {}).get('type', 'unknown')
            category = config.get('metadata', {}).get('source_category', 'unknown')
            auto_start = config.get('metadata', {}).get('auto_start', False)
            
            # 统计类型
            summary["source_types"][source_type] = summary["source_types"].get(source_type, 0) + 1
            
            # 统计分类
            summary["categories"][category] = summary["categories"].get(category, 0) + 1
            
            # 统计自动启动
            if auto_start:
                summary["auto_start_count"] += 1
            
            # 统计文件/硬件数据源
            if source_type == 'file':
                summary["file_sources"] += 1
            else:
                summary["hardware_sources"] += 1
        
        return summary
