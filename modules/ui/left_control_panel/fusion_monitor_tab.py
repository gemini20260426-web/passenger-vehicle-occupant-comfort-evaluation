#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据融合监控标签页
显示数据融合的实时信息
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import logging


class FusionMonitorTab(QWidget):
    """数据融合监控标签页"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.init_ui()
        self.logger.info("数据融合监控标签页已初始化")
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        
        # 性能指标区
        metrics_group = QGroupBox("数据融合性能指标")
        metrics_layout = QGridLayout()
        
        self.throughput_label = QLabel("数据吞吐量: 0 条/秒")
        self.latency_label = QLabel("平均延迟: 0 ms")
        self.quality_label = QLabel("融合质量: 0%")
        self.consistency_label = QLabel("数据一致性: 0%")
        
        self.throughput_label.setFont(QFont("Microsoft YaHei", 10))
        self.latency_label.setFont(QFont("Microsoft YaHei", 10))
        self.quality_label.setFont(QFont("Microsoft YaHei", 10))
        self.consistency_label.setFont(QFont("Microsoft YaHei", 10))
        
        metrics_layout.addWidget(self.throughput_label, 0, 0)
        metrics_layout.addWidget(self.latency_label, 0, 1)
        metrics_layout.addWidget(self.quality_label, 1, 0)
        metrics_layout.addWidget(self.consistency_label, 1, 1)
        
        # 进度条
        self.fusion_progress_bar = QProgressBar()
        self.fusion_progress_bar.setRange(0, 100)
        self.fusion_progress_bar.setValue(0)
        self.fusion_progress_bar.setFormat("融合质量: %v%")
        
        metrics_layout.addWidget(self.fusion_progress_bar, 2, 0, 1, 2)
        metrics_group.setLayout(metrics_layout)
        
        main_layout.addWidget(metrics_group)
        
        # 数据源状态表
        sources_group = QGroupBox("数据源状态")
        sources_layout = QVBoxLayout()
        
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(4)
        self.source_table.setHorizontalHeaderLabels([
            "数据源名称", "状态", "数据速率", "数据质量"
        ])
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.setAlternatingRowColors(True)
        
        sources_layout.addWidget(self.source_table)
        sources_group.setLayout(sources_layout)
        
        main_layout.addWidget(sources_group)
        
        # 实时日志区
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "QTextEdit { font-family: Consolas; font-size: 9pt; background-color: #f5f5f5; }"
        )
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(log_group)
        
        main_layout.addStretch()
    
    def update_fusion_metrics(self, metrics: dict):
        """更新融合指标"""
        try:
            throughput = metrics.get('throughput', 0)
            latency = metrics.get('latency', 0)
            quality = metrics.get('quality', 0)
            consistency = metrics.get('consistency', 0)
            
            self.throughput_label.setText(f"数据吞吐量: {throughput} 条/秒")
            self.latency_label.setText(f"平均延迟: {latency} ms")
            self.quality_label.setText(f"融合质量: {quality:.1f}%")
            self.consistency_label.setText(f"数据一致性: {consistency:.1f}%")
            
            self.fusion_progress_bar.setValue(int(quality))
            
            self.logger.debug(f"融合指标已更新: {metrics}")
        except Exception as e:
            self.logger.error(f"更新融合指标失败: {e}")
    
    def update_source_status(self, sources: list):
        """更新数据源状态"""
        try:
            self.source_table.setRowCount(len(sources))
            
            for row, source in enumerate(sources):
                name_item = QTableWidgetItem(source.get('name', ''))
                name_item.setTextAlignment(Qt.AlignCenter)
                
                status_text = source.get('status', '未启用')
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                
                if '采集中' in status_text:
                    status_item.setForeground(Qt.green)
                elif '已连接' in status_text:
                    status_item.setForeground(Qt.darkGreen)
                else:
                    status_item.setForeground(Qt.gray)
                
                rate_item = QTableWidgetItem(source.get('rate', '0 Hz'))
                rate_item.setTextAlignment(Qt.AlignCenter)
                
                quality_item = QTableWidgetItem(source.get('quality', '-'))
                quality_item.setTextAlignment(Qt.AlignCenter)
                
                self.source_table.setItem(row, 0, name_item)
                self.source_table.setItem(row, 1, status_item)
                self.source_table.setItem(row, 2, rate_item)
                self.source_table.setItem(row, 3, quality_item)
            
            self.logger.debug(f"数据源状态已更新: {len(sources)} 个")
        except Exception as e:
            self.logger.error(f"更新数据源状态失败: {e}")
    
    def add_log(self, message: str):
        """添加日志"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            
            self.log_text.append(formatted_message)
            
            # 自动滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            self.logger.debug(f"添加日志: {message}")
        except Exception as e:
            self.logger.error(f"添加日志失败: {e}")
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.logger.info("日志已清空")
