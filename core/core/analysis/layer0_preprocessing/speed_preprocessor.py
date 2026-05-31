#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Layer0 — 速度预处理器
将量化整数速度转为平滑车辆加速度

数据流：
  量化整数速度(km/h) → np.gradient → 原始加速度尖峰
  → Butterworth 5Hz 零相位低通 → 平滑 vehicle_accel(m/s²)

参照算法: test_data/验证数据/驾驶行为检测算法.py _precompute()
"""

import numpy as np
import pandas as pd
from scipy import signal
from typing import Dict, List, Any, Optional, Tuple


class SpeedPreprocessor:
    """速度反量化与车辆加速度计算

    解决 CAN 总线 1 km/h 整数分辨率导致的 np.gradient 梯度失控问题。
    参照 SAE J211-1 推荐的 Butterworth 2阶 5Hz 低通滤波器。

    Usage:
        preproc = SpeedPreprocessor()
        enriched = preproc.enrich_all(records)  # records: List[Dict] 含 speed/wheel/rel_time
        # 每条 record 新增: vehicle_accel, steer_rate, speed_ma, speed_std, wheel_std, accel_ma
    """

    CUTOFF_HZ = 5.0          # Butterworth 截止频率 (Hz)
    FILTER_ORDER = 2          # 滤波器阶数
    ROLLING_WINDOW_S = 0.5    # 滚动统计窗口 (秒)

    def __init__(self, cutoff_hz: float = None, filter_order: int = None,
                 rolling_window_s: float = None):
        self.cutoff_hz = cutoff_hz or self.CUTOFF_HZ
        self.filter_order = filter_order or self.FILTER_ORDER
        self.rolling_window_s = rolling_window_s or self.ROLLING_WINDOW_S

        # 缓存的预处理结果（供 frame-by-frame 查询）
        self._vehicle_accel: Optional[np.ndarray] = None
        self._steer_rate: Optional[np.ndarray] = None
        self._speed_ma: Optional[np.ndarray] = None
        self._speed_std: Optional[np.ndarray] = None
        self._wheel_std: Optional[np.ndarray] = None
        self._accel_ma: Optional[np.ndarray] = None

    # ──────────────────────────────────────────────
    # 批量预处理（全数据集）
    # ──────────────────────────────────────────────

    def enrich_all(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对全量数据执行预处理，为每条记录追加预处理字段

        Args:
            records: 解析器输出的记录列表，每条含 speed, wheel, rel_time/timestamp

        Returns:
            原列表（原地修改+返回），每条新增字段:
            - vehicle_accel: 车辆纵向加速度 (m/s²)
            - steer_rate: 方向盘角速率绝对值 (deg/s)
            - speed_ma: 速度滚动均值 (km/h)
            - speed_std: 速度滚动标准差 (km/h)
            - wheel_std: 方向盘角滚动标准差 (deg)
            - accel_ma: 加速度滚动均值 (m/s²)
        """
        if not records:
            return records

        N = len(records)

        # 提取数组
        speed_kmh = np.array([r.get('speed', 0.0) or 0.0 for r in records], dtype=float)
        wheel_deg = np.array([r.get('wheel', 0.0) or 0.0 for r in records], dtype=float)

        # 时间戳 — 兼容多种字段名
        if 'rel_time' in records[0]:
            t = np.array([float(r['rel_time']) for r in records], dtype=float)
        elif 'timestamp' in records[0]:
            t = np.array([float(r['timestamp']) for r in records], dtype=float)
        else:
            t = np.arange(N, dtype=float)

        # 采样间隔 — 用总时长/样本数作为有效间隔（CAN数据时间戳不规则）
        t_unique = np.unique(t)
        if len(t_unique) >= 2:
            t_total = float(t_unique[-1]) - float(t_unique[0])
            if t_total > 0:
                dt = t_total / float(len(t_unique) - 1)
            else:
                dt = 0.001
        elif N >= 2:
            t_total = float(t[-1]) - float(t[0])
            dt = t_total / float(N - 1) if t_total > 0 else 0.001
        else:
            dt = 0.001
        dt = max(dt, 5e-5)  # 防除零：最低对应 20kHz
        fs = 1.0 / dt

        # ── Step 1: 速度梯度 → 加速度 ──
        # 对量化整数速度，np.gradient 在速度跳变处产生极大尖峰
        # 策略: 降采样 → 梯度 → 裁剪到物理范围 → Butterworth
        MAX_PHYSICAL_ACCEL = 15.0  # m/s², 约1.5g, 超过此值的梯度尖峰视为量化伪影
        TARGET_FS = 100.0
        if fs > TARGET_FS:
            ds_factor = max(1, int(fs / TARGET_FS))
            speed_series = pd.Series(speed_kmh)
            speed_ds = speed_series.rolling(
                ds_factor, center=True, min_periods=1
            ).mean().iloc[::ds_factor].values
            N_ds = len(speed_ds)
            ds_indices = np.arange(0, N, ds_factor, dtype=int)[:N_ds]
            dt_ds = ds_factor * dt
            fs_ds = 1.0 / dt_ds

            raw_accel_ds = np.gradient(speed_ds, dt_ds, edge_order=2) / 3.6
            # 裁剪到物理范围
            raw_accel_ds = np.clip(raw_accel_ds, -MAX_PHYSICAL_ACCEL, MAX_PHYSICAL_ACCEL)

            nyq_ds = fs_ds / 2.0
            cutoff_norm = self.cutoff_hz / nyq_ds
            if 0.01 < cutoff_norm < 0.99:
                b, a = signal.butter(self.filter_order, cutoff_norm)
                vehicle_accel_ds = signal.filtfilt(b, a, raw_accel_ds)
            else:
                vehicle_accel_ds = raw_accel_ds.copy()

            x_orig = np.arange(N, dtype=float)
            x_ds = ds_indices.astype(float)
            min_len = min(len(x_ds), len(vehicle_accel_ds))
            vehicle_accel = np.interp(x_orig, x_ds[:min_len], vehicle_accel_ds[:min_len])
        else:
            raw_accel = np.gradient(speed_kmh, dt, edge_order=2) / 3.6
            raw_accel = np.clip(raw_accel, -MAX_PHYSICAL_ACCEL, MAX_PHYSICAL_ACCEL)
            nyq = fs / 2.0
            cutoff_norm = self.cutoff_hz / nyq
            if 0.01 < cutoff_norm < 0.99:
                b, a = signal.butter(self.filter_order, cutoff_norm)
                vehicle_accel = signal.filtfilt(b, a, raw_accel)
            else:
                vehicle_accel = raw_accel.copy()

        # ── Step 3: 方向盘角速率 ──
        steer_rate = np.abs(np.gradient(wheel_deg, dt, edge_order=2))

        # ── Step 4: 滚动统计 (0.5s 窗口) ──
        w = max(1, int(self.rolling_window_s / dt))
        speed_series = pd.Series(speed_kmh)
        wheel_series = pd.Series(wheel_deg)
        accel_series = pd.Series(vehicle_accel)

        speed_ma = speed_series.rolling(w, center=True, min_periods=1).mean().bfill().ffill().values
        speed_std = speed_series.rolling(w, center=True, min_periods=1).std().bfill().ffill().values
        wheel_std = wheel_series.rolling(w, center=True, min_periods=1).std().bfill().ffill().values
        accel_ma = accel_series.rolling(w, center=True, min_periods=1).mean().bfill().ffill().values

        # ── 缓存 ──
        self._vehicle_accel = vehicle_accel
        self._steer_rate = steer_rate
        self._speed_ma = speed_ma
        self._speed_std = speed_std
        self._wheel_std = wheel_std
        self._accel_ma = accel_ma

        # ── 写入每条记录 ──
        for i, r in enumerate(records):
            r['vehicle_accel'] = float(vehicle_accel[i])
            r['steer_rate'] = float(steer_rate[i])
            r['speed_ma'] = float(speed_ma[i])
            r['speed_std'] = float(speed_std[i])
            r['wheel_std'] = float(wheel_std[i])
            r['accel_ma'] = float(accel_ma[i])

        return records

    # ──────────────────────────────────────────────
    # 逐帧查询（streaming 兼容）
    # ──────────────────────────────────────────────

    def get_frame_values(self, index: int) -> Dict[str, float]:
        """获取指定帧的预处理值（需先调用 enrich_all）"""
        if self._vehicle_accel is None:
            return {}
        if index < 0 or index >= len(self._vehicle_accel):
            return {}
        return {
            'vehicle_accel': float(self._vehicle_accel[index]),
            'steer_rate': float(self._steer_rate[index]),
            'speed_ma': float(self._speed_ma[index]),
            'speed_std': float(self._speed_std[index]),
            'wheel_std': float(self._wheel_std[index]),
            'accel_ma': float(self._accel_ma[index]),
        }

    @property
    def vehicle_accel_array(self) -> Optional[np.ndarray]:
        return self._vehicle_accel

    @property
    def steer_rate_array(self) -> Optional[np.ndarray]:
        return self._steer_rate

    def reset(self):
        self._vehicle_accel = None
        self._steer_rate = None
        self._speed_ma = None
        self._speed_std = None
        self._wheel_std = None
        self._accel_ma = None