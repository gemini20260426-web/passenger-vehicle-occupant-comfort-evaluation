#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAN行为时间轴视图（简化版）— CAN全量解析标签页专用

只保留事件列表展示，用于：
  - 显示EventDataMapper中的所有事件
  - 点击事件可高亮对应时间区间的数据
"""

import logging
import time
from typing import Optional, List

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QTableWidget, QTableWidgetItem,
                               QHeaderView, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont

from core.core.analysis.core_types import RiskLevel
from core.core.analysis.event_distributor import EventDistributor, BehaviorEventView


RISK_COLORS_HEX = {
    'low': "#27ae60",
    'medium': "#f1c40f",
    'high': "#e74c3c",
}

RISK_LABELS_CN = {
    'low': "低",
    'medium': "中",
    'high': "高",
}


class CANBehaviorTimelineView(QWidget):
    """CAN行为时间轴视图（简化版）
    
    功能特点：
    - 只展示事件列表
    - 从EventDistributor获取事件（唯一事件分发中心）
    - 点击事件可发射信号，用于联动数据表格
    - 支持事件导出
    """
    
    event_selected = Signal(int, float, float)  # event_id, start_ts, end_ts

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        self._distributor = EventDistributor.instance()
        self._events: List[BehaviorEventView] = []
        self._last_event_count = 0
        
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_check)
        self._auto_refresh_timer.start(1500)
        
        self._init_ui()
        self._refresh_event_list()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        self.refresh_btn = QPushButton("刷新事件列表")
        self.refresh_btn.setMinimumHeight(28)
        self.refresh_btn.clicked.connect(self._refresh_event_list)
        toolbar.addWidget(self.refresh_btn)
        
        self.clear_btn = QPushButton("清空事件列表")
        self.clear_btn.setMinimumHeight(28)
        self.clear_btn.clicked.connect(self._clear_events)
        toolbar.addWidget(self.clear_btn)
        
        self.export_btn = QPushButton("导出事件")
        self.export_btn.setMinimumHeight(28)
        self.export_btn.clicked.connect(self._export_events)
        toolbar.addWidget(self.export_btn)
        
        toolbar.addStretch()
        
        self.event_count_label = QLabel("事件: 0")
        self.event_count_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 12px; }")
        toolbar.addWidget(self.event_count_label)
        
        layout.addLayout(toolbar)
        
        # 事件列表
        table_card = QGroupBox("事件列表")
        table_card.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 12px; font-family: 'Microsoft YaHei'; "
            "border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 4, 8, 8)
        
        self.event_table = QTableWidget()
        self.event_table.setColumnCount(8)
        self.event_table.setHorizontalHeaderLabels([
            "ID", "时间", "行为类型", "严重程度", "风险等级", "开始时间", "结束时间", "持续时长"
        ])
        self.event_table.horizontalHeader().setStretchLastSection(True)
        for i in range(self.event_table.columnCount()):
            if i in (0, 3, 4, 7):
                self.event_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                self.event_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.event_table.verticalHeader().setDefaultSectionSize(26)
        self.event_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.event_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.event_table.setAlternatingRowColors(True)
        self.event_table.verticalHeader().setVisible(False)
        self.event_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.event_table.itemClicked.connect(self._on_event_clicked)
        table_layout.addWidget(self.event_table)
        
        layout.addWidget(table_card, stretch=1)
        
        # 说明标签
        info_label = QLabel("💡 提示：点击事件可高亮对应时间区间的数据")
        info_label.setStyleSheet("QLabel { color: #95a5a6; font-size: 11px; padding: 4px; }")
        layout.addWidget(info_label)

    def _refresh_event_list(self):
        """刷新事件列表"""
        try:
            self._events = self._distributor.get_behavior_events()
            self._last_event_count = len(self._events)
            self._update_event_table()
            self.event_count_label.setText(f"事件: {len(self._events)}")
            self.logger.debug(f"已刷新事件列表，共 {len(self._events)} 个事件")
        except Exception as e:
            self.logger.error(f"刷新事件列表失败: {e}")

    def _auto_refresh_check(self):
        """自动检测事件变化并刷新"""
        try:
            current_count = self._distributor.get_event_count()
            if current_count != self._last_event_count:
                self._refresh_event_list()
        except Exception:
            pass

    def notify_events_changed(self):
        """外部通知事件已变更，立即刷新"""
        self._refresh_event_list()

    def start_auto_refresh(self):
        """启动自动刷新"""
        if not self._auto_refresh_timer.isActive():
            self._auto_refresh_timer.start(1500)

    def stop_auto_refresh(self):
        """停止自动刷新"""
        self._auto_refresh_timer.stop()

    def _update_event_table(self):
        """更新事件表格"""
        self.event_table.setRowCount(0)
        
        for event in self._events:
            row = self.event_table.rowCount()
            self.event_table.insertRow(row)
            
            self.event_table.setItem(row, 0, QTableWidgetItem(str(event.event_id)))
            
            t = time.strftime('%H:%M:%S', time.localtime(event.end_ts))
            ms = int((event.end_ts - int(event.end_ts)) * 1000)
            self.event_table.setItem(row, 1, QTableWidgetItem(f"{t}.{ms:03d}"))
            
            self.event_table.setItem(row, 2, QTableWidgetItem(event.behavior))
            
            self.event_table.setItem(row, 3, QTableWidgetItem(f"{event.severity:.1f}"))
            
            risk_str = str(event.risk_level).lower() if hasattr(event.risk_level, 'value') else str(event.risk_level).lower()
            risk_item = QTableWidgetItem(RISK_LABELS_CN.get(risk_str, "未知"))
            risk_color = QColor(RISK_COLORS_HEX.get(risk_str, "#95a5a6"))
            risk_item.setForeground(risk_color)
            self.event_table.setItem(row, 4, risk_item)
            
            self.event_table.setItem(row, 5, QTableWidgetItem(f"{event.start_ts:.3f}"))
            
            self.event_table.setItem(row, 6, QTableWidgetItem(f"{event.end_ts:.3f}"))
            
            duration = event.end_ts - event.start_ts
            self.event_table.setItem(row, 7, QTableWidgetItem(f"{duration:.2f}s"))
            
            if risk_str == 'high':
                for col in range(self.event_table.columnCount()):
                    item = self.event_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 235, 238))
            elif risk_str == 'medium':
                for col in range(self.event_table.columnCount()):
                    item = self.event_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 252, 224))

    def _on_event_clicked(self, item):
        """处理事件点击"""
        row = item.row()
        if 0 <= row < len(self._events):
            event = self._events[row]
            self.logger.info(f"事件已选中: ID={event.event_id}, "
                           f"行为={event.behavior}, "
                           f"时间=[{event.start_ts:.3f}, {event.end_ts:.3f}]")
            self.event_selected.emit(event.event_id, event.start_ts, event.end_ts)

    def _clear_events(self):
        """清空事件列表 — 同步清除 EventDistributor 内存事件"""
        try:
            self._events = []
            self._last_event_count = 0
            self.event_table.setRowCount(0)
            self.event_count_label.setText("事件: 0")
            cleared = self._distributor.clear()
            self.logger.info(f"事件列表已清空 (Distributor清除 {cleared} 个事件)")
        except Exception as e:
            self.logger.error(f"清空事件列表失败: {e}")

    def _export_events(self):
        """导出事件（使用增强导出功能）"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QComboBox, QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel
        import csv
        import os
        
        if not self._events:
            QMessageBox.warning(self, "提示", "当前无事件可导出")
            return
        
        # 显示导出选项对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("导出事件选项")
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        # 格式选择
        format_label = QLabel("导出格式：")
        format_combo = QComboBox()
        format_combo.addItems(["完整格式 (CSV)", "简化格式 (CSV)"])
        format_combo.setCurrentIndex(0)
        
        format_layout = QHBoxLayout()
        format_layout.addWidget(format_label)
        format_layout.addWidget(format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        use_full_format = format_combo.currentIndex() == 0
        
        # 选择文件路径
        default_name = "can_events_export_full.csv" if use_full_format else "can_events_export_simple.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出事件数据", default_name, "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            if use_full_format:
                events = self._distributor.get_behavior_events()
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "事件ID", "行为类型", "行为代码", "严重程度", "风险等级",
                        "风险分数", "置信度", "开始时间(s)", "结束时间(s)", "持续时长(s)",
                        "峰值ax", "峰值ay", "峰值jerk", "速度下限", "速度上限"
                    ])
                    for event in events:
                        writer.writerow([
                            event.event_id,
                            event.behavior,
                            event.behavior_type,
                            f"{event.severity:.2f}",
                            event.risk_level,
                            f"{event.risk_score:.2f}",
                            f"{event.confidence:.2f}",
                            f"{event.start_ts:.3f}",
                            f"{event.end_ts:.3f}",
                            f"{event.duration:.3f}",
                            f"{event.peak_ax:.3f}",
                            f"{event.peak_ay:.3f}",
                            f"{event.peak_jerk:.3f}",
                            f"{event.speed_range[0]:.2f}" if event.speed_range else "0.00",
                            f"{event.speed_range[1]:.2f}" if event.speed_range else "0.00",
                        ])
                count = len(events)
                msg = f"已导出 {count} 个事件到:\n{file_path}\n\n包含完整字段：行为类型代码、风险分数、峰值加速度、峰值角速度、速度范围、置信度等"
            else:
                # 简化格式（保持原逻辑）
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "事件ID", "行为类型", "严重程度", "风险等级", 
                        "开始时间(s)", "结束时间(s)", "持续时长(s)",
                        "创建时间"
                    ])
                    for event in self._events:
                        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.end_ts))
                        ms = int((event.end_ts - int(event.end_ts)) * 1000)
                        duration = event.end_ts - event.start_ts
                        risk_str = str(event.risk_level).lower() if hasattr(event.risk_level, 'value') else str(event.risk_level).lower()
                        writer.writerow([
                            event.event_id,
                            event.behavior,
                            f"{event.severity:.1f}",
                            RISK_LABELS_CN.get(risk_str, "未知"),
                            f"{event.start_ts:.3f}",
                            f"{event.end_ts:.3f}",
                            f"{duration:.2f}",
                            f"{t}.{ms:03d}"
                        ])
                count = len(self._events)
                msg = f"已导出 {count} 个事件到:\n{file_path}"
            
            QMessageBox.information(self, "导出成功", msg)
        except Exception as e:
            self.logger.error(f"导出事件失败: {e}")
            QMessageBox.critical(self, "导出失败", str(e))

    def add_event(self, event):
        """添加单个事件（从EventDistributor刷新）"""
        self._refresh_event_list()

    def reset(self):
        """重置"""
        self._clear_events()
