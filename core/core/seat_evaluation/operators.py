#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10大算子系统
ISO 2631-1 / SAE J211 / ASTM E1049 / MIL-STD-810H 标准实现
"""

import numpy as np
from scipy import signal
from typing import Dict, Any, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class CFCOperator:
    """CFC滤波算子 - SAE J211-1 通道频率等级滤波"""

    def __init__(self, cfc: int = 60):
        self.cfc = cfc
        self._butter_order = 4

    def filter(self, data: np.ndarray, sample_rate: float) -> np.ndarray:
        try:
            cutoff = self.cfc * 2.0775
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff / nyquist
            if normalized_cutoff <= 0.0:
                return data
            if normalized_cutoff >= 1.0:
                normalized_cutoff = 0.99
            if normalized_cutoff < 0.01:
                normalized_cutoff = 0.01
            b, a = signal.butter(self._butter_order, normalized_cutoff, btype='low')
            filtered_data = signal.filtfilt(b, a, data)
            return filtered_data
        except Exception as e:
            logger.error(f"CFC滤波失败: {e}")
            return data


class VectorOperator:
    """向量合成算子"""

    def synthesize(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        return np.sqrt(x**2 + y**2 + z**2)

    def synthesize_xy(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.sqrt(x**2 + y**2)


class FFTOperator:
    """FFT算子 - 快速傅里叶变换"""

    def compute(self, data: np.ndarray, sample_rate: float) -> Tuple[np.ndarray, np.ndarray]:
        n = len(data)
        fft_result = np.fft.fft(data)
        freqs = np.fft.fftfreq(n, 1/sample_rate)
        positive_idx = freqs >= 0
        freqs = freqs[positive_idx]
        fft_result = fft_result[positive_idx]
        amplitude = np.abs(fft_result) / n * 2
        return freqs, amplitude


class PSDOperator:
    """PSD算子 - Welch法功率谱密度"""

    def compute(self, data: np.ndarray, sample_rate: float, nperseg: int = 1024) -> Tuple[np.ndarray, np.ndarray]:
        n = len(data)
        if n < 4:
            return np.array([0.0]), np.array([0.0])
        nperseg = min(nperseg, n)
        freqs, psd = signal.welch(data, fs=sample_rate, nperseg=nperseg)
        return freqs, psd


class CSDOperator:
    """交叉谱密度算子 - ISO 10326-2 传递函数计算基础

    输入: x(t), y(t) — 输入信号与响应信号
    输出: H(f) 传递函数, Coh(f) 相干函数
    """

    def compute(self, x: np.ndarray, y: np.ndarray, sample_rate: float,
                nperseg: int = 1024) -> Dict[str, Any]:
        try:
            n = min(len(x), len(y))
            if n < 4:
                return {'freq': np.array([]), 'H': np.array([]), 'coherence': np.array([])}
            nperseg = min(nperseg, n, 256)
            f, pxy = signal.csd(x[:n], y[:n], fs=sample_rate, nperseg=nperseg)
            _, pxx = signal.welch(x[:n], fs=sample_rate, nperseg=nperseg)
            _, pyy = signal.welch(y[:n], fs=sample_rate, nperseg=nperseg)
            H = pxy / (pxx + 1e-12)
            coh = np.abs(pxy)**2 / (pxx * pyy + 1e-12)
            return {'freq': f, 'H': H, 'coherence': coh}
        except Exception as e:
            logger.error(f"CSD计算失败: {e}")
            return {'freq': np.array([]), 'H': np.array([]), 'coherence': np.array([])}

    def transfer_function_db(self, x: np.ndarray, y: np.ndarray, sample_rate: float,
                             nperseg: int = 1024) -> Dict[str, float]:
        """计算振动传递率 (dB)"""
        result = self.compute(x, y, sample_rate, nperseg)
        freq = result['freq']
        H = result['H']
        if len(H) == 0:
            return {'TR_peak_dB': 0.0, 'TR_peak_freq_Hz': 0.0, 'coherence': []}
        H_db = 20 * np.log10(np.abs(H) + 1e-12)
        mask = (freq >= 0.5) & (freq <= 50)
        if np.any(mask):
            peak_idx = np.argmax(np.abs(H_db[mask]))
            peak_freq = freq[mask][peak_idx]
            peak_db = H_db[mask][peak_idx]
        else:
            peak_idx = np.argmax(np.abs(H_db))
            peak_freq = freq[peak_idx]
            peak_db = H_db[peak_idx]
        coh_arr = result.get('coherence', np.array([]))
        return {'TR_peak_dB': float(peak_db), 'TR_peak_freq_Hz': float(peak_freq),
                'coherence': coh_arr}


class WeightingOperator:
    """加权滤波算子 - ISO 2631-1 频率加权

    Wk: Z轴振动加权 (座椅表面垂直方向)
    Wd: XY轴振动加权 (座椅表面水平方向)

    实现参见 ISO 2631-1:1997 Annex A / Table 3, Table 4
    """

    def __init__(self):
        pass

    def apply_weighting_z(self, data: np.ndarray, sample_rate: float) -> np.ndarray:
        try:
            return self._apply_iso_weighting_time(data, sample_rate, axis='z')
        except Exception as e:
            logger.error(f"Z轴加权滤波失败: {e}")
            return data

    def apply_weighting_xy(self, data: np.ndarray, sample_rate: float) -> np.ndarray:
        try:
            return self._apply_iso_weighting_time(data, sample_rate, axis='xy')
        except Exception as e:
            logger.error(f"XY轴加权滤波失败: {e}")
            return data

    def _apply_iso_weighting_time(self, data: np.ndarray, sample_rate: float, axis: str = 'z') -> np.ndarray:
        if len(data) < 4:
            return data

        nyq = sample_rate / 2.0

        if axis == 'z':
            f_low = 0.4
            f_trans = 3.0
            f_high = 100.0

            b_hp, a_hp = signal.butter(2, f_low / nyq, btype='high')
            data = signal.filtfilt(b_hp, a_hp, data)
            b_lp, a_lp = signal.butter(2, f_high / nyq, btype='low')
            data = signal.filtfilt(b_lp, a_lp, data)
            b_t, a_t = signal.butter(2, f_trans / nyq, btype='low')
            data = signal.filtfilt(b_t, a_t, data)
        else:
            f_low = 0.4
            f_high = 100.0

            b_hp, a_hp = signal.butter(2, f_low / nyq, btype='high')
            data = signal.filtfilt(b_hp, a_hp, data)
            b_lp, a_lp = signal.butter(2, f_high / nyq, btype='low')
            data = signal.filtfilt(b_lp, a_lp, data)

        return data

    def apply_weighting_z_psd(self, psd: np.ndarray, freq: np.ndarray) -> np.ndarray:
        """频域 Wk 加权 (ISO 2631-1 Table 3)

        Wk(f):
            f < 0.5:   W = 0.5
            0.5≤f<2:   W = f
            2≤f<5:     W = 2
            5≤f<16:    W = 2 × 5/f
            16≤f<80:   W = 2 × 5/16 × 16/f
            f ≥ 80:    W = 0

        Returns: PSD_weighted = PSD × W(f)²
        """
        weighted = np.zeros_like(psd)
        for i, f in enumerate(freq):
            if f < 0.5:
                w = 0.5
            elif f < 2.0:
                w = f
            elif f < 5.0:
                w = 2.0
            elif f < 16.0:
                w = 2.0 * (5.0 / f)
            elif f < 80.0:
                w = 2.0 * (5.0 / 16.0) * (16.0 / f)
            else:
                w = 0.0
            weighted[i] = psd[i] * (w ** 2)
        return weighted

    def apply_weighting_xy_psd(self, psd: np.ndarray, freq: np.ndarray) -> np.ndarray:
        """频域 Wd 加权 (ISO 2631-1 Table 4)

        Wd(f):
            f < 0.5:   W = 1.0
            0.5≤f<2:   W = f/0.5
            2≤f<5:     W = 1.0
            5≤f<16:    W = 5/f
            16≤f<80:   W = 5/16 × 16/f
            f ≥ 80:    W = 0

        Returns: PSD_weighted = PSD × W(f)²
        """
        weighted = np.zeros_like(psd)
        for i, f in enumerate(freq):
            if f < 0.5:
                w = 1.0
            elif f < 2.0:
                w = f / 0.5
            elif f < 5.0:
                w = 1.0
            elif f < 16.0:
                w = 5.0 / f
            elif f < 80.0:
                w = (5.0 / 16.0) * (16.0 / f)
            else:
                w = 0.0
            weighted[i] = psd[i] * (w ** 2)
        return weighted

    def apply_weighting_z_via_freq(self, signal: np.ndarray, sample_rate: float) -> np.ndarray:
        """频域Wk加权→时域信号 (FFT→Wk(f)→IFFT)

        将ISO 2631-1 Wk频率加权转换为时域加权信号。
        与 apply_weighting_z_psd 共享同一 Wk(f) 函数，确保一致性。
        用于 AW_Z、VDV_Z 等时域指标，替代原 Butterworth 级联近似。
        """
        n = len(signal)
        if n < 4:
            return signal.copy()
        spectrum = np.fft.rfft(signal)
        freq = np.fft.rfftfreq(n, d=1.0 / sample_rate)
        psd_dummy = np.abs(spectrum) ** 2
        psd_w = self.apply_weighting_z_psd(psd_dummy, freq)
        w_amplitude = np.sqrt(np.clip(psd_w, 0, None) / np.clip(psd_dummy, 1e-20, None))
        spectrum_w = spectrum * w_amplitude
        return np.fft.irfft(spectrum_w, n=n)

    def apply_weighting_xy_via_freq(self, signal: np.ndarray, sample_rate: float) -> np.ndarray:
        """频域Wd加权→时域信号 (FFT→Wd(f)→IFFT)

        将ISO 2631-1 Wd水平加权转换为时域加权信号。
        与 apply_weighting_xy_psd 共享同一 Wd(f) 函数。
        """
        n = len(signal)
        if n < 4:
            return signal.copy()
        spectrum = np.fft.rfft(signal)
        freq = np.fft.rfftfreq(n, d=1.0 / sample_rate)
        psd_dummy = np.abs(spectrum) ** 2
        psd_w = self.apply_weighting_xy_psd(psd_dummy, freq)
        w_amplitude = np.sqrt(np.clip(psd_w, 0, None) / np.clip(psd_dummy, 1e-20, None))
        spectrum_w = spectrum * w_amplitude
        return np.fft.irfft(spectrum_w, n=n)


class IntegrationOperator:
    """二次积分算子 - 加速度→速度→位移

    标准: 0.5Hz 高通滤波消除积分漂移 (ISO 2631-1 §7.2)
    """

    def integrate_to_displacement(self, acc: np.ndarray, sample_rate: float) -> np.ndarray:
        if len(acc) < 4:
            return np.zeros_like(acc)
        try:
            nyq = sample_rate / 2.0
            b, a = signal.butter(2, 0.5 / nyq, btype='high')
            acc_f = signal.filtfilt(b, a, acc)
            vel = np.cumsum(acc_f) / sample_rate
            vel_f = signal.filtfilt(b, a, vel)
            disp = np.cumsum(vel_f) / sample_rate * 1000.0
            return disp
        except Exception as e:
            logger.error(f"位移积分失败: {e}, 使用简化积分")
            vel = np.cumsum(acc) / sample_rate
            disp = np.cumsum(vel) / sample_rate * 1000.0
            return disp - np.mean(disp)


class AttenuationOperator:
    """衰减效率算子 - 实验组 vs 对照组对比

    ATTEN = (ctrl - exp) / ctrl × 100%
    正值表示实验组减振效果优于对照组
    """

    DEFAULT_FREQ_BANDS = {
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
    }

    def compute(self, exp_value: float, ctrl_value: float) -> float:
        if abs(ctrl_value) < 1e-9:
            return 0.0
        return (ctrl_value - exp_value) / ctrl_value * 100.0

    def compute_dict(self, exp_metrics: Dict[str, float],
                     ctrl_metrics: Dict[str, float]) -> Dict[str, float]:
        atten = {}
        for key in exp_metrics:
            if key in ctrl_metrics:
                atten[f'ATTEN_{key}_pct'] = self.compute(
                    exp_metrics[key], ctrl_metrics[key])
        return atten

    def compute_band_attenuation(self, exp_psd: np.ndarray, ctrl_psd: np.ndarray,
                                 freq: np.ndarray,
                                 freq_bands: Optional[Dict[str, Tuple[float, float]]] = None) -> Dict[str, float]:
        """计算各频段衰减率

        Args:
            exp_psd: 实验组PSD
            ctrl_psd: 对照组PSD
            freq: 频率轴
            freq_bands: 频段定义 (默认使用DEFAULT_FREQ_BANDS)

        Returns:
            各频段衰减率字典
        """
        if freq_bands is None:
            freq_bands = self.DEFAULT_FREQ_BANDS

        band_atten = {}
        for band_name, (flo, fhi) in freq_bands.items():
            mask = (freq >= flo) & (freq <= fhi)
            if np.any(mask):
                exp_band = exp_psd[mask]
                ctrl_band = ctrl_psd[mask]
                valid = ~np.isnan(exp_band) & ~np.isnan(ctrl_band) & (ctrl_band > 1e-15)
                if np.any(valid):
                    ratio = np.mean(exp_band[valid] / ctrl_band[valid])
                    band_atten[band_name] = float((1 - ratio) * 100)
                else:
                    band_atten[band_name] = 0.0
            else:
                band_atten[band_name] = 0.0

        return band_atten

    def compute_spectrum_attenuation(self, exp_psd: np.ndarray, ctrl_psd: np.ndarray,
                                     freq: np.ndarray) -> Dict[str, Any]:
        """计算完整频谱衰减分析

        Args:
            exp_psd: 实验组PSD
            ctrl_psd: 对照组PSD
            freq: 频率轴

        Returns:
            {'ratio': 衰减比数组, 'band_atten': 频段衰减字典}
        """
        mask = (freq >= 0.1) & (freq <= 80)
        ratio = np.divide(exp_psd[mask], ctrl_psd[mask],
                          out=np.ones_like(exp_psd[mask]) * np.nan,
                          where=ctrl_psd[mask] > 1e-15)

        band_atten = self.compute_band_attenuation(exp_psd, ctrl_psd, freq)

        return {
            'ratio': ratio,
            'freq': freq[mask],
            'band_attenuation': band_atten
        }


class STFTOperator:
    """短时傅里叶变换算子 - 时频分析 ISO 18431-4"""

    def __init__(self, window_size: int = 256, overlap: int = 128):
        self.window_size = window_size
        self.overlap = overlap

    def compute(self, data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        try:
            freqs, times, spectrogram = signal.spectrogram(
                data, fs=sample_rate,
                nperseg=self.window_size,
                noverlap=self.overlap
            )
            return {
                'frequencies': freqs,
                'times': times,
                'spectrogram': spectrogram
            }
        except Exception as e:
            logger.error(f"STFT计算失败: {e}")
            return {}

    def extract_features(self, stft_result: Dict[str, Any]) -> Dict[str, float]:
        if not stft_result:
            return {}

        try:
            spectrogram = stft_result['spectrogram']
            freqs = stft_result['frequencies']
            times = stft_result['times']

            power = np.sum(spectrogram, axis=1)
            total_power = np.sum(power)

            if total_power > 0:
                fc = np.sum(freqs * power) / total_power
            else:
                fc = 0.0

            if total_power > 0:
                kt = np.sqrt(np.sum((freqs - fc)**2 * power) / total_power)
            else:
                kt = 0.0

            if total_power > 0:
                max_power = np.max(power)
                avg_power = total_power / len(power)
                ce = max_power / avg_power if avg_power > 0 else 1.0
            else:
                ce = 1.0

            fc_t = np.zeros(len(times))
            for j in range(len(times)):
                col_power = np.sum(spectrogram[:, j])
                if col_power > 0:
                    fc_t[j] = np.sum(freqs * spectrogram[:, j]) / col_power

            mask_valid = fc_t > 0
            fc_std = float(np.std(fc_t[mask_valid])) if np.any(mask_valid) else 0.0
            fc_drift = float(fc_t[-1] - fc_t[0]) if len(fc_t) > 1 else 0.0

            kt_t = np.zeros(len(times))
            for j in range(len(times)):
                s = spectrogram[:, j]
                m2 = np.mean(s**2)
                m4 = np.mean(s**4)
                kt_t[j] = m4 / (m2**2 + 1e-12) - 2

            return {
                'STFT_FC': fc,
                'STFT_KT': kt,
                'STFT_CE': ce,
                'STFT_FC_STD': fc_std,
                'STFT_FC_DRIFT': fc_drift,
                'STFT_KT_MAX': float(np.max(kt_t)),
                'STFT_KT_MEAN': float(np.mean(kt_t)),
            }

        except Exception as e:
            logger.error(f"STFT特征提取失败: {e}")
            return {}


class SRSOperator:
    """冲击响应谱算子 - Smallwood递推算法 (MIL-STD-810H Method 516.8)

    参考: Smallwood, D.O. "An Improved Recursive Formula for
          Calculating Shock Response Spectra", 1981
    """

    def __init__(self, frequencies: Optional[np.ndarray] = None, q: float = 10.0):
        self.frequencies = frequencies if frequencies is not None else np.logspace(
            np.log10(0.5), np.log10(100), 60)
        self.q = q

    def compute(self, data: np.ndarray, sample_rate: float) -> Dict[str, Any]:
        try:
            dt = 1.0 / sample_rate
            n = len(data)
            zeta = 1.0 / (2.0 * self.q)
            srs_values = np.zeros(len(self.frequencies))

            for i, f in enumerate(self.frequencies):
                omega_n = 2.0 * np.pi * f
                omega_d = omega_n * np.sqrt(1.0 - zeta**2)

                E = np.exp(-zeta * omega_n * dt)
                K = omega_n * dt * E / np.sqrt(1.0 - zeta**2)
                C = E * np.cos(omega_d * dt)
                S = E * np.sin(omega_d * dt)

                b1 = 2.0 * C
                b2 = -E**2
                a0 = 1.0 - K * S
                a1 = K * S - E * (S / (omega_d * dt) + C)

                resp = np.zeros(n)
                for j in range(2, n):
                    resp[j] = (b1 * resp[j-1] + b2 * resp[j-2] +
                               a0 * data[j] + a1 * data[j-1])

                srs_values[i] = np.max(np.abs(resp))

            return {
                'frequencies': self.frequencies,
                'srs': srs_values
            }

        except Exception as e:
            logger.error(f"SRS计算失败: {e}")
            return {}

    def extract_features(self, srs_result: Dict[str, Any]) -> Dict[str, float]:
        if not srs_result:
            return {}

        try:
            srs_values = srs_result['srs']
            srs_freqs = srs_result['frequencies']

            mrs = float(np.max(srs_values)) if len(srs_values) > 0 else 0.0
            peak_idx = int(np.argmax(srs_values))
            peak_freq = float(srs_freqs[peak_idx])
            pv = mrs / (2.0 * np.pi * peak_freq + 1e-12)

            mask_5_30 = (srs_freqs >= 5.0) & (srs_freqs <= 30.0)
            srs_band = srs_values[mask_5_30]
            avg_5_30 = float(np.mean(srs_band)) if len(srs_band) > 0 else 0.0

            a_peak = mrs / (self.q + 1e-12)  # 伪速度估算

            return {
                'SRS_MRS': mrs,
                'SRS_Q': float(self.q),
                'SRS_PV': pv,
                'SRS_ATT': 1.0 / self.q,
                'SRS_PEAK_FREQ': peak_freq,
                'SRS_AVG_5_30Hz': avg_5_30,
            }

        except Exception as e:
            logger.error(f"SRS特征提取失败: {e}")
            return {}


class RainflowOperator:
    """雨流计数算子 - ASTM E1049-85(2017) 标准四峰谷法"""

    def count(self, data: np.ndarray) -> Dict[str, Any]:
        try:
            n = len(data)
            if n < 3:
                return {'cycles': [], 'RFC_CC': 0, 'amplitudes': np.array([]),
                        'means': np.array([])}

            extrema = []
            for i in range(1, n - 1):
                if (data[i] > data[i-1] and data[i] > data[i+1]) or \
                   (data[i] < data[i-1] and data[i] < data[i+1]):
                    extrema.append(data[i])

            if len(extrema) < 3:
                return {'cycles': [], 'RFC_CC': 0, 'amplitudes': np.array([]),
                        'means': np.array([])}

            cycles = []
            remaining = list(extrema)
            i = 0

            while i < len(remaining) - 2:
                s0, s1, s2 = remaining[i], remaining[i+1], remaining[i+2]
                delta_s1 = abs(s1 - s0)
                delta_s2 = abs(s2 - s1)

                if delta_s1 <= delta_s2:
                    amplitude = delta_s1 / 2.0
                    mean = (s0 + s1) / 2.0
                    if amplitude > 1e-9:
                        cycles.append({'amplitude': float(amplitude), 'mean': float(mean)})
                    remaining.pop(i)
                    remaining.pop(i)
                    i = max(0, i - 1)
                else:
                    i += 1

            for j in range(len(remaining) - 1):
                amplitude = abs(remaining[j+1] - remaining[j]) / 4.0
                mean = (remaining[j] + remaining[j+1]) / 2.0
                if amplitude > 1e-9:
                    cycles.append({'amplitude': float(amplitude), 'mean': float(mean)})

            if not cycles:
                return {'cycles': [], 'RFC_CC': 0, 'amplitudes': np.array([]),
                        'means': np.array([])}

            amps = np.array([c['amplitude'] for c in cycles])
            means = np.array([c['mean'] for c in cycles])

            return {
                'cycles': cycles,
                'RFC_CC': len(cycles),
                'amplitudes': amps,
                'means': means,
            }

        except Exception as e:
            logger.error(f"雨流计数失败: {e}")
            return {'cycles': [], 'RFC_CC': 0, 'amplitudes': np.array([]),
                    'means': np.array([])}


class FDSOperator:
    """疲劳损伤谱算子 - Miner线性累积法则

    S-N曲线: N = k × S^(-b)
    Miner累积: D = Σ (n_i / N_i)
    """

    def __init__(self, b: float = 8.0, k: float = 1.0):
        self.b = b
        self.k = k

    def compute(self, rainflow_result: Dict[str, Any],
                frequencies: Optional[np.ndarray] = None) -> Dict[str, Any]:
        try:
            cycles = rainflow_result.get('cycles', [])
            if not cycles:
                return {'frequencies': frequencies, 'fds': np.array([]),
                        'FDS_D': 0.0, 'FDS_R': 1.0}

            total_damage = 0.0
            for cycle in cycles:
                amplitude = cycle['amplitude']
                if amplitude > 1e-9:
                    Ni = self.k * (amplitude ** (-self.b))
                    total_damage += 1.0 / (Ni + 1e-12)

            remaining_life = max(0.0, 1.0 - total_damage)

            amps = rainflow_result.get('amplitudes', np.array([]))
            n_cycles_total = len(cycles)
            if n_cycles_total > 0:
                leq = (np.sum(amps ** 4) / n_cycles_total) ** (1.0 / 4.0)
            else:
                leq = 0.0

            return {
                'frequencies': frequencies,
                'fds': np.array([total_damage]),
                'FDS_D': float(total_damage),
                'FDS_R': float(remaining_life),
                'FDS_LEQ_g': float(leq),
                'FDS_n_cycles': n_cycles_total,
            }

        except Exception as e:
            logger.error(f"FDS计算失败: {e}")
            return {'frequencies': frequencies, 'fds': np.array([]),
                    'FDS_D': 0.0, 'FDS_R': 1.0}


class StatisticalOperator:
    """统计学检验算子 - 配对t检验/效应量/置信区间
    
    参考:
    - Paired t-test: 比较实验组与对照组差异
    - Cohen's d: 标准化效应量 (小:0.2, 中:0.5, 大:0.8)
    - 95% CI: 均值差异的置信区间
    - RMS衰减率: 振动衰减百分比
    """

    def __init__(self):
        pass

    def ttest_paired(self, exp_data: np.ndarray, ctrl_data: np.ndarray) -> Dict[str, float]:
        """配对t检验
        
        Args:
            exp_data: 实验组数据
            ctrl_data: 对照组数据
        
        Returns:
            {'t_stat': t统计量, 'p_value': p值, 'df': 自由度}
        """
        from scipy import stats
        
        valid = ~np.isnan(exp_data) & ~np.isnan(ctrl_data)
        e_valid = exp_data[valid]
        c_valid = ctrl_data[valid]
        
        if len(e_valid) < 10:
            return {'t_stat': 0.0, 'p_value': 1.0, 'df': 0}
        
        # 降采样避免数据量过大导致的统计膨胀
        ds_factor = max(1, len(e_valid) // 1000)
        e_down = e_valid[::ds_factor]
        c_down = c_valid[::ds_factor]
        
        t_stat, p_val = stats.ttest_rel(e_down, c_down)
        
        return {
            't_stat': float(t_stat),
            'p_value': float(p_val),
            'df': len(e_down) - 1
        }

    def cohens_d(self, exp_data: np.ndarray, ctrl_data: np.ndarray) -> float:
        """计算Cohen's d效应量
        
        Args:
            exp_data: 实验组数据
            ctrl_data: 对照组数据
        
        Returns:
            Cohen's d值
        """
        valid = ~np.isnan(exp_data) & ~np.isnan(ctrl_data)
        e_valid = exp_data[valid]
        c_valid = ctrl_data[valid]
        
        if len(e_valid) < 10:
            return 0.0
        
        mean_diff = np.mean(e_valid) - np.mean(c_valid)
        pooled_std = np.sqrt((np.std(e_valid)**2 + np.std(c_valid)**2) / 2)
        
        return float(mean_diff / pooled_std) if pooled_std > 1e-9 else 0.0

    def confidence_interval(self, exp_data: np.ndarray, ctrl_data: np.ndarray, 
                           confidence: float = 0.95) -> Dict[str, float]:
        """计算均值差异的置信区间
        
        Args:
            exp_data: 实验组数据
            ctrl_data: 对照组数据
            confidence: 置信水平 (默认0.95)
        
        Returns:
            {'diff_mean': 差异均值, 'ci_low': 下限, 'ci_high': 上限}
        """
        from scipy import stats
        
        valid = ~np.isnan(exp_data) & ~np.isnan(ctrl_data)
        e_valid = exp_data[valid]
        c_valid = ctrl_data[valid]
        
        if len(e_valid) < 10:
            return {'diff_mean': 0.0, 'ci_low': 0.0, 'ci_high': 0.0}
        
        diff = e_valid - c_valid
        mean_diff = np.mean(diff)
        std_diff = np.std(diff, ddof=1)
        n = len(diff)
        
        t_critical = stats.t.ppf((1 + confidence) / 2, n - 1)
        margin = t_critical * std_diff / np.sqrt(n)
        
        return {
            'diff_mean': float(mean_diff),
            'ci_low': float(mean_diff - margin),
            'ci_high': float(mean_diff + margin)
        }

    def rms_attenuation(self, exp_data: np.ndarray, ctrl_data: np.ndarray) -> float:
        """计算RMS衰减率
        
        Args:
            exp_data: 实验组数据
            ctrl_data: 对照组数据
        
        Returns:
            衰减率百分比 (正值表示实验组优于对照组)
        """
        valid = ~np.isnan(exp_data) & ~np.isnan(ctrl_data)
        e_valid = exp_data[valid]
        c_valid = ctrl_data[valid]
        
        if len(e_valid) < 10:
            return 0.0
        
        e_rms = np.sqrt(np.mean(e_valid**2))
        c_rms = np.sqrt(np.mean(c_valid**2))
        
        return float((1 - e_rms / c_rms) * 100) if c_rms > 1e-9 else 0.0

    def run_all_tests(self, exp_data: np.ndarray, ctrl_data: np.ndarray, 
                      axis_name: str = '') -> Dict[str, Any]:
        """执行全部统计检验
        
        Args:
            exp_data: 实验组数据
            ctrl_data: 对照组数据
            axis_name: 轴名称 (用于结果键名)
        
        Returns:
            包含所有统计量的字典
        """
        ttest = self.ttest_paired(exp_data, ctrl_data)
        d = self.cohens_d(exp_data, ctrl_data)
        ci = self.confidence_interval(exp_data, ctrl_data)
        atn = self.rms_attenuation(exp_data, ctrl_data)
        
        # 显著性标记
        p_val = ttest['p_value']
        if p_val < 0.001:
            sig = '***'
        elif p_val < 0.01:
            sig = '**'
        elif p_val < 0.05:
            sig = '*'
        else:
            sig = 'ns'
        
        prefix = f'{axis_name}_' if axis_name else ''
        
        return {
            f'{prefix}t_stat': ttest['t_stat'],
            f'{prefix}p_value': ttest['p_value'],
            f'{prefix}df': ttest['df'],
            f'{prefix}cohens_d': d,
            f'{prefix}diff_mean': ci['diff_mean'],
            f'{prefix}ci_low': ci['ci_low'],
            f'{prefix}ci_high': ci['ci_high'],
            f'{prefix}attenuation_pct': atn,
            f'{prefix}significant': sig
        }


class ISO2631_5_Operator:

    def __init__(self, weight_kg: float = 75.0, backrest_angle_deg: float = 23.0):
        self.weight_kg = weight_kg
        self.backrest_angle_deg = backrest_angle_deg

    def compute(self, ax: np.ndarray, ay: np.ndarray, az: np.ndarray,
                sample_rate: float, timestamps: Optional[np.ndarray] = None) -> Dict[str, Any]:
        try:
            n = len(ax)
            if n < 4:
                return {'S_d_MPa': 0.0, 'S_d_level': '无显著冲击', 'n_events': 0}

            dt = 1.0 / sample_rate
            if timestamps is None:
                timestamps = np.arange(n) * dt

            theta = np.radians(self.backrest_angle_deg)
            ct, st = np.cos(theta), np.sin(theta)
            ax_h = ax * ct - az * st
            ay_h = ay
            az_h = ax * st + az * ct

            omega_n = 2.0 * np.pi * 9.85 * np.sqrt(75.0 / self.weight_kg)
            zeta_val = 0.23 * np.sqrt(self.weight_kg / 75.0)

            sys_h = signal.lti([0.0, 1.0], [1.0, 31.4, 400.0])
            _, a_lx, _ = signal.lsim(sys_h, U=ax_h, T=timestamps)
            _, a_ly, _ = signal.lsim(sys_h, U=ay_h, T=timestamps)

            a_lz = np.zeros(n)
            disp, vel = 0.0, 0.0
            for i in range(1, n):
                u_z = -az_h[i]
                k_mod = 1.0 + 2.0 * (abs(disp) * 1000) if disp < 0 else 1.0
                acc_spinal = u_z - (2.0 * zeta_val * omega_n * vel) - (k_mod * omega_n ** 2 * disp)
                vel += acc_spinal * dt
                disp += vel * dt
                a_lz[i] = acc_spinal

            from scipy.signal import find_peaks
            px, _ = find_peaks(np.abs(a_lx), distance=int(sample_rate * 0.2))
            py, _ = find_peaks(np.abs(a_ly), distance=int(sample_rate * 0.2))
            pz, _ = find_peaks(np.abs(a_lz), distance=int(sample_rate * 0.2))

            max_len = min(len(px), len(py), len(pz))
            if max_len == 0:
                return {'S_d_MPa': 0.0, 'S_d_level': '绿色: 低风险', 'n_events': 0}

            cx, cy, cz = 0.018, 0.015, 0.003
            d_k6 = (cx * np.abs(a_lx[px[:max_len]])) ** 6 + \
                   (cy * np.abs(a_ly[py[:max_len]])) ** 6 + \
                   (cz * np.abs(a_lz[pz[:max_len]])) ** 6
            sd = np.sum(d_k6) ** (1.0 / 6.0)

            if sd < 0.5:
                level = '绿色: 低风险'
            elif sd <= 0.8:
                level = '黄色: 中度风险'
            else:
                level = '红色: 高风险'

            return {
                'S_d_MPa': float(sd),
                'S_d_level': level,
                'n_events': int(max_len),
                'a_lx': a_lx,
                'a_ly': a_ly,
                'a_lz': a_lz,
                'peaks_x': px,
                'peaks_y': py,
                'peaks_z': pz,
            }

        except Exception as e:
            logger.error(f"ISO 2631-5 S_d计算失败: {e}", exc_info=True)
            return {'S_d_MPa': 0.0, 'S_d_level': '计算失败', 'n_events': 0}


class OperatorSystem:
    """12大算子系统 - 统一管理"""

    def __init__(self):
        self.cfc = CFCOperator()
        self.vector = VectorOperator()
        self.fft = FFTOperator()
        self.psd = PSDOperator()
        self.csd = CSDOperator()
        self.weighting = WeightingOperator()
        self.integration = IntegrationOperator()
        self.attenuation = AttenuationOperator()
        self.stft = STFTOperator()
        self.srs = SRSOperator()
        self.rainflow = RainflowOperator()
        self.fds = FDSOperator()
        self.iso2631_5 = ISO2631_5_Operator()
        self.statistics = StatisticalOperator()

        self.operators = {
            'CFC': self.cfc,
            'VECTOR': self.vector,
            'FFT': self.fft,
            'PSD': self.psd,
            'CSD': self.csd,
            'WEIGHTING': self.weighting,
            'INTEGRATION': self.integration,
            'ATTENUATION': self.attenuation,
            'STFT': self.stft,
            'SRS': self.srs,
            'RAINFLOW': self.rainflow,
            'FDS': self.fds,
            'ISO2631_5': self.iso2631_5,
            'STATISTICS': self.statistics,
        }

    def get_operator(self, name: str):
        return self.operators.get(name.upper())