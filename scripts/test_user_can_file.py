#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接测试用户实际的CAN数据文件"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

# 用户实际的CAN数据文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"

print("=" * 70)
print("Direct Test: User's Actual CAN File")
print("=" * 70)
print(f"\nFile: {can_file}")
print(f"Exists: {os.path.exists(can_file)}")

if not os.path.exists(can_file):
    print("FILE NOT FOUND!")
    sys.exit(1)

# 使用数据源配置对话框完全相同的逻辑读取
print("\n1. Reading with dialog's exact logic:")
encodings_to_try = ['gbk', 'gb2312', 'utf-8-sig', 'utf-8', 'latin-1']
sample_content = None

for enc in encodings_to_try:
    try:
        with open(can_file, 'r', encoding=enc) as f:
            lines = [f.readline() for _ in range(30)]
            sample_content = ''.join(lines)
        if sample_content and len(sample_content.strip()) > 50:
            print(f"   [OK] Encoding: {enc}, Chars: {len(sample_content)}")
            break
        sample_content = None
    except Exception as e:
        print(f"   [FAIL] {enc}: {e}")

# 调用检测
print("\n2. Detection:")
manager = ParserManager()
result = manager.smart_detect_parser(file_path=can_file, data_content=sample_content)

print(f"   Recommended: {result.name if result else 'None'}")

# 检查IMU检测为什么被触发
print("\n3. Why IMU might be detected:")
is_can = ParserManager._is_can_content(sample_content)
is_imu = ParserManager._is_imu_content(sample_content)
print(f"   _is_can_content: {is_can}")
print(f"   _is_imu_content: {is_imu}")

if sample_content:
    print(f"\n4. Content preview (first 200 chars):")
    print(f"   {repr(sample_content[:200])}")

print("\n" + "=" * 70)
if result and "CAN" in result.name:
    print("[PASS] CAN Parser Detected!")
else:
    print("[FAIL] NOT CAN Parser!")
print("=" * 70)
