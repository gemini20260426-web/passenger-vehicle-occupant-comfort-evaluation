"""
流水线管理器 - 管理数据融合流水线的生命周期
提供流水线的启动、停止、监控功能（事件驱动优化版）
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)

from core.core.multi_source_sync.time_aligner import IntelligentTimeAligner
from core.core.multi_source_sync.data_fusion import AdaptiveDataFusion
from core.core.multi_source_sync.data_source_interfaces import DataSourceSample

class PipelineStatus(Enum):
    """流水线状态"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class PipelineMetrics:
    """流水线性能指标"""
    timestamp: float = 0.0
    total_sources: int = 0
    active_sources: int = 0
    sync_frequency: float = 0.0
    avg_latency: float = 0.0
    sync_quality: float = 0.0
    fusion_quality: float = 0.0
    processed_samples: int = 0
    error_count: int = 0

class DataPipelineManager:
    """数据融合流水线管理器（事件驱动优化版）"""
    
    def __init__(self, config_manager):
        """初始化流水线管理器"""
        self.config_manager = config_manager
        
        self.time_aligner: Optional[IntelligentTimeAligner] = None
        self.data_fusion: Optional[AdaptiveDataFusion] = None
        
        self.status = PipelineStatus.IDLE
        self.status_lock = threading.Lock()
        
        self.data_buffer: Dict[str, deque] = {}
        self.buffer_max_size = 1000
        
        self.is_running = False
        self.pipeline_thread: Optional[threading.Thread] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        
        self.metrics = PipelineMetrics()
        self.metrics_history = deque(maxlen=1000)
        
        self.on_data_received: Optional[Callable] = None
        self.on_data_aligned: Optional[Callable] = None
        self.on_data_fused: Optional[Callable] = None
        self.on_status_changed: Optional[Callable] = None
        self.on_metrics_updated: Optional[Callable] = None
        
        self.data_source_interfaces = {}

        self._pipeline_error_cache = {}
        
        self._data_ready_event = threading.Event()
        self._stop_event = threading.Event()
        
        logger.info("流水线管理器已初始化（事件驱动优化版）")
    
    def _record_pipeline_error_once(self, error_key, error_detail):
        prev = self._pipeline_error_cache.get(error_key, 0)
        if time.time() - prev > 300:
            self._pipeline_error_cache[error_key] = time.time()
            logger.debug(f"流水线错误: {error_detail}")

    def initialize_pipeline(self) -> bool:
        """初始化流水线"""
        try:
            self._update_status(PipelineStatus.INITIALIZING)
            logger.info("正在初始化流水线...")
            
            # 初始化时间对齐器
            self.time_aligner = IntelligentTimeAligner()
            logger.info("时间对齐器已初始化")
            
            # 初始化数据融合器
            self.data_fusion = AdaptiveDataFusion()
            logger.info("数据融合器已初始化")
            
            # 初始化数据缓冲
            self.data_buffer = {}
            for source_id in self.config_manager.data_sources.keys():
                self.data_buffer[source_id] = deque(maxlen=self.buffer_max_size)
            
            self._update_status(PipelineStatus.IDLE)
            logger.info("流水线初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"流水线初始化失败: {e}")
            self._update_status(PipelineStatus.ERROR)
            return False
    
    def start_pipeline(self) -> bool:
        """启动流水线"""
        try:
            if self.status == PipelineStatus.RUNNING:
                logger.warning("流水线已在运行中")
                return True
            
            if self.status != PipelineStatus.RUNNING:
                if not self.initialize_pipeline():
                    return False
            
            self.is_running = True
            
            # 启动流水线线程
            self.pipeline_thread = threading.Thread(
                target=self._pipeline_loop,
                daemon=True,
                name="PipelineThread"
            )
            self.pipeline_thread.start()
            
            # 启动监控线程
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="MonitoringThread"
            )
            self.monitoring_thread.start()
            
            self._update_status(PipelineStatus.RUNNING)
            logger.info("流水线已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动流水线失败: {e}")
            self._update_status(PipelineStatus.ERROR)
            return False
    
    def stop_pipeline(self) -> bool:
        """停止流水线"""
        try:
            if self.status != PipelineStatus.RUNNING:
                logger.warning("流水线未在运行中")
                return True
            
            self._update_status(PipelineStatus.STOPPING)
            self.is_running = False
            
            # 等待线程结束
            if self.pipeline_thread:
                self.pipeline_thread.join(timeout=2.0)
            
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=2.0)
            
            # 关闭组件
            if self.time_aligner:
                self.time_aligner.shutdown()
            
            if self.data_fusion:
                self.data_fusion.shutdown()
            
            self._update_status(PipelineStatus.IDLE)
            logger.info("流水线已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止流水线失败: {e}")
            self._update_status(PipelineStatus.ERROR)
            return False
    
    def pause_pipeline(self) -> bool:
        """暂停流水线"""
        if self.status == PipelineStatus.RUNNING:
            self._update_status(PipelineStatus.PAUSED)
            logger.info("流水线已暂停")
            return True
        return False
    
    def resume_pipeline(self) -> bool:
        """恢复流水线"""
        if self.status == PipelineStatus.PAUSED:
            self._update_status(PipelineStatus.RUNNING)
            logger.info("流水线已恢复")
            return True
        return False
    
    def _pipeline_loop(self):
        """流水线主循环（事件驱动优化版）"""
        logger.info("流水线循环已开始")
        
        sync_interval = 1.0 / self.config_manager.sync_config.sync_frequency
        last_sync_time = time.time()
        
        while self.is_running and not self._stop_event.is_set():
            try:
                if self.status == PipelineStatus.PAUSED:
                    self._data_ready_event.wait(timeout=0.1)
                    self._data_ready_event.clear()
                    continue
                
                self._data_ready_event.wait(timeout=sync_interval)
                self._data_ready_event.clear()
                
                current_time = time.time()
                
                source_data = self._collect_source_data()
                
                if not source_data:
                    continue
                
                if not self.time_aligner:
                    self._record_pipeline_error_once("aligner_none", "时间对齐器未初始化")
                    continue
                
                aligned_data = self.time_aligner.align_data(source_data)
                
                if self.on_data_aligned:
                    self.on_data_aligned(aligned_data)
                
                active_sources = [sid for sid, cfg in self.config_manager.data_sources.items() if cfg.enabled]
                if len(active_sources) <= 1:
                    single_source_id = active_sources[0] if active_sources else None
                    if single_source_id and single_source_id in aligned_data:
                        fused_result = {
                            'timestamp': time.time(),
                            'source_id': single_source_id,
                            'data': aligned_data[single_source_id].get('values', [None])[-1] if aligned_data[single_source_id].get('values') else None,
                            'fusion_method': 'passthrough_single_source',
                            'quality': 1.0,
                            'metadata': {
                                'mode': 'single_source',
                                'source_count': 1,
                                'note': '单数据源模式，跳过融合直接分析'
                            }
                        }
                    else:
                        continue
                elif not self.data_fusion:
                    self._record_pipeline_error_once("fusion_none", "数据融合器未初始化")
                    continue
                else:
                    fused_result = self.data_fusion.fuse_data(aligned_data)
                
                if self.on_data_fused:
                    self.on_data_fused(fused_result)
                
                self._update_metrics(current_time - last_sync_time, len(source_data))
                last_sync_time = current_time
                
            except Exception as e:
                self._record_pipeline_error_once(f"loop_err_{str(e)[:30]}", str(e))
                self.metrics.error_count += 1
                time.sleep(0.05)
        
        logger.info("流水线循环已结束")

    def trigger_data_processing(self):
        """触发数据处理（事件驱动）"""
        self._data_ready_event.set()
    
    def _collect_source_data(self) -> Dict[str, Any]:
        """收集所有数据源数据"""
        source_data = {}
        
        for source_id, source_config in self.config_manager.data_sources.items():
            if not source_config.enabled:
                continue
            
            # 尝试从数据缓冲中获取数据
            if source_id in self.data_buffer and self.data_buffer[source_id]:
                buffer = self.data_buffer[source_id]
                # 取最新的数据
                source_data[source_id] = {
                    'id': source_id,
                    'type': source_config.type,
                    'timestamps': [s.timestamp for s in buffer],
                    'values': [s.data for s in buffer],
                    'quality_score': 0.9
                }
        
        return source_data
    
    def push_data(self, source_id: str, sample: DataSourceSample):
        """推送数据到流水线"""
        if source_id not in self.data_buffer:
            self.data_buffer[source_id] = deque(maxlen=self.buffer_max_size)
        
        self.data_buffer[source_id].append(sample)
        
        if self.on_data_received:
            self.on_data_received(source_id, sample)
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                if self.on_metrics_updated:
                    self.on_metrics_updated(self.metrics)
                
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
    
    def _update_metrics(self, latency: float, source_count: int):
        """更新性能指标"""
        self.metrics.timestamp = time.time()
        self.metrics.total_sources = len(self.config_manager.data_sources)
        self.metrics.active_sources = sum(
            1 for s in self.config_manager.data_sources.values()
            if s.enabled
        )
        self.metrics.avg_latency = latency * 1000  # 转换为毫秒
        self.metrics.sync_frequency = 1.0 / max(latency, 0.001)
        self.metrics.sync_quality = 0.0
        self.metrics.fusion_quality = 0.0
        self.metrics.processed_samples += 1
        
        # 保存到历史
        self.metrics_history.append(self.metrics)
    
    def _update_status(self, new_status: PipelineStatus):
        """更新状态"""
        with self.status_lock:
            old_status = self.status
            self.status = new_status
        
        if old_status != new_status and self.on_status_changed:
            self.on_status_changed(old_status, new_status)
    
    def get_status(self) -> PipelineStatus:
        """获取当前状态"""
        with self.status_lock:
            return self.status
    
    def get_metrics(self) -> PipelineMetrics:
        """获取性能指标"""
        return self.metrics
    
    def get_metrics_history(self, count: int = 100) -> list:
        """获取性能指标历史"""
        return list(self.metrics_history)[-count:]
    
    def register_data_source_interface(self, source_id: str, interface):
        """注册数据源接口"""
        self.data_source_interfaces[source_id] = interface
        logger.info(f"已注册数据源接口: {source_id}")
    
    def unregister_data_source_interface(self, source_id: str):
        """注销数据源接口"""
        if source_id in self.data_source_interfaces:
            del self.data_source_interfaces[source_id]
            logger.info(f"已注销数据源接口: {source_id}")


# 全局流水线管理器实例
_pipeline_manager_instance: Optional[DataPipelineManager] = None

def get_pipeline_manager(config_manager=None) -> DataPipelineManager:
    """获取流水线管理器单例"""
    global _pipeline_manager_instance
    if _pipeline_manager_instance is None:
        if config_manager is None:
            from .config_manager import get_config_manager
            config_manager = get_config_manager()
        _pipeline_manager_instance = DataPipelineManager(config_manager)
    return _pipeline_manager_instance
