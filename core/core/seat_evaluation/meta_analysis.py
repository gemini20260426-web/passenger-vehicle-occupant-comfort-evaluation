#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多志愿者统计融合模块 (F3: Meta-Analysis)

提供跨志愿者/跨趟次的群体统计分析功能：
- 多志愿者指标聚合 (均值/标准差/置信区间)
- 跨趟次重复性分析 (ICC/SEM)
- 群体效应量计算 (Cohen's d / Hedges' g)
- 志愿者间变异分解 (ANOVA)
- Meta-Analysis综合报告生成

参考: ISO 2631-1:1997/Amd 1:2010, ISO 10326-2:2001
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class VolunteerMeta:
    """志愿者元数据"""
    volunteer_id: str
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    gender: Optional[str] = None
    notes: str = ''


@dataclass
class SessionMeta:
    """采集趟次元数据"""
    session_id: str
    volunteer_id: str
    timestamp: float = 0.0
    condition: str = 'experimental'  # experimental / control
    seat_type: str = ''
    vehicle_speed_kmh: float = 0.0
    road_type: str = ''
    duration_s: float = 0.0
    notes: str = ''


@dataclass
class GroupStatistics:
    """群体统计结果"""
    metric_id: str
    n_samples: int
    n_volunteers: int
    mean: float
    std: float
    sem: float  # 标准误
    ci_95_lower: float
    ci_95_upper: float
    cv_pct: float  # 变异系数
    min_val: float
    max_val: float
    median: float
    p25: float
    p75: float


@dataclass
class CrossSessionResult:
    """跨趟次重复性结果"""
    metric_id: str
    icc: float  # 组内相关系数
    icc_ci_lower: float
    icc_ci_upper: float
    icc_grade: str  # poor/moderate/good/excellent
    sem: float  # 测量标准误
    mdc_95: float  # 最小可检测变化 (95%置信)
    cv_within_pct: float  # 趟次内变异系数


@dataclass
class EffectSizeResult:
    """效应量结果"""
    metric_id: str
    cohens_d: float
    hedges_g: float
    effect_magnitude: str  # negligible/small/medium/large
    ci_95_lower: float
    ci_95_upper: float
    p_value: Optional[float] = None


class MetaAnalyzer:
    """多志愿者统计融合分析器 (F3)

    功能:
    - 多志愿者指标聚合
    - 跨趟次重复性分析
    - 群体效应量计算
    - 志愿者间变异分解
    - Meta-Analysis综合报告
    """

    def __init__(self):
        self._volunteers: Dict[str, VolunteerMeta] = {}
        self._sessions: Dict[str, SessionMeta] = {}
        # 原始数据: {metric_id: {volunteer_id: {session_id: value}}}
        self._data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def register_volunteer(self, volunteer: VolunteerMeta):
        """注册志愿者"""
        self._volunteers[volunteer.volunteer_id] = volunteer
        logger.info(f"志愿者已注册: {volunteer.volunteer_id}")

    def register_session(self, session: SessionMeta):
        """注册采集趟次"""
        self._sessions[session.session_id] = session
        if session.volunteer_id not in self._volunteers:
            self._volunteers[session.volunteer_id] = VolunteerMeta(
                volunteer_id=session.volunteer_id
            )
        logger.debug(f"趟次已注册: {session.session_id} (volunteer={session.volunteer_id})")

    def add_metric_value(self, metric_id: str, volunteer_id: str,
                         session_id: str, value: float):
        """添加单次指标值"""
        self._data[metric_id][volunteer_id][session_id] = value

    def add_session_results(self, volunteer_id: str, session_id: str,
                            metrics: Dict[str, float]):
        """批量添加一趟次的所有指标结果"""
        for metric_id, value in metrics.items():
            self.add_metric_value(metric_id, volunteer_id, session_id, value)

    def get_group_statistics(self, metric_id: str,
                             volunteer_ids: List[str] = None) -> GroupStatistics:
        """计算群体统计 (跨志愿者聚合)

        Args:
            metric_id: 指标ID
            volunteer_ids: 指定志愿者列表, None则使用全部

        Returns:
            GroupStatistics: 群体统计结果
        """
        values = self._get_all_values(metric_id, volunteer_ids)
        if not values:
            return GroupStatistics(
                metric_id=metric_id, n_samples=0, n_volunteers=0,
                mean=0, std=0, sem=0, ci_95_lower=0, ci_95_upper=0,
                cv_pct=0, min_val=0, max_val=0, median=0, p25=0, p75=0
            )

        arr = np.array(values)
        n = len(arr)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0

        # 标准误
        sem = std / np.sqrt(n) if n > 0 else 0.0

        # 95% 置信区间 (t-distribution)
        if n > 1:
            from scipy import stats
            t_crit = stats.t.ppf(0.975, n - 1)
            ci_95_lower = mean - t_crit * sem
            ci_95_upper = mean + t_crit * sem
        else:
            ci_95_lower = mean
            ci_95_upper = mean

        # 变异系数
        cv_pct = (std / mean * 100) if abs(mean) > 1e-6 else 0.0

        # 志愿者计数
        if volunteer_ids:
            n_volunteers = len(volunteer_ids)
        else:
            n_volunteers = len(self._data.get(metric_id, {}))

        return GroupStatistics(
            metric_id=metric_id,
            n_samples=n,
            n_volunteers=n_volunteers,
            mean=mean, std=std, sem=sem,
            ci_95_lower=ci_95_lower, ci_95_upper=ci_95_upper,
            cv_pct=cv_pct,
            min_val=float(np.min(arr)), max_val=float(np.max(arr)),
            median=float(np.median(arr)),
            p25=float(np.percentile(arr, 25)),
            p75=float(np.percentile(arr, 75))
        )

    def compute_cross_session_repeatability(self, metric_id: str,
                                            volunteer_ids: List[str] = None
                                            ) -> CrossSessionResult:
        """跨趟次重复性分析 (ICC)

        使用 ICC(1,1) 模型: 单次测量, 绝对一致性
        """
        values_by_volunteer = self._get_values_by_volunteer(metric_id, volunteer_ids)
        valid_groups = {k: v for k, v in values_by_volunteer.items() if len(v) >= 2}

        if len(valid_groups) < 2:
            return CrossSessionResult(
                metric_id=metric_id, icc=0, icc_ci_lower=0, icc_ci_upper=0,
                icc_grade='insufficient_data', sem=0, mdc_95=0, cv_within_pct=0
            )

        # 计算 ICC(1,1) 单向随机效应模型
        group_means = []
        all_values = []
        group_sizes = []
        for vals in valid_groups.values():
            group_means.append(np.mean(vals))
            all_values.extend(vals)
            group_sizes.append(len(vals))

        grand_mean = np.mean(all_values)
        k = len(valid_groups)  # 组数 (志愿者数)
        n_total = len(all_values)

        # MSB: 组间均方
        ssb = sum(ni * (mi - grand_mean) ** 2 for ni, mi in zip(group_sizes, group_means))
        msb = ssb / (k - 1) if k > 1 else 0

        # MSW: 组内均方
        ssw = 0
        for vals in valid_groups.values():
            m = np.mean(vals)
            ssw += sum((v - m) ** 2 for v in vals)
        msw = ssw / (n_total - k) if n_total > k else 0

        # ICC(1,1)
        if msw > 0:
            icc = (msb - msw) / (msb + (np.mean(group_sizes) - 1) * msw)
            icc = max(0.0, min(1.0, icc))
        else:
            icc = 1.0 if msb > 0 else 0.0

        # ICC 等级
        if icc >= 0.9:
            icc_grade = 'excellent'
        elif icc >= 0.75:
            icc_grade = 'good'
        elif icc >= 0.5:
            icc_grade = 'moderate'
        elif icc >= 0.3:
            icc_grade = 'poor'
        else:
            icc_grade = 'very_poor'

        # SEM (Standard Error of Measurement)
        sem = np.sqrt(msw) if msw > 0 else 0.0

        # MDC_95 (Minimum Detectable Change)
        mdc_95 = 1.96 * np.sqrt(2) * sem

        # 趟次内变异系数
        within_cv_pct = (np.sqrt(msw) / abs(grand_mean) * 100) if abs(grand_mean) > 1e-6 else 0.0

        # ICC 置信区间 (F-distribution approximation)
        if k > 1 and n_total > k:
            from scipy import stats
            n0 = np.mean(group_sizes)
            f_val = msb / msw if msw > 0 else float('inf')
            f_lower = f_val / stats.f.ppf(0.975, k - 1, n_total - k) if f_val < float('inf') else float('inf')
            f_upper = f_val * stats.f.ppf(0.975, n_total - k, k - 1) if f_val < float('inf') else float('inf')
            icc_lower = (f_lower - 1) / (f_lower + n0 - 1) if f_lower < float('inf') else 1.0
            icc_upper = (f_upper - 1) / (f_upper + n0 - 1) if f_upper < float('inf') else 1.0
            icc_lower = max(0.0, min(1.0, icc_lower))
            icc_upper = max(0.0, min(1.0, icc_upper))
        else:
            icc_lower = icc_upper = icc

        return CrossSessionResult(
            metric_id=metric_id, icc=icc,
            icc_ci_lower=icc_lower, icc_ci_upper=icc_upper,
            icc_grade=icc_grade, sem=sem, mdc_95=mdc_95,
            cv_within_pct=within_cv_pct
        )

    def compute_effect_size(self, metric_id: str,
                            exp_volunteer_ids: List[str] = None,
                            ctrl_volunteer_ids: List[str] = None
                            ) -> EffectSizeResult:
        """计算实验组 vs 对照组效应量 (Cohen's d / Hedges' g)

        Args:
            metric_id: 指标ID
            exp_volunteer_ids: 实验组志愿者列表
            ctrl_volunteer_ids: 对照组志愿者列表

        Returns:
            EffectSizeResult: 效应量结果
        """
        exp_values = self._get_all_values(metric_id, exp_volunteer_ids)
        ctrl_values = self._get_all_values(metric_id, ctrl_volunteer_ids)

        if len(exp_values) < 2 or len(ctrl_values) < 2:
            return EffectSizeResult(
                metric_id=metric_id, cohens_d=0, hedges_g=0,
                effect_magnitude='insufficient_data',
                ci_95_lower=0, ci_95_upper=0
            )

        exp_arr = np.array(exp_values)
        ctrl_arr = np.array(ctrl_values)

        n1, n2 = len(exp_arr), len(ctrl_arr)
        m1, m2 = np.mean(exp_arr), np.mean(ctrl_arr)
        s1, s2 = np.std(exp_arr, ddof=1), np.std(ctrl_arr, ddof=1)

        # Cohen's d (pooled SD)
        pooled_sd = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
        if pooled_sd < 1e-10:
            cohens_d = 0.0
        else:
            cohens_d = (m1 - m2) / pooled_sd

        # Hedges' g (小样本校正)
        df = n1 + n2 - 2
        correction = 1 - 3 / (4 * df - 1) if df > 3 else 1.0
        hedges_g = cohens_d * correction

        # 效应量大小判断
        abs_d = abs(cohens_d)
        if abs_d < 0.2:
            magnitude = 'negligible'
        elif abs_d < 0.5:
            magnitude = 'small'
        elif abs_d < 0.8:
            magnitude = 'medium'
        else:
            magnitude = 'large'

        # 95% CI for Cohen's d
        se_d = np.sqrt((n1 + n2) / (n1 * n2) + cohens_d**2 / (2 * (n1 + n2)))
        ci_lower = cohens_d - 1.96 * se_d
        ci_upper = cohens_d + 1.96 * se_d

        # Welch's t-test p-value
        try:
            from scipy import stats
            t_stat, p_value = stats.ttest_ind(exp_arr, ctrl_arr, equal_var=False)
        except Exception:
            p_value = None

        return EffectSizeResult(
            metric_id=metric_id,
            cohens_d=cohens_d, hedges_g=hedges_g,
            effect_magnitude=magnitude,
            ci_95_lower=ci_lower, ci_95_upper=ci_upper,
            p_value=p_value
        )

    def compute_all_statistics(self, metric_ids: List[str] = None,
                               exp_volunteer_ids: List[str] = None,
                               ctrl_volunteer_ids: List[str] = None
                               ) -> Dict[str, Dict[str, Any]]:
        """计算所有指标的综合统计 (Meta-Analysis综合报告)

        Returns:
            {metric_id: {
                'group_stats': GroupStatistics,
                'repeatability': CrossSessionResult,
                'effect_size': EffectSizeResult (if both groups available)
            }}
        """
        if metric_ids is None:
            metric_ids = list(self._data.keys())

        results = {}
        for metric_id in metric_ids:
            metric_result = {
                'group_stats': self.get_group_statistics(metric_id, exp_volunteer_ids),
                'repeatability': self.compute_cross_session_repeatability(metric_id, exp_volunteer_ids),
            }

            if ctrl_volunteer_ids:
                metric_result['effect_size'] = self.compute_effect_size(
                    metric_id, exp_volunteer_ids, ctrl_volunteer_ids
                )
                metric_result['ctrl_group_stats'] = self.get_group_statistics(
                    metric_id, ctrl_volunteer_ids
                )

            results[metric_id] = metric_result

        return results

    def generate_meta_report(self, metric_ids: List[str] = None,
                             exp_volunteer_ids: List[str] = None,
                             ctrl_volunteer_ids: List[str] = None) -> Dict[str, Any]:
        """生成Meta-Analysis综合报告

        Returns:
            结构化报告字典，可直接用于UI渲染或导出
        """
        all_stats = self.compute_all_statistics(metric_ids, exp_volunteer_ids, ctrl_volunteer_ids)

        # 汇总统计
        n_volunteers = len(exp_volunteer_ids) if exp_volunteer_ids else len(self._volunteers)
        n_sessions = len(self._sessions)
        n_metrics = len(all_stats)

        # 志愿者间变异汇总
        cv_summary = []
        for metric_id, stats in all_stats.items():
            gs = stats['group_stats']
            if gs.n_samples > 0:
                cv_summary.append({
                    'metric_id': metric_id,
                    'cv_pct': gs.cv_pct,
                    'mean': gs.mean,
                    'ci_range': gs.ci_95_upper - gs.ci_95_lower
                })

        cv_summary.sort(key=lambda x: x['cv_pct'], reverse=True)

        # 效应量汇总
        effect_summary = []
        for metric_id, stats in all_stats.items():
            if 'effect_size' in stats:
                es = stats['effect_size']
                effect_summary.append({
                    'metric_id': metric_id,
                    'cohens_d': es.cohens_d,
                    'hedges_g': es.hedges_g,
                    'magnitude': es.effect_magnitude,
                    'p_value': es.p_value,
                    'significant': es.p_value is not None and es.p_value < 0.05
                })

        effect_summary.sort(key=lambda x: abs(x['cohens_d']), reverse=True)

        # 重复性汇总
        icc_summary = []
        for metric_id, stats in all_stats.items():
            rs = stats['repeatability']
            icc_summary.append({
                'metric_id': metric_id,
                'icc': rs.icc,
                'icc_grade': rs.icc_grade,
                'sem': rs.sem,
                'mdc_95': rs.mdc_95,
                'cv_within_pct': rs.cv_within_pct
            })

        icc_summary.sort(key=lambda x: x['icc'], reverse=True)

        return {
            'summary': {
                'n_volunteers': n_volunteers,
                'n_sessions': n_sessions,
                'n_metrics': n_metrics,
                'volunteer_ids': list(self._volunteers.keys()),
                'session_ids': list(self._sessions.keys()),
            },
            'cv_summary': cv_summary,
            'effect_summary': effect_summary,
            'icc_summary': icc_summary,
            'detailed_stats': {
                metric_id: {
                    'group_stats': self._stat_to_dict(stats['group_stats']),
                    'repeatability': self._stat_to_dict(stats['repeatability']),
                    'effect_size': self._stat_to_dict(stats.get('effect_size'))
                }
                for metric_id, stats in all_stats.items()
            }
        }

    def _get_all_values(self, metric_id: str,
                        volunteer_ids: List[str] = None) -> List[float]:
        """获取某指标的所有值 (跨志愿者)"""
        metric_data = self._data.get(metric_id, {})
        values = []
        target_volunteers = volunteer_ids or list(metric_data.keys())
        for vid in target_volunteers:
            if vid in metric_data:
                values.extend(metric_data[vid].values())
        return values

    def _get_values_by_volunteer(self, metric_id: str,
                                 volunteer_ids: List[str] = None
                                 ) -> Dict[str, List[float]]:
        """获取某指标按志愿者分组的值列表"""
        metric_data = self._data.get(metric_id, {})
        result = {}
        target_volunteers = volunteer_ids or list(metric_data.keys())
        for vid in target_volunteers:
            if vid in metric_data:
                result[vid] = list(metric_data[vid].values())
        return result

    @staticmethod
    def _stat_to_dict(stat_obj) -> Optional[Dict]:
        """将dataclass转换为字典"""
        if stat_obj is None:
            return None
        if hasattr(stat_obj, '__dataclass_fields__'):
            return {f: getattr(stat_obj, f) for f in stat_obj.__dataclass_fields__}
        return stat_obj

    def clear(self):
        """清空所有数据"""
        self._volunteers.clear()
        self._sessions.clear()
        self._data.clear()
        logger.info("MetaAnalyzer数据已清空")