#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一指标元数据注册中心 — 指标定义与评测数据

来源: core/core/analysis/core_types.py (lines 387-1201)
包含:
  - INDICATOR_DEFINITIONS : 24个核心指标定义
  - INDICATOR_DETAIL      : 指标计算详情(算子管线/公式/逻辑)
  - DIAGNOSIS_THRESHOLDS  : 诊断阈值
  - DIAGNOSIS_STATE_ICONS : 诊断状态图标
  - STANDARD_REFERENCES   : 标准引用
  - COMPARISON_DIMENSIONS : 评测对比维度
"""

import dataclasses
import enum
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

INDICATOR_DEFINITIONS = {
    # 原有频域指标 (8个)
    'SEAT_Z': {'name': '座椅垂直传递率', 'unit': '', 'type': 'frequency'},
    'SEAT_XY': {'name': '座椅水平传递率', 'unit': '', 'type': 'frequency'},
    'VDV_Z': {'name': '垂直振动剂量值', 'unit': 'm/s^1.75', 'type': 'frequency'},
    'TR_Z': {'name': '垂直传递率(dB)', 'unit': 'dB', 'type': 'frequency'},
    'AW_Z': {'name': '垂直加权加速度', 'unit': 'g', 'type': 'frequency'},
    'AW_XY': {'name': '水平加权加速度', 'unit': 'g', 'type': 'frequency'},
    'OVTV': {'name': '总体振动值', 'unit': 'm/s^1.75', 'type': 'frequency'},
    'R_FACTOR': {'name': 'R因子', 'unit': '', 'type': 'frequency'},

    # 新增瞬态指标 (15个)
    'HIC15': {'name': '头部损伤准则', 'unit': '', 'type': 'shock'},
    'ACC_H_PEAK': {'name': '头部加速度峰值', 'unit': 'g', 'type': 'shock'},
    'JERK_H': {'name': '头部冲击度', 'unit': 'g/s', 'type': 'shock'},
    'SRS_MRS': {'name': '最大响应谱', 'unit': 'g', 'type': 'shock'},
    'SRS_Q': {'name': '品质因数', 'unit': '', 'type': 'shock'},
    'SRS_PV': {'name': '峰值速度', 'unit': 'g·s', 'type': 'shock'},
    'SRS_ATT': {'name': '衰减时间', 'unit': 's', 'type': 'shock'},
    'RFC_CC': {'name': '循环计数', 'unit': '', 'type': 'fatigue'},
    'FDS_D': {'name': '疲劳损伤度', 'unit': '', 'type': 'fatigue'},
    'FDS_R': {'name': '剩余寿命', 'unit': '', 'type': 'fatigue'},
    'STFT_FC': {'name': '频率中心', 'unit': 'Hz', 'type': 'time_frequency'},
    'STFT_KT': {'name': '频率扩展', 'unit': 'Hz', 'type': 'time_frequency'},
    'STFT_CE': {'name': '能量集中度', 'unit': '', 'type': 'time_frequency'},
    'DISP_TR': {'name': '位移轨迹', 'unit': 'mm', 'type': 'structure'},

    'ACC_RMS': {'name': '加速度均方根', 'unit': 'g', 'type': 'basic'},
    'ACC_PEAK': {'name': '峰值加速度', 'unit': 'g', 'type': 'basic'},
    'S_D': {'name': '脊柱压缩应力', 'unit': 'MPa', 'type': 'spine'},
    'DISP_HR': {'name': '头部三维合成位移', 'unit': 'mm', 'type': 'dynamic'},

    # ═══════════════════════════════════════════════════════════
    #  全时域统计指标 (Full Timeseries Statistics) — 87个
    # ═══════════════════════════════════════════════════════════

    # ── 实验组 (E) 全套指标 ──
    'RMS_Ax_E': {'name': '实验组 Ax-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Ay_E': {'name': '实验组 Ay-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Az_E': {'name': '实验组 Az-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ax_E': {'name': '实验组 Ax-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ay_E': {'name': '实验组 Ay-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Az_E': {'name': '实验组 Az-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Crest_Ax_E': {'name': '实验组 Ax-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Ay_E': {'name': '实验组 Ay-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Az_E': {'name': '实验组 Az-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'VDV_Ax_E': {'name': '实验组 Ax-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Ay_E': {'name': '实验组 Ay-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Az_E': {'name': '实验组 Az-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'Skew_Ax_E': {'name': '实验组 Ax-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Ay_E': {'name': '实验组 Ay-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Az_E': {'name': '实验组 Az-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ax_E': {'name': '实验组 Ax-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ay_E': {'name': '实验组 Ay-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Az_E': {'name': '实验组 Az-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'MAV_Ax_E': {'name': '实验组 Ax-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Ay_E': {'name': '实验组 Ay-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Az_E': {'name': '实验组 Az-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'Impf_Ax_E': {'name': '实验组 Ax-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Ay_E': {'name': '实验组 Ay-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Az_E': {'name': '实验组 Az-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},

    # ── 对照组 (C) 全套指标 ──
    'RMS_Ax_C': {'name': '对照组 Ax-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Ay_C': {'name': '对照组 Ay-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Az_C': {'name': '对照组 Az-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ax_C': {'name': '对照组 Ax-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ay_C': {'name': '对照组 Ay-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Az_C': {'name': '对照组 Az-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Crest_Ax_C': {'name': '对照组 Ax-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Ay_C': {'name': '对照组 Ay-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Az_C': {'name': '对照组 Az-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'VDV_Ax_C': {'name': '对照组 Ax-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Ay_C': {'name': '对照组 Ay-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Az_C': {'name': '对照组 Az-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'Skew_Ax_C': {'name': '对照组 Ax-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Ay_C': {'name': '对照组 Ay-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Az_C': {'name': '对照组 Az-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ax_C': {'name': '对照组 Ax-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ay_C': {'name': '对照组 Ay-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Az_C': {'name': '对照组 Az-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'MAV_Ax_C': {'name': '对照组 Ax-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Ay_C': {'name': '对照组 Ay-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Az_C': {'name': '对照组 Az-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'Impf_Ax_C': {'name': '对照组 Ax-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Ay_C': {'name': '对照组 Ay-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Az_C': {'name': '对照组 Az-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},

    # ── 总振动剂量值 ──
    'E_total_VDV': {'name': '实验组总VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'C_total_VDV': {'name': '对照组总VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},

    # ── 胸骨指标 (Sternum) ──
    'RMS_Ax_S': {'name': '胸骨 Ax-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Ay_S': {'name': '胸骨 Ay-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'RMS_Az_S': {'name': '胸骨 Az-RMS', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ax_S': {'name': '胸骨 Ax-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Ay_S': {'name': '胸骨 Ay-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Peak_Az_S': {'name': '胸骨 Az-Peak', 'unit': 'g', 'type': 'full_timeseries'},
    'Crest_Ax_S': {'name': '胸骨 Ax-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Ay_S': {'name': '胸骨 Ay-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'Crest_Az_S': {'name': '胸骨 Az-CrestFactor', 'unit': '', 'type': 'full_timeseries'},
    'VDV_Ax_S': {'name': '胸骨 Ax-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Ay_S': {'name': '胸骨 Ay-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'VDV_Az_S': {'name': '胸骨 Az-VDV', 'unit': 'm/s^1.75', 'type': 'full_timeseries'},
    'Skew_Ax_S': {'name': '胸骨 Ax-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Ay_S': {'name': '胸骨 Ay-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Skew_Az_S': {'name': '胸骨 Az-Skewness', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ax_S': {'name': '胸骨 Ax-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Ay_S': {'name': '胸骨 Ay-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'Kurt_Az_S': {'name': '胸骨 Az-Kurtosis', 'unit': '', 'type': 'full_timeseries'},
    'MAV_Ax_S': {'name': '胸骨 Ax-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Ay_S': {'name': '胸骨 Ay-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'MAV_Az_S': {'name': '胸骨 Az-MAV', 'unit': 'g', 'type': 'full_timeseries'},
    'Impf_Ax_S': {'name': '胸骨 Ax-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Ay_S': {'name': '胸骨 Ay-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},
    'Impf_Az_S': {'name': '胸骨 Az-ImpulseFactor', 'unit': '', 'type': 'full_timeseries'},

    # ── 概览仪表盘指标 ──
    'OVTV_DASHBOARD': {'name': '总振动值 OVTV(g)', 'unit': 'g', 'type': 'dashboard'},
    'DOM_BAND': {'name': '主导频带', 'unit': 'Hz', 'type': 'dashboard'},
    'CF_Z': {'name': '冲击因数 CF(Z)', 'unit': '', 'type': 'dashboard'},
    'LOCATION_COUNT': {'name': '位置数', 'unit': '个', 'type': 'dashboard'},
    'ISO_REF_ZONE': {'name': 'ISO参考区', 'unit': '', 'type': 'dashboard'},
    'DURATION': {'name': '分析时长', 'unit': 's', 'type': 'dashboard'},
    'BEHAVIOR_EVENT_COUNT': {'name': '驾驶行为事件数', 'unit': '次', 'type': 'dashboard'},
    'BEHAVIOR_EVENT_TYPES': {'name': '事件类型覆盖', 'unit': '种', 'type': 'dashboard'},

    # ── 频段衰减指标 ──
    'BAND_ATT_01_05': {'name': '超低频段衰减率(0.1-0.5Hz)', 'unit': '%', 'type': 'band_attenuation'},
    'BAND_ATT_05_1': {'name': '低频段衰减率(0.5-1Hz)', 'unit': '%', 'type': 'band_attenuation'},
    'BAND_ATT_1_5': {'name': '中频段衰减率(1-5Hz)', 'unit': '%', 'type': 'band_attenuation'},
    'BAND_ATT_5_20': {'name': '高频段衰减率(5-20Hz)', 'unit': '%', 'type': 'band_attenuation'},
    'BAND_ATT_20_80': {'name': '超高频段衰减率(20-80Hz)', 'unit': '%', 'type': 'band_attenuation'},
}

INDICATOR_DETAIL = {
    # ═══════════════════════════════════════════════════════════
    #                稳态舒适度 (Steady-state Comfort)
    # ═══════════════════════════════════════════════════════════

    'SEAT_Z': {
        'category': 'steady_state',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': '座椅 IMU5_座垫R点-1',
        'reference_imu': '座椅 IMU7_座椅底部-1',
        'data_fields': 'az[点数N]@seat_bottom(地板激励) + az[点数N]@seat_r(座椅响应)',
        'operator_pipeline': (
            '① PSD算子(Welch法, nperseg≤1024): az_seat→(f_seat, PSD_seat), az_floor→(f_floor, PSD_floor)\n'
            '② Weighting算子(freq Wk): PSD→PSD_w = PSD×Wk(f)², f∈[0→fs/2]\n'
            '    Wk(f): f<0.5→0.5; 0.5-2→f; 2-5→2; 5-16→10/f; 16-80→10/f; f≥80→0 (ISO 2631-1 Table 3)\n'
            '③ numpy梯形积分: I_seat=∫PSD_seat_w df, I_floor=∫PSD_floor_w df\n'
            '④ SEAT_Z = √(I_seat/I_floor)'
        ),
        'formula': (
            'SEAT_Z = √( ∫₀^{fs/2} PSD_seat(f)×[Wk(f)]² df / ∫₀^{fs/2} PSD_floor(f)×[Wk(f)]² df )\n'
            '☑ Coherence验证: 计算CSD→mean(coh), coh<0.5时Warning\n'
            'Fallback(floor缺失时): SEAT_Z ≈ RMS(FFT→Wk(f)→IFFT(az_seat)), 失去传递率物理意义'
        ),
        'calculation_logic': (
            'SEAT因子 — 座椅有效振幅传递率 (ISO 10326-2)\n'
            '衡量座椅对0.5-80Hz垂直振动的衰减效率\n'
            'SEAT_Z < 1: 座椅主动隔振(优秀)\n'
            'SEAT_Z = 1: 座椅无衰减(中性)\n'
            'SEAT_Z > 1: 座椅放大振动(不良)'
        ),
        'single_point_description': (
            '单点不可用: 降级为RMS×1后恒≈自比值1.0，完全失去传递率物理含义\n'
            '必须获得seat_r与seat_bottom的同步采样AZ数据'
        ),
        'two_point_description': '✅ 必须: seat_r(AZ) vs seat_bottom(AZ) 频率域PSD比值',
        'three_point_description': '不适用',
    },

    'SEAT_XY': {
        'category': 'steady_state',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': 'IMU5_座垫R点-1',
        'reference_imu': 'IMU7_座椅底部-1',
        'data_fields': 'ax[点数N]+ay[点数N]@seat_bottom(地板), ax[点数N]+ay[点数N]@seat_r(座椅表面)',
        'operator_pipeline': (
            '① Vector算子.synthesize_xy(ax,ay): xy_seat=√(ax²+ay²)@seat_r, xy_floor=√(ax²+ay²)@seat_bottom\n'
            '② PSD算子(Welch): xy_seat→(f, PSD_seat), xy_floor→(f, PSD_floor)\n'
            '③ Weighting算子(freq Wd): PSD_w=PSD×Wd(f)²\n'
            '    Wd(f): f<0.5→1; 0.5-2→f/0.5; 2-5→1; 5-16→5/f; 16-80→5/16×16/f; f≥80→0\n'
            '④ 梯形积分 + √(int_seat/int_floor) = SEAT_XY'
        ),
        'formula': (
            'SEAT_XY = √( ∫₀^{fs/2} PSD(xy_seat)×[Wd(f)]² df / ∫₀^{fs/2} PSD(xy_floor)×[Wd(f)]² df )\n'
            '☑ Coherence验证: 计算CSD→mean(coh), coh<0.5时Warning\n'
            'Fallback: 单点RMS(FFT→Wd(f)→IFFT(xy_seat))'
        ),
        'calculation_logic': 'SEAT_XY — 座椅水平振幅传递率 (ISO 10326-2)，Wk→Wd加权，衡量水平方向振动衰减',
        'single_point_description': '单点不可用(same as SEAT_Z)',
        'two_point_description': '✅ 必须: seat_r(XY合成) vs seat_bottom(XY合成) 频率域PSD比值',
        'three_point_description': '不适用',
    },

    'AW_Z': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@指定位置',
        'operator_pipeline': (
            '① Weighting算子.apply_weighting_z_via_freq(az, sr): 频域Wk加权\n'
            '    FFT(az)→Wk(f)→IFFT, 与SEAT_Z共用同一Wk(f)函数 (ISO 2631-1 Table 3)\n'
            '② RMS: AW_Z = √[ (1/N)×Σ(az_weighted_i²) ]'
        ),
        'formula': (
            'az → FFT→Wk(f)→IFFT → aw[0..N-1]\n'
            'AW_Z = √( Σᵢ aw_i² / N )  [单位: g]'
        ),
        'calculation_logic': 'ISO 2631-1 Wk加权垂直加速度RMS。head/torso/seat_r三位置对比构成振动传递梯度',
        'single_point_description': '✅ 单IMU: az_raw → Wk时域卷积 → √mean(weighted²)',
        'two_point_description': '🔶 seat_r vs head AW_z比值 反映 人头对臀点振动的隔振效率',
        'three_point_description': '🔶 head/torso/seat_r 三个AW_z构成完整的Z轴振动传递梯度曲线',
    },

    'AW_XY': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]@指定位置',
        'operator_pipeline': (
            '① VectorOperator.synthesize_xy(ax,ay): xy=√(ax_i²+ay_i²) for i=0..N-1\n'
            '② WeightingOperator.apply_weighting_xy_via_freq(xy, sr): 频域Wd加权\n'
            '    FFT(xy)→Wd(f)→IFFT, 与SEAT_XY共用同一Wd(f)函数 (ISO 2631-1 Table 4)\n'
            '③ AW_XY = RMS(xy_weighted)'
        ),
        'formula': (
            'xy_i = √(ax_i²+ay_i²), i=0..N-1\n'
            'xy → FFT→Wd(f)→IFFT → xyw[0..N-1]\n'
            'AW_XY = √( Σᵢ xyw_i² / N )  [单位: g]'
        ),
        'calculation_logic': 'ISO 2631-1 Wd加权水平加速度RMS。多位置对比可评价侧向振动沿人体的传递路径',
        'single_point_description': '✅ 单IMU: (ax,ay)→√合成→Wd滤波→RMS',
        'two_point_description': '🔶 两位置 AW_xy 对比可评价侧向振动衰减效率',
        'three_point_description': '🔶 head/torso/seat_r 三位置构成水平振动传递梯度',
    },

    'OVTV': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① VectorOperator.synthesize(ax,ay,az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
            '② 四次方累计: D = mean(a_total_i⁴) × N/sr\n'
            '③ OVTV = D^(0.25) = (∫a_total⁴ dt)^(1/4)'
        ),
        'formula': (
            'a_total_i = √(ax_i²+ay_i²+az_i²)  [3-axis resultant]\n'
            'OVTV = [ (1/N)×Σᵢ a_total_i⁴ … × (N/f_s) ] ^ (1/4)  [单位: m/s^1.75]\n'
            '等价: OVTV = (∫₀^T a_total(t)⁴ dt)^(1/4)'
        ),
        'calculation_logic': (
            'BS 6841 四次方振动剂量\n'
            '四次方积分比RMS(²)更敏感于振动峰值因子\n'
            'excellent<0.5, good<1.0, fair<1.7'
        ),
        'single_point_description': '✅ 单IMU三轴合成, 四次方积分, 4th-root, 独立计算',
        'two_point_description': '🔶 seat_r vs head OVTV差值 反映全身振动剂量衰减率',
        'three_point_description': '不适用',
    },

    'R_FACTOR': {
        'category': 'steady_state',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector: lateral_strength = ax + ay (横向求和)\n'
            '② σ(ax+ay) = np.std(ax+ay), σ(az) = np.std(az)\n'
            '③ R_FACTOR = σ(ax+ay)/(σ(az)+1e-9)'
        ),
        'formula': (
            'R_FACTOR = σ(ax+ay) / [ σ(az) + 0.001 ]\n'
            'σ = 标准差 = √( (1/N)×Σ(x_i-x̄)² )\n'
            'R<1→垂向主宰; R≈1→均衡; R>1→侧向主宰(curves)'
        ),
        'calculation_logic': 'R因子 — 侧向/垂向振动方向性比率。head vs seat_r差值反映人体对方向振动的选择性衰减',
        'single_point_description': '✅ 单IMU: 标准差比值(标量)',
        'two_point_description': '🔶 head vs seat_r R_FACTOR差异 反映 人体对水平/垂直振动的衰减不对称性',
        'three_point_description': '不适用',
    },

    # ═══════════════════════════════════════════════════════════
    #                动态舒适度 (Dynamic Comfort)
    # ═══════════════════════════════════════════════════════════

    'VDV_Z': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@指定位置',
        'operator_pipeline': (
            '① WeightingOp.apply_weighting_z_via_freq(az, sr): 频域Wk加权→azw[0..N-1]\n'
            '    FFT→Wk(f)→IFFT, 与SEAT_Z共用同一Wk(f)函数\n'
            '② dt = 1.0/sr (采样间隔)\n'
            '③ VDV_Z = [ Σᵢ azw_i⁴  × dt ] ^ (1/4)'
        ),
        'formula': (
            'az_raw[N] → Wk时域滤波 → azw[N]\n'
            'VDV_Z = ( Σᵢ₌₀ᴺ⁻¹ azw_i⁴ × (1/sr) ) ^ (1/4)  [单位: g·s^0.25 或 m/s^1.75]\n'
            'BS 6841: VDV>1.5 ⇒ "可能不适"'
        ),
        'calculation_logic': (
            'BS 6841 累积振动剂量值\n'
            'Wk加权+四次方积分 → 对高冲击事件(peak)的剂量累积极为敏感\n'
            'head/torso/seat_r三位置VDV梯度 = 全身振动剂量传输画像'
        ),
        'single_point_description': '✅ 单IMU: az→Wk时域滤波→四次方积分→4th-root',
        'two_point_description': '🔶 head VDV / seat_r VDV 比值 = 座椅对振动剂量的隔振效率',
        'three_point_description': '🔶 head→torso→seat_r VDV梯度 沿脊柱下行, 揭示振动剂量从小(臀)→大(头)的传递规律',
    },

    'TR_Z': {
        'category': 'dynamic',
        'location_dependency': 'two_positions',
        'location_dependency_label': '需要 2 个位置',
        'required_locations': ['seat_r', 'seat_bottom'],
        'primary_imu': 'IMU5_座垫R点-1(响应y) + IMU7_座椅底部-1(输入x)',
        'data_fields': 'az[点数N]@seat_bottom, az[点数N]@seat_r, 两通道需同步采样长度一致',
        'operator_pipeline': (
            '① CSDOperator.compute(az_floor, az_seat, sr, nperseg≤256):\n'
            '    - welch(floor) → Pxx\n'
            '    - welch(seat)  → Pyy\n'
            '    - csd(floor,seat) → Pxy\n'
            '    - H(f)=Pxy(f)/(Pxx(f)+1e-12)\n'
            '    - coherence(f) = |Pxy|²/(Pxx·Pyy+1e-12)\n'
            '② CSD.transfer_function_db: |H(f)|→20log10→dB谱\n'
            '    - mask 0.5-50Hz找峰值\n'
            '    - TR_Z = peak_dB(0.5-50Hz)\n'
            '☑ Coherence验证: mean(coh)<0.5→Warning\n'
            '③ Fallback(floor数据缺失): TR_Z = σ(az_seat)/σ(az_floor) ≈1.0 无意义'
        ),
        'formula': (
            'CSD(Floor→Seat): H(f)=CSD(floor,seat,f)/PSD(floor,f)\n'
            'H_dB(f) = 20×log₁₀(|H(f)|)\n'
            'TR_Z = max[ H_dB(f) for f∈(0.5,50)Hz ], 0dB等价(输出=输入)\n'
            'TR_Z_image: 需4位置全TR链\n'
            '   seat_bottom→seat_r (TR_SEAT): 座椅垂向传递率\n'
            '   seat_r→torso      (TR_TORSO):人体脊椎下段传递率\n'
            '   torso→head        (TR_HEAD): 人体脊椎上段传递率'
        ),
        'calculation_logic': (
            'TR_Z — 频率域跨位置振动传递函数峰值dB\n'
            '>0dB: 振动在特定频段被放大(共振峰值)\n'
            '<0dB: 振动衰减\n'
            '含coherence验证函数确保传递率可靠性'
        ),
        'single_point_description': '单点不可用: 自CSD→H≈1→0dB, 完全无意义, 必须两个位置同步数据',
        'two_point_description': '✅ 必须: seat_r vs seat_bottom CSD 传递函数 峰值dB',
        'three_point_description': '🔴 完整TR链需要4个位置: seat_bottom→seat_r→torso→head 构成三级传递率CSD链',
    },

    'DISP_TR': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU3_躯干T8-1 (torso)',
        'data_fields': 'az[点数N]@torso',
        'operator_pipeline': (
            '① IntegrationOperator.integrate_to_displacement(az, sr):\n'
            '    - scipy signal.butter(2, 0.5/sr·2, HP): 消除积分漂移\n'
            '    - acc_f = signal.filtfilt(b,a,az)\n'
            '    - vel   = cumsum(acc_f)/sr          (一次积分 → 速度)\n'
            '    - vel_f = filtfilt(b,a,vel)          (HP二次滤波)\n'
            '    - disp  = cumsum(vel_f)/sr × 1000   (二次积分→位移[mm])\n'
            '    注: HP滤波已消除DC漂移, 异常路径额外有 disp-mean(disp)\n'
            '② DISP_TR = max(|disp|)'
        ),
        'formula': (
            'Step1: az → Butterworth HP(0.5Hz,2nd) → az_f[N]\n'
            'Step2: v(tᵢ) = Σⱼ[0→i] az_f(j)×Δt , v_f=HP_filter(v)\n'
            'Step3: d(tᵢ) = Σⱼ[0→i] v_f(j)×Δt × 1000.0  [mm]\n'
            'Step4: DISP_TR = max(|d_i|,∀i)  [峰值位移, mm]\n'
            'Δt = 1/sr, HP双通已消DC, 无需额外-mean(d)'
        ),
        'calculation_logic': (
            '振动引起相对空间的绝对位移轨迹(mm)\n'
            '0.5Hz HP = 消除加速度计中低频直流漂移\n'
            '1000 coeff = g→mm/s² 单位转换\n'
            'seat_r vs torso DISP对比: 评价座椅靠背对人体的约束效果'
        ),
        'single_point_description': '✅ 单IMU: az→HP→1次积分→HP→2次积分→max_abs(×1000)',
        'two_point_description': '🔶 seat_r vs torso DISP_TR对比: 臀部(座) vs 躯干(背)相对位移差异',
        'three_point_description': '不适用',
    },

    'RFC_CC': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r',
        'operator_pipeline': (
            '① 提取az信号的局部极值序列 (peak/valley检测)\n'
            '② RainflowOperator.count(az): 四峰谷雨流计数法(ASTM E1049-85)\n'
            '    - 4-point 分组规则(S0,S1,S2,S3): 配对Δ₁=Δ₂循环\n'
            '    - 生成amplitude_ₖ, mean_ₖ 值对\n'
            '③ RFC_CC = len(valid_cycles) (过滤出 amplitude>1e-9 的有效循环数)'
        ),
        'formula': (
            'Peaks[] = {ai if ai>ai-1 and ai>ai+1}\n'
            'Valleys[] = {ai if ai<ai-1 and ai+1 and ai<ai+1}\n'
            'Rainflow(S0,S1,S2,S3, peaks/valleys):\n'
            '   Δ₁ = |S1-S0|, Δ₂ = |S2-S1|\n'
            '   if Δ₁≤Δ₂: 生成cycle(amplitude=Δ₁/2, mean=(S0+S1)/2)\n'
            '     pop(S0,S1) from list\n'
            '   else: i+=1 (跳过)\n'
            'RFC_CC = Σ valid_cycles (amp_i>1e-9)'
        ),
        'calculation_logic': (
            '应力/振动循环计数\n'
            '统计独立振动负载循环的总次数\n'
            '多位置循环数对比 → 判断各部位承受的交变振动载荷差异'
        ),
        'single_point_description': '✅ 单IMU: az→极值提取→四峰谷pairing→cycle count',
        'two_point_description': '🔶 多位置 RFC_CC 对比 判断 各部位的交变载荷次数差异',
        'three_point_description': '不适用',
    },

    'FDS_D': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r → rainflow cycles[]',
        'operator_pipeline': (
            '① RainflowOperator.count(az) → RF_result {cycles, amplitudes, means}\n'
            '② FDSOperator.compute(RF_result):\n'
            '    S-N曲线: Nᵢ = k × Sᵢ^(-b)  [Sᵢ=amplitude]\n'
            '    默认 b=8 (S-N曲线的Basquin指数,金属/结构疲劳高灵敏度)\n'
            '    total_damage D = Σᵢ (1/(Nᵢ+1e-12)) = Σᵢ (1/(k×amp_i^(-8)))\n'
            '    = Σᵢ (amp_i^8)  (k=1近似)\n'
            '③ FDS_D = D'
        ),
        'formula': (
            'Rainflow(az)→{amp_i,∀i}\n'
            'N_i = k × amp_i^(-b) = 1.0 × amp_i^(-8)  [S-N curve, Miner materials]\n'
            'FDS_D = Σᵢ amp_i^8   [Miner累积, 如果>1.0 ⇒ 预计疲劳失效]\n'
            '同时: LEQ = (Σᵢ (amp_i/9.81)^4 / (#cycles))^0.25'
        ),
        'calculation_logic': (
            'Miner线性累积疲劳损伤度 (BS 7608 / ASTM E1049)\n'
            'b=8: 标准钢结构Basquin指数\n'
            '总损伤D的累计, D≥1.0时表明到达疲劳寿命极限\n'
            '本指标是对S-N曲线与Miner法则的科学实现'
        ),
        'single_point_description': '✅ 单IMU: az→Rainflow→S-N curve(b=8)→ΣMiner累积损伤',
        'two_point_description': '🔶 seat_r vs torso FDS_D对比 揭示 座垫 vs 靠背的疲劳风险分布',
        'three_point_description': '不适用',
    },

    'FDS_R': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU5_座垫R点-1 (seat_r)',
        'data_fields': 'az[点数N]@seat_r → FDS_D派生',
        'operator_pipeline': (
            '① 先计算 FDS_D (rainflow → Miner 累积损伤度)\n'
            '② FDS_R = max(0.0, 1.0 - FDS_D)\n'
            '    0≤FDS_R≤1: 比例剩余疲劳寿命\n'
            '    0: 寿命已耗尽; 1: 寿命完全剩余'
        ),
        'formula': (
            'FDS_R = max(0, 1.0 - FDS_D)\n'
            'FDS_D = total Miner损伤度\n'
            '   0.0: 未损伤\n'
            '   0.1: 寿命用去10%\n'
            '   1.0: 寿命用去100%, FDS_R=0\n'
            '   2.0: 寿命用去200%, FDS_R=0'
        ),
        'calculation_logic': '疲劳剩余寿命(由FDS_D派生, 0-1区间)',
        'single_point_description': '✅ 从FDS_D派生: R = max(0, 1-D)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'STFT_FC': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFTOperator.compute(az, sr): scipy signal.stft\n'
            '    → spectrogram[S(freq)×T(time)]\n'
            '② extract_features:\n'
            '    Power per freq: P_f = Σⱼ spectrum[f,j]\n'
            '    Total power:  T = Σ_f P_f\n'
            '    if T>0: STFT_FC = Σ_f freqs·P_f / T  [频率重心, Hz]'
        ),
        'formula': (
            'STFT(az) → spectra_of dimensions [F×T]\n'
            'P(f) = Σ_j spectra[f,j] for all time indices j\n'
            'fc = Σ_f (freq[f] × P(f)) / Σ_f P(f)  [Hz: 功率加权平均主导频率]\n'
            'Human-sensitive range: 2-8 Hz (internal organ resonance)'
        ),
        'calculation_logic': (
            '时频谱功率加权平均频率\n'
            '反映该位置的"主导振动频率"\n'
            'Benz 4-5Hz: 人体内脏共振区 → 高风险\n'
            '12-20Hz: 脊柱轴向共振\n'
            '>20Hz: 高频抖颤, 不适感为主'
        ),
        'single_point_description': '✅ 单IMU: az→STFT→功率加权平均频率',
        'two_point_description': '🔶 seat_r(Wk weighted) vs sternum fc差异 辅助判断共振源位置',
        'three_point_description': '不适用',
    },

    'STFT_KT': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFT.compute → spectrum, freqs\n'
            '② extract P(f) and fc as in STFT_FC above\n'
            '③ STFT_KT = √[ Σ_f (freq[f]-fc)² × P(f) / Σ_f P(f) ]'
        ),
        'formula': (
            'fc = 频率重心(from STFT_FC)\n'
            'σ² = Σ_f (f-fc)² × P_f / Σ_f P_f\n'
            'STFT_KT = √σ²  [Hz: 频率分布的"宽度/频谱扩散度"]\n'
            '   Narrow: KT<3Hz → 纯频率(共振危险)\n'
            '   Wide:   KT>10Hz → 宽带振动(浑沌)'
        ),
        'calculation_logic': (
            '振动频率分布的"厚度/集中度"\n'
            '低KT: 振动集中窄带(如"在4.3Hz尖峰") → 共振风险\n'
            '高KT: 宽带振动 → 含多频率组分混乱感'
        ),
        'single_point_description': '✅ 从STFT结果: 频率标准差(二阶矩)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'STFT_CE': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'az[点数N]@sternum',
        'operator_pipeline': (
            '① STFT→spectrogram→P_f per freq\n'
            '② STFT_CE = max(P_f) / mean(P_f)  [无量纲, ≥1.0]'
        ),
        'formula': (
            'P_max = max_f {P(f)}\n'
            'P_avg = (1/F)×Σ_f P(f)  (F: #frequencies)\n'
            'STFT_CE = P_max / P_avg  [≥1.0, ≥5→强烈能量集中]\n'
            '  CE≈1: 均匀宽带\n'
            '  CE≈5: 能量集中在1个特定频率(共振)\n'
            '  CE>10: 极尖锐共振峰'
        ),
        'calculation_logic': (
            '谱能量集中度 — 功率峰值 / 平均功率\n'
            '→ CE越大 = 共振越尖锐(危险性高)\n'
            '→ CE接近1 = 体系无固有频率(宽带随机振动)\n'
            '联合fc & kt 构成完整的[重心,扩散,集中度]振动画像'
        ),
        'single_point_description': '✅ 峰/均比值, 从STFT频谱获取',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    # ═══════════════════════════════════════════════════════════
    #              瞬态感受评价 (Transient Sensation)
    # ═══════════════════════════════════════════════════════════

    'HIC15': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@head',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i²+ay_i²+az_i²) / 9.81  (→ g units)\n'
            '② 15ms window: n₍₁₅₎ = max(1, ceil(0.015·sr))\n'
            '    ☑ sr<200Hz: np.interp自动升采样至≥200Hz (≥3样本/15ms)\n'
            '    滑动窗口 i = 0..(N-n₁₅):\n'
            '    - segment = a_total[i:i+n₁₅], a_avg = mean(segment)\n'
            '    - dt_window = t(i+n₁₅-1)-t(i) ≈ 0.015s\n'
            '    - hic_candidate = dt_window × (a_avg)^(2.5)\n'
            '③ HIC15 = maxᵢ(hic_candidate_i)  (SAE J211, FMVSS 208)'
        ),
        'formula': (
            'aᵢ(g) = (1/9.81)×√(axᵢ²+ayᵢ²+azᵢ²)  for i=0..N-1\n'
            'n₁₅ = ⌈0.015·sr⌉, dt=1/sr (sr<200→自动升采样至200)\n'
            'for idx=0..N-n₁₅:\n'
            '   ā(input_window idx..idx+n15-1)\n'
            '   HIC_candidate(idx) = (t_n15-t_0) × ā^(2.5)\n'
            'HIC15 = argmax candidate(HIC_candidate)\n'
            'Limits (FMVSS 208): ≤700, >1000 fatal risk\n'
            '⚠️ **仅在头部眉心IMU1位置有意义**,其他位置计算无物理损伤意义'
        ),
        'calculation_logic': (
            'SAE J211 / FMVSS 208 头部损伤准则\n'
            '15ms时间窗口内合成加速度的2.5次方增幅\n'
            '—— 损伤概率: HIC15∞, 全时域取max\n'
            '→ 公式来自实验数据fit, 2.5次方代表加速度"敏感性"超过线性损伤\n'
            '→ 紧急制动/碰撞/过颠簸事件出现高强度HIC15'
        ),
        'single_point_description': '✅ 单IMU(head): 三轴合成g + 15ms滑动窗max[dt×avg²⁵]',
        'two_point_description': '不适用 (仅在head有意义)',
        'three_point_description': '不适用',
    },

    'ACC_H_PEAK': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@head',
        'operator_pipeline': (
            '① VectorOperator.synthesize(ax, ay, az): a_total_i = √(ax_i²+ay_i²+az_i²)\n'
            '② ACC_H_PEAK = max_i(|a_total_i|) — 合加速度绝对值的全程峰值 (g单位)'
        ),
        'formula': (
            'head_accel_i(g) = √(ax_i²+ay_i²+az_i²)\n'
            'ACC_H_PEAK = max_i{head_accel_i}  [g]\n'
            'SAE J211: >20g extreme, >10g moderate, >5g low\n'
            '⚠️ **仅在头部眉心IMU1位置有意义**'
        ),
        'calculation_logic': '头部承受的最大合加速度(peak of resultant) — SAE J211标准',
        'single_point_description': '✅ 单IMU(head): 三轴合成→max|output|',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'JERK_H': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (head专用)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head',
        'operator_pipeline': (
            '① np.diff(az) × sr: 一阶前向差分×采样率 = da/dt  [g/s]\n'
            '② JERK_H = max_i(|jerk_i|×1.0)'
        ),
        'formula': (
            'For i=0..N-2:\n'
            '   da_i = (az_{i+1}-az_i) · sr\n'
            'jerk_i = |da_i|  [g/s: 加速度变化率=急动度]\n'
            'JERK_H = max_i(jerk_i)  [单位: g/s]\n'
            'High-jerk = "sharp impact" → 冲击锋利'
        ),
        'calculation_logic': '头部加速度变化率(急动度/jerk), 反映冲击的"锋利程度" — 高Jerk值指示硬撞击/突发冲击事件',
        'single_point_description': '✅ 单IMU Z轴差分: jerk←np.diff(az)×sr→max abs',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_MRS': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head(时域数组)',
        'operator_pipeline': (
            '① SRS Operator (MIL-STD-810H Method 516.8 Smallwood Recursion):\n'
            '    - Q=10 → ζ=1/(2Q)=0.05\n'
            '    - f_group = 60 SDOF, 0.5-100Hz logspace\n'
            '    - For each f: damping = 0.05, Smallwood递推\{a₀,a₁,b₁,b₂\}\n'
            '        SDOF=Tₙ,Q=10→abs(response peak) for this freq→svalues[f]\n'
            '② SRS_MRS = max(svalues across full freq group)  [单位: g]'
        ),
        'formula': (
            'For each SDOF system π (0.5Hz<π<100Hz):\n'
            '   ωn=2πF₀; Δt=1/sr; ζ=0.05; compute constants:\n'
            '     E = e^(-ζωnΔt)\n'
            '     K = ωnΔtE/√(1-ζ²)\n'
            '     C = E·cos(ωnΔt√(1-ζ²)); S=E·sin(ωnΔt√1-ζ²)\n'
            '     b₁=2C, b₂=-E², a₀=1-K·S, a₁=K·S-E·[S/(ωdΔt)+C]\n'
            '   For all j=2..N-1:\n'
            '     resp[j]=b₁·resp[j-1]+b₂·resp[j-2]+a₀·az[j]+a₁·az[j-1]\n'
            '   svalue(π) = max_j(|resp_j|)\n'
            '   svalues_all(π) = envel; MRS = max_π sprom peak → SRS_MRS\n'
            'PV: from peak_freq displace; ATT: A=1/Q=0.1 temporal'
        ),
        'calculation_logic': (
            'MIL-STD-810H 冲击响应谱分析 — 最大响应谱(加速度)\n'
            '在0.5-100Hz频率范围内,定义60个SDOF系统\n'
            'Q=10系统 Smallwood高效递推 → SRS(f)的包络 → SRS_MRS = 包络峰值\n'
            'MRS数值对应"理想支持结构"在冲击中的最大承受加速度'
        ),
        'single_point_description': '✅ 单IMU Z轴→SRS Smallwood recursion(60 SDOF从0.5→100Hz)',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_Q': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (固定参数)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS分析固定参数',
        'operator_pipeline': (
            '① SRS类定义时固定 Q = 10.0 (MIL-STD-810H标准)\n'
            '② SRS_Q = 10.0'
        ),
        'formula': (
            'Q = 10.0 (固定值)\n'
            'ζ = 1/(2Q) = 0.05 (5% critical damping)\n'
            '用于 Shock Response Spectrum analysis\n'
            '**属计算参数,非直接测量指标**'
        ),
        'calculation_logic': '品质因数(属MIL-STD-810H标准编制参数)',
        'single_point_description': '✅ 计算系统的默认参数,非传感器映射,恒等Q=10',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_PV': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS+derivation',
        'operator_pipeline': (
            '① SRS compute获取: svalues, frequencies[]  → MRS, peak_freq index\n'
            '② PV = MRS / (2π·peak_freq)  (in m/s)'
        ),
        'formula': (
            'MRS = maxᵢ svaluesᵢ\n'
            'peak_f = frequencies[argmax svalues]\n'
            'SRS_PV = MRS / (2π·peak_f + 1e-12)  [m/s]\n'
            'Pseudo-velocity = 从SRS频率 & MRS推算的结构特定速度'
        ),
        'calculation_logic': (
            'SRS峰值频率所对应的伪速度(位移率)\n'
            'MIL-STD-810H冲击分析中, 从SRS输出MRS & peakF → 推算伪速度\n'
            '— 表示结构需吸收的冲击能量需求'
        ),
        'single_point_description': '✅ 从SRS峰值加速度x频率→伪速度派生, 单IMU即可',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'SRS_ATT': {
        'category': 'transient',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (固定参数)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'az[点数N]@head → SRS固定参数',
        'operator_pipeline': (
            '① SRS衰减 τ = 1/Q = 0.1s (from the same Q system)\n'
            '② SRS_ATT = 1/Q = 0.1'
        ),
        'formula': (
            'τ = 1/Q = 0.1 (秒)  [system impulse decay tim]\n'
            '— SDOF振子在初始激励后自由振动,持续约0.1s参数\n'
            '**属标准参数, 非实测值**'
        ),
        'calculation_logic': 'SRS冲击响应衰减时长(固定值1/Q = 0.1s)',
        'single_point_description': '✅ 固定计算参数, 非测量指标, τ = 0.1s',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'ACC_RMS': {
        'category': 'general',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (通用)',
        'primary_imu': '全部IMU通道通用',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
            '② RMS: ACC_RMS = √[ (1/N)×Σᵢ a_total_i² ]'
        ),
        'formula': (
            'a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\n'
            'ACC_RMS = √( Σᵢ₌₀ᴺ⁻¹ a_total_i² / N )  [g]\n'
            '物理意义: 该位置的总体振动能量水平\n'
            'excellent<0.3, good<0.6, fair<1.0'
        ),
        'calculation_logic': (
            'ISO 2631-1 基础时域指标\n'
            '三轴合成加速度均方根 → 反映指定位置的总体振动能量\n'
            'acc_rms_{pos}对比构成 全身→臀部→头部 的振动能量传递梯度'
        ),
        'single_point_description': '✅ 单IMU: 三轴合成 → RMS, 适用于所有位置',
        'two_point_description': '🔶 seat_r vs head ACC_RMS 比值 反映 座椅对总振动能量的隔振率',
        'three_point_description': '🔶 head→torso→seat_r ACC_RMS梯度 揭示振动能量沿脊柱的衰减路径',
    },

    'ACC_PEAK': {
        'category': 'general',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点即可 (通用)',
        'primary_imu': '全部IMU通道通用',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@指定位置',
        'operator_pipeline': (
            '① Vector合成: a_total_i = √(ax_i² + ay_i² + az_i²) for i=0..N-1\n'
            '② Peak: ACC_PEAK = max(a_total_i)'
        ),
        'formula': (
            'a_total_i = √(ax_i² + ay_i² + az_i²)  [三轴合成, g]\n'
            'ACC_PEAK = max( a_total_i )  [g]\n'
            '物理意义: 该位置在事件窗口内的瞬时最大冲击\n'
            'excellent<1.0, good<2.0, fair<4.0'
        ),
        'calculation_logic': (
            'ISO 2631-1 / BS 6841 瞬态峰值检测\n'
            '三轴合成瞬时加速度最大值 → 反映该位置的冲击强度\n'
            'peak_{pos}对比 构成 全身→臀部→头部 的冲击传递画像'
        ),
        'single_point_description': '✅ 单IMU: 三轴合成 → max, 适用于所有位置',
        'two_point_description': '🔶 head vs seat_r PEAK衰减 = 座椅对冲击峰值的隔振效果',
        'three_point_description': '🔶 head→torso→seat_r 峰值梯度 揭示冲击沿脊柱衰减的传递路径',
    },

    'S_D': {
        'category': 'spine',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点 (胸骨剑突)',
        'primary_imu': 'IMU9_胸骨剑突-1 (sternum)',
        'data_fields': 'ax[点数N]+ay[点数N]+az[点数N]@sternum',
        'operator_pipeline': (
            '① ISO2631_5Operator.compute(ax*9.81, ay*9.81, az*9.81, sr):\n'
            '   - cont2discrete 双线性变换 → 离散状态空间模型\n'
            '   - 输入: 三轴加速度[m/s²]@胸骨剑突\n'
            '   - 输出: S_d [MPa] 脊柱压缩应力\n'
            '② 若采样率<200Hz: np.interp 线性插值至200Hz\n'
        ),
        'formula': (
            'ISO 2631-5:2018 Annex D\n'
            'S_e(t) = [ Σ(m_k × a_k(t)) + Σ(c_k × S_{k-1}(t)) ]\n'
            'S_d = max_t(S_e(t)) / cross_sectional_area\n'
            'c_stress = 1.0 (应力转换因子)'
        ),
        'calculation_logic': (
            'ISO 2631-5 脊柱压缩应力模型\n'
            '通过多自由度离散状态空间模型将三轴加速度转化为\n'
            '腰椎(L4/L5)间盘压缩应力\n'
            'S_d < 0.5 MPa: 低风险\n'
            'S_d > 0.8 MPa: 高风险(ISO 2631-5 Annex C)'
        ),
        'single_point_description': '✅ 胸骨剑突单点加速度→脊柱压缩应力模型→S_d',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },

    'DISP_HR': {
        'category': 'dynamic',
        'location_dependency': 'single_point',
        'location_dependency_label': '单点 (头部)',
        'primary_imu': 'IMU1_头部眉心-1 (head)',
        'data_fields': 'ax+ay+az@head → 三轴位移合成',
        'operator_pipeline': (
            '① 三轴分别HP滤波(0.5Hz) → 一次积分(速度) → HP滤波 → 二次积分(位移)\n'
            '② VectorOperator.synthesize(dx, dy, dz): 三维合成位移\n'
            '③ DISP_HR = max(disp_3d) [mm]'
        ),
        'formula': (
            'For axis in (ax,ay,az):\n'
            '  vel = cumsum(HP_filter(axis))/sr  →  vel_f = HP_filter(vel)\n'
            '  disp_axis = cumsum(vel_f)/sr × 1000\n'
            'DISP_HR = max(√(dx²+dy²+dz²)) [mm]'
        ),
        'calculation_logic': '头部三维合成位移峰值，表征头部在空间中的最大偏移量',
        'single_point_description': '✅ 头部三轴加速度→二次积分→三维合成位移峰值',
        'two_point_description': '不适用',
        'three_point_description': '不适用',
    },
}


# ═══════════════════════════════════════════════════════════════
# 方案C — 单组诊断 (Transfer Path + Weakest Link)
# ═══════════════════════════════════════════════════════════════

FIXED_PARAMETERS = {
    'SRS_Q':  {'value': 10.0, 'desc': '品质因数(固定参数, MIL-STD-810H)', 'unit': ''},
    'SRS_ATT': {'value': 0.10, 'desc': '衰减时间常数(固定参数, MIL-STD-810H)', 'unit': 's'},
}

DIAGNOSIS_THRESHOLDS = {
    'SEAT_Z':  {'pass': 0.80, 'warn': 1.00, 'desc': '座椅垂直传递率', 'loc': 'seat_r'},
    'SEAT_XY': {'pass': 0.80, 'warn': 1.00, 'desc': '座椅水平传递率', 'loc': 'seat_r'},
    'HIC15':   {'pass': 700,  'warn': 1000, 'desc': '头部损伤准则', 'loc': 'head'},
    'SRS_MRS': {'pass': 15.0, 'warn': 30.0, 'desc': '冲击响应谱峰值', 'loc': 'head'},
    'SRS_PV':  {'pass': 5.0,  'warn': 10.0, 'desc': '峰值速度[m/s]', 'loc': 'head'},
    'ACC_H_PEAK': {'pass': 5.0, 'warn': 10.0, 'desc': '头部峰值加速度', 'loc': 'head'},
    'JERK_H':  {'pass': 5.0, 'warn': 15.0, 'desc': '头部冲击急动度', 'loc': 'head'},
    'FDS_D':   {'pass': 0.30, 'warn': 0.70, 'desc': '疲劳累积损伤', 'loc': 'seat_r'},
    'FDS_R':   {'pass': 0.70, 'warn': 0.30, 'desc': '剩余寿命', 'loc': 'seat_r'},
    'RFC_CC':  {'pass': 20,   'warn': 50,   'desc': '雨流循环计数', 'loc': 'seat_r'},
    'AW_Z':    {'pass': 0.30, 'warn': 0.60, 'desc': 'Wk加权加速度RMS', 'loc': 'seat_r'},
    'AW_XY':   {'pass': 0.30, 'warn': 0.60, 'desc': 'Wd加权加速度RMS', 'loc': 'seat_r'},
    'VDV_Z':   {'pass': 2.0,  'warn': 5.0,  'desc': '振动剂量值', 'loc': 'seat_r'},
    'OVTV':    {'pass': 0.50, 'warn': 1.70, 'desc': '总体振动值', 'loc': 'seat_r'},
    'R_FACTOR': {'pass': 0.50, 'warn': 1.00, 'desc': 'R因子(侧向/垂向)', 'loc': 'seat_r'},
    'TR_Z':    {'pass': 0.0,  'warn': 5.0,  'desc': '垂直传递率[dB]', 'loc': 'seat_r'},
    'DISP_TR': {'pass': 200,  'warn': 500,  'desc': '峰值相对位移[mm]', 'loc': 'seat_r'},
    'STFT_FC': {'pass': 8.0,  'warn': 12.0, 'desc': '频率中心[Hz]', 'loc': 'torso'},
    'STFT_KT': {'pass': 3.0,  'warn': 10.0, 'desc': '频率扩展[Hz]', 'loc': 'torso'},
    'STFT_CE': {'pass': 5.0,  'warn': 10.0, 'desc': '能量集中度', 'loc': 'torso'},
    'ACC_RMS': {'pass': 0.3, 'warn': 1.0, 'desc': '加速度均方根[g]', 'loc': 'seat_r'},
    'ACC_PEAK': {'pass': 1.0, 'warn': 4.0, 'desc': '峰值加速度[g]', 'loc': 'seat_r'},

    # ═══════════════════════════════════════════════════════════
    #  全时域统计指标诊断阈值 (87项)
    # ═══════════════════════════════════════════════════════════

    # ── 实验组 (E) 头部指标阈值 ──
    'RMS_Ax_E': {'pass': 3.0, 'warn': 8.0, 'desc': '实验组头部纵向RMS', 'loc': 'head'},
    'RMS_Ay_E': {'pass': 3.0, 'warn': 6.0, 'desc': '实验组头部横向RMS', 'loc': 'head'},
    'RMS_Az_E': {'pass': 2.0, 'warn': 5.0, 'desc': '实验组头部垂向RMS', 'loc': 'head'},
    'Peak_Ax_E': {'pass': 10.0, 'warn': 25.0, 'desc': '实验组头部纵向峰值', 'loc': 'head'},
    'Peak_Ay_E': {'pass': 10.0, 'warn': 20.0, 'desc': '实验组头部横向峰值', 'loc': 'head'},
    'Peak_Az_E': {'pass': 8.0, 'warn': 18.0, 'desc': '实验组头部垂向峰值', 'loc': 'head'},
    'Crest_Ax_E': {'pass': 5.0, 'warn': 12.0, 'desc': '实验组头部纵向波峰因数', 'loc': 'head'},
    'Crest_Ay_E': {'pass': 5.0, 'warn': 12.0, 'desc': '实验组头部横向波峰因数', 'loc': 'head'},
    'Crest_Az_E': {'pass': 6.0, 'warn': 15.0, 'desc': '实验组头部垂向波峰因数', 'loc': 'head'},
    'VDV_Ax_E': {'pass': 15.0, 'warn': 30.0, 'desc': '实验组头部纵向VDV', 'loc': 'head'},
    'VDV_Ay_E': {'pass': 12.0, 'warn': 25.0, 'desc': '实验组头部横向VDV', 'loc': 'head'},
    'VDV_Az_E': {'pass': 18.0, 'warn': 35.0, 'desc': '实验组头部垂向VDV', 'loc': 'head'},
    'Skew_Ax_E': {'pass': 1.0, 'warn': 3.0, 'desc': '实验组 Ax 歪度', 'loc': 'head'},
    'Skew_Ay_E': {'pass': 1.0, 'warn': 3.0, 'desc': '实验组 Ay 歪度', 'loc': 'head'},
    'Skew_Az_E': {'pass': 1.0, 'warn': 3.0, 'desc': '实验组 Az 歪度', 'loc': 'head'},
    'Kurt_Ax_E': {'pass': 3.0, 'warn': 8.0, 'desc': '实验组 Ax 峰度', 'loc': 'head'},
    'Kurt_Ay_E': {'pass': 3.0, 'warn': 8.0, 'desc': '实验组 Ay 峰度', 'loc': 'head'},
    'Kurt_Az_E': {'pass': 3.0, 'warn': 8.0, 'desc': '实验组 Az 峰度', 'loc': 'head'},
    'MAV_Ax_E': {'pass': 1.5, 'warn': 4.0, 'desc': '实验组 Ax MAV', 'loc': 'head'},
    'MAV_Ay_E': {'pass': 1.5, 'warn': 3.5, 'desc': '实验组 Ay MAV', 'loc': 'head'},
    'MAV_Az_E': {'pass': 1.0, 'warn': 3.0, 'desc': '实验组 Az MAV', 'loc': 'head'},
    'Impf_Ax_E': {'pass': 5.0, 'warn': 15.0, 'desc': '实验组 Ax 冲击因子', 'loc': 'head'},
    'Impf_Ay_E': {'pass': 5.0, 'warn': 15.0, 'desc': '实验组 Ay 冲击因子', 'loc': 'head'},
    'Impf_Az_E': {'pass': 6.0, 'warn': 18.0, 'desc': '实验组 Az 冲击因子', 'loc': 'head'},

    # ── 对照组 (C) 头部指标阈值 ──
    'RMS_Ax_C': {'pass': 3.5, 'warn': 9.0, 'desc': '对照组头部纵向RMS', 'loc': 'head'},
    'RMS_Ay_C': {'pass': 4.0, 'warn': 8.0, 'desc': '对照组头部横向RMS', 'loc': 'head'},
    'RMS_Az_C': {'pass': 3.0, 'warn': 6.0, 'desc': '对照组头部垂向RMS', 'loc': 'head'},
    'Peak_Ax_C': {'pass': 12.0, 'warn': 28.0, 'desc': '对照组头部纵向峰值', 'loc': 'head'},
    'Peak_Ay_C': {'pass': 12.0, 'warn': 25.0, 'desc': '对照组头部横向峰值', 'loc': 'head'},
    'Peak_Az_C': {'pass': 10.0, 'warn': 22.0, 'desc': '对照组头部垂向峰值', 'loc': 'head'},
    'Crest_Ax_C': {'pass': 6.0, 'warn': 14.0, 'desc': '对照组 Ax 波峰因数', 'loc': 'head'},
    'Crest_Ay_C': {'pass': 6.0, 'warn': 14.0, 'desc': '对照组 Ay 波峰因数', 'loc': 'head'},
    'Crest_Az_C': {'pass': 7.0, 'warn': 16.0, 'desc': '对照组 Az 波峰因数', 'loc': 'head'},
    'VDV_Ax_C': {'pass': 12.0, 'warn': 25.0, 'desc': '对照组 Ax VDV', 'loc': 'head'},
    'VDV_Ay_C': {'pass': 20.0, 'warn': 40.0, 'desc': '对照组 Ay VDV', 'loc': 'head'},
    'VDV_Az_C': {'pass': 18.0, 'warn': 35.0, 'desc': '对照组 Az VDV', 'loc': 'head'},
    'Skew_Ax_C': {'pass': 1.0, 'warn': 3.0, 'desc': '对照组 Ax 歪度', 'loc': 'head'},
    'Skew_Ay_C': {'pass': 1.0, 'warn': 3.0, 'desc': '对照组 Ay 歪度', 'loc': 'head'},
    'Skew_Az_C': {'pass': 1.0, 'warn': 3.0, 'desc': '对照组 Az 歪度', 'loc': 'head'},
    'Kurt_Ax_C': {'pass': 3.0, 'warn': 8.0, 'desc': '对照组 Ax 峰度', 'loc': 'head'},
    'Kurt_Ay_C': {'pass': 3.0, 'warn': 8.0, 'desc': '对照组 Ay 峰度', 'loc': 'head'},
    'Kurt_Az_C': {'pass': 3.0, 'warn': 8.0, 'desc': '对照组 Az 峰度', 'loc': 'head'},
    'MAV_Ax_C': {'pass': 2.0, 'warn': 5.0, 'desc': '对照组 Ax MAV', 'loc': 'head'},
    'MAV_Ay_C': {'pass': 2.5, 'warn': 5.0, 'desc': '对照组 Ay MAV', 'loc': 'head'},
    'MAV_Az_C': {'pass': 1.5, 'warn': 3.5, 'desc': '对照组 Az MAV', 'loc': 'head'},
    'Impf_Ax_C': {'pass': 6.0, 'warn': 18.0, 'desc': '对照组 Ax 冲击因子', 'loc': 'head'},
    'Impf_Ay_C': {'pass': 5.0, 'warn': 15.0, 'desc': '对照组 Ay 冲击因子', 'loc': 'head'},
    'Impf_Az_C': {'pass': 7.0, 'warn': 20.0, 'desc': '对照组 Az 冲击因子', 'loc': 'head'},

    # ── 胸骨 (S) 指标阈值 ──
    'RMS_Ax_S': {'pass': 3.0, 'warn': 7.0, 'desc': '胸骨 Ax RMS', 'loc': 'sternum'},
    'RMS_Ay_S': {'pass': 3.0, 'warn': 6.0, 'desc': '胸骨 Ay RMS', 'loc': 'sternum'},
    'RMS_Az_S': {'pass': 2.5, 'warn': 5.5, 'desc': '胸骨 Az RMS', 'loc': 'sternum'},
    'Peak_Ax_S': {'pass': 10.0, 'warn': 25.0, 'desc': '胸骨 Ax Peak', 'loc': 'sternum'},
    'Peak_Ay_S': {'pass': 10.0, 'warn': 22.0, 'desc': '胸骨 Ay Peak', 'loc': 'sternum'},
    'Peak_Az_S': {'pass': 9.0, 'warn': 20.0, 'desc': '胸骨 Az Peak', 'loc': 'sternum'},
    'Crest_Ax_S': {'pass': 5.0, 'warn': 12.0, 'desc': '胸骨 Ax Cf', 'loc': 'sternum'},
    'Crest_Ay_S': {'pass': 5.0, 'warn': 12.0, 'desc': '胸骨 Ay Cf', 'loc': 'sternum'},
    'Crest_Az_S': {'pass': 6.0, 'warn': 14.0, 'desc': '胸骨 Az Cf', 'loc': 'sternum'},
    'VDV_Ax_S': {'pass': 14.0, 'warn': 28.0, 'desc': '胸骨 Ax VDV', 'loc': 'sternum'},
    'VDV_Ay_S': {'pass': 13.0, 'warn': 26.0, 'desc': '胸骨 Ay VDV', 'loc': 'sternum'},
    'VDV_Az_S': {'pass': 17.0, 'warn': 34.0, 'desc': '胸骨 Az VDV', 'loc': 'sternum'},
    'Skew_Ax_S': {'pass': 1.0, 'warn': 3.0, 'desc': '胸骨 Ax 歪度', 'loc': 'sternum'},
    'Skew_Ay_S': {'pass': 1.0, 'warn': 3.0, 'desc': '胸骨 Ay 歪度', 'loc': 'sternum'},
    'Skew_Az_S': {'pass': 1.0, 'warn': 3.0, 'desc': '胸骨 Az 歪度', 'loc': 'sternum'},
    'Kurt_Ax_S': {'pass': 3.0, 'warn': 8.0, 'desc': '胸骨 Ax 峰度', 'loc': 'sternum'},
    'Kurt_Ay_S': {'pass': 3.0, 'warn': 8.0, 'desc': '胸骨 Ay 峰度', 'loc': 'sternum'},
    'Kurt_Az_S': {'pass': 3.0, 'warn': 8.0, 'desc': '胸骨 Az 峰度', 'loc': 'sternum'},

    # ── 总VDV ──
    'E_total_VDV': {'pass': 30.0, 'warn': 60.0, 'desc': '实验组三轴合成VDV', 'loc': 'head'},
    'C_total_VDV': {'pass': 35.0, 'warn': 70.0, 'desc': '对照组三轴合成VDV', 'loc': 'head'},

    # ── 频段衰减 ──
    'BAND_ATT_01_05': {'pass': 30.0, 'warn': 10.0, 'desc': '0.1-0.5Hz衰减率', 'loc': 'comparative'},
    'BAND_ATT_05_1': {'pass': 20.0, 'warn': 5.0, 'desc': '0.5-1Hz衰减率', 'loc': 'comparative'},
    'BAND_ATT_1_5': {'pass': 10.0, 'warn': 0.0, 'desc': '1-5Hz衰减率', 'loc': 'comparative'},
    'BAND_ATT_5_20': {'pass': 0.0, 'warn': -20.0, 'desc': '5-20Hz衰减率', 'loc': 'comparative'},
    'BAND_ATT_20_80': {'pass': 0.0, 'warn': -20.0, 'desc': '20-80Hz衰减率', 'loc': 'comparative'},
}

DIAGNOSIS_STATE_ICONS = {
    'pass': '✅',
    'warn': '⚠️',
    'fail': '❌',
    'na':   '—',
}

STANDARD_REFERENCES = {
    'HIC15':      {'standard': 'SAE J211 / FMVSS 208', 'limit': '≤700 (pass), >1000 (fail)', 'source_url': ''},
    'ACC_H_PEAK': {'standard': 'SAE J211',             'limit': '≤5g (excellent), ≤10g (good)', 'source_url': ''},
    'JERK_H':     {'standard': 'SAE J211 (derived)',    'limit': '≤5 g/s (excellent), ≤15 g/s (good)', 'source_url': ''},
    'SRS_MRS':    {'standard': 'MIL-STD-810H Method 516.8', 'limit': '≤15g (recommended)', 'source_url': ''},
    'SRS_Q':      {'standard': 'MIL-STD-810H',          'limit': 'Q=10 (standard parameter)', 'source_url': ''},
    'SRS_PV':     {'standard': 'MIL-STD-810H (derived)','limit': '≤5 m/s (recommended)', 'source_url': ''},
    'SRS_ATT':    {'standard': 'MIL-STD-810H',          'limit': 'τ=0.1s (standard parameter)', 'source_url': ''},
    'SEAT_Z':     {'standard': 'ISO 2631-1:1997',       'limit': '≤0.80 (pass), >1.0 (amplify)', 'source_url': ''},
    'SEAT_XY':    {'standard': 'ISO 2631-1:1997',       'limit': '≤0.80 (pass), >1.0 (amplify)', 'source_url': ''},
    'AW_Z':       {'standard': 'ISO 2631-1:1997',       'limit': '≤0.315 m/s² (comfortable)', 'source_url': ''},
    'AW_XY':      {'standard': 'ISO 2631-1:1997',       'limit': '≤0.315 m/s² (comfortable)', 'source_url': ''},
    'VDV_Z':      {'standard': 'BS 6841 / ISO 2631-1',  'limit': '≤8.5 (low), ≤17 (high)', 'source_url': ''},
    'OVTV':       {'standard': 'ISO 2631-1:1997',       'limit': '≤0.5 (comfortable), ≤1.7 (very uncomfortable)', 'source_url': ''},
    'R_FACTOR':   {'standard': 'ISO 2631-1 (derived)',  'limit': '≤1.0 (recommended)', 'source_url': ''},
    'DISP_TR':    {'standard': 'Engineering guideline',   'limit': '≤200mm (pass), ≤500mm (warn)', 'source_url': ''},
    'TR_Z':       {'standard': 'ISO 2631-1 (derived)',  'limit': '≤0 dB (no amplification)', 'source_url': ''},
    'FDS_D':      {'standard': 'Miner\'s Rule / BS 7608','limit': '≤0.20 (pass), ≤0.50 (warn)', 'source_url': ''},
    'FDS_R':      {'standard': 'Miner\'s Rule / BS 7608','limit': '≤0.20 (pass), ≤0.50 (warn)', 'source_url': ''},
    'RFC_CC':     {'standard': 'ASTM E1049-85',         'limit': '≤20 (pass), ≤50 (warn)', 'source_url': ''},
    'STFT_FC':    {'standard': 'Engineering guideline',   'limit': '2-8 Hz (内脏共振危险区)', 'source_url': ''},
    'STFT_KT':    {'standard': 'Engineering guideline',   'limit': '≤3 Hz (窄带共振), ≥10 Hz (宽带)', 'source_url': ''},
    'STFT_CE':    {'standard': 'Engineering guideline',   'limit': '≤5 (低集中度), ≥10 (尖锐共振)', 'source_url': ''},
}

# ── 四档评分阈值 (excellent/good/fair/poor) ──
# 用于 engine_v2._threshold_score 和 ResultStore 的4档分级
METRIC_THRESHOLDS = {
    'HIC15':      {'excellent': 200.0, 'good': 500.0, 'fair': 700.0, 'poor': 1000.0},
    'ACC_H_PEAK': {'excellent': 5.0,   'good': 10.0,  'fair': 15.0,  'poor': 20.0},
    'JERK_H':     {'excellent': 5.0,   'good': 15.0,  'fair': 25.0,  'poor': 40.0},
    'SRS_MRS':    {'excellent': 5.0,   'good': 10.0,  'fair': 15.0,  'poor': 20.0},
    'SRS_PV':     {'excellent': 2.0,   'good': 3.5,   'fair': 5.0,   'poor': 7.0},
    'SRS_Q':      {'excellent': 10.0,  'good': 10.0,  'fair': 10.0,  'poor': 10.0},
    'SRS_ATT':    {'excellent': 0.10,  'good': 0.10,  'fair': 0.10,  'poor': 0.10},
    'SEAT_Z':     {'excellent': 0.5,   'good': 0.8,   'fair': 1.0,   'poor': 1.25},
    'SEAT_XY':    {'excellent': 0.5,   'good': 0.8,   'fair': 1.0,   'poor': 1.25},
    'AW_Z':       {'excellent': 0.315, 'good': 0.5,   'fair': 0.8,   'poor': 1.0},
    'AW_XY':      {'excellent': 0.315, 'good': 0.5,   'fair': 0.8,   'poor': 1.0},
    'VDV_Z':      {'excellent': 5.0,   'good': 8.5,   'fair': 17.0,  'poor': 25.0},
    'OVTV':       {'excellent': 0.315, 'good': 0.5,   'fair': 1.0,   'poor': 1.7},
    'R_FACTOR':   {'excellent': 0.5,   'good': 1.0,   'fair': 1.5,   'poor': 2.0},
    'DISP_TR':    {'excellent': 50.0,  'good': 100.0, 'fair': 200.0, 'poor': 500.0},
    'TR_Z':       {'excellent': -3.0,  'good': 0.0,   'fair': 3.0,   'poor': 6.0},
    'FDS_D':      {'excellent': 0.05,  'good': 0.2,   'fair': 0.5,   'poor': 1.0},
    'FDS_R':      {'excellent': 0.05,  'good': 0.2,   'fair': 0.5,   'poor': 1.0},
    'RFC_CC':     {'excellent': 10.0,  'good': 20.0,  'fair': 50.0,  'poor': 100.0},
    'STFT_FC':    {'excellent': 1.0,   'good': 2.0,   'fair': 8.0,   'poor': 15.0},
    'STFT_KT':    {'excellent': 1.0,   'good': 3.0,   'fair': 10.0,  'poor': 20.0},
    'STFT_CE':    {'excellent': 2.0,   'good': 5.0,   'fair': 10.0,  'poor': 20.0},

    # ── 全时域统计指标的四档评分阈值 ──
    'RMS_Ay_E': {'excellent': 1.5, 'good': 3.0, 'fair': 5.0, 'poor': 8.0},
    'RMS_Az_E': {'excellent': 1.0, 'good': 2.0, 'fair': 4.0, 'poor': 7.0},
    'RMS_Ay_C': {'excellent': 3.0, 'good': 5.0, 'fair': 8.0, 'poor': 12.0},
    'RMS_Az_C': {'excellent': 2.0, 'good': 3.5, 'fair': 6.0, 'poor': 10.0},
    'VDV_Ay_E': {'excellent': 8.0, 'good': 15.0, 'fair': 25.0, 'poor': 40.0},
    'VDV_Ay_C': {'excellent': 15.0, 'good': 25.0, 'fair': 40.0, 'poor': 60.0},
    'E_total_VDV': {'excellent': 20.0, 'good': 35.0, 'fair': 55.0, 'poor': 80.0},
    'C_total_VDV': {'excellent': 25.0, 'good': 40.0, 'fair': 65.0, 'poor': 100.0},
    'BAND_ATT_01_05': {'excellent': 60.0, 'good': 40.0, 'fair': 15.0, 'poor': 0.0},
    'BAND_ATT_05_1': {'excellent': 50.0, 'good': 30.0, 'fair': 10.0, 'poor': 0.0},
    'BAND_ATT_1_5': {'excellent': 30.0, 'good': 15.0, 'fair': 5.0, 'poor': -10.0},
}

FOUR_LEVEL_GRADES = {
    'excellent': ('A', '优秀'),
    'good': ('B', '良好'),
    'fair': ('C', '一般'),
    'poor': ('D', '差'),
}


class EvaluationDirection(enum.Enum):
    LOWER_IS_BETTER = 'lower'
    LOWER_BETTER = 'lower'
    HIGHER_IS_BETTER = 'higher'
    HIGHER_BETTER = 'higher'
    CENTER_IS_BETTER = 'center'


class DataSourceType(enum.Enum):
    CAN_FILE = enum.auto()
    SERIAL_IMU = enum.auto()
    CNAP = enum.auto()
    MQTT = enum.auto()
    FILE_OFFLINE = enum.auto()


class RiskCategory(enum.Enum):
    NORMAL = 'normal'
    WARNING = 'warning'
    DANGER = 'danger'
    CRITICAL = 'critical'


@dataclasses.dataclass
class DrivingStateDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    risk_category: RiskCategory = RiskCategory.NORMAL
    risk_level_cn: str = ''
    color_hex: str = '#28a745'
    accel_range: tuple = (0.0, 0.0)
    speed_range: tuple = (0.0, 0.0)
    description: str = ''


@dataclasses.dataclass
class DataSourceDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    imu_labels: dict = dataclasses.field(default_factory=dict)
    vehicle_signal_fields: list = dataclasses.field(default_factory=list)
    protocol: str = ''
    physical_channel: str = ''
    sampling_rate_hz: float = 0.0
    sensor_model: str = ''
    supported_channels: list = dataclasses.field(default_factory=list)
    data_category: str = ''
    can_protocol: str = ''
    sync_strategy: str = ''


@dataclasses.dataclass
class RawFieldDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    physical_unit: str = ''
    data_type: str = ''
    range_min: float = 0.0
    range_max: float = 0.0
    sample_rate_hz: float = 0.0
    source_device: str = ''
    field_category: str = ''


@dataclasses.dataclass
class OperatorDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    category: str = ''
    pipeline_id: str = ''
    input_type: Any = None
    output_type: Any = None
    input_count: int = 0
    output_count: int = 0
    description: str = ''


@dataclasses.dataclass
class IndicatorDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    unit: str = ''
    direction: EvaluationDirection = EvaluationDirection.LOWER_IS_BETTER
    threshold_pass: str = ''
    threshold_excellent: str = ''
    evaluation_dimension: str = ''
    formula_text: str = ''
    formula_latex: str = ''
    operator_pipeline: tuple = ()
    applicable_locations: tuple = ()
    standard_refs: tuple = ()


@dataclasses.dataclass
class EvaluationModuleDef:
    code: str
    display_name_cn: str
    display_name_en: str = ''
    applicable_indicators: tuple = ()
    operator_count: int = 0
    status: str = 'active'
    description: str = ''


class MetadataRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.indicators: Dict[str, IndicatorDef] = {
            'HIC15':      IndicatorDef('HIC15',      '头部损伤准则 HIC15',      unit='',     evaluation_dimension='冲击域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'ACC_H_PEAK': IndicatorDef('ACC_H_PEAK', '头部峰值加速度',           unit='g',    evaluation_dimension='冲击域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'JERK_H':     IndicatorDef('JERK_H',     '头部加加速度',             unit='g/s',  evaluation_dimension='冲击域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'SRS_MRS':    IndicatorDef('SRS_MRS',    'SRS最大响应谱',            unit='g',    evaluation_dimension='冲击域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'SRS_PV':     IndicatorDef('SRS_PV',     'SRS伪速度',               unit='m/s',  evaluation_dimension='冲击域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'SRS_Q':      IndicatorDef('SRS_Q',      'SRS品质因数',             unit='',     evaluation_dimension='冲击域', direction=EvaluationDirection.CENTER_IS_BETTER),
            'SRS_ATT':    IndicatorDef('SRS_ATT',    'SRS衰减时间常数',          unit='s',    evaluation_dimension='冲击域', direction=EvaluationDirection.CENTER_IS_BETTER),
            'SEAT_Z':     IndicatorDef('SEAT_Z',     'Z轴SEAT因子',             unit='',     evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'SEAT_XY':    IndicatorDef('SEAT_XY',    '水平SEAT因子',             unit='',     evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'AW_Z':       IndicatorDef('AW_Z',       'Z轴加权加速度均方根',      unit='m/s2', evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'AW_XY':      IndicatorDef('AW_XY',      '水平加权加速度均方根',      unit='m/s2', evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'VDV_Z':      IndicatorDef('VDV_Z',      'Z轴振动剂量值',            unit='',     evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'OVTV':       IndicatorDef('OVTV',       '总振动值',                unit='m/s2', evaluation_dimension='频域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'R_FACTOR':   IndicatorDef('R_FACTOR',   '振动暴露因子',             unit='',     evaluation_dimension='时域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'DISP_TR':    IndicatorDef('DISP_TR',    'Z轴峰峰位移',             unit='mm',   evaluation_dimension='时域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'TR_Z':       IndicatorDef('TR_Z',       'Z轴传递率',               unit='dB',   evaluation_dimension='频域',   direction=EvaluationDirection.CENTER_IS_BETTER),
            'FDS_D':      IndicatorDef('FDS_D',      'Z轴疲劳损伤谱',            unit='',     evaluation_dimension='疲劳域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'FDS_R':      IndicatorDef('FDS_R',      '水平疲劳损伤谱',           unit='',     evaluation_dimension='疲劳域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'RFC_CC':     IndicatorDef('RFC_CC',     '雨流计数',                unit='次',   evaluation_dimension='疲劳域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'STFT_FC':    IndicatorDef('STFT_FC',    '主频中心',                unit='Hz',   evaluation_dimension='时频域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'STFT_KT':    IndicatorDef('STFT_KT',    '频带宽度',                unit='Hz',   evaluation_dimension='时频域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'STFT_CE':    IndicatorDef('STFT_CE',    '频率集中度',              unit='',     evaluation_dimension='时频域', direction=EvaluationDirection.LOWER_IS_BETTER),
            'ACC_RMS':    IndicatorDef('ACC_RMS',    '加速度均方根',             unit='g',    evaluation_dimension='时域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'ACC_PEAK':   IndicatorDef('ACC_PEAK',   '加速度峰值',              unit='g',    evaluation_dimension='时域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'DISP_HR':    IndicatorDef('DISP_HR',    '三轴峰峰位移',             unit='mm',   evaluation_dimension='时域',   direction=EvaluationDirection.LOWER_IS_BETTER),
            'S_D':        IndicatorDef('S_D',        '脊柱应力S_D',              unit='MPa',  evaluation_dimension='生物力学', direction=EvaluationDirection.LOWER_IS_BETTER),
        }
        self._register_full_timeseries_indicators()
        self._register_dashboard_indicators()
        self._register_band_attenuation_indicators()

        self.metric_thresholds_4level = METRIC_THRESHOLDS
        self.diagnosis_thresholds = DIAGNOSIS_THRESHOLDS
        self.indicator_details = INDICATOR_DETAIL
        self.data_sources: Dict[str, DataSourceDef] = {
            'CAN_IMU': DataSourceDef(
                'CAN_IMU', 'CAN总线IMU数据',
                display_name_en='CAN Bus IMU',
                imu_labels={
                    'IMU1': '头部眉心-1', 'IMU2': '头部眉心-2',
                    'IMU3': '躯干T8-1', 'IMU4': '躯干T8-2',
                    'IMU5': '座垫R点-1', 'IMU6': '座垫R点-2',
                    'IMU7': '座椅底部-1', 'IMU8': '座椅底部-2',
                    'IMU9': '胸骨剑突-1', 'IMU10': '胸骨剑突-2',
                },
                protocol='CAN 2.0B', physical_channel='ch1',
                sampling_rate_hz=100.0, sensor_model='SEN-IMU-V3',
                data_category='振动加速度', can_protocol='CAN2.0B_EXT',
                sync_strategy='timestamp',
            ),
            'CNAP_MONITOR': DataSourceDef(
                'CNAP_MONITOR', 'CNAP监护仪',
                display_name_en='CNAP Monitor',
                vehicle_signal_fields=['HR', 'BP_SYS', 'BP_DIA', 'SPO2', 'RR'],
                protocol='Serial/RS232', physical_channel='COM3',
                sampling_rate_hz=50.0, sensor_model='CNAP500',
                data_category='生理信号', sync_strategy='timestamp',
            ),
            'SERIAL_IMU': DataSourceDef(
                'SERIAL_IMU', '串口IMU传感器',
                display_name_en='Serial IMU Sensor',
                imu_labels={'IMU_S1': '座椅导轨-1', 'IMU_S2': '座椅导轨-2'},
                protocol='UART', physical_channel='COM4',
                sampling_rate_hz=200.0, sensor_model='WT901BLECL',
                data_category='振动加速度', can_protocol='N/A',
                sync_strategy='timestamp',
            ),
            'MQTT_REMOTE': DataSourceDef(
                'MQTT_REMOTE', 'MQTT远程数据',
                display_name_en='MQTT Remote Data',
                vehicle_signal_fields=['gps_lat', 'gps_lon', 'gps_speed'],
                protocol='MQTT/TCP', physical_channel='broker:1883',
                sampling_rate_hz=10.0, sensor_model='RemoteGPS',
                data_category='位置轨迹', sync_strategy='timestamp_align',
            ),
        }
        self.driving_states: Dict[str, DrivingStateDef] = {
            'steady_cruise': DrivingStateDef('steady_cruise', '匀速直行', 'Steady Cruise',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#28a745', accel_range=(-0.1, 0.1), speed_range=(30, 120),
                description='车辆保持恒定速度直线行驶，加速度接近零'),
            'acceleration': DrivingStateDef('acceleration', '正常加速', 'Normal Acceleration',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#17a2b8', accel_range=(0.1, 2.0), speed_range=(0, 120),
                description='车辆以正常速率加速行驶'),
            'deceleration': DrivingStateDef('deceleration', '正常减速', 'Normal Deceleration',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#ffc107', accel_range=(-2.0, -0.1), speed_range=(0, 120),
                description='车辆以正常速率减速行驶'),
            'hard_accel': DrivingStateDef('hard_accel', '急加速', 'Hard Acceleration',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#fd7e14', accel_range=(2.0, 5.0), speed_range=(0, 120),
                description='车辆急加速，加速度超过正常范围'),
            'hard_brake': DrivingStateDef('hard_brake', '急刹车', 'Hard Brake',
                risk_category=RiskCategory.DANGER, risk_level_cn='危险',
                color_hex='#dc3545', accel_range=(-5.0, -2.0), speed_range=(0, 120),
                description='车辆紧急制动，减速度超过正常范围'),
            'cornering': DrivingStateDef('cornering', '弯道行驶', 'Cornering',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#6f42c1', accel_range=(-0.5, 0.5), speed_range=(10, 60),
                description='车辆通过弯道，产生侧向加速度'),
            'sharp_turn': DrivingStateDef('sharp_turn', '急转弯', 'Sharp Turn',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#fd7e14', accel_range=(-1.0, 1.0), speed_range=(10, 40),
                description='车辆急转弯，侧向加速度较大'),
            'rough_road': DrivingStateDef('rough_road', '颠簸路面', 'Rough Road',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#e83e8c', accel_range=(-3.0, 3.0), speed_range=(10, 80),
                description='车辆通过不平整路面，产生较大垂向振动'),
            'severe_shock': DrivingStateDef('severe_shock', '剧烈冲击', 'Severe Shock',
                risk_category=RiskCategory.CRITICAL, risk_level_cn='严重',
                color_hex='#721c24', accel_range=(-8.0, 8.0), speed_range=(0, 120),
                description='车辆遭遇剧烈冲击，加速度超过极限范围'),
            'roll_risk': DrivingStateDef('roll_risk', '侧翻风险', 'Rollover Risk',
                risk_category=RiskCategory.CRITICAL, risk_level_cn='极度危险',
                color_hex='#721c24', accel_range=(-3.0, 3.0), speed_range=(10, 80),
                description='车辆存在侧翻风险，侧向加速度持续偏高'),
            'idle': DrivingStateDef('idle', '怠速/静止', 'Idle/Stationary',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#6c757d', accel_range=(-0.05, 0.05), speed_range=(0, 3),
                description='车辆怠速或处于静止状态'),

            # ── 补齐22种驾驶事件类型 (来自 DrivingEventDetector EVENT_TYPES) ──
            'cruising': DrivingStateDef('cruising', '恒速行驶', 'Cruising',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#2E86C1', accel_range=(-0.05, 0.05), speed_range=(30, 120),
                description='车辆保持恒定速度行驶，无加减速'),
            'stopped': DrivingStateDef('stopped', '停车', 'Stopped',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#85929E', accel_range=(-0.02, 0.02), speed_range=(0, 0),
                description='车辆完全停止'),
            'parked': DrivingStateDef('parked', '驻车', 'Parked',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#95A5A6', accel_range=(0.0, 0.0), speed_range=(0, 0),
                description='车辆处于驻车状态'),
            'lane_keeping': DrivingStateDef('lane_keeping', '车道保持', 'Lane Keeping',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#27AE60', accel_range=(-0.1, 0.1), speed_range=(30, 120),
                description='车辆保持车道居中行驶'),
            'left_turn': DrivingStateDef('left_turn', '左转', 'Left Turn',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#3498DB', accel_range=(-0.5, 0.5), speed_range=(10, 50),
                description='车辆向左转弯行驶'),
            'right_turn': DrivingStateDef('right_turn', '右转', 'Right Turn',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#2980B9', accel_range=(-0.5, 0.5), speed_range=(10, 50),
                description='车辆向右转弯行驶'),
            'tight_turn': DrivingStateDef('tight_turn', '小半径转弯', 'Tight Turn',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#E67E22', accel_range=(-1.5, 1.5), speed_range=(5, 30),
                description='车辆以小半径转弯，侧向加速度较大'),
            'wide_turn': DrivingStateDef('wide_turn', '大半径转弯', 'Wide Turn',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#1ABC9C', accel_range=(-0.3, 0.3), speed_range=(20, 80),
                description='车辆以大半径转弯，侧向加速度较小'),
            'u_turn': DrivingStateDef('u_turn', 'U型转弯', 'U-Turn',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#8E44AD', accel_range=(-1.0, 1.0), speed_range=(5, 20),
                description='车辆进行U型掉头转弯'),
            'cornering_acceleration': DrivingStateDef('cornering_acceleration', '弯道加速', 'Cornering Acceleration',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#D35400', accel_range=(0.5, 2.0), speed_range=(10, 60),
                description='车辆在弯道中加速行驶'),
            'cornering_deceleration': DrivingStateDef('cornering_deceleration', '弯道减速', 'Cornering Deceleration',
                risk_category=RiskCategory.NORMAL, risk_level_cn='安全',
                color_hex='#F39C12', accel_range=(-2.0, -0.5), speed_range=(10, 60),
                description='车辆在弯道中减速行驶'),
            'aggressive_deceleration': DrivingStateDef('aggressive_deceleration', '激进减速', 'Aggressive Deceleration',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#E74C3C', accel_range=(-5.0, -2.0), speed_range=(0, 120),
                description='车辆以异常速率减速，减速度较大'),
            'weaving': DrivingStateDef('weaving', '蛇形驾驶', 'Weaving',
                risk_category=RiskCategory.DANGER, risk_level_cn='危险',
                color_hex='#C0392B', accel_range=(-1.5, 1.5), speed_range=(20, 100),
                description='车辆频繁左右变道，蛇形行驶'),
            'rapid_direction_change': DrivingStateDef('rapid_direction_change', '急速变向', 'Rapid Direction Change',
                risk_category=RiskCategory.DANGER, risk_level_cn='危险',
                color_hex='#922B21', accel_range=(-3.0, 3.0), speed_range=(30, 100),
                description='车辆急速改变行驶方向，侧向加速度突变'),
            'severe_bump': DrivingStateDef('severe_bump', '剧烈颠簸', 'Severe Bump',
                risk_category=RiskCategory.WARNING, risk_level_cn='警告',
                color_hex='#E74C3C', accel_range=(-5.0, 5.0), speed_range=(10, 80),
                description='车辆遭遇剧烈颠簸，垂向加速度大幅突变'),
            'skid_risk': DrivingStateDef('skid_risk', '侧滑风险', 'Skid Risk',
                risk_category=RiskCategory.CRITICAL, risk_level_cn='严重',
                color_hex='#7B241C', accel_range=(-4.0, 4.0), speed_range=(20, 100),
                description='车辆存在侧滑风险，轮胎附着力不足'),
        }
        self.raw_fields: Dict[str, RawFieldDef] = {
            'ax': RawFieldDef('ax', 'X轴加速度', 'Accel X',
                physical_unit='g', data_type='float32',
                range_min=-16.0, range_max=16.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='加速度'),
            'ay': RawFieldDef('ay', 'Y轴加速度', 'Accel Y',
                physical_unit='g', data_type='float32',
                range_min=-16.0, range_max=16.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='加速度'),
            'az': RawFieldDef('az', 'Z轴加速度', 'Accel Z',
                physical_unit='g', data_type='float32',
                range_min=-16.0, range_max=16.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='加速度'),
            'gx': RawFieldDef('gx', 'X轴角速度', 'Gyro X',
                physical_unit='deg/s', data_type='float32',
                range_min=-2000.0, range_max=2000.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='角速度'),
            'gy': RawFieldDef('gy', 'Y轴角速度', 'Gyro Y',
                physical_unit='deg/s', data_type='float32',
                range_min=-2000.0, range_max=2000.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='角速度'),
            'gz': RawFieldDef('gz', 'Z轴角速度', 'Gyro Z',
                physical_unit='deg/s', data_type='float32',
                range_min=-2000.0, range_max=2000.0,
                sample_rate_hz=100.0, source_device='IMU_6DOF',
                field_category='角速度'),
            'speed': RawFieldDef('speed', '车速', 'Vehicle Speed',
                physical_unit='km/h', data_type='float32',
                range_min=0.0, range_max=250.0,
                sample_rate_hz=100.0, source_device='CAN_Bus',
                field_category='车辆状态'),
            'wheel': RawFieldDef('wheel', '方向盘转角', 'Steering Angle',
                physical_unit='deg', data_type='float32',
                range_min=-720.0, range_max=720.0,
                sample_rate_hz=100.0, source_device='CAN_Bus',
                field_category='车辆控制'),
            'hr': RawFieldDef('hr', '心率', 'Heart Rate',
                physical_unit='bpm', data_type='int16',
                range_min=0.0, range_max=255.0,
                sample_rate_hz=50.0, source_device='CNAP500',
                field_category='生理信号'),
            'bp_sys': RawFieldDef('bp_sys', '收缩压', 'Systolic BP',
                physical_unit='mmHg', data_type='float32',
                range_min=0.0, range_max=300.0,
                sample_rate_hz=50.0, source_device='CNAP500',
                field_category='生理信号'),
            'bp_dia': RawFieldDef('bp_dia', '舒张压', 'Diastolic BP',
                physical_unit='mmHg', data_type='float32',
                range_min=0.0, range_max=200.0,
                sample_rate_hz=50.0, source_device='CNAP500',
                field_category='生理信号'),
            'spo2': RawFieldDef('spo2', '血氧饱和度', 'SpO2',
                physical_unit='%', data_type='int16',
                range_min=0.0, range_max=100.0,
                sample_rate_hz=50.0, source_device='CNAP500',
                field_category='生理信号'),
            'rr': RawFieldDef('rr', '呼吸率', 'Respiratory Rate',
                physical_unit='bpm', data_type='int16',
                range_min=0.0, range_max=60.0,
                sample_rate_hz=50.0, source_device='CNAP500',
                field_category='生理信号'),
        }
        self.derived_fields: Dict[str, RawFieldDef] = {
            'accel_mag': RawFieldDef('accel_mag', '加速度合成幅值', 'Accel Magnitude',
                physical_unit='g', data_type='float32',
                range_min=0.0, range_max=27.7,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'jerk_x': RawFieldDef('jerk_x', 'X轴加加速度', 'Jerk X',
                physical_unit='g/s', data_type='float32',
                range_min=-500.0, range_max=500.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'jerk_y': RawFieldDef('jerk_y', 'Y轴加加速度', 'Jerk Y',
                physical_unit='g/s', data_type='float32',
                range_min=-500.0, range_max=500.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'jerk_z': RawFieldDef('jerk_z', 'Z轴加加速度', 'Jerk Z',
                physical_unit='g/s', data_type='float32',
                range_min=-500.0, range_max=500.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'vdv_total': RawFieldDef('vdv_total', '总振动剂量值', 'Total VDV',
                physical_unit='m/s^1.75', data_type='float32',
                range_min=0.0, range_max=50.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'seat_attenuation': RawFieldDef('seat_attenuation', '座椅衰减率', 'Seat Attenuation',
                physical_unit='%', data_type='float32',
                range_min=-100.0, range_max=100.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'band_energy_01_05': RawFieldDef('band_energy_01_05', '超低频段能量(0.1-0.5Hz)', 'Band Energy 0.1-0.5Hz',
                physical_unit='g²/Hz', data_type='float32',
                range_min=0.0, range_max=10.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'band_energy_05_1': RawFieldDef('band_energy_05_1', '低频段能量(0.5-1Hz)', 'Band Energy 0.5-1Hz',
                physical_unit='g²/Hz', data_type='float32',
                range_min=0.0, range_max=10.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'band_energy_1_5': RawFieldDef('band_energy_1_5', '中频段能量(1-5Hz)', 'Band Energy 1-5Hz',
                physical_unit='g²/Hz', data_type='float32',
                range_min=0.0, range_max=10.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'band_energy_5_20': RawFieldDef('band_energy_5_20', '高频段能量(5-20Hz)', 'Band Energy 5-20Hz',
                physical_unit='g²/Hz', data_type='float32',
                range_min=0.0, range_max=10.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'band_energy_20_80': RawFieldDef('band_energy_20_80', '超高频段能量(20-80Hz)', 'Band Energy 20-80Hz',
                physical_unit='g²/Hz', data_type='float32',
                range_min=0.0, range_max=10.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'crest_factor_z': RawFieldDef('crest_factor_z', 'Z轴波峰因子', 'Crest Factor Z',
                physical_unit='', data_type='float32',
                range_min=1.0, range_max=20.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'skewness_z': RawFieldDef('skewness_z', 'Z轴偏度', 'Skewness Z',
                physical_unit='', data_type='float32',
                range_min=-5.0, range_max=5.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'kurtosis_z': RawFieldDef('kurtosis_z', 'Z轴峭度', 'Kurtosis Z',
                physical_unit='', data_type='float32',
                range_min=-3.0, range_max=20.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'impulse_factor_z': RawFieldDef('impulse_factor_z', 'Z轴脉冲因子', 'Impulse Factor Z',
                physical_unit='', data_type='float32',
                range_min=1.0, range_max=50.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
            'mav_z': RawFieldDef('mav_z', 'Z轴平均绝对值', 'MAV Z',
                physical_unit='g', data_type='float32',
                range_min=0.0, range_max=5.0,
                sample_rate_hz=100.0, source_device='Derived',
                field_category='衍生量'),
        }
        self.operators: Dict[str, OperatorDef] = {
            'w_bz': OperatorDef('w_bz', 'ISO2631 W_b 垂直加权',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='ISO2631-1 垂直方向(W_b)频率加权滤波器'),
            'w_d': OperatorDef('w_d', 'ISO2631 W_d 水平加权',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='ISO2631-1 水平方向(W_d)频率加权滤波器'),
            'rms': OperatorDef('rms', '均方根 RMS',
                category='统计', pipeline_id='basic',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='计算时间序列的均方根值'),
            'peak': OperatorDef('peak', '峰值检测',
                category='统计', pipeline_id='basic',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='检测时间序列的绝对峰值'),
            'vdv': OperatorDef('vdv', '振动剂量值 VDV',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='ISO2631-1 振动剂量值计算'),
            'hic': OperatorDef('hic', '头部损伤准则 HIC15',
                category='冲击', pipeline_id='shock',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='NHTSA头部损伤准则，15ms窗口'),
            'srs': OperatorDef('srs', '冲击响应谱 SRS',
                category='冲击', pipeline_id='shock',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='计算冲击响应谱(最大响应、伪速度)'),
            'fds': OperatorDef('fds', '疲劳损伤谱 FDS',
                category='疲劳', pipeline_id='fatigue',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='Miner线性累积疲劳损伤谱'),
            'rfc': OperatorDef('rfc', '雨流计数 RFC',
                category='疲劳', pipeline_id='fatigue',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=2,
                description='ASTM E1049 雨流循环计数法'),
            'stft': OperatorDef('stft', '短时傅里叶变换 STFT',
                category='时频', pipeline_id='time_frequency',
                input_type='array[float]', output_type='array[complex]',
                input_count=1, output_count=1,
                description='短时傅里叶变换，分析时频特性'),
            'transmissibility': OperatorDef('transmissibility', '传递率 SEAT',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='座椅有效振幅传递率因子'),
            'spine_model': OperatorDef('spine_model', 'ISO2631-5 脊柱模型',
                category='生物力学', pipeline_id='shock',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='ISO2631-5 脊柱压缩应力模型'),
            'psd': OperatorDef('psd', '功率谱密度 PSD',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='Welch法功率谱密度估计'),
            'jerk': OperatorDef('jerk', '加加速度 Jerk',
                category='冲击', pipeline_id='shock',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='加速度时间导数，衡量冲击的瞬变速率'),
            'seat_z': OperatorDef('seat_z', 'SEAT Z传递率',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='ISO2631-1 座椅Z轴有效振幅传递率'),
            'seat_xy': OperatorDef('seat_xy', 'SEAT XY传递率',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='ISO2631-1 座椅XY轴有效振幅传递率'),
            'aw_z': OperatorDef('aw_z', '频率加权加速度Z',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='ISO2631-1 W_b加权垂直加速度均方根'),
            'aw_xy': OperatorDef('aw_xy', '频率加权加速度XY',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='ISO2631-1 W_d加权水平加速度均方根'),
            'ovtv': OperatorDef('ovtv', '总振动值 OVTV',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='ISO2631-1 总体振动总值'),
            'disp_tr': OperatorDef('disp_tr', '位移传递率',
                category='频域', pipeline_id='frequency',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='振动位移传递特性'),
            'r_factor': OperatorDef('r_factor', 'R因子',
                category='时域', pipeline_id='basic',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='VDV与容许值比值，评估舒适度裕量'),
            'skewness': OperatorDef('skewness', '偏度算子',
                category='统计', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='计算时间序列的三阶中心矩偏度'),
            'kurtosis': OperatorDef('kurtosis', '峭度算子',
                category='统计', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='计算时间序列的四阶中心矩峭度'),
            'mav': OperatorDef('mav', '平均绝对值 MAV',
                category='统计', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='计算时间序列的平均绝对幅值'),
            'impulse_factor': OperatorDef('impulse_factor', '脉冲因子',
                category='统计', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='峰值与平均绝对值的比值，检测冲击脉冲'),
            'crest_factor': OperatorDef('crest_factor', '波峰因子',
                category='统计', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=1, output_count=1,
                description='峰值与RMS的比值，衡量信号冲击特征'),
            'band_energy': OperatorDef('band_energy', '频段能量',
                category='频域', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='float',
                input_count=2, output_count=1,
                description='计算指定频段的PSD积分能量'),
            'sliding_window': OperatorDef('sliding_window', '滑动窗口',
                category='时域', pipeline_id='full_timeseries',
                input_type='array[float]', output_type='array[float]',
                input_count=1, output_count=1,
                description='全时域滑动窗口分割与逐窗统计'),
        }
        self.evaluation_modules: Dict[str, EvaluationModuleDef] = {
            'seat_evaluation': EvaluationModuleDef(
                'seat_evaluation', '座椅评测引擎V2',
                display_name_en='Seat Evaluation Engine V2',
                applicable_indicators=(
                    'HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                    'SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'VDV_Z', 'OVTV',
                    'R_FACTOR', 'DISP_TR', 'TR_Z', 'FDS_D', 'FDS_R', 'RFC_CC',
                    'STFT_FC', 'STFT_KT', 'STFT_CE', 'ACC_RMS', 'ACC_PEAK',
                    'DISP_HR', 'S_D',
                ),
                operator_count=12, status='active',
                description='ISO 2631 / ISO 8608 全量座椅评测，涵盖频域、冲击、疲劳、时频和生物力学',
            ),
            'comparative': EvaluationModuleDef(
                'comparative', '对照分析引擎V2',
                display_name_en='Comparative Analysis Engine V2',
                applicable_indicators=(
                    'HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                    'SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'VDV_Z', 'OVTV',
                    'R_FACTOR', 'DISP_TR', 'TR_Z', 'FDS_D', 'FDS_R', 'RFC_CC',
                    'STFT_FC', 'STFT_KT', 'STFT_CE', 'ACC_RMS', 'ACC_PEAK',
                    'DISP_HR', 'S_D',
                ),
                operator_count=12, status='active',
                description='多座椅/多工况横向对比评测，支持A/B位、多方案对照分析',
            ),
            'frequency': EvaluationModuleDef(
                'frequency', '频域分析模块',
                display_name_en='Frequency Domain Analysis',
                applicable_indicators=('SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'VDV_Z', 'OVTV', 'TR_Z'),
                operator_count=3, status='active',
                description='ISO 2631-1 W_b / W_d 频率加权，SEAT传递率，VDV振动剂量值',
            ),
            'shock': EvaluationModuleDef(
                'shock', '冲击分析模块',
                display_name_en='Shock Analysis Module',
                applicable_indicators=('HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV'),
                operator_count=3, status='active',
                description='ISO 2631-5 SRS冲击响应谱，HIC头部损伤准则，ISO 2631-5脊柱模型',
            ),
            'fatigue': EvaluationModuleDef(
                'fatigue', '疲劳分析模块',
                display_name_en='Fatigue Analysis Module',
                applicable_indicators=('FDS_D', 'FDS_R', 'RFC_CC'),
                operator_count=2, status='active',
                description='FDS疲劳损伤谱，雨流计数RFC，累积疲劳评估',
            ),
            'time_frequency': EvaluationModuleDef(
                'time_frequency', '时频分析模块',
                display_name_en='Time-Frequency Analysis Module',
                applicable_indicators=('STFT_FC', 'STFT_KT', 'STFT_CE'),
                operator_count=1, status='active',
                description='STFT短时傅里叶变换，主频中心、频带宽度、频率集中度',
            ),
            'biomechanics': EvaluationModuleDef(
                'biomechanics', '生物力学模块',
                display_name_en='Biomechanics Module',
                applicable_indicators=('S_D',),
                operator_count=1, status='active',
                description='脊柱应力S_D，ISO 2631-5脊柱模型生物力学响应',
            ),
            'full_timeseries_eval': EvaluationModuleDef(
                'full_timeseries_eval', '全时域统计评测引擎',
                display_name_en='Full Timeseries Evaluation Engine',
                applicable_indicators=(
                    'RMS_Ax_E', 'RMS_Ay_E', 'RMS_Az_E', 'RMS_Ax_C', 'RMS_Ay_C', 'RMS_Az_C',
                    'Peak_Ax_E', 'Peak_Ay_E', 'Peak_Az_E', 'Peak_Ax_C', 'Peak_Ay_C', 'Peak_Az_C',
                    'Crest_Ax_E', 'Crest_Ay_E', 'Crest_Az_E', 'Crest_Ax_C', 'Crest_Ay_C', 'Crest_Az_C',
                    'VDV_Ax_E', 'VDV_Ay_E', 'VDV_Az_E', 'VDV_Ax_C', 'VDV_Ay_C', 'VDV_Az_C',
                    'Skew_Ax_E', 'Skew_Ay_E', 'Skew_Az_E', 'Skew_Ax_C', 'Skew_Ay_C', 'Skew_Az_C',
                    'Kurt_Ax_E', 'Kurt_Ay_E', 'Kurt_Az_E', 'Kurt_Ax_C', 'Kurt_Ay_C', 'Kurt_Az_C',
                    'MAV_Ax_E', 'MAV_Ay_E', 'MAV_Az_E', 'MAV_Ax_C', 'MAV_Ay_C', 'MAV_Az_C',
                    'Impf_Ax_E', 'Impf_Ay_E', 'Impf_Az_E', 'Impf_Ax_C', 'Impf_Ay_C', 'Impf_Az_C',
                    'E_total_VDV', 'C_total_VDV',
                ),
                operator_count=11, status='active',
                description='全时域滑动窗口8类统计特征(RMS/Peak/Crest/VDV/Skew/Kurt/MAV/Impulse)×3轴×2组，含胸骨扩展',
            ),
            'dashboard_overview': EvaluationModuleDef(
                'dashboard_overview', '概览仪表盘引擎',
                display_name_en='Dashboard Overview Engine',
                applicable_indicators=(
                    'OVTV_DASHBOARD', 'DOM_BAND', 'CF_Z', 'LOCATION_COUNT',
                    'ISO_REF_ZONE', 'DURATION', 'BEHAVIOR_EVENT_COUNT', 'BEHAVIOR_EVENT_TYPES',
                ),
                operator_count=3, status='active',
                description='全量统计分析概览仪表盘，含OVTV/主导频带/冲击因数/ISO参考区等8项关键指标',
            ),
        }
        self.standard_references = STANDARD_REFERENCES

    def _register_full_timeseries_indicators(self):
        features = ['RMS', 'Peak', 'Crest', 'VDV', 'Skew', 'Kurt', 'MAV', 'Impf']
        axes = ['Ax', 'Ay', 'Az']
        groups = [
            ('E', '实验组', '全时域统计'),
            ('C', '对照组', '全时域统计'),
            ('S', '胸骨', '全时域统计'),
        ]
        for group_code, group_cn, dim in groups:
            for feat in features:
                for axis in axes:
                    code = f'{feat}_{axis}_{group_code}'
                    name = f'{group_cn} {axis}-{feat}'
                    self.indicators[code] = IndicatorDef(
                        code, name,
                        unit='', evaluation_dimension=dim,
                        direction=EvaluationDirection.LOWER_IS_BETTER,
                    )
        self.indicators['E_total_VDV'] = IndicatorDef(
            'E_total_VDV', '实验组总VDV',
            unit='m/s^1.75', evaluation_dimension='全时域统计',
            direction=EvaluationDirection.LOWER_IS_BETTER,
        )
        self.indicators['C_total_VDV'] = IndicatorDef(
            'C_total_VDV', '对照组总VDV',
            unit='m/s^1.75', evaluation_dimension='全时域统计',
            direction=EvaluationDirection.LOWER_IS_BETTER,
        )

    def _register_dashboard_indicators(self):
        dashboards = [
            ('OVTV_DASHBOARD', '总振动值 OVTV(g)', 'g'),
            ('DOM_BAND', '主导频带', 'Hz'),
            ('CF_Z', '冲击因数 CF(Z)', ''),
            ('LOCATION_COUNT', '位置数', '个'),
            ('ISO_REF_ZONE', 'ISO参考区', ''),
            ('DURATION', '分析时长', 's'),
            ('BEHAVIOR_EVENT_COUNT', '驾驶行为事件数', '次'),
            ('BEHAVIOR_EVENT_TYPES', '事件类型覆盖', '种'),
        ]
        for code, name, unit in dashboards:
            self.indicators[code] = IndicatorDef(
                code, name,
                unit=unit, evaluation_dimension='概览仪表盘',
                direction=EvaluationDirection.CENTER_IS_BETTER,
            )

    def _register_band_attenuation_indicators(self):
        bands = [
            ('BAND_ATT_01_05', '超低频段衰减率(0.1-0.5Hz)'),
            ('BAND_ATT_05_1', '低频段衰减率(0.5-1Hz)'),
            ('BAND_ATT_1_5', '中频段衰减率(1-5Hz)'),
            ('BAND_ATT_5_20', '高频段衰减率(5-20Hz)'),
            ('BAND_ATT_20_80', '超高频段衰减率(20-80Hz)'),
        ]
        for code, name in bands:
            self.indicators[code] = IndicatorDef(
                code, name,
                unit='%', evaluation_dimension='频段衰减',
                direction=EvaluationDirection.HIGHER_IS_BETTER,
            )

    def generate_result_schema(self) -> Dict[str, Any]:
        def _serialize(obj):
            if isinstance(obj, enum.Enum):
                return obj.name
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj, dict_factory=lambda fields: {k: _serialize(v) for k, v in fields})
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_serialize(v) for v in obj]
            return obj
        return {
            'indicators': [_serialize(ind) for ind in self.indicators.values()],
            'thresholds': self.metric_thresholds_4level,
            'diagnosis': self.diagnosis_thresholds,
            'fixed_parameters': FIXED_PARAMETERS,
        }

    def get_4level_grade(self, indicator_code: str, value: float) -> str:
        thresholds = self.metric_thresholds_4level.get(indicator_code, {})
        if not thresholds:
            return ''
        direction = self.indicators.get(indicator_code, IndicatorDef(indicator_code, indicator_code)).direction
        if direction == EvaluationDirection.LOWER_IS_BETTER:
            if value <= thresholds.get('excellent', float('inf')):
                return 'A-优秀'
            if value <= thresholds.get('good', float('inf')):
                return 'B-良好'
            if value <= thresholds.get('fair', float('inf')):
                return 'C-一般'
            return 'D-差'
        elif direction == EvaluationDirection.HIGHER_IS_BETTER:
            if value >= thresholds.get('excellent', float('-inf')):
                return 'A-优秀'
            if value >= thresholds.get('good', float('-inf')):
                return 'B-良好'
            if value >= thresholds.get('fair', float('-inf')):
                return 'C-一般'
            return 'D-差'
        else:
            center = thresholds.get('excellent', 0)
            if abs(value - center) <= abs(thresholds.get('good', center * 2)):
                return 'A-优秀'
            if abs(value - center) <= abs(thresholds.get('fair', center * 3)):
                return 'B-良好'
            return 'C-一般'

    def get_driving_state_cn_label(self, state_name: str) -> str:
        return self.driving_states.get(state_name, state_name)

    def validate_field_value(self, field_code: str, value) -> Tuple[bool, str]:
        field = self.raw_fields.get(field_code) or self.derived_fields.get(field_code)
        if field is None:
            return False, f"未注册字段: {field_code}"
        if value is None:
            return True, ""
        try:
            f_val = float(value)
            if f_val < field.range_min:
                return False, f"{field_code}={f_val:.2f} 低于下限 {field.range_min}{field.physical_unit}"
            if f_val > field.range_max:
                return False, f"{field_code}={f_val:.2f} 超出上限 {field.range_max}{field.physical_unit}"
        except (ValueError, TypeError):
            return False, f"{field_code}={value} 类型不匹配，期望 {field.data_type}"
        return True, ""

    def validate_indicator_code(self, code: str) -> bool:
        return code in self.indicators

    def validate_raw_data_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        violations = []
        for field_code, value in record.items():
            ok, msg = self.validate_field_value(field_code, value)
            if not ok:
                violations.append({
                    'field': field_code, 'value': value,
                    'message': msg, 'severity': 'error',
                })
        return {
            'total_fields': len(record),
            'violations': violations,
            'valid': len(violations) == 0,
        }

    def validate_operator_input(self, op_code: str, input_count: int) -> Tuple[bool, str]:
        op = self.operators.get(op_code)
        if op is None:
            return False, f"未注册算子: {op_code}"
        if input_count < op.input_count:
            return False, f"算子 {op_code} 需要至少 {op.input_count} 个输入，当前 {input_count}"
        return True, ""

    def get_indicator_definition(self, code: str) -> Dict[str, str]:
        return INDICATOR_DEFINITIONS.get(code, {})

    def get_indicator_meta(self, code: str):
        return self.indicators.get(code)

    def get_indicator_detail(self, code: str) -> Dict[str, Any]:
        return self.indicator_details.get(code, {})

    def get_threshold(self, code: str) -> dict:
        return self.diagnosis_thresholds.get(code, {})

    def get_metric_thresholds(self, code: str) -> Dict[str, float]:
        return self.metric_thresholds_4level.get(code, {})

    def get_diagnosis_thresholds(self, code: str) -> Dict[str, float]:
        return self.diagnosis_thresholds.get(code, {})

    def get_standard_reference(self, code: str) -> Dict[str, str]:
        return self.standard_references.get(code, {})

    def get_diagnosis_state_icon(self, state: str) -> str:
        return DIAGNOSIS_STATE_ICONS.get(state, '—')

    def get_fixed_parameter(self, name: str) -> float:
        return FIXED_PARAMETERS.get(name, 0.0)

    def get_comparison_dimension(self, dim_id: str) -> Dict[str, Any]:
        return COMPARISON_DIMENSIONS.get(dim_id, {})

    @property
    def indicator_definitions(self) -> Dict[str, Dict[str, str]]:
        return INDICATOR_DEFINITIONS

    @property
    def fixed_parameters(self) -> Dict[str, float]:
        return FIXED_PARAMETERS

    @property
    def four_level_grades(self) -> Dict[str, str]:
        return FOUR_LEVEL_GRADES

    @property
    def diagnosis_state_icons(self) -> Dict[str, str]:
        return DIAGNOSIS_STATE_ICONS

    @property
    def comparison_dimensions(self) -> Dict[str, Any]:
        return COMPARISON_DIMENSIONS


_global_registry: Optional[MetadataRegistry] = None


# ═══════════════════════════════════════════════════════════
#  事件-指标自动映射表 (F1: 补全25种事件→最优指标组合)
# ═══════════════════════════════════════════════════════════
EVENT_TO_EVALUATION_MAP = {
    # ── 纵向事件 (5种) ──
    'emergency_braking': {
        'priority': 0,
        'category': 'longitudinal',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                     'SEAT_Z', 'VDV_Z', 'AW_Z', 'DISP_HR', 'OVTV'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'aggressive_acceleration': {
        'priority': 0,
        'category': 'longitudinal',
        'metrics': ['SEAT_XY', 'VDV_Z', 'AW_Z', 'AW_XY', 'R_FACTOR',
                     'DISP_TR', 'ACC_RMS', 'ACC_PEAK'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'sudden_deceleration': {
        'priority': 1,
        'category': 'longitudinal',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS',
                     'SEAT_Z', 'VDV_Z', 'AW_Z', 'DISP_HR'],
        'window': {'pre': 0.3, 'post': 1.0},
    },
    'rapid_speed_change': {
        'priority': 2,
        'category': 'longitudinal',
        'metrics': ['SEAT_XY', 'VDV_Z', 'AW_XY', 'ACC_RMS', 'ACC_PEAK'],
        'window': {'pre': 0.3, 'post': 1.0},
    },
    'speed_fluctuation': {
        'priority': 3,
        'category': 'longitudinal',
        'metrics': ['AW_Z', 'ACC_RMS', 'OVTV', 'R_FACTOR'],
        'window': {'pre': 0.5, 'post': 1.0},
    },

    # ── 侧向事件 (5种) ──
    'sharp_turn': {
        'priority': 0,
        'category': 'lateral',
        'metrics': ['SEAT_XY', 'AW_XY', 'R_FACTOR', 'ACC_RMS', 'ACC_PEAK',
                     'DISP_TR', 'SRS_MRS', 'SRS_PV'],
        'window': {'pre': 0.3, 'post': 1.0},
    },
    'lane_change': {
        'priority': 1,
        'category': 'lateral',
        'metrics': ['SEAT_XY', 'AW_XY', 'R_FACTOR', 'ACC_RMS', 'ACC_PEAK'],
        'window': {'pre': 0.3, 'post': 1.0},
    },
    'slalom': {
        'priority': 1,
        'category': 'lateral',
        'metrics': ['SEAT_XY', 'AW_XY', 'R_FACTOR', 'STFT_FC', 'STFT_KT', 'STFT_CE'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'lateral_jerk': {
        'priority': 2,
        'category': 'lateral',
        'metrics': ['JERK_H', 'SEAT_XY', 'ACC_RMS', 'ACC_PEAK'],
        'window': {'pre': 0.2, 'post': 0.5},
    },
    'side_slip': {
        'priority': 2,
        'category': 'lateral',
        'metrics': ['SEAT_XY', 'AW_XY', 'R_FACTOR', 'ACC_RMS'],
        'window': {'pre': 0.3, 'post': 1.0},
    },

    # ── 复合事件 (5种) ──
    'combined_braking_turn': {
        'priority': 0,
        'category': 'compound',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                     'SEAT_Z', 'SEAT_XY', 'VDV_Z', 'AW_Z', 'AW_XY',
                     'DISP_HR', 'OVTV', 'R_FACTOR'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'evasive_maneuver': {
        'priority': 0,
        'category': 'compound',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                     'SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_HR', 'OVTV'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'acceleration_with_turn': {
        'priority': 1,
        'category': 'compound',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'VDV_Z', 'AW_Z', 'AW_XY',
                     'DISP_HR', 'OVTV', 'R_FACTOR'],
        'window': {'pre': 0.3, 'post': 1.0},
    },
    'braking_with_steering': {
        'priority': 1,
        'category': 'compound',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS',
                     'SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_HR'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'multi_axis_vibration': {
        'priority': 2,
        'category': 'compound',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'VDV_Z', 'AW_Z', 'AW_XY',
                     'OVTV', 'R_FACTOR', 'STFT_FC', 'STFT_KT', 'STFT_CE'],
        'window': {'pre': 0.5, 'post': 1.5},
    },

    # ── 异常事件 (5种) ──
    'impact_event': {
        'priority': 0,
        'category': 'anomaly',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                     'SRS_Q', 'SRS_ATT', 'S_D', 'DISP_HR', 'ACC_PEAK'],
        'window': {'pre': 0.1, 'post': 0.5},
    },
    'vibration_spike': {
        'priority': 1,
        'category': 'anomaly',
        'metrics': ['SRS_MRS', 'SRS_PV', 'ACC_PEAK', 'JERK_H', 'VDV_Z'],
        'window': {'pre': 0.2, 'post': 0.5},
    },
    'sensor_anomaly': {
        'priority': 2,
        'category': 'anomaly',
        'metrics': ['ACC_RMS', 'ACC_PEAK', 'STFT_FC', 'STFT_KT', 'STFT_CE'],
        'window': {'pre': 0.1, 'post': 0.3},
    },
    'data_gap': {
        'priority': 3,
        'category': 'anomaly',
        'metrics': ['ACC_RMS', 'ACC_PEAK'],
        'window': {'pre': 0.1, 'post': 0.3},
    },
    'signal_saturation': {
        'priority': 3,
        'category': 'anomaly',
        'metrics': ['ACC_PEAK', 'STFT_FC', 'STFT_KT'],
        'window': {'pre': 0.1, 'post': 0.3},
    },

    # ── 状态事件 (5种) ──
    'steady_state': {
        'priority': 2,
        'category': 'state',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'VDV_Z',
                     'ACC_RMS', 'OVTV', 'R_FACTOR', 'FDS_D', 'FDS_R', 'RFC_CC'],
        'window': {'pre': 1.0, 'post': 2.0},
    },
    'idle_vibration': {
        'priority': 2,
        'category': 'state',
        'metrics': ['SEAT_Z', 'AW_Z', 'VDV_Z', 'OVTV', 'STFT_FC', 'STFT_KT', 'STFT_CE'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'cruise_condition': {
        'priority': 2,
        'category': 'state',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'VDV_Z',
                     'ACC_RMS', 'OVTV', 'R_FACTOR'],
        'window': {'pre': 1.0, 'post': 2.0},
    },
    'road_roughness_response': {
        'priority': 1,
        'category': 'state',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'VDV_Z', 'AW_Z', 'AW_XY',
                     'OVTV', 'R_FACTOR', 'DISP_TR', 'SRS_MRS', 'SRS_PV'],
        'window': {'pre': 0.5, 'post': 1.5},
    },
    'periodic_excitation': {
        'priority': 2,
        'category': 'state',
        'metrics': ['SEAT_Z', 'AW_Z', 'VDV_Z', 'OVTV', 'STFT_FC', 'STFT_KT',
                     'STFT_CE', 'FDS_D', 'FDS_R', 'RFC_CC'],
        'window': {'pre': 1.0, 'post': 2.0},
    },
}


def get_metrics_for_event(event_type: str) -> List[str]:
    """获取事件类型对应的最优指标组合

    Args:
        event_type: 事件类型 (如 'emergency_braking')

    Returns:
        指标ID列表
    """
    event_config = EVENT_TO_EVALUATION_MAP.get(event_type, {})
    return event_config.get('metrics', [])


def get_event_window(event_type: str) -> Dict[str, float]:
    """获取事件类型对应的数据窗口配置

    Args:
        event_type: 事件类型

    Returns:
        {'pre': float, 'post': float}
    """
    event_config = EVENT_TO_EVALUATION_MAP.get(event_type, {})
    return event_config.get('window', {'pre': 0.5, 'post': 1.5})


def get_event_priority(event_type: str) -> int:
    """获取事件优先级 (0=P0最高, 3=P3最低)

    Args:
        event_type: 事件类型

    Returns:
        优先级 0-3
    """
    event_config = EVENT_TO_EVALUATION_MAP.get(event_type, {})
    return event_config.get('priority', 3)


def get_events_by_category(category: str) -> List[str]:
    """获取指定类别下的所有事件类型

    Args:
        category: 事件类别 ('longitudinal', 'lateral', 'compound', 'anomaly', 'state')

    Returns:
        事件类型列表
    """
    return [event_type for event_type, config in EVENT_TO_EVALUATION_MAP.items()
            if config.get('category') == category]


def get_all_event_types() -> List[str]:
    """获取所有25种事件类型"""
    return list(EVENT_TO_EVALUATION_MAP.keys())


def get_event_categories() -> List[str]:
    """获取所有事件类别"""
    return ['longitudinal', 'lateral', 'compound', 'anomaly', 'state']


# ═══════════════════════════════════════════════════════════
#  采样率自适应阈值 (DQ3)
# ═══════════════════════════════════════════════════════════

def sr_adaptive_threshold(base_threshold: float, sample_rate: float,
                           base_sr: float = 100.0,
                           metric_id: str = '') -> float:
    """采样率自适应阈值调整 (DQ3)

    sr=100 和 sr=1000 共用同一阈值不合理，本函数根据采样率自动调整阈值。
    低采样率→放宽阈值（避免误报），高采样率→收紧阈值（更高的检测精度）。

    Args:
        base_threshold: 基准阈值 (在 base_sr 采样率下)
        sample_rate: 实际采样率 [Hz]
        base_sr: 基准采样率 [Hz] (默认100Hz)
        metric_id: 指标ID (可选，用于指标特定调整)

    Returns:
        调整后的阈值
    """
    if sample_rate <= 0:
        return base_threshold

    ratio = sample_rate / base_sr

    # RMS类指标: sr越高→峰值检测越精准→阈值应略收紧
    if 'RMS' in metric_id:
        factor = max(0.8, min(1.2, 1.0 / np.sqrt(ratio)))
    # 冲击类指标 (Peak, Crest, Impf): sr越高→峰值捕获越准→阈值应收紧
    elif any(k in metric_id for k in ['Peak', 'Crest', 'Impf']):
        factor = max(0.75, min(1.3, 0.9 + 0.1 / ratio))
    # VDV/功率类: 与sr平方根相关
    elif any(k in metric_id for k in ['VDV', 'AW']):
        factor = max(0.85, min(1.15, np.power(ratio, 0.1)))
    # 默认: 微调
    else:
        factor = max(0.85, min(1.15, 1.0))

    return base_threshold * factor


# ═══════════════════════════════════════════════════════════
#  置信度传播辅助函数 (F2)
# ═══════════════════════════════════════════════════════════

def propagate_confidence(event_confidence: float, metric_quality: float = 1.0,
                          data_quality: float = 1.0) -> Dict[str, float]:
    """置信度传播链: 事件检测→指标计算→评分不确定性 (F2)

    Args:
        event_confidence: 事件检测置信度 [0, 1]
        metric_quality: 指标计算质量 [0, 1] (如 coherence)
        data_quality: 数据质量评分 [0, 1]

    Returns:
        {'overall_confidence': float, 'level': str, 'uncertainty_band': str}
    """
    overall = event_confidence * metric_quality * data_quality
    overall = max(0.0, min(1.0, overall))

    if overall >= 0.95:
        level = 'high'
        band = '±5%'
    elif overall >= 0.85:
        level = 'medium'
        band = '±15%'
    elif overall >= 0.70:
        level = 'low'
        band = '±30%'
    else:
        level = 'unreliable'
        band = '>±30%'

    return {
        'overall_confidence': round(overall, 4),
        'level': level,
        'uncertainty_band': band,
        'components': {
            'event_confidence': event_confidence,
            'metric_quality': metric_quality,
            'data_quality': data_quality
        }
    }


def get_global_registry() -> MetadataRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = MetadataRegistry()
    return _global_registry


COMPARISON_DIMENSIONS = [
    {
        'id': 'isolation',
        'name': '隔振能力',
        'description': '座椅系统对振动的衰减/放大效应',
        'color': '#4A90D9',
        'metrics': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'DISP_TR', 'TR_Z', 'ACC_RMS', 'ACC_PEAK', 'OVTV', 'R_FACTOR'],
    },
    {
        'id': 'head_safety',
        'name': '终端安全',
        'description': '乘员头部冲击风险与损伤概率',
        'color': '#E74C3C',
        'metrics': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT'],
    },
    {
        'id': 'fatigue',
        'name': '累积疲劳',
        'description': '长期振动暴露引起的疲劳损伤累积',
        'color': '#F39C12',
        'metrics': ['FDS_D', 'FDS_R', 'RFC_CC', 'VDV_Z'],
    },
    {
        'id': 'time_frequency',
        'name': '时频分析',
        'description': '振动的频率分布与能量集中度',
        'color': '#9B59B6',
        'metrics': ['STFT_FC', 'STFT_KT', 'STFT_CE'],
    },
    {
        'id': 'full_timeseries',
        'name': '全时域统计',
        'description': '全时域滑动窗口统计特征(RMS/Peak/Crest/VDV/Skew/Kurt/MAV/Impulse)',
        'color': '#1ABC9C',
        'metrics': [
            'RMS_Ax_E', 'RMS_Ay_E', 'RMS_Az_E', 'RMS_Ax_C', 'RMS_Ay_C', 'RMS_Az_C',
            'Peak_Ax_E', 'Peak_Ay_E', 'Peak_Az_E', 'Peak_Ax_C', 'Peak_Ay_C', 'Peak_Az_C',
            'Crest_Ax_E', 'Crest_Ay_E', 'Crest_Az_E', 'Crest_Ax_C', 'Crest_Ay_C', 'Crest_Az_C',
            'VDV_Ax_E', 'VDV_Ay_E', 'VDV_Az_E', 'VDV_Ax_C', 'VDV_Ay_C', 'VDV_Az_C',
            'E_total_VDV', 'C_total_VDV',
        ],
    },
    {
        'id': 'band_attenuation',
        'name': '频段衰减',
        'description': '各频段(0.1-80Hz)的振动能量衰减率',
        'color': '#E67E22',
        'metrics': ['BAND_ATT_01_05', 'BAND_ATT_05_1', 'BAND_ATT_1_5', 'BAND_ATT_5_20', 'BAND_ATT_20_80'],
    },
]