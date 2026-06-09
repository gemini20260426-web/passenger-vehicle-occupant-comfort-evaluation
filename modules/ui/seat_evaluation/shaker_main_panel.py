#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""振动台架实验主面板 (ISO 10326-1)"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox, QGroupBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QSizePolicy

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import numpy as np

from .shaker_import_panel import ShakerImportPanel
from .shaker_worker import ShakerAnalysisWorker


class ShakerMainPanel(QWidget):
    """ISO 10326-1 振动台架实验主面板。

    整合数据导入、分析执行、结果展示（SEAT因子 / 传递函数 /
    PSD频谱 / 多工况对比 / 数据表格）的容器组件。
    """

    # 通道名缩写
    CHANNEL_SHORT = {
        'r_point_x': 'R点 X', 'r_point_y': 'R点 Y', 'r_point_z': 'R点 Z',
        't8_x': 'T8 X', 't8_y': 'T8 Y', 't8_z': 'T8 Z',
        'platform_x': '平台 X', 'platform_y': '平台 Y', 'platform_z': '平台 Z',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []
        self._worker = None
        self._init_ui()

    # ══════════════════════════════════════════════════════
    # UI 构建
    # ══════════════════════════════════════════════════════

    def _init_ui(self):
        # 外层布局: 仅放一个 QScrollArea 实现垂直滚动 + 高度自适应
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        # 内层容器: 所有实际内容
        inner = QWidget()
        inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        root = QVBoxLayout(inner)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        # ── 上部: 数据导入面板 ──
        self._import_panel = ShakerImportPanel()
        root.addWidget(self._import_panel)

        # ── 中部: 进度区域 (默认隐藏) ──
        self._progress_group = self._create_progress_area()
        self._progress_group.setVisible(False)
        root.addWidget(self._progress_group)

        # ── 下部: 结果卡片 (全量显示) ──
        self._seat_card = self._make_card("SEAT 因子", self._create_seat_result_tab())
        root.addWidget(self._seat_card)

        self._tf_card = self._make_card("传递函数", self._create_tf_result_tab())
        root.addWidget(self._tf_card)

        self._psd_card = self._make_card("PSD 频谱", self._create_psd_result_tab())
        root.addWidget(self._psd_card)

        self._cross_card = self._make_card("多工况对比", self._create_cross_result_tab())
        root.addWidget(self._cross_card)

        self._table_card = self._make_card("数据表格", self._create_table_result_tab())
        root.addWidget(self._table_card)

        # ── 信号连接 ──
        self._import_panel.files_loaded.connect(self._on_files_loaded)
        self._import_panel.start_analysis.connect(lambda _mode: self.start_analysis())
        self._import_panel._btn_stop.clicked.connect(self._on_cancel)

        scroll.setWidget(inner)

    def _create_progress_area(self) -> QGroupBox:
        """进度条 + 状态文本区域"""
        group = QGroupBox("分析进度")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(22)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("准备中...")
        self._progress_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self._progress_label)

        return group

    @staticmethod
    def _make_card(title: str, content: QWidget) -> QGroupBox:
        """创建统一样式的卡片容器"""
        card = QGroupBox(title)
        card.setStyleSheet("""
            QGroupBox {
                font-size: 13px; font-weight: bold;
                border: 1px solid #d0d7de; border-radius: 8px;
                margin-top: 10px; padding-top: 18px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px; padding: 2px 8px;
                color: #2c3e50;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.addWidget(content)
        return card

    # ══════════════════════════════════════════════════════
    # SEAT因子标签页
    # ══════════════════════════════════════════════════════

    def _create_seat_result_tab(self) -> QWidget:
        """SEAT因子结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._seat_summary = QLabel("等待分析...")
        self._seat_summary.setStyleSheet("font-size: 13px; padding: 6px;")
        layout.addWidget(self._seat_summary)

        self._seat_warning = QLabel()
        self._seat_warning.setVisible(False)
        self._seat_warning.setStyleSheet(
            "font-size: 12px; padding: 6px 10px; margin: 4px 0;"
            "background: #fff3cd; color: #856404;"
            "border: 1px solid #ffc107; border-radius: 4px;"
            "font-weight: bold;"
        )
        layout.addWidget(self._seat_warning)

        self._seat_table = QTableWidget()
        self._seat_table.setColumnCount(5)
        self._seat_table.setHorizontalHeaderLabels(
            ["通道", "SEAT (%)", "等级", "加权RMS", "VDV"]
        )
        self._seat_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        layout.addWidget(self._seat_table, 1)

        return widget

    # ══════════════════════════════════════════════════════
    # 传递函数标签页
    # ══════════════════════════════════════════════════════

    def _create_tf_result_tab(self) -> QWidget:
        """传递函数结果标签页 — 幅频 + 相干 + 峰值表"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # 工况选择器
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("选择工况:"))
        self._tf_condition_combo = QComboBox()
        self._tf_condition_combo.currentIndexChanged.connect(self._on_tf_condition_changed)
        sel_layout.addWidget(self._tf_condition_combo)

        sel_layout.addSpacing(20)
        sel_layout.addWidget(QLabel("传递路径:"))
        self._tf_path_combo = QComboBox()
        self._tf_path_combo.currentIndexChanged.connect(self._on_tf_path_changed)
        sel_layout.addWidget(self._tf_path_combo)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # 图表容器 (matplotlib)
        self._tf_canvas_container = QWidget()
        self._tf_canvas_container.setMinimumHeight(320)
        self._tf_canvas_layout = QVBoxLayout(self._tf_canvas_container)
        self._tf_canvas_layout.setContentsMargins(0, 0, 0, 0)
        self._tf_canvas = None
        self._tf_fig = None
        layout.addWidget(self._tf_canvas_container, 2)

        # 初始化空占位图表
        self._init_placeholder_chart(self._tf_canvas_layout, "传递函数\n加载数据并分析后显示")

        # 峰值表格
        self._tf_peak_label = QLabel("共振峰检测结果")
        self._tf_peak_label.setStyleSheet("font-weight: bold; font-size: 12px; padding-top: 4px;")
        layout.addWidget(self._tf_peak_label)

        self._tf_peak_table = QTableWidget()
        self._tf_peak_table.setColumnCount(5)
        self._tf_peak_table.setHorizontalHeaderLabels(
            ["序号", "频率 (Hz)", "增益 (dB)", "相干系数 γ²", "备注"]
        )
        self._tf_peak_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._tf_peak_table, 1)

        return widget

    # ══════════════════════════════════════════════════════
    # PSD频谱标签页
    # ══════════════════════════════════════════════════════

    def _create_psd_result_tab(self) -> QWidget:
        """PSD频谱结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # 工况 + 位置选择
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("工况:"))
        self._psd_condition_combo = QComboBox()
        self._psd_condition_combo.currentIndexChanged.connect(self._on_psd_selection_changed)
        sel_layout.addWidget(self._psd_condition_combo)
        sel_layout.addSpacing(20)
        sel_layout.addWidget(QLabel("对比位置:"))
        self._psd_location_combo = QComboBox()
        self._psd_location_combo.addItems(["全部 (平台/R点/T8)", "仅平台", "仅R点", "仅T8", "平台 vs R点", "平台 vs T8"])
        self._psd_location_combo.currentIndexChanged.connect(self._on_psd_selection_changed)
        sel_layout.addWidget(self._psd_location_combo)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # PSD图表
        self._psd_canvas_container = QWidget()
        self._psd_canvas_container.setMinimumHeight(350)
        self._psd_canvas_layout = QVBoxLayout(self._psd_canvas_container)
        self._psd_canvas_layout.setContentsMargins(0, 0, 0, 0)
        self._psd_fig = None
        layout.addWidget(self._psd_canvas_container, 1)

        # 初始化空占位图表
        self._init_placeholder_chart(self._psd_canvas_layout, "PSD 频谱\n加载数据并分析后显示")

        return widget

    def _on_psd_selection_changed(self):
        if self._results:
            idx = self._psd_condition_combo.currentIndex()
            if idx >= 0:
                loc_mode = self._psd_location_combo.currentText()
                self._display_psd_for_result(self._results[idx], loc_mode)

    # ══════════════════════════════════════════════════════
    # 多工况对比标签页
    # ══════════════════════════════════════════════════════

    def _create_cross_result_tab(self) -> QWidget:
        """多工况对比标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # 对比类型选择
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("对比指标:"))
        self._cross_metric_combo = QComboBox()
        self._cross_metric_combo.addItems(["SEAT因子 (%)", "加权RMS (m/s²)", "VDV (m/s^1.75)"])
        self._cross_metric_combo.currentIndexChanged.connect(self._on_cross_metric_changed)
        sel_layout.addWidget(self._cross_metric_combo)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # 对比矩阵表格
        self._cross_table = QTableWidget()
        self._cross_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._cross_table, 1)

        # 排名汇总
        self._cross_summary = QLabel()
        self._cross_summary.setStyleSheet(
            "font-size: 12px; padding: 6px; background: #f0f4f8; border-radius: 4px;"
        )
        layout.addWidget(self._cross_summary)

        return widget

    def _on_cross_metric_changed(self):
        if self._results:
            metric = self._cross_metric_combo.currentIndex()
            self._display_cross_results(self._results, metric)

    # ══════════════════════════════════════════════════════
    # 数据表格标签页
    # ══════════════════════════════════════════════════════

    def _create_table_result_tab(self) -> QWidget:
        """综合数据表格标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._data_table = QTableWidget()
        self._data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._data_table, 1)

        return widget

    # ══════════════════════════════════════════════════════
    # 分析流程
    # ══════════════════════════════════════════════════════

    def start_analysis(self):
        """启动后台分析"""
        files = self._import_panel.checked_files()
        if not files:
            QMessageBox.warning(self, "提示", "请先导入数据文件。")
            return

        # 显示进度区域
        self._progress_group.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_label.setText("启动分析...")
        self._import_panel._btn_start.setEnabled(False)
        self._import_panel._btn_stop.setEnabled(True)
        self._import_panel.set_running_state(True)

        # 启动后台工作线程
        self._worker = ShakerAnalysisWorker(files)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        """更新进度条与状态文本"""
        self._progress_bar.setValue(pct)
        self._progress_label.setText(msg)

    def _on_finished(self, results: list):
        """分析完成，隐藏进度，展示所有结果"""
        self._results = results
        self._progress_group.setVisible(False)
        self._import_panel._btn_start.setEnabled(True)
        self._import_panel._btn_stop.setEnabled(False)
        self._import_panel.set_running_state(False)
        self._progress_label.setText(f"分析完成 ({len(results)} 个工况)")

        # 展示各标签页结果
        self._display_seat_results(results)
        self._display_tf_results(results)
        self._display_psd_results(results, "全部 (平台/R点/T8)")
        self._display_cross_results(results, 0)
        self._display_table_results(results)

    # ══════════════════════════════════════════════════════
    # SEAT因子展示
    # ══════════════════════════════════════════════════════

    def _display_seat_results(self, results: list):
        """在SEAT因子标签页展示结果，含低激励警告"""
        if not results:
            self._seat_summary.setText("无分析结果")
            self._seat_warning.setVisible(False)
            return

        # ── 警告横幅 ──
        all_low_channels = set()
        for r in results:
            all_low_channels.update(r.low_excitation_channels)

        if all_low_channels:
            low_list = sorted(all_low_channels)
            low_count = len(low_list)
            self._seat_warning.setText(
                f"⚠ ISO 10326-1 §5.2.3: 检测到 {low_count} 个低激励通道 "
                f"({', '.join(low_list)})，对应 SEAT 值不可靠。"
                f"建议提高台架激励幅值。"
            )
            self._seat_warning.setVisible(True)
        else:
            self._seat_warning.setVisible(False)

        # ── 汇总文字 ──
        summary_parts = []
        for r in results:
            seat_val = r.seat.seat_values.get('r_point_z', float('inf'))
            seat_str = f"{seat_val:.1f}%" if seat_val < 1e10 else "N/A"
            low_mark = " ⚠" if 'r_point_z' in r.low_excitation_channels else ""
            summary_parts.append(
                f"{r.condition_name}: SEAT Rz={seat_str}{low_mark} ({r.seat.grade})"
            )
        self._seat_summary.setText(" | ".join(summary_parts))

        # ── 表格 ──
        all_seat_keys = []
        for r in results:
            for k in r.seat.seat_values:
                if k not in all_seat_keys:
                    all_seat_keys.append(k)
        all_seat_keys.sort(key=lambda k: (0 if k.startswith('r_point') else 1, k))

        n_rows = len(results)
        n_cols = len(all_seat_keys)
        self._seat_table.setRowCount(n_rows)
        self._seat_table.setColumnCount(n_cols)
        headers = [self.CHANNEL_SHORT.get(k, k) for k in all_seat_keys]
        self._seat_table.setHorizontalHeaderLabels(headers)

        GREEN = QBrush(QColor('#28a745'))
        GREEN_BG = QColor('#d4edda')
        YELLOW = QBrush(QColor('#ffc107'))
        YELLOW_BG = QColor('#fff3cd')
        RED = QBrush(QColor('#dc3545'))
        RED_BG = QColor('#f8d7da')
        GRAY = QBrush(QColor('#adb5bd'))
        GRAY_BG = QColor('#e9ecef')

        for row, r in enumerate(results):
            for col, key in enumerate(all_seat_keys):
                seat_val = r.seat.seat_values.get(key, float('inf'))
                if key in r.low_excitation_channels:
                    cell_text = f"({seat_val:.0f}%)" if seat_val < 1e10 else "N/A"
                    item = QTableWidgetItem(cell_text)
                    item.setForeground(GRAY)
                    item.setBackground(GRAY_BG)
                    item.setToolTip(f"{key}: 平台激励过低，SEAT 值不可靠")
                elif seat_val <= 100:
                    item = QTableWidgetItem(f"{seat_val:.0f}%")
                    item.setForeground(GREEN)
                    item.setBackground(GREEN_BG)
                elif seat_val <= 200:
                    item = QTableWidgetItem(f"{seat_val:.0f}%")
                    item.setForeground(YELLOW)
                    item.setBackground(YELLOW_BG)
                else:
                    item = QTableWidgetItem(f"{seat_val:.0f}%")
                    item.setForeground(RED)
                    item.setBackground(RED_BG)
                item.setTextAlignment(Qt.AlignCenter)
                self._seat_table.setItem(row, col, item)

        self._seat_table.setVerticalHeaderLabels([r.condition_name for r in results])
        self._seat_table.resizeColumnsToContents()
        self._seat_table.resizeRowsToContents()

    # ══════════════════════════════════════════════════════
    # 传递函数展示
    # ══════════════════════════════════════════════════════

    def _display_tf_results(self, results: list):
        """填充传递函数标签页的工况和路径选择器，并展示第一个"""
        self._tf_condition_combo.blockSignals(True)
        self._tf_condition_combo.clear()
        for r in results:
            self._tf_condition_combo.addItem(r.condition_name)
        self._tf_condition_combo.blockSignals(False)

        if results:
            self._tf_condition_combo.setCurrentIndex(0)

    def _display_tf_for_result(self, result):
        """为单个工况展示传递函数"""
        tf_data = result.transfer_functions
        if not tf_data:
            return

        # 更新路径选择器
        self._tf_path_combo.blockSignals(True)
        self._tf_path_combo.clear()
        all_paths = sorted(tf_data.keys(), key=lambda k: (0 if 'r_point' in k else 1, k))
        for path in all_paths:
            self._tf_path_combo.addItem(self.CHANNEL_SHORT.get(path, path))
        self._tf_path_combo.blockSignals(False)

        if all_paths:
            self._tf_path_combo.setCurrentIndex(0)

    def _on_tf_condition_changed(self, idx: int):
        if self._results and 0 <= idx < len(self._results):
            self._display_tf_for_result(self._results[idx])

    def _on_tf_path_changed(self, idx: int):
        if self._results and idx >= 0:
            cond_idx = self._tf_condition_combo.currentIndex()
            if 0 <= cond_idx < len(self._results):
                self._display_tf_chart(self._results[cond_idx], idx)

    def _display_tf_chart(self, result, path_idx: int):
        """渲染传递函数图表"""
        tf_data = result.transfer_functions
        all_paths = sorted(tf_data.keys(), key=lambda k: (0 if 'r_point' in k else 1, k))
        if path_idx >= len(all_paths):
            return
        path_key = all_paths[path_idx]
        tr = tf_data[path_key]

        # 创建 matplotlib Figure
        self._tf_fig = Figure(figsize=(9, 6), dpi=100)
        ax1 = self._tf_fig.add_subplot(211)
        ax2 = self._tf_fig.add_subplot(212, sharex=ax1)

        # 幅频响应 (dB)
        mag_db = 20 * np.log10(np.maximum(tr.magnitude, 1e-10))
        ax1.semilogx(tr.frequencies, mag_db, 'b-', linewidth=1.2)
        ax1.set_ylabel('增益 (dB)', fontsize=10)
        ax1.set_title(f'{result.condition_name} — {self.CHANNEL_SHORT.get(path_key, path_key)} 传递函数',
                       fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

        # 标记峰值
        for pf, pg in zip(tr.peak_freqs[:3], tr.peak_gains[:3]):
            pg_db = 20 * np.log10(max(pg, 1e-10))
            ax1.axvline(x=pf, color='red', linestyle='--', alpha=0.4, linewidth=0.8)
            ax1.annotate(f'{pf:.1f} Hz', xy=(pf, pg_db),
                         xytext=(5, 5), textcoords='offset points',
                         fontsize=8, color='red')

        # 相干函数
        ax2.semilogx(tr.frequencies, tr.coherence, 'g-', linewidth=1.2)
        ax2.set_xlabel('频率 (Hz)', fontsize=10)
        ax2.set_ylabel('相干系数 γ²', fontsize=10)
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5, label='γ²=0.5 阈值')
        ax2.legend(fontsize=8)

        self._tf_fig.tight_layout()

        # 嵌入容器
        self._clear_layout(self._tf_canvas_layout)
        canvas = FigureCanvas(self._tf_fig)
        self._tf_canvas_layout.addWidget(canvas)

        # 峰值表格
        n_peaks = min(len(tr.peak_freqs), 10)
        self._tf_peak_table.setRowCount(n_peaks)
        for i in range(n_peaks):
            freq = tr.peak_freqs[i]
            gain_db = 20 * np.log10(max(tr.peak_gains[i], 1e-10))
            coh = tr.peak_coherences[i]
            note = ""
            if coh < 0.5:
                note = "相干性不足"
            elif gain_db > 6:
                note = "强共振"

            self._tf_peak_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._tf_peak_table.setItem(i, 1, QTableWidgetItem(f"{freq:.2f}"))
            self._tf_peak_table.setItem(i, 2, QTableWidgetItem(f"{gain_db:.2f}"))
            self._tf_peak_table.setItem(i, 3, QTableWidgetItem(f"{coh:.4f}"))
            self._tf_peak_table.setItem(i, 4, QTableWidgetItem(note))
        self._tf_peak_table.resizeColumnsToContents()

    # ══════════════════════════════════════════════════════
    # PSD频谱展示
    # ══════════════════════════════════════════════════════

    def _display_psd_results(self, results: list, loc_mode: str = "全部 (平台/R点/T8)"):
        """填充PSD标签页的工况选择器并展示"""
        self._psd_condition_combo.blockSignals(True)
        self._psd_condition_combo.clear()
        for r in results:
            self._psd_condition_combo.addItem(r.condition_name)
        self._psd_condition_combo.blockSignals(False)

        if results:
            self._psd_condition_combo.setCurrentIndex(0)

    def _display_psd_for_result(self, result, loc_mode: str):
        """渲染PSD频谱图"""
        psd_data = result.psd
        if not psd_data:
            return

        # 解析位置模式
        if loc_mode == "全部 (平台/R点/T8)":
            locations = ['platform', 'r_point', 't8']
        elif loc_mode == "仅平台":
            locations = ['platform']
        elif loc_mode == "仅R点":
            locations = ['r_point']
        elif loc_mode == "仅T8":
            locations = ['t8']
        elif loc_mode == "平台 vs R点":
            locations = ['platform', 'r_point']
        elif loc_mode == "平台 vs T8":
            locations = ['platform', 't8']
        else:
            locations = ['platform', 'r_point', 't8']

        axes = ['x', 'y', 'z']
        n_loc = len(locations)
        n_ax = len(axes)

        self._psd_fig = Figure(figsize=(12, 3 * n_ax), dpi=100)
        colors = {'platform': '#1f77b4', 'r_point': '#ff7f0e', 't8': '#2ca02c'}
        labels = {'platform': '平台', 'r_point': 'R点', 't8': 'T8'}

        for ax_idx, ax_name in enumerate(axes):
            sub = self._psd_fig.add_subplot(n_ax, 1, ax_idx + 1)
            for loc in locations:
                key = f"{loc}_{ax_name}"
                if key in psd_data:
                    psd = psd_data[key]
                    sub.loglog(psd.frequencies, psd.psd,
                               color=colors.get(loc, '#333'),
                               label=labels.get(loc, loc),
                               linewidth=1.0, alpha=0.85)
            sub.set_ylabel(f'{ax_name.upper()} PSD\n((m/s²)²/Hz)', fontsize=9)
            sub.grid(True, alpha=0.3, which='both')
            sub.legend(fontsize=8, loc='upper right')
            if ax_idx == 0:
                sub.set_title(f'PSD频谱 — {result.condition_name}', fontsize=11, fontweight='bold')
            if ax_idx == n_ax - 1:
                sub.set_xlabel('频率 (Hz)', fontsize=9)

        self._psd_fig.tight_layout()

        self._clear_layout(self._psd_canvas_layout)
        canvas = FigureCanvas(self._psd_fig)
        self._psd_canvas_layout.addWidget(canvas)

    # ══════════════════════════════════════════════════════
    # 多工况对比展示
    # ══════════════════════════════════════════════════════

    def _display_cross_results(self, results: list, metric_idx: int):
        """多工况对比矩阵"""
        if not results:
            return

        # 收集所有SEAT通道
        all_channels = []
        for r in results:
            for k in r.seat.seat_values:
                if k not in all_channels:
                    all_channels.append(k)
        all_channels.sort(key=lambda k: (0 if k.startswith('r_point') else 1, k))

        n_rows = len(results)
        n_cols = len(all_channels)
        self._cross_table.setRowCount(n_rows)
        self._cross_table.setColumnCount(n_cols)
        headers = [self.CHANNEL_SHORT.get(k, k) for k in all_channels]
        self._cross_table.setHorizontalHeaderLabels(headers)
        self._cross_table.setVerticalHeaderLabels([r.condition_name for r in results])

        GREEN = QBrush(QColor('#28a745'))
        GREEN_BG = QColor('#d4edda')
        YELLOW = QBrush(QColor('#e67e22'))
        YELLOW_BG = QColor('#fff3cd')
        RED = QBrush(QColor('#dc3545'))
        RED_BG = QColor('#f8d7da')
        GRAY = QBrush(QColor('#adb5bd'))
        GRAY_BG = QColor('#e9ecef')

        for row, r in enumerate(results):
            for col, ch in enumerate(all_channels):
                if metric_idx == 0:  # SEAT
                    val = r.seat.seat_values.get(ch, float('inf'))
                    cell_text = f"{val:.0f}%" if val < 1e10 else "N/A"
                    color, bg = GREEN, GREEN_BG
                    if ch in r.low_excitation_channels:
                        color, bg = GRAY, GRAY_BG
                        cell_text = f"({val:.0f}%)" if val < 1e10 else "N/A"
                    elif val > 200:
                        color, bg = RED, RED_BG
                    elif val > 100:
                        color, bg = YELLOW, YELLOW_BG
                elif metric_idx == 1:  # RMS
                    val = r.weighted_rms.get(ch, -1)
                    cell_text = f"{val:.3f}" if val >= 0 else "N/A"
                    color, bg = QBrush(QColor('#333')), QColor('#ffffff')
                    if val > 3.0:
                        color, bg = RED, RED_BG
                    elif val > 1.5:
                        color, bg = YELLOW, YELLOW_BG
                else:  # VDV
                    td = r.time_domain.get(ch)
                    val = td.vdv if td else -1
                    cell_text = f"{val:.2f}" if val >= 0 else "N/A"
                    color, bg = QBrush(QColor('#333')), QColor('#ffffff')
                    if val > 8.5:
                        color, bg = RED, RED_BG
                    elif val > 4.0:
                        color, bg = YELLOW, YELLOW_BG

                item = QTableWidgetItem(cell_text)
                item.setForeground(color)
                item.setBackground(bg)
                item.setTextAlignment(Qt.AlignCenter)
                self._cross_table.setItem(row, col, item)

        self._cross_table.resizeColumnsToContents()
        self._cross_table.resizeRowsToContents()

        # 排名汇总
        metric_names = ["SEAT因子", "加权RMS", "VDV"]
        metric_name = metric_names[metric_idx] if metric_idx < 3 else "指标"

        # 按 overall SEAT 排名
        sorted_results = sorted(results, key=lambda r: r.seat.overall)
        rank_parts = []
        for i, r in enumerate(sorted_results):
            seat_val = r.seat.overall
            seat_str = f"{seat_val:.0f}%" if seat_val < 1e10 else "N/A"
            rank_parts.append(f"#{i+1} {r.condition_name} (SEAT={seat_str})")
        self._cross_summary.setText(
            f"SEAT 综合排名: {'  >  '.join(rank_parts)}  |  "
            f"最优工况: {sorted_results[0].condition_name if sorted_results else 'N/A'}"
        )

    # ══════════════════════════════════════════════════════
    # 数据表格展示
    # ══════════════════════════════════════════════════════

    def _display_table_results(self, results: list):
        """综合数据表格 — 所有通道的时域指标"""
        if not results:
            return

        # 列: 工况 | 位置 | 通道 | RMS | VDV | 峰值 | CF | MTVV | SEAT
        columns = ["工况", "位置", "通道", "加权RMS", "VDV", "峰值", "波峰因子", "MTVV", "SEAT(%)"]

        # 展开所有通道
        rows_data = []
        for r in results:
            for ch, td in r.time_domain.items():
                seat = r.seat.seat_values.get(ch, float('inf'))
                loc = "平台" if ch.startswith("platform") else ("R点" if ch.startswith("r_point") else "T8")
                ax = ch.split('_')[-1].upper()
                rows_data.append({
                    'condition': r.condition_name,
                    'location': loc,
                    'channel': f"{loc} {ax}",
                    'rms': td.rms,
                    'vdv': td.vdv,
                    'peak': td.peak,
                    'cf': td.crest_factor,
                    'mtvv': td.mtvv,
                    'seat': seat,
                })

        self._data_table.setRowCount(len(rows_data))
        self._data_table.setColumnCount(len(columns))
        self._data_table.setHorizontalHeaderLabels(columns)

        for row, d in enumerate(rows_data):
            self._data_table.setItem(row, 0, QTableWidgetItem(d['condition']))
            self._data_table.setItem(row, 1, QTableWidgetItem(d['location']))
            self._data_table.setItem(row, 2, QTableWidgetItem(d['channel']))
            self._data_table.setItem(row, 3, QTableWidgetItem(f"{d['rms']:.4f}"))
            self._data_table.setItem(row, 4, QTableWidgetItem(f"{d['vdv']:.2f}"))
            self._data_table.setItem(row, 5, QTableWidgetItem(f"{d['peak']:.4f}"))
            self._data_table.setItem(row, 6, QTableWidgetItem(f"{d['cf']:.2f}"))
            self._data_table.setItem(row, 7, QTableWidgetItem(f"{d['mtvv']:.4f}"))
            seat_str = f"{d['seat']:.0f}%" if d['seat'] < 1e10 else "N/A"
            seat_item = QTableWidgetItem(seat_str)
            if d['seat'] > 200:
                seat_item.setForeground(QBrush(QColor('#dc3545')))
                seat_item.setBackground(QColor('#f8d7da'))
            elif d['seat'] > 100:
                seat_item.setForeground(QBrush(QColor('#e67e22')))
                seat_item.setBackground(QColor('#fff3cd'))
            seat_item.setTextAlignment(Qt.AlignCenter)
            self._data_table.setItem(row, 8, seat_item)

        self._data_table.resizeColumnsToContents()
        self._data_table.resizeRowsToContents()

    # ══════════════════════════════════════════════════════
    # 工具方法
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _clear_layout(layout):
        """清空布局中的所有子控件"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    @staticmethod
    def _init_placeholder_chart(layout, text: str = "等待数据..."):
        """在布局中初始化空占位 matploblib 图表"""
        fig = Figure(figsize=(8, 3.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, text, transform=ax.transAxes,
                ha='center', va='center', fontsize=13,
                color='#adb5bd', style='italic')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        fig.tight_layout()
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

    # ══════════════════════════════════════════════════════
    # 错误处理与控制
    # ══════════════════════════════════════════════════════

    def _on_error(self, error_msg: str):
        """分析出错，弹出错误提示"""
        self._progress_group.setVisible(False)
        self._import_panel._btn_start.setEnabled(True)
        self._import_panel._btn_stop.setEnabled(False)
        self._import_panel.set_running_state(False)
        QMessageBox.critical(self, "分析失败",
            f"分析过程中发生错误:\n\n{error_msg}")

    def _on_cancel(self):
        """取消当前分析"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._progress_label.setText("正在取消...")
            self._import_panel._btn_stop.setEnabled(False)

    def _on_files_loaded(self, file_list: list):
        """导入面板加载文件后的响应"""
        self._import_panel._btn_start.setEnabled(len(file_list) > 0)