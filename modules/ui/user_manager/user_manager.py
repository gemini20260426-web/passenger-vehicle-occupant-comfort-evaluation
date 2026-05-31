#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理模块
提供完整的用户管理功能，包括用户信息管理、用户偏好设置、用户活动记录等
"""

import os
import sys
import json
import logging
import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# PySide6 imports
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QTextEdit, QTabWidget,
    QScrollArea, QMessageBox, QFileDialog, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QDateEdit, QTimeEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject, QDate, QTime
from PySide6.QtGui import QFont, QIcon, QAction


class UserManager(QObject):
    """用户管理器核心类"""
    
    # 信号定义
    user_created = Signal(str)
    user_updated = Signal(str)
    user_deleted = Signal(str)
    user_preferences_changed = Signal(str, str, str)  # username, key, value
    
    def __init__(self, user_file: str = None):
        super().__init__()
        self.user_file = user_file or "config/users.json"
        self.users = {}
        self.user_preferences = {}
        self.user_activities = {}
        self.logger = logging.getLogger(__name__)
        
        # 加载用户配置
        self.load_user_config()
        self.create_default_users()
    
    def load_user_config(self):
        """加载用户配置文件"""
        try:
            if os.path.exists(self.user_file):
                with open(self.user_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
                    self.user_preferences = data.get('preferences', {})
                    self.user_activities = data.get('activities', {})
                self.logger.info(f"用户配置文件加载成功: {self.user_file}")
            else:
                self.logger.warning(f"用户配置文件不存在: {self.user_file}")
        except Exception as e:
            self.logger.error(f"加载用户配置文件失败: {e}")
    
    def save_user_config(self):
        """保存用户配置文件"""
        try:
            os.makedirs(os.path.dirname(self.user_file), exist_ok=True)
            data = {
                'users': self.users,
                'preferences': self.user_preferences,
                'activities': self.user_activities
            }
            with open(self.user_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"用户配置文件保存成功: {self.user_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存用户配置文件失败: {e}")
            return False
    
    def create_default_users(self):
        """创建默认用户"""
        if not self.users:
            self.users = {
                'admin': {
                    'username': 'admin',
                    'full_name': '系统管理员',
                    'email': 'admin@example.com',
                    'phone': '',
                    'department': 'IT部门',
                    'position': '系统管理员',
                    'created_at': datetime.datetime.now().isoformat(),
                    'last_active': None,
                    'status': 'active',
                    'avatar': '',
                    'notes': '系统默认管理员账户'
                },
                'user1': {
                    'username': 'user1',
                    'full_name': '测试用户1',
                    'email': 'user1@example.com',
                    'phone': '13800138001',
                    'department': '测试部门',
                    'position': '测试工程师',
                    'created_at': datetime.datetime.now().isoformat(),
                    'last_active': None,
                    'status': 'active',
                    'avatar': '',
                    'notes': '测试用户账户'
                }
            }
            
            # 创建默认用户偏好设置
            self.user_preferences = {
                'admin': {
                    'theme': 'dark',
                    'language': 'zh_CN',
                    'font_size': '12',
                    'auto_save': True,
                    'notifications': True,
                    'timezone': 'Asia/Shanghai'
                },
                'user1': {
                    'theme': 'light',
                    'language': 'zh_CN',
                    'font_size': '14',
                    'auto_save': False,
                    'notifications': False,
                    'timezone': 'Asia/Shanghai'
                }
            }
            
            self.save_user_config()
    
    def add_user(self, user_data: Dict[str, Any]) -> bool:
        """添加用户"""
        username = user_data.get('username', '').strip()
        if not username:
            return False
        
        if username in self.users:
            return False
        
        # 设置默认值
        user_data['created_at'] = datetime.datetime.now().isoformat()
        user_data['last_active'] = None
        user_data['status'] = user_data.get('status', 'active')
        user_data['avatar'] = user_data.get('avatar', '')
        user_data['notes'] = user_data.get('notes', '')
        
        self.users[username] = user_data
        
        # 创建默认偏好设置
        self.user_preferences[username] = {
            'theme': 'light',
            'language': 'zh_CN',
            'font_size': '12',
            'auto_save': True,
            'notifications': True,
            'timezone': 'Asia/Shanghai'
        }
        
        self.logger.info(f"用户 {username} 已创建")
        self.user_created.emit(username)
        self.save_user_config()
        return True
    
    def update_user(self, username: str, **kwargs) -> bool:
        """更新用户信息"""
        if username not in self.users:
            return False
        
        for key, value in kwargs.items():
            if key in ['full_name', 'email', 'phone', 'department', 'position', 'status', 'avatar', 'notes']:
                self.users[username][key] = value
        
        self.logger.info(f"用户 {username} 信息已更新")
        self.user_updated.emit(username)
        self.save_user_config()
        return True
    
    def delete_user(self, username: str) -> bool:
        """删除用户"""
        if username not in self.users:
            return False
        
        if username == 'admin':
            return False  # 不能删除管理员
        
        del self.users[username]
        
        # 删除相关数据
        if username in self.user_preferences:
            del self.user_preferences[username]
        if username in self.user_activities:
            del self.user_activities[username]
        
        self.logger.info(f"用户 {username} 已删除")
        self.user_deleted.emit(username)
        self.save_user_config()
        return True
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        return self.users.get(username)
    
    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """获取所有用户"""
        return self.users.copy()
    
    def get_user_preferences(self, username: str) -> Dict[str, Any]:
        """获取用户偏好设置"""
        return self.user_preferences.get(username, {})
    
    def set_user_preferences(self, username: str, preferences: Dict[str, Any]) -> bool:
        """设置用户偏好"""
        if username not in self.users:
            return False
        
        if username not in self.user_preferences:
            self.user_preferences[username] = {}
        
        for key, value in preferences.items():
            self.user_preferences[username][key] = value
            self.user_preferences_changed.emit(username, key, str(value))
        
        self.save_user_config()
        return True
    
    def record_user_activity(self, username: str, activity_type: str, description: str):
        """记录用户活动"""
        if username not in self.user_activities:
            self.user_activities[username] = []
        
        activity = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': activity_type,
            'description': description
        }
        
        self.user_activities[username].append(activity)
        
        # 保留最近100条活动记录
        if len(self.user_activities[username]) > 100:
            self.user_activities[username] = self.user_activities[username][-100:]
        
        # 更新最后活动时间
        if username in self.users:
            self.users[username]['last_active'] = datetime.datetime.now().isoformat()
    
    def get_user_activities(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户活动记录"""
        if username in self.user_activities:
            return self.user_activities[username][-limit:]
        return []
    
    def get_users_summary(self) -> Dict[str, int]:
        """获取用户统计信息"""
        total_users = len(self.users)
        active_users = sum(1 for u in self.users.values() if u['status'] == 'active')
        inactive_users = total_users - active_users
        
        # 按部门统计
        departments = {}
        for user in self.users.values():
            dept = user.get('department', '未分配')
            departments[dept] = departments.get(dept, 0) + 1
        
        return {
            'total': total_users,
            'active': active_users,
            'inactive': inactive_users,
            'departments': departments
        }
    
    def search_users(self, query: str) -> List[str]:
        """搜索用户"""
        results = []
        query_lower = query.lower()
        
        for username, user_data in self.users.items():
            if (query_lower in username.lower() or
                query_lower in user_data.get('full_name', '').lower() or
                query_lower in user_data.get('email', '').lower() or
                query_lower in user_data.get('department', '').lower()):
                results.append(username)
        
        return results


class UserDialog(QDialog):
    """用户管理对话框"""
    
    def __init__(self, user_manager: UserManager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setup_ui()
        self.load_user_data()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("用户管理")
        self.setGeometry(100, 100, 1200, 800)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.add_user_btn = QPushButton("➕ 添加用户")
        self.edit_user_btn = QPushButton("✏️ 编辑用户")
        self.delete_user_btn = QPushButton("🗑️ 删除用户")
        self.view_preferences_btn = QPushButton("⚙️ 用户偏好")
        self.export_btn = QPushButton("📤 导出用户")
        self.import_btn = QPushButton("📥 导入用户")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        toolbar_layout.addWidget(self.add_user_btn)
        toolbar_layout.addWidget(self.edit_user_btn)
        toolbar_layout.addWidget(self.delete_user_btn)
        toolbar_layout.addWidget(self.view_preferences_btn)
        toolbar_layout.addWidget(self.export_btn)
        toolbar_layout.addWidget(self.import_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索用户:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入用户名、姓名、邮箱或部门进行搜索...")
        search_layout.addWidget(self.search_edit)
        main_layout.addLayout(search_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧用户列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 用户表格
        user_group = QGroupBox("用户列表")
        user_layout = QVBoxLayout(user_group)
        
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(7)
        self.user_table.setHorizontalHeaderLabels(['用户名', '姓名', '邮箱', '部门', '职位', '状态', '最后活动'])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        user_layout.addWidget(self.user_table)
        left_layout.addWidget(user_group)
        
        # 用户统计
        stats_group = QGroupBox("用户统计")
        stats_layout = QFormLayout(stats_group)
        
        self.total_users_label = QLabel("0")
        self.active_users_label = QLabel("0")
        self.inactive_users_label = QLabel("0")
        
        stats_layout.addRow("总用户数:", self.total_users_label)
        stats_layout.addRow("活跃用户:", self.active_users_label)
        stats_layout.addRow("非活跃用户:", self.inactive_users_label)
        
        left_layout.addWidget(stats_group)
        
        # 右侧用户详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 用户详情
        detail_group = QGroupBox("用户详情")
        detail_layout = QVBoxLayout(detail_group)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)
        
        right_layout.addWidget(detail_group)
        
        # 用户活动
        activity_group = QGroupBox("用户活动")
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_list = QListWidget()
        activity_layout.addWidget(self.activity_list)
        
        right_layout.addWidget(activity_group)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 600])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(self.status_label)
    
    def load_user_data(self):
        """加载用户数据"""
        self.load_users_table()
        self.update_user_stats()
        self.update_ui_state()
    
    def load_users_table(self):
        """加载用户表格"""
        self.user_table.setRowCount(0)
        users = self.user_manager.get_all_users()
        
        for row, (username, user_data) in enumerate(users.items()):
            self.user_table.insertRow(row)
            
            self.user_table.setItem(row, 0, QTableWidgetItem(username))
            self.user_table.setItem(row, 1, QTableWidgetItem(user_data.get('full_name', '')))
            self.user_table.setItem(row, 2, QTableWidgetItem(user_data.get('email', '')))
            self.user_table.setItem(row, 3, QTableWidgetItem(user_data.get('department', '')))
            self.user_table.setItem(row, 4, QTableWidgetItem(user_data.get('position', '')))
            self.user_table.setItem(row, 5, QTableWidgetItem(user_data.get('status', '')))
            
            last_active = user_data.get('last_active', '')
            if last_active:
                try:
                    dt = datetime.datetime.fromisoformat(last_active)
                    last_active = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            self.user_table.setItem(row, 6, QTableWidgetItem(last_active))
    
    def update_user_stats(self):
        """更新用户统计"""
        stats = self.user_manager.get_users_summary()
        self.total_users_label.setText(str(stats['total']))
        self.active_users_label.setText(str(stats['active']))
        self.inactive_users_label.setText(str(stats['inactive']))
    
    def update_ui_state(self):
        """更新UI状态"""
        has_selection = self.user_table.currentRow() >= 0
        self.edit_user_btn.setEnabled(has_selection)
        self.delete_user_btn.setEnabled(has_selection)
        self.view_preferences_btn.setEnabled(has_selection)
    
    def connect_signals(self):
        """连接信号"""
        self.add_user_btn.clicked.connect(self.show_add_user_dialog)
        self.edit_user_btn.clicked.connect(self.show_edit_user_dialog)
        self.delete_user_btn.clicked.connect(self.delete_user)
        self.view_preferences_btn.clicked.connect(self.show_preferences_dialog)
        self.export_btn.clicked.connect(self.export_users)
        self.import_btn.clicked.connect(self.import_users)
        self.refresh_btn.clicked.connect(self.load_user_data)
        
        self.search_edit.textChanged.connect(self.search_users)
        self.user_table.itemSelectionChanged.connect(self.on_user_selection_changed)
        
        # 用户管理器信号
        self.user_manager.user_created.connect(self.on_user_created)
        self.user_manager.user_updated.connect(self.on_user_updated)
        self.user_manager.user_deleted.connect(self.on_user_deleted)
    
    def search_users(self):
        """搜索用户"""
        query = self.search_edit.text().strip()
        if not query:
            self.load_users_table()
            return
        
        results = self.user_manager.search_users(query)
        self.user_table.setRowCount(0)
        
        for row, username in enumerate(results):
            user_data = self.user_manager.get_user(username)
            if user_data:
                self.user_table.insertRow(row)
                
                self.user_table.setItem(row, 0, QTableWidgetItem(username))
                self.user_table.setItem(row, 1, QTableWidgetItem(user_data.get('full_name', '')))
                self.user_table.setItem(row, 2, QTableWidgetItem(user_data.get('email', '')))
                self.user_table.setItem(row, 3, QTableWidgetItem(user_data.get('department', '')))
                self.user_table.setItem(row, 4, QTableWidgetItem(user_data.get('position', '')))
                self.user_table.setItem(row, 5, QTableWidgetItem(user_data.get('status', '')))
                
                last_active = user_data.get('last_active', '')
                if last_active:
                    try:
                        dt = datetime.datetime.fromisoformat(last_active)
                        last_active = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                self.user_table.setItem(row, 6, QTableWidgetItem(last_active))
    
    def on_user_selection_changed(self):
        """用户选择改变事件"""
        self.update_ui_state()
        self.load_user_details()
        self.load_user_activities()
    
    def load_user_details(self):
        """加载用户详情"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            user_data = self.user_manager.get_user(username)
            
            if user_data:
                details = f"""用户详细信息
                
用户名: {username}
姓名: {user_data.get('full_name', '')}
邮箱: {user_data.get('email', '')}
电话: {user_data.get('phone', '')}
部门: {user_data.get('department', '')}
职位: {user_data.get('position', '')}
状态: {user_data.get('status', '')}
创建时间: {user_data.get('created_at', '')}
最后活动: {user_data.get('last_active', '')}
备注: {user_data.get('notes', '')}
头像: {user_data.get('avatar', '')}"""
                
                self.detail_text.setText(details)
            else:
                self.detail_text.setText("用户信息加载失败")
        else:
            self.detail_text.setText("请选择用户查看详情")
    
    def load_user_activities(self):
        """加载用户活动"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            activities = self.user_manager.get_user_activities(username, 20)
            
            self.activity_list.clear()
            for activity in reversed(activities):
                timestamp = activity['timestamp']
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
                
                item_text = f"[{timestamp}] {activity['type']}: {activity['description']}"
                item = QListWidgetItem(item_text)
                self.activity_list.addItem(item)
        else:
            self.activity_list.clear()
    
    def show_add_user_dialog(self):
        """显示添加用户对话框"""
        dialog = UserEditDialog(self.user_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_user_data()
    
    def show_edit_user_dialog(self):
        """显示编辑用户对话框"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            dialog = UserEditDialog(self.user_manager, username=username, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_user_data()
        else:
            QMessageBox.warning(self, "警告", "请先选择要编辑的用户")
    
    def delete_user(self):
        """删除用户"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            
            if username == 'admin':
                QMessageBox.warning(self, "警告", "不能删除管理员账户")
                return
            
            reply = QMessageBox.question(
                self, "确认删除", 
                f"确定要删除用户 {username} 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.user_manager.delete_user(username):
                    QMessageBox.information(self, "成功", f"用户 {username} 已删除")
                    self.load_user_data()
                else:
                    QMessageBox.warning(self, "错误", "删除用户失败")
        else:
            QMessageBox.warning(self, "警告", "请先选择要删除的用户")
    
    def show_preferences_dialog(self):
        """显示用户偏好设置对话框"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            dialog = UserPreferencesDialog(self.user_manager, username, parent=self)
            dialog.exec()
    
    def export_users(self):
        """导出用户数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出用户数据", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                users_data = {
                    'users': self.user_manager.get_all_users(),
                    'preferences': self.user_manager.user_preferences,
                    'export_time': datetime.datetime.now().isoformat()
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(users_data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"用户数据已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def import_users(self):
        """导入用户数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入用户数据", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'users' in data:
                    # 这里可以实现导入逻辑，暂时只显示信息
                    QMessageBox.information(self, "信息", f"检测到 {len(data['users'])} 个用户")
                else:
                    QMessageBox.warning(self, "警告", "文件格式不正确")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def on_user_created(self, username: str):
        """用户创建事件"""
        self.status_label.setText(f"用户 {username} 已创建")
        self.load_user_data()
    
    def on_user_updated(self, username: str):
        """用户更新事件"""
        self.status_label.setText(f"用户 {username} 信息已更新")
        self.load_user_data()
    
    def on_user_deleted(self, username: str):
        """用户删除事件"""
        self.status_label.setText(f"用户 {username} 已删除")
        self.load_user_data()


class UserEditDialog(QDialog):
    """用户编辑对话框"""
    
    def __init__(self, user_manager: UserManager, username: str = None, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.username = username
        self.is_edit = username is not None
        self.setup_ui()
        self.load_user_data()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        title = "编辑用户" if self.is_edit else "添加用户"
        self.setWindowTitle(title)
        self.setFixedSize(400, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.full_name_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.department_edit = QLineEdit()
        self.position_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.avatar_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        
        # 填充状态选项
        self.status_combo.addItems(['active', 'inactive'])
        
        form_layout.addRow("用户名:", self.username_edit)
        form_layout.addRow("姓名:", self.full_name_edit)
        form_layout.addRow("邮箱:", self.email_edit)
        form_layout.addRow("电话:", self.phone_edit)
        form_layout.addRow("部门:", self.department_edit)
        form_layout.addRow("职位:", self.position_edit)
        form_layout.addRow("状态:", self.status_combo)
        form_layout.addRow("头像:", self.avatar_edit)
        form_layout.addRow("备注:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 设置字段状态
        if self.is_edit:
            self.username_edit.setEnabled(False)
    
    def load_user_data(self):
        """加载用户数据"""
        if self.is_edit and self.username in self.user_manager.users:
            user_data = self.user_manager.users[self.username]
            self.username_edit.setText(self.username)
            self.full_name_edit.setText(user_data.get('full_name', ''))
            self.email_edit.setText(user_data.get('email', ''))
            self.phone_edit.setText(user_data.get('phone', ''))
            self.department_edit.setText(user_data.get('department', ''))
            self.position_edit.setText(user_data.get('position', ''))
            self.status_combo.setCurrentText(user_data.get('status', 'active'))
            self.avatar_edit.setText(user_data.get('avatar', ''))
            self.notes_edit.setText(user_data.get('notes', ''))
    
    def connect_signals(self):
        """连接信号"""
        self.save_btn.clicked.connect(self.save_user)
        self.cancel_btn.clicked.connect(self.reject)
    
    def save_user(self):
        """保存用户"""
        username = self.username_edit.text().strip()
        full_name = self.full_name_edit.text().strip()
        email = self.email_edit.text().strip()
        phone = self.phone_edit.text().strip()
        department = self.department_edit.text().strip()
        position = self.position_edit.text().strip()
        status = self.status_combo.currentText()
        avatar = self.avatar_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()
        
        if not username:
            QMessageBox.warning(self, "警告", "请输入用户名")
            return
        
        if not full_name:
            QMessageBox.warning(self, "警告", "请输入姓名")
            return
        
        try:
            user_data = {
                'username': username,
                'full_name': full_name,
                'email': email,
                'phone': phone,
                'department': department,
                'position': position,
                'status': status,
                'avatar': avatar,
                'notes': notes
            }
            
            if self.is_edit:
                # 编辑用户
                if self.user_manager.update_user(username, **user_data):
                    QMessageBox.information(self, "成功", "用户信息已更新")
                    self.accept()
                else:
                    QMessageBox.warning(self, "错误", "更新用户信息失败")
            else:
                # 添加用户
                if self.user_manager.add_user(user_data):
                    QMessageBox.information(self, "成功", "用户已创建")
                    self.accept()
                else:
                    QMessageBox.warning(self, "错误", "创建用户失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {e}")


class UserPreferencesDialog(QDialog):
    """用户偏好设置对话框"""
    
    def __init__(self, user_manager: UserManager, username: str, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.username = username
        self.setup_ui()
        self.load_preferences()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle(f"用户偏好设置 - {self.username}")
        self.setFixedSize(400, 300)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.language_combo = QComboBox()
        self.font_size_spin = QSpinBox()
        self.auto_save_check = QCheckBox()
        self.notifications_check = QCheckBox()
        self.timezone_combo = QComboBox()
        
        # 填充选项
        self.theme_combo.addItems(['light', 'dark', 'auto'])
        self.language_combo.addItems(['zh_CN', 'en_US'])
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setValue(12)
        self.timezone_combo.addItems(['Asia/Shanghai', 'UTC', 'America/New_York'])
        
        form_layout.addRow("主题:", self.theme_combo)
        form_layout.addRow("语言:", self.language_combo)
        form_layout.addRow("字体大小:", self.font_size_spin)
        form_layout.addRow("自动保存:", self.auto_save_check)
        form_layout.addRow("通知:", self.notifications_check)
        form_layout.addRow("时区:", self.timezone_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_preferences(self):
        """加载用户偏好设置"""
        preferences = self.user_manager.get_user_preferences(self.username)
        
        self.theme_combo.setCurrentText(preferences.get('theme', 'light'))
        self.language_combo.setCurrentText(preferences.get('language', 'zh_CN'))
        self.font_size_spin.setValue(int(preferences.get('font_size', '12')))
        self.auto_save_check.setChecked(preferences.get('auto_save', True))
        self.notifications_check.setChecked(preferences.get('notifications', True))
        self.timezone_combo.setCurrentText(preferences.get('timezone', 'Asia/Shanghai'))
    
    def connect_signals(self):
        """连接信号"""
        self.save_btn.clicked.connect(self.save_preferences)
        self.cancel_btn.clicked.connect(self.reject)
    
    def save_preferences(self):
        """保存用户偏好设置"""
        try:
            preferences = {
                'theme': self.theme_combo.currentText(),
                'language': self.language_combo.currentText(),
                'font_size': str(self.font_size_spin.value()),
                'auto_save': self.auto_save_check.isChecked(),
                'notifications': self.notifications_check.isChecked(),
                'timezone': self.timezone_combo.currentText()
            }
            
            if self.user_manager.set_user_preferences(self.username, preferences):
                QMessageBox.information(self, "成功", "用户偏好设置已保存")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "保存用户偏好设置失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


if __name__ == "__main__":
    # 测试用户管理器
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建用户管理器
    user_manager = UserManager()
    
    # 创建用户管理对话框
    dialog = UserDialog(user_manager)
    dialog.show()
    
    sys.exit(app.exec())
