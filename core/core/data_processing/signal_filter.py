#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号滤波模块
提供多种数字信号滤波算法，用于IMU/CNAP等传感器数据的预处理

支持的滤波算法：
- 移动平均滤波 (Moving Average)
- 中值滤波 (Median Filter)
- 指数加权滤波 / RC低通滤波 (Exponential/RC Low-Pass)
- 高通滤波 (High-Pass Filter)
- 带通滤波 (Band-Pass Filter)
- 卡尔曼滤波 (Kalman Filter for 1D signal smoothing)
- 巴特沃斯低通滤波 (Butterworth Low-Pass, 纯numpy实现)
- CFC通道频率等级滤波 (SAE J211 / ISO 6487 碰撞试验标准)
  CFC 1000 / CFC 600 / CFC 180 / CFC 60 / CFC 30

版本: 1.1
创建时间: 2026年5月5日
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class FilterType(Enum):
    MOVING_AVERAGE = "moving_average"
    MEDIAN = "median"
    EXPONENTIAL = "exponential"
    LOW_PASS = "low_pass"
    HIGH_PASS = "high_pass"
    BAND_PASS = "band_pass"
    KALMAN = "kalman"
    BUTTERWORTH_LOWPASS = "butterworth_lowpass"
    CFC_1000 = "cfc_1000"
    CFC_600 = "cfc_600"
    CFC_180 = "cfc_180"
    CFC_60 = "cfc_60"
    CFC_30 = "cfc_30"


CFC_PARAMETERS = {
    FilterType.CFC_1000: {"cutoff": 1000.0, "stopband": -40, "description": "CFC 1000 — 截止频率 1000 Hz，适用于高频碰撞加速度信号"},
    FilterType.CFC_600:  {"cutoff": 600.0,  "stopband": -40, "description": "CFC 600 — 截止频率 600 Hz，适用于头部/胸部碰撞加速度"},
    FilterType.CFC_180:  {"cutoff": 180.0,  "stopband": -40, "description": "CFC 180 — 截止频率 180 Hz，适用于胸部压缩/力传感器"},
    FilterType.CFC_60:   {"cutoff": 60.0,   "stopband": -40, "description": "CFC 60 — 截止频率 60 Hz，适用于安全带力/位移传感器"},
    FilterType.CFC_30:   {"cutoff": 30.0,   "stopband": -40, "description": "CFC 30 — 截止频率 30 Hz，适用于膝部位移/低速碰撞"},
}


@dataclass
class FilterConfig:
    filter_type: FilterType = FilterType.MOVING_AVERAGE
    enabled: bool = True
    window_size: int = 5
    alpha: float = 0.3
    cutoff_frequency: float = 10.0
    high_cutoff: float = 50.0
    sample_rate: float = 100.0
    order: int = 2
    process_noise: float = 0.01
    measurement_noise: float = 0.1
    target_fields: List[str] = field(default_factory=lambda: ["ax", "ay", "az"])


class SignalFilter:
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self._buffer: Dict[str, deque] = {}
        self._kalman_state: Dict[str, Dict[str, float]] = {}
        self._prev_output: Dict[str, float] = {}
        self._prev_input: Dict[str, float] = {}
        self._butterworth_state: Dict[str, List[np.ndarray]] = {}

    def reset(self):
        self._buffer.clear()
        self._kalman_state.clear()
        self._prev_output.clear()
        self._prev_input.clear()
        self._butterworth_state.clear()

    def apply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config.enabled:
            return data

        result = dict(data)
        for field in self.config.target_fields:
            if field in data and data[field] is not None:
                try:
                    raw_value = float(data[field])
                    filtered_value = self._apply_filter(field, raw_value)
                    result[field] = filtered_value
                except (ValueError, TypeError):
                    pass
        return result

    def _apply_filter(self, field: str, value: float) -> float:
        ft = self.config.filter_type

        if ft == FilterType.MOVING_AVERAGE:
            return self._moving_average(field, value)
        elif ft == FilterType.MEDIAN:
            return self._median_filter(field, value)
        elif ft == FilterType.EXPONENTIAL or ft == FilterType.LOW_PASS:
            return self._exponential_filter(field, value)
        elif ft == FilterType.HIGH_PASS:
            return self._high_pass_filter(field, value)
        elif ft == FilterType.BAND_PASS:
            return self._band_pass_filter(field, value)
        elif ft == FilterType.KALMAN:
            return self._kalman_filter(field, value)
        elif ft == FilterType.BUTTERWORTH_LOWPASS:
            return self._butterworth_lowpass(field, value)
        elif ft in (FilterType.CFC_1000, FilterType.CFC_600, FilterType.CFC_180,
                    FilterType.CFC_60, FilterType.CFC_30):
            return self._cfc_filter(field, value)
        else:
            return value

    def _moving_average(self, field: str, value: float) -> float:
        if field not in self._buffer:
            self._buffer[field] = deque(maxlen=self.config.window_size)
        buf = self._buffer[field]
        buf.append(value)
        if len(buf) == 0:
            return value
        return sum(buf) / len(buf)

    def _median_filter(self, field: str, value: float) -> float:
        if field not in self._buffer:
            self._buffer[field] = deque(maxlen=self.config.window_size)
        buf = self._buffer[field]
        buf.append(value)
        if len(buf) == 0:
            return value
        return float(np.median(list(buf)))

    def _exponential_filter(self, field: str, value: float) -> float:
        alpha = self.config.alpha
        if field not in self._prev_output:
            self._prev_output[field] = value
            return value
        prev = self._prev_output[field]
        filtered = alpha * value + (1 - alpha) * prev
        self._prev_output[field] = filtered
        return filtered

    def _high_pass_filter(self, field: str, value: float) -> float:
        alpha = self.config.alpha
        if field not in self._prev_input or field not in self._prev_output:
            self._prev_input[field] = value
            self._prev_output[field] = 0.0
            return 0.0
        prev_in = self._prev_input[field]
        prev_out = self._prev_output[field]
        filtered = alpha * (prev_out + value - prev_in)
        self._prev_input[field] = value
        self._prev_output[field] = filtered
        return filtered

    def _band_pass_filter(self, field: str, value: float) -> float:
        low_val = self._exponential_filter(field, value)
        if f"{field}_hp" not in self._prev_input:
            self._prev_input[f"{field}_hp"] = low_val
            self._prev_output[f"{field}_hp"] = 0.0
            return 0.0
        prev_in = self._prev_input[f"{field}_hp"]
        prev_out = self._prev_output[f"{field}_hp"]
        alpha = self.config.alpha
        filtered = alpha * (prev_out + low_val - prev_in)
        self._prev_input[f"{field}_hp"] = low_val
        self._prev_output[f"{field}_hp"] = filtered
        return filtered

    def _kalman_filter(self, field: str, value: float) -> float:
        if field not in self._kalman_state:
            self._kalman_state[field] = {
                "x": value,
                "p": 1.0
            }
            return value

        state = self._kalman_state[field]
        q = self.config.process_noise
        r = self.config.measurement_noise

        x_pred = state["x"]
        p_pred = state["p"] + q

        k = p_pred / (p_pred + r)
        x_new = x_pred + k * (value - x_pred)
        p_new = (1 - k) * p_pred

        state["x"] = x_new
        state["p"] = p_new
        return x_new

    def _butterworth_lowpass(self, field: str, value: float) -> float:
        order = self.config.order
        cutoff = self.config.cutoff_frequency
        fs = self.config.sample_rate

        if field not in self._butterworth_state:
            nyquist = fs / 2.0
            if cutoff >= nyquist:
                cutoff = nyquist * 0.99
            wc = np.tan(np.pi * cutoff / fs)

            a_coeffs = []
            b_coeffs = []
            for k in range(order):
                theta = np.pi * (2 * k + 1) / (2 * order)
                pole_real = -np.sin(theta)
                pole_imag = np.cos(theta)

                denom = 1 + 2 * pole_real * wc + wc * wc
                b0 = wc * wc / denom
                b1 = 2 * wc * wc / denom
                b2 = wc * wc / denom
                a1 = 2 * (wc * wc - 1) / denom
                a2 = (1 - 2 * pole_real * wc + wc * wc) / denom

                a_coeffs.append(np.array([1.0, a1, a2]))
                b_coeffs.append(np.array([b0, b1, b2]))

            self._butterworth_state[field] = {
                "a": a_coeffs,
                "b": b_coeffs,
                "x_history": [np.zeros(3) for _ in range(order)],
                "y_history": [np.zeros(3) for _ in range(order)]
            }

        state = self._butterworth_state[field]
        current = value

        for stage in range(order):
            x_hist = state["x_history"][stage]
            y_hist = state["y_history"][stage]
            a = state["a"][stage]
            b = state["b"][stage]

            x_hist[2] = x_hist[1]
            x_hist[1] = x_hist[0]
            x_hist[0] = current

            y_hist[2] = y_hist[1]
            y_hist[1] = y_hist[0]

            y_new = (b[0] * x_hist[0] + b[1] * x_hist[1] + b[2] * x_hist[2]
                     - a[1] * y_hist[1] - a[2] * y_hist[2])
            y_hist[0] = y_new
            current = y_new

        return current

    def _cfc_filter(self, field: str, value: float) -> float:
        ft = self.config.filter_type
        cfc_info = CFC_PARAMETERS.get(ft, CFC_PARAMETERS[FilterType.CFC_60])
        cutoff = cfc_info["cutoff"]
        fs = self.config.sample_rate

        cfc_field = f"{field}_cfc_{ft.value}"
        if cfc_field not in self._butterworth_state:
            nyquist = fs / 2.0
            if cutoff >= nyquist:
                cutoff = nyquist * 0.99
            wc = np.tan(np.pi * cutoff / fs)

            order = 4
            a_coeffs = []
            b_coeffs = []
            for k in range(order):
                theta = np.pi * (2 * k + 1) / (2 * order)
                pole_real = -np.sin(theta)
                pole_imag = np.cos(theta)

                denom = 1 + 2 * pole_real * wc + wc * wc
                b0 = wc * wc / denom
                b1 = 2 * wc * wc / denom
                b2 = wc * wc / denom
                a1 = 2 * (wc * wc - 1) / denom
                a2 = (1 - 2 * pole_real * wc + wc * wc) / denom

                a_coeffs.append(np.array([1.0, a1, a2]))
                b_coeffs.append(np.array([b0, b1, b2]))

            self._butterworth_state[cfc_field] = {
                "a": a_coeffs,
                "b": b_coeffs,
                "x_history": [np.zeros(3) for _ in range(order)],
                "y_history": [np.zeros(3) for _ in range(order)]
            }

        state = self._butterworth_state[cfc_field]
        current = value

        for stage in range(4):
            x_hist = state["x_history"][stage]
            y_hist = state["y_history"][stage]
            a = state["a"][stage]
            b = state["b"][stage]

            x_hist[2] = x_hist[1]
            x_hist[1] = x_hist[0]
            x_hist[0] = current

            y_hist[2] = y_hist[1]
            y_hist[1] = y_hist[0]

            y_new = (b[0] * x_hist[0] + b[1] * x_hist[1] + b[2] * x_hist[2]
                     - a[1] * y_hist[1] - a[2] * y_hist[2])
            y_hist[0] = y_new
            current = y_new

        return current

    def apply_batch(self, data_array: np.ndarray) -> np.ndarray:
        if not self.config.enabled or len(data_array) == 0:
            return data_array

        ft = self.config.filter_type
        if ft == FilterType.MOVING_AVERAGE:
            return self._batch_moving_average(data_array)
        elif ft == FilterType.MEDIAN:
            return self._batch_median(data_array)
        else:
            result = np.zeros_like(data_array)
            for i in range(len(data_array)):
                result[i] = self._apply_filter("_batch", float(data_array[i]))
            return result

    def _batch_moving_average(self, data: np.ndarray) -> np.ndarray:
        ws = self.config.window_size
        if len(data) < ws:
            return data
        kernel = np.ones(ws) / ws
        return np.convolve(data, kernel, mode='same')

    def _batch_median(self, data: np.ndarray) -> np.ndarray:
        ws = self.config.window_size
        if len(data) < ws:
            return data
        half = ws // 2
        result = np.zeros_like(data)
        for i in range(len(data)):
            start = max(0, i - half)
            end = min(len(data), i + half + 1)
            result[i] = np.median(data[start:end])
        return result

    def get_config_dict(self) -> Dict[str, Any]:
        return {
            "filter_type": self.config.filter_type.value,
            "enabled": self.config.enabled,
            "window_size": self.config.window_size,
            "alpha": self.config.alpha,
            "cutoff_frequency": self.config.cutoff_frequency,
            "high_cutoff": self.config.high_cutoff,
            "sample_rate": self.config.sample_rate,
            "order": self.config.order,
            "process_noise": self.config.process_noise,
            "measurement_noise": self.config.measurement_noise,
            "target_fields": self.config.target_fields,
        }

    def update_config(self, config_dict: Dict[str, Any]):
        if "filter_type" in config_dict:
            ft = config_dict["filter_type"]
            if isinstance(ft, str):
                self.config.filter_type = FilterType(ft)
            elif isinstance(ft, FilterType):
                self.config.filter_type = ft
        if "enabled" in config_dict:
            self.config.enabled = config_dict["enabled"]
        if "window_size" in config_dict:
            self.config.window_size = config_dict["window_size"]
        if "alpha" in config_dict:
            self.config.alpha = config_dict["alpha"]
        if "cutoff_frequency" in config_dict:
            self.config.cutoff_frequency = config_dict["cutoff_frequency"]
        if "high_cutoff" in config_dict:
            self.config.high_cutoff = config_dict["high_cutoff"]
        if "sample_rate" in config_dict:
            self.config.sample_rate = config_dict["sample_rate"]
        if "order" in config_dict:
            self.config.order = config_dict["order"]
        if "process_noise" in config_dict:
            self.config.process_noise = config_dict["process_noise"]
        if "measurement_noise" in config_dict:
            self.config.measurement_noise = config_dict["measurement_noise"]
        if "target_fields" in config_dict:
            self.config.target_fields = config_dict["target_fields"]
        self.reset()


class FilterPipeline:
    def __init__(self):
        self.filters: List[SignalFilter] = []

    def add_filter(self, filter_instance: SignalFilter):
        self.filters.append(filter_instance)

    def remove_filter(self, index: int):
        if 0 <= index < len(self.filters):
            self.filters.pop(index)

    def clear(self):
        self.filters.clear()

    def apply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = data
        for f in self.filters:
            result = f.apply(result)
        return result

    def reset(self):
        for f in self.filters:
            f.reset()


_filter_instances: Dict[str, SignalFilter] = {}


def get_signal_filter(source_id: str, config: Optional[FilterConfig] = None) -> SignalFilter:
    if source_id not in _filter_instances:
        _filter_instances[source_id] = SignalFilter(config)
    elif config is not None:
        _filter_instances[source_id] = SignalFilter(config)
    return _filter_instances[source_id]


def reset_all_filters():
    _filter_instances.clear()
