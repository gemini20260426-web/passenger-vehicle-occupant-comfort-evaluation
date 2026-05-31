#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步文件读取器 - 基于生产系统的优化实现
解决离线数据解析卡阻问题，采用数据块处理策略
"""

import os
import time
import threading
import logging
from typing import Callable, Optional, List, Dict, Any
from PySide6.QtCore import QObject, Signal, QThread, QTimer, QMetaObject, Qt
import gc

# 可选导入 chardet
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


class AsyncFileReader(QObject):
    """异步文件读取器，采用数据块处理策略"""
    
    # 定义信号
    data_received = Signal(dict)  # 数据接收信号
    progress_updated = Signal(float)  # 进度更新信号
    reading_completed = Signal()  # 读取完成信号
    error_occurred = Signal(str)  # 错误发生信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self, file_path: str, chunk_size: int = 1024 * 1024):
        super().__init__()
        self.file_path = file_path
        self.chunk_size = chunk_size  # 1MB数据块大小
        self.running = False
        self.paused = False
        self.thread = None
        
        # 导入IMU数据解析器
        from .data_parser import IMUDataParser
        self.imu_parser = IMUDataParser()
        
        # 性能优化参数 - 针对大文件处理优化
        self.max_buffer_size = 2000  # 减少缓冲区大小，避免内存累积
        self.data_buffer = []
        self.process_count = 0
        self.gc_threshold = 10000  # 降低垃圾回收阈值，更频繁地释放内存
        
        # 进度控制 - 减少进度更新频率
        self.last_progress_update = 0
        self.progress_update_interval = 5.0  # 至少间隔5%才更新进度
        
        # 回调函数
        self.callback = None
        self.progress_callback = None
        self.complete_callback = None
        self.log_callback = None
        
        # 统计信息
        self.total_lines = 0
        self.processed_lines = 0
        self.parsed_packets = 0
        self.start_time = None
        
        # 数据块处理参数 - 大文件处理优化
        self.lines_per_chunk = 500   # 减少每次处理行数，降低内存峰值
        self.chunk_delay = 0.005     # 增加延迟，给系统更多时间处理
        
        # 线程安全的数据队列
        self.data_queue = []
        self.data_queue_lock = threading.Lock()
        
        self.logger = logging.getLogger(__name__)

    def set_callbacks(self, data_callback=None, progress_callback=None, 
                     complete_callback=None, log_callback=None):
        """设置回调函数"""
        self.callback = data_callback
        self.progress_callback = progress_callback
        self.complete_callback = complete_callback
        self.log_callback = log_callback

    def start(self) -> bool:
        """启动异步文件读取"""
        try:
            if self.running:
                self.logger.warning("文件读取器已在运行")
                return False
                
            if not os.path.exists(self.file_path):
                error_msg = f"文件不存在: {self.file_path}"
                self.logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False
            
            # 计算文件总行数
            self._calculate_total_lines()
            
            self.running = True
            self.start_time = time.time()
            
            # 创建工作线程
            self.thread = threading.Thread(target=self._read_file_worker, daemon=True)
            self.thread.start()
            
            # 启动主线程定时器，定期处理数据队列
            self._start_main_thread_timer()
            
            self.logger.info(f"异步文件读取器启动成功，文件: {self.file_path}")
            return True
            
        except Exception as e:
            error_msg = f"启动文件读取器失败: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def _start_main_thread_timer(self):
        """启动主线程定时器，定期处理数据队列"""
        try:
            self.main_thread_timer = QTimer()
            self.main_thread_timer.timeout.connect(self._process_data_queue)
            self.main_thread_timer.start(200)
        except Exception as e:
            self.logger.error(f"启动主线程定时器失败: {e}")

    def _process_data_queue(self):
        """在主线程中处理数据队列（节流优化版）"""
        try:
            now = time.time()
            if not hasattr(self, '_last_process_time'):
                self._last_process_time = 0
            if now - self._last_process_time < 0.15:
                return
            self._last_process_time = now

            with self.data_queue_lock:
                if not self.data_queue:
                    return

                batch_size = min(5, len(self.data_queue))
                batch_data = self.data_queue[:batch_size]
                self.data_queue = self.data_queue[batch_size:]
                if len(self.data_queue) > 3000:
                    self.data_queue = self.data_queue[-1000:]

            for data in batch_data:
                try:
                    self.data_received.emit(data)
                    if self.callback:
                        self.callback(data)
                except Exception as e:
                    self.logger.warning(f"处理数据时出错: {e}")

        except Exception as e:
            self.logger.error(f"处理数据队列时出错: {e}")

    def _calculate_total_lines(self):
        """计算文件总行数"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.total_lines = sum(1 for _ in f)
            self.logger.info(f"文件总行数: {self.total_lines}")
        except Exception as e:
            self.logger.warning(f"无法计算文件总行数: {e}")
            self.total_lines = 0

    def _read_file_worker(self):
        """文件读取工作线程 - 协程优化版本"""
        try:
            import asyncio
            
            with open(self.file_path, 'rb') as f:
                raw_data = f.read(1024)
                if HAS_CHARDET:
                    detected = chardet.detect(raw_data)
                    encoding = detected.get('encoding') or 'utf-8'
                else:
                    encoding = 'utf-8'
            
            self.logger.info(f"检测到文件编码: {encoding}")
            
            with open(self.file_path, 'r', encoding=encoding) as f:
                lines_buffer = []
                line_count = 0
                
                for line in f:
                    if not self.running:
                        break
                        
                    while self.paused and self.running:
                        time.sleep(0.01)
                        if not self.running:
                            break
                    
                    if not self.running:
                        break
                    
                    line = line.strip()
                    if line:
                        lines_buffer.append(line)
                        line_count += 1
                    
                    if len(lines_buffer) >= self.lines_per_chunk:
                        self._process_chunk(lines_buffer)
                        lines_buffer = []
                        
                        self._update_progress(line_count)
                        
                        asyncio.sleep(0)
                
                if lines_buffer and self.running:
                    self._process_chunk(lines_buffer)
                
                if self.running:
                    self._complete_reading()
                    
        except Exception as e:
            error_msg = f"文件读取工作线程出错: {str(e)}"
            self.logger.error(error_msg)
            QTimer.singleShot(0, lambda: self.error_occurred.emit(error_msg))
        finally:
            self.running = False

    def _process_chunk(self, lines: List[str]):
        """批量处理数据块 - 线程安全版本"""
        try:
            chunk_start_time = time.time()
            chunk_parsed_count = 0
            
            # 批量解析数据
            for line in lines:
                if not self.running:
                    break
                    
                try:
                    parsed_data = self.imu_parser.parse_line(line)
                    if parsed_data:
                        chunk_parsed_count += 1
                        self.parsed_packets += 1
                        
                        # 将数据添加到线程安全队列，而不是直接发送信号
                        with self.data_queue_lock:
                            self.data_buffer.append(parsed_data)
                            self.data_queue.append(parsed_data)
                        
                        # 检查缓冲区大小
                        if len(self.data_buffer) >= self.max_buffer_size:
                            # 清空缓冲区，避免内存占用过大
                            self.data_buffer.clear()
                            
                except Exception as e:
                    self.logger.debug(f"解析行数据失败: {e}")
                    continue
            
            # 更新处理计数
            self.processed_lines += len(lines)
            
            # 触发垃圾回收
            self.process_count += 1
            if self.process_count % self.gc_threshold == 0:
                gc.collect()
                
        except Exception as e:
            self.logger.error(f"处理数据块时出错: {e}")

    def _update_progress(self, current_line: int):
        """更新进度 - 线程安全版本"""
        try:
            if self.total_lines > 0:
                progress = (current_line / self.total_lines) * 100
                
                # 检查是否需要更新进度
                if progress - self.last_progress_update >= self.progress_update_interval:
                    self.last_progress_update = progress
                    
                    # 使用QTimer.singleShot确保在主线程中发送进度信号
                    QTimer.singleShot(0, lambda: self.progress_updated.emit(progress))
                    
                    # 调用进度回调函数
                    if self.progress_callback:
                        QTimer.singleShot(0, lambda: self.progress_callback(progress))
                        
        except Exception as e:
            self.logger.warning(f"更新进度时出错: {e}")

    def _complete_reading(self):
        """完成读取 - 线程安全版本"""
        try:
            # 处理剩余的数据队列
            QTimer.singleShot(0, self._process_data_queue)
            
            # 使用QTimer.singleShot确保在主线程中发送完成信号
            QTimer.singleShot(0, lambda: self.reading_completed.emit())
            
            # 调用完成回调函数
            if self.complete_callback:
                QTimer.singleShot(0, self.complete_callback)
                
            # 记录完成信息
            elapsed_time = time.time() - self.start_time
            self.logger.info(f"文件读取完成，总行数: {self.total_lines}, 解析数据包: {self.parsed_packets}, 耗时: {elapsed_time:.2f}秒")
            
        except Exception as e:
            self.logger.error(f"完成读取时出错: {e}")

    def pause(self):
        """暂停文件读取 - 改进版本：保持数据流但暂停新数据添加"""
        try:
            self.paused = True
            self.logger.info("文件读取已暂停（保持现有数据流）")
            
            # 暂停时不清空数据队列，保持现有数据
            # 只停止添加新数据到队列
            
        except Exception as e:
            self.logger.error(f"暂停文件读取时出错: {e}")

    def resume(self):
        """恢复文件读取 - 改进版本：检查状态并恢复"""
        try:
            self.paused = False
            self.logger.info("文件读取已恢复")
            
            # 检查数据队列状态
            with self.data_queue_lock:
                queue_size = len(self.data_queue)
                if queue_size > 0:
                    self.logger.info(f"恢复时数据队列中有 {queue_size} 条待处理数据")
                    
            # 确保主线程定时器正在运行
            if hasattr(self, 'main_thread_timer') and not self.main_thread_timer.isActive():
                self.logger.warning("检测到主线程定时器已停止，重新启动")
                self._start_main_thread_timer()
                
        except Exception as e:
            self.logger.error(f"恢复文件读取时出错: {e}")

    def stop(self):
        """停止文件读取 - 改进版本：安全停止并清理资源"""
        try:
            self.running = False
            self.paused = False
            
            # 等待工作线程结束
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=2.0)  # 增加超时时间
                if self.thread.is_alive():
                    self.logger.warning("工作线程未能在超时时间内结束")
            
            # 停止主线程定时器
            if hasattr(self, 'main_thread_timer'):
                self.main_thread_timer.stop()
                self.main_thread_timer.deleteLater()
                
            # 清理数据队列和缓冲区
            with self.data_queue_lock:
                self.data_queue.clear()
                self.data_buffer.clear()
                
            self.logger.info("文件读取器已安全停止")
            
        except Exception as e:
            self.logger.error(f"停止文件读取器时出错: {e}")
    
    def get_status(self) -> dict:
        """获取读取器状态信息"""
        try:
            status = {
                'running': self.running,
                'paused': self.paused,
                'queue_size': len(self.data_queue),
                'buffer_size': len(self.data_buffer),
                'processed_lines': self.processed_lines,
                'parsed_packets': self.parsed_packets,
                'total_lines': self.total_lines,
                'timer_active': hasattr(self, 'main_thread_timer') and self.main_thread_timer.isActive()
            }
            return status
        except Exception as e:
            self.logger.error(f"获取状态信息时出错: {e}")
            return {}
    
    def is_healthy(self) -> bool:
        """检查读取器是否健康运行"""
        try:
            # 检查基本状态
            if not self.running:
                return False
                
            # 检查主线程定时器
            if not hasattr(self, 'main_thread_timer') or not self.main_thread_timer.isActive():
                return False
                
            # 检查工作线程
            if not self.thread or not self.thread.is_alive():
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"检查读取器健康状态时出错: {e}")
            return False
    
    def get_progress(self) -> float:
        """获取当前进度"""
        if self.total_lines > 0:
            return (self.processed_lines / self.total_lines) * 100
        return 0.0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_lines': self.total_lines,
            'processed_lines': self.processed_lines,
            'parsed_packets': self.parsed_packets,
            'running': self.running,
            'paused': self.paused
        }
