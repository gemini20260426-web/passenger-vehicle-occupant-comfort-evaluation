#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
提供完整的系统配置管理功能，包括本地配置文件管理和远程配置更新接口
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

# PySide6 imports
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QTextEdit, QTabWidget,
    QScrollArea, QMessageBox, QFileDialog, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QFont, QIcon, QAction

# 配置解析器
import configparser
# 延迟导入requests，避免在模块加载时出错
requests = None


class ConfigManager(QObject):
    """配置管理器核心类"""
    
    # 信号定义
    config_changed = Signal(str, str, str)  # section, key, value
    config_loaded = Signal()
    config_saved = Signal()
    remote_update_started = Signal()
    remote_update_finished = Signal(bool, str)  # success, message
    
    def __init__(self, config_file: str = None):
        super().__init__()
        self.config_file = config_file or "config/config.ini"
        self.config = configparser.ConfigParser()
        self.remote_config_url = None
        self.auto_save = True
        self.logger = logging.getLogger(__name__)
        
        # 加载配置文件
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file, encoding='utf-8')
                self.logger.info(f"配置文件加载成功: {self.config_file}")
                # 检查并补充缺失的配置节
                self._ensure_all_config_sections()
                self.config_loaded.emit()
                return True
            else:
                self.logger.warning(f"配置文件不存在: {self.config_file}")
                self.create_default_config()
                return False
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return False
    
    def _ensure_all_config_sections(self):
        """确保所有必需的配置节都存在"""
        # 创建临时配置对象，获取所有默认配置
        temp_config = configparser.ConfigParser()
        
        # 添加所有默认配置
        temp_config['MySQLConfig'] = {
            'host': 'localhost',
            'port': '3306',
            'user': 'root',
            'password': '',
            'database': 'driving_data',
            'charset': 'utf8mb4'
        }
        
        temp_config['RedisConfig'] = {
            'host': 'localhost',
            'port': '6379',
            'db': '0',
            'password': ''
        }
        
        temp_config['InfluxDBConfig'] = {
            'url': 'http://localhost:8086',
            'token': '',
            'org': 'my-org',
            'bucket': 'imu-data',
            'host': 'localhost',
            'port': '8086',
            'timeout': '30',
            'verify_ssl': 'False'
        }
        
        temp_config['paths'] = {
            'data_dir': 'data'
        }
        
        temp_config['DrivingThresholds'] = {
            'max_acceleration': '3.5',
            'max_deceleration': '-10.07',
            'max_steering_angle': '45.0',
            'turning_window': '0.6'
        }
        
        # ====================== 基础分析配置 ======================
        temp_config['BasicAnalysisThresholds'] = {
            'small_steering_angle_threshold': '4.0',
            'acceleration_positive_threshold': '0.15',
            'acceleration_negative_threshold': '-0.15',
            'steering_angle_turn_threshold': '10.0',
            'z_angular_velocity_turn_threshold': '0.08',
            'skid_acceleration_change_rate_threshold': '0.8',
            'skid_z_angular_velocity_threshold': '0.15',
            'emergency_brake_acceleration_threshold': '-8.0',
            'emergency_brake_speed_drop_threshold': '0.15',
            'curve_steering_angle_threshold': '15.0',
            'curve_acceleration_positive_threshold': '0.1',
            'curve_acceleration_negative_threshold': '-0.1',
            'curve_z_angular_velocity_speed_ratio_low': '0.001',
            'curve_z_angular_velocity_speed_ratio_high': '0.01',
            'snake_steering_angle_change_threshold': '15.0',
            'rapid_direction_change_steering_angle_threshold': '15.0',
            'steering_angle_lane_change_threshold': '10.0',
            'x_acceleration_lane_change_threshold': '0.1',
            'large_radius_turn_steering_angle_low': '10.0',
            'large_radius_turn_steering_angle_high': '20.0',
            'large_radius_turn_z_angular_velocity_low': '0.05',
            'large_radius_turn_z_angular_velocity_high': '0.15',
            'u_turn_steering_angle_threshold': '45.0',
            'u_turn_z_angular_velocity_threshold': '0.2',
            'acc_speed_range': '5.0',
            'acc_acceleration_range': '0.1',
            'a_acc_acceleration_threshold': '0.3',
            'a_acc_speed_range': '10.0',
            'brake_acceleration_low': '-0.3',
            'brake_acceleration_high': '-0.1',
            'a_brake_acceleration_threshold': '-0.5',
            'a_brake_speed_drop_threshold': '5.0',
            'constant_speed_std_threshold': '2.0',
            'constant_speed_accel_threshold': '0.075',
            'parking_speed_threshold': '3.0',
            'parking_accel_threshold': '0.05'
        }
        
        temp_config['BasicAnalysisWindowSizes'] = {
            'parking_window': '15',
            'constant_speed_straight_window': '10',
            'accelerating_window': '5',
            'decelerating_window': '5',
            'turning_window': '15',
            'emergency_brake_window': '5',
            'u_turn_window': '20',
            'snake_driving_window': '30',
            'rapid_direction_change_window': '5',
            'large_radius_turning_window': '20',
            'normal_acc_window': '10',
            'aggressive_acc_window': '5',
            'normal_brake_window': '10',
            'aggressive_brake_window': '5',
            'lane_changing_window': '15'
        }
        
        # ====================== 高级分析配置 ======================
        temp_config['AdvancedAnalysisConfig'] = {
            'model_path': 'models/driving_model.pkl',
            'scaler_path': 'models/driving_scaler.pkl',
            'algorithm': 'RandomForest',
            'use_cross_validation': 'True',
            'compare_algorithms': 'False',
            'n_estimators': '100',
            'max_depth': '10',
            'random_state': '42',
            'test_size': '0.2',
            'cv_folds': '5'
        }
        
        temp_config['AdvancedAnalysisFeatures'] = {
            'use_speed': 'True',
            'use_accel_magnitude': 'True',
            'use_turn_rate': 'True',
            'use_speed_change_rate': 'True',
            'use_behavior_confidence': 'True'
        }
        
        # ====================== 分析对比配置 ======================
        temp_config['ComparisonConfig'] = {
            'confidence_threshold': '0.8',
            'time_window_size': '100',
            'auto_sync': 'True',
            'show_data_stream': 'True'
        }
        
        temp_config['Logging'] = {
            'level': 'DEBUG',
            'format': '{asctime} - {levelname} - {message}',
            'file': 'logs/app.log',
            'max_bytes': '10485760',
            'backup_count': '5'
        }
        
        temp_config['UISettings'] = {
            'theme': 'dark',
            'font_size': '12',
            'language': 'zh_CN'
        }
        
        temp_config['MQTTConfig'] = {
            'host': 'localhost',
            'port': '1883',
            'username': 'admin',
            'password': 'public',
            'client_id': 'vehicle_monitor',
            'keepalive': '60',
            'topic': 'vehicle/data',
            'qos': '1',
            'reconnect_interval': '5000',
            'data_topic': 'driving/data',
            'control_topic': 'vehicle/control',
            'threshold_topic': 'alarm/threshold'
        }
        
        temp_config['BehaviorConfig'] = {
            'anomaly_sensitivity': '0.8',
            'window_size': '20',
            'smoothing_window': '10',
            'speed_window': '10',
            'accel_window': '15',
            'angle_window': '20',
            'speeding_threshold': '10.0',
            'speeding_window': '10',
            'rapid_acceleration_threshold': '10.0',
            'rapid_acceleration_window': '10',
            'rapid_deceleration_threshold': '10.0',
            'rapid_deceleration_window': '10',
            'sharp_turn_threshold': '10.0',
            'sharp_turn_window': '10',
            'lane_change_threshold': '10.0',
            'lane_change_window': '10',
            'tailgating_threshold': '10.0',
            'tailgating_window': '10',
            'hard_braking_threshold': '10.0',
            'hard_braking_window': '10',
            'sudden_steering_threshold': '10.0',
            'sudden_steering_window': '10',
            'overspeeding_in_curve_threshold': '10.0',
            'overspeeding_in_curve_window': '10',
            'fatigue_driving_threshold': '10.0',
            'fatigue_driving_window': '10',
            'aggressive_driving_threshold': '10.0',
            'aggressive_driving_window': '10',
            'excessive_lane_change_threshold': '10.0',
            'excessive_lane_change_window': '10',
            'speeding_on_straight_threshold': '10.0',
            'speeding_on_straight_window': '10',
            'speeding_in_school_zone_threshold': '10.0',
            'speeding_in_school_zone_window': '10',
            'speeding_in_residential_threshold': '10.0',
            'speeding_in_residential_window': '10',
            'running_red_light_threshold': '10.0',
            'running_red_light_window': '10',
            'running_stop_sign_threshold': '10.0',
            'running_stop_sign_window': '10'
        }
        
        # 检查并添加缺失的配置节
        config_updated = False
        for section in temp_config.sections():
            if section not in self.config:
                self.logger.info(f"添加缺失的配置节: {section}")
                self.config[section] = temp_config[section]
                config_updated = True
            else:
                # 检查该节是否缺少某些键
                for key, value in temp_config[section].items():
                    if key not in self.config[section]:
                        self.logger.info(f"添加缺失的配置项: [{section}][{key}] = {value}")
                        self.config[section][key] = value
                        config_updated = True
        
        # 如果有更新，保存配置
        if config_updated:
            self.save_config()
            self.logger.info("配置文件已更新，添加了缺失的配置节")
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            
            self.logger.info(f"配置文件保存成功: {self.config_file}")
            self.config_saved.emit()
            return True
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            return False
    
    def create_default_config(self):
        """创建默认配置"""
        self.config['MySQLConfig'] = {
            'host': 'localhost',
            'port': '3306',
            'user': 'root',
            'password': '',
            'database': 'driving_data',
            'charset': 'utf8mb4'
        }
        
        self.config['RedisConfig'] = {
            'host': 'localhost',
            'port': '6379',
            'db': '0',
            'password': ''
        }
        
        self.config['InfluxDBConfig'] = {
            'url': 'http://localhost:8086',
            'token': '',
            'org': 'my-org',
            'bucket': 'imu-data',
            'host': 'localhost',
            'port': '8086',
            'timeout': '27',
            'verify_ssl': 'False'
        }
        
        self.config['paths'] = {
            'data_dir': 'data',
            'model_dir': 'models'
        }
        
        self.config['DrivingThresholds'] = {
            'max_acceleration': '3.5',
            'max_deceleration': '-10.07',
            'max_steering_angle': '45.0',
            'turning_window': '0.6'
        }
        
        # ====================== 基础分析配置 ======================
        self.config['BasicAnalysisThresholds'] = {
            'small_steering_angle_threshold': '4.0',
            'acceleration_positive_threshold': '0.15',
            'acceleration_negative_threshold': '-0.15',
            'steering_angle_turn_threshold': '10.0',
            'z_angular_velocity_turn_threshold': '0.08',
            'skid_acceleration_change_rate_threshold': '0.8',
            'skid_z_angular_velocity_threshold': '0.15',
            'emergency_brake_acceleration_threshold': '-8.0',
            'emergency_brake_speed_drop_threshold': '0.15',
            'curve_steering_angle_threshold': '15.0',
            'curve_acceleration_positive_threshold': '0.1',
            'curve_acceleration_negative_threshold': '-0.1',
            'curve_z_angular_velocity_speed_ratio_low': '0.001',
            'curve_z_angular_velocity_speed_ratio_high': '0.01',
            'snake_steering_angle_change_threshold': '15.0',
            'rapid_direction_change_steering_angle_threshold': '15.0',
            'steering_angle_lane_change_threshold': '10.0',
            'x_acceleration_lane_change_threshold': '0.1',
            'large_radius_turn_steering_angle_low': '10.0',
            'large_radius_turn_steering_angle_high': '20.0',
            'large_radius_turn_z_angular_velocity_low': '0.05',
            'large_radius_turn_z_angular_velocity_high': '0.15',
            'u_turn_steering_angle_threshold': '45.0',
            'u_turn_z_angular_velocity_threshold': '0.2',
            'acc_speed_range': '5.0',
            'acc_acceleration_range': '0.1',
            'a_acc_acceleration_threshold': '0.3',
            'a_acc_speed_range': '10.0',
            'brake_acceleration_low': '-0.3',
            'brake_acceleration_high': '-0.1',
            'a_brake_acceleration_threshold': '-0.5',
            'a_brake_speed_drop_threshold': '5.0',
            'constant_speed_std_threshold': '2.0',
            'constant_speed_accel_threshold': '0.075',
            'parking_speed_threshold': '3.0',
            'parking_accel_threshold': '0.05'
        }
        
        self.config['BasicAnalysisWindowSizes'] = {
            'parking_window': '15',
            'constant_speed_straight_window': '10',
            'accelerating_window': '5',
            'decelerating_window': '5',
            'turning_window': '15',
            'emergency_brake_window': '5',
            'u_turn_window': '20',
            'snake_driving_window': '30',
            'rapid_direction_change_window': '5',
            'large_radius_turning_window': '20',
            'normal_acc_window': '10',
            'aggressive_acc_window': '5',
            'normal_brake_window': '10',
            'aggressive_brake_window': '5',
            'lane_changing_window': '15'
        }
        
        # ====================== 高级分析配置 ======================
        self.config['AdvancedAnalysisConfig'] = {
            'model_path': 'models/driving_model.pkl',
            'scaler_path': 'models/driving_scaler.pkl',
            'algorithm': 'RandomForest',
            'use_cross_validation': 'True',
            'compare_algorithms': 'False',
            'n_estimators': '100',
            'max_depth': '10',
            'random_state': '42',
            'test_size': '0.2',
            'cv_folds': '5'
        }
        
        self.config['AdvancedAnalysisFeatures'] = {
            'use_speed': 'True',
            'use_accel_magnitude': 'True',
            'use_turn_rate': 'True',
            'use_speed_change_rate': 'True',
            'use_behavior_confidence': 'True'
        }
        
        # ====================== 分析对比配置 ======================
        self.config['ComparisonConfig'] = {
            'confidence_threshold': '0.8',
            'time_window_size': '100',
            'auto_sync': 'True',
            'show_data_stream': 'True'
        }
        
        self.config['Logging'] = {
            'level': 'DEBUG',
            'format': '{asctime} - {levelname} - {message}',
            'file': 'logs/app.log',
            'max_bytes': '10485760',
            'backup_count': '5'
        }
        
        self.config['UISettings'] = {
            'theme': 'dark',
            'font_size': '12',
            'language': 'zh_CN'
        }
        
        self.config['MQTTConfig'] = {
            'host': 'localhost',
            'port': '1883',
            'username': 'admin',
            'password': 'public',
            'client_id': 'vehicle_monitor',
            'keepalive': '60',
            'topic': 'vehicle/data',
            'qos': '1',
            'reconnect_interval': '5000',
            'data_topic': 'driving/data',
            'control_topic': 'vehicle/control',
            'threshold_topic': 'alarm/threshold'
        }
        
        self.config['BehaviorConfig'] = {
            'anomaly_sensitivity': '0.8',
            'window_size': '20',
            'smoothing_window': '10',
            'speed_window': '10',
            'accel_window': '15',
            'angle_window': '20',
            'speeding_threshold': '10.0',
            'speeding_window': '10',
            'rapid_acceleration_threshold': '10.0',
            'rapid_acceleration_window': '10',
            'rapid_deceleration_threshold': '10.0',
            'rapid_deceleration_window': '10',
            'sharp_turn_threshold': '10.0',
            'sharp_turn_window': '10',
            'lane_change_threshold': '10.0',
            'lane_change_window': '10',
            'tailgating_threshold': '10.0',
            'tailgating_window': '10',
            'hard_braking_threshold': '10.0',
            'hard_braking_window': '10',
            'sudden_steering_threshold': '10.0',
            'sudden_steering_window': '10',
            'overspeeding_in_curve_threshold': '10.0',
            'overspeeding_in_curve_window': '10',
            'fatigue_driving_threshold': '10.0',
            'fatigue_driving_window': '10',
            'aggressive_driving_threshold': '10.0',
            'aggressive_driving_window': '10',
            'excessive_lane_change_threshold': '10.0',
            'excessive_lane_change_window': '10',
            'speeding_on_straight_threshold': '10.0',
            'speeding_on_straight_window': '10',
            'speeding_in_school_zone_threshold': '10.0',
            'speeding_in_school_zone_window': '10',
            'speeding_in_residential_threshold': '10.0',
            'speeding_in_residential_window': '10',
            'running_red_light_threshold': '10.0',
            'running_red_light_window': '10',
            'running_stop_sign_threshold': '10.0',
            'running_stop_sign_window': '10'
        }
        
        # 保存默认配置
        self.save_config()
    
    def get_value(self, section: str, key: str, default: str = "") -> str:
        """获取配置值"""
        try:
            return self.config.get(section, key, fallback=default)
        except Exception as e:
            self.logger.error(f"获取配置值失败 [{section}][{key}]: {e}")
            return default
    
    def set_value(self, section: str, key: str, value: str) -> bool:
        """设置配置值"""
        try:
            if section not in self.config:
                self.config[section] = {}
            
            self.config[section][key] = str(value)
            
            if self.auto_save:
                self.save_config()
            
            self.config_changed.emit(section, key, str(value))
            return True
        except Exception as e:
            self.logger.error(f"设置配置值失败 [{section}][{key}]: {e}")
            return False
    
    def get_section(self, section: str) -> Dict[str, str]:
        """获取整个配置节"""
        try:
            if section in self.config:
                return dict(self.config[section])
            return {}
        except Exception as e:
            self.logger.error(f"获取配置节失败 [{section}]: {e}")
            return {}
    
    def set_section(self, section: str, data: Dict[str, str]) -> bool:
        """设置整个配置节"""
        try:
            self.config[section] = data
            if self.auto_save:
                self.save_config()
            return True
        except Exception as e:
            self.logger.error(f"设置配置节失败 [{section}]: {e}")
            return False
    
    def get_all_sections(self) -> List[str]:
        """获取所有配置节名称"""
        return list(self.config.sections())
    
    def export_config(self, file_path: str) -> bool:
        """导出配置到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self.logger.info(f"配置导出成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"配置导出失败: {e}")
            return False
    
    def import_config(self, file_path: str) -> bool:
        """从文件导入配置"""
        try:
            temp_config = configparser.ConfigParser()
            temp_config.read(file_path, encoding='utf-8')
            
            # 验证配置文件格式
            if not temp_config.sections():
                raise ValueError("无效的配置文件格式")
            
            # 更新配置
            for section in temp_config.sections():
                self.config[section] = temp_config[section]
            
            self.save_config()
            self.logger.info(f"配置导入成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"配置导入失败: {e}")
            return False
    
    def set_remote_config_url(self, url: str):
        """设置远程配置URL"""
        self.remote_config_url = url
        self.logger.info(f"远程配置URL设置: {url}")
    
    def update_from_remote(self) -> bool:
        """从远程更新配置"""
        if not self.remote_config_url:
            self.logger.warning("未设置远程配置URL")
            return False
        
        try:
            self.remote_update_started.emit()
            
            # 延迟导入requests
            global requests
            if requests is None:
                try:
                    import requests
                except ImportError:
                    self.logger.error("requests库未安装，无法进行远程配置更新")
                    self.remote_update_finished.emit(False, "requests库未安装")
                    return False
            
            response = requests.get(self.remote_config_url, timeout=30)
            response.raise_for_status()
            
            remote_config = response.json()
            
            # 更新配置
            for section, data in remote_config.items():
                if isinstance(data, dict):
                    self.set_section(section, data)
            
            self.save_config()
            self.remote_update_finished.emit(True, "远程配置更新成功")
            return True
            
        except Exception as e:
            error_msg = f"远程配置更新失败: {e}"
            self.logger.error(error_msg)
            self.remote_update_finished.emit(False, error_msg)
            return False


class RemoteConfigUpdater(QThread):
    """远程配置更新线程"""
    
    update_finished = Signal(bool, str)
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
    
    def run(self):
        """运行远程配置更新"""
        success = self.config_manager.update_from_remote()
        self.update_finished.emit(success, "更新完成")


class ConfigurationDialog(QDialog):
    """配置管理对话框"""
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setup_ui()
        self.load_config_to_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("系统配置管理")
        self.setGeometry(100, 100, 1200, 800)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 保存配置")
        self.load_btn = QPushButton("📂 加载配置")
        self.export_btn = QPushButton("📤 导出配置")
        self.import_btn = QPushButton("📥 导入配置")
        self.remote_update_btn = QPushButton("🌐 远程更新")
        self.refresh_btn = QPushButton("🔄 刷新")
        
        toolbar_layout.addWidget(self.save_btn)
        toolbar_layout.addWidget(self.load_btn)
        toolbar_layout.addWidget(self.export_btn)
        toolbar_layout.addWidget(self.import_btn)
        toolbar_layout.addWidget(self.remote_update_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧配置树
        self.config_tree = QTreeWidget()
        self.config_tree.setHeaderLabel("配置分类")
        self.config_tree.setMinimumWidth(250)
        self.config_tree.setMaximumWidth(300)
        
        # 右侧配置编辑区
        self.config_editor = QTabWidget()
        
        splitter.addWidget(self.config_tree)
        splitter.addWidget(self.config_editor)
        splitter.setSizes([250, 950])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
    
    def load_config_to_ui(self):
        """加载配置到UI"""
        self.config_tree.clear()
        
        # 获取所有配置节
        sections = self.config_manager.get_all_sections()
        
        for section in sections:
            section_item = QTreeWidgetItem(self.config_tree)
            section_item.setText(0, section)
            section_item.setData(0, Qt.UserRole, section)
            
            # 获取该节下的所有键
            section_data = self.config_manager.get_section(section)
            for key in section_data.keys():
                key_item = QTreeWidgetItem(section_item)
                key_item.setText(0, key)
                key_item.setData(0, Qt.UserRole, (section, key))
        
        self.config_tree.expandAll()
        
        # 创建配置编辑标签页
        self.create_config_editor_tabs()
    
    def create_config_editor_tabs(self):
        """创建配置编辑标签页"""
        self.config_editor.clear()
        
        sections = self.config_manager.get_all_sections()
        
        for section in sections:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # 创建表单布局
            form_layout = QFormLayout()
            
            section_data = self.config_manager.get_section(section)
            for key, value in section_data.items():
                # 根据值的类型创建相应的控件
                if self.is_numeric(value):
                    if '.' in value:
                        # 浮点数
                        widget = QDoubleSpinBox()
                        widget.setRange(-999999, 999999)
                        widget.setDecimals(6)
                        widget.setValue(float(value))
                    else:
                        # 整数
                        widget = QSpinBox()
                        widget.setRange(-999999, 999999)
                        widget.setValue(int(value))
                elif value.lower() in ['true', 'false']:
                    # 布尔值
                    widget = QCheckBox()
                    widget.setChecked(value.lower() == 'true')
                else:
                    # 字符串
                    widget = QLineEdit()
                    widget.setText(value)
                
                # 存储控件引用以便后续获取值
                widget.setProperty("section", section)
                widget.setProperty("key", key)
                
                # 连接信号
                if isinstance(widget, QLineEdit):
                    widget.textChanged.connect(self.on_config_value_changed)
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.valueChanged.connect(self.on_config_value_changed)
                elif isinstance(widget, QCheckBox):
                    widget.toggled.connect(self.on_config_value_changed)
                
                form_layout.addRow(key, widget)
            
            layout.addLayout(form_layout)
            layout.addStretch()
            
            # 添加标签页
            self.config_editor.addTab(tab, section)
    
    def is_numeric(self, value: str) -> bool:
        """判断值是否为数字"""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def connect_signals(self):
        """连接信号"""
        self.config_tree.itemClicked.connect(self.on_tree_item_clicked)
        self.save_btn.clicked.connect(self.save_config)
        self.load_btn.clicked.connect(self.load_config)
        self.export_btn.clicked.connect(self.export_config)
        self.import_btn.clicked.connect(self.import_config)
        self.remote_update_btn.clicked.connect(self.remote_update)
        self.refresh_btn.clicked.connect(self.refresh_config)
        
        # 配置管理器信号
        self.config_manager.config_saved.connect(self.on_config_saved)
        self.config_manager.config_loaded.connect(self.on_config_loaded)
        self.config_manager.remote_update_started.connect(self.on_remote_update_started)
        self.config_manager.remote_update_finished.connect(self.on_remote_update_finished)
    
    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """配置树项目点击事件"""
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple):
            # 键项目被点击
            section, key = data
            # 切换到相应的标签页
            for i in range(self.config_editor.count()):
                if self.config_editor.tabText(i) == section:
                    self.config_editor.setCurrentIndex(i)
                    break
    
    def on_config_value_changed(self):
        """配置值改变事件"""
        sender = self.sender()
        if sender:
            section = sender.property("section")
            key = sender.property("key")
            
            if isinstance(sender, QLineEdit):
                value = sender.text()
            elif isinstance(sender, (QSpinBox, QDoubleSpinBox)):
                value = str(sender.value())
            elif isinstance(sender, QCheckBox):
                value = str(sender.isChecked()).lower()
            else:
                return
            
            # 更新配置
            self.config_manager.set_value(section, key, value)
            self.status_label.setText(f"配置已更新: [{section}][{key}] = {value}")
    
    def save_config(self):
        """保存配置"""
        try:
            if self.config_manager.save_config():
                self.status_label.setText("配置保存成功")
                QMessageBox.information(self, "成功", "配置保存成功！")
            else:
                self.status_label.setText("配置保存失败")
                QMessageBox.warning(self, "错误", "配置保存失败！")
        except Exception as e:
            self.status_label.setText(f"保存失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置时发生错误：{e}")
    
    def load_config(self):
        """加载配置"""
        try:
            if self.config_manager.load_config():
                self.load_config_to_ui()
                self.status_label.setText("配置加载成功")
                QMessageBox.information(self, "成功", "配置加载成功！")
            else:
                self.status_label.setText("配置加载失败")
                QMessageBox.warning(self, "错误", "配置加载失败！")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
            QMessageBox.critical(self, "错误", f"加载配置时发生错误：{e}")
    
    def export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "", "INI Files (*.ini);;All Files (*)"
        )
        if file_path:
            try:
                if self.config_manager.export_config(file_path):
                    self.status_label.setText("配置导出成功")
                    QMessageBox.information(self, "成功", "配置导出成功！")
                else:
                    self.status_label.setText("配置导出失败")
                    QMessageBox.warning(self, "错误", "配置导出失败！")
            except Exception as e:
                self.status_label.setText(f"导出失败: {e}")
                QMessageBox.critical(self, "错误", f"导出配置时发生错误：{e}")
    
    def import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "INI Files (*.ini);;All Files (*)"
        )
        if file_path:
            try:
                if self.config_manager.import_config(file_path):
                    self.load_config_to_ui()
                    self.status_label.setText("配置导入成功")
                    QMessageBox.information(self, "成功", "配置导入成功！")
                else:
                    self.status_label.setText("配置导入失败")
                    QMessageBox.warning(self, "错误", "配置导入失败！")
            except Exception as e:
                self.status_label.setText(f"导入失败: {e}")
                QMessageBox.critical(self, "错误", f"导入配置时发生错误：{e}")
    
    def remote_update(self):
        """远程更新配置"""
        # 检查是否设置了远程URL
        if not self.config_manager.remote_config_url:
            url, ok = QMessageBox.getText(self, "远程配置", "请输入远程配置URL:")
            if ok and url:
                self.config_manager.set_remote_config_url(url)
            else:
                return
        
        # 确认更新
        reply = QMessageBox.question(
            self, "确认更新", 
            f"确定要从远程更新配置吗？\nURL: {self.config_manager.remote_config_url}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 启动远程更新线程
            self.remote_updater = RemoteConfigUpdater(self.config_manager)
            self.remote_updater.update_finished.connect(self.on_remote_update_finished)
            self.remote_updater.start()
    
    def refresh_config(self):
        """刷新配置"""
        self.load_config_to_ui()
        self.status_label.setText("配置已刷新")
    
    def on_config_saved(self):
        """配置保存成功事件"""
        self.status_label.setText("配置保存成功")
    
    def on_config_loaded(self):
        """配置加载成功事件"""
        self.status_label.setText("配置加载成功")
    
    def on_remote_update_started(self):
        """远程更新开始事件"""
        self.status_label.setText("正在从远程更新配置...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 无限进度条
        self.remote_update_btn.setEnabled(False)
    
    def on_remote_update_finished(self, success: bool, message: str):
        """远程更新完成事件"""
        self.progress_bar.setVisible(False)
        self.remote_update_btn.setEnabled(True)
        
        if success:
            self.status_label.setText("远程配置更新成功")
            self.load_config_to_ui()
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("远程配置更新失败")
            QMessageBox.warning(self, "错误", message)
    
    def on_remote_update_finished(self, success: bool, message: str):
        """远程更新完成事件（线程信号）"""
        self.progress_bar.setVisible(False)
        self.remote_update_btn.setEnabled(True)
        
        if success:
            self.status_label.setText("远程配置更新成功")
            self.load_config_to_ui()
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("远程配置更新失败")
            QMessageBox.warning(self, "错误", message)


if __name__ == "__main__":
    # 测试配置管理器
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    # 创建配置对话框
    dialog = ConfigurationDialog(config_manager)
    dialog.show()
    
    sys.exit(app.exec())
