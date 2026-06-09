#!/usr/bin/env python3
"""
脊柱健康评估 — ISO 2631-5 冲击振动对脊柱的累积损伤评估

核心指标:
  1. S_e — 等效静态压缩应力 (MPa)
  2. R — 脊柱损伤风险因子 (R = S_e / S_ut, 其中 S_ut = 0.5 MPa 为椎体极限强度)
  3. 风险等级: R < 0.5 低 / 0.5-0.8 中 / > 0.8 高

算法依据:
  - ISO 2631-5:2018 Annex C: 加速度剂量模型
  - D_k = [Σ A_k^6 * Δt]^(1/6)  (各轴加速度剂量)
  - S_e = [(Σ m_k * D_k^6) / Σ m_k]^(1/6)  (等效静态压缩)
  - m_x = 0.015, m_y = 0.035, m_z = 0.032 (MPa·s 单位转换因子)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass
class SpineHealthResult:
    """脊柱健康评估结果"""

    # 各轴加速度剂量 D_k (m/s^2)
    d_x: float = 0
    d_y: float = 0
    d_z: float = 0

    # 等效静态压缩应力 S_e (MPa)
    s_e: float = 0

    # 风险因子 R
    risk_factor: float = 0

    # 风险等级
    risk_level: str = 'N/A'       # 低/中/高
    risk_label: str = 'N/A'

    # 每日允许暴露次数 (参考)
    daily_exposure: str = 'N/A'

    # 详细数据
    details: Dict = field(default_factory=dict)

    # 风险等级阈值
    RISK_THRESHOLDS = [
        (0.5, '低', '脊柱损伤风险低 — 可接受'),
        (0.8, '中', '脊柱损伤风险中等 — 建议关注'),
        (float('inf'), '高', '脊柱损伤风险高 — 需改进'),
    ]


class SpineHealthCalculator:
    """ISO 2631-5 脊柱健康计算器

    用法:
        calc = SpineHealthCalculator()
        result = calc.compute(analysis_results)
        print(f"脊柱风险: {result.risk_level} (R={result.risk_factor:.2f})")
    """

    # 轴间耦合系数 (MPa·s / m^6)^(1/6) — 将加速度剂量转换为应力
    AXIS_FACTORS = {
        'X': 0.015,   # 前后方向
        'Y': 0.035,   # 左右方向
        'Z': 0.032,   # 垂直方向 (主要)
    }

    # 椎体极限强度 (MPa)
    S_UT = 0.5

    def __init__(self, sampling_rate: float = 100.0):
        self.sampling_rate = sampling_rate

    def compute(self, results: dict) -> SpineHealthResult:
        """计算脊柱健康评估

        Args:
            results: 已适配的分析结果 (来自 _normalize_results)

        Returns:
            SpineHealthResult
        """
        sr = SpineHealthResult()

        try:
            # 1. 从时域提取加速度峰值
            td = results.get('time_domain', {})
            acc_peak = td.get('acc_peak', {})
            seat_acc = acc_peak.get('座垫', {}).get('实验组', {})

            # 使用加速度峰值和VDV近似计算D_k
            # D_k ≈ a_peak * T^(1/6)  (简化近似)
            vdv = td.get('vdv', {})
            seat_vdv = vdv.get('座垫', {}).get('实验组', {})

            # 从VDV计算累积剂量: VDV ≈ a * T^(1/4), D_k = VDV * T^(1/12)
            # 注: ISO 2631-5 Annex C 要求 D_k 单位为 m/s²
            T = results.get('metadata', {}).get('duration_s', 600)
            T_factor = T ** (1/12) if T > 0 else 1.0
            sr.d_x = seat_vdv.get('X', 0) * T_factor
            sr.d_y = seat_vdv.get('Y', 0) * T_factor
            sr.d_z = seat_vdv.get('Z', 0) * T_factor

            # 2. 计算 S_e (等效静态压缩应力)
            # S_e = [ (m_x * D_x^6 + m_y * D_y^6 + m_z * D_z^6) / (m_x + m_y + m_z) ]^(1/6)
            d6_x = sr.d_x ** 6
            d6_y = sr.d_y ** 6
            d6_z = sr.d_z ** 6

            m_sum = self.AXIS_FACTORS['X'] + self.AXIS_FACTORS['Y'] + self.AXIS_FACTORS['Z']
            weighted_d6 = (
                self.AXIS_FACTORS['X'] * d6_x +
                self.AXIS_FACTORS['Y'] * d6_y +
                self.AXIS_FACTORS['Z'] * d6_z
            )
            sr.s_e = (weighted_d6 / m_sum) ** (1/6) if m_sum > 0 else 0

            # 3. 计算风险因子 R
            sr.risk_factor = sr.s_e / self.S_UT if self.S_UT > 0 else 0

            # 4. 风险等级
            for threshold, level, label in sr.RISK_THRESHOLDS:
                if sr.risk_factor <= threshold:
                    sr.risk_level = level
                    sr.risk_label = label
                    break

            # 5. 每日暴露次数估算
            sr.daily_exposure = self._estimate_daily_exposure(sr.risk_factor)

            sr.details = {
                'd_x': round(sr.d_x, 2),
                'd_y': round(sr.d_y, 2),
                'd_z': round(sr.d_z, 2),
                's_e': round(sr.s_e, 3),
                'risk_factor': round(sr.risk_factor, 3),
                's_ut': self.S_UT,
                'axis_factors': self.AXIS_FACTORS,
            }

        except Exception as e:
            logger.warning(f"脊柱健康计算失败: {e}")

        return sr

    @staticmethod
    def _estimate_daily_exposure(risk: float) -> str:
        """根据风险因子估算每日允许暴露次数"""
        if risk <= 0.3:
            return '> 100 次/天'
        elif risk <= 0.5:
            return '50-100 次/天'
        elif risk <= 0.8:
            return '10-50 次/天'
        else:
            return '< 10 次/天 — 建议减少暴露'