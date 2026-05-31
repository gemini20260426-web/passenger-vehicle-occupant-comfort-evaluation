#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟数据源配置对话框的检测行为"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

# 模拟用户使用的CAN数据文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_ch6_CAN.csv"

print("=" * 70)
print("Simulate Data Source Config Dialog Detection")
print("=" * 70)

# 模拟 _detect_parser 方法中的编码尝试
print("\n1. Reading with dialog's encoding order:")
print("-" * 70)

encodings_to_try = ['gbk', 'gb2312', 'utf-8-sig', 'utf-8', 'latin-1']
sample_content = None
used_encoding = None

for enc in encodings_to_try:
    try:
        with open(can_file, 'r', encoding=enc) as f:
            lines = [f.readline() for _ in range(30)]
            sample_content = ''.join(lines)
        if sample_content and len(sample_content.strip()) > 50:
            used_encoding = enc
            print(f"[OK] Read with encoding: {enc}")
            print(f"     Content length: {len(sample_content)} chars")
            print(f"     First 200 chars: {repr(sample_content[:200])}")
            break
        sample_content = None
    except Exception as e:
        print(f"[FAIL] {enc}: {e}")
        sample_content = None

if sample_content is None:
    try:
        with open(can_file, 'r', encoding='utf-8', errors='ignore') as f:
            sample_content = ''.join(f.readlines(30))
        print(f"[FALLBACK] Read with utf-8 errors='ignore'")
    except Exception as e:
        print(f"[FAIL] Fallback also failed: {e}")

print("\n2. Testing smart_detect_parser with dialog's behavior:")
print("-" * 70)

# 初始化 parser_manager
parser_manager = ParserManager()

# 调用 smart_detect_parser
recommended_parser = parser_manager.smart_detect_parser(
    file_path=can_file,
    data_content=sample_content
)

print(f"Recommended parser: {recommended_parser.name if recommended_parser else None}")
if recommended_parser:
    print(f"Supported types: {recommended_parser.supported_types}")

# 检查可用的解析器
print("\n3. Available parsers in manager:")
print("-" * 70)
available = parser_manager.get_available_parsers()
for p in available:
    print(f"  - {p.name}: {p.supported_types}")

# 检查 _is_can_content 和 _is_imu_content
print("\n4. Direct content checks:")
print("-" * 70)
if sample_content:
    is_can = ParserManager._is_can_content(sample_content)
    is_imu = ParserManager._is_imu_content(sample_content)
    print(f"_is_can_content: {is_can}")
    print(f"_is_imu_content: {is_imu}")

print("\n5. Analysis:")
print("-" * 70)
if recommended_parser and "CAN" in recommended_parser.name:
    print("[PASS] CAN parser correctly detected!")
else:
    print("[FAIL] CAN parser NOT detected - THIS IS THE PROBLEM!")
    print("\nPossible causes:")
    print("  1. Encoding issue - content not read correctly")
    print("  2. Parser not registered in parser_manager")
    print("  3. Detection logic has edge case")
