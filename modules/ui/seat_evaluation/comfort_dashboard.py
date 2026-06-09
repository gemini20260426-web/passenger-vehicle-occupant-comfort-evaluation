#!/usr/bin/env python3
"""
舒适度综合仪表盘 — 嵌入全量统计标签页顶部
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel

import logging
logger = logging.getLogger(__name__)


class ComfortDashboard(QFrame):
    """舒适度综合仪表盘 — 嵌入全量统计标签页顶部"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("comfortDashboard")
        self.setStyleSheet("""
            QFrame#comfortDashboard {
                background: white;
                border-radius: 8px;
                padding: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 总分数码
        self.score_label = QLabel("—")
        self.score_label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #2F5496;"
        )
        layout.addWidget(self.score_label)

        # 等级徽章
        self.grade_label = QLabel("N/A")
        self.grade_label.setStyleSheet("""
            font-size: 20px; font-weight: bold; padding: 8px 16px;
            border-radius: 20px; background: #ddd;
        """)
        layout.addWidget(self.grade_label)

        # 分项得分
        details = QVBoxLayout()
        self.vib_label = QLabel("振动: —")
        self.shock_label = QLabel("冲击: —")
        self.trans_label = QLabel("衰减: —")
        self.post_label = QLabel("姿态: —")
        for lbl in [self.vib_label, self.shock_label, self.trans_label, self.post_label]:
            lbl.setStyleSheet("font-size: 12px; color: #666;")
            details.addWidget(lbl)
        layout.addLayout(details)

        # 脊柱健康 & 平顺性
        health_layout = QVBoxLayout()
        self.spine_label = QLabel("脊柱: —")
        self.ride_label = QLabel("平顺: —")
        for lbl in [self.spine_label, self.ride_label]:
            lbl.setStyleSheet("font-size: 12px; color: #666;")
            health_layout.addWidget(lbl)
        layout.addLayout(health_layout)

        # 主观描述
        self.narrative = QLabel("")
        self.narrative.setWordWrap(True)
        self.narrative.setStyleSheet(
            "font-size: 11px; color: #333; font-style: italic;"
        )
        layout.addWidget(self.narrative, stretch=1)

    def update_from_report(self, report: dict):
        """从结构化报告更新仪表盘"""
        ci = report.get('comfort_index') or {}
        sub = report.get('subjective') or {}

        score = ci.get('overall_score', 0)
        self.score_label.setText(f"{score:.0f}")

        # 颜色分级
        if score >= 85:
            color = '#27ae60'
        elif score >= 70:
            color = '#2ecc71'
        elif score >= 55:
            color = '#f39c12'
        elif score >= 40:
            color = '#e67e22'
        else:
            color = '#e74c3c'

        self.score_label.setStyleSheet(
            f"font-size: 48px; font-weight: bold; color: {color};"
        )
        self.grade_label.setText(f"{ci.get('grade', '?')}级")
        self.grade_label.setStyleSheet(f"""
            font-size: 20px; font-weight: bold; padding: 8px 16px;
            border-radius: 20px; background: {color}; color: white;
        """)

        self.vib_label.setText(f"振动: {ci.get('vibration_score', 0):.0f}")
        self.shock_label.setText(f"冲击: {ci.get('shock_score', 0):.0f}")
        self.trans_label.setText(f"衰减: {ci.get('transfer_score', 0):.0f}")
        self.post_label.setText(f"姿态: {ci.get('posture_score', 0):.0f}")
        self.narrative.setText(sub.get('narrative', ''))

        # 脊柱健康 & 平顺性
        sh = report.get('spine_health') or {}
        rq = report.get('ride_quality') or {}
        if sh:
            self.spine_label.setText(f"脊柱: {sh.get('risk_label', '—')}")
        else:
            self.spine_label.setText("脊柱: —")
        if rq:
            self.ride_label.setText(f"平顺: {rq.get('comfort_label', '—')}")
        else:
            self.ride_label.setText("平顺: —")

    def clear(self):
        """清空仪表盘"""
        self.score_label.setText("—")
        self.score_label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #2F5496;"
        )
        self.grade_label.setText("N/A")
        self.grade_label.setStyleSheet("""
            font-size: 20px; font-weight: bold; padding: 8px 16px;
            border-radius: 20px; background: #ddd;
        """)
        self.vib_label.setText("振动: —")
        self.shock_label.setText("冲击: —")
        self.trans_label.setText("衰减: —")
        self.post_label.setText("姿态: —")
        self.narrative.setText("")