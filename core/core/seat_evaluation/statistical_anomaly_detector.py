#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计异常标注模块 (F5: 自动异常标注)

基于基线数据的自动异常检测与标注:
- 指标偏离基线 >2σ 自动标记
- 诊断建议自动生成
- 异常严重度分级
- 异常历史追踪
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyMark:
    """异常标注"""
    metric_id: str
    value: float
    baseline_mean: float
    baseline_std: float
    deviation_sigma: float  # 偏离基线标准差的倍数
    severity: str  # critical / warning / notice
    direction: str  # high / low (高于或低于基线)
    suggestion: str  # 诊断建议
    timestamp: float = 0.0
    diagnosed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """诊断报告"""
    report_id: str
    timestamp: float
    total_metrics: int
    anomaly_count: int
    anomalies: List[AnomalyMark]
    summary: str
    recommendations: List[str]
    risk_level: str  # low / medium / high / critical


class StatisticalAnomalyDetector:
    """统计异常检测器 (F5)

    功能:
    - 基于基线数据的统计异常检测 (>2σ)
    - 自动标记异常指标
    - 诊断建议自动生成
    - 异常严重度分级
    - 异常历史追踪
    """

    # 异常严重度阈值 (偏离标准差倍数)
    THRESHOLD_CRITICAL = 3.0  # >3σ
    THRESHOLD_WARNING = 2.0   # >2σ
    THRESHOLD_NOTICE = 1.5    # >1.5σ

    # 诊断建议模板
    DIAGNOSIS_TEMPLATES = {
        'SEAT_Z': {
            'high': '座垫垂向传递率偏高，建议检查座垫刚度和阻尼特性',
            'low': '座垫垂向传递率低于预期，可能为座垫过软或传感器安装问题'
        },
        'VDV_Z': {
            'high': '垂向振动剂量值偏高，长时间乘坐可能导致不适，建议优化悬架',
            'low': '垂向VDV低于预期，数据可能不完整'
        },
        'HIC15': {
            'high': '头部损伤指标超标，存在安全风险，需立即检查约束系统',
            'low': 'HIC15值正常'
        },
        'AW_Z': {
            'high': '垂向加权加速度偏高，乘坐舒适性较差',
            'low': '垂向加权加速度正常'
        },
        'S_D': {
            'high': '脊柱压缩应力偏高，存在腰椎损伤风险，建议降低座椅刚度',
            'low': '脊柱应力正常'
        },
        'DISP_HR': {
            'high': '头部三维位移偏大，需检查安全带约束效果',
            'low': '头部位移正常'
        },
        'BAND_ATT_01_05': {
            'high': '低频段衰减率偏高，座椅在低频段隔振效果良好',
            'low': '低频段衰减率不足，座椅在0.1-0.5Hz隔振效果差'
        },
        'BAND_ATT_05_1': {
            'high': '0.5-1Hz衰减率偏高',
            'low': '0.5-1Hz衰减率不足，可能影响动态舒适性'
        },
        'BAND_ATT_1_5': {
            'high': '1-5Hz衰减率偏高',
            'low': '1-5Hz衰减率不足，主管感知频段隔振差'
        },
    }

    # 通用诊断建议
    GENERIC_SUGGESTION_HIGH = '指标值显著高于基线，建议检查相关系统配置'
    GENERIC_SUGGESTION_LOW = '指标值显著低于基线，可能为数据异常或系统降级'

    def __init__(self):
        self._baseline: Dict[str, Tuple[float, float]] = {}  # {metric_id: (mean, std)}
        self._anomaly_history: List[AnomalyMark] = []
        self._diagnostic_reports: List[DiagnosticReport] = []

    def set_baseline(self, baseline_metrics: Dict[str, float],
                     baseline_std: Dict[str, float] = None):
        """设置基线数据 (均值和标准差)

        Args:
            baseline_metrics: {metric_id: mean}
            baseline_std: {metric_id: std}, 为None则默认std=0.1*mean
        """
        for metric_id, mean_val in baseline_metrics.items():
            if baseline_std and metric_id in baseline_std:
                std_val = baseline_std[metric_id]
            else:
                std_val = abs(mean_val) * 0.1 if abs(mean_val) > 1e-6 else 0.01
            self._baseline[metric_id] = (mean_val, max(std_val, 0.001))

        logger.info(f"基线已设置: {len(self._baseline)} metrics")

    def detect_anomalies(self, current_metrics: Dict[str, float],
                         threshold_map: Dict[str, Dict[str, float]] = None
                         ) -> List[AnomalyMark]:
        """检测异常指标

        Args:
            current_metrics: 当前指标值 {metric_id: value}
            threshold_map: 自定义阈值 {metric_id: {pass: val, warn: val}}

        Returns:
            List[AnomalyMark]: 异常标注列表
        """
        anomalies = []
        timestamp = datetime.now().timestamp()

        for metric_id, value in current_metrics.items():
            # 方法1: 基于基线统计检测
            if metric_id in self._baseline:
                baseline_mean, baseline_std = self._baseline[metric_id]
                if baseline_std > 0:
                    deviation = (value - baseline_mean) / baseline_std
                else:
                    deviation = 0.0

                if abs(deviation) >= self.THRESHOLD_NOTICE:
                    severity = self._get_severity(abs(deviation))
                    direction = 'high' if deviation > 0 else 'low'
                    suggestion = self._generate_suggestion(metric_id, direction)

                    mark = AnomalyMark(
                        metric_id=metric_id,
                        value=value,
                        baseline_mean=baseline_mean,
                        baseline_std=baseline_std,
                        deviation_sigma=round(deviation, 2),
                        severity=severity,
                        direction=direction,
                        suggestion=suggestion,
                        timestamp=timestamp
                    )
                    anomalies.append(mark)

            # 方法2: 基于阈值检测
            if threshold_map and metric_id in threshold_map:
                thresholds = threshold_map[metric_id]
                warn_threshold = thresholds.get('warn')
                if warn_threshold is not None and abs(value) > abs(warn_threshold):
                    # 如果还没被基线检测标记, 添加阈值标记
                    if not any(a.metric_id == metric_id for a in anomalies):
                        direction = 'high' if value > 0 else 'low'
                        mark = AnomalyMark(
                            metric_id=metric_id,
                            value=value,
                            baseline_mean=0,
                            baseline_std=0,
                            deviation_sigma=0,
                            severity='warning',
                            direction=direction,
                            suggestion=f'指标超出警告阈值 ({warn_threshold})',
                            timestamp=timestamp
                        )
                        anomalies.append(mark)

        # 记录历史
        self._anomaly_history.extend(anomalies)

        # 保持历史记录在合理范围
        if len(self._anomaly_history) > 5000:
            self._anomaly_history = self._anomaly_history[-5000:]

        if anomalies:
            logger.info(f"检测到 {len(anomalies)} 个异常指标")

        return anomalies

    def generate_diagnostic_report(self, current_metrics: Dict[str, float],
                                   threshold_map: Dict[str, Dict[str, float]] = None
                                   ) -> DiagnosticReport:
        """生成诊断报告 (F5: 自动异常标注 + 诊断建议)

        Args:
            current_metrics: 当前指标值
            threshold_map: 自定义阈值

        Returns:
            DiagnosticReport: 诊断报告
        """
        anomalies = self.detect_anomalies(current_metrics, threshold_map)
        timestamp = datetime.now().timestamp()

        # 按严重度排序
        severity_order = {'critical': 0, 'warning': 1, 'notice': 2}
        anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))

        # 风险等级
        critical_count = sum(1 for a in anomalies if a.severity == 'critical')
        warning_count = sum(1 for a in anomalies if a.severity == 'warning')

        if critical_count > 0:
            risk_level = 'critical'
        elif warning_count >= 3:
            risk_level = 'high'
        elif warning_count >= 1:
            risk_level = 'medium'
        elif len(anomalies) > 0:
            risk_level = 'low'
        else:
            risk_level = 'normal'

        # 汇总建议
        recommendations = []
        if len(anomalies) > 0:
            # 去重建议
            seen = set()
            for a in anomalies:
                if a.suggestion not in seen:
                    recommendations.append(f"[{a.severity.upper()}] {a.metric_id}: {a.suggestion}")
                    seen.add(a.suggestion)

        # 生成摘要
        if risk_level == 'critical':
            summary = f"检测到 {critical_count} 个严重异常, {warning_count} 个警告, 共 {len(anomalies)} 个异常指标。建议立即检查相关系统。"
        elif risk_level == 'high':
            summary = f"检测到 {warning_count} 个警告级别异常, 共 {len(anomalies)} 个异常指标。建议尽快排查。"
        elif risk_level == 'medium':
            summary = f"检测到 {len(anomalies)} 个异常指标, 建议关注并定期检查。"
        elif risk_level == 'low':
            summary = f"检测到 {len(anomalies)} 个轻微异常, 系统运行基本正常。"
        else:
            summary = "所有指标正常, 未检测到异常。"

        report = DiagnosticReport(
            report_id=f"DIA_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=timestamp,
            total_metrics=len(current_metrics),
            anomaly_count=len(anomalies),
            anomalies=anomalies,
            summary=summary,
            recommendations=recommendations,
            risk_level=risk_level
        )

        self._diagnostic_reports.append(report)
        if len(self._diagnostic_reports) > 100:
            self._diagnostic_reports = self._diagnostic_reports[-100:]

        return report

    def get_anomaly_summary(self, metric_ids: List[str] = None,
                            severity_filter: str = None) -> Dict[str, Any]:
        """获取异常摘要统计

        Returns:
            {
                'total_anomalies': int,
                'by_severity': {severity: count},
                'by_metric': {metric_id: count},
                'recent_anomalies': [...]
            }
        """
        history = self._anomaly_history
        if metric_ids:
            history = [a for a in history if a.metric_id in metric_ids]
        if severity_filter:
            history = [a for a in history if a.severity == severity_filter]

        by_severity = {}
        by_metric = {}
        for a in history:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            by_metric[a.metric_id] = by_metric.get(a.metric_id, 0) + 1

        recent = sorted(history[-20:], key=lambda a: abs(a.deviation_sigma), reverse=True)

        return {
            'total_anomalies': len(history),
            'by_severity': by_severity,
            'by_metric': dict(sorted(by_metric.items(), key=lambda x: x[1], reverse=True)[:10]),
            'recent_anomalies': [
                {
                    'metric_id': a.metric_id,
                    'value': a.value,
                    'deviation_sigma': a.deviation_sigma,
                    'severity': a.severity,
                    'direction': a.direction,
                    'suggestion': a.suggestion,
                    'timestamp': a.timestamp
                }
                for a in recent
            ]
        }

    def get_metric_stability(self, metric_id: str) -> Dict[str, Any]:
        """获取指标稳定性评估

        Returns:
            {stability: 'stable'/'volatile'/'erratic', recent_deviation: float, ...}
        """
        relevant = [a for a in self._anomaly_history if a.metric_id == metric_id]
        if not relevant:
            return {'stability': 'stable', 'anomaly_count': 0}

        recent = relevant[-10:]
        avg_deviation = np.mean([abs(a.deviation_sigma) for a in recent])

        if avg_deviation > 3.0:
            stability = 'erratic'
        elif avg_deviation > 2.0:
            stability = 'volatile'
        else:
            stability = 'stable'

        return {
            'stability': stability,
            'anomaly_count': len(relevant),
            'recent_count': len(recent),
            'avg_deviation_sigma': round(avg_deviation, 2),
            'max_deviation_sigma': round(max(abs(a.deviation_sigma) for a in recent), 2),
            'last_anomaly_time': recent[-1].timestamp if recent else None
        }

    def _get_severity(self, abs_deviation: float) -> str:
        """根据偏离标准差倍数确定严重度"""
        if abs_deviation >= self.THRESHOLD_CRITICAL:
            return 'critical'
        elif abs_deviation >= self.THRESHOLD_WARNING:
            return 'warning'
        else:
            return 'notice'

    def _generate_suggestion(self, metric_id: str, direction: str) -> str:
        """生成诊断建议"""
        if metric_id in self.DIAGNOSIS_TEMPLATES:
            return self.DIAGNOSIS_TEMPLATES[metric_id].get(
                direction, self.GENERIC_SUGGESTION_HIGH if direction == 'high' else self.GENERIC_SUGGESTION_LOW
            )

        # 通用建议
        if direction == 'high':
            return self.GENERIC_SUGGESTION_HIGH
        else:
            return self.GENERIC_SUGGESTION_LOW

    def clear(self):
        """清空所有数据"""
        self._baseline.clear()
        self._anomaly_history.clear()
        self._diagnostic_reports.clear()
        logger.info("StatisticalAnomalyDetector数据已清空")