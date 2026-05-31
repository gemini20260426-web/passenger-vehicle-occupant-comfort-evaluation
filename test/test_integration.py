#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端集成测试 — pytest + CSV 回放

评审报告 AR-7: 缺少端到端集成测试
覆盖: StreamingDetector, MetricComputer, MultiChannelSeatEvaluationEngine

运行方式:
    pytest test/test_integration.py -v
    pytest test/test_integration.py -v -k "test_metric"  # 只运行指标测试
"""

import os
import sys
import csv
import time
import numpy as np
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'main'))
os.chdir(str(project_root))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestCSVDataLoader:
    """CSV数据加载器 — 回放测试数据"""

    @staticmethod
    def load(rel_path: str):
        csv_path = project_root / rel_path
        if not csv_path.exists():
            raise FileNotFoundError(f"测试数据文件不存在: {csv_path}")
        timestamps, ax, ay, az, gx, gy, gz = [], [], [], [], [], [], []
        speeds, steering, labels = [], [], []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamps.append(float(row['timestamp']))
                ax.append(float(row['ax']))
                ay.append(float(row['ay']))
                az.append(float(row['az']))
                gx.append(float(row['gx']))
                gy.append(float(row['gy']))
                gz.append(float(row['gz']))
                speeds.append(float(row['speed_kmh']))
                steering.append(float(row['steering_deg']))
                labels.append(row['event_label'])
        return {
            'timestamps': np.array(timestamps),
            'ax': np.array(ax), 'ay': np.array(ay), 'az': np.array(az),
            'gx': np.array(gx), 'gy': np.array(gy), 'gz': np.array(gz),
            'speed_kmh': np.array(speeds),
            'steering_deg': np.array(steering),
            'event_labels': labels,
            'sample_rate': 100.0,
        }


class TestStreamingDetector:
    """AR-3 验证: StreamingDetector 流式处理"""

    def test_streaming_detector_basic(self):
        from core.core.analysis.streaming_detector import StreamingDetector, StreamingConfig, StreamingStats
        config = StreamingConfig(ring_max=64, processing_interval=0.05)
        detector = StreamingDetector(config)
        detector.start()
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        timestamps = data['timestamps']
        speeds = data['speed_kmh']
        for i in range(len(timestamps)):
            stats = detector.ingest(timestamps[i], speed_kmh=speeds[i])
            if i > 0:
                assert isinstance(stats, StreamingStats)
                assert stats.buffer_usage > 0
        final_stats = detector.get_stats()
        assert final_stats.frame_count == len(timestamps)
        assert final_stats.peak_accel > 0, "应检测到车辆加速度"
        assert final_stats.vdv_cumulative >= 0, "VDV应为非负值"
        assert final_stats.buffer_usage <= config.ring_max
        detector.stop()
        print(f"  [OK] StreamingDetector: {final_stats.frame_count}帧, "
              f"peak={final_stats.peak_accel:.3f}, VDV={final_stats.vdv_cumulative:.3f}")

    def test_streaming_detector_reset(self):
        from core.core.analysis.streaming_detector import StreamingDetector, StreamingConfig
        detector = StreamingDetector(StreamingConfig(ring_max=32))
        detector.start()
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        for i in range(50):
            detector.ingest(data['timestamps'][i], speed_kmh=data['speed_kmh'][i])
        before = detector.get_stats()
        detector.reset()
        after = detector.get_stats()
        assert after.frame_count == 0
        assert after.vdv_cumulative == 0.0
        assert after.peak_accel == 0.0
        assert not after.is_active
        print(f"  [OK] StreamingDetector.reset: {before.frame_count}→{after.frame_count}")

    def test_ring_buffer_correctness(self):
        from core.core.analysis.streaming_detector import RingBuffer
        buf = RingBuffer(capacity=8, n_channels=2)
        for i in range(12):
            buf.write(float(i), float(i * 10))
        t, v = buf.slice()
        assert len(t) == 8
        assert t[0] == 4.0, f"最旧数据应为4, 实际{t[0]}"
        assert t[-1] == 11.0, f"最新数据应为11, 实际{t[-1]}"
        assert v[-1] == 110.0
        print(f"  [OK] RingBuffer: 8/8容量, 最旧={t[0]}, 最新={t[-1]}")


class TestMetricComputer:
    """AR-5 验证: MetricComputer 统一指标计算"""

    def test_metric_computer_all_metrics(self):
        from core.core.seat_evaluation.operators import OperatorSystem
        from core.core.seat_evaluation.metric_computer import (
            MetricComputer, MetricComputeContext, METRIC_INSUFFICIENT_DATA
        )
        ops = OperatorSystem()
        computer = MetricComputer(ops)
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        ctx = MetricComputeContext(
            ax=data['ax'], ay=data['ay'], az=data['az'],
            sample_rate=data['sample_rate'],
            gx=data['gx'], gy=data['gy'], gz=data['gz'],
        )
        metrics = ['AW_Z', 'AW_XY', 'VDV_Z', 'OVTV', 'R_FACTOR',
                   'ACC_RMS', 'ACC_PEAK', 'DISP_TR', 'DISP_HR']
        for mid in metrics:
            value = computer.compute(mid, ctx)
            assert value != METRIC_INSUFFICIENT_DATA, f"{mid} 数据不足"
            assert isinstance(value, float), f"{mid} 应为float"
            assert np.isfinite(value), f"{mid} 应为有限值"
            print(f"    {mid}: {value:.4f}")

        hic = computer.compute('HIC15', ctx)
        assert hic >= 0
        print(f"    HIC15: {hic:.4f}")

        print(f"  [OK] MetricComputer: {len(metrics)+1}个指标全部计算成功")

    def test_metric_computer_insufficient_data(self):
        from core.core.seat_evaluation.operators import OperatorSystem
        from core.core.seat_evaluation.metric_computer import (
            MetricComputer, MetricComputeContext, METRIC_INSUFFICIENT_DATA
        )
        ops = OperatorSystem()
        computer = MetricComputer(ops)
        ctx = MetricComputeContext(
            ax=np.array([0.1, 0.2]), ay=np.array([0.1, 0.2]),
            az=np.array([0.1, 0.2]), sample_rate=100.0,
        )
        value = computer.compute('SRS_MRS', ctx)
        assert value == METRIC_INSUFFICIENT_DATA, f"2样本应返回数据不足"
        print(f"  [OK] MetricComputer: 数据不足返回{METRIC_INSUFFICIENT_DATA}")


class TestSeatEvaluationPipeline:
    """AR-7 验证: 座椅评测端到端流水线"""

    def test_evaluation_engine_v2(self):
        from core.core.seat_evaluation.engine_v2 import MultiChannelSeatEvaluationEngine
        from core.core.seat_evaluation.metadata_registry import get_global_registry
        from core.core.seat_evaluation.operators import OperatorSystem
        from core.core.analysis.core_types import VehicleConfig
        reg = get_global_registry()
        config = VehicleConfig()
        ops = OperatorSystem()
        engine = MultiChannelSeatEvaluationEngine(
            config_manager=None, data_storage=None
        )
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        data_window = {
            'ax': data['ax'], 'ay': data['ay'], 'az': data['az'],
            'gx': data['gx'], 'gy': data['gy'], 'gz': data['gz'],
            'sample_rate': data['sample_rate'],
            'timestamps': data['timestamps'],
        }
        metrics_to_test = ['AW_Z', 'VDV_Z', 'SEAT_Z', 'TR_Z',
                          'HIC15', 'ACC_H_PEAK', 'DISP_TR', 'R_FACTOR']
        results = {}
        for mid in metrics_to_test:
            value = engine._calculate_single_metric(mid, data_window)
            results[mid] = value
            assert isinstance(value, float), f"{mid} 类型错误"
            print(f"    {mid}: {value:.4f}")
        location_score = engine._calculate_location_score(results, 'seat')
        assert 0 <= location_score <= 100
        print(f"    位置评分: {location_score:.1f}")
        risk = engine._assess_location_risk(results, 'seat')
        print(f"    风险等级: {risk}")
        print(f"  [OK] MultiChannelSeatEvaluationEngine: {len(metrics_to_test)}个指标+评分+风险")

    def test_operators_iso2631_5(self):
        from core.core.seat_evaluation.operators import OperatorSystem
        ops = OperatorSystem()
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        s_d = ops.iso2631_5.compute(data['ax'] * 9.81, data['ay'] * 9.81, data['az'] * 9.81, data['sample_rate'])
        assert 'S_d_MPa' in s_d, "缺少S_d_MPa"
        assert s_d['S_d_MPa'] >= 0, "S_d应为非负值"
        print(f"  [OK] ISO2631-5: S_d={s_d['S_d_MPa']:.4f} MPa")

    def test_operators_fds(self):
        from core.core.seat_evaluation.operators import OperatorSystem
        ops = OperatorSystem()
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        rf = ops.rainflow.count(data['az'])
        fds = ops.fds.compute(rf)
        assert 'FDS_D' in fds, "缺少FDS_D"
        assert fds['FDS_D'] >= 0, "FDS_D应为非负值"
        print(f"  [OK] FDS: FDS_D={fds['FDS_D']:.6f}")

    def test_operators_weighting(self):
        from core.core.seat_evaluation.operators import OperatorSystem
        ops = OperatorSystem()
        data = TestCSVDataLoader.load('test/test_data_seat_vibration.csv')
        weighted = ops.weighting.apply_weighting_z_via_freq(data['az'], data['sample_rate'])
        assert len(weighted) == len(data['az']), "加权后长度应一致"
        rms = float(np.sqrt(np.mean(weighted**2)))
        assert rms > 0, "加权RMS应大于0"
        print(f"  [OK] Wk加权: RMS={rms:.4f} m/s2")


class TestDataSync:
    """CR-9/CR-10 验证: data_sync 插值外推和缓冲截断"""

    def test_no_extrapolation(self):
        from core.core.seat_evaluation.data_sync import MultiChannelDataSynchronizer
        sync = MultiChannelDataSynchronizer()
        t1 = np.linspace(0, 0.5, 50)
        v1 = np.sin(2 * np.pi * 5 * t1)
        t2 = np.linspace(0.1, 0.4, 30)
        v2 = np.cos(2 * np.pi * 5 * t2)
        for i in range(len(t1)):
            sync.add_channel_data('ch1', float(t1[i]), float(v1[i]))
        for i in range(len(t2)):
            sync.add_channel_data('ch2', float(t2[i]), float(v2[i]))
        result = sync.sync_and_align(channel_ids=['ch1', 'ch2'],
                                      start_time=0.1, end_time=0.4)
        assert result is not None, "同步结果不应为None"
        if result is not None:
            for key, arr in result.items():
                if hasattr(arr, '__array__'):
                    assert not np.any(np.isinf(arr)), "不应有inf值"
                    nan_count = np.sum(np.isnan(arr))
                    total = arr.size if hasattr(arr, 'size') else 0
                    nan_ratio = nan_count / total if total > 0 else 0
                    assert nan_ratio < 0.3, f"NaN比例过高: {nan_ratio:.1%}"
        print(f"  [OK] data_sync: 同步成功")


class TestMetadataRegistry:
    """AR-1 验证: metadata_registry 完整性"""

    def test_registry_singleton(self):
        from core.core.seat_evaluation.metadata_registry import get_global_registry, METRIC_THRESHOLDS
        r1 = get_global_registry()
        r2 = get_global_registry()
        assert r1 is r2, "全局注册表应为单例"
        assert len(METRIC_THRESHOLDS) >= 18, f"指标阈值不足: {len(METRIC_THRESHOLDS)}"
        print(f"  [OK] MetadataRegistry: 单例, {len(METRIC_THRESHOLDS)}个指标阈值")

    def test_4level_grading(self):
        from core.core.seat_evaluation.metadata_registry import get_global_registry
        r = get_global_registry()
        grade = r.get_4level_grade('HIC15', 150.0)
        assert '优秀' in grade, f"HIC15=150应优秀, 实际{grade}"
        grade2 = r.get_4level_grade('HIC15', 600.0)
        assert '一般' in grade2, f"HIC15=600应一般, 实际{grade2}"
        print(f"  [OK] 4级评分: HIC15=150→{grade}, HIC15=600→{grade2}")


def run_all_tests():
    """运行所有测试并返回结果"""
    test_classes = [
        TestStreamingDetector, TestMetricComputer,
        TestSeatEvaluationPipeline, TestDataSync, TestMetadataRegistry
    ]
    total = 0
    passed = 0
    for cls in test_classes:
        instance = cls()
        for name in dir(instance):
            if name.startswith('test_'):
                total += 1
                try:
                    getattr(instance, name)()
                    passed += 1
                    print(f"  [PASS] {cls.__name__}.{name}")
                except Exception as e:
                    print(f"  [FAIL] {cls.__name__}.{name}: {e}")
                    import traceback
                    traceback.print_exc()
    print(f"\n{'='*60}")
    print(f"结果: {passed}/{total} 通过")
    return passed, total


if __name__ == '__main__':
    run_all_tests()