#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整模拟数据源配置对话框的检测流程"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, project_root)

print("=" * 70)
print("Full Dialog Simulation Test")
print("=" * 70)

# 1. 模拟 _init_parser_manager
print("\n1. Initializing parser_manager:")
print("-" * 70)
try:
    from core.core.data_processing.parser_manager import get_parser_manager
    parser_manager = get_parser_manager()
    available = parser_manager.get_available_parsers()
    print(f"   [OK] Initialized, {len(available)} parsers:")
    for p in available:
        print(f"     - {p.name}")
except Exception as e:
    print(f"   [FAIL] {e}")
    import traceback
    traceback.print_exc()
    parser_manager = None

# 2. 测试用户文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"

print(f"\n2. File: {os.path.basename(can_file)}")
print("-" * 70)

sample_content = None
encodings_to_try = ['gbk', 'gb2312', 'utf-8-sig', 'utf-8', 'latin-1']
for enc in encodings_to_try:
    try:
        with open(can_file, 'r', encoding=enc) as f:
            lines = [f.readline() for _ in range(30)]
            sample_content = ''.join(lines)
        if sample_content and len(sample_content.strip()) > 50:
            print(f"   [OK] {enc}, {len(sample_content)} chars")
            break
        sample_content = None
    except:
        pass

if not sample_content:
    print("   [FAIL] Cannot read!")
    sys.exit(1)

# 3. smart_detect_parser
print("\n3. smart_detect_parser:")
print("-" * 70)
if parser_manager:
    recommended = parser_manager.smart_detect_parser(file_path=can_file, data_content=sample_content)
    print(f"   Result: {recommended.name if recommended else 'None'}")
else:
    print("   [FAIL] No parser_manager")
    recommended = None

# 4. Load CAN parser
print("\n4. Loading CAN parser:")
print("-" * 70)
if parser_manager:
    try:
        parser = parser_manager.load_parser("CAN全量数据解析器")
        if parser:
            print(f"   [OK] {type(parser).__name__}")
        else:
            print("   [FAIL] None")
    except Exception as e:
        print(f"   [FAIL] {e}")
        import traceback
        traceback.print_exc()

# 5. Check detection methods
print("\n5. Detection methods:")
print("-" * 70)
from core.core.data_processing.parser_manager import ParserManager
print(f"   _is_can_content: {ParserManager._is_can_content(sample_content)}")
print(f"   _is_imu_content: {ParserManager._is_imu_content(sample_content)}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)