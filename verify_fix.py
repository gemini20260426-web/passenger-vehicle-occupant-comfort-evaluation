# -*- coding: utf-8 -*-
"""验证修复后的 floor_imu_parser 解析结果与开发者数据对比"""
import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403\core')

from core.data_processing.floor_imu_parser import (
    parse_can_file, extract_imu_pairs, parse_imu_pair, parse_all_channels,
    ACC_SCALE, GYRO_SCALE, IMU_GROUP_A_IDS, IMU_GROUP_B_IDS, IMU_NAME_MAP,
    TARGET_CHANNELS
)
import csv

FSRC = r'd:\UI重构_全量备份_20250824_233403\data_output\验证数据\2026_05_08_094717_ID0001K.txt'
FDEV = r'd:\UI重构_全量备份_20250824_233403\data_output\验证数据\2026_05_08_094717_ID0001K.csv'

print(f"修复后配置:")
print(f"  ACC_SCALE = {ACC_SCALE}")
print(f"  GYRO_SCALE = {GYRO_SCALE}")
print(f"  GROUP_A (实验组) = {IMU_GROUP_A_IDS}")
print(f"  GROUP_B (对照组) = {IMU_GROUP_B_IDS}")
print()

# Parse using the fixed floor_imu_parser
print("正在解析CAN数据...")
all_data, vehicle_data = parse_all_channels(FSRC)

print(f"解析完成, 共 {len(all_data)} 个IMU通道:")
for imu_name in sorted(all_data.keys()):
    print(f"  {imu_name}: {len(all_data[imu_name])} 条记录")

# Read developer data
with open(FDEV, 'r', encoding='gbk') as f:
    dev_rows = list(csv.DictReader(f))

# ===== Compare ch4 IMU7 (实验组, group_a = 0x53+0x54) =====
print("\n" + "="*70)
print("ch4 实验组 (IMU7_座椅底部-1) 对比: 前5个非零配对")
print("="*70)

imu7_data = all_data.get('IMU7_座椅底部-1', [])
if imu7_data:
    print("系统解析 (修复后):")
    cnt = 0
    for d in imu7_data[:10]:
        if d['ax'] == 0 and d['ay'] == 0 and d['az'] == 0:
            continue
        print(f"  t={d['timestamp']:.6f}: ax={d['ax']:.6f} ay={d['ay']:.6f} az={d['az']:.6f} "
              f"gx={d['gx']:.6f} gy={d['gy']:.6f} gz={d['gz']:.6f}")
        cnt += 1
        if cnt >= 5:
            break

print("\n开发者正确解析 (IMU7-实验组):")
print("  x=0.200977 y=0.181836 z=0.382812 gx=-16.647339 gy=-223.953247 gz=6.759644")
print("  (以上为File1首条非零IMU7数据)")

# ===== Compare ch4 IMU8 (对照组, group_b = 0x51+0x52) =====
print("\n" + "="*70)
print("ch4 对照组 (IMU8_座椅底部-2) 对比: 前5个非零配对")
print("="*70)

imu8_data = all_data.get('IMU8_座椅底部-2', [])
if imu8_data:
    print("系统解析 (修复后):")
    cnt = 0
    for d in imu8_data[:10]:
        if d['ax'] == 0 and d['ay'] == 0 and d['az'] == 0:
            continue
        print(f"  t={d['timestamp']:.6f}: ax={d['ax']:.6f} ay={d['ay']:.6f} az={d['az']:.6f} "
              f"gx={d['gx']:.6f} gy={d['gy']:.6f} gz={d['gz']:.6f}")
        cnt += 1
        if cnt >= 5:
            break

print("\n开发者正确解析 (IMU8-对照组):")
print("  x=0.526367 y=-0.354102 z=0.363672 gx=47.836304")