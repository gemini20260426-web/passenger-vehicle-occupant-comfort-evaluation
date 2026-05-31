import logging
import gc
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)

class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self, check_interval: int = 120000, is_test: bool = False, auto_start: bool = False):
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._optimize_memory)
        self.check_interval = check_interval
        self.memory_threshold = 85.0
        self.cache_data = []
        self.max_cache_size = 50  # 减少缓存大小
        if auto_start and not is_test:
            self.start_optimizing()
    
    def start_optimizing(self):
        """启动优化"""
        self.check_timer.start(self.check_interval)
        logger.info("内存优化已启动")
    
    def stop_optimizing(self):
        """停止优化"""
        self.check_timer.stop()
        logger.info("内存优化已停止")
    
    def _optimize_memory(self):
        """优化内存"""
        if not PSUTIL_AVAILABLE:
            self.stop_optimizing()
            return
        try:
            memory_usage = psutil.virtual_memory().percent
            if memory_usage > self.memory_threshold:
                logger.info(f"内存使用率较高: {memory_usage}%，执行优化")
                
                # 执行垃圾回收
                collected = gc.collect()
                logger.info(f"垃圾回收完成: 清理了 {collected} 个对象")
                
                # 其他优化策略，例如清除缓存
                self._clear_caches()
                
                # 限制缓存大小
                if len(self.cache_data) > self.max_cache_size:
                    self.cache_data = self.cache_data[-self.max_cache_size:]
                    logger.info(f"缓存大小受限: 限制为 {self.max_cache_size} 项")
                
                # 释放其他资源
                self._release_additional_resources()
                
                # 重新检查
                new_usage = psutil.virtual_memory().percent
                logger.info(f"优化后内存使用率: {new_usage}%")
            else:
                logger.info(f"内存使用率正常: {memory_usage}%")
        except Exception as e:
            logger.error(f"内存优化失败: {e}")
    
    def _clear_caches(self):
        """清除缓存"""
        try:
            initial_len = len(self.cache_data)
            self.cache_data.clear()
            logger.info(f"🧹 缓存已清除: 移除了 {initial_len} 个缓存项")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
    
    def _release_additional_resources(self):
        try:
            import sys
            large_modules = []
            for name, mod in list(sys.modules.items()):
                try:
                    size = sys.getsizeof(mod)
                    if size > 1024 * 1024:
                        large_modules.append((name, size))
                except Exception:
                    pass
            if large_modules:
                large_modules.sort(key=lambda x: x[1], reverse=True)
                logger.info(f"检测到 {len(large_modules)} 个大内存模块")
        except Exception as e:
            logger.error(f"释放其他资源失败: {e}")
