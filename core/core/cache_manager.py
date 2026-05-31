# -*- coding: utf-8 -*-
"""
磁盘缓存管理器
使用 diskcache 库实现热数据在内存、冷数据在磁盘的智能缓存策略

主要功能：
- 热数据内存缓存（快速访问）
- 冷数据磁盘缓存（节省内存）
- 自动数据迁移（LRU策略）
- 缓存大小限制

版本: 1.0
创建时间: 2026-05-10
"""

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional, Dict
from collections import OrderedDict

try:
    import diskcache
    HAS_DISKCACHE = True
except ImportError:
    HAS_DISKCACHE = False
    diskcache = None

logger = logging.getLogger(__name__)


class DiskBackedCache:
    """磁盘支持的缓存管理器
    
    热数据存储在内存中，冷数据自动迁移到磁盘
    """
    
    def __init__(self, 
                 cache_dir: str = './cache',
                 max_memory_items: int = 100,
                 max_disk_size_mb: int = 500):
        """
        初始化磁盘缓存管理器
        
        Args:
            cache_dir: 磁盘缓存目录
            max_memory_items: 内存中最大热数据项数
            max_disk_size_mb: 磁盘缓存最大大小（MB）
        """
        self.max_memory_items = max_memory_items
        self._memory_cache: OrderedDict = OrderedDict()  # 热数据
        self._disk_cache = None  # 冷数据（懒加载）
        self._cache_dir = cache_dir
        self._max_disk_size_mb = max_disk_size_mb
        self._disk_cache_initialized = False
        self._init_lock = threading.Lock()
        
        # 统计信息
        self._hits = 0
        self._misses = 0
        self._disk_reads = 0
        self._disk_writes = 0
        
        logger.info(f"磁盘缓存管理器已创建: {cache_dir}")
    
    def _ensure_disk_cache(self):
        """确保磁盘缓存已初始化（懒加载）"""
        if self._disk_cache_initialized:
            return
        
        with self._init_lock:
            if self._disk_cache_initialized:
                return
            
            if HAS_DISKCACHE:
                try:
                    cache_path = Path(self._cache_dir)
                    cache_path.mkdir(parents=True, exist_ok=True)
                    self._disk_cache = diskcache.Cache(
                        str(cache_path),
                        size_limit=self._max_disk_size_mb * 1024 * 1024,
                        eviction_policy='least-recently-used',
                        timeout=1  # 减少锁等待时间
                    )
                    self._disk_cache_initialized = True
                    logger.info(f"磁盘缓存已初始化: {cache_path}")
                except Exception as e:
                    logger.error(f"初始化磁盘缓存失败: {e}")
                    self._disk_cache = None
                    self._disk_cache_initialized = True
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据
        
        优先从内存获取，如果不存在则从磁盘获取
        """
        # 尝试从内存缓存获取
        if key in self._memory_cache:
            self._hits += 1
            # 更新访问顺序（LRU）
            self._memory_cache.move_to_end(key)
            return self._memory_cache[key]
        
        # 尝试从磁盘缓存获取
        if self._disk_cache is not None:
            try:
                value = self._disk_cache.get(key)
                if value is not None:
                    self._hits += 1
                    self._disk_reads += 1
                    # 将数据提升到内存（热数据）
                    self._set_memory(key, value)
                    return value
            except Exception as e:
                logger.error(f"从磁盘缓存获取失败: {e}")
        
        self._misses += 1
        return None
    
    def get_latest(self) -> Optional[Any]:
        """获取最新的数据项（最后存入的）"""
        if self._memory_cache:
            return next(reversed(self._memory_cache.values()))
        
        # 不遍历磁盘缓存（避免阻塞），直接返回None
        return None
    
    def set(self, key: str, value: Any):
        """设置缓存数据
        
        新数据先存入内存，内存满时迁移到磁盘
        """
        # 先存入内存
        self._set_memory(key, value)
    
    def _set_memory(self, key: str, value: Any):
        """将数据存入内存缓存"""
        # 如果已存在，先移除
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
            self._memory_cache[key] = value
            return
        
        # 检查内存缓存大小
        if len(self._memory_cache) >= self.max_memory_items:
            # 内存满，将最旧的数据迁移到磁盘
            self._evict_oldest()
        
        # 存入内存
        self._memory_cache[key] = value
    
    def _evict_oldest(self):
        """将最旧的数据迁移到磁盘"""
        if not self._memory_cache:
            return
        
        # 获取最旧的项
        oldest_key, oldest_value = next(iter(self._memory_cache.items()))
        
        # 懒加载磁盘缓存
        self._ensure_disk_cache()
        
        # 迁移到磁盘
        if self._disk_cache is not None:
            try:
                self._disk_cache.set(oldest_key, oldest_value)
                self._disk_writes += 1
            except Exception as e:
                logger.error(f"迁移数据到磁盘失败: {e}")
        
        # 从内存移除
        del self._memory_cache[oldest_key]
    
    def delete(self, key: str) -> bool:
        """删除缓存数据"""
        deleted = False
        
        # 从内存删除
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
        
        # 从磁盘删除
        if self._disk_cache is not None:
            try:
                if self._disk_cache.delete(key):
                    deleted = True
            except Exception as e:
                logger.error(f"从磁盘缓存删除失败: {e}")
        
        return deleted
    
    def clear(self):
        """清空所有缓存"""
        self._memory_cache.clear()
        
        if self._disk_cache is not None:
            try:
                self._disk_cache.clear()
                logger.info("磁盘缓存已清空")
            except Exception as e:
                logger.error(f"清空磁盘缓存失败: {e}")
        
        logger.info("缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        disk_size = 0
        if self._disk_cache is not None:
            try:
                disk_size = self._disk_cache.volume()
            except:
                pass
        
        return {
            'memory_items': len(self._memory_cache),
            'max_memory_items': self.max_memory_items,
            'disk_size_mb': round(disk_size / (1024 * 1024), 2),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'disk_reads': self._disk_reads,
            'disk_writes': self._disk_writes
        }
    
    def close(self):
        """关闭缓存，释放资源"""
        if self._disk_cache is not None:
            try:
                self._disk_cache.close()
                logger.info("磁盘缓存已关闭")
            except Exception as e:
                logger.error(f"关闭磁盘缓存失败: {e}")
    
    def __len__(self):
        """返回缓存项数量（仅计算内存中的）"""
        return len(self._memory_cache)
    
    def __contains__(self, key):
        """检查键是否存在"""
        return key in self._memory_cache
    
    def __del__(self):
        """析构函数"""
        self.close()


# 全局缓存实例
_global_caches: Dict[str, DiskBackedCache] = {}


def get_cache(name: str = 'default', **kwargs) -> DiskBackedCache:
    """获取或创建全局缓存实例
    
    Args:
        name: 缓存名称
        **kwargs: 缓存配置参数
    
    Returns:
        DiskBackedCache 实例
    """
    if name not in _global_caches:
        _global_caches[name] = DiskBackedCache(**kwargs)
    return _global_caches[name]


def close_all_caches():
    """关闭所有全局缓存"""
    for name, cache in _global_caches.items():
        cache.close()
    _global_caches.clear()
    logger.info("所有全局缓存已关闭")
