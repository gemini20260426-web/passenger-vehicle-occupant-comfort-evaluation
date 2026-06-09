#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多工况对比分析器

功能:
  1. SEAT 因子跨工况稳定度分析 (变异系数 CV)
  2. 共振频率漂移检测 (Δf > 0.5 Hz 告警)
  3. 工况排序 (综合评分)
  4. 工程改进建议生成
"""

import numpy as np
from typing import Dict, List, Tuple
import logging

from .shaker_models import AnalysisResult, CrossConditionReport

logger = logging.getLogger(__name__)


class CrossConditionAnalyzer:
    """多工况对比分析器"""

    CV_STABLE_THRESHOLD = 0.15      # CV < 15% → 稳定
    FREQ_DRIFT_ALERT = 0.5          # Δf > 0.5 Hz → 频率漂移告警
    GAIN_DROP_ALERT_PCT = 30        # 增益下降 > 30% → 告警

    def analyze(self, results: Dict[str, AnalysisResult]) -> CrossConditionReport:
        """
        跨工况对比分析。

        Args:
            results: {condition_name: AnalysisResult} 字典

        Returns:
            CrossConditionReport: 对比分析报告
        """
        if len(results) < 2:
            logger.warning(f"需要至少 2 个工况进行对比，当前: {len(results)}")
            return CrossConditionReport(conditions=list(results.keys()))

        report = CrossConditionReport()
        report.conditions = sorted(results.keys())

        # ── 1. SEAT 因子矩阵 ──
        self._build_seat_matrix(results, report)

        # ── 2. RMS/VDV 矩阵 ──
        self._build_rms_vdv_matrices(results, report)

        # ── 3. 共振汇总 ──
        self._build_resonance_summary(results, report)

        # ── 4. 稳定性分析 ──
        self._stability_analysis(report)

        # ── 5. 排序 ──
        self._rank_conditions(report)

        # ── 6. 工程建议 ──
        report.recommendations = self._generate_recommendations(report)

        return report

    # ══════════════════════════════════════════════════
    # 矩阵构建
    # ══════════════════════════════════════════════════

    def _build_seat_matrix(self, results: Dict[str, AnalysisResult],
                           report: CrossConditionReport):
        """构建 SEAT 因子矩阵 (工况 × 通道)"""
        seat_matrix = {}
        for cond_name, ar in results.items():
            seat_matrix[cond_name] = ar.seat.seat_values.copy()
        report.seat_matrix = seat_matrix

    def _build_rms_vdv_matrices(self, results: Dict[str, AnalysisResult],
                                 report: CrossConditionReport):
        """构建 RMS 和 VDV 矩阵"""
        rms_matrix = {}
        vdv_matrix = {}
        for cond_name, ar in results.items():
            rms_matrix[cond_name] = {}
            vdv_matrix[cond_name] = {}
            for ch, td in ar.time_domain.items():
                rms_matrix[cond_name][ch] = td.rms
                vdv_matrix[cond_name][ch] = td.vdv
        report.rms_matrix = rms_matrix
        report.vdv_matrix = vdv_matrix

    def _build_resonance_summary(self, results: Dict[str, AnalysisResult],
                                  report: CrossConditionReport):
        """构建共振汇总"""
        report.resonance_summary = {}
        for cond_name, ar in results.items():
            report.resonance_summary[cond_name] = ar.resonance_summary.copy()

    # ══════════════════════════════════════════════════
    # 稳定性分析
    # ══════════════════════════════════════════════════

    def _stability_analysis(self, report: CrossConditionReport):
        """跨工况稳定性分析"""
        cv_dict = {}

        # SEAT 变异系数
        seat_channels = set()
        for cond_name in report.conditions:
            seat_channels.update(report.seat_matrix.get(cond_name, {}).keys())

        for ch in seat_channels:
            vals = [report.seat_matrix[c].get(ch, 0) for c in report.conditions]
            finite_vals = [v for v in vals if v > 0 and v < 1e10]
            if len(finite_vals) >= 2:
                mean_val = np.mean(finite_vals)
                std_val = np.std(finite_vals)
                cv = std_val / max(1e-6, mean_val)
                cv_dict[ch] = round(cv, 4)
            else:
                cv_dict[ch] = 0

        report.stability = cv_dict

        # 共振频率漂移检测
        for path_key in report.resonance_summary.get(report.conditions[0], {}):
            freqs = []
            for cond_name in report.conditions:
                r = report.resonance_summary.get(cond_name, {}).get(path_key, {})
                if r.get('freq', 0) > 0:
                    freqs.append(r['freq'])
            if len(freqs) >= 2:
                freq_range = max(freqs) - min(freqs)
                if freq_range > self.FREQ_DRIFT_ALERT:
                    logger.warning(
                        f"{path_key}: 共振频率漂移 {freq_range:.2f} Hz "
                        f"(min={min(freqs):.1f}, max={max(freqs):.1f})"
                    )

    # ══════════════════════════════════════════════════
    # 排序
    # ══════════════════════════════════════════════════

    def _rank_conditions(self, report: CrossConditionReport):
        """按 SEAT 综合得分排序 (越低越好)"""
        ranking = {}

        # 对每个通道排序
        seat_channels = set()
        for cond_name in report.conditions:
            seat_channels.update(report.seat_matrix.get(cond_name, {}).keys())

        for ch in seat_channels:
            pairs = [(c, report.seat_matrix.get(c, {}).get(ch, float('inf')))
                     for c in report.conditions]
            ranked = sorted([p[0] for p in pairs if p[1] < 1e10],
                           key=lambda c: report.seat_matrix[c].get(ch, float('inf')))
            ranking[ch] = ranked

        report.ranking = ranking

        # 综合最优/最差 (基于 R_z SEAT)
        if 'r_point_z' in ranking and ranking['r_point_z']:
            report.best_condition = ranking['r_point_z'][0]
            report.worst_condition = ranking['r_point_z'][-1]

    # ══════════════════════════════════════════════════
    # 建议生成
    # ══════════════════════════════════════════════════

    def _generate_recommendations(self, report: CrossConditionReport) -> List[str]:
        """生成工程改进建议"""
        recs = []

        # 1. 共振问题
        resonance_channels = []
        for cond_name in report.conditions:
            for ch, info in report.resonance_summary.get(cond_name, {}).items():
                if info.get('gain', 0) > 10:
                    resonance_channels.append(ch)
        if resonance_channels:
            main_ch = max(set(resonance_channels), key=resonance_channels.count)
            main_info = report.resonance_summary.get(report.conditions[0], {}).get(main_ch, {})
            recs.append(
                f"座椅在 {main_info.get('freq', 'N/A')} Hz 处存在严重共振 "
                f"(增益 {main_info.get('gain', 0):.1f}×)，建议增加悬架阻尼"
            )

        # 2. 稳定性问题
        unstable = [k for k, v in report.stability.items() if v >= self.CV_STABLE_THRESHOLD]
        if unstable:
            recs.append(
                f"以下通道 SEAT 值跨工况不稳定 (CV≥{self.CV_STABLE_THRESHOLD*100:.0f}%): "
                f"{', '.join(unstable[:5])}，建议检查测试条件一致性"
            )

        # 3. SEAT 异常高
        if report.worst_condition:
            worst_seat = report.seat_matrix.get(report.worst_condition, {})
            high_channels = [k for k, v in worst_seat.items() if v > 300]
            if high_channels:
                recs.append(
                    f"最差工况 {report.worst_condition} 中 {len(high_channels)} 个通道 "
                    f"SEAT > 300%，重点关注"
                )

        # 4. 台架激励不足
        recs.append(
            "若平台 Z 轴激励 RMS < 0.5 m/s²，建议提高激励幅值"
            "以获得更可靠的 SEAT 评估"
        )

        return recs

    # ══════════════════════════════════════════════════
    # 便捷函数
    # ══════════════════════════════════════════════════

    def get_seat_table(self, report: CrossConditionReport) -> List[Dict]:
        """生成 SEAT 对比表格 (适合导出)"""
        rows = []
        seat_channels = set()
        for cond_name in report.conditions:
            seat_channels.update(report.seat_matrix.get(cond_name, {}).keys())

        for ch in sorted(seat_channels):
            row = {'通道': ch}
            for cond_name in report.conditions:
                val = report.seat_matrix.get(cond_name, {}).get(ch, 0)
                row[cond_name] = f"{val:.1f}%" if val < 1e10 else 'N/A'
            rows.append(row)
        return rows

    def get_summary_dict(self, report: CrossConditionReport) -> Dict:
        """生成可序列化的对比摘要"""
        return {
            'conditions': report.conditions,
            'best': report.best_condition,
            'worst': report.worst_condition,
            'stability': report.stability,
            'recommendations': report.recommendations,
            'seat_matrix': {
                c: {k: round(v, 1) for k, v in report.seat_matrix.get(c, {}).items()}
                for c in report.conditions
            },
        }