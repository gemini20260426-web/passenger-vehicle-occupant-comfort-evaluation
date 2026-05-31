#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 创建日期: 2026-05-03
# 用途: 专业UI样式系统 - 深色主题 + 现代设计
# ============================================================

PRO_COLORS = {
    'bg_primary': '#0f1117',
    'bg_secondary': '#161822',
    'bg_card': '#1a1d2e',
    'bg_card_hover': '#1e2137',
    'bg_input': '#12141f',
    'bg_header': '#0d0f15',
    'bg_sidebar': '#111318',

    'accent': '#4f8cff',
    'accent_hover': '#6ba0ff',
    'accent_light': 'rgba(79, 140, 255, 0.15)',
    'accent_glow': 'rgba(79, 140, 255, 0.3)',

    'text_primary': '#e8eaed',
    'text_secondary': '#9aa0b0',
    'text_muted': '#5f6570',
    'text_accent': '#4f8cff',

    'border_default': '#252836',
    'border_light': '#2a2d3a',
    'border_accent': '#4f8cff',

    'success': '#34d399',
    'warning': '#fbbf24',
    'danger': '#f87171',
    'info': '#60a5fa',

    'gradient_header': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d0f15, stop:0.5 #111827, stop:1 #0d0f15)',
    'gradient_accent': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f8cff, stop:1 #7c3aed)',
}

PRO_GLOBAL_STYLE = f"""
* {{
    color: {PRO_COLORS['text_primary']};
    font-family: 'Microsoft YaHei', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
    font-size: 12px;
}}

QMainWindow {{
    background-color: {PRO_COLORS['bg_primary']};
}}

QWidget {{
    background-color: transparent;
    color: {PRO_COLORS['text_primary']};
    font-family: 'Microsoft YaHei', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
    font-size: 12px;
}}

QFrame {{
    background-color: transparent;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QMenuBar {{
    background-color: {PRO_COLORS['bg_header']};
    color: {PRO_COLORS['text_secondary']};
    border-bottom: 1px solid {PRO_COLORS['border_default']};
    padding: 2px 0px;
    font-size: 12px;
}}

QMenuBar::item {{
    padding: 6px 12px;
    background: transparent;
    border-radius: 4px;
    margin: 2px 2px;
}}

QMenuBar::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QMenu {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QMenu::separator {{
    height: 1px;
    background: {PRO_COLORS['border_default']};
    margin: 4px 8px;
}}

QTabWidget::pane {{
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    background-color: {PRO_COLORS['bg_secondary']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {PRO_COLORS['bg_card']};
    color: {PRO_COLORS['text_secondary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {PRO_COLORS['bg_secondary']};
    color: {PRO_COLORS['text_accent']};
    border-bottom: 2px solid {PRO_COLORS['accent']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {PRO_COLORS['bg_card_hover']};
    color: {PRO_COLORS['text_primary']};
}}

QGroupBox {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-size: 12px;
    font-weight: 600;
    color: {PRO_COLORS['text_primary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {PRO_COLORS['text_primary']};
    background-color: {PRO_COLORS['bg_card']};
    border-radius: 4px;
}}

QPushButton {{
    background-color: {PRO_COLORS['accent']};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {PRO_COLORS['accent_hover']};
}}

QPushButton:pressed {{
    background-color: #3b7ae0;
}}

QPushButton:disabled {{
    background-color: #2a2d3a;
    color: #5f6570;
}}

QLineEdit {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    selection-background-color: {PRO_COLORS['accent_light']};
}}

QLineEdit:focus {{
    border-color: {PRO_COLORS['accent']};
}}

QLineEdit:hover:!focus {{
    border-color: {PRO_COLORS['border_light']};
}}

QComboBox {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {PRO_COLORS['border_light']};
}}

QComboBox:focus {{
    border-color: {PRO_COLORS['accent']};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {PRO_COLORS['bg_card']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    selection-background-color: {PRO_COLORS['accent_light']};
    selection-color: {PRO_COLORS['text_accent']};
    padding: 4px;
}}

QTextEdit {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px;
    font-size: 12px;
    font-family: 'Consolas', 'Courier New', 'Microsoft YaHei', monospace;
}}

QProgressBar {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 4px;
    text-align: center;
    color: {PRO_COLORS['text_primary']};
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background: {PRO_COLORS['gradient_accent']};
    border-radius: 3px;
}}

QSlider::groove:horizontal {{
    background: {PRO_COLORS['bg_input']};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {PRO_COLORS['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: {PRO_COLORS['accent_hover']};
}}

QCheckBox {{
    color: {PRO_COLORS['text_secondary']};
    spacing: 8px;
    font-size: 12px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 3px;
    background-color: {PRO_COLORS['bg_input']};
}}

QCheckBox::indicator:checked {{
    background-color: {PRO_COLORS['accent']};
    border-color: {PRO_COLORS['accent']};
}}

QScrollBar:vertical {{
    background: {PRO_COLORS['bg_primary']};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {PRO_COLORS['border_light']};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {PRO_COLORS['text_muted']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {PRO_COLORS['bg_primary']};
    height: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {PRO_COLORS['border_light']};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {PRO_COLORS['text_muted']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QSplitter::handle {{
    background-color: {PRO_COLORS['border_default']};
    width: 1px;
}}

QSplitter::handle:hover {{
    background-color: {PRO_COLORS['accent']};
}}

QStatusBar {{
    background-color: {PRO_COLORS['bg_header']};
    color: {PRO_COLORS['text_secondary']};
    border-top: 1px solid {PRO_COLORS['border_default']};
    font-size: 11px;
    padding: 4px 12px;
}}

QToolTip {{
    background-color: {PRO_COLORS['bg_card']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}

QTableWidget {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    gridline-color: {PRO_COLORS['border_default']};
}}

QTableWidget::item {{
    padding: 6px;
    color: {PRO_COLORS['text_primary']};
    font-size: 11px;
}}

QTableWidget::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QHeaderView::section {{
    background-color: {PRO_COLORS['bg_card']};
    color: {PRO_COLORS['text_secondary']};
    padding: 8px;
    font-size: 11px;
    font-weight: 600;
    border-bottom: 1px solid {PRO_COLORS['border_default']};
}}

QLabel {{
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {PRO_COLORS['bg_card']};
    border: none;
}}

QTreeWidget {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
}}

QTreeWidget::item {{
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
}}

QTreeWidget::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QListWidget {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
}}

QListWidget::item {{
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
    padding: 6px;
}}

QListWidget::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QFrame#dashboardCard {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 10px;
    padding: 16px;
}}

QFrame#dashboardCard:hover {{
    border-color: {PRO_COLORS['accent']};
    background-color: {PRO_COLORS['bg_card_hover']};
}}

QLabel#metricTitle {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#metricValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 28px;
    font-weight: 800;
}}

QLabel#metricValueAccent {{
    color: {PRO_COLORS['accent']};
    font-size: 28px;
    font-weight: 800;
}}

QLabel#metricValueSuccess {{
    color: {PRO_COLORS['success']};
    font-size: 28px;
    font-weight: 800;
}}

QLabel#metricValueWarning {{
    color: {PRO_COLORS['warning']};
    font-size: 28px;
    font-weight: 800;
}}

QLabel#metricValueDanger {{
    color: {PRO_COLORS['danger']};
    font-size: 28px;
    font-weight: 800;
}}

QLabel#metricSub {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
}}

QLabel#statusBadge {{
    background-color: {PRO_COLORS['success']};
    color: #ffffff;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
}}

QLabel#statusBadgeWarning {{
    background-color: {PRO_COLORS['warning']};
    color: #1a1a1a;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
}}

QLabel#statusBadgeDanger {{
    background-color: {PRO_COLORS['danger']};
    color: #ffffff;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
}}

QLabel#statusBadgeMuted {{
    background-color: {PRO_COLORS['border_light']};
    color: {PRO_COLORS['text_muted']};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
}}

QLabel#sectionTitle {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
    padding: 4px 0px;
}}

QLabel#sectionDesc {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    padding: 0px 0px 8px 0px;
}}

QFrame#separatorH {{
    background-color: {PRO_COLORS['border_default']};
    min-height: 1px;
    max-height: 1px;
}}

QFrame#separatorV {{
    background-color: {PRO_COLORS['border_default']};
    min-width: 1px;
    max-width: 1px;
}}

QPushButton#btnSuccess {{
    background-color: {PRO_COLORS['success']};
    color: #1a1a1a;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#btnSuccess:hover {{
    background-color: #2ecc71;
}}

QPushButton#btnWarning {{
    background-color: {PRO_COLORS['warning']};
    color: #1a1a1a;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#btnWarning:hover {{
    background-color: #f59e0b;
}}

QPushButton#btnDanger {{
    background-color: {PRO_COLORS['danger']};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#btnDanger:hover {{
    background-color: #ef4444;
}}

QPushButton#btnOutline {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#btnOutline:hover {{
    background-color: {PRO_COLORS['bg_card_hover']};
    border-color: {PRO_COLORS['accent']};
    color: {PRO_COLORS['text_accent']};
}}

QPushButton#btnGhost {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}}

QPushButton#btnGhost:hover {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QTableWidget#syncSourcesTable {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    gridline-color: transparent;
    alternate-background-color: {PRO_COLORS['bg_card']};
}}

QTableWidget#syncSourcesTable::item {{
    padding: 10px 12px;
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
    border-bottom: 1px solid {PRO_COLORS['border_default']};
}}

QTableWidget#syncSourcesTable::item:selected {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QHeaderView#syncSourcesHeader::section {{
    background-color: {PRO_COLORS['bg_card']};
    color: {PRO_COLORS['text_muted']};
    padding: 10px 12px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    border: none;
    border-bottom: 2px solid {PRO_COLORS['border_default']};
}}

QGroupBox#compactGroup {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-size: 11px;
    font-weight: 600;
}}

QGroupBox#compactGroup::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {PRO_COLORS['text_secondary']};
    background-color: {PRO_COLORS['bg_card']};
    border-radius: 4px;
}}

QLabel#logTimestamp {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
}}

QLabel#logInfo {{
    color: {PRO_COLORS['text_secondary']};
    font-size: 11px;
}}

QLabel#logSuccess {{
    color: {PRO_COLORS['success']};
    font-size: 11px;
}}

QLabel#logWarning {{
    color: {PRO_COLORS['warning']};
    font-size: 11px;
}}

QLabel#logError {{
    color: {PRO_COLORS['danger']};
    font-size: 11px;
}}

QFrame#panelCard {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 10px;
    padding: 14px;
}}

QFrame#panelCard:hover {{
    border-color: {PRO_COLORS['border_light']};
}}

QLabel#panelTitle {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
    padding-bottom: 4px;
}}

QLabel#panelSubtitle {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    padding-bottom: 8px;
}}

QLabel#statLabel {{
    color: {PRO_COLORS['text_secondary']};
    font-size: 11px;
}}

QLabel#statValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#statValueAccent {{
    color: {PRO_COLORS['accent']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#statValueSuccess {{
    color: {PRO_COLORS['success']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#statValueWarning {{
    color: {PRO_COLORS['warning']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#statValueDanger {{
    color: {PRO_COLORS['danger']};
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#btnSmall {{
    background-color: {PRO_COLORS['accent']};
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton#btnSmall:hover {{
    background-color: {PRO_COLORS['accent_hover']};
}}

QPushButton#btnSmallOutline {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton#btnSmallOutline:hover {{
    background-color: {PRO_COLORS['bg_card_hover']};
    border-color: {PRO_COLORS['accent']};
    color: {PRO_COLORS['text_accent']};
}}

QPushButton#btnIconOnly {{
    background-color: transparent;
    color: {PRO_COLORS['text_muted']};
    border: none;
    border-radius: 4px;
    padding: 4px;
    font-size: 14px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}}

QPushButton#btnIconOnly:hover {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QTabWidget#innerTabs::pane {{
    border: none;
    background-color: transparent;
}}

QTabWidget#innerTabs QTabBar::tab {{
    background-color: transparent;
    color: {PRO_COLORS['text_muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 500;
    margin-right: 0px;
}}

QTabWidget#innerTabs QTabBar::tab:selected {{
    color: {PRO_COLORS['text_accent']};
    border-bottom: 2px solid {PRO_COLORS['accent']};
}}

QTabWidget#innerTabs QTabBar::tab:hover:!selected {{
    color: {PRO_COLORS['text_primary']};
}}

QFrame#statusDotGreen {{
    background-color: {PRO_COLORS['success']};
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
}}

QFrame#statusDotYellow {{
    background-color: {PRO_COLORS['warning']};
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
}}

QFrame#statusDotRed {{
    background-color: {PRO_COLORS['danger']};
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
}}

QFrame#statusDotGray {{
    background-color: {PRO_COLORS['text_muted']};
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
}}

QFrame#miniCard {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    padding: 10px 12px;
}}

QFrame#miniCard:hover {{
    border-color: {PRO_COLORS['accent']};
    background-color: {PRO_COLORS['bg_card']};
}}

QLabel#miniCardTitle {{
    color: {PRO_COLORS['text_muted']};
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QLabel#miniCardValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#miniCardValueAccent {{
    color: {PRO_COLORS['accent']};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#miniCardValueSuccess {{
    color: {PRO_COLORS['success']};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#miniCardValueWarning {{
    color: {PRO_COLORS['warning']};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#miniCardValueDanger {{
    color: {PRO_COLORS['danger']};
    font-size: 18px;
    font-weight: 700;
}}

QGroupBox#panelGroup {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-size: 12px;
    font-weight: 600;
    color: {PRO_COLORS['text_primary']};
}}

QGroupBox#panelGroup::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {PRO_COLORS['text_primary']};
    background-color: {PRO_COLORS['bg_card']};
    border-radius: 4px;
}}

QFormLayout#compactForm {{
    spacing: 4px;
}}

QLabel#formLabel {{
    color: {PRO_COLORS['text_secondary']};
    font-size: 11px;
    font-weight: 500;
}}

QLabel#formValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 11px;
    font-weight: 600;
}}

QProgressBar#miniProgress {{
    background-color: {PRO_COLORS['bg_input']};
    border: none;
    border-radius: 3px;
    text-align: center;
    color: {PRO_COLORS['text_primary']};
    font-size: 9px;
    height: 12px;
    min-height: 12px;
    max-height: 12px;
}}

QProgressBar#miniProgress::chunk {{
    background: {PRO_COLORS['gradient_accent']};
    border-radius: 3px;
}}

QWidget#leftPanelContainer {{
    background-color: {PRO_COLORS['bg_secondary']};
    border-right: 1px solid {PRO_COLORS['border_default']};
}}

QWidget#tabContentArea {{
    background-color: {PRO_COLORS['bg_secondary']};
}}

QLabel#sectionHeader {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
    padding: 6px 0px 2px 0px;
}}

QLabel#sectionSubheader {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    padding: 0px 0px 8px 0px;
}}

QFrame#infoBanner {{
    background-color: {PRO_COLORS['accent_light']};
    border: 1px solid rgba(79, 140, 255, 0.25);
    border-radius: 8px;
    padding: 10px 14px;
}}

QLabel#infoBannerText {{
    color: {PRO_COLORS['text_accent']};
    font-size: 11px;
}}

QFrame#warningBanner {{
    background-color: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 8px;
    padding: 10px 14px;
}}

QLabel#warningBannerText {{
    color: {PRO_COLORS['warning']};
    font-size: 11px;
}}

QFrame#successBanner {{
    background-color: rgba(52, 211, 153, 0.1);
    border: 1px solid rgba(52, 211, 153, 0.25);
    border-radius: 8px;
    padding: 10px 14px;
}}

QLabel#successBannerText {{
    color: {PRO_COLORS['success']};
    font-size: 11px;
}}

QLabel#emptyStateText {{
    color: {PRO_COLORS['text_muted']};
    font-size: 12px;
    padding: 20px;
}}

QFrame#toolbar {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    padding: 8px 12px;
}}

QPushButton#toolbarBtn {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 500;
}}

QPushButton#toolbarBtn:hover {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QPushButton#toolbarBtnActive {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#tagLabel {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_secondary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#tagLabelAccent {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
    border: 1px solid rgba(79, 140, 255, 0.3);
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#tagLabelSuccess {{
    background-color: rgba(52, 211, 153, 0.15);
    color: {PRO_COLORS['success']};
    border: 1px solid rgba(52, 211, 153, 0.3);
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#tagLabelWarning {{
    background-color: rgba(251, 191, 36, 0.15);
    color: {PRO_COLORS['warning']};
    border: 1px solid rgba(251, 191, 36, 0.3);
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#tagLabelDanger {{
    background-color: rgba(248, 113, 113, 0.15);
    color: {PRO_COLORS['danger']};
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 500;
}}

QFrame#linkSummaryCard {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 10px;
    padding: 14px 16px;
}}

QLabel#linkSummaryTitle {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
    padding-bottom: 8px;
}}

QLabel#linkStatLabel {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    font-weight: 500;
}}

QLabel#linkStatValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 22px;
    font-weight: 800;
}}

QLabel#linkStatValueGreen {{
    color: {PRO_COLORS['success']};
    font-size: 22px;
    font-weight: 800;
}}

QLabel#linkStatValueRed {{
    color: {PRO_COLORS['danger']};
    font-size: 22px;
    font-weight: 800;
}}

QLabel#linkStatValueGray {{
    color: {PRO_COLORS['text_muted']};
    font-size: 22px;
    font-weight: 800;
}}

QFrame#linkIndicatorGreen {{
    background-color: {PRO_COLORS['success']};
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
    border-radius: 5px;
}}

QFrame#linkIndicatorRed {{
    background-color: {PRO_COLORS['danger']};
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
    border-radius: 5px;
}}

QFrame#linkIndicatorGray {{
    background-color: {PRO_COLORS['text_muted']};
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
    border-radius: 5px;
}}

QFrame#linkIndicatorYellow {{
    background-color: {PRO_COLORS['warning']};
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
    border-radius: 5px;
}}

QPushButton#linkBtn {{
    background-color: {PRO_COLORS['success']};
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton#linkBtn:hover {{
    background-color: #2dd4a0;
}}

QPushButton#unlinkBtn {{
    background-color: transparent;
    color: {PRO_COLORS['danger']};
    border: 1px solid {PRO_COLORS['danger']};
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton#unlinkBtn:hover {{
    background-color: rgba(248, 113, 113, 0.15);
}}

QPushButton#testLinkBtn {{
    background-color: transparent;
    color: {PRO_COLORS['text_accent']};
    border: 1px solid {PRO_COLORS['accent']};
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton#testLinkBtn:hover {{
    background-color: {PRO_COLORS['accent_light']};
}}

QFrame#connectionConfigCard {{
    background-color: {PRO_COLORS['bg_input']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 8px;
    padding: 12px 14px;
}}

QLabel#connectionConfigTitle {{
    color: {PRO_COLORS['text_primary']};
    font-size: 12px;
    font-weight: 700;
    padding-bottom: 6px;
}}

QLabel#linkHealthLabel {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    font-weight: 500;
}}

QLabel#linkHealthGood {{
    color: {PRO_COLORS['success']};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#linkHealthWarning {{
    color: {PRO_COLORS['warning']};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#linkHealthBad {{
    color: {PRO_COLORS['danger']};
    font-size: 11px;
    font-weight: 700;
}}

QFrame#linkDivider {{
    background-color: {PRO_COLORS['border_default']};
    min-height: 1px;
    max-height: 1px;
}}
"""

HEADER_STYLE = f"""
QWidget#proHeader {{
    background: {PRO_COLORS['gradient_header']};
    border-bottom: 1px solid {PRO_COLORS['border_default']};
    min-height: 52px;
    max-height: 52px;
}}

QLabel#headerTitle {{
    color: #333333;
    font-size: 16px;
    font-weight: 700;
    padding: 0px 16px;
}}

QLabel#headerSubtitle {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    padding: 0px 16px;
}}

QLabel#statusDot {{
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
}}

QLabel#statusText {{
    color: {PRO_COLORS['text_secondary']};
    font-size: 11px;
    font-weight: 500;
}}

QLabel#metricLabel {{
    color: {PRO_COLORS['text_muted']};
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#metricValue {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
}}

QWidget#headerSeparator {{
    background-color: {PRO_COLORS['border_default']};
    min-width: 1px;
    max-width: 1px;
    min-height: 28px;
    max-height: 28px;
}}
"""

SIDEBAR_STYLE = f"""
QWidget#proSidebar {{
    background-color: {PRO_COLORS['bg_sidebar']};
    border-right: 1px solid {PRO_COLORS['border_default']};
}}

QPushButton#sidebarBtn {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 500;
    text-align: left;
}}

QPushButton#sidebarBtn:hover {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
}}

QPushButton#sidebarBtn:checked {{
    background-color: {PRO_COLORS['accent_light']};
    color: {PRO_COLORS['text_accent']};
    border-left: 3px solid {PRO_COLORS['accent']};
}}

QPushButton#actionBtn {{
    background-color: {PRO_COLORS['accent']};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#actionBtn:hover {{
    background-color: {PRO_COLORS['accent_hover']};
}}

QPushButton#dangerBtn {{
    background-color: transparent;
    color: {PRO_COLORS['danger']};
    border: 1px solid {PRO_COLORS['danger']};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#dangerBtn:hover {{
    background-color: rgba(248, 113, 113, 0.1);
}}

QPushButton#outlineBtn {{
    background-color: transparent;
    color: {PRO_COLORS['text_secondary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#outlineBtn:hover {{
    background-color: {PRO_COLORS['bg_card_hover']};
    border-color: {PRO_COLORS['border_light']};
    color: {PRO_COLORS['text_primary']};
}}

QComboBox#sidebarCombo {{
    background-color: {PRO_COLORS['bg_input']};
    color: {PRO_COLORS['text_primary']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}}

QComboBox#sidebarCombo:hover {{
    border-color: {PRO_COLORS['border_light']};
}}

QLabel#sectionTitle {{
    color: {PRO_COLORS['text_muted']};
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 8px 14px 4px 14px;
}}
"""

CARD_STYLE = f"""
QFrame#proCard {{
    background-color: {PRO_COLORS['bg_card']};
    border: 1px solid {PRO_COLORS['border_default']};
    border-radius: 10px;
    padding: 16px;
}}

QFrame#proCard:hover {{
    border-color: {PRO_COLORS['border_light']};
}}

QLabel#cardTitle {{
    color: {PRO_COLORS['text_primary']};
    font-size: 13px;
    font-weight: 700;
}}

QLabel#cardValue {{
    color: {PRO_COLORS['text_accent']};
    font-size: 24px;
    font-weight: 800;
}}

QLabel#cardDesc {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
}}
"""

BOTTOM_BAR_STYLE = f"""
QStatusBar#proBottomBar {{
    background-color: {PRO_COLORS['bg_header']};
    border-top: 1px solid {PRO_COLORS['border_default']};
    padding: 2px 12px;
    min-height: 28px;
    max-height: 28px;
}}

QLabel#bottomLabel {{
    color: {PRO_COLORS['text_muted']};
    font-size: 10px;
    padding: 0px 8px;
}}

QLabel#bottomValue {{
    color: {PRO_COLORS['text_secondary']};
    font-size: 10px;
    font-weight: 600;
    padding: 0px 4px;
}}

QWidget#bottomSeparator {{
    background-color: {PRO_COLORS['border_default']};
    min-width: 1px;
    max-width: 1px;
    min-height: 14px;
    max-height: 14px;
}}
"""