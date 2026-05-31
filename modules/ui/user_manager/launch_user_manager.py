#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理模块独立启动脚本
"""

import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, project_root)

try:
    from PySide6.QtWidgets import QApplication
    from user_manager import UserManager, UserDialog
    
    def main():
        """主函数"""
        app = QApplication(sys.argv)
        app.setApplicationName("用户管理")
        app.setApplicationVersion("1.0.0")
        
        # 创建用户管理器
        user_manager = UserManager()
        
        # 创建用户管理对话框
        dialog = UserDialog(user_manager)
        dialog.show()
        
        # 运行应用程序
        sys.exit(app.exec())
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装PySide6")
    input("按回车键退出...")
except Exception as e:
    print(f"运行错误: {e}")
    input("按回车键退出...")
