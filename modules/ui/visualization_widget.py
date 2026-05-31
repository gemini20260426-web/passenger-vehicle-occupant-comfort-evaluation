import sys
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('QtAgg', force=True)
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
                              QSizePolicy, QFrame)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont
import logging
from collections import deque

logger = logging.getLogger(__name__)

MAX_POINTS = 500
RENDER_INTERVAL_MS = 100


class RingBuffer:
    def __init__(self, maxlen=2000):
        self._buf = deque(maxlen=maxlen)

    def append(self, item):
        self._buf.append(item)

    def drain(self):
        if not self._buf:
            return []
        items = list(self._buf)
        self._buf.clear()
        return items

    def clear(self):
        self._buf.clear()

    def __len__(self):
        return len(self._buf)


class VisualizationWidget(QWidget):

    def __init__(self, channel_suffix=""):
        super().__init__()
        self.setFont(QFont("Microsoft YaHei", 9))
        self.channel = f'driving_realtime_data{channel_suffix}'
        self.setWindowTitle("IMU驾驶数据实时可视化")

        self.is_running = True
        self._sample_count = 0
        self._fps_counter = 0
        self._ring = RingBuffer(maxlen=2000)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(4)

        self._create_control_panel()
        self._create_plot_area()
        self._init_timers()

    def _init_timers(self):
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._render_loop)
        self._render_timer.start(RENDER_INTERVAL_MS)

        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)

    def _render_loop(self):
        if not self.is_running:
            return
        batch = self._ring.drain()
        if not batch:
            return

        for record in batch:
            self._apply_record(record)
        self._fps_counter += 1

    def _apply_record(self, record):
        if not isinstance(record, dict):
            return
        self._sample_count += 1

        ts = record.get('timestamp', time.time())
        if isinstance(ts, (int, float)):
            t = datetime.fromtimestamp(ts)
        else:
            t = datetime.now()

        ax = self._safe_float(record.get('ax'))
        ay = self._safe_float(record.get('ay'))
        az = self._safe_float(record.get('az'))
        gx = self._safe_float(record.get('gx'))
        gy = self._safe_float(record.get('gy'))
        gz = self._safe_float(record.get('gz'))
        speed = self._safe_float(record.get('speed'))
        wheel = self._safe_float(record.get('wheel'))

        self._accel_times.append(t)
        self._accel_ax.append(ax)
        self._accel_ay.append(ay)
        self._accel_az.append(az)

        self._gyro_times.append(t)
        self._gyro_gx.append(gx)
        self._gyro_gy.append(gy)
        self._gyro_gz.append(gz)

        self._vehicle_times.append(t)
        self._vehicle_speed.append(speed)
        self._vehicle_wheel.append(wheel)

    def _safe_float(self, val):
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def _update_fps(self):
        self.lbl_fps.setText(f"FPS: {self._fps_counter}  样本: {self._sample_count}")
        self._fps_counter = 0

    def _create_plot_area(self):
        self.figure = Figure(figsize=(16, 9), dpi=80, constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout.addWidget(self.canvas, 1)

        gs = self.figure.add_gridspec(3, 1, hspace=0.35)

        self.ax_accel = self.figure.add_subplot(gs[0])
        self.ax_accel.set_ylabel('加速度 (m/s²)', fontsize=9, color='#ff5252')
        self.ax_accel.tick_params(axis='y', labelcolor='#ff5252', labelsize=7)
        self.ax_accel.grid(True, linestyle='--', alpha=0.3)
        self.ax_accel.set_ylim(-16, 16)
        self.ax_accel.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

        self.ax_gyro = self.figure.add_subplot(gs[1])
        self.ax_gyro.set_ylabel('角速度 (rad/s)', fontsize=9, color='#00e5ff')
        self.ax_gyro.tick_params(axis='y', labelcolor='#00e5ff', labelsize=7)
        self.ax_gyro.grid(True, linestyle='--', alpha=0.3)
        self.ax_gyro.set_ylim(-5, 5)
        self.ax_gyro.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

        self.ax_vehicle = self.figure.add_subplot(gs[2])
        self.ax_vehicle.set_ylabel('车速 (km/h)', fontsize=9, color='#ffffff')
        self.ax_vehicle.tick_params(axis='y', labelcolor='#ffffff', labelsize=7)
        self.ax_vehicle.grid(True, linestyle='--', alpha=0.3)
        self.ax_vehicle.set_ylim(0, 150)
        self.ax_vehicle.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        self.ax_vehicle.set_xlabel('时间', fontsize=9)

        self.ax_wheel = self.ax_vehicle.twinx()
        self.ax_wheel.set_ylabel('转向角 (°)', fontsize=9, color='#ff9800')
        self.ax_wheel.tick_params(axis='y', labelcolor='#ff9800', labelsize=7)
        self.ax_wheel.set_ylim(-720, 720)

        self._accel_times = deque(maxlen=MAX_POINTS)
        self._accel_ax = deque(maxlen=MAX_POINTS)
        self._accel_ay = deque(maxlen=MAX_POINTS)
        self._accel_az = deque(maxlen=MAX_POINTS)

        self._gyro_times = deque(maxlen=MAX_POINTS)
        self._gyro_gx = deque(maxlen=MAX_POINTS)
        self._gyro_gy = deque(maxlen=MAX_POINTS)
        self._gyro_gz = deque(maxlen=MAX_POINTS)

        self._vehicle_times = deque(maxlen=MAX_POINTS)
        self._vehicle_speed = deque(maxlen=MAX_POINTS)
        self._vehicle_wheel = deque(maxlen=MAX_POINTS)

        (self.line_ax,) = self.ax_accel.plot([], [], color='#ff5252', linewidth=1.0, label='AX')
        (self.line_ay,) = self.ax_accel.plot([], [], color='#69f0ae', linewidth=1.0, label='AY')
        (self.line_az,) = self.ax_accel.plot([], [], color='#448aff', linewidth=1.0, label='AZ')
        self.ax_accel.legend(loc='upper right', fontsize=7, framealpha=0.6)

        (self.line_gx,) = self.ax_gyro.plot([], [], color='#00e5ff', linewidth=1.0, label='GX')
        (self.line_gy,) = self.ax_gyro.plot([], [], color='#ea80fc', linewidth=1.0, label='GY')
        (self.line_gz,) = self.ax_gyro.plot([], [], color='#ffd740', linewidth=1.0, label='GZ')
        self.ax_gyro.legend(loc='upper right', fontsize=7, framealpha=0.6)

        (self.line_speed,) = self.ax_vehicle.plot([], [], color='#ffffff', linewidth=1.2, label='Speed')
        (self.line_wheel,) = self.ax_wheel.plot([], [], color='#ff9800', linewidth=1.0, label='Wheel')
        lines_v = [self.line_speed, self.line_wheel]
        labels_v = [l.get_label() for l in lines_v]
        self.ax_vehicle.legend(lines_v, labels_v, loc='upper left', fontsize=7, framealpha=0.6)

        self._redraw_timer = QTimer(self)
        self._redraw_timer.timeout.connect(self._redraw_canvas)
        self._redraw_timer.start(RENDER_INTERVAL_MS)

        self.canvas.draw_idle()

    def _redraw_canvas(self):
        if not self.is_running:
            return
        try:
            t_accel = list(self._accel_times)
            if len(t_accel) >= 2:
                self.line_ax.set_data(t_accel, list(self._accel_ax))
                self.line_ay.set_data(t_accel, list(self._accel_ay))
                self.line_az.set_data(t_accel, list(self._accel_az))
                self.ax_accel.set_xlim(t_accel[0], t_accel[-1])

            t_gyro = list(self._gyro_times)
            if len(t_gyro) >= 2:
                self.line_gx.set_data(t_gyro, list(self._gyro_gx))
                self.line_gy.set_data(t_gyro, list(self._gyro_gy))
                self.line_gz.set_data(t_gyro, list(self._gyro_gz))
                self.ax_gyro.set_xlim(t_gyro[0], t_gyro[-1])

            t_veh = list(self._vehicle_times)
            if len(t_veh) >= 2:
                self.line_speed.set_data(t_veh, list(self._vehicle_speed))
                self.line_wheel.set_data(t_veh, list(self._vehicle_wheel))
                self.ax_vehicle.set_xlim(t_veh[0], t_veh[-1])

            self.canvas.draw_idle()
        except Exception as e:
            logger.debug(f"重绘异常: {e}")

    def _create_control_panel(self):
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(36)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 0, 8, 0)
        bar_layout.setSpacing(10)

        self.start_stop_btn = QPushButton("暂停")
        self.start_stop_btn.setFixedHeight(26)
        self.start_stop_btn.clicked.connect(self._toggle_pause)
        bar_layout.addWidget(self.start_stop_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedHeight(26)
        self.clear_btn.clicked.connect(self._clear_data)
        bar_layout.addWidget(self.clear_btn)

        bar_layout.addStretch()

        freq_label = QLabel("刷新:")
        freq_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        bar_layout.addWidget(freq_label)

        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setMinimum(16)
        self.freq_slider.setMaximum(200)
        self.freq_slider.setValue(33)
        self.freq_slider.setFixedWidth(100)
        self.freq_slider.valueChanged.connect(self._change_frequency)
        bar_layout.addWidget(self.freq_slider)

        self.freq_value = QLabel("33ms")
        self.freq_value.setFixedWidth(38)
        self.freq_value.setStyleSheet("QLabel { font-size: 11px; }")
        bar_layout.addWidget(self.freq_value)

        points_label = QLabel("点数:")
        points_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        bar_layout.addWidget(points_label)

        self.points_slider = QSlider(Qt.Horizontal)
        self.points_slider.setMinimum(100)
        self.points_slider.setMaximum(2000)
        self.points_slider.setValue(500)
        self.points_slider.setFixedWidth(100)
        self.points_slider.valueChanged.connect(self._change_points)
        bar_layout.addWidget(self.points_slider)

        self.points_value = QLabel("500")
        self.points_value.setFixedWidth(32)
        self.points_value.setStyleSheet("QLabel { font-size: 11px; }")
        bar_layout.addWidget(self.points_value)

        self.lbl_fps = QLabel("FPS: 0  样本: 0")
        self.lbl_fps.setStyleSheet("QLabel { color: #4caf50; font-size: 10px; }")
        bar_layout.addWidget(self.lbl_fps)

        self.main_layout.addWidget(bar)

    def _toggle_pause(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.start_stop_btn.setText("暂停")
        else:
            self.start_stop_btn.setText("继续")

    def _clear_data(self):
        self._sample_count = 0
        self._ring.clear()
        for dq in [self._accel_times, self._accel_ax, self._accel_ay, self._accel_az,
                    self._gyro_times, self._gyro_gx, self._gyro_gy, self._gyro_gz,
                    self._vehicle_times, self._vehicle_speed, self._vehicle_wheel]:
            dq.clear()
        self.lbl_fps.setText("FPS: 0  样本: 0")

    def _change_frequency(self, value):
        self.freq_value.setText(f"{value}ms")
        self._render_timer.setInterval(value)
        self._redraw_timer.setInterval(value)

    def _change_points(self, value):
        self.points_value.setText(str(value))
        for dq in [self._accel_times, self._accel_ax, self._accel_ay, self._accel_az,
                    self._gyro_times, self._gyro_gx, self._gyro_gy, self._gyro_gz,
                    self._vehicle_times, self._vehicle_speed, self._vehicle_wheel]:
            dq.maxlen = value

    def update_imu_data(self, imu_data):
        if not isinstance(imu_data, dict):
            return
        self._ring.append(imu_data)

    def update_from_analyzer(self, imu_data, analysis_result=None):
        self.update_imu_data(imu_data)

    def update_display(self, imu_data):
        if isinstance(imu_data, dict):
            data = imu_data.get('data', imu_data)
        elif isinstance(imu_data, list) and imu_data:
            last = imu_data[-1]
            data = last.get('data', last) if isinstance(last, dict) else {}
        else:
            return
        self.update_imu_data(data)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'canvas'):
            self.canvas.draw_idle()

    def closeEvent(self, event):
        event.accept()
