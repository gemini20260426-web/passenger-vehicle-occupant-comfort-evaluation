#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步数据处理器
提供高性能的异步数据处理能力，支持并发处理和实时优化

主要功能：
- 异步数据流处理
- 多线程并发处理
- 动态性能优化
- 实时性能监控

版本: 1.0
创建时间: 2025年8月16日
"""

import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from queue import Queue, Empty
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """处理性能指标"""
    throughput: float = 0.0          # 吞吐量 (数据点/秒)
    latency: float = 0.0             # 延迟 (秒)
    cpu_usage: float = 0.0           # CPU使用率
    memory_usage: float = 0.0        # 内存使用率
    error_rate: float = 0.0          # 错误率
    timestamp: float = 0.0           # 时间戳


class AsyncDataProcessor:
    """异步数据处理器"""
    
    def __init__(self, max_workers: int = 4, queue_size: int = 1000, auto_start_monitor: bool = False):
        self.max_workers = max_workers
        self.queue_size = queue_size
        
        # 线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 处理队列
        self.processing_queue = Queue(maxsize=queue_size)
        self.result_queue = Queue(maxsize=queue_size)
        
        # 性能监控
        self.metrics = ProcessingMetrics()
        self.metrics_history = []
        self._max_history_size = 100  # 限制历史记录大小
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # 处理任务
        self.processing_tasks = {}
        self.is_processing = False
        
        # 性能优化
        self.optimization_enabled = True
        self.performance_thresholds = {
            'low_throughput': 100,
            'high_latency': 0.1,
            'high_cpu': 95,
            'high_memory': 90
        }
        
        # 启动性能监控
        if auto_start_monitor:
            self.start_performance_monitoring()
        
        logger.info(f"异步数据处理器已初始化，最大工作线程: {max_workers}")
    
    async def process_data_stream(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """异步处理数据流"""
        start_time = time.time()
        
        try:
            # 1. 数据预处理
            preprocessed_data = await self._preprocess_data(data)
            
            # 2. 并行数据源处理
            source_tasks = []
            for source_id, source_data in preprocessed_data.items():
                task = asyncio.create_task(
                    self._process_source_data(source_id, source_data)
                )
                source_tasks.append(task)
            
            # 3. 等待所有任务完成
            source_results = await asyncio.gather(*source_tasks)
            
            # 4. 数据融合
            fused_data = await self._fuse_source_results(source_results)
            
            # 5. 后处理
            final_data = await self._postprocess_data(fused_data)
            
            # 6. 更新性能指标
            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time, len(data))
            
            # 7. 自适应优化
            if self.optimization_enabled:
                await self._adaptively_optimize()
            
            return final_data
            
        except Exception as e:
            logger.error(f"数据处理错误: {e}")
            return {}
    
    def process_data_stream_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """同步处理数据流（用于非异步环境）"""
        start_time = time.time()
        
        try:
            # 1. 数据预处理
            preprocessed_data = self._preprocess_data_sync(data)
            
            # 2. 串行数据源处理
            source_results = []
            for source_id, source_data in preprocessed_data.items():
                result = self._process_source_data_sync(source_id, source_data)
                source_results.append(result)
            
            # 3. 数据融合
            fused_data = self._fuse_source_results_sync(source_results)
            
            # 4. 后处理
            final_data = self._postprocess_data_sync(fused_data)
            
            # 5. 更新性能指标
            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time, len(data))
            
            return final_data
            
        except Exception as e:
            logger.error(f"同步数据处理错误: {e}")
            return {}
    
    def _preprocess_data_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """同步数据预处理"""
        try:
            validated_data = {}
            
            # 检查是否是数据融合的结果格式
            if 'fused_data' in data:
                # 这是数据融合的结果，直接返回
                return data
            
            for source_id, source_data in data.items():
                # 跳过特殊字段（这些不是数据源）
                if source_id in ['quality_metrics', 'algorithm', 'algorithm_used', 'fusion_quality', 'metadata']:
                    continue
                    
                # 验证数据完整性
                if self._validate_source_data(source_data):
                    validated_data[source_id] = source_data
                else:
                    logger.warning(f"数据源 {source_id} 数据不完整，跳过处理")
            
            return validated_data
            
        except Exception as e:
            logger.error(f"同步数据预处理失败: {e}")
            return {}
    
    def _process_source_data_sync(self, source_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """同步处理单个数据源数据"""
        try:
            # 直接执行CPU密集型任务
            result = self._cpu_intensive_processing(source_data)
            return {source_id: result}
            
        except Exception as e:
            logger.error(f"同步处理数据源 {source_id} 失败: {e}")
            return {source_id: None}
    
    def _fuse_source_results_sync(self, source_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """同步融合数据源结果"""
        try:
            fused_data = {}
            
            for result in source_results:
                for source_id, data in result.items():
                    if data is not None:
                        fused_data[source_id] = data
            
            return fused_data
            
        except Exception as e:
            logger.error(f"同步数据融合失败: {e}")
            return {}
    
    def _postprocess_data_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """同步数据后处理"""
        try:
            # 简单的后处理逻辑
            processed_data = {}
            
            for source_id, source_data in data.items():
                if source_data and isinstance(source_data, dict):
                    processed_data[source_id] = {
                        **source_data,
                        'postprocessed': True,
                        'postprocess_timestamp': time.time()
                    }
            
            return processed_data
            
        except Exception as e:
            logger.error(f"同步数据后处理失败: {e}")
            return {}
    
    async def _preprocess_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """数据预处理"""
        try:
            validated_data = {}
            
            # 检查是否是数据融合的结果格式
            if 'fused_data' in data:
                # 这是数据融合的结果，直接返回
                return data
            
            for source_id, source_data in data.items():
                # 跳过特殊字段（这些不是数据源）
                if source_id in ['quality_metrics', 'algorithm', 'algorithm_used', 'fusion_quality', 'metadata']:
                    continue
                    
                # 验证数据完整性
                if self._validate_source_data(source_data):
                    validated_data[source_id] = source_data
                else:
                    logger.warning(f"数据源 {source_id} 数据不完整，跳过处理")
            
            return validated_data
            
        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            return {}
    
    def _validate_source_data(self, source_data: Dict[str, Any]) -> bool:
        """验证数据源数据"""
        try:
            # 检查是否是数据融合后的格式
            if 'fused_data' in source_data:
                # 数据融合后的格式，检查fused_data字段
                fused_data = source_data['fused_data']
                if isinstance(fused_data, dict) and 'values' in fused_data:
                    return True
                else:
                    return False
            
            # 检查是否是原始数据源格式
            if 'timestamp' in source_data and 'value' in source_data:
                # 检查数据类型
                if not isinstance(source_data['timestamp'], (int, float)):
                    return False
                return True
            
            # 检查是否是其他有效格式
            if isinstance(source_data, dict):
                # 如果是字典，检查是否为空
                try:
                    if len(source_data) > 0:
                        return True
                    else:
                        return False
                except (TypeError, AttributeError):
                    # 如果len()失败，检查是否有任何属性
                    return hasattr(source_data, '__dict__') or hasattr(source_data, '__slots__')
            
            # 检查是否是FusionQualityMetrics对象
            if hasattr(source_data, '__class__') and 'FusionQualityMetrics' in str(source_data.__class__):
                # 对于FusionQualityMetrics对象，检查是否有必要的属性
                return hasattr(source_data, 'overall_score') or hasattr(source_data, 'accuracy_score')
            
            # 检查是否是其他类型的对象（包括FusionQualityMetrics等）
            if hasattr(source_data, '__dict__') or hasattr(source_data, '__slots__'):
                return True
            
            # 检查是否是基本数据类型
            if isinstance(source_data, (str, int, float, bool)):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"数据验证过程中出现异常: {e}")
            return False
    
    async def _process_source_data(self, source_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个数据源数据"""
        try:
            # 在线程池中执行CPU密集型任务
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._cpu_intensive_processing, 
                source_data
            )
            
            return {source_id: result}
            
        except Exception as e:
            logger.error(f"处理数据源 {source_id} 失败: {e}")
            return {source_id: None}
    
    def _cpu_intensive_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """CPU密集型数据处理"""
        try:
            # 检查是否是数据融合后的格式
            if 'fused_data' in data:
                # 处理数据融合后的格式
                fused_data = data['fused_data']
                metadata = data.get('metadata', {})
                quality_metrics = metadata.get('quality_metrics', {})
                algorithm = metadata.get('algorithm', 'unknown')
                
                processed_data = {
                    'timestamp': time.time(),
                    'fused_data': fused_data,
                    'quality_metrics': quality_metrics,
                    'algorithm': algorithm,
                    'processed': True,
                    'quality_score': self._calculate_fusion_quality(quality_metrics),
                    'processed_timestamp': time.time()
                }
                
                # 添加数据质量评估
                if isinstance(quality_metrics, dict):
                    processed_data['quality_metrics_processed'] = True
                elif hasattr(quality_metrics, '__class__') and 'FusionQualityMetrics' in str(quality_metrics.__class__):
                    # 处理FusionQualityMetrics对象
                    processed_data['quality_metrics_processed'] = True
                    processed_data['quality_metrics_type'] = 'FusionQualityMetrics'
                
                return processed_data
            
            # 处理原始数据格式
            if 'timestamp' in data and 'value' in data:
                processed_data = {
                    'timestamp': data['timestamp'],
                    'value': data['value'],
                    'processed': True,
                    'quality_score': self._calculate_data_quality(data),
                    'processed_timestamp': time.time()
                }
                return processed_data
            
            # 处理其他格式
            processed_data = {
                'timestamp': time.time(),
                'original_data': data,
                'processed': True,
                'quality_score': 0.5,  # 默认质量分数
                'processed_timestamp': time.time()
            }
            return processed_data
            
        except Exception as e:
            logger.error(f"CPU密集型数据处理失败: {e}")
            return {
                'timestamp': time.time(),
                'error': str(e),
                'processed': False,
                'quality_score': 0.0
            }
    
    def _calculate_data_quality(self, data: Dict[str, Any]) -> float:
        """计算数据质量分数"""
        try:
            # 简化的质量评估算法
            quality_score = 1.0
            
            # 检查时间戳的新鲜度
            current_time = time.time()
            timestamp_age = current_time - data['timestamp']
            
            if timestamp_age > 60:  # 超过1分钟
                quality_score *= 0.8
            elif timestamp_age > 10:  # 超过10秒
                quality_score *= 0.9
            
            # 检查数值的合理性
            value = data['value']
            if isinstance(value, (int, float)):
                if abs(value) > 1e6:  # 数值过大
                    quality_score *= 0.7
                elif abs(value) < 1e-9:  # 数值过小
                    quality_score *= 0.8
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            logger.error(f"计算数据质量失败: {e}")
            return 0.5
    
    def _calculate_fusion_quality(self, quality_metrics: Any) -> float:
        """计算融合质量分数"""
        try:
            # 首先检查是否为None或空
            if quality_metrics is None:
                return 0.8
            
            if isinstance(quality_metrics, dict):
                # 如果是字典格式，提取质量信息
                overall_quality = quality_metrics.get('overall_quality', 0.5)
                algorithm_performance = quality_metrics.get('algorithm_performance', {})
                
                if algorithm_performance and isinstance(algorithm_performance, dict):
                    # 计算平均算法性能
                    performance_scores = []
                    try:
                        for algo, metrics in algorithm_performance.items():
                            if isinstance(metrics, dict) and 'quality' in metrics:
                                performance_scores.append(metrics['quality'])
                    except (AttributeError, TypeError):
                        pass
                    
                    if performance_scores:
                        avg_performance = sum(performance_scores) / len(performance_scores)
                        return (overall_quality + avg_performance) / 2
                
                return overall_quality
            
            elif hasattr(quality_metrics, '__class__') and 'FusionQualityMetrics' in str(quality_metrics.__class__):
                # 处理FusionQualityMetrics对象，使用更安全的方法
                try:
                    # 尝试直接访问overall_quality属性
                    if hasattr(quality_metrics, 'overall_quality'):
                        overall_quality = getattr(quality_metrics, 'overall_quality', 0.8)
                        if isinstance(overall_quality, (int, float)):
                            return float(overall_quality)
                    
                    # 尝试访问其他可能的质量相关属性
                    for attr_name in ['accuracy_score', 'stability_score', 'consistency_score']:
                        if hasattr(quality_metrics, attr_name):
                            score = getattr(quality_metrics, attr_name, 0.8)
                            if isinstance(score, (int, float)):
                                return float(score)
                    
                    # 如果都没有，返回默认值
                    return 0.8
                    
                except Exception:
                    # 如果任何访问失败，返回默认值
                    return 0.8
            
            else:
                # 其他类型，尝试转换为浮点数
                try:
                    return float(quality_metrics)
                except (TypeError, ValueError):
                    return 0.8
            
        except Exception as e:
            logger.warning(f"计算融合质量分数失败: {e}")
            return 0.8
    
    def _is_valid_value(self, value: Any) -> bool:
        """检查数值是否有效"""
        try:
            if value is None:
                return False
            
            if isinstance(value, (int, float)):
                # 检查是否为有限数
                if not np.isfinite(value):
                    return False
                
                # 检查数值范围
                if abs(value) > 1e10:
                    return False
            
            return True
            
        except Exception:
            return False
    
    async def _fuse_source_results(self, source_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """融合数据源结果"""
        try:
            fused_data = {'timestamp': None, 'values': {}, 'metadata': {}}
            
            for result in source_results:
                if result:
                    for source_id, data in result.items():
                        if data and data.get('processed', False):
                            # 设置融合数据的时间戳（使用第一个有效数据源的时间戳）
                            if fused_data['timestamp'] is None:
                                fused_data['timestamp'] = data['timestamp']
                            
                            # 添加数据源值
                            fused_data['values'][source_id] = data
                            
                            # 添加元数据
                            if 'metadata' not in fused_data:
                                fused_data['metadata'] = {}
                            
                            fused_data['metadata'][source_id] = {
                                'quality_score': data.get('quality_score', 0.5),
                                'validation_status': data.get('validation_status', 'unknown'),
                                'processing_time': data.get('processed_timestamp', 0)
                            }
            
            return fused_data
            
        except Exception as e:
            logger.error(f"数据融合失败: {e}")
            return {}
    
    async def _postprocess_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """数据后处理"""
        try:
            if not data:
                return {}
            
            # 添加后处理元数据
            postprocessed_data = data.copy()
            
            # 安全地处理数据统计
            try:
                data_values = data.get('values', {})
                if isinstance(data_values, dict):
                    valid_sources = 0
                    quality_scores = []
                    
                    for v in data_values.values():
                        if isinstance(v, dict):
                            if v.get('validation_status') == 'valid':
                                valid_sources += 1
                            quality_score = v.get('quality_score', 0)
                            if isinstance(quality_score, (int, float)):
                                quality_scores.append(quality_score)
                    
                    avg_quality = np.mean(quality_scores) if quality_scores else 0.0
                    
                    postprocessed_data['postprocessing'] = {
                        'timestamp': time.time(),
                        'total_sources': len(data_values),
                        'valid_sources': valid_sources,
                        'average_quality': avg_quality
                    }
                else:
                    postprocessed_data['postprocessing'] = {
                        'timestamp': time.time(),
                        'total_sources': 0,
                        'valid_sources': 0,
                        'average_quality': 0.0
                    }
            except Exception as summary_error:
                logger.warning(f"创建后处理元数据失败: {summary_error}")
                postprocessed_data['postprocessing'] = {
                    'timestamp': time.time(),
                    'total_sources': 0,
                    'valid_sources': 0,
                    'average_quality': 0.0
                }
            
            return postprocessed_data
            
        except Exception as e:
            logger.error(f"数据后处理失败: {e}")
            return data
    
    def _update_performance_metrics(self, processing_time: float, data_count: int):
        """更新性能指标"""
        try:
            # 计算吞吐量
            if processing_time > 0:
                throughput = data_count / processing_time
            else:
                throughput = 0
            
            # 更新指标
            self.metrics.throughput = throughput
            self.metrics.latency = processing_time
            self.metrics.timestamp = time.time()
            
            # 记录历史
            self.metrics_history.append(self.metrics.__dict__.copy())
            
            # 保持历史记录在合理大小
            if len(self.metrics_history) > 100:
                self.metrics_history.pop(0)
            
        except Exception as e:
            logger.error(f"更新性能指标失败: {e}")
    
    async def _adaptively_optimize(self):
        """自适应优化"""
        try:
            if len(self.metrics_history) < 5:
                return
            
            # 分析最近5次的性能
            recent_metrics = self.metrics_history[-5:]
            avg_throughput = np.mean([m['throughput'] for m in recent_metrics])
            avg_latency = np.mean([m['latency'] for m in recent_metrics])
            
            # 检查是否需要优化
            if avg_throughput < self.performance_thresholds['low_throughput']:
                await self._optimize_for_low_throughput()
            
            if avg_latency > self.performance_thresholds['high_latency']:
                await self._optimize_for_high_latency()
                
        except Exception as e:
            logger.error(f"自适应优化失败: {e}")
    
    async def _optimize_for_low_throughput(self):
        """针对低吞吐量的优化"""
        try:
            current_workers = self.executor._max_workers
            
            if current_workers < 8:  # 最大8个工作线程
                new_workers = min(8, current_workers + 1)
                
                # 创建新的线程池
                new_executor = ThreadPoolExecutor(max_workers=new_workers)
                old_executor = self.executor
                
                # 更新线程池
                self.executor = new_executor
                
                # 关闭旧的线程池
                old_executor.shutdown(wait=False)
                
                logger.info(f"吞吐量优化：增加工作线程 {current_workers} -> {new_workers}")
                
        except Exception as e:
            logger.error(f"吞吐量优化失败: {e}")
    
    async def _optimize_for_high_latency(self):
        """针对高延迟的优化"""
        try:
            # 检查队列大小
            if self.processing_queue.qsize() > self.queue_size * 0.8:
                # 队列接近满，增加队列大小
                new_queue_size = int(self.queue_size * 1.5)
                
                # 创建新队列
                new_processing_queue = Queue(maxsize=new_queue_size)
                new_result_queue = Queue(maxsize=new_queue_size)
                
                # 转移现有数据
                while not self.processing_queue.empty():
                    try:
                        item = self.processing_queue.get_nowait()
                        new_processing_queue.put(item)
                    except Empty:
                        break
                
                while not self.result_queue.empty():
                    try:
                        item = self.result_queue.get_nowait()
                        new_result_queue.put(item)
                    except Empty:
                        break
                
                # 更新队列
                self.processing_queue = new_processing_queue
                self.result_queue = new_result_queue
                self.queue_size = new_queue_size
                
                logger.info(f"延迟优化：增加队列大小 -> {new_queue_size}")
                
        except Exception as e:
            logger.error(f"延迟优化失败: {e}")
    
    def start_performance_monitoring(self):
        """启动性能监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(
                target=self._performance_monitoring_worker,
                daemon=True
            )
            self.monitoring_thread.start()
            logger.info("性能监控已启动")
    
    def _performance_monitoring_worker(self):
        """性能监控工作线程"""
        while self.is_monitoring:
            try:
                # 收集系统性能指标
                self._collect_system_metrics()
                
                # 检查性能阈值
                self._check_performance_thresholds()
                
                # 每15秒更新一次
                time.sleep(15)
                
            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                time.sleep(10)
    
    def _collect_system_metrics(self):
        """收集系统性能指标"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.cpu_usage = cpu_percent
            
            # 内存使用率
            memory_info = psutil.virtual_memory()
            self.metrics.memory_usage = memory_info.percent
            
            # 计算错误率
            if self.metrics_history:
                total_processed = sum(m.get('throughput', 0) for m in self.metrics_history)
                if total_processed > 0:
                    # 简化的错误率计算
                    self.metrics.error_rate = 0.01  # 假设1%错误率
            
        except ImportError:
            logger.warning("psutil未安装，无法收集系统性能指标")
        except Exception as e:
            logger.error(f"收集系统性能指标失败: {e}")
    
    def _check_performance_thresholds(self):
        """检查性能阈值"""
        try:
            current_time = time.time()
            if not hasattr(self, '_last_perf_alert_time'):
                self._last_perf_alert_time = {}

            if self.metrics.cpu_usage > self.performance_thresholds['high_cpu']:
                last = self._last_perf_alert_time.get('cpu', 0)
                if current_time - last > 60:
                    self._last_perf_alert_time['cpu'] = current_time
                    logger.warning(f"CPU使用率过高: {self.metrics.cpu_usage}%")

            if self.metrics.memory_usage > 85:
                last = self._last_perf_alert_time.get('memory', 0)
                if current_time - last > 60:
                    self._last_perf_alert_time['memory'] = current_time
                    logger.warning(f"内存使用率过高: {self.metrics.memory_usage}%")
                    self._optimize_memory_usage()
            elif self.metrics.memory_usage > 75:
                logger.debug(f"内存使用率较高: {self.metrics.memory_usage}%")
                self._light_memory_optimization()

            if self.metrics.throughput > 0 and self.metrics.throughput < self.performance_thresholds['low_throughput']:
                last = self._last_perf_alert_time.get('throughput', 0)
                if current_time - last > 60:
                    self._last_perf_alert_time['throughput'] = current_time
                    logger.warning(f"吞吐量过低: {self.metrics.throughput:.2f} 数据点/秒")

            if self.metrics.latency > self.performance_thresholds['high_latency']:
                last = self._last_perf_alert_time.get('latency', 0)
                if current_time - last > 60:
                    self._last_perf_alert_time['latency'] = current_time
                    logger.warning(f"延迟过高: {self.metrics.latency:.3f} 秒")

        except Exception as e:
            logger.error(f"性能阈值检查失败: {e}")
    
    def _optimize_memory_usage(self):
        """优化内存使用（带冷却）"""
        try:
            current_time = time.time()
            if not hasattr(self, '_last_memory_optimize_time'):
                self._last_memory_optimize_time = 0
            if current_time - self._last_memory_optimize_time < 60:
                return
            self._last_memory_optimize_time = current_time

            logger.info("🧹 开始执行内存优化...")

            if len(self.metrics_history) > 100:
                self.metrics_history = self.metrics_history[-100:]
                logger.info("🧹 清理性能历史，保留最近100条记录")

            import gc
            collected = gc.collect()
            logger.info(f"🧹 垃圾回收完成: 清理了 {collected} 个对象")

            try:
                import psutil
                memory_info = psutil.virtual_memory()
                logger.info(f"🧹 内存优化后使用率: {memory_info.percent:.1f}%")
            except:
                pass

        except Exception as e:
            logger.error(f"内存优化失败: {e}")

    def _light_memory_optimization(self):
        """轻度内存优化"""
        try:
            logger.debug("🧹 执行轻度内存优化...")
            
            # 清理过期的性能历史
            if len(self.metrics_history) > 200:
                self.metrics_history = self.metrics_history[-200:]
                logger.debug("🧹 轻度清理性能历史，保留最近200条记录")
            
            # 轻度垃圾回收
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 轻度垃圾回收完成: 清理了 {collected} 个对象")
                
        except Exception as e:
            logger.debug(f"轻度内存优化失败: {e}")
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_performance_history(self, count: int = None) -> List[Dict[str, Any]]:
        """获取性能历史"""
        if count is None:
            return self.metrics_history.copy()
        else:
            return self.metrics_history[-count:]
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            'is_processing': self.is_processing,
            'queue_size': self.processing_queue.qsize(),
            'max_queue_size': self.queue_size,
            'active_workers': self.executor._max_workers,
            'max_workers': self.max_workers,
            'is_monitoring': self.is_monitoring
        }
    
    def set_optimization_enabled(self, enabled: bool):
        """设置是否启用优化"""
        self.optimization_enabled = enabled
        logger.info(f"性能优化已{'启用' if enabled else '禁用'}")
    
    def set_performance_thresholds(self, thresholds: Dict[str, float]):
        """设置性能阈值"""
        self.performance_thresholds.update(thresholds)
        logger.info(f"性能阈值已更新: {thresholds}")
    
    def shutdown(self):
        """关闭异步数据处理器"""
        try:
            # 停止性能监控
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            # 清空队列
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except Empty:
                    break
            
            while not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except Empty:
                    break
            
            logger.info("异步数据处理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭异步数据处理器失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        # 创建异步数据处理器
        processor = AsyncDataProcessor(max_workers=4)
        
        # 模拟数据
        test_data = {
            'imu_source': {
                'timestamp': time.time(),
                'value': 1.23,
                'type': 'imu'
            },
            'cnap_source': {
                'timestamp': time.time(),
                'value': 120.5,
                'type': 'cnap'
            }
        }
        
        # 处理数据
        result = await processor.process_data_stream(test_data)
        logger.info(f"处理结果: {result}")
        
        # 获取性能指标
        metrics = processor.get_performance_metrics()
        logger.info(f"性能指标: {metrics}")
        
        # 获取处理状态
        status = processor.get_processing_status()
        logger.info(f"处理状态: {status}")
        
        # 关闭处理器
        processor.shutdown()
    
    # 运行示例
    asyncio.run(main())


    def _light_memory_optimization(self):
        """轻度内存优化"""
        try:
            logger.debug("🧹 执行轻度内存优化...")
            
            # 清理过期的性能历史
            if len(self.metrics_history) > 200:
                self.metrics_history = self.metrics_history[-200:]
                logger.debug("🧹 轻度清理性能历史，保留最近200条记录")
            
            # 轻度垃圾回收
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 轻度垃圾回收完成: 清理了 {collected} 个对象")
                
        except Exception as e:
            logger.debug(f"轻度内存优化失败: {e}")
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_performance_history(self, count: int = None) -> List[Dict[str, Any]]:
        """获取性能历史"""
        if count is None:
            return self.metrics_history.copy()
        else:
            return self.metrics_history[-count:]
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            'is_processing': self.is_processing,
            'queue_size': self.processing_queue.qsize(),
            'max_queue_size': self.queue_size,
            'active_workers': self.executor._max_workers,
            'max_workers': self.max_workers,
            'is_monitoring': self.is_monitoring
        }
    
    def set_optimization_enabled(self, enabled: bool):
        """设置是否启用优化"""
        self.optimization_enabled = enabled
        logger.info(f"性能优化已{'启用' if enabled else '禁用'}")
    
    def set_performance_thresholds(self, thresholds: Dict[str, float]):
        """设置性能阈值"""
        self.performance_thresholds.update(thresholds)
        logger.info(f"性能阈值已更新: {thresholds}")
    
    def shutdown(self):
        """关闭异步数据处理器"""
        try:
            # 停止性能监控
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            # 清空队列
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except Empty:
                    break
            
            while not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except Empty:
                    break
            
            logger.info("异步数据处理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭异步数据处理器失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        # 创建异步数据处理器
        processor = AsyncDataProcessor(max_workers=4)
        
        # 模拟数据
        test_data = {
            'imu_source': {
                'timestamp': time.time(),
                'value': 1.23,
                'type': 'imu'
            },
            'cnap_source': {
                'timestamp': time.time(),
                'value': 120.5,
                'type': 'cnap'
            }
        }
        
        # 处理数据
        result = await processor.process_data_stream(test_data)
        logger.info(f"处理结果: {result}")
        
        # 获取性能指标
        metrics = processor.get_performance_metrics()
        logger.info(f"性能指标: {metrics}")
        
        # 获取处理状态
        status = processor.get_processing_status()
        logger.info(f"处理状态: {status}")
        
        # 关闭处理器
        processor.shutdown()
    
    # 运行示例
    asyncio.run(main())


    def _light_memory_optimization(self):
        """轻度内存优化"""
        try:
            logger.debug("🧹 执行轻度内存优化...")
            
            # 清理过期的性能历史
            if len(self.metrics_history) > 200:
                self.metrics_history = self.metrics_history[-200:]
                logger.debug("🧹 轻度清理性能历史，保留最近200条记录")
            
            # 轻度垃圾回收
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 轻度垃圾回收完成: 清理了 {collected} 个对象")
                
        except Exception as e:
            logger.debug(f"轻度内存优化失败: {e}")
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_performance_history(self, count: int = None) -> List[Dict[str, Any]]:
        """获取性能历史"""
        if count is None:
            return self.metrics_history.copy()
        else:
            return self.metrics_history[-count:]
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            'is_processing': self.is_processing,
            'queue_size': self.processing_queue.qsize(),
            'max_queue_size': self.queue_size,
            'active_workers': self.executor._max_workers,
            'max_workers': self.max_workers,
            'is_monitoring': self.is_monitoring
        }
    
    def set_optimization_enabled(self, enabled: bool):
        """设置是否启用优化"""
        self.optimization_enabled = enabled
        logger.info(f"性能优化已{'启用' if enabled else '禁用'}")
    
    def set_performance_thresholds(self, thresholds: Dict[str, float]):
        """设置性能阈值"""
        self.performance_thresholds.update(thresholds)
        logger.info(f"性能阈值已更新: {thresholds}")
    
    def shutdown(self):
        """关闭异步数据处理器"""
        try:
            # 停止性能监控
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            # 清空队列
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except Empty:
                    break
            
            while not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except Empty:
                    break
            
            logger.info("异步数据处理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭异步数据处理器失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        # 创建异步数据处理器
        processor = AsyncDataProcessor(max_workers=4)
        
        # 模拟数据
        test_data = {
            'imu_source': {
                'timestamp': time.time(),
                'value': 1.23,
                'type': 'imu'
            },
            'cnap_source': {
                'timestamp': time.time(),
                'value': 120.5,
                'type': 'cnap'
            }
        }
        
        # 处理数据
        result = await processor.process_data_stream(test_data)
        logger.info(f"处理结果: {result}")
        
        # 获取性能指标
        metrics = processor.get_performance_metrics()
        logger.info(f"性能指标: {metrics}")
        
        # 获取处理状态
        status = processor.get_processing_status()
        logger.info(f"处理状态: {status}")
        
        # 关闭处理器
        processor.shutdown()
    
    # 运行示例
    asyncio.run(main())


    def _light_memory_optimization(self):
        """轻度内存优化"""
        try:
            logger.debug("🧹 执行轻度内存优化...")
            
            # 清理过期的性能历史
            if len(self.metrics_history) > 200:
                self.metrics_history = self.metrics_history[-200:]
                logger.debug("🧹 轻度清理性能历史，保留最近200条记录")
            
            # 轻度垃圾回收
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 轻度垃圾回收完成: 清理了 {collected} 个对象")
                
        except Exception as e:
            logger.debug(f"轻度内存优化失败: {e}")
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_performance_history(self, count: int = None) -> List[Dict[str, Any]]:
        """获取性能历史"""
        if count is None:
            return self.metrics_history.copy()
        else:
            return self.metrics_history[-count:]
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            'is_processing': self.is_processing,
            'queue_size': self.processing_queue.qsize(),
            'max_queue_size': self.queue_size,
            'active_workers': self.executor._max_workers,
            'max_workers': self.max_workers,
            'is_monitoring': self.is_monitoring
        }
    
    def set_optimization_enabled(self, enabled: bool):
        """设置是否启用优化"""
        self.optimization_enabled = enabled
        logger.info(f"性能优化已{'启用' if enabled else '禁用'}")
    
    def set_performance_thresholds(self, thresholds: Dict[str, float]):
        """设置性能阈值"""
        self.performance_thresholds.update(thresholds)
        logger.info(f"性能阈值已更新: {thresholds}")
    
    def shutdown(self):
        """关闭异步数据处理器"""
        try:
            # 停止性能监控
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            # 清空队列
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except Empty:
                    break
            
            while not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except Empty:
                    break
            
            logger.info("异步数据处理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭异步数据处理器失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        # 创建异步数据处理器
        processor = AsyncDataProcessor(max_workers=4)
        
        # 模拟数据
        test_data = {
            'imu_source': {
                'timestamp': time.time(),
                'value': 1.23,
                'type': 'imu'
            },
            'cnap_source': {
                'timestamp': time.time(),
                'value': 120.5,
                'type': 'cnap'
            }
        }
        
        # 处理数据
        result = await processor.process_data_stream(test_data)
        logger.info(f"处理结果: {result}")
        
        # 获取性能指标
        metrics = processor.get_performance_metrics()
        logger.info(f"性能指标: {metrics}")
        
        # 获取处理状态
        status = processor.get_processing_status()
        logger.info(f"处理状态: {status}")
        
        # 关闭处理器
        processor.shutdown()
    
    # 运行示例
    asyncio.run(main())
