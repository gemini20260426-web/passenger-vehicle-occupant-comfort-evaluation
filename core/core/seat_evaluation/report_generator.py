#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测报告生成器
基于 ISO 2631-1 / SAE J211 标准的评测报告生成
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import numpy as np

from .metadata_registry import INDICATOR_DEFINITIONS
from ..analysis.core_types import (
    EvaluationResult, LocationEvaluationResult, RiskLevel,
    ComparativeEvaluationResult
)
from .imu_location_config import LOCATION_IDS, get_location_config

logger = logging.getLogger(__name__)

LOCATION_LABELS_CN = {
    'head': '头部眉心',
    'torso': '躯干T8',
    'seat_r': '座垫R点',
    'seat_bottom': '座椅底部',
    'sternum': '胸骨剑突',
}

GRADE_THRESHOLDS = [
    (90, 'A', '优秀'),
    (70, 'B', '良好'),
    (50, 'C', '一般'),
    (0,  'D', '差'),
]


class SeatEvaluationReportGenerator:
    """座椅评测报告生成器"""

    def __init__(self):
        self._report_history: List[Dict[str, Any]] = []

    def generate_single_event_report(self, result: EvaluationResult) -> Dict[str, Any]:
        """生成单事件评测报告"""
        location_details = {}
        for loc_id, loc_result in result.location_results.items():
            label = LOCATION_LABELS_CN.get(loc_id, loc_id)
            grade, grade_cn = self._get_grade(loc_result.location_score)
            metric_details = {}
            for metric_id, value in loc_result.metrics.items():
                metric_def = INDICATOR_DEFINITIONS.get(metric_id, {})
                metric_details[metric_id] = {
                    'value': round(value, 4),
                    'name': metric_def.get('name', metric_id),
                    'unit': metric_def.get('unit', ''),
                    'type': metric_def.get('type', ''),
                }
            location_details[loc_id] = {
                'label_cn': label,
                'channel_id': loc_result.channel_id,
                'score': round(loc_result.location_score, 2),
                'grade': grade,
                'grade_cn': grade_cn,
                'risk_level': loc_result.risk_level.value,
                'metrics': metric_details,
            }

        overall_grade, overall_grade_cn = self._get_grade(result.overall_score)

        report = {
            'report_type': 'single_event',
            'generated_at': datetime.now().isoformat(),
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'overall_score': round(result.overall_score, 2),
            'overall_grade': overall_grade,
            'overall_grade_cn': overall_grade_cn,
            'overall_risk': result.risk_level.value,
            'location_count': len(result.location_results),
            'locations': location_details,
            'metadata': result.metadata,
        }

        self._report_history.append(report)
        return report

    def generate_comparative_report(self, result: ComparativeEvaluationResult) -> Dict[str, Any]:
        """生成对照评测报告"""
        exp_report = self.generate_single_event_report(result.experimental_results)
        ctrl_report = self.generate_single_event_report(result.control_results)

        location_comparisons = {}
        for loc_id in LOCATION_IDS:
            exp_loc = exp_report['locations'].get(loc_id, {})
            ctrl_loc = ctrl_report['locations'].get(loc_id, {})
            if exp_loc and ctrl_loc:
                improvement = ((exp_loc['score'] - ctrl_loc['score'])
                               / max(ctrl_loc['score'], 0.01) * 100)
                location_comparisons[loc_id] = {
                    'label_cn': LOCATION_LABELS_CN.get(loc_id, loc_id),
                    'exp_score': exp_loc['score'],
                    'ctrl_score': ctrl_loc['score'],
                    'improvement_pct': round(improvement, 1),
                }

        metric_comparisons = {}
        for metric_id, comp in result.comparisons.items():
            metric_def = INDICATOR_DEFINITIONS.get(metric_id, {})
            metric_comparisons[metric_id] = {
                'name': metric_def.get('name', metric_id),
                'unit': metric_def.get('unit', ''),
                'diff': round(comp.get('diff', 0), 4),
                'improvement_pct': round(comp.get('improvement_pct', 0), 1),
                'stat_sig': comp.get('stat_sig', False),
                'p_value': round(comp.get('p_value', 1.0), 4),
                'effect_size': round(comp.get('effect_size', 0), 4),
            }

        overall_grade, overall_grade_cn = self._get_grade(
            result.overall_score.get('experimental_score', 50))

        report = {
            'report_type': 'comparative',
            'generated_at': datetime.now().isoformat(),
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'experimental': exp_report,
            'control': ctrl_report,
            'overall_score': result.overall_score,
            'overall_grade': overall_grade,
            'overall_grade_cn': overall_grade_cn,
            'location_comparisons': location_comparisons,
            'metric_comparisons': metric_comparisons,
        }

        self._report_history.append(report)
        return report

    def generate_batch_summary(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """生成批量评测汇总报告"""
        if not results:
            return {'report_type': 'batch_summary', 'event_count': 0}

        scores = [r.overall_score for r in results]
        risks = [r.risk_level for r in results]

        event_type_counts = {}
        for r in results:
            et = r.event_type or 'unknown'
            event_type_counts[et] = event_type_counts.get(et, 0) + 1

        location_avg_scores = {}
        for loc_id in LOCATION_IDS:
            loc_scores = []
            for r in results:
                loc = r.location_results.get(loc_id)
                if loc:
                    loc_scores.append(loc.location_score)
            if loc_scores:
                location_avg_scores[loc_id] = {
                    'label_cn': LOCATION_LABELS_CN.get(loc_id, loc_id),
                    'avg_score': round(np.mean(loc_scores), 2),
                    'min_score': round(np.min(loc_scores), 2),
                    'max_score': round(np.max(loc_scores), 2),
                    'count': len(loc_scores),
                }

        metric_avg = {}
        for r in results:
            for metric_id, value in r.metrics.items():
                if metric_id not in metric_avg:
                    metric_avg[metric_id] = []
                metric_avg[metric_id].append(value)

        metric_summary = {}
        for metric_id, values in metric_avg.items():
            metric_def = INDICATOR_DEFINITIONS.get(metric_id, {})
            metric_summary[metric_id] = {
                'name': metric_def.get('name', metric_id),
                'unit': metric_def.get('unit', ''),
                'mean': round(np.mean(values), 4),
                'std': round(np.std(values), 4),
                'min': round(np.min(values), 4),
                'max': round(np.max(values), 4),
            }

        overall_grade, overall_grade_cn = self._get_grade(np.mean(scores))

        report = {
            'report_type': 'batch_summary',
            'generated_at': datetime.now().isoformat(),
            'event_count': len(results),
            'overall_avg_score': round(np.mean(scores), 2),
            'overall_grade': overall_grade,
            'overall_grade_cn': overall_grade_cn,
            'score_range': [round(np.min(scores), 2), round(np.max(scores), 2)],
            'score_std': round(np.std(scores), 2),
            'risk_distribution': {
                'SAFE': risks.count(RiskLevel.SAFE),
                'CAUTION': risks.count(RiskLevel.CAUTION),
                'WARNING': risks.count(RiskLevel.WARNING),
                'DANGER': risks.count(RiskLevel.DANGER),
            },
            'event_type_distribution': event_type_counts,
            'location_avg_scores': location_avg_scores,
            'metric_summary': metric_summary,
        }

        return report

    def generate_markdown_summary(self, report: Dict[str, Any]) -> str:
        """生成Markdown格式的评测摘要"""
        lines = []
        report_type = report.get('report_type', 'unknown')

        if report_type == 'single_event':
            lines.append(f"# 座椅评测报告")
            lines.append(f"")
            lines.append(f"- **事件ID**: {report.get('trigger_id', 'N/A')}")
            lines.append(f"- **事件类型**: {report.get('event_type', 'N/A')}")
            lines.append(f"- **时间戳**: {report.get('timestamp', 0):.2f}s")
            lines.append(f"- **总体评分**: {report.get('overall_score', 0):.1f} "
                         f"({report.get('overall_grade_cn', '未知')})")
            lines.append(f"- **风险等级**: {report.get('overall_risk', 'N/A')}")
            lines.append(f"")

            for loc_id, loc in report.get('locations', {}).items():
                lines.append(f"## {loc.get('label_cn', loc_id)} "
                             f"({loc.get('channel_id', '')})")
                lines.append(f"- 评分: {loc.get('score', 0):.1f} "
                             f"({loc.get('grade_cn', '')})")
                lines.append(f"- 风险: {loc.get('risk_level', 'N/A')}")
                lines.append(f"")
                lines.append(f"| 指标 | 值 | 单位 |")
                lines.append(f"|------|-----|------|")
                for mid, m in loc.get('metrics', {}).items():
                    lines.append(f"| {m.get('name', mid)} "
                                 f"| {m.get('value', 0):.4f} "
                                 f"| {m.get('unit', '')} |")
                lines.append(f"")

        elif report_type == 'comparative':
            lines.append(f"# 座椅对照评测报告")
            lines.append(f"")
            lines.append(f"- **事件ID**: {report.get('trigger_id', 'N/A')}")
            lines.append(f"- **事件类型**: {report.get('event_type', 'N/A')}")
            lines.append(f"")

            os = report.get('overall_score', {})
            lines.append(f"## 总体对比")
            lines.append(f"- 实验组: {os.get('experimental_score', 0):.1f}")
            lines.append(f"- 对照组: {os.get('control_score', 0):.1f}")
            lines.append(f"- 改善率: {os.get('improvement', 0):.1f}%")
            lines.append(f"")

            lines.append(f"## 位置级对比")
            lines.append(f"| 位置 | 实验组 | 对照组 | 改善率 |")
            lines.append(f"|------|--------|--------|--------|")
            for loc_id, comp in report.get('location_comparisons', {}).items():
                lines.append(f"| {comp.get('label_cn', loc_id)} "
                             f"| {comp.get('exp_score', 0):.1f} "
                             f"| {comp.get('ctrl_score', 0):.1f} "
                             f"| {comp.get('improvement_pct', 0):.1f}% |")
            lines.append(f"")

        elif report_type == 'batch_summary':
            lines.append(f"# 座椅评测批量汇总")
            lines.append(f"")
            lines.append(f"- **事件总数**: {report.get('event_count', 0)}")
            lines.append(f"- **平均评分**: {report.get('overall_avg_score', 0):.1f} "
                         f"({report.get('overall_grade_cn', '未知')})")
            sr = report.get('score_range', [0, 0])
            lines.append(f"- **评分范围**: {sr[0]:.1f} - {sr[1]:.1f}")
            lines.append(f"- **标准差**: {report.get('score_std', 0):.2f}")
            lines.append(f"")

            rd = report.get('risk_distribution', {})
            lines.append(f"## 风险分布")
            lines.append(f"| 风险等级 | 数量 |")
            lines.append(f"|----------|------|")
            for level, count in rd.items():
                lines.append(f"| {level} | {count} |")
            lines.append(f"")

            lines.append(f"## 位置平均评分")
            for loc_id, loc in report.get('location_avg_scores', {}).items():
                lines.append(f"- {loc.get('label_cn', loc_id)}: "
                             f"均值{loc.get('avg_score', 0):.1f}, "
                             f"范围[{loc.get('min_score', 0):.1f}-{loc.get('max_score', 0):.1f}]")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"*报告生成时间: {report.get('generated_at', 'N/A')}*")
        return '\n'.join(lines)

    def clear_history(self):
        self._report_history.clear()

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._report_history)

    @staticmethod
    def _get_grade(score: float) -> tuple:
        for threshold, grade, grade_cn in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade, grade_cn
        return 'D', '差'