#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件数据源适配器
用于处理离线文件数据的加载和解析
"""
import os
import time
import logging
from PySide6.QtCore import QThread, QObject, Signal
from .data_source_adapter import DataSourceAdapter
from .cnap_parser import CNAPDataParser
from .data_parser import IMUDataParser
from utils.utils import get_timestamp


class FileDataSourceAdapter(DataSourceAdapter):
    """文件数据源适配器"""
    def __init__(self, config=None):
        """初始化文件数据源适配器

        Args:
            config (dict, optional): 数据源配置. Defaults to None.
        """
        super().__init__(config)
        self.parser = None
        self.file_paths = []
        self.data_type = self.config.get('data_type', 'IMU')  # 默认为IMU数据
        self.reader_thread = None
        self._init_parser()
        self.logger.info(f"文件数据源适配器初始化完成，数据类型: {self.data_type}")

    def _init_parser(self):
        """初始化解析器"""
        try:
            if self.data_type.upper() == 'CNAP':
                self.parser = CNAPDataParser()
                self.parser.set_parse_callback(self._on_data_parsed)
            elif self.data_type.upper() == 'IMU':
                self.parser = IMUDataParser()
                self.parser.set_parse_callback(self._on_data_parsed)
            else:
                raise ValueError(f"不支持的数据类型: {self.data_type}")
            self.logger.info(f"初始化{self.data_type}解析器成功")
        except Exception as e:
            self.logger.error(f"初始化解析器失败: {str(e)}")
            self._emit_error(f"初始化解析器失败: {str(e)}")

    def _on_data_parsed(self, data):
        """数据解析回调

        Args:
            data (dict): 解析后的数据
        """
        if data:
            # 添加数据源标识
            data['source'] = 'file'
            data['data_type'] = self.data_type
            data['timestamp'] = data.get('timestamp', get_timestamp())
            self._emit_data(data)

    def connect(self):
        """连接数据源(文件系统)

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            # 检查文件路径是否存在
            file_paths = self.config.get('file_paths', [])
            if not file_paths:
                self.logger.error("未指定文件路径")
                self._emit_error("未指定文件路径")
                return False

            valid_paths = []
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    valid_paths.append(file_path)
                else:
                    self.logger.warning(f"文件不存在: {file_path}")

            if not valid_paths:
                self.logger.error("没有有效的文件路径")
                self._emit_error("没有有效的文件路径")
                return False

            self.file_paths = valid_paths
            self._emit_connection_status(True)
            self.logger.info(f"成功连接文件数据源，找到{len(valid_paths)}个有效文件")
            return True
        except Exception as e:
            self.logger.error(f"连接文件数据源失败: {str(e)}")
            self._emit_error(f"连接文件数据源失败: {str(e)}")
            return False

    def disconnect(self):
        """断开数据源连接"""
        self.stop()
        self.file_paths = []
        self._emit_connection_status(False)
        self.logger.info("已断开文件数据源连接")

    def start(self):
        """开始从数据源读取数据"""
        if not self.is_connected():
            self.logger.error("未连接数据源，无法开始读取")
            self._emit_error("未连接数据源，无法开始读取")
            return

        if self.running:
            self.logger.warning("数据读取已在运行中")
            return

        try:
            self.reader_thread = QThread()
            self.reader_worker = FileReaderWorker(self.file_paths, self.parser, self.data_type)
            self.reader_worker.moveToThread(self.reader_thread)
            self.reader_thread.started.connect(self.reader_worker.run)
            self.reader_worker.finished.connect(self.reader_thread.quit)
            self.reader_worker.finished.connect(self.reader_worker.deleteLater)
            self.reader_thread.finished.connect(self.reader_thread.deleteLater)
            self.reader_worker.data_parsed.connect(self._on_data_parsed)
            self.reader_worker.error_occurred.connect(self._emit_error)
            self.reader_thread.start()
            self.running = True
            self.logger.info("开始读取文件数据")
        except Exception as e:
            self.logger.error(f"启动文件数据读取失败: {str(e)}")
            self._emit_error(f"启动文件数据读取失败: {str(e)}")

    def stop(self):
        """停止从数据源读取数据"""
        if not self.running:
            return

        try:
            if self.reader_thread and self.reader_thread.isRunning():
                self.reader_thread.quit()
                self.reader_thread.wait()
            self.running = False
            self.logger.info("已停止读取文件数据")
        except Exception as e:
            self.logger.error(f"停止文件数据读取失败: {str(e)}")
            self._emit_error(f"停止文件数据读取失败: {str(e)}")

    def get_data(self):
        """获取数据(文件数据源不直接支持此方法)

        Returns:
            dict: 空字典
        """
        self.logger.warning("文件数据源不支持直接获取数据，请使用data_received信号")
        return {}


class FileReaderWorker(QObject):
    """文件读取工作线程"""
    finished = Signal()
    data_parsed = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, file_paths, parser, data_type):
        """初始化文件读取工作线程

        Args:
            file_paths (list): 文件路径列表
            parser (object): 数据解析器
            data_type (str): 数据类型
        """
        super().__init__()
        self.file_paths = file_paths
        self.parser = parser
        self.data_type = data_type
        self.running = True
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        """运行文件读取工作线程"""
        try:
            for file_path in self.file_paths:
                if not self.running:
                    break

                self.logger.info(f"开始解析文件: {file_path}")
                try:
                    # 根据数据类型选择不同的解析方法
                    if self.data_type.upper() == 'CNAP':
                        self.parser.parse_file(file_path)
                    elif self.data_type.upper() == 'IMU':
                        with open(file_path, 'r') as f:
                            for line in f:
                                if not self.running:
                                    break
                                parsed_data = self.parser.parse_line(line.strip())
                                if parsed_data:
                                    self.data_parsed.emit(parsed_data)
                                # 添加小延迟，避免UI卡顿
                                time.sleep(0.001)
                    self.logger.info(f"文件解析完成: {file_path}")
                except Exception as e:
                    self.logger.error(f"解析文件{file_path}失败: {str(e)}")
                    self.error_occurred.emit(f"解析文件{file_path}失败: {str(e)}")
        finally:
            self.running = False
            self.finished.emit()
            self.logger.info("文件读取工作线程已完成")

    def stop(self):
        """停止文件读取工作线程"""
        self.running = False
        self.logger.info("文件读取工作线程已停止")