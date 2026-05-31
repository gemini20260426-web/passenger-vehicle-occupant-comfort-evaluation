#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标配置对话框
用于配置座椅评测指标的权重、启用/禁用状态等
"""

import logging
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QSlider, QDoubleSpinBox,
    QCheckBox, QGroupBox, QScrollArea, QWidget,
    QFormLayout, QComboBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class IndicatorConfigDialog(QDialog):
    """指标配置对话框"""
    
    config_saved = Signal(dict)  # 配置保存信号
    
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.indicator_definitions = {}
        self.current_config = {}
        self._init_ui()
        self._load_indicator_definitions()
        self._load_config()
        self._apply_style()
        logger.info("指标配置对话框已初始化")
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("座椅评测指标配置")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("座椅评测指标配置")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #E0E0E0;")
        layout.addWidget(separator)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 指标权重配置标签页
        self._create_weight_config_tab()
        
        # 触发事件配置标签页
        self._create_trigger_config_tab()
        
        # 高级设置标签页
        self._create_advanced_settings_tab()
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self._reset_to_default)
        
        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self._import_config)
        
        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self._export_config)
        
        button_layout.addStretch()
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(export_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        save_btn.clicked.connect(self._save_config)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _create_weight_config_tab(self):
        """创建指标权重配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 说明
        info_label = QLabel(
            "配置座椅评测指标的权重和启用状态。权重总和应为100%。\n"
            "鼠标悬停在指标名称上可查看详细说明。"
        )
        info_label.setStyleSheet("color: #666; padding: 8px; background-color: #F5F5F5; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # 指标表格
        self.indicator_table = QTableWidget()
        self.indicator_table.setColumnCount(5)
        self.indicator_table.setHorizontalHeaderLabels([
            "启用", "指标名称", "类别", "权重(%)", "操作"
        ])
        self.indicator_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.indicator_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.indicator_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.indicator_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.indicator_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.indicator_table.setAlternatingRowColors(True)
        self.indicator_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.indicator_table)
        
        # 权重检查和自动分配
        check_layout = QHBoxLayout()
        
        self.weight_total_label = QLabel("权重总和: 0%")
        self.weight_total_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        
        auto_balance_btn = QPushButton("自动平衡权重")
        auto_balance_btn.clicked.connect(self._auto_balance_weights)
        
        check_layout.addWidget(self.weight_total_label)
        check_layout.addStretch()
        check_layout.addWidget(auto_balance_btn)
        
        layout.addLayout(check_layout)
        
        self.tab_widget.addTab(tab, "指标权重配置")
    
    def _create_trigger_config_tab(self):
        """创建触发事件配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 说明
        info_label = QLabel(
            "配置座椅评测的触发事件。系统在检测到这些事件时会自动开始评测。"
        )
        info_label.setStyleSheet("color: #666; padding: 8px; background-color: #F5F5F5; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # 触发事件表格
        self.trigger_table = QTableWidget()
        self.trigger_table.setColumnCount(4)
        self.trigger_table.setHorizontalHeaderLabels([
            "启用", "事件类型", "描述", "参数设置"
        ])
        self.trigger_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.trigger_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.trigger_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.trigger_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.trigger_table.setAlternatingRowColors(True)
        self.trigger_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.trigger_table)
        
        self.tab_widget.addTab(tab, "触发事件配置")
    
    def _create_advanced_settings_tab(self):
        """创建高级设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 评测时长设置
        duration_group = QGroupBox("评测时长设置")
        duration_layout = QFormLayout(duration_group)
        
        self.pre_duration_spin = QDoubleSpinBox()
        self.pre_duration_spin.setRange(0, 30)
        self.pre_duration_spin.setSuffix(" 秒")
        self.pre_duration_spin.setValue(5)
        self.pre_duration_spin.setDecimals(1)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(1, 120)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setValue(30)
        self.duration_spin.setDecimals(1)
        
        self.post_duration_spin = QDoubleSpinBox()
        self.post_duration_spin.setRange(0, 30)
        self.post_duration_spin.setSuffix(" 秒")
        self.post_duration_spin.setValue(5)
        self.post_duration_spin.setDecimals(1)
        
        duration_layout.addRow("事件前采集时长:", self.pre_duration_spin)
        duration_layout.addRow("事件中评测时长:", self.duration_spin)
        duration_layout.addRow("事件后采集时长:", self.post_duration_spin)
        
        scroll_layout.addWidget(duration_group)
        
        # 评分算法设置
        scoring_group = QGroupBox("评分算法设置")
        scoring_layout = QFormLayout(scoring_group)
        
        self.scoring_method_combo = QComboBox()
        self.scoring_method_combo.addItems([
            "加权平均法",
            "几何平均法",
            "调和平均法",
            "最大值加权法"
        ])
        
        self.min_score_spin = QDoubleSpinBox()
        self.min_score_spin.setRange(0, 100)
        self.min_score_spin.setValue(0)
        self.min_score_spin.setSuffix(" 分")
        
        self.max_score_spin = QDoubleSpinBox()
        self.max_score_spin.setRange(0, 100)
        self.max_score_spin.setValue(100)
        self.max_score_spin.setSuffix(" 分")
        
        scoring_layout.addRow("评分算法:", self.scoring_method_combo)
        scoring_layout.addRow("最低分数:", self.min_score_spin)
        scoring_layout.addRow("最高分数:", self.max_score_spin)
        
        scroll_layout.addWidget(scoring_group)
        
        # 数据同步设置
        sync_group = QGroupBox("数据同步设置")
        sync_layout = QFormLayout(sync_group)
        
        self.sync_tolerance_spin = QDoubleSpinBox()
        self.sync_tolerance_spin.setRange(0.001, 1)
        self.sync_tolerance_spin.setSingleStep(0.01)
        self.sync_tolerance_spin.setSuffix(" 秒")
        self.sync_tolerance_spin.setValue(0.01)
        self.sync_tolerance_spin.setDecimals(3)
        
        self.interpolation_method_combo = QComboBox()
        self.interpolation_method_combo.addItems([
            "线性插值",
            "最近邻插值",
            "三次样条插值"
        ])
        
        sync_layout.addRow("同步容差:", self.sync_tolerance_spin)
        sync_layout.addRow("插值方法:", self.interpolation_method_combo)
        
        scroll_layout.addWidget(sync_group)
        
        # 可视化设置
        viz_group = QGroupBox("可视化设置")
        viz_layout = QFormLayout(viz_group)
        
        self.show_raw_data_check = QCheckBox("显示原始数据")
        self.show_raw_data_check.setChecked(True)
        
        self.show_statistics_check = QCheckBox("显示统计信息")
        self.show_statistics_check.setChecked(True)
        
        self.chart_height_spin = QDoubleSpinBox()
        self.chart_height_spin.setRange(100, 500)
        self.chart_height_spin.setSuffix(" 像素")
        self.chart_height_spin.setValue(200)
        self.chart_height_spin.setDecimals(0)
        
        viz_layout.addRow(self.show_raw_data_check)
        viz_layout.addRow(self.show_statistics_check)
        viz_layout.addRow("图表高度:", self.chart_height_spin)
        
        scroll_layout.addWidget(viz_group)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(tab, "高级设置")
    
    def _load_indicator_definitions(self):
        """加载指标定义"""
        try:
            from core.core.seat_evaluation.metadata_registry import INDICATOR_DEFINITIONS
            self.indicator_definitions = INDICATOR_DEFINITIONS
            self._populate_indicator_table()
            self._populate_trigger_table()
        except Exception as e:
            logger.error(f"加载指标定义失败: {e}")
    
    def _populate_indicator_table(self):
        """填充指标表格"""
        self.indicator_table.setRowCount(0)
        
        for indicator_id, definition in self.indicator_definitions.items():
            row = self.indicator_table.rowCount()
            self.indicator_table.insertRow(row)
            
            # 启用复选框
            enable_check = QCheckBox()
            enable_check.setChecked(True)
            enable_check.stateChanged.connect(self._on_indicator_enabled_changed)
            self.indicator_table.setCellWidget(row, 0, enable_check)
            
            # 指标名称
            name_item = QTableWidgetItem(definition.get('name', indicator_id))
            name_item.setData(Qt.UserRole, indicator_id)
            name_item.setToolTip(definition.get('description', ''))
            self.indicator_table.setItem(row, 1, name_item)
            
            # 类别
            category_item = QTableWidgetItem(definition.get('category', '通用'))
            self.indicator_table.setItem(row, 2, category_item)
            
            # 权重
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(0, 100)
            weight_spin.setSingleStep(1)
            weight_spin.setSuffix(" %")
            weight_spin.setValue(definition.get('default_weight', 5))
            weight_spin.valueChanged.connect(self._update_weight_total)
            self.indicator_table.setCellWidget(row, 3, weight_spin)
            
            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            detail_btn = QPushButton("详情")
            detail_btn.setMaximumWidth(60)
            detail_btn.clicked.connect(lambda checked, i=indicator_id: self._show_indicator_detail(i))
            
            btn_layout.addWidget(detail_btn)
            btn_layout.addStretch()
            self.indicator_table.setCellWidget(row, 4, btn_widget)
        
        self._update_weight_total()
    
    def _populate_trigger_table(self):
        """填充触发事件表格"""
        trigger_types = [
            ('brake', '紧急制动', '检测到急刹车事件时触发评测'),
            ('accelerate', '急加速', '检测到急加速事件时触发评测'),
            ('turn', '急转弯', '检测到急转弯事件时触发评测'),
            ('lane_change', '变道', '检测到变道事件时触发评测'),
            ('start', '起步', '检测到车辆起步时触发评测'),
            ('stop', '停车', '检测到车辆停止时触发评测'),
            ('manual', '手动触发', '用户手动触发评测')
        ]
        
        self.trigger_table.setRowCount(0)
        
        for trigger_id, name, description in trigger_types:
            row = self.trigger_table.rowCount()
            self.trigger_table.insertRow(row)
            
            # 启用复选框
            enable_check = QCheckBox()
            enable_check.setChecked(trigger_id != 'manual')
            self.trigger_table.setCellWidget(row, 0, enable_check)
            
            # 事件类型
            type_item = QTableWidgetItem(name)
            type_item.setData(Qt.UserRole, trigger_id)
            self.trigger_table.setItem(row, 1, type_item)
            
            # 描述
            desc_item = QTableWidgetItem(description)
            self.trigger_table.setItem(row, 2, desc_item)
            
            # 参数设置按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            config_btn = QPushButton("设置")
            config_btn.setMaximumWidth(60)
            config_btn.clicked.connect(lambda checked, t=trigger_id: self._show_trigger_config(t))
            
            btn_layout.addWidget(config_btn)
            btn_layout.addStretch()
            self.trigger_table.setCellWidget(row, 3, btn_widget)
    
    def _load_config(self):
        """加载配置"""
        # 从config_manager加载配置
        if self.config_manager:
            try:
                config = self.config_manager.get('seat_evaluation', {})
                self.current_config = config
                self._apply_config_to_ui(config)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
    
    def _apply_config_to_ui(self, config: dict):
        """将配置应用到UI"""
        # 指标权重配置
        if 'indicator_weights' in config:
            weights = config['indicator_weights']
            for row in range(self.indicator_table.rowCount()):
                indicator_id = self.indicator_table.item(row, 1).data(Qt.UserRole)
                if indicator_id in weights:
                    weight_spin = self.indicator_table.cellWidget(row, 3)
                    weight_spin.setValue(weights[indicator_id])
        
        # 触发事件配置
        if 'trigger_events' in config:
            triggers = config['trigger_events']
            for row in range(self.trigger_table.rowCount()):
                trigger_id = self.trigger_table.item(row, 1).data(Qt.UserRole)
                if trigger_id in triggers:
                    trigger_config = triggers[trigger_id]
                    enable_check = self.trigger_table.cellWidget(row, 0)
                    enable_check.setChecked(trigger_config.get('enabled', True))
        
        # 高级设置
        if 'advanced' in config:
            advanced = config['advanced']
            self.pre_duration_spin.setValue(advanced.get('pre_duration', 5))
            self.duration_spin.setValue(advanced.get('duration', 30))
            self.post_duration_spin.setValue(advanced.get('post_duration', 5))
            self.scoring_method_combo.setCurrentText(advanced.get('scoring_method', '加权平均法'))
            self.min_score_spin.setValue(advanced.get('min_score', 0))
            self.max_score_spin.setValue(advanced.get('max_score', 100))
            self.sync_tolerance_spin.setValue(advanced.get('sync_tolerance', 0.01))
            self.interpolation_method_combo.setCurrentText(advanced.get('interpolation_method', '线性插值'))
            self.show_raw_data_check.setChecked(advanced.get('show_raw_data', True))
            self.show_statistics_check.setChecked(advanced.get('show_statistics', True))
            self.chart_height_spin.setValue(advanced.get('chart_height', 200))
    
    def _update_weight_total(self):
        """更新权重总和"""
        total = 0
        for row in range(self.indicator_table.rowCount()):
            weight_spin = self.indicator_table.cellWidget(row, 3)
            total += weight_spin.value()
        
        self.weight_total_label.setText(f"权重总和: {total:.1f}%")
        
        if abs(total - 100) < 0.1:
            self.weight_total_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #4CAF50;")
        else:
            self.weight_total_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #F44336;")
    
    def _auto_balance_weights(self):
        """自动平衡权重"""
        enabled_count = 0
        for row in range(self.indicator_table.rowCount()):
            enable_check = self.indicator_table.cellWidget(row, 0)
            if enable_check.isChecked():
                enabled_count += 1
        
        if enabled_count == 0:
            QMessageBox.warning(self, "警告", "请至少启用一个指标！")
            return
        
        weight_per_indicator = 100.0 / enabled_count
        
        for row in range(self.indicator_table.rowCount()):
            enable_check = self.indicator_table.cellWidget(row, 0)
            weight_spin = self.indicator_table.cellWidget(row, 3)
            if enable_check.isChecked():
                weight_spin.setValue(weight_per_indicator)
            else:
                weight_spin.setValue(0)
    
    def _on_indicator_enabled_changed(self, state: int):
        """指标启用状态变化"""
        self._update_weight_total()
    
    def _show_indicator_detail(self, indicator_id: str):
        """显示指标详情"""
        if indicator_id not in self.indicator_definitions:
            return
        
        definition = self.indicator_definitions[indicator_id]
        
        detail_text = f"""
指标名称: {definition.get('name', indicator_id)}
类别: {definition.get('category', '通用')}
描述: {definition.get('description', '')}
单位: {definition.get('unit', '')}
默认权重: {definition.get('default_weight', 5)}%
取值范围: {definition.get('value_range', '')}
算子: {definition.get('operator', '')}
"""
        
        QMessageBox.information(self, f"指标详情 - {definition.get('name', indicator_id)}", detail_text)
    
    def _show_trigger_config(self, trigger_id: str):
        """显示触发事件配置"""
        QMessageBox.information(self, "触发事件配置", f"触发事件 '{trigger_id}' 的详细配置功能开发中...")
    
    def _reset_to_default(self):
        """重置为默认配置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要将所有配置重置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._populate_indicator_table()
            self._populate_trigger_table()
            # 重置高级设置
            self.pre_duration_spin.setValue(5)
            self.duration_spin.setValue(30)
            self.post_duration_spin.setValue(5)
            self.scoring_method_combo.setCurrentText("加权平均法")
            self.min_score_spin.setValue(0)
            self.max_score_spin.setValue(100)
            self.sync_tolerance_spin.setValue(0.01)
            self.interpolation_method_combo.setCurrentText("线性插值")
            self.show_raw_data_check.setChecked(True)
            self.show_statistics_check.setChecked(True)
            self.chart_height_spin.setValue(200)
    
    def _import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.current_config = config
                self._apply_config_to_ui(config)
                QMessageBox.information(self, "成功", "配置导入成功！")
            except Exception as e:
                logger.error(f"导入配置失败: {e}")
                QMessageBox.critical(self, "错误", f"导入配置失败: {e}")
    
    def _export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "seat_evaluation_config.json", "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                config = self._collect_config_from_ui()
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "配置导出成功！")
            except Exception as e:
                logger.error(f"导出配置失败: {e}")
                QMessageBox.critical(self, "错误", f"导出配置失败: {e}")
    
    def _collect_config_from_ui(self) -> dict:
        """从UI收集配置"""
        config = {}
        
        # 指标权重配置
        indicator_weights = {}
        for row in range(self.indicator_table.rowCount()):
            indicator_id = self.indicator_table.item(row, 1).data(Qt.UserRole)
            enable_check = self.indicator_table.cellWidget(row, 0)
            weight_spin = self.indicator_table.cellWidget(row, 3)
            
            if enable_check.isChecked():
                indicator_weights[indicator_id] = weight_spin.value()
        
        config['indicator_weights'] = indicator_weights
        
        # 触发事件配置
        trigger_events = {}
        for row in range(self.trigger_table.rowCount()):
            trigger_id = self.trigger_table.item(row, 1).data(Qt.UserRole)
            enable_check = self.trigger_table.cellWidget(row, 0)
            
            trigger_events[trigger_id] = {
                'enabled': enable_check.isChecked()
            }
        
        config['trigger_events'] = trigger_events
        
        # 高级设置
        config['advanced'] = {
            'pre_duration': self.pre_duration_spin.value(),
            'duration': self.duration_spin.value(),
            'post_duration': self.post_duration_spin.value(),
            'scoring_method': self.scoring_method_combo.currentText(),
            'min_score': self.min_score_spin.value(),
            'max_score': self.max_score_spin.value(),
            'sync_tolerance': self.sync_tolerance_spin.value(),
            'interpolation_method': self.interpolation_method_combo.currentText(),
            'show_raw_data': self.show_raw_data_check.isChecked(),
            'show_statistics': self.show_statistics_check.isChecked(),
            'chart_height': self.chart_height_spin.value()
        }
        
        return config
    
    def _save_config(self):
        """保存配置"""
        try:
            # 收集配置
            config = self._collect_config_from_ui()
            
            # 验证权重总和
            total_weight = sum(config['indicator_weights'].values())
            if abs(total_weight - 100) > 0.1:
                reply = QMessageBox.question(
                    self, "权重警告",
                    f"权重总和为 {total_weight:.1f}%，不是100%。是否继续保存？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            # 保存到config_manager
            if self.config_manager:
                self.config_manager.set('seat_evaluation', config)
                self.config_manager.save()
            
            self.current_config = config
            self.config_saved.emit(config)
            
            QMessageBox.information(self, "成功", "配置保存成功！")
            self.accept()
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
    
    def _apply_style(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #E0E0E0;
                gridline-color: #F0F0F0;
                selection-background-color: #E3F2FD;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                padding: 6px;
                border: 1px solid #E0E0E0;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QDoubleSpinBox, QComboBox {
                padding: 4px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
            }
            QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #2196F3;
            }
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #F5F5F5;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #2196F3;
            }
        """)
