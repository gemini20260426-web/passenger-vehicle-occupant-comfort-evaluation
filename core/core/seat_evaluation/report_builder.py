#!/usr/bin/env python3
"""
结构化报告构建器 — 将所有分析结果组装为完整报告 JSON
供 PDF/Excel/UI 渲染

核心功能:
  1. _normalize_results() — 将 FullTimeseriesEvaluator.results 适配为扩展模块期望格式
  2. build() — 组装完整结构化报告
"""

import json
import numpy as np
from datetime import datetime
from typing import Dict, Any

import logging
logger = logging.getLogger(__name__)


class ReportBuilder:
    """全量统计分析 — 结构化报告构建器"""

    def __init__(self):
        self.sections = {}

    def build(self,
              evaluator_results: dict = None,
              behavior_summary: dict = None,
              analysis_results: dict = None,
              location_results: dict = None,
              include_comfort: bool = True,
              include_subjective: bool = True,
              include_tuning: bool = True,
              include_spine: bool = True,
              include_ride: bool = True,
              include_ml_events: bool = True) -> dict:
        """
        构建完整结构化报告

        Args:
            evaluator_results: FullTimeseriesEvaluator 的 results 字典
            behavior_summary: DataBridge 行为摘要 (含 events)
            analysis_results: 已适配的分析结果 (直接传入则跳过适配)
            location_results: 外层 report 的 location_results (含 per-location 指标)
            include_comfort: 是否包含舒适度指数
            include_subjective: 是否包含主观评价
            include_tuning: 是否包含调校建议
            include_spine: 是否包含脊柱健康 (ISO 2631-5)
            include_ride: 是否包含平顺性 (GB/T 4970)
            include_ml_events: 是否包含 ML 事件

        Returns:
            完整结构化报告 dict
        """
        # ── 数据适配: 如果未提供 analysis_results，从原始结果构建 ──
        if analysis_results is None:
            analysis_results = self._normalize_results(
                evaluator_results or {},
                behavior_summary or {},
                location_results or {},
            )

        report = {
            'metadata': {
                'report_type': 'full_statistics_analysis_v2',
                'generated_at': datetime.now().isoformat(),
                'version': '2.0',
                'modules': {
                    'comfort_index': include_comfort,
                    'subjective_mapping': include_subjective,
                    'tuning_advisor': include_tuning,
                    'spine_health': include_spine,
                    'ride_quality': include_ride,
                    'ml_events': include_ml_events,
                }
            },
        }

        # ── 现有模块 ──
        for key in ['events', 'time_domain', 'frequency_domain', 'shock_fatigue',
                     'attenuation', 'statistical_tests', 'diagnostics']:
            if key in analysis_results:
                report[key] = analysis_results[key]

        # ── 新增: 舒适度指数 ──
        if include_comfort:
            try:
                from core.core.seat_evaluation.comfort_index import ComfortIndexCalculator
                calc = ComfortIndexCalculator()
                ci = calc.compute(analysis_results)
                report['comfort_index'] = {
                    'overall_score': round(ci.overall_score, 1),
                    'grade': ci.grade,
                    'grade_label': ci.details.get('grade_label', ''),
                    'vibration_score': round(ci.vibration_score, 1),
                    'shock_score': round(ci.shock_score, 1),
                    'transfer_score': round(ci.transfer_score, 1),
                    'posture_score': round(ci.posture_score, 1),
                }
            except Exception as e:
                logger.warning(f"舒适度计算失败: {e}")
                report['comfort_index'] = None

        # ── 新增: 主观评价 ──
        if include_subjective:
            try:
                from core.core.seat_evaluation.subjective_mapping import SubjectiveMapping
                td = report.get('time_domain', {})
                seat_vdv = td.get('vdv', {}).get('座垫', {}).get('实验组', {})
                # 统一转换: VDV → aw (与 ride_quality.py 一致)
                T = analysis_results.get('metadata', {}).get('duration_s', 600)
                T_factor = T ** 0.25 if T > 0 else 1.0
                aw_z = seat_vdv.get('Z', 0) / T_factor
                aw_xy = max(seat_vdv.get('X', 0), seat_vdv.get('Y', 0)) / T_factor
                disc = SubjectiveMapping.aw_to_discomfort(aw_z, aw_xy)
                disc['narrative'] = SubjectiveMapping.generate_narrative(
                    analysis_results.get('metadata', {}).get('speed_avg', 40),
                    {'name': '城市道路'},
                    disc
                )
                report['subjective'] = disc
            except Exception as e:
                logger.warning(f"主观评价计算失败: {e}")
                report['subjective'] = None

        # ── 新增: 调校建议 ──
        if include_tuning:
            try:
                from core.core.seat_evaluation.seat_tuning_advisor import SeatTuningAdvisor
                advisor = SeatTuningAdvisor()
                recs = advisor.analyze(analysis_results)
                report['tuning_recommendations'] = [
                    {
                        'component': r.component,
                        'parameter': r.parameter,
                        'direction': r.direction,
                        'confidence': r.confidence,
                        'reason': r.reason,
                        'expected': r.expected_improvement,
                    }
                    for r in recs
                ]
            except Exception as e:
                logger.warning(f"调校建议生成失败: {e}")
                report['tuning_recommendations'] = []

        # ── 新增: 脊柱健康 (ISO 2631-5) ──
        if include_spine:
            try:
                from core.core.seat_evaluation.spine_health import SpineHealthCalculator
                calc = SpineHealthCalculator()
                sh = calc.compute(analysis_results)
                report['spine_health'] = {
                    'risk_factor': round(sh.risk_factor, 3),
                    'risk_level': sh.risk_level,
                    'risk_label': sh.risk_label,
                    's_e': round(sh.s_e, 3),
                    'd_x': round(sh.d_x, 2),
                    'd_y': round(sh.d_y, 2),
                    'd_z': round(sh.d_z, 2),
                    'daily_exposure': sh.daily_exposure,
                }
            except Exception as e:
                logger.warning(f"脊柱健康计算失败: {e}")
                report['spine_health'] = None

        # ── 新增: 平顺性 (GB/T 4970) ──
        if include_ride:
            try:
                from core.core.seat_evaluation.ride_quality import RideQualityCalculator
                calc = RideQualityCalculator()
                rq = calc.compute(analysis_results)
                report['ride_quality'] = {
                    'aw_total': round(rq.aw_total, 4),
                    'aw_x': round(rq.aw_x, 4),
                    'aw_y': round(rq.aw_y, 4),
                    'aw_z': round(rq.aw_z, 4),
                    'comfort_level': rq.comfort_level,
                    'comfort_label': rq.comfort_label,
                }
            except Exception as e:
                logger.warning(f"平顺性计算失败: {e}")
                report['ride_quality'] = None

        return report

    def to_json(self, report: dict, path: str = None) -> str:
        """序列化为 JSON"""
        text = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        return text

    # ── 数据适配层 ──

    @staticmethod
    def _normalize_results(evaluator_results: dict, behavior_summary: dict,
                           location_results: dict = None) -> dict:
        """将 FullTimeseriesEvaluator.results 适配为扩展模块期望的格式

        数据来源优先级:
          1. location_results (外层 report 的 per-location 指标) — 精度最高
          2. evaluator_results.metrics (全时域评测器扁平指标) — 回退方案

        evaluator_results 结构:
          {'metrics': {exp_Ax_VDV, exp_Ay_VDV, ...},  ← 扁平 dict
           'spectrum': {Ax: {bands_atten: {...}, ...}, ...},
           'statistics': {Ax: {t_stat, p_value, ...}, ...},
           'events': DataFrame, 'windows': DataFrame}

        location_results 结构 (可选):
          {'head': {'metrics': {exp_Ax_VDV: ..., S_d: ..., ...}}, ...}
        """
        metrics = evaluator_results.get('metrics', {})
        spectrum = evaluator_results.get('spectrum', {})
        statistics = evaluator_results.get('statistics', {})

        # ── 提取采样率与时长 ──
        duration_s = location_results.get('duration_s', 600) if location_results else 600
        sample_rate = location_results.get('sample_rate', 1000) if location_results else 1000

        normalized = {
            'events': behavior_summary.get('events', []),
            'metadata': {
                'total_events': behavior_summary.get('total_events', 0),
                'event_types': behavior_summary.get('event_types', {}),
                'source': behavior_summary.get('source', 'rule'),
                'speed_avg': metrics.get('speed_avg', 40),
                'duration_s': duration_s,
                'sampling_rate': sample_rate,
                'created_at': datetime.now().isoformat(),
            },
        }

        # ── time_domain ──
        # 优先从 location_results 提取，回退到扁平 metrics
        td = {'vdv': {}, 'acc_peak': {}, 'gyro': {}}
        loc_data_extracted = False

        if location_results:
            try:
                for loc_id, loc_data in location_results.items():
                    if not isinstance(loc_data, dict):
                        continue
                    loc_metrics = loc_data.get('metrics', {})
                    if not loc_metrics:
                        continue
                    loc_name = ReportBuilder._loc_name(loc_id)
                    td['vdv'][loc_name] = {
                        '实验组': {
                            'X': loc_metrics.get('exp_Ax_VDV', 0),
                            'Y': loc_metrics.get('exp_Ay_VDV', 0),
                            'Z': loc_metrics.get('exp_Az_VDV', 0),
                        },
                        '对照组': {
                            'X': loc_metrics.get('ctrl_Ax_VDV', 0),
                            'Y': loc_metrics.get('ctrl_Ay_VDV', 0),
                            'Z': loc_metrics.get('ctrl_Az_VDV', 0),
                        },
                    }
                    td['acc_peak'][loc_name] = {
                        '实验组': {
                            'X': loc_metrics.get('exp_Ax_Peak', 0),
                            'Y': loc_metrics.get('exp_Ay_Peak', 0),
                            'Z': loc_metrics.get('exp_Az_Peak', 0),
                        },
                    }
                    td['gyro'][loc_name] = {
                        'Gz_rms': loc_metrics.get('exp_Gz_RMS', 0),
                    }
                    loc_data_extracted = True
            except Exception as e:
                logger.debug(f"从 location_results 提取时域指标失败: {e}")

        # 回退: 从扁平 metrics 提取 (单一位置「座垫」)
        if not loc_data_extracted and metrics:
            try:
                td['vdv']['座垫'] = {
                    '实验组': {
                        'X': metrics.get('exp_Ax_VDV', 0),
                        'Y': metrics.get('exp_Ay_VDV', 0),
                        'Z': metrics.get('exp_Az_VDV', 0),
                    },
                    '对照组': {
                        'X': metrics.get('ctrl_Ax_VDV', 0),
                        'Y': metrics.get('ctrl_Ay_VDV', 0),
                        'Z': metrics.get('ctrl_Az_VDV', 0),
                    },
                }
                td['acc_peak']['座垫'] = {
                    '实验组': {
                        'X': metrics.get('exp_Ax_Peak', 0),
                        'Y': metrics.get('exp_Ay_Peak', 0),
                        'Z': metrics.get('exp_Az_Peak', 0),
                    },
                }
                td['gyro']['座垫'] = {
                    'Gz_rms': metrics.get('exp_Gz_RMS', 0),
                }
            except Exception as e:
                logger.debug(f"从扁平 metrics 提取时域指标失败: {e}")
        normalized['time_domain'] = td

        # ── frequency_domain ──
        fd = {'seat': {}, 'psd': {}, 'transfer': {}}

        # 从扁平 metrics 计算 SEAT 和 TR (sternum 存在时)
        try:
            sternum_rms_x = metrics.get('sternum_Ax_RMS', None)
            if sternum_rms_x is not None:
                for ax, axis_key in [('X', 'Ax'), ('Y', 'Ay'), ('Z', 'Az')]:
                    exp_rms = metrics.get(f'exp_{axis_key}_RMS', 0)
                    sternum_rms = metrics.get(f'sternum_{axis_key}_RMS', 1.0)
                    if sternum_rms > 1e-6:
                        fd['seat']['座垫'] = fd['seat'].get('座垫', {})
                        fd['seat']['座垫'][ax] = round(exp_rms / sternum_rms, 4)
                        fd['transfer']['座垫'] = fd['transfer'].get('座垫', {})
                        fd['transfer']['座垫'][ax] = round(exp_rms / sternum_rms, 4)
        except Exception:
            pass

        # 从 location_results 提取 SEAT/TR
        if location_results:
            try:
                for loc_id, loc_data in location_results.items():
                    if not isinstance(loc_data, dict):
                        continue
                    loc_metrics = loc_data.get('metrics', {})
                    loc_name = ReportBuilder._loc_name(loc_id)
                    seat_vals = {}
                    tr_vals = {}
                    for ax in ['X', 'Y', 'Z']:
                        seat_key = f'SEAT_A{ax.lower()}'
                        tr_key = f'TR_A{ax.lower()}'
                        if seat_key in loc_metrics:
                            seat_vals[ax] = loc_metrics[seat_key]
                        if tr_key in loc_metrics:
                            tr_vals[ax] = loc_metrics[tr_key]
                    if seat_vals:
                        fd['seat'][loc_name] = seat_vals
                    if tr_vals:
                        fd['transfer'][loc_name] = tr_vals
            except Exception:
                pass

        # PSD 从 spectrum 提取
        try:
            for ax in ['Ax', 'Ay', 'Az']:
                ax_data = spectrum.get(ax, {})
                if isinstance(ax_data, dict):
                    psd_data = ax_data.get('psd', {})
                    if isinstance(psd_data, dict):
                        fd['psd'][ax] = {str(k): float(v) for k, v in psd_data.items()}
        except Exception:
            pass
        normalized['frequency_domain'] = fd

        # ── shock_fatigue ──
        sf = {'iso2631_5': {}}
        loc_sd_extracted = False

        if location_results:
            try:
                for loc_id, loc_data in location_results.items():
                    if not isinstance(loc_data, dict):
                        continue
                    loc_metrics = loc_data.get('metrics', {})
                    loc_name = ReportBuilder._loc_name(loc_id)
                    exp_sd = loc_metrics.get('S_d', loc_metrics.get('exp_S_d', 0))
                    ctrl_sd = loc_metrics.get('ctrl_S_d', 0)
                    if exp_sd or ctrl_sd:
                        sf['iso2631_5'][loc_name] = {
                            '实验组': {'S_d': exp_sd},
                            '对照组': {'S_d': ctrl_sd},
                        }
                        loc_sd_extracted = True
            except Exception:
                pass

        # 回退: 从扁平 metrics 提取
        if not loc_sd_extracted and metrics:
            try:
                exp_sd = metrics.get('exp_S_d', 0)
                ctrl_sd = metrics.get('ctrl_S_d', 0)
                sf['iso2631_5']['座垫'] = {
                    '实验组': {'S_d': exp_sd},
                    '对照组': {'S_d': ctrl_sd},
                }
            except Exception:
                pass
        normalized['shock_fatigue'] = sf

        # ── attenuation ──
        # 从 spectrum 提取频段衰减，同时计算整体 RMS 衰减
        atten = {}
        try:
            for ax in ['Ax', 'Ay', 'Az']:
                ax_data = spectrum.get(ax, {})
                if isinstance(ax_data, dict):
                    bands = ax_data.get('bands_atten', {})
                    # 只取 Hz 格式的频段 (5个)，避免重复计数
                    hz_bands = {k: v for k, v in bands.items() if 'Hz' in k}
                    band_mean = np.mean(list(hz_bands.values())) if hz_bands else 0
                    # 同时计算整体 RMS 衰减
                    exp_rms_key = f'exp_{ax}_RMS'
                    ctrl_rms_key = f'ctrl_{ax}_RMS'
                    exp_rms = metrics.get(exp_rms_key, 0)
                    ctrl_rms = metrics.get(ctrl_rms_key, 0)
                    overall_atten = (1 - exp_rms / ctrl_rms) * 100 if ctrl_rms > 1e-6 else 0
                    atten[ax] = {
                        'overall': round(overall_atten, 1),
                        'band_mean': round(band_mean, 1),
                        'bands': {k: round(v, 1) for k, v in hz_bands.items()},
                    }
        except Exception:
            pass
        normalized['attenuation'] = atten

        # ── statistical_tests ──
        normalized['statistical_tests'] = {
            't_test': statistics.get('t_test', {}),
            'cohens_d': statistics.get('cohens_d', {}),
            'significant_count': statistics.get('significant_count', 0),
        }

        return normalized

    @staticmethod
    def _loc_name(loc_id: str) -> str:
        """位置ID → 中文名"""
        _MAP = {
            'seat_cushion': '座垫', 'seat_back': '靠背',
            'floor': '地板', 'steering': '方向盘',
            'head': '头部', 'foot': '脚部',
            'seat': '座垫', 'back': '靠背',
        }
        return _MAP.get(loc_id, loc_id)