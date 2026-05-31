#!/usr/bin/env python3
"""
驾驶行为事件流式检测引擎 V4.0
==============================
支持三种模式:
  1. 批量模式 (Batch)    — 加载完整CSV, 一次性检测全部事件
  2. 流式模式 (Stream)   — 逐帧/逐窗口输入, 实时检测
  3. 混合模式 (Hybrid)   — 模拟实时流, 从CSV逐帧读取

核心设计:
  - 环形缓冲区 (CircularBuffer)      — 维护最近N秒的历史数据
  - 事件状态机 (EventStateMachine)   — 跟踪事件的生命周期
  - 增量指标计算器 (OnlineMetrics)    — 在线更新VDV/S_d等累积指标

用法:
  from driving_event_streaming import StreamingDetector
  
  # 批量模式
  detector = StreamingDetector()
  events = detector.process_batch("data.csv")
  
  # 流式模式
  detector = StreamingDetector(buffer_sec=5.0)
  for frame in data_stream:
      events = detector.process_sample(t, ax, ay, az, gx, gy, gz, speed, wheel)
      if events:
          for e in events:
              print(f"检测到: {e}")

作者: SciClaw | 版本: V4.0 Streaming | 日期: 2026-05-23
"""

import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
from enum import Enum
import pandas as pd
import json, sys, time

# ============================================================================
# 事件类型与状态
# ============================================================================

class EventState(Enum):
    BEGIN  = "begin"   # 事件开始
    UPDATE = "update"  # 事件进行中
    END    = "end"     # 事件结束
    SINGLE = "single"  # 瞬时事件(无持续)

EVENT_TYPES = {
    'constant_speed':    '匀速直行',   'normal_accel':  '正常加速',
    'normal_decel':      '正常减速',   'cruising':      '恒速行驶',
    'stopped':           '停车',       'parked':        '驻车',
    'lane_keeping':      '车道保持',   'left_turn':     '左转',
    'right_turn':        '右转',       'tight_turn':    '小半径转弯',
    'wide_turn':         '大半径转弯', 'u_turn':        'U型转弯',
    'corner_accel':      '弯道加速',   'corner_decel':  '弯道减速',
    'aggressive_accel':  '激进加速',   'aggressive_decel': '激进减速',
    'hard_brake':        '急刹车',     'slalom':        '蛇形驾驶',
    'rapid_lane_change': '急速变向',   'severe_bump':   '剧烈颠簸',
    'side_slip_risk':    '侧滑风险',   'rollover_risk': '侧翻风险',
}

@dataclass
class StreamEvent:
    """流式事件"""
    event_type: str
    event_name: str
    state: EventState
    t_start: float
    t_current: float
    duration_s: float
    confidence: float
    features: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'event_type': self.event_type, 'event_name': self.event_name,
            'state': self.state.value, 't_start': round(self.t_start, 3),
            't_current': round(self.t_current, 3),
            'duration_s': round(self.duration_s, 3),
            'confidence': round(self.confidence, 3),
            'features': {k: round(v, 4) if isinstance(v, float) else v
                         for k, v in self.features.items()}
        }

# ============================================================================
# 环形缓冲区
# ============================================================================

class CircularBuffer:
    """固定时长的环形缓冲区, 高效维护最近N秒的历史数据"""

    def __init__(self, max_sec: float = 5.0, fs: float = 1000.0):
        self.fs = fs
        self.max_samples = int(max_sec * fs)
        self.dt = 1.0 / fs

        # 数据缓冲 (预分配, 避免动态realloc)
        self.t = np.full(self.max_samples, np.nan)
        self.ax = np.full(self.max_samples, np.nan)
        self.ay = np.full(self.max_samples, np.nan)
        self.az = np.full(self.max_samples, np.nan)
        self.gx = np.full(self.max_samples, np.nan)
        self.gy = np.full(self.max_samples, np.nan)
        self.gz = np.full(self.max_samples, np.nan)
        self.speed = np.full(self.max_samples, np.nan)
        self.wheel = np.full(self.max_samples, np.nan)

        self.write_pos = 0   # 当前写入位置
        self.total_written = 0

    def push(self, t: float, ax: float, ay: float, az: float,
             gx: float, gy: float, gz: float, speed: float, wheel: float):
        """写入一个采样帧"""
        idx = self.write_pos
        self.t[idx] = t
        self.ax[idx] = ax; self.ay[idx] = ay; self.az[idx] = az
        self.gx[idx] = gx; self.gy[idx] = gy; self.gz[idx] = gz
        self.speed[idx] = speed; self.wheel[idx] = wheel

        self.write_pos = (self.write_pos + 1) % self.max_samples
        self.total_written += 1

    @property
    def count(self) -> int:
        """有效样本数"""
        return min(self.total_written, self.max_samples)

    def get_slice(self) -> Tuple[np.ndarray, ...]:
        """获取有效数据的连续视图 (按时间排序)"""
        n = self.count
        if n < self.max_samples:
            return (self.t[:n], self.ax[:n], self.ay[:n], self.az[:n],
                    self.gx[:n], self.gy[:n], self.gz[:n],
                    self.speed[:n], self.wheel[:n])
        else:
            pos = self.write_pos
            t = np.concatenate([self.t[pos:], self.t[:pos]])
            ax = np.concatenate([self.ax[pos:], self.ax[:pos]])
            ay = np.concatenate([self.ay[pos:], self.ay[:pos]])
            az = np.concatenate([self.az[pos:], self.az[:pos]])
            gx = np.concatenate([self.gx[pos:], self.gx[:pos]])
            gy = np.concatenate([self.gy[pos:], self.gy[:pos]])
            gz = np.concatenate([self.gz[pos:], self.gz[:pos]])
            speed = np.concatenate([self.speed[pos:], self.speed[:pos]])
            wheel = np.concatenate([self.wheel[pos:], self.wheel[:pos]])
            return t, ax, ay, az, gx, gy, gz, speed, wheel

    def get_window(self, duration_s: float) -> Tuple[np.ndarray, ...]:
        """获取最近 duration_s 秒的窗口数据"""
        t, ax, ay, az, gx, gy, gz, speed, wheel = self.get_slice()
        if len(t) == 0:
            return t, ax, ay, az, gx, gy, gz, speed, wheel

        t_end = t[-1]
        mask = (t >= t_end - duration_s)
        return (t[mask], ax[mask], ay[mask], az[mask],
                gx[mask], gy[mask], gz[mask], speed[mask], wheel[mask])


# ============================================================================
# 事件状态机
# ============================================================================

class EventStateMachine:
    """管理每个事件类型的状态转移"""

    def __init__(self):
        # 每种事件类型的活跃状态 {event_type: StreamEvent or None}
        self.active_events: Dict[str, Optional[StreamEvent]] = {}
        # 事件历史 (已完成的)
        self.completed_events: List[StreamEvent] = []

    def update(self, event_type: str, cond: bool, t: float,
               features: Dict = None, confidence: float = 0.8,
               min_duration_s: float = 0.2,
               gap_tolerance_s: float = 0.3) -> Optional[StreamEvent]:
        """
        更新事件状态

        Args:
            event_type: 事件类型编码
            cond: 当前帧是否满足条件
            t: 当前时间
            confidence: 置信度
            min_duration_s: 最小持续时长 (低于此时长的视为噪声)

        Returns:
            StreamEvent or None
        """
        active = self.active_events.get(event_type)

        if cond:
            if active is None:
                # 事件开始
                evt = StreamEvent(
                    event_type=event_type,
                    event_name=EVENT_TYPES.get(event_type, event_type),
                    state=EventState.BEGIN, t_start=t, t_current=t,
                    duration_s=0.0, confidence=confidence,
                    features=features or {}
                )
                self.active_events[event_type] = evt
                return evt
            else:
                # 事件持续
                gap = t - active.t_current
                if gap > gap_tolerance_s:
                    # 间隔太长 → 结束旧事件, 开始新事件
                    active.state = EventState.END
                    active.t_current = t
                    active.duration_s = t - active.t_start
                    self.completed_events.append(active)

                    evt = StreamEvent(
                        event_type=event_type,
                        event_name=EVENT_TYPES.get(event_type, event_type),
                        state=EventState.BEGIN, t_start=t, t_current=t,
                        duration_s=0.0, confidence=confidence,
                        features=features or {}
                    )
                    self.active_events[event_type] = evt
                    return evt
                else:
                    # 正常持续
                    active.t_current = t
                    active.duration_s = t - active.t_start
                    if features:
                        active.features.update(features)
                    # 不返回事件 (减少输出噪声)
                    return None
        else:
            if active is not None:
                # 事件可能结束
                gap = t - active.t_current
                if gap > gap_tolerance_s:
                    # 确认结束
                    active.state = EventState.END
                    active.t_current = t
                    active.duration_s = t - active.t_start
                    self.active_events[event_type] = None

                    if active.duration_s >= min_duration_s:
                        self.completed_events.append(active)
                        return active
                    else:
                        # 持续时间太短, 丢弃
                        return None
                    return None

        return None

    def flush(self, t: float):
        """强制结束所有活跃事件"""
        flushed = []
        for etype, evt in self.active_events.items():
            if evt is not None:
                evt.state = EventState.END
                evt.duration_s = t - evt.t_start
                self.completed_events.append(evt)
                flushed.append(evt)
                self.active_events[etype] = None
        return flushed

    def get_all_events(self) -> List[StreamEvent]:
        """获取全部事件 (活跃中的 + 已完成的)"""
        all_events = list(self.completed_events)
        for evt in self.active_events.values():
            if evt is not None and evt.duration_s > 0:
                all_events.append(evt)
        all_events.sort(key=lambda e: e.t_start)
        return all_events


# ============================================================================
# 在线指标计算器
# ============================================================================

class OnlineMetrics:
    """支持增量更新的在线指标计算器"""

    def __init__(self):
        # VDV 累积量
        self.vdv_z_sum4 = 0.0
        # FDS 用循环计数
        self.rainflow_cycles = []
        # 峰值跟踪
        self.a_mag_peak = 0.0

    def update_vdv(self, az_weighted: float, dt: float):
        """增量更新VDV: VDV = (Σ a⁴·Δt)^(1/4)"""
        self.vdv_z_sum4 += (az_weighted ** 4) * dt

    def get_vdv(self) -> float:
        return self.vdv_z_sum4 ** 0.25

    def update_peak(self, a_mag: float):
        """更新合成加速度峰值"""
        if a_mag > self.a_mag_peak:
            self.a_mag_peak = a_mag

    def reset(self):
        self.vdv_z_sum4 = 0.0
        self.rainflow_cycles.clear()
        self.a_mag_peak = 0.0


# ============================================================================
# 流式检测器
# ============================================================================

class StreamingDetector:
    """流式驾驶行为事件检测器"""

    def __init__(self, buffer_sec: float = 5.0, fs: float = 1000.0,
                 callback: Callable = None):
        """
        Args:
            buffer_sec: 环形缓冲区时长 (秒)
            fs: 采样频率
            callback: 事件回调函数 callback(StreamEvent)
        """
        self.buf = CircularBuffer(buffer_sec, fs)
        self.fsm = EventStateMachine()
        self.metrics = OnlineMetrics()
        self.callback = callback
        self.fs = fs
        self.dt = 1.0 / fs
        self.frame_count = 0
        self.processing_interval = 0.1  # 每0.1秒触发一次检测 (减少计算开销)

    def _compute_features(self, t, ax, ay, az, gx, gy, gz, speed, wheel):
        """从窗口数据计算特征"""
        a_mag = np.sqrt(ax**2 + ay**2 + az**2)

        # 车辆加速度 (从speed估算)
        if len(speed) > 1:
            vehicle_accel = np.mean(np.diff(speed[-min(5, len(speed)):])) / self.dt / 3.6
        else:
            vehicle_accel = 0.0

        return {
            'speed_mean': float(np.mean(speed)),
            'speed_std': float(np.std(speed)) if len(speed)>1 else 0.0,
            'wheel_mean': float(np.mean(wheel)),
            'wheel_std': float(np.std(wheel)) if len(wheel)>1 else 0.0,
            'wheel_range': float(np.max(wheel)-np.min(wheel)) if len(wheel)>0 else 0.0,
            'vehicle_accel': float(vehicle_accel),
            'a_mag_max': float(np.max(a_mag)),
            'a_mag_rms': float(np.sqrt(np.mean(a_mag**2))),
            'a_lat_max': float(np.max(np.abs(ay))),
            'a_vert_max': float(np.max(np.abs(az))),
            'roll_rate_max': float(np.max(np.abs(gx))),
        }

    def process_sample(self, t: float, ax: float, ay: float, az: float,
                       gx: float, gy: float, gz: float,
                       speed: float, wheel: float) -> List[StreamEvent]:
        """处理单个采样帧, 返回新检测到的事件列表"""

        # 写入缓冲
        self.buf.push(t, ax, ay, az, gx, gy, gz, speed, wheel)
        self.frame_count += 1

        # 更新在线指标
        a_mag = np.sqrt(ax**2 + ay**2 + az**2)
        self.metrics.update_peak(a_mag)

        # 降频处理: 每 processing_interval 秒检测一次
        if self.frame_count % max(1, int(self.processing_interval / self.dt)) != 0:
            return []

        # 获取窗口数据
        tw, axw, ayw, azw, gxw, gyw, gzw, sw, ww = self.buf.get_window(1.5)
        if len(tw) < 10:
            return []

        # 计算特征
        feat = self._compute_features(tw, axw, ayw, azw, gxw, gyw, gzw, sw, ww)

        # ---- 逐类型检测 ----
        triggered = []
        sp_mean = feat['speed_mean']
        sp_std = feat['speed_std']
        wh_mean = feat['wheel_mean']
        wh_std = feat['wheel_std']
        wh_range = feat['wheel_range']
        accel = feat['vehicle_accel']

        # 速度基事件
        triggered.extend(self._detect_speed(sp_mean, sp_std, accel, t, feat))
        # 转向基事件
        triggered.extend(self._detect_steering(wh_mean, wh_std, wh_range, sp_mean, t, feat))
        # 复合事件
        triggered.extend(self._detect_compound(wh_mean, sp_mean, accel, t, feat))
        # 激进事件
        triggered.extend(self._detect_aggressive(accel, sp_mean, t, feat))
        # 动态事件
        triggered.extend(self._detect_dynamic(ww, tw, sp_mean, t, feat))
        # IMU事件
        triggered.extend(self._detect_imu(feat, sp_mean, t))

        # 回调
        if self.callback:
            for evt in triggered:
                self.callback(evt)

        return triggered

    def _detect_speed(self, sp_mean, sp_std, accel, t, feat):
        events = []
        # 驻车/停车
        evt = self.fsm.update('parked', sp_mean <= 1, t, feat, 0.95, 1.0, 1.5)
        if evt: events.append(evt)
        evt = self.fsm.update('stopped', sp_mean <= 1, t, feat, 0.95, 0.3, 0.5)
        if evt: events.append(evt)

        # 恒速行驶
        evt = self.fsm.update('cruising', sp_mean > 5 and sp_std < 3, t, feat, 0.85, 1.0, 0.5)
        if evt: events.append(evt)

        # 匀速直行
        evt = self.fsm.update('constant_speed',
            sp_mean > 5 and sp_std < 2 and abs(feat['wheel_mean']) < 1, t, feat, 0.85, 1.0, 0.5)
        if evt: events.append(evt)

        # 正常加速
        evt = self.fsm.update('normal_accel',
            0.5 < accel < 3.0 and sp_mean > 3, t, feat, 0.80, 0.3, 0.3)
        if evt: events.append(evt)

        # 正常减速
        evt = self.fsm.update('normal_decel',
            -3.0 < accel < -0.5 and sp_mean > 3, t, feat, 0.80, 0.3, 0.3)
        if evt: events.append(evt)

        return events

    def _detect_steering(self, wh_mean, wh_std, wh_range, sp_mean, t, feat):
        events = []
        # 车道保持
        evt = self.fsm.update('lane_keeping',
            abs(wh_mean) < 1 and wh_std < 0.5 and sp_mean > 5, t, feat, 0.85, 2.0, 0.5)
        if evt: events.append(evt)

        # 左转/右转
        evt = self.fsm.update('left_turn', wh_mean < -2 and sp_mean > 3, t, feat, 0.85, 0.3, 0.3)
        if evt: events.append(evt)
        evt = self.fsm.update('right_turn', wh_mean > 2 and sp_mean > 3, t, feat, 0.85, 0.3, 0.3)
        if evt: events.append(evt)

        # 小/大半径转弯
        evt = self.fsm.update('tight_turn', abs(wh_mean) > 15 and sp_mean > 3, t, feat, 0.80, 0.3, 0.2)
        if evt: events.append(evt)
        evt = self.fsm.update('wide_turn',
            3 < abs(wh_mean) < 15 and sp_mean > 5, t, feat, 0.75, 1.0, 0.5)
        if evt: events.append(evt)

        # U型转弯
        evt = self.fsm.update('u_turn',
            wh_range > 30 and abs(wh_mean) > 10 and sp_mean > 2, t, feat, 0.70, 1.0, 0.5)
        if evt: events.append(evt)

        return events

    def _detect_compound(self, wh_mean, sp_mean, accel, t, feat):
        events = []
        in_corner = abs(wh_mean) > 3
        evt = self.fsm.update('corner_accel',
            in_corner and accel > 0.5 and sp_mean > 3, t, feat, 0.75, 0.3, 0.3)
        if evt: events.append(evt)
        evt = self.fsm.update('corner_decel',
            in_corner and accel < -0.5 and sp_mean > 3, t, feat, 0.75, 0.3, 0.3)
        if evt: events.append(evt)
        return events

    def _detect_aggressive(self, accel, sp_mean, t, feat):
        events = []
        evt = self.fsm.update('aggressive_accel',
            accel > 3.0 and sp_mean > 3, t, feat, 0.85, 0.2, 0.2)
        if evt: events.append(evt)
        evt = self.fsm.update('aggressive_decel',
            accel < -3.0 and sp_mean > 3, t, feat, 0.85, 0.2, 0.2)
        if evt: events.append(evt)
        evt = self.fsm.update('hard_brake',
            accel < -5.0 and sp_mean > 5, t, feat, 0.90, 0.15, 0.2)
        if evt: events.append(evt)
        return events

    def _detect_dynamic(self, ww, tw, sp_mean, t, feat):
        events = []
        # 蛇形: 零交叉 ≥ 2 + 幅值 > 5°
        if len(ww) > 3:
            zero_crossings = np.sum(np.diff(np.signbit(ww)))
            if zero_crossings >= 2 and feat['wheel_range'] > 5 and sp_mean > 10:
                evt = self.fsm.update('slalom', True, t, feat, 0.75, 0.5, 0.5)
                if evt: events.append(evt)
            else:
                self.fsm.update('slalom', False, t, feat)

        # 急速变向: 转向速率
        if len(tw) > 1:
            steer_rate = np.abs(np.diff(ww[-min(5, len(ww)):])).mean() / (tw[1]-tw[0])
            evt = self.fsm.update('rapid_lane_change',
                steer_rate > 50 and sp_mean > 10, t, feat, 0.80, 0.2, 0.2)
            if evt: events.append(evt)

        return events

    def _detect_imu(self, feat, sp_mean, t):
        events = []
        evt = self.fsm.update('severe_bump',
            feat['a_vert_max'] > 15, t, feat, 0.85, 0.05, 0.1)
        if evt: events.append(evt)
        evt = self.fsm.update('side_slip_risk',
            feat['a_lat_max'] > 5 and sp_mean > 20, t, feat, 0.75, 0.2, 0.2)
        if evt: events.append(evt)
        evt = self.fsm.update('rollover_risk',
            feat['a_lat_max'] > 6 and feat['roll_rate_max'] > 20 and sp_mean > 20,
            t, feat, 0.70, 0.15, 0.2)
        if evt: events.append(evt)
        return events

    def flush(self, t: float) -> List[StreamEvent]:
        """强制结束所有活跃事件"""
        return self.fsm.flush(t)

    def get_all_events(self) -> List[StreamEvent]:
        return self.fsm.get_all_events()

    # ====================================================================
    # 批量模式 (兼容现有接口)
    # ====================================================================
    def process_batch(self, csv_path: str,
                      ref_imu: str = 'IMU1_头部眉心-1') -> List[StreamEvent]:
        """批量处理CSV文件 (模拟流式逐帧输入)"""
        df = pd.read_csv(csv_path)
        ref = df[(df['channel'] == 'ch1') &
                 (df['imu_name'] == ref_imu)].sort_values('rel_time')

        print(f"流式处理: {len(ref)} 帧, {ref['rel_time'].iloc[-1]-ref['rel_time'].iloc[0]:.1f}s")
        t0 = time.time()

        all_triggered = []
        for _, row in ref.iterrows():
            triggered = self.process_sample(
                row['rel_time'],
                row['Ax_m_s2'], row['Ay_m_s2'], row['Az_m_s2'],
                row['Gx_dps'], row['Gy_dps'], row['Gz_dps'],
                row['speed'], row['wheel']
            )
            all_triggered.extend(triggered)

        # 刷新残余
        all_triggered.extend(self.flush(ref['rel_time'].iloc[-1]))

        elapsed = time.time() - t0
        print(f"完成: {elapsed:.2f}s, {len(ref)/elapsed:.0f} 帧/s, "
              f"检测到 {len(all_triggered)} 个事件边界")

        return all_triggered

    def print_summary(self):
        """打印检测摘要"""
        events = self.get_all_events()
        print(f"\n检测事件总数: {len(events)} (含中间状态)")

        # 仅统计完整事件
        completed = [e for e in events if e.state in (EventState.END, EventState.SINGLE)]
        by_type = {}
        for e in completed:
            by_type.setdefault(e.event_type, []).append(e)

        for etype in sorted(by_type):
            elist = by_type[etype]
            print(f"  {EVENT_TYPES.get(etype, etype):<14} ×{len(elist):>2}  "
                  f"t={elist[0].t_start:.1f}~{elist[-1].t_current:.1f}s, "
                  f"dur={sum(e.duration_s for e in elist):.1f}s")


# ============================================================================
# 测试
# ============================================================================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n用法:")
        print("  python driving_event_streaming.py <data.csv>  # 批量模式(模拟流式)")
        sys.exit(1)

    detector = StreamingDetector(buffer_sec=5.0, fs=1000.0)
    events = detector.process_batch(sys.argv[1])
    detector.print_summary()

    # 导出
    if len(events) > 0:
        json.dump([e.to_dict() for e in events],
                  open('streaming_events.json', 'w', encoding='utf-8'),
                  indent=2, ensure_ascii=False)
        print("\n导出: streaming_events.json")
