#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车辆管理组件
集成到现有UI架构中，保持风格一致
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                               QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
                               QScrollArea, QFrame, QMessageBox, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

class VehicleManagementWidget(QWidget):
    """车辆管理组件"""
    
    # 定义信号
    vehicle_added = Signal(dict)
    vehicle_updated = Signal(str, dict)
    vehicle_deleted = Signal(str)
    vehicle_status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vehicles = {}  # 车辆数据存储
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === 车辆概览 ===
        overview_group = QGroupBox("📊 车辆概览")
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
        self.total_vehicles_label = QLabel("总车辆数: 0")
        self.total_vehicles_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #17a2b8;
            padding: 5px 10px;
            background-color: #d1ecf1;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.active_vehicles_label = QLabel("在线车辆: 0")
        self.active_vehicles_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
            padding: 5px 10px;
            background-color: #d4edda;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.maintenance_vehicles_label = QLabel("维护中: 0")
        self.maintenance_vehicles_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #ffc107;
            padding: 5px 10px;
            background-color: #fff3cd;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.offline_vehicles_label = QLabel("离线车辆: 0")
        self.offline_vehicles_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6c757d;
            padding: 5px 10px;
            background-color: #f8f9fa;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        overview_layout.addWidget(self.total_vehicles_label, 0, 0)
        overview_layout.addWidget(self.active_vehicles_label, 0, 1)
        overview_layout.addWidget(self.maintenance_vehicles_label, 1, 0)
        overview_layout.addWidget(self.offline_vehicles_label, 1, 1)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # === 车辆操作 ===
        operations_group = QGroupBox("🔧 车辆操作")
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
        self.add_vehicle_btn = QPushButton("➕ 添加车辆")
        self.add_vehicle_btn.setStyleSheet("""
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
        self.add_vehicle_btn.clicked.connect(self.show_add_vehicle_dialog)
        
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
        self.refresh_btn.clicked.connect(self.refresh_vehicle_list)
        
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
        self.export_btn.clicked.connect(self.export_vehicle_data)
        
        operations_layout.addWidget(self.add_vehicle_btn)
        operations_layout.addWidget(self.refresh_btn)
        operations_layout.addWidget(self.export_btn)
        operations_layout.addStretch()
        
        operations_group.setLayout(operations_layout)
        layout.addWidget(operations_group)
        
        # === 车辆列表 ===
        list_group = QGroupBox("🚗 车辆列表")
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
        
        # 车辆表格
        self.vehicle_table = QTableWidget()
        self.vehicle_table.setColumnCount(8)
        self.vehicle_table.setHorizontalHeaderLabels([
            "车牌号", "车型", "司机", "状态", "位置", "里程", "最后更新", "操作"
        ])
        
        # 设置表格样式
        self.vehicle_table.setStyleSheet("""
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
        header = self.vehicle_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 车牌号
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 车型
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 司机
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 位置
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 里程
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 最后更新
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 操作
        
        list_layout.addWidget(self.vehicle_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 填充空间
        layout.addStretch()
        
    def load_sample_data(self):
        """加载示例数据"""
        sample_vehicles = {
            "京A12345": {
                "plate": "京A12345",
                "model": "东风天龙",
                "driver": "张三",
                "status": "在线",
                "location": "北京市朝阳区",
                "mileage": "125,680 km",
                "last_update": "2025-08-13 10:30:00"
            },
            "京B67890": {
                "plate": "京B67890",
                "model": "解放J6",
                "driver": "李四",
                "status": "维护中",
                "location": "北京市海淀区",
                "mileage": "89,234 km",
                "last_update": "2025-08-13 09:15:00"
            },
            "京C11111": {
                "plate": "京C11111",
                "model": "重汽豪沃",
                "driver": "王五",
                "status": "离线",
                "location": "北京市丰台区",
                "mileage": "156,789 km",
                "last_update": "2025-08-12 18:45:00"
            }
        }
        
        self.vehicles = sample_vehicles
        self.update_vehicle_table()
        self.update_statistics()
        
    def update_vehicle_table(self):
        """更新车辆表格"""
        self.vehicle_table.setRowCount(len(self.vehicles))
        
        for row, (plate, vehicle) in enumerate(self.vehicles.items()):
            # 车牌号
            self.vehicle_table.setItem(row, 0, QTableWidgetItem(vehicle["plate"]))
            
            # 车型
            self.vehicle_table.setItem(row, 1, QTableWidgetItem(vehicle["model"]))
            
            # 司机
            self.vehicle_table.setItem(row, 2, QTableWidgetItem(vehicle["driver"]))
            
            # 状态
            status_item = QTableWidgetItem(vehicle["status"])
            if vehicle["status"] == "在线":
                status_item.setBackground(QColor("#d4edda"))
                status_item.setForeground(QColor("#155724"))
            elif vehicle["status"] == "维护中":
                status_item.setBackground(QColor("#fff3cd"))
                status_item.setForeground(QColor("#856404"))
            else:
                status_item.setBackground(QColor("#f8d7da"))
                status_item.setForeground(QColor("#721c24"))
            self.vehicle_table.setItem(row, 3, status_item)
            
            # 位置
            self.vehicle_table.setItem(row, 4, QTableWidgetItem(vehicle["location"]))
            
            # 里程
            self.vehicle_table.setItem(row, 5, QTableWidgetItem(vehicle["mileage"]))
            
            # 最后更新
            self.vehicle_table.setItem(row, 6, QTableWidgetItem(vehicle["last_update"]))
            
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
            edit_btn.clicked.connect(lambda checked, p=plate: self.edit_vehicle(p))
            
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
            delete_btn.clicked.connect(lambda checked, p=plate: self.delete_vehicle(p))
            
            operations_layout.addWidget(edit_btn)
            operations_layout.addWidget(delete_btn)
            operations_layout.addStretch()
            
            self.vehicle_table.setCellWidget(row, 7, operations_widget)
    
    def update_statistics(self):
        """更新统计信息"""
        total = len(self.vehicles)
        active = sum(1 for v in self.vehicles.values() if v["status"] == "在线")
        maintenance = sum(1 for v in self.vehicles.values() if v["status"] == "维护中")
        offline = sum(1 for v in self.vehicles.values() if v["status"] == "离线")
        
        self.total_vehicles_label.setText(f"总车辆数: {total}")
        self.active_vehicles_label.setText(f"在线车辆: {active}")
        self.maintenance_vehicles_label.setText(f"维护中: {maintenance}")
        self.offline_vehicles_label.setText(f"离线车辆: {offline}")
    
    def show_add_vehicle_dialog(self):
        """显示添加车辆对话框"""
        # 这里可以实现添加车辆的对话框
        QMessageBox.information(self, "添加车辆", "添加车辆功能待实现")
    
    def edit_vehicle(self, plate):
        """编辑车辆信息"""
        QMessageBox.information(self, "编辑车辆", f"编辑车辆 {plate} 功能待实现")
    
    def delete_vehicle(self, plate):
        """删除车辆"""
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除车辆 {plate} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.vehicles[plate]
            self.update_vehicle_table()
            self.update_statistics()
            self.vehicle_deleted.emit(plate)
    
    def refresh_vehicle_list(self):
        """刷新车辆列表"""
        self.update_vehicle_table()
        self.update_statistics()
        QMessageBox.information(self, "刷新完成", "车辆列表已刷新")
    
    def export_vehicle_data(self):
        """导出车辆数据"""
        QMessageBox.information(self, "导出数据", "导出车辆数据功能待实现")
