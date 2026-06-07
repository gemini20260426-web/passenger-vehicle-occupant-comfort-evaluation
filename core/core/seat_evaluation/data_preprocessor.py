#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据预处理管道
融合参考脚本的: 零偏校准 + 坐标系对齐 + Butterworth低通滤波

提供三级预处理选项:
  Level 0: 原始数据（不做任何处理）
  Level 1: 零偏校准 + 坐标系对齐
  Level 2: 零偏校准 + 坐标系对齐 + 低通滤波（完整管线）
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DataPreprocessor:

    def __init__(self, sample_rate: float = 1000.0, lowpass_cutoff: float = 10.0):
        self.sample_rate = sample_rate
        self.lowpass_cutoff = lowpass_cutoff
        self.g = 9.80665
        self._calib_samples_count = 1000

    def process(self, acc_data: np.ndarray, gyro_data: np.ndarray,
                timestamps: np.ndarray, level: int = 1) -> Dict[str, Any]:
        if level == 0:
            return {
                'acc': np.asarray(acc_data), 'gyro': np.asarray(gyro_data),
                'timestamps': np.asarray(timestamps), 'level': 0,
                'acc_bias': np.zeros(3), 'gyro_bias': np.zeros(3),
                'correction_matrix': np.eye(3)
            }

        acc_calib, gyro_calib, acc_bias, gyro_bias = self._calibrate_static(acc_data, gyro_data)

        acc_aligned, gyro_aligned, R = self._align_gravity(acc_calib, gyro_calib)

        if level == 1:
            return {
                'acc': acc_aligned, 'gyro': gyro_aligned,
                'timestamps': np.asarray(timestamps), 'level': 1,
                'acc_bias': acc_bias, 'gyro_bias': gyro_bias,
                'correction_matrix': R
            }

        acc_filtered = np.zeros_like(acc_aligned)
        gyro_filtered = np.zeros_like(gyro_aligned)
        for i in range(3):
            acc_filtered[:, i] = self._butter_lowpass(acc_aligned[:, i])
            gyro_filtered[:, i] = self._butter_lowpass(gyro_aligned[:, i])

        return {
            'acc': acc_filtered, 'gyro': gyro_filtered,
            'timestamps': np.asarray(timestamps), 'level': 2,
            'acc_bias': acc_bias, 'gyro_bias': gyro_bias,
            'correction_matrix': R
        }

    def process_single_channel(self, acc_data: np.ndarray, gyro_data: np.ndarray,
                               timestamps: np.ndarray, level: int = 1,
                               manual_acc_bias: Optional[np.ndarray] = None,
                               manual_gyro_bias: Optional[np.ndarray] = None) -> Dict[str, Any]:
        if level == 0:
            return {
                'acc': np.asarray(acc_data), 'gyro': np.asarray(gyro_data),
                'timestamps': np.asarray(timestamps), 'level': 0,
                'acc_bias': np.zeros(3), 'gyro_bias': np.zeros(3),
                'correction_matrix': np.eye(3)
            }

        if manual_acc_bias is not None and manual_gyro_bias is not None:
            acc_calib = acc_data - manual_acc_bias
            gyro_calib = gyro_data - manual_gyro_bias
            acc_bias, gyro_bias = manual_acc_bias, manual_gyro_bias
        else:
            acc_calib, gyro_calib, acc_bias, gyro_bias = self._calibrate_static(acc_data, gyro_data)

        acc_aligned, gyro_aligned, R = self._align_gravity(acc_calib, gyro_calib)

        if level == 1:
            return {
                'acc': acc_aligned, 'gyro': gyro_aligned,
                'timestamps': np.asarray(timestamps), 'level': 1,
                'acc_bias': acc_bias, 'gyro_bias': gyro_bias,
                'correction_matrix': R
            }

        acc_filtered = np.zeros_like(acc_aligned)
        gyro_filtered = np.zeros_like(gyro_aligned)
        for i in range(3):
            acc_filtered[:, i] = self._butter_lowpass(acc_aligned[:, i])
            gyro_filtered[:, i] = self._butter_lowpass(gyro_aligned[:, i])

        return {
            'acc': acc_filtered, 'gyro': gyro_filtered,
            'timestamps': np.asarray(timestamps), 'level': 2,
            'acc_bias': acc_bias, 'gyro_bias': gyro_bias,
            'correction_matrix': R
        }

    def _calibrate_static(self, acc: np.ndarray, gyro: np.ndarray) -> Tuple:
        n = min(self._calib_samples_count, len(acc))
        acc_bias = np.mean(acc[:n], axis=0)
        gyro_bias = np.mean(gyro[:n], axis=0)

        acc_calib = acc - acc_bias
        gyro_calib = gyro - gyro_bias

        return acc_calib, gyro_calib, acc_bias, gyro_bias

    def _align_gravity(self, acc: np.ndarray, gyro: np.ndarray) -> Tuple:
        n = min(self._calib_samples_count, len(acc))
        g_vec = np.mean(acc[:n], axis=0)
        g_norm = np.linalg.norm(g_vec)
        if g_norm < 1e-9:
            return acc, gyro, np.eye(3)
        g_vec = g_vec / g_norm

        z_std = np.array([0, 0, -1])
        v = np.cross(g_vec, z_std)
        s = np.linalg.norm(v)
        c = np.dot(g_vec, z_std)

        if s < 1e-9:
            sign = 1.0 if c > 0 else -1.0
            return acc * sign, gyro, np.eye(3) * sign

        skew = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + skew + skew @ skew * (1 - c) / (s ** 2)

        acc_aligned = acc @ R.T
        gyro_aligned = gyro @ R.T

        return acc_aligned, gyro_aligned, R

    def _butter_lowpass(self, data: np.ndarray, order: int = 2) -> np.ndarray:
        if len(data) < 4:
            return data
        nyq = 0.5 * self.sample_rate
        normal_cutoff = min(self.lowpass_cutoff / nyq, 0.99)
        sos = butter(order, normal_cutoff, btype='low', output='sos')
        return sosfiltfilt(sos, data)

    def compute_calibration_params(self, acc_data: np.ndarray, gyro_data: np.ndarray) -> Dict[str, Any]:
        n = min(self._calib_samples_count, len(acc_data))
        acc_bias = np.mean(acc_data[:n], axis=0)
        gyro_bias = np.mean(gyro_data[:n], axis=0)

        g_vec = np.mean(acc_data[:n], axis=0) - acc_bias
        g_norm = np.linalg.norm(g_vec)
        z_sign = 1.0
        if g_norm > 1e-9:
            g_vec = g_vec / g_norm
            z_sign = 1.0 if g_vec[2] < 0 else -1.0

        return {
            'acc_bias': acc_bias.tolist(),
            'gyro_bias': gyro_bias.tolist(),
            'z_sign': float(z_sign),
            'g_magnitude': float(np.linalg.norm(np.mean(acc_data[:n], axis=0)))
        }