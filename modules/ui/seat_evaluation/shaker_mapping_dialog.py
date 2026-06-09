#!/usr/bin/env python3
"""手动通道配置对话框 — 自动检测失败后由用户指定各通道对应的列索引"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QDoubleSpinBox, QPushButton, QFormLayout, QGroupBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt


class ShakerManualMappingDialog(QDialog):
    """手动映射对话框。

    用户指定 CSV / Excel 中每一列所对应的传感器通道，
    以及采样率。点击确定后通过 ``get_mapping()`` 获取配置字典。
    """

    def __init__(self, parent=None, num_columns: int = 10):
        super().__init__(parent)
        self.num_columns = max(num_columns, 1)

        self._spin_time: QSpinBox = None
        self._spin_platform_x: QSpinBox = None
        self._spin_platform_y: QSpinBox = None
        self._spin_platform_z: QSpinBox = None
        self._spin_rpoint_x: QSpinBox = None
        self._spin_rpoint_y: QSpinBox = None
        self._spin_rpoint_z: QSpinBox = None
        self._spin_t8_x: QSpinBox = None
        self._spin_t8_y: QSpinBox = None
        self._spin_t8_z: QSpinBox = None
        self._spin_fs: QDoubleSpinBox = None

        self._init_ui()

    # ------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("手动配置通道映射")
        self.resize(420, 460)

        root = QVBoxLayout(self)

        # ── 说明 ──
        hint = QLabel(
            "自动检测未能识别所有通道。\n"
            "请手动指定每一列 (从 0 开始编号) 对应的传感器信号，\n"
            "并输入正确的采样率。"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        # ── 通道映射 ──
        map_group = QGroupBox("通道 → 列索引")
        form = QFormLayout(map_group)

        spin_opts = self._spin_opts()

        self._spin_time       = self._add_spin_row(form, "时间列",         spin_opts)
        self._spin_platform_x = self._add_spin_row(form, "平台 X (加速度)", spin_opts)
        self._spin_platform_y = self._add_spin_row(form, "平台 Y (加速度)", spin_opts)
        self._spin_platform_z = self._add_spin_row(form, "平台 Z (加速度)", spin_opts)
        self._spin_rpoint_x   = self._add_spin_row(form, "R点 X (加速度)",  spin_opts)
        self._spin_rpoint_y   = self._add_spin_row(form, "R点 Y (加速度)",  spin_opts)
        self._spin_rpoint_z   = self._add_spin_row(form, "R点 Z (加速度)",  spin_opts)
        self._spin_t8_x       = self._add_spin_row(form, "T8 X (加速度)",   spin_opts)
        self._spin_t8_y       = self._add_spin_row(form, "T8 Y (加速度)",   spin_opts)
        self._spin_t8_z       = self._add_spin_row(form, "T8 Z (加速度)",   spin_opts)

        root.addWidget(map_group)

        # ── 采样率 ──
        fs_group = QGroupBox("采样参数")
        fs_layout = QFormLayout(fs_group)

        self._spin_fs = QDoubleSpinBox()
        self._spin_fs.setRange(1.0, 100000.0)
        self._spin_fs.setDecimals(1)
        self._spin_fs.setValue(1000.0)
        self._spin_fs.setSuffix(" Hz")
        fs_layout.addRow("采样率:", self._spin_fs)

        root.addWidget(fs_group)

        # ── 按钮 ──
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    def _spin_opts(self) -> dict:
        """返回所有 SpinBox 的通用配置。"""
        return {
            "minimum": 0,
            "maximum": self.num_columns - 1,
            "value": 0,
            "prefix": "列 ",
        }

    @staticmethod
    def _add_spin_row(form: QFormLayout, label: str, opts: dict) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(opts["minimum"], opts["maximum"])
        spin.setValue(opts["value"])
        spin.setPrefix(opts["prefix"])
        form.addRow(label, spin)
        return spin

    # ------------------------------------------------------------------
    def get_mapping(self) -> dict:
        """返回当前配置的通道映射字典。

        Returns
        -------
        dict
            {
                'time_col': int,        # 时间列索引
                'platform_x': int,      # 平台 X 列索引
                'platform_y': int,
                'platform_z': int,
                'rpoint_x': int,        # R 点 X 列索引
                'rpoint_y': int,
                'rpoint_z': int,
                't8_x': int,            # T8 X 列索引
                't8_y': int,
                't8_z': int,
                'fs': float,            # 采样率
            }
        """
        return {
            "time_col":   self._spin_time.value(),
            "platform_x": self._spin_platform_x.value(),
            "platform_y": self._spin_platform_y.value(),
            "platform_z": self._spin_platform_z.value(),
            "rpoint_x":   self._spin_rpoint_x.value(),
            "rpoint_y":   self._spin_rpoint_y.value(),
            "rpoint_z":   self._spin_rpoint_z.value(),
            "t8_x":       self._spin_t8_x.value(),
            "t8_y":       self._spin_t8_y.value(),
            "t8_z":       self._spin_t8_z.value(),
            "fs":         self._spin_fs.value(),
        }