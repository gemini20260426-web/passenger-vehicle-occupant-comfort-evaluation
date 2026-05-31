"""用户管理模块（多用户支持与权限控制）"""
import logging
import os
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker

class UserManagement(QObject):
    """用户管理模块（保持原有类名）"""
    # 信号定义（新增状态通知机制）
    user_login = Signal(str, str)        # 用户名, 用户角色
    user_logout = Signal(str)            # 用户名
    user_created = Signal(str, str)      # 用户名, 用户角色
    user_deleted = Signal(str)           # 用户名
    user_updated = Signal(str, Dict[str, Any])  # 用户名, 更新后的信息
    password_changed = Signal(str)       # 用户名
    error_occurred = Signal(str)         # 错误信息

    def __init__(self, data_path: str = "data/users"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.data_path = data_path
        
        # 线程安全锁（新增）
        self.user_lock = QMutex()
        
        # 用户数据存储（保持原有）
        self.users = {}  # {username: user_data}
        self.current_user = None  # 当前登录用户
        
        # 用户操作日志（新增）
        self.action_logs = []
        
        # 初始化（保持原有方法）
        self._init_data_dir()
        self._load_users()

    def _init_data_dir(self) -> None:
        """初始化数据目录（保持原有方法）"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            self.logger.info(f"用户数据目录已初始化: {self.data_path}")
        except Exception as e:
            self.logger.error(f"初始化用户数据目录失败: {str(e)}")
            raise

    def _load_users(self) -> None:
        """加载用户数据（保持原有方法）"""
        try:
            import json
            users_file = os.path.join(self.data_path, "users.json")
            
            if os.path.exists(users_file):
                with open(users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                
                # 验证并加载用户数据
                with QMutexLocker(self.user_lock):
                    for username, user_info in users_data.items():
                        # 基本验证
                        if all(key in user_info for key in ['password_hash', 'role', 'created_at']):
                            self.users[username] = user_info
                        else:
                            self.logger.warning(f"跳过无效用户数据: {username}")
            
            self.logger.info(f"已加载 {len(self.users)} 个用户")
            
            # 检查是否有管理员用户，如果没有则创建默认管理员
            if not any(user['role'] == 'admin' for user in self.users.values()):
                self._create_default_admin()
                
        except Exception as e:
            self.logger.error(f"加载用户数据失败: {str(e)}")

    def _create_default_admin(self) -> None:
        """创建默认管理员用户（保持原有方法）"""
        try:
            # 创建默认管理员，提示用户修改密码
            username = "admin"
            password = "admin123"  # 默认密码，应提示用户修改
            
            with QMutexLocker(self.user_lock):
                if username not in self.users:
                    password_hash = self._hash_password(password)
                    self.users[username] = {
                        'password_hash': password_hash,
                        'role': 'admin',
                        'created_at': datetime.now().timestamp(),
                        'last_login': 0,
                        'status': 'active',
                        'settings': {}
                    }
                    
                    self._save_users()
                    self.logger.warning("已创建默认管理员用户，请尽快修改密码")
                    
        except Exception as e:
            self.logger.error(f"创建默认管理员失败: {str(e)}")

    def _save_users(self) -> None:
        """保存用户数据（保持原有方法）"""
        try:
            import json
            users_file = os.path.join(self.data_path, "users.json")
            
            with QMutexLocker(self.user_lock):
                with open(users_file, 'w', encoding='utf-8') as f:
                    json.dump(self.users, f, ensure_ascii=False, indent=4)
            
            self.logger.info(f"已保存 {len(self.users)} 个用户数据")
            
        except Exception as e:
            self.logger.error(f"保存用户数据失败: {str(e)}")
            self.error_occurred.emit(f"保存用户数据失败: {str(e)}")

    def _hash_password(self, password: str) -> str:
        """密码哈希（保持原有方法）"""
        # 使用盐值哈希增强安全性（新增盐值机制）
        salt = os.urandom(16).hex()
        hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
        return f"{salt}:{hash_obj.hexdigest()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码（保持原有方法）"""
        try:
            # 分离盐值和哈希值
            salt, hash_str = password_hash.split(':')
            # 计算输入密码的哈希
            input_hash = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
            # 比较哈希值
            return input_hash == hash_str
        except Exception as e:
            self.logger.error(f"密码验证失败: {str(e)}")
            return False

    def login(self, username: str, password: str) -> bool:
        """用户登录（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            # 检查用户是否存在
            if username not in self.users:
                self.logger.warning(f"登录失败: 用户 {username} 不存在")
                self.error_occurred.emit(f"登录失败: 用户 {username} 不存在")
                return False
                
            user = self.users[username]
            
            # 检查用户状态
            if user.get('status') != 'active':
                self.logger.warning(f"登录失败: 用户 {username} 已被禁用")
                self.error_occurred.emit(f"登录失败: 用户 {username} 已被禁用")
                return False
                
            # 验证密码
            if not self._verify_password(password, user['password_hash']):
                self.logger.warning(f"登录失败: 用户 {username} 密码错误")
                self.error_occurred.emit(f"登录失败: 密码错误")
                return False
                
            # 更新最后登录时间
            user['last_login'] = datetime.now().timestamp()
            self._save_users()
            
            # 记录当前登录用户
            self.current_user = username
            
            # 记录操作日志
            self._log_action(username, 'login', '用户登录成功')
            
            # 发射登录信号
            self.user_login.emit(username, user['role'])
            self.logger.info(f"用户登录成功: {username} (角色: {user['role']})")
            
            return True

    def logout(self) -> None:
        """用户登出（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            if self.current_user:
                username = self.current_user
                
                # 记录操作日志
                self._log_action(username, 'logout', '用户登出成功')
                
                # 发射登出信号
                self.user_logout.emit(username)
                self.logger.info(f"用户登出成功: {username}")
                
                # 清除当前用户
                self.current_user = None

    def create_user(self, username: str, password: str, role: str = 'user', 
                   creator: str = '') -> bool:
        """创建新用户（保持原有方法）"""
        # 检查权限（新增权限检查）
        if not self._has_permission(creator, 'create_user'):
            self.logger.warning(f"创建用户失败: {creator} 没有权限创建用户")
            self.error_occurred.emit("没有权限创建用户")
            return False
            
        with QMutexLocker(self.user_lock):
            # 检查用户是否已存在
            if username in self.users:
                self.logger.warning(f"创建用户失败: 用户 {username} 已存在")
                self.error_occurred.emit(f"创建用户失败: 用户 {username} 已存在")
                return False
                
            # 验证角色合法性
            if role not in ['admin', 'user', 'viewer']:
                self.logger.warning(f"创建用户失败: 无效角色 {role}")
                self.error_occurred.emit(f"创建用户失败: 无效角色 {role}")
                return False
                
            # 创建用户
            password_hash = self._hash_password(password)
            self.users[username] = {
                'password_hash': password_hash,
                'role': role,
                'created_at': datetime.now().timestamp(),
                'created_by': creator,
                'last_login': 0,
                'status': 'active',
                'settings': {}
            }
            
            # 保存用户数据
            self._save_users()
            
            # 记录操作日志
            self._log_action(creator, 'create_user', f'创建用户 {username} (角色: {role})')
            
            # 发射用户创建信号
            self.user_created.emit(username, role)
            self.logger.info(f"用户创建成功: {username} (角色: {role})")
            
            return True

    def delete_user(self, username: str, operator: str = '') -> bool:
        """删除用户（保持原有方法）"""
        # 检查权限（新增权限检查）
        if not self._has_permission(operator, 'delete_user'):
            self.logger.warning(f"删除用户失败: {operator} 没有权限删除用户")
            self.error_occurred.emit("没有权限删除用户")
            return False
            
        # 防止删除自己
        if username == operator:
            self.logger.warning(f"删除用户失败: 不能删除自己的账户")
            self.error_occurred.emit("不能删除自己的账户")
            return False
            
        # 防止删除最后一个管理员
        with QMutexLocker(self.user_lock):
            admin_users = [u for u, info in self.users.items() if info['role'] == 'admin']
            if username in admin_users and len(admin_users) <= 1:
                self.logger.warning(f"删除用户失败: 不能删除最后一个管理员")
                self.error_occurred.emit("不能删除最后一个管理员")
                return False
                
            # 检查用户是否存在
            if username not in self.users:
                self.logger.warning(f"删除用户失败: 用户 {username} 不存在")
                self.error_occurred.emit(f"删除用户失败: 用户 {username} 不存在")
                return False
                
            # 删除用户
            del self.users[username]
            
            # 如果删除的是当前登录用户，执行登出
            if username == self.current_user:
                self.current_user = None
                
            # 保存用户数据
            self._save_users()
            
            # 记录操作日志
            self._log_action(operator, 'delete_user', f'删除用户 {username}')
            
            # 发射用户删除信号
            self.user_deleted.emit(username)
            self.logger.info(f"用户删除成功: {username}")
            
            return True

    def update_user(self, username: str, user_data: Dict[str, Any], operator: str = '') -> bool:
        """更新用户信息（保持原有方法）"""
        # 检查权限（新增权限检查）
        if not self._has_permission(operator, 'update_user', username):
            self.logger.warning(f"更新用户失败: {operator} 没有权限更新用户 {username}")
            self.error_occurred.emit("没有权限更新用户信息")
            return False
            
        with QMutexLocker(self.user_lock):
            # 检查用户是否存在
            if username not in self.users:
                self.logger.warning(f"更新用户失败: 用户 {username} 不存在")
                self.error_occurred.emit(f"更新用户失败: 用户 {username} 不存在")
                return False
                
            # 过滤允许更新的字段
            allowed_fields = ['role', 'status', 'settings']
            update_data = {k: v for k, v in user_data.items() if k in allowed_fields}
            
            # 特殊处理角色更新
            if 'role' in update_data:
                # 检查是否是最后一个管理员
                if self.users[username]['role'] == 'admin' and update_data['role'] != 'admin':
                    admin_users = [u for u, info in self.users.items() if info['role'] == 'admin']
                    if len(admin_users) <= 1:
                        self.logger.warning(f"更新用户失败: 不能移除最后一个管理员的权限")
                        self.error_occurred.emit("不能移除最后一个管理员的权限")
                        del update_data['role']  # 移除角色更新
            
            # 应用更新
            self.users[username].update(update_data)
            
            # 保存用户数据
            self._save_users()
            
            # 记录操作日志
            self._log_action(operator, 'update_user', f'更新用户 {username} 信息: {update_data.keys()}')
            
            # 发射用户更新信号
            self.user_updated.emit(username, self.users[username].copy())
            self.logger.info(f"用户更新成功: {username}")
            
            return True

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            # 检查用户是否存在
            if username not in self.users:
                self.logger.warning(f"修改密码失败: 用户 {username} 不存在")
                self.error_occurred.emit(f"修改密码失败: 用户 {username} 不存在")
                return False
                
            # 验证旧密码
            if not self._verify_password(old_password, self.users[username]['password_hash']):
                self.logger.warning(f"修改密码失败: 用户 {username} 旧密码错误")
                self.error_occurred.emit("修改密码失败: 旧密码错误")
                return False
                
            # 更新密码
            self.users[username]['password_hash'] = self._hash_password(new_password)
            self.users[username]['password_changed_at'] = datetime.now().timestamp()
            
            # 保存用户数据
            self._save_users()
            
            # 记录操作日志
            self._log_action(username, 'change_password', '修改密码成功')
            
            # 发射密码修改信号
            self.password_changed.emit(username)
            self.logger.info(f"用户密码修改成功: {username}")
            
            return True

    def reset_password(self, username: str, new_password: str, operator: str = '') -> bool:
        """重置用户密码（管理员功能，新增）"""
        # 检查权限
        if not self._has_permission(operator, 'reset_password'):
            self.logger.warning(f"重置密码失败: {operator} 没有权限重置密码")
            self.error_occurred.emit("没有权限重置密码")
            return False
            
        with QMutexLocker(self.user_lock):
            # 检查用户是否存在
            if username not in self.users:
                self.logger.warning(f"重置密码失败: 用户 {username} 不存在")
                self.error_occurred.emit(f"重置密码失败: 用户 {username} 不存在")
                return False
                
            # 更新密码
            self.users[username]['password_hash'] = self._hash_password(new_password)
            self.users[username]['password_changed_at'] = datetime.now().timestamp()
            self.users[username]['password_reset_by'] = operator
            
            # 保存用户数据
            self._save_users()
            
            # 记录操作日志
            self._log_action(operator, 'reset_password', f'重置用户 {username} 密码')
            
            # 发射密码修改信号
            self.password_changed.emit(username)
            self.logger.info(f"用户密码重置成功: {username} (操作人: {operator})")
            
            return True

    def get_user_list(self) -> List[Dict[str, Any]]:
        """获取用户列表（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            user_list = []
            for username, user_info in self.users.items():
                # 复制并移除敏感信息
                user_data = user_info.copy()
                user_data.pop('password_hash', None)  # 不返回密码哈希
                user_data['username'] = username
                user_list.append(user_data)
            return user_list

    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户信息（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            if username in self.users:
                # 复制并移除敏感信息
                user_info = self.users[username].copy()
                user_info.pop('password_hash', None)  # 不返回密码哈希
                user_info['username'] = username
                return user_info
            return None

    def get_current_user(self) -> Optional[str]:
        """获取当前登录用户（保持原有方法）"""
        with QMutexLocker(self.user_lock):
            return self.current_user

    def get_current_user_role(self) -> Optional[str]:
        """获取当前登录用户角色（新增）"""
        with QMutexLocker(self.user_lock):
            if self.current_user and self.current_user in self.users:
                return self.users[self.current_user].get('role')
            return None

    def _has_permission(self, username: str, action: str, target_user: str = None) -> bool:
        """检查用户是否有指定操作的权限（新增权限控制）"""
        # 未登录用户没有任何权限
        if not username:
            return False
            
        # 获取用户角色
        user_role = self.users.get(username, {}).get('role', '')
        
        # 管理员拥有所有权限
        if user_role == 'admin':
            return True
            
        # 用户只能管理自己的部分信息
        if user_role == 'user':
            if action == 'update_user' and target_user == username:
                return True  # 允许用户更新自己的非角色信息
            if action == 'change_password' and target_user == username:
                return True  # 允许用户修改自己的密码
            return False
            
        # 查看者只有有限的查看权限
        if user_role == 'viewer':
            return action in ['view_data', 'view_reports']
            
        return False

    def _log_action(self, username: str, action: str, details: str) -> None:
        """记录用户操作日志（新增）"""
        log_entry = {
            'id': str(uuid.uuid4()),
            'username': username,
            'action': action,
            'details': details,
            'timestamp': datetime.now().timestamp(),
            'ip_address': 'unknown'  # 实际应用中可以记录IP地址
        }
        
        with QMutexLocker(self.user_lock):
            self.action_logs.append(log_entry)
            
            # 限制日志数量，只保留最近1000条
            if len(self.action_logs) > 1000:
                self.action_logs = self.action_logs[-1000:]
            
            # 保存日志到文件
            self._save_action_logs()

    def _save_action_logs(self) -> None:
        """保存操作日志到文件（新增）"""
        try:
            import json
            logs_file = os.path.join(self.data_path, "action_logs.json")
            
            with open(logs_file, 'w', encoding='utf-8') as f:
                json.dump(self.action_logs, f, ensure_ascii=False, indent=4)
                
        except Exception as e:
            self.logger.error(f"保存操作日志失败: {str(e)}")

    def get_action_logs(self, limit: int = 100, username: str = None) -> List[Dict[str, Any]]:
        """获取操作日志（新增）"""
        with QMutexLocker(self.user_lock):
            logs = self.action_logs.copy()
            
            # 按用户筛选
            if username:
                logs = [log for log in logs if log['username'] == username]
                
            # 按时间排序（最新的在前）
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # 限制数量
            return logs[:limit]
