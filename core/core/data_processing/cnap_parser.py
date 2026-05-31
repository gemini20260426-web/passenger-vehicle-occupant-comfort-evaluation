#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cnap_parser_Custom 数据解析器
专用于CNAP心血管监测数据（%WAVE% 连续血压波形 + %BEATS% 逐拍血流动力学参数）
"""

import re
import time
import logging
from typing import Dict, Any, Optional, List
import pandas as pd

logger = logging.getLogger(__name__)

BEATS_PARAM_MAPPING = [
    ('Systolic_BP', 0),
    ('Diastolic_BP', 1),
    ('Heart_Rate', 2),
    ('Mean_Arterial_Pressure', 3),
    ('Pulse_Pressure', 4),
    ('Heart_Rate_Variability', 5),
    ('Mean_Pulse_Pressure', 6),
    ('Stroke_Volume', 7),
    ('Vascular_Resistance', 8),
    ('PPV', 9),
    ('SVV', 10),
    ('Ejection_Fraction', 11),
]


class cnap_parser_CustomParser:
    """CNAP 数据专用解析器"""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.wave_count = 0
        self.beat_count = 0
        self.parsing_callback = None
        self._beats_buffer: List[dict] = []
        self._init_patterns()

    def _init_patterns(self):
        self.pattern_wave = re.compile(r"""Data:\s*b'%WAVE%([\d.]+):\s*([\d.]+)'""")
        self.pattern_beats = re.compile(r"""Data:\s*b'%BEATS%([\d.]+):\s*([^']+)'""")
        self.pattern_ts = re.compile(r"Timestamp:\s*(\d+\.\d+)")

    def set_parse_callback(self, callback):
        self.parsing_callback = callback

    def _extract_number(self, line: str) -> Optional[float]:
        m = re.search(r"([\d.]+)", line)
        return float(m.group(1)) if m else None

    def _parse_beats_params(self, params_str: str) -> Dict[str, Optional[float]]:
        result = {}
        clean = params_str.strip().rstrip('\\n').rstrip(';').strip()
        parts = [p.strip() for p in clean.split(';')]
        for name, idx in BEATS_PARAM_MAPPING:
            try:
                v = float(parts[idx])
                result[name] = None if v in (-1.0, -1) else v
            except (IndexError, ValueError):
                result[name] = None
        return result

    def _emit(self, record: dict):
        self.success_count += 1
        if self.parsing_callback:
            try:
                self.parsing_callback(record)
            except Exception:
                pass

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        try:
            line = line.strip()
            if not line:
                return None

            m = self.pattern_wave.search(line)
            if m:
                record = {
                    'cnap_type': 'WAVE',
                    'wave_t': float(m.group(1)),
                    'pressure': float(m.group(2)),
                }
                self.wave_count += 1
                self._emit(record)
                return record

            m = self.pattern_beats.search(line)
            if m:
                params = self._parse_beats_params(m.group(2))
                record = {
                    'cnap_type': 'BEATS',
                    'beat_t': float(m.group(1)),
                }
                record.update(params)
                self.beat_count += 1
                self._beats_buffer.append(record)
                self._emit(record)
                return record

            self.error_count += 1
            return None

        except Exception as e:
            self.error_count += 1
            logger.error(f"解析失败: {e}")
            return None

    def parse_file(self, file_path: str) -> pd.DataFrame:
        records = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for m in self.pattern_wave.finditer(content):
                r = {
                    'cnap_type': 'WAVE',
                    'wave_t': float(m.group(1)),
                    'pressure': float(m.group(2)),
                }
                records.append(r)
                self.wave_count += 1

            for m in self.pattern_beats.finditer(content):
                params = self._parse_beats_params(m.group(2))
                r = {'cnap_type': 'BEATS', 'beat_t': float(m.group(1))}
                r.update(params)
                records.append(r)
                self.beat_count += 1
                self._beats_buffer.append(r)

            self.success_count = len(records)
            logger.info(f"解析完成: WAVE={self.wave_count}, BEATS={self.beat_count}")
        except Exception as e:
            logger.error(f"读取文件失败: {e}")

        return pd.DataFrame(records)

    def get_beats_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self._beats_buffer)

    def validate_data(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict) and len(data) > 0

    def get_stats(self) -> Dict[str, int]:
        return {
            'wave_count': self.wave_count,
            'beat_count': self.beat_count,
            'success': self.success_count,
            'error': self.error_count,
        }
