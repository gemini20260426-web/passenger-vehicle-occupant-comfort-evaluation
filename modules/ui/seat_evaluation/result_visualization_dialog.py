#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结果可视化对话框
用于展示座椅评测的详细结果，包括图表、统计信息等
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QGroupBox, QScrollArea, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class ResultVisualizationDialog(QDialog):
    """结果可视化对话框"""
    
    def __init__(self, result: dict, config_manager=None, parent=None):
        super().__init__(parent)
        self.result = result
        self.config_manager = config_manager
        self._init_ui()
        self._populate_data()
        self._apply_style()
        logger.info("结果可视化对话框已初始化")
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("座椅评测结果详情")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(800)
        
        layout = QVBoxLayout(self)
        
        # 标题信息
        info_layout = self._create_header_info()
        layout.addLayout(info_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 概览标签页
        self._create_overview_tab()
        
        # 指标详情标签页
        self._create_metrics_tab()
        
        # 统计分析标签页
        self._create_statistics_tab()
        
        # 原始数据标签页
        self._create_raw_data_tab()
        
        layout.addWidget(self.tab_widget)
    
    def _create_header_info(self) -> QHBoxLayout:
        """创建头部信息"""
        layout = QHBoxLayout()
        
        # 总体评分
        score_layout = QVBoxLayout()
        overall_score = self.result.get('overall_score', 0)
        
        score_label = QLabel(f"{overall_score:.1f}")
        score_label.setAlignment(Qt.AlignCenter)
        score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 48px;
                font-weight: bold;
                color: {self._get_score_color(overall_score)};
                background-color: {self._get_score_bg_color(overall_score)};
                border: 3px solid {self._get_score_color(overall_score)};
                border-radius: 8px;
                padding: 20px;
                min-width: 120px;
            }}
        """)
        
        score_title = QLabel("总体评分")
        score_title.setAlignment(Qt.AlignCenter)
        score_title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        
        score_layout.addWidget(score_label)
        score_layout.addWidget(score_title)
        
        # 详细信息
        detail_layout = QVBoxLayout()
        
        timestamp = self.result.get('timestamp', datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        time_label = QLabel(f"评测时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        event_type = self.result.get('event_type', '未知')
        event_label = QLabel(f"触发事件: {event_type}")
        
        risk_level = self.result.get('risk_level', 'SAFE')
        risk_label = QLabel(f"风险等级: {risk_level}")
        risk_label.setStyleSheet(f"color: {self._get_risk_color(risk_level)}; font-weight: bold;")
        
        duration = self.result.get('duration', 0)
        duration_label = QLabel(f"评测时长: {duration:.1f}秒")
        
        for label in [time_label, event_label, risk_label, duration_label]:
            label.setStyleSheet("font-size: 11pt; padding: 4px;")
            detail_layout.addWidget(label)
        
        detail_layout.addStretch()
        
        layout.addLayout(score_layout)
        layout.addSpacing(30)
        layout.addLayout(detail_layout)
        layout.addStretch()
        
        return layout
    
    def _create_overview_tab(self):
        """创建概览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        splitter = QSplitter(Qt.Vertical)
        
        # 风险评估
        risk_group = self._create_risk_analysis()
        splitter.addWidget(risk_group)
        
        # 指标评分分布
        metrics_distribution = self._create_metrics_distribution()
        splitter.addWidget(metrics_distribution)
        
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(tab, "概览")
    
    def _create_metrics_tab(self):
        """创建指标详情标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        metrics = self.result.get('metrics', {})
        
        for metric_id, metric_info in metrics.items():
            metric_group = self._create_metric_detail(metric_id, metric_info)
            scroll_layout.addWidget(metric_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(tab, "指标详情")
    
    def _create_statistics_tab(self):
        """创建统计分析标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        splitter = QSplitter(Qt.Vertical)
        
        # 统计摘要
        stats_group = self._create_statistics_summary()
        splitter.addWidget(stats_group)
        
        # 对比分析
        compare_group = self._create_comparison_analysis()
        splitter.addWidget(compare_group)
        
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(tab, "统计分析")
    
    def _create_raw_data_tab(self):
        """创建原始数据标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel("原始数据展示区域（图表功能开发中）")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #666; font-size: 14pt; padding: 40px;")
        layout.addWidget(info_label)
        
        self.tab_widget.addTab(tab, "原始数据")
    
    def _create_risk_analysis(self) -> QGroupBox:
        """创建风险分析"""
        group = QGroupBox("风险分析")
        layout = QVBoxLayout(group)
        
        risk_level = self.result.get('risk_level', 'SAFE')
        risk_factors = self.result.get('risk_factors', [])
        
        # 风险等级说明
        risk_desc = {
            'SAFE': '安全 - 驾乘体验良好，无明显风险',
            'LOW': '低风险 - 轻微不舒适感，建议关注',
            'MEDIUM': '中风险 - 存在明显不适，建议改进',
            'HIGH': '高风险 - 严重不适，需立即改进'
        }
        
        desc_label = QLabel(risk_desc.get(risk_level, '未知风险等级'))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {self._get_risk_color(risk_level)}; font-weight: bold; padding: 10px;")
        layout.addWidget(desc_label)
        
        # 风险因子列表
        if risk_factors:
            factors_label = QLabel("主要风险因子:")
            factors_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            layout.addWidget(factors_label)
            
            for factor in risk_factors:
                factor_label = QLabel(f"• {factor}")
                factor_label.setStyleSheet("padding: 4px; padding-left: 20px;")
                layout.addWidget(factor_label)
        
        return group
    
    def _create_metrics_distribution(self) -> QGroupBox:
        """创建指标评分分布"""
        group = QGroupBox("指标评分分布")
        layout = QVBoxLayout(group)
        
        metrics = self.result.get('metrics', {})
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["指标名称", "评分", "权重", "等级"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        
        table.setRowCount(len(metrics))
        
        row = 0
        for metric_id, metric_info in metrics.items():
            name = metric_info.get('name', metric_id)
            score = metric_info.get('score', 0)
            weight = metric_info.get('weight', 0)
            level = metric_info.get('level', 'NORMAL')
            
            name_item = QTableWidgetItem(name)
            score_item = QTableWidgetItem(f"{score:.1f}")
            weight_item = QTableWidgetItem(f"{weight:.1f}%")
            level_item = QTableWidgetItem(level)
            
            score_item.setForeground(QColor(self._get_score_color(score)))
            level_item.setForeground(QColor(self._get_level_color(level)))
            
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, score_item)
            table.setItem(row, 2, weight_item)
            table.setItem(row, 3, level_item)
            
            row += 1
        
        layout.addWidget(table)
        
        return group
    
    def _create_metric_detail(self, metric_id: str, metric_info: dict) -> QGroupBox:
        """创建单个指标的详细信息"""
        group = QGroupBox(metric_info.get('name', metric_id))
        layout = QVBoxLayout(group)
        
        # 基本信息
        info_layout = QHBoxLayout()
        
        score = metric_info.get('score', 0)
        score_label = QLabel(f"评分: {score:.1f}")
        score_label.setStyleSheet(f"color: {self._get_score_color(score)}; font-weight: bold; font-size: 14pt;")
        
        level = metric_info.get('level', 'NORMAL')
        level_label = QLabel(f"等级: {level}")
        level_label.setStyleSheet(f"color: {self._get_level_color(level)}; font-weight: bold;")
        
        weight = metric_info.get('weight', 0)
        weight_label = QLabel(f"权重: {weight:.1f}%")
        
        info_layout.addWidget(score_label)
        info_layout.addSpacing(30)
        info_layout.addWidget(level_label)
        info_layout.addSpacing(30)
        info_layout.addWidget(weight_label)
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        
        # 详细描述
        description = metric_info.get('description', '')
        if description:
            desc_label = QLabel(f"说明: {description}")
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666; padding: 8px;")
            layout.addWidget(desc_label)
        
        # 统计数据
        stats = metric_info.get('statistics', {})
        if stats:
            stats_layout = QHBoxLayout()
            
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    stat_label = QLabel(f"{key}: {value:.3f}")
                else:
                    stat_label = QLabel(f"{key}: {value}")
                stat_label.setStyleSheet("padding: 4px 8px; background-color: #F5F5F5; border-radius: 4px;")
                stats_layout.addWidget(stat_label)
            
            stats_layout.addStretch()
            layout.addLayout(stats_layout)
        
        return group
    
    def _create_statistics_summary(self) -> QGroupBox:
        """创建统计摘要"""
        group = QGroupBox("统计摘要")
        layout = QVBoxLayout(group)
        
        stats = self.result.get('statistics', {})
        
        if not stats:
            no_data_label = QLabel("暂无统计数据")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: #999; padding: 20px;")
            layout.addWidget(no_data_label)
            return group
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["统计项", "数值"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        
        table.setRowCount(len(stats))
        
        row = 0
        for key, value in stats.items():
            key_item = QTableWidgetItem(str(key))
            if isinstance(value, (int, float)):
                value_item = QTableWidgetItem(f"{value:.3f}")
            else:
                value_item = QTableWidgetItem(str(value))
            
            table.setItem(row, 0, key_item)
            table.setItem(row, 1, value_item)
            row += 1
        
        layout.addWidget(table)
        
        return group
    
    def _create_comparison_analysis(self) -> QGroupBox:
        """创建对比分析"""
        group = QGroupBox("对比分析")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("与历史评测结果的对比分析功能开发中...")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #666; padding: 40px;")
        layout.addWidget(info_label)
        
        return group
    
    def _populate_data(self):
        """填充数据"""
        pass  # 数据已在创建标签页时填充
    
    def _get_score_color(self, score: float) -> str:
        """获取评分颜色"""
        if score >= 90:
            return "#4CAF50"  # 绿色
        elif score >= 70:
            return "#8BC34A"  # 浅绿
        elif score >= 50:
            return "#FF9800"  # 橙色
        elif score >= 30:
            return "#FF5722"  # 深橙
        else:
            return "#F44336"  # 红色
    
    def _get_score_bg_color(self, score: float) -> str:
        """获取评分背景色"""
        if score >= 90:
            return "#E8F5E9"
        elif score >= 70:
            return "#F1F8E9"
        elif score >= 50:
            return "#FFF3E0"
        elif score >= 30:
            return "#FBE9E7"
        else:
            return "#FFEBEE"
    
    def _get_risk_color(self, risk_level: str) -> str:
        """获取风险等级颜色"""
        color_map = {
            'SAFE': '#4CAF50',
            'LOW': '#8BC34A',
            'MEDIUM': '#FF9800',
            'HIGH': '#F44336'
        }
        return color_map.get(risk_level, '#666666')
    
    def _get_level_color(self, level: str) -> str:
        """获取指标等级颜色"""
        color_map = {
            'EXCELLENT': '#4CAF50',
            'GOOD': '#8BC34A',
            'NORMAL': '#FF9800',
            'POOR': '#FF5722',
            'BAD': '#F44336'
        }
        return color_map.get(level, '#666666')
    
    def _apply_style(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
            }
            QGroupBox {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #E0E0E0;
                gridline-color: #F0F0F0;
                selection-background-color: #E3F2FD;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                padding: 8px;
                border: 1px solid #E0E0E0;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #F5F5F5;
                padding: 10px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #2196F3;
            }
        """)
