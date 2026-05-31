#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校准参数持久化存储
管理各通道IMU的零偏校准参数和坐标系对齐矩阵的持久化

功能:
  - JSON文件格式持久化
  - 版本控制和迁移
  - 批量导入/导出
  - 与DataPreprocessor集成
  - 校准历史追溯
"""

import json
import os
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_CALIBRATION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'data_output', 'calibration_params.json'
)

CALIBRATION_VERSION = '2.0'

IMU_CHANNELS = [
    'ch1_imu', 'ch2_imu', 'ch3_imu', 'ch4_imu', 'ch5_imu',
    'ch6_imu', 'ch7_imu', 'ch8_imu', 'ch9_imu', 'ch10_imu',
]

IMU_GROUP_MAP = {
    'ch1_imu': ('experimental', 'head'),
    'ch2_imu': ('control', 'head'),
    'ch3_imu': ('experimental', 'torso'),
    'ch4_imu': ('control', 'torso'),
    'ch5_imu': ('experimental', 'seat_r'),
    'ch6_imu': ('control', 'seat_r'),
    'ch7_imu': ('experimental', 'seat_bottom'),
    'ch8_imu': ('control', 'seat_bottom'),
    'ch9_imu': ('experimental', 'sternum'),
    'ch10_imu': ('control', 'sternum'),
}


@dataclass
class ChannelCalibration:
    """单通道校准数据"""

    channel_id: str
    acc_bias_x: float = 0.0
    acc_bias_y: float = 0.0
    acc_bias_z: float = 0.0
    gyro_bias_x: float = 0.0
    gyro_bias_y: float = 0.0
    gyro_bias_z: float = 0.0
    correction_r11: float = 1.0
    correction_r12: float = 0.0
    correction_r13: float = 0.0
    correction_r21: float = 0.0
    correction_r22: float = 1.0
    correction_r23: float = 0.0
    correction_r31: float = 0.0
    correction_r32: float = 0.0
    correction_r33: float = 1.0
    has_calibration: bool = False
    calibrated_at: str = ''
    source_file: str = ''
    source_hash: str = ''
    notes: str = ''

    def get_acc_bias(self) -> np.ndarray:
        return np.array([self.acc_bias_x, self.acc_bias_y, self.acc_bias_z])

    def set_acc_bias(self, bias: np.ndarray):
        if len(bias) >= 3:
            self.acc_bias_x = float(bias[0])
            self.acc_bias_y = float(bias[1])
            self.acc_bias_z = float(bias[2])

    def get_gyro_bias(self) -> np.ndarray:
        return np.array([self.gyro_bias_x, self.gyro_bias_y, self.gyro_bias_z])

    def set_gyro_bias(self, bias: np.ndarray):
        if len(bias) >= 3:
            self.gyro_bias_x = float(bias[0])
            self.gyro_bias_y = float(bias[1])
            self.gyro_bias_z = float(bias[2])

    def get_correction_matrix(self) -> np.ndarray:
        return np.array([
            [self.correction_r11, self.correction_r12, self.correction_r13],
            [self.correction_r21, self.correction_r22, self.correction_r23],
            [self.correction_r31, self.correction_r32, self.correction_r33],
        ])

    def set_correction_matrix(self, R: np.ndarray):
        if R.shape == (3, 3):
            self.correction_r11 = float(R[0, 0])
            self.correction_r12 = float(R[0, 1])
            self.correction_r13 = float(R[0, 2])
            self.correction_r21 = float(R[1, 0])
            self.correction_r22 = float(R[1, 1])
            self.correction_r23 = float(R[1, 2])
            self.correction_r31 = float(R[2, 0])
            self.correction_r32 = float(R[2, 1])
            self.correction_r33 = float(R[2, 2])

    @classmethod
    def from_dict(cls, data: dict) -> 'ChannelCalibration':
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)


@dataclass
class CalibrationMetadata:
    """校准参数元数据"""

    version: str = CALIBRATION_VERSION
    created_at: str = ''
    updated_at: str = ''
    source_dataset: str = ''
    description: str = ''
    total_channels: int = 10
    calibrated_channels: int = 0
    preprocess_level: int = 2


class CalibrationStore:

    def __init__(self, file_path: Optional[str] = None):
        self._file_path = file_path or DEFAULT_CALIBRATION_FILE
        self._metadata = CalibrationMetadata()
        self._channels: Dict[str, ChannelCalibration] = {}
        self._history: List[Dict[str, Any]] = []
        self._initialized = False

        self._init_default_channels()
        self._load()

    def _init_default_channels(self):
        for ch_id in IMU_CHANNELS:
            self._channels[ch_id] = ChannelCalibration(channel_id=ch_id)

    def _ensure_dir(self):
        dir_path = os.path.dirname(self._file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    def _load(self):
        if not os.path.exists(self._file_path):
            logger.info(f"校准文件不存在，将使用默认值: {self._file_path}")
            self._initialized = True
            return

        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            meta = data.get('metadata', {})
            self._metadata = CalibrationMetadata(
                version=meta.get('version', CALIBRATION_VERSION),
                created_at=meta.get('created_at', ''),
                updated_at=meta.get('updated_at', ''),
                source_dataset=meta.get('source_dataset', ''),
                description=meta.get('description', ''),
                total_channels=meta.get('total_channels', 10),
                calibrated_channels=meta.get('calibrated_channels', 0),
                preprocess_level=meta.get('preprocess_level', 2),
            )

            channels_data = data.get('channels', {})
            for ch_id, ch_data in channels_data.items():
                if ch_id in self._channels:
                    self._channels[ch_id] = ChannelCalibration.from_dict(ch_data)
                else:
                    self._channels[ch_id] = ChannelCalibration.from_dict(ch_data)

            self._history = data.get('history', [])

            calibrated_count = sum(1 for ch in self._channels.values() if ch.has_calibration)
            self._metadata.calibrated_channels = calibrated_count

            self._initialized = True
            logger.info(f"校准参数已加载: {self._file_path} "
                        f"({calibrated_count}/{len(self._channels)} 通道已校准)")

        except Exception as e:
            logger.error(f"加载校准文件失败: {e}")
            self._initialized = True

    def save(self) -> bool:
        self._ensure_dir()
        self._metadata.updated_at = datetime.now().isoformat()
        calibrated_count = sum(1 for ch in self._channels.values() if ch.has_calibration)
        self._metadata.calibrated_channels = calibrated_count

        data = {
            'metadata': asdict(self._metadata),
            'channels': {ch_id: asdict(ch) for ch_id, ch in self._channels.items()},
            'history': self._history[-50:],
        }

        try:
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"校准参数已保存: {self._file_path} ({calibrated_count} 通道)")
            return True
        except Exception as e:
            logger.error(f"保存校准文件失败: {e}")
            return False

    def get_channel(self, channel_id: str) -> Optional[ChannelCalibration]:
        return self._channels.get(channel_id)

    def get_all_channels(self) -> Dict[str, ChannelCalibration]:
        return dict(self._channels)

    def get_calibrated_channels(self) -> Dict[str, ChannelCalibration]:
        return {k: v for k, v in self._channels.items() if v.has_calibration}

    def set_channel_calibration(self, channel_id: str, acc_bias: np.ndarray,
                                gyro_bias: np.ndarray, correction_matrix: Optional[np.ndarray] = None,
                                source_file: str = '', notes: str = '') -> bool:
        ch = self._channels.get(channel_id)
        if ch is None:
            ch = ChannelCalibration(channel_id=channel_id)
            self._channels[channel_id] = ch

        ch.set_acc_bias(acc_bias)
        ch.set_gyro_bias(gyro_bias)

        if correction_matrix is not None:
            ch.set_correction_matrix(correction_matrix)

        ch.has_calibration = True
        ch.calibrated_at = datetime.now().isoformat()
        ch.source_file = source_file

        if source_file:
            ch.source_hash = self._compute_file_hash(source_file)

        if notes:
            ch.notes = notes

        self._add_history_entry('update', channel_id, {
            'acc_bias': acc_bias.tolist(),
            'gyro_bias': gyro_bias.tolist(),
            'source_file': source_file,
        })

        logger.info(f"通道 {channel_id} 校准参数已更新")
        return True

    def set_batch_calibration(self, calibrations: Dict[str, Dict[str, Any]]) -> int:
        count = 0
        for channel_id, calib in calibrations.items():
            acc_bias = np.array(calib.get('acc_bias', [0, 0, 0]))
            gyro_bias = np.array(calib.get('gyro_bias', [0, 0, 0]))
            corr = np.array(calib.get('correction_matrix', np.eye(3).tolist()))

            if self._channels.get(channel_id) is None:
                self._channels[channel_id] = ChannelCalibration(channel_id=channel_id)

            self._channels[channel_id].set_acc_bias(acc_bias)
            self._channels[channel_id].set_gyro_bias(gyro_bias)
            self._channels[channel_id].set_correction_matrix(corr)
            self._channels[channel_id].has_calibration = True
            self._channels[channel_id].calibrated_at = datetime.now().isoformat()
            self._channels[channel_id].source_file = calib.get('source_file', '')
            count += 1

        if count > 0:
            self._add_history_entry('batch_update', 'batch', {'count': count})
            self.save()

        logger.info(f"批量校准完成: {count} 通道")
        return count

    def reset_channel(self, channel_id: str) -> bool:
        self._channels[channel_id] = ChannelCalibration(channel_id=channel_id)
        self._add_history_entry('reset', channel_id, {})
        logger.info(f"通道 {channel_id} 校准参数已重置")
        return True

    def reset_all(self) -> int:
        count = self._metadata.calibrated_channels
        self._channels.clear()
        self._init_default_channels()
        self._metadata.calibrated_channels = 0
        self._add_history_entry('reset_all', 'all', {'previous_count': count})
        logger.info(f"所有通道校准参数已重置 (原先 {count} 通道已校准)")
        return count

    def export_to_json(self, export_path: str, channels: Optional[List[str]] = None) -> bool:
        try:
            chs = channels or list(self._channels.keys())
            export_data = {
                'version': CALIBRATION_VERSION,
                'exported_at': datetime.now().isoformat(),
                'channels': {ch_id: asdict(self._channels[ch_id])
                           for ch_id in chs if ch_id in self._channels},
            }
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            logger.info(f"校准参数已导出: {export_path}")
            return True
        except Exception as e:
            logger.error(f"导出校准参数失败: {e}")
            return False

    def import_from_json(self, import_path: str, overwrite: bool = True) -> int:
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            channels_data = data.get('channels', {})
            count = 0
            for ch_id, ch_data in channels_data.items():
                if overwrite or ch_id not in self._channels or not self._channels[ch_id].has_calibration:
                    calib = ChannelCalibration.from_dict(ch_data)
                    self._channels[ch_id] = calib
                    count += 1

            if count > 0:
                self._add_history_entry('import', 'batch', {
                    'import_path': import_path, 'count': count
                })
                self.save()

            logger.info(f"已从 {import_path} 导入 {count} 个通道的校准参数")
            return count
        except Exception as e:
            logger.error(f"导入校准参数失败: {e}")
            return 0

    def apply_to_preprocessor(self, preprocessor, channel_id: str) -> bool:
        ch = self._channels.get(channel_id)
        if ch is None or not ch.has_calibration:
            logger.debug(f"通道 {channel_id} 无校准参数可应用")
            return False

        preprocessor.acc_bias = ch.get_acc_bias()
        preprocessor.gyro_bias = ch.get_gyro_bias()
        preprocessor.correction_matrix = ch.get_correction_matrix()
        logger.debug(f"通道 {channel_id} 校准参数已应用到预处理器")
        return True

    def get_calibration_summary(self) -> Dict[str, Any]:
        calibrated = self.get_calibrated_channels()
        return {
            'total_channels': len(self._channels),
            'calibrated_channels': len(calibrated),
            'last_updated': self._metadata.updated_at,
            'source_dataset': self._metadata.source_dataset,
            'preprocess_level': self._metadata.preprocess_level,
            'channel_details': {
                ch_id: {
                    'has_calibration': ch.has_calibration,
                    'calibrated_at': ch.calibrated_at,
                    'source_file': os.path.basename(ch.source_file) if ch.source_file else '',
                    'acc_bias': [ch.acc_bias_x, ch.acc_bias_y, ch.acc_bias_z],
                    'gyro_bias': [ch.gyro_bias_x, ch.gyro_bias_y, ch.gyro_bias_z],
                    'group': IMU_GROUP_MAP.get(ch_id, ('unknown', 'unknown')),
                }
                for ch_id, ch in self._channels.items()
            },
        }

    def _add_history_entry(self, action: str, channel_id: str, details: Dict[str, Any]):
        self._history.append({
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'channel_id': channel_id,
            'details': details,
        })

    def _compute_file_hash(self, file_path: str) -> str:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return hashlib.md5(f.read(4096)).hexdigest()
        except Exception:
            pass
        return ''

    def get_version(self) -> str:
        return self._metadata.version

    def is_initialized(self) -> bool:
        return self._initialized