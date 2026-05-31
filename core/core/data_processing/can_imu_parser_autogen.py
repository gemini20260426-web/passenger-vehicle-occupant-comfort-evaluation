#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
can_imu_parser_Custom 数据解析器
自动生成的解析脚本
"""

import re
import time
import logging
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class can_imu_parser_CustomParser:
    """can_imu_parser_Custom 数据解析器"""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.parsing_callback = None
        self._init_patterns()

    def _init_patterns(self):
        """初始化解析模式"""
        self.pattern_0 = re.compile(r": ")
        self.pattern_1 = re.compile(r": ")
        self.pattern_2 = re.compile(r": ")
        self.pattern_3 = re.compile(r": ")
        self.pattern_4 = re.compile(r": ")
        self.pattern_5 = re.compile(r"CSV")

    def set_parse_callback(self, callback):
        """设置解析回调"""
        self.parsing_callback = callback

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行数据"""
        try:
            line = line.strip()
            if not line:
                return None

            # 解析 CAN 全量多通道数据
            parts = line.split(',')
            if len(parts) >= 8:
                result = {
                    'timestamp': self._try_int(parts[0]) if len(parts) > 0 else 0,
                    'cnt': self._try_int(parts[0]) if len(parts) > 0 else 0,
                }
                field_names = ['ch1_ax', 'ch1_ay', 'ch1_az', 'ch1_gx', 'ch1_gy', 'ch1_gz',
                               'ch3_ax', 'ch3_ay', 'ch3_az', 'ch3_gx', 'ch3_gy', 'ch3_gz',
                               'ch4_ax', 'ch4_ay', 'ch4_az', 'ch4_gx', 'ch4_gy', 'ch4_gz',
                               'ch5_ax', 'ch5_ay', 'ch5_az', 'ch5_gx', 'ch5_gy', 'ch5_gz']
                for i, name in enumerate(field_names):
                    idx = i + 2
                    if idx < len(parts):
                        result[name] = self._try_float(parts[idx])
                if len(parts) > len(field_names) + 2:
                    result['speed'] = self._try_int(parts[len(field_names) + 2])
                    result['reverse'] = self._try_int(parts[len(field_names) + 3]) if len(parts) > len(field_names) + 3 else 0
                    result['steering'] = self._try_float(parts[len(field_names) + 4]) if len(parts) > len(field_names) + 4 else 0.0
                    result['emergency_brake'] = self._try_int(parts[len(field_names) + 5]) if len(parts) > len(field_names) + 5 else 0
                    result['brake_pressure'] = self._try_float(parts[len(field_names) + 6]) if len(parts) > len(field_names) + 6 else 0.0

                self.success_count += 1
                if self.parsing_callback:
                    try:
                        self.parsing_callback(result)
                    except Exception as e:
                        logger.error(f"回调执行失败: {e}")
                return result
            return None

        except Exception as e:
            self.error_count += 1
            logger.error(f"解析失败: {e}")
            return None

    def parse_file(self, file_path: str) -> pd.DataFrame:
        """解析整个文件"""
        records = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parsed_data = self.parse_line(line)
                    if parsed_data:
                        records.append(parsed_data)
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
        
        return pd.DataFrame(records)

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """验证数据合法性"""
        return True

    def get_stats(self) -> Dict[str, int]:
        """获取解析统计"""
        return {
            'success': self.success_count,
            'error': self.error_count,
            'total': self.success_count + self.error_count
        }
