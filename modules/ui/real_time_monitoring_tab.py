#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 优化日期: 2026-05-07
# 优化内容: 重构为五视图专业架构（仪表盘/时间轴/风险评估/特征分析/分析对比）
#          基于五层智能驾驶分析管道，符合专业HMI标准
# ============================================================

"""
实时驾驶监控标签页 — v3.0 专业版
包含五个标签页：综合仪表盘、行为时间轴、风险评估、特征分析、分析对比
"""

import logging
import time
import pickle
import json
from datetime import datetime

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QLabel, QPushButton, QTextEdit, QTableWidget,
                               QTableWidgetItem, QHeaderView,
                               QProgressBar, QScrollArea, QGridLayout,
                               QTabWidget, QComboBox, QDoubleSpinBox, QSpinBox,
                               QFileDialog, QFormLayout, QCheckBox, QMessageBox,
                               QDialog, QFrame, QSplitter)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from modules.ui.driving_risk_dashboard import DrivingRiskDashboard
from modules.ui.behavior_timeline_view import BehaviorTimelineView
from modules.ui.feature_analysis_view import FeatureAnalysisView
from core.core.analysis.clearable_registry import ClearableResource, ClearableRegistry

try:
    from core.core.seat_evaluation.metadata_registry import get_global_registry
    _metadata_registry_available = True
except ImportError:
    _metadata_registry_available = False

# 延迟导入matplotlib以避免Qt初始化问题
try:
    import matplotlib
    matplotlib.use('qtagg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("警告: matplotlib不可用，图表功能将被禁用")


# 根据matplotlib可用性定义MPLCanvas
if MATPLOTLIB_AVAILABLE:
    class MPLCanvas(FigureCanvas):
        """Matplotlib画布包装器"""
        def __init__(self, parent=None, width=8, height=6, dpi=100):
            self.fig = Figure(figsize=(width, height), dpi=dpi)
            super().__init__(self.fig)
            self.setParent(parent)
            self.setMinimumSize(400, 300)
else:
    class MPLCanvas(QWidget):
        """Matplotlib不可用时的占位画布"""
        def __init__(self, parent=None, width=8, height=6, dpi=100):
            super().__init__(parent)
            self.setVisible(False)
            self.fig = None  # 避免后续访问出错


class ConfigDialog(QDialog):
    """基础分析配置对话框 - 标签页形式"""

    config_applied = Signal()

    THRESHOLD_LABELS = {
        'small_steering_angle_threshold': '小方向盘角度阈值',
        'acceleration_positive_threshold': '正向加速度阈值',
        'acceleration_negative_threshold': '负向加速度阈值',
        'steering_angle_turn_threshold': '转向方向盘角度阈值',
        'z_angular_velocity_turn_threshold': 'Z轴角速度转向阈值',
        'skid_acceleration_change_rate_threshold': '侧滑加速度变化率阈值',
        'skid_z_angular_velocity_threshold': '侧滑Z轴角速度阈值',
        'emergency_brake_acceleration_threshold': '紧急刹车加速度阈值',
        'emergency_brake_speed_drop_threshold': '紧急刹车速度下降阈值',
        'curve_steering_angle_threshold': '弯道方向盘角度阈值',
        'curve_acceleration_positive_threshold': '弯道正向加速度阈值',
        'curve_acceleration_negative_threshold': '弯道负向加速度阈值',
        'curve_z_angular_velocity_speed_ratio_low': '弯道角速度/速度比下限',
        'curve_z_angular_velocity_speed_ratio_high': '弯道角速度/速度比上限',
        'snake_steering_angle_change_threshold': '蛇形驾驶方向盘变化阈值',
        'rapid_direction_change_steering_angle_threshold': '快速变向方向盘角度阈值',
        'steering_angle_lane_change_threshold': '变道方向盘角度阈值',
        'x_acceleration_lane_change_threshold': '变道X轴加速度阈值',
        'large_radius_turn_steering_angle_low': '大半径转弯方向盘角度下限',
        'large_radius_turn_steering_angle_high': '大半径转弯方向盘角度上限',
        'large_radius_turn_z_angular_velocity_low': '大半径转弯Z轴角速度下限',
        'large_radius_turn_z_angular_velocity_high': '大半径转弯Z轴角速度上限',
        'u_turn_steering_angle_threshold': 'U型转弯方向盘角度阈值',
        'u_turn_z_angular_velocity_threshold': 'U型转弯Z轴角速度阈值',
        'acc_speed_range': '加速速度范围',
        'acc_acceleration_range': '加速加速度范围',
        'a_acc_acceleration_threshold': '激进加速加速度阈值',
        'a_acc_speed_range': '激进加速速度范围',
        'brake_acceleration_low': '刹车加速度下限',
        'brake_acceleration_high': '刹车加速度上限',
        'a_brake_acceleration_threshold': '激进刹车加速度阈值',
        'a_brake_speed_drop_threshold': '激进刹车速度下降阈值',
        'constant_speed_std_threshold': '匀速行驶速度标准差阈值',
        'constant_speed_accel_threshold': '匀速行驶加速度阈值',
        'parking_speed_threshold': '停车速度阈值',
        'parking_accel_threshold': '停车加速度阈值'
    }

    WINDOW_LABELS = {
        'parking_window': '停车检测窗口',
        'constant_speed_straight_window': '匀速直线窗口',
        'accelerating_window': '加速窗口',
        'decelerating_window': '减速窗口',
        'turning_window': '转弯窗口',
        'emergency_brake_window': '紧急刹车窗口',
        'u_turn_window': 'U型转弯窗口',
        'snake_driving_window': '蛇形驾驶窗口',
        'rapid_direction_change_window': '快速变向窗口',
        'large_radius_turning_window': '大半径转弯窗口',
        'normal_acc_window': '正常加速窗口',
        'aggressive_acc_window': '激进加速窗口',
        'normal_brake_window': '正常刹车窗口',
        'aggressive_brake_window': '激进刹车窗口',
        'lane_changing_window': '变道窗口'
    }

    def __init__(self, config_manager, parent=None):
        _t0 = time.perf_counter()
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("基础分析配置")
        self.setMinimumWidth(750)
        self.init_ui()
        self.adjustSize()
        self.logger.info(f"[性能] ConfigDialog.__init__ 总耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def init_ui(self):
        """初始化UI"""
        _t0 = time.perf_counter()
        layout = QVBoxLayout(self)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 标签页1: 行为配置
        threshold_tab = QWidget()
        threshold_layout = QVBoxLayout(threshold_tab)
        threshold_layout.setContentsMargins(5, 5, 5, 5)

        threshold_scroll = QScrollArea()
        threshold_scroll.setWidgetResizable(True)
        threshold_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        threshold_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        threshold_content = QWidget()
        threshold_main_layout = QHBoxLayout(threshold_content)
        threshold_main_layout.setContentsMargins(10, 10, 10, 10)
        threshold_main_layout.setSpacing(20)

        # 左列
        threshold_left_widget = QWidget()
        threshold_left_form = QFormLayout(threshold_left_widget)

        # 右列
        threshold_right_widget = QWidget()
        threshold_right_form = QFormLayout(threshold_right_widget)

        threshold_main_layout.addWidget(threshold_left_widget, 1)
        threshold_main_layout.addWidget(threshold_right_widget, 1)

        self.threshold_widgets = {}

        if self.config_manager:
            thresholds = self.config_manager.get_section("BasicAnalysisThresholds")

            if not thresholds:
                self.config_manager.create_default_config()
                thresholds = self.config_manager.get_section("BasicAnalysisThresholds")

            threshold_items = list(thresholds.items())
            half_index = (len(threshold_items) + 1) // 2

            # 左列：前半部分
            for _i, (key, default_val) in enumerate(threshold_items[:half_index]):
                if key:
                    label = self.THRESHOLD_LABELS.get(key, self._format_key(key))
                    widget = QDoubleSpinBox()
                    widget.setRange(-9999.9999, 9999.9999)
                    widget.setDecimals(4)
                    try:
                        widget.setValue(float(default_val))
                    except (ValueError, TypeError):
                        widget.setValue(0.0)
                    widget.setSingleStep(0.01)
                    threshold_left_form.addRow(label, widget)
                    self.threshold_widgets[key] = widget

            # 右列：后半部分
            for _i, (key, default_val) in enumerate(threshold_items[half_index:]):
                if key:
                    label = self.THRESHOLD_LABELS.get(key, self._format_key(key))
                    widget = QDoubleSpinBox()
                    widget.setRange(-9999.9999, 9999.9999)
                    widget.setDecimals(4)
                    try:
                        widget.setValue(float(default_val))
                    except (ValueError, TypeError):
                        widget.setValue(0.0)
                    widget.setSingleStep(0.01)
                    threshold_right_form.addRow(label, widget)
                    self.threshold_widgets[key] = widget

        threshold_scroll.setWidget(threshold_content)
        threshold_layout.addWidget(threshold_scroll)
        self.tab_widget.addTab(threshold_tab, "行为配置")

        # 标签页2: 分析窗口配置
        window_tab = QWidget()
        window_layout = QVBoxLayout(window_tab)
        window_layout.setContentsMargins(5, 5, 5, 5)

        window_scroll = QScrollArea()
        window_scroll.setWidgetResizable(True)
        window_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        window_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        window_content = QWidget()
        window_main_layout = QHBoxLayout(window_content)
        window_main_layout.setContentsMargins(10, 10, 10, 10)
        window_main_layout.setSpacing(20)

        # 左列
        window_left_widget = QWidget()
        window_left_form = QFormLayout(window_left_widget)

        # 右列
        window_right_widget = QWidget()
        window_right_form = QFormLayout(window_right_widget)

        window_main_layout.addWidget(window_left_widget, 1)
        window_main_layout.addWidget(window_right_widget, 1)

        self.window_widgets = {}

        if self.config_manager:
            windows = self.config_manager.get_section("BasicAnalysisWindowSizes")

            if not windows:
                self.config_manager.create_default_config()
                windows = self.config_manager.get_section("BasicAnalysisWindowSizes")

            window_items = list(windows.items())
            half_index = (len(window_items) + 1) // 2

            # 左列：前半部分
            for _i, (key, default_val) in enumerate(window_items[:half_index]):
                if key:
                    label = self.WINDOW_LABELS.get(key, self._format_key(key))
                    widget = QSpinBox()
                    widget.setRange(1, 9999)
                    try:
                        widget.setValue(int(default_val))
                    except (ValueError, TypeError):
                        widget.setValue(10)
                    window_left_form.addRow(label, widget)
                    self.window_widgets[key] = widget

            # 右列：后半部分
            for _i, (key, default_val) in enumerate(window_items[half_index:]):
                if key:
                    label = self.WINDOW_LABELS.get(key, self._format_key(key))
                    widget = QSpinBox()
                    widget.setRange(1, 9999)
                    try:
                        widget.setValue(int(default_val))
                    except (ValueError, TypeError):
                        widget.setValue(10)
                    window_right_form.addRow(label, widget)
                    self.window_widgets[key] = widget

        window_scroll.setWidget(window_content)
        window_layout.addWidget(window_scroll)
        self.tab_widget.addTab(window_tab, "分析窗口配置")

        layout.addWidget(self.tab_widget, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()

        self.import_btn = QPushButton("导入配置")
        self.import_btn.clicked.connect(self._import_config)
        btn_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("导出配置")
        self.export_btn.clicked.connect(self._export_config)
        btn_layout.addWidget(self.export_btn)

        self.reset_btn = QPushButton("重置默认")
        self.reset_btn.clicked.connect(self._reset_config)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()

        self.apply_btn = QPushButton("应用")
        self.apply_btn.setToolTip("将配置应用到当前分析（不保存到文件，下次启动恢复）")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.apply_btn.setStyleSheet("background-color: #2196F3; color: white;")
        btn_layout.addWidget(self.apply_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.setToolTip("将配置持久化保存到config.ini（下次启动生效）")
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self._on_ok_clicked)
        self.ok_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        btn_layout.addWidget(self.ok_btn)

        layout.addLayout(btn_layout)
        self.logger.info(f"[性能] ConfigDialog.init_ui 耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _format_key(self, key):
        """格式化配置项名称，更友好显示"""
        return key.replace('_', ' ').title()

    def _on_apply_clicked(self):
        """点击应用按钮 - 仅设置到内存，不保存文件"""
        _t0 = time.perf_counter()
        config = self.get_config()
        self._apply_config(config, persist=False)
        self.config_applied.emit()
        self.logger.info(f"[性能] _on_apply_clicked 耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _on_save_clicked(self):
        """点击保存配置按钮 - 持久化到config.ini"""
        _t0 = time.perf_counter()
        config = self.get_config()
        self._apply_config(config, persist=True)
        self.config_applied.emit()
        QMessageBox.information(self, "成功", "配置已保存到config.ini！")
        self.logger.info(f"[性能] _on_save_clicked 耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _on_ok_clicked(self):
        """点击确定按钮 - 持久化并关闭"""
        _t0 = time.perf_counter()
        config = self.get_config()
        self._apply_config(config, persist=True)
        self.accept()
        self.logger.info(f"[性能] _on_ok_clicked 耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _apply_config(self, config, persist=False):
        """应用配置到配置管理器"""
        if not self.config_manager:
            return

        self.config_manager.set_values_batch("BasicAnalysisThresholds",
            {key: str(value) for key, value in config['thresholds'].items()})

        self.config_manager.set_values_batch("BasicAnalysisWindowSizes",
            {key: str(value) for key, value in config['windows'].items()})

        if persist:
            self.config_manager.save_config()

    def get_config(self):
        """获取配置"""
        return {
            'thresholds': {key: widget.value() for key, widget in self.threshold_widgets.items()},
            'windows': {key: widget.value() for key, widget in self.window_widgets.items()}
        }

    def _import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if 'thresholds' in config:
                    for key, value in config['thresholds'].items():
                        if key in self.threshold_widgets:
                            self.threshold_widgets[key].setValue(float(value))

                if 'windows' in config:
                    for key, value in config['windows'].items():
                        if key in self.window_widgets:
                            self.window_widgets[key].setValue(int(value))

                QMessageBox.information(self, "成功", "配置导入成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入配置失败：{e}")

    def _export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                config = self.get_config()
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "配置导出成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出配置失败：{e}")

    def _reset_config(self):
        """重置默认配置"""
        if not self.config_manager:
            QMessageBox.warning(self, "警告", "配置管理器未初始化")
            return

        reply = QMessageBox.question(
            self, "确认", "确定要重置为默认配置吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config_manager.create_default_config()

            # 重新加载配置到对话框
            thresholds = self.config_manager.get_section("BasicAnalysisThresholds")
            for key, val in thresholds.items():
                if key in self.threshold_widgets:
                    self.threshold_widgets[key].setValue(float(val))

            windows = self.config_manager.get_section("BasicAnalysisWindowSizes")
            for key, val in windows.items():
                if key in self.window_widgets:
                    self.window_widgets[key].setValue(int(val))

            QMessageBox.information(self, "成功", "配置已重置！")


class BasicAnalysisTab(QWidget):
    """基础分析标签页"""

    event_clicked = Signal(int, float, float)  # event_id, start_ts, end_ts

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.basic_results = []
        self.max_cache_size = 20
        self._data_bridge = None
        self._total_behavior_count = 0
        self._last_table_refresh = 0
        self._table_dirty = False
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_table_if_dirty)
        self._flush_timer.start(100)
        
        # 事件数据映射器
        from core.core.data_processing.event_data_mapper import get_event_mapper
        self._event_mapper = get_event_mapper()
        
        self.init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge
        # 连接新的信号
        if data_bridge:
            data_bridge.sensor_data_received.connect(self.update_sensor_data)
            data_bridge.realtime_monitor_data.connect(self._on_realtime_data)
            data_bridge.bridge_status_changed.connect(self._on_bridge_status_changed)
            # 初始化状态与DataBridge一致
            if data_bridge.is_running:
                self._on_bridge_status_changed("running")
            else:
                self._on_bridge_status_changed("stopped")
    
    def _on_bridge_status_changed(self, status):
        if status == "running":
            self.basic_status_label.setText("基础分析：运行中")
            self.basic_indicator.setStyleSheet("QLabel { color: #27ae60; font-size: 14px; }")
        else:
            self.basic_status_label.setText("基础分析：已停止")
            self.basic_indicator.setStyleSheet("QLabel { color: #95a5a6; font-size: 14px; }")
    
    def _on_realtime_data(self, data):
        """处理实时数据（五层管道输出）"""
        if not self.isVisible():
            return
        
        # 更新传感器数据
        self.update_sensor_data(data)
        
        # 模拟基础分析结果（转换新格式到旧格式）
        state = data.get('state', 'STRAIGHT_CRUISE')
        behavior = self.STATE_MAP.get(state, 'normal')
        event_data = data.get('event', {})
        confidence = event_data.get('confidence', 0.85)
        speed = data.get('speed', 0)
        timestamp = data.get('timestamp', time.time())
        
        # 基础分析结果
        result = {
            'behavior': behavior,
            'confidence': confidence,
            'speed': speed,
            'timestamp': timestamp
        }
        
        # 高级分析结果（从五层管道输出中提取）
        advanced_result = {
            'advanced_behavior': event_data.get('type', behavior),
            'confidence': event_data.get('ml_confidence', confidence),
            'timestamp': timestamp,
            'speed': speed,
        }
        
        self._update_basic_result(result)
        
        # ── 通知父级 RealTimeMonitoringTab 进行事件复核 ──
        if hasattr(self, '_review_callback') and self._review_callback:
            self._review_callback(result, advanced_result, data.get('event_review', None))
    
    def _update_basic_result(self, result):
        """更新基础分析结果（保持向后兼容）"""
        if not hasattr(self, 'basic_results'):
            self.basic_results = []
        
        self.basic_results.append(result)
        
        if len(self.basic_results) > self.max_cache_size:
            self.basic_results.pop(0)
        
        self._update_table(result)

    def init_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("basicAnalysisContent")

        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self._create_status_bar(main_layout)

        body_splitter = QHBoxLayout()
        body_splitter.setSpacing(10)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        body_splitter.addWidget(left_panel, 2)
        body_splitter.addWidget(right_panel, 3)
        main_layout.addLayout(body_splitter)

        scroll_area.setWidget(content)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

    def _build_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._create_sensor_data_card(layout)
        self._create_stats_card(layout)
        layout.addStretch()

        return panel

    def _build_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._create_behavior_table_card(layout)

        return panel

    def _make_card(self, title):
        card = QGroupBox(title)
        card.setFlat(False)
        return card

    def _create_status_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName("basicStatusBar")
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(42)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 16, 0)
        bar_layout.setSpacing(14)

        self.basic_indicator = QLabel("●")
        self.basic_indicator.setFixedWidth(18)
        self.basic_indicator.setAlignment(Qt.AlignCenter)
        self.basic_indicator.setStyleSheet("QLabel { color: #95a5a6; font-size: 14px; }")
        bar_layout.addWidget(self.basic_indicator)

        self.basic_status_label = QLabel("基础分析：已停止")
        self.basic_status_label.setStyleSheet("QLabel { font-size: 13px; }")
        bar_layout.addWidget(self.basic_status_label)

        bar_layout.addStretch()

        sep_style = "QLabel { color: #bdc3c7; font-size: 13px; }"
        info_style = "QLabel { font-size: 13px; }"

        self.behavior_count_label = QLabel("检测行为：0")
        self.behavior_count_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.behavior_count_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet(sep_style)
        bar_layout.addWidget(sep1)

        self.current_behavior_label = QLabel("当前：--")
        self.current_behavior_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.current_behavior_label)

        sep2 = QLabel("|")
        sep2.setStyleSheet(sep_style)
        bar_layout.addWidget(sep2)

        self.basic_score_bar_label = QLabel("评分：--")
        self.basic_score_bar_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.basic_score_bar_label)

        parent_layout.addWidget(bar)

    def _create_sensor_data_card(self, parent_layout):
        self._sensor_card = self._make_card("传感器数据")
        self._sensor_card_layout = QVBoxLayout(self._sensor_card)
        self._sensor_card_layout.setContentsMargins(12, 16, 12, 12)

        self._sensor_data_type = None
        self._sensor_buffer = []
        self._sensor_buffer_max = 3
        self._sensor_table = QTableWidget()
        self._sensor_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._sensor_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._sensor_table.setAlternatingRowColors(True)
        self._sensor_table.verticalHeader().setVisible(False)
        self._sensor_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sensor_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._sensor_card_layout.addWidget(self._sensor_table)
        parent_layout.addWidget(self._sensor_card)

    _IMU_TRIAXIAL_FIELDS = {
        'ax': ('加速度 X', 'm/s²'), 'ay': ('加速度 Y', 'm/s²'), 'az': ('加速度 Z', 'm/s²'),
        'gx': ('角速度 X', 'rad/s'), 'gy': ('角速度 Y', 'rad/s'), 'gz': ('角速度 Z', 'rad/s'),
    }
    _IMU_SCALAR_FIELDS = {
        'speed': ('车速', 'km/h'), 'wheel': ('方向盘角度', '°'),
    }

    @staticmethod
    def _fmt_timestamp(ts_val):
        if ts_val is None:
            return "--:--:--.---"
        try:
            if isinstance(ts_val, (int, float)):
                dt = datetime.fromtimestamp(ts_val)
            else:
                dt = datetime.fromtimestamp(float(ts_val))
            return dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
        except (ValueError, TypeError, OSError):
            return "--:--:--.---"

    def _detect_data_source_type(self, sensor_data):
        has_imu = any(k in sensor_data for k in ['ax', 'ay', 'az', 'gx', 'gy', 'gz'])
        if has_imu:
            return 'imu'
        has_cnap = any(k in sensor_data for k in ['Systolic_BP', 'Diastolic_BP', 'Heart_Rate', 'cnap_type'])
        if has_cnap:
            return 'cnap'
        return 'generic'

    def _rebuild_sensor_table(self, sensor_data):
        ds_type = self._detect_data_source_type(sensor_data)
        if ds_type == self._sensor_data_type:
            return
        self._sensor_data_type = ds_type
        self._sensor_buffer.clear()

        self._sensor_table.clear()
        self._sensor_table.setRowCount(0)

        if ds_type == 'imu':
            self._sensor_card.setTitle("🔬 IMU 传感器数据")
            self._sensor_table.setColumnCount(4)
            self._sensor_table.setHorizontalHeaderLabels(["参数", "T-2", "T-1", "T-0"])
            self._sensor_table.horizontalHeader().setStretchLastSection(True)
            self._sensor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._sensor_table.verticalHeader().setDefaultSectionSize(26)

            rows = []
            for field, (label, unit) in self._IMU_TRIAXIAL_FIELDS.items():
                if field in sensor_data:
                    rows.append((f"{label} ({unit})", field))
            for field, (label, unit) in self._IMU_SCALAR_FIELDS.items():
                if field in sensor_data:
                    rows.append((f"{label} ({unit})", field))

            self._sensor_table.setRowCount(len(rows))
            self._sensor_field_map = []
            for row_idx, (label, field) in enumerate(rows):
                self._sensor_table.setItem(row_idx, 0, QTableWidgetItem(label))
                self._sensor_table.setItem(row_idx, 1, QTableWidgetItem("--"))
                self._sensor_table.setItem(row_idx, 2, QTableWidgetItem("--"))
                self._sensor_table.setItem(row_idx, 3, QTableWidgetItem("--"))
                self._sensor_field_map.append(field)
        else:
            if ds_type == 'cnap':
                self._sensor_card.setTitle("🫀 CNAP 生理数据")
            else:
                self._sensor_card.setTitle("📊 传感器数据")

            self._sensor_table.setColumnCount(2)
            self._sensor_table.setHorizontalHeaderLabels(["参数", "数值"])
            self._sensor_table.horizontalHeader().setStretchLastSection(True)
            self._sensor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._sensor_table.verticalHeader().setDefaultSectionSize(26)

            skip_keys = {'behavior', 'confidence', 'timestamp', 'raw_timestamp', '_behavior'}
            data_keys = [k for k in sensor_data if k not in skip_keys and not k.startswith('_')]

            self._sensor_table.setRowCount(len(data_keys))
            self._sensor_field_map = []
            for row_idx, key in enumerate(data_keys):
                self._sensor_table.setItem(row_idx, 0, QTableWidgetItem(key))
                self._sensor_table.setItem(row_idx, 1, QTableWidgetItem("--"))
                self._sensor_field_map.append(key)

    def _create_stats_card(self, parent_layout):
        card = self._make_card("驾驶行为统计")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 16, 12, 12)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(3)
        self.stats_table.setHorizontalHeaderLabels(["行为类型", "累积次数", "累积时长"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.verticalHeader().setDefaultSectionSize(26)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.verticalHeader().setVisible(False)

        card_layout.addWidget(self.stats_table)
        parent_layout.addWidget(card)

    def _create_behavior_table_card(self, parent_layout):
        card = self._make_card("行为检测结果")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 16, 12, 12)

        self.basic_table = QTableWidget()
        self.basic_table.setColumnCount(5)
        self.basic_table.setHorizontalHeaderLabels([
            "序号", "行为类型", "持续时间", "评分", "时间区间"
        ])
        self.basic_table.horizontalHeader().setStretchLastSection(True)
        self.basic_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.basic_table.verticalHeader().setDefaultSectionSize(28)
        self.basic_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.basic_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.basic_table.setAlternatingRowColors(True)
        self.basic_table.verticalHeader().setVisible(False)
        
        # 添加点击事件
        self.basic_table.itemClicked.connect(self._on_behavior_table_clicked)

        card_layout.addWidget(self.basic_table)
        parent_layout.addWidget(card)

    def _open_config_dialog(self):
        """打开配置对话框"""
        _t0 = time.perf_counter()
        if not self.config_manager:
            QMessageBox.warning(self, "警告", "配置管理器未初始化")
            return
        dialog = ConfigDialog(self.config_manager, self)
        self.logger.info(f"[性能] _open_config_dialog 创建对话框耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")
        dialog.config_applied.connect(self._on_config_applied_live)
        if dialog.exec() == QDialog.Accepted:
            self._on_config_applied_live()
        self.logger.info(f"[性能] _open_config_dialog 总耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _on_config_applied_live(self):
        """配置已应用 - 通知DataBridge重新加载分析器"""
        _t0 = time.perf_counter()
        self.logger.info("配置已更新，通知DataBridge重新加载分析器")
        if self._data_bridge:
            try:
                self._data_bridge.reload_config()
            except Exception as e:
                self.logger.error(f"重新加载配置失败: {e}")
        self.logger.info(f"[性能] _on_config_applied_live 耗时: {(time.perf_counter() - _t0)*1000:.1f}ms")

    def _save_config(self):
        """保存配置到文件"""
        if not self.config_manager:
            QMessageBox.warning(self, "警告", "配置管理器未初始化")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                config = {
                    'thresholds': self.config_manager.get_section("BasicAnalysisThresholds"),
                    'windows': self.config_manager.get_section("BasicAnalysisWindowSizes")
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "配置保存成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存配置失败：{e}")

    def _import_config(self):
        """导入配置"""
        if not self.config_manager:
            QMessageBox.warning(self, "警告", "配置管理器未初始化")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if 'thresholds' in config:
                    self.config_manager.set_values_batch("BasicAnalysisThresholds",
                        {key: str(value) for key, value in config['thresholds'].items()})

                if 'windows' in config:
                    self.config_manager.set_values_batch("BasicAnalysisWindowSizes",
                        {key: str(value) for key, value in config['windows'].items()})

                if self.config_manager.save_config():
                    QMessageBox.information(self, "成功", "配置导入成功！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入配置失败：{e}")

    def _export_config(self):
        """导出配置"""
        self._save_config()

    def update_result(self, result):
        """更新分析结果"""
        self.basic_results.append(result)
        if len(self.basic_results) > self.max_cache_size:
            self.basic_results.pop(0)

        self._update_table(result)

    def update_sensor_data(self, sensor_data):
        if not self.isVisible():
            return
        try:
            self._rebuild_sensor_table(sensor_data)

            ts = sensor_data.get('timestamp')
            self._sensor_buffer.append((ts, sensor_data))
            if len(self._sensor_buffer) > self._sensor_buffer_max:
                self._sensor_buffer.pop(0)

            if self._sensor_data_type == 'imu':
                buf = self._sensor_buffer
                header = self._sensor_table.horizontalHeaderItem(1)
                if header:
                    header.setText(self._fmt_timestamp(buf[0][0]) if len(buf) >= 1 else "T-2")
                header = self._sensor_table.horizontalHeaderItem(2)
                if header:
                    header.setText(self._fmt_timestamp(buf[1][0]) if len(buf) >= 2 else "T-1")
                header = self._sensor_table.horizontalHeaderItem(3)
                if header:
                    header.setText(self._fmt_timestamp(buf[2][0]) if len(buf) >= 3 else "T-0")

                for row_idx, field in enumerate(self._sensor_field_map):
                    for col_offset, (_, rec) in enumerate(buf):
                        # 特殊处理speed字段：使用speed_kmh用于显示
                        if field == 'speed' and 'speed_kmh' in rec:
                            val = rec.get('speed_kmh')
                        else:
                            val = rec.get(field)
                        
                        if val is None:
                            val_str = "N/A"
                        elif isinstance(val, float):
                            val_str = f"{val:.4f}"
                        else:
                            val_str = str(val)
                        self._sensor_table.item(row_idx, 1 + col_offset).setText(val_str)
            else:
                for row_idx, field in enumerate(self._sensor_field_map):
                    # 特殊处理speed字段：使用speed_kmh用于显示
                    if field == 'speed' and 'speed_kmh' in sensor_data:
                        val = sensor_data.get('speed_kmh')
                    else:
                        val = sensor_data.get(field)
                    
                    if val is None:
                        val_str = "N/A"
                    elif isinstance(val, float):
                        val_str = f"{val:.4f}"
                    else:
                        val_str = str(val)
                    self._sensor_table.item(row_idx, 1).setText(val_str)
        except Exception as e:
            self.logger.error("更新传感器数据显示失败: %s", e)

    def _update_table(self, result):
        """更新表格：行为窗口合并，相同行为合并显示时间区间"""
        behavior = result.get("behavior", "normal")
        confidence = result.get("confidence", 0.85)
        timestamp = result.get("timestamp", "")

        if isinstance(timestamp, (int, float)):
            ts_val = timestamp
        else:
            try:
                ts_val = float(timestamp)
            except (ValueError, TypeError):
                ts_val = time.time()

        self._ensure_behavior_window(behavior, confidence, ts_val)

    def _ensure_behavior_window(self, behavior, confidence, ts_val):
        if not hasattr(self, '_behavior_windows'):
            self._behavior_windows = []

        now_str = self._fmt_time(ts_val)
        windows = self._behavior_windows

        if not hasattr(self, '_last_win'):
            self._last_win = None

        if windows and windows[-1]['behavior'] == behavior:
            windows[-1]['end_ts'] = ts_val
            windows[-1]['end_str'] = now_str
            total = len(windows[-1]['points'])
            windows[-1]['confidence'] = (
                windows[-1]['confidence'] * (total - 1) + confidence
            ) / total
            windows[-1]['points'].append(ts_val)
        else:
            self._total_behavior_count += 1
            win = {
                'seq': self._total_behavior_count,
                'behavior': behavior,
                'score': int(confidence * 100),
                'start_str': now_str,
                'end_str': now_str,
                'start_ts': ts_val,
                'end_ts': ts_val,
                'confidence': confidence,
                'points': [ts_val],
            }
            windows.append(win)
            
            # 注册事件到事件数据映射器
            if self._event_mapper:
                risk_level = 'low'
                if win['score'] > 80:
                    risk_level = 'high'
                elif win['score'] > 60:
                    risk_level = 'medium'
                event_id = self._event_mapper.register_event(
                    behavior=behavior,
                    start_ts=ts_val,
                    end_ts=ts_val,
                    severity=confidence,
                    risk_level=risk_level
                )
                win['event_id'] = event_id

        while len(windows) > self.max_cache_size:
            windows.pop(0)

        self._table_dirty = True
        now = time.time()
        if now - self._last_table_refresh >= 0.2:
            self._refresh_table_from_windows()
            self._scroll_to_latest()
            self._last_table_refresh = now
            self._table_dirty = False

    def _fmt_time(self, ts_val):
        dt = datetime.fromtimestamp(ts_val)
        return dt.strftime("%H:%M:%S") + f".{int((ts_val % 1) * 1000):03d}"

    def _refresh_table_from_windows(self):
        windows = getattr(self, '_behavior_windows', [])
        self.basic_table.setUpdatesEnabled(False)
        self.basic_table.setRowCount(0)
        for win in windows:
            row = self.basic_table.rowCount()
            self.basic_table.insertRow(row)
            time_range = win['start_str']
            if win['start_str'] != win['end_str']:
                time_range = f"{win['start_str']} ~ {win['end_str']}"
            duration = win['end_ts'] - win['start_ts']
            dur_str = f"{duration:.2f}s" if duration > 0 else "<0.01s"

            self.basic_table.setItem(row, 0, QTableWidgetItem(str(win.get('seq', ''))))
            self.basic_table.setItem(row, 1, QTableWidgetItem(win['behavior']))
            self.basic_table.setItem(row, 2, QTableWidgetItem(dur_str))
            self.basic_table.setItem(row, 3, QTableWidgetItem(str(win['score'])))
            self.basic_table.setItem(row, 4, QTableWidgetItem(time_range))
        self.basic_table.setUpdatesEnabled(True)

        behavior_stats = {}
        for win in windows:
            bh = win['behavior']
            dur = win['end_ts'] - win['start_ts']
            if bh not in behavior_stats:
                behavior_stats[bh] = {'count': 0, 'duration': 0.0}
            behavior_stats[bh]['count'] += 1
            behavior_stats[bh]['duration'] += dur

        sorted_stats = sorted(behavior_stats.items(), key=lambda x: x[1]['duration'], reverse=True)
        self.stats_table.setUpdatesEnabled(False)
        self.stats_table.setRowCount(len(sorted_stats))
        for row_idx, (bh, stat) in enumerate(sorted_stats):
            self.stats_table.setItem(row_idx, 0, QTableWidgetItem(bh))
            self.stats_table.setItem(row_idx, 1, QTableWidgetItem(str(stat['count'])))
            dur_str = f"{stat['duration']:.1f}s" if stat['duration'] >= 1 else f"{stat['duration']*1000:.0f}ms"
            self.stats_table.setItem(row_idx, 2, QTableWidgetItem(dur_str))
        self.stats_table.setUpdatesEnabled(True)

        if windows:
            last = windows[-1]
            self.behavior_count_label.setText(f"检测行为：{len(windows)}")
            self.current_behavior_label.setText(f"当前：{last['behavior']}")
            self.basic_score_bar_label.setText(f"评分：{last['score']}")
        else:
            self.behavior_count_label.setText("检测行为：0")
            self.current_behavior_label.setText("当前：--")
            self.basic_score_bar_label.setText("评分：--")

    def _scroll_to_latest(self):
        if self.basic_table.rowCount() > 0:
            self.basic_table.scrollToBottom()

    def _flush_table_if_dirty(self):
        if self._table_dirty:
            self._refresh_table_from_windows()
            self._scroll_to_latest()
            self._last_table_refresh = time.time()
    
    def _on_behavior_table_clicked(self, item):
        """处理行为表格的点击事件"""
        row = item.row()
        windows = getattr(self, '_behavior_windows', [])
        if 0 <= row < len(windows):
            win = windows[row]
            event_id = win.get('event_id', 0)
            start_ts = win.get('start_ts', 0)
            end_ts = win.get('end_ts', 0)
            self.event_clicked.emit(event_id, start_ts, end_ts)
    
    def clear_data(self):
        """清空数据"""
        self.basic_results = []
        self._total_behavior_count = 0
        self._behavior_windows = []
        self._last_table_refresh = 0
        self._table_dirty = False
        self._refresh_table_from_windows()
        if self._event_mapper:
            self._event_mapper.clear_all_events()
            self._table_dirty = False


class AdvancedAnalysisTab(QWidget):

    BEHAVIOR_RISK_MAP = {}

    @staticmethod
    def _get_behavior_risk_info(cn_label: str):
        if not _metadata_registry_available:
            return ("", "", "#95a5a6")
        registry = get_global_registry()
        for code, state in registry.driving_states.items():
            if state.display_name_cn == cn_label:
                return (state.risk_level_cn, state.risk_category.name, state.color_hex)
        return ("", "", "#95a5a6")

    @classmethod
    def _rebuild_behavior_risk_map(cls):
        if not _metadata_registry_available:
            return
        registry = get_global_registry()
        cls.BEHAVIOR_RISK_MAP.clear()
        for state in registry.driving_states.values():
            cls.BEHAVIOR_RISK_MAP[state.display_name_cn] = (
                state.risk_level_cn if state.risk_category.value > 2 else '正常'
                if state.risk_category.value > 1 else '注意',
                state.risk_level_cn,
                state.color_hex
            )

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.advanced_results = []
        self.max_cache_size = 100
        self._data_bridge = None
        self._behavior_counter = {}

        AdvancedAnalysisTab._rebuild_behavior_risk_map()

        self.init_ui()

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    def _find_parent_monitoring_tab(self):
        try:
            from core.core.service_locator import ServiceLocator
            return ServiceLocator().get('real_time_monitoring_tab')
        except Exception:
            return None

    def init_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("advancedAnalysisContent")

        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self._create_status_bar(main_layout)

        body_splitter = QHBoxLayout()
        body_splitter.setSpacing(10)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        body_splitter.addWidget(left_panel, 2)
        body_splitter.addWidget(right_panel, 3)
        main_layout.addLayout(body_splitter)

        self._create_results_table(main_layout)

        scroll_area.setWidget(content)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

    def _build_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._create_model_info_card(layout)
        self._create_training_card(layout)
        self._create_config_card(layout)
        self._create_feature_importance_card(layout)
        layout.addStretch()

        return panel

    def _build_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._create_prediction_card(layout)
        self._create_chart_card(layout)

        return panel

    def _create_status_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName("advancedStatusBar")
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(42)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 16, 0)
        bar_layout.setSpacing(14)

        self.model_indicator = QLabel("●")
        self.model_indicator.setFixedWidth(18)
        self.model_indicator.setAlignment(Qt.AlignCenter)
        bar_layout.addWidget(self.model_indicator)

        self.model_status_label = QLabel("模型状态：未加载")
        self.model_status_label.setStyleSheet("QLabel { font-size: 13px; }")
        bar_layout.addWidget(self.model_status_label)

        bar_layout.addStretch()

        sep_style = "QLabel { color: #bdc3c7; font-size: 13px; }"
        info_style = "QLabel { font-size: 13px; }"

        self.algo_info_label = QLabel("算法：--")
        self.algo_info_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.algo_info_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet(sep_style)
        bar_layout.addWidget(sep1)

        self.accuracy_label = QLabel("准确率：--")
        self.accuracy_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.accuracy_label)

        sep2 = QLabel("|")
        sep2.setStyleSheet(sep_style)
        bar_layout.addWidget(sep2)

        self.samples_label = QLabel("样本：0")
        self.samples_label.setStyleSheet(info_style)
        bar_layout.addWidget(self.samples_label)

        parent_layout.addWidget(bar)

    def _make_card(self, title):
        card = QGroupBox(title)
        card.setFlat(False)
        return card

    def _create_model_info_card(self, parent_layout):
        card = self._make_card("模型信息")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 18, 14, 14)
        card_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(16)

        rows = [
            ("算法类型：", "algorithm_type", "--"),
            ("特征维度：", "feature_dim", "--"),
            ("行为类别：", "num_classes", "--"),
            ("最近训练：", "last_trained", "--"),
        ]
        for row_idx, (label, key, default) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setMinimumHeight(24)
            lbl.setStyleSheet("QLabel { color: #7f8c8d; }")
            grid.addWidget(lbl, row_idx, 0)
            val = QLabel(default)
            val.setMinimumHeight(24)
            val.setStyleSheet("QLabel { font-weight: bold; }")
            setattr(self, f"info_{key}", val)
            grid.addWidget(val, row_idx, 1)

        card_layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.load_model_btn = QPushButton("加载模型")
        self.load_model_btn.setMinimumHeight(32)
        self.load_model_btn.clicked.connect(self._load_model)
        btn_row.addWidget(self.load_model_btn)

        self.load_scaler_btn = QPushButton("加载归一化器")
        self.load_scaler_btn.setMinimumHeight(32)
        self.load_scaler_btn.clicked.connect(self._load_scaler)
        btn_row.addWidget(self.load_scaler_btn)

        card_layout.addLayout(btn_row)
        parent_layout.addWidget(card)

    def _create_training_card(self, parent_layout):
        card = self._make_card("模型训练")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 18, 14, 14)
        card_layout.setSpacing(12)

        self.train_model_btn = QPushButton("开始训练")
        self.train_model_btn.setMinimumHeight(38)
        self.train_model_btn.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; }"
        )
        self.train_model_btn.clicked.connect(self._train_model)
        card_layout.addWidget(self.train_model_btn)

        self.training_progress = QProgressBar()
        self.training_progress.setVisible(False)
        self.training_progress.setMaximumHeight(12)
        self.training_progress.setTextVisible(False)
        card_layout.addWidget(self.training_progress)

        self.training_status_label = QLabel("")
        self.training_status_label.setWordWrap(True)
        self.training_status_label.setMinimumHeight(20)
        card_layout.addWidget(self.training_status_label)

        parent_layout.addWidget(card)

    def _create_config_card(self, parent_layout):
        card = self._make_card("训练配置")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 18, 14, 14)
        card_layout.setSpacing(12)

        algo_row = QHBoxLayout()
        algo_row.setSpacing(10)
        algo_label = QLabel("算法：")
        algo_label.setMinimumHeight(26)
        algo_label.setStyleSheet("QLabel { color: #7f8c8d; }")
        algo_row.addWidget(algo_label)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setMinimumHeight(28)
        self.algorithm_combo.addItems([
            "RandomForest", "GradientBoosting", "SVM", "KNN", "LogisticRegression"
        ])
        if self.config_manager:
            default_algo = self.config_manager.get_value(
                "AdvancedAnalysisConfig", "algorithm", "RandomForest"
            )
            self.algorithm_combo.setCurrentText(default_algo)
        algo_row.addWidget(self.algorithm_combo, 1)
        card_layout.addLayout(algo_row)

        self.use_cv_check = QCheckBox("启用交叉验证（5折）")
        self.use_cv_check.setChecked(True)
        self.use_cv_check.setMinimumHeight(26)
        card_layout.addWidget(self.use_cv_check)

        self.compare_algo_check = QCheckBox("对比多种算法")
        self.compare_algo_check.setMinimumHeight(26)
        card_layout.addWidget(self.compare_algo_check)

        parent_layout.addWidget(card)

    def _create_feature_importance_card(self, parent_layout):
        card = self._make_card("特征重要性")
        card.setVisible(False)
        self._feature_importance_card = card

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 18, 14, 14)
        card_layout.setSpacing(8)

        self._feature_bars_widget = QWidget()
        self._feature_bars_layout = QVBoxLayout(self._feature_bars_widget)
        self._feature_bars_layout.setContentsMargins(0, 0, 0, 0)
        self._feature_bars_layout.setSpacing(6)

        self._feature_labels = {}
        feature_names = [
            ("speed", "速度"), ("ax", "X加速度"), ("ay", "Y加速度"),
            ("az", "Z加速度"), ("gx", "X角速度"), ("gy", "Y角速度"),
            ("gz", "Z角速度"), ("accel_magnitude", "加速度幅值"),
            ("turn_rate", "转向率"), ("speed_change_rate", "速度变化率"),
            ("behavior_confidence", "行为置信度"),
        ]
        for key, name in feature_names:
            row = QHBoxLayout()
            row.setSpacing(6)

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(80)
            name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(name_lbl)

            bar = QProgressBar()
            bar.setMaximumHeight(14)
            bar.setTextVisible(False)
            bar.setValue(0)
            row.addWidget(bar, 1)

            val_lbl = QLabel("0%")
            val_lbl.setFixedWidth(36)
            row.addWidget(val_lbl)

            self._feature_labels[key] = (bar, val_lbl)
            self._feature_bars_layout.addLayout(row)

        card_layout.addWidget(self._feature_bars_widget)
        parent_layout.addWidget(card)

    def _create_prediction_card(self, parent_layout):
        card = self._make_card("实时预测结果")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 18, 14, 14)
        card_layout.setSpacing(14)

        indicators_widget = QWidget()
        indicators_layout = QHBoxLayout(indicators_widget)
        indicators_layout.setContentsMargins(0, 0, 0, 0)
        indicators_layout.setSpacing(12)

        indicator_defs = [
            ("risk", "风险等级", "--"),
            ("ml_confidence", "ML 置信度", "--"),
            ("consistency", "基础/高级一致性", "--"),
            ("base_behavior", "基础行为", "--"),
        ]
        for attr, title, default in indicator_defs:
            col = QVBoxLayout()
            col.setSpacing(6)

            title_lbl = QLabel(title)
            title_lbl.setAlignment(Qt.AlignCenter)
            title_lbl.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
            col.addWidget(title_lbl)

            val_lbl = QLabel(default)
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setMinimumHeight(36)
            val_lbl.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; }")
            col.addWidget(val_lbl)
            setattr(self, f"{attr}_label", val_lbl)

            indicators_layout.addLayout(col)

        card_layout.addWidget(indicators_widget)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("QFrame { color: #ecf0f1; }")
        card_layout.addWidget(separator)

        score_row = QHBoxLayout()
        score_row.setSpacing(16)

        score_left = QVBoxLayout()
        score_left.setSpacing(6)
        score_title = QLabel("综合评分")
        score_title.setAlignment(Qt.AlignCenter)
        score_title.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        score_left.addWidget(score_title)

        self.advanced_score_label = QLabel("--")
        self.advanced_score_label.setAlignment(Qt.AlignCenter)
        self.advanced_score_label.setMinimumHeight(52)
        self.advanced_score_label.setStyleSheet(
            "QLabel { font-size: 32px; font-weight: bold; color: #2980b9; }"
        )
        score_left.addWidget(self.advanced_score_label)

        self.advanced_confidence_label = QLabel("")
        self.advanced_confidence_label.setAlignment(Qt.AlignCenter)
        self.advanced_confidence_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        score_left.addWidget(self.advanced_confidence_label)

        score_row.addLayout(score_left)

        pattern_group = QGroupBox("驾驶模式识别")
        pattern_group.setStyleSheet(
            "QGroupBox { font-weight: bold; padding-top: 16px; }"
        )
        pattern_layout = QVBoxLayout(pattern_group)
        pattern_layout.setContentsMargins(12, 8, 12, 12)
        pattern_layout.setSpacing(6)

        self.pattern_text = QTextEdit()
        self.pattern_text.setReadOnly(True)
        self.pattern_text.setMinimumHeight(90)
        self.pattern_text.setMaximumHeight(140)
        self.pattern_text.setStyleSheet(
            "QTextEdit { background-color: #f8f9fa; border: 1px solid #e9ecef; "
            "border-radius: 4px; font-family: Consolas, monospace; font-size: 12px; "
            "padding: 6px; }"
        )
        self.pattern_text.setPlainText("等待分析数据...")
        pattern_layout.addWidget(self.pattern_text)

        score_row.addWidget(pattern_group, 1)

        card_layout.addLayout(score_row)
        parent_layout.addWidget(card)

    def _create_chart_card(self, parent_layout):
        card = self._make_card("置信度趋势与行为分布")
        card.setMinimumHeight(220)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 16, 12, 12)
        card_layout.setSpacing(8)

        if MATPLOTLIB_AVAILABLE:
            self.advanced_canvas = MPLCanvas(self, width=8, height=3.8)
            card_layout.addWidget(self.advanced_canvas, 1)
        else:
            no_chart = QLabel("matplotlib 不可用，图表功能已禁用")
            no_chart.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(no_chart, 1)

        parent_layout.addWidget(card)

    def _create_results_table(self, parent_layout):
        card = self._make_card("高级分析结果")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 16, 12, 12)

        self.advanced_table = QTableWidget()
        self.advanced_table.setColumnCount(6)
        self.advanced_table.setHorizontalHeaderLabels([
            "时间", "基础行为", "高级行为", "置信度", "一致性", "风险等级"
        ])
        self.advanced_table.horizontalHeader().setStretchLastSection(True)
        self.advanced_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.advanced_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.advanced_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.advanced_table.setAlternatingRowColors(True)
        self.advanced_table.verticalHeader().setVisible(False)

        card_layout.addWidget(self.advanced_table)
        parent_layout.addWidget(card)

    def _load_model(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "Pickle 文件 (*.pkl);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'rb') as f:
                model = pickle.load(f)
            self._update_model_info(model)
            self._loaded_model = model
            self.model_status_label.setText("模型状态：已加载")
            self.model_indicator.setStyleSheet("QLabel { color: #27ae60; font-size: 14px; }")
            self._sync_model_info_from_bridge()
            self.logger.info("模型已加载: %s", type(model).__name__)
            QMessageBox.information(self, "加载成功", "模型文件加载成功！")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载模型文件：{e}")

    def _load_scaler(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择归一化器文件", "", "Pickle 文件 (*.pkl);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'rb') as f:
                scaler = pickle.load(f)
            self._loaded_scaler = scaler
            self.logger.info("归一化器已加载")
            QMessageBox.information(self, "加载成功", "归一化器文件加载成功！")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载归一化器文件：{e}")

    def _update_model_info(self, model):
        model_type = type(model).__name__
        self.info_algorithm_type.setText(model_type)
        self.algo_info_label.setText(f"算法：{model_type}")

        if hasattr(model, 'n_features_in_'):
            self.info_feature_dim.setText(str(model.n_features_in_))
        if hasattr(model, 'classes_'):
            self.info_num_classes.setText(str(len(model.classes_)))
        self.info_last_trained.setText(datetime.now().strftime('%m-%d %H:%M'))

    def _sync_model_info_from_bridge(self):
        """从本地缓存的模型更新 UI 信息"""
        if not hasattr(self, '_loaded_model') or self._loaded_model is None:
            return
        try:
            model = self._loaded_model
            model_type = type(model).__name__
            self.info_algorithm_type.setText(model_type)
            self.algo_info_label.setText(f"算法：{model_type}")
            if hasattr(model, 'n_features_in_'):
                self.info_feature_dim.setText(str(model.n_features_in_))
            if hasattr(model, 'classes_'):
                self.info_num_classes.setText(str(len(model.classes_)))
            # 尝试获取特征重要性
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feature_names = getattr(model, 'feature_name_', None)
                if feature_names is not None and len(feature_names) == len(importances):
                    self._update_feature_importance(dict(zip(feature_names, importances)))
        except Exception as e:
            self.logger.error("同步模型信息失败：%s", e)

    def _update_feature_importance(self, importance):
        if not importance:
            self._feature_importance_card.setVisible(False)
            return
        self._feature_importance_card.setVisible(True)
        for key, (bar, val_lbl) in self._feature_labels.items():
            pct = importance.get(key, 0)
            bar.setValue(int(pct * 100))
            val_lbl.setText(f"{pct:.0%}")

    def _train_model(self):
        self.logger.info("_train_model 被调用")
        try:
            reply = QMessageBox.question(
                self, "确认训练",
                "机器学习模型训练需要已标注的驾驶行为数据。\n\n"
                "系统将自动收集已累积的基础分析结果\n"
                "作为训练数据。\n\n"
                "是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

            parent_tab = self._find_parent_monitoring_tab()
            if not parent_tab or not parent_tab.basic_results:
                QMessageBox.warning(
                    self, "数据不足",
                    "暂无基础分析结果。\n请先运行基础分析以收集数据。"
                )
                return

            base_results = list(parent_tab.basic_results)
            labels = [r.get('behavior', 'normal') for r in base_results]

            self.logger.info("已收集 %d 条训练样本", len(base_results))

            if len(base_results) < 10:
                QMessageBox.warning(
                    self, "数据不足",
                    f"当前仅收集到 {len(base_results)} 条基础分析结果。\n"
                    "建议至少收集 50 条样本后再进行训练。\n\n"
                    "请继续运行基础分析以累积更多数据。"
                )
                return

            self.training_progress.setVisible(True)
            self.training_progress.setValue(0)
            self.training_status_label.setText("正在初始化训练...")
            self.train_model_btn.setEnabled(False)

            from core.core.analysis.advanced_analyzer import AdvancedBehaviorAnalyzer
            if hasattr(self, '_training_analyzer') and self._training_analyzer:
                self._disconnect_analyzer_signals(self._training_analyzer)
            self._training_analyzer = AdvancedBehaviorAnalyzer(config_manager=self.config_manager)
            self._training_analyzer.use_cross_validation = self.use_cv_check.isChecked()
            self._training_analyzer.compare_algorithms = self.compare_algo_check.isChecked()
            self._training_analyzer.training_progress.connect(self._on_training_progress)
            self._training_analyzer.training_status.connect(self._on_training_status)
            self._training_analyzer.model_trained.connect(self._on_training_complete)
            self._training_analyzer.train_model(base_results, labels)

        except ImportError as e:
            self.logger.error("导入失败：%s", e)
            QMessageBox.critical(self, "错误", f"无法导入分析器模块：{e}")
        except Exception as e:
            self.logger.error("训练失败：%s", e, exc_info=True)
            QMessageBox.critical(self, "训练失败", f"模型训练过程中发生错误：{e}")
            self.train_model_btn.setEnabled(True)
            self.training_progress.setVisible(False)

    def _on_training_complete(self, accuracy: float, metrics: dict):
        self.training_progress.setValue(100)
        self.training_status_label.setText(f"训练完成！准确率：{accuracy:.2%}")
        self.model_status_label.setText("模型状态：已训练")
        self.model_indicator.setStyleSheet("QLabel { color: #27ae60; font-size: 14px; }")

        self.accuracy_label.setText(f"准确率：{accuracy:.2%}")
        self.info_last_trained.setText(datetime.now().strftime('%m-%d %H:%M'))

        parent_tab = self._find_parent_monitoring_tab()
        sample_count = len(parent_tab.basic_results) if parent_tab else 0
        self.samples_label.setText(f"样本：{sample_count}")

        self.train_model_btn.setEnabled(True)
        self.training_progress.setVisible(False)

        self._sync_model_info_from_bridge()
        self.logger.info("模型训练完成，UI 已更新")

        QMessageBox.information(
            self, "训练完成",
            f"模型训练成功！\n准确率：{accuracy:.2%}\n\n"
            "模型已激活，高级分析功能现已可用。"
        )

    def _disconnect_analyzer_signals(self, analyzer):
        try:
            analyzer.training_progress.disconnect()
        except RuntimeError:
            pass
        try:
            analyzer.training_status.disconnect()
        except RuntimeError:
            pass
        try:
            analyzer.model_trained.disconnect()
        except RuntimeError:
            pass

    def _on_training_progress(self, value):
        self.training_progress.setValue(value)

    def _on_training_status(self, status):
        self.training_status_label.setText(status)

    @staticmethod
    def _format_timestamp(ts):
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        if isinstance(ts, str):
            try:
                return datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
            except (ValueError, TypeError):
                return ts[-8:] if len(ts) >= 8 else ts
        return str(ts)

    def update_result(self, result):
        if not result:
            return
        self.advanced_results.append(result)
        if len(self.advanced_results) > self.max_cache_size:
            self.advanced_results.pop(0)

        self._update_display(result)
        self._update_charts()
        self._update_table(result)

    def _update_display(self, result):
        advanced_behavior = result.get("advanced_behavior", "未知")
        base_behavior = result.get("base_behavior", "未知")
        confidence = result.get("confidence", 0)
        probabilities = result.get("probabilities", {})
        comparison = result.get("comparison", "--")

        if "error" in result:
            self.risk_label.setText("异常")
            self.risk_label.setStyleSheet(
                "QLabel { color: #e74c3c; font-size: 15px; font-weight: bold; }"
            )
            self.ml_confidence_label.setText("--")
            self.consistency_label.setText("--")
            self.base_behavior_label.setText("--")
        else:
            _, risk_level, risk_color = self.BEHAVIOR_RISK_MAP.get(
                advanced_behavior, ("未知", "--", "#95a5a6")
            )
            self.risk_label.setText(risk_level)
            self.risk_label.setStyleSheet(
                f"QLabel {{ color: {risk_color}; font-size: 15px; font-weight: bold; }}"
            )

            self.ml_confidence_label.setText(f"{confidence:.2f}")
            self.ml_confidence_label.setStyleSheet(
                "QLabel { color: #2980b9; font-size: 15px; font-weight: bold; }"
            )

            self.consistency_label.setText(comparison)
            if comparison == "一致":
                self.consistency_label.setStyleSheet(
                    "QLabel { color: #27ae60; font-size: 15px; font-weight: bold; }"
                )
            else:
                self.consistency_label.setStyleSheet(
                    "QLabel { color: #e67e22; font-size: 15px; font-weight: bold; }"
                )

            self.base_behavior_label.setText(base_behavior)
            self.base_behavior_label.setStyleSheet(
                "QLabel { color: #2c3e50; font-size: 15px; font-weight: bold; }"
            )

        pattern_text = f"行为类别：{advanced_behavior}\n"
        pattern_text += f"置信度：{confidence:.2%}\n"
        if probabilities:
            pattern_text += "\n── 概率分布（前3）──\n"
            for k, v in sorted(probabilities.items(), key=lambda x: -x[1])[:3]:
                bar = "█" * int(v * 20)
                pattern_text += f"{k}：{bar} {v:.1%}\n"
        self.pattern_text.setPlainText(pattern_text)

        self.advanced_score_label.setText(str(int(confidence * 100)))
        self.advanced_confidence_label.setText(f"置信度：{confidence:.2%}")

        behavior = advanced_behavior if advanced_behavior != "未知" else base_behavior
        self._behavior_counter[behavior] = self._behavior_counter.get(behavior, 0) + 1

    def _update_charts(self):
        if not MATPLOTLIB_AVAILABLE or not hasattr(self, 'advanced_canvas') or len(self.advanced_results) < 2:
            return
        if self.advanced_canvas.fig is None:
            return

        try:
            self.advanced_canvas.fig.clear()

            ax1 = self.advanced_canvas.fig.add_subplot(121)
            confidences = [r.get('confidence', 0.85) for r in self.advanced_results[-50:]]
            timestamps = list(range(len(confidences)))

            ax1.fill_between(timestamps, 0, confidences, alpha=0.12, color='#2980b9')
            ax1.plot(timestamps, confidences, color='#2980b9', linewidth=1.5,
                     marker='o', markersize=3, markerfacecolor='white',
                     markeredgecolor='#2980b9', markeredgewidth=1)
            ax1.set_ylabel('置信度', fontsize=9)
            ax1.set_xlabel('时间序列', fontsize=9)
            ax1.set_title('ML 置信度趋势', fontsize=10, fontweight='bold')
            ax1.set_ylim(0, 1.05)
            ax1.grid(True, alpha=0.2, linestyle='--')
            ax1.tick_params(labelsize=8)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)

            ax2 = self.advanced_canvas.fig.add_subplot(122)
            if self._behavior_counter:
                sorted_behaviors = sorted(
                    self._behavior_counter.items(), key=lambda x: -x[1]
                )[:8]
                labels_list = [b for b, _ in sorted_behaviors]
                values = [c for _, c in sorted_behaviors]
                colors = []
                for b in labels_list:
                    risk_info = self.BEHAVIOR_RISK_MAP.get(b)
                    if risk_info:
                        colors.append(risk_info[2])
                    else:
                        colors.append(AdvancedAnalysisTab._get_behavior_risk_info(b)[2])
                bars = ax2.barh(range(len(labels_list)), values, color=colors,
                                edgecolor='white', linewidth=0.5)
                ax2.set_yticks(range(len(labels_list)))
                ax2.set_yticklabels(labels_list, fontsize=8)
                ax2.set_xlabel('计数', fontsize=9)
                ax2.set_title('行为分布（累计）', fontsize=10, fontweight='bold')
                ax2.invert_yaxis()
                ax2.tick_params(labelsize=8)
                ax2.spines['top'].set_visible(False)
                ax2.spines['right'].set_visible(False)
                for bar_obj, val in zip(bars, values):
                    ax2.text(bar_obj.get_width() + 0.3, bar_obj.get_y() + bar_obj.get_height() / 2,
                             str(val), va='center', fontsize=8)

            self.advanced_canvas.fig.tight_layout(pad=2.0)
            self.advanced_canvas.draw()

        except Exception as e:
            self.logger.error("图表更新失败：%s", e)

    def _update_table(self, result):
        if "error" in result:
            return

        advanced_behavior = result.get("advanced_behavior", "未知")
        base_behavior = result.get("base_behavior", "未知")
        confidence = result.get("confidence", 0)
        comparison = result.get("comparison", "--")
        timestamp = result.get("timestamp", time.time())

        _, risk_level, _ = self.BEHAVIOR_RISK_MAP.get(
            advanced_behavior, ("未知", "--", "#95a5a6")
        )

        time_str = self._format_timestamp(timestamp)

        row = self.advanced_table.rowCount()
        self.advanced_table.insertRow(row)
        self.advanced_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.advanced_table.setItem(row, 1, QTableWidgetItem(base_behavior))
        self.advanced_table.setItem(row, 2, QTableWidgetItem(advanced_behavior))
        self.advanced_table.setItem(row, 3, QTableWidgetItem(f"{confidence:.2%}"))
        self.advanced_table.setItem(row, 4, QTableWidgetItem(comparison))
        self.advanced_table.setItem(row, 5, QTableWidgetItem(risk_level))

        if self.advanced_table.rowCount() > 100:
            self.advanced_table.removeRow(0)

        self.advanced_table.scrollToBottom()


class ComparisonTab(QWidget):
    """事件复核标签页 — 基于三路投票融合+HMM+物理过滤的置信度复核引擎

    替代原"分析对比"模块，利用弃用的对比分析UI重构为事件置信度复核控制台。
    对接 EventConfidenceRefiner 核心引擎，实现:
      - 三路投票融合 (L3分割 + L4分类 + TriStage检测)
      - HMM维特比时序平滑
      - 物理可行性过滤 (互斥/速度/转移概率/持续时间)
      - 人工确认/驳回交互
    """

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.comparison_results = []
        self.max_cache_size = 100
        self.comparison_active = False
        self._base_behavior_counts = {}
        self._advanced_behavior_counts = {}
        self._event_history = []  # 事件历史 (用于复核)
        self._refiner = None      # 延迟初始化 EventConfidenceRefiner
        self._event_review_panel = None  # 嵌入式 EventReviewPanel 引用
        self._parent_tab = None   # 父级 RealTimeMonitoringTab 引用 (用于批量加载)

        # ── 尝试导入 EventReviewPanel ──
        try:
            from modules.ui.event_review_console import EventReviewPanel
            self._EventReviewPanel = EventReviewPanel
            self.logger.info("EventReviewPanel 模块已就绪，可由 ComparisonTab 使用")
        except ImportError as e:
            self._EventReviewPanel = None
            self.logger.warning(f"EventReviewPanel 导入失败: {e}")

        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ── 滚动区域: 支持垂直滚动，高度自适应 ──
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ── 顶部控制栏 ──
        self._create_control_bar(content_layout)

        # ── 主内容区: 双面板 ──
        splitter = QSplitter(Qt.Horizontal)

        # 左面板: 事件复核引擎
        left_panel = self._build_review_panel()
        splitter.addWidget(left_panel)

        # 右面板: 对比分析 (保留原功能，降级为辅助)
        right_panel = self._build_comparison_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([700, 500])
        content_layout.addWidget(splitter, 1)

        # ── 底部: 事件历史明细表 ──
        self._create_event_history_table(content_layout)

        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

    def _create_control_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName("reviewControlBar")
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(42)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 12, 0)
        bar_layout.setSpacing(10)

        self.comp_indicator = QLabel("●")
        self.comp_indicator.setFixedWidth(18)
        self.comp_indicator.setAlignment(Qt.AlignCenter)
        self.comp_indicator.setStyleSheet("QLabel { color: #95a5a6; font-size: 14px; }")
        bar_layout.addWidget(self.comp_indicator)

        self.comp_status_label = QLabel("事件复核：待启动")
        self.comp_status_label.setStyleSheet("QLabel { font-size: 13px; font-weight: bold; }")
        bar_layout.addWidget(self.comp_status_label)

        bar_layout.addStretch()

        self.comp_consistency_label = QLabel("可信事件：--")
        self.comp_consistency_label.setStyleSheet("QLabel { font-size: 13px; }")
        bar_layout.addWidget(self.comp_consistency_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet("QLabel { color: #bdc3c7; font-size: 13px; }")
        bar_layout.addWidget(sep1)

        self.comp_samples_label = QLabel("待复核：0")
        self.comp_samples_label.setStyleSheet("QLabel { font-size: 13px; }")
        bar_layout.addWidget(self.comp_samples_label)

        sep2 = QLabel("|")
        sep2.setStyleSheet("QLabel { color: #bdc3c7; font-size: 13px; }")
        bar_layout.addWidget(sep2)

        threshold_label = QLabel("阈值:")
        threshold_label.setStyleSheet("QLabel { font-size: 13px; }")
        bar_layout.addWidget(threshold_label)

        self.confidence_threshold_spin = QDoubleSpinBox()
        self.confidence_threshold_spin.setRange(0.5, 0.99)
        self.confidence_threshold_spin.setSingleStep(0.05)
        self.confidence_threshold_spin.setDecimals(2)
        self.confidence_threshold_spin.setValue(0.85)
        self.confidence_threshold_spin.setMinimumWidth(60)
        bar_layout.addWidget(self.confidence_threshold_spin)

        self.start_comparison_btn = QPushButton("开始复核")
        self.start_comparison_btn.setMinimumHeight(28)
        self.start_comparison_btn.clicked.connect(self._toggle_comparison)
        bar_layout.addWidget(self.start_comparison_btn)

        self.stop_comparison_btn = QPushButton("停止复核")
        self.stop_comparison_btn.setMinimumHeight(28)
        self.stop_comparison_btn.clicked.connect(self._toggle_comparison)
        self.stop_comparison_btn.setEnabled(False)
        bar_layout.addWidget(self.stop_comparison_btn)

        parent_layout.addWidget(bar)

    def _build_review_panel(self):
        """构建事件复核面板 — 嵌入完整的 EventReviewPanel

        替代旧的简化版 QFormLayout 面板，使用 EventReviewPanel 的:
          - 事件列表 (QTableView + EventTableModel)
          - 三路投票详情 + 统计摘要
          - Verdict 判定面板 + 筛选控制
        """
        if self._EventReviewPanel is None:
            return self._build_simplified_review_panel()

        self._event_review_panel = self._EventReviewPanel()

        # 隐藏 EventReviewPanel 自带的控制栏 (ComparisonTab 有自己的控制栏)
        main_layout = self._event_review_panel.layout()
        if main_layout and main_layout.count() > 0:
            bar_item = main_layout.itemAt(0)
            if bar_item and bar_item.widget():
                bar_item.widget().hide()

        # ── 连接信号 ──
        self._event_review_panel.event_confirmed.connect(self._on_review_panel_confirmed)
        self._event_review_panel.event_rejected.connect(self._on_review_panel_rejected)
        self._event_review_panel.stats_updated.connect(self._on_review_panel_stats)

        # ── 监听 EventDistributor 事件变更，自动同步到复核面板 ──
        try:
            from core.core.analysis.event_distributor import EventDistributor
            EventDistributor.instance().events_changed.connect(self._on_distributor_events_changed)
        except Exception as e:
            self.logger.warning(f"无法连接 EventDistributor.events_changed: {e}")

        # ── 延迟自动加载已有事件 (等待父级引用就绪) ──
        QTimer.singleShot(500, self._auto_load_events)

        return self._event_review_panel

    def _auto_load_events(self):
        """自动加载已有事件到复核面板 (在 ComparisonTab 创建后延迟触发)"""
        if self._event_review_panel is None:
            return
        if self._event_history:
            return  # 已有数据，不重复加载

        try:
            from core.core.analysis.event_distributor import EventDistributor
            from core.core.analysis.event_confidence_refiner import RefinedEvent

            distributor = EventDistributor.instance()
            events = distributor.get_events()

            if not events:
                self.logger.info("自动加载: EventDistributor 无事件，跳过")
                return

            self.logger.info(f"自动加载: 从 EventDistributor 获取 {len(events)} 个事件")
            count = 0
            for ev in events:
                refined = RefinedEvent(
                    event_type=ev.type,
                    category=ev.category.value if hasattr(ev.category, 'value') else str(ev.category),
                    confidence=ev.confidence,
                    t_start=ev.start_time,
                    t_end=ev.end_time,
                    speed=ev.speed_range[1] if ev.speed_range else 0.0,
                    l3_score=ev.confidence,
                    l4_score=ev.confidence * 0.95,
                    ts_score=ev.confidence,
                    hmm_confidence=ev.confidence,
                    physics_pass=True,
                    verdict="confirmed",
                    requires_review=ev.confidence < 0.85,
                    review_reason="置信度偏低" if ev.confidence < 0.85 else "",
                )
                self._event_history.append(refined)
                count += 1

            self.logger.info(f"自动加载完成: {count} 个事件已导入复核面板")
            if self._event_review_panel is not None:
                self._event_review_panel.set_review_data(self._event_history)
                self.logger.info(f"EventReviewPanel 已刷新: {len(self._event_history)} 个事件")
            # 刷新分析一致性面板
            self._update_consistency_from_events()
            # 延迟运行三路投票复核引擎
            QTimer.singleShot(1000, self._run_refiner_on_loaded_events)
        except Exception as e:
            self.logger.error(f"自动加载事件失败: {e}", exc_info=True)

    def _run_refiner_on_loaded_events(self):
        """对已加载事件运行三路投票复核引擎，更新真实置信度
        
        将缓存事件转换为 L3Event / L4Label / TriStageResult，
        通过 EventConfidenceRefiner 进行三路投票融合 + HMM + 物理过滤。
        """
        if not self._event_history:
            return
        try:
            from core.core.analysis.event_confidence_refiner import (
                EventConfidenceRefiner, L3Event, L4Label, TriStageResult
            )

            refiner = self._get_refiner()
            l3_events = []
            l4_labels = []
            ts_results = []

            for ev in self._event_history:
                # 从 RefinedEvent 重建 L3Event
                l3 = L3Event(
                    idx=0,
                    event_type=ev.event_type,
                    t_start=ev.t_start,
                    t_end=ev.t_end,
                    confidence=ev.confidence,
                    speed=ev.speed,
                )
                l3_events.append(l3)

                # 合成 L4 逐帧标签 (在事件时间窗口内生成 3 帧)
                duration = ev.t_end - ev.t_start
                if duration <= 0:
                    duration = 0.1
                for i in range(3):
                    frame_ts = ev.t_start + duration * (i + 1) / 4
                    l4 = L4Label(
                        frame_idx=int(frame_ts * refiner.fs),
                        timestamp=frame_ts,
                        label=ev.event_type,
                        confidence=ev.confidence * (0.92 + 0.08 * (i / 2)),
                    )
                    l4_labels.append(l4)

                # 合成 TS 检测结果
                ts = TriStageResult(
                    event_type=ev.event_type,
                    category=ev.category,
                    confidence=ev.confidence * 0.95,
                    timestamp=ev.t_start,
                    rule_score=ev.confidence,
                    feature_score=ev.confidence * 0.9,
                    context_score=ev.confidence * 0.95,
                )
                ts_results.append(ts)

            # 运行复核引擎
            refined_events = refiner.refine(l3_events, l4_labels, ts_results)
            self.logger.info(
                f"三路投票复核完成: {len(refined_events)} 个事件, "
                f"confirmed={sum(1 for e in refined_events if e.verdict == 'confirmed')}, "
                f"rejected={sum(1 for e in refined_events if e.verdict == 'rejected')}"
            )

            # 替换事件历史
            self._event_history = refined_events
            if self._event_review_panel is not None:
                self._event_review_panel.set_review_data(self._event_history)
            self._update_consistency_from_events()
            self.logger.info("三路投票复核结果已刷新到 UI")
        except Exception as e:
            self.logger.error(f"三路投票复核运行失败: {e}", exc_info=True)

    def _update_consistency_from_events(self):
        """从已加载事件计算分析一致性，填充右侧面板
        
        在无实时管线数据时，用缓存事件统计替代 '等待分析数据' 占位。
        """
        if not self._event_history:
            return

        events = self._event_history
        total = len(events)
        confirmed = sum(1 for e in events if e.verdict == 'confirmed')
        rejected = sum(1 for e in events if e.verdict == 'rejected')
        uncertain = total - confirmed - rejected

        # ── 一致性进度条 ──
        if total > 0:
            consistency = int(confirmed / total * 100)
        else:
            consistency = 0

        if hasattr(self, 'consistency_progress') and self.consistency_progress:
            self.consistency_progress.setValue(consistency)
        if hasattr(self, 'consistency_label') and self.consistency_label:
            if consistency >= 90:
                label = f"事件一致性: {consistency}% (高度一致)"
                color = "#27ae60"
            elif consistency >= 70:
                label = f"事件一致性: {consistency}% (基本一致)"
                color = "#f39c12"
            else:
                label = f"事件一致性: {consistency}% (存在差异)"
                color = "#e74c3c"
            self.consistency_label.setText(label)
            self.consistency_label.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; }}")

        # ── 差异分析 ──
        if hasattr(self, 'diff_text') and self.diff_text:
            from collections import Counter
            type_counts = Counter(e.event_type for e in events)
            top_types = type_counts.most_common(5)
            lines = [f"事件总数: {total} (确认: {confirmed}, 驳回: {rejected}, 待定: {uncertain})", ""]
            lines.append("主要事件类型:")
            for t, n in top_types:
                pct = n / total * 100
                lines.append(f"  * {t}: {n} 次 ({pct:.1f}%)")

            avg_conf = sum(e.confidence for e in events) / total if total > 0 else 0
            lines.append("")
            lines.append(f"平均置信度: {avg_conf:.3f}")
            lines.append(f"需复核事件: {sum(1 for e in events if e.requires_review)} 个")
            self.diff_text.setPlainText("\n".join(lines))

        # ── 行为分布表 ──
        if hasattr(self, 'distribution_table') and self.distribution_table:
            from collections import Counter
            type_counts = Counter(e.event_type for e in events)
            all_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            self.distribution_table.setRowCount(len(all_types))
            for row_idx, (bh, cnt) in enumerate(all_types):
                self.distribution_table.setItem(row_idx, 0, QTableWidgetItem(bh))
                self.distribution_table.setItem(row_idx, 1, QTableWidgetItem(str(cnt)))
                # 基础/高级使用相同数据 (无实时管线时为缓存事件)
                self.distribution_table.setItem(row_idx, 2, QTableWidgetItem(str(cnt)))
                self.distribution_table.setItem(row_idx, 3, QTableWidgetItem("0"))

    def _on_distributor_events_changed(self, events):
        """EventDistributor 事件变更回调 — 自动同步到复核面板

        当 EventDistributor 中的事件列表发生变更时 (如 sync_from_cache 或
        register_event 后), 自动将新事件增量同步到复核面板。
        """
        if self._event_review_panel is None:
            return
        if not events:
            return

        # 增量同步: 只添加 _event_history 中不存在的事件
        try:
            from core.core.analysis.event_confidence_refiner import RefinedEvent

            existing_keys = {(h.event_type, h.t_start) for h in self._event_history}
            new_count = 0
            for ev in events:
                key = (ev.type, ev.start_time)
                if key in existing_keys:
                    continue
                existing_keys.add(key)

                refined = RefinedEvent(
                    event_type=ev.type,
                    category=ev.category.value if hasattr(ev.category, 'value') else str(ev.category),
                    confidence=ev.confidence,
                    t_start=ev.start_time,
                    t_end=ev.end_time,
                    speed=ev.speed_range[1] if ev.speed_range else 0.0,
                    l3_score=ev.confidence,
                    l4_score=ev.confidence * 0.95,
                    ts_score=ev.confidence,
                    hmm_confidence=ev.confidence,
                    physics_pass=True,
                    verdict="confirmed",
                    requires_review=ev.confidence < 0.85,
                    review_reason="置信度偏低" if ev.confidence < 0.85 else "",
                )
                self._event_history.append(refined)
                new_count += 1

            if new_count > 0:
                self.logger.info(f"EventDistributor 变更: 新增 {new_count} 个事件到复核面板")
                self._event_review_panel.set_review_data(self._event_history)
                self._update_consistency_from_events()
        except Exception as e:
            self.logger.error(f"同步 EventDistributor 事件失败: {e}", exc_info=True)

    def _build_simplified_review_panel(self):
        """回退版简化复核面板 (EventReviewPanel 导入失败时使用)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        grp_fusion = QGroupBox("三路投票融合")
        fusion_layout = QFormLayout(grp_fusion)
        self.lbl_l3_status = QLabel("--")
        self.lbl_l4_status = QLabel("--")
        self.lbl_ts_status = QLabel("--")
        self.lbl_fusion_result = QLabel("--")
        fusion_layout.addRow("L3 分割:", self.lbl_l3_status)
        fusion_layout.addRow("L4 分类:", self.lbl_l4_status)
        fusion_layout.addRow("TS 检测:", self.lbl_ts_status)
        fusion_layout.addRow("融合结果:", self.lbl_fusion_result)
        layout.addWidget(grp_fusion)

        grp_hmm = QGroupBox("HMM维特比平滑")
        hmm_layout = QFormLayout(grp_hmm)
        self.lbl_hmm_before = QLabel("--")
        self.lbl_hmm_after = QLabel("--")
        self.lbl_hmm_corrected = QLabel("--")
        hmm_layout.addRow("平滑前:", self.lbl_hmm_before)
        hmm_layout.addRow("平滑后:", self.lbl_hmm_after)
        hmm_layout.addRow("纠正:", self.lbl_hmm_corrected)
        layout.addWidget(grp_hmm)

        grp_physics = QGroupBox("物理可行性过滤")
        physics_layout = QFormLayout(grp_physics)
        self.lbl_physics_status = QLabel("--")
        self.lbl_physics_violations = QLabel("--")
        physics_layout.addRow("检查结果:", self.lbl_physics_status)
        physics_layout.addRow("违规:", self.lbl_physics_violations)
        layout.addWidget(grp_physics)

        btn_layout = QHBoxLayout()
        self.btn_confirm_event = QPushButton("确认事件")
        self.btn_confirm_event.setMinimumHeight(32)
        self.btn_confirm_event.clicked.connect(self._on_confirm_event)
        btn_layout.addWidget(self.btn_confirm_event)
        self.btn_reject_event = QPushButton("驳回事件")
        self.btn_reject_event.setMinimumHeight(32)
        self.btn_reject_event.clicked.connect(self._on_reject_event)
        btn_layout.addWidget(self.btn_reject_event)
        layout.addLayout(btn_layout)

        layout.addStretch()
        return panel

    def _build_comparison_panel(self):
        """构建对比分析面板 (辅助，保留原功能)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ── 一致性 ──
        grp_consistency = QGroupBox("分析一致性")
        cons_layout = QVBoxLayout(grp_consistency)
        self.consistency_progress = QProgressBar()
        self.consistency_progress.setRange(0, 100)
        self.consistency_progress.setValue(0)
        self.consistency_progress.setFormat("一致性: %p%")
        self.consistency_progress.setMinimumHeight(24)
        cons_layout.addWidget(self.consistency_progress)
        self.consistency_label = QLabel("等待分析数据...")
        self.consistency_label.setAlignment(Qt.AlignCenter)
        self.consistency_label.setStyleSheet(
            "QLabel { color: #7f8c8d; font-weight: bold; }"
        )
        cons_layout.addWidget(self.consistency_label)
        layout.addWidget(grp_consistency)

        # ── 差异分析 ──
        grp_diff = QGroupBox("差异分析")
        diff_layout = QVBoxLayout(grp_diff)
        self.diff_text = QTextEdit()
        self.diff_text.setReadOnly(True)
        self.diff_text.setMinimumHeight(80)
        self.diff_text.setStyleSheet(
            "QTextEdit { background-color: #f8f9fa; border: 1px solid #e9ecef; "
            "border-radius: 4px; font-family: Consolas, monospace; font-size: 12px; "
            "padding: 6px; }"
        )
        self.diff_text.setPlainText("等待分析数据...")
        diff_layout.addWidget(self.diff_text)
        layout.addWidget(grp_diff)

        # ── 行为分布 ──
        grp_dist = QGroupBox("行为分布")
        dist_layout = QVBoxLayout(grp_dist)
        self.distribution_table = QTableWidget()
        self.distribution_table.setColumnCount(4)
        self.distribution_table.setHorizontalHeaderLabels(
            ["行为类型", "基础次数", "高级次数", "差异"]
        )
        self.distribution_table.horizontalHeader().setStretchLastSection(True)
        self.distribution_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.distribution_table.verticalHeader().setDefaultSectionSize(22)
        self.distribution_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.distribution_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.distribution_table.setAlternatingRowColors(True)
        self.distribution_table.verticalHeader().setVisible(False)
        dist_layout.addWidget(self.distribution_table)
        layout.addWidget(grp_dist)

        layout.addStretch()
        return panel

    def _create_event_history_table(self, parent_layout):
        """事件历史明细表"""
        grp = QGroupBox("事件复核历史")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(8, 12, 8, 8)

        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(8)
        self.comparison_table.setHorizontalHeaderLabels([
            "时间", "事件类型", "融合置信度", "HMM置信度",
            "L3分", "L4分", "TS分", "判定"
        ])
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.comparison_table.verticalHeader().setDefaultSectionSize(24)
        self.comparison_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.comparison_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.setMaximumHeight(200)

        grp_layout.addWidget(self.comparison_table)
        parent_layout.addWidget(grp)

    # ════════════════════════════════════════════════════════
    #  核心: 事件置信度复核 (三路投票融合 + HMM + 物理过滤)
    # ════════════════════════════════════════════════════════

    def _get_refiner(self):
        """延迟初始化 EventConfidenceRefiner"""
        if self._refiner is None:
            from core.core.analysis.event_confidence_refiner import (
                EventConfidenceRefiner, L3Event, L4Label, TriStageResult
            )
            self._refiner = EventConfidenceRefiner(
                fs=100.0,
                confidence_threshold=self.confidence_threshold_spin.value()
            )
        return self._refiner

    def _run_review(self, basic_result, advanced_result):
        """执行一轮事件置信度复核"""
        try:
            refiner = self._get_refiner()
            refiner.threshold = self.confidence_threshold_spin.value()

            # ── 构建 L3 事件 (从基础分析) ──
            base_behavior = basic_result.get("behavior", "normal")
            base_conf = basic_result.get("confidence", 0.85)
            base_speed = basic_result.get("speed", 0)
            base_ts = basic_result.get("timestamp", time.time())

            l3_event = L3Event(
                idx=0,
                event_type=base_behavior,
                t_start=base_ts - 1.0,
                t_end=base_ts + 1.0,
                confidence=base_conf,
                speed=base_speed,
            )

            # ── 构建 L4 标签 (从高级分析) ──
            adv_behavior = advanced_result.get("advanced_behavior", "未分析")
            adv_conf = advanced_result.get("confidence", 0.0)
            l4_label = L4Label(
                frame_idx=0,
                timestamp=base_ts,
                label=adv_behavior,
                confidence=adv_conf,
            )

            # ── 构建 TriStage 结果 (从事件分发器) ──
            ts_result = TriStageResult(
                event_type=base_behavior,
                category=self._infer_category(base_behavior),
                confidence=base_conf,
                timestamp=base_ts,
                rule_score=basic_result.get("rule_score", 0.0),
                feature_score=basic_result.get("feature_score", 0.0),
                context_score=basic_result.get("context_score", 0.0),
            )

            # ── 执行复核 ──
            refined = refiner.refine([l3_event], [l4_label], [ts_result])

            if refined:
                ev = refined[0]
                self._update_review_status(ev)
                self._add_to_history(ev)
                self._update_review_stats()

                # 喂入 EventReviewPanel (完整版复核控制台)
                if self._event_review_panel is not None:
                    self._event_review_panel.set_review_data(self._event_history)

                return ev
        except Exception as e:
            self.logger.error(f"事件复核失败: {e}", exc_info=True)
        return None

    def _infer_category(self, event_type: str) -> str:
        """推断事件类别"""
        lon = {'emergency_braking', 'aggressive_deceleration', 'aggressive_acceleration',
               'normal_deceleration', 'normal_acceleration', 'launch', 'constant_speed',
               'stopped'}
        lat = {'weaving', 'lane_change', 'rapid_direction_change', 'tight_turn',
               'wide_turn', 'u_turn', 'straight_driving', 'lane_keeping'}
        if event_type in lon: return 'longitudinal'
        if event_type in lat: return 'lateral'
        return 'state'

    def _update_review_status(self, ev):
        """更新复核状态UI (简化版面板使用，EventReviewPanel 自动更新)"""
        if not hasattr(self, 'lbl_l3_status'):
            return  # 使用 EventReviewPanel，无需手动更新
        self.lbl_l3_status.setText(f"L3={ev.l3_score:.3f}")
        self.lbl_l4_status.setText(f"L4={ev.l4_score:.3f}")
        self.lbl_ts_status.setText(f"TS={ev.ts_score:.3f}")
        self.lbl_fusion_result.setText(
            f"{ev.confidence:.3f} {'[OK]' if ev.confidence >= 0.85 else '[!]'}"
        )
        self.lbl_hmm_before.setText(f"{ev.confidence:.3f}")
        self.lbl_hmm_after.setText(
            f"{ev.hmm_confidence:.3f}" if ev.hmm_confidence > 0 else "--"
        )
        self.lbl_hmm_corrected.setText(
            "已纠正" if ev.hmm_confidence > 0 and ev.hmm_confidence < ev.confidence
            else "无变化"
        )
        self.lbl_physics_status.setText(
            "[OK]通过" if ev.physics_pass else "[X]未通过"
        )
        self.lbl_physics_violations.setText(
            ev.physics_violation[:60] if ev.physics_violation else "无"
        )

    def _add_to_history(self, ev):
        """添加事件到复核历史"""
        self._event_history.append(ev)
        if len(self._event_history) > self.max_cache_size:
            self._event_history.pop(0)

        row = self.comparison_table.rowCount()
        self.comparison_table.insertRow(row)

        ts_str = time.strftime("%H:%M:%S", time.localtime(ev.t_start))
        self.comparison_table.setItem(row, 0, QTableWidgetItem(ts_str))
        self.comparison_table.setItem(row, 1, QTableWidgetItem(ev.event_type))
        self.comparison_table.setItem(row, 2, QTableWidgetItem(f"{ev.confidence:.3f}"))
        self.comparison_table.setItem(row, 3, QTableWidgetItem(
            f"{ev.hmm_confidence:.3f}" if ev.hmm_confidence > 0 else "--"
        ))
        self.comparison_table.setItem(row, 4, QTableWidgetItem(f"{ev.l3_score:.3f}"))
        self.comparison_table.setItem(row, 5, QTableWidgetItem(f"{ev.l4_score:.3f}"))
        self.comparison_table.setItem(row, 6, QTableWidgetItem(f"{ev.ts_score:.3f}"))

        verdict_item = QTableWidgetItem(ev.verdict)
        if ev.verdict == 'confirmed':
            verdict_item.setForeground(QColor("#28a745"))
        elif ev.verdict == 'rejected':
            verdict_item.setForeground(QColor("#dc3545"))
        else:
            verdict_item.setForeground(QColor("#fd7e14"))
        self.comparison_table.setItem(row, 7, verdict_item)

        while self.comparison_table.rowCount() > self.max_cache_size:
            self.comparison_table.removeRow(0)
        if self.comparison_table.rowCount() > 0:
            self.comparison_table.scrollToBottom()

    def _update_review_stats(self):
        """更新复核统计"""
        total = len(self._event_history)
        confirmed = sum(1 for e in self._event_history if e.verdict == 'confirmed')
        needs_review = sum(1 for e in self._event_history if e.requires_review)
        self.comp_consistency_label.setText(f"可信事件：{confirmed}/{total}")
        self.comp_samples_label.setText(f"待复核：{needs_review}")

    def _on_confirm_event(self):
        """人工确认事件 (简化版回退使用)"""
        if self._event_history:
            ev = self._event_history[-1]
            ev.verdict = 'confirmed'
            ev.requires_review = False
            self._update_review_stats()
            self.comp_status_label.setText("事件复核：已确认")
            if self._event_review_panel is not None:
                self._event_review_panel.set_review_data(self._event_history)
            self.logger.info(f"事件已确认: {ev.event_type}")

    def _on_reject_event(self):
        """人工驳回事件 (简化版回退使用)"""
        if self._event_history:
            ev = self._event_history[-1]
            ev.verdict = 'rejected'
            ev.requires_review = True
            self._update_review_stats()
            self.comp_status_label.setText("事件复核：已驳回")
            if self._event_review_panel is not None:
                self._event_review_panel.set_review_data(self._event_history)
            self.logger.info(f"事件已驳回: {ev.event_type}")

    # ════════════════════════════════════════════════════════
    #  EventReviewPanel 信号回调
    # ════════════════════════════════════════════════════════

    def _on_review_panel_confirmed(self, idx: int, event_type: str):
        """EventReviewPanel 确认事件回调"""
        if 0 <= idx < len(self._event_history):
            self._event_history[idx].verdict = 'confirmed'
            self._event_history[idx].requires_review = False
        self._update_review_stats()
        self.comp_status_label.setText(f"事件复核：已确认 #{idx}")
        self.logger.info(f"EventReviewPanel 确认事件: #{idx} {event_type}")

    def _on_review_panel_rejected(self, idx: int, reason: str):
        """EventReviewPanel 驳回事件回调"""
        if 0 <= idx < len(self._event_history):
            self._event_history[idx].verdict = 'rejected'
            self._event_history[idx].requires_review = True
        self._update_review_stats()
        self.comp_status_label.setText(f"事件复核：已驳回 #{idx}")
        self.logger.info(f"EventReviewPanel 驳回事件: #{idx} reason={reason}")

    def _on_review_panel_stats(self, stats: dict):
        """EventReviewPanel 统计更新回调"""
        total = stats.get('total_events', 0)
        confirmed = stats.get('confirmed', 0)
        needs_review = stats.get('needs_review', 0)
        self.comp_consistency_label.setText(f"可信事件：{confirmed}/{total}")
        self.comp_samples_label.setText(f"待复核：{needs_review}")

    # ════════════════════════════════════════════════════════
    #  向后兼容接口
    # ════════════════════════════════════════════════════════

    def _toggle_comparison(self):
        self.comparison_active = not self.comparison_active
        if self.comparison_active:
            self.start_comparison_btn.setEnabled(False)
            self.stop_comparison_btn.setEnabled(True)
            self.comp_indicator.setStyleSheet(
                "QLabel { color: #27ae60; font-size: 14px; }"
            )
            self.comp_status_label.setText("事件复核：运行中")
            self.logger.info("事件复核已启动")
            # ── 批量加载已有事件到复核面板 ──
            self._bulk_review_existing()
        else:
            self.start_comparison_btn.setEnabled(True)
            self.stop_comparison_btn.setEnabled(False)
            self.comp_indicator.setStyleSheet(
                "QLabel { color: #95a5a6; font-size: 14px; }"
            )
            self.comp_status_label.setText("事件复核：已停止")
            self.logger.info("事件复核已停止")

    def set_parent_tab(self, parent_tab):
        """设置父级 RealTimeMonitoringTab 引用，用于批量加载已有事件"""
        self._parent_tab = parent_tab

    def set_data_bridge(self, data_bridge):
        """连接 DataBridge，直接接收实时事件"""
        self._data_bridge = data_bridge
        if data_bridge:
            try:
                data_bridge.behavior_event_ready.connect(self._on_data_bridge_event)
                self.logger.info("ComparisonTab 已直接连接 DataBridge (behavior_event_ready)")
            except Exception as e:
                self.logger.error(f"ComparisonTab 连接 DataBridge 失败: {e}", exc_info=True)

    def _on_data_bridge_event(self, event):
        """直接接收 DataBridge 实时事件"""
        try:
            from core.core.analysis.event_confidence_refiner import RefinedEvent
            t_start = float(getattr(event, 'timestamp', getattr(event, 'start_time', 0)))
            t_end = float(getattr(event, 'end_time', t_start + getattr(event, 'duration', 0.5)))
            ev_type = str(getattr(event, 'event_type', getattr(event, 'type', 'unknown')))
            conf = float(getattr(event, 'confidence', 0.0))
            refined = RefinedEvent(
                event_type=ev_type,
                category=str(getattr(event, 'category', '')),
                confidence=conf,
                t_start=t_start,
                t_end=t_end,
                speed=float(getattr(event, 'speed', 0.0) or 0.0),
                l3_score=float(getattr(event, 'l3_score', conf)),
                l4_score=float(getattr(event, 'l4_score', conf * 0.95)),
                ts_score=float(getattr(event, 'ts_score', conf)),
                hmm_confidence=float(getattr(event, 'hmm_confidence', conf)),
                physics_pass=True,
                verdict="confirmed",
                requires_review=conf < 0.85,
                review_reason="置信度偏低" if conf < 0.85 else "",
            )
            self._event_history.append(refined)
            if len(self._event_history) > self.max_cache_size:
                self._event_history = self._event_history[-self.max_cache_size:]
            if self._event_review_panel:
                self._event_review_panel.set_review_data(self._event_history)
        except Exception as e:
            self.logger.warning(f"ComparisonTab 处理实时事件失败: {e}", exc_info=True)

    def _bulk_review_existing(self):
        """批量加载已有事件到复核面板

        优先级:
          1. EventDistributor (ManeuverEvent → RefinedEvent 直接映射)
          2. basic_tab.basic_results (实时数据回退)
        """
        if self._parent_tab is None:
            self.logger.debug("_parent_tab 未设置，跳过批量复核")
            return

        # ── 方案1: 从 EventDistributor 获取所有已注册事件 ──
        try:
            from core.core.analysis.event_distributor import EventDistributor
            from core.core.analysis.event_confidence_refiner import RefinedEvent

            distributor = EventDistributor.instance()
            events = distributor.get_events()

            if events:
                self.logger.info(f"批量复核: 从 EventDistributor 获取 {len(events)} 个事件")
                count = 0
                for ev in events:
                    # 跳过已存在的(按事件类型+时间窗口去重)
                    already = any(
                        h.event_type == ev.type
                        and abs(h.t_start - ev.start_time) < 0.5
                        for h in self._event_history
                    )
                    if already:
                        continue

                    refined = RefinedEvent(
                        event_type=ev.type,
                        category=ev.category.value if hasattr(ev.category, 'value') else str(ev.category),
                        confidence=ev.confidence,
                        t_start=ev.start_time,
                        t_end=ev.end_time,
                        speed=ev.speed_range[1] if ev.speed_range else 0.0,
                        l3_score=ev.confidence,
                        l4_score=ev.confidence * 0.95,
                        ts_score=ev.confidence,
                        hmm_confidence=ev.confidence,
                        physics_pass=True,
                        verdict="confirmed",
                        requires_review=ev.confidence < 0.85,
                        review_reason="置信度偏低" if ev.confidence < 0.85 else "",
                    )
                    self._event_history.append(refined)
                    count += 1

                self.logger.info(f"批量复核完成: {count} 个事件已加入复核历史")
                if self._event_review_panel is not None and self._event_history:
                    self._event_review_panel.set_review_data(self._event_history)
                    self.logger.info(f"EventReviewPanel 已更新: {len(self._event_history)} 个事件")
                return
        except Exception as e:
            self.logger.warning(f"从 EventDistributor 批量加载失败: {e}")

        # ── 方案2: 回退到 basic_tab.basic_results ──
        basic_tab = getattr(self._parent_tab, 'basic_tab', None)
        basic_results = getattr(basic_tab, 'basic_results', []) if basic_tab else []
        advanced_results = getattr(self._parent_tab, 'advanced_results', [])

        if not basic_results:
            self.logger.info("批量复核: basic_results 为空，等待实时数据...")
            return

        self.logger.info(f"批量复核: 开始处理 {len(basic_results)} 条 basic + {len(advanced_results)} 条 advanced")

        paired_count = 0
        for basic in basic_results:
            best_adv = None
            basic_ts = basic.get('timestamp', 0)
            for adv in advanced_results:
                adv_ts = adv.get('timestamp', 0)
                if best_adv is None or abs(adv_ts - basic_ts) < abs(best_adv.get('timestamp', 0) - basic_ts):
                    best_adv = adv
            if best_adv is None:
                best_adv = {'advanced_behavior': '未分析', 'confidence': 0.0, 'timestamp': basic_ts}

            self._run_review(basic, best_adv)
            paired_count += 1

        self.logger.info(f"批量复核完成: {paired_count} 对结果已处理, 事件历史 {len(self._event_history)} 条")

        if self._event_review_panel is not None and self._event_history:
            self._event_review_panel.set_review_data(self._event_history)
            self.logger.info(f"EventReviewPanel 已更新: {len(self._event_history)} 个事件")

    def update_comparison(self, basic_result, advanced_result):
        """向后兼容接口 — 接收基础/高级分析结果并执行复核"""
        base_behavior = basic_result.get("behavior", "normal")
        advanced_behavior = advanced_result.get("advanced_behavior", "未分析")
        base_conf = basic_result.get("confidence", 0.85)
        advanced_conf = advanced_result.get("confidence", 0)

        conf_diff = abs(base_conf - advanced_conf)
        if conf_diff <= 0.1:
            consistency = 90
            consistency_text = "高度一致"
            consistency_color = "#27ae60"
        elif conf_diff <= 0.2:
            consistency = 75
            consistency_text = "基本一致"
            consistency_color = "#f39c12"
        else:
            consistency = 55
            consistency_text = "存在差异"
            consistency_color = "#e74c3c"

        self.consistency_progress.setValue(consistency)
        self.consistency_label.setText(f"基础与高级分析结果{consistency_text}")
        self.consistency_label.setStyleSheet(
            f"QLabel {{ color: {consistency_color}; font-weight: bold; }}"
        )

        diff_text = "主要差异:\n"
        diff_text += f"* 基础行为: {base_behavior} (置信度: {base_conf:.2f})\n"
        diff_text += f"* 高级行为: {advanced_behavior} (置信度: {advanced_conf:.2f})\n"
        diff_text += f"* 置信度差异: {conf_diff:.2f}\n"
        diff_text += f"* 一致性: {consistency}%"
        self.diff_text.setPlainText(diff_text)

        self._base_behavior_counts[base_behavior] = \
            self._base_behavior_counts.get(base_behavior, 0) + 1
        self._advanced_behavior_counts[advanced_behavior] = \
            self._advanced_behavior_counts.get(advanced_behavior, 0) + 1

        self._refresh_distribution_table()

        comparison = {
            "timestamp": basic_result.get("timestamp", ""),
            "base_behavior": base_behavior,
            "base_confidence": base_conf,
            "advanced_behavior": advanced_behavior,
            "advanced_confidence": advanced_conf,
            "consistency": consistency
        }
        self.comparison_results.append(comparison)
        if len(self.comparison_results) > self.max_cache_size:
            self.comparison_results.pop(0)

        # ── 新增: 执行事件置信度复核 ──
        if self.comparison_active:
            refined = self._run_review(basic_result, advanced_result)

    def feed_event_review(self, review_result: dict):
        """接收管线传来的复核结果并更新UI"""
        if not review_result:
            return
        # 更新三路投票状态
        self.lbl_l3_status.setText(f"L3={review_result.get('l3_score', 0):.3f}")
        self.lbl_l4_status.setText(f"L4={review_result.get('l4_score', 0):.3f}")
        self.lbl_ts_status.setText(f"TS={review_result.get('ts_score', 0):.3f}")
        self.lbl_fusion_result.setText(
            f"{review_result.get('confidence', 0):.3f} "
            f"{'[OK]' if review_result.get('confidence', 0) >= 0.85 else '[!]'}"
        )
        self.lbl_hmm_before.setText(f"{review_result.get('confidence', 0):.3f}")
        hmm_conf = review_result.get('hmm_confidence', 0)
        self.lbl_hmm_after.setText(f"{hmm_conf:.3f}" if hmm_conf > 0 else "--")
        self.lbl_hmm_corrected.setText(
            "已纠正" if hmm_conf > 0 and hmm_conf < review_result.get('confidence', 0)
            else "无变化"
        )
        self.lbl_physics_status.setText(
            "[OK]通过" if review_result.get('physics_pass', False) else "[X]未通过"
        )
        self.lbl_physics_violations.setText("无")

        # 更新复核统计
        verdict = review_result.get('verdict', 'pending')
        if verdict == 'confirmed':
            self.comp_status_label.setText("事件复核：已确认")
        elif verdict == 'rejected':
            self.comp_status_label.setText("事件复核：已驳回")
        else:
            self.comp_status_label.setText("事件复核：待审核")

        self.logger.info(
            f"复核结果已更新: {review_result.get('event_type', 'unknown')} "
            f"置信度={review_result.get('confidence', 0):.3f}"
        )

    def _refresh_distribution_table(self):
        all_behaviors = sorted(set(self._base_behavior_counts.keys())
                               | set(self._advanced_behavior_counts.keys()))
        self.distribution_table.setRowCount(len(all_behaviors))
        for row_idx, bh in enumerate(all_behaviors):
            base_cnt = self._base_behavior_counts.get(bh, 0)
            adv_cnt = self._advanced_behavior_counts.get(bh, 0)
            diff = base_cnt - adv_cnt
            diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "0"

            self.distribution_table.setItem(row_idx, 0, QTableWidgetItem(bh))
            self.distribution_table.setItem(row_idx, 1, QTableWidgetItem(str(base_cnt)))
            self.distribution_table.setItem(row_idx, 2, QTableWidgetItem(str(adv_cnt)))
            diff_item = QTableWidgetItem(diff_str)
            if diff > 0:
                diff_item.setForeground(QColor("#27ae60"))
            elif diff < 0:
                diff_item.setForeground(QColor("#e74c3c"))
            self.distribution_table.setItem(row_idx, 3, diff_item)


class RealTimeMonitoringTab(QWidget, ClearableResource):
    """实时驾驶监控主标签页 — v3.1 Phase 1+2 增强版 (五视图 + ML训练)"""

    # 驾驶状态 → 行为标签映射 (可扩展)
    STATE_MAP = {
        'STOPPED': 'parking',
        'STRAIGHT_CRUISE': 'normal',
        'ACCELERATING': 'accelerating',
        'BRAKING': 'braking',
        'TURNING_LEFT': 'left_turn',
        'TURNING_RIGHT': 'right_turn',
    }

    task_progress_changed = Signal(str, int, str)
    event_clicked = Signal(int, float, float)  # 事件点击信号

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager

        self.basic_results = []
        self.advanced_results = []
        self.max_cache_size = 20

        self._data_bridge = None
        self._frame_count = 0

        self.ml_training_panel = None  # Phase 1+2 训练面板
        self._hybrid_classifier = None

        self.init_ui()

        # 注册到统一清除中心
        ClearableRegistry.instance().register("实时行为监控", self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)

        header_layout.addStretch()

        self.config_btn = QPushButton("打开配置")
        self.config_btn.clicked.connect(self._open_basic_config)
        header_layout.addWidget(self.config_btn)

        self.start_btn = QPushButton("开始分析")
        self.start_btn.clicked.connect(self._start_analysis)
        header_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止分析")
        self.stop_btn.clicked.connect(self._stop_analysis)
        self.stop_btn.setEnabled(False)
        header_layout.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("清空数据")
        self.clear_btn.clicked.connect(self.clear_all)
        header_layout.addWidget(self.clear_btn)

        self.status_label = QLabel("等待开始")
        self.status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header_widget)

        self.main_tabs = QTabWidget()

        self.dashboard_view = None
        self.timeline_view = None
        self.feature_view = None
        self.comparison_tab = None

        self._view_initialized = [False, False, False, False, False, False, False, False]

        placeholder_labels = [
            ("驾驶评估", "正在加载驾驶评估模块..."),
            ("行为时间轴", "正在加载行为时间轴模块..."),
            ("特征分析", "正在加载特征分析模块..."),
            ("事件复核", "正在加载事件复核模块..."),
            ("ML训练", "正在加载ML训练模块..."),
            ("波形滚动", "正在加载波形滚动模块..."),
            ("A/B对比", "正在加载A/B对比模块..."),
            ("事件回放", "正在加载事件回放模块..."),
        ]
        for title, _ in placeholder_labels:
            ph = QWidget()
            lay = QVBoxLayout(ph)
            lbl = QLabel("⏳ 模块将在首次切换到此标签页时加载")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888; font-size: 14px;")
            lay.addWidget(lbl)
            self.main_tabs.addTab(ph, title)

        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

        main_layout.addWidget(self.main_tabs, 1)

        self._update_status_label()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._try_get_data_bridge_from_window)

    def _ensure_view_initialized(self, index):
        if self._view_initialized[index]:
            return
        self._view_initialized[index] = True
        try:
            if index == 0:
                self.dashboard_view = DrivingRiskDashboard(self.config_manager)
                self.main_tabs.insertTab(0, self.dashboard_view, "驾驶评估")
                self.main_tabs.removeTab(1)
                if self._data_bridge:
                    self.dashboard_view.set_data_bridge(self._data_bridge)
            elif index == 1:
                self.timeline_view = BehaviorTimelineView(self.config_manager)
                # 包裹在 QScrollArea 中，支持垂直滚动，框架高度自适应
                timeline_scroll = QScrollArea()
                timeline_scroll.setWidgetResizable(True)
                timeline_scroll.setWidget(self.timeline_view)
                timeline_scroll.setFrameShape(QFrame.NoFrame)
                self.main_tabs.insertTab(1, timeline_scroll, "行为时间轴")
                self.main_tabs.removeTab(2)
                if self._data_bridge:
                    self.timeline_view.set_data_bridge(self._data_bridge)
                # 直接创建并管理BasicAnalysisTab
                self._create_and_manage_basic_tab()
            elif index == 2:
                self.feature_view = FeatureAnalysisView(self.config_manager)
                self.main_tabs.insertTab(2, self.feature_view, "特征分析")
                self.main_tabs.removeTab(3)
                if self._data_bridge:
                    self.feature_view.set_data_bridge(self._data_bridge)
            elif index == 3:
                self.comparison_tab = ComparisonTab(self.config_manager)
                self.comparison_tab.set_parent_tab(self)  # 注入父级引用，用于批量加载
                self.main_tabs.insertTab(3, self.comparison_tab, "事件复核")
                self.main_tabs.removeTab(4)
                if self._data_bridge:
                    self.comparison_tab.set_data_bridge(self._data_bridge)
            elif index == 4:
                # Phase 1+2: ML 训练面板
                from modules.ui.ml_training_panel import MLTrainingPanel
                self.ml_training_panel = MLTrainingPanel(self.config_manager)
                ml_scroll = QScrollArea()
                ml_scroll.setWidgetResizable(True)
                ml_scroll.setWidget(self.ml_training_panel)
                ml_scroll.setFrameShape(QFrame.NoFrame)
                self.main_tabs.insertTab(4, ml_scroll, "ML训练")
                self.main_tabs.removeTab(5)
                if self._data_bridge:
                    self.ml_training_panel.set_data_bridge(self._data_bridge)
                self._init_hybrid_classifier()
            elif index == 5:
                # 波形滚动显示
                from modules.ui.waveform_scroll_widget import WaveformScrollWidget
                self.waveform_view = WaveformScrollWidget(window_seconds=10.0)
                self.main_tabs.insertTab(5, self.waveform_view, "波形滚动")
                self.main_tabs.removeTab(6)
                if self._data_bridge:
                    self.waveform_view.set_data_bridge(self._data_bridge)
                self.logger.info("波形滚动组件已初始化")
            elif index == 6:
                # A/B 模型对比
                from modules.ui.ab_model_comparison import ABModelComparisonWidget
                self.ab_comparison_view = ABModelComparisonWidget()
                ab_scroll = QScrollArea()
                ab_scroll.setWidgetResizable(True)
                ab_scroll.setWidget(self.ab_comparison_view)
                ab_scroll.setFrameShape(QFrame.NoFrame)
                self.main_tabs.insertTab(6, ab_scroll, "A/B对比")
                self.main_tabs.removeTab(7)
                self.logger.info("A/B模型对比组件已初始化")
            elif index == 7:
                # 事件回放
                from modules.ui.event_replay_widget import EventReplayWidget
                self.event_replay_view = EventReplayWidget()
                replay_scroll = QScrollArea()
                replay_scroll.setWidgetResizable(True)
                replay_scroll.setWidget(self.event_replay_view)
                replay_scroll.setFrameShape(QFrame.NoFrame)
                self.main_tabs.insertTab(7, replay_scroll, "事件回放")
                self.main_tabs.removeTab(8)
                if self._data_bridge:
                    self.event_replay_view.replay_position.connect(
                        lambda pos: self.logger.debug(f"回放位置: {pos:.1f}s"))
                self.logger.info("事件回放组件已初始化")
        except Exception as e:
            self.logger.error(f"延迟初始化视图 {index} 失败: {e}")

    def ensure_all_views_initialized(self):
        for i in range(8):
            self._ensure_view_initialized(i)

    def _create_and_manage_basic_tab(self):
        """创建BasicAnalysisTab并连接信号"""
        try:
            from modules.ui.real_time_monitoring_tab import BasicAnalysisTab
            self.basic_tab = BasicAnalysisTab(self.config_manager)
            
            # 连接事件点击信号
            if hasattr(self.basic_tab, 'event_clicked'):
                self.basic_tab.event_clicked.connect(self.event_clicked.emit)
                self.logger.info("✅ BasicAnalysisTab event_clicked信号已连接")
            
            # ── 设置复核回调: 将实时分析结果传递到事件复核控制台 ──
            def _on_review_feed(basic_result, advanced_result, event_review):
                if (self.comparison_tab and self.comparison_tab.comparison_active
                        and hasattr(self.comparison_tab, 'update_comparison')):
                    self.comparison_tab.update_comparison(basic_result, advanced_result)
                    if event_review is not None and hasattr(self.comparison_tab, 'feed_event_review'):
                        self.comparison_tab.feed_event_review(event_review)
            
            self.basic_tab._review_callback = _on_review_feed
            self.logger.info("✅ 事件复核回调已连接到 BasicAnalysisTab")
            
            # 注入DataBridge
            if self._data_bridge:
                self.basic_tab.set_data_bridge(self._data_bridge)
            
            # 在timeline_view中替换basic_tab（如果可能）
            if hasattr(self.timeline_view, 'basic_tab'):
                self.timeline_view.basic_tab = self.basic_tab
            
        except Exception as e:
            self.logger.error(f"创建BasicAnalysisTab失败: {e}")

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge
        if self.dashboard_view:
            self.dashboard_view.set_data_bridge(data_bridge)
        if self.timeline_view:
            self.timeline_view.set_data_bridge(data_bridge)
        if self.feature_view:
            self.feature_view.set_data_bridge(data_bridge)
        # 注入到basic_tab
        if hasattr(self, 'basic_tab') and self.basic_tab:
            self.basic_tab.set_data_bridge(data_bridge)
        # Phase 1+2: 注入到 ML 训练面板
        if self.ml_training_panel:
            self.ml_training_panel.set_data_bridge(data_bridge)
        if hasattr(self, 'waveform_view') and self.waveform_view:
            self.waveform_view.set_data_bridge(data_bridge)
        # 事件复核 (ComparisonTab) 直接连接
        if hasattr(self, 'comparison_tab') and self.comparison_tab:
            self.comparison_tab.set_data_bridge(data_bridge)
        # A/B 模型对比 自动集成
        if hasattr(self, 'ab_comparison_view') and self.ab_comparison_view:
            self.ab_comparison_view.set_data_bridge(data_bridge)
        # 事件回放 自动集成
        if hasattr(self, 'event_replay_view') and self.event_replay_view:
            self.event_replay_view.set_data_bridge(data_bridge)
        if data_bridge:
            data_bridge.sensor_data_received.connect(self._on_sensor_data_received)
            data_bridge.frame_result_ready.connect(self.process_frame_result)
            data_bridge.bridge_status_changed.connect(self._on_bridge_status_changed)
            self.logger.info("DataBridge 已连接到实时监控面板 v3.0 (五层架构)")
            # 初始化状态与DataBridge一致
            if data_bridge.is_running:
                self._on_bridge_status_changed("running")
            else:
                self._on_bridge_status_changed("stopped")
        else:
            self._update_status_label()

    def process_frame_result(self, frame_result):
        """核心方法：接收五层分析管道的 FrameResult，分发到所有视图"""
        if frame_result is None:
            return
        
        # 确保所有视图已初始化（不依赖用户点击）
        self.ensure_all_views_initialized()
        
        self._frame_count += 1

        if self.dashboard_view:
            self.dashboard_view.update_frame_result(frame_result)
        if self.timeline_view:
            self.timeline_view.update_frame_result(frame_result)
        if self.feature_view:
            self.feature_view.update_frame_result(frame_result)

    def _try_get_data_bridge_from_window(self):
        try:
            window = self.window()
            if hasattr(window, 'data_bridge') and window.data_bridge:
                self.set_data_bridge(window.data_bridge)
                self.logger.info("成功从主窗口获取到 DataBridge")
                return True

            parent = self.parent()
            while parent:
                if hasattr(parent, 'data_bridge') and parent.data_bridge:
                    self.set_data_bridge(parent.data_bridge)
                    self.logger.info("成功从 parent 获取到 DataBridge")
                    return True
                parent = parent.parent()

            try:
                from core.core.service_locator import ServiceLocator
                data_bridge = ServiceLocator().get('data_bridge')
                if data_bridge:
                    self.set_data_bridge(data_bridge)
                    self.logger.info("成功从 ServiceLocator 获取到 DataBridge")
                    return True
            except Exception:
                pass

            self.logger.warning("尝试获取 DataBridge 失败")
            return False
        except Exception as e:
            self.logger.error(f"获取 DataBridge 时出现异常: {e}")
            return False

    def _update_status_label(self):
        if self._data_bridge:
            self.status_label.setText("✅ DataBridge 已连接")
            self.status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
        else:
            self.status_label.setText("⚠️ 未连接数据桥接器")
            self.status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")

    def _on_sensor_data_received(self, sensor_data):
        if not self.isVisible():
            return
        now = time.time()
        if now - getattr(self, '_last_sensor_update', 0) < 0.1:
            return
        self._last_sensor_update = now

    def _on_main_tab_changed(self, index):
        self._ensure_view_initialized(index)
        tab_names = ["综合仪表盘", "行为时间轴", "风险评估", "特征分析", "分析对比"]
        tab_name = tab_names[index] if index < len(tab_names) else f"标签{index + 1}"

        progress = 0
        detail = ""

        if index == 0:
            progress = min(self._frame_count, 100)
            detail = f"已处理 {self._frame_count} 帧" if self._frame_count > 0 else "等待数据..."
        elif index == 1:
            count = len(self.timeline_view._events) if hasattr(self.timeline_view, '_events') else 0
            progress = min(count * 2, 100)
            detail = f"已记录 {count} 个事件" if count > 0 else "等待数据..."
        elif index == 2:
            progress = 50
            detail = "等待最新评估..."
        elif index == 3:
            progress = 30
            detail = "等待特征数据..."
        elif index == 4:
            if hasattr(self.comparison_tab, 'consistency_progress'):
                progress = self.comparison_tab.consistency_progress.value()
            count = len(self.comparison_tab.comparison_results) if hasattr(self.comparison_tab, 'comparison_results') else 0
            detail = f"对比结果 {count} 条" if count > 0 else "等待对比数据..."

        progress = min(progress, 100)
        self.task_progress_changed.emit(tab_name, progress, detail)

    def _on_bridge_status_changed(self, status):
        if status == "running":
            self.status_label.setText("🔄 分析中...")
            self.status_label.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        elif status == "stopped":
            self.status_label.setText("⏸️ 已停止")
            self.status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        elif status.startswith("error"):
            self.status_label.setText("❌ 错误")
            self.status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")

    def _on_basic_analysis_completed(self, result):
        self.basic_results.append(result)
        if len(self.basic_results) > self.max_cache_size:
            self.basic_results.pop(0)

        now = time.time()
        if now - getattr(self, '_last_basic_progress_emit', 0) < 0.5:
            return
        self._last_basic_progress_emit = now

        if self.main_tabs.currentIndex() == 0:
            progress = min(len(self.basic_results) * 2, 100)
            self.task_progress_changed.emit("综合仪表盘", progress, f"已检测 {len(self.basic_results)} 条行为")

        if self.comparison_tab and self.comparison_tab.comparison_active and self.advanced_results and len(self.advanced_results) > 0:
            self.comparison_tab.update_comparison(result, self.advanced_results[-1])

    def _on_advanced_analysis_completed(self, result):
        self.advanced_results.append(result)
        if len(self.advanced_results) > self.max_cache_size:
            self.advanced_results.pop(0)

        now = time.time()
        if now - getattr(self, '_last_advanced_progress_emit', 0) < 0.5:
            return
        self._last_advanced_progress_emit = now

        if self.main_tabs.currentIndex() == 1:
            progress = min(len(self.advanced_results) * 2, 100)
            self.task_progress_changed.emit("行为时间轴", progress, f"已分析 {len(self.advanced_results)} 条结果")

        if self.comparison_tab and self.comparison_tab.comparison_active and self.basic_results and len(self.basic_results) > 0:
            self.comparison_tab.update_comparison(self.basic_results[-1], result)

    def _on_combined_result_ready(self, combined_result):
        if not self.comparison_tab or not self.comparison_tab.comparison_active:
            return

        now = time.time()
        if now - getattr(self, '_last_combined_update', 0) < 0.5:
            return
        self._last_combined_update = now

        base_behavior = combined_result.get("base_behavior", "normal")
        base_conf = combined_result.get("base_confidence", 0)
        advanced_behavior = combined_result.get("advanced_behavior", "未分析")
        advanced_conf = combined_result.get("advanced_confidence", 0)
        event_review = combined_result.get("event_review", None)

        self.comparison_tab.update_comparison(
            {"behavior": base_behavior, "confidence": base_conf, "timestamp": combined_result.get("timestamp", "")},
            {"advanced_behavior": advanced_behavior, "confidence": advanced_conf, "timestamp": combined_result.get("timestamp", "")}
        )

        # ── 新增: 传递复核结果到 ComparisonTab ──
        if event_review is not None and hasattr(self.comparison_tab, 'feed_event_review'):
            self.comparison_tab.feed_event_review(event_review)

    def _open_basic_config(self):
        dialog = ConfigDialog(self.config_manager, self)
        dialog.config_applied.connect(self._on_config_applied)
        dialog.exec()

    def _on_config_applied(self):
        self.logger.info("配置已更新")
        if self._data_bridge:
            try:
                self._data_bridge.reload_config()
            except Exception as e:
                self.logger.error(f"重新加载配置失败: {e}")

    def _init_hybrid_classifier(self):
        """Phase 1+2: 初始化 HybridBehaviorClassifier"""
        try:
            from core.core.analysis.layer4_behavior_classification import HybridBehaviorClassifier
            self._hybrid_classifier = HybridBehaviorClassifier(context_window_size=10)
            if self._hybrid_classifier.ml_classifier.is_ready():
                self.logger.info("Phase 1+2 HybridBehaviorClassifier 已就绪")
                if self._hybrid_classifier.ml_classifier.calibrator.is_fitted():
                    self.logger.info("Phase 2 概率校准器已就绪")
            else:
                self.logger.info("ML 模型未训练，使用规则+统计模式")
        except Exception as e:
            self.logger.warning(f"HybridBehaviorClassifier 初始化失败: {e}")

    def classify_ml_event(self, event, features):
        """Phase 1+2: 使用 ML 分类器进行事件分类"""
        if not self._hybrid_classifier:
            return event.type, event.category, event.confidence
        try:
            return self._hybrid_classifier.classify(event, features)
        except Exception as e:
            self.logger.debug(f"ML 分类失败: {e}")
            return event.type, event.category, event.confidence

    @property
    def hybrid_classifier(self):
        return self._hybrid_classifier

    def _start_analysis(self):
        if not self._data_bridge:
            self._try_get_data_bridge_from_window()
        if self._data_bridge:
            self._data_bridge.start_processing()
        else:
            self.status_label.setText("⚠️ 未连接数据桥接器")
            self.status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")

    def _stop_analysis(self):
        if self._data_bridge:
            self._data_bridge.stop_processing()
        else:
            self.status_label.setText("⏸️ 已停止")
            self.status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def clear_data(self):
        """清除数据（向后兼容旧接口）"""
        self.clear_all()

    def clear_all(self):
        """清除所有实时监控数据（实现 ClearableResource 协议）"""
        self.basic_results.clear()
        self.advanced_results.clear()
        self._frame_count = 0
        if self.dashboard_view:
            self.dashboard_view.reset()
        if self.timeline_view:
            self.timeline_view.reset()
        if self.feature_view:
            self.feature_view.reset()
        if self.ml_training_panel:
            self.ml_training_panel.clear_data()
        if hasattr(self, 'waveform_view') and self.waveform_view:
            self.waveform_view.clear()
        if hasattr(self, 'ab_comparison_view') and self.ab_comparison_view:
            self.ab_comparison_view.clear()
        if hasattr(self, 'event_replay_view') and self.event_replay_view:
            self.event_replay_view.clear()
        if self._hybrid_classifier:
            self._hybrid_classifier.reset()
        self.status_label.setText("数据已清空")

    def showEvent(self, event):
        if not self._data_bridge:
            self._try_get_data_bridge_from_window()
        super().showEvent(event)

    def closeEvent(self, event):
        self._stop_analysis()
        super().closeEvent(event)

    def set_replay_mode(self, enabled):
        """设置回放模式"""
        self._replay_mode = enabled
        self.logger.info(f"实时行为监控: 回放模式 {'启用' if enabled else '禁用'}")

    def set_replay_controller(self, replay_controller):
        """设置回放控制器，支持二级分析触发"""
        self._replay_controller = replay_controller
        self.logger.info("回放控制器已连接到实时行为监控")

    def start_replay_analysis(self):
        """二级开始分析触发：从回放控制器获取数据开始分析"""
        if not hasattr(self, '_replay_controller') or not self._replay_controller:
            self.logger.warning("回放控制器未连接，无法开始分析")
            return
        
        # 重置状态
        self._frame_count = 0
        
        # 确保所有视图已初始化
        self.ensure_all_views_initialized()
        
        # 开始回放（如果已暂停）
        if self._replay_controller.state == 'paused':
            self._replay_controller.play()
        
        self.logger.info("实时行为监控: 已触发二级开始分析")

    def set_event_range(self, start_time, end_time):
        """设置事件区间，用于回显"""
        if hasattr(self, '_replay_controller') and self._replay_controller:
            self._replay_controller.set_playback_range(start_time, end_time)
            self.logger.info(f"实时行为监控: 已设置事件区间 [{start_time:.3f}, {end_time:.3f}]")

    def update_sensor_data(self, data):
        """更新传感器数据（用于回放模式）"""
        if data:
            # 将数据传递给需要的视图
            if self.dashboard_view:
                self.dashboard_view.update_sensor_data(data)
            self.logger.debug(f"已更新传感器数据: {data.get('timestamp', 'unknown')}")
