"""
样式管理器 - 统一UI样式规范
提供统一的配色、间距、组件尺寸管理
"""

from dataclasses import dataclass
from typing import Dict, Any
from PySide6.QtWidgets import QPushButton, QLabel, QFrame
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

@dataclass
class ProfessionalColors:
    """专业配色方案"""
    # 主色调
    primary: str = '#6366f1'
    primary_hover: str = '#4f46e5'
    secondary: str = '#8b5cf6'
    
    # 功能色
    success: str = '#10b981'
    warning: str = '#f59e0b'
    error: str = '#ef4444'
    info: str = '#3b82f6'
    
    # 数据色系
    imu_data: str = '#8b5cf6'
    cnap_data: str = '#10b981'
    fusion_data: str = '#f59e0b'
    mqtt_data: str = '#3b82f6'
    
    # 状态色
    connected: str = '#10b981'
    disconnected: str = '#6b7280'
    connecting: str = '#f59e0b'
    
    # 背景色
    bg_dark: str = '#1e1e2e'
    bg_medium: str = '#2d2d3f'
    bg_light: str = '#3d3d5f'
    
    # 文字色
    text_primary: str = '#f1f5f9'
    text_secondary: str = '#94a3b8'
    text_disabled: str = '#64748b'

@dataclass
class Spacing:
    """间距规范"""
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32

@dataclass
class Sizes:
    """组件尺寸规范"""
    btn_height: int = 36
    input_height: int = 32
    panel_padding: int = 16
    card_radius: int = 8
    header_height: int = 48

class StyleManager:
    """样式管理器单例"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.colors = ProfessionalColors()
            cls._instance.spacing = Spacing()
            cls._instance.sizes = Sizes()
        return cls._instance
    
    def get_button_style(self, button_type: str = 'primary') -> str:
        """获取按钮样式"""
        colors = self.colors
        
        if button_type == 'primary':
            return f"""
                QPushButton {{
                    background-color: {colors.primary};
                    color: {colors.text_primary};
                    border: none;
                    border-radius: {self.sizes.card_radius}px;
                    padding: 8px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: {colors.primary_hover};
                }}
                QPushButton:pressed {{
                    background-color: {colors.secondary};
                }}
                QPushButton:disabled {{
                    background-color: {colors.text_disabled};
                    color: {colors.text_secondary};
                }}
            """
        elif button_type == 'success':
            return f"""
                QPushButton {{
                    background-color: {colors.success};
                    color: {colors.text_primary};
                    border: none;
                    border-radius: {self.sizes.card_radius}px;
                    padding: 8px 20px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #0d9668;
                }}
            """
        elif button_type == 'danger':
            return f"""
                QPushButton {{
                    background-color: {colors.error};
                    color: {colors.text_primary};
                    border: none;
                    border-radius: {self.sizes.card_radius}px;
                    padding: 8px 20px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #dc2626;
                }}
            """
        else:  # secondary
            return f"""
                QPushButton {{
                    background-color: {colors.bg_medium};
                    color: {colors.text_primary};
                    border: 1px solid {colors.bg_light};
                    border-radius: {self.sizes.card_radius}px;
                    padding: 8px 20px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {colors.bg_light};
                }}
            """
    
    def get_card_style(self) -> str:
        """获取卡片样式"""
        colors = self.colors
        return f"""
            QFrame {{
                background-color: {colors.bg_medium};
                border-radius: {self.sizes.card_radius}px;
                border: 1px solid {colors.bg_light};
            }}
        """
    
    def get_input_style(self) -> str:
        """获取输入框样式"""
        colors = self.colors
        return f"""
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: {colors.bg_light};
                color: {colors.text_primary};
                border: 1px solid {colors.bg_dark};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                min-height: {self.sizes.input_height}px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 2px solid {colors.primary};
            }}
        """
    
    def get_label_style(self, label_type: str = 'normal') -> str:
        """获取标签样式"""
        colors = self.colors
        
        if label_type == 'header':
            return f"""
                QLabel {{
                    color: {colors.text_primary};
                    font-size: 18px;
                    font-weight: 700;
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                }}
            """
        elif label_type == 'subheader':
            return f"""
                QLabel {{
                    color: {colors.text_primary};
                    font-size: 14px;
                    font-weight: 600;
                }}
            """
        else:
            return f"""
                QLabel {{
                    color: {colors.text_secondary};
                    font-size: 13px;
                }}
            """
    
    def apply_button_style(self, button: QPushButton, button_type: str = 'primary'):
        """应用按钮样式"""
        button.setStyleSheet(self.get_button_style(button_type))
        button.setMinimumHeight(self.sizes.btn_height)
    
    def apply_card_style(self, frame: QFrame):
        """应用卡片样式"""
        frame.setStyleSheet(self.get_card_style())
        frame.setFrameShape(QFrame.Shape.StyledPanel)


# 全局样式管理器实例
style_manager = StyleManager()

# 导出常量供其他模块使用
PRO_COLORS = style_manager.colors
SPACING = style_manager.spacing
SIZES = style_manager.sizes
