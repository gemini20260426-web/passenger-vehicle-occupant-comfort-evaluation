#!/usr/bin/env python3
"""
乘员头部运动响应评测脚本 — 主动控制座椅 vs 被动座椅 对比分析
基于真人志愿者实测IMU数据集

输入: parsed_data CSV文件 (rel_time, channel, imu_name, Ax_m_s2, Ay_m_s2, Az_m_s2, Gx_dps, Gy_dps, Gz_dps, Gx_rad_s, Gy_rad_s, Gz_rad_s, speed, wheel)
输出: 评测报告 (CSV + PNG图表)
"""

import pandas as pd
import numpy as np
from scipy import signal, stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class OccupantMotionEvaluator:
    """乘员运动响应评测器"""

    def __init__(self, csv_path, fs=1000):
        self.csv_path = csv_path
        self.fs = fs
        self.df = None
        self.common_t = None
        self.exp_head = None
        self.ctrl_head = None
        self.exp_sternum = None
        self.sw_data = None
        self.events = []

    def load_data(self):
        """加载CSV数据"""
        self.df = pd.read_csv(self.csv_path)
        print(f"[INFO] 加载数据: {len(self.df)}行")

        # 传感器映射
        exp_imus = ['IMU1_头部眉心-1', 'IMU9_胸骨剑突-1']
        ctrl_imus = ['IMU2_头部眉心-2']

        # 对齐公共时间轴
        pivot = {}
        for imu in exp_imus + ctrl_imus:
            sub = self.df[self.df['imu_name']==imu].sort_values('rel_time')
            pivot[imu] = sub[['rel_time','Ax_m_s2','Ay_m_s2','Az_m_s2','Gx_dps','Gy_dps','Gz_dps']].values

        t_exp = set(round(t,4) for t in pivot['IMU1_头部眉心-1'][:,0])
        t_ctrl = set(round(t,4) for t in pivot['IMU2_头部眉心-2'][:,0])
        self.common_t = sorted(t_exp & t_ctrl)

        def align(name):
            d = pivot[name]
            tmap = {round(row[0],4): row[1:] for row in d}
            result = []
            for t in self.common_t:
                result.append([t] + list(tmap.get(t, [np.nan]*6)))
            return np.array(result)

        self.exp_head = align('IMU1_头部眉心-1')
        self.ctrl_head = align('IMU2_头部眉心-2')
        self.exp_sternum = align('IMU9_胸骨剑突-1')

        # Speed/Wheel 对齐
        sw = self.df[self.df['channel']=='ch1'].drop_duplicates('rel_time').sort_values('rel_time')
        sw_data = []
        for t in self.common_t:
            match = sw[abs(sw['rel_time']-t)<1e-3]
            if len(match)>0:
                sw_data.append((t, match.iloc[0]['speed'], match.iloc[0]['wheel']))
            else:
                sw_data.append((t, np.nan, np.nan))
        self.sw_data = np.array(sw_data)

        print(f"[INFO] 对齐: {len(self.common_t)}点, fs={self.fs}Hz, {self.common_t[-1]-self.common_t[0]:.1f}s")

    def detect_events(self, ds_thresh=-2, da_thresh=3, dw_thresh=3):
        """事件检测"""
        speed = self.sw_data[:,1]
        wheel = self.sw_data[:,2]
        ds = np.diff(speed, prepend=speed[0])
        dw = np.diff(np.abs(wheel), prepend=np.abs(wheel[0]))

        event_mask = (ds < ds_thresh) | (ds > da_thresh) | (dw > dw_thresh)
        event_indices = np.where(event_mask)[0]

        events = []
        if len(event_indices) > 0:
            seg_start = event_indices[0]
            for i in range(1, len(event_indices)):
                if event_indices[i] - event_indices[i-1] > int(self.fs * 0.5):
                    events.append((seg_start, event_indices[i-1]))
                    seg_start = event_indices[i]
            events.append((seg_start, event_indices[-1]))

        classified = []
        for seg_start, seg_end in events:
            seg_speed = speed[seg_start:seg_end+1]
            seg_wheel = wheel[seg_start:seg_end+1]
            max_ds = seg_speed[-1] - seg_speed[0]
            max_dw = np.max(np.abs(np.diff(seg_wheel, prepend=seg_wheel[0])))

            if max_ds < -5:
                etype = '制动减速'
            elif max_ds > 5:
                etype = '加速'
            elif max_dw > 10:
                etype = '转向/变道'
            else:
                etype = '复合工况'

            classified.append({
                't_start': self.common_t[seg_start],
                't_end': self.common_t[seg_end],
                'type': etype,
                'speed_start': speed[seg_start],
                'speed_end': speed[seg_end],
                'idx_start': seg_start,
                'idx_end': seg_end
            })

        self.events = classified
        print(f"[INFO] 检测到 {len(classified)} 个驾驶事件")
        return classified

    def window_analysis(self, window_sec=1.0, step_sec=0.5):
        """滑动窗口连续分析"""
        window_samples = int(window_sec * self.fs)
        step_samples = int(step_sec * self.fs)
        results = []

        for start in range(0, len(self.common_t) - window_samples, step_samples):
            end = start + window_samples
            exp_a = self.exp_head[start:end, :]
            ctrl_a = self.ctrl_head[start:end, :]

            win = {'t_center': self.common_t[start+window_samples//2]}

            for col_idx, axis in enumerate(['Ax','Ay','Az']):
                evals = exp_a[:, col_idx+1]
                cvals = ctrl_a[:, col_idx+1]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    e_rms = np.sqrt(np.mean(evals[valid]**2))
                    c_rms = np.sqrt(np.mean(cvals[valid]**2))
                    win[f'exp_{axis}_RMS'] = e_rms
                    win[f'ctrl_{axis}_RMS'] = c_rms
                    if c_rms > 0.01:
                        win[f'attenuation_{axis}'] = (1-e_rms/c_rms)*100

            results.append(win)
        return pd.DataFrame(results)

    def spectrum_analysis(self):
        """频谱分析"""
        nfft = 8192
        spec_results = {}

        for axis_idx, axis in enumerate(['Ax','Ay','Az']):
            evals = self.exp_head[:, axis_idx+1]
            cvals = self.ctrl_head[:, axis_idx+1]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)

            f_exp, Pxx_exp = signal.welch(evals[valid], fs=self.fs, nperseg=nfft)
            f_ctrl, Pxx_ctrl = signal.welch(cvals[valid], fs=self.fs, nperseg=nfft)

            mask = (f_exp >= 0.1) & (f_exp <= 80)
            ratio = np.divide(Pxx_exp[mask], Pxx_ctrl[mask], 
                             out=np.ones_like(Pxx_exp[mask])*np.nan, where=Pxx_ctrl[mask]>1e-15)

            spec_results[axis] = {'freq': f_exp[mask], 'exp_psd': Pxx_exp[mask], 
                                  'ctrl_psd': Pxx_ctrl[mask], 'ratio': ratio}

        return spec_results

    def generate_report(self, output_prefix='evaluation_report'):
        """生成完整评测报告"""
        # 1. 全量统计
        stats = {}
        for label, data in [('ExpHead', self.exp_head), ('CtrlHead', self.ctrl_head)]:
            for col_idx, axis in enumerate(['Ax','Ay','Az']):
                vals = data[:, col_idx+1]
                valid = vals[~np.isnan(vals)]
                if len(valid) > 100:
                    stats[f'{label}_{axis}_RMS'] = np.sqrt(np.mean(valid**2))
                    stats[f'{label}_{axis}_Peak'] = np.max(np.abs(valid))

        # 2. 频谱分析
        spec = self.spectrum_analysis()

        # 3. 窗口分析
        windows = self.window_analysis()

        # 4. 生成图表
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))

        for row_idx, (label, data) in enumerate([('实验组(主动)', self.exp_head), ('对照组(被动)', self.ctrl_head)]):
            for col_idx, axis in enumerate(['Ax','Ay','Az']):
                ax = axes[row_idx, col_idx]
                vals = data[:, col_idx+1]
                valid = vals[~np.isnan(vals)]
                t = self.common_t[:len(vals)]
                ax.plot(t, vals, 'b-' if row_idx==0 else 'r-', linewidth=0.3, alpha=0.7)
                ax.set_title(f'{label} — 头部{axis}')
                ax.set_xlabel('Time (s)')
                ax.set_ylabel(f'{axis} (m/s²)')
                ax.grid(True, alpha=0.3)

        plt.suptitle(f'乘员头部运动响应评测 — 主动控制座椅 vs 被动座椅', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f'{output_prefix}_overview.png', dpi=150)
        plt.close()

        # 生成CSV报告
        report_df = pd.DataFrame([stats])
        report_df.to_csv(f'{output_prefix}_stats.csv', index=False)
        windows.to_csv(f'{output_prefix}_windows.csv', index=False)

        print(f"[DONE] 报告已生成: {output_prefix}_stats.csv, {output_prefix}_windows.csv, {output_prefix}_overview.png")

        return {'stats': stats, 'spec': spec, 'windows': windows}


if __name__ == '__main__':
    evaluator = OccupantMotionEvaluator('parsed_data.csv')
    evaluator.load_data()
    evaluator.detect_events()
    evaluator.generate_report('evaluation_report')
