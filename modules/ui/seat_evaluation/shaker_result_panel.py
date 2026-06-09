#!/usr/bin/env python3
"""台架实验结果展示面板"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QFrame, QTextEdit
)
from PySide6.QtCore import Qt


class ShakerResultPanel(QWidget):
    """台架试验分析结果展示面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    # ------------------------------------------------------------------
    # UI 搭建
    # ------------------------------------------------------------------
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ---------- 外框 ----------
        self._frame = QFrame()
        self._frame.setFrameStyle(QFrame.StyledPanel)
        self._frame.setObjectName("shakerResultFrame")

        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)

        # ---------- 工况标签 ----------
        self._condition_label = QLabel("当前工况: --")
        self._condition_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._condition_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-bottom: 6px;"
        )
        frame_layout.addWidget(self._condition_label)

        # ---------- 指标摘要 ----------
        self._metrics_label = QLabel("")
        self._metrics_label.setWordWrap(True)
        self._metrics_label.setStyleSheet("margin-bottom: 6px;")
        frame_layout.addWidget(self._metrics_label)

        # ---------- 选项卡 ----------
        self._tab_widget = QTabWidget()
        frame_layout.addWidget(self._tab_widget)

        # SEAT因子 页面
        self._seat_tab = QWidget()
        seat_layout = QVBoxLayout(self._seat_tab)
        self._seat_placeholder = QLabel("SEAT 柱状图区域")
        self._seat_placeholder.setAlignment(Qt.AlignCenter)
        self._seat_placeholder.setStyleSheet("color: #888; font-size: 16px;")
        seat_layout.addWidget(self._seat_placeholder)
        self._tab_widget.addTab(self._seat_tab, "SEAT因子")

        # 传递函数 页面
        self._transfer_tab = QWidget()
        transfer_layout = QVBoxLayout(self._transfer_tab)
        self._transfer_placeholder = QLabel("传递函数图区域")
        self._transfer_placeholder.setAlignment(Qt.AlignCenter)
        self._transfer_placeholder.setStyleSheet("color: #888; font-size: 16px;")
        transfer_layout.addWidget(self._transfer_placeholder)
        self._tab_widget.addTab(self._transfer_tab, "传递函数")

        # PSD频谱 页面
        self._psd_tab = QWidget()
        psd_layout = QVBoxLayout(self._psd_tab)
        self._psd_placeholder = QLabel("PSD 频谱图区域")
        self._psd_placeholder.setAlignment(Qt.AlignCenter)
        self._psd_placeholder.setStyleSheet("color: #888; font-size: 16px;")
        psd_layout.addWidget(self._psd_placeholder)
        self._tab_widget.addTab(self._psd_tab, "PSD频谱")

        # ---------- 加权 RMS 摘要 ----------
        self._rms_text = QTextEdit()
        self._rms_text.setReadOnly(True)
        self._rms_text.setMaximumHeight(120)
        self._rms_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        frame_layout.addWidget(self._rms_text)

        main_layout.addWidget(self._frame)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------
    def update_results(self, result):
        """使用 AnalysisResult 更新面板内容。

        Parameters
        ----------
        result : AnalysisResult
            来自 shaker_models 的分析结果数据类，预期属性：
            condition_name, seat, resonance_summary,
            weighted_rms, time_domain, duration, fs
        """
        if result is None:
            self._condition_label.setText("当前工况: --")
            self._metrics_label.setText("")
            self._rms_text.clear()
            return

        # 1. 工况
        self._condition_label.setText(f"当前工况: {result.condition_name}")

        # 2. 关键指标
        seat = getattr(result, "seat", None)
        resonance = getattr(result, "resonance_summary", None)

        seat_overall = ""
        seat_grade = ""
        resonance_channels = ""

        if seat is not None:
            seat_overall = str(getattr(seat, "overall", "--"))
            seat_grade = str(getattr(seat, "grade", "--"))

        if resonance is not None:
            if isinstance(resonance, dict):
                resonance_channels = str(resonance.get("channel_count", "--"))
            else:
                resonance_channels = str(
                    getattr(resonance, "channel_count", "--")
                )

        metrics_text = (
            f"SEAT Overall: {seat_overall}    "
            f"Grade: {seat_grade}    "
            f"共振通道数: {resonance_channels}"
        )
        self._metrics_label.setText(metrics_text)

        # 3. 加权 RMS 摘要
        weighted_rms = getattr(result, "weighted_rms", None)
        self._rms_text.clear()

        if weighted_rms is not None:
            if isinstance(weighted_rms, dict):
                lines = ["Weighted RMS (各通道):"]
                for ch_name, val in weighted_rms.items():
                    lines.append(f"  {ch_name}: {val}")
                self._rms_text.setPlainText("\n".join(lines))
            else:
                self._rms_text.setPlainText(str(weighted_rms))
        else:
            self._rms_text.setPlainText("(无加权 RMS 数据)")