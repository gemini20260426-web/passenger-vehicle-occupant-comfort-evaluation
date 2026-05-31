#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车队管理组件
集成到现有UI架构中，保持风格一致
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                               QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
                               QScrollArea, QFrame, QMessageBox, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

class FleetManagementWidget(QWidget):
    """车队管理组件"""
    
    # 定义信号
    fleet_added = Signal(dict)
    fleet_updated = Signal(str, dict)
    fleet_deleted = Signal(str)
    fleet_status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fleets = {}  # 车队数据存储
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === 车队概览 ===
        overview_group = QGroupBox("📊 车队概览")
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
        self.total_fleets_label = QLabel("总车队数: 0")
        self.total_fleets_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #17a2b8;
            padding: 5px 10px;
            background-color: #d1ecf1;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.total_vehicles_label = QLabel("总车辆数: 0")
        self.total_vehicles_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
            padding: 5px 10px;
            background-color: #d4edda;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.total_drivers_label = QLabel("总司机数: 0")
        self.total_drivers_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6f42c1;
            padding: 5px 10px;
            background-color: #e2d9f3;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.active_trips_label = QLabel("进行中行程: 0")
        self.active_trips_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #fd7e14;
            padding: 5px 10px;
            background-color: #ffe8d1;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        overview_layout.addWidget(self.total_fleets_label, 0, 0)
        overview_layout.addWidget(self.total_vehicles_label, 0, 1)
        overview_layout.addWidget(self.total_drivers_label, 1, 0)
        overview_layout.addWidget(self.active_trips_label, 1, 1)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # === 车队操作 ===
        operations_group = QGroupBox("🔧 车队操作")
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
        self.add_fleet_btn = QPushButton("➕ 添加车队")
        self.add_fleet_btn.setStyleSheet("""
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
        self.add_fleet_btn.clicked.connect(self.show_add_fleet_dialog)
        
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
        self.refresh_btn.clicked.connect(self.refresh_fleet_list)
        
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
        self.export_btn.clicked.connect(self.export_fleet_data)
        
        operations_layout.addWidget(self.add_fleet_btn)
        operations_layout.addWidget(self.refresh_btn)
        operations_layout.addWidget(self.export_btn)
        operations_layout.addStretch()
        
        operations_group.setLayout(operations_layout)
        layout.addWidget(operations_group)
        
        # === 车队列表 ===
        list_group = QGroupBox("🚛 车队列表")
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
        
        # 车队表格
        self.fleet_table = QTableWidget()
        self.fleet_table.setColumnCount(8)
        self.fleet_table.setHorizontalHeaderLabels([
            "车队ID", "车队名称", "负责人", "车辆数量", "司机数量", "状态", "创建时间", "操作"
        ])
        
        # 设置表格样式
        self.fleet_table.setStyleSheet("""
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
        header = self.fleet_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 车队ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 车队名称
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 负责人
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 车辆数量
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 司机数量
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 创建时间
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 操作
        
        list_layout.addWidget(self.fleet_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 填充空间
        layout.addStretch()
        
    def load_sample_data(self):
        """加载示例数据"""
        sample_fleets = {
            "F001": {
                "id": "F001",
                "name": "北京物流一队",
                "manager": "赵经理",
                "vehicle_count": "15",
                "driver_count": "18",
                "status": "运营中",
                "create_time": "2025-01-15"
            },
            "F002": {
                "id": "F002",
                "name": "上海运输二队",
                "manager": "钱经理",
                "vehicle_count": "12",
                "driver_count": "14",
                "status": "运营中",
                "create_time": "2025-02-20"
            },
            "F003": {
                "id": "F003",
                "name": "广州配送三队",
                "manager": "孙经理",
                "vehicle_count": "8",
                "driver_count": "10",
                "status": "筹建中",
                "create_time": "2025-03-10"
            }
        }
        
        self.fleets = sample_fleets
        self.update_fleet_table()
        self.update_statistics()
        
    def update_fleet_table(self):
        """更新车队表格"""
        self.fleet_table.setRowCount(len(self.fleets))
        
        for row, (fleet_id, fleet) in enumerate(self.fleets.items()):
            # 车队ID
            self.fleet_table.setItem(row, 0, QTableWidgetItem(fleet["id"]))
            
            # 车队名称
            self.fleet_table.setItem(row, 1, QTableWidgetItem(fleet["name"]))
            
            # 负责人
            self.fleet_table.setItem(row, 2, QTableWidgetItem(fleet["manager"]))
            
            # 车辆数量
            vehicle_count_item = QTableWidgetItem(fleet["vehicle_count"])
            vehicle_count_item.setBackground(QColor("#d4edda"))
            vehicle_count_item.setForeground(QColor("#155724"))
            self.fleet_table.setItem(row, 3, vehicle_count_item)
            
            # 司机数量
            driver_count_item = QTableWidgetItem(fleet["driver_count"])
            driver_count_item.setBackground(QColor("#e2d9f3"))
            driver_count_item.setForeground(QColor("#6f42c1"))
            self.fleet_table.setItem(row, 4, driver_count_item)
            
            # 状态
            status_item = QTableWidgetItem(fleet["status"])
            if fleet["status"] == "运营中":
                status_item.setBackground(QColor("#d4edda"))
                status_item.setForeground(QColor("#155724"))
            else:
                status_item.setBackground(QColor("#fff3cd"))
                status_item.setForeground(QColor("#856404"))
            self.fleet_table.setItem(row, 5, status_item)
            
            # 创建时间
            self.fleet_table.setItem(row, 6, QTableWidgetItem(fleet["create_time"]))
            
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
            edit_btn.clicked.connect(lambda checked, f=fleet_id: self.edit_fleet(f))
            
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
            delete_btn.clicked.connect(lambda checked, f=fleet_id: self.delete_fleet(f))
            
            operations_layout.addWidget(edit_btn)
            operations_layout.addWidget(delete_btn)
            operations_layout.addStretch()
            
            self.fleet_table.setCellWidget(row, 7, operations_widget)
    
    def update_statistics(self):
        """更新统计信息"""
        total_fleets = len(self.fleets)
        total_vehicles = sum(int(f["vehicle_count"]) for f in self.fleets.values())
        total_drivers = sum(int(f["driver_count"]) for f in self.fleets.values())
        active_trips = 5  # 示例数据
        
        self.total_fleets_label.setText(f"总车队数: {total_fleets}")
        self.total_vehicles_label.setText(f"总车辆数: {total_vehicles}")
        self.total_drivers_label.setText(f"总司机数: {total_drivers}")
        self.active_trips_label.setText(f"进行中行程: {active_trips}")
    
    def show_add_fleet_dialog(self):
        """显示添加车队对话框"""
        QMessageBox.information(self, "添加车队", "添加车队功能待实现")
    
    def edit_fleet(self, fleet_id):
        """编辑车队信息"""
        QMessageBox.information(self, "编辑车队", f"编辑车队 {fleet_id} 功能待实现")
    
    def delete_fleet(self, fleet_id):
        """删除车队"""
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除车队 {fleet_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.fleets[fleet_id]
            self.update_fleet_table()
            self.update_statistics()
            self.fleet_deleted.emit(fleet_id)
    
    def refresh_fleet_list(self):
        """刷新车队列表"""
        self.update_fleet_table()
        self.update_statistics()
        QMessageBox.information(self, "刷新完成", "车队列表已刷新")
    
    def export_fleet_data(self):
        """导出车队数据"""
        QMessageBox.information(self, "导出数据", "导出车队数据功能待实现")
