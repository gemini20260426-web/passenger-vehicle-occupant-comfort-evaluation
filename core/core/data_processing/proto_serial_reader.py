#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
协议串口数据读取器
支持特定协议格式的串口数据读取和解析
"""

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    serial = None
import threading
import time
import logging
from collections import deque
import queue
import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from PySide6.QtCore import QObject, Signal, QTimer

# 修复导入路径
from .data_parser import IMUDataParser

logger = logging.getLogger(__name__)

class ProtoSerialDataReader(QObject):
    """协议串口数据读取器"""
    
    # 定义信号
    data_received_signal = Signal(dict)  # 数据接收信号
    error_occurred_signal = Signal(str)  # 错误发生信号
    connected_signal = Signal()  # 连接成功信号
    disconnected_signal = Signal(str)  # 断开连接信号
    connection_status_changed_signal = Signal(bool)  # 连接状态变化信号
    
    def __init__(self, port="COM9", baudrate=921600, flow_control='none', auto_reconnect=True, reconnect_interval=3):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.flow_control = flow_control
        self.serial_port = None
        self.is_connected = False
        self.connect_callback = None
        self.running = False
        self.imu_parser = IMUDataParser()
        self.data_queue = queue.Queue(maxsize=1000)  # 限制队列大小
        self.data_buffer = deque(maxlen=100)
        self.sample_count = 0
        self.processed_count = 0
        self.root = None
        self.log_callback = None
        self.receive_buffer = b''
        self.callback = None
        self.thread = None
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.last_error_time = 0
        self.error_types = {}
        
        # 流控制参数
        self.xonxoff = False
        self.rtscts = False
        self.dsrdtr = False
        
        # 根据flow_control设置流控制参数
        if isinstance(flow_control, str):
            flow_control = flow_control.lower()
            if flow_control == 'hardware':
                self.rtscts = True
            elif flow_control == 'software':
                self.xonxoff = True
        elif isinstance(flow_control, dict):
            # 如果是字典形式的流控制配置
            self.xonxoff = flow_control.get('xonxoff', False)
            self.rtscts = flow_control.get('rtscts', False)
            self.dsrdtr = flow_control.get('dsrdtr', False)

    def _log(self, message):
        """记录日志"""
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as e:
                logger.error(f"日志记录失败: {e}")
        logger.info(message)

    def connect_to_serial_port(self, port=None, baudrate=None):
        """连接到串口"""
        self._log(f"connect_to_serial_port方法被调用，参数: port={port}, baudrate={baudrate}")
        
        # 参数类型验证
        if port is not None and not isinstance(port, str):
            error_msg = f"port参数必须是字符串类型，当前类型: {type(port)}"
            self._log(error_msg)
            self.error_occurred_signal.emit(error_msg)
            return False
        
        if baudrate is not None and not isinstance(baudrate, (int, str)):
            error_msg = f"baudrate参数必须是整数或字符串类型，当前类型: {type(baudrate)}"
            self._log(error_msg)
            self.error_occurred_signal.emit(error_msg)
            return False
        
        if self.is_connected:
            self._log("串口已连接")
            return True

        # 使用指定参数或默认参数
        connect_port = port or self.port
        connect_baudrate = baudrate or self.baudrate
        self.reconnect_timer.stop()  # 停止重连计时器

        try:
            # 配置流控制
            rtscts = self.rtscts
            dsrdtr = self.dsrdtr
            xonxoff = self.xonxoff
            
            # 如果flow_control是字符串，根据字符串设置流控制
            if isinstance(self.flow_control, str):
                flow_control_lower = self.flow_control.lower()
                if flow_control_lower == 'hardware':
                    rtscts = True
                elif flow_control_lower == 'software':
                    xonxoff = True
            
            self._log(f"尝试连接串口: {connect_port}@{connect_baudrate}，流控制设置: xonxoff={xonxoff}, rtscts={rtscts}, dsrdtr={dsrdtr}")
            
            # 创建串口连接
            self.serial_port = serial.Serial(
                port=connect_port,
                baudrate=connect_baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                rtscts=rtscts,
                dsrdtr=dsrdtr,
                xonxoff=xonxoff
            )
            
            self.is_connected = True
            self.port = connect_port
            self.baudrate = connect_baudrate
            
            self._log(f"串口连接成功: {connect_port}@{connect_baudrate}")
            self.connected_signal.emit()
            self.connection_status_changed_signal.emit(True)
            return True
            
        except Exception as e:
            error_type = type(e).__name__
            current_time = time.time()
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
            self.last_error_time = current_time
            
            error_msg = f"串口连接失败 {connect_port}@{connect_baudrate}: {e}"
            self._log(error_msg)
            self.error_occurred_signal.emit(error_msg)
            self.is_connected = False
            self.connection_status_changed_signal.emit(False)
            
            # 如果启用了自动重连，启动重连计时器
            if self.auto_reconnect:
                self._log(f"{self.reconnect_interval}秒后尝试重连...")
                self.reconnect_timer.start(self.reconnect_interval * 1000)
            
            return False

    def _attempt_reconnect(self):
        """尝试重新连接串口"""
        if self.is_connected or not self.auto_reconnect:
            self.reconnect_timer.stop()
            return
        
        self._log(f"尝试重新连接到 {self.port}@{self.baudrate}...")
        if self.connect_to_serial_port():
            # 重新连接成功，恢复数据读取
            self._log("重连成功，尝试恢复数据读取...")
            if self.running:
                self.start(self.callback)
        else:
            # 重连失败，继续计时
            self._log(f"重连失败，{self.reconnect_interval}秒后再次尝试...")

    def disconnect(self):
        """断开串口连接"""
        if not self.is_connected:
            self._log("串口已断开或未连接")
            return True

        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.is_connected = False
            self._log("串口连接已断开")
            self.disconnected_signal.emit("用户断开连接")
            self.connection_status_changed_signal.emit(False)
            return True
        except Exception as e:
            error_msg = f"断开串口连接时出错: {e}"
            self._log(error_msg)
            self.error_occurred_signal.emit(error_msg)
            return False

    def connect_serial(self, port=None, baudrate=None, timeout=None):
        """连接到串口（connect_to_serial_port的别名）
        
        Args:
            port: 串口端口
            baudrate: 波特率
            timeout: 超时时间（兼容性参数，实际未使用）
            
        Returns:
            bool: 是否连接成功
        """
        return self.connect_to_serial_port(port, baudrate)

    def start(self, callback=None):
        """启动数据读取"""
        if not self.is_connected:
            self._log("错误: 串口未连接")
            return False

        if self.running:
            self._log("数据读取已在运行")
            return False

        self.callback = callback
        self.running = True
        self.receive_buffer = b''
        
        # 启动读取线程
        self.thread = threading.Thread(target=self._read_data, daemon=True)
        self.thread.start()
        
        self._log("数据读取已启动")
        return True

    def stop(self):
        """停止数据读取"""
        self.running = False
        
        # 等待线程结束
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            
        self._log("数据读取已停止")

    def _read_data(self):
        """在独立线程中读取串口数据"""
        self._log("串口数据读取线程已启动")
        no_data_count = 0
        max_no_data_count = 50000  # 约50秒无数据则认为连接异常
        
        while self.running and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    no_data_count = 0
                    try:
                        # 读取可用数据
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        self.receive_buffer += data
                        
                        # 记录接收到的数据量
                        if len(data) > 0:
                            self._log(f"接收到 {len(data)} 字节数据")
                            
                            # 处理缓冲区中的数据
                            self._process_buffer()
                    except serial.SerialException as se:
                        error_msg = f"串口读取异常: {se}"
                        self._log(error_msg)
                        self.error_occurred_signal.emit(error_msg)
                        self.is_connected = False
                        self.connection_status_changed_signal.emit(False)
                        
                        # 如果启用了自动重连，启动重连计时器
                        if self.auto_reconnect:
                            self._log(f"{self.reconnect_interval}秒后尝试重连...")
                            self.reconnect_timer.start(self.reconnect_interval * 1000)
                        break
                else:
                    no_data_count += 1
                    # 每5秒输出一次无数据提示
                    if no_data_count % 5000 == 0:
                        self._log("未接收到串口数据...")
                    
                    # 如果长时间无数据，认为连接异常
                    if no_data_count > max_no_data_count:
                        self._log("长时间未接收到数据，认为连接异常")
                        self.is_connected = False
                        self.connection_status_changed_signal.emit(False)
                        
                        # 如果启用了自动重连，启动重连计时器
                        if self.auto_reconnect:
                            self._log(f"{self.reconnect_interval}秒后尝试重连...")
                            self.reconnect_timer.start(self.reconnect_interval * 1000)
                        break
                    
                    # 短暂休眠以避免CPU占用过高
                    time.sleep(0.001)
                    
            except Exception as e:
                error_msg = f"读取串口数据时出错: {e}"
                self._log(error_msg)
                self.error_occurred_signal.emit(error_msg)
                self.is_connected = False
                self.connection_status_changed_signal.emit(False)
                
                # 如果启用了自动重连，启动重连计时器
                if self.auto_reconnect:
                    self._log(f"{self.reconnect_interval}秒后尝试重连...")
                    self.reconnect_timer.start(self.reconnect_interval * 1000)
                break
                
        self._log("串口数据读取线程结束")

    def _process_buffer(self):
        """处理接收缓冲区中的数据"""
        try:
            # 将字节数据解码为字符串
            text_data = self.receive_buffer.decode('utf-8', errors='replace')
            
            # 按行分割数据
            lines = text_data.split('\n')
            
            # 保留未完成的行在缓冲区中
            if text_data.endswith('\n'):
                self.receive_buffer = b''
            else:
                # 将最后一行保留在缓冲区中
                self.receive_buffer = lines[-1].encode('utf-8')
                lines = lines[:-1]
                
            # 处理完整的行
            for line in lines:
                line = line.strip()
                if line:
                    self._process_line(line)
                    self.processed_count += 1
                    
            # 每处理100条数据，短暂休眠以避免CPU占用过高
            if self.processed_count % 100 == 0 and self.processed_count > 0:
                time.sleep(0.001)
                
        except Exception as e:
            self._log(f"处理数据缓冲区时出错: {e}")
            import traceback
            traceback.print_exc()

    def _process_line(self, line):
        """处理单行数据"""
        try:
            # 输出原始行数据（前100个字符）
            self._log(f"原始数据行: {line[:100]}{'...' if len(line) > 100 else ''}")
            
            # 使用IMU解析器解析数据
            result = self.imu_parser.parse_line(line)
            
            if result:
                self.sample_count += 1
                self.data_buffer.append(result)
                
                # 发送数据信号
                self.data_received_signal.emit(result)
                
                # 如果设置了回调函数，也调用回调函数
                if self.callback:
                    try:
                        self.callback(result)
                    except Exception as e:
                        self._log(f"调用数据回调函数时出错: {e}")
            else:
                self._log(f"无法解析数据行: {line[:50]}{'...' if len(line) > 50 else ''}")
                
        except Exception as e:
            self._log(f"处理数据行时出错: {e}")
            import traceback
            traceback.print_exc()

    def get_serial_status(self):
        """获取串口状态信息"""
        status = {
            "port": self.port,
            "baudrate": self.baudrate,
            "is_connected": self.is_connected,
            "running": self.running,
            "sample_count": self.sample_count,
            "processed_count": self.processed_count,
            "buffer_size": len(self.data_buffer),
            "auto_reconnect": self.auto_reconnect,
            "reconnect_interval": self.reconnect_interval,
            "is_reconnecting": self.reconnect_timer.isActive(),
            "error_count": self.error_types,
            "last_error_time": self.last_error_time if self.last_error_time > 0 else None
        }
        return status

    def is_serial_connected(self):
        """检查串口是否连接"""
        return self.is_connected and self.serial_port and self.serial_port.is_open

    def set_connect_callback(self, callback):
        """设置连接状态回调"""
        self.connect_callback = callback

    def set_flow_control(self, flow_control):
        """
        设置流控制参数
        
        Args:
            flow_control: 流控制参数，可以是字符串('none', 'hardware', 'software')或字典
        """
        if isinstance(flow_control, str):
            self.flow_control = flow_control.lower()
            if self.flow_control == 'hardware':
                self.rtscts = True
                self.xonxoff = False
                self.dsrdtr = False
            elif self.flow_control == 'software':
                self.xonxoff = True
                self.rtscts = False
                self.dsrdtr = False
            else:  # none
                self.rtscts = False
                self.xonxoff = False
                self.dsrdtr = False
        elif isinstance(flow_control, dict):
            self.flow_control = flow_control
            self.xonxoff = flow_control.get('xonxoff', False)
            self.rtscts = flow_control.get('rtscts', False)
            self.dsrdtr = flow_control.get('dsrdtr', False)
        else:
            self.flow_control = 'none'
            self.rtscts = False
            self.xonxoff = False
            self.dsrdtr = False
            
        self._log(f"流控制设置已更新: {self.flow_control}")

    def start_reading(self, data_callback=None, connect_callback=None):
        """
        启动数据读取（兼容旧接口）
        
        Args:
            data_callback: 数据回调函数
            connect_callback: 连接状态回调函数
            
        Returns:
            bool: 是否启动成功
        """
        self.callback = data_callback
        self.connect_callback = connect_callback
        
        # 尝试连接（如果尚未连接）
        if not self.is_connected:
            if not self.connect_serial():
                return False
                
        # 启动数据读取
        return self.start(data_callback)
    
    def __del__(self):
        """析构函数，确保资源被正确释放"""
        try:
            # 停止数据读取
            if self.running:
                self.stop()
            
            # 断开串口连接
            if self.is_connected:
                self.disconnect()
        except Exception as e:
            logger.error(f"ProtoSerialDataReader析构时出错: {e}")

# 优化的测试函数
def test_proto_serial_reader():
    """测试协议串口读取器"""
    def data_callback(data):
        # 只打印时间戳和数据量，避免过多输出
        print(f"[数据] 时间戳: {data['timestamp']:.3f}, 数据项: {len(data['data'])}个")
        
    def log_callback(message):
        print(f"[LOG] {message}")
        
    # 使用COM9端口进行测试
    reader = ProtoSerialDataReader(port="COM9", baudrate=921600)
    reader.set_logger(log_callback)
    
    if reader.connect_serial():
        print("串口连接成功，开始读取数据...")
        reader.start(data_callback)
        try:
            while True:
                time.sleep(1)  # 持续运行直到用户中断
        except KeyboardInterrupt:
            print("用户中断测试")
        finally:
            reader.stop()
            reader.disconnect()
            print("测试结束")


if __name__ == "__main__":
    test_proto_serial_reader()