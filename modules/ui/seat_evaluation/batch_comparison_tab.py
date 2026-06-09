#!/usr/bin/env python3
"""
批次对比标签页 — 多批次测试结果的横向对比视图
可作为独立标签页或在全量统计标签页中展开
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import json
import logging
logger = logging.getLogger(__name__)


class BatchComparisonTab(QFrame):
    """批次对比标签页

    用法:
        tab = BatchComparisonTab(parent)
        tab.load_batches(list_of_reports)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("BatchComparisonTab { background: #FAFBFC; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题栏
        header_layout = QHBoxLayout()
        title = QLabel("批次对比分析")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._export_btn = QPushButton("导出JSON")
        self._export_btn.clicked.connect(self._export_json)
        self._export_btn.setEnabled(False)
        header_layout.addWidget(self._export_btn)
        layout.addLayout(header_layout)

        # 摘要区
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        self._count_label = self._make_stat_label("批次数量", "0")
        self._best_label = self._make_stat_label("最佳批次", "—")
        self._worst_label = self._make_stat_label("最差批次", "—")
        self._trend_label = self._make_stat_label("趋势", "—")

        summary_layout.addWidget(self._count_label)
        summary_layout.addWidget(self._best_label)
        summary_layout.addWidget(self._worst_label)
        summary_layout.addWidget(self._trend_label)
        layout.addLayout(summary_layout)

        # 排名表
        self._table = QTableWidget()
        self._table.setMinimumHeight(200)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table)

        self.clear()

    def _make_stat_label(self, title: str, value: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet("QFrame { background: white; border: 1px solid #E0E3E8; border-radius: 6px; padding: 8px; }")
        cl = QVBoxLayout(card)
        cl.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        cl.addWidget(t)
        v = QLabel(value)
        v.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        cl.addWidget(v)
        return card

    def load_batches(self, batch_reports: list):
        """加载批次数据"""
        try:
            if not batch_reports:
                self.clear()
                return

            from core.core.seat_evaluation.batch_comparison import BatchComparisonEngine

            engine = BatchComparisonEngine()
            result = engine.compare(batch_reports)

            # 更新摘要
            self._count_label.findChildren(QLabel)[1].setText(str(result.batch_count))
            self._best_label.findChildren(QLabel)[1].setText(f"{result.best_batch} ({result.best_score:.1f})")
            self._worst_label.findChildren(QLabel)[1].setText(f"{result.worst_batch} ({result.worst_score:.1f})")

            trend_map = {'improving': '↑ 改善', 'degrading': '↓ 退化', 'stable': '→ 稳定'}
            trend_text = f"{trend_map.get(result.trend_direction, '—')} ({result.trend_magnitude:+.1f})"
            self._trend_label.findChildren(QLabel)[1].setText(trend_text)

            # 更新表格
            headers = ['排名', '批次名称', '舒适度', '等级', 'VDV Z', 'S_d', 'SEAT Z', '事件数']
            self._table.setColumnCount(len(headers))
            self._table.setHorizontalHeaderLabels(headers)
            self._table.setRowCount(len(result.batches))

            sorted_batches = sorted(result.batches, key=lambda b: b.comfort_score, reverse=True)
            for i, b in enumerate(sorted_batches):
                items = [
                    str(i + 1),
                    b.name,
                    f"{b.comfort_score:.1f}",
                    b.comfort_grade,
                    f"{b.vdv_z:.2f}",
                    f"{b.s_d:.3f}",
                    f"{b.seat_z:.3f}",
                    str(b.event_count),
                ]
                for j, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                    if j == 2:
                        score = b.comfort_score
                        if score >= 85:
                            item.setForeground(QColor('#27AE60'))
                        elif score >= 70:
                            item.setForeground(QColor('#F39C12'))
                        else:
                            item.setForeground(QColor('#E74C3C'))
                    self._table.setItem(i, j, item)

            self._export_btn.setEnabled(True)
            self._last_result = result

        except Exception as e:
            logger.warning(f"批次对比加载失败: {e}")
            self.clear()

    def _export_json(self):
        """导出批次对比结果为 JSON"""
        if not hasattr(self, '_last_result'):
            return

        path, _ = QFileDialog.getSaveFileName(self, "导出批次对比", "batch_comparison.json", "JSON (*.json)")
        if not path:
            return

        try:
            data = {
                'batch_count': self._last_result.batch_count,
                'best_batch': self._last_result.best_batch,
                'worst_batch': self._last_result.worst_batch,
                'comfort_mean': self._last_result.comfort_mean,
                'comfort_std': self._last_result.comfort_std,
                'trend': self._last_result.trend_direction,
                'batches': [
                    {
                        'name': b.name,
                        'comfort_score': b.comfort_score,
                        'vdv_z': b.vdv_z,
                        's_d': b.s_d,
                        'seat_z': b.seat_z,
                    }
                    for b in self._last_result.batches
                ],
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "导出成功", f"已保存到: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def clear(self):
        """清空为默认状态"""
        self._count_label.findChildren(QLabel)[1].setText("0")
        self._best_label.findChildren(QLabel)[1].setText("—")
        self._worst_label.findChildren(QLabel)[1].setText("—")
        self._trend_label.findChildren(QLabel)[1].setText("—")

        self._table.setColumnCount(1)
        self._table.setHorizontalHeaderLabels(['状态'])
        self._table.setRowCount(1)
        self._table.setItem(0, 0, QTableWidgetItem('暂无批次对比数据'))
        self._export_btn.setEnabled(False)