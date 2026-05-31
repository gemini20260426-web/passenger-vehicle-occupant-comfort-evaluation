#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据流管道管理模块
负责管理系统中所有模块之间的数据流，确保数据能够正确传递和处理
"""

import time
import logging
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class DataPipelineManager(QObject):
    """🚨 数据流管道管理器"""
    
    # 信号定义
    data_flow_status_changed = Signal(dict)  # 数据流状态变更
    data_pipeline_health_updated = Signal(dict)  # 管道健康状态更新
    module_data_received = Signal(str, dict)  # 模块数据接收
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        
        # 🚨 建立真实数据流管道
        self.data_pipeline = {
            'sensor_data': None,      # 传感器数据
            'parsing_status': None,   # 解析状态
            'analysis_result': None,  # 分析结果
            'advanced_analysis_result': None,  # 高级分析结果
            'system_status': None,    # 系统状态
            'data_flow_status': 'initialized'  # 数据流状态
        }
        
        # 数据流健康监控
        self.data_pipeline_health = {
            'last_update': time.time(),
            'update_count': 0,
            'error_count': 0,
            'health_score': 100,
            'data_flow_health': 100,
            'module_health': {}
        }

        self._last_restart_time = 0
        self._restart_count = 0
        self._restart_cooldown = 60
        self._max_restarts = 3
        
        # 启动数据流管道监控
        self.setup_data_pipeline_monitoring()
        
        self.logger.info("🚀 数据流管道管理器初始化完成")
    
    def setup_data_pipeline_monitoring(self):
        """🚨 启动数据流管道监控"""
        try:
            self.logger.info("🚀 启动数据流管道监控...")
            
            # 创建数据流监控定时器
            self.data_pipeline_timer = QTimer()
            self.data_pipeline_timer.timeout.connect(self._monitor_data_pipeline_health)
            # 无数据源时无需监控，按需启动

            # 创建数据流状态更新定时器
            self.data_flow_update_timer = QTimer()
            self.data_flow_update_timer.timeout.connect(self._update_data_flow_status)
            # 无数据源时无需更新，按需启动
            
            self.logger.info("✅ 数据流管道监控已启动")
            
        except Exception as e:
            self.logger.error(f"启动数据流管道监控失败: {e}")
    
    def _monitor_data_pipeline_health(self):
        """🚨 监控数据流管道健康状态"""
        try:
            current_time = time.time()
            health_score = 100
            
            # 检查各个模块的健康状态
            module_health = {}
            
            # 1. 检查传感器数据流
            if self.data_pipeline['sensor_data']:
                last_sensor_update = self.data_pipeline['sensor_data'].get('timestamp', 0)
                if current_time - last_sensor_update < 10:  # 10秒内有数据
                    module_health['sensor_data'] = 100
                else:
                    module_health['sensor_data'] = 50
            else:
                module_health['sensor_data'] = 0
            
            # 2. 检查解析状态流
            if self.data_pipeline['parsing_status']:
                last_parsing_update = self.data_pipeline['parsing_status'].get('timestamp', 0)
                if current_time - last_parsing_update < 10:
                    module_health['parsing_status'] = 100
                else:
                    module_health['parsing_status'] = 50
            else:
                module_health['parsing_status'] = 0
            
            # 3. 检查分析结果流
            if self.data_pipeline['analysis_result']:
                last_analysis_update = self.data_pipeline['analysis_result'].get('timestamp', 0)
                if current_time - last_analysis_update < 30:  # 30秒内有数据
                    module_health['analysis_result'] = 100
                else:
                    module_health['analysis_result'] = 50
            else:
                module_health['analysis_result'] = 0
            
            # 4. 检查高级分析结果流
            if self.data_pipeline['advanced_analysis_result']:
                last_advanced_update = self.data_pipeline['advanced_analysis_result'].get('timestamp', 0)
                if current_time - last_advanced_update < 60:  # 60秒内有数据
                    module_health['advanced_analysis_result'] = 100
                else:
                    module_health['advanced_analysis_result'] = 50
            else:
                module_health['advanced_analysis_result'] = 0
            
            # 计算总体健康度
            if module_health:
                health_score = sum(module_health.values()) / len(module_health)
            
            # 更新健康状态
            self.data_pipeline_health['module_health'] = module_health
            self.data_pipeline_health['data_flow_health'] = health_score
            self.data_pipeline_health['last_update'] = current_time
            
            # 检查是否需要重启数据流
            if health_score < 30:
                self.logger.debug(f"数据流健康度过低: {health_score:.1f}%，尝试重启数据流")
                self._restart_data_pipeline()
            
            # 发送健康状态更新信号
            self.data_pipeline_health_updated.emit(self.data_pipeline_health)
            
            self.logger.debug(f"数据流健康监控完成，健康度: {health_score:.1f}%")
            
        except Exception as e:
            self.logger.error(f"监控数据流管道健康状态失败: {e}")
    
    def _update_data_flow_status(self):
        """🚨 更新数据流状态"""
        try:
            current_time = time.time()
            
            # 更新数据流状态
            if self.data_pipeline_health['data_flow_health'] > 80:
                self.data_pipeline['data_flow_status'] = 'healthy'
            elif self.data_pipeline_health['data_flow_health'] > 50:
                self.data_pipeline['data_flow_status'] = 'warning'
            else:
                self.data_pipeline['data_flow_status'] = 'critical'
            
            # 更新系统状态
            self.data_pipeline['system_status'] = {
                'timestamp': current_time,
                'data_flow_health': self.data_pipeline_health['data_flow_health'],
                'module_health': self.data_pipeline_health['module_health'],
                'overall_status': self.data_pipeline['data_flow_status']
            }
            
            # 发送数据流状态变更信号
            self.data_flow_status_changed.emit(self.data_pipeline['system_status'])
            
        except Exception as e:
            self.logger.error(f"更新数据流状态失败: {e}")
    
    def _restart_data_pipeline(self):
        """重启数据流管道（带冷却机制，防止无限重启循环）"""
        try:
            now = time.time()

            if self._restart_count >= self._max_restarts:
                self.logger.warning("数据流管道重启已达上限，不再自动重启，请手动检查数据源")
                return

            if now - self._last_restart_time < self._restart_cooldown:
                return

            self._last_restart_time = now
            self._restart_count += 1

            self.logger.info(f"正在重启数据流管道... (第{self._restart_count}次)")

            if hasattr(self, 'data_pipeline_timer'):
                self.data_pipeline_timer.stop()
            if hasattr(self, 'data_flow_update_timer'):
                self.data_flow_update_timer.stop()

            self.data_pipeline['data_flow_status'] = 'restarting'
            self.data_pipeline_health['error_count'] += 1

            self.setup_data_pipeline_monitoring()
            
            self.logger.info("✅ 数据流管道重启完成")
            
        except Exception as e:
            self.logger.error(f"重启数据流管道失败: {e}")
    
    def update_data_pipeline(self, data_type: str, data: dict):
        """🚨 更新数据流管道中的数据"""
        try:
            if data_type in self.data_pipeline:
                # 添加时间戳
                data_with_timestamp = {
                    **data,
                    'timestamp': time.time()
                }
                
                self.data_pipeline[data_type] = data_with_timestamp
                self.data_pipeline_health['update_count'] += 1
                
                # 根据数据类型转发到相应模块
                self._forward_data_to_modules(data_type, data_with_timestamp)
                
                # 发送模块数据接收信号
                self.module_data_received.emit(data_type, data_with_timestamp)
                
                self.logger.debug(f"✅ 数据流管道已更新: {data_type}")
                return True
            else:
                self.logger.warning(f"⚠️ 未知的数据类型: {data_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"更新数据流管道失败: {e}")
            self.data_pipeline_health['error_count'] += 1
            return False
    
    def _forward_data_to_modules(self, data_type: str, data: dict):
        """🚨 将数据转发到相应模块"""
        try:
            if data_type == 'sensor_data':
                # 转发传感器数据到分析模块
                if hasattr(self.parent, 'left_panel') and hasattr(self.parent.left_panel, 'analysis_control'):
                    self.parent.left_panel.analysis_control.receive_sensor_data(data)
                
                # 转发到实时行为监控
                if hasattr(self.parent, 'right_tab') and hasattr(self.parent.right_tab, 'real_time_behavior_monitoring_tab'):
                    self.parent.right_tab.real_time_behavior_monitoring_tab.update_sensor_data(data)
            
            elif data_type == 'parsing_status':
                # 转发解析状态到监控面板
                if hasattr(self.parent, 'right_tab') and hasattr(self.parent.right_tab, 'monitoring_tab'):
                    self.parent.right_tab.monitoring_tab.receive_parsing_status(data)
            
            elif data_type == 'analysis_result':
                # 转发分析结果到高级分析模块
                if hasattr(self.parent, 'left_panel') and hasattr(self.parent.left_panel, 'analysis_control'):
                    self.parent.left_panel.analysis_control.receive_advanced_analysis_data(data)
            
            elif data_type == 'advanced_analysis_result':
                # 转发高级分析结果到显示模块
                if hasattr(self.parent, 'right_tab') and hasattr(self.parent.right_tab, 'monitoring_tab'):
                    self.parent.right_tab.monitoring_tab.receive_advanced_analysis_result(data)
            
            self.logger.debug(f"✅ 数据已转发到相应模块: {data_type}")
            
        except Exception as e:
            self.logger.error(f"转发数据到模块失败: {e}")
    
    def get_data_pipeline_status(self):
        """🚨 获取数据流管道状态"""
        try:
            return {
                'pipeline_status': self.data_pipeline,
                'health_status': self.data_pipeline_health,
                'timestamp': time.time()
            }
        except Exception as e:
            self.logger.error(f"获取数据流管道状态失败: {e}")
            return {}
    
    def clear_data_pipeline(self):
        """🚨 清空数据流管道"""
        try:
            for key in self.data_pipeline:
                if key != 'data_flow_status':
                    self.data_pipeline[key] = None
            
            self.data_pipeline['data_flow_status'] = 'cleared'
            self.data_pipeline_health['update_count'] = 0
            self.data_pipeline_health['error_count'] = 0
            
            self.logger.info("✅ 数据流管道已清空")
            
        except Exception as e:
            self.logger.error(f"清空数据流管道失败: {e}")
    
    def shutdown(self):
        """🚨 关闭数据流管道管理器"""
        try:
            # 停止定时器
            if hasattr(self, 'data_pipeline_timer'):
                self.data_pipeline_timer.stop()
            if hasattr(self, 'data_flow_update_timer'):
                self.data_flow_update_timer.stop()
            
            # 清空数据
            self.clear_data_pipeline()
            
            self.logger.info("✅ 数据流管道管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭数据流管道管理器失败: {e}")


# 便捷函数
def create_data_pipeline_manager(parent=None):
    """创建数据流管道管理器实例"""
    return DataPipelineManager(parent)


def get_data_pipeline_status(manager):
    """获取数据流管道状态"""
    if manager:
        return manager.get_data_pipeline_status()
    return {}


def update_data_pipeline(manager, data_type: str, data: dict):
    """更新数据流管道"""
    if manager:
        return manager.update_data_pipeline(data_type, data)
    return False
