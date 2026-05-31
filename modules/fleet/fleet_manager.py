#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车队管理模块
提供车队信息的增删改查功能
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
                               QMessageBox, QDialogButtonBox, QListWidget)

class FleetManager(QObject):
    """车队管理器"""
    
    # 信号定义
    fleet_added = Signal(str)           # 车队ID
    fleet_updated = Signal(str)         # 车队ID
    fleet_deleted = Signal(str)         # 车队ID
    fleet_selected = Signal(str)        # 车队ID
    error_occurred = Signal(str)          # 错误信息
    
    def __init__(self, data_path: str = "data/fleets"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.data_path = data_path
        self.fleets = {}  # {fleet_id: fleet_data}
        
        # 确保数据目录存在
        self._ensure_data_dir()
        
        # 加载车队数据
        self._load_fleets()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            self.logger.info(f"车队数据目录已初始化: {self.data_path}")
        except Exception as e:
            self.logger.error(f"初始化车队数据目录失败: {e}")
            raise
    
    def _load_fleets(self):
        """加载车队数据"""
        try:
            fleets_file = os.path.join(self.data_path, "fleets.json")
            if os.path.exists(fleets_file):
                with open(fleets_file, 'r', encoding='utf-8') as f:
                    self.fleets = json.load(f)
                self.logger.info(f"已加载 {len(self.fleets)} 个车队")
            else:
                self.logger.info("车队数据文件不存在，创建空数据")
                self.fleets = {}
        except Exception as e:
            self.logger.error(f"加载车队数据失败: {e}")
            self.fleets = {}
    
    def _save_fleets(self):
        """保存车队数据"""
        try:
            fleets_file = os.path.join(self.data_path, "fleets.json")
            with open(fleets_file, 'w', encoding='utf-8') as f:
                json.dump(self.fleets, f, indent=2, ensure_ascii=False)
            self.logger.info("车队数据已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存车队数据失败: {e}")
            return False
    
    def add_fleet(self, fleet_data: Dict[str, Any]) -> Optional[str]:
        """添加车队"""
        try:
            # 生成车队ID
            fleet_id = f"F{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 添加创建时间
            fleet_data['id'] = fleet_id
            fleet_data['created_at'] = datetime.now().isoformat()
            fleet_data['updated_at'] = fleet_data['created_at']
            
            # 确保vehicle_ids是列表
            if 'vehicle_ids' not in fleet_data:
                fleet_data['vehicle_ids'] = []
            
            # 保存车队信息
            self.fleets[fleet_id] = fleet_data
            
            # 保存到文件
            if self._save_fleets():
                self.fleet_added.emit(fleet_id)
                self.logger.info(f"车队添加成功: {fleet_id}")
                return fleet_id
            else:
                # 保存失败，回滚
                del self.fleets[fleet_id]
                return None
        except Exception as e:
            self.logger.error(f"添加车队失败: {e}")
            self.error_occurred.emit(f"添加车队失败: {e}")
            return None
    
    def update_fleet(self, fleet_id: str, fleet_data: Dict[str, Any]) -> bool:
        """更新车队信息"""
        try:
            if fleet_id not in self.fleets:
                self.logger.error(f"车队不存在: {fleet_id}")
                return False
            
            # 更新数据
            old_data = self.fleets[fleet_id].copy()
            self.fleets[fleet_id].update(fleet_data)
            self.fleets[fleet_id]['updated_at'] = datetime.now().isoformat()
            
            # 保存到文件
            if self._save_fleets():
                self.fleet_updated.emit(fleet_id)
                self.logger.info(f"车队更新成功: {fleet_id}")
                return True
            else:
                # 保存失败，回滚
                self.fleets[fleet_id] = old_data
                return False
        except Exception as e:
            self.logger.error(f"更新车队失败: {e}")
            self.error_occurred.emit(f"更新车队失败: {e}")
            return False
    
    def delete_fleet(self, fleet_id: str) -> bool:
        """删除车队"""
        try:
            if fleet_id not in self.fleets:
                self.logger.error(f"车队不存在: {fleet_id}")
                return False
            
            # 删除车队
            del self.fleets[fleet_id]
            
            # 保存到文件
            if self._save_fleets():
                self.fleet_deleted.emit(fleet_id)
                self.logger.info(f"车队删除成功: {fleet_id}")
                return True
            else:
                # 保存失败，回滚
                self.fleets[fleet_id] = self.fleets.get(fleet_id, {})
                return False
        except Exception as e:
            self.logger.error(f"删除车队失败: {e}")
            self.error_occurred.emit(f"删除车队失败: {e}")
            return False
    
    def get_fleet(self, fleet_id: str) -> Optional[Dict[str, Any]]:
        """获取车队信息"""
        return self.fleets.get(fleet_id)
    
    def get_all_fleets(self) -> Dict[str, Dict[str, Any]]:
        """获取所有车队"""
        return self.fleets.copy()
    
    def search_fleets(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """搜索车队"""
        results = []
        for fleet_id, fleet_data in self.fleets.items():
            match = True
            for key, value in criteria.items():
                if key in fleet_data:
                    if isinstance(value, str) and value.lower() not in str(fleet_data[key]).lower():
                        match = False
                        break
                    elif fleet_data[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                results.append({**fleet_data, 'id': fleet_id})
        
        return results
    
    def get_fleet_count(self) -> int:
        """获取车队总数"""
        return len(self.fleets)
    
    def add_vehicle_to_fleet(self, fleet_id: str, vehicle_id: str) -> bool:
        """向车队添加车辆"""
        try:
            if fleet_id not in self.fleets:
                self.logger.error(f"车队不存在: {fleet_id}")
                return False
            
            if 'vehicle_ids' not in self.fleets[fleet_id]:
                self.fleets[fleet_id]['vehicle_ids'] = []
            
            if vehicle_id not in self.fleets[fleet_id]['vehicle_ids']:
                self.fleets[fleet_id]['vehicle_ids'].append(vehicle_id)
                self.fleets[fleet_id]['updated_at'] = datetime.now().isoformat()
                
                if self._save_fleets():
                    self.logger.info(f"车辆 {vehicle_id} 已添加到车队 {fleet_id}")
                    return True
                else:
                    # 保存失败，回滚
                    self.fleets[fleet_id]['vehicle_ids'].remove(vehicle_id)
                    return False
            else:
                self.logger.info(f"车辆 {vehicle_id} 已在车队 {fleet_id} 中")
                return True
        except Exception as e:
            self.logger.error(f"向车队添加车辆失败: {e}")
            return False
    
    def remove_vehicle_from_fleet(self, fleet_id: str, vehicle_id: str) -> bool:
        """从车队移除车辆"""
        try:
            if fleet_id not in self.fleets:
                self.logger.error(f"车队不存在: {fleet_id}")
                return False
            
            if 'vehicle_ids' in self.fleets[fleet_id] and vehicle_id in self.fleets[fleet_id]['vehicle_ids']:
                self.fleets[fleet_id]['vehicle_ids'].remove(vehicle_id)
                self.fleets[fleet_id]['updated_at'] = datetime.now().isoformat()
                
                if self._save_fleets():
                    self.logger.info(f"车辆 {vehicle_id} 已从车队 {fleet_id} 移除")
                    return True
                else:
                    # 保存失败，回滚
                    self.fleets[fleet_id]['vehicle_ids'].append(vehicle_id)
                    return False
            else:
                self.logger.info(f"车辆 {vehicle_id} 不在车队 {fleet_id} 中")
                return True
        except Exception as e:
            self.logger.error(f"从车队移除车辆失败: {e}")
            return False
    
    def get_fleet_vehicles(self, fleet_id: str) -> List[str]:
        """获取车队中的车辆列表"""
        if fleet_id in self.fleets:
            return self.fleets[fleet_id].get('vehicle_ids', [])
        return []


class FleetManagementDialog(QDialog):
    """车队管理对话框"""
    
    def __init__(self, fleet_manager: FleetManager, parent=None):
        super().__init__(parent)
        self.fleet_manager = fleet_manager
        self.current_fleet_id = None
        self.init_ui()
        self.load_fleets()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("车队管理")
        self.setGeometry(100, 100, 900, 600)
        
        layout = QVBoxLayout(self)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 添加车队")
        self.edit_btn = QPushButton("✏️ 编辑车队")
        self.delete_btn = QPushButton("🗑️ 删除车队")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        self.add_btn.clicked.connect(self.add_fleet)
        self.edit_btn.clicked.connect(self.edit_fleet)
        self.delete_btn.clicked.connect(self.delete_fleet)
        self.refresh_btn.clicked.connect(self.load_fleets)
        
        control_layout.addWidget(self.add_btn)
        control_layout.addWidget(self.edit_btn)
        control_layout.addWidget(self.delete_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 车队列表
        self.fleet_table = QTableWidget()
        self.fleet_table.setColumnCount(7)
        self.fleet_table.setHorizontalHeaderLabels([
            "车队ID", "名称", "描述", "管理员", "联系方式", "车辆数量", "最后更新"
        ])
        self.fleet_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.fleet_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.fleet_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.fleet_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 连接信号
        self.fleet_manager.fleet_added.connect(self.on_fleet_added)
        self.fleet_manager.fleet_updated.connect(self.on_fleet_updated)
        self.fleet_manager.fleet_deleted.connect(self.on_fleet_deleted)
        self.fleet_manager.error_occurred.connect(self.on_error)
    
    def load_fleets(self):
        """加载车队列表"""
        try:
            fleets = self.fleet_manager.get_all_fleets()
            self.fleet_table.setRowCount(len(fleets))
            
            for row, (fleet_id, fleet_data) in enumerate(fleets.items()):
                self.fleet_table.setItem(row, 0, QTableWidgetItem(fleet_id))
                self.fleet_table.setItem(row, 1, QTableWidgetItem(fleet_data.get('name', '')))
                self.fleet_table.setItem(row, 2, QTableWidgetItem(fleet_data.get('description', '')))
                self.fleet_table.setItem(row, 3, QTableWidgetItem(fleet_data.get('manager', '')))
                self.fleet_table.setItem(row, 4, QTableWidgetItem(fleet_data.get('contact', '')))
                
                vehicle_count = len(fleet_data.get('vehicle_ids', []))
                self.fleet_table.setItem(row, 5, QTableWidgetItem(str(vehicle_count)))
                
                self.fleet_table.setItem(row, 6, QTableWidgetItem(fleet_data.get('updated_at', '')))
            
            self.status_label.setText(f"已加载 {len(fleets)} 个车队")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
    
    def add_fleet(self):
        """添加车队"""
        dialog = FleetEditDialog(self.fleet_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_fleets()
    
    def edit_fleet(self):
        """编辑车队"""
        if not self.current_fleet_id:
            QMessageBox.warning(self, "警告", "请先选择一个车队")
            return
        
        fleet_data = self.fleet_manager.get_fleet(self.current_fleet_id)
        if fleet_data:
            dialog = FleetEditDialog(self.fleet_manager, fleet_data, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_fleets()
    
    def delete_fleet(self):
        """删除车队"""
        if not self.current_fleet_id:
            QMessageBox.warning(self, "警告", "请先选择一个车队")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除车队 {self.current_fleet_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.fleet_manager.delete_fleet(self.current_fleet_id):
                self.current_fleet_id = None
                self.load_fleets()
    
    def on_selection_changed(self):
        """选择变化处理"""
        current_row = self.fleet_table.currentRow()
        if current_row >= 0:
            self.current_fleet_id = self.fleet_table.item(current_row, 0).text()
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.current_fleet_id = None
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def on_fleet_added(self, fleet_id: str):
        """车队添加事件"""
        self.status_label.setText(f"车队 {fleet_id} 添加成功")
    
    def on_fleet_updated(self, fleet_id: str):
        """车队更新事件"""
        self.status_label.setText(f"车队 {fleet_id} 更新成功")
    
    def on_fleet_deleted(self, fleet_id: str):
        """车队删除事件"""
        self.status_label.setText(f"车队 {fleet_id} 删除成功")
    
    def on_error(self, error_msg: str):
        """错误事件"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)


class FleetEditDialog(QDialog):
    """车队编辑对话框"""
    
    def __init__(self, fleet_manager: FleetManager, fleet_data: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.fleet_manager = fleet_manager
        self.fleet_data = fleet_data or {}
        self.is_edit_mode = bool(fleet_data)
        self.init_ui()
        self.load_fleet_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑车队" if self.is_edit_mode else "添加车队")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        
        self.manager_edit = QLineEdit()
        self.contact_edit = QLineEdit()
        
        # 车辆ID列表
        self.vehicle_ids_edit = QTextEdit()
        self.vehicle_ids_edit.setMaximumHeight(80)
        self.vehicle_ids_edit.setPlaceholderText("每行一个车辆ID")
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        
        form_layout.addRow("车队名称:", self.name_edit)
        form_layout.addRow("描述:", self.description_edit)
        form_layout.addRow("管理员:", self.manager_edit)
        form_layout.addRow("联系方式:", self.contact_edit)
        form_layout.addRow("车辆ID列表:", self.vehicle_ids_edit)
        form_layout.addRow("备注:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_fleet_data(self):
        """加载车队数据"""
        if self.fleet_data:
            self.name_edit.setText(self.fleet_data.get('name', ''))
            self.description_edit.setPlainText(self.fleet_data.get('description', ''))
            self.manager_edit.setText(self.fleet_data.get('manager', ''))
            self.contact_edit.setText(self.fleet_data.get('contact', ''))
            
            # 处理车辆ID列表
            vehicle_ids = self.fleet_data.get('vehicle_ids', [])
            if vehicle_ids:
                self.vehicle_ids_edit.setPlainText('\n'.join(vehicle_ids))
            
            self.notes_edit.setPlainText(self.fleet_data.get('notes', ''))
    
    def accept(self):
        """确认保存"""
        try:
            # 收集数据
            fleet_data = {
                'name': self.name_edit.text().strip(),
                'description': self.description_edit.toPlainText().strip(),
                'manager': self.manager_edit.text().strip(),
                'contact': self.contact_edit.text().strip(),
                'notes': self.notes_edit.toPlainText().strip()
            }
            
            # 处理车辆ID列表
            vehicle_ids_text = self.vehicle_ids_edit.toPlainText().strip()
            if vehicle_ids_text:
                vehicle_ids = [vid.strip() for vid in vehicle_ids_text.split('\n') if vid.strip()]
                fleet_data['vehicle_ids'] = vehicle_ids
            else:
                fleet_data['vehicle_ids'] = []
            
            # 验证必填字段
            if not fleet_data['name']:
                QMessageBox.warning(self, "警告", "车队名称不能为空")
                return
            
            # 保存数据
            if self.is_edit_mode:
                # 编辑模式
                if self.fleet_manager.update_fleet(self.fleet_data['id'], fleet_data):
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "更新车队失败")
            else:
                # 添加模式
                fleet_id = self.fleet_manager.add_fleet(fleet_data)
                if fleet_id:
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "添加车队失败")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


# 全局实例
fleet_manager = FleetManager()
