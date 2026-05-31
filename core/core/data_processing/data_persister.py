#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据持久化模块 - 将行为检测结果和IMU+behavior数据落盘
供高级分析直接提取，同时不影响流式处理
"""

import os
import csv
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional


class DataPersister:
    """数据持久化器 - 双路CSV落盘"""

    BEHAVIOR_COLUMNS = [
        'timestamp', 'behavior', 'confidence', 'speed', 'wheel',
        'ax', 'ay', 'az', 'gx', 'gy', 'gz'
    ]

    IMU_BEHAVIOR_COLUMNS = [
        'timestamp', 'ax', 'ay', 'az', 'gx', 'gy', 'gz',
        'speed', 'wheel', 'behavior', 'confidence'
    ]

    def __init__(self, output_root: str = None, flush_interval: int = 200, flush_seconds: float = 5.0):
        self.logger = logging.getLogger(__name__)

        if output_root is None:
            output_root = os.path.join(os.getcwd(), 'data_output')
        self.output_root = output_root

        self._behavior_dir = os.path.join(output_root, 'behavior_results')
        self._imu_behavior_dir = os.path.join(output_root, 'imu_behavior')

        os.makedirs(self._behavior_dir, exist_ok=True)
        os.makedirs(self._imu_behavior_dir, exist_ok=True)

        self._flush_interval = flush_interval
        self._flush_seconds = flush_seconds

        self._lock = threading.Lock()

        self._behavior_file: Optional[str] = None
        self._behavior_writer: Optional[object] = None
        self._behavior_buffer: list = []
        self._behavior_count: int = 0

        self._imu_behavior_file: Optional[str] = None
        self._imu_behavior_writer: Optional[object] = None
        self._imu_behavior_buffer: list = []
        self._imu_behavior_count: int = 0

        self._last_flush: float = time.time()
        self._flush_check_counter: int = 0
        self._flush_check_mod: int = max(1, flush_interval // 5)

        self._init_files()

        self.logger.info(f"DataPersister 初始化完成，输出目录: {self.output_root}")

    def _init_files(self):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        self._behavior_file = os.path.join(self._behavior_dir, f'behavior_{ts}.csv')
        self._imu_behavior_file = os.path.join(self._imu_behavior_dir, f'imu_behavior_{ts}.csv')

        self._behavior_fh = open(self._behavior_file, 'w', newline='', encoding='utf-8')
        self._behavior_writer = csv.DictWriter(self._behavior_fh, fieldnames=self.BEHAVIOR_COLUMNS)
        self._behavior_writer.writeheader()
        self._behavior_fh.flush()

        self._imu_behavior_fh = open(self._imu_behavior_file, 'w', newline='', encoding='utf-8')
        self._imu_behavior_writer = csv.DictWriter(self._imu_behavior_fh, fieldnames=self.IMU_BEHAVIOR_COLUMNS)
        self._imu_behavior_writer.writeheader()
        self._imu_behavior_fh.flush()

        self.logger.info(f"行为结果文件: {self._behavior_file}")
        self.logger.info(f"IMU+行为文件: {self._imu_behavior_file}")

    def write_behavior_result(self, result: Dict[str, Any]):
        """写入行为检测结果"""
        with self._lock:
            raw = result.get('raw_data', result)
            row = {
                'timestamp': result.get('timestamp', ''),
                'behavior': result.get('behavior', ''),
                'confidence': result.get('confidence', 0),
                'speed': raw.get('speed', 0) if isinstance(raw, dict) else 0,
                'wheel': raw.get('wheel', 0) if isinstance(raw, dict) else 0,
                'ax': raw.get('ax', 0) if isinstance(raw, dict) else 0,
                'ay': raw.get('ay', 0) if isinstance(raw, dict) else 0,
                'az': raw.get('az', 0) if isinstance(raw, dict) else 0,
                'gx': self._safe_val(raw, 'gx'),
                'gy': self._safe_val(raw, 'gy'),
                'gz': self._safe_val(raw, 'gz'),
            }
            self._behavior_buffer.append(row)
            self._behavior_count += 1
            self._maybe_flush()

    def write_imu_behavior(self, combined: Dict[str, Any]):
        """写入IMU+行为合并数据"""
        with self._lock:
            base = combined.get('_base', combined)
            raw = base.get('raw_data', base) if isinstance(base, dict) else {}

            row = {
                'timestamp': combined.get('timestamp', ''),
                'ax': raw.get('ax', 0) if isinstance(raw, dict) else 0,
                'ay': raw.get('ay', 0) if isinstance(raw, dict) else 0,
                'az': raw.get('az', 0) if isinstance(raw, dict) else 0,
                'gx': self._safe_val(raw, 'gx'),
                'gy': self._safe_val(raw, 'gy'),
                'gz': self._safe_val(raw, 'gz'),
                'speed': raw.get('speed', 0) if isinstance(raw, dict) else 0,
                'wheel': raw.get('wheel', 0) if isinstance(raw, dict) else 0,
                'behavior': combined.get('base_behavior', combined.get('behavior', '')),
                'confidence': combined.get('base_confidence', combined.get('confidence', 0)),
            }
            self._imu_behavior_buffer.append(row)
            self._imu_behavior_count += 1
            self._maybe_flush()

    @staticmethod
    def _safe_val(raw: Any, key: str) -> Any:
        """安全获取字段值，None时返回空字符串"""
        if not isinstance(raw, dict):
            return ''
        val = raw.get(key)
        return '' if val is None else val

    def _maybe_flush(self):
        self._flush_check_counter += 1
        if self._flush_check_counter % self._flush_check_mod != 0:
            return
        if len(self._behavior_buffer) >= self._flush_interval or len(self._imu_behavior_buffer) >= self._flush_interval:
            self._flush()
            return
        now = time.time()
        if (now - self._last_flush) >= self._flush_seconds:
            self._flush()

    def _flush(self):
        if self._behavior_buffer:
            self._behavior_writer.writerows(self._behavior_buffer)
            self._behavior_fh.flush()
            self._behavior_buffer.clear()

        if self._imu_behavior_buffer:
            self._imu_behavior_writer.writerows(self._imu_behavior_buffer)
            self._imu_behavior_fh.flush()
            self._imu_behavior_buffer.clear()

        self._last_flush = time.time()

    def flush(self):
        """强制刷新缓冲区"""
        with self._lock:
            self._flush()

    def close(self):
        """关闭文件"""
        with self._lock:
            self._flush()
            if hasattr(self, '_behavior_fh') and self._behavior_fh:
                self._behavior_fh.close()
            if hasattr(self, '_imu_behavior_fh') and self._imu_behavior_fh:
                self._imu_behavior_fh.close()
            self.logger.info(f"DataPersister 已关闭，行为结果: {self._behavior_count} 条, IMU+行为: {self._imu_behavior_count} 条")

    def get_stats(self) -> Dict[str, Any]:
        return {
            'behavior_count': self._behavior_count,
            'imu_behavior_count': self._imu_behavior_count,
            'behavior_file': self._behavior_file,
            'imu_behavior_file': self._imu_behavior_file,
            'output_root': self.output_root,
        }
