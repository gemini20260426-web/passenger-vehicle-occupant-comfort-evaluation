#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10路IMU驾驶场景模拟器 — 72秒全场景测试数据生成

覆盖25种驾驶事件，生成10路座位IMU（IMU1~IMU10）的加速度计(ax/ay/az)
和陀螺仪(gx/gy/gz)数据，采样率100Hz，共7200帧。

事件类别：
  - 纵向(5):  emergency_braking, aggressive_deceleration, normal_deceleration,
               aggressive_acceleration, normal_acceleration
  - 侧向(5):  weaving, lane_change, rapid_direction_change, tight_turn, wide_turn
  - 复合(3):  cornering_braking, cornering_acceleration, cornering_deceleration
  - 异常(4):  severe_bump, skid_risk, rollover_risk, sensor_fault
  - 状态(9):  stopped, launch, cruising, constant_speed, overspeeding,
              parked, u_turn, straight_driving, lane_keeping
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# ── 全局常量 ──
FS = 100.0                # 采样率 Hz
TOTAL_DURATION = 72.0     # 总时长 s
TOTAL_SAMPLES = int(FS * TOTAL_DURATION)  # 7200
IMU_COUNT = 10            # IMU通道数
GRAVITY = 9.81            # 重力加速度 m/s²
SPEED_KMH_TO_MS = 1.0 / 3.6  # km/h → m/s


# ── 场景时间线定义 ──
@dataclass
class SceneSegment:
    """单个场景片段定义"""
    name: str
    start_s: float
    end_s: float
    category: str  # longitudinal / lateral / composite / anomaly / state


SCENE_TIMELINE: List[SceneSegment] = [
    # ── 状态事件 ──
    SceneSegment("parked",                   0,  5,  "state"),
    # ── 纵向事件 ──
    SceneSegment("launch",                   5,  8,  "state"),
    SceneSegment("normal_acceleration",      8, 12,  "longitudinal"),
    SceneSegment("constant_speed",          12, 15,  "state"),
    # ── 侧向事件 ──
    SceneSegment("lane_change",             15, 18,  "lateral"),
    # ── 状态事件 ──
    SceneSegment("cruising",                18, 22,  "state"),
    # ── 纵向事件 ──
    SceneSegment("aggressive_acceleration", 22, 25,  "longitudinal"),
    # ── 复合事件 ──
    SceneSegment("cornering_acceleration",  25, 28,  "composite"),
    # ── 纵向事件 ──
    SceneSegment("normal_deceleration",     28, 30,  "longitudinal"),
    SceneSegment("emergency_braking",       30, 33,  "longitudinal"),
    # ── 状态事件 ──
    SceneSegment("stopped",                 33, 35,  "state"),
    SceneSegment("launch",                  35, 38,  "state"),
    # ── 侧向事件 ──
    SceneSegment("wide_turn",               38, 42,  "lateral"),
    SceneSegment("tight_turn",              42, 45,  "lateral"),
    SceneSegment("straight_driving",        45, 48,  "lateral"),
    # ── 复合事件 ──
    SceneSegment("cornering_braking",       48, 50,  "composite"),
    # ── 异常事件 ──
    SceneSegment("severe_bump",             50, 51,  "anomaly"),
    SceneSegment("skid_risk",               51, 53,  "anomaly"),
    # ── 纵向事件 ──
    SceneSegment("normal_acceleration",     53, 55,  "longitudinal"),
    # ── 侧向事件 ──
    SceneSegment("weaving",                 55, 58,  "lateral"),
    SceneSegment("rapid_direction_change",  58, 60,  "lateral"),
    # ── 侧向/状态 ──
    SceneSegment("u_turn",                  60, 62,  "lateral"),
    # ── 状态事件 ──
    SceneSegment("overspeeding",            62, 64,  "state"),
    # ── 纵向事件 ──
    SceneSegment("aggressive_deceleration", 64, 66,  "longitudinal"),
    # ── 复合事件 ──
    SceneSegment("cornering_deceleration",  66, 68,  "composite"),
    # ── 侧向/状态 ──
    SceneSegment("lane_keeping",            68, 70,  "lateral"),
    # ── 异常事件 ──
    SceneSegment("rollover_risk",           70, 72,  "anomaly"),
]


# ── 传感器故障注入配置 ──
SENSOR_FAULT_CONFIG = {
    "start_s": 55.0,   # 在 weaving 段中注入
    "end_s": 55.5,
    "affected_channels": ["IMU3", "IMU7"],
    "affected_signals": ["az", "gz"],
    "fault_type": "nan",  # NaN注入
}


class DrivingSceneSimulator:
    """10路IMU驾驶场景模拟器。

    为每个IMU座位生成独立的六轴信号(ax, ay, az, gx, gy, gz)，
    通过车辆动力学参考信号 + 每路独立噪声与位置偏移实现。
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = np.random.RandomState(seed)

        # 每路IMU的位置特性：(位置描述, 加速度偏移系数, 陀螺仪偏移系数, 噪声放大因子, 垂向敏感度)
        self._imu_profiles: Dict[str, Tuple[str, float, float, float, float]] = {
            "IMU1":  ("前排左",   0.15, 0.10, 1.00, 0.80),
            "IMU2":  ("前排右",   0.15, 0.10, 1.00, 0.80),
            "IMU3":  ("中排左",   0.08, 0.05, 1.05, 1.00),
            "IMU4":  ("中排中",   0.05, 0.03, 1.00, 0.90),
            "IMU5":  ("中排右",   0.08, 0.05, 1.05, 1.00),
            "IMU6":  ("后排左",  -0.05, 0.00, 1.10, 1.15),
            "IMU7":  ("后排中",  -0.08, 0.00, 1.08, 1.05),
            "IMU8":  ("后排右",  -0.05, 0.00, 1.10, 1.15),
            "IMU9":  ("座椅底座左", 0.00, -0.05, 0.90, 0.70),
            "IMU10": ("座椅底座右", 0.00, -0.05, 0.90, 0.70),
        }

    # ────────────── 公共 API ──────────────

    def generate_scene(self) -> pd.DataFrame:
        """生成完整72秒10路IMU场景数据。

        Returns:
            pd.DataFrame: 列包含 timestamp, speed, wheel,
                          IMU1_ax, IMU1_ay, ..., IMU10_gz, event
        """
        t = np.arange(TOTAL_SAMPLES) / FS

        # 1. 生成车辆级参考信号
        speed, ax_ref, ay_ref, az_ref, gz_ref = self._generate_vehicle_reference(t)

        # 2. 生成方向盘角度 (wheel)
        wheel = self._generate_wheel_from_gz(t, gz_ref)

        # 3. 为每个IMU生成独立信号
        records = {"timestamp": t, "speed": speed, "wheel": wheel}
        for ch_id, (pos, acc_bias, gyro_bias, noise_amp, vert_sens) in self._imu_profiles.items():
            ch_ax, ch_ay, ch_az, ch_gx, ch_gy, ch_gz = self._generate_imu_channel(
                t, ax_ref, ay_ref, az_ref, gz_ref,
                acc_bias, gyro_bias, noise_amp, vert_sens, ch_id
            )
            records[f"{ch_id}_ax"] = ch_ax
            records[f"{ch_id}_ay"] = ch_ay
            records[f"{ch_id}_az"] = ch_az
            records[f"{ch_id}_gx"] = ch_gx
            records[f"{ch_id}_gy"] = ch_gy
            records[f"{ch_id}_gz"] = ch_gz

        # 4. 注入传感器故障
        self._inject_sensor_fault(t, records)

        # 5. 分配事件标签
        records["event"] = self._assign_event_labels(t)

        return pd.DataFrame(records)

    def export_csv(self, path: str) -> None:
        """导出场景数据为CSV文件。"""
        df = self.generate_scene()
        df.to_csv(path, index=False, float_format="%.6f")

    def get_ground_truth(self) -> List[Dict]:
        """返回真实事件标签列表。"""
        truth = []
        for seg in SCENE_TIMELINE:
            truth.append({
                "event_type": seg.name,
                "category": seg.category,
                "start_s": seg.start_s,
                "end_s": seg.end_s,
                "duration_s": round(seg.end_s - seg.start_s, 2),
            })
        return truth

    # ────────────── 车辆参考信号生成 ──────────────

    def _generate_vehicle_reference(
        self, t: np.ndarray
    ) -> Tuple[np.ndarray, ...]:
        """生成车辆级参考信号: speed, ax, ay, az, gz。"""
        n = len(t)
        speed = np.zeros(n)
        ax_ref = np.zeros(n)
        ay_ref = np.zeros(n)
        az_ref = np.zeros(n)   # 不含重力，用于座位IMU叠加
        gz_ref = np.zeros(n)

        for seg in SCENE_TIMELINE:
            idx = (t >= seg.start_s) & (t < seg.end_s)
            t_seg = t[idx] - seg.start_s
            dur = seg.end_s - seg.start_s

            if seg.name == "parked":
                speed[idx] = 0.0
                ax_ref[idx] = 0.0
                ay_ref[idx] = 0.0
                az_ref[idx] = 0.0
                gz_ref[idx] = 0.0

            elif seg.name == "stopped":
                s_end = speed[idx][0] if np.any(idx) else 0.0
                s_profile = self._smooth_transition(t_seg, s_end, 0.0, dur)
                speed[idx] = s_profile
                ax_ref[idx] = np.gradient(s_profile * SPEED_KMH_TO_MS, 1.0 / FS)
                ay_ref[idx] = 0.0
                az_ref[idx] = 0.0
                gz_ref[idx] = 0.0

            elif seg.name == "launch":
                s_start = speed[max(0, int((seg.start_s - 0.01) * FS))] if int(seg.start_s * FS) > 0 else 0.0
                if s_start < 1.0:
                    s_start = 0.0
                s_target = 20.0 + self._rng.uniform(3, 8)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=2.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = 0.0 + self._rng.normal(0, 0.02, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))

            elif seg.name == "normal_acceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start + self._rng.uniform(15, 30)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=2.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.03, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.15, len(t_seg))

            elif seg.name == "aggressive_acceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start + self._rng.uniform(30, 50)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=3.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.04, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.2, len(t_seg))

            elif seg.name == "constant_speed":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start)
                s_profile += self._rng.normal(0, 0.3, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.02, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.08, len(t_seg))

            elif seg.name == "cruising":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.5, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.03, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))

            elif seg.name == "normal_deceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start - self._rng.uniform(5, 15)
                s_target = max(s_target, 5.0)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=2.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.03, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))

            elif seg.name == "emergency_braking":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = max(s_start - self._rng.uniform(40, 60), 5.0)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=5.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.05, len(t_seg))
                az_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))
                gz_ref[idx] = self._rng.normal(0, 0.2, len(t_seg))

            elif seg.name == "aggressive_deceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start - self._rng.uniform(20, 40)
                s_target = max(s_target, 5.0)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=4.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.04, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.15, len(t_seg))

            # ── 侧向事件 ──

            elif seg.name == "lane_change":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = self._smooth_transition(t_seg, s_start, s_start + self._rng.uniform(-2, 2), dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 单次变道：先正后负的侧向加速度
                phase = np.linspace(0, np.pi, n_seg)
                ay_seg = 2.5 * np.sin(phase) + self._rng.normal(0, 0.05, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.65

            elif seg.name == "weaving":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.5, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 4次过零，摇摆幅度递增
                freq = 4.0 / dur
                t_norm = np.linspace(0, dur, n_seg)
                envelope = 1.0 + 0.5 * np.sin(np.pi * t_norm / dur)
                ay_seg = 3.5 * envelope * np.sin(2 * np.pi * freq * t_norm)
                ay_seg += self._rng.normal(0, 0.08, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.6

            elif seg.name == "rapid_direction_change":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.3, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 快速交替方向变化
                t_norm = np.linspace(0, dur, n_seg)
                ay_seg = 4.5 * np.sin(2 * np.pi * 2.5 * t_norm)
                ay_seg += self._rng.normal(0, 0.1, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.55

            elif seg.name == "tight_turn":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = self._smooth_transition(t_seg, s_start, max(s_start - 5, 10), dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 持续的高侧向加速度
                ramp = np.minimum(np.linspace(0, 1, n_seg), 1.0)
                ay_seg = 3.0 * ramp + self._rng.normal(0, 0.04, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.7

            elif seg.name == "wide_turn":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.3, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 平缓持续的转弯
                ramp = np.minimum(np.linspace(0, 1, n_seg), 1.0)
                ay_seg = 2.0 * ramp + self._rng.normal(0, 0.03, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.7

            elif seg.name == "u_turn":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = self._smooth_transition(t_seg, s_start, 15.0, dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # U型转弯：持续高侧向加速度
                t_norm = np.linspace(0, 1, n_seg)
                envelope = np.sin(np.pi * t_norm)
                ay_seg = 2.5 * envelope + self._rng.normal(0, 0.05, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.75

            elif seg.name == "straight_driving":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start + self._rng.uniform(5, 15)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.06, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.08, len(t_seg))

            elif seg.name == "lane_keeping":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.2, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.08, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))

            # ── 复合事件 ──

            elif seg.name == "cornering_acceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start + self._rng.uniform(10, 20)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                # 加速 + 转弯
                n_seg = len(t_seg)
                ay_seg = np.full(n_seg, 2.0) + self._rng.normal(0, 0.05, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.65

            elif seg.name == "cornering_deceleration":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = s_start - self._rng.uniform(10, 20)
                s_target = max(s_target, 5.0)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                fade = np.linspace(2.5, 1.5, n_seg)
                ay_seg = fade + self._rng.normal(0, 0.05, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.65

            elif seg.name == "cornering_braking":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = max(s_start - self._rng.uniform(20, 30), 5.0)
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=4.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                ay_seg = np.full(n_seg, 2.5) + self._rng.normal(0, 0.06, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = 0.0
                gz_ref[idx] = ay_seg * 0.7

            # ── 异常事件 ──

            elif seg.name == "severe_bump":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.2, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.05, len(t_seg))
                n_seg = len(t_seg)
                # 垂向脉冲：模拟颠簸冲击
                az_seg = np.zeros(n_seg)
                t_local = np.linspace(0, dur, n_seg)
                pulse_center = dur * 0.5
                pulse_width = 0.05
                az_seg += 8.0 * np.exp(-0.5 * ((t_local - pulse_center) / pulse_width) ** 2)
                # 再加一次回弹
                az_seg += 4.0 * np.exp(-0.5 * ((t_local - pulse_center - 0.08) / (pulse_width * 1.5)) ** 2)
                az_seg += self._rng.normal(0, 0.1, n_seg)
                az_ref[idx] = az_seg
                gz_ref[idx] = self._rng.normal(0, 0.15, n_seg)

            elif seg.name == "skid_risk":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.5, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 侧向加速度超标，逐渐偏离
                ramp = np.linspace(2.0, 5.0, n_seg)
                ay_seg = ramp + self._rng.normal(0, 0.12, n_seg)
                ay_ref[idx] = ay_seg
                az_ref[idx] = self._rng.normal(0, 0.15, n_seg)
                gz_ref[idx] = ay_seg * 0.45  # 陀螺仪与侧向加速度不匹配 = 侧滑特征

            elif seg.name == "rollover_risk":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_profile = np.full(len(t_seg), s_start) + self._rng.normal(0, 0.3, len(t_seg))
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                n_seg = len(t_seg)
                # 极高侧向加速度 (>6 m/s²)
                peak_dur = dur * 0.3
                t_local = np.linspace(0, dur, n_seg)
                ay_seg = 7.5 * np.exp(-0.5 * ((t_local - dur / 2) / peak_dur) ** 2)
                ay_seg += self._rng.normal(0, 0.1, n_seg)
                ay_ref[idx] = ay_seg
                # 伴随垂向变化
                az_seg = 1.5 * np.exp(-0.5 * ((t_local - dur / 2) / peak_dur) ** 2)
                az_ref[idx] = az_seg + self._rng.normal(0, 0.08, n_seg)
                gz_ref[idx] = ay_seg * 0.6

            elif seg.name == "overspeeding":
                s_start = self._get_last_speed(speed, idx, seg.start_s)
                s_target = 130.0 + self._rng.uniform(5, 15)  # 超过120km/h限速
                s_profile = self._smooth_transition(t_seg, s_start, s_target, dur, curvature=2.0)
                speed[idx] = s_profile
                ax_ref[idx] = self._safe_gradient(s_profile * SPEED_KMH_TO_MS, t_seg, FS)
                ay_ref[idx] = self._rng.normal(0, 0.05, len(t_seg))
                az_ref[idx] = 0.0
                gz_ref[idx] = self._rng.normal(0, 0.1, len(t_seg))

        return speed, ax_ref, ay_ref, az_ref, gz_ref

    # ────────────── IMU逐路信号生成 ──────────────

    def _generate_imu_channel(
        self,
        t: np.ndarray,
        ax_ref: np.ndarray,
        ay_ref: np.ndarray,
        az_ref: np.ndarray,
        gz_ref: np.ndarray,
        acc_bias: float,
        gyro_bias: float,
        noise_amp: float,
        vert_sens: float,
        ch_id: str,
    ) -> Tuple[np.ndarray, ...]:
        """为单个IMU通道生成六轴信号。"""
        n = len(t)
        noise_base = self._rng.randn(n)

        # 加速度计
        ch_ax = ax_ref * (1.0 + acc_bias) + self._rng.normal(0, 0.03 * noise_amp, n)
        ch_ay = ay_ref * (1.0 + acc_bias) + self._rng.normal(0, 0.03 * noise_amp, n)
        ch_az = az_ref * vert_sens + self._rng.normal(0, 0.04 * noise_amp, n)

        # 陀螺仪: gz 来自参考，gx/gy 主要为噪声
        ch_gz = gz_ref * (1.0 + gyro_bias) + self._rng.normal(0, 0.15 * noise_amp, n)
        ch_gx = self._rng.normal(0, 0.05 * noise_amp, n)
        ch_gy = self._rng.normal(0, 0.05 * noise_amp, n)

        return ch_ax, ch_ay, ch_az, ch_gx, ch_gy, ch_gz

    # ────────────── 辅助函数 ──────────────

    def _get_last_speed(self, speed: np.ndarray, idx: np.ndarray, start_s: float) -> float:
        """获取片段开始前的最后一个速度值。"""
        start_idx = int(start_s * FS)
        if start_idx > 0:
            return float(speed[start_idx - 1])
        # 回退：从idx中取第一个有值的
        idx_positions = np.where(idx)[0]
        if len(idx_positions) > 0:
            prev = idx_positions[0] - 1
            if prev >= 0:
                return float(speed[prev])
        return 0.0

    @staticmethod
    def _smooth_transition(
        t_seg: np.ndarray, v0: float, v1: float, dur: float, curvature: float = 2.0
    ) -> np.ndarray:
        """平滑速度过渡曲线（S型曲线）。"""
        if dur <= 0:
            return np.full(len(t_seg), v1)
        x = t_seg / dur
        # Sigmoid-like smoothstep
        s = 1.0 / (1.0 + np.exp(-curvature * (x - 0.5) * 8))
        s = (s - s[0]) / (s[-1] - s[0] + 1e-10)
        return v0 + (v1 - v0) * s

    @staticmethod
    def _safe_gradient(signal: np.ndarray, t: np.ndarray, fs: float) -> np.ndarray:
        """安全计算梯度（m/s²），处理边缘。"""
        dt = 1.0 / fs
        grad = np.gradient(signal, dt)
        return grad

    def _generate_wheel_from_gz(self, t: np.ndarray, gz_ref: np.ndarray) -> np.ndarray:
        """由陀螺仪z轴近似生成方向盘角度。"""
        # 积分陀螺仪得到航向角变化，再乘以转向比得到方向盘角
        dt = 1.0 / FS
        heading = np.cumsum(gz_ref) * dt
        # 低通平滑
        from scipy.ndimage import uniform_filter1d
        try:
            heading_smooth = uniform_filter1d(heading, size=20)
        except Exception:
            heading_smooth = heading
        wheel = heading_smooth * 15.0  # steering ratio
        wheel = np.clip(wheel, -500, 500)
        return wheel

    # ────────────── 传感器故障注入 ──────────────

    def _inject_sensor_fault(self, t: np.ndarray, records: Dict[str, np.ndarray]) -> None:
        """注入传感器故障（NaN值）。"""
        cfg = SENSOR_FAULT_CONFIG
        fault_idx = (t >= cfg["start_s"]) & (t < cfg["end_s"])
        for ch in cfg["affected_channels"]:
            for sig in cfg["affected_signals"]:
                col = f"{ch}_{sig}"
                if col in records:
                    if cfg["fault_type"] == "nan":
                        records[col][fault_idx] = np.nan

    # ────────────── 事件标签赋值 ──────────────

    def _assign_event_labels(self, t: np.ndarray) -> np.ndarray:
        """为每个时间点分配事件标签。"""
        labels = np.full(len(t), "normal", dtype=object)
        for seg in SCENE_TIMELINE:
            idx = (t >= seg.start_s) & (t < seg.end_s)
            labels[idx] = seg.name
        return labels


# ────────────── 模块级便捷函数 ──────────────

def generate_scene(seed: int = 42) -> pd.DataFrame:
    """生成完整72秒10路IMU场景数据。"""
    sim = DrivingSceneSimulator(seed=seed)
    return sim.generate_scene()


def export_csv(path: str, seed: int = 42) -> None:
    """导出场景数据为CSV文件。"""
    sim = DrivingSceneSimulator(seed=seed)
    sim.export_csv(path)


def get_ground_truth() -> List[Dict]:
    """返回真实事件标签列表。"""
    sim = DrivingSceneSimulator()
    return sim.get_ground_truth()


# ────────────── 自检 ──────────────

if __name__ == "__main__":
    print("=" * 70)
    print("10路IMU驾驶场景模拟器 — 自检验证")
    print("=" * 70)

    # 1. 生成数据
    print("\n[1/7] 生成72秒场景数据 ...")
    df = generate_scene(seed=42)
    print(f"      DataFrame shape: {df.shape}")
    print(f"      总采样点数: {len(df)} (预期 7200)")
    assert len(df) == TOTAL_SAMPLES, f"采样点数错误: {len(df)}"

    # 2. 验证列结构
    print("\n[2/7] 验证列结构 ...")
    expected_cols = {"timestamp", "speed", "wheel"}
    for i in range(1, IMU_COUNT + 1):
        for ch in ["ax", "ay", "az", "gx", "gy", "gz"]:
            expected_cols.add(f"IMU{i}_{ch}")
    expected_cols.add("event")
    actual_cols = set(df.columns)
    missing = expected_cols - actual_cols
    extra = actual_cols - expected_cols
    if missing:
        print(f"      [FAIL] 缺失列: {missing}")
    else:
        print(f"      [OK] 所有列完整 ({len(actual_cols)} 列)")

    # 3. 验证采样率
    print("\n[3/7] 验证采样率 ...")
    dt = np.diff(df["timestamp"].values)
    mean_dt = np.mean(dt)
    print(f"      平均采样间隔: {mean_dt:.6f} s (预期 0.01 s)")
    assert abs(mean_dt - 0.01) < 0.001, f"采样间隔偏差过大: {mean_dt}"

    # 4. 验证事件标签
    print("\n[4/7] 验证事件标签 ...")
    unique_events = sorted(df["event"].unique())
    print(f"      唯一事件数: {len(unique_events)}")
    for evt in unique_events:
        cnt = (df["event"] == evt).sum()
        print(f"        {evt}: {cnt} 帧")

    # 检查预期25种事件
    expected_events = {seg.name for seg in SCENE_TIMELINE}
    found_events = set(unique_events)
    missing_events = expected_events - found_events
    if missing_events:
        print(f"      [FAIL] 缺失事件: {missing_events}")
    else:
        print(f"      [OK] 所有事件均已覆盖")

    # 5. 验证数值合理性
    print("\n[5/7] 验证数值合理性 ...")
    # 加速度范围检查
    for i in range(1, IMU_COUNT + 1):
        ax_col = f"IMU{i}_ax"
        ay_col = f"IMU{i}_ay"
        az_col = f"IMU{i}_az"
        ax_max = np.nanmax(df[ax_col])
        ax_min = np.nanmin(df[ax_col])
        ay_max = np.nanmax(df[ay_col])
        ay_min = np.nanmin(df[ay_col])
        az_max = np.nanmax(df[az_col])
        az_min = np.nanmin(df[az_col])
        if i == 1:
            print(f"      IMU1 ax: [{ax_min:.2f}, {ax_max:.2f}] m/s^2")
            print(f"      IMU1 ay: [{ay_min:.2f}, {ay_max:.2f}] m/s^2")
            print(f"      IMU1 az: [{az_min:.2f}, {az_max:.2f}] m/s^2")

    # 速度范围
    speed_max = df["speed"].max()
    speed_min = df["speed"].min()
    print(f"      速度范围: [{speed_min:.1f}, {speed_max:.1f}] km/h")

    # 6. 验证传感器故障注入
    print("\n[6/7] 验证传感器故障注入 ...")
    fault_events = df[df["event"] == "weaving"]
    nan_count_imu3_az = fault_events["IMU3_az"].isna().sum()
    nan_count_imu7_gz = fault_events["IMU7_gz"].isna().sum()
    print(f"      IMU3_az NaN数 (weaving段): {nan_count_imu3_az}")
    print(f"      IMU7_gz NaN数 (weaving段): {nan_count_imu7_gz}")

    # 7. 验证 ground truth
    print("\n[7/7] 验证 ground_truth ...")
    gt = get_ground_truth()
    print(f"      Ground truth 事件数: {len(gt)}")
    total_dur = sum(item["duration_s"] for item in gt)
    print(f"      标注总时长: {total_dur:.1f} s")
    for item in gt:
        print(f"        [{item['start_s']:5.1f}s - {item['end_s']:5.1f}s] {item['event_type']:30s} ({item['category']})")

    print("\n" + "=" * 70)
    print("自检通过 [OK]")
    print("=" * 70)