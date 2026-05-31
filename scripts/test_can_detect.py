#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 parser_manager 智能检测CAN数据"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.parser_manager import ParserManager

manager = ParserManager()

# 测试1: 从实际CAN数据文件测试
print("=" * 60)
print("测试1: 从实际CAN数据文件检测")
print("=" * 60)

can_file_path = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_ch6_CAN.csv"

if os.path.exists(can_file_path):
    with open(can_file_path, 'r', encoding='utf-8') as f:
        sample_content = ''.join([f.readline() for _ in range(30)])
    
    print(f"读取样本内容（前30行）:")
    try:
        content_to_print = sample_content[:500] + "..." if len(sample_content) > 500 else sample_content
        print(content_to_print)
    except UnicodeEncodeError:
        print("(内容包含特殊字符，已跳过打印)")
    print()
    
    result = manager.smart_detect_parser(
        file_path=can_file_path,
        data_content=sample_content
    )
    
    if result:
        print(f"检测结果: {result.name}")
        print(f"支持类型: {result.supported_types}")
        if "CAN" in result.name:
            print("PASS - 正确识别为CAN解析器")
        else:
            print(f"FAIL - 错误识别为 {result.name}")
    else:
        print("FAIL - 未能识别")
else:
    print(f"文件不存在: {can_file_path}")

# 测试2: 模拟CAN数据格式
print()
print("=" * 60)
print("测试2: 模拟CAN数据格式检测")
print("=" * 60)

sample_can = """timestamp,rel_time,can_id,signal_name,车速_kmh,倒挡,方向盘转角_deg
10:25:11.113870,0.0,0x51000,高频自定义帧,35,0,-27
10:25:11.113897,2.7e-05,0x101,方向盘转角,,,-27
10:25:11.114074,0.000204,0x51000,高频自定义帧,34,0,-25
10:25:11.114409,0.000538,0x1F01,扩展帧1F01(数据),,,,
10:25:11.116044,0.002173,0x51000,高频自定义帧,36,0,-23"""

result = manager.smart_detect_parser(
    file_path="test_can_data.csv",
    data_content=sample_can
)

if result:
    print(f"检测结果: {result.name}")
    print(f"支持类型: {result.supported_types}")
    if "CAN" in result.name:
        print("PASS - 正确识别为CAN解析器")
    else:
        print(f"FAIL - 错误识别为 {result.name}")
else:
    print("FAIL - 未能识别")

# 测试3: 验证_is_can_content方法
print()
print("=" * 60)
print("测试3: _is_can_content方法测试")
print("=" * 60)

test_cases = [
    ("包含can_id的CSV表头", "timestamp,can_id,signal_name,value", True),
    ("包含CAN ID值", "0x100,0x101,0x102", True),
    ("包含中文CAN标识", "CAN通道,帧类型,数据", True),
    ("普通文本", "hello world", False),
    ("IMU数据", "[2025-04-17 12:51:33] AA123,0.1,0.2,0.3", False),
]

for name, test_content, expected in test_cases:
    result = ParserManager._is_can_content(test_content)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {name}: {result} (预期: {expected}) [{status}]")

# 测试4: 验证_is_imu_content方法
print()
print("=" * 60)
print("测试4: _is_imu_content方法测试")
print("=" * 60)

test_cases_imu = [
    ("标准IMU数据", "[2025-04-17 12:51:33] AA123,0.1,0.2,0.3,0.4,0.5,0.6,BB456", True),
    ("包含IMU字段的CSV", "ax,ay,az,gx,gy,gz,timestamp", True),
    ("CAN数据不应被识别为IMU", "timestamp,can_id,signal_name,0x100", False),
    ("普通文本", "hello world", False),
]

for name, test_content, expected in test_cases_imu:
    result = ParserManager._is_imu_content(test_content)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {name}: {result} (预期: {expected}) [{status}]")
