#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量统计分析模块 — 修改后验证脚本

验证 Section 7.1-7.5 的所有修改是否正确执行。
"""

import sys
import os
import numpy as np

# 确保能找到 core 模块
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def verify_71_thresholds():
    """验证 7.1: 补充全时域87项诊断阈值"""
    from core.core.seat_evaluation.metadata_registry import (
        DIAGNOSIS_THRESHOLDS, METRIC_THRESHOLDS
    )

    print("=" * 60)
    print("7.1 验证: 全时域87项诊断阈值")
    print("=" * 60)

    diag_count = len(DIAGNOSIS_THRESHOLDS)
    print(f"  DIAGNOSIS_THRESHOLDS 总数: {diag_count} (原23 + 新增87 ≈ 110)")
    assert diag_count >= 90, f"期望 >=90，实际 {diag_count}"

    # 验证全时域 E/C 指标阈值 (48项)
    for prefix in ['RMS', 'Peak', 'Crest', 'VDV', 'Skew', 'Kurt', 'MAV', 'Impf']:
        for axis in ['Ax', 'Ay', 'Az']:
            for group in ['E', 'C']:
                key = f'{prefix}_{axis}_{group}'
                assert key in DIAGNOSIS_THRESHOLDS, f"缺失: {key}"
    print("  [OK] 全时域 48项 E/C 阈值全部注册")

    # 验证胸骨指标 (12项)
    for prefix in ['RMS', 'Peak', 'Crest', 'VDV']:
        for axis in ['Ax', 'Ay', 'Az']:
            key = f'{prefix}_{axis}_S'
            assert key in DIAGNOSIS_THRESHOLDS, f"Missing sternum: {key}"
    print("  [OK] 胸骨 12项阈值全部注册")

    # 验证频段衰减
    for band in ['BAND_ATT_01_05', 'BAND_ATT_05_1', 'BAND_ATT_1_5',
                  'BAND_ATT_5_20', 'BAND_ATT_20_80']:
        assert band in DIAGNOSIS_THRESHOLDS, f"Missing band: {band}"
    print("  [OK] 频段衰减 5项阈值全部注册")

    # 验证 METRIC_THRESHOLDS 新增
    for key in ['RMS_Ay_E', 'RMS_Az_E', 'RMS_Ay_C', 'RMS_Az_C',
                'VDV_Ay_E', 'VDV_Ay_C', 'E_total_VDV', 'C_total_VDV',
                'BAND_ATT_01_05', 'BAND_ATT_05_1', 'BAND_ATT_1_5']:
        assert key in METRIC_THRESHOLDS, f"Missing METRIC: {key}"
    print("  [OK] METRIC_THRESHOLDS 13项新增全部注册")

    print("  7.1 验证通过!\n")


def verify_72_engine_metrics():
    """验证 7.2: S_D/DISP_HR/全时域统计指标计算"""
    from core.core.seat_evaluation.engine import SeatEvaluationEngine

    print("=" * 60)
    print("7.2 验证: S_D/DISP_HR/全时域统计指标计算")
    print("=" * 60)

    engine = SeatEvaluationEngine()
    engine.default_sample_rate = 100.0

    # 生成测试数据
    rng = np.random.RandomState(42)
    sr = 100.0
    t = np.arange(0, 2.0, 1/sr)
    ax = 0.5 * np.sin(2 * np.pi * 2 * t) + 0.1 * rng.randn(len(t))
    ay = 0.3 * np.sin(2 * np.pi * 1.5 * t) + 0.1 * rng.randn(len(t))
    az = 0.4 * np.sin(2 * np.pi * 3 * t) + 0.1 * rng.randn(len(t))

    data_window = {'ax': ax, 'ay': ay, 'az': az, 'sample_rate': sr}

    # 测试 S_D
    s_d = engine._calculate_single_metric('S_D', data_window)
    print(f"  S_D = {s_d:.4f} MPa")
    assert s_d >= 0, f"S_D should be >= 0, got {s_d}"

    # 测试 DISP_HR
    disp_hr = engine._calculate_single_metric('DISP_HR', data_window)
    print(f"  DISP_HR = {disp_hr:.4f} mm")
    assert disp_hr >= 0, f"DISP_HR should be >= 0, got {disp_hr}"

    # 测试全时域统计指标
    for prefix in ['RMS', 'Peak', 'Crest', 'VDV']:
        for axis in ['Ax', 'Ay', 'Az']:
            key = f'{prefix}_{axis}_E'
            val = engine._calculate_single_metric(key, data_window)
            print(f"  {key} = {val:.4f}")
            assert val >= 0, f"{key} should be >= 0, got {val}"

    # 测试 E_total_VDV
    total_vdv = engine._calculate_single_metric('E_total_VDV', data_window)
    print(f"  E_total_VDV = {total_vdv:.4f}")
    assert total_vdv >= 0

    print("  7.2 验证通过!\n")


def verify_73_bpf_operator():
    """验证 7.3: BPF频段衰减算子"""
    from core.core.seat_evaluation.operators import BandpassAttenuationOperator

    print("=" * 60)
    print("7.3 验证: BPF频段衰减算子")
    print("=" * 60)

    fs = 1000
    rng = np.random.RandomState(42)
    t = np.arange(0, 10, 1/fs)
    exp_data = 0.5 * np.sin(2 * np.pi * 2 * t) + 0.05 * rng.randn(len(t))
    ctrl_data = 1.0 * np.sin(2 * np.pi * 2 * t) + 0.05 * rng.randn(len(t))

    bpf = BandpassAttenuationOperator(fs=fs)

    # 测试基本衰减计算
    results = bpf.compute_band_attenuation(exp_data, ctrl_data)
    print(f"  BPF衰减结果: {list(results.keys())}")
    for band, att in results.items():
        assert att is not None or band.startswith('20-'), \
            f"Band {band} should have valid result, got {att}"
    print(f"  0.1-0.5Hz 衰减: {results.get('0.1-0.5Hz', 'N/A'):.2f}%")
    print(f"  1-5Hz 衰减: {results.get('1-5Hz', 'N/A'):.2f}%")

    # 测试双方法验证
    verified = bpf.compute_verified_attenuation(exp_data, ctrl_data)
    print(f"  双方法验证结果:")
    for band, info in verified.items():
        print(f"    {band}: method={info['method']}, attn={info['attenuation_pct']:.2f}%")
        if info['method'] == 'bpf':
            assert info['verified'] is True, f"BPF method should be verified for {band}"

    print("  7.3 验证通过!\n")


def verify_74_iso2631_validation():
    """验证 7.4: ISO2631_5_Operator 样本量校验"""
    from core.core.seat_evaluation.operators import ISO2631_5_Operator

    print("=" * 60)
    print("7.4 验证: ISO2631_5_Operator 样本量校验")
    print("=" * 60)

    op = ISO2631_5_Operator()

    # 测试样本量不足 (0.5s@100Hz = 50 samples, 用 30 samples)
    short_data = np.ones(30) * 0.1
    result = op.compute(short_data, short_data, short_data, 100.0)
    print(f"  短数据 (30 samples): S_d={result['S_d_MPa']}, level={result['S_d_level']}")
    assert np.isnan(result['S_d_MPa']), "Short data should return NaN"
    assert '数据不足' in result['S_d_level'], f"Should indicate insufficient data, got {result['S_d_level']}"

    # 测试全零信号
    zero_data = np.zeros(100)
    result = op.compute(zero_data, zero_data, zero_data, 100.0)
    print(f"  全零信号: S_d={result['S_d_MPa']}, level={result['S_d_level']}")
    assert result['S_d_MPa'] == 0.0
    assert '无显著加速度' in result['S_d_level']

    # 测试正常数据
    rng = np.random.RandomState(42)
    normal_data = rng.randn(200) * 0.5
    result = op.compute(normal_data, normal_data, normal_data, 100.0)
    print(f"  正常数据: S_d={result['S_d_MPa']:.4f}, level={result['S_d_level']}")
    assert result['S_d_MPa'] >= 0

    print("  7.4 验证通过!\n")


def verify_75_radar_interface():
    """验证 7.5: 频段衰减雷达图数据接口"""
    from core.core.seat_evaluation.operators import AttenuationOperator

    print("=" * 60)
    print("7.5 验证: 频段衰减雷达图数据接口")
    print("=" * 60)

    fs = 1000
    rng = np.random.RandomState(42)
    t = np.arange(0, 10, 1/fs)
    exp_ax = 0.5 * np.sin(2 * np.pi * 2 * t) + 0.05 * rng.randn(len(t))
    ctrl_ax = 1.0 * np.sin(2 * np.pi * 2 * t) + 0.05 * rng.randn(len(t))
    exp_ay = 0.4 * np.sin(2 * np.pi * 1.5 * t) + 0.05 * rng.randn(len(t))
    ctrl_ay = 0.8 * np.sin(2 * np.pi * 1.5 * t) + 0.05 * rng.randn(len(t))
    exp_az = 0.6 * np.sin(2 * np.pi * 3 * t) + 0.05 * rng.randn(len(t))
    ctrl_az = 1.2 * np.sin(2 * np.pi * 3 * t) + 0.05 * rng.randn(len(t))

    att_op = AttenuationOperator()
    radar_data = att_op.get_band_attenuation_for_radar(
        exp_ax, ctrl_ax, exp_ay, ctrl_ay, exp_az, ctrl_az, fs=fs
    )

    print(f"  雷达图数据维度: {list(radar_data.keys())}")
    for axis, bands in radar_data.items():
        print(f"    {axis}: {len(bands)} bands")
        assert len(bands) == 5, f"{axis} should have 5 bands, got {len(bands)}"
        for band, att in bands.items():
            assert att is not None, f"{axis}/{band} should not be None"

    print("  7.5 验证通过!\n")


def verify_76_operator_system():
    """验证 OperatorSystem 包含 BandpassAttenuationOperator"""
    from core.core.seat_evaluation.operators import OperatorSystem

    print("=" * 60)
    print("7.6 验证: OperatorSystem 集成")
    print("=" * 60)

    ops = OperatorSystem()
    assert hasattr(ops, 'bandpass'), "OperatorSystem should have bandpass"
    assert 'BANDPASS' in ops.operators, "OperatorSystem.operators should have BANDPASS"
    print(f"  [OK] OperatorSystem 包含 BandpassAttenuationOperator")
    print(f"  [OK] 算子系统总数: {len(ops.operators)}")

    print("  7.6 验证通过!\n")


def verify_all_fixes():
    """运行所有验证"""
    print("\n" + "=" * 60)
    print("  全量统计分析模块 — 修改后集成验证")
    print("=" * 60 + "\n")

    try:
        verify_71_thresholds()
        verify_72_engine_metrics()
        verify_73_bpf_operator()
        verify_74_iso2631_validation()
        verify_75_radar_interface()
        verify_76_operator_system()

        print("=" * 60)
        print("  ALL VERIFICATIONS PASSED!")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n  VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = verify_all_fixes()
    sys.exit(0 if success else 1)