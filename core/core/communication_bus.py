import logging
from queue import Queue
import time
from PySide6.QtCore import QObject, Signal
from threading import Thread

logger = logging.getLogger(__name__)

class CommunicationBus(QObject):
    """通信总线 - 面板间通信的核心"""
    
    data_source_updated = Signal(str, dict)
    sync_status_changed = Signal(str, dict)
    analysis_result_ready = Signal(str, dict)
    error_occurred = Signal(str, dict)
    performance_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.subscribers = {}
        self.message_queue = Queue(maxsize=1000)
        self.message_processor = MessageProcessor(self.message_queue)
        self.message_processor.start()
    
    _signal_map = None

    def _get_signal_map(self):
        if self._signal_map is None:
            self._signal_map = {
                'data_source': self.data_source_updated,
                'sync_status': self.sync_status_changed,
                'analysis_result': self.analysis_result_ready,
                'error': self.error_occurred,
                'performance': self.performance_updated,
            }
        return self._signal_map

    def publish(self, topic: str, message: dict):
        """发布消息到指定主题 — 同时发射 Qt 信号 + 通知回调订阅者"""
        try:
            self.message_queue.put({
                'topic': topic,
                'message': message,
                'timestamp': time.time()
            })

            signal = self._get_signal_map().get(topic)
            if signal is not None:
                try:
                    if topic == 'performance':
                        signal.emit(message)
                    else:
                        signal.emit(topic, message)
                except Exception as e:
                    logger.error("Qt 信号发射失败 [%s]: %s", topic, e)

            if topic in self.subscribers:
                for subscriber in self.subscribers[topic]:
                    try:
                        subscriber(message)
                    except Exception as e:
                        logger.error("回调订阅者通知失败: %s", e)

        except Exception as e:
            logger.error("发布消息失败: %s", e)

    def publish_status_change(self, status: str, data: dict):
        """发布状态变更消息（兼容接口）"""
        self.publish(status, data)
    
    def subscribe(self, topic: str, callback):
        """订阅指定主题"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

class MessageProcessor(Thread):
    """消息处理器线程"""
    
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self._stop_flag = False
    
    def run(self):
        """运行消息处理循环"""
        while not self._stop_flag:
            try:
                if not self.queue.empty():
                    message = self.queue.get()
                    # 处理消息（例如，额外日志或分发）
                    logger.debug(f"处理消息: {message['topic']} at {message['timestamp']}")
                    # 可以添加更多处理逻辑
                time.sleep(0.1)  # 避免高CPU占用
            except Exception as e:
                logger.error(f"消息处理失败: {e}")
    
    def stop(self):
        """停止处理器"""
        self._stop_flag = True
