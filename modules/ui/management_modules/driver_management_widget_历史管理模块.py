#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
司机管理组件
集成到现有UI架构中，保持风格一致
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                               QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
                               QScrollArea, QFrame, QMessageBox, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

class DriverManagementWidget(QWidget):
    """司机管理组件"""
    
    # 定义信号
    driver_added = Signal(dict)
    driver_updated = Signal(str, dict)
    driver_deleted = Signal(str)
    driver_status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drivers = {}  # 司机数据存储
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === 司机概览 ===
        overview_group = QGroupBox("📊 司机概览")
        overview_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #17a2b8;
                font-weight: bold;
                font-size: 13px;
                color: #495057;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
        """)
        overview_layout = QGridLayout()
        
        # 统计信息
        self.total_drivers_label = QLabel("总司机数: 0")
        self.total_drivers_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #17a2b8;
            padding: 5px 10px;
            background-color: #d1ecf1;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.on_duty_label = QLabel("在岗司机: 0")
        self.on_duty_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
            padding: 5px 10px;
            background-color: #d4edda;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.off_duty_label = QLabel("休息司机: 0")
        self.off_duty_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6c757d;
            padding: 5px 10px;
            background-color: #f8f9fa;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.training_label = QLabel("培训中: 0")
        self.training_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #ffc107;
            padding: 5px 10px;
            background-color: #fff3cd;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        overview_layout.addWidget(self.total_drivers_label, 0, 0)
        overview_layout.addWidget(self.on_duty_label, 0, 1)
        overview_layout.addWidget(self.off_duty_label, 1, 0)
        overview_layout.addWidget(self.training_label, 1, 1)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # === 司机操作 ===
        operations_group = QGroupBox("🔧 司机操作")
        operations_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #28a745;
                font-weight: bold;
                font-size: 13px;
                color: #495057;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
        """)
        operations_layout = QHBoxLayout()
        
        # 操作按钮
        self.add_driver_btn = QPushButton("➕ 添加司机")
        self.add_driver_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #28a745;
                border-radius: 6px;
                padding: 8px 16px;
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #1e7e34;
            }
        """)
        self.add_driver_btn.clicked.connect(self.show_add_driver_dialog)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #17a2b8;
                border-radius: 6px;
                padding: 8px 16px;
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #138496;
                border-color: #117a8b;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_driver_list)
        
        self.export_btn = QPushButton("📤 导出")
        self.export_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #6f42c1;
                border-radius: 6px;
                padding: 8px 16px;
                background-color: #6f42c1;
                color: white;
                font-weight: bold;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
                border-color: #4c2889;
            }
        """)
        self.export_btn.clicked.connect(self.export_driver_data)
        
        operations_layout.addWidget(self.add_driver_btn)
        operations_layout.addWidget(self.refresh_btn)
        operations_layout.addWidget(self.export_btn)
        operations_layout.addStretch()
        
        operations_group.setLayout(operations_layout)
        layout.addWidget(operations_group)
        
        # === 司机列表 ===
        list_group = QGroupBox("👨‍💼 司机列表")
        list_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #6c757d;
                font-weight: bold;
                font-size: 13px;
                color: #495057;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
        """)
        list_layout = QVBoxLayout()
        
        # 司机表格
        self.driver_table = QTableWidget()
        self.driver_table.setColumnCount(9)
        self.driver_table.setHorizontalHeaderLabels([
            "工号", "姓名", "手机号", "驾驶证号", "状态", "车辆", "评分", "最后更新", "操作"
        ])
        
        # 设置表格样式
        self.driver_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                gridline-color: #dee2e6;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #dee2e6;
                font-weight: bold;
                color: #495057;
            }
        """)
        
        # 设置列宽
        header = self.driver_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 工号
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 姓名
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 手机号
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 驾驶证号
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 车辆
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 评分
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 最后更新
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 操作
        
        list_layout.addWidget(self.driver_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 填充空间
        layout.addStretch()
        
    def load_sample_data(self):
        """加载示例数据"""
        sample_drivers = {
            "D001": {
                "id": "D001",
                "name": "张三",
                "phone": "13800138001",
                "license": "110101199001011234",
                "status": "在岗",
                "vehicle": "京A12345",
                "rating": "4.8",
                "last_update": "2025-08-13 10:30:00"
            },
            "D002": {
                "id": "D002",
                "name": "李四",
                "phone": "13800138002",
                "license": "110101199002022345",
                "status": "休息",
                "vehicle": "京B67890",
                "rating": "4.6",
                "last_update": "2025-08-13 09:15:00"
            },
            "D003": {
                "id": "D003",
                "name": "王五",
                "phone": "13800138003",
                "license": "110101199003033456",
                "status": "培训中",
                "vehicle": "无",
                "rating": "4.2",
                "last_update": "2025-08-13 08:45:00"
            }
        }
        
        self.drivers = sample_drivers
        self.update_driver_table()
        self.update_statistics()
        
    def update_driver_table(self):
        """更新司机表格"""
        self.driver_table.setRowCount(len(self.drivers))
        
        for row, (driver_id, driver) in enumerate(self.drivers.items()):
            # 工号
            self.driver_table.setItem(row, 0, QTableWidgetItem(driver["id"]))
            
            # 姓名
            self.driver_table.setItem(row, 1, QTableWidgetItem(driver["name"]))
            
            # 手机号
            self.driver_table.setItem(row, 2, QTableWidgetItem(driver["phone"]))
            
            # 驾驶证号
            self.driver_table.setItem(row, 3, QTableWidgetItem(driver["license"]))
            
            # 状态
            status_item = QTableWidgetItem(driver["status"])
            if driver["status"] == "在岗":
                status_item.setBackground(QColor("#d4edda"))
                status_item.setForeground(QColor("#155724"))
            elif driver["status"] == "培训中":
                status_item.setBackground(QColor("#fff3cd"))
                status_item.setForeground(QColor("#856404"))
            else:
                status_item.setBackground(QColor("#f8f9fa"))
                status_item.setForeground(QColor("#6c757d"))
            self.driver_table.setItem(row, 4, status_item)
            
            # 车辆
            self.driver_table.setItem(row, 5, QTableWidgetItem(driver["vehicle"]))
            
            # 评分
            rating_item = QTableWidgetItem(driver["rating"])
            rating_item.setBackground(QColor("#e2d9f3"))
            rating_item.setForeground(QColor("#6f42c1"))
            self.driver_table.setItem(row, 6, rating_item)
            
            # 最后更新
            self.driver_table.setItem(row, 7, QTableWidgetItem(driver["last_update"]))
            
            # 操作按钮
            operations_widget = QWidget()
            operations_layout = QHBoxLayout(operations_widget)
            operations_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_btn = QPushButton("✏️")
            edit_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #17a2b8;
                    border-radius: 4px;
                    padding: 4px 8px;
                    background-color: #17a2b8;
                    color: white;
                    font-size: 10px;
                    min-width: 30px;
                }
                QPushButton:hover {
                    background-color: #138496;
                }
            """)
            edit_btn.clicked.connect(lambda checked, d=driver_id: self.edit_driver(d))
            
            delete_btn = QPushButton("🗑️")
            delete_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #dc3545;
                    border-radius: 4px;
                    padding: 4px 8px;
                    background-color: #dc3545;
                    color: white;
                    font-size: 10px;
                    min-width: 30px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            delete_btn.clicked.connect(lambda checked, d=driver_id: self.delete_driver(d))
            
            operations_layout.addWidget(edit_btn)
            operations_layout.addWidget(delete_btn)
            operations_layout.addStretch()
            
            self.driver_table.setCellWidget(row, 8, operations_widget)
    
    def update_statistics(self):
        """更新统计信息"""
        total = len(self.drivers)
        on_duty = sum(1 for d in self.drivers.values() if d["status"] == "在岗")
        off_duty = sum(1 for d in self.drivers.values() if d["status"] == "休息")
        training = sum(1 for d in self.drivers.values() if d["status"] == "培训中")
        
        self.total_drivers_label.setText(f"总司机数: {total}")
        self.on_duty_label.setText(f"在岗司机: {on_duty}")
        self.off_duty_label.setText(f"休息司机: {off_duty}")
        self.training_label.setText(f"培训中: {training}")
    
    def show_add_driver_dialog(self):
        """显示添加司机对话框"""
        QMessageBox.information(self, "添加司机", "添加司机功能待实现")
    
    def edit_driver(self, driver_id):
        """编辑司机信息"""
        QMessageBox.information(self, "编辑司机", f"编辑司机 {driver_id} 功能待实现")
    
    def delete_driver(self, driver_id):
        """删除司机"""
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除司机 {driver_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.drivers[driver_id]
            self.update_driver_table()
            self.update_statistics()
            self.driver_deleted.emit(driver_id)
    
    def refresh_driver_list(self):
        """刷新司机列表"""
        self.update_driver_table()
        self.update_statistics()
        QMessageBox.information(self, "刷新完成", "司机列表已刷新")
    
    def export_driver_data(self):
        """导出司机数据"""
        QMessageBox.information(self, "导出数据", "导出司机数据功能待实现")
