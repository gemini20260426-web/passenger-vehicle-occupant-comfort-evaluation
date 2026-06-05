"""
IMU 专用双冗余融合引擎

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第四部分 4.4.2 节。
替代通用 AdaptiveDataFusion，直接适配本项目 CSV 数据格式。
提供：头部IMU双冗余融合、座垫-底板SEAT因子计算、CSV离线融合桥接。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class IMUDualRedundantFusion:
    """IMU 双冗余融合引擎 — 本项目专用融合场景

    场景1: 头部IMU冗余融合 (IMU1 + IMU2 → 加权平均)
    场景2: 座垫-底板 SEAT 传递因子计算
    """

    def __init__(self, fs: float = 1000.0):
        self.fs = fs
        self.snr_cache: Dict[str, float] = {}
        self.fusion_quality: list = []

    # ── 场景1: 头部IMU双冗余融合 ──

    def fuse_head_imus(self, imu1_data: np.ndarray, imu2_data: np.ndarray) -> dict:
        """头部IMU双冗余融合 (IMU1实验组 + IMU2对照组)

        Args:
            imu1_data: [N, 10] array [time, Ax, Ay, Az, Gx, Gy, Gz, Gx_r, Gy_r, Gz_r]
            imu2_data: 同上

        Returns:
            {'data': fused_array, 'quality': {axis: {snr1, snr2, w1}}}
        """
        if len(imu1_data) != len(imu2_data):
            raise ValueError(f"IMU数据长度不匹配: {len(imu1_data)} vs {len(imu2_data)}")

        fused = np.zeros_like(imu1_data)
        fused[:, 0] = imu1_data[:, 0]  # 时间戳

        quality = {}

        # 逐轴融合 (Ax=col1, Ay=col2, Az=col3)
        for axis_idx, axis_name in enumerate(['Ax', 'Ay', 'Az'], 1):
            if axis_idx >= imu1_data.shape[1]:
                break
            vals1 = imu1_data[:, axis_idx]
            vals2 = imu2_data[:, axis_idx]

            # 信噪比加权
            snr1 = self._estimate_snr(vals1)
            snr2 = self._estimate_snr(vals2)
            w1 = snr1 / (snr1 + snr2 + 1e-6)
            w2 = 1.0 - w1

            fused[:, axis_idx] = w1 * vals1 + w2 * vals2
            quality[axis_name] = {'snr1': round(float(snr1), 3), 'snr2': round(float(snr2), 3), 'w1': round(float(w1), 3)}

        self.fusion_quality.append(quality)
        return {'data': fused, 'quality': quality}

    # ── 场景2: 座垫-底板 SEAT 传递因子 ──

    def fuse_seat_transfer(self, seat_r_data: np.ndarray, seat_bottom_data: np.ndarray) -> dict:
        """座垫-底板传递分析 (SEAT因子计算)

        用于计算: SEAT_Z = sqrt(∫PSD_seat / ∫PSD_bottom)

        Args:
            seat_r_data: 座垫R点 IMU 数据 [N, 10]
            seat_bottom_data: 座椅底部 IMU 数据 [N, 10]

        Returns:
            {'SEAT_Z': float, 'SEAT_X': float, 'SEAT_Y': float}
        """
        from scipy import signal

        seat_factors = {}

        for axis_idx, axis_name in enumerate(['Ax', 'Ay', 'Az'], 1):
            if axis_idx >= min(seat_r_data.shape[1], seat_bottom_data.shape[1]):
                break

            az_seat = seat_r_data[:, axis_idx]
            az_bottom = seat_bottom_data[:, axis_idx]

            # 去除NaN
            valid = ~np.isnan(az_seat) & ~np.isnan(az_bottom)
            if valid.sum() < 100:
                seat_factors[f'SEAT_{axis_name[1]}'] = float('nan')
                continue

            az_seat = az_seat[valid]
            az_bottom = az_bottom[valid]

            # Welch PSD
            nperseg = min(1024, len(az_seat) // 2)
            f_seat, Pxx_seat = signal.welch(az_seat, fs=self.fs, nperseg=nperseg)
            f_bot, Pxx_bot = signal.welch(az_bottom, fs=self.fs, nperseg=nperseg)

            # Wk 频率加权 (ISO 2631-1)
            wk = self._iso_wk_weighting(f_seat)
            Pxx_seat_w = Pxx_seat * (wk ** 2)
            Pxx_bot_w = Pxx_bot * (wk ** 2)

            # SEAT因子
            I_seat = np.trapz(Pxx_seat_w, f_seat)
            I_bot = np.trapz(Pxx_bot_w, f_bot)
            seat_factor = np.sqrt(I_seat / (I_bot + 1e-12))

            seat_factors[f'SEAT_{axis_name[1]}'] = round(float(seat_factor), 4)

        return seat_factors

    # ── 信噪比估计 ──

    def _estimate_snr(self, signal_data: np.ndarray) -> float:
        """信噪比估计: 信号功率 / 噪声功率"""
        valid = ~np.isnan(signal_data)
        if valid.sum() < 10:
            return 0.0
        sig = signal_data[valid]
        if len(sig) < 2:
            return 0.0
        sig_power = float(np.var(sig))
        noise_power = float(np.var(np.diff(sig))) / 2.0  # 差分法估计噪声
        if noise_power < 1e-12:
            return 100.0  # 极低噪声
        return sig_power / noise_power

    # ── ISO 2631-1 Wk 频率加权 ──

    def _iso_wk_weighting(self, freq: np.ndarray) -> np.ndarray:
        """ISO 2631-1 Wk 频率加权函数 (垂直方向)"""
        wk = np.ones_like(freq)
        for i, f in enumerate(freq):
            if f < 0.5:
                wk[i] = 0.5
            elif f < 2.0:
                wk[i] = f
            elif f < 5.0:
                wk[i] = 1.0
            elif f < 16.0:
                wk[i] = 16.0 / f
            elif f < 80.0:
                wk[i] = 1.0
            else:
                wk[i] = 0.0
        return wk


class CSVDataFusionBridge:
    """CSV 离线数据融合桥接器 — 连接本数据集与融合模块"""

    def __init__(self, csv_path: str):
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV文件不存在: {csv_path}")
        self.df = pd.read_csv(csv_path)
        self.fusion = IMUDualRedundantFusion()
        self._imu_cache: Dict[str, np.ndarray] = {}

    def run_all_fusions(self) -> dict:
        """执行所有预设融合场景"""
        results = {}

        # 场景1: 头部IMU双冗余 (IMU1 实验组 + IMU2 对照组)
        try:
            imu1 = self._extract_imu('IMU1_头部眉心-1')
            imu2 = self._extract_imu('IMU2_头部眉心-2')
            if imu1 is not None and imu2 is not None:
                results['head_fusion'] = self.fusion.fuse_head_imus(imu1, imu2)
                logger.info("头部IMU双冗余融合完成")
        except Exception as e:
            logger.warning(f"头部IMU融合失败: {e}")

        # 场景2: 座垫-底板 SEAT 传递
        try:
            seat_r = self._extract_imu('IMU5_座垫R点-1')
            seat_bottom = self._extract_imu('IMU7_座椅底部-1')
            if seat_r is not None and seat_bottom is not None:
                results['seat_transfer'] = self.fusion.fuse_seat_transfer(seat_r, seat_bottom)
                logger.info("座垫-底板SEAT传递计算完成")
        except Exception as e:
            logger.warning(f"SEAT传递计算失败: {e}")

        # 场景3: 对照组座垫-底板 SEAT 传递
        try:
            seat_r_ctrl = self._extract_imu('IMU6_座垫R点-2')
            seat_bottom_ctrl = self._extract_imu('IMU8_座椅底部-2')
            if seat_r_ctrl is not None and seat_bottom_ctrl is not None:
                results['seat_transfer_control'] = self.fusion.fuse_seat_transfer(
                    seat_r_ctrl, seat_bottom_ctrl
                )
                logger.info("对照组座垫-底板SEAT传递计算完成")
        except Exception as e:
            logger.warning(f"对照组SEAT传递计算失败: {e}")

        return results

    def _extract_imu(self, imu_name: str) -> Optional[np.ndarray]:
        """从 CSV 中提取指定 IMU 的数据"""
        if imu_name in self._imu_cache:
            return self._imu_cache[imu_name]

        cols = ['rel_time']
        for axis in ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2', 'Gx_dps', 'Gy_dps', 'Gz_dps',
                     'Gx_r_dps', 'Gy_r_dps', 'Gz_r_dps']:
            col_name = f"{imu_name}_{axis}"
            if col_name in self.df.columns:
                cols.append(col_name)

        if len(cols) < 2:
            logger.warning(f"IMU {imu_name} 在CSV中无数据列")
            return None

        # 只取存在的列
        available_cols = [c for c in cols if c in self.df.columns]
        data = self.df[available_cols].values
        self._imu_cache[imu_name] = data
        return data