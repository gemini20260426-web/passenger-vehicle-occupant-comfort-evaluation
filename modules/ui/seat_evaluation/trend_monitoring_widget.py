#!/usr/bin/env python3
"""
趋势监测组件 — 显示多次测试的关键指标趋势
嵌入全量统计标签页
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import logging
logger = logging.getLogger(__name__)


class TrendMonitoringWidget(QFrame):
    """趋势监测组件 — 显示 TrendMonitor 的结果

    用法:
        widget = TrendMonitoringWidget(parent)
        widget.update_from_report(report_dict)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("TrendMonitoringWidget { background: #FAFBFC; border: 1px solid #E0E3E8; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题栏
        header_layout = QHBoxLayout()
        title = QLabel("趋势监测")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._add_btn = QPushButton("记录当前点")
        self._add_btn.setStyleSheet("QPushButton { color: #3498DB; font-weight: bold; }")
        self._add_btn.clicked.connect(self._on_add_point)
        header_layout.addWidget(self._add_btn)
        layout.addLayout(header_layout)

        # 趋势摘要
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("color: #7F8C8D; font-size: 12px; padding: 8px; background: white; border-radius: 4px;")
        layout.addWidget(self._summary_label)

        # 告警列表
        self._alert_table = QTableWidget()
        self._alert_table.setMaximumHeight(120)
        self._alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._alert_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._alert_table)

        # 历史点表格
        self._history_table = QTableWidget()
        self._history_table.setMinimumHeight(100)
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._history_table)

        self._current_report = None
        self.clear()

    def update_from_report(self, report: dict):
        """从报告字典更新趋势视图"""
        self._current_report = report
        try:
            ts = report.get('trend_summary', {})
            alerts = report.get('trend_alerts', [])
            history = report.get('trend_history', [])

            # 趋势摘要
            if ts:
                trend = ts.get('direction', 'stable')
                trend_map = {'improving': '↑ 改善中', 'degrading': '↓ 退化中', 'stable': '→ 稳定'}
                lines = [
                    f"趋势: {trend_map.get(trend, '—')}",
                    f"变化幅度: {ts.get('magnitude', 0):+.1f}",
                    f"历史点数: {ts.get('point_count', 0)}",
                    f"最后更新: {ts.get('last_updated', '—')}",
                ]
                self._summary_label.setText(" | ".join(lines))
            else:
                self._summary_label.setText("暂无趋势数据 — 点击「记录当前点」开始追踪")

            # 告警表
            if alerts:
                self._alert_table.setColumnCount(3)
                self._alert_table.setHorizontalHeaderLabels(['类型', '指标', '信息'])
                self._alert_table.setRowCount(len(alerts))
                for i, alert in enumerate(alerts):
                    alert_type = alert.get('type', '—')
                    items = [
                        alert_type,
                        alert.get('metric', '—'),
                        alert.get('message', '—'),
                    ]
                    for j, text in enumerate(items):
                        item = QTableWidgetItem(str(text))
                        item.setTextAlignment(Qt.AlignCenter)
                        if j == 0:
                            colors = {'degradation': '#E74C3C', 'improvement': '#27AE60', 'anomaly': '#F39C12'}
                            item.setForeground(QColor(colors.get(alert_type, '#7F8C8D')))
                        self._alert_table.setItem(i, j, item)
            else:
                self._alert_table.setColumnCount(1)
                self._alert_table.setHorizontalHeaderLabels(['告警'])
                self._alert_table.setRowCount(1)
                self._alert_table.setItem(0, 0, QTableWidgetItem('无告警'))

            # 历史点表
            if history:
                self._history_table.setColumnCount(5)
                self._history_table.setHorizontalHeaderLabels(['时间', '舒适度', 'VDV Z', 'S_d', '标签'])
                self._history_table.setRowCount(len(history))
                for i, pt in enumerate(history):
                    items = [
                        str(pt.get('timestamp', '—'))[:19],
                        f"{pt.get('comfort_index', 0):.1f}",
                        f"{pt.get('vdv_z', 0):.2f}",
                        f"{pt.get('s_d', 0):.3f}",
                        pt.get('label', '—'),
                    ]
                    for j, text in enumerate(items):
                        item = QTableWidgetItem(text)
                        item.setTextAlignment(Qt.AlignCenter)
                        self._history_table.setItem(i, j, item)
            else:
                self._history_table.setColumnCount(1)
                self._history_table.setHorizontalHeaderLabels(['历史记录'])
                self._history_table.setRowCount(1)
                self._history_table.setItem(0, 0, QTableWidgetItem('暂无历史数据'))

        except Exception as e:
            logger.warning(f"趋势监测组件更新失败: {e}")
            self.clear()

    def _on_add_point(self):
        """记录当前点"""
        if not self._current_report:
            return

        try:
            from core.core.seat_evaluation.trend_monitor import TrendMonitor

            monitor = TrendMonitor()
            ci = self._current_report.get('comfort_index', {})
            td = self._current_report.get('time_domain', {})
            sf = self._current_report.get('shock_fatigue', {})

            result = {
                'comfort_index': ci,
                'time_domain': td,
                'shock_fatigue': sf,
            }
            label = f"记录点 @ {self._current_report.get('metadata', {}).get('created_at', '')}"

            alerts = monitor.add_point(result, label)
            summary = monitor.get_summary()

            # 更新报告
            self._current_report['trend_summary'] = summary
            self._current_report['trend_alerts'] = [
                {'type': a.alert_type, 'metric': a.metric, 'message': a.message}
                for a in alerts
            ]
            self._current_report['trend_history'] = [
                {
                    'timestamp': p.timestamp,
                    'comfort_index': p.comfort_index,
                    'vdv_z': p.vdv_z,
                    's_d': p.s_d,
                    'label': p.label,
                }
                for p in monitor.history
            ]

            self.update_from_report(self._current_report)
            logger.info("趋势监测: 已记录当前点")

        except Exception as e:
            logger.warning(f"趋势监测记录失败: {e}")

    def clear(self):
        """清空为默认状态"""
        self._summary_label.setText("暂无趋势数据 — 点击「记录当前点」开始追踪")
        self._alert_table.setColumnCount(1)
        self._alert_table.setHorizontalHeaderLabels(['告警'])
        self._alert_table.setRowCount(1)
        self._alert_table.setItem(0, 0, QTableWidgetItem('无告警'))
        self._history_table.setColumnCount(1)
        self._history_table.setHorizontalHeaderLabels(['历史记录'])
        self._history_table.setRowCount(1)
        self._history_table.setItem(0, 0, QTableWidgetItem('暂无历史数据'))