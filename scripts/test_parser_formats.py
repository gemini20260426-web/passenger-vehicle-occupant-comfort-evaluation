#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 IMUDataParser 对两种格式的解析能力"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.core.data_processing.data_parser import IMUDataParser

parser = IMUDataParser()

# ── 12字段格式（含 gx/gy/gz） ──────────────────────────
line_12f = "[2025-07-15 13:36:54-880] AA185,0.169873,0.000000,10.070361,-0.022500,-0.033750,-0.018750,57.000000,0.000000,119.100014,29.000099,BB37"

# ── 8字段格式（无 gx/gy/gz，speed/wheel/loc1/loc2） ────
line_8f = "[2025-04-17 12:51:33-577] 29.000099BBA4AA68,-0.126807,0.354102,10.101465,0.000000,-2.000000,119.100014,29.000099BB9D"

print("=" * 60)
print("测试 12字段格式 (含 gx/gy/gz)")
print("=" * 60)
result = parser.parse_line(line_12f)
if result:
    print(f"  cnt={result['cnt']}, ax={result['ax']}, ay={result['ay']}, az={result['az']}")
    print(f"  gx={result['gx']}, gy={result['gy']}, gz={result['gz']}")
    print(f"  speed={result['speed']}, wheel={result['wheel']}")
    print(f"  loc1={result['loc1']}, loc2={result['loc2']}")
    print(f"  crc={result.get('crc', 'N/A')}")
    print(f"  PASS")
else:
    print(f"  FAIL - 解析返回 None")

print()
print("=" * 60)
print("测试 8字段格式 (无 gx/gy/gz)")
print("=" * 60)
result = parser.parse_line(line_8f)
if result:
    print(f"  cnt={result['cnt']}, ax={result['ax']}, ay={result['ay']}, az={result['az']}")
    print(f"  gx={result['gx']}, gy={result['gy']}, gz={result['gz']}")
    print(f"  speed={result['speed']}, wheel={result['wheel']}")
    print(f"  loc1={result['loc1']}, loc2={result['loc2']}")
    print(f"  crc={result.get('crc', 'N/A')}")
    print(f"  PASS")
else:
    print(f"  FAIL - 解析返回 None")

print()
print("=" * 60)
print("测试 parse_file 全量解析 IMU路测数据.txt")
print("=" * 60)
data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'test_data', 'IMU路测数据.txt')
records = parser.parse_file(data_file)
print(f"  解析到: {len(records)} 条")
if records:
    r = records[0]
    print(f"  首条: cnt={r.get('cnt')}, ax={r.get('ax')}, speed={r.get('speed')}, wheel={r.get('wheel')}")
    r = records[-1]
    print(f"  末条: cnt={r.get('cnt')}, ax={r.get('ax')}, speed={r.get('speed')}, wheel={r.get('wheel')}")
    speeds = [r.get('speed', 0) or 0 for r in records]
    wheels = [r.get('wheel', 0) or 0 for r in records]
    print(f"  speed: min={min(speeds):.2f} max={max(speeds):.2f} avg={sum(speeds)/len(speeds):.2f}")
    print(f"  wheel: min={min(wheels):.2f} max={max(wheels):.2f} avg={sum(wheels)/len(wheels):.2f}")
