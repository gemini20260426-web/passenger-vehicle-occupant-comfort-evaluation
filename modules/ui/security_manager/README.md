# 安全管理模块

## 概述

安全管理模块提供完整的系统安全管理功能，包括用户认证、权限管理、安全日志等核心功能。

## 功能特性

### 🔐 用户认证
- 用户登录/登出
- 密码哈希加密
- 账户状态管理（活跃/禁用）

### 👥 权限管理
- 角色基础访问控制（RBAC）
- 预定义角色：管理员、普通用户、只读用户
- 细粒度权限控制

### 📊 用户管理
- 添加/编辑/删除用户
- 用户信息管理（姓名、邮箱、部门、职位等）
- 用户搜索功能

### 📝 安全日志
- 完整的操作审计日志
- 登录失败记录
- 用户活动追踪

## 目录结构

```
modules/ui/security_manager/
├── __init__.py                        # 包初始化文件
├── security_manager.py                # 安全管理核心模块
├── launch_security_manager.py         # Python启动脚本
├── launch_security_manager.bat        # Windows批处理启动脚本
├── launch_security_manager.ps1        # PowerShell启动脚本
└── README.md                          # 本文档
```

## 快速开始

### 方法1: 在主应用程序中使用
1. 启动主应用程序 (`core_ui_2.py`)
2. 点击菜单栏 `文件` → `🔒 安全管理` (快捷键: `Ctrl+Shift+S`)

### 方法2: 独立启动安全管理器
```bash
# 在security_manager目录中运行
cd modules/ui/security_manager

# 使用批处理文件
launch_security_manager.bat

# 使用PowerShell脚本
.\launch_security_manager.ps1

# 直接运行Python脚本
python launch_security_manager.py
```

## 默认账户

系统预置了以下默认账户：

| 用户名 | 密码 | 角色 | 描述 |
|--------|------|------|------|
| admin | admin123 | 管理员 | 系统默认管理员账户 |

## 角色权限说明

### 管理员 (admin)
- 拥有所有权限
- 可以管理所有用户
- 可以查看所有安全日志

### 普通用户 (user)
- 基本读写权限
- 可以修改自己的信息
- 可以查看基本功能

### 只读用户 (viewer)
- 仅读取权限
- 不能修改任何数据
- 适合监控和审计用途

## 配置文件

安全管理模块使用JSON格式的配置文件：
- 位置：`config/security.json`
- 包含：用户信息、角色定义、权限配置、安全日志

## 安全特性

- **密码安全**：使用SHA-256哈希算法
- **会话管理**：安全的登录状态管理
- **审计日志**：完整的操作记录
- **权限验证**：严格的访问控制

## 扩展开发

### 添加新权限
在 `SecurityManager` 类中添加新的权限检查方法：

```python
def check_custom_permission(self, permission_name: str) -> bool:
    """检查自定义权限"""
    return self.check_permission(permission_name)
```

### 自定义角色
在 `create_default_roles` 方法中添加新角色：

```python
'custom_role': {
    'name': '自定义角色',
    'permissions': ['read', 'custom_action'],
    'description': '自定义角色描述'
}
```

## 故障排除

### 常见问题

1. **导入错误**
   - 确保PySide6已正确安装
   - 检查Python路径设置

2. **配置文件错误**
   - 检查JSON格式是否正确
   - 确保配置文件有读写权限

3. **权限问题**
   - 确认用户角色设置正确
   - 检查权限配置

### 日志查看

安全管理模块会记录详细的日志信息，可以通过以下方式查看：
- 应用程序日志
- 安全日志文件
- 控制台输出

## 技术支持

如有问题或建议，请联系开发团队。
