#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理启动脚本
独立启动配置管理模块，用于测试和独立使用
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def main():
    """主函数"""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setApplicationName("配置管理系统")
        app.setApplicationVersion("1.0.0")
        
        # 设置应用程序属性
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 导入配置管理模块
        from .configuration_manager import ConfigManager, ConfigurationDialog
        
        # 创建配置管理器
        config_file = os.path.join(project_root, "config", "config.ini")
        config_manager = ConfigManager(config_file)
        
        # 创建配置对话框
        dialog = ConfigurationDialog(config_manager)
        dialog.show()
        
        # 运行应用程序
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装 PySide6: pip install PySide6")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
