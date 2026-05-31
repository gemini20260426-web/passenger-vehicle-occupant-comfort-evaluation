#!/usr/bin/env python3
"""
驾驶行为事件检测引擎 V3.0
=========================
从解析后的IMU+CAN数据中检测22种驾驶行为事件。

事件类型:
  匀速直行  正常加速  正常减速  恒速行驶  停车  驻车
  车道保持  左转      右转      小半径转弯  大半径转弯
  弯道加速  弯道减速  U型转弯  激进加速  激进减速
  急刹车    蛇形驾驶  急速变向  剧烈颠簸  侧滑风险  侧翻风险

检测策略:
  - 速度基: 加速/减速/巡航/停止  (CAN speed)
  - 转向基: 左转/右转/U-turn/蛇形 (CAN wheel angle)
  - IMU基:  颠簸/侧滑/侧翻       (IMU accel + gyro)
  - 复合基: 弯道加速/减速, 激进加减速

输入: parsed_data CSV (rel_time, channel, imu_name, Ax~Gz, speed, wheel)
输出: events JSON + CSV

用法: python driving_event_detector.py <parsed_data.csv> [output_prefix]
"""

import pandas as pd
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import json, sys

# ============================================================================
# 事件类型枚举
# ============================================================================
EVENT_TYPES = {
    # 速度基 (Speed-based)
    'constant_speed':        '匀速直行',
    'normal_accel':          '正常加速',
    'normal_decel':          '正常减速',
    'cruising':              '恒速行驶',
    'stopped':               '停车',
    'parked':                '驻车',

    # 转向基 (Steering-based)
    'lane_keeping':          '车道保持',
    'left_turn':             '左转',
    'right_turn':            '右转',
    'tight_turn':            '小半径转弯',
    'wide_turn':             '大半径转弯',
    'u_turn':                'U型转弯',

    # 复合基 (Speed × Steering)
    'corner_accel':          '弯道加速',
    'corner_decel':          '弯道减速',

    # 激进基 (Aggressive)
    'aggressive_accel':      '激进加速',
    'aggressive_decel':      '激进减速',
    'hard_brake':            '急刹车',

    # 动态基 (Dynamic/Oscillatory)
    'slalom':                '蛇形驾驶',
    'rapid_lane_change':     '急速变向',

    # IMU基 (IMU-based)
    'severe_bump':           '剧烈颠簸',
    'side_slip_risk':        '侧滑风险',
    'rollover_risk':         '侧翻风险',
}

@dataclass
class Event:
    """驾驶行为事件"""
    event_id: int
    event_type: str
    event_name: str
    t_start: float
    t_end: float
    duration_s: float
    confidence: float             # 0~1 置信度
    features: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id, 'event_type': self.event_type,
            'event_name': self.event_name,
            't_start': round(self.t_start, 3), 't_end': round(self.t_end, 3),
            'duration_s': round(self.duration_s, 3),
            'confidence': round(self.confidence, 3),
            'features': {k: round(v, 4) if isinstance(v, float) else v
                         for k, v in self.features.items()}
        }


class DrivingEventDetector:
    """22种驾驶行为事件检测器"""

    def __init__(self, csv_path: str, ref_imu: str = 'IMU1_头部眉心-1'):
        df = pd.read_csv(csv_path)
        ref = df[(df['channel'] == 'ch1') & (df['imu_name'] == ref_imu)].sort_values('rel_time')
        self.t = ref['rel_time'].values
        self.speed = ref['speed'].values.astype(float)
        self.wheel = ref['wheel'].values.astype(float)
        imu = ref[['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps']].values
        self.ax, self.ay, self.az = imu[:, 0], imu[:, 1], imu[:, 2]
        self.gx, self.gy, self.gz = imu[:, 3], imu[:, 4], imu[:, 5]
        self.dt = np.median(np.diff(self.t))
        self.fs = 1.0 / self.dt
        self.N = len(self.t)
        self.events: List[Event] = []
        self.eid = 0

        # 预计算派生信号
        self._precompute()

    def _precompute(self):
        """预计算所有派生信号"""
        dt = self.dt

        # 加速度 (从速度计算, 经低通滤波)
        raw_accel = np.gradient(self.speed, dt) / 3.6
        b, a = signal.butter(2, 5.0 / (self.fs / 2))
        self.vehicle_accel = signal.filtfilt(b, a, raw_accel)  # m/s²

        # 转向角速度
        self.steer_rate = np.abs(np.gradient(self.wheel, dt))

        # IMU合成量
        self.a_lat = np.abs(self.ay)      # 侧向加速度幅值
        self.a_vert = np.abs(self.az)     # 垂向加速度幅值
        self.a_mag = np.sqrt(self.ax**2 + self.ay**2 + self.az**2)
        self.roll_rate = np.abs(self.gx)  # 侧倾角速度

        # 滑动统计 (0.5s窗)
        win = int(0.5 / dt)
        self.speed_ma = pd.Series(self.speed).rolling(win, center=True).mean().bfill().ffill().values
        self.speed_std = pd.Series(self.speed).rolling(win, center=True).std().bfill().ffill().values
        self.wheel_ma = pd.Series(self.wheel).rolling(win, center=True).mean().bfill().ffill().values
        self.wheel_std = pd.Series(self.wheel).rolling(win, center=True).std().bfill().ffill().values
        self.accel_ma = pd.Series(self.vehicle_accel).rolling(win, center=True).mean().bfill().ffill().values

    def _add_event(self, event_type: str, t0: float, t1: float,
                   confidence: float = 0.8, features: Dict = None) -> Event:
        """添加事件"""
        e = Event(
            event_id=self.eid, event_type=event_type,
            event_name=EVENT_TYPES.get(event_type, event_type),
            t_start=t0, t_end=t1, duration_s=t1 - t0,
            confidence=confidence, features=features or {}
        )
        self.events.append(e)
        self.eid += 1
        return e

    def _find_segments(self, condition: np.ndarray,
                       min_duration_s: float = 0.2,
                       max_gap_s: float = 0.3) -> List[Tuple[int, int]]:
        """从布尔条件数组提取连续段"""
        if not np.any(condition):
            return []
        idx = np.where(condition)[0]
        gaps = np.where(np.diff(idx) > int(max_gap_s / self.dt))[0]
        groups = np.split(idx, gaps + 1)
        min_samples = int(min_duration_s / self.dt)
        return [(g[0], g[-1]) for g in groups if len(g) >= min_samples]

    # ========================================================================
    # 速度基事件
    # ========================================================================

    def detect_speed_events(self):
        """检测速度相关事件: 加速/减速/巡航/停止/驻车"""
        min_dur = 0.3

        # --- 停车 (speed=0持续) ---
        for i0, i1 in self._find_segments(self.speed <= 1, min_dur, 1.0):
            dur = self.t[i1] - self.t[i0]
            if dur > 1.0:
                self._add_event('parked', self.t[i0], self.t[i1], 0.95,
                                {'speed_max': float(self.speed[i0:i1].max())})
            elif dur > 0.3:
                self._add_event('stopped', self.t[i0], self.t[i1], 0.95,
                                {'speed_max': float(self.speed[i0:i1].max())})

        # --- 恒速行驶 (速度波动<3km/h, 持续时间>1s) ---
        for i0, i1 in self._find_segments(
            (self.speed > 5) & (self.speed_std < 3), 1.0, 0.5
        ):
            self._add_event('cruising', self.t[i0], self.t[i1], 0.85,
                            {'speed_mean': float(self.speed[i0:i1].mean()),
                             'speed_std': float(self.speed[i0:i1].std())})

        # --- 匀速直行 (恒速 + 方向盘近0) ---
        for i0, i1 in self._find_segments(
            (self.speed > 5) & (self.speed_std < 2) & (np.abs(self.wheel) < 1), 1.0, 0.5
        ):
            self._add_event('constant_speed', self.t[i0], self.t[i1], 0.85,
                            {'speed_mean': float(self.speed[i0:i1].mean())})

        # --- 正常加速 (0.5~3 m/s²) ---
        for i0, i1 in self._find_segments(
            (self.accel_ma > 0.5) & (self.accel_ma < 3.0) & (self.speed > 3), min_dur, 0.3
        ):
            dur = self.t[i1] - self.t[i0]
            ds = self.speed[i1] - self.speed[i0]
            if dur > 0.2 and ds > 1:
                self._add_event('normal_accel', self.t[i0], self.t[i1], 0.80,
                                {'speed_delta': float(ds), 'accel_mean': float(self.accel_ma[i0:i1].mean())})

        # --- 正常减速 (-3~-0.5 m/s²) ---
        for i0, i1 in self._find_segments(
            (self.accel_ma < -0.5) & (self.accel_ma > -3.0) & (self.speed > 3), min_dur, 0.3
        ):
            dur = self.t[i1] - self.t[i0]
            ds = self.speed[i1] - self.speed[i0]
            if dur > 0.2 and ds < -1:
                self._add_event('normal_decel', self.t[i0], self.t[i1], 0.80,
                                {'speed_delta': float(ds), 'accel_mean': float(self.accel_ma[i0:i1].mean())})

    # ========================================================================
    # 转向基事件
    # ========================================================================

    def detect_steering_events(self):
        """检测转向相关事件"""
        min_dur = 0.3
        abs_wheel = np.abs(self.wheel)

        # --- 车道保持 (|wheel| < 1°, speed > 5) ---
        for i0, i1 in self._find_segments(
            (abs_wheel < 1) & (self.speed > 5), 2.0, 0.5
        ):
            self._add_event('lane_keeping', self.t[i0], self.t[i1], 0.85,
                            {'wheel_std': float(self.wheel[i0:i1].std())})

        # --- 左转 (wheel < -3°, 持续) ---
        for i0, i1 in self._find_segments(self.wheel < -2, min_dur, 0.3):
            if self.speed[i0:i1].mean() > 3:
                self._add_event('left_turn', self.t[i0], self.t[i1], 0.85,
                                {'wheel_mean': float(self.wheel[i0:i1].mean()),
                                 'speed_mean': float(self.speed[i0:i1].mean())})

        # --- 右转 (wheel > 3°) ---
        for i0, i1 in self._find_segments(self.wheel > 2, min_dur, 0.3):
            if self.speed[i0:i1].mean() > 3:
                self._add_event('right_turn', self.t[i0], self.t[i1], 0.85,
                                {'wheel_mean': float(self.wheel[i0:i1].mean()),
                                 'speed_mean': float(self.speed[i0:i1].mean())})

        # --- 小半径转弯 (|wheel| > 20°) ---
        for i0, i1 in self._find_segments(abs_wheel > 15, min_dur, 0.2):
            if self.speed[i0:i1].mean() > 3:
                self._add_event('tight_turn', self.t[i0], self.t[i1], 0.80,
                                {'wheel_max': float(abs_wheel[i0:i1].max()),
                                 'speed_mean': float(self.speed[i0:i1].mean())})

        # --- 大半径转弯 (5° < |wheel| < 15°) ---
        for i0, i1 in self._find_segments(
            (abs_wheel > 3) & (abs_wheel < 15), 1.0, 0.5
        ):
            if self.speed[i0:i1].mean() > 5:
                self._add_event('wide_turn', self.t[i0], self.t[i1], 0.75,
                                {'wheel_mean': float(abs_wheel[i0:i1].mean()),
                                 'speed_mean': float(self.speed[i0:i1].mean())})

        # --- U型转弯 (方向盘扫过>100°范围) ---
        for i0, i1 in self._find_segments(
            (self.wheel_std > 5) & (self.speed > 2), 1.0, 0.5
        ):
            wheel_range = self.wheel[i0:i1].max() - self.wheel[i0:i1].min()
            if wheel_range > 30 and np.sign(self.wheel[i0]) != np.sign(self.wheel[i1]):
                self._add_event('u_turn', self.t[i0], self.t[i1], 0.70,
                                {'wheel_range': float(wheel_range),
                                 'speed_mean': float(self.speed[i0:i1].mean())})

    # ========================================================================
    # 复合事件 (Speed × Steering)
    # ========================================================================

    def detect_compound_events(self):
        """检测复合事件: 弯道加速/减速"""

        # --- 弯道加速 (|wheel|>3° + speed增加>3km/h/s) ---
        in_corner = np.abs(self.wheel) > 3
        accelerating = self.vehicle_accel > 0.5
        corner_accel = in_corner & accelerating & (self.speed > 3)

        for i0, i1 in self._find_segments(corner_accel, 0.3, 0.3):
            ds = self.speed[i1] - self.speed[i0]
            if ds > 1:
                self._add_event('corner_accel', self.t[i0], self.t[i1], 0.75,
                                {'speed_delta': float(ds),
                                 'wheel_mean': float(self.wheel[i0:i1].mean())})

        # --- 弯道减速 (|wheel|>3° + speed减少>3km/h/s) ---
        decelerating = self.vehicle_accel < -0.5
        corner_decel = in_corner & decelerating & (self.speed > 3)

        for i0, i1 in self._find_segments(corner_decel, 0.3, 0.3):
            ds = self.speed[i1] - self.speed[i0]
            if ds < -1:
                self._add_event('corner_decel', self.t[i0], self.t[i1], 0.75,
                                {'speed_delta': float(ds),
                                 'wheel_mean': float(self.wheel[i0:i1].mean())})

    # ========================================================================
    # 激进事件
    # ========================================================================

    def detect_aggressive_events(self):
        """检测激进驾驶事件"""

        # --- 激进加速 (accel > 3 m/s², ~0.3g) ---
        for i0, i1 in self._find_segments(
            (self.vehicle_accel > 3.0) & (self.speed > 3), 0.2, 0.2
        ):
            self._add_event('aggressive_accel', self.t[i0], self.t[i1], 0.85,
                            {'accel_max': float(self.vehicle_accel[i0:i1].max()),
                             'speed_delta': float(self.speed[i1] - self.speed[i0])})

        # --- 激进减速 (accel < -3 m/s²) ---
        for i0, i1 in self._find_segments(
            (self.vehicle_accel < -3.0) & (self.speed > 3), 0.2, 0.2
        ):
            self._add_event('aggressive_decel', self.t[i0], self.t[i1], 0.85,
                            {'accel_min': float(self.vehicle_accel[i0:i1].min()),
                             'speed_delta': float(self.speed[i1] - self.speed[i0])})

        # --- 急刹车 (accel < -5 m/s², ~0.5g) ---
        for i0, i1 in self._find_segments(
            (self.vehicle_accel < -5.0) & (self.speed > 5), 0.15, 0.2
        ):
            self._add_event('hard_brake', self.t[i0], self.t[i1], 0.90,
                            {'accel_min': float(self.vehicle_accel[i0:i1].min()),
                             'speed_from': float(self.speed[i0]),
                             'speed_to': float(self.speed[i1])})

    # ========================================================================
    # 动态/振荡事件
    # ========================================================================

    def detect_dynamic_events(self):
        """检测蛇形驾驶、急速变向"""

        # --- 蛇形驾驶 (方向盘振荡: 穿零次数多 + 幅值>5°) ---
        win = int(1.5 / self.dt)
        step = int(0.3 / self.dt)

        for start in range(0, self.N - win, step):
            end = start + win
            w = self.wheel[start:end]
            # 零交叉次数
            zero_crossings = np.sum(np.diff(np.signbit(w)))
            wheel_range = w.max() - w.min()

            if (zero_crossings >= 2 and wheel_range > 5
                    and self.speed[start:end].mean() > 10):
                self._add_event('slalom', self.t[start], self.t[end], 0.75,
                                {'zero_crossings': int(zero_crossings),
                                 'wheel_range': float(wheel_range),
                                 'speed_mean': float(self.speed[start:end].mean())})

        # --- 急速变向 (转向速率 > 50°/s) ---
        for i0, i1 in self._find_segments(
            (self.steer_rate > 50) & (self.speed > 10), 0.2, 0.2
        ):
            self._add_event('rapid_lane_change', self.t[i0], self.t[i1], 0.80,
                            {'steer_rate_max': float(self.steer_rate[i0:i1].max()),
                             'speed_mean': float(self.speed[i0:i1].mean())})

    # ========================================================================
    # IMU基事件
    # ========================================================================

    def detect_imu_events(self):
        """检测颠簸、侧滑、侧翻风险"""

        # --- 剧烈颠簸 (垂向加速度 > 3g 或 峰值>15m/s²) ---
        for i0, i1 in self._find_segments(self.a_vert > 15, 0.05, 0.1):
            self._add_event('severe_bump', self.t[i0], self.t[i1], 0.85,
                            {'az_peak': float(self.az[i0:i1].max()),
                             'speed': float(self.speed[i0:i1].mean())})

        # --- 侧滑风险 (侧向加速度 > 0.5g, 高速) ---
        # 理论: lateral_accel = v²/R, 当 ay > 0.5g 时轮胎接近附着极限
        for i0, i1 in self._find_segments(
            (self.a_lat > 5.0) & (self.speed > 20), 0.2, 0.2
        ):
            slip_margin = 5.0 / (self.a_lat[i0:i1].mean() + 1e-9)
            self._add_event('side_slip_risk', self.t[i0], self.t[i1], 0.75,
                            {'ay_peak': float(self.a_lat[i0:i1].max()),
                             'slip_margin': float(slip_margin),
                             'speed_mean': float(self.speed[i0:i1].mean())})

        # --- 侧翻风险 (高侧向加速度 + 高侧倾角速度) ---
        # 侧翻指标: |ay| > 0.6g 且 roll_rate > 20°/s
        rollover_cond = (self.a_lat > 6.0) & (self.roll_rate > 20) & (self.speed > 20)
        for i0, i1 in self._find_segments(rollover_cond, 0.15, 0.2):
            rtf = (self.a_lat[i0:i1].mean() / 9.81) / 0.7  # Rollover Threat Factor
            self._add_event('rollover_risk', self.t[i0], self.t[i1], 0.70,
                            {'ay_peak_g': float(self.a_lat[i0:i1].max() / 9.81),
                             'roll_rate_max': float(self.roll_rate[i0:i1].max()),
                             'rtf': float(rtf),
                             'speed_mean': float(self.speed[i0:i1].mean())})

    # ========================================================================
    # 全量检测 + 去重排序
    # ========================================================================

    def detect_all(self) -> List[Event]:
        """执行全部检测"""
        self.events = []
        self.eid = 0

        self.detect_speed_events()
        self.detect_steering_events()
        self.detect_compound_events()
        self.detect_aggressive_events()
        self.detect_dynamic_events()
        self.detect_imu_events()

        # 按时间排序, 重新编号
        self.events.sort(key=lambda e: (e.t_start, -e.confidence))
        for i, e in enumerate(self.events):
            e.event_id = i

        return self.events

    # ========================================================================
    # 摘要与导出
    # ========================================================================

    def print_summary(self):
        """打印检测摘要"""
        print("=" * 70)
        print(f"  驾驶行为事件检测 — 摘要 (fs≈{self.fs:.0f}Hz, {self.t[-1]-self.t[0]:.1f}s)")
        print("=" * 70)
        print(f"  车速: {self.speed.min():.0f}~{self.speed.max():.0f} km/h  |  "
              f"方向盘: {self.wheel.min():.1f}°~{self.wheel.max():.1f}°")
        print(f"  检测事件总数: {len(self.events)}")

        by_type = {}
        for e in self.events:
            by_type.setdefault(e.event_type, []).append(e)

        print(f"\n{'事件类型':<16} {'数量':>5}  {'示例时段':<25}  {'置信度范围'}")
        print("-" * 70)
        for etype in sorted(by_type.keys()):
            elist = by_type[etype]
            name = EVENT_TYPES.get(etype, etype)
            examples = ", ".join(
                f"{e.t_start:.1f}-{e.t_end:.1f}s" for e in elist[:3]
            )
            conf_range = f"{min(e.confidence for e in elist):.2f}~{max(e.confidence for e in elist):.2f}"
            print(f"  {name:<14} {len(elist):>5}  {examples:<25}  {conf_range}")

    def export(self, prefix: str = 'detected_events'):
        """导出事件"""
        events_json = [e.to_dict() for e in self.events]
        path = f'{prefix}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(events_json, f, indent=2, ensure_ascii=False)

        # 同时输出CSV (扁平化)
        rows = []
        for e in self.events:
            row = {'event_id': e.event_id, 'event_type': e.event_type,
                   'event_name': e.event_name, 't_start': round(e.t_start, 3),
                   't_end': round(e.t_end, 3), 'duration_s': round(e.duration_s, 3),
                   'confidence': round(e.confidence, 3)}
            for k, v in e.features.items():
                row[f'feat_{k}'] = round(v, 4) if isinstance(v, float) else v
            rows.append(row)

        pd.DataFrame(rows).to_csv(f'{prefix}.csv', index=False, encoding='utf-8-sig')
        print(f"\n  事件已导出: {prefix}.json ({len(self.events)}个), {prefix}.csv")


# ============================================================================
# 主入口
# ============================================================================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    csv_path = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else 'detected_events'

    detector = DrivingEventDetector(csv_path)
    detector.detect_all()
    detector.print_summary()
    detector.export(prefix)
