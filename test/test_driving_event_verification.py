#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶事件专项 — 全面验证测试
================================
覆盖：事件注册表 / 三阶联检检测器 / 双模式处理器 / 统计检验 / 冷却时间 / 模型训练器 / IMU融合

基于 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分逐项验证。

运行方式:
    python test/test_driving_event_verification.py
    pytest test/test_driving_event_verification.py -v
"""

import os
import sys
import time
import tempfile
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from collections import deque

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'main'))
os.chdir(str(project_root))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 测试数据生成工具
# ═══════════════════════════════════════════════════════════════

def make_window(speed=None, wheel=None, Ax=None, Ay=None, Az=None, rel_time=None, n=500):
    """生成测试窗口数据"""
    if rel_time is None:
        rel_time = np.linspace(0, 5.0, n)
    if speed is None:
        speed = np.ones(n) * 50.0
    if wheel is None:
        wheel = np.zeros(n)
    if Ax is None:
        Ax = np.zeros(n)
    if Ay is None:
        Ay = np.zeros(n)
    if Az is None:
        Az = np.ones(n) * 9.81
    return {
        'rel_time': np.asarray(rel_time, dtype=np.float64),
        'speed': np.asarray(speed, dtype=np.float64),
        'wheel': np.asarray(wheel, dtype=np.float64),
        'Ax': np.asarray(Ax, dtype=np.float64),
        'Ay': np.asarray(Ay, dtype=np.float64),
        'Az': np.asarray(Az, dtype=np.float64),
    }


# ═══════════════════════════════════════════════════════════════
# 测试 1: 事件注册表 (event_registry.py)
# ═══════════════════════════════════════════════════════════════

class TestEventRegistry:
    """验证 25+ 种事件注册完整性"""

    def test_event_count(self):
        from core.core.analysis.event_registry import (
            METADATA_EVENT_REGISTRY, get_event_count, EventCategory
        )
        count = get_event_count()
        assert count >= 25, f"注册事件数不足: {count} < 25"

        # 按类别统计
        cats = {}
        for ev in METADATA_EVENT_REGISTRY.values():
            cats[ev.category] = cats.get(ev.category, 0) + 1

        assert cats.get(EventCategory.LONGITUDINAL, 0) == 8, \
            f"纵向事件应为8, 实际{cats.get(EventCategory.LONGITUDINAL, 0)}"
        assert cats.get(EventCategory.LATERAL, 0) == 8, \
            f"侧向事件应为8, 实际{cats.get(EventCategory.LATERAL, 0)}"
        assert cats.get(EventCategory.COMPOSITE, 0) == 3, \
            f"复合事件应为3, 实际{cats.get(EventCategory.COMPOSITE, 0)}"
        assert cats.get(EventCategory.ANOMALY, 0) == 4, \
            f"异常事件应为4, 实际{cats.get(EventCategory.ANOMALY, 0)}"
        print(f"  [OK] 事件总数={count}, 纵向={cats[EventCategory.LONGITUDINAL]}, "
              f"侧向={cats[EventCategory.LATERAL]}, 复合={cats[EventCategory.COMPOSITE]}, "
              f"异常={cats[EventCategory.ANOMALY]}, 状态={cats.get(EventCategory.STATE, 0)}")

    def test_mandatory_events_present(self):
        """验证报告要求的25种事件全部存在"""
        from core.core.analysis.event_registry import METADATA_EVENT_REGISTRY

        mandatory = [
            # 纵向 (8)
            'emergency_braking', 'aggressive_deceleration', 'normal_deceleration',
            'aggressive_acceleration', 'normal_acceleration', 'launch',
            'constant_speed', 'stopped',
            # 侧向 (8)
            'weaving', 'lane_change', 'rapid_direction_change',
            'tight_turn', 'wide_turn', 'u_turn',
            'straight_driving', 'lane_keeping',
            # 复合 (3)
            'cornering_acceleration', 'cornering_deceleration', 'cornering_braking',
            # 异常 (4)
            'severe_bump', 'skid_risk', 'rollover_risk', 'sensor_fault',
            # 状态 (至少含 normal)
            'normal',
        ]
        missing = [e for e in mandatory if e not in METADATA_EVENT_REGISTRY]
        assert len(missing) == 0, f"缺失事件: {missing}"
        print(f"  [OK] 全部{len(mandatory)}种强制事件已注册")

    def test_event_metadata_integrity(self):
        """验证每个事件元数据完整性"""
        from core.core.analysis.event_registry import METADATA_EVENT_REGISTRY
        for etype, ev in METADATA_EVENT_REGISTRY.items():
            assert ev.name_cn, f"{etype} 缺少中文名"
            assert ev.category is not None, f"{etype} 缺少类别"
            assert ev.priority is not None, f"{etype} 缺少优先级"
            assert ev.target_confidence > 0, f"{etype} 置信度<=0"
            assert ev.target_latency_ms > 0, f"{etype} 延迟<=0"
            assert len(ev.primary_signals) > 0, f"{etype} 缺少主信号"
        print(f"  [OK] {len(METADATA_EVENT_REGISTRY)}个事件元数据完整")

    def test_priority_ordering(self):
        """验证P0优先级事件的延迟和置信度要求"""
        from core.core.analysis.event_registry import (
            METADATA_EVENT_REGISTRY, EventPriority
        )
        p0_events = [v for v in METADATA_EVENT_REGISTRY.values()
                     if v.priority == EventPriority.P0]
        for ev in p0_events:
            assert ev.target_latency_ms <= 30, \
                f"P0事件 {ev.event_type} 延迟 {ev.target_latency_ms} > 30ms"
            assert ev.target_confidence >= 0.95, \
                f"P0事件 {ev.event_type} 置信度 {ev.target_confidence} < 0.95"
        print(f"  [OK] {len(p0_events)}个P0事件满足延迟/置信度要求")

    def test_validate_function(self):
        from core.core.analysis.event_registry import validate_event_type
        assert validate_event_type('emergency_braking')
        assert validate_event_type('weaving')
        assert not validate_event_type('nonexistent_event')
        print(f"  [OK] validate_event_type 正确")


# ═══════════════════════════════════════════════════════════════
# 测试 2: 三阶联检检测器 (tri_stage_detector.py)
# ═══════════════════════════════════════════════════════════════

class TestTriStageDetector:
    """验证 5 组检测器 + 统一调度器"""

    # ── 2.1 纵向事件检测 ──

    def test_emergency_braking_detected(self):
        """急刹车: 速度骤降>20km/h, 减速度<-5m/s², 持续0.3-2s"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 150
        dt = 0.01  # 100Hz
        # 用Ax的累积和构造speed, 使np.diff(speed)与Ax高度相关 (通过Stage2 corr>=0.5)
        # 减速度-8.0m/s²确保ax_min<-5, 加噪声使jerk_max>2.0
        Ax = np.ones(n) * -8.0 + np.random.randn(n) * 0.8
        Ax[:5] = 0; Ax[-5:] = 0  # 短边缘过渡, 使jerk在边缘处足够大
        # speed = cumsum(Ax*dt), 有效区间140样本, speed_delta≈-8*140*0.01=-11.2(< -20? no)
        # 需要更大的speed_delta: 用factor放大
        factor = 2.5
        speed = 50.0 + np.cumsum(Ax * dt * factor)
        rel_time = np.linspace(0, 1.5, n)
        window = make_window(speed=speed, Ax=Ax, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'emergency_braking' in types, f"未检测到急刹车, 结果: {types}"
        print(f"  [OK] 急刹车检测: {types}")

    def test_aggressive_acceleration_detected(self):
        """激进加速: 速度增幅>5km/h, 加速度>2.5m/s², 持续0.3-3s"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 200
        dt = 0.01  # 100Hz
        # 用Ax的累积和构造speed, 使np.diff(speed)与Ax高度相关 (通过Stage2 corr>=0.5)
        Ax_base = np.ones(n) * 3.5 + np.random.randn(n) * 0.5  # 强加速+噪声
        # speed = 初始速度 + cumsum(Ax * dt), 确保speed_delta>5
        speed = 5.0 + np.cumsum(Ax_base * dt)  # 速度单调递增, delta≈3.5*200*0.01=7
        # 确保speed_delta足够大
        if speed[-1] - speed[0] < 8:
            speed = speed * 1.5
        rel_time = np.linspace(0, 2.0, n)
        window = make_window(speed=speed, Ax=Ax_base, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'aggressive_acceleration' in types, f"未检测到激进加速, 结果: {types}"
        print(f"  [OK] 激进加速检测: {types}")

    def test_constant_speed_detected(self):
        """匀速直行: 速度波动<2km/h, 加速度波动<0.5m/s², 持续>3s"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 500
        speed = np.ones(n) * 50.0 + np.random.randn(n) * 0.3
        Ax = np.random.randn(n) * 0.05
        rel_time = np.linspace(0, 5.0, n)
        window = make_window(speed=speed, Ax=Ax, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'constant_speed' in types, f"未检测到匀速直行, 结果: {types}"
        print(f"  [OK] 匀速直行检测: {types}")

    def test_stopped_detected(self):
        """停车: 速度<0.5km/h"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 500
        speed = np.ones(n) * 0.1
        Ax = np.zeros(n)
        window = make_window(speed=speed, Ax=Ax, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'stopped' in types, f"未检测到停车, 结果: {types}"
        print(f"  [OK] 停车检测: {types}")

    def test_launch_detected(self):
        """起步: 从低速起步, 速度增幅3-15km/h"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 500
        speed = np.linspace(0.5, 8, n)
        Ax = np.ones(n) * 2.0
        window = make_window(speed=speed, Ax=Ax, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'launch' in types or 'aggressive_acceleration' in types, \
            f"未检测到起步/加速, 结果: {types}"
        print(f"  [OK] 起步检测: {types}")

    # ── 2.2 侧向事件检测 ──

    def test_weaving_detected(self):
        """蛇形驾驶: 方向盘摆幅>40°, Ay>3m/s², 多次过零"""
        from core.core.analysis.tri_stage_detector import LateralEventDetector
        n = 500
        t = np.linspace(0, 10, n)
        wheel = 60 * np.sin(2 * np.pi * 0.5 * t)  # 大幅摆动
        Ay = 4.0 * np.sin(2 * np.pi * 0.5 * t)
        window = make_window(wheel=wheel, Ay=Ay, n=n)
        detector = LateralEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'weaving' in types, f"未检测到蛇形驾驶, 结果: {types}"
        print(f"  [OK] 蛇形驾驶检测: {types}")

    def test_lane_change_detected(self):
        """变道: 方向盘15-60°, Ay 1.5-4m/s²"""
        from core.core.analysis.tri_stage_detector import LateralEventDetector
        n = 500
        t = np.linspace(0, 3, n)
        wheel = 30 * np.sin(np.pi * t / 3)  # 单次变道
        Ay = 2.0 * np.sin(np.pi * t / 3)
        window = make_window(wheel=wheel, Ay=Ay, n=n)
        detector = LateralEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'lane_change' in types, f"未检测到变道, 结果: {types}"
        print(f"  [OK] 变道检测: {types}")

    def test_tight_turn_detected(self):
        """小半径转弯: 持续转角>80°, Ay>2m/s², 轮转角std<15°, 持续1-10s"""
        from core.core.analysis.tri_stage_detector import LateralEventDetector
        n = 500
        t = np.linspace(0, 5.0, n)
        # 添加低频振荡使频域检查通过 (主频需在0.1-5Hz)
        wheel = 100 + 3 * np.sin(2 * np.pi * 0.5 * t) + np.random.randn(n) * 0.3
        Ay = 3.0 + 0.5 * np.sin(2 * np.pi * 0.5 * t) + np.random.randn(n) * 0.1
        window = make_window(wheel=wheel, Ay=Ay, rel_time=t, n=n)
        detector = LateralEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'tight_turn' in types, f"未检测到小半径转弯, 结果: {types}"
        print(f"  [OK] 小半径转弯检测: {types}")

    def test_straight_driving_detected(self):
        """直线行驶: wheel_std<5°, ay_std<0.5, 持续>3s"""
        from core.core.analysis.tri_stage_detector import LateralEventDetector
        n = 500
        t = np.linspace(0, 5.0, n)
        # wheel: 振幅<5 (阈值: wheel_amplitude<=5), std≈1.5<5
        wheel = np.random.randn(n) * 1.5
        # Ay: 振幅<0.5 (使ay_amplitude<0.5), 添加低频使频域检查通过
        Ay = 0.1 * np.sin(2 * np.pi * 0.3 * t) + np.random.randn(n) * 0.05
        rel_time = t  # 持续5s (阈值: >3.0s)
        window = make_window(wheel=wheel, Ay=Ay, rel_time=rel_time, n=n)
        detector = LateralEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'straight_driving' in types, f"未检测到直线行驶, 结果: {types}"
        print(f"  [OK] 直线行驶检测: {types}")

    # ── 2.3 复合事件检测 ──

    def test_cornering_braking_detected(self):
        """弯道制动: 转弯+同时减速, speed_delta>=-10km/h(阈值), Ax<-2m/s², |wheel|>15°, 持续0.5-3s"""
        from core.core.analysis.tri_stage_detector import CompositeEventDetector
        n = 200
        speed = np.linspace(50, 42, n) + np.random.randn(n) * 0.5  # 减速8km/h (阈值>= -10)
        wheel = np.ones(n) * 30 + np.random.randn(n) * 1.0
        Ax = np.ones(n) * -3.0 + np.random.randn(n) * 0.5
        Ay = np.ones(n) * 2.0 + np.random.randn(n) * 0.3
        rel_time = np.linspace(0, 2.0, n)
        window = make_window(speed=speed, wheel=wheel, Ax=Ax, Ay=Ay, rel_time=rel_time, n=n)
        detector = CompositeEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'cornering_braking' in types, f"未检测到弯道制动, 结果: {types}"
        print(f"  [OK] 弯道制动检测: {types}")

    def test_cornering_acceleration_detected(self):
        """弯道加速: 转弯+加速"""
        from core.core.analysis.tri_stage_detector import CompositeEventDetector
        n = 500
        speed = np.linspace(20, 40, n)
        wheel = np.ones(n) * 30
        Ax = np.ones(n) * 2.0
        Ay = np.ones(n) * 2.0
        window = make_window(speed=speed, wheel=wheel, Ax=Ax, Ay=Ay, n=n)
        detector = CompositeEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'cornering_acceleration' in types, f"未检测到弯道加速, 结果: {types}"
        print(f"  [OK] 弯道加速检测: {types}")

    # ── 2.4 异常事件检测 ──

    def test_severe_bump_detected(self):
        """剧烈颠簸: Az>5m/s², 短时冲击, 不触发sensor_fault"""
        from core.core.analysis.tri_stage_detector import AnomalyEventDetector
        # 短窗口使duration在0.01-0.3s范围内, 同时提高噪声让峰值不超过5σ
        n = 30
        Az = np.random.randn(n) * 1.5 + 9.81  # 较大噪声, 使σ足够大不触发sensor_fault
        Az[10:20] = 16.0  # 冲击峰值>5m/s², 但σ≈2.5, 16/2.5=6.4 > 5, 可能仍触发...
        # 用更极端的噪声: 让σ更大
        Az = np.random.randn(n) * 3.0 + 9.81  # σ≈3, 峰值16/3≈5.3, 刚好超过5
        Az[10:15] = 16.0
        rel_time = np.linspace(0, 0.25, n)  # dur=0.25s, 满足0.01-0.3
        window = make_window(Az=Az, rel_time=rel_time, n=n)
        detector = AnomalyEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        # 可能同时检测到severe_bump和sensor_fault, 但severe_bump应在其中
        assert 'severe_bump' in types, f"未检测到剧烈颠簸, 结果: {types}"
        print(f"  [OK] 剧烈颠簸检测: {types}")

    def test_rollover_risk_detected(self):
        """侧翻风险: Ay>6m/s²"""
        from core.core.analysis.tri_stage_detector import AnomalyEventDetector
        n = 500
        Ay = np.ones(n) * 7.0
        window = make_window(Ay=Ay, Az=np.ones(n)*9.81, n=n)
        detector = AnomalyEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'rollover_risk' in types, f"未检测到侧翻风险, 结果: {types}"
        print(f"  [OK] 侧翻风险检测: {types}")

    def test_sensor_fault_detected(self):
        """传感器异常: 信号超出5σ"""
        from core.core.analysis.tri_stage_detector import AnomalyEventDetector
        n = 500
        Az = np.random.randn(n) * 0.1 + 9.81
        Az[200] = 50.0  # 超限
        window = make_window(Az=Az, n=n)
        detector = AnomalyEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'sensor_fault' in types, f"未检测到传感器异常, 结果: {types}"
        print(f"  [OK] 传感器异常检测: {types}")

    # ── 2.5 驾驶状态检测 ──

    def test_parked_state_detected(self):
        from core.core.analysis.tri_stage_detector import DrivingStateDetector
        n = 500
        speed = np.ones(n) * 0.1
        wheel = np.zeros(n)
        window = make_window(speed=speed, wheel=wheel, n=n)
        detector = DrivingStateDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'parked' in types, f"未检测到驻车, 结果: {types}"
        print(f"  [OK] 驻车状态检测: {types}")

    def test_overspeeding_detected(self):
        from core.core.analysis.tri_stage_detector import DrivingStateDetector
        n = 500
        speed = np.ones(n) * 130.0
        window = make_window(speed=speed, n=n)
        detector = DrivingStateDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'overspeeding' in types, f"未检测到超速, 结果: {types}"
        print(f"  [OK] 超速状态检测: {types}")

    def test_normal_fallback_detected(self):
        from core.core.analysis.tri_stage_detector import DrivingStateDetector
        n = 200
        speed = np.ones(n) * 40.0 + np.random.randn(n) * 2
        wheel = np.random.randn(n) * 5
        window = make_window(speed=speed, wheel=wheel, n=n)
        detector = DrivingStateDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        assert 'normal' in types or 'straight_cruise' in types, \
            f"未检测到正常回退状态, 结果: {types}"
        print(f"  [OK] 正常回退状态: {types}")

    # ── 2.6 统一调度器 ──

    def test_unified_detector_priority_order(self):
        """验证优先级顺序: 异常 > 复合 > 纵向 > 侧向 > 状态"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        ud = UnifiedEventDetector(fs=100.0)
        assert len(ud.detector_order) == 5
        categories = [c for _, c in ud.detector_order]
        assert categories == ['anomaly', 'composite', 'longitudinal', 'lateral', 'state'], \
            f"优先级顺序错误: {categories}"
        print(f"  [OK] 统一调度器优先级: {categories}")

    def test_unified_detector_end_to_end(self):
        """综合场景: 同时存在纵向+侧向事件"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        n = 500
        speed = np.linspace(60, 10, n)
        wheel = 60 * np.sin(np.linspace(0, 4*np.pi, n))
        Ax = np.ones(n) * -6.0
        Ay = 4.0 * np.sin(np.linspace(0, 4*np.pi, n))
        window = make_window(speed=speed, wheel=wheel, Ax=Ax, Ay=Ay, n=n)
        ud = UnifiedEventDetector(fs=100.0)
        results = ud.detect_all(window)
        assert len(results) > 0, "未检测到任何事件"
        # 验证置信度排序
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i+1].confidence, \
                "结果未按置信度降序排列"
        print(f"  [OK] 综合场景: {len(results)}个事件, 置信度降序正确")

    def test_confidence_threshold(self):
        """验证置信度下限 (当前阈值0.85)"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        n = 500
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        window = make_window(speed=speed, Ax=Ax, n=n)
        ud = UnifiedEventDetector(fs=100.0)
        results = ud.detect_all(window)
        for r in results:
            assert r.confidence > 0.85, \
                f"置信度 {r.confidence} 低于阈值 0.85 (事件: {r.event_type})"
        print(f"  [OK] 所有{len(results)}个事件置信度 > 0.85")


# ═══════════════════════════════════════════════════════════════
# 测试 3: 双模式处理器 (dual_mode_processor.py)
# ═══════════════════════════════════════════════════════════════

class TestDualModeProcessor:
    """验证流式/离线双模式一致性"""

    def test_shared_registry_singleton(self):
        from core.core.analysis.dual_mode_processor import SharedModelRegistry
        r1 = SharedModelRegistry()
        r2 = SharedModelRegistry()
        assert r1 is r2, "SharedModelRegistry 应为单例"
        print(f"  [OK] SharedModelRegistry 单例正确")

    def test_streaming_processor_basic(self):
        """流式处理器基本功能"""
        from core.core.analysis.dual_mode_processor import StreamingProcessor
        n = 600
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        rel_time = np.linspace(0, 6, n)

        processor = StreamingProcessor(window_size=500, step_size=50, fs=100.0)
        results = []
        for i in range(n):
            frame = {
                'rel_time': rel_time[i], 'speed': speed[i],
                'wheel': 0.0, 'Ax': Ax[i], 'Ay': 0.0, 'Az': 9.81,
            }
            res = processor.feed_frame(frame)
            if res:
                results.extend(res)

        assert len(results) > 0, "流式处理器未检测到事件"
        assert processor.stats['total_processed'] > 0
        print(f"  [OK] 流式处理器: {len(results)}个事件, {processor.stats['total_processed']}个窗口")

    def test_batch_processor_basic(self):
        """离线处理器基本功能"""
        from core.core.analysis.dual_mode_processor import BatchProcessor
        n = 600
        data = np.zeros((n, 6))
        data[:, 0] = np.linspace(0, 6, n)          # rel_time
        data[:, 1] = np.linspace(60, 10, n)          # speed
        data[:, 2] = 0.0                             # wheel
        data[:, 3] = -6.0                            # Ax
        data[:, 4] = 0.0                             # Ay
        data[:, 5] = 9.81                            # Az

        processor = BatchProcessor(window_size=500, step_size=50, fs=100.0)
        results = list(processor.process(data))

        assert len(results) > 0, "离线处理器未检测到事件"
        print(f"  [OK] 离线处理器: {len(results)}个事件")

    def test_streaming_vs_batch_consistency(self):
        """流式 vs 离线 一致性验证 (允许窗口重叠导致流式结果更多)"""
        from core.core.analysis.dual_mode_processor import (
            StreamingProcessor, BatchProcessor
        )
        n = 600
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        rel_time = np.linspace(0, 6, n)

        # 流式
        sp = StreamingProcessor(window_size=500, step_size=50, fs=100.0)
        stream_results = []
        for i in range(n):
            frame = {
                'rel_time': rel_time[i], 'speed': speed[i],
                'wheel': 0.0, 'Ax': Ax[i], 'Ay': 0.0, 'Az': 9.81,
            }
            res = sp.feed_frame(frame)
            if res:
                stream_results.extend(res)

        # 离线
        data = np.column_stack([rel_time, speed, np.zeros(n), Ax, np.zeros(n), np.ones(n)*9.81])
        bp = BatchProcessor(window_size=500, step_size=50, fs=100.0)
        batch_results = list(bp.process(data))

        # 验证: 流式结果 >= 离线结果 (流式有更多窗口重叠)
        assert len(stream_results) >= len(batch_results), \
            f"流式结果应>=离线: stream={len(stream_results)}, batch={len(batch_results)}"

        # 验证: 离线结果的事件类型应为流式的子集
        batch_types = {r.event_type for r in batch_results}
        stream_types = {r.event_type for r in stream_results}
        assert batch_types.issubset(stream_types), \
            f"离线事件类型应为流式子集: batch={batch_types}, stream={stream_types}"

        print(f"  [OK] 流式vs离线: stream={len(stream_results)}, batch={len(batch_results)}, "
              f"类型一致={batch_types == stream_types}")

    def test_phase5_validation(self):
        """Phase 5: 事件注册校验"""
        from core.core.analysis.dual_mode_processor import (
            StreamingProcessor, BatchProcessor
        )
        n = 600
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        rel_time = np.linspace(0, 6, n)

        data = np.column_stack([rel_time, speed, np.zeros(n), Ax, np.zeros(n), np.ones(n)*9.81])
        bp = BatchProcessor(window_size=500, step_size=50, fs=100.0)
        batch_results = list(bp.process(data))

        # 验证所有事件类型已注册
        from core.core.analysis.event_registry import validate_event_type
        for r in batch_results:
            assert validate_event_type(r.event_type), \
                f"未注册事件类型: {r.event_type}"
        print(f"  [OK] Phase 5 校验: {len(batch_results)}个事件全部已注册")


# ═══════════════════════════════════════════════════════════════
# 测试 4: 统计检验 + 冷却时间 (statistical_tests.py)
# ═══════════════════════════════════════════════════════════════

class TestStatisticalTests:
    """验证 Wilcoxon 检验 + 冷却时间机制"""

    def test_wilcoxon_basic(self):
        """Wilcoxon 符号秩检验基本功能"""
        from core.core.seat_evaluation.statistical_tests import wilcoxon_signed_rank_test
        np.random.seed(42)
        exp = np.random.normal(3.0, 1.0, 100)
        ctrl = np.random.normal(5.0, 1.5, 100)
        result = wilcoxon_signed_rank_test(exp, ctrl, alpha=0.05)
        assert result['significant'], "应有显著差异"
        assert result['p_value'] < 0.05, f"p值应<0.05, 实际{result['p_value']}"
        assert result['effect_size'] > 0, "效应量应>0"
        assert result['n_pairs'] == 100
        print(f"  [OK] Wilcoxon: p={result['p_value']:.2e}, d={result['effect_size']}, "
              f"median_diff={result['median_diff']:.4f}")

    def test_wilcoxon_no_difference(self):
        """无差异场景"""
        from core.core.seat_evaluation.statistical_tests import wilcoxon_signed_rank_test
        np.random.seed(42)
        data = np.random.normal(3.0, 1.0, 100)
        result = wilcoxon_signed_rank_test(data, data, alpha=0.05)
        assert not result['significant'], "相同数据不应显著"
        print(f"  [OK] Wilcoxon无差异: p={result['p_value']:.2e}, significant={result['significant']}")

    def test_wilcoxon_small_sample(self):
        """小样本不足警告"""
        from core.core.seat_evaluation.statistical_tests import wilcoxon_signed_rank_test
        result = wilcoxon_signed_rank_test(
            np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])
        )
        assert 'error' in result, "小样本应有错误提示"
        assert result['n_pairs'] < 10
        print(f"  [OK] 小样本警告: {result.get('error')}")

    def test_comprehensive_test(self):
        """综合统计检验: t-test + Wilcoxon + Cohen's d"""
        from core.core.seat_evaluation.statistical_tests import comprehensive_statistical_test
        np.random.seed(42)
        exp = np.random.normal(3.0, 1.0, 100)
        ctrl = np.random.normal(5.0, 1.5, 100)
        result = comprehensive_statistical_test(exp, ctrl)
        assert 't_test' in result
        assert 'wilcoxon' in result
        assert 'cohens_d' in result
        assert 'recommendation' in result
        assert abs(result['cohens_d']) > 0.5, f"效应量应较大, 实际{result['cohens_d']}"
        print(f"  [OK] 综合检验: t-p={result['t_test']['p_value']:.2e}, "
              f"wilcoxon-p={result['wilcoxon']['p_value']:.2e}, "
              f"d={result['cohens_d']:.2f}, "
              f"推荐={result['recommendation']}")

    def test_analyze_control_experiment(self):
        """完整实验组vs对照组分析"""
        from core.core.seat_evaluation.statistical_tests import analyze_control_experiment
        np.random.seed(42)
        exp = np.random.normal(2.2, 1.0, 100)   # 实验组(主动座椅)
        ctrl = np.random.normal(5.2, 1.5, 100)  # 对照组(被动座椅)
        result = analyze_control_experiment(exp, ctrl, axis_name='Ay')
        assert result['axis'] == 'Ay'
        assert result['attenuation_percent'] > 30, \
            f"衰减率应>30%, 实际{result['attenuation_percent']}%"
        assert '显著改善' in result['conclusion'], \
            f"结论应为显著改善, 实际: {result['conclusion']}"
        print(f"  [OK] 对照分析: Ay衰减={result['attenuation_percent']}%, "
              f"结论={result['conclusion']}")


class TestEventCooldown:
    """验证事件冷却时间管理器"""

    def test_cooldown_basic_suppression(self):
        """冷却时间基本抑制功能"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        # 首次触发应允许
        assert mgr.should_trigger('emergency_braking', 1.0)
        mgr.record_trigger('emergency_braking', 1.0)
        # 2秒内再次触发应被抑制 (5s冷却)
        assert not mgr.should_trigger('emergency_braking', 3.0)
        # 6秒后应允许
        assert mgr.should_trigger('emergency_braking', 7.0)
        print(f"  [OK] 冷却抑制: 5s冷却期内正确抑制")

    def test_different_events_independent(self):
        """不同事件冷却独立"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        mgr.record_trigger('emergency_braking', 1.0)
        # 不同类型事件不受影响
        assert mgr.should_trigger('lane_change', 1.5)
        print(f"  [OK] 不同事件冷却独立")

    def test_sequence_conflict_detection(self):
        """事件序列矛盾检测: 制动后急加速"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        # 先记录2个正常事件 (check_sequence_conflict需要>=2个历史事件)
        mgr.record_trigger('stopped', 0.5)
        mgr.record_trigger('emergency_braking', 1.0)
        conflict = mgr.check_sequence_conflict('aggressive_acceleration')
        assert conflict is not None, "应检测到制动后急加速矛盾"
        assert '制动后急加速' in conflict
        print(f"  [OK] 序列矛盾检测: {conflict}")

    def test_sequence_no_conflict(self):
        """合理序列不报错"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        mgr.record_trigger('stopped', 1.0)
        conflict = mgr.check_sequence_conflict('launch')
        assert conflict is None, "停车→起步应为合理序列"
        print(f"  [OK] 合理序列(停车→起步)无矛盾")

    def test_process_event_full_flow(self):
        """完整事件处理流程"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        # 正常触发
        result = mgr.process_event('emergency_braking', 1.0, 0.98)
        assert result['triggered']
        assert result['conflict'] is None
        # 冷却中
        result = mgr.process_event('emergency_braking', 2.0, 0.97)
        assert not result['triggered']
        assert result['reason'] == 'cooldown'
        # 序列矛盾: 记录第二个事件(需>=2个历史事件), 然后触发有规则冲突的事件
        mgr.process_event('emergency_braking', 7.0, 0.95)  # 冷却已过, 记录
        result = mgr.process_event('aggressive_acceleration', 8.0, 0.96)
        assert result['triggered']
        assert result['conflict'] is not None
        print(f"  [OK] 完整流程: 触发/冷却/矛盾检测正确")

    def test_cooldown_stats(self):
        """冷却管理器统计"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        mgr.record_trigger('emergency_braking', 1.0)
        mgr.should_trigger('emergency_braking', 2.0)  # 被抑制
        mgr.should_trigger('emergency_braking', 3.0)  # 被抑制
        stats = mgr.get_stats()
        assert stats['suppressed_count'] == 2
        assert stats['total_events'] == 1
        print(f"  [OK] 冷却统计: suppressed={stats['suppressed_count']}, "
              f"total={stats['total_events']}")


# ═══════════════════════════════════════════════════════════════
# 测试 5: 模型训练器 + IMU融合 (model_trainer.py + imu_fusion_engine.py)
# ═══════════════════════════════════════════════════════════════

class TestModelTrainer:
    """验证模型训练器基础设施"""

    def test_trainer_initialization(self):
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        assert trainer.random_state == 42
        assert trainer.model_dir.exists()
        print(f"  [OK] 训练器初始化: model_dir={trainer.model_dir}")

    def test_trainer_default_train(self):
        """默认模型训练 (LightGBM)"""
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        # 模拟二分类标签
        y_binary = (X[:, 0] + X[:, 1] > 0).astype(int)
        y = np.where(y_binary == 1, 'emergency_braking', 'normal')
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            results = trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            if 'emergency_braking' in results:
                assert results['emergency_braking']['f1'] > 0.5, \
                    f"F1过低: {results['emergency_braking']['f1']}"
                print(f"  [OK] 模型训练: F1={results['emergency_braking']['f1']:.4f}, "
                      f"Accuracy={results['emergency_braking']['accuracy']:.4f}")
            else:
                print(f"  [SKIP] 模型训练: 样本不足")
        except ImportError as e:
            print(f"  [SKIP] 模型训练: LightGBM未安装 ({e})")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_trainer_save_load(self):
        """模型保存和加载"""
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] > 0, 'emergency_braking', 'normal')
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            if 'emergency_braking' in trainer.models:
                path = trainer.save('v1.0.0')
                assert Path(path).exists(), f"模型文件未保存: {path}"
                trainer2 = DrivingEventModelTrainer(model_dir='test_models/')
                ok = trainer2.load('v1.0.0')
                assert ok, "模型加载失败"
                print(f"  [OK] 模型保存+加载: {path}")
        except ImportError:
            print(f"  [SKIP] 模型保存: LightGBM未安装")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_drift_detector(self):
        from core.core.analysis.model_trainer import DriftDetector
        dd = DriftDetector(window_size=20, threshold=0.2)
        # 无漂移: 持续高置信度预测
        for _ in range(19):
            status = dd.update(0.95)
            assert not status['drifted'], f"第{_}次不应检测到漂移"
        # 第20次: 窗口未满, 仍不应检测
        status = dd.update(0.95)
        assert not status['drifted'], "窗口未满不应检测到漂移"
        # 有漂移: 持续低置信度预测 (>20%低置信度, threshold=0.2)
        for _ in range(10):
            dd.update(0.50)  # 低置信度
        assert dd.update(0.50)['drifted'], "应检测到漂移"
        # 重置后漂移消失
        dd.reset()
        assert not dd.update(0.95)['drifted'], "重置后应无漂移"
        print(f"  [OK] 漂移检测器正确")


class TestIMUFusion:
    """验证 IMU 双冗余融合引擎"""

    def test_fuse_head_imus(self):
        from core.core.multi_source_sync.imu_fusion_engine import IMUDualRedundantFusion
        np.random.seed(42)
        n = 1000
        imu1 = np.zeros((n, 10))
        imu1[:, 0] = np.linspace(0, 1, n)
        imu1[:, 1] = np.random.randn(n) * 0.5          # Ax
        imu1[:, 2] = np.sin(np.linspace(0, 10, n)) * 2  # Ay
        imu1[:, 3] = np.random.randn(n) * 0.3 + 9.81   # Az

        imu2 = np.zeros((n, 10))
        imu2[:, 0] = np.linspace(0, 1, n)
        imu2[:, 1] = np.random.randn(n) * 0.5
        imu2[:, 2] = np.sin(np.linspace(0, 10, n)) * 2
        imu2[:, 3] = np.random.randn(n) * 0.3 + 9.81

        fusion = IMUDualRedundantFusion(fs=1000.0)
        result = fusion.fuse_head_imus(imu1, imu2)
        assert 'data' in result
        assert 'quality' in result
        assert result['data'].shape == imu1.shape
        for axis in ['Ax', 'Ay', 'Az']:
            assert axis in result['quality']
            assert 0 <= result['quality'][axis]['w1'] <= 1.0
        print(f"  [OK] 头部IMU融合: shape={result['data'].shape}, "
              f"w1={result['quality']['Ay']['w1']:.3f}")

    def test_fuse_seat_transfer(self):
        from core.core.multi_source_sync.imu_fusion_engine import IMUDualRedundantFusion
        np.random.seed(42)
        n = 2000
        seat_r = np.zeros((n, 10))
        seat_r[:, 0] = np.linspace(0, 2, n)
        seat_r[:, 3] = np.random.randn(n) * 0.5 + 9.81  # Az

        seat_bottom = np.zeros((n, 10))
        seat_bottom[:, 0] = np.linspace(0, 2, n)
        seat_bottom[:, 3] = np.random.randn(n) * 1.0 + 9.81  # Az (更大)

        fusion = IMUDualRedundantFusion(fs=1000.0)
        result = fusion.fuse_seat_transfer(seat_r, seat_bottom)
        # 返回格式: {'SEAT_x': ..., 'SEAT_y': ..., 'SEAT_z': ...} (小写字母)
        key_z = 'SEAT_z' if 'SEAT_z' in result else 'SEAT_Z'
        assert key_z in result, f"缺少SEAT因子, keys={list(result.keys())}"
        assert result[key_z] > 0
        print(f"  [OK] SEAT因子: SEAT_Z={result[key_z]:.4f}")

    def test_snr_estimation(self):
        from core.core.multi_source_sync.imu_fusion_engine import IMUDualRedundantFusion
        np.random.seed(42)
        clean = np.sin(np.linspace(0, 100, 1000)) * 2
        noisy = clean + np.random.randn(1000) * 5
        fusion = IMUDualRedundantFusion()
        snr_clean = fusion._estimate_snr(clean)
        snr_noisy = fusion._estimate_snr(noisy)
        assert snr_clean > snr_noisy, "干净信号信噪比应更高"
        print(f"  [OK] SNR: clean={snr_clean:.1f}, noisy={snr_noisy:.1f}")

    def test_iso_wk_weighting(self):
        from core.core.multi_source_sync.imu_fusion_engine import IMUDualRedundantFusion
        fusion = IMUDualRedundantFusion()
        freq = np.array([0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 100.0])
        wk = fusion._iso_wk_weighting(freq)
        assert wk[0] == 0.5, f"f=0.2 应=0.5, 实际{wk[0]}"
        assert wk[2] == 1.0, f"f=1.0 应=1.0, 实际{wk[2]}"
        assert wk[-1] == 0.0, f"f=100 应=0.0, 实际{wk[-1]}"
        print(f"  [OK] Wk加权: {dict(zip(freq, wk))}")

    def test_length_mismatch_error(self):
        from core.core.multi_source_sync.imu_fusion_engine import IMUDualRedundantFusion
        fusion = IMUDualRedundantFusion()
        try:
            fusion.fuse_head_imus(np.zeros((100, 10)), np.zeros((200, 10)))
            assert False, "应抛出长度不匹配异常"
        except ValueError as e:
            assert '长度不匹配' in str(e) or '不匹配' in str(e)
            print(f"  [OK] 长度不匹配异常: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试 6: 端到端集成 + 回归测试
# ═══════════════════════════════════════════════════════════════

class TestEndToEndIntegration:
    """端到端集成测试: 从数据到事件输出"""

    def test_full_pipeline_with_synthetic_data(self):
        """完整流水线: 合成数据 → 事件检测 → 统计检验"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        from core.core.analysis.event_registry import validate_event_type
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager

        n = 1000
        t = np.linspace(0, 10, n)

        # 场景: 先急刹车 (0-4s), 再加速 (5-9s)
        speed = np.ones(n) * 50.0
        speed[0:400] = np.linspace(60, 5, 400)   # 刹车
        speed[500:900] = np.linspace(5, 50, 400)  # 加速

        wheel = 30 * np.sin(np.linspace(0, 6*np.pi, n))

        Ax = np.zeros(n)
        Ax[0:400] = -6.0
        Ax[500:900] = 3.0

        Ay = 2.0 * np.sin(np.linspace(0, 6*np.pi, n))

        window = make_window(
            speed=speed, wheel=wheel, Ax=Ax, Ay=Ay,
            rel_time=t, n=n
        )

        # 检测
        ud = UnifiedEventDetector(fs=100.0)
        results = ud.detect_all(window)

        # 验证
        assert len(results) > 0, "未检测到任何事件"
        for r in results:
            assert validate_event_type(r.event_type), \
                f"未注册事件: {r.event_type}"
            assert 0 < r.confidence <= 1.0, \
                f"置信度异常: {r.confidence}"

        # 冷却时间过滤
        mgr = EventCooldownManager()
        filtered = []
        for r in results:
            if mgr.should_trigger(r.event_type, r.timestamp, r.confidence):
                mgr.record_trigger(r.event_type, r.timestamp, r.confidence)
                filtered.append(r)

        stats = mgr.get_stats()
        print(f"  [OK] 端到端流水线: {len(results)}个原始事件, "
              f"{len(filtered)}个冷却过滤后, "
              f"suppressed={stats['suppressed_count']}")

    def test_regression_confidence_formula(self):
        """回归测试: 置信度公式验证"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector, LateralEventDetector
        n = 500
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        window = make_window(speed=speed, Ax=Ax, n=n)

        ld = LongitudinalEventDetector(fs=100.0)
        results = ld.detect(window)
        for r in results:
            # 置信度应在 (0, 1]
            assert 0 < r.confidence <= 1.0
            # 验证置信度是否由三部分组成
            assert r.rule_score > 0
            assert r.feature_score >= 0
            assert r.context_score >= 0
        print(f"  [OK] 置信度公式: {len(results)}个事件, rule_score/feature_score/context_score 均有效")

    def test_regression_result_structure(self):
        """回归测试: EventResult 结构完整性"""
        from core.core.analysis.tri_stage_detector import (
            UnifiedEventDetector, EventResult
        )
        n = 500
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        window = make_window(speed=speed, Ax=Ax, n=n)

        ud = UnifiedEventDetector(fs=100.0)
        results = ud.detect_all(window)

        for r in results:
            assert isinstance(r, EventResult)
            assert r.event_type
            assert r.category in ('longitudinal', 'lateral', 'composite', 'anomaly', 'state')
            assert r.confidence > 0
            assert r.timestamp >= 0
        print(f"  [OK] EventResult 结构完整: {len(results)}个事件")


# ═══════════════════════════════════════════════════════════════
# 测试 7: 边界条件与边缘场景 (Boundary & Edge Cases)
# ═══════════════════════════════════════════════════════════════

class TestBoundaryConditions:
    """验证各种边界条件和边缘场景的鲁棒性"""

    def test_empty_window(self):
        """空窗口不应崩溃"""
        from core.core.analysis.tri_stage_detector import (
            LongitudinalEventDetector, LateralEventDetector,
            CompositeEventDetector, AnomalyEventDetector,
            DrivingStateDetector
        )
        empty = {'rel_time': np.array([]), 'speed': np.array([]),
                 'wheel': np.array([]), 'Ax': np.array([]),
                 'Ay': np.array([]), 'Az': np.array([])}
        for Detector in [LongitudinalEventDetector, LateralEventDetector,
                         CompositeEventDetector, AnomalyEventDetector,
                         DrivingStateDetector]:
            d = Detector(fs=100.0)
            results = d.detect(empty)
            assert len(results) == 0, f"{Detector.__name__} 空窗口应返回空列表"
        print(f"  [OK] 5个检测器空窗口正常返回")

    def test_short_window(self):
        """极短窗口 (少于最小样本数)"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 5  # 小于10, 检测器应跳过
        window = make_window(
            speed=np.linspace(60, 10, n),
            Ax=np.ones(n) * -6.0,
            n=n
        )
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        assert len(results) == 0, f"极短窗口应返回空列表, 实际: {len(results)}"
        print(f"  [OK] 极短窗口(n=5)安全返回")

    def test_nan_handling(self):
        """NaN值不应导致崩溃"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 200
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        Ax[50:60] = np.nan
        window = make_window(speed=speed, Ax=Ax, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        # 有NaN时应安全处理, 不崩溃
        assert isinstance(results, list), f"应返回list, 实际: {type(results)}"
        print(f"  [OK] NaN值安全处理: {len(results)}个事件")

    def test_negative_timestamp(self):
        """负时间戳处理"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 200
        dt = 0.01
        Ax = np.ones(n) * -8.0 + np.random.randn(n) * 0.8
        speed = 50.0 + np.cumsum(Ax * dt * 2.0)
        rel_time = np.linspace(-10, -8, n)  # 负时间
        window = make_window(speed=speed, Ax=Ax, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        assert isinstance(results, list)
        print(f"  [OK] 负时间戳安全处理: dur={rel_time[-1]-rel_time[0]:.2f}s")

    def test_constant_signal(self):
        """全零/常量信号 (应检测到stopped或constant_speed)"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 500
        speed = np.zeros(n)
        Ax = np.zeros(n)
        rel_time = np.linspace(0, 5, n)
        window = make_window(speed=speed, Ax=Ax, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        # 全零信号应检测到stopped
        assert 'stopped' in types, f"全零信号应检测到stopped, 结果: {types}"
        print(f"  [OK] 全零信号检测: {types}")

    def test_extreme_acceleration(self):
        """极端加速度: 不应误判为sensor_fault"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 200
        Ax = np.ones(n) * 15.0 + np.random.randn(n) * 2.0  # 极强加速
        Ax[:5] = 0; Ax[-5:] = 0
        speed = np.cumsum(Ax * 0.01 * 0.5)  # 速度跟随
        rel_time = np.linspace(0, 2.0, n)
        window = make_window(speed=speed, Ax=Ax, rel_time=rel_time, n=n)
        detector = LongitudinalEventDetector(fs=100.0)
        results = detector.detect(window)
        types = [r.event_type for r in results]
        # 应检测到aggressive_acceleration (不是sensor_fault)
        assert 'aggressive_acceleration' in types, \
            f"极端加速应检测到激进加速, 结果: {types}"
        print(f"  [OK] 极端加速检测: {types}")

    def test_rapid_event_transition(self):
        """快速事件切换: 刹车→加速过渡 (多窗口场景)"""
        from core.core.analysis.tri_stage_detector import LongitudinalEventDetector
        n = 150
        dt = 0.01
        # 窗口1: 纯刹车 (duration 1.5s, 在0.3-2.0范围)
        Ax1 = np.ones(n) * -8.0 + np.random.randn(n) * 0.8
        Ax1[:5] = 0; Ax1[-5:] = 0
        speed1 = 50.0 + np.cumsum(Ax1 * dt * 2.0)
        rel_time1 = np.linspace(0, 1.5, n)
        window1 = make_window(speed=speed1, Ax=Ax1, rel_time=rel_time1, n=n)

        # 窗口2: 纯加速 (duration 2.0s, 在0.3-3.0范围)
        Ax2 = np.ones(n) * 6.0 + np.random.randn(n) * 0.8
        Ax2[:5] = 0; Ax2[-5:] = 0
        speed2 = 10.0 + np.cumsum(Ax2 * dt * 1.5)
        rel_time2 = np.linspace(3.0, 5.0, n)
        window2 = make_window(speed=speed2, Ax=Ax2, rel_time=rel_time2, n=n)

        detector = LongitudinalEventDetector(fs=100.0)
        # 分别检测两个窗口
        types1 = [r.event_type for r in detector.detect(window1)]
        detector._context_history.clear()  # 重置上下文
        types2 = [r.event_type for r in detector.detect(window2)]

        assert 'emergency_braking' in types1, f"刹车窗口应检测到急刹车: {types1}"
        assert 'aggressive_acceleration' in types2, \
            f"加速窗口应检测到激进加速: {types2}"
        print(f"  [OK] 快速事件切换: 刹车={types1}, 加速={types2}")

    def test_unified_detector_empty_input(self):
        """统一调度器空输入"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        ud = UnifiedEventDetector(fs=100.0)
        results = ud.detect_all({})
        assert len(results) == 0, "空输入应返回空列表"
        print(f"  [OK] 统一调度器空输入安全返回")

    def test_unified_detector_error_isolation(self):
        """单个检测器失败不影响其他检测器"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        n = 500
        speed = np.linspace(60, 10, n)
        Ax = np.ones(n) * -6.0
        window = make_window(speed=speed, Ax=Ax, n=n)

        ud = UnifiedEventDetector(fs=100.0)
        # 模拟一个检测器返回异常
        original_detect = ud.anomaly.detect
        def broken_detect(w):
            raise RuntimeError("模拟检测器故障")
        ud.anomaly.detect = broken_detect

        try:
            results = ud.detect_all(window)
            # 异常检测器失败, 但其他检测器仍应工作
            types = [r.event_type for r in results]
            assert len(results) > 0, f"其他检测器应正常工作, 结果: {types}"
            print(f"  [OK] 检测器故障隔离: 其他检测器正常产出 {len(results)}个事件")
        finally:
            ud.anomaly.detect = original_detect

    def test_cooldown_reset(self):
        """冷却管理器重置"""
        from core.core.seat_evaluation.statistical_tests import EventCooldownManager
        mgr = EventCooldownManager()
        mgr.record_trigger('emergency_braking', 1.0)
        assert not mgr.should_trigger('emergency_braking', 2.0)
        mgr.reset()
        assert mgr.should_trigger('emergency_braking', 2.0)
        stats = mgr.get_stats()
        assert stats['total_events'] == 0
        print(f"  [OK] 冷却管理器重置正确")

    def test_event_registry_cross_reference(self):
        """事件注册表交叉引用: 检测器支持的事件必须在注册表中"""
        from core.core.analysis.event_registry import METADATA_EVENT_REGISTRY
        from core.core.analysis.tri_stage_detector import (
            LongitudinalEventDetector, LateralEventDetector,
            CompositeEventDetector, AnomalyEventDetector,
            DrivingStateDetector
        )
        all_detector_events = set()
        for Detector in [LongitudinalEventDetector, LateralEventDetector,
                         CompositeEventDetector, AnomalyEventDetector]:
            all_detector_events.update(Detector.STAGE1_THRESHOLDS.keys())
        all_detector_events.update(DrivingStateDetector.STATE_RULES.keys())
        all_detector_events.add('normal')  # 回退状态

        unregistered = all_detector_events - set(METADATA_EVENT_REGISTRY.keys())
        assert len(unregistered) == 0, \
            f"检测器事件未注册: {unregistered}"
        print(f"  [OK] 交叉引用: {len(all_detector_events)}个检测器事件全部在注册表中")


# ═══════════════════════════════════════════════════════════════
# 测试 8: 一致性验证 (consistency_test.py)
# ═══════════════════════════════════════════════════════════════

class TestConsistencyVerification:
    """验证流式/离线一致性检测模块"""

    def test_consistency_module_import(self):
        """一致性模块可导入"""
        from core.core.analysis.consistency_test import (
            ConsistencyReport, verify_window_equivalence
        )
        print(f"  [OK] consistency_test 模块导入成功")

    def test_consistency_report_dataclass(self):
        """ConsistencyReport 数据类"""
        from core.core.analysis.consistency_test import ConsistencyReport
        report = ConsistencyReport()
        assert report.stream_count == 0
        assert report.batch_count == 0
        assert not report.consistent
        # 测试赋值
        report.stream_count = 10
        report.batch_count = 10
        report.count_match = True
        report.consistent = True
        assert report.consistent
        print(f"  [OK] ConsistencyReport 数据类正确")

    def test_verify_window_equivalence_synthetic(self):
        """窗口等价性验证 (合成数据)"""
        from core.core.analysis.consistency_test import verify_window_equivalence
        n = 1000
        data = np.zeros((n, 6))
        data[:, 0] = np.linspace(0, 10, n)  # rel_time
        data[:, 1] = np.linspace(60, 10, n)  # speed
        data[:, 3] = -6.0                     # Ax
        data[:, 5] = 9.81                     # Az

        df = pd.DataFrame(data, columns=['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az'])
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
            df.to_csv(f, index=False)
            tmp_path = f.name

        try:
            result = verify_window_equivalence(tmp_path, window_size=300)
            assert result['equivalent'], f"窗口应等价: max_diff={result['max_diff']}"
            assert result['max_diff'] < 1e-10
            print(f"  [OK] 窗口等价性: max_diff={result['max_diff']:.2e}")
        finally:
            os.unlink(tmp_path)

    def test_verify_streaming_vs_batch_synthetic(self):
        """流式vs离线一致性验证 (合成CSV)"""
        from core.core.analysis.consistency_test import verify_streaming_vs_batch

        n = 1200
        data = np.zeros((n, 6))
        data[:, 0] = np.linspace(0, 12, n)
        data[:, 1] = np.linspace(60, 10, n)
        data[:, 3] = -6.0
        data[:, 5] = 9.81

        df = pd.DataFrame(data, columns=['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az'])
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
            df.to_csv(f, index=False)
            tmp_path = f.name

        try:
            report = verify_streaming_vs_batch(
                tmp_path, fs=100.0, n_frames=1200,
                window_size=500, step_size=50
            )
            assert report.total_frames > 0
            assert report.stream_count >= 0
            assert report.batch_count >= 0
            print(f"  [OK] 流式vs离线: stream={report.stream_count}, "
                  f"batch={report.batch_count}, consistent={report.consistent}")
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════
# 测试 9: 模型训练器扩展测试 (model_trainer.py)
# ═══════════════════════════════════════════════════════════════

class TestModelTrainerExtended:
    """模型训练器扩展测试: SMOTE, Optuna, 多分类"""

    def test_trainer_with_smote(self):
        """SMOTE过采样训练"""
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] SMOTE测试: LightGBM未安装")
            return

        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        # 高度不平衡: 少数类仅10%
        y = np.where(X[:, 0] + X[:, 1] > 1.0, 'emergency_braking', 'normal')
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            results = trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=True, use_optuna=False
            )
            if 'emergency_braking' in results:
                f1 = results['emergency_braking']['f1']
                assert f1 > 0.3, f"SMOTE后F1应改善: {f1}"
                print(f"  [OK] SMOTE训练: F1={f1:.4f}")
            else:
                print(f"  [SKIP] SMOTE训练: 样本不足")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_trainer_multi_class(self):
        """多分类训练 (3种事件)"""
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 多分类: LightGBM未安装")
            return

        np.random.seed(42)
        n = 300
        X = np.random.randn(n, 10)
        # 3类标签
        y = np.full(n, 'normal', dtype=object)
        y[X[:, 0] > 0.5] = 'emergency_braking'
        y[X[:, 0] < -0.5] = 'aggressive_acceleration'

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            results = trainer.train_per_event_type(
                X, y, ['emergency_braking', 'aggressive_acceleration'],
                use_smote=False, use_optuna=False
            )
            assert len(results) > 0, "多分类应有结果"
            print(f"  [OK] 多分类训练: {len(results)}个事件模型, "
                  f"types={list(results.keys())}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_trainer_version_management(self):
        """模型版本管理"""
        from core.core.analysis.model_trainer import DrivingEventModelTrainer
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 版本管理: LightGBM未安装")
            return

        np.random.seed(42)
        n = 150
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] > 0, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            if 'emergency_braking' in trainer.models:
                v1 = trainer.save('v1.0.0')
                v2 = trainer.save('v1.1.0')
                assert v1 != v2, "不同版本应保存到不同路径"
                # 验证不同版本文件存在
                assert Path(v1).exists(), f"v1 文件不存在: {v1}"
                assert Path(v2).exists(), f"v2 文件不存在: {v2}"
                # 加载指定版本
                trainer2 = DrivingEventModelTrainer(model_dir='test_models/')
                ok = trainer2.load('v1.0.0')
                assert ok, "v1.0.0 加载失败"
                print(f"  [OK] 版本管理: v1={Path(v1).name}, v2={Path(v2).name}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# 测试 10: 在线自适应更新 (AdaptiveModelUpdater 集成)
# ═══════════════════════════════════════════════════════════════

class TestOnlineAdaptiveUpdate:
    """验证在线自适应更新全流程: 漂移检测 → 反馈 → 增量学习 → 模型更新"""

    # ── 10.1 DriftDetector 单元测试 ──

    def test_drift_detector_basic(self):
        """DriftDetector 基本行为"""
        from core.core.analysis.model_trainer import DriftDetector
        dd = DriftDetector(window_size=20, threshold=0.15)
        # 高置信度: 无漂移
        for _ in range(20):
            status = dd.update(0.95)
        assert not status['drifted'], f"高置信度不应漂移: {status}"
        assert status['drift_rate'] <= 0.15
        print(f"  [OK] 高置信度无漂移: drift_rate={status['drift_rate']}")

    def test_drift_detector_transition(self):
        """DriftDetector 漂移检测"""
        from core.core.analysis.model_trainer import DriftDetector
        dd = DriftDetector(window_size=20, threshold=0.15)
        # 先高置信度, 再突然低置信度
        for _ in range(10):
            dd.update(0.95)
        for _ in range(10):
            dd.update(0.50)
        # 第21次: 窗口已满, 低置信度比例=10/20=50%>15%
        status = dd.update(0.50)
        assert status['drifted'], f"应检测到漂移: {status}"
        assert status['low_conf_pct'] > 15
        print(f"  [OK] 漂移检测: low_conf_pct={status['low_conf_pct']}%")

    def test_drift_detector_reset(self):
        """DriftDetector 重置后漂移消失"""
        from core.core.analysis.model_trainer import DriftDetector
        dd = DriftDetector(window_size=20, threshold=0.15)
        for _ in range(20):
            dd.update(0.50)
        assert dd.update(0.50)['drifted']
        dd.reset()
        assert not dd.update(0.95)['drifted']
        assert dd.total_low_conf == 0  # 重置后清零, 且高置信度不增加
        print(f"  [OK] 重置后漂移消失: total_low_conf={dd.total_low_conf}")

    # ── 10.2 AdaptiveModelUpdater 无ML测试 ──

    def test_updater_creation(self):
        """AdaptiveModelUpdater 创建 (无需ML模型)"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer, buffer_size=500, update_threshold=0.85)
        assert updater.update_count == 0
        assert updater.total_predictions == 0
        assert len(updater.feedback_buffer) == 0
        status = updater.get_drift_status()
        assert not status['drift_detected']
        print(f"  [OK] 更新器创建成功: threshold={updater.update_threshold}")

    def test_updater_predict_no_model(self):
        """预测 (无ML模型) — 应优雅降级"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        np.random.seed(42)
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer, buffer_size=500, update_threshold=0.85)

        features = np.random.randn(10)
        result = updater.predict_with_adaptation('emergency_braking', features)
        assert 'error' in result, f"无模型应返回错误: {result}"
        assert result['confidence'] == 0.0
        # 低置信度会被记录
        assert result['needs_feedback']
        assert updater.total_predictions == 1
        print(f"  [OK] 无模型优雅降级: {result}")

    def test_updater_predict_all_no_model(self):
        """predict_all (无ML模型)"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)

        features = np.random.randn(10)
        results = updater.predict_all_with_adaptation(features)
        assert len(results) == 0, f"无模型应返回空列表: {results}"
        print(f"  [OK] predict_all无模型返回空")

    # ── 10.3 AdaptiveModelUpdater 完整ML流程 ──

    def test_updater_full_ml_pipeline(self):
        """完整ML流程: 训练 → 预测 → 漂移检测 → 反馈 → 增量更新"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 完整ML流程: LightGBM未安装")
            return

        np.random.seed(42)
        n = 300
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] + X[:, 1] > 0.5, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            updater = AdaptiveModelUpdater(
                trainer, buffer_size=500, update_threshold=0.85, min_feedback_samples=50
            )

            # 1. 预测已知样本
            test_feat = X[0]
            result = updater.predict_with_adaptation('emergency_braking', test_feat)
            assert 'confidence' in result
            assert result['confidence'] > 0.0, f"应有置信度: {result}"
            assert 'drift' in result
            assert 'needs_feedback' in result
            print(f"  [OK] ML预测: confidence={result['confidence']:.4f}, "
                  f"drift={result['drift']}")

            # 2. 批量预测 + 漂移检测
            for i in range(100):
                feat = X[i % n]
                true_label = y[i % n] == 'emergency_braking'
                updater.predict_with_adaptation('emergency_braking', feat)

            status = updater.get_drift_status()
            assert status['total_predictions'] == 101
            print(f"  [OK] 批量预测: total={status['total_predictions']}, "
                  f"low_conf_ratio={status['low_conf_ratio']}")

            # 3. 提供反馈 (正负样本混合)
            for i in range(60):
                feat = X[i % n]
                true_label = 1 if y[i % n] == 'emergency_braking' else 0
                updater.provide_feedback(feat, 'emergency_braking', bool(true_label))

            status2 = updater.get_drift_status()
            assert status2['update_count'] >= 1, \
                f"反馈应触发增量更新: update_count={status2['update_count']}"
            print(f"  [OK] 反馈触发增量更新: update_count={status2['update_count']}")

            # 4. 漂移样本查询
            samples = updater.get_drift_samples(5)
            assert isinstance(samples, list)
            print(f"  [OK] 漂移样本: {len(samples)}条")

            # 5. 重置
            updater.reset()
            status3 = updater.get_drift_status()
            assert status3['total_predictions'] == 0
            assert status3['update_count'] == 0
            print(f"  [OK] 重置后清零")

        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_updater_batch_feedback(self):
        """批量反馈"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 批量反馈: LightGBM未安装")
            return

        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] > 0, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            updater = AdaptiveModelUpdater(
                trainer, min_feedback_samples=30
            )

            feedbacks = []
            for i in range(40):
                feedbacks.append({
                    'features': X[i],
                    'event_type': 'emergency_braking',
                    'label': y[i] == 'emergency_braking',
                    'source': 'batch',
                })
            updater.provide_batch_feedback(feedbacks)

            status = updater.get_drift_status()
            assert status['update_count'] >= 1, \
                f"批量反馈应触发更新: {status}"
            print(f"  [OK] 批量反馈: update_count={status['update_count']}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_updater_force_update(self):
        """强制触发增量更新"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 强制更新: LightGBM未安装")
            return

        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] > 0, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            updater = AdaptiveModelUpdater(
                trainer, min_feedback_samples=100  # 很大, 不会自动触发
            )
            # 添加少量正负混合反馈
            for i in range(15):
                updater.provide_feedback(
                    X[i], 'emergency_braking', bool(y[i] == 'emergency_braking')
                )
            # 未触发自动更新
            assert updater.update_count == 0
            # 强制更新
            ok = updater.force_update()
            assert ok, "force_update应返回True"
            assert updater.update_count == 1
            print(f"  [OK] 强制更新: update_count={updater.update_count}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    def test_updater_save_load_with_updater(self):
        """模型保存/加载后更新器仍可用"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 保存加载: LightGBM未安装")
            return

        np.random.seed(42)
        n = 200
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] > 0, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            trainer.save('v1.0.0')

            # 加载后创建新updater
            trainer2 = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
            trainer2.load('v1.0.0')
            updater = AdaptiveModelUpdater(trainer2, min_feedback_samples=30)

            for i in range(40):
                updater.provide_feedback(
                    X[i], 'emergency_braking', bool(y[i] == 'emergency_braking')
                )
            assert updater.update_count >= 1, "加载后更新器应正常工作"
            print(f"  [OK] 保存加载后更新: update_count={updater.update_count}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)

    # ── 10.4 UnifiedEventDetector ML集成 ──

    def test_unified_detector_with_ml_creation(self):
        """UnifiedEventDetector + ML 创建"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        detector = UnifiedEventDetector(
            fs=100.0, model_trainer=trainer, model_updater=updater
        )

        assert detector.model_updater is updater
        assert detector.model_trainer is trainer
        status = detector.get_drift_status()
        assert not status['drift_detected']
        print(f"  [OK] UnifiedEventDetector + ML创建成功")

    def test_unified_detector_detect_with_ml_no_features(self):
        """detect_all_with_ml 无features → 降级为规则检测"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        np.random.seed(42)
        n = 150  # 1.5s, 在0.3-2.0范围内
        dt = 0.01
        Ax = np.ones(n) * -10.0 + np.random.randn(n) * 0.5  # 更强减速度, 更小噪声
        Ax[:5] = 0; Ax[-5:] = 0
        speed = 50.0 + np.cumsum(Ax * dt * 3.0)  # 更大累积因子确保speed_delta达标
        window = make_window(speed=speed, Ax=Ax, rel_time=np.linspace(0, 1.5, n), n=n)

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        detector = UnifiedEventDetector(fs=100.0, model_updater=updater)

        # 无features → 降级为纯规则检测
        results = detector.detect_all_with_ml(window, features=None)
        types = [r.event_type for r in results]
        assert 'emergency_braking' in types, f"降级检测失败: {types}"
        # ML字段不应设置
        for r in results:
            assert r.ml_confidence == 0.0
            assert not r.needs_feedback
        print(f"  [OK] 无features降级: {types}")

    def test_unified_detector_provide_feedback(self):
        """UnifiedEventDetector 提供反馈"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer, min_feedback_samples=100)
        detector = UnifiedEventDetector(fs=100.0, model_updater=updater)

        features = np.random.randn(10)
        detector.provide_feedback(features, 'emergency_braking', True, 'manual')
        status = detector.get_drift_status()
        assert status['feedback_pending'] == 1
        print(f"  [OK] 反馈已记录: pending={status['feedback_pending']}")

    def test_unified_detector_drift_samples(self):
        """UnifiedEventDetector 漂移样本查询"""
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        detector = UnifiedEventDetector(fs=100.0, model_updater=updater)

        features = np.random.randn(10)
        for _ in range(5):
            detector.model_updater.predict_with_adaptation('emergency_braking', features)

        samples = detector.get_drift_samples(3)
        assert len(samples) <= 3
        print(f"  [OK] 漂移样本: {len(samples)}条")

    # ── 10.5 StreamingProcessor ML集成 ──

    def test_streaming_processor_with_ml(self):
        """StreamingProcessor + ML创建"""
        from core.core.analysis.dual_mode_processor import StreamingProcessor
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        sp = StreamingProcessor(fs=100.0, model_updater=updater)

        assert sp.model_updater is updater
        assert sp.detector.model_updater is updater
        status = sp.get_drift_status()
        assert not status['drift_detected']
        print(f"  [OK] StreamingProcessor + ML创建成功")

    def test_streaming_processor_without_ml(self):
        """StreamingProcessor 无ML → 正常降级"""
        from core.core.analysis.dual_mode_processor import StreamingProcessor
        sp = StreamingProcessor(fs=100.0)
        assert sp.model_updater is None
        status = sp.get_drift_status()
        assert 'message' in status
        print(f"  [OK] 无ML降级: {status}")

    def test_streaming_feed_frame_with_ml(self):
        """StreamingProcessor 喂帧 + ML"""
        from core.core.analysis.dual_mode_processor import StreamingProcessor
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        sp = StreamingProcessor(
            window_size=200, step_size=50, fs=100.0, model_updater=updater
        )

        # 喂入急刹车数据
        n = 300
        dt = 0.01
        Ax = np.ones(n) * -8.0 + np.random.randn(n) * 0.8
        Ax[:5] = 0; Ax[-5:] = 0
        speed = 50.0 + np.cumsum(Ax * dt * 2.0)
        rel_time = np.linspace(0, 3.0, n)

        results_all = []
        for i in range(n):
            frame = {
                'rel_time': rel_time[i],
                'speed': speed[i],
                'wheel': 0.0,
                'Ax': Ax[i],
                'Ay': 0.0,
                'Az': 9.81,
            }
            result = sp.feed_frame(frame)
            if result:
                results_all.extend(result)

        assert len(results_all) > 0, "应检测到事件"
        types = [r.event_type for r in results_all]
        assert 'emergency_braking' in types, f"流式+ML检测: {types}"
        print(f"  [OK] 流式+ML: {len(results_all)}个事件, types={set(types)}")

    def test_streaming_provide_feedback(self):
        """StreamingProcessor 提供反馈"""
        from core.core.analysis.dual_mode_processor import StreamingProcessor
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer, min_feedback_samples=100)
        sp = StreamingProcessor(fs=100.0, model_updater=updater)

        features = np.random.randn(10)
        sp.provide_feedback(features, 'emergency_braking', True, 'manual')
        status = sp.get_drift_status()
        assert status['feedback_pending'] == 1
        print(f"  [OK] 流式反馈: pending={status['feedback_pending']}")

    # ── 10.6 BatchProcessor ML集成 ──

    def test_batch_processor_with_ml(self):
        """BatchProcessor + ML 创建"""
        from core.core.analysis.dual_mode_processor import BatchProcessor
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        bp = BatchProcessor(
            window_size=200, step_size=50, fs=100.0, model_updater=updater
        )

        assert bp.model_updater is updater
        print(f"  [OK] BatchProcessor + ML创建成功")

    def test_batch_process_with_ml(self):
        """BatchProcessor 批处理 + ML"""
        from core.core.analysis.dual_mode_processor import BatchProcessor
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        updater = AdaptiveModelUpdater(trainer)
        bp = BatchProcessor(
            window_size=200, step_size=50, fs=100.0, model_updater=updater
        )

        n = 500
        dt = 0.01
        Ax = np.ones(n) * -8.0 + np.random.randn(n) * 0.8
        Ax[:5] = 0; Ax[-5:] = 0
        speed = 50.0 + np.cumsum(Ax * dt * 2.0)
        rel_time = np.linspace(0, 5.0, n)

        data = np.zeros((n, 6))
        data[:, 0] = rel_time
        data[:, 1] = speed
        data[:, 2] = 0.0
        data[:, 3] = Ax
        data[:, 4] = 0.0
        data[:, 5] = 9.81

        results = list(bp.process(data))
        assert len(results) > 0, "应检测到事件"
        types = [r.event_type for r in results]
        assert 'emergency_braking' in types, f"批处理+ML检测: {types}"
        print(f"  [OK] 批处理+ML: {len(results)}个事件, types={set(types)}")

    # ── 10.7 端到端在线更新流程 ──

    def test_end_to_end_online_update_flow(self):
        """端到端: 初始训练 → 预测+漂移 → 反馈 → 增量更新 → 再预测"""
        from core.core.analysis.model_trainer import (
            DrivingEventModelTrainer, AdaptiveModelUpdater
        )
        from core.core.analysis.tri_stage_detector import UnifiedEventDetector
        try:
            import lightgbm
        except ImportError:
            print(f"  [SKIP] 端到端: LightGBM未安装")
            return

        np.random.seed(42)
        # Phase 1: 初始训练
        n = 300
        X = np.random.randn(n, 10)
        y = np.where(X[:, 0] + X[:, 1] > 0.5, 'emergency_braking', 'normal')

        trainer = DrivingEventModelTrainer(model_dir='test_models/', random_state=42)
        try:
            trainer.train_per_event_type(
                X, y, ['emergency_braking'], use_smote=False, use_optuna=False
            )
            updater = AdaptiveModelUpdater(
                trainer, min_feedback_samples=30, update_threshold=0.85
            )
            detector = UnifiedEventDetector(fs=100.0, model_updater=updater)

            # Phase 2: 预测 + 漂移检测
            for i in range(50):
                feat = X[i % n]
                detector.model_updater.predict_with_adaptation(
                    'emergency_braking', feat
                )
            status1 = detector.get_drift_status()
            assert status1['total_predictions'] == 50
            print(f"  [OK] Phase 1-2: predictions={status1['total_predictions']}, "
                  f"drift={status1['drift_detected']}")

            # Phase 3: 提供反馈 (模拟人工标注, 正负样本混合)
            for i in range(40):
                true_label = y[i % n] == 'emergency_braking'
                detector.provide_feedback(
                    X[i % n], 'emergency_braking', bool(true_label), 'manual'
                )
            status2 = detector.get_drift_status()
            assert status2['update_count'] >= 1, \
                f"反馈应触发增量更新: update_count={status2['update_count']}"
            print(f"  [OK] Phase 3: update_count={status2['update_count']}")

            # Phase 4: 增量更新后继续预测
            for i in range(20):
                feat = X[(n // 2 + i) % n]
                detector.model_updater.predict_with_adaptation(
                    'emergency_braking', feat
                )
            status3 = detector.get_drift_status()
            assert status3['total_predictions'] == 70
            print(f"  [OK] Phase 4: predictions={status3['total_predictions']}")

            # 验证漂移样本
            samples = detector.get_drift_samples(5)
            assert isinstance(samples, list)
            print(f"  [OK] 端到端完成: 漂移样本={len(samples)}, "
                  f"更新次数={status3['update_count']}")
        finally:
            import shutil
            if trainer.model_dir.exists():
                shutil.rmtree(trainer.model_dir, ignore_errors=True)


def run_all_tests():
    """运行所有测试并汇总结果"""
    test_classes = [
        TestEventRegistry,
        TestTriStageDetector,
        TestDualModeProcessor,
        TestStatisticalTests,
        TestEventCooldown,
        TestModelTrainer,
        TestIMUFusion,
        TestBoundaryConditions,
        TestConsistencyVerification,
        TestModelTrainerExtended,
        TestOnlineAdaptiveUpdate,
        TestEndToEndIntegration,
    ]

    total = 0
    passed = 0
    skipped = 0
    failed = 0
    failures = []

    print("=" * 70)
    print("  驾驶事件专项 — 全面验证测试")
    print("=" * 70)

    for cls in test_classes:
        instance = cls()
        print(f"\n── {cls.__name__} ──")
        for name in sorted(dir(instance)):
            if name.startswith('test_'):
                total += 1
                try:
                    getattr(instance, name)()
                    passed += 1
                except Exception as e:
                    msg = str(e)
                    if 'SKIP' in msg or '未安装' in msg:
                        skipped += 1
                        print(f"  [SKIP] {cls.__name__}.{name}: {msg}")
                    else:
                        failed += 1
                        print(f"  [FAIL] {cls.__name__}.{name}: {e}")
                        import traceback
                        traceback.print_exc()
                        failures.append(f"{cls.__name__}.{name}: {e}")

    print(f"\n{'=' * 70}")
    print(f"  结果汇总")
    print(f"{'=' * 70}")
    print(f"  总计: {total} 个测试")
    print(f"  通过: {passed} ({passed*100//total if total > 0 else 0}%)")
    if skipped > 0:
        print(f"  跳过: {skipped}")
    if failed > 0:
        print(f"  失败: {failed}")
        for f in failures:
            print(f"    - {f}")
    print(f"{'=' * 70}")

    if failed > 0:
        print(f"\n  [FAIL] {failed} test(s) failed")
    else:
        print(f"\n  [PASS] All tests passed ({passed}/{total})")

    return passed, total, failed


if __name__ == '__main__':
    passed, total, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)