"""
高级可视化图表生成器
====================
参照 SciClaw 专家系统，提供出版物质量的科学图表：
- 驾驶事件时间线（车速 + 方向盘 + 事件色块）
- PSD 功率谱密度对比（3点位）
- SRS 冲击响应谱对比
- 归一化雷达对比图
- 衰减效率柱状图
- 三轴加速度时域波形
"""

import os
import numpy as np
from typing import Dict, List, Optional, Any
import logging

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.font_manager import FontProperties
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

# ── 配色方案（专业实验室风格）──
COLORS = {
    'primary':   '#2E75B6',
    'secondary': '#1F3864',
    'accent':    '#E74C3C',
    'green':     '#27AE60',
    'orange':    '#F39C12',
    'purple':    '#8E44AD',
    'exp':       '#2E75B6',
    'ctrl':      '#E67E22',
    'grey':      '#95A5A6',
}

# ── 事件类型配色 ──
EVENT_COLORS = {
    'parked':                  '#7F8C8D',
    'cruising':                '#27AE60',
    'normal_acceleration':     '#3498DB',
    'aggressive_acceleration': '#F39C12',
    'normal_deceleration':     '#3498DB',
    'aggressive_deceleration': '#E74C3C',
    'emergency_braking':       '#E74C3C',
    'left_turn':               '#9B59B6',
    'right_turn':              '#2E86C1',
    'tight_turn':              '#E74C3C',
    'wide_turn':               '#F39C12',
    'weaving':                 '#8E44AD',
    'cornering_acceleration':  '#E67E22',
    'skid_risk':               '#E74C3C',
    'rapid_direction_change':  '#D35400',
    'lane_keeping':            '#1ABC9C',
    'constant_speed':          '#2980B9',
}

# ── 中文字体配置 ──
CN_FONT_FAMILY = 'Microsoft YaHei'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': [CN_FONT_FAMILY, 'SimHei', 'DejaVu Sans'],
    'axes.unicode_minus': False,
})

# ══════════════════════════════════════════════════════════════════
# 图表1: 驾驶事件时间线
# ══════════════════════════════════════════════════════════════════

def create_event_timeline(t: np.ndarray, speed: np.ndarray, wheel: np.ndarray,
                          events: List[Dict], title: str = "驾驶事件时间线",
                          figsize: tuple = (12, 5)) -> Figure:
    """生成驾驶事件时间线图（车速曲线 + 方向盘曲线 + 事件色块标注）"""
    fig = Figure(figsize=figsize, dpi=100)
    fig.patch.set_facecolor('white')
    
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    
    # ── 上车速曲线 ──
    ax1.plot(t, speed, color=COLORS['primary'], linewidth=1.5, label='车速')
    ax1.fill_between(t, 0, speed, alpha=0.08, color=COLORS['primary'])
    ax1.set_ylabel('车速 (km/h)', fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax1.set_title(title, fontsize=13, fontweight='bold', fontfamily=CN_FONT_FAMILY)
    
    # ── 事件色块标注 ──
    y_top = speed.max() * 0.88
    y_step = speed.max() * 0.06
    label_positions = []
    for i, evt in enumerate(events):
        t0 = evt.get('t_start', evt.get('start_time', 0))
        t1 = evt.get('t_end', evt.get('end_time', t0 + 0.5))
        etype = evt.get('event_type', evt.get('type', ''))
        ename = evt.get('event_name', evt.get('name', etype))
        color = EVENT_COLORS.get(etype, '#3498DB')
        
        ax1.axvspan(t0, t1, alpha=0.12, color=color)
        # 避免标签重叠
        mid = (t0 + t1) / 2
        y_idx = 0
        for prev_mid, prev_y in label_positions:
            if abs(mid - prev_mid) < 0.5:
                y_idx = max(y_idx, prev_y + 1)
        label_positions.append((mid, y_idx))
        y_label = y_top - y_idx * y_step
        ax1.annotate(ename, (mid, y_label), fontsize=6, ha='center',
                     color=color, fontfamily=CN_FONT_FAMILY, rotation=35,
                     alpha=0.85)
    
    ax1.legend(loc='upper right', prop={'family': CN_FONT_FAMILY, 'size': 8})
    ax1.grid(True, alpha=0.2)
    
    # ── 下方向盘曲线 ──
    ax2.plot(t, wheel, color=COLORS['purple'], linewidth=0.8)
    ax2.fill_between(t, 0, wheel, alpha=0.06, color=COLORS['purple'])
    ax2.axhline(y=0, color='grey', linewidth=0.5, linestyle='--', alpha=0.5)
    ax2.set_xlabel('时间 (s)', fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax2.set_ylabel('转角 (°)', fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax2.grid(True, alpha=0.2)
    
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表2: PSD功率谱密度对比
# ══════════════════════════════════════════════════════════════════

def create_psd_comparison(channel_data_map: Dict[str, Dict],
                          exp_imus: List[str], ctrl_imus: List[str],
                          positions: List[tuple] = None,
                          axis: str = 'Z',
                          figsize: tuple = (14, 4.5)) -> Optional[Figure]:
    """
    生成 PSD 功率谱密度对比图。
    
    Args:
        channel_data_map: {imu_name: {channel: numpy_array}}
        exp_imus: 实验组 IMU 名称列表
        ctrl_imus: 对照组 IMU 名称列表
        positions: [(位置名, exp_imu, ctrl_imu), ...]
        axis: 分析轴 ('X', 'Y', 'Z')
    """
    from scipy import signal as sp_signal
    
    if positions is None:
        # 默认：头部、座垫R点、座椅底部
        positions = [
            (n for n in exp_imus if '头部' in n or 'Head' in n),
            (n for n in exp_imus if '座垫R点' in n or 'SeatR' in n),
            (n for n in exp_imus if '座椅底部' in n or 'SeatBase' in n),
        ]
        # 查找匹配的对照组
        paired = []
        for exp_name in exp_imus[:3]:
            ctrl_name = exp_name.replace('-1', '-2')
            location = exp_name.split('_')[1] if '_' in exp_name else exp_name
            paired.append((location, exp_name, ctrl_name if ctrl_name in ctrl_imus else None))
        positions = paired
    
    valid_positions = [(loc, e, c) for loc, e, c in positions
                       if e in channel_data_map and c and c in channel_data_map]
    
    if len(valid_positions) < 2:
        return None
    
    n = len(valid_positions)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4.5))
    if n == 1:
        axes = [axes]
    
    channel_key = f"Az_m_s2" if axis == 'Z' else f"A{axis.lower()}_m_s2"
    
    for ax, (loc, exp_imu, ctrl_imu) in zip(axes, valid_positions):
        for label, imu, style in [
            ('实验组', exp_imu, {'color': COLORS['exp'], 'ls': '-'}),
            ('对照组', ctrl_imu, {'color': COLORS['ctrl'], 'ls': '--'})
        ]:
            data_dict = channel_data_map.get(imu, {})
            ch_data = data_dict.get(channel_key)
            if ch_data is None:
                continue
            
            # 估算采样率
            if 'rel_time' in data_dict:
                t_arr = data_dict['rel_time']
                fs = 1.0 / np.median(np.diff(t_arr)) if len(t_arr) > 1 else 512
            else:
                fs = 512
            
            nperseg = min(1024, len(ch_data) // 2)
            noverlap = min(512, nperseg // 2)
            try:
                f, pxx = sp_signal.welch(ch_data, fs, nperseg=nperseg,
                                         noverlap=noverlap, window='hann')
                mask = (f >= 0.5) & (f <= 80)
                ax.semilogx(f[mask], 10 * np.log10(pxx[mask] + 1e-12),
                           label=label, linewidth=1.5, **style)
            except Exception as e:
                logger.debug(f"PSD计算失败 {imu}: {e}")
        
        ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT_FAMILY)
        ax.set_ylabel(f'{axis}轴 PSD (dB)', fontsize=10, fontfamily=CN_FONT_FAMILY)
        ax.set_title(f'{loc} {axis}轴PSD', fontsize=11, fontfamily=CN_FONT_FAMILY)
        ax.legend(prop={'family': CN_FONT_FAMILY, 'size': 8})
        ax.grid(True, alpha=0.25)
    
    fig.suptitle(f'座椅各点位 {axis}轴 功率谱密度对比', fontsize=14,
                 fontweight='bold', fontfamily=CN_FONT_FAMILY, y=1.02)
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表3: 归一化雷达对比图
# ══════════════════════════════════════════════════════════════════

def create_comparison_radar(comparison_data: Dict[str, Dict],
                            figsize: tuple = (7, 7)) -> Optional[Figure]:
    """
    生成归一化雷达对比图。
    
    Args:
        comparison_data: {指标名: {'exp': float, 'ctrl': float, 'atten_pct': float, ...}}
    """
    # 提取可对比的标量指标
    items = []
    for key, val in comparison_data.items():
        if isinstance(val, dict) and 'exp' in val and 'ctrl' in val:
            e, c = val['exp'], val['ctrl']
            if abs(c) > 1e-9:
                items.append((key[:10], e / c))
    
    if len(items) < 3:
        return None
    
    labels = [it[0] for it in items]
    exp_vals = [it[1] for it in items]
    ctrl_vals = [1.0] * len(items)
    
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    exp_vals_plot = exp_vals + [exp_vals[0]]
    ctrl_vals_plot = ctrl_vals + [ctrl_vals[0]]
    angles_plot = angles + [angles[0]]
    
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={'projection': 'polar'})
    
    ax.fill(angles_plot, exp_vals_plot, alpha=0.2, color=COLORS['exp'])
    ax.plot(angles_plot, exp_vals_plot, color=COLORS['exp'], linewidth=2,
            marker='o', markersize=6, label='实验组')
    ax.fill(angles_plot, ctrl_vals_plot, alpha=0.1, color=COLORS['ctrl'])
    ax.plot(angles_plot, ctrl_vals_plot, color=COLORS['ctrl'], linewidth=2,
            marker='s', markersize=6, linestyle='--', label='对照组(基准=1.0)')
    
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9, fontfamily=CN_FONT_FAMILY)
    ax.set_yticklabels([])
    ax.set_title('实验组 vs 对照组 — 归一化对比 (对照组=1.0)',
                 fontsize=13, fontweight='bold', fontfamily=CN_FONT_FAMILY, pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.05),
              prop={'family': CN_FONT_FAMILY, 'size': 9})
    
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表4: 衰减效率柱状图
# ══════════════════════════════════════════════════════════════════

def create_attenuation_bar(comparison_data: Dict[str, Dict],
                           figsize: tuple = (10, 5.5)) -> Optional[Figure]:
    """
    生成衰减效率柱状图。
    
    Args:
        comparison_data: {指标名: {'exp': float, 'ctrl': float, 'atten_pct': float, ...}}
    """
    items = {}
    for key, val in comparison_data.items():
        if isinstance(val, dict) and 'atten_pct' in val:
            items[key[:18]] = val['atten_pct']
    
    if not items:
        return None
    
    labels = list(items.keys())
    values = list(items.values())
    bar_colors = [COLORS['green'] if v > 0 else COLORS['accent'] for v in values]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    bars = ax.barh(range(len(labels)), values, color=bar_colors,
                   edgecolor='white', height=0.6)
    
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9, fontfamily=CN_FONT_FAMILY)
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.axvline(x=10, color=COLORS['green'], linewidth=0.8, linestyle='--', alpha=0.4)
    ax.axvline(x=-10, color=COLORS['accent'], linewidth=0.8, linestyle='--', alpha=0.4)
    
    for bar, val in zip(bars, values):
        x_pos = bar.get_width() + (1.5 if val >= 0 else -1.5)
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f'{val:+.1f}%', va='center', fontsize=8,
                fontfamily=CN_FONT_FAMILY,
                ha='left' if val >= 0 else 'right',
                fontweight='bold')
    
    ax.set_xlabel('衰减率 (%)', fontsize=11, fontfamily=CN_FONT_FAMILY)
    ax.set_title('实验组 vs 对照组 — 各指标衰减效率',
                 fontsize=13, fontweight='bold', fontfamily=CN_FONT_FAMILY)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.2)
    
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表5: 三轴加速度时域波形
# ══════════════════════════════════════════════════════════════════

def create_acceleration_waveform(channel_data_map: Dict[str, Dict],
                                 imu_names: List[str] = None,
                                 figsize: tuple = (14, 8)) -> Optional[Figure]:
    """
    生成三轴加速度时域波形。
    
    Args:
        channel_data_map: {imu_name: {channel: numpy_array, 'rel_time': array}}
        imu_names: 要绘制的 IMU 名称列表
    """
    if imu_names is None:
        imu_names = [k for k in channel_data_map.keys()
                     if k.endswith('-1')][:3]
    
    if not imu_names:
        return None
    
    axes_keys = ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2']
    axis_labels = ['X轴 (纵向) m/s²', 'Y轴 (侧向) m/s²', 'Z轴 (垂向) m/s²']
    line_colors = [COLORS['accent'], COLORS['primary'], COLORS['green']]
    alphas = [0.85, 0.65, 0.5]
    
    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
    
    for row, (axis_key, ylabel, col) in enumerate(zip(axes_keys, axis_labels, line_colors)):
        ax = axes[row]
        for i, (imu_name, alpha) in enumerate(zip(imu_names, alphas)):
            data_dict = channel_data_map.get(imu_name, {})
            ch_data = data_dict.get(axis_key)
            if ch_data is None:
                continue
            t_arr = data_dict.get('rel_time', np.arange(len(ch_data)))
            if len(t_arr) != len(ch_data):
                t_arr = np.linspace(0, len(ch_data) / 512, len(ch_data))
            label = imu_name.replace('_', ' ').replace('-1', '')
            ax.plot(t_arr, ch_data, alpha=alpha, linewidth=0.8,
                    label=label, color=col)
        
        ax.set_ylabel(ylabel, fontsize=10, fontfamily=CN_FONT_FAMILY)
        ax.legend(loc='upper right', prop={'family': CN_FONT_FAMILY, 'size': 7}, ncol=3)
        ax.grid(True, alpha=0.2)
    
    axes[0].set_title('三轴加速度时域波形 (实验组)', fontsize=13,
                      fontweight='bold', fontfamily=CN_FONT_FAMILY)
    axes[-1].set_xlabel('时间 (s)', fontsize=11, fontfamily=CN_FONT_FAMILY)
    
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表6: SRS冲击响应谱对比
# ══════════════════════════════════════════════════════════════════

def create_srs_comparison(channel_data_map: Dict[str, Dict],
                          exp_imu: str, ctrl_imu: str,
                          location_name: str = "",
                          axis: str = 'X',
                          figsize: tuple = (10, 4.5)) -> Optional[Figure]:
    """
    生成 SRS 冲击响应谱对比。
    
    Args:
        channel_data_map: {imu_name: {channel: numpy_array}}
        exp_imu: 实验组 IMU 名称
        ctrl_imu: 对照组 IMU 名称
        location_name: 位置名称
        axis: 分析轴 ('X', 'Y', 'Z')
    """
    channel_key = f"A{axis.lower()}_m_s2"
    
    fig, ax = plt.subplots(figsize=figsize)
    
    for label, imu, ls in [('实验组', exp_imu, '-'), ('对照组', ctrl_imu, '--')]:
        data_dict = channel_data_map.get(imu, {})
        ch_data = data_dict.get(channel_key)
        if ch_data is None:
            continue
        
        if 'rel_time' in data_dict:
            t_arr = data_dict['rel_time']
            fs = 1.0 / np.median(np.diff(t_arr)) if len(t_arr) > 1 else 512
        else:
            fs = 512
        
        # 简化 SRS 计算 (小波叠加法)
        fn = np.logspace(np.log10(0.5), np.log10(100), 60)
        Q = 10
        zeta = 1 / (2 * Q)
        dt = 1 / fs
        
        srs = np.zeros(len(fn))
        acc = np.asarray(ch_data, dtype=np.float64)
        
        for i_f, f in enumerate(fn):
            wn = 2 * np.pi * f
            wd = wn * np.sqrt(1 - zeta ** 2)
            E_val = np.exp(-zeta * wn * dt)
            Ev = E_val * np.sin(wd * dt)
            Ec = E_val * np.cos(wd * dt)
            b1 = 2 * Ec
            b2 = -E_val ** 2
            a0 = 1 - wn * dt * E_val * wd ** (-1) * np.sqrt(1 - zeta ** 2) ** (-1) * Ev
            a1 = a0 - E_val * (Ev / (wd * dt) + Ec)
            r = np.zeros(len(acc))
            for j in range(2, len(acc)):
                r[j] = b1 * r[j-1] + b2 * r[j-2] + a0 * acc[j] + a1 * acc[j-1]
            srs[i_f] = np.max(np.abs(r))
        
        style = {'color': COLORS['exp'] if '实验' in label else COLORS['ctrl'],
                 'linestyle': ls, 'linewidth': 1.5}
        ax.loglog(fn, srs / 9.81, label=label, **style)
    
    ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax.set_ylabel('SRS (g)', fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax.set_title(f'{location_name} {axis}轴 冲击响应谱' if location_name
                 else f'{axis}轴 SRS冲击响应谱',
                 fontsize=11, fontfamily=CN_FONT_FAMILY)
    ax.legend(prop={'family': CN_FONT_FAMILY, 'size': 8})
    ax.grid(True, alpha=0.25, which='both')
    
    fig.suptitle(f'冲击响应谱(SRS)对比 — Q=10', fontsize=13,
                 fontweight='bold', fontfamily=CN_FONT_FAMILY)
    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════
# 衰减率判定文案
# ══════════════════════════════════════════════════════════════════

def verdict_text(atten_pct: float) -> str:
    """根据衰减率返回结论评级文案"""
    if atten_pct > 15:
        return '显著优于'
    elif atten_pct > 5:
        return '略优于'
    elif atten_pct > -5:
        return '无显著差异'
    elif atten_pct > -15:
        return '略差于'
    else:
        return '显著差于'

def verdict_icon(atten_pct: float) -> str:
    """返回对应图标"""
    if atten_pct > 15:
        return '\u2705'  # ✅
    elif atten_pct > 5:
        return '\u2714'   # ✔
    elif atten_pct > -5:
        return '\u2248'   # ≈
    elif atten_pct > -15:
        return '\u26A0'   # ⚠
    else:
        return '\u274C'   # ❌