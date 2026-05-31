#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专用解析器：解析所有IMU通道（ch1/ch3/ch4/ch5）的对照组数据
用于IMU可视化、实时行为分析和CAN全量数据解析
"""
import csv
import struct
import sys
import time
import logging
import bisect
from collections import defaultdict
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置
GYRO_SCALE = 0.07  # 陀螺仪转换系数 (dps/LSB)
ACC_SCALE = 9.8 / 4096.0      # 加速度计转换系数 (m/s²/LSB) (±8g, align with dev code)
IMU_GROUP_A_IDS = ['0x1FFF0053', '0x1FFF0054']  # 实验组
IMU_GROUP_B_IDS = ['0x1FFF0051', '0x1FFF0052']  # 对照组
TARGET_CHANNELS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']  # 所有IMU通道
FLOOR_CHANNELS = ['ch4', 'ch5']  # 车厢地板IMU

# IMU名称映射 - 完整支持10个IMU
IMU_NAME_MAP = {
    ('ch1', 'group_a'): 'IMU1_头部眉心-1',
    ('ch1', 'group_b'): 'IMU2_头部眉心-2',
    ('ch2', 'group_a'): 'IMU3_躯干T8-1',
    ('ch2', 'group_b'): 'IMU4_躯干T8-2',
    ('ch3', 'group_a'): 'IMU5_座垫R点-1',
    ('ch3', 'group_b'): 'IMU6_座垫R点-2',
    ('ch4', 'group_a'): 'IMU7_座椅底部-1',
    ('ch4', 'group_b'): 'IMU8_座椅底部-2',
    ('ch5', 'group_a'): 'IMU9_胸骨剑突-1',
    ('ch5', 'group_b'): 'IMU10_胸骨剑突-2',
}


def _open_file_auto_encoding(file_path, mode='r'):
    """尝试多种编码打开文件"""
    for enc in ['gbk', 'utf-8-sig', 'utf-8', 'gb2312', 'latin-1']:
        try:
            f = open(file_path, mode, encoding=enc)
            f.read(1024)
            f.seek(0)
            return f
        except (UnicodeDecodeError, UnicodeError):
            try:
                f.close()
            except Exception:
                pass
            continue
    return open(file_path, mode, encoding='utf-8', errors='ignore')


def parse_can_file(fpath: str) -> Dict[Tuple[str, str], List[Dict]]:
    """解析原始CAN文件
    
    Args:
        fpath: CAN文件路径
        
    Returns:
        字典，key为(can_id, channel)，value为该CAN ID在该channel的记录列表
    """
    records = defaultdict(list)
    line_count = 0
    
    with _open_file_auto_encoding(fpath) as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return dict(records)
        
        for row in reader:
            line_count += 1
            if line_count % 100000 == 0:
                logger.info(f"[CAN解析] 已处理 {line_count} 行...")
            if line_count % 50000 == 0:
                time.sleep(0)
            if len(row) < 10:
                continue
            try:
                idx = int(row[0])
                timestamp_str = row[1].strip('="')
                rel_time = float(row[2])
                channel = row[3]
                can_id = row[4]
                dlc = int(row[8]) if row[8].strip().isdigit() else 0
                hex_str = row[9]
                if hex_str.startswith('x| '):
                    hex_str = hex_str[3:]
                hex_bytes = hex_str.strip().split()
                data_bytes = bytes([int(b, 16) for b in hex_bytes if b])
                
                records[(can_id, channel)].append({
                    'idx': idx,
                    'timestamp': timestamp_str,
                    'rel_time': rel_time,
                    'dlc': dlc,
                    'data': data_bytes,
                })
            except (ValueError, IndexError):
                continue
    
    return dict(records)


def extract_imu_pairs(
    raw_records: Dict[Tuple[str, str], List[Dict]], 
    channel: str, 
    group: str = 'group_b',
    tolerance_ms: float = 2.0
) -> List[Dict]:
    """提取一个通道的IMU配对
    
    Args:
        raw_records: parse_can_file返回的原始记录
        channel: 要解析的通道（如'ch4', 'ch5'）
        group: 'group_a' 或 'group_b'，指定要解析的组
        tolerance_ms: 时间容忍度（毫秒）
        
    Returns:
        配对后的IMU数据列表
    """
    if group == 'group_a':
        target_ids = IMU_GROUP_A_IDS
    else:
        target_ids = IMU_GROUP_B_IDS
    
    id_recs = {}
    for can_id in target_ids:
        key = (can_id, channel)
        if key in raw_records:
            id_recs[can_id] = raw_records[key]
    
    if len(id_recs) != 2:
        return []
    
    pairs = []
    pointers = {can_id: 0 for can_id in target_ids}
    
    while True:
        times = {}
        for can_id in target_ids:
            if pointers[can_id] >= len(id_recs[can_id]):
                break
            times[can_id] = id_recs[can_id][pointers[can_id]]['rel_time']
        
        if len(times) != 2:
            break
        
        t_list = list(times.values())
        t_min = min(t_list)
        t_max = max(t_list)
        
        if t_max - t_min <= tolerance_ms / 1000.0:
            pair_data = {}
            for can_id in target_ids:
                pair_data[can_id] = id_recs[can_id][pointers[can_id]]
                pointers[can_id] += 1
            pairs.append({
                'time': sum(t_list) / 2.0,
                'data': pair_data,
                'group': group
            })
        else:
            slowest = min(times, key=times.get)
            pointers[slowest] += 1
    
    return pairs


def parse_imu_pair(pair: Dict) -> Optional[Dict[str, float]]:
    """解析IMU配对数据，返回ax/ay/az/gx/gy/gz
    
    Args:
        pair: extract_imu_pairs返回的一个配对数据
        
    Returns:
        包含timestamp, ax, ay, az, gx, gy, gz的字典，或None（解析失败）
    """
    raw_values = []
    
    group = pair.get('group', 'group_b')
    if group == 'group_a':
        target_ids = IMU_GROUP_A_IDS
    else:
        target_ids = IMU_GROUP_B_IDS
    
    # 解析第一个CAN ID
    data1 = pair['data'].get(target_ids[0], {}).get('data', b'')
    if len(data1) >= 8:
        v1 = struct.unpack('<h', data1[0:2])[0]
        v2 = struct.unpack('<h', data1[2:4])[0]
        v3 = struct.unpack('<h', data1[4:6])[0]
        v4 = struct.unpack('<h', data1[6:8])[0]
        raw_values.extend([v1, v2, v3, v4])
    
    # 解析第二个CAN ID
    data2 = pair['data'].get(target_ids[1], {}).get('data', b'')
    if len(data2) >= 4:
        v5 = struct.unpack('<h', data2[0:2])[0]
        v6 = struct.unpack('<h', data2[2:4])[0]
        raw_values.extend([v5, v6])
    
    if len(raw_values) < 6:
        return None
    
    # 简化映射（需要根据实际硬件调整）
    ax, ay, az = raw_values[0], raw_values[1], raw_values[2]
    gx, gy, gz = raw_values[3], raw_values[4], raw_values[5]
    
    # 转换单位
    ax_m = ax * ACC_SCALE
    ay_m = ay * ACC_SCALE
    az_m = az * ACC_SCALE
    gx_r = gx * GYRO_SCALE * 3.14159 / 180.0  # dps -> rad/s
    gy_r = gy * GYRO_SCALE * 3.14159 / 180.0
    gz_r = gz * GYRO_SCALE * 3.14159 / 180.0
    
    return {
        'timestamp': pair['time'],
        'ax': ax_m,
        'ay': ay_m,
        'az': az_m,
        'gx': gx_r,
        'gy': gy_r,
        'gz': gz_r,
    }


def parse_vehicle_data(raw_records: Dict[Tuple[str, str], List[Dict]]) -> Tuple[List, List, List]:
    """解析ch6的车辆数据（速度、方向盘、刹车）
    
    Args:
        raw_records: parse_can_file返回的原始记录
        
    Returns:
        (speed_data, steering_data, brake_data)
        speed_data: (time, speed_m_s) 元组列表
        steering_data: (time, steering_deg) 元组列表
        brake_data: (time, emergency_brake, brake_pressure) 元组列表
    """
    speed_data = []
    steering_data = []
    brake_data = []
    KMH_TO_MS = 1.0 / 3.6  # km/h 转 m/s
    
    # 速度：0x100 — byte[0] 0~255 km/h
    key_speed = ('0x100', 'ch6')
    if key_speed in raw_records:
        for r in raw_records[key_speed]:
            if len(r['data']) >= 1:
                speed_kmh = float(r['data'][0])
                speed_ms = speed_kmh * KMH_TO_MS
                speed_data.append((r['rel_time'], speed_ms))
    
    # 方向盘：0x101 — int16 BE -540~540 deg
    key_steer = ('0x101', 'ch6')
    if key_steer in raw_records:
        for r in raw_records[key_steer]:
            if len(r['data']) >= 2:
                steering = float(struct.unpack('>h', r['data'][0:2])[0])
                steering_data.append((r['rel_time'], steering))
    
    # 急刹+油压：0x102 — byte[0] 急刹标志, byte[2:4] uint16 BE 油压 0~1000
    key_brake = ('0x102', 'ch6')
    if key_brake in raw_records:
        for r in raw_records[key_brake]:
            d = r['data']
            if len(d) >= 4:
                emergency = bool(d[0])
                pressure = float(struct.unpack('>H', d[2:4])[0])
                brake_data.append((r['rel_time'], emergency, pressure))
    
    return speed_data, steering_data, brake_data


def _interpolate(data_list: List[Tuple[float, float]], target_time: float) -> float:
    """线性插值——比最近邻匹配更精确地在时间上对齐低频车辆数据与高频IMU数据"""
    if not data_list:
        return 0.0
    if len(data_list) == 1:
        return data_list[0][1]

    times = [t for t, _ in data_list]
    idx = bisect.bisect_left(times, target_time)

    if idx == 0:
        return data_list[0][1]
    if idx >= len(data_list):
        return data_list[-1][1]

    t0, v0 = data_list[idx - 1]
    t1, v1 = data_list[idx]

    if t1 - t0 < 1e-9:
        return v0

    alpha = (target_time - t0) / (t1 - t0)
    if alpha < 0.0:
        alpha = 0.0
    if alpha > 1.0:
        alpha = 1.0

    return v0 + alpha * (v1 - v0)


def find_closest_data(data_list: List[Tuple[float, float]], target_time: float) -> float:
    """保留旧名称，内部升级为线性插值"""
    return _interpolate(data_list, target_time)


def _interpolate_brake(brake_data: List[Tuple[float, bool, float]], target_time: float) -> Tuple[bool, float]:
    """刹车数据插值：急刹标志用最近邻，油压用线性插值"""
    if not brake_data:
        return False, 0.0
    if len(brake_data) == 1:
        return brake_data[0][1], brake_data[0][2]

    times = [t for t, _, _ in brake_data]
    idx = bisect.bisect_left(times, target_time)

    if idx == 0:
        return brake_data[0][1], brake_data[0][2]
    if idx >= len(brake_data):
        return brake_data[-1][1], brake_data[-1][2]

    t0, eb0, bp0 = brake_data[idx - 1]
    t1, eb1, bp1 = brake_data[idx]

    emergency = eb0 if abs(target_time - t0) <= abs(target_time - t1) else eb1

    if t1 - t0 < 1e-9:
        pressure = bp0
    else:
        alpha = max(0.0, min(1.0, (target_time - t0) / (t1 - t0)))
        pressure = bp0 + alpha * (bp1 - bp0)

    return emergency, pressure


def parse_file_and_select(
    fpath: str,
    preferred_channel: Optional[str] = None
) -> Tuple[List[Dict], str]:
    """完整解析CAN文件，选择最优通道
    
    Args:
        fpath: CAN文件路径
        preferred_channel: 优先选择的通道（None则自动选择）
    
    Returns:
        (parsed_records, selected_channel)
    """
    # 1. 解析原始CAN数据
    raw_records = parse_can_file(fpath)
    
    # 2. 解析ch4和ch5的IMU配对
    imu_data = {}
    for ch in TARGET_CHANNELS:
        pairs = extract_imu_pairs(raw_records, ch)
        parsed = []
        for p in pairs:
            res = parse_imu_pair(p)
            if res:
                parsed.append(res)
        imu_data[ch] = parsed
    
    # 3. 解析车辆数据
    speed_data, steering_data, brake_data = parse_vehicle_data(raw_records)
    
    # 4. 选择通道
    selected_channel = 'ch5'  # 默认
    
    if preferred_channel and preferred_channel in imu_data and imu_data[preferred_channel]:
        selected_channel = preferred_channel
    else:
        # 优先选择数据量多的
        len_ch5 = len(imu_data.get('ch5', []))
        len_ch4 = len(imu_data.get('ch4', []))
        if len_ch5 > 0 and len_ch4 > 0:
            selected_channel = 'ch5' if len_ch5 >= len_ch4 else 'ch4'
        elif len_ch5 > 0:
            selected_channel = 'ch5'
        elif len_ch4 > 0:
            selected_channel = 'ch4'
    
    # 5. 合并车辆数据（线性插值对齐）
    final_records = []
    if selected_channel in imu_data:
        for imu in imu_data[selected_channel]:
            t = imu['timestamp']
            imu['speed'] = find_closest_data(speed_data, t)
            imu['wheel'] = find_closest_data(steering_data, t)
            emergency, pressure = _interpolate_brake(brake_data, t)
            imu['emergency_brake'] = emergency
            imu['brake_pressure'] = pressure
            imu['loc1'] = 0.0
            imu['loc2'] = 0.0
            imu['_source_type'] = 'can_long'
            imu['_source_id'] = f'{selected_channel}_group_b'
            imu['_normalized_from'] = 'can_long'
            imu['_imu_name'] = IMU_NAME_MAP.get((selected_channel, 'group_b'), f'{selected_channel}_unknown')
            final_records.append(imu)
    
    return final_records, selected_channel


def parse_single_channel(
    fpath: str,
    channel: str
) -> Tuple[List[Dict], Dict[str, Any]]:
    """解析单个指定通道的IMU数据 + 车辆数据
    
    Args:
        fpath: CAN文件路径
        channel: 要解析的通道（'ch1'/'ch3'/'ch4'/'ch5'）
    
    Returns:
        (parsed_records, vehicle_data)
        vehicle_data 包含 'speed_data' 和 'steering_data'
    """
    # 1. 解析原始CAN数据
    raw_records = parse_can_file(fpath)
    
    # 2. 解析指定通道的IMU配对
    imu_data = []
    pairs = extract_imu_pairs(raw_records, channel)
    for p in pairs:
        res = parse_imu_pair(p)
        if res:
            imu_data.append(res)
    
    # 3. 解析车辆数据
    speed_data, steering_data, brake_data = parse_vehicle_data(raw_records)
    
    # 4. 合并车辆数据（线性插值对齐）
    final_records = []
    for imu in imu_data:
        t = imu['timestamp']
        imu['speed'] = find_closest_data(speed_data, t)
        imu['wheel'] = find_closest_data(steering_data, t)
        emergency, pressure = _interpolate_brake(brake_data, t)
        imu['emergency_brake'] = emergency
        imu['brake_pressure'] = pressure
        imu['loc1'] = 0.0
        imu['loc2'] = 0.0
        imu['_channel'] = channel
        imu['_source_type'] = 'can_long'
        imu['_source_id'] = f'{channel}_group_b'
        imu['_normalized_from'] = 'can_long'
        imu['_imu_name'] = IMU_NAME_MAP.get((channel, 'group_b'), f'{channel}_unknown')
        final_records.append(imu)
    
    vehicle_data = {
        'speed_data': speed_data,
        'steering_data': steering_data,
        'brake_data': brake_data,
    }
    
    return final_records, vehicle_data


def parse_all_channels(
    fpath: str
) -> Tuple[Dict[str, List[Dict]], Dict[str, Any]]:
    """解析所有IMU通道的实验组和对照组数据 + 车辆数据
    
    Args:
        fpath: CAN文件路径
    
    Returns:
        (all_channel_data, vehicle_data)
        all_channel_data: { 'IMU1_...': [...], 'IMU2_...': [...], ... }
        vehicle_data: 包含 'speed_data' 和 'steering_data'
    """
    # 1. 解析原始CAN数据
    logger.info(f"[全通道解析] 开始解析CAN文件: {fpath}")
    raw_records = parse_can_file(fpath)
    total_raw = sum(len(v) for v in raw_records.values())
    logger.info(f"[全通道解析] CAN文件解析完成, 共 {len(raw_records)} 个CAN ID/通道组合, {total_raw} 条原始记录")
    
    # 2. 解析所有通道的实验组和对照组IMU配对
    all_channel_data = {}
    for channel in TARGET_CHANNELS:
        logger.info(f"[全通道解析] 正在解析通道: {channel}")
        
        has_group_a = all((can_id, channel) in raw_records for can_id in IMU_GROUP_A_IDS)
        has_group_b = all((can_id, channel) in raw_records for can_id in IMU_GROUP_B_IDS)
        
        if has_group_a and not has_group_b:
            pairs = extract_imu_pairs(raw_records, channel, 'group_a')
            parsed_a = []
            parsed_b = []
            for i, p in enumerate(pairs):
                res = parse_imu_pair(p)
                if res:
                    if i % 2 == 0:
                        parsed_b.append(res)
                    else:
                        parsed_a.append(res)
            logger.info(f"[全通道解析]   {channel}: 仅group_a CAN ID存在, 交替拆分 group_a={len(parsed_a)}条, group_b={len(parsed_b)}条")
        else:
            pairs_a = extract_imu_pairs(raw_records, channel, 'group_a')
            parsed_a = []
            for p in pairs_a:
                res = parse_imu_pair(p)
                if res:
                    parsed_a.append(res)
            
            pairs_b = extract_imu_pairs(raw_records, channel, 'group_b')
            parsed_b = []
            for p in pairs_b:
                res = parse_imu_pair(p)
                if res:
                    parsed_b.append(res)
        
        # 获取IMU名称
        imu_name_a = IMU_NAME_MAP.get((channel, 'group_a'), f'{channel}_group_a_unknown')
        imu_name_b = IMU_NAME_MAP.get((channel, 'group_b'), f'{channel}_group_b_unknown')
        
        logger.info(f"[全通道解析]   {channel}: {imu_name_a}={len(parsed_a)}条, {imu_name_b}={len(parsed_b)}条")
        
        # 添加到结果中
        all_channel_data[imu_name_a] = parsed_a
        all_channel_data[imu_name_b] = parsed_b
    
    # 3. 解析车辆数据
    logger.info(f"[全通道解析] 解析车辆数据...")
    speed_data, steering_data, brake_data = parse_vehicle_data(raw_records)
    logger.info(f"[全通道解析] 车辆数据: 速度{len(speed_data)}条, 方向盘{len(steering_data)}条, 刹车{len(brake_data)}条")
    
    # 4. 为每个IMU合并车辆数据（线性插值对齐）
    for imu_name in all_channel_data:
        final_records = []
        for imu in all_channel_data[imu_name]:
            t = imu['timestamp']
            imu['speed'] = _interpolate(speed_data, t)
            imu['wheel'] = _interpolate(steering_data, t)
            emergency, pressure = _interpolate_brake(brake_data, t)
            imu['emergency_brake'] = emergency
            imu['brake_pressure'] = pressure
            imu['loc1'] = 0.0
            imu['loc2'] = 0.0
            imu['_channel'] = imu_name.split('_')[0]
            imu['_source_type'] = 'can_long'
            imu['_source_id'] = imu_name
            imu['_normalized_from'] = 'can_long'
            imu['_imu_name'] = imu_name
            final_records.append(imu)
        all_channel_data[imu_name] = final_records
    
    vehicle_data = {
        'speed_data': speed_data,
        'steering_data': steering_data,
        'brake_data': brake_data,
    }
    
    return all_channel_data, vehicle_data


def get_channel_stats(all_channel_data: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """获取各IMU的数据统计信息
    
    Args:
        all_channel_data: parse_all_channels返回的结果
    
    Returns:
        { 'IMU1_...': {'count': 123, 't_min': 0.0, 't_max': 100.0}, ... }
    """
    stats = {}
    for imu_name, records in all_channel_data.items():
        if records:
            times = [r['timestamp'] for r in records]
            stats[imu_name] = {
                'count': len(records),
                't_min': min(times),
                't_max': max(times),
                'imu_name': records[0]['_imu_name']
            }
        else:
            stats[imu_name] = {
                'count': 0,
                't_min': None,
                't_max': None,
                'imu_name': '无数据'
            }
    return stats


class FloorIMUParser:
    """地板IMU数据解析器 - 兼容旧API，封装多通道解析用于座椅评测

    将 parse_all_channels 的逐帧列表格式转换为通道聚合格式，
    供 StatisticsAnalysisTab 等模块调用。
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def parse_file_and_select(self, file_path: str):
        """解析CAN文件，返回多通道IMU数据 + 车辆数据 + 采样信息

        Args:
            file_path: CAN数据文件路径

        Returns:
            (multi_channel_data, vehicle_data, sample_info)
            - multi_channel_data: {IMU名称: {ax, ay, az, gx, gy, gz, timestamps}, _sample_rate: float}
            - vehicle_data: {speed_data, steering_data, brake_data}
            - sample_info: {channels, total_records}
        """
        self._logger.info(f"[FloorIMUParser] 开始解析: {file_path}")
        all_channel_data, vehicle_data = parse_all_channels(file_path)

        multi_channel_data = {}
        sample_rate = 1000.0

        for ch_name, records in all_channel_data.items():
            if not records:
                continue

            ax_list = [r['ax'] for r in records]
            ay_list = [r['ay'] for r in records]
            az_list = [r['az'] for r in records]
            gx_list = [r['gx'] for r in records]
            gy_list = [r['gy'] for r in records]
            gz_list = [r['gz'] for r in records]
            ts_list = [r['timestamp'] for r in records]

            if len(ts_list) >= 2:
                dt_total = ts_list[-1] - ts_list[0]
                if dt_total > 0:
                    sample_rate = (len(ts_list) - 1) / dt_total

            multi_channel_data[ch_name] = {
                'ax': ax_list,
                'ay': ay_list,
                'az': az_list,
                'gx': gx_list,
                'gy': gy_list,
                'gz': gz_list,
                'timestamps': ts_list,
            }

        multi_channel_data['_sample_rate'] = sample_rate

        sample_info = {
            'channels': list(all_channel_data.keys()),
            'total_records': sum(len(v) for v in all_channel_data.values()),
        }

        self._logger.info(
            f"[FloorIMUParser] 解析完成: {len(multi_channel_data) - 1} 通道, "
            f"采样率≈{sample_rate:.1f}Hz, {sample_info['total_records']} 条记录"
        )
        return multi_channel_data, vehicle_data, sample_info


def main():
    """命令行测试"""
    if len(sys.argv) < 2:
        print("使用方法: python floor_imu_parser.py <can_data_file.txt>")
        sys.exit(1)
    
    txt_path = sys.argv[1]
    print("=" * 80)
    print("全通道IMU解析器")
    print("=" * 80)
    print(f"输入文件: {txt_path}")
    
    try:
        # 测试全通道解析
        print("\n--- 测试全通道解析 ---")
        all_channel_data, vehicle_data = parse_all_channels(txt_path)
        stats = get_channel_stats(all_channel_data)
        
        for channel in sorted(stats.keys()):
            s = stats[channel]
            print(f"\n{channel}: {s['imu_name']}")
            print(f"  数据量: {s['count']} 条")
            if s['t_min'] is not None:
                print(f"  时间范围: {s['t_min']:.3f} - {s['t_max']:.3f}")
        
        # 测试单个通道解析
        print("\n--- 测试单个通道解析 (ch5) ---")
        records, vehicle = parse_single_channel(txt_path, 'ch5')
        if records:
            sample = records[0]
            print(f"  数据量: {len(records)} 条")
            print(f"\n  示例记录:")
            print(f"    timestamp: {sample.get('timestamp'):.3f}")
            print(f"    ax: {sample.get('ax'):.3f}, ay: {sample.get('ay'):.3f}, az: {sample.get('az'):.3f}")
            print(f"    gx: {sample.get('gx'):.3f}, gy: {sample.get('gy'):.3f}, gz: {sample.get('gz'):.3f}")
            print(f"    speed: {sample.get('speed'):.1f}, wheel: {sample.get('wheel'):.1f}")
            print(f"    emergency_brake: {sample.get('emergency_brake')}, brake_pressure: {sample.get('brake_pressure'):.1f}")
            print(f"    imu_name: {sample.get('_imu_name')}")
        
        # 测试原始的 parse_file_and_select
        print("\n--- 测试 parse_file_and_select (车厢地板) ---")
        records, channel = parse_file_and_select(txt_path)
        print(f"  自动选择通道: {channel} ({IMU_NAME_MAP.get((channel, 'group_b'), 'unknown')})")
        print(f"  数据量: {len(records)} 条")
            
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
