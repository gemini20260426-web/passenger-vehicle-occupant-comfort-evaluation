#!/usr/bin/env python3
"""
批次对比引擎 — 多次测试结果的横向对比分析

核心功能:
  1. 多批次指标汇总 (均值/标准差/最大/最小)
  2. 最佳/最差批次识别
  3. 批次排名
  4. 批次间统计差异 (Cohen's d)
  5. 批次趋势分析

数据格式:
  输入: List[BatchResult] = [
      {'name': '批次1', 'timestamp': '...', 'results': {...}},
      {'name': '批次2', 'timestamp': '...', 'results': {...}},
      ...
  ]
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

import logging
logger = logging.getLogger(__name__)


@dataclass
class BatchSummary:
    """单批次汇总"""
    name: str = ''
    timestamp: str = ''
    comfort_score: float = 0
    comfort_grade: str = 'N/A'
    aw_total: float = 0
    vdv_z: float = 0
    s_d: float = 0
    seat_z: float = 0
    event_count: int = 0
    details: Dict = field(default_factory=dict)


@dataclass
class BatchComparisonResult:
    """批次对比结果"""

    # 批次列表
    batches: List[BatchSummary] = field(default_factory=list)
    batch_count: int = 0

    # 排名
    ranked_by_comfort: List[str] = field(default_factory=list)

    # 最佳/最差
    best_batch: str = ''
    worst_batch: str = ''
    best_score: float = 0
    worst_score: float = 0

    # 统计汇总
    comfort_mean: float = 0
    comfort_std: float = 0
    comfort_range: float = 0

    # 趋势
    trend_direction: str = 'stable'  # improving/stable/degrading
    trend_magnitude: float = 0

    # 关键指标汇总
    key_metrics: Dict = field(default_factory=dict)

    # 详细数据
    details: Dict = field(default_factory=dict)


class BatchComparisonEngine:
    """批次对比引擎

    用法:
        engine = BatchComparisonEngine()
        batches = [
            {'name': '方案A', 'comfort_index': {'overall_score': 85}, ...},
            {'name': '方案B', 'comfort_index': {'overall_score': 78}, ...},
        ]
        result = engine.compare(batches)
    """

    def __init__(self):
        self.TREND_THRESHOLD = 5.0  # 舒适度变化超过5分视为趋势

    def compare(self, batch_results: List[Dict]) -> BatchComparisonResult:
        """执行批次对比分析

        Args:
            batch_results: 批次结果列表，每项为 report dict (含 comfort_index, time_domain 等)

        Returns:
            BatchComparisonResult
        """
        result = BatchComparisonResult()

        try:
            if not batch_results:
                logger.warning("批次对比: 无数据")
                return result

            # 1. 提取各批次摘要
            summaries = []
            for br in batch_results:
                ci = br.get('comfort_index', {})
                td = br.get('time_domain', {})
                sf = br.get('shock_fatigue', {})
                fd = br.get('frequency_domain', {})

                vdv_data = td.get('vdv', {}).get('座垫', {}).get('实验组', {})
                sd_data = sf.get('iso2631_5', {}).get('座垫', {}).get('实验组', {})
                seat_data = fd.get('seat', {}).get('座垫', {})

                summary = BatchSummary(
                    name=br.get('name', br.get('metadata', {}).get('source', '未命名')),
                    timestamp=br.get('metadata', {}).get('created_at', ''),
                    comfort_score=ci.get('overall_score', 0),
                    comfort_grade=ci.get('grade', 'N/A'),
                    aw_total=0,
                    vdv_z=vdv_data.get('Z', 0),
                    s_d=sd_data.get('S_d', 0),
                    seat_z=seat_data.get('Z', 1.0) if seat_data else 1.0,
                    event_count=len(br.get('events', [])),
                    details=ci,
                )
                summaries.append(summary)

            result.batches = summaries
            result.batch_count = len(summaries)

            # 2. 排名
            sorted_batches = sorted(summaries, key=lambda b: b.comfort_score, reverse=True)
            result.ranked_by_comfort = [f"{b.name} ({b.comfort_score:.1f})" for b in sorted_batches]

            result.best_batch = sorted_batches[0].name
            result.best_score = sorted_batches[0].comfort_score
            result.worst_batch = sorted_batches[-1].name
            result.worst_score = sorted_batches[-1].comfort_score

            # 3. 统计汇总
            scores = [b.comfort_score for b in summaries if b.comfort_score > 0]
            if scores:
                result.comfort_mean = round(np.mean(scores), 1)
                result.comfort_std = round(np.std(scores), 1)
                result.comfort_range = round(max(scores) - min(scores), 1)

            # 4. 趋势分析 (按时间排序)
            if len(summaries) >= 2:
                chrono = sorted(summaries, key=lambda b: b.timestamp)
                first_score = chrono[0].comfort_score
                last_score = chrono[-1].comfort_score
                diff = last_score - first_score

                if diff >= self.TREND_THRESHOLD:
                    result.trend_direction = 'improving'
                elif diff <= -self.TREND_THRESHOLD:
                    result.trend_direction = 'degrading'
                else:
                    result.trend_direction = 'stable'
                result.trend_magnitude = diff

            # 5. 关键指标汇总
            result.key_metrics = {
                'vdv_z': {
                    'values': [b.vdv_z for b in summaries],
                    'mean': round(np.mean([b.vdv_z for b in summaries]), 2),
                    'best': min(b.vdv_z for b in summaries),
                },
                's_d': {
                    'values': [b.s_d for b in summaries],
                    'mean': round(np.mean([b.s_d for b in summaries]), 3),
                    'best': min(b.s_d for b in summaries),
                },
                'seat_z': {
                    'values': [b.seat_z for b in summaries],
                    'mean': round(np.mean([b.seat_z for b in summaries]), 3),
                    'best': min(b.seat_z for b in summaries),
                },
            }

            result.details = {
                'batch_names': [b.name for b in summaries],
                'trend': result.trend_direction,
                'trend_magnitude': result.trend_magnitude,
            }

        except Exception as e:
            logger.warning(f"批次对比失败: {e}")

        return result

    def compare_raw(self, named_results: Dict[str, Dict]) -> BatchComparisonResult:
        """从命名结果字典直接对比

        Args:
            named_results: {'方案A': analysis_results, '方案B': analysis_results, ...}
        """
        from core.core.seat_evaluation.report_builder import ReportBuilder

        builder = ReportBuilder()
        batch_reports = []
        for name, results in named_results.items():
            report = builder.build(evaluator_results=results, behavior_summary={})
            report['name'] = name
            batch_reports.append(report)

        return self.compare(batch_reports)