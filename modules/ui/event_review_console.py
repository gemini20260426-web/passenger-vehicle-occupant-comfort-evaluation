#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复核控制台 — 替代弃用的对比分析模块
═══════════════════════════════════════════════════════════
对接: EventConfidenceRefiner + analysis_pipeline
框架: PySide6 QWidget (嵌入主窗口标签页)

布局:
  ┌─────────────┬──────────────────┬──────────────────────┐
  │ 事件列表(Table) │ 三路投票详情(Widget) │ Verdict (确认/驳回)    │
  ├─────────────┴──────────────────┴──────────────────────┤
  │  统计摘要 + 置信度分布                                │
  └──────────────────────────────────────────────────────┘
"""
import sys, os, json, logging, time
from typing import Dict, List, Optional, Any
from datetime import datetime

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
    QTableView, QPushButton, QLabel, QComboBox, QSlider,
    QTextEdit, QGroupBox, QFormLayout, QSpinBox, QStatusBar,
    QHeaderView, QMessageBox, QFileDialog, QAbstractItemView,
    QProgressBar, QTableWidget, QTableWidgetItem, QGridLayout,
    QScrollArea, QDoubleSpinBox,
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, Signal, Slot,
    QTimer, QThread, QObject, QSize,
)
from PySide6.QtGui import QColor, QFont, QBrush, QPainter, QPen

from core.core.analysis.event_confidence_refiner import (
    EventConfidenceRefiner, DataPipelineAdapter, ReviewConsoleData,
    L3Event, L4Label, TriStageResult, RefinedEvent,
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════
#  数据模型
# ════════════════════════════════════════════════════════

_COLUMN_HEADERS = [
    "#", "事件类型", "置信度", "HMM置信", "开始(s)", "结束(s)",
    "速度(km/h)", "L3分", "L4分", "TS分", "物理", "判定", "原因"
]
_COLUMN_FIELDS = [
    'idx', 'event_type', 'confidence', 'hmm_confidence',
    't_start', 't_end', 'speed', 'l3_score', 'l4_score',
    'ts_score', 'physics_pass', 'verdict', 'review_reason'
]


class EventTableModel(QAbstractTableModel):
    """事件列表表格模型"""

    def __init__(self, console_data: ReviewConsoleData = None):
        super().__init__()
        self._data: ReviewConsoleData = console_data
        self._filtered: List[RefinedEvent] = []
        self._apply_filter("all")

    def rowCount(self, parent=QModelIndex()):
        return len(self._filtered)

    def columnCount(self, parent=QModelIndex()):
        return len(_COLUMN_HEADERS)

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _COLUMN_HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        ev = self._filtered[row]
        field = _COLUMN_FIELDS[col]

        if role == Qt.DisplayRole:
            if field == 'idx':
                return str(row + 1)
            val = getattr(ev, field, '')
            if field in ('confidence', 'hmm_confidence'):
                return f"{val:.3f}" if isinstance(val, float) else str(val)
            if field in ('t_start', 't_end'):
                return f"{val:.1f}s" if isinstance(val, float) else str(val)
            if field == 'physics_pass':
                return "[OK]" if val else "[X]"
            if field == 'review_reason':
                return str(val)[:60]
            return str(val)

        if role == Qt.ForegroundRole:
            if ev.verdict == 'rejected':
                return QBrush(QColor('#dc3545'))
            if ev.requires_review:
                return QBrush(QColor('#fd7e14'))
            if ev.confidence >= 0.95:
                return QBrush(QColor('#28a745'))
            return None

        if role == Qt.BackgroundRole and ev.requires_review:
            return QBrush(QColor('#fff3cd'))
        return None

    def update_data(self, console_data: ReviewConsoleData):
        self.beginResetModel()
        self._data = console_data
        self._apply_filter("all")
        self.endResetModel()

    def _apply_filter(self, filter_mode: str):
        if self._data is None:
            self._filtered = []
            return
        if filter_mode == "needs_review":
            self._filtered = self._data.filter_needs_review()
        elif filter_mode == "confirmed":
            self._filtered = [e for e in self._data.events if e.verdict == 'confirmed']
        elif filter_mode == "rejected":
            self._filtered = [e for e in self._data.events if e.verdict == 'rejected']
        else:
            self._filtered = list(self._data.events)

    def set_filter(self, filter_mode: str):
        self.beginResetModel()
        self._apply_filter(filter_mode)
        self.endResetModel()

    def get_event(self, row_idx: int) -> Optional[RefinedEvent]:
        return self._filtered[row_idx] if row_idx < len(self._filtered) else None

    def get_real_index(self, row_idx: int) -> int:
        """映射回原列表index"""
        if row_idx < len(self._filtered) and self._data:
            ev = self._filtered[row_idx]
            for i, e in enumerate(self._data.events):
                if e is ev:
                    return i
        return row_idx


# ════════════════════════════════════════════════════════
#  EventReviewPanel — 嵌入主窗口的事件复核面板
# ════════════════════════════════════════════════════════

class EventReviewPanel(QWidget):
    """事件复核控制台 — 替代 ComparisonTab

    可嵌入到 real_time_monitoring_tab.py 的右侧面板中。
    直接对接 analysis_pipeline 的输出结果。
    """

    stats_updated = Signal(dict)          # 统计数据更新
    event_confirmed = Signal(int, str)    # 事件确认 (idx, event_type)
    event_rejected = Signal(int, str)     # 事件驳回 (idx, reason)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.console_data: Optional[ReviewConsoleData] = None
        self.adapter = DataPipelineAdapter(fs=100.0)
        self._last_pipeline_results = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── 顶部控制栏 ──
        self._create_control_bar(main_layout)

        # ── 主分割器 ──
        splitter = QSplitter(Qt.Horizontal)

        # 左: 事件列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.table_view = QTableView()
        self.table_model = EventTableModel()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setWordWrap(False)
        self.table_view.setTextElideMode(Qt.ElideRight)

        # ── 列宽策略: 按内容设置合理宽度，避免挤压 ──
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)  # 最后一列"原因"自动填充剩余空间
        header.setMinimumSectionSize(40)

        # 按列索引预设宽度 (字符数 × 字体宽度估算)
        _col_widths = {
            0: 32,   # #
            1: 100,  # 事件类型
            2: 60,   # 置信度
            3: 60,   # HMM置信
            4: 60,   # 开始(s)
            5: 60,   # 结束(s)
            6: 72,   # 速度(km/h)
            7: 48,   # L3分
            8: 48,   # L4分
            9: 48,   # TS分
            10: 40,  # 物理
            11: 50,  # 判定
        }
        for col, width in _col_widths.items():
            header.resizeSection(col, width)

        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        left_layout.addWidget(self.table_view)
        splitter.addWidget(left_panel)

        # 中: 三路投票详情 + 统计
        mid_panel = QWidget()
        mid_layout = QVBoxLayout(mid_panel)
        mid_layout.setContentsMargins(0, 0, 0, 0)

        # 详情
        self.grp_detail = QGroupBox("三路投票详情")
        detail_form = QFormLayout()
        self.lbl_l3 = QLabel("--"); detail_form.addRow("L3(分割):", self.lbl_l3)
        self.lbl_l4 = QLabel("--"); detail_form.addRow("L4(分类):", self.lbl_l4)
        self.lbl_ts = QLabel("--"); detail_form.addRow("TS(检测):", self.lbl_ts)
        self.lbl_fused = QLabel("--"); detail_form.addRow("融合置信:", self.lbl_fused)
        self.lbl_hmm = QLabel("--"); detail_form.addRow("HMM平滑:", self.lbl_hmm)
        self.lbl_physics = QLabel("--"); detail_form.addRow("物理:", self.lbl_physics)
        self.grp_detail.setLayout(detail_form)
        mid_layout.addWidget(self.grp_detail)

        # 统计摘要
        self.grp_stats = QGroupBox("统计摘要")
        stats_layout = QFormLayout()
        self.lbl_total = QLabel("--"); stats_layout.addRow("总事件:", self.lbl_total)
        self.lbl_confirmed = QLabel("--"); stats_layout.addRow("已确认:", self.lbl_confirmed)
        self.lbl_review = QLabel("--"); stats_layout.addRow("待复核:", self.lbl_review)
        self.lbl_mean = QLabel("--"); stats_layout.addRow("平均置信:", self.lbl_mean)
        self.lbl_violations = QLabel("--"); stats_layout.addRow("物理违规:", self.lbl_violations)
        self.grp_stats.setLayout(stats_layout)
        mid_layout.addWidget(self.grp_stats)
        mid_layout.addStretch()
        splitter.addWidget(mid_panel)

        # 右: Verdict + 筛选
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 判定
        self.grp_verdict = QGroupBox("判定操作")
        verdict_layout = QVBoxLayout()
        self.btn_confirm = QPushButton("确认事件")
        self.btn_confirm.setMinimumHeight(32)
        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_reject = QPushButton("驳回事件")
        self.btn_reject.setMinimumHeight(32)
        self.btn_reject.clicked.connect(self._on_reject)
        self.txt_reason = QTextEdit()
        self.txt_reason.setPlaceholderText("驳回/复核原因...")
        self.txt_reason.setMaximumHeight(60)
        self.lbl_status = QLabel("选中一个事件查看详情")
        self.lbl_status.setWordWrap(True)
        verdict_layout.addWidget(self.btn_confirm)
        verdict_layout.addWidget(self.btn_reject)
        verdict_layout.addWidget(QLabel("原因:"))
        verdict_layout.addWidget(self.txt_reason)
        verdict_layout.addWidget(self.lbl_status)
        self.grp_verdict.setLayout(verdict_layout)
        right_layout.addWidget(self.grp_verdict)

        # 筛选
        self.grp_filter = QGroupBox("筛选")
        filter_layout = QVBoxLayout()
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("阈值:"))
        self.sld_threshold = QSlider(Qt.Horizontal)
        self.sld_threshold.setRange(75, 98)
        self.sld_threshold.setValue(85)
        self.sld_threshold.valueChanged.connect(self._on_threshold_changed)
        threshold_row.addWidget(self.sld_threshold)
        self.lbl_threshold_val = QLabel("85%")
        threshold_row.addWidget(self.lbl_threshold_val)
        filter_layout.addLayout(threshold_row)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["全部", "需复核", "已确认", "已拒绝"])
        self.cmb_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.cmb_filter)
        self.grp_filter.setLayout(filter_layout)
        right_layout.addWidget(self.grp_filter)
        right_layout.addStretch()
        splitter.addWidget(right_panel)

        splitter.setSizes([500, 300, 300])
        main_layout.addWidget(splitter)

    def _create_control_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName("reviewControlBar")
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(42)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 12, 0)
        bar_layout.setSpacing(10)

        self.lbl_status_bar = QLabel("事件复核控制台 — 就绪")
        self.lbl_status_bar.setStyleSheet("QLabel { font-size: 13px; font-weight: bold; }")
        bar_layout.addWidget(self.lbl_status_bar)

        bar_layout.addStretch()

        self.btn_run = QPushButton("执行复核")
        self.btn_run.setMinimumHeight(28)
        self.btn_run.clicked.connect(self._on_run)
        bar_layout.addWidget(self.btn_run)

        self.btn_load = QPushButton("加载CSV")
        self.btn_load.setMinimumHeight(28)
        self.btn_load.clicked.connect(self._on_load_csv)
        bar_layout.addWidget(self.btn_load)

        parent_layout.addWidget(bar)

    # ════════════════════════════════════════════════════════
    #  槽函数
    # ════════════════════════════════════════════════════════

    @Slot()
    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择IMU数据CSV", "", "CSV (*.csv);;All (*)"
        )
        if path:
            self.csv_path = path
            self.lbl_status_bar.setText(
                f"已加载: {os.path.basename(path)}"
            )

    @Slot()
    def _on_run(self):
        self.lbl_status_bar.setText("复核中...")
        self.btn_run.setEnabled(False)

        try:
            threshold = self.sld_threshold.value() / 100.0
            self.adapter.refiner.threshold = threshold

            # 如果有FTE实例则使用，否则使用管线结果
            if hasattr(self, 'fte') and self.fte is not None:
                refined = self.adapter.run(
                    self.fte,
                    getattr(self, 'csv_path', None)
                )
            elif self._last_pipeline_results is not None:
                refined = self.adapter.run_from_analysis_results(
                    self._last_pipeline_results.get('base_result'),
                    self._last_pipeline_results.get('advanced_result'),
                    self._last_pipeline_results.get('behavior_events'),
                )
            else:
                QMessageBox.warning(self, "无数据", "请先加载CSV文件或等待分析结果")
                self.btn_run.setEnabled(True)
                return

            self.console_data = ReviewConsoleData(refined)
            self.table_model.update_data(self.console_data)
            self._update_stats()

            confirmed = sum(1 for e in refined if e.verdict == 'confirmed')
            self.lbl_status_bar.setText(
                f"复核完成: {len(refined)}事件, {confirmed}确认, "
                f"阈值={threshold:.0%}"
            )
        except Exception as e:
            logger.error(f"复核失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"复核执行失败:\n{e}")
        finally:
            self.btn_run.setEnabled(True)

    @Slot(str)
    def _on_filter_changed(self, text: str):
        filter_map = {
            "全部": "all", "需复核": "needs_review",
            "已确认": "confirmed", "已拒绝": "rejected"
        }
        self.table_model.set_filter(filter_map.get(text, "all"))

    @Slot(int)
    def _on_threshold_changed(self, value):
        self.lbl_threshold_val.setText(f"{value}%")

    @Slot()
    def _on_selection_changed(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            self._clear_detail()
            return
        ev = self.table_model.get_event(indexes[0].row())
        if ev is None:
            self._clear_detail()
            return
        self._update_detail(ev, indexes[0].row())

    @Slot()
    def _on_confirm(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        real_idx = self.table_model.get_real_index(indexes[0].row())
        self.console_data.confirm_event(real_idx)
        self.table_model.update_data(self.console_data)
        self._update_stats()
        self.lbl_status_bar.setText(f"事件 #{real_idx} 已确认")
        self.event_confirmed.emit(
            real_idx, self.console_data.events[real_idx].event_type
        )

    @Slot()
    def _on_reject(self):
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        real_idx = self.table_model.get_real_index(indexes[0].row())
        reason = self.txt_reason.toPlainText().strip() or "人工驳回"
        self.console_data.reject_event(real_idx, reason)
        self.table_model.update_data(self.console_data)
        self._update_stats()
        self.lbl_status_bar.setText(f"事件 #{real_idx} 已驳回")
        self.event_rejected.emit(real_idx, reason)

    # ════════════════════════════════════════════════════════
    #  外部接口: 接收分析管线结果
    # ════════════════════════════════════════════════════════

    def feed_pipeline_result(self, base_result: dict, advanced_result: dict,
                             behavior_events: dict):
        """接收分析管线结果 (由 analysis_pipeline 或 DataBridge 调用)"""
        self._last_pipeline_results = {
            'base_result': base_result,
            'advanced_result': advanced_result,
            'behavior_events': behavior_events,
        }
        # 自动运行复核
        self._on_run()

    def set_fte(self, fte):
        """设置 FullTimeseriesEvaluator 实例"""
        self.fte = fte

    def set_review_data(self, refined_events: list):
        """直接设置复核数据 — 由外部 (ComparisonTab) 调用，绕过自动执行流程"""
        self.console_data = ReviewConsoleData(refined_events)
        self.table_model.update_data(self.console_data)
        self._update_stats()
        confirmed = sum(1 for e in refined_events if e.verdict == 'confirmed')
        self.lbl_status_bar.setText(
            f"复核完成: {len(refined_events)}事件, {confirmed}确认"
        )
        # 自动选中第一行，触发三路投票详情更新
        if refined_events:
            self.table_view.selectRow(0)

    # ════════════════════════════════════════════════════════
    #  辅助方法
    # ════════════════════════════════════════════════════════

    def _update_detail(self, ev: RefinedEvent, row: int):
        self.lbl_l3.setText(f"L3={ev.l3_score:.3f}")
        self.lbl_l4.setText(f"L4={ev.l4_score:.3f}")
        self.lbl_ts.setText(f"TS={ev.ts_score:.3f}")
        self.lbl_fused.setText(f"{ev.confidence:.3f}")
        self.lbl_hmm.setText(
            f"{ev.hmm_confidence:.3f}" if ev.hmm_confidence > 0 else "--"
        )
        self.lbl_physics.setText(
            "[OK]通过" if ev.physics_pass
            else f"[X] {ev.physics_violation[:50]}"
        )

        status_parts = [f"#{row}: {ev.event_type}"]
        if ev.requires_review:
            status_parts.append("[!]需复核")
        status_parts.append(f"裁决={ev.verdict}")
        self.lbl_status.setText("\n".join(status_parts))

    def _clear_detail(self):
        for lbl in [self.lbl_l3, self.lbl_l4, self.lbl_ts,
                    self.lbl_fused, self.lbl_hmm, self.lbl_physics]:
            lbl.setText("--")
        self.lbl_status.setText("选中一个事件查看详情")

    def _update_stats(self):
        if self.console_data is None:
            return
        s = self.console_data.get_statistics()
        self.lbl_total.setText(str(s['total_events']))
        self.lbl_confirmed.setText(
            f"{s['confirmed']} ({s['confirmation_rate']:.0%})"
        )
        self.lbl_review.setText(str(s['needs_review']))
        self.lbl_mean.setText(f"{s['mean_confidence']:.3f}")
        self.lbl_violations.setText(str(s['physics_violations']))

        self.stats_updated.emit(s)


# ════════════════════════════════════════════════════════
#  独立运行入口
# ════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = EventReviewPanel()
    window.setWindowTitle("驾驶行为事件复核控制台 v1.0")
    window.setMinimumSize(1200, 600)
    window.show()
    sys.exit(app.exec())