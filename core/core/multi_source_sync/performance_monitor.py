#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️ DEPRECATED: 此组件已废弃

此文件保留仅为了向后兼容，将在未来版本中移除。
请使用 core.core.performance_monitor.PerformanceMonitor 作为统一的性能监控器。

实时性能监控器模块
提供系统性能监控、指标收集和性能分析功能

主要功能：
- 实时性能指标监控
- 性能数据收集和存储
- 性能趋势分析
- 性能告警和阈值管理
- 性能报告生成
- 性能优化建议

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"          # 计数器
    GAUGE = "gauge"              # 仪表盘
    HISTOGRAM = "histogram"      # 直方图
    TIMER = "timer"              # 计时器


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"                # 信息
    WARNING = "warning"          # 警告
    CRITICAL = "critical"        # 严重


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str                    # 指标名称
    value: float                 # 指标值
    metric_type: MetricType      # 指标类型
    timestamp: float             # 时间戳
    source: str                  # 数据源
    tags: Dict[str, str] = field(default_factory=dict)  # 标签


@dataclass
class PerformanceAlert:
    """性能告警"""
    metric_name: str             # 指标名称
    alert_level: AlertLevel      # 告警级别
    message: str                 # 告警消息
    threshold: float             # 阈值
    current_value: float         # 当前值
    timestamp: float             # 告警时间戳
    source: str                  # 数据源


@dataclass
class PerformanceSummary:
    """性能摘要"""
    metric_name: str             # 指标名称
    current_value: float         # 当前值
    min_value: float             # 最小值
    max_value: float             # 最大值
    avg_value: float             # 平均值
    count: int                   # 数据点数量
    last_updated: float          # 最后更新时间


class RealTimePerformanceMonitor:
    """实时性能监控器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化性能监控器
        
        Args:
            config: 监控配置
        """
        self.config = config or {}
        self.metrics = defaultdict(lambda: deque(maxlen=1000))  # 每个指标最多保存1000个数据点
        self.alerts = deque(maxlen=100)  # 最多保存100个告警
        self.alert_callbacks = []
        self.monitoring_active = False
        self.monitor_thread = None
        self.alert_thresholds = self._load_alert_thresholds()
        self.monitoring_interval = self.config.get("monitoring_interval", 5.0)  # 监控间隔（秒）
        
        logger.info("实时性能监控器初始化完成")
    
    def _load_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """加载告警阈值配置"""
        default_thresholds = {
            "cpu_usage": {"warning": 85.0, "critical": 95.0},
            "memory_usage": {"warning": 85.0, "critical": 95.0},
            "response_time": {"warning": 100.0, "critical": 500.0},
            "throughput": {"warning": 1000.0, "critical": 5000.0},
            "error_rate": {"warning": 5.0, "critical": 20.0},
            "latency": {"warning": 50.0, "critical": 200.0}
        }
        
        # 合并用户配置
        if self.config and "alert_thresholds" in self.config:
            default_thresholds.update(self.config["alert_thresholds"])
        
        return default_thresholds
    
    def start_monitoring(self):
        """启动性能监控"""
        if self.monitoring_active:
            logger.warning("性能监控已在运行中")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if not self.monitoring_active:
            logger.warning("性能监控未在运行")
            return
        
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("性能监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring_active:
            try:
                # 收集系统性能指标
                self._collect_system_metrics()
                
                # 检查告警条件
                self._check_alerts()
                
                # 等待下次监控
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"性能监控循环中发生错误: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_system_metrics(self):
        """收集系统性能指标"""
        try:
            current_time = time.time()
            
            cpu_usage = self._get_cpu_usage()
            self.record_metric("cpu_usage", cpu_usage, MetricType.GAUGE, "system", current_time)
            
            memory_usage = self._get_memory_usage()
            self.record_metric("memory_usage", memory_usage, MetricType.GAUGE, "system", current_time)
            
            response_time = self._get_response_time()
            self.record_metric("response_time", response_time, MetricType.HISTOGRAM, "system", current_time)
            
            throughput = self._get_throughput()
            self.record_metric("throughput", throughput, MetricType.COUNTER, "system", current_time)
            
            error_rate = self._get_error_rate()
            self.record_metric("error_rate", error_rate, MetricType.GAUGE, "system", current_time)
            
            latency = self._get_latency()
            self.record_metric("latency", latency, MetricType.HISTOGRAM, "system", current_time)
            
        except Exception as e:
            logger.error(f"收集系统性能指标失败: {e}")
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率（真实系统监控）"""
        try:
            import psutil
            return psutil.cpu_percent(interval=None)
        except ImportError:
            logger.warning("psutil模块不可用，无法获取真实CPU使用率")
            return 0.0
        except Exception as e:
            logger.error(f"获取CPU使用率失败: {e}")
            return 0.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率（真实系统监控）"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent
        except ImportError:
            logger.warning("psutil模块不可用，无法获取真实内存使用率")
            return 0.0
        except Exception as e:
            logger.error(f"获取内存使用率失败: {e}")
            return 0.0
    
    def _get_response_time(self) -> float:
        """获取响应时间（真实性能测试）"""
        try:
            # 这里应该实现真实的性能测试逻辑
            # 例如：API调用延迟、数据库查询时间等
            start_time = time.time()
            # 执行一个简单的操作来测量响应时间
            time.sleep(0.001)  # 1ms
            return (time.time() - start_time) * 1000  # 转换为毫秒
        except Exception as e:
            logger.error(f"获取响应时间失败: {e}")
            return 0.0
    
    def _get_throughput(self) -> float:
        """获取吞吐量（真实性能测试）"""
        try:
            # 这里应该实现真实的吞吐量测试逻辑
            # 例如：每秒处理的数据量、请求数等
            # 临时返回一个基于系统状态的估算值
            cpu_usage = self._get_cpu_usage()
            memory_usage = self._get_memory_usage()
            
            # 基于系统资源使用情况估算吞吐量
            if cpu_usage < 50 and memory_usage < 70:
                return 2000.0  # 高吞吐量
            elif cpu_usage < 80 and memory_usage < 85:
                return 1000.0  # 中等吞吐量
            else:
                return 500.0   # 低吞吐量
                
        except Exception as e:
            logger.error(f"获取吞吐量失败: {e}")
            return 0.0
    
    def _get_error_rate(self) -> float:
        """获取错误率（真实错误统计）"""
        try:
            # 这里应该实现真实的错误统计逻辑
            # 例如：从日志文件统计错误数量
            # 临时返回0，表示需要实现真实错误统计
            return 0.0
        except Exception as e:
            logger.error(f"获取错误率失败: {e}")
            return 0.0
    
    def _get_latency(self) -> float:
        """获取延迟（真实网络测试）"""
        try:
            # 这里应该实现真实的网络延迟测试逻辑
            # 例如：ping测试、网络请求延迟等
            # 临时返回0，表示需要实现真实网络测试
            return 0.0
        except Exception as e:
            logger.error(f"获取延迟失败: {e}")
            return 0.0
    
    def record_metric(self, name: str, value: float, metric_type: MetricType, 
                     source: str, timestamp: Optional[float] = None):
        """
        记录性能指标
        
        Args:
            name: 指标名称
            value: 指标值
            metric_type: 指标类型
            source: 数据源
            timestamp: 时间戳（可选）
        """
        try:
            if timestamp is None:
                timestamp = time.time()
            
            metric = PerformanceMetric(
                name=name,
                value=value,
                metric_type=metric_type,
                timestamp=timestamp,
                source=source
            )
            
            self.metrics[name].append(metric)
            
            # 检查是否需要告警
            self._check_metric_alert(metric)
            
        except Exception as e:
            logger.error(f"记录性能指标失败: {e}")
    
    def _check_metric_alert(self, metric: PerformanceMetric):
        """检查指标是否需要告警"""
        try:
            if metric.name not in self.alert_thresholds:
                return
            
            thresholds = self.alert_thresholds[metric.name]
            current_value = metric.value
            
            # 检查严重告警
            if "critical" in thresholds and current_value >= thresholds["critical"]:
                self._create_alert(metric.name, AlertLevel.CRITICAL, 
                                 f"指标 {metric.name} 达到严重阈值: {current_value:.2f} >= {thresholds['critical']:.2f}",
                                 thresholds["critical"], current_value, metric.source)
            
            # 检查警告
            elif "warning" in thresholds and current_value >= thresholds["warning"]:
                self._create_alert(metric.name, AlertLevel.WARNING,
                                 f"指标 {metric.name} 达到警告阈值: {current_value:.2f} >= {thresholds['warning']:.2f}",
                                 thresholds["warning"], current_value, metric.source)
                
        except Exception as e:
            logger.error(f"检查指标告警失败: {e}")
    
    def _create_alert(self, metric_name: str, alert_level: AlertLevel, message: str,
                     threshold: float, current_value: float, source: str):
        """创建告警"""
        try:
            alert = PerformanceAlert(
                metric_name=metric_name,
                alert_level=alert_level,
                message=message,
                threshold=threshold,
                current_value=current_value,
                timestamp=time.time(),
                source=source
            )
            
            self.alerts.append(alert)
            
            # 调用告警回调函数
            self._trigger_alert_callbacks(alert)
            
            logger.warning(f"性能告警: {message}")
            
        except Exception as e:
            logger.error(f"创建告警失败: {e}")
    
    def _trigger_alert_callbacks(self, alert: PerformanceAlert):
        """触发告警回调函数"""
        try:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"告警回调函数执行失败: {e}")
        except Exception as e:
            logger.error(f"触发告警回调函数失败: {e}")
    
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加告警回调函数"""
        if callback not in self.alert_callbacks:
            self.alert_callbacks.append(callback)
            logger.info("告警回调函数已添加")
    
    def remove_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """移除告警回调函数"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
            logger.info("告警回调函数已移除")
    
    def _check_alerts(self):
        """检查告警条件"""
        try:
            # 这里可以添加更复杂的告警逻辑
            # 比如检查指标趋势、组合条件等
            pass
        except Exception as e:
            logger.error(f"检查告警条件失败: {e}")
    
    def get_metric_summary(self, metric_name: str) -> Optional[PerformanceSummary]:
        """获取指标摘要"""
        try:
            if metric_name not in self.metrics:
                return None
            
            metric_data = self.metrics[metric_name]
            if not metric_data:
                return None
            
            values = [metric.value for metric in metric_data]
            
            summary = PerformanceSummary(
                metric_name=metric_name,
                current_value=values[-1] if values else 0.0,
                min_value=min(values) if values else 0.0,
                max_value=max(values) if values else 0.0,
                avg_value=statistics.mean(values) if values else 0.0,
                count=len(values),
                last_updated=metric_data[-1].timestamp if metric_data else 0.0
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"获取指标摘要失败: {e}")
            return None
    
    def get_all_metrics_summary(self) -> Dict[str, PerformanceSummary]:
        """获取所有指标的摘要"""
        try:
            summaries = {}
            
            for metric_name in self.metrics:
                summary = self.get_metric_summary(metric_name)
                if summary:
                    summaries[metric_name] = summary
            
            return summaries
            
        except Exception as e:
            logger.error(f"获取所有指标摘要失败: {e}")
            return {}
    
    def get_recent_alerts(self, count: int = 10) -> List[PerformanceAlert]:
        """获取最近的告警"""
        try:
            return list(self.alerts)[-count:]
        except Exception as e:
            logger.error(f"获取最近告警失败: {e}")
            return []
    
    def clear_metrics(self, metric_name: Optional[str] = None):
        """清除指标数据"""
        try:
            if metric_name is None:
                # 清除所有指标
                self.metrics.clear()
                logger.info("所有指标数据已清除")
            else:
                # 清除指定指标
                if metric_name in self.metrics:
                    self.metrics[metric_name].clear()
                    logger.info(f"指标 {metric_name} 数据已清除")
                    
        except Exception as e:
            logger.error(f"清除指标数据失败: {e}")
    
    def clear_alerts(self):
        """清除告警数据"""
        try:
            self.alerts.clear()
            logger.info("告警数据已清除")
        except Exception as e:
            logger.error(f"清除告警数据失败: {e}")
    
    def export_performance_report(self) -> Dict[str, Any]:
        """导出性能报告"""
        try:
            # 获取所有指标摘要
            metrics_summary = self.get_all_metrics_summary()
            
            # 获取最近告警
            recent_alerts = self.get_recent_alerts(20)
            
            # 计算整体性能评分
            overall_score = self._calculate_overall_performance_score(metrics_summary)
            
            report = {
                "report_timestamp": time.time(),
                "overall_performance_score": overall_score,
                "metrics_summary": {
                    name: {
                        "current_value": summary.current_value,
                        "min_value": summary.min_value,
                        "max_value": summary.max_value,
                        "avg_value": summary.avg_value,
                        "count": summary.count,
                        "last_updated": summary.last_updated
                    }
                    for name, summary in metrics_summary.items()
                },
                "recent_alerts": [
                    {
                        "metric_name": alert.metric_name,
                        "alert_level": alert.alert_level.value,
                        "message": alert.message,
                        "threshold": alert.threshold,
                        "current_value": alert.current_value,
                        "timestamp": alert.timestamp,
                        "source": alert.source
                    }
                    for alert in recent_alerts
                ],
                "alert_thresholds": self.alert_thresholds,
                "monitoring_status": {
                    "active": self.monitoring_active,
                    "interval": self.monitoring_interval
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"导出性能报告失败: {e}")
            return {}
    
    def _calculate_overall_performance_score(self, metrics_summary: Dict[str, PerformanceSummary]) -> float:
        """计算整体性能评分"""
        try:
            if not metrics_summary:
                return 0.0
            
            # 定义各指标的权重
            metric_weights = {
                "cpu_usage": 0.25,
                "memory_usage": 0.20,
                "response_time": 0.20,
                "throughput": 0.15,
                "error_rate": 0.15,
                "latency": 0.05
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for metric_name, summary in metrics_summary.items():
                if metric_name in metric_weights:
                    weight = metric_weights[metric_name]
                    
                    # 根据指标类型计算评分
                    if metric_name in ["cpu_usage", "memory_usage", "error_rate"]:
                        # 这些指标越低越好
                        score = max(0.0, 100.0 - summary.avg_value)
                    else:
                        # 其他指标需要根据阈值判断
                        score = min(100.0, summary.avg_value)
                    
                    total_score += score * weight
                    total_weight += weight
            
            if total_weight == 0:
                return 0.0
            
            overall_score = total_score / total_weight
            return min(overall_score, 100.0)
            
        except Exception as e:
            logger.error(f"计算整体性能评分失败: {e}")
            return 0.0
    
    def set_alert_threshold(self, metric_name: str, alert_level: str, threshold: float):
        """设置告警阈值"""
        try:
            if metric_name not in self.alert_thresholds:
                self.alert_thresholds[metric_name] = {}
            
            self.alert_thresholds[metric_name][alert_level] = threshold
            logger.info(f"指标 {metric_name} 的 {alert_level} 阈值已设置为 {threshold}")
            
        except Exception as e:
            logger.error(f"设置告警阈值失败: {e}")
    
    def get_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """获取告警阈值配置"""
        return self.alert_thresholds.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取所有性能指标
        
        Returns:
            Dict[str, Any]: 包含所有性能指标的字典
        """
        try:
            current_time = time.time()
            metrics_data = {}
            
            # 获取系统性能指标
            metrics_data['system'] = {
                'cpu_usage': self._get_current_cpu_usage(),
                'memory_usage': self._get_current_memory_usage(),
                'disk_usage': self._get_current_disk_usage(),
                'network_io': self._get_current_network_io()
            }
            
            # 获取同步性能指标
            metrics_data['sync'] = {
                'sync_latency': self._get_sync_latency(),
                'data_throughput': self._get_data_throughput(),
                'error_rate': self._get_error_rate(),
                'active_sources': self._get_active_sources_count()
            }
            
            # 获取性能摘要
            metrics_data['summaries'] = self.get_all_metrics_summary()
            
            # 获取最近告警
            metrics_data['recent_alerts'] = [
                {
                    'metric_name': alert.metric_name,
                    'alert_level': alert.alert_level.value,
                    'message': alert.message,
                    'threshold': alert.threshold,
                    'current_value': alert.current_value,
                    'timestamp': alert.timestamp
                }
                for alert in self.get_recent_alerts(5)
            ]
            
            # 添加时间戳
            metrics_data['timestamp'] = current_time
            metrics_data['monitoring_active'] = self.monitoring_active
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return {
                'error': str(e),
                'timestamp': time.time(),
                'monitoring_active': self.monitoring_active
            }
    
    def _get_current_cpu_usage(self) -> float:
        """获取当前CPU使用率"""
        try:
            import psutil
            return psutil.cpu_percent(interval=None)
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    def _get_current_memory_usage(self) -> float:
        """获取当前内存使用率"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    def _get_current_disk_usage(self) -> float:
        """获取当前磁盘使用率"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            return (disk.used / disk.total) * 100
        except ImportError:
            return 0.0
        except Exception:
            return 0.0
    
    def _get_current_network_io(self) -> Dict[str, float]:
        """获取当前网络IO"""
        try:
            import psutil
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except ImportError:
            return {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0}
        except Exception:
            return {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0}
    
    def _get_sync_latency(self) -> float:
        """获取同步延迟"""
        try:
            if 'sync_latency' in self.metrics:
                recent_latencies = list(self.metrics['sync_latency'])[-10:]
                if recent_latencies:
                    return statistics.mean([m.value for m in recent_latencies])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_data_throughput(self) -> float:
        """获取数据吞吐量"""
        try:
            if 'data_throughput' in self.metrics:
                recent_throughput = list(self.metrics['data_throughput'])[-10:]
                if recent_throughput:
                    return statistics.mean([m.value for m in recent_throughput])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_error_rate(self) -> float:
        """获取错误率"""
        try:
            if 'error_count' in self.metrics and 'total_count' in self.metrics:
                error_count = sum(m.value for m in self.metrics['error_count'][-10:])
                total_count = sum(m.value for m in self.metrics['total_count'][-10:])
                if total_count > 0:
                    return (error_count / total_count) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def _get_active_sources_count(self) -> int:
        """获取活跃数据源数量"""
        try:
            if 'active_sources' in self.metrics:
                recent_count = list(self.metrics['active_sources'])[-1:]
                if recent_count:
                    return int(recent_count[0].value)
            return 0
        except Exception:
            return 0
    def _get_sync_latency(self) -> float:
        """获取同步延迟"""
        try:
            if 'sync_latency' in self.metrics:
                recent_latencies = list(self.metrics['sync_latency'])[-10:]
                if recent_latencies:
                    return statistics.mean([m.value for m in recent_latencies])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_data_throughput(self) -> float:
        """获取数据吞吐量"""
        try:
            if 'data_throughput' in self.metrics:
                recent_throughput = list(self.metrics['data_throughput'])[-10:]
                if recent_throughput:
                    return statistics.mean([m.value for m in recent_throughput])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_error_rate(self) -> float:
        """获取错误率"""
        try:
            if 'error_count' in self.metrics and 'total_count' in self.metrics:
                error_count = sum(m.value for m in self.metrics['error_count'][-10:])
                total_count = sum(m.value for m in self.metrics['total_count'][-10:])
                if total_count > 0:
                    return (error_count / total_count) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def _get_active_sources_count(self) -> int:
        """获取活跃数据源数量"""
        try:
            if 'active_sources' in self.metrics:
                recent_count = list(self.metrics['active_sources'])[-1:]
                if recent_count:
                    return int(recent_count[0].value)
            return 0
        except Exception:
            return 0

    def _get_sync_latency(self) -> float:
        """获取同步延迟"""
        try:
            if 'sync_latency' in self.metrics:
                recent_latencies = list(self.metrics['sync_latency'])[-10:]
                if recent_latencies:
                    return statistics.mean([m.value for m in recent_latencies])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_data_throughput(self) -> float:
        """获取数据吞吐量"""
        try:
            if 'data_throughput' in self.metrics:
                recent_throughput = list(self.metrics['data_throughput'])[-10:]
                if recent_throughput:
                    return statistics.mean([m.value for m in recent_throughput])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_error_rate(self) -> float:
        """获取错误率"""
        try:
            if 'error_count' in self.metrics and 'total_count' in self.metrics:
                error_count = sum(m.value for m in self.metrics['error_count'][-10:])
                total_count = sum(m.value for m in self.metrics['total_count'][-10:])
                if total_count > 0:
                    return (error_count / total_count) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def _get_active_sources_count(self) -> int:
        """获取活跃数据源数量"""
        try:
            if 'active_sources' in self.metrics:
                recent_count = list(self.metrics['active_sources'])[-1:]
                if recent_count:
                    return int(recent_count[0].value)
            return 0
        except Exception:
            return 0

    def _get_sync_latency(self) -> float:
        """获取同步延迟"""
        try:
            if 'sync_latency' in self.metrics:
                recent_latencies = list(self.metrics['sync_latency'])[-10:]
                if recent_latencies:
                    return statistics.mean([m.value for m in recent_latencies])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_data_throughput(self) -> float:
        """获取数据吞吐量"""
        try:
            if 'data_throughput' in self.metrics:
                recent_throughput = list(self.metrics['data_throughput'])[-10:]
                if recent_throughput:
                    return statistics.mean([m.value for m in recent_throughput])
            return 0.0
        except Exception:
            return 0.0
    
    def _get_error_rate(self) -> float:
        """获取错误率"""
        try:
            if 'error_count' in self.metrics and 'total_count' in self.metrics:
                error_count = sum(m.value for m in self.metrics['error_count'][-10:])
                total_count = sum(m.value for m in self.metrics['total_count'][-10:])
                if total_count > 0:
                    return (error_count / total_count) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def _get_active_sources_count(self) -> int:
        """获取活跃数据源数量"""
        try:
            if 'active_sources' in self.metrics:
                recent_count = list(self.metrics['active_sources'])[-1:]
                if recent_count:
                    return int(recent_count[0].value)
            return 0
        except Exception:
            return 0

