#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测引擎核心
基于9大算子系统的指标计算引擎
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal

from .operators import OperatorSystem
from ..analysis.core_types import (
    EvaluationTrigger, EvaluationResult, RiskLevel, INDICATOR_DEFINITIONS
)

logger = logging.getLogger(__name__)


class SeatEvaluationEngine(QObject):
    """座椅评测引擎核心"""
    
    evaluation_started = Signal(dict)
    evaluation_completed = Signal(dict)
    metric_calculated = Signal(dict)
    
    def __init__(self, config_manager=None, data_storage=None):
        super().__init__()
        self.config_manager = config_manager
        self.data_storage = data_storage
        
        # 初始化算子系统
        self.operator_system = OperatorSystem()
        
        # 默认采样率
        self.default_sample_rate = 100.0
        
        logger.info("座椅评测引擎初始化完成")
    
    def evaluate_by_event(self, trigger: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于事件执行评测
        
        Args:
            trigger: 评测触发器字典
            
        Returns:
            评测结果字典
        """
        try:
            self.evaluation_started.emit(trigger)
            
            trigger_id = trigger.get('event_id', '')
            event_type = trigger.get('event_type', '')
            metrics = trigger.get('metrics', [])
            raw_data = trigger.get('raw_data', {})
            
            # 提取数据窗口
            data_window = self._extract_data_window(raw_data, trigger.get('data_window', {}))
            
            if not data_window:
                logger.warning(f"无法提取数据窗口: {trigger_id}")
                return None
            
            # 计算指标
            calculated_metrics = self._calculate_metrics(data_window, metrics)
            
            # 计算总体评分
            overall_score = self._calculate_overall_score(calculated_metrics)
            
            # 评估风险等级
            risk_level = self._assess_risk(calculated_metrics)
            
            # 构造结果
            result = EvaluationResult(
                trigger_id=trigger_id,
                event_type=event_type,
                timestamp=trigger.get('timestamp', 0.0),
                metrics=calculated_metrics,
                overall_score=overall_score,
                risk_level=risk_level
            )
            
            # 转换为字典并发送信号
            result_dict = self._result_to_dict(result)
            self.evaluation_completed.emit(result_dict)
            
            logger.info(f"座椅评测完成: {trigger_id}, 总体评分: {overall_score:.2f}")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"座椅评测失败: {e}", exc_info=True)
            return None
    
    def _extract_data_window(self, raw_data: Dict[str, Any], 
                            window_config: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        提取数据窗口（单位转换：m/s² → g）
        
        Args:
            raw_data: 原始数据
            window_config: 窗口配置 (pre, post)
            
        Returns:
            数据窗口字典（加速度单位：g）
        """
        try:
            # 简化实现 - 实际需要从数据存储中提取指定时间窗口的数据
            # 这里假设raw_data已经包含需要的数据
            
            # 提取三轴加速度数据（单位转换：m/s² → g）
            data_window = {
                'ax': np.array(raw_data.get('ax', [])) / 9.81,
                'ay': np.array(raw_data.get('ay', [])) / 9.81,
                'az': np.array(raw_data.get('az', [])) / 9.81,
                'sample_rate': self.default_sample_rate
            }
            
            # 如果数据为空，生成一些模拟数据用于测试
            if len(data_window['ax']) == 0:
                n_samples = int((window_config.get('pre', 0.5) + window_config.get('post', 1.5)) * self.default_sample_rate)
                data_window['ax'] = np.random.randn(n_samples) * 0.5
                data_window['ay'] = np.random.randn(n_samples) * 0.3
                data_window['az'] = np.random.randn(n_samples) * 1.0 + 1.0
            
            return data_window
            
        except Exception as e:
            logger.error(f"提取数据窗口失败: {e}")
            return None
    
    def _calculate_metrics(self, data_window: Dict[str, Any], 
                          metrics: List[str]) -> Dict[str, float]:
        """
        计算指定指标
        
        Args:
            data_window: 数据窗口
            metrics: 指标ID列表
            
        Returns:
            指标结果字典
        """
        results = {}
        
        for metric_id in metrics:
            try:
                value = self._calculate_single_metric(metric_id, data_window)
                results[metric_id] = value
                
                # 发送指标计算完成信号
                self.metric_calculated.emit({
                    'metric_id': metric_id,
                    'value': value,
                    'definition': INDICATOR_DEFINITIONS.get(metric_id, {})
                })
                
            except Exception as e:
                logger.error(f"计算指标 {metric_id} 失败: {e}")
                results[metric_id] = 0.0
        
        return results
    
    def _calculate_single_metric(self, metric_id: str, 
                                data_window: Dict[str, Any]) -> float:
        """
        计算单个指标
        
        Args:
            metric_id: 指标ID
            data_window: 数据窗口
            
        Returns:
            指标值
        """
        ops = self.operator_system
        ax = data_window.get('ax', np.array([]))
        ay = data_window.get('ay', np.array([]))
        az = data_window.get('az', np.array([]))
        sr = data_window.get('sample_rate', self.default_sample_rate)
        
        # 原有频域指标
        if metric_id == 'SEAT_Z':
            # 座椅垂直加速度 RMS (ISO 2631-1 加权)
            weighted = ops.weighting.apply_weighting_z(az, sr)
            return np.sqrt(np.mean(weighted**2))
        
        elif metric_id == 'SEAT_XY':
            # 座椅水平加速度 RMS (ISO 2631-1 加权)
            xy = ops.vector.synthesize_xy(ax, ay)
            weighted = ops.weighting.apply_weighting_xy(xy, sr)
            return np.sqrt(np.mean(weighted**2))
        
        elif metric_id == 'VDV_Z':
            # 垂直振动剂量值 (VDV = (∫a(t)^4 dt)^(1/4))
            vdv = np.power(np.mean(az**4) * len(az)/sr, 0.25)
            return float(vdv)
        
        elif metric_id == 'TR_Z':
            # 垂直传递率 (简化)
            floor_accel = data_window.get('floor_accel', None)
            if floor_accel is not None and len(floor_accel) > 0 and np.std(floor_accel) > 0:
                return float(np.std(az) / np.std(floor_accel))
            # 无地板数据时返回无效标记
            return np.nan
        
        elif metric_id == 'AW_Z':
            # 垂直加权加速度
            weighted = ops.weighting.apply_weighting_z(az, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'AW_XY':
            # 水平加权加速度
            xy = ops.vector.synthesize_xy(ax, ay)
            weighted = ops.weighting.apply_weighting_xy(xy, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'OVTV':
            # 总体振动值 (简化)
            total = ops.vector.synthesize(ax, ay, az)
            return float(np.power(np.mean(total**4) * len(total)/sr, 0.25))
        
        elif metric_id == 'R_FACTOR':
            # R因子 (简化)
            xy = ops.vector.synthesize_xy(ax, ay)
            return float(np.std(xy) / (np.std(az) + 0.001))
        
        # 新增瞬态指标 - 冲击类
        elif metric_id == 'HIC15':
            # 头部损伤准则 HIC15 (标准 15ms)
            total_accel = ops.vector.synthesize(ax, ay, az)
            if len(total_accel) > 0:
                dt = 1.0 / sr
                n_15 = int(0.015 / dt)  # 15ms (修正)
                if n_15 < 2:
                    return 0.0
                max_hic = 0.0
                
                for i in range(len(total_accel) - n_15 + 1):
                    segment = total_accel[i:i+n_15]
                    mean_a = np.mean(segment)
                    # mean_a 单位为 g
                    hic = mean_a ** 2.5 * 0.015  # 15ms (修正)
                    max_hic = max(max_hic, hic)
                
                return float(max_hic)
            return 0.0
        
        elif metric_id == 'ACC_H_PEAK':
            # 头部加速度峰值
            head_accel = ops.vector.synthesize(ax, ay, az)
            return float(np.max(np.abs(head_accel)))
        
        elif metric_id == 'JERK_H':
            # 头部冲击度 (jerk = da/dt)
            total_accel = ops.vector.synthesize(ax, ay, az)
            if len(total_accel) > 1:
                jerk = np.diff(total_accel) * sr
                return float(np.max(np.abs(jerk)))
            return 0.0
        
        # SRS指标
        elif metric_id.startswith('SRS_'):
            srs_result = ops.srs.compute(az, sr)
            srs_features = ops.srs.extract_features(srs_result)
            if metric_id == 'SRS_MRS':
                return srs_features.get('SRS_MRS', 0.0)
            elif metric_id == 'SRS_Q':
                return srs_features.get('SRS_Q', 0.0)
            elif metric_id == 'SRS_PV':
                return srs_features.get('SRS_PV', 0.0)
            elif metric_id == 'SRS_ATT':
                return srs_features.get('SRS_ATT', 0.0)
        
        # 疲劳指标
        elif metric_id == 'RFC_CC':
            rf_result = ops.rainflow.count(az)
            return float(rf_result.get('RFC_CC', 0.0))
        
        elif metric_id.startswith('FDS_'):
            rf_result = ops.rainflow.count(az)
            fds_result = ops.fds.compute(rf_result)
            if metric_id == 'FDS_D':
                return fds_result.get('FDS_D', 0.0)
            elif metric_id == 'FDS_R':
                return fds_result.get('FDS_R', 0.0)
        
        # STFT时频指标
        elif metric_id.startswith('STFT_'):
            stft_result = ops.stft.compute(az, sr)
            stft_features = ops.stft.extract_features(stft_result)
            if metric_id == 'STFT_FC':
                return stft_features.get('STFT_FC', 0.0)
            elif metric_id == 'STFT_KT':
                return stft_features.get('STFT_KT', 0.0)
            elif metric_id == 'STFT_CE':
                return stft_features.get('STFT_CE', 0.0)
        
        elif metric_id == 'ACC_RMS':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.sqrt(np.mean(total**2)))
        
        elif metric_id == 'ACC_PEAK':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.max(total))
        
        # 结构指标
        elif metric_id == 'DISP_TR':
            if len(az) > 0:
                disp = self.operator_system.integration.integrate_to_displacement(az, sr)
                return float(np.max(np.abs(disp)))
            return 0.0
        
        return 0.0
    
    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """
        计算总体评分
        
        Args:
            metrics: 指标结果字典
            
        Returns:
            总体评分 (0-100)
        """
        if not metrics:
            return 0.0
        
        # 简化评分: 基于主要指标的加权平均
        weights = {
            'SEAT_Z': 0.15,
            'SEAT_XY': 0.10,
            'VDV_Z': 0.15,
            'AW_Z': 0.10,
            'HIC15': 0.10,
            'ACC_H_PEAK': 0.10,
            'FDS_D': 0.10,
            'R_FACTOR': 0.10,
            'ACC_RMS': 0.05,
            'ACC_PEAK': 0.05,
        }
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for metric_id, weight in weights.items():
            if metric_id in metrics:
                # 归一化到0-100分数 (简化)
                value = metrics[metric_id]
                # 假设越小越好的指标，反向评分
                normalized_score = max(0.0, min(100.0, 100.0 - value * 10.0))
                weighted_score += normalized_score * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_score / total_weight
        return 50.0
    
    def _assess_risk(self, metrics: Dict[str, float]) -> RiskLevel:
        """
        评估风险等级
        
        Args:
            metrics: 指标结果字典
            
        Returns:
            风险等级
        """
        # 简化风险评估逻辑
        hic = metrics.get('HIC15', 0.0)
        acc_peak = metrics.get('ACC_H_PEAK', 0.0)
        fds = metrics.get('FDS_D', 0.0)
        
        if hic > 1000 or acc_peak > 20 or fds > 0.5:
            return RiskLevel.DANGER
        elif hic > 500 or acc_peak > 10 or fds > 0.2:
            return RiskLevel.WARNING
        elif hic > 100 or acc_peak > 5 or fds > 0.05:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE
    
    def _result_to_dict(self, result: EvaluationResult) -> Dict[str, Any]:
        """
        将结果对象转换为字典
        
        Args:
            result: 评测结果对象
            
        Returns:
            结果字典
        """
        return {
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'metrics': result.metrics,
            'overall_score': result.overall_score,
            'risk_level': result.risk_level.value,
            'metadata': result.metadata
        }
