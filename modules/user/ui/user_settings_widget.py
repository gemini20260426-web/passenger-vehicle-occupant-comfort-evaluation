"""用户设置组件（管理系统参数和用户偏好）"""
import logging
import json
import os
from typing import Dict, Any, List
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
                             QCheckBox, QPushButton, QComboBox, QMessageBox,
                             QFileDialog, QColorDialog)
from PySide6.QtCore import Qt, Slot, QMutex, QMutexLocker
from PySide6.QtGui import QColor

class UserSettingsWidget(QWidget):
    """用户设置组件（保持原有类名）"""
    def __init__(self, settings_path: str = "config/settings.json"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.settings_path = settings_path
        
        # 线程安全锁（新增）
        self.settings_lock = QMutex()
        
        # 设置数据（保持原有）
        self.settings = self._load_default_settings()
        self._load_settings()  # 加载保存的设置
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 加载当前设置到表单（保持原有方法）
        self._load_settings_to_form()

    def _load_default_settings(self) -> Dict[str, Any]:
        """加载默认设置（保持原有方法）"""
        return {
            # 系统设置
            'system': {
                'auto_start': False,
                'minimize_to_tray': True,
                'language': 'zh_CN',
                'theme': 'light'
            },
            # 数据采集设置
            'data_collection': {
                'sample_rate': 10,  # 采样率(Hz)
                'buffer_size': 1000,  # 缓冲区大小
                'auto_save': True,
                'save_interval': 60  # 自动保存间隔(秒)
            },
            # 行为分析设置
            'behavior_analysis': {
                'hard_acceleration_threshold': 0.8,  # g
                'hard_braking_threshold': -0.8,  # g
                'sharp_turning_threshold': 5.0,  # °/s
                'overspeed_threshold': 120,  # km/h
                'analysis_interval': 1.0  # 分析间隔(秒)
            },
            # 通知设置
            'notifications': {
                'show_hard_acceleration': True,
                'show_hard_braking': True,
                'show_sharp_turning': True,
                'show_overspeeding': True,
                'play_sound': True,
                'notification_duration': 5  # 通知显示时间(秒)
            },
            # 界面设置
            'interface': {
                'show_toolbar': True,
                'show_statusbar': True,
                'auto_refresh': True,
                'refresh_interval': 5  # 刷新间隔(秒)
            }
        }

    def _load_settings(self) -> None:
        """加载保存的设置（保持原有方法）"""
        if not os.path.exists(self.settings_path):
            self.logger.info(f"设置文件不存在，使用默认设置: {self.settings_path}")
            return
            
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
            
            # 合并保存的设置到默认设置（不覆盖新增的设置项）
            with QMutexLocker(self.settings_lock):
                self._merge_settings(self.settings, saved_settings)
            
            self.logger.info("设置已加载")
            
        except Exception as e:
            self.logger.error(f"加载设置失败: {str(e)}，使用默认设置")

    def _merge_settings(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """合并设置（递归）（保持原有方法）"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_settings(target[key], value)
            else:
                target[key] = value

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("系统设置")
        self.resize(600, 600)
        
        # 创建设置分组（保持原有）
        self._create_system_group(main_layout)
        self._create_data_collection_group(main_layout)
        self._create_behavior_analysis_group(main_layout)
        self._create_notifications_group(main_layout)
        self._create_interface_group(main_layout)
        
        # 按钮区域（保持原有）
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(self.reset_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(btn_layout)

    def _create_system_group(self, parent_layout) -> None:
        """创建系统设置分组（保持原有方法）"""
        group = QGroupBox("系统设置")
        layout = QFormLayout()
        
        # 开机自启
        self.auto_start_check = QCheckBox()
        layout.addRow("开机自动启动:", self.auto_start_check)
        
        # 最小化到托盘
        self.minimize_to_tray_check = QCheckBox()
        layout.addRow("关闭时最小化到托盘:", self.minimize_to_tray_check)
        
        # 语言选择
        self.language_combo = QComboBox()
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        layout.addRow("语言:", self.language_combo)
        
        # 主题选择
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色主题", "light")
        self.theme_combo.addItem("深色主题", "dark")
        layout.addRow("主题:", self.theme_combo)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_data_collection_group(self, parent_layout) -> None:
        """创建数据采集设置分组（保持原有方法）"""
        group = QGroupBox("数据采集设置")
        layout = QFormLayout()
        
        # 采样率
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(1, 100)
        self.sample_rate_spin.setSuffix(" Hz")
        layout.addRow("采样率:", self.sample_rate_spin)
        
        # 缓冲区大小
        self.buffer_size_spin = QSpinBox()
        self.buffer_size_spin.setRange(100, 10000)
        layout.addRow("缓冲区大小:", self.buffer_size_spin)
        
        # 自动保存
        self.auto_save_check = QCheckBox()
        layout.addRow("自动保存数据:", self.auto_save_check)
        
        # 自动保存间隔
        self.save_interval_spin = QSpinBox()
        self.save_interval_spin.setRange(10, 300)
        self.save_interval_spin.setSuffix(" 秒")
        layout.addRow("自动保存间隔:", self.save_interval_spin)
        
        # 数据保存路径
        path_layout = QHBoxLayout()
        self.data_path_edit = QLineEdit()
        self.browse_data_btn = QPushButton("浏览...")
        self.browse_data_btn.clicked.connect(self._browse_data_path)
        path_layout.addWidget(self.data_path_edit)
        path_layout.addWidget(self.browse_data_btn)
        layout.addRow("数据保存路径:", path_layout)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_behavior_analysis_group(self, parent_layout) -> None:
        """创建行为分析设置分组（保持原有方法）"""
        group = QGroupBox("行为分析设置")
        layout = QFormLayout()
        
        # 急加速阈值
        self.accel_threshold_spin = QDoubleSpinBox()
        self.accel_threshold_spin.setRange(0.1, 2.0)
        self.accel_threshold_spin.setDecimals(2)
        self.accel_threshold_spin.setSuffix(" g")
        layout.addRow("急加速阈值:", self.accel_threshold_spin)
        
        # 急刹车阈值
        self.brake_threshold_spin = QDoubleSpinBox()
        self.brake_threshold_spin.setRange(-2.0, -0.1)
        self.brake_threshold_spin.setDecimals(2)
        self.brake_threshold_spin.setSuffix(" g")
        layout.addRow("急刹车阈值:", self.brake_threshold_spin)
        
        # 急转弯阈值
        self.turn_threshold_spin = QDoubleSpinBox()
        self.turn_threshold_spin.setRange(1.0, 20.0)
        self.turn_threshold_spin.setDecimals(1)
        self.turn_threshold_spin.setSuffix(" °/s")
        layout.addRow("急转弯阈值:", self.turn_threshold_spin)
        
        # 超速阈值
        self.overspeed_threshold_spin = QSpinBox()
        self.overspeed_threshold_spin.setRange(50, 200)
        self.overspeed_threshold_spin.setSuffix(" km/h")
        layout.addRow("超速阈值:", self.overspeed_threshold_spin)
        
        # 分析间隔
        self.analysis_interval_spin = QDoubleSpinBox()
        self.analysis_interval_spin.setRange(0.1, 10.0)
        self.analysis_interval_spin.setDecimals(1)
        self.analysis_interval_spin.setSuffix(" 秒")
        layout.addRow("分析间隔:", self.analysis_interval_spin)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_notifications_group(self, parent_layout) -> None:
        """创建通知设置分组（保持原有方法）"""
        group = QGroupBox("通知设置")
        layout = QFormLayout()
        
        # 急加速通知
        self.notify_accel_check = QCheckBox()
        layout.addRow("急加速通知:", self.notify_accel_check)
        
        # 急刹车通知
        self.notify_brake_check = QCheckBox()
        layout.addRow("急刹车通知:", self.notify_brake_check)
        
        # 急转弯通知
        self.notify_turn_check = QCheckBox()
        layout.addRow("急转弯通知:", self.notify_turn_check)
        
        # 超速通知
        self.notify_overspeed_check = QCheckBox()
        layout.addRow("超速通知:", self.notify_overspeed_check)
        
        # 播放提示音
        self.play_sound_check = QCheckBox()
        layout.addRow("播放提示音:", self.play_sound_check)
        
        # 通知显示时间
        self.notification_duration_spin = QSpinBox()
        self.notification_duration_spin.setRange(1, 30)
        self.notification_duration_spin.setSuffix(" 秒")
        layout.addRow("通知显示时间:", self.notification_duration_spin)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_interface_group(self, parent_layout) -> None:
        """创建界面设置分组（保持原有方法）"""
        group = QGroupBox("界面设置")
        layout = QFormLayout()
        
        # 显示工具栏
        self.show_toolbar_check = QCheckBox()
        layout.addRow("显示工具栏:", self.show_toolbar_check)
        
        # 显示状态栏
        self.show_statusbar_check = QCheckBox()
        layout.addRow("显示状态栏:", self.show_statusbar_check)
        
        # 自动刷新
        self.auto_refresh_check = QCheckBox()
        layout.addRow("自动刷新数据:", self.auto_refresh_check)
        
        # 刷新间隔
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 60)
        self.refresh_interval_spin.setSuffix(" 秒")
        layout.addRow("自动刷新间隔:", self.refresh_interval_spin)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _load_settings_to_form(self) -> None:
        """加载设置到表单（保持原有方法）"""
        with QMutexLocker(self.settings_lock):
            # 系统设置
            self.auto_start_check.setChecked(self.settings['system']['auto_start'])
            self.minimize_to_tray_check.setChecked(self.settings['system']['minimize_to_tray'])
            
            lang_idx = self.language_combo.findData(self.settings['system']['language'])
            if lang_idx >= 0:
                self.language_combo.setCurrentIndex(lang_idx)
                
            theme_idx = self.theme_combo.findData(self.settings['system']['theme'])
            if theme_idx >= 0:
                self.theme_combo.setCurrentIndex(theme_idx)
            
            # 数据采集设置
            self.sample_rate_spin.setValue(self.settings['data_collection']['sample_rate'])
            self.buffer_size_spin.setValue(self.settings['data_collection']['buffer_size'])
            self.auto_save_check.setChecked(self.settings['data_collection']['auto_save'])
            self.save_interval_spin.setValue(self.settings['data_collection']['save_interval'])
            
            # 行为分析设置
            self.accel_threshold_spin.setValue(self.settings['behavior_analysis']['hard_acceleration_threshold'])
            self.brake_threshold_spin.setValue(self.settings['behavior_analysis']['hard_braking_threshold'])
            self.turn_threshold_spin.setValue(self.settings['behavior_analysis']['sharp_turning_threshold'])
            self.overspeed_threshold_spin.setValue(self.settings['behavior_analysis']['overspeed_threshold'])
            self.analysis_interval_spin.setValue(self.settings['behavior_analysis']['analysis_interval'])
            
            # 通知设置
            self.notify_accel_check.setChecked(self.settings['notifications']['show_hard_acceleration'])
            self.notify_brake_check.setChecked(self.settings['notifications']['show_hard_braking'])
            self.notify_turn_check.setChecked(self.settings['notifications']['show_sharp_turning'])
            self.notify_overspeed_check.setChecked(self.settings['notifications']['show_overspeeding'])
            self.play_sound_check.setChecked(self.settings['notifications']['play_sound'])
            self.notification_duration_spin.setValue(self.settings['notifications']['notification_duration'])
            
            # 界面设置
            self.show_toolbar_check.setChecked(self.settings['interface']['show_toolbar'])
            self.show_statusbar_check.setChecked(self.settings['interface']['show_statusbar'])
            self.auto_refresh_check.setChecked(self.settings['interface']['auto_refresh'])
            self.refresh_interval_spin.setValue(self.settings['interface']['refresh_interval'])

    @Slot()
    def _browse_data_path(self) -> None:
        """浏览数据保存路径（保持原有方法）"""
        current_path = self.data_path_edit.text() or os.getcwd()
        
        directory = QFileDialog.getExistingDirectory(
            self, "选择数据保存路径", current_path
        )
        
        if directory:
            self.data_path_edit.setText(directory)

    @Slot()
    def _save_settings(self) -> None:
        """保存设置（保持原有方法）"""
        # 从表单收集设置（线程安全）
        with QMutexLocker(self.settings_lock):
            # 系统设置
            self.settings['system']['auto_start'] = self.auto_start_check.isChecked()
            self.settings['system']['minimize_to_tray'] = self.minimize_to_tray_check.isChecked()
            self.settings['system']['language'] = self.language_combo.currentData()
            self.settings['system']['theme'] = self.theme_combo.currentData()
            
            # 数据采集设置
            self.settings['data_collection']['sample_rate'] = self.sample_rate_spin.value()
            self.settings['data_collection']['buffer_size'] = self.buffer_size_spin.value()
            self.settings['data_collection']['auto_save'] = self.auto_save_check.isChecked()
            self.settings['data_collection']['save_interval'] = self.save_interval_spin.value()
            
            # 行为分析设置
            self.settings['behavior_analysis']['hard_acceleration_threshold'] = self.accel_threshold_spin.value()
            self.settings['behavior_analysis']['hard_braking_threshold'] = self.brake_threshold_spin.value()
            self.settings['behavior_analysis']['sharp_turning_threshold'] = self.turn_threshold_spin.value()
            self.settings['behavior_analysis']['overspeed_threshold'] = self.overspeed_threshold_spin.value()
            self.settings['behavior_analysis']['analysis_interval'] = self.analysis_interval_spin.value()
            
            # 通知设置
            self.settings['notifications']['show_hard_acceleration'] = self.notify_accel_check.isChecked()
            self.settings['notifications']['show_hard_braking'] = self.notify_brake_check.isChecked()
            self.settings['notifications']['show_sharp_turning'] = self.notify_turn_check.isChecked()
            self.settings['notifications']['show_overspeeding'] = self.notify_overspeed_check.isChecked()
            self.settings['notifications']['play_sound'] = self.play_sound_check.isChecked()
            self.settings['notifications']['notification_duration'] = self.notification_duration_spin.value()
            
            # 界面设置
            self.settings['interface']['show_toolbar'] = self.show_toolbar_check.isChecked()
            self.settings['interface']['show_statusbar'] = self.show_statusbar_check.isChecked()
            self.settings['interface']['auto_refresh'] = self.auto_refresh_check.isChecked()
            self.settings['interface']['refresh_interval'] = self.refresh_interval_spin.value()
        
        # 保存到文件
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            
            # 应用设置（新增即时生效逻辑）
            self._apply_settings()
            
            QMessageBox.information(self, "保存成功", "设置已保存并生效")
            self.logger.info("设置已保存")
            
        except Exception as e:
            error_msg = f"保存设置失败: {str(e)}"
            self.logger.error(error_msg)
            QMessageBox.warning(self, "保存失败", error_msg)

    def _apply_settings(self) -> None:
        """应用设置（新增即时生效逻辑）"""
        with QMutexLocker(self.settings_lock):
            # 通知主应用更新设置
            if hasattr(self.parent(), 'apply_settings'):
                self.parent().apply_settings(self.settings.copy())
                
            # 应用界面相关设置
            self._apply_interface_settings()

    def _apply_interface_settings(self) -> None:
        """应用界面设置（新增）"""
        # 这里可以根据设置立即更新界面元素
        # 例如显示/隐藏工具栏、状态栏等
        if hasattr(self.parent(), 'update_interface_from_settings'):
            self.parent().update_interface_from_settings(
                self.settings['interface'].copy()
            )

    @Slot()
    def _reset_settings(self) -> None:
        """恢复默认设置（保持原有方法）"""
        reply = QMessageBox.question(
            self, "确认恢复默认", "确定要恢复默认设置吗？当前设置将被覆盖。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            with QMutexLocker(self.settings_lock):
                self.settings = self._load_default_settings()
            
            # 更新表单
            self._load_settings_to_form()
            
            self.logger.info("已恢复默认设置（未保存）")
            QMessageBox.information(self, "恢复默认", "已恢复默认设置，请点击保存使设置生效")

    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置（线程安全）"""
        with QMutexLocker(self.settings_lock):
            return json.loads(json.dumps(self.settings))  # 深拷贝
    