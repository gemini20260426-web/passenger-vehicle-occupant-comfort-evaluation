#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车辆管理模块
提供车辆信息的增删改查功能
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QLabel, QPushButton, QTextEdit, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
                               QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                               QDateEdit, QMessageBox, QDialogButtonBox)

class VehicleManager(QObject):
    """车辆管理器"""
    
    # 信号定义
    vehicle_added = Signal(str)           # 车辆ID
    vehicle_updated = Signal(str)         # 车辆ID
    vehicle_deleted = Signal(str)         # 车辆ID
    vehicle_selected = Signal(str)        # 车辆ID
    error_occurred = Signal(str)          # 错误信息
    
    def __init__(self, data_path: str = "data/vehicles"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.data_path = data_path
        self.vehicles = {}  # {vehicle_id: vehicle_data}
        
        # 确保数据目录存在
        self._ensure_data_dir()
        
        # 加载车辆数据
        self._load_vehicles()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            self.logger.info(f"车辆数据目录已初始化: {self.data_path}")
        except Exception as e:
            self.logger.error(f"初始化车辆数据目录失败: {e}")
            raise
    
    def _load_vehicles(self):
        """加载车辆数据"""
        try:
            vehicles_file = os.path.join(self.data_path, "vehicles.json")
            if os.path.exists(vehicles_file):
                with open(vehicles_file, 'r', encoding='utf-8') as f:
                    self.vehicles = json.load(f)
                self.logger.info(f"已加载 {len(self.vehicles)} 辆车辆")
            else:
                self.logger.info("车辆数据文件不存在，创建空数据")
                self.vehicles = {}
        except Exception as e:
            self.logger.error(f"加载车辆数据失败: {e}")
            self.vehicles = {}
    
    def _save_vehicles(self):
        """保存车辆数据"""
        try:
            vehicles_file = os.path.join(self.data_path, "vehicles.json")
            with open(vehicles_file, 'w', encoding='utf-8') as f:
                json.dump(self.vehicles, f, indent=2, ensure_ascii=False)
            self.logger.info("车辆数据已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存车辆数据失败: {e}")
            return False
    
    def add_vehicle(self, vehicle_data: Dict[str, Any]) -> Optional[str]:
        """添加车辆"""
        try:
            # 生成车辆ID
            vehicle_id = f"V{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 添加创建时间
            vehicle_data['id'] = vehicle_id
            vehicle_data['created_at'] = datetime.now().isoformat()
            vehicle_data['updated_at'] = vehicle_data['created_at']
            
            # 保存车辆信息
            self.vehicles[vehicle_id] = vehicle_data
            
            # 保存到文件
            if self._save_vehicles():
                self.vehicle_added.emit(vehicle_id)
                self.logger.info(f"车辆添加成功: {vehicle_id}")
                return vehicle_id
            else:
                # 保存失败，回滚
                del self.vehicles[vehicle_id]
                return None
        except Exception as e:
            self.logger.error(f"添加车辆失败: {e}")
            self.error_occurred.emit(f"添加车辆失败: {e}")
            return None
    
    def update_vehicle(self, vehicle_id: str, vehicle_data: Dict[str, Any]) -> bool:
        """更新车辆信息"""
        try:
            if vehicle_id not in self.vehicles:
                self.logger.error(f"车辆不存在: {vehicle_id}")
                return False
            
            # 更新数据
            old_data = self.vehicles[vehicle_id].copy()
            self.vehicles[vehicle_id].update(vehicle_data)
            self.vehicles[vehicle_id]['updated_at'] = datetime.now().isoformat()
            
            # 保存到文件
            if self._save_vehicles():
                self.vehicle_updated.emit(vehicle_id)
                self.logger.info(f"车辆更新成功: {vehicle_id}")
                return True
            else:
                # 保存失败，回滚
                self.vehicles[vehicle_id] = old_data
                return False
        except Exception as e:
            self.logger.error(f"更新车辆失败: {e}")
            self.error_occurred.emit(f"更新车辆失败: {e}")
            return False
    
    def delete_vehicle(self, vehicle_id: str) -> bool:
        """删除车辆"""
        try:
            if vehicle_id not in self.vehicles:
                self.logger.error(f"车辆不存在: {vehicle_id}")
                return False
            
            # 删除车辆
            del self.vehicles[vehicle_id]
            
            # 保存到文件
            if self._save_vehicles():
                self.vehicle_deleted.emit(vehicle_id)
                self.logger.info(f"车辆删除成功: {vehicle_id}")
                return True
            else:
                # 保存失败，回滚
                self.vehicles[vehicle_id] = self.vehicles.get(vehicle_id, {})
                return False
        except Exception as e:
            self.logger.error(f"删除车辆失败: {e}")
            self.error_occurred.emit(f"删除车辆失败: {e}")
            return False
    
    def get_vehicle(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """获取车辆信息"""
        return self.vehicles.get(vehicle_id)
    
    def get_all_vehicles(self) -> Dict[str, Dict[str, Any]]:
        """获取所有车辆"""
        return self.vehicles.copy()
    
    def search_vehicles(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """搜索车辆"""
        results = []
        for vehicle_id, vehicle_data in self.vehicles.items():
            match = True
            for key, value in criteria.items():
                if key in vehicle_data:
                    if isinstance(value, str) and value.lower() not in str(vehicle_data[key]).lower():
                        match = False
                        break
                    elif vehicle_data[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                results.append({**vehicle_data, 'id': vehicle_id})
        
        return results
    
    def get_vehicle_count(self) -> int:
        """获取车辆总数"""
        return len(self.vehicles)
    
    def get_vehicles_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取车辆"""
        return [v for v in self.vehicles.values() if v.get('status') == status]


class VehicleManagementDialog(QDialog):
    """车辆管理对话框"""
    
    def __init__(self, vehicle_manager: VehicleManager, parent=None):
        super().__init__(parent)
        self.vehicle_manager = vehicle_manager
        self.current_vehicle_id = None
        self.init_ui()
        self.load_vehicles()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("车辆管理")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout(self)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 添加车辆")
        self.edit_btn = QPushButton("✏️ 编辑车辆")
        self.delete_btn = QPushButton("🗑️ 删除车辆")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        self.add_btn.clicked.connect(self.add_vehicle)
        self.edit_btn.clicked.connect(self.edit_vehicle)
        self.delete_btn.clicked.connect(self.delete_vehicle)
        self.refresh_btn.clicked.connect(self.load_vehicles)
        
        control_layout.addWidget(self.add_btn)
        control_layout.addWidget(self.edit_btn)
        control_layout.addWidget(self.delete_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 车辆列表
        self.vehicle_table = QTableWidget()
        self.vehicle_table.setColumnCount(8)
        self.vehicle_table.setHorizontalHeaderLabels([
            "车辆ID", "车牌号", "品牌", "型号", "年份", "状态", "司机", "最后更新"
        ])
        self.vehicle_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vehicle_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.vehicle_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.vehicle_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 连接信号
        self.vehicle_manager.vehicle_added.connect(self.on_vehicle_added)
        self.vehicle_manager.vehicle_updated.connect(self.on_vehicle_updated)
        self.vehicle_manager.vehicle_deleted.connect(self.on_vehicle_deleted)
        self.vehicle_manager.error_occurred.connect(self.on_error)
    
    def load_vehicles(self):
        """加载车辆列表"""
        try:
            vehicles = self.vehicle_manager.get_all_vehicles()
            self.vehicle_table.setRowCount(len(vehicles))
            
            for row, (vehicle_id, vehicle_data) in enumerate(vehicles.items()):
                self.vehicle_table.setItem(row, 0, QTableWidgetItem(vehicle_id))
                self.vehicle_table.setItem(row, 1, QTableWidgetItem(vehicle_data.get('license_plate', '')))
                self.vehicle_table.setItem(row, 2, QTableWidgetItem(vehicle_data.get('brand', '')))
                self.vehicle_table.setItem(row, 3, QTableWidgetItem(vehicle_data.get('model', '')))
                self.vehicle_table.setItem(row, 4, QTableWidgetItem(str(vehicle_data.get('year', ''))))
                self.vehicle_table.setItem(row, 5, QTableWidgetItem(vehicle_data.get('status', '')))
                self.vehicle_table.setItem(row, 6, QTableWidgetItem(vehicle_data.get('driver_name', '')))
                self.vehicle_table.setItem(row, 7, QTableWidgetItem(vehicle_data.get('updated_at', '')))
            
            self.status_label.setText(f"已加载 {len(vehicles)} 辆车辆")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
    
    def add_vehicle(self):
        """添加车辆"""
        dialog = VehicleEditDialog(self.vehicle_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_vehicles()
    
    def edit_vehicle(self):
        """编辑车辆"""
        if not self.current_vehicle_id:
            QMessageBox.warning(self, "警告", "请先选择一辆车辆")
            return
        
        vehicle_data = self.vehicle_manager.get_vehicle(self.current_vehicle_id)
        if vehicle_data:
            dialog = VehicleEditDialog(self.vehicle_manager, vehicle_data, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_vehicles()
    
    def delete_vehicle(self):
        """删除车辆"""
        if not self.current_vehicle_id:
            QMessageBox.warning(self, "警告", "请先选择一辆车辆")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除车辆 {self.current_vehicle_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.vehicle_manager.delete_vehicle(self.current_vehicle_id):
                self.current_vehicle_id = None
                self.load_vehicles()
    
    def on_selection_changed(self):
        """选择变化处理"""
        current_row = self.vehicle_table.currentRow()
        if current_row >= 0:
            self.current_vehicle_id = self.vehicle_table.item(current_row, 0).text()
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.current_vehicle_id = None
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def on_vehicle_added(self, vehicle_id: str):
        """车辆添加事件"""
        self.status_label.setText(f"车辆 {vehicle_id} 添加成功")
    
    def on_vehicle_updated(self, vehicle_id: str):
        """车辆更新事件"""
        self.status_label.setText(f"车辆 {vehicle_id} 更新成功")
    
    def on_vehicle_deleted(self, vehicle_id: str):
        """车辆删除事件"""
        self.status_label.setText(f"车辆 {vehicle_id} 删除成功")
    
    def on_error(self, error_msg: str):
        """错误事件"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)


class VehicleEditDialog(QDialog):
    """车辆编辑对话框"""
    
    def __init__(self, vehicle_manager: VehicleManager, vehicle_data: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.vehicle_manager = vehicle_manager
        self.vehicle_data = vehicle_data or {}
        self.is_edit_mode = bool(vehicle_data)
        self.init_ui()
        self.load_vehicle_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑车辆" if self.is_edit_mode else "添加车辆")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        self.license_plate_edit = QLineEdit()
        self.brand_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(2020)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "maintenance", "retired"])
        
        self.driver_name_edit = QLineEdit()
        self.vin_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        
        form_layout.addRow("车牌号:", self.license_plate_edit)
        form_layout.addRow("品牌:", self.brand_edit)
        form_layout.addRow("型号:", self.model_edit)
        form_layout.addRow("年份:", self.year_spin)
        form_layout.addRow("状态:", self.status_combo)
        form_layout.addRow("司机:", self.driver_name_edit)
        form_layout.addRow("VIN:", self.vin_edit)
        form_layout.addRow("备注:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_vehicle_data(self):
        """加载车辆数据"""
        if self.vehicle_data:
            self.license_plate_edit.setText(self.vehicle_data.get('license_plate', ''))
            self.brand_edit.setText(self.vehicle_data.get('brand', ''))
            self.model_edit.setText(self.vehicle_data.get('model', ''))
            self.year_spin.setValue(self.vehicle_data.get('year', 2020))
            self.status_combo.setCurrentText(self.vehicle_data.get('status', 'active'))
            self.driver_name_edit.setText(self.vehicle_data.get('driver_name', ''))
            self.vin_edit.setText(self.vehicle_data.get('vin', ''))
            self.notes_edit.setPlainText(self.vehicle_data.get('notes', ''))
    
    def accept(self):
        """确认保存"""
        try:
            # 收集数据
            vehicle_data = {
                'license_plate': self.license_plate_edit.text().strip(),
                'brand': self.brand_edit.text().strip(),
                'model': self.model_edit.text().strip(),
                'year': self.year_spin.value(),
                'status': self.status_combo.currentText(),
                'driver_name': self.driver_name_edit.text().strip(),
                'vin': self.vin_edit.text().strip(),
                'notes': self.notes_edit.toPlainText().strip()
            }
            
            # 验证必填字段
            if not vehicle_data['license_plate']:
                QMessageBox.warning(self, "警告", "车牌号不能为空")
                return
            
            if not vehicle_data['brand']:
                QMessageBox.warning(self, "警告", "品牌不能为空")
                return
            
            # 保存数据
            if self.is_edit_mode:
                # 编辑模式
                if self.vehicle_manager.update_vehicle(self.vehicle_data['id'], vehicle_data):
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "更新车辆失败")
            else:
                # 添加模式
                vehicle_id = self.vehicle_manager.add_vehicle(vehicle_data)
                if vehicle_id:
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "添加车辆失败")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


# 全局实例
vehicle_manager = VehicleManager()
