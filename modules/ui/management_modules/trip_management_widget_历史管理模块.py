#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行程管理组件
集成到现有UI架构中，保持风格一致
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                               QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
                               QScrollArea, QFrame, QMessageBox, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

class TripManagementWidget(QWidget):
    """行程管理组件"""
    
    # 定义信号
    trip_added = Signal(dict)
    trip_updated = Signal(str, dict)
    trip_deleted = Signal(str)
    trip_status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.trips = {}  # 行程数据存储
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # === 行程概览 ===
        overview_group = QGroupBox("📊 行程概览")
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
        self.total_trips_label = QLabel("总行程数: 0")
        self.total_trips_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #17a2b8;
            padding: 5px 10px;
            background-color: #d1ecf1;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.active_trips_label = QLabel("进行中: 0")
        self.active_trips_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
            padding: 5px 10px;
            background-color: #d4edda;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.completed_trips_label = QLabel("已完成: 0")
        self.completed_trips_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6f42c1;
            padding: 5px 10px;
            background-color: #e2d9f3;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        self.cancelled_trips_label = QLabel("已取消: 0")
        self.cancelled_trips_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #6c757d;
            padding: 5px 10px;
            background-color: #f8f9fa;
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        """)
        
        overview_layout.addWidget(self.total_trips_label, 0, 0)
        overview_layout.addWidget(self.active_trips_label, 0, 1)
        overview_layout.addWidget(self.completed_trips_label, 1, 0)
        overview_layout.addWidget(self.cancelled_trips_label, 1, 1)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # === 行程操作 ===
        operations_group = QGroupBox("🔧 行程操作")
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
        self.add_trip_btn = QPushButton("➕ 添加行程")
        self.add_trip_btn.setStyleSheet("""
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
        self.add_trip_btn.clicked.connect(self.show_add_trip_dialog)
        
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
        self.refresh_btn.clicked.connect(self.refresh_trip_list)
        
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
        self.export_btn.clicked.connect(self.export_trip_data)
        
        operations_layout.addWidget(self.add_trip_btn)
        operations_layout.addWidget(self.refresh_btn)
        operations_layout.addWidget(self.export_btn)
        operations_layout.addStretch()
        
        operations_group.setLayout(operations_layout)
        layout.addWidget(operations_group)
        
        # === 行程列表 ===
        list_group = QGroupBox("🗺️ 行程列表")
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
        
        # 行程表格
        self.trip_table = QTableWidget()
        self.trip_table.setColumnCount(9)
        self.trip_table.setHorizontalHeaderLabels([
            "行程ID", "起点", "终点", "车辆", "司机", "状态", "开始时间", "预计到达", "操作"
        ])
        
        # 设置表格样式
        self.trip_table.setStyleSheet("""
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
        header = self.trip_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 行程ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 起点
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 终点
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 车辆
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 司机
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 开始时间
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 预计到达
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 操作
        
        list_layout.addWidget(self.trip_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # 填充空间
        layout.addStretch()
        
    def load_sample_data(self):
        """加载示例数据"""
        sample_trips = {
            "T001": {
                "id": "T001",
                "start": "北京市朝阳区",
                "end": "上海市浦东新区",
                "vehicle": "京A12345",
                "driver": "张三",
                "status": "进行中",
                "start_time": "2025-08-13 08:00",
                "eta": "2025-08-14 16:00"
            },
            "T002": {
                "id": "T002",
                "start": "广州市天河区",
                "end": "深圳市南山区",
                "vehicle": "粤B67890",
                "driver": "李四",
                "status": "已完成",
                "start_time": "2025-08-12 09:00",
                "eta": "2025-08-12 12:00"
            },
            "T003": {
                "id": "T003",
                "start": "杭州市西湖区",
                "end": "南京市鼓楼区",
                "vehicle": "浙C11111",
                "driver": "王五",
                "status": "已取消",
                "start_time": "2025-08-11 10:00",
                "eta": "2025-08-11 15:00"
            }
        }
        
        self.trips = sample_trips
        self.update_trip_table()
        self.update_statistics()
        
    def update_trip_table(self):
        """更新行程表格"""
        self.trip_table.setRowCount(len(self.trips))
        
        for row, (trip_id, trip) in enumerate(self.trips.items()):
            # 行程ID
            self.trip_table.setItem(row, 0, QTableWidgetItem(trip["id"]))
            
            # 起点
            self.trip_table.setItem(row, 1, QTableWidgetItem(trip["start"]))
            
            # 终点
            self.trip_table.setItem(row, 2, QTableWidgetItem(trip["end"]))
            
            # 车辆
            self.trip_table.setItem(row, 3, QTableWidgetItem(trip["vehicle"]))
            
            # 司机
            self.trip_table.setItem(row, 4, QTableWidgetItem(trip["driver"]))
            
            # 状态
            status_item = QTableWidgetItem(trip["status"])
            if trip["status"] == "进行中":
                status_item.setBackground(QColor("#d4edda"))
                status_item.setForeground(QColor("#155724"))
            elif trip["status"] == "已完成":
                status_item.setBackground(QColor("#e2d9f3"))
                status_item.setForeground(QColor("#6f42c1"))
            else:
                status_item.setBackground(QColor("#f8f9fa"))
                status_item.setForeground(QColor("#6c757d"))
            self.trip_table.setItem(row, 5, status_item)
            
            # 开始时间
            self.trip_table.setItem(row, 6, QTableWidgetItem(trip["start_time"]))
            
            # 预计到达
            self.trip_table.setItem(row, 7, QTableWidgetItem(trip["eta"]))
            
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
            edit_btn.clicked.connect(lambda checked, t=trip_id: self.edit_trip(t))
            
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
            delete_btn.clicked.connect(lambda checked, t=trip_id: self.delete_trip(t))
            
            operations_layout.addWidget(edit_btn)
            operations_layout.addWidget(delete_btn)
            operations_layout.addStretch()
            
            self.trip_table.setCellWidget(row, 8, operations_widget)
    
    def update_statistics(self):
        """更新统计信息"""
        total = len(self.trips)
        active = sum(1 for t in self.trips.values() if t["status"] == "进行中")
        completed = sum(1 for t in self.trips.values() if t["status"] == "已完成")
        cancelled = sum(1 for t in self.trips.values() if t["status"] == "已取消")
        
        self.total_trips_label.setText(f"总行程数: {total}")
        self.active_trips_label.setText(f"进行中: {active}")
        self.completed_trips_label.setText(f"已完成: {completed}")
        self.cancelled_trips_label.setText(f"已取消: {cancelled}")
    
    def show_add_trip_dialog(self):
        """显示添加行程对话框"""
        QMessageBox.information(self, "添加行程", "添加行程功能待实现")
    
    def edit_trip(self, trip_id):
        """编辑行程信息"""
        QMessageBox.information(self, "编辑行程", f"编辑行程 {trip_id} 功能待实现")
    
    def delete_trip(self, trip_id):
        """删除行程"""
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除行程 {trip_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.trips[trip_id]
            self.update_trip_table()
            self.update_statistics()
            self.trip_deleted.emit(trip_id)
    
    def refresh_trip_list(self):
        """刷新行程列表"""
        self.update_trip_table()
        self.update_statistics()
        QMessageBox.information(self, "刷新完成", "行程列表已刷新")
    
    def export_trip_data(self):
        """导出行程数据"""
        QMessageBox.information(self, "导出数据", "导出行程数据功能待实现")
