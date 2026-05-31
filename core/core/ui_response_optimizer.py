import logging
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

class UIResponseOptimizer:
    """UI响应优化器"""
    
    def __init__(self, max_cache_size: int = 100):
        self.response_cache = lru_cache(maxsize=max_cache_size)(self._cached_response)
        self.response_times = {}
    
    def optimize_response(self, response_func, *args, **kwargs):
        """优化响应函数"""
        start_time = time.time()
        try:
            result = response_func(*args, **kwargs)
            end_time = time.time()
            
            # 记录响应时间
            func_name = response_func.__name__
            self._record_response_time(func_name, end_time - start_time)
            
            # 如果响应慢，触发优化
            if end_time - start_time > 0.1:  # 100ms阈值
                logger.warning(f"响应慢: {func_name} 用了 {end_time - start_time}s")
                # 可以添加自动优化，如异步执行
            
            return result
        except Exception as e:
            logger.error(f"响应优化失败: {e}")
            raise
    
    def _cached_response(self, key, response_func, *args, **kwargs):
        """缓存响应"""
        return response_func(*args, **kwargs)
    
    def _record_response_time(self, func_name: str, response_time: float):
        """记录响应时间"""
        if func_name not in self.response_times:
            self.response_times[func_name] = []
        self.response_times[func_name].append(response_time)
