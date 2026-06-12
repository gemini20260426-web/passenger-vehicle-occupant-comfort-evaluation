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

logger = logging.getLogger(__name__)

# 导入统一样式（必须在 COLOR/EVENT_COLORS 之前）
from .visualization_manager import ChartStyle, CN_FONT, CN_FONT_FAMILY, CN_FONT_LIST

# ── 配色方案（统一使用 ChartStyle Okabe-Ito 色盲友好配色）──
COLORS = {
    'primary':   ChartStyle.C_EXP,
    'secondary': '#1F3864',
    'accent':    ChartStyle.C_RED,
    'green':     ChartStyle.C_DIFF,
    'orange':    ChartStyle.C_CTRL,
    'purple':    ChartStyle.C_PURPLE,
    'exp':       ChartStyle.C_EXP,
    'ctrl':      ChartStyle.C_CTRL,
    'grey':      ChartStyle.C_NEUTRAL,
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

# ── 中文字体配置：复用 visualization_manager 统一检测结果 ──
# CN_FONT / CN_FONT_FAMILY / CN_FONT_LIST 由 visualization_manager 模块级导入

# ══════════════════════════════════════════════════════════════════
# 图表1: 驾驶事件时间线
# ══════════════════════════════════════════════════════════════════

def create_event_timeline(t: np.ndarray, speed: np.ndarray, wheel: np.ndarray,
                          events: List[Dict], title: str = "驾驶事件时间线",
                          figsize: tuple = (14, 6)):
    """生成驾驶事件时间线图（车速曲线 + 方向盘曲线 + 事件色块标注）

    对标参考图标准：2 行布局，清晰层次，事件色块限制在顶部 15% 区域。
    """
    if len(t) == 0 or len(speed) == 0:
        return None

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 2], hspace=0.12)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # ── 数据降采样：超过 3000 点时抽稀 ──
    n_raw = min(len(speed), len(wheel), len(t))
    MAX_POINTS = 3000
    ds_every = max(1, n_raw // MAX_POINTS) if n_raw > MAX_POINTS else 1
    if ds_every > 1:
        t = t[::ds_every]
        speed = speed[::ds_every]
        wheel = wheel[::ds_every]

    # ── 图标题（figure suptitle） ──
    fig.suptitle(title, fontsize=10, fontweight='bold',
                 fontfamily=CN_FONT_FAMILY, y=0.97)

    # ── 上车速曲线 ──
    vmax = max(float(np.nanmax(speed)), 1.0)
    ax1.plot(t, speed, color=COLORS['exp'], linewidth=1.8,
             solid_capstyle='round', alpha=0.95)
    ax1.fill_between(t, 0, speed, alpha=0.10, color=COLORS['exp'])
    ax1.set_ylabel('车速 (km/h)', fontsize=11, fontfamily=CN_FONT_FAMILY)
    ax1.grid(True, alpha=0.20, linestyle='-')
    ax1.set_ylim(bottom=0, top=vmax * 1.15)

    # ── 事件色块 + 标签（限制在顶部 15% 区域，最多 12 个标签） ──
    event_band_top = vmax * 0.90
    event_band_bottom = vmax * 0.72
    band_height = event_band_top - event_band_bottom
    events_sorted = sorted(events, key=lambda e: (e.get('t_start', e.get('start_time', 0))))

    for i, evt in enumerate(events_sorted):
        t0 = evt.get('t_start', evt.get('start_time', 0))
        t1 = evt.get('t_end', evt.get('end_time', t0 + 0.5))
        if t1 <= t0:
            t1 = t0 + 0.5
        etype = evt.get('event_type', evt.get('type', ''))
        ename = evt.get('event_name', evt.get('name', etype)) or etype or '事件'
        color = EVENT_COLORS.get(etype, COLORS['accent'])

        # 事件色块只画在事件带区域（不覆盖曲线）
        ax1.axvspan(t0, t1, ymin=event_band_bottom / ax1.get_ylim()[1],
                    ymax=event_band_top / ax1.get_ylim()[1],
                    alpha=0.25, color=color, linewidth=0)

        # 仅前 12 个事件加文字标签（避免拥挤）
        if i < 12:
            y_text = event_band_top + band_height * 0.10
            ax1.text((t0 + t1) / 2.0, y_text, ename,
                     ha='center', va='bottom',
                     fontsize=8, color=color,
                     fontfamily=CN_FONT_FAMILY,
                     bbox=dict(boxstyle='round,pad=0.15',
                               facecolor='white', edgecolor=color,
                               linewidth=0.5, alpha=0.85))

    # ── 下方向盘曲线 ──
    ax2.plot(t, wheel, color=COLORS['purple'], linewidth=1.5,
             solid_capstyle='round', alpha=0.95)
    ax2.fill_between(t, 0, wheel, alpha=0.08, color=COLORS['purple'])
    ax2.axhline(y=0, color='grey', linewidth=0.6, linestyle='--', alpha=0.6)
    ax2.set_xlabel('时间 (s)', fontsize=11, fontfamily=CN_FONT_FAMILY)
    ax2.set_ylabel('转角 (°)', fontsize=11, fontfamily=CN_FONT_FAMILY)
    ax2.grid(True, alpha=0.20, linestyle='-')

    # ── 布局：预留 suptitle 空间 ──
    fig.subplots_adjust(top=0.88, bottom=0.10, left=0.07, right=0.98)
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表2: PSD功率谱密度对比
# ══════════════════════════════════════════════════════════════════

def create_psd_comparison(channel_data_map: Dict[str, Dict],
                          exp_imus: List[str], ctrl_imus: List[str],
                          positions: List[tuple] = None,
                          axis: str = 'Z',
                          figsize: tuple = None):
    """生成 PSD 功率谱密度对比图（对标参考图标准）。

    布局：
      - axis='all'  → 3 行 × N 列（每行为一个轴 X/Y/Z，每列为一个位置）
      - axis='X'/'Y'/'Z' → 1 行 × N 列（单轴，多位置对比 — 最接近参考图）

    设计规范：统一蓝实线(实验组) / 橙虚线(对照组)，单图例在左上角，suptitle 与子图 title 双层结构。
    """
    from scipy import signal as sp_signal

    if positions is None:
        paired = []
        for exp_name in exp_imus[:3]:
            # 正确配对: 移除尾部 '-1' 后缀，在 ctrl_imus 中查找对应的 '-2' 通道
            if exp_name.endswith('-1'):
                base_name = exp_name[:-2]  # 移除末尾 '-1'
                # 在 ctrl_imus 中查找以 base_name 开头且以 '-2' 结尾的匹配项
                ctrl_name = None
                for ctrl in ctrl_imus:
                    if ctrl.endswith('-2') and ctrl[:-2] == base_name:
                        ctrl_name = ctrl
                        break
                # 备选: 按 IMU 编号 +1 匹配 (IMU1→IMU2, IMU3→IMU4, ...)
                if ctrl_name is None:
                    try:
                        imu_num = int(exp_name.split('_')[0].replace('IMU', ''))
                        ctrl_num = imu_num + 1
                        ctrl_prefix = f'IMU{ctrl_num}_'
                        for ctrl in ctrl_imus:
                            if ctrl.startswith(ctrl_prefix) and ctrl.endswith('-2'):
                                ctrl_name = ctrl
                                break
                    except (ValueError, IndexError):
                        pass
                location = exp_name.split('_')[1] if '_' in exp_name else exp_name
                paired.append((location, exp_name, ctrl_name))
            else:
                location = exp_name.split('_')[1] if '_' in exp_name else exp_name
                paired.append((location, exp_name, None))
        positions = paired

    valid_positions = [(loc, e, c) for loc, e, c in positions
                       if e in channel_data_map and c and c in channel_data_map]

    if len(valid_positions) < 1:
        return None

    n_pos = len(valid_positions)
    if axis == 'all':
        axes_list = ['X', 'Y', 'Z']
    else:
        axes_list = [axis.upper()]
    n_rows = len(axes_list)

    # ── 画布尺寸按网格算：每列 ~5 inch, 每行 ~3.2 inch ──
    if figsize is None:
        fig_w = max(10.0, min(18.0, 4.5 * n_pos))
        fig_h = max(4.5, 2.8 * n_rows + 1.2)
        figsize = (fig_w, fig_h)

    fig, axes_grid = plt.subplots(n_rows, n_pos, figsize=figsize,
                                  sharex='col', squeeze=False)

    # ── 统一频率范围 & 每一列的 PSD Y 轴对齐范围（便于横向比较）──
    ylim_buffer: Dict[int, List[float]] = {col: [np.inf, -np.inf] for col in range(n_pos)}

    line_style_map = {
        '实验组': {'color': COLORS['exp'], 'ls': '-', 'lw': 1.8},
        '对照组': {'color': COLORS['ctrl'], 'ls': '--', 'lw': 1.6},
    }

    for row, ax_name in enumerate(axes_list):
        ch_key = f"a{ax_name.lower()}"
        for col, (loc, exp_imu, ctrl_imu) in enumerate(valid_positions):
            ax = axes_grid[row, col]

            for label, imu in [('实验组', exp_imu), ('对照组', ctrl_imu)]:
                data_dict = channel_data_map.get(imu, {})
                ch_data = data_dict.get(ch_key)
                if ch_data is None or len(ch_data) < 256:
                    continue

                fs = data_dict.get('sample_rate', 0)
                if not fs and 'timestamps' in data_dict:
                    t_arr = data_dict['timestamps']
                    fs = 1.0 / np.median(np.diff(t_arr)) if len(t_arr) > 1 else 512
                if not fs:
                    fs = 512

                n_samp = len(ch_data)
                nperseg = min(1024, max(256, n_samp // 4))
                noverlap = nperseg // 2
                try:
                    f, pxx = sp_signal.welch(ch_data, fs, nperseg=nperseg,
                                             noverlap=noverlap, window='hann')
                    mask = (f >= 0.5) & (f <= 80)
                    y_db = 10.0 * np.log10(pxx[mask] + 1e-12)
                    ls = line_style_map[label]
                    # 只在 (0, 0) 画 legend 一次
                    lab = label if (row == 0 and col == 0) else None
                    ax.semilogx(f[mask], y_db, label=lab, color=ls['color'],
                               linestyle=ls['ls'], linewidth=ls['lw'])

                    # 追踪每列 Y 轴范围
                    lo, hi = float(np.nanmin(y_db)), float(np.nanmax(y_db))
                    ylim_buffer[col][0] = min(ylim_buffer[col][0], lo)
                    ylim_buffer[col][1] = max(ylim_buffer[col][1], hi)
                except Exception as e:
                    logger.debug(f"PSD计算失败 {imu} {ax_name}: {e}")

            # ── 子图标签：只在第 0 列加 ylabel，只在第 0 行加 title，只在末行加 xlabel ──
            if col == 0:
                ax.set_ylabel(f'{ax_name}轴 PSD (dB)',
                              fontsize=10, fontfamily=CN_FONT_FAMILY)
            if row == 0:
                ax.set_title(f'{loc} {ax_name}轴PSD' if n_rows == 1 else f'{loc}',
                            fontsize=10, fontweight='bold', fontfamily=CN_FONT_FAMILY)
            if row == n_rows - 1:
                ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT_FAMILY)
            ax.grid(True, alpha=0.20, linestyle='-')
            ax.tick_params(axis='both', labelsize=9)

    # ── 统一每列的 Y 轴范围（同位置 X/Y/Z 轴共用一个 Y 刻度范围便于比较）──
    for col in range(n_pos):
        lo, hi = ylim_buffer[col]
        if not np.isfinite(lo) or not np.isfinite(hi):
            continue
        pad = max(2.0, (hi - lo) * 0.08)
        for row in range(n_rows):
            axes_grid[row, col].set_ylim(lo - pad, hi + pad)

    # ── Figure suptitle ──
    if n_rows == 1:
        main_title = f'座椅各点位 {axes_list[0]}轴 功率谱密度对比'
    else:
        main_title = '座椅各点位 三轴功率谱密度对比'
    fig.suptitle(main_title, fontsize=10, fontweight='bold',
                     fontfamily=CN_FONT_FAMILY, y=1.0)

    # ── 单图例（只在左上角出现一次）──
    axes_grid[0, 0].legend(loc='upper right', frameon=True,
                          prop={'family': CN_FONT_FAMILY, 'size': 10})

    # ── 显式布局：预留 suptitle 空间，控制 wspace/hspace ──
    fig.subplots_adjust(top=0.87, bottom=0.12, left=0.07, right=0.98,
                        wspace=0.25, hspace=0.22)
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表3: 归一化雷达对比图
# ══════════════════════════════════════════════════════════════════

def create_comparison_radar(comparison_data: Dict[str, Dict],
                            figsize: tuple = None):
    """生成归一化雷达对比图（对标参考图标准）。

    选择策略：按 |atten_pct| 从大到小排序，截取最显著的前 8 个指标。
    对照组作为 r=1 的正八边形基准线，实验组为其归一化值。
    """
    # ── 1. 提取并筛选标量指标 ──
    candidates = []
    for key, val in comparison_data.items():
        if not (isinstance(val, dict) and 'exp' in val and 'ctrl' in val):
            continue
        e, c = float(val['exp']), float(val['ctrl'])
        if abs(c) < 1e-9:
            continue
        atten = val.get('atten_pct', (e - c) / abs(c) * 100)
        ratio = e / c
        if not np.isfinite(ratio):
            continue
        candidates.append((key, ratio, float(atten)))

    if len(candidates) < 3:
        return None

    # ── 2. 选择最显著的 TOP 8（控制标签密度）──
    candidates_sorted = sorted(candidates, key=lambda x: abs(x[2]), reverse=True)[:8]
    labels_raw = [c[0] for c in candidates_sorted]
    exp_ratios = [c[1] for c in candidates_sorted]
    n = len(labels_raw)

    # 标签截断至 ~8 汉字（保持可读性）
    labels = [l[:8] for l in labels_raw]

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    angles_close = np.concatenate([angles, [angles[0]]])
    exp_close = np.array(exp_ratios + [exp_ratios[0]])
    ctrl_close = np.array([1.0] * (n + 1))

    # ── 3. 画布尺寸 ──
    if figsize is None:
        side = max(5.5, min(7.5, 5.0 + n * 0.2))
        figsize = (side, side)

    fig, ax = plt.subplots(figsize=figsize, subplot_kw={'projection': 'polar'})

    # ── 4. 绘制两条闭合多边形 ──
    ax.fill(angles_close, exp_close, alpha=0.18, color=COLORS['exp'], edgecolor=None)
    ax.plot(angles_close, exp_close, color=COLORS['exp'], linewidth=2.2,
            marker='o', markersize=7, label='实验组')

    ax.fill(angles_close, ctrl_close, alpha=0.10, color=COLORS['ctrl'], edgecolor=None)
    ax.plot(angles_close, ctrl_close, color=COLORS['ctrl'], linewidth=1.8,
            linestyle='--', marker='s', markersize=5, label='对照组 (基准=1.0)')

    # ── 5. 坐标轴与标签 ──
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10, fontfamily=CN_FONT_FAMILY)
    # 径向范围：数据波动 ± 10%
    rmin = max(0.2, float(np.nanmin(exp_ratios)) * 0.85)
    rmax = min(3.0, float(np.nanmax(exp_ratios)) * 1.15)
    if rmax <= rmin:
        rmax = rmin + 1.0
    ax.set_rlim(rmin, rmax)
    ax.set_yticklabels([])  # 隐藏径向刻度文字，保持参考图简洁风格
    ax.grid(True, alpha=0.25)

    # ── 6. 标题与图例 ──
    fig.suptitle('实验组 vs 对照组 — 归一化对比 (对照组=1.0)',
                 fontsize=10, fontweight='bold', fontfamily=CN_FONT_FAMILY, y=0.97)

    ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1),
              frameon=True, prop={'family': CN_FONT_FAMILY, 'size': 10})

    fig.subplots_adjust(top=0.88, bottom=0.10, left=0.08, right=0.92)
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表4: 衰减效率柱状图
# ══════════════════════════════════════════════════════════════════

def create_attenuation_bar(comparison_data: Dict[str, Dict],
                           figsize: tuple = None):
    """生成衰减效率柱状图（对标参考图标准）。

    策略：
      1. 按 |atten_pct| 从大到小排序，截取最显著的 TOP 15
      2. 从顶部向下排列（最大绝对值在最上面），符合阅读习惯
      3. 正值=绿色=实验组更优；负值=红色=对照组更优
      4. 数值标注放在条形末端，避免溢出
    """
    # ── 1. 提取并筛选 ──
    items_raw = []
    for key, val in comparison_data.items():
        if isinstance(val, dict) and 'atten_pct' in val:
            v = float(val['atten_pct'])
            if np.isfinite(v):
                items_raw.append((key, v))

    if not items_raw:
        return None

    # ── 2. 排序 + TOP 15 截断 ──
    items_raw.sort(key=lambda x: abs(x[1]), reverse=True)
    items_raw = items_raw[:15]
    # 再按数值本身排序，把最大正值放在顶部（默认 matplotlib barh 0 从底部，invert_yaxis 后 0 到顶部）
    items_raw.sort(key=lambda x: x[1])  # 从小到大（底部为最小，顶部为最大）

    labels = [k[:18] for k, _ in items_raw]
    values = [v for _, v in items_raw]
    n = len(values)

    bar_colors = []
    for v in values:
        bar_colors.append(COLORS['green'] if v >= 0 else COLORS['accent'])

    # ── 3. 画布尺寸：每条 ~0.35 inch + 头部 1.2 inch ──
    if figsize is None:
        w = max(10.0, min(14.0, 8.0 + max(abs(v) for v in values) * 0.04))
        h = max(5.0, min(9.0, 2.5 + n * 0.38))
        figsize = (w, h)

    fig, ax = plt.subplots(figsize=figsize)

    bars = ax.barh(range(n), values, color=bar_colors,
                   edgecolor='white', linewidth=0.8, height=0.65)

    # ── 4. 坐标轴 ──
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=10, fontfamily=CN_FONT_FAMILY)
    ax.axvline(x=0, color='#333333', linewidth=1.0)
    ax.set_xlabel('衰减率 (%)', fontsize=12, fontfamily=CN_FONT_FAMILY)

    # ── 5. 数值标注（条形末端）──
    vrange = max(abs(max(values)), abs(min(values)))
    label_offset = vrange * 0.025 if vrange > 0 else 1.0
    for bar, val in zip(bars, values):
        if val >= 0:
            x_pos = val + label_offset
            ha = 'left'
        else:
            x_pos = val - label_offset
            ha = 'right'
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f'{val:+.1f}%', va='center', ha=ha,
                fontsize=9, fontfamily=CN_FONT_FAMILY, fontweight='bold')

    # ── 6. 标题（figure suptitle）与图例 ──
    fig.suptitle('实验组 vs 对照组 — 各指标衰减效率',
                 fontsize=10, fontweight='bold',
                 fontfamily=CN_FONT_FAMILY, y=0.97)

    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.20, linestyle='-')

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['green'], label='实验组更优 (衰减率 > 0)'),
        Patch(facecolor=COLORS['accent'], label='对照组更优 (衰减率 < 0)'),
    ]
    ax.legend(handles=legend_elements, loc='lower right',
              prop={'family': CN_FONT_FAMILY, 'size': 10})

    fig.subplots_adjust(top=0.89, bottom=0.10, left=0.22, right=0.96)
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表5: 三轴加速度时域波形
# ══════════════════════════════════════════════════════════════════

def create_acceleration_waveform(channel_data_map: Dict[str, Dict],
                                 imu_names: List[str] = None,
                                 figsize: tuple = None):
    """生成三轴加速度时域波形（对标参考图标准）。

    关键改进：每个 IMU 使用**不同的颜色**（不是同一颜色+不同透明度），
    这样 3 条曲线可以被明确区分。布局为 3 行 × 1 列（X/Y/Z 轴）。
    """
    if imu_names is None:
        imu_names = [k for k in channel_data_map.keys()
                     if k.endswith('-1')][:3]

    if not imu_names:
        return None

    # ── 每个 IMU 分配一个独立的、高对比的颜色 ──
    imu_colors = [COLORS['exp'], COLORS['ctrl'], COLORS['purple']]
    imu_display_names = []
    for name in imu_names:
        imu_display_names.append(name.replace('_', ' ').replace('-1', ''))

    axes_keys = ['ax', 'ay', 'az']
    axis_labels = ['X轴 (纵向) m/s$^2$', 'Y轴 (侧向) m/s$^2$', 'Z轴 (垂向) m/s$^2$']

    # ── 画布尺寸 ──
    if figsize is None:
        figsize = (15.0, 7.5)

    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)

    # ── 收集所有子图的有效时间轴 ──
    global_t = None
    for row, (axis_key, ylabel) in enumerate(zip(axes_keys, axis_labels)):
        ax = axes[row]
        plotted = False
        for i, (imu_name, color, display) in enumerate(
                zip(imu_names, imu_colors, imu_display_names)):
            data_dict = channel_data_map.get(imu_name, {})
            ch_data = data_dict.get(axis_key)
            if ch_data is None or len(ch_data) == 0:
                continue
            t_arr = data_dict.get('timestamps',
                                   np.arange(len(ch_data)) / data_dict.get('sample_rate', 512))
            if len(t_arr) != len(ch_data):
                t_arr = np.linspace(0, len(ch_data) / 512.0, len(ch_data))
            # 降采样：超过 2 万点时抽稀（保持视觉清晰度）
            max_points = 20000
            if len(ch_data) > max_points:
                step = len(ch_data) // max_points
                t_arr = t_arr[::step]
                ch_data = ch_data[::step]

            ax.plot(t_arr, ch_data, color=color, linewidth=1.2,
                    label=display, alpha=0.92, solid_capstyle='round')
            plotted = True
            if global_t is None and len(t_arr) > 0:
                global_t = t_arr

        ax.set_ylabel(ylabel, fontsize=10, fontfamily=CN_FONT_FAMILY)
        ax.grid(True, alpha=0.20, linestyle='-')
        ax.tick_params(axis='both', labelsize=9)

    # ── 标题与图例 ──
    fig.suptitle('三轴加速度时域波形 (实验组)', fontsize=10,
                 fontweight='bold', fontfamily=CN_FONT_FAMILY, y=0.97)

    axes[-1].set_xlabel('时间 (s)', fontsize=11, fontfamily=CN_FONT_FAMILY)

    # 图例放在顶部，避免遮挡曲线
    axes[0].legend(loc='upper right', frameon=True, ncol=min(len(imu_names), 3),
                   prop={'family': CN_FONT_FAMILY, 'size': 10})

    fig.subplots_adjust(top=0.88, bottom=0.08, left=0.06, right=0.98, hspace=0.15)
    return fig


# ══════════════════════════════════════════════════════════════════
# 图表6: SRS冲击响应谱对比
# ══════════════════════════════════════════════════════════════════

def create_srs_comparison(channel_data_map: Dict[str, Dict],
                          exp_imu: str, ctrl_imu: str,
                          location_name: str = "",
                          axis: str = 'X',
                          figsize: tuple = None):
    """生成 SRS 冲击响应谱对比（对标参考图标准）。

    布局：
      - axis='all' → 1 行 × 3 列（X/Y/Z 三列，同参考图 PSD 风格
      - 单轴 → 1 行 × 1 列

    使用 scipy.signal.lfilter 向量化递归计算。
    """
    from scipy.signal import lfilter

    # ── 1. 轴列表 ──
    if axis == 'all':
        axes_list = ['X', 'Y', 'Z']
    else:
        axes_list = [axis.upper()]
    n_axes = len(axes_list)

    # ── 2. 画布尺寸 ──
    if figsize is None:
        if n_axes == 1:
            figsize = (10.0, 4.5)
        else:
            figsize = (16.0, 5.0)

    fig, axes_arr = plt.subplots(1, n_axes, figsize=figsize, squeeze=False)
    axes_arr = axes_arr[0]  # 展开成一维，1 行

    # ── 3. 固定参数 ──
    fn = np.logspace(np.log10(0.5), np.log10(100.0), 60)
    Q = 10
    zeta = 1.0 / (2.0 * Q)

    # ── 4. 逐轴计算与绘制 ──
    line_styles = {
        '实验组': {'color': COLORS['exp'], 'ls': '-', 'lw': 1.8},
        '对照组': {'color': COLORS['ctrl'], 'ls': '--', 'lw': 1.6},
    }

    for col, ax_name in enumerate(axes_list):
        ax = axes_arr[col]
        channel_key = f"a{ax_name.lower()}"

        for label, imu in [('实验组', exp_imu), ('对照组', ctrl_imu)]:
            data_dict = channel_data_map.get(imu, {})
            ch_data = data_dict.get(channel_key)
            if ch_data is None or len(ch_data) == 0:
                continue

            fs = data_dict.get('sample_rate', 0)
            if not fs and 'timestamps' in data_dict:
                t_arr = data_dict['timestamps']
                fs = 1.0 / np.median(np.diff(t_arr)) if len(t_arr) > 1 else 512
            if not fs:
                fs = 512

            dt = 1.0 / fs
            acc = np.asarray(ch_data, dtype=np.float64)
            srs = np.zeros(len(fn))

            for i_f, f in enumerate(fn):
                wn = 2.0 * np.pi * f
                wd = wn * np.sqrt(1.0 - zeta ** 2)
                E = np.exp(-zeta * wn * dt)
                a_coeff = [1.0, -2.0 * E * np.cos(wd * dt), E * E]
                A_val = 1.0 - wn * dt
                B_val = wn * dt * E * np.sin(wd * dt) / wd
                b_coeff = [A_val * B_val, A_val * (E * np.cos(wd * dt) - 1.0) - B_val]
                filtered = lfilter(b_coeff, a_coeff, acc)
                srs[i_f] = np.max(np.abs(filtered))

            ls = line_styles[label]
            lab = label if col == 0 else None  # 只在第 1 个轴加 legend
            ax.loglog(fn, srs / 9.81, color=ls['color'],
                      linestyle=ls['ls'], linewidth=ls['lw'],
                      label=lab)

        ax.set_title(f'{ax_name}轴 SRS', fontsize=10, fontweight='bold', fontfamily=CN_FONT_FAMILY)
        ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT_FAMILY)
        if col == 0:
            ax.set_ylabel(f'SRS (g)', fontsize=10, fontfamily=CN_FONT_FAMILY)
        ax.grid(True, alpha=0.20, linestyle='-')
        ax.tick_params(axis='both', labelsize=9)
        if col == 0:
            ax.legend(loc='upper right', frameon=True,
                     prop={'family': CN_FONT_FAMILY, 'size': 10})

    # ── 5. Figure 标题 ──
    title = f'冲击响应谱(SRS)对比 — Q=10'
    if location_name:
        title += f'  |  {location_name}'
    fig.suptitle(title, fontsize=10, fontweight='bold',
                 fontfamily=CN_FONT_FAMILY, y=0.98)

    fig.subplots_adjust(top=0.88, bottom=0.12, left=0.07, right=0.98, wspace=0.28)
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