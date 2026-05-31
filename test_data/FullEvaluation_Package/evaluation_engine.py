#!/usr/bin/env python3
"""
=============================================================================
 主动控制座椅悬架 — 乘员头部运动响应 全维度评测引擎
 Evaluation Engine v2.0

 功能:
   1. 数据加载与自动验证 (传感器映射、采样率、同步检查)
   2. 事件检测 (制动/加速/转向/冲击)
   3. 全时域连续滑动窗口分析
   4. 事件级精细化对比 (实验组vs对照组)
   5. 频谱分析 (Welch PSD + 频段衰减 + 相干性)
   6. 时频分析 (短时傅里叶变换 STFT)
   7. 统计学分析 (t检验/效应量/置信区间)
   8. 综合评价指标 (VDV/SEAT等效/Crest Factor/传递系数)
   9. V4.05手册指标对照
  10. 自动生成评测报告 (Markdown + CSV + PNG)

 输入: parsed_data CSV (rel_time, channel, imu_name, Ax..Az, Gx..Gz, speed, wheel)
 输出: 评测报告包 (report.md + 图表 + 统计表)

 传感器映射: 奇数IMU=实验组(主动座椅), 偶数IMU=对照组(被动座椅)
=============================================================================
"""

import pandas as pd
import numpy as np
from scipy import signal, stats, fft
from scipy.fft import fft, fftfreq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.colors as mcolors
import warnings, os, sys, json
from datetime import datetime
from io import StringIO

warnings.filterwarnings('ignore')
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'savefig.dpi': 150,
                      'axes.grid': True, 'grid.alpha': 0.3})

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    'fs': 1000,                       # 采样率 Hz
    'window_sec': 1.0,                # 滑动窗口 秒
    'step_sec': 0.5,                  # 滑动步长 秒
    'nfft_welch': 8192,               # Welch PSD FFT点数
    'nfft_stft': 512,                 # STFT FFT点数
    'stft_overlap': 384,              # STFT重叠
    'ds_brake_thresh': -2,            # 制动检测阈值 km/h/s
    'ds_accel_thresh': 3,             # 加速检测阈值 km/h/s
    'dw_steer_thresh': 3,             # 转向检测阈值 deg/s
    'da_shock_thresh': 0.5,           # 冲击检测阈值 m/s²
    'freq_bands': {                   # 频段划分
        'sub_low': (0.1, 0.5),
        'low': (0.5, 1.0),
        'mid_low': (1.0, 5.0),
        'mid_high': (5.0, 20.0),
        'high': (20.0, 80.0),
        '0.1-0.5Hz': (0.1, 0.5),
        '0.5-1Hz': (0.5, 1.0),
        '1-5Hz': (1.0, 5.0),
        '5-20Hz': (5.0, 20.0),
        '20-80Hz': (20.0, 80.0),
    },
}

# ============================================================
# CLASS: OccupantMotionEvaluator
# ============================================================
class OccupantMotionEvaluator:
    """乘员运动响应全维度评测器"""

    def __init__(self, csv_path, config=None):
        self.path = csv_path
        self.cfg = config or CONFIG
        self.df_raw = None
        self.df_clean = None
        self.fs = self.cfg['fs']
        self.common_t = None
        self.exp = {}   # 实验组 IMUx-1
        self.ctrl = {}  # 对照组 IMUx-2
        self.sw = None  # speed/wheel
        self.events = []
        self.results = {}  # 各级分析结果缓存

    # ---------- 1. DATA LOADING ----------
    def load(self):
        """加载并自动验证传感器映射"""
        print("[1/10] 数据加载...")
        self.df_raw = pd.read_csv(self.path)
        print(f"  原始数据: {len(self.df_raw)}行 × {len(self.df_raw.columns)}列")

        # 传感器清单
        imus = self.df_raw['imu_name'].unique()
        print(f"  IMU传感器: {len(imus)}个")
        for im in sorted(imus):
            num = int(im.split('_')[0].replace('IMU', ''))
            grp = '实验组(主动)' if num % 2 == 1 else '对照组(被动)'
            n = len(self.df_raw[self.df_raw['imu_name'] == im])
            body = im.split('_')[1] if '_' in im else '?'
            print(f"    IMU{num:>2d} [{grp:>12s}] {body:>12s} → {n:>6d}行")

        # 构建实验/对照数据字典
        for im in imus:
            sub = self.df_raw[self.df_raw['imu_name'] == im].sort_values('rel_time')
            vals = sub[['rel_time', 'Ax_m_s2', 'Ay_m_s2', 'Az_m_s2',
                         'Gx_dps', 'Gy_dps', 'Gz_dps',
                         'Gx_rad_s', 'Gy_rad_s', 'Gz_rad_s']].values
            num = int(im.split('_')[0].replace('IMU', ''))
            if num % 2 == 1:
                self.exp[im] = vals
            else:
                self.ctrl[im] = vals

        # 对齐公共时间基准
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if exp_keys and ctrl_keys:
            t_exp = set(round(t, 4) for t in self.exp[exp_keys[0]][:, 0])
            t_ctrl = set(round(t, 4) for t in self.ctrl[ctrl_keys[0]][:, 0])
            self.common_t = sorted(t_exp & t_ctrl)
            self.fs = 1.0 / (self.common_t[1] - self.common_t[0]) if len(self.common_t) > 1 else self.cfg['fs']
            print(f"  对齐时间: {len(self.common_t)}点, fs≈{self.fs:.0f}Hz, {self.common_t[-1]-self.common_t[0]:.1f}s")
        else:
            print("  ⚠️ 缺少实验组或对照组!")

        # Speed/Wheel
        sw_sub = self.df_raw[self.df_raw['channel'] == 'ch1'].drop_duplicates('rel_time').sort_values('rel_time')
        self.sw = []
        for t in self.common_t:
            match = sw_sub[abs(sw_sub['rel_time'] - t) < 1e-3]
            if len(match) > 0:
                self.sw.append((t, match.iloc[0]['speed'], match.iloc[0]['wheel']))
            else:
                self.sw.append((t, np.nan, np.nan))
        self.sw = np.array(self.sw)
        print(f"  Speed: [{self.sw[:,1].min():.0f}~{self.sw[:,1].max():.0f}] km/h")

    # ---------- 2. ALIGNMENT ----------
    def get_aligned(self, imu_name):
        """返回对齐到common_t的数据 [time, Ax, Ay, Az, Gx, Gy, Gz, Gx_r, Gy_r, Gz_r]"""
        source = self.exp.get(imu_name)
        if source is None:
            source = self.ctrl.get(imu_name)
        if source is None:
            return None
        tmap = {round(row[0], 4): row[1:] for row in source}
        result = []
        for t in self.common_t:
            result.append([t] + list(tmap.get(t, [np.nan] * 9)))
        return np.array(result)

    # ---------- 3. EVENT DETECTION ----------
    def detect_events(self):
        """事件检测: 制动/加速/转向/冲击"""
        print("[2/10] 事件检测...")
        speed = self.sw[:, 1]
        wheel = self.sw[:, 2]
        ds = np.diff(speed, prepend=speed[0])
        dw = np.diff(np.abs(wheel), prepend=np.abs(wheel[0]))

        # 冲击检测（从头部Ay）
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ay_vals = exp_head[:, 2]
        day = np.diff(ay_vals, prepend=ay_vals[0])

        event_mask = (ds < self.cfg['ds_brake_thresh']) | (ds > self.cfg['ds_accel_thresh']) | \
                     (dw > self.cfg['dw_steer_thresh']) | (np.abs(day) > self.cfg['da_shock_thresh'])
        indices = np.where(event_mask)[0]

        segments = []
        if len(indices) > 0:
            seg_start = indices[0]
            for i in range(1, len(indices)):
                if indices[i] - indices[i-1] > int(self.fs * 0.5):
                    segments.append((int(seg_start), int(indices[i-1])))
                    seg_start = indices[i]
            segments.append((int(seg_start), int(indices[-1])))

        self.events = []
        for s, e in segments:
            seg_speed = speed[s:e+1]
            seg_wheel = wheel[s:e+1]
            max_ds = seg_speed[-1] - seg_speed[0]
            max_dw = np.max(np.abs(np.diff(np.abs(seg_wheel), prepend=np.abs(seg_wheel[0]))))

            if max_ds < -5:
                etype = '制动减速'
            elif max_ds > 5:
                etype = '加速'
            elif max_dw > 10:
                etype = '转向/变道'
            else:
                etype = '复合工况'

            self.events.append({
                't_start': self.common_t[s], 't_end': self.common_t[e],
                'type': etype, 'speed_start': speed[s], 'speed_end': speed[e],
                'wheel_change': max_dw, 'idx_start': s, 'idx_end': e,
                'duration': self.common_t[e] - self.common_t[s]
            })

        etype_counts = pd.Series([ev['type'] for ev in self.events]).value_counts()
        print(f"  检测到 {len(self.events)} 个事件:")
        for t, c in etype_counts.items():
            print(f"    {t}: {c}次")

    # ---------- 4. FULL WINDOW ANALYSIS ----------
    def window_analysis(self):
        """全时域滑动窗口连续对比"""
        print("[3/10] 全时域滑动窗口分析...")
        ws = int(self.cfg['window_sec'] * self.fs)
        ss = int(self.cfg['step_sec'] * self.fs)
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])
        exp_sternum = self.get_aligned(list(self.exp.keys())[-1]) if len(self.exp) > 1 else None

        results = []
        for start in range(0, len(self.common_t) - ws, ss):
            end = start + ws
            win = {'t_center': self.common_t[start + ws // 2],
                   'speed': np.nanmean(self.sw[start:end, 1])}

            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                ev = exp_head[start:end, col]
                cv = ctrl_head[start:end, col]
                val = ~np.isnan(ev) & ~np.isnan(cv)
                if val.sum() > 50:
                    e_rms = np.sqrt(np.mean(ev[val]**2))
                    c_rms = np.sqrt(np.mean(cv[val]**2))
                    win[f'e_{axis}_RMS'] = e_rms
                    win[f'c_{axis}_RMS'] = c_rms
                    win[f'e_{axis}_Peak'] = np.max(np.abs(ev[val]))
                    win[f'c_{axis}_Peak'] = np.max(np.abs(cv[val]))
                    if c_rms > 1e-3:
                        win[f'atten_{axis}_pct'] = (1 - e_rms / c_rms) * 100

            # 头部-胸骨传递
            if exp_sternum is not None:
                for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                    col = axis_idx + 1
                    hv = exp_head[start:end, col]
                    sv = exp_sternum[start:end, col]
                    val = ~np.isnan(hv) & ~np.isnan(sv)
                    if val.sum() > 50:
                        h_rms = np.sqrt(np.mean(hv[val]**2))
                        s_rms = np.sqrt(np.mean(sv[val]**2))
                        if s_rms > 1e-3:
                            win[f'transfer_{axis}'] = h_rms / s_rms

            # 三轴合成
            for label, data in [('e', exp_head), ('c', ctrl_head)]:
                vals = np.sqrt(data[start:end, 1]**2 + data[start:end, 2]**2 + data[start:end, 3]**2)
                valid = ~np.isnan(vals)
                win[f'{label}_total_RMS'] = np.sqrt(np.mean(vals[valid]**2))

            results.append(win)

        df_win = pd.DataFrame(results)
        # 计算统计
        for ax in ['Ax', 'Ay', 'Az']:
            col = f'atten_{ax}_pct'
            if col in df_win.columns:
                vals = df_win[col].dropna()
                print(f"  {ax}衰减: mean={vals.mean():.1f}%, median={vals.median():.1f}%, "
                      f"正值比={(vals>0).mean()*100:.1f}%")
        self.results['windows'] = df_win
        return df_win

    # ---------- 5. EVENT-LEVEL ANALYSIS ----------
    def event_analysis(self):
        """事件级精细化对比"""
        print("[4/10] 事件级精细化分析...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])
        exp_sternum = self.get_aligned(list(self.exp.keys())[-1]) if len(self.exp) > 1 else None

        results = []
        for ev in self.events:
            s, e = ev['idx_start'], min(ev['idx_end'] + 1, len(self.common_t))
            if e - s < int(self.fs * 0.1):
                continue

            row = {'event': ev['type'], 't_start': ev['t_start'], 't_end': ev['t_end'],
                   'duration': ev['duration'], 'speed_start': ev['speed_start']}

            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                evals = exp_head[s:e, col]
                cvals = ctrl_head[s:e, col]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    row[f'e_{axis}_RMS'] = np.sqrt(np.mean(evals[valid]**2))
                    row[f'c_{axis}_RMS'] = np.sqrt(np.mean(cvals[valid]**2))
                    if row[f'c_{axis}_RMS'] > 1e-3:
                        row[f'atten_{axis}_pct'] = (1 - row[f'e_{axis}_RMS'] / row[f'c_{axis}_RMS']) * 100

            if exp_sternum is not None:
                for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                    col = axis_idx + 1
                    hv = exp_head[s:e, col]
                    sv = exp_sternum[s:e, col]
                    valid = ~np.isnan(hv) & ~np.isnan(sv)
                    if valid.sum() > 50:
                        h_rms = np.sqrt(np.mean(hv[valid]**2))
                        s_rms = np.sqrt(np.mean(sv[valid]**2))
                        if s_rms > 1e-3:
                            row[f'transfer_{axis}'] = h_rms / s_rms

            results.append(row)

        df_ev = pd.DataFrame(results)
        self.results['events'] = df_ev
        print(f"  分析 {len(df_ev)} 个事件窗口")
        return df_ev

    # ---------- 6. SPECTRUM ANALYSIS ----------
    def spectrum_analysis(self):
        """频谱分析 + 频段衰减 + 相干性"""
        print("[5/10] 频谱分析...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])
        nfft = self.cfg['nfft_welch']

        spec = {}
        for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
            col = axis_idx + 1
            evals = exp_head[:, col]
            cvals = ctrl_head[:, col]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)

            f_e, Pxx_e = signal.welch(evals[valid], fs=self.fs, nperseg=nfft)
            f_c, Pxx_c = signal.welch(cvals[valid], fs=self.fs, nperseg=nfft)
            f_coh, coh = signal.coherence(evals[valid], cvals[valid], fs=self.fs, nperseg=nfft)

            mask = (f_e >= 0.1) & (f_e <= 80)
            ratio = np.divide(Pxx_e[mask], Pxx_c[mask],
                              out=np.ones_like(Pxx_e[mask]) * np.nan,
                              where=Pxx_c[mask] > 1e-15)

            bands_atten = {}
            for bname, (flo, fhi) in self.cfg['freq_bands'].items():
                bm = (f_e[mask] >= flo) & (f_e[mask] <= fhi)
                if bm.sum() > 0:
                    bands_atten[bname] = (1 - np.nanmean(ratio[bm])) * 100

            spec[axis] = {
                'freq': f_e[mask], 'exp_psd': Pxx_e[mask],
                'ctrl_psd': Pxx_c[mask], 'ratio': ratio,
                'coherence': coh[mask] if len(coh) == len(mask) else coh[mask[:len(coh)]],
                'bands_atten': bands_atten
            }
            print(f"  {axis}: " + ", ".join([f"{b}={v:.1f}%" for b, v in bands_atten.items() if 'Hz' in b]))

        self.results['spectrum'] = spec
        return spec

    # ---------- 7. STFT TIME-FREQUENCY ----------
    def stft_analysis(self):
        """短时傅里叶变换时频分析"""
        print("[6/10] 时频分析 (STFT)...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])

        stft_results = {}
        for axis_idx, axis in enumerate(['Ay']):  # 专注于Ay
            col = axis_idx + 1
            f_e, t_e, Zxx_e = signal.stft(exp_head[:, col], fs=self.fs,
                                           nperseg=self.cfg['nfft_stft'],
                                           noverlap=self.cfg['stft_overlap'])
            f_c, t_c, Zxx_c = signal.stft(ctrl_head[:, col], fs=self.fs,
                                           nperseg=self.cfg['nfft_stft'],
                                           noverlap=self.cfg['stft_overlap'])
            stft_results[axis] = {
                'f': f_e, 't': t_e + self.common_t[0],
                'exp_spec': np.abs(Zxx_e), 'ctrl_spec': np.abs(Zxx_c),
            }

        self.results['stft'] = stft_results
        return stft_results

    # ---------- 8. STATISTICAL TESTS ----------
    def statistical_analysis(self):
        """统计学检验"""
        print("[7/10] 统计学分析...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])

        stats_results = {}
        for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
            col = axis_idx + 1
            evals = exp_head[:, col]
            cvals = ctrl_head[:, col]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)

            # Paired t-test (downsampled to avoid inflation)
            ds_factor = 10
            e_down = evals[valid][::ds_factor]
            c_down = cvals[valid][::ds_factor]
            t_stat, p_val = stats.ttest_rel(e_down, c_down)

            # Cohen's d
            d = (np.mean(e_down) - np.mean(c_down)) / np.sqrt((np.std(e_down)**2 + np.std(c_down)**2) / 2)

            # 95% CI of difference
            diff = e_down - c_down
            ci_lo, ci_hi = np.percentile(diff, [2.5, 97.5])

            # RMS-based attenuation
            e_rms = np.sqrt(np.mean(evals[valid]**2))
            c_rms = np.sqrt(np.mean(cvals[valid]**2))
            atn = (1 - e_rms / c_rms) * 100 if c_rms > 1e-3 else np.nan

            stats_results[axis] = {
                't_stat': t_stat, 'p_value': p_val,
                'cohens_d': d, 'ci_lo': ci_lo, 'ci_hi': ci_hi,
                'e_rms': e_rms, 'c_rms': c_rms, 'attenuation_pct': atn,
                'significant': '***' if p_val < 0.001 else ('**' if p_val < 0.01 else ('*' if p_val < 0.05 else 'ns'))
            }
            print(f"  {axis}: t={t_stat:.2f}, p={p_val:.2e}, d={d:.2f}, atn={atn:.1f}% {stats_results[axis]['significant']}")

        self.results['statistics'] = stats_results
        return stats_results

    # ---------- 9. COMPREHENSIVE METRICS ----------
    def comprehensive_metrics(self):
        """综合评价指标 (VDV, Crest Factor, SEAT等效, 传递系数)"""
        print("[8/10] 综合评价指标...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])
        exp_sternum = self.get_aligned(list(self.exp.keys())[-1]) if len(self.exp) > 1 else None

        metrics = {}
        for label, data in [('exp', exp_head), ('ctrl', ctrl_head),
                             ('sternum', exp_sternum) if exp_sternum is not None else ('_skip', None)]:
            if data is None:
                continue
            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                vals = data[:, col]
                valid = vals[~np.isnan(vals)]
                if len(valid) < 100:
                    continue
                prefix = f'{label}_{axis}'
                metrics[f'{prefix}_RMS'] = np.sqrt(np.mean(valid**2))
                metrics[f'{prefix}_Peak'] = np.max(np.abs(valid))
                metrics[f'{prefix}_CrestFactor'] = metrics[f'{prefix}_Peak'] / metrics[f'{prefix}_RMS'] if metrics[f'{prefix}_RMS'] > 1e-6 else np.nan
                metrics[f'{prefix}_VDV'] = (np.sum(valid**4) / self.fs) ** 0.25
                # 歪度/峰度
                metrics[f'{prefix}_Skewness'] = stats.skew(valid)
                metrics[f'{prefix}_Kurtosis'] = stats.kurtosis(valid, fisher=True)
                # 绝对值均值(MAV)
                metrics[f'{prefix}_MAV'] = np.mean(np.abs(valid))
                # 冲击因子
                metrics[f'{prefix}_ImpulseFactor'] = metrics[f'{prefix}_Peak'] / metrics[f'{prefix}_MAV'] if metrics[f'{prefix}_MAV'] > 1e-6 else np.nan

        # 三轴合成VDV
        for label, data in [('exp', exp_head), ('ctrl', ctrl_head)]:
            total = np.sqrt(data[:, 1]**2 + data[:, 2]**2 + data[:, 3]**2)
            valid = total[~np.isnan(total)]
            metrics[f'{label}_total_VDV'] = (np.sum(valid**4) / self.fs) ** 0.25

        self.results['metrics'] = metrics
        print(f"  计算 {len(metrics)} 个指标")
        return metrics

    # ---------- 10. VISUALIZATION ----------
    def generate_visualizations(self, out_dir='.'):
        """生成全部可视化图表"""
        print("[9/10] 生成可视化图表...")
        exp_head = self.get_aligned(list(self.exp.keys())[0])
        ctrl_head = self.get_aligned(list(self.ctrl.keys())[0])
        exp_sternum = self.get_aligned(list(self.exp.keys())[-1]) if len(self.exp) > 1 else None

        # ── Fig 1: 全时程概览 ──
        fig, axes = plt.subplots(4, 1, figsize=(18, 12), sharex=True)
        t_arr = self.sw[:, 0]

        axes[0].plot(t_arr, self.sw[:, 1], 'b-', linewidth=0.8)
        axes[0].set_ylabel('Speed\n(km/h)')
        axes[0].set_title('Vehicle State & Occupant Head Response — 全维度评测概览', fontsize=13, fontweight='bold')

        axes[1].plot(t_arr, self.sw[:, 2], 'r-', linewidth=0.8)
        axes[1].set_ylabel('Wheel\n(deg)')

        for axis_idx, axis_name, color in [(1, 'Ax', '#2196F3'), (2, 'Ay', '#4CAF50'), (3, 'Az', '#FF9800')]:
            axes[2].plot(self.common_t[:len(exp_head)], exp_head[:, axis_idx],
                         color=color, linewidth=0.3, alpha=0.6, label=f'Exp {axis_name}')
            axes[3].plot(self.common_t[:len(ctrl_head)], ctrl_head[:, axis_idx],
                         color=color, linewidth=0.3, alpha=0.6, label=f'Ctrl {axis_name}')
        axes[2].set_ylabel('Exp Head\n(m/s²)')
        axes[3].set_ylabel('Ctrl Head\n(m/s²)')
        axes[3].set_xlabel('Time (s)')
        for ax in axes[2:]:
            ax.legend(fontsize=7, loc='upper right', ncol=3)

        plt.tight_layout()
        plt.savefig(f'{out_dir}/fig1_overview.png', dpi=150)
        plt.close()
        print("  fig1_overview.png")

        # ── Fig 2: 事件概览 ──
        n_ev = min(len(self.events), 12)
        ncols = 4
        nrows = (n_ev + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(18, 3 * nrows))
        axes_flat = axes.flatten() if nrows * ncols > 1 else [axes]

        for i, ev in enumerate(self.events[:n_ev]):
            s = max(0, ev['idx_start'] - int(self.fs * 0.5))
            e = min(len(self.common_t) - 1, ev['idx_end'] + int(self.fs * 1.5))
            t_seg = self.common_t[s:e] - self.common_t[ev['idx_start']]
            ax = axes_flat[i]
            ax.plot(t_seg, exp_head[s:e, 2], 'b-', linewidth=1.2, alpha=0.8, label='Active')
            ax.plot(t_seg, ctrl_head[s:e, 2], 'r--', linewidth=1.0, alpha=0.8, label='Passive')
            ax.axvline(x=0, color='k', linestyle=':', alpha=0.4)
            ax.axvspan(0, ev['duration'], alpha=0.1, color='yellow')
            ax.set_title(f'E{i+1}: {ev["type"][:6]} t={ev["t_start"]:.1f}s', fontsize=8)
            if ev['duration'] > 0.1:
                # 计算该事件Ay衰减
                evals = exp_head[s:e, 2]
                cvals = ctrl_head[s:e, 2]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    e_rms = np.sqrt(np.mean(evals[valid]**2))
                    c_rms = np.sqrt(np.mean(cvals[valid]**2))
                    atn = (1 - e_rms / c_rms) * 100 if c_rms > 1e-3 else 0
                    color = 'green' if atn > 0 else 'red'
                    ax.text(0.95, 0.95, f'Δ={atn:.0f}%', transform=ax.transAxes,
                            ha='right', va='top', fontsize=8, color=color, fontweight='bold')
            ax.grid(True, alpha=0.2)
        if n_ev > 0:
            axes_flat[0].legend(fontsize=7, loc='upper left')
        for i in range(n_ev, nrows * ncols):
            axes_flat[i].set_visible(False)
        plt.suptitle('全部驾驶事件 — 主动座椅(蓝) vs 被动座椅(红) 头部Ay对比', fontsize=12)
        plt.tight_layout()
        plt.savefig(f'{out_dir}/fig2_events.png', dpi=150)
        plt.close()
        print("  fig2_events.png")

        # ── Fig 3: 频谱对比 ──
        spec = self.results.get('spectrum', self.spectrum_analysis())
        fig, axes = plt.subplots(3, 3, figsize=(18, 14))
        for row, axis_name in enumerate(['Ax', 'Ay', 'Az']):
            s = spec[axis_name]
            f = s['freq']
            # PSD
            axes[row, 0].semilogy(f, s['exp_psd'], 'b-', linewidth=1, alpha=0.8, label='Active Seat')
            axes[row, 0].semilogy(f, s['ctrl_psd'], 'r-', linewidth=1, alpha=0.8, label='Passive Seat')
            axes[row, 0].set_title(f'{axis_name} — Power Spectral Density')
            axes[row, 0].set_ylabel('PSD')
            axes[row, 0].legend(fontsize=7)
            # PSD Ratio
            axes[row, 1].plot(f, s['ratio'], 'g-', linewidth=1.5)
            axes[row, 1].axhline(y=1, color='k', linestyle='--', alpha=0.5)
            axes[row, 1].set_ylabel('PSD Ratio (Exp/Ctrl)')
            axes[row, 1].set_title(f'{axis_name} — Attenuation Ratio (<1 = Effective)')
            # Coherence
            axes[row, 2].plot(f[:len(s['coherence'])], s['coherence'], 'm-', linewidth=1)
            axes[row, 2].set_ylim(0, 1)
            axes[row, 2].set_ylabel('Coherence')
            axes[row, 2].set_title(f'{axis_name} — Exp-Ctrl Coherence')
        for ax in axes.flatten():
            ax.set_xlabel('Frequency (Hz)')
            ax.grid(True, alpha=0.3)
        plt.suptitle('频域分析 — 主动座椅 vs 被动座椅', fontsize=13, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f'{out_dir}/fig3_spectrum.png', dpi=150)
        plt.close()
        print("  fig3_spectrum.png")

        # ── Fig 4: STFT时频图 ──
        stft = self.results.get('stft', self.stft_analysis())
        if 'Ay' in stft:
            s = stft['Ay']
            f_mask = s['f'] <= 50
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 8), sharex=True, sharey=True)
            im1 = ax1.pcolormesh(s['t'], s['f'][f_mask], s['exp_spec'][f_mask],
                                  shading='gouraud', cmap='viridis', norm=mcolors.LogNorm())
            ax1.set_ylabel('Freq (Hz)')
            ax1.set_title('Active Seat — Head Ay STFT')
            plt.colorbar(im1, ax=ax1, label='Magnitude')
            im2 = ax2.pcolormesh(s['t'], s['f'][f_mask], s['ctrl_spec'][f_mask],
                                  shading='gouraud', cmap='inferno', norm=mcolors.LogNorm())
            ax2.set_ylabel('Freq (Hz)')
            ax2.set_xlabel('Time (s)')
            ax2.set_title('Passive Seat — Head Ay STFT')
            plt.colorbar(im2, ax=ax2, label='Magnitude')
            plt.suptitle('时频分析 (STFT) — Ay横向加速度', fontsize=13, fontweight='bold')
            plt.tight_layout()
            plt.savefig(f'{out_dir}/fig4_stft.png', dpi=150)
            plt.close()
            print("  fig4_stft.png")

        # ── Fig 5: 统计学仪表盘 ──
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        for coli, (axis_name, color) in enumerate([('Ax', '#2196F3'), ('Ay', '#4CAF50'), ('Az', '#FF9800')]):
            # RMS对比
            col = {'Ax': 1, 'Ay': 2, 'Az': 3}[axis_name]
            evals = exp_head[:, col]
            cvals = ctrl_head[:, col]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)
            axes[0, coli].hist(evals[valid], bins=100, alpha=0.5, density=True, color=color, label='Active')
            axes[0, coli].hist(cvals[valid], bins=100, alpha=0.5, density=True, color='gray', label='Passive')
            axes[0, coli].set_title(f'{axis_name} Distribution')
            axes[0, coli].legend(fontsize=7)

            # Box plot (downsampled)
            ds = 50
            data_box = [evals[valid][::ds], cvals[valid][::ds]]
            axes[1, coli].boxplot(data_box, labels=['Active', 'Passive'], patch_artist=True,
                                   boxprops=dict(facecolor=color, alpha=0.5))
            axes[1, coli].set_title(f'{axis_name} Box Plot')

        # 综合雷达图
        ax = axes[0, 3] if axes.shape[1] >= 4 else None  # skip radar if 3 cols
        # 衰减率柱状图
        ax_bar = axes[1, 3] if axes.shape[1] >= 4 else None

        # 隐藏多余子图
        if axes.shape[1] > 3:
            for i in range(3, axes.shape[1]):
                axes[0, i].set_visible(False)
                axes[1, i].set_visible(False)

        plt.suptitle('统计学分析 — 主动座椅 vs 被动座椅', fontsize=13, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f'{out_dir}/fig5_statistics.png', dpi=150)
        plt.close()
        print("  fig5_statistics.png")

        # ── Fig 6: 频段衰减雷达图 ──
        bands_5 = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']
        band_labels = bands_5
        fig, ax = plt.subplots(1, 1, figsize=(8, 8), subplot_kw=dict(polar=True))
        angles = np.linspace(0, 2 * np.pi, len(bands_5), endpoint=False).tolist()
        angles += angles[:1]  # close the loop
        for axis_name, color, marker in [('Ax', 'blue', 'o'), ('Ay', 'green', 's'), ('Az', 'orange', '^')]:
            vals = [spec[axis_name]['bands_atten'].get(b, 0) for b in bands_5]
            vals_clipped = [max(-100, min(200, v)) for v in vals]
            vals_clipped += vals_clipped[:1]
            ax.plot(angles, vals_clipped, marker=marker, linestyle='-', color=color,
                    linewidth=2, label=axis_name, markersize=8)
            ax.fill(angles, vals_clipped, alpha=0.1, color=color)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(band_labels)
        ax.set_title('Frequency Band Attenuation Radar\n(Active vs Passive Seat)', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax.set_ylim(-100, 200)
        plt.tight_layout()
        plt.savefig(f'{out_dir}/fig6_band_radar.png', dpi=150)
        plt.close()
        print("  fig6_band_radar.png")

        print("  全部图表生成完成!")

    # ---------- RUN ALL ----------
    def run_all(self, out_dir='.'):
        """执行全部分析流程"""
        self.load()
        self.detect_events()
        self.window_analysis()
        self.event_analysis()
        self.spectrum_analysis()
        self.stft_analysis()
        self.statistical_analysis()
        self.comprehensive_metrics()
        self.generate_visualizations(out_dir)
        self.generate_report(out_dir)
        return self.results

    # ---------- REPORT ----------
    def generate_report(self, out_dir='.'):
        """生成综合评测报告"""
        print("[10/10] 生成评测报告...")
        spec = self.results.get('spectrum', {})
        stats = self.results.get('statistics', {})
        metrics = self.results.get('metrics', {})
        windows = self.results.get('windows', pd.DataFrame())

        lines = []
        lines.append("# 主动控制座椅悬架 — 乘员头部运动响应全维度评测报告")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"数据文件: {os.path.basename(self.path)}")
        lines.append(f"分析维度: 时域/频域/时频/事件/统计/综合指标")
        lines.append("")

        # 1. 数据概况
        lines.append("## 1. 数据概况")
        lines.append(f"- 采样率: {self.fs:.0f} Hz")
        lines.append(f"- 时长: {self.common_t[-1]-self.common_t[0]:.1f} s")
        lines.append(f"- 检测事件: {len(self.events)} 个")
        lines.append(f"- 传感器: {len(self.exp) + len(self.ctrl)} 个IMU")
        lines.append("")

        # 2. 频段衰减
        lines.append("## 2. 频段衰减效果 (主动座椅 vs 被动座椅)")
        lines.append("| 频段 | Ax | Ay | Az |")
        lines.append("|:---|---:|---:|---:|")
        for band in ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']:
            vals = []
            for ax in ['Ax', 'Ay', 'Az']:
                v = spec.get(ax, {}).get('bands_atten', {}).get(band, np.nan)
                vals.append(f"{v:.1f}%" if not np.isnan(v) else "—")
            lines.append(f"| {band} | {vals[0]} | {vals[1]} | {vals[2]} |")
        lines.append("")

        # 3. 综合指标
        lines.append("## 3. 综合评价指标")
        lines.append("| 指标 | 主动座椅 | 被动座椅 | 改善幅度 |")
        lines.append("|:---|---:|---:|---:|")
        for ax in ['Ax', 'Ay', 'Az']:
            e_vdv = metrics.get(f'exp_{ax}_VDV', np.nan)
            c_vdv = metrics.get(f'ctrl_{ax}_VDV', np.nan)
            e_rms = metrics.get(f'exp_{ax}_RMS', np.nan)
            c_rms = metrics.get(f'ctrl_{ax}_RMS', np.nan)
            if not np.isnan(e_vdv) and not np.isnan(c_vdv):
                imp = ((c_vdv - e_vdv) / abs(c_vdv)) * 100 if abs(c_vdv) > 1e-6 else np.nan
                lines.append(f"| {ax} VDV | {e_vdv:.2f} | {c_vdv:.2f} | {imp:+.1f}% |")
            if not np.isnan(e_rms) and not np.isnan(c_rms):
                imp = ((c_rms - e_rms) / abs(c_rms)) * 100 if abs(c_rms) > 1e-6 else np.nan
                lines.append(f"| {ax} RMS | {e_rms:.3f} | {c_rms:.3f} | {imp:+.1f}% |")
        lines.append("")

        # 4. 显著性检验
        lines.append("## 4. 统计学检验")
        lines.append("| 轴 | t值 | p值 | Cohen's d | RMS衰减 | 显著性 |")
        lines.append("|:---|---:|---:|---:|---:|:---:|")
        for ax in ['Ax', 'Ay', 'Az']:
            s = stats.get(ax, {})
            lines.append(f"| {ax} | {s.get('t_stat', np.nan):.2f} | {s.get('p_value', 1):.2e} | "
                         f"{s.get('cohens_d', np.nan):.3f} | {s.get('attenuation_pct', np.nan):.1f}% | "
                         f"{s.get('significant', '—')} |")
        lines.append("")

        # 5. 事件摘要
        lines.append("## 5. 驾驶事件摘要")
        for i, ev in enumerate(self.events[:10]):
            lines.append(f"- **E{i+1}** [{ev['type']}] t={ev['t_start']:.1f}s dur={ev['duration']:.2f}s "
                         f"speed {ev['speed_start']:.0f}→{ev['speed_end']:.0f} km/h")
        lines.append("")

        # 6. 图表清单
        lines.append("## 6. 输出图表清单")
        for f in ['fig1_overview.png', 'fig2_events.png', 'fig3_spectrum.png',
                   'fig4_stft.png', 'fig5_statistics.png', 'fig6_band_radar.png']:
            if os.path.exists(f'{out_dir}/{f}'):
                lines.append(f"- ✅ {f}")

        lines.append("\n---\n*本报告由 OccupantMotionEvaluator v2.0 自动生成*")

        report_md = "\n".join(lines)
        with open(f'{out_dir}/EVALUATION_REPORT.md', 'w', encoding='utf-8') as f:
            f.write(report_md)

        # Save CSVs
        if len(windows) > 0:
            windows.to_csv(f'{out_dir}/window_analysis.csv', index=False)
        events_df = self.results.get('events', pd.DataFrame())
        if len(events_df) > 0:
            events_df.to_csv(f'{out_dir}/event_analysis.csv', index=False)
        pd.DataFrame([metrics]).to_csv(f'{out_dir}/comprehensive_metrics.csv', index=False)

        print(f"  报告: EVALUATION_REPORT.md, CSVs: window/event/metrics")
        return report_md


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='主动座椅全维度评测')
    parser.add_argument('csv_path', nargs='?',
                        default='parsed_data.csv',
                        help='CSV数据文件路径')
    parser.add_argument('-o', '--out-dir', default='.',
                        help='输出目录 (默认当前)')
    args = parser.parse_args()

    evaluator = OccupantMotionEvaluator(args.csv_path)
    evaluator.run_all(args.out_dir)
    print("\n" + "=" * 60)
    print("  全维度评测完成!")
    print(f"  输出: {args.out_dir}/")
    print(f"    EVALUATION_REPORT.md      综合评测报告")
    print(f"    fig1-6_*.png             可视化图表")
    print(f"    window_analysis.csv      滑动窗口数据")
    print(f"    event_analysis.csv       事件分析数据")
    print(f"    comprehensive_metrics.csv 综合指标数据")
    print("=" * 60)
