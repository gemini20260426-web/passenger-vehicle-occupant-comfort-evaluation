#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
特征工程分析视图 — Phase 4（卡片式两列布局）
展示 Layer 2 的特征提取结果：时域/频域/运动学/物理特征 + 信号质量监控
"""

import logging
import time
from collections import deque
from typing import Dict, Any

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QFrame, QScrollArea,
                               QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.core.analysis.core_types import (
    FrameFeatures, SignalQuality, FrameResult
)


class FeatureAnalysisView(QWidget):
    """特征工程分析视图 — 卡片式两列布局"""

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None

        self._latest_features = None
        self._feature_history = deque(maxlen=100)

        self._init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("featureContent")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._build_temporal_card())
        row1.addWidget(self._build_spectral_card())
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self._build_kinematic_card())
        row2.addWidget(self._build_physics_card())
        layout.addLayout(row2)

        layout.addWidget(self._build_signal_card())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _make_card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setFlat(False)
        card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 11px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        return card

    def _make_table(self, headers: list, rows: int = 0) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setStyleSheet(
            "QTableWidget { border: 1px solid #e0e0e0; gridline-color: #ecf0f1; "
            "alternate-background-color: #f8f9fa; font-size: 10px; }"
            "QHeaderView::section { background-color: #f5f6fa; border: 1px solid #e0e0e0; "
            "padding: 3px; font-weight: bold; font-size: 9px; }"
        )
        if rows > 0:
            table.setRowCount(rows)
            self._fit_table_height(table, rows)
        return table

    def _fit_table_height(self, table: QTableWidget, row_count: int):
        h = table.horizontalHeader().height() + 2
        for r in range(row_count):
            h += table.rowHeight(r) if table.rowHeight(r) > 0 else 26
        table.setMinimumHeight(h)
        table.setMaximumHeight(h)

    def _set_cell(self, table, row: int, col: int, text: str,
                   color: str = "#2c3e50", bold: bool = False):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        font = QFont("Microsoft YaHei", 9, QFont.Bold if bold else QFont.Normal)
        item.setFont(font)
        item.setForeground(QColor(color))
        table.setItem(row, col, item)

    # ================================================================
    # 时域特征
    # ================================================================
    def _build_temporal_card(self) -> QGroupBox:
        card = self._make_card("⏱️ 时域特征")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["通道", "均值", "标准差", "RMS", "范围", "偏度", "峰度"]
        self._temporal_table = self._make_table(headers, 3)

        channels = ["ax", "ay", "gz"]
        for i, ch in enumerate(channels):
            self._set_cell(self._temporal_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 7):
                self._set_cell(self._temporal_table, i, j, "--", "#95a5a6")

        layout.addWidget(self._temporal_table)
        return card

    # ================================================================
    # 频域特征
    # ================================================================
    def _build_spectral_card(self) -> QGroupBox:
        card = self._make_card("📶 频域特征")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["通道", "主频 (Hz)", "谱质心", "谱熵"]
        self._spectral_table = self._make_table(headers, 3)

        channels = ["ax", "ay", "gz"]
        for i, ch in enumerate(channels):
            self._set_cell(self._spectral_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 4):
                self._set_cell(self._spectral_table, i, j, "--", "#95a5a6")

        layout.addWidget(self._spectral_table)
        return card

    # ================================================================
    # 运动学特征
    # ================================================================
    def _build_kinematic_card(self) -> QGroupBox:
        card = self._make_card("🚗 运动学特征 (Jerk / Snap)")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["通道", "Jerk", "Jerk RMS", "Jerk 峰值", "Snap", "Snap RMS"]
        self._kinematic_table = self._make_table(headers, 3)

        channels = ["ax", "ay", "gz"]
        for i, ch in enumerate(channels):
            self._set_cell(self._kinematic_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 6):
                self._set_cell(self._kinematic_table, i, j, "--", "#95a5a6")

        layout.addWidget(self._kinematic_table)
        return card

    # ================================================================
    # 物理特征
    # ================================================================
    def _build_physics_card(self) -> QGroupBox:
        card = self._make_card("🔬 物理特征 (车辆动力学)")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["指标", "数值", "单位"]
        self._physics_table = self._make_table(headers, 7)

        fields = [
            ("slip_angle_est", "侧偏角估计", "°"),
            ("expected_yaw_rate", "期望横摆角速度", "rad/s"),
            ("yaw_rate_error", "横摆角速度误差", "rad/s"),
            ("turn_radius", "转弯半径", "m"),
            ("lateral_accel_ratio", "侧向加速度比", ""),
            ("accel_speed_ratio", "纵加速/速度比", ""),
            ("speed_ms", "速度", "m/s"),
        ]
        for i, (key, label, unit) in enumerate(fields):
            self._set_cell(self._physics_table, i, 0, label, "#2c3e50")
            self._set_cell(self._physics_table, i, 1, "--", "#95a5a6")
            self._set_cell(self._physics_table, i, 2, unit, "#7f8c8d")

        layout.addWidget(self._physics_table)
        return card

    # ================================================================
    # 信号质量监控
    # ================================================================
    def _build_signal_card(self) -> QGroupBox:
        card = self._make_card("📡 信号质量监控")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 6)

        headers = ["通道", "SNR (dB)", "状态", "异常值", "饱和", "丢包"]
        self._signal_table = self._make_table(headers, 6)

        channels = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
        for i, ch in enumerate(channels):
            self._set_cell(self._signal_table, i, 0, ch, "#2980b9", True)
            self._set_cell(self._signal_table, i, 1, "--", "#95a5a6")
            self._set_cell(self._signal_table, i, 2, "无信号", "#95a5a6")
            self._set_cell(self._signal_table, i, 3, "0", "#95a5a6")
            self._set_cell(self._signal_table, i, 4, "0", "#95a5a6")
            self._set_cell(self._signal_table, i, 5, "0", "#95a5a6")

        layout.addWidget(self._signal_table)
        return card

    # ================================================================
    # 数据更新
    # ================================================================
    def update_frame_result(self, result):
        if result is None:
            return

        now = time.time()
        if now - getattr(self, '_last_update', 0) < 0.2:
            return
        self._last_update = now

        features = result.features
        if features and features is not self._latest_features:
            self._latest_features = features
            self._feature_history.append(features)
            self._update_features(features)

        # 使用真实的 quality 数据，不是硬编码
        self._update_signal_quality(result)

    def _update_features(self, features: FrameFeatures):
        self._update_temporal(features)
        self._update_spectral(features)
        self._update_kinematic(features)
        self._update_physics(features)

    def _update_temporal(self, features: FrameFeatures):
        channels = ["ax", "ay", "gz"]
        col_map = {
            "mean": 1, "std": 2, "rms": 3, "range": 4,
            "skewness": 5, "kurtosis": 6,
        }
        for i, ch in enumerate(channels):
            for suffix, col in col_map.items():
                key = f"{ch}_{suffix}"
                val = features.temporal.get(key)
                if val is not None:
                    self._set_cell(self._temporal_table, i, col, f"{val:.4f}")

    def _update_spectral(self, features: FrameFeatures):
        channels = ["ax", "ay", "gz"]
        col_map = {"dominant_freq": 1, "spectral_centroid": 2, "spectral_entropy": 3}
        for i, ch in enumerate(channels):
            for suffix, col in col_map.items():
                key = f"{ch}_{suffix}"
                val = features.spectral.get(key)
                if val is not None:
                    self._set_cell(self._spectral_table, i, col, f"{val:.4f}")

    def _update_kinematic(self, features: FrameFeatures):
        channels = ["ax", "ay", "gz"]
        col_map = {
            "jerk": 1, "jerk_rms": 2, "jerk_peak": 3,
            "snap": 4, "snap_rms": 5,
        }
        for i, ch in enumerate(channels):
            for suffix, col in col_map.items():
                key = f"{ch}_{suffix}"
                val = features.kinematic.get(key)
                if val is not None:
                    self._set_cell(self._kinematic_table, i, col, f"{val:.6f}")

    def _update_physics(self, features: FrameFeatures):
        field_map = {
            "slip_angle_est": (0, "{:.4f}"),
            "expected_yaw_rate": (1, "{:.4f}"),
            "yaw_rate_error": (2, "{:.4f}"),
            "turn_radius": (3, "{:.2f}"),
            "lateral_accel_ratio": (4, "{:.4f}"),
            "accel_speed_ratio": (5, "{:.4f}"),
            "speed_ms": (6, "{:.2f}"),
        }
        for key, (row, fmt) in field_map.items():
            val = features.physics.get(key)
            if val is not None:
                self._set_cell(self._physics_table, row, 1, fmt.format(val))

    def _update_signal_quality(self, result):
        channels = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
        for i, ch in enumerate(channels):
            is_valid = True
            
            # 从 FrameResult 的 quality 属性中获取真实的 SignalQuality 数据
            quality = result.quality.get(ch) if hasattr(result, 'quality') else None
            
            if quality:
                # 转换 SignalQuality dataclass 为 dict（如果需要）
                if hasattr(quality, 'snr'):
                    snr = quality.snr
                    outlier = quality.outlier_count
                    saturation = quality.saturation_count
                    dropout = quality.dropout_count
                    is_valid = quality.is_valid
                else:
                    snr = quality.get('snr', 0.0)
                    outlier = quality.get('outlier_count', 0)
                    saturation = quality.get('saturation_count', 0)
                    dropout = quality.get('dropout_count', 0)
                    is_valid = quality.get('is_valid', True)
            else:
                snr = 0.0
                outlier = 0
                saturation = 0
                dropout = 0
                is_valid = True

            self._set_cell(self._signal_table, i, 1, f"{snr:.1f}")

            if is_valid and snr > 25:
                status, color = "优秀", "#27ae60"
            elif is_valid and snr > 15:
                status, color = "一般", "#f1c40f"
            elif is_valid:
                status, color = "较差", "#e74c3c"
            else:
                status, color = "无信号", "#95a5a6"

            self._set_cell(self._signal_table, i, 2, status, color, True)
            self._set_cell(self._signal_table, i, 3, str(outlier), "#95a5a6")
            self._set_cell(self._signal_table, i, 4, str(saturation), "#95a5a6")
            self._set_cell(self._signal_table, i, 5, str(dropout), "#95a5a6")

    def reset(self):
        self._latest_features = None
        self._feature_history.clear()

        for i, ch in enumerate(["ax", "ay", "gz"]):
            self._set_cell(self._temporal_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 7):
                self._set_cell(self._temporal_table, i, j, "--", "#95a5a6")

            self._set_cell(self._spectral_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 4):
                self._set_cell(self._spectral_table, i, j, "--", "#95a5a6")

            self._set_cell(self._kinematic_table, i, 0, ch, "#2980b9", True)
            for j in range(1, 6):
                self._set_cell(self._kinematic_table, i, j, "--", "#95a5a6")

        physics_fields = [
            "侧偏角估计", "期望横摆角速度", "横摆角速度误差",
            "转弯半径", "侧向加速度比", "纵加速/速度比", "速度",
        ]
        for i, label in enumerate(physics_fields):
            self._set_cell(self._physics_table, i, 0, label, "#2c3e50")
            self._set_cell(self._physics_table, i, 1, "--", "#95a5a6")

        for i, ch in enumerate(['ax', 'ay', 'az', 'gx', 'gy', 'gz']):
            self._set_cell(self._signal_table, i, 0, ch, "#2980b9", True)
            self._set_cell(self._signal_table, i, 1, "--", "#95a5a6")
            self._set_cell(self._signal_table, i, 2, "无信号", "#95a5a6")
            self._set_cell(self._signal_table, i, 3, "0", "#95a5a6")
            self._set_cell(self._signal_table, i, 4, "0", "#95a5a6")
            self._set_cell(self._signal_table, i, 5, "0", "#95a5a6")
