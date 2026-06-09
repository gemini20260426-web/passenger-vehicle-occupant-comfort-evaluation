#!/usr/bin/env python3
"""
多工况对比视图 — 显示多工况对比分析结果
嵌入全量统计标签页下方
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import logging
logger = logging.getLogger(__name__)


class ConditionComparisonView(QFrame):
    """多工况对比视图 — 显示 MultiConditionComparator 的结果

    用法:
        view = ConditionComparisonView(parent)
        view.update_from_report(report_dict)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("ConditionComparisonView { background: #FAFBFC; border: 1px solid #E0E3E8; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题
        title = QLabel("多工况对比分析")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # 表格
        self._table = QTableWidget()
        self._table.setMinimumHeight(150)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table)

        # 排名区
        self._ranking_label = QLabel()
        self._ranking_label.setWordWrap(True)
        layout.addWidget(self._ranking_label)

        self.clear()

    def update_from_report(self, report: dict):
        """从报告字典更新视图"""
        try:
            mc = report.get('multi_condition', {})
            if not mc or not mc.get('conditions'):
                self.clear()
                return

            conditions = mc.get('conditions', [])
            rankings = mc.get('rankings', {})
            suggestions = mc.get('suggestions', [])

            # 设置表格
            headers = ['工况', '速度(km/h)', '舒适度', '等级', 'VDV Z', 'S_d']
            self._table.setColumnCount(len(headers))
            self._table.setHorizontalHeaderLabels(headers)
            self._table.setRowCount(len(conditions))

            for i, cond in enumerate(conditions):
                items = [
                    cond.get('name', f'工况{i+1}'),
                    str(cond.get('speed', '—')),
                    f"{cond.get('comfort_score', 0):.1f}",
                    cond.get('comfort_grade', '—'),
                    f"{cond.get('vdv_z', 0):.2f}",
                    f"{cond.get('s_d', 0):.3f}",
                ]
                for j, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                    if j == 2:  # 舒适度列着色
                        score = cond.get('comfort_score', 0)
                        if score >= 85:
                            item.setForeground(QColor('#27AE60'))
                        elif score >= 70:
                            item.setForeground(QColor('#F39C12'))
                        else:
                            item.setForeground(QColor('#E74C3C'))
                    self._table.setItem(i, j, item)

            # 排名文字
            rank_lines = []
            if rankings:
                rank_lines.append("<b>排名:</b>")
                for rank_name, rank_data in rankings.items():
                    rank_lines.append(f"  {rank_name}: {rank_data}")
            if suggestions:
                rank_lines.append("<br><b>建议:</b>")
                for s in suggestions:
                    rank_lines.append(f"  - {s}")
            self._ranking_label.setText("<br>".join(rank_lines) if rank_lines else "—")

        except Exception as e:
            logger.warning(f"多工况对比视图更新失败: {e}")
            self.clear()

    def clear(self):
        """清空为默认状态"""
        self._table.setColumnCount(1)
        self._table.setHorizontalHeaderLabels(['状态'])
        self._table.setRowCount(1)
        self._table.setItem(0, 0, QTableWidgetItem('暂无多工况对比数据'))
        self._ranking_label.setText('')