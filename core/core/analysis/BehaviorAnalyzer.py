"""行为事件分发器"""
import time
import logging
from typing import Dict, Any, List
from collections import deque

# 使用try-except方式导入PySide6模块，避免IDE报错
try:
    from PySide6.QtCore import QObject, QThread, Slot, QMutex, QMutexLocker, Signal
except ImportError:
    # IDE静态检查时的替代方案
    class QObject:
        pass
    
    class QThread:
        pass
        
    class Signal:
        def __init__(self, *args):
            pass
    
    def Slot(*args):
        return lambda x: x
    
    class QMutex:
        pass
    
    class QMutexLocker:
        def __init__(self, mutex):
            pass

# 使用try-except方式导入本地模块，避免IDE报错
try:
    from .base_analyzer import BasicDrivingAnalyzer, BEHAVIOR_TYPES
except ImportError:
    BasicDrivingAnalyzer = object
    BEHAVIOR_TYPES = []

class DataProcessingThread(QThread):
    """数据处理线程，避免阻塞UI"""
    processed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, analyzer: BasicDrivingAnalyzer):
        super().__init__()
        self.analyzer = analyzer
        self.data_queue = []
        self.mutex = QMutex()
        self.running = True

    def add_data(self, data: Dict[str, Any]) -> None:
        """添加数据到处理队列"""
        with QMutexLocker(self.mutex):
            self.data_queue.append(data)

    def stop(self) -> None:
        """停止线程"""
        self.running = False
        try:
            self.processed.disconnect()
        except Exception:
            pass
        try:
            self.error_occurred.disconnect()
        except Exception:
            pass
        self.quit()
        if not self.wait(3000):
            self.terminate()
            self.wait()

    def run(self) -> None:
        """线程运行函数，处理队列中的数据"""
        while self.running and not self.isInterruptionRequested():
            data = None
            with QMutexLocker(self.mutex):
                if self.data_queue:
                    data = self.data_queue.pop(0)

            if data:
                try:
                    result = self.analyzer.analyze(data)
                    self.processed.emit(result)
                except Exception as e:
                    self.error_occurred.emit(f"数据处理错误: {str(e)}")

            self.msleep(10)

class BehaviorEventDispatcher(QObject):
    """基础分析结果事件分发器，转发行为事件到UI或其他模块"""
    # 定义信号类型
    behavior_updated = Signal(dict)  # 单个行为事件
    batch_behavior_updated = Signal(list)  # 批量行为事件
    analysis_status = Signal(str)  # 分析状态（进度/错误）
    data_received = Signal(int)  # 数据接收进度（已接收数量）
    processing_progress = Signal(int)  # 处理进度（百分比）
    evaluation_triggered = Signal(dict)  # 评测触发信号

    def __init__(self, analyzer: BasicDrivingAnalyzer = None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer or BasicDrivingAnalyzer()
        
        # 线程安全机制
        self.mutex = QMutex()
        self.data_count = 0
        self.processed_count = 0
        
        # 冷却机制 - 确保包含所有行为类型
        self.cooldowns = {}
        self.behavior_cooldowns = {}
        self.default_cooldown = 2.0  # 默认冷却时间（秒）
        
        # 最新行为结果缓存
        self._latest_behavior = None
        
        # 多通道数据缓存
        self.channel_data_buffers = {}  # channel_id -> deque
        self.buffer_size = 1000  # 每个通道的缓存大小
        
        # 评测相关配置
        self.evaluation_enabled = True  # 是否启用评测触发
        self.evaluation_metrics = []  # 要计算的指标列表
        self.evaluation_data_window = {'pre': 0.5, 'post': 1.5}  # 数据窗口
        self.evaluation_triggers = ['急刹车', '激进加速', '变道']  # 触发评测的行为
        self.evaluation_locations = []  # 要评测的位置（空表示所有位置）
        
        # 初始化所有行为类型的冷却时间
        try:
            from .base_analyzer import BEHAVIOR_TYPES
            for behavior in BEHAVIOR_TYPES:
                self.cooldowns[behavior] = 0.0
                self.behavior_cooldowns[behavior] = self.default_cooldown
        except ImportError:
            # 如果无法导入，使用默认行为类型
            default_behaviors = [
                "normal", "急刹车", "左转", "右转", "加速", "减速", 
                "匀速直线", "停车", "U型转弯", "蛇形驾驶", "急速变向", 
                "大半径转弯", "正常加速", "激进加速", "正常刹车", "激进刹车", "变道"
            ]
            for behavior in default_behaviors:
                self.cooldowns[behavior] = 0.0
                self.behavior_cooldowns[behavior] = self.default_cooldown
        
        # 创建并启动处理线程
        self.processing_thread = DataProcessingThread(self.analyzer)
        self.processing_thread.processed.connect(self._on_analysis_complete)
        self.processing_thread.error_occurred.connect(self._on_analysis_error)
        self.processing_thread.start()

    def set_cooldown(self, behavior: str, period: float) -> None:
        """设置特定行为的冷却时间"""
        with QMutexLocker(self.mutex):
            self.behavior_cooldowns[behavior] = period

    def get_cooldown(self, behavior: str) -> float:
        """获取行为的冷却时间，没有则使用默认值"""
        with QMutexLocker(self.mutex):
            return self.behavior_cooldowns.get(behavior, self.default_cooldown)

    def on_imu_data_received(self, data: Dict[str, Any]) -> None:
        """处理接收到的IMU数据，添加到处理队列"""
        try:
            with QMutexLocker(self.mutex):
                self.data_count += 1
                current_count = self.data_count
                
                # 缓存多通道数据
                self._cache_channel_data(data)
            
            self.data_received.emit(current_count)
            self.analysis_status.emit(f"接收数据: {current_count}条")
            
            # 将数据添加到处理线程的队列
            self.processing_thread.add_data(data)
            
        except Exception as e:
            error_msg = f"接收数据失败: {str(e)}"
            self.logger.error(error_msg)
            self.analysis_status.emit(error_msg)
    
    def _cache_channel_data(self, data: Dict[str, Any]) -> None:
        """
        缓存多通道数据
        
        Args:
            data: 输入数据，可能包含多通道信息
        """
        from collections import deque
        
        timestamp = data.get('timestamp', 0.0)
        
        # 检查是否包含多通道数据
        if 'multi_channel_data' in data:
            # 已经是多通道格式
            multi_channel = data['multi_channel_data']
            for channel_id, channel_data in multi_channel.items():
                if channel_id not in self.channel_data_buffers:
                    self.channel_data_buffers[channel_id] = deque(maxlen=self.buffer_size)
                
                self.channel_data_buffers[channel_id].append({
                    'timestamp': timestamp,
                    'ax': channel_data.get('ax', 0.0),
                    'ay': channel_data.get('ay', 0.0),
                    'az': channel_data.get('az', 0.0)
                })
        else:
            # 单通道数据，尝试从数据中提取通道ID
            channel_id = data.get('channel_id', 'imu1')
            
            if channel_id not in self.channel_data_buffers:
                self.channel_data_buffers[channel_id] = deque(maxlen=self.buffer_size)
            
            self.channel_data_buffers[channel_id].append({
                'timestamp': timestamp,
                'ax': data.get('ax', 0.0),
                'ay': data.get('ay', 0.0),
                'az': data.get('az', 0.0)
            })

    def get_latest_behavior(self) -> Dict[str, Any]:
        """获取最新的行为分析结果"""
        with QMutexLocker(self.mutex):
            if self._latest_behavior:
                return self._latest_behavior.copy()
            return None

    @Slot(dict)
    def _on_analysis_complete(self, result: Dict[str, Any]) -> None:
        """分析完成回调函数"""
        with QMutexLocker(self.mutex):
            self.processed_count += 1
            processed = self.processed_count
            total = self.data_count

        if total > 0:
            progress = int((processed / total) * 100)
            self.processing_progress.emit(progress)
            self.analysis_status.emit(f"处理进度: {processed}/{total} ({progress}%)")

        event = {
            "timestamp": result["timestamp"],
            "primary_behavior": result["behavior"],
            "behaviors": result.get("detected_all", [result["behavior"]]),
            "confidence": result["confidence"],
            "raw_data": result.get("raw_data", {})
        }
        self._latest_behavior = event
        self.behavior_updated.emit(event)
        
        # 检查是否需要触发评测
        if self.evaluation_enabled:
            self._check_evaluation_trigger(event)
    
    def _check_evaluation_trigger(self, event: Dict[str, Any]) -> None:
        """检查是否需要触发评测"""
        try:
            behavior = event.get("primary_behavior", "")
            
            # 检查行为是否在触发列表中
            if behavior in self.evaluation_triggers:
                # 收集多通道数据
                multi_channel_data = self._collect_multi_channel_data(event.get("timestamp", time.time()))
                
                trigger = {
                    "event_id": f"eval_{int(time.time() * 1000)}",
                    "event_type": behavior,
                    "source_behavior": behavior,
                    "timestamp": event.get("timestamp", time.time()),
                    "metrics": self.evaluation_metrics,
                    "raw_data": event.get("raw_data", {}),
                    "multi_channel_data": multi_channel_data,
                    "data_window": self.evaluation_data_window,
                    "locations": self.evaluation_locations,
                    "group_tag": "both"
                }
                
                self.evaluation_triggered.emit(trigger)
                self.logger.info(f"触发座椅评测: {behavior}, 通道数: {len(multi_channel_data)}")
                
        except Exception as e:
            self.logger.error(f"检查评测触发失败: {e}")
    
    def _collect_multi_channel_data(self, center_timestamp: float) -> Dict[str, Dict[str, Any]]:
        """
        收集指定时间窗口内的多通道数据
        
        Args:
            center_timestamp: 中心时间戳
        
        Returns:
            多通道数据字典
        """
        multi_channel_data = {}
        
        pre_seconds = self.evaluation_data_window.get('pre', 0.5)
        post_seconds = self.evaluation_data_window.get('post', 1.5)
        
        for channel_id, buffer in self.channel_data_buffers.items():
            if not buffer:
                continue
            
            # 筛选时间窗口内的数据
            ax_list = []
            ay_list = []
            az_list = []
            
            for data_point in buffer:
                dp_time = data_point.get('timestamp', 0.0)
                if (center_timestamp - pre_seconds) <= dp_time <= (center_timestamp + post_seconds):
                    ax_list.append(data_point.get('ax', 0.0))
                    ay_list.append(data_point.get('ay', 0.0))
                    az_list.append(data_point.get('az', 0.0))
            
            if ax_list:
                multi_channel_data[channel_id] = {
                    'ax': ax_list,
                    'ay': ay_list,
                    'az': az_list
                }
        
        return multi_channel_data
    
    def set_evaluation_metrics(self, metrics: list) -> None:
        """设置评测指标列表"""
        with QMutexLocker(self.mutex):
            self.evaluation_metrics = metrics
    
    def set_evaluation_triggers(self, behaviors: list) -> None:
        """设置触发评测的行为列表"""
        with QMutexLocker(self.mutex):
            self.evaluation_triggers = behaviors
    
    def set_evaluation_enabled(self, enabled: bool) -> None:
        """设置是否启用评测触发"""
        with QMutexLocker(self.mutex):
            self.evaluation_enabled = enabled
    
    def set_evaluation_locations(self, locations: list) -> None:
        """设置要评测的位置列表"""
        with QMutexLocker(self.mutex):
            self.evaluation_locations = locations
    
    def clear_channel_buffers(self) -> None:
        """清空通道数据缓冲区"""
        with QMutexLocker(self.mutex):
            self.channel_data_buffers.clear()
            self.logger.info("通道数据缓冲区已清空")

    @Slot(str)
    def _on_analysis_error(self, error: str) -> None:
        """分析错误回调函数"""
        self.logger.error(error)
        self.analysis_status.emit(error)

    def batch_analyze(self, data_list: List[Dict[str, Any]]) -> None:
        """批量分析数据并转发结果"""
        total = len(data_list)
        if total == 0:
            self.analysis_status.emit("批量分析: 无数据可分析")
            return
            
        self.analysis_status.emit(f"开始批量分析（{total}条数据）")
        results = []
        
        for i, data in enumerate(data_list):
            try:
                result = self.analyzer.analyze(data)
                results.append(result)
                
                # 每10条更新一次进度
                if i % 10 == 0 or i == total - 1:
                    progress = int((i + 1) / total * 100)
                    self.processing_progress.emit(progress)
                    self.analysis_status.emit(f"批量分析中: {i+1}/{total} ({progress}%)")
                    
            except Exception as e:
                self.logger.warning(f"第{i}条数据分析失败: {e}")
                self.analysis_status.emit(f"批量分析警告: 第{i}条数据处理失败")

        self.batch_behavior_updated.emit(results)
        self.analysis_status.emit(f"批量分析完成: 成功处理{len(results)}/{total}条数据")

    def shutdown(self) -> None:
        """关闭分发器，停止处理线程"""
        self.processing_thread.stop()
        self.logger.info("行为事件分发器已关闭")
