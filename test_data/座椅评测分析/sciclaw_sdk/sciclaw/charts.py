"""
SciClaw 专业图表生成器
======================
提供出版物质量的科学图表，含中文字体支持。
"""

import os, numpy as np
from typing import Dict
import matplotlib
matplotlib.use('Agg')  # 无头模式
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.font_manager import FontProperties

# ============================================================
# 中文字体配置
# ============================================================

def _setup_chinese_font():
    """配置中文字体"""
    font_candidates = [
        'SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei',
        'Noto Sans CJK SC', 'Noto Sans SC', 'Source Han Sans CN',
        'Arial Unicode MS', 'DejaVu Sans',
    ]
    for font_name in font_candidates:
        try:
            fp = FontProperties(family=font_name)
            return font_name
        except:
            continue
    return 'sans-serif'

CN_FONT = _setup_chinese_font()

# SciClaw 配色方案 (专业实验室风格)
COLORS = {
    'primary':   '#2E75B6',  # 深蓝
    'secondary': '#1F3864',  # 海军蓝
    'accent':    '#E74C3C',  # 红
    'green':     '#27AE60',  # 绿
    'orange':    '#F39C12',  # 橙
    'purple':    '#8E44AD',  # 紫
    'exp':       '#2E75B6',  # 实验组色
    'ctrl':      '#E67E22',  # 对照组色
    'grey':      '#95A5A6',
}

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': [CN_FONT, 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'figure.dpi': 150,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'axes.spines.top': False,
    'axes.spines.right': False,
})


# ============================================================
# 图表1: 驾驶事件时间线
# ============================================================

def plot_event_timeline(df, events, output_path: str):
    """驾驶事件时间线图"""
    ref = df[(df['channel']=='ch1')&(df['imu_name'].str.contains('IMU1'))].sort_values('rel_time')
    t = ref['rel_time'].values
    speed = ref['speed'].values

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 5), sharex=True,
                                     gridspec_kw={'height_ratios': [2, 1]})

    # 上车速曲线
    ax1.plot(t, speed, color=COLORS['primary'], linewidth=1.5, label='车速')
    ax1.fill_between(t, 0, speed, alpha=0.1, color=COLORS['primary'])
    ax1.set_ylabel('车速 (km/h)', fontsize=11, fontfamily=CN_FONT)

    # 标注事件
    y_pos = ax1.get_ylim()[1] * 0.9
    event_colors = {
        'hard_brake': '#E74C3C', 'aggressive_accel': '#F39C12',
        'aggressive_decel': '#E74C3C', 'slalom': '#8E44AD',
        'left_turn': '#3498DB', 'right_turn': '#3498DB',
        'cruising': '#27AE60', 'stopped': '#95A5A6',
        'parked': '#7F8C8D',
    }

    for e in events:
        c = event_colors.get(e.event_type, '#3498DB')
        ax1.axvspan(e.t_start, e.t_end, alpha=0.15, color=c)
        ax1.annotate(e.event_name, ((e.t_start+e.t_end)/2, y_pos-y_pos*0.15*len(ax1.patches)%3),
                     fontsize=7, ha='center', color=c, fontfamily=CN_FONT,
                     rotation=45)

    ax1.legend(loc='upper right', prop=FontProperties(family=CN_FONT, size=8))
    ax1.set_title('驾驶事件时间线', fontsize=13, fontweight='bold', fontfamily=CN_FONT)

    # 下方向盘
    wheel = ref['wheel'].values
    ax2.plot(t, wheel, color=COLORS['purple'], linewidth=1)
    ax2.fill_between(t, 0, wheel, alpha=0.1, color=COLORS['purple'])
    ax2.axhline(y=0, color='grey', linewidth=0.5, linestyle='--')
    ax2.set_xlabel('时间 (s)', fontsize=11, fontfamily=CN_FONT)
    ax2.set_ylabel('转角 (°)', fontsize=11, fontfamily=CN_FONT)

    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# ============================================================
# 图表2: 实验组vs对照组对比雷达图
# ============================================================

def plot_comparison_radar(comparison: dict, output_path: str):
    """实验组vs对照组雷达对比图"""
    # 提取可对比的标量指标
    items = {}
    for key, val in comparison.items():
        if isinstance(val, dict) and 'exp' in val and 'ctrl' in val:
            items[key] = val

    if len(items) < 3:
        return

    labels = list(items.keys())
    exp_vals = [items[k]['exp'] for k in labels]
    ctrl_vals = [items[k]['ctrl'] for k in labels]

    # 归一化 (以对照组为基准)
    norm_exp = []
    norm_ctrl = []
    norm_labels = []
    for i, (e, c) in enumerate(zip(exp_vals, ctrl_vals)):
        if abs(c) > 1e-9:
            norm_exp.append(e / c)
            norm_ctrl.append(1.0)
            norm_labels.append(labels[i][:8])

    if len(norm_labels) < 3:
        return

    angles = np.linspace(0, 2*np.pi, len(norm_labels), endpoint=False).tolist()
    norm_exp.append(norm_exp[0])
    norm_ctrl.append(norm_ctrl[0])
    angles.append(angles[0])

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={'projection': 'polar'})

    ax.fill(angles, norm_exp, alpha=0.25, color=COLORS['exp'], label='实验组(GQY魔椅)')
    ax.plot(angles, norm_exp, color=COLORS['exp'], linewidth=2, marker='o', markersize=6)
    ax.fill(angles, norm_ctrl, alpha=0.15, color=COLORS['ctrl'], label='对照组(传统座椅)')
    ax.plot(angles, norm_ctrl, color=COLORS['ctrl'], linewidth=2, marker='s', markersize=6)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(norm_labels, fontsize=9, fontfamily=CN_FONT)
    ax.set_yticklabels([])
    ax.set_title('实验组 vs 对照组 — 归一化对比 (对照组=1.0)',
                 fontsize=13, fontweight='bold', fontfamily=CN_FONT, pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1),
              prop=FontProperties(family=CN_FONT, size=9))

    plt.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return output_path


# ============================================================
# 图表3: PSD功率谱密度对比
# ============================================================

def plot_psd_comparison(df, output_path: str):
    """实验组vs对照组 PSD功率谱对比"""
    from scipy import signal

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    seat_imus = {
        '头部眉心': ('IMU1_头部眉心-1', 'IMU2_头部眉心-2'),
        '座垫R点':  ('IMU5_座垫R点-1', 'IMU6_座垫R点-2'),
        '座椅底部': ('IMU7_座椅底部-1', 'IMU8_座椅底部-2'),
    }

    for ax, (location, (exp_name, ctrl_name)) in zip(axes, seat_imus.items()):
        for label, imu, style in [('实验组', exp_name, {'color': COLORS['exp'], 'ls':'-'}),
                                    ('对照组', ctrl_name, {'color': COLORS['ctrl'], 'ls':'-'})]:
            d = df[df['imu_name'] == imu].sort_values('rel_time')
            if len(d) < 100:
                continue
            t = d['rel_time'].values
            fs = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 512
            az = d['Az_m_s2'].values

            f, pxx = signal.welch(az, fs, nperseg=min(1024, len(az)//2),
                                  noverlap=min(512, len(az)//4), window='hann')
            mask = (f >= 0.5) & (f <= 80)
            ax.semilogx(f[mask], 10*np.log10(pxx[mask]+1e-12),
                       label=label, linewidth=1.5, **style)

        ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT)
        ax.set_ylabel('PSD (dB)', fontsize=10, fontfamily=CN_FONT)
        ax.set_title(f'{location} Z轴PSD', fontsize=11, fontfamily=CN_FONT)
        ax.legend(prop=FontProperties(family=CN_FONT, size=8))
        ax.grid(True, alpha=0.3)

    plt.suptitle('座椅各点位 Z轴功率谱密度对比', fontsize=14, fontweight='bold',
                 fontfamily=CN_FONT, y=1.02)
    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# ============================================================
# 图表4: 衰减效率柱状图
# ============================================================

def plot_attenuation_bar(comparison: dict, output_path: str):
    """衰减效率柱状图"""
    items = {}
    for key, val in comparison.items():
        if isinstance(val, dict) and 'atten_pct' in val:
            items[key] = val['atten_pct']

    if not items:
        return

    labels = list(items.keys())
    values = list(items.values())
    colors = [COLORS['green'] if v > 0 else COLORS['accent'] for v in values]

    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.barh(range(len(labels)), values, color=colors, edgecolor='white',
                   height=0.6)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels([f"{l[:15]}" for l in labels], fontsize=9, fontfamily=CN_FONT)
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.axvline(x=20, color=COLORS['green'], linewidth=0.8, linestyle='--', alpha=0.5)
    ax.axvline(x=-20, color=COLORS['accent'], linewidth=0.8, linestyle='--', alpha=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + (2 if val >= 0 else -2),
                bar.get_y() + bar.get_height()/2,
                f'{val:+.1f}%', va='center',
                fontsize=8, fontfamily=CN_FONT,
                ha='left' if val >= 0 else 'right')

    ax.set_xlabel('衰减率 (%)', fontsize=11, fontfamily=CN_FONT)
    ax.set_title('实验组 vs 对照组 — 各指标衰减效率',
                 fontsize=13, fontweight='bold', fontfamily=CN_FONT)
    ax.invert_yaxis()

    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# ============================================================
# 图表5: 时域加速度波形
# ============================================================

def plot_acceleration_waveform(df, output_path: str):
    """三轴加速度时域波形"""
    imu_names = ['IMU1_头部眉心-1', 'IMU5_座垫R点-1', 'IMU7_座椅底部-1']
    axes_names = ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2']
    axis_labels = ['X轴 (纵向) m/s²', 'Y轴 (侧向) m/s²', 'Z轴 (垂向) m/s²']
    colors = [COLORS['accent'], COLORS['primary'], COLORS['green']]
    alphas = [0.9, 0.7, 0.5]

    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    for row, (axis, ylabel, col) in enumerate(zip(axes_names, axis_labels, colors)):
        for i, (imu, alpha) in enumerate(zip(imu_names, alphas)):
            d = df[df['imu_name'] == imu].sort_values('rel_time')
            if len(d) < 10:
                continue
            t = d['rel_time'].values
            v = d[axis].values
            label = imu.replace('_',' ').replace('-1','')
            axes[row].plot(t, v, alpha=alpha, linewidth=0.8,
                          label=label, color=col)

        axes[row].set_ylabel(ylabel, fontsize=10, fontfamily=CN_FONT)
        axes[row].legend(loc='upper right', prop=FontProperties(family=CN_FONT, size=7),
                        ncol=3, fontsize=7)

    axes[0].set_title('三轴加速度时域波形 (实验组)', fontsize=13,
                     fontweight='bold', fontfamily=CN_FONT)
    axes[-1].set_xlabel('时间 (s)', fontsize=11, fontfamily=CN_FONT)

    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# ============================================================
# 图表6: SRS冲击响应谱对比
# ============================================================

def plot_srs_comparison(df, output_path: str):
    """SRS冲击响应谱对比"""
    from scipy import signal as sp_signal

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    imu_pairs = [
        ('头部眉心', 'IMU1_头部眉心-1', 'IMU2_头部眉心-2'),
        ('座垫R点', 'IMU5_座垫R点-1', 'IMU6_座垫R点-2'),
    ]

    for ax, (name, exp_n, ctrl_n) in zip(axes, imu_pairs):
        for label, imu, ls in [('实验组', exp_n, '-'), ('对照组', ctrl_n, '--')]:
            d = df[df['imu_name'] == imu].sort_values('rel_time')
            if len(d) < 100:
                continue
            t = d['rel_time'].values
            fs = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 512
            ax_val = d['Ax_m_s2'].values  # X轴 (制动方向)

            # 简化SRS
            fn = np.logspace(np.log10(0.5), np.log10(100), 60)
            Q = 10; zeta = 1/(2*Q); dt = 1/fs
            srs = np.zeros(len(fn))
            for i, f in enumerate(fn):
                wn = 2*np.pi*f; wd = wn*np.sqrt(1-zeta**2)
                E = np.exp(-zeta*wn*dt)
                Ev = E*np.sin(wd*dt); Ec = E*np.cos(wd*dt)
                b1, b2 = 2*Ec, -E**2
                a0 = 1 - wn*dt*E*wd**-1*np.sqrt(1-zeta**2)**-1*Ev
                a1 = a0 - E*(Ev/(wd*dt)+Ec)
                r = np.zeros(len(ax_val))
                for j in range(2, len(ax_val)):
                    r[j] = b1*r[j-1]+b2*r[j-2]+a0*ax_val[j]+a1*ax_val[j-1]
                srs[i] = np.max(np.abs(r))

            style = {'color': COLORS['exp'] if '实验' in label else COLORS['ctrl'],
                     'linestyle': ls, 'linewidth': 1.5}
            ax.loglog(fn, srs/9.81, label=label, **style)

        ax.set_xlabel('频率 (Hz)', fontsize=10, fontfamily=CN_FONT)
        ax.set_ylabel('SRS (g)', fontsize=10, fontfamily=CN_FONT)
        ax.set_title(f'{name} X轴冲击响应谱', fontsize=11, fontfamily=CN_FONT)
        ax.legend(prop=FontProperties(family=CN_FONT, size=8))
        ax.grid(True, alpha=0.3, which='both')

    plt.suptitle('冲击响应谱(SRS)对比 — AEB制动方向 Q=10',
                 fontsize=13, fontweight='bold', fontfamily=CN_FONT)
    plt.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# ============================================================
# 统一生成入口
# ============================================================

def generate_all(df, events, comparison, output_dir: str) -> Dict[str, str]:
    """生成全部图表，返回路径字典"""
    os.makedirs(output_dir, exist_ok=True)
    charts = {}

    generators = [
        ('01_event_timeline.png',     plot_event_timeline,       [df, events]),
        ('02_acceleration_waveform.png', plot_acceleration_waveform, [df]),
        ('03_psd_comparison.png',     plot_psd_comparison,       [df]),
        ('04_srs_comparison.png',     plot_srs_comparison,       [df]),
        ('05_comparison_radar.png',   plot_comparison_radar,     [comparison]),
        ('06_attenuation_bar.png',    plot_attenuation_bar,      [comparison]),
    ]

    for filename, func, args in generators:
        try:
            path = os.path.join(output_dir, filename)
            func(*args, path)
            charts[filename.replace('.png','')] = path
        except Exception as e:
            print(f"  图表 {filename} 生成失败: {e}")

    return charts


def generate_from_dict(data: dict, output_dir: str) -> Dict[str, str]:
    """从字典数据生成简化图表"""
    return {}  # 字典模式暂不支持完整图表
