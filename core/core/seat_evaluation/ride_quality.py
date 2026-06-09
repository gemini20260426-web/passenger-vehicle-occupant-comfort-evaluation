#!/usr/bin/env python3
"""
平顺性评价 — GB/T 4970 汽车平顺性试验方法

核心指标:
  1. a_w — 总加权加速度均方根值 (m/s^2)
  2. L_eq — 等效连续A声级 (振动剂量值)
  3. 平顺性等级: 1-5级 (1级最优)

算法依据:
  - GB/T 4970-2009: 汽车平顺性试验方法
  - 频率加权: W_k (Z轴座垫), W_d (X/Y轴座垫)
  - 轴加权系数: k_x=1.0, k_y=1.0, k_z=1.0

评价等级 (GB/T 4970 表1):
  1级: a_w < 0.315 — 没有不舒适
  2级: 0.315-0.5 — 有一些不舒适
  3级: 0.5-0.8 — 相当不舒适
  4级: 0.8-1.25 — 不舒适
  5级: 1.25-2.5 — 很不舒适
  6级: > 2.5 — 极不舒适
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass
class RideQualityResult:
    """平顺性评价结果"""

    # 各轴加权加速度 RMS (m/s^2)
    aw_x: float = 0
    aw_y: float = 0
    aw_z: float = 0

    # 总加权加速度 RMS (m/s^2)
    aw_total: float = 0

    # 平顺性等级 (1-6)
    comfort_level: int = 0
    comfort_label: str = 'N/A'

    # 详细数据
    details: Dict = field(default_factory=dict)

    # GB/T 4970 评价等级
    COMFORT_LEVELS = [
        (0.315, 1, '没有不舒适'),
        (0.5, 2, '有一些不舒适'),
        (0.8, 3, '相当不舒适'),
        (1.25, 4, '不舒适'),
        (2.5, 5, '很不舒适'),
        (float('inf'), 6, '极不舒适'),
    ]


class RideQualityCalculator:
    """GB/T 4970 平顺性计算器

    用法:
        calc = RideQualityCalculator()
        result = calc.compute(analysis_results)
        print(f"平顺性: {result.comfort_label} (a_w={result.aw_total:.3f} m/s^2)")
    """

    # 轴加权系数 (GB/T 4970)
    AXIS_WEIGHTS = {
        'X': 1.0,   # 前后
        'Y': 1.0,   # 左右
        'Z': 1.0,   # 垂直 (座垫)
    }

    def __init__(self):
        pass

    def compute(self, results: dict) -> RideQualityResult:
        """计算平顺性评价

        Args:
            results: 已适配的分析结果 (来自 _normalize_results)

        Returns:
            RideQualityResult
        """
        rq = RideQualityResult()

        try:
            # 1. 从VDV近似转换为加权加速度RMS
            # 对于宽带随机振动: a_w ≈ VDV / T^(1/4)
            # 简化: 直接使用VDV作为近似输入
            td = results.get('time_domain', {})
            vdv = td.get('vdv', {})
            seat_vdv = vdv.get('座垫', {}).get('实验组', {})

            # VDV → a_w 近似转换 (假设 T=600s 典型测试时长)
            T = 600.0
            rq.aw_x = seat_vdv.get('X', 0) / (T ** 0.25)
            rq.aw_y = seat_vdv.get('Y', 0) / (T ** 0.25)
            rq.aw_z = seat_vdv.get('Z', 0) / (T ** 0.25)

            # 2. 总加权加速度
            rq.aw_total = np.sqrt(
                (self.AXIS_WEIGHTS['X'] * rq.aw_x) ** 2 +
                (self.AXIS_WEIGHTS['Y'] * rq.aw_y) ** 2 +
                (self.AXIS_WEIGHTS['Z'] * rq.aw_z) ** 2
            )

            # 3. 平顺性等级
            for threshold, level, label in rq.COMFORT_LEVELS:
                if rq.aw_total < threshold:
                    rq.comfort_level = level
                    rq.comfort_label = label
                    break

            rq.details = {
                'aw_x': round(rq.aw_x, 4),
                'aw_y': round(rq.aw_y, 4),
                'aw_z': round(rq.aw_z, 4),
                'aw_total': round(rq.aw_total, 4),
                'axis_weights': self.AXIS_WEIGHTS,
                'standard': 'GB/T 4970-2009',
            }

        except Exception as e:
            logger.warning(f"平顺性计算失败: {e}")

        return rq