#!/usr/bin/env python3
"""
舒适度综合指数 — 多维度加权合成单一评分
依据: ISO 2631-1 附录C, VDI 2057, 行业经验权重
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict

import logging
logger = logging.getLogger(__name__)


@dataclass
class ComfortIndex:
    """舒适度综合指数 (0-100, 越高越舒适)"""

    # 分项得分 (0-100)
    vibration_score: float = 0       # 振动 (VDV/SEAT)
    shock_score: float = 0           # 冲击 (S_d)
    posture_score: float = 0         # 姿态 (角速度)
    transfer_score: float = 0        # 传递 (衰减率)
    overall_score: float = 0         # 综合

    # 原始数据
    details: Dict = field(default_factory=dict)
    grade: str = 'N/A'               # A/B/C/D/E

    # 等级阈值 (指数 → 等级)
    GRADE_THRESHOLDS = [
        (85, 'A', '极佳 — 豪华车水准'),
        (70, 'B', '良好 — 可在长途使用'),
        (55, 'C', '一般 — 短途可接受'),
        (40, 'D', '较差 — 需改进'),
        (0,  'E', '差 — 不可接受'),
    ]


class ComfortIndexCalculator:
    """舒适度指数计算器

    用法:
        calc = ComfortIndexCalculator()
        index = calc.compute(analysis_results)
        print(f"综合舒适度: {index.overall_score:.0f}/100 ({index.grade}级)")
    """

    def __init__(self):
        # 权重配置 (可调)
        self.weights = {
            'vibration': 0.35,    # 振动 (最重要)
            'shock': 0.25,        # 冲击
            'transfer': 0.25,     # 传递衰减
            'posture': 0.15,      # 姿态稳定性
        }

        # VDV → 得分映射 (ISO 2631-1 表 C.1)
        self.VDV_THRESHOLDS = {
            'X': [(0, 100), (3.0, 80), (6.0, 60), (9.0, 40), (12.0, 20)],
            'Y': [(0, 100), (3.0, 80), (6.0, 60), (9.0, 40), (12.0, 20)],
            'Z': [(0, 100), (4.0, 80), (8.0, 60), (12.0, 40), (16.0, 20)],
        }

        # S_d → 得分映射
        self.SD_THRESHOLDS = [
            (0.3, 100), (0.5, 80), (0.8, 60), (1.0, 40), (1.2, 20)
        ]

    def compute(self, results: dict) -> ComfortIndex:
        """计算舒适度综合指数

        Args:
            results: 已适配的分析结果字典 (来自 _normalize_results)
        """
        ci = ComfortIndex()

        try:
            # 1. 振动得分 (基于VDV)
            td = results.get('time_domain', {})
            vdv = td.get('vdv', {})
            seat_vdv = vdv.get('座垫', {})

            vdv_x = seat_vdv.get('实验组', {}).get('X', 0)
            vdv_y = seat_vdv.get('实验组', {}).get('Y', 0)
            vdv_z = seat_vdv.get('实验组', {}).get('Z', 0)

            score_x = self._linear_interp(vdv_x, self.VDV_THRESHOLDS['X'])
            score_y = self._linear_interp(vdv_y, self.VDV_THRESHOLDS['Y'])
            score_z = self._linear_interp(vdv_z, self.VDV_THRESHOLDS['Z'])
            ci.vibration_score = (score_x * 0.3 + score_y * 0.3 + score_z * 0.4)

            # 2. 冲击得分 (基于 S_d)
            sf = results.get('shock_fatigue', {})
            sd = self._extract_sd(sf)
            ci.shock_score = self._linear_interp(sd, self.SD_THRESHOLDS)

            # 3. 传递衰减得分
            atten = results.get('attenuation', {})
            vals = [v.get('overall', 0) for v in atten.values() if isinstance(v, dict)]
            avg_atten = np.mean(vals) if vals else 0
            ci.transfer_score = max(0, min(100, avg_atten * 2))  # 50%衰减=100分

            # 4. 姿态得分 (基于角速度)
            td_gyro = td.get('gyro', {})
            gz_rms = td_gyro.get('座垫', {}).get('Gz_rms', 0)
            ci.posture_score = max(0, 100 - gz_rms * 10)  # 10°/s = 0分

            # 5. 加权合成
            ci.overall_score = (
                ci.vibration_score * self.weights['vibration'] +
                ci.shock_score * self.weights['shock'] +
                ci.transfer_score * self.weights['transfer'] +
                ci.posture_score * self.weights['posture']
            )

            # 6. 等级判定
            for threshold, grade, label in ci.GRADE_THRESHOLDS:
                if ci.overall_score >= threshold:
                    ci.grade = grade
                    ci.details['grade_label'] = label
                    break

            ci.details.update({
                'vibration_score': ci.vibration_score,
                'shock_score': ci.shock_score,
                'transfer_score': ci.transfer_score,
                'posture_score': ci.posture_score,
                'weights': self.weights,
            })

        except Exception as e:
            logger.warning(f"舒适度计算部分失败: {e}")

        return ci

    @staticmethod
    def _linear_interp(value, thresholds):
        """线性插值: value → score"""
        for i, (v1, s1) in enumerate(thresholds):
            if value <= v1:
                if i == 0:
                    return s1
                v0, s0 = thresholds[i - 1]
                return s0 + (s1 - s0) * (value - v0) / (v1 - v0) if v1 > v0 else s0
        return thresholds[-1][1]

    @staticmethod
    def _extract_sd(shock_fatigue: dict) -> float:
        """从 shock_fatigue 嵌套结构中安全提取 S_d 值

        结构: iso2631_5[loc_name]['实验组']['S_d']
        优先取第一个位置的实验组 S_d
        """
        iso = shock_fatigue.get('iso2631_5', {})
        for loc_name in ['座垫', '靠背', '地板', '方向盘', '头部']:
            loc_data = iso.get(loc_name, {})
            if loc_data:
                exp = loc_data.get('实验组', {})
                sd = exp.get('S_d', 0)
                if sd:
                    return sd
        # 回退: 遍历所有位置
        for loc_data in iso.values():
            if isinstance(loc_data, dict):
                exp = loc_data.get('实验组', {})
                sd = exp.get('S_d', 0)
                if sd:
                    return sd
        return 0.0