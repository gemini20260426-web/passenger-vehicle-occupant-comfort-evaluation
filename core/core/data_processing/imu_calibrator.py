#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10路IMU离线校准器
完整迁移 离线imu数据校准.py 中的校准逻辑

功能:
  - 10路IMU CAN ID → 物理位置映射
  - 静态零偏校准（加速度+陀螺仪）
  - Z轴方向校正（重力向量检测）
  - 校准参数JSON持久化
"""

import csv
import struct
import json
import os
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)

IMU_CONFIG = [
    {"name": "头部眉心-左", "acc_id": 0x1FFF0051, "gyro_id": 0x1FFF0052},
    {"name": "头部眉心-右", "acc_id": 0x1FFF0053, "gyro_id": 0x1FFF0054},
    {"name": "T8脊柱-左", "acc_id": 0x1FFF0055, "gyro_id": 0x1FFF0056},
    {"name": "T8脊柱-右", "acc_id": 0x1FFF0057, "gyro_id": 0x1FFF0058},
    {"name": "座椅R点-左", "acc_id": 0x1FFF0059, "gyro_id": 0x1FFF005A},
    {"name": "座椅R点-右", "acc_id": 0x1FFF005B, "gyro_id": 0x1FFF005C},
    {"name": "座椅下方-左", "acc_id": 0x1FFF005D, "gyro_id": 0x1FFF005E},
    {"name": "座椅下方-右", "acc_id": 0x1FFF005F, "gyro_id": 0x1FFF0060},
    {"name": "胸骨剑突-左", "acc_id": 0x1FFF0061, "gyro_id": 0x1FFF0062},
    {"name": "胸骨剑突-右", "acc_id": 0x1FFF0063, "gyro_id": 0x1FFF0064},
]

VEHICLE_IDS = {
    0x100: "speed_reverse",
    0x101: "steering_angle",
    0x102: "brake_signal"
}

ACC_SCALE = 9.8 / 4096.0
GYRO_SCALE = 0.07
GRAVITY = 9.80665
DEFAULT_CALIB_FILE = "imu_calib_result.json"


class OfflineIMUCalibrator:

    def __init__(self, dataset_path: str, calib_config_path: Optional[str] = None):
        self.dataset_path = dataset_path
        self.imu_list = IMU_CONFIG
        self.raw_data = defaultdict(list)
        self.calib_results: Dict[str, Any] = {}
        self.all_parsed_frames: List[Dict] = []
        self.calib_config_path = calib_config_path or DEFAULT_CALIB_FILE

    def load_dataset(self) -> bool:
        logger.info(f"加载数据集: {self.dataset_path}")
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 9:
                        continue
                    try:
                        can_id = int(row[4], 16)
                        data = [int(x, 16) for x in row[8].split()] if row[8] else []
                        timestamp = row[2]
                        channel = row[3]

                        for imu in self.imu_list:
                            if can_id == imu['acc_id'] and len(data) == 8:
                                self.raw_data[f"{imu['name']}_acc"].append(data)
                            if can_id == imu['gyro_id'] and len(data) == 8:
                                self.raw_data[f"{imu['name']}_gyro"].append(data)

                        self.all_parsed_frames.append({
                            "timestamp": timestamp, "channel": channel,
                            "can_id": can_id, "data": data
                        })
                    except (ValueError, IndexError):
                        continue

            logger.info(f"数据集加载完成: {len(self.all_parsed_frames)} 帧")
            return True
        except Exception as e:
            logger.error(f"数据集加载失败: {e}")
            return False

    def calibrate_single_sensor(self, data_list: List[List[int]],
                                sensor_type: str) -> Dict[str, Any]:
        best = {"byte_order": "<", "x_bias": 0, "y_bias": 0, "z_bias": 0, "z_sign": 1}
        scale = ACC_SCALE if sensor_type == "acc" else GYRO_SCALE

        x_vals, y_vals, z_vals = [], [], []
        for d in data_list:
            x = struct.unpack('<h', bytes(d[0:2]))[0] * scale
            y = struct.unpack('<h', bytes(d[2:4]))[0] * scale
            z = struct.unpack('<h', bytes(d[4:6]))[0] * scale
            x_vals.append(x)
            y_vals.append(y)
            z_vals.append(z)

        best["x_bias"] = sum(x_vals) / len(x_vals) if x_vals else 0.0
        best["y_bias"] = sum(y_vals) / len(y_vals) if y_vals else 0.0
        best["z_bias"] = sum(z_vals) / len(z_vals) if z_vals else 0.0

        if sensor_type == "acc":
            best["z_sign"] = 1 if abs(best["z_bias"]) > 5 else -1
            best["scale"] = ACC_SCALE
        else:
            best["scale"] = GYRO_SCALE
            best["z_sign"] = 1

        return best

    def run_calibration(self) -> Dict[str, Any]:
        logger.info("开始 10路IMU 全自动静态校准")
        logger.info("=" * 60)

        for imu in self.imu_list:
            name = imu['name']
            logger.info(f"校准: {name}")

            acc_data = self.raw_data.get(f"{name}_acc", [])
            gyro_data = self.raw_data.get(f"{name}_gyro", [])

            if not acc_data or not gyro_data:
                logger.warning(f"  {name} 无有效数据，跳过")
                self.calib_results[name] = {
                    "acc": {"byte_order": "<", "x_bias": 0, "y_bias": 0,
                            "z_bias": 0, "z_sign": 1, "scale": ACC_SCALE},
                    "gyro": {"byte_order": "<", "x_bias": 0, "y_bias": 0,
                             "z_bias": 0, "z_sign": 1, "scale": GYRO_SCALE}
                }
                continue

            acc_params = self.calibrate_single_sensor(acc_data, "acc")
            gyro_params = self.calibrate_single_sensor(gyro_data, "gyro")

            self.calib_results[name] = {"acc": acc_params, "gyro": gyro_params}
            logger.info(f"  {name} 校准完成 | acc_bias: "
                        f"({acc_params['x_bias']:.3f}, {acc_params['y_bias']:.3f}, {acc_params['z_bias']:.3f})")

        try:
            with open(self.calib_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.calib_results, f, indent=4, ensure_ascii=False)
            logger.info(f"校准配置已保存: {self.calib_config_path}")
        except Exception as e:
            logger.error(f"校准配置保存失败: {e}")

        return self.calib_results

    def parse_calibrated_frame(self, can_id: int, data: List[int]) -> Optional[Dict[str, Any]]:
        for imu in self.imu_list:
            name = imu['name']
            calib = self.calib_results.get(name)
            if not calib:
                continue

            if can_id == imu['acc_id'] and len(data) >= 6:
                x = struct.unpack('<h', bytes(data[0:2]))[0] * calib['acc']['scale'] - calib['acc']['x_bias']
                y = struct.unpack('<h', bytes(data[2:4]))[0] * calib['acc']['scale'] - calib['acc']['y_bias']
                z = (struct.unpack('<h', bytes(data[4:6]))[0] * calib['acc']['scale'] - calib['acc']['z_bias']) * calib['acc']['z_sign']
                return {'imu_name': name, 'acc': [x, y, z], 'gyro': [0, 0, 0], 'type': 'acc'}

            if can_id == imu['gyro_id'] and len(data) >= 6:
                x = struct.unpack('<h', bytes(data[0:2]))[0] * calib['gyro']['scale'] - calib['gyro']['x_bias']
                y = struct.unpack('<h', bytes(data[2:4]))[0] * calib['gyro']['scale'] - calib['gyro']['y_bias']
                z = (struct.unpack('<h', bytes(data[4:6]))[0] * calib['gyro']['scale'] - calib['gyro']['z_bias']) * calib['gyro']['z_sign']
                return {'imu_name': name, 'acc': [0, 0, 0], 'gyro': [x, y, z], 'type': 'gyro'}

        return None

    def load_calibration_from_file(self, file_path: Optional[str] = None) -> bool:
        path = file_path or self.calib_config_path
        if not os.path.exists(path):
            logger.warning(f"校准配置文件不存在: {path}")
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.calib_results = json.load(f)
            logger.info(f"校准配置已加载: {path}")
            return True
        except Exception as e:
            logger.error(f"校准配置加载失败: {e}")
            return False

    def get_calibration_for_imu(self, imu_name: str) -> Optional[Dict[str, Any]]:
        return self.calib_results.get(imu_name)

    def get_all_calibrated_imus(self) -> List[str]:
        return list(self.calib_results.keys())

    def get_acc_bias(self, imu_name: str) -> Tuple[float, float, float]:
        calib = self.get_calibration_for_imu(imu_name)
        if not calib:
            return (0.0, 0.0, 0.0)
        acc = calib.get('acc', {})
        return (acc.get('x_bias', 0.0), acc.get('y_bias', 0.0), acc.get('z_bias', 0.0))

    def get_gyro_bias(self, imu_name: str) -> Tuple[float, float, float]:
        calib = self.get_calibration_for_imu(imu_name)
        if not calib:
            return (0.0, 0.0, 0.0)
        gyro = calib.get('gyro', {})
        return (gyro.get('x_bias', 0.0), gyro.get('y_bias', 0.0), gyro.get('z_bias', 0.0))


def parse_vehicle_can(can_id: int, data: List[int]) -> Dict[str, Any]:
    result = {"valid": True}

    if can_id == 0x100:
        result["type"] = "speed_reverse"
        result["speed_kmh"] = data[0] if data else 0
        result["reverse_gear"] = bool(data[1]) if len(data) > 1 else False
        result["description"] = f"车速:{result['speed_kmh']}km/h"

    elif can_id == 0x101:
        result["type"] = "steering_angle"
        if len(data) >= 2:
            angle = struct.unpack('>h', bytes(data[:2]))[0]
            result["steering_angle_deg"] = max(min(angle, 540), -540)
        else:
            result["steering_angle_deg"] = 0
        result["description"] = f"方向盘:{result['steering_angle_deg']}°"

    elif can_id == 0x102:
        result["type"] = "brake_signal"
        result["emergency_brake"] = bool(data[0]) if data else False
        if len(data) >= 4:
            pressure = struct.unpack('>H', bytes(data[2:4]))[0]
            result["brake_pressure"] = max(min(pressure, 1000), 0)
        else:
            result["brake_pressure"] = 0
        result["description"] = f"急刹:{result['emergency_brake']} 油压:{result['brake_pressure']}"

    return result