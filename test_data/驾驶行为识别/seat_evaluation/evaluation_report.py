#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评估报告生成器（增强版）
整合元数据注册中心，生成包含完整溯源信息的评测报告

输出格式:
  - JSON报告（结构化数据）
  - Markdown报告（人工可读）
  - CSV报告（指标导出）
  - 全量统计汇总报告
"""

import json
import csv
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import asdict
from io import StringIO

import numpy as np

from .metadata_registry import MetadataRegistry, EvaluationDirection
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


class EvaluationReportGenerator:

    def __init__(self):
        self._metadata = MetadataRegistry()
        self._report_history: List[Dict[str, Any]] = []

    def get_metadata_for_indicator(self, indicator_code: str) -> Optional[Dict[str, Any]]:
        indicator = self._metadata.indicators.get(indicator_code)
        if indicator:
            return asdict(indicator)
        return None

    def generate_single_event_report(self, result: EvaluationResult) -> Dict[str, Any]:
        location_details = {}
        for loc_id, loc_result in result.location_results.items():
            label = LOCATION_LABELS_CN.get(loc_id, loc_id)
            grade, grade_cn = self._get_grade(loc_result.location_score)
            metric_details = {}
            for metric_id, value in loc_result.metrics.items():
                meta = self._metadata.indicators.get(metric_id)
                metric_details[metric_id] = {
                    'value': round(value, 4) if isinstance(value, (int, float)) else value,
                    'name': meta.display_name_cn if meta else metric_id,
                    'unit': meta.unit if meta else '',
                    'threshold_pass': meta.threshold_pass if meta else '',
                    'threshold_excellent': meta.threshold_excellent if meta else '',
                }
            location_details[loc_id] = {
                'label_cn': label,
                'channel_id': loc_result.channel_id,
                'score': round(loc_result.location_score, 2),
                'grade': grade,
                'grade_cn': grade_cn,
                'risk_level': loc_result.risk_level.value if hasattr(loc_result.risk_level, 'value') else str(loc_result.risk_level),
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
            'overall_risk': result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level),
            'location_count': len(result.location_results),
            'locations': location_details,
            'diagnosis': result.metadata.get('diagnosis', {}),
            'metadata': result.metadata,
        }

        self._report_history.append(report)
        return report

    def generate_comparative_report(self, result) -> Dict[str, Any]:
        exp_report = self.generate_single_event_report(result.experimental_results)
        ctrl_report = self.generate_single_event_report(result.control_results)

        location_comparisons = {}
        for loc_id in LOCATION_IDS:
            exp_loc = exp_report['locations'].get(loc_id, {})
            ctrl_loc = ctrl_report['locations'].get(loc_id, {})
            if exp_loc and ctrl_loc:
                improvement = ((exp_loc['score'] - ctrl_loc['score'])
                               / max(ctrl_loc['score'], 0.01) * 100)
                metric_comparisons = {}
                for metric_id in set(list(exp_loc.get('metrics', {}).keys()) +
                                     list(ctrl_loc.get('metrics', {}).keys())):
                    exp_val = exp_loc.get('metrics', {}).get(metric_id, {}).get('value', 0)
                    ctrl_val = ctrl_loc.get('metrics', {}).get(metric_id, {}).get('value', 0)
                    if isinstance(exp_val, (int, float)) and isinstance(ctrl_val, (int, float)):
                        atten = ((ctrl_val - exp_val) / max(abs(ctrl_val), 0.001) * 100)
                    else:
                        atten = 0.0
                    metric_comparisons[metric_id] = {
                        'experimental': exp_val,
                        'control': ctrl_val,
                        'attenuation_pct': round(atten, 2),
                    }
                location_comparisons[loc_id] = {
                    'label_cn': LOCATION_LABELS_CN.get(loc_id, loc_id),
                    'exp_score': exp_loc['score'],
                    'ctrl_score': ctrl_loc['score'],
                    'improvement_pct': round(improvement, 2),
                    'exp_grade': exp_loc['grade'],
                    'ctrl_grade': ctrl_loc['grade'],
                    'metric_comparisons': metric_comparisons,
                }

        overall_grade, overall_grade_cn = self._get_grade(
            (result.experimental_results.overall_score + result.control_results.overall_score) / 2
        )

        report = {
            'report_type': 'comparative',
            'generated_at': datetime.now().isoformat(),
            'trigger_id': result.trigger_id,
            'overall_grade': overall_grade,
            'overall_grade_cn': overall_grade_cn,
            'experimental': exp_report,
            'control': ctrl_report,
            'location_comparisons': location_comparisons,
            'metadata': result.metadata,
        }

        self._report_history.append(report)
        return report

    def generate_batch_summary_report(self, results: List[EvaluationResult],
                                      event_type: str = '') -> Dict[str, Any]:
        if not results:
            return {'report_type': 'batch_summary', 'count': 0, 'error': '无评测结果'}

        scores = [r.overall_score for r in results]
        all_metrics: Dict[str, List[float]] = {}
        all_location_scores: Dict[str, List[float]] = {}

        for r in results:
            for loc_id, loc_result in r.location_results.items():
                if loc_id not in all_location_scores:
                    all_location_scores[loc_id] = []
                all_location_scores[loc_id].append(loc_result.location_score)
                for metric_id, value in loc_result.metrics.items():
                    if metric_id not in all_metrics:
                        all_metrics[metric_id] = []
                    if isinstance(value, (int, float)):
                        all_metrics[metric_id].append(value)

        metric_summary = {}
        for metric_id, values in all_metrics.items():
            if values:
                meta = self._metadata.indicators.get(metric_id)
                metric_summary[metric_id] = {
                    'name': meta.display_name_cn if meta else metric_id,
                    'unit': meta.unit if meta else '',
                    'mean': round(float(np.mean(values)), 4),
                    'std': round(float(np.std(values)), 4),
                    'min': round(float(np.min(values)), 4),
                    'max': round(float(np.max(values)), 4),
                    'count': len(values),
                    'threshold_pass': meta.threshold_pass if meta else '',
                    'threshold_excellent': meta.threshold_excellent if meta else '',
                }

        location_summary = {}
        for loc_id, loc_scores in all_location_scores.items():
            location_summary[loc_id] = {
                'label_cn': LOCATION_LABELS_CN.get(loc_id, loc_id),
                'mean_score': round(float(np.mean(loc_scores)), 2),
                'std_score': round(float(np.std(loc_scores)), 2),
                'min_score': round(float(np.min(loc_scores)), 2),
                'max_score': round(float(np.max(loc_scores)), 2),
                'count': len(loc_scores),
            }

        report = {
            'report_type': 'batch_summary',
            'generated_at': datetime.now().isoformat(),
            'event_type': event_type,
            'count': len(results),
            'overall_score_mean': round(float(np.mean(scores)), 2),
            'overall_score_std': round(float(np.std(scores)), 2),
            'overall_score_min': round(float(np.min(scores)), 2),
            'overall_score_max': round(float(np.max(scores)), 2),
            'metrics': metric_summary,
            'locations': location_summary,
            'grade_distribution': self._get_grade_distribution(scores),
        }

        self._report_history.append(report)
        return report

    def generate_full_statistics_report(self, dataset_name: str,
                                        location_results: Dict[str, Dict[str, Any]],
                                        analysis_type: str = 'full') -> Dict[str, Any]:
        report = {
            'report_type': 'full_statistics',
            'generated_at': datetime.now().isoformat(),
            'dataset_name': dataset_name,
            'analysis_type': analysis_type,
            'preprocess_level': location_results.get('preprocess_level', 1),
            'sample_rate': location_results.get('sample_rate', 1000.0),
            'duration_s': location_results.get('duration_s', 0.0),
            'locations': {},
            'overall_summary': {},
            'vehicle_summary': location_results.get('vehicle_summary', {}),
        }

        all_metric_values: Dict[str, List[float]] = {}

        _meta_keys = {'preprocess_level', 'sample_rate', 'duration_s', 'vehicle_summary'}

        for loc_id, loc_data in location_results.items():
            if loc_id.startswith('_') or loc_id in _meta_keys:
                continue
            if not isinstance(loc_data, dict):
                continue

            metrics = loc_data.get('metrics', {})
            profile = loc_data.get('profile', None)
            contrast = loc_data.get('contrast', None)
            control_profile = loc_data.get('control_profile', None)
            control_metrics = loc_data.get('control_metrics', {})
            loc_report = {
                'label_cn': LOCATION_LABELS_CN.get(loc_id, loc_id),
                'metrics': {},
                'profile': profile,
                'contrast': contrast,
                'control_profile': control_profile,
                'control_metrics': control_metrics,
            }

            for metric_id, value in metrics.items():
                meta = self._metadata.indicators.get(metric_id)
                val = round(value, 4) if isinstance(value, (int, float)) else value
                loc_report['metrics'][metric_id] = {
                    'value': val,
                    'name': meta.display_name_cn if meta else metric_id,
                    'unit': meta.unit if meta else '',
                    'threshold_pass': meta.threshold_pass if meta else '',
                    'threshold_excellent': meta.threshold_excellent if meta else '',
                }
                if isinstance(value, (int, float)) and value != -1.0:
                    if metric_id not in all_metric_values:
                        all_metric_values[metric_id] = []
                    all_metric_values[metric_id].append(value)

            # 对照组指标同样富集元数据（P0修复: 防止 CSV/Markdown 导出 AttributeError）
            enriched_ctrl = {}
            for metric_id, value in control_metrics.items():
                meta = self._metadata.indicators.get(metric_id)
                val = round(value, 4) if isinstance(value, (int, float)) else value
                enriched_ctrl[metric_id] = {
                    'value': val,
                    'name': meta.display_name_cn if meta else metric_id,
                    'unit': meta.unit if meta else '',
                    'threshold_pass': meta.threshold_pass if meta else '',
                    'threshold_excellent': meta.threshold_excellent if meta else '',
                }
            loc_report['control_metrics'] = enriched_ctrl

            report['locations'][loc_id] = loc_report

        for metric_id, values in all_metric_values.items():
            if values:
                meta = self._metadata.indicators.get(metric_id)
                report['overall_summary'][metric_id] = {
                    'name': meta.display_name_cn if meta else metric_id,
                    'unit': meta.unit if meta else '',
                    'mean': round(float(np.mean(values)), 4),
                    'std': round(float(np.std(values)), 4),
                    'min': round(float(np.min(values)), 4),
                    'max': round(float(np.max(values)), 4),
                }

        self._report_history.append(report)
        return report

    def export_to_markdown(self, report: Dict[str, Any]) -> str:
        report_type = report.get('report_type', 'unknown')

        if report_type == 'single_event':
            return self._export_single_event_md(report)
        elif report_type == 'comparative':
            return self._export_comparative_md(report)
        elif report_type == 'batch_summary':
            return self._export_batch_summary_md(report)
        elif report_type == 'full_statistics':
            return self._export_full_statistics_md(report)
        else:
            return f"# 评测报告\n\n报告类型: {report_type}\n生成时间: {report.get('generated_at', '')}"

    def _export_single_event_md(self, report: Dict) -> str:
        lines = [
            f"# 座椅评测报告 — 单事件",
            f"",
            f"**生成时间**: {report.get('generated_at', '')}",
            f"**事件ID**: {report.get('trigger_id', '')}",
            f"**事件类型**: {report.get('event_type', '')}",
            f"**时间戳**: {report.get('timestamp', 0.0):.3f}s",
            f"**总体评分**: {report.get('overall_score', 0):.2f} ({report.get('overall_grade', 'N/A')}{report.get('overall_grade_cn', '')})",
            f"**风险等级**: {report.get('overall_risk', '')}",
            f"",
            f"## 各位置评测详情",
            f"",
        ]

        locations = report.get('locations', {})
        for loc_id, loc_data in locations.items():
            lines.append(f"### {loc_data.get('label_cn', loc_id)}")
            lines.append(f"")
            lines.append(f"- **评分**: {loc_data.get('score', 0):.2f} ({loc_data.get('grade', '')}{loc_data.get('grade_cn', '')})")
            lines.append(f"- **风险**: {loc_data.get('risk_level', '')}")
            lines.append(f"")

            metrics = loc_data.get('metrics', {})
            if metrics:
                lines.append(f"| 指标 | 值 | 单位 | 通过阈值 | 优秀阈值 |")
                lines.append(f"|------|-----|------|----------|----------|")
                for metric_id, metric_info in metrics.items():
                    name = metric_info.get('name', metric_id)
                    value = metric_info.get('value', '')
                    unit = metric_info.get('unit', '')
                    pass_th = metric_info.get('threshold_pass', '')
                    exc_th = metric_info.get('threshold_excellent', '')
                    if isinstance(value, float):
                        value_str = f"{value:.4f}"
                    else:
                        value_str = str(value)
                    lines.append(f"| {name} | {value_str} | {unit} | {pass_th} | {exc_th} |")
                lines.append(f"")

        diagnosis = report.get('diagnosis', {})
        if diagnosis:
            lines.append(f"## 诊断建议")
            lines.append(f"")
            if isinstance(diagnosis, dict):
                for key, val in diagnosis.items():
                    lines.append(f"- **{key}**: {val}")
            lines.append(f"")

        return "\n".join(lines)

    def _export_comparative_md(self, report: Dict) -> str:
        lines = [
            f"# 座椅评测报告 — 对照分析",
            f"",
            f"**生成时间**: {report.get('generated_at', '')}",
            f"**事件ID**: {report.get('trigger_id', '')}",
            f"**总体评级**: {report.get('overall_grade', 'N/A')}{report.get('overall_grade_cn', '')}",
            f"",
            f"## 各位置对照详情",
            f"",
        ]

        comparisons = report.get('location_comparisons', {})
        for loc_id, comp in comparisons.items():
            lines.append(f"### {comp.get('label_cn', loc_id)}")
            lines.append(f"")
            lines.append(f"- **实验组评分**: {comp.get('exp_score', 0):.2f} ({comp.get('exp_grade', '')})")
            lines.append(f"- **对照组评分**: {comp.get('ctrl_score', 0):.2f} ({comp.get('ctrl_grade', '')})")
            lines.append(f"- **改善率**: {comp.get('improvement_pct', 0):.1f}%")
            lines.append(f"")

            metric_comps = comp.get('metric_comparisons', {})
            if metric_comps:
                lines.append(f"| 指标 | 实验组 | 对照组 | 衰减率 |")
                lines.append(f"|------|--------|--------|--------|")
                for metric_id, mc in metric_comps.items():
                    lines.append(f"| {metric_id} | {mc.get('experimental', '')} | {mc.get('control', '')} | {mc.get('attenuation_pct', 0):.1f}% |")
                lines.append(f"")

        return "\n".join(lines)

    def _export_batch_summary_md(self, report: Dict) -> str:
        lines = [
            f"# 座椅评测报告 — 批量汇总",
            f"",
            f"**生成时间**: {report.get('generated_at', '')}",
            f"**事件类型**: {report.get('event_type', '')}",
            f"**事件数量**: {report.get('count', 0)}",
            f"**平均评分**: {report.get('overall_score_mean', 0):.2f} ± {report.get('overall_score_std', 0):.2f}",
            f"**评分范围**: {report.get('overall_score_min', 0):.2f} ~ {report.get('overall_score_max', 0):.2f}",
            f"",
        ]

        grade_dist = report.get('grade_distribution', {})
        if grade_dist:
            lines.append(f"## 等级分布")
            lines.append(f"")
            lines.append(f"| 等级 | 数量 | 占比 |")
            lines.append(f"|------|------|------|")
            for grade, info in grade_dist.items():
                lines.append(f"| {grade} | {info.get('count', 0)} | {info.get('ratio', 0):.1f}% |")
            lines.append(f"")

        metrics = report.get('metrics', {})
        if metrics:
            lines.append(f"## 指标汇总")
            lines.append(f"")
            lines.append(f"| 指标 | 均值 | 标准差 | 最小值 | 最大值 | 通过阈值 |")
            lines.append(f"|------|------|--------|--------|--------|----------|")
            for metric_id, ms in metrics.items():
                lines.append(f"| {ms.get('name', metric_id)} | {ms.get('mean', 0):.4f} | {ms.get('std', 0):.4f} | {ms.get('min', 0):.4f} | {ms.get('max', 0):.4f} | {ms.get('threshold_pass', '')} |")
            lines.append(f"")

        locations = report.get('locations', {})
        if locations:
            lines.append(f"## 位置汇总")
            lines.append(f"")
            lines.append(f"| 位置 | 平均评分 | 标准差 | 最小 | 最大 |")
            lines.append(f"|------|----------|--------|------|------|")
            for loc_id, ls in locations.items():
                lines.append(f"| {ls.get('label_cn', loc_id)} | {ls.get('mean_score', 0):.2f} | {ls.get('std_score', 0):.2f} | {ls.get('min_score', 0):.2f} | {ls.get('max_score', 0):.2f} |")
            lines.append(f"")

        return "\n".join(lines)

    def _export_full_statistics_md(self, report: Dict) -> str:
        lines = [
            f"# 座椅评测报告 — 全量统计分析",
            f"",
            f"**生成时间**: {report.get('generated_at', '')}",
            f"**数据集**: {report.get('dataset_name', '')}",
            f"**分析类型**: {report.get('analysis_type', '')}",
            f"**预处理级别**: Level {report.get('preprocess_level', 1)}",
            f"**采样率**: {report.get('sample_rate', 1000)}Hz",
            f"**数据时长**: {report.get('duration_s', 0):.2f}s",
            f"",
            f"## 总体统计",
            f"",
        ]

        overall = report.get('overall_summary', {})
        if overall:
            lines.append(f"| 指标 | 均值 | 标准差 | 最小值 | 最大值 | 单位 |")
            lines.append(f"|------|------|--------|--------|--------|------|")
            for metric_id, ms in overall.items():
                lines.append(f"| {ms.get('name', metric_id)} | {ms.get('mean', 0):.4f} | {ms.get('std', 0):.4f} | {ms.get('min', 0):.4f} | {ms.get('max', 0):.4f} | {ms.get('unit', '')} |")
            lines.append(f"")

        locations = report.get('locations', {})
        if locations:
            lines.append(f"## 各位置详细结果")
            lines.append(f"")
            for loc_id, loc_data in locations.items():
                lines.append(f"### {loc_data.get('label_cn', loc_id)}")
                lines.append(f"- **评分**: {loc_data.get('score', 0):.2f}")
                lines.append(f"")
                metrics = loc_data.get('metrics', {})
                if metrics:
                    lines.append(f"| 指标 | 值 | 单位 | 通过阈值 | 优秀阈值 |")
                    lines.append(f"|------|-----|------|----------|----------|")
                    for metric_id, mi in metrics.items():
                        lines.append(f"| {mi.get('name', metric_id)} | {mi.get('value', '')} | {mi.get('unit', '')} | {mi.get('threshold_pass', '')} | {mi.get('threshold_excellent', '')} |")
                    lines.append(f"")
                # 对照组指标
                control_metrics = loc_data.get('control_metrics', {})
                if control_metrics:
                    lines.append(f"#### 对照组")
                    lines.append(f"| 指标 | 值 | 单位 | 通过阈值 | 优秀阈值 |")
                    lines.append(f"|------|-----|------|----------|----------|")
                    for metric_id, cmi in control_metrics.items():
                        lines.append(f"| {cmi.get('name', metric_id)} | {cmi.get('value', '')} | {cmi.get('unit', '')} | {cmi.get('threshold_pass', '')} | {cmi.get('threshold_excellent', '')} |")
                    lines.append(f"")

        return "\n".join(lines)

    def export_to_csv(self, report: Dict[str, Any]) -> str:
        output = StringIO()
        writer = csv.writer(output)

        report_type = report.get('report_type', 'unknown')

        if report_type == 'single_event':
            writer.writerow(['位置', '指标', '值', '单位'])
            for loc_id, loc_data in report.get('locations', {}).items():
                label = loc_data.get('label_cn', loc_id)
                for metric_id, mi in loc_data.get('metrics', {}).items():
                    writer.writerow([label, mi.get('name', metric_id), mi.get('value', ''), mi.get('unit', '')])

        elif report_type == 'batch_summary':
            writer.writerow(['指标', '均值', '标准差', '最小值', '最大值'])
            for metric_id, ms in report.get('metrics', {}).items():
                writer.writerow([ms.get('name', metric_id), ms.get('mean', 0), ms.get('std', 0), ms.get('min', 0), ms.get('max', 0)])

        elif report_type == 'full_statistics':
            writer.writerow(['位置', '指标', '实验组值', '单位', '对照组值', '衰减率(%)'])
            for loc_id, loc_data in report.get('locations', {}).items():
                label = loc_data.get('label_cn', loc_id)
                exp_metrics = loc_data.get('metrics', {})
                ctrl_metrics = loc_data.get('control_metrics', {})
                all_metric_ids = set(exp_metrics.keys()) | set(ctrl_metrics.keys())
                for metric_id in all_metric_ids:
                    em = exp_metrics.get(metric_id, {})
                    cm = ctrl_metrics.get(metric_id, {})
                    e_val = em.get('value', '')
                    c_val = cm.get('value', '')
                    unit = em.get('unit', cm.get('unit', ''))
                    # 计算衰减率
                    att_pct = ''
                    try:
                        ev, cv = float(e_val), float(c_val)
                        if abs(cv) > 1e-9:
                            att_pct = f"{(1 - ev / cv) * 100:.1f}"
                    except (ValueError, TypeError):
                        pass
                    writer.writerow([label, cm.get('name', em.get('name', metric_id)), e_val, unit, c_val, att_pct])

        else:
            writer.writerow(['报告类型', report_type])

        return output.getvalue()

    def export_to_json(self, report: Dict[str, Any], indent: int = 2) -> str:
        def _json_serializer(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)

        return json.dumps(report, indent=indent, ensure_ascii=False, default=_json_serializer)

    def _get_grade(self, score: float) -> Tuple[str, str]:
        if score >= 100:
            return 'A+', '卓越'
        for threshold, grade, grade_cn in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade, grade_cn
        return 'D', '差'

    def _get_grade_distribution(self, scores: List[float]) -> Dict[str, Any]:
        dist = {}
        for threshold, grade, grade_cn in GRADE_THRESHOLDS:
            count = sum(1 for s in scores if s >= threshold and s < (threshold + 20 if threshold < 90 else 200))
            count = max(count, sum(1 for s in scores if s >= threshold)) if threshold == 0 else count
            dist[grade] = {
                'label': grade_cn,
                'count': count,
                'ratio': round(count / max(len(scores), 1) * 100, 1),
            }
        return dist

    def get_report_history(self) -> List[Dict[str, Any]]:
        return self._report_history

    def clear_history(self):
        self._report_history.clear()