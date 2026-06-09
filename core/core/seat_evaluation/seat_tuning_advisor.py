#!/usr/bin/env python3
"""
座椅调校建议引擎 — 基于分析结果自动生成可执行的调校参数
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

import logging
logger = logging.getLogger(__name__)


@dataclass
class TuningRecommendation:
    """调校建议"""
    component: str           # 部件 (阻尼器/弹簧/衬套/...)
    parameter: str           # 参数 (刚度/阻尼系数/预压/...)
    current_value: Optional[float] = None   # 当前值
    target_value: Optional[float] = None     # 目标值
    direction: str = '保持'                  # 增大/减小/保持
    confidence: float = 0.5                  # 置信度 (0-1)
    reason: str = ''                         # 原因
    expected_improvement: str = ''           # 预期效果


class SeatTuningAdvisor:
    """座椅调校建议引擎

    知识库: 基于物理模型 + 行业经验规则
    """

    RULES = [
        # (条件, 建议)
        # ── 垂向振动 (Z轴) ──
        {
            'condition': lambda r: r.get('SEAT_Z', 1.0) > 0.9,
            'recommendation': TuningRecommendation(
                '主弹簧', '刚度_k', direction='减小', confidence=0.85,
                reason='SEAT_Z > 0.9 表示座椅未有效衰减垂向振动',
                expected_improvement='SEAT_Z 预计下降 10-15%'
            )
        },
        {
            'condition': lambda r: r.get('PSD_Z_peak_freq', 0) < 3,
            'recommendation': TuningRecommendation(
                '阻尼器', '阻尼系数_c', direction='增大', confidence=0.80,
                reason='垂向共振频率 < 3Hz，与人体内脏共振区 (4-8Hz) 脱耦不足',
                expected_improvement='共振峰值预计降低 20-30%'
            )
        },
        # ── 侧向振动 (Y轴) ──
        {
            'condition': lambda r: r.get('SEAT_Y', 1.0) > 0.8,
            'recommendation': TuningRecommendation(
                '侧向衬套', '刚度_ky', direction='增大', confidence=0.75,
                reason='SEAT_Y > 0.8 侧向隔振不足，弯道时侧倾明显',
                expected_improvement='侧向摇摆预计减少 15-20%'
            )
        },
        # ── 冲击 (S_d) ──
        {
            'condition': lambda r: r.get('S_d', 0) > 0.8,
            'recommendation': TuningRecommendation(
                '缓冲块', '间隙_d', direction='增大', confidence=0.90,
                reason='S_d > 0.8MPa 冲击过大，底触风险',
                expected_improvement='冲击峰值预计降低 25-35%'
            )
        },
        # ── 姿态 (角速度) ──
        {
            'condition': lambda r: r.get('Gz_rms', 0) > 5,
            'recommendation': TuningRecommendation(
                '抗侧倾杆', '刚度_kr', direction='增大', confidence=0.70,
                reason='Gz_RMS > 5°/s 侧倾过大，影响乘坐姿态',
                expected_improvement='侧倾角速度预计降低 20%'
            )
        },
    ]

    def analyze(self, results: dict) -> List[TuningRecommendation]:
        """基于全量统计结果生成调校建议"""
        recommendations = []

        # 提取关键指标
        metrics = self._extract_metrics(results)

        for rule in self.RULES:
            try:
                if rule['condition'](metrics):
                    rec = rule['recommendation']
                    # 根据实际值填充建议值
                    if rec.parameter == '刚度_k':
                        rec.current_value = metrics.get('SEAT_Z', 1.0) * 100
                        rec.target_value = rec.current_value * 0.8
                    elif rec.parameter == '阻尼系数_c':
                        rec.current_value = metrics.get('PSD_Z_peak', 0)
                        rec.target_value = rec.current_value * 1.3
                    elif rec.parameter == '刚度_ky':
                        rec.current_value = metrics.get('SEAT_Y', 1.0) * 100
                        rec.target_value = rec.current_value * 1.2
                    elif rec.parameter == '间隙_d':
                        rec.current_value = metrics.get('S_d', 0)
                        rec.target_value = rec.current_value * 1.3
                    elif rec.parameter == '刚度_kr':
                        rec.current_value = metrics.get('Gz_rms', 0)
                        rec.target_value = rec.current_value * 1.2

                    recommendations.append(rec)

                    if len(recommendations) >= 5:
                        break
            except Exception as e:
                logger.debug(f"规则评估跳过: {e}")
                continue

        return recommendations

    def _extract_metrics(self, results: dict) -> dict:
        """从适配后的分析结果中提取关键指标"""
        metrics = {}

        try:
            fd = results.get('frequency_domain', {})
            seat = fd.get('seat', {})
            pair = list(seat.values())[0] if seat else {}
            metrics['SEAT_Z'] = pair.get('Z', 1.0)
            metrics['SEAT_Y'] = pair.get('Y', 1.0)

            sf = results.get('shock_fatigue', {})
            sd_data = sf.get('iso2631_5', {})
            # 从嵌套结构 iso2631_5[loc_name]['实验组']['S_d'] 提取
            for loc_name in ['座垫', '靠背', '地板', '方向盘', '头部']:
                loc = sd_data.get(loc_name, {})
                if loc:
                    exp = loc.get('实验组', {})
                    sd_val = exp.get('S_d', 0)
                    if sd_val:
                        metrics['S_d'] = sd_val
                        break
            else:
                metrics['S_d'] = 0

            # 从 PSD 中推算共振峰
            psd = fd.get('psd', {})
            psd_z = psd.get('Az', {})
            if psd_z:
                if isinstance(psd_z, dict):
                    resonance_freq = max(psd_z.keys(), key=lambda k: float(psd_z[k]))
                    metrics['PSD_Z_peak_freq'] = float(resonance_freq)
                    metrics['PSD_Z_peak'] = psd_z.get(str(resonance_freq), 0)
                else:
                    metrics['PSD_Z_peak_freq'] = 5.0
                    metrics['PSD_Z_peak'] = 0

            td = results.get('time_domain', {})
            td_gyro = td.get('gyro', {})
            metrics['Gz_rms'] = td_gyro.get('座垫', {}).get('Gz_rms', 0)
        except Exception as e:
            logger.debug(f"指标提取跳过: {e}")

        return metrics

    def generate_report(self, recommendations: List[TuningRecommendation]) -> str:
        """生成调校报告 Markdown"""
        if not recommendations:
            return "✅ 当前座椅调校状态良好，无需调整。\n"

        lines = ["## 座椅调校建议\n"]

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"### 建议 {i}: {rec.component} — {rec.parameter}")
            lines.append("| 项目 | 值 |")
            lines.append("|:---|---|")
            lines.append(f"| 当前值 | {rec.current_value or '—'} |")
            lines.append(f"| 目标值 | {rec.target_value or '—'} |")
            lines.append(f"| 调整方向 | {rec.direction} |")
            lines.append(f"| 置信度 | {rec.confidence:.0%} |")
            lines.append(f"| 原因 | {rec.reason} |")
            lines.append(f"| 预期效果 | {rec.expected_improvement} |")
            lines.append("")

        return '\n'.join(lines)