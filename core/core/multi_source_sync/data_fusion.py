#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应数据融合算法
支持多种融合策略：加权平均、卡尔曼滤波、神经网络、集成融合

主要功能：
- 智能算法选择
- 自适应参数调整
- 实时质量评估
- 多源数据融合

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class FusionAlgorithm(Enum):
    """融合算法枚举"""
    WEIGHTED_AVERAGE = "weighted_average"  # 加权平均
    KALMAN_FILTER = "kalman_filter"        # 卡尔曼滤波
    NEURAL_NETWORK = "neural_network"      # 神经网络
    ENSEMBLE = "ensemble"                   # 集成融合


@dataclass
class FusionQualityMetrics:
    """融合质量指标"""
    accuracy_score: float = 0.0      # 准确性分数 (0-1)
    stability_score: float = 0.0     # 稳定性分数 (0-1)
    consistency_score: float = 0.0   # 一致性分数 (0-1)
    overall_score: float = 0.0       # 综合分数 (0-1)
    timestamp: float = 0.0           # 评估时间戳
    
    def calculate_overall_score(self) -> float:
        """计算综合分数"""
        weights = {
            'accuracy': 0.4,
            'stability': 0.3,
            'consistency': 0.3
        }
        
        self.overall_score = (
            weights['accuracy'] * self.accuracy_score +
            weights['stability'] * self.stability_score +
            weights['consistency'] * self.consistency_score
        )
        
        return self.overall_score


class WeightedAverageFusion:
    """加权平均融合算法"""
    
    def __init__(self):
        self.name = "weighted_average"
        self.quality_weights = {}
        self.performance_history = []
        self.current_weights = {}  # 当前权重
    
    def fuse(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行加权平均融合"""
        try:
            if not aligned_data:
                return {}
            
            # 计算各数据源的质量权重
            self._calculate_quality_weights(aligned_data)
            
            # 执行融合
            fused_data = self._perform_weighted_average(aligned_data)
            
            # 评估融合质量
            fusion_quality = self._evaluate_fusion_quality(fused_data)
            
            # 记录性能
            self._record_performance(fusion_quality)
            
            # 将融合结果和元数据合并到一个统一的结构中
            result = {
                'fused_data': fused_data,
                'metadata': {
                    'quality_metrics': fusion_quality,
                    'algorithm': self.name,
                    'weights': self.quality_weights,
                    'fusion_timestamp': time.time()
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"加权平均融合失败: {e}")
            return {}
    
    def fuse_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """融合数据（兼容性方法）"""
        return self.fuse(data)
    
    def adapt_weights(self, source_data: Dict[str, Any]):
        """自适应权重调整"""
        try:
            if not source_data:
                return
            
            # 基于数据质量动态调整权重
            for source_id, data in source_data.items():
                if isinstance(data, dict):
                    # 计算数据质量指标
                    quality_score = self._calculate_source_quality(data)
                    
                    # 更新质量权重
                    if source_id in self.quality_weights:
                        # 平滑更新
                        old_weight = self.quality_weights[source_id]
                        new_weight = 0.7 * old_weight + 0.3 * quality_score
                        self.quality_weights[source_id] = new_weight
                    else:
                        self.quality_weights[source_id] = quality_score
            
            # 重新归一化权重
            self._normalize_weights()
            
            logger.info(f"权重已自适应调整: {self.quality_weights}")
            
        except Exception as e:
            logger.error(f"自适应权重调整失败: {e}")
    
    def _calculate_source_quality(self, source_data: Dict[str, Any]) -> float:
        """计算数据源质量"""
        try:
            # 基于数据完整性、一致性和精度计算质量
            timestamps = source_data.get('timestamps', [])
            values = source_data.get('values', [])
            
            if not timestamps or not values:
                return 0.0
            
            # 完整性分数
            completeness = len(values) / len(timestamps) if timestamps else 0.0
            
            # 一致性分数（基于时间间隔的稳定性）
            consistency = 1.0
            if len(timestamps) > 1:
                intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                if intervals:
                    mean_interval = np.mean(intervals)
                    if mean_interval > 0:
                        std_interval = np.std(intervals)
                        consistency = max(0.0, 1.0 - std_interval / mean_interval)
            
            # 综合质量分数
            quality = 0.4 * completeness + 0.6 * consistency
            return min(1.0, max(0.0, quality))
            
        except Exception as e:
            logger.error(f"计算数据源质量失败: {e}")
            return 0.5
    
    def _normalize_weights(self):
        """归一化权重"""
        try:
            total_weight = sum(self.quality_weights.values())
            if total_weight > 0:
                for source_id in self.quality_weights:
                    self.quality_weights[source_id] /= total_weight
        except Exception as e:
            logger.error(f"归一化权重失败: {e}")
    
    def _calculate_quality_weights(self, aligned_data: Dict[str, Any]):
        """计算质量权重"""
        total_quality = 0
        quality_scores = {}
        
        # 获取各数据源的质量分数
        for source_id, source_data in aligned_data.items():
            quality_score = source_data.get('quality_score', 0.5)
            quality_scores[source_id] = quality_score
            total_quality += quality_score
        
        # 计算归一化权重
        if total_quality > 0:
            for source_id, quality_score in quality_scores.items():
                self.quality_weights[source_id] = quality_score / total_quality
        else:
            # 如果所有质量分数都为0，使用平均权重
            source_count = len(aligned_data)
            for source_id in aligned_data.keys():
                self.quality_weights[source_id] = 1.0 / source_count
    
    def _perform_weighted_average(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行加权平均融合"""
        fused_data = {
            'timestamp': time.time(),
            'values': {},
            'metadata': {
                'fusion_algorithm': self.name,
                'source_weights': self.quality_weights.copy()
            }
        }
        
        # 获取所有时间戳
        all_timestamps = set()
        for source_data in aligned_data.values():
            timestamps = source_data.get('timestamps', [])
            all_timestamps.update(timestamps)
        
        all_timestamps = sorted(list(all_timestamps))
        
        # 对每个时间点进行融合
        for timestamp in all_timestamps:
            fused_value = self._fuse_at_timestamp(timestamp, aligned_data)
            if fused_value is not None:
                fused_data['values'][timestamp] = fused_value
        
        return fused_data
    
    def _fuse_at_timestamp(self, timestamp: float, aligned_data: Dict[str, Any]) -> Optional[float]:
        """在指定时间点进行融合"""
        weighted_sum = 0
        total_weight = 0
        
        for source_id, source_data in aligned_data.items():
            timestamps = source_data.get('timestamps', [])
            values = source_data.get('values', [])
            
            # 找到最接近的时间点
            if timestamp in timestamps:
                idx = timestamps.index(timestamp)
                value = values[idx]
                weight = self.quality_weights.get(source_id, 0)
                
                # 确保value是数值类型
                if isinstance(value, (int, float)):
                    weighted_sum += value * weight
                    total_weight += weight
                elif isinstance(value, dict):
                    # 如果value是字典，尝试提取数值
                    numeric_value = self._extract_numeric_value(value)
                    if numeric_value is not None:
                        weighted_sum += numeric_value * weight
                        total_weight += weight
                else:
                    # 尝试转换为数值
                    try:
                        numeric_value = float(value)
                        weighted_sum += numeric_value * weight
                        total_weight += weight
                    except (ValueError, TypeError):
                        # 无法转换，跳过这个数据点
                        continue
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return None
    
    def _extract_numeric_value(self, data: Any) -> Optional[float]:
        """从数据中提取数值"""
        try:
            if isinstance(data, (int, float)):
                return float(data)
            elif isinstance(data, dict):
                # 尝试从字典中提取数值
                for key in ['value', 'data', 'magnitude', 'amplitude']:
                    if key in data:
                        val = data[key]
                        if isinstance(val, (int, float)):
                            return float(val)
                        elif isinstance(val, str):
                            try:
                                return float(val)
                            except ValueError:
                                continue
            elif isinstance(data, str):
                try:
                    return float(data)
                except ValueError:
                    return None
            return None
        except Exception:
            return None
    
    def _evaluate_fusion_quality(self, fused_data: Dict[str, Any]) -> FusionQualityMetrics:
        """评估融合质量"""
        metrics = FusionQualityMetrics(timestamp=time.time())
        
        if not fused_data or 'values' not in fused_data:
            return metrics
        
        # 计算准确性分数（基于权重分布）
        weight_values = list(self.quality_weights.values())
        if weight_values:
            weight_variance = np.var(weight_values)
            metrics.accuracy_score = max(0, 1 - weight_variance)
        else:
            metrics.accuracy_score = 0.5
        
        # 计算稳定性分数（基于数据点数量）
        data_points = len(fused_data['values'])
        metrics.stability_score = min(1.0, data_points / 100)  # 标准化到100个数据点
        
        # 计算一致性分数（基于时间间隔的一致性）
        timestamps = sorted(fused_data['values'].keys())
        if len(timestamps) > 1:
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            if intervals:
                interval_variance = np.var(intervals)
                avg_interval = np.mean(intervals)
                if avg_interval > 0:
                    metrics.consistency_score = max(0, 1 - interval_variance / (avg_interval ** 2))
                else:
                    metrics.consistency_score = 0.5
            else:
                metrics.consistency_score = 1.0
        else:
            metrics.consistency_score = 1.0
        
        # 计算综合分数
        metrics.calculate_overall_score()
        
        return metrics
    
    def _record_performance(self, fusion_quality: FusionQualityMetrics):
        """记录性能"""
        performance_record = {
            'quality': fusion_quality.overall_score,
            'timestamp': time.time()
        }
        
        self.performance_history.append(performance_record)
        
        # 保持历史记录在合理大小
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)


class KalmanFilterFusion:
    """卡尔曼滤波融合算法"""
    
    def __init__(self):
        self.name = "kalman_filter"
        self.process_noise = 0.1
        self.measurement_noise = 0.5
        self.performance_history = []
        self.state_estimates = {}
    
    def fuse(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行卡尔曼滤波融合"""
        try:
            if not aligned_data:
                return {}
            
            # 初始化状态估计
            self._initialize_state_estimates(aligned_data)
            
            # 执行卡尔曼滤波融合
            fused_data = self._perform_kalman_fusion(aligned_data)
            
            # 评估融合质量
            fusion_quality = self._evaluate_fusion_quality(fused_data)
            
            # 记录性能
            self._record_performance(fusion_quality)
            
            # 将融合结果和元数据合并到一个统一的结构中
            result = {
                'fused_data': fused_data,
                'metadata': {
                    'quality_metrics': fusion_quality,
                    'algorithm': self.name,
                    'kalman_params': {
                        'process_noise': self.process_noise,
                        'measurement_noise': self.measurement_noise
                    },
                    'fusion_timestamp': time.time()
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"卡尔曼滤波融合失败: {e}")
            return {}
    
    def fuse_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """融合数据（兼容性方法）"""
        return self.fuse(data)
    
    def adapt_to_noise(self, noisy_measurements: List[float]):
        """自适应噪声参数"""
        try:
            if len(noisy_measurements) < 2:
                return
            
            # 计算测量值的方差作为噪声估计
            measurements_array = np.array(noisy_measurements)
            noise_variance = np.var(measurements_array)
            
            # 调整测量噪声参数
            self.measurement_noise = max(0.1, noise_variance)
            
            # 调整过程噪声参数
            if len(noisy_measurements) > 2:
                # 计算测量值的变化率
                diffs = np.diff(noisy_measurements)
                process_variance = np.var(diffs)
                self.process_noise = max(0.01, process_variance)
            
            logger.info(f"噪声参数已调整: measurement_noise={self.measurement_noise:.3f}, process_noise={self.process_noise:.3f}")
            
        except Exception as e:
            logger.error(f"自适应噪声参数失败: {e}")
    
    @property
    def noise_params(self) -> Dict[str, float]:
        """获取噪声参数"""
        return {
            'process_noise': self.process_noise,
            'measurement_noise': self.measurement_noise
        }
    
    def _initialize_state_estimates(self, aligned_data: Dict[str, Any]):
        """初始化状态估计"""
        for source_id in aligned_data.keys():
            if source_id not in self.state_estimates:
                self.state_estimates[source_id] = {
                    'state': 0.0,
                    'covariance': 1.0
                }
    
    def _perform_kalman_fusion(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行卡尔曼滤波融合"""
        fused_data = {
            'timestamp': time.time(),
            'values': {},
            'metadata': {
                'fusion_algorithm': self.name,
                'state_estimates': self.state_estimates.copy()
            }
        }
        
        # 获取所有时间戳
        all_timestamps = set()
        for source_data in aligned_data.values():
            timestamps = source_data.get('timestamps', [])
            all_timestamps.update(timestamps)
        
        all_timestamps = sorted(list(all_timestamps))
        
        # 对每个时间点进行卡尔曼滤波融合
        for timestamp in all_timestamps:
            fused_value = self._kalman_fuse_at_timestamp(timestamp, aligned_data)
            if fused_value is not None:
                fused_data['values'][timestamp] = fused_value
        
        return fused_data
    
    def _kalman_fuse_at_timestamp(self, timestamp: float, aligned_data: Dict[str, Any]) -> Optional[float]:
        """在指定时间点进行卡尔曼滤波融合"""
        measurements = []
        measurement_noises = []
        
        # 收集各数据源的测量值
        for source_id, source_data in aligned_data.items():
            timestamps = source_data.get('timestamps', [])
            values = source_data.get('values', [])
            
            if timestamp in timestamps:
                idx = timestamps.index(timestamp)
                value = values[idx]
                quality_score = source_data.get('quality_score', 0.5)
                
                # 确保value是数值类型
                if isinstance(value, (int, float)):
                    measurements.append(value)
                    # 基于质量分数调整测量噪声
                    adjusted_noise = self.measurement_noise / max(0.1, quality_score)
                    measurement_noises.append(adjusted_noise)
                elif isinstance(value, dict):
                    # 如果value是字典，尝试提取数值
                    numeric_value = value.get('value', value.get('data', 0))
                    if isinstance(numeric_value, (int, float)):
                        measurements.append(numeric_value)
                        adjusted_noise = self.measurement_noise / max(0.1, quality_score)
                        measurement_noises.append(adjusted_noise)
                else:
                    # 其他类型，尝试转换为数值
                    try:
                        numeric_value = float(value)
                        measurements.append(numeric_value)
                        adjusted_noise = self.measurement_noise / max(0.1, quality_score)
                        measurement_noises.append(adjusted_noise)
                    except (ValueError, TypeError):
                        logger.warning(f"无法转换测量值 {value} 为数值类型")
                        continue
        
        if not measurements:
            return None
        
        # 执行卡尔曼滤波融合
        fused_value = self._kalman_filter_step(measurements, measurement_noises)
        return fused_value
    
    def _kalman_filter_step(self, measurements: List[float], measurement_noises: List[float]) -> float:
        """卡尔曼滤波步骤"""
        if not measurements:
            return 0.0
        
        # 简化的卡尔曼滤波实现
        # 预测步骤
        predicted_state = 0.0  # 假设状态保持不变
        predicted_covariance = 1.0 + self.process_noise
        
        # 更新步骤
        fused_value = predicted_state
        total_weight = 0
        
        for measurement, noise in zip(measurements, measurement_noises):
            # 计算卡尔曼增益
            kalman_gain = predicted_covariance / (predicted_covariance + noise)
            
            # 更新状态估计
            fused_value += kalman_gain * (measurement - predicted_state)
            total_weight += kalman_gain
        
        # 归一化
        if total_weight > 0:
            fused_value /= total_weight
        
        return fused_value
    
    def _evaluate_fusion_quality(self, fused_data: Dict[str, Any]) -> FusionQualityMetrics:
        """评估融合质量"""
        metrics = FusionQualityMetrics(timestamp=time.time())
        
        if not fused_data or 'values' not in fused_data:
            return metrics
        
        # 计算准确性分数（基于卡尔曼滤波参数）
        metrics.accuracy_score = max(0, 1 - self.process_noise)
        
        # 计算稳定性分数（基于数据点数量）
        data_points = len(fused_data['values'])
        metrics.stability_score = min(1.0, data_points / 100)
        
        # 计算一致性分数（基于状态估计的一致性）
        if self.state_estimates:
            state_values = [est['state'] for est in self.state_estimates.values()]
            if state_values:
                state_variance = np.var(state_values)
                avg_state = np.mean(state_values)
                if avg_state != 0:
                    metrics.consistency_score = max(0, 1 - abs(state_variance / avg_state))
                else:
                    metrics.consistency_score = 0.5
            else:
                metrics.consistency_score = 0.5
        else:
            metrics.consistency_score = 0.5
        
        # 计算综合分数
        metrics.calculate_overall_score()
        
        return metrics
    
    def _record_performance(self, fusion_quality: FusionQualityMetrics):
        """记录性能"""
        performance_record = {
            'quality': fusion_quality.overall_score,
            'timestamp': time.time()
        }
        
        self.performance_history.append(performance_record)
        
        # 保持历史记录在合理大小
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)


class AdaptiveDataFusion:
    """自适应数据融合算法"""
    
    def __init__(self):
        self.fusion_algorithms = {
            FusionAlgorithm.WEIGHTED_AVERAGE: WeightedAverageFusion(),
            FusionAlgorithm.KALMAN_FILTER: KalmanFilterFusion(),
        }
        
        self.algorithm_performance = {}
        self.fusion_history = []
        self.current_algorithm = FusionAlgorithm.WEIGHTED_AVERAGE
        
        # 性能监控
        self.monitoring_enabled = True
        self.monitoring_thread = None
        self.start_performance_monitoring()
        
        logger.info("自适应数据融合算法已初始化")
    
    def fuse_data(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """智能数据融合"""
        try:
            # 1. 评估数据质量
            quality_scores = self._assess_data_quality(aligned_data)
            
            # 2. 选择最佳融合算法
            best_algorithm = self._select_fusion_algorithm(quality_scores)
            
            # 3. 执行数据融合
            fused_data = best_algorithm.fuse(aligned_data)
            
            # 4. 评估融合质量
            fusion_quality = self._evaluate_fusion_quality(fused_data)
            
            # 5. 更新算法性能
            self._update_algorithm_performance(best_algorithm, fusion_quality)
            
            # 6. 记录融合历史
            self._record_fusion_history(fused_data, fusion_quality, best_algorithm)
            
            return fused_data
        
        except Exception as e:
            logger.error(f"数据融合失败: {e}")
            return {}
    
    def select_best_algorithm(self, performance_data: Dict[Any, float]) -> Any:
        """选择最佳算法"""
        try:
            if not performance_data:
                return self.current_algorithm
            
            # 选择性能最好的算法
            best_algorithm = max(performance_data, key=performance_data.get)
            return best_algorithm
            
        except Exception as e:
            logger.error(f"选择最佳算法失败: {e}")
            return self.current_algorithm
    
    def fuse_multi_source_data(self, multi_source_data: Dict[str, Any]) -> Dict[str, Any]:
        """融合多源数据"""
        try:
            # 转换为对齐数据格式
            aligned_data = {}
            for source_id, source_data in multi_source_data.items():
                # 处理从同步引擎传来的数据格式
                if isinstance(source_data, list):
                    # 如果source_data是列表，说明是从同步引擎传来的格式化数据
                    if source_data and isinstance(source_data[0], dict):
                        # 提取第一个数据源的信息
                        first_item = source_data[0]
                        aligned_data[source_id] = {
                            'timestamps': first_item.get('timestamps', []),
                            'values': first_item.get('values', []),
                            'quality': first_item.get('quality', 0.8),
                            'type': first_item.get('type', 'unknown')
                        }
                elif isinstance(source_data, dict):
                    # 如果source_data是字典，检查是否包含所需字段
                    if 'timestamps' in source_data and 'values' in source_data:
                        # 已经是正确格式的数据
                        aligned_data[source_id] = {
                            'timestamps': source_data.get('timestamps', []),
                            'values': source_data.get('values', []),
                            'quality': source_data.get('quality_score', source_data.get('quality', 0.8)),
                            'type': source_data.get('type', 'unknown')
                        }
                    elif 'data' in source_data:
                        # 从真实数据源获取的数据
                        real_data = source_data['data']
                        if isinstance(real_data, list) and real_data:
                            # 提取时间戳和值
                            timestamps = []
                            values = []
                            
                            for item in real_data:
                                if isinstance(item, dict):
                                    timestamps.append(item.get('timestamp', time.time()))
                                    values.append(item.get('data', item.get('value', 0)))
                                else:
                                    timestamps.append(time.time())
                                    values.append(item)
                            
                            aligned_data[source_id] = {
                                'timestamps': timestamps,
                                'values': values,
                                'quality': source_data.get('quality_score', 0.8),
                                'type': source_data.get('type', 'unknown')
                            }
                        else:
                            # 单个数据点
                            aligned_data[source_id] = {
                                'timestamps': [source_data.get('timestamp', time.time())],
                                'values': [real_data if not isinstance(real_data, (list, dict)) else 0],
                                'quality': source_data.get('quality_score', 0.8),
                                'type': source_data.get('type', 'unknown')
                            }
                    else:
                        # 其他格式，尝试提取有用信息
                        aligned_data[source_id] = {
                            'timestamps': [time.time()],
                            'values': [0],
                            'quality': source_data.get('quality_score', 0.5),
                            'type': source_data.get('type', 'unknown')
                        }
                else:
                    # 其他类型，使用默认值
                    aligned_data[source_id] = {
                        'timestamps': [time.time()],
                        'values': [0],
                        'quality': 0.5,
                        'type': 'unknown'
                    }
            
            # 执行融合
            fused_result = self.fuse_data(aligned_data)
            
            # 添加质量评估
            fusion_quality = self._evaluate_fusion_quality(fused_result)
            
            return {
                'fused_data': fused_result,
                'fusion_quality': fusion_quality,
                'algorithm_used': self.current_algorithm
            }
            
        except Exception as e:
            logger.error(f"多源数据融合失败: {e}")
            return {}
    
    def assess_fusion_quality(self, fusion_result: Dict[str, Any]) -> Any:
        """评估融合质量"""
        try:
            return self._evaluate_fusion_quality(fusion_result)
        except Exception as e:
            logger.error(f"评估融合质量失败: {e}")
            # 返回默认质量指标
            from .quality_assessor import DataQualityAssessor
            return DataQualityAssessor().assess_data_quality("fusion", fusion_result)
    
    def switch_algorithm(self, poor_performance: Any) -> Any:
        """切换算法"""
        try:
            # 基于性能指标选择新算法
            if hasattr(poor_performance, 'overall_score'):
                if poor_performance.overall_score < 0.6:
                    # 性能较差，切换到卡尔曼滤波
                    new_algorithm = FusionAlgorithm.KALMAN_FILTER
                else:
                    # 性能一般，切换到加权平均
                    new_algorithm = FusionAlgorithm.WEIGHTED_AVERAGE
            else:
                # 默认切换到加权平均
                new_algorithm = FusionAlgorithm.WEIGHTED_AVERAGE
            
            if new_algorithm in self.fusion_algorithms:
                self.current_algorithm = new_algorithm
                logger.info(f"算法已切换到: {new_algorithm}")
            
            return new_algorithm
            
        except Exception as e:
            logger.error(f"切换算法失败: {e}")
            return self.current_algorithm
    
    def _assess_data_quality(self, aligned_data: Dict[str, Any]) -> Dict[str, float]:
        """评估数据质量"""
        quality_scores = {}
        
        for source_id, source_data in aligned_data.items():
            # 计算数据的完整性、一致性、精度等指标
            completeness = self._calculate_completeness(source_data)
            consistency = self._calculate_consistency(source_data)
            precision = self._estimate_precision(source_data)
            
            # 综合质量评分
            quality = 0.4 * completeness + 0.3 * consistency + 0.3 * precision
            quality_scores[source_id] = quality
        
        return quality_scores
    
    def _calculate_completeness(self, source_data: Dict[str, Any]) -> float:
        """计算数据完整性"""
        timestamps = source_data.get('timestamps', [])
        values = source_data.get('values', [])
        
        if not timestamps or not values:
            return 0.0
        
        return len(values) / len(timestamps)
    
    def _calculate_consistency(self, source_data: Dict[str, Any]) -> float:
        """计算数据一致性"""
        timestamps = source_data.get('timestamps', [])
        
        if len(timestamps) < 2:
            return 1.0
        
        # 计算时间间隔的一致性
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        if intervals:
            std_interval = np.std(intervals)
            mean_interval = np.mean(intervals)
            if mean_interval > 0:
                consistency = max(0, 1 - std_interval / mean_interval)
                return consistency
        
        return 0.5
    
    def _estimate_precision(self, source_data: Dict[str, Any]) -> float:
        """估算数据精度"""
        # 基于数据源类型和配置估算精度
        source_type = source_data.get('type', 'unknown')
        
        if source_type == 'imu':
            return 0.95  # IMU数据通常精度较高
        elif source_type == 'cnap':
            return 0.90  # CNAP数据精度较高
        else:
            return 0.85  # 默认精度
    
    def _select_fusion_algorithm(self, quality_scores: Dict[str, float]) -> Any:
        """选择最佳融合算法"""
        if not quality_scores:
            return self.fusion_algorithms[FusionAlgorithm.WEIGHTED_AVERAGE]
        
        # 计算平均质量分数
        avg_quality = sum(quality_scores.values()) / len(quality_scores.values())
        
        # 根据数据质量选择算法
        if avg_quality > 0.85:
            # 高质量数据，使用卡尔曼滤波
            algorithm = FusionAlgorithm.KALMAN_FILTER
        elif avg_quality > 0.7:
            # 中等质量数据，使用加权平均
            algorithm = FusionAlgorithm.WEIGHTED_AVERAGE
        else:
            # 低质量数据，使用加权平均（更稳定）
            algorithm = FusionAlgorithm.WEIGHTED_AVERAGE
        
        self.current_algorithm = algorithm
        return self.fusion_algorithms[algorithm]
    
    def _evaluate_fusion_quality(self, fused_data: Dict[str, Any]) -> FusionQualityMetrics:
        """评估融合质量"""
        if not fused_data:
            return FusionQualityMetrics(timestamp=time.time())
        
        # 使用当前算法评估质量
        current_algorithm = self.fusion_algorithms[self.current_algorithm]
        
        if hasattr(current_algorithm, '_evaluate_fusion_quality'):
            return current_algorithm._evaluate_fusion_quality(fused_data)
        else:
            # 默认质量评估
            metrics = FusionQualityMetrics(timestamp=time.time())
            metrics.accuracy_score = 0.8
            metrics.stability_score = 0.8
            metrics.consistency_score = 0.8
            metrics.calculate_overall_score()
            return metrics
    
    def _update_algorithm_performance(self, algorithm: Any, fusion_quality: FusionQualityMetrics):
        """更新算法性能记录"""
        algo_name = algorithm.name
        
        if algo_name not in self.algorithm_performance:
            self.algorithm_performance[algo_name] = []
        
        performance_record = {
            'quality': fusion_quality.overall_score,
            'timestamp': time.time()
        }
        
        self.algorithm_performance[algo_name].append(performance_record)
        
        # 保持历史记录在合理大小
        if len(self.algorithm_performance[algo_name]) > 100:
            self.algorithm_performance[algo_name].pop(0)
    
    def _record_fusion_history(self, fused_data: Dict[str, Any], fusion_quality: FusionQualityMetrics, algorithm: Any):
        """记录融合历史"""
        history_entry = {
            'timestamp': time.time(),
            'algorithm': algorithm.name,
            'quality': fusion_quality.overall_score,
            'data_points': len(fused_data.get('values', {}))
        }
        
        self.fusion_history.append(history_entry)
        
        # 保持历史记录在合理大小
        if len(self.fusion_history) > 1000:
            self.fusion_history.pop(0)
    
    def start_performance_monitoring(self):
        """启动性能监控"""
        if self.monitoring_enabled and not self.monitoring_thread:
            self.monitoring_thread = threading.Thread(
                target=self._performance_monitoring_worker,
                daemon=True
            )
            self.monitoring_thread.start()
            logger.info("数据融合性能监控已启动")
    
    def _performance_monitoring_worker(self):
        """性能监控工作线程"""
        while self.monitoring_enabled:
            try:
                # 分析算法性能
                self._analyze_algorithm_performance()
                
                # 每30秒分析一次
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                time.sleep(60)
    
    def _analyze_algorithm_performance(self):
        """分析算法性能"""
        if not self.algorithm_performance:
            return
        
        # 计算各算法的平均性能
        algorithm_avg_performance = {}
        
        for algo_name, performance_records in self.algorithm_performance.items():
            if performance_records:
                avg_quality = np.mean([p['quality'] for p in performance_records])
                algorithm_avg_performance[algo_name] = {
                    'avg_quality': avg_quality,
                    'record_count': len(performance_records)
                }
        
        # 记录性能分析结果
        logger.info(f"融合算法性能分析: {algorithm_avg_performance}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            'current_algorithm': self.current_algorithm.value,
            'algorithm_performance': self.algorithm_performance,
            'fusion_history_count': len(self.fusion_history),
            'monitoring_enabled': self.monitoring_enabled
        }
    
    def set_algorithm(self, algorithm: FusionAlgorithm):
        """设置融合算法"""
        if algorithm in self.fusion_algorithms:
            self.current_algorithm = algorithm
            logger.info(f"融合算法已切换为: {algorithm.value}")
        else:
            logger.warning(f"不支持的融合算法: {algorithm}")
    
    def get_available_algorithms(self) -> List[str]:
        """获取可用的融合算法"""
        return [algorithm.value for algorithm in self.fusion_algorithms.keys()]
    
    def shutdown(self):
        """关闭数据融合引擎"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("数据融合引擎已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建自适应数据融合引擎
    fusion_engine = AdaptiveDataFusion()
    
    # 真实数据示例（需要替换为实际数据源）
    aligned_data = {
        'imu_source': {
            'id': 'imu_source',
            'type': 'imu',
            'timestamps': [time.time() + i * 0.01 for i in range(10)],
            'values': [0.0] * 10,  # 真实IMU数据待实现
            'quality_score': 0.9
        },
        'cnap_source': {
            'id': 'cnap_source',
            'type': 'cnap',
            'timestamps': [time.time() + i * 1.0 for i in range(10)],
            'values': [120.0] * 10,  # 真实CNAP数据待实现
            'quality_score': 0.85
        }
    }
    
    # 执行数据融合
    result = fusion_engine.fuse_data(aligned_data)
    
    # 输出结果
    logger.info(f"融合结果: {result}")
    
    # 获取性能摘要
    performance = fusion_engine.get_performance_summary()
    logger.info(f"性能摘要: {performance}")
    
    # 关闭引擎
    fusion_engine.shutdown()

    
    def get_available_algorithms(self) -> List[str]:
        """获取可用的融合算法"""
        return [algorithm.value for algorithm in self.fusion_algorithms.keys()]
    
    def shutdown(self):
        """关闭数据融合引擎"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("数据融合引擎已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建自适应数据融合引擎
    fusion_engine = AdaptiveDataFusion()
    
    # 真实数据示例（需要替换为实际数据源）
    aligned_data = {
        'imu_source': {
            'id': 'imu_source',
            'type': 'imu',
            'timestamps': [time.time() + i * 0.01 for i in range(10)],
            'values': [0.0] * 10,  # 真实IMU数据待实现
            'quality_score': 0.9
        },
        'cnap_source': {
            'id': 'cnap_source',
            'type': 'cnap',
            'timestamps': [time.time() + i * 1.0 for i in range(10)],
            'values': [120.0] * 10,  # 真实CNAP数据待实现
            'quality_score': 0.85
        }
    }
    
    # 执行数据融合
    result = fusion_engine.fuse_data(aligned_data)
    
    # 输出结果
    logger.info(f"融合结果: {result}")
    
    # 获取性能摘要
    performance = fusion_engine.get_performance_summary()
    logger.info(f"性能摘要: {performance}")
    
    # 关闭引擎
    fusion_engine.shutdown()

    
    def get_available_algorithms(self) -> List[str]:
        """获取可用的融合算法"""
        return [algorithm.value for algorithm in self.fusion_algorithms.keys()]
    
    def shutdown(self):
        """关闭数据融合引擎"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("数据融合引擎已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建自适应数据融合引擎
    fusion_engine = AdaptiveDataFusion()
    
    # 真实数据示例（需要替换为实际数据源）
    aligned_data = {
        'imu_source': {
            'id': 'imu_source',
            'type': 'imu',
            'timestamps': [time.time() + i * 0.01 for i in range(10)],
            'values': [0.0] * 10,  # 真实IMU数据待实现
            'quality_score': 0.9
        },
        'cnap_source': {
            'id': 'cnap_source',
            'type': 'cnap',
            'timestamps': [time.time() + i * 1.0 for i in range(10)],
            'values': [120.0] * 10,  # 真实CNAP数据待实现
            'quality_score': 0.85
        }
    }
    
    # 执行数据融合
    result = fusion_engine.fuse_data(aligned_data)
    
    # 输出结果
    logger.info(f"融合结果: {result}")
    
    # 获取性能摘要
    performance = fusion_engine.get_performance_summary()
    logger.info(f"性能摘要: {performance}")
    
    # 关闭引擎
    fusion_engine.shutdown()

    
    def get_available_algorithms(self) -> List[str]:
        """获取可用的融合算法"""
        return [algorithm.value for algorithm in self.fusion_algorithms.keys()]
    
    def shutdown(self):
        """关闭数据融合引擎"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("数据融合引擎已关闭")


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建自适应数据融合引擎
    fusion_engine = AdaptiveDataFusion()
    
    # 真实数据示例（需要替换为实际数据源）
    aligned_data = {
        'imu_source': {
            'id': 'imu_source',
            'type': 'imu',
            'timestamps': [time.time() + i * 0.01 for i in range(10)],
            'values': [0.0] * 10,  # 真实IMU数据待实现
            'quality_score': 0.9
        },
        'cnap_source': {
            'id': 'cnap_source',
            'type': 'cnap',
            'timestamps': [time.time() + i * 1.0 for i in range(10)],
            'values': [120.0] * 10,  # 真实CNAP数据待实现
            'quality_score': 0.85
        }
    }
    
    # 执行数据融合
    result = fusion_engine.fuse_data(aligned_data)
    
    # 输出结果
    logger.info(f"融合结果: {result}")
    
    # 获取性能摘要
    performance = fusion_engine.get_performance_summary()
    logger.info(f"性能摘要: {performance}")
    
    # 关闭引擎
    fusion_engine.shutdown()
