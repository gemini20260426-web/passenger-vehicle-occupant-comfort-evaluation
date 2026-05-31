#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照分析引擎（重构版）
支持实验组vs对照组的多位置对比分析
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal

from .engine_v2 import MultiChannelSeatEvaluationEngine
from .imu_location_config import (
    IMU_LOCATION_MAPPING, LOCATION_IDS,
    get_location_config, get_channel_by_location
)
from ..analysis.core_types import (
    EvaluationTrigger, EvaluationResult, LocationEvaluationResult,
    ComparativeEvaluationResult, RiskLevel
)

logger = logging.getLogger(__name__)


class MultiChannelComparativeEngine(QObject):
    """多通道对照分析引擎"""
    
    comparison_started = Signal(dict)
    comparison_completed = Signal(dict)
    metric_comparison_updated = Signal(dict)
    location_comparison_ready = Signal(dict)
    
    def __init__(self, config_manager=None, data_storage=None):
        super().__init__()
        self.config_manager = config_manager
        self.data_storage = data_storage
        
        # 初始化座椅评测引擎（实验组和对照组各一个）
        self.experimental_engine = MultiChannelSeatEvaluationEngine(config_manager, data_storage)
        self.control_engine = MultiChannelSeatEvaluationEngine(config_manager, data_storage)
        
        # 历史结果缓存
        self.results_cache: Dict[str, ComparativeEvaluationResult] = {}
        
        logger.info("多通道对照分析引擎初始化完成")
    
    def compare_groups(self, trigger: Dict[str, Any]) -> Optional[ComparativeEvaluationResult]:
        """
        对比两组数据
        
        Args:
            trigger: 对比触发器字典
        
        Returns:
            ComparativeEvaluationResult 对照结果对象
        """
        try:
            self.comparison_started.emit(trigger)
            
            trigger_id = trigger.get('event_id', trigger.get('comparison_id', ''))
            event_type = trigger.get('event_type', '')
            timestamp = trigger.get('timestamp', 0.0)
            metrics = trigger.get('metrics', [])
            multi_channel_data = trigger.get('multi_channel_data', {})
            locations = trigger.get('locations', LOCATION_IDS)
            
            # 分别评测两组
            exp_result = self._evaluate_group(
                multi_channel_data, metrics, locations, 'experimental'
            )
            ctrl_result = self._evaluate_group(
                multi_channel_data, metrics, locations, 'control'
            )
            
            if not exp_result or not ctrl_result:
                logger.warning(f"评测结果不完整: {trigger_id}")
                return None
            
            # 计算对比指标
            comparisons = self._compute_comparison_metrics(
                exp_result, ctrl_result
            )
            
            # 计算位置级对比
            location_comparisons = self._compute_location_comparisons(
                exp_result, ctrl_result
            )
            
            # 计算总体评分
            overall_score = {
                'experimental_score': exp_result.overall_score,
                'control_score': ctrl_result.overall_score,
                'improvement': self._calculate_improvement(
                    exp_result.overall_score, ctrl_result.overall_score
                )
            }
            
            # 创建对照结果
            result = ComparativeEvaluationResult(
                trigger_id=trigger_id,
                event_type=event_type,
                timestamp=timestamp,
                experimental_results=exp_result,
                control_results=ctrl_result,
                comparisons=comparisons,
                location_comparisons=location_comparisons,
                overall_score=overall_score
            )
            
            # 缓存结果
            self.results_cache[trigger_id] = result
            
            # 发送信号
            self.comparison_completed.emit(self._result_to_dict(result))
            
            logger.info(f"对照分析完成: {trigger_id}, 总体改善: {overall_score['improvement']:.1f}%")
            
            return result
            
        except Exception as e:
            logger.error(f"对照分析失败: {e}", exc_info=True)
            return None
    
    def _evaluate_group(self, multi_channel_data: Dict[str, Any],
                      metrics: List[str], locations: List[str],
                      group_tag: str) -> Optional[EvaluationResult]:
        """
        评测单组数据
        
        Args:
            multi_channel_data: 多通道数据
            metrics: 指标列表
            locations: 位置列表
            group_tag: 组标签
        
        Returns:
            EvaluationResult
        """
        try:
            group_channels = {}
            missing_channels = []

            for location_id in locations:
                channel_id = get_channel_by_location(location_id, group_tag)
                if channel_id and channel_id in multi_channel_data:
                    group_channels[channel_id] = multi_channel_data[channel_id]
                elif channel_id:
                    fallback_channel = get_channel_by_location(location_id, 'experimental')
                    if fallback_channel and fallback_channel in multi_channel_data:
                        group_channels[channel_id] = multi_channel_data[fallback_channel]
                        missing_channels.append(channel_id)
                        logger.debug(f"对照组通道 {channel_id} 不存在，回退使用实验组通道 {fallback_channel}")

            if not group_channels:
                logger.warning(f"{group_tag} 组没有可用通道数据")
                return None

            eval_trigger = {
                'trigger_id': f'{group_tag}_eval',
                'event_id': f'{group_tag}_eval',
                'event_type': 'single_evaluation',
                'source_behavior': '',
                'timestamp': 0.0,
                'metrics': metrics,
                'data_window': {'pre': 0.5, 'post': 1.5},
                'multi_channel_data': group_channels,
                'locations': locations,
                'group_tag': group_tag
            }

            engine = self.experimental_engine if group_tag == 'experimental' else self.control_engine

            result = engine.evaluate_by_event(eval_trigger)

            if result and missing_channels:
                if not hasattr(result, 'metadata'):
                    result.metadata = {}
                result.metadata['fallback_channels'] = missing_channels
                result.metadata['single_source_warning'] = True

            return result
            
        except Exception as e:
            logger.error(f"评测 {group_tag} 组失败: {e}")
            return None
    
    def _compute_comparison_metrics(self, exp_result: EvaluationResult,
                                  ctrl_result: EvaluationResult) -> Dict[str, Dict[str, Any]]:
        """
        计算对比指标
        
        Args:
            exp_result: 实验组结果
            ctrl_result: 对照组结果
        
        Returns:
            对比指标字典
        """
        comparisons = {}
        
        # 合并两组的指标
        all_metric_ids = set(exp_result.metrics.keys()) | set(ctrl_result.metrics.keys())
        
        for metric_id in all_metric_ids:
            exp_val = exp_result.metrics.get(metric_id, 0.0)
            ctrl_val = ctrl_result.metrics.get(metric_id, 0.0)
            
            # 计算差异
            diff = exp_val - ctrl_val
            
            # 计算改善百分比（假设越小越好）
            if ctrl_val != 0:
                improvement_pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
            else:
                improvement_pct = 0.0 if exp_val == 0 else 100.0 if exp_val < ctrl_val else -100.0
            
            comparisons[metric_id] = {
                'experimental': exp_val,
                'control': ctrl_val,
                'diff': diff,
                'improvement_pct': improvement_pct,
                'improved': exp_val < ctrl_val
            }
            
            # 发送指标对比更新信号
            self.metric_comparison_updated.emit({
                'metric_id': metric_id,
                'data': comparisons[metric_id]
            })
        
        return comparisons
    
    def _compute_location_comparisons(self, exp_result: EvaluationResult,
                                     ctrl_result: EvaluationResult) -> Dict[str, Dict[str, Any]]:
        """
        计算位置级对比
        
        Args:
            exp_result: 实验组结果
            ctrl_result: 对照组结果
        
        Returns:
            位置对比字典
        """
        location_comparisons = {}
        
        # 合并两组的位置
        all_locations = set(exp_result.location_results.keys()) | set(ctrl_result.location_results.keys())
        
        for location_id in all_locations:
            exp_loc_result = exp_result.location_results.get(location_id)
            ctrl_loc_result = ctrl_result.location_results.get(location_id)
            
            if not exp_loc_result or not ctrl_loc_result:
                continue
            
            # 计算位置指标对比
            location_metrics = {}
            all_loc_metric_ids = set(exp_loc_result.metrics.keys()) | set(ctrl_loc_result.metrics.keys())
            
            for metric_id in all_loc_metric_ids:
                exp_val = exp_loc_result.metrics.get(metric_id, 0.0)
                ctrl_val = ctrl_loc_result.metrics.get(metric_id, 0.0)
                
                if ctrl_val != 0:
                    improvement_pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
                else:
                    improvement_pct = 0.0
                
                location_metrics[metric_id] = {
                    'experimental': exp_val,
                    'control': ctrl_val,
                    'improvement_pct': improvement_pct,
                    'improved': exp_val < ctrl_val
                }
            
            # 计算位置评分对比
            exp_score = exp_loc_result.location_score
            ctrl_score = ctrl_loc_result.location_score
            improvement_pct = self._calculate_improvement(exp_score, ctrl_score)
            
            location_comparison = {
                'location_id': location_id,
                'location_name': exp_loc_result.location_name,
                'experimental_score': exp_score,
                'control_score': ctrl_score,
                'improvement_pct': improvement_pct,
                'improved': exp_score > ctrl_score,
                'metrics': location_metrics
            }
            
            location_comparisons[location_id] = location_comparison
            
            # 发送位置对比更新信号
            self.location_comparison_ready.emit(location_comparison)
        
        return location_comparisons
    
    def _calculate_improvement(self, exp_score: float, ctrl_score: float) -> float:
        """
        计算改善百分比
        
        Args:
            exp_score: 实验组评分
            ctrl_score: 对照组评分
        
        Returns:
            改善百分比 (-100 到 +100)
        """
        if ctrl_score == 0:
            return 0.0
        
        improvement = ((exp_score - ctrl_score) / ctrl_score) * 100.0
        return float(np.clip(improvement, -100.0, 100.0))
    
    def _result_to_dict(self, result: ComparativeEvaluationResult) -> Dict[str, Any]:
        """
        将结果对象转换为字典
        
        Args:
            result: 对照结果对象
        
        Returns:
            结果字典
        """
        # 转换位置结果
        exp_loc_results = {}
        for loc_id, loc_result in result.experimental_results.location_results.items():
            exp_loc_results[loc_id] = {
                'location_id': loc_result.location_id,
                'location_name': loc_result.location_name,
                'channel_id': loc_result.channel_id,
                'metrics': loc_result.metrics,
                'location_score': loc_result.location_score,
                'risk_level': loc_result.risk_level.value
            }
        
        ctrl_loc_results = {}
        for loc_id, loc_result in result.control_results.location_results.items():
            ctrl_loc_results[loc_id] = {
                'location_id': loc_result.location_id,
                'location_name': loc_result.location_name,
                'channel_id': loc_result.channel_id,
                'metrics': loc_result.metrics,
                'location_score': loc_result.location_score,
                'risk_level': loc_result.risk_level.value
            }
        
        return {
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'experimental_results': {
                'metrics': result.experimental_results.metrics,
                'overall_score': result.experimental_results.overall_score,
                'risk_level': result.experimental_results.risk_level.value,
                'location_results': exp_loc_results
            },
            'control_results': {
                'metrics': result.control_results.metrics,
                'overall_score': result.control_results.overall_score,
                'risk_level': result.control_results.risk_level.value,
                'location_results': ctrl_loc_results
            },
            'comparisons': result.comparisons,
            'location_comparisons': result.location_comparisons,
            'overall_score': result.overall_score,
            'summary': self._generate_summary(result)
        }
    
    def _generate_summary(self, result: ComparativeEvaluationResult) -> str:
        """
        生成摘要文本
        
        Args:
            result: 对照结果
        
        Returns:
            摘要字符串
        """
        overall_improvement = result.overall_score.get('improvement', 0.0)
        
        if overall_improvement > 10:
            status = "显著提升"
        elif overall_improvement > 0:
            status = "有所改善"
        elif overall_improvement > -10:
            status = "基本持平"
        else:
            status = "有所下降"
        
        summary = f"总体表现: {status} (改善: {overall_improvement:.1f}%)\n"
        summary += f"实验组评分: {result.overall_score['experimental_score']:.1f} vs 对照组: {result.overall_score['control_score']:.1f}\n"
        
        # 列出位置改善
        improved_locations = []
        for loc_id, loc_comp in result.location_comparisons.items():
            if loc_comp.get('improved', False):
                improved_locations.append((loc_id, loc_comp.get('improvement_pct', 0.0)))
        
        if improved_locations:
            summary += f"\n改善位置 ({len(improved_locations)}个):\n"
            for loc_id, imp in sorted(improved_locations, key=lambda x: x[1], reverse=True):
                loc_config = get_location_config(loc_id)
                loc_name = loc_config.location_name_cn if loc_config else loc_id
                summary += f"  {loc_name}: +{imp:.1f}%\n"
        
        return summary
    
    def get_cached_result(self, trigger_id: str) -> Optional[ComparativeEvaluationResult]:
        """
        获取缓存的结果
        
        Args:
            trigger_id: 触发ID
        
        Returns:
            缓存的结果
        """
        return self.results_cache.get(trigger_id)
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.results_cache.clear()
        logger.info("对照分析缓存已清空")
