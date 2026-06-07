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
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
import csv as csv_mod

import numpy as np

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QTextEdit,
    QSplitter, QFrame, QCheckBox, QSpinBox, QHeaderView,
    QTabWidget, QScrollArea, QGridLayout, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSize, QTimer
from PySide6.QtGui import QFont, QColor
import shiboken6

from core.core.seat_evaluation.engine_v2 import MultiChannelSeatEvaluationEngine
from core.core.seat_evaluation.data_preprocessor import DataPreprocessor
from core.core.seat_evaluation.evaluation_report import EvaluationReportGenerator
from core.core.seat_evaluation.full_timeseries_evaluator import FullTimeseriesEvaluator
from modules.ui.seat_evaluation.visualization_manager import VisualizationManager
from modules.ui.seat_evaluation.advanced_charts import (
    create_event_timeline, create_psd_comparison, create_comparison_radar,
    create_attenuation_bar, create_acceleration_waveform, create_srs_comparison,
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
    font-size: 12px;
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
    font-size: 11px;
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
    import csv as _csv
    from collections import defaultdict

    by_imu = defaultdict(lambda: {'ax': [], 'ay': [], 'az': [],
                                   'gx': [], 'gy': [], 'gz': [],
                                   'timestamps': [], 'speed': [], 'wheel': []})
    raw_records = []  # 保留原始记录用于 DrivingEventDetector

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = _csv.DictReader(f)
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
    import numpy as np

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
        import sqlite3
        conn = sqlite3.connect(file_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return 'data_records' in tables or 'analysis_results' in tables
    except Exception:
        return False

def _parse_sqlite_cache(file_path: str):
    """从SQLite缓存文件解析数据"""
    import sqlite3
    import json
    
    conn = sqlite3.connect(file_path)
    cursor = conn.execute("SELECT source_type, rel_time, channel, imu_name, payload FROM data_records ORDER BY rel_time")
    
    by_imu = {}
    
    for row in cursor.fetchall():
        source_type, rel_time, channel, imu_name, payload = row
        try:
            record = json.loads(payload)
        except json.JSONDecodeError:
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
                        'ax': processed['acc'][:, 0],
                        'ay': processed['acc'][:, 1],
                        'az': processed['acc'][:, 2],
                        'timestamps': processed['timestamps'],
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
                    }

                    metrics = {}
                    for metric_id in self._selected_metrics:
                        if metric_id == 'ATTEN_H':
                            continue  # ATTEN_H is computed post-hoc as a cross-group metric
                        try:
                            value = self._engine._calculate_single_metric(metric_id, data_window)
                            metrics[metric_id] = value
                        except Exception as e:
                            metrics[metric_id] = -1.0

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

                # ── P1修复: ATTEN_H 后计算 ──
                # η_H = (DISP_HR_ctrl - DISP_HR_exp) / DISP_HR_ctrl × 100%
                if 'ATTEN_H' in self._selected_metrics:
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
                        exp_profile, ctrl_profile, loc_id
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
                    # 从 raw_records 构建时间→车速快速查找表 (单位转为 km/h)
                    _speed_lookup = {}
                    for rec in raw_records:
                        ts = rec.get('rel_time', rec.get('timestamp', None))
                        sp = rec.get('speed', None)
                        if ts is not None and sp is not None:
                            _speed_lookup[round(float(ts), 3)] = float(sp)
                    _speed_keys = sorted(_speed_lookup.keys()) if _speed_lookup else []

                    def _lookup_speed(t_val: float) -> float:
                        """二分查找最接近 t_val 的车速"""
                        if not _speed_keys:
                            return 0.0
                        import bisect
                        idx = bisect.bisect_left(_speed_keys, t_val)
                        if idx == 0:
                            return _speed_lookup[_speed_keys[0]]
                        if idx >= len(_speed_keys):
                            return _speed_lookup[_speed_keys[-1]]
                        # 取更近的
                        if abs(_speed_keys[idx] - t_val) < abs(_speed_keys[idx - 1] - t_val):
                            return _speed_lookup[_speed_keys[idx]]
                        return _speed_lookup[_speed_keys[idx - 1]]

                    for evt in events:
                        t0 = evt.get('t_start', 0)
                        t1 = evt.get('t_end', 0)
                        evt['speed_at_start'] = round(_lookup_speed(t0), 1)
                        evt['speed_at_end'] = round(_lookup_speed(t1), 1)
                        evt['speed_delta'] = round(evt['speed_at_end'] - evt['speed_at_start'], 1)

                    behavior_summary['events'] = events[:200]
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
                    import traceback
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
                speed_bins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 70]
                hist, _ = np.histogram(combined_speed, bins=speed_bins)
                vehicle_summary['speed_histogram'] = {
                    'bins': speed_bins,
                    'counts': hist.tolist(),
                    'labels': [f'{speed_bins[i]}-{speed_bins[i+1]}' for i in range(len(speed_bins)-1)],
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
                is_db = _is_sqlite_cache_file(self._dataset_path)
                logger.info(f"[全时域诊断] dataset_path={self._dataset_path}, is_db={is_db}, channel_data_map keys={list(channel_data_map.keys())[:5]}...")
                if is_db:
                    import pandas as pd
                    rows = []
                    for ch_name, ch_data in channel_data_map.items():
                        if ch_name.startswith('_'):
                            continue
                        ts = ch_data.get('timestamps', [])
                        ax = ch_data.get('ax', [])
                        ay = ch_data.get('ay', [])
                        az = ch_data.get('az', [])
                        gx = ch_data.get('gx', [])
                        gy = ch_data.get('gy', [])
                        gz = ch_data.get('gz', [])
                        sp = ch_data.get('speed', [])
                        wh = ch_data.get('wheel', [])
                        n = min(len(ts), len(ax), len(ay), len(az))
                        for i in range(n):
                            rows.append({
                                'imu_name': ch_name,
                                'rel_time': ts[i] if i < len(ts) else 0.0,
                                'Ax_m_s2': ax[i] if i < len(ax) else 0.0,
                                'Ay_m_s2': ay[i] if i < len(ay) else 0.0,
                                'Az_m_s2': az[i] if i < len(az) else 0.0,
                                'Gx_dps': gx[i] if i < len(gx) else 0.0,
                                'Gy_dps': gy[i] if i < len(gy) else 0.0,
                                'Gz_dps': gz[i] if i < len(gz) else 0.0,
                                'speed': sp[i] if i < len(sp) else 0.0,
                                'wheel': wh[i] if i < len(wh) else 0.0,
                            })
                    if rows:
                        df_for_eval = pd.DataFrame(rows)
                        evaluator.load_from_dataframe(df_for_eval)
                        logger.info(f"[全时域诊断] load_from_dataframe完成: exp_keys={list(evaluator.exp.keys())[:3]}, ctrl_keys={list(evaluator.ctrl.keys())[:3]}, common_t={len(evaluator.common_t) if evaluator.common_t else 0}")
                    else:
                        raise RuntimeError("SQLite缓存数据为空，无法构建DataFrame")
                else:
                    evaluator.load_from_csv(self._dataset_path)
                
                if not self._is_running: return
                self.progress_updated.emit(80, '检测事件...')
                behavior_events = behavior_summary.get('events', [])
                if behavior_events:
                    evaluator.set_external_events(behavior_events)
                    logger.info(f"[全时域诊断] 使用驾驶行为事件: {len(behavior_events)} 个")
                else:
                    evaluator.detect_events()
                    logger.info("[全时域诊断] 使用全时域引擎内部事件检测")
                
                if not self._is_running: return
                self.progress_updated.emit(81, '事件级对比分析...')
                evaluator.event_analysis()

                if not self._is_running: return
                self.progress_updated.emit(83, '滑动窗口分析...')
                evaluator.window_analysis()
                
                if not self._is_running: return
                self.progress_updated.emit(86, '频谱分析...')
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
                
                if not self._is_running: return
                self.progress_updated.emit(96, '生成报告...')
                evaluator.generate_report(output_dir)
                
                if not self._is_running: return
                self.progress_updated.emit(98, '生成图表...')
                viz_manager = VisualizationManager()
                try:
                    viz_manager.generate_all_plots(evaluator, output_dir)
                except Exception as viz_e:
                    logger.warning(f"图表文件生成失败(非致命): {viz_e}")

                num_plots = len([f for f in os.listdir(output_dir) if f.endswith('.png')])

                full_timeseries_result = {
                    'events': evaluator.events,
                    'results': evaluator.results,
                    'output_dir': output_dir,
                    'num_plots': num_plots,
                }
                logger.info(f"[全时域诊断] 评测成功: events={len(evaluator.events)}, "
                           f"results_keys={list(evaluator.results.keys())}, "
                           f"results_empty={not bool(evaluator.results)}")
            except Exception as e:
                import traceback
                logger.warning(f"全时域评测失败(非致命): {e}")
                logger.warning(f"全时域评测 Traceback:\n{traceback.format_exc()}")
                full_timeseries_result = {'error': str(e)}

            logger.info(f"[全时域诊断] full_timeseries_result type={type(full_timeseries_result).__name__}, "
                       f"keys={list(full_timeseries_result.keys()) if isinstance(full_timeseries_result, dict) else 'N/A'}")
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
                overview_data = {
                    'timestamps': ts.tolist() if hasattr(ts, 'tolist') else list(ts),
                    'speed': sp_arr.tolist() if hasattr(sp_arr, 'tolist') else list(sp_arr),
                    'wheel': wh_arr.tolist() if hasattr(wh_arr, 'tolist') else list(wh_arr),
                    'exp_ax': exp_data.get('ax', np.array([])).tolist() if hasattr(exp_data.get('ax', np.array([])), 'tolist') else list(exp_data.get('ax', [])),
                    'exp_ay': exp_data.get('ay', np.array([])).tolist() if hasattr(exp_data.get('ay', np.array([])), 'tolist') else list(exp_data.get('ay', [])),
                    'exp_az': exp_data.get('az', np.array([])).tolist() if hasattr(exp_data.get('az', np.array([])), 'tolist') else list(exp_data.get('az', [])),
                    'ctrl_ax': ctrl_data.get('ax', np.array([])).tolist() if hasattr(ctrl_data.get('ax', np.array([])), 'tolist') else list(ctrl_data.get('ax', [])),
                    'ctrl_ay': ctrl_data.get('ay', np.array([])).tolist() if hasattr(ctrl_data.get('ay', np.array([])), 'tolist') else list(ctrl_data.get('ay', [])),
                    'ctrl_az': ctrl_data.get('az', np.array([])).tolist() if hasattr(ctrl_data.get('az', np.array([])), 'tolist') else list(ctrl_data.get('az', [])),
                    'exp_channel': exp_head_ch,
                    'ctrl_channel': ctrl_head_ch,
                }
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
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.setMinimumWidth(0)
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
            f"<table style='font-size:11px;width:100%;border-collapse:collapse;'>"
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
            f"<table style='font-size:11px;width:100%;border-collapse:collapse;'>"
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

        if self._meta.industry_references:
            l.addWidget(QLabel(""))
            refs_html = (
                f"<div style='font-size:10px;color:{LC['text_muted']};border-top:1px solid {LC['border_light']};padding-top:4px;'>"
                f"<b>行业参考:</b><br>"
                + "<br>".join([f"• {r}" for r in self._meta.industry_references])
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

        self._pipeline_labels = ['加载数据', '提取通道', '预处理', '指标计算', '生成报告']
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder

        self._trip_summary = None
        self._behavior_events_for_timeline = []  # 行为事件列表（含时间戳）
        self._type_labels: Dict[str, str] = {}

        self._chart_slots: Dict[str, Dict] = {}

        # ── 数据源模式 ──
        self._data_source_mode = self.DataSourceMode.OFFLINE_FILE
        self._cache_registry = None           # CacheRegistry 引用
        self._selected_cache_id: str = ''     # 当前选中的缓存 ID
        self._time_range: Tuple[float, float] = (0.0, 0.0)  # 分析时间范围

        self._init_ui()
        self.logger.info("全量统计分析标签页已初始化")

    def clear_all(self):
        """清除全量统计分析所有数据（实现 ClearableResource 协议）"""
        self._current_report = None
        self._current_timeseries_result = None
        self._contrast_data = []
        self._dataset_path = ''
        self._trip_summary = None
        self._behavior_events_for_timeline = []
        self._selected_cache_id = ''
        self._time_range = (0.0, 0.0)
        self._chart_slots.clear()
        if hasattr(self, '_results_table') and self._results_table:
            self._results_table.setRowCount(0)
        self.logger.info("全量统计分析数据已清空")

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content.setMinimumSize(0, 0)
        content.minimumSizeHint = lambda: QSize(0, 0)

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
        #   控制 → 概览 → 时序行为 → 剖面 → 对照 →
        #   全时域 → 频域频谱 → 统计检验 → 输出
        # ════════════════════════════════════════════════════════════

        self._group_chart_layouts = {}

        # ════ 1. 分析总览 ════
        self._overview_group = self._create_section_group("分析总览")
        self._overview_group.setVisible(True)
        main_layout.addWidget(self._overview_group)

        self._overview_container = self._create_overview_dashboard()
        self._overview_group._content_layout.addWidget(self._overview_container)

        self._condition_overview_card = self._create_condition_overview_card()
        self._overview_group._content_layout.addWidget(self._condition_overview_card)

        _overview_charts = QVBoxLayout()
        _overview_charts.setSpacing(12)
        self._overview_group._content_layout.addLayout(_overview_charts)
        self._group_chart_layouts['overview'] = _overview_charts

        self._create_chart_placeholder("全时程概览图", "full_timeseries_overview", "overview", 360)

        # ════ 2. 时序与行为分析 ════
        self._timeline_behavior_group = self._create_section_group("时序与行为分析")
        self._timeline_behavior_group.setVisible(True)
        main_layout.addWidget(self._timeline_behavior_group)

        self._behavior_events_card = self._create_behavior_events_card()
        self._timeline_behavior_group._content_layout.addWidget(self._behavior_events_card)

        timeline_card = self._create_timeline_card()
        self._timeline_behavior_group._content_layout.addWidget(timeline_card)

        _timeline_charts = QVBoxLayout()
        _timeline_charts.setSpacing(12)
        self._timeline_behavior_group._content_layout.addLayout(_timeline_charts)
        self._group_chart_layouts['timeline_behavior'] = _timeline_charts

        self._create_chart_placeholder("加速度波形", "acceleration_waveform", "timeline_behavior", 400)
        self._create_chart_placeholder("事件对比图", "event_comparison", "timeline_behavior", 320)

        # ════ 3. 多通道剖面分析 ════
        self._profile_group = self._create_section_group("多通道剖面分析")
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

        self._contrast_profile_card = self._create_contrast_profile_card()
        self._profile_group._content_layout.addWidget(self._contrast_profile_card)

        # ════ 4. 指标对照分析 ════
        self._contrast_group = self._create_section_group("指标对照分析")
        self._contrast_group.setVisible(True)
        main_layout.addWidget(self._contrast_group)

        comp_control_card = self._create_comparison_control_card()
        self._contrast_group._content_layout.addWidget(comp_control_card)

        comparison_card = self._create_indicator_comparison_card()
        self._contrast_group._content_layout.addWidget(comparison_card)

        _contrast_charts = QVBoxLayout()
        _contrast_charts.setSpacing(12)
        self._contrast_group._content_layout.addLayout(_contrast_charts)
        self._group_chart_layouts['contrast'] = _contrast_charts

        self._create_chart_placeholder("衰减柱状图", "attenuation_bar", "contrast", 300)
        self._create_chart_placeholder("雷达对比图", "comparison_radar", "contrast", 400)

        # ════ 5. 全时域滑动窗口评测 ════
        self._fulltimeseries_group = self._create_section_group("全时域滑动窗口评测")
        self._fulltimeseries_group.setVisible(True)
        main_layout.addWidget(self._fulltimeseries_group)

        self._sliding_window_card = self._create_sliding_window_card()
        self._fulltimeseries_group._content_layout.addWidget(self._sliding_window_card)

        _fullts_charts = QVBoxLayout()
        _fullts_charts.setSpacing(12)
        self._fulltimeseries_group._content_layout.addLayout(_fullts_charts)
        self._group_chart_layouts['fulltimeseries'] = _fullts_charts

        self._create_chart_placeholder("滑动窗口衰减趋势图", "window_attenuation", "fulltimeseries", 380)

        # ════ 6. 频域与频谱分析 ════
        self._spectrum_group = self._create_section_group("频域与频谱分析")
        self._spectrum_group.setVisible(True)
        main_layout.addWidget(self._spectrum_group)

        self._band_attenuation_card = self._create_band_attenuation_card()
        self._spectrum_group._content_layout.addWidget(self._band_attenuation_card)
        self._comprehensive_metrics_card = self._create_comprehensive_metrics_card()
        self._spectrum_group._content_layout.addWidget(self._comprehensive_metrics_card)
        self._stft_card = self._create_stft_card()
        self._spectrum_group._content_layout.addWidget(self._stft_card)

        _spectrum_charts = QVBoxLayout()
        _spectrum_charts.setSpacing(12)
        self._spectrum_group._content_layout.addLayout(_spectrum_charts)
        self._group_chart_layouts['spectrum'] = _spectrum_charts

        self._create_chart_placeholder("PSD频谱对比", "psd_comparison", "spectrum", 320)
        self._create_chart_placeholder("SRS冲击响应谱", "srs_comparison", "spectrum", 300)
        self._create_chart_placeholder("频谱分析图", "spectrum_analysis", "spectrum", 320)
        self._create_chart_placeholder("频谱衰减比图", "spectrum_ratio", "spectrum", 320)
        self._create_chart_placeholder("频段雷达图", "band_radar", "spectrum", 420)

        # ════ 7. 统计检验分析 ════
        self._statistics_group = self._create_section_group("统计检验分析")
        self._statistics_group.setVisible(True)
        main_layout.addWidget(self._statistics_group)

        self._statistics_card = self._create_statistics_card()
        self._statistics_group._content_layout.addWidget(self._statistics_card)

        _statistics_charts = QVBoxLayout()
        _statistics_charts.setSpacing(12)
        self._statistics_group._content_layout.addLayout(_statistics_charts)
        self._group_chart_layouts['statistics'] = _statistics_charts

        self._create_chart_placeholder("时频分析图", "stft_analysis", "statistics", 400)
        self._create_chart_placeholder("统计仪表盘", "statistics_dashboard", "statistics", 340)
        self._create_chart_placeholder("统计特征(算子级输出)", "statistical_features", "statistics", 500)

        # ════ 8. 统一输出：QTabWidget（报告预览 + 对比数据表）════
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

        ec_title = QLabel("综合分析报告")
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

        self._export_pdf_btn = QPushButton("导出 PDF")
        self._export_pdf_btn.setStyleSheet(self._export_btn_style())
        self._export_pdf_btn.clicked.connect(self._on_export_pdf_clicked)
        self._export_pdf_btn.setEnabled(False)
        ec_layout.addWidget(self._export_pdf_btn)

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

        # --- Tab 2: 对比数据表（实验组 / 对照组 / 差值）---
        contrast_data_tab = QWidget()
        cd_layout = QVBoxLayout(contrast_data_tab)
        cd_layout.setContentsMargins(0, 8, 0, 0)
        cd_layout.setSpacing(6)

        # 对照数据过滤栏
        cd_filter_bar = QFrame()
        cd_filter_bar.setStyleSheet(f"background: transparent; border: none;")
        cdf_layout = QHBoxLayout(cd_filter_bar)
        cdf_layout.setContentsMargins(4, 0, 4, 4)

        cd_title = QLabel("实验组 vs 对照组 指标对比")
        cd_title.setStyleSheet(
            f"color: {LC['text_primary']}; font-size: 12px; font-weight: 600; background: transparent;"
        )
        cdf_layout.addWidget(cd_title)

        cdf_layout.addStretch()

        cd_loc_label = QLabel("筛选位置:")
        cd_loc_label.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 11px;")
        cdf_layout.addWidget(cd_loc_label)

        self._contrast_loc_filter = QComboBox()
        self._contrast_loc_filter.addItem("全部位置", "all")
        self._contrast_loc_filter.setMaximumWidth(150)
        self._contrast_loc_filter.currentIndexChanged.connect(self._on_contrast_loc_filter_changed)
        cdf_layout.addWidget(self._contrast_loc_filter)

        cd_layout.addWidget(cd_filter_bar)

        # 对比数据表格
        self._contrast_data_table = QTableWidget()
        self._contrast_data_table.setAlternatingRowColors(True)
        self._contrast_data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._contrast_data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._contrast_data_table.verticalHeader().setVisible(False)
        self._contrast_data_table.verticalHeader().setDefaultSectionSize(24)
        self._contrast_data_table.setColumnCount(10)
        self._contrast_data_table.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "位置", "实验组", "对照组", "变化率(%)", "评级", "裁决", "通过阈值", "改进"
        ])
        self._contrast_data_table.setStyleSheet(self._card_table_style())
        header = self._contrast_data_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for i in range(3, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        cd_layout.addWidget(self._contrast_data_table)

        # 汇总统计标签（Tab页内的，区别于卡片内的 _contrast_summary_label）
        self._contrast_tab_summary_label = QLabel("")
        self._contrast_tab_summary_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 10px; padding: 2px 4px;"
        )
        cd_layout.addWidget(self._contrast_tab_summary_label)

        # 添加到TabWidget
        self._output_tab_widget.addTab(report_preview_tab, "\U0001F4CA 报告预览")
        self._output_tab_widget.addTab(contrast_data_tab, "\U0001F4CB 对比数据表")

        self._status_label = QLabel('就绪 — 请加载数据集开始分析')
        self._status_label.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 11px; padding: 7px 12px; "
            f"background: {LC['bg_card']}; border: 1px solid {LC['border_light']}; border-radius: 6px;"
        )
        main_layout.addWidget(self._status_label)

        self._scroll_area.setWidget(content)
        self._content_initialized = True

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._constrain_content_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._constrain_content_width()

    def _constrain_content_width(self):
        viewport = self._scroll_area.viewport()
        content = self._content_widget
        if viewport is None or content is None:
            return
        if shiboken6.isValid(content) and shiboken6.isValid(viewport):
            vp_width = viewport.width()
            if vp_width > 50:
                content.setMaximumWidth(vp_width)
                for i in range(content.layout().count() if content.layout() else 0):
                    item = content.layout().itemAt(i)
                    if item and item.widget():
                        w = item.widget()
                        if shiboken6.isValid(w):
                            w.setMaximumWidth(vp_width)
                            if isinstance(w, QGroupBox):
                                inner = w.findChild(QWidget)
                                if inner and shiboken6.isValid(inner):
                                    inner.setMaximumWidth(vp_width - 24)
                            if isinstance(w, QTabWidget):
                                w.setMaximumWidth(vp_width)

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
        from PySide6.QtWidgets import QDoubleSpinBox
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
        self._results_table.setColumnCount(11)
        self._results_table.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "评测维度", "单位",
            "实验组", "对照组", "绝对差", "变化率(%)", "状态", "通过阈值", "位置"
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
        title = QLabel("倍频程能量分布")
        title.setStyleSheet(
            f"font-family: Microsoft YaHei; font-size: 12px; font-weight: 600; color: {LC['text_primary']};"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self._freq_viz_frame = QFrame()
        self._freq_viz_frame.setMinimumHeight(180)
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
        title = QLabel("传递特性链")
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
        title = QLabel("时间分段分析 (10s 窗口)")
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
                font-size: 11px;
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

        title = QLabel("驾驶工况概览")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._cond_speed_info = QLabel("速度分布: --")
        self._cond_speed_info.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(self._cond_speed_info)

        self._cond_turning_info = QLabel("转向信息: --")
        self._cond_turning_info.setStyleSheet(f"color: {LC['text_secondary']}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(self._cond_turning_info)

        self._cond_speed_hist_table = QTableWidget()
        self._cond_speed_hist_table.setAlternatingRowColors(True)
        self._cond_speed_hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._cond_speed_hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._cond_speed_hist_table.verticalHeader().setVisible(False)
        self._cond_speed_hist_table.verticalHeader().setDefaultSectionSize(24)
        self._cond_speed_hist_table.setColumnCount(3)
        self._cond_speed_hist_table.setHorizontalHeaderLabels(["速度区间 (km/h)", "频次", "占比%"])
        self._cond_speed_hist_table.setMinimumHeight(200)
        # 列宽适配
        hh = self._cond_speed_hist_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self._cond_speed_hist_table)

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

        title = QLabel("驾驶行为事件")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {LC['text_primary']};")
        layout.addWidget(title)

        # 时序概览图（fig1_overview: 车速/方向盘/实验组头部/对照组头部）
        self._behavior_overview_chart = QWidget()
        self._behavior_overview_chart.setLayout(QVBoxLayout())
        self._behavior_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._behavior_overview_chart.setMinimumHeight(180)
        self._behavior_overview_chart.setVisible(False)
        layout.addWidget(self._behavior_overview_chart)

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

        return card

    def _create_contrast_profile_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("⚖️ 实验组 vs 对照组 基线对比")
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
        header.setStyleSheet(f"color: {LC['text_primary']}; font-size: 11px; font-weight: 600; background: transparent;")
        layout.addWidget(header)

        # 图例
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)
        exp_legend = QLabel("■ 实验组")
        exp_legend.setStyleSheet("color: #3498DB; font-size: 9px; font-weight: 600; background: transparent;")
        legend_row.addWidget(exp_legend)
        ctrl_legend = QLabel("■ 对照组")
        ctrl_legend.setStyleSheet("color: #E67E22; font-size: 9px; font-weight: 600; background: transparent;")
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
        chart.setContentsMargins(0, 2, 0, 0)
        chart.setSpacing(4)

        for i, band in enumerate(band_order):
            exp_pct = band_energy.get(band, 0)
            ctrl_pct = ctrl_band_energy.get(band, 0) if ctrl_band_energy else 0

            pair = QWidget()
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(1)

            # 实验组柱子（蓝色）
            exp_bar = QFrame()
            exp_bar.setFixedWidth(24)
            exp_bar.setStyleSheet("background: #3498DB; border-radius: 2px;")
            exp_height = int(max(16, exp_pct / max(max_pct, 1) * 120))
            exp_bar.setMinimumHeight(exp_height)
            exp_bar.setMaximumHeight(exp_height)
            exp_layout = QVBoxLayout(exp_bar)
            exp_layout.setContentsMargins(1, 1, 1, 1)
            exp_layout.setSpacing(0)
            exp_val = QLabel(f"{exp_pct:.1f}" if exp_pct > 0 else "")
            exp_val.setAlignment(Qt.AlignCenter)
            exp_val.setStyleSheet("color: white; font-size: 7px; font-weight: 700; background: transparent;")
            exp_layout.addWidget(exp_val)
            exp_layout.addStretch()
            pair_layout.addWidget(exp_bar, alignment=Qt.AlignBottom)

            # 对照组柱子（橙色）
            ctrl_bar = QFrame()
            ctrl_bar.setFixedWidth(24)
            ctrl_bar.setStyleSheet("background: #E67E22; border-radius: 2px;")
            ctrl_height = int(max(16, ctrl_pct / max(max_pct, 1) * 120))
            ctrl_bar.setMinimumHeight(ctrl_height)
            ctrl_bar.setMaximumHeight(ctrl_height)
            ctrl_layout = QVBoxLayout(ctrl_bar)
            ctrl_layout.setContentsMargins(1, 1, 1, 1)
            ctrl_layout.setSpacing(0)
            ctrl_val = QLabel(f"{ctrl_pct:.1f}" if ctrl_pct > 0 else "")
            ctrl_val.setAlignment(Qt.AlignCenter)
            ctrl_val.setStyleSheet("color: white; font-size: 7px; font-weight: 700; background: transparent;")
            ctrl_layout.addWidget(ctrl_val)
            ctrl_layout.addStretch()
            pair_layout.addWidget(ctrl_bar, alignment=Qt.AlignBottom)

            pair.setMinimumHeight(max(exp_height, ctrl_height) + 20)
            chart.addWidget(pair)

            # 频段标签
            tag_label = QLabel(band_labels[i])
            tag_label.setAlignment(Qt.AlignCenter)
            tag_label.setStyleSheet(f"color: {LC['text_muted']}; font-size: 7px; background: transparent;")
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
                    delta = (ovtv_exp - ovtv_ctrl) / max(abs(ovtv_ctrl), 0.001) * 100
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

        speed_hist = vehicle_summary.get('speed_histogram', {})
        labels = speed_hist.get('labels', [])
        counts = speed_hist.get('counts', [])
        if labels and counts:
            self._populate_speed_histogram(labels, counts)

        self._condition_overview_card.setVisible(True)

    def _generate_events_overview_chart(self, overview_data: Optional[Dict], events: List[Dict]) -> Optional[Figure]:
        """生成事件概览图（参照 OccupantMotionEvaluator.fig2_events）

        网格布局：每个子图展示一个事件的实验组(蓝) vs 对照组(红) 头部Ay对比
        Returns: Figure 对象，失败返回 None
        """
        if not overview_data or not events:
            return None
        ts_arr = np.array(overview_data.get('timestamps', []))
        if len(ts_arr) < 2:
            return None
        exp_ay = np.array(overview_data.get('exp_ay', []))
        ctrl_ay = np.array(overview_data.get('ctrl_ay', []))
        if len(exp_ay) == 0 or len(ctrl_ay) == 0:
            return None

        # 截断以匹配时间戳
        n = len(ts_arr)
        if len(exp_ay) > n: exp_ay = exp_ay[:n]
        if len(ctrl_ay) > n: ctrl_ay = ctrl_ay[:n]

        # 计算采样率
        fs = 1000.0
        if n > 1:
            dt = ts_arr[1] - ts_arr[0]
            if dt > 0:
                fs = 1.0 / dt

        # 取最多12个事件
        n_ev = min(len(events), 12)
        ncols = 4
        nrows = max(1, (n_ev + ncols - 1) // ncols)

        try:
            fig, axes = plt.subplots(nrows, ncols, figsize=(18, 3 * nrows))
            axes_flat = axes.flatten() if nrows * ncols > 1 else [axes]

            for i, ev in enumerate(events[:n_ev]):
                # 用 t_start/t_end 在 overview_data 中定位
                t_s = ev.get('t_start', 0)
                t_e = ev.get('t_end', 0)
                s = max(0, int(t_s * fs) - int(fs * 0.5))
                e = min(n - 1, int(t_e * fs) + int(fs * 1.5))
                # 回退：使用事件持续时间
                if e <= s:
                    s = max(0, int(t_s * fs))
                    e = min(n - 1, int(t_e * fs + fs * 1.0))
                if e <= s + 10:
                    # 事件太短，扩展窗口
                    margin = int(fs * 1.0)
                    s = max(0, int(t_s * fs) - margin)
                    e = min(n - 1, int(t_e * fs) + margin)

                t_seg = ts_arr[s:e] - t_s  # 相对时间
                ax = axes_flat[i]
                ax.plot(t_seg, exp_ay[s:e], 'b-', linewidth=1.2, alpha=0.8, label='实验组')
                ax.plot(t_seg, ctrl_ay[s:e], 'r--', linewidth=1.0, alpha=0.8, label='对照组')
                ax.axvline(x=0, color='k', linestyle=':', alpha=0.4)
                if ev.get('duration', 0) > 0:
                    ax.axvspan(0, ev.get('duration', 0.1), alpha=0.1, color='yellow')

                ev_type = ev.get('type', '?')[:6]
                ax.set_title(f'E{i+1}: {ev_type} t={t_s:.1f}s', fontsize=8)

                # 计算该事件 Ay 衰减
                evals = exp_ay[s:e]
                cvals = ctrl_ay[s:e]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    e_rms = np.sqrt(np.mean(evals[valid]**2))
                    c_rms = np.sqrt(np.mean(cvals[valid]**2))
                    if c_rms > 1e-3:
                        atn = (1 - e_rms / c_rms) * 100
                        color = '#27AE60' if atn > 0 else '#E74C3C'
                        ax.text(0.95, 0.95, f'Δ={atn:.0f}%', transform=ax.transAxes,
                                ha='right', va='top', fontsize=8, color=color, fontweight='bold')
                ax.grid(True, alpha=0.2)

            if n_ev > 0:
                axes_flat[0].legend(fontsize=7, loc='upper left')
            # 隐藏多余子图
            for i in range(n_ev, nrows * ncols):
                axes_flat[i].set_visible(False)

            plt.suptitle('全部驾驶事件 — 实验组(蓝) vs 对照组(红) 头部Ay对比', fontsize=12)
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成事件概览图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_spectrum_overview_chart(self, spectrum: Dict) -> Optional[Figure]:
        """生成频域分析图（参照 OccupantMotionEvaluator.fig3_spectrum）

        3x3网格: 每行一个轴(Ax/Ay/Az), 每列 PSD | 衰减比 | 相干性
        Returns: Figure 对象，失败返回 None
        """
        if not spectrum:
            return None

        try:
            fig, axes = plt.subplots(3, 3, figsize=(16, 12))
            for row, axis_name in enumerate(['Ax', 'Ay', 'Az']):
                s = spectrum.get(axis_name)
                if not s:
                    for col in range(3):
                        axes[row, col].set_visible(False)
                    continue

                f_arr = np.array(s.get('freq', []))
                if len(f_arr) == 0:
                    for col in range(3):
                        axes[row, col].set_visible(False)
                    continue

                # PSD
                ax0 = axes[row, 0]
                exp_psd = np.array(s.get('exp_psd', []))
                ctrl_psd = np.array(s.get('ctrl_psd', []))
                if len(exp_psd) > 0:
                    ax0.semilogy(f_arr, exp_psd, 'b-', linewidth=1, alpha=0.8, label='实验组')
                if len(ctrl_psd) > 0:
                    ax0.semilogy(f_arr, ctrl_psd, 'r-', linewidth=1, alpha=0.8, label='对照组')
                ax0.set_title(f'{axis_name} — Power Spectral Density', fontsize=10)
                ax0.set_ylabel('PSD')
                ax0.legend(fontsize=7)
                ax0.grid(True, alpha=0.3)

                # PSD Ratio
                ax1 = axes[row, 1]
                ratio = np.array(s.get('ratio', []))
                if len(ratio) > 0:
                    ax1.plot(f_arr[:len(ratio)], ratio, 'g-', linewidth=1.5)
                ax1.axhline(y=1, color='k', linestyle='--', alpha=0.5)
                ax1.set_ylabel('PSD Ratio (Exp/Ctrl)')
                ax1.set_title(f'{axis_name} — Attenuation Ratio (<1 = Effective)', fontsize=10)
                ax1.grid(True, alpha=0.3)

                # Coherence
                ax2 = axes[row, 2]
                coh = np.array(s.get('coherence', []))
                if len(coh) > 0:
                    ax2.plot(f_arr[:len(coh)], coh, 'm-', linewidth=1)
                ax2.set_ylim(0, 1)
                ax2.set_ylabel('Coherence')
                ax2.set_title(f'{axis_name} — Exp-Ctrl Coherence', fontsize=10)
                ax2.grid(True, alpha=0.3)

            for ax in axes.flatten():
                ax.set_xlabel('Frequency (Hz)', fontsize=8)

            plt.suptitle('频域分析 — 实验组 vs 对照组', fontsize=13, fontweight='bold')
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成频域分析图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_stft_overview_chart(self, stft: Dict) -> Optional[Figure]:
        """生成 STFT 时频图（参照 OccupantMotionEvaluator.fig4_stft）

        2面板: 主动座椅 Ay | 被动座椅 Ay 时频谱
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
            from matplotlib.colors import LogNorm
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 7), sharex=True, sharey=True)

            if exp_filt is not None and exp_filt.size > 0:
                im1 = ax1.pcolormesh(t_arr, f_filt, exp_filt,
                                     shading='gouraud', cmap='viridis', norm=LogNorm())
                plt.colorbar(im1, ax=ax1, label='Magnitude')
            ax1.set_ylabel('Freq (Hz)', fontsize=9)
            ax1.set_title('实验组 — Head Ay STFT', fontsize=11)

            if ctrl_filt is not None and ctrl_filt.size > 0:
                im2 = ax2.pcolormesh(t_arr, f_filt, ctrl_filt,
                                     shading='gouraud', cmap='inferno', norm=LogNorm())
                plt.colorbar(im2, ax=ax2, label='Magnitude')
            ax2.set_ylabel('Freq (Hz)', fontsize=9)
            ax2.set_xlabel('Time (s)', fontsize=9)
            ax2.set_title('对照组 — Head Ay STFT', fontsize=11)

            plt.suptitle('时频分析 (STFT) — Ay 横向加速度', fontsize=13, fontweight='bold')
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成 STFT 图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_statistics_distribution_chart(self, overview_data: Optional[Dict]) -> Optional[Figure]:
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
            fig, axes = plt.subplots(2, 3, figsize=(16, 8))
            for coli, (axis_name, color) in enumerate([('Ax', '#2196F3'), ('Ay', '#4CAF50'), ('Az', '#FF9800')]):
                evals, cvals, _ = data_map[axis_name]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() < 50:
                    axes[0, coli].set_visible(False)
                    axes[1, coli].set_visible(False)
                    continue

                # 直方图
                axes[0, coli].hist(evals[valid], bins=100, alpha=0.5, density=True,
                                   color=color, label='实验组')
                axes[0, coli].hist(cvals[valid], bins=100, alpha=0.5, density=True,
                                   color='gray', label='对照组')
                axes[0, coli].set_title(f'{axis_name} Distribution', fontsize=10)
                axes[0, coli].legend(fontsize=7)
                axes[0, coli].grid(True, alpha=0.2)

                # 箱线图（下采样）
                ds = max(1, int(len(evals[valid]) / 500))
                data_box = [evals[valid][::ds], cvals[valid][::ds]]
                bp = axes[1, coli].boxplot(data_box, labels=['实验组', '对照组'],
                                            patch_artist=True,
                                            boxprops=dict(facecolor=color, alpha=0.5))
                axes[1, coli].set_title(f'{axis_name} Box Plot', fontsize=10)
                axes[1, coli].grid(True, alpha=0.2)

            plt.suptitle('统计学分析 — 实验组 vs 对照组', fontsize=13, fontweight='bold')
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成统计分布图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_band_radar_chart(self, spectrum: Dict) -> Optional[Figure]:
        """生成全频段衰减雷达图（参照 OccupantMotionEvaluator.fig6_band_radar）

        极坐标: 5频段 x 3轴(Ax/Ay/Az) 衰减率
        Returns: Figure 对象，失败返回 None
        """
        if not spectrum:
            return None

        bands_5 = ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']

        try:
            fig, ax = plt.subplots(1, 1, figsize=(8, 8), subplot_kw=dict(polar=True))
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
                        linewidth=2, label=axis_name, markersize=8)
                ax.fill(angles, vals_clipped, alpha=0.1, color=color)

            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(bands_5, fontsize=9)
            ax.set_title('Frequency Band Attenuation Radar\n(实验组 vs 对照组)',
                         fontsize=12, fontweight='bold', pad=20)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
            ax.set_ylim(-100, 200)
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成频段雷达图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _generate_behavior_overview_chart(self, overview_data: Optional[Dict]) -> Optional[Figure]:
        """生成驾驶行为时序概览图（参照 OccupantMotionEvaluator.fig1_overview）

        4面板: 车速 | 方向盘 | 实验组头部加速度 | 对照组头部加速度
        Returns: Figure 对象，失败返回 None
        """
        if not overview_data:
            return None
        ts = overview_data.get('timestamps', [])
        if len(ts) < 2:
            return None
        ts_arr = np.array(ts)
        sp_arr = np.array(overview_data.get('speed', []))
        wh_arr = np.array(overview_data.get('wheel', []))
        exp_ax = np.array(overview_data.get('exp_ax', []))
        exp_ay = np.array(overview_data.get('exp_ay', []))
        exp_az = np.array(overview_data.get('exp_az', []))
        ctrl_ax = np.array(overview_data.get('ctrl_ax', []))
        ctrl_ay = np.array(overview_data.get('ctrl_ay', []))
        ctrl_az = np.array(overview_data.get('ctrl_az', []))

        n = len(ts_arr)
        # 截断加速度数组以匹配时间戳长度
        if len(exp_ax) > n: exp_ax = exp_ax[:n]
        if len(exp_ay) > n: exp_ay = exp_ay[:n]
        if len(exp_az) > n: exp_az = exp_az[:n]
        if len(ctrl_ax) > n: ctrl_ax = ctrl_ax[:n]
        if len(ctrl_ay) > n: ctrl_ay = ctrl_ay[:n]
        if len(ctrl_az) > n: ctrl_az = ctrl_az[:n]

        try:
            fig, axes = plt.subplots(4, 1, figsize=(16, 10), sharex=True)

            # Panel 1: 车速
            if len(sp_arr) >= n:
                sp_arr = sp_arr[:n]
            axes[0].plot(ts_arr, sp_arr, 'b-', linewidth=0.8)
            axes[0].set_ylabel('Speed\n(km/h)', fontsize=9)
            axes[0].set_title('驾驶行为时序概览 — 实验组 vs 对照组 头部响应', fontsize=12, fontweight='bold')
            axes[0].grid(True, alpha=0.3)

            # Panel 2: 方向盘转角
            if len(wh_arr) >= n:
                wh_arr = wh_arr[:n]
            axes[1].plot(ts_arr, wh_arr, 'r-', linewidth=0.8)
            axes[1].set_ylabel('Wheel\n(deg)', fontsize=9)
            axes[1].grid(True, alpha=0.3)

            # Panel 3: 实验组头部三轴
            for vals, name, color in [(exp_ax, 'Ax', '#2196F3'), (exp_ay, 'Ay', '#4CAF50'), (exp_az, 'Az', '#FF9800')]:
                if len(vals) > 0:
                    axes[2].plot(ts_arr[:len(vals)], vals, color=color, linewidth=0.3, alpha=0.6, label=name)
            axes[2].set_ylabel('Exp Head\n(m/s²)', fontsize=9)
            axes[2].legend(fontsize=7, loc='upper right', ncol=3)
            axes[2].grid(True, alpha=0.3)

            # Panel 4: 对照组头部三轴
            for vals, name, color in [(ctrl_ax, 'Ax', '#2196F3'), (ctrl_ay, 'Ay', '#4CAF50'), (ctrl_az, 'Az', '#FF9800')]:
                if len(vals) > 0:
                    axes[3].plot(ts_arr[:len(vals)], vals, color=color, linewidth=0.3, alpha=0.6, label=name)
            axes[3].set_ylabel('Ctrl Head\n(m/s²)', fontsize=9)
            axes[3].set_xlabel('Time (s)', fontsize=9)
            axes[3].legend(fontsize=7, loc='upper right', ncol=3)
            axes[3].grid(True, alpha=0.3)

            plt.tight_layout()
            return fig
        except Exception as e:
            logger.warning(f"生成行为概览图失败: {e}")
            try:
                plt.close('all')
            except Exception:
                pass
            return None

    def _populate_behavior_events(self, report: Dict):
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

        self._behavior_events_card.setVisible(True)

    def _populate_speed_histogram(self, labels, counts):
        """将速度频次数据填入 QTableWidget（3列：速度区间、频次、占比）"""
        table = self._cond_speed_hist_table
        table.setRowCount(0)
        total = sum(counts) if counts else 0
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
                att_rms = ((ctrl_rms - exp_rms) / max(abs(ctrl_rms), 1e-9)) * 100
                
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
        if meta.industry_references:
            industry_lines = "<br>".join([f"• {r}" for r in meta.industry_references])

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
        title = QLabel("滑动窗口评坚决果 — 实验组/对照组 RMS 衰减率时序")
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

        # 事件概览图（fig2_events: 各事件实验组/对照组 Ay 对比）
        self._events_overview_chart = QWidget()
        self._events_overview_chart.setLayout(QVBoxLayout())
        self._events_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._events_overview_chart.setMinimumHeight(180)
        self._events_overview_chart.setVisible(False)
        layout.addWidget(self._events_overview_chart)

        return card

    def _create_statistics_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("统计检验 — 配对t检验 + Cohen's d + 95%置信区间")
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

        # 全频段衰减雷达图（fig6_band_radar）
        self._band_radar_chart = QWidget()
        self._band_radar_chart.setLayout(QVBoxLayout())
        self._band_radar_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._band_radar_chart.setMinimumHeight(200)
        self._band_radar_chart.setVisible(False)
        layout.addWidget(self._band_radar_chart)

        return card

    def _create_band_attenuation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("频谱与频段衰减分析")
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

        # 频域分析图（fig3_spectrum: PSD / 衰减比 / 相干性 3x3）
        self._spectrum_overview_chart = QWidget()
        self._spectrum_overview_chart.setLayout(QVBoxLayout())
        self._spectrum_overview_chart.layout().setContentsMargins(0, 0, 0, 0)
        self._spectrum_overview_chart.setMinimumHeight(200)
        self._spectrum_overview_chart.setVisible(False)
        layout.addWidget(self._spectrum_overview_chart)

        return card

    def _create_comprehensive_metrics_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("统计特征（算子级输出）— VDV / Crest / Skew / Kurt / MAV / Impulse")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {LC['text_primary']};")
        layout.addWidget(title)

        self._comp_metrics_table = QTableWidget()
        self._comp_metrics_table.setAlternatingRowColors(True)
        self._comp_metrics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_metrics_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._comp_metrics_table.verticalHeader().setVisible(False)
        self._comp_metrics_table.verticalHeader().setDefaultSectionSize(24)
        self._comp_metrics_table.setColumnCount(5)
        self._comp_metrics_table.setHorizontalHeaderLabels([
            '特征量', '轴', '实验组', '对照组', '衰减率(%)'
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

        return card

    def _create_stft_card(self) -> QFrame:
        """STFT 时频分析卡片"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("时频分析（STFT 时频谱）— 实验组 vs 对照组 Ay")
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
        import pandas as pd

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

        # ── 3. 频谱频段衰减: per-axis {Ax: {bands_atten}} → per-band {band: {attenuation_pct}} ──
        spectrum_raw = raw_results.get('spectrum', {})
        if spectrum_raw:
            bands = {}
            for axis_name, spec_data in spectrum_raw.items():
                if not isinstance(spec_data, dict):
                    continue
                bands_atten = spec_data.get('bands_atten', {})
                for band_name, att_val in bands_atten.items():
                    if band_name not in bands:
                        bands[band_name] = {'exp_energy': 0.0, 'ctrl_energy': 0.0, 'attenuation_pct': 0.0}
                    bands[band_name]['attenuation_pct'] = att_val
            # 计算平均相干性和总衰减
            coherences = []
            all_atten = []
            for spec_data in spectrum_raw.values():
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

        # ── 4. 综合指标: flat {exp_Ax_VDV} → nested {experimental: {VDV_X}} ──
        metrics_raw = raw_results.get('metrics', {})
        if metrics_raw:
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
                        if src_key in metrics_raw:
                            group_dict[dst_key] = float(metrics_raw[src_key]) if isinstance(metrics_raw[src_key], (int, float, np.floating)) else 0.0
                # Total
                for prefix, field in [('_Ax_RMS', 'RMS_res'), ('_total_VDV', 'VDV_total')]:
                    for m2_src, m2_dst in [('exp', 'exp'), ('ctrl', 'ctrl')]:
                        if m2_src == group_name:
                            src_k = f'{group_name}{prefix}'
                            if src_k in metrics_raw:
                                group_dict[field] = float(metrics_raw[src_k]) if isinstance(metrics_raw[src_k], (int, float, np.floating)) else 0.0
            # 衰减率
            attenuation = {}
            for key in set(experimental.keys()) | set(control.keys()):
                e_val = experimental.get(key, 0)
                c_val = control.get(key, 0)
                if isinstance(c_val, (int, float)) and abs(c_val) > 1e-9:
                    attenuation[f'{key}_pct'] = (1 - e_val / c_val) * 100
            normalized['comprehensive_metrics'] = {
                'experimental': experimental,
                'control': control,
                'attenuation': attenuation,
            }

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

    def _embed_figure(self, fig: Figure, container: QWidget):
        """将 matplotlib Figure 嵌入式渲染到容器中，自适应窗体宽度"""
        layout = container.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dpi = fig.get_dpi()
        orig_w, orig_h = fig.get_size_inches()

        viewport = self._scroll_area.viewport()
        if viewport is not None and viewport.width() > 50:
            max_px_w = viewport.width() - 30
        else:
            max_px_w = max(600, self.width() - 60)

        target_w_inches = min(orig_w, max_px_w / dpi)
        target_w_inches = max(4, target_w_inches)
        target_w_inches = min(target_w_inches, 12)
        target_h_inches = orig_h * (target_w_inches / orig_w)
        target_h_inches = min(target_h_inches, 10)

        fig.set_size_inches(target_w_inches, target_h_inches, forward=True)
        fig.tight_layout()

        canvas = FigureCanvas(fig)
        px_w = int(target_w_inches * dpi)
        px_h = int(target_h_inches * dpi)
        canvas.resize(px_w, px_h)

        canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        canvas.setMinimumHeight(px_h)
        canvas.setStyleSheet("background: white;")
        layout.addWidget(canvas)
        container.setVisible(True)

    def _populate_sliding_window_results(self, window_results: list):
        """填充滑动窗口表格（兼容 DataFrame 和 list[dict]）"""
        self._window_table.setRowCount(0)
        if window_results is None or len(window_results) == 0:
            self._window_summary_label.setText("无窗口分析数据")
            return

        # 统一转换为 list[dict] 格式
        try:
            import pandas as pd
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

    def _populate_comprehensive_metrics_results(self, comprehensive: dict):
        """填充统计特征表格（算子级输出，非注册考核指标）"""
        self._comp_metrics_table.setRowCount(0)
        exp_metrics = comprehensive.get('experimental', {})
        ctrl_metrics = comprehensive.get('control', {})
        attenuation = comprehensive.get('attenuation', {})

        key_metrics = [
            ('振动剂量值(总)', 'VDV_total', 'total'), ('振动剂量值(X)', 'VDV_X', 'X'), ('振动剂量值(Y)', 'VDV_Y', 'Y'), ('振动剂量值(Z)', 'VDV_Z', 'Z'),
            ('RMS加速度(合成)', 'RMS_res', 'total'), ('RMS加速度(X)', 'RMS_X', 'X'), ('RMS加速度(Y)', 'RMS_Y', 'Y'), ('RMS加速度(Z)', 'RMS_Z', 'Z'),
            ('峰值加速度(合成)', 'Peak_res', 'total'),
            ('峰值因数(X)', 'Crest_X', 'X'), ('峰值因数(Y)', 'Crest_Y', 'Y'), ('峰值因数(Z)', 'Crest_Z', 'Z'),
            ('偏度(X)', 'Skew_X', 'X'), ('偏度(Y)', 'Skew_Y', 'Y'), ('偏度(Z)', 'Skew_Z', 'Z'),
            ('峭度(X)', 'Kurt_X', 'X'), ('峭度(Y)', 'Kurt_Y', 'Y'), ('峭度(Z)', 'Kurt_Z', 'Z'),
            ('平均绝对值(X)', 'MAV_X', 'X'), ('平均绝对值(Y)', 'MAV_Y', 'Y'), ('平均绝对值(Z)', 'MAV_Z', 'Z'),
            ('冲击指数(X)', 'Impulse_X', 'X'), ('冲击指数(Y)', 'Impulse_Y', 'Y'), ('冲击指数(Z)', 'Impulse_Z', 'Z'),
        ]

        self._comp_metrics_table.setRowCount(len(key_metrics))
        for i, (display_name, data_key, axis) in enumerate(key_metrics):
            self._comp_metrics_table.setItem(i, 0, QTableWidgetItem(display_name))
            self._comp_metrics_table.setItem(i, 1, QTableWidgetItem(axis))
            self._comp_metrics_table.setItem(i, 2, QTableWidgetItem(str(exp_metrics.get(data_key, '-'))))
            self._comp_metrics_table.setItem(i, 3, QTableWidgetItem(str(ctrl_metrics.get(data_key, '-'))))
            att_key = f"{data_key}_pct"
            att_val = attenuation.get(att_key, '-')
            att_text = f"{att_val:.1f}%" if isinstance(att_val, (int, float)) else str(att_val)
            self._comp_metrics_table.setItem(i, 4, QTableWidgetItem(att_text))

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
                    import csv
                    import pandas as pd
                    normalized = self._normalize_timeseries_data(ts_result.get('results', {}))
                    windows = normalized.get('windows', [])
                    if isinstance(windows, pd.DataFrame):
                        windows = windows.to_dict('records')
                    if windows:
                        w = csv.DictWriter(f, fieldnames=list(windows[0].keys()))
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
            self._contrast_group.setVisible(False)
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

            if isinstance(profile, dict) and not profile.get('error'):
                mag = profile.get('magnitude') or {}
                if isinstance(mag, dict):
                    ovtv_vals.append(mag.get('OVTV', 0))
                freq = profile.get('frequency') or {}
                if isinstance(freq, dict):
                    db = freq.get('dominant_band', 'N/A')
                    dom_band_counts[db] = dom_band_counts.get(db, 0) + 1
                impact = profile.get('impact') or {}
                if isinstance(impact, dict):
                    cf_z_vals.append(impact.get('crest_Z', 0))
                iso = profile.get('iso_ref') or {}
                if isinstance(iso, dict):
                    iso_zones.append(iso.get('comfort_zone_cn', 'N/A'))

            if isinstance(ctrl_profile, dict) and not ctrl_profile.get('error'):
                mag = ctrl_profile.get('magnitude') or {}
                if isinstance(mag, dict):
                    ctrl_ovtv_vals.append(mag.get('OVTV', 0))
                freq = ctrl_profile.get('frequency') or {}
                if isinstance(freq, dict):
                    db = freq.get('dominant_band', 'N/A')
                    ctrl_dom_band_counts[db] = ctrl_dom_band_counts.get(db, 0) + 1
                impact = ctrl_profile.get('impact') or {}
                if isinstance(impact, dict):
                    ctrl_cf_z_vals.append(impact.get('crest_Z', 0))
                iso = ctrl_profile.get('iso_ref') or {}
                if isinstance(iso, dict):
                    ctrl_iso_zones.append(iso.get('comfort_zone_cn', 'N/A'))

        has_ctrl = bool(ctrl_ovtv_vals)

        # --- OVTV 实验 vs 对照 ---
        if ovtv_vals:
            avg_ovtv = np.mean(ovtv_vals)
            if has_ctrl:
                avg_ctrl_ovtv = np.mean(ctrl_ovtv_vals)
                delta_pct = (avg_ovtv - avg_ctrl_ovtv) / max(abs(avg_ctrl_ovtv), 0.001) * 100
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
                delta_cf = (avg_cf - avg_ctrl_cf) / max(abs(avg_ctrl_cf), 0.001) * 100
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
            from collections import Counter
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

        selected_metrics = self._get_selected_metrics()
        if not selected_metrics:
            QMessageBox.warning(self, "错误", "请至少选择一个评测指标")
            return

        selected_locations = self._get_selected_locations()
        if not selected_locations:
            QMessageBox.warning(self, "错误", "请至少选择一个评测位置")
            return

        preprocess_level = self._preprocess_combo.currentData()

        # ── 清除旧的行为事件和时间轴，避免不同数据集间事件串扰 ──
        self._behavior_events_for_timeline = []
        self._clear_timeline_widgets()
        self._show_timeline_empty()

        self._analyze_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._browse_btn.setEnabled(False)
        self._empty_guide.setVisible(False)
        self._report_preview.clear()
        self._report_preview.setPlaceholderText("分析完成后此处将展示详细报告内容...")
        self._export_json_btn.setEnabled(False)
        self._export_md_btn.setEnabled(False)
        self._export_csv_btn.setEnabled(False)
        self._export_pdf_btn.setEnabled(False)
        self._overview_group.setVisible(False)
        self._profile_group.setVisible(True)
        self._contrast_group.setVisible(False)
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
        self._auto_generate_charts_if_ready(report)
        self._populate_results_table(report)
        md_text = self._report_generator.export_to_markdown(report)
        self._report_preview.setMarkdown(md_text)
        self._update_overview_dashboard(report)
        self._populate_profile_visualization(report)
        try:
            self._populate_contrast_profile(report)
        except Exception as e:
            self.logger.warning(f"对比基线卡片填充失败: {e}")
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
        if behavior_events:
            self.set_behavior_events_for_timeline(behavior_events, duration_s)
        else:
            # ── 离线文件模式下无行为事件时，确保时间轴已清空 ──
            self._behavior_events_for_timeline = []
            self._clear_timeline_widgets()
            self._show_timeline_empty()

        self._fill_indicator_comparison_data(report)
        self._populate_contrast_data_table(report)
        # ── 高级图表已提前调度，此处仅置基础分组可见 ──
        self._overview_group.setVisible(True)
        self._profile_group.setVisible(True)
        self._contrast_group.setVisible(True)
        self._output_tab_widget.setVisible(True)

        # ---- 全时域评测结果填充 ----
        full_ts = report.get('_full_timeseries')
        if full_ts and isinstance(full_ts, dict) and (full_ts.get('output_dir') or full_ts.get('results')):
            self._current_timeseries_result = full_ts
            # 填充表格数据（先归一化数据结构，使评估器和UI字段名对齐）
            normalized = self._normalize_timeseries_data(full_ts.get('results', {}))
            if full_ts.get('results'):
                self._populate_sliding_window_results(normalized.get('windows', []))
                self._populate_statistics_results(normalized.get('statistics', {}))
                self._populate_band_attenuation_results(normalized.get('spectrum', {}))
                self._populate_comprehensive_metrics_results(normalized.get('comprehensive_metrics', {}))
            # 生成事件概览图（fig2_events）
            overview_data = report.get('_overview_data')
            ts_events = full_ts.get('events', [])
            if overview_data and ts_events:
                adapted_ov = self._adapt_chart_overview_data(overview_data)
                fig = self._generate_events_overview_chart(adapted_ov, ts_events)
                if fig:
                    self._embed_figure(fig, self._events_overview_chart)
                else:
                    self._events_overview_chart.setVisible(False)
            else:
                self._events_overview_chart.setVisible(False)
            # 生成频域分析图（fig3_spectrum）
            spectrum_data = full_ts.get('results', {}).get('spectrum', {})
            if spectrum_data:
                adapted_spec = self._adapt_chart_spectrum_data(spectrum_data)
                fig = self._generate_spectrum_overview_chart(adapted_spec)
                if fig:
                    self._embed_figure(fig, self._spectrum_overview_chart)
                else:
                    self._spectrum_overview_chart.setVisible(False)
            else:
                self._spectrum_overview_chart.setVisible(False)
            # 生成 STFT 时频图（fig4_stft）
            stft_data = full_ts.get('results', {}).get('stft', {})
            if stft_data:
                adapted_stft = self._adapt_chart_stft_data(stft_data)
                fig = self._generate_stft_overview_chart(adapted_stft)
                if fig:
                    self._embed_figure(fig, self._stft_overview_chart)
                else:
                    self._stft_overview_chart.setVisible(False)
            else:
                self._stft_overview_chart.setVisible(False)
            # 生成统计分布与箱线图（fig5_statistics）
            if overview_data:
                adapted_ov5 = self._adapt_chart_overview_data(overview_data)
                fig = self._generate_statistics_distribution_chart(adapted_ov5)
                if fig:
                    self._embed_figure(fig, self._stats_distribution_chart)
                else:
                    self._stats_distribution_chart.setVisible(False)
            else:
                self._stats_distribution_chart.setVisible(False)
            # 生成全频段衰减雷达图（fig6_band_radar）
            if spectrum_data:
                adapted_spec6 = self._adapt_chart_spectrum_data(spectrum_data)
                fig = self._generate_band_radar_chart(adapted_spec6)
                if fig:
                    self._embed_figure(fig, self._band_radar_chart)
                else:
                    self._band_radar_chart.setVisible(False)
            else:
                self._band_radar_chart.setVisible(False)
            self._fulltimeseries_group.setVisible(True)
            self._statistics_group.setVisible(True)
            self._spectrum_group.setVisible(True)
            self._export_window_csv_btn.setEnabled(True)
        else:
            self._fulltimeseries_group.setVisible(False)
            self._statistics_group.setVisible(False)
            self._spectrum_group.setVisible(False)
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
        QTimer.singleShot(50, self._constrain_content_width)

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
        self._export_pdf_btn.setEnabled(True)

    def _populate_results_table(self, report: Dict):
        self._current_report = report
        self._results_loc_filter.blockSignals(True)
        self._results_loc_filter.setCurrentIndex(0)
        self._results_loc_filter.blockSignals(False)
        self._do_populate_results_table()

    def _do_populate_results_table(self):
        report = self._current_report
        if not report:
            return

        locations = report.get('locations', {})
        selected_loc = self._results_loc_filter.currentData()

        all_metric_ids = set()
        for loc_data in locations.values():
            if isinstance(loc_data, dict):
                all_metric_ids.update(loc_data.get('metrics', {}).keys())

        grouped = {}
        for m_id in all_metric_ids:
            meta = self._registry.get_indicator_meta(m_id)
            raw_dim = meta.evaluation_dimension if meta else '通用-基础'
            dim = DIMENSION_MAP.get(raw_dim, '通用-基础')
            grouped.setdefault(dim, []).append(m_id)
        for indicators in grouped.values():
            indicators.sort()

        rows = []
        for dim in sorted(grouped.keys(), key=lambda d: DIMENSION_ORDER.get(d, 99)):
            for m_id in grouped[dim]:
                rows.append((m_id, dim))

        self._results_table.setRowCount(len(rows))
        self._results_row_map = {}

        for row, (m_id, dim) in enumerate(rows):
            meta = self._registry.get_indicator_meta(m_id)
            threshold = self._registry.get_threshold(m_id)

            code_item = QTableWidgetItem(m_id)
            code_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 0, code_item)

            name_text = meta.display_name_cn if meta else m_id
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

            dim_item = QTableWidgetItem(dim)
            dim_item.setTextAlignment(Qt.AlignCenter)
            dim_color = DIM_COLORS.get(dim, '#95A5A6')
            dim_item.setForeground(QColor(dim_color))
            self._results_table.setItem(row, 2, dim_item)

            unit_text = meta.unit if meta and meta.unit != '-' else ''
            unit_item = QTableWidgetItem(unit_text)
            unit_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 3, unit_item)

            # ----- 获取实验组 & 对照组值 -----
            exp_val = None
            ctrl_val = None

            if selected_loc == 'all':
                os_data = (report.get('overall_summary') or {}).get(m_id, {})
                exp_val = os_data.get('mean') if isinstance(os_data, dict) else None
                ctrl_vals_all = []
                for loc_d in locations.values():
                    if isinstance(loc_d, dict):
                        ctr = (loc_d.get('contrast') or {}).get('magnitude', {})
                        entry = ctr.get(m_id)
                        if isinstance(entry, dict):
                            cv = entry.get('control', entry.get('ctrl'))
                            if cv is not None:
                                ctrl_vals_all.append(cv)
                if ctrl_vals_all:
                    import statistics as _stat
                    ctrl_val = _stat.mean(ctrl_vals_all)
            else:
                loc_data = locations.get(selected_loc) or {}
                if isinstance(loc_data, dict):
                    prof = loc_data.get('profile') or {}
                    mag = prof.get('magnitude') or {}
                    exp_val = mag.get(m_id)
                    ctr = (loc_data.get('contrast') or {}).get('magnitude', {})
                    entry = ctr.get(m_id)
                    if isinstance(entry, dict):
                        ctrl_val = entry.get('control', entry.get('ctrl'))

            # 列4: 实验组
            if exp_val is not None and isinstance(exp_val, (int, float)):
                exp_item = QTableWidgetItem(f"{exp_val:.4f}")
            else:
                exp_item = QTableWidgetItem("--")
                exp_item.setForeground(QColor('#CCC'))
            exp_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 4, exp_item)

            # 列5: 对照组
            if ctrl_val is not None and isinstance(ctrl_val, (int, float)):
                ctrl_item = QTableWidgetItem(f"{ctrl_val:.4f}")
            else:
                ctrl_item = QTableWidgetItem("--")
                ctrl_item.setForeground(QColor('#CCC'))
            ctrl_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 5, ctrl_item)

            # 列6: 绝对差
            if exp_val is not None and ctrl_val is not None:
                diff_val = exp_val - ctrl_val
                diff_item = QTableWidgetItem(f"{diff_val:+.4f}")
            else:
                diff_item = QTableWidgetItem("--")
                diff_item.setForeground(QColor('#CCC'))
            diff_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 6, diff_item)

            # 列7: 变化率%
            if exp_val is not None and ctrl_val is not None and ctrl_val != 0:
                delta_pct = (exp_val - ctrl_val) / abs(ctrl_val) * 100
                pct_item = QTableWidgetItem(f"{delta_pct:+.1f}%")
                lower_better = meta.direction.name in ('LOWER_IS_BETTER', 'LOWER_BETTER') if meta else True
                is_better = delta_pct < 0 if lower_better else delta_pct > 0
                pct_item.setForeground(QColor('#27AE60') if is_better else QColor('#E74C3C'))
            else:
                pct_item = QTableWidgetItem("--")
                pct_item.setForeground(QColor('#CCC'))
            pct_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 7, pct_item)

            # 列8: 状态（基于实验组值判断）
            primary_val = exp_val
            if primary_val is not None and isinstance(primary_val, (int, float)):
                pass_thr = meta.threshold_pass if meta else (threshold.get('pass') if threshold else None)
                warn_thr = (threshold.get('warn') if threshold else None)
                status_text = '-'; status_color = LC['text_muted']
                if pass_thr is not None:
                    try:
                        pass_v = float(pass_thr)
                        warn_v = float(warn_thr) if warn_thr is not None else None
                        direction = meta.direction.name if meta else 'LOWER_IS_BETTER'
                        if direction in ('LOWER_IS_BETTER', 'LOWER_BETTER'):
                            if primary_val <= pass_v:
                                status_text = '✓ 通过'; status_color = '#27AE60'
                            elif warn_v is not None and primary_val <= warn_v:
                                status_text = '⚠ 警告'; status_color = '#F39C12'
                            else:
                                status_text = '✗ 超标'; status_color = '#E74C3C'
                        else:
                            if primary_val >= pass_v:
                                status_text = '✓ 通过'; status_color = '#27AE60'
                            elif warn_v is not None and primary_val >= warn_v:
                                status_text = '⚠ 警告'; status_color = '#F39C12'
                            else:
                                status_text = '✗ 超标'; status_color = '#E74C3C'
                    except (TypeError, ValueError):
                        pass
            else:
                status_text = '-'; status_color = LC['text_muted']
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor(status_color))
            font = QFont("Microsoft YaHei", 10)
            font.setBold(status_text.startswith('✗'))
            status_item.setFont(font)
            self._results_table.setItem(row, 8, status_item)

            # 列9: 通过阈值 (P2修复)
            threshold_text = ''
            if meta and meta.threshold_pass:
                threshold_text = meta.threshold_pass
            elif threshold and threshold.get('pass') is not None:
                threshold_text = str(threshold.get('pass'))
            threshold_item = QTableWidgetItem(threshold_text if threshold_text else '-')
            threshold_item.setTextAlignment(Qt.AlignCenter)
            if not threshold_text:
                threshold_item.setForeground(QColor('#CCC'))
            self._results_table.setItem(row, 9, threshold_item)

            # 列10: 适用位置
            loc_text = ', '.join(meta.applicable_locations) if meta and meta.applicable_locations else '-'
            locs_item = QTableWidgetItem(loc_text)
            locs_item.setTextAlignment(Qt.AlignCenter)
            self._results_table.setItem(row, 10, locs_item)

            self._results_row_map[row] = m_id
        self._results_loc_count.setText(f"{len(rows)} 个指标")

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

    def _on_export_pdf_clicked(self):
        if not self._current_report:
            QMessageBox.warning(self, "警告", "没有可导出的报告")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存PDF", "", "PDF (*.pdf)"
        )

        if not file_path:
            return

        try:
            from modules.evaluation_report.report_exporter import ReportExporter
            exporter = ReportExporter()
            result_path = exporter.export(self._current_report, format='pdf', filename=file_path)
            QMessageBox.information(self, "导出成功", f"报告已导出到:\n{result_path}")
            self._status_label.setText(f'报告已导出: {os.path.basename(result_path)}')
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _create_comparison_control_card(self) -> QFrame:
        """创建对照分析控制卡片"""
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        title = QLabel("⚖️ 对照分析控制")
        title.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {LC['text_primary']};"
        )
        layout.addWidget(title)

        layout.addSpacing(20)

        layout.addWidget(QLabel("实验组:"))
        self._exp_combo = QComboBox()
        self._exp_combo.addItem("当前数据（实验组）", "current_experimental")
        self._exp_combo.setMaximumWidth(180)
        layout.addWidget(self._exp_combo)

        layout.addSpacing(8)

        layout.addWidget(QLabel("对照组:"))
        self._ctrl_combo = QComboBox()
        self._ctrl_combo.addItem("当前数据（对照组）", "current_control")
        self._ctrl_combo.setMaximumWidth(180)
        layout.addWidget(self._ctrl_combo)

        layout.addSpacing(8)

        layout.addWidget(QLabel("查看位置:"))
        self._comp_location_combo = QComboBox()
        self._comp_location_combo.addItem("总体")
        locations = get_all_locations()
        for loc_id in locations:
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            self._comp_location_combo.addItem(loc_name, loc_id)
        self._comp_location_combo.setMaximumWidth(150)
        layout.addWidget(self._comp_location_combo)

        layout.addStretch()

        self._start_compare_btn = QPushButton("🔄 开始对比")
        self._start_compare_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {LC['accent']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {LC['accent_hover']};
            }}
            """
        )
        self._start_compare_btn.clicked.connect(self._on_start_comparison)
        layout.addWidget(self._start_compare_btn)

        return card

    def _on_start_comparison(self):
        """开始对比 — 根据当前位置选择重新加载指标对照数据"""
        report = getattr(self, '_current_report', None)
        if report:
            self._fill_indicator_comparison_data(report)
            self._populate_contrast_data_table(report)
        else:
            self.logger.warning("指标对照: 无可用报告数据")

    def _create_indicator_comparison_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._indicator_comp_table = QTableWidget()
        self._indicator_comp_table.setAlternatingRowColors(True)
        self._indicator_comp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._indicator_comp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._indicator_comp_table.verticalHeader().setVisible(False)
        self._indicator_comp_table.verticalHeader().setDefaultSectionSize(24)
        self._indicator_comp_table.setColumnCount(10)
        self._indicator_comp_table.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "评测维度", "单位",
            "实验组", "对照组", "绝对差", "变化率(%)", "改进方向", "操作"
        ])
        self._indicator_comp_table.setStyleSheet(self._card_table_style())

        header = self._indicator_comp_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for i in range(3, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        self._indicator_comp_table.setColumnWidth(9, 52)

        self._populate_indicator_comparison_table()

        self._indicator_comp_table.cellClicked.connect(self._on_indicator_comp_cell_clicked)
        layout.addWidget(self._indicator_comp_table)
        return card

    # ═══════════════════════════════════════════════════════
    #  对比数据表填充（Phase C: 强制 exp/ctrl/diff 三列输出）
    # ═══════════════════════════════════════════════════════

    def _populate_contrast_data_table(self, report: Dict):
        """从分析报告中提取 exp/ctrl 对比数据，填充到对比数据表中。
        
        数据来源：report['locations'][loc_id]['contrast']['magnitude']
        每项指标包含 experimental / control / delta_pct 字段。
        """
        self._contrast_data = []  # 存储完整对比数据供过滤使用
        locations = report.get('locations', {})

        # 收集所有位置到过滤器
        self._contrast_loc_filter.blockSignals(True)
        current_loc = self._contrast_loc_filter.currentData()
        self._contrast_loc_filter.clear()
        self._contrast_loc_filter.addItem("全部位置", "all")
        loc_ids_with_data = []

        for loc_id, loc_data in locations.items():
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
            if magnitude:
                label_cn = loc_data.get('label_cn', loc_id)
                self._contrast_loc_filter.addItem(f"{label_cn} ({loc_id})", loc_id)
                loc_ids_with_data.append(loc_id)

        # 恢复之前选择的位置
        idx = self._contrast_loc_filter.findData(current_loc)
        if idx >= 0:
            self._contrast_loc_filter.setCurrentIndex(idx)
        self._contrast_loc_filter.blockSignals(False)

        # 提取所有对比数据
        all_rows = []
        for loc_id, loc_data in locations.items():
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
            if not magnitude:
                continue

            label_cn = loc_data.get('label_cn', loc_id)

            for metric_id, metric_data in magnitude.items():
                if not isinstance(metric_data, dict):
                    continue

                exp_val = metric_data.get('experimental', metric_data.get('exp', None))
                ctrl_val = metric_data.get('control', metric_data.get('ctrl', None))
                delta_pct = metric_data.get('delta_pct', None)

                if exp_val is None and ctrl_val is None:
                    continue

                # 获取指标元数据
                meta = self._registry.get_indicator_meta(metric_id)
                raw_dim = meta.evaluation_dimension if meta else '通用-基础'
                dim = DIMENSION_MAP.get(raw_dim, '通用-基础')
                unit = meta.unit if meta and meta.unit != '-' else ''
                dim_order = DIMENSION_ORDER.get(dim, 99)

                # 计算评级
                grade = '-'
                grade_color = LC['text_muted']
                if delta_pct is not None:
                    delta = float(delta_pct)
                    direction = meta.direction.name if meta else 'LOWER_BETTER'
                    if direction in ('HIGHER_BETTER',):
                        if delta >= 35:
                            grade = '优秀'
                            grade_color = '#27AE60'
                        elif delta >= 20:
                            grade = '良好'
                            grade_color = '#4A90D9'
                        elif delta >= 0:
                            grade = '一般'
                            grade_color = '#F39C12'
                        else:
                            grade = '退步'
                            grade_color = '#E74C3C'
                    else:
                        if delta <= -35:
                            grade = '优秀'
                            grade_color = '#27AE60'
                        elif delta <= -20:
                            grade = '良好'
                            grade_color = '#4A90D9'
                        elif delta <= 0:
                            grade = '一般'
                            grade_color = '#F39C12'
                        else:
                            grade = '退步'
                            grade_color = '#E74C3C'

                all_rows.append({
                    'loc_id': loc_id,
                    'label_cn': label_cn,
                    'metric_id': metric_id,
                    'dim_order': dim_order,
                    'grade': grade,
                    'grade_color': grade_color,
                })

        self._contrast_data = all_rows
        self._do_render_contrast_data_table()

    def _do_render_contrast_data_table(self):
        """根据当前位置过滤条件渲染对比数据表"""
        selected_loc = self._contrast_loc_filter.currentData()
        report = self._current_report
        if not report:
            return

        locations = report.get('locations', {})

        # 过滤数据
        filtered = []
        for row_data in self._contrast_data:
            if selected_loc != 'all' and row_data['loc_id'] != selected_loc:
                continue
            filtered.append(row_data)

        # 按维度排序
        filtered.sort(key=lambda r: (r['dim_order'], r['metric_id']))

        self._contrast_data_table.setRowCount(len(filtered))

        total_improved = 0
        total_degraded = 0
        total_items = len(filtered)

        for row, data in enumerate(filtered):
            loc_id = data['loc_id']
            metric_id = data['metric_id']
            label_cn = data['label_cn']

            loc_data = locations.get(loc_id, {})
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
            metric_data = magnitude.get(metric_id, {})

            exp_val = metric_data.get('experimental', metric_data.get('exp', None))
            ctrl_val = metric_data.get('control', metric_data.get('ctrl', None))
            delta_pct = metric_data.get('delta_pct', None)

            meta = self._registry.get_indicator_meta(metric_id)
            name_cn = meta.display_name_cn if meta else metric_id
            unit = meta.unit if meta and meta.unit != '-' else ''

            # 指标ID
            code_item = QTableWidgetItem(metric_id)
            code_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 0, code_item)

            # 指标名称
            name_item = QTableWidgetItem(name_cn)
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setToolTip(
                f"{meta.display_name_cn} ({meta.display_name_en})\n"
                f"单位: {meta.unit}\n"
                f"维度: {meta.evaluation_dimension}"
            ) if meta else None
            self._contrast_data_table.setItem(row, 1, name_item)

            # 位置
            loc_item = QTableWidgetItem(label_cn)
            loc_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 2, loc_item)

            # 实验组值
            if exp_val is not None and isinstance(exp_val, (int, float)):
                exp_item = QTableWidgetItem(f"{exp_val:.3f}")
                exp_item.setForeground(QColor('#27AE60'))
            else:
                exp_item = QTableWidgetItem('--')
                exp_item.setForeground(QColor('#CCC'))
            exp_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 3, exp_item)

            # 对照组值
            if ctrl_val is not None and isinstance(ctrl_val, (int, float)):
                ctrl_item = QTableWidgetItem(f"{ctrl_val:.3f}")
                ctrl_item.setForeground(QColor('#F39C12'))
            else:
                ctrl_item = QTableWidgetItem('--')
                ctrl_item.setForeground(QColor('#CCC'))
            ctrl_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 4, ctrl_item)

            # 差值%
            if delta_pct is not None:
                delta = float(delta_pct)
                if delta > 0:
                    delta_str = f"+{delta:.1f}%"
                else:
                    delta_str = f"{delta:.1f}%"

                direction = meta.direction.name if meta else 'LOWER_IS_BETTER'
                is_better = delta < 0 if direction in ('LOWER_IS_BETTER', 'LOWER_BETTER') else delta > 0

                delta_item = QTableWidgetItem(delta_str)
                if abs(delta) > 40:
                    delta_item.setForeground(QColor('#27AE60' if is_better else '#E74C3C'))
                elif abs(delta) > 15:
                    delta_item.setForeground(QColor('#F39C12'))
                else:
                    delta_item.setForeground(QColor('#27AE60' if is_better else '#95A5A6'))

                if is_better:
                    total_improved += 1
                else:
                    total_degraded += 1
            else:
                delta_item = QTableWidgetItem('--')
                delta_item.setForeground(QColor('#CCC'))
            delta_item.setTextAlignment(Qt.AlignCenter)
            font = QFont("Microsoft YaHei", 10)
            font.setBold(True)
            delta_item.setFont(font)
            self._contrast_data_table.setItem(row, 5, delta_item)

            # 评级
            grade_item = QTableWidgetItem(data['grade'])
            grade_item.setTextAlignment(Qt.AlignCenter)
            grade_item.setForeground(QColor(data['grade_color']))
            self._contrast_data_table.setItem(row, 6, grade_item)

            # ── 裁决 (专家级衰减判定) ──
            if delta_pct is not None:
                delta = float(delta_pct)
                # 根据 direction 反转符号
                direction = meta.direction.name if meta else 'LOWER_BETTER'
                if direction in ('HIGHER_BETTER',):
                    atten = delta  # 正值=改善
                else:
                    atten = -delta  # 负值=改善，取反
                verdict_str = f"{verdict_icon(atten)} {verdict_text(atten)}"
            else:
                verdict_str = '--'
            verdict_item = QTableWidgetItem(verdict_str)
            verdict_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 7, verdict_item)

            # 通过阈值 (P2修复)
            threshold_text = meta.threshold_pass if meta and meta.threshold_pass else '-'
            threshold_col_item = QTableWidgetItem(threshold_text)
            threshold_col_item.setTextAlignment(Qt.AlignCenter)
            if threshold_text == '-':
                threshold_col_item.setForeground(QColor('#CCC'))
            self._contrast_data_table.setItem(row, 8, threshold_col_item)

            # 改进方向
            if delta_pct is not None:
                delta = float(delta_pct)
                direction = meta.direction.name if meta else 'LOWER_BETTER'
                if direction in ('HIGHER_BETTER',):
                    improved = delta > 0
                else:
                    improved = delta < 0

                if improved:
                    improve_item = QTableWidgetItem("✅ 改善")
                    improve_item.setForeground(QColor('#27AE60'))
                else:
                    improve_item = QTableWidgetItem("⚠️ 需优化")
                    improve_item.setForeground(QColor('#E74C3C'))
            else:
                improve_item = QTableWidgetItem("--")
                improve_item.setForeground(QColor('#CCC'))
            improve_item.setTextAlignment(Qt.AlignCenter)
            self._contrast_data_table.setItem(row, 9, improve_item)

        # 汇总统计（保留 _populate_contrast_profile 已有的概要文本）
        if total_items > 0:
            improve_rate = total_improved / total_items * 100
            summary = (
                f"共 {total_items} 项指标  |  "
                f"改善: {total_improved} 项 ({improve_rate:.0f}%)  |  "
                f"退步: {total_degraded} 项 ({(total_degraded/total_items*100):.0f}%)"
            )
            existing = self._contrast_tab_summary_label.text()
            if existing:
                self._contrast_tab_summary_label.setText(existing + "  |  " + summary)
            else:
                self._contrast_tab_summary_label.setText(summary)
            if improve_rate >= 70:
                self._contrast_tab_summary_label.setStyleSheet(
                    f"color: #27AE60; font-size: 11px; font-weight: 600; padding: 4px 8px;"
                    f"background: #F0FFF4; border-radius: 4px;"
                )
            elif improve_rate >= 40:
                self._contrast_tab_summary_label.setStyleSheet(
                    f"color: #F39C12; font-size: 11px; font-weight: 600; padding: 4px 8px;"
                    f"background: #FFF8E1; border-radius: 4px;"
                )
            else:
                self._contrast_tab_summary_label.setStyleSheet(
                    f"color: #E74C3C; font-size: 11px; font-weight: 600; padding: 4px 8px;"
                    f"background: #FDEDEC; border-radius: 4px;"
                )
        else:
            self._contrast_tab_summary_label.setText("暂无对比数据 — 请确保数据包含实验组和对照组")
            self._contrast_tab_summary_label.setStyleSheet(
                f"color: {LC['text_muted']}; font-size: 11px; padding: 4px 8px;"
            )

    def _on_contrast_loc_filter_changed(self):
        """当对比数据表的位置过滤器改变时重新渲染"""
        self._do_render_contrast_data_table()

    def _populate_indicator_comparison_table(self):
        grouped = {}
        for code, meta in self._registry.indicators.items():
            raw_dim = meta.evaluation_dimension
            dim = DIMENSION_MAP.get(raw_dim, '通用-基础')
            grouped.setdefault(dim, []).append(meta)
        for indicators in grouped.values():
            indicators.sort(key=lambda m: m.code)

        rows = []
        for dim in sorted(grouped.keys(), key=lambda d: DIMENSION_ORDER.get(d, 99)):
            for meta in grouped[dim]:
                rows.append(meta)

        self._indicator_comp_table.setRowCount(len(rows))
        self._indicator_row_map = {}

        for row, meta in enumerate(rows):
            code_item = QTableWidgetItem(meta.code)
            code_item.setTextAlignment(Qt.AlignCenter)
            self._indicator_comp_table.setItem(row, 0, code_item)

            name_item = QTableWidgetItem(meta.display_name_cn)
            name_item.setTextAlignment(Qt.AlignCenter)
            tip_lines = [
                f"{meta.display_name_cn} ({meta.display_name_en})",
                f"单位: {meta.unit}",
                f"公式: {meta.formula_text}",
                f"管线: {' → '.join(meta.operator_pipeline)}",
                f"适用位置: {', '.join(meta.applicable_locations)}",
            ]
            if meta.standard_refs:
                tip_lines.append(f"标准: {', '.join([str(r) for r in meta.standard_refs[:3]])}")
            if meta.threshold_pass:
                tip_lines.append(f"通过阈值: {meta.threshold_pass}")
            name_item.setToolTip('\n'.join(tip_lines))
            self._indicator_comp_table.setItem(row, 1, name_item)

            dim_ui = DIMENSION_MAP.get(meta.evaluation_dimension, '通用-基础')
            dim_item = QTableWidgetItem(dim_ui)
            dim_item.setTextAlignment(Qt.AlignCenter)
            dim_color = DIM_COLORS.get(dim_ui, '#95A5A6')
            dim_item.setForeground(QColor(dim_color))
            self._indicator_comp_table.setItem(row, 2, dim_item)

            unit_item = QTableWidgetItem(meta.unit if meta.unit != '-' else '')
            unit_item.setTextAlignment(Qt.AlignCenter)
            self._indicator_comp_table.setItem(row, 3, unit_item)

            for c in range(4, 9):
                self._indicator_comp_table.setItem(row, c, QTableWidgetItem("--"))

            detail_btn = QPushButton("详情")
            detail_btn.setFixedSize(45, 24)
            detail_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {LC['text_accent']};
                    border: 1px solid {LC['border_default']}; border-radius: 3px;
                    font-size: 9px; padding: 1px 2px;
                }}
                QPushButton:hover {{
                    background: {LC['accent_light']}; border-color: {LC['accent']};
                }}
            """)
            code = meta.code
            detail_btn.clicked.connect(
                lambda checked=False, c=code: self._open_comparison_indicator_detail(c)
            )
            self._indicator_comp_table.setCellWidget(row, 9, detail_btn)

            self._indicator_row_map[meta.code] = row

    def _fill_indicator_comparison_data(self, report: dict):
        """用 report 中的对比数据填充 _indicator_comp_table 的实验组/对照组列
        
        策略:
          - "总体" → 聚合全部位置取均值
          - 具体位置 → 读取该位置的 contrast.magnitude
        """
        locations = report.get('locations', {}) if isinstance(report, dict) else {}
        if not locations:
            return

        # 更新位置下拉框，添加 report 中实际存在的位置
        combo = getattr(self, '_comp_location_combo', None)
        if combo is not None:
            combo.blockSignals(True)
            current_data = combo.currentData()
            combo.clear()
            combo.addItem("总体", "__aggregate__")
            for loc_id, loc_data in locations.items():
                if isinstance(loc_data, dict):
                    label = loc_data.get('label_cn', loc_data.get('label', loc_id))
                    combo.addItem(f"{label}", loc_id)
            idx = combo.findData(current_data)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        selected_loc = combo.currentData() if combo is not None else None
        if not selected_loc:
            return

        # ── 收集数据 ──
        if selected_loc == '__aggregate__':
            agg_exp: Dict[str, list] = {}
            agg_ctrl: Dict[str, list] = {}
            agg_delta: Dict[str, list] = {}
            for loc_id, loc_data in locations.items():
                contrast = (loc_data.get('contrast') or {}) if isinstance(loc_data, dict) else {}
                magnitude = contrast.get('magnitude') or {}
                if not isinstance(magnitude, dict):
                    continue
                for code, mag_entry in magnitude.items():
                    if not isinstance(mag_entry, dict):
                        continue
                    exp_val = mag_entry.get('experimental', mag_entry.get('exp'))
                    ctrl_val = mag_entry.get('control', mag_entry.get('ctrl'))
                    delta_pct = mag_entry.get('delta_pct')
                    if exp_val is not None:
                        agg_exp.setdefault(code, []).append(float(exp_val))
                    if ctrl_val is not None:
                        agg_ctrl.setdefault(code, []).append(float(ctrl_val))
                    if delta_pct is not None:
                        agg_delta.setdefault(code, []).append(float(delta_pct))

            for code, row in self._indicator_row_map.items():
                meta = self._registry.get_indicator_meta(code) if self._registry else None
                exp_val = np.mean(agg_exp.get(code, [])) if agg_exp.get(code) else None
                ctrl_val = np.mean(agg_ctrl.get(code, [])) if agg_ctrl.get(code) else None
                delta_pct = np.mean(agg_delta.get(code, [])) if agg_delta.get(code) else None
                self._write_indicator_comp_row(row, meta, exp_val, ctrl_val, delta_pct)
        else:
            loc_data = (locations.get(selected_loc) or {})
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude') or {}
            for code, row in self._indicator_row_map.items():
                meta = self._registry.get_indicator_meta(code) if self._registry else None
                mag_entry = magnitude.get(code)
                if not isinstance(mag_entry, dict):
                    self._write_indicator_comp_row(row, meta, None, None, None)
                    continue
                exp_val = mag_entry.get('experimental', mag_entry.get('exp'))
                ctrl_val = mag_entry.get('control', mag_entry.get('ctrl'))
                delta_pct = mag_entry.get('delta_pct')
                self._write_indicator_comp_row(row, meta, exp_val, ctrl_val, delta_pct)

    def _write_indicator_comp_row(self, row: int, meta, exp_val, ctrl_val, delta_pct):
        """向指标对照表的指定行写入实验组/对照组/差值数据"""
        abs_diff = (exp_val - ctrl_val) if (exp_val is not None and ctrl_val is not None) else None

        exp_item = QTableWidgetItem(f"{exp_val:.4f}" if exp_val is not None else "--")
        exp_item.setTextAlignment(Qt.AlignCenter)
        self._indicator_comp_table.setItem(row, 4, exp_item)

        ctrl_item = QTableWidgetItem(f"{ctrl_val:.4f}" if ctrl_val is not None else "--")
        ctrl_item.setTextAlignment(Qt.AlignCenter)
        self._indicator_comp_table.setItem(row, 5, ctrl_item)

        diff_item = QTableWidgetItem(f"{abs_diff:+.4f}" if abs_diff is not None else "--")
        diff_item.setTextAlignment(Qt.AlignCenter)
        self._indicator_comp_table.setItem(row, 6, diff_item)

        pct_item = QTableWidgetItem(f"{delta_pct:+.1f}%" if delta_pct is not None else "--")
        pct_item.setTextAlignment(Qt.AlignCenter)
        if delta_pct is not None and meta:
            improve = meta.direction.name in ('LOWER_IS_BETTER', 'LOWER_BETTER') if meta else True
            is_better = delta_pct < 0 if improve else delta_pct > 0
            pct_item.setForeground(QColor('#27AE60') if is_better else QColor('#E74C3C'))
        self._indicator_comp_table.setItem(row, 7, pct_item)

        if delta_pct is not None and meta:
            lower_better = meta.direction.name in ('LOWER_IS_BETTER', 'LOWER_BETTER')
            dir_text = "↓改善" if ((delta_pct < 0 and lower_better) or (delta_pct > 0 and not lower_better)) else "↑退步"
            dir_color = '#27AE60' if "改善" in dir_text else '#E74C3C'
        else:
            dir_text = "--"
            dir_color = LC['text_muted']
        dir_item = QTableWidgetItem(dir_text)
        dir_item.setTextAlignment(Qt.AlignCenter)
        dir_item.setForeground(QColor(dir_color))
        self._indicator_comp_table.setItem(row, 8, dir_item)

    def _on_indicator_comp_cell_clicked(self, row: int, col: int):
        if col != 0 and col != 1:
            return
        code_item = self._indicator_comp_table.item(row, 0)
        if not code_item:
            return
        self._open_comparison_indicator_detail(code_item.text())

    def _open_comparison_indicator_detail(self, indicator_code: str):
        dialog = IndicatorDetailDialog(indicator_code, self._registry, self)
        dialog.exec()

    def set_trip_summary(self, trip_summary):
        self._trip_summary = trip_summary
        self._update_timeline()

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
            # ── 清除 SQLite 缓存模式遗留的行为事件和时间轴 ──
            self._behavior_events_for_timeline = []
            self._clear_timeline_widgets()
            self._show_timeline_empty()

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
        from PySide6.QtCore import QTimer
        self._charts_pending_report = report
        QTimer.singleShot(800, self._generate_advanced_charts_from_pending)

    def _on_generate_charts(self):
        """用户手动点击「生成全部图表」按钮"""
        report = getattr(self, '_current_report', None)
        if report:
            self._generate_advanced_charts(report)
        else:
            self.logger.warning("无可用报告，请先完成分析")

    def _generate_advanced_charts_from_pending(self):
        """从待处理报告生成图表"""
        report = getattr(self, '_charts_pending_report', None)
        if report:
            self._generate_advanced_charts(report)

    def _create_chart_canvas(self, fig, min_height=300):
        """创建带尺寸约束的图表canvas"""
        dpi = fig.get_dpi()
        orig_w, orig_h = fig.get_size_inches()

        viewport = self._scroll_area.viewport()
        if viewport is not None and viewport.width() > 50:
            max_px_w = viewport.width() - 40
        else:
            max_px_w = max(600, self.width() - 80)

        target_w_inches = min(orig_w, max_px_w / dpi)
        target_w_inches = max(4, target_w_inches)
        target_w_inches = min(target_w_inches, 12)
        target_h_inches = orig_h * (target_w_inches / orig_w)
        target_h_inches = min(target_h_inches, 10)
        target_h_inches = max(target_h_inches, min_height / dpi)

        fig.set_size_inches(target_w_inches, target_h_inches, forward=True)
        fig.tight_layout()

        canvas = FigureCanvas(fig)
        px_w = int(target_w_inches * dpi)
        px_h = int(target_h_inches * dpi)
        canvas.resize(px_w, px_h)

        canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        canvas.setMinimumHeight(px_h)
        canvas.setStyleSheet("background: white;")

        return canvas

    def _create_chart_placeholder(self, title: str, key: str, group_key: str, min_height: int = 300):
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.setMinimumWidth(0)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; "
            f"padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};"
        )
        card_layout.addWidget(title_label)

        placeholder = QLabel("等待数据加载...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setMinimumHeight(min_height)
        placeholder.setStyleSheet(
            f"color: {LC['text_muted']}; font-size: 13px; "
            f"background: {LC['bg_input']}; border-radius: 4px;"
        )
        card_layout.addWidget(placeholder)

        self._chart_slots[key] = {
            'card': card,
            'layout': card_layout,
            'placeholder': placeholder,
            'group': group_key,
            'title': title,
            'min_height': min_height,
            'filled': False,
        }

        group_layout = self._group_chart_layouts.get(group_key)
        if group_layout:
            group_layout.addWidget(card)

    def _fill_chart_slot(self, key: str, fig):
        slot = self._chart_slots.get(key)
        if not slot:
            return False
        canvas = self._create_chart_canvas(fig, min_height=slot['min_height'])
        old_widget = slot['placeholder']
        slot['layout'].replaceWidget(old_widget, canvas)
        old_widget.deleteLater()
        slot['placeholder'] = canvas
        slot['filled'] = True
        return True

    def _reset_chart_slots(self):
        for key, slot in self._chart_slots.items():
            if slot['filled']:
                old_widget = slot['placeholder']
                new_placeholder = QLabel("暂无数据")
                new_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                new_placeholder.setMinimumHeight(slot['min_height'])
                new_placeholder.setStyleSheet(
                    f"color: {LC['text_muted']}; font-size: 13px; "
                    f"background: {LC['bg_input']}; border-radius: 4px;"
                )
                slot['layout'].replaceWidget(old_widget, new_placeholder)
                old_widget.deleteLater()
                slot['placeholder'] = new_placeholder
                slot['filled'] = False
            else:
                slot['placeholder'].setText("暂无数据")

    def _clear_group_chart_layouts(self):
        self._reset_chart_slots()

    def _generate_advanced_charts(self, report: Dict):
        self._clear_group_chart_layouts()

        overview = report.get('_overview_data', {})
        channel_data_map = report.get('_channel_data_map', {})
        full_ts = report.get('_full_timeseries', {})
        ft_results = full_ts.get('results', {}) if isinstance(full_ts, dict) else {}
        self.logger.info(f"[图表诊断] _full_timeseries存在={isinstance(full_ts,dict) and bool(full_ts)}, "
                         f"results_keys={list(ft_results.keys()) if isinstance(ft_results,dict) else 'N/A'}, "
                         f"channel_data_map count={len(channel_data_map)}, "
                         f"overview_data keys={list(overview.keys()) if overview else 'EMPTY'}")

        charts_generated = 0
        failed_charts = []

        if channel_data_map:
            exp_imus = [k for k in channel_data_map.keys() if k.endswith('-1')]
            ctrl_imus = [k for k in channel_data_map.keys() if k.endswith('-2')]
            if len(exp_imus) >= 2 and len(ctrl_imus) >= 2:
                try:
                    fig = create_psd_comparison(channel_data_map, exp_imus, ctrl_imus, axis='Z')
                    if fig and self._fill_chart_slot("psd_comparison", fig):
                        charts_generated += 1
                    else:
                        failed_charts.append("PSD频谱对比(create_psd_comparison返回None)")
                except Exception as e:
                    self.logger.warning(f"PSD图表生成失败: {e}")
                    failed_charts.append(f"PSD频谱对比({e})")
            else:
                failed_charts.append(f"PSD频谱对比(exp={len(exp_imus)},ctrl={len(ctrl_imus)})")
        else:
            failed_charts.append("PSD频谱对比(无channel_data_map)")

        comparison = self._build_comparison_dict(report)
        if comparison:
            try:
                fig = create_attenuation_bar(comparison)
                if fig and self._fill_chart_slot("attenuation_bar", fig):
                    charts_generated += 1
                else:
                    failed_charts.append("衰减柱状图(create_attenuation_bar返回None)")
            except Exception as e:
                self.logger.warning(f"衰减柱状图生成失败: {e}")
                failed_charts.append(f"衰减柱状图({e})")

            try:
                fig = create_comparison_radar(comparison)
                if fig and self._fill_chart_slot("comparison_radar", fig):
                    charts_generated += 1
                else:
                    failed_charts.append("雷达对比图(create_comparison_radar返回None)")
            except Exception as e:
                self.logger.warning(f"雷达图生成失败: {e}")
                failed_charts.append(f"雷达对比图({e})")
        else:
            failed_charts.append("衰减柱状图(comparison为空)")
            failed_charts.append("雷达对比图(comparison为空)")

        exp_imus_1 = [k for k in channel_data_map.keys() if k.endswith('-1')]
        ctrl_imus_2 = [k for k in channel_data_map.keys() if k.endswith('-2')]
        if len(exp_imus_1) >= 1 and len(ctrl_imus_2) >= 1:
            try:
                fig = create_acceleration_waveform(channel_data_map, exp_imus_1[:3], ctrl_imus_2[:3])
                if fig and self._fill_chart_slot("acceleration_waveform", fig):
                    charts_generated += 1
                else:
                    failed_charts.append("加速度波形(create_acceleration_waveform返回None)")
            except Exception as e:
                self.logger.warning(f"加速度波形生成失败: {e}")
                failed_charts.append(f"加速度波形({e})")
        else:
            failed_charts.append(f"加速度波形(exp={len(exp_imus_1)},ctrl={len(ctrl_imus_2)})")

        head_exp = next((k for k in channel_data_map if '头部' in k and k.endswith('-1')), None)
        head_ctrl = next((k for k in channel_data_map if '头部' in k and k.endswith('-2')), None)
        if head_exp and head_ctrl:
            try:
                fig = create_srs_comparison(channel_data_map, head_exp, head_ctrl,
                                           location_name='头部眉心', axis='X')
                if fig and self._fill_chart_slot("srs_comparison", fig):
                    charts_generated += 1
                else:
                    failed_charts.append("SRS冲击响应谱(create_srs_comparison返回None)")
            except Exception as e:
                self.logger.warning(f"SRS图表生成失败: {e}")
                failed_charts.append(f"SRS冲击响应谱({e})")
        else:
            failed_charts.append(f"SRS冲击响应谱(头部exp={head_exp},头部ctrl={head_ctrl})")

        charts_generated += self._generate_viz_manager_charts(report)

        _group_map = {
            'overview': self._overview_group,
            'timeline_behavior': self._timeline_behavior_group,
            'contrast': self._contrast_group,
            'fulltimeseries': self._fulltimeseries_group,
            'spectrum': self._spectrum_group,
            'statistics': self._statistics_group,
        }
        for _key, _group in _group_map.items():
            _layout = self._group_chart_layouts.get(_key)
            if _layout and _layout.count() > 0:
                _group.setVisible(True)

        self.logger.info(f"图表生成完成: {charts_generated} 张")
        if failed_charts:
            self.logger.info(f"未生成图表: {len(failed_charts)}张 — {', '.join(failed_charts)}")
        QTimer.singleShot(50, self._constrain_content_width)

    def _create_chart_card(self, title: str, fig, min_height: int = 300):
        canvas = self._create_chart_canvas(fig, min_height=min_height)
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.setMinimumWidth(0)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {LC['text_primary']}; "
            f"padding-bottom: 4px; border-bottom: 1px solid {LC['border_light']};"
        )
        card_layout.addWidget(title_label)
        card_layout.addWidget(canvas)
        return card

    def _generate_viz_manager_charts(self, report: Dict) -> int:
        full_ts = report.get('_full_timeseries')
        overview_data = report.get('_overview_data')
        if not full_ts or not isinstance(full_ts, dict):
            return 0
        results = full_ts.get('results', {})
        if not results:
            return 0

        viz = VisualizationManager()
        generated = 0
        failed_viz = []

        events_list = full_ts.get('events', [])

        if overview_data and overview_data.get('timestamps') and events_list:
            try:
                timestamps = np.array(overview_data['timestamps'])
                speed_arr = np.array(overview_data['speed'])
                wheel_arr = np.array(overview_data['wheel'])
                if len(timestamps) > 10 and len(speed_arr) > 10:
                    sw = np.column_stack([timestamps, speed_arr, wheel_arr])
                    exp_head = np.column_stack([
                        timestamps,
                        np.array(overview_data.get('exp_ax', np.zeros_like(timestamps))),
                        np.array(overview_data.get('exp_ay', np.zeros_like(timestamps))),
                        np.array(overview_data.get('exp_az', np.zeros_like(timestamps))),
                    ])
                    ctrl_head = np.column_stack([
                        timestamps,
                        np.array(overview_data.get('ctrl_ax', np.zeros_like(timestamps))),
                        np.array(overview_data.get('ctrl_ay', np.zeros_like(timestamps))),
                        np.array(overview_data.get('ctrl_az', np.zeros_like(timestamps))),
                    ])
                    fig = viz.plot_overview(sw, exp_head, ctrl_head, events_list)
                    if fig and self._fill_chart_slot("full_timeseries_overview", fig):
                        generated += 1
                    else:
                        failed_viz.append("全时程概览图(plot_overview返回None)")
                else:
                    failed_viz.append(f"全时程概览图(timestamps={len(timestamps)},speed={len(speed_arr)})")
            except Exception as e:
                self.logger.warning(f"全时程概览图生成失败: {e}")
                failed_viz.append(f"全时程概览图({e})")
        else:
            failed_viz.append("全时程概览图(无overview_data或events_list)")

        if 'events' in results:
            try:
                df_events = results['events']
                if hasattr(df_events, 'empty') and not df_events.empty:
                    fig = viz.plot_event_comparison(df_events)
                    if fig and self._fill_chart_slot("event_comparison", fig):
                        generated += 1
                    else:
                        failed_viz.append("事件对比图(plot_event_comparison返回None)")
                else:
                    failed_viz.append("事件对比图(events DataFrame为空)")
            except Exception as e:
                self.logger.warning(f"事件对比图生成失败: {e}")
                failed_viz.append(f"事件对比图({e})")
        else:
            failed_viz.append("事件对比图(结果中无events)")

        if 'spectrum' in results:
            try:
                spec = results['spectrum']
                if spec:
                    fig = viz.plot_spectrum(spec)
                    if fig and self._fill_chart_slot("spectrum_analysis", fig):
                        generated += 1
                    else:
                        failed_viz.append("频谱分析图(plot_spectrum返回None)")
                else:
                    failed_viz.append("频谱分析图(spectrum为空)")
            except Exception as e:
                self.logger.warning(f"频谱分析图生成失败: {e}")
                failed_viz.append(f"频谱分析图({e})")
        else:
            failed_viz.append("频谱分析图(结果中无spectrum)")

        if 'spectrum' in results:
            try:
                spec = results['spectrum']
                if spec:
                    fig = viz.plot_spectrum_ratio(spec)
                    if fig and self._fill_chart_slot("spectrum_ratio", fig):
                        generated += 1
                    else:
                        failed_viz.append("频谱衰减比图(plot_spectrum_ratio返回None)")
                else:
                    failed_viz.append("频谱衰减比图(spectrum为空)")
            except Exception as e:
                self.logger.warning(f"频谱衰减比图生成失败: {e}")
                failed_viz.append(f"频谱衰减比图({e})")
        else:
            failed_viz.append("频谱衰减比图(结果中无spectrum)")

        if 'stft' in results:
            try:
                stft_data = results['stft']
                if stft_data:
                    fig = viz.plot_stft(stft_data)
                    if fig and self._fill_chart_slot("stft_analysis", fig):
                        generated += 1
                    else:
                        failed_viz.append("时频分析图(plot_stft返回None)")
                else:
                    failed_viz.append("时频分析图(stft为空)")
            except Exception as e:
                self.logger.warning(f"时频分析图生成失败: {e}")
                failed_viz.append(f"时频分析图({e})")
        else:
            failed_viz.append("时频分析图(结果中无stft)")

        if 'statistics' in results:
            try:
                stats_data = results['statistics']
                if stats_data:
                    fig = viz.plot_statistics(stats_data)
                    if fig and self._fill_chart_slot("statistics_dashboard", fig):
                        generated += 1
                    else:
                        failed_viz.append("统计仪表盘(plot_statistics返回None)")
                else:
                    failed_viz.append("统计仪表盘(statistics为空)")
            except Exception as e:
                self.logger.warning(f"统计仪表盘生成失败: {e}")
                failed_viz.append(f"统计仪表盘({e})")
        else:
            failed_viz.append("统计仪表盘(结果中无statistics)")

        if 'metrics' in results:
            try:
                metrics_data = results['metrics']
                if metrics_data:
                    fig = viz.plot_statistical_features(metrics_data)
                    if fig and self._fill_chart_slot("statistical_features", fig):
                        generated += 1
                    else:
                        failed_viz.append("统计特征图(plot_statistical_features返回None)")
                else:
                    failed_viz.append("统计特征图(metrics为空)")
            except Exception as e:
                self.logger.warning(f"统计特征图生成失败: {e}")
                failed_viz.append(f"统计特征图({e})")
        else:
            failed_viz.append("统计特征图(结果中无metrics)")

        if 'spectrum' in results:
            try:
                spec = results['spectrum']
                if spec:
                    fig = viz.plot_band_radar(spec)
                    if fig and self._fill_chart_slot("band_radar", fig):
                        generated += 1
                    else:
                        failed_viz.append("频段雷达图(plot_band_radar返回None)")
                else:
                    failed_viz.append("频段雷达图(spectrum为空)")
            except Exception as e:
                self.logger.warning(f"频段雷达图生成失败: {e}")
                failed_viz.append(f"频段雷达图({e})")
        else:
            failed_viz.append("频段雷达图(结果中无spectrum)")

        if 'windows' in results:
            try:
                df_windows = results['windows']
                if hasattr(df_windows, 'empty') and not df_windows.empty:
                    fig = viz.plot_window_attenuation(df_windows)
                    if fig and self._fill_chart_slot("window_attenuation", fig):
                        generated += 1
                    else:
                        failed_viz.append("滑动窗口衰减趋势图(plot_window_attenuation返回None)")
                else:
                    failed_viz.append("滑动窗口衰减趋势图(windows DataFrame为空)")
            except Exception as e:
                self.logger.warning(f"滑动窗口衰减趋势图生成失败: {e}")
                failed_viz.append(f"滑动窗口衰减趋势图({e})")
        else:
            failed_viz.append("滑动窗口衰减趋势图(结果中无windows)")

        if failed_viz:
            self.logger.info(f"VizManager未生成图表: {len(failed_viz)}张 — {', '.join(failed_viz)}")

        return generated

    def _build_comparison_dict(self, report: Dict) -> Dict[str, Dict]:
        """从报告中构建 comparison_data 字典，用于雷达图和衰减图"""
        result = {}
        locations = report.get('locations', {})
        for loc_id, loc_data in locations.items():
            contrast = loc_data.get('contrast') or {}
            magnitude = contrast.get('magnitude', {})
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

        title = QLabel("行程时间轴")
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

        # ── 新路径：从行为事件列表构建热力图 ──
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
            self._contrast_group.setVisible(False)
            self._output_tab_widget.setVisible(False)
            self._status_label.setText(f'数据集已加载: {basename}')