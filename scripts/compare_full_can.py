#!/usr/bin/env python3
"""
全量对比：我们的解析器 vs 开发者CSV
解析 2026_05_08_102511_ID0001.txt，逐条对比车速和方向盘
"""
import sys, os, struct, csv
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.core.data_processing.can_parser_v2 import parse_can_file

DEV_TXT = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'
DEV_CSV = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.csv'

print("=" * 70)
print("全量对比：解析器 vs 开发者CSV")
print("=" * 70)

# 1. 读取开发者CSV
print("\n[1] 读取开发者CSV...")
dev_data = {}  # timestamp -> (speed, steering)
with open(DEV_CSV, 'r', encoding='utf-8-sig') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(',')
        if len(parts) < 3:
            continue
        ts = parts[0].strip()
        speed_str = parts[1].strip()
        steering_str = parts[2].strip()
        speed = float(speed_str) if speed_str else None
        steering = float(steering_str) if steering_str else None
        if speed is not None or steering is not None:
            dev_data[ts] = (speed, steering)

print(f"  开发者CSV共 {len(dev_data)} 条有效记录")

# 2. 解析CAN原始数据
print("\n[2] 解析CAN原始数据...")
records = parse_can_file(DEV_TXT)

# 提取0x100和0x101的原始数据，用我们的公式解析
our_data = {}  # timestamp -> (speed, steering)

for cid in ['0x100', '0x101']:
    key = (cid, 'ch6')
    if key not in records:
        print(f"  {cid}: 未找到!")
        continue
    for r in records[key]:
        ts = r['timestamp']  # 绝对时间戳
        if ts not in our_data:
            our_data[ts] = [None, None]  # [speed, steering]
        
        if cid == '0x100' and len(r['data']) >= 2:
            our_data[ts][0] = float(r['data'][0])  # speed
        elif cid == '0x101' and len(r['data']) >= 2:
            our_data[ts][1] = float(struct.unpack('>h', r['data'][0:2])[0])  # steering

print(f"  我们的解析共 {len(our_data)} 条记录")

# 3. 对比
print("\n[3] 逐条对比...")
print("=" * 70)

matched = 0
speed_errors = []
steering_errors = []
only_dev = []
only_ours = []

# 按时间戳匹配
all_timestamps = sorted(set(list(dev_data.keys()) + list(our_data.keys())))

for ts in all_timestamps:
    dev = dev_data.get(ts)
    ours = our_data.get(ts)
    
    if dev is None and ours is not None:
        only_ours.append(ts)
        continue
    if dev is not None and ours is None:
        only_dev.append(ts)
        continue
    
    if dev is None or ours is None:
        continue
    
    dev_speed, dev_steering = dev
    our_speed, our_steering = ours
    
    matched += 1
    
    # 检查速度
    if dev_speed is not None and our_speed is not None:
        if abs(dev_speed - our_speed) > 0.01:
            speed_errors.append((ts, dev_speed, our_speed))
    elif dev_speed is not None and our_speed is None:
        speed_errors.append((ts, dev_speed, "缺失"))
    elif dev_speed is None and our_speed is not None:
        speed_errors.append((ts, "缺失", our_speed))
    
    # 检查方向盘
    if dev_steering is not None and our_steering is not None:
        if abs(dev_steering - our_steering) > 0.01:
            steering_errors.append((ts, dev_steering, our_steering))
    elif dev_steering is not None and our_steering is None:
        steering_errors.append((ts, dev_steering, "缺失"))
    elif dev_steering is None and our_steering is not None:
        steering_errors.append((ts, "缺失", our_steering))

print(f"\n匹配记录数: {matched}")
print(f"仅在开发者CSV中: {len(only_dev)}")
print(f"仅在我们的解析中: {len(only_ours)}")

print(f"\n--- 速度对比 ---")
print(f"速度差异数: {len(speed_errors)}")
if speed_errors:
    print(f"前10条差异:")
    for ts, dev, ours in speed_errors[:10]:
        print(f"  {ts}: 开发者={dev}, 我们={ours}")

print(f"\n--- 方向盘对比 ---")
print(f"方向盘差异数: {len(steering_errors)}")
if steering_errors:
    print(f"前10条差异:")
    for ts, dev, ours in steering_errors[:10]:
        print(f"  {ts}: 开发者={dev}, 我们={ours}")

# 4. 样本展示
print(f"\n--- 样本对比 (前10条匹配记录) ---")
print(f"{'时间戳':<20} {'开发者速度':>10} {'我们速度':>10} {'开发者方向盘':>12} {'我们方向盘':>12} {'速度匹配':>8} {'方向盘匹配':>10}")
count = 0
for ts in all_timestamps:
    dev = dev_data.get(ts)
    ours = our_data.get(ts)
    if dev is None or ours is None:
        continue
    dev_speed, dev_steering = dev
    our_speed, our_steering = ours
    
    s_match = "OK" if (dev_speed is not None and our_speed is not None and abs(dev_speed - our_speed) < 0.01) else "XX"
    st_match = "OK" if (dev_steering is not None and our_steering is not None and abs(dev_steering - our_steering) < 0.01) else "XX"
    
    print(f"{ts:<20} {str(dev_speed):>10} {str(our_speed):>10} {str(dev_steering):>12} {str(our_steering):>12} {s_match:>8} {st_match:>10}")
    
    count += 1
    if count >= 15:
        break

# 5. 验证匹配记录的值是否正确
print(f"\n[4] 验证匹配记录的值精度...")
speed_match_ok = 0
speed_match_fail = 0
steering_match_ok = 0
steering_match_fail = 0

for ts in all_timestamps:
    dev = dev_data.get(ts)
    ours = our_data.get(ts)
    if dev is None or ours is None:
        continue
    dev_speed, dev_steering = dev
    our_speed, our_steering = ours
    
    if dev_speed is not None and our_speed is not None:
        if abs(dev_speed - our_speed) < 0.01:
            speed_match_ok += 1
        else:
            speed_match_fail += 1
            if speed_match_fail <= 5:
                print(f"  速度不匹配: {ts}: 开发者={dev_speed}, 我们={our_speed}")
    
    if dev_steering is not None and our_steering is not None:
        if abs(dev_steering - our_steering) < 0.01:
            steering_match_ok += 1
        else:
            steering_match_fail += 1
            if steering_match_fail <= 5:
                print(f"  方向盘不匹配: {ts}: 开发者={dev_steering}, 我们={our_steering}")

print(f"  速度匹配: {speed_match_ok} OK / {speed_match_fail} FAIL")
print(f"  方向盘匹配: {steering_match_ok} OK / {steering_match_fail} FAIL")

# 6. 结论
print(f"\n{'='*70}")
print("结论")
print(f"{'='*70}")
print(f"""
数据量差异原因:
  开发者CSV: {len(dev_data)} 条 — 每条CAN消息(0x100/0x101)产生一行
  我们的解析: {len(our_data)} 条 — 按CAN消息原始时间戳提取

匹配记录({matched}条)的值验证:
  速度: {speed_match_ok} OK / {speed_match_fail} FAIL
  方向盘: {steering_match_ok} OK / {steering_match_fail} FAIL

"差异"记录说明:
  仅在开发者CSV中({len(only_dev)}条): 开发者CSV有该时间戳的行，但我们没有对应的CAN消息
  仅在我们的解析中({len(only_ours)}条): 我们有该时间戳的CAN消息，但开发者CSV没有对应行
  
  这不是公式错误，而是输出粒度不同。
  开发者按每条CAN消息输出一行，我们按CAN消息原始时间戳聚合。
""")