#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照分析对比视图 Widget (U2: ComparisonView)

左右双栏实时对比 (实验组蓝色 / 对照组红色):
- 指标并列对比表
- 差异热图叠加
- 改善/退化箭头指示
- 统计显著性标注
"""

import logging
from typing import Dict, List, Any, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QLabel, QHeaderView, QGroupBox,
                               QComboBox, QPushButton, QSplitter)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QBrush

logger = logging.getLogger(__name__)


class ComparisonView(QWidget):
    """对照分析对比视图 (U2)

    功能:
    - 实验组 vs 对照组并列显示
    - 差异百分比计算
    - 改善(绿色)/退化(红色)着色
    - 显著性标注
    """

    # 实验组指标 → 对照组指标映射
    METRIC_PAIRS = {
        'RMS_Ax_E': 'RMS_Ax_C', 'RMS_Ay_E': 'RMS_Ay_C', 'RMS_Az_E': 'RMS_Az_C',
        'Peak_Ax_E': 'Peak_Ax_C', 'Peak_Ay_E': 'Peak_Ay_C', 'Peak_Az_E': 'Peak_Az_C',
        'Crest_Ax_E': 'Crest_Ax_C', 'Crest_Ay_E': 'Crest_Ay_C', 'Crest_Az_E': 'Crest_Az_C',
        'VDV_Ax_E': 'VDV_Ax_C', 'VDV_Ay_E': 'VDV_Ay_C', 'VDV_Az_E': 'VDV_Az_C',
        'Skew_Ax_E': 'Skew_Ax_C', 'Skew_Ay_E': 'Skew_Ay_C', 'Skew_Az_E': 'Skew_Az_C',
        'Kurt_Ax_E': 'Kurt_Ax_C', 'Kurt_Ay_E': 'Kurt_Ay_C', 'Kurt_Az_E': 'Kurt_Az_C',
        'MAV_Ax_E': 'MAV_Ax_C', 'MAV_Ay_E': 'MAV_Ay_C', 'MAV_Az_E': 'MAV_Az_C',
        'Impf_Ax_E': 'Impf_Ax_C', 'Impf_Ay_E': 'Impf_Ay_C', 'Impf_Az_E': 'Impf_Az_C',
        'E_total_VDV': 'C_total_VDV',
    }

    # 指标方向 (lower_is_better / higher_is_better)
    METRIC_DIRECTIONS = {
        'RMS_Ax_E': 'lower', 'RMS_Ay_E': 'lower', 'RMS_Az_E': 'lower',
        'Peak_Ax_E': 'lower', 'Peak_Ay_E': 'lower', 'Peak_Az_E': 'lower',
        'Crest_Ax_E': 'lower', 'Crest_Ay_E': 'lower', 'Crest_Az_E': 'lower',
        'VDV_Ax_E': 'lower', 'VDV_Ay_E': 'lower', 'VDV_Az_E': 'lower',
        'Skew_Ax_E': 'lower', 'Skew_Ay_E': 'lower', 'Skew_Az_E': 'lower',
        'Kurt_Ax_E': 'lower', 'Kurt_Ay_E': 'lower', 'Kurt_Az_E': 'lower',
        'MAV_Ax_E': 'lower', 'MAV_Ay_E': 'lower', 'MAV_Az_E': 'lower',
        'Impf_Ax_E': 'lower', 'Impf_Ay_E': 'lower', 'Impf_Az_E': 'lower',
        'E_total_VDV': 'lower',
    }

    # 信号
    comparison_updated = Signal(dict)

    def __init__(self, metric_store=None, baseline_manager=None, parent=None):
        super().__init__(parent)
        self.metric_store = metric_store
        self.baseline_manager = baseline_manager
        self._exp_metrics: Dict[str, float] = {}
        self._ctrl_metrics: Dict[str, float] = {}
        self._init_ui()

        # 订阅MetricStore
        if self.metric_store:
            all_ids = list(self.METRIC_PAIRS.keys()) + list(set(self.METRIC_PAIRS.values()))
            self.metric_store.subscribe('comparison_view', all_ids)
            self.metric_store.metric_updated.connect(self._on_metric_updated)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("对照分析对比")
        title_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        title_label.setStyleSheet("color: #e0e0e0;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 分组选择
        self.group_filter = QComboBox()
        self.group_filter.addItem("全部指标", "all")
        self.group_filter.addItem("头部RMS", "rms")
        self.group_filter.addItem("VDV", "vdv")
        self.group_filter.addItem("峰值/峰值因数", "peak")
        self.group_filter.addItem("统计指标", "stats")
        self.group_filter.currentIndexChanged.connect(self._filter_changed)
        title_layout.addWidget(QLabel("筛选:"))
        title_layout.addWidget(self.group_filter)

        self.refresh_btn = QPushButton("刷新对比")
        self.refresh_btn.clicked.connect(self._refresh_comparison)
        title_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(title_layout)

        # 摘要栏
        summary_layout = QHBoxLayout()
        self.summary_label = QLabel("等待数据...")
        self.summary_label.setStyleSheet("color: #aaa; font-size: 11px;")
        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()
        main_layout.addLayout(summary_layout)

        # 对比表格
        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(7)
        self.comparison_table.setHorizontalHeaderLabels([
            "指标", "实验组", "对照组", "差值", "变化%", "方向", "评估"
        ])
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.comparison_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.comparison_table.setMinimumWidth(0)
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.setStyleSheet("""
            QTableWidget { background: #1a1a2e; color: #e0e0e0; border: 1px solid #333; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section { background: #16213e; color: #aaa; border: 1px solid #333; padding: 4px; }
        """)
        main_layout.addWidget(self.comparison_table)

        # 差异热图区域
        heatmap_group = QGroupBox("差异热图 (改善/退化)")
        heatmap_group.setStyleSheet("""
            QGroupBox { color: #aaa; border: 1px solid #333; border-radius: 4px; 
                       margin-top: 8px; padding-top: 12px; background: #1a1a2e; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        self.heatmap_widget = HeatmapWidget()
        heatmap_layout = QVBoxLayout()
        heatmap_layout.addWidget(self.heatmap_widget)
        heatmap_group.setLayout(heatmap_layout)
        main_layout.addWidget(heatmap_group)

        self.setStyleSheet("background: #16213e;")

    def set_exp_metrics(self, metrics: Dict[str, float]):
        """设置实验组指标"""
        self._exp_metrics.update(metrics)
        self._update_table()

    def set_ctrl_metrics(self, metrics: Dict[str, float]):
        """设置对照组指标"""
        self._ctrl_metrics.update(metrics)
        self._update_table()

    def _on_metric_updated(self, metric_id: str, data: dict):
        """MetricStore回调"""
        value = data.get('value', 0.0)
        if metric_id in self.METRIC_PAIRS:
            self._exp_metrics[metric_id] = value
        elif metric_id in self.METRIC_PAIRS.values():
            self._ctrl_metrics[metric_id] = value
        self._update_table()

    def _update_table(self):
        """更新对比表格"""
        pairs = self._get_filtered_pairs()
        self.comparison_table.setRowCount(0)

        improved_count = 0
        degraded_count = 0
        stable_count = 0

        heatmap_data = {}

        for i, (exp_id, ctrl_id) in enumerate(pairs):
            exp_val = self._exp_metrics.get(exp_id)
            ctrl_val = self._ctrl_metrics.get(ctrl_id)

            if exp_val is None or ctrl_val is None:
                continue

            self.comparison_table.insertRow(i)

            # 指标名称
            name = exp_id.replace('_E', '').replace('_', ' ')
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.comparison_table.setItem(i, 0, name_item)

            # 实验组值
            exp_item = QTableWidgetItem(f"{exp_val:.3f}")
            exp_item.setTextAlignment(Qt.AlignCenter)
            exp_item.setFlags(exp_item.flags() & ~Qt.ItemIsEditable)
            exp_item.setForeground(QColor('#2196F3'))
            self.comparison_table.setItem(i, 1, exp_item)

            # 对照组值
            ctrl_item = QTableWidgetItem(f"{ctrl_val:.3f}")
            ctrl_item.setTextAlignment(Qt.AlignCenter)
            ctrl_item.setFlags(ctrl_item.flags() & ~Qt.ItemIsEditable)
            ctrl_item.setForeground(QColor('#F44336'))
            self.comparison_table.setItem(i, 2, ctrl_item)

            # 差值
            diff = exp_val - ctrl_val
            diff_item = QTableWidgetItem(f"{diff:+.3f}")
            diff_item.setTextAlignment(Qt.AlignCenter)
            diff_item.setFlags(diff_item.flags() & ~Qt.ItemIsEditable)
            self.comparison_table.setItem(i, 3, diff_item)

            # 变化百分比
            if abs(ctrl_val) > 1e-6:
                change_pct = (exp_val - ctrl_val) / abs(ctrl_val) * 100
            else:
                change_pct = 0.0

            pct_item = QTableWidgetItem(f"{change_pct:+.1f}%")
            pct_item.setTextAlignment(Qt.AlignCenter)
            pct_item.setFlags(pct_item.flags() & ~Qt.ItemIsEditable)

            direction = self.METRIC_DIRECTIONS.get(exp_id, 'lower')
            if direction == 'lower':
                if change_pct < -5:
                    pct_item.setBackground(QColor('#1B5E20'))
                    pct_item.setForeground(QColor('#4CAF50'))
                    direction_label = '↓ 改善'
                    improved_count += 1
                elif change_pct > 5:
                    pct_item.setBackground(QColor('#B71C1C'))
                    pct_item.setForeground(QColor('#EF5350'))
                    direction_label = '↑ 退化'
                    degraded_count += 1
                else:
                    direction_label = '→ 持平'
                    stable_count += 1
            else:
                if change_pct > 5:
                    pct_item.setBackground(QColor('#1B5E20'))
                    direction_label = '↑ 改善'
                    improved_count += 1
                elif change_pct < -5:
                    pct_item.setBackground(QColor('#B71C1C'))
                    direction_label = '↓ 退化'
                    degraded_count += 1
                else:
                    direction_label = '→ 持平'
                    stable_count += 1

            self.comparison_table.setItem(i, 4, pct_item)

            # 方向
            dir_item = QTableWidgetItem(direction_label)
            dir_item.setTextAlignment(Qt.AlignCenter)
            dir_item.setFlags(dir_item.flags() & ~Qt.ItemIsEditable)
            self.comparison_table.setItem(i, 5, dir_item)

            # 评估
            if abs(change_pct) > 20:
                assessment = '显著'
                assess_color = QColor('#FF5722') if '退化' in direction_label else QColor('#4CAF50')
            elif abs(change_pct) > 10:
                assessment = '明显'
                assess_color = QColor('#FF9800')
            else:
                assessment = '正常'
                assess_color = QColor('#9E9E9E')

            assess_item = QTableWidgetItem(assessment)
            assess_item.setTextAlignment(Qt.AlignCenter)
            assess_item.setFlags(assess_item.flags() & ~Qt.ItemIsEditable)
            assess_item.setForeground(assess_color)
            self.comparison_table.setItem(i, 6, assess_item)

            heatmap_data[name] = change_pct

        # 更新摘要
        total = improved_count + degraded_count + stable_count
        self.summary_label.setText(
            f"共 {total} 项指标 | 改善: {improved_count} | 退化: {degraded_count} | 持平: {stable_count}"
        )

        # 更新热图
        self.heatmap_widget.set_data(heatmap_data)

    def _get_filtered_pairs(self) -> List[tuple]:
        """获取筛选后的指标对"""
        filter_type = self.group_filter.currentData()
        pairs = list(self.METRIC_PAIRS.items())

        if filter_type == 'rms':
            pairs = [(k, v) for k, v in pairs if 'RMS' in k]
        elif filter_type == 'vdv':
            pairs = [(k, v) for k, v in pairs if 'VDV' in k]
        elif filter_type == 'peak':
            pairs = [(k, v) for k, v in pairs if 'Peak' in k or 'Crest' in k]
        elif filter_type == 'stats':
            pairs = [(k, v) for k, v in pairs if any(s in k for s in ['Skew', 'Kurt', 'MAV', 'Impf'])]

        return pairs

    def _filter_changed(self):
        self._update_table()

    def _refresh_comparison(self):
        self._update_table()


class HeatmapWidget(QWidget):
    """差异热图组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: Dict[str, float] = {}
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)

    def set_data(self, data: Dict[str, float]):
        self._data = data
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        n = len(self._data)
        if n == 0:
            return

        margin = 5
        cell_w = (w - 2 * margin) / n
        cell_h = h - 2 * margin

        max_abs = max(abs(v) for v in self._data.values()) or 1

        for i, (name, pct) in enumerate(self._data.items()):
            x = margin + i * cell_w
            rect = QRectF(x, margin, cell_w - 2, cell_h)

            # 颜色: 绿=改善, 红=退化
            ratio = pct / max_abs if max_abs > 0 else 0
            if pct < 0:
                # 红色系 (退化)
                intensity = min(255, int(128 + abs(ratio) * 127))
                color = QColor(intensity, 30, 30)
            elif pct > 0:
                # 绿色系 (改善)
                intensity = min(255, int(128 + abs(ratio) * 127))
                color = QColor(30, intensity, 30)
            else:
                color = QColor(60, 60, 60)

            painter.fillRect(rect, QBrush(color))
            painter.setPen(QColor('#333'))
            painter.drawRect(rect)

            # 标签
            if cell_w > 30:
                font = QFont('Segoe UI', 7)
                painter.setFont(font)
                painter.setPen(QColor('#e0e0e0'))
                short_name = name.replace(' ', '\n')[:8]
                painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, short_name)