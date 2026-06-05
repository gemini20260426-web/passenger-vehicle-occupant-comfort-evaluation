#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测引擎核心
基于9大算子系统的指标计算引擎
"""

import numpy as np
import logging
import warnings
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal

from .operators import OperatorSystem
from .metadata_registry import INDICATOR_DEFINITIONS, METRIC_THRESHOLDS, get_global_registry
from ..analysis.core_types import (
    EvaluationTrigger, EvaluationResult, RiskLevel
)

logger = logging.getLogger(__name__)


class SeatEvaluationEngine(QObject):
    """座椅评测引擎 v1.0 — [已弃用] 请使用 engine_v2.MultiChannelSeatEvaluationEngine

    自 v3.5 起，本引擎已弃用。所有新代码应直接使用 engine_v2.MultiChannelSeatEvaluationEngine。
    本引擎保留仅为向后兼容，内部指标计算为简化实现，存在已知缺陷。
    """

    _DEPRECATED = True

    evaluation_started = Signal(dict)
    evaluation_completed = Signal(dict)
    metric_calculated = Signal(dict)
    
    def __init__(self, config_manager=None, data_storage=None):
        super().__init__()
        warnings.warn(
            "SeatEvaluationEngine is deprecated. Use MultiChannelSeatEvaluationEngine from engine_v2 instead.",
            DeprecationWarning, stacklevel=2
        )
        self.config_manager = config_manager
        self.data_storage = data_storage
        
        # 初始化算子系统
        self.operator_system = OperatorSystem()
        
        # 默认采样率
        self.default_sample_rate = 100.0
        
        logger.info("座椅评测引擎初始化完成")
    
    def evaluate_by_event(self, trigger: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于事件执行评测
        
        Args:
            trigger: 评测触发器字典
            
        Returns:
            评测结果字典
        """
        try:
            self.evaluation_started.emit(trigger)
            
            trigger_id = trigger.get('event_id', '')
            event_type = trigger.get('event_type', '')
            metrics = trigger.get('metrics', [])
            raw_data = trigger.get('raw_data', {})
            
            # 提取数据窗口
            data_window = self._extract_data_window(raw_data, trigger.get('data_window', {}))
            
            if not data_window:
                logger.warning(f"无法提取数据窗口: {trigger_id}")
                return None
            
            # 计算指标
            calculated_metrics = self._calculate_metrics(data_window, metrics)
            
            # 计算总体评分
            overall_score = self._calculate_overall_score(calculated_metrics)
            
            # 评估风险等级
            risk_level = self._assess_risk(calculated_metrics)
            
            # 构造结果
            result = EvaluationResult(
                trigger_id=trigger_id,
                event_type=event_type,
                timestamp=trigger.get('timestamp', 0.0),
                metrics=calculated_metrics,
                overall_score=overall_score,
                risk_level=risk_level
            )
            
            # 转换为字典并发送信号
            result_dict = self._result_to_dict(result)
            self.evaluation_completed.emit(result_dict)
            
            logger.info(f"座椅评测完成: {trigger_id}, 总体评分: {overall_score:.2f}")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"座椅评测失败: {e}", exc_info=True)
            return None
    
    def _extract_data_window(self, raw_data: Dict[str, Any], 
                            window_config: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        提取数据窗口（单位转换：m/s² → g）
        
        Args:
            raw_data: 原始数据
            window_config: 窗口配置 (pre, post)
            
        Returns:
            数据窗口字典（加速度单位：g）
        """
        try:
            # 简化实现 - 实际需要从数据存储中提取指定时间窗口的数据
            # 这里假设raw_data已经包含需要的数据
            
            # 提取三轴加速度数据（单位转换：m/s² → g）
            data_window = {
                'ax': np.array(raw_data.get('ax', [])) / 9.81,
                'ay': np.array(raw_data.get('ay', [])) / 9.81,
                'az': np.array(raw_data.get('az', [])) / 9.81,
                'sample_rate': self.default_sample_rate
            }
            
            if len(data_window['ax']) == 0:
                logger.warning("数据为空，无法提取数据窗口")
                return None
            
            return data_window
            
        except Exception as e:
            logger.error(f"提取数据窗口失败: {e}")
            return None
    
    def _calculate_metrics(self, data_window: Dict[str, Any], 
                          metrics: List[str]) -> Dict[str, float]:
        """
        计算指定指标
        
        Args:
            data_window: 数据窗口
            metrics: 指标ID列表
            
        Returns:
            指标结果字典
        """
        results = {}
        
        for metric_id in metrics:
            try:
                value = self._calculate_single_metric(metric_id, data_window)
                results[metric_id] = value
                
                # 发送指标计算完成信号
                self.metric_calculated.emit({
                    'metric_id': metric_id,
                    'value': value,
                    'definition': INDICATOR_DEFINITIONS.get(metric_id, {})
                })
                
            except Exception as e:
                logger.error(f"计算指标 {metric_id} 失败: {e}")
                results[metric_id] = 0.0
        
        return results
    
    def _calculate_single_metric(self, metric_id: str, 
                                data_window: Dict[str, Any]) -> float:
        """
        计算单个指标

        NOTE: 本V1引擎的指标计算为简化实现，存在已知缺陷。
        权威实现请参见 engine_v2.py 中的 MultiChannelSeatEvaluationEngine._calculate_single_metric，
        该版本包含 CFC 滤波(SAE J211-1)、相干性检查、样本量校验等完整修正。

        Args:
            metric_id: 指标ID
            data_window: 数据窗口

        Returns:
            指标值
        """
        warnings.warn(
            "SeatEvaluationEngine._calculate_single_metric is deprecated. "
            "Use MultiChannelSeatEvaluationEngine from engine_v2.py instead.",
            DeprecationWarning, stacklevel=2
        )

        logger.warning(
            "使用V1引擎(SeatEvaluationEngine)的 _calculate_single_metric 计算指标 %s，"
            "该实现为简化版本，存在已知缺陷。建议使用 engine_v2.py 中的 "
            "MultiChannelSeatEvaluationEngine 获取正确的计算结果。",
            metric_id
        )

        reg = get_global_registry()
        if not reg.validate_indicator_code(metric_id):
            logger.warning(
                f"[MetadataConstraint] 未注册指标代码被调用: {metric_id}, "
                f"请在元数据管理中心注册该指标"
            )
            return float('nan')

        ops = self.operator_system
        ax = data_window.get('ax', np.array([]))
        ay = data_window.get('ay', np.array([]))
        az = data_window.get('az', np.array([]))
        sr = data_window.get('sample_rate', self.default_sample_rate)
        
        # 原有频域指标
        if metric_id == 'SEAT_Z':
            floor_az = data_window.get('floor_az', None)
            if floor_az is not None and len(floor_az) > 0:
                f_seat, psd_seat = ops.psd.compute(az, sr, nperseg=min(1024, len(az)))
                f_floor, psd_floor = ops.psd.compute(floor_az, sr, nperseg=min(1024, len(floor_az)))
                psd_seat_w = ops.weighting.apply_weighting_z_psd(psd_seat, f_seat)
                psd_floor_w = ops.weighting.apply_weighting_z_psd(psd_floor, f_floor)
                integral_seat = np.trapz(psd_seat_w, f_seat)
                integral_floor = np.trapz(psd_floor_w, f_floor)
                if integral_floor > 0:
                    return float(np.sqrt(integral_seat / integral_floor))
            weighted = ops.weighting.apply_weighting_z_via_freq(az, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'SEAT_XY':
            xy = ops.vector.synthesize_xy(ax, ay)
            floor_axy = data_window.get('floor_axy', None)
            if floor_axy is not None and len(floor_axy) > 0:
                f_seat, psd_seat = ops.psd.compute(xy, sr, nperseg=min(1024, len(xy)))
                f_floor, psd_floor = ops.psd.compute(floor_axy, sr, nperseg=min(1024, len(floor_axy)))
                psd_seat_w = ops.weighting.apply_weighting_xy_psd(psd_seat, f_seat)
                psd_floor_w = ops.weighting.apply_weighting_xy_psd(psd_floor, f_floor)
                integral_seat = np.trapz(psd_seat_w, f_seat)
                integral_floor = np.trapz(psd_floor_w, f_floor)
                if integral_floor > 0:
                    return float(np.sqrt(integral_seat / integral_floor))
            weighted = ops.weighting.apply_weighting_xy_via_freq(xy, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'VDV_Z':
            # 垂直振动剂量值 (VDV = (∫a_w(t)^4 dt)^(1/4)), a_w是Wk加权后信号
            az_cfc = ops.cfc.filter(az, sr) if len(az) >= 4 else az
            az_w = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
            dt = 1.0 / sr
            vdv = np.power(np.sum(az_w**4) * dt, 0.25)
            return float(vdv)
        
        elif metric_id == 'TR_Z':
            floor_az = data_window.get('floor_az', None)
            if floor_az is not None and len(floor_az) > 0 and len(az) > 0:
                tf_result = ops.csd.transfer_function_db(
                    floor_az, az, sr, nperseg=min(1024, len(az)))
                if tf_result.get('TR_peak_dB', 0.0) != 0.0:
                    return float(tf_result['TR_peak_dB'])
            if len(az) > 0 and len(data_window.get('floor_az', az)) > 0:
                return float(np.std(az) / (np.std(data_window.get('floor_az', az)) + 0.001))
            return 1.0
        
        elif metric_id == 'AW_Z':
            weighted = ops.weighting.apply_weighting_z_via_freq(az, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'AW_XY':
            xy = ops.vector.synthesize_xy(ax, ay)
            weighted = ops.weighting.apply_weighting_xy_via_freq(xy, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'OVTV':
            # 总体振动值 (简化)
            total = ops.vector.synthesize(ax, ay, az)
            return float(np.power(np.mean(total**4) * len(total)/sr, 0.25))
        
        elif metric_id == 'R_FACTOR':
            # R因子 (简化)
            xy = ops.vector.synthesize_xy(ax, ay)
            return float(np.std(xy) / (np.std(az) + 0.001))
        
        # 新增瞬态指标 - 冲击类
        elif metric_id == 'HIC15':
            # 头部损伤准则 HIC15 (标准 15ms)
            total_accel = ops.vector.synthesize(ax, ay, az)
            if len(total_accel) > 0:
                dt = 1.0 / sr
                n_15 = max(1, int(sr * 0.015))
                if n_15 < 2:
                    return 0.0

                if sr < 200:
                    old_n = len(total_accel)
                    new_n = max(old_n, int(old_n * 200.0 / sr))
                    t_old = np.linspace(0, (old_n - 1) / sr, old_n)
                    t_new = np.linspace(0, t_old[-1], new_n)
                    total_accel = np.interp(t_new, t_old, total_accel)
                    n_15 = max(1, int((new_n / t_old[-1]) * 0.015)) if t_old[-1] > 0 else 1
                max_hic = 0.0
                
                for i in range(len(total_accel) - n_15 + 1):
                    segment = total_accel[i:i+n_15]
                    mean_a = np.mean(segment)
                    # mean_a 单位为 g
                    hic = mean_a ** 2.5 * 0.015  # 15ms (修正)
                    max_hic = max(max_hic, hic)
                
                return float(max_hic)
            return 0.0
        
        elif metric_id == 'ACC_H_PEAK':
            # 头部加速度峰值
            head_accel = ops.vector.synthesize(ax, ay, az)
            return float(np.max(np.abs(head_accel)))
        
        elif metric_id == 'JERK_H':
            # 头部冲击度 (jerk = da/dt)
            total_accel = ops.vector.synthesize(ax, ay, az)
            if len(total_accel) > 1:
                jerk = np.diff(total_accel) * sr
                return float(np.max(np.abs(jerk)))
            return 0.0
        
        # SRS指标
        elif metric_id.startswith('SRS_'):
            srs_result = ops.srs.compute(az, sr)
            srs_features = ops.srs.extract_features(srs_result)
            if metric_id == 'SRS_MRS':
                return srs_features.get('SRS_MRS', 0.0)
            elif metric_id == 'SRS_Q':
                return srs_features.get('SRS_Q', 0.0)
            elif metric_id == 'SRS_PV':
                return srs_features.get('SRS_PV', 0.0)
            elif metric_id == 'SRS_ATT':
                return srs_features.get('SRS_ATT', 0.0)
        
        # 疲劳指标
        elif metric_id == 'RFC_CC':
            rf_result = ops.rainflow.count(az)
            return float(rf_result.get('RFC_CC', 0.0))
        
        elif metric_id.startswith('FDS_'):
            rf_result = ops.rainflow.count(az)
            fds_result = ops.fds.compute(rf_result)
            if metric_id == 'FDS_D':
                return fds_result.get('FDS_D', 0.0)
            elif metric_id == 'FDS_R':
                return fds_result.get('FDS_R', 0.0)
        
        # STFT时频指标
        elif metric_id.startswith('STFT_'):
            stft_result = ops.stft.compute(az, sr)
            stft_features = ops.stft.extract_features(stft_result)
            if metric_id == 'STFT_FC':
                return stft_features.get('STFT_FC', 0.0)
            elif metric_id == 'STFT_KT':
                return stft_features.get('STFT_KT', 0.0)
            elif metric_id == 'STFT_CE':
                return stft_features.get('STFT_CE', 0.0)
        
        elif metric_id == 'ACC_RMS':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.sqrt(np.mean(total**2)))
        
        elif metric_id == 'ACC_PEAK':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.max(total))
        
        # 结构指标
        elif metric_id == 'DISP_TR':
            if len(az) > 0:
                disp = self.operator_system.integration.integrate_to_displacement(az, sr)
                return float(np.max(np.abs(disp)))
            return 0.0

        # ── 新增: 脊柱压缩应力 S_D (ISO 2631-5) ──
        elif metric_id == 'S_D':
            if len(ax) > 0 and len(ay) > 0 and len(az) > 0:
                s_d_result = self.operator_system.iso2631_5.compute(
                    ax * 9.81, ay * 9.81, az * 9.81, sr
                )
                return float(s_d_result.get('S_d_MPa', 0.0))
            return 0.0

        # ── 新增: 头部三维合成位移 DISP_HR ──
        elif metric_id == 'DISP_HR':
            if len(ax) > 0 and len(ay) > 0 and len(az) > 0:
                disp_x = ops.integration.integrate_to_displacement(ax, sr)
                disp_y = ops.integration.integrate_to_displacement(ay, sr)
                disp_z = ops.integration.integrate_to_displacement(az, sr)
                min_len = min(len(disp_x), len(disp_y), len(disp_z))
                disp_3d = np.sqrt(disp_x[:min_len]**2 + disp_y[:min_len]**2 + disp_z[:min_len]**2)
                return float(np.max(disp_3d))
            return 0.0

        # ── 新增: 全时域统计指标 (实验组 E / 对照组 C / 胸骨 S) ──
        elif metric_id.endswith('_E') or metric_id.endswith('_C') or metric_id.endswith('_S'):
            group = data_window.get('group', 'E')
            data_arrays = {'Ax': ax, 'Ay': ay, 'Az': az}

            for axis in ['Ax', 'Ay', 'Az']:
                for stat in ['RMS', 'Peak', 'Crest', 'VDV', 'Skew', 'Kurt', 'MAV', 'Impf']:
                    expected_key = f'{stat}_{axis}_{group}'
                    if metric_id != expected_key:
                        continue

                    arr = data_arrays[axis]
                    if len(arr) < 10:
                        return 0.0

                    if stat == 'RMS':
                        return float(np.sqrt(np.mean(arr**2)))
                    elif stat == 'Peak':
                        return float(np.max(np.abs(arr)))
                    elif stat == 'Crest':
                        rms = np.sqrt(np.mean(arr**2))
                        return float(np.max(np.abs(arr)) / rms) if rms > 1e-6 else 0.0
                    elif stat == 'VDV':
                        return float(np.power(np.sum(arr**4) / sr, 0.25))
                    elif stat == 'Skew':
                        from scipy import stats
                        return float(stats.skew(arr))
                    elif stat == 'Kurt':
                        from scipy import stats
                        return float(stats.kurtosis(arr, fisher=True))
                    elif stat == 'MAV':
                        return float(np.mean(np.abs(arr)))
                    elif stat == 'Impf':
                        peak = np.max(np.abs(arr))
                        mav = np.mean(np.abs(arr))
                        return float(peak / mav) if mav > 1e-6 else 0.0

        # ── 总VDV (E_total_VDV / C_total_VDV) ──
        elif metric_id == 'E_total_VDV':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.power(np.sum(total**4) / sr, 0.25))
        elif metric_id == 'C_total_VDV':
            total = np.sqrt(ax**2 + ay**2 + az**2)
            return float(np.power(np.sum(total**4) / sr, 0.25))

        # ── 新增: 频段衰减指标 ──
        elif metric_id.startswith('BAND_ATT_'):
            exp_data = data_window.get('exp_data', az)
            ctrl_data = data_window.get('ctrl_data', None)
            if ctrl_data is None:
                return 0.0
            from .operators import BandpassAttenuationOperator
            bpf = BandpassAttenuationOperator(fs=sr)
            results = bpf.compute_band_attenuation(exp_data, ctrl_data)
            band_key = metric_id.replace('BAND_ATT_', '').replace('_', '-') + 'Hz'
            return float(results.get(band_key, 0.0))

        logger.warning(
            "V1引擎 _calculate_single_metric 碰到未知指标 %s，返回 0.0。"
            "请检查该指标是否已在 engine_v2.py 中实现。",
            metric_id
        )
        return 0.0
    
    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """
        计算总体评分
        
        Args:
            metrics: 指标结果字典
            
        Returns:
            总体评分 (0-100)
        """
        if not metrics:
            return 0.0
        
        # 简化评分: 基于主要指标的加权平均
        weights = {
            'SEAT_Z': 0.15,
            'SEAT_XY': 0.10,
            'VDV_Z': 0.15,
            'AW_Z': 0.10,
            'HIC15': 0.10,
            'ACC_H_PEAK': 0.10,
            'FDS_D': 0.10,
            'R_FACTOR': 0.10,
            'ACC_RMS': 0.05,
            'ACC_PEAK': 0.05,
        }
        
        def _threshold_score(value, thresholds):
            excellent = thresholds.get('excellent')
            good = thresholds.get('good')
            fair = thresholds.get('fair')
            poor = thresholds.get('poor')
            if excellent is not None and value <= excellent:
                return 95.0 + (value / max(excellent, 0.001)) * 5.0
            if good is not None and value <= good:
                return 90.0 - (value - excellent) / max(good - excellent, 0.001) * 20.0
            if fair is not None and value <= fair:
                return 70.0 - (value - good) / max(fair - good, 0.001) * 20.0
            if poor is not None and value <= poor:
                return max(0.0, 50.0 - (value - fair) / max(poor - fair, 0.001) * 50.0)
            fair_val = fair if fair is not None else value
            return max(0.0, 50.0 - (value - fair_val) / max(fair_val, 0.001) * 50.0)

        total_weight = 0.0
        weighted_score = 0.0

        for metric_id, weight in weights.items():
            if metric_id in metrics:
                value = metrics[metric_id]
                thresholds_entry = METRIC_THRESHOLDS.get(metric_id, {})
                if thresholds_entry:
                    normalized_score = _threshold_score(value, thresholds_entry)
                else:
                    normalized_score = max(0.0, min(100.0, 100.0 - value * 10.0))
                weighted_score += normalized_score * weight
                total_weight += weight

        if total_weight > 0:
            return weighted_score / total_weight
        return 50.0
    
    def _assess_risk(self, metrics: Dict[str, float]) -> RiskLevel:
        """
        评估风险等级
        
        Args:
            metrics: 指标结果字典
            
        Returns:
            风险等级
        """
        # 简化风险评估逻辑
        hic = metrics.get('HIC15', 0.0)
        acc_peak = metrics.get('ACC_H_PEAK', 0.0)
        fds = metrics.get('FDS_D', 0.0)
        
        if hic > 700 or acc_peak > 20 or fds > 1.0:
            return RiskLevel.DANGER
        elif hic > 500 or acc_peak > 15 or fds > 0.5:
            return RiskLevel.WARNING
        elif hic > 300 or acc_peak > 10 or fds > 0.2:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE
    
    def _result_to_dict(self, result: EvaluationResult) -> Dict[str, Any]:
        """
        将结果对象转换为字典
        
        Args:
            result: 评测结果对象
            
        Returns:
            结果字典
        """
        return {
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'metrics': result.metrics,
            'overall_score': result.overall_score,
            'risk_level': result.risk_level.value,
            'metadata': result.metadata
        }
