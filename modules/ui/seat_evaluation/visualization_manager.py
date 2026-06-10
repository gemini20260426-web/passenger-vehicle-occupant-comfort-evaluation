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


class ChartStyle:
    """全量统计分析图表统一样式 — 与台架实验 shaker_charts 对齐"""

    # ── DPI ──
    DESIGN_DPI = 200        # 导出用高DPI
    SCREEN_DPI = None       # 屏幕DPI(首次访问时自动检测)

    # ── 配色 (Okabe-Ito 色盲友好) ──
    C_BG = '#FAFAFA'
    C_EXP = '#56B4E9'       # 实验组 - 天蓝
    C_CTRL = '#E69F00'      # 对照组 - 橙
    C_DIFF = '#009E73'      # 改善量 - 绿
    C_GRID = '#CCCCCC'
    C_NEUTRAL = '#999999'
    C_GRID_ALPHA = 0.15

    # ── 字体 (绝对点数, 基准为7.5英寸卡片) ──
    FONT_SIZE = 9
    TITLE_SIZE = 10          # 子图标题
    LABEL_SIZE = 9           # 坐标轴标签
    TICK_SIZE = 8            # 刻度标签
    LEGEND_SIZE = 7.5        # 图例
    ANNOT_SIZE = 7           # 标注
    SUPTITLE_SIZE = 12       # 总标题

    # ── 线宽 ──
    LW_MAIN = 0.7            # 主数据线
    LW_GRID = 0.4            # 网格线
    LW_REF = 0.8             # 参考线

    # ── 标记大小 ──
    MS = 5

    # ── 卡片基准 ──
    CARD_W = 7.5             # 基准卡片宽度(英寸)
    ROW_H = 2.5              # 每行高度

    @classmethod
    def screen_dpi(cls):
        if cls.SCREEN_DPI is None:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            cls.SCREEN_DPI = int(screen.logicalDotsPerInch()) if screen else 96
        return cls.SCREEN_DPI

    @classmethod
    def apply_rcparams(cls):
        """应用全局 matplotlib 样式参数"""
        plt.rcParams.update({
            'figure.dpi': cls.DESIGN_DPI,
            'savefig.dpi': cls.DESIGN_DPI,
            'font.size': cls.FONT_SIZE,
            'axes.titlesize': cls.TITLE_SIZE,
            'axes.labelsize': cls.LABEL_SIZE,
            'xtick.labelsize': cls.TICK_SIZE,
            'ytick.labelsize': cls.TICK_SIZE,
            'legend.fontsize': cls.LEGEND_SIZE,
            'figure.facecolor': cls.C_BG,
            'axes.facecolor': cls.C_BG,
            'axes.edgecolor': cls.C_NEUTRAL,
            'axes.grid': True,
            'grid.color': cls.C_GRID,
            'grid.linewidth': cls.LW_GRID,
            'grid.alpha': cls.C_GRID_ALPHA,
            'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
            'axes.unicode_minus': False,
        })


def card_adapted_figure(card_widget, nrows=1, ncols=1, height_mul=None,
                         approach='auto', radar=False):
    """
    根据 QWidget 的实际像素宽度动态创建 matplotlib Figure。
    核心原则: 创建时确定最终尺寸, 不做 post-creation 缩放。

    approach:
      'auto'    — 检测屏幕DPI, 自适应
      'screen'  — 强制使用屏幕DPI(嵌入用)
      'export'  — 强制使用设计DPI(导出用)

    返回: (fig, axes, scale) where scale 是字体/线宽的缩放因子
    """
    if height_mul is None:
        height_mul = float(nrows)

    # ── 获取卡片实际可用宽度 ──
    if hasattr(card_widget, 'width'):
        card_px = card_widget.width()
        if card_px < 400:
            card_px = card_widget.parent().width() if card_widget.parent() else 1200
    else:
        card_px = 1200

    # ── DPI 选择 ──
    if approach == 'export':
        dpi = ChartStyle.DESIGN_DPI
    else:
        dpi = ChartStyle.screen_dpi()

    # ── 计算英寸: 减去 card padding ≈ 40px ──
    usable_px = max(400, card_px - 40)
    width_inches = usable_px / dpi

    # 高度: 行高2.2英寸(比 ROW_H=2.5 稍小, 留出卡片标题空间)
    row_height = 2.2
    if radar:
        height_inches = width_inches  # 雷达图 1:1
    else:
        height_inches = row_height * height_mul

    # ── 缩放因子 (相对于设计基准 7.5") ──
    scale = width_inches / ChartStyle.CARD_W
    # 使用 sqrt 避免极端缩放
    fs_ratio = np.sqrt(max(0.6, min(1.8, scale)))

    # ── 创建 figure ──
    if radar:
        fig, axes = plt.subplots(nrows, ncols,
            figsize=(width_inches, height_inches),
            dpi=dpi, facecolor=ChartStyle.C_BG,
            subplot_kw=dict(polar=True))
    else:
        fig, axes = plt.subplots(nrows, ncols,
            figsize=(width_inches, height_inches),
            dpi=dpi, facecolor=ChartStyle.C_BG)

    # ── 展平 axes ──
    if nrows == 1 and ncols == 1:
        ax_arr = np.array([axes])
    else:
        ax_arr = np.array(axes).ravel() if hasattr(axes, '__len__') else np.array([axes])

    # ── 统一 ax 样式 + 字体缩放 ──
    for ax in ax_arr:
        ax.set_facecolor(ChartStyle.C_BG)
        lw_grid = max(0.3, ChartStyle.LW_GRID * scale)
        ax.grid(True, color=ChartStyle.C_GRID, linewidth=lw_grid, alpha=0.15)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(ChartStyle.C_NEUTRAL)
        ax.spines['bottom'].set_color(ChartStyle.C_NEUTRAL)
        ax.tick_params(labelsize=max(7, int(ChartStyle.TICK_SIZE * fs_ratio)),
                       colors='#555555')

    return fig, axes, scale


class VisualizationManager:
    """可视化管理器 — 全量统计分析图表生成

    所有图表统一使用 ChartStyle 配色 + card_adapted_figure 自适应尺寸
    """

    def plot_overview(self, sw: np.ndarray, exp_head: np.ndarray, ctrl_head: np.ndarray,
                      events: list, out_path: str = None, card_widget=None):
        """全时程概览图 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 3, 1, height_mul=3.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))
        ax1, ax2, ax3 = axes.flatten() if hasattr(axes, '__len__') else [axes]
        t = sw[:, 0]

        ax1.plot(t, sw[:, 1], color=ChartStyle.C_EXP, linewidth=ChartStyle.LW_MAIN * scale)
        ax1.set_ylabel('Speed (km/h)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
        ax1.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)
        ax1.set_title('Vehicle Speed', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))

        ax2.plot(t, sw[:, 2], color=ChartStyle.C_DIFF, linewidth=ChartStyle.LW_MAIN * scale)
        ax2.set_ylabel('Wheel Angle (deg)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
        ax2.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)
        ax2.set_title('Steering Wheel Angle', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))

        ax3.plot(t, exp_head[:, 2], color=ChartStyle.C_EXP, linewidth=ChartStyle.LW_MAIN * scale, alpha=0.8, label='Active')
        ax3.plot(t, ctrl_head[:, 2], color=ChartStyle.C_CTRL, linewidth=ChartStyle.LW_MAIN * scale, alpha=0.8, label='Passive')
        ax3.set_ylabel('Ay (m/s²)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
        ax3.set_xlabel('Time (s)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
        ax3.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)
        ax3.legend(fontsize=max(6, int(ChartStyle.LEGEND_SIZE * fs)))
        ax3.set_title('Head Lateral Acceleration', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))

        for ev in events:
            ax1.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color='#d62728')
            ax2.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color='#d62728')
            ax3.axvspan(ev['t_start'], ev['t_end'], alpha=0.1, color='#d62728')

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_event_comparison(self, df_events: pd.DataFrame, out_path: str = None, card_widget=None):
        """事件RMS对比柱状图 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 1, 3, height_mul=1.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))
        ax1, ax2, ax3 = axes.flatten() if hasattr(axes, '__len__') else [axes]

        for ax, axis in zip([ax1, ax2, ax3], ['Ax', 'Ay', 'Az']):
            e_vals = df_events[f'e_{axis}_RMS'].dropna()
            c_vals = df_events[f'c_{axis}_RMS'].dropna()

            x = np.arange(len(e_vals))
            width = 0.35

            ax.bar(x - width/2, e_vals, width, label='Active', color=ChartStyle.C_EXP, alpha=0.8)
            ax.bar(x + width/2, c_vals, width, label='Passive', color=ChartStyle.C_CTRL, alpha=0.8)

            ax.set_title(f'{axis} RMS Comparison per Event', fontsize=max(7, int(ChartStyle.TITLE_SIZE * fs)))
            ax.set_xlabel('Event Index', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.set_ylabel('RMS (m/s²)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.legend(fontsize=max(6, int(ChartStyle.LEGEND_SIZE * fs)))
            ax.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)
            ax.tick_params(axis='x', labelsize=max(6, int(ChartStyle.TICK_SIZE * fs)))

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_spectrum(self, spec: Dict[str, Any], out_path: str = None, card_widget=None):
        """频谱分析图 (PSD) — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 1, 3, height_mul=1.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))

        for i, ax in enumerate(axes.flatten() if hasattr(axes, '__len__') else [axes]):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = spec.get(axis, {})
            if not s:
                continue

            f = s['freq']
            exp_psd = s['exp_psd']
            ctrl_psd = s['ctrl_psd']

            ax.semilogy(f, exp_psd, color=ChartStyle.C_EXP, label='Active',
                       linewidth=ChartStyle.LW_MAIN * scale)
            ax.semilogy(f, ctrl_psd, color=ChartStyle.C_CTRL, label='Passive',
                       linewidth=ChartStyle.LW_MAIN * scale)
            ax.set_xlim(0.1, 80)
            ax.set_xlabel('Frequency (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.set_ylabel('PSD (m²/s⁴/Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.set_title(f'{axis} Power Spectral Density', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))
            ax.legend(fontsize=max(6, int(ChartStyle.LEGEND_SIZE * fs)))
            ax.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_spectrum_ratio(self, spec: Dict[str, Any], out_path: str = None, card_widget=None):
        """频谱衰减比图 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 1, 3, height_mul=1.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))

        for i, ax in enumerate(axes.flatten() if hasattr(axes, '__len__') else [axes]):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = spec.get(axis, {})
            if not s:
                continue

            f = s['freq']
            ratio = s['ratio']

            ax.plot(f, ratio, color=ChartStyle.C_DIFF, linewidth=ChartStyle.LW_MAIN * scale * 1.5)
            ax.axhline(1.0, color=ChartStyle.C_NEUTRAL, linestyle='--', alpha=0.5,
                      linewidth=ChartStyle.LW_REF * scale)
            ax.set_xlim(0.1, 80)
            ax.set_ylim(0, 2)
            ax.set_xlabel('Frequency (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.set_ylabel('Active/Passive Ratio', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax.set_title(f'{axis} Attenuation Ratio', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))
            ax.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)

            for band_name, (flo, fhi) in {'1-5Hz': (1, 5), '5-20Hz': (5, 20)}.items():
                ax.axvspan(flo, fhi, alpha=0.08, color=ChartStyle.C_DIFF)
                ax.text((flo + fhi)/2, 1.85, band_name, ha='center',
                       fontsize=max(6, int(ChartStyle.ANNOT_SIZE * fs)))

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_stft(self, stft: Dict[str, Any], out_path: str = None, card_widget=None):
        """时频分析图 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 2, 1, height_mul=2.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))
        ax1, ax2 = axes.flatten() if hasattr(axes, '__len__') else [axes]

        s = stft.get('Ay', {})
        if s:
            f = s['f']
            t = s['t']
            exp_spec = s['exp_spec']
            ctrl_spec = s['ctrl_spec']

            im1 = ax1.pcolormesh(t, f, 10 * np.log10(exp_spec + 1e-10),
                                vmin=-80, vmax=-20, cmap='viridis')
            ax1.set_ylim(0, 50)
            ax1.set_ylabel('Frequency (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax1.set_title('Active Seat - STFT', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))

            im2 = ax2.pcolormesh(t, f, 10 * np.log10(ctrl_spec + 1e-10),
                                vmin=-80, vmax=-20, cmap='viridis')
            ax2.set_ylim(0, 50)
            ax2.set_xlabel('Time (s)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax2.set_ylabel('Frequency (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax2.set_title('Passive Seat - STFT', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))

            fig.colorbar(im1, ax=[ax1, ax2], label='Power (dB)')

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_statistics(self, stats: Dict[str, Any], out_path: str = None, card_widget=None):
        """统计仪表盘 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 1, 3, height_mul=1.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))

        for i, ax in enumerate(axes.flatten() if hasattr(axes, '__len__') else [axes]):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = stats.get(axis, {})
            if not s:
                continue

            metrics = ['e_rms', 'c_rms', 'attenuation_pct']
            values = [s.get(m, 0) for m in metrics]
            labels = ['Active RMS', 'Passive RMS', 'Attenuation (%)']

            bars = ax.bar(labels, values, color=[ChartStyle.C_EXP, ChartStyle.C_CTRL, ChartStyle.C_DIFF], alpha=0.8)
            ax.set_title(f'{axis} Statistics', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))
            ax.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)

            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}', ha='center', va='bottom',
                        fontsize=max(7, int(ChartStyle.ANNOT_SIZE * fs)))

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_band_radar(self, spec: Dict[str, Any], out_path: str = None, card_widget=None):
        """频段雷达图 — card_adapted_figure 自适应 (polar)"""
        bands = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
        angles = np.linspace(0, 2 * np.pi, len(bands), endpoint=False)

        fig, ax, scale = card_adapted_figure(card_widget, 1, 1, radar=True)
        fs = np.sqrt(max(0.6, min(1.8, scale)))

        for axis, color in zip(['Ax', 'Ay', 'Az'], [ChartStyle.C_EXP, ChartStyle.C_CTRL, ChartStyle.C_DIFF]):
            values = []
            for band in bands:
                val = spec.get(axis, {}).get('bands_atten', {}).get(band, 0)
                values.append(val)
            values += values[:1]
            ax.plot(np.append(angles, angles[0]), values, 'o-',
                    linewidth=ChartStyle.LW_MAIN * scale * 1.5,
                    markersize=max(3, int(ChartStyle.MS * scale)),
                    label=axis, color=color)

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles)
        ax.set_xticklabels(bands, fontsize=max(7, int(ChartStyle.TICK_SIZE * fs)))
        ax.set_ylim(0, 100)
        ax.set_title('Band Attenuation (%)', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0),
                 fontsize=max(6, int(ChartStyle.LEGEND_SIZE * fs)))
        ax.grid(True)

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_window_attenuation(self, df_windows: pd.DataFrame, out_path: str = None, card_widget=None):
        """滑动窗口衰减趋势图 — card_adapted_figure 自适应"""
        fig, axes, scale = card_adapted_figure(card_widget, 3, 1, height_mul=3.0)
        fs = np.sqrt(max(0.6, min(1.8, scale)))
        ax_arr = axes.flatten() if hasattr(axes, '__len__') else [axes]

        for i, ax in enumerate(ax_arr):
            axis = ['Ax', 'Ay', 'Az'][i]
            col = f'atten_{axis}_pct'
            if col in df_windows.columns:
                ax.plot(df_windows['t_center'], df_windows[col],
                        color=ChartStyle.C_DIFF, linewidth=ChartStyle.LW_MAIN * scale, alpha=0.8)
                ax.axhline(0, color=ChartStyle.C_NEUTRAL, linestyle='--', alpha=0.5,
                          linewidth=ChartStyle.LW_REF * scale)
                ax.set_ylabel(f'{axis} Attenuation (%)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
                ax.set_title(f'{axis} Window Attenuation', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)))
                ax.grid(True, color=ChartStyle.C_GRID, linewidth=ChartStyle.LW_GRID, alpha=0.15)

        ax_arr[-1].set_xlabel('Time (s)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def plot_statistical_features(self, stats: Dict[str, Any], spec: Dict[str, Any],
                                   out_path: str = None, card_widget=None):
        """★ 新增: 统计特征热力图 (fig9_stat_features) — card_adapted_figure 自适应"""
        axes_names = ['Ax', 'Ay', 'Az']
        bands = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
        metrics_names = ['e_rms', 'c_rms', 'attenuation_pct', 't_stat', 'p_value', 'cohens_d']

        data = np.zeros((len(metrics_names), len(axes_names)))
        row_labels = ['Active RMS', 'Passive RMS', 'Attenuation %', 't-stat', 'p-value', 'Cohen\'s d']
        col_labels = axes_names

        for j, ax_name in enumerate(axes_names):
            s = stats.get(ax_name, {})
            data[0, j] = s.get('e_rms', 0)
            data[1, j] = s.get('c_rms', 0)
            data[2, j] = s.get('attenuation_pct', 0)
            data[3, j] = s.get('t_stat', 0)
            data[4, j] = s.get('p_value', 1)
            data[5, j] = s.get('cohens_d', 0)

        fig, ax, scale = card_adapted_figure(card_widget, 1, 1, height_mul=1.2)
        fs = np.sqrt(max(0.6, min(1.8, scale)))

        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=-1, vmax=1)
        # 单独处理p_value: 对已经填充的data[4]行, 按p值调整颜色
        for j in range(len(axes_names)):
            p = data[4, j]
            data[4, j] = 1 - p if p < 1 else 0  # 越小越绿
        im.set_data(data)

        ax.set_xticks(range(len(axes_names)))
        ax.set_xticklabels(col_labels, fontsize=max(7, int(ChartStyle.TICK_SIZE * fs)))
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, fontsize=max(7, int(ChartStyle.TICK_SIZE * fs)))

        for i in range(len(row_labels)):
            for j in range(len(axes_names)):
                val = stats.get(axes_names[j], {}).get(
                    metrics_names[i].replace('cohens_d', 'cohens_d'), 0)
                if i == 4:  # p-value
                    text = f'{stats.get(axes_names[j], {}).get("p_value", 1):.2e}'
                else:
                    text = f'{stats.get(axes_names[j], {}).get(metrics_names[i], 0):.2f}'
                ax.text(j, i, text, ha='center', va='center',
                       fontsize=max(6, int(ChartStyle.ANNOT_SIZE * fs)))

        ax.set_title('Statistical Feature Heatmap', fontsize=max(8, int(ChartStyle.TITLE_SIZE * fs)), fontweight='bold')
        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.ax.tick_params(labelsize=max(6, int(ChartStyle.TICK_SIZE * fs)))

        fig.tight_layout(pad=1.2 * scale)
        if out_path:
            fig.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"  生成: {os.path.basename(out_path)}")
        return fig

    def generate_all_plots(self, evaluator, out_dir: str):
        """生成所有图表 (9张) — 全部使用 card_adapted_figure + ChartStyle

        返回: out_dir (str) — PNG 输出目录
        """
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
                                     os.path.join(out_dir, 'fig4_spectrum_ratio.png'))
            self.plot_band_radar(evaluator.results['spectrum'],
                                  os.path.join(out_dir, 'fig5_band_radar.png'))

        if 'stft' in evaluator.results:
            self.plot_stft(evaluator.results['stft'],
                           os.path.join(out_dir, 'fig6_stft.png'))

        if 'statistics' in evaluator.results:
            self.plot_statistics(evaluator.results['statistics'],
                                 os.path.join(out_dir, 'fig7_statistics.png'))

        if 'windows' in evaluator.results and len(evaluator.results['windows']) > 0:
            self.plot_window_attenuation(evaluator.results['windows'],
                                          os.path.join(out_dir, 'fig8_window_atten.png'))

        # ★ 新增: 统计特征热力图
        if 'statistics' in evaluator.results and 'spectrum' in evaluator.results:
            self.plot_statistical_features(evaluator.results['statistics'],
                                           evaluator.results['spectrum'],
                                           os.path.join(out_dir, 'fig9_stat_features.png'))

        logger.info(f"  共生成 {len(os.listdir(out_dir))} 个图表")
        return out_dir