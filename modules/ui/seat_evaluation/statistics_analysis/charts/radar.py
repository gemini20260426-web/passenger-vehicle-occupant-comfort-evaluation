#!/usr/bin/env python3
"""charts/radar.py — 归一化雷达图 + 衰减柱状图 + 加速度波形 + SRS + 热力图 (重写版)"""

from __future__ import annotations
import numpy as np
from scipy.signal import lfilter
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from typing import Dict, List, Optional
import logging
from .style import S, C, CN

logger = logging.getLogger(__name__)

# ═══ 归一化雷达图 ═══
def create_comparison_radar(comparison: Dict[str, Dict],
                            figsize: tuple = (7, 7)) -> Optional[Figure]:
    items = []
    for k, v in comparison.items():
        if isinstance(v, dict) and 'exp' in v and 'ctrl' in v:
            e, c = v['exp'], v['ctrl']
            if abs(c) > 1e-9: items.append((k[:10], e/c))
    if len(items) < 3: return None

    labels = [i[0] for i in items]; vals = [i[1] for i in items]
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    vp = vals + [vals[0]]; ctrl = [1.0]*len(items)+[1.0]; ap = angles + [angles[0]]

    fig = S.fig(*figsize)
    ax = fig.add_subplot(111, projection='polar')
    ax.fill(ap, vp, alpha=0.15, color=C['exp'])
    ax.plot(ap, vp, 'o-', linewidth=2, markersize=5, color=C['exp'], label='实验组')
    ax.fill(ap, ctrl, alpha=0.08, color=C['ctrl'])
    ax.plot(ap, ctrl, 's--', linewidth=1.5, markersize=4, color=C['ctrl'], label='对照组(=1.0)')
    ax.set_xticks(angles); ax.set_xticklabels(labels, fontsize=8); ax.set_yticklabels([])
    ax.set_title('归一化对比 (对照组=1.0)', fontsize=10, **S.cnb(10), pad=18)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.05), fontsize=8)
    fig.tight_layout(); return fig


# ═══ 衰减效率柱状图 ═══
def create_attenuation_bar(comparison: Dict[str, Dict],
                           figsize: tuple = (10, 5.5)) -> Optional[Figure]:
    items = {}
    for k, v in comparison.items():
        if isinstance(v, dict) and 'atten_pct' in v: items[k[:18]] = v['atten_pct']
    if not items: return None

    labels = list(items.keys()); values = list(items.values())
    colors = [C['diff'] if v > 0 else C['bad'] for v in values]

    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    bars = ax.barh(range(len(labels)), values, color=colors, height=0.6,
                   edgecolor='white', alpha=0.85)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8); ax.invert_yaxis()
    ax.axvline(x=0, color='#333', linewidth=0.8)
    ax.axvline(x=10, color=C['diff'], linewidth=0.6, linestyle='--', alpha=0.3)
    ax.axvline(x=-10, color=C['bad'], linewidth=0.6, linestyle='--', alpha=0.3)
    for b, v in zip(bars, values):
        x = b.get_width() + (1.2 if v >= 0 else -1.2)
        ax.text(x, b.get_y()+b.get_height()/2, f'{v:+.1f}%', va='center', fontsize=7,
                ha='left' if v >= 0 else 'right', fontweight='bold',
                color=C['diff'] if v > 0 else C['bad'])
    ax.set_xlabel('衰减率 (%)', fontsize=10); ax.set_title('各指标衰减效率', fontsize=10, **S.cnb(10))
    ax.grid(axis='x', alpha=0.2); fig.tight_layout(); return fig


# ═══ 三轴加速度波形 ═══
def create_acceleration_waveform(channel_map: Dict[str, Dict],
                                  exp_imus: List[str] = None,
                                  ctrl_imus: List[str] = None,
                                  figsize: tuple = (14, 8)) -> Optional[Figure]:
    if exp_imus is None: exp_imus = [k for k in channel_map if k.endswith('-1')][:3]
    if ctrl_imus is None: ctrl_imus = [k for k in channel_map if k.endswith('-2')][:3]
    if not exp_imus: return None

    akeys = ['ax','ay','az']; alabs = ['Ax 纵向 (m/s²)','Ay 侧向 (m/s²)','Az 垂向 (m/s²)']
    ecols = ['#DC2626','#2563EB','#059669']; ccols = ['#991B1B','#1D4ED8','#047857']

    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True, dpi=S.screen_dpi())
    for row, (ak, yl) in enumerate(zip(akeys, alabs)):
        ax = axes[row]
        for i, imu in enumerate(exp_imus[:3]):
            dd = channel_map.get(imu, {}); ch = dd.get(ak)
            if ch is None: continue
            t = dd.get('timestamps', np.arange(len(ch)))
            if len(t) != len(ch): t = np.linspace(0, len(ch)/512, len(ch))
            ax.plot(t, ch, alpha=[0.85,0.6,0.4][i], linewidth=0.7,
                    color=ecols[row], label=f'实验-{i+1}')
        for i, imu in enumerate(ctrl_imus[:3]):
            dd = channel_map.get(imu, {}); ch = dd.get(ak)
            if ch is None: continue
            t = dd.get('timestamps', np.arange(len(ch)))
            if len(t) != len(ch): t = np.linspace(0, len(ch)/512, len(ch))
            ax.plot(t, ch, alpha=[0.85,0.6,0.4][i], linewidth=0.7,
                    color=ccols[row], linestyle='--', label=f'对照-{i+1}')
        ax.set_ylabel(yl, fontsize=9); ax.legend(fontsize=6, ncol=3)
        ax.grid(True, alpha=0.2)
    axes[0].set_title('三轴加速度时域波形', fontsize=10, **S.cnb(10))
    axes[-1].set_xlabel('时间 (s)', fontsize=10); fig.tight_layout(); return fig


# ═══ SRS冲击响应谱 (向量化) ═══
def create_srs_comparison(channel_map: Dict[str, Dict], exp_imu: str, ctrl_imu: str,
                          location_name: str = "", axis: str = 'X',
                          figsize: tuple = (10, 4.5)) -> Optional[Figure]:
    ck = {'X':'ax','Y':'ay','Z':'az'}.get(axis.upper(), 'ax')
    fig = S.fig(*figsize); ax = fig.add_subplot(111)

    for label, imu, ls, color in [('实验组',exp_imu,'-',C['exp']),('对照组',ctrl_imu,'--',C['ctrl'])]:
        dd = channel_map.get(imu, {}); ch = dd.get(ck)
        if ch is None: continue
        fs = 1.0/np.median(np.diff(dd['timestamps'])) if 'timestamps' in dd and len(dd['timestamps'])>1 else 512
        fn = np.logspace(np.log10(0.5), np.log10(100), 60)
        Qv, zeta, dt = 10.0, 0.05, 1.0/fs
        acc = np.asarray(ch, dtype=np.float64); srs = np.zeros(len(fn))
        for i_f, f in enumerate(fn):
            wn = 2*np.pi*f; wd = wn*np.sqrt(1-zeta*zeta)
            E = np.exp(-zeta*wn*dt)
            den = [1.0, -2*E*np.cos(wd*dt), E*E]
            A = 1-wn*dt; B = wn*dt*E*np.sin(wd*dt)/wd
            num = [A*B, A*(E*np.cos(wd*dt)-1)-B]
            srs[i_f] = float(np.max(np.abs(lfilter(num, den, acc))))
        ax.loglog(fn, srs/9.81, label=label, color=color, linestyle=ls, linewidth=1.5)

    ax.set_xlabel('频率 (Hz)', fontsize=9); ax.set_ylabel('SRS (g)', fontsize=9)
    t = f'{location_name} {axis}轴 冲击响应谱' if location_name else f'{axis}轴 SRS'
    ax.set_title(t, fontsize=10, **S.cnb(10)); ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, which='both')
    fig.suptitle('SRS冲击响应谱 (Q=10)', fontsize=10, **S.cnb(10)); fig.tight_layout(); return fig


# ═══ 指标热力图 ═══
def create_metric_heatmap(location_results: Dict[str, Dict], metric_list: List[str],
                          location_ids: List[str], figsize: tuple = (12, 7)) -> Optional[Figure]:
    nm, nl = len(metric_list), len(location_ids)
    data = np.full((nm, nl), np.nan)
    for i, mid in enumerate(metric_list):
        for j, loc in enumerate(location_ids):
            lr = location_results.get(loc, {})
            em = lr.get('metrics',{}).get(mid, float('nan'))
            cm = lr.get('control_metrics',{}).get(mid, float('nan'))
            if np.isfinite(em) and np.isfinite(cm) and abs(cm) > 1e-9:
                data[i, j] = (cm - em) / abs(cm) * 100

    if np.all(np.isnan(data)): return None
    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    im = ax.imshow(data, aspect='auto', cmap='RdYlGn', vmin=-50, vmax=50)
    for i in range(nm):
        for j in range(nl):
            v = data[i, j]
            if np.isfinite(v):
                c = 'white' if abs(v) > 25 else 'black'
                ax.text(j, i, f'{v:.0f}%', ha='center', va='center', fontsize=6,
                        fontweight='bold', color=c)
    ax.set_xticks(range(nl)); ax.set_xticklabels(location_ids, fontsize=8)
    ax.set_yticks(range(nm)); ax.set_yticklabels(metric_list, fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.9, label='改善率 (%)')
    ax.set_title('指标改善率热力图', fontsize=10, **S.cnb(10)); fig.tight_layout(); return fig


# ═══ STFT时频图 ═══
def create_stft_chart(stft_data: dict, figsize: tuple = (8, 4)) -> Optional[Figure]:
    s = stft_data.get('Ay', stft_data) if stft_data else None
    if not s or 'exp_spec' not in s: return None
    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    im = ax.pcolormesh(s.get('t',[]), s.get('f',[]),
                       10*np.log10(np.abs(s['exp_spec'])+1e-10),
                       vmin=-80, vmax=-20, cmap='viridis')
    ax.set_ylim(0, 50); ax.set_ylabel('频率 (Hz)', fontsize=9)
    ax.set_xlabel('时间 (s)', fontsize=9); ax.set_title('STFT时频图 — 实验组', fontsize=10, **S.cnb(10))
    fig.colorbar(im, ax=ax, label='Power (dB)'); fig.tight_layout(); return fig


# ═══ 滑动窗口趋势 ═══
def create_sliding_window_chart(window_results: list, figsize: tuple = (8, 3)) -> Optional[Figure]:
    if not window_results: return None
    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    tc = [w.get('t_center', i) for i, w in enumerate(window_results)]
    att = [w.get('attenuation_pct', w.get('atten_Ay_pct', 0)) for w in window_results]
    ax.plot(tc, att, color=C['diff'], linewidth=1.2, alpha=0.85)
    ax.fill_between(tc, 0, att, alpha=0.08, color=C['diff'])
    ax.axhline(y=0, color=C['muted'], linewidth=0.6, linestyle='--', alpha=0.4)
    ax.set_xlabel('时间 (s)', fontsize=9); ax.set_ylabel('衰减率 (%)', fontsize=9)
    ax.set_title('滑动窗口衰减趋势', fontsize=10, **S.cnb(10)); ax.grid(alpha=0.2)
    fig.tight_layout(); return fig


# ═══ 频段衰减柱状图 ═══
def create_band_attenuation_chart(spectrum: dict, figsize: tuple = (7, 3.5)) -> Optional[Figure]:
    ba = spectrum.get('bands_atten', {})
    bands = ['0.1-0.5Hz','0.5-1Hz','1-5Hz','5-20Hz','20-80Hz']
    vals = [ba.get(b, 0) for b in bands]
    if sum(abs(v) for v in vals) < 0.01: return None
    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    colors = [C['diff'] if v > 0 else C['bad'] for v in vals]
    ax.bar(bands, vals, color=colors, alpha=0.8, edgecolor='white')
    ax.axhline(y=0, color='#333', linewidth=0.8)
    for i, v in enumerate(vals):
        ax.text(i, v+0.3 if v>=0 else v-2, f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')
    ax.set_ylabel('衰减率 (%)', fontsize=9); ax.set_title('频段衰减分析', fontsize=10, **S.cnb(10))
    ax.grid(axis='y', alpha=0.2); fig.tight_layout(); return fig


# ═══ 频段雷达图 ═══
def create_band_radar_chart(spectrum: dict, figsize: tuple = (5, 5)) -> Optional[Figure]:
    ba = spectrum.get('bands_atten', {})
    bands = ['0.1-0.5Hz','0.5-1Hz','1-5Hz','5-20Hz','20-80Hz']
    vals = [ba.get(b, 0) for b in bands]
    if sum(abs(v) for v in vals) < 0.01: return None
    angles = np.linspace(0, 2*np.pi, len(bands), endpoint=False)
    fig = S.fig(*figsize); ax = fig.add_subplot(111, projection='polar')
    vc = vals + [vals[0]]; ac = np.append(angles, angles[0])
    ax.fill(ac, vc, alpha=0.15, color=C['exp'])
    ax.plot(ac, vc, 'o-', linewidth=2, markersize=5, color=C['exp'])
    ax.set_xticks(angles); ax.set_xticklabels(bands, fontsize=7); ax.set_yticklabels([])
    ax.set_title('频段衰减雷达图', fontsize=10, **S.cnb(10), pad=18); fig.tight_layout(); return fig
