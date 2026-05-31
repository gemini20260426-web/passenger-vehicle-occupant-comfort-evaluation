import os
import threading
import time
import logging
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal

# 可选导入 chardet
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

# 移除metaclass=abc.ABCMeta，避免与QObject的元类冲突
class DataReader(QObject):
    """数据读取器抽象基类"""
    
    # 定义信号
    data_received = Signal(dict)  # 数据接收信号
    progress_updated = Signal(float)  # 进度更新信号
    reading_completed = Signal()  # 读取完成信号
    error_occurred = Signal(str)  # 错误发生信号
    log_message = Signal(str)  # 日志消息信号

    def __init__(self):
        super().__init__()
        
        # 回调函数
        self.callback = None
        self.progress_callback = None
        self.complete_callback = None
        self.log_callback = None

    def set_callback(self, callback: Callable[[dict], None]):
        """设置数据回调函数"""
        self.callback = callback

    def set_progress_callback(self, callback: Callable[[float], None]):
        """设置进度回调函数"""
        self.progress_callback = callback

    def set_complete_callback(self, callback: Callable[[], None]):
        """设置完成回调函数"""
        self.complete_callback = callback

    def set_logger(self, log_func: Callable[[str], None]):
        """设置日志函数"""
        self.log_callback = log_func

    def log(self, message: str):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            logging.info(message)

    def start(self, callback: Optional[Callable[[dict], None]] = None):
        """开始读取数据（抽象方法，需要子类实现）"""
        raise NotImplementedError("子类必须实现start方法")

    def stop(self):
        """停止读取数据（抽象方法，需要子类实现）"""
        raise NotImplementedError("子类必须实现stop方法")


class FileDataReader(DataReader):
    """文件数据读取器，用于读取离线数据文件（块读取 + 多包支持）"""

    def __init__(self, file_path: str, enable_normalization: bool = True):
        super().__init__()
        self.file_path = file_path
        self.running = False
        self.paused = False
        self.thread = None
        self.enable_normalization = enable_normalization
        self.normalized_file_path = None

        from .data_parser import IMUDataParser
        self.imu_parser = IMUDataParser()

    def set_logger(self, log_func):
        self.log_callback = log_func

    def set_data_callback(self, callback):
        self.callback = callback

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def set_complete_callback(self, callback):
        self.complete_callback = callback

    def start(self, callback):
        if self.running and not self.paused:
            if self.log_callback:
                self.log_callback("文件读取已在运行中")
            return False
        self.running = True
        self.paused = False
        self.callback = callback
        try:
            self.thread = threading.Thread(target=self._read_file, daemon=True)
            self.thread.start()
            if self.log_callback:
                self.log_callback(f"开始读取文件: {self.file_path}")
            return True
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"启动文件读取线程失败: {e}")
            self.running = False
            return False

    def pause(self):
        self.paused = not self.paused
        return self.paused

    def stop(self):
        self.running = False
        self.paused = False
        if self.thread and self.thread.is_alive() and self.thread.ident != threading.current_thread().ident:
            self.thread.join(timeout=1)

    def _read_file(self):
        try:
            encoding = self._detect_file_encoding()
            file_size = os.path.getsize(self.file_path)
            if self.log_callback:
                self.log_callback(f"文件大小: {file_size} 字节, 编码: {encoding}")

            bytes_read = 0
            line_count = 0
            processed_packets = 0
            last_progress_update = 0
            progress_update_interval = max(1, file_size // 100)

            buffer = ""
            packet_batch = []
            BATCH_SIZE = 200

            def _flush_batch():
                nonlocal processed_packets
                if packet_batch:
                    for p in packet_batch:
                        self.data_received.emit(p)
                    processed_packets += len(packet_batch)
                    packet_batch.clear()

            with open(self.file_path, 'r', encoding=encoding, errors='replace') as f:
                while self.running:
                    while self.paused and self.running:
                        time.sleep(0.1)

                    if not self.running:
                        break

                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        if buffer:
                            packets = self.imu_parser._parse_log_line(buffer)
                            packet_batch.extend(packets)
                        _flush_batch()
                        break

                    bytes_read += len(chunk)
                    buffer += chunk
                    lines = buffer.split('\n')

                    for line in lines[:-1]:
                        if not self.running:
                            break
                        if not line.strip():
                            continue
                        line_count += 1
                        packets = self.imu_parser._parse_log_line(line)
                        packet_batch.extend(packets)
                        if len(packet_batch) >= BATCH_SIZE:
                            _flush_batch()

                    buffer = lines[-1]

                    if bytes_read - last_progress_update >= progress_update_interval:
                        progress = min(100, (bytes_read / file_size) * 100)
                        if self.progress_callback:
                            self.progress_callback(progress)
                        last_progress_update = bytes_read

                _flush_batch()

                if self.running:
                    if self.log_callback:
                        self.log_callback(f"[INFO] 文件读取完成，总行数: {line_count}, 解析数据包: {processed_packets}")
                    if self.progress_callback:
                        self.progress_callback(100)

                    if self.enable_normalization:
                        self._run_normalization()

                    if self.complete_callback:
                        self.complete_callback()

        except Exception as e:
            error_msg = f"文件读取错误: {e}"
            if self.log_callback:
                self.log_callback(error_msg)
            if self.complete_callback:
                self.complete_callback()
        finally:
            self.running = False

    def _detect_file_encoding(self) -> str:
        try:
            with open(self.file_path, 'rb') as f:
                raw_data = f.read(4096)
                if HAS_CHARDET:
                    result = chardet.detect(raw_data)
                    encoding = result.get('encoding', 'utf-8')
                    if encoding and encoding.lower() in ['gb2312', 'gbk']:
                        encoding = 'gb18030'
                    elif encoding and encoding.lower() == 'ascii':
                        encoding = 'utf-8'
                else:
                    encoding = 'utf-8'
                return encoding
        except Exception:
            return 'utf-8'

    def _run_normalization(self):
        try:
            from .data_normalizer import DataNormalizer
            normalizer = DataNormalizer()
            filepath, written, stats = normalizer.parse_and_normalize(self.file_path)
            if filepath:
                self.normalized_file_path = filepath
                if self.log_callback:
                    self.log_callback(
                        f"[INFO] 数据标准化完成: {written} 条记录 → {filepath}"
                    )
                    self.log_callback(
                        f"[INFO] 格式统计: 12字段={stats.get('twelve_field', 0)}, "
                        f"8字段={stats.get('eight_field', 0)}, "
                        f"估算gz={stats.get('estimated_gz', 0)}"
                    )
            else:
                if self.log_callback:
                    self.log_callback("[WARN] 数据标准化失败，无输出文件")
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"[ERROR] 数据标准化异常: {e}")

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass




class MQTTDataReader(QObject):
    """MQTT数据读取器"""
    # 定义信号
    data_received = Signal(dict)
    error_occurred = Signal(str)
    connected = Signal()
    disconnected = Signal()
    
    def __init__(self, host, port, username, password, topic):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.client = None
        self.is_connected = False
        self.running = False
        self.imu_parser = IMUDataParser()
        self.callback = None
        self.log_callback = None
        self.connect_callback = None
        # 内部数据读取器实现
        self.data_reader_impl = self

    def log(self, message):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)

    def set_logger(self, log_func):
        """设置日志回调函数"""
        self.log_callback = log_func

    def set_connect_callback(self, callback):
        """设置连接状态回调"""
        self.connect_callback = callback

    def start(self, callback=None):
        """开始读取MQTT数据"""
        if self.running:
            return False
            
        self.running = True
        if callback:
            self.callback = callback
        
        try:
            self.client = mqtt.Client()
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            self.client.connect_async(self.host, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            error_msg = f"MQTT启动失败: {str(e)}"
            self.log(error_msg)
            self.error_occurred.emit(error_msg)
            self.running = False
            return False

    def stop(self):
        """停止读取MQTT数据"""
        if not self.running:
            return
            
        self.running = False
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.client = None
                self.log("MQTT客户端已停止")
        except Exception as e:
            error_msg = f"停止MQTT客户端时出错: {e}"
            self.log(error_msg)
            self.error_occurred.emit(error_msg)

    def set_logger(self, log_func):
        """设置日志回调函数"""
        self.log_callback = log_func

    def log(self, message):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            self.is_connected = True
            self.log(f"MQTT连接成功: {self.host}:{self.port}")
            client.subscribe(self.topic)
            self.log(f"已订阅主题: {self.topic}")
            # 发射连接成功信号
            self.connected.emit()
            if self.connect_callback:
                self.connect_callback(True, "MQTT连接成功")
        else:
            self.is_connected = False
            error_msg = f"MQTT连接失败，错误代码: {rc}"
            self.log(error_msg)
            # 发射错误信号
            self.error_occurred.emit(error_msg)
            if self.connect_callback:
                self.connect_callback(False, error_msg)

    def _on_message(self, client, userdata, msg):
        """MQTT消息回调"""
        try:
            payload = msg.payload.decode('utf-8')
            # 尝试解析为JSON
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    # 确保有时间戳
                    if 'timestamp' not in data:
                        data['timestamp'] = time.time()
                    # 发射数据接收信号
                    self.data_received.emit(data)
                    if self.callback:
                        self.callback(data)
            except json.JSONDecodeError:
                # 如果不是JSON，尝试使用IMU解析器解析
                parsed_data = self.imu_parser.parse_line(payload)
                if parsed_data:
                    # 发射数据接收信号
                    self.data_received.emit(parsed_data)
                    if self.callback:
                        self.callback(parsed_data)
        except Exception as e:
            error_msg = f"处理MQTT消息时出错: {e}"
            self.log(error_msg)
            # 发射错误信号
            self.error_occurred.emit(error_msg)

    def _on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        self.is_connected = False
        # 发射断开连接信号
        self.disconnected.emit()
        if rc != 0:
            error_msg = "MQTT意外断开连接"
            self.log(error_msg)
            # 发射错误信号
            self.error_occurred.emit(error_msg)
        else:
            self.log("MQTT连接已断开")

    def set_connect_callback(self, callback):
        """设置连接状态回调"""
        self.connect_callback = callback

    def start(self, callback=None):
        """开始读取MQTT数据"""
        if self.running:
            return False
            
        self.running = True
        if callback:
            self.callback = callback
        
        try:
            self.client = mqtt.Client()
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            error_msg = f"MQTT启动失败: {str(e)}"
            self.log(error_msg)
            return False

    def stop(self):
        """停止读取MQTT数据"""
        self.running = False
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                self.log(f"关闭MQTT客户端时出错: {e}")
        self.is_connected = False