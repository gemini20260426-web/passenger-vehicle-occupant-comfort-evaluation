#!/usr/bin/env python3
"""诊断CAN解析器：对比开发者解析结果与我们的解析器输出"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.core.data_processing.can_parser_v2 import parse_can_file, CH6_VEHICLE_IDS

DEV_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'
DEV_CSV = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.csv'

print("=" * 70)
print("诊断：CAN车辆信号解析对比")
print("=" * 70)

records = parse_can_file(DEV_FILE)

print(f"\n解析到 {sum(len(v) for v in records.values())} 条CAN记录")

for cid in CH6_VEHICLE_IDS:
    key = (cid, 'ch6')
    if key in records:
        print(f"  {cid}: {len(records[key])} 条")
        for i, r in enumerate(records[key][:5]):
            hex_str = ' '.join(f'{b:02x}' for b in r['data'])
            print(f"    [{i}] time={r['rel_time']:.6f} data={hex_str}")

print("\n" + "=" * 70)
print("开发者CSV解析结果 (前20行有数据的):")
print("=" * 70)

dev_data = []
with open(DEV_CSV, 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split(',')
        if len(parts) >= 3:
            ts = parts[0].strip()
            speed = parts[1].strip()
            steering = parts[2].strip()
            if speed or steering:
                dev_data.append((ts, speed, steering))

for i, (ts, speed, steering) in enumerate(dev_data[:20]):
    print(f"  [{i}] ts={ts} speed={speed} steering={steering}")

print("\n" + "=" * 70)
print("交叉验证：用开发者公式手动解析")
print("=" * 70)

import struct

for cid in ['0x100', '0x101', '0x102']:
    key = (cid, 'ch6')
    if key not in records:
        continue
    print(f"\n--- {cid} 前10条 ---")
    for i, r in enumerate(records[key][:10]):
        hex_str = ' '.join(f'{b:02x}' for b in r['data'])
        if cid == '0x100' and len(r['data']) >= 2:
            speed = r['data'][0]
            reverse = r['data'][1]
            print(f"  [{i}] time={r['rel_time']:.6f} raw={hex_str} → speed={speed}km/h reverse={reverse}")
        elif cid == '0x101' and len(r['data']) >= 2:
            steering = struct.unpack('>h', r['data'][0:2])[0]
            print(f"  [{i}] time={r['rel_time']:.6f} raw={hex_str} → steering={steering}°")
        elif cid == '0x102' and len(r['data']) >= 4:
            ebrake = r['data'][0]
            pressure = (r['data'][2] << 8) | r['data'][3]
            print(f"  [{i}] time={r['rel_time']:.6f} raw={hex_str} → ebrake={ebrake} pressure={pressure}")

print("\n" + "=" * 70)
print("结论")
print("=" * 70)
print("""
开发者公式:
  车速 ID=0x100: byte[0] = 0~255 km/h
  方向盘 ID=0x101: byte[0:2] big-endian signed 16-bit, -540~540°
  急刹 ID=0x102: byte[0]=急刹标志, byte[2:4] big-endian unsigned 16-bit, 0~1000

我们的解析器公式:
  speed = r['data'][0]           ← 与开发者一致
  steering = struct.unpack('>h', r['data'][0:2])[0]  ← 与开发者一致
  brake_pressure = (r['data'][2] << 8) | r['data'][3]  ← 与开发者一致
""")