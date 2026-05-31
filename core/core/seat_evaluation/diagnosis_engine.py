#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单组诊断引擎 — Transfer Path + Weakest Link 分析
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .metadata_registry import get_global_registry

_registry = get_global_registry()
DIAGNOSIS_THRESHOLDS = _registry.diagnosis_thresholds
DIAGNOSIS_STATE_ICONS = _registry.diagnosis_state_icons


def _diagnosis_state(value, thresholds):
    if value is None:
        return 'na'
    if value <= thresholds['pass']:
        return 'pass'
    if value <= thresholds['warn']:
        return 'warn'
    return 'fail'


def _diagnosis_comment(metric_id, value, state, threshold_def):
    t = threshold_def
    if state == 'na':
        return '数据缺失'
    if state == 'pass':
        if metric_id in ('SEAT_Z', 'SEAT_XY'):
            pct = (1 - value) * 100 if value <= 1.0 else (value - 1) * 100
            return f'隔振率 {pct:.0f}%'
        elif metric_id == 'HIC15':
            return f'远低于限值 {t["pass"]}'
        elif metric_id == 'FDS_D':
            return f'剩余寿命 {((1-value)*100):.0f}%'
        return '良好'
    if state == 'warn':
        if metric_id in ('SEAT_Z', 'SEAT_XY'):
            return f'隔振率仅 {(1-value)*100:.0f}%，接近临界'
        return f'接近限值 {t["warn"]}'
    if metric_id in ('SEAT_Z', 'SEAT_XY') and value > 1.0:
        pct = (value - 1) * 100
        return f'振动放大 {pct:.0f}%（不良）'
    return f'超过安全限值 {t["warn"]}'


@dataclass
class DiagnosisItem:
    label: str
    metric_id: str
    value: Optional[float]
    state: str = 'na'
    comment: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'metric_id': self.metric_id,
            'value': self.value,
            'state': self.state,
            'comment': self.comment,
        }


@dataclass
class SingleGroupDiagnosis:
    group_tag: str = 'experimental'
    isolation: List[DiagnosisItem] = field(default_factory=list)
    head_safety: List[DiagnosisItem] = field(default_factory=list)
    fatigue: List[DiagnosisItem] = field(default_factory=list)
    conclusion: str = ''
    weakest_link: str = ''
    overall_verdict: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'group_tag': self.group_tag,
            'isolation': [i.to_dict() for i in self.isolation],
            'head_safety': [i.to_dict() for i in self.head_safety],
            'fatigue': [i.to_dict() for i in self.fatigue],
            'conclusion': self.conclusion,
            'weakest_link': self.weakest_link,
            'overall_verdict': self.overall_verdict,
        }


def generate_single_group_diagnosis(
    location_results: Dict[str, Any],
    group_tag: str = 'experimental',
) -> SingleGroupDiagnosis:
    diag = SingleGroupDiagnosis(group_tag=group_tag)

    def _get_metric(loc_id: str, metric_id: str) -> Optional[float]:
        lr = location_results.get(loc_id)
        if lr is None:
            return None
        metrics = getattr(lr, 'metrics', {}) or {}
        val = metrics.get(metric_id)
        if val is not None and isinstance(val, (int, float)) and val == -1.0:
            return None
        return val

    def _build_section(metric_ids):
        items = []
        for mid in metric_ids:
            td = DIAGNOSIS_THRESHOLDS[mid]
            if td.get('fixed', False):
                continue
            val = _get_metric(td['loc'], mid)
            state = _diagnosis_state(val, td)
            comment = _diagnosis_comment(mid, val, state, td)
            items.append(DiagnosisItem(
                label=td['desc'],
                metric_id=mid,
                value=val,
                state=state,
                comment=comment,
            ))
        return items

    diag.isolation = _build_section(['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_TR', 'ACC_RMS', 'ACC_PEAK'])
    diag.head_safety = _build_section(['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS'])
    diag.fatigue = _build_section(['FDS_D', 'RFC_CC', 'VDV_Z'])

    all_states = []
    for item in diag.isolation + diag.head_safety + diag.fatigue:
        if item.state != 'na':
            all_states.append(item.state)

    fail_count = all_states.count('fail')
    warn_count = all_states.count('warn')

    fails = [it for it in diag.isolation + diag.head_safety + diag.fatigue if it.state == 'fail']
    warns = [it for it in diag.isolation + diag.head_safety + diag.fatigue if it.state == 'warn']

    if fail_count > 0:
        diag.overall_verdict = f'存在 {fail_count} 项不合格'
        diag.weakest_link = ' / '.join(f.label for f in fails[:3])
        diag.conclusion = f'❌ 单组诊断：{diag.overall_verdict}\n最薄弱环节：{diag.weakest_link}'
    elif warn_count > 0:
        diag.overall_verdict = f'基本合格，{warn_count} 项需关注'
        diag.weakest_link = ' / '.join(w.label for w in warns[:3])
        diag.conclusion = f'⚠️ 单组诊断：{diag.overall_verdict}\n需关注：{diag.weakest_link}'
    else:
        diag.overall_verdict = '各项指标正常'
        diag.weakest_link = '无'
        diag.conclusion = '✅ 单组诊断：各项指标均在安全范围内'

    return diag