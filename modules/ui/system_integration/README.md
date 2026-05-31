# 系统集成模块 (System Integration Module)

## 概述

系统集成模块提供了完整的系统扩展与集成功能，包括API接口管理、插件管理和第三方服务集成。

## 功能特性

### 🔌 API接口管理
- **API服务器控制**：启动/停止API服务器
- **端口配置**：可配置的API服务端口
- **状态监控**：实时显示API服务器运行状态
- **API文档**：内置API接口文档查看

### 🔌 插件管理
- **插件列表**：显示已安装和可用的插件
- **插件控制**：加载/卸载/重新加载插件
- **插件安装**：支持新插件的安装
- **插件信息**：显示插件的详细信息和状态

### 🔌 第三方服务集成
- **GPS轨迹服务**：GPS数据追踪服务集成
- **驾驶分析服务**：驾驶行为分析服务
- **通知推送服务**：实时通知和推送服务
- **服务配置**：每个服务的详细配置选项
- **连接管理**：服务的连接/断开控制
- **数据同步**：与服务的数据同步功能

## 文件结构

```
system_integration/
├── __init__.py              # 模块初始化文件
├── integration_widget.py    # 主要的UI组件
└── README.md               # 说明文档
```

## 使用方法

### 在主应用程序中访问
1. 启动主应用程序 (`core_ui_2.py`)
2. 在 `File` 菜单中选择 "🔗 系统集成"
3. 使用快捷键 `Ctrl+Shift+I`

### 独立运行
```python
from modules.ui.system_integration import ExtensionIntegrationWidget

app = QApplication(sys.argv)
widget = ExtensionIntegrationWidget()
widget.show()
sys.exit(app.exec())
```

## 信号说明

### 输入信号
- `save_config(service_id, config)`：保存服务配置
- `connect_service(service_id)`：连接指定服务
- `disconnect_service(service_id)`：断开指定服务
- `sync_data(service_id)`：同步服务数据
- `start_api_server(port)`：启动API服务器
- `stop_api_server()`：停止API服务器

### 输出信号
- 所有信号都会发送到主控制器进行处理

## 配置说明

### API服务器配置
- 默认端口：5000
- 端口范围：1024-65535
- 支持动态启动/停止

### 插件配置
- 插件目录：`modules/ui/system_integration/plugins/`
- 支持Python插件文件 (*.py)
- 自动创建插件目录

### 服务配置
- API地址配置
- API密钥配置
- 同步间隔配置（可选）
- 服务启用/禁用状态

## 注意事项

1. **插件管理**：确保插件文件格式正确，避免导入错误
2. **服务配置**：API密钥等敏感信息请妥善保管
3. **端口冲突**：确保API端口不被其他服务占用
4. **权限要求**：某些功能可能需要管理员权限

## 扩展开发

### 添加新服务
1. 在 `_create_services_tab()` 方法中添加新服务行
2. 实现相应的配置和连接逻辑
3. 更新服务状态管理

### 添加新插件类型
1. 扩展插件加载机制
2. 添加插件验证逻辑
3. 实现插件依赖管理

## 版本信息

- **版本**：1.0.0
- **作者**：Core System Team
- **更新日期**：2025-08-13
