import logging
from typing import Dict, Any
import time

logger = logging.getLogger(__name__)

class UnifiedErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.error_history = []
        self.recovery_strategies = {
            'retry': self._retry_strategy,
            'fallback': self._fallback_strategy,
            'ignore': self._ignore_strategy
        }
    
    def handle_error(self, error_type: str, error_details: Dict[str, Any], recovery_strategy: str = 'retry'):
        """处理错误"""
        try:
            logger.error(f"处理错误: {error_type} - {error_details}")
            
            # 记录错误历史
            self._record_error(error_type, error_details)
            
            # 执行恢复策略
            if recovery_strategy in self.recovery_strategies:
                return self.recovery_strategies[recovery_strategy](error_details)
            else:
                logger.warning(f"未知恢复策略: {recovery_strategy}")
                return self._default_recovery(error_details)
            
        except Exception as e:
            logger.critical(f"错误处理失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _record_error(self, error_type: str, error_details: Dict[str, Any]):
        """记录错误"""
        self.error_history.append({
            'type': error_type,
            'details': error_details,
            'timestamp': time.time()
        })
    
    def _retry_strategy(self, details: Dict[str, Any]):
        retry_count = details.get('retry_count', 3)
        retry_delay = details.get('retry_delay', 0.5)
        retry_backoff = details.get('retry_backoff', 2.0)
        retry_callback = details.get('callback')
        if retry_callback is None:
            return {'success': False, 'reason': '重试回调函数未提供'}
        for attempt in range(retry_count):
            try:
                result = retry_callback()
                return {'success': True, 'attempt': attempt + 1, 'result': result}
            except Exception as e:
                logger.warning(f"重试第 {attempt + 1}/{retry_count} 次失败: {e}")
                if attempt < retry_count - 1:
                    delay = retry_delay * (retry_backoff ** attempt)
                    time.sleep(delay)
        return {'success': False, 'reason': f'{retry_count}次重试全部失败'}
    
    def _fallback_strategy(self, details: Dict[str, Any]):
        """回退策略"""
        # 实现回退逻辑，例如切换到模拟模式
        return {'success': True, 'mode': 'fallback'}
    
    def _ignore_strategy(self, details: Dict[str, Any]):
        """忽略策略"""
        return {'success': True, 'ignored': True}
    
    def _default_recovery(self, details: Dict[str, Any]):
        """默认恢复"""
        return {'success': False, 'reason': '无恢复策略'}
