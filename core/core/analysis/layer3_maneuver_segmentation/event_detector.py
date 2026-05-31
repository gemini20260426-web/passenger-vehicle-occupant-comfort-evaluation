#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶行为事件检测器 V3.0
—— 6组22种事件类型，参照专业检测算法

6组检测器:
  1. 速度基: 停车/驻车/恒速行驶/匀速直行/正常加速/正常减速
  2. 转向基: 车道保持/左转/右转/小半径转弯/大半径转弯/U型转弯
  3. 复合:   弯道加速/弯道减速
  4. 激进:   激进加速/激进减速/急刹车
  5. 动态:   蛇形驾驶/急速变向
  6. IMU基:  剧烈颠簸/侧滑风险/侧翻风险

参照: test_data/验证数据/驾驶行为检测算法.py DrivingEventDetector
"""

import numpy as np
import pandas as pd
from scipy import signal as scipy_signal
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# 事件类型中英文映射
# ──────────────────────────────────────────────
EVENT_TYPES = {
    # ── key 对齐 BEHAVIOR_LABELS_CN / MetadataRegistry._register_driving_states ──
    'constant_speed': '匀速直行',
    'normal_acceleration': '正常加速',
    'normal_deceleration': '正常减速',
    'cruising': '恒速行驶',
    'stopped': '停车',
    'parked': '驻车',
    'lane_keeping': '车道保持',
    'left_turn': '左转',
    'right_turn': '右转',
    'tight_turn': '小半径转弯',
    'wide_turn': '大半径转弯',
    'u_turn': 'U型转弯',
    'cornering_acceleration': '弯道加速',
    'cornering_deceleration': '弯道减速',
    'aggressive_acceleration': '激进加速',
    'aggressive_deceleration': '激进减速',
    'emergency_braking': '急刹车',
    'weaving': '蛇形驾驶',
    'rapid_direction_change': '急速变向',
    'severe_bump': '剧烈颠簸',
    'skid_risk': '侧滑风险',
    'rollover_risk': '侧翻风险',
}

# 事件类型 → 所属分组标签
EVENT_GROUPS = {
    'speed': ['stopped', 'parked', 'cruising', 'constant_speed',
              'normal_acceleration', 'normal_deceleration'],
    'steering': ['lane_keeping', 'left_turn', 'right_turn',
                 'tight_turn', 'wide_turn', 'u_turn'],
    'compound': ['cornering_acceleration', 'cornering_deceleration'],
    'aggressive': ['aggressive_acceleration', 'aggressive_deceleration', 'emergency_braking'],
    'dynamic': ['weaving', 'rapid_direction_change'],
    'imu': ['severe_bump', 'skid_risk', 'rollover_risk'],
}


@dataclass
class Event:
    """驾驶行为事件"""
    event_id: int
    event_type: str
    event_name: str
    t_start: float           # 开始时间 (s)
    t_end: float             # 结束时间 (s)
    duration_s: float        # 持续时间 (s)
    confidence: float        # 置信度 0-1
    features: Dict = field(default_factory=dict)

    # ---- EventDistributor 兼容别名 ----
    @property
    def id(self): return self.event_id
    @property
    def type(self): return self.event_type
    @property
    def label_cn(self): return self.event_name
    @property
    def start_time(self): return self.t_start
    @property
    def end_time(self): return self.t_end
    @property
    def duration(self): return self.duration_s
    @property
    def risk_score(self): return self.features.get('risk_score', self.confidence)
    @property
    def risk_level(self): return 'safe'
    @property
    def peak_ax(self): return self.features.get('accel_max', 0)
    @property
    def peak_ay(self): return self.features.get('ay_max', 0)
    @property
    def peak_jerk(self): return self.features.get('jerk', 0)
    @property
    def speed_range(self): return self.features.get('speed_range', 0)
    @property
    def category(self):
        try:
            return EVENT_TYPE_CATEGORY.get(self.event_type, 'unknown')
        except NameError:
            return 'maneuver'

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'event_name': self.event_name,
            't_start': round(self.t_start, 3),
            't_end': round(self.t_end, 3),
            'duration_s': round(self.duration_s, 3),
            'confidence': round(self.confidence, 3),
            'features': {k: round(v, 4) if isinstance(v, float) else v
                         for k, v in self.features.items()},
        }


class DrivingEventDetector:
    """22种驾驶行为事件检测器

    Usage:
        detector = DrivingEventDetector.from_records(records)
        events = detector.detect_all()
        # events: List[Event], 按 t_start 排序
    """

    # ── 阈值参数 ──
    # 速度基
    STOP_SPEED = 3.0            # km/h (停车判定, 含逐渐减速至停车边界)
    PARK_DURATION = 0.5        # s, 驻车最小持续 (was 1.0)
    STOP_MIN_DUR = 0.3         # s
    CRUISE_MIN_SPEED = 5.0     # km/h
    CRUISE_MIN_DUR = 1.0
    CRUISE_MAX_GAP = 2.0       # s, 恒速行驶合并间隙（跨越转向/加速等短暂事件）
    CONST_SPEED_STD = 1.5      # km/h, 匀速直行标准差 (降低捕获匀速段)
    NORMAL_ACCEL_LOW = 0.5     # m/s² (专家级: accel_ma_expert > 0.5)
    NORMAL_ACCEL_HIGH = 3.0    # m/s²
    NORMAL_DECEL_LOW = -3.0    # m/s²
    NORMAL_DECEL_HIGH = -0.5   # m/s² (专家级)
    SPEED_CHANGE_MIN = 1.0     # km/h, 加/减速最少速度变化

    # 转向基
    WHEEL_STRAIGHT = 1.5       # deg, 直行方向盘角阈值 (abs) (放宽捕获车道保持)
    WHEEL_TURN = 1.5           # deg, 转向入口 (降低捕获细微转向)
    WHEEL_TIGHT = 15.0         # deg, 小半径转弯
    WHEEL_WIDE_LOW = 3.0       # deg
    WHEEL_WIDE_HIGH = 15.0     # deg
    WHEEL_STD_U = 5.0          # deg, U型转弯 std阈值
    WHEEL_RANGE_U = 30.0       # deg, U型转弯 range阈值
    LANE_KEEP_MIN_DUR = 1.5    # s (降低捕获短时车道保持)
    TURN_MIN_DUR = 0.25        # s (降低捕获短转向)
    TURN_MAX_GAP = 0.5         # s, 转向合并间隙 (合并碎片化转向段)

    # 复合
    CORNER_WHEEL = 3.0         # deg, 弯道判定 abs(wheel)

    # 激进
    AGGRESSIVE_ACCEL = 3.0     # m/s² (专家级: vehicle_accel_expert > 3.0 ≈ 0.3g)
    AGGRESSIVE_DECEL = -3.0    # m/s² (专家级)
    AGGRESSIVE_MAX_GAP = 0.5   # s, 合并相邻激进加速段的间隙（避免吞并巡航段）
    HARD_BRAKE_DECEL = -5.0    # m/s² (专家级: ≈ 0.5g)
    HARD_BRAKE_MIN_SPEED = 5.0 # km/h

    # 动态
    SLALOM_WINDOW = 0.75       # s, 检测窗口 (匹配专家0.75s窗口)
    SLALOM_STEP = 0.15         # s, 滑动步长 (细化粒度)
    SLALOM_ZC_MIN = 2          # 过零点次数
    SLALOM_WHEEL_RANGE = 3.0   # deg (专家级: 降至3°捕获细微蛇形)
    SLALOM_MIN_SPEED = 5.0     # km/h (降低门槛覆盖低速蛇形)
    STEER_RATE_THRESH = 30.0   # deg/s, 急速变向 (降低触发门槛)
    RAPID_LC_MIN_SPEED = 5.0   # km/h
    RAPID_DIR_MIN_DUR = 0.5    # s, 急速变向最少持续
    RAPID_STEER_SWING = 15.0   # deg, 方向反转幅度 (连续反向打方向盘)

    # IMU基
    SEVERE_BUMP_AZ = 15.0      # m/s², 垂向加速度
    SIDE_SLIP_AY = 5.0         # m/s², 侧向加速度
    ROLLOVER_AY = 6.0          # m/s²
    ROLLOVER_GX = 20.0         # rad/s
    IMU_MIN_SPEED = 20.0       # km/h, 侧滑/侧翻最低速度

    def __init__(self):
        self.t: np.ndarray = None
        self.speed: np.ndarray = None       # km/h
        self.wheel: np.ndarray = None       # deg
        self.vehicle_accel: np.ndarray = None  # m/s² (来自 SpeedPreprocessor)
        self.vehicle_accel_expert: np.ndarray = None  # m/s² (专家算法: gradient→/3.6→Butterworth 5Hz, 无裁剪)
        self.accel_ma_expert: np.ndarray = None  # m/s² (专家 accel_ma: vehicle_accel_expert 的 0.5s 滑动均值)
        self.steer_rate: np.ndarray = None  # deg/s
        self.speed_ma: np.ndarray = None    # 滚动均值
        self.speed_std: np.ndarray = None
        self.wheel_std: np.ndarray = None
        self.accel_ma: np.ndarray = None
        # IMU
        self.ax: np.ndarray = None
        self.ay: np.ndarray = None
        self.az: np.ndarray = None
        self.gx: np.ndarray = None
        self.gy: np.ndarray = None
        self.gz: np.ndarray = None
        # 衍生
        self.a_lat: np.ndarray = None   # |ay|
        self.a_vert: np.ndarray = None  # |az|
        self.roll_rate: np.ndarray = None  # |gx|
        # 内部
        self.dt: float = 0.001
        self.fs: float = 1000.0
        self.events: List[Event] = []
        self._eid: int = 0

    # ──────────────────────────────────────────
    # 工厂方法
    # ──────────────────────────────────────────

    @classmethod
    def from_records(cls, records: List[Dict], ref_channel: str = 'ch1',
                     ref_imu: str = 'IMU1_头部眉心-1') -> 'DrivingEventDetector':
        """从解析数据记录列表创建检测器

        Args:
            records: SpeedPreprocessor.enrich_all() 处理后的记录列表
            ref_channel: 参考IMU通道
            ref_imu: 参考IMU名称
        """
        import pandas as pd

        # 过滤参考通道数据
        ref = [r for r in records
               if r.get('channel', '') == ref_channel
               and r.get('imu_name', '') == ref_imu]

        if not ref:
            # fallback: 使用全部数据，按时间排序
            ref = sorted(records, key=lambda r: r.get('rel_time', r.get('timestamp', 0)))

        detector = cls()
        detector.t = np.array([r.get('rel_time', r.get('timestamp', i))
                               for i, r in enumerate(ref)], dtype=float)
        detector.speed = np.array([r.get('speed', 0.0) or 0.0 for r in ref], dtype=float)
        # 自动单位检测: speed 在 m/s (<50) → 转换为 km/h（阈值均为 km/h）
        _speed_is_ms = detector.speed.max() < 50 and detector.speed.max() > 0
        if _speed_is_ms:
            detector.speed = detector.speed * 3.6
        detector.wheel = np.array([r.get('wheel', 0.0) or 0.0 for r in ref], dtype=float)
        detector.vehicle_accel = np.array([r.get('vehicle_accel', 0.0) or 0.0 for r in ref],
                                          dtype=float)
        detector.steer_rate = np.array([r.get('steer_rate', 0.0) or 0.0 for r in ref],
                                       dtype=float)
        # 平滑 steer_rate：消除高采样率下的梯度噪声（静默修复 26991 deg/s 异常）
        if len(detector.steer_rate) > 10 and detector.dt < 0.01:
            w = max(3, int(0.05 / detector.dt))  # 50ms 窗口
            detector.steer_rate = np.array(
                pd.Series(detector.steer_rate).rolling(w, center=True, min_periods=1).median()
            )
        detector.speed_ma = np.array([r.get('speed_ma', r.get('speed', 0.0)) for r in ref],
                                     dtype=float)
        detector.speed_std = np.array([r.get('speed_std', 0.0) or 0.0 for r in ref],
                                      dtype=float)
        # speed_ma / speed_std 也跟随单位转换
        if _speed_is_ms:
            detector.speed_ma = detector.speed_ma * 3.6
            detector.speed_std = detector.speed_std * 3.6
        detector.wheel_std = np.array([r.get('wheel_std', 0.0) or 0.0 for r in ref],
                                      dtype=float)
        detector.accel_ma = np.array([r.get('accel_ma', r.get('vehicle_accel', 0.0)) for r in ref],
                                     dtype=float)

        # IMU数据
        detector.ax = np.array([r.get('Ax_m_s2', r.get('ax', 0.0)) or 0.0 for r in ref],
                               dtype=float)
        detector.ay = np.array([r.get('Ay_m_s2', r.get('ay', 0.0)) or 0.0 for r in ref],
                               dtype=float)
        detector.az = np.array([r.get('Az_m_s2', r.get('az', 0.0)) or 0.0 for r in ref],
                               dtype=float)
        detector.gx = np.array([r.get('Gx_rad_s', r.get('gx', 0.0)) or 0.0 for r in ref],
                               dtype=float)
        detector.gy = np.array([r.get('Gy_rad_s', r.get('gy', 0.0)) or 0.0 for r in ref],
                               dtype=float)
        detector.gz = np.array([r.get('Gz_rad_s', r.get('gz', 0.0)) or 0.0 for r in ref],
                               dtype=float)

        detector._init_derived()
        return detector

    @classmethod
    def from_dataframe(cls, df, ref_channel: str = 'ch1',
                       ref_imu: str = 'IMU1_头部眉心-1') -> 'DrivingEventDetector':
        """从 DataFrame 创建（兼容旧API）"""
        if ref_channel and 'channel' in df.columns and ref_imu and 'imu_name' in df.columns:
            ref = df[(df.channel == ref_channel) & (df.imu_name == ref_imu)].sort_values('rel_time')
        else:
            ref = df.sort_values('rel_time') if 'rel_time' in df.columns else df

        detector = cls()
        detector.t = ref['rel_time'].values.astype(float) if 'rel_time' in ref else np.arange(len(ref))
        detector.speed = ref['speed'].values.astype(float) if 'speed' in ref else np.zeros(len(ref))
        _df_speed_ms = detector.speed.max() < 50 and detector.speed.max() > 0
        if _df_speed_ms:
            detector.speed = detector.speed * 3.6
        detector.wheel = ref['wheel'].values.astype(float) if 'wheel' in ref else np.zeros(len(ref))
        detector.vehicle_accel = ref['vehicle_accel'].values.astype(float) if 'vehicle_accel' in ref \
            else np.zeros(len(ref))
        detector.steer_rate = ref['steer_rate'].values.astype(float) if 'steer_rate' in ref \
            else np.zeros(len(ref))
        detector.speed_ma = ref['speed_ma'].values.astype(float) if 'speed_ma' in ref \
            else detector.speed.copy()
        detector.speed_std = ref['speed_std'].values.astype(float) if 'speed_std' in ref \
            else np.zeros(len(ref))
        if _df_speed_ms:
            detector.speed_ma = detector.speed_ma * 3.6
            detector.speed_std = detector.speed_std * 3.6
        detector.wheel_std = ref['wheel_std'].values.astype(float) if 'wheel_std' in ref \
            else np.zeros(len(ref))
        detector.accel_ma = ref['accel_ma'].values.astype(float) if 'accel_ma' in ref \
            else detector.vehicle_accel.copy()

        for col, attr in [('Ax_m_s2', 'ax'), ('Ay_m_s2', 'ay'), ('Az_m_s2', 'az'),
                          ('Gx_dps', 'gx'), ('Gy_dps', 'gy'), ('Gz_dps', 'gz')]:
            if col in ref:
                setattr(detector, attr, ref[col].values.astype(float))
            elif attr in ref:
                setattr(detector, attr, ref[attr].values.astype(float))
            else:
                setattr(detector, attr, np.zeros(len(ref)))

        detector._init_derived()
        return detector

    def _init_derived(self):
        """初始化衍生信号（含专家级 vehicle_accel 计算）"""
        N = len(self.t)
        if N >= 2:
            self.dt = float(np.median(np.diff(self.t)))
            self.fs = 1.0 / self.dt if self.dt > 0 else 1000.0

        # ── 专家级 vehicle_accel: gradient(speed) / 3.6 → Butterworth 5Hz ──
        # 与 test_data/驾驶行为识别/driving_event_detector.py _precompute() 一致
        # 无 clip 裁剪, 保留激进驾驶的真实峰值
        if N >= 10 and self.speed is not None:
            try:
                raw_accel = np.gradient(self.speed, self.dt) / 3.6  # km/h/s → m/s²
                nyq = self.fs / 2.0
                cutoff = min(5.0, nyq * 0.95)
                if cutoff > 0:
                    b, a = scipy_signal.butter(2, cutoff / nyq)
                    self.vehicle_accel_expert = scipy_signal.filtfilt(b, a, raw_accel)
                else:
                    self.vehicle_accel_expert = raw_accel.copy()
            except Exception:
                self.vehicle_accel_expert = self.vehicle_accel.copy() if self.vehicle_accel is not None else np.zeros(N)
        else:
            self.vehicle_accel_expert = self.vehicle_accel.copy() if self.vehicle_accel is not None else np.zeros(N)

        # ── 专家级 accel_ma: vehicle_accel_expert 的 0.5s 滑动均值 ──
        # 与 driving_event_detector.py _precompute() _sliding_mean 一致
        if self.vehicle_accel_expert is not None and N > 0:
            w = max(1, int(0.5 / self.dt))
            self.accel_ma_expert = np.array(
                pd.Series(self.vehicle_accel_expert).rolling(w, center=True, min_periods=1).mean()
            )
        else:
            self.accel_ma_expert = self.accel_ma.copy() if self.accel_ma is not None else np.zeros(N)

        self.a_lat = np.abs(self.ay)
        self.a_vert = np.abs(self.az)
        self.roll_rate = np.abs(self.gx * 180.0 / np.pi)  # rad/s → deg/s
        # gx 可能已在 rad/s，直接取abs
        if np.median(self.roll_rate) < 0.1:
            self.roll_rate = np.abs(self.gx)  # 已是 rad/s，不需要转换

    # ──────────────────────────────────────────
    # 内部工具
    # ──────────────────────────────────────────

    def _add(self, etype: str, t0: float, t1: float,
             conf: float = 0.8, feat: Dict = None) -> Event:
        e = Event(self._eid, etype, EVENT_TYPES.get(etype, etype),
                  float(t0), float(t1), float(t1 - t0), conf, feat or {})
        self.events.append(e)
        self._eid += 1
        return e

    def _segments(self, cond: np.ndarray, min_dur: float = 0.2,
                  max_gap: float = 0.3) -> List[Tuple[int, int]]:
        """将连续满足条件的索引分组为段"""
        if not np.any(cond):
            return []
        idx = np.where(cond)[0]
        gaps = np.where(np.diff(idx) > int(max_gap / self.dt))[0]
        groups = np.split(idx, gaps + 1)
        min_n = max(1, int(min_dur / self.dt))
        return [(int(g[0]), int(g[-1])) for g in groups if len(g) >= min_n]

    def _compute_vdv(self, accel: np.ndarray, dt: float) -> float:
        """ISO 2631-1 VDV (Vibration Dose Value): (∫|a|^4 dt)^(1/4)  [m/s^1.75]"""
        return float(np.sum(np.abs(accel) ** 4) * dt) ** 0.25 if len(accel) > 0 else 0.0

    def _compute_jerk(self, i0: int, i1: int, acc: np.ndarray) -> float:
        """峰值 Jerk: max(|da/dt|)  [m/s³]"""
        if i1 <= i0 + 2:
            return 0.0
        da = np.diff(acc[i0:i1+1])
        return float(np.max(np.abs(da)) / self.dt) if len(da) > 0 else 0.0

    # ════════════════════════════════════════════
    # 1. 速度基事件
    # ════════════════════════════════════════════

    def detect_speed_events(self) -> List[Event]:
        events = []
        # 停车 / 驻车
        for i0, i1 in self._segments(self.speed <= self.STOP_SPEED,
                                      self.STOP_MIN_DUR, 1.0):
            d = self.t[i1] - self.t[i0]
            events.append(self._add(
                'parked' if d > self.PARK_DURATION else 'stopped',
                self.t[i0], self.t[i1], 0.95,
                {'speed_min': float(self.speed[i0:i1+1].min()),
                 'speed_max': float(self.speed[i0:i1+1].max())}))

        # 恒速行驶 — 使用较大 max_gap 使其能跨越短暂的非匀速事件
        for i0, i1 in self._segments(
                (self.speed > self.CRUISE_MIN_SPEED) & (self.speed_std < 3),
                self.CRUISE_MIN_DUR, self.CRUISE_MAX_GAP):
            events.append(self._add('cruising', self.t[i0], self.t[i1], 0.85,
                                    {'speed_mean': float(self.speed[i0:i1+1].mean())}))

        # 匀速直行
        for i0, i1 in self._segments(
                (self.speed > self.CRUISE_MIN_SPEED) &
                (self.speed_std < self.CONST_SPEED_STD) &
                (np.abs(self.wheel) < self.WHEEL_STRAIGHT),
                self.CRUISE_MIN_DUR, 0.5):
            events.append(self._add('constant_speed', self.t[i0], self.t[i1], 0.85,
                                    {'speed_mean': float(self.speed[i0:i1+1].mean())}))

        # 正常加速 — accel_ma_expert 专家级平滑检测
        ama = self.accel_ma_expert if self.accel_ma_expert is not None else self.accel_ma
        for i0, i1 in self._segments(
                (ama > self.NORMAL_ACCEL_LOW) &
                (ama < self.NORMAL_ACCEL_HIGH) &
                (self.speed > 3),
                0.2, 0.3):
            if self.speed[i1] - self.speed[i0] > self.SPEED_CHANGE_MIN:
                events.append(self._add('normal_acceleration', self.t[i0], self.t[i1], 0.80,
                                        {'speed_delta': float(self.speed[i1] - self.speed[i0]),
                                         'accel_max': float(self.vehicle_accel[i0:i1+1].max())}))

        # 正常减速 — accel_ma_expert 专家级平滑检测
        for i0, i1 in self._segments(
                (ama < self.NORMAL_DECEL_HIGH) &
                (ama > self.NORMAL_DECEL_LOW) &
                (self.speed > 3),
                0.2, 0.3):
            if self.speed[i1] - self.speed[i0] < -self.SPEED_CHANGE_MIN:
                events.append(self._add('normal_deceleration', self.t[i0], self.t[i1], 0.80,
                                        {'speed_delta': float(self.speed[i1] - self.speed[i0]),
                                         'decel_min': float(self.vehicle_accel[i0:i1+1].min())}))

        return events

    # ════════════════════════════════════════════
    # 2. 转向基事件
    # ════════════════════════════════════════════

    def detect_steering_events(self) -> List[Event]:
        events = []
        aw = np.abs(self.wheel)

        # 车道保持
        for i0, i1 in self._segments(
                (aw < self.WHEEL_STRAIGHT) & (self.speed > self.CRUISE_MIN_SPEED),
                self.LANE_KEEP_MIN_DUR, 0.5):
            events.append(self._add('lane_keeping', self.t[i0], self.t[i1], 0.85,
                                    {'wheel_mean': float(self.wheel[i0:i1+1].mean())}))

        # 左转
        for i0, i1 in self._segments(self.wheel < -self.WHEEL_TURN,
                                      self.TURN_MIN_DUR, self.TURN_MAX_GAP):
            if self.speed[i0:i1+1].mean() > 3:
                events.append(self._add('left_turn', self.t[i0], self.t[i1], 0.85,
                                        {'wheel_min': float(self.wheel[i0:i1+1].min())}))

        # 右转
        for i0, i1 in self._segments(self.wheel > self.WHEEL_TURN,
                                      self.TURN_MIN_DUR, self.TURN_MAX_GAP):
            if self.speed[i0:i1+1].mean() > 3:
                events.append(self._add('right_turn', self.t[i0], self.t[i1], 0.85,
                                        {'wheel_max': float(self.wheel[i0:i1+1].max())}))

        # 小半径转弯
        for i0, i1 in self._segments(aw > self.WHEEL_TIGHT, self.TURN_MIN_DUR, 0.2):
            if self.speed[i0:i1+1].mean() > 3:
                events.append(self._add('tight_turn', self.t[i0], self.t[i1], 0.80,
                                        {'wheel_max': float(aw[i0:i1+1].max())}))

        # 大半径转弯
        for i0, i1 in self._segments(
                (aw > self.WHEEL_WIDE_LOW) & (aw < self.WHEEL_WIDE_HIGH),
                1.0, 0.5):
            if self.speed[i0:i1+1].mean() > 5:
                events.append(self._add('wide_turn', self.t[i0], self.t[i1], 0.75,
                                        {'wheel_mean': float(self.wheel[i0:i1+1].mean())}))

        # U型转弯
        for i0, i1 in self._segments(
                (self.wheel_std > self.WHEEL_STD_U) & (self.speed > 2),
                1.0, 0.5):
            w_range = self.wheel[i0:i1+1].max() - self.wheel[i0:i1+1].min()
            if w_range > self.WHEEL_RANGE_U and np.sign(self.wheel[i0]) != np.sign(self.wheel[i1]):
                events.append(self._add('u_turn', self.t[i0], self.t[i1], 0.70,
                                        {'wheel_range': float(w_range)}))

        return events

    # ════════════════════════════════════════════
    # 3. 复合事件（弯道 + 加/减速）
    # ════════════════════════════════════════════

    def detect_compound_events(self) -> List[Event]:
        events = []
        ic = np.abs(self.wheel) > self.CORNER_WHEEL

        # 弯道加速
        for i0, i1 in self._segments(
                ic & (self.vehicle_accel > self.NORMAL_ACCEL_LOW) & (self.speed > 3),
                0.3, 0.3):
            if self.speed[i1] - self.speed[i0] > 1:
                events.append(self._add('cornering_acceleration', self.t[i0], self.t[i1], 0.75,
                                        {'speed_delta': float(self.speed[i1] - self.speed[i0]),
                                         'wheel': float(self.wheel[i0:i1+1].mean())}))

        # 弯道减速
        for i0, i1 in self._segments(
                ic & (self.vehicle_accel < self.NORMAL_DECEL_HIGH) & (self.speed > 3),
                0.3, 0.3):
            if self.speed[i1] - self.speed[i0] < -1:
                events.append(self._add('cornering_deceleration', self.t[i0], self.t[i1], 0.75,
                                        {'speed_delta': float(self.speed[i1] - self.speed[i0]),
                                         'wheel': float(self.wheel[i0:i1+1].mean())}))

        return events

    # ════════════════════════════════════════════
    # 4. 激进驾驶事件
    # ════════════════════════════════════════════

    def detect_aggressive_events(self) -> List[Event]:
        events = []
        acc = self.vehicle_accel_expert if self.vehicle_accel_expert is not None else self.vehicle_accel

        # 激进加速 — 专家级 vehicle_accel_expert（gradient→/3.6→BW5Hz，无裁剪）
        for i0, i1 in self._segments(
                (acc > self.AGGRESSIVE_ACCEL) & (self.speed > 3),
                0.2, self.AGGRESSIVE_MAX_GAP):
            events.append(self._add('aggressive_acceleration', self.t[i0], self.t[i1], 0.85,
                                        {'accel_max': float(acc[i0:i1+1].max()),
                                         'vdv': self._compute_vdv(acc[i0:i1+1], self.dt),
                                         'jerk': self._compute_jerk(i0, i1, acc)}))

        for i0, i1 in self._segments(
                (acc < self.AGGRESSIVE_DECEL) & (self.speed > 3),
                0.2, 0.3):
            events.append(self._add('aggressive_deceleration', self.t[i0], self.t[i1], 0.85,
                                    {'decel_min': float(acc[i0:i1+1].min()),
                                     'vdv': self._compute_vdv(acc[i0:i1+1], self.dt),
                                     'jerk': self._compute_jerk(i0, i1, acc)}))

        for i0, i1 in self._segments(
                (acc < self.HARD_BRAKE_DECEL) &
                (self.speed > self.HARD_BRAKE_MIN_SPEED),
                0.15, 0.2):
            events.append(self._add('emergency_braking', self.t[i0], self.t[i1], 0.90,
                                    {'decel_min': float(acc[i0:i1+1].min()),
                                     'vdv': self._compute_vdv(acc[i0:i1+1], self.dt),
                                     'jerk': self._compute_jerk(i0, i1, acc),
                                     'speed_at_brake': float(self.speed[i0])}))

        return events

    # ════════════════════════════════════════════
    # 5. 动态驾驶事件（蛇形/急速变向）
    # ════════════════════════════════════════════

    def detect_dynamic_events(self) -> List[Event]:
        events = []
        w = max(1, int(self.SLALOM_WINDOW / self.dt))
        s = max(1, int(self.SLALOM_STEP / self.dt))
        N = len(self.t)
        # 防越界：窗口不能超过数据长度
        w = min(w, N)
        s = min(s, max(1, N // 2))

        # 蛇形驾驶 — 滑动窗口检测方向盘过零 + NMS 去重
        slalom_candidates = []
        for start in range(0, max(1, N - w), s):
            end = min(start + w, N)
            end_idx = min(end, N - 1)  # 元素访问防越界
            ww = self.wheel[start:end]
            zc = int(np.sum(np.diff(np.signbit(ww))))
            if (zc >= self.SLALOM_ZC_MIN and
                    (ww.max() - ww.min()) > self.SLALOM_WHEEL_RANGE and
                    self.speed[start:end].mean() > self.SLALOM_MIN_SPEED):
                slalom_candidates.append({
                    't0': self.t[start], 't1': self.t[end_idx],
                    'zc': zc, 'wheel_range': float(ww.max() - ww.min()),
                })

        # NMS: 按过零次数降序，贪心地选择非重叠窗口
        slalom_candidates.sort(key=lambda x: -x['zc'])
        kept = []
        for c in slalom_candidates:
            # 检查与已保留窗口的重叠度
            overlap = False
            for k in kept:
                o = min(c['t1'], k['t1']) - max(c['t0'], k['t0'])
                if o > 0.3 * self.SLALOM_WINDOW:  # 重叠超过30%窗口 → 跳过
                    overlap = True
                    break
            if not overlap:
                kept.append(c)
                events.append(self._add('weaving', c['t0'], c['t1'], 0.75,
                                        {'zero_crossings': c['zc'],
                                         'wheel_range': c['wheel_range']}))

        # 急速变向 — 两阶段检测：
        #   (a) 高 steer_rate 单阈值
        #   (b) 连续反向打方向盘 (wheel 正→负→正 摆动)
        for i0, i1 in self._segments(
                (self.steer_rate > self.STEER_RATE_THRESH) &
                (self.speed > self.RAPID_LC_MIN_SPEED),
                self.RAPID_DIR_MIN_DUR, 0.3):
            events.append(self._add('rapid_direction_change', self.t[i0], self.t[i1], 0.80,
                                    {'steer_rate_max': float(self.steer_rate[i0:i1+1].max()),
                                     'method': 'steer_rate'}))
        # (b) 滑动窗口检测方向反转: wheel 在窗口内同时出现 >+SWING 和 <-SWING
        w_rd = max(1, int(1.0 / self.dt))
        s_rd = max(1, int(0.3 / self.dt))
        rapid_candidates = []
        for start in range(0, max(1, N - w_rd), s_rd):
            end = min(start + w_rd, N)
            end_idx = min(end, N - 1)
            ww = self.wheel[start:end]
            if (ww.max() > self.RAPID_STEER_SWING and ww.min() < -self.RAPID_STEER_SWING
                    and self.speed[start:end].mean() > self.RAPID_LC_MIN_SPEED):
                rapid_candidates.append({
                    't0': self.t[start], 't1': self.t[end_idx],
                    'wheel_range': float(ww.max() - ww.min()),
                })
        # NMS 去重
        rapid_candidates.sort(key=lambda x: -x['wheel_range'])
        kept_rapid = []
        for c in rapid_candidates:
            overlap = False
            for k in kept_rapid:
                o = min(c['t1'], k['t1']) - max(c['t0'], k['t0'])
                if o > 0.5:
                    overlap = True
                    break
            if not overlap:
                kept_rapid.append(c)
                events.append(self._add('rapid_direction_change', c['t0'], c['t1'], 0.75,
                                        {'wheel_range': c['wheel_range'],
                                         'method': 'direction_reversal'}))

        return events

    # ════════════════════════════════════════════
    # 6. IMU基事件（颠簸/侧滑/侧翻）
    # ════════════════════════════════════════════

    def detect_imu_events(self) -> List[Event]:
        events = []

        # 剧烈颠簸
        for i0, i1 in self._segments(self.a_vert > self.SEVERE_BUMP_AZ,
                                      0.05, 0.1):
            events.append(self._add('severe_bump', self.t[i0], self.t[i1], 0.85,
                                    {'az_max': float(self.a_vert[i0:i1+1].max())}))

        # 侧滑风险
        for i0, i1 in self._segments(
                (self.a_lat > self.SIDE_SLIP_AY) &
                (self.speed > self.IMU_MIN_SPEED),
                0.2, 0.2):
            events.append(self._add('skid_risk', self.t[i0], self.t[i1], 0.75,
                                    {'ay_max': float(self.a_lat[i0:i1+1].max()),
                                     'speed': float(self.speed[i0:i1+1].mean())}))

        # 侧翻风险
        for i0, i1 in self._segments(
                (self.a_lat > self.ROLLOVER_AY) &
                (self.roll_rate > 20.0) &
                (self.speed > self.IMU_MIN_SPEED),
                0.15, 0.2):
            events.append(self._add('rollover_risk', self.t[i0], self.t[i1], 0.70,
                                    {'ay_max': float(self.a_lat[i0:i1+1].max()),
                                     'gx_max': float(self.roll_rate[i0:i1+1].max())}))

        return events

    # ════════════════════════════════════════════
    # 全量检测
    # ════════════════════════════════════════════

    def detect_all(self) -> List[Event]:
        """执行全部6组检测，返回排序后的事件列表"""
        self.events = []
        self._eid = 0

        for method in [
            self.detect_speed_events,
            self.detect_steering_events,
            self.detect_compound_events,
            self.detect_aggressive_events,
            self.detect_dynamic_events,
            self.detect_imu_events,
        ]:
            method()

        self.events.sort(key=lambda e: (e.t_start, -e.confidence))
        for i, e in enumerate(self.events):
            e.event_id = i

        return self.events

    def get_summary(self) -> Dict:
        """按类型统计事件"""
        by_type = {}
        for e in self.events:
            by_type.setdefault(e.event_type, []).append(e)
        return {
            'total': len(self.events),
            'by_type': {
                et: {'count': len(el), 'name': EVENT_TYPES.get(et, et)}
                for et, el in sorted(by_type.items())
            },
            'time_range': (
                (self.events[0].t_start, self.events[-1].t_end)
                if self.events else (0.0, 0.0)
            ),
        }

    @classmethod
    def process_window(cls, t: np.ndarray, speed_kmh: np.ndarray,
                       wheel_deg: np.ndarray, vehicle_accel_expert: np.ndarray = None,
                       accel_ma_expert: np.ndarray = None,
                       ax: np.ndarray = None, ay: np.ndarray = None,
                       az: np.ndarray = None, gx: np.ndarray = None,
                       gy: np.ndarray = None, gz: np.ndarray = None,
                       speed_ma: np.ndarray = None, speed_std: np.ndarray = None,
                       wheel_std: np.ndarray = None, steer_rate: np.ndarray = None,
                       ) -> List['Event']:
        """流式滑动窗口检测 (O(n) per window vs O(N) full batch)

        接收当前窗口的 numpy 数组，直接赋值到检测器内部并运行全量检测。
        避免每次调用都重新构建 from_records 的开销。

        Args:
            t: 时间戳 (秒)
            speed_kmh: 速度 (km/h)
            wheel_deg: 方向盘转角 (度)
            vehicle_accel_expert: 专家级车辆加速度 (m/s², optional)
            accel_ma_expert: 专家级滑动均值 (m/s², optional)
            ax..gz: IMU 数据 (optional, 取零)
            speed_ma, speed_std, wheel_std, steer_rate: 预计算特征 (optional)

        Returns:
            当前窗口检测到的事件列表
        """
        N = len(t)
        if N < 10:
            return []

        detector = cls()
        detector.t = np.asarray(t, dtype=float)
        detector.speed = np.asarray(speed_kmh, dtype=float)
        detector.wheel = np.asarray(wheel_deg, dtype=float)

        # 直接赋值专家级加速度（跳过完整 gradient+Butterworth 重算）
        if vehicle_accel_expert is not None and len(vehicle_accel_expert) == N:
            detector.vehicle_accel_expert = np.asarray(vehicle_accel_expert, dtype=float)
        if accel_ma_expert is not None and len(accel_ma_expert) == N:
            detector.accel_ma_expert = np.asarray(accel_ma_expert, dtype=float)

        # IMU 数据 (optional, 用于颠簸/侧滑/侧翻检测)
        detector.ax = np.asarray(ax, dtype=float) if ax is not None else np.zeros(N)
        detector.ay = np.asarray(ay, dtype=float) if ay is not None else np.zeros(N)
        detector.az = np.asarray(az, dtype=float) if az is not None else np.zeros(N)
        detector.gx = np.asarray(gx, dtype=float) if gx is not None else np.zeros(N)
        detector.gy = np.asarray(gy, dtype=float) if gy is not None else np.zeros(N)
        detector.gz = np.asarray(gz, dtype=float) if gz is not None else np.zeros(N)

        # 预计算特征 (含来自 preprocessor 的 vehicle_accel 作为 fallback)
        detector.vehicle_accel = vehicle_accel_expert if vehicle_accel_expert is not None else np.zeros(N)
        detector.accel_ma = accel_ma_expert if accel_ma_expert is not None else np.zeros(N)
        detector.speed_ma = np.asarray(speed_ma, dtype=float) if speed_ma is not None else detector.speed.copy()
        detector.speed_std = np.asarray(speed_std, dtype=float) if speed_std is not None else np.zeros(N)
        detector.wheel_std = np.asarray(wheel_std, dtype=float) if wheel_std is not None else np.zeros(N)
        detector.steer_rate = np.asarray(steer_rate, dtype=float) if steer_rate is not None else np.zeros(N)

        # 初始化衍生信号 (dt, fs, a_lat, a_vert, roll_rate)
        detector._init_derived()

        return detector.detect_all()

    def export_dicts(self) -> List[Dict]:
        """导出为 dict 列表（兼容旧 API）"""
        return [e.to_dict() for e in self.events]