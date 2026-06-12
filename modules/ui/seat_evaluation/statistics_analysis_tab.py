#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量统计分析标签页
加载已解析数据集，执行全量多通道座椅评测及IMU点位对照分析

功能:
  - 数据集加载与管理
  - 预处理级别选择（Level 0/1/2）
  - 多通道评测指标计算
  - IMU点位对照分析
  - 统计分析结果表格展示
  - JSON/Markdown/CSV报告导出
"""

import logging
import os
import json
import sqlite3
import traceback
import statistics as _stat
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import csv as csv_mod

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LogNorm

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QTextEdit,
    QSplitter, QFrame, QCheckBox, QSpinBox, QHeaderView,
    QTabWidget, QScrollArea, QGridLayout, QSizePolicy, QDialog,
    QDoubleSpinBox, QApplication,
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSize, QTimer
from PySide6.QtGui import QFont, QColor

from core.core.seat_evaluation.engine_v2 import MultiChannelSeatEvaluationEngine
from core.core.seat_evaluation.data_preprocessor import DataPreprocessor
from core.core.seat_evaluation.evaluation_report import EvaluationReportGenerator
from core.core.seat_evaluation.full_timeseries_evaluator import FullTimeseriesEvaluator
from modules.ui.seat_evaluation.visualization_manager import (
    VisualizationManager, ChartStyle, card_adapted_figure,
)
from modules.ui.seat_evaluation.advanced_charts import (
    create_event_timeline, create_psd_comparison, create_comparison_radar,
    create_attenuation_bar, create_srs_comparison,
    verdict_text, verdict_icon, EVENT_COLORS,
)
from core.core.seat_evaluation.imu_location_config import (
    LOCATION_IDS, LOCATION_NAMES, get_location_config, get_channel_by_location,
    IMU_LOCATION_MAPPING, get_all_locations
)
from core.core.data_processing.floor_imu_parser import FloorIMUParser
from core.core.seat_evaluation.metadata_registry import METRIC_THRESHOLDS, get_global_registry, EvaluationDirection
from core.core.seat_evaluation.eval_queue import TYPE_COLORS
try:
    from modules.driving_evaluation.behavior_analyzer import BehaviorAnalyzer
    BEHAVIOR_ANALYZER_AVAILABLE = True
except ImportError:
    BehaviorAnalyzer = None
    BEHAVIOR_ANALYZER_AVAILABLE = False

logger = logging.getLogger(__name__)

BEHAVIOR_COLORS = {
    'hard_acceleration': '#E74C3C',
    'hard_braking': '#E74C3C',
    'sharp_turning': '#F39C12',
    'overspeeding': '#F39C12',
}

BEHAVIOR_LABELS_CN = {
    'hard_acceleration': '急加速',
    'hard_braking': '急刹车',
    'sharp_turning': '急转弯',
    'overspeeding': '超速',
}

STYLE_SHEET = """
QTableWidget {
    font-family: "Microsoft YaHei";
    font-size: 10px;
    gridline-color: #d0d0d0;
    selection-background-color: #d4e6f9;
    selection-color: #333;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background-color: #f0f0f0;
    padding: 6px 8px;
    border: 1px solid #d0d0d0;
    font-weight: bold;
    font-size: 10px;
}
QGroupBox {
    font-family: "Microsoft YaHei";
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    font-family: "Microsoft YaHei";
    font-size: 12px;
    padding: 6px 16px;
    border: 1px solid #bbb;
    border-radius: 4px;
    background-color: #f5f5f5;
}
QPushButton:hover { background-color: #e8f0fe; border-color: #4A90D9; }
QPushButton#btnPrimary {
    background-color: #4A90D9;
    color: white;
    border: none;
}
QPushButton#btnPrimary:hover { background-color: #357ABD; }
QPushButton#btnDanger {
    background-color: #E74C3C;
    color: white;
    border: none;
}
QPushButton#btnDanger:hover { background-color: #C0392B; }
QPushButton#btnSecondary {
    background-color: #F5F5F5;
    color: #333;
    border: 1px solid #ddd;
}
QComboBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}
QLineEdit {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QTextEdit {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}
QFrame#proCard {
    background-color: #FFFFFF;
    border: 1px solid #D0D0D0;
    border-radius: 8px;
    font-family: "Microsoft YaHei";
}
QFrame#proCard:hover {
    border-color: #4A90D9;
}
"""

LC = {
    'bg_primary': '#FFFFFF', 'bg_card': '#FFFFFF', 'bg_input': '#F5F6F8',
    'bg_header': '#EBEDF0', 'bg_hover': '#E8F0FE',
    'accent': '#4A90D9', 'accent_hover': '#357ABD',
    'accent_light': 'rgba(74,144,217,0.10)',
    'text_primary': '#333333', 'text_secondary': '#666666',
    'text_muted': '#999999', 'text_accent': '#4A90D9',
    'border_default': '#D0D0D0', 'border_light': '#E0E0E0',
    'success': '#27AE60', 'warning': '#F39C12', 'danger': '#E74C3C',
    'info': '#4A90D9', 'orange_dark': '#E67E22',
    'improvement_good': '#27AE60',
    'improvement_bad': '#E74C3C',
    'improvement_neutral': '#95A5A6',
}

CARD_STYLE = """
    QFrame#proCard {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 8px;
        font-family: "Microsoft YaHei";
    }
    QFrame#proCard:hover {
        border-color: #4A90D9;
    }
"""

LOCATION_LABELS = {
    'head': '头部眉心', 'torso': '躯干T8', 'seat_r': '座垫R点',
    'seat_bottom': '座椅底部', 'sternum': '胸骨剑突',
}

PREPROCESS_LABELS = {
    0: 'Level 0: 原始数据',
    1: 'Level 1: 零偏校准+坐标系对齐',
    2: 'Level 2: 零偏校准+对齐+10Hz滤波',
}


def _parse_csv_dataset(file_path: str):
    """解析预解析CSV数据集(带imu_name/Ax_m_s2列的手工格式)

    Returns: (multi_channel_data, vehicle_data, sample_info) 同FloorIMUParser格式
    vehicle_data 额外包含 '_raw_records' 字段，用于驾驶行为事件检测
    """
    by_imu = defaultdict(lambda: {'ax': [], 'ay': [], 'az': [],
                                   'gx': [], 'gy': [], 'gz': [],
                                   'timestamps': [], 'speed': [], 'wheel': []})
    raw_records = []  # 保留原始记录用于 DrivingEventDetector

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv_mod.DictReader(f)
        for row in reader:
            imu = row.get('imu_name', '')
            if not imu:
                continue
            try:
                by_imu[imu]['ax'].append(float(row.get('Ax_m_s2', 0)))
                by_imu[imu]['ay'].append(float(row.get('Ay_m_s2', 0)))
                by_imu[imu]['az'].append(float(row.get('Az_m_s2', 0)))
                by_imu[imu]['gx'].append(float(row.get('Gx_dps', 0)))
                by_imu[imu]['gy'].append(float(row.get('Gy_dps', 0)))
                by_imu[imu]['gz'].append(float(row.get('Gz_dps', 0)))
                by_imu[imu]['timestamps'].append(float(row.get('rel_time', 0)))
                by_imu[imu]['speed'].append(float(row.get('speed', 0)))
                by_imu[imu]['wheel'].append(float(row.get('wheel', 0)))
                raw_records.append(row)
            except (ValueError, KeyError):
                continue

    multi_channel_data = {}
    sample_rate = 1000.0

    for imu, data in by_imu.items():
        n = len(data['ax'])
        if n < 2:
            continue
        ts = data['timestamps']
        if len(ts) >= 2 and (ts[-1] - ts[0]) > 0:
            # 使用中位数时间间隔检测采样率 (抗抖动)
            dts = np.diff(ts)
            median_dt = np.median(dts) if len(dts) > 0 else 0.0
            if median_dt > 0:
                sample_rate = 1.0 / median_dt
                std_dt = np.std(dts)
                jitter_ratio = std_dt / median_dt
                if jitter_ratio > 0.5 and std_dt > 0.05:
                    logger.warning(
                        f"时间戳抖动较大 (IMU={imu}): σ={std_dt:.4f}s, "
                        f"中值={median_dt:.4f}s, 抖动比={jitter_ratio:.2%}"
                    )
                elif jitter_ratio > 0.1:
                    logger.info(
                        f"时间戳轻微抖动 (IMU={imu}): σ={std_dt:.4f}s, "
                        f"中值={median_dt:.4f}s, 抖动比={jitter_ratio:.2%} (离线CSV正常)"
                    )
            else:
                sample_rate = (n - 1) / (ts[-1] - ts[0])

        multi_channel_data[imu] = {
            'ax': data['ax'], 'ay': data['ay'], 'az': data['az'],
            'gx': data['gx'], 'gy': data['gy'], 'gz': data['gz'],
            'timestamps': ts,
            'speed': data['speed'], 'wheel': data['wheel'],
        }

    multi_channel_data['_sample_rate'] = sample_rate

    vehicle_data = {
        'speed_data': [],
        'steering_data': [],
        'brake_data': [],
        '_csv_parsed': True,
        '_raw_records': raw_records,
        '_speed_arrays': {imu: data['speed'] for imu, data in by_imu.items()},
        '_wheel_arrays': {imu: data['wheel'] for imu, data in by_imu.items()},
    }

    sample_info = {
        'channels': list(by_imu.keys()),
        'total_records': sum(len(v['ax']) for v in by_imu.values()),
    }

    return multi_channel_data, vehicle_data, sample_info


def _build_records_from_channel_map(channel_data_map: dict, sample_rate: float) -> list:
    """从 channel_data_map (numpy数组) 重建 records 列表供 DrivingEventDetector 使用

    用于 CAN 文件解析路径（非 CSV 预解析格式）。
    提取 ch1 通道 IMU1_头部眉心-1 的数据作为参考通道。
    """
    ref_imu = 'IMU1_头部眉心-1'
    ref_data = channel_data_map.get(ref_imu)
    if ref_data is None:
        # fallback: 取第一个非 _ 开头的通道
        for name, data in channel_data_map.items():
            if not name.startswith('_') and isinstance(data, dict):
                ref_data = data
                ref_imu = name
                break

    if ref_data is None or len(ref_data.get('ax', [])) == 0:
        return []

    n = len(ref_data['ax'])
    ts = ref_data.get('timestamps', np.arange(n) / sample_rate)
    speed = ref_data.get('speed', np.zeros(n))
    wheel = ref_data.get('wheel', np.zeros(n))
    ax = ref_data.get('ax', np.zeros(n))
    ay = ref_data.get('ay', np.zeros(n))
    az = ref_data.get('az', np.zeros(n))
    gx = ref_data.get('gx', np.zeros(n))
    gy = ref_data.get('gy', np.zeros(n))
    gz = ref_data.get('gz', np.zeros(n))

    records = []
    for i in range(n):
        records.append({
            'rel_time': float(ts[i]) if i < len(ts) else float(i) / sample_rate,
            'channel': 'ch1',
            'imu_name': ref_imu,
            'Ax_m_s2': float(ax[i]) if i < len(ax) else 0,
            'Ay_m_s2': float(ay[i]) if i < len(ay) else 0,
            'Az_m_s2': float(az[i]) if i < len(az) else 0,
            'Gx_dps': float(gx[i]) if i < len(gx) else 0,
            'Gy_dps': float(gy[i]) if i < len(gy) else 0,
            'Gz_dps': float(gz[i]) if i < len(gz) else 0,
            'speed': float(speed[i]) if i < len(speed) else 0,
            'wheel': float(wheel[i]) if i < len(wheel) else 0,
        })

    return records


def _is_csv_parsed_format(file_path: str) -> bool:
    """检测CSV是否为预解析格式(非原始CAN日志)"""
    if not file_path.lower().endswith('.csv'):
        return False
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv_mod.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            return 'imu_name' in fieldnames and 'Ax_m_s2' in fieldnames
    except Exception:
        return False

def _is_sqlite_cache_file(file_path: str) -> bool:
    """检测是否为SQLite缓存文件"""
    if not file_path.lower().endswith('.db'):
        return False
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return 'data_records' in tables or 'analysis_results' in tables
    except Exception:
        return False

def _parse_sqlite_cache(file_path: str):
    """从SQLite缓存文件解析数据"""
    
    conn = sqlite3.connect(file_path)
    cursor = conn.execute("SELECT source_type, rel_time, channel, imu_name, payload FROM data_records ORDER BY rel_time")
    
    by_imu = {}
    bad_records = 0
    total_records = 0
    
    for row in cursor.fetchall():
        total_records += 1
        source_type, rel_time, channel, imu_name, payload = row
        try:
            record = json.loads(payload)
        except json.JSONDecodeError:
            bad_records += 1
            continue
        
        imu = imu_name or record.get('imu_name', record.get('_imu_name', channel or 'unknown'))
        if imu not in by_imu:
            by_imu[imu] = {'ax': [], 'ay': [], 'az': [],
                           'gx': [], 'gy': [], 'gz': [],
                           'timestamps': [], 'speed': [], 'wheel': []}
        
        if 'Ax_m_s2' in record:
            by_imu[imu]['ax'].append(float(record['Ax_m_s2']))
            by_imu[imu]['ay'].append(float(record.get('Ay_m_s2', 0)))
            by_imu[imu]['az'].append(float(record.get('Az_m_s2', 0)))
            by_imu[imu]['gx'].append(float(record.get('Gx_dps', 0)))
            by_imu[imu]['gy'].append(float(record.get('Gy_dps', 0)))
            by_imu[imu]['gz'].append(float(record.get('Gz_dps', 0)))
            by_imu[imu]['timestamps'].append(float(rel_time))
            by_imu[imu]['speed'].append(float(record.get('speed', record.get('VehicleSpeed', 0))))
            by_imu[imu]['wheel'].append(float(record.get('wheel', record.get('SteeringAngle', 0))))
        elif 'ax' in record:
            by_imu[imu]['ax'].append(float(record['ax']))
            by_imu[imu]['ay'].append(float(record.get('ay', 0)))
            by_imu[imu]['az'].append(float(record.get('az', 0)))
            by_imu[imu]['gx'].append(float(record.get('gx', 0)))
            by_imu[imu]['gy'].append(float(record.get('gy', 0)))
            by_imu[imu]['gz'].append(float(record.get('gz', 0)))
            by_imu[imu]['timestamps'].append(float(rel_time))
            by_imu[imu]['speed'].append(float(record.get('speed', 0)))
            by_imu[imu]['wheel'].append(float(record.get('wheel', 0)))
    
    conn.close()

    if bad_records > 0:
        pct = bad_records / float(total_records) * 100 if total_records > 0 else 0
        logger.warning(f"SQLite缓存解析: {bad_records}/{total_records} 条损坏记录被跳过 ({pct:.1f}%)")

    multi_channel_data = {}
    sample_rate = 1000.0
    
    for imu, data in by_imu.items():
        n = len(data['ax'])
        if n < 2:
            continue
        ts = data['timestamps']
        if len(ts) >= 2 and (ts[-1] - ts[0]) > 0:
            sample_rate = (n - 1) / (ts[-1] - ts[0])
        
        multi_channel_data[imu] = {
            'ax': data['ax'], 'ay': data['ay'], 'az': data['az'],
            'gx': data['gx'], 'gy': data['gy'], 'gz': data['gz'],
            'timestamps': ts,
            'speed': data['speed'], 'wheel': data['wheel'],
        }
    
    multi_channel_data['_sample_rate'] = sample_rate
    
    vehicle_data = {
        'speed_data': [],
        'steering_data': [],
        'brake_data': [],
        '_csv_parsed': True,
        '_speed_arrays': {imu: data['speed'] for imu, data in by_imu.items()},
        '_wheel_arrays': {imu: data['wheel'] for imu, data in by_imu.items()},
    }
    
    sample_info = {
        'channels': list(by_imu.keys()),
        'total_records': sum(len(v['ax']) for v in by_imu.values()),
    }
    
    return multi_channel_data, vehicle_data, sample_info


class UnifiedEvaluationWorker(QObject):
    """统一评测工作器 — 事件级和全时域模式共用
    - event: 使用 MultiChannelSeatEvaluationEngine
    - full_timeseries: 使用 FullTimeseriesEvaluator (含频谱/STFT/统计检验/可视化)
    """

    progress_updated = Signal(int, str)
    analysis_completed = Signal(dict)
    analysis_failed = Signal(str)

    def __init__(self, engine, preprocessor, report_generator):
        super().__init__()
        self._engine = engine
        self._preprocessor = preprocessor
        self._report_generator = report_generator
        self._is_running = False
        self._dataset_path = ''
        self._preprocess_level = 1
        self._selected_metrics = []
        self._locations = []
        if BEHAVIOR_ANALYZER_AVAILABLE and BehaviorAnalyzer is not None:
            self._behavior_analyzer = BehaviorAnalyzer({
                'hard_accel_threshold': 4.0,
                'hard_brake_threshold': 6.0,
                'sharp_turn_threshold': 30.0,
                'overspeed_threshold': 120.0,
            })
        else:
            self._behavior_analyzer = None
        self._eval_mode = 'event'

    def configure(self, dataset_path: str, preprocess_level: int,
                  selected_metrics: List[str], locations: List[str],
                  eval_mode: str = 'event'):
        self._dataset_path = dataset_path
        self._preprocess_level = preprocess_level
        self._selected_metrics = selected_metrics
        self._locations = locations
        self._eval_mode = eval_mode

    def run(self):
        self._is_running = True
        try:
            self.progress_updated.emit(5, '正在加载数据集...')

            if _is_csv_parsed_format(self._dataset_path):
                parse_result = _parse_csv_dataset(self._dataset_path)
            elif _is_sqlite_cache_file(self._dataset_path):
                self.progress_updated.emit(8, '正在从SQLite缓存加载数据...')
                parse_result = _parse_sqlite_cache(self._dataset_path)
            else:
                parser = FloorIMUParser()
                parse_result = parser.parse_file_and_select(self._dataset_path)

            if not parse_result or parse_result[0] is None:
                self.analysis_failed.emit('数据集解析失败，请检查文件格式')
                return

            multi_channel_data, vehicle_data, sample_info = parse_result
            is_csv = vehicle_data.get('_csv_parsed', False)
            detected_sr = multi_channel_data.get('_sample_rate', 1000.0)

            csv_speed_arrays = vehicle_data.get('_speed_arrays', {}) if is_csv else {}
            csv_wheel_arrays = vehicle_data.get('_wheel_arrays', {}) if is_csv else {}

            self.progress_updated.emit(15, '正在提取各通道数据...')

            channel_data_map = {}
            for ch_name in multi_channel_data:
                if ch_name.startswith('_'):
                    continue
                ch_data = multi_channel_data[ch_name]
                ax = np.array(ch_data.get('ax', []))
                ay = np.array(ch_data.get('ay', []))
                az = np.array(ch_data.get('az', []))
                gx = np.array(ch_data.get('gx', []))
                gy = np.array(ch_data.get('gy', []))
                gz = np.array(ch_data.get('gz', []))
                ts = np.array(ch_data.get('timestamps', []))
                if len(ts) == 0 and len(ax) > 0:
                    ts = np.arange(len(ax)) / detected_sr
                ch_speed = np.array(ch_data.get('speed', []))
                ch_wheel = np.array(ch_data.get('wheel', []))
                channel_data_map[ch_name] = {
                    'ax': ax, 'ay': ay, 'az': az,
                    'gx': gx, 'gy': gy, 'gz': gz,
                    'timestamps': ts, 'sample_rate': detected_sr,
                    'speed': ch_speed, 'wheel': ch_wheel,
                }

            self.progress_updated.emit(25, '正在执行数据预处理...')

            preprocessor = DataPreprocessor(sample_rate=detected_sr, lowpass_cutoff=10.0)
            preprocessed_channels = {}

            for ch_name, ch_data in channel_data_map.items():
                if self._preprocess_level > 0 and len(ch_data['ax']) > 4:
                    acc_2d = np.column_stack([ch_data['ax'], ch_data['ay'], ch_data['az']])
                    gyro_2d = np.column_stack([ch_data['gx'], ch_data['gy'], ch_data['gz']])
                    processed = preprocessor.process(
                        acc_2d, gyro_2d,
                        ch_data['timestamps'], level=self._preprocess_level
                    )
                    preprocessed_channels[ch_name] = {
                        'ax': processed['acc'][:, 0] if processed['acc'].ndim > 1 else processed['acc'],
                        'ay': processed['acc'][:, 1] if processed['acc'].ndim > 1 else np.zeros_like(processed['acc']),
                        'az': processed['acc'][:, 2] if processed['acc'].ndim > 1 else np.zeros_like(processed['acc']),
                        'gx': processed.get('gyro', ch_data.get('gx', np.array([]))),
                        'gy': processed.get('gyro', ch_data.get('gy', np.array([]))),
                        'gz': processed.get('gyro', ch_data.get('gz', np.array([]))),
                        'timestamps': processed['timestamps'],
                        '_preprocess_level': self._preprocess_level,
                    }
                else:
                    preprocessed_channels[ch_name] = ch_data

            self.progress_updated.emit(35, '正在计算评测指标...')

            location_results = {}
            total_locations = len(self._locations)
            for idx, loc_id in enumerate(self._locations):
                if not self._is_running:
                    return

                loc_config = get_location_config(loc_id)
                if not loc_config:
                    continue

                metric_results = {}

                for group_tag in ['experimental', 'control']:
                    channel_id = get_channel_by_location(loc_id, group_tag)
                    if not channel_id:
                        continue

                    ch_data = preprocessed_channels.get(channel_id)
                    if ch_data is None:
                        continue

                    data_window = {
                        'ax': ch_data['ax'] / 9.81 if len(ch_data['ax']) > 0 else np.array([]),
                        'ay': ch_data['ay'] / 9.81 if len(ch_data['ay']) > 0 else np.array([]),
                        'az': ch_data['az'] / 9.81 if len(ch_data['az']) > 0 else np.array([]),
                        'sample_rate': ch_data.get('sample_rate', detected_sr),
                        'speed': np.array(ch_data.get('speed', [])),
                        'wheel': np.array(ch_data.get('wheel', [])),
                        '_unit': 'g',
                        '_converted_from': 'm/s²',
                        '_preprocess_level': ch_data.get('_preprocess_level', 0),
                    }

                    metrics = {}
                    for metric_id in self._selected_metrics:
                        if metric_id == 'ATTEN_H':
                            continue  # ATTEN_H is computed post-hoc as a cross-group metric
                        # ── 数据有效性前置检查 ──
                        if len(ch_data.get('ax', [])) < 10:
                            metrics[metric_id] = float('nan')
                            metrics[f'{metric_id}_status'] = 'insufficient_data'
                            continue
                        try:
                            value = self._engine._calculate_single_metric(metric_id, data_window)
                            metrics[metric_id] = value
                            metrics[f'{metric_id}_status'] = 'ok'
                        except ValueError as e:
                            metrics[metric_id] = float('nan')
                            metrics[f'{metric_id}_status'] = 'value_error'
                            metrics[f'{metric_id}_error'] = str(e)[:200]
                        except Exception as e:
                            metrics[metric_id] = float('nan')
                            metrics[f'{metric_id}_status'] = 'computation_error'
                            metrics[f'{metric_id}_error'] = f'{type(e).__name__}: {str(e)[:200]}'

                    profile = self._engine._build_vibration_profile(
                        data_window, metrics, loc_id
                    )

                    metric_results[group_tag] = {
                        'metrics': metrics,
                        'profile': profile,
                        'data_window': data_window,
                    }

                exp = metric_results.get('experimental', {})
                ctrl = metric_results.get('control', {})

                # ── ATTEN_H 后计算 ──
                # η_H = (DISP_HR_ctrl - DISP_HR_exp) / DISP_HR_ctrl × 100%
                exp_hr = exp.get('metrics', {}).get('DISP_HR', 0.0)
                ctrl_hr = ctrl.get('metrics', {}).get('DISP_HR', 0.0)
                if abs(ctrl_hr) > 1e-9:
                    atten_h = (ctrl_hr - exp_hr) / ctrl_hr * 100.0
                else:
                    atten_h = 0.0
                exp.setdefault('metrics', {})['ATTEN_H'] = atten_h
                ctrl.setdefault('metrics', {})['ATTEN_H'] = atten_h

                exp_profile = exp.get('profile')
                ctrl_profile = ctrl.get('profile')

                contrast = {}
                if exp_profile and ctrl_profile:
                    contrast = self._engine._build_contrast_profile(
                        exp_profile, ctrl_profile, loc_id,
                        exp_metrics=exp.get('metrics'),
                        ctrl_metrics=ctrl.get('metrics'),
                    )

                location_results[loc_id] = {
                    'profile': exp_profile,
                    'contrast': contrast,
                    'control_profile': ctrl_profile,
                    'metrics': exp.get('metrics', {}),
                    'control_metrics': ctrl.get('metrics', {}),
                }

                progress_pct = 35 + int((idx + 1) / max(total_locations, 1) * 30)
                self.progress_updated.emit(progress_pct,
                    f'正在计算: {LOCATION_LABELS.get(loc_id, loc_id)} ({idx+1}/{total_locations})')

            self.progress_updated.emit(68, '正在分析驾驶行为...')

            behavior_summary = {
                'hard_acceleration_count': 0,
                'hard_braking_count': 0,
                'sharp_turning_count': 0,
                'overspeeding_count': 0,
                'events': [],
                'total_events': 0,
                'event_types': {},
            }

            # 获取原始记录用于 DrivingEventDetector
            raw_records = vehicle_data.get('_raw_records', None)

            if raw_records is None and not is_csv:
                # CAN 文件路径: 从 channel_data_map 重建 records
                raw_records = _build_records_from_channel_map(channel_data_map, detected_sr)

            if raw_records:
                try:
                    from core.core.analysis.data_bridge import DataBridge
                    bridge = DataBridge()
                    batch_result = bridge.analyze_behavior_batch(
                        raw_records, ref_channel='ch1', ref_imu='IMU1_头部眉心-1'
                    )

                    events = batch_result.get('events', [])
                    summary = batch_result.get('summary', {})
                    by_type = summary.get('by_type', {})

                    # ── 丰富事件：附加瞬时车速查找 ──
                    # 使用 NumPy 数组 + searchsorted 替代 round() 字典，避免高采样率键冲突
                    _speed_ts = np.array([float(rec.get('rel_time', rec.get('timestamp', 0)))
                                           for rec in raw_records], dtype=np.float64)
                    _speed_vals = np.array([float(rec.get('speed', 0))
                                             for rec in raw_records], dtype=np.float64)

                    for evt in events:
                        t0 = evt.get('t_start', 0)
                        t1 = evt.get('t_end', 0)
                        evt['speed_at_start'] = round(_lookup_speed_by_time(_speed_ts, _speed_vals, t0), 1)
                        evt['speed_at_end'] = round(_lookup_speed_by_time(_speed_ts, _speed_vals, t1), 1)
                        evt['speed_delta'] = round(evt['speed_at_end'] - evt['speed_at_start'], 1)

                    MAX_DISPLAY_EVENTS = 200
                    behavior_summary['events'] = events[:MAX_DISPLAY_EVENTS]
                    behavior_summary['_truncated'] = len(events) > MAX_DISPLAY_EVENTS
                    behavior_summary['_total_detected'] = len(events)
                    if behavior_summary['_truncated']:
                        logger.warning(f"驾驶事件列表被截断: 展示{MAX_DISPLAY_EVENTS}/{len(events)}个事件")
                    behavior_summary['total_events'] = len(events)
                    behavior_summary['event_types'] = {
                        et: info['count']
                        for et, info in by_type.items()
                    }
                    behavior_summary['vehicle_accel_range'] = batch_result.get(
                        'vehicle_accel_range', (0.0, 0.0))

                    # 向后兼容旧字段
                    behavior_summary['hard_acceleration_count'] = by_type.get(
                        'aggressive_accel', {}).get('count', 0)
                    behavior_summary['hard_braking_count'] = by_type.get(
                        'hard_brake', {}).get('count', 0)
                    behavior_summary['sharp_turning_count'] = by_type.get(
                        'tight_turn', {}).get('count', 0)

                    logger.info(
                        f"[驾驶行为] 检测完成: {len(events)} 个事件, "
                        f"{len(by_type)} 种类型"
                    )
                except Exception as e:
                    logger.warning(f"驾驶行为检测失败(非致命): {e}")
                    traceback.print_exc()
            
            self.progress_updated.emit(72, '正在生成报告...')

            duration_s = 0.0
            for ch_data in channel_data_map.values():
                ts_arr = ch_data.get('timestamps', np.array([]))
                if len(ts_arr) > 0:
                    duration_s = max(duration_s, float(ts_arr[-1] - ts_arr[0]))

            location_results['preprocess_level'] = self._preprocess_level
            location_results['sample_rate'] = detected_sr
            location_results['duration_s'] = duration_s
            location_results['behavior_summary'] = behavior_summary

            all_speeds = []
            all_wheels = []
            for ch_data in channel_data_map.values():
                sp = np.array(ch_data.get('speed', []))
                wh = np.array(ch_data.get('wheel', []))
                if len(sp) > 0:
                    all_speeds.append(sp)
                if len(wh) > 0:
                    all_wheels.append(wh)

            vehicle_summary = {}
            if all_speeds:
                combined_speed = np.concatenate(all_speeds)
                vehicle_summary['speed_mean'] = float(np.mean(combined_speed))
                vehicle_summary['speed_std'] = float(np.std(combined_speed))
                vehicle_summary['speed_median'] = float(np.median(combined_speed))
                vehicle_summary['speed_max'] = float(np.max(combined_speed))
                # 自适应 bins: Freedman-Diaconis 规则，适应不同车速范围
                iqr = np.percentile(combined_speed, 75) - np.percentile(combined_speed, 25)
                bin_width = 2 * iqr / (len(combined_speed) ** (1/3))
                bin_width = max(2.0, min(20.0, bin_width))  # clamp [2, 20] km/h
                vmax = np.percentile(combined_speed, 99)
                vmin = 0.0
                speed_bins = list(np.arange(vmin, vmax + bin_width, bin_width))
                hist, _ = np.histogram(combined_speed, bins=speed_bins)
                vehicle_summary['speed_histogram'] = {
                    'bins': speed_bins,
                    'counts': hist,
                    'labels': [f'{speed_bins[i]:.0f}-{speed_bins[i+1]:.0f}' for i in range(len(speed_bins)-1)],
                }
            if all_wheels:
                combined_wheel = np.concatenate(all_wheels)
                vehicle_summary['wheel_mean'] = float(np.mean(np.abs(combined_wheel)))
                vehicle_summary['wheel_max'] = float(np.max(np.abs(combined_wheel)))
                turning_ratio = float(np.sum(np.abs(combined_wheel) > 10) / len(combined_wheel) * 100)
                vehicle_summary['turning_ratio_pct'] = turning_ratio

            location_results['vehicle_summary'] = vehicle_summary

            # ---- 全时域专家评测 (使用 FullTimeseriesEvaluator，所有模式均生成) ----
            full_timeseries_result = None
            self.progress_updated.emit(75, '正在执行全时域专家评测...')
            try:
                evaluator = FullTimeseriesEvaluator()
                if not self._is_running: return
                self.progress_updated.emit(78, '加载数据...')
                evaluator.load_from_csv(self._dataset_path)
                
                if not self._is_running: return
                self.progress_updated.emit(80, '检测事件...')
                evaluator.detect_events()
                
                if not self._is_running: return
                self.progress_updated.emit(83, '滑动窗口分析...')
                evaluator.window_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(86, '事件窗口分析...')
                evaluator.event_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(87, '频谱分析...')
                evaluator.spectrum_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(89, '时频分析...')
                evaluator.stft_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(92, '统计学检验...')
                evaluator.statistical_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(94, '统计特征...')
                evaluator.comprehensive_metrics()
                
                if not self._is_running: return
                output_dir = os.path.join(
                    os.path.dirname(self._dataset_path),
                    f"expert_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                
                # 构建 results 数据（在 generate_report 之前，避免因 to_csv 等异常丢失数据）
                full_timeseries_result = {
                    'events': evaluator.events,
                    'results': evaluator.results,
                }
                
                if not self._is_running: return
                self.progress_updated.emit(96, '生成报告...')
                try:
                    evaluator.generate_report(output_dir)
                    full_timeseries_result['output_dir'] = output_dir
                except Exception as report_err:
                    logger.warning(f"报告生成失败(非致命): {report_err}")
                
                if not self._is_running: return
                self.progress_updated.emit(98, '生成图表...')
                try:
                    viz_manager = VisualizationManager()
                    viz_manager.generate_all_plots(evaluator, output_dir)
                    num_plots = len([f for f in os.listdir(output_dir) if f.endswith('.png')])
                    full_timeseries_result['num_plots'] = num_plots
                except Exception as plot_err:
                    logger.warning(f"PNG图表生成失败(非致命): {plot_err}")
                    full_timeseries_result['num_plots'] = 0
            except Exception as e:
                tb = traceback.format_exc()
                logger.warning(f"全时域评测失败(非致命): {e}\n{tb}")
                full_timeseries_result = {'error': str(e), 'traceback': tb}
                if hasattr(self, '_status_label') and self._status_label:
                    self._status_label.setText(f"⚠ 全时域评测失败: {e}")
                    self._status_label.setStyleSheet(
                        f"color: #E74C3C; font-size: 11px; padding: 7px 12px; "
                        f"background: {LC['bg_card']}; border: 1px solid #E74C3C; border-radius: 6px;")

            location_results['_full_timeseries'] = full_timeseries_result

            # ── 概览图原始数据 (驾驶行为事件卡片的时序概览图) ──
            overview_data = None
            exp_head_ch = None
            ctrl_head_ch = None
            for ch_name in channel_data_map:
                if ch_name.startswith('_'):
                    continue
                try:
                    imu_num = int(ch_name.split('_')[0].replace('IMU', ''))
                except (ValueError, IndexError):
                    continue
                # 第一优先: 查找座垫R点通道 (IMU5_座垫R点-1 / IMU6_座垫R点-2)
                is_seat_r = '座垫' in ch_name or 'R点' in ch_name or 'seat_r' in ch_name.lower()
                if imu_num % 2 == 1 and is_seat_r and exp_head_ch is None:
                    exp_head_ch = ch_name
                elif imu_num % 2 == 0 and is_seat_r and ctrl_head_ch is None:
                    ctrl_head_ch = ch_name

            # 第二优先: 查找头部通道 (IMU1_头部眉心-1 / IMU2_头部眉心-2)
            if exp_head_ch is None or ctrl_head_ch is None:
                for ch_name in channel_data_map:
                    if ch_name.startswith('_'):
                        continue
                    try:
                        imu_num = int(ch_name.split('_')[0].replace('IMU', ''))
                    except (ValueError, IndexError):
                        continue
                    is_head = 'head' in ch_name.lower() or '头部' in ch_name
                    if imu_num % 2 == 1 and is_head and exp_head_ch is None:
                        exp_head_ch = ch_name
                    elif imu_num % 2 == 0 and is_head and ctrl_head_ch is None:
                        ctrl_head_ch = ch_name

            # 回退：如果没找到 head 通道，取第一个实验/对照通道
            for ch_name in channel_data_map:
                if ch_name.startswith('_'):
                    continue
                try:
                    imu_num = int(ch_name.split('_')[0].replace('IMU', ''))
                except (ValueError, IndexError):
                    continue
                if imu_num % 2 == 1 and exp_head_ch is None:
                    exp_head_ch = ch_name
                elif imu_num % 2 == 0 and ctrl_head_ch is None:
                    ctrl_head_ch = ch_name

            if exp_head_ch and ctrl_head_ch:
                exp_data = channel_data_map[exp_head_ch]
                ctrl_data = channel_data_map[ctrl_head_ch]
                ts = exp_data.get('timestamps', np.array([]))
                # 速度/方向盘取任意通道
                sp_arr = np.array(exp_data.get('speed', []))
                wh_arr = np.array(exp_data.get('wheel', []))

                # 按通道名判断实际 IMU 位置，用于图表标题动态显示
                if '座垫' in exp_head_ch or 'R点' in exp_head_ch or 'seat_r' in exp_head_ch.lower():
                    loc_label = '座垫R点'
                elif '头部' in exp_head_ch or 'head' in exp_head_ch.lower():
                    loc_label = '头部眉心'
                else:
                    loc_label = exp_head_ch.split('_')[0] if '_' in exp_head_ch else exp_head_ch[:8]

                overview_data = {
                    'timestamps': ts,
                    'speed': sp_arr,
                    'wheel': wh_arr,
                    'exp_ax': exp_data.get('ax', np.array([])),
                    'exp_ay': exp_data.get('ay', np.array([])),
                    'exp_az': exp_data.get('az', np.array([])),
                    'ctrl_ax': ctrl_data.get('ax', np.array([])),
                    'ctrl_ay': ctrl_data.get('ay', np.array([])),
                    'ctrl_az': ctrl_data.get('az', np.array([])),
                    'exp_channel': exp_head_ch,
                    'ctrl_channel': ctrl_head_ch,
                    'location_label': loc_label,
                }

                # ── 多部位数据采集: 头部/胸剑突/座垫R点/座椅底部 ──
                BODY_PART_KEYWORDS = {
                    'head': ['头部', 'head', '眉心'],
                    'sternum': ['胸骨', 'sternum', '剑突'],
                    'seat_r': ['座垫', 'R点', 'seat_r'],
                    'seat_bottom': ['座椅底部', 'seat_bottom', '地板'],
                }
                BODY_PART_LABELS = {
                    'head': '头部', 'sternum': '胸剑突',
                    'seat_r': '座垫R点', 'seat_bottom': '座椅底部',
                }
                multi_location = {}
                for part_id, keywords in BODY_PART_KEYWORDS.items():
                    exp_ch = None
                    ctrl_ch = None
                    for ch_name in channel_data_map:
                        if ch_name.startswith('_'):
                            continue
                        try:
                            imu_num = int(ch_name.split('_')[0].replace('IMU', ''))
                        except (ValueError, IndexError):
                            continue
                        if not any(kw in ch_name for kw in keywords):
                            continue
                        if imu_num % 2 == 1:
                            exp_ch = ch_name
                        else:
                            ctrl_ch = ch_name
                    if exp_ch and ctrl_ch:
                        ed = channel_data_map[exp_ch]
                        cd = channel_data_map[ctrl_ch]
                        multi_location[part_id] = {
                            'label': BODY_PART_LABELS.get(part_id, part_id),
                            'exp_ax': np.array(ed.get('ax', [])),
                            'exp_ay': np.array(ed.get('ay', [])),
                            'exp_az': np.array(ed.get('az', [])),
                            'ctrl_ax': np.array(cd.get('ax', [])),
                            'ctrl_ay': np.array(cd.get('ay', [])),
                            'ctrl_az': np.array(cd.get('az', [])),
                            'timestamps': np.array(ed.get('timestamps', [])),
                            'exp_ch': exp_ch, 'ctrl_ch': ctrl_ch,
                        }
                overview_data['multi_location'] = multi_location if multi_location else None
            location_results['_overview_data'] = overview_data

            report = self._report_generator.generate_full_statistics_report(
                os.path.basename(self._dataset_path),
                location_results,
                'full'
            )
            # 注入 report generator 跳过的顶层 key
            report['_full_timeseries'] = full_timeseries_result
            report['_overview_data'] = overview_data
            report['_channel_data_map'] = channel_data_map  # 高级图表需要
            report['behavior_summary'] = behavior_summary

            self.progress_updated.emit(100, '分析完成')
            self.analysis_completed.emit(report)

        except Exception as e:
            logger.error(f"全量统计分析失败: {e}", exc_info=True)
            self.analysis_failed.emit(f'分析失败: {str(e)}')
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False


class IndicatorDetailDialog(QDialog):
    """指标详情对话框 — 与实例视图保持一致的结构化展示"""

    def __init__(self, indicator_code: str, registry, parent=None):
        super().__init__(parent)
        self._indicator_code = indicator_code
        self._registry = registry
        self._meta = registry.get_indicator_meta(indicator_code)
        self._detail = registry.get_indicator_detail(indicator_code)
        self._threshold = registry.get_threshold(indicator_code)

        self.setWindowTitle(f"指标详情 — {self._meta.display_name_cn if self._meta else indicator_code}")
        self.setMinimumSize(680, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(10)

        if not self._meta:
            cl.addWidget(QLabel("未找到指标元数据"))
        else:
            cl.addWidget(self._build_basic_info_card())
            cl.addWidget(self._build_formula_card())
            cl.addWidget(self._build_pipeline_card())
            cl.addWidget(self._build_threshold_card())

        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {LC['bg_input']}; color: {LC['text_primary']}; "
            f"border: 1px solid {LC['border_default']}; border-radius: 3px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {LC['bg_header']}; }}"
        )
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        return card

    def _build_basic_info_card(self) -> QFrame:
        card = self._make_card()
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        title = QLabel("基本信息")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};")
        l.addWidget(title)

        html = (
            f"<table style='font-size:10px;width:100%;border-collapse:collapse;'>"
            f"<tr><td style='color:{LC['text_muted']};width:100px;'>指标编码</td>"
            f"<td style='color:{LC['text_accent']};font-weight:600;'>{self._meta.code}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>中文名称</td><td>{self._meta.display_name_cn}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>英文名称</td><td>{self._meta.display_name_en}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>评测维度</td><td>{self._meta.evaluation_dimension}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>适用位置</td><td>{', '.join(self._meta.applicable_locations)}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>单位</td><td>{self._meta.unit}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>精度</td><td>{self._meta.precision} 位小数</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>IMU来源</td><td>{', '.join(self._meta.source_imus)}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>原始字段</td><td>{', '.join(self._meta.source_raw_fields)}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>前置派生</td><td>{', '.join(self._meta.prerequisite_derived) if self._meta.prerequisite_derived else '无'}</td></tr>"
            f"</table>"
        )
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent;")
        l.addWidget(lbl)

        if self._meta.standard_refs:
            l.addWidget(QLabel(""))
            refs_html = (
                f"<div style='font-size:10px;color:{LC['text_muted']};border-top:1px solid {LC['border_light']};padding-top:4px;'>"
                f"<b>标准引用:</b><br>"
                + "<br>".join([f"• {r}" for r in self._meta.standard_refs])
                + "</div>"
            )
            refs_lbl = QLabel(refs_html)
            refs_lbl.setWordWrap(True)
            refs_lbl.setStyleSheet("background: transparent;")
            l.addWidget(refs_lbl)

        return card

    def _build_formula_card(self) -> QFrame:
        card = self._make_card()
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        title = QLabel("计算公式")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};")
        l.addWidget(title)

        formula_view = QTextEdit()
        formula_view.setReadOnly(True)
        formula_view.setStyleSheet(
            f"font-family: Consolas, Microsoft YaHei; font-size: 10px; "
            f"background-color: #1E1E1E; color: #D4D4D4; "
            f"border: 1px solid #333; border-radius: 3px;"
        )
        formula_view.setMinimumHeight(60)

        content = f"{self._meta.formula_text}\n\nLaTeX: {self._meta.formula_latex}"
        if self._detail:
            content += f"\n\n计算逻辑: {self._detail.calculation_logic}"
            content += f"\n\n公式推导: {self._detail.formula_detail}"
        formula_view.setText(content)

        l.addWidget(formula_view)
        return card

    def _build_pipeline_card(self) -> QFrame:
        card = self._make_card()
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        title = QLabel("算子管线")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};")
        l.addWidget(title)

        pipeline_html = (
            f"<div style='font-size:11px;padding:6px;background:{LC['bg_input']};border-radius:4px;'>"
            f"<b>管线:</b> {' → '.join(self._meta.operator_pipeline)}"
        )
        if self._detail and self._detail.operator_pipeline_detail:
            pipeline_html += f"<br><br><b>详情:</b><br>{self._detail.operator_pipeline_detail}"
        pipeline_html += "</div>"

        if self._detail and self._detail.data_fields:
            pipeline_html += (
                f"<div style='font-size:10px;color:{LC['text_muted']};margin-top:6px;padding:4px;background:{LC['bg_input']};border-radius:4px;'>"
                f"<b>数据字段:</b> {self._detail.data_fields}"
                f"</div>"
            )

        lbl = QLabel(pipeline_html)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent;")
        l.addWidget(lbl)
        return card

    def _build_threshold_card(self) -> QFrame:
        card = self._make_card()
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        title = QLabel("阈值与判定")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};")
        l.addWidget(title)

        pass_val = self._meta.threshold_pass or (self._threshold.get('pass') if self._threshold else '-')
        warn_val = (self._threshold.get('warn') if self._threshold else '-')
        excellent = self._meta.threshold_excellent or '-'
        direction = self._meta.direction.name

        html = (
            f"<table style='font-size:10px;width:100%;border-collapse:collapse;'>"
            f"<tr><td style='color:{LC['text_muted']};width:100px;'>通过阈值</td>"
            f"<td style='color:{LC['success']};font-weight:600;'>{pass_val}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>警告阈值</td><td>{warn_val}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>优秀基线</td><td>{excellent}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>判定方向</td><td>{direction}</td></tr>"
            f"</table>"
        )
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent;")
        l.addWidget(lbl)

        if self._meta.standard_refs:
            l.addWidget(QLabel(""))
            refs_html = (
                f"<div style='font-size:10px;color:{LC['text_muted']};border-top:1px solid {LC['border_light']};padding-top:4px;'>"
                f"<b>行业参考:</b><br>"
                + "<br>".join([f"• {r}" for r in self._meta.standard_refs])
                + "</div>"
            )
            refs_lbl = QLabel(refs_html)
            refs_lbl.setWordWrap(True)
            refs_lbl.setStyleSheet("background: transparent;")
            l.addWidget(refs_lbl)

        return card


# ═══════════════════════════════════════════════════════════════
# 维度名称映射: Registry 细粒度 → UI 粗粒度（统一用于排序和着色）
# ═══════════════════════════════════════════════════════════════
DIMENSION_MAP = {
    '时域-冲击': '瞬态-冲击', '冲击域-结构响应': '瞬态-冲击',
    '冲击域-参数': '瞬态-冲击', '冲击域-响应': '瞬态-冲击',
    '冲击域-隔振效率': '瞬态-冲击',
    '频域-传递特性': '稳态-舒适度', '频域-舒适度': '稳态-舒适度',
    '频域-综合': '稳态-舒适度', '频域-方向性': '稳态-舒适度',
    '时域-剂量': '动态-响应', '时域-位移': '动态-响应',
    '隔振-综合': '动态-响应',
    '疲劳-计数': '疲劳-损伤', '疲劳-累积损伤': '疲劳-损伤',
    '疲劳-剩余寿命': '疲劳-损伤',
    '时频域-频率': '时频-分析', '时频域-扩展': '时频-分析',
    '时频域-集中度': '时频-分析',
    '生物力学-脊柱': '生物力学',
    '通用-振动能量': '通用-基础', '通用-冲击强度': '通用-基础',
}

DIMENSION_ORDER = {
    '瞬态-冲击': 0, '稳态-舒适度': 1, '动态-响应': 2,
    '疲劳-损伤': 3, '时频-分析': 4, '生物力学': 5, '通用-基础': 6,
}

DIM_COLORS = {
    '瞬态-冲击': '#E74C3C', '稳态-舒适度': '#4A90D9',
    '动态-响应': '#27AE60', '疲劳-损伤': '#F39C12',
    '时频-分析': '#9B59B6', '生物力学': '#2ECC71',
    '通用-基础': '#95A5A6',
}

# 按评测模块分组的全部27个考核指标
ALL_METRIC_GROUPS: List[tuple] = [
    ("瞬态冲击", ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT']),
    ("稳态舒适", ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'OVTV', 'R_FACTOR']),
    ("动态响应", ['VDV_Z', 'TR_Z', 'DISP_HR', 'DISP_TR', 'ATTEN_H']),
    ("疲劳耐久", ['RFC_CC', 'FDS_D', 'FDS_R']),
    ("时频分析", ['STFT_FC', 'STFT_KT', 'STFT_CE']),
    ("通用综合", ['ACC_RMS', 'ACC_PEAK', 'S_D']),
]


def _extract_metric_value(raw):
    """从指标值中提取纯数值，兼容 enriched 格式 {'value': N} 和裸值"""
    if isinstance(raw, dict):
        return raw.get('value')
    if isinstance(raw, (int, float)):
        return raw
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _lookup_speed_by_time(speed_ts: np.ndarray, speed_vals: np.ndarray, t_val: float) -> float:
    """NumPy 二分查找最接近 t_val 的车速"""
    if len(speed_ts) == 0:
        return 0.0
    idx = np.searchsorted(speed_ts, t_val)
    idx = min(idx, len(speed_vals) - 1)
    return float(speed_vals[idx])


class StatisticsAnalysisTab(QWidget):
    """序列统计分析与驾驶行为事件分析标签页"""

    # ── 数据源模式 ──
    class DataSourceMode(Enum):
        OFFLINE_FILE = "offline_file"   # 离线 CSV/TXT 文件（现有）
        SQLITE_CACHE = "sqlite_cache"   # SQLite 缓存数据集（新增）

    analysis_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager

        self._engine = MultiChannelSeatEvaluationEngine()
        self._report_generator = EvaluationReportGenerator()
        self._registry = get_global_registry()
        self._worker = None
        self._worker_thread = None
        self._current_report = None
        self._current_timeseries_result = None
        self._contrast_data = []
        self._dataset_path = ''
        self._selected_metrics = []  # 用户勾选的评测指标

        self._pipeline_labels = ['加载数据', '提取通道', '预处理', '指标计算', '生成报告']
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder

        self._trip_summary = None
        self._behavior_events_for_timeline = []  # 行为事件列表（含时间戳）
        self._type_labels: Dict[str, str] = {}

        # ── 数据源模式 ──
        self._data_source_mode = self.DataSourceMode.OFFLINE_FILE
        self._cache_registry = None           # CacheRegistry 引用
        self._selected_cache_id: str = ''     # 当前选中的缓存 ID
        self._time_range: Tuple[float, float] = (0.0, 0.0)  # 分析时间范围

        self._init_ui()
        self.logger.info("全量统计分析标签页已初始化")

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet(
            f"QScrollArea {{ background: #F0F2F5; border: none; }}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: #C0C4CC; border-radius: 3px; min-height: 30px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: #909399; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        outer_layout.addWidget(self._scroll_area)

        content = QWidget()
        self._content_widget = content

        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self._empty_guide = self._create_empty_guide()
        main_layout.addWidget(self._empty_guide)

        self._control_card = self._create_control_card()
        main_layout.addWidget(self._control_card)

        pipeline_card = self._create_pipeline_indicator()
        main_layout.addWidget(pipeline_card)

        # ════════════════════════════════════════════════════════════
        # 卡片布局顺序（递进式）:
        #   控制 → 概览 → 行为 → 时间轴 → 剖面 → 对照 →
        #   全时域 → 衰减 → 检验 → 输出
        # ════════════════════════════════════════════════════════════

        # ════ 1. 分析总览 ════
        self._overview_group = self._create_section_group("1. 分析总览")
        self._overview_group.setVisible(True)
        main_layout.addWidget(self._overview_group)

        self._overview_container = self._create_overview_dashboard()
        self._overview_group._content_layout.addWidget(self._overview_container)

        self._condition_overview_card = self._create_condition_overview_card()
        self._overview_group._content_layout.addWidget(self._condition_overview_card)

        # ════ 1.2 驾驶行为事件 ════
        self._behavior_events_card = self._create_behavior_events_card()
        main_layout.addWidget(self._behavior_events_card)

        # ════ 2. 行程时间轴 (已清除) ════
        timeline_card = self._create_timeline_card()
        timeline_card.setVisible(False)
        main_layout.addWidget(timeline_card)

        # ════ 3. 多通道剖面分析 ════
        self._profile_group = self._create_section_group("3. 多通道剖面分析")
        self._profile_group.setVisible(True)
        main_layout.addWidget(self._profile_group)

        results_card = self._create_results_card()
        self._profile_group._content_layout.addWidget(results_card)

        detail_card = self._create_detail_card()
        self._profile_group._content_layout.addWidget(detail_card)

        self._freq_card = self._create_frequency_card()
        self._profile_group._content_layout.addWidget(self._freq_card)

        self._trans_card = self._create_transmission_card()
        self._profile_group._content_layout.addWidget(self._trans_card)

        self._temporal_card = self._create_temporal_card()
        self._profile_group._content_layout.addWidget(self._temporal_card)

        # ════ 4. 全时域滑动窗口评测 ════
        self._fulltimeseries_group = self._create_section_group("5. 全时域滑动窗口评测")
        self._fulltimeseries_group.setVisible(True)
        main_layout.addWidget(self._fulltimeseries_group)

        self._sliding_window_card = self._create_sliding_window_card()
        self._fulltimeseries_group._content_layout.addWidget(self._sliding_window_card)

        # ════ 6. 全部驾驶事件 Ay对比 ════
        self._events_ay_overview_card = self._create_events_ay_overview_card()
        self._events_ay_overview_card.setVisible(True)
        main_layout.addWidget(self._events_ay_overview_card)

        # ════ 7. 频段衰减分析 ════
        self._spectrum_group = self._create_section_group("7. 频段衰减分析")
        self._spectrum_group.setVisible(True)
        main_layout.addWidget(self._spectrum_group)

        self._band_attenuation_card = self._create_band_attenuation_card()
        self._spectrum_group._content_layout.addWidget(self._band_attenuation_card)

        # ── 8. PSD 功率谱密度对比（移至 7.2 之前）──
        self._advanced_psd_card = self._create_advanced_card("8. PSD 功率谱密度对比",
            "头部眉心 / 座垫R点 / 座椅底部 三轴功率谱", "psd")
        self._spectrum_group._content_layout.addWidget(self._advanced_psd_card)

        # 一行为三个位置的 PSD 容器创建横向排列
        psd_layout = self._advanced_psd_card.layout()
        # 从卡片的垂直布局中取出 _advanced_psd_container（由 _create_advanced_card 添加）
        psd_layout.removeWidget(self._advanced_psd_container)

        # 创建座垫R点和座椅底部的额外容器
        self._advanced_psd_container_seatr = QWidget()
        self._advanced_psd_container_seatr.setLayout(QVBoxLayout())
        self._advanced_psd_container_seatr.layout().setContentsMargins(0, 0, 0, 0)
        self._advanced_psd_container_seatr.setMinimumHeight(180)
        self._advanced_psd_container_seatr.setVisible(False)

        self._advanced_psd_container_seatbottom = QWidget()
        self._advanced_psd_container_seatbottom.setLayout(QVBoxLayout())
        self._advanced_psd_container_seatbottom.layout().setContentsMargins(0, 0, 0, 0)
        self._advanced_psd_container_seatbottom.setMinimumHeight(180)
        self._advanced_psd_container_seatbottom.setVisible(False)

        # 横向行容器，一行三列
        psd_row = QWidget()
        psd_row_layout = QHBoxLayout(psd_row)
        psd_row_layout.setContentsMargins(0, 0, 0, 0)
        psd_row_layout.setSpacing(8)
        psd_row_layout.addWidget(self._advanced_psd_container)
        psd_row_layout.addWidget(self._advanced_psd_container_seatr)
        psd_row_layout.addWidget(self._advanced_psd_container_seatbottom)
        psd_layout.addWidget(psd_row)

        self._comprehensive_metrics_card = self._create_comprehensive_metrics_card()
        self._spectrum_group._content_layout.addWidget(self._comprehensive_metrics_card)
        self._stat_features_card = self._create_stat_features_card()
        self._spectrum_group._content_layout.addWidget(self._stat_features_card)

        # ════ 9. 频段衰减雷达图 ════
        self._band_radar_card = self._create_band_radar_card()
        self._band_radar_card.setVisible(True)
        main_layout.addWidget(self._band_radar_card)

        # ════ 10. 事件时间线 (已整合到 2.行程时间轴, 隐藏) ════
        self._advanced_timeline_card = self._create_advanced_card("10. 事件时间线",
            "车速 + 方向盘转角 + 驾驶事件色块标记", "timeline")
        self._advanced_timeline_card.setVisible(False)  # 已整合到 2.行程时间轴
        main_layout.addWidget(self._advanced_timeline_card)

        # ════ 11. 衰减效率柱状图 ════
        self._advanced_attenuation_card = self._create_advanced_card("11. 衰减效率柱状图",
            "各指标改善率排序 (±百分比)", "attenuation")
        main_layout.addWidget(self._advanced_attenuation_card)

        # ════ 12. 雷达对比图 ════
        self._advanced_radar_card = self._create_advanced_card("12. 雷达对比图",
            "多维度指标归一化对比", "radar")
        main_layout.addWidget(self._advanced_radar_card)

        # ════ STFT 时频分析 (移至 SRS 之前) ════
        self._stft_card = self._create_stft_card()
        main_layout.addWidget(self._stft_card)

        # ════ 14. SRS 冲击响应谱 ════
        self._advanced_srs_card = self._create_advanced_card("14. SRS 冲击响应谱",
            "头部眉心 / 胸剑突 / 座垫R点 三轴冲击响应谱对比", "srs")
        main_layout.addWidget(self._advanced_srs_card)

        # 为胸剑突和座垫R点添加额外的图表容器
        srs_layout = self._advanced_srs_card.layout()
        self._advanced_srs_container_chest = QWidget()
        self._advanced_srs_container_chest.setLayout(QVBoxLayout())
        self._advanced_srs_container_chest.layout().setContentsMargins(0, 0, 0, 0)
        self._advanced_srs_container_chest.setMinimumHeight(180)
        self._advanced_srs_container_chest.setVisible(False)
        srs_layout.addWidget(self._advanced_srs_container_chest)

        self._advanced_srs_container_seatr = QWidget()
        self._advanced_srs_container_seatr.setLayout(QVBoxLayout())
        self._advanced_srs_container_seatr.layout().setContentsMargins(0, 0, 0, 0)
        self._advanced_srs_container_seatr.setMinimumHeight(180)
        self._advanced_srs_container_seatr.setVisible(False)
        srs_layout.addWidget(self._advanced_srs_container_seatr)

        # ════ 14. 统计检验分析（页尾）════
        self._statistics_group = self._create_section_group("14. 统计检验分析")
        self._statistics_group.setVisible(True)
        main_layout.addWidget(self._statistics_group)

        self._statistics_card = self._create_statistics_card()
        self._statistics_group._content_layout.addWidget(self._statistics_card)

        # ════ 17. 统一输出：QTabWidget（报告预览 + 对比数据表）════
        self._output_tab_widget = QTabWidget()
        self._output_tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {LC['border_light']};
                border-radius: 6px;
                background: white;
            }}
            QTabBar::tab {{
                background: {LC['bg_card']};
                color: {LC['text_secondary']};
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid {LC['border_light']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: white;
                color: {LC['accent']};
                border-bottom: 2px solid {LC['accent']};
            }}
            QTabBar::tab:hover {{
                background: {LC['bg_hover']};
            }}
        """)
        self._output_tab_widget.setVisible(True)
        main_layout.addWidget(self._output_tab_widget)

        # --- Tab 1: 报告预览 ---
        report_preview_tab = QWidget()
        rp_layout = QVBoxLayout(report_preview_tab)
        rp_layout.setContentsMargins(0, 8, 0, 0)
        rp_layout.setSpacing(6)

        # 导出控制栏
        export_control = QFrame()
        export_control.setStyleSheet(f"background: transparent; border: none;")
        ec_layout = QHBoxLayout(export_control)
        ec_layout.setContentsMargins(4, 0, 4, 4)

        ec_title = QLabel("17. 综合分析报告")
        ec_title.setStyleSheet(
            f"color: {LC['text_primary']}; font-size: 12px; font-weight: 600; background: transparent;"
        )
        ec_layout.addWidget(ec_title)
        ec_layout.addStretch()

        self._export_json_btn = QPushButton("导出 JSON")
        self._export_json_btn.setStyleSheet(self._export_btn_style())
        self._export_json_btn.clicked.connect(lambda: self._on_export('json'))
        self._export_json_btn.setEnabled(False)
        ec_layout.addWidget(self._export_json_btn)

        self._export_md_btn = QPushButton("导出 Markdown")
        self._export_md_btn.setStyleSheet(self._export_btn_style())
        self._export_md_btn.clicked.connect(lambda: self._on_export('md'))
        self._export_md_btn.setEnabled(False)
        ec_layout.addWidget(self._export_md_btn)

        self._export_csv_btn = QPushButton("导出 CSV")
        self._export_csv_btn.setStyleSheet(self._export_btn_style())
        self._export_csv_btn.clicked.connect(lambda: self._on_export('csv'))
        self._export_csv_btn.setEnabled(False)
        ec_layout.addWidget(self._export_csv_btn)

        rp_layout.addWidget(export_control)

        self._report_preview = QTextEdit()
        self._report_preview.setReadOnly(True)
        self._report_preview.setPlaceholderText("分析完成后此处将展示详细报告内容...")
        self._report_preview.setMinimumHeight(200)
        self._report_preview.setStyleSheet(
            f"""
            QTextEdit {{
                border: 1px solid {LC['border_light']};
                border-radius: 4px;
                font-family: "Microsoft YaHei";
                font-size: 11px;
                color: {LC['text_primary']};
                background: white;
                padding: 8px;
            }}
            QTextEdit:focus {{ border-color: {LC['accent']}; }}
            """
        )
        rp_layout.addWidget(self._report_preview)

        # 添加到TabWidget（仅保留报告预览）
        self._output_tab_widget.addTab(report_preview_tab, "\U0001F4CA 报告预览")

        self._status_label = QLabel('就绪 — 请加载数据集开始分析')
        self._status_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 11px; padding: 7px 12px; "
            f"background: {LC['bg_card']}; border: 1px solid {LC['border_light']}; border-radius: 6px;"
        )
        main_layout.addWidget(self._status_label)

        self._scroll_area.setWidget(content)

    def _create_empty_guide(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        icon_lbl = QLabel("\u25C9")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size: 40px; color: {LC['border_default']}; background: transparent;"
        )
        layout.addWidget(icon_lbl)

        title = QLabel("欢迎使用全量统计分析")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {LC['text_primary']}; background: transparent;"
        )
        layout.addWidget(title)

        desc = QLabel("请先加载已解析的数据集文件，然后选择评测指标和位置，点击「开始全量分析」即可自动完成多通道座椅振动评测。")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: 12px; color: {LC['text_secondary']}; background: transparent; line-height: 1.5;"
        )
        layout.addWidget(desc)

        steps_widget = QWidget()
        steps_widget.setStyleSheet("background: transparent;")
        steps_layout = QHBoxLayout(steps_widget)
        steps_layout.setContentsMargins(0, 4, 0, 0)
        steps_layout.setSpacing(16)

        guide_steps = [
            ("1", "加载数据集", "选择已解析的\n数据文件"),
            ("2", "配置参数", "选择预处理级别\n与评测指标"),
            ("3", "开始分析", "点击按钮自动\n完成全量评测"),
            ("4", "查看导出", "浏览结果表格\n导出报告文件"),
        ]
        for num, title_s, desc_s in guide_steps:
            step = QFrame()
            step.setStyleSheet(
                f"background: {LC['bg_input']}; border-radius: 8px; padding: 10px 14px;"
            )
            sl = QVBoxLayout(step)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(4)
            nl = QLabel(num)
            nl.setAlignment(Qt.AlignCenter)
            nl.setStyleSheet(
                f"color: {LC['accent']}; font-size: 18px; font-weight: 700; background: transparent;"
            )
            sl.addWidget(nl)
            tl = QLabel(title_s)
            tl.setAlignment(Qt.AlignCenter)
            tl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {LC['text_primary']}; background: transparent;"
            )
            sl.addWidget(tl)
            dl = QLabel(desc_s)
            dl.setAlignment(Qt.AlignCenter)
            dl.setStyleSheet(
                f"font-size: 10px; color: {LC['text_muted']}; background: transparent;"
            )
            sl.addWidget(dl)
            steps_layout.addWidget(step)

        layout.addWidget(steps_widget, alignment=Qt.AlignCenter)
        return card

    def _create_section_group(self, title_text: str) -> QGroupBox:
        group = QGroupBox(title_text)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-family: "Microsoft YaHei";
                font-size: 13px;
                font-weight: bold;
                color: {LC['text_primary']};
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                margin-top: 8px;
                padding: 20px 12px 10px 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                color: {LC['accent']};
            }}
        """)

        group._content_layout = QVBoxLayout()
        group._content_layout.setSpacing(8)
        group._content_layout.setContentsMargins(0, 0, 0, 0)

        inner = QWidget()
        inner.setLayout(group._content_layout)
        inner.setStyleSheet("background: transparent;")
        group.setLayout(QVBoxLayout())
        group.layout().addWidget(inner)
        group.layout().setContentsMargins(0, 0, 0, 0)

        return group

    def _create_control_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        title = QLabel("全量统计分析")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {LC['text_primary']}; "
            f"padding-right: 8px;"
        )
        row1.addWidget(title)

        self._dataset_badge = QLabel("未加载")
        self._dataset_badge.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px; padding: 3px 10px; "
            f"background: {LC['bg_input']}; border-radius: 10px;"
        )
        row1.addWidget(self._dataset_badge)
        row1.addStretch()

        self._analyze_btn = QPushButton("开始全量分析")
        self._analyze_btn.setStyleSheet(self._primary_btn_style())
        self._analyze_btn.clicked.connect(self._on_start_analysis)
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setCursor(Qt.PointingHandCursor)
        row1.addWidget(self._analyze_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setStyleSheet(self._danger_btn_style())
        self._stop_btn.clicked.connect(self._on_stop_analysis)
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        row1.addWidget(self._stop_btn)

        layout.addLayout(row1)

        # ── 数据源模式切换行 ──
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.addWidget(QLabel("数据源:"))
        self._source_mode_combo = QComboBox()
        self._source_mode_combo.addItem("离线文件 (CSV/TXT)", self.DataSourceMode.OFFLINE_FILE.value)
        self._source_mode_combo.addItem("SQLite 缓存数据集", self.DataSourceMode.SQLITE_CACHE.value)
        self._source_mode_combo.setCurrentIndex(0)
        self._source_mode_combo.setFixedWidth(180)
        self._source_mode_combo.setStyleSheet(
            f"border: 1px solid {LC['accent']}; border-radius: 4px; "
            f"padding: 3px 8px; background: white; font-size: 11px; "
            f"color: {LC['accent']}; font-weight: 600;"
        )
        self._source_mode_combo.currentIndexChanged.connect(self._on_source_mode_changed)
        mode_row.addWidget(self._source_mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── SQLite 缓存选择行（默认隐藏） ──
        self._sqlite_row = QHBoxLayout()
        self._sqlite_row.setSpacing(8)
        self._sqlite_row.addWidget(QLabel("缓存:"))
        self._cache_combo = QComboBox()
        self._cache_combo.setToolTip("选择 SQLite 缓存数据集")
        self._cache_combo.setMinimumWidth(260)
        self._cache_combo.setStyleSheet(
            f"border: 1px solid {LC['accent']}; border-radius: 4px; "
            f"padding: 3px 8px; background: white; font-size: 11px;"
        )
        self._cache_combo.currentIndexChanged.connect(self._on_cache_selected)
        self._cache_combo.setEnabled(False)
        self._sqlite_row.addWidget(self._cache_combo, 1)

        self._sqlite_row.addWidget(QLabel("时间:"))
        self._t_min_spin = QDoubleSpinBox()
        self._t_min_spin.setDecimals(1)
        self._t_min_spin.setSingleStep(1.0)
        self._t_min_spin.setSuffix("s")
        self._t_min_spin.setFixedWidth(75)
        self._t_min_spin.setStyleSheet(
            f"border: 1px solid {LC['border_light']}; border-radius: 4px; "
            f"padding: 3px 4px; background: white; font-size: 11px;"
        )
        self._t_min_spin.valueChanged.connect(self._on_time_range_changed)
        self._sqlite_row.addWidget(self._t_min_spin)
        self._sqlite_row.addWidget(QLabel("~"))
        self._t_max_spin = QDoubleSpinBox()
        self._t_max_spin.setDecimals(1)
        self._t_max_spin.setSingleStep(1.0)
        self._t_max_spin.setSuffix("s")
        self._t_max_spin.setFixedWidth(75)
        self._t_max_spin.setStyleSheet(
            f"border: 1px solid {LC['border_light']}; border-radius: 4px; "
            f"padding: 3px 4px; background: white; font-size: 11px;"
        )
        self._t_max_spin.valueChanged.connect(self._on_time_range_changed)
        self._sqlite_row.addWidget(self._t_max_spin)

        self._btn_full_range = QPushButton("全量")
        self._btn_full_range.setFixedWidth(42)
        self._btn_full_range.setStyleSheet(self._secondary_btn_style())
        self._btn_full_range.clicked.connect(self._on_full_range)
        self._btn_full_range.setCursor(Qt.PointingHandCursor)
        self._sqlite_row.addWidget(self._btn_full_range)
        self._sqlite_row.addStretch()
        layout.addLayout(self._sqlite_row)

        self._sqlite_widgets = [self._sqlite_row]
        for i in range(self._sqlite_row.count()):
            w = self._sqlite_row.itemAt(i)
            if w and w.widget():
                self._sqlite_widgets.append(w.widget())

        # ── 离线文件行（原有） ──
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(QLabel("数据文件:"))
        self._file_label = QLabel("未选择文件")
        self._file_label.setStyleSheet(
            f"color: {LC['text_muted']}; border: 1px solid {LC['border_light']}; "
            f"padding: 4px 10px; border-radius: 4px; background: {LC['bg_input']};"
        )
        self._file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row2.addWidget(self._file_label)

        self._browse_btn = QPushButton("浏览")
        self._browse_btn.setFixedWidth(56)
        self._browse_btn.setStyleSheet(self._secondary_btn_style())
        self._browse_btn.clicked.connect(self._on_browse_dataset)
        self._browse_btn.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self._browse_btn)
        row2.addSpacing(12)

        row2.addWidget(QLabel("评测模式:"))
        self._eval_mode_combo = QComboBox()
        self._eval_mode_combo.addItem("事件触发评测", "event")
        self._eval_mode_combo.addItem("全时域滑动窗口", "full_timeseries")
        self._eval_mode_combo.setCurrentIndex(0)
        self._eval_mode_combo.setFixedWidth(140)
        self._eval_mode_combo.setStyleSheet(
            f"border: 1px solid {LC['border_light']}; border-radius: 4px; "
            f"padding: 3px 8px; background: white; font-size: 11px;"
        )
        self._eval_mode_combo.setToolTip("事件触发：基于检测到的驾驶事件分析 | 全时域滑动窗口：连续1s/0.5s窗口全程扫描")
        row2.addWidget(self._eval_mode_combo)
        row2.addSpacing(8)

        row2.addWidget(QLabel("预处理:"))
        self._preprocess_combo = QComboBox()
        self._preprocess_combo.addItem("Level 0: 原始数据", 0)
        self._preprocess_combo.addItem("Level 1: 零偏+对齐", 1)
        self._preprocess_combo.addItem("Level 2: 零偏+对齐+滤波", 2)
        self._preprocess_combo.setCurrentIndex(1)
        self._preprocess_combo.setFixedWidth(180)
        self._preprocess_combo.setStyleSheet(
            f"border: 1px solid {LC['border_light']}; border-radius: 4px; "
            f"padding: 3px 8px; background: white; font-size: 11px;"
        )
        row2.addWidget(self._preprocess_combo)
        row2.addStretch()

        self._select_all_cb = QCheckBox("全选")
        self._select_all_cb.setChecked(True)
        self._select_all_cb.stateChanged.connect(self._on_select_all_metrics)
        self._select_all_cb.setStyleSheet(
            f"font-size: 11px; color: {LC['text_secondary']};"
        )
        row2.addWidget(self._select_all_cb)
        layout.addLayout(row2)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {LC['border_light']}; max-height: 1px;")
        layout.addWidget(sep)

        row3_wrap = QVBoxLayout()
        row3_wrap.setSpacing(4)

        header_row = QHBoxLayout()
        lbl_indicator = QLabel("评测指标")
        lbl_indicator.setStyleSheet(
            f"color: {LC['text_primary']}; font-size: 11px; font-weight: 700; "
            f"padding: 2px 6px;"
        )
        header_row.addWidget(lbl_indicator)
        header_row.addStretch()
        row3_wrap.addLayout(header_row)

        self._metric_checkboxes: Dict[str, QCheckBox] = {}
        metric_groups = ALL_METRIC_GROUPS

        # 计算最大复选框数，确保各组一致列数便于对齐
        max_cols = max(len(m_ids) for _, m_ids in metric_groups)
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnMinimumWidth(0, 52)  # 分组标签列

        for row_idx, (group_name, m_ids) in enumerate(metric_groups):
            # 分组标签
            group_tag = QLabel(group_name)
            group_tag.setFixedWidth(48)
            group_tag.setAlignment(Qt.AlignCenter)
            group_tag.setStyleSheet(
                f"color: white; font-size: 9px; font-weight: 600; "
                f"padding: 2px 6px; background: {LC['accent']}; border-radius: 3px;"
            )
            grid.addWidget(group_tag, row_idx, 0, Qt.AlignVCenter)

            # 指标复选框 — 同列对齐
            for col, m_id in enumerate(m_ids):
                cb = QCheckBox(m_id)
                cb.setChecked(True)
                cb.setStyleSheet(
                    f"font-size: 11px; padding: 1px 6px; color: {LC['text_secondary']}; "
                    f"spacing: 3px;"
                )
                cb.stateChanged.connect(self._on_metric_check_changed)
                self._metric_checkboxes[m_id] = cb
                grid.addWidget(cb, row_idx, col + 1)

            # 不足 max_cols 的补充占位
            for col in range(len(m_ids), max_cols):
                spacer = QWidget()
                spacer.setFixedWidth(0)
                grid.addWidget(spacer, row_idx, col + 1)

        # 最后一列弹性拉伸，让整体靠左
        grid.setColumnStretch(max_cols + 1, 1)
        row3_wrap.addLayout(grid)

        layout.addLayout(row3_wrap)

        row4 = QHBoxLayout()
        row4.setSpacing(1)
        lbl_loc = QLabel("位置")
        lbl_loc.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 9px; font-weight: 600; padding: 1px 4px; "
            f"background: {LC['bg_input']}; border-radius: 3px;"
        )
        row4.addWidget(lbl_loc)

        self._location_checkboxes: Dict[str, QCheckBox] = {}
        loc_configs = [(loc, LOCATION_NAMES.get(loc, loc)) for loc in get_all_locations()]
        for loc_id, loc_label in loc_configs:
            cb = QCheckBox(loc_label)
            cb.setChecked(True)
            cb.setStyleSheet(
                f"font-size: 11px; padding: 1px 5px; color: {LC['text_secondary']};"
            )
            self._location_checkboxes[loc_id] = cb
            row4.addWidget(cb)

        row4.addStretch()
        layout.addLayout(row4)

        # ── 初始状态: SQLite 行隐藏 ──
        self._set_sqlite_row_visible(False)

        return card

    def _create_overview_dashboard(self) -> QWidget:
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Row 0: OVTV + 主导频带 + 冲击因数 + 位置数
        self._ov_ovtv = self._make_metric_card("总振动值 OVTV (g)", "--", LC['accent'])
        layout.addWidget(self._ov_ovtv, 0, 0, 1, 2)

        self._ov_dom_band = self._make_metric_card("主导频带", "--", LC['info'])
        layout.addWidget(self._ov_dom_band, 0, 2)

        self._ov_cf_z = self._make_metric_card("冲击因数 CF(Z)", "--", LC['warning'])
        layout.addWidget(self._ov_cf_z, 0, 3)

        self._ov_locations = self._make_metric_card("位置数", "--", LC['info'])
        layout.addWidget(self._ov_locations, 0, 4)

        # Row 1: ISO 参考区 + 时长 + 驾驶行为事件
        self._ov_iso = self._make_metric_card("ISO 参考区", "--", LC['success'])
        layout.addWidget(self._ov_iso, 1, 0, 1, 2)

        self._ov_duration = self._make_metric_card("时长(s)", "--", LC['accent'])
        layout.addWidget(self._ov_duration, 1, 2)

        self._ov_behavior = self._make_metric_card("驾驶行为事件", "--", '#E74C3C')
        layout.addWidget(self._ov_behavior, 1, 3, 1, 2)

        # 列均匀拉伸
        for col in range(5):
            layout.setColumnStretch(col, 1)

        return container

    def _make_metric_card(self, title: str, value: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(1)

        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(
            f"color: {accent_color}; font-size: 22px; font-weight: 700; background: transparent;"
        )
        layout.addWidget(val_lbl)

        sub_lbl = QLabel("")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(sub_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(title_lbl)

        card._val_label = val_lbl
        card._sub_label = sub_lbl
        card._title_lbl = title_lbl
        return card

    def _create_pipeline_indicator(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        bar = QFrame()
        bar.setStyleSheet("background: transparent;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(3)

        self._pipeline_segments: List[QFrame] = []
        for i, step_name in enumerate(self._pipeline_labels):
            seg = QFrame()
            seg.setMinimumHeight(36)
            seg.setStyleSheet(
                "background: #E0E0E0; border-radius: 4px;"
            )
            seg_layout = QVBoxLayout(seg)
            seg_layout.setContentsMargins(4, 4, 4, 4)
            seg_layout.setSpacing(1)

            num_lbl = QLabel(str(i + 1))
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(
                "color: #999; font-size: 13px; font-weight: 700; background: transparent;"
            )
            seg_layout.addWidget(num_lbl)

            name_lbl = QLabel(step_name)
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setStyleSheet(
                "color: #999; font-size: 8px; background: transparent;"
            )
            seg_layout.addWidget(name_lbl)

            seg._num_lbl = num_lbl
            seg._name_lbl = name_lbl
            self._pipeline_segments.append(seg)
            bar_layout.addWidget(seg, 1)

        layout.addWidget(bar)

        self._pipeline_status_label = QLabel("就绪")
        self._pipeline_status_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px; padding: 2px 4px;"
        )
        self._elapsed_label = QLabel("")
        self._elapsed_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px;"
        )

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._pipeline_status_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self._elapsed_label)
        layout.addLayout(bottom_row)

        return card

    def _update_pipeline_indicator(self, pct: int):
        stage_idx = -1
        if pct >= 5:
            stage_idx = 0
        if pct >= 15:
            stage_idx = 1
        if pct >= 25:
            stage_idx = 2
        if pct >= 45:
            stage_idx = 3
        if pct >= 90:
            stage_idx = 4

        for i, seg in enumerate(self._pipeline_segments):
            if i < stage_idx:
                seg.setStyleSheet(
                    f"background: {LC['success']}; border-radius: 4px;"
                )
                seg._num_lbl.setText("✓")
                seg._num_lbl.setStyleSheet(
                    "color: white; font-size: 13px; font-weight: 700; background: transparent;"
                )
                seg._name_lbl.setStyleSheet(
                    "color: rgba(255,255,255,0.9); font-size: 8px; background: transparent;"
                )
            elif i == stage_idx:
                seg.setStyleSheet(
                    f"background: {LC['accent']}; border-radius: 4px;"
                )
                seg._num_lbl.setText(str(i + 1))
                seg._num_lbl.setStyleSheet(
                    "color: white; font-size: 13px; font-weight: 700; background: transparent;"
                )
                seg._name_lbl.setStyleSheet(
                    "color: rgba(255,255,255,0.9); font-size: 8px; background: transparent;"
                )
            else:
                seg.setStyleSheet(
                    "background: #E0E0E0; border-radius: 4px;"
                )
                seg._num_lbl.setText(str(i + 1))
                seg._num_lbl.setStyleSheet(
                    "color: #999; font-size: 13px; font-weight: 700; background: transparent;"
                )
                seg._name_lbl.setStyleSheet(
                    "color: #999; font-size: 8px; background: transparent;"
                )

    def _create_results_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("指标统计结果")
        title.setStyleSheet(
            f"font-family: Microsoft YaHei; font-size: 12px; font-weight: 600; color: {LC['text_primary']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        ctrl_bar = QFrame()
        ctrl_bar.setStyleSheet(f"background: {LC['bg_input']}; border: none; border-radius: 4px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(10, 6, 10, 6)
        ctrl_layout.setSpacing(10)

        ctrl_layout.addWidget(QLabel("筛选位置:"))
        self._results_loc_filter = QComboBox()
        self._results_loc_filter.addItem("全部位置", "all")
        for loc_id in get_all_locations():
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            self._results_loc_filter.addItem(loc_name, loc_id)
        self._results_loc_filter.setMaximumWidth(150)
        self._results_loc_filter.setStyleSheet(
            f"QComboBox {{ border: 1px solid {LC['border_light']}; border-radius: 3px; padding: 2px 6px; font-size: 11px; }}"
        )
        self._results_loc_filter.currentIndexChanged.connect(self._on_results_loc_filter_changed)
        ctrl_layout.addWidget(self._results_loc_filter)

        ctrl_layout.addStretch()

        self._results_loc_count = QLabel("0 个指标")
        self._results_loc_count.setStyleSheet(f"color: {LC['text_muted']}; font-size: 10px;")
        ctrl_layout.addWidget(self._results_loc_count)

        layout.addWidget(ctrl_bar)

        self._results_table = QTableWidget()
        self._results_table.setAlternatingRowColors(True)
        self._results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._results_table.verticalHeader().setVisible(False)
        self._results_table.verticalHeader().setDefaultSectionSize(24)
        self._results_table.setColumnCount(13)
        self._results_table.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "评测维度", "单位", "位置",
            "实验组", "对照组", "绝对差", "变化率(%)", "状态",
            "评级", "改进方向", "通过阈值"
        ])
        self._results_table.setMinimumHeight(280)
        self._results_table.setStyleSheet(self._card_table_style())

        header = self._results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        self._results_table.cellClicked.connect(self._on_result_cell_clicked)
        layout.addWidget(self._results_table)

        return card

    def _create_frequency_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("3.3 倍频程能量分布")
        title.setStyleSheet(
            f"font-family: Microsoft YaHei; font-size: 12px; font-weight: 600; color: {LC['text_primary']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self._freq_viz_frame = QFrame()
        self._freq_viz_frame.setMinimumHeight(260)
        self._freq_viz_frame.setStyleSheet(
            f"background: white; border: 1px solid {LC['border_light']}; border-radius: 6px; padding: 4px;"
        )
        layout.addWidget(self._freq_viz_frame)
        return card

    def _create_transmission_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("3.4 传递特性链")
        title.setStyleSheet(
            f"font-family: Microsoft YaHei; font-size: 12px; font-weight: 600; color: {LC['text_primary']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self._trans_table = QTableWidget()
        self._trans_table.setAlternatingRowColors(True)
        self._trans_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._trans_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._trans_table.horizontalHeader().setStretchLastSection(True)
        self._trans_table.verticalHeader().setVisible(False)
        self._trans_table.verticalHeader().setDefaultSectionSize(24)
        self._trans_table.setMinimumHeight(120)
        self._trans_table.setMaximumHeight(250)
        self._trans_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._trans_table)
        return card

    def _create_temporal_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("3.5 时间分段分析 (10s 窗口)")
        title.setStyleSheet(
            f"font-family: Microsoft YaHei; font-size: 12px; font-weight: 600; color: {LC['text_primary']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self._temporal_table = QTableWidget()
        self._temporal_table.setAlternatingRowColors(True)
        self._temporal_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._temporal_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._temporal_table.horizontalHeader().setStretchLastSection(True)
        self._temporal_table.verticalHeader().setVisible(False)
        self._temporal_table.verticalHeader().setDefaultSectionSize(24)
        self._temporal_table.setMinimumHeight(140)
        self._temporal_table.setMaximumHeight(400)
        self._temporal_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._temporal_table)
        return card

    def _card_table_style(self) -> str:
        return f"""
            QTableWidget {{
                gridline-color: {LC['border_light']};
                background-color: {LC['bg_card']};
                alternate-background-color: #F8F9FA;
                border: 1px solid {LC['border_light']};
                border-radius: 4px;
                font-family: "Microsoft YaHei";
                font-size: 10px;
            }}
            QTableWidget::item {{ padding: 3px 8px; }}
            QTableWidget::item:selected {{
                background-color: {LC['bg_hover']};
                color: {LC['text_primary']};
            }}
            QTableWidget::item:hover {{ background-color: #EEF2F7; }}
            QHeaderView::section {{
                background-color: #F0F3F8;
                border: none;
                border-bottom: 2px solid {LC['border_light']};
                padding: 5px 8px;
                font-weight: 600;
                font-size: 10px;
                color: {LC['text_secondary']};
            }}
        """

    def _create_condition_overview_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("1.1 驾驶工况概览")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {LC['text_primary']};")
        layout.addWidget(title)

        # 基本信息行
        self._cond_speed_info = QLabel("速度分布: --")
        self._cond_speed_info.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(self._cond_speed_info)

        self._cond_turning_info = QLabel("转向信息: --")
        self._cond_turning_info.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(self._cond_turning_info)

        # ── 速度直方图 (matplotlib 图表) ──
        self._cond_speed_hist_chart = QWidget()
        self._cond_speed_hist_chart.setLayout(QVBoxLayout())
        self._cond_speed_hist_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._cond_speed_hist_chart.setMinimumHeight(180)
        self._cond_speed_hist_chart.setVisible(False)
        layout.addWidget(self._cond_speed_hist_chart)

        # ── 速度统计量柱状图 ──
        self._cond_speed_stats_chart = QWidget()
        self._cond_speed_stats_chart.setLayout(QVBoxLayout())
        self._cond_speed_stats_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._cond_speed_stats_chart.setMinimumHeight(180)
        self._cond_speed_stats_chart.setVisible(False)
        layout.addWidget(self._cond_speed_stats_chart)

        # ── 两列布局：驾驶行为摘要 (左) + 速度区间频次表 (右) ──
        two_col_widget = QWidget()
        two_col_layout = QHBoxLayout(two_col_widget)
        two_col_layout.setContentsMargins(0, 0, 0, 0)
        two_col_layout.setSpacing(12)

        # 左列：驾驶行为摘要（内部分两小列）
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(4)
        left_col.addWidget(QLabel("<b>驾驶行为:</b>"))
        # 驾驶行为内部分两列
        behavior_inner = QHBoxLayout()
        behavior_inner.setContentsMargins(0, 0, 0, 0)
        behavior_inner.setSpacing(8)
        self._cond_behavior_info = QLabel("")
        self._cond_behavior_info.setWordWrap(True)
        self._cond_behavior_info.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px;")
        self._cond_behavior_info.setVisible(False)
        self._cond_behavior_info2 = QLabel("")
        self._cond_behavior_info2.setWordWrap(True)
        self._cond_behavior_info2.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px;")
        self._cond_behavior_info2.setVisible(False)
        behavior_inner.addWidget(self._cond_behavior_info, 1)
        behavior_inner.addWidget(self._cond_behavior_info2, 1)
        left_col.addLayout(behavior_inner)
        left_col.addStretch()
        two_col_layout.addLayout(left_col, 1)  # 比例 1

        # 右列：速度区间频次表
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.addWidget(QLabel("<b>速度区间分布:</b>"))
        self._cond_speed_hist_table = QTableWidget()
        self._cond_speed_hist_table.setAlternatingRowColors(True)
        self._cond_speed_hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._cond_speed_hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._cond_speed_hist_table.verticalHeader().setVisible(False)
        self._cond_speed_hist_table.verticalHeader().setDefaultSectionSize(24)
        self._cond_speed_hist_table.setColumnCount(3)
        self._cond_speed_hist_table.setHorizontalHeaderLabels(["速度区间 (km/h)", "频次", "占比%"])
        self._cond_speed_hist_table.setMaximumHeight(200)
        hh = self._cond_speed_hist_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        right_col.addWidget(self._cond_speed_hist_table, 1)
        two_col_layout.addLayout(right_col, 1)  # 比例 1

        layout.addWidget(two_col_widget)

        self._cond_corr_info = QLabel("速度-振动相关性: --")
        self._cond_corr_info.setStyleSheet(f"color: {LC['info']}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(self._cond_corr_info)

        return card

    def _create_behavior_events_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("1.2 驾驶行为事件")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {LC['text_primary']};")
        layout.addWidget(title)

        # 多部位三轴加速度合成图 (头部/胸剑突/座垫R点/座椅底部 X/Y/Z 轴)
        self._behavior_overview_chart = QWidget()
        self._behavior_overview_chart.setLayout(QVBoxLayout())
        self._behavior_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._behavior_overview_chart.setMinimumHeight(360)
        self._behavior_overview_chart.setVisible(False)
        layout.addWidget(self._behavior_overview_chart)

        # ── v8.0 移植: 全部驾驶事件 Ay加速度对比图 (已合并至上方三轴IMU概览图) ──

        self._behavior_events_table = QTableWidget()
        self._behavior_events_table.setAlternatingRowColors(True)
        self._behavior_events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._behavior_events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._behavior_events_table.verticalHeader().setVisible(False)
        self._behavior_events_table.verticalHeader().setDefaultSectionSize(24)
        self._behavior_events_table.setColumnCount(6)
        self._behavior_events_table.setHorizontalHeaderLabels(
            ["#", "事件类型", "时间区间", "瞬时车速(km/h)", "区间车速变化(km/h)", "区间峰值"]
        )
        self._behavior_events_table.setMinimumHeight(160)
        self._behavior_events_table.setMaximumHeight(300)
        hh = self._behavior_events_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # #
        hh.setSectionResizeMode(1, QHeaderView.Stretch)            # 事件类型 — 自适应填充
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # 时间区间
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # 瞬时车速
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)   # 区间车速变化
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)   # 区间峰值
        hh.setMinimumSectionSize(40)
        layout.addWidget(self._behavior_events_table)

        self._behavior_summary_label = QLabel("")
        self._behavior_summary_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px; padding: 4px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )
        layout.addWidget(self._behavior_summary_label)

        # ── v8.0 移植: 驾驶行为事件分布图 (水平柱状图) ──
        self._behavior_dist_chart = QWidget()
        self._behavior_dist_chart.setLayout(QVBoxLayout())
        self._behavior_dist_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._behavior_dist_chart.setMinimumHeight(180)
        self._behavior_dist_chart.setVisible(False)
        layout.addWidget(self._behavior_dist_chart)

        return card

    def _create_contrast_profile_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("4.1 ⚖️ 实验组 vs 对照组 基线对比")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {LC['text_primary']};")
        title_row.addWidget(title)
        
        self._contrast_baseline_label = QLabel("基于ISO 10326-1标准基线")
        self._contrast_baseline_label.setStyleSheet(
            f"font-size: 9px; color: {LC['text_muted']}; padding: 2px 6px; "
            f"background: {LC['bg_input']}; border-radius: 3px;"
        )
        title_row.addStretch()
        title_row.addWidget(self._contrast_baseline_label)
        layout.addLayout(title_row)

        self._contrast_grid_layout = QVBoxLayout()
        self._contrast_grid_layout.setSpacing(6)
        layout.addLayout(self._contrast_grid_layout)

        self._contrast_summary_label = QLabel("")
        self._contrast_summary_label.setStyleSheet(
            f"color: {LC['accent']}; font-size: 11px; font-weight: 600; padding: 8px; "
            f"background: #FFF8E1; border: 1px solid #FFE0B2; border-radius: 4px;"
        )
        self._contrast_summary_label.setVisible(False)
        layout.addWidget(self._contrast_summary_label)

        self._contrast_group_stats = QHBoxLayout()
        self._contrast_group_stats.setSpacing(16)
        self._contrast_group_stats.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._contrast_group_stats)

        return card

    def _populate_profile_visualization(self, report: Dict):
        locations = report.get('locations', {})
        profiles = {}          # 实验组 profile
        ctrl_profiles = {}     # 对照组 profile

        for loc_id, loc_data in locations.items():
            label = loc_data.get('label_cn', loc_id)
            prof = loc_data.get('profile')
            ctrl_prof = loc_data.get('control_profile')

            if isinstance(prof, dict) and not prof.get('error'):
                profiles[label] = prof
            if isinstance(ctrl_prof, dict) and not ctrl_prof.get('error'):
                ctrl_profiles[label] = ctrl_prof

        if not profiles:
            self._profile_group.setVisible(True)
            return

        self._profile_group.setVisible(True)
        self._populate_frequency_viz(profiles, ctrl_profiles)
        self._populate_transmission_table(profiles, ctrl_profiles)
        self._populate_temporal_table(profiles, ctrl_profiles)

    def _populate_frequency_viz(self, profiles: Dict[str, Dict], ctrl_profiles: Dict[str, Dict] = None):
        frame = self._freq_viz_frame
        if frame.layout():
            QWidget().setLayout(frame.layout())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        header = QLabel("倍频程能量分布 — 实验组 vs 对照组")
        header.setStyleSheet(f"color: {LC['text_primary']}; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(header)

        # 图例
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)
        exp_legend = QLabel("■ 实验组")
        exp_legend.setStyleSheet("color: #3498DB; font-size: 10px; font-weight: 600; background: transparent;")
        legend_row.addWidget(exp_legend)
        ctrl_legend = QLabel("■ 对照组")
        ctrl_legend.setStyleSheet("color: #E67E22; font-size: 10px; font-weight: 600; background: transparent;")
        legend_row.addWidget(ctrl_legend)
        legend_row.addStretch()
        layout.addLayout(legend_row)

        band_order = ['0.1-1Hz', '1-2Hz', '2-4Hz', '4-8Hz', '8-20Hz', '20-50Hz', '50-100Hz']
        band_labels = ['0.1-1\n晕动', '1-2\n侧向', '2-4\n躯干', '4-8\n脊椎', '8-20\n头颈', '20-50\n组织', '50-100\n高频']

        first_profile = list(profiles.values())[0]
        freq_data = first_profile.get('frequency', {}) or {}
        band_energy = freq_data.get('band_energy_pct', {})

        # 获取对照组数据
        ctrl_band_energy = {}
        if ctrl_profiles:
            first_ctrl = list(ctrl_profiles.values())[0]
            ctrl_freq_data = (first_ctrl.get('frequency', {}) or {}) if isinstance(first_ctrl, dict) else {}
            ctrl_band_energy = ctrl_freq_data.get('band_energy_pct', {})

        if not band_energy and not ctrl_band_energy:
            label = QLabel("无频域数据")
            label.setStyleSheet(f"color: {LC['text_muted']}; font-size: 10px; background: transparent;")
            layout.addWidget(label)
            layout.addStretch()
            return

        # 计算最大值用于比例尺
        all_vals = list(band_energy.values()) + list(ctrl_band_energy.values())
        max_pct = max(all_vals) if all_vals else 1

        chart_area = QWidget()
        chart = QHBoxLayout(chart_area)
        chart.setContentsMargins(0, 4, 0, 0)
        chart.setSpacing(8)

        for i, band in enumerate(band_order):
            exp_pct = band_energy.get(band, 0)
            ctrl_pct = ctrl_band_energy.get(band, 0) if ctrl_band_energy else 0

            pair = QWidget()
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(2)

            # 实验组柱子（蓝色）
            exp_bar = QFrame()
            exp_bar.setFixedWidth(34)
            exp_bar.setStyleSheet("background: #3498DB; border-radius: 3px;")
            exp_height = int(max(20, exp_pct / max(max_pct, 1) * 180))
            exp_bar.setMinimumHeight(exp_height)
            exp_bar.setMaximumHeight(exp_height)
            exp_layout = QVBoxLayout(exp_bar)
            exp_layout.setContentsMargins(1, 1, 1, 1)
            exp_layout.setSpacing(0)
            exp_val = QLabel(f"{exp_pct:.1f}" if exp_pct > 0 else "")
            exp_val.setAlignment(Qt.AlignCenter)
            exp_val.setStyleSheet("color: white; font-size: 8px; font-weight: 700; background: transparent;")
            exp_layout.addWidget(exp_val)
            exp_layout.addStretch()
            pair_layout.addWidget(exp_bar, alignment=Qt.AlignBottom)

            # 对照组柱子（橙色）
            ctrl_bar = QFrame()
            ctrl_bar.setFixedWidth(34)
            ctrl_bar.setStyleSheet("background: #E67E22; border-radius: 3px;")
            ctrl_height = int(max(20, ctrl_pct / max(max_pct, 1) * 180))
            ctrl_bar.setMinimumHeight(ctrl_height)
            ctrl_bar.setMaximumHeight(ctrl_height)
            ctrl_layout = QVBoxLayout(ctrl_bar)
            ctrl_layout.setContentsMargins(1, 1, 1, 1)
            ctrl_layout.setSpacing(0)
            ctrl_val = QLabel(f"{ctrl_pct:.1f}" if ctrl_pct > 0 else "")
            ctrl_val.setAlignment(Qt.AlignCenter)
            ctrl_val.setStyleSheet("color: white; font-size: 8px; font-weight: 700; background: transparent;")
            ctrl_layout.addWidget(ctrl_val)
            ctrl_layout.addStretch()
            pair_layout.addWidget(ctrl_bar, alignment=Qt.AlignBottom)

            pair.setMinimumHeight(max(exp_height, ctrl_height) + 28)
            chart.addWidget(pair)

            # 频段标签
            tag_label = QLabel(band_labels[i])
            tag_label.setAlignment(Qt.AlignCenter)
            tag_label.setStyleSheet(f"color: {LC['text_muted']}; font-size: 9px; background: transparent;")
            chart.addWidget(tag_label)

        chart.addStretch()
        layout.addWidget(chart_area)
        layout.addStretch()

    def _populate_transmission_table(self, profiles: Dict[str, Dict], ctrl_profiles: Dict[str, Dict] = None):
        table = self._trans_table
        table.clear()

        has_ctrl = bool(ctrl_profiles)

        if has_ctrl:
            cols = ['位置', 'OVTV_实验', 'OVTV_对照', '变化率(%)',
                    'Z传递_实验', 'Z传递_对照', 'XY传递_实验', 'XY传递_对照',
                    'SEAT_Z_实验', 'SEAT_Z_对照', 'SEAT_XY_实验', 'SEAT_XY_对照']
        else:
            cols = ['位置', 'OVTV (g)', 'Z传递率', 'XY传递率', 'SEAT_Z', 'SEAT_XY']

        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)

        rows = []
        for label, prof in profiles.items():
            trans = prof.get('transmission') or {}
            mag = prof.get('magnitude') or {}

            # 对照组数据
            ctrl_prof = (ctrl_profiles or {}).get(label)
            if ctrl_prof and isinstance(ctrl_prof, dict):
                ctrl_trans = ctrl_prof.get('transmission') or {}
                ctrl_mag = ctrl_prof.get('magnitude') or {}
            else:
                ctrl_prof = {}
                ctrl_trans = {}
                ctrl_mag = {}

            if has_ctrl:
                ovtv_exp = mag.get('OVTV', 0) if isinstance(mag, dict) else 0
                ovtv_ctrl = ctrl_mag.get('OVTV', 0) if isinstance(ctrl_mag, dict) else 0
                try:
                    delta = (ovtv_exp - ovtv_ctrl) / max(abs(ovtv_exp), abs(ovtv_ctrl), 1e-6) * 100
                    delta_str = f"{delta:+.1f}%"
                except Exception:
                    delta_str = '-'

                z_exp = f"{trans['Z_trans_base']:.1f}×" if trans.get('Z_trans_base') else '-'
                z_ctrl = f"{ctrl_trans['Z_trans_base']:.1f}×" if ctrl_trans.get('Z_trans_base') else '-'

                xy_exp = f"{trans['XY_trans_base']:.1f}×" if trans.get('XY_trans_base') else '-'
                xy_ctrl = f"{ctrl_trans['XY_trans_base']:.1f}×" if ctrl_trans.get('XY_trans_base') else '-'

                seat_z_exp = f"{float(trans['SEAT_Z']):.2f}" if trans.get('SEAT_Z') is not None else '-'
                seat_z_ctrl = f"{float(ctrl_trans['SEAT_Z']):.2f}" if ctrl_trans.get('SEAT_Z') is not None else '-'
                seat_xy_exp = f"{float(trans['SEAT_XY']):.2f}" if trans.get('SEAT_XY') is not None else '-'
                seat_xy_ctrl = f"{float(ctrl_trans['SEAT_XY']):.2f}" if ctrl_trans.get('SEAT_XY') is not None else '-'

                rows.append([label, f"{ovtv_exp:.3f}", f"{ovtv_ctrl:.3f}", delta_str,
                             z_exp, z_ctrl, xy_exp, xy_ctrl,
                             seat_z_exp, seat_z_ctrl, seat_xy_exp, seat_xy_ctrl])
            else:
                ovtv = f"{mag.get('OVTV', 0):.3f}" if isinstance(mag, dict) else '-'
                z_trans = f"{trans['Z_trans_base']:.1f}×" if trans.get('Z_trans_base') else '-'
                xy_trans = f"{trans['XY_trans_base']:.1f}×" if trans.get('XY_trans_base') else '-'
                seat_z = '-'
                seat_xy = '-'
                if trans.get('SEAT_Z') is not None:
                    try:
                        seat_z = f"{float(trans['SEAT_Z']):.2f}"
                    except (TypeError, ValueError):
                        pass
                if trans.get('SEAT_XY') is not None:
                    try:
                        seat_xy = f"{float(trans['SEAT_XY']):.2f}"
                    except (TypeError, ValueError):
                        pass
                rows.append([label, ovtv, z_trans, xy_trans, seat_z, seat_xy])

        table.setRowCount(len(rows))
        for r, row_data in enumerate(rows):
            for c, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c == 0:
                    item.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
                table.setItem(r, c, item)

        table.resizeColumnsToContents()
        table.setColumnWidth(0, 70)
        for c in range(1, len(cols)):
            table.setColumnWidth(c, 88)

    def _populate_condition_overview(self, report: Dict):
        vehicle_summary = report.get('vehicle_summary', {})
        locations = report.get('locations', {})

        speed_mean = vehicle_summary.get('speed_mean')
        speed_std = vehicle_summary.get('speed_std')
        speed_median = vehicle_summary.get('speed_median')
        speed_max = vehicle_summary.get('speed_max')

        if speed_mean is not None:
            std_str = f"{speed_std:.1f}" if speed_std is not None else "--"
            med_str = f"{speed_median:.1f}" if speed_median is not None else "--"
            max_str = f"{speed_max:.0f}" if speed_max is not None else "--"
            self._cond_speed_info.setText(
                f"速度分布: 均值 {speed_mean:.1f} km/h  |  标准差 {std_str}  |  "
                f"中位数 {med_str}  |  最大 {max_str} km/h"
            )
        turning_ratio = vehicle_summary.get('turning_ratio_pct')
        if turning_ratio is not None:
            self._cond_turning_info.setText(
                f"转向信息: 转角>10°占比 {turning_ratio:.1f}%  |  "
                f"均值 |wheel|={vehicle_summary.get('wheel_mean', 0):.1f}°  |  "
                f"最大 |wheel|={vehicle_summary.get('wheel_max', 0):.0f}°"
            )

        corr_values = []
        for loc_data in locations.values():
            prof = loc_data.get('profile', {})
            if isinstance(prof, dict):
                cond = prof.get('condition', {})
                if isinstance(cond, dict) and 'speed_vibration_correlation' in cond:
                    corr_values.append(cond['speed_vibration_correlation'])

        if corr_values:
            avg_corr = sum(corr_values) / len(corr_values)
            if abs(avg_corr) > 0.5:
                corr_note = '强相关'
            elif abs(avg_corr) > 0.3:
                corr_note = '中等相关'
            else:
                corr_note = '弱相关'
            self._cond_corr_info.setText(f"速度-振动相关性: r={avg_corr:.3f} ({corr_note})")

        # ── 驾驶行为摘要 (左列) ── 内部分两列显示
        behavior_summary = report.get('behavior_summary', {})
        if behavior_summary:
            total_events = behavior_summary.get('total_events', 0)
            event_types = behavior_summary.get('event_types', {})
            if total_events > 0 and event_types:
                sorted_items = sorted(event_types.items(), key=lambda x: -x[1])
                mid = (len(sorted_items) + 1) // 2
                # 总事件行
                header = f"总事件: {total_events}个 ({len(event_types)}种)"
                # 左列 = header + 前半部分
                col1_lines = [header] + [f"{et}: {ct}个" for et, ct in sorted_items[:mid]]
                self._cond_behavior_info.setText("\n".join(col1_lines))
                self._cond_behavior_info.setVisible(True)
                # 右列 = 后半部分
                if len(sorted_items) > mid:
                    col2_lines = [f"{et}: {ct}个" for et, ct in sorted_items[mid:]]
                    self._cond_behavior_info2.setText("\n".join(col2_lines))
                    self._cond_behavior_info2.setVisible(True)

        speed_hist = vehicle_summary.get('speed_histogram', {})
        labels = speed_hist.get('labels', [])
        counts = speed_hist.get('counts', [])
        if labels and len(counts) > 0:
            self._populate_speed_histogram(labels, counts)

        # ── v8.0 移植: 速度直方图图表 ──
        hist_data = vehicle_summary.get('speed_histogram', {})
        bins = hist_data.get('bins') or hist_data.get('edges')
        hist_counts = hist_data.get('counts', [])
        if bins is not None and len(hist_counts) > 0:
            try:
                bins_arr = np.array(bins, dtype=float)
                counts_arr = np.array(hist_counts, dtype=float)
                if len(bins_arr) > 1 and len(counts_arr) == len(bins_arr) - 1:
                    fig = Figure(figsize=(7, 2.2), dpi=ChartStyle.screen_dpi())
                    fig.patch.set_facecolor('#FAFAFA')
                    ax = fig.add_subplot(111)
                    ax.bar((bins_arr[:-1] + bins_arr[1:]) / 2, counts_arr,
                           width=np.diff(bins_arr) * 0.9, alpha=0.75,
                           color=LC.get('accent', '#2563EB'), edgecolor='white')
                    ax.set_xlabel('车速 (km/h)', fontsize=9)
                    ax.set_ylabel('计数', fontsize=9)
                    ax.set_title('车速分布直方图', fontsize=10, fontweight='bold')
                    ax.grid(axis='y', alpha=0.2)
                    fig.tight_layout()
                    self._create_chart_canvas(fig, self._cond_speed_hist_chart)
                    self._cond_speed_hist_chart.setVisible(True)
            except Exception:
                self._cond_speed_hist_chart.setVisible(False)

        # ── v8.0 移植: 速度统计量柱状图 ──
        if speed_mean is not None:
            try:
                fig = Figure(figsize=(7, 2.5), dpi=ChartStyle.screen_dpi())
                ax = fig.add_subplot(111)
                vals = [speed_mean, speed_median or 0, speed_max or 0, speed_std or 0]
                chart_labels = ['均值', '中位数', '最大值', '标准差']
                colors = [LC.get('accent', '#2563EB'), '#5DADE2', '#E74C3C', '#F39C12']
                ax.bar(chart_labels, vals, color=colors, alpha=0.7, edgecolor='white')
                ax.set_ylabel('车速 (km/h)', fontsize=9)
                ax.set_title('车速统计量', fontsize=10, fontweight='bold')
                ax.grid(axis='y', alpha=0.2)
                for i, v in enumerate(vals):
                    ax.text(i, v + 0.5, f'{v:.1f}', ha='center', fontsize=8)
                fig.tight_layout()
                self._create_chart_canvas(fig, self._cond_speed_stats_chart)
                self._cond_speed_stats_chart.setVisible(True)
            except Exception:
                self._cond_speed_stats_chart.setVisible(False)

        self._condition_overview_card.setVisible(True)

    def _generate_events_overview_chart(self, card_widget: QWidget, location_data: Optional[Dict], events: List[Dict]) -> Optional[Figure]:
        """生成全部驾驶事件概览图 — 每事件1行×3列 (Ax/Ay/Az)

        每行展示一个事件的实验组(蓝) vs 对照组(红) 三轴加速度对比。
        生成所有事件（不限制数量），布局为 N行 × 3列。

        Args:
            card_widget: 目标卡片容器
            location_data: 包含 exp_ax/exp_ay/exp_az/ctrl_ax/ctrl_ay/ctrl_az/timestamps/location_label
            events: 事件列表
        Returns: Figure 对象，失败返回 None
        """
        if not location_data or not events:
            return None
        ts_arr = np.array(location_data.get('timestamps', []))
        if len(ts_arr) < 2:
            return None
        exp_ax = np.array(location_data.get('exp_ax', []))
        exp_ay = np.array(location_data.get('exp_ay', []))
        exp_az = np.array(location_data.get('exp_az', []))
        ctrl_ax = np.array(location_data.get('ctrl_ax', []))
        ctrl_ay = np.array(location_data.get('ctrl_ay', []))
        ctrl_az = np.array(location_data.get('ctrl_az', []))
        if len(exp_ay) == 0 or len(ctrl_ay) == 0:
            return None

        loc_label = location_data.get('location_label', '头部')

        n = len(ts_arr)
        if len(exp_ax) > n: exp_ax = exp_ax[:n]
        if len(exp_ay) > n: exp_ay = exp_ay[:n]
        if len(exp_az) > n: exp_az = exp_az[:n]
        if len(ctrl_ax) > n: ctrl_ax = ctrl_ax[:n]
        if len(ctrl_ay) > n: ctrl_ay = ctrl_ay[:n]
        if len(ctrl_az) > n: ctrl_az = ctrl_az[:n]

        # ── 数据清洗：参照 IMU 可视化模块策略 (NaN/Inf插值 + 99.9%分位裁剪) ──
        exp_ax = self._clean_imu_data(exp_ax)
        exp_ay = self._clean_imu_data(exp_ay)
        exp_az = self._clean_imu_data(exp_az)
        ctrl_ax = self._clean_imu_data(ctrl_ax)
        ctrl_ay = self._clean_imu_data(ctrl_ay)
        ctrl_az = self._clean_imu_data(ctrl_az)

        fs_data = 1000.0
        if n > 1:
            dt = ts_arr[1] - ts_arr[0]
            if dt > 0:
                fs_data = 1.0 / dt

        # ── 全部事件，每事件1行×3列 (Ax/Ay/Az) ──
        n_ev = len(events)
        ncols = 3
        nrows = n_ev

        # 事件类型 → 中文显示映射
        EVENT_CN = {
            'constant_speed': '匀速直行', 'normal_acceleration': '正常加速',
            'normal_deceleration': '正常减速', 'cruising': '恒速行驶',
            'stopped': '停车', 'parked': '驻车',
            'lane_keeping': '车道保持', 'left_turn': '左转', 'right_turn': '右转',
            'tight_turn': '小半径转弯', 'wide_turn': '大半径转弯', 'u_turn': 'U型转弯',
            'cornering_acceleration': '弯道加速', 'cornering_deceleration': '弯道减速',
            'aggressive_acceleration': '激进加速', 'aggressive_deceleration': '激进减速',
            'emergency_braking': '急刹车',
            'weaving': '蛇形驾驶', 'rapid_direction_change': '急速变向',
            'severe_bump': '剧烈颠簸', 'skid_risk': '侧滑风险', 'rollover_risk': '侧翻风险',
            'lane_change': '变道', 'hard_acceleration': '急加速',
            'hard_braking': '急刹车', 'sharp_turn': '急转弯',
        }

        def _cn_event(etype: str) -> str:
            if not etype or etype == '?':
                return '事件'
            cn = EVENT_CN.get(etype)
            if cn:
                return cn
            try:
                from core.core.seat_evaluation.metadata_registry import get_global_registry
                registry = get_global_registry()
                state = registry.driving_states.get(etype)
                if state:
                    return state.display_name_cn
            except ImportError:
                pass
            if any('\u4e00' <= c <= '\u9fff' for c in etype):
                return etype[:12]
            return etype[:12]

        try:
            fig, axes, scale = card_adapted_figure(card_widget, nrows, ncols, height_mul=float(nrows) * 0.55)
            fs = np.sqrt(max(0.6, min(1.8, scale)))
            axes_flat = axes.flatten() if nrows * ncols > 1 else [axes]

            for i, ev in enumerate(events):
                t_s = ev.get('t_start', 0)
                t_e = ev.get('t_end', 0)
                s = max(0, int(t_s * fs_data) - int(fs_data * 0.5))
                e = min(n - 1, int(t_e * fs_data) + int(fs_data * 1.5))
                if e <= s:
                    s = max(0, int(t_s * fs_data))
                    e = min(n - 1, int(t_e * fs_data + fs_data * 1.0))
                if e <= s + 10:
                    margin = int(fs_data * 1.0)
                    s = max(0, int(t_s * fs_data) - margin)
                    e = min(n - 1, int(t_e * fs_data) + margin)

                t_seg = ts_arr[s:e] - t_s
                row_base = i * ncols

                # ── Ax 子图 ──
                ax_ax = axes_flat[row_base]
                if len(exp_ax) > 0:
                    ax_ax.plot(t_seg, exp_ax[s:e], 'b-', linewidth=0.6 * scale, alpha=0.85, label='实验组')
                if len(ctrl_ax) > 0:
                    ax_ax.plot(t_seg, ctrl_ax[s:e], 'r--', linewidth=0.6 * scale, alpha=0.85, label='对照组')
                ax_ax.axvline(x=0, color='k', linestyle=':', alpha=0.4)
                if ev.get('duration', 0) > 0:
                    ax_ax.axvspan(0, ev.get('duration', 0.1), alpha=0.12, color='yellow')
                ax_ax.set_ylabel('Ax (m/s²)', fontsize=max(5, int(6 * fs)))
                ax_ax.grid(True, alpha=0.2, linestyle='-')
                # Ax 衰减率标注
                if len(exp_ax) > 0 and len(ctrl_ax) > 0:
                    evals_ax = exp_ax[s:e]; cvals_ax = ctrl_ax[s:e]
                    valid_ax = ~np.isnan(evals_ax) & ~np.isnan(cvals_ax)
                    if valid_ax.sum() > 50:
                        e_rms_ax = np.sqrt(np.mean(evals_ax[valid_ax]**2))
                        c_rms_ax = np.sqrt(np.mean(cvals_ax[valid_ax]**2))
                        if c_rms_ax > 1e-3:
                            atn_ax = (1 - e_rms_ax / c_rms_ax) * 100
                            color_ax = '#27AE60' if atn_ax > 0 else '#E74C3C'
                            ax_ax.text(0.95, 0.95, f'Δ={atn_ax:.0f}%', transform=ax_ax.transAxes,
                                      ha='right', va='top', fontsize=max(5, int(6 * fs)),
                                      color=color_ax, fontweight='bold')

                # ── Ay 子图 ──
                ax_ay = axes_flat[row_base + 1]
                ax_ay.plot(t_seg, exp_ay[s:e], 'b-', linewidth=0.6 * scale, alpha=0.85, label='实验组')
                ax_ay.plot(t_seg, ctrl_ay[s:e], 'r--', linewidth=0.6 * scale, alpha=0.85, label='对照组')
                ax_ay.axvline(x=0, color='k', linestyle=':', alpha=0.4)
                if ev.get('duration', 0) > 0:
                    ax_ay.axvspan(0, ev.get('duration', 0.1), alpha=0.12, color='yellow')
                ax_ay.set_ylabel('Ay (m/s²)', fontsize=max(5, int(6 * fs)))
                ax_ay.grid(True, alpha=0.2, linestyle='-')

                # ── Az 子图 ──
                ax_az = axes_flat[row_base + 2]
                if len(exp_az) > 0:
                    ax_az.plot(t_seg, exp_az[s:e], 'b-', linewidth=0.6 * scale, alpha=0.85, label='实验组')
                if len(ctrl_az) > 0:
                    ax_az.plot(t_seg, ctrl_az[s:e], 'r--', linewidth=0.6 * scale, alpha=0.85, label='对照组')
                ax_az.axvline(x=0, color='k', linestyle=':', alpha=0.4)
                if ev.get('duration', 0) > 0:
                    ax_az.axvspan(0, ev.get('duration', 0.1), alpha=0.12, color='yellow')
                ax_az.set_ylabel('Az (m/s²)', fontsize=max(5, int(6 * fs)))
                ax_az.grid(True, alpha=0.2, linestyle='-')
                # Az 衰减率标注
                if len(exp_az) > 0 and len(ctrl_az) > 0:
                    evals_az = exp_az[s:e]; cvals_az = ctrl_az[s:e]
                    valid_az = ~np.isnan(evals_az) & ~np.isnan(cvals_az)
                    if valid_az.sum() > 50:
                        e_rms_az = np.sqrt(np.mean(evals_az[valid_az]**2))
                        c_rms_az = np.sqrt(np.mean(cvals_az[valid_az]**2))
                        if c_rms_az > 1e-3:
                            atn_az = (1 - e_rms_az / c_rms_az) * 100
                            color_az = '#27AE60' if atn_az > 0 else '#E74C3C'
                            ax_az.text(0.95, 0.95, f'Δ={atn_az:.0f}%', transform=ax_az.transAxes,
                                      ha='right', va='top', fontsize=max(5, int(6 * fs)),
                                      color=color_az, fontweight='bold')

                # ── 事件标题（显示在Ay子图上方）──
                ev_type_raw = ev.get('type', ev.get('event_type', '?'))
                ev_name = _cn_event(ev_type_raw)
                ax_ay.set_title(f'E{i+1} {ev_name} t={t_s:.1f}s',
                              fontsize=max(6, int(8 * fs)), fontweight='bold')

                # ── 衰减率标注（Ay子图）──
                evals = exp_ay[s:e]
                cvals = ctrl_ay[s:e]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    e_rms = np.sqrt(np.mean(evals[valid]**2))
                    c_rms = np.sqrt(np.mean(cvals[valid]**2))
                    if c_rms > 1e-3:
                        atn = (1 - e_rms / c_rms) * 100
                        color = '#27AE60' if atn > 0 else '#E74C3C'
                        ax_ay.text(0.95, 0.95, f'Δ={atn:.0f}%', transform=ax_ay.transAxes,
                                  ha='right', va='top', fontsize=max(5, int(6 * fs)),
                                  color=color, fontweight='bold')

                # ── X轴标签（仅最后一行）──
                if i == n_ev - 1:
                    for ax_j in range(3):
                        axes_flat[row_base + ax_j].set_xlabel('时间 (s)',
                            fontsize=max(5, int(6 * fs)))

            # 第一行图例
            if n_ev > 0:
                axes_flat[0].legend(fontsize=max(4, int(5 * fs)), loc='upper left', framealpha=0.8)

            fig.suptitle(f'全部驾驶事件 — 实验组(蓝) vs 对照组(红) {loc_label}三轴加速度对比',
                        fontsize=10, fontweight='bold')
            fig.subplots_adjust(top=0.96, bottom=0.04, left=0.08, right=0.98,
                               wspace=0.25, hspace=0.40)
            return fig
        except Exception as e:
            logger.warning(f"生成事件概览图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_spectrum_overview_chart(self, card_widget: QWidget, spectrum: Dict,
                                           title_suffix: str = '') -> Optional[Figure]:
        """生成频域分析图（参照 OccupantMotionEvaluator.fig3_spectrum）

        紧凑布局: 1行3列 PSD (Ax/Ay/Az) — 专家方案 card_adapted_figure
        title_suffix: 位置标注（如 " — 头部"）
        Returns: Figure 对象，失败返回 None
        """
        if not spectrum:
            return None

        try:
            fig, axes, scale = card_adapted_figure(card_widget, 1, 3, height_mul=1.0)
            fs = np.sqrt(max(0.6, min(1.8, scale)))

            for col, axis_name in enumerate(['Ax', 'Ay', 'Az']):
                ax = axes[col]
                s = spectrum.get(axis_name)
                if not s:
                    ax.set_visible(False)
                    continue

                f_arr = np.array(s.get('freq', []))
                if len(f_arr) == 0:
                    ax.set_visible(False)
                    continue

                exp_psd = np.array(s.get('exp_psd', []))
                ctrl_psd = np.array(s.get('ctrl_psd', []))
                if len(exp_psd) > 0:
                    ax.semilogy(f_arr, exp_psd, color=ChartStyle.C_EXP,
                               linewidth=ChartStyle.LW_MAIN * scale, alpha=0.8, label='实验组')
                if len(ctrl_psd) > 0:
                    ax.semilogy(f_arr, ctrl_psd, color=ChartStyle.C_CTRL,
                               linewidth=ChartStyle.LW_MAIN * scale, alpha=0.8, label='对照组')
                ax.set_title(f'{axis_name}轴 — PSD', fontsize=10, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
                ax.set_ylabel('PSD (m²/s⁴/Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
                ax.legend(fontsize=max(6, ChartStyle.LEGEND_SIZE * fs))
                ax.grid(True, alpha=0.15)

            fig.suptitle(f'频域分析 — 实验组 vs 对照组 (PSD){title_suffix}',
                        fontsize=10, fontweight='bold')
            fig.tight_layout(pad=1.2 * scale)
            return fig
        except Exception as e:
            logger.warning(f"生成频域分析图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_stft_overview_chart(self, card_widget: QWidget, stft: Dict) -> Optional[Figure]:
        """生成 STFT 时频图（参照 OccupantMotionEvaluator.fig4_stft）

        2面板: 实验组 Ay | 对照组 Ay 时频谱
        Returns: Figure 对象，失败返回 None
        """
        if not stft:
            return None
        s = stft.get('Ay')
        if not s:
            return None

        f_arr = np.array(s.get('f', []))
        t_arr = np.array(s.get('t', []))
        exp_spec = np.array(s.get('exp_spec', []))
        ctrl_spec = np.array(s.get('ctrl_spec', []))

        if len(f_arr) == 0 or len(t_arr) == 0:
            return None

        f_mask = f_arr <= 50
        f_filt = f_arr[f_mask]
        exp_filt = exp_spec[f_mask, :len(t_arr)] if exp_spec.shape[0] == len(f_arr) else None
        ctrl_filt = ctrl_spec[f_mask, :len(t_arr)] if ctrl_spec.shape[0] == len(f_arr) else None

        try:
            fig, axes, scale = card_adapted_figure(card_widget, 2, 1, height_mul=2.0, radar=False)
            fs = np.sqrt(max(0.6, min(1.8, scale)))
            ax1, ax2 = axes[0], axes[1]

            if exp_filt is not None and exp_filt.size > 0:
                im1 = ax1.pcolormesh(t_arr, f_filt, exp_filt,
                                     shading='gouraud', cmap='viridis', norm=LogNorm())
                plt.colorbar(im1, ax=ax1, label='Magnitude')
            ax1.set_ylabel('频率 (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax1.set_title('实验组 — 头部Ay 时频谱', fontsize=10, fontweight='bold')

            if ctrl_filt is not None and ctrl_filt.size > 0:
                im2 = ax2.pcolormesh(t_arr, f_filt, ctrl_filt,
                                     shading='gouraud', cmap='viridis', norm=LogNorm())
                plt.colorbar(im2, ax=ax2, label='Magnitude')
            ax2.set_ylabel('频率 (Hz)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax2.set_xlabel('时间 (s)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            ax2.set_title('对照组 — 头部Ay 时频谱', fontsize=10, fontweight='bold')

            fig.suptitle('时频分析 (STFT) — Ay 横向加速度',
                        fontsize=10, fontweight='bold')
            fig.tight_layout(pad=1.2 * scale)
            return fig
        except Exception as e:
            logger.warning(f"生成 STFT 图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_statistics_distribution_chart(self, card_widget: QWidget, overview_data: Optional[Dict]) -> Optional[Figure]:
        """生成统计分布与箱线图（参照 OccupantMotionEvaluator.fig5_statistics）

        2x3网格: 上排=分布直方图, 下排=箱线图 (Ax/Ay/Az)
        Returns: Figure 对象，失败返回 None
        """
        if not overview_data:
            return None
        exp_ax = np.array(overview_data.get('exp_ax', []))
        exp_ay = np.array(overview_data.get('exp_ay', []))
        exp_az = np.array(overview_data.get('exp_az', []))
        ctrl_ax = np.array(overview_data.get('ctrl_ax', []))
        ctrl_ay = np.array(overview_data.get('ctrl_ay', []))
        ctrl_az = np.array(overview_data.get('ctrl_az', []))

        data_map = {
            'Ax': (exp_ax, ctrl_ax, '#2196F3'),
            'Ay': (exp_ay, ctrl_ay, '#4CAF50'),
            'Az': (exp_az, ctrl_az, '#FF9800'),
        }

        try:
            fig, axes, scale = card_adapted_figure(card_widget, 2, 3, height_mul=2.0, radar=False)
            fs = np.sqrt(max(0.6, min(1.8, scale)))

            for coli, (axis_name, color) in enumerate([('Ax', '#2196F3'), ('Ay', '#4CAF50'), ('Az', '#FF9800')]):
                evals, cvals, _ = data_map[axis_name]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() < 50:
                    axes[0, coli].set_visible(False)
                    axes[1, coli].set_visible(False)
                    continue

                axes[0, coli].hist(evals[valid], bins=100, alpha=0.5, density=True,
                                   color=color, label='实验组')
                axes[0, coli].hist(cvals[valid], bins=100, alpha=0.5, density=True,
                                   color='gray', label='对照组')
                axes[0, coli].set_title(f'{axis_name} Distribution',
                                       fontsize=10, fontweight='bold')
                axes[0, coli].legend(fontsize=max(6, ChartStyle.LEGEND_SIZE * fs))
                axes[0, coli].grid(True, alpha=0.2)

                ds = max(1, int(len(evals[valid]) / 500))
                data_box = [evals[valid][::ds], cvals[valid][::ds]]
                bp = axes[1, coli].boxplot(data_box, labels=['Active', 'Passive'],
                                            patch_artist=True,
                                            boxprops=dict(facecolor=color, alpha=0.5))
                axes[1, coli].set_title(f'{axis_name} Box Plot',
                                       fontsize=10, fontweight='bold')
                axes[1, coli].grid(True, alpha=0.2)

            fig.suptitle('统计学分析 — 实验组 vs 对照组',
                        fontsize=10, fontweight='bold')
            fig.tight_layout(pad=1.2 * scale)
            return fig
        except Exception as e:
            logger.warning(f"生成统计分布图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_band_radar_chart(self, card_widget: QWidget, spectrum: Dict) -> Optional[Figure]:
        """生成全频段衰减雷达图（参照 OccupantMotionEvaluator.fig6_band_radar）

        极坐标: 5频段 x 3轴(Ax/Ay/Az) 衰减率
        Returns: Figure 对象，失败返回 None
        """
        if not spectrum:
            return None

        bands_5 = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']

        try:
            fig, ax, scale = card_adapted_figure(card_widget, 1, 1, height_mul=1.0, radar=True)
            fs = np.sqrt(max(0.6, min(1.8, scale)))
            angles = np.linspace(0, 2 * np.pi, len(bands_5), endpoint=False).tolist()
            angles += angles[:1]

            for axis_name, color, marker in [('Ax', 'blue', 'o'), ('Ay', 'green', 's'), ('Az', 'orange', '^')]:
                s = spectrum.get(axis_name)
                if not s:
                    continue
                bands_atten = s.get('bands_atten', {})
                vals = [bands_atten.get(b, 0) for b in bands_5]
                vals_clipped = [max(-100, min(200, v)) for v in vals]
                vals_clipped += vals_clipped[:1]
                ax.plot(angles, vals_clipped, marker=marker, linestyle='-', color=color,
                        linewidth=ChartStyle.LW_MAIN * scale * 1.5, label=axis_name,
                        markersize=max(3, ChartStyle.MS * scale))
                ax.fill(angles, vals_clipped, alpha=0.1, color=color)

            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(bands_5, fontsize=max(7, int(ChartStyle.TICK_SIZE * fs)))
            ax.set_title('频段衰减雷达图\n(实验组 vs 对照组)',
                         fontsize=10, fontweight='bold', pad=10)
            ax.legend(loc='upper right', bbox_to_anchor=(1.2, 1.0),
                     fontsize=max(6, ChartStyle.LEGEND_SIZE * fs))
            # 数据自适应范围，至少覆盖 ±50
            ax.set_ylim(-50, max(100, ax.get_ylim()[1]))
            # 添加 0% 衰减率参考圆环
            ax.plot(angles, [0] * len(angles), 'k--', linewidth=0.6, alpha=0.3)
            fig.tight_layout(pad=1.2 * scale)
            return fig
        except Exception as e:
            logger.warning(f"生成频段雷达图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_stat_features_chart(self, card_widget: QWidget, metrics: Dict,
                                         location_label: str = '') -> Optional[Figure]:
        """生成统计特征(算子级输出)图表 — 2x3 子图: VDV/Crest/Skew/Kurt/MAV/Impulse

        location_label: 数据来源位置标注（如 "头部"），为空则不显示
        Returns: Figure 对象，失败返回 None
        """
        if not metrics:
            return None

        try:
            fig, axes, scale = card_adapted_figure(card_widget, nrows=2, ncols=3, height_mul=2.0)
            fs = np.sqrt(max(0.6, min(1.8, scale)))
            axes_flat = np.array(axes).ravel()

            metric_keys = ['VDV', 'CrestFactor', 'Skewness', 'Kurtosis', 'MAV', 'ImpulseFactor']
            metric_cn = ['振动剂量值(VDV)', '峰值因数(Crest)', '偏度(Skew)', '峭度(Kurt)', '平均绝对值(MAV)', '冲击指数(Impulse)']
            axes_names = ['Ax', 'Ay', 'Az']
            x = np.arange(len(axes_names))
            width = 0.35

            for idx, (mkey, mlabel) in enumerate(zip(metric_keys, metric_cn)):
                ax = axes_flat[idx]
                exp_vals = []
                ctrl_vals = []
                for a in axes_names:
                    ev = metrics.get(f'exp_{a}_{mkey}', np.nan)
                    cv = metrics.get(f'ctrl_{a}_{mkey}', np.nan)
                    exp_vals.append(ev if np.isfinite(ev) else 0.0)
                    ctrl_vals.append(cv if np.isfinite(cv) else 0.0)

                x_pos = np.arange(len(axes_names))
                ax.bar(x_pos - width/2, exp_vals, width, label='实验组',
                       color=ChartStyle.C_EXP, edgecolor='white', linewidth=0.5)
                ax.bar(x_pos + width/2, ctrl_vals, width, label='对照组',
                       color=ChartStyle.C_CTRL, edgecolor='white', linewidth=0.5)

                ax.set_title(mlabel, fontsize=10,
                            fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(axes_names, fontsize=max(7, int(ChartStyle.TICK_SIZE * fs)))
                ax.tick_params(axis='y', labelsize=max(6, int(ChartStyle.TICK_SIZE * fs * 0.9)))
                if idx == 0:
                    ax.legend(fontsize=max(6, int(ChartStyle.LEGEND_SIZE * fs)),
                             loc='upper left')

            title_text = '统计特征 (算子级输出) — 实验组 vs 对照组'
            if location_label:
                title_text += f' ({location_label})'
            fig.suptitle(title_text,
                        fontsize=10, fontweight='bold', y=0.99)
            fig.tight_layout(rect=[0, 0, 1, 0.95], pad=1.0 * scale)
            return fig
        except Exception as e:
            logger.warning(f"生成统计特征图表失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    @staticmethod
    def _clean_imu_data(arr: np.ndarray, clip_percentile: float = 99.9, smooth_alpha: float = 0.0) -> np.ndarray:
        """参照 IMU 可视化模块的数据清洗策略:
        1. NaN/Inf → 插值填充
        2. 异常值裁剪: 超过 clip_percentile 分位数的值钳制到边界 (保留99.9%有效数据)
        3. 低通平滑: 指数移动平均 (alpha=0 则跳过)

        Args:
            arr: 原始数据数组
            clip_percentile: 裁剪分位数 (默认 99.9，即裁剪 0.05% 极端值)
            smooth_alpha: EMA 平滑系数 (0.0=不平滑，0.3=参照 _filter_low_pass)
        """
        if len(arr) < 2:
            return arr.copy()
        out = arr.copy().astype(np.float64)

        # 1. NaN/Inf → 前后相邻值线性插值
        mask = ~np.isfinite(out)
        if mask.any():
            valid_idx = np.where(~mask)[0]
            if len(valid_idx) > 0:
                out[mask] = np.interp(np.where(mask)[0], valid_idx, out[valid_idx])
            else:
                out[:] = 0.0

        # 2. 异常值裁剪: 基于百分位数的钳制
        lo = np.percentile(out, 100.0 - clip_percentile)
        hi = np.percentile(out, clip_percentile)
        if hi - lo > 1e-9:
            out = np.clip(out, lo, hi)

        # 3. 低通平滑 (EMA, 参照 _filter_low_pass)
        if smooth_alpha > 0:
            smoothed = out.copy()
            for i in range(1, len(out)):
                smoothed[i] = smooth_alpha * out[i] + (1.0 - smooth_alpha) * smoothed[i - 1]
            out = smoothed

        return out


    def _generate_multi_location_accel_chart(self, card_widget: QWidget, overview_data: Optional[Dict], events: List[Dict] = None) -> Optional[Figure]:
        """生成多部位三轴加速度合成图 — 3面板: X轴/Y轴/Z轴

        每面板叠加 4 个身体部位（头部/胸剑突/座垫R点/座椅底部）的实验组+对照组曲线。
        实验组=实线，对照组=虚线，采用强对比色区分部位。

        Returns: Figure 对象，失败返回 None
        """
        if not overview_data:
            return None
        multi = overview_data.get('multi_location')
        if not multi:
            return None

        events = events or []

        # ── 部位配色方案（实验组暖色 vs 对照组冷色，每位置强对比反色）──
        # 4部位 × 2组 = 8条曲线，暖/冷色调区分实验/对照，各部位色相显著分离
        PART_COLORS = {
            'head':        {'exp': '#E74C3C', 'ctrl': '#3498DB'},  # 头部: 红 vs 蓝
            'sternum':     {'exp': '#E67E22', 'ctrl': '#2ECC71'},  # 胸剑突: 橙 vs 绿
            'seat_r':      {'exp': '#F39C12', 'ctrl': '#9B59B6'},  # 座垫R点: 金 vs 紫
            'seat_bottom': {'exp': '#1ABC9C', 'ctrl': '#E91E63'},  # 座椅底部: 青 vs 粉
        }

        # 事件类型 → 颜色
        EVENT_COLORS = {
            'hard_acceleration': '#E74C3C', 'hard_braking': '#E74C3C',
            'sharp_turning': '#9B59B6', 'overspeeding': '#F39C12',
            'lane_change': '#3498DB', 'severe_bump': '#16A085',
            'skid_risk': '#C0392B', 'rollover_risk': '#C0392B',
        }

        try:
            fig, axes, scale = card_adapted_figure(card_widget, 3, 1, height_mul=3.5)
            fs = np.sqrt(max(0.6, min(1.8, scale)))

            axis_names = ['Ax', 'Ay', 'Az']
            axis_keys = ['exp_ax', 'exp_ay', 'exp_az']
            axis_ctrl_keys = ['ctrl_ax', 'ctrl_ay', 'ctrl_az']

            for panel_idx, (ax_name, data_key, ctrl_key) in enumerate(zip(axis_names, axis_keys, axis_ctrl_keys)):
                ax_sp = axes[panel_idx]

                for part_id, part_data in multi.items():
                    pt_colors = PART_COLORS.get(part_id, {'exp': '#888888', 'ctrl': '#666666'})
                    color_exp = pt_colors['exp']
                    color_ctrl = pt_colors['ctrl']
                    label = part_data.get('label', part_id)

                    # 统一细线宽
                    lw = max(0.5, 0.7 * scale)

                    # 实验组（实线）
                    exp_arr = part_data.get(data_key)
                    if exp_arr is not None and len(exp_arr) > 2:
                        ts_arr = part_data.get('timestamps', np.arange(len(exp_arr)))
                        if len(ts_arr) != len(exp_arr):
                            ts_arr = np.arange(len(exp_arr))
                        clean_exp = self._clean_imu_data(exp_arr, clip_percentile=99.9, smooth_alpha=0.0)
                        step = max(1, len(ts_arr) // 3000)
                        ax_sp.plot(ts_arr[::step], clean_exp[::step],
                                  color=color_exp, linewidth=lw, alpha=0.88,
                                  solid_capstyle='round', label=f'{label} 实验组')

                    # 对照组（实线 + 对比反色）
                    ctrl_arr = part_data.get(ctrl_key)
                    if ctrl_arr is not None and len(ctrl_arr) > 2:
                        ts_arr = part_data.get('timestamps', np.arange(len(ctrl_arr)))
                        if len(ts_arr) != len(ctrl_arr):
                            ts_arr = np.arange(len(ctrl_arr))
                        clean_ctrl = self._clean_imu_data(ctrl_arr, clip_percentile=99.9, smooth_alpha=0.0)
                        step = max(1, len(ts_arr) // 3000)
                        ax_sp.plot(ts_arr[::step], clean_ctrl[::step],
                                  color=color_ctrl, linewidth=lw, alpha=0.88,
                                  linestyle='--', solid_capstyle='round', label=f'{label} 对照组')

                ax_sp.set_ylabel(f'{ax_name} (m/s²)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
                ax_sp.grid(alpha=0.2, linewidth=0.5)
                ax_sp.axhline(y=0, color='#999', linewidth=0.5, linestyle=':', alpha=0.4)

                # 事件色块（限前 20 个）
                all_ts = None
                for pd_ in multi.values():
                    ts_ = pd_.get('timestamps')
                    if ts_ is not None and len(ts_) > 0:
                        all_ts = ts_
                        break
                t_max = all_ts[-1] if all_ts is not None and len(all_ts) > 0 else 1e6
                for idx, evt in enumerate(events[:20]):
                    if not isinstance(evt, dict):
                        continue
                    t0 = float(evt.get('t_start', evt.get('start_time', 0)))
                    t1 = float(evt.get('t_end', evt.get('end_time', t0 + 0.5)))
                    if t1 <= t0:
                        t1 = t0 + 0.5
                    et = evt.get('event_type', evt.get('type', ''))
                    color = EVENT_COLORS.get(et, '#3498DB')
                    ax_sp.axvspan(t0, min(t1, t_max), alpha=0.08, color=color, linewidth=0)

                # 图例（仅第一面板）
                if panel_idx == 0:
                    ax_sp.legend(fontsize=max(5, int(7 * fs)), loc='upper right', ncol=2)

            axes[0].set_title('多部位三轴加速度合成图 (头部/胸剑突/座垫R点/座椅底部)', fontsize=10, fontweight='bold')
            axes[-1].set_xlabel('时间 (s)', fontsize=max(7, int(ChartStyle.LABEL_SIZE * fs)))
            for ax_sp in axes:
                ax_sp.tick_params(colors='#555555')

            fig.subplots_adjust(top=0.92, bottom=0.10, left=0.12, right=0.97, hspace=0.22)
            return fig
        except Exception as e:
            logger.warning(f"生成多部位加速度合成图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _populate_behavior_events(self, report: Dict):
        # ── 约束内容宽度 ──
        self._constrain_content_width()
        # ── 时序概览图 ──
        overview_data = report.get('_overview_data')
        if overview_data:
            adapted_ov = self._adapt_chart_overview_data(overview_data)
            # 从报告中获取事件数据
            ev = []
            try:
                ev = report.get('behavior_summary', {}).get('events', [])
                if not ev:
                    ev = getattr(self, '_behavior_events_for_timeline', [])
            except Exception:
                ev = []
            # ── 多部位三轴加速度合成图 (头部/胸剑突/座垫R点/座椅底部 X/Y/Z轴) ──
            fig_behavior = self._generate_multi_location_accel_chart(self._behavior_overview_chart, adapted_ov, ev)
            if fig_behavior:
                self._create_chart_canvas(fig_behavior, self._behavior_overview_chart)
                self._behavior_overview_chart.setVisible(True)
            else:
                self._behavior_overview_chart.setVisible(False)

        behavior_summary = report.get('behavior_summary', {})
        events = behavior_summary.get('events', [])
        total_events = behavior_summary.get('total_events', len(events))

        # ── 事件类型→中文（提前加载，供摘要使用）──
        event_cn_names = {}
        try:
            from core.core.analysis.layer3_maneuver_segmentation.event_detector import EVENT_TYPES
            event_cn_names.update(EVENT_TYPES)
        except ImportError:
            pass
        try:
            from core.core.analysis.core_types import BEHAVIOR_LABELS_CN as _BL
            event_cn_names.update(_BL)
        except ImportError:
            pass

        if total_events > 0:
            # ── 动态摘要：展示所有检测到的事件类型及数量 ──
            event_types = behavior_summary.get('event_types', {})
            if event_types:
                # 取数量最多的前 6 种事件类型
                top_types = sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:6]
                parts = [f"共检测到 {total_events} 个行为事件"]
                for et, cnt in top_types:
                    cn = event_cn_names.get(et, et)
                    parts.append(f"{cn}:{cnt}")
                self._behavior_summary_label.setText("  |  ".join(parts))
            else:
                self._behavior_summary_label.setText(
                    f"共检测到 {total_events} 个行为事件  "
                    f"急加速:{behavior_summary.get('hard_acceleration_count',0)}  |  "
                    f"急刹车:{behavior_summary.get('hard_braking_count',0)}  |  "
                    f"急转弯:{behavior_summary.get('sharp_turning_count',0)}  |  "
                    f"超速:{behavior_summary.get('overspeeding_count',0)}"
                )
        else:
            self._behavior_summary_label.setText("未检测到异常瞬时行为事件")

        table = self._behavior_events_table
        table.setRowCount(0)
        table.setRowCount(len(events))

        # ── 事件类型→颜色：优先使用 TYPE_COLORS ──
        try:
            from core.core.seat_evaluation.eval_queue import TYPE_COLORS as _TYPE_COLORS
            event_colors = dict(_TYPE_COLORS)
        except ImportError:
            event_colors = {}
        # 补充 BEHAVIOR_COLORS 中可能缺失的
        event_colors.update(BEHAVIOR_COLORS)

        # ── 轴峰值映射：不同事件类型关注不同轴向 ──
        AXIS_PEAK_MAP = {
            # 纵向（X轴）：加速/减速/制动类
            'aggressive_acceleration': ('accel_max', 'X'),
            'aggressive_deceleration': ('decel_min', 'X'),
            'emergency_braking': ('accel_max', 'X'),
            'normal_acceleration': ('accel_max', 'X'),
            'normal_deceleration': ('decel_min', 'X'),
            'cornering_acceleration': ('accel_max', 'X'),
            'cornering_deceleration': ('decel_min', 'X'),
            # 横向（Y轴）：转向类
            'tight_turn': ('ay_max', 'Y'),
            'wide_turn': ('ay_max', 'Y'),
            'u_turn': ('ay_max', 'Y'),
            'left_turn': ('ay_max', 'Y'),
            'right_turn': ('ay_max', 'Y'),
            'lane_change': ('ay_max', 'Y'),
            'weaving': ('ay_max', 'Y'),
            'rapid_direction_change': ('ay_max', 'Y'),
            'skid_risk': ('ay_max', 'Y'),
            'rollover_risk': ('ay_max', 'Y'),
            # 垂向（Z轴）：颠簸类
            'severe_bump': ('az_max', 'Z'),
        }

        for i, evt in enumerate(events):
            if not isinstance(evt, dict):
                continue

            # ── 统一适配：兼容 Batch 分析格式和 SQLite 格式 ──
            evt_type = evt.get('event_type', evt.get('type', 'unknown'))
            evt_name = evt.get('event_name', evt.get('name', ''))
            t_start = evt.get('t_start', evt.get('start_time', 0))
            t_end = evt.get('t_end', evt.get('end_time', 0))
            features = evt.get('features', {})
            if not features:
                # SQLite 格式：features 字段直接展开在事件 dict 顶层
                features = {k: v for k, v in evt.items()
                           if k not in ('id', 'type', 'name', 'start_time', 'end_time',
                                        'duration', 'confidence', 'event_type', 'event_name',
                                        't_start', 't_end', 'duration_s', 'event_id',
                                        'speed_at_start', 'speed_at_end', 'speed_delta')}

            # 瞬时车速：优先用 enriched 字段，否则从 features/speed_from 取
            speed_at_start = evt.get('speed_at_start', None)
            if speed_at_start is None:
                speed_at_start = features.get('speed_at_brake',
                                              features.get('speed_from',
                                              features.get('speed', 0)))

            # 区间车速变化
            speed_delta = evt.get('speed_delta', None)
            if speed_delta is None:
                speed_delta = features.get('speed_delta', 0)
            # SQLite 格式可能有 speed_from/speed_to
            if speed_delta == 0:
                sf = features.get('speed_from', features.get('speed_to', 0))
                st = features.get('speed_to', 0)
                if sf and st:
                    speed_delta = float(st) - float(sf)

            # ── 区间峰值（轴向） ──
            peak_feat_key, axis_label = AXIS_PEAK_MAP.get(evt_type, (None, ''))
            if peak_feat_key:
                peak_val = features.get(peak_feat_key, 0)
                if peak_feat_key == 'decel_min':
                    peak_val = abs(peak_val)  # decel_min 是负值，取绝对值
                # 单位: m/s² → g
                peak_val_g = peak_val / 9.81
                peak_str = f"{axis_label}:{peak_val_g:+.2f}g"
            else:
                # 通用：取 accel_max/ay_max/az_max 中最大值
                candidates = []
                for k in ('accel_max', 'ay_max', 'az_max'):
                    v = features.get(k, 0)
                    if v:
                        candidates.append((abs(v), k[0].upper(), v))
                if candidates:
                    _, label, val = max(candidates, key=lambda x: x[0])
                    peak_str = f"{label}:{val / 9.81:+.2f}g"
                else:
                    peak_str = '--'

            # ── 中文事件类型名 ──
            type_cn = evt_name if evt_name and evt_name != evt_type else event_cn_names.get(evt_type, evt_type)
            type_color = event_colors.get(evt_type, '#95A5A6')

            # 1. 序号
            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, idx_item)

            # 2. 事件类型（中文 + 着色）
            type_item = QTableWidgetItem(type_cn)
            type_item.setForeground(QColor(type_color))
            type_item.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
            table.setItem(i, 1, type_item)

            # 3. 时间区间
            time_item = QTableWidgetItem(f"{t_start:.1f} ~ {t_end:.1f}")
            time_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 2, time_item)

            # 4. 瞬时车速
            sp_item = QTableWidgetItem(f"{speed_at_start:.0f}")
            sp_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 3, sp_item)

            # 5. 区间车速变化
            sd_text = f"{speed_delta:+.0f}" if speed_delta != 0 else "0"
            sd_item = QTableWidgetItem(sd_text)
            sd_item.setTextAlignment(Qt.AlignCenter)
            if speed_delta > 0:
                sd_item.setForeground(QColor('#27AE60'))  # 加速绿色
            elif speed_delta < 0:
                sd_item.setForeground(QColor('#E74C3C'))  # 减速红色
            table.setItem(i, 4, sd_item)

            # 6. 区间峰值
            peak_item = QTableWidgetItem(peak_str)
            peak_item.setTextAlignment(Qt.AlignCenter)
            peak_item.setFont(QFont('Consolas', 9))
            table.setItem(i, 5, peak_item)

        table.setStyleSheet(self._card_table_style())

        # ── v8.0 移植: 驾驶行为事件分布图 (水平柱状图) ──
        event_types = behavior_summary.get('event_types', {})
        if event_types:
            try:
                # 事件颜色映射
                try:
                    from core.core.seat_evaluation.eval_queue import TYPE_COLORS as _TC
                    ev_colors = dict(_TC)
                except ImportError:
                    ev_colors = {}
                ev_colors.update(BEHAVIOR_COLORS)

                fig = Figure(figsize=(7, 3), dpi=ChartStyle.screen_dpi())
                ax = fig.add_subplot(111)
                types = list(event_types.keys())[:12]
                counts = [event_types[t] for t in types]
                colors = [ev_colors.get(t, '#3498DB') for t in types]
                # 转为中文标签显示
                cn_types = [event_cn_names.get(t, t) for t in types]
                ax.barh(range(len(types)), counts, color=colors, alpha=0.7, edgecolor='white')
                ax.set_yticks(range(len(types)))
                ax.set_yticklabels(cn_types, fontsize=8)
                ax.set_xlabel('事件数', fontsize=9)
                ax.set_title('驾驶行为事件分布', fontsize=10, fontweight='bold')
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.2)
                fig.tight_layout()
                self._create_chart_canvas(fig, self._behavior_dist_chart)
                self._behavior_dist_chart.setVisible(True)
            except Exception:
                self._behavior_dist_chart.setVisible(False)

        self._behavior_events_card.setVisible(True)

    def _populate_speed_histogram(self, labels, counts):
        """将速度频次数据填入 QTableWidget（3列：速度区间、频次、占比）"""
        table = self._cond_speed_hist_table
        table.setRowCount(0)
        total = sum(counts) if len(counts) > 0 else 0
        table.setRowCount(len(labels))
        for i, (label, count_val) in enumerate(zip(labels, counts)):
            table.setItem(i, 0, QTableWidgetItem(str(label)))
            table.setItem(i, 1, QTableWidgetItem(str(count_val)))
            pct = f"{count_val / total * 100:.1f}%" if total > 0 else "0%"
            pct_item = QTableWidgetItem(pct)
            pct_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 2, pct_item)
        table.setStyleSheet(self._card_table_style())

    def _populate_contrast_profile(self, report: Dict):
        locations = report.get('locations', {})
        any_contrast = False

        while self._contrast_grid_layout.count():
            item = self._contrast_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        while self._contrast_group_stats.count():
            item = self._contrast_group_stats.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        summary_notes = []
        ovtv_deltas = []
        improvement_count = 0
        degradation_count = 0

        for loc_id, loc_data in locations.items():
            contrast = loc_data.get('contrast', {})
            if not contrast:
                continue

            any_contrast = True
            label_cn = loc_data.get('label_cn', loc_id)

            frame = QFrame()
            frame.setStyleSheet(
                f"background: white; border: 1px solid {LC['border_light']}; border-radius: 4px; padding: 6px;"
            )
            row = QHBoxLayout(frame)
            row.setContentsMargins(8, 4, 8, 4)
            row.setSpacing(10)

            pos_lbl = QLabel(label_cn)
            pos_lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {LC['accent']}; background: transparent; min-width: 50px;")
            row.addWidget(pos_lbl)

            mag = contrast.get('magnitude', {})
            ovtv_delta = mag.get('OVTV', {})
            delta_str = ""
            if isinstance(ovtv_delta, dict) and 'delta_pct' in ovtv_delta:
                d = ovtv_delta['delta_pct']
                color = '#E74C3C' if abs(d) > 40 else ('#F39C12' if abs(d) > 15 else '#27AE60')
                delta_str = f"OVTV差: <span style='color:{color};font-weight:700;'>{d:+.1f}%</span>"

            awz = mag.get('AW_Z', {})
            if isinstance(awz, dict):
                awz_exp = awz.get('exp', awz.get('experimental', 0))
                awz_ctrl = awz.get('ctrl', awz.get('control', 0))
                delta_str += f"  |  AW_Z: {awz_exp:.3f} vs {awz_ctrl:.3f}"

            contrast_lbl = QLabel(delta_str)
            contrast_lbl.setStyleSheet(
                f"color: {LC['text_secondary']}; font-size: 9px; background: transparent;"
            )
            contrast_lbl.setTextFormat(Qt.RichText)
            row.addWidget(contrast_lbl, 1)

            freq = contrast.get('frequency_bands', {})
            dom_shift = max(
                freq.items(),
                key=lambda x: abs(x[1].get('shift') if isinstance(x[1], dict) and x[1].get('shift') is not None else 0)
            ) if freq else ('', {})
            freq_str = ""
            if dom_shift[0]:
                s = dom_shift[1].get('shift', 0)
                freq_str = f"主频移: {dom_shift[0]} {s:+.1f}%"

            imp = contrast.get('impact', {})
            imp_item = imp.get('crest_Z', {}) if isinstance(imp, dict) else {}
            imp_str = ""
            if isinstance(imp_item, dict) and 'delta_pct' in imp_item:
                imp_str = f"CF_Z: {imp_item['delta_pct']:+.1f}%"

            extra = QLabel(f"{freq_str}  {imp_str}")
            extra.setStyleSheet(f"color: {LC['text_muted']}; font-size: 9px; background: transparent;")
            row.addWidget(extra)

            self._contrast_grid_layout.addWidget(frame)

            note = contrast.get('summary_note', '')
            if note:
                summary_notes.append(f"[{label_cn}] {note}")

            ovtv_delta_val = ovtv_delta.get('delta_pct') if isinstance(ovtv_delta, dict) else None
            if ovtv_delta_val is not None:
                ovtv_deltas.append(ovtv_delta_val)
                if ovtv_delta_val < -5:
                    improvement_count += 1
                elif ovtv_delta_val > 5:
                    degradation_count += 1

        if ovtv_deltas:
            avg_delta = sum(ovtv_deltas) / len(ovtv_deltas)
            stats_html = (
                f"<div style='display: flex; gap: 16px;'>"
                f"<div style='text-align: center;'>"
                f"<div style='font-size: 16px; font-weight: 700; color: {'#27AE60' if avg_delta < 0 else '#E74C3C'};'>{avg_delta:+.1f}%</div>"
                f"<div style='font-size: 9px; color: {LC['text_muted']};'>平均OVTV变化</div>"
                f"</div>"
                f"<div style='text-align: center;'>"
                f"<div style='font-size: 16px; font-weight: 700; color: #27AE60;'>{improvement_count}</div>"
                f"<div style='font-size: 9px; color: {LC['text_muted']};'>改善位置</div>"
                f"</div>"
                f"<div style='text-align: center;'>"
                f"<div style='font-size: 16px; font-weight: 700; color: #E74C3C;'>{degradation_count}</div>"
                f"<div style='font-size: 9px; color: {LC['text_muted']};'>退化位置</div>"
                f"</div>"
                f"</div>"
            )
            stats_label = QLabel(stats_html)
            stats_label.setTextFormat(Qt.RichText)
            self._contrast_group_stats.addWidget(stats_label)

        if any_contrast and summary_notes:
            self._contrast_summary_label.setText("  ".join(summary_notes))
            self._contrast_summary_label.setVisible(True)
        else:
            self._contrast_summary_label.setVisible(False)

    def _populate_temporal_table(self, profiles: Dict[str, Dict], ctrl_profiles: Dict[str, Dict] = None):
        table = self._temporal_table
        table.clear()

        # ── 收集实验组片段 ──
        exp_segs: Dict[tuple, dict] = {}  # key=(label, t_range) → values
        for label, prof in profiles.items():
            temporal = prof.get('temporal') or {}
            segments = temporal.get('segments', []) if isinstance(temporal, dict) else []
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                t_range = f"{seg.get('t_start', 0):.0f}-{seg.get('t_end', 0):.0f}s"
                exp_segs[(label, t_range)] = {
                    'rms': seg.get('rms_g', 0),
                    'peak': seg.get('peak_g', 0),
                    'cf': seg.get('crest_factor', 0),
                }

        # ── 收集对照组片段 ──
        ctrl_segs: Dict[tuple, dict] = {}
        if ctrl_profiles:
            for label, ctrl_prof in ctrl_profiles.items():
                if not isinstance(ctrl_prof, dict):
                    continue
                temporal = ctrl_prof.get('temporal') or {}
                segments = temporal.get('segments', []) if isinstance(temporal, dict) else []
                for seg in segments:
                    if not isinstance(seg, dict):
                        continue
                    t_range = f"{seg.get('t_start', 0):.0f}-{seg.get('t_end', 0):.0f}s"
                    ctrl_segs[(label, t_range)] = {
                        'rms': seg.get('rms_g', 0),
                        'peak': seg.get('peak_g', 0),
                        'cf': seg.get('crest_factor', 0),
                    }

        # ── 并列行：统一按 (位置, 窗口) 合并 ──
        all_keys = sorted(set(list(exp_segs.keys()) + list(ctrl_segs.keys())))

        has_ctrl = bool(ctrl_profiles)
        if has_ctrl:
            cols = ['位置', '窗口(s)', '实验组RMS', '对照组RMS', '衰减率(%)',
                    '实验组Peak', '对照组Peak', '实验组CF', '对照组CF']
        else:
            cols = ['位置', '窗口(s)', 'RMS (g)', 'Peak (g)', '波峰因数']

        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(len(all_keys))

        exp_color = QColor('#3498DB')
        ctrl_color = QColor('#E67E22')

        for r, (label, t_range) in enumerate(all_keys):
            exp_val = exp_segs.get((label, t_range), {})
            ctrl_val = ctrl_segs.get((label, t_range), {})

            if has_ctrl:
                exp_rms = exp_val.get('rms', 0)
                ctrl_rms = ctrl_val.get('rms', 0)
                att_rms = ((exp_rms - ctrl_rms) / max(abs(exp_rms), abs(ctrl_rms), 1e-6)) * 100
                
                row_data = [
                    label, t_range,
                    f"{exp_rms:.2f}", f"{ctrl_rms:.2f}", f"{att_rms:+.1f}%",
                    f"{exp_val.get('peak', 0):.1f}", f"{ctrl_val.get('peak', 0):.1f}",
                    f"{exp_val.get('cf', 0):.1f}", f"{ctrl_val.get('cf', 0):.1f}",
                ]
                color_cols = [2, 5, 7]  # 实验组列着色: RMS, Peak, CF
                ctrl_cols = [3, 6, 8]   # 对照组列着色: RMS, Peak, CF
            else:
                row_data = [
                    label, t_range,
                    f"{exp_val.get('rms', 0):.2f}",
                    f"{exp_val.get('peak', 0):.1f}",
                    f"{exp_val.get('cf', 0):.1f}",
                ]

            for c, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if has_ctrl and c in color_cols:
                    item.setForeground(exp_color)
                elif has_ctrl and c in ctrl_cols:
                    item.setForeground(ctrl_color)
                table.setItem(r, c, item)

        table.resizeColumnsToContents()
        # 固定列宽
        table.setColumnWidth(0, 70)
        if has_ctrl:
            for c in range(1, len(cols)):
                table.setColumnWidth(c, max(80, table.columnWidth(c)))
        else:
            for c in range(1, len(cols)):
                table.setColumnWidth(c, 90)

    def _create_detail_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        self._detail_title = QLabel("指标详情")
        self._detail_title.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; "
            f"padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};"
        )
        title_row.addWidget(self._detail_title)
        title_row.addStretch()

        self._detail_open_btn = QPushButton("查阅完整详情")
        self._detail_open_btn.setFixedWidth(90)
        self._detail_open_btn.setStyleSheet(self._mini_btn_style())
        self._detail_open_btn.clicked.connect(self._on_open_detail_dialog)
        self._detail_open_btn.setCursor(Qt.PointingHandCursor)
        self._detail_open_btn.setVisible(False)
        title_row.addWidget(self._detail_open_btn)

        self._collapse_btn = QPushButton("收起")
        self._collapse_btn.setFixedWidth(52)
        self._collapse_btn.setStyleSheet(self._mini_btn_style())
        self._collapse_btn.clicked.connect(self._on_toggle_detail)
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        title_row.addWidget(self._collapse_btn)
        layout.addLayout(title_row)

        self._detail_content = QWidget()
        detail_layout = QVBoxLayout(self._detail_content)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self._detail_html = QLabel(
            "点击结果表格中的<span style='color:#4A90D9;'>指标数值</span>查看指标详情"
        )
        self._detail_html.setWordWrap(True)
        self._detail_html.setStyleSheet(
            f"font-size: 10px; color: {LC['text_muted']}; "
            f"padding: 8px; background: {LC['bg_input']}; border: 1px solid {LC['border_light']}; border-radius: 4px;"
        )
        self._detail_html.setTextFormat(Qt.RichText)
        detail_layout.addWidget(self._detail_html)
        layout.addWidget(self._detail_content)

        self._current_detail_code = None
        return card

    def _on_toggle_detail(self):
        visible = self._detail_content.isVisible()
        if visible:
            self._detail_content.setVisible(False)
            self._collapse_btn.setText("展开")
        else:
            self._detail_content.setVisible(True)
            self._collapse_btn.setText("收起")

    def _on_results_loc_filter_changed(self, index: int):
        if self._current_report:
            self._do_populate_results_table()

    def _on_result_cell_clicked(self, row: int, col: int):
        m_id = self._results_row_map.get(row)
        if m_id:
            self._show_indicator_detail_in_report(m_id)

    def _show_indicator_detail_in_report(self, indicator_code: str):
        meta = self._registry.get_indicator_meta(indicator_code)
        detail = self._registry.get_indicator_detail(indicator_code)
        threshold = self._registry.get_threshold(indicator_code)
        if not meta:
            self._detail_html.setText("未找到该指标的注册信息")
            self._detail_title.setText("指标详情")
            return

        self._current_detail_code = indicator_code
        self._detail_title.setText(f"指标详情: {meta.display_name_cn}")
        self._detail_open_btn.setVisible(True)

        pass_val = meta.threshold_pass or (threshold.get('pass') if threshold else '-')
        warn_val = (threshold.get('warn') if threshold else '-')
        excellent = meta.threshold_excellent or '-'

        refs_lines = ""
        if meta.standard_refs:
            refs_lines = "<br>".join([f"• {r}" for r in meta.standard_refs])
        else:
            refs_lines = "无标准引用"

        industry_lines = ""
        if meta.standard_refs:
            industry_lines = "<br>".join([f"• {r}" for r in meta.standard_refs])

        detail_html = (
            f"<table style='font-size:10px;width:100%;border-collapse:collapse;'>"
            f"<tr><td style='color:{LC['text_muted']};width:85px;'>指标编码</td>"
            f"<td style='color:{LC['text_accent']};font-weight:600;'>{meta.code}</td>"
            f"<td style='color:{LC['text_muted']};width:70px;'>单位</td><td>{meta.unit}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>中文名称</td><td>{meta.display_name_cn}</td>"
            f"<td style='color:{LC['text_muted']}'>英文</td><td style='font-size:9px;'>{meta.display_name_en}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>评测维度</td><td>{meta.evaluation_dimension}</td>"
            f"<td style='color:{LC['text_muted']}'>精度</td><td>{meta.precision}位</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>适用位置</td><td colspan='3'>{', '.join(meta.applicable_locations)}</td></tr>"
            f"</table>"
            f"<div style='margin-top:4px;font-size:10px;color:{LC['text_secondary']};'>"
            f"<b>公式:</b> {meta.formula_text}<br>"
            f"<b>管线:</b> {' → '.join(meta.operator_pipeline)}<br>"
            f"<b>阈值:</b> 通过={pass_val}, 警告={warn_val}, 优秀={excellent}, 方向={meta.direction.name}"
            f"</div>"
            f"<div style='margin-top:4px;font-size:9px;color:{LC['text_muted']};"
            f"border-top:1px solid {LC['border_light']};padding-top:3px;'>"
            f"<b>标准引用:</b><br>{refs_lines}"
        )
        if industry_lines:
            detail_html += f"<br><br><b>行业参考:</b><br>{industry_lines}"
        detail_html += "</div>"
        if detail:
            detail_html += (
                f"<div style='margin-top:3px;font-size:9px;color:{LC['text_muted']};"
                f"border-top:1px solid {LC['border_light']};padding-top:3px;'>"
                f"<b>计算逻辑:</b> {detail.calculation_logic}<br>"
                f"<b>数据字段:</b> {detail.data_fields or '-'}"
                f"</div>"
            )
        self._detail_html.setText(detail_html)

    def _on_open_detail_dialog(self):
        if not self._current_detail_code:
            return
        dialog = IndicatorDetailDialog(self._current_detail_code, self._registry, self)
        dialog.exec()

    def _primary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {LC['accent']}; color: white; font-weight: 600;
                border: none; border-radius: 5px; padding: 8px 20px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {LC['accent_hover']}; }}
            QPushButton:disabled {{ background: #CCC; }}
        """

    def _danger_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {LC['danger']}; color: white; border: none;
                border-radius: 5px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #C0392B; }}
            QPushButton:disabled {{ background: #CCC; }}
        """

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {LC['bg_input']}; color: {LC['text_secondary']};
                border: 1px solid {LC['border_light']}; border-radius: 4px;
                padding: 5px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ border-color: {LC['accent']}; color: {LC['accent']}; }}
        """

    def _export_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {LC['bg_input']}; color: {LC['text_secondary']};
                border: 1px solid {LC['border_light']}; border-radius: 4px;
                padding: 4px 10px; font-size: 10px;
            }}
            QPushButton:hover {{ background: {LC['bg_hover']}; border-color: {LC['accent']}; }}
            QPushButton:disabled {{ background: #EEE; color: #CCC; }}
        """

    def _mini_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: transparent; color: {LC['text_muted']};
                border: 1px solid {LC['border_light']}; border-radius: 3px;
                padding: 2px 6px; font-size: 9px;
            }}
            QPushButton:hover {{ border-color: {LC['accent']}; color: {LC['accent']}; }}
        """

    # ════ 全时域滑动窗口卡片 ════

    def _create_sliding_window_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("5.1 滑动窗口评坚决果 — 实验组/对照组 RMS 衰减率时序")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        header.addWidget(title)
        header.addStretch()

        self._export_window_csv_btn = QPushButton("导出窗口CSV")
        self._export_window_csv_btn.setStyleSheet(self._export_btn_style())
        self._export_window_csv_btn.setEnabled(False)
        self._export_window_csv_btn.clicked.connect(lambda: self._on_export_fulltimeseries('window_csv'))
        header.addWidget(self._export_window_csv_btn)

        layout.addLayout(header)

        self._window_table = QTableWidget()
        self._window_table.setAlternatingRowColors(True)
        self._window_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._window_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._window_table.verticalHeader().setVisible(False)
        self._window_table.verticalHeader().setDefaultSectionSize(24)
        self._window_table.setColumnCount(10)
        self._window_table.setHorizontalHeaderLabels([
            't_start(s)', 't_end(s)', '实验组RMS', '对照组RMS', '衰减率(%)',
            '实验组Peak', '对照组Peak', 'Peak衰减率(%)', 'Crest(Z)_exp', 'TR估算'
        ])
        self._window_table.setMinimumHeight(180)
        self._window_table.setAlternatingRowColors(True)
        self._window_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._window_table)

        # 摘要行
        self._window_summary_label = QLabel("窗口评测摘要将在分析完成后显示")
        self._window_summary_label.setStyleSheet(
            f"font-size: 10px; color: {LC['text_muted']}; padding: 4px 8px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )
        self._window_summary_label.setWordWrap(True)
        layout.addWidget(self._window_summary_label)

        return card

    def _create_events_ay_overview_card(self) -> QFrame:
        """创建「全部驾驶事件 — 三轴加速度对比」卡片

        包含两个独立图表容器:
        1. 头部(实验组) vs 头部(对照组) 三轴对比
        2. 座垫R点(实验组) vs 座垫R点(对照组) 三轴对比
        """
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("6. 全部驾驶事件 — 实验组(蓝) vs 对照组(红) 三轴加速度对比")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        # ── 头部事件概览图 ──
        head_label = QLabel("  ▸ 头部")
        head_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {LC['text_secondary']};")
        layout.addWidget(head_label)
        self._events_overview_head_chart = QWidget()
        self._events_overview_head_chart.setLayout(QVBoxLayout())
        self._events_overview_head_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._events_overview_head_chart.setMinimumHeight(180)
        self._events_overview_head_chart.setVisible(False)
        layout.addWidget(self._events_overview_head_chart)

        # ── 座垫R点事件概览图 ──
        seatr_label = QLabel("  ▸ 座垫R点")
        seatr_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {LC['text_secondary']};")
        layout.addWidget(seatr_label)
        self._events_overview_seatr_chart = QWidget()
        self._events_overview_seatr_chart.setLayout(QVBoxLayout())
        self._events_overview_seatr_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._events_overview_seatr_chart.setMinimumHeight(180)
        self._events_overview_seatr_chart.setVisible(False)
        layout.addWidget(self._events_overview_seatr_chart)

        return card

    def _create_statistics_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("15.1 统计检验 — 配对t检验 + Cohen's d + 95%置信区间")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._stats_table = QTableWidget()
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.verticalHeader().setDefaultSectionSize(24)
        self._stats_table.setColumnCount(8)
        self._stats_table.setHorizontalHeaderLabels([
            '轴向', 't统计量', 'p值', "Cohen's d", '置信下限(95%)', '置信上限(95%)', '显著性', '效应量'
        ])
        self._stats_table.setMaximumHeight(160)
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._stats_table)

        # 统计分布图（fig5_statistics: 分布直方图 + 箱线图 2x3）
        self._stats_distribution_chart = QWidget()
        self._stats_distribution_chart.setLayout(QVBoxLayout())
        self._stats_distribution_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._stats_distribution_chart.setMinimumHeight(200)
        self._stats_distribution_chart.setVisible(False)
        layout.addWidget(self._stats_distribution_chart)

        return card

    def _create_stat_features_card(self) -> QFrame:
        """创建统计特征(算子级输出)卡片 — VDV/Crest/Skew/Kurt/MAV/Impulse"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("7.3 统计特征 (算子级输出) — VDV / Crest / Skew / Kurt / MAV / Impulse")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        desc = QLabel("实验组 vs 对照组 三轴算子级统计量对比")
        desc.setStyleSheet(f"font-size: 11px; color: {LC['text_secondary']};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 图表容器
        self._stat_features_chart = QWidget()
        self._stat_features_chart.setLayout(QVBoxLayout())
        self._stat_features_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._stat_features_chart.setMinimumHeight(300)
        self._stat_features_chart.setVisible(False)
        layout.addWidget(self._stat_features_chart)

        self._stat_features_chart_2 = QWidget()
        self._stat_features_chart_2.setLayout(QVBoxLayout())
        self._stat_features_chart_2.layout().setContentsMargins(0, 0, 0, 0)
        self._stat_features_chart_2.setMinimumHeight(300)
        self._stat_features_chart_2.setVisible(False)
        layout.addWidget(self._stat_features_chart_2)

        self._stat_features_chart_3 = QWidget()
        self._stat_features_chart_3.setLayout(QVBoxLayout())
        self._stat_features_chart_3.layout().setContentsMargins(0, 0, 0, 0)
        self._stat_features_chart_3.setMinimumHeight(300)
        self._stat_features_chart_3.setVisible(False)
        layout.addWidget(self._stat_features_chart_3)

        self._stat_features_chart_4 = QWidget()
        self._stat_features_chart_4.setLayout(QVBoxLayout())
        self._stat_features_chart_4.layout().setContentsMargins(0, 0, 0, 0)
        self._stat_features_chart_4.setMinimumHeight(300)
        self._stat_features_chart_4.setVisible(False)
        layout.addWidget(self._stat_features_chart_4)

        return card

    def _create_band_radar_card(self) -> QFrame:
        """创建全频段衰减雷达图卡片（从统计检验分析中提取）"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("8. 频段衰减雷达图")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {LC['text_primary']};")
        layout.addWidget(title)

        desc = QLabel("实验组 vs 对照组 各频段衰减率对比")
        desc.setStyleSheet(f"font-size: 10px; color: {LC['text_muted']}; margin-bottom: 2px;")
        layout.addWidget(desc)

        self._band_radar_chart = QWidget()
        self._band_radar_chart.setLayout(QVBoxLayout())
        self._band_radar_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._band_radar_chart.setMinimumHeight(200)
        self._band_radar_chart.setVisible(False)
        layout.addWidget(self._band_radar_chart)

        return card

    def _create_advanced_card(self, title_text: str, desc: str, chart_key: str) -> QFrame:
        """创建高级可视化图表卡片 (统一工厂方法)"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        subtitle = QLabel(desc)
        subtitle.setStyleSheet(f"font-size: 11px; color: {LC['text_secondary']};")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 图表容器
        container_attr = f"_advanced_{chart_key}_container"
        chart_widget = QWidget()
        chart_widget.setLayout(QVBoxLayout())
        chart_widget.layout().setContentsMargins(0, 0, 0, 0)
        chart_widget.setMinimumHeight(180)
        chart_widget.setVisible(False)
        setattr(self, container_attr, chart_widget)
        layout.addWidget(chart_widget)

        return card

    def _create_band_attenuation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("7.1 频谱与频段衰减分析")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._band_table = QTableWidget()
        self._band_table.setAlternatingRowColors(True)
        self._band_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._band_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._band_table.verticalHeader().setVisible(False)
        self._band_table.verticalHeader().setDefaultSectionSize(24)
        self._band_table.setColumnCount(4)
        self._band_table.setHorizontalHeaderLabels([
            '频段', '实验组能量', '对照组能量', '衰减率(%)'
        ])
        self._band_table.setMaximumHeight(200)
        self._band_table.setAlternatingRowColors(True)
        self._band_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._band_table)

        self._band_coherence_label = QLabel("相干性: --")
        self._band_coherence_label.setStyleSheet(
            f"font-size: 10px; color: {LC['text_muted']}; padding: 4px 8px;"
        )
        layout.addWidget(self._band_coherence_label)

        # 频域分析图（fig3_spectrum: PSD / 衰减比 / 相干性 3x3）— 4 个位置
        self._spectrum_overview_chart = QWidget()
        self._spectrum_overview_chart.setLayout(QVBoxLayout())
        self._spectrum_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._spectrum_overview_chart.setMinimumHeight(200)
        self._spectrum_overview_chart.setVisible(False)
        layout.addWidget(self._spectrum_overview_chart)

        self._spectrum_overview_chart_2 = QWidget()
        self._spectrum_overview_chart_2.setLayout(QVBoxLayout())
        self._spectrum_overview_chart_2.layout().setContentsMargins(0, 0, 0, 0)
        self._spectrum_overview_chart_2.setMinimumHeight(200)
        self._spectrum_overview_chart_2.setVisible(False)
        layout.addWidget(self._spectrum_overview_chart_2)

        self._spectrum_overview_chart_3 = QWidget()
        self._spectrum_overview_chart_3.setLayout(QVBoxLayout())
        self._spectrum_overview_chart_3.layout().setContentsMargins(0, 0, 0, 0)
        self._spectrum_overview_chart_3.setMinimumHeight(200)
        self._spectrum_overview_chart_3.setVisible(False)
        layout.addWidget(self._spectrum_overview_chart_3)

        self._spectrum_overview_chart_4 = QWidget()
        self._spectrum_overview_chart_4.setLayout(QVBoxLayout())
        self._spectrum_overview_chart_4.layout().setContentsMargins(0, 0, 0, 0)
        self._spectrum_overview_chart_4.setMinimumHeight(200)
        self._spectrum_overview_chart_4.setVisible(False)
        layout.addWidget(self._spectrum_overview_chart_4)

        return card

    def _create_comprehensive_metrics_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("7.2 统计特征（算子级输出）— VDV / Crest / Skew / Kurt / MAV / Impulse")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._comp_metrics_table = QTableWidget()
        self._comp_metrics_table.setAlternatingRowColors(True)
        self._comp_metrics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_metrics_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._comp_metrics_table.verticalHeader().setVisible(False)
        self._comp_metrics_table.verticalHeader().setDefaultSectionSize(24)
        self._comp_metrics_table.setColumnCount(6)
        self._comp_metrics_table.setHorizontalHeaderLabels([
            '特征量', '中文指标名', '轴', '实验组', '对照组', '衰减率(%)'
        ])
        self._comp_metrics_table.setMinimumHeight(200)
        self._comp_metrics_table.setAlternatingRowColors(True)
        self._comp_metrics_table.setStyleSheet(self._card_table_style())
        layout.addWidget(self._comp_metrics_table)

        self._comp_attenuation_label = QLabel("衰减率摘要: --")
        self._comp_attenuation_label.setStyleSheet(
            f"font-size: 10px; color: {LC['success']}; padding: 4px 8px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )
        self._comp_attenuation_label.setWordWrap(True)
        layout.addWidget(self._comp_attenuation_label)

        # ── 位置 2: 胸剑突 ──
        self._comp_metrics_pos2_label = QLabel("")
        self._comp_metrics_pos2_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {LC['text_primary']}; padding: 8px 0 2px 0;")
        self._comp_metrics_pos2_label.setVisible(False)
        layout.addWidget(self._comp_metrics_pos2_label)

        self._comp_metrics_table_2 = QTableWidget()
        self._comp_metrics_table_2.setAlternatingRowColors(True)
        self._comp_metrics_table_2.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_metrics_table_2.setSelectionBehavior(QTableWidget.SelectRows)
        self._comp_metrics_table_2.verticalHeader().setVisible(False)
        self._comp_metrics_table_2.verticalHeader().setDefaultSectionSize(24)
        self._comp_metrics_table_2.setColumnCount(6)
        self._comp_metrics_table_2.setHorizontalHeaderLabels([
            '特征量', '中文指标名', '轴', '实验组', '对照组', '衰减率(%)'
        ])
        self._comp_metrics_table_2.setMinimumHeight(200)
        self._comp_metrics_table_2.setAlternatingRowColors(True)
        self._comp_metrics_table_2.setStyleSheet(self._card_table_style())
        self._comp_metrics_table_2.setVisible(False)
        layout.addWidget(self._comp_metrics_table_2)

        # ── 位置 3: 座垫R点 ──
        self._comp_metrics_pos3_label = QLabel("")
        self._comp_metrics_pos3_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {LC['text_primary']}; padding: 8px 0 2px 0;")
        self._comp_metrics_pos3_label.setVisible(False)
        layout.addWidget(self._comp_metrics_pos3_label)

        self._comp_metrics_table_3 = QTableWidget()
        self._comp_metrics_table_3.setAlternatingRowColors(True)
        self._comp_metrics_table_3.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_metrics_table_3.setSelectionBehavior(QTableWidget.SelectRows)
        self._comp_metrics_table_3.verticalHeader().setVisible(False)
        self._comp_metrics_table_3.verticalHeader().setDefaultSectionSize(24)
        self._comp_metrics_table_3.setColumnCount(6)
        self._comp_metrics_table_3.setHorizontalHeaderLabels([
            '特征量', '中文指标名', '轴', '实验组', '对照组', '衰减率(%)'
        ])
        self._comp_metrics_table_3.setMinimumHeight(200)
        self._comp_metrics_table_3.setAlternatingRowColors(True)
        self._comp_metrics_table_3.setStyleSheet(self._card_table_style())
        self._comp_metrics_table_3.setVisible(False)
        layout.addWidget(self._comp_metrics_table_3)

        # ── 位置 4: 座椅底部 ──
        self._comp_metrics_pos4_label = QLabel("")
        self._comp_metrics_pos4_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {LC['text_primary']}; padding: 8px 0 2px 0;")
        self._comp_metrics_pos4_label.setVisible(False)
        layout.addWidget(self._comp_metrics_pos4_label)

        self._comp_metrics_table_4 = QTableWidget()
        self._comp_metrics_table_4.setAlternatingRowColors(True)
        self._comp_metrics_table_4.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_metrics_table_4.setSelectionBehavior(QTableWidget.SelectRows)
        self._comp_metrics_table_4.verticalHeader().setVisible(False)
        self._comp_metrics_table_4.verticalHeader().setDefaultSectionSize(24)
        self._comp_metrics_table_4.setColumnCount(6)
        self._comp_metrics_table_4.setHorizontalHeaderLabels([
            '特征量', '中文指标名', '轴', '实验组', '对照组', '衰减率(%)'
        ])
        self._comp_metrics_table_4.setMinimumHeight(200)
        self._comp_metrics_table_4.setAlternatingRowColors(True)
        self._comp_metrics_table_4.setStyleSheet(self._card_table_style())
        self._comp_metrics_table_4.setVisible(False)
        layout.addWidget(self._comp_metrics_table_4)

        return card

    def _create_stft_card(self) -> QFrame:
        """STFT 时频分析卡片"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("13. 时频分析（STFT 时频谱）— 实验组 vs 对照组 Ay")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._stft_overview_chart = QWidget()
        self._stft_overview_chart.setLayout(QVBoxLayout())
        self._stft_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._stft_overview_chart.setMinimumHeight(200)
        self._stft_overview_chart.setVisible(False)
        layout.addWidget(self._stft_overview_chart)

        return card

    # ════ Populate 方法 ════

    def _normalize_timeseries_data(self, raw_results: dict) -> dict:
        """将 FullTimeseriesEvaluator.results 转换为 _populate_* 方法期望的格式"""
        if not raw_results:
            return {}

        normalized = {}

        # ── 1. 滑动窗口: DataFrame → list[dict] (列名映射) ──
        windows_raw = raw_results.get('windows', pd.DataFrame())
        if isinstance(windows_raw, pd.DataFrame) and not windows_raw.empty:
            df = windows_raw.copy()
            rename_map = {}
            if 't_center' in df.columns:
                df['t_start'] = df['t_center'] - 0.5
                df['t_end'] = df['t_center'] + 0.5
            for evaluator_col, ui_col in [
                ('e_Ax_RMS', 'RMS_X_exp'), ('e_Ay_RMS', 'RMS_Y_exp'), ('e_Az_RMS', 'RMS_Z_exp'),
                ('c_Ax_RMS', 'RMS_X_ctrl'), ('c_Ay_RMS', 'RMS_Y_ctrl'), ('c_Az_RMS', 'RMS_Z_ctrl'),
                ('atten_Ax_pct', 'RMS_attenuation_X_pct'), ('atten_Ay_pct', 'RMS_attenuation_Y_pct'),
                ('atten_Az_pct', 'RMS_attenuation_Z_pct'),
                ('e_total_RMS', 'RMS_res_exp'), ('c_total_RMS', 'RMS_res_ctrl'),
                ('e_Ax_Peak', 'Peak_X_exp'), ('e_Ay_Peak', 'Peak_Y_exp'), ('e_Az_Peak', 'Peak_Z_exp'),
                ('c_Ax_Peak', 'Peak_X_ctrl'), ('c_Ay_Peak', 'Peak_Y_ctrl'), ('c_Az_Peak', 'Peak_Z_ctrl'),
            ]:
                if evaluator_col in df.columns:
                    rename_map[evaluator_col] = ui_col
            df.rename(columns=rename_map, inplace=True)
            # 计算组合列
            for prefix_out, prefixes_in in [
                ('Peak_exp', ['Peak_X_exp', 'Peak_Y_exp', 'Peak_Z_exp']),
                ('Peak_ctrl', ['Peak_X_ctrl', 'Peak_Y_ctrl', 'Peak_Z_ctrl']),
            ]:
                cols_present = [c for c in prefixes_in if c in df.columns]
                if cols_present:
                    df[prefix_out] = df[cols_present].max(axis=1)
            if 'Peak_exp' in df.columns and 'Peak_ctrl' in df.columns:
                df['Peak_attenuation_pct'] = (1 - df['Peak_exp'] / df['Peak_ctrl'].replace(0, np.nan)) * 100
            # Crest_Z_exp (从 comprehensive_metrics 补充，若无则0)
            if 'Crest_Z_exp' not in df.columns:
                df['Crest_Z_exp'] = 0.0
            # TR_estimate (transfer_* 的平均)
            tr_cols = [c for c in df.columns if c.startswith('transfer_')]
            if tr_cols:
                df['TR_estimate'] = df[tr_cols].mean(axis=1)
            else:
                df['TR_estimate'] = 0.0
            if 'RMS_res_exp' in df.columns and 'RMS_res_ctrl' in df.columns:
                df['RMS_attenuation_pct'] = (1 - df['RMS_res_exp'] / df['RMS_res_ctrl'].replace(0, np.nan)) * 100
            normalized['windows'] = df

        # ── 2. 统计检验: 键名映射 (t_stat→t_statistic, ci_lo→ci_95_low) ──
        stats_raw = raw_results.get('statistics', {})
        if stats_raw:
            norm_stats = {}
            for axis, data in stats_raw.items():
                if isinstance(data, dict):
                    norm_stats[axis] = {
                        't_statistic': data.get('t_stat', 0),
                        'p_value': data.get('p_value', 1),
                        'cohens_d': data.get('cohens_d', 0),
                        'ci_95_low': data.get('ci_lo', 0),
                        'ci_95_high': data.get('ci_hi', 0),
                        'significance': data.get('significant', 'ns'),
                    }
            normalized['statistics'] = norm_stats

        # ── 3. 频谱频段衰减: 支持嵌套格式(head/Chest/...)和扁平格式(Ax/Ay/Az) ──
        spectrum_raw = raw_results.get('spectrum', {})
        if spectrum_raw:
            # 检测是否为嵌套格式: {body_part: {axis: data}}
            first_val = next(iter(spectrum_raw.values()), None)
            is_nested = isinstance(first_val, dict) and not any(
                k in first_val for k in ['freq', 'exp_psd', 'bands_atten']
            )
            if is_nested:
                # 嵌套格式: 取第一个位置(head)的数据用于频段表格和雷达图
                first_body = list(spectrum_raw.keys())[0]
                flat_spec = spectrum_raw[first_body]
            else:
                flat_spec = spectrum_raw

            bands = {}
            for axis_name, spec_data in flat_spec.items():
                if not isinstance(spec_data, dict):
                    continue
                bands_atten = spec_data.get('bands_atten', {})
                for band_name, att_val in bands_atten.items():
                    if band_name not in bands:
                        bands[band_name] = {'exp_energy': 0.0, 'ctrl_energy': 0.0, 'attenuation_pct': 0.0}
                    bands[band_name]['attenuation_pct'] = att_val
            # 计算平均相干性和总衰减（使用扁平化后的第一位置数据）
            coherences = []
            all_atten = []
            for spec_data in flat_spec.values():
                if isinstance(spec_data, dict):
                    coh = np.array(spec_data.get('coherence', []))
                    if len(coh) > 0:
                        coherences.append(float(np.nanmean(coh)))
                    for v in spec_data.get('bands_atten', {}).values():
                        all_atten.append(float(v) if isinstance(v, (int, float)) else 0)
            normalized['spectrum'] = {
                'bands': bands,
                'mean_coherence': float(np.nanmean(coherences)) if coherences else 0.0,
                'total_attenuation_pct': float(np.nanmean(all_atten)) if all_atten else 0.0,
            }

        # ── 4. 综合指标: 支持嵌套格式 {body: {exp_Ax_VDV}} 和扁平格式 {exp_Ax_VDV} ──
        metrics_raw = raw_results.get('metrics', {})
        if metrics_raw:
            def _normalize_one_metrics(raw: dict) -> dict:
                """将单位置扁平指标归一化为 {experimental, control, attenuation}"""
                experimental = {}
                control = {}
                metric_src_dst = {
                    'RMS': 'RMS', 'Peak': 'Peak', 'CrestFactor': 'Crest',
                    'VDV': 'VDV', 'Skewness': 'Skew', 'Kurtosis': 'Kurt',
                    'MAV': 'MAV', 'ImpulseFactor': 'Impulse',
                }
                axis_src_dst = {'Ax': 'X', 'Ay': 'Y', 'Az': 'Z'}
                for group_name, group_dict in [('exp', experimental), ('ctrl', control)]:
                    for m_src, m_dst in metric_src_dst.items():
                        for a_src, a_dst in axis_src_dst.items():
                            src_key = f'{group_name}_{a_src}_{m_src}'
                            dst_key = f'{m_dst}_{a_dst}'
                            if src_key in raw:
                                group_dict[dst_key] = float(raw[src_key]) if isinstance(raw[src_key], (int, float, np.floating)) else 0.0
                    # Total
                    for prefix, field in [('_Ax_RMS', 'RMS_res'), ('_total_VDV', 'VDV_total')]:
                        src_k = f'{group_name}{prefix}'
                        if src_k in raw:
                            group_dict[field] = float(raw[src_k]) if isinstance(raw.get(src_k), (int, float, np.floating)) else 0.0
                attenuation = {}
                for key in set(experimental.keys()) | set(control.keys()):
                    e_val = experimental.get(key, 0)
                    c_val = control.get(key, 0)
                    if isinstance(c_val, (int, float)) and abs(c_val) > 1e-9:
                        attenuation[f'{key}_pct'] = (1 - e_val / c_val) * 100
                return {'experimental': experimental, 'control': control, 'attenuation': attenuation}

            # 检测嵌套格式
            first_val = next(iter(metrics_raw.values()), None)
            is_nested = isinstance(first_val, dict) and any(
                k.startswith(('exp_', 'ctrl_')) for k in (first_val or {}).keys()
            )
            if is_nested:
                all_metrics = {}
                for body_key, body_raw in metrics_raw.items():
                    all_metrics[body_key] = _normalize_one_metrics(body_raw)
                normalized['comprehensive_metrics'] = all_metrics
            else:
                normalized['comprehensive_metrics'] = _normalize_one_metrics(metrics_raw)

        # STFT 直通
        normalized['stft'] = raw_results.get('stft', {})

        return normalized

    def _adapt_chart_overview_data(self, data: Optional[Dict]) -> Dict:
        """P2修复: 为 overview_data 添加字段别名，防止 Evaluator 字段名变更导致图表静默失效"""
        if not data or not isinstance(data, dict):
            return {}
        d = dict(data)  # 浅拷贝，保留原始字段
        # 字段别名映射: (备选名, 期望名)
        alias_map = [
            ('exp_ax', 'exp_ax'), ('experimental_ax', 'exp_ax'), ('ax_exp', 'exp_ax'),
            ('exp_ay', 'exp_ay'), ('experimental_ay', 'exp_ay'), ('ay_exp', 'exp_ay'),
            ('exp_az', 'exp_az'), ('experimental_az', 'exp_az'), ('az_exp', 'exp_az'),
            ('ctrl_ax', 'ctrl_ax'), ('control_ax', 'ctrl_ax'), ('ax_ctrl', 'ctrl_ax'),
            ('ctrl_ay', 'ctrl_ay'), ('control_ay', 'ctrl_ay'), ('ay_ctrl', 'ctrl_ay'),
            ('ctrl_az', 'ctrl_az'), ('control_az', 'ctrl_az'), ('az_ctrl', 'ctrl_az'),
            ('speed', 'speed'), ('vehicle_speed', 'speed'), ('speed_kmh', 'speed'),
            ('wheel', 'wheel'), ('steering_angle', 'wheel'), ('wheel_angle', 'wheel'),
        ]
        for src, dst in alias_map:
            if src in d and dst not in d:
                d[dst] = d[src]
        return d

    def _adapt_chart_spectrum_data(self, data: Dict) -> Dict:
        """P2修复: 为 spectrum 数据添加字段别名"""
        if not data or not isinstance(data, dict):
            return {}
        d = {}
        for axis_name in ['Ax', 'Ay', 'Az']:
            s = data.get(axis_name)
            if not isinstance(s, dict):
                continue
            axis_data = dict(s)
            # freq 别名
            for alias in ['freq', 'frequencies', 'frequency', 'f']:
                if alias in s and 'freq' not in axis_data:
                    axis_data['freq'] = s[alias]
            # exp_psd 别名
            for alias in ['exp_psd', 'experimental_psd', 'psd_exp']:
                if alias in s and 'exp_psd' not in axis_data:
                    axis_data['exp_psd'] = s[alias]
            # ctrl_psd 别名
            for alias in ['ctrl_psd', 'control_psd', 'psd_ctrl']:
                if alias in s and 'ctrl_psd' not in axis_data:
                    axis_data['ctrl_psd'] = s[alias]
            # ratio 别名
            for alias in ['ratio', 'attenuation_ratio', 'psd_ratio']:
                if alias in s and 'ratio' not in axis_data:
                    axis_data['ratio'] = s[alias]
            # coherence 别名
            for alias in ['coherence', 'coh', 'coherency']:
                if alias in s and 'coherence' not in axis_data:
                    axis_data['coherence'] = s[alias]
            d[axis_name] = axis_data
        return d

    def _adapt_chart_stft_data(self, data: Dict) -> Dict:
        """P2修复: 为 STFT 数据添加字段别名"""
        if not data or not isinstance(data, dict):
            return {}
        d = {}
        for axis_name in ['Ax', 'Ay', 'Az']:
            s = data.get(axis_name)
            if not isinstance(s, dict):
                continue
            axis_data = dict(s)
            for alias in ['f', 'freq', 'frequencies']:
                if alias in s and 'f' not in axis_data:
                    axis_data['f'] = s[alias]
            for alias in ['t', 'time', 'times']:
                if alias in s and 't' not in axis_data:
                    axis_data['t'] = s[alias]
            for alias in ['exp_spec', 'experimental_spectrum', 'spec_exp']:
                if alias in s and 'exp_spec' not in axis_data:
                    axis_data['exp_spec'] = s[alias]
            for alias in ['ctrl_spec', 'control_spectrum', 'spec_ctrl']:
                if alias in s and 'ctrl_spec' not in axis_data:
                    axis_data['ctrl_spec'] = s[alias]
            d[axis_name] = axis_data
        return d

    def _constrain_content_width(self):
        """约束 QScrollArea 内容宽度以匹配视口，防止水平滚动条"""
        viewport = self._scroll_area.viewport()
        if viewport and self._content_widget:
            vp_w = viewport.width()
            if vp_w > 100:
                self._content_widget.setMaximumWidth(vp_w)

    def _create_chart_canvas(self, fig: Figure, card_widget: QWidget):
        """将 matplotlib Figure 嵌入卡片容器 — 专家方案 card_adapted_figure 嵌入"""
        layout = card_widget.layout()
        if layout is None:
            return
        # 清除旧 canvas 并关闭旧 Figure 释放内存
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                old_widget = item.widget()
                # 提取旧 Canvas 的 Figure 并关闭
                if hasattr(old_widget, 'figure'):
                    try:
                        plt.close(old_widget.figure)
                    except Exception:
                        pass
                old_widget.deleteLater()

        # 统一 Figure DPI 为屏幕 DPI，避免 DESIGN_DPI(200) 导致的像素尺寸翻倍
        screen_dpi = ChartStyle.screen_dpi()
        fig.set_dpi(screen_dpi)

        # FigureCanvas: 使用 figure 自带的 DPI, 不缩放
        canvas = FigureCanvas(fig)
        fig_dpi = fig.get_dpi()
        fig_w_px = int(fig.get_figwidth() * fig_dpi)
        fig_h_px = int(fig.get_figheight() * fig_dpi)

        # 宽度跟随卡片, 高度固定为 Figure 像素高度 (防止 Qt 拉伸字体)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if fig_w_px > 100:
            canvas.setMinimumWidth(min(400, fig_w_px))
        if fig_h_px > 50:
            canvas.setFixedHeight(fig_h_px)
        canvas.setStyleSheet("background: white; border: none;")
        layout.addWidget(canvas)
        card_widget.setVisible(True)

    def _populate_sliding_window_results(self, window_results: list):
        """填充滑动窗口表格（兼容 DataFrame 和 list[dict]）"""
        self._window_table.setRowCount(0)
        if window_results is None or len(window_results) == 0:
            self._window_summary_label.setText("无窗口分析数据")
            return

        # 统一转换为 list[dict] 格式
        try:
            if isinstance(window_results, pd.DataFrame):
                records = window_results.to_dict('records')
            else:
                records = window_results
        except ImportError:
            records = window_results

        self._window_table.setRowCount(len(records))
        for i, row in enumerate(records):
            if not isinstance(row, dict):
                continue
            self._window_table.setItem(i, 0, QTableWidgetItem(f"{row.get('t_start', 0):.3f}"))
            self._window_table.setItem(i, 1, QTableWidgetItem(f"{row.get('t_end', 0):.3f}"))
            self._window_table.setItem(i, 2, QTableWidgetItem(f"{row.get('RMS_res_exp', 0):.4f}"))
            self._window_table.setItem(i, 3, QTableWidgetItem(f"{row.get('RMS_res_ctrl', 0):.4f}"))

            att_pct = row.get('RMS_attenuation_pct', 0)
            att_item = QTableWidgetItem(f"{att_pct:.1f}%")
            if att_pct >= 20:
                att_item.setForeground(QColor(LC['success']))
            elif att_pct >= 5:
                att_item.setForeground(QColor(LC['accent']))
            else:
                att_item.setForeground(QColor(LC['danger']))
            self._window_table.setItem(i, 4, att_item)

            self._window_table.setItem(i, 5, QTableWidgetItem(f"{row.get('Peak_exp', 0):.4f}"))
            self._window_table.setItem(i, 6, QTableWidgetItem(f"{row.get('Peak_ctrl', 0):.4f}"))
            self._window_table.setItem(i, 7, QTableWidgetItem(f"{row.get('Peak_attenuation_pct', 0):.1f}%"))
            self._window_table.setItem(i, 8, QTableWidgetItem(f"{row.get('Crest_Z_exp', 0):.1f}"))
            self._window_table.setItem(i, 9, QTableWidgetItem(f"{row.get('TR_estimate', 0):.3f}"))

        # 摘要
        att_vals = [w.get('RMS_attenuation_pct', 0) for w in records]
        mean_att = np.mean(att_vals) if att_vals else 0
        best = max(att_vals) if att_vals else 0
        worst = min(att_vals) if att_vals else 0
        self._window_summary_label.setText(
            f"共 {len(records)} 个窗口 | 平均衰减率: {mean_att:.1f}% | "
            f"最佳: {best:.1f}% | 最差: {worst:.1f}%"
        )

    def _populate_statistics_results(self, statistics: dict):
        """填充统计检验表格"""
        self._stats_table.setRowCount(0)
        axes = ['X', 'Y', 'Z', 'res']
        self._stats_table.setRowCount(len(axes))

        for i, axis in enumerate(axes):
            st = statistics.get(axis, {})
            self._stats_table.setItem(i, 0, QTableWidgetItem(axis))
            self._stats_table.setItem(i, 1, QTableWidgetItem(str(st.get('t_statistic', '-'))))
            self._stats_table.setItem(i, 2, QTableWidgetItem(f"{st.get('p_value', 1):.6f}"))
            self._stats_table.setItem(i, 3, QTableWidgetItem(str(st.get('cohens_d', '-'))))
            self._stats_table.setItem(i, 4, QTableWidgetItem(f"{st.get('ci_95_low', 0):.4f}"))
            self._stats_table.setItem(i, 5, QTableWidgetItem(f"{st.get('ci_95_high', 0):.4f}"))

            sig = st.get('significance', 'ns')
            sig_item = QTableWidgetItem(sig)
            if sig == '***':
                sig_item.setForeground(QColor('#E74C3C'))
                sig_item.setFont(QFont(sig_item.font().family(), -1, QFont.Bold))
            elif sig == '**':
                sig_item.setForeground(QColor('#E67E22'))
            elif sig == '*':
                sig_item.setForeground(QColor('#2ECC71'))
            else:
                sig_item.setForeground(QColor(LC['text_muted']))
            self._stats_table.setItem(i, 6, sig_item)

            # Cohen's d effect size interpretation
            d_val = st.get('cohens_d', 0)
            if abs(d_val) >= 0.8:
                effect = '大'
            elif abs(d_val) >= 0.5:
                effect = '中'
            elif abs(d_val) >= 0.2:
                effect = '小'
            else:
                effect = '微小'
            self._stats_table.setItem(i, 7, QTableWidgetItem(effect))

    def _populate_band_attenuation_results(self, spectrum: dict):
        """填充频段衰减表格"""
        self._band_table.setRowCount(0)
        bands = spectrum.get('bands', {})
        self._band_table.setRowCount(len(bands))

        sorted_bands = sorted(bands.items())
        for i, (band_name, data) in enumerate(sorted_bands):
            self._band_table.setItem(i, 0, QTableWidgetItem(band_name))
            self._band_table.setItem(i, 1, QTableWidgetItem(f"{data.get('exp_energy', 0):.4f}"))
            self._band_table.setItem(i, 2, QTableWidgetItem(f"{data.get('ctrl_energy', 0):.4f}"))

            att_pct = data.get('attenuation_pct', 0)
            att_item = QTableWidgetItem(f"{att_pct}%")
            if att_pct >= 20:
                att_item.setForeground(QColor(LC['success']))
            elif att_pct >= 5:
                att_item.setForeground(QColor(LC['accent']))
            else:
                att_item.setForeground(QColor(LC['danger']))
            self._band_table.setItem(i, 3, att_item)

        mean_coh = spectrum.get('mean_coherence', 0)
        total_att = spectrum.get('total_attenuation_pct', 0)
        coh_color = LC['success'] if mean_coh >= 0.8 else (LC['accent'] if mean_coh >= 0.5 else LC['danger'])
        self._band_coherence_label.setText(
            f"全频段衰减率: {total_att}% | 平均相干性: {mean_coh:.3f} (≥0.8 可靠, ≥0.5 中等)"
        )
        self._band_coherence_label.setStyleSheet(
            f"font-size: 10px; color: {coh_color}; padding: 4px 8px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )

    def _populate_comprehensive_metrics_results(self, comprehensive: dict, table: QTableWidget = None):
        """填充统计特征表格（算子级输出，非注册考核指标）
        table: 目标表格，默认 self._comp_metrics_table
        """
        if table is None:
            table = self._comp_metrics_table

        table.setRowCount(0)
        exp_metrics = comprehensive.get('experimental', {})
        ctrl_metrics = comprehensive.get('control', {})
        attenuation = comprehensive.get('attenuation', {})

        key_metrics = [
            ('振动剂量值(总)', '振动剂量值', 'VDV_total', 'total'),
            ('振动剂量值(X)', '振动剂量值', 'VDV_X', 'X'),
            ('振动剂量值(Y)', '振动剂量值', 'VDV_Y', 'Y'),
            ('振动剂量值(Z)', '振动剂量值', 'VDV_Z', 'Z'),
            ('RMS加速度(合成)', 'RMS加速度', 'RMS_res', 'total'),
            ('RMS加速度(X)', 'RMS加速度', 'RMS_X', 'X'),
            ('RMS加速度(Y)', 'RMS加速度', 'RMS_Y', 'Y'),
            ('RMS加速度(Z)', 'RMS加速度', 'RMS_Z', 'Z'),
            ('峰值加速度(合成)', '峰值加速度', 'Peak_res', 'total'),
            ('峰值因数(X)', '峰值因数', 'Crest_X', 'X'),
            ('峰值因数(Y)', '峰值因数', 'Crest_Y', 'Y'),
            ('峰值因数(Z)', '峰值因数', 'Crest_Z', 'Z'),
            ('偏度(X)', '偏度', 'Skew_X', 'X'),
            ('偏度(Y)', '偏度', 'Skew_Y', 'Y'),
            ('偏度(Z)', '偏度', 'Skew_Z', 'Z'),
            ('峭度(X)', '峭度', 'Kurt_X', 'X'),
            ('峭度(Y)', '峭度', 'Kurt_Y', 'Y'),
            ('峭度(Z)', '峭度', 'Kurt_Z', 'Z'),
            ('平均绝对值(X)', '平均绝对值', 'MAV_X', 'X'),
            ('平均绝对值(Y)', '平均绝对值', 'MAV_Y', 'Y'),
            ('平均绝对值(Z)', '平均绝对值', 'MAV_Z', 'Z'),
            ('冲击指数(X)', '冲击指数', 'Impulse_X', 'X'),
            ('冲击指数(Y)', '冲击指数', 'Impulse_Y', 'Y'),
            ('冲击指数(Z)', '冲击指数', 'Impulse_Z', 'Z'),
        ]

        table.setRowCount(len(key_metrics))
        for i, (display_name, cn_name, data_key, axis) in enumerate(key_metrics):
            table.setItem(i, 0, QTableWidgetItem(display_name))
            table.setItem(i, 1, QTableWidgetItem(cn_name))
            table.setItem(i, 2, QTableWidgetItem(axis))
            table.setItem(i, 3, QTableWidgetItem(str(exp_metrics.get(data_key, '-'))))
            table.setItem(i, 4, QTableWidgetItem(str(ctrl_metrics.get(data_key, '-'))))
            att_key = f"{data_key}_pct"
            att_val = attenuation.get(att_key, '-')
            att_text = f"{att_val:.1f}%" if isinstance(att_val, (int, float)) else str(att_val)
            table.setItem(i, 5, QTableWidgetItem(att_text))

        # 衰减率摘要
        att_text = (
            f"VDV衰减率: {attenuation.get('VDV_total_pct', '--')}% | "
            f"RMS衰减率: {attenuation.get('RMS_res_pct', '--')}% | "
            f"Peak衰减率: {attenuation.get('Peak_res_pct', '--')}%"
        )
        vdv_att = attenuation.get('VDV_total_pct', 0)
        att_color = LC['success'] if vdv_att >= 20 else (LC['accent'] if vdv_att >= 10 else LC['danger'])
        self._comp_attenuation_label.setText(att_text)
        self._comp_attenuation_label.setStyleSheet(
            f"font-size: 10px; color: {att_color}; padding: 4px 8px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )

    def _on_export_fulltimeseries(self, fmt: str):
        """导出全时域评测结果"""
        ts_result = self._current_timeseries_result
        if not ts_result:
            QMessageBox.warning(self, "提示", "尚无全时域评测结果")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出全时域评测结果", f"full_timeseries_{fmt}.csv",
            "CSV (*.csv);;Markdown (*.md)"
        )
        if not path:
            return

        try:
            if fmt == 'window_csv':
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    normalized = self._normalize_timeseries_data(ts_result.get('results', {}))
                    windows = normalized.get('windows', [])
                    if isinstance(windows, pd.DataFrame):
                        windows = windows.to_dict('records')
                    if windows:
                        w = csv_mod.DictWriter(f, fieldnames=list(windows[0].keys()))
                        w.writeheader()
                        w.writerows(windows)
            QMessageBox.information(self, "成功", f"已导出至 {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _on_browse_dataset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择已解析数据集", "",
            "数据文件 (*.txt *.csv);;SQLite缓存文件 (*.db);;所有文件 (*.*)"
        )
        if file_path:
            self._dataset_path = file_path
            basename = os.path.basename(file_path)
            self._file_label.setText(basename)
            self._file_label.setStyleSheet(
                f"color: {LC['success']}; border: 1px solid {LC['success']}; "
                f"padding: 5px 10px; border-radius: 4px; background: #F0FFF4;"
            )
            self._dataset_badge.setText("数据已加载")
            self._dataset_badge.setStyleSheet(
                f"color: {LC['success']}; font-size: 10px; padding: 2px 10px; "
                f"background: #F0FFF4; border: 1px solid {LC['success']}; border-radius: 10px;"
            )
            self._analyze_btn.setEnabled(True)
            self._empty_guide.setVisible(False)
            self._overview_group.setVisible(False)
            self._profile_group.setVisible(True)
            self._output_tab_widget.setVisible(False)
            self._status_label.setText(f'数据集已加载: {basename}')

    def _update_overview_dashboard(self, report: Dict):
        """
        v4.0: 实验组 vs 对照组对比概览仪表板
        """
        locations = report.get('locations', {})
        loc_count = len(locations)

        # 实验组数据
        ovtv_vals = []
        dom_band_counts = {}
        cf_z_vals = []
        iso_zones = []

        # 对照组数据
        ctrl_ovtv_vals = []
        ctrl_dom_band_counts = {}
        ctrl_cf_z_vals = []
        ctrl_iso_zones = []

        for loc_id, loc_data in locations.items():
            profile = loc_data.get('profile')
            ctrl_profile = loc_data.get('control_profile')
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})

            # ── 优先使用 contrast.magnitude（统一数据源）──
            if isinstance(magnitude, dict):
                ovtv_entry = magnitude.get('OVTV', {})
                if isinstance(ovtv_entry, dict) and 'exp' in ovtv_entry:
                    ovtv_vals.append(ovtv_entry['exp'])
                    if 'ctrl' in ovtv_entry:
                        ctrl_ovtv_vals.append(ovtv_entry['ctrl'])
                cf_entry = magnitude.get('crest_Z', {})
                if isinstance(cf_entry, dict) and 'exp' in cf_entry:
                    cf_z_vals.append(cf_entry['exp'])
                    if 'ctrl' in cf_entry:
                        ctrl_cf_z_vals.append(cf_entry['ctrl'])
            else:
                # Fallback: 从原始 profile 读取
                if isinstance(profile, dict) and not profile.get('error'):
                    mag = profile.get('magnitude') or {}
                    if isinstance(mag, dict):
                        ovtv_vals.append(mag.get('OVTV', 0))
                    impact = profile.get('impact') or {}
                    if isinstance(impact, dict):
                        cf_z_vals.append(impact.get('crest_Z', 0))
                if isinstance(ctrl_profile, dict) and not ctrl_profile.get('error'):
                    mag = ctrl_profile.get('magnitude') or {}
                    if isinstance(mag, dict):
                        ctrl_ovtv_vals.append(mag.get('OVTV', 0))
                    impact = ctrl_profile.get('impact') or {}
                    if isinstance(impact, dict):
                        ctrl_cf_z_vals.append(impact.get('crest_Z', 0))

            # ── 频段和舒适区（仅 profile 有）──
            if isinstance(profile, dict) and not profile.get('error'):
                freq = profile.get('frequency') or {}
                if isinstance(freq, dict):
                    db = freq.get('dominant_band', 'N/A')
                    dom_band_counts[db] = dom_band_counts.get(db, 0) + 1
                iso = profile.get('iso_ref') or {}
                if isinstance(iso, dict):
                    iso_zones.append(iso.get('comfort_zone_cn', 'N/A'))

            if isinstance(ctrl_profile, dict) and not ctrl_profile.get('error'):
                freq = ctrl_profile.get('frequency') or {}
                if isinstance(freq, dict):
                    db = freq.get('dominant_band', 'N/A')
                    ctrl_dom_band_counts[db] = ctrl_dom_band_counts.get(db, 0) + 1
                iso = ctrl_profile.get('iso_ref') or {}
                if isinstance(iso, dict):
                    ctrl_iso_zones.append(iso.get('comfort_zone_cn', 'N/A'))

        has_ctrl = bool(ctrl_ovtv_vals)

        # --- OVTV 实验 vs 对照 ---
        if ovtv_vals:
            avg_ovtv = np.mean(ovtv_vals)
            if has_ctrl:
                avg_ctrl_ovtv = np.mean(ctrl_ovtv_vals)
                delta_pct = (avg_ovtv - avg_ctrl_ovtv) / max(abs(avg_ovtv), abs(avg_ctrl_ovtv), 1e-6) * 100
                delta_color = '#27AE60' if delta_pct < 0 else '#E74C3C'
                self._ov_ovtv._val_label.setText(f"{avg_ovtv:.2f}")
                self._ov_ovtv._sub_label.setText(
                    f"实验组: {avg_ovtv:.2f} g  |  对照组: {avg_ctrl_ovtv:.2f} g  |  Δ {delta_pct:+.1f}%"
                )
                self._ov_ovtv._sub_label.setStyleSheet(
                    f"color: {delta_color}; font-size: 10px; font-weight: 600; background: transparent;"
                )
            else:
                self._ov_ovtv._val_label.setText(f"{avg_ovtv:.2f}")
                self._ov_ovtv._sub_label.setText(f"实验组均值: {avg_ovtv:.2f} g")
                self._ov_ovtv._sub_label.setStyleSheet(
                    f"color: {LC['text_muted']}; font-size: 10px; background: transparent;"
                )
        else:
            self._ov_ovtv._val_label.setText('--')
            self._ov_ovtv._sub_label.setText("无数据")
        self._ov_ovtv._val_label.setStyleSheet(
            f"color: {LC['accent']}; font-size: 22px; font-weight: 700; background: transparent;"
        )

        # --- 主频段 ---
        if dom_band_counts:
            top_band = max(dom_band_counts.items(), key=lambda x: x[1])[0]
            if has_ctrl and ctrl_dom_band_counts:
                ctrl_top = max(ctrl_dom_band_counts.items(), key=lambda x: x[1])[0]
                self._ov_dom_band._val_label.setText(f"{top_band}")
                self._ov_dom_band._sub_label.setText(f"实验组: {top_band}  |  对照组: {ctrl_top}")
                self._ov_dom_band._sub_label.setStyleSheet(
                    f"color: {LC['text_muted']}; font-size: 10px; font-weight: 500; background: transparent;"
                )
            else:
                self._ov_dom_band._val_label.setText(top_band)
                self._ov_dom_band._sub_label.setText(f"实验组: {top_band}")
                self._ov_dom_band._sub_label.setStyleSheet(
                    f"color: {LC['text_muted']}; font-size: 10px; background: transparent;"
                )
        else:
            self._ov_dom_band._val_label.setText('--')
            self._ov_dom_band._sub_label.setText("无数据")
        self._ov_dom_band._val_label.setStyleSheet(
            f"color: {LC['info']}; font-size: 18px; font-weight: 700; background: transparent;"
        )

        # --- 波峰因数 CF ---
        if cf_z_vals:
            avg_cf = np.mean(cf_z_vals)
            if has_ctrl and ctrl_cf_z_vals:
                avg_ctrl_cf = np.mean(ctrl_cf_z_vals)
                delta_cf = (avg_cf - avg_ctrl_cf) / max(abs(avg_cf), abs(avg_ctrl_cf), 1e-6) * 100
                cf_delta_color = '#27AE60' if delta_cf < 0 else '#E74C3C'
                self._ov_cf_z._val_label.setText(f"{avg_cf:.1f}×")
                self._ov_cf_z._sub_label.setText(f"实验组: {avg_cf:.1f}×  |  对照组: {avg_ctrl_cf:.1f}×  |  Δ {delta_cf:+.1f}%")
                self._ov_cf_z._sub_label.setStyleSheet(
                    f"color: {cf_delta_color}; font-size: 10px; font-weight: 600; background: transparent;"
                )
            else:
                self._ov_cf_z._val_label.setText(f"{avg_cf:.1f}×")
                self._ov_cf_z._sub_label.setText("")
        else:
            self._ov_cf_z._val_label.setText('--')
            self._ov_cf_z._sub_label.setText("")
        self._ov_cf_z._val_label.setStyleSheet(
            f"color: {LC['warning']}; font-size: 22px; font-weight: 700; background: transparent;"
        )

        # --- 评测位置数 ---
        self._ov_locations._val_label.setText(str(loc_count))
        if has_ctrl:
            self._ov_locations._sub_label.setText("含对照组")
            self._ov_locations._sub_label.setStyleSheet(
                f"color: #E67E22; font-size: 10px; font-weight: 500; background: transparent;"
            )
        else:
            self._ov_locations._sub_label.setText("")

        # --- 分析时长 ---
        duration = report.get('duration_s', 0)
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 0
        self._ov_duration._val_label.setText(f"{duration:.1f}")

        # --- ISO 舒适区 ---
        if iso_zones:
            iso_counter = Counter(iso_zones)
            top_iso = iso_counter.most_common(1)[0][0]
            if has_ctrl and ctrl_iso_zones:
                ctrl_counter = Counter(ctrl_iso_zones)
                ctrl_top_iso = ctrl_counter.most_common(1)[0][0]
                self._ov_iso._val_label.setText(top_iso)
                self._ov_iso._sub_label.setText(f"实验组: {top_iso}  |  对照组: {ctrl_top_iso}")
                self._ov_iso._sub_label.setStyleSheet(
                    f"color: {LC['text_muted']}; font-size: 10px; font-weight: 500; background: transparent;"
                )
            else:
                self._ov_iso._val_label.setText(top_iso)
                self._ov_iso._sub_label.setText("")
        else:
            self._ov_iso._val_label.setText('--')
            self._ov_iso._sub_label.setText("")
        self._ov_iso._val_label.setStyleSheet(
            f"color: {LC['success']}; font-size: 14px; font-weight: 700; background: transparent;"
        )

        # --- 行为事件 ---
        behavior_summary = report.get('behavior_summary', {})
        total_events = behavior_summary.get('total_events', 0)
        if total_events > 0:
            self._ov_behavior._val_label.setText(f"{total_events} 次")
            self._ov_behavior._val_label.setStyleSheet(
                f"color: {'#E74C3C' if total_events > 5 else '#F39C12'}; font-size: 18px; font-weight: 700; background: transparent;"
            )
        else:
            self._ov_behavior._val_label.setText('--')

    def _on_select_all_metrics(self, state):
        is_checked = state == Qt.Checked
        for cb in self._metric_checkboxes.values():
            cb.setChecked(is_checked)

    def _on_metric_check_changed(self):
        all_checked = all(cb.isChecked() for cb in self._metric_checkboxes.values())
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(all_checked)
        self._select_all_cb.blockSignals(False)

    def _get_selected_metrics(self) -> List[str]:
        return [m_id for m_id, cb in self._metric_checkboxes.items() if cb.isChecked()]

    def _get_selected_locations(self) -> List[str]:
        return [loc_id for loc_id, cb in self._location_checkboxes.items() if cb.isChecked()]

    def _on_start_analysis(self):
        # ── SQLite 缓存模式 ──
        if self._data_source_mode == self.DataSourceMode.SQLITE_CACHE:
            if not self._selected_cache_id:
                QMessageBox.warning(self, "错误", "请先选择一个 SQLite 缓存数据集")
                return
            if not self._cache_registry:
                QMessageBox.warning(self, "错误", "CacheRegistry 未注入")
                return
            entry = self._cache_registry.get_entry(self._selected_cache_id)
            if not entry:
                QMessageBox.warning(self, "错误", "缓存条目不存在")
                return
            self._dataset_path = entry.cache_db_path

        if not self._dataset_path or not os.path.exists(self._dataset_path):
            QMessageBox.warning(self, "错误", "请先选择有效的数据集文件")
            return

        # 全部注册表指标参与计算（不限于页首勾选项），排除全时域统计分组指标
        selected_metrics = [
            k for k, v in self._registry.indicators.items()
            if v.evaluation_dimension != '全时域统计'
        ]
        # ATTEN_H 是后计算跨组指标，注册表中无定义，需显式加入
        if 'ATTEN_H' not in selected_metrics:
            selected_metrics.append('ATTEN_H')
        if not selected_metrics:
            QMessageBox.warning(self, "错误", "请至少选择一个评测指标")
            return

        selected_locations = self._get_selected_locations()
        if not selected_locations:
            QMessageBox.warning(self, "错误", "请至少选择一个评测位置")
            return

        preprocess_level = self._preprocess_combo.currentData()

        self._analyze_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._browse_btn.setEnabled(False)
        self._empty_guide.setVisible(False)
        self._report_preview.clear()
        self._report_preview.setPlaceholderText("分析完成后此处将展示详细报告内容...")
        self._export_json_btn.setEnabled(False)
        self._export_md_btn.setEnabled(False)
        self._export_csv_btn.setEnabled(False)
        self._overview_group.setVisible(False)
        self._profile_group.setVisible(True)
        self._output_tab_widget.setVisible(False)
        self._elapsed_label.setText("")
        self._pipeline_status_label.setText("启动分析...")

        for seg in self._pipeline_segments:
            seg.setStyleSheet("background: #E0E0E0; border-radius: 4px;")
            seg._name_lbl.setStyleSheet("color: #999; font-size: 8px; background: transparent;")
        for i, seg in enumerate(self._pipeline_segments):
            seg._num_lbl.setText(str(i + 1))
            seg._num_lbl.setStyleSheet("color: #999; font-size: 13px; font-weight: 700; background: transparent;")

        self._status_label.setText('分析进行中...')
        self._status_label.setStyleSheet(
            f"color: {LC['accent']}; font-size: 11px; padding: 7px 12px; "
            f"background: {LC['accent_light']}; border: 1px solid {LC['accent']}; border-radius: 6px;"
        )

        self._worker = UnifiedEvaluationWorker(self._engine, DataPreprocessor(), self._report_generator)
        self._selected_metrics = selected_metrics  # 同步到 tab 供指标对照表过滤使用
        self._worker.configure(
            self._dataset_path, preprocess_level,
            selected_metrics, selected_locations,
            eval_mode=self._eval_mode_combo.currentData()
        )

        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.analysis_completed.connect(self._on_analysis_completed)
        self._worker.analysis_failed.connect(self._on_analysis_failed)

        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    def _on_stop_analysis(self):
        if self._worker:
            self._worker.stop()
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        self._stop_btn.setEnabled(True)
        self._reset_ui_state()
        self._status_label.setText('分析已停止')
        self._status_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 11px; padding: 7px 12px; "
            f"background: {LC['bg_card']}; border: 1px solid {LC['border_light']}; border-radius: 6px;"
        )

    def _on_progress_updated(self, value: int, message: str):
        self._update_pipeline_indicator(value)
        self._pipeline_status_label.setText(message)
        self._status_label.setText(f'分析中: {message} [{value}%]')

    def _on_analysis_completed(self, report: Dict):
        self._current_report = report
        for seg in self._pipeline_segments:
            seg.setStyleSheet(
                f"background: {LC['success']}; border-radius: 4px;"
            )
            seg._num_lbl.setText("✓")
            seg._num_lbl.setStyleSheet(
                "color: white; font-size: 13px; font-weight: 700; background: transparent;"
            )
            seg._name_lbl.setStyleSheet(
                "color: rgba(255,255,255,0.9); font-size: 8px; background: transparent;"
            )
        self._pipeline_status_label.setText("分析完成")
        self._populate_results_table(report)
        md_text = self._report_generator.export_to_markdown(report)
        self._report_preview.setMarkdown(md_text)
        self._update_overview_dashboard(report)
        self._populate_profile_visualization(report)
        self._populate_condition_overview(report)
        self._populate_behavior_events(report)

        # ── SQLite 模式: 注入行为事件 ──
        if self._data_source_mode == self.DataSourceMode.SQLITE_CACHE and self._selected_cache_id:
            try:
                behavior_report = self._load_behavior_events_from_sqlite(self._selected_cache_id)
                if behavior_report:
                    self._populate_behavior_events(behavior_report)
                    self.logger.info("SQLite 行为事件已注入到全量统计分析")
            except Exception as e:
                self.logger.warning(f"SQLite 行为事件加载失败: {e}")

        # ── 行程时间轴：从行为事件构建 ──
        behavior_summary = report.get('behavior_summary', {})
        behavior_events = behavior_summary.get('events', [])
        # SQLite 模式: 使用已加载的事件
        if (not behavior_events and
            self._data_source_mode == self.DataSourceMode.SQLITE_CACHE and
            self._behavior_events_for_timeline):
            behavior_events = self._behavior_events_for_timeline
        duration_s = 0.0
        locations = report.get('locations', {})
        for loc_id, loc_data in locations.items():
            ds = loc_data.get('duration_s', 0)
            if ds > duration_s:
                duration_s = ds
        # ── 2. 行程时间轴已清除, 跳过 timeline 数据填充 ──
        # if behavior_events:
        #     self.set_behavior_events_for_timeline(behavior_events, duration_s)

        # ── 自动触发高级图表生成 ──
        self.logger.info(f"[高级图表] _on_analysis_completed 触发, report keys: {list(report.keys())[:10]}")
        self._auto_generate_charts_if_ready(report)
        self._overview_group.setVisible(True)
        self._profile_group.setVisible(True)
        self._output_tab_widget.setVisible(True)

        # ---- 全时域评测结果填充 ----
        full_ts = report.get('_full_timeseries')
        if full_ts and isinstance(full_ts, dict) and (full_ts.get('output_dir') or full_ts.get('results')):
            self._current_timeseries_result = full_ts
            # ── 约束内容宽度 ──
            self._constrain_content_width()
            # 填充表格数据（先归一化数据结构，使评估器和UI字段名对齐）
            normalized = self._normalize_timeseries_data(full_ts.get('results', {}))
            if full_ts.get('results'):
                self._populate_sliding_window_results(normalized.get('windows', []))
                self._populate_statistics_results(normalized.get('statistics', {}))
                self._populate_band_attenuation_results(normalized.get('spectrum', {}))
                # 身体部位中文名映射（供后续所有位置循环使用）
                _body_cn_map = {
                    'Head': '头部', 'head': '头部', '头部眉心': '头部眉心',
                    'Chest': '胸剑突', 'Sternum': '胸剑突', 'sternum': '胸剑突',
                    '胸骨剑突': '胸骨剑突', '躯干T8': '躯干T8',
                    'SeatR': '座垫R点', 'Seat_R': '座垫R点', 'seat_r': '座垫R点', '座垫R点': '座垫R点',
                    'SeatBottom': '座椅底部', 'Seat_Bottom': '座椅底部', 'seat_bottom': '座椅底部', '座椅底部': '座椅底部',
                }
                # 综合指标表格 — 支持嵌套格式（4个位置各一张表）
                comp = normalized.get('comprehensive_metrics', {})
                if comp:
                    # 检测嵌套格式 vs 扁平格式
                    has_exp = isinstance(comp, dict) and 'experimental' in comp
                    is_comp_nested = has_exp or (isinstance(comp, dict) and isinstance(
                        next(iter(comp.values()), None), dict
                    ) and 'experimental' in next(iter(comp.values()), {}))
                    _comp_tables = [
                        self._comp_metrics_table,
                        self._comp_metrics_table_2,
                        self._comp_metrics_table_3,
                        self._comp_metrics_table_4,
                    ]
                    _comp_pos_labels = [
                        None,
                        self._comp_metrics_pos2_label,
                        self._comp_metrics_pos3_label,
                        self._comp_metrics_pos4_label,
                    ]
                    if is_comp_nested and isinstance(comp, dict) and not has_exp:
                        # 嵌套格式: {body_part: {experimental: {...}, ...}}
                        for i, (body_key, body_comp) in enumerate(comp.items()):
                            if i >= len(_comp_tables):
                                break
                            cn = _body_cn_map.get(body_key, body_key)
                            self._populate_comprehensive_metrics_results(body_comp, _comp_tables[i])
                            _comp_tables[i].setVisible(True)
                            if i > 0:
                                _comp_pos_labels[i].setText(f"— {cn} —")
                                _comp_pos_labels[i].setVisible(True)
                        for j in range(len(comp), len(_comp_tables)):
                            _comp_tables[j].setVisible(False)
                            if j > 0:
                                _comp_pos_labels[j].setVisible(False)
                    elif has_exp:
                        # 扁平格式（兼容旧数据）
                        self._populate_comprehensive_metrics_results(comp, _comp_tables[0])
                        _comp_tables[0].setVisible(True)
                        for j in range(1, len(_comp_tables)):
                            _comp_tables[j].setVisible(False)
                            _comp_pos_labels[j].setVisible(False)
                    else:
                        for t in _comp_tables:
                            t.setVisible(False)
                        for l in _comp_pos_labels:
                            if l:
                                l.setVisible(False)
                else:
                    self._comp_metrics_table.setVisible(False)
                    self._comp_metrics_table_2.setVisible(False)
                    self._comp_metrics_table_3.setVisible(False)
                    self._comp_metrics_table_4.setVisible(False)
                    self._comp_metrics_pos2_label.setVisible(False)
                    self._comp_metrics_pos3_label.setVisible(False)
                    self._comp_metrics_pos4_label.setVisible(False)
            # 生成事件概览图（fig2_events）— 头部 + 座垫R点
            overview_data = report.get('_overview_data')
            ts_events = full_ts.get('events', [])
            if overview_data and ts_events:
                adapted_ov = self._adapt_chart_overview_data(overview_data)
                multi_loc = adapted_ov.get('multi_location', {}) if isinstance(adapted_ov, dict) else {}

                # ── 头部事件概览图 ──
                # 优先使用头部通道数据；若 overview_data 实际是座垫R点，则从 multi_location 取 head 数据
                head_loc_label = adapted_ov.get('location_label', '头部')
                head_data = adapted_ov if '头部' in head_loc_label or 'head' in head_loc_label.lower() else multi_loc.get('head', adapted_ov)
                if head_data:
                    head_data['location_label'] = '头部'
                    head_data.setdefault('timestamps', adapted_ov.get('timestamps', []))
                    fig_head = self._generate_events_overview_chart(self._events_overview_head_chart, head_data, ts_events)
                    if fig_head:
                        self._create_chart_canvas(fig_head, self._events_overview_head_chart)
                        self._events_overview_head_chart.setVisible(True)
                    else:
                        self._events_overview_head_chart.setVisible(False)
                else:
                    self._events_overview_head_chart.setVisible(False)

                # ── 座垫R点事件概览图 ──
                seatr_data = multi_loc.get('seat_r')
                if seatr_data:
                    seatr_data = dict(seatr_data)
                    seatr_data['location_label'] = '座垫R点'
                    fig_seatr = self._generate_events_overview_chart(self._events_overview_seatr_chart, seatr_data, ts_events)
                    if fig_seatr:
                        self._create_chart_canvas(fig_seatr, self._events_overview_seatr_chart)
                        self._events_overview_seatr_chart.setVisible(True)
                    else:
                        self._events_overview_seatr_chart.setVisible(False)
                else:
                    self._events_overview_seatr_chart.setVisible(False)
            else:
                self._events_overview_head_chart.setVisible(False)
                self._events_overview_seatr_chart.setVisible(False)
            # 生成频域分析图（fig3_spectrum）— 每个身体部位独立一张 1x3 PSD 图
            spectrum_data = full_ts.get('results', {}).get('spectrum', {})
            _spec_chart_widgets = [
                self._spectrum_overview_chart,
                self._spectrum_overview_chart_2,
                self._spectrum_overview_chart_3,
                self._spectrum_overview_chart_4,
            ]
            if spectrum_data:
                # 检测嵌套格式 vs 扁平格式
                first_val = next(iter(spectrum_data.values()), None)
                is_nested = isinstance(first_val, dict) and not any(
                    k in first_val for k in ['freq', 'exp_psd', 'bands_atten']
                )
                if is_nested:
                    # 嵌套格式: {body_part: {Ax: ..., Ay: ..., Az: ...}}
                    for i, (body_key, body_spec) in enumerate(spectrum_data.items()):
                        if i >= len(_spec_chart_widgets):
                            break
                        cn = _body_cn_map.get(body_key, body_key)
                        adapted = self._adapt_chart_spectrum_data(body_spec)
                        fig = self._generate_spectrum_overview_chart(
                            _spec_chart_widgets[i], adapted, f' — {cn}'
                        )
                        if fig:
                            self._create_chart_canvas(fig, _spec_chart_widgets[i])
                            _spec_chart_widgets[i].setVisible(True)
                        else:
                            _spec_chart_widgets[i].setVisible(False)
                else:
                    # 扁平格式: 兼容旧数据
                    adapted_spec = self._adapt_chart_spectrum_data(spectrum_data)
                    fig = self._generate_spectrum_overview_chart(self._spectrum_overview_chart, adapted_spec)
                    if fig:
                        self._create_chart_canvas(fig, self._spectrum_overview_chart)
                        self._spectrum_overview_chart.setVisible(True)
                    else:
                        self._spectrum_overview_chart.setVisible(False)
                # 隐藏未使用的图容器
                for j in range(len(spectrum_data) if is_nested else 1, len(_spec_chart_widgets)):
                    _spec_chart_widgets[j].setVisible(False)
            else:
                for w in _spec_chart_widgets:
                    w.setVisible(False)
            # 生成 STFT 时频图（fig4_stft）
            stft_data = full_ts.get('results', {}).get('stft', {})
            if stft_data:
                adapted_stft = self._adapt_chart_stft_data(stft_data)
                fig = self._generate_stft_overview_chart(self._stft_overview_chart, adapted_stft)
                if fig:
                    self._create_chart_canvas(fig, self._stft_overview_chart)
                else:
                    self._stft_overview_chart.setVisible(False)
            else:
                self._stft_overview_chart.setVisible(False)
            # 生成统计分布与箱线图（fig5_statistics）
            if overview_data:
                adapted_ov5 = self._adapt_chart_overview_data(overview_data)
                fig = self._generate_statistics_distribution_chart(self._stats_distribution_chart, adapted_ov5)
                if fig:
                    self._create_chart_canvas(fig, self._stats_distribution_chart)
                else:
                    self._stats_distribution_chart.setVisible(False)
            else:
                self._stats_distribution_chart.setVisible(False)
            # 生成全频段衰减雷达图（fig6_band_radar）
            if spectrum_data:
                # 嵌套格式取第一个位置数据用于雷达图
                first_val = next(iter(spectrum_data.values()), None)
                is_nested = isinstance(first_val, dict) and not any(
                    k in first_val for k in ['freq', 'exp_psd', 'bands_atten']
                )
                spec_for_radar = spectrum_data[list(spectrum_data.keys())[0]] if is_nested else spectrum_data
                adapted_spec6 = self._adapt_chart_spectrum_data(spec_for_radar)
                fig = self._generate_band_radar_chart(self._band_radar_chart, adapted_spec6)
                if fig:
                    self._create_chart_canvas(fig, self._band_radar_chart)
                else:
                    self._band_radar_chart.setVisible(False)
            else:
                self._band_radar_chart.setVisible(False)
            # 生成统计特征(算子级输出)图表（fig8_stat_features）— 每个身体部位独立一张
            metrics_data = full_ts.get('results', {}).get('metrics', {})
            _stat_chart_widgets = [
                self._stat_features_chart,
                self._stat_features_chart_2,
                self._stat_features_chart_3,
                self._stat_features_chart_4,
            ]
            if metrics_data:
                # 检测嵌套格式 vs 扁平格式
                first_mv = next(iter(metrics_data.values()), None)
                is_metrics_nested = isinstance(first_mv, dict) and any(
                    k.startswith(('exp_', 'ctrl_')) for k in (first_mv or {}).keys()
                )
                if is_metrics_nested:
                    for i, (body_key, body_metrics) in enumerate(metrics_data.items()):
                        if i >= len(_stat_chart_widgets):
                            break
                        cn = _body_cn_map.get(body_key, body_key)
                        fig = self._generate_stat_features_chart(
                            _stat_chart_widgets[i], body_metrics, cn
                        )
                        if fig:
                            self._create_chart_canvas(fig, _stat_chart_widgets[i])
                            _stat_chart_widgets[i].setVisible(True)
                        else:
                            _stat_chart_widgets[i].setVisible(False)
                    for j in range(len(metrics_data), len(_stat_chart_widgets)):
                        _stat_chart_widgets[j].setVisible(False)
                else:
                    # 扁平格式（兼容旧数据）
                    fig = self._generate_stat_features_chart(
                        _stat_chart_widgets[0], metrics_data
                    )
                    if fig:
                        self._create_chart_canvas(fig, _stat_chart_widgets[0])
                        _stat_chart_widgets[0].setVisible(True)
                    else:
                        _stat_chart_widgets[0].setVisible(False)
                    for j in range(1, len(_stat_chart_widgets)):
                        _stat_chart_widgets[j].setVisible(False)
            else:
                for w in _stat_chart_widgets:
                    w.setVisible(False)
            self._fulltimeseries_group.setVisible(True)
            self._statistics_group.setVisible(True)
            self._spectrum_group.setVisible(True)
            self._export_window_csv_btn.setEnabled(True)
        else:
            # 即使无 full_timeseries 结果，也保持这些分组可见，让用户知道存在这些分析区域
            self._fulltimeseries_group.setVisible(True)
            self._statistics_group.setVisible(True)
            self._spectrum_group.setVisible(True)
            self._export_window_csv_btn.setEnabled(False)

        self._reset_ui_state()
        duration = report.get("duration_s", 0)
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 0
        self._elapsed_label.setText(f"耗时: {duration:.1f}s")
        dataset_name = report.get("dataset_name", "")
        self._status_label.setText(
            f'分析完成 | 数据: {dataset_name} | 耗时: {duration:.1f}s'
        )
        self._status_label.setStyleSheet(
            f"color: {LC['success']}; font-size: 11px; padding: 7px 12px; "
            f"background: #F0FFF4; border: 1px solid {LC['success']}; border-radius: 6px;"
        )

        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(1000)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        self._worker_thread = None

    def _on_analysis_failed(self, error_msg: str):
        QMessageBox.critical(self, "分析失败", error_msg)
        self._reset_ui_state()
        self._status_label.setText(f'分析失败: {error_msg}')
        self._status_label.setStyleSheet(
            f"color: {LC['danger']}; font-size: 11px; padding: 7px 12px; "
            f"background: #FDEDEC; border: 1px solid {LC['danger']}; border-radius: 6px;"
        )
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(1000)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        self._worker_thread = None

    def _reset_ui_state(self):
        self._analyze_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._browse_btn.setEnabled(True)
        self._export_json_btn.setEnabled(True)
        self._export_md_btn.setEnabled(True)
        self._export_csv_btn.setEnabled(True)

    def _populate_results_table(self, report: Dict):
        self._current_report = report
        self._results_loc_filter.blockSignals(True)
        self._results_loc_filter.setCurrentIndex(0)
        self._results_loc_filter.blockSignals(False)
        self._do_populate_results_table()

    def _do_populate_results_table(self):
        """统一指标统计结果表（13列合并版）
        
        数据源: contrast.magnitude 优先 → fallback metrics/control_metrics
        公式:   delta = (exp - ctrl) / max(abs(exp), abs(ctrl), 1e-6) * 100
        行结构: 每个指标 × 每个位置 = 一行
        """
        report = self._current_report
        if not report:
            return

        locations = report.get('locations', {})
        selected_loc = self._results_loc_filter.currentData()

        # ── 辅助: 统一 delta 公式 ──
        def _calc_delta(e_val, c_val):
            if e_val is None or c_val is None:
                return None
            try:
                ev, cv = float(e_val), float(c_val)
                denom = max(abs(ev), abs(cv), 1e-6)
                return (ev - cv) / denom * 100
            except (ValueError, TypeError):
                return None

        # ── 辅助: 提取数值 ──
        def _extract_val(raw):
            if isinstance(raw, dict):
                return raw.get('value')
            if isinstance(raw, (int, float)):
                return raw
            return None

        # 收集所有 (位置, 指标ID) 行
        all_rows = []
        for loc_id, loc_data in locations.items():
            if not isinstance(loc_data, dict):
                continue
            if selected_loc not in ('all', loc_id):
                continue

            label_cn = loc_data.get('label_cn', loc_id)
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
            fallback_exp = loc_data.get('metrics') or {}
            fallback_ctrl = loc_data.get('control_metrics') or {}

            # 收集指标键
            all_keys = set()
            if isinstance(magnitude, dict):
                all_keys.update(magnitude.keys())
            all_keys.update(k for k in fallback_exp if not k.endswith('_status') and not k.endswith('_error'))
            all_keys.update(k for k in fallback_ctrl if not k.endswith('_status') and not k.endswith('_error'))

            for metric_id in sorted(all_keys):
                meta = self._registry.get_indicator_meta(metric_id)
                if meta and meta.evaluation_dimension == '全时域统计':
                    continue

                # 数据源: contrast.magnitude 优先
                mag_entry = magnitude.get(metric_id) if isinstance(magnitude, dict) else None
                if isinstance(mag_entry, dict):
                    exp_val = mag_entry.get('experimental', mag_entry.get('exp'))
                    ctrl_val = mag_entry.get('control', mag_entry.get('ctrl'))
                    delta_pct = mag_entry.get('delta_pct')
                else:
                    exp_val = _extract_val(fallback_exp.get(metric_id))
                    ctrl_val = _extract_val(fallback_ctrl.get(metric_id))
                    delta_pct = _calc_delta(exp_val, ctrl_val)

                if exp_val is None and ctrl_val is None:
                    continue

                # 维度
                raw_dim = meta.evaluation_dimension if meta else '通用-基础'
                dim = DIMENSION_MAP.get(raw_dim, '通用-基础')
                dim_order = DIMENSION_ORDER.get(dim, 99)

                # 状态 (基于实验组值 vs 阈值)
                threshold = self._registry.get_threshold(metric_id)
                status_text = '-'
                status_color = LC['text_muted']
                if exp_val is not None and isinstance(exp_val, (int, float)):
                    pass_thr = meta.threshold_pass if meta else (threshold.get('pass') if threshold else None)
                    if pass_thr is not None:
                        try:
                            pass_v = float(pass_thr)
                            direction = meta.direction.name if meta else 'LOWER_IS_BETTER'
                            if direction in ('LOWER_IS_BETTER', 'LOWER_BETTER'):
                                if exp_val <= pass_v:
                                    status_text = '✓ 通过'; status_color = '#27AE60'
                                else:
                                    status_text = '✗ 超标'; status_color = '#E74C3C'
                            else:
                                if exp_val >= pass_v:
                                    status_text = '✓ 通过'; status_color = '#27AE60'
                                else:
                                    status_text = '✗ 超标'; status_color = '#E74C3C'
                        except (TypeError, ValueError):
                            pass

                # 评级 (基于 delta_pct)
                grade = '-'
                grade_color = LC['text_muted']
                if delta_pct is not None:
                    delta = float(delta_pct)
                    direction = meta.direction.name if meta else 'LOWER_BETTER'
                    if direction in ('HIGHER_BETTER',):
                        if delta >= 35:
                            grade = '优秀'; grade_color = '#27AE60'
                        elif delta >= 20:
                            grade = '良好'; grade_color = '#4A90D9'
                        elif delta >= 0:
                            grade = '一般'; grade_color = '#F39C12'
                        else:
                            grade = '退步'; grade_color = '#E74C3C'
                    else:
                        if delta <= -35:
                            grade = '优秀'; grade_color = '#27AE60'
                        elif delta <= -20:
                            grade = '良好'; grade_color = '#4A90D9'
                        elif delta <= 0:
                            grade = '一般'; grade_color = '#F39C12'
                        else:
                            grade = '退步'; grade_color = '#E74C3C'

                # 改进方向
                dir_text = '--'
                dir_color = LC['text_muted']
                if delta_pct is not None:
                    delta = float(delta_pct)
                    lower_better = meta.direction.name in ('LOWER_IS_BETTER', 'LOWER_BETTER') if meta else True
                    if (delta < 0 and lower_better) or (delta > 0 and not lower_better):
                        dir_text = '↓改善'; dir_color = '#27AE60'
                    else:
                        dir_text = '↑退步'; dir_color = '#E74C3C'

                all_rows.append({
                    'loc_id': loc_id, 'label_cn': label_cn,
                    'metric_id': metric_id, 'dim': dim, 'dim_order': dim_order,
                    'exp_val': exp_val, 'ctrl_val': ctrl_val,
                    'delta_pct': delta_pct,
                    'status_text': status_text, 'status_color': status_color,
                    'grade': grade, 'grade_color': grade_color,
                    'dir_text': dir_text, 'dir_color': dir_color,
                })

        # 排序
        all_rows.sort(key=lambda r: (r['dim_order'], r['metric_id'], r['loc_id']))

        self._results_table.setRowCount(len(all_rows))
        self._results_row_map = {}

        for row, data in enumerate(all_rows):
            metric_id = data['metric_id']
            meta = self._registry.get_indicator_meta(metric_id)
            threshold = self._registry.get_threshold(metric_id)

            # 0: 指标ID
            code_item = QTableWidgetItem(metric_id)
            code_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 0, code_item)

            # 1: 指标名称
            name_text = meta.display_name_cn if meta else metric_id
            name_item = QTableWidgetItem(name_text)
            name_item.setTextAlignment(Qt.AlignCenter)
            if meta:
                tip_lines = [
                    f"{meta.display_name_cn} ({meta.display_name_en})",
                    f"单位: {meta.unit}",
                    f"公式: {meta.formula_text}",
                    f"管线: {' → '.join(meta.operator_pipeline)}",
                ]
                if meta.standard_refs:
                    tip_lines.append(f"标准: {', '.join([str(r) for r in meta.standard_refs[:3]])}")
                if meta.threshold_pass:
                    tip_lines.append(f"通过阈值: {meta.threshold_pass}")
                name_item.setToolTip('\n'.join(tip_lines))
            self._results_table.setItem(row, 1, name_item)

            # 2: 评测维度
            dim_item = QTableWidgetItem(data['dim'])
            dim_item.setTextAlignment(Qt.AlignCenter)
            dim_color = DIM_COLORS.get(data['dim'], '#95A5A6')
            dim_item.setForeground(QColor(dim_color))
            self._results_table.setItem(row, 2, dim_item)

            # 3: 单位
            unit_text = meta.unit if meta and meta.unit != '-' else ''
            unit_item = QTableWidgetItem(unit_text)
            unit_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 3, unit_item)

            # 4: 位置
            loc_item = QTableWidgetItem(data['label_cn'])
            loc_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 4, loc_item)

            # 5: 实验组
            exp_val = data['exp_val']
            if exp_val is not None and isinstance(exp_val, (int, float)):
                exp_item = QTableWidgetItem(f"{exp_val:.4f}")
            else:
                exp_item = QTableWidgetItem("--")
                exp_item.setForeground(QColor('#CCC'))
            exp_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 5, exp_item)

            # 6: 对照组
            ctrl_val = data['ctrl_val']
            if ctrl_val is not None and isinstance(ctrl_val, (int, float)):
                ctrl_item = QTableWidgetItem(f"{ctrl_val:.4f}")
            else:
                ctrl_item = QTableWidgetItem("--")
                ctrl_item.setForeground(QColor('#CCC'))
            ctrl_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 6, ctrl_item)

            # 7: 绝对差
            if exp_val is not None and ctrl_val is not None and isinstance(exp_val, (int, float)) and isinstance(ctrl_val, (int, float)):
                diff_val = exp_val - ctrl_val
                diff_item = QTableWidgetItem(f"{diff_val:+.4f}")
            else:
                diff_item = QTableWidgetItem("--")
                diff_item.setForeground(QColor('#CCC'))
            diff_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 7, diff_item)

            # 8: 变化率(%)
            delta_pct = data['delta_pct']
            if delta_pct is not None:
                pct_item = QTableWidgetItem(f"{delta_pct:+.1f}%")
                lower_better = meta.direction.name in ('LOWER_IS_BETTER', 'LOWER_BETTER') if meta else True
                is_better = delta_pct < 0 if lower_better else delta_pct > 0
                pct_item.setForeground(QColor('#27AE60') if is_better else QColor('#E74C3C'))
            else:
                pct_item = QTableWidgetItem("--")
                pct_item.setForeground(QColor('#CCC'))
            pct_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 8, pct_item)

            # 9: 状态
            status_item = QTableWidgetItem(data['status_text'])
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor(data['status_color']))
            font = QFont("Microsoft YaHei", 10)
            font.setBold(data['status_text'].startswith('✗'))
            status_item.setFont(font)
            self._results_table.setItem(row, 9, status_item)

            # 10: 评级
            grade_item = QTableWidgetItem(data['grade'])
            grade_item.setTextAlignment(Qt.AlignCenter)
            grade_item.setForeground(QColor(data['grade_color']))
            self._results_table.setItem(row, 10, grade_item)

            # 11: 改进方向
            dir_item = QTableWidgetItem(data['dir_text'])
            dir_item.setTextAlignment(Qt.AlignCenter)
            dir_item.setForeground(QColor(data['dir_color']))
            self._results_table.setItem(row, 11, dir_item)

            # 12: 通过阈值
            threshold_text = ''
            if meta and meta.threshold_pass:
                threshold_text = meta.threshold_pass
            elif threshold and threshold.get('pass') is not None:
                threshold_text = str(threshold.get('pass'))
            thr_item = QTableWidgetItem(threshold_text if threshold_text else '-')
            thr_item.setTextAlignment(Qt.AlignCenter)
            if not threshold_text:
                thr_item.setForeground(QColor('#CCC'))
            self._results_table.setItem(row, 12, thr_item)

            self._results_row_map[row] = metric_id

        self._results_loc_count.setText(f"{len(all_rows)} 条记录")

    def _on_export(self, fmt: str):
        if not self._current_report:
            QMessageBox.warning(self, "警告", "没有可导出的报告")
            return

        file_filter = "JSON (*.json)" if fmt == 'json' else \
                      "Markdown (*.md)" if fmt == 'md' else "CSV (*.csv)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, f"导出{fmt.upper()}报告", "", file_filter
        )

        if not file_path:
            return

        try:
            if fmt == 'json':
                content = self._report_generator.export_to_json(self._current_report)
            elif fmt == 'md':
                content = self._report_generator.export_to_markdown(self._current_report)
            else:
                content = self._report_generator.export_to_csv(self._current_report)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            QMessageBox.information(self, "导出成功", f"报告已导出到:\n{file_path}")
            self._status_label.setText(f'报告已导出: {os.path.basename(file_path)}')

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def set_trip_summary(self, trip_summary):
        self._trip_summary = trip_summary
        # _update_timeline() 已移除 — 2.行程时间轴已清除

    def set_behavior_events_for_timeline(self, events: list, duration_s: float = 0):
        """从报告行为事件构建时间轴数据（替代 TripSummary）"""
        self._behavior_events_for_timeline = events
        self._total_duration_s = max(duration_s, 1)
        self._update_timeline()

    def set_type_labels(self, labels: Dict[str, str]):
        self._type_labels = labels

    # ── CacheRegistry 注入 ──

    def set_cache_registry(self, registry):
        """注入 CacheRegistry（由 right_content_panel 调用）"""
        self._cache_registry = registry
        self._refresh_cache_selector()
        self.logger.info(f"CacheRegistry 已注入到全量统计分析页: {registry.count if registry else 0} 个缓存")

    def _refresh_cache_selector(self):
        """刷新 SQLite 缓存选择器下拉列表"""
        if not hasattr(self, '_cache_combo') or self._cache_combo is None:
            return
        self._cache_combo.blockSignals(True)
        self._cache_combo.clear()
        self._cache_entries = {}
        if self._cache_registry:
            entries = self._cache_registry.list_caches()
            for entry in entries:
                self._cache_entries[self._cache_combo.count()] = entry
                self._cache_combo.addItem(entry.display_label)
            if entries:
                self._cache_combo.setCurrentIndex(0)
                self._selected_cache_id = entries[0].id
                self._update_time_range_from_entry(entries[0])
                self._cache_combo.setEnabled(True)
                self._analyze_btn.setEnabled(True)
            else:
                self._cache_combo.addItem('(无可用缓存)')
                self._cache_combo.setEnabled(False)
                self._analyze_btn.setEnabled(False)
        else:
            self._cache_combo.addItem('(未注入CacheRegistry)')
            self._cache_combo.setEnabled(False)
        self._cache_combo.blockSignals(False)

    def _update_time_range_from_entry(self, entry):
        """根据缓存条目更新时间范围控件"""
        if hasattr(self, '_t_min_spin') and hasattr(self, '_t_max_spin'):
            t_min, t_max = entry.time_range
            if t_max > t_min:
                self._t_min_spin.blockSignals(True)
                self._t_max_spin.blockSignals(True)
                self._t_min_spin.setRange(t_min, t_max)
                self._t_max_spin.setRange(t_min, t_max)
                self._t_min_spin.setValue(t_min)
                self._t_max_spin.setValue(t_max)
                self._time_range = (t_min, t_max)
                self._t_min_spin.blockSignals(False)
                self._t_max_spin.blockSignals(False)

    def _on_cache_selected(self, index: int):
        """缓存选择器变更回调"""
        entry = self._cache_entries.get(index) if hasattr(self, '_cache_entries') else None
        if entry:
            self._selected_cache_id = entry.id
            self._update_time_range_from_entry(entry)
            self._dataset_badge.setText(f"SQLite: {entry.record_count}条")
            self._dataset_badge.setStyleSheet(
                f"color: {LC['success']}; font-size: 10px; padding: 2px 10px; "
                f"background: #F0FFF4; border: 1px solid {LC['success']}; border-radius: 10px;"
            )
            self._analyze_btn.setEnabled(True)
            self._empty_guide.setVisible(False)

    def _on_full_range(self):
        """重置为全量时间范围"""
        if hasattr(self, '_cache_entries') and self._cache_combo.currentIndex() in self._cache_entries:
            entry = self._cache_entries[self._cache_combo.currentIndex()]
            self._update_time_range_from_entry(entry)

    def _set_sqlite_row_visible(self, visible: bool):
        """控制 SQLite 缓存选择行及离线文件行的可见性"""
        for w in getattr(self, '_sqlite_widgets', []):
            if isinstance(w, QHBoxLayout):
                for i in range(w.count()):
                    wi = w.itemAt(i)
                    if wi and wi.widget():
                        wi.widget().setVisible(visible)
            elif hasattr(w, 'setVisible'):
                w.setVisible(visible)

        # 控制离线文件行（row2）可见性
        if hasattr(self, '_browse_btn'):
            row2_visible = not visible
            if hasattr(self, '_file_label'):
                self._file_label.setVisible(row2_visible)
            self._browse_btn.setVisible(row2_visible)

    def _on_source_mode_changed(self, index: int):
        """数据源模式切换回调"""
        mode_value = self._source_mode_combo.currentData()
        if mode_value == self.DataSourceMode.SQLITE_CACHE.value:
            self._data_source_mode = self.DataSourceMode.SQLITE_CACHE
            self._set_sqlite_row_visible(True)
            self._dataset_badge.setText("SQLite 缓存模式")
            self._dataset_badge.setStyleSheet(
                f"color: {LC['success']}; font-size: 10px; padding: 2px 10px; "
                f"background: #F0FFF4; border: 1px solid {LC['success']}; border-radius: 10px;"
            )
            self._refresh_cache_selector()
        else:
            self._data_source_mode = self.DataSourceMode.OFFLINE_FILE
            self._set_sqlite_row_visible(False)
            self._dataset_badge.setText("离线文件模式")
            self._dataset_badge.setStyleSheet(
                f"color: {LC['warning']}; font-size: 10px; padding: 2px 10px; "
                f"background: #FFF9DB; border: 1px solid {LC['warning']}; border-radius: 10px;"
            )
            self._analyze_btn.setEnabled(False)

    def _on_time_range_changed(self, value):
        """时间范围变更回调"""
        if hasattr(self, '_t_min_spin') and hasattr(self, '_t_max_spin'):
            t_min = self._t_min_spin.value()
            t_max = self._t_max_spin.value()
            if t_min < t_max:
                self._time_range = (t_min, t_max)

    def set_event_manager(self, event_manager):
        """设置共享事件管理器（统一事件源）"""
        self._event_manager = event_manager

    # ── 高级图表生成 ──

    def _auto_generate_charts_if_ready(self, report: Dict):
        """分析完成后自动触发高级图表生成（延迟执行确保UI先渲染）"""
        self._charts_pending_report = report
        self.logger.info("[高级图表] _auto_generate_charts_if_ready, 800ms 后执行")
        QTimer.singleShot(800, self._generate_advanced_charts_from_pending)

    def _generate_advanced_charts_from_pending(self):
        """从待处理报告生成图表"""
        self.logger.info("[高级图表] _generate_advanced_charts_from_pending 触发")
        report = getattr(self, '_charts_pending_report', None)
        if report:
            self._generate_advanced_charts(report)
        else:
            self.logger.warning("[高级图表] _charts_pending_report 为空!")

    def _make_advanced_figsize(self, card_widget, default_w: float = 12, default_h: float = 5):
        """根据卡片实际宽度动态计算高级图表的 figsize，与 card_adapted_figure 对齐。

        统一使用 card_adapted_figure 的宽度获取逻辑, 确保所有 Canvas 图表尺寸一致。
        """
        from .visualization_manager import ChartStyle as _CS
        if not card_widget.isVisible():
            card_widget.show()
        QApplication.processEvents()
        card_widget.updateGeometry()
        QApplication.processEvents()
        parent = card_widget.parent()
        if isinstance(parent, QScrollArea):
            card_px = parent.viewport().width()
        elif hasattr(card_widget, 'contentsRect'):
            card_px = card_widget.contentsRect().width()
        else:
            card_px = card_widget.width()
        if card_px < 200:
            p = card_widget.parent()
            depth = 0
            while p and depth < 5:
                if hasattr(p, 'viewport'):
                    card_px = p.viewport().width()
                    break
                card_px = p.width()
                if card_px >= 400:
                    break
                p = p.parent()
                depth += 1
            if card_px < 200:
                top = card_widget.window()
                card_px = max(400, int(top.width() * 0.65)) if top else 1200
        dpi = _CS.screen_dpi()
        usable_px = max(400, card_px - 60)
        w_inch = usable_px / dpi
        scale = w_inch / _CS.CARD_W
        scale_clamped = max(0.5, min(1.5, scale))
        h_inch = _CS.ROW_H * (default_h / default_w) * scale_clamped
        return (w_inch, h_inch)

    def _generate_advanced_charts(self, report: Dict):
        """生成全部高级图表，嵌入到各自的卡片容器中"""
        overview = report.get('_overview_data', {})
        channel_data_map = report.get('_channel_data_map', {})
        events = report.get('behavior_summary', {}).get('events', []) or \
                 getattr(self, '_behavior_events_for_timeline', [])

        self.logger.info(f"开始生成高级图表: channel_map={len(channel_data_map)} keys, "
                        f"locations={len(report.get('locations', {}))}")
        if channel_data_map:
            self.logger.info(f"[PSD调试] channel_map keys: {list(channel_data_map.keys())[:10]}")

        charts_generated = 0

        # ── 图表1: 事件时间线 → 已整合到 2.行程时间轴, 跳过 ──

        # ── 图表2: PSD 功率谱对比 → 头部 / 座垫R点 / 座椅底部 ──
        def _find_psd_imu_pair(keyword: str, cn_name: str):
            """在 channel_data_map 中查找指定身体部位的实验组/对照组 IMU 对"""
            exp = next((k for k in channel_data_map if keyword in k and k.endswith('-1')), None)
            ctrl = next((k for k in channel_data_map if keyword in k and k.endswith('-2')), None)
            if not exp or not ctrl:
                # 备选: IMU编号奇偶分组
                imu_pairs = [[], []]
                for name in channel_data_map.keys():
                    if name.startswith('_'):
                        continue
                    try:
                        imu_num = int(name.split('_')[0].replace('IMU', ''))
                        imu_pairs[0 if imu_num % 2 == 1 else 1].append(name)
                    except (ValueError, IndexError):
                        continue
                exp = next((k for k in imu_pairs[0] if keyword in k), imu_pairs[0][0] if imu_pairs[0] else None)
                ctrl = next((k for k in imu_pairs[1] if keyword in k), imu_pairs[1][0] if imu_pairs[1] else None)
            return exp, ctrl, cn_name

        psd_positions = [
            ('头部', '头部眉心', self._advanced_psd_container),
            ('座垫', '座垫R点', self._advanced_psd_container_seatr),
            ('座椅底部', '座椅底部', self._advanced_psd_container_seatbottom),
        ]
        for keyword, cn_name, container in psd_positions:
            exp_imu, ctrl_imu, loc_name = _find_psd_imu_pair(keyword, cn_name)
            if exp_imu and ctrl_imu:
                try:
                    fig = create_psd_comparison(channel_data_map, [exp_imu], [ctrl_imu],
                                               axis='all')
                    if fig:
                        self._create_chart_canvas(fig, container)
                        container.setVisible(True)
                        self._advanced_psd_card.setVisible(True)
                        charts_generated += 1
                except Exception as e:
                    self.logger.warning(f"PSD图表生成失败 ({loc_name}): {e}")
            else:
                self.logger.info(f"PSD: 未找到 {cn_name} 的 IMU 对，跳过")

        # ── 图表3: 衰减效率柱状图 → _advanced_attenuation_container ──
        # ── 图表4: 雷达对比图 → _advanced_radar_container ──
        comparison = self._build_comparison_dict(report)
        self.logger.info(f"[衰减图调试] _build_comparison_dict 返回 {len(comparison)} 条数据")
        if comparison:
            self.logger.info(f"[衰减图调试] comparison keys: {list(comparison.keys())[:10]}")

        atten_generated = False
        if comparison:
            try:
                fig = create_attenuation_bar(comparison, figsize=(10, 5.5))
                self.logger.info(f"[衰减图调试] create_attenuation_bar 返回: {fig is not None}")
                if fig:
                    self._create_chart_canvas(fig, self._advanced_attenuation_container)
                    self._advanced_attenuation_container.setVisible(True)
                    atten_generated = True
                    charts_generated += 1
            except Exception as e:
                self.logger.warning(f"衰减柱状图生成失败: {e}", exc_info=True)

            try:
                fig = create_comparison_radar(comparison, figsize=(7, 7))
                if fig:
                    self._create_chart_canvas(fig, self._advanced_radar_container)
                    self._advanced_radar_container.setVisible(True)
                    self._advanced_radar_card.setVisible(True)
                    charts_generated += 1
            except Exception as e:
                self.logger.warning(f"雷达图生成失败: {e}")

        # ── 图表5: SRS 冲击响应谱 → 头部 / 胸剑突 / 座垫R点 ──
        def _find_imu_pair(keyword: str, cn_name: str):
            """在 channel_data_map 中查找指定身体部位的实验组/对照组 IMU 对"""
            exp = next((k for k in channel_data_map if keyword in k and k.endswith('-1')), None)
            ctrl = next((k for k in channel_data_map if keyword in k and k.endswith('-2')), None)
            if not exp or not ctrl:
                # 备选: IMU编号奇偶分组
                imu_pairs = [[], []]
                for name in channel_data_map.keys():
                    if name.startswith('_'):
                        continue
                    try:
                        imu_num = int(name.split('_')[0].replace('IMU', ''))
                        imu_pairs[0 if imu_num % 2 == 1 else 1].append(name)
                    except (ValueError, IndexError):
                        continue
                exp = next((k for k in imu_pairs[0] if keyword in k), imu_pairs[0][0] if imu_pairs[0] else None)
                ctrl = next((k for k in imu_pairs[1] if keyword in k), imu_pairs[1][0] if imu_pairs[1] else None)
            if not exp or not ctrl:
                exp = next((k for k in channel_data_map if k.endswith('-1') and keyword in k), None)
                ctrl = next((k for k in channel_data_map if k.endswith('-2') and keyword in k), None)
            return exp, ctrl, cn_name

        srs_positions = [
            ('头部', '头部眉心', self._advanced_srs_container),
            ('胸', '胸剑突', self._advanced_srs_container_chest),
            ('座垫', '座垫R点', self._advanced_srs_container_seatr),
        ]
        for keyword, cn_name, container in srs_positions:
            exp_imu, ctrl_imu, loc_name = _find_imu_pair(keyword, cn_name)
            if exp_imu and ctrl_imu:
                try:
                    fig = create_srs_comparison(channel_data_map, exp_imu, ctrl_imu,
                                               location_name=loc_name, axis='all', figsize=(16, 5))
                    if fig:
                        self._create_chart_canvas(fig, container)
                        container.setVisible(True)
                        self._advanced_srs_card.setVisible(True)
                        charts_generated += 1
                except Exception as e:
                    self.logger.warning(f"SRS图表生成失败 ({loc_name}): {e}")
            else:
                self.logger.info(f"SRS: 未找到 {cn_name} 的 IMU 对，跳过")

        if charts_generated > 0:
            self.logger.info(f"高级可视化图表生成完成: {charts_generated} 张")
        else:
            self.logger.warning("当前数据不支持生成高级可视化图表")

        # 确保所有高级图表卡片始终可见（即使无数据也显示占位）
        for card_key in ['psd', 'attenuation', 'radar', 'accel', 'srs']:
            card = getattr(self, f'_advanced_{card_key}_card', None)
            container = getattr(self, f'_advanced_{card_key}_container', None)
            if card and container:
                card.setVisible(True)
                # 如果容器内没有widget（图表未生成），添加占位标签
                if container.layout().count() == 0:
                    from PySide6.QtWidgets import QLabel as _QL
                    no_data_label = _QL("暂无数据 — 请检查实验组/对照组通道数据")
                    no_data_label.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 12px;")
                    no_data_label.setAlignment(Qt.AlignCenter)
                    container.layout().addWidget(no_data_label)
                container.setVisible(True)

        # SRS 多位置容器: 胸剑突和座垫R点
        for extra_key in ['_advanced_srs_container_chest', '_advanced_srs_container_seatr']:
            extra_container = getattr(self, extra_key, None)
            if extra_container:
                if extra_container.layout().count() == 0:
                    from PySide6.QtWidgets import QLabel as _QL
                    no_data_label = _QL("暂无数据 — 请检查实验组/对照组通道数据")
                    no_data_label.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 12px;")
                    no_data_label.setAlignment(Qt.AlignCenter)
                    extra_container.layout().addWidget(no_data_label)
                extra_container.setVisible(True)

        # PSD 多位置容器: 座垫R点和座椅底部
        for extra_key in ['_advanced_psd_container_seatr', '_advanced_psd_container_seatbottom']:
            extra_container = getattr(self, extra_key, None)
            if extra_container:
                if extra_container.layout().count() == 0:
                    from PySide6.QtWidgets import QLabel as _QL
                    no_data_label = _QL("暂无数据 — 请检查实验组/对照组通道数据")
                    no_data_label.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 12px;")
                    no_data_label.setAlignment(Qt.AlignCenter)
                    extra_container.layout().addWidget(no_data_label)
                extra_container.setVisible(True)

    def _build_comparison_dict(self, report: Dict) -> Dict[str, Dict]:
        """从报告中构建 comparison_data 字典，用于雷达图和衰减图
        
        优先从 contrast.magnitude 读取，若无则从 metrics/control_metrics 直接构建
        """
        result = {}
        locations = report.get('locations', {})
        self.logger.info(f"[comparison调试] locations keys: {list(locations.keys())[:5] if locations else '空'}")
        for loc_id, loc_data in locations.items():
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
            self.logger.info(f"[comparison调试] {loc_id}: contrast={bool(contrast)}, magnitude keys={list(magnitude.keys())[:5]}")
            for metric_id, metric_data in magnitude.items():
                if not isinstance(metric_data, dict):
                    continue
                exp_val = metric_data.get('experimental', metric_data.get('exp'))
                ctrl_val = metric_data.get('control', metric_data.get('ctrl'))
                delta = metric_data.get('delta_pct')
                if exp_val is not None and ctrl_val is not None and delta is not None:
                    label = f"{loc_id[:6]}-{metric_id[:8]}"
                    result[label] = {
                        'exp': float(exp_val) if exp_val else 0,
                        'ctrl': float(ctrl_val) if ctrl_val else 0,
                        'atten_pct': float(delta),
                    }
        
        # 备选: 若 contrast.magnitude 为空, 从 metrics/control_metrics 直接计算
        if not result:
            self.logger.info("[comparison调试] contrast.magnitude 为空, 尝试从 metrics/control_metrics 构建")
            for loc_id, loc_data in locations.items():
                metrics = loc_data.get('metrics', {})
                ctrl_metrics = loc_data.get('control_metrics', {})
                self.logger.info(f"[comparison调试] 备选路径 {loc_id}: metrics.keys={list(metrics.keys())[:5]}, ctrl_metrics.keys={list(ctrl_metrics.keys())[:5]}")
                for metric_id, exp_val in metrics.items():
                    if not isinstance(exp_val, (int, float)):
                        continue
                    ctrl_val = ctrl_metrics.get(metric_id)
                    if not isinstance(ctrl_val, (int, float)):
                        continue
                    if exp_val == -1.0 or ctrl_val == -1.0:
                        continue
                    denom = max(abs(exp_val), abs(ctrl_val), 1e-6)
                    delta = (exp_val - ctrl_val) / denom * 100
                    label = f"{loc_id[:6]}-{metric_id[:8]}"
                    result[label] = {
                        'exp': float(exp_val),
                        'ctrl': float(ctrl_val),
                        'atten_pct': round(delta, 1),
                    }
        return result

    # ── SQLite 数据加载 ──

    def _load_behavior_events_from_sqlite(self, cache_id: str) -> Optional[Dict]:
        """
        从 CacheRegistry 加载行为事件数据：
        1. 通过 CacheRegistry.get_cache(cache_id) 获取 AnalysisResultCache
        2. 从 AnalysisResultCache 查询 behavior_events 表
        3. 转换为 behavior_summary 格式
        4. 返回兼容的报告字典用于 UI 填充
        """
        if not self._cache_registry:
            self.logger.warning("CacheRegistry 未注入，无法加载 SQLite 事件")
            return None

        try:
            cache, analysis_cache = self._cache_registry.get_cache(cache_id)
        except Exception as e:
            self.logger.error(f"获取缓存失败 ({cache_id[:8]}...): {e}")
            return None

        if not analysis_cache:
            self.logger.warning("AnalysisResultCache 不可用，无法加载行为事件")
            return None

        events = []
        try:
            if hasattr(analysis_cache, 'get_all_maneuver_events'):
                events = analysis_cache.get_all_maneuver_events()
        except Exception as e:
            self.logger.error(f"读取行为事件失败: {e}")

        if not events:
            self._behavior_events_for_timeline = []
            return {'behavior_summary': {'total_events': 0, 'events': []}}

        self._ensure_type_labels()

        behavior_events = []
        for event in events:
            e_type = getattr(event, 'event_type', '') or getattr(event, 'type', '')
            e_name = getattr(event, 'event_name', '') or getattr(event, 'label_cn', '')
            if not e_name and e_type and self._type_labels:
                e_name = self._type_labels.get(e_type, e_type)

            eid = getattr(event, 'event_id', '') or getattr(event, 'id', '')
            e_start = getattr(event, 'start_time', 0.0) or getattr(event, 't_start', 0.0)
            e_end = getattr(event, 'end_time', 0.0) or getattr(event, 't_end', 0.0)
            e_duration = e_end - e_start if e_end > e_start else getattr(event, 'duration', 0.0)

            feat = {}
            if hasattr(event, 'features') and event.features:
                feat = dict(event.features)
            elif hasattr(event, 'speed_mean'):
                feat = {'speed_mean': getattr(event, 'speed_mean', 0.0),
                        'speed_std': getattr(event, 'speed_std', 0.0),
                        'accel_mean': getattr(event, 'accel_mean', 0.0),
                        'speed_from': getattr(event, 'speed_from', 0.0),
                        'speed_to': getattr(event, 'speed_to', 0.0)}

            be = {'id': str(eid), 'type': e_type, 'name': e_name,
                  'start_time': e_start, 'end_time': e_end,
                  'duration': e_duration,
                  'confidence': getattr(event, 'confidence', 0.0), **feat}
            behavior_events.append(be)

        behavior_events.sort(key=lambda e: e['start_time'])
        self._behavior_events_for_timeline = behavior_events

        report = {'behavior_summary': {'total_events': len(behavior_events), 'events': behavior_events}}
        return report

    def _ensure_type_labels(self):
        """确保事件类型中文标签已加载"""
        if not self._type_labels:
            try:
                from core.core.analysis.layer3_maneuver_segmentation.event_detector import EVENT_TYPES
                self._type_labels = dict(EVENT_TYPES)
            except ImportError:
                pass

    def _create_timeline_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("2. 行程时间轴")
        title.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {LC['text_primary']};"
            f"padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};"
        )
        layout.addWidget(title)

        self._timeline_widget = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline_widget)
        self._timeline_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline_layout.setSpacing(4)
        layout.addWidget(self._timeline_widget)

        self._timeline_empty = QLabel("暂无数据")
        self._timeline_empty.setAlignment(Qt.AlignCenter)
        self._timeline_empty.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 11px; padding: 20px;"
        )
        self._timeline_layout.addWidget(self._timeline_empty)

        return card

    def _ensure_timeline_empty(self):
        try:
            if self._timeline_empty is not None:
                _ = self._timeline_empty.isWidgetType()
        except RuntimeError:
            self._timeline_empty = None

        if self._timeline_empty is None:
            self._timeline_empty = QLabel("暂无数据")
            self._timeline_empty.setAlignment(Qt.AlignCenter)
            self._timeline_empty.setStyleSheet(
                "color: #CCCCCC; font-size: 13px; padding: 30px;"
            )

    def _update_timeline(self):
        """渲染行程时间轴 — 基于行为事件（含时间/类型/评分）"""
        events = getattr(self, '_behavior_events_for_timeline', [])
        if not events and self._trip_summary is not None:
            # 兼容旧的 TripSummary 路径
            ts = self._trip_summary
            self._ensure_timeline_empty()
            self._clear_timeline_widgets()

            heatmap = ts.generate_timeline_heatmap()
            if not heatmap:
                self._show_timeline_empty()
                return

            self._remove_timeline_empty()
            max_time = max(r.end_ts for r in ts.all_records) if ts.all_records else 10
            if max_time <= 0:
                max_time = 10

            sorted_types = sorted(heatmap.items(), key=lambda x: len(x[1]), reverse=True)
            for etype, segments in sorted_types:
                self._add_timeline_row(etype, segments, max_time)
            return

        if not events:
            self._show_timeline_empty()
            return

        # ── v8.0 移植: 优先使用 matplotlib 事件时间线图表 ──
        from modules.ui.seat_evaluation.advanced_charts import create_event_timeline
        overview_data = getattr(self, '_current_report', {}).get('_overview_data')
        if overview_data:
            ts_arr = np.asarray(overview_data.get('timestamps', []))
            sp_arr = np.asarray(overview_data.get('speed', []))
            wh_arr = np.asarray(overview_data.get('wheel', []))
            if len(ts_arr) > 2:
                try:
                    self._ensure_timeline_empty()
                    self._clear_timeline_widgets()
                    self._remove_timeline_empty()

                    loc_label = overview_data.get('location_label', '')
                    fig = create_event_timeline(ts_arr, sp_arr, wh_arr, events,
                        title=f"驾驶事件时间线 — {loc_label}通道")
                    canvas = FigureCanvas(fig)
                    self._timeline_layout.addWidget(canvas)
                    return
                except Exception as e:
                    self.logger.warning(f"事件时间线图表生成失败, 回退到行段模式: {e}")

        # ── 回退：从行为事件列表构建行段热力图 ──
        self._ensure_timeline_empty()
        self._clear_timeline_widgets()
        self._remove_timeline_empty()

        max_time = getattr(self, '_total_duration_s', 60)
        # 按事件类型聚合
        heatmap: Dict[str, list] = {}
        for evt in events:
            if not isinstance(evt, dict):
                continue
            etype = evt.get('event_type', evt.get('type', 'unknown'))
            start_t = evt.get('t_start', evt.get('start_time', evt.get('timestamp', 0)))
            score = evt.get('score')
            # 去重：同类型、同时间段的合并
            found = False
            for existing in heatmap.get(etype, []):
                if abs(existing[0] - start_t) < 0.5:
                    found = True
                    break
            if not found:
                heatmap.setdefault(etype, []).append((start_t, start_t + 2, score))

        sorted_types = sorted(heatmap.items(), key=lambda x: len(x[1]), reverse=True)
        for etype, segments in sorted_types:
            self._add_timeline_row(etype, segments, max_time)

    def _clear_timeline_widgets(self):
        while self._timeline_layout.count():
            item = self._timeline_layout.takeAt(0)
            if item.widget():
                try:
                    item.widget().deleteLater()
                except RuntimeError:
                    pass

    def _show_timeline_empty(self):
        self._ensure_timeline_empty()
        self._timeline_layout.addWidget(self._timeline_empty)

    def _remove_timeline_empty(self):
        try:
            if self._timeline_empty and self._timeline_empty.parent() is not None:
                self._timeline_layout.removeWidget(self._timeline_empty)
                self._timeline_empty.setParent(None)
        except RuntimeError:
            self._timeline_empty = None

    def _add_timeline_row(self, etype: str, segments: list, max_time: float):
        row_widget = QWidget()
        row_widget.setFixedHeight(28)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        cn = self._type_labels.get(etype, etype)
        color = TYPE_COLORS.get(etype, '#95A5A6')
        lbl = QLabel(cn)
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: 600; padding-right: 4px;"
        )
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(lbl)

        track = QFrame()
        track.setStyleSheet(f"background-color: {LC['bg_input']}; border-radius: 2px;")
        track.setFixedHeight(16)
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)

        for start_t, end_t, score in segments:
            left_pct = max(0, int((start_t / max_time) * 100))
            width_pct = max(2, int(((end_t - start_t) / max_time) * 100))

            spacer = QWidget()
            spacer.setFixedWidth(left_pct)
            spacer.setStyleSheet("background: transparent;")
            track_layout.addWidget(spacer)

            seg = QWidget()
            seg.setFixedWidth(width_pct)

            if score is not None:
                if score >= 90:
                    seg_color = '#27AE60'
                elif score >= 70:
                    seg_color = '#4A90D9'
                elif score >= 50:
                    seg_color = '#F39C12'
                else:
                    seg_color = '#E74C3C'
            else:
                seg_color = '#D0D0D0'

            seg.setStyleSheet(f"background-color: {seg_color}; border-radius: 2px;")
            seg.setToolTip(
                f"{cn}: {start_t:.1f}s-{end_t:.1f}s"
                + (f" 评分:{score:.0f}" if score else " (未评)")
            )
            track_layout.addWidget(seg)

        track_layout.addStretch()
        row_layout.addWidget(track, 1)
        self._timeline_layout.addWidget(row_widget)

    def set_dataset_path(self, path: str):
        if path and os.path.exists(path):
            self._dataset_path = path
            basename = os.path.basename(path)
            self._file_label.setText(basename)
            self._file_label.setStyleSheet(
                f"color: {LC['success']}; border: 1px solid {LC['success']}; "
                f"padding: 5px 10px; border-radius: 4px; background: #F0FFF4;"
            )
            self._dataset_badge.setText("数据已加载")
            self._dataset_badge.setStyleSheet(
                f"color: {LC['success']}; font-size: 10px; padding: 2px 10px; "
                f"background: #F0FFF4; border: 1px solid {LC['success']}; border-radius: 10px;"
            )
            self._analyze_btn.setEnabled(True)
            self._empty_guide.setVisible(False)
            self._overview_group.setVisible(False)
            self._profile_group.setVisible(True)
            self._output_tab_widget.setVisible(False)
            self._status_label.setText(f'数据集已加载: {basename}')

# ══════════════════════════════════════════════════════════════════
# 模块级辅助函数
# ══════════════════════════════════════════════════════════════════

def _smooth_curve(data: "np.ndarray", window: int = 5) -> "np.ndarray":
    """曲线平滑：对原始数据做滑动平均，去除高频毛刺，使曲线更美观。

    Args:
        data: 一维 numpy 数组
        window: 滑动窗口大小（奇数），越大越平滑

    Returns:
        平滑后的一维数组（长度不变，两端用边缘值填充）
    """
    if window < 3 or len(data) < window:
        return data
    if window % 2 == 0:
        window += 1  # 确保奇数
    half = window // 2
    padded = np.pad(data, (half, half), mode='edge')
    kernel = np.ones(window) / window
    smoothed = np.convolve(padded, kernel, mode='valid')
    return smoothed[:len(data)]
