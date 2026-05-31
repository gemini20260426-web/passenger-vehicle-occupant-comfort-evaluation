#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实例视图面板 — 单事件评测详情
核心设计原则:
  1. 物理量优先 — 展示带单位的原始测量值
  2. 标准锚定 — 每个指标标注 ISO/SAE 国际标准引用及限值
  3. 组内对照 — 实验组与对照组并排展示，差值+改善率一目了然
  4. 降噪聚焦 — 按工程意义维度分组（隔振能力 / 终端安全 / 累积疲劳）
"""

import csv
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea,
    QComboBox, QHeaderView, QFrame, QSizePolicy, QDialog, QTextEdit,
    QTextBrowser, QFileDialog, QMessageBox, QSplitter, QGroupBox,
    QGridLayout, QProgressDialog, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.core.seat_evaluation.metadata_registry import (
    INDICATOR_DEFINITIONS, DIAGNOSIS_THRESHOLDS,
    STANDARD_REFERENCES, COMPARISON_DIMENSIONS, INDICATOR_DETAIL,
)
from core.core.seat_evaluation.imu_location_config import (
    LOCATION_NAMES, LOCATION_IDS, INDICATOR_CATEGORIES,
    IMU_LOCATION_MAPPING,
)

logger = logging.getLogger(__name__)

LC = {
    'bg_primary': '#FFFFFF', 'bg_card': '#FFFFFF', 'bg_input': '#F5F6F8',
    'bg_header': '#EBEDF0', 'bg_hover': '#E8F0FE',
    'accent': '#4A90D9', 'accent_hover': '#357ABD',
    'accent_light': 'rgba(74,144,217,0.10)',
    'text_primary': '#333333', 'text_secondary': '#666666',
    'text_muted': '#999999', 'text_accent': '#4A90D9',
    'border_default': '#D0D0D0', 'border_light': '#E0E0E0',
    'success': '#27AE60', 'warning': '#F39C12', 'danger': '#E74C3C',
    'info': '#4A90D9', 'orange_dark': '#E67E22',
    'improvement_good': '#27AE60',
    'improvement_bad': '#E74C3C',
    'improvement_neutral': '#95A5A6',
    'exp_color': '#4A90D9',
    'ctrl_color': '#E67E22',
}

CARD_STYLE = """
    QFrame#proCard {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 6px;
    }
"""

COMPARISON_CARD_STYLE = """
    QFrame#compCard {
        background-color: #F5F6F8;
        border: 1px solid #E0E0E0;
        border-radius: 6px;
    }
    QFrame#compCard:hover {
        border-color: #D0D0D0;
    }
"""

TABLE_STYLE = """
    QTableWidget {
        background-color: #F5F6F8;
        border: 1px solid #D0D0D0;
        border-radius: 4px;
        gridline-color: #E0E0E0;
        font-size: 11px;
    }
    QTableWidget::item {
        padding: 4px 8px;
        color: #333333;
    }
    QHeaderView::section {
        background-color: #EBEDF0;
        color: #666666;
        border: none;
        border-bottom: 1px solid #D0D0D0;
        padding: 6px 8px;
        font-size: 10px;
        font-weight: 600;
    }
"""

LOCATION_PRIMARY_METRIC = {
    'head': 'HIC15',
    'torso': 'SEAT_XY',
    'seat_r': 'VDV_Z',
    'seat_bottom': 'TR_Z',
    'sternum': 'STFT_FC',
}


class ScoreCard(QFrame):
    """评分卡片（保留供 trip_overview / type_summary 使用）"""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("compCard")
        self.setStyleSheet(COMPARISON_CARD_STYLE)
        self.setFixedSize(120, 90)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 6, 8, 6)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(
            "color: {}; font-size: 9px; font-weight: 500;".format(
                LC['text_secondary']))
        layout.addWidget(self._title_label)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setAlignment(Qt.AlignCenter)
            sub.setStyleSheet(
                "color: {}; font-size: 8px;".format(LC['text_muted']))
            layout.addWidget(sub)

        self._score_label = QLabel("--")
        self._score_label.setAlignment(Qt.AlignCenter)
        self._score_label.setStyleSheet(
            "color: {}; font-size: 22px; font-weight: 700;".format(
                LC['accent']))
        layout.addWidget(self._score_label)

        self._grade_label = QLabel("")
        self._grade_label.setAlignment(Qt.AlignCenter)
        self._grade_label.setStyleSheet("font-size: 10px; font-weight: 600;")
        layout.addWidget(self._grade_label)

    def set_score(
            self, score: Optional[float],
            grade: str = "",
            color: str = ""
    ):
        if not color:
            color = LC['accent']
        if score is not None:
            fmt = f"{score:.0f}" if score >= 10 else f"{score:.1f}"
            self._score_label.setText(fmt)
            self._grade_label.setText(grade)
        else:
            self._score_label.setText("--")
            self._grade_label.setText("")
        self._score_label.setStyleSheet(
            "color: {}; font-size: 22px; font-weight: 700;".format(color)
        )
        self._grade_label.setStyleSheet(
            "color: {}; font-size: 10px; font-weight: 600;".format(color)
        )


class NavigationBar(QFrame):
    prev_requested = Signal()
    next_requested = Signal()
    jump_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("proCard")
        self.setStyleSheet(CARD_STYLE)
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._prev_btn = QPushButton("◀ 上一条")
        self._prev_btn.setFixedSize(68, 24)
        self._style_nav_btn(self._prev_btn)
        self._prev_btn.clicked.connect(self.prev_requested.emit)
        layout.addWidget(self._prev_btn)

        self._event_label = QLabel("未选择事件")
        self._event_label.setAlignment(Qt.AlignCenter)
        self._event_label.setStyleSheet(
            "color: {}; font-size: 11px; font-weight: 600;".format(
                LC['text_primary']))
        layout.addWidget(self._event_label, 1)

        self._next_btn = QPushButton("下一条 ▶")
        self._next_btn.setFixedSize(68, 24)
        self._style_nav_btn(self._next_btn)
        self._next_btn.clicked.connect(self.next_requested.emit)
        layout.addWidget(self._next_btn)

        self._jump_combo = QComboBox()
        self._jump_combo.setFixedWidth(130)
        self._jump_combo.setFixedHeight(24)
        self._jump_combo.currentTextChanged.connect(
            lambda t: self.jump_requested.emit(t) if t else None
        )
        layout.addWidget(self._jump_combo)

    def _style_nav_btn(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {{
                background-color: transparent;
                color: {text_sec};
                border: 1px solid {border_def};
                border-radius: 3px;
                font-size: 10px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {text_acc};
                border-color: {accent};
                background-color: {accent_lt};
            }}
        """.format(
            text_sec=LC['text_secondary'],
            border_def=LC['border_default'],
            text_acc=LC['text_accent'],
            accent=LC['accent'],
            accent_lt=LC['accent_light'],
        ))

    def update_nav(self, event_id: str, event_label: str, all_ids: List[str]):
        self._event_label.setText(event_label)
        self._jump_combo.clear()
        self._jump_combo.addItem("跳转到...")
        for eid in all_ids:
            self._jump_combo.addItem(eid)


def _get_metric_value_from_locations(
        metric_id: str,
        all_metrics: Dict[str, Dict[str, float]]
) -> Optional[float]:
    vals = []
    for loc_metrics in all_metrics.values():
        v = loc_metrics.get(metric_id)
        if v is not None and not (isinstance(v, float) and v == -1.0):
            vals.append(v)
    if not vals:
        return None
    return sum(vals) / len(vals)


def _compute_improvement_pct(
        exp_val: Optional[float],
        ctrl_val: Optional[float]
) -> Optional[float]:
    if exp_val is None or ctrl_val is None or ctrl_val == 0:
        return None
    return ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0


class CoreComparisonTable(QTableWidget):
    """核心指标对照表 — 以表格形式展示5个位置的核心指标对照"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "评测位置", "核心指标", "实验组", "对照组", "改善情况"
        ])
        self.setStyleSheet(TABLE_STYLE)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.verticalHeader().setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(160)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        self.setColumnWidth(0, 100)
        self.setColumnWidth(1, 110)
        self.setColumnWidth(2, 90)
        self.setColumnWidth(3, 90)

    def populate(self, exp_metrics: Dict[str, Dict[str, float]],
                 ctrl_metrics: Dict[str, Dict[str, float]]):
        self.setRowCount(0)
        rows = []
        for loc_id in LOCATION_IDS:
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            primary_metric = LOCATION_PRIMARY_METRIC.get(loc_id, 'SEAT_Z')
            info = INDICATOR_DEFINITIONS.get(primary_metric, {})
            metric_name = info.get('name', primary_metric)
            unit = info.get('unit', '')

            exp_val = None
            for l_metrics in exp_metrics.values():
                v = l_metrics.get(primary_metric)
                if v is not None and not (isinstance(v, float) and v == -1.0):
                    exp_val = v
                    break

            ctrl_val = None
            for l_metrics in ctrl_metrics.values():
                v = l_metrics.get(primary_metric)
                if v is not None and not (isinstance(v, float) and v == -1.0):
                    ctrl_val = v
                    break

            rows.append((loc_name, metric_name, unit, exp_val, ctrl_val))

        self.setRowCount(len(rows))
        for i, (loc_name, metric_name, unit, exp_val, ctrl_val) in enumerate(rows):
            loc_item = QTableWidgetItem(loc_name)
            loc_item.setTextAlignment(Qt.AlignCenter)
            loc_item.setForeground(QColor(LC['text_primary']))
            self.setItem(i, 0, loc_item)

            metric_text = f"{metric_name} ({unit})" if unit else metric_name
            metric_item = QTableWidgetItem(metric_text)
            metric_item.setTextAlignment(Qt.AlignCenter)
            metric_item.setForeground(QColor(LC['text_accent']))
            self.setItem(i, 1, metric_item)

            exp_text = f"{exp_val:.2f}" if exp_val is not None else "--"
            self._set_color_cell(i, 2, exp_text, LC['exp_color'])

            ctrl_text = f"{ctrl_val:.2f}" if ctrl_val is not None else "--"
            self._set_color_cell(i, 3, ctrl_text, LC['ctrl_color'])

            imp_text = self._format_improvement(exp_val, ctrl_val)
            imp_color = self._improvement_color(exp_val, ctrl_val)
            self._set_color_cell(i, 4, imp_text, imp_color)

        for r in range(self.rowCount()):
            self.setRowHeight(r, 30)
        
        self._adjust_table_height()
    
    def _adjust_table_height(self):
        height = self.horizontalHeader().height() + 4
        for r in range(self.rowCount()):
            height += self.rowHeight(r)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def _set_color_cell(self, row: int, col: int, text: str, color: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(QColor(color))
        font = item.font()
        font.setBold(True)
        font.setPointSize(10)
        item.setFont(font)
        self.setItem(row, col, item)

    def _format_improvement(self, exp_val, ctrl_val) -> str:
        if exp_val is None or ctrl_val is None or ctrl_val == 0:
            return "--"
        pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
        if abs(pct) < 3:
            return f"→ 持平 (+{pct:.1f}%)"
        elif pct > 0:
            return f"↓ 改善 (+{pct:.1f}%)"
        else:
            return f"↑ 变差 ({pct:.1f}%)"

    def _improvement_color(self, exp_val, ctrl_val) -> str:
        if exp_val is None or ctrl_val is None or ctrl_val == 0:
            return LC['text_muted']
        pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
        if abs(pct) < 3:
            return LC['improvement_neutral']
        elif pct > 0:
            return LC['improvement_good']
        else:
            return LC['improvement_bad']

    def clear(self):
        self.setRowCount(0)


class RawDataDrillDownDialog(QDialog):
    def __init__(self, metric_id: str, metric_name: str,
                 detail: dict, group_tag: str,
                 data_window: tuple, data_query_fn: Callable = None,
                 parent=None):
        super().__init__(parent)
        self._metric_id = metric_id
        self._metric_name = metric_name
        self._detail = detail
        self._group_tag = group_tag
        self._data_window = data_window
        self._data_query_fn = data_query_fn
        self._raw_data = {}

        self.setWindowTitle(f"下钻原始数据 — {metric_name} ({metric_id})")
        self.setMinimumSize(900, 600)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(
            f"<h3>{self._metric_name} ({self._metric_id})</h3>"
            f"<span style='color:#666;font-size:10px;'>"
            f"事件区间: [{self._data_window[0]:.2f}s, {self._data_window[1]:.2f}s] "
            f"| 分组: {self._group_tag}</span>"
        )
        layout.addWidget(title)

        self._status_label = QLabel(
            "<span style='color:#666;'>点击按钮加载原始数据...</span>"
        )
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("🔍 加载原始数据")
        load_btn.setFixedWidth(140)
        load_btn.setStyleSheet("""
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {accent_hv}; }}
        """.format(accent=LC['accent'], accent_hv=LC['accent_hover']))
        load_btn.clicked.connect(self._load_raw_data)
        btn_row.addWidget(load_btn)

        self._export_btn = QPushButton("📋 导出CSV")
        self._export_btn.setFixedWidth(100)
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet("""
            QPushButton {{
                background-color: {success};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #219A52; }}
            QPushButton:disabled {{
                background-color: #CCC;
            }}
        """.format(success=LC['success']))
        self._export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(self._export_btn)
        btn_row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(60)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        splitter = QSplitter(Qt.Vertical)

        self._summary_table = QTableWidget()
        self._summary_table.setColumnCount(6)
        self._summary_table.setHorizontalHeaderLabels([
            "IMU通道", "位置", "数据点数", "均值(g)", "标准差(g)", "峰值范围(g)"
        ])
        self._summary_table.setStyleSheet(TABLE_STYLE)
        self._summary_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._summary_table.verticalHeader().setVisible(False)
        hdr = self._summary_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        self._summary_table.setColumnWidth(1, 80)
        self._summary_table.setColumnWidth(2, 80)
        self._summary_table.setColumnWidth(3, 80)
        self._summary_table.setColumnWidth(4, 80)
        self._summary_table.setColumnWidth(5, 150)
        splitter.addWidget(self._summary_table)

        raw_data_container = QWidget()
        raw_data_layout = QVBoxLayout(raw_data_container)
        raw_data_layout.setSpacing(4)
        raw_data_layout.setContentsMargins(0, 0, 0, 0)

        channel_row = QHBoxLayout()
        channel_row.addWidget(QLabel("IMU通道:"))
        self._channel_combo = QComboBox()
        self._channel_combo.currentTextChanged.connect(self._on_channel_changed)
        channel_row.addWidget(self._channel_combo)
        channel_row.addStretch()
        self._raw_count_label = QLabel("")
        channel_row.addWidget(self._raw_count_label)
        raw_data_layout.addLayout(channel_row)

        self._raw_data_table = QTableWidget()
        self._raw_data_table.setColumnCount(4)
        self._raw_data_table.setHorizontalHeaderLabels([
            "时间(s)", "Ax(m/s²)", "Ay(m/s²)", "Az(m/s²)"
        ])
        self._raw_data_table.setStyleSheet(TABLE_STYLE)
        self._raw_data_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._raw_data_table.verticalHeader().setVisible(False)
        raw_hdr = self._raw_data_table.horizontalHeader()
        raw_hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        raw_hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        raw_hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        raw_hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        raw_data_layout.addWidget(self._raw_data_table)

        splitter.addWidget(raw_data_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _load_raw_data(self):
        import numpy as np

        if not self._data_query_fn or not self._data_window:
            self._status_label.setText(
                "<span style='color:#E74C3C;'>"
                "无法获取原始数据: 数据源未连接或时间窗口为空</span>"
            )
            return

        self._status_label.setText(
            "<span style='color:#F39C12;'>正在加载原始数据...</span>"
        )
        QApplication.processEvents()

        try:
            raw = self._data_query_fn(self._data_window[0], self._data_window[1])
        except Exception as e:
            self._status_label.setText(
                f"<span style='color:#E74C3C;'>加载失败: {e}</span>"
            )
            return

        if not raw:
            self._status_label.setText(
                "<span style='color:#E74C3C;'>"
                "指定时间窗口内无原始数据记录</span>"
            )
            return

        self._raw_data = raw

        self._summary_table.setRowCount(0)
        row = 0
        for ch_name, samples in sorted(raw.items()):
            if not samples or not isinstance(samples, list):
                continue
            loc_info = ""
            for loc_id, cfg in IMU_LOCATION_MAPPING.items():
                if cfg.experimental_channel == ch_name or cfg.control_channel == ch_name:
                    loc_info = f"{LOCATION_NAMES.get(loc_id, loc_id)}"
                    break

            n = len(samples)
            az_vals = []
            for s in samples:
                if isinstance(s, dict):
                    az_vals.append(s.get('az', 0))
                elif isinstance(s, (int, float)):
                    az_vals.append(s)

            if not az_vals:
                continue

            az_arr = np.array(az_vals, dtype=float)
            mean_v = float(np.mean(az_arr))
            std_v = float(np.std(az_arr))
            peak_range = f"[{float(np.min(az_arr)):.3f}, {float(np.max(az_arr)):.3f}]"

            self._summary_table.insertRow(row)
            self._summary_table.setItem(row, 0, QTableWidgetItem(ch_name))
            loc_item = QTableWidgetItem(loc_info)
            loc_item.setTextAlignment(Qt.AlignCenter)
            self._summary_table.setItem(row, 1, loc_item)
            n_item = QTableWidgetItem(str(n))
            n_item.setTextAlignment(Qt.AlignCenter)
            self._summary_table.setItem(row, 2, n_item)
            m_item = QTableWidgetItem(f"{mean_v:.4f}")
            m_item.setTextAlignment(Qt.AlignCenter)
            self._summary_table.setItem(row, 3, m_item)
            s_item = QTableWidgetItem(f"{std_v:.4f}")
            s_item.setTextAlignment(Qt.AlignCenter)
            self._summary_table.setItem(row, 4, s_item)
            p_item = QTableWidgetItem(peak_range)
            p_item.setTextAlignment(Qt.AlignCenter)
            self._summary_table.setItem(row, 5, p_item)
            row += 1

        self._channel_combo.blockSignals(True)
        self._channel_combo.clear()
        self._channel_data_map = {}
        all_channels = sorted(raw.keys())
        for ch_name in all_channels:
            samples = raw[ch_name]
            if isinstance(samples, list):
                self._channel_data_map[ch_name] = samples
                self._channel_combo.addItem(ch_name)
        self._channel_combo.blockSignals(False)

        if self._channel_combo.count() > 0:
            self._channel_combo.setCurrentIndex(0)
            self._populate_raw_data_table()

        total_pts = sum(len(v) for v in self._channel_data_map.values())
        self._status_label.setText(
            "<span style='color:#27AE60;'>"
            f"✓ 已加载 {len(raw)} 个通道, 共 {total_pts} 个数据点</span>"
        )
        self._export_btn.setEnabled(True)

    def _on_channel_changed(self, channel_name: str):
        self._populate_raw_data_table()

    def _populate_raw_data_table(self):
        channel = self._channel_combo.currentText()
        if not channel or channel not in self._channel_data_map:
            self._raw_data_table.setRowCount(0)
            self._raw_count_label.setText("")
            return

        samples = self._channel_data_map[channel]
        self._raw_data_table.setRowCount(len(samples))
        self._raw_count_label.setText(f"共 {len(samples)} 条记录")

        for row_idx, s in enumerate(samples):
            if isinstance(s, dict):
                ts = s.get('timestamp', s.get('rel_time', ''))
                ax = s.get('ax', '')
                ay = s.get('ay', '')
                az = s.get('az', '')

                ts_item = QTableWidgetItem(f"{float(ts):.6f}" if ts != '' else '')
                ax_item = QTableWidgetItem(f"{float(ax):.6f}" if ax != '' else '')
                ay_item = QTableWidgetItem(f"{float(ay):.6f}" if ay != '' else '')
                az_item = QTableWidgetItem(f"{float(az):.6f}" if az != '' else '')

                ts_item.setTextAlignment(Qt.AlignCenter)
                ax_item.setTextAlignment(Qt.AlignCenter)
                ay_item.setTextAlignment(Qt.AlignCenter)
                az_item.setTextAlignment(Qt.AlignCenter)

                self._raw_data_table.setItem(row_idx, 0, ts_item)
                self._raw_data_table.setItem(row_idx, 1, ax_item)
                self._raw_data_table.setItem(row_idx, 2, ay_item)
                self._raw_data_table.setItem(row_idx, 3, az_item)

    def _export_csv(self):
        if not self._raw_data:
            QMessageBox.warning(self, "无数据", "暂无数据可导出，请先加载原始数据。")
            return

        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
            "data_output", "seat_evaluation_raw"
        )
        os.makedirs(base_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{self._metric_id}_{self._group_tag}_{ts}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出CSV", os.path.join(base_dir, default_name),
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "IMU_channel", "ax(m/s²)", "ay(m/s²)",
                    "az(m/s²)", "gx(rad/s)", "gy(rad/s)", "gz(rad/s)"
                ])
                for ch_name, samples in sorted(self._raw_data.items()):
                    for s in samples:
                        if isinstance(s, dict):
                            writer.writerow([
                                s.get('timestamp', s.get('rel_time', '')),
                                ch_name,
                                s.get('ax', ''),
                                s.get('ay', ''),
                                s.get('az', ''),
                                s.get('gx', ''),
                                s.get('gy', ''),
                                s.get('gz', ''),
                            ])
                        elif isinstance(s, (int, float)):
                            writer.writerow(['', ch_name, '', '', s, '', '', ''])

            QMessageBox.information(
                self, "导出成功",
                f"数据已导出到:\n{file_path}\n\n"
                f"共 {len(self._raw_data)} 个通道的数据。"
            )
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出CSV时出错: {e}")


class IndicatorDetailDialog(QDialog):

    def __init__(self, metric_id: str, metric_name: str, unit: str,
                 exp_metrics: Dict[str, Dict[str, float]],
                 ctrl_metrics: Dict[str, Dict[str, float]],
                 data_window: tuple = None,
                 data_query_fn: Callable = None,
                 parent=None):
        super().__init__(parent)
        self._metric_id = metric_id
        self._metric_name = metric_name
        self._unit = unit
        self._exp_metrics = exp_metrics
        self._ctrl_metrics = ctrl_metrics
        self._data_window = data_window
        self._data_query_fn = data_query_fn
        self._detail = INDICATOR_DETAIL.get(metric_id, {})
        self._cat_id = self._detail.get('category', '')
        self._cat_info = INDICATOR_CATEGORIES.get(self._cat_id, {})
        self._collapsed_sections = {}

        self.setWindowTitle(f"指标详情 — {metric_name} ({metric_id})")
        self.setMinimumSize(750, 500)
        self._init_ui()

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(self._build_section_a())
        layout.addWidget(self._build_section_b())
        layout.addWidget(self._build_section_c())
        layout.addWidget(self._build_section_d())

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_section_a(self) -> QFrame:
        cat_name = self._cat_info.get('name', self._cat_id or '未分类')
        loc_label = self._detail.get('location_dependency_label', '')
        two_desc = self._detail.get('two_point_description', '')
        if two_desc:
            loc_label = f"{loc_label}  |  {two_desc}"

        frame = QFrame()
        frame.setObjectName("proCard")
        frame.setStyleSheet(CARD_STYLE)
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(4)

        title = QLabel(
            f"<span style='color:#888;font-size:9px;'>{cat_name}</span><br>"
            f"<b style='font-size:14px;'>{self._metric_name}</b>"
            f"<span style='color:#666;font-size:11px;'> ({self._metric_id})</span>"
        )
        f_layout.addWidget(title)

        if self._unit:
            unit_lbl = QLabel(
                f"<span style='color:#666;font-size:10px;'>单位: {self._unit}</span>"
            )
            f_layout.addWidget(unit_lbl)

        if loc_label:
            loc_lbl = QLabel(
                f"<span style='color:#4A90D9;font-size:10px;'>{loc_label}</span>"
            )
            loc_lbl.setWordWrap(True)
            f_layout.addWidget(loc_lbl)

        calc_logic = self._detail.get('calculation_logic', '')
        if calc_logic:
            logic_lbl = QLabel(
                f"<span style='color:#666;font-size:10px;'>{calc_logic}</span>"
            )
            logic_lbl.setWordWrap(True)
            f_layout.addWidget(logic_lbl)

        return frame

    def _build_section_b(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("proCard")
        frame.setStyleSheet(CARD_STYLE)
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(6)

        sec_title = QLabel("<b style='font-size:12px;'>采集点信息</b>")
        f_layout.addWidget(sec_title)

        grid = QGridLayout()
        grid.setSpacing(6)

        primary_imu = self._detail.get('primary_imu', '—')
        grid.addWidget(QLabel("<span style='color:#666;font-size:10px;'>主IMU:</span>"), 0, 0)
        grid.addWidget(QLabel(f"<span style='color:#333;font-size:10px;'>{primary_imu}</span>"), 0, 1)

        ref_imu = self._detail.get('reference_imu', '')
        if ref_imu:
            grid.addWidget(QLabel("<span style='color:#666;font-size:10px;'>参考IMU:</span>"), 1, 0)
            grid.addWidget(QLabel(f"<span style='color:#333;font-size:10px;'>{ref_imu}</span>"), 1, 1)
            grid_row = 2
        else:
            grid_row = 1

        data_fields = self._detail.get('data_fields', '—')
        grid.addWidget(QLabel("<span style='color:#666;font-size:10px;'>数据字段:</span>"), grid_row, 0)
        data_lbl = QLabel(f"<span style='color:#333;font-size:10px;background-color:#F0F0F0;padding:2px 6px;border-radius:2px;'>{data_fields}</span>")
        data_lbl.setWordWrap(True)
        grid.addWidget(data_lbl, grid_row, 1)

        req_locs = self._detail.get('required_locations', [])
        if req_locs:
            loc_names = []
            for loc_id in req_locs:
                cfg = IMU_LOCATION_MAPPING.get(loc_id)
                ch = cfg.experimental_channel if cfg else loc_id
                loc_names.append(f"{LOCATION_NAMES.get(loc_id, loc_id)} ({ch})")
            grid.addWidget(QLabel("<span style='color:#666;font-size:10px;'>需要位置:</span>"), grid_row + 1, 0)
            grid.addWidget(QLabel(
                f"<span style='color:#333;font-size:10px;'>{', '.join(loc_names)}</span>"
            ), grid_row + 1, 1)

        f_layout.addLayout(grid)
        return frame

    def _build_section_c(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("proCard")
        frame.setStyleSheet(CARD_STYLE)
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(6)

        sec_title = QLabel("<b style='font-size:12px;'>算子及公式</b>")
        f_layout.addWidget(sec_title)

        for section_key, section_title, content_key in [
            ('operator', '▸ 算子流水线', 'operator_pipeline'),
            ('formula', '▸ 计算公式', 'formula'),
        ]:
            content = self._detail.get(content_key, '')
            if not content:
                continue

            toggle_btn = QPushButton(section_title)
            toggle_btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    background-color: #F5F6F8;
                    border: 1px solid #D0D0D0;
                    border-radius: 3px;
                    padding: 4px 10px;
                    font-size: 10px;
                    color: #333;
                }
                QPushButton:hover { background-color: #E8F0FE; }
            """)
            is_collapsed = self._collapsed_sections.get(section_key, False)
            if is_collapsed:
                toggle_btn.setText(section_title.replace("▸", "▹"))

            detail_view = QTextBrowser()
            detail_view.setStyleSheet(
                "font-family: Consolas, Microsoft YaHei; font-size: 10px;"
                "background-color: #1E1E1E; color: #D4D4D4;"
                "border: 1px solid #333; border-radius: 3px;"
            )
            detail_view.setMinimumHeight(80)
            detail_view.setMaximumHeight(220)
            detail_view.setText(content)
            detail_view.setVisible(not is_collapsed)

            def make_toggle(btn, view, sk):
                def handler(checked=False):
                    view.setVisible(not view.isVisible())
                    self._collapsed_sections[sk] = not view.isVisible()
                    btn.setText(
                        btn.text().replace("▸", "▹")
                        if view.isVisible() else
                        btn.text().replace("▹", "▸")
                    )
                return handler

            toggle_btn.clicked.connect(make_toggle(toggle_btn, detail_view, section_key))

            f_layout.addWidget(toggle_btn)
            f_layout.addWidget(detail_view)

        return frame

    def _build_section_d(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("proCard")
        frame.setStyleSheet(CARD_STYLE)
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(6)

        sec_title = QLabel(
            "<b style='font-size:12px;'>各位置原生数据对照</b>"
            "<span style='color:#666;font-size:9px;'> （仅显示该指标涉及的位置）</span>"
        )
        f_layout.addWidget(sec_title)

        req_locs = self._detail.get('required_locations', LOCATION_IDS[:])
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "评测位置", "实验组", "对照组", "差值", "改善率", "说明"
        ])
        table.setStyleSheet(TABLE_STYLE)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)

        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        table.setColumnWidth(0, 100)
        table.setColumnWidth(1, 85)
        table.setColumnWidth(2, 85)
        table.setColumnWidth(3, 85)
        table.setColumnWidth(4, 85)
        table.setMinimumHeight(60)

        rows_data = []
        for loc_id in req_locs:
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            exp_val = self._exp_metrics.get(loc_id, {}).get(self._metric_id)
            ctrl_val = self._ctrl_metrics.get(loc_id, {}).get(self._metric_id)

            if exp_val is not None and isinstance(exp_val, float) and exp_val == -1.0:
                exp_val = None
            if ctrl_val is not None and isinstance(ctrl_val, float) and ctrl_val == -1.0:
                ctrl_val = None

            if exp_val is None and ctrl_val is None:
                continue

            diff = None
            pct = None
            if exp_val is not None and ctrl_val is not None and ctrl_val != 0:
                diff = exp_val - ctrl_val
                pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0

            note = ""
            diag = DIAGNOSIS_THRESHOLDS.get(self._metric_id, {})
            if exp_val is not None:
                pass_val = diag.get('pass')
                warn_val = diag.get('warn')
                if pass_val is not None and exp_val > pass_val:
                    note = f"⚠ 超过推荐限值 {pass_val}"
                elif warn_val is not None and exp_val > warn_val:
                    note = f"△ 接近限值 {warn_val}"

            rows_data.append((loc_name, exp_val, ctrl_val, diff, pct, note))

        table.setRowCount(len(rows_data))
        for i, (loc_name, exp_val, ctrl_val, diff, pct, note) in enumerate(rows_data):
            loc_item = QTableWidgetItem(loc_name)
            loc_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, loc_item)

            exp_text = f"{exp_val:.3f}" if exp_val is not None else "--"
            exp_item = QTableWidgetItem(exp_text)
            exp_item.setTextAlignment(Qt.AlignCenter)
            exp_item.setForeground(QColor(LC['exp_color']))
            table.setItem(i, 1, exp_item)

            ctrl_text = f"{ctrl_val:.3f}" if ctrl_val is not None else "--"
            ctrl_item = QTableWidgetItem(ctrl_text)
            ctrl_item.setTextAlignment(Qt.AlignCenter)
            ctrl_item.setForeground(QColor(LC['ctrl_color']))
            table.setItem(i, 2, ctrl_item)

            if diff is not None:
                diff_text = f"{diff:+.3f}"
                diff_color = LC['improvement_good'] if diff < 0 else (
                    LC['improvement_bad'] if diff > 0 else LC['text_muted'])
            else:
                diff_text = "--"
                diff_color = LC['text_muted']
            diff_item = QTableWidgetItem(diff_text)
            diff_item.setTextAlignment(Qt.AlignCenter)
            diff_item.setForeground(QColor(diff_color))
            table.setItem(i, 3, diff_item)

            if pct is not None:
                arrow = "↓" if pct > 3 else ("↑" if pct < -3 else "→")
                pct_text = f"{arrow} {pct:+.1f}%"
                pct_color = LC['improvement_good'] if pct > 3 else (
                    LC['improvement_bad'] if pct < -3 else LC['improvement_neutral'])
            else:
                pct_text = "--"
                pct_color = LC['text_muted']
            pct_item = QTableWidgetItem(pct_text)
            pct_item.setTextAlignment(Qt.AlignCenter)
            pct_item.setForeground(QColor(pct_color))
            table.setItem(i, 4, pct_item)

            note_item = QTableWidgetItem(note if note else "--")
            note_item.setForeground(QColor(LC['text_muted']))
            table.setItem(i, 5, note_item)

        if rows_data:
            for r in range(len(rows_data)):
                table.setRowHeight(r, 28)

        f_layout.addWidget(table)

        drill_row = QHBoxLayout()
        drill_btn = QPushButton("🔬 下钻提取原始数据（事件区间全部IMU数据）")
        drill_btn.setStyleSheet("""
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {accent_hv}; }}
        """.format(accent=LC['accent'], accent_hv=LC['accent_hover']))
        drill_btn.clicked.connect(self._open_drill_down)
        drill_row.addWidget(drill_btn)
        drill_row.addStretch()
        f_layout.addLayout(drill_row)

        return frame

    def _open_drill_down(self):
        if not self._data_window or not self._data_query_fn:
            QMessageBox.information(
                self, "暂不可用",
                "下钻功能需要数据源支持。\n\n"
                "请先加载数据文件并完成评测后重试。"
            )
            return

        dialog = RawDataDrillDownDialog(
            self._metric_id, self._metric_name,
            self._detail, '',
            self._data_window, self._data_query_fn,
            self
        )
        dialog.exec()


class DimensionComparisonTable(QTableWidget):
    """关键维度对照表 — 替代旧诊断表 + 三分类表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(10)
        self.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "单位",
            "实验组", "对照组", "差值", "改善率",
            "标准参考", "注释说明", "操作"
        ])
        self.setStyleSheet(TABLE_STYLE)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.verticalHeader().setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(120)

        self._exp_metrics: Dict[str, Dict[str, float]] = {}
        self._ctrl_metrics: Dict[str, Dict[str, float]] = {}
        self._data_window: Optional[tuple] = None
        self._data_query_fn: Optional[Callable] = None

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        hdr.setSectionResizeMode(8, QHeaderView.Stretch)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        hdr.setDefaultSectionSize(70)
        self.setColumnWidth(0, 70)
        self.setColumnWidth(2, 36)
        self.setColumnWidth(3, 72)
        self.setColumnWidth(4, 72)
        self.setColumnWidth(5, 72)
        self.setColumnWidth(6, 72)
        self.setColumnWidth(7, 120)
        self.setColumnWidth(9, 60)

    def populate(self, exp_metrics: Dict[str, Dict[str, float]],
                 ctrl_metrics: Dict[str, Dict[str, float]]):
        self.setRowCount(0)
        self._exp_metrics = exp_metrics
        self._ctrl_metrics = ctrl_metrics

        metric_to_dim = {}
        for dim in COMPARISON_DIMENSIONS:
            for mid in dim['metrics']:
                metric_to_dim[mid] = dim

        all_usable = self._usable_metrics(
            list(INDICATOR_DEFINITIONS.keys()), exp_metrics)

        if not all_usable:
            self.setRowCount(1)
            empty = QTableWidgetItem("无可用对照数据，请确保实验组与对照组均已评测")
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setForeground(QColor(LC['text_muted']))
            self.setSpan(0, 0, 1, 10)
            self.setItem(0, 0, empty)
            return

        self.setRowCount(len(all_usable))
        for current_row, metric_id in enumerate(all_usable):
            info = INDICATOR_DEFINITIONS.get(metric_id, {})
            unit = info.get('unit', '')
            name = info.get('name', metric_id)
            ref = STANDARD_REFERENCES.get(metric_id, {})
            ref_standard = ref.get('standard', '')
            ref_limit = ref.get('limit', '')
            dim = metric_to_dim.get(metric_id)
            dim_color = dim['color'] if dim else LC['text_primary']

            description = (
                info.get('single_point_description', '') or
                info.get('two_point_description', '') or
                info.get('description', '') or ''
            )

            id_item = QTableWidgetItem(metric_id)
            id_item.setForeground(QColor(dim_color))
            id_font = id_item.font()
            id_font.setPointSize(9)
            id_font.setBold(True)
            id_item.setFont(id_font)
            self.setItem(current_row, 0, id_item)
            self.setItem(current_row, 1, QTableWidgetItem(name))
            self.setItem(current_row, 2, QTableWidgetItem(unit))

            exp_val = _get_metric_value_from_locations(
                metric_id, exp_metrics)
            ctrl_val = _get_metric_value_from_locations(
                metric_id, ctrl_metrics)

            exp_text = (
                f"{exp_val:.2f}" if exp_val is not None else "--"
            )
            ctrl_text = (
                f"{ctrl_val:.2f}" if ctrl_val is not None else "--"
            )
            self._set_value_cell(current_row, 3, exp_text, LC['exp_color'])
            self._set_value_cell(
                current_row, 4, ctrl_text,
                LC['ctrl_color'])

            if exp_val is not None and ctrl_val is not None:
                diff = exp_val - ctrl_val
                if diff < 0:
                    diff_color = LC['improvement_good']
                elif diff > 0:
                    diff_color = LC['improvement_bad']
                else:
                    diff_color = LC['text_muted']
                diff_text = f"{diff:+.2f}"
                self._set_value_cell(
                    current_row, 5, diff_text,
                    diff_color, bold=True)

                if ctrl_val != 0:
                    pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
                    if pct > 0:
                        pct_color = LC['improvement_good']
                    elif pct < 0:
                        pct_color = LC['improvement_bad']
                    else:
                        pct_color = LC['improvement_neutral']
                    pct_text = f"{pct:+.1f}%"
                    if pct > 3:
                        arrow = "↓"
                    elif pct < -3:
                        arrow = "↑"
                    else:
                        arrow = "→"
                    self._set_value_cell(
                        current_row, 6,
                        "{} {}".format(arrow, pct_text),
                        pct_color, bold=True
                    )
                else:
                    self._set_value_cell(
                        current_row, 6, "--",
                        LC['text_muted'])
            else:
                self._set_value_cell(
                    current_row, 5, "--",
                    LC['text_muted'])
                self._set_value_cell(
                    current_row, 6, "--",
                    LC['text_muted'])

            ref_text = (
                "{}\n{}".format(ref_standard, ref_limit)
                if ref_standard else "--"
            )
            ref_item = QTableWidgetItem(ref_text)
            ts = LC['text_secondary']
            ref_item.setForeground(QColor(ts))
            ref_font = ref_item.font()
            ref_font.setPointSize(8)
            ref_item.setFont(ref_font)
            self.setItem(current_row, 7, ref_item)

            desc_item = QTableWidgetItem(description if description else "--")
            desc_item.setForeground(QColor(LC['text_muted']))
            desc_font = desc_item.font()
            desc_font.setPointSize(8)
            desc_item.setFont(desc_font)
            self.setItem(current_row, 8, desc_item)

            detail_btn = QPushButton("详情")
            detail_btn.setFixedSize(50, 24)
            detail_btn.setStyleSheet("""
                QPushButton {{
                    background-color: transparent;
                    color: {text_acc};
                    border: 1px solid {border_def};
                    border-radius: 3px;
                    font-size: 10px;
                    padding: 1px 4px;
                }}
                QPushButton:hover {{
                    background-color: {accent_lt};
                    border-color: {accent};
                }}
            """.format(
                text_acc=LC['text_accent'],
                border_def=LC['border_default'],
                accent_lt=LC['accent_light'],
                accent=LC['accent'],
            ))
            mid = metric_id
            detail_btn.clicked.connect(
                lambda checked=False, m_id=mid: self._show_indicator_detail(m_id)
            )
            self.setCellWidget(current_row, 9, detail_btn)

        for r in range(self.rowCount()):
            self.setRowHeight(r, 36)
        
        self._adjust_table_height()

    def _usable_metrics(self, metric_ids: List[str],
                        all_metrics: Dict[str, Dict[str, float]]) -> List[str]:
        return metric_ids
    
    def _adjust_table_height(self):
        height = self.horizontalHeader().height() + 4
        for r in range(self.rowCount()):
            height += self.rowHeight(r)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def _set_value_cell(self, row: int, col: int, text: str,
                        color: str, bold: bool = False):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(QColor(color))
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        self.setItem(row, col, item)

    def _show_indicator_detail(self, metric_id: str):
        info = INDICATOR_DEFINITIONS.get(metric_id, {})
        metric_name = info.get('name', metric_id)
        unit = info.get('unit', '')
        dialog = IndicatorDetailDialog(
            metric_id, metric_name, unit,
            self._exp_metrics, self._ctrl_metrics,
            self._data_window, self._data_query_fn,
            self
        )
        dialog.exec()


class InstanceViewPanel(QWidget):
    event_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_record = None
        self._control_record = None
        self._all_record_ids = []
        self._all_records: Dict[str, Any] = {}
        self._type_labels = {}
        self._data_query_fn: Optional[Callable] = None
        self._init_ui()

    def set_data_query_fn(self, query_fn: Callable):
        self._data_query_fn = query_fn

    def set_all_records(self, records: Dict[str, Any]):
        self._all_records = records

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self._nav_bar = NavigationBar()
        self._nav_bar.prev_requested.connect(self._on_prev)
        self._nav_bar.next_requested.connect(self._on_next)
        self._nav_bar.jump_requested.connect(self._on_jump)
        layout.addWidget(self._nav_bar)

        self._context_card = self._make_card()
        self._context_layout = QVBoxLayout(self._context_card)
        self._context_layout.setContentsMargins(14, 10, 14, 10)
        self._context_layout.setSpacing(4)
        self._context_label = QLabel("选择事件以查看评测详情")
        self._context_label.setStyleSheet(
            "color: {}; font-size: 12px; padding: 20px;".format(
                LC['text_muted']))
        self._context_label.setAlignment(Qt.AlignCenter)
        self._context_layout.addWidget(self._context_label)
        self._context_card.setVisible(True)
        layout.addWidget(self._context_card)

        self._comparison_card = self._make_card()
        comp_layout = QVBoxLayout(self._comparison_card)
        comp_layout.setContentsMargins(12, 8, 12, 8)
        comp_layout.setSpacing(6)

        comp_title = QLabel("核心指标对照")
        comp_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: {};"
            "padding-bottom: 4px; border-bottom: 1px solid {};".format(
                LC['text_primary'], LC['border_light']
            )
        )
        comp_layout.addWidget(comp_title)

        self._core_comparison_table = CoreComparisonTable()
        comp_layout.addWidget(self._core_comparison_table)
        self._comparison_card.setVisible(True)
        layout.addWidget(self._comparison_card)

        self._table_card = self._make_card()
        table_layout = QVBoxLayout(self._table_card)
        table_layout.setContentsMargins(12, 8, 12, 8)
        table_layout.setSpacing(6)

        table_title = QLabel("关键维度对照表")
        table_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: {};"
            "padding-bottom: 4px; border-bottom: 1px solid {};".format(
                LC['text_primary'], LC['border_light']
            )
        )
        table_layout.addWidget(table_title)

        self._comparison_table = DimensionComparisonTable()
        table_layout.addWidget(self._comparison_table)

        self._comparison_conclusion = QLabel("")
        self._comparison_conclusion.setStyleSheet(
            "color: {}; font-size: 11px; padding: 4px 8px;".format(
                LC['text_muted']))
        self._comparison_conclusion.setWordWrap(True)
        table_layout.addWidget(self._comparison_conclusion)

        self._table_card.setVisible(True)
        layout.addWidget(self._table_card)

        self._detail_card = self._make_card()
        detail_layout = QVBoxLayout(self._detail_card)
        detail_layout.setContentsMargins(12, 8, 12, 8)
        detail_layout.setSpacing(6)

        detail_title = QLabel("指标详细信息")
        detail_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: {};"
            "padding-bottom: 4px; border-bottom: 1px solid {};".format(
                LC['text_primary'], LC['border_light']
            )
        )
        detail_layout.addWidget(detail_title)

        detail_grid = QHBoxLayout()
        detail_grid.setSpacing(4)
        for cat_id in ['steady_state', 'dynamic', 'transient']:
            btn = QPushButton(cat_id)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton {{
                    background-color: {bg_in};
                    color: {text_sec};
                    border: 1px solid {border_lt};
                    border-radius: 3px;
                    font-size: 9px;
                    padding: 2px 8px;
                }}
                QPushButton:hover {{
                    color: {text_acc};
                    border-color: {accent};
                }}
            """.format(
                bg_in=LC['bg_input'],
                text_sec=LC['text_secondary'],
                border_lt=LC['border_light'],
                text_acc=LC['text_accent'],
                accent=LC['accent'],
            ))
            btn.clicked.connect(
                lambda checked=False, c=cat_id: self._show_category_detail(c)
            )
            detail_grid.addWidget(btn)
        detail_grid.addStretch()
        detail_layout.addLayout(detail_grid)

        self._detail_card.setVisible(True)
        layout.addWidget(self._detail_card)

        self._instance_table_card = self._make_card()
        it_layout = QVBoxLayout(self._instance_table_card)
        it_layout.setContentsMargins(12, 8, 12, 8)
        it_layout.setSpacing(6)

        it_title = QLabel("同类型各实例对比表")
        it_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: {};"
            "padding-bottom: 4px; border-bottom: 1px solid {};".format(
                LC['text_primary'], LC['border_light']
            )
        )
        it_layout.addWidget(it_title)

        self._instance_compare_table = QTableWidget()
        self._instance_compare_table.setColumnCount(5)
        self._instance_compare_table.setHorizontalHeaderLabels([
            "实例", "时间范围", "总体评分", "风险", "最弱位置"
        ])
        self._instance_compare_table.setStyleSheet(TABLE_STYLE)
        self._instance_compare_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._instance_compare_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._instance_compare_table.verticalHeader().setVisible(False)
        self._instance_compare_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._instance_compare_table.setMaximumHeight(220)

        ihdr = self._instance_compare_table.horizontalHeader()
        ihdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ihdr.setSectionResizeMode(1, QHeaderView.Stretch)
        ihdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        ihdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        ihdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self._instance_compare_table.cellClicked.connect(self._on_instance_table_clicked)
        it_layout.addWidget(self._instance_compare_table)
        self._instance_table_card.setVisible(False)
        layout.addWidget(self._instance_table_card)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        return card

    def set_type_labels(self, labels: Dict[str, str]):
        self._type_labels = labels

    def show_record(self, record, all_record_ids: Optional[List[str]] = None,
                    control_record=None):
        self._current_record = record
        self._control_record = control_record
        if all_record_ids:
            self._all_record_ids = all_record_ids

        self._update_context()
        self._update_comparison_cards()
        self._update_comparison_table()
        self._update_instance_compare_table()

    def _update_context(self):
        r = self._current_record
        if not r:
            self._context_label.setText("选择事件以查看评测详情")
            self._context_card.setVisible(True)
            self._comparison_card.setVisible(False)
            self._table_card.setVisible(False)
            self._detail_card.setVisible(False)
            return

        type_cn = r.event_type_cn or r.event_type
        status_text = {
            'pending': '待评测', 'evaluating': '评测中',
            'evaluated': '已评测', 'stale': '可能过期', 'failed': '失败',
        }.get(r.status, r.status)

        active_groups = getattr(r, 'active_groups', [])
        if active_groups:
            parts = []
            for g in active_groups:
                if g == 'experimental':
                    parts.append('<span style="color:{};">🔬 实验组</span>'.format(LC['exp_color']))
                elif g == 'control':
                    parts.append('<span style="color:{};">📊 对照组</span>'.format(LC['ctrl_color']))
                else:
                    parts.append('<span>{}</span>'.format(g))
            group_label = ' | '.join(parts)
        else:
            tag = getattr(r, 'group_tag', '')
            group_label = {
                'experimental': '🔬 实验组', 'control': '📊 对照组'
            }.get(tag, tag or '—')

        has_ctrl = r.has_ctrl_result
        ctrl_label = ""
        if has_ctrl:
            ctrl_label = " | 对照可用: ✓"
        elif 'control' in active_groups and not has_ctrl:
            ctrl_label = " | 对照: 未评测"

        if r.data_window_range:
            imu_window_text = "{:.1f}s → {:.1f}s".format(
                r.data_window_range[0], r.data_window_range[1]
            )
        else:
            imu_window_text = "—"

        context_html = """
        <style>
            .label {{ color: {text_sec}; font-size: 10px; }}
            .value {{ color: {text_pri}; font-size: 10px; font-weight: 600; }}
        </style>
        <table>
        <tr>
            <td class='label'>事件编号:</td>
            <td class='value'>{eid}</td>
            <td width='30'></td>
            <td class='label'>评测分组:</td>
            <td class='value'>{gl}</td>
        </tr>
        <tr>
            <td class='label'>事件类型:</td>
            <td class='value'>{type_cn}</td>
            <td></td>
            <td class='label'>评测状态:</td>
            <td class='value' style='color:{sc};'>{si} {st}{cl}</td>
        </tr>
        <tr>
            <td class='label'>时间窗口:</td>
            <td class='value'>{ts:.1f}s -> {te:.1f}s ({dur:.1f}s)</td>
            <td></td>
            <td class='label'>置信度:</td><td class='value'>{conf:.0%}</td>
        </tr>
        <tr>
            <td class='label'>匹配规则:</td><td class='value'>{rule}</td>
            <td></td>
            <td class='label'>IMU窗口:</td><td class='value'>{imu_win}</td>
        </tr>
        </table>
        """.format(
            text_sec=LC['text_secondary'],
            text_pri=LC['text_primary'],
            eid=r.event_id,
            gl=group_label,
            type_cn=type_cn,
            sc=r.status_color,
            si=r.status_icon,
            st=status_text,
            cl=ctrl_label,
            ts=r.start_ts,
            te=r.end_ts,
            dur=r.duration,
            conf=r.confidence,
            rule=r.rule_applied or '自动匹配',
            imu_win=imu_window_text,
        )
        self._context_label.setText(context_html)
        self._context_card.setVisible(True)

        cur_idx = 0
        for i, eid in enumerate(self._all_record_ids):
            if eid == r.event_id:
                cur_idx = i
                break
        total = len(self._all_record_ids)
        self._nav_bar.update_nav(
            r.event_id,
            "{} ({}/{})".format(type_cn, cur_idx + 1, total),
            self._all_record_ids
        )

    def _update_comparison_cards(self):
        r = self._current_record

        if not r:
            self._core_comparison_table.clear()
            return

        self._comparison_card.setVisible(True)

        exp_metrics = r.location_metrics or {}
        ctrl_metrics = r.location_metrics_ctrl or {}

        self._core_comparison_table.populate(exp_metrics, ctrl_metrics)

    def _update_comparison_table(self):
        r = self._current_record

        if not r:
            self._comparison_table.setRowCount(0)
            return

        self._table_card.setVisible(True)
        self._detail_card.setVisible(True)

        exp_metrics = r.location_metrics or {}
        ctrl_metrics = r.location_metrics_ctrl or {}

        self._comparison_table._data_window = r.data_window_range
        self._comparison_table._data_query_fn = self._data_query_fn
        self._comparison_table.populate(exp_metrics, ctrl_metrics)

        conclusion = self._build_conclusion(exp_metrics, ctrl_metrics)
        self._comparison_conclusion.setText(conclusion)

    def _build_conclusion(self, exp_metrics: Dict[str, Dict[str, float]],
                          ctrl_metrics: Dict[str, Dict[str, float]]) -> str:
        if not ctrl_metrics:
            return (
                "<span style='color:#F39C12;font-size:11px;'>"
                "⚠️ 无对照组数据 — 对照组记录未评测或不存在。"
                "请确保实验组与对照组均已运行评测。</span>"
            )

        improvements = []
        degradations = []
        warnings = []

        for dim in COMPARISON_DIMENSIONS:
            for mid in dim['metrics']:
                exp_val = _get_metric_value_from_locations(mid, exp_metrics)
                ctrl_val = _get_metric_value_from_locations(mid, ctrl_metrics)
                if exp_val is None or ctrl_val is None or ctrl_val == 0:
                    continue

                pct = ((ctrl_val - exp_val) / abs(ctrl_val)) * 100.0
                def_info = INDICATOR_DEFINITIONS.get(mid, {})
                metric_name = def_info.get('name', mid)

                if pct > 10:
                    improvements.append(
                        "{}({:+.0f}%)".format(metric_name, pct))
                elif pct < -10:
                    degradations.append(
                        "{}({:+.0f}%)".format(metric_name, pct))

                td = DIAGNOSIS_THRESHOLDS.get(mid, {})
                pass_val = td.get('pass')
                if pass_val is not None and exp_val > pass_val:
                    warnings.append(
                        "{}超出限值({:.2f}>{})".format(
                            metric_name, exp_val, pass_val)
                    )

        parts = []
        if improvements:
            parts.append(
                "<span style='color:{};'>"
                "✅ 实验组在 {} 项指标上优于对照组: "
                "{}</span>".format(
                    LC['improvement_good'],
                    len(improvements),
                    ', '.join(improvements[:8])
                )
            )

        if degradations:
            parts.append(
                "<span style='color:{};'>"
                "⚠️ 实验组在 {} 项指标上劣于对照组: "
                "{}</span>".format(
                    LC['improvement_bad'],
                    len(degradations),
                    ', '.join(degradations[:8])
                )
            )

        if warnings:
            parts.append(
                "<span style='color:{};'>"
                "🔔 {} 项指标超出推荐限值: "
                "{}</span>".format(
                    LC['warning'],
                    len(warnings),
                    ', '.join(warnings[:5])
                )
            )

        if not parts:
            parts.append(
                "<span style='color:#27AE60;'>"
                "✅ 实验组与对照组各项指标均无显著差异，整体表现一致</span>"
            )

        return "<br>".join(parts)

    def _update_instance_compare_table(self):
        r = self._current_record
        if not r:
            self._instance_table_card.setVisible(False)
            return

        etype = r.event_type or getattr(r, 'event_type_cn', None)
        same_type_records = [
            rec for rec in self._all_records.values()
            if getattr(rec, 'event_type', None) == etype
        ]
        if not same_type_records:
            self._instance_table_card.setVisible(False)
            return

        loc_names = {lid: LOCATION_NAMES.get(lid, lid) for lid in LOCATION_IDS}

        self._instance_compare_table.setRowCount(len(same_type_records))
        for i, rec in enumerate(same_type_records):
            idx_item = QTableWidgetItem(rec.event_id[:30] if rec.event_id else "--")
            idx_item.setToolTip(getattr(rec, 'event_id', ''))
            self._instance_compare_table.setItem(i, 0, idx_item)

            ts_start = getattr(rec, 'start_ts', 0)
            ts_end = getattr(rec, 'end_ts', 0)
            dur = ts_end - ts_start if ts_start is not None and ts_end is not None else 0
            time_item = QTableWidgetItem(f"{ts_start:.1f}s → {ts_end:.1f}s ({dur:.1f}s)" if ts_start is not None else "--")
            self._instance_compare_table.setItem(i, 1, time_item)

            if getattr(rec, 'is_evaluated', False):
                score_val = getattr(rec, 'overall_score', 0) or 0
                grade = getattr(rec, 'score_grade', '')
                score_item = QTableWidgetItem(f"{score_val:.1f} {grade}")
                score_item.setForeground(QColor(getattr(rec, 'grade_color', LC['text_muted'])))
                self._instance_compare_table.setItem(i, 2, score_item)

                risk = getattr(rec, 'risk_level', '--')
                risk_item = QTableWidgetItem(risk)
                risk_color = {'低': LC['success'], '中': LC['warning'], '高': LC['danger']}.get(
                    risk, LC['text_muted']
                )
                risk_item.setForeground(QColor(risk_color))
                self._instance_compare_table.setItem(i, 3, risk_item)

                weak = getattr(rec, 'weakest_location', None)
                weak_text = loc_names.get(weak, weak) if weak else "--"
                self._instance_compare_table.setItem(i, 4, QTableWidgetItem(weak_text))
            else:
                self._instance_compare_table.setItem(i, 2, QTableWidgetItem("--"))
                self._instance_compare_table.setItem(i, 3, QTableWidgetItem("--"))
                self._instance_compare_table.setItem(i, 4, QTableWidgetItem("--"))

        self._instance_table_card.setVisible(True)

    def _on_instance_table_clicked(self, row: int, col: int):
        eid_item = self._instance_compare_table.item(row, 0)
        if eid_item:
            self.event_selected.emit(eid_item.text())

    def _show_category_detail(self, cat_id: str):
        dialog = QDialog(self)
        dialog.setWindowTitle("指标详览 — {}".format(cat_id))
        dialog.setFixedSize(480, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            "font-family: Microsoft YaHei; font-size: 11px;"
        )

        from core.core.seat_evaluation.imu_location_config import \
            INDICATOR_CATEGORIES as CATS
        cat_info = CATS.get(cat_id)
        if not cat_info:
            text_edit.setHtml("<p>无此分类信息</p>")
        else:
            lines = ["<h3>{}</h3>".format(cat_info.get('name', cat_id))]
            for ind_id in cat_info.get('indicators', []):
                info = INDICATOR_DEFINITIONS.get(ind_id, {})
                ref = STANDARD_REFERENCES.get(ind_id, {})
                lines.append(
                    "<p><b>{}</b> — {} ({})<br>"
                    "<span style='color:#666;font-size:10px;'>"
                    "标准: {} | 限值: {}"
                    "</span></p>".format(
                        ind_id,
                        info.get('name', ''),
                        info.get('unit', '—'),
                        ref.get('standard', '—'),
                        ref.get('limit', '—'),
                    )
                )
            text_edit.setHtml("<br>".join(lines))

        layout.addWidget(text_edit)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def _on_prev(self):
        if not self._current_record or not self._all_record_ids:
            return
        cur_id = self._current_record.event_id
        try:
            idx = self._all_record_ids.index(cur_id)
            if idx > 0:
                self.event_selected.emit(self._all_record_ids[idx - 1])
        except ValueError:
            pass

    def _on_next(self):
        if not self._current_record or not self._all_record_ids:
            return
        cur_id = self._current_record.event_id
        try:
            idx = self._all_record_ids.index(cur_id)
            if idx < len(self._all_record_ids) - 1:
                self.event_selected.emit(self._all_record_ids[idx + 1])
        except ValueError:
            pass

    def _on_jump(self, event_id: str):
        if event_id and event_id != "跳转到...":
            self.event_selected.emit(event_id)
