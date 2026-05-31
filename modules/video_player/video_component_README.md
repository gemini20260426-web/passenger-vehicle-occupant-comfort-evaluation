# 视频播放器组件使用说明

本视频播放器组件基于PySide6开发，提供了完整的视频播放功能，包括播放控制、进度条、音量调节、全屏切换以及时间戳映射等特性。

## 文件结构

- `video_component.py`：核心视频播放器组件实现
- `video_ui.py`：演示如何使用该组件的UI应用
- `video_component_README.md`：本说明文件

## 功能特性

1. **基本播放控制**：播放、暂停、停止、快进/快退
2. **进度管理**：可视化进度条，支持拖动定位
3. **音量控制**：音量滑块和静音功能
4. **全屏切换**：支持窗口模式和全屏模式
5. **时间戳映射**：支持视频时间与数据时间戳的关联
6. **错误处理**：完善的播放错误提示
7. **键盘快捷键**：支持空格键播放/暂停，ESC键退出全屏

## 使用方法

### 1. 直接运行演示应用

```bash
python video_ui.py
```

### 2. 在自定义应用中集成视频组件

```python
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from video_component import VideoPlayerWidget

# 创建应用
app = QApplication(sys.argv)

# 创建主窗口
window = QWidget()
layout = QVBoxLayout(window)

# 创建并添加视频播放器组件
video_player = VideoPlayerWidget()
layout.addWidget(video_player)

# 显示窗口
window.show()

sys.exit(app.exec())
```

### 3. 信号与槽连接

```python
# 视频加载完成信号
video_player.videoLoaded.connect(self.on_video_loaded)

# 视频位置改变信号
video_player.videoPositionChanged.connect(self.on_position_changed)

# 自定义槽函数
def on_video_loaded(self, video_path):
    print(f"视频已加载: {video_path}")

def on_position_changed(self, position):
    # 处理视频位置变化
    pass
```

### 4. 时间戳映射功能

组件支持视频时间与数据时间戳的映射，方便视频与行车数据同步分析：

```python
# 获取当前视频位置对应的数据点
current_position = video_player.media_player.position()
data_point = video_player.get_nearest_data_point(current_position)
if data_point:
    print(f"当前视频位置对应的数据: {data_point}")
```

## 依赖项

- PySide6：用于UI和多媒体播放

## 注意事项

1. 视频播放器支持常见格式如MP4、AVI、MOV、MKV等
2. 时间戳映射功能需要视频文件同名的JSON数据文件
3. 全屏模式下按ESC键退出
4. 空格键可快速切换播放/暂停状态

## 扩展建议

1. 添加视频截图功能
2. 实现多视频切换播放
3. 增加视频滤镜效果
4. 集成视频分析功能
5. 添加字幕支持