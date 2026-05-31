#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据统一接入MQTT示例
展示如何使用数据接入管理器接入文件和串口数据并转发到MQTT
"""
import os
import sys
import logging
import time
import json
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, pyqtSignal
from core.data_processing.data_ingestion_manager import DataIngestionManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("multi_source_ingestion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CommandThread(QThread):
    """命令线程，用于接收用户输入"""
    stop_signal = pyqtSignal()

    def run(self):
        """运行命令线程"""
        logger.info("命令线程已启动，输入 'q' 退出，'s' 启动所有数据源，'t' 停止所有数据源")
        while True:
            cmd = input("请输入命令: ").strip().lower()
            if cmd == 'q':
                self.stop_signal.emit()
                break
            elif cmd == 's':
                logger.info("启动所有数据源...")
                self.parent().start_all_data_sources()
            elif cmd == 't':
                logger.info("停止所有数据源...")
                self.parent().stop_all_data_sources()
            elif cmd == 'status':
                self.parent().print_status()
            else:
                logger.info("未知命令，可用命令: q(退出), s(启动所有数据源), t(停止所有数据源), status(查看状态)")


class MultiSourceIngestionDemo(QThread):
    """多源数据接入演示"""
    def __init__(self):
        """初始化演示"""
        super().__init__()
        self.app = QApplication(sys.argv)
        self.ingestion_manager = None
        self.command_thread = None

    def run(self):
        """运行演示"""
        try:
            # 初始化数据接入管理器
            mqtt_config = {
                'broker': 'localhost',
                'port': 1883,
                'client_id': 'multi_source_ingestion_demo',
                'username': '',
                'password': '',
                'keepalive': 60
            }

            self.ingestion_manager = DataIngestionManager(mqtt_config)

            # 等待MQTT连接
            time.sleep(2)
            if not self.ingestion_manager.is_mqtt_connected():
                logger.error("MQTT连接失败，尝试重新连接...")
                if not self.ingestion_manager.connect_mqtt(mqtt_config):
                    logger.error("MQTT重新连接失败，程序退出")
                    return

            # 添加文件数据源 - IMU数据
            imu_file_config = {
                'file_paths': [
                    'd:\\UI重构\\test\\imudata\\log0.txt',
                    'd:\\UI重构\\test\\imudata\\log1.txt'
                ],
                'data_type': 'IMU'
            }
            self.ingestion_manager.add_data_source('imu_file', 'file', imu_file_config)

            # 添加文件数据源 - CNAP数据
            cnap_file_config = {
                'file_paths': [
                    'd:\\UI重构\\test\\cnapdata\\1.txt',
                    'd:\\UI重构\\test\\cnapdata\\2.txt'
                ],
                'data_type': 'CNAP'
            }
            self.ingestion_manager.add_data_source('cnap_file', 'file', cnap_file_config)

            # 添加串口数据源 - IMU数据
            imu_serial_config = {
                'port': 'COM3',
                'baudrate': 115200,
                'timeout': 1,
                'data_type': 'IMU'
            }
            self.ingestion_manager.add_data_source('imu_serial', 'serial', imu_serial_config)

            # 添加串口数据源 - CNAP数据
            cnap_serial_config = {
                'port': 'COM4',
                'baudrate': 9600,
                'timeout': 1,
                'data_type': 'CNAP'
            }
            self.ingestion_manager.add_data_source('cnap_serial', 'serial', cnap_serial_config)

            # 启动命令线程
            self.command_thread = CommandThread()
            self.command_thread.setParent(self)
            self.command_thread.stop_signal.connect(self.stop)
            self.command_thread.start()

            logger.info("多源数据接入系统已初始化完成")
            logger.info("请输入 's' 启动所有数据源，'t' 停止所有数据源，'status' 查看状态，'q' 退出")

            # 运行Qt事件循环
            sys.exit(self.app.exec_())
        except Exception as e:
            logger.error(f"程序发生异常: {str(e)}")

    def start_all_data_sources(self):
        """启动所有数据源"""
        if self.ingestion_manager:
            self.ingestion_manager.start_all_data_sources()

    def stop_all_data_sources(self):
        """停止所有数据源"""
        if self.ingestion_manager:
            self.ingestion_manager.stop_all_data_sources()

    def print_status(self):
        """打印系统状态"""
        if not self.ingestion_manager:
            logger.info("系统未初始化")
            return

        # 打印MQTT状态
        mqtt_status = "已连接" if self.ingestion_manager.is_mqtt_connected() else "未连接"
        logger.info(f"MQTT状态: {mqtt_status}")

        # 打印适配器状态
        adapters_status = self.ingestion_manager.get_all_adapters_status()
        for adapter_id, status in adapters_status.items():
            if status:
                connected = "已连接" if status['connected'] else "未连接"
                running = "运行中" if status['running'] else "已停止"
                data_type = status['data_type']
                logger.info(f"适配器 {adapter_id}: 类型={data_type}, 连接状态={connected}, 运行状态={running}")
            else:
                logger.info(f"适配器 {adapter_id}: 状态未知")

    def stop(self):
        """停止演示"""
        logger.info("正在停止系统...")
        # 停止所有数据源
        self.stop_all_data_sources()
        # 停止命令线程
        if self.command_thread and self.command_thread.isRunning():
            self.command_thread.quit()
            self.command_thread.wait()
        # 退出应用
        if self.app:
            self.app.quit()
        logger.info("系统已停止")


if __name__ == '__main__':
    """主函数"""
    demo = MultiSourceIngestionDemo()
    demo.run()