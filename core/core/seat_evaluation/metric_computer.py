#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一指标计算器 — 消除 engine.py 与 engine_v2.py 的双重实现

评审报告 AR-5: analysis/ 6层管线 + 独立的 engine.py 重复实现指标
修复: 将所有指标计算逻辑集中到 MetricComputer，两个引擎通过委托调用

支持的指标 (20个):
  频域: SEAT_Z, SEAT_XY, TR_Z, AW_Z, AW_XY, VDV_Z, OVTV, R_FACTOR, DISP_TR, DISP_HR
  冲击: HIC15, ACC_H_PEAK, JERK_H, SRS_MRS, SRS_Q, SRS_PV, SRS_ATT
  疲劳: FDS_D, FDS_R, RFC_CC
  脊柱: S_D
  时频: STFT_FC, STFT_KT, STFT_CE
  基础: ACC_RMS, ACC_PEAK
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass

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


@dataclass
class MetricComputeContext:
    """指标计算上下文"""
    ax: np.ndarray
    ay: np.ndarray
    az: np.ndarray
    sample_rate: float
    floor_az: Optional[np.ndarray] = None
    floor_axy: Optional[np.ndarray] = None
    gx: Optional[np.ndarray] = None
    gy: Optional[np.ndarray] = None
    gz: Optional[np.ndarray] = None


class MetricComputer:
    """统一指标计算器 — 所有指标计算的单一入口

    使用方式:
        computer = MetricComputer(operator_system)
        ctx = MetricComputeContext(ax=..., ay=..., az=..., sample_rate=100.0, floor_az=...)
        value = computer.compute('SEAT_Z', ctx)
    """

    def __init__(self, operator_system):
        self._ops = operator_system
        self._cfc60 = None
        self._cfc600 = None
        self._cfc1000 = None
        self._initialized = False

    def _init_cfc(self):
        if self._initialized:
            return
        from .operators import CFCOperator
        self._cfc60 = CFCOperator(cfc=60)
        self._cfc600 = CFCOperator(cfc=600)
        self._cfc1000 = CFCOperator(cfc=1000)
        self._initialized = True

    # ── SRS/FDS/STFT 子指标映射 ──
    _SRS_SUB_IDS = {'SRS_MRS': 'SRS_MRS', 'SRS_Q': 'SRS_Q', 'SRS_PV': 'SRS_PV', 'SRS_ATT': 'SRS_ATT'}
    _FDS_SUB_IDS = {'FDS_D': 'FDS_D', 'FDS_R': 'FDS_R'}
    _STFT_SUB_IDS = {'STFT_FC': 'STFT_FC', 'STFT_KT': 'STFT_KT', 'STFT_CE': 'STFT_CE'}
    _ALL_SUB_METRICS = {**_SRS_SUB_IDS, **_FDS_SUB_IDS, **_STFT_SUB_IDS}

    def compute(self, metric_id: str, ctx: MetricComputeContext) -> float:
        self._init_cfc()
        ops = self._ops

        n_samples = len(ctx.az) if len(ctx.az) > 0 else len(ctx.ax) if len(ctx.ax) > 0 else len(ctx.ay)
        min_required = MIN_SAMPLES_PER_METRIC.get(metric_id, MIN_WINDOW_SAMPLES)
        if n_samples < min_required:
            return METRIC_INSUFFICIENT_DATA

        sr = ctx.sample_rate
        ax, ay, az = ctx.ax, ctx.ay, ctx.az

        # ── 主路由: _METRIC_HANDLERS ──
        handler = self._METRIC_HANDLERS.get(metric_id)
        if handler:
            return handler(self, ctx, ops, sr, ax, ay, az)

        # ── SRS子指标路由 ──
        if metric_id in self._SRS_SUB_IDS:
            return self.compute_srs(ctx, self._SRS_SUB_IDS[metric_id])

        # ── FDS子指标路由 ──
        if metric_id in self._FDS_SUB_IDS:
            return self.compute_fds(ctx, self._FDS_SUB_IDS[metric_id])

        # ── STFT子指标路由 ──
        if metric_id in self._STFT_SUB_IDS:
            return self.compute_stft(ctx, self._STFT_SUB_IDS[metric_id])

        # ── 未识别指标: 报错而非静默返回0 ──
        logger.error(f"未知指标: {metric_id}")
        raise ValueError(
            f"MetricComputer.compute(): 未知指标 '{metric_id}'。"
            f"有效指标: {list(self._METRIC_HANDLERS.keys()) + list(self._ALL_SUB_METRICS.keys())}"
        )

    def _compute_seat_z(self, ctx, ops, sr, ax, ay, az):
        az_cfc = self._cfc1000.filter(az, sr) if len(az) >= 4 else az
        floor_az = ctx.floor_az
        if floor_az is not None and len(floor_az) > 0:
            floor_az_cfc = self._cfc1000.filter(floor_az, sr) if len(floor_az) >= 4 else floor_az
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
                        logger.warning(f"SEAT_Z coherence={mean_coh:.3f} < 0.5")
                return float(np.sqrt(integral_seat / integral_floor))
        weighted = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
        return float(np.sqrt(np.mean(weighted**2)))

    def _compute_seat_xy(self, ctx, ops, sr, ax, ay, az):
        ax_cfc = self._cfc600.filter(ax, sr) if len(ax) >= 4 else ax
        ay_cfc = self._cfc600.filter(ay, sr) if len(ay) >= 4 else ay
        xy = ops.vector.synthesize_xy(ax_cfc, ay_cfc)
        floor_axy = ctx.floor_axy
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

    def _compute_vdv_z(self, ctx, ops, sr, ax, ay, az):
        az_cfc = self._cfc1000.filter(az, sr) if len(az) >= 4 else az
        az_w = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
        dt = 1.0 / sr
        return float(np.power(np.sum(az_w**4) * dt, 0.25))

    def _compute_tr_z(self, ctx, ops, sr, ax, ay, az):
        az_cfc = self._cfc1000.filter(az, sr) if len(az) >= 4 else az
        floor_az = ctx.floor_az
        if floor_az is not None and len(floor_az) > 0 and len(az_cfc) > 0:
            floor_az_cfc = self._cfc1000.filter(floor_az, sr) if len(floor_az) >= 4 else floor_az
            tf_result = ops.csd.transfer_function_db(
                floor_az_cfc, az_cfc, sr, nperseg=min(1024, len(az_cfc)))
            if tf_result.get('TR_peak_dB', 0.0) != 0.0:
                return float(tf_result['TR_peak_dB'])
        if len(az_cfc) > 0 and len(ctx.floor_az or az_cfc) > 0:
            return float(np.std(az_cfc) / (np.std(ctx.floor_az or az_cfc) + 0.001))
        return 1.0

    def _compute_aw_z(self, ctx, ops, sr, ax, ay, az):
        az_cfc = self._cfc1000.filter(az, sr) if len(az) >= 4 else az
        weighted = ops.weighting.apply_weighting_z_via_freq(az_cfc, sr)
        return float(np.sqrt(np.mean(weighted**2)))

    def _compute_aw_xy(self, ctx, ops, sr, ax, ay, az):
        ax_cfc = self._cfc60.filter(ax, sr) if len(ax) >= 4 else ax
        ay_cfc = self._cfc60.filter(ay, sr) if len(ay) >= 4 else ay
        xy = ops.vector.synthesize_xy(ax_cfc, ay_cfc)
        weighted = ops.weighting.apply_weighting_xy_via_freq(xy, sr)
        return float(np.sqrt(np.mean(weighted**2)))

    def _compute_ovtv(self, ctx, ops, sr, ax, ay, az):
        aw_x = float(np.sqrt(np.mean(ops.weighting.apply_weighting_xy_via_freq(ax, sr)**2))) if len(ax) > 0 else 0.0
        aw_y = float(np.sqrt(np.mean(ops.weighting.apply_weighting_xy_via_freq(ay, sr)**2))) if len(ay) > 0 else 0.0
        aw_z = float(np.sqrt(np.mean(ops.weighting.apply_weighting_z_via_freq(az, sr)**2))) if len(az) > 0 else 0.0
        return float(np.sqrt(1.4**2 * aw_x**2 + 1.4**2 * aw_y**2 + 1.0**2 * aw_z**2))

    def _compute_r_factor(self, ctx, ops, sr, ax, ay, az):
        return float(np.std(ax + ay) / (np.std(az) + 0.001))

    def _compute_hic15(self, ctx, ops, sr, ax, ay, az):
        if len(az) == 0:
            return 0.0
        ax_cfc = self._cfc600.filter(ax, sr) if len(ax) >= 4 else ax
        ay_cfc = self._cfc600.filter(ay, sr) if len(ay) >= 4 else ay
        az_cfc = self._cfc600.filter(az, sr) if len(az) >= 4 else az
        a_mag = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
        dt = 1.0 / sr
        n_15 = max(1, int(0.015 / dt))
        if n_15 < 3:
            target_sr = max(sr, 200.0)
            t_original = np.arange(len(a_mag)) / sr
            t_target = np.arange(0, t_original[-1], 1.0 / target_sr)
            a_mag = np.interp(t_target, t_original, a_mag)
            dt = 1.0 / target_sr
            n_15 = max(1, int(0.015 * target_sr))
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

    def _compute_s_d(self, ctx, ops, sr, ax, ay, az):
        result = ops.iso2631_5.compute(ax * 9.81, ay * 9.81, az * 9.81, sr)
        return result.get('S_d_MPa', 0.0)

    def _compute_acc_h_peak(self, ctx, ops, sr, ax, ay, az):
        ax_cfc = self._cfc600.filter(ax, sr) if len(ax) >= 4 else ax
        ay_cfc = self._cfc600.filter(ay, sr) if len(ay) >= 4 else ay
        az_cfc = self._cfc600.filter(az, sr) if len(az) >= 4 else az
        head_accel = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
        return float(np.max(np.abs(head_accel)))

    def _compute_jerk_h(self, ctx, ops, sr, ax, ay, az):
        ax_cfc = self._cfc600.filter(ax, sr) if len(ax) >= 4 else ax
        ay_cfc = self._cfc600.filter(ay, sr) if len(ay) >= 4 else ay
        az_cfc = self._cfc600.filter(az, sr) if len(az) >= 4 else az
        head_accel = ops.vector.synthesize(ax_cfc, ay_cfc, az_cfc)
        head_accel = ops.cfc.filter(head_accel, sr)
        jerk = np.diff(head_accel) * sr
        return float(np.max(np.abs(jerk))) if len(jerk) > 0 else 0.0

    def _compute_srs(self, ctx, ops, sr, ax, ay, az, sub_id):
        srs_result = ops.srs.compute(az, sr)
        srs_features = ops.srs.extract_features(srs_result)
        return srs_features.get(sub_id, 0.0)

    def _compute_rfc_cc(self, ctx, ops, sr, ax, ay, az):
        rf_result = ops.rainflow.count(az)
        return float(rf_result.get('RFC_CC', 0.0))

    def _compute_fds(self, ctx, ops, sr, ax, ay, az, sub_id):
        rf_result = ops.rainflow.count(az)
        fds_result = ops.fds.compute(rf_result)
        return fds_result.get(sub_id, 0.0)

    def _compute_stft(self, ctx, ops, sr, ax, ay, az, sub_id):
        stft_result = ops.stft.compute(az, sr)
        stft_features = ops.stft.extract_features(stft_result)
        return stft_features.get(sub_id, 0.0)

    def _compute_acc_rms(self, ctx, ops, sr, ax, ay, az):
        total = np.sqrt(ax**2 + ay**2 + az**2)
        return float(np.sqrt(np.mean(total**2)))

    def _compute_acc_peak(self, ctx, ops, sr, ax, ay, az):
        total = np.sqrt(ax**2 + ay**2 + az**2)
        return float(np.max(total))

    def _compute_disp_tr(self, ctx, ops, sr, ax, ay, az):
        if len(az) > 0:
            az_cfc = self._cfc60.filter(az, sr) if len(az) >= 4 else az
            disp = ops.integration.integrate_to_displacement(az_cfc, sr)
            return float(np.max(np.abs(disp)))
        return 0.0

    def _compute_disp_hr(self, ctx, ops, sr, ax, ay, az):
        n_ref = max(len(ax), len(ay), len(az))
        if n_ref < 4:
            return 0.0
        ax_f = self._cfc600.filter(ax, sr) if len(ax) >= 4 else np.zeros(n_ref)
        ay_f = self._cfc600.filter(ay, sr) if len(ay) >= 4 else np.zeros(n_ref)
        az_f = self._cfc600.filter(az, sr) if len(az) >= 4 else np.zeros(n_ref)
        dx = ops.integration.integrate_to_displacement(ax_f, sr) if len(ax) >= 4 else np.zeros(n_ref)
        dy = ops.integration.integrate_to_displacement(ay_f, sr) if len(ay) >= 4 else np.zeros(n_ref)
        dz = ops.integration.integrate_to_displacement(az_f, sr) if len(az) >= 4 else np.zeros(n_ref)
        disp_3d = ops.vector.synthesize(dx, dy, dz)
        return float(np.max(disp_3d))

    _METRIC_HANDLERS: Dict[str, Callable] = {}

    def _register_handlers(self):
        if self._METRIC_HANDLERS:
            return
        self._METRIC_HANDLERS.update({
            'SEAT_Z': MetricComputer._compute_seat_z,
            'SEAT_XY': MetricComputer._compute_seat_xy,
            'VDV_Z': MetricComputer._compute_vdv_z,
            'TR_Z': MetricComputer._compute_tr_z,
            'AW_Z': MetricComputer._compute_aw_z,
            'AW_XY': MetricComputer._compute_aw_xy,
            'OVTV': MetricComputer._compute_ovtv,
            'R_FACTOR': MetricComputer._compute_r_factor,
            'HIC15': MetricComputer._compute_hic15,
            'S_D': MetricComputer._compute_s_d,
            'ACC_H_PEAK': MetricComputer._compute_acc_h_peak,
            'JERK_H': MetricComputer._compute_jerk_h,
            'RFC_CC': MetricComputer._compute_rfc_cc,
            'ACC_RMS': MetricComputer._compute_acc_rms,
            'ACC_PEAK': MetricComputer._compute_acc_peak,
            'DISP_TR': MetricComputer._compute_disp_tr,
            'DISP_HR': MetricComputer._compute_disp_hr,
        })

    def compute_srs(self, ctx, sub_id):
        return self._compute_srs(ctx, self._ops, ctx.sample_rate, ctx.ax, ctx.ay, ctx.az, sub_id)

    def compute_fds(self, ctx, sub_id):
        return self._compute_fds(ctx, self._ops, ctx.sample_rate, ctx.ax, ctx.ay, ctx.az, sub_id)

    def compute_stft(self, ctx, sub_id):
        return self._compute_stft(ctx, self._ops, ctx.sample_rate, ctx.ax, ctx.ay, ctx.az, sub_id)


MetricComputer._register_handlers(MetricComputer)


def verify_all_metrics_registered():
    """验证所有metadata定义的指标均可通过compute()计算
    返回 True 表示所有指标已注册，False 表示存在缺失指标
    """
    from .metadata_registry import INDICATOR_DEFINITIONS
    defined = set(INDICATOR_DEFINITIONS.keys())
    registered = set(MetricComputer._METRIC_HANDLERS.keys()) | set(MetricComputer._ALL_SUB_METRICS.keys())
    missing = defined - registered
    extra = registered - defined
    if missing:
        logger.error(f"MetricComputer 未注册指标: {missing}")
    if extra:
        logger.warning(f"MetricComputer 多余指标(不在metadata中): {extra}")
    if missing:
        return False
    logger.info(f"MetricComputer 指标完整性验证通过: {len(registered)} 个指标已注册")
    return True