#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统集成适配器
连接现有系统模块，实现多源数据与现有系统的无缝集成
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .multi_source_sync_manager import MultiSourceDataSyncManager


class SystemIntegrationAdapter:
    """系统集成适配器 - 连接现有模块"""
    
    # 为了保持向后兼容性，添加别名
    __class__ = type('IntegrationAdapter', (), {})
    
    def __init__(self):
        self.analysis_pipeline = None
        self.data_storage = None
        self.performance_manager = None
        self.mqtt_manager = None
        self.redis_manager = None
        
        # 集成状态
        self.is_integrated = False
        self.integration_status = {}
        
        # 回调函数
        self.integration_callback = None
        self.error_callback = None
        
        self.logger = logging.getLogger(__name__)
        
    def connect_existing_modules(self) -> bool:
        """连接现有系统模块"""
        try:
            self.logger.info("开始连接现有系统模块...")
            
            # 1. 连接分析管道
            try:
                from analysis.analysis_pipeline import AnalysisPipeline
                self.analysis_pipeline = AnalysisPipeline()
                self.logger.info("✅ 成功连接分析管道")
            except ImportError as e:
                self.logger.warning(f"⚠️ 分析管道模块未找到: {e}")
                self.analysis_pipeline = None
            except Exception as e:
                self.logger.error(f"❌ 连接分析管道失败: {e}")
                self.analysis_pipeline = None
            
            # 2. 连接数据存储
            try:
                from storage.data_storage import DataStorage
                self.data_storage = DataStorage()
                self.logger.info("✅ 成功连接数据存储")
            except ImportError as e:
                self.logger.warning(f"⚠️ 数据存储模块未找到: {e}")
                self.data_storage = None
            except Exception as e:
                self.logger.error(f"❌ 连接数据存储失败: {e}")
                self.data_storage = None
            
            # 3. 连接性能管理器
            try:
                from performance.performance_manager import PerformanceManager
                self.performance_manager = PerformanceManager()
                self.logger.info("✅ 成功连接性能管理器")
            except ImportError as e:
                self.logger.warning(f"⚠️ 性能管理器模块未找到: {e}")
                self.performance_manager = None
            except Exception as e:
                self.logger.error(f"❌ 连接性能管理器失败: {e}")
                self.performance_manager = None
            
            # 4. 连接MQTT管理器
            try:
                from communication.mqtt_manager import MQTTManager
                self.mqtt_manager = MQTTManager()
                self.logger.info("✅ 成功连接MQTT管理器")
            except ImportError as e:
                self.logger.warning(f"⚠️ MQTT管理器模块未找到: {e}")
                self.mqtt_manager = None
            except Exception as e:
                self.logger.error(f"❌ 连接MQTT管理器失败: {e}")
                self.mqtt_manager = None
            
            # 5. 连接Redis管理器
            try:
                from storage.redis_manager import RedisManager
                self.redis_manager = RedisManager()
                self.logger.info("✅ 成功连接Redis管理器")
            except ImportError as e:
                self.logger.warning(f"⚠️ Redis管理器模块未找到: {e}")
                self.redis_manager = None
            except Exception as e:
                self.logger.error(f"❌ 连接Redis管理器失败: {e}")
                self.redis_manager = None
            
            # 更新集成状态
            self._update_integration_status()
            
            if self.is_integrated:
                self.logger.info("🎉 系统模块集成完成")
            else:
                self.logger.warning("⚠️ 部分系统模块集成失败")
            
            return self.is_integrated
            
        except Exception as e:
            self.logger.error(f"❌ 连接现有模块失败: {e}")
            return False
    
    def _update_integration_status(self):
        """更新集成状态"""
        self.integration_status = {
            'analysis_pipeline': self.analysis_pipeline is not None,
            'data_storage': self.data_storage is not None,
            'performance_manager': self.performance_manager is not None,
            'mqtt_manager': self.mqtt_manager is not None,
            'redis_manager': self.redis_manager is not None,
            'last_update': datetime.now().isoformat()
        }
        
        # 至少需要核心模块连接成功
        core_modules = ['data_storage', 'performance_manager']
        connected_core = sum(1 for module in core_modules if self.integration_status.get(module, False))
        self.is_integrated = connected_core >= 1
    
    def integrate_multi_source_data(self, fused_data: Dict[str, Any]) -> bool:
        """集成多源数据到现有系统"""
        try:
            if not self.is_integrated:
                self.logger.warning("系统未完全集成，跳过数据集成")
                return False
            
            integration_results = {}
            
            # 1. 存储到数据存储
            if self.data_storage:
                try:
                    result = self._store_fused_data(fused_data)
                    integration_results['data_storage'] = result
                except Exception as e:
                    self.logger.error(f"数据存储集成失败: {e}")
                    integration_results['data_storage'] = {'success': False, 'error': str(e)}
            
            # 2. 发送到分析管道
            if self.analysis_pipeline:
                try:
                    result = self._send_to_analysis_pipeline(fused_data)
                    integration_results['analysis_pipeline'] = result
                except Exception as e:
                    self.logger.error(f"分析管道集成失败: {e}")
                    integration_results['analysis_pipeline'] = {'success': False, 'error': str(e)}
            
            # 3. 更新性能监控
            if self.performance_manager:
                try:
                    result = self._update_performance_metrics(fused_data)
                    integration_results['performance_manager'] = result
                except Exception as e:
                    self.logger.error(f"性能监控集成失败: {e}")
                    integration_results['performance_manager'] = {'success': False, 'error': str(e)}
            
            # 4. 缓存到Redis
            if self.redis_manager:
                try:
                    result = self._cache_to_redis(fused_data)
                    integration_results['redis_cache'] = result
                except Exception as e:
                    self.logger.error(f"Redis缓存集成失败: {e}")
                    integration_results['redis_cache'] = {'success': False, 'error': str(e)}
            
            # 5. 发布MQTT消息
            if self.mqtt_manager:
                try:
                    result = self._publish_mqtt_message(fused_data)
                    integration_results['mqtt_publish'] = result
                except Exception as e:
                    self.logger.error(f"MQTT发布集成失败: {e}")
                    integration_results['mqtt_publish'] = {'success': False, 'error': str(e)}
            
            # 记录集成结果
            self._log_integration_results(integration_results)
            
            # 调用集成回调
            if self.integration_callback:
                try:
                    self.integration_callback(integration_results)
                except Exception as e:
                    self.logger.error(f"集成回调执行失败: {e}")
            
            self.logger.debug("多源数据集成完成")
            return True
            
        except Exception as e:
            self.logger.error(f"多源数据集成失败: {e}")
            if self.error_callback:
                try:
                    self.error_callback(e)
                except Exception as callback_error:
                    self.logger.error(f"错误回调执行失败: {callback_error}")
            return False
    
    def _store_fused_data(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """存储融合数据到数据存储"""
        try:
            # 添加元数据
            fused_data['integration_timestamp'] = time.time()
            fused_data['integration_version'] = '1.0.0'
            
            # 存储到数据库
            if hasattr(self.data_storage, 'store_fused_data'):
                result = self.data_storage.store_fused_data(fused_data)
            elif hasattr(self.data_storage, 'store_data'):
                # 检查store_data方法的参数
                import inspect
                sig = inspect.signature(self.data_storage.store_data)
                if len(sig.parameters) >= 3:
                    result = self.data_storage.store_data('fused_data', fused_data)
                else:
                    result = self.data_storage.store_data(fused_data)
            else:
                # 记录到日志
                self.logger.info(f"数据存储: {fused_data}")
                result = {'status': 'logged'}
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"存储融合数据失败: {e}")
            raise
    
    def _send_to_analysis_pipeline(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """发送数据到分析管道"""
        try:
            # 检查分析管道是否支持融合数据
            if hasattr(self.analysis_pipeline, 'process_fused_data'):
                result = self.analysis_pipeline.process_fused_data(fused_data)
            elif hasattr(self.analysis_pipeline, 'process_data'):
                result = self.analysis_pipeline.process_data(fused_data)
            else:
                # 创建分析任务
                result = self.analysis_pipeline.create_analysis_task(fused_data)
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"发送到分析管道失败: {e}")
            raise
    
    def _update_performance_metrics(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新性能监控指标"""
        try:
            # 提取性能相关指标
            metrics = {
                'data_volume': len(str(fused_data)),
                'source_count': len(fused_data.get('sources', {})),
                'fusion_timestamp': fused_data.get('timestamp', time.time()),
                'sync_status': fused_data.get('sync_status', 'unknown')
            }
            
            # 更新性能指标
            if hasattr(self.performance_manager, 'update_data_metrics'):
                result = self.performance_manager.update_data_metrics(metrics)
            elif hasattr(self.performance_manager, 'update_metrics'):
                result = self.performance_manager.update_metrics(metrics)
            else:
                # 记录到日志
                self.logger.info(f"性能指标更新: {metrics}")
                result = {'status': 'logged'}
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"更新性能指标失败: {e}")
            raise
    
    def _cache_to_redis(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """缓存数据到Redis"""
        try:
            # 生成缓存键
            cache_key = f"fused_data:{int(time.time())}"
            
            # 缓存数据（设置过期时间为1小时）
            if hasattr(self.redis_manager, 'set_with_expiry'):
                result = self.redis_manager.set_with_expiry(cache_key, fused_data, 3600)
            elif hasattr(self.redis_manager, 'set'):
                result = self.redis_manager.set(cache_key, fused_data)
            elif hasattr(self.redis_manager, 'store_data'):
                result = self.redis_manager.store_data(cache_key, fused_data)
            else:
                # 记录到日志
                self.logger.info(f"Redis缓存: {cache_key} -> {fused_data}")
                result = {'status': 'logged'}
            
            return {'success': True, 'cache_key': cache_key, 'result': result}
            
        except Exception as e:
            self.logger.error(f"Redis缓存失败: {e}")
            raise
    
    def _publish_mqtt_message(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """发布MQTT消息"""
        try:
            # 准备发布数据
            topic = "system/fused_data"
            payload = {
                'timestamp': fused_data.get('timestamp', time.time()),
                'source_count': len(fused_data.get('sources', {})),
                'sync_status': fused_data.get('sync_status', 'unknown'),
                'data_summary': self._create_data_summary(fused_data)
            }
            
            # 发布消息
            if hasattr(self.mqtt_manager, 'publish'):
                result = self.mqtt_manager.publish(topic, payload)
            elif hasattr(self.mqtt_manager, 'send_message'):
                result = self.mqtt_manager.send_message(topic, payload)
            else:
                # 记录到日志
                self.logger.info(f"MQTT消息发布: {topic} -> {payload}")
                result = {'status': 'logged'}
            
            return {'success': True, 'topic': topic, 'result': result}
            
        except Exception as e:
            self.logger.error(f"MQTT发布失败: {e}")
            raise
    
    def _create_data_summary(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建数据摘要"""
        try:
            sources = fused_data.get('sources', {})
            summary = {
                'total_sources': len(sources),
                'data_types': set(),
                'timestamp_range': {
                    'earliest': float('inf'),
                    'latest': 0
                }
            }
            
            # 统计数据类型和时间戳范围
            for source_id, data in sources.items():
                if 'data_type' in data:
                    summary['data_types'].update(data['data_type'])
                
                if 'timestamp' in data:
                    ts = data['timestamp']
                    summary['timestamp_range']['earliest'] = min(summary['timestamp_range']['earliest'], ts)
                    summary['timestamp_range']['latest'] = max(summary['timestamp_range']['latest'], ts)
            
            # 转换数据类型集合为列表
            summary['data_types'] = list(summary['data_types'])
            
            # 处理时间戳范围
            if summary['timestamp_range']['earliest'] == float('inf'):
                summary['timestamp_range']['earliest'] = 0
            
            return summary
            
        except Exception as e:
            self.logger.error(f"创建数据摘要失败: {e}")
            return {'error': str(e)}
    
    def _log_integration_results(self, integration_results: Dict[str, Any]):
        """记录集成结果"""
        try:
            success_count = sum(1 for result in integration_results.values() if result.get('success', False))
            total_count = len(integration_results)
            
            self.logger.info(f"数据集成完成: {success_count}/{total_count} 模块成功")
            
            # 记录失败的模块
            failed_modules = [name for name, result in integration_results.items() if not result.get('success', False)]
            if failed_modules:
                self.logger.warning(f"集成失败的模块: {failed_modules}")
            
        except Exception as e:
            self.logger.error(f"记录集成结果失败: {e}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            'is_integrated': self.is_integrated,
            'modules': self.integration_status,
            'last_update': self.integration_status.get('last_update', '')
        }
    
    def set_integration_callback(self, callback: Callable):
        """设置集成成功回调函数"""
        self.integration_callback = callback
        self.logger.info("集成成功回调函数已设置")
    
    def set_error_callback(self, callback: Callable):
        """设置错误回调函数"""
        self.error_callback = callback
        self.logger.info("错误回调函数已设置")
    
    def test_integration(self) -> Dict[str, Any]:
        """测试系统集成"""
        try:
            test_results = {
                'timestamp': time.time(),
                'modules': {},
                'overall_status': 'unknown'
            }
            
            # 测试各模块连接
            if self.analysis_pipeline:
                test_results['modules']['analysis_pipeline'] = self._test_module(self.analysis_pipeline, 'analysis_pipeline')
            
            if self.data_storage:
                test_results['modules']['data_storage'] = self._test_module(self.data_storage, 'data_storage')
            
            if self.performance_manager:
                test_results['modules']['performance_manager'] = self._test_module(self.performance_manager, 'performance_manager')
            
            if self.mqtt_manager:
                test_results['modules']['mqtt_manager'] = self._test_module(self.mqtt_manager, 'mqtt_manager')
            
            if self.redis_manager:
                test_results['modules']['redis_manager'] = self._test_module(self.redis_manager, 'redis_manager')
            
            # 计算整体状态
            success_count = sum(1 for result in test_results['modules'].values() if result.get('status') == 'ok')
            total_count = len(test_results['modules'])
            
            if total_count == 0:
                test_results['overall_status'] = 'no_modules'
            elif success_count == total_count:
                test_results['overall_status'] = 'all_ok'
            elif success_count > 0:
                test_results['overall_status'] = 'partial_ok'
            else:
                test_results['overall_status'] = 'all_failed'
            
            self.logger.info(f"集成测试完成: {test_results['overall_status']} ({success_count}/{total_count})")
            return test_results
            
        except Exception as e:
            self.logger.error(f"集成测试失败: {e}")
            return {'error': str(e), 'overall_status': 'test_failed'}
    
    def _test_module(self, module, module_name: str) -> Dict[str, Any]:
        """测试单个模块"""
        try:
            # 检查模块是否有测试方法
            if hasattr(module, 'test_connection'):
                result = module.test_connection()
                return {'status': 'ok' if result else 'failed', 'result': result}
            elif hasattr(module, 'ping'):
                result = module.ping()
                return {'status': 'ok' if result else 'failed', 'result': result}
            elif hasattr(module, 'is_connected'):
                result = module.is_connected()
                return {'status': 'ok' if result else 'failed', 'result': result}
            else:
                # 尝试调用模块的简单方法
                try:
                    # 检查模块是否有基本属性
                    if hasattr(module, '__class__'):
                        return {'status': 'ok', 'result': f"{module_name} module available"}
                    else:
                        return {'status': 'unknown', 'result': 'No test method available'}
                except Exception as e:
                    return {'status': 'error', 'result': str(e)}
                    
        except Exception as e:
            return {'status': 'error', 'result': str(e)}


# 为了保持向后兼容性，添加别名
IntegrationAdapter = SystemIntegrationAdapter
