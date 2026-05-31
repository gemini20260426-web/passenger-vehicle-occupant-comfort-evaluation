import sys
import os
import logging
import json
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QPointF
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, 
                               QLabel, QGroupBox, QFormLayout, QScrollArea, QSplitter,
                               QListWidget, QListWidgetItem, QProgressBar, QMessageBox,
                               QComboBox, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
                               QCheckBox, QDateTimeEdit, QTextEdit)
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath

import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget, DateAxisItem

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from config.config_manager import ConfigManager
except ImportError:
    # 创建一个虚拟的ConfigManager类以避免导入错误
    class ConfigManager:
        def get_config(self, name):
            return {}


try:
    from core.storage.db_handler import MySQLHandler
except ImportError:
    # 创建一个虚拟的MySQLHandler类以避免导入错误
    class MySQLHandler:
        def __init__(self):
            pass

# 设置中文字体支持
pg.setConfigOption('foreground', 'd')
pg.setConfigOption('background', 'w')
pg.setConfigOption('antialias', True)


class DashboardDataAdapter:
    """Dashboard数据适配器，统一数据格式"""
    
    # 字段映射：从数据解析器输出到Dashboard期望格式
    FIELD_MAPPING = {
        # 加速度字段映射
        'ax': 'acceleration_x',
        'ay': 'acceleration_y', 
        'az': 'acceleration_z',
        
        # 角速度字段映射
        'gx': 'gyro_x',
        'gy': 'gyro_y',
        'gz': 'gyro_z',
        
        # 其他字段保持原样
        'speed': 'speed',
        'wheel': 'wheel',
        'timestamp': 'timestamp',
        'cnt': 'cnt',
        'loc1': 'loc1',
        'loc2': 'loc2'
    }
    
    # 行为类型映射：从分析器输出到Dashboard期望格式
    # 修复：与base_analyzer.py中的BEHAVIOR_TYPES保持一致
    BEHAVIOR_MAPPING = {
        # 基础行为映射 - 与base_analyzer.py保持一致
        "急刹车": "急刹车",           # 保持中文一致性
        "激进刹车": "激进刹车",       # 保持中文一致性
        "正常刹车": "正常刹车",       # 保持中文一致性
        
        "激进加速": "激进加速",       # 保持中文一致性
        "正常加速": "正常加速",       # 保持中文一致性
        "加速": "加速",               # 保持中文一致性
        
        "左转": "左转",               # 保持中文一致性
        "右转": "右转",               # 保持中文一致性
        "急转弯": "急转弯",           # 保持中文一致性
        "U型转弯": "U型转弯",         # 保持中文一致性
        "大半径转弯": "大半径转弯",   # 保持中文一致性
        
        "蛇形驾驶": "蛇形驾驶",       # 保持中文一致性
        "急速变向": "急速变向",       # 保持中文一致性
        "变道": "变道",               # 保持中文一致性
        
        "减速": "减速",               # 保持中文一致性
        "匀速直线": "匀速直线",       # 保持中文一致性
        "停车": "停车",               # 保持中文一致性
        
        # 特殊行为映射
        "normal": "正常行驶",         # 英文转中文
        "overspeed": "超速",          # 添加超速映射
        "idle": "怠速超时"            # 添加怠速映射
    }
    
    # Dashboard期望的行为类型 - 修复：使用中文保持一致性
    DASHBOARD_BEHAVIORS = [
        "正常行驶",
        "急刹车", 
        "左转",
        "右转", 
        "加速",
        "减速",
        "匀速直线",
        "停车",
        "U型转弯",
        "蛇形驾驶",
        "急速变向",
        "大半径转弯",
        "正常加速",
        "激进加速",
        "正常刹车",
        "激进刹车",
        "变道",
        "超速",
        "怠速超时"
    ]
    
    @classmethod
    def adapt_data(cls, raw_data: dict) -> dict:
        """适配数据格式，统一字段名称和数据结构"""
        if not raw_data:
            return {}
            
        adapted_data = {}
        
        # 1. 字段名称映射
        for old_key, new_key in cls.FIELD_MAPPING.items():
            if old_key in raw_data:
                adapted_data[new_key] = raw_data[old_key]
        
        # 2. 处理behaviors字段
        if 'behaviors' in raw_data:
            # 如果已经有behaviors字段，直接使用
            adapted_data['behaviors'] = raw_data['behaviors']
        elif 'behavior' in raw_data:
            # 如果只有单个behavior字段，转换为behaviors格式
            behavior = raw_data['behavior']
            adapted_data['behaviors'] = cls._convert_single_behavior_to_behaviors(behavior)
        elif 'detected_all' in raw_data:
            # 如果使用detected_all字段，转换为behaviors格式
            detected_behaviors = raw_data['detected_all']
            adapted_data['behaviors'] = cls._convert_detected_behaviors_to_behaviors(detected_behaviors)
        else:
            # 默认正常驾驶
            adapted_data['behaviors'] = {"normal_driving": True}
        
        # 3. 确保时间戳格式正确
        if 'timestamp' in adapted_data:
            timestamp = adapted_data['timestamp']
            if isinstance(timestamp, str):
                try:
                    # 尝试解析ISO格式时间戳
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    adapted_data['timestamp'] = dt
                except:
                    # 如果解析失败，保持原样
                    pass
        
        # 4. 添加缺失的字段（使用默认值）
        required_fields = {
            'acceleration_x': 0.0,
            'acceleration_y': 0.0, 
            'acceleration_z': 0.0,
            'gyro_x': 0.0,
            'gyro_y': 0.0,
            'gyro_z': 0.0,
            'speed': 0.0,
            'latitude': 0.0,
            'longitude': 0.0
        }
        
        for field, default_value in required_fields.items():
            if field not in adapted_data:
                adapted_data[field] = default_value
        
        return adapted_data
    
    @classmethod
    def _convert_single_behavior_to_behaviors(cls, behavior: str) -> dict:
        """将单个行为转换为behaviors字典格式"""
        behaviors = {}
        
        # 映射到Dashboard期望的行为类型
        mapped_behavior = cls.BEHAVIOR_MAPPING.get(behavior, behavior)
        
        # 设置所有行为为False，只有检测到的为True
        for behavior_type in cls.DASHBOARD_BEHAVIORS:
            behaviors[behavior_type] = (behavior_type == mapped_behavior)
        
        return behaviors
    
    @classmethod
    def _convert_detected_behaviors_to_behaviors(cls, detected_behaviors: list) -> dict:
        """将detected_all列表转换为behaviors字典格式"""
        behaviors = {}
        
        # 初始化所有行为为False
        for behavior_type in cls.DASHBOARD_BEHAVIORS:
            behaviors[behavior_type] = False
        
        # 映射检测到的行为
        for detected_behavior in detected_behaviors:
            if detected_behavior == "normal":
                behaviors["normal_driving"] = True
            else:
                mapped_behavior = cls.BEHAVIOR_MAPPING.get(detected_behavior, detected_behavior)
                if mapped_behavior in behaviors:
                    behaviors[mapped_behavior] = True
        
        return behaviors
    
    @classmethod
    def get_behavior_display_name(cls, behavior_key: str) -> str:
        """获取行为的显示名称"""
        display_names = {
            "overspeed": "超速",
            "hard_brake": "急刹车",
            "emergency_braking": "急刹车",
            "hard_acceleration": "急加速", 
            "sharp_turn": "急转弯",
            "idle": "怠速超时",
            "normal_driving": "正常行驶"
        }
        return display_names.get(behavior_key, behavior_key)


class GaugeWidget(QWidget):
    """仪表盘组件，用于显示速度等需要直观展示的数值"""
    def __init__(self, title, unit, min_val, max_val, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.current_value = 0
        self.setMinimumSize(200, 200)
        
        # 设置颜色区间（绿-黄-红）
        self.color_ranges = [
            (max_val * 0.6, QColor(0, 200, 0)),   # 正常
            (max_val * 0.8, QColor(255, 200, 0)), # 警告
            (max_val, QColor(255, 0, 0))          # 危险
        ]
        
    def set_value(self, value):
        """设置当前值"""
        # 限制值在范围内
        self.current_value = max(min(value, self.max_val), self.min_val)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height * 0.6)
        radius = min(width, height) * 0.4
        
        # 绘制标题
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(0, 20, width, 20, Qt.AlignCenter, self.title)
        
        # 绘制外圆弧
        painter.save()
        painter.translate(center)
        
        # 绘制刻度背景
        pen = QPen(QColor(200, 200, 200), 8)
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius * 2, radius * 2, 30 * 16, 120 * 16)
        
        # 绘制颜色区间
        total_range = self.max_val - self.min_val
        start_angle = 30 * 16
        
        for i, (range_val, color) in enumerate(self.color_ranges):
            if i == 0:
                prev_val = self.min_val
            else:
                prev_val = self.color_ranges[i-1][0]
                
            # 计算角度
            prev_angle = 120 * 16 * (prev_val - self.min_val) / total_range
            current_angle = 120 * 16 * (range_val - self.min_val) / total_range
            span_angle = current_angle - prev_angle
            
            # 绘制颜色区间
            pen = QPen(color, 6)
            painter.setPen(pen)
            painter.drawArc(-radius, -radius, radius * 2, radius * 2, 
                           start_angle + prev_angle, span_angle)
        
        # 绘制主要刻度
        pen = QPen(QColor(100, 100, 100), 2)
        painter.setPen(pen)
        
        for i in range(7):  # 6个主要刻度
            angle = 30 + 20 * i  # 从30度到150度，每20度一个刻度
            rad = np.radians(angle)
            x1 = radius * np.cos(rad)
            y1 = -radius * np.sin(rad)
            x2 = (radius * 0.9) * np.cos(rad)
            y2 = -(radius * 0.9) * np.sin(rad)
            painter.drawLine(x1, y1, x2, y2)
            
            # 绘制刻度值
            val = self.min_val + (self.max_val - self.min_val) * i / 5
            text_x = (radius * 0.8) * np.cos(rad)
            text_y = -(radius * 0.8) * np.sin(rad)
            painter.drawText(text_x - 15, text_y + 5, 30, 20, Qt.AlignCenter, f"{int(val)}")
        
        # 绘制指针
        value_ratio = (self.current_value - self.min_val) / (self.max_val - self.min_val)
        pointer_angle = 30 + 120 * value_ratio  # 转换为角度
        rad = np.radians(pointer_angle)
        
        # 选择指针颜色
        pointer_color = QColor(0, 200, 0)
        for range_val, color in self.color_ranges:
            if self.current_value >= range_val:
                pointer_color = color
        
        painter.setPen(QPen(pointer_color, 3))
        painter.setBrush(pointer_color)
        painter.drawLine(0, 0, 
                        (radius * 0.7) * np.cos(rad), 
                        -(radius * 0.7) * np.sin(rad))
        
        # 绘制指针原点
        painter.drawEllipse(-5, -5, 10, 10)
        
        painter.restore()
        
        # 绘制当前值
        value_font = QFont()
        value_font.setPointSize(14)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(pointer_color)
        painter.drawText(0, height * 0.75, width, 30, Qt.AlignCenter, 
                        f"{self.current_value:.1f} {self.unit}")


class VehicleStatusWidget(QWidget):
    """车辆状态信息展示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        # 状态标签
        self.speed_label = QLabel("0.0 km/h")
        self.acceleration_label = QLabel("0.0 m/s²")
        self.gyro_label = QLabel("0.0 rad/s")
        self.location_label = QLabel("未知")
        self.timestamp_label = QLabel("N/A")
        self.behavior_label = QLabel("正常行驶")
        
        # 设置样式
        for label in [self.speed_label, self.acceleration_label, self.gyro_label,
                     self.location_label, self.timestamp_label, self.behavior_label]:
            label.setStyleSheet("font-size: 12pt; padding: 5px;")
        
        # 添加到布局
        layout.addRow("当前速度:", self.speed_label)
        layout.addRow("加速度:", self.acceleration_label)
        layout.addRow("角速度:", self.gyro_label)
        layout.addRow("位置:", self.location_label)
        layout.addRow("时间:", self.timestamp_label)
        layout.addRow("驾驶行为:", self.behavior_label)
        
    def update_status(self, data):
        """更新车辆状态信息"""
        self.speed_label.setText(f"{data.get('speed', 0.0):.1f} km/h")
        
        accel = np.sqrt(
            data.get('acceleration_x', 0.0)**2 + 
            data.get('acceleration_y', 0.0)** 2 + 
            data.get('acceleration_z', 0.0)**2
        )
        self.acceleration_label.setText(f"{accel:.2f} m/s²")
        
        gyro = np.sqrt(
            data.get('gyro_x', 0.0)** 2 + 
            data.get('gyro_y', 0.0)**2 + 
            data.get('gyro_z', 0.0)** 2
        )
        self.gyro_label.setText(f"{gyro:.2f} rad/s")
        
        lat = data.get('latitude', 0.0)
        lon = data.get('longitude', 0.0)
        if lat != 0 or lon != 0:
            self.location_label.setText(f"({lat:.6f}, {lon:.6f})")
        else:
            self.location_label.setText("未知")
            
        timestamp = data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except:
                timestamp = datetime.now()
        self.timestamp_label.setText(timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        
        behaviors = data.get('behaviors', {})
        if behaviors:
            # 使用数据适配器获取显示名称
            detected_behaviors = []
            for behavior_key, detected in behaviors.items():
                if detected:
                    display_name = DashboardDataAdapter.get_behavior_display_name(behavior_key)
                    detected_behaviors.append(display_name)
            
            if detected_behaviors:
                behavior_text = ", ".join(detected_behaviors)
                self.behavior_label.setText(behavior_text)
                self.behavior_label.setStyleSheet("font-size: 12pt; padding: 5px; color: #e74c3c;")
            else:
                self.behavior_label.setText("正常行驶")
                self.behavior_label.setStyleSheet("font-size: 12pt; padding: 5px;")
        else:
            self.behavior_label.setText("正常行驶")
            self.behavior_label.setStyleSheet("font-size: 12pt; padding: 5px;")


class DrivingBehaviorMonitor(QWidget):
    """驾驶行为监控组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        # 修复：使用中文字段保持一致性
        self.behavior_counts = {
            "超速": 0,
            "急刹车": 0,
            "激进刹车": 0,
            "急加速": 0,
            "激进加速": 0,
            "急转弯": 0,
            "左转": 0,
            "右转": 0,
            "怠速超时": 0,
            "正常行驶": 0,
            "加速": 0,
            "减速": 0,
            "匀速直线": 0,
            "停车": 0,
            "U型转弯": 0,
            "蛇形驾驶": 0,
            "急速变向": 0,
            "大半径转弯": 0,
            "正常加速": 0,
            "正常刹车": 0,
            "变道": 0
        }
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("驾驶行为统计")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 行为列表
        self.behavior_layout = QVBoxLayout()
        self.behavior_items = {}
        
        # 行为图标和描述 - 修复：使用中文字段保持一致性
        behavior_info = {
            "超速": ("超速", "#e74c3c", "超过设定速度阈值"),
            "急刹车": ("急刹车", "#f39c12", "刹车加速度超过阈值"),
            "激进刹车": ("激进刹车", "#f39c12", "激进刹车行为"),
            "急加速": ("急加速", "#f39c12", "加速加速度超过阈值"),
            "激进加速": ("激进加速", "#f39c12", "激进加速行为"),
            "急转弯": ("急转弯", "#3498db", "转向角速度超过阈值"),
            "左转": ("左转", "#3498db", "左转弯行为"),
            "右转": ("右转", "#3498db", "右转弯行为"),
            "怠速超时": ("怠速超时", "#9b59b6", "怠速时间超过阈值"),
            "正常行驶": ("正常行驶", "#27ae60", "正常驾驶状态"),
            "加速": ("加速", "#f39c12", "加速行驶"),
            "减速": ("减速", "#f39c12", "减速行驶"),
            "匀速直线": ("匀速直线", "#27ae60", "匀速直线行驶"),
            "停车": ("停车", "#9b59b6", "停车行为"),
            "U型转弯": ("U型转弯", "#3498db", "U型转弯行为"),
            "蛇形驾驶": ("蛇形驾驶", "#e74c3c", "蛇形驾驶行为"),
            "急速变向": ("急速变向", "#e74c3c", "急速变向行为"),
            "大半径转弯": ("大半径转弯", "#3498db", "大半径转弯行为"),
            "正常加速": ("正常加速", "#f39c12", "正常加速行为"),
            "正常刹车": ("正常刹车", "#f39c12", "正常刹车行为"),
            "变道": ("变道", "#3498db", "变道行为")
        }
        
        for behavior, (name, color, desc) in behavior_info.items():
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)
            
            # 行为名称
            name_label = QLabel(name)
            name_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
            # 计数
            count_label = QLabel("0次")
            count_label.setMinimumWidth(50)
            count_label.setAlignment(Qt.AlignRight)
            
            # 描述
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("font-size: 9pt; color: #666;")
            
            item_layout.addWidget(name_label)
            item_layout.addWidget(desc_label, 1)
            item_layout.addWidget(count_label)
            
            self.behavior_layout.addWidget(item_widget)
            self.behavior_items[behavior] = count_label
        
        layout.addLayout(self.behavior_layout)
        
        # 最近行为列表
        recent_group = QGroupBox("最近异常行为")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_list = QListWidget()
        recent_layout.addWidget(self.recent_list)
        layout.addWidget(recent_group)
        
        layout.addStretch(1)
        
    def update_behavior(self, behaviors, data):
        """更新驾驶行为统计"""
        # 更新计数
        for behavior in behaviors:
            if behavior in self.behavior_counts:
                self.behavior_counts[behavior] += 1
                self.behavior_items[behavior].setText(f"{self.behavior_counts[behavior]}次")
        
        # 添加到最近行为列表
        if behaviors:
            timestamp = data.get('timestamp', datetime.now())
            if isinstance(timestamp, datetime):
                time_str = timestamp.strftime("%H:%M:%S")
            else:
                time_str = str(timestamp)
                
            behavior_text = ", ".join(behaviors)
            item_text = f"{time_str} - {behavior_text} (速度: {data.get('speed', 0):.1f} km/h)"
            
            item = QListWidgetItem(item_text)
            item.setForeground(QColor("#e74c3c"))
            self.recent_list.insertItem(0, item)
            
            # 限制列表长度
            if self.recent_list.count() > 10:
                self.recent_list.takeItem(self.recent_list.count() - 1)
    
    def reset_counts(self):
        """重置行为计数"""
        for behavior in self.behavior_counts:
            self.behavior_counts[behavior] = 0
            self.behavior_items[behavior].setText("0次")
        self.recent_list.clear()


class DataPlotWidget(PlotWidget):
    """数据趋势图组件"""
    def __init__(self, title, y_label, color="#3498db", parent=None):
        # 使用日期轴作为X轴
        axis = DateAxisItem(orientation='bottom')
        super().__init__(parent=parent, axisItems={'bottom': axis})
        
        self.title = title
        self.y_label = y_label
        self.color = color
        self.data = []  # 存储数据点 (时间戳, 值)
        self.max_points = 100  # 最大数据点数量
        
        self._init_plot()
        
    def _init_plot(self):
        """初始化图表"""
        self.setBackground('w')
        self.setTitle(self.title)
        self.showGrid(x=True, y=True)
        self.setLabel('left', self.y_label)
        self.setLabel('bottom', '时间')
        
        # 设置坐标轴字体大小
        font = QFont()
        font.setPointSize(9)  # 减小字体大小
        self.getAxis('bottom').setTickFont(font)
        self.getAxis('left').setTickFont(font)
        
        # 创建曲线
        self.curve = self.plot(pen=pg.mkPen(color=self.color, width=2))
        
    def add_data_point(self, timestamp, value):
        """添加数据点"""
        # 确保时间戳是时间戳格式
        if isinstance(timestamp, datetime):
            timestamp = timestamp.timestamp() * 1000  # 转换为毫秒
        
        self.data.append((timestamp, value))
        
        # 限制数据点数量
        if len(self.data) > self.max_points:
            self.data = self.data[-self.max_points:]
        
        # 更新曲线
        x = [p[0] for p in self.data]
        y = [p[1] for p in self.data]
        self.curve.setData(x, y)
        
    def clear_data(self):
        """清除数据"""
        self.data = []
        self.curve.clear()


class DashboardTab(QWidget):
    """仪表盘标签页"""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger("DashboardTab")
        
        self._init_ui()
        
    def _init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 顶部：速度仪表盘和状态信息
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # 速度仪表盘
        self.speed_gauge = GaugeWidget("当前速度", "km/h", 0, 160)
        top_layout.addWidget(self.speed_gauge)
        
        # 车辆状态信息
        self.status_widget = VehicleStatusWidget()
        top_layout.addWidget(self.status_widget, 1)
        
        splitter.addWidget(top_widget)
        
        # 中间：图表区域
        charts_widget = QWidget()
        charts_layout = QGridLayout(charts_widget)
        
        # 加速度图表
        self.accel_plot = DataPlotWidget("加速度变化", "加速度 (m/s²)", "#e74c3c")
        charts_layout.addWidget(self.accel_plot, 0, 0)
        
        # 角速度图表
        self.gyro_plot = DataPlotWidget("角速度变化", "角速度 (rad/s)", "#3498db")
        charts_layout.addWidget(self.gyro_plot, 0, 1)
        
        # 速度趋势图表
        self.speed_plot = DataPlotWidget("速度趋势", "速度 (km/h)", "#2ecc71")
        charts_layout.addWidget(self.speed_plot, 1, 0, 1, 2)
        
        splitter.addWidget(charts_widget)
        
        # 底部：驾驶行为监控
        self.behavior_monitor = DrivingBehaviorMonitor()
        splitter.addWidget(self.behavior_monitor)
        
        # 设置分割器初始大小
        splitter.setSizes([300, 500, 300])
        
        main_layout.addWidget(splitter)
        
    def update_realtime_data(self, data):
        """更新实时数据"""
        # 使用数据适配器统一数据格式
        adapted_data = DashboardDataAdapter.adapt_data(data)
        
        # 更新速度仪表盘
        speed = adapted_data.get('speed', 0.0)
        self.speed_gauge.set_value(speed)
        
        # 更新状态信息
        self.status_widget.update_status(adapted_data)
        
        # 更新图表
        timestamp = adapted_data.get('timestamp', datetime.now())
        
        # 计算合加速度
        accel = np.sqrt(
            adapted_data.get('acceleration_x', 0.0)**2 + 
            adapted_data.get('acceleration_y', 0.0)** 2 + 
            adapted_data.get('acceleration_z', 0.0)**2
        )
        self.accel_plot.add_data_point(timestamp, accel)
        
        # 计算合角速度
        gyro = np.sqrt(
            adapted_data.get('gyro_x', 0.0)** 2 + 
            adapted_data.get('gyro_y', 0.0)**2 + 
            adapted_data.get('gyro_z', 0.0)** 2
        )
        self.gyro_plot.add_data_point(timestamp, gyro)
        
        # 速度趋势
        self.speed_plot.add_data_point(timestamp, speed)
        
        # 更新驾驶行为
        behaviors = adapted_data.get('behaviors', {})
        detected_behaviors = [k for k, v in behaviors.items() if v]
        if detected_behaviors:
            self.behavior_monitor.update_behavior(detected_behaviors, adapted_data)
    
    def clear_data(self):
        """清除所有数据"""
        self.accel_plot.clear_data()
        self.gyro_plot.clear_data()
        self.speed_plot.clear_data()
        self.behavior_monitor.reset_counts()


class HistoricalDataTab(QWidget):
    """历史数据标签页"""
    def __init__(self, config_manager, db_handler, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.db_handler = db_handler
        self.logger = logging.getLogger("HistoricalDataTab")
        
        self._init_ui()
        self._setup_timer()
        
    def _init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 时间范围选择
        time_range_widget = QWidget()
        time_range_layout = QHBoxLayout(time_range_widget)
        
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems([
            "近1小时", "近3小时", "近6小时", 
            "近12小时", "近24小时", "近7天"
        ])
        self.time_range_combo.setCurrentIndex(4)  # 默认近24小时
        
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.clicked.connect(self._load_historical_data)
        
        time_range_layout.addWidget(QLabel("时间范围:"))
        time_range_layout.addWidget(self.time_range_combo)
        time_range_layout.addWidget(self.refresh_btn)
        time_range_layout.addStretch(1)
        
        main_layout.addWidget(time_range_widget)
        
        # 图表区域
        charts_widget = QWidget()
        charts_layout = QVBoxLayout(charts_widget)
        
        # 速度统计图表
        self.hist_speed_plot = DataPlotWidget("历史速度趋势", "速度 (km/h)", "#2ecc71")
        charts_layout.addWidget(self.hist_speed_plot)
        
        # 行为统计图表
        self.behavior_stats_widget = QWidget()
        self.behavior_stats_layout = QHBoxLayout(self.behavior_stats_widget)
        
        # 使用pyqtgraph的柱状图
        self.behavior_plot = pg.PlotWidget(title="驾驶行为统计")
        self.behavior_plot.setBackground('w')
        self.behavior_plot.setLabel('left', '次数')
        self.behavior_plot.setLabel('bottom', '行为类型')
        
        self.behavior_stats_layout.addWidget(self.behavior_plot)
        
        charts_layout.addWidget(self.behavior_stats_widget)
        
        main_layout.addWidget(charts_widget)
        
    def _setup_timer(self):
        """设置定时器定期刷新数据"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._load_historical_data)
        self.timer.start(60000)  # 每60秒刷新一次
        
    def _get_time_range(self):
        """获取时间范围"""
        current_time = datetime.now()
        range_text = self.time_range_combo.currentText()
        
        if "1小时" in range_text:
            return current_time - timedelta(hours=1), current_time
        elif "3小时" in range_text:
            return current_time - timedelta(hours=3), current_time
        elif "6小时" in range_text:
            return current_time - timedelta(hours=6), current_time
        elif "12小时" in range_text:
            return current_time - timedelta(hours=12), current_time
        elif "24小时" in range_text:
            return current_time - timedelta(hours=24), current_time
        elif "7天" in range_text:
            return current_time - timedelta(days=7), current_time
        return current_time - timedelta(hours=24), current_time
        
    def _load_historical_data(self):
        """加载历史数据"""
        self.logger.info(f"db_handler: {self.db_handler}")
        if not self.db_handler:
            self.logger.warning("db_handler为空，无法加载历史数据")
            return
            
        if not self.db_handler.is_connected():
            self.logger.warning("数据库未连接，尝试连接...")
            if not self.db_handler.connect():
                self.logger.error("数据库连接失败，无法加载历史数据")
                return
            
        start_time, end_time = self._get_time_range()
        self.logger.info(f"加载历史数据: {start_time} 至 {end_time}")
        
        try:
            # 加载速度数据
            speed_data = self._get_speed_data(start_time, end_time)
            self.logger.info(f"速度数据: {speed_data}")
            if speed_data:
                self.hist_speed_plot.data = speed_data
                x = [p[0] for p in speed_data]
                y = [p[1] for p in speed_data]
                self.hist_speed_plot.curve.setData(x, y)
            
            # 加载行为统计数据
            behavior_data = self._get_behavior_stats(start_time, end_time)
            self.logger.info(f"行为统计数据: {behavior_data}")
            if behavior_data:
                self._update_behavior_chart(behavior_data)
                
        except Exception as e:
            self.logger.error(f"加载历史数据失败: {str(e)}")
    
    def _get_speed_data(self, start_time, end_time):
        """获取速度数据"""
        try:
            self.logger.info(f"执行查询: SELECT timestamp, speed FROM driving_data WHERE timestamp BETWEEN {start_time} AND {end_time}")
            sql = """
                SELECT timestamp, speed 
                FROM driving_data 
                WHERE timestamp BETWEEN %s AND %s
                ORDER BY timestamp
            """
            results = self.db_handler.execute_query(sql, (start_time, end_time))
            self.logger.info(f"查询结果: {results}")
            
            # 转换为图表所需格式
            data = []
            if results:
                for row in results:
                    # 转换为毫秒时间戳
                    ts = datetime.timestamp(row['timestamp']) * 1000
                    data.append((ts, row['speed']))
            
            return data
        except Exception as e:
            self.logger.error(f"获取速度数据失败: {str(e)}")
            return []
    
    def _get_behavior_stats(self, start_time, end_time):
        """获取行为统计数据"""
        try:
            self.logger.info(f"执行查询: SELECT behaviors FROM behavior_events WHERE timestamp BETWEEN {start_time} AND {end_time}")
            sql = """
                SELECT behaviors 
                FROM behavior_events 
                WHERE timestamp BETWEEN %s AND %s
            """
            results = self.db_handler.execute_query(sql, (start_time, end_time))
            self.logger.info(f"查询结果: {results}")
            
            # 统计行为 - 修复：使用中文字段保持一致性
            behavior_counts = {
                "超速": 0,
                "急刹车": 0,
                "激进刹车": 0,
                "急加速": 0,
                "激进加速": 0,
                "急转弯": 0,
                "左转": 0,
                "右转": 0,
                "怠速超时": 0,
                "正常行驶": 0,
                "加速": 0,
                "减速": 0,
                "匀速直线": 0,
                "停车": 0,
                "U型转弯": 0,
                "蛇形驾驶": 0,
                "急速变向": 0,
                "大半径转弯": 0,
                "正常加速": 0,
                "正常刹车": 0,
                "变道": 0
            }
            
            # 修复：使用新的中文字段映射
            behavior_map = {
                "overspeed": "超速",
                "hard_brake": "急刹车",
                "emergency_braking": "急刹车",
                "hard_acceleration": "急加速",
                "sharp_turn": "急转弯",
                "idle": "怠速超时",
                "normal_driving": "正常行驶",
                "normal": "正常行驶",
                # 添加新的映射
                "急刹车": "急刹车",
                "激进刹车": "激进刹车",
                "正常刹车": "正常刹车",
                "激进加速": "激进加速",
                "正常加速": "正常加速",
                "加速": "加速",
                "左转": "左转",
                "右转": "右转",
                "急转弯": "急转弯",
                "U型转弯": "U型转弯",
                "大半径转弯": "大半径转弯",
                "蛇形驾驶": "蛇形驾驶",
                "急速变向": "急速变向",
                "变道": "变道",
                "减速": "减速",
                "匀速直线": "匀速直线",
                "停车": "停车"
            }
            
            if results:
                for row in results:
                    if row['behaviors']:
                        behaviors = json.loads(row['behaviors'])
                        for behavior, detected in behaviors.items():
                            if detected and behavior in behavior_map:
                                mapped_behavior = behavior_map[behavior]
                                if mapped_behavior in behavior_counts:
                                    behavior_counts[mapped_behavior] += 1
            
            return behavior_counts
        except Exception as e:
            self.logger.error(f"获取行为统计数据失败: {str(e)}")
            return {}
    
    def _update_behavior_chart(self, behavior_data):
        """更新行为统计图表"""
        # 清除现有数据
        self.behavior_plot.clear()
        
        # 准备数据
        behaviors = list(behavior_data.keys())
        counts = list(behavior_data.values())
        x = np.arange(len(behaviors))
        
        # 创建柱状图 - 使用单个颜色字符串，PyQtGraph不支持颜色列表
        bars = pg.BarGraphItem(
            x=x, 
            height=counts, 
            width=0.6, 
            brush="#3498db"  # 使用单个蓝色
        )
        self.behavior_plot.addItem(bars)
        
        # 设置X轴标签
        self.behavior_plot.setXRange(-0.5, len(behaviors)-0.5)
        ticks = [tuple(zip(x, [str(b) for b in behaviors]))]
        self.behavior_plot.getAxis('bottom').setTicks([ticks])
        
        # 在柱状图上显示数值
        for i, count in enumerate(counts):
            text = pg.TextItem(str(count), anchor=(0.5, 1))
            text.setPos(i, count)
            self.behavior_plot.addItem(text)


class VehicleDashboard(QWidget):
    """车辆监控仪表盘主界面"""
    def __init__(self, config_manager, db_handler, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.db_handler = db_handler
        self.logger = logging.getLogger("VehicleDashboard")
        
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 实时仪表盘（已移除"实时监控"标签页）
        self.dashboard_tab = DashboardTab(self.config_manager)
        
        # 历史数据
        self.historical_tab = HistoricalDataTab(self.config_manager, self.db_handler)
        self.tabs.addTab(self.historical_tab, "历史数据")
        
        main_layout.addWidget(self.tabs)
        
        # 应用配置
        self._apply_ui_config()
        
        # 连接配置更新信号
        self.config_manager.config_updated.connect(self._on_config_updated)
    
    def _apply_ui_config(self):
        """应用界面配置"""
        ui_config = self.config_manager.get_config("UIConfig")
        theme = ui_config.get("theme", "light")
        
        # 设置主题
        if theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #333;
                    color: #fff;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 4px;
                    margin-top: 6px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 7px;
                    color: #fff;
                }
            """)
        else:
            self.setStyleSheet("")
    
    def update_realtime_data(self, data):
        """更新实时数据"""
        # 使用数据适配器统一数据格式
        adapted_data = DashboardDataAdapter.adapt_data(data)
        self.dashboard_tab.update_realtime_data(adapted_data)
    
    def clear_dashboard_data(self):
        """清除仪表盘数据"""
        self.dashboard_tab.clear_data()
    
    @Slot(str, dict)
    def _on_config_updated(self, config_name, config_data):
        """配置更新回调"""
        if config_name == "UIConfig":
            self._apply_ui_config()
        elif config_name == "AnalysisConfig":
            # 分析配置更新时刷新历史数据
            self.historical_tab._load_historical_data()
    