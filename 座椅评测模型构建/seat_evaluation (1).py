#!/usr/bin/env python3
"""
乘用车座椅综合性能评测 — 10路IMU考核指标计算引擎
==================================================
基于四层映射架构: 数据源 → 位置 → 数据字段 → 算子 → 考核指标

IMU布局 (2026-05 实车试验):
  ch1: IMU1(头部眉心-实验组) | IMU2(头部眉心-对照组)
  ch2: IMU3(躯干T8-实验组)   | IMU4(躯干T8-对照组)
  ch3: IMU5(座垫R点-实验组)   | IMU6(座垫R点-对照组)
  ch4: IMU7(座椅底部-实验组)⭐ | IMU8(座椅底部-对照组)
  ch5: IMU9(胸骨剑突-实验组)  | IMU10(胸骨剑突-对照组)

用法:
  from seat_evaluation import SeatEvaluator
  evaluator = SeatEvaluator(imu_data_dict)
  results = evaluator.compute_all_indicators()

作者: SciClaw | 版本: V1.0 | 日期: 2026-05-16
"""

import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
import warnings

# ============================================================================
# 第一层映射: 数据源 → 位置
# ============================================================================

@dataclass
class IMUPosition:
    """IMU传感器位置定义"""
    imu_id: str          # IMU编号, 如 "IMU1"
    imu_name: str        # 完整名称, 如 "IMU1_头部眉心-1"
    channel: str         # CAN通道, 如 "ch1"
    group: str           # 分组: "实验组(A)" 或 "对照组(B)"
    body_location: str   # 身体位置: "头部眉心" / "躯干T8" / "座垫R点" / "座椅底部" / "胸骨剑突"
    is_base: bool = False  # 是否为底座参考IMU (IMU7/IMU8)

# 完整的10路IMU位置映射表
IMU_POSITIONS: Dict[str, IMUPosition] = {
    'IMU1_头部眉心-1':   IMUPosition('IMU1', 'IMU1_头部眉心-1',   'ch1', '实验组(A)', '头部眉心',  False),
    'IMU2_头部眉心-2':   IMUPosition('IMU2', 'IMU2_头部眉心-2',   'ch1', '对照组(B)', '头部眉心',  False),
    'IMU3_躯干T8-1':     IMUPosition('IMU3', 'IMU3_躯干T8-1',     'ch2', '实验组(A)', '躯干T8',    False),
    'IMU4_躯干T8-2':     IMUPosition('IMU4', 'IMU4_躯干T8-2',     'ch2', '对照组(B)', '躯干T8',    False),
    'IMU5_座垫R点-1':   IMUPosition('IMU5', 'IMU5_座垫R点-1',   'ch3', '实验组(A)', '座垫R点',   False),
    'IMU6_座垫R点-2':   IMUPosition('IMU6', 'IMU6_座垫R点-2',   'ch3', '对照组(B)', '座垫R点',   False),
    'IMU7_座椅底部-1':   IMUPosition('IMU7', 'IMU7_座椅底部-1',   'ch4', '实验组(A)', '座椅底部',  True),
    'IMU8_座椅底部-2':   IMUPosition('IMU8', 'IMU8_座椅底部-2',   'ch4', '对照组(B)', '座椅底部',  True),
    'IMU9_胸骨剑突-1':  IMUPosition('IMU9', 'IMU9_胸骨剑突-1',  'ch5', '实验组(A)', '胸骨剑突', False),
    'IMU10_胸骨剑突-2': IMUPosition('IMU10', 'IMU10_胸骨剑突-2', 'ch5', '对照组(B)', '胸骨剑突', False),
}

# 简化别名映射 (兼容数据中可能出现的名称变体)
IMU_ALIASES = {
    'IMU-01_头部眉心_实验组': 'IMU1_头部眉心-1',
    'IMU-01_头部眉心_对照组': 'IMU2_头部眉心-2',
    'IMU-02_躯干T8_实验组':   'IMU3_躯干T8-1',
    'IMU-02_躯干T8_对照组':   'IMU4_躯干T8-2',
    'IMU-03_座垫R点_实验组':   'IMU5_座垫R点-1',
    'IMU-03_座垫R点_对照组':   'IMU6_座垫R点-2',
    'IMU-04_座椅底部_实验组':  'IMU7_座椅底部-1',
    'IMU-04_座椅底部_对照组':  'IMU8_座椅底部-2',
    'IMU-BAK_胸骨剑突_实验组': 'IMU9_胸骨剑突-1',
    'IMU-BAK_胸骨剑突_对照组': 'IMU10_胸骨剑突-2',
}


# ============================================================================
# 第二层映射: 位置 → 数据字段
# ============================================================================

@dataclass
class IMUDataFrame:
    """单个IMU的完整数据帧"""
    imu_name: str
    rel_time: np.ndarray       # 相对时间 [s]
    ax: np.ndarray             # X轴加速度 [m/s²]
    ay: np.ndarray             # Y轴加速度 [m/s²]
    az: np.ndarray             # Z轴加速度 [m/s²]
    gx: np.ndarray             # X轴角速度 [°/s]
    gy: np.ndarray             # Y轴角速度 [°/s]
    gz: np.ndarray             # Z轴角速度 [°/s]
    fs: float = 512.0          # 采样频率 [Hz]
    
    @property
    def n_samples(self) -> int:
        return len(self.rel_time)
    
    @property
    def duration(self) -> float:
        return self.rel_time[-1] - self.rel_time[0] if self.n_samples > 1 else 0
    
    @property
    def a_mag(self) -> np.ndarray:
        """三轴合成加速度幅值"""
        return np.sqrt(self.ax**2 + self.ay**2 + self.az**2)
    
    @property
    def g_mag(self) -> np.ndarray:
        """三轴合成角速度幅值"""
        return np.sqrt(self.gx**2 + self.gy**2 + self.gz**2)
    
    def get_vector(self) -> np.ndarray:
        """返回 [N, 6] 矩阵 (ax,ay,az,gx,gy,gz)"""
        return np.column_stack([self.ax, self.ay, self.az, self.gx, self.gy, self.gz])


# ============================================================================
# 第三层映射: 数据字段 → 算子 (数据处理函数)
# ============================================================================

class SignalOperators:
    """信号处理算子集合"""
    
    @staticmethod
    def welch_psd(data: np.ndarray, fs: float = 512.0, 
                  nperseg: int = 1024, overlap: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
        """Welch法功率谱密度估计 → G(f)"""
        f, pxx = signal.welch(data, fs, nperseg=nperseg, 
                              noverlap=int(nperseg * overlap), 
                              window='hann', scaling='density')
        return f, pxx
    
    @staticmethod
    def cross_psd(x: np.ndarray, y: np.ndarray, fs: float = 512.0, 
                  nperseg: int = 1024) -> Tuple[np.ndarray, np.ndarray]:
        """交叉功率谱密度 → G_xy(f)"""
        f, pxy = signal.csd(x, y, fs, nperseg=nperseg, 
                            noverlap=nperseg//2, window='hann')
        return f, pxy
    
    @staticmethod
    def cfc_filter(data: np.ndarray, fs: float, cfc_class: int = 600) -> np.ndarray:
        """CFC通道频率类滤波 (SAE J211-1)"""
        if cfc_class == 60:
            fc = 100.0
        elif cfc_class == 180:
            fc = 300.0
        elif cfc_class == 600:
            fc = 1000.0
        elif cfc_class == 1000:
            fc = 1650.0
        else:
            fc = 1000.0
        
        nyq = fs / 2.0
        b, a = signal.butter(4, fc / nyq, btype='low')
        return signal.filtfilt(b, a, data)
    
    @staticmethod
    def frequency_weighting(psd: np.ndarray, f: np.ndarray, 
                            axis: str = 'z') -> np.ndarray:
        """ISO 2631-1频率加权 (Wk for Z, Wd for X/Y)"""
        weighted = psd.copy()
        
        if axis.lower() == 'z':
            # Wk: ISO 2631-1 Table 3
            for i, freq in enumerate(f):
                if freq < 0.5:
                    w = 0.5
                elif freq <= 2.0:
                    w = freq
                elif freq <= 5.0:
                    w = 2.0
                elif freq <= 16.0:
                    w = 2.0 * (5.0 / freq)
                elif freq <= 80.0:
                    w = 2.0 * (5.0 / 16.0) * (16.0 / freq)
                else:
                    w = 0
                weighted[i] = psd[i] * w**2
        elif axis.lower() in ('x', 'y'):
            # Wd: ISO 2631-1 Table 4
            for i, freq in enumerate(f):
                if freq < 0.5:
                    w = 1.0
                elif freq <= 2.0:
                    w = freq / 0.5
                elif freq <= 5.0:
                    w = 1.0
                elif freq <= 16.0:
                    w = 5.0 / freq
                elif freq <= 80.0:
                    w = (5.0 / 16.0) * (16.0 / freq)
                else:
                    w = 0
                weighted[i] = psd[i] * w**2
        
        return weighted
    
    @staticmethod
    def stft_spectrogram(data: np.ndarray, fs: float = 512.0,
                         window_size: float = 1.0, overlap: float = 0.75
                         ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """短时傅里叶变换 → 时频谱 S(t,f)"""
        nperseg = int(window_size * fs)
        f, t, Sxx = signal.spectrogram(data, fs, window='hann',
                                        nperseg=nperseg,
                                        noverlap=int(nperseg * overlap),
                                        scaling='density')
        return f, t, Sxx
    
    @staticmethod
    def srs_maximax(acc: np.ndarray, fs: float = 512.0,
                    fn: np.ndarray = None, Q: float = 10.0) -> np.ndarray:
        """冲击响应谱 (Smallwood递推算法, Maximax)"""
        if fn is None:
            fn = np.logspace(np.log10(0.5), np.log10(100), 60)  # 0.5-100Hz, 60点
        
        dt = 1.0 / fs
        zeta = 1.0 / (2.0 * Q)
        srs = np.zeros(len(fn))
        
        for i, f in enumerate(fn):
            omega_n = 2.0 * np.pi * f
            omega_d = omega_n * np.sqrt(1.0 - zeta**2)
            
            # SDOF impulse response
            E = np.exp(-zeta * omega_n * dt)
            K = omega_n * dt * E / np.sqrt(1.0 - zeta**2)
            C = E * np.cos(omega_d * dt)
            S = E * np.sin(omega_d * dt)
            
            # Smallwood递推
            b1 = 2.0 * C
            b2 = -E**2
            a0 = 1.0 - K * S
            a1 = K * S - E * (S / omega_d / dt + C)
            
            resp = np.zeros(len(acc))
            for j in range(2, len(acc)):
                resp[j] = (b1 * resp[j-1] + b2 * resp[j-2] + 
                          a0 * acc[j] + a1 * acc[j-1])
            
            srs[i] = np.max(np.abs(resp))
        
        return fn, srs
    
    @staticmethod
    def rainflow_counting(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """雨流计数法 (ASTM E1049 四峰谷法)"""
        # Extract peaks and valleys
        peaks = []
        valleys = []
        
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append((i, data[i]))
            elif data[i] < data[i-1] and data[i] < data[i+1]:
                valleys.append((i, data[i]))
        
        if len(peaks) < 2 or len(valleys) < 2:
            return np.array([]), np.array([]), np.array([])
        
        # Merge peaks and valleys into sequence
        all_points = sorted(peaks + valleys, key=lambda x: x[0])
        extrema = np.array([p[1] for p in all_points])
        
        # Rainflow counting
        cycles = []
        i = 0
        while i < len(extrema) - 3:
            y1, y2, y3, y4 = extrema[i:i+4]
            if abs(y2 - y1) <= abs(y3 - y2):
                amp = abs(y2 - y1) / 2.0
                mean = (y1 + y2) / 2.0
                cycles.append((amp, mean))
                extrema = np.delete(extrema, [i, i+1])
                i = max(0, i - 2)
            else:
                i += 1
        
        # Process remaining points as half-cycles
        for j in range(0, len(extrema) - 1, 2):
            if j + 1 < len(extrema):
                amp = abs(extrema[j+1] - extrema[j]) / 2.0
                mean = (extrema[j] + extrema[j+1]) / 2.0
                cycles.append((amp * 0.5, mean))
        
        if not cycles:
            return np.array([]), np.array([]), np.array([])
        
        cycles = np.array(cycles)
        amplitudes = cycles[:, 0]
        means = cycles[:, 1]
        counts = np.ones(len(amplitudes))
        
        return amplitudes, means, counts


# ============================================================================
# 第四层映射: 算子 → 考核指标
# ============================================================================

class IndicatorCalculator:
    """考核指标计算器"""
    
    def __init__(self, ops: SignalOperators = None):
        self.ops = ops or SignalOperators()
    
    # ---- 时域指标 ----
    
    def calc_peak_acceleration(self, imu: IMUDataFrame) -> Dict:
        """ACC-PEAK: 三轴峰值加速度"""
        a_mag = imu.a_mag
        t_peak = imu.rel_time[np.argmax(a_mag)]
        return {
            'ACC_X_PEAK_g': float(np.max(np.abs(imu.ax)) / 9.81),
            'ACC_Y_PEAK_g': float(np.max(np.abs(imu.ay)) / 9.81),
            'ACC_Z_PEAK_g': float(np.max(np.abs(imu.az)) / 9.81),
            'ACC_MAG_PEAK_g': float(np.max(a_mag) / 9.81),
            't_peak_s': float(t_peak),
        }
    
    def calc_jerk(self, imu: IMUDataFrame) -> Dict:
        """JERK: 加速度变化率"""
        dt = 1.0 / imu.fs
        jerk_x = np.diff(imu.ax) / dt
        jerk_y = np.diff(imu.ay) / dt
        jerk_z = np.diff(imu.az) / dt
        return {
            'JERK_X_MAX_g_s': float(np.max(np.abs(jerk_x)) / 9.81),
            'JERK_Y_MAX_g_s': float(np.max(np.abs(jerk_y)) / 9.81),
            'JERK_Z_MAX_g_s': float(np.max(np.abs(jerk_z)) / 9.81),
        }
    
    def calc_displacement(self, imu: IMUDataFrame) -> Dict:
        """DISP: 积分位移 (需高通滤波去除漂移)"""
        dt = 1.0 / imu.fs
        # 0.5Hz高通滤波
        b, a = signal.butter(2, 0.5 / (imu.fs/2), btype='high')
        
        def integrate(acc):
            acc_f = signal.filtfilt(b, a, acc)
            vel = np.cumsum(acc_f) * dt
            vel_f = signal.filtfilt(b, a, vel)
            disp = np.cumsum(vel_f) * dt
            return disp * 1000  # m → mm
        
        dx = integrate(imu.ax)
        dy = integrate(imu.ay)
        dz = integrate(imu.az)
        d_mag = np.sqrt(dx**2 + dy**2 + dz**2)
        
        return {
            'DISP_X_MAX_mm': float(np.max(np.abs(dx))),
            'DISP_Y_MAX_mm': float(np.max(np.abs(dy))),
            'DISP_Z_MAX_mm': float(np.max(np.abs(dz))),
            'DISP_3D_MAX_mm': float(np.max(d_mag)),
        }
    
    def calc_hic15(self, imu: IMUDataFrame) -> Dict:
        """HIC15: 头部损伤指标 (15ms窗口)"""
        a_mag = imu.a_mag / 9.81  # 转换为g
        dt = 1.0 / imu.fs
        win_samples = int(0.015 / dt)  # 15ms
        
        if win_samples < 1:
            return {'HIC15': 0.0, 't_HIC15_s': 0.0}
        
        hic_max = 0.0
        t_hic = 0.0
        
        for i in range(len(a_mag) - win_samples):
            window = a_mag[i:i+win_samples]
            a_avg = np.mean(window)
            t1 = imu.rel_time[i]
            t2 = imu.rel_time[i + win_samples - 1]
            dt_window = t2 - t1
            if dt_window > 0:
                hic = dt_window * (a_avg)**2.5
                if hic > hic_max:
                    hic_max = hic
                    t_hic = t1
        
        return {'HIC15': float(hic_max), 't_HIC15_s': float(t_hic)}
    
    # ---- 频域指标 (振动舒适度) ----
    
    def calc_seat(self, imu_seat: IMUDataFrame, imu_base: IMUDataFrame,
                  axis: str = 'z') -> Dict:
        """SEAT因子:座椅有效振幅传递率"""
        # 选择对应轴的数据
        axis_map = {'x': (0, 0), 'y': (1, 1), 'z': (2, 2)}
        idx_s, idx_b = axis_map[axis]
        
        seat_data = imu_seat.get_vector()[:, idx_s]
        base_data = imu_base.get_vector()[:, idx_b]
        
        # PSD + 频率加权
        f, psd_seat = self.ops.welch_psd(seat_data, imu_seat.fs)
        _, psd_base = self.ops.welch_psd(base_data, imu_base.fs)
        
        psd_seat_w = self.ops.frequency_weighting(psd_seat, f, axis)
        psd_base_w = self.ops.frequency_weighting(psd_base, f, axis)
        
        # SEAT = sqrt(∫加权PSD_seat / ∫加权PSD_base)
        integral_seat = np.trapz(psd_seat_w, f)
        integral_base = np.trapz(psd_base_w, f)
        
        seat_val = np.sqrt(integral_seat / integral_base) if integral_base > 0 else np.nan
        
        return {f'SEAT_{axis.upper()}': float(seat_val)}
    
    def calc_vdv(self, imu: IMUDataFrame, axis: str = 'z') -> Dict:
        """VDV: 振动剂量值"""
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
        a = imu.get_vector()[:, axis_idx]
        
        # 频率加权 (简化为时域滤波)
        nyq = imu.fs / 2.0
        if axis == 'z':
            b_w, a_w = signal.butter(2, [0.4/nyq, 100.0/nyq], btype='band')
        else:
            b_w, a_w = signal.butter(2, [0.5/nyq, 100.0/nyq], btype='band')
        
        a_w = signal.filtfilt(b_w, a_w, a)
        dt = 1.0 / imu.fs
        vdv = (np.sum(a_w**4) * dt)**0.25
        
        return {f'VDV_{axis.upper()}_m_s175': float(vdv)}
    
    def calc_tr(self, imu_seat: IMUDataFrame, imu_base: IMUDataFrame,
                axis: str = 'z') -> Dict:
        """TR: 振动传递率 (频率函数)"""
        axis_map = {'x': (0, 0), 'y': (1, 1), 'z': (2, 2)}
        idx_s, idx_b = axis_map[axis]
        
        f, psd_seat = self.ops.welch_psd(imu_seat.get_vector()[:, idx_s], imu_seat.fs)
        _, psd_base = self.ops.welch_psd(imu_base.get_vector()[:, idx_b], imu_base.fs)
        
        tr_db = 20 * np.log10(np.sqrt(psd_seat / psd_base + 1e-12))
        
        return {
            f'TR_{axis.upper()}_peak_dB': float(np.max(tr_db[(f >= 0.5) & (f <= 50)])),
            f'TR_{axis.upper()}_peak_freq_Hz': float(f[np.argmax(tr_db)]),
            f'TR_{axis.upper()}_freq': f.tolist(),
            f'TR_{axis.upper()}_dB': tr_db.tolist(),
        }
    
    # ---- 瞬态冲击指标 ----
    
    def calc_srs_indicators(self, imu: IMUDataFrame, axis: str = 'x') -> Dict:
        """SRS冲击响应谱指标"""
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
        a = imu.get_vector()[:, axis_idx]
        
        fn, srs = self.ops.srs_maximax(a, imu.fs)
        a_peak = np.max(np.abs(a))
        
        # 关键频段 (5-30Hz人体敏感)
        mask = (fn >= 5) & (fn <= 30)
        srs_band = srs[mask] if np.any(mask) else srs
        
        return {
            f'SRS_{axis.upper()}_PEAK_m_s2': float(np.max(srs)),
            f'SRS_{axis.upper()}_PEAK_freq_Hz': float(fn[np.argmax(srs)]),
            f'SRS_{axis.upper()}_Q': float(np.max(srs) / (a_peak + 1e-12)),
            f'SRS_{axis.upper()}_AVG_5_30Hz_m_s2': float(np.mean(srs_band)),
            f'SRS_{axis.upper()}_fn': fn.tolist(),
            f'SRS_{axis.upper()}_values': srs.tolist(),
        }
    
    # ---- 疲劳损伤指标 ----
    
    def calc_fds(self, imu: IMUDataFrame, axis: str = 'z',
                 b: float = 8.0, k: float = 4.0) -> Dict:
        """FDS: 疲劳损伤谱"""
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
        a = imu.get_vector()[:, axis_idx]
        
        amps, means, counts = self.ops.rainflow_counting(a)
        
        if len(amps) == 0:
            return {f'FDS_{axis.upper()}_D': 0.0, f'FDS_{axis.upper()}_LEQ_g': 0.0}
        
        # Miner累积损伤
        ni = counts
        Ni = k * (amps + 1e-12)**(-b)  # S-N曲线
        D = np.sum(ni / Ni)
        
        # 等效损伤载荷
        leq = (np.sum(counts * (amps/9.81)**k) / np.sum(counts))**(1.0/k)
        
        return {
            f'FDS_{axis.upper()}_D': float(D),
            f'FDS_{axis.upper()}_LEQ_g': float(leq),
            f'FDS_{axis.upper()}_n_cycles': int(np.sum(counts)),
            f'FDS_{axis.upper()}_max_amp_g': float(np.max(amps) / 9.81),
        }
    
    # ---- 时频域指标 ----
    
    def calc_stft_indicators(self, imu: IMUDataFrame, axis: str = 'y') -> Dict:
        """STFT时频域指标"""
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[axis]
        a = imu.get_vector()[:, axis_idx]
        
        f, t, Sxx = self.ops.stft_spectrogram(a, imu.fs)
        
        # 瞬时频率重心
        fc_t = np.zeros(len(t))
        for j in range(len(t)):
            if np.sum(Sxx[:, j]) > 0:
                fc_t[j] = np.sum(f * Sxx[:, j]) / np.sum(Sxx[:, j])
        
        # 时频峭度
        kt_t = np.zeros(len(t))
        for j in range(len(t)):
            s = Sxx[:, j]
            m2 = np.mean(s**2)
            m4 = np.mean(s**4)
            if m2 > 0:
                kt_t[j] = m4 / (m2**2) - 2
        
        mask_valid = fc_t > 0
        
        return {
            f'STFT_FC_MEAN_Hz': float(np.mean(fc_t[mask_valid])) if np.any(mask_valid) else 0.0,
            f'STFT_FC_STD_Hz': float(np.std(fc_t[mask_valid])) if np.any(mask_valid) else 0.0,
            f'STFT_FC_DRIFT_Hz': float(fc_t[-1] - fc_t[0]) if mask_valid[0] and mask_valid[-1] else 0.0,
            f'STFT_KT_MAX': float(np.max(kt_t)),
            f'STFT_KT_MEAN': float(np.mean(kt_t)),
            f'STFT_t': t.tolist(),
            f'STFT_fc_t': fc_t.tolist(),
        }
    
    # ---- ISO 2631-5 脊柱健康 ----
    
    def calc_iso2631_5_sd(self, imu: IMUDataFrame,
                          weight: float = 75.0,
                          backrest_angle: float = 23.0) -> Dict:
        """ISO 2631-5 腰椎压缩应力 S_d"""
        from scipy.signal import lti, lsim
        
        dt = 1.0 / imu.fs
        
        # 步骤1: 靠背倾角空间旋转
        theta = np.radians(backrest_angle)
        ct, st = np.cos(theta), np.sin(theta)
        ax_h = imu.ax * ct - imu.az * st
        ay_h = imu.ay
        az_h = imu.ax * st + imu.az * ct
        
        # 步骤2: 体重修正
        omega_n_base = 2.0 * np.pi * 9.85
        zeta_base = 0.23
        alpha_m = np.sqrt(75.0 / weight)
        beta_m = np.sqrt(weight / 75.0)
        omega_n = omega_n_base * alpha_m
        zeta = zeta_base * beta_m
        
        # 步骤3: 水平向线性滤波 (X, Y)
        num_h, den_h = [0.0, 1.0], [1.0, 31.4, 400.0]
        sys_h = lti(num_h, den_h)
        _, a_lx, _ = lsim(sys_h, U=ax_h, T=imu.rel_time)
        _, a_ly, _ = lsim(sys_h, U=ay_h, T=imu.rel_time)
        
        # 步骤4: 垂向非线性脊柱压缩
        a_lz = np.zeros(imu.n_samples)
        disp, vel = 0.0, 0.0
        for t in range(1, imu.n_samples):
            u_z = -az_h[t]
            if disp < 0:
                k_mod = 1.0 + 2.0 * (abs(disp) * 1000)
            else:
                k_mod = 1.0
            acc_spinal = u_z - (2.0*zeta*omega_n*vel) - (k_mod*omega_n**2*disp)
            vel += acc_spinal * dt
            disp += vel * dt
            a_lz[t] = acc_spinal
        
        # 步骤5: 峰值提取与六次方剂量
        from scipy.signal import find_peaks
        px, _ = find_peaks(np.abs(a_lx), distance=int(imu.fs * 0.2))
        py, _ = find_peaks(np.abs(a_ly), distance=int(imu.fs * 0.2))
        pz, _ = find_peaks(np.abs(a_lz), distance=int(imu.fs * 0.2))
        
        max_len = min(len(px), len(py), len(pz))
        if max_len == 0:
            return {'S_d_MPa': 0.0, 'S_d_level': '无显著冲击', 'omega_n_Hz': float(omega_n/(2*np.pi))}
        
        cx, cy, cz = 0.018, 0.015, 0.003
        d_k6 = (cx*np.abs(a_lx[px[:max_len]]))**6 + (cy*np.abs(a_ly[py[:max_len]]))**6 + (cz*np.abs(a_lz[pz[:max_len]]))**6
        s_d = np.sum(d_k6)**(1.0/6.0)
        
        if s_d < 0.5:
            level = '绿色: 低风险'
        elif s_d <= 0.8:
            level = '黄色: 中度风险'
        else:
            level = '红色: 高风险'
        
        return {
            'S_d_MPa': float(s_d),
            'S_d_level': level,
            'S_d_n_events': int(max_len),
            'omega_n_Hz': float(omega_n / (2*np.pi)),
        }
    
    # ---- 衰减效率 ----
    
    def calc_attenuation(self, imu_exp: IMUDataFrame, imu_ctrl: IMUDataFrame,
                         indicator_func: Callable, **kwargs) -> Dict:
        """ATTEN: 衰减效率 = (对照-实验)/对照 × 100%"""
        res_ctrl = indicator_func(imu_ctrl, **kwargs)
        res_exp = indicator_func(imu_exp, **kwargs)
        
        atten = {}
        for key in res_ctrl:
            if key in res_exp and isinstance(res_ctrl[key], (int, float)):
                if abs(res_ctrl[key]) > 1e-9:
                    atten[f'ATTEN_{key}_pct'] = float((res_ctrl[key] - res_exp[key]) / res_ctrl[key] * 100)
                else:
                    atten[f'ATTEN_{key}_pct'] = 0.0
        
        return atten


# ============================================================================
# 完整评估引擎
# ============================================================================

class SeatEvaluator:
    """座椅综合评测引擎 — 整合四层映射与全部指标计算"""
    
    def __init__(self):
        self.ops = SignalOperators()
        self.calc = IndicatorCalculator(self.ops)
        self.imus: Dict[str, IMUDataFrame] = {}
        self.results: Dict = {}
    
    def load_imu_data(self, imu_name: str, data_dict: Dict) -> None:
        """加载单个IMU数据
        
        Args:
            imu_name: IMU名称, 如 'IMU7_座椅底部-1'
            data_dict: 包含 rel_time, Ax_m_s2, Ay_m_s2, Az_m_s2, Gx_dps, Gy_dps, Gz_dps 的字典
        """
        # 处理别名
        if imu_name in IMU_ALIASES:
            imu_name = IMU_ALIASES[imu_name]
        
        # 提取数据
        t = np.asarray(data_dict.get('rel_time', [0]))
        ax = np.asarray(data_dict.get('Ax_m_s2', [0]))
        ay = np.asarray(data_dict.get('Ay_m_s2', [0]))
        az = np.asarray(data_dict.get('Az_m_s2', [0]))
        gx = np.asarray(data_dict.get('Gx_dps', [0]))
        gy = np.asarray(data_dict.get('Gy_dps', [0]))
        gz = np.asarray(data_dict.get('Gz_dps', [0]))
        
        self.imus[imu_name] = IMUDataFrame(
            imu_name=imu_name,
            rel_time=t, ax=ax, ay=ay, az=az, gx=gx, gy=gy, gz=gz,
            fs=1.0 / (t[1] - t[0]) if len(t) > 1 else 512.0
        )
    
    def get_imu(self, imu_name: str) -> Optional[IMUDataFrame]:
        """获取IMU数据 (支持别名查找)"""
        if imu_name in self.imus:
            return self.imus[imu_name]
        if imu_name in IMU_ALIASES:
            canonical = IMU_ALIASES[imu_name]
            if canonical in self.imus:
                return self.imus[canonical]
        return None
    
    def get_position(self, imu_name: str) -> Optional[IMUPosition]:
        """获取IMU位置信息"""
        if imu_name in IMU_ALIASES:
            imu_name = IMU_ALIASES[imu_name]
        return IMU_POSITIONS.get(imu_name)
    
    def get_position_pair(self, body_location: str) -> Tuple[Optional[IMUDataFrame], Optional[IMUDataFrame]]:
        """获取同一身体位置的实验组/对照组IMU对"""
        imu_exp = None
        imu_ctrl = None
        for name in self.imus:
            pos = self.get_position(name)
            if pos and pos.body_location == body_location:
                if pos.group == '实验组(A)':
                    imu_exp = self.imus[name]
                else:
                    imu_ctrl = self.imus[name]
        return imu_exp, imu_ctrl
    
    def compute_all_indicators(self) -> Dict:
        """计算全部考核指标"""
        results = {}
        
        # 获取底座参考IMU
        imu_base_exp = self.get_imu('IMU7_座椅底部-1')
        imu_base_ctrl = self.get_imu('IMU8_座椅底部-2')
        
        # 获取座垫IMU
        imu_seat_exp = self.get_imu('IMU5_座垫R点-1')
        imu_seat_ctrl = self.get_imu('IMU6_座垫R点-2')
        
        # 获取头部IMU
        imu_head_exp = self.get_imu('IMU1_头部眉心-1')
        imu_head_ctrl = self.get_imu('IMU2_头部眉心-2')
        
        # 获取躯干IMU
        imu_torso_exp = self.get_imu('IMU3_躯干T8-1')
        imu_torso_ctrl = self.get_imu('IMU4_躯干T8-2')
        
        # ====== M1: AEB紧急制动指标 ======
        results['M1_AEB'] = {}
        for label, imu in [('头部_实验组', imu_head_exp), ('头部_对照组', imu_head_ctrl)]:
            if imu:
                results['M1_AEB'][label] = {
                    'HIC15': self.calc.calc_hic15(imu),
                    'ACC_PEAK': self.calc.calc_peak_acceleration(imu),
                    'JERK': self.calc.calc_jerk(imu),
                }
                for axis in ['x', 'y', 'z']:
                    results['M1_AEB'][label].update(
                        self.calc.calc_srs_indicators(imu, axis)
                    )
        
        # ====== M2: 蛇形驾驶/变道指标 ======
        results['M2_SLALOM'] = {}
        for label, imu in [('躯干_实验组', imu_torso_exp), ('躯干_对照组', imu_torso_ctrl)]:
            if imu:
                results['M2_SLALOM'][label] = {}
                for axis in ['x', 'y']:
                    results['M2_SLALOM'][label].update(
                        self.calc.calc_stft_indicators(imu, axis)
                    )
        
        # ====== M3: 位移指标 ======
        results['M3_DISPLACEMENT'] = {}
        for label, imu in [('头部_实验组', imu_head_exp), ('头部_对照组', imu_head_ctrl),
                            ('躯干_实验组', imu_torso_exp), ('躯干_对照组', imu_torso_ctrl)]:
            if imu:
                results['M3_DISPLACEMENT'][label] = self.calc.calc_displacement(imu)
        
        # 衰减效率
        if imu_head_exp and imu_head_ctrl:
            results['M3_DISPLACEMENT']['ATTEN_头部'] = self.calc.calc_attenuation(
                imu_head_exp, imu_head_ctrl, self.calc.calc_displacement
            )
        
        # ====== M4: 振动台舒适度指标 ======
        results['M4_VIBRATION'] = {}
        for label, (imu_s, imu_b) in [
            ('实验组', (imu_seat_exp, imu_base_exp)),
            ('对照组', (imu_seat_ctrl, imu_base_ctrl))
        ]:
            if imu_s and imu_b:
                results['M4_VIBRATION'][label] = {}
                for axis in ['x', 'y', 'z']:
                    results['M4_VIBRATION'][label].update(
                        self.calc.calc_seat(imu_s, imu_b, axis)
                    )
                    results['M4_VIBRATION'][label].update(
                        self.calc.calc_vdv(imu_s, axis)
                    )
                    results['M4_VIBRATION'][label].update(
                        self.calc.calc_tr(imu_s, imu_b, axis)
                    )
                
                # 多轴总值 OVTV
                ovtv_x = results['M4_VIBRATION'][label].get('VDV_X_m_s175', 0)
                ovtv_y = results['M4_VIBRATION'][label].get('VDV_Y_m_s175', 0)
                ovtv_z = results['M4_VIBRATION'][label].get('VDV_Z_m_s175', 0)
                results['M4_VIBRATION'][label]['OVTV'] = np.sqrt(1.4**2*ovtv_x**2 + 1.4**2*ovtv_y**2 + ovtv_z**2)
        
        # ====== C3: 脊柱健康 ======
        results['C3_SPINE'] = {}
        for label, imu in [('实验组_标准', imu_seat_exp), ('对照组_标准', imu_seat_ctrl)]:
            if imu:
                results['C3_SPINE'][label] = self.calc.calc_iso2631_5_sd(imu, weight=75, backrest_angle=23)
        
        # ====== FDS: 疲劳损伤 ======
        results['FDS_FATIGUE'] = {}
        for label, imu in [('座垫_实验组', imu_seat_exp), ('座垫_对照组', imu_seat_ctrl),
                            ('底座_实验组', imu_base_exp), ('底座_对照组', imu_base_ctrl)]:
            if imu:
                results['FDS_FATIGUE'][label] = {}
                for axis in ['x', 'y', 'z']:
                    results['FDS_FATIGUE'][label].update(
                        self.calc.calc_fds(imu, axis)
                    )
        
        self.results = results
        return results
    
    def print_summary(self) -> None:
        """打印评估摘要"""
        if not self.results:
            self.compute_all_indicators()
        
        print("=" * 70)
        print("  乘用车座椅综合性能评测 — 考核指标计算摘要")
        print("=" * 70)
        
        # M1: AEB
        print("\n[M1] AEB紧急制动:")
        m1 = self.results.get('M1_AEB', {})
        for group, data in m1.items():
            if 'HIC15' in data:
                print(f"  {group}: HIC15={data['HIC15']['HIC15']:.1f}")
            if 'ACC_PEAK' in data:
                p = data['ACC_PEAK']
                print(f"          峰值加速度: X={p['ACC_X_PEAK_g']:.2f}g Y={p['ACC_Y_PEAK_g']:.2f}g Z={p['ACC_Z_PEAK_g']:.2f}g")
        
        # M4: Vibration
        print("\n[M4] 振动舒适度:")
        m4 = self.results.get('M4_VIBRATION', {})
        for group, data in m4.items():
            if 'SEAT_Z' in data:
                print(f"  {group}: SEAT_Z={data['SEAT_Z']:.3f}, VDV_Z={data.get('VDV_Z_m_s175', 0):.3f}, OVTV={data.get('OVTV', 0):.3f}")
        
        # C3: Spine
        print("\n[C3] 脊柱健康:")
        c3 = self.results.get('C3_SPINE', {})
        for group, data in c3.items():
            print(f"  {group}: S_d={data['S_d_MPa']:.4f} MPa ({data['S_d_level']})")
        
        # FDS
        print("\n[FDS] 疲劳损伤:")
        fds = self.results.get('FDS_FATIGUE', {})
        for group, data in fds.items():
            if 'FDS_Z_D' in data:
                print(f"  {group}: D_Z={data['FDS_Z_D']:.6f}, LEQ_Z={data['FDS_Z_LEQ_g']:.3f}g, N={data['FDS_Z_n_cycles']}")
        
        print("=" * 70)
    
    def print_mapping(self) -> None:
        """打印四层映射关系"""
        print("\n" + "=" * 80)
        print("  四层映射: 数据源 → 位置 → 数据字段 → 算子 → 考核指标")
        print("=" * 80)
        
        for imu_name in sorted(IMU_POSITIONS.keys(), key=lambda n: IMU_POSITIONS[n].imu_id):
            pos = IMU_POSITIONS[imu_name]
            print(f"\n  [{pos.imu_id}] {pos.imu_name} | ch={pos.channel} | 组别={pos.group}")
            print(f"       位置={pos.body_location} {'(底座参考)' if pos.is_base else ''}")
            print(f"       字段: Ax_m_s2, Ay_m_s2, Az_m_s2, Gx_dps, Gy_dps, Gz_dps, rel_time")
    
    def export_results_json(self, filepath: str) -> None:
        """导出结果为JSON"""
        import json
        
        # 清理numpy类型
        def convert(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(v) for v in obj]
            return obj
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(convert(self.results), f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已导出: {filepath}")


# ============================================================================
# 快速测试
# ============================================================================

if __name__ == '__main__':
    print("乘用车座椅综合评测 — IMU考核指标计算引擎 V1.0")
    print("=" * 60)
    
    # 生成模拟数据验证
    fs = 512
    t = np.linspace(0, 5, 5 * fs)
    
    # 模拟AEB制动: 0-1g纵向减速度 + 垂向振动
    sim_z = 0.1 * np.random.randn(len(t))  # 随机振动基底
    sim_x = np.zeros_like(t)
    sim_y = 0.05 * np.sin(2 * np.pi * 2 * t)  # 侧向小幅摆动
    
    # 在t=2-3.5s施加AEB: -0.8g纵向减速度
    brake_start = int(2 * fs)
    brake_end = int(3.5 * fs)
    sim_x[brake_start:brake_end] = -0.8 * 9.81  # -0.8g
    
    # 叠加减速带冲击 (t=4s)
    bump_start = int(4 * fs)
    bump_end = int(4.15 * fs)
    sim_z[bump_start:bump_end] += 25 * np.sin(np.pi * (t[bump_start:bump_end] - 4) / 0.15)
    
    # 角速度 (制动俯仰)
    sim_gy = np.zeros_like(t)
    sim_gy[brake_start:brake_end] = 50 * (1 - np.exp(-(t[brake_start:brake_end] - 2) / 0.5))
    
    # 加载到评估引擎
    evaluator = SeatEvaluator()
    
    evaluator.load_imu_data('IMU1_头部眉心-1', {
        'rel_time': t, 'Ax_m_s2': sim_x, 'Ay_m_s2': sim_y, 'Az_m_s2': sim_z,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU2_头部眉心-2', {
        'rel_time': t, 'Ax_m_s2': sim_x * 1.3, 'Ay_m_s2': sim_y * 1.3, 'Az_m_s2': sim_z * 1.3,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 1.3, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU3_躯干T8-1', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.7, 'Ay_m_s2': sim_y * 0.7, 'Az_m_s2': sim_z * 0.7,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.7, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU4_躯干T8-2', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.9, 'Ay_m_s2': sim_y * 0.9, 'Az_m_s2': sim_z * 0.9,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.9, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU5_座垫R点-1', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.5, 'Ay_m_s2': sim_y * 0.5, 'Az_m_s2': sim_z * 0.5,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.5, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU6_座垫R点-2', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.6, 'Ay_m_s2': sim_y * 0.6, 'Az_m_s2': sim_z * 0.6,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.6, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU7_座椅底部-1', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.2, 'Ay_m_s2': sim_y * 0.2, 'Az_m_s2': sim_z * 0.2,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.2, 'Gz_dps': np.zeros_like(t),
    })
    evaluator.load_imu_data('IMU8_座椅底部-2', {
        'rel_time': t, 'Ax_m_s2': sim_x * 0.25, 'Ay_m_s2': sim_y * 0.25, 'Az_m_s2': sim_z * 0.25,
        'Gx_dps': np.zeros_like(t), 'Gy_dps': sim_gy * 0.25, 'Gz_dps': np.zeros_like(t),
    })
    
    # 计算全部指标
    evaluator.compute_all_indicators()
    
    # 打印映射和结果
    evaluator.print_mapping()
    evaluator.print_summary()
    
    # 导出JSON
    evaluator.export_results_json('/tmp/test_results.json')
    
    print("\n✓ 引擎验证通过")
