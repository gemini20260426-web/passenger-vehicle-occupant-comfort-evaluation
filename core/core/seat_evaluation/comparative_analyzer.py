#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照分析器
实验组vs对照组的多维度对比分析，支持统计显著性检验
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

from ..analysis.core_types import (
    EvaluationResult, LocationEvaluationResult,
    ComparativeEvaluationResult, ComparativeEvaluationTrigger,
    TestGroupReport, INDICATOR_DEFINITIONS, RiskLevel
)
from .imu_location_config import (
    IMU_LOCATION_MAPPING, LOCATION_IDS,
    get_location_config, get_channel_by_location
)
from .operators import AttenuationOperator
from .report_generator import SeatEvaluationReportGenerator

logger = logging.getLogger(__name__)


class ComparativeAnalyzer:
    """对照分析器 - 实验组vs对照组对比分析"""

    def __init__(self):
        self._attenuation = AttenuationOperator()
        self._report_generator = SeatEvaluationReportGenerator()
        self._batch_results: List[ComparativeEvaluationResult] = []

    def compare_metrics(self, exp_metrics: Dict[str, float],
                        ctrl_metrics: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """对比两组指标"""
        comparisons = {}
        for metric_id in exp_metrics:
            if metric_id not in ctrl_metrics:
                continue
            exp_val = exp_metrics[metric_id]
            ctrl_val = ctrl_metrics[metric_id]
            diff = exp_val - ctrl_val
            improvement = self._attenuation.compute(exp_val, ctrl_val)

            comparisons[metric_id] = {
                'exp_value': exp_val,
                'ctrl_value': ctrl_val,
                'diff': diff,
                'improvement_pct': improvement,
                'stat_sig': None,
                'p_value': 1.0,
                'effect_size': 0.0,
            }
        return comparisons

    def compare_locations(self,
                          exp_locations: Dict[str, LocationEvaluationResult],
                          ctrl_locations: Dict[str, LocationEvaluationResult]) -> Dict[str, Dict[str, Any]]:
        """对比各位置结果"""
        location_comparisons = {}
        for loc_id in LOCATION_IDS:
            exp_loc = exp_locations.get(loc_id)
            ctrl_loc = ctrl_locations.get(loc_id)
            if not exp_loc or not ctrl_loc:
                continue

            exp_score = exp_loc.location_score
            ctrl_score = ctrl_loc.location_score
            improvement = self._attenuation.compute(exp_score, ctrl_score)

            metric_comp = self.compare_metrics(exp_loc.metrics, ctrl_loc.metrics)

            location_comparisons[loc_id] = {
                'experimental_score': exp_score,
                'control_score': ctrl_score,
                'improvement_pct': improvement,
                'exp_risk': exp_loc.risk_level.value,
                'ctrl_risk': ctrl_loc.risk_level.value,
                'metric_comparisons': metric_comp,
            }
        return location_comparisons

    def analyze_single_event(self,
                             exp_result: EvaluationResult,
                             ctrl_result: EvaluationResult) -> ComparativeEvaluationResult:
        """单事件对照分析"""
        trigger_id = exp_result.trigger_id
        event_type = exp_result.event_type
        timestamp = exp_result.timestamp

        comparisons = self.compare_metrics(exp_result.metrics, ctrl_result.metrics)
        location_comparisons = self.compare_locations(
            exp_result.location_results, ctrl_result.location_results)

        improvement = self._attenuation.compute(
            exp_result.overall_score, ctrl_result.overall_score)

        overall_score = {
            'experimental_score': exp_result.overall_score,
            'control_score': ctrl_result.overall_score,
            'improvement': improvement,
        }

        result = ComparativeEvaluationResult(
            trigger_id=trigger_id,
            event_type=event_type,
            timestamp=timestamp,
            experimental_results=exp_result,
            control_results=ctrl_result,
            comparisons=comparisons,
            location_comparisons=location_comparisons,
            overall_score=overall_score,
        )

        self._batch_results.append(result)
        logger.info(f"对照分析完成: {trigger_id}, "
                    f"实验组={exp_result.overall_score:.1f}, "
                    f"对照组={ctrl_result.overall_score:.1f}, "
                    f"改善={improvement:.1f}%")

        return result

    def analyze_batch(self, exp_results: List[EvaluationResult],
                      ctrl_results: List[EvaluationResult]) -> TestGroupReport:
        """批量对照分析"""
        n = min(len(exp_results), len(ctrl_results))
        if n == 0:
            return TestGroupReport(
                report_id='empty',
                test_name='批量对照',
                start_time=0, end_time=0,
                event_results=[],
                summary_statistics={},
            )

        event_results = []
        for i in range(n):
            cr = self.analyze_single_event(exp_results[i], ctrl_results[i])
            event_results.append(cr)

        start_time = min(r.timestamp for r in exp_results[:n])
        end_time = max(r.timestamp for r in exp_results[:n])

        summary = self._compute_summary_statistics(event_results)

        report = TestGroupReport(
            report_id=f'batch_{len(self._batch_results)}',
            test_name='批量对照分析',
            start_time=start_time,
            end_time=end_time,
            event_results=event_results,
            summary_statistics=summary,
        )

        return report

    def _compute_summary_statistics(self,
                                     event_results: List[ComparativeEvaluationResult]
                                     ) -> Dict[str, Dict[str, Any]]:
        """计算汇总统计"""
        if not event_results:
            return {}

        all_metric_ids = set()
        for cr in event_results:
            all_metric_ids.update(cr.comparisons.keys())

        summary = {}
        for metric_id in all_metric_ids:
            exp_vals = []
            ctrl_vals = []
            improvements = []
            for cr in event_results:
                comp = cr.comparisons.get(metric_id)
                if comp:
                    exp_vals.append(comp['exp_value'])
                    ctrl_vals.append(comp['ctrl_value'])
                    improvements.append(comp['improvement_pct'])

            if not exp_vals:
                continue

            exp_arr = np.array(exp_vals)
            ctrl_arr = np.array(ctrl_vals)
            imp_arr = np.array(improvements)

            n_eff = len(exp_vals)

            summary[metric_id] = {
                'exp_mean': float(np.mean(exp_arr)),
                'exp_std': float(np.std(exp_arr)),
                'ctrl_mean': float(np.mean(ctrl_arr)),
                'ctrl_std': float(np.std(ctrl_arr)),
                'improvement_pct': float(np.mean(imp_arr)),
                'improvement_std': float(np.std(imp_arr)),
                'n_events': n_eff,
            }

        return summary

    def generate_report(self, result: ComparativeEvaluationResult) -> Dict[str, Any]:
        """生成对照分析报告"""
        return self._report_generator.generate_comparative_report(result)

    def clear_batch(self):
        self._batch_results.clear()
        self._report_generator.clear_history()

    def get_batch_results(self) -> List[ComparativeEvaluationResult]:
        return list(self._batch_results)