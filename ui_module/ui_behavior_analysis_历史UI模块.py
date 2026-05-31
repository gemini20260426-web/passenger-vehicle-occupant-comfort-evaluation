#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
行为分析UI组件
基于data_processing/visual.py中的AnalysisDashboard类重构
"""

import sys
import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import matplotlib
matplotlib.use('cairo', force=True)  # 使用cairo后端避免QPainter问题
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QDateTime, QMutex, QMutexLocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QLabel, QTextEdit, QTableWidget, QTableWidgetItem,
                               QPushButton, QHeaderView, QTabWidget, QProgressBar,
                               QSplitter, QComboBox, QSpinBox, QDoubleSpinBox, 
                               QCheckBox, QMessageBox, QFileDialog, QFormLayout,
                               QLineEdit, QApplication, QMainWindow, QDialog,
                               QDialogButtonBox, QListWidget, QFrame, QSizePolicy)
from PySide6.QtGui import QAction, QColor, QFont, QTextCursor

# 导入数据源相关库
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    serial = None
try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None
try:
    import redis
except ImportError:
    redis = None
try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    mysql = None
    Error = Exception

# 导入分析模块
try:
    from data_processing.base_analyzer import BasicDrivingAnalyzer, BEHAVIOR_TYPES
    from data_processing.BehaviorAnalyzer import BehaviorEventDispatcher
    from data_processing.analysis import AdvancedBehaviorAnalyzer
except ImportError as e:
    print(f"导入分析模块失败: {e}")
    # 创建模拟类以避免启动错误
    class BasicDrivingAnalyzer:
        def __init__(self):
            self.thresholds = {}
    
    class BehaviorEventDispatcher:
        def __init__(self, analyzer):
            pass
    
    class AdvancedBehaviorAnalyzer:
        pass
    BEHAVIOR_TYPES = []

# 添加对dashboard模块的导入支持
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入字体工具模块
try:
    from utils.font_utils import setup_chinese_fonts
except ImportError as e:
    print(f"导入字体工具模块失败: {e}")
    def setup_chinese_fonts():
        pass

# 延迟字体设置，直到需要时再调用
selected_font = None


class MPLCanvas(FigureCanvas):
    """Matplotlib画布封装"""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        try:
            self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
            super().__init__(self.fig)
            self.setParent(parent)
        except Exception as e:
            logging.error(f"MPLCanvas初始化失败: {e}")
            raise


class BehaviorAnalysisWidget(QWidget):
    """行为分析显示组件"""
    
    def __init__(self, analyzer=None, parent=None):
        try:
            super().__init__(parent)
            
            # 数据缓存
            self.base_results = []
            self.advanced_results = []
            self.event_log = []
            
            # 初始化分析器
            try:
                self.analyzer = analyzer or BasicDrivingAnalyzer()
                # 确保BEHAVIOR_TYPES在实例中可用
                self.BEHAVIOR_TYPES = BEHAVIOR_TYPES
            except Exception as e:
                logging.error(f"初始化分析器失败: {e}")
                # 创建一个基础的分析器作为后备
                class DummyAnalyzer:
                    def __init__(self):
                        self.thresholds = {
                            "max_acceleration": 4.0,
                            "max_deceleration": -8.0,
                            "sharp_turn_angle": 25.0,
                            "high_speed_limit": 120.0
                        }
                    
                    def analyze(self, data):
                        return {
                            "timestamp": datetime.now().isoformat(),
                            "behavior": "normal",
                            "confidence": 0.85,
                            "raw_data": data,
                            "detected_all": ["normal"]
                        }
                
                self.analyzer = DummyAnalyzer()
                # 即使在后备模式下，也要确保BEHAVIOR_TYPES可用
                self.BEHAVIOR_TYPES = BEHAVIOR_TYPES if 'BEHAVIOR_TYPES' in globals() else ["normal"]
            
            try:
                self.event_dispatcher = BehaviorEventDispatcher(self.analyzer)
            except:
                self.event_dispatcher = None
            
            # 初始化UI
            self._init_ui()
            
            # 初始化定时器
            try:
                self.update_timer = QTimer(self)
                self.update_timer.timeout.connect(self._update_display)
                self.update_timer.start(1000)  # 每秒更新一次
                
                # 日志更新定时器
                self.log_timer = QTimer(self)
                self.log_timer.timeout.connect(self._update_event_log)
                self.log_timer.start(5000)  # 每5秒更新一次日志
            except Exception as e:
                logging.warning(f"初始化定时器失败: {e}")
            
            logging.info("行为分析组件初始化完成")
        except Exception as e:
            error_msg = f"BehaviorAnalysisWidget初始化过程中发生错误: {str(e)}"
            print(error_msg)
            logging.error(error_msg, exc_info=True)
            
            # 显示错误信息给用户
            try:
                QMessageBox.critical(parent, "初始化错误", 
                                   f"行为分析组件初始化过程中发生错误:\n{str(e)}\n\n请检查日志文件获取详细信息。")
            except:
                pass  # 如果连QMessageBox都无法显示，就只能打印错误信息了
            
            # 重新抛出异常，让上层处理
            raise

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 主标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 1. 实时监控标签页（已移除）
        self.monitor_tab = QWidget()
        self._init_monitor_tab()
        
        # 2. 分析结果标签页
        self.results_tab = QWidget()
        self._init_results_tab()
        self.tabs.addTab(self.results_tab, "分析结果")
        
        # 3. 模型训练标签页
        self.model_tab = QWidget()
        self._init_model_tab()
        self.tabs.addTab(self.model_tab, "模型训练")
        
        # 4. 系统配置标签页
        self.config_tab = QWidget()
        self._init_config_tab()
        self.tabs.addTab(self.config_tab, "系统配置")
        
        # 5. 行为统计标签页
        try:
            # 尝试导入仪表盘模块
            sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard_module'))
            from dashboard import VehicleDashboard
            
            # 创建一个简化版的配置管理器和数据库处理器占位符
            from PySide6.QtCore import QObject, Signal
            
            class DummyConfigManager(QObject):
                config_updated = Signal(str, dict)  # 添加信号
                
                def get_config(self, name):
                    return {}
                
                def __getattr__(self, name):
                    # 为缺失的属性提供默认实现
                    return lambda *args, **kwargs: None

            class DummyDBHandler:
                def __init__(self):
                    pass
                
                def __getattr__(self, name):
                    # 为缺失的方法提供默认实现
                    return lambda *args, **kwargs: None
            
            # 创建仪表盘实例
            dummy_config = DummyConfigManager()
            dummy_db = DummyDBHandler()
            self.industry_stats_tab = VehicleDashboard(dummy_config, dummy_db)
            self.tabs.addTab(self.industry_stats_tab, "行为统计")
        except Exception as e:
            print(f"行为统计标签页初始化失败: {e}")
            import traceback
            traceback.print_exc()
            # 如果仪表盘模块失败，则使用占位符
            placeholder = QLabel("行为统计模块暂不可用")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("font-size: 16px; color: gray;")
            container = QWidget()
            layout_container = QVBoxLayout(container)
            layout_container.addWidget(placeholder)
            self.tabs.addTab(container, "行为统计")
        
    def _init_monitor_tab(self) -> None:
        """初始化实时监控标签页"""
        # 主布局
        layout = QVBoxLayout(self.monitor_tab)
        
        # 图表区域（使用分割器）
        splitter = QSplitter(Qt.Vertical)
        
        # 上部分图表（2行2列）
        top_charts = QWidget()
        top_layout = QVBoxLayout(top_charts)
        self.top_canvas = MPLCanvas(width=12, height=6, dpi=100)
        top_layout.addWidget(self.top_canvas)
        splitter.addWidget(top_charts)
        
        # 下部分图表（2行1列）
        bottom_charts = QWidget()
        bottom_layout = QVBoxLayout(bottom_charts)
        self.bottom_canvas = MPLCanvas(width=12, height=6, dpi=100)
        bottom_layout.addWidget(self.bottom_canvas)
        splitter.addWidget(bottom_charts)
        
        # 设置分割器初始大小
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # 初始化图表
        self._init_monitor_plots()

    def _init_monitor_plots(self) -> None:
        """初始化监控图表"""
        # 上部图表
        self.top_gs = gridspec.GridSpec(2, 2, figure=self.top_canvas.fig)
        self.ax_speed = self.top_canvas.fig.add_subplot(self.top_gs[0, 0])  # 速度曲线
        self.ax_accel = self.top_canvas.fig.add_subplot(self.top_gs[0, 1])  # 加速度曲线
        self.ax_gyro = self.top_canvas.fig.add_subplot(self.top_gs[1, 0])   # 陀螺仪曲线
        self.ax_confidence = self.top_canvas.fig.add_subplot(self.top_gs[1, 1])  # 置信度
        
        # 下部图表
        self.bottom_gs = gridspec.GridSpec(2, 1, figure=self.bottom_canvas.fig)
        self.ax_behavior = self.bottom_canvas.fig.add_subplot(self.bottom_gs[0, 0])  # 行为分布
        self.ax_comparison = self.bottom_canvas.fig.add_subplot(self.bottom_gs[1, 0])  # 基础vs高级分析对比

    def _init_results_tab(self) -> None:
        """初始化分析结果标签页"""
        layout = QVBoxLayout(self.results_tab)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 表格区域
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "时间戳", "基础行为", "高级行为", "置信度", "一致性"
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.results_table)
        
        splitter.addWidget(table_widget)
        
        # 日志区域
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(QLabel("分析日志:"))
        log_layout.addWidget(self.log_text)
        
        splitter.addWidget(log_widget)
        
        # 设置分割器比例
        splitter.setSizes([500, 300])
        layout.addWidget(splitter)

    def _init_model_tab(self) -> None:
        """初始化模型训练标签页"""
        layout = QVBoxLayout(self.model_tab)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 训练配置区域
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        
        # 训练控制
        train_ctrl_group = QGroupBox("模型训练控制")
        train_ctrl_layout = QHBoxLayout()
        
        self.train_btn = QPushButton("开始训练")
        self.cancel_train_btn = QPushButton("取消训练")
        self.cancel_train_btn.setEnabled(False)
        self.load_data_btn = QPushButton("加载训练数据")
        
        train_ctrl_layout.addWidget(self.train_btn)
        train_ctrl_layout.addWidget(self.cancel_train_btn)
        train_ctrl_layout.addWidget(self.load_data_btn)
        train_ctrl_group.setLayout(train_ctrl_layout)
        config_layout.addWidget(train_ctrl_group)
        
        # 训练参数
        param_group = QGroupBox("训练参数")
        param_layout = QFormLayout()
        
        self.sample_count_label = QLabel("可用样本: 0")
        self.train_test_split = QDoubleSpinBox()
        self.train_test_split.setRange(0.1, 0.9)
        self.train_test_split.setValue(0.2)
        self.train_test_split.setSuffix(" (测试集比例)")
        
        param_layout.addRow("样本数量:", self.sample_count_label)
        param_layout.addRow("数据集划分:", self.train_test_split)
        param_group.setLayout(param_layout)
        config_layout.addWidget(param_group)
        
        # 训练进度
        progress_group = QGroupBox("训练进度")
        progress_layout = QVBoxLayout()
        
        self.train_progress = QProgressBar()
        self.train_progress.setRange(0, 100)
        self.train_status = QLabel("等待训练...")
        
        progress_layout.addWidget(self.train_progress)
        progress_layout.addWidget(self.train_status)
        progress_group.setLayout(progress_layout)
        config_layout.addWidget(progress_group)
        
        # 训练结果
        result_group = QGroupBox("训练结果")
        result_layout = QFormLayout()
        
        self.model_accuracy = QLabel("准确率: --")
        self.model_status = QLabel("状态: 未训练")
        
        result_layout.addRow("模型状态:", self.model_status)
        result_layout.addRow("模型准确率:", self.model_accuracy)
        result_group.setLayout(result_layout)
        config_layout.addWidget(result_group)
        
        config_layout.addStretch(1)
        splitter.addWidget(config_widget)
        
        # 训练日志和详细结果
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        self.train_log = QTextEdit()
        self.train_log.setReadOnly(True)
        log_layout.addWidget(QLabel("训练日志:"))
        log_layout.addWidget(self.train_log)
        
        splitter.addWidget(log_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

    def _init_config_tab(self) -> None:
        """初始化系统配置标签页"""
        layout = QVBoxLayout(self.config_tab)
        
        # 创建配置标签页控件
        config_tabs = QTabWidget()
        layout.addWidget(config_tabs)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 基础分析阈值配置
        base_config_widget = QWidget()
        base_config_layout = QVBoxLayout(base_config_widget)
        
        base_group = QGroupBox("基础行为分析阈值配置")
        base_form = QFormLayout()
        
        # 阈值配置控件
        self.max_accel_edit = QDoubleSpinBox()
        self.max_accel_edit.setRange(0, 10)
        self.max_accel_edit.setValue(getattr(self.analyzer.thresholds, "EMERGENCY_BRAKE_ACCELERATION_THRESHOLD", -8.0))
        
        self.max_decel_edit = QDoubleSpinBox()
        self.max_decel_edit.setRange(-20, 0)
        self.max_decel_edit.setValue(getattr(self.analyzer.thresholds, "A_BRAKE_ACCELERATION_THRESHOLD", -0.5))
        
        self.sharp_turn_edit = QDoubleSpinBox()
        self.sharp_turn_edit.setRange(0, 90)
        self.sharp_turn_edit.setValue(getattr(self.analyzer.thresholds, "STEERING_ANGLE_TURN_THRESHOLD", 10.0))
        
        self.high_speed_edit = QDoubleSpinBox()
        self.high_speed_edit.setRange(50, 200)
        self.high_speed_edit.setValue(getattr(self.analyzer.thresholds, "CONSTANT_SPEED_STD_THRESHOLD", 2.0))
        
        # 添加到表单
        base_form.addRow("紧急刹车加速度阈值:", self.max_accel_edit)
        base_form.addRow("激进刹车加速度阈值:", self.max_decel_edit)
        base_form.addRow("转向方向盘角度阈值:", self.sharp_turn_edit)
        base_form.addRow("匀速行驶速度标准差阈值:", self.high_speed_edit)
        
        base_group.setLayout(base_form)
        base_config_layout.addWidget(base_group)
        
        # 添加保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._save_config)
        base_config_layout.addWidget(save_btn)
        base_config_layout.addStretch()
        
        # 高级配置标签页
        advanced_config_widget = QWidget()
        advanced_config_layout = QVBoxLayout(advanced_config_widget)
        
        # 行为检测开关
        behavior_group = QGroupBox("行为检测开关")
        behavior_layout = QVBoxLayout()
        
        # 创建行为检测开关复选框
        self.behavior_checkboxes = {}
        for behavior in self.BEHAVIOR_TYPES:
            if behavior != "normal":  # 跳过正常行为
                checkbox = QCheckBox(behavior)
                checkbox.setChecked(True)  # 默认启用所有行为检测
                self.behavior_checkboxes[behavior] = checkbox
                behavior_layout.addWidget(checkbox)
        
        behavior_group.setLayout(behavior_layout)
        advanced_config_layout.addWidget(behavior_group)
        
        # 置信度阈值设置
        confidence_group = QGroupBox("置信度阈值设置")
        confidence_form = QFormLayout()
        
        self.confidence_threshold_edit = QDoubleSpinBox()
        self.confidence_threshold_edit.setRange(0.0, 1.0)
        self.confidence_threshold_edit.setSingleStep(0.05)
        self.confidence_threshold_edit.setValue(0.8)
        
        confidence_form.addRow("最低置信度阈值:", self.confidence_threshold_edit)
        confidence_group.setLayout(confidence_form)
        advanced_config_layout.addWidget(confidence_group)
        
        # 添加保存按钮
        advanced_save_btn = QPushButton("保存高级配置")
        advanced_save_btn.clicked.connect(self._save_advanced_config)
        advanced_config_layout.addWidget(advanced_save_btn)
        advanced_config_layout.addStretch()
        
        # 添加标签页
        config_tabs.addTab(base_config_widget, "基础配置")
        config_tabs.addTab(advanced_config_widget, "高级配置")
        
        # 设置分割器比例
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

    def _save_threshold_config(self) -> None:
        """保存阈值配置"""
        try:
            # 获取用户输入的阈值
            max_accel = self.max_accel_edit.value()
            max_decel = self.max_decel_edit.value()
            sharp_turn = self.sharp_turn_edit.value()
            high_speed = self.high_speed_edit.value()
            
            # 更新分析器的阈值
            self.analyzer.thresholds["max_acceleration"] = max_accel
            self.analyzer.thresholds["max_deceleration"] = max_decel
            self.analyzer.thresholds["sharp_turn_angle"] = sharp_turn
            self.analyzer.thresholds["high_speed_limit"] = high_speed
            
            # 显示保存成功的消息
            QMessageBox.information(self, "保存成功", "阈值配置已保存")
            
            # 记录日志
            self.logger.info(f"阈值配置已更新: max_accel={max_accel}, max_decel={max_decel}, "
                           f"sharp_turn={sharp_turn}, high_speed={high_speed}")
        except Exception as e:
            self.logger.error(f"保存阈值配置时出错: {e}")
            QMessageBox.critical(self, "保存失败", f"保存阈值配置时出错: {str(e)}")

    def update_visualization(self) -> None:
        """更新可视化图表"""
        if not self.base_results:
            # 清除图表
            for ax in [self.ax_speed, self.ax_accel, self.ax_gyro, 
                      self.ax_confidence, self.ax_behavior, self.ax_comparison]:
                ax.clear()
            
            # 显示空图表提示信息
            self.ax_speed.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                              verticalalignment='center', transform=self.ax_speed.transAxes)
            self.ax_accel.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                              verticalalignment='center', transform=self.ax_accel.transAxes)
            self.ax_gyro.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                             verticalalignment='center', transform=self.ax_gyro.transAxes)
            self.ax_confidence.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                                   verticalalignment='center', transform=self.ax_confidence.transAxes)
            self.ax_behavior.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                                verticalalignment='center', transform=self.ax_behavior.transAxes)
            self.ax_comparison.text(0.5, 0.5, '等待数据...', horizontalalignment='center', 
                                   verticalalignment='center', transform=self.ax_comparison.transAxes)
            
            # 设置标题
            self.ax_speed.set_title("车辆速度 (km/h)")
            self.ax_accel.set_title("加速度 magnitude (m/s²)")
            self.ax_gyro.set_title("转向角速度 (deg/s)")
            self.ax_confidence.set_title("行为判定置信度")
            self.ax_behavior.set_title("近期行为分布")
            self.ax_comparison.set_title("分析一致性")
            
            # 刷新画布
            self.top_canvas.draw()
            self.bottom_canvas.draw()
            return
            
        # 只使用最近的数据进行绘制
        recent_count = min(100, len(self.base_results))
        recent_base = self.base_results[-recent_count:]
        recent_advanced = self.advanced_results[-recent_count:] if self.advanced_results else []
        
        # 清除图表
        for ax in [self.ax_speed, self.ax_accel, self.ax_gyro, 
                  self.ax_confidence, self.ax_behavior, self.ax_comparison]:
            ax.clear()
        
        # 准备时间数据
        try:
            times = [datetime.fromisoformat(r["timestamp"]) for r in recent_base]
        except Exception:
            # 如果时间格式不正确，使用索引代替
            times = list(range(len(recent_base)))
        
        # 1. 速度曲线
        speeds = [r.get("raw_data", {}).get("speed", 0) for r in recent_base]
        self.ax_speed.plot(times, speeds, 'b-')
        self.ax_speed.set_title("车辆速度 (km/h)")
        self.ax_speed.axhline(y=getattr(self.analyzer.thresholds, "CONSTANT_SPEED_STD_THRESHOLD", 120),
                             color='r', linestyle='--', label='高速阈值')
        self.ax_speed.axhline(y=getattr(self.analyzer.thresholds, "low_speed_limit", 20),
                             color='orange', linestyle='--', label='低速阈值')
        self.ax_speed.legend()
        self.ax_speed.tick_params(axis='x', rotation=45)
        
        # 2. 加速度曲线
        accels = [np.linalg.norm([r.get("raw_data", {}).get("ax", 0), 
                                 r.get("raw_data", {}).get("ay", 0), 
                                 r.get("raw_data", {}).get("az", 0)]) 
                 for r in recent_base]
        self.ax_accel.plot(times, accels, 'r-')
        self.ax_accel.set_title("加速度 magnitude (m/s²)")
        self.ax_accel.axhline(y=getattr(self.analyzer.thresholds, "EMERGENCY_BRAKE_ACCELERATION_THRESHOLD", 4),
                             color='r', linestyle='--', label='急加速阈值')
        self.ax_accel.legend()
        self.ax_accel.tick_params(axis='x', rotation=45)
        
        # 3. 陀螺仪曲线 (转向)
        gyros = [r.get("raw_data", {}).get("gy", 0) for r in recent_base]
        self.ax_gyro.plot(times, gyros, 'g-')
        self.ax_gyro.set_title("转向角速度 (deg/s)")
        self.ax_gyro.axhline(y=getattr(self.analyzer.thresholds, "STEERING_ANGLE_TURN_THRESHOLD", 25),
                            color='r', linestyle='--')
        self.ax_gyro.axhline(y=-getattr(self.analyzer.thresholds, "STEERING_ANGLE_TURN_THRESHOLD", 25),
                            color='r', linestyle='--', label='急转弯阈值')
        self.ax_gyro.legend()
        self.ax_gyro.tick_params(axis='x', rotation=45)
        
        # 4. 置信度曲线
        confidences = [r.get("confidence", 0) for r in recent_base]
        self.ax_confidence.plot(times, confidences, 'purple')
        self.ax_confidence.set_title("行为判定置信度")
        self.ax_confidence.set_ylim(0, 1)
        self.ax_confidence.tick_params(axis='x', rotation=45)
        
        # 5. 行为分布
        recent_behaviors = [r.get("behavior", "") for r in recent_base]
        behavior_counts = {}
        for b in self.BEHAVIOR_TYPES:
            cnt = recent_behaviors.count(b)
            if cnt > 0:
                behavior_counts[b] = cnt
        
        if behavior_counts:
            behaviors = list(behavior_counts.keys())
            counts = list(behavior_counts.values())
            # 将行为分布图改为水平放置的条形图
            self.ax_behavior.barh(behaviors, counts)
            self.ax_behavior.set_title("近期行为分布")
            # 移除旋转，因为水平条形图标签是垂直排列的
            self.ax_behavior.tick_params(axis='y', rotation=0)
        
        # 6. 基础vs高级分析对比
        if recent_advanced:
            # 计算一致性比例
            consistent = sum(1 for r in recent_advanced if r.get("comparison", "") == "一致")
            inconsistent = len(recent_advanced) - consistent
            
            self.ax_comparison.bar(["一致", "不一致"], [consistent, inconsistent], 
                                  color=['green', 'red'])
            self.ax_comparison.set_title(f"分析一致性 ({consistent}/{len(recent_advanced)})")
            self.ax_comparison.set_ylim(0, len(recent_advanced) * 1.1)
        
        # 刷新画布
        self.top_canvas.draw()
        self.bottom_canvas.draw()
        
    def _update_display(self):
        """更新显示内容"""
        # 这里保留原始方法以保持兼容性
        pass
            
    def _update_event_log(self):
        """更新事件日志"""
        # 这里保留原始方法以保持兼容性
        pass
            
    def _clear_records(self):
        """清空记录"""
        # 这里保留原始方法以保持兼容性
        pass
        
    def update_analysis(self, analysis_result):
        """
        更新行为分析结果显示
        
        Args:
            analysis_result (dict): 二次分析结果
        """
        if not analysis_result:
            return
            
        # 将分析结果添加到缓存中
        self.base_results.append(analysis_result)
        
        # 限制缓存大小
        if len(self.base_results) > self.max_cache_size:
            self.base_results = self.base_results[-self.max_cache_size:]
            
        # 触发告警检查
        self._check_and_trigger_alarm(analysis_result)
            
        # 更新可视化
        self.update_visualization()
        
    def _check_and_trigger_alarm(self, analysis_result):
        """
        检查分析结果并触发告警
        
        Args:
            analysis_result (dict): 二次分析结果
        """
        try:
            # 获取置信度
            confidence = analysis_result.get('confidence', 0)
            behavior = analysis_result.get('behavior', 'normal')
            
            # 如果是正常行为，不触发告警
            if behavior == 'normal':
                return
                
            # 根据置信度确定告警级别
            alarm_level = 'normal'  # 默认一般告警
            if confidence >= 0.8:
                alarm_level = 'emergency'  # 紧急告警
            elif confidence >= 0.6:
                alarm_level = 'serious'    # 严重告警
            elif confidence >= 0.3:
                alarm_level = 'normal'     # 一般告警
            else:
                return  # 置信度太低，不触发告警
                
            # 获取主控制器实例来触发告警（如果可用）
            try:
                from main_module.main_controller import MainController
                # 注意：这里可能需要根据实际项目结构调整
                # 通常可以通过信号或回调函数来触发告警
                pass
            except ImportError:
                pass
                
        except Exception as e:
            print(f"告警检查过程中出错: {e}")
    
    def _save_config(self):
        """保存基础配置"""
        try:
            # 获取用户设置的值
            max_accel = self.max_accel_edit.value()
            max_decel = self.max_decel_edit.value()
            sharp_turn = self.sharp_turn_edit.value()
            high_speed = self.high_speed_edit.value()
            
            # 更新分析器的阈值
            if hasattr(self.analyzer, 'thresholds'):
                self.analyzer.thresholds.EMERGENCY_BRAKE_ACCELERATION_THRESHOLD = max_accel
                self.analyzer.thresholds.A_BRAKE_ACCELERATION_THRESHOLD = max_decel
                self.analyzer.thresholds.STEERING_ANGLE_TURN_THRESHOLD = sharp_turn
                self.analyzer.thresholds.CONSTANT_SPEED_STD_THRESHOLD = high_speed
            
            QMessageBox.information(self, "配置保存", 
                                  f"配置已保存并应用:\n"
                                  f"紧急刹车加速度阈值: {max_accel}\n"
                                  f"激进刹车加速度阈值: {max_decel}\n"
                                  f"转向方向盘角度阈值: {sharp_turn}\n"
                                  f"匀速行驶速度标准差阈值: {high_speed}")
            
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存配置时出错: {str(e)}")

    def _save_advanced_config(self):
        """保存高级配置"""
        try:
            # 获取置信度阈值
            confidence_threshold = self.confidence_threshold_edit.value()
            
            # 获取行为检测开关状态
            enabled_behaviors = []
            disabled_behaviors = []
            for behavior, checkbox in self.behavior_checkboxes.items():
                if checkbox.isChecked():
                    enabled_behaviors.append(behavior)
                else:
                    disabled_behaviors.append(behavior)
            
            # 显示配置信息
            QMessageBox.information(self, "高级配置保存",
                                  f"配置已保存:\n"
                                  f"最低置信度阈值: {confidence_threshold}\n"
                                  f"启用的行为检测: {', '.join(enabled_behaviors) if enabled_behaviors else '无'}\n"
                                  f"禁用的行为检测: {', '.join(disabled_behaviors) if disabled_behaviors else '无'}")
            
            # 如果需要实际应用这些配置，可以在这里添加代码
            # 例如，保存到配置文件或更新分析器设置
            
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存高级配置时出错: {str(e)}")


# 如果需要单独测试
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("BehaviorAnalysisWidget Test")
            self.setGeometry(100, 100, 1200, 800)
            
            # 创建测试部件
            central_widget = BehaviorAnalysisWidget()
            self.setCentralWidget(central_widget)

            # 运行测试
            app = QApplication(sys.argv)
            window = TestWindow()
            window.show()
            sys.exit(app.exec())
