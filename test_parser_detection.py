#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试解析器管理器和智能检测功能"""

import os
import sys

print("=" * 60)
print("Test Parser Manager & Detection")
print("=" * 60)

# 添加核心路径
core_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    'core', 'core', 'data_processing'
))
if core_path not in sys.path:
    sys.path.insert(0, core_path)

print(f"Core path: {core_path}")
print(f"Core path exists: {os.path.exists(core_path)}")

print("\n[1] Importing parser_manager...")
try:
    from core.core.data_processing.parser_manager import get_parser_manager
    print("[OK] Import successful")
    
    print("\n[2] Getting parser manager instance...")
    parser_manager = get_parser_manager()
    print("[OK] Parser manager initialized")
    
    print(f"\n[3] Available parsers:")
    available_parsers = parser_manager.get_available_parsers()
    for i, p in enumerate(available_parsers):
        print(f"  {i+1}. {p.name} - {p.description}")
    print(f"  Total: {len(available_parsers)} parsers")
    
    print("\n[4] Testing sample CAN file...")
    sample_file = os.path.join(
        os.path.dirname(__file__),
        'test_data', '验证数据', '2026_05_08_094717_ID0001.txt'
    )
    print(f"  Test file: {sample_file}")
    if os.path.exists(sample_file):
        print("  [OK] File exists")
        # Read sample content
        with open(sample_file, 'r', encoding='utf-8', errors='ignore') as f:
            sample_content = ''.join(f.readlines(10))
        
        print(f"  Sample preview:\n{sample_content[:300]}...")
        
        print("\n  [4a] Using smart_detect_parser...")
        recommended = parser_manager.smart_detect_parser(
            file_path=sample_file,
            data_content=sample_content
        )
        if recommended:
            print(f"  [OK] Detected parser: {recommended.name}")
        else:
            print("  [FAIL] No parser detected")
    else:
        print("  [FAIL] File not found")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
