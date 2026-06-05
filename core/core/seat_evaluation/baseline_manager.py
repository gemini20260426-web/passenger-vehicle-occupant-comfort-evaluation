#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基线管理与历史对比模块 (F4: 实时vs历史对比模式)

提供:
- 基线采集与管理 (多基线支持)
- 实时vs历史对比 (改善/退化百分比)
- 趋势追踪 (多时间点对比)
- 基线稳定性评估
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BaselineSnapshot:
    """基线快照"""
    id: str
    label: str
    timestamp: float
    description: str = ''
    metrics: Dict[str, float] = field(default_factory=dict)
    n_samples: int = 0
    condition: str = 'unknown'  # experimental / control / mixed
    tags: List[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """对比结果"""
    metric_id: str
    baseline_value: float
    current_value: float
    change_pct: float  # 变化百分比 (正=改善, 负=退化)
    change_absolute: float  # 绝对变化量
    direction: str  # improved / degraded / stable
    significance: str  # significant / moderate / negligible
    z_score: float  # 偏离基线标准差的倍数


class BaselineManager:
    """基线管理器 (F4)

    功能:
    - 多基线采集与存储
    - 实时vs历史对比
    - 改善/退化百分比计算
    - 趋势追踪
    - 基线稳定性评估
    """

    DEFAULT_IMPROVEMENT_METRICS = {
        # 指标ID: direction (lower_is_better / higher_is_better)
        'SEAT_Z': 'lower_is_better',
        'SEAT_XY': 'lower_is_better',
        'VDV_Z': 'lower_is_better',
        'VDV_XY': 'lower_is_better',
        'AW_Z': 'lower_is_better',
        'AW_XY': 'lower_is_better',
        'OVTV': 'lower_is_better',
        'HIC15': 'lower_is_better',
        'ACC_H_PEAK': 'lower_is_better',
        'JERK_H': 'lower_is_better',
        'S_D': 'lower_is_better',
        'DISP_HR': 'lower_is_better',
        'BAND_ATT_01_05': 'higher_is_better',
        'BAND_ATT_05_1': 'higher_is_better',
        'BAND_ATT_1_5': 'higher_is_better',
        'R_FACTOR': 'higher_is_better',
    }

    def __init__(self):
        self._baselines: Dict[str, BaselineSnapshot] = {}
        self._current_metrics: Dict[str, float] = {}
        self._history: Dict[str, List[float]] = {}  # {metric_id: [values over time]}
        self._baseline_std: Dict[str, Dict[str, float]] = {}  # {bid: {metric_id: std}}

    def capture_baseline(self, metrics: Dict[str, float], label: str = '',
                         description: str = '', condition: str = 'unknown',
                         tags: List[str] = None) -> BaselineSnapshot:
        """采集基线数据

        Args:
            metrics: 指标字典 {metric_id: value}
            label: 基线标签
            description: 描述
            condition: 条件 (experimental/control)
            tags: 标签列表

        Returns:
            BaselineSnapshot: 基线快照
        """
        bid = f"BL_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if label:
            bid = label.replace(' ', '_')

        baseline = BaselineSnapshot(
            id=bid,
            label=label or f'Baseline_{len(self._baselines) + 1}',
            timestamp=datetime.now().timestamp(),
            description=description,
            metrics=dict(metrics),
            n_samples=1,
            condition=condition,
            tags=tags or []
        )

        self._baselines[bid] = baseline

        # 初始化基线标准差 (后续通过多次采集累积)
        self._baseline_std[bid] = {k: 0.0 for k in metrics}

        logger.info(f"基线已采集: {bid} ({len(metrics)} metrics)")
        return baseline

    def update_baseline(self, baseline_id: str, metrics: Dict[str, float]):
        """更新已有基线 (多次采集累积)

        使用Welford在线算法更新均值和方差
        """
        if baseline_id not in self._baselines:
            logger.warning(f"基线不存在: {baseline_id}")
            return

        bl = self._baselines[baseline_id]
        old_n = bl.n_samples
        new_n = old_n + 1

        for metric_id, new_val in metrics.items():
            old_mean = bl.metrics.get(metric_id, 0.0)
            old_std = self._baseline_std.get(baseline_id, {}).get(metric_id, 0.0)

            # Welford 在线更新
            if metric_id in bl.metrics:
                delta = new_val - old_mean
                bl.metrics[metric_id] = old_mean + delta / new_n
                # 更新方差累计
                delta2 = new_val - bl.metrics[metric_id]
                if baseline_id not in self._baseline_std:
                    self._baseline_std[baseline_id] = {}
                old_var = old_std ** 2
                new_var = ((old_n - 1) * old_var + delta * delta2) / new_n if new_n > 1 else 0
                self._baseline_std[baseline_id][metric_id] = np.sqrt(max(0, new_var))
            else:
                bl.metrics[metric_id] = new_val

        bl.n_samples = new_n
        logger.debug(f"基线更新: {baseline_id} (n={new_n})")

    def compare_with_baseline(self, baseline_id: str,
                              current_metrics: Dict[str, float] = None,
                              direction_map: Dict[str, str] = None
                              ) -> Dict[str, ComparisonResult]:
        """与基线对比

        Args:
            baseline_id: 基线ID
            current_metrics: 当前指标值, 为None则使用set_current_metrics设置的值
            direction_map: 指标方向映射 {metric_id: 'lower_is_better'/'higher_is_better'}

        Returns:
            {metric_id: ComparisonResult}: 对比结果
        """
        if baseline_id not in self._baselines:
            logger.warning(f"基线不存在: {baseline_id}")
            return {}

        baseline = self._baselines[baseline_id]
        current = current_metrics or self._current_metrics
        direction_map = direction_map or self.DEFAULT_IMPROVEMENT_METRICS

        results = {}
        for metric_id, curr_val in current.items():
            base_val = baseline.metrics.get(metric_id)
            if base_val is None:
                continue

            # 变化百分比
            if abs(base_val) > 1e-6:
                change_pct = round((curr_val - base_val) / abs(base_val) * 100, 2)
            else:
                change_pct = 0.0

            change_abs = curr_val - base_val

            # 方向判断
            direction = self._get_direction(metric_id, direction_map)
            if direction == 'lower_is_better':
                # 降低 = 改善
                if change_pct < -5:
                    direction_label = 'improved'
                elif change_pct > 5:
                    direction_label = 'degraded'
                else:
                    direction_label = 'stable'
            elif direction == 'higher_is_better':
                if change_pct > 5:
                    direction_label = 'improved'
                elif change_pct < -5:
                    direction_label = 'degraded'
                else:
                    direction_label = 'stable'
            else:
                direction_label = 'stable'

            # 显著性
            abs_change = abs(change_pct)
            if abs_change > 20:
                significance = 'significant'
            elif abs_change > 10:
                significance = 'moderate'
            else:
                significance = 'negligible'

            # Z-score (偏离基线标准差)
            std_val = self._baseline_std.get(baseline_id, {}).get(metric_id, 0.0)
            if std_val > 1e-6:
                z_score = change_abs / std_val
            else:
                z_score = 0.0

            results[metric_id] = ComparisonResult(
                metric_id=metric_id,
                baseline_value=base_val,
                current_value=curr_val,
                change_pct=change_pct,
                change_absolute=change_abs,
                direction=direction_label,
                significance=significance,
                z_score=round(z_score, 2)
            )

        return results

    def compare_multi_baseline(self, current_metrics: Dict[str, float] = None,
                               direction_map: Dict[str, str] = None
                               ) -> Dict[str, Dict[str, ComparisonResult]]:
        """与所有基线对比"""
        current = current_metrics or self._current_metrics
        results = {}
        for bid in self._baselines:
            results[bid] = self.compare_with_baseline(bid, current, direction_map)
        return results

    def get_trend(self, metric_id: str, baseline_id: str = None,
                  n_points: int = 10) -> List[Dict[str, Any]]:
        """获取指标趋势数据

        Returns:
            [{timestamp, value, baseline_value, change_pct}, ...]
        """
        history = self._history.get(metric_id, [])
        if not history:
            return []

        base_val = None
        if baseline_id and baseline_id in self._baselines:
            base_val = self._baselines[baseline_id].metrics.get(metric_id)

        trend = []
        for i, val in enumerate(history[-n_points:]):
            point = {
                'index': i,
                'value': val,
                'baseline_value': base_val
            }
            if base_val is not None and abs(base_val) > 1e-6:
                point['change_pct'] = round((val - base_val) / abs(base_val) * 100, 2)
            else:
                point['change_pct'] = 0.0
            trend.append(point)

        return trend

    def set_current_metrics(self, metrics: Dict[str, float]):
        """设置当前指标值并记录历史"""
        self._current_metrics = dict(metrics)
        for metric_id, value in metrics.items():
            if metric_id not in self._history:
                self._history[metric_id] = []
            self._history[metric_id].append(value)

    def get_improvement_summary(self, baseline_id: str = None,
                                current_metrics: Dict[str, float] = None
                                ) -> Dict[str, Any]:
        """获取改善/退化摘要"""
        if baseline_id is None and self._baselines:
            baseline_id = list(self._baselines.keys())[-1]

        results = self.compare_with_baseline(baseline_id, current_metrics)

        improved = []
        degraded = []
        stable = []
        significant_changes = []

        for metric_id, result in results.items():
            if result.direction == 'improved':
                improved.append(metric_id)
            elif result.direction == 'degraded':
                degraded.append(metric_id)
            else:
                stable.append(metric_id)

            if result.significance == 'significant':
                significant_changes.append({
                    'metric_id': metric_id,
                    'change_pct': result.change_pct,
                    'direction': result.direction
                })

        # 总体改善率
        total = len(results)
        improvement_rate = len(improved) / total * 100 if total > 0 else 0

        return {
            'baseline_id': baseline_id,
            'total_metrics': total,
            'improved_count': len(improved),
            'degraded_count': len(degraded),
            'stable_count': len(stable),
            'improvement_rate_pct': round(improvement_rate, 1),
            'improved_metrics': improved,
            'degraded_metrics': degraded,
            'significant_changes': significant_changes
        }

    def assess_baseline_stability(self, baseline_id: str) -> Dict[str, Any]:
        """评估基线稳定性

        Returns:
            {stability: 'stable'/'moderate'/'unstable', cv_summary: {...}}
        """
        if baseline_id not in self._baselines:
            return {'stability': 'unknown', 'reason': 'baseline not found'}

        bl = self._baselines[baseline_id]
        if bl.n_samples < 2:
            return {'stability': 'unknown', 'reason': 'insufficient samples (need >=2)'}

        cv_values = []
        for metric_id, std_val in self._baseline_std.get(baseline_id, {}).items():
            mean_val = bl.metrics.get(metric_id, 0)
            if abs(mean_val) > 1e-6:
                cv = std_val / abs(mean_val) * 100
                cv_values.append(cv)

        if not cv_values:
            return {'stability': 'unknown', 'reason': 'no valid metrics'}

        avg_cv = np.mean(cv_values)
        if avg_cv < 10:
            stability = 'stable'
        elif avg_cv < 25:
            stability = 'moderate'
        else:
            stability = 'unstable'

        return {
            'stability': stability,
            'avg_cv_pct': round(avg_cv, 2),
            'n_samples': bl.n_samples,
            'n_metrics': len(cv_values),
            'high_cv_metrics': [f"CV={cv:.1f}%" for cv in cv_values if cv > 30]
        }

    def get_baseline_list(self) -> List[Dict[str, Any]]:
        """获取所有基线列表"""
        return [
            {
                'id': bl.id,
                'label': bl.label,
                'timestamp': bl.timestamp,
                'description': bl.description,
                'n_samples': bl.n_samples,
                'n_metrics': len(bl.metrics),
                'condition': bl.condition,
                'tags': bl.tags
            }
            for bl in self._baselines.values()
        ]

    def delete_baseline(self, baseline_id: str) -> bool:
        """删除基线"""
        if baseline_id in self._baselines:
            del self._baselines[baseline_id]
            self._baseline_std.pop(baseline_id, None)
            logger.info(f"基线已删除: {baseline_id}")
            return True
        return False

    def clear(self):
        """清空所有数据"""
        self._baselines.clear()
        self._current_metrics.clear()
        self._history.clear()
        self._baseline_std.clear()
        logger.info("BaselineManager数据已清空")

    @staticmethod
    def _get_direction(metric_id: str, direction_map: Dict[str, str]) -> str:
        """获取指标改进方向"""
        return direction_map.get(metric_id, 'lower_is_better')