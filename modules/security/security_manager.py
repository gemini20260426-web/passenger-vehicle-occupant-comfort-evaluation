import os
import json
import bcrypt
from datetime import datetime
from cryptography.fernet import Fernet
import logging
import os
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QFormLayout, QTableWidget, QTableWidgetItem, QComboBox
from PySide6.QtGui import QFont

# 延迟导入ConfigManager，解决循环依赖问题
ConfigManager = None

def _get_config_manager():
    global ConfigManager
    if ConfigManager is None:
        from config_manager import ConfigManager
    return ConfigManager

logger = logging.getLogger("SecurityManager")

# 定义角色和权限
ROLES = {
    "admin": {
        "name": "系统管理员",
        "permissions": ["user_manage", "config_manage", "data_export", "system_monitor", "log_view"]
    },
    "operator": {
        "name": "操作员",
        "permissions": ["data_view", "alarm_handle", "log_view"]
    },
    "viewer": {
        "name": "查看员",
        "permissions": ["data_view", "log_view"]
    }
}

class SecurityManager(QObject):
    """安全管理器，处理用户认证、权限控制和数据加密"""
    user_authenticated = Signal(dict)  # 用户认证成功信号，传递用户信息
    user_logged_out = Signal()         # 用户登出信号
    users_updated = Signal(list)       # 用户列表更新信号
    
    def __init__(self, config_manager=None, log_manager=None):
        super().__init__()
        if config_manager is None:
            ConfigManagerClass = _get_config_manager()
            # 使用默认配置目录而不是当前目录
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_manager = ConfigManagerClass(config_dir)
        else:
            self.config_manager = config_manager
        self.log_manager = log_manager  # 日志管理器
        self.current_user = None
        
        # 从配置获取用户数据存储路径
        paths_section = self.config_manager.get_section("paths") or {}
        data_dir = paths_section.get("data_dir", os.path.join(os.getcwd(), "data"))
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        self.data_path = os.path.join(data_dir, "users.json")
        
        self.users = self._load_users()
        # 只有当这是独立创建的SecurityManager时才输出此日志
        if config_manager is None:
            logger.info(f"用户数据文件路径: {self.data_path}")
        
        # 初始化加密系统
        self.encryption_key_file = os.path.join(data_dir, "encryption.key")
        self.cipher_suite = None
        self._init_encryption()
        
        # 确保至少有一个管理员用户
        self._ensure_admin_exists()
    
    def _init_encryption(self):
        """初始化加密系统"""
        try:
            # 尝试加载现有密钥
            if os.path.exists(self.encryption_key_file):
                with open(self.encryption_key_file, 'rb') as f:
                    key = f.read()
                self.cipher_suite = Fernet(key)
            else:
                # 生成新密钥
                key = Fernet.generate_key()
                with open(self.encryption_key_file, 'wb') as f:
                    f.write(key)
                self.cipher_suite = Fernet(key)
                logger.info("生成了新的加密密钥")
        except Exception as e:
            logger.error(f"加密系统初始化失败: {str(e)}")
            self.cipher_suite = None
    
    def _load_users(self):
        """加载用户数据"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载用户数据失败: {str(e)}")
            return []
    
    def _save_users(self):
        """保存用户数据"""
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            logger.info("用户数据已保存")
            self.users_updated.emit(self.users)
            return True
        except Exception as e:
            logger.error(f"保存用户数据失败: {str(e)}")
            return False
    
    def _ensure_admin_exists(self):
        """确保系统中至少有一个管理员用户"""
        has_admin = any(user["role"] == "admin" for user in self.users)
        if not has_admin:
            # 创建默认管理员用户
            password_hash = self._hash_password("admin123")
            admin_user = {
                "id": f"user_{int(datetime.now().timestamp() * 1000)}",
                "username": "admin",
                "password_hash": password_hash.decode('utf-8'),
                "name": "系统管理员",
                "role": "admin",
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "last_login": None
            }
            self.users.append(admin_user)
            self._save_users()
            logger.warning("创建了默认管理员用户: admin / admin123，请尽快修改密码")
    
    def _hash_password(self, password):
        """加密密码"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    def _check_password(self, password, password_hash):
        """验证密码"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def encrypt_data(self, data):
        """加密数据"""
        if not self.cipher_suite or not data:
            return None
            
        try:
            if isinstance(data, str):
                return self.cipher_suite.encrypt(data.encode('utf-8')).decode('utf-8')
            elif isinstance(data, bytes):
                return self.cipher_suite.encrypt(data).decode('utf-8')
            else:
                return self.cipher_suite.encrypt(json.dumps(data).encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"数据加密失败: {str(e)}")
            return None

    def decrypt_data(self, encrypted_data):
        """解密数据"""
        if not self.cipher_suite or not encrypted_data:
            return None
            
        try:
            decrypted_bytes = self.cipher_suite.decrypt(encrypted_data.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            # 检查是否是无效token错误（可能是未加密的数据）
            if "InvalidToken" in str(e):
                # 如果是无效token错误，可能是未加密的原始数据
                try:
                    # 尝试直接返回原始数据（如果它是明文）
                    return encrypted_data
                except:
                    pass
            # 对于空字符串或None值，不记录警告日志
            if encrypted_data and str(encrypted_data).strip():
                self.logger.warning(f"数据解密失败: {str(e)}")
            return None

    def login(self, username, password):
        """用户登录"""
        for user in self.users:
            if user["username"] == username and user["status"] == "active":
                if self._check_password(password, user["password_hash"]):
                    # 更新最后登录时间
                    user["last_login"] = datetime.now().isoformat()
                    self._save_users()
                    
                    # 记录登录日志
                    self._log_action(user["id"], "login", "用户登录成功")
                    
                    # 存储当前用户信息（不包含密码）
                    self.current_user = {k: v for k, v in user.items() if k != "password_hash"}
                    self.user_authenticated.emit(self.current_user)
                    return True, "登录成功"
                else:
                    self._log_action(None, "login_failed", f"用户 {username} 密码错误")
                    return False, "用户名或密码错误"
        
        self._log_action(None, "login_failed", f"用户 {username} 不存在")
        return False, "用户名或密码错误"
    
    def logout(self):
        """用户登出"""
        if self.current_user:
            self._log_action(self.current_user["id"], "logout", "用户登出")
            self.current_user = None
            self.user_logged_out.emit()
            return True
        return False
    
    def get_current_user(self):
        """获取当前登录用户"""
        return self.current_user.copy() if self.current_user else None
    
    def has_permission(self, permission):
        """检查当前用户是否有指定权限"""
        if not self.current_user:
            return False
            
        user_role = self.current_user["role"]
        return permission in ROLES.get(user_role, {}).get("permissions", [])
    
    def add_user(self, user_data):
        """添加新用户"""
        # 检查权限
        if not self.has_permission("user_manage"):
            return False, "没有添加用户的权限"
        
        # 检查用户名是否已存在
        if any(user["username"] == user_data["username"] for user in self.users):
            return False, "用户名已存在"
        
        # 生成用户ID
        user_id = f"user_{int(datetime.now().timestamp() * 1000)}"
        
        # 加密密码
        password_hash = self._hash_password(user_data["password"])
        
        # 创建用户对象
        user = {
            "id": user_id,
            "username": user_data["username"],
            "password_hash": password_hash.decode('utf-8'),
            "name": user_data.get("name", ""),
            "role": user_data["role"],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        self.users.append(user)
        success = self._save_users()
        if success:
            self._log_action(self.current_user["id"], "add_user", f"添加用户: {user['username']}")
            return True, user_id
        return False, "保存用户失败"
    
    def update_user(self, user_id, user_data, update_password=False):
        """更新用户信息"""
        # 检查权限
        if not self.has_permission("user_manage"):
            return False, "没有更新用户的权限"
        
        for i, user in enumerate(self.users):
            if user["id"] == user_id:
                # 不允许普通管理员修改超级管理员
                if user["role"] == "admin" and self.current_user["role"] == "admin" and user["id"] != self.current_user["id"]:
                    return False, "不能修改其他管理员的信息"
                
                # 更新字段
                if "name" in user_data:
                    self.users[i]["name"] = user_data["name"]
                if "role" in user_data and self.current_user["role"] == "admin":
                    self.users[i]["role"] = user_data["role"]
                if "status" in user_data and self.current_user["role"] == "admin":
                    self.users[i]["status"] = user_data["status"]
                
                # 更新密码
                if update_password and "password" in user_data and user_data["password"]:
                    self.users[i]["password_hash"] = self._hash_password(user_data["password"]).decode('utf-8')
                
                success = self._save_users()
                if success:
                    self._log_action(self.current_user["id"], "update_user", f"更新用户: {user['username']}")
                    return True, "更新成功"
                return False, "保存更新失败"
        
        return False, "未找到用户"
    
    def delete_user(self, user_id):
        """删除用户"""
        # 检查权限
        if not self.has_permission("user_manage"):
            return False, "没有删除用户的权限"
        
        # 不能删除自己
        if self.current_user and user_id == self.current_user["id"]:
            return False, "不能删除当前登录用户"
        
        # 不能删除最后一个管理员
        admin_users = [u for u in self.users if u["role"] == "admin"]
        if len(admin_users) == 1 and admin_users[0]["id"] == user_id:
            return False, "不能删除最后一个管理员"
        
        initial_count = len(self.users)
        self.users = [u for u in self.users if u["id"] != user_id]
        
        if len(self.users) < initial_count:
            success = self._save_users()
            if success:
                self._log_action(self.current_user["id"], "delete_user", f"删除用户: {user_id}")
                return True, "删除成功"
            return False, "保存删除结果失败"
        
        return False, "未找到用户"
    
    def get_all_users(self):
        """获取所有用户（不包含密码）"""
        if not self.has_permission("user_manage"):
            return []
            
        return [{k: v for k, v in user.items() if k != "password_hash"} for user in self.users]
    
    def get_user(self, user_id):
        """获取指定用户（不包含密码）"""
        if not self.has_permission("user_manage") and (not self.current_user or self.current_user["id"] != user_id):
            return None
            
        for user in self.users:
            if user["id"] == user_id:
                return {k: v for k, v in user.items() if k != "password_hash"}
        return None
    
    def _log_action(self, user_id, action, details):
        """记录用户操作日志"""
        if self.log_manager:
            self.log_manager.add_log({
                "user_id": user_id,
                "action": action,
                "details": details,
                "timestamp": datetime.now().isoformat(),
                "ip_address": "127.0.0.1"  # 在实际应用中可以获取真实IP
            })
        else:
            logger.info(f"用户操作: {user_id} - {action} - {details}")


class LoginDialog(QDialog):
    """登录对话框"""
    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setWindowTitle("用户登录")
        self.setFixedSize(300, 200)
        self.init_ui()
        
    def init_ui(self):
        """初始化登录界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("车辆管理系统")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(20)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("请输入密码")
        
        form_layout.addRow("用户名:", self.username_edit)
        form_layout.addRow("密码:", self.password_edit)
        
        layout.addLayout(form_layout)
        layout.addSpacing(20)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("登录")
        self.login_btn.clicked.connect(self.handle_login)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # 设置焦点
        self.username_edit.setFocus()
    
    def handle_login(self):
        """处理登录逻辑"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "输入错误", "请输入用户名和密码")
            return
        
        success, msg = self.security_manager.login(username, password)
        if success:
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "失败", msg)


class UserManagementDialog(QDialog):
    """用户管理对话框"""
    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setWindowTitle("用户管理")
        self.resize(700, 500)
        self.init_ui()
        
        # 连接信号
        self.security_manager.users_updated.connect(self.refresh_user_table)
        
        # 初始加载数据
        self.refresh_user_table()
    
    def init_ui(self):
        """初始化用户管理界面"""
        layout = QVBoxLayout(self)
        
        # 顶部操作区
        top_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("添加用户")
        self.add_btn.clicked.connect(self.show_add_user_dialog)
        
        self.edit_btn = QPushButton("编辑用户")
        self.edit_btn.clicked.connect(self.show_edit_user_dialog)
        self.edit_btn.setEnabled(False)
        
        self.delete_btn = QPushButton("删除用户")
        self.delete_btn.clicked.connect(self.delete_selected_user)
        self.delete_btn.setEnabled(False)
        
        top_layout.addWidget(self.add_btn)
        top_layout.addWidget(self.edit_btn)
        top_layout.addWidget(self.delete_btn)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # 用户表格
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels([
            "用户名", "姓名", "角色", "状态", "创建时间", "最后登录"
        ])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.user_table)
    
    def refresh_user_table(self):
        """刷新用户表格"""
        users = self.security_manager.get_all_users()
        self.user_table.setRowCount(len(users))
        
        role_names = {k: v["name"] for k, v in ROLES.items()}
        
        for row, user in enumerate(users):
            self.user_table.setItem(row, 0, QTableWidgetItem(user["username"]))
            self.user_table.setItem(row, 1, QTableWidgetItem(user.get("name", "")))
            self.user_table.setItem(row, 2, QTableWidgetItem(role_names.get(user["role"], user["role"])))
            
            # 状态单元格
            status_item = QTableWidgetItem("启用" if user["status"] == "active" else "禁用")
            status_item.setBackground(Qt.green if user["status"] == "active" else Qt.gray)
            self.user_table.setItem(row, 3, status_item)
            
            # 格式化时间
            created_time = datetime.fromisoformat(user["created_at"]).strftime("%Y-%m-%d %H:%M")
            self.user_table.setItem(row, 4, QTableWidgetItem(created_time))
            
            last_login = user["last_login"]
            if last_login:
                last_login_str = datetime.fromisoformat(last_login).strftime("%Y-%m-%d %H:%M")
            else:
                last_login_str = "从未登录"
            self.user_table.setItem(row, 5, QTableWidgetItem(last_login_str))
            
            # 存储用户ID
            self.user_table.item(row, 0).setData(Qt.UserRole, user["id"])
        
        # 调整列宽
        self.user_table.resizeColumnsToContents()
    
    def on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.user_table.selectedItems()
        self.edit_btn.setEnabled(len(selected_items) > 0)
        self.delete_btn.setEnabled(len(selected_items) > 0)
    
    def get_selected_user_id(self):
        """获取选中的用户ID"""
        selected_rows = set()
        for item in self.user_table.selectedItems():
            selected_rows.add(item.row())
        
        if len(selected_rows) != 1:
            QMessageBox.warning(self, "选择错误", "请选择一个用户进行操作")
            return None
            
        row = next(iter(selected_rows))
        return self.user_table.item(row, 0).data(Qt.UserRole)
    
    def show_add_user_dialog(self):
        """显示添加用户对话框"""
        dialog = UserDetailDialog(self.security_manager, parent=self)
        dialog.exec()
    
    def show_edit_user_dialog(self):
        """显示编辑用户对话框"""
        user_id = self.get_selected_user_id()
        if user_id:
            dialog = UserDetailDialog(self.security_manager, user_id=user_id, parent=self)
            dialog.exec()
    
    def delete_selected_user(self):
        """删除选中的用户"""
        user_id = self.get_selected_user_id()
        if not user_id:
            return
            
        user = self.security_manager.get_user(user_id)
        if not user:
            QMessageBox.error(self, "错误", "未找到用户信息")
            return
            
        if QMessageBox.question(
            self, "确认删除", f"确定要删除用户 {user['username']} 吗？"
        ) == QMessageBox.Yes:
            success, msg = self.security_manager.delete_user(user_id)
            if success:
                QMessageBox.information(self, "成功", msg)
                self.refresh_user_table()
            else:
                QMessageBox.error(self, "失败", msg)


class UserDetailDialog(QDialog):
    """用户详情对话框，用于添加和编辑用户"""
    def __init__(self, security_manager, user_id=None, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.user_id = user_id
        self.user = None
        
        if user_id:
            self.user = self.security_manager.get_user(user_id)
            self.setWindowTitle(f"编辑用户: {self.user.get('username', '')}")
        else:
            self.setWindowTitle("添加新用户")
        
        self.resize(400, 300)
        self.init_ui()
    
    def init_ui(self):
        """初始化用户详情界面"""
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setReadOnly(self.user_id is not None)  # 用户名不可修改
        
        self.name_edit = QLineEdit()
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        if self.user_id:
            self.password_edit.setPlaceholderText("不修改密码请留空")
        
        self.role_combo = QComboBox()
        for role_key, role_info in ROLES.items():
            self.role_combo.addItem(role_info["name"], role_key)
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("启用", "active")
        self.status_combo.addItem("禁用", "inactive")
        
        form_layout.addRow("用户名*:", self.username_edit)
        form_layout.addRow("姓名:", self.name_edit)
        form_layout.addRow("密码*:", self.password_edit)
        form_layout.addRow("角色*:", self.role_combo)
        form_layout.addRow("状态:", self.status_combo)
        
        layout.addLayout(form_layout)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_user)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载用户数据
        self.load_user_data()
    
    def load_user_data(self):
        """加载用户数据到表单"""
        if not self.user:
            return
            
        self.username_edit.setText(self.user.get("username", ""))
        self.name_edit.setText(self.user.get("name", ""))
        
        # 设置角色
        role_index = self.role_combo.findData(self.user["role"])
        if role_index >= 0:
            self.role_combo.setCurrentIndex(role_index)
        
        # 设置状态
        status_index = self.status_combo.findData(self.user["status"])
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)
    
    def save_user(self):
        """保存用户信息"""
        # 收集表单数据
        user_data = {
            "username": self.username_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "role": self.role_combo.currentData(),
            "status": self.status_combo.currentData()
        }
        
        # 验证必填字段
        if not user_data["username"]:
            QMessageBox.warning(self, "输入错误", "请输入用户名")
            return
            
        # 新用户或修改密码时需要验证密码
        if not self.user_id:
            if not self.password_edit.text().strip():
                QMessageBox.warning(self, "输入错误", "请输入密码")
                return
            user_data["password"] = self.password_edit.text().strip()
        elif self.password_edit.text().strip():
            user_data["password"] = self.password_edit.text().strip()
        
        # 保存数据
        if self.user_id:
            # 更新现有用户
            update_password = "password" in user_data
            success, msg = self.security_manager.update_user(
                self.user_id, user_data, update_password
            )
        else:
            # 添加新用户
            success, msg = self.security_manager.add_user(user_data)
        
        if success:
            QMessageBox.information(self, "成功", "用户信息已保存")
            self.close()
        else:
            QMessageBox.error(self, "失败", msg)


class LogManager(QObject):
    """日志管理器，负责记录和查询系统操作日志"""
    logs_updated = Signal(list)  # 日志更新信号
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        # 从配置获取日志存储路径
        data_dir = config_manager.get_config("paths").get("data_dir", os.path.join(os.getcwd(), "data"))
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        self.data_path = os.path.join(data_dir, "operation_logs.json")
        self.logs = self._load_logs()
    
    def _load_logs(self):
        """加载日志数据"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载日志数据失败: {str(e)}")
            return []
    
    def _save_logs(self):
        """保存日志数据"""
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
            self.logs_updated.emit(self.logs)
            return True
        except Exception as e:
            logger.error(f"保存日志数据失败: {str(e)}")
            return False
    
    def add_log(self, log_data):
        """添加操作日志"""
        log = {
            "id": f"log_{int(datetime.now().timestamp() * 1000)}",
            **log_data
        }
        self.logs.append(log)
        
        # 限制日志数量，只保留最近10000条
        if len(self.logs) > 10000:
            self.logs = self.logs[-10000:]
        
        return self._save_logs()
    
    def get_logs(self, count=100, user_id=None, action=None):
        """获取日志列表，支持筛选"""
        filtered_logs = self.logs
        
        # 按用户筛选
        if user_id:
            filtered_logs = [log for log in filtered_logs if log.get("user_id") == user_id]
        
        # 按操作筛选
        if action:
            filtered_logs = [log for log in filtered_logs if log.get("action") == action]
        
        # 按时间排序（最新的在前）
        filtered_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # 限制数量
        return filtered_logs[:count]


class LogViewerDialog(QDialog):
    """日志查看器对话框"""
    def __init__(self, log_manager, security_manager, parent=None):
        super().__init__(parent)
        self.log_manager = log_manager
        self.security_manager = security_manager
        self.setWindowTitle("操作日志")
        self.resize(900, 600)
        self.init_ui()
        
        # 连接信号
        self.log_manager.logs_updated.connect(self.refresh_log_table)
        
        # 初始加载数据
        self.refresh_log_table()
    
    def init_ui(self):
        """初始化日志查看界面"""
        layout = QVBoxLayout(self)
        
        # 日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(5)
        self.log_table.setHorizontalHeaderLabels([
            "时间", "用户ID", "操作", "详情", "IP地址"
        ])
        self.log_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.log_table)
    
    def refresh_log_table(self):
        """刷新日志表格"""
        logs = self.log_manager.get_logs(count=500)
        self.log_table.setRowCount(len(logs))
        
        for row, log in enumerate(logs):
            # 格式化时间
            timestamp = datetime.fromisoformat(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            self.log_table.setItem(row, 0, QTableWidgetItem(timestamp))
            
            self.log_table.setItem(row, 1, QTableWidgetItem(log.get("user_id", "未知")))
            self.log_table.setItem(row, 2, QTableWidgetItem(log.get("action", "")))
            self.log_table.setItem(row, 3, QTableWidgetItem(log.get("details", "")))
            self.log_table.setItem(row, 4, QTableWidgetItem(log.get("ip_address", "")))
        
        # 调整列宽
        self.log_table.resizeColumnsToContents()
