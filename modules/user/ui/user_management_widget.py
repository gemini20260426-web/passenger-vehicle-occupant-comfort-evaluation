"""用户管理界面组件（管理系统用户与权限）"""
import logging
import os
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QDialog, QLineEdit, QComboBox,
                             QTabWidget, QTextEdit, QDateEdit, QFilterProxyModel,
                             QItemDelegate, QCheckBox, QSpinBox, QMessageBox)
from PySide6.QtCore import Qt, Slot, QDateTime, QMutex, QMutexLocker, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QIcon, QStandardItemModel, QStandardItem

class UserManagementWidget(QWidget):
    """用户管理界面组件（保持原有类名）"""
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.user_manager = user_manager
        
        # 线程安全锁（新增）
        self.widget_lock = QMutex()
        
        # 当前选中的用户（保持原有）
        self.selected_user = None
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 连接信号（新增）
        self._connect_signals()
        
        # 加载数据
        self._load_user_list()

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("用户管理")
        self.resize(900, 600)
        
        # 创建标签页（保持原有）
        self.tab_widget = QTabWidget()
        
        # 用户列表标签页
        self.user_list_tab = QWidget()
        self._init_user_list_tab()
        self.tab_widget.addTab(self.user_list_tab, "用户列表")
        
        # 操作日志标签页
        self.logs_tab = QWidget()
        self._init_logs_tab()
        self.tab_widget.addTab(self.logs_tab, "操作日志")
        
        # 个人设置标签页
        self.profile_tab = QWidget()
        self._init_profile_tab()
        self.tab_widget.addTab(self.profile_tab, "个人设置")
        
        main_layout.addWidget(self.tab_widget)

    def _init_user_list_tab(self) -> None:
        """初始化用户列表标签页（保持原有方法）"""
        layout = QVBoxLayout(self.user_list_tab)
        
        # 操作按钮区域（保持原有）
        btn_layout = QHBoxLayout()
        
        self.add_user_btn = QPushButton("新增用户")
        self.add_user_btn.clicked.connect(self._add_user)
        btn_layout.addWidget(self.add_user_btn)
        
        self.edit_user_btn = QPushButton("编辑用户")
        self.edit_user_btn.clicked.connect(self._edit_user)
        self.edit_user_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_user_btn)
        
        self.delete_user_btn = QPushButton("删除用户")
        self.delete_user_btn.clicked.connect(self._delete_user)
        self.delete_user_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_user_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_user_btn)
        
        self.reset_pwd_btn = QPushButton("重置密码")
        self.reset_pwd_btn.clicked.connect(self._reset_password)
        btn_layout.addWidget(self.reset_pwd_btn)
        
        btn_layout.addStretch()
        
        # 搜索框（新增）
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索用户...")
        self.search_input.textChanged.connect(self._filter_users)
        btn_layout.addWidget(self.search_input)
        
        layout.addLayout(btn_layout)
        
        # 用户列表（保持原有）
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels(["用户名", "角色", "状态", "创建时间", "最后登录", "操作"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.cellClicked.connect(self._on_user_selected)
        layout.addWidget(self.user_table)
        
        # 状态栏（新增）
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

    def _init_logs_tab(self) -> None:
        """初始化操作日志标签页（新增）"""
        layout = QVBoxLayout(self.logs_tab)
        
        # 筛选区域（新增）
        filter_layout = QHBoxLayout()
        
        self.log_user_filter = QComboBox()
        self.log_user_filter.addItem("所有用户", "")
        # 用户列表将在加载时填充
        filter_layout.addWidget(QLabel("用户:"))
        filter_layout.addWidget(self.log_user_filter)
        
        self.log_action_filter = QComboBox()
        self.log_action_filter.addItem("所有操作", "")
        self.log_action_filter.addItem("登录", "login")
        self.log_action_filter.addItem("登出", "logout")
        self.log_action_filter.addItem("创建用户", "create_user")
        self.log_action_filter.addItem("删除用户", "delete_user")
        self.log_action_filter.addItem("更新用户", "update_user")
        self.log_action_filter.addItem("修改密码", "change_password")
        self.log_action_filter.addItem("重置密码", "reset_password")
        filter_layout.addWidget(QLabel("操作:"))
        filter_layout.addWidget(self.log_action_filter)
        
        self.refresh_logs_btn = QPushButton("刷新日志")
        self.refresh_logs_btn.clicked.connect(self._load_action_logs)
        filter_layout.addWidget(self.refresh_logs_btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # 日志列表（新增）
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["时间", "用户", "操作", "详情"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.log_table)

    def _init_profile_tab(self) -> None:
        """初始化个人设置标签页（保持原有方法）"""
        layout = QVBoxLayout(self.profile_tab)
        
        # 当前用户信息（新增）
        self.current_user_label = QLabel("当前用户: 未登录")
        self.current_user_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.current_user_label)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 密码修改区域（保持原有）
        pwd_group = QGroupBox("修改密码")
        pwd_layout = QFormLayout()
        
        self.old_pwd_input = QLineEdit()
        self.old_pwd_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addRow("当前密码:", self.old_pwd_input)
        
        self.new_pwd_input = QLineEdit()
        self.new_pwd_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addRow("新密码:", self.new_pwd_input)
        
        self.confirm_pwd_input = QLineEdit()
        self.confirm_pwd_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addRow("确认新密码:", self.confirm_pwd_input)
        
        self.change_pwd_btn = QPushButton("修改密码")
        self.change_pwd_btn.clicked.connect(self._change_password)
        pwd_layout.addRow(self.change_pwd_btn)
        
        pwd_group.setLayout(pwd_layout)
        layout.addWidget(pwd_group)
        
        layout.addStretch()

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 用户管理器信号
        self.user_manager.user_login.connect(self._on_user_login)
        self.user_manager.user_logout.connect(self._on_user_logout)
        self.user_manager.user_created.connect(self._on_user_created)
        self.user_manager.user_deleted.connect(self._on_user_deleted)
        self.user_manager.user_updated.connect(self._on_user_updated)
        self.user_manager.password_changed.connect(self._on_password_changed)
        self.user_manager.error_occurred.connect(self._on_error_occurred)
        
        # 初始加载当前用户信息
        current_user = self.user_manager.get_current_user()
        if current_user:
            self._update_current_user_info(current_user)
        else:
            self._update_current_user_info(None)

    def _load_user_list(self) -> None:
        """加载用户列表（保持原有方法）"""
        # 清空表格
        self.user_table.setRowCount(0)
        
        # 获取用户列表
        users = self.user_manager.get_user_list()
        
        # 添加到表格
        for i, user in enumerate(users):
            self.user_table.insertRow(i)
            
            # 用户名
            username_item = QTableWidgetItem(user['username'])
            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)
            self.user_table.setItem(i, 0, username_item)
            
            # 角色
            role_map = {
                'admin': '管理员',
                'user': '普通用户',
                'viewer': '查看者'
            }
            role_item = QTableWidgetItem(role_map.get(user['role'], user['role']))
            role_item.setTextAlignment(Qt.AlignCenter)
            role_item.setFlags(role_item.flags() & ~Qt.ItemIsEditable)
            self.user_table.setItem(i, 1, role_item)
            
            # 状态
            status_map = {
                'active': '活跃',
                'inactive': '不活跃',
                'locked': '已锁定'
            }
            status = user.get('status', 'active')
            status_item = QTableWidgetItem(status_map.get(status, status))
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            
            # 设置状态颜色
            if status == 'active':
                status_item.setBackground(QColor(220, 255, 220))
            elif status == 'locked':
                status_item.setBackground(QColor(255, 220, 220))
            else:
                status_item.setBackground(QColor(255, 255, 220))
                
            self.user_table.setItem(i, 2, status_item)
            
            # 创建时间
            created_item = QTableWidgetItem(
                QDateTime.fromSecsSinceEpoch(int(user['created_at'])).toString("yyyy-MM-dd HH:mm")
            )
            created_item.setTextAlignment(Qt.AlignCenter)
            created_item.setFlags(created_item.flags() & ~Qt.ItemIsEditable)
            self.user_table.setItem(i, 3, created_item)
            
            # 最后登录
            last_login = user.get('last_login', 0)
            if last_login > 0:
                login_item = QTableWidgetItem(
                    QDateTime.fromSecsSinceEpoch(int(last_login)).toString("yyyy-MM-dd HH:mm")
                )
            else:
                login_item = QTableWidgetItem("从未登录")
                
            login_item.setTextAlignment(Qt.AlignCenter)
            login_item.setFlags(login_item.flags() & ~Qt.ItemIsEditable)
            self.user_table.setItem(i, 4, login_item)
            
            # 操作按钮
            btn_layout = QHBoxLayout()
            edit_btn = QPushButton("编辑")
            edit_btn.setMinimumWidth(50)
            edit_btn.clicked.connect(lambda checked, u=user: self._edit_user(u))
            
            reset_btn = QPushButton("重置密码")
            reset_btn.setMinimumWidth(80)
            reset_btn.clicked.connect(lambda checked, u=user: self._reset_password(u))
            
            delete_btn = QPushButton("删除")
            delete_btn.setMinimumWidth(50)
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(lambda checked, u=user: self._delete_user(u))
            
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(reset_btn)
            btn_layout.addWidget(delete_btn)
            
            btn_widget = QWidget()
            btn_widget.setLayout(btn_layout)
            self.user_table.setCellWidget(i, 5, btn_widget)
        
        # 更新用户筛选下拉框
        self._update_user_filter()
        
        # 重置选中状态
        with QMutexLocker(self.widget_lock):
            self.selected_user = None
            self.edit_user_btn.setEnabled(False)
            self.delete_user_btn.setEnabled(False)
            self.reset_pwd_btn.setEnabled(False)

    def _update_user_filter(self) -> None:
        """更新用户筛选下拉框（新增）"""
        current_index = self.log_user_filter.currentIndex()
        
        # 保存当前选择的用户
        current_user = self.log_user_filter.currentData()
        
        # 清空并重新填充
        self.log_user_filter.clear()
        self.log_user_filter.addItem("所有用户", "")
        
        # 添加所有用户
        users = self.user_manager.get_user_list()
        for user in users:
            self.log_user_filter.addItem(user['username'], user['username'])
        
        # 恢复之前的选择
        if current_user:
            index = self.log_user_filter.findData(current_user)
            if index >= 0:
                self.log_user_filter.setCurrentIndex(index)
            else:
                self.log_user_filter.setCurrentIndex(0)
        else:
            self.log_user_filter.setCurrentIndex(current_index)

    def _load_action_logs(self) -> None:
        """加载操作日志（新增）"""
        # 清空表格
        self.log_table.setRowCount(0)
        
        # 获取筛选条件
        username = self.log_user_filter.currentData()
        action = self.log_action_filter.currentData()
        
        # 获取日志列表
        logs = self.user_manager.get_action_logs(limit=1000, username=username)
        
        # 应用操作筛选
        if action:
            logs = [log for log in logs if log['action'] == action]
        
        # 添加到表格
        for i, log in enumerate(logs):
            self.log_table.insertRow(i)
            
            # 时间
            time_item = QTableWidgetItem(
                QDateTime.fromSecsSinceEpoch(int(log['timestamp'])).toString("yyyy-MM-dd HH:mm:ss")
            )
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 0, time_item)
            
            # 用户
            user_item = QTableWidgetItem(log['username'])
            user_item.setFlags(user_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 1, user_item)
            
            # 操作
            action_map = {
                'login': '登录',
                'logout': '登出',
                'create_user': '创建用户',
                'delete_user': '删除用户',
                'update_user': '更新用户',
                'change_password': '修改密码',
                'reset_password': '重置密码'
            }
            action_item = QTableWidgetItem(action_map.get(log['action'], log['action']))
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 2, action_item)
            
            # 详情
            detail_item = QTableWidgetItem(log['details'])
            detail_item.setFlags(detail_item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(i, 3, detail_item)

    def _update_current_user_info(self, username: Optional[str]) -> None:
        """更新当前用户信息（新增）"""
        if username:
            self.current_user_label.setText(f"当前用户: {username}")
            
            # 检查权限，控制用户管理功能的可见性
            user_role = self.user_manager.get_current_user_role()
            if user_role != 'admin':
                self.tab_widget.setTabEnabled(0, False)  # 禁用用户列表标签页
                self.tab_widget.setTabEnabled(1, False)  # 禁用操作日志标签页
                self.tab_widget.setCurrentIndex(2)       # 切换到个人设置
        else:
            self.current_user_label.setText("当前用户: 未登录")
            self.tab_widget.setTabEnabled(0, False)
            self.tab_widget.setTabEnabled(1, False)

    @Slot(int, int)
    def _on_user_selected(self, row: int, column: int) -> None:
        """处理用户选中（保持原有方法）"""
        # 获取选中的用户名
        username_item = self.user_table.item(row, 0)
        if username_item:
            username = username_item.text()
            
            # 查找完整的用户信息
            for user in self.user_manager.get_user_list():
                if user['username'] == username:
                    with QMutexLocker(self.widget_lock):
                        self.selected_user = user
                        self.edit_user_btn.setEnabled(True)
                        self.delete_user_btn.setEnabled(True)
                        self.reset_pwd_btn.setEnabled(True)
                    break

    @Slot()
    def _filter_users(self, text: str) -> None:
        """筛选用户（新增）"""
        text = text.lower()
        for row in range(self.user_table.rowCount()):
            username_item = self.user_table.item(row, 0)
            role_item = self.user_table.item(row, 1)
            
            if username_item and role_item:
                username = username_item.text().lower()
                role = role_item.text().lower()
                
                match = text in username or text in role
                self.user_table.setRowHidden(row, not match)

    @Slot()
    def _add_user(self) -> None:
        """新增用户（保持原有方法）"""
        # 检查权限
        current_user = self.user_manager.get_current_user()
        if not current_user:
            QMessageBox.warning(self, "权限不足", "请先登录")
            return
            
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("新增用户")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 用户名
        username_input = QLineEdit()
        form_layout.addRow("用户名:", username_input)
        
        # 密码
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("密码:", password_input)
        
        # 确认密码
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("确认密码:", confirm_input)
        
        # 角色
        role_combo = QComboBox()
        role_combo.addItem("普通用户", "user")
        role_combo.addItem("查看者", "viewer")
        
        # 如果当前用户是管理员，允许创建管理员
        if self.user_manager.get_current_user_role() == 'admin':
            role_combo.insertItem(0, "管理员", "admin")
            
        form_layout.addRow("角色:", role_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("创建")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # 显示对话框
        if dialog.exec() == QDialog.Accepted:
            username = username_input.text().strip()
            password = password_input.text()
            confirm = confirm_input.text()
            role = role_combo.currentData()
            
            # 验证输入
            if not username:
                QMessageBox.warning(self, "输入错误", "用户名不能为空")
                return
                
            if not password:
                QMessageBox.warning(self, "输入错误", "密码不能为空")
                return
                
            if password != confirm:
                QMessageBox.warning(self, "输入错误", "两次输入的密码不一致")
                return
                
            # 创建用户
            if self.user_manager.create_user(username, password, role, current_user):
                self.status_label.setText(f"用户 {username} 创建成功")
            else:
                self.status_label.setText(f"用户 {username} 创建失败")

    @Slot()
    def _edit_user(self, user: Optional[Dict[str, Any]] = None) -> None:
        """编辑用户（保持原有方法）"""
        # 如果没有指定用户，使用选中的用户
        if not user:
            with QMutexLocker(self.widget_lock):
                user = self.selected_user
                
        if not user:
            QMessageBox.warning(self, "操作失败", "请先选择一个用户")
            return
            
        username = user['username']
        current_user = self.user_manager.get_current_user()
        
        # 检查权限
        if not current_user:
            QMessageBox.warning(self, "权限不足", "请先登录")
            return
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"编辑用户: {username}")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 用户名（不可修改）
        username_label = QLabel(username)
        username_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(QLabel("用户名:"))
        layout.addWidget(username_label)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 角色（只有管理员可以修改）
        role_combo = QComboBox()
        role_combo.addItem("普通用户", "user")
        role_combo.addItem("查看者", "viewer")
        
        current_role = user.get('role', 'user')
        
        # 如果当前用户是管理员，允许修改为管理员
        if self.user_manager.get_current_user_role() == 'admin':
            role_combo.insertItem(0, "管理员", "admin")
            
            # 设置当前角色
            role_index = role_combo.findData(current_role)
            if role_index >= 0:
                role_combo.setCurrentIndex(role_index)
                
            form_layout.addRow("角色:", role_combo)
        else:
            # 非管理员不能修改角色，只显示
            role_label = QLabel({
                'admin': '管理员',
                'user': '普通用户',
                'viewer': '查看者'
            }.get(current_role, current_role))
            form_layout.addRow("角色:", role_label)
        
        # 状态
        status_combo = QComboBox()
        status_combo.addItem("活跃", "active")
        status_combo.addItem("不活跃", "inactive")
        status_combo.addItem("已锁定", "locked")
        
        current_status = user.get('status', 'active')
        status_index = status_combo.findData(current_status)
        if status_index >= 0:
            status_combo.setCurrentIndex(status_index)
            
        form_layout.addRow("状态:", status_combo)
        
        layout.addLayout(form_layout)
        
        # 创建时间（只读）
        created_time = QDateTime.fromSecsSinceEpoch(int(user['created_at'])).toString("yyyy-MM-dd HH:mm")
        form_layout.addRow("创建时间:", QLabel(created_time))
        
        # 最后登录（只读）
        last_login = user.get('last_login', 0)
        if last_login > 0:
            login_time = QDateTime.fromSecsSinceEpoch(int(last_login)).toString("yyyy-MM-dd HH:mm")
        else:
            login_time = "从未登录"
        form_layout.addRow("最后登录:", QLabel(login_time))
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # 显示对话框
        if dialog.exec() == QDialog.Accepted:
            # 收集更新数据
            update_data = {
                'status': status_combo.currentData()
            }
            
            # 只有管理员可以修改角色
            if self.user_manager.get_current_user_role() == 'admin':
                update_data['role'] = role_combo.currentData()
            
            # 更新用户
            if self.user_manager.update_user(username, update_data, current_user):
                self.status_label.setText(f"用户 {username} 更新成功")
            else:
                self.status_label.setText(f"用户 {username} 更新失败")

    @Slot()
    def _delete_user(self, user: Optional[Dict[str, Any]] = None) -> None:
        """删除用户（保持原有方法）"""
        # 如果没有指定用户，使用选中的用户
        if not user:
            with QMutexLocker(self.widget_lock):
                user = self.selected_user
                
        if not user:
            QMessageBox.warning(self, "操作失败", "请先选择一个用户")
            return
            
        username = user['username']
        current_user = self.user_manager.get_current_user()
        
        # 检查权限
        if not current_user:
            QMessageBox.warning(self, "权限不足", "请先登录")
            return
            
        # 确认删除操作
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除用户 {username} 吗？\n"
            f"此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 执行删除
            if self.user_manager.delete_user(username, current_user):
                self.status_label.setText(f"用户 {username} 已删除")
            else:
                self.status_label.setText(f"删除用户 {username} 失败")

    @Slot()
    def _reset_password(self, user: Optional[Dict[str, Any]] = None) -> None:
        """重置用户密码（新增）"""
        # 如果没有指定用户，使用选中的用户
        if not user:
            with QMutexLocker(self.widget_lock):
                user = self.selected_user
                
        if not user:
            QMessageBox.warning(self, "操作失败", "请先选择一个用户")
            return
            
        username = user['username']
        current_user = self.user_manager.get_current_user()
        
        # 检查权限
        if not current_user:
            QMessageBox.warning(self, "权限不足", "请先登录")
            return
            
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"重置密码: {username}")
        dialog.resize(300, 200)
        
        layout = QVBoxLayout(dialog)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 新密码
        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("新密码:", password_input)
        
        # 确认密码
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("确认密码:", confirm_input)
        
        layout.addLayout(form_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("重置")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # 显示对话框
        if dialog.exec() == QDialog.Accepted:
            password = password_input.text()
            confirm = confirm_input.text()
            
            # 验证输入
            if not password:
                QMessageBox.warning(self, "输入错误", "密码不能为空")
                return
                
            if password != confirm:
                QMessageBox.warning(self, "输入错误", "两次输入的密码不一致")
                return
                
            # 重置密码
            if self.user_manager.reset_password(username, password, current_user):
                QMessageBox.information(self, "操作成功", f"用户 {username} 的密码已重置")
                self.status_label.setText(f"用户 {username} 的密码已重置")
            else:
                self.status_label.setText(f"重置用户 {username} 的密码失败")

    @Slot()
    def _change_password(self) -> None:
        """修改当前用户密码（保持原有方法）"""
        current_user = self.user_manager.get_current_user()
        if not current_user:
            QMessageBox.warning(self, "操作失败", "请先登录")
            return
            
        old_pwd = self.old_pwd_input.text()
        new_pwd = self.new_pwd_input.text()
        confirm_pwd = self.confirm_pwd_input.text()
        
        # 验证输入
        if not old_pwd:
            QMessageBox.warning(self, "输入错误", "当前密码不能为空")
            return
            
        if not new_pwd:
            QMessageBox.warning(self, "输入错误", "新密码不能为空")
            return
            
        if new_pwd != confirm_pwd:
            QMessageBox.warning(self, "输入错误", "两次输入的新密码不一致")
            return
            
        # 修改密码
        if self.user_manager.change_password(current_user, old_pwd, new_pwd):
            QMessageBox.information(self, "操作成功", "密码已成功修改，请使用新密码登录")
            
            # 清空输入框
            self.old_pwd_input.clear()
            self.new_pwd_input.clear()
            self.confirm_pwd_input.clear()
        else:
            # 错误信息会通过信号处理
            pass

    @Slot(str, str)
    def _on_user_login(self, username: str, role: str) -> None:
        """处理用户登录（新增）"""
        self._update_current_user_info(username)
        self._load_user_list()
        self._load_action_logs()
        self.status_label.setText(f"用户 {username} 已登录")

    @Slot(str)
    def _on_user_logout(self, username: str) -> None:
        """处理用户登出（新增）"""
        self._update_current_user_info(None)
        self._load_user_list()
        self.status_label.setText(f"用户 {username} 已登出")

    @Slot(str, str)
    def _on_user_created(self, username: str, role: str) -> None:
        """处理用户创建（新增）"""
        self._load_user_list()
        self._load_action_logs()
        self.status_label.setText(f"用户 {username} 已创建 (角色: {role})")

    @Slot(str)
    def _on_user_deleted(self, username: str) -> None:
        """处理用户删除（新增）"""
        self._load_user_list()
        self._load_action_logs()
        self.status_label.setText(f"用户 {username} 已删除")

    @Slot(str, Dict[str, Any])
    def _on_user_updated(self, username: str, user_data: Dict[str, Any]) -> None:
        """处理用户更新（新增）"""
        self._load_user_list()
        self._load_action_logs()
        self.status_label.setText(f"用户 {username} 已更新")

    @Slot(str)
    def _on_password_changed(self, username: str) -> None:
        """处理密码修改（新增）"""
        self._load_action_logs()
        self.status_label.setText(f"用户 {username} 的密码已修改")

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        """处理错误信息（新增）"""
        self.status_label.setText(message)
        QMessageBox.warning(self, "操作失败", message)
