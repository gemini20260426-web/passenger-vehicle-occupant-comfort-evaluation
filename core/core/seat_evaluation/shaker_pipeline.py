#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
振动台架实验分析管线 (ISO 10326-1 / ISO 2631-1)

端到端流程: 数据加载 → 预处理 → 频率加权 → 指标计算 → 结果组装
"""

import numpy as np
from typing import Dict, List, Optional
import logging
import time

from .shaker_models import (
    ShakerData, ProcessedShakerData, AnalysisResult,
    TimeDomainMetrics, SEATMetrics, TransferResult, PSDResult,
    DataQuality
)
from .shaker_data_loader import ShakerDataLoader
from .shaker_preprocessor import ShakerPreprocessor
from .frequency_weighting import (
    ISO2631WeightingFilter, get_filter,
    compute_weighted_rms, compute_vdv, compute_crest_factor, compute_mtvv
)
from .operators import (
    SEATOperator, CrestFactorOperator, TransferFunctionOperator,
    PSDNormalizedOperator, VDVOperator, MTVVOperator
)

logger = logging.getLogger(__name__)


class ShakerAnalysisPipeline:
    """
    台架实验完整分析管线。

    使用方法:
        pipeline = ShakerAnalysisPipeline()
        result = pipeline.analyze_single('一汽红旗1_Waveform.XLS')
        print(f"SEAT R_z/Wk: {result.seat.seat_values['r_z']:.1f}%")

    或批量:
        results = pipeline.analyze_batch('/path/to/ACC-*/')
        for r in results:
            print(f"{r.condition_name}: SEAT R_z = {r.seat.seat_values['r_z']:.1f}%")
    """

    def __init__(self, fs: float = 1000.0):
        self.fs = fs
        self.loader = ShakerDataLoader()
        self.preprocessor = ShakerPreprocessor()
        self.filter = get_filter(fs)

        # 算子系统
        self.seat_op = SEATOperator(fs)
        self.cf_op = CrestFactorOperator()
        self.transfer_op = TransferFunctionOperator(fs)
        self.psd_op = PSDNormalizedOperator(fs)
        self.vdv_op = VDVOperator()
        self.mtvv_op = MTVVOperator()

        # 进度回调
        self._progress_callback = None
        self._cancel_requested = False

    # ══════════════════════════════════════════════════
    # 公开接口
    # ══════════════════════════════════════════════════

    def analyze_single(self, filepath: str, condition_label: str = '') -> AnalysisResult:
        """分析单个数据文件"""
        self._cancel_requested = False
        t0 = time.time()

        # ── 阶段 1/6: 数据加载 (5%) ──
        self._report_progress(5, '加载数据...')
        data = self.loader.load(filepath, condition_label)

        # ── 阶段 2/6: 预处理 (20%) ──
        self._report_progress(20, '预处理 (去直流+滤波)...')
        processed = self.preprocessor.process(data)
        if self._cancel_requested:
            return None

        # ── 阶段 3/6: 频率加权 (45%) ──
        self._report_progress(45, '频率加权 (Wk/Wd/Wc)...')
        # 加权已在 preprocessor 中完成

        # ── 阶段 4/6: 指标计算 (70%) ──
        self._report_progress(70, '计算 SEAT / RMS / VDV / CF...')
        result = self._compute_all_metrics(data, processed)
        if self._cancel_requested:
            return None

        # ── 阶段 5/6: 图表预渲染 (90%) ──
        self._report_progress(90, '构建图表数据...')

        # ── 阶段 6/6: 完成 ──
        self._report_progress(100, '分析完成')

        elapsed = time.time() - t0
        logger.info(f"{data.condition_label}: 分析完成 ({elapsed:.1f}s)")

        return result

    def analyze_batch(self, directory: str, pattern: str = '*.XLS') -> List[AnalysisResult]:
        """批量分析目录中的所有文件"""
        data_list = self.loader.load_batch(directory, pattern)
        results = []
        n = len(data_list)
        for i, d in enumerate(data_list):
            self._report_progress(
                int(5 + (i / max(1, n)) * 90),
                f'分析工况 {i+1}/{n}: {d.condition_label}'
            )
            result = self.analyze_single(d.filepath, d.condition_label)
            if result:
                results.append(result)
            if self._cancel_requested:
                break
        self._report_progress(100, f'全部分析完成 ({len(results)}/{n})')
        return results

    def analyze_loaded(self, data: ShakerData) -> AnalysisResult:
        """分析已加载的数据"""
        self._cancel_requested = False
        t0 = time.time()

        self._report_progress(20, '预处理...')
        processed = self.preprocessor.process(data)
        if self._cancel_requested:
            return None

        self._report_progress(60, '计算指标...')
        result = self._compute_all_metrics(data, processed)
        if self._cancel_requested:
            return None

        self._report_progress(100, '完成')
        logger.info(f"{data.condition_label}: 分析完成 ({time.time()-t0:.1f}s)")
        return result

    def set_progress_callback(self, callback):
        """设置进度回调函数: callback(progress_pct: int, status_msg: str)"""
        self._progress_callback = callback

    def cancel(self):
        """请求取消分析"""
        self._cancel_requested = True

    # ══════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════

    def _report_progress(self, pct: int, msg: str):
        if self._progress_callback:
            try:
                self._progress_callback(pct, msg)
            except Exception:
                pass

    def _compute_all_metrics(self, data: ShakerData,
                             processed: ProcessedShakerData) -> AnalysisResult:
        """计算所有指标并组装结果"""
        result = AnalysisResult(
            condition_name=data.condition_label,
            filepath=data.filepath,
            fs=data.fs,
            duration=data.duration,
            quality=data.quality,
        )

        # ── 全部 9 通道加权 RMS ──
        rms_results = {}
        vdv_results = {}
        cf_results = {}
        mtvv_results = {}

        channel_rms = {}  # 用于 SEAT 计算
        platform_rms = {}

        for loc_name in ['platform', 'r_point', 't8']:
            loc_weighted = getattr(processed, f'{loc_name}_weighted')
            for ax in ['x', 'y', 'z']:
                channel_key = f"{loc_name}_{ax}"
                wtype = self.filter.get_weighting_for_channel(loc_name, ax)
                signal_w = getattr(loc_weighted[wtype], ax)

                rms_val = compute_weighted_rms(signal_w)
                channel_rms[channel_key] = rms_val
                if loc_name == 'platform':
                    platform_rms[ax] = rms_val

                vdv_val = compute_vdv(signal_w, self.fs)
                cf_val = compute_crest_factor(signal_w)
                mtvv_val = compute_mtvv(signal_w, self.fs)

                rms_results[channel_key] = rms_val
                vdv_results[channel_key] = vdv_val
                cf_results[channel_key] = cf_val
                mtvv_results[channel_key] = mtvv_val

                # 时域指标汇总
                result.time_domain[channel_key] = TimeDomainMetrics(
                    rms=rms_val, vdv=vdv_val,
                    peak=float(np.max(np.abs(signal_w))),
                    crest_factor=cf_val, mtvv=mtvv_val,
                )

        result.weighted_rms = rms_results

        # ── SEAT 因子 ──
        seat_values = {}
        low_exc = []  # 低激励通道列表

        # 低激励检测阈值 (加权RMS < 0.5 m/s²)
        LOW_EXC_THRESHOLD = 0.5

        for loc_prefix in ['r_point', 't8']:
            for ax in ['x', 'y', 'z']:
                seat_key = f"{loc_prefix}_{ax}"
                seat_channel_key = f"{loc_prefix}_{ax}"
                plat_channel_key = f"platform_{ax}"
                plat_rms = channel_rms.get(plat_channel_key, 1.0)
                seat_rms_val = channel_rms.get(seat_channel_key, 0.0)
                seat_pct = self.seat_op.compute(seat_rms_val, plat_rms)
                seat_values[seat_key] = seat_pct

                # 标记低激励通道
                if plat_rms < LOW_EXC_THRESHOLD:
                    low_exc.append(seat_key)

        result.low_excitation_channels = low_exc

        # 计算 overall SEAT 和评级 (排除低激励通道)
        reliable_vals = [v for k, v in seat_values.items()
                        if v < 1e10 and k not in low_exc]
        overall = float(np.mean(reliable_vals)) if reliable_vals else float('inf')

        _, grade_label = self.seat_op.grade(overall)
        resonance_ch = [k for k, v in seat_values.items() if v > 300]

        result.seat = SEATMetrics(
            seat_values=seat_values,
            overall=overall,
            grade=grade_label,
            resonance_channels=resonance_ch,
        )

        # ── 传递函数 (6 个路径: r_x, r_y, r_z, t8_x, t8_y, t8_z vs platform) ──
        for loc_prefix in ['r_point', 't8']:
            for ax in ['x', 'y', 'z']:
                seat_key = f"{loc_prefix}_{ax}"
                wtype_seat = self.filter.get_weighting_for_channel(loc_prefix, ax)

                seat_loc_weighted = getattr(processed, f'{loc_prefix}_weighted')
                plat_loc_weighted = getattr(processed, 'platform_weighted')
                wtype_plat = self.filter.get_weighting_for_channel('platform', ax)

                output_sig = getattr(seat_loc_weighted[wtype_seat], ax)
                input_sig = getattr(plat_loc_weighted[wtype_plat], ax)

                tf_data = self.transfer_op.compute(input_sig, output_sig)

                peaks = self.transfer_op.find_peaks(
                    tf_data['frequencies'], tf_data['magnitude'],
                    tf_data['coherence'], coh_threshold=0.5
                )

                tr = TransferResult(
                    frequencies=tf_data['frequencies'],
                    magnitude=tf_data['magnitude'],
                    coherence=tf_data['coherence'],
                    peak_freqs=[p['frequency'] for p in peaks],
                    peak_gains=[p['gain'] for p in peaks],
                    peak_coherences=[p['coherence'] for p in peaks],
                )
                result.transfer_functions[seat_key] = tr

                # 共振汇总
                main_peak = peaks[0] if peaks else {}
                result.resonance_summary[seat_key] = {
                    'freq': main_peak.get('frequency', 0),
                    'gain': main_peak.get('gain', 0),
                    'coherence': main_peak.get('coherence', 0),
                    'n_peaks': len(peaks),
                    'seat_value': seat_values.get(seat_key, 0),
                }

                self._check_cancel()

        # ── PSD ──
        for loc_name in ['platform', 'r_point', 't8']:
            loc_raw = getattr(processed, f'{loc_name}_raw')
            for ax in ['x', 'y', 'z']:
                key = f"{loc_name}_{ax}"
                psd_data = self.psd_op.compute(getattr(loc_raw, ax))
                result.psd[key] = PSDResult(
                    frequencies=psd_data['frequencies'],
                    psd=psd_data['psd'],
                    resolution=psd_data['resolution'],
                )

        return result

    def _check_cancel(self):
        if self._cancel_requested:
            raise InterruptedError("分析已取消")