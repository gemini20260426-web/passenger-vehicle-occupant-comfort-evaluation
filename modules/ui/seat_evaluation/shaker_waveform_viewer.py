#!/usr/bin/env python3
"""波形预览组件"""

import numpy as np

from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class ShakerWaveformViewer(QGroupBox):
    """6通道波形预览组件 — 预览平台和R点三轴加速度波形"""

    def __init__(self, parent=None):
        super().__init__("波形预览", parent)
        self._labels: dict = {}       # key → QLabel
        self._t8_label: QLabel = None
        self._init_ui()

    # ------------------------------------------------------------------
    def _init_ui(self):
        outer = QVBoxLayout(self)

        # ── 网格容器 ──
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(8)

        channels = [
            # (row, col, key, title)
            (0, 0, "platform_z", "平台 Z"),
            (0, 1, "platform_y", "平台 Y"),
            (0, 2, "platform_x", "平台 X"),
            (1, 0, "r_point_z",  "R点 Z"),
            (1, 1, "r_point_y",  "R点 Y"),
            (1, 2, "r_point_x",  "R点 X"),
        ]

        for row, col, key, title in channels:
            label = QLabel(f"{title}\n(波形将在分析后显示)")
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(140, 70)
            label.setStyleSheet(
                "border: 1px solid #999; border-radius: 4px; "
                "background: #f5f5f5; padding: 6px;"
            )
            grid.addWidget(label, row, col)
            self._labels[key] = label

        outer.addWidget(grid_widget)

        # ── T8 行 ──
        self._t8_label = QLabel("靠背 T8: 分析后显示")
        self._t8_label.setAlignment(Qt.AlignCenter)
        self._t8_label.setStyleSheet(
            "border: 1px solid #999; border-radius: 4px; "
            "background: #f5f5f5; padding: 6px; margin-top: 4px;"
        )
        self._t8_label.setMinimumHeight(36)
        outer.addWidget(self._t8_label)

    # ------------------------------------------------------------------
    def set_data(self, data):
        """用 ShakerData 或 ProcessedShakerData 更新波形信息。

        Parameters
        ----------
        data : ShakerData or ProcessedShakerData
            分析后的数据对象。
        """
        if data is None:
            self._reset()
            return

        duration = self._safe_duration(data)

        # 判断数据类型并获取对应的三轴通道
        # ProcessedShakerData 有 ``source`` 属性且 platform_raw 等存在
        if hasattr(data, 'source') and hasattr(data, 'platform_raw'):
            platform = data.platform_raw
            r_point = data.r_point_raw
            t8 = data.t8_raw
        else:
            platform = data.platform
            r_point = data.r_point
            t8 = data.t8

        # 网格: platform_z / platform_y / platform_x ; r_point_z / r_point_y / r_point_x
        mapping = {
            "platform_z": platform.z,
            "platform_y": platform.y,
            "platform_x": platform.x,
            "r_point_z":  r_point.z,
            "r_point_y":  r_point.y,
            "r_point_x":  r_point.x,
        }

        for key, label in self._labels.items():
            signal = mapping.get(key)
            label.setText(self._format_channel(key, duration, signal))

        # T8 综合
        t8_text = self._format_t8(duration, t8.x, t8.y, t8.z)
        self._t8_label.setText(t8_text)

    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_duration(data) -> float:
        """安全获取时长 (秒)。"""
        try:
            return float(getattr(data, 'duration', 0.0) or 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def _format_channel(name: str, duration: float, signal: np.ndarray) -> str:
        """格式化单个通道的摘要文本。"""
        if signal is None or len(signal) == 0:
            return f"{name}\n(无数据)"

        sig = np.asarray(signal, dtype=float)
        sig = sig[np.isfinite(sig)]
        if len(sig) == 0:
            return f"{name}\n(数据无效)"

        return (
            f"{name}\n"
            f"时长: {duration:.3f} s\n"
            f"Max: {sig.max():.4f}  Min: {sig.min():.4f}"
        )

    def _format_t8(self, duration: float, x: np.ndarray,
                   y: np.ndarray, z: np.ndarray) -> str:
        parts = ["靠背 T8"]
        for axis_name, signal in [("X", x), ("Y", y), ("Z", z)]:
            parts.append(self._fmt_axis(axis_name, duration, signal))
        return "  |  ".join(parts)

    @staticmethod
    def _fmt_axis(name: str, duration: float, signal: np.ndarray) -> str:
        if signal is None or len(signal) == 0:
            return f"{name}: (无数据)"
        sig = np.asarray(signal, dtype=float)
        sig = sig[np.isfinite(sig)]
        if len(sig) == 0:
            return f"{name}: (无效)"
        return f"{name}: {duration:.3f}s, ↑{sig.max():.4f} ↓{sig.min():.4f}"

    def _reset(self):
        """恢复为占位文本。"""
        for key, label in self._labels.items():
            label.setText(f"{key}\n(波形将在分析后显示)")
        if self._t8_label:
            self._t8_label.setText("靠背 T8: 分析后显示")