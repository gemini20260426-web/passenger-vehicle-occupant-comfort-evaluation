#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可视化管理器 - 专家评测报告图表生成

图表类型:
  1. 全时程概览图 (Overview)
  2. 事件对比图 (Event Comparison)
  3. 频谱分析图 (Spectrum)
  4. 时频分析图 (STFT)
  5. 统计仪表盘 (Statistics Dashboard)
  6. 频段雷达图 (Band Radar)
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class VisualizationManager:
    """可视化管理器"""

    def __init__(self):
        self.colors = {
            'exp': '#1f77b4',      # 实验组 - 蓝色
            'ctrl': '#ff7f0e',     # 对照组 - 橙色
            'exp_light': '#aec7e8',
            'ctrl_light': '#ffbb78',
            'green': '#2ca02c',
            'red': '#d62728',
            'purple': '#9467bd',
        }

    def plot_overview(self, sw: np.ndarray, exp_head: np.ndarray, ctrl_head: np.ndarray,
                      events: list, out_path: str):
        """全时程概览图"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
        t = sw[:, 0]

        ax1.plot(t, sw[:, 1], color='#1f77b4', linewidth=1.5)
        ax1.set_ylabel('Speed (km/h)', fontsize=12)
        ax1.grid(alpha=0.3)
        ax1.set_title('Vehicle Speed', fontsize=14)

        ax2.plot(t, sw[:, 2], color='#9467bd', linewidth=1.5)
        ax2.set_ylabel('Wheel Angle (deg)', fontsize=12)
        ax2.grid(alpha=0.3)
        ax2.set_title('Steering Wheel Angle', fontsize=14)

        ax3.plot(t, exp_head[:, 2], color=self.colors['exp'], linewidth=0.8, alpha=0.8, label='Active')
        ax3.plot(t, ctrl_head[:, 2], color=self.colors['ctrl'], linewidth=0.8, alpha=0.8, label='Passive')
        ax3.set_ylabel('Ay (m/s²)', fontsize=12)
        ax3.set_xlabel('Time (s)', fontsize=12)
        ax3.grid(alpha=0.3)
        ax3.legend()
        ax3.set_title('Head Lateral Acceleration', fontsize=14)

        for ev in events:
            ax1.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color=self.colors['red'])
            ax2.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color=self.colors['red'])
            ax3.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color=self.colors['red'])

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_event_comparison(self, df_events: pd.DataFrame, out_path: str):
        """事件对比图"""
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        ax1, ax2, ax3 = axes

        for ax, axis in zip([ax1, ax2, ax3], ['Ax', 'Ay', 'Az']):
            e_vals = df_events[f'e_{axis}_RMS'].dropna()
            c_vals = df_events[f'c_{axis}_RMS'].dropna()
            
            x = np.arange(len(e_vals))
            width = 0.35
            
            ax.bar(x - width/2, e_vals, width, label='Active', color=self.colors['exp'])
            ax.bar(x + width/2, c_vals, width, label='Passive', color=self.colors['ctrl'])
            
            ax.set_title(f'{axis} RMS Comparison per Event', fontsize=12)
            ax.set_xlabel('Event Index', fontsize=10)
            ax.set_ylabel('RMS (m/s²)', fontsize=10)
            ax.legend()
            ax.grid(alpha=0.3)
            ax.tick_params(axis='x', labelsize=8)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_spectrum(self, spec: Dict[str, Any], out_path: str):
        """频谱分析图"""
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = spec.get(axis, {})
            if not s:
                continue
            
            f = s['freq']
            exp_psd = s['exp_psd']
            ctrl_psd = s['ctrl_psd']
            ratio = s['ratio']
            
            ax.semilogy(f, exp_psd, color=self.colors['exp'], label='Active', linewidth=1.2)
            ax.semilogy(f, ctrl_psd, color=self.colors['ctrl'], label='Passive', linewidth=1.2)
            ax.set_xlim(0.1, 80)
            ax.set_xlabel('Frequency (Hz)', fontsize=10)
            ax.set_ylabel('PSD (m²/s⁴/Hz)', fontsize=10)
            ax.set_title(f'{axis} Power Spectral Density', fontsize=12)
            ax.legend()
            ax.grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_spectrum_ratio(self, spec: Dict[str, Any], out_path: str):
        """频谱衰减比图"""
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = spec.get(axis, {})
            if not s:
                continue
            
            f = s['freq']
            ratio = s['ratio']
            
            ax.plot(f, ratio, color=self.colors['purple'], linewidth=1.2)
            ax.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
            ax.set_xlim(0.1, 80)
            ax.set_ylim(0, 2)
            ax.set_xlabel('Frequency (Hz)', fontsize=10)
            ax.set_ylabel('Active/Passive Ratio', fontsize=10)
            ax.set_title(f'{axis} Attenuation Ratio', fontsize=12)
            ax.grid(alpha=0.3)
            
            for band_name, (flo, fhi) in {'1-5Hz': (1, 5), '5-20Hz': (5, 20)}.items():
                ax.axvspan(flo, fhi, alpha=0.1, color=self.colors['green'])
                ax.text((flo + fhi)/2, 1.8, band_name, ha='center', fontsize=8)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_stft(self, stft: Dict[str, Any], out_path: str):
        """时频分析图"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
        
        s = stft.get('Ay', {})
        if s:
            f = s['f']
            t = s['t']
            exp_spec = s['exp_spec']
            ctrl_spec = s['ctrl_spec']
            
            im1 = ax1.pcolormesh(t, f, 10 * np.log10(exp_spec + 1e-10), 
                                vmin=-80, vmax=-20, cmap='viridis')
            ax1.set_ylim(0, 50)
            ax1.set_ylabel('Frequency (Hz)', fontsize=12)
            ax1.set_title('Active Seat - STFT', fontsize=14)
            
            im2 = ax2.pcolormesh(t, f, 10 * np.log10(ctrl_spec + 1e-10),
                                vmin=-80, vmax=-20, cmap='viridis')
            ax2.set_ylim(0, 50)
            ax2.set_xlabel('Time (s)', fontsize=12)
            ax2.set_ylabel('Frequency (Hz)', fontsize=12)
            ax2.set_title('Passive Seat - STFT', fontsize=14)
            
            fig.colorbar(im1, ax=[ax1, ax2], label='Power (dB)')

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_statistics(self, stats: Dict[str, Any], out_path: str):
        """统计仪表盘"""
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = stats.get(axis, {})
            if not s:
                continue
            
            metrics = ['e_rms', 'c_rms', 'attenuation_pct']
            values = [s.get(m, 0) for m in metrics]
            labels = ['Active RMS', 'Passive RMS', 'Attenuation (%)']
            
            bars = ax.bar(labels, values, color=[self.colors['exp'], self.colors['ctrl'], self.colors['green']])
            ax.set_title(f'{axis} Statistics', fontsize=12)
            ax.grid(alpha=0.3)
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_band_radar(self, spec: Dict[str, Any], out_path: str):
        """频段雷达图"""
        bands = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
        angles = np.linspace(0, 2 * np.pi, len(bands), endpoint=False)
        
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))
        
        for axis, color in zip(['Ax', 'Ay', 'Az'], [self.colors['exp'], self.colors['ctrl'], self.colors['purple']]):
            values = []
            for band in bands:
                val = spec.get(axis, {}).get('bands_atten', {}).get(band, 0)
                values.append(val)
            values += values[:1]
            ax.plot(np.append(angles, angles[0]), values, 'o-', linewidth=2, markersize=6,
                    label=axis, color=color)
        
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles)
        ax.set_xticklabels(bands)
        ax.set_ylim(0, 100)
        ax.set_title('Band Attenuation (%)', fontsize=14)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax.grid(True)
        
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_window_attenuation(self, df_windows: pd.DataFrame, out_path: str):
        """滑动窗口衰减趋势图"""
        fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            col = f'atten_{axis}_pct'
            if col in df_windows.columns:
                ax.plot(df_windows['t_center'], df_windows[col], 
                        color=self.colors['green'], linewidth=1, alpha=0.8)
                ax.axhline(0, color='gray', linestyle='--', alpha=0.5)
                ax.set_ylabel(f'{axis} Attenuation (%)', fontsize=12)
                ax.set_title(f'{axis} Window Attenuation', fontsize=12)
                ax.grid(alpha=0.3)
        
        axes[-1].set_xlabel('Time (s)', fontsize=12)
        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def generate_all_plots(self, evaluator, out_dir: str):
        """生成所有图表"""
        os.makedirs(out_dir, exist_ok=True)
        
        sw = evaluator.sw
        exp_keys = list(evaluator.exp.keys())
        ctrl_keys = list(evaluator.ctrl.keys())
        
        if sw is not None and len(exp_keys) > 0 and len(ctrl_keys) > 0:
            exp_head = evaluator.get_aligned(exp_keys[0])
            ctrl_head = evaluator.get_aligned(ctrl_keys[0])
            
            if exp_head is not None and ctrl_head is not None:
                self.plot_overview(sw, exp_head, ctrl_head, evaluator.events,
                                  os.path.join(out_dir, 'fig1_overview.png'))
        
        if 'events' in evaluator.results and len(evaluator.results['events']) > 0:
            self.plot_event_comparison(evaluator.results['events'],
                                      os.path.join(out_dir, 'fig2_events.png'))
        
        if 'spectrum' in evaluator.results:
            self.plot_spectrum(evaluator.results['spectrum'],
                               os.path.join(out_dir, 'fig3_spectrum.png'))
            self.plot_spectrum_ratio(evaluator.results['spectrum'],
                                     os.path.join(out_dir, 'fig3b_ratio.png'))
            self.plot_band_radar(evaluator.results['spectrum'],
                                  os.path.join(out_dir, 'fig6_band_radar.png'))
        
        if 'stft' in evaluator.results:
            self.plot_stft(evaluator.results['stft'],
                           os.path.join(out_dir, 'fig4_stft.png'))
        
        if 'statistics' in evaluator.results:
            self.plot_statistics(evaluator.results['statistics'],
                                 os.path.join(out_dir, 'fig5_statistics.png'))
        
        if 'windows' in evaluator.results and len(evaluator.results['windows']) > 0:
            self.plot_window_attenuation(evaluator.results['windows'],
                                          os.path.join(out_dir, 'fig7_window_atten.png'))
        
        logger.info(f"  共生成 {len(os.listdir(out_dir))} 个图表")
        return out_dir