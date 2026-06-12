#!/usr/bin/env python3
"""charts/timeline.py — 驾驶事件时间线 (重写版)"""

from __future__ import annotations
import numpy as np
from matplotlib.figure import Figure
import logging
from .style import S, C, EV, EV_CN, CN

logger = logging.getLogger(__name__)

def create_event_timeline(t: np.ndarray, speed: np.ndarray, wheel: np.ndarray,
                          events: list, title: str = "驾驶事件时间线",
                          figsize: tuple = (12, 5)) -> Figure:
    """事件时间线: 上车速+事件色块, 下方向盘"""
    fig = S.fig(*figsize)
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # 上车速
    ax1.plot(t, speed, color=C['exp'], linewidth=1.2, label='车速')
    ax1.fill_between(t, 0, speed, alpha=0.06, color=C['exp'])
    ax1.set_ylabel('车速 (km/h)', fontsize=9, **S.cn(9))
    ax1.set_title(title, fontsize=10, **S.cnb(10))
    ax1.grid(True, alpha=0.2); ax1.tick_params(labelsize=8)

    # 事件色块
    y_top = float(speed.max()) * 0.85 if len(speed) > 0 else 100
    y_step = float(speed.max()) * 0.05 if len(speed) > 0 else 5
    positions = []
    for evt in events[:100]:
        t0 = evt.get('t_start', evt.get('start_time', 0))
        t1 = evt.get('t_end', evt.get('end_time', t0 + 0.5))
        et = evt.get('event_type', evt.get('type', ''))
        en = evt.get('event_name', evt.get('name', ''))
        if not en or en == et:
            en = EV_CN.get(et, et)
        color = EV.get(et, '#3B82F6')
        ax1.axvspan(t0, t1, alpha=0.12, color=color)
        mid = float(t0 + t1) / 2; yi = 0
        for pm, py in positions:
            if abs(mid - pm) < 0.5: yi = max(yi, py + 1)
        positions.append((mid, yi))
        ax1.annotate(en, (mid, y_top - yi * y_step), fontsize=5, ha='center',
                     color=color, rotation=30, alpha=0.8, **S.cn(5))
    ax1.legend(fontsize=7)

    # 下方向盘
    ax2.plot(t, wheel, color=C['accent'], linewidth=0.7)
    ax2.fill_between(t, 0, wheel, alpha=0.05, color=C['accent'])
    ax2.axhline(y=0, color=C['muted'], linewidth=0.5, linestyle='--', alpha=0.4)
    ax2.set_xlabel('时间 (s)', fontsize=9, **S.cn(9))
    ax2.set_ylabel('转角 (°)', fontsize=9, **S.cn(9))
    ax2.grid(True, alpha=0.2); ax2.tick_params(labelsize=8)
    fig.tight_layout(); return fig
