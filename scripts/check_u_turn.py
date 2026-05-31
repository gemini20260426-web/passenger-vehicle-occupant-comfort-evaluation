import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')
import logging
logging.basicConfig(level=logging.WARNING)
import struct

from core.core.data_processing.can_parser_v2 import parse_can_file, CH6_VEHICLE_IDS

records = parse_can_file(r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt')

# Check 0x101 records around rel_time 0.9-1.0
print("=== 0x101 records around rel_time 0.9-1.0 ===")
recs_101 = records.get(('0x101', 'ch6'), [])
for r in recs_101:
    if 0.85 < r['rel_time'] < 1.05:
        steering = struct.unpack('>h', r['data'][0:2])[0]
        print(f"  rel_time={r['rel_time']:.6f} data={r['data'].hex()} steering={steering}")

# Check 0x100 records around rel_time 0.9-1.0
print("\n=== 0x100 records around rel_time 0.9-1.0 ===")
recs_100 = records.get(('0x100', 'ch6'), [])
for r in recs_100:
    if 0.85 < r['rel_time'] < 1.05:
        speed = r['data'][0]
        print(f"  rel_time={r['rel_time']:.6f} data={r['data'].hex()} speed={speed}")

# Check ALL 0x101 records - show first 20 and last 20
print("\n=== First 20 0x101 records ===")
for r in recs_101[:20]:
    steering = struct.unpack('>h', r['data'][0:2])[0]
    print(f"  rel_time={r['rel_time']:.6f} steering={steering}")

print("\n=== Last 20 0x101 records ===")
for r in recs_101[-20:]:
    steering = struct.unpack('>h', r['data'][0:2])[0]
    print(f"  rel_time={r['rel_time']:.6f} steering={steering}")

# Check steering range in raw data
all_steering = [struct.unpack('>h', r['data'][0:2])[0] for r in recs_101]
print(f"\n=== 0x101 steering stats ===")
print(f"  Count: {len(all_steering)}")
print(f"  Min: {min(all_steering)}")
print(f"  Max: {max(all_steering)}")
print(f"  Unique values: {len(set(all_steering))}")

# Check 0x100 speed stats
all_speed = [r['data'][0] for r in recs_100]
print(f"\n=== 0x100 speed stats ===")
print(f"  Count: {len(all_speed)}")
print(f"  Min: {min(all_speed)}")
print(f"  Max: {max(all_speed)}")
print(f"  Unique values: {len(set(all_speed))}")