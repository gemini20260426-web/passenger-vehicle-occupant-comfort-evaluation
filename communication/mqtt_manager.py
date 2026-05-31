#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import time
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker, QThread
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

# MQTT连接状态常量
MQTT_DISCONNECTED = 0
MQTT_CONNECTING = 1
MQTT_CONNECTED = 2

class MQTTManager(QObject):
    """MQTT管理类，负责处理MQTT连接、订阅和消息处理"""
    
    # 定义信号 - 严格按照文档定义
    data_received = Signal(str, dict)  # 数据类型, 解析后的数据
    sig_connection_status_changed = Signal(bool, str)  # 连接状态, 状态描述
    sig_error_occurred = Signal(str, str)  # 客户端ID, 错误信息
    sig_message_received = Signal(str, str)  # 主题, 消息内容
    
    def __init__(self, client_id=None, broker=None, port=None, topics=None, username=None, password=None, tls=False):
        super().__init__()
        self.mqtt_clients = {}  # 存储客户端配置和状态信息
        self.mqtt_client_instances = {}  # 存储实际的paho-mqtt客户端实例
        self.logger = logging.getLogger(__name__)
        self.mutex = QMutex()
        
        # 初始化线程相关属性
        self.worker_thread = None
        self._should_stop = False  # 线程停止标志
        
        # 初始化客户端属性
        self.client = None
        self.is_connected = False
        self.broker = broker or 'localhost'
        self.port = port or 1883
        self.username = username
        self.password = password
        self.topics = topics or ['vehicle/data']  # 支持多主题订阅，默认主题
        self.client_id = client_id or f"vehicle_monitor_{int(time.time())}"
        self.tls = tls
        
        # 重连相关配置
        self.auto_reconnect = True  # 是否自动重连
        self.reconnect_interval = 5  # 重连间隔(秒)
        self.max_reconnect_attempts = 0  # 最大重连尝试次数，0表示无限尝试
        self.reconnect_count = 0  # 当前重连次数
        
    def get_mqtt_config(self):
        """获取MQTT配置"""
        return {
            'host': self.broker,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'client_id': self.client_id,
            'topics': self.topics,
            'tls': self.tls,
            'auto_reconnect': self.auto_reconnect,
            'reconnect_interval': self.reconnect_interval,
            'max_reconnect_attempts': self.max_reconnect_attempts
        }
    
    def get_all_configs(self):
        """获取所有MQTT客户端配置"""
        configs = {}
        with QMutexLocker(self.mutex):
            for client_id, client_info in self.mqtt_clients.items():
                configs[client_id] = client_info.get('config', {})
        return configs
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT日志回调函数"""
        self.logger.debug(f"MQTT日志: {buf}")
    
    def connect_mqtt(self, broker=None, port=None, client_id=None, topics=None, username=None, password=None):
        """连接到MQTT服务器
        
        Args:
            broker (str, optional): MQTT服务器地址
            port (int, optional): MQTT服务器端口
            client_id (str, optional): 客户端ID
            topics (list, optional): 订阅的主题列表
            username (str, optional): 用户名
            password (str, optional): 密码
        """
        try:
            # 更新配置
            if broker is not None:
                self.broker = broker
            if port is not None:
                self.port = port
            if client_id is not None:
                self.client_id = client_id
            if topics is not None:
                self.topics = topics if isinstance(topics, list) else [topics]
            if username is not None:
                self.username = username
            if password is not None:
                self.password = password
            
            self.logger.info(f"开始连接MQTT服务器: {self.broker}:{self.port}, client_id: {self.client_id}")
            
            # 验证参数类型
            if not isinstance(self.broker, str):
                raise TypeError(f"broker必须是字符串类型，当前类型: {type(self.broker)}")
            if not isinstance(self.port, int):
                raise TypeError(f"port必须是整数类型，当前类型: {type(self.port)}")
            if not isinstance(self.client_id, str):
                raise TypeError(f"client_id必须是字符串类型，当前类型: {type(self.client_id)}")
            
            # 创建MQTT客户端
            self.client = mqtt.Client(client_id=self.client_id)
            
            # 设置认证信息
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            # 设置TLS
            if self.tls:
                self.client.tls_set()
            
            # 设置回调函数
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_log = self._on_log
            
            # 连接服务器
            self.client.connect(self.broker, self.port, 60)
            
            # 启动网络循环
            self.client.loop_start()
            
            self.logger.info("MQTT客户端连接请求已发送")
            return True
            
        except Exception as e:
            self.logger.error(f"连接MQTT服务器时出错: {e}")
            self.sig_error_occurred.emit(self.client_id, f"连接错误: {str(e)}")
            return False
    
    def disconnect(self):
        """断开MQTT连接并释放所有相关资源"""
        try:
            # 重置重连计数
            self.reconnect_count = 0
            
            # 停止工作线程
            self.stop_worker_thread()
            
            if self.client:
                # 停止网络循环
                try:
                    self.client.loop_stop()
                    self.logger.debug("MQTT网络循环已停止")
                except Exception as loop_err:
                    self.logger.error(f"停止MQTT网络循环时出错: {str(loop_err)}")
                
                # 断开连接
                try:
                    self.client.disconnect()
                    self.logger.debug("MQTT连接已断开")
                except Exception as disconnect_err:
                    self.logger.error(f"断开MQTT连接时出错: {str(disconnect_err)}")
                
                # 清理客户端资源
                self.client = None
                self.is_connected = False
                
                self.logger.info("已断开MQTT连接并释放资源")
                self.sig_connection_status_changed.emit(False, "MQTT连接已断开")
            else:
                self.logger.info("没有活动的MQTT连接需要断开")
                self.is_connected = False
        except Exception as e:
            self.logger.error(f"断开MQTT连接过程中发生错误: {str(e)}", exc_info=True)
            self.sig_error_occurred.emit(self.client_id, f"断开连接时出错: {str(e)}")
            # 确保状态被更新
            self.is_connected = False
            self.client = None

    def subscribe(self, topic):
        """
        订阅指定的MQTT主题
        
        Args:
            topic (str): 要订阅的主题
        
        Returns:
            bool: 订阅是否成功
        """
        try:
            if not self.client or not self.is_connected:
                self.logger.error("无法订阅主题: 未连接到MQTT服务器")
                return False
            
            if not isinstance(topic, str):
                raise TypeError(f"topic 必须是字符串类型，当前类型: {type(topic)}")
            
            result, mid = self.client.subscribe(topic)
            if result != mqtt.MQTT_ERR_SUCCESS:
                self.logger.warning(f"订阅主题失败: {topic}，错误码: {result}")
                return False
            else:
                self.logger.info(f"已订阅主题: {topic}")
                # 如果是新主题，添加到主题列表
                if topic not in self.topics:
                    self.topics.append(topic)
                return True
        except Exception as e:
            self.logger.error(f"订阅主题时发生错误: {str(e)}")
            return False

    def unsubscribe(self, topic):
        """
        取消订阅指定的MQTT主题
        
        Args:
            topic (str): 要取消订阅的主题
        
        Returns:
            bool: 取消订阅是否成功
        """
        try:
            if not self.client or not self.is_connected:
                self.logger.error("无法取消订阅主题: 未连接到MQTT服务器")
                return False
            
            if not isinstance(topic, str):
                raise TypeError(f"topic 必须是字符串类型，当前类型: {type(topic)}")
            
            if topic not in self.topics:
                self.logger.warning(f"未订阅主题: {topic}，无法取消订阅")
                return False
            
            result, mid = self.client.unsubscribe(topic)
            if result != mqtt.MQTT_ERR_SUCCESS:
                self.logger.warning(f"取消订阅主题失败: {topic}，错误码: {result}")
                return False
            else:
                self.logger.info(f"已取消订阅主题: {topic}")
                # 从主题列表中移除
                self.topics.remove(topic)
                return True
        except Exception as e:
            self.logger.error(f"取消订阅主题时发生错误: {str(e)}")
            return False

    def subscribe_multiple(self, topics):
        """
        订阅多个MQTT主题
        
        Args:
            topics (list): 要订阅的主题列表
        
        Returns:
            dict: 每个主题的订阅结果
        """
        results = {}
        for topic in topics:
            results[topic] = self.subscribe(topic)
        return results
    
    def disconnect_all(self):
        """断开所有MQTT连接"""
        self.disconnect()
        self.logger.info("已断开所有MQTT连接")
        
    def reconnect(self):
        """重新连接MQTT服务器"""
        try:
            self.logger.info("尝试重新连接MQTT服务器...")
            # 先断开现有连接
            self.disconnect_all()
            # 重新连接
            self.connect_mqtt(
                self.broker,
                self.port,
                self.username,
                self.password,
                self.tls
            )
            self.logger.info("MQTT重新连接成功")
        except Exception as e:
            self.logger.error(f"MQTT重新连接失败: {e}")
            
    def shutdown(self):
        """关闭MQTT管理器，确保所有资源被释放"""
        try:
            self.logger.info("正在关闭MQTT管理器...")
            # 设置停止标志
            self._should_stop = True
            # 断开所有连接
            self.disconnect_all()
            # 停止工作线程
            self.stop_worker_thread()
            self.logger.info("MQTT管理器已成功关闭")
        except Exception as e:
            self.logger.error(f"关闭MQTT管理器时发生错误: {str(e)}")
        
    def move_to_thread(self, thread):
        """将MQTTManager移动到指定线程"""
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        
        self.worker_thread = thread
        super().moveToThread(thread)
        
    def start_worker_thread(self):
        """启动工作线程"""
        if not self.worker_thread:
            self.worker_thread = QThread()
            self.moveToThread(self.worker_thread)
            self.worker_thread.start()
            
    def stop_worker_thread(self):
        """停止工作线程"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.logger.info("正在停止MQTT工作线程...")
            # 设置停止标志
            self._should_stop = True
            # 取消任何活跃的重连定时器
            if self.reconnect_timer and self.reconnect_timer.isActive():
                self.reconnect_timer.stop()
                self.reconnect_timer = None
                self.logger.info("已取消活跃的重连定时器")
            # 先尝试正常退出
            self.worker_thread.quit()
            # 增加等待时间至10秒，确保线程有足够时间处理退出
            wait_time = 0
            max_wait = 10000  # 10秒
            wait_interval = 500  # 0.5秒
            while self.worker_thread.isRunning() and wait_time < max_wait:
                self.logger.debug(f"等待MQTT工作线程停止... ({wait_time/1000:.1f}s)")
                self.worker_thread.wait(wait_interval)
                wait_time += wait_interval

            if self.worker_thread.isRunning():
                self.logger.warning("MQTT工作线程未在指定时间内正常停止，强制终止...")
                self.worker_thread.terminate()
                self.worker_thread.wait(2000)  # 再等待2秒
                if self.worker_thread.isRunning():
                    self.logger.error("无法终止MQTT工作线程")
                else:
                    self.logger.info("MQTT工作线程已通过强制终止停止")
            else:
                self.logger.info("MQTT工作线程已成功停止")
            self.worker_thread = None
            # 重置停止标志
            self._should_stop = False
    
    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            # 断开MQTT连接
            self.disconnect_all()
            # 停止工作线程
            self.stop_worker_thread()
        except Exception as e:
            self.logger.error(f"MQTTManager析构时出错: {e}")

    def _on_connect(self, client, userdata, flags, reason_code):
        """连接回调"""
        try:
            client_id = userdata or self.client_id
            self.is_connected = (reason_code == 0)
            
            if reason_code == 0:
                self.logger.info(f"客户端 {client_id} 连接成功")
                self.sig_connection_status_changed.emit(True, f"客户端 {client_id} 连接成功")
            else:
                error_msg = f"客户端 {client_id} 连接失败，错误码: {reason_code}"
                self.logger.error(error_msg)
                self.sig_error_occurred.emit(client_id, error_msg)
        except Exception as e:
            self.logger.error(f"处理连接回调时出错: {str(e)}")
            self.sig_error_occurred.emit(self.client_id, f"处理连接回调时出错: {str(e)}")

    def _on_disconnect(self, client, userdata, reason_code):
        """断开连接回调"""
        try:
            client_id = userdata or self.client_id
            self.is_connected = False
            
            if reason_code == 0:
                self.logger.info(f"客户端 {client_id} 正常断开连接")
                self.sig_connection_status_changed.emit(False, f"客户端 {client_id} 正常断开连接")
                # 正常断开连接时不自动重连
                self.reconnect_count = 0
            else:
                error_msg = f"客户端 {client_id} 异常断开连接，错误码: {reason_code}"
                self.logger.error(error_msg)
                self.sig_connection_status_changed.emit(False, error_msg)
                
                # 异常断开连接时自动重连
                if self.auto_reconnect:
                    self._schedule_reconnect()
        except Exception as e:
            self.logger.error(f"处理断开连接回调时出错: {str(e)}")
            self.sig_error_occurred.emit(self.client_id, f"处理断开连接回调时出错: {str(e)}")

    def _schedule_reconnect(self):
        """安排重连"""
        # 取消任何现有的重连定时器
        if self.reconnect_timer and self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
            self.reconnect_timer = None

        if self.max_reconnect_attempts > 0 and self.reconnect_count >= self.max_reconnect_attempts:
            self.logger.error(f"已达到最大重连尝试次数 {self.max_reconnect_attempts}，停止重连")
            return
        
        self.reconnect_count += 1
        delay = self.reconnect_interval * self.reconnect_count  # 指数退避
        self.logger.info(f"尝试第 {self.reconnect_count} 次重连，延迟 {delay} 秒")
        
        # 使用定时器安排重连
        from PySide6.QtCore import QTimer
        self.reconnect_timer = QTimer()
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self._reconnect)
        self.reconnect_timer.start(delay * 1000)

    def _reconnect(self):
        """执行重连"""
        # 检查是否应该停止
        if self._should_stop:
            self.logger.info("重连操作已取消，因为线程正在停止")
            return

        try:
            self.logger.info(f"尝试重连到MQTT服务器: {self.broker}:{self.port}")
            if self.connect_mqtt(self.broker, self.port, self.username, self.password, self.tls):
                self.reconnect_count = 0  # 重连成功，重置计数
                # 重连成功后重新订阅所有主题
                if self.topics:
                    for topic in self.topics:
                        self.subscribe(topic)
        except Exception as e:
            self.logger.error(f"重连失败: {str(e)}")
            # 如果不应该停止，则安排下一次重连
            if not self._should_stop:
                self._schedule_reconnect()

    def _on_message(self, client, userdata, msg):
        """消息接收回调"""
        try:
            client_id = userdata or self.client_id
            # 解析消息
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            self.logger.debug(f"客户端 {client_id} 收到消息: {topic} -> {payload}")
            
            # 发出原始消息信号
            self.sig_message_received.emit(topic, payload)
            
            # 尝试解析JSON数据
            try:
                data = json.loads(payload)
                # 从主题中提取数据类型
                if 'imu' in topic.lower():
                    data_type = 'imu'
                elif 'cnap' in topic.lower():
                    data_type = 'cnap'
                else:
                    data_type = 'unknown'
                # 发送解析后的数据
                self.logger.debug(f"发射data_received信号: data_type={data_type}, data类型={type(data)}")
                self.data_received.emit(data_type, data)
            except json.JSONDecodeError:
                # 如果不是JSON格式，发送原始数据
                data = {
                    'topic': topic,
                    'payload': payload,
                    'timestamp': time.time()
                }
                # 从主题中提取数据类型
                if 'imu' in topic.lower():
                    data_type = 'imu'
                elif 'cnap' in topic.lower():
                    data_type = 'cnap'
                else:
                    data_type = 'unknown'
                self.data_received.emit(data_type, data)
                
        except Exception as e:
            self.logger.error(f"处理消息回调时出错: {str(e)}")
            self.sig_error_occurred.emit(self.client_id, f"处理消息回调时出错: {str(e)}")
    
