import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import asyncio
from typing import Dict, Any, Optional
import time

import numpy as np

logger = logging.getLogger(__name__)

_IMU_FIELD_RANGES = {
    'ax': (-100.0, 100.0), 'ay': (-100.0, 100.0), 'az': (-100.0, 100.0),
    'gx': (-2000.0, 2000.0), 'gy': (-2000.0, 2000.0), 'gz': (-2000.0, 2000.0),
    'speed': (0.0, 300.0), 'wheel': (-720.0, 720.0),
}


class ParallelDataProcessor:
    """并行数据处理器 — 委托已有解析器与验证器"""

    def __init__(self, max_workers: int = 8, max_data_size: int = 10000,
                 clip_enabled: bool = True, evaluation_mode: bool = False,
                 truncation_strategy: str = 'tail'):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.processing_queue = Queue(maxsize=1000)
        self.result_queue = Queue(maxsize=1000)
        self.processing_tasks = {}
        self.max_data_size = max_data_size
        self.truncation_strategy = truncation_strategy
        if evaluation_mode:
            clip_enabled = False
        self.clip_enabled = clip_enabled
        self.evaluation_mode = evaluation_mode
        self.outlier_flags = {}

        self._imu_parser = None
        self._validator = None

    def _ensure_imu_parser(self):
        if self._imu_parser is None:
            from .data_processing.data_parser import IMUDataParser
            self._imu_parser = IMUDataParser()
        return self._imu_parser

    def _ensure_validator(self):
        if self._validator is None:
            from .multi_source_sync.utils.data_validator import DataValidator
            self._validator = DataValidator()
        return self._validator

    async def process_data_stream(self, data_streams: Dict[str, Any]):
        """并行处理多个数据流"""
        try:
            tasks = []
            for source_id, data in data_streams.items():
                task = asyncio.create_task(
                    self._process_source_data(source_id, data)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_data = {}
            for i, result in enumerate(results):
                source_id = list(data_streams.keys())[i]
                if isinstance(result, Exception):
                    logger.error("数据源 %s 处理失败: %s", source_id, result)
                    processed_data[source_id] = None
                else:
                    processed_data[source_id] = result

            return processed_data

        except Exception as e:
            logger.error("并行数据处理失败: %s", e)
            return {}

    async def _process_source_data(self, source_id: str, data: Any):
        """处理单个数据源的数据"""
        try:
            preprocessed_data = await self._preprocess_data(data)
            parsed_data = await self._parse_data(preprocessed_data)
            validated_data = await self._validate_data(parsed_data)

            if isinstance(validated_data, list) and len(validated_data) > self.max_data_size:
                if self.truncation_strategy == 'tail':
                    validated_data = validated_data[-self.max_data_size:]
                elif self.truncation_strategy == 'head':
                    validated_data = validated_data[:self.max_data_size]
                elif self.truncation_strategy == 'sample':
                    rng = np.random.default_rng(42)
                    indices = rng.choice(len(validated_data), size=self.max_data_size, replace=False)
                    validated_data = [validated_data[i] for i in np.sort(indices)]
                logger.info("数据大小受限: 限制为 %d 项 (策略: %s)", self.max_data_size, self.truncation_strategy)

            return {
                'source_id': source_id,
                'data': validated_data,
                'timestamp': time.time(),
                'status': 'success'
            }

        except Exception as e:
            logger.error("数据源 %s 处理失败: %s", source_id, e)
            return {
                'source_id': source_id,
                'data': None,
                'timestamp': time.time(),
                'status': 'error',
                'error': str(e)
            }

    async def _preprocess_data(self, data):
        """数据预处理：异常值裁剪、基本清洗"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    result[key] = self._clip_outliers(value, key)
                else:
                    result[key] = value
            return result
        if isinstance(data, list):
            return [await self._preprocess_data(item) if isinstance(item, dict) else item for item in data]
        return data

    async def _parse_data(self, data):
        """数据解析：委托 IMUDataParser"""
        if isinstance(data, str):
            parser = self._ensure_imu_parser()
            try:
                parsed = parser.parse_line(data)
                if parsed:
                    return parsed
            except Exception as e:
                logger.warning("IMU 解析失败: %s", e)
        return data

    async def _validate_data(self, data):
        """数据验证：委托 DataValidator"""
        if isinstance(data, dict):
            validator = self._ensure_validator()
            try:
                result = validator.validate_data_source(
                    source_id=data.get('source_id', 'unknown'),
                    data=data
                )
                if not result.is_valid:
                    logger.warning("数据验证未通过: %s", result.message)
            except Exception as e:
                logger.warning("数据验证异常: %s", e)
        return data

    def set_evaluation_mode(self, enabled: bool = True):
        if enabled:
            self.clip_enabled = False
            logger.info("评测模式: 异常值裁剪已关闭")

    def _clip_outliers(self, value: float, field_name: str) -> float:
        lo, hi = _IMU_FIELD_RANGES.get(field_name, (float('-inf'), float('inf')))
        if value < lo or value > hi:
            self.outlier_flags[field_name] = {
                'value': value, 'range': (lo, hi),
                'field': field_name
            }
            if self.clip_enabled:
                return max(lo, min(hi, value))
        return value
