#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.components.video_player import VideoPlayerWidget


class VideoPlayerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 设置窗口标题和大小
        self.setWindowTitle("视频播放器")
        self.resize(1024, 768)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建视频播放器组件
        self.video_player = VideoPlayerWidget(self)
        main_layout.addWidget(self.video_player)

        # 创建字幕显示标签
        self.subtitle_label = QLabel("")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setFont(QFont("SimHei", 14))
        self.subtitle_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 0.5); padding: 5px;")
        self.subtitle_label.setWordWrap(True)
        main_layout.addWidget(self.subtitle_label)

        # 连接字幕更新信号
        self.video_player.subtitleUpdated.connect(self.update_subtitle)
        self.video_player.screenshotSaved.connect(self.on_screenshot_saved)
        self.video_player.analysisCompleted.connect(self.on_analysis_completed)

        # 创建控制按钮布局
        control_layout = QVBoxLayout()

        # 全屏按钮
        self.fullscreen_btn = QPushButton("全屏显示")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        control_layout.addWidget(self.fullscreen_btn)

        # 添加控制布局到主布局
        main_layout.addLayout(control_layout)

        # 连接视频加载信号
        self.video_player.videoLoaded.connect(self.on_video_loaded)
        self.video_player.videoPositionChanged.connect(self.on_position_changed)

    def toggle_fullscreen(self):
        # 切换全屏状态
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("全屏显示")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("退出全屏")

    def on_video_loaded(self, video_path):
        # 视频加载完成回调
        self.setWindowTitle(f"视频播放器 - {video_path}")

    def on_position_changed(self, position):
        # 视频位置改变回调
        # 在这里可以添加与视频位置相关的逻辑
        pass

    def update_subtitle(self, subtitle_text):
        # 更新字幕显示
        self.subtitle_label.setText(subtitle_text)

    def on_screenshot_saved(self, file_path):
        # 截图保存提示
        self.statusBar().showMessage(f"截图已保存至: {file_path}", 3000)

    def on_analysis_completed(self, analysis_result):
        # 处理分析结果
        motion_detected = analysis_result.get('motion_detected', False)
        brightness = analysis_result.get('brightness', 0)
        message = f"分析结果: 运动检测={motion_detected}, 亮度={brightness}"
        self.statusBar().showMessage(message, 5000)

    def keyPressEvent(self, event):
        # 键盘事件处理
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("全屏显示")
        elif event.key() == Qt.Key_Space:
            self.video_player.play_pause()
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoPlayerUI()
    window.show()
    sys.exit(app.exec())