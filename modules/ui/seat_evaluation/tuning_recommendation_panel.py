#!/usr/bin/env python3
"""
调校建议面板 — 显示座椅调校优化建议
嵌入全量统计标签页
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import logging
logger = logging.getLogger(__name__)


class TuningRecommendationPanel(QFrame):
    """调校建议面板 — 显示 SeatTuningAdvisor 的结果

    用法:
        panel = TuningRecommendationPanel(parent)
        panel.update_from_report(report_dict)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("TuningRecommendationPanel { background: #FAFBFC; border: 1px solid #E0E3E8; border-radius: 8px; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # 标题
        title = QLabel("调校优化建议")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # 建议列表容器
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        main_layout.addWidget(scroll)

        self.clear()

    def update_from_report(self, report: dict):
        """从报告字典更新面板"""
        try:
            recs = report.get('tuning_recommendations', [])
            if not recs:
                self.clear()
                return

            # 清除旧内容
            self._clear_content()

            for i, rec in enumerate(recs):
                card = self._create_recommendation_card(rec, i + 1)
                self._content_layout.insertWidget(self._content_layout.count() - 1, card)

        except Exception as e:
            logger.warning(f"调校建议面板更新失败: {e}")
            self.clear()

    def _create_recommendation_card(self, rec: dict, index: int) -> QFrame:
        """创建单条建议卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E8ECF0;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        # 标题行: 编号 + 部件 + 参数
        header_layout = QHBoxLayout()
        idx_label = QLabel(f"#{index}")
        idx_label.setStyleSheet("color: #3498DB; font-weight: bold;")
        header_layout.addWidget(idx_label)

        comp_label = QLabel(f"{rec.get('component', '—')} · {rec.get('parameter', '—')}")
        comp_font = QFont()
        comp_font.setBold(True)
        comp_label.setFont(comp_font)
        header_layout.addWidget(comp_label)
        header_layout.addStretch()

        # 方向标签
        direction = rec.get('direction', '—')
        dir_label = QLabel(direction)
        dir_color = '#27AE60' if '增加' in direction or '提高' in direction else '#E74C3C' if '减少' in direction or '降低' in direction else '#7F8C8D'
        dir_label.setStyleSheet(f"color: {dir_color}; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(dir_label)
        layout.addLayout(header_layout)

        # 原因
        reason = QLabel(f"原因: {rec.get('reason', '—')}")
        reason.setWordWrap(True)
        reason.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        layout.addWidget(reason)

        # 预期改善
        expected = rec.get('expected', rec.get('expected_improvement', '—'))
        exp_label = QLabel(f"预期改善: {expected}")
        exp_label.setStyleSheet("color: #27AE60; font-size: 11px;")
        layout.addWidget(exp_label)

        # 置信度进度条
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("置信度:"))
        conf_bar = QProgressBar()
        conf_bar.setMaximum(100)
        conf_bar.setValue(int(rec.get('confidence', 0) * 100))
        conf_bar.setTextVisible(True)
        conf_bar.setFormat(f"{rec.get('confidence', 0):.0%}")
        conf_bar.setMaximumHeight(16)
        conf_layout.addWidget(conf_bar)
        layout.addLayout(conf_layout)

        return card

    def _clear_content(self):
        """清除所有建议卡片"""
        while self._content_layout.count() > 1:  # 保留底部的 stretch
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def clear(self):
        """清空为默认状态"""
        self._clear_content()
        placeholder = QLabel("暂无调校建议")
        placeholder.setStyleSheet("color: #BDC3C7; font-style: italic; padding: 12px;")
        self._content_layout.insertWidget(0, placeholder)