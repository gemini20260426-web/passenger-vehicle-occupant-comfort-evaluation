#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整模拟数据源配置对话框的检测流程"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

# 用户实际的CAN文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"

print("=" * 70)
print("Complete Simulation of DataSourceConfigDialog Detection")
print("=" * 70)

# 1. 模拟 _detect_parser 的文件读取逻辑
print("\n1. Simulating _detect_parser file reading:")
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
            print(f"[OK] Read with encoding={enc}, {len(sample_content)} chars")
            print(f"     First 200 chars: {repr(sample_content[:200])}")
            break
        sample_content = None
        print(f"[FAIL] Content too short: {len(sample_content) if sample_content else 0} chars")
    except Exception as e:
        print(f"[FAIL] {enc}: {e}")
        sample_content = None

if sample_content is None:
    try:
        with open(can_file, 'r', encoding='utf-8', errors='ignore') as f:
            sample_content = ''.join(f.readlines(30))
        print(f"[FALLBACK] Read with utf-8 errors='ignore'")
    except Exception as e:
        print(f"[FATAL] All encodings failed: {e}")

# 2. 模拟 parser_manager 初始化
print("\n2. Initializing parser_manager:")
print("-" * 70)
parser_manager = ParserManager()
print(f"parser_manager initialized: {parser_manager is not None}")
print(f"Available parsers: {[p.name for p in parser_manager.get_available_parsers()]}")

# 3. 调用 smart_detect_parser
print("\n3. Calling smart_detect_parser:")
print("-" * 70)
recommended_parser = parser_manager.smart_detect_parser(
    file_path=can_file,
    data_content=sample_content
)
print(f"recommended_parser: {recommended_parser.name if recommended_parser else None}")

# 4. 检查解析器是否在 combo 中
print("\n4. Checking if parser is in combo box:")
print("-" * 70)
available_parsers = parser_manager.get_available_parsers()
print(f"Available parsers list:")
for i, p in enumerate(available_parsers):
    is_recommended = p == recommended_parser if recommended_parser else False
    print(f"  [{i}] {p.name} {'<-- RECOMMENDED' if is_recommended else ''}")

# 5. 验证检测逻辑
print("\n5. Verifying detection logic:")
print("-" * 70)
if sample_content:
    is_can = ParserManager._is_can_content(sample_content)
    is_imu = ParserManager._is_imu_content(sample_content)
    print(f"_is_can_content: {is_can}")
    print(f"_is_imu_content: {is_imu}")

    # 检查中文特征
    print(f"\nKey CAN features check:")
    print(f"  'CAN通道' in content: {'CAN通道' in sample_content}")
    print(f"  'ID号' in content: {'ID号' in sample_content}")
    print(f"  'ch6' in content: {'ch6' in sample_content}")
    print(f"  '0x100' in content: {'0x100' in sample_content}")

print("\n" + "=" * 70)
print("FINAL RESULT:")
if recommended_parser and "CAN" in recommended_parser.name:
    print("[PASS] CAN parser correctly detected!")
else:
    print("[FAIL] CAN parser NOT detected - THIS IS THE PROBLEM!")
print("=" * 70)
