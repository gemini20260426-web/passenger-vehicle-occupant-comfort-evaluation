#!/usr/bin/env python3
"""
主观评价映射 — 客观指标 → 乘客主观感受
依据: ISO 2631-1 附录C, VDI 2057, 心理物理学映射
"""

import numpy as np


class SubjectiveMapping:
    """客观指标 → 主观评价 映射器

    输出示例:
        "在 30km/h 城市道路条件下，乘员感受到 '轻微不舒适'，
         主要来源于垂向振动 (贡献 60%) 和侧向摇摆 (贡献 25%)。"
    """

    # 主观等级 (ISO 2631-1 表 C.1)
    SUBJECTIVE_SCALE = {
        1: '无不适感',
        2: '轻微不适',
        3: '中等不适',
        4: '明显不适',
        5: '严重不适',
        6: '极端不适',
    }

    # 加速度 → 主观等级映射 (m/s² RMS, 加权)
    @staticmethod
    def aw_to_discomfort(aw_z: float, aw_xy: float) -> dict:
        """频率加权加速度 → 主观不适等级"""
        # 综合加权 (Z轴主导)
        aw_total = np.sqrt((1.4 * aw_z) ** 2 + aw_xy ** 2)

        # 阈值 (ISO 2631-1)
        if aw_total < 0.315:
            level = 1
        elif aw_total < 0.5:
            level = 2
        elif aw_total < 0.8:
            level = 3
        elif aw_total < 1.25:
            level = 4
        elif aw_total < 2.0:
            level = 5
        else:
            level = 6

        # 贡献分解
        z_contrib = (1.4 * aw_z) ** 2 / (aw_total ** 2 + 0.001)
        xy_contrib = (aw_xy ** 2 * 2) / (aw_total ** 2 + 0.001)

        return {
            'level': level,
            'label': SubjectiveMapping.SUBJECTIVE_SCALE[level],
            'aw_total': round(aw_total, 3),
            'z_contribution': round(z_contrib * 100),
            'xy_contribution': round(xy_contrib * 100),
            'main_source': '垂向振动' if z_contrib > xy_contrib else '侧向摇摆',
        }

    @staticmethod
    def generate_narrative(speed: float, condition: dict, discomfort: dict) -> str:
        """生成自然语言描述"""
        templates = {
            1: "在 {speed:.0f}km/h {cond}条件下，乘员{feel}。座椅表现优秀，满足长途舒适性要求。",
            2: "在 {speed:.0f}km/h {cond}条件下，乘员感受到'轻微不适'，主要来源于{source}(贡献{contrib}%)。建议优化{source}方向的阻尼特性。",
            3: "在 {speed:.0f}km/h {cond}条件下，乘员感受到'中等不适'。以{source}为主(贡献{contrib}%)，长时间乘坐可能产生疲劳感。建议增强{source}方向的隔振能力。",
            4: "在 {speed:.0f}km/h {cond}条件下，乘员感受到'明显不适'！{source}(贡献{contrib}%)为主要来源。需重点优化该方向的减振系统，否则影响乘坐体验。",
            5: "⚠️ 在 {speed:.0f}km/h {cond}条件下，乘员感受到'严重不适'！当前座椅系统无法有效隔离{source}方向的振动，强烈建议重新设计减振方案。",
            6: "🚨 在 {speed:.0f}km/h {cond}条件下，乘员感受到'极端不适'！当前座椅配置不可接受，必须立即改进{source}方向的隔振性能。",
        }

        tmpl = templates.get(discomfort['level'], templates[3])
        return tmpl.format(
            speed=speed,
            cond=condition.get('name', '城市'),
            feel=discomfort['label'],
            source=discomfort['main_source'],
            contrib=discomfort['z_contribution'] if discomfort['z_contribution'] > discomfort['xy_contribution'] else discomfort['xy_contribution'],
        )