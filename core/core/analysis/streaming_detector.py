#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式检测器 — 环形缓冲 + 降采样 + 状态机 的流式处理模式

参考: sciclaw StreamingDetector 设计模式
评审报告 AR-3: 缺少流式处理模式

核心设计:
  1. 环形缓冲区(RingBuffer) — pre-allocated numpy array, O(1)写入, 避免deque→array转换
  2. 降采样控制器(DecimationController) — processing_interval 间隔触发检测
  3. 增量VDV累积 — 每帧增量更新, 无需重新扫描全量历史
  4. 车辆加速度在线计算 — diff(speed)/dt 梯度法, 匹配专家算法
"""

import time
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class StreamingConfig:
    """流式检测器配置"""
    ring_max: int = 128
    processing_interval: float = 0.1
    speed_window_for_accel: int = 5
    min_speed_points_for_accel: int = 3


@dataclass
class StreamingStats:
    """流式统计快照"""
    frame_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    buffer_usage: int = 0
    buffer_capacity: int = 0
    vdv_cumulative: float = 0.0
    peak_accel: float = 0.0
    stream_fps: float = 0.0
    is_active: bool = False
    uptime_s: float = 0.0


class RingBuffer:
    """环形缓冲区 — 固定大小, 预分配numpy数组, O(1)读写"""

    def __init__(self, capacity: int, n_channels: int = 4):
        self._capacity = capacity
        self._n_channels = n_channels
        self._buffers = [np.full(capacity, np.nan) for _ in range(n_channels)]
        self._pos = 0
        self._count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        return self._count

    def write(self, *values: float) -> None:
        idx = self._pos
        for ch, val in enumerate(values[:self._n_channels]):
            self._buffers[ch][idx] = val if val is not None else np.nan
        self._pos = (idx + 1) % self._capacity
        self._count = min(self._count + 1, self._capacity)

    def slice(self) -> Tuple[np.ndarray, ...]:
        """获取环形缓冲区的时序连续视图 (最新数据在末尾)"""
        n = min(self._count, self._capacity)
        pos = self._pos
        if n < self._capacity:
            return tuple(buf[:n] for buf in self._buffers)
        if pos == 0:
            return tuple(buf[:n] for buf in self._buffers)
        if pos >= n:
            return tuple(buf[pos - n:pos] for buf in self._buffers)
        return tuple(
            np.concatenate([buf[-(n - pos):], buf[:pos]])
            for buf in self._buffers
        )

    def last_n(self, n: int = 5) -> Tuple[np.ndarray, ...]:
        slices = self.slice()
        return tuple(s[-n:] for s in slices)

    def reset(self) -> None:
        for buf in self._buffers:
            buf.fill(np.nan)
        self._pos = 0
        self._count = 0


class DecimationController:
    """降采样控制器 — processing_interval 间隔触发"""

    def __init__(self, interval: float = 0.1):
        self._interval = interval
        self._last_process_time = -1.0

    @property
    def interval(self) -> float:
        return self._interval

    def should_process(self, timestamp: float) -> bool:
        if self._last_process_time < 0:
            return True
        return (timestamp - self._last_process_time) >= self._interval

    def mark_processed(self, timestamp: float) -> None:
        self._last_process_time = timestamp

    def reset(self) -> None:
        self._last_process_time = -1.0


class IncrementalVDV:
    """增量VDV累积器 — ISO 2631-1 VDV在线计算"""

    def __init__(self):
        self._sum4 = 0.0

    def update(self, acceleration: float, dt: float) -> None:
        if dt > 0:
            self._sum4 += (abs(acceleration) ** 4) * dt

    @property
    def value(self) -> float:
        return self._sum4 ** 0.25 if self._sum4 > 0 else 0.0

    @property
    def sum4(self) -> float:
        return self._sum4

    def reset(self) -> None:
        self._sum4 = 0.0


class StreamingDetector:
    """流式检测器 — 环形缓冲 + 降采样 + VDV累积的统一封装

    职责:
      - 管理环形缓冲区(时序/速度/方向盘/加速度)
      - 在线计算 vehicle_accel (speed梯度法)
      - 累积 VDV (ISO 2631-1)
      - 控制处理帧率 (降采样)
      - 暴露统计快照供UI监控

    不负责(由 AnalysisPipeline 负责):
      - 信号处理 (SignalProcessor)
      - 特征提取 (FeatureExtractor)
      - 状态机更新 (DrivingStateMachine)
      - 机动检测/行为分类/风险评估

    使用示例:
        detector = StreamingDetector(StreamingConfig(ring_max=256, processing_interval=0.05))
        detector.start()
        for frame in data_stream:
            stats = detector.ingest(timestamp, speed_kmh, wheel_deg)
            vehicle_accel = detector.vehicle_accel
            if detector.should_process:
                # 执行状态机更新 / 特征提取等
                pass
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        self._config = config or StreamingConfig()
        self._ring = RingBuffer(self._config.ring_max, n_channels=4)
        self._decimator = DecimationController(self._config.processing_interval)
        self._vdv = IncrementalVDV()
        self._peak_accel = 0.0
        self._vehicle_accel = 0.0

        self._frame_count = 0
        self._processed_count = 0
        self._skipped_count = 0
        self._is_active = False
        self._start_time = 0.0
        self._should_process = False

    @property
    def vehicle_accel(self) -> float:
        return self._vehicle_accel

    @property
    def should_process(self) -> bool:
        return self._should_process

    @property
    def vdv_current(self) -> float:
        return self._vdv.value

    @property
    def peak_accel(self) -> float:
        return self._peak_accel

    @property
    def is_active(self) -> bool:
        return self._is_active

    def start(self) -> None:
        self._is_active = True
        self._start_time = time.time()
        self._frame_count = 0
        self._processed_count = 0
        self._skipped_count = 0
        logger.debug(f"[StreamingDetector] 启动, interval={self._config.processing_interval}s")

    def stop(self) -> None:
        self._is_active = False
        logger.debug(
            f"[StreamingDetector] 停止, 处理{self._processed_count}帧, "
            f"跳过{self._skipped_count}帧, "
            f"VDV={self._vdv.value:.3f}, peak={self._peak_accel:.3f}"
        )

    def reset(self) -> None:
        self._ring.reset()
        self._decimator.reset()
        self._vdv.reset()
        self._peak_accel = 0.0
        self._vehicle_accel = 0.0
        self._frame_count = 0
        self._processed_count = 0
        self._skipped_count = 0
        self._is_active = False
        self._should_process = False

    def ingest(
        self,
        timestamp: float,
        speed_kmh: Optional[float] = None,
        wheel_deg: Optional[float] = None,
    ) -> StreamingStats:
        """投喂一帧数据到环形缓冲区并计算在线指标

        Returns:
            StreamingStats: 当前统计快照
        """
        self._frame_count += 1

        if speed_kmh is not None and speed_kmh >= 0:
            self._ring.write(timestamp, speed_kmh, wheel_deg or 0.0, 0.0)
        else:
            self._ring.write(timestamp, np.nan, np.nan, 0.0)

        self._vehicle_accel = 0.0

        if self._ring.count >= 2:
            self._compute_vehicle_accel()

        self._should_process = self._decimator.should_process(timestamp)
        if self._should_process:
            self._processed_count += 1
            self._decimator.mark_processed(timestamp)
        else:
            self._skipped_count += 1

        return self.get_stats()

    def _compute_vehicle_accel(self) -> None:
        """在线计算 vehicle_accel = diff(speed)/dt/3.6 (km/h→m/s²)"""
        n = min(self._config.speed_window_for_accel, self._ring.count)
        t_arr, sp_arr, _, _ = self._ring.slice()
        valid = ~np.isnan(sp_arr)
        if valid.sum() < self._config.min_speed_points_for_accel:
            return
        speeds = sp_arr[valid][-n:]
        times = t_arr[valid][-n:]
        if len(speeds) < 2 or times[-1] <= times[-2]:
            return
        dt_actual = np.median(np.diff(times))
        if dt_actual <= 0:
            return
        dv = np.mean(np.diff(speeds))
        accel = dv / dt_actual / 3.6
        self._vehicle_accel = float(accel)
        self._vdv.update(accel, dt_actual)
        if abs(accel) > self._peak_accel:
            self._peak_accel = abs(accel)

    def get_stats(self) -> StreamingStats:
        uptime = (time.time() - self._start_time) if self._start_time > 0 else 0.0
        return StreamingStats(
            frame_count=self._frame_count,
            processed_count=self._processed_count,
            skipped_count=self._skipped_count,
            buffer_usage=self._ring.count,
            buffer_capacity=self._ring.capacity,
            vdv_cumulative=round(self._vdv.value, 3),
            peak_accel=round(self._peak_accel, 3),
            stream_fps=round(self._processed_count / max(1.0, uptime), 1) if self._is_active else 0.0,
            is_active=self._is_active,
            uptime_s=round(uptime, 1),
        )