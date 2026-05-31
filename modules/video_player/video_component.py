#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSlider, QFileDialog, QMessageBox, QStyle, QListWidget, QListWidgetItem
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt, QUrl, Signal, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QPixmap, QImage

# 字幕文件解析器类
class SubtitleParser:
    def __init__(self):
        self.subtitles = []

    def load_srt(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                blocks = content.split('\n\n')
                for block in blocks:
                    if not block.strip():
                        continue
                    lines = block.split('\n')
                    if len(lines) < 3:
                        continue
                    # 解析时间戳
                    time_line = lines[1]
                    start_end = time_line.split(' --> ')
                    if len(start_end) != 2:
                        continue
                    start_time = self.time_to_ms(start_end[0])
                    end_time = self.time_to_ms(start_end[1])
                    # 解析字幕文本
                    text = '\n'.join(lines[2:])
                    self.subtitles.append((start_time, end_time, text))
            return True
        except Exception as e:
            QMessageBox.critical(None, "错误", f"加载字幕文件失败: {str(e)}")
            return False

    def time_to_ms(self, time_str):
        # 格式: 00:01:23,456
        parts = time_str.replace(',', '.').split(':')
        if len(parts) != 3:
            return 0
        hours, minutes, seconds = parts
        total_ms = (float(hours) * 3600 + float(minutes) * 60 + float(seconds)) * 1000
        return int(total_ms)

    def get_subtitle_at_time(self, ms):
        for start, end, text in self.subtitles:
            if start <= ms <= end:
                return text
        return None

# 视频分析器类
class VideoAnalyzer:
    def __init__(self):
        self.is_analyzing = False
        self.analysis_results = {}

    def start_analysis(self, video_path):
        self.is_analyzing = True
        self.analysis_results = {}
        # 模拟视频分析过程
        self.analysis_results['duration'] = 0  # 将由播放器提供
        self.analysis_results['motion_events'] = []
        self.analysis_results['brightness'] = []
        return True

    def stop_analysis(self):
        self.is_analyzing = False
        return self.analysis_results

    def analyze_frame(self, frame, timestamp):
        if not self.is_analyzing:
            return None
        # 模拟帧分析
        result = {
            'timestamp': timestamp,
            'motion_detected': bool(timestamp % 3000 < 1000),  # 每3秒检测一次运动
            'brightness': 0.5 + 0.5 * (timestamp % 5000) / 5000  # 亮度在0.5-1.0之间变化
        }
        if result['motion_detected']:
            self.analysis_results['motion_events'].append(timestamp)
        self.analysis_results['brightness'].append((timestamp, result['brightness']))
        return result


class VideoPlayerWidget(QWidget):
    # 定义信号
    videoLoaded = Signal(str)
    videoPositionChanged = Signal(int)
    screenshotSaved = Signal(str)
    analysisCompleted = Signal(dict)
    subtitleUpdated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.timestamp_data = {}
        self.playlist = []  # 播放列表
        self.current_video_index = -1  # 当前视频索引
        self.subtitle_parser = SubtitleParser()
        self.current_subtitle = ''
        self.video_analyzer = VideoAnalyzer()
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setInterval(1000)  # 每秒分析一次
        self.analysis_timer.timeout.connect(self.analyze_current_frame)

    def init_ui(self):
        # 创建布局
        self.main_layout = QVBoxLayout(self)
        self.control_layout = QHBoxLayout()

        # 创建媒体播放器和视频窗口
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)

        # 添加视频窗口到主布局
        self.main_layout.addWidget(self.video_widget)

        # 创建控制按钮
        self.open_btn = QPushButton("打开文件")
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.screenshot_btn = QPushButton("截图")
        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.next_btn = QPushButton()
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.load_subtitle_btn = QPushButton("加载字幕")
        self.analysis_btn = QPushButton("开始分析")

        # 创建进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)

        # 创建时间标签
        self.time_label = QLabel("00:00 / 00:00")

        # 创建音量控制
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.audio_output.setVolume(0.7)

        # 添加控件到控制布局
        self.control_layout.addWidget(self.open_btn)
        self.control_layout.addWidget(self.play_btn)
        self.control_layout.addWidget(self.stop_btn)
        self.control_layout.addWidget(self.prev_btn)
        self.control_layout.addWidget(self.next_btn)
        self.control_layout.addWidget(self.screenshot_btn)
        self.control_layout.addWidget(self.load_subtitle_btn)
        self.control_layout.addWidget(self.analysis_btn)
        self.control_layout.addWidget(self.position_slider)
        self.control_layout.addWidget(self.time_label)
        self.control_layout.addWidget(QLabel("音量:"))
        self.control_layout.addWidget(self.volume_slider)

        # 添加控制布局到主布局
        self.main_layout.addLayout(self.control_layout)

        # 连接信号和槽
        self.open_btn.clicked.connect(self.open_file)
        self.play_btn.clicked.connect(self.play_pause)
        self.stop_btn.clicked.connect(self.stop)
        self.prev_btn.clicked.connect(self.play_previous)
        self.next_btn.clicked.connect(self.play_next)
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.load_subtitle_btn.clicked.connect(self.load_subtitle)
        self.analysis_btn.clicked.connect(self.toggle_analysis)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed)
        self.media_player.playbackStateChanged.connect(self.check_playlist_end)

    def open_file(self):
        # 打开文件对话框
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "打开视频文件", "", "视频文件 (*.mp4 *.avi *.mkv *.mov);;所有文件 (*)"
        )

        if file_paths:
            # 添加到播放列表
            for file_path in file_paths:
                if file_path not in self.playlist:
                    self.playlist.append(file_path)
            
            # 如果当前没有播放视频，播放第一个
            if self.current_video_index == -1 and self.playlist:
                self.current_video_index = 0
                self.media_player.setSource(QUrl.fromLocalFile(self.playlist[self.current_video_index]))
                self.play()
                self.videoLoaded.emit(self.playlist[self.current_video_index])

    def play_pause(self):
        # 播放/暂停切换
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def play(self):
        # 播放视频
        self.media_player.play()

    def pause(self):
        # 暂停视频
        self.media_player.pause()

    def stop(self):
        # 停止播放
        self.media_player.stop()

    def set_position(self, position):
        # 设置播放位置
        self.media_player.setPosition(position)

    def position_changed(self, position):
        # 播放位置改变
        self.position_slider.setValue(position)
        self.update_time_label()
        self.videoPositionChanged.emit(position)
        
        # 更新字幕
        subtitle = self.subtitle_parser.get_subtitle_at_time(position)
        if subtitle != self.current_subtitle:
            self.current_subtitle = subtitle or ''
            self.subtitleUpdated.emit(self.current_subtitle)

    def duration_changed(self, duration):
        # 视频时长改变
        self.position_slider.setRange(0, duration)
        self.update_time_label()

    def update_time_label(self):
        # 更新时间标签
        current_time = self.format_time(self.media_player.position())
        duration = self.format_time(self.media_player.duration())
        self.time_label.setText(f"{current_time} / {duration}")

    def format_time(self, ms):
        # 格式化时间（毫秒转分:秒）
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def set_volume(self, value):
        # 设置音量
        self.audio_output.setVolume(value / 100)

    def media_status_changed(self, status):
        # 媒体状态改变
        if status == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def load_timestamp_data(self, json_path):
        # 加载时间戳数据
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.timestamp_data = json.load(f)
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载时间戳数据失败: {str(e)}")
            return False

    def get_data_at_position(self, position_ms):
        # 根据视频位置获取对应的数据
        # 这里假设timestamp_data是一个字典，键是时间戳（毫秒），值是对应的数据
        # 找到最接近当前位置的时间戳
        closest_timestamp = None
        min_diff = float('inf')

        for ts in self.timestamp_data.keys():
            try:
                ts_ms = int(ts)
                diff = abs(ts_ms - position_ms)
                if diff < min_diff:
                    min_diff = diff
                    closest_timestamp = ts
            except ValueError:
                continue

        if closest_timestamp is not None:
            return self.timestamp_data[closest_timestamp]
        return None
        
    def play_previous(self):
        # 播放上一个视频
        if not self.playlist:
            return
        
        self.current_video_index -= 1
        if self.current_video_index < 0:
            self.current_video_index = len(self.playlist) - 1
        
        self.media_player.setSource(QUrl.fromLocalFile(self.playlist[self.current_video_index]))
        self.play()
        self.videoLoaded.emit(self.playlist[self.current_video_index])
        
    def play_next(self):
        # 播放下一个视频
        if not self.playlist:
            return
        
        self.current_video_index += 1
        if self.current_video_index >= len(self.playlist):
            self.current_video_index = 0
        
        self.media_player.setSource(QUrl.fromLocalFile(self.playlist[self.current_video_index]))
        self.play()
        self.videoLoaded.emit(self.playlist[self.current_video_index])
        
    def check_playlist_end(self, state):
        # 检查播放列表是否结束
        if state == QMediaPlayer.StoppedState and self.playlist and self.current_video_index < len(self.playlist) - 1:
            self.play_next()
        
    def take_screenshot(self):
        # 截图功能
        if not self.video_widget.isVisible():
            QMessageBox.warning(self, "警告", "无法截图，视频窗口不可见")
            return
        
        # 创建截图目录
        screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # 生成截图文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")
        
        # 抓取视频窗口的图像
        image = self.video_widget.grab()
        if image.save(screenshot_path):
            self.screenshotSaved.emit(screenshot_path)
            QMessageBox.information(self, "成功", f"截图已保存到: {screenshot_path}")
        else:
            QMessageBox.critical(self, "错误", "截图保存失败")
        
    def load_subtitle(self):
        # 加载字幕文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开字幕文件", "", "字幕文件 (*.srt);;所有文件 (*)"
        )
        
        if file_path:
            if self.subtitle_parser.load_srt(file_path):
                QMessageBox.information(self, "成功", "字幕加载成功")
            else:
                QMessageBox.critical(self, "错误", "字幕加载失败")
        
    def toggle_analysis(self):
        # 切换视频分析状态
        if self.video_analyzer.is_analyzing:
            # 停止分析
            results = self.video_analyzer.stop_analysis()
            self.analysis_timer.stop()
            self.analysis_btn.setText("开始分析")
            self.analysisCompleted.emit(results)
            
            # 显示分析结果
            motion_count = len(results.get('motion_events', []))
            QMessageBox.information(self, "分析完成", f"检测到 {motion_count} 个运动事件")
        else:
            # 开始分析
            if not self.playlist or self.current_video_index == -1:
                QMessageBox.warning(self, "警告", "请先加载视频")
                return
            
            self.video_analyzer.start_analysis(self.playlist[self.current_video_index])
            self.video_analyzer.analysis_results['duration'] = self.media_player.duration()
            self.analysis_timer.start()
            self.analysis_btn.setText("停止分析")
        
    def analyze_current_frame(self):
        # 分析当前帧
        if not self.video_analyzer.is_analyzing:
            return
        
        # 模拟帧分析，实际应用中可能需要使用OpenCV等库
        current_position = self.media_player.position()
        self.video_analyzer.analyze_frame(None, current_position)