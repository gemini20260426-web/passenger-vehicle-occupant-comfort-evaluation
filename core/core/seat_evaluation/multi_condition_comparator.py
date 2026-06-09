#!/usr/bin/env python3
"""
多工况对比分析 — 同一座椅在不同工况下的表现
典型工况: 城市(30km/h) / 乡村(60km/h) / 高速(100km/h) / 急刹 / 转弯
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass
class ConditionResult:
    name: str              # 工况名
    speed: float           # 速度 km/h
    comfort_index: float   # 舒适度
    vdv_z: float           # VDV Z轴
    seat_z: float          # SEAT因子
    sd: float              # S_d
    events: List[str] = field(default_factory=list)


class MultiConditionComparator:
    """多工况对比分析器"""

    CONDITIONS = [
        {'name': '城市低速', 'speed_range': (0, 30), 'label': '城市'},
        {'name': '市郊中速', 'speed_range': (30, 60), 'label': '市郊'},
        {'name': '高速', 'speed_range': (60, 120), 'label': '高速'},
        {'name': '制动', 'speed_range': None, 'label': '紧急制动', 'detect': 'brake'},
        {'name': '转弯', 'speed_range': None, 'label': '大角度转弯', 'detect': 'steer'},
    ]

    def compare(self, results_by_condition: Dict[str, dict]) -> Dict:
        """多工况对比 → 雷达图 + 排名表"""
        comparison = {
            'conditions': [],
            'best': None,
            'worst': None,
            'recommendations': [],
            'radar_image': None,
        }

        for cond_name, result in results_by_condition.items():
            try:
                from core.core.seat_evaluation.comfort_index import ComfortIndexCalculator
                calc = ComfortIndexCalculator()
                ci = calc.compute(result)

                comparison['conditions'].append({
                    'name': cond_name,
                    'comfort_index': ci.overall_score,
                    'grade': ci.grade,
                    'vibration_score': ci.vibration_score,
                    'shock_score': ci.shock_score,
                    'transfer_score': ci.transfer_score,
                    'posture_score': ci.posture_score,
                })
            except Exception as e:
                logger.warning(f"工况 {cond_name} 对比跳过: {e}")

        # 排序
        conds = sorted(comparison['conditions'], key=lambda x: x['comfort_index'], reverse=True)
        if conds:
            comparison['best'] = conds[0]['name']
            comparison['worst'] = conds[-1]['name']

        # 生成建议
        comparison['recommendations'] = self._generate_recommendations(conds)

        # 生成雷达图
        try:
            comparison['radar_image'] = self._plot_radar(conds)
        except Exception as e:
            logger.warning(f"雷达图生成失败: {e}")

        return comparison

    def _generate_recommendations(self, conds):
        recs = []
        for c in conds:
            if c['comfort_index'] < 55:
                recs.append(
                    f"⚠️ {c['name']}: 舒适度{c['grade']}级({c['comfort_index']:.0f})，"
                    f"振动得分{c['vibration_score']:.0f}，建议增强隔振"
                )
            elif c['comfort_index'] < 70:
                recs.append(
                    f"⚡ {c['name']}: 舒适度{c['grade']}级({c['comfort_index']:.0f})，"
                    f"可通过微调阻尼改善"
                )
        return recs

    def _plot_radar(self, conds) -> Optional[bytes]:
        """多工况雷达图"""
        if len(conds) < 2:
            return None

        categories = ['振动', '冲击', '传递', '姿态']
        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
        for i, c in enumerate(conds):
            vals = [
                c.get('vibration_score', 0),
                c.get('shock_score', 0),
                c.get('transfer_score', 0),
                c.get('posture_score', 0),
            ]
            vals += vals[:1]
            ax.fill(angles, vals, alpha=0.1, color=colors[i % len(colors)])
            ax.plot(angles, vals, 'o-', linewidth=2, color=colors[i % len(colors)],
                    label=f"{c['name']} ({c['grade']}级)")

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        ax.set_ylim(0, 100)
        ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=9)
        ax.set_title('多工况舒适度对比雷达图', fontsize=14, pad=20)

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()