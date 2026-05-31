#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
司机管理模块
提供司机信息的增删改查功能
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
                               QDateEdit, QMessageBox, QDialogButtonBox)

class DriverManager(QObject):
    """司机管理器"""
    
    # 信号定义
    driver_added = Signal(str)           # 司机ID
    driver_updated = Signal(str)         # 司机ID
    driver_deleted = Signal(str)         # 司机ID
    driver_selected = Signal(str)        # 司机ID
    error_occurred = Signal(str)          # 错误信息
    
    def __init__(self, data_path: str = "data/drivers"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.data_path = data_path
        self.drivers = {}  # {driver_id: driver_data}
        
        # 确保数据目录存在
        self._ensure_data_dir()
        
        # 加载司机数据
        self._load_drivers()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            self.logger.info(f"司机数据目录已初始化: {self.data_path}")
        except Exception as e:
            self.logger.error(f"初始化司机数据目录失败: {e}")
            raise
    
    def _load_drivers(self):
        """加载司机数据"""
        try:
            drivers_file = os.path.join(self.data_path, "drivers.json")
            if os.path.exists(drivers_file):
                with open(drivers_file, 'r', encoding='utf-8') as f:
                    self.drivers = json.load(f)
                self.logger.info(f"已加载 {len(self.drivers)} 名司机")
            else:
                self.logger.info("司机数据文件不存在，创建空数据")
                self.drivers = {}
        except Exception as e:
            self.logger.error(f"加载司机数据失败: {e}")
            self.drivers = {}
    
    def _save_drivers(self):
        """保存司机数据"""
        try:
            drivers_file = os.path.join(self.data_path, "drivers.json")
            with open(drivers_file, 'w', encoding='utf-8') as f:
                json.dump(self.drivers, f, indent=2, ensure_ascii=False)
            self.logger.info("司机数据已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存司机数据失败: {e}")
            return False
    
    def add_driver(self, driver_data: Dict[str, Any]) -> Optional[str]:
        """添加司机"""
        try:
            # 生成司机ID
            driver_id = f"D{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 添加创建时间
            driver_data['id'] = driver_id
            driver_data['created_at'] = datetime.now().isoformat()
            driver_data['updated_at'] = driver_data['created_at']
            
            # 保存司机信息
            self.drivers[driver_id] = driver_data
            
            # 保存到文件
            if self._save_drivers():
                self.driver_added.emit(driver_id)
                self.logger.info(f"司机添加成功: {driver_id}")
                return driver_id
            else:
                # 保存失败，回滚
                del self.drivers[driver_id]
                return None
        except Exception as e:
            self.logger.error(f"添加司机失败: {e}")
            self.error_occurred.emit(f"添加司机失败: {e}")
            return None
    
    def update_driver(self, driver_id: str, driver_data: Dict[str, Any]) -> bool:
        """更新司机信息"""
        try:
            if driver_id not in self.drivers:
                self.logger.error(f"司机不存在: {driver_id}")
                return False
            
            # 更新数据
            old_data = self.drivers[driver_id].copy()
            self.drivers[driver_id].update(driver_data)
            self.drivers[driver_id]['updated_at'] = datetime.now().isoformat()
            
            # 保存到文件
            if self._save_drivers():
                self.driver_updated.emit(driver_id)
                self.logger.info(f"司机更新成功: {driver_id}")
                return True
            else:
                # 保存失败，回滚
                self.drivers[driver_id] = old_data
                return False
        except Exception as e:
            self.logger.error(f"更新司机失败: {e}")
            self.error_occurred.emit(f"更新司机失败: {e}")
            return False
    
    def delete_driver(self, driver_id: str) -> bool:
        """删除司机"""
        try:
            if driver_id not in self.drivers:
                self.logger.error(f"司机不存在: {driver_id}")
                return False
            
            # 删除司机
            del self.drivers[driver_id]
            
            # 保存到文件
            if self._save_drivers():
                self.driver_deleted.emit(driver_id)
                self.logger.info(f"司机删除成功: {driver_id}")
                return True
            else:
                # 保存失败，回滚
                self.drivers[driver_id] = self.drivers.get(driver_id, {})
                return False
        except Exception as e:
            self.logger.error(f"删除司机失败: {e}")
            self.error_occurred.emit(f"删除司机失败: {e}")
            return False
    
    def get_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """获取司机信息"""
        return self.drivers.get(driver_id)
    
    def get_all_drivers(self) -> Dict[str, Dict[str, Any]]:
        """获取所有司机"""
        return self.drivers.copy()
    
    def search_drivers(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """搜索司机"""
        results = []
        for driver_id, driver_data in self.drivers.items():
            match = True
            for key, value in criteria.items():
                if key in driver_data:
                    if isinstance(value, str) and value.lower() not in str(driver_data[key]).lower():
                        match = False
                        break
                    elif driver_data[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                results.append({**driver_data, 'id': driver_id})
        
        return results
    
    def get_driver_count(self) -> int:
        """获取司机总数"""
        return len(self.drivers)
    
    def get_drivers_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取司机"""
        return [d for d in self.drivers.values() if d.get('status') == status]
    
    def get_drivers_by_license_type(self, license_type: str) -> List[Dict[str, Any]]:
        """根据驾照类型获取司机"""
        return [d for d in self.drivers.values() if d.get('license_type') == license_type]


class DriverManagementDialog(QDialog):
    """司机管理对话框"""
    
    def __init__(self, driver_manager: DriverManager, parent=None):
        super().__init__(parent)
        self.driver_manager = driver_manager
        self.current_driver_id = None
        self.init_ui()
        self.load_drivers()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("司机管理")
        self.setGeometry(100, 100, 900, 600)
        
        layout = QVBoxLayout(self)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 添加司机")
        self.edit_btn = QPushButton("✏️ 编辑司机")
        self.delete_btn = QPushButton("🗑️ 删除司机")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        self.add_btn.clicked.connect(self.add_driver)
        self.edit_btn.clicked.connect(self.edit_driver)
        self.delete_btn.clicked.connect(self.delete_driver)
        self.refresh_btn.clicked.connect(self.load_drivers)
        
        control_layout.addWidget(self.add_btn)
        control_layout.addWidget(self.edit_btn)
        control_layout.addWidget(self.delete_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 司机列表
        self.driver_table = QTableWidget()
        self.driver_table.setColumnCount(9)
        self.driver_table.setHorizontalHeaderLabels([
            "司机ID", "姓名", "驾照号", "驾照类型", "入职日期", "性别", "状态", "行为评分", "最后更新"
        ])
        self.driver_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.driver_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.driver_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.driver_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 连接信号
        self.driver_manager.driver_added.connect(self.on_driver_added)
        self.driver_manager.driver_updated.connect(self.on_driver_updated)
        self.driver_manager.driver_deleted.connect(self.on_driver_deleted)
        self.driver_manager.error_occurred.connect(self.on_error)
    
    def load_drivers(self):
        """加载司机列表"""
        try:
            drivers = self.driver_manager.get_all_drivers()
            self.driver_table.setRowCount(len(drivers))
            
            for row, (driver_id, driver_data) in enumerate(drivers.items()):
                self.driver_table.setItem(row, 0, QTableWidgetItem(driver_id))
                self.driver_table.setItem(row, 1, QTableWidgetItem(driver_data.get('name', '')))
                self.driver_table.setItem(row, 2, QTableWidgetItem(driver_data.get('license_number', '')))
                self.driver_table.setItem(row, 3, QTableWidgetItem(driver_data.get('license_type', '')))
                self.driver_table.setItem(row, 4, QTableWidgetItem(driver_data.get('hire_date', '')))
                self.driver_table.setItem(row, 5, QTableWidgetItem(driver_data.get('gender', '')))
                self.driver_table.setItem(row, 6, QTableWidgetItem(driver_data.get('status', '')))
                self.driver_table.setItem(row, 7, QTableWidgetItem(str(driver_data.get('behavior_score', ''))))
                self.driver_table.setItem(row, 8, QTableWidgetItem(driver_data.get('updated_at', '')))
            
            self.status_label.setText(f"已加载 {len(drivers)} 名司机")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
    
    def add_driver(self):
        """添加司机"""
        dialog = DriverEditDialog(self.driver_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_drivers()
    
    def edit_driver(self):
        """编辑司机"""
        if not self.current_driver_id:
            QMessageBox.warning(self, "警告", "请先选择一名司机")
            return
        
        driver_data = self.driver_manager.get_driver(self.current_driver_id)
        if driver_data:
            dialog = DriverEditDialog(self.driver_manager, driver_data, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_drivers()
    
    def delete_driver(self):
        """删除司机"""
        if not self.current_driver_id:
            QMessageBox.warning(self, "警告", "请先选择一名司机")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除司机 {self.current_driver_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.driver_manager.delete_driver(self.current_driver_id):
                self.current_driver_id = None
                self.load_drivers()
    
    def on_selection_changed(self):
        """选择变化处理"""
        current_row = self.driver_table.currentRow()
        if current_row >= 0:
            self.current_driver_id = self.driver_table.item(current_row, 0).text()
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.current_driver_id = None
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def on_driver_added(self, driver_id: str):
        """司机添加事件"""
        self.status_label.setText(f"司机 {driver_id} 添加成功")
    
    def on_driver_updated(self, driver_id: str):
        """司机更新事件"""
        self.status_label.setText(f"司机 {driver_id} 更新成功")
    
    def on_driver_deleted(self, driver_id: str):
        """司机删除事件"""
        self.status_label.setText(f"司机 {driver_id} 删除成功")
    
    def on_error(self, error_msg: str):
        """错误事件"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)


class DriverEditDialog(QDialog):
    """司机编辑对话框"""
    
    def __init__(self, driver_manager: DriverManager, driver_data: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.driver_manager = driver_manager
        self.driver_data = driver_data or {}
        self.is_edit_mode = bool(driver_data)
        self.init_ui()
        self.load_driver_data()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("编辑司机" if self.is_edit_mode else "添加司机")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.license_number_edit = QLineEdit()
        self.license_type_combo = QComboBox()
        self.license_type_combo.addItems(["A1", "A2", "A3", "B1", "B2", "C1", "C2", "D", "E", "F", "M", "N", "P"])
        
        self.hire_date_edit = QDateEdit()
        self.hire_date_edit.setCalendarPopup(True)
        self.hire_date_edit.setDate(date.today())
        
        self.birth_date_edit = QDateEdit()
        self.birth_date_edit.setCalendarPopup(True)
        self.birth_date_edit.setDate(date(1990, 1, 1))
        
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["male", "female", ""])
        
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.address_edit = QTextEdit()
        self.address_edit.setMaximumHeight(80)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "suspended", "inactive"])
        
        self.behavior_score_spin = QDoubleSpinBox()
        self.behavior_score_spin.setRange(0.0, 100.0)
        self.behavior_score_spin.setValue(100.0)
        self.behavior_score_spin.setSuffix(" 分")
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        
        form_layout.addRow("姓名:", self.name_edit)
        form_layout.addRow("驾照号:", self.license_number_edit)
        form_layout.addRow("驾照类型:", self.license_type_combo)
        form_layout.addRow("入职日期:", self.hire_date_edit)
        form_layout.addRow("出生日期:", self.birth_date_edit)
        form_layout.addRow("性别:", self.gender_combo)
        form_layout.addRow("电话:", self.phone_edit)
        form_layout.addRow("邮箱:", self.email_edit)
        form_layout.addRow("地址:", self.address_edit)
        form_layout.addRow("状态:", self.status_combo)
        form_layout.addRow("行为评分:", self.behavior_score_spin)
        form_layout.addRow("备注:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_driver_data(self):
        """加载司机数据"""
        if self.driver_data:
            self.name_edit.setText(self.driver_data.get('name', ''))
            self.license_number_edit.setText(self.driver_data.get('license_number', ''))
            self.license_type_combo.setCurrentText(self.driver_data.get('license_type', 'C1'))
            
            # 处理日期
            hire_date = self.driver_data.get('hire_date', '')
            if hire_date:
                try:
                    if isinstance(hire_date, str):
                        hire_date = datetime.fromisoformat(hire_date).date()
                    self.hire_date_edit.setDate(hire_date)
                except:
                    pass
            
            birth_date = self.driver_data.get('birth_date', '')
            if birth_date:
                try:
                    if isinstance(birth_date, str):
                        birth_date = datetime.fromisoformat(birth_date).date()
                    self.birth_date_edit.setDate(birth_date)
                except:
                    pass
            
            self.gender_combo.setCurrentText(self.driver_data.get('gender', ''))
            self.phone_edit.setText(self.driver_data.get('phone', ''))
            self.email_edit.setText(self.driver_data.get('email', ''))
            self.address_edit.setPlainText(self.driver_data.get('address', ''))
            self.status_combo.setCurrentText(self.driver_data.get('status', 'active'))
            self.behavior_score_spin.setValue(self.driver_data.get('behavior_score', 100.0))
            self.notes_edit.setPlainText(self.driver_data.get('notes', ''))
    
    def accept(self):
        """确认保存"""
        try:
            # 收集数据
            driver_data = {
                'name': self.name_edit.text().strip(),
                'license_number': self.license_number_edit.text().strip(),
                'license_type': self.license_type_combo.currentText(),
                'hire_date': self.hire_date_edit.date().isoformat(),
                'birth_date': self.birth_date_edit.date().isoformat(),
                'gender': self.gender_combo.currentText(),
                'phone': self.phone_edit.text().strip(),
                'email': self.email_edit.text().strip(),
                'address': self.address_edit.toPlainText().strip(),
                'status': self.status_combo.currentText(),
                'behavior_score': self.behavior_score_spin.value(),
                'notes': self.notes_edit.toPlainText().strip()
            }
            
            # 验证必填字段
            if not driver_data['name']:
                QMessageBox.warning(self, "警告", "姓名不能为空")
                return
            
            if not driver_data['license_number']:
                QMessageBox.warning(self, "警告", "驾照号不能为空")
                return
            
            # 保存数据
            if self.is_edit_mode:
                # 编辑模式
                if self.driver_manager.update_driver(self.driver_data['id'], driver_data):
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "更新司机失败")
            else:
                # 添加模式
                driver_id = self.driver_manager.add_driver(driver_data)
                if driver_id:
                    super().accept()
                else:
                    QMessageBox.critical(self, "错误", "添加司机失败")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


# 全局实例
driver_manager = DriverManager()
