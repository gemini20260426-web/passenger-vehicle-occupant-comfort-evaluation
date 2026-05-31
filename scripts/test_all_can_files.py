#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 CAN全量解析 文件的检测结果"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

# 测试不同的CAN相关文件
test_files = [
    r"d:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_ch6_CAN.csv",
    r"d:\UI重构_全量备份_20250824_233403\data_output\CAN全量解析_2026_05_08_095939_ID0001_20260509_184402.csv",
    r"d:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_IMU.csv",
]

print("=" * 70)
print("Test Different CAN-related Files")
print("=" * 70)

manager = ParserManager()

for file_path in test_files:
    print(f"\n{'='*70}")
    print(f"File: {os.path.basename(file_path)}")
    print("-" * 70)

    if not os.path.exists(file_path):
        print("  [NOT FOUND]")
        continue

    # 读取文件
    encodings_to_try = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']
    sample_content = None

    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = [f.readline() for _ in range(30)]
                sample_content = ''.join(lines)
            if sample_content and len(sample_content.strip()) > 50:
                break
        except Exception:
            sample_content = None

    if not sample_content:
        print("  [READ FAILED]")
        continue

    # 显示表头
    first_line = sample_content.split('\n')[0]
    print(f"  Header: {first_line[:100]}...")

    # 检测
    is_can = ParserManager._is_can_content(sample_content)
    is_imu = ParserManager._is_imu_content(sample_content)
    result = manager.smart_detect_parser(file_path=file_path, data_content=sample_content)

    print(f"  _is_can_content: {is_can}")
    print(f"  _is_imu_content: {is_imu}")
    print(f"  Recommended: {result.name if result else 'None'}")

print("\n" + "=" * 70)
print("Analysis:")
print("-" * 70)
print("""
文件类型说明:
1. *ch6_CAN.csv - 真正的CAN原始数据（包含can_id, signal_name等）
2. CAN全量解析*.csv - 混合数据（IMU格式 + 车速/方向盘等CAN解析字段）
3. *_IMU.csv - 纯IMU数据

如果用户选择的是 #2 或 #3，识别为IMU是正常的！
需要确认用户实际加载的是哪种文件。
""")
