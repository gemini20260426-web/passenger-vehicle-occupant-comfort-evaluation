#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
⚠️ DEPRECATED: 此组件已废弃

此文件保留仅为了向后兼容，将在未来版本中移除。
请使用 core.core.performance_monitor.PerformanceMonitor 作为统一的性能监控器。

系统性能管理器
负责全局性能优化，包括可视化性能优化
"""

import logging
import time
import gc
from typing import Dict, Any
from PySide6.QtCore import QObject, QTimer, Signal, QThread
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import threading

class VisualizationPerformanceManager(QObject):
    """可视化性能管理器"""
    
    # 性能调整信号
    visualization_performance_adjusted = Signal(dict)
    performance_alert = Signal(str, str)  # alert_type, message
    performance_adjusted = Signal(dict)   # 可视化参数调整信号
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("VisualizationPerformanceManager")
        
        # 性能监控参数
        self.monitoring_enabled = True
        self.monitoring_interval = 10000  # 10秒
        self.performance_monitor = QTimer()
        self.performance_monitor.timeout.connect(self._check_system_performance)
        
        # 可视化性能参数
        self.visualization_params = {
            'max_data_points': 500,
            'update_interval': 100,
            'data_buffer_size': 5,
            'enable_animation': True,
            'high_performance_mode': False
        }
        
        # 系统性能状态
        self.system_performance = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'visualization_lag': 0
        }
        
        # 性能阈值（降低阈值以提前触发清理）
        self.performance_thresholds = {
            'cpu_warning': 70,
            'cpu_critical': 85,
            'memory_warning': 75,
            'memory_critical': 85
        }
        
        # 开始性能监控
        self.start_monitoring()
        
    def start_monitoring(self):
        """开始性能监控"""
        if not self.performance_monitor.isActive():
            self.performance_monitor.start(self.monitoring_interval)
            self.logger.info("开始系统性能监控")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if self.performance_monitor.isActive():
            self.performance_monitor.stop()
            self.logger.info("停止系统性能监控")
    
    def _check_system_performance(self):
        """检查系统性能"""
        if not PSUTIL_AVAILABLE:
            self.stop_monitoring()
            return
        try:
            # 获取系统资源使用情况
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            self.system_performance['cpu_percent'] = cpu_percent
            self.system_performance['memory_percent'] = memory_percent
            
            # 根据系统性能自动调整可视化参数
            self._adjust_visualization_performance()
            
        except Exception as e:
            self.logger.error(f"检查系统性能时出错: {e}")
    
    def _adjust_visualization_performance(self):
        """根据系统性能自动调整可视化参数"""
        try:
            cpu_percent = self.system_performance.get('cpu_percent', 0)
            memory_percent = self.system_performance.get('memory_percent', 0)
            
            # 获取性能阈值
            cpu_warning = self.performance_thresholds.get('cpu_warning', 70)
            cpu_critical = self.performance_thresholds.get('cpu_critical', 85)
            memory_warning = self.performance_thresholds.get('memory_warning', 75)
            memory_critical = self.performance_thresholds.get('memory_critical', 90)
            
            # 根据CPU使用率调整参数
            if cpu_percent > cpu_critical:
                # 严重性能问题，大幅降低性能
                self.visualization_params['max_data_points'] = 200
                self.visualization_params['update_interval'] = 200
                self.visualization_params['data_buffer_size'] = 2
                self.visualization_params['enable_animation'] = False
                self.visualization_params['high_performance_mode'] = False
                self.performance_alert.emit('critical', f'CPU使用率过高({cpu_percent}%)，已启用最低性能模式')
                
            elif cpu_percent > cpu_warning:
                # 性能警告，适度降低性能
                self.visualization_params['max_data_points'] = 300
                self.visualization_params['update_interval'] = 150
                self.visualization_params['data_buffer_size'] = 3
                self.visualization_params['enable_animation'] = True
                self.visualization_params['high_performance_mode'] = False
                self.performance_alert.emit('warning', f'CPU使用率较高({cpu_percent}%)，已适度降低性能')
                
            elif cpu_percent < 30 and memory_percent < 50:
                # 系统资源充足，可以启用高性能模式
                self.visualization_params['max_data_points'] = 800
                self.visualization_params['update_interval'] = 50
                self.visualization_params['data_buffer_size'] = 8
                self.visualization_params['enable_animation'] = True
                self.visualization_params['high_performance_mode'] = True
                
            # 根据内存使用率调整参数
            if memory_percent > memory_critical:
                # 内存严重不足，强制垃圾回收
                self.force_garbage_collection()
                self.visualization_params['max_data_points'] = 150
                self.visualization_params['update_interval'] = 300
                self.performance_alert.emit('critical', f'内存使用率过高({memory_percent}%)，已强制清理内存')
                
            elif memory_percent > memory_warning:
                # 内存警告，减少数据点数量
                self.visualization_params['max_data_points'] = min(self.visualization_params['max_data_points'], 400)
                self.visualization_params['data_buffer_size'] = min(self.visualization_params['data_buffer_size'], 4)
                
            # 发送性能调整信号
            self.performance_adjusted.emit(self.visualization_params.copy())
            
        except Exception as e:
            self.logger.error(f"调整可视化性能时出错: {e}")
    
    def _cleanup_old_data(self):
        """清理旧数据以释放内存"""
        try:
            # 强制垃圾回收
            gc.collect()
            self.logger.debug("已执行内存清理")
        except Exception as e:
            self.logger.error(f"清理内存时出错: {e}")
    
    def get_performance_status(self):
        """获取当前性能状态"""
        return self.system_performance.copy()
    
    def get_visualization_params(self) -> Dict[str, Any]:
        """获取当前可视化参数"""
        return self.visualization_params.copy()
    
    def set_visualization_param(self, param_name: str, value: Any) -> bool:
        """设置可视化参数"""
        try:
            if param_name in self.visualization_params:
                self.visualization_params[param_name] = value
                self.logger.info(f"已设置可视化参数 {param_name} = {value}")
                return True
            else:
                self.logger.warning(f"未知的可视化参数: {param_name}")
                return False
        except Exception as e:
            self.logger.error(f"设置可视化参数时出错: {e}")
            return False
    
    def force_garbage_collection(self):
        """强制垃圾回收（带冷却）"""
        try:
            current_time = time.time()
            if not hasattr(self, '_last_gc_time'):
                self._last_gc_time = 0
            if current_time - self._last_gc_time < 30:
                return
            self._last_gc_time = current_time
            gc.collect()
            self.logger.debug("已执行强制垃圾回收")
        except Exception as e:
            self.logger.error(f"强制垃圾回收时出错: {e}")

# 为兼容性提供PerformanceManager别名
PerformanceManager = VisualizationPerformanceManager


class SystemPerformanceManager(QObject):
    """系统性能管理器"""
    
    performance_updated = Signal(dict)
    performance_alert = Signal(str, str)  # alert_type, message
    performance_adjusted = Signal(dict)   # 可视化参数调整信号
    
    def __init__(self):
        """初始化系统性能管理器"""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # 系统性能监控相关
        self.monitoring_interval = 5000  # 监控间隔(毫秒)
        self.system_performance = {
            'cpu_percent': 0.0,
            'memory_percent': 0.0
        }

        # 创建性能监控定时器
        self.performance_monitor = QTimer()
        self.performance_monitor.timeout.connect(self._monitor_system_performance)

        # 可视化参数
        self.visualization_params = {
            'update_interval': 100,
            'max_data_points': 500,
            'enable_animation': True,
            'high_performance_mode': False,
            'data_sample_rate': 1
        }

        # 性能阈值
        self.performance_thresholds = {
            'cpu_warning': 85,
            'cpu_critical': 95,
            'memory_warning': 85,
            'memory_critical': 95
        }
        
        # 开始性能监控
        self.start_monitoring()

    def start_monitoring(self):
        """开始性能监控"""
        if not self.performance_monitor.isActive():
            self.performance_monitor.start(self.monitoring_interval)
            self.logger.info("开始系统性能监控")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if self.performance_monitor.isActive():
            self.performance_monitor.stop()
            self.logger.info("停止系统性能监控")
            
    def _monitor_system_performance(self):
        """监控系统性能"""
        if not PSUTIL_AVAILABLE:
            self.stop_monitoring()
            return
        try:
            # 获取CPU和内存使用率
            cpu_percent = psutil.cpu_percent(interval=0)
            memory_percent = psutil.virtual_memory().percent
            
            # 更新性能数据
            self.system_performance['cpu_percent'] = cpu_percent
            self.system_performance['memory_percent'] = memory_percent
            
            # 发出性能更新信号
            self.performance_updated.emit(self.system_performance.copy())
            
            # 根据性能自动调整可视化参数
            self._adjust_visualization_performance()
            
        except Exception as e:
            self.logger.error(f"监控系统性能时出错: {e}")
    
    def _adjust_visualization_performance(self):
        """根据系统性能自动调整可视化参数"""
        try:
            cpu_percent = self.system_performance.get('cpu_percent', 0)
            memory_percent = self.system_performance.get('memory_percent', 0)
            
            # 获取性能阈值
            cpu_warning = self.performance_thresholds.get('cpu_warning', 70)
            cpu_critical = self.performance_thresholds.get('cpu_critical', 85)
            memory_warning = self.performance_thresholds.get('memory_warning', 75)
            memory_critical = self.performance_thresholds.get('memory_critical', 90)
            
            # 检查是否需要调整性能
            need_adjustment = False
            new_params = {}
            
            # CPU使用率过高时调整参数
            if cpu_percent > cpu_critical or memory_percent > memory_critical:
                # 严重性能问题，切换到节能模式
                new_params = {
                    'max_data_points': 100,
                    'update_interval': 500,
                    'enable_animation': False,
                    'high_performance_mode': False,
                    'data_sample_rate': 10
                }
                need_adjustment = True
                self.performance_alert.emit("critical", 
                    f"系统资源使用率过高: CPU {cpu_percent:.1f}%, 内存 {memory_percent:.1f}%")
                
            elif cpu_percent > cpu_warning or memory_percent > memory_warning:
                # 中等性能问题，适度调整
                new_params = {
                    'max_data_points': 200,
                    'update_interval': 200,
                    'enable_animation': True,
                    'high_performance_mode': False,
                    'data_sample_rate': 5
                }
                need_adjustment = True
                self.performance_alert.emit("warning", 
                    f"系统资源使用率偏高: CPU {cpu_percent:.1f}%, 内存 {memory_percent:.1f}%")
            
            # 如果需要调整，则更新参数并发出信号
            if need_adjustment:
                self.visualization_params.update(new_params)
                self.performance_adjusted.emit(self.visualization_params.copy())
                
        except Exception as e:
            self.logger.error(f"调整可视化性能时出错: {e}")
    
    def adjust_for_high_performance(self):
        """调整为高性能模式"""
        params = {
            'max_data_points': 1000,
            'update_interval': 50,
            'enable_animation': True,
            'high_performance_mode': True
        }
        
        # 更新可视化参数
        self.visualization_params.update(params)
        self.performance_adjusted.emit(self.visualization_params.copy())
        self.logger.info("已切换到高性能模式")
    
    def adjust_for_power_saving(self):
        """调整为节能模式"""
        params = {
            'max_data_points': 100,
            'update_interval': 500,
            'enable_animation': False,
            'high_performance_mode': False
        }
        
        # 更新可视化参数
        self.visualization_params.update(params)
        self.performance_adjusted.emit(self.visualization_params.copy())
        self.logger.info("已切换到节能模式")
