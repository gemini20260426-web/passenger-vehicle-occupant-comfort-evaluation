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
                
            self.data_received.emit(current_count)
            self.analysis_status.emit(f"接收数据: {current_count}条")
            
            # 将数据添加到处理线程的队列
            self.processing_thread.add_data(data)
            
        except Exception as e:
            error_msg = f"接收数据失败: {str(e)}"
            self.logger.error(error_msg)
            self.analysis_status.emit(error_msg)

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
