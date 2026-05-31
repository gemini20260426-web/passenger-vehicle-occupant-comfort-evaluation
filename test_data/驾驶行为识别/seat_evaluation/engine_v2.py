#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测引擎核心（重构版）
基于9大算子系统的多通道多位置指标计算引擎
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal

from .operators import OperatorSystem
from .data_preprocessor import DataPreprocessor
from .imu_location_config import (
    IMU_LOCATION_MAPPING, LOCATION_IDS,
    get_location_config, get_metrics_for_location,
    get_channel_by_location
)
from ..analysis.core_types import (
    EvaluationTrigger, EvaluationResult, LocationEvaluationResult,
    RiskLevel, INDICATOR_DEFINITIONS, generate_single_group_diagnosis
)
from .metadata_registry import get_global_registry, METRIC_THRESHOLDS

logger = logging.getLogger(__name__)

MIN_WINDOW_SAMPLES = 20
MIN_SAMPLES_PER_METRIC = {
    'SRS_MRS': 50, 'SRS_Q': 50, 'SRS_PV': 50, 'SRS_ATT': 50,
    'RFC_CC': 100, 'FDS_D': 100, 'FDS_R': 100,
    'JERK_H': 30,
    'SEAT_Z': 16, 'SEAT_XY': 16,
    'AW_Z': 16, 'AW_XY': 16,
    'TR_Z': 16, 'VDV_Z': 16,
    'DISP_TR': 16, 'OVTV': 16, 'R_FACTOR': 16,
    'STFT_FC': 64, 'STFT_KT': 64, 'STFT_CE': 64,
    'S_D': 100,
}
METRIC_INSUFFICIENT_DATA = -1.0


class MultiChannelSeatEvaluationEngine(QObject):
    """多通道座椅评测引擎"""
    
    evaluation_started = Signal(dict)
    evaluation_completed = Signal(dict)
    metric_calculated = Signal(dict)
    location_result_ready = Signal(dict)
    
    def __init__(self, config_manager=None, data_storage=None):
        super().__init__()
        self.config_manager = config_manager
        self.data_storage = data_storage
        
        # 初始化算子系统
        self.operator_system = OperatorSystem()

        # 初始化数据预处理器
        self.preprocessor = DataPreprocessor(sample_rate=1000.0, lowpass_cutoff=10.0)

        # 预处理级别: 0=原始, 1=校准+对齐, 2=校准+对齐+滤波
        self.preprocess_level = 1

        # 默认采样率
        self.default_sample_rate = 100.0

        logger.info("多通道座椅评测引擎初始化完成")
    
    def set_preprocess_level(self, level: int):
        self.preprocess_level = max(0, min(2, level))
        logger.info(f"预处理级别已设置为: Level {self.preprocess_level}")
    
    def evaluate_by_event(self, trigger: Dict[str, Any], preprocess_level: int = None) -> Optional[EvaluationResult]:
        """
        基于事件执行多通道评测
        
        Args:
            trigger: 评测触发器字典
        
        Returns:
            EvaluationResult 评测结果对象
        """
        try:
            self.evaluation_started.emit(trigger)
            
            trigger_id = trigger.get('event_id', trigger.get('trigger_id', ''))
            event_type = trigger.get('event_type', '')
            source_behavior = trigger.get('source_behavior', event_type)
            timestamp = trigger.get('timestamp', 0.0)
            metrics = trigger.get('metrics', [])
            data_window = trigger.get('data_window', {'pre': 0.5, 'post': 1.5})
            multi_channel_data = trigger.get('multi_channel_data', {})
            locations = trigger.get('locations', LOCATION_IDS)
            group_tag = trigger.get('group_tag', 'experimental')
            
            detected_sr = multi_channel_data.get('_sample_rate', self.default_sample_rate)
            
            if not metrics:
                metrics = self._get_all_metrics()
            
            location_results = {}
            all_metrics = {}

            location_data_windows = {}
            for location_id in locations:
                location_config = get_location_config(location_id)
                if not location_config:
                    continue

                channel_id = get_channel_by_location(location_id, group_tag)
                if not channel_id or channel_id not in multi_channel_data:
                    continue

                channel_data = multi_channel_data[channel_id]
                location_data_window = self._extract_channel_data_window(
                    channel_data, data_window, sample_rate=detected_sr
                )
                if location_data_window:
                    location_data_windows[location_id] = location_data_window
            
            floor_window = location_data_windows.get('seat_bottom')
            
            for location_id in locations:
                location_config = get_location_config(location_id)
                if not location_config:
                    logger.warning(f"未知位置: {location_id}")
                    continue
                
                if location_id not in location_data_windows:
                    logger.warning(f"位置 {location_id} 无法提取数据窗口")
                    continue

                channel_id = get_channel_by_location(location_id, group_tag)

                location_data_window = location_data_windows[location_id]

                if floor_window is not None and location_id in ('seat_r', 'torso', 'head'):
                    floor_az = floor_window.get('az')
                    if floor_az is not None and len(floor_az) == len(location_data_window.get('az', [])):
                        location_data_window = dict(location_data_window)
                        location_data_window['floor_az'] = floor_az
                    floor_ax = floor_window.get('ax')
                    floor_ay = floor_window.get('ay')
                    if floor_ax is not None and floor_ay is not None and \
                       len(floor_ax) == len(location_data_window.get('ax', [])):
                        location_data_window['floor_axy'] = np.sqrt(
                            np.array(floor_ax)**2 + np.array(floor_ay)**2
                        )
                
                location_metrics = get_metrics_for_location(location_id)
                location_metrics = [m for m in location_metrics if m in metrics]
                if not location_metrics:
                    location_metrics = metrics
                
                calculated_metrics = self._calculate_metrics_for_location(
                    location_data_window, location_metrics, location_id
                )

                profile = self._build_vibration_profile(
                    location_data_window, calculated_metrics, location_id
                )

                location_result = LocationEvaluationResult(
                    location_id=location_id,
                    location_name=location_config.location_name_cn,
                    channel_id=channel_id,
                    metrics=calculated_metrics,
                    location_score=0.0,
                    risk_level=RiskLevel.SAFE,
                    profile=profile,
                    metadata={
                        'location_config': location_config,
                        'data_window': data_window
                    }
                )
                
                location_results[location_id] = location_result
                
                self.location_result_ready.emit({
                    'trigger_id': trigger_id,
                    'location_id': location_id,
                    'location_result': location_result
                })
                
                for metric_id, value in calculated_metrics.items():
                    if metric_id not in all_metrics:
                        all_metrics[metric_id] = []
                    all_metrics[metric_id].append(value)
            
            overall_metrics = self._calculate_overall_metrics(all_metrics, location_results)

            diagnosis = generate_single_group_diagnosis(location_results, group_tag)

            result = EvaluationResult(
                trigger_id=trigger_id,
                event_type=event_type,
                timestamp=timestamp,
                metrics=overall_metrics,
                overall_score=0.0,
                risk_level=RiskLevel.SAFE,
                location_results=location_results,
                metadata={
                    'source_behavior': source_behavior,
                    'locations': locations,
                    'group_tag': group_tag,
                    'diagnosis': diagnosis.to_dict()
                }
            )

            result_dict = self._result_to_dict(result)
            self.evaluation_completed.emit(result_dict)

            logger.info(f"座椅评测完成: {trigger_id}, 评测位置: {len(location_results)}")
            
            return result
            
        except Exception as e:
            logger.error(f"座椅评测失败: {e}", exc_info=True)
            return None
    
    def _get_all_metrics(self) -> List[str]:
        """获取所有指标"""
        return list(INDICATOR_DEFINITIONS.keys())
    
    def _extract_channel_data_window(self, channel_data: Dict[str, Any], 
                                     window_config: Dict[str, float],
                                     sample_rate: float = None) -> Optional[Dict[str, Any]]:
        """
        提取单通道数据窗口（单位转换：m/s² → g）
        
        Args:
            channel_data: 通道数据 {'ax': [...], 'ay': [...], 'az': [...], 'gx': [...], ...}
            window_config: 窗口配置
            sample_rate: 检测到的采样率，None则使用默认值
        
        Returns:
            数据窗口字典，包含ax/ay/az/gx/gy/gz/sample_rate（加速度单位：g）
        """
        try:
            ax = np.array(channel_data.get('ax', [])) / 9.81
            ay = np.array(channel_data.get('ay', [])) / 9.81
            az = np.array(channel_data.get('az', [])) / 9.81
            
            if len(ax) == 0 or len(ay) == 0 or len(az) == 0:
                logger.debug(f"通道数据为空，ax={len(ax)}, ay={len(ay)}, az={len(az)}，跳过数据窗口提取")
                return None
            
            sr = sample_rate if sample_rate else self.default_sample_rate
            
            data_window = {
                'ax': ax,
                'ay': ay,
                'az': az,
                'sample_rate': sr
            }
            
            gx = channel_data.get('gx', None)
            if gx is not None and len(gx) >= len(ax):
                data_window['gx'] = np.array(gx)
                data_window['gy'] = np.array(channel_data.get('gy', np.zeros_like(gx)))
                data_window['gz'] = np.array(channel_data.get('gz', np.zeros_like(gx)))
            
            timestamps = channel_data.get('timestamps', [])
            if timestamps and len(timestamps) == len(ax):
                data_window['timestamps'] = timestamps
            
            return data_window
            
        except Exception as e:
            logger.error(f"提取通道数据窗口失败: {e}")
            return None
    
    def _calculate_metrics_for_location(self, data_window: Dict[str, Any], 
                                       metrics: List[str], location_id: str) -> Dict[str, float]:
        """
        为指定位置计算指标
        
        Args:
            data_window: 数据窗口
            metrics: 指标列表
            location_id: 位置ID
        
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
                    'location_id': location_id,
                    'definition': INDICATOR_DEFINITIONS.get(metric_id, {})
                })
                
            except Exception as e:
                logger.error(f"位置 {location_id} 计算指标 {metric_id} 失败: {e}")
                results[metric_id] = 0.0
        
        return results
    
    def _calculate_single_metric(self, metric_id: str, 
                               data_window: Dict[str, Any]) -> float:
        """
        计算单个指标
        
        Args:
            metric_id: 指标ID
            data_window: 数据窗口
        
        Returns:
            指标值
        """
        ops = self.operator_system
        ax = data_window.get('ax', np.array([]))
        ay = data_window.get('ay', np.array([]))
        az = data_window.get('az', np.array([]))
        sr = data_window.get('sample_rate', self.default_sample_rate)
        
        # CFC 滤波器实例（按 SAE J211-1 分级）
        from .operators import CFCOperator as _CFC
        _cfc60 = _CFC(cfc=60)
        _cfc600 = _CFC(cfc=600)
        _cfc1000 = _CFC(cfc=1000)
        
        n_samples = len(az) if len(az) > 0 else len(ax) if len(ax) > 0 else len(ay)
        min_required = MIN_SAMPLES_PER_METRIC.get(metric_id, MIN_WINDOW_SAMPLES)
        if n_samples < min_required:
            return METRIC_INSUFFICIENT_DATA
        
        # 原有频域指标
        if metric_id == 'SEAT_Z':
            az_cfc = _cfc1000.filter(az, sr) if len(az) >= 4 else az
            floor_az = data_window.get('floor_az', None)
            if floor_az is not None and len(floor_az) > 0:
                floor_az_cfc = _cfc1000.filter(floor_az, sr) if len(floor_az) >= 4 else floor_az
                f_seat, psd_seat = ops.psd.compute(az_cfc, sr, nperseg=min(1024, len(az_cfc)))
                f_floor, psd_floor = ops.psd.compute(floor_az_cfc, sr, nperseg=min(1024, len(floor_az_cfc)))
                psd_seat_w = ops.weighting.apply_weighting_z_psd(psd_seat, f_seat)
                psd_floor_w = ops.weighting.apply_weighting_z_psd(psd_floor, f_floor)
                integral_seat = np.trapz(psd_seat_w, f_seat)
                integral_floor = np.trapz(psd_floor_w, f_floor)
                if integral_floor > 0:
                    coh_result = ops.csd.compute(floor_az_cfc, az_cfc, sr, nperseg=min(1024, len(az_cfc)))
                    if len(coh_result.get('coherence', [])) > 0:
                        mean_coh = float(np.mean(coh_result['coherence']))
                        if mean_coh < 0.5:
                            logger.warning(f"SEAT_Z coherence={mean_coh:.3f} < 0.5, 传递率需谨慎参考")
                    return float(np.sqrt(integral_seat / integral_floor))
            weighted = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'SEAT_XY':
            ax_cfc = _cfc600.filter(ax, sr) if len(ax) >= 4 else ax
            ay_cfc = _cfc600.filter(ay, sr) if len(ay) >= 4 else ay
            xy = ops.vector.synthesize_xy(ax_cfc, ay_cfc)
            floor_axy = data_window.get('floor_axy', None)
            if floor_axy is not None and len(floor_axy) > 0:
                f_seat, psd_seat = ops.psd.compute(xy, sr, nperseg=min(1024, len(xy)))
                f_floor, psd_floor = ops.psd.compute(floor_axy, sr, nperseg=min(1024, len(floor_axy)))
                psd_seat_w = ops.weighting.apply_weighting_xy_psd(psd_seat, f_seat)
                psd_floor_w = ops.weighting.apply_weighting_xy_psd(psd_floor, f_floor)
                integral_seat = np.trapz(psd_seat_w, f_seat)
                integral_floor = np.trapz(psd_floor_w, f_floor)
                if integral_floor > 0:
                    coh_result = ops.csd.compute(floor_axy, xy, sr, nperseg=min(1024, len(xy)))
                    if len(coh_result.get('coherence', [])) > 0:
                        mean_coh = float(np.mean(coh_result['coherence']))
                        if mean_coh < 0.5:
                            logger.warning(f"SEAT_XY coherence={mean_coh:.3f} < 0.5, 传递率需谨慎参考")
                    return float(np.sqrt(integral_seat / integral_floor))
            weighted = ops.weighting.apply_weighting_xy_via_freq(xy, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'VDV_Z':
            az_cfc = _cfc1000.filter(az, sr) if len(az) >= 4 else az
            az_w = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
            dt = 1.0 / sr
            vdv = np.power(np.sum(az_w**4) * dt, 0.25)
            return float(vdv)
        
        elif metric_id == 'TR_Z':
            az_cfc = _cfc1000.filter(az, sr) if len(az) >= 4 else az
            floor_az = data_window.get('floor_az', None)
            if floor_az is not None and len(floor_az) > 0 and len(az_cfc) > 0:
                floor_az_cfc = _cfc1000.filter(floor_az, sr) if len(floor_az) >= 4 else floor_az
                tf_result = ops.csd.transfer_function_db(
                    floor_az_cfc, az_cfc, sr, nperseg=min(1024, len(az_cfc)))
                coh = float(np.mean(tf_result.get('coherence', [np.nan])))
                if not np.isnan(coh) and coh < 0.5:
                    logger.warning(f"TR_Z coherence={coh:.3f} < 0.5, 传递函数峰值需谨慎参考")
                if tf_result.get('TR_peak_dB', 0.0) != 0.0:
                    return float(tf_result['TR_peak_dB'])
            if len(az_cfc) > 0 and len(data_window.get('floor_az', az_cfc)) > 0:
                return float(np.std(az_cfc) / (np.std(data_window.get('floor_az', az_cfc)) + 0.001))
            return 1.0
        
        elif metric_id == 'AW_Z':
            az_cfc = _cfc1000.filter(az, sr) if len(az) >= 4 else az
            weighted = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'AW_XY':
            ax_cfc = _cfc60.filter(ax, sr) if len(ax) >= 4 else ax
            ay_cfc = _cfc60.filter(ay, sr) if len(ay) >= 4 else ay
            xy = ops.vector.synthesize_xy(ax_cfc, ay_cfc)
            weighted = ops.weighting.apply_weighting_xy_via_freq(xy, sr)
            return float(np.sqrt(np.mean(weighted**2)))
        
        elif metric_id == 'OVTV':
            # 公式: OVTV = sqrt(kx²·AW_X² + ky²·AW_Y² + kz²·AW_Z²), kx=ky=1.4, kz=1.0
            aw_x = float(np.sqrt(np.mean(ops.weighting.apply_weighting_xy_via_freq(ax, sr)**2))) if len(ax) > 0 else 0.0
            aw_y = float(np.sqrt(np.mean(ops.weighting.apply_weighting_xy_via_freq(ay, sr)**2))) if len(ay) > 0 else 0.0
            aw_z = float(np.sqrt(np.mean(ops.weighting.apply_weighting_z_via_freq(az, sr)**2))) if len(az) > 0 else 0.0
            return float(np.sqrt(1.4**2 * aw_x**2 + 1.4**2 * aw_y**2 + 1.0**2 * aw_z**2))
        
        elif metric_id == 'R_FACTOR':
            return float(np.std(ax + ay) / (np.std(az) + 0.001))
        
        # 新增瞬态指标 - 冲击类
        elif metric_id == 'HIC15':
            if len(az) > 0:
                ax_cfc = _cfc600.filter(ax, sr) if len(ax) >= 4 else ax
                ay_cfc = _cfc600.filter(ay, sr) if len(ay) >= 4 else ay
                az_cfc = _cfc600.filter(az, sr) if len(az) >= 4 else az
                a_mag = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
                dt = 1.0 / sr
                n_15 = max(1, int(0.015 / dt))
                if n_15 < 3:
                    target_sr = max(sr, 200.0)
                    t_original = np.arange(len(a_mag)) / sr
                    t_target = np.arange(0, t_original[-1], 1.0 / target_sr)
                    a_mag = np.interp(t_target, t_original, a_mag)
                    sr = target_sr
                    dt = 1.0 / sr
                    n_15 = max(1, int(0.015 * sr))
                    logger.debug(f"HIC15: sr {data_window.get('sample_rate', 0):.0f}→{sr:.0f}Hz (保障≥3样本/15ms)")
                max_hic = 0.0

                for i in range(len(a_mag) - n_15 + 1):
                    segment = a_mag[i:i+n_15]
                    a_avg = np.mean(segment)
                    t1 = i * dt
                    t2 = (i + n_15 - 1) * dt
                    dt_window = t2 - t1
                    if dt_window > 0:
                        hic = dt_window * (a_avg ** 2.5)
                        max_hic = max(max_hic, hic)

                return float(max_hic)
            return 0.0

        elif metric_id == 'S_D':
            ax_ms2 = ax * 9.81
            ay_ms2 = ay * 9.81
            az_ms2 = az * 9.81
            result = ops.iso2631_5.compute(ax_ms2, ay_ms2, az_ms2, sr)
            return result.get('S_d_MPa', 0.0)
        
        elif metric_id == 'ACC_H_PEAK':
            ax_cfc = _cfc600.filter(ax, sr) if len(ax) >= 4 else ax
            ay_cfc = _cfc600.filter(ay, sr) if len(ay) >= 4 else ay
            az_cfc = _cfc600.filter(az, sr) if len(az) >= 4 else az
            head_accel = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
            return float(np.max(np.abs(head_accel)))
        
        elif metric_id == 'JERK_H':
            ax_cfc = _cfc600.filter(ax, sr) if len(ax) >= 4 else ax
            ay_cfc = _cfc600.filter(ay, sr) if len(ay) >= 4 else ay
            az_cfc = _cfc600.filter(az, sr) if len(az) >= 4 else az
            head_accel = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
            head_accel = ops.cfc.filter(head_accel, sr)
            jerk = np.diff(head_accel) * sr
            return float(np.max(np.abs(jerk))) if len(jerk) > 0 else 0.0
        
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
        
        elif metric_id == 'DISP_TR':
            if len(az) > 0:
                az_cfc = _cfc60.filter(az, sr) if len(az) >= 4 else az
                disp = ops.integration.integrate_to_displacement(az_cfc, sr)
                return float(np.max(np.abs(disp)))
            return 0.0
        
        elif metric_id == 'DISP_HR':
            # 管道: OP-CFC(CFC600)→OP-INT2→OP-VECSYN→OP-MAX
            # 公式: DISP_HR = max(√(Dx²(t)+Dy²(t)+Dz²(t)))
            n_ref = max(len(ax), len(ay), len(az))
            if n_ref < 4:
                return 0.0
            ax_f = _cfc600.filter(ax, sr) if len(ax) >= 4 else np.zeros(n_ref)
            ay_f = _cfc600.filter(ay, sr) if len(ay) >= 4 else np.zeros(n_ref)
            az_f = _cfc600.filter(az, sr) if len(az) >= 4 else np.zeros(n_ref)
            dx = ops.integration.integrate_to_displacement(ax_f, sr) if len(ax) >= 4 else np.zeros(n_ref)
            dy = ops.integration.integrate_to_displacement(ay_f, sr) if len(ay) >= 4 else np.zeros(n_ref)
            dz = ops.integration.integrate_to_displacement(az_f, sr) if len(az) >= 4 else np.zeros(n_ref)
            disp_3d = ops.vector.synthesize(dx, dy, dz)
            return float(np.max(disp_3d))
        
        return 0.0
    
    def _calculate_location_score(self, metrics: Dict[str, float], location_id: str) -> float:
        """
        计算位置评分（基于行业标准阈值）

        使用 SAE J211 / ISO 2631 阈值进行归一化评分:
            优秀(90-100)、良好(70-90)、一般(50-70)、差(0-50)
        """
        if not metrics:
            return 50.0

        weights = {}
        for metric_id in metrics:
            weights[metric_id] = 1.0 / len(metrics)

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

        weighted_score = 0.0
        total_weight = 0.0

        for metric_id, weight in weights.items():
            value = metrics[metric_id]
            thresholds = METRIC_THRESHOLDS.get(metric_id, {})
            if thresholds:
                normalized_score = _threshold_score(value, thresholds)
            else:
                normalized_score = max(0.0, min(100.0, 100.0 - value * 10.0))
            weighted_score += normalized_score * weight
            total_weight += weight

        if total_weight > 0:
            return weighted_score / total_weight
        return 50.0
    
    def _assess_location_risk(self, metrics: Dict[str, float], location_id: str) -> RiskLevel:
        """
        评估位置风险等级
        
        Args:
            metrics: 指标结果
            location_id: 位置ID
        
        Returns:
            风险等级
        """
        hic = metrics.get('HIC15', 0.0)
        acc_peak = metrics.get('ACC_H_PEAK', 0.0)
        fds = metrics.get('FDS_D', 0.0)
        
        if hic > 1000 or acc_peak > 20 or fds > 0.5:
            return RiskLevel.DANGER
        elif hic > 500 or acc_peak > 10 or fds > 0.2:
            return RiskLevel.WARNING
        elif hic > 100 or acc_peak > 5 or fds > 0.05:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE
    
    def _calculate_overall_metrics(self, all_metrics: Dict[str, List[float]], 
                                  location_results: Dict[str, LocationEvaluationResult]) -> Dict[str, float]:
        """
        计算总体指标（加权平均）
        
        Args:
            all_metrics: 各位置的指标值
            location_results: 位置结果
        
        Returns:
            总体指标
        """
        overall_metrics = {}
        
        for metric_id, values in all_metrics.items():
            if values:
                overall_metrics[metric_id] = float(np.mean(values))
        
        return overall_metrics
    
    def _calculate_overall_score(self, metrics: Dict[str, float], 
                                location_results: Dict[str, LocationEvaluationResult]) -> float:
        """
        计算总体评分
        
        Args:
            metrics: 总体指标
            location_results: 位置结果
        
        Returns:
            总体评分 (0-100)
        """
        if not location_results:
            return 50.0
        
        location_weights = {
            'head': 0.3,
            'torso': 0.2,
            'seat_r': 0.3,
            'sternum': 0.1,
            'seat_bottom': 0.1
        }
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for location_id, result in location_results.items():
            weight = location_weights.get(location_id, 0.2)
            weighted_score += result.location_score * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_score / total_weight
        return 50.0
    
    def _assess_overall_risk(self, location_results: Dict[str, LocationEvaluationResult]) -> RiskLevel:
        """
        评估总体风险
        
        Args:
            location_results: 位置结果
        
        Returns:
            总体风险等级
        """
        if not location_results:
            return RiskLevel.SAFE
        
        risk_levels = [result.risk_level for result in location_results.values()]
        
        # 取最高风险等级
        if RiskLevel.DANGER in risk_levels:
            return RiskLevel.DANGER
        elif RiskLevel.WARNING in risk_levels:
            return RiskLevel.WARNING
        elif RiskLevel.CAUTION in risk_levels:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE
    
    def _build_vibration_profile(self, window_data: Dict[str, Any],
                                 metrics: Dict[str, float],
                                 location_id: str) -> Dict[str, Any]:
        """
        构建多维振动剖面数据（v3.0 — 免评分模式）
        
        返回6维度剖面：
        - magnitude: 幅值统计（RMS/peak/p95/p99 per axis + OVTV/AW）
        - frequency: 频域特征（主频、倍频程能量分布）
        - transmission: 传递特性
        - impact: 冲击特征（波峰因数、峰值事件、急动度、HIC/VDV）
        - temporal: 时间分段分析
        - iso_ref: ISO 2631 舒适参考区间
        
        Args:
            window_data: 原始数据窗口 {'ax': ndarray, 'ay': ndarray, 'az': ndarray, 'sample_rate': float, ...}
            metrics: 已计算的指标字典
            location_id: 位置ID
        
        Returns:
            振动剖面字典
        """
        try:
            from scipy.fft import rfft, rfftfreq
            
            sr = window_data.get('sample_rate', 1000.0)
            ax = np.asarray(window_data.get('ax', []), dtype=np.float64)
            ay = np.asarray(window_data.get('ay', []), dtype=np.float64)
            az = np.asarray(window_data.get('az', []), dtype=np.float64)
            
            if len(ax) < 20:
                return {'error': 'insufficient_data'}
            
            dt = 1.0 / sr
            n = len(ax)
            t = np.arange(n) * dt
            
            a_res = np.sqrt(ax**2 + ay**2 + az**2)
            
            profile = {}
            
            # ---- Dimension 1: Magnitude ----
            magnitude = {}
            for lbl, arr in [('X', ax), ('Y', ay), ('Z', az), ('res', a_res)]:
                magnitude[lbl] = {
                    'rms': float(np.sqrt(np.mean(arr**2))),
                    'p95': float(np.percentile(np.abs(arr), 95)),
                    'p99': float(np.percentile(np.abs(arr), 99)),
                    'max': float(np.max(np.abs(arr))),
                }
            magnitude['OVTV'] = float(np.sqrt(np.mean(ax**2 + ay**2 + az**2)))
            
            aw_z = float(np.sqrt(np.mean(az**2)))
            aw_xy = float(np.sqrt(np.mean(ax**2 + ay**2)))
            magnitude['AW_Z'] = aw_z
            magnitude['AW_XY'] = aw_xy
            profile['magnitude'] = magnitude
            
            # ---- Dimension 1.5: Condition (驾驶工况) ----
            condition = {}
            speed_arr = np.asarray(window_data.get('speed', []), dtype=np.float64)
            wheel_arr = np.asarray(window_data.get('wheel', []), dtype=np.float64)
            
            if len(speed_arr) >= 20:
                cond_labels = [(0, 5, '0-5'), (5, 10, '5-10'), (10, 15, '10-15'),
                              (15, 20, '15-20'), (20, 25, '20-25'), (25, 30, '25-30'),
                              (30, 35, '30-35'), (35, 40, '35-40'), (40, 50, '40-50'),
                              (50, 70, '50-70')]
                speed_band_vibration = {}
                for lo, hi, label in cond_labels:
                    mask = (speed_arr >= lo) & (speed_arr < hi)
                    n_mask = np.sum(mask)
                    if n_mask >= 10:
                        band_rms = float(np.sqrt(np.mean(a_res[mask]**2))) if n_mask > 0 else 0.0
                        band_p95 = float(np.percentile(np.abs(a_res[mask]), 95)) if n_mask > 1 else 0.0
                        speed_band_vibration[label] = {
                            'rms_g': round(band_rms, 3),
                            'p95_g': round(band_p95, 3),
                            'n_samples': int(n_mask),
                            'pct': round(n_mask / len(speed_arr) * 100, 1),
                        }
                condition['speed_band_vibration'] = speed_band_vibration
                
                condition['speed_mean'] = float(np.mean(speed_arr))
                condition['speed_std'] = float(np.std(speed_arr))
                condition['speed_median'] = float(np.median(speed_arr))
                condition['speed_range'] = [float(np.min(speed_arr)), float(np.max(speed_arr))]
                
                if len(a_res) == len(speed_arr) and len(a_res) >= 10:
                    corr = float(np.corrcoef(speed_arr, a_res)[0, 1]) if np.std(speed_arr) > 1e-6 else 0.0
                    condition['speed_vibration_correlation'] = round(corr, 3)
            
            if len(wheel_arr) >= 10:
                condition['wheel_abs_mean'] = round(float(np.mean(np.abs(wheel_arr))), 2)
                condition['wheel_abs_max'] = round(float(np.max(np.abs(wheel_arr))), 2)
                turning_pct = float(np.sum(np.abs(wheel_arr) > 10) / len(wheel_arr) * 100)
                condition['turning_ratio_pct'] = round(turning_pct, 1)
            
            profile['condition'] = condition
            
            # ---- Dimension 2: Frequency ----
            freqs = rfftfreq(n, dt)
            freq_profile = {}
            
            for lbl, arr in [('X', ax), ('Y', ay), ('Z', az), ('res', a_res)]:
                mag = np.abs(rfft(arr))
                top_indices = np.argsort(mag)[-5:][::-1]
                peaks = []
                seen_hz = set()
                for idx in top_indices:
                    hz = round(float(freqs[idx]), 1)
                    if hz > 0 and hz <= 100 and hz not in seen_hz:
                        peaks.append((hz, round(float(mag[idx]), 1)))
                        seen_hz.add(hz)
                        if len(peaks) >= 3:
                            break
                freq_profile[lbl] = peaks
            
            res_mag = np.abs(rfft(a_res))
            total_energy = np.sum(res_mag**2)
            bands = [
                (0.1, 1, '0.1-1Hz'),
                (1, 2, '1-2Hz'),
                (2, 4, '2-4Hz'),
                (4, 8, '4-8Hz'),
                (8, 20, '8-20Hz'),
                (20, 50, '20-50Hz'),
                (50, 100, '50-100Hz'),
            ]
            band_energy = {}
            for lo, hi, label in bands:
                mask = (freqs >= lo) & (freqs < hi)
                pct = float(np.sum(res_mag[mask]**2) / total_energy * 100) if total_energy > 0 else 0.0
                band_energy[label] = round(pct, 1)
            freq_profile['band_energy_pct'] = band_energy
            
            dom_band_max = max(band_energy.items(), key=lambda x: x[1]) if band_energy else ('N/A', 0)
            freq_profile['dominant_band'] = dom_band_max[0]
            freq_profile['dominant_band_pct'] = dom_band_max[1]
            
            profile['frequency'] = freq_profile
            
            # ---- Dimension 3: Transmission ----
            trans = {}
            floor_az = window_data.get('floor_az', None)
            floor_axy = window_data.get('floor_axy', None)
            
            if floor_az is not None and len(floor_az) == n:
                trans['Z_trans_base'] = round(float(np.sqrt(np.mean(az**2))) / max(float(np.sqrt(np.mean(floor_az**2))), 1e-6), 2)
            if floor_axy is not None and len(floor_axy) == n:
                trans['XY_trans_base'] = round(aw_xy / max(float(np.sqrt(np.mean(floor_axy**2))), 1e-6), 2)
            
            trans['SEAT_Z'] = metrics.get('SEAT_Z', None)
            trans['SEAT_XY'] = metrics.get('SEAT_XY', None)
            profile['transmission'] = trans
            
            # ---- Dimension 4: Impact ----
            impact = {}
            for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
                rms = float(np.sqrt(np.mean(arr**2)))
                peak = float(np.max(np.abs(arr)))
                cf = round(peak / max(rms, 1e-6), 1)
                impact[f'crest_{lbl}'] = cf
            
            thresholds_g = [2.0, 5.0, 10.0, 20.0]
            peak_counts = {}
            for th in thresholds_g:
                count = int(np.sum(np.abs(a_res) > th))
                peak_counts[f'>{th:.0f}g'] = count
            impact['peak_counts'] = peak_counts
            
            jerk_total = 0.0
            jerk_max = 0.0
            for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
                da = np.diff(arr) / dt
                j_mean = float(np.mean(np.abs(da)))
                j_max = float(np.max(np.abs(da)))
                impact[f'jerk_{lbl}_mean'] = round(j_mean, 1)
                impact[f'jerk_{lbl}_max'] = round(j_max, 1)
                jerk_total += j_mean
                jerk_max = max(jerk_max, j_max)
            impact['jerk_total_mean'] = round(jerk_total, 1)
            impact['jerk_max'] = round(jerk_max, 1)
            
            impact['HIC15'] = metrics.get('HIC15', None)
            impact['VDV_Z'] = metrics.get('VDV_Z', None)
            impact['ACC_H_PEAK'] = metrics.get('ACC_H_PEAK', None)
            profile['impact'] = impact
            
            # ---- Dimension 5: Temporal ----
            temporal = {'segments': []}
            seg_dur = 10.0
            seg_samples = int(seg_dur * sr)
            if seg_samples > 0 and n >= seg_samples:
                for start in range(0, n, seg_samples):
                    end = min(start + seg_samples, n)
                    seg = a_res[start:end]
                    if len(seg) < 20:
                        continue
                    seg_rms = float(np.sqrt(np.mean(seg**2)))
                    seg_peak = float(np.max(np.abs(seg)))
                    seg_cf = round(seg_peak / max(seg_rms, 1e-6), 1)
                    temporal['segments'].append({
                        't_start': round(t[start], 2),
                        't_end': round(t[end - 1], 2),
                        'rms_g': round(seg_rms, 3),
                        'peak_g': round(seg_peak, 3),
                        'crest_factor': seg_cf,
                        'n_samples': end - start,
                    })
            if temporal['segments']:
                temporal['max_rms_seg'] = max(temporal['segments'], key=lambda s: s['rms_g'])
                temporal['max_cf_seg'] = max(temporal['segments'], key=lambda s: s['crest_factor'])
            profile['temporal'] = temporal
            
            # ---- Dimension 6: ISO Reference ----
            iso_ref = {}
            ovtv = magnitude['OVTV']
            if ovtv < 0.315:
                zone = 'not_uncomfortable'
                zone_cn = '无不舒适感'
            elif ovtv < 0.63:
                zone = 'a_little_uncomfortable'
                zone_cn = '稍有不舒适感'
            elif ovtv < 1.0:
                zone = 'fairly_uncomfortable'
                zone_cn = '比较不舒适'
            elif ovtv < 1.6:
                zone = 'uncomfortable'
                zone_cn = '不舒适'
            else:
                zone = 'very_uncomfortable'
                zone_cn = '非常不舒适'
            iso_ref['comfort_zone'] = zone
            iso_ref['comfort_zone_cn'] = zone_cn
            iso_ref['OVTV'] = round(ovtv, 3)
            iso_ref['VDV_Z'] = impact.get('VDV_Z')
            iso_ref['aw_z'] = round(aw_z, 3)
            profile['iso_ref'] = iso_ref
            
            return profile
            
        except ImportError:
            return {'error': 'scipy_not_available'}
        except Exception as e:
            logger.error(f"构建振动剖面失败: {e}")
            return {'error': str(e)}

    def _build_contrast_profile(self, exp_profile: Dict, ctrl_profile: Dict,
                                location_id: str) -> Dict[str, Any]:
        """
        构建两组对照剖面差量（v3.0）

        Args:
            exp_profile: 实验组剖面（-1组）
            ctrl_profile: 对照组剖面（-2组）
            location_id: 位置ID

        Returns:
            对照剖面字典，含各维度差量
        """
        contrast = {'location_id': location_id}

        def _safe_delta(e_val, c_val, default=0.0):
            if isinstance(e_val, (int, float)) and isinstance(c_val, (int, float)):
                denominator = max(abs(e_val), abs(c_val), 1e-6)
                delta = (e_val - c_val) / denominator * 100
                return {
                    'exp': round(e_val, 4),
                    'ctrl': round(c_val, 4),
                    'delta_pct': round(delta, 1),
                    'abs_diff': round(e_val - c_val, 4),
                }
            return {'exp': e_val, 'ctrl': c_val, 'delta_pct': 0.0, 'abs_diff': 0.0}

        mag_e = (exp_profile or {}).get('magnitude', {})
        mag_c = (ctrl_profile or {}).get('magnitude', {})
        mag_contrast = {}
        for key in ['OVTV', 'AW_Z', 'AW_XY']:
            if key in mag_e or key in mag_c:
                mag_contrast[key] = _safe_delta(mag_e.get(key), mag_c.get(key))
        for axis in ['X', 'Y', 'Z']:
            e_rms = (mag_e.get(axis, {}) or {}).get('rms')
            c_rms = (mag_c.get(axis, {}) or {}).get('rms')
            if e_rms is not None or c_rms is not None:
                mag_contrast[f'{axis}_rms'] = _safe_delta(e_rms, c_rms)
        contrast['magnitude'] = mag_contrast

        freq_e = (exp_profile or {}).get('frequency', {})
        freq_c = (ctrl_profile or {}).get('frequency', {})
        band_contrast = {}
        e_bands = (freq_e or {}).get('band_energy_pct', {}) or {}
        c_bands = (freq_c or {}).get('band_energy_pct', {}) or {}
        for band in sorted(set(list(e_bands.keys()) + list(c_bands.keys()))):
            e_val = e_bands.get(band, 0.0)
            c_val = c_bands.get(band, 0.0)
            band_contrast[band] = {
                'exp_pct': round(e_val, 1),
                'ctrl_pct': round(c_val, 1),
                'shift': round(e_val - c_val, 1),
            }
        contrast['frequency_bands'] = band_contrast

        imp_e = (exp_profile or {}).get('impact', {})
        imp_c = (ctrl_profile or {}).get('impact', {})
        imp_contrast = {}
        for key in ['crest_Z', 'jerk_total_mean', 'VDV_Z']:
            if key in imp_e or key in imp_c:
                imp_contrast[key] = _safe_delta(imp_e.get(key), imp_c.get(key))
        contrast['impact'] = imp_contrast

        trans_e = (exp_profile or {}).get('transmission', {})
        trans_c = (ctrl_profile or {}).get('transmission', {})
        trans_contrast = {}
        for key in ['SEAT_Z', 'SEAT_XY', 'Z_trans_base']:
            if key in trans_e or key in trans_c:
                trans_contrast[key] = _safe_delta(trans_e.get(key), trans_c.get(key))
        contrast['transmission'] = trans_contrast

        cond_e = (exp_profile or {}).get('condition', {})
        cond_c = (ctrl_profile or {}).get('condition', {})
        cond_contrast = {}
        for key in ['speed_mean', 'speed_std', 'turning_ratio_pct']:
            if key in cond_e or key in cond_c:
                cond_contrast[key] = _safe_delta(cond_e.get(key), cond_c.get(key))
        contrast['condition'] = cond_contrast

        iso_e = (exp_profile or {}).get('iso_ref', {})
        iso_c = (ctrl_profile or {}).get('iso_ref', {})
        contrast['iso_contrast'] = {
            'exp_zone': iso_e.get('comfort_zone_cn', '-'),
            'ctrl_zone': iso_c.get('comfort_zone_cn', '-'),
            'OVTV': _safe_delta(iso_e.get('OVTV'), iso_c.get('OVTV')),
        }

        ovtv_delta = (mag_contrast.get('OVTV', {}) or {}).get('delta_pct', 0)
        if abs(ovtv_delta) > 40:
            note = '两组振动总量差异显著'
        elif abs(ovtv_delta) > 15:
            note = '两组振动总量有中等差异'
        else:
            note = '两组振动总量接近'
        contrast['summary_note'] = note

        return contrast

    # ========================================================================
    # 全时域滑动窗口评测 + 统计检验 + 频段衰减 + 综合指标
    # 参照 OccupantMotionEvaluator v2.0 专家评测方案
    # ========================================================================

    def evaluate_full_timeseries(self,
                                 exp_data: Dict[str, Any],
                                 ctrl_data: Dict[str, Any],
                                 window_sec: float = 1.0,
                                 step_sec: float = 0.5,
                                 sample_rate: float = None,
                                 progress_callback=None) -> Dict[str, Any]:
        """
        全时域滑动窗口评测（参照专家方案的 window_analysis + event_analysis + spectrum + statistics）

        Args:
            exp_data: 实验组数据 {'ax': [...], 'ay': [...], 'az': [...], 'timestamps': [...], ...}
            ctrl_data: 对照组数据 (同上结构)
            window_sec: 滑动窗口宽度(秒)
            step_sec: 窗口步长(秒)
            sample_rate: 采样率，None则自动检测
            progress_callback: 进度回调 callable(percent, message)

        Returns:
            综合评测结果字典:
            - window_results: list[dict] 逐窗口指标
            - statistics: dict 统计检验结果
            - spectrum: dict 频谱/衰减率
            - comprehensive_metrics: dict 综合指标
            - summary: dict 评测摘要
        """
        try:
            sr = sample_rate or self._detect_sample_rate(exp_data)
            if sr is None:
                return {'error': 'cannot_detect_sample_rate'}

            ax_exp = np.asarray(exp_data.get('ax', []), dtype=np.float64)
            ay_exp = np.asarray(exp_data.get('ay', []), dtype=np.float64)
            az_exp = np.asarray(exp_data.get('az', []), dtype=np.float64)
            ax_ctrl = np.asarray(ctrl_data.get('ax', []), dtype=np.float64)
            ay_ctrl = np.asarray(ctrl_data.get('ay', []), dtype=np.float64)
            az_ctrl = np.asarray(ctrl_data.get('az', []), dtype=np.float64)

            n = min(len(ax_exp), len(ax_ctrl))
            if n < 20:
                return {'error': 'insufficient_data'}

            # 截断到相同长度
            ax_exp, ay_exp, az_exp = ax_exp[:n], ay_exp[:n], az_exp[:n]
            ax_ctrl, ay_ctrl, az_ctrl = ax_ctrl[:n], ay_ctrl[:n], az_ctrl[:n]

            # ---- Step 1: 滑动窗口分析 ----
            if progress_callback:
                progress_callback(10, '滑动窗口分析中...')
            window_results = self._sliding_window_analysis(
                ax_exp, ay_exp, az_exp, ax_ctrl, ay_ctrl, az_ctrl,
                sr, window_sec, step_sec
            )

            # ---- Step 2: 统计检验 ----
            if progress_callback:
                progress_callback(40, '统计检验中...')
            statistics = self._statistical_tests(
                ax_exp, ay_exp, az_exp, ax_ctrl, ay_ctrl, az_ctrl, sr
            )

            # ---- Step 3: 频谱与频段衰减 ----
            if progress_callback:
                progress_callback(60, '频谱与频段衰减分析中...')
            spectrum = self._band_attenuation_analysis(
                ax_exp, ay_exp, az_exp, ax_ctrl, ay_ctrl, az_ctrl, sr
            )

            # ---- Step 4: 综合评价指标 ----
            if progress_callback:
                progress_callback(80, '综合评价指标计算中...')
            comp_exp = self._compute_comprehensive_metrics(ax_exp, ay_exp, az_exp, sr)
            comp_ctrl = self._compute_comprehensive_metrics(ax_ctrl, ay_ctrl, az_ctrl, sr)

            comprehensive = {
                'experimental': comp_exp,
                'control': comp_ctrl,
                'attenuation': {
                    'VDV_total_pct': round(
                        (1.0 - comp_exp['VDV_total'] / max(comp_ctrl.get('VDV_total', 1e-6), 1e-6)) * 100, 1
                    ),
                    'RMS_res_pct': round(
                        (1.0 - comp_exp['RMS_res'] / max(comp_ctrl.get('RMS_res', 1e-6), 1e-6)) * 100, 1
                    ),
                    'Peak_res_pct': round(
                        (1.0 - comp_exp['Peak_res'] / max(comp_ctrl.get('Peak_res', 1e-6), 1e-6)) * 100, 1
                    ),
                }
            }

            # ---- Step 5: 摘要 ----
            summary = self._build_evaluation_summary(
                window_results, statistics, spectrum, comprehensive
            )

            if progress_callback:
                progress_callback(100, '评测完成')

            return {
                'window_results': window_results,
                'statistics': statistics,
                'spectrum': spectrum,
                'comprehensive_metrics': comprehensive,
                'summary': summary,
            }

        except Exception as e:
            logger.error(f"全时域评测失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _detect_sample_rate(self, data: Dict) -> Optional[float]:
        """从时间戳或采样率字段检测采样率"""
        sr = data.get('sample_rate')
        if sr:
            return float(sr)
        ts = data.get('timestamps', [])
        if len(ts) >= 10:
            intervals = np.diff(ts[:100])
            return float(1.0 / np.mean(intervals))
        return None

    def _sliding_window_analysis(self, ax_exp, ay_exp, az_exp,
                                  ax_ctrl, ay_ctrl, az_ctrl,
                                  sr: float, window_sec: float, step_sec: float) -> List[Dict]:
        """全时域滑动窗口逐窗分析"""
        from scipy import signal as scipy_signal

        n = len(ax_exp)
        win_samples = int(window_sec * sr)
        step_samples = int(step_sec * sr)
        if win_samples < 10 or step_samples < 1:
            return []

        results = []
        dt = 1.0 / sr
        t_total = n * dt
        a_res_exp = np.sqrt(ax_exp**2 + ay_exp**2 + az_exp**2)
        a_res_ctrl = np.sqrt(ax_ctrl**2 + ay_ctrl**2 + az_ctrl**2)

        for start in range(0, n - win_samples + 1, step_samples):
            end = start + win_samples
            t_center = (start + win_samples / 2) * dt

            # Exp 窗口指标
            e_ax, e_ay, e_az = ax_exp[start:end], ay_exp[start:end], az_exp[start:end]
            e_res = a_res_exp[start:end]
            c_ax, c_ay, c_az = ax_ctrl[start:end], ay_ctrl[start:end], az_ctrl[start:end]
            c_res = a_res_ctrl[start:end]

            row = {
                't_start': round(start * dt, 3),
                't_end': round(end * dt, 3),
                't_center': round(t_center, 3),
                'n_samples': win_samples,
            }

            # 三轴 RMS
            for lbl, e_arr, c_arr in [('X', e_ax, c_ax), ('Y', e_ay, c_ay), ('Z', e_az, c_az)]:
                rms_e = float(np.sqrt(np.mean(e_arr**2)))
                rms_c = float(np.sqrt(np.mean(c_arr**2)))
                row[f'A{lbl}_rms_exp'] = round(rms_e, 4)
                row[f'A{lbl}_rms_ctrl'] = round(rms_c, 4)
                row[f'A{lbl}_attenuation_pct'] = round(
                    (1.0 - rms_e / max(rms_c, 1e-6)) * 100, 1
                )

            # 合成 RMS 与衰减
            rms_res_e = float(np.sqrt(np.mean(e_res**2)))
            rms_res_c = float(np.sqrt(np.mean(c_res**2)))
            row['RMS_res_exp'] = round(rms_res_e, 4)
            row['RMS_res_ctrl'] = round(rms_res_c, 4)
            row['RMS_attenuation_pct'] = round(
                (1.0 - rms_res_e / max(rms_res_c, 1e-6)) * 100, 1
            )

            # 合成 Peak 与衰减
            peak_e = float(np.max(np.abs(e_res)))
            peak_c = float(np.max(np.abs(c_res)))
            row['Peak_exp'] = round(peak_e, 4)
            row['Peak_ctrl'] = round(peak_c, 4)
            row['Peak_attenuation_pct'] = round(
                (1.0 - peak_e / max(peak_c, 1e-6)) * 100, 1
            )

            # Crest Factor (波峰因数)
            for lbl, e_arr, c_arr in [('X', e_ax, c_ax), ('Y', e_ay, c_ay), ('Z', e_az, c_az)]:
                cf_e = round(float(np.max(np.abs(e_arr)) / max(np.sqrt(np.mean(e_arr**2)), 1e-6)), 1)
                cf_c = round(float(np.max(np.abs(c_arr)) / max(np.sqrt(np.mean(c_arr**2)), 1e-6)), 1)
                row[f'Crest_{lbl}_exp'] = cf_e
                row[f'Crest_{lbl}_ctrl'] = cf_c

            # 传递率 (RMS ratio as proxy SEAT)
            row['TR_estimate'] = round(rms_res_e / max(rms_res_c, 1e-6), 3)

            results.append(row)

        return results

    def _statistical_tests(self, ax_exp, ay_exp, az_exp,
                           ax_ctrl, ay_ctrl, az_ctrl, sr: float) -> Dict[str, Any]:
        """统计检验：配对t检验 + Cohen's d + 95%CI（参照专家方案）"""
        stats = {}
        dt = 1.0 / sr

        for lbl, e_arr, c_arr in [('X', ax_exp, ax_ctrl), ('Y', ay_exp, ay_ctrl), ('Z', az_exp, az_ctrl)]:
            # 降采样到 ~10Hz 避免膨胀（参照专家方案第964行）
            ds_factor = max(1, int(sr / 10))
            e_ds = e_arr[::ds_factor]
            c_ds = c_arr[::ds_factor]

            try:
                from scipy import stats as scipy_stats
                t_stat, p_val = scipy_stats.ttest_rel(e_ds, c_ds)

                # Cohen's d
                diff = e_ds - c_ds
                d = float(np.mean(diff) / max(np.std(diff), 1e-6))

                # 95% CI of mean difference
                n_ds = len(diff)
                se = np.std(diff) / np.sqrt(n_ds)
                ci_lo = float(np.mean(diff) - 1.96 * se)
                ci_hi = float(np.mean(diff) + 1.96 * se)

                # 显著性标记
                if p_val < 0.001:
                    sig = '***'
                elif p_val < 0.01:
                    sig = '**'
                elif p_val < 0.05:
                    sig = '*'
                else:
                    sig = 'ns'

                stats[lbl] = {
                    't_statistic': round(float(t_stat), 3),
                    'p_value': round(float(p_val), 6),
                    'cohens_d': round(d, 3),
                    'ci_95_low': round(ci_lo, 6),
                    'ci_95_high': round(ci_hi, 6),
                    'significance': sig,
                    'mean_exp': round(float(np.mean(e_ds)), 4),
                    'mean_ctrl': round(float(np.mean(c_ds)), 4),
                    'mean_diff': round(float(np.mean(diff)), 6),
                }
            except Exception as e:
                logger.warning(f"统计检验 {lbl} 轴失败: {e}")
                stats[lbl] = {'error': str(e)}

        # 合成向量统计
        a_res_exp = np.sqrt(ax_exp**2 + ay_exp**2 + az_exp**2)
        a_res_ctrl = np.sqrt(ax_ctrl**2 + ay_ctrl**2 + az_ctrl**2)
        ds_factor = max(1, int(sr / 10))
        e_res_ds = a_res_exp[::ds_factor]
        c_res_ds = a_res_ctrl[::ds_factor]
        try:
            from scipy import stats as scipy_stats
            t_res, p_res = scipy_stats.ttest_rel(e_res_ds, c_res_ds)
            diff_res = e_res_ds - c_res_ds
            d_res = float(np.mean(diff_res) / max(np.std(diff_res), 1e-6))
            stats['res'] = {
                't_statistic': round(float(t_res), 3),
                'p_value': round(float(p_res), 6),
                'cohens_d': round(d_res, 3),
                'significance': '***' if p_res < 0.001 else ('**' if p_res < 0.01 else ('*' if p_res < 0.05 else 'ns')),
            }
        except Exception:
            stats['res'] = {'error': 'calc_failed'}

        return stats

    def _band_attenuation_analysis(self, ax_exp, ay_exp, az_exp,
                                    ax_ctrl, ay_ctrl, az_ctrl, sr: float) -> Dict[str, Any]:
        """频段衰减分析（Welch PSD + 5频段衰减率 + Coherence）"""
        from scipy import signal as scipy_signal

        a_res_exp = np.sqrt(ax_exp**2 + ay_exp**2 + az_exp**2)
        a_res_ctrl = np.sqrt(ax_ctrl**2 + ay_ctrl**2 + az_ctrl**2)

        n = len(a_res_exp)
        nperseg = min(1024, n // 2, 256)

        # Welch PSD
        f_e, psd_e = scipy_signal.welch(a_res_exp, fs=sr, nperseg=nperseg)
        f_c, psd_c = scipy_signal.welch(a_res_ctrl, fs=sr, nperseg=nperseg)

        # Coherence
        try:
            from scipy import signal as scipy_signal
            f_coh, cxy = scipy_signal.coherence(
                a_res_exp[:n], a_res_ctrl[:n], fs=sr, nperseg=nperseg
            )
            mean_coh = float(np.mean(cxy))
        except Exception:
            f_coh, cxy = np.array([]), np.array([])
            mean_coh = 0.0

        # 5个标准频段（参照专家方案）
        bands = {
            '0.1-0.5Hz': (0.1, 0.5),
            '0.5-1Hz':   (0.5, 1.0),
            '1-5Hz':     (1.0, 5.0),
            '5-20Hz':    (5.0, 20.0),
            '20-80Hz':   (20.0, 80.0),
        }

        band_results = {}
        for band_name, (lo, hi) in bands.items():
            mask_e = (f_e >= lo) & (f_e < hi)
            mask_c = (f_c >= lo) & (f_c < hi)
            e_energy = float(np.trapz(psd_e[mask_e], f_e[mask_e])) if np.any(mask_e) else 0.0
            c_energy = float(np.trapz(psd_c[mask_c], f_c[mask_c])) if np.any(mask_c) else 0.0
            attenuation = round((1.0 - e_energy / max(c_energy, 1e-12)) * 100, 1)
            band_results[band_name] = {
                'exp_energy': round(e_energy, 6),
                'ctrl_energy': round(c_energy, 6),
                'attenuation_pct': attenuation,
            }

        # 全频段总能量
        total_e = float(np.trapz(psd_e, f_e))
        total_c = float(np.trapz(psd_c, f_c))
        total_att = round((1.0 - total_e / max(total_c, 1e-12)) * 100, 1)

        return {
            'bands': band_results,
            'total_attenuation_pct': total_att,
            'mean_coherence': round(mean_coh, 3),
            'psd_exp': {
                'freq': f_e.tolist()[:50],
                'psd': psd_e.tolist()[:50],
            },
            'psd_ctrl': {
                'freq': f_c.tolist()[:50],
                'psd': psd_c.tolist()[:50],
            },
        }

    def _compute_comprehensive_metrics(self, ax, ay, az, sr: float) -> Dict[str, float]:
        """综合指标集：VDV / Crest Factor / Skewness / Kurtosis / MAV / Impulse Factor"""
        dt = 1.0 / sr
        a_res = np.sqrt(ax**2 + ay**2 + az**2)
        n = len(ax)

        results = {}

        # VDV (振动剂量值) — per axis + total
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az), ('total', a_res)]:
            vdv = np.power(np.sum(arr**4) * dt, 0.25)
            results[f'VDV_{lbl}'] = round(float(vdv), 4)

        # RMS per axis + resultant
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            results[f'RMS_{lbl}'] = round(float(np.sqrt(np.mean(arr**2))), 4)
        results['RMS_res'] = round(float(np.sqrt(np.mean(a_res**2))), 4)

        # Peak per axis + resultant
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            results[f'Peak_{lbl}'] = round(float(np.max(np.abs(arr))), 4)
        results['Peak_res'] = round(float(np.max(np.abs(a_res))), 4)

        # Crest Factor (波峰因数 = Peak / RMS)
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            rms = float(np.sqrt(np.mean(arr**2)))
            peak = float(np.max(np.abs(arr)))
            results[f'Crest_{lbl}'] = round(peak / max(rms, 1e-6), 1)

        # Skewness (歪度)
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            mean_val = np.mean(arr)
            std_val = np.std(arr)
            if std_val > 1e-10:
                from scipy import stats as scipy_stats
                sk = float(scipy_stats.skew(arr))
            else:
                sk = 0.0
            results[f'Skew_{lbl}'] = round(sk, 3)

        # Kurtosis (峰度)
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            mean_val = np.mean(arr)
            std_val = np.std(arr)
            if std_val > 1e-10:
                from scipy import stats as scipy_stats
                kt = float(scipy_stats.kurtosis(arr, fisher=True))
            else:
                kt = 0.0
            results[f'Kurt_{lbl}'] = round(kt, 3)

        # MAV (Mean Absolute Value, 平均整流值)
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            results[f'MAV_{lbl}'] = round(float(np.mean(np.abs(arr))), 4)

        # Impulse Factor (冲击因子 = Peak / MAV)
        for lbl, arr in [('X', ax), ('Y', ay), ('Z', az)]:
            mav = float(np.mean(np.abs(arr)))
            peak = float(np.max(np.abs(arr)))
            results[f'Impulse_{lbl}'] = round(peak / max(mav, 1e-6), 1)

        return results

    def _build_evaluation_summary(self, window_results: List[Dict],
                                   statistics: Dict, spectrum: Dict,
                                   comprehensive: Dict) -> Dict[str, Any]:
        """构建评测摘要"""
        if not window_results:
            return {'status': 'no_results'}

        # 窗口统计
        att_vals = [w.get('RMS_attenuation_pct', 0) for w in window_results]
        mean_att = float(np.mean(att_vals))
        best_idx = int(np.argmax(att_vals))
        worst_idx = int(np.argmin(att_vals))

        # 显著性判断
        sig_axes = []
        for axis in ['X', 'Y', 'Z', 'res']:
            st = statistics.get(axis, {})
            p = st.get('p_value', 1.0)
            if p < 0.05:
                sig_axes.append(f"{axis}(p={p:.4f})")

        # 频段衰减概览
        band_atts = spectrum.get('bands', {})
        max_att_band = max(band_atts.items(), key=lambda x: x[1].get('attenuation_pct', -999)) if band_atts else ('N/A', {})

        return {
            'num_windows': len(window_results),
            'mean_attenuation_pct': round(mean_att, 1),
            'best_window': {
                't_start': window_results[best_idx]['t_start'],
                'attenuation_pct': round(att_vals[best_idx], 1),
            },
            'worst_window': {
                't_start': window_results[worst_idx]['t_start'],
                'attenuation_pct': round(att_vals[worst_idx], 1),
            },
            'significant_axes': sig_axes if sig_axes else ['无统计学显著差异'],
            'mean_coherence': spectrum.get('mean_coherence', 0),
            'total_band_attenuation_pct': spectrum.get('total_attenuation_pct', 0),
            'max_attenuation_band': max_att_band[0],
            'max_attenuation_band_pct': max_att_band[1].get('attenuation_pct', 0) if isinstance(max_att_band[1], dict) else 0,
            'VDV_attenuation_pct': comprehensive.get('attenuation', {}).get('VDV_total_pct', 0),
            'RMS_attenuation_pct': comprehensive.get('attenuation', {}).get('RMS_res_pct', 0),
        }

    # ----- 评测报告导出（参照专家方案格式） -----

    def export_full_evaluation_report(self, result: Dict[str, Any],
                                       output_dir: str,
                                       prefix: str = 'seat_evaluation') -> Dict[str, str]:
        """
        导出全量评测报告（Markdown + CSV）

        Returns:
            {file_type: file_path} 字典
        """
        import os
        from datetime import datetime

        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        exported = {}

        # 1. Comprehensive Metrics CSV
        csv_path = os.path.join(output_dir, f'{prefix}_comprehensive_metrics_{ts}.csv')
        self._export_metrics_csv(result, csv_path)
        exported['comprehensive_csv'] = csv_path

        # 2. Window Analysis CSV
        win_csv = os.path.join(output_dir, f'{prefix}_window_analysis_{ts}.csv')
        self._export_window_csv(result, win_csv)
        exported['window_csv'] = win_csv

        # 3. Statistics CSV
        stats_csv = os.path.join(output_dir, f'{prefix}_statistics_{ts}.csv')
        self._export_statistics_csv(result, stats_csv)
        exported['statistics_csv'] = stats_csv

        # 4. Markdown Report
        md_path = os.path.join(output_dir, f'{prefix}_report_{ts}.md')
        self._export_markdown_report(result, md_path)
        exported['markdown_report'] = md_path

        return exported

    def _export_metrics_csv(self, result: Dict, path: str):
        """导出综合指标 CSV"""
        comp = result.get('comprehensive_metrics', {})
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            import csv
            w = csv.writer(f)
            w.writerow(['Group', 'Metric', 'Axis', 'Value'])
            for group in ['experimental', 'control']:
                metrics = comp.get(group, {})
                for key, val in sorted(metrics.items()):
                    # 解析 axis (VDV_X, RMS_Y, etc.)
                    parts = key.rsplit('_', 1)
                    metric_name = parts[0]
                    axis = parts[1] if len(parts) > 1 else 'total'
                    w.writerow([group, metric_name, axis, val])
            att = comp.get('attenuation', {})
            for key, val in att.items():
                w.writerow(['attenuation', key.replace('_pct', ''), '-', val])

    def _export_window_csv(self, result: Dict, path: str):
        """导出窗口分析 CSV"""
        windows = result.get('window_results', [])
        if not windows:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            import csv
            w = csv.DictWriter(f, fieldnames=list(windows[0].keys()))
            w.writeheader()
            w.writerows(windows)

    def _export_statistics_csv(self, result: Dict, path: str):
        """导出统计检验 CSV"""
        stats = result.get('statistics', {})
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            import csv
            w = csv.writer(f)
            w.writerow(['Axis', 't_statistic', 'p_value', 'cohens_d', 'ci_95_low', 'ci_95_high', 'significance'])
            for axis in ['X', 'Y', 'Z', 'res']:
                st = stats.get(axis, {})
                if st:
                    w.writerow([
                        axis,
                        st.get('t_statistic', ''),
                        st.get('p_value', ''),
                        st.get('cohens_d', ''),
                        st.get('ci_95_low', ''),
                        st.get('ci_95_high', ''),
                        st.get('significance', ''),
                    ])

    def _export_markdown_report(self, result: Dict, path: str):
        """导出 Markdown 评测报告"""
        summary = result.get('summary', {})
        stats = result.get('statistics', {})
        comp = result.get('comprehensive_metrics', {})
        spectrum = result.get('spectrum', {})

        lines = [
            '# 座椅振动全量评测报告',
            '',
            '## 评测摘要',
            f'- 评测窗口数: {summary.get("num_windows", 0)}',
            f'- 平均 RMS 衰减率: {summary.get("mean_attenuation_pct", "N/A")}%',
            f'- 最佳窗口衰减率: {summary.get("best_window", {}).get("attenuation_pct", "N/A")}% (t={summary.get("best_window", {}).get("t_start", "N/A")})',
            f'- 最差窗口衰减率: {summary.get("worst_window", {}).get("attenuation_pct", "N/A")}% (t={summary.get("worst_window", {}).get("t_start", "N/A")})',
            f'- 显著差异轴: {", ".join(summary.get("significant_axes", ["N/A"]))}',
            f'- 平均相干性: {summary.get("mean_coherence", "N/A")}',
            '',
            '## 统计检验',
            '',
            '| Axis | t | p | Cohen\'s d | 95% CI | Sig |',
            '|------|---|---|-----------|-------|-----|',
        ]
        for axis in ['X', 'Y', 'Z', 'res']:
            st = stats.get(axis, {})
            if st:
                lines.append(
                    f'| {axis} | {st.get("t_statistic","-")} | {st.get("p_value","-")} | '
                    f'{st.get("cohens_d","-")} | [{st.get("ci_95_low","-")}, {st.get("ci_95_high","-")}] | '
                    f'{st.get("significance","-")} |'
                )

        lines.extend([
            '',
            '## 频段衰减',
            '',
            '| Band | Exp Energy | Ctrl Energy | Attenuation % |',
            '|------|-----------|-------------|--------------|',
        ])
        bands = spectrum.get('bands', {})
        for band_name, band_data in bands.items():
            lines.append(
                f'| {band_name} | {band_data.get("exp_energy","-")} | '
                f'{band_data.get("ctrl_energy","-")} | {band_data.get("attenuation_pct","-")}% |'
            )

        lines.extend([
            '',
            f'## 综合评价指标（对照组衰减率）',
            '',
            f'- VDV 总衰减率: {comp.get("attenuation", {}).get("VDV_total_pct", "N/A")}%',
            f'- RMS 合成衰减率: {comp.get("attenuation", {}).get("RMS_res_pct", "N/A")}%',
            f'- Peak 合成衰减率: {comp.get("attenuation", {}).get("Peak_res_pct", "N/A")}%',
        ])

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def _result_to_dict(self, result: EvaluationResult) -> Dict[str, Any]:
        """
        将结果对象转换为字典
        
        Args:
            result: 评测结果对象
        
        Returns:
            结果字典
        """
        location_results_dict = {}
        for loc_id, loc_result in result.location_results.items():
            location_results_dict[loc_id] = {
                'location_id': loc_result.location_id,
                'location_name': loc_result.location_name,
                'channel_id': loc_result.channel_id,
                'metrics': loc_result.metrics,
                'location_score': loc_result.location_score,
                'risk_level': loc_result.risk_level.value,
                'profile': loc_result.profile,
                'metadata': loc_result.metadata
            }
        
        return {
            'trigger_id': result.trigger_id,
            'event_type': result.event_type,
            'timestamp': result.timestamp,
            'metrics': result.metrics,
            'overall_score': result.overall_score,
            'risk_level': result.risk_level.value,
            'profile': result.profile,
            'location_results': location_results_dict,
            'metadata': result.metadata
        }
