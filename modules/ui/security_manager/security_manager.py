#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全管理模块
提供完整的系统安全管理功能，包括用户认证、权限管理、安全日志等
"""

import os
import sys
import json
import logging
import hashlib
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
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QFont, QIcon, QAction


class SecurityManager(QObject):
    """安全管理器核心类"""
    
    # 信号定义
    user_logged_in = Signal(str, str)  # username, role
    user_logged_out = Signal(str)
    permission_changed = Signal(str, str, str)  # username, permission, action
    security_alert = Signal(str, str)  # level, message
    
    def __init__(self, security_file: str = None):
        super().__init__()
        self.security_file = security_file or "config/security.json"
        self.users = {}
        self.roles = {}
        self.permissions = {}
        self.security_log = []
        self.current_user = None
        self.logger = logging.getLogger(__name__)
        
        # 加载安全配置
        self.load_security_config()
        self.create_default_roles()
    
    def load_security_config(self):
        """加载安全配置文件"""
        try:
            if os.path.exists(self.security_file):
                with open(self.security_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
                    self.roles = data.get('roles', {})
                    self.permissions = data.get('permissions', {})
                    self.security_log = data.get('security_log', [])
                self.logger.info(f"安全配置文件加载成功: {self.security_file}")
            else:
                self.logger.warning(f"安全配置文件不存在: {self.security_file}")
                self.create_default_users()
        except Exception as e:
            self.logger.error(f"加载安全配置文件失败: {e}")
    
    def save_security_config(self):
        """保存安全配置文件"""
        try:
            os.makedirs(os.path.dirname(self.security_file), exist_ok=True)
            data = {
                'users': self.users,
                'roles': self.roles,
                'permissions': self.permissions,
                'security_log': self.security_log[-1000:]  # 保留最近1000条日志
            }
            with open(self.security_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"安全配置文件保存成功: {self.security_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存安全配置文件失败: {e}")
            return False
    
    def create_default_roles(self):
        """创建默认角色"""
        if not self.roles:
            self.roles = {
                'admin': {
                    'name': '系统管理员',
                    'permissions': ['all'],
                    'description': '拥有所有权限'
                },
                'user': {
                    'name': '普通用户',
                    'permissions': ['read', 'basic_edit'],
                    'description': '基本读写权限'
                },
                'viewer': {
                    'name': '只读用户',
                    'permissions': ['read'],
                    'description': '仅读取权限'
                }
            }
    
    def create_default_users(self):
        """创建默认用户"""
        if not self.users:
            self.users = {
                'admin': {
                    'username': 'admin',
                    'password_hash': self.hash_password('admin123'),
                    'role': 'admin',
                    'email': 'admin@example.com',
                    'created_at': datetime.datetime.now().isoformat(),
                    'last_login': None,
                    'status': 'active'
                }
            }
            self.save_security_config()
    
    def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, username: str, password: str) -> bool:
        """验证密码"""
        if username in self.users:
            stored_hash = self.users[username]['password_hash']
            return stored_hash == self.hash_password(password)
        return False
    
    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        if self.verify_password(username, password):
            if self.users[username]['status'] == 'active':
                self.current_user = username
                self.users[username]['last_login'] = datetime.datetime.now().isoformat()
                self.log_security_event('login', f"用户 {username} 登录成功")
                self.user_logged_in.emit(username, self.users[username]['role'])
                return True
            else:
                self.log_security_event('login_failed', f"用户 {username} 账户已被禁用")
        else:
            self.log_security_event('login_failed', f"用户 {username} 登录失败")
        return False
    
    def logout(self):
        """用户登出"""
        if self.current_user:
            username = self.current_user
            self.log_security_event('logout', f"用户 {username} 登出")
            self.user_logged_out.emit(username)
            self.current_user = None
    
    def check_permission(self, permission: str) -> bool:
        """检查当前用户权限"""
        if not self.current_user:
            return False
        
        user_role = self.users[self.current_user]['role']
        if user_role in self.roles:
            role_permissions = self.roles[user_role]['permissions']
            return 'all' in role_permissions or permission in role_permissions
        return False
    
    def add_user(self, username: str, password: str, role: str, email: str = "") -> bool:
        """添加用户"""
        if not self.check_permission('user_management'):
            return False
        
        if username in self.users:
            return False
        
        self.users[username] = {
            'username': username,
            'password_hash': self.hash_password(password),
            'role': role,
            'email': email,
            'created_at': datetime.datetime.now().isoformat(),
            'last_login': None,
            'status': 'active'
        }
        
        self.log_security_event('user_created', f"创建用户 {username}")
        self.save_security_config()
        return True
    
    def update_user(self, username: str, **kwargs) -> bool:
        """更新用户信息"""
        if not self.check_permission('user_management'):
            return False
        
        if username not in self.users:
            return False
        
        for key, value in kwargs.items():
            if key in ['password', 'role', 'email', 'status']:
                if key == 'password':
                    self.users[username]['password_hash'] = self.hash_password(value)
                else:
                    self.users[username][key] = value
        
        self.log_security_event('user_updated', f"更新用户 {username}")
        self.save_security_config()
        return True
    
    def delete_user(self, username: str) -> bool:
        """删除用户"""
        if not self.check_permission('user_management'):
            return False
        
        if username in self.users and username != 'admin':
            del self.users[username]
            self.log_security_event('user_deleted', f"删除用户 {username}")
            self.save_security_config()
            return True
        return False
    
    def log_security_event(self, event_type: str, message: str):
        """记录安全事件"""
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'event_type': event_type,
            'message': message,
            'user': self.current_user or 'system',
            'ip_address': '127.0.0.1'  # 简化处理
        }
        self.security_log.append(log_entry)
        self.logger.info(f"安全事件: {event_type} - {message}")
    
    def get_security_log(self, limit: int = 100) -> List[Dict]:
        """获取安全日志"""
        return self.security_log[-limit:]
    
    def get_users_summary(self) -> Dict[str, int]:
        """获取用户统计信息"""
        total_users = len(self.users)
        active_users = sum(1 for u in self.users.values() if u['status'] == 'active')
        admin_users = sum(1 for u in self.users.values() if u['role'] == 'admin')
        
        return {
            'total': total_users,
            'active': active_users,
            'admin': admin_users,
            'inactive': total_users - active_users
        }


class SecurityDialog(QDialog):
    """安全管理对话框"""
    
    def __init__(self, security_manager: SecurityManager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setup_ui()
        self.load_security_data()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("系统安全管理")
        self.setGeometry(100, 100, 1200, 800)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("🔐 用户登录")
        self.logout_btn = QPushButton("🚪 用户登出")
        self.add_user_btn = QPushButton("➕ 添加用户")
        self.edit_user_btn = QPushButton("✏️ 编辑用户")
        self.delete_user_btn = QPushButton("🗑️ 删除用户")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        toolbar_layout.addWidget(self.login_btn)
        toolbar_layout.addWidget(self.logout_btn)
        toolbar_layout.addWidget(self.add_user_btn)
        toolbar_layout.addWidget(self.edit_user_btn)
        toolbar_layout.addWidget(self.delete_user_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧用户管理
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 用户列表
        user_group = QGroupBox("用户管理")
        user_layout = QVBoxLayout(user_group)
        
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(5)
        self.user_table.setHorizontalHeaderLabels(['用户名', '角色', '邮箱', '状态', '最后登录'])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        
        user_layout.addWidget(self.user_table)
        left_layout.addWidget(user_group)
        
        # 用户统计
        stats_group = QGroupBox("用户统计")
        stats_layout = QFormLayout(stats_group)
        
        self.total_users_label = QLabel("0")
        self.active_users_label = QLabel("0")
        self.admin_users_label = QLabel("0")
        
        stats_layout.addRow("总用户数:", self.total_users_label)
        stats_layout.addRow("活跃用户:", self.active_users_label)
        stats_layout.addRow("管理员:", self.admin_users_label)
        
        left_layout.addWidget(stats_group)
        
        # 右侧安全日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        log_group = QGroupBox("安全日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_list = QListWidget()
        log_layout.addWidget(self.log_list)
        
        right_layout.addWidget(log_group)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 600])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(self.status_label)
    
    def load_security_data(self):
        """加载安全数据"""
        self.load_users_table()
        self.load_security_log()
        self.update_user_stats()
        self.update_ui_state()
    
    def load_users_table(self):
        """加载用户表格"""
        self.user_table.setRowCount(0)
        users = self.security_manager.users
        
        for row, (username, user_data) in enumerate(users.items()):
            self.user_table.insertRow(row)
            
            self.user_table.setItem(row, 0, QTableWidgetItem(username))
            self.user_table.setItem(row, 1, QTableWidgetItem(user_data.get('role', '')))
            self.user_table.setItem(row, 2, QTableWidgetItem(user_data.get('email', '')))
            self.user_table.setItem(row, 3, QTableWidgetItem(user_data.get('status', '')))
            
            last_login = user_data.get('last_login', '')
            if last_login:
                try:
                    dt = datetime.datetime.fromisoformat(last_login)
                    last_login = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            self.user_table.setItem(row, 4, QTableWidgetItem(last_login))
    
    def load_security_log(self):
        """加载安全日志"""
        self.log_list.clear()
        logs = self.security_manager.get_security_log(100)
        
        for log in reversed(logs):  # 最新的在前面
            timestamp = log['timestamp']
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
            
            item_text = f"[{timestamp}] {log['event_type']}: {log['message']}"
            item = QListWidgetItem(item_text)
            
            # 根据事件类型设置颜色
            if 'failed' in log['event_type']:
                item.setForeground(Qt.red)
            elif 'login' in log['event_type']:
                item.setForeground(Qt.green)
            elif 'logout' in log['event_type']:
                item.setForeground(Qt.blue)
            
            self.log_list.addItem(item)
    
    def update_user_stats(self):
        """更新用户统计"""
        stats = self.security_manager.get_users_summary()
        self.total_users_label.setText(str(stats['total']))
        self.active_users_label.setText(str(stats['active']))
        self.admin_users_label.setText(str(stats['admin']))
    
    def update_ui_state(self):
        """更新UI状态"""
        is_logged_in = self.security_manager.current_user is not None
        has_admin_permission = self.security_manager.check_permission('user_management')
        
        self.login_btn.setEnabled(not is_logged_in)
        self.logout_btn.setEnabled(is_logged_in)
        self.add_user_btn.setEnabled(is_logged_in and has_admin_permission)
        self.edit_user_btn.setEnabled(is_logged_in and has_admin_permission)
        self.delete_user_btn.setEnabled(is_logged_in and has_admin_permission)
        
        if is_logged_in:
            username = self.security_manager.current_user
            role = self.security_manager.users[username]['role']
            self.status_label.setText(f"当前用户: {username} ({role})")
        else:
            self.status_label.setText("未登录")
    
    def connect_signals(self):
        """连接信号"""
        self.login_btn.clicked.connect(self.show_login_dialog)
        self.logout_btn.clicked.connect(self.logout)
        self.add_user_btn.clicked.connect(self.show_add_user_dialog)
        self.edit_user_btn.clicked.connect(self.show_edit_user_dialog)
        self.delete_user_btn.clicked.connect(self.delete_user)
        self.refresh_btn.clicked.connect(self.load_security_data)
        
        # 安全管理器信号
        self.security_manager.user_logged_in.connect(self.on_user_logged_in)
        self.security_manager.user_logged_out.connect(self.on_user_logged_out)
    
    def show_login_dialog(self):
        """显示登录对话框"""
        dialog = LoginDialog(self.security_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.load_security_data()
    
    def logout(self):
        """用户登出"""
        self.security_manager.logout()
        self.load_security_data()
    
    def show_add_user_dialog(self):
        """显示添加用户对话框"""
        dialog = UserDialog(self.security_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_security_data()
    
    def show_edit_user_dialog(self):
        """显示编辑用户对话框"""
        current_row = self.user_table.currentRow()
        if current_row >= 0:
            username = self.user_table.item(current_row, 0).text()
            dialog = UserDialog(self.security_manager, username=username, parent=self)
            if dialog.exec() == QDialog.Accepted:
                self.load_security_data()
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
                if self.security_manager.delete_user(username):
                    QMessageBox.information(self, "成功", f"用户 {username} 已删除")
                    self.load_security_data()
                else:
                    QMessageBox.warning(self, "错误", "删除用户失败")
        else:
            QMessageBox.warning(self, "警告", "请先选择要删除的用户")
    
    def on_user_logged_in(self, username: str, role: str):
        """用户登录事件"""
        self.status_label.setText(f"用户 {username} 登录成功")
        self.load_security_data()
    
    def on_user_logged_out(self, username: str):
        """用户登出事件"""
        self.status_label.setText(f"用户 {username} 已登出")
        self.load_security_data()


class LoginDialog(QDialog):
    """登录对话框"""
    
    def __init__(self, security_manager: SecurityManager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("用户登录")
        self.setFixedSize(300, 150)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        
        form_layout.addRow("用户名:", self.username_edit)
        form_layout.addRow("密码:", self.password_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("登录")
        self.cancel_btn = QPushButton("取消")
        
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def connect_signals(self):
        """连接信号"""
        self.login_btn.clicked.connect(self.login)
        self.cancel_btn.clicked.connect(self.reject)
        self.password_edit.returnPressed.connect(self.login)
    
    def login(self):
        """登录"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        if self.security_manager.login(username, password):
            QMessageBox.information(self, "成功", "登录成功！")
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "用户名或密码错误")


class UserDialog(QDialog):
    """用户编辑对话框"""
    
    def __init__(self, security_manager: SecurityManager, username: str = None, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.username = username
        self.is_edit = username is not None
        self.setup_ui()
        self.load_user_data()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        title = "编辑用户" if self.is_edit else "添加用户"
        self.setWindowTitle(title)
        self.setFixedSize(350, 250)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.role_combo = QComboBox()
        self.email_edit = QLineEdit()
        self.status_combo = QComboBox()
        
        # 填充角色和状态选项
        self.role_combo.addItems(['admin', 'user', 'viewer'])
        self.status_combo.addItems(['active', 'inactive'])
        
        form_layout.addRow("用户名:", self.username_edit)
        form_layout.addRow("密码:", self.password_edit)
        form_layout.addRow("角色:", self.role_combo)
        form_layout.addRow("邮箱:", self.email_edit)
        form_layout.addRow("状态:", self.status_combo)
        
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
            self.password_edit.setPlaceholderText("留空表示不修改密码")
    
    def load_user_data(self):
        """加载用户数据"""
        if self.is_edit and self.username in self.security_manager.users:
            user_data = self.security_manager.users[self.username]
            self.username_edit.setText(self.username)
            self.role_combo.setCurrentText(user_data.get('role', 'user'))
            self.email_edit.setText(user_data.get('email', ''))
            self.status_combo.setCurrentText(user_data.get('status', 'active'))
    
    def connect_signals(self):
        """连接信号"""
        self.save_btn.clicked.connect(self.save_user)
        self.cancel_btn.clicked.connect(self.reject)
    
    def save_user(self):
        """保存用户"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        role = self.role_combo.currentText()
        email = self.email_edit.text().strip()
        status = self.status_combo.currentText()
        
        if not username:
            QMessageBox.warning(self, "警告", "请输入用户名")
            return
        
        if not self.is_edit and not password:
            QMessageBox.warning(self, "警告", "请输入密码")
            return
        
        try:
            if self.is_edit:
                # 编辑用户
                update_data = {'role': role, 'email': email, 'status': status}
                if password:
                    update_data['password'] = password
                
                if self.security_manager.update_user(username, **update_data):
                    QMessageBox.information(self, "成功", "用户信息已更新")
                    self.accept()
                else:
                    QMessageBox.warning(self, "错误", "更新用户信息失败")
            else:
                # 添加用户
                if self.security_manager.add_user(username, password, role, email):
                    QMessageBox.information(self, "成功", "用户已创建")
                    self.accept()
                else:
                    QMessageBox.warning(self, "错误", "创建用户失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {e}")


if __name__ == "__main__":
    # 测试安全管理器
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建安全管理器
    security_manager = SecurityManager()
    
    # 创建安全管理对话框
    dialog = SecurityDialog(security_manager)
    dialog.show()
    
    sys.exit(app.exec())
