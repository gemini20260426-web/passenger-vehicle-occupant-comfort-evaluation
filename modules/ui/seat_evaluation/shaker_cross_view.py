#!/usr/bin/env python3
"""多工况对比视图"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QTextEdit, QSplitter, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import logging
logger = logging.getLogger(__name__)


class ShakerCrossView(QWidget):
    """多工况对比视图 — 显示 CrossConditionReport 的 SEAT 对比分析结果

    用法:
        view = ShakerCrossView(parent)
        view.update_from_report(cross_condition_report)
    """

    # 预期显示的 SEAT 通道列表
    SEAT_CHANNELS = ['r_point_x', 'r_point_y', 'r_point_z', 't8_x', 't8_y', 't8_z']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    # ── UI 初始化 ─────────────────────────────────────────
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("多工况对比分析")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # 主体: 左右分栏
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ── 左侧: SEAT 对比表格 ──
        self._table = QTableWidget()
        self._table.setMinimumWidth(420)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        splitter.addWidget(self._table)

        # ── 右侧: 分析建议文本 ──
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setMinimumWidth(260)
        splitter.addWidget(self._text_edit)

        # 初始比例
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self._clear()

    # ── 公开方法 ──────────────────────────────────────────
    def update_from_report(self, report):
        """从 CrossConditionReport 填充表格与分析文本

        Args:
            report: CrossConditionReport (来自 shaker_cross_comparator)
        """
        try:
            if not report or not report.conditions:
                self._clear()
                return

            conditions = report.conditions
            seat_matrix = report.seat_matrix  # {condition: {channel: value}}
            stability = report.stability or {}  # {channel: CV}
            recommendations = report.recommendations or []
            best = report.best_condition
            worst = report.worst_condition

            # 收集所有出现在矩阵中的通道
            all_channels = set()
            for ch_map in seat_matrix.values():
                all_channels.update(ch_map.keys())

            # 按预定义顺序排列，多出的附在末尾
            channels = [ch for ch in self.SEAT_CHANNELS if ch in all_channels]
            extra = sorted(all_channels - set(channels))
            channels.extend(extra)

            if not channels:
                self._clear()
                return

            # ── 构建表格 ──
            col_headers = list(conditions) + ["均值", "CV%"]
            self._table.setColumnCount(len(col_headers))
            self._table.setHorizontalHeaderLabels(col_headers)
            self._table.setRowCount(len(channels))

            for row_idx, ch in enumerate(channels):
                # 各工况值
                col_values = []
                for col_idx, cond_name in enumerate(conditions):
                    val = seat_matrix.get(cond_name, {}).get(ch, 0)
                    col_values.append(val)
                    text = self._fmt_seat(val)
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                    self._set_seat_color(item, val)
                    self._table.setItem(row_idx, col_idx, item)

                # 均值列
                mean_col = len(conditions)
                finite = [v for v in col_values if v > 0 and v < 1e10]
                mean_val = sum(finite) / len(finite) if finite else 0
                mean_item = QTableWidgetItem(self._fmt_seat(mean_val))
                mean_item.setTextAlignment(Qt.AlignCenter)
                self._set_seat_color(mean_item, mean_val)
                self._table.setItem(row_idx, mean_col, mean_item)

                # CV% 列
                cv_col = len(conditions) + 1
                cv_val = stability.get(ch, 0)
                # stability 存的是小数 (0.15 = 15%), 转为百分比显示
                cv_text = f"{cv_val * 100:.1f}%" if cv_val >= 0 else "—"
                cv_item = QTableWidgetItem(cv_text)
                cv_item.setTextAlignment(Qt.AlignCenter)
                # CV 着色: < 15% 绿, >= 15% 黄, >= 30% 红
                if cv_val < 0.15:
                    cv_item.setForeground(QColor('#27AE60'))
                elif cv_val < 0.30:
                    cv_item.setForeground(QColor('#F39C12'))
                else:
                    cv_item.setForeground(QColor('#E74C3C'))
                self._table.setItem(row_idx, cv_col, cv_item)

            # 行表头用第一列显示通道名
            self._table.setVerticalHeaderLabels(channels)

            # ── 构建右侧分析文本 ──
            lines = []

            if best or worst:
                lines.append("<b>综合评估</b>")
                if best:
                    lines.append(f"最优工况: {best}")
                if worst:
                    lines.append(f"最差工况: {worst}")
                lines.append("")

            # 稳定性摘要
            stable = [k for k, v in stability.items() if v < 0.15]
            unstable = [k for k, v in stability.items() if v >= 0.15]
            if stable or unstable:
                lines.append("<b>稳定度摘要 (CV)</b>")
                if stable:
                    lines.append(f"稳定通道 ({len(stable)}): {', '.join(stable)}")
                if unstable:
                    lines.append(
                        f"<span style='color:#E74C3C;'>不稳定通道 ({len(unstable)}): "
                        f"{', '.join(unstable)}</span>"
                    )
                lines.append("")

            # 排名
            ranking = getattr(report, 'ranking', {})
            if ranking:
                lines.append("<b>各通道工况排序 (SEAT 由低到高)</b>")
                for ch, ranked_list in ranking.items():
                    rank_str = "  >  ".join(ranked_list)
                    lines.append(f"{ch}: {rank_str}")
                lines.append("")

            # 建议
            if recommendations:
                lines.append("<b>工程建议</b>")
                for i, rec in enumerate(recommendations, 1):
                    lines.append(f"{i}. {rec}")
                lines.append("")

            self._text_edit.setHtml("<br>".join(lines))

        except Exception as e:
            logger.warning(f"ShakerCrossView 更新失败: {e}", exc_info=True)
            self._clear()

    # ── 内部辅助 ──────────────────────────────────────────
    def _clear(self):
        """重置为空白状态"""
        self._table.setColumnCount(1)
        self._table.setHorizontalHeaderLabels(["状态"])
        self._table.setRowCount(1)
        self._table.setItem(0, 0, QTableWidgetItem("暂无多工况对比数据"))
        self._text_edit.clear()

    @staticmethod
    def _fmt_seat(value: float) -> str:
        """格式化 SEAT 值"""
        if value <= 0 or value >= 1e10:
            return "—"
        return f"{value:.1f}%"

    @staticmethod
    def _set_seat_color(item: QTableWidgetItem, value: float):
        """根据 SEAT 值设置颜色"""
        if value <= 0 or value >= 1e10:
            return
        if value <= 100:
            item.setForeground(QColor('#27AE60'))
        elif value <= 150:
            item.setForeground(QColor('#F39C12'))
        else:
            item.setForeground(QColor('#E74C3C'))