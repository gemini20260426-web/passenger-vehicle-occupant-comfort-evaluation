import os
import matplotlib
matplotlib.use('QtAgg', force=True)
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

import logging
logging.info(f"当前Matplotlib后端: {matplotlib.get_backend()}")

import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib.dates import DateFormatter
import matplotlib.patches as patches
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QSlider, 
                            QGridLayout, QSizePolicy, QGroupBox, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QFont
# 尝试导入redis，若失败则设置为None
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class DataProcessor(QObject):
    data_processed = Signal(pd.DataFrame)

    def __init__(self, max_points, time_window):
        super().__init__()
        self.max_points = max_points
        self.time_window = time_window
        self.data = pd.DataFrame(columns=['time', 'speed', 'ax', 'ay', 'az', 'wheel', 'operation'])
        self.data_buffer = []
        self.buffer_size = 20
        self._emit_counter = 0
        self._emit_throttle = 3

    def process_data(self, redis_data):
        real_data = redis_data.get('data', {})

        wheel_value = real_data.get('wheel', 0)
        wheel_percent = wheel_value / 90 * 100 if abs(wheel_value) <= 90 else 100 if wheel_value > 0 else -100

        speed_value = real_data.get('speed', 0)
        speed_percent = min(speed_value / 120 * 100, 100)

        ts = redis_data.get('timestamp', datetime.now().timestamp())
        row = {
            'time': datetime.fromtimestamp(ts),
            'speed': speed_percent,
            'ax': real_data.get('ax', 0),
            'ay': real_data.get('ay', 0),
            'az': real_data.get('az', 0),
            'wheel': wheel_percent,
            'operation': self.determine_operation(real_data)
        }
        self.data_buffer.append(row)

        if len(self.data_buffer) >= self.buffer_size:
            new_df = pd.DataFrame(self.data_buffer)
            self.data = pd.concat([self.data, new_df], ignore_index=True)
            self.data_buffer = []

            if not self.data.empty:
                latest_time = self.data['time'].iloc[-1]
                cutoff = latest_time - self.time_window
                self.data = self.data[self.data['time'] >= cutoff]
                if len(self.data) > self.max_points:
                    self.data = self.data.iloc[-self.max_points:]

            self._emit_counter += 1
            if self._emit_counter >= self._emit_throttle:
                self._emit_counter = 0
                self.data_processed.emit(self.data)

    def determine_operation(self, data):
        speed = data.get('speed', 0)
        ax = data.get('ax', 0)
        wheel = data.get('wheel', 0)

        if abs(wheel) > 5:
            return '转弯'
        elif ax > 0.3:
            return '加速'
        elif ax < -0.3:
            return '减速'
        elif speed > 0:
            return '正常行驶'
        else:
            return '静止'

class Plotter(QObject):
    def __init__(self, figure, axes, ax_accel, ax_speed, ax_wheel, line_ax, line_ay, line_az, line_speed, line_wheel, canvas):
        super().__init__()
        self.figure = figure
        self.axes = axes
        self.ax_accel = ax_accel
        self.ax_speed = ax_speed
        self.ax_wheel = ax_wheel
        self.line_ax = line_ax
        self.line_ay = line_ay
        self.line_az = line_az
        self.line_speed = line_speed
        self.line_wheel = line_wheel
        self.canvas = canvas

        self.accel_ref = self.ax_accel.axhspan(-0.5, 0.5, alpha=0.1, color='green', zorder=0)
        self.speed_ref = self.ax_speed.axhspan(0, 50, alpha=0.1, color='blue', zorder=0)
        self.wheel_ref = self.ax_wheel.axhspan(-15, 15, alpha=0.1, color='purple', zorder=0)

        self.accel_threshold = self.ax_accel.axhline(0.5, color='red', linestyle='--', alpha=0.5, linewidth=0.8)
        self.accel_threshold2 = self.ax_accel.axhline(-0.5, color='red', linestyle='--', alpha=0.5, linewidth=0.8)
        self.wheel_threshold = self.ax_wheel.axhline(30, color='red', linestyle='--', alpha=0.5, linewidth=0.8)
        self.wheel_threshold2 = self.ax_wheel.axhline(-30, color='red', linestyle='--', alpha=0.5, linewidth=0.8)

        self._draw_pending = False
        self._last_draw_time = 0
        self._draw_throttle_ms = 50

    def smart_scale(self, data, default_min, default_max):
        if len(data) == 0:
            return default_min, default_max

        if default_min == -2 and default_max == 2:
            return -2, 2

        if default_min == -100 and default_max == 100:
            return -100, 100

        min_val = min(data)
        max_val = max(data)
        padding = (max_val - min_val) * 0.2
        if padding == 0:
            padding = default_max * 0.2

        return max(0, min_val - padding), max_val + padding

    def update_plot(self, data):
        if data.empty:
            return

        self.line_ax.set_data(data['time'], data['ax'])
        self.line_ay.set_data(data['time'], data['ay'])
        self.line_az.set_data(data['time'], data['az'])
        self.line_speed.set_data(data['time'], data['speed'])
        self.line_wheel.set_data(data['time'], data['wheel'])

        if len(data) > 1:
            min_time = data['time'].min()
            max_time = data['time'].max()
            padding = (max_time - min_time) * 0.1
            self.axes.set_xlim(min_time - padding, max_time + padding)

        self.ax_accel.set_ylim(-2, 2)
        self.ax_speed.set_ylim(0, 100)
        self.ax_wheel.set_ylim(-100, 100)

        self._schedule_draw()

    def _schedule_draw(self):
        import time as _time
        now = _time.time() * 1000
        if now - self._last_draw_time < self._draw_throttle_ms:
            if not self._draw_pending:
                self._draw_pending = True
                from PySide6.QtCore import QTimer
                QTimer.singleShot(self._draw_throttle_ms, self._do_draw)
            return

        self._last_draw_time = now
        self._draw_pending = False
        self._do_draw()

    def _do_draw(self):
        self._draw_pending = False
        self._last_draw_time = time.time() * 1000
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() and self.canvas and not self.canvas.isNull():
                if self.canvas.isVisible():
                    self.canvas.draw_idle()
        except Exception:
            pass

class RedisSubscriber(QRunnable):
    def __init__(self, data_processor):
        super().__init__()
        self.data_processor = data_processor
        self.channel = 'driving_realtime_data'
        self.redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(self.channel)
        self.running = True
        self.reconnect_count = 0
        self.max_reconnect = 5
        self.executor = ThreadPoolExecutor(max_workers=1)

    def run(self):
        # 使用线程池执行异步任务
        future = self.executor.submit(self.run_async)
        future.result()

    def run_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.subscribe())

    async def subscribe(self):
        while self.running:
            try:
                message = self.pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        self.data_processor.process_data(data)
                        self.reconnect_count = 0
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON解析错误: {e}")
            except (redis.ConnectionError, OSError) as e:
                if self.running and self.reconnect_count < self.max_reconnect:
                    logging.error(f"Redis连接错误，尝试重连({self.reconnect_count+1}/{self.max_reconnect}): {e}")
                    try:
                        self.pubsub.close()
                        self.redis_client.close()
                    except:
                        pass
                    
                    # 使用相同端口重连
                    self.redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)
                    self.pubsub = self.redis_client.pubsub()
                    self.pubsub.subscribe(self.channel)
                    self.reconnect_count += 1
                    await asyncio.sleep(1)
                else:
                    if self.running:
                        logging.error("达到最大重连次数，停止尝试")
                        self.stop()
            except Exception as e:
                logging.error(f"处理消息时发生错误: {e}")

    def stop(self):
        self.running = False
        try:
            self.pubsub.close()
            self.redis_client.close()
        except:
            pass
        self.executor.shutdown(wait=False)

class IMUVisualizer(QWidget):
    def __init__(self, channel_suffix=""):
        super().__init__()

        self.setFont(QFont("Microsoft YaHei", 9))
        self.channel = f'driving_realtime_data{channel_suffix}'

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self.create_enhanced_control_panel()

        self.create_aspect_ratio_plot_area()

        self.max_points = 500
        self.time_window = timedelta(seconds=8)
        self.data_processor = DataProcessor(self.max_points, self.time_window)
        
        self.plotter = Plotter(
            self.figure, self.axes, 
            self.ax_accel, self.ax_speed, self.ax_wheel,
            self.line_ax, self.line_ay, self.line_az, 
            self.line_speed, self.line_wheel, 
            self.canvas
        )
        
        self.data_processor.data_processed.connect(self.plotter.update_plot)

        self.thread_pool = None
        self.redis_subscriber = None

        self.is_running = True
        self.start_time = datetime.now()
        
    def start_redis_subscription(self):
        """启动Redis订阅（显式调用而非自动启动）"""
        if self.thread_pool is None:
            self.thread_pool = QThreadPool()
        if self.redis_subscriber is None:
            self.redis_subscriber = RedisSubscriber(self.data_processor)
        self.thread_pool.start(self.redis_subscriber)
    
    def create_enhanced_control_panel(self):
        """创建优化的控制面板布局"""
        # 创建主控制面板容器
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(20)
        
        # 按钮组
        button_group = QGroupBox("")
        button_layout = QHBoxLayout(button_group)
        button_layout.setContentsMargins(10, 10, 10, 10)
        
        self.mq_btn = QPushButton("智能队列")
        self.mq_btn.setFixedSize(100, 35)
        button_layout.addWidget(self.mq_btn)
        
        self.start_stop_btn = QPushButton("暂停")
        self.start_stop_btn.setFixedSize(90, 35)
        button_layout.addWidget(self.start_stop_btn)
        
        self.clear_btn = QPushButton("清空数据")
        self.clear_btn.setFixedSize(100, 35)
        button_layout.addWidget(self.clear_btn)
        
        # 参数控制组
        param_group = QGroupBox("")
        param_layout = QGridLayout(param_group)
        param_layout.setContentsMargins(10, 15, 10, 15)
        param_layout.setHorizontalSpacing(15)
        param_layout.setVerticalSpacing(10)
        
        # 更新频率控制
        freq_label = QLabel("更新频率 (ms):")
        param_layout.addWidget(freq_label, 0, 0)
        
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setMinimum(50)
        self.freq_slider.setMaximum(500)
        self.freq_slider.setValue(100)
        self.freq_slider.setFixedWidth(180)
        param_layout.addWidget(self.freq_slider, 0, 1)
        
        self.freq_value = QLabel("100")
        self.freq_value.setFixedWidth(40)
        param_layout.addWidget(self.freq_value, 0, 2)
        
        # 显示点数控制
        points_label = QLabel("显示点数:")
        param_layout.addWidget(points_label, 1, 0)
        
        self.points_slider = QSlider(Qt.Horizontal)
        self.points_slider.setMinimum(100)
        self.points_slider.setMaximum(2000)
        self.points_slider.setValue(1000)
        self.points_slider.setFixedWidth(180)
        param_layout.addWidget(self.points_slider, 1, 1)
        
        self.points_value = QLabel("1000")
        self.points_value.setFixedWidth(40)
        param_layout.addWidget(self.points_value, 1, 2)
        
        # 状态指示器
        status_group = QGroupBox("")
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(10, 15, 10, 15)
        
        self.status_label = QLabel("状态: 运行中")
        self.status_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: green;
                background-color: #f0f0f0;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        status_layout.addWidget(self.status_label)
        
        # 添加控件到主控制布局
        control_layout.addWidget(button_group)
        control_layout.addWidget(param_group)
        control_layout.addWidget(status_group)
        control_layout.addStretch()
        
        # 连接信号
        self.start_stop_btn.clicked.connect(self.toggle_pause)
        self.clear_btn.clicked.connect(self.clear_data)
        self.mq_btn.clicked.connect(self.toggle_mq_mode)
        self.freq_slider.valueChanged.connect(self.update_frequency)
        self.points_slider.valueChanged.connect(self.update_points_display)
        
        # 添加到主布局
        self.main_layout.addWidget(control_container)

    def create_aspect_ratio_plot_area(self):
        """创建16:9比例的绘图区域"""
        # 创建绘图容器
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用16:9比例的容器
        aspect_container = QWidget()
        # 修复尺寸策略设置
        aspect_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        aspect_layout = QVBoxLayout(aspect_container)
        aspect_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建图表
        self.figure = Figure(figsize=(16, 9), dpi=80)  # 16:9比例
        self.canvas = FigureCanvas(self.figure)
        # 修复尺寸策略设置
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        aspect_layout.addWidget(self.canvas)
        
        # 设置容器的最小尺寸以保持比例
        aspect_container.setMinimumSize(800, 450)  # 16:9比例
        
        plot_layout.addWidget(aspect_container)
        self.main_layout.addWidget(plot_container, 1)  # 占据主要空间

        # 创建图表内容
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title("IMU驾驶数据实时可视化", fontsize=16, fontweight='bold')
        self.axes.set_xlabel("时间", fontsize=10)
        
        # 设置时间格式化
        date_format = DateFormatter('%H:%M:%S')
        self.axes.xaxis.set_major_formatter(date_format)
        self.figure.autofmt_xdate()

        # 调整Y轴位置避免重叠
        # 加速度轴
        self.ax_accel = self.axes.twinx()
        self.ax_accel.spines['right'].set_position(('axes', 0.0))
        self.ax_accel.set_ylabel('加速度 (m/s²)', color='#FF4500', fontsize=10)
        self.ax_accel.tick_params(axis='y', labelcolor='#FF4500', labelsize=8)
        self.ax_accel.grid(True, linestyle='--', alpha=0.3, color='#FF4500')
        
        # 速度轴（百分比）
        self.ax_speed = self.axes.twinx()
        self.ax_speed.spines['right'].set_position(('axes', 0.15))
        self.ax_speed.set_ylabel('速度 (%)', color='#1E90FF', fontsize=10)
        self.ax_speed.tick_params(axis='y', labelcolor='#1E90FF', labelsize=8)
        self.ax_speed.grid(True, linestyle='--', alpha=0.3, color='#1E90FF')
        
        # 方向盘轴（百分比）
        self.ax_wheel = self.axes.twinx()
        self.ax_wheel.spines['right'].set_position(('axes', 0.3))
        self.ax_wheel.set_ylabel('方向盘转角 (%)', color='#4169E1', fontsize=10)
        self.ax_wheel.tick_params(axis='y', labelcolor='#4169E1', labelsize=8)
        self.ax_wheel.grid(True, linestyle='--', alpha=0.3, color='#4169E1')
        
        # 设置初始轴范围
        self.ax_accel.set_ylim(-2, 2)
        self.ax_speed.set_ylim(0, 100)  # 百分比范围
        self.ax_wheel.set_ylim(-100, 100)  # 百分比范围
        
        # 创建曲线 - 使用不同样式
        self.line_ax, = self.ax_accel.plot(
            [], [], 'r-', label='纵向加速度', 
            linewidth=1.8, alpha=0.9
        )
        self.line_ay, = self.ax_accel.plot(
            [], [], 'g-', label='横向加速度', 
            linewidth=1.8, alpha=0.9
        )
        self.line_az, = self.ax_accel.plot(
            [], [], 'b-', label='垂直加速度', 
            linewidth=1.8, alpha=0.9
        )
        self.line_speed, = self.ax_speed.plot(
            [], [], 'c-', label='速度', 
            linewidth=2.2, alpha=0.95
        )
        self.line_wheel, = self.ax_wheel.plot(
            [], [], 'm-', label='方向盘转角', 
            linewidth=2.5, alpha=0.95
        )
        
        # 添加图例（放在图表内部右上角）
        lines = [self.line_ax, self.line_ay, self.line_az, self.line_speed, self.line_wheel]
        self.axes.legend(
            lines, [l.get_label() for l in lines], 
            loc='upper right',
            framealpha=0.8,
            fontsize=9,
            bbox_to_anchor=(0.98, 0.98),
            ncol=1
        )

        # 添加图表说明
        self.axes.text(
            0.5, 1.03, 
            "说明: 加速度范围: ±2 m/s² | 速度范围: 0-100% | 方向盘范围: ±100%",
            transform=self.axes.transAxes,
            ha='center',
            fontsize=9,
            alpha=0.8
        )

        # 调整图表布局
        self.figure.subplots_adjust(
            left=0.08, 
            right=0.92, 
            top=0.92, 
            bottom=0.12,
            hspace=0.2
        )
        self.canvas.draw_idle()
    
    def toggle_pause(self):
        """切换暂停/继续状态"""
        self.is_running = not self.is_running
        if self.is_running:
            self.start_stop_btn.setText("暂停")
            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            # 重新启动订阅
            self.redis_subscriber.running = True
            self.thread_pool.start(self.redis_subscriber)
        else:
            self.start_stop_btn.setText("继续")
            self.status_label.setText("状态: 已暂停")
            self.status_label.setStyleSheet("font-weight: bold; color: gray;")
            # 停止订阅
            self.redis_subscriber.stop()
    
    def clear_data(self):
        """清空数据"""
        self.data_processor.data = pd.DataFrame(columns=['time', 'speed', 'ax', 'ay', 'az', 'wheel', 'operation'])
        self.plotter.update_plot(self.data_processor.data)
    
    def update_frequency(self, value):
        """改变更新频率"""
        self.freq_value.setText(str(value))
        # 这里可以添加实际改变频率的逻辑
    
    def update_points_display(self, value):
        """改变显示点数"""
        self.points_value.setText(str(value))
        self.data_processor.max_points = value
    
    def toggle_mq_mode(self):
        """切换到消息队列界面（占位函数）"""
        logging.info("切换到消息队列界面")
        # 实际实现需要根据需求添加
    
    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于 IMU 可视化", 
                         "<b>IMU 驾驶数据实时可视化工具</b><br><br>"
                         "版本: 1.0<br>"
                         "开发人员: 您的团队<br>"
                         "© 2023 您的公司")
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        self.redis_subscriber.stop()
        event.accept()

if __name__ == "__main__":
    import sys
    import traceback
    
    try:
        app = QApplication(sys.argv)

        font = QFont()
        font.setStyleHint(QFont.SansSerif)
        app.setFont(font)

        window = QMainWindow()
        window.setWindowTitle("IMU驾驶数据实时可视化")
        window.setGeometry(100, 100, 1200, 800)
        visualizer = IMUVisualizer()
        window.setCentralWidget(visualizer)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        # 记录异常信息到日志
        logging.error(f"程序崩溃: {str(e)}")
        logging.error(traceback.format_exc())
        # 显示错误对话框
        QMessageBox.critical(None, "程序错误", f"""发生错误: {str(e)}
请查看日志获取详细信息""")