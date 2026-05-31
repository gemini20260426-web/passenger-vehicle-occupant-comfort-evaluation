#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试真实的CAN原始数据文件"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"

print("=" * 70)
print("Test Real CAN Raw Data File (GBK encoded)")
print("=" * 70)

# 使用GBK编码读取
print("\n1. Reading with GBK encoding:")
with open(can_file, 'r', encoding='gbk') as f:
    lines = [f.readline() for _ in range(30)]
    sample_content = ''.join(lines)

print(f"   Content length: {len(sample_content)} chars")
print(f"   First 300 chars: {repr(sample_content[:300])}")

print("\n2. CAN features in content:")
print("-" * 70)

can_indicators = [
    'CAN通道', '帧类型', '帧格式', 'ID号', 'CAN类型',
    'CANID', 'can_id', 'canid', 'signal_name',
    '0x1FFF0051', '0x1FFF0053',
    '0x100', '0x101', '0x102', '0x103',
    '0x51000', '0x1F01', '0x1F02', '0x6100',
]

for indicator in can_indicators:
    found = indicator in sample_content
    print(f"   {indicator}: {found}")

print("\n3. Detection results:")
print("-" * 70)
is_can = ParserManager._is_can_content(sample_content)
is_imu = ParserManager._is_imu_content(sample_content)
print(f"   _is_can_content: {is_can}")
print(f"   _is_imu_content: {is_imu}")

manager = ParserManager()
result = manager.smart_detect_parser(file_path=can_file, data_content=sample_content)
print(f"   Recommended: {result.name if result else 'None'}")

print("\n4. Analysis:")
print("-" * 70)
if is_can:
    print("   [OK] CAN detection PASSED")
else:
    print("   [FAIL] CAN detection FAILED - THIS IS THE PROBLEM!")
    print("\n   Root cause: The Chinese characters 'CAN通道', 'ID号', etc.")
    print("   are NOT being found in the content check.")
    print("   Let's verify the actual content...")

# Debug: check what's actually in the content
print("\n5. Debug - checking content encoding:")
print("-" * 70)
# Check if Chinese chars are present
has_chinese = False
for char in sample_content[:500]:
    if '\u4e00' <= char <= '\u9fff':
        has_chinese = True
        print(f"   Found Chinese char: {char}")
        break
print(f"   Has Chinese chars: {has_chinese}")
