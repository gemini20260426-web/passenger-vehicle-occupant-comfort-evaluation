#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行程管理模块
提供行程信息的增删改查功能
"""

import logging
import json
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QLabel, QPushButton, QTextEdit, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
                               QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                               QDateEdit, QDateTimeEdit, QMessageBox, QDialogButtonBox)

class TripManager(QObject):
    """行程管理器"""
    
    # 信号定义
    trip_added = Signal(str)           # 行程ID
    trip_updated = Signal(str)         # 行程ID
    trip_deleted = Signal(str)         # 行程ID
    trip_selected = Signal(str)        # 行程ID
    error_occurred = Signal(str)          # 错误信息
    
    def __init__(self, data_path: str = "data/trips"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.data_path = data_path
        self.trips = {}  # {trip_id: trip_data}
        
        # 确保数据目录存在
        self._ensure_data_dir()
        
        # 加载行程数据
        self._load_trips()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            self.logger.info(f"行程数据目录已初始化: {self.data_path}")
        except Exception as e:
            self.logger.error(f"初始化行程数据目录失败: {e}")
            raise
    
    def _load_trips(self):
        """加载行程数据"""
        try:
            trips_file = os.path.join(self.data_path, "trips.json")
            if os.path.exists(trips_file):
                with open(trips_file, 'r', encoding='utf-8') as f:
                    self.trips = json.load(f)
                self.logger.info(f"已加载 {len(self.trips)} 个行程")
            else:
                self.logger.info("行程数据文件不存在，创建空数据")
                self.trips = {}
        except Exception as e:
            self.logger.error(f"加载行程数据失败: {e}")
            self.trips = {}
    
    def _save_trips(self):
        """保存行程数据"""
        try:
            trips_file = os.path.join(self.data_path, "trips.json")
            with open(trips_file, 'w', encoding='utf-8') as f:
                json.dump(self.trips, f, indent=2, ensure_ascii=False)
            self.logger.info("行程数据已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存行程数据失败: {e}")
            return False
    
    def add_trip(self, trip_data: Dict[str, Any]) -> Optional[str]:
        """添加行程"""
        try:
            # 生成行程ID
            trip_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 添加创建时间
            trip_data['id'] = trip_id
            trip_data['created_at'] = datetime.now().isoformat()
            trip_data['updated_at'] = trip_data['created_at']
            
            # 设置默认状态
            if 'status' not in trip_data:
                trip_data['status'] = 'in_progress'
            
            # 保存行程信息
            self.trips[trip_id] = trip_data
            
            # 保存到文件
            if self._save_trips():
                self.trip_added.emit(trip_id)
                self.logger.info(f"行程添加成功: {trip_id}")
                return trip_id
            else:
                # 保存失败，回滚
                del self.trips[trip_id]
                return None
        except Exception as e:
            self.logger.error(f"添加行程失败: {e}")
            self.error_occurred.emit(f"添加行程失败: {e}")
            return None
    
    def update_trip(self, trip_id: str, trip_data: Dict[str, Any]) -> bool:
        """更新行程信息"""
        try:
            if trip_id not in self.trips:
                self.logger.error(f"行程不存在: {trip_id}")
                return False
            
            # 更新数据
            old_data = self.trips[trip_id].copy()
            self.trips[trip_id].update(trip_data)
            self.trips[trip_id]['updated_at'] = datetime.now().isoformat()
            
            # 保存到文件
            if self._save_trips():
                self.trip_updated.emit(trip_id)
                self.logger.info(f"行程更新成功: {trip_id}")
                return True
            else:
                # 保存失败，回滚
                self.trips[trip_id] = old_data
                return False
        except Exception as e:
            self.logger.error(f"更新行程失败: {e}")
            self.error_occurred.emit(f"更新行程失败: {e}")
            return False
    
    def delete_trip(self, trip_id: str) -> bool:
        """删除行程"""
        try:
            if trip_id not in self.trips:
                self.logger.error(f"行程不存在: {trip_id}")
                return False
            
            # 删除行程
            del self.trips[trip_id]
            
            # 保存到文件
            if self._save_trips():
                self.trip_deleted.emit(trip_id)
                self.logger.info(f"行程删除成功: {trip_id}")
                return True
            else:
                # 保存失败，回滚
                self.trips[trip_id] = self.trips.get(trip_id, {})
                return False
        except Exception as e:
            self.logger.error(f"删除行程失败: {e}")
            self.error_occurred.emit(f"删除行程失败: {e}")
            return False
    
    def get_trip(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """获取行程信息"""
        return self.trips.get(trip_id)
    
    def get_all_trips(self) -> Dict[str, Dict[str, Any]]:
        """获取所有行程"""
        return self.trips.copy()
    
    def search_trips(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """搜索行程"""
        results = []
        for trip_id, trip_data in self.trips.items():
            match = True
            for key, value in criteria.items():
                if key in trip_data:
                    if isinstance(value, str) and value.lower() not in str(trip_data[key]).lower():
                        match = False
                        break
                    elif trip_data[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                results.append({**trip_data, 'id': trip_id})
        
        return results
    
    def get_trip_count(self) -> int:
        """获取行程总数"""
        return len(self.trips)
    
    def get_trips_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取行程"""
        return [t for t in self.trips.values() if t.get('status') == status]
    
    def get_trips_by_vehicle(self, vehicle_id: str) -> List[Dict[str, Any]]:
        """根据车辆ID获取行程"""
        return [t for t in self.trips.values() if t.get('vehicle_id') == vehicle_id]
    
    def get_trips_by_driver(self, driver_id: str) -> List[Dict[str, Any]]:
        """根据司机ID获取行程"""
        return [t for t in self.trips.values() if t.get('driver_id') == driver_id]
    
    def get_trips_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """根据日期范围获取行程"""
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            results = []
            for trip_data in self.trips.values():
                trip_start = trip_data.get('start_time')
                if trip_start:
                    try:
                        trip_start_dt = datetime.fromisoformat(trip_start)
                        if start_dt <= trip_start_dt <= end_dt:
                            results.append(trip_data)
                    except:
                        continue
            
            return results
        except Exception as e:
            self.logger.error(f"日期范围查询失败: {e}")
            return []
    
    def complete_trip(self, trip_id: str, end_time: str = None, distance: float = None, 
                     fuel_consumption: float = None, behavior_evaluation: Dict[str, Any] = None) -> bool:
        """完成行程"""
        try:
            if trip_id not in self.trips:
                self.logger.error(f"行程不存在: {trip_id}")
                return False
            
            update_data = {
                'status': 'completed',
                'end_time': end_time or datetime.now().isoformat()
            }
            
            if distance is not None:
                update_data['distance'] = distance
            
            if fuel_consumption is not None:
                update_data['fuel_consumption'] = fuel_consumption
            
            if behavior_evaluation is not None:
                update_data['behavior_evaluation'] = behavior_evaluation
            
            return self.update_trip(trip_id, update_data)
        
        except Exception as e:
            self.logger.error(f"完成行程失败: {e}")
            return False


class TripManagementDialog(QDialog):
    """行程管理对话框"""
    
    def __init__(self, trip_manager: TripManager, parent=None):
        super().__init__(parent)
        self.trip_manager = trip_manager
        self.current_trip_id = None
        self.init_ui()
        self.load_trips()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("行程管理")
        self.setGeometry(100, 100, 1000, 600)
        
        layout = QVBoxLayout(self)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 添加行程")
        self.edit_btn = QPushButton("✏️ 编辑行程")
        self.delete_btn = QPushButton("🗑️ 删除行程")
        self.complete_btn = QPushButton("✅ 完成行程")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        self.add_btn.clicked.connect(self.add_trip)
        self.edit_btn.clicked.connect(self.edit_trip)
        self.delete_btn.clicked.connect(self.delete_trip)
        self.complete_btn.clicked.connect(self.complete_trip)
        self.refresh_btn.clicked.connect(self.load_trips)
        
        control_layout.addWidget(self.add_btn)
        control_layout.addWidget(self.edit_btn)
        control_layout.addWidget(self.delete_btn)
        control_layout.addWidget(self.complete_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 行程列表
        self.trip_table = QTableWidget()
        self.trip_table.setColumnCount(10)
        self.trip_table.setHorizontalHeaderLabels([
            "行程ID", "车辆ID", "司机ID", "开始时间", "结束时间", "距离(km)", 
            "最大速度", "平均速度", "状态", "最后更新"
        ])
        self.trip_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trip_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.trip_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.trip_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 连接信号
        self.trip_manager.trip_added.connect(self.on_trip_added)
        self.trip_manager.trip_updated.connect(self.on_trip_updated)
        self.trip_manager.trip_deleted.connect(self.on_trip_deleted)
        self.trip_manager.error_occurred.connect(self.on_error)
    
    def load_trips(self):
        """加载行程列表"""
        try:
            trips = self.trip_manager.get_all_trips()
            self.trip_table.setRowCount(len(trips))
            
            for row, (trip_id, trip_data) in enumerate(trips.items()):
                self.trip_table.setItem(row, 0, QTableWidgetItem(trip_id))
                self.trip_table.setItem(row, 1, QTableWidgetItem(trip_data.get('vehicle_id', '')))
                self.trip_table.setItem(row, 2, QTableWidgetItem(trip_data.get('driver_id', '')))
                self.trip_table.setItem(row, 3, QTableWidgetItem(trip_data.get('start_time', '')))
                self.trip_table.setItem(row, 4, QTableWidgetItem(trip_data.get('end_time', '')))
                self.trip_table.setItem(row, 5, QTableWidgetItem(str(trip_data.get('distance', ''))))
                self.trip_table.setItem(row, 6, QTableWidgetItem(str(trip_data.get('max_speed', ''))))
                self.trip_table.setItem(row, 7, QTableWidgetItem(str(trip_data.get('avg_speed', ''))))
                self.trip_table.setItem(row, 8, QTableWidgetItem(trip_data.get('status', '')))
                self.trip_table.setItem(row, 9, QTableWidgetItem(trip_data.get('updated_at', '')))
            
            self.status_label.setText(f"已加载 {len(trips)} 个行程")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
    
    def add_trip(self):
        """添加行程"""
        dialog = TripEditDialog(self.trip_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_trips()
    
    def edit_trip(self):
        """编辑行程"""
        if not self.current_trip_id:
            QMessageBox.warning(self, "警告", "请先选择一个行程")
            return
        
        trip_data = self.trip_manager.get_trip(self.current_trip_id)
        if trip_data:
            dialog = TripEditDialog(self.trip_manager, trip_data, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_trips()
    
    def delete_trip(self):
        """删除行程"""
        if not self.current_trip_id:
            QMessageBox.warning(self, "警告", "请先选择一个行程")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除行程 {self.current_trip_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.trip_manager.delete_trip(self.current_trip_id):
                self.current_trip_id = None
                self.load_trips()
    
    def complete_trip(self):
        """完成行程"""
        if not self.current_trip_id:
            QMessageBox.warning(self, "警告", "请先选择一个行程")
            return
        
        trip_data = self.trip_manager.get_trip(self.current_trip_id)
        if trip_data and trip_data.get('status') == 'in_progress':
            if self.trip_manager.complete_trip(self.current_trip_id):
                QMessageBox.information(self, "成功", f"行程 {self.current_trip_id} 已完成")
                self.load_trips()
            else:
                QMessageBox.critical(self, "错误", "完成行程失败")
        else:
            QMessageBox.warning(self, "警告", "只能完成进行中的行程")
    
    def on_selection_changed(self):
        """选择变化处理"""
        current_row = self.trip_table.currentRow()
        if current_row >= 0:
            self.current_trip_id = self.trip_table.item(current_row, 0).text()
            trip_data = self.trip_manager.get_trip(self.current_trip_id)
            
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            
            # 只有进行中的行程才能完成
            if trip_data and trip_data.get('status') == 'in_progress':
                self.complete_btn.setEnabled(True)
            else:
                self.complete_btn.setEnabled(False)
        else:
            self.current_trip_id = None
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.complete_btn.setEnabled(False)
    
    def on_trip_added(self, trip_id: str):
        """行程添加事件"""
        self.status_label.setText(f"行程 {trip_id} 添加成功")
    
    def on_trip_updated(self, trip_id: str):
        """行程更新事件"""
        self.status_label.setText(f"行程 {trip_id} 更新成功")
    
    def on_trip_deleted(self, trip_id: str):
        """行程删除事件"""
        self.status_label.setText(f"行程 {trip_id} 删除成功")
    
    def on_error(self, error_msg: str):
        """错误事件"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)


class TripEditDialog(QDialog):
    """行程编辑对话框"""
    
    def __init__(self, trip_manager: TripManager, trip_data: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.trip_manager = trip_manager
        self.trip_data = trip_data or {}
        self.is_edit_mode = bool(trip_data)
        self.init_ui()
        self.load_trip_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑行程" if self.is_edit_mode else "添加行程")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        self.vehicle_id_edit = QLineEdit()
        self.driver_id_edit = QLineEdit()
        
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setDateTime(datetime.now())
        
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.setDateTime(datetime.now())
        
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.0, 10000.0)
        self.distance_spin.setSuffix(" km")
        
        self.max_speed_spin = QDoubleSpinBox()
        self.max_speed_spin.setRange(0.0, 200.0)
        self.max_speed_spin.setSuffix(" km/h")
        
        self.avg_speed_spin = QDoubleSpinBox()
        self.avg_speed_spin.setRange(0.0, 200.0)
        self.avg_speed_spin.setSuffix(" km/h")
        
        self.fuel_consumption_spin = QDoubleSpinBox()
        self.fuel_consumption_spin.setRange(0.0, 1000.0)
        self.fuel_consumption_spin.setSuffix(" L")
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["in_progress", "completed", "cancelled"])
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        
        form_layout.addRow("车辆ID:", self.vehicle_id_edit)
        form_layout.addRow("司机ID:", self.driver_id_edit)
        form_layout.addRow("开始时间:", self.start_time_edit)
        form_layout.addRow("结束时间:", self.end_time_edit)
        form_layout.addRow("距离:", self.distance_spin)
        form_layout.addRow("最大速度:", self.max_speed_spin)
        form_layout.addRow("平均速度:", self.avg_speed_spin)
        form_layout.addRow("油耗:", self.fuel_consumption_spin)
        form_layout.addRow("状态:", self.status_combo)
        form_layout.addRow("备注:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_trip_data(self):
        """加载行程数据"""
        if self.trip_data:
            self.vehicle_id_edit.setText(self.trip_data.get('vehicle_id', ''))
            self.driver_id_edit.setText(self.trip_data.get('driver_id', ''))
            
            # 处理时间
            start_time = self.trip_data.get('start_time', '')
            if start_time:
                try:
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time)
                    self.start_time_edit.setDateTime(start_time)
                except:
                    pass
            
            end_time = self.trip_data.get('end_time', '')
            if end_time:
                try:
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time)
                    self.end_time_edit.setDateTime(end_time)
                except:
                    pass
            
            self.distance_spin.setValue(self.trip_data.get('distance', 0.0))
            self.max_speed_spin.setValue(self.trip_data.get('max_speed', 0.0))
            self.avg_speed_spin.setValue(self.trip_data.get('avg_speed', 0.0))
            self.fuel_consumption_spin.setValue(self.trip_data.get('fuel_consumption', 0.0))
            self.status_combo.setCurrentText(self.trip_data.get('status', 'in_progress'))
            self.notes_edit.setPlainText(self.trip_data.get('notes', ''))
    
    def accept(self):
        """确认保存"""
        try:
            # 收集数据
            trip_data = {
                'vehicle_id': self.vehicle_id_edit.text().strip(),
                'driver_id': self.driver_id_edit.text().strip(),
                'start_time': self.start_time_edit.dateTime().toPython().isoformat(),
                'end_time': self.end_time_edit.dateTime().toPython().isoformat(),
                'distance': self.distance_spin.value(),
                'max_speed': self.max_speed_spin.value(),
                'avg_speed': self.avg_speed_spin.value(),
                'fuel_consumption': self.fuel_consumption_spin.value(),
                'status': self.status_combo.currentText(),
                'notes': self.notes_edit.toPlainText().strip()
            }
            
            # 验证必填字段
            if not trip_data['vehicle_id']:
                QMessageBox.warning(self, "警告", "车辆ID不能为空")
                return
            
            if not trip_data['driver_id']:
                QMessageBox.warning(self, "警告", "司机ID不能为空")
                return
            
            # 保存数据
            if self.is_edit_mode:
                # 编辑模式
                if self.trip_manager.update_trip(self.trip_data['id'], trip_data):
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "更新行程失败")
            else:
                # 添加模式
                trip_id = self.trip_manager.add_trip(trip_data)
                if trip_id:
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "添加行程失败")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


# 全局实例
trip_manager = TripManager()
