#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试CAN数据识别问题"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

# 使用实际CAN文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_ch6_CAN.csv"

print("=" * 70)
print("Debug CAN Data Recognition Issue")
print("=" * 70)

# 读取文件
print("\n1. Reading file...")
print("-" * 70)

encodings_to_try = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']
sample_content = None
used_encoding = None

for enc in encodings_to_try:
    try:
        with open(can_file, 'r', encoding=enc) as f:
            lines = [f.readline() for _ in range(30)]
            sample_content = ''.join(lines)
        if sample_content and len(sample_content.strip()) > 50:
            used_encoding = enc
            print(f"SUCCESS with encoding: {enc}")
            break
    except Exception as e:
        continue

if not sample_content:
    print("FAILED to read file!")
    sys.exit(1)

print("\n2. Sample content preview (first 800 chars):")
print("-" * 70)
print(repr(sample_content[:800]))

print("\n3. CAN feature detection:")
print("-" * 70)

# Check CAN features
can_indicators = [
    'CAN通道', '帧类型', '帧格式', 'ID号', 'CAN类型',
    'CANID', 'can_id', 'canid', 'signal_name',
    '0x1FFF0051', '0x1FFF0053',
    '0x100', '0x101', '0x102', '0x103',
    '0x51000', '0x1F01', '0x1F02', '0x6100',
    '车速', '方向盘转角', '急刹', '刹车油压',
]

found_features = []
not_found_features = []

for indicator in can_indicators:
    if indicator in sample_content:
        found_features.append(indicator)
    else:
        not_found_features.append(indicator)

print(f"FOUND ({len(found_features)}):")
for f in found_features:
    print(f"  + {f}")

print(f"\nNOT FOUND ({len(not_found_features)}):")
for f in not_found_features:
    print(f"  - {f}")

print("\n4. _is_can_content result:")
print("-" * 70)
is_can = ParserManager._is_can_content(sample_content)
print(f"_is_can_content: {is_can}")

print("\n5. _is_imu_content result:")
print("-" * 70)
is_imu = ParserManager._is_imu_content(sample_content)
print(f"_is_imu_content: {is_imu}")

print("\n6. smart_detect_parser result:")
print("-" * 70)
manager = ParserManager()
result = manager.smart_detect_parser(file_path=can_file, data_content=sample_content)
if result:
    print(f"RECOMMENDED: {result.name}")
    print(f"SUPPORTED: {result.supported_types}")
else:
    print("NO RESULT")

print("\n7. Analysis:")
print("-" * 70)
if is_can:
    print("[OK] CAN detection PASSED")
else:
    print("[FAIL] CAN detection FAILED - THIS IS THE PROBLEM!")

if is_imu:
    print("[FAIL] IMU detection incorrectly passed")

# Check the actual detection flow
print("\n8. Detection flow check:")
print("-" * 70)
content_lower = sample_content.lower()
print(f"  'cnap' in content_lower: {'cnap' in content_lower}")
print(f"  'systolic' in content_lower: {'systolic' in content_lower}")
print(f"  'diastolic' in content_lower: {'diastolic' in content_lower}")
print(f"  _is_can_content: {_is_can_content}")
print(f"  _is_imu_content: {_is_imu_content}")
