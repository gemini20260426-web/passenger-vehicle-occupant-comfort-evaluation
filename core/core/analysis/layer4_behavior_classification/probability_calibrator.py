#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
概率校准模块 — Phase 2 核心组件

对 LightGBM 原始输出概率进行 Platt Scaling 校准:

功能:
  1. Platt Scaling (sigmoid) 校准 — 将原始概率映射到真实概率
  2. 温度缩放 (Temperature Scaling) — 对多分类 logits 校准
  3. 校准模型持久化 (与主模型一起保存/加载)
  4. 校准后置信度更接近真实准确率

背景:
  LightGBM 的 predict_proba 输出通常偏极端 (接近 0 或 1)，
  不直接反映真实概率。Platt Scaling 通过 sigmoid 函数
  将原始分数映射到经过校准的概率。

  温度缩放公式: softmax(logits / T)，T 为温度参数。
  T > 1 使分布更平滑，T < 1 使分布更尖锐。

用法:
    calibrator = ProbabilityCalibrator()
    calibrator.fit(X_val, y_val, model)  # 在验证集上拟合
    calibrated_proba = calibrator.calibrate(raw_proba)
"""

import numpy as np
import logging
from typing import Optional, Dict, Any
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """概率校准器 — Platt Scaling + 温度缩放

    用法:
        cal = ProbabilityCalibrator()
        cal.fit(X_val, y_val, model)  # 在验证集上拟合校准参数
        cal_proba = cal.calibrate(raw_proba)  # 校准原始概率
    """

    def __init__(self):
        self._is_fitted = False
        # Platt Scaling 参数 (per-class sigmoid: A * score + B)
        self._platt_A: Optional[np.ndarray] = None  # shape=(n_classes,)
        self._platt_B: Optional[np.ndarray] = None  # shape=(n_classes,)
        # 温度缩放参数
        self._temperature: float = 1.0
        self._n_classes: int = 0

    def fit(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        model: Any,
        method: str = 'platt',
    ) -> Dict[str, float]:
        """在验证集上拟合校准参数

        Args:
            X_val: 验证集特征 shape=(N, 55)
            y_val: 验证集标签 shape=(N,)
            model: 已训练的 LightGBM 模型 (有 predict_proba 方法)
            method: 校准方法 'platt' (sigmoid) 或 'temperature' 或 'both'

        Returns:
            校准指标字典 (ECE, MCE, etc.)
        """
        raw_proba = model.predict_proba(X_val)
        if hasattr(raw_proba, 'values'):
            raw_proba = raw_proba.values
        if hasattr(y_val, 'values'):
            y_val = y_val.values
        self._n_classes = raw_proba.shape[1]

        if method in ('platt', 'both'):
            self._fit_platt(raw_proba, y_val)

        if method in ('temperature', 'both'):
            self._fit_temperature(raw_proba, y_val)

        self._is_fitted = True

        # 计算校准指标
        metrics = self._compute_calibration_metrics(raw_proba, y_val)
        logger.info(
            f"概率校准完成: method={method}, "
            f"ECE={metrics.get('ece', 0):.4f}, "
            f"temperature={self._temperature:.3f}"
        )
        return metrics

    def _fit_platt(self, raw_proba: np.ndarray, y_val: np.ndarray):
        """对每个类别独立拟合 Platt Scaling sigmoid

        Platt Scaling: P_calibrated = 1 / (1 + exp(-(A * logit + B)))
        其中 logit = log(proba / (1 - proba))
        """
        n_classes = raw_proba.shape[1]
        self._platt_A = np.ones(n_classes)
        self._platt_B = np.zeros(n_classes)

        for c in range(n_classes):
            # 二分类标签: 1 表示属于该类，0 表示不属于
            y_binary = (y_val == c).astype(np.float64)

            # 提取该类别的原始概率
            proba_c = raw_proba[:, c].copy()

            # 避免 log(0) 或 log(1)
            eps = 1e-12
            proba_c = np.clip(proba_c, eps, 1 - eps)

            # 转为 logit
            logit_c = np.log(proba_c / (1 - proba_c))

            # 优化 Platt 参数 A, B
            try:
                result = minimize(
                    self._platt_loss,
                    x0=[1.0, 0.0],
                    args=(logit_c, y_binary),
                    method='L-BFGS-B',
                    options={'maxiter': 100},
                )
                if result.success:
                    self._platt_A[c] = result.x[0]
                    self._platt_B[c] = result.x[1]
            except Exception as e:
                logger.debug(f"类别 {c} Platt 拟合失败: {e}，使用默认参数")

    def _fit_temperature(self, raw_proba: np.ndarray, y_val: np.ndarray):
        """拟合温度缩放参数 T

        温度缩放: softmax(logits / T)
        优化 NLL (Negative Log-Likelihood)
        """
        # 从概率反推 logits
        eps = 1e-12
        proba_clipped = np.clip(raw_proba, eps, 1 - eps)
        logits = np.log(proba_clipped)

        try:
            result = minimize(
                self._temperature_nll,
                x0=[1.0],
                args=(logits, y_val),
                method='L-BFGS-B',
                bounds=[(0.1, 10.0)],
                options={'maxiter': 100},
            )
            if result.success:
                self._temperature = float(np.clip(result.x[0], 0.1, 10.0))
        except Exception as e:
            logger.debug(f"温度缩放拟合失败: {e}，使用默认 T=1.0")

    def calibrate(self, raw_proba: np.ndarray) -> np.ndarray:
        """校准原始概率

        Args:
            raw_proba: 原始模型输出概率 shape=(N, n_classes) 或 shape=(n_classes,)

        Returns:
            校准后的概率，同 shape
        """
        if not self._is_fitted:
            return raw_proba

        was_1d = raw_proba.ndim == 1
        if was_1d:
            raw_proba = raw_proba.reshape(1, -1)

        calibrated = raw_proba.copy()

        # 1. 温度缩放
        if self._temperature != 1.0:
            eps = 1e-12
            proba_clipped = np.clip(calibrated, eps, 1 - eps)
            logits = np.log(proba_clipped)
            scaled_logits = logits / self._temperature
            # softmax
            max_logits = np.max(scaled_logits, axis=1, keepdims=True)
            exp_logits = np.exp(scaled_logits - max_logits)
            calibrated = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # 2. Platt Scaling (per-class sigmoid)
        if self._platt_A is not None:
            for c in range(self._n_classes):
                eps = 1e-12
                p = np.clip(calibrated[:, c], eps, 1 - eps)
                logit = np.log(p / (1 - p))
                calibrated[:, c] = 1.0 / (1.0 + np.exp(-(self._platt_A[c] * logit + self._platt_B[c])))

            # 重新归一化
            row_sums = np.sum(calibrated, axis=1, keepdims=True)
            calibrated = calibrated / np.clip(row_sums, 1e-8, None)

        if was_1d:
            calibrated = calibrated[0]

        return calibrated

    def _platt_loss(self, params: np.ndarray, logits: np.ndarray, y: np.ndarray) -> float:
        """Platt Scaling 损失函数 (交叉熵)"""
        A, B = params
        f = 1.0 / (1.0 + np.exp(-(A * logits + B)))
        # 防止 log(0)
        f = np.clip(f, 1e-12, 1 - 1e-12)
        return -np.mean(y * np.log(f) + (1 - y) * np.log(1 - f))

    def _temperature_nll(self, params: np.ndarray, logits: np.ndarray, y: np.ndarray) -> float:
        """温度缩放 NLL 损失"""
        T = params[0]
        scaled_logits = logits / T
        max_logits = np.max(scaled_logits, axis=1, keepdims=True)
        exp_logits = np.exp(scaled_logits - max_logits)
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # NLL
        n_samples = len(y)
        log_probs = np.log(np.clip(probs[np.arange(n_samples), y], 1e-12, 1.0))
        return -np.mean(log_probs)

    def _compute_calibration_metrics(
        self, raw_proba: np.ndarray, y_val: np.ndarray
    ) -> Dict[str, float]:
        """计算校准质量指标"""
        calibrated = self.calibrate(raw_proba)

        # ECE (Expected Calibration Error)
        ece = self._compute_ece(calibrated, y_val, n_bins=10)
        raw_ece = self._compute_ece(raw_proba, y_val, n_bins=10)

        # 置信度统计
        raw_max_conf = np.mean(np.max(raw_proba, axis=1))
        cal_max_conf = np.mean(np.max(calibrated, axis=1))

        return {
            'ece': ece,
            'ece_raw': raw_ece,
            'ece_improvement': raw_ece - ece,
            'raw_mean_max_conf': raw_max_conf,
            'calibrated_mean_max_conf': cal_max_conf,
            'temperature': self._temperature,
        }

    def _compute_ece(self, proba: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> float:
        """计算 Expected Calibration Error"""
        if hasattr(y_true, 'values'):
            y_true = y_true.values
        confidences = np.max(proba, axis=1)
        predictions = np.argmax(proba, axis=1)
        accuracies = (predictions == y_true).astype(float)

        bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
            bin_size = np.sum(in_bin)
            if bin_size > 0:
                avg_conf = np.mean(confidences[in_bin])
                avg_acc = np.mean(accuracies[in_bin])
                ece += (bin_size / len(y_true)) * abs(avg_acc - avg_conf)

        return float(ece)

    def is_fitted(self) -> bool:
        return self._is_fitted

    def get_params(self) -> Dict[str, Any]:
        """获取校准参数 (用于持久化)"""
        return {
            'temperature': self._temperature,
            'platt_A': self._platt_A.tolist() if self._platt_A is not None else None,
            'platt_B': self._platt_B.tolist() if self._platt_B is not None else None,
            'n_classes': self._n_classes,
            'is_fitted': self._is_fitted,
        }

    def set_params(self, params: Dict[str, Any]):
        """从持久化参数恢复校准器"""
        self._temperature = params.get('temperature', 1.0)
        self._n_classes = params.get('n_classes', 0)
        self._is_fitted = params.get('is_fitted', False)

        platt_A = params.get('platt_A')
        platt_B = params.get('platt_B')
        if platt_A is not None:
            self._platt_A = np.array(platt_A)
        if platt_B is not None:
            self._platt_B = np.array(platt_B)

    def reset(self):
        """重置校准器"""
        self._is_fitted = False
        self._platt_A = None
        self._platt_B = None
        self._temperature = 1.0
        self._n_classes = 0