#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试修复后的数据检测方法"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# 导入需要测试的模块
from modules.ui.left_control_panel.data_source_config.data_source_config_dialog import DataSourceConfigDialog

# 用户的真实CAN数据文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"

print("=" * 70)
print("Testing Fixed Detection Methods")
print("=" * 70)

# 创建临时对话框实例（仅用于测试方法）
class TestDialog(DataSourceConfigDialog):
    def __init__(self):
        pass

dialog = TestDialog()

# 测试 _is_can_data
print(f"\n1. Testing _is_can_data:")
print(f"   File: {os.path.basename(can_file)}")
result = dialog._is_can_data(can_file)
print(f"   Result: {result}")

# 测试 _is_imu_data
print(f"\n2. Testing _is_imu_data:")
result = dialog._is_imu_data(can_file)
print(f"   Result: {result}")

# 测试 _is_cnap_data
print(f"\n3. Testing _is_cnap_data:")
result = dialog._is_cnap_data(can_file)
print(f"   Result: {result}")

print("\n" + "=" * 70)
print("Expected: _is_can_data=True, _is_imu_data=False, _is_cnap_data=False")
print("=" * 70)
