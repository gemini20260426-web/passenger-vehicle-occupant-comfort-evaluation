# 用户管理模块

## 概述

用户管理模块提供完整的用户管理功能，包括用户信息管理、用户偏好设置、用户活动记录等核心功能。

## 功能特性

### 👥 用户信息管理
- 添加/编辑/删除用户
- 用户基本信息（姓名、邮箱、电话、部门、职位等）
- 用户状态管理（活跃/非活跃）
- 用户搜索和筛选

### ⚙️ 用户偏好设置
- 界面主题设置（浅色/深色/自动）
- 语言设置（中文/英文）
- 字体大小调整
- 自动保存选项
- 通知设置
- 时区设置

### 📊 用户统计
- 总用户数统计
- 活跃用户统计
- 按部门统计
- 用户活动记录

### 📝 活动记录
- 用户操作日志
- 登录时间记录
- 活动类型分类
- 时间戳记录

## 目录结构

```
modules/ui/user_manager/
├── __init__.py                        # 包初始化文件
├── user_manager.py                    # 用户管理核心模块
├── launch_user_manager.py             # Python启动脚本
├── launch_user_manager.bat            # Windows批处理启动脚本
├── launch_user_manager.ps1            # PowerShell启动脚本
└── README.md                          # 本文档
```

## 快速开始

### 方法1: 在主应用程序中使用
1. 启动主应用程序 (`core_ui_2.py`)
2. 点击菜单栏 `文件` → `👥 用户管理` (快捷键: `Ctrl+Shift+U`)

### 方法2: 独立启动用户管理器
```bash
# 在user_manager目录中运行
cd modules/ui/user_manager

# 使用批处理文件
launch_user_manager.bat

# 使用PowerShell脚本
.\launch_user_manager.ps1

# 直接运行Python脚本
python launch_user_manager.py
```

## 默认用户

系统预置了以下默认用户：

| 用户名 | 姓名 | 邮箱 | 部门 | 职位 | 状态 |
|--------|------|------|------|------|------|
| admin | 系统管理员 | admin@example.com | IT部门 | 系统管理员 | 活跃 |
| user1 | 测试用户1 | user1@example.com | 测试部门 | 测试工程师 | 活跃 |

## 用户偏好设置说明

### 主题设置
- **浅色主题**：适合白天使用，界面明亮清晰
- **深色主题**：适合夜间使用，减少眼睛疲劳
- **自动主题**：根据系统时间自动切换

### 语言设置
- **中文 (zh_CN)**：简体中文界面
- **英文 (en_US)**：英文界面

### 字体大小
- 范围：8-20像素
- 默认：12像素
- 支持实时预览

### 其他设置
- **自动保存**：自动保存用户操作
- **通知**：启用/禁用系统通知
- **时区**：设置用户所在时区

## 配置文件

用户管理模块使用JSON格式的配置文件：
- 位置：`config/users.json`
- 包含：用户信息、用户偏好、活动记录

## 功能详解

### 用户搜索
支持多种搜索条件：
- 用户名
- 真实姓名
- 邮箱地址
- 部门名称

### 用户详情
显示用户的完整信息：
- 基本信息
- 创建时间
- 最后活动时间
- 备注信息

### 用户活动
记录用户的各种操作：
- 登录/登出
- 信息修改
- 偏好设置更改
- 其他操作

## 扩展开发

### 添加新用户字段
在 `UserManager` 类中添加新的用户属性：

```python
def add_user(self, user_data: Dict[str, Any]) -> bool:
    # 添加新字段
    user_data['new_field'] = user_data.get('new_field', 'default_value')
    # ... 其他代码
```

### 自定义用户偏好
在 `UserPreferencesDialog` 中添加新的偏好选项：

```python
def setup_ui(self):
    # 添加新的偏好控件
    self.new_preference = QComboBox()
    self.new_preference.addItems(['option1', 'option2', 'option3'])
    form_layout.addRow("新偏好:", self.new_preference)
```

### 扩展活动记录
在 `record_user_activity` 方法中添加新的活动类型：

```python
def record_user_activity(self, username: str, activity_type: str, description: str):
    # 支持新的活动类型
    if activity_type == 'custom_action':
        # 特殊处理逻辑
        pass
    # ... 其他代码
```

## 数据导入导出

### 导出用户数据
- 格式：JSON
- 包含：用户信息、偏好设置、活动记录
- 用途：备份、迁移、分析

### 导入用户数据
- 支持JSON格式
- 数据验证和冲突处理
- 批量导入支持

## 故障排除

### 常见问题

1. **用户创建失败**
   - 检查用户名是否重复
   - 确认必填字段已填写
   - 检查文件权限

2. **偏好设置不生效**
   - 确认设置已保存
   - 检查配置文件格式
   - 重启应用程序

3. **搜索功能异常**
   - 检查搜索关键词
   - 确认数据完整性
   - 查看错误日志

### 日志查看

用户管理模块会记录详细的操作日志：
- 用户操作记录
- 系统错误信息
- 性能统计信息

## 性能优化

### 数据缓存
- 用户信息缓存
- 偏好设置缓存
- 活动记录分页

### 搜索优化
- 索引优化
- 模糊匹配
- 结果排序

## 安全考虑

- 用户数据加密存储
- 访问权限控制
- 操作审计日志
- 数据备份恢复

## 技术支持

如有问题或建议，请联系开发团队。
