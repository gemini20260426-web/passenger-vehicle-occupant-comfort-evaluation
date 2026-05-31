"""
MQTT客户端模块（已弃用）
此模块已合并到mqtt_manager.py中，为保持向后兼容性而保留此文件
"""

import logging
from PySide6.QtCore import QObject, Signal

# 为保持向后兼容性，保留MQTTClient类名
# 实际实现已合并到MQTTManager中
class MQTTClient(QObject):
    """已弃用的MQTT客户端类，为保持向后兼容性而保留"""
    
    # 保留信号定义以保持向后兼容性
    connection_status_changed = Signal(bool)
    data_processed = Signal(str, dict)
    message_received = Signal(str, str)
    error_occurred = Signal(str, str)
    status_updated = Signal(str, bool, str)

    def __init__(self, client_id, config_manager=None):
        super().__init__()
        self.logger = logging.getLogger("MQTTClient")
        self.logger.warning("MQTTClient类已弃用，请使用MQTTManager替代")
        
    def start(self, config=None):
        """已弃用的方法"""
        self.logger.warning("MQTTClient.start()已弃用，请使用MQTTManager.connect()替代")
        return False
        
    def stop(self):
        """已弃用的方法"""
        self.logger.warning("MQTTClient.stop()已弃用，请使用MQTTManager.disconnect()替代")
        
    def publish(self, topic, payload):
        """已弃用的方法"""
        self.logger.warning("MQTTClient.publish()已弃用，请使用MQTTManager.publish()替代")