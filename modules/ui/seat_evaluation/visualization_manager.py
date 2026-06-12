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

# ── 中文字体（跨平台检测 — 统一入口）──
import platform as _platform

def detect_cn_font():
    """跨平台检测最佳可用中文字体（模块级单例，供 advanced_charts 等复用）"""
    from matplotlib.font_manager import FontManager
    fm = FontManager()
    available = {f.name for f in fm.ttflist}
    candidates = []
    if _platform.system() == 'Windows':
        candidates = ['Microsoft YaHei', 'SimHei', 'FangSong', 'KaiTi']
    elif _platform.system() == 'Darwin':
        candidates = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Apple LiGothic']
    else:
        candidates = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Noto Sans SC']
    for name in candidates:
        if name in available:
            return name
    for f in fm.ttflist:
        fn = f.name.lower()
        if any(kw in fn for kw in ['cjk', 'hei', 'ming', 'song', 'yahei']):
            return f.name
    return 'sans-serif'

CN_FONT = detect_cn_font()
CN_FONT_FAMILY = CN_FONT            # 兼容别名
CN_FONT_LIST = [CN_FONT, 'SimHei', 'DejaVu Sans']

# 统一入口：配置全局 rcParams（advanced_charts 通过 import 继承，不再单独设置）
plt.rcParams['font.sans-serif'] = CN_FONT_LIST
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['mathtext.default'] = 'regular'  # 修复 \u2212 字形缺失警告


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
    C_RED = '#D55E00'       # 警示 - 红
    C_PURPLE = '#CC79A7'    # 辅助 - 紫
    C_EXP_LIGHT = '#AED6F1' # 实验组浅
    C_CTRL_LIGHT = '#F9E79F'# 对照组浅
    C_GRID = '#CCCCCC'
    C_NEUTRAL = '#999999'
    C_GRID_ALPHA = 0.15

    # ── 字体 (绝对点数, 基准为7.5英寸卡片) ──
    FONT_SIZE = 9
    TITLE_SIZE = 10          # 子图标题 (统一为10pt)
    LABEL_SIZE = 9           # 坐标轴标签
    TICK_SIZE = 8            # 刻度标签
    LEGEND_SIZE = 7.5        # 图例
    ANNOT_SIZE = 7           # 标注
    SUPTITLE_SIZE = 10       # 总标题 (统一为10pt)

    # ── 导出图表字体缩放 (相对于卡片基准) ──
    EXPORT_FONT_SCALE = 1.3  # 导出图表 (16-18英寸) 字体放大系数

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
            'font.sans-serif': CN_FONT_LIST,
            'axes.unicode_minus': False,
        })

# 模块导入时自动应用—次全局样式(advanced_charts 等下游模块都继承此设置)
ChartStyle.apply_rcparams()


def card_adapted_figure(card_widget, nrows=1, ncols=1, height_mul=None,
                         approach='auto', radar=False):
    """
    根据 QWidget 的实际像素宽度动态创建 matplotlib Figure。

    修复内容:
    - 强制触发布局计算后再获取宽度
    - 区分 ScrollArea viewport / 普通 QWidget
    - 无效值检测 + 父级链遍历

    返回: (fig, axes, scale) where scale 是字体/线宽的缩放因子
    """
    from PySide6.QtWidgets import QApplication, QScrollArea

    if height_mul is None:
        height_mul = float(nrows)

    # ── 强制完成布局 ──
    if not card_widget.isVisible():
        card_widget.show()
    QApplication.processEvents()
    card_widget.updateGeometry()
    QApplication.processEvents()

    # ── 获取可用宽度 ──
    parent = card_widget.parent()
    if isinstance(parent, QScrollArea):
        card_px = parent.viewport().width()
    elif hasattr(card_widget, 'contentsRect'):
        card_px = card_widget.contentsRect().width()
    else:
        card_px = card_widget.width()

    # ── 无效值检测与回退 ──
    if card_px < 200:
        # 遍历父级链查找有效宽度
        p = card_widget.parent()
        depth = 0
        while p and depth < 5:
            if hasattr(p, 'viewport'):
                card_px = p.viewport().width()
                break
            card_px = p.width()
            if card_px >= 400:
                break
            p = p.parent()
            depth += 1

        # 最终回退: 顶层窗口的 65%
        if card_px < 200:
            top = card_widget.window()
            card_px = max(400, int(top.width() * 0.65)) if top else 1200

    # ── DPI 选择 ──
    if approach == 'export':
        dpi = ChartStyle.DESIGN_DPI
    else:
        dpi = ChartStyle.screen_dpi()

    # ── 计算英寸: 减去 card padding (30px each side) ──
    usable_px = max(400, card_px - 60)
    width_inches = usable_px / dpi

    # 高度: 行高2.2英寸(比 ROW_H=2.5 稍小, 留出卡片标题空间)
    row_height = 2.2
    if radar:
        height_inches = width_inches  # 雷达图 1:1
    else:
        height_inches = row_height * height_mul

    # ── 缩放因子 (相对于设计基准 7.5") ──
    scale = width_inches / ChartStyle.CARD_W
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
        # 极坐标无矩形spine，跳过top/right/left/bottom样式
        if not radar:
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color(ChartStyle.C_NEUTRAL)
            ax.spines['bottom'].set_color(ChartStyle.C_NEUTRAL)
        ax.tick_params(labelsize=max(7, round(ChartStyle.TICK_SIZE * fs_ratio)),
                       colors='#555555')

    return fig, axes, scale


class VisualizationManager:
    """可视化管理器"""

    def __init__(self):
        # 统一使用 ChartStyle 配色 (Okabe-Ito 色盲友好)
        self.colors = {
            'exp': ChartStyle.C_EXP,
            'ctrl': ChartStyle.C_CTRL,
            'exp_light': ChartStyle.C_EXP_LIGHT,
            'ctrl_light': ChartStyle.C_CTRL_LIGHT,
            'green': ChartStyle.C_DIFF,
            'red': ChartStyle.C_RED,
            'purple': ChartStyle.C_PURPLE,
        }

    def plot_overview(self, sw: np.ndarray, exp_head: np.ndarray, ctrl_head: np.ndarray,
                      events: list, out_path: str):
        """全时程概览图"""
        # 数组边界校验
        if sw is None or sw.shape[1] < 3:
            logger.warning("全时程概览图: 车速数据缺失或列数不足，跳过")
            return
        if exp_head is None or exp_head.shape[1] < 3:
            logger.warning("全时程概览图: 实验组头部数据缺失或列数不足，跳过")
            return
        if ctrl_head is None or ctrl_head.shape[1] < 3:
            logger.warning("全时程概览图: 对照组头部数据缺失或列数不足，跳过")
            return

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
        t = sw[:, 0]

        ax1.plot(t, sw[:, 1], color=ChartStyle.C_EXP, linewidth=1.5)
        ax1.set_ylabel('车速 (km/h)', fontsize=ChartStyle.LABEL_SIZE)
        ax1.grid(alpha=0.3)
        ax1.set_title('车辆速度', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')

        ax2.plot(t, sw[:, 2], color=ChartStyle.C_PURPLE, linewidth=1.5)
        ax2.set_ylabel('方向盘转角 (°)', fontsize=ChartStyle.LABEL_SIZE)
        ax2.grid(alpha=0.3)
        ax2.set_title('方向盘转角', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')

        ax3.plot(t, exp_head[:, 2], color=self.colors['exp'], linewidth=0.8, alpha=0.8, label='实验组')
        ax3.plot(t, ctrl_head[:, 2], color=self.colors['ctrl'], linewidth=0.8, alpha=0.8, label='对照组')
        ax3.set_ylabel('Ay (m/s$^2$)', fontsize=ChartStyle.LABEL_SIZE)
        ax3.set_xlabel('时间 (s)', fontsize=ChartStyle.LABEL_SIZE)
        ax3.grid(alpha=0.3)
        ax3.legend()
        ax3.set_title('头部横向加速度', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')

        # 事件数 > 30 时截断并标注
        t_max = t[-1] if len(t) > 0 else 1e6
        shown_events = events[:30] if len(events) > 30 else events
        for ev in shown_events:
            ts_val = max(0, ev['t_start'])
            te_val = min(t_max, ev['t_end'])
            if te_val <= ts_val:
                continue
            ax1.axvspan(ts_val, te_val, alpha=0.1, color=ChartStyle.C_RED)
            ax2.axvspan(ts_val, te_val, alpha=0.1, color=ChartStyle.C_RED)
            ax3.axvspan(ts_val, te_val, alpha=0.1, color=ChartStyle.C_RED)
        if len(events) > 30:
            ax1.text(0.99, 0.95, f'(仅显示前30个，共{len(events)}个事件)',
                     transform=ax1.transAxes, ha='right', va='top', fontsize=ChartStyle.ANNOT_SIZE,
                     color=ChartStyle.C_NEUTRAL)

        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
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
            
            ax.bar(x - width/2, e_vals, width, label='实验组', color=self.colors['exp'])
            ax.bar(x + width/2, c_vals, width, label='对照组', color=self.colors['ctrl'])
            
            ax.set_title(f'{axis}轴 每事件RMS对比', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            ax.set_xlabel('事件序号', fontsize=ChartStyle.LABEL_SIZE)
            ax.set_ylabel('RMS (m/s$^2$)', fontsize=ChartStyle.LABEL_SIZE)
            ax.legend()
            ax.grid(alpha=0.3)
            ax.tick_params(axis='x', labelsize=ChartStyle.TICK_SIZE)

        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_spectrum(self, spec: Dict[str, Any], out_path: str):
        """频谱分析图"""
        if not spec or not isinstance(spec, dict):
            logger.warning("频谱数据为空, 跳过 fig3_spectrum")
            return
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        has_data = False
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = spec.get(axis, {})
            if not s:
                continue
            
            f = s.get('freq')
            exp_psd = s.get('exp_psd')
            ctrl_psd = s.get('ctrl_psd')
            if f is None or exp_psd is None or ctrl_psd is None:
                continue
            if len(f) == 0 or len(exp_psd) == 0 or len(ctrl_psd) == 0:
                continue
                
            ax.semilogy(f, exp_psd, color=self.colors['exp'], label='实验组', linewidth=1.2)
            ax.semilogy(f, ctrl_psd, color=self.colors['ctrl'], label='对照组', linewidth=1.2)
            ax.set_xlim(0.1, 80)
            ax.set_xlabel('频率 (Hz)', fontsize=ChartStyle.LABEL_SIZE)
            ax.set_ylabel('PSD (m²/s⁴/Hz)', fontsize=ChartStyle.LABEL_SIZE)
            ax.set_title(f'{axis}轴 功率谱密度', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)
            has_data = True

        if not has_data:
            plt.close(fig)
            logger.warning("频谱数据无有效内容, 跳过 fig3_spectrum")
            return
        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
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
            
            ax.plot(f, ratio, color=ChartStyle.C_PURPLE, linewidth=1.2)
            ax.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
            ax.set_xlim(0.1, 80)
            # 数据驱动上限: 95分位但不低于2, 不高于10
            ratio_clipped = np.clip(ratio, 0, 10)
            y_max = max(2.0, np.percentile(ratio_clipped[~np.isnan(ratio_clipped)], 95)) if len(ratio) > 0 else 2.0
            ax.set_ylim(0, y_max)
            ax.set_xlabel('频率 (Hz)', fontsize=ChartStyle.LABEL_SIZE)
            ax.set_ylabel('Active/Passive 比值 (>1=实验组更大)', fontsize=ChartStyle.LABEL_SIZE)
            ax.set_title(f'{axis}轴 衰减率', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            ax.grid(alpha=0.3)
            
            for band_name, (flo, fhi) in {'1-5Hz': (1, 5), '5-20Hz': (5, 20)}.items():
                ax.axvspan(flo, fhi, alpha=0.1, color=self.colors['green'])
                ax.text((flo + fhi)/2, 1.8, band_name, ha='center', fontsize=8)

        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_stft(self, stft_data: Dict[str, Any], out_path: str):
        """时频分析图"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
        plt.subplots_adjust(hspace=0.25)
        
        s = stft.get('Ay', {})
        if s:
            f = s['f']
            t = s['t']
            exp_spec = s['exp_spec']
            ctrl_spec = s['ctrl_spec']
            
            im1 = ax1.pcolormesh(t, f, 10 * np.log10(exp_spec + 1e-10), 
                                vmin=-80, vmax=-20, cmap='viridis')
            ax1.set_ylim(0, 50)
            ax1.set_ylabel('频率 (Hz)', fontsize=ChartStyle.LABEL_SIZE)
            ax1.set_title('实验组 - STFT', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            
            im2 = ax2.pcolormesh(t, f, 10 * np.log10(ctrl_spec + 1e-10),
                                vmin=-80, vmax=-20, cmap='viridis')
            ax2.set_ylim(0, 50)
            ax2.set_xlabel('时间 (s)', fontsize=ChartStyle.LABEL_SIZE)
            ax2.set_ylabel('频率 (Hz)', fontsize=ChartStyle.LABEL_SIZE)
            
            fig.colorbar(im1, ax=ax1, label='Power (dB)')
            fig.colorbar(im2, ax=ax2, label='Power (dB)')

        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_statistics(self, stats: Dict[str, Any], out_path: str):
        """统计仪表盘 — 三轴 RMS / Peak / 衰减率对比"""
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            s = stats.get(axis, {})
            if not s:
                continue
            
            metrics = ['e_rms', 'c_rms', 'e_peak', 'c_peak', 'attenuation_pct']
            values = [s.get(m, 0) for m in metrics]
            labels = ['Active\nRMS', 'Passive\nRMS', 'Active\nPeak', 'Passive\nPeak', '衰减率\n(%)']
            colors_bar = [self.colors['exp'], self.colors['ctrl'],
                         self.colors['exp_light'], self.colors['ctrl_light'],
                         self.colors['green']]
            
            bars = ax.bar(labels, values, color=colors_bar, edgecolor='white', linewidth=0.5)
            ax.set_title(f'{axis}轴 统计分析', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            ax.set_ylabel('加速度 (m/s$^2$) / 百分比 (%)', fontsize=ChartStyle.LABEL_SIZE)
            ax.grid(axis='y', alpha=0.3)
            
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{height:.2f}', ha='center', va='bottom', fontsize=ChartStyle.ANNOT_SIZE, rotation=90)

        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_band_radar(self, spec: Dict[str, Any], out_path: str):
        """频段雷达图"""
        bands = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
        angles = np.linspace(0, 2 * np.pi, len(bands), endpoint=False)
        
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))
        
        all_values = []
        for axis, color in zip(['Ax', 'Ay', 'Az'], [self.colors['exp'], self.colors['ctrl'], self.colors['purple']]):
            values = []
            for band in bands:
                val = spec.get(axis, {}).get('bands_atten', {}).get(band, 0)
                values.append(val)
            all_values.extend(values)
            values += values[:1]
            ax.plot(np.append(angles, angles[0]), values, 'o-', linewidth=2, markersize=6,
                    label=axis, color=color)
        
        # 数据自适应 Y 轴范围（含 10% padding）
        if all_values:
            v_min, v_max = min(all_values), max(all_values)
            pad = max((v_max - v_min) * 0.1, 1)
            ax.set_ylim(max(v_min - pad, 0) if v_min >= 0 else v_min - pad, v_max + pad)
        
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles)
        ax.set_xticklabels(bands)
        ax.set_title('频段衰减率 (%)', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
        ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1.0))
        ax.grid(True)
        
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_window_attenuation(self, df_windows: pd.DataFrame, out_path: str):
        """滑动窗口衰减趋势图"""
        if 't_center' not in df_windows.columns:
            logger.warning("滑动窗口衰减图: 缺少 t_center 列，跳过")
            return

        fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
        
        for i, ax in enumerate(axes):
            axis = ['Ax', 'Ay', 'Az'][i]
            col = f'atten_{axis}_pct'
            if col in df_windows.columns:
                ax.plot(df_windows['t_center'], df_windows[col], 
                        color=self.colors['green'], linewidth=1, alpha=0.8)
                ax.axhline(0, color='gray', linestyle='--', alpha=0.5)
                ax.set_ylabel(f'{axis} 衰减率 (%)', fontsize=ChartStyle.LABEL_SIZE)
                ax.set_title(f'{axis}轴 窗口衰减', fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
                ax.grid(alpha=0.3)
        
        axes[-1].set_xlabel('时间 (s)', fontsize=ChartStyle.LABEL_SIZE)
        plt.tight_layout()
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def plot_stat_features(self, metrics: Dict[str, float], out_path: str):
        """统计特征(算子级输出) — VDV/CrestFactor/Skewness/Kurtosis/MAV/ImpulseFactor
        
        2行×3列 布局:
          Row1: VDV | CrestFactor | Skewness
          Row2: Kurtosis | MAV | ImpulseFactor
        每组内 exp(蓝) vs ctrl(橙) 分三轴(Ax/Ay/Az) 对比
        """
        if not metrics:
            logger.warning("统计特征数据为空, 跳过 fig8_stat_features")
            return

        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        axes_flat = axes.flatten()

        metric_keys = ['VDV', 'CrestFactor', 'Skewness', 'Kurtosis', 'MAV', 'ImpulseFactor']
        metric_labels = ['VDV', 'Crest Factor', 'Skewness', 'Kurtosis (excess)', 'MAV', 'Impulse Factor']
        axes_names = ['Ax', 'Ay', 'Az']
        x = np.arange(len(axes_names))
        width = 0.35

        for idx, (mkey, mlabel) in enumerate(zip(metric_keys, metric_labels)):
            ax = axes_flat[idx]
            exp_vals = []
            ctrl_vals = []
            nan_mask_exp = []
            nan_mask_ctrl = []
            for a in axes_names:
                ev = metrics.get(f'exp_{a}_{mkey}', np.nan)
                cv = metrics.get(f'ctrl_{a}_{mkey}', np.nan)
                nan_mask_exp.append(not np.isfinite(ev))
                nan_mask_ctrl.append(not np.isfinite(cv))
                exp_vals.append(ev if np.isfinite(ev) else 0.0)
                ctrl_vals.append(cv if np.isfinite(cv) else 0.0)

            x_pos = np.arange(len(axes_names))
            bars1 = ax.bar(x_pos - width/2, exp_vals, width, label='实验组',
                          color=self.colors['exp'], edgecolor='white', linewidth=0.5)
            bars2 = ax.bar(x_pos + width/2, ctrl_vals, width, label='对照组',
                          color=self.colors['ctrl'], edgecolor='white', linewidth=0.5)

            ax.set_title(mlabel, fontsize=ChartStyle.TITLE_SIZE, fontweight='bold')
            ax.set_xticks(x_pos)
            ax.set_xticklabels(axes_names)
            ax.grid(axis='y', alpha=0.3)
            if idx == 0:
                ax.legend(fontsize=ChartStyle.LEGEND_SIZE)

            # 数值标注（NaN 项显示 N/A）
            for bar, is_nan in zip(bars1, nan_mask_exp):
                h = bar.get_height()
                if is_nan:
                    ax.text(bar.get_x() + bar.get_width()/2., 0.05,
                            'N/A', ha='center', va='bottom', fontsize=6, color='gray')
                elif h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., h,
                            f'{h:.2f}', ha='center', va='bottom', fontsize=ChartStyle.ANNOT_SIZE, rotation=90)
            for bar, is_nan in zip(bars2, nan_mask_ctrl):
                h = bar.get_height()
                if is_nan:
                    ax.text(bar.get_x() + bar.get_width()/2., 0.05,
                            'N/A', ha='center', va='bottom', fontsize=6, color='gray')
                elif h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., h,
                            f'{h:.2f}', ha='center', va='bottom', fontsize=ChartStyle.ANNOT_SIZE, rotation=90)

        fig.suptitle('统计特征 (算子级输出) — 实验组 vs 对照组', fontsize=ChartStyle.SUPTITLE_SIZE, fontweight='bold', y=0.99)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(out_path, dpi=ChartStyle.DESIGN_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  生成: {os.path.basename(out_path)}")

    def generate_all_plots(self, evaluator, out_dir: str):
        """生成所有图表 — 容错模式: 单图失败不影响其他图表"""
        os.makedirs(out_dir, exist_ok=True)
        generated = []

        def _safe_plot(label, out_path, plot_fn, *args):
            """安全调用单个 plot 方法, 失败时记录日志"""
            try:
                plot_fn(*args, out_path)
                generated.append(label)
            except Exception as e:
                logger.warning(f"  ✗ {label} 生成失败: {e}")

        sw = evaluator.sw
        exp_keys = list(evaluator.exp.keys())
        ctrl_keys = list(evaluator.ctrl.keys())

        if sw is not None and len(exp_keys) > 0 and len(ctrl_keys) > 0:
            exp_head = evaluator.get_aligned(exp_keys[0])
            ctrl_head = evaluator.get_aligned(ctrl_keys[0])
            if exp_head is not None and ctrl_head is not None:
                _safe_plot('fig1_overview', os.path.join(out_dir, 'fig1_overview.png'),
                           self.plot_overview, sw, exp_head, ctrl_head, evaluator.events)

        if 'events' in evaluator.results and len(evaluator.results['events']) > 0:
            _safe_plot('fig2_events', os.path.join(out_dir, 'fig2_events.png'),
                       self.plot_event_comparison, evaluator.results['events'])

        if 'spectrum' in evaluator.results:
            spec = evaluator.results['spectrum']
            _safe_plot('fig3_spectrum', os.path.join(out_dir, 'fig3_spectrum.png'),
                       self.plot_spectrum, spec)
            _safe_plot('fig3b_ratio', os.path.join(out_dir, 'fig3b_ratio.png'),
                       self.plot_spectrum_ratio, spec)
            _safe_plot('fig6_band_radar', os.path.join(out_dir, 'fig6_band_radar.png'),
                       self.plot_band_radar, spec)

        if 'stft' in evaluator.results:
            _safe_plot('fig4_stft', os.path.join(out_dir, 'fig4_stft.png'),
                       self.plot_stft, evaluator.results['stft'])

        if 'statistics' in evaluator.results:
            _safe_plot('fig5_statistics', os.path.join(out_dir, 'fig5_statistics.png'),
                       self.plot_statistics, evaluator.results['statistics'])

        if 'windows' in evaluator.results and len(evaluator.results['windows']) > 0:
            _safe_plot('fig7_window_atten', os.path.join(out_dir, 'fig7_window_atten.png'),
                       self.plot_window_attenuation, evaluator.results['windows'])

        if 'metrics' in evaluator.results and evaluator.results['metrics']:
            _safe_plot('fig8_stat_features', os.path.join(out_dir, 'fig8_stat_features.png'),
                       self.plot_stat_features, evaluator.results['metrics'])

        logger.info(f"  共生成 {len(generated)} 个图表: {', '.join(generated)}")
        return out_dir