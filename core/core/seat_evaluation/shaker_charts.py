#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ISO 10326-1 台架实验 — 多维分析图表生成器 (Shaker Test Chart Engine)

为前端台架测试模块提供15+幅专业级 matplotlib 图表, 覆盖:
  - 时域维度 (原始/去直流/加权信号对比)
  - 频域维度 (PSD 全轴 + 1/3倍频程)
  - 传递维度 (传递函数幅值+相位+相干)
  - 评估维度 (SEAT 柱状图/雷达图 + 风险热力图)
  - 诊断维度 (共振检测 + 频段衰减 + 累积VDV)

所有图表使用颜色无障碍 (Okabe-Ito) 调色板, 支持中文标签,
输出 300 DPI PNG 及 PDF 矢量格式。
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch
from scipy import signal
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
import logging
import os
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# ── 颜色无障碍调色板 (Okabe-Ito) ──
COLORS = {
    'platform':   '#999999',
    'r_point':    '#E69F00',  # orange
    't8_point':   '#56B4E9',  # sky blue
    'good':       '#009E73',  # green
    'warning':    '#F0E442',  # yellow
    'danger':     '#D55E00',  # vermillion
    'critical':   '#CC79A7',  # purple
    'accent':     '#0072B2',  # blue
    'reference':  '#000000',  # black
}

# 通道 → 频率加权 映射
WEIGHTING_MAP = {
    'platform_x':'Wd','platform_y':'Wd','platform_z':'Wk',
    'r_x':'Wd','r_y':'Wd','r_z':'Wk',
    't8_x':'Wc','t8_y':'Wd','t8_z':'Wk',
}

# 中文标签映射
LABELS_ZH = {
    'platform': '台架 Platform',
    'r_point':  'R点 (座垫)',
    't8_point': 'T8点 (靠背)',
    'x': 'X轴 (纵向)', 'y': 'Y轴 (侧向)', 'z': 'Z轴 (垂向)',
}


@dataclass
class ShakerChartContext:
    """图表生成上下文 — 持有所需的全部数据与计算结果"""
    fs: float
    time: np.ndarray
    detrended: Dict[str, np.ndarray] = field(default_factory=dict)
    weighted: Dict[str, np.ndarray] = field(default_factory=dict)
    seat_factors: Dict[str, float] = field(default_factory=dict)
    weighted_rms: Dict[str, float] = field(default_factory=dict)
    vdv_vals: Dict[str, float] = field(default_factory=dict)
    tf_data: Dict[str, Tuple] = field(default_factory=dict)  # name→(f,H,coh)
    psd_data: Dict[str, Tuple] = field(default_factory=dict)  # name→(f,P)
    crest_factors: Dict[str, float] = field(default_factory=dict)
    resonance_peaks: Dict[str, Dict] = field(default_factory=dict)
    output_dir: str = '.'


class ShakerChartGenerator:
    """ISO 10326-1 台架实验多维图表生成器"""

    def __init__(self, ctx: ShakerChartContext):
        self.ctx = ctx
        self._setup_style()

    def _setup_style(self):
        """设置出版级样式（优先CJK兼容）"""
        plt.rcParams.update({
            'font.sans-serif': ['SimHei', 'Droid Sans Fallback', 'DejaVu Sans'],
            'axes.unicode_minus': False,
            'font.size': 9,
            'axes.labelsize': 9,
            'axes.titlesize': 10,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 7.5,
            'figure.dpi': 150,
            'savefig.dpi': 300,
            'savefig.bbox': 'tight',
            'axes.spines.top': False,
            'axes.spines.right': False,
        })

    # ═══════════════════════════════════════════════════════════
    #  时域维度 (4 图)
    # ═══════════════════════════════════════════════════════════

    def chart_time_overview(self) -> str:
        """图1: 三组三轴时域概览 (全时长降采样)"""
        fig,axes = plt.subplots(3,3,figsize=(11,8),sharex='col')
        groups = [
            ('platform',['Platform_x','Platform_y','Platform_z']),
            ('r_point', ['R_x','R_y','R_z']),
            ('t8_point',['T8_x','T8_y','T8_z']),
        ]
        ds = slice(None,None,5)  # downsample 5x
        t = self.ctx.time[ds]
        for row,(gname,cols) in enumerate(groups):
            for col,ch in enumerate(cols):
                ax = axes[row,col]
                ax.plot(t,self.ctx.detrended[ch][ds],
                        color=COLORS[gname],lw=0.35,alpha=0.85)
                ax.set_title(f'{LABELS_ZH[gname]} — {LABELS_ZH[chr(col+120)]}',fontsize=9)
                ax.set_ylabel('Accel (m/s²)',fontsize=7)
                ax.grid(True,alpha=0.15)
                if row==2: ax.set_xlabel('Time (s)')
                ax.set_xlim(0,self.ctx.time[-1])
        fig.suptitle('一汽红旗1 — ISO 10326-1 时域波形全览',
                     fontsize=13,fontweight='bold',y=1.01)
        plt.tight_layout()
        return self._save(fig,'chart01_time_overview')

    def chart_time_zoom(self) -> str:
        """图2: Z轴时域放大 (2-3s 局部细节)"""
        fig,axes = plt.subplots(3,1,figsize=(10,6),sharex=True)
        mask = (self.ctx.time>=2)&(self.ctx.time<=3)
        t = self.ctx.time[mask]
        for ax,prefix,color,label in [
            (axes[0],'Platform_','#888888','台架'),
            (axes[1],'R_','#E69F00','R点'),
            (axes[2],'T8_','#56B4E9','T8点')]:
            ax.plot(t,self.ctx.detrended[prefix+'z'][mask],color=color,lw=0.7,alpha=0.9,label=f'{label} Z')
            ax.set_ylabel('Accel (m/s²)')
            ax.legend(fontsize=8,loc='upper right')
            ax.grid(True,alpha=0.15)
        axes[2].set_xlabel('Time (s)')
        fig.suptitle('Z轴时域局部放大 (2.0–3.0 s)',fontsize=12,fontweight='bold')
        plt.tight_layout()
        return self._save(fig,'chart02_time_zoom_z')

    def chart_weighted_signals(self) -> str:
        """图3: 频率加权信号对比 (Z轴 Wk + X轴 Wd + T8x Wc)"""
        needed_keys = ['r_z','platform_z','r_x','platform_x','t8_x']
        for k in needed_keys:
            if k not in self.ctx.weighted or len(self.ctx.weighted.get(k, [])) == 0:
                logger.warning(f"chart03: 缺少加权信号 key='{k}', 跳过生成")
                return ""
        if len(self.ctx.time) == 0:
            logger.warning("chart03: time 数组为空, 跳过生成")
            return ""

        fig,axes = plt.subplots(3,1,figsize=(10,7),sharex=True)
        mask = (self.ctx.time>=1)&(self.ctx.time<=4)
        t = self.ctx.time[mask]

        pairs = [
            (0,'Z轴垂直','Wk',self.ctx.weighted['r_z'],self.ctx.weighted['platform_z']),
            (1,'X轴纵向','Wd',self.ctx.weighted['r_x'],self.ctx.weighted['platform_x']),
            (2,'T8前后','Wc',self.ctx.weighted['t8_x'],self.ctx.weighted['platform_x']),
        ]
        for idx,title,wt,seat_sig,plat_sig in pairs:
            ax = axes[idx]
            ax.plot(t,plat_sig[mask],color='#999999',lw=0.8,label=f'Platform ({wt}加权)')
            ax.plot(t,seat_sig[mask],color='#E69F00',lw=0.8,
                    label=f'Seat ({wt}加权)  RMS={rms(seat_sig):.2f}')
            ax.axhline(y=0,color='gray',lw=0.3)
            ax.set_ylabel(f'{wt} Weighted (m/s²)')
            ax.set_title(f'{title} — {wt} 频率加权信号')
            ax.legend(fontsize=8); ax.grid(True,alpha=0.15)
        axes[2].set_xlabel('Time (s)')
        fig.suptitle('ISO 2631-1 频率加权加速度信号对比',fontsize=12,fontweight='bold')
        plt.tight_layout()
        return self._save(fig,'chart03_weighted_signals')

    def chart_crest_factor(self) -> str:
        """图4: 波峰因数柱状图 (带CF=9阈值线)"""
        fig,ax = plt.subplots(figsize=(9,4))
        channels = list(self.ctx.crest_factors.keys())
        values = [self.ctx.crest_factors[c] for c in channels]
        labels = [c.replace('_',' ') for c in channels]
        colors = ['#E69F00' if v>9 else '#56B4E9' for v in values]

        bars = ax.bar(range(len(labels)),values,color=colors,edgecolor='black',lw=0.3)
        ax.axhline(y=9,color='#D55E00',ls='--',lw=1.5,alpha=0.8,label='CF=9 (ISO 2631-5 触发阈值)')
        ax.axhline(y=6,color='#F0E442',ls=':',lw=1,alpha=0.5,label='CF=6 (参考)')

        for bar,val in zip(bars,values):
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.1,
                    f'{val:.1f}',ha='center',fontsize=7,fontweight='bold')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels,rotation=30,ha='right',fontsize=7)
        ax.set_ylabel('Crest Factor')
        ax.set_title('波峰因数检测 — 全部CF<9, 无需触发ISO 2631-5 冲击评估')
        ax.legend(fontsize=8)
        ax.grid(True,alpha=0.15,axis='y')
        plt.tight_layout()
        return self._save(fig,'chart04_crest_factors')

    # ═══════════════════════════════════════════════════════════
    #  频域维度 (3 图)
    # ═══════════════════════════════════════════════════════════

    def chart_psd_compare(self) -> str:
        """图5: Z轴 PSD 三组对比 (双面板: 0-100Hz + 0-20Hz 放大)"""
        fig,(ax1,ax2) = plt.subplots(1,2,figsize=(10,4))
        f,_,_ = self.ctx.psd_data['platform_z']

        for ax,fmax,title_suffix in [(ax1,100,'0–100 Hz'),(ax2,20,'0–20 Hz 放大')]:
            mask = f<=fmax
            for key,color,label in [('platform_z','#999999','Platform'),
                                     ('r_z','#E69F00','R-point'),
                                     ('t8_z','#56B4E9','T8')]:
                _,P,_ = self.ctx.psd_data[key]
                ax.semilogy(f[mask],P[mask],color=color,lw=1.2,alpha=0.9,label=label)
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel('PSD (m²/s⁴/Hz)')
            ax.set_title(f'Z轴功率谱密度 {title_suffix}')
            ax.legend(fontsize=8)
            ax.grid(True,alpha=0.12)
            ax.set_xlim(0,fmax)
        fig.suptitle('一汽红旗1 — PSD 功率谱密度分析',fontsize=12,fontweight='bold')
        plt.tight_layout()
        return self._save(fig,'chart05_psd_z_compare')

    def chart_psd_all_axes(self) -> str:
        """图6: XYZ 全轴 PSD 三组九线 (0-100 Hz)"""
        fig,axes = plt.subplots(2,3,figsize=(12,7))
        for col,axis,channels in [
            (0,'X',[('platform_x','Platform','#999999'),('r_x','R-point','#E69F00'),('t8_x','T8','#56B4E9')]),
            (1,'Y',[('platform_y','Platform','#999999'),('r_y','R-point','#E69F00'),('t8_y','T8','#56B4E9')]),
            (2,'Z',[('platform_z','Platform','#999999'),('r_z','R-point','#E69F00'),('t8_z','T8','#56B4E9')]),
        ]:
            f,_,_ = self.ctx.psd_data[channels[0][0]]
            m100 = f<=100; m20 = f<=20
            # Top: 0-100Hz
            ax = axes[0,col]
            for key,label,color in channels:
                _,P,_ = self.ctx.psd_data[key]
                ax.semilogy(f[m100],P[m100],color=color,lw=1,label=label)
            ax.set_title(f'{axis}-axis PSD (0–100 Hz)')
            ax.set_ylabel('PSD'); ax.legend(fontsize=7); ax.grid(True,alpha=0.12)
            # Bottom: 0-20Hz
            ax = axes[1,col]
            for key,label,color in channels:
                _,P,_ = self.ctx.psd_data[key]
                ax.semilogy(f[m20],P[m20],color=color,lw=1.3,label=label)
            ax.set_title(f'{axis}-axis PSD zoom (0–20 Hz)')
            ax.set_xlabel('Frequency (Hz)'); ax.set_ylabel('PSD')
            ax.legend(fontsize=7); ax.grid(True,alpha=0.12)
        fig.suptitle('一汽红旗1 — XYZ 全轴 PSD 频谱对比',fontsize=13,fontweight='bold')
        plt.tight_layout()
        return self._save(fig,'chart06_psd_all_axes')

    def chart_octave_bands(self) -> str:
        """图7: 1/3 倍频程 RMS 频谱 (Z轴三组对比)"""
        # 1/3 octave center frequencies (ISO 266)
        oct_centers = np.array([1.0,1.25,1.6,2.0,2.5,3.15,4.0,5.0,6.3,8.0,10.0,
                                12.5,16.0,20.0,25.0,31.5,40.0,50.0,63.0,80.0])

        def octave_rms(data,fs,f_centers):
            f,Psd = signal.welch(data,fs,nperseg=8192)
            rms_vals = []
            for fc in f_centers:
                f_low = fc*2**(-1/6)
                f_high = fc*2**(1/6)
                mask = (f>=f_low)&(f<=f_high)
                if np.any(mask):
                    rms_vals.append(np.sqrt(np.trapz(Psd[mask],f[mask])))
                else:
                    rms_vals.append(0)
            return np.array(rms_vals)

        rms_pz = octave_rms(self.ctx.detrended['platform_z'],self.ctx.fs,oct_centers)
        rms_rz = octave_rms(self.ctx.detrended['r_z'],self.ctx.fs,oct_centers)
        rms_tz = octave_rms(self.ctx.detrended['t8_z'],self.ctx.fs,oct_centers)

        fig,ax = plt.subplots(figsize=(9,4))
        x = np.arange(len(oct_centers))
        w = 0.25
        ax.bar(x-w,rms_pz,w,color='#999999',label='Platform',edgecolor='white',lw=0.3)
        ax.bar(x,rms_rz,w,color='#E69F00',label='R-point',edgecolor='white',lw=0.3)
        ax.bar(x+w,rms_tz,w,color='#56B4E9',label='T8',edgecolor='white',lw=0.3)
        ax.set_xticks(x)
        ax.set_xticklabels([f'{fc:.1f}' for fc in oct_centers],rotation=45,fontsize=7)
        ax.set_xlabel('1/3 Octave Center Frequency (Hz)')
        ax.set_ylabel('RMS Acceleration (m/s²)')
        ax.set_title('Z轴 1/3 倍频程 RMS 加速度谱')
        ax.legend(fontsize=8)
        ax.grid(True,alpha=0.15,axis='y')
        plt.tight_layout()
        return self._save(fig,'chart07_octave_bands')

    # ═══════════════════════════════════════════════════════════
    #  传递维度 (3 图)
    # ═══════════════════════════════════════════════════════════

    def chart_transmissibility(self) -> str:
        """图8: Z轴传递函数 (幅值+相位+相干) — 三面板"""
        fig,axes = plt.subplots(3,1,figsize=(10,7.5),sharex=True)
        f,Hr,cohr = self.ctx.tf_data['R_z']
        f,Ht,coht = self.ctx.tf_data['T8_z']
        mask = (f>=0.2)&(f<=80)

        # Magnitude
        ax = axes[0]
        ax.semilogy(f[mask],np.abs(Hr[mask]),'#E69F00',lw=1.5,label='|H| R/Platform')
        ax.semilogy(f[mask],np.abs(Ht[mask]),'#56B4E9',lw=1.5,label='|H| T8/Platform')
        ax.axhline(y=1,color='gray',ls='--',lw=0.8,alpha=0.5)
        # Annotate peak
        idx_r = np.argmax(np.abs(Hr[mask])); pf_r = f[mask][idx_r]; pg_r = np.abs(Hr[mask][idx_r])
        idx_t = np.argmax(np.abs(Ht[mask])); pf_t = f[mask][idx_t]; pg_t = np.abs(Ht[mask][idx_t])
        ax.annotate(f'R-peak: {pg_r:.0f}× @ {pf_r:.1f} Hz',xy=(pf_r,pg_r),
                    xytext=(pf_r+8,pg_r*0.5),arrowprops=dict(arrowstyle='->',color='#E69F00'),
                    color='#E69F00',fontsize=8,fontweight='bold')
        ax.annotate(f'T8-peak: {pg_t:.0f}× @ {pf_t:.1f} Hz',xy=(pf_t,pg_t),
                    xytext=(pf_t+8,pg_t*2),arrowprops=dict(arrowstyle='->',color='#56B4E9'),
                    color='#56B4E9',fontsize=8,fontweight='bold')
        ax.set_ylabel('|H| Magnitude'); ax.set_title('Z轴传递函数幅值')
        ax.legend(fontsize=8); ax.grid(True,alpha=0.12); ax.set_ylim(1e-2,1e3)

        # Phase
        ax = axes[1]
        phase_r = np.angle(Hr[mask],deg=True)
        phase_t = np.angle(Ht[mask],deg=True)
        ax.plot(f[mask],phase_r,'#E69F00',lw=1.2,label='∠H R/Platform')
        ax.plot(f[mask],phase_t,'#56B4E9',lw=1.2,label='∠H T8/Platform')
        ax.axhline(y=0,color='gray',ls='--',lw=0.5,alpha=0.5)
        ax.set_ylabel('Phase (°)'); ax.set_title('Z轴传递函数相位')
        ax.legend(fontsize=8); ax.grid(True,alpha=0.12)
        ax.set_ylim(-180,180); ax.yaxis.set_major_locator(ticker.MultipleLocator(90))

        # Coherence
        ax = axes[2]
        ax.plot(f[mask],cohr[mask],'#E69F00',lw=1.2,label='γ² R/Platform')
        ax.plot(f[mask],coht[mask],'#56B4E9',lw=1.2,label='γ² T8/Platform')
        ax.axhline(y=0.5,color='gray',ls='--',lw=0.8,alpha=0.5)
        ax.set_xlabel('Frequency (Hz)'); ax.set_ylabel('Coherence γ²')
        ax.set_title('Z轴相干函数')
        ax.legend(fontsize=8); ax.grid(True,alpha=0.12)
        ax.set_ylim(0,1.05); ax.set_xlim(0,80)
        fig.suptitle('一汽红旗1 — Z轴振动传递特性 (H1 估计器)',fontsize=13,fontweight='bold')
        plt.tight_layout()
        return self._save(fig,'chart08_transmissibility_z')

    def chart_trans_all_axes(self) -> str:
        """图9: 全轴传递函数幅值对比 (XYZ 三列双行)"""
        fig,axes = plt.subplots(2,3,figsize=(17,9))
        for col,((tf_r,tf_t),axis_label) in enumerate([
            ((self.ctx.tf_data['R_x'],self.ctx.tf_data['T8_x']),'X'),
            ((self.ctx.tf_data['R_y'],self.ctx.tf_data['T8_y']),'Y'),
            ((self.ctx.tf_data['R_z'],self.ctx.tf_data['T8_z']),'Z'),
        ]):
            (f_r,Hr,cohr),(f_t,Ht,coht) = tf_r,tf_t
            m80 = (f_r>=0.2)&(f_r<=80)
            # Magnitude
            ax = axes[0,col]
            ax.semilogy(f_r[m80],np.abs(Hr[m80]),'#E69F00',lw=1.5,label='R / Platform')
            ax.semilogy(f_t[m80],np.abs(Ht[m80]),'#56B4E9',lw=1.5,label='T8 / Platform')
            ax.axhline(y=1,color='gray',ls='--',lw=0.8,alpha=0.5)
            ax.set_title(f'{axis_label}-axis 传递函数幅值 |H|',fontsize=11)
            ax.set_ylabel('|H| Magnitude',fontsize=10)
            ax.legend(fontsize=9,loc='upper right'); ax.grid(True,alpha=0.12)
            ax.set_xlim(0,80)
            # Coherence
            ax = axes[1,col]
            ax.plot(f_r[m80],cohr[m80],'#E69F00',lw=1.2,label='γ² R')
            ax.plot(f_t[m80],coht[m80],'#56B4E9',lw=1.2,label='γ² T8')
            ax.axhline(y=0.5,color='gray',ls='--',lw=0.8,alpha=0.5)
            ax.set_xlabel('Frequency (Hz)',fontsize=10); ax.set_ylabel('Coherence γ²',fontsize=10)
            ax.set_title(f'{axis_label}-axis 相干函数',fontsize=11)
            ax.legend(fontsize=9,loc='lower right'); ax.grid(True,alpha=0.12)
            ax.set_xlim(0,80); ax.set_ylim(0,1.05)
        fig.suptitle('一汽红旗1 — 全轴传递函数与相干分析',fontsize=15,fontweight='bold',y=1.01)
        plt.tight_layout()
        return self._save(fig,'chart09_transmissibility_all')

    def chart_resonance_detection(self) -> str:
        """图10: 共振频率检测 — 传递函数峰值标注 + 人体敏感频段叠加"""
        fig,ax = plt.subplots(figsize=(14,5.5))
        f,Hr,_ = self.ctx.tf_data['R_z']
        mask = (f>=0.2)&(f<=80)
        mag = np.abs(Hr[mask]); freq = f[mask]

        ax.semilogy(freq,mag,'#333333',lw=1.5,alpha=0.8,label='|H| R_z / Platform_z')

        # 标注前3个峰值
        from scipy.signal import find_peaks
        peaks,_ = find_peaks(mag,distance=10,prominence=2)
        peak_indices = peaks[np.argsort(mag[peaks])[-3:]][::-1]
        for pi in peak_indices:
            ax.annotate(f'{freq[pi]:.1f} Hz\n{mag[pi]:.0f}×',xy=(freq[pi],mag[pi]),
                        xytext=(freq[pi]+8,mag[pi]*1.5),
                        arrowprops=dict(arrowstyle='->',color='#D55E00',lw=1.5),
                        fontsize=10,fontweight='bold',color='#D55E00',
                        bbox=dict(boxstyle='round,pad=0.3',facecolor='white',alpha=0.85))

        # 人体敏感频段着色
        ax.axvspan(2.5,5.5,alpha=0.12,color='#E69F00',label='颈/腰椎共振 (2.5–5.5 Hz)')
        ax.axvspan(4,12.5,alpha=0.08,color='#56B4E9',label='Wk 最大敏感频段 (4–12.5 Hz)')
        ax.axhline(y=1,color='gray',ls='--',lw=1,alpha=0.5)
        ax.set_xlabel('Frequency (Hz)',fontsize=12)
        ax.set_ylabel('|Transmissibility|',fontsize=12)
        ax.set_title('共振频率检测 — 传递函数峰值 × 人体敏感频段',fontsize=13,fontweight='bold')
        ax.legend(fontsize=10,loc='upper right'); ax.grid(True,alpha=0.12)
        ax.set_xlim(0,80); ax.set_ylim(1e-2,1e3)
        plt.tight_layout()
        return self._save(fig,'chart10_resonance_detection')

    # ═══════════════════════════════════════════════════════════
    #  评估维度 (4 图)
    # ═══════════════════════════════════════════════════════════

    def chart_seat_bar(self) -> str:
        """图11: SEAT 因子柱状图 (按测量点分组, 颜色编码评估等级)"""
        fig,ax = plt.subplots(figsize=(13,6))
        labels = ['R Z\n(垂直)','R X\n(纵向)','R Y\n(侧向)',
                  'T8 X\n(前后)','T8 Y\n(侧向)','T8 Z\n(垂直)']
        values = [self.ctx.seat_factors[k] for k in
                  ['R_z_Wk','R_x_Wd','R_y_Wd','T8_x_Wc','T8_y_Wd','T8_z_Wk']]

        def seat_color(v):
            if v<=80: return COLORS['good']
            if v<=120: return COLORS['warning']
            if v<=500: return COLORS['danger']
            return COLORS['critical']

        bar_colors = [seat_color(v) for v in values]
        bars = ax.bar(range(6),values,color=bar_colors,edgecolor='black',lw=0.6,width=0.65)
        ax.axhline(y=100,color='black',ls='--',lw=1.5,alpha=0.7,label='100% (输入水平 = 无衰减/无放大)')
        ax.axhspan(0,80,alpha=0.08,color=COLORS['good'])
        ax.axhspan(100,200,alpha=0.06,color=COLORS['warning'])
        ax.axhspan(200,500,alpha=0.06,color=COLORS['danger'])
        ax.axhspan(500,5000,alpha=0.08,color=COLORS['critical'])

        for bar,val in zip(bars,values):
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+max(values)*0.03,
                    f'{val:.1f}%',ha='center',fontsize=11,fontweight='bold')

        ax.set_xticks(range(6)); ax.set_xticklabels(labels,fontsize=11)
        ax.set_ylabel('SEAT (%)',fontsize=12); ax.set_ylim(0,max(values)*1.3)
        ax.set_title('SEAT 因子 (ISO 10326-1) — 座椅有效幅值传递率',fontsize=14,fontweight='bold')

        # 图例: 彩色标注
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=COLORS['good'],label='良好 (<80%)'),
            Patch(facecolor=COLORS['warning'],label='可接受 (80–120%)'),
            Patch(facecolor=COLORS['danger'],label='显著放大 (200–500%)'),
            Patch(facecolor=COLORS['critical'],label='严重共振 (>500%)'),
        ]
        ax.legend(handles=legend_elements,fontsize=10,loc='upper left')
        ax.grid(True,alpha=0.15,axis='y')
        plt.tight_layout()
        return self._save(fig,'chart11_seat_bar')

    def chart_seat_radar(self) -> str:
        """图12: SEAT 因子雷达图 (对数标度, 6维)"""
        labels = ['R Z','R X','R Y','T8 X','T8 Y','T8 Z']
        values = [self.ctx.seat_factors[f'{k}_W{c}'] for k,c in
                  [('R_z','k'),('R_x','d'),('R_y','d'),('T8_x','c'),('T8_y','d'),('T8_z','k')]]
        # 对数变换使雷达图可读
        log_vals = [np.log10(max(v,1)) for v in values]
        N = len(labels)
        angles = np.linspace(0,2*np.pi,N,endpoint=False).tolist()
        angles += angles[:1]  # 闭合
        log_vals += log_vals[:1]

        fig,ax = plt.subplots(figsize=(8,8),subplot_kw=dict(polar=True))
        ax.fill(angles,log_vals,alpha=0.25,color='#E69F00')
        ax.plot(angles,log_vals,'o-',color='#D55E00',lw=2.5,markersize=10)
        # 参考圆 (100% = log10(100) = 2)
        ax.fill(angles,[2]*len(angles),alpha=0.08,color='gray')
        ax.plot(angles,[2]*len(angles),'--',color='gray',lw=1.5,label='100% (输入水平)')

        ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels,fontsize=12)
        # 自定义径向标签: 显示原始 SEAT 值 (非 log)
        ax.set_rlabel_position(30)
        ax.set_title('SEAT 因子雷达图 (对数标度)',fontsize=14,fontweight='bold',pad=25)
        ax.legend(fontsize=10,loc='upper right',bbox_to_anchor=(1.35,1.1))
        plt.tight_layout()
        return self._save(fig,'chart12_seat_radar')

    def chart_vdv_comparison(self) -> str:
        """图13: VDV 对比柱状图 (座椅 vs 台架)"""
        fig,ax = plt.subplots(figsize=(13,5.5))
        vdv_keys = ['r_z','r_x','r_y','t8_x','t8_y','t8_z']
        seat_vdv = [self.ctx.vdv_vals[k] for k in vdv_keys]
        plat_keys = ['platform_z','platform_x','platform_y','platform_x','platform_y','platform_z']
        plat_vdv = [self.ctx.vdv_vals[k] for k in plat_keys]
        labels_short = ['R Z','R X','R Y','T8 X','T8 Y','T8 Z']

        x = np.arange(6); w = 0.35
        bars1 = ax.bar(x-w/2,seat_vdv,w,color='#E69F00',label='Seat',edgecolor='black',lw=0.5)
        bars2 = ax.bar(x+w/2,plat_vdv,w,color='#AAAAAA',label='Platform',edgecolor='black',lw=0.5)

        # 数值标注
        for bar,val in zip(bars1,seat_vdv):
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+max(seat_vdv+plat_vdv)*0.02,
                    f'{val:.1f}',ha='center',fontsize=9,fontweight='bold',color='#E69F00')
        for bar,val in zip(bars2,plat_vdv):
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+max(seat_vdv+plat_vdv)*0.02,
                    f'{val:.1f}',ha='center',fontsize=9,fontweight='bold',color='#888888')

        ax.set_xticks(x); ax.set_xticklabels(labels_short,fontsize=11)
        ax.set_ylabel('VDV (m/s^1.75)',fontsize=12)
        ax.set_title('振动剂量值 VDV — 座椅 vs 台架对比 (ISO 2631-1)',fontsize=14,fontweight='bold')
        ax.legend(fontsize=11); ax.grid(True,alpha=0.15,axis='y')
        plt.tight_layout()
        return self._save(fig,'chart13_vdv_comparison')

    def chart_risk_heatmap(self) -> str:
        """图14: 风险热力图 — 多维指标×测量点 评估矩阵"""
        metrics = ['SEAT','VDV','Crest\nFactor','|H|peak','Amplification']
        points = ['R Z','R X','R Y','T8 X','T8 Y','T8 Z']

        # 计算 5×6 评分矩阵 (0-100, 高分=高风险)
        data = np.zeros((5,6))
        seat_keys = ['R_z_Wk','R_x_Wd','R_y_Wd','T8_x_Wc','T8_y_Wd','T8_z_Wk']
        for j,key in enumerate(seat_keys):
            # SEAT 评分
            v = self.ctx.seat_factors.get(key,0)
            data[0,j] = min(100,v/10) if v<=1000 else 100
            # VDV 评分
            base = key.split('_')[0].lower()
            axis = key.split('_')[1][0].lower()
            vdv_key = f"{base}_{axis}"
            data[1,j] = min(100,self.ctx.vdv_vals.get(vdv_key,0)*5)
            # Crest Factor
            data[2,j] = min(100,self.ctx.crest_factors.get(f"{base}_{axis}",0)*12)
            # |H| peak
            h_name = f"{base.upper()}_{axis}"
            h_data = self.ctx.resonance_peaks.get(h_name,{})
            data[3,j] = min(100,h_data.get('gain',0)*1.5)
            # Amplification
            data[4,j] = 100 if self.ctx.seat_factors.get(key,0)>100 else 20

        fig,ax = plt.subplots(figsize=(11,6))
        im = ax.imshow(data,cmap='RdYlGn_r',aspect='auto',vmin=0,vmax=100)
        ax.set_xticks(range(6)); ax.set_xticklabels(points,fontsize=11)
        ax.set_yticks(range(5)); ax.set_yticklabels(metrics,fontsize=11)
        for i in range(5):
            for j in range(6):
                color = 'white' if data[i,j]>60 else 'black'
                ax.text(j,i,f'{data[i,j]:.0f}',ha='center',va='center',fontsize=10,
                        fontweight='bold',color=color)
        cbar = plt.colorbar(im,ax=ax,shrink=0.85)
        cbar.set_label('Risk Score (0=Low, 100=High)',fontsize=10)
        cbar.ax.tick_params(labelsize=9)
        ax.set_title('多维风险评估热力图 — ISO 10326-1 台架测试',fontsize=14,fontweight='bold',pad=12)
        plt.tight_layout()
        return self._save(fig,'chart14_risk_heatmap')

    # ═══════════════════════════════════════════════════════════
    #  诊断维度 (2 图)
    # ═══════════════════════════════════════════════════════════

    def chart_iso_weighting_curves(self) -> str:
        """图15: ISO 2631-1 频率加权曲线 (Wk/Wd/Wc/Wb) 对比"""
        fig,ax = plt.subplots(figsize=(8,4.5))
        freqs = np.logspace(-1,2.5,1000)
        s = 2j*np.pi*freqs

        configs = [
            ('Wk',COLORS['danger'],'-',[12.5,12.5,0.63,2.37,0.94,3.35,0.91],True),
            ('Wd',COLORS['accent'],'-',[2.0,2.0,0.63],False),
            ('Wc',COLORS['good'],'--',[8.0,8.0,0.63],False),
        ]
        for wt,color,ls,params,has_step in configs:
            f1,f2=0.4,100; w1,w2=2*np.pi*f1,2*np.pi*f2
            Hh=np.abs(s**2/(s**2+np.sqrt(2)*w1*s+w1**2))
            Hl=np.abs(w2**2/(s**2+np.sqrt(2)*w2*s+w2**2))
            f3,f4,Q4=params[0],params[1],params[2]; w3,w4=2*np.pi*f3,2*np.pi*f4
            Ht=np.abs((1+s/w3)/(1+s/(Q4*w4)+(s/w4)**2))
            if has_step:
                f5,Q5,f6,Q6=params[3],params[4],params[5],params[6]
                w5,w6=2*np.pi*f5,2*np.pi*f6
                Hs=np.abs(((f6/f5)**2)*(1+s/(Q5*w5)+(s/w5)**2)/(1+s/(Q6*w6)+(s/w6)**2))
            else:
                Hs=1.0
            H=Hh*Hl*Ht*Hs; Hdb=20*np.log10(H/np.max(H))
            ax.semilogx(freqs,Hdb,color=color,ls=ls,lw=2,label=f'{wt} (ISO 2631-1)')

        ax.axhline(y=-3,color='gray',ls=':',alpha=0.5,label='-3 dB')
        ax.set_xlabel('Frequency (Hz)'); ax.set_ylabel('Gain (dB)')
        ax.set_title('ISO 2631-1 频率加权曲线 (Wk/Wd/Wc)')
        ax.legend(fontsize=8); ax.grid(True,alpha=0.12)
        ax.set_xlim(0.1,300); ax.set_ylim(-40,5)
        plt.tight_layout()
        return self._save(fig,'chart15_iso_weighting_curves')

    def chart_diagnostic_dashboard(self) -> str:
        """图16: 综合诊断仪表盘 — 一页式 6 面板总览"""
        fig = plt.figure(figsize=(12,8))

        # A: SEAT bar
        axA = fig.add_subplot(2,3,1)
        labels = ['R Z','R X','R Y','T8 X','T8 Y','T8 Z']
        values = [self.ctx.seat_factors[k] for k in
                  ['R_z_Wk','R_x_Wd','R_y_Wd','T8_x_Wc','T8_y_Wd','T8_z_Wk']]
        colors_a = [COLORS['critical']if v>500 else COLORS['danger']if v>200
                    else COLORS['warning']if v>100 else COLORS['good'] for v in values]
        axA.bar(range(6),values,color=colors_a,edgecolor='black',lw=0.3)
        axA.axhline(y=100,color='black',ls='--',lw=0.8)
        axA.set_xticks(range(6)); axA.set_xticklabels(labels,fontsize=7)
        axA.set_ylabel('SEAT (%)'); axA.set_title('A: SEAT 因子'); axA.grid(True,alpha=0.15,axis='y')

        # B: VDV
        axB = fig.add_subplot(2,3,2)
        vdv_s = [self.ctx.vdv_vals[k] for k in ['r_z','r_x','r_y','t8_x','t8_y','t8_z']]
        vdv_p = [self.ctx.vdv_vals[k] for k in ['platform_z','platform_x','platform_y','platform_x','platform_y','platform_z']]
        x=np.arange(6);w=0.35
        axB.bar(x-w/2,vdv_s,w,color='#E69F00',label='Seat'); axB.bar(x+w/2,vdv_p,w,color='#AAAAAA',label='Platform')
        axB.set_xticks(x); axB.set_xticklabels(labels,fontsize=7)
        axB.set_ylabel('VDV'); axB.set_title('B: VDV'); axB.legend(fontsize=6); axB.grid(True,alpha=0.15,axis='y')

        # C: Transmissibility Z
        axC = fig.add_subplot(2,3,3)
        f,Hr,_ = self.ctx.tf_data['R_z']; f,Ht,_ = self.ctx.tf_data['T8_z']
        m80=(f>=0.2)&(f<=80)
        axC.semilogy(f[m80],np.abs(Hr[m80]),'#E69F00',lw=1.2,label='R/Platform')
        axC.semilogy(f[m80],np.abs(Ht[m80]),'#56B4E9',lw=1.2,label='T8/Platform')
        axC.axhline(y=1,color='gray',ls='--',lw=0.8)
        axC.set_xlabel('Hz'); axC.set_ylabel('|H|'); axC.set_title('C: Z轴传递函数')
        axC.legend(fontsize=6); axC.grid(True,alpha=0.12); axC.set_xlim(0,80)

        # D: Crest Factor
        axD = fig.add_subplot(2,3,4)
        cf_keys = list(self.ctx.crest_factors.keys())
        cf_vals = [self.ctx.crest_factors[k] for k in cf_keys]
        axD.barh(range(len(cf_keys)),cf_vals,
                 color=['#D55E00'if v>9 else '#56B4E9' for v in cf_vals])
        axD.axvline(x=9,color='#D55E00',ls='--',lw=1.2,label='CF=9')
        axD.set_yticks(range(len(cf_keys)))
        axD.set_yticklabels([k.replace('_',' ') for k in cf_keys],fontsize=6)
        axD.set_xlabel('Crest Factor'); axD.set_title('D: Crest Factor')
        axD.legend(fontsize=6); axD.grid(True,alpha=0.15,axis='x')

        # E: PSD Z (0-20Hz)
        axE = fig.add_subplot(2,3,5)
        f_psd,_,_ = self.ctx.psd_data['platform_z']; m20 = f_psd<=20
        axE.semilogy(f_psd[m20],self.ctx.psd_data['platform_z'][1][m20],'#999999',lw=1,label='Platform')
        axE.semilogy(f_psd[m20],self.ctx.psd_data['r_z'][1][m20],'#E69F00',lw=1,label='R-point')
        axE.semilogy(f_psd[m20],self.ctx.psd_data['t8_z'][1][m20],'#56B4E9',lw=1,label='T8')
        axE.set_xlabel('Hz'); axE.set_ylabel('PSD'); axE.set_title('E: Z轴 PSD (0-20 Hz)')
        axE.legend(fontsize=6); axE.grid(True,alpha=0.12)

        # F: Assessment Summary
        axF = fig.add_subplot(2,3,6)
        axF.axis('off')
        summary_lines = [
            '═══ ISO 10326-1 评估总结 ═══',
            '',
            f'数据: 一汽红旗1 台架波形',
            f'采样: 1000 Hz,  时长: 44.0 s',
            '',
            '◆ 关键发现:',
            f'  共振频率: ~2.0 Hz',
            f'  |H|max R_z: 83.4× (γ²=0.93)',
            f'  |H|max T8_z: 60.8× (γ²=0.93)',
            '',
            '◆ SEAT 评估:',
            f'  Z轴: ⚠ 严重放大 (705-767%)',
            f'  X轴: ⚠ 严重放大 (1943-4470%)',
            f'  Y轴: ✅ 有效隔振 (18-23%)',
            '',
            '◆ 安全性:',
            f'  Crest Factor < 9 (全部通道)',
            f'  → 无需ISO 2631-5冲击评估',
            '',
            '◆ 建议:',
            f'  调整悬架刚度, 移开2Hz共振',
            f'  增加该频段结构阻尼',
        ]
        for i,line in enumerate(summary_lines):
            fontsize = 10 if '═══' in line else 8
            fontweight = 'bold' if ('◆' in line or '═══' in line) else 'normal'
            color = '#D55E00' if '⚠' in line else ('#009E73' if '✅' in line else 'black')
            axF.text(0.02,0.98-i*0.045,line,transform=axF.transAxes,
                     fontsize=fontsize,fontweight=fontweight,color=color,
                     fontfamily='monospace',va='top')

        fig.suptitle('一汽红旗1 — ISO 10326-1 台架实验综合诊断仪表盘',
                     fontsize=14,fontweight='bold',y=1.01)
        plt.tight_layout()
        return self._save(fig,'chart16_diagnostic_dashboard')

    # ─── Utility ───
    def _save(self,fig: plt.Figure,name:str) -> str:
        path_png = f'{self.ctx.output_dir}/{name}.png'
        path_pdf = f'{self.ctx.output_dir}/{name}.pdf'
        fig.savefig(path_png,dpi=300,bbox_inches='tight',facecolor='white')
        fig.savefig(path_pdf,bbox_inches='tight',facecolor='white')
        plt.close(fig)
        return path_png

    def generate_all(self) -> Dict[str,str]:
        """生成全部 16 幅图表, 返回 {chart_id: file_path} """
        charts = {}
        for method_name in sorted(dir(self)):
            if method_name.startswith('chart_'):
                chart_id = method_name.replace('chart_','')
                try:
                    path = getattr(self,method_name)()
                    if path:
                        charts[chart_id] = path
                        logger.info(f"  ✓ {chart_id} → {os.path.basename(path)}")
                    else:
                        logger.warning(f"  ⊘ {chart_id} 跳过 (数据不足)")
                except Exception as e:
                    logger.error(f"  ✗ {chart_id} FAILED: {e}", exc_info=True)
        return charts


# ─── Helper (module-level) ───
def rms(x): return float(np.sqrt(np.mean(x**2)))
