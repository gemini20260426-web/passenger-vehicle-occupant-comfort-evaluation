#!/usr/bin/env python3
"""
趋势监测 — 多次测试的关键指标趋势追踪
识别座椅性能退化 / 改进效果 / 异常突变
"""

import os
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import logging
logger = logging.getLogger(__name__)


@dataclass
class TrendPoint:
    timestamp: str
    comfort_index: float
    seat_z: float
    vdv_z: float
    sd: float
    label: str = ''


@dataclass
class TrendAlert:
    type: str          # degradation / improvement / anomaly
    metric: str        # 指标名
    severity: str      # warning / critical / info
    message: str


class TrendMonitor:
    """趋势监测器

    持久化: JSON 文件存储历史记录，重启不丢失
    """

    DEGRADATION_THRESHOLD = 0.15  # 15% 下降 = 退化
    ANOMALY_SIGMA = 3.0           # 3σ = 异常

    def __init__(self, history: List[Dict] = None, storage_path: str = None):
        self.history: List[TrendPoint] = []
        self.storage_path = storage_path or 'data_output/trend_history.json'

        # 从 JSON 文件加载历史
        if history:
            for h in history:
                self.add_point(h)
        elif os.path.exists(self.storage_path):
            self._load_from_file()

    def add_point(self, result: dict):
        """添加一次测试结果"""
        try:
            from core.core.seat_evaluation.comfort_index import ComfortIndexCalculator
            calc = ComfortIndexCalculator()
            ci = calc.compute(result)

            td = result.get('time_domain', {})
            vdv = td.get('vdv', {}).get('座垫', {}).get('实验组', {})
            fd = result.get('frequency_domain', {})
            seat = fd.get('seat', {})
            pair = list(seat.values())[0] if seat else {}

            point = TrendPoint(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
                comfort_index=ci.overall_score,
                seat_z=pair.get('Z', 1.0),
                vdv_z=vdv.get('Z', 0),
                sd=self._extract_sd(result.get('shock_fatigue', {})),
            )
            self.history.append(point)

            # 持久化
            self._save_to_file()

            # 自动检测告警
            alerts = self.check_alerts()
            if alerts:
                for a in alerts:
                    logger.warning(f"[{a.severity.upper()}] {a.type}: {a.message}")

        except Exception as e:
            logger.warning(f"趋势监测点添加失败: {e}")

    @staticmethod
    def _extract_sd(shock_fatigue: dict) -> float:
        """从 shock_fatigue 嵌套结构中安全提取 S_d 值"""
        iso = shock_fatigue.get('iso2631_5', {})
        for loc_name in ['座垫', '靠背', '地板', '方向盘', '头部']:
            loc = iso.get(loc_name, {})
            if loc:
                exp = loc.get('实验组', {})
                sd = exp.get('S_d', 0)
                if sd:
                    return sd
        for loc_data in iso.values():
            if isinstance(loc_data, dict):
                exp = loc_data.get('实验组', {})
                sd = exp.get('S_d', 0)
                if sd:
                    return sd
        return 0.0

    # 指标方向: True = 越高越好, False = 越低越好
    METRIC_DIRECTION = {
        'comfort_index': True,   # 越高越舒适
        'seat_z': False,         # 越低隔振越好
        'vdv_z': False,          # 越低越舒适
        'sd': False,             # 越低冲击越小
    }

    def check_alerts(self) -> List[TrendAlert]:
        """检测趋势异常"""
        if len(self.history) < 2:
            return []

        alerts = []
        latest = self.history[-1]
        prev = self.history[-2]

        # 退化检测
        for metric, name, threshold in [
            ('comfort_index', '舒适度指数', 0.10),
            ('seat_z', 'SEAT_Z', 0.05),
            ('vdv_z', 'VDV_Z', 0.15),
            ('sd', 'S_d', 0.10),
        ]:
            new_val = getattr(latest, metric)
            old_val = getattr(prev, metric)

            if old_val > 0:
                change = (new_val - old_val) / old_val
                higher_is_better = self.METRIC_DIRECTION.get(metric, True)
                # 退化: 好指标下降 或 坏指标上升
                is_degraded = (higher_is_better and change < -threshold) or \
                              (not higher_is_better and change > threshold)
                if is_degraded:
                    direction = '↓' if change < 0 else '↑'
                    alerts.append(TrendAlert(
                        type='degradation',
                        metric=metric,
                        severity='warning',
                        message=f"{name}: {old_val:.2f} → {new_val:.2f} ({direction} {abs(change) * 100:.0f}%)"
                    ))

        # 异常突变检测 (需要 ≥ 5 个点)
        if len(self.history) >= 5:
            ci_values = [p.comfort_index for p in self.history[:-1]]
            mean, std = np.mean(ci_values), np.std(ci_values)
            if std > 0 and abs(latest.comfort_index - mean) > self.ANOMALY_SIGMA * std:
                alerts.append(TrendAlert(
                    type='anomaly',
                    metric='comfort_index',
                    severity='critical',
                    message=f"舒适度突变! 当前: {latest.comfort_index:.0f}, 历史均值: {mean:.0f}±{std:.0f}"
                ))

        return alerts

    def get_trend_summary(self) -> dict:
        """趋势摘要"""
        if len(self.history) < 2:
            return {'status': 'insufficient_data', 'message': '数据不足, 需 ≥2 次测试'}

        ci_values = [p.comfort_index for p in self.history]
        ci_trend = np.polyfit(range(len(ci_values)), ci_values, 1)[0]

        return {
            'total_tests': len(self.history),
            'first_comfort': self.history[0].comfort_index,
            'latest_comfort': self.history[-1].comfort_index,
            'trend': 'improving' if ci_trend > 0.5 else 'degrading' if ci_trend < -0.5 else 'stable',
            'trend_slope': round(ci_trend, 2),
            'alerts': [
                {'type': a.type, 'metric': a.metric, 'severity': a.severity, 'message': a.message}
                for a in self.check_alerts()
            ],
        }

    # ── 持久化 ──

    def _save_to_file(self):
        """保存历史到 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = [
                {
                    'timestamp': p.timestamp,
                    'comfort_index': p.comfort_index,
                    'seat_z': p.seat_z,
                    'vdv_z': p.vdv_z,
                    'sd': p.sd,
                    'label': p.label,
                }
                for p in self.history
            ]
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"趋势历史保存失败: {e}")

    def _load_from_file(self):
        """从 JSON 文件加载历史"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                self.history.append(TrendPoint(
                    timestamp=item.get('timestamp', ''),
                    comfort_index=item.get('comfort_index', 0),
                    seat_z=item.get('seat_z', 0),
                    vdv_z=item.get('vdv_z', 0),
                    sd=item.get('sd', 0),
                    label=item.get('label', ''),
                ))
            logger.info(f"趋势监测: 从 {self.storage_path} 加载了 {len(self.history)} 个历史点")
        except Exception as e:
            logger.debug(f"趋势历史加载失败: {e}")

    def clear(self):
        """清除历史"""
        self.history.clear()
        if os.path.exists(self.storage_path):
            try:
                os.remove(self.storage_path)
            except Exception:
                pass