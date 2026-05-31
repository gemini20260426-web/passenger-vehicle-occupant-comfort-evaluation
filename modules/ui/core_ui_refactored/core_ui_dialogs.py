#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 对话框模块
负责所有对话框的显示逻辑
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox
)

from .core_ui_utils import translations


class CoreUIDialogs:
    """对话框管理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

    def show_configuration_dialog(self):
        """显示配置对话框"""
        try:
            from config.config_manager import ConfigManager, ConfigWidget
            config_manager = ConfigManager.instance()
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("系统配置")
            dialog.resize(820, 640)
            dialog.setMinimumSize(700, 500)
            layout = QVBoxLayout(dialog)
            config_widget = ConfigWidget(config_manager, parent=dialog)
            layout.addWidget(config_widget)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self.main_window, "导入错误", f"无法导入配置管理模块:\n{e}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"启动配置管理失败:\n{e}")

    def show_security_dialog(self):
        """显示安全管理对话框"""
        try:
            from modules.ui.security_manager.security_manager import SecurityManager, SecurityDialog
            security_manager = SecurityManager()
            dialog = SecurityDialog(security_manager, self.main_window)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self.main_window, "导入错误", f"无法导入安全管理模块:\n{e}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"启动安全管理失败:\n{e}")

    def show_user_dialog(self):
        """显示用户管理对话框"""
        try:
            from modules.ui.user_manager.user_manager import UserManager, UserDialog
            user_manager = UserManager()
            dialog = UserDialog(user_manager, self.main_window)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self.main_window, "导入错误", f"无法导入用户管理模块:\n{e}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"启动用户管理失败:\n{e}")

    def show_integration_dialog(self):
        """显示系统集成对话框"""
        try:
            from modules.ui.system_integration.integration_widget import ExtensionIntegrationWidget
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("系统集成管理")
            dialog.setMinimumSize(800, 600)

            layout = QVBoxLayout(dialog)
            integration_widget = ExtensionIntegrationWidget()
            layout.addWidget(integration_widget)

            close_button = QPushButton("关闭")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self.main_window, "导入错误", f"无法导入系统集成模块:\n{e}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"启动系统集成失败:\n{e}")

    def show_about_dialog(self):
        """显示关于对话框"""
        QMessageBox.about(
            self.main_window,
            "关于",
            "Core System Dashboard\n\n多源异构数据管理系统\n\n版本: 1.0.0"
        )

    def show_help_dialog(self):
        """显示帮助对话框"""
        main = self.main_window
        help_text = translations.get(main.current_lang, translations['en']).get('help_text', '帮助文档正在编写中...')
        QMessageBox.information(main, "帮助", help_text)
