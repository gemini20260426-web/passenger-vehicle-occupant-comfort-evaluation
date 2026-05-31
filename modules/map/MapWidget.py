#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import time
import numpy as np
import logging
from datetime import datetime
from PySide6.QtCore import Qt, QUrl, QTimer, Signal, Slot, QMutex, QMutexLocker, QMetaObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QSplitter, QFrame
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from PySide6.QtCore import Qt
import matplotlib.pyplot as plt

# 导入配置和分析模块
from config import app_config, driving_thresholds
import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, QTimer, Qt
import json

# 导入可视化模块
from driving_behavior_evaluation.visual import VisualizationModule

class MapWidget(QWebEngineView):
    """高德地图控件，用于显示行车轨迹（已移除WebEngine依赖）"""

    positionUpdated = Signal(dict)

    def __init__(self, data_storage, parent=None):
        super().__init__(parent)
        self.data_lock = QMutex()
        # 连接数据存储的信号到UI更新槽函数
        data_storage.data_updated_signal.connect(self.on_data_updated)
        self.init_ui()

        # 轨迹数据
        self.trajectory = []
        self.current_position = None

        # 定时器，用于模拟实时数据
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_map_position)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 移除WebEngine依赖，显示占位信息
        self.info_label = QLabel("地图功能暂时不可用", self)
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(self.info_label)
        self.visualization = VisualizationModule()
        self.visualization.setup_ui(self)

    def load_map(self):
        """加载高德地图HTML"""
        # 构建高德地图HTML
        map_html = self._generate_map_html()

        # 加载HTML内容
        self.web_view.setHtml(map_html)

    def _generate_map_html(self):
        """生成高德地图HTML代码"""
        # 使用高德地图API的基本HTML模板
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>高德地图 - 行车轨迹</title>
            <style>
                html, body, #container {{
                    width: 100%;
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}
                .amap-logo, .amap-copyright {{
                    opacity: 0;
                }}
            </style>
            <script src="https://webapi.amap.com/maps?v=2.0&key={app_config.GAODE_MAP_KEY}"></script>
            <script src="https://webapi.amap.com/ui/1.1/main.js?v=1.1.1"></script>
        </head>
        <body>
            <div id="container"></div>
            <script>
                // 初始化地图
                var map = new AMap.Map('container', {{
                    zoom: 16,
                    center: [116.397428, 39.90923], // 默认中心位置
                    viewMode: '3D'
                }});
                
                // 添加地图控件
                map.addControl(new AMap.ToolBar());
                map.addControl(new AMap.Scale());
                
                // 轨迹线
                var polyline = new AMap.Polyline({{
                    path: [],
                    strokeColor: "#FF33FF",
                    strokeWeight: 6,
                    strokeOpacity: 1,
                    lineJoin: 'round',
                    lineCap: 'round',
                    zIndex: 50
                }});
                map.add(polyline);
                
                // 定位标记
                var marker = new AMap.Marker({{
                    position: [116.397428, 39.90923],
                    icon: "https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png",
                    offset: new AMap.Pixel(-10, -34),
                    zIndex: 100
                }});
                map.add(marker);
                
                // 信息窗口
                var infoWindow = new AMap.InfoWindow({{
                    isCustom: true,
                    content: '<div style="padding:0 5px;">当前位置</div>',
                    offset: new AMap.Pixel(0, -30)
                }});
                
                // 接收Python发送的位置数据
                window.receivePosition = function(position) {{
                    try {{
                        var pos = JSON.parse(position);
                        var lng = pos.longitude;
                        var lat = pos.latitude;
                        
                        // 更新标记位置
                        marker.setPosition([lng, lat]);
                        
                        // 更新轨迹
                        var path = polyline.getPath();
                        path.push([lng, lat]);
                        polyline.setPath(path);
                        
                        // 移动地图中心
                        map.setCenter([lng, lat]);
                        
                        // 显示信息窗口
                        infoWindow.setContent(
                            '<div style="padding:5px;">' +
                            '<p>时间: ' + pos.timestamp + '</p>' +
                            '<p>速度: ' + pos.speed + ' km/h</p>' +
                            '<p>加速度: ' + pos.acceleration + ' m/s²</p>' +
                            '</div>'
                        );
                        infoWindow.open(map, [lng, lat]);
                        
                        // 发送确认消息
                        window.pywebview.api.mapUpdated(JSON.stringify({{
                            success: true,
                            message: "位置已更新"
                        }}));
                    }} catch (e) {{
                        console.error("处理位置数据出错:", e);
                        window.pywebview.api.mapUpdated(JSON.stringify({{
                            success: false,
                            message: "处理位置数据出错: " + e.message
                        }}));
                    }}
                }};
                
                // 初始化地图完成
                window.pywebview.api.mapReady(JSON.stringify({{
                    success: true,
                    message: "地图已加载完成"
                }}));
            </script>
        </body>
        </html>
        """
        return html

    @Slot(str)
    def map_ready(self, message):
        """处理地图准备就绪的消息"""
        result = json.loads(message)
        if result.get("success"):
            logging.info(f"地图组件初始化完成 | 类型: 高德 | 版本: {app_config.MAP_VERSION}")
            # 开始模拟数据
            self.start_updating()
        else:
            logging.warning(f"地图图层加载失败 | 图层: 基础图层 | 错误: {result.get('message')}")

    @Slot(str)
    def map_updated(self, message):
        """处理地图更新的消息"""
        result = json.loads(message)
        if not result.get("success"):
            logging.error(f"地图更新失败: {result.get('message')}")

    def add_position(self, position):
        """添加新位置到轨迹"""
        self.trajectory.append(position)
        self.current_position = position

        # 发送位置数据到JavaScript
        self.web_view.page().runJavaScript(f"receivePosition('{json.dumps(position)}')")

    def start_updating(self):
        """开始更新地图位置"""
        self.timer.start(1000)  # 每秒更新一次

    @Slot(dict)
    def on_data_updated(self, latest_data):
        """处理数据更新并刷新地图（仅UI线程调用）"""
        with QMutexLocker(self.data_lock):
            self.update_map_position(latest_data)

    def update_map_position(self, data):
        """使用信号传递的数据更新地图位置"""
        if data and "latitude" in data and "longitude" in data:
            self.current_position = data
            QMetaObject.invokeMethod(self, '_thread_safe_update', Qt.QueuedConnection)

    def _thread_safe_update(self):
        if self.current_position:
            latest_data = self.current_position
            if latest_data:
                self.visualization.update_data(latest_data)
                self.visualization.update_plots()
                position = {
                    "timestamp": latest_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "longitude": latest_data.get("longitude", 116.397428),
                    "latitude": latest_data.get("latitude", 39.90923),
                    "speed": latest_data.get("speed", 0),
                    "acceleration": latest_data.get("acceleration_x", 0),
                }
                self.add_position(position)


class MainWindow(QMainWindow):
    """主窗口，集成地图和可视化模块"""

    def __init__(self):
        super().__init__()
        from data_processing.DataStorage import DataStorage
        self.data_storage = DataStorage(redis_config={}, mysql_config={})
        self.init_ui()

        # 设置定时器，定期更新数据
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)  # 每秒更新一次

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("驾驶行为分析系统")
        self.setGeometry(100, 100, 1200, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QHBoxLayout(central_widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 创建地图控件
        self.map_widget = MapWidget(self.data_storage)
        splitter.addWidget(self.map_widget)

        # 创建标签页控件
        self.tab_widget = QTabWidget()

        # 创建可视化模块
        self.visualization = VisualizationModule()
        self.dashboard_widget = self.visualization.get_canvas()
        self.tab_widget.addTab(self.dashboard_widget, "驾驶数据")

        # 添加其他功能页...

        splitter.addWidget(self.tab_widget)

        # 设置分割器初始大小
        splitter.setSizes([500, 700])

        main_layout.addWidget(splitter)

    def update_data(self):
        """更新数据和UI"""
        # 更新可视化数据
        self.visualization.update_data()
        self.visualization.update_plots()

        # 更新地图位置
        self.map_widget.update_map_position()


if __name__ == "__main__":
    # 确保中文显示正常
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]

    app = QApplication.instance()
    if not app:
        app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


class MapChartView(QChartView):
    def __init__(self):
        chart = QChart()
        super().__init__(chart)
