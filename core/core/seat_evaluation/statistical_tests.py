"""
对照分析统计检验补全 — Wilcoxon符号秩检验 + 事件冷却时间机制

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第二部分 3.5 节 (P2对照分析完整性)。
补全仓库缺失的 Wilcoxon检验 和 冷却时间机制(3s cooldown)。
"""

import numpy as np
from scipy import stats as scipy_stats
from typing import Tuple, Dict, Optional, List
from collections import deque
import time
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. Wilcoxon 符号秩检验
# ═══════════════════════════════════════════════════════════════

def wilcoxon_signed_rank_test(
    experimental: np.ndarray,
    control: np.ndarray,
    alternative: str = 'two-sided',
    alpha: float = 0.05,
) -> dict:
    """Wilcoxon 符号秩检验 — 配对样本非参数检验

    与t检验互补: t检验假设正态分布, Wilcoxon无需分布假设。
    适用于实验组vs对照组配对的非正态分布检验。

    Args:
        experimental: 实验组数据 (需与control等长)
        control: 对照组数据
        alternative: 'two-sided' / 'less' / 'greater'
        alpha: 显著性水平

    Returns:
        {
            'statistic': float,      # W统计量
            'p_value': float,        # p值
            'significant': bool,     # 是否显著
            'effect_size': float,    # 效应量 (r = Z/sqrt(N))
            'median_diff': float,    # 中位数差异
            'n_pairs': int,          # 配对数
            'ci_95': (float, float), # 95%置信区间
        }
    """
    # 去除NaN
    valid = ~np.isnan(experimental) & ~np.isnan(control)
    exp = experimental[valid]
    ctrl = control[valid]

    if len(exp) < 10:
        return {
            'statistic': float('nan'),
            'p_value': float('nan'),
            'significant': False,
            'effect_size': 0.0,
            'median_diff': 0.0,
            'n_pairs': len(exp),
            'ci_95': (float('nan'), float('nan')),
            'error': f'样本量不足 ({len(exp)} < 10)',
        }

    # 配对检验
    diff = exp - ctrl
    try:
        statistic, p_value = scipy_stats.wilcoxon(
            exp, ctrl, alternative=alternative
        )
    except Exception as e:
        logger.warning(f"Wilcoxon检验失败: {e}")
        return {
            'statistic': float('nan'),
            'p_value': float('nan'),
            'significant': False,
            'effect_size': 0.0,
            'median_diff': 0.0,
            'n_pairs': len(exp),
            'ci_95': (float('nan'), float('nan')),
            'error': str(e),
        }

    # 效应量: r = Z / sqrt(N)
    z_stat = scipy_stats.norm.ppf(p_value / 2) if alternative == 'two-sided' else scipy_stats.norm.ppf(p_value)
    r = abs(z_stat) / np.sqrt(len(exp))

    median_diff = float(np.median(diff))

    # 95%置信区间 (bootstrap)
    try:
        n_boot = 1000
        boot_medians = []
        rng = np.random.RandomState(42)
        for _ in range(n_boot):
            idx = rng.randint(0, len(diff), len(diff))
            boot_medians.append(np.median(diff[idx]))
        ci_lo = np.percentile(boot_medians, 2.5)
        ci_hi = np.percentile(boot_medians, 97.5)
        ci_95 = (float(ci_lo), float(ci_hi))
    except Exception:
        ci_95 = (float('nan'), float('nan'))

    return {
        'statistic': float(statistic),
        'p_value': float(p_value),
        'significant': p_value < alpha,
        'effect_size': round(float(r), 4),
        'median_diff': round(median_diff, 6),
        'n_pairs': len(exp),
        'ci_95': ci_95,
    }


def comprehensive_statistical_test(
    experimental: np.ndarray,
    control: np.ndarray,
    alpha: float = 0.05,
) -> dict:
    """综合统计检验 — t检验 + Wilcoxon + Cohen's d

    Returns:
        {
            't_test': {...},         # 配对t检验结果
            'wilcoxon': {...},       # Wilcoxon符号秩检验结果
            'cohens_d': float,       # Cohen's d效应量
            'normality': {...},      # 正态性检验(Shapiro-Wilk)
            'recommendation': str,   # 推荐使用哪个检验
        }
    """
    valid = ~np.isnan(experimental) & ~np.isnan(control)
    exp = experimental[valid]
    ctrl = control[valid]

    if len(exp) < 10:
        return {'error': f'样本量不足 ({len(exp)})'}

    # 正态性检验
    diff = exp - ctrl
    try:
        shapiro_stat, shapiro_p = scipy_stats.shapiro(diff)
        is_normal = shapiro_p > alpha
    except Exception:
        shapiro_stat, shapiro_p = float('nan'), float('nan')
        is_normal = False

    # t检验
    t_stat, t_p = scipy_stats.ttest_rel(exp, ctrl)

    # Wilcoxon
    wilcoxon_result = wilcoxon_signed_rank_test(exp, ctrl, alpha=alpha)

    # Cohen's d
    d = (np.mean(diff)) / (np.std(diff) + 1e-10)

    # 推荐
    if is_normal:
        recommendation = 't_test (数据符合正态分布)'
    else:
        recommendation = 'wilcoxon (数据不符合正态分布, 推荐非参数检验)'

    return {
        't_test': {
            'statistic': float(t_stat),
            'p_value': float(t_p),
            'significant': t_p < alpha,
        },
        'wilcoxon': wilcoxon_result,
        'cohens_d': round(float(d), 4),
        'normality': {
            'shapiro_statistic': float(shapiro_stat) if not np.isnan(shapiro_stat) else None,
            'shapiro_p_value': float(shapiro_p) if not np.isnan(shapiro_p) else None,
            'is_normal': is_normal,
        },
        'recommendation': recommendation,
        'n_pairs': len(exp),
    }


# ═══════════════════════════════════════════════════════════════
# 2. 事件冷却时间机制 (Cooldown)
# ═══════════════════════════════════════════════════════════════

class EventCooldownManager:
    """事件冷却时间管理器

    防止同一类型事件在冷却期内重复触发:
    - 急刹车(emergency_braking): 5s cooldown
    - 变道(lane_change): 3s cooldown
    - 蛇形驾驶(weaving): 10s cooldown
    - 默认: 3s cooldown

    同时检测事件序列异常:
    - 如 braking 后 0.5s 内又出现 acceleration → 标记为事件序列异常
    """

    # 事件类型 → 冷却时间 (秒)
    DEFAULT_COOLDOWNS = {
        'emergency_braking': 5.0,
        'aggressive_deceleration': 3.0,
        'normal_deceleration': 1.0,
        'aggressive_acceleration': 3.0,
        'normal_acceleration': 1.0,
        'launch': 3.0,
        'weaving': 10.0,
        'lane_change': 3.0,
        'rapid_direction_change': 1.0,
        'tight_turn': 5.0,
        'wide_turn': 5.0,
        'u_turn': 5.0,
        'cornering_braking': 3.0,
        'cornering_acceleration': 3.0,
        'cornering_deceleration': 3.0,
        'severe_bump': 1.0,
        'skid_risk': 3.0,
        'rollover_risk': 5.0,
        'sensor_fault': 1.0,
    }

    # 事件序列矛盾规则 (A → B 不合理)
    CONFLICT_RULES = {
        ('emergency_braking', 'aggressive_acceleration'): '制动后急加速',
        ('emergency_braking', 'normal_acceleration'): '急刹后加速',
        ('aggressive_deceleration', 'aggressive_acceleration'): '减速后急加速',
        ('stopped', 'launch'): None,  # 允许: 停车→起步
        ('launch', 'emergency_braking'): '起步后急刹',
        ('severe_bump', 'sensor_fault'): '颠簸后传感器异常',
    }

    def __init__(self, cooldowns: dict = None):
        self.cooldowns = cooldowns or self.DEFAULT_COOLDOWNS
        self._last_trigger_time: Dict[str, float] = {}
        self._event_history: deque = deque(maxlen=50)
        self._suppressed_count: int = 0
        self._conflict_count: int = 0

    def should_trigger(self, event_type: str, timestamp: float,
                       confidence: float = 0.0) -> bool:
        """检查事件是否应该触发 (无冷却冲突)

        Args:
            event_type: 事件类型
            timestamp: 事件时间戳
            confidence: 事件置信度

        Returns:
            True if should trigger, False if suppressed by cooldown
        """
        cooldown = self.cooldowns.get(event_type, 3.0)

        if event_type in self._last_trigger_time:
            elapsed = timestamp - self._last_trigger_time[event_type]
            if elapsed < cooldown:
                self._suppressed_count += 1
                logger.debug(
                    f"事件 {event_type} 冷却中 "
                    f"(已过 {elapsed:.2f}s / 冷却 {cooldown}s)"
                )
                return False

        return True

    def record_trigger(self, event_type: str, timestamp: float,
                       confidence: float = 0.0) -> None:
        """记录事件触发并更新冷却时间"""
        self._last_trigger_time[event_type] = timestamp
        self._event_history.append({
            'type': event_type,
            'timestamp': timestamp,
            'confidence': confidence,
        })

    def check_sequence_conflict(self, event_type: str) -> Optional[str]:
        """检查事件序列是否矛盾

        Returns:
            None if no conflict, or conflict description string
        """
        if len(self._event_history) < 2:
            return None

        last_event = self._event_history[-1]
        last_type = last_event['type']

        conflict = self.CONFLICT_RULES.get((last_type, event_type))
        if conflict:
            self._conflict_count += 1
            return conflict

        return None

    def process_event(self, event_type: str, timestamp: float,
                      confidence: float = 0.0) -> dict:
        """完整的事件处理流程 (冷却检查 + 矛盾检测 + 记录)

        Returns:
            {'triggered': bool, 'conflict': str|None}
        """
        # 冷却检查
        if not self.should_trigger(event_type, timestamp, confidence):
            return {'triggered': False, 'conflict': None, 'reason': 'cooldown'}

        # 序列矛盾检测
        conflict = self.check_sequence_conflict(event_type)
        if conflict:
            self.record_trigger(event_type, timestamp, confidence)
            return {'triggered': True, 'conflict': conflict, 'reason': 'conflict'}

        # 正常触发
        self.record_trigger(event_type, timestamp, confidence)
        return {'triggered': True, 'conflict': None, 'reason': 'normal'}

    def get_stats(self) -> dict:
        """获取冷却管理器统计"""
        return {
            'suppressed_count': self._suppressed_count,
            'conflict_count': self._conflict_count,
            'total_events': len(self._event_history),
            'active_cooldowns': {
                k: v for k, v in self._last_trigger_time.items()
                if time.time() - v < self.cooldowns.get(k, 3.0)
            },
        }

    def reset(self) -> None:
        """重置冷却管理器"""
        self._last_trigger_time.clear()
        self._event_history.clear()
        self._suppressed_count = 0
        self._conflict_count = 0


# ═══════════════════════════════════════════════════════════════
# 3. 综合对照分析函数
# ═══════════════════════════════════════════════════════════════

def analyze_control_experiment(
    experimental: np.ndarray,
    control: np.ndarray,
    axis_name: str = 'Ay',
    confidence_level: float = 0.95,
) -> dict:
    """完整的实验组 vs 对照组统计分析

    Returns:
        {
            'axis': str,
            'n': int,
            'descriptive': {mean, std, median, min, max, q25, q75},
            't_test': {...},
            'wilcoxon': {...},
            'cohens_d': float,
            'attenuation_percent': float,
            'conclusion': str,
        }
    """
    valid = ~np.isnan(experimental) & ~np.isnan(control)
    exp = experimental[valid]
    ctrl = control[valid]

    if len(exp) < 10:
        return {'error': f'样本量不足 ({len(exp)})'}

    # 描述性统计
    exp_mean = float(np.mean(exp))
    ctrl_mean = float(np.mean(ctrl))
    attenuation = (1 - exp_mean / ctrl_mean) * 100 if ctrl_mean != 0 else 0.0

    # 综合检验
    comprehensive = comprehensive_statistical_test(exp, ctrl)

    # 结论
    if comprehensive['t_test']['significant'] or comprehensive['wilcoxon']['significant']:
        if attenuation > 30:
            conclusion = f'{axis_name}轴显著改善, 衰减率 {attenuation:.1f}%'
        elif attenuation > 10:
            conclusion = f'{axis_name}轴有改善, 衰减率 {attenuation:.1f}%'
        elif attenuation > -10:
            conclusion = f'{axis_name}轴无显著变化'
        else:
            conclusion = f'{axis_name}轴恶化, 衰减率 {attenuation:.1f}%'
    else:
        conclusion = f'{axis_name}轴无统计学显著差异'

    return {
        'axis': axis_name,
        'n': len(exp),
        'descriptive': {
            'exp_mean': round(exp_mean, 4),
            'ctrl_mean': round(ctrl_mean, 4),
            'exp_std': round(float(np.std(exp)), 4),
            'ctrl_std': round(float(np.std(ctrl)), 4),
            'exp_median': round(float(np.median(exp)), 4),
            'ctrl_median': round(float(np.median(ctrl)), 4),
            'exp_min': round(float(np.min(exp)), 4),
            'exp_max': round(float(np.max(exp)), 4),
            'ctrl_min': round(float(np.min(ctrl)), 4),
            'ctrl_max': round(float(np.max(ctrl)), 4),
        },
        't_test': comprehensive['t_test'],
        'wilcoxon': comprehensive['wilcoxon'],
        'cohens_d': comprehensive['cohens_d'],
        'attenuation_percent': round(attenuation, 2),
        'conclusion': conclusion,
        'recommendation': comprehensive['recommendation'],
    }