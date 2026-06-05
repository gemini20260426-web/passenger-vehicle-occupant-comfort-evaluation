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
    STREAMING_KALMAN = "streaming_kalman"  # 流式卡尔曼滤波 (新增)


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
        """从数据中提取数值 (扁平化, 无嵌套 try/except)"""
        if data is None:
            return None
        if isinstance(data, (int, float, np.integer, np.floating)):
            return float(data)
        if isinstance(data, str):
            try:
                return float(data)
            except (ValueError, TypeError):
                return None
        if isinstance(data, dict):
            for key in ('value', 'data', 'magnitude', 'amplitude'):
                val = data.get(key)
                if isinstance(val, (int, float, np.integer, np.floating)):
                    return float(val)
                if isinstance(val, str):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
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
    """卡尔曼滤波融合算法 (多维状态向量, 6-12维)
    
    状态向量: [x, vx, ax, y, vy, ay, z, vz, az]  (9维IMU)
    或简化: [value, velocity, acceleration]         (3维通用)
    
    支持:
    - 多维状态估计
    - 自适应噪声协方差
    - 多传感器测量融合
    """
    
    def __init__(self, state_dim: int = 3, dt: float = 0.01):
        self.name = "kalman_filter"
        self.state_dim = state_dim  # 状态维度
        self.dt = dt                # 时间步长
        
        # 状态向量 x
        self.x = np.zeros(state_dim)
        
        # 状态协方差矩阵 P
        self.P = np.eye(state_dim) * 1000.0
        
        # 状态转移矩阵 F
        self.F = self._build_transition_matrix(state_dim, dt)
        
        # 过程噪声协方差 Q
        self.Q = np.eye(state_dim) * 0.01
        
        # 测量矩阵 H (观测第1个状态分量)
        self.H = np.zeros((1, state_dim))
        self.H[0, 0] = 1.0
        
        # 测量噪声协方差 R
        self.R = np.array([[0.5]])
        
        self.performance_history = []
        self.state_history: List[np.ndarray] = []
    
    def _build_transition_matrix(self, dim: int, dt: float) -> np.ndarray:
        """构建状态转移矩阵
        
        对于3维通用状态 [value, velocity, acceleration]:
        F = [[1, dt, 0.5*dt^2],
             [0, 1,  dt       ],
             [0, 0,  1        ]]
        """
        F = np.eye(dim)
        if dim >= 2:
            # 速度分量
            F[0, 1] = dt
            if dim >= 3:
                F[0, 2] = 0.5 * dt * dt
                F[1, 2] = dt
        return F
    
    def fuse(self, aligned_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行卡尔曼滤波融合"""
        try:
            if not aligned_data:
                return {}
            
            # 重置状态
            self._reset_state()
            
            # 执行卡尔曼滤波
            fused_values = self._perform_kalman_fusion(aligned_data)
            
            fusion_quality = self._evaluate_fusion_quality(
                {'values': fused_values}
            )
            self._record_performance(fusion_quality)
            
            return {
                'fused_data': {
                    'timestamp': time.time(),
                    'values': fused_values,
                    'metadata': {
                        'fusion_algorithm': self.name,
                        'state_dim': self.state_dim,
                        'kalman_params': {
                            'process_noise': np.trace(self.Q),
                            'measurement_noise': float(self.R[0, 0]),
                        }
                    }
                },
                'metadata': {
                    'quality_metrics': fusion_quality,
                    'algorithm': self.name,
                    'fusion_timestamp': time.time()
                }
            }
            
        except Exception as e:
            logger.error(f"卡尔曼滤波融合失败: {e}")
            return {}
    
    def fuse_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.fuse(data)
    
    def fuse_numpy(self, data: np.ndarray, dt: Optional[float] = None) -> np.ndarray:
        """直接对 numpy 数组进行卡尔曼滤波 (CSV格式支持)
        
        Args:
            data: (N,) 或 (N, M) 测量值数组
            dt: 时间步长 (默认使用初始化值)
            
        Returns:
            (N,) 滤波后的值
        """
        if dt is not None:
            self.dt = dt
            self.F = self._build_transition_matrix(self.state_dim, dt)
        
        data = np.atleast_1d(data)
        if data.ndim > 1:
            data = data.ravel()
        
        n = len(data)
        filtered = np.zeros(n)
        self._reset_state()
        
        for i in range(n):
            # 预测
            self._predict()
            # 更新
            self._update(data[i])
            filtered[i] = self.x[0]
        
        return filtered
    
    def fuse_numpy_batch(self, data: np.ndarray, dt: Optional[float] = None) -> Dict[str, np.ndarray]:
        """批量 numpy 融合: 返回滤波值 + 速度 + 加速度估计
        
        Args:
            data: (N,) 测量值
            dt: 时间步长
            
        Returns:
            {'filtered': (N,), 'velocity': (N,), 'acceleration': (N,)}
        """
        if dt is not None:
            self.dt = dt
            self.F = self._build_transition_matrix(self.state_dim, dt)
        
        data = np.atleast_1d(data).ravel()
        n = len(data)
        filtered = np.zeros(n)
        velocity = np.zeros(n) if self.state_dim >= 2 else None
        acceleration = np.zeros(n) if self.state_dim >= 3 else None
        
        self._reset_state()
        
        for i in range(n):
            self._predict()
            self._update(data[i])
            filtered[i] = self.x[0]
            if velocity is not None:
                velocity[i] = self.x[1] if self.state_dim >= 2 else 0
            if acceleration is not None:
                acceleration[i] = self.x[2] if self.state_dim >= 3 else 0
        
        result = {'filtered': filtered}
        if velocity is not None:
            result['velocity'] = velocity
        if acceleration is not None:
            result['acceleration'] = acceleration
        return result
    
    def _reset_state(self):
        """重置状态估计"""
        self.x = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim) * 1000.0
        self.state_history = []
    
    def _predict(self):
        """预测步骤"""
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
    
    def _update(self, measurement: float):
        """更新步骤 (标量测量值)
        
        Args:
            measurement: 测量值
        """
        innovation = measurement - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        self.x = self.x + K @ innovation
        self.P = (np.eye(self.state_dim) - K @ self.H) @ self.P
        
        self.state_history.append(self.x.copy())
    
    def adapt_to_noise(self, noisy_measurements: List[float]):
        """自适应噪声参数"""
        try:
            if len(noisy_measurements) < 2:
                return
            
            measurements_array = np.array(noisy_measurements)
            noise_variance = np.var(measurements_array)
            self.R = np.array([[max(0.001, noise_variance)]])
            
            if len(noisy_measurements) > 2:
                diffs = np.diff(noisy_measurements)
                process_variance = np.var(diffs)
                self.Q = np.eye(self.state_dim) * max(1e-6, process_variance)
            
            logger.info(
                f"噪声参数已调整: R={float(self.R[0,0]):.4f}, "
                f"Q_trace={np.trace(self.Q):.4f}"
            )
            
        except Exception as e:
            logger.error(f"自适应噪声参数失败: {e}")
    
    @property
    def noise_params(self) -> Dict[str, float]:
        return {
            'process_noise_trace': float(np.trace(self.Q)),
            'measurement_noise': float(self.R[0, 0]),
        }
    
    def _perform_kalman_fusion(self, aligned_data: Dict[str, Any]) -> Dict[float, float]:
        """执行卡尔曼滤波融合 (多维版)"""
        all_timestamps = set()
        for source_data in aligned_data.values():
            all_timestamps.update(source_data.get('timestamps', []))
        
        all_timestamps = sorted(all_timestamps)
        fused_values = {}
        
        for ts in all_timestamps:
            measurement = self._kalman_fuse_at_timestamp(ts, aligned_data)
            if measurement is not None:
                fused_values[ts] = measurement
        
        return fused_values
    
    def _kalman_fuse_at_timestamp(self, timestamp: float, aligned_data: Dict[str, Any]) -> Optional[float]:
        """在指定时间点进行卡尔曼滤波融合 (多维版)"""
        measurements = []
        measurement_noises = []
        
        for source_id, source_data in aligned_data.items():
            timestamps = source_data.get('timestamps', [])
            values = source_data.get('values', [])
            
            if timestamp in timestamps:
                idx = timestamps.index(timestamp)
                value = values[idx]
                quality_score = source_data.get('quality_score', 0.5)
                
                if isinstance(value, (int, float, np.integer, np.floating)):
                    measurements.append(float(value))
                    adjusted_noise = float(self.R[0, 0]) / max(0.1, quality_score)
                    measurement_noises.append(adjusted_noise)
                elif isinstance(value, dict):
                    numeric_value = value.get('value', value.get('data', 0))
                    if isinstance(numeric_value, (int, float, np.integer, np.floating)):
                        measurements.append(float(numeric_value))
                        measurement_noises.append(float(self.R[0, 0]) / max(0.1, quality_score))
                else:
                    try:
                        measurements.append(float(value))
                        measurement_noises.append(float(self.R[0, 0]) / max(0.1, quality_score))
                    except (ValueError, TypeError):
                        continue
        
        if not measurements:
            return None
        
        # 预测
        self._predict()
        
        # 使用多传感器测量更新
        for measurement, noise in zip(measurements, measurement_noises):
            self.R = np.array([[noise]])
            self._update(measurement)
        
        return float(self.x[0])
    
    def _evaluate_fusion_quality(self, fused_data: Dict[str, Any]) -> FusionQualityMetrics:
        metrics = FusionQualityMetrics(timestamp=time.time())
        if not fused_data or 'values' not in fused_data:
            return metrics
        
        values = fused_data['values']
        if isinstance(values, dict):
            data_points = len(values)
        else:
            data_points = len(values) if hasattr(values, '__len__') else 0
        
        metrics.accuracy_score = max(0, 1 - np.trace(self.Q) / 10)
        metrics.stability_score = min(1.0, data_points / 100)
        
        if self.state_history:
            states = np.array([s[0] for s in self.state_history])
            if len(states) > 1:
                avg_state = np.mean(states)
                if abs(avg_state) > 1e-6:
                    metrics.consistency_score = max(0, 1 - np.std(states) / abs(avg_state))
                else:
                    metrics.consistency_score = 0.5
            else:
                metrics.consistency_score = 0.5
        else:
            metrics.consistency_score = 0.5
        
        metrics.calculate_overall_score()
        return metrics
    
    def _record_performance(self, fusion_quality: FusionQualityMetrics):
        self.performance_history.append({
            'quality': fusion_quality.overall_score,
            'timestamp': time.time()
        })
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)


class StreamingKalmanFusion:
    """流式卡尔曼滤波融合 (逐帧处理, 支持实时在线)
    
    与 KalmanFilterFusion 的区别:
    - 不需要全量时间戳, 逐帧处理
    - 状态持续保持, 不清空
    - 支持 numpy 数组实时输入
    """
    
    def __init__(self, state_dim: int = 3, dt: float = 0.01):
        self.name = "streaming_kalman"
        self.state_dim = state_dim
        self.dt = dt
        
        self.x = np.zeros(state_dim)
        self.P = np.eye(state_dim) * 1000.0
        self.F = self._build_transition_matrix(state_dim, dt)
        self.Q = np.eye(state_dim) * 0.01
        self.H = np.zeros((1, state_dim))
        self.H[0, 0] = 1.0
        self.R = np.array([[0.5]])
        
        self.frame_count = 0
        self.filtered_history: List[float] = []
    
    def _build_transition_matrix(self, dim: int, dt: float) -> np.ndarray:
        F = np.eye(dim)
        if dim >= 2:
            F[0, 1] = dt
            if dim >= 3:
                F[0, 2] = 0.5 * dt * dt
                F[1, 2] = dt
        return F
    
    def update(self, measurement: float) -> float:
        """处理单帧测量值, 返回滤波后的值
        
        Args:
            measurement: 当前帧测量值
            
        Returns:
            滤波后的估计值
        """
        # 预测
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        # 更新
        innovation = measurement - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        self.x = self.x + K @ innovation
        self.P = (np.eye(self.state_dim) - K @ self.H) @ self.P
        
        self.frame_count += 1
        filtered_value = float(self.x[0])
        self.filtered_history.append(filtered_value)
        
        # 限制历史长度
        if len(self.filtered_history) > 10000:
            self.filtered_history = self.filtered_history[-5000:]
        
        return filtered_value
    
    def update_multi_source(self, measurements: List[float],
                           quality_scores: Optional[List[float]] = None) -> float:
        """多传感器流式融合
        
        Args:
            measurements: 多个传感器的测量值
            quality_scores: 对应的质量分数 (用于调整噪声)
            
        Returns:
            融合后的估计值
        """
        if not measurements:
            return float(self.x[0])
        
        # 预测
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        for i, measurement in enumerate(measurements):
            if quality_scores and i < len(quality_scores):
                adjusted_R = np.array([[float(self.R[0, 0]) / max(0.1, quality_scores[i])]])
            else:
                adjusted_R = self.R
            
            innovation = measurement - self.H @ self.x
            S = self.H @ self.P @ self.H.T + adjusted_R
            K = self.P @ self.H.T @ np.linalg.inv(S)
            
            self.x = self.x + K @ innovation
            self.P = (np.eye(self.state_dim) - K @ self.H) @ self.P
        
        self.frame_count += 1
        return float(self.x[0])
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态估计"""
        return {
            'value': float(self.x[0]),
            'velocity': float(self.x[1]) if self.state_dim >= 2 else 0.0,
            'acceleration': float(self.x[2]) if self.state_dim >= 3 else 0.0,
            'covariance_trace': float(np.trace(self.P)),
            'frame_count': self.frame_count,
        }
    
    def reset(self):
        """重置状态"""
        self.x = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim) * 1000.0
        self.frame_count = 0
        self.filtered_history = []


class AdaptiveDataFusion:
    """自适应数据融合算法 (已废弃 — 请使用 IMUDualRedundantFusion)
    
    Deprecated: 通用融合引擎, 从未在本项目数据上实测, 输入格式与本CSV不匹配。
    替代方案: core.core.multi_source_sync.imu_fusion_engine.IMUDualRedundantFusion
    """
    
    def __init__(self):
        self.fusion_algorithms = {
            FusionAlgorithm.WEIGHTED_AVERAGE: WeightedAverageFusion(),
            FusionAlgorithm.KALMAN_FILTER: KalmanFilterFusion(state_dim=3),
            FusionAlgorithm.STREAMING_KALMAN: StreamingKalmanFusion(state_dim=3),
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
    
    def fuse_numpy(self, data: np.ndarray, dt: float = 0.01,
                   algorithm: FusionAlgorithm = FusionAlgorithm.KALMAN_FILTER) -> np.ndarray:
        """直接对 numpy 数组进行融合 (CSV/离线数据格式)
        
        Args:
            data: (N,) 或 (N, M) 测量值数组
            dt: 时间步长
            algorithm: 融合算法
            
        Returns:
            (N,) 融合后的值
        """
        if algorithm not in self.fusion_algorithms:
            raise ValueError(f"不支持的融合算法: {algorithm}")
        
        algo = self.fusion_algorithms[algorithm]
        if hasattr(algo, 'fuse_numpy'):
            return algo.fuse_numpy(data, dt)
        elif hasattr(algo, 'update'):
            # StreamingKalmanFusion
            result = np.zeros(len(data))
            for i in range(len(data)):
                result[i] = algo.update(float(data[i]))
            return result
        else:
            raise TypeError(f"算法 {algorithm} 不支持 numpy 融合")
    
    def fuse_numpy_batch(self, data: np.ndarray, dt: float = 0.01,
                         algorithm: FusionAlgorithm = FusionAlgorithm.KALMAN_FILTER) -> Dict[str, np.ndarray]:
        """批量 numpy 融合: 返回滤波值 + 速度 + 加速度
        
        Args:
            data: (N,) 测量值
            dt: 时间步长
            algorithm: 融合算法
            
        Returns:
            {'filtered': (N,), 'velocity': (N,), 'acceleration': (N,)}
        """
        if algorithm not in self.fusion_algorithms:
            raise ValueError(f"不支持的融合算法: {algorithm}")
        
        algo = self.fusion_algorithms[algorithm]
        if hasattr(algo, 'fuse_numpy_batch'):
            return algo.fuse_numpy_batch(data, dt)
        else:
            filtered = algo.fuse_numpy(data, dt)
            return {'filtered': filtered}
    
    @staticmethod
    def interp_align(data_a: np.ndarray, ts_a: np.ndarray,
                     data_b: np.ndarray, ts_b: np.ndarray,
                     target_ts: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """不同采样率插值对齐
        
        将两个不同采样率的数据源对齐到统一时间轴。
        
        Args:
            data_a: 数据源A (N,)
            ts_a: 数据源A的时间戳 (N,)
            data_b: 数据源B (M,)
            ts_b: 数据源B的时间戳 (M,)
            target_ts: 目标时间轴 (默认合并两个时间轴)
            
        Returns:
            {'ts': (K,), 'data_a': (K,), 'data_b': (K,)}
        """
        if target_ts is None:
            target_ts = np.union1d(ts_a, ts_b)
        
        target_ts = np.sort(target_ts)
        
        aligned_a = np.interp(target_ts, ts_a, data_a)
        aligned_b = np.interp(target_ts, ts_b, data_b)
        
        return {
            'ts': target_ts,
            'data_a': aligned_a,
            'data_b': aligned_b,
        }
    
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
    
    # 模拟真实IMU数据 (1000Hz, 1秒)
    np.random.seed(42)
    t = np.arange(0, 1.0, 0.001)
    # 模拟加速度信号: 正弦波 + 噪声
    signal = 0.5 * np.sin(2 * np.pi * 5 * t) + 0.1 * np.random.randn(len(t))
    
    # 1. 多维卡尔曼滤波融合
    kf = KalmanFilterFusion(state_dim=3, dt=0.001)
    result = kf.fuse_numpy_batch(signal)
    logger.info(f"多维KF融合: filtered均值={result['filtered'].mean():.4f}, "
                f"velocity范围=[{result['velocity'].min():.4f}, {result['velocity'].max():.4f}]")
    
    # 2. 流式卡尔曼滤波
    sf = StreamingKalmanFusion(state_dim=3, dt=0.001)
    filtered_stream = np.array([sf.update(float(v)) for v in signal])
    logger.info(f"流式KF融合: 均值={filtered_stream.mean():.4f}, 状态={sf.get_state()}")
    
    # 3. 插值对齐 (模拟不同采样率: 1000Hz vs 100Hz)
    ts_imu = np.arange(0, 1.0, 0.001)  # 1000Hz IMU
    ts_cnap = np.arange(0, 1.0, 0.01)  # 100Hz CNAP
    data_imu = signal
    data_cnap = 120.0 + 5.0 * np.sin(2 * np.pi * 0.5 * ts_cnap) + 0.5 * np.random.randn(len(ts_cnap))
    
    aligned = AdaptiveDataFusion.interp_align(data_imu, ts_imu, data_cnap, ts_cnap)
    logger.info(f"插值对齐: ts={len(aligned['ts'])}点, "
                f"IMU范围=[{aligned['data_a'].min():.2f}, {aligned['data_a'].max():.2f}], "
                f"CNAP范围=[{aligned['data_b'].min():.2f}, {aligned['data_b'].max():.2f}]")
    
    # 4. 自适应融合引擎
    fusion_engine = AdaptiveDataFusion()
    performance = fusion_engine.get_performance_summary()
    logger.info(f"融合引擎: {performance['current_algorithm']}")
    logger.info(f"可用算法: {fusion_engine.get_available_algorithms()}")
    
    fusion_engine.shutdown()
