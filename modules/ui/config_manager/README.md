# 配置管理模块

## 目录结构

```
modules/ui/config_manager/
├── __init__.py                        # 包初始化文件
├── configuration_manager.py            # 配置管理核心模块
├── launch_config_manager.py           # Python启动脚本
├── launch_config_manager.bat          # Windows批处理启动脚本
├── launch_config_manager.ps1          # PowerShell启动脚本
├── README.md                          # 本文档
├── 配置管理系统使用说明.md            # 详细使用说明
└── 配置管理解决方案总结.md            # 解决方案总结
```

## 快速开始

### 方法1: 在主应用程序中使用
1. 启动主应用程序 (`core_ui_2.py`)
2. 点击菜单栏 `文件` → `⚙️ 配置管理` (快捷键: `Ctrl+Shift+C`)

### 方法2: 独立启动配置管理器
```bash
# 在config_manager目录中运行
cd modules/ui/config_manager

# 使用批处理文件
launch_config_manager.bat

# 使用PowerShell脚本
.\launch_config_manager.ps1

# 直接运行Python脚本
python launch_config_manager.py
```

## 模块导入

在主应用程序中，配置管理模块通过以下方式导入：

```python
from .config_manager import ConfigManager, ConfigurationDialog
```

## 配置文件路径

配置文件路径设置为：`config/config.ini`（相对于项目根目录）

## 注意事项

- 所有启动脚本已更新为正确的项目根目录路径
- 导入路径已更新为新的包结构
- 配置文件路径保持相对路径，确保跨平台兼容性

