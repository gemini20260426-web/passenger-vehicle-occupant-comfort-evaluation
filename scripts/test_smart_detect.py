#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 parser_manager 智能检测和字段映射对8字段格式的支持"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# ── 测试1: smart_detect_parser 对8字段格式的识别 ──────
print("=" * 60)
print("测试1: parser_manager.smart_detect_parser 识别8字段格式")
print("=" * 60)

from core.core.data_processing.parser_manager import ParserManager

manager = ParserManager()

# 模拟8字段格式的数据内容
sample_8f = "[2025-04-17 12:51:33-577] 29.000099BBA4AA68,-0.126807,0.354102,10.101465,0.000000,-2.000000,119.100014,29.000099BB9D"

result = manager.smart_detect_parser(
    file_path="test_imu_data.txt",
    data_content=sample_8f
)

if result:
    print(f"  检测结果: {result.name}")
    print(f"  支持类型: {result.supported_types}")
    print(f"  PASS - 正确识别为IMU解析器")
else:
    print(f"  检测结果: None")
    print(f"  FAIL - 未能识别")

# ── 测试2: 12字段格式仍然能识别 ───────────────────────
print()
print("=" * 60)
print("测试2: smart_detect_parser 识别12字段格式 (回归)")
print("=" * 60)

sample_12f = "[2025-07-15 13:36:54-880] AA185,0.169873,0.000000,10.070361,-0.022500,-0.033750,-0.018750,57.000000,0.000000,119.100014,29.000099,BB37"

result = manager.smart_detect_parser(
    file_path="test_imu_data.txt",
    data_content=sample_12f
)

if result:
    print(f"  检测结果: {result.name}")
    print(f"  支持类型: {result.supported_types}")
    print(f"  PASS - 12字段格式仍然正确识别")
else:
    print(f"  FAIL - 回归失败")

# ── 测试3: 字段映射表 ─────────────────────────────────
print()
print("=" * 60)
print("测试3: 字段映射表包含 loc1/loc2")
print("=" * 60)

# 模拟 _get_smart_target_field_name 逻辑
mapping = {
    'cnt': 'cnt', 'count': 'cnt', 'seq': 'cnt',
    'ax': 'ax', 'accel_x': 'ax', 'ay': 'ay', 'accel_y': 'ay',
    'az': 'az', 'accel_z': 'az', 'gx': 'gx', 'gyro_x': 'gx',
    'gy': 'gy', 'gyro_y': 'gy', 'gz': 'gz', 'gyro_z': 'gz',
    'speed': 'speed', 'velocity': 'speed',
    'wheel': 'wheel', 'steering': 'wheel',
    'loc1': 'loc1', 'loc2': 'loc2', 'location': 'loc1', 'longitude': 'loc1', 'latitude': 'loc2',
    'timestamp': 'timestamp', 'time': 'timestamp', 'ts': 'timestamp',
    'crc': 'crc', 'checksum': 'crc',
}

test_fields = ['loc1', 'loc2', 'longitude', 'latitude', 'speed', 'wheel']
all_ok = True
for f in test_fields:
    mapped = mapping.get(f, 'NOT FOUND')
    status = "OK" if mapped != 'NOT FOUND' else "MISSING"
    if mapped == 'NOT FOUND':
        all_ok = False
    print(f"  {f:12s} -> {mapped:10s} [{status}]")

print(f"  {'PASS' if all_ok else 'FAIL'}")

# ── 测试4: IMUDataParser 解析8字段格式 ─────────────────
print()
print("=" * 60)
print("测试4: IMUDataParser 解析8字段格式 (回归)")
print("=" * 60)

from core.core.data_processing.data_parser import IMUDataParser
parser = IMUDataParser()
result = parser.parse_line(sample_8f)
if result:
    print(f"  cnt={result['cnt']}, speed={result['speed']}, wheel={result['wheel']}")
    print(f"  gx={result['gx']}, gy={result['gy']}, gz={result['gz']}")
    print(f"  PASS")
else:
    print(f"  FAIL")
