#!/usr/bin/env python3
"""charts/psd.py — PSD功率谱密度对比 (重写版)"""

from __future__ import annotations
import numpy as np
from scipy import signal as sp_signal
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from typing import Dict, List, Optional
import logging
from .style import S, C, CN

logger = logging.getLogger(__name__)

def create_psd_comparison(channel_map: Dict[str, Dict], exp_imus: List[str],
                          ctrl_imus: List[str], axis: str = 'Z',
                          figsize: tuple = (14, 4.5)) -> Optional[Figure]:
    """PSD功率谱密度: Welch法, 半对数坐标"""
    # 自动配对
    paired = []
    for en in exp_imus:
        bp = en.split('_',1)[1].rsplit('-',1)[0] if '_' in en else en
        cn = next((k for k in ctrl_imus if bp in k), None)
        if cn: paired.append((bp, en, cn))

    valid = [(l,e,c) for l,e,c in paired if e in channel_map and c in channel_map]
    if len(valid) < 1: return None

    n = len(valid)
    fig, axes = plt.subplots(1, n, figsize=(5*n, 4.5), dpi=S.screen_dpi())
    if n == 1: axes = [axes]
    ck = 'az' if axis.upper() == 'Z' else axis.lower()

    for ax, (loc, ei, ci) in zip(axes, valid):
        for label, imu, style in [('实验组',ei,{'color':C['exp'],'ls':'-'}),
                                   ('对照组',ci,{'color':C['ctrl'],'ls':'--'})]:
            dd = channel_map.get(imu, {}); ch = dd.get(ck)
            if ch is None or len(ch) < 256: continue
            fs = 1.0/np.median(np.diff(dd['timestamps'])) if 'timestamps' in dd and len(dd['timestamps'])>1 else 512
            nperseg = min(1024, max(128, len(ch)//4))
            try:
                f, pxx = sp_signal.welch(ch, fs, nperseg=nperseg, noverlap=nperseg//2, window='hann')
                m = (f >= 0.5) & (f <= 80)
                ax.semilogx(f[m], 10*np.log10(pxx[m]+1e-12), label=label, linewidth=1.3, **style)
            except: pass
        ax.set_xlabel('频率 (Hz)', fontsize=9, **S.cn(9))
        ax.set_ylabel(f'{axis}轴 PSD (dB)', fontsize=9, **S.cn(9))
        ax.set_title(f'{loc}', fontsize=10, **S.cnb(10))
        ax.legend(fontsize=7); ax.grid(True, alpha=0.2)
    fig.suptitle(f'PSD功率谱密度 — {axis}轴', fontsize=10, **S.cnb(10), y=1.02)
    fig.tight_layout(); return fig


def create_psd_band_comparison(channel_map: Dict[str, Dict], exp_imu: str,
                                ctrl_imu: str, figsize: tuple = (8, 3.5)) -> Optional[Figure]:
    """倍频程能量分布 — 7频段柱状图"""
    ed = channel_map.get(exp_imu, {}); cd = channel_map.get(ctrl_imu, {})
    ck = 'az'; ech = ed.get(ck); cch = cd.get(ck)
    if ech is None or cch is None: return None

    fs = 1.0/np.median(np.diff(ed['timestamps'])) if 'timestamps' in ed and len(ed['timestamps'])>1 else 512
    bands = [(0.1,1),(1,2),(2,4),(4,8),(8,20),(20,50),(50,100)]
    blabs = ['0.1-1\n晕动','1-2\n侧向','2-4\n躯干','4-8\n脊椎','8-20\n头颈','20-50\n组织','50-100\n高频']
    try:
        f, ep = sp_signal.welch(ech, fs, nperseg=1024, window='hann')
        _, cp = sp_signal.welch(cch, fs, nperseg=1024, window='hann')
    except: return None

    ev = [float(np.trapz(ep[(f>=fl)&(f<fh)], f[(f>=fl)&(f<fh)])) for fl,fh in bands]
    cv = [float(np.trapz(cp[(f>=fl)&(f<fh)], f[(f>=fl)&(f<fh)])) for fl,fh in bands]
    total_e = sum(ev); total_c = sum(cv)
    epct = [v/total_e*100 if total_e>0 else 0 for v in ev]
    cpct = [v/total_c*100 if total_c>0 else 0 for v in cv]

    fig = S.fig(*figsize); ax = fig.add_subplot(111)
    x = np.arange(len(bands)); w = 0.35
    ax.bar(x-w/2, epct, w, color=C['exp'], alpha=0.8, label='实验组', edgecolor='white')
    ax.bar(x+w/2, cpct, w, color=C['ctrl'], alpha=0.8, label='对照组', edgecolor='white')
    ax.set_xticks(x); ax.set_xticklabels(blabs, fontsize=7)
    ax.set_ylabel('能量占比 (%)', fontsize=9); ax.legend(fontsize=8)
    ax.set_title('倍频程能量分布', fontsize=10, **S.cnb(10)); ax.grid(axis='y', alpha=0.2)
    fig.tight_layout(); return fig
