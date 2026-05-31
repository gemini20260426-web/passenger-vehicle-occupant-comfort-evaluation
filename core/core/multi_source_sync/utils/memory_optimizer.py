#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️ DEPRECATED: 此组件已废弃

此文件保留仅为了向后兼容，将在未来版本中移除。
请使用 core.core.memory_optimizer.MemoryOptimizer 作为统一的内存优化器。

内存优化管理器
提供智能内存管理功能，支持动态内存分配和垃圾回收优化

主要功能：
- 智能内存分配
- 动态缓冲区管理
- 内存使用监控
- 垃圾回收优化

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import gc
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
import numpy as np

logger = logging.getLogger(__name__)


class MemoryStrategy(Enum):
    """内存策略枚举"""
    AGGRESSIVE = "aggressive"      # 激进策略：优先性能
    BALANCED = "balanced"          # 平衡策略：性能和内存平衡
    CONSERVATIVE = "conservative"  # 保守策略：优先内存节省


@dataclass
class MemoryMetrics:
    """内存使用指标"""
    total_memory: float = 0.0      # 总内存 (MB)
    used_memory: float = 0.0       # 已使用内存 (MB)
    available_memory: float = 0.0   # 可用内存 (MB)
    memory_percent: float = 0.0     # 内存使用率 (%)
    buffer_count: int = 0           # 缓冲区数量
    total_buffer_size: float = 0.0  # 总缓冲区大小 (MB)
    gc_count: int = 0               # 垃圾回收次数
    timestamp: float = 0.0          # 时间戳


class MemoryOptimizedBuffer:
    """内存优化缓冲区"""
    
    def __init__(self, initial_size: int = 1024, max_size: int = 10000):
        self.initial_size = initial_size
        self.max_size = max_size
        self.current_size = initial_size
        
        # 缓冲区
        self.buffer = []
        self.buffer_lock = threading.Lock()
        
        # 性能监控
        self.access_count = 0
        self.last_access = time.time()
        self.creation_time = time.time()
        
        logger.info(f"内存优化缓冲区已创建，初始大小: {initial_size}, 最大大小: {max_size}")
    
    def add_data(self, data: Any) -> bool:
        """添加数据到缓冲区"""
        try:
            with self.buffer_lock:
                # 检查缓冲区大小
                if len(self.buffer) >= self.current_size:
                    # 缓冲区满，尝试扩容
                    if not self._expand_buffer():
                        # 扩容失败，清理旧数据
                        self._cleanup_old_data()
                
                self.buffer.append(data)
                self.access_count += 1
                self.last_access = time.time()
                
                return True
                
        except Exception as e:
            logger.error(f"添加数据到缓冲区失败: {e}")
            return False
    
    def get_data(self, index: int = -1) -> Optional[Any]:
        """从缓冲区获取数据"""
        try:
            with self.buffer_lock:
                if not self.buffer:
                    return None
                
                if index < 0:
                    index = len(self.buffer) + index
                
                if 0 <= index < len(self.buffer):
                    self.access_count += 1
                    self.last_access = time.time()
                    return self.buffer[index]
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"从缓冲区获取数据失败: {e}")
            return None
    
    def get_all_data(self) -> List[Any]:
        """获取所有数据"""
        try:
            with self.buffer_lock:
                data = self.buffer.copy()
                self.access_count += 1
                self.last_access = time.time()
                return data
                
        except Exception as e:
            logger.error(f"获取所有数据失败: {e}")
            return []
    
    def clear_buffer(self):
        """清空缓冲区"""
        try:
            with self.buffer_lock:
                self.buffer.clear()
                self.access_count = 0
                logger.info("缓冲区已清空")
                
        except Exception as e:
            logger.error(f"清空缓冲区失败: {e}")
    
    def get_buffer_info(self) -> Dict[str, Any]:
        """获取缓冲区信息"""
        with self.buffer_lock:
            return {
                'current_size': len(self.buffer),
                'max_size': self.max_size,
                'access_count': self.access_count,
                'last_access': self.last_access,
                'creation_time': self.creation_time,
                'memory_usage': self._estimate_memory_usage()
            }
    
    def _expand_buffer(self) -> bool:
        """扩容缓冲区"""
        try:
            if self.current_size >= self.max_size:
                return False
            
            # 计算新大小
            new_size = min(self.current_size * 2, self.max_size)
            
            # 检查内存是否足够
            if not self._check_memory_availability(new_size):
                return False
            
            self.current_size = new_size
            logger.info(f"缓冲区已扩容至: {new_size}")
            return True
            
        except Exception as e:
            logger.error(f"扩容缓冲区失败: {e}")
            return False
    
    def _cleanup_old_data(self):
        """清理旧数据"""
        try:
            if len(self.buffer) <= self.initial_size:
                return
            
            # 保留最新的数据
            keep_count = self.initial_size
            removed_count = len(self.buffer) - keep_count
            
            self.buffer = self.buffer[-keep_count:]
            
            logger.info(f"已清理 {removed_count} 个旧数据项")
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
    
    def _check_memory_availability(self, required_size: int) -> bool:
        """检查内存可用性"""
        try:
            # 估算所需内存
            estimated_memory = required_size * 0.001  # 假设每个数据项占用1KB
            
            # 获取系统内存信息
            memory_info = psutil.virtual_memory()
            available_memory = memory_info.available / (1024 * 1024)  # 转换为MB
            
            # 检查是否有足够内存
            return available_memory > estimated_memory * 2  # 预留2倍内存
            
        except ImportError:
            # psutil未安装，假设内存充足
            return True
        except Exception as e:
            logger.error(f"检查内存可用性失败: {e}")
            return False
    
    def _estimate_memory_usage(self) -> float:
        """估算内存使用量"""
        try:
            # 简化的内存估算
            item_count = len(self.buffer)
            estimated_bytes = item_count * 1024  # 假设每个数据项占用1KB
            return estimated_bytes / (1024 * 1024)  # 转换为MB
            
        except Exception as e:
            logger.error(f"估算内存使用量失败: {e}")
            return 0.0


class MemoryOptimizer:
    """内存优化管理器"""
    
    def __init__(self, strategy: MemoryStrategy = MemoryStrategy.BALANCED, auto_start: bool = False):
        self.strategy = strategy
        self.buffers = {}
        self.memory_thresholds = self._get_strategy_thresholds()
        
        # 性能监控
        self.metrics = MemoryMetrics()
        self.metrics_history = []
        self._max_history_size = 100  # 限制历史记录大小
        self.monitoring_enabled = True
        self.monitoring_thread = None
        
        # 垃圾回收控制
        self.gc_enabled = True
        self.gc_threshold = 0.8  # 内存使用率超过80%时触发GC
        
        # 启动内存监控
        if auto_start:
            self.start_memory_monitoring()
        
        logger.info(f"内存优化管理器已初始化，策略: {strategy.value}")
    
    def _get_strategy_thresholds(self) -> Dict[str, float]:
        """获取策略阈值"""
        if self.strategy == MemoryStrategy.AGGRESSIVE:
            return {
                'memory_warning': 0.9,    # 90%警告
                'memory_critical': 0.95,  # 95%严重
                'gc_threshold': 0.9,     # 90%触发GC
                'buffer_expansion': 0.7   # 70%时扩容
            }
        elif self.strategy == MemoryStrategy.CONSERVATIVE:
            return {
                'memory_warning': 0.7,    # 70%警告
                'memory_critical': 0.8,  # 80%严重
                'gc_threshold': 0.75,    # 75%触发GC
                'buffer_expansion': 0.5   # 50%时扩容
            }
        else:  # BALANCED
            return {
                'memory_warning': 0.8,    # 80%警告
                'memory_critical': 0.9,  # 90%严重
                'gc_threshold': 0.8,     # 80%触发GC
                'buffer_expansion': 0.6   # 60%时扩容
            }
    
    def create_buffer(self, buffer_id: str, initial_size: int = 1024, max_size: int = 10000) -> MemoryOptimizedBuffer:
        """创建优化缓冲区"""
        try:
            if buffer_id in self.buffers:
                logger.warning(f"缓冲区 {buffer_id} 已存在，将被覆盖")
            
            buffer = MemoryOptimizedBuffer(initial_size, max_size)
            self.buffers[buffer_id] = buffer
            
            logger.info(f"缓冲区 {buffer_id} 已创建")
            return buffer
            
        except Exception as e:
            logger.error(f"创建缓冲区 {buffer_id} 失败: {e}")
            return None
    
    def get_buffer(self, buffer_id: str) -> Optional[MemoryOptimizedBuffer]:
        """获取缓冲区"""
        return self.buffers.get(buffer_id)
    
    def remove_buffer(self, buffer_id: str) -> bool:
        """移除缓冲区"""
        try:
            if buffer_id in self.buffers:
                buffer = self.buffers[buffer_id]
                buffer.clear_buffer()
                del self.buffers[buffer_id]
                
                logger.info(f"缓冲区 {buffer_id} 已移除")
                return True
            else:
                logger.warning(f"缓冲区 {buffer_id} 不存在")
                return False
                
        except Exception as e:
            logger.error(f"移除缓冲区 {buffer_id} 失败: {e}")
            return False
    
    def optimize_memory(self):
        """优化内存使用"""
        try:
            # 1. 检查内存使用情况
            current_memory = self._get_current_memory_usage()
            
            # 2. 根据策略执行优化
            if current_memory > self.memory_thresholds['memory_critical']:
                self._emergency_memory_cleanup()
            elif current_memory > self.memory_thresholds['memory_warning']:
                self._aggressive_memory_cleanup()
            elif current_memory > self.memory_thresholds['gc_threshold']:
                self._trigger_garbage_collection()
            
            # 3. 优化缓冲区
            self._optimize_buffers()
            
            # 4. 更新指标
            self._update_memory_metrics()
            
        except Exception as e:
            logger.error(f"内存优化失败: {e}")
    
    def _get_current_memory_usage(self) -> float:
        """获取当前内存使用率"""
        try:
            memory_info = psutil.virtual_memory()
            return memory_info.percent / 100.0
            
        except ImportError:
            # psutil未安装，返回默认值
            return 0.5
        except Exception as e:
            logger.error(f"获取内存使用率失败: {e}")
            return 0.5
    
    def _emergency_memory_cleanup(self):
        """紧急内存清理"""
        logger.warning("执行紧急内存清理")
        
        # 1. 强制垃圾回收
        self._force_garbage_collection()
        
        # 2. 清理所有缓冲区
        for buffer_id, buffer in self.buffers.items():
            buffer.clear_buffer()
        
        # 3. 等待系统释放内存
        time.sleep(1)
    
    def _aggressive_memory_cleanup(self):
        """激进内存清理"""
        logger.info("执行激进内存清理")
        
        # 1. 触发垃圾回收
        self._trigger_garbage_collection()
        
        # 2. 清理不活跃的缓冲区
        current_time = time.time()
        for buffer_id, buffer in self.buffers.items():
            buffer_info = buffer.get_buffer_info()
            last_access = buffer_info['last_access']
            
            # 如果缓冲区超过5分钟未访问，清理一半数据
            if current_time - last_access > 300:  # 5分钟
                buffer._cleanup_old_data()
    
    def _trigger_garbage_collection(self):
        """触发垃圾回收"""
        if not self.gc_enabled:
            return
        
        try:
            # 记录GC前的内存使用
            before_memory = self._get_current_memory_usage()
            
            # 执行垃圾回收
            collected = gc.collect()
            
            # 记录GC后的内存使用
            after_memory = self._get_current_memory_usage()
            
            # 更新指标
            self.metrics.gc_count += 1
            
            logger.info(f"垃圾回收完成，收集对象: {collected}, "
                       f"内存使用: {before_memory:.2%} -> {after_memory:.2%}")
            
        except Exception as e:
            logger.error(f"垃圾回收失败: {e}")
    
    def _force_garbage_collection(self):
        """强制垃圾回收"""
        try:
            # 设置更激进的GC参数
            gc.set_threshold(0, 0, 0)
            
            # 执行多次GC
            for i in range(3):
                collected = gc.collect()
                if collected == 0:
                    break
                time.sleep(0.1)
            
            # 恢复默认GC参数
            gc.set_threshold(700, 10, 10)
            
            logger.info("强制垃圾回收完成")
            
        except Exception as e:
            logger.error(f"强制垃圾回收失败: {e}")
    
    def _optimize_buffers(self):
        """优化缓冲区"""
        try:
            current_memory = self._get_current_memory_usage()
            
            for buffer_id, buffer in self.buffers.items():
                buffer_info = buffer.get_buffer_info()
                
                # 检查缓冲区使用率
                usage_ratio = buffer_info['current_size'] / buffer_info['max_size']
                
                # 根据策略决定是否优化
                if usage_ratio > self.memory_thresholds['buffer_expansion']:
                    # 缓冲区使用率较高，考虑扩容
                    if current_memory < 0.7:  # 内存充足时扩容
                        buffer._expand_buffer()
                elif usage_ratio < 0.3:
                    # 缓冲区使用率较低，考虑收缩
                    if current_memory > 0.6:  # 内存紧张时收缩
                        buffer._cleanup_old_data()
                        
        except Exception as e:
            logger.error(f"优化缓冲区失败: {e}")
    
    def _update_memory_metrics(self):
        """更新内存指标"""
        try:
            # 获取系统内存信息
            memory_info = psutil.virtual_memory()
            
            self.metrics.total_memory = memory_info.total / (1024 * 1024)  # MB
            self.metrics.used_memory = memory_info.used / (1024 * 1024)    # MB
            self.metrics.available_memory = memory_info.available / (1024 * 1024)  # MB
            self.metrics.memory_percent = memory_info.percent
            self.metrics.timestamp = time.time()
            
            # 计算缓冲区统计
            total_buffer_size = 0
            for buffer in self.buffers.values():
                buffer_info = buffer.get_buffer_info()
                total_buffer_size += buffer_info['memory_usage']
            
            self.metrics.buffer_count = len(self.buffers)
            self.metrics.total_buffer_size = total_buffer_size
            
            # 记录历史
            self.metrics_history.append(self.metrics.__dict__.copy())
            
            # 保持历史记录在合理大小
            if len(self.metrics_history) > 100:
                self.metrics_history.pop(0)
                
        except ImportError:
            logger.warning("psutil未安装，无法获取详细内存信息")
        except Exception as e:
            logger.error(f"更新内存指标失败: {e}")
    
    def start_memory_monitoring(self):
        """启动内存监控"""
        if self.monitoring_enabled and not self.monitoring_thread:
            self.monitoring_thread = threading.Thread(
                target=self._memory_monitoring_worker,
                daemon=True
            )
            self.monitoring_thread.start()
            logger.info("内存监控已启动")
    
    def _memory_monitoring_worker(self):
        """内存监控工作线程"""
        while self.monitoring_enabled:
            try:
                # 执行内存优化
                self.optimize_memory()
                
                # 每30秒检查一次
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"内存监控错误: {e}")
                time.sleep(60)
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """获取内存使用摘要"""
        return {
            'strategy': self.strategy.value,
            'current_memory_usage': self._get_current_memory_usage(),
            'buffer_count': len(self.buffers),
            'total_buffer_size': sum(b.get_buffer_info()['memory_usage'] 
                                   for b in self.buffers.values()),
            'gc_enabled': self.gc_enabled,
            'gc_count': self.metrics.gc_count,
            'memory_thresholds': self.memory_thresholds
        }
    
    def set_strategy(self, strategy: MemoryStrategy):
        """设置内存策略"""
        self.strategy = strategy
        self.memory_thresholds = self._get_strategy_thresholds()
        logger.info(f"内存策略已切换为: {strategy.value}")
    
    def set_gc_enabled(self, enabled: bool):
        """设置是否启用垃圾回收"""
        self.gc_enabled = enabled
        logger.info(f"垃圾回收已{'启用' if enabled else '禁用'}")
    
    def shutdown(self):
        """关闭内存优化管理器"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        
        # 清理所有缓冲区
        for buffer_id in list(self.buffers.keys()):
            self.remove_buffer(buffer_id)
        
        logger.info("内存优化管理器已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建内存优化管理器
    optimizer = MemoryOptimizer(strategy=MemoryStrategy.BALANCED)
    
    # 创建缓冲区
    buffer1 = optimizer.create_buffer('test_buffer_1', initial_size=100, max_size=1000)
    buffer2 = optimizer.create_buffer('test_buffer_2', initial_size=200, max_size=2000)
    
    # 添加测试数据
    for i in range(50):
        buffer1.add_data(f"data_{i}")
        buffer2.add_data(f"value_{i}")
    
    # 获取内存摘要
    summary = optimizer.get_memory_summary()
    logger.info(f"内存摘要: {summary}")
    
    # 执行内存优化
    optimizer.optimize_memory()
    
    # 关闭管理器
    optimizer.shutdown()
