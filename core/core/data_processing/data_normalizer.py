#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据标准化器
将8字段IMU数据补齐为12字段统一格式，估算gz（偏航角速度），
输出标准化CSV到 data_output/normalized/ 目录，
作为后续所有数据处理和分析的统一数据源。
"""

import os
import csv
import math
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DataNormalizer:
    """IMU数据标准化器

    职责:
    1. 检测数据格式 (8字段 / 12字段)
    2. 对8字段数据估算gz (偏航角速度)
    3. 补齐为统一12字段格式
    4. 输出标准化CSV文件
    """

    DEFAULT_STEERING_RATIO = 16.0
    DEFAULT_WHEELBASE = 2.7

    STANDARD_FIELDS = [
        'timestamp', 'cnt', 'ax', 'ay', 'az',
        'gx', 'gy', 'gz', 'speed', 'wheel',
        'loc1', 'loc2', 'crc', 'source_format'
    ]

    def __init__(self, steering_ratio: float = None, wheelbase: float = None):
        self.steering_ratio = steering_ratio or self.DEFAULT_STEERING_RATIO
        self.wheelbase = wheelbase or self.DEFAULT_WHEELBASE
        self._stats = {
            'total': 0,
            'eight_field': 0,
            'twelve_field': 0,
            'estimated_gz': 0,
            'errors': 0
        }

    @staticmethod
    def detect_format(record: Dict[str, Any]) -> str:
        """检测数据记录格式

        Returns:
            '12field' - 包含完整 gx/gy/gz 数据
            '8field'  - 缺少 gx/gy/gz (均为 None)
            'unknown' - 无法判定
        """
        gx = record.get('gx')
        gy = record.get('gy')
        gz = record.get('gz')

        if gx is not None and gy is not None and gz is not None:
            return '12field'
        if gx is None and gy is None and gz is None:
            if all(k in record for k in ['ax', 'ay', 'az', 'speed', 'wheel']):
                return '8field'
        return 'unknown'

    @staticmethod
    def estimate_gz(speed_kmh: float, wheel_deg: float,
                    steering_ratio: float = None,
                    wheelbase: float = None) -> float:
        """自行车模型估算偏航角速度 (yaw rate)

        gz = v * tan(δ) / L

        Parameters:
            speed_kmh: 车速 (km/h)
            wheel_deg: 方向盘转角 (度)
            steering_ratio: 转向比 (方向盘转角/车轮转角), 默认16
            wheelbase: 轴距 (m), 默认2.7

        Returns:
            gz: 偏航角速度 (rad/s)
        """
        sr = steering_ratio or DataNormalizer.DEFAULT_STEERING_RATIO
        wb = wheelbase or DataNormalizer.DEFAULT_WHEELBASE

        v = speed_kmh / 3.6
        delta_deg = wheel_deg / sr
        delta_rad = math.radians(delta_deg)

        if abs(delta_rad) < 1e-10:
            return 0.0

        return v * math.tan(delta_rad) / wb

    def normalize_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将单条记录标准化为12字段格式

        8字段 → 估算gz，补齐12字段
        12字段 → 直接透传
        """
        fmt = self.detect_format(record)
        self._stats['total'] += 1

        ts = record.get('timestamp', time.time())
        if isinstance(ts, (int, float)):
            ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        else:
            ts_str = str(ts)

        if fmt == '12field':
            self._stats['twelve_field'] += 1
            return {
                'timestamp': ts_str,
                'cnt': record.get('cnt', 0),
                'ax': record.get('ax', 0),
                'ay': record.get('ay', 0),
                'az': record.get('az', 0),
                'gx': record.get('gx', 0),
                'gy': record.get('gy', 0),
                'gz': record.get('gz', 0),
                'speed': record.get('speed', 0),
                'wheel': record.get('wheel', 0),
                'loc1': record.get('loc1', 0),
                'loc2': record.get('loc2', 0),
                'crc': record.get('crc', ''),
                'source_format': '12field_original'
            }

        if fmt == '8field':
            self._stats['eight_field'] += 1
            speed = record.get('speed', 0)
            wheel = record.get('wheel', 0)

            try:
                gz_est = self.estimate_gz(
                    float(speed), float(wheel),
                    self.steering_ratio, self.wheelbase
                )
                self._stats['estimated_gz'] += 1
            except (ValueError, TypeError):
                gz_est = 0.0
                self._stats['errors'] += 1

            return {
                'timestamp': ts_str,
                'cnt': record.get('cnt', 0),
                'ax': record.get('ax', 0),
                'ay': record.get('ay', 0),
                'az': record.get('az', 0),
                'gx': '',
                'gy': '',
                'gz': round(gz_est, 6),
                'speed': speed,
                'wheel': wheel,
                'loc1': record.get('loc1', 0),
                'loc2': record.get('loc2', 0),
                'crc': '',
                'source_format': '8field_estimated'
            }

        self._stats['errors'] += 1
        logger.warning(f"无法识别数据格式: {fmt}, record keys={list(record.keys())[:8]}")
        return None

    def normalize_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量标准化"""
        normalized = []
        for rec in records:
            norm = self.normalize_record(rec)
            if norm:
                normalized.append(norm)
        return normalized

    def save_normalized(self, records: List[Dict[str, Any]],
                        output_dir: str = None) -> Tuple[str, int]:
        """保存标准化CSV文件

        Returns:
            (输出文件路径, 写入记录数)
        """
        if output_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            output_dir = os.path.join(project_root, 'data_output', 'normalized')
        else:
            output_dir = os.path.join(output_dir, 'normalized')

        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'imu_normalized_{timestamp}.csv'
        filepath = os.path.join(output_dir, filename)

        written = 0
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.STANDARD_FIELDS,
                                    extrasaction='ignore')
            writer.writeheader()
            for rec in records:
                writer.writerow(rec)
                written += 1

        logger.info(f"标准化CSV已保存: {filepath} ({written} 条)")
        return filepath, written

    def normalize_batch_and_save(self, records: List[Dict[str, Any]],
                                 output_dir: str = None) -> Tuple[str, int, Dict[str, int]]:
        """批量标准化并保存（用于已解析的数据缓存）

        Returns:
            (标准化CSV路径, 记录数, 统计信息)
        """
        normalized = self.normalize_batch(records)
        filepath, written = self.save_normalized(normalized, output_dir)
        return filepath, written, self.get_stats()

    def parse_and_normalize(self, file_path: str,
                            output_dir: str = None) -> Tuple[str, int, Dict[str, int]]:
        """一站式：解析原始文件 → 标准化 → 存盘

        Returns:
            (标准化CSV路径, 记录数, 统计信息)
        """
        from .data_parser import IMUDataParser

        parser = IMUDataParser()
        raw_records = parser.parse_file(file_path)

        if not raw_records:
            logger.error(f"解析文件失败或无数据: {file_path}")
            return '', 0, dict(self._stats)

        normalized = self.normalize_batch(raw_records)
        filepath, written = self.save_normalized(normalized, output_dir)

        stats = dict(self._stats)
        logger.info(
            f"标准化完成: total={stats['total']}, "
            f"12field={stats['twelve_field']}, "
            f"8field={stats['eight_field']}, "
            f"estimated_gz={stats['estimated_gz']}, "
            f"errors={stats['errors']}"
        )

        return filepath, written, stats

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def reset_stats(self):
        self._stats = {
            'total': 0,
            'eight_field': 0,
            'twelve_field': 0,
            'estimated_gz': 0,
            'errors': 0
        }
