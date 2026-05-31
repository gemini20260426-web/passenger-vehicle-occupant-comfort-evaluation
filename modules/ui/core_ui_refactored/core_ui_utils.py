#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 工具模块
包含翻译字典、主题样式、通用UI更新函数
"""

from PySide6.QtWidgets import QProgressBar, QLabel

translations = {
    'en': {
        'app_title': 'Core System Dashboard',
        'status_ready': 'Ready',
        'status_running': 'Running',
        'status_error': 'Error',
        'recording_no': 'No',
        'recording_yes': 'Yes',
        'mode_standard': 'Standard',
        'data_source_config': 'Data Source Configuration',
        'source_type': 'Source Type:',
        'connect': 'Connect',
        'disconnect': 'Disconnect',
        'file_path': 'File Path:',
        'browse': 'Browse',
        'data_recording': 'Data Recording',
        'start_recording': 'Start Recording',
        'stop_recording': 'Stop Recording',
        'export_data': 'Export Recorded Data',
        'analysis_control': 'Analysis Control',
        'analysis_level': 'Analysis Level:',
        'start_analysis': 'Start Analysis',
        'stop_analysis': 'Stop Analysis',
        'sensitivity': 'Sensitivity:',
        'confidence_threshold': 'Confidence Threshold:',
        'system_settings': 'System Settings',
        'theme': 'Theme:',
        'auto_save': 'Auto-save results',
        'log_level': 'Log Level:',
        'source_management': 'Source Management',
        'add_source': 'Add Source',
        'remove_source': 'Remove Source',
        'set_active': 'Set Active',
        'add_data_source': 'Add Data Source',
        'port': 'Port:',
        'baud_rate': 'Baud Rate:',
        'broker': 'Broker:',
        'topic': 'Topic:',
        'host': 'Host:',
        'real_time_monitoring': 'Real-time Monitoring',
        'system_monitoring': 'System Monitoring',
        'comprehensive_monitoring': 'Comprehensive Monitoring',
        'fused_analysis': 'Fused Analysis',
        'data_source': 'Data Source',
        'behavior_analysis': 'Behavior Analysis',
        'analysis_visualization': 'Analysis Visualization',
        'imu_visualization': 'IMU Visualization',
        'cnap_visualization': 'CNAP Visualization',
        'configuration': 'Configuration',
        'system_status_summary': 'System Status Summary',
        'state': 'State:',
        'data_rate': 'Data Rate:',
        'analysis': 'Analysis:',
        'connection': 'Connection:',
        'key_metrics': 'Key Metrics',
        'processing_progress': 'Processing Progress:',
        'data_source_information': 'Data Source Information',
        'connection_status': 'Connection Status:',
        'data_format': 'Data Format:',
        'last_update': 'Last Update:',
        'data_preview': 'Data Preview',
        'analysis_results': 'Analysis Results',
        'system_parameters': 'System Parameters',
        'sample_rate': 'Sample Rate (Hz):',
        'buffer_size': 'Buffer Size:',
        'timeout': 'Timeout (ms):',
        'analysis_parameters': 'Analysis Parameters',
        'window_size': 'Window Size (s):',
        'confidence': 'Confidence Threshold:',
        'smoothing_factor': 'Smoothing Factor:',
        'save_config': 'Save Configuration',
        'load_config': 'Load Configuration',
        'select_data_sources': 'Select Data Sources',
        'data_sources': 'Data Sources',
        'select_all': 'Select All',
        'deselect_all': 'Deselect All',
        'ok': 'OK',
        'cancel': 'Cancel',
        'file': 'File',
        'new': 'New',
        'open': 'Open',
        'save': 'Save',
        'exit': 'Exit',
        'view': 'View',
        'help': 'Help',
        'about': 'About',
        'language': 'Language',
        'english': 'English',
        'chinese': 'Chinese',
        'new_session': 'New Session',
        'new_session_msg': 'Start a new session? Current data will be lost.',
        'yes': 'Yes',
        'no': 'No',
        'open_data_file': 'Open Data File',
        'save_current_data': 'Save Current Data',
        'no_data_to_save': 'No data to save.',
        'save_successful': 'Save Successful',
        'data_saved_to': 'Current data saved to:',
        'save_failed': 'Save Failed',
        'export_failed': 'Export Failed',
        'no_data_to_export': 'No recorded data to export.',
        'export_successful': 'Export Successful',
        'data_exported_to': 'Data saved to:',
        'about_core': 'About Core System Dashboard',
        'about_text': 'Core System Dashboard v2.0.0\n\nA comprehensive UI for monitoring and analyzing IMU and CNAP data.\n\n 2023 Core System Technologies',
        'help_text': 'Core System Dashboard Help\n\n1. Connect to a data source using the left panel\n2. Start/stop data visualization using the controls on each tab\n3. Use the Analysis tab to view and export analysis results\n4. Configure system settings in the Configuration Management menu\n\nFor more detailed documentation, visit our website.',
        'light': 'Light',
        'dark': 'Dark'
    },
    'zh': {
        'app_title': '核心系统仪表盘',
        'status_ready': '就绪',
        'status_running': '运行中',
        'status_error': '错误',
        'recording_no': '否',
        'recording_yes': '是',
        'mode_standard': '标准模式',
        'data_source_config': '数据源配置',
        'source_type': '源类型',
        'connect': '连接',
        'disconnect': '断开',
        'file_path': '文件路径:',
        'browse': '浏览',
        'data_recording': '数据记录',
        'start_recording': '开始记录',
        'stop_recording': '停止记录',
        'export_data': '导出记录数据',
        'analysis_control': '分析控制',
        'analysis_level': '分析级别:',
        'start_analysis': '开始分析',
        'stop_analysis': '停止分析',
        'sensitivity': '灵敏度',
        'confidence_threshold': '置信度阈值',
        'system_settings': '系统设置',
        'theme': '主题:',
        'auto_save': '自动保存结果',
        'log_level': '日志级别:',
        'source_management': '源管理',
        'add_source': '添加源',
        'remove_source': '移除源',
        'set_active': '设为活动',
        'add_data_source': '添加数据源',
        'port': '端口:',
        'baud_rate': '波特率',
        'broker': '代理服务器',
        'topic': '主题:',
        'host': '主机:',
        'real_time_monitoring': '实时监控',
        'system_monitoring': '系统监控',
        'comprehensive_monitoring': '综合监控',
        'fused_analysis': '融合分析',
        'data_source': '数据源',
        'behavior_analysis': '行为分析',
        'analysis_visualization': '分析可视化',
        'imu_visualization': 'IMU可视化',
        'cnap_visualization': 'CNAP可视化',
        'configuration': '配置',
        'system_status_summary': '系统状态摘要',
        'state': '状态',
        'data_rate': '数据速率:',
        'analysis': '分析:',
        'connection': '连接:',
        'key_metrics': '关键指标',
        'processing_progress': '处理进度:',
        'data_source_information': '数据源信息',
        'connection_status': '连接状态',
        'data_format': '数据格式:',
        'last_update': '最后更新',
        'data_preview': '数据预览',
        'analysis_results': '分析结果',
        'system_parameters': '系统参数',
        'sample_rate': '采样率 (Hz):',
        'buffer_size': '缓冲区大小',
        'timeout': '超时时间 (ms):',
        'analysis_parameters': '分析参数',
        'window_size': '窗口大小 (s):',
        'confidence': '置信度阈值',
        'smoothing_factor': '平滑因子:',
        'save_config': '保存配置',
        'load_config': '加载配置',
        'select_data_sources': '选择数据源',
        'data_sources': '数据源',
        'select_all': '全选',
        'deselect_all': '取消全选',
        'ok': '确定',
        'cancel': '取消',
        'file': '文件',
        'new': '新建',
        'open': '打开',
        'save': '保存',
        'exit': '退出',
        'view': '视图',
        'help': '帮助',
        'about': '关于',
        'language': '语言',
        'english': '英文',
        'chinese': '中文',
        'new_session': '新建会话',
        'new_session_msg': '开始新会话?当前数据将丢失',
        'yes': '是',
        'no': '否',
        'open_data_file': '打开数据文件',
        'save_current_data': '保存当前数据',
        'no_data_to_save': '没有数据可保存。',
        'save_successful': '保存成功',
        'data_saved_to': '当前数据已保存到:',
        'save_failed': '保存失败',
        'export_failed': '导出失败',
        'no_data_to_export': '没有记录的数据可导出。',
        'export_successful': '导出成功',
        'data_exported_to': '数据已保存到:',
        'about_core': '关于核心系统仪表盘',
        'about_text': '核心系统仪表盘 v2.0.0\n\n用于监控和分析IMU和CNAP数据的综合UI。\n\n 2023 核心系统技术',
        'help_text': '核心系统仪表盘帮助\n\n1. 使用左侧面板连接到数据源\n2. 使用每个标签页上的控件开始/停止数据可视化\n3. 使用分析标签页查看和导出分析结果\n4. 在配置管理菜单中配置系统设置\n\n更多详细文档，请访问我们的网站。',
        'light': '浅色',
        'dark': '深色'
    }
}


def get_light_theme_style():
    """获取浅色主题样式"""
    return """
        QMainWindow {
            background-color: #f5f6fa;
        }
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #dcdde1;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            color: #2c3e50;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #2c3e50;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #2471a3;
        }
        QPushButton:disabled {
            background-color: #bdc3c7;
            color: #95a5a6;
        }
        QLabel {
            color: #2c3e50;
        }
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            padding: 4px 8px;
            color: #2c3e50;
        }
        QComboBox:hover {
            border-color: #3498db;
        }
        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            padding: 4px 8px;
            color: #2c3e50;
        }
        QLineEdit:focus {
            border-color: #3498db;
        }
        QTabWidget::pane {
            border: 1px solid #dcdde1;
            background-color: #ffffff;
        }
        QTabBar::tab {
            background-color: #ecf0f1;
            border: 1px solid #dcdde1;
            padding: 8px 16px;
            margin-right: 2px;
            color: #2c3e50;
        }
        QTabBar::tab:selected {
            background-color: #3498db;
            color: white;
        }
        QProgressBar {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            text-align: center;
            background-color: #ecf0f1;
        }
        QProgressBar::chunk {
            background-color: #3498db;
            border-radius: 3px;
        }
        QStatusBar {
            background-color: #ecf0f1;
            color: #2c3e50;
            border-top: 1px solid #dcdde1;
        }
        QMenuBar {
            background-color: #ffffff;
            border-bottom: 1px solid #dcdde1;
            color: #2c3e50;
        }
        QMenuBar::item:selected {
            background-color: #3498db;
            color: white;
        }
        QMenu {
            background-color: #ffffff;
            border: 1px solid #dcdde1;
            color: #2c3e50;
        }
        QMenu::item:selected {
            background-color: #3498db;
            color: white;
        }
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #dcdde1;
            gridline-color: #ecf0f1;
            color: #2c3e50;
        }
        QHeaderView::section {
            background-color: #ecf0f1;
            border: 1px solid #dcdde1;
            padding: 4px;
            color: #2c3e50;
            font-weight: bold;
        }
    """


def get_dark_theme_style():
    """获取深色主题样式"""
    return """
        QMainWindow {
            background-color: #1a1a2e;
        }
        QGroupBox {
            background-color: #16213e;
            border: 1px solid #0f3460;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            color: #e0e0e0;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #0f3460;
            color: #e0e0e0;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1a5276;
        }
        QPushButton:pressed {
            background-color: #0d2b4e;
        }
        QPushButton:disabled {
            background-color: #2c3e50;
            color: #7f8c8d;
        }
        QLabel {
            color: #e0e0e0;
        }
        QComboBox {
            background-color: #16213e;
            border: 1px solid #0f3460;
            border-radius: 4px;
            padding: 4px 8px;
            color: #e0e0e0;
        }
        QComboBox:hover {
            border-color: #3498db;
        }
        QLineEdit {
            background-color: #16213e;
            border: 1px solid #0f3460;
            border-radius: 4px;
            padding: 4px 8px;
            color: #e0e0e0;
        }
        QLineEdit:focus {
            border-color: #3498db;
        }
        QTabWidget::pane {
            border: 1px solid #0f3460;
            background-color: #16213e;
        }
        QTabBar::tab {
            background-color: #1a1a2e;
            border: 1px solid #0f3460;
            padding: 8px 16px;
            margin-right: 2px;
            color: #e0e0e0;
        }
        QTabBar::tab:selected {
            background-color: #0f3460;
            color: #3498db;
        }
        QProgressBar {
            border: 1px solid #0f3460;
            border-radius: 4px;
            text-align: center;
            background-color: #1a1a2e;
            color: #e0e0e0;
        }
        QProgressBar::chunk {
            background-color: #0f3460;
            border-radius: 3px;
        }
        QStatusBar {
            background-color: #16213e;
            color: #e0e0e0;
            border-top: 1px solid #0f3460;
        }
        QMenuBar {
            background-color: #16213e;
            border-bottom: 1px solid #0f3460;
            color: #e0e0e0;
        }
        QMenuBar::item:selected {
            background-color: #0f3460;
            color: #3498db;
        }
        QMenu {
            background-color: #16213e;
            border: 1px solid #0f3460;
            color: #e0e0e0;
        }
        QMenu::item:selected {
            background-color: #0f3460;
            color: #3498db;
        }
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QTableWidget {
            background-color: #16213e;
            border: 1px solid #0f3460;
            gridline-color: #1a1a2e;
            color: #e0e0e0;
        }
        QHeaderView::section {
            background-color: #1a1a2e;
            border: 1px solid #0f3460;
            padding: 4px;
            color: #e0e0e0;
            font-weight: bold;
        }
    """


def _safe_update_progress_bar(progress_bar: QProgressBar, value: int):
    """安全更新进度条"""
    try:
        if progress_bar and not progress_bar.signalsBlocked():
            progress_bar.setValue(value)
    except Exception:
        pass


def _safe_update_label(label: QLabel, text: str):
    """安全更新标签"""
    try:
        if label and not label.signalsBlocked():
            label.setText(text)
    except Exception:
        pass
