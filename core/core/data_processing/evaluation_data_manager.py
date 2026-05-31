#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评估数据管理器
整合驾驶评估模块所需的算子和衍生指标
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
# from data_processing.data_source_manager import DataSourceManager  # 已删除，使用unified_data_source_manager替代
from ..analysis.base_analyzer import BasicDrivingAnalyzer
from ..analysis.advanced_analyzer import AdvancedBehaviorAnalyzer

logger = logging.getLogger(__name__)


class EvaluationDataManager:
    """
    评估数据管理器
    整合驾驶评估模块所需的算子和衍生指标
    """
    
    def __init__(self, data_source_manager=None):  # 类型注解暂时移除
        self.data_source_manager = data_source_manager
        self.derived_metrics = {}
        self.evaluation_operators = {}
        self._init_evaluation_operators()
        
    def _init_evaluation_operators(self):
        """初始化评估算子"""
        # 基础统计算子
        self.evaluation_operators.update({
            'mean': np.mean,
            'std': np.std,
            'min': np.min,
            'max': np.max,
            'percentile_25': lambda x: np.percentile(x, 25) if len(x) > 0 else 0,
            'percentile_75': lambda x: np.percentile(x, 75) if len(x) > 0 else 0,
            'median': np.median,
        })
        
        # 行为计数算子
        self.evaluation_operators.update({
            'hard_acceleration_count': self._count_hard_accelerations,
            'hard_braking_count': self._count_hard_brakings,
            'sharp_turn_count': self._count_sharp_turns,
            'overspeed_count': self._count_overspeeds,
        })
        
        # 时间相关算子
        self.evaluation_operators.update({
            'total_driving_time': self._calculate_total_driving_time,
            'idle_time': self._calculate_idle_time,
            'average_speed': self._calculate_average_speed,
        })
        
    def _count_hard_accelerations(self, data: List[Dict[str, Any]]) -> int:
        """计算急加速次数"""
        count = 0
        if hasattr(self.data_source_manager.config_manager, 'get_config'):
            threshold = self.data_source_manager.config_manager.get_config(
                'AnalysisConfig', 'hard_acceleration_threshold', 3.0)
        else:
            threshold = 3.0
            
        for record in data:
            if 'acceleration' in record and record['acceleration'] > threshold:
                count += 1
        return count
        
    def _count_hard_brakings(self, data: List[Dict[str, Any]]) -> int:
        """计算急刹车次数"""
        count = 0
        if hasattr(self.data_source_manager.config_manager, 'get_config'):
            threshold = self.data_source_manager.config_manager.get_config(
                'AnalysisConfig', 'hard_brake_threshold', -4.0)
        else:
            threshold = -4.0
            
        for record in data:
            if 'acceleration' in record and record['acceleration'] < threshold:
                count += 1
        return count
        
    def _count_sharp_turns(self, data: List[Dict[str, Any]]) -> int:
        """计算急转弯次数"""
        count = 0
        if hasattr(self.data_source_manager.config_manager, 'get_config'):
            threshold = self.data_source_manager.config_manager.get_config(
                'AnalysisConfig', 'sharp_turn_threshold', 2.0)
        else:
            threshold = 2.0
            
        for record in data:
            if 'angular_velocity' in record:
                # 计算角速度的模
                angular_vel = record['angular_velocity']
                if isinstance(angular_vel, (list, tuple)) and len(angular_vel) >= 3:
                    magnitude = np.sqrt(sum([x**2 for x in angular_vel[:3]]))
                    if magnitude > threshold:
                        count += 1
                elif isinstance(angular_vel, (int, float)) and abs(angular_vel) > threshold:
                    count += 1
        return count
        
    def _count_overspeeds(self, data: List[Dict[str, Any]]) -> int:
        """计算超速次数"""
        count = 0
        if hasattr(self.data_source_manager.config_manager, 'get_config'):
            threshold = self.data_source_manager.config_manager.get_config(
                'AnalysisConfig', 'overspeed_threshold', 120.0)
        else:
            threshold = 120.0
            
        for record in data:
            if 'speed' in record and record['speed'] > threshold:
                count += 1
        return count
        
    def _calculate_total_driving_time(self, data: List[Dict[str, Any]]) -> float:
        """计算总驾驶时间"""
        if len(data) < 2:
            return 0
            
        # 假设数据按时间排序
        start_time = data[0].get('timestamp')
        end_time = data[-1].get('timestamp')
        
        if start_time and end_time:
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
                
            return (end_time - start_time).total_seconds()
        return 0
        
    def _calculate_idle_time(self, data: List[Dict[str, Any]]) -> float:
        """计算怠速时间"""
        idle_time = 0
        if hasattr(self.data_source_manager.config_manager, 'get_config'):
            threshold = self.data_source_manager.config_manager.get_config(
                'AnalysisConfig', 'idle_speed_threshold', 1.0)
        else:
            threshold = 1.0
            
        for record in data:
            if 'speed' in record and record['speed'] < threshold:
                # 假设每个记录代表1秒的数据
                idle_time += 1
        return idle_time
        
    def _calculate_average_speed(self, data: List[Dict[str, Any]]) -> float:
        """计算平均速度"""
        speeds = [record['speed'] for record in data if 'speed' in record]
        if speeds:
            return np.mean(speeds)
        return 0
        
    def calculate_derived_metrics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算衍生指标
        
        Args:
            data: 原始数据列表
            
        Returns:
            Dict[str, Any]: 衍生指标字典
        """
        metrics = {}
        
        # 计算基础统计指标
        speeds = [record['speed'] for record in data if 'speed' in record]
        accelerations = [record['acceleration'] for record in data if 'acceleration' in record]
        
        if speeds:
            metrics['speed_stats'] = {
                'mean': self.evaluation_operators['mean'](speeds),
                'std': self.evaluation_operators['std'](speeds),
                'min': self.evaluation_operators['min'](speeds),
                'max': self.evaluation_operators['max'](speeds),
                'percentile_25': self.evaluation_operators['percentile_25'](speeds),
                'percentile_75': self.evaluation_operators['percentile_75'](speeds),
                'median': self.evaluation_operators['median'](speeds),
            }
            
        if accelerations:
            metrics['acceleration_stats'] = {
                'mean': self.evaluation_operators['mean'](accelerations),
                'std': self.evaluation_operators['std'](accelerations),
                'min': self.evaluation_operators['min'](accelerations),
                'max': self.evaluation_operators['max'](accelerations),
                'percentile_25': self.evaluation_operators['percentile_25'](accelerations),
                'percentile_75': self.evaluation_operators['percentile_75'](accelerations),
                'median': self.evaluation_operators['median'](accelerations),
            }
            
        # 计算行为计数指标
        metrics['behavior_counts'] = {
            'hard_acceleration_count': self.evaluation_operators['hard_acceleration_count'](data),
            'hard_braking_count': self.evaluation_operators['hard_braking_count'](data),
            'sharp_turn_count': self.evaluation_operators['sharp_turn_count'](data),
            'overspeed_count': self.evaluation_operators['overspeed_count'](data),
        }
        
        # 计算时间相关指标
        metrics['time_metrics'] = {
            'total_driving_time': self.evaluation_operators['total_driving_time'](data),
            'idle_time': self.evaluation_operators['idle_time'](data),
            'average_speed': self.evaluation_operators['average_speed'](data),
        }
        
        # 计算评分相关指标
        metrics['scoring_metrics'] = self._calculate_scoring_metrics(data, metrics)
        
        self.derived_metrics = metrics
        return metrics
        
    def _calculate_scoring_metrics(self, data: List[Dict[str, Any]], base_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算评分相关指标
        
        Args:
            data: 原始数据列表
            base_metrics: 基础指标
            
        Returns:
            Dict[str, Any]: 评分相关指标
        """
        scoring_metrics = {}
        
        # 计算行为频率
        total_time_hours = base_metrics.get('time_metrics', {}).get('total_driving_time', 0) / 3600
        if total_time_hours > 0:
            behavior_counts = base_metrics.get('behavior_counts', {})
            scoring_metrics['behavior_frequency'] = {
                'hard_acceleration_per_hour': behavior_counts.get('hard_acceleration_count', 0) / total_time_hours,
                'hard_braking_per_hour': behavior_counts.get('hard_braking_count', 0) / total_time_hours,
                'sharp_turn_per_hour': behavior_counts.get('sharp_turn_count', 0) / total_time_hours,
                'overspeed_per_hour': behavior_counts.get('overspeed_count', 0) / total_time_hours,
            }
            
        # 计算平稳性指标
        accelerations = [abs(record['acceleration']) for record in data if 'acceleration' in record]
        if accelerations:
            scoring_metrics['smoothness'] = {
                'avg_abs_acceleration': np.mean(accelerations),
                'std_acceleration': np.std(accelerations),
            }
            
        return scoring_metrics
        
    def get_evaluation_data(self, time_range: Optional[tuple] = None) -> Dict[str, Any]:
        """
        获取评估数据
        
        Args:
            time_range: 时间范围 (start_time, end_time)，可选
            
        Returns:
            Dict[str, Any]: 评估数据
        """
        try:
            # 从数据源管理器获取数据
            # 注意：这里需要根据实际的数据源类型来获取数据
            evaluation_data = {
                'derived_metrics': self.derived_metrics,
                'timestamp': datetime.now().isoformat(),
            }
            
            return evaluation_data
        except Exception as e:
            logger.error(f"获取评估数据时发生错误: {e}")
            return {}
            
    def update_data(self, new_data: List[Dict[str, Any]]) -> None:
        """
        更新数据并重新计算衍生指标
        
        Args:
            new_data: 新数据列表
        """
        try:
            # 计算新的衍生指标
            self.calculate_derived_metrics(new_data)
            logger.info("评估数据更新完成")
        except Exception as e:
            logger.error(f"更新评估数据时发生错误: {e}")