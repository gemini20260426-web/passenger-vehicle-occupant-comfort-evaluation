#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
系统性能优化器
专门解决系统卡阻和性能问题
"""

import logging
import time
import gc
import threading
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal, QThread, QMutex, QMutexLocker
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import weakref

class SystemPerformanceOptimizer(QObject):
    """系统性能优化器"""

    optimization_applied = Signal(dict)
    performance_warning = Signal(str, str)
    resource_cleanup_completed = Signal()

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("SystemPerformanceOptimizer")

        self.monitoring_enabled = True
        self.monitoring_interval = 2000
        self.performance_monitor = QTimer()
        self.performance_monitor.timeout.connect(self._check_and_optimize)

        self.system_status = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'active_timers': 0,
            'active_threads': 0,
            'memory_usage_mb': 0
        }

        self.thresholds = {
            'cpu_warning': 60,
            'cpu_critical': 80,
            'memory_warning': 70,
            'memory_critical': 85,
            'timer_warning': 10,
            'thread_warning': 15
        }

        self.optimization_strategies = {
            'aggressive': {
                'max_data_points': 200,
                'update_interval': 200,
                'buffer_size': 3,
                'enable_animation': False,
                'force_gc': True
            },
            'moderate': {
                'max_data_points': 300,
                'update_interval': 150,
                'buffer_size': 4,
                'enable_animation': True,
                'force_gc': False
            },
            'conservative': {
                'max_data_points': 500,
                'update_interval': 100,
                'buffer_size': 5,
                'enable_animation': True,
                'force_gc': False
            }
        }

        self.current_optimization_level = 'conservative'

        self.cleanup_mutex = QMutex()

        self._gc_thread = None
        self._gc_running = False
        self._last_memory_mb = 0
        self._memory_growth_rate = 0
        self._start_background_gc()
        
    def start_monitoring(self):
        """开始性能监控"""
        if not self.performance_monitor.isActive():
            self.performance_monitor.start(self.monitoring_interval)
            self.logger.info("开始系统性能监控和优化")

    def stop_monitoring(self):
        """停止性能监控"""
        if self.performance_monitor.isActive():
            self.performance_monitor.stop()
            self.logger.info("停止系统性能监控")

    def shutdown(self):
        """关闭性能优化器"""
        try:
            self.stop_monitoring()
            self._gc_running = False
            if self._gc_thread and self._gc_thread.is_alive():
                self._gc_thread.join(timeout=2.0)

            with QMutexLocker(self.cleanup_mutex):
                self._cleanup_resources()

            self.resource_cleanup_completed.emit()

            self.logger.info("性能优化器已关闭")
        except Exception as e:
            self.logger.error(f"关闭性能优化器时出错: {e}")

    def _start_background_gc(self):
        """启动后台GC线程，定期清理内存但不阻塞UI"""
        self._gc_running = True
        self._gc_thread = threading.Thread(target=self._background_gc_loop, daemon=True)
        self._gc_thread.start()
        self.logger.info("后台GC线程已启动")

    def _background_gc_loop(self):
        """后台GC循环 - 轻量gen0收集频繁执行，全量收集按需执行"""
        gen0_interval = 5.0
        full_gc_interval = 60.0
        last_gen0 = time.time()
        last_full = time.time()

        while self._gc_running:
            try:
                now = time.time()

                if now - last_gen0 >= gen0_interval:
                    gc.collect(0)
                    last_gen0 = now

                if now - last_full >= full_gc_interval:
                    collected = gc.collect()
                    if collected > 0:
                        self.logger.debug(f"后台全量GC: 回收 {collected} 个对象")

                    if PSUTIL_AVAILABLE:
                        mem = psutil.virtual_memory()
                        current_mb = mem.used / (1024 * 1024)
                        if self._last_memory_mb > 0:
                            self._memory_growth_rate = (current_mb - self._last_memory_mb) / full_gc_interval
                            if self._memory_growth_rate > 5:
                                gc.collect()
                                gc.collect()
                                self.logger.info(f"内存快速增长 ({self._memory_growth_rate:.1f} MB/s)，已执行紧急GC")
                        self._last_memory_mb = current_mb

                    last_full = now

                time.sleep(1.0)
            except Exception:
                time.sleep(5.0)
    
    def _check_and_optimize(self):
        """检查系统性能并应用优化"""
        try:
            with QMutexLocker(self.cleanup_mutex):
                # 获取系统状态
                self._update_system_status()
                
                # 检查是否需要优化
                if self._needs_optimization():
                    self._apply_optimization()
                
                # 定期清理资源
                if time.time() % 30 < 2:  # 每30秒清理一次
                    self._cleanup_resources()
                    
        except Exception as e:
            self.logger.error(f"性能检查和优化时出错: {e}")
    
    def _update_system_status(self):
        """更新系统状态"""
        try:
            # CPU和内存使用率 (interval=None 非阻塞, 返回上次缓存值)
            self.system_status['cpu_percent'] = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            self.system_status['memory_percent'] = memory.percent
            self.system_status['memory_usage_mb'] = memory.used / (1024 * 1024)
            
            # 统计活跃的定时器和线程
            self.system_status['active_timers'] = self._count_active_timers()
            self.system_status['active_threads'] = threading.active_count()
            
        except Exception as e:
            self.logger.error(f"更新系统状态时出错: {e}")
    
    def _count_active_timers(self):
        """统计活跃的定时器数量"""
        try:
            # 这里我们只能统计已知的定时器
            # 实际项目中应该维护一个定时器注册表
            return 0  # 暂时返回0，后续可以改进
        except Exception as e:
            self.logger.error(f"统计定时器时出错: {e}")
            return 0
    
    def _needs_optimization(self):
        """检查是否需要优化"""
        cpu_percent = self.system_status['cpu_percent']
        memory_percent = self.system_status['memory_percent']
        active_timers = self.system_status['active_timers']
        active_threads = self.system_status['active_threads']
        
        # 检查各种阈值
        if (cpu_percent > self.thresholds['cpu_critical'] or 
            memory_percent > self.thresholds['memory_critical']):
            return True
        
        if (cpu_percent > self.thresholds['cpu_warning'] or 
            memory_percent > self.thresholds['memory_warning']):
            return True
        
        if (active_timers > self.thresholds['timer_warning'] or 
            active_threads > self.thresholds['thread_warning']):
            return True
        
        return False
    
    def _apply_optimization(self):
        """应用性能优化"""
        try:
            cpu_percent = self.system_status['cpu_percent']
            memory_percent = self.system_status['memory_percent']
            
            # 根据系统负载选择优化策略
            if cpu_percent > self.thresholds['cpu_critical'] or memory_percent > self.thresholds['memory_critical']:
                new_level = 'aggressive'
            elif cpu_percent > self.thresholds['cpu_warning'] or memory_percent > self.thresholds['memory_warning']:
                new_level = 'moderate'
            else:
                new_level = 'conservative'
            
            if new_level != self.current_optimization_level:
                self.current_optimization_level = new_level
                self._apply_optimization_strategy(new_level)
                self.logger.info(f"应用{new_level}优化策略")
                
        except Exception as e:
            self.logger.error(f"应用优化策略时出错: {e}")
    
    def _apply_optimization_strategy(self, strategy_name: str):
        """应用具体的优化策略"""
        try:
            strategy = self.optimization_strategies.get(strategy_name, {})
            
            # 发送优化信号
            self.optimization_applied.emit(strategy)
            
            # 强制垃圾回收（如果策略要求）
            if strategy.get('force_gc', False):
                self._force_garbage_collection()
                
        except Exception as e:
            self.logger.error(f"应用优化策略{strategy_name}时出错: {e}")
    
    def _cleanup_resources(self):
        """清理系统资源"""
        try:
            with QMutexLocker(self.cleanup_mutex):
                # 强制垃圾回收
                self._force_garbage_collection()
                
                # 清理临时文件
                self._cleanup_temp_files()
                
                # 清理缓存
                self._cleanup_caches()
                
                self.logger.info("系统资源清理完成")
                self.resource_cleanup_completed.emit()
                
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
    
    def _force_garbage_collection(self):
        """强制垃圾回收（含matplotlib资源清理）"""
        try:
            collected = gc.collect()
            self.logger.debug(f"垃圾回收完成，清理了{collected}个对象")

            try:
                import matplotlib.pyplot as plt
                for fig_num in plt.get_fignums():
                    fig = plt.figure(fig_num)
                    if not hasattr(fig, '_keep_alive') or not fig._keep_alive:
                        plt.close(fig)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(f"垃圾回收时出错: {e}")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            # 这里可以添加临时文件清理逻辑
            pass
        except Exception as e:
            self.logger.error(f"清理临时文件时出错: {e}")
    
    def _cleanup_caches(self):
        """清理缓存"""
        try:
            # 这里可以添加缓存清理逻辑
            pass
        except Exception as e:
            self.logger.error(f"清理缓存时出错: {e}")
    
    def get_optimization_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        cpu_percent = self.system_status['cpu_percent']
        memory_percent = self.system_status['memory_percent']
        
        if cpu_percent > self.thresholds['cpu_critical']:
            recommendations.append("CPU使用率过高，建议关闭不必要的功能")
        
        if memory_percent > self.thresholds['memory_critical']:
            recommendations.append("内存使用率过高，建议重启应用程序")
        
        if self.system_status['active_timers'] > self.thresholds['timer_warning']:
            recommendations.append("活跃定时器过多，建议检查定时器使用")
        
        if self.system_status['active_threads'] > self.thresholds['thread_warning']:
            recommendations.append("活跃线程过多，建议检查线程管理")
        
        return recommendations
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return self.system_status.copy()
    
    def get_current_optimization_level(self) -> str:
        """获取当前优化级别"""
        return self.current_optimization_level
    
    def manual_optimization(self, level: str):
        """手动应用优化"""
        try:
            if level in self.optimization_strategies:
                self.current_optimization_level = level
                self._apply_optimization_strategy(level)
                self.logger.info(f"手动应用{level}优化策略")
            else:
                self.logger.warning(f"未知的优化级别: {level}")
        except Exception as e:
            self.logger.error(f"手动优化时出错: {e}")

class TimerManager(QObject):
    """定时器管理器，统一管理所有定时器"""
    
    timer_created = Signal(str, int)  # 定时器名称, 间隔
    timer_destroyed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("TimerManager")
        self.timers = {}  # 定时器注册表
        self.timer_mutex = QMutex()
        
    def create_timer(self, name: str, interval: int, callback) -> QTimer:
        """创建并注册定时器"""
        try:
            with QMutexLocker(self.timer_mutex):
                if name in self.timers:
                    self.logger.warning(f"定时器{name}已存在，将被替换")
                    self.destroy_timer(name)
                
                timer = QTimer()
                timer.timeout.connect(callback)
                timer.start(interval)
                
                self.timers[name] = {
                    'timer': timer,
                    'interval': interval,
                    'callback': callback,
                    'created_time': time.time()
                }
                
                self.timer_created.emit(name, interval)
                self.logger.info(f"创建定时器: {name}, 间隔: {interval}ms")
                
                return timer
                
        except Exception as e:
            self.logger.error(f"创建定时器{name}时出错: {e}")
            return None
    
    def destroy_timer(self, name: str):
        """销毁定时器"""
        try:
            with QMutexLocker(self.timer_mutex):
                if name in self.timers:
                    timer_info = self.timers[name]
                    timer_info['timer'].stop()
                    timer_info['timer'].deleteLater()
                    del self.timers[name]
                    
                    self.timer_destroyed.emit(name)
                    self.logger.info(f"销毁定时器: {name}")
                    
        except Exception as e:
            self.logger.error(f"销毁定时器{name}时出错: {e}")
    
    def get_active_timers(self) -> List[str]:
        """获取活跃定时器列表"""
        with QMutexLocker(self.timer_mutex):
            return list(self.timers.keys())
    
    def get_timer_count(self) -> int:
        """获取定时器数量"""
        with QMutexLocker(self.timer_mutex):
            return len(self.timers)
    
    def cleanup_unused_timers(self, max_age_seconds: int = 300):
        """清理长时间未使用的定时器"""
        try:
            current_time = time.time()
            with QMutexLocker(self.timer_mutex):
                timers_to_remove = []
                
                for name, info in self.timers.items():
                    if current_time - info['created_time'] > max_age_seconds:
                        timers_to_remove.append(name)
                
                for name in timers_to_remove:
                    self.destroy_timer(name)
                    
                if timers_to_remove:
                    self.logger.info(f"清理了{len(timers_to_remove)}个未使用的定时器")
                    
        except Exception as e:
            self.logger.error(f"清理未使用定时器时出错: {e}")
    
    def destroy_all_timers(self):
        """销毁所有定时器"""
        try:
            with QMutexLocker(self.timer_mutex):
                timer_names = list(self.timers.keys())
                for name in timer_names:
                    self.destroy_timer(name)
                    
                self.logger.info("所有定时器已销毁")
                
        except Exception as e:
            self.logger.error(f"销毁所有定时器时出错: {e}")

# 全局实例
performance_optimizer = SystemPerformanceOptimizer()
timer_manager = TimerManager()

