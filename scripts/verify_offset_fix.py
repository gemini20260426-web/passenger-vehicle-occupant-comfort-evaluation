import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')

from core.core.data_processing.can_parser_v2 import CANFullParser

PARK_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001\2026_05_07_180932_ID0001.txt'
DRIVE_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

print("=" * 60)
print("验证 IMU 偏移量校正修复")
print("=" * 60)

parser = CANFullParser()
print("\n[1] 驻车标定...")
configs = parser.calibrate(PARK_FILE)
for ch, cfg in configs.items():
    offsets = cfg['offsets']
    print(f"  {ch}: {len(offsets)} offsets, range=[{min(offsets):.1f}, {max(offsets):.1f}]")

print("\n[2] 解析行驶数据 (wide format)...")
wide_records = []
ay_values = []
for i, record in enumerate(parser.parse_file(DRIVE_FILE)):
    wide_records.append(record)
    ay = record.get('ch4_ay', 0)
    ay_values.append(ay)
    if i < 5:
        print(f"  [{i}] ch4_ax={record.get('ch4_ax', 0):.4f} ch4_ay={record.get('ch4_ay', 0):.4f} ch4_az={record.get('ch4_az', 0):.4f} speed={record.get('speed', 0)} steering={record.get('steering', 0)}")

if ay_values:
    print(f"\n  Wide format ay stats: min={min(ay_values):.4f} max={max(ay_values):.4f} mean={sum(ay_values)/len(ay_values):.4f}")

print("\n[3] 解析行驶数据 (long format)...")
long_records = []
ay_long_values = []
for i, record in enumerate(parser.parse_file_long_format(DRIVE_FILE)):
    long_records.append(record)
    ay = record.get('Ay_m_s2', 0)
    ay_long_values.append(ay)
    if i < 5:
        print(f"  [{i}] imu={record.get('imu_name','')} Ax={record.get('Ax_m_s2',0):.4f} Ay={record.get('Ay_m_s2',0):.4f} Az={record.get('Az_m_s2',0):.4f}")

if ay_long_values:
    print(f"\n  Long format ay stats: min={min(ay_long_values):.4f} max={max(ay_long_values):.4f} mean={sum(ay_long_values)/len(ay_long_values):.4f}")

print("\n[4] 对比开发者 CSV...")
dev_ay_values = []
try:
    import csv
    with open(r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        print(f"  CSV header has {len(header)} columns")
        for row in reader:
            if len(row) > 7:
                try:
                    dev_ay_values.append(float(row[7]) if row[7] else 0.0)
                except ValueError:
                    pass
    if dev_ay_values:
        print(f"  Developer ay stats: min={min(dev_ay_values):.4f} max={max(dev_ay_values):.4f} mean={sum(dev_ay_values)/len(dev_ay_values):.4f}")
except Exception as e:
    print(f"  Could not read developer CSV: {e}")

print("\n[5] 结论:")
if ay_values:
    max_ay = max(ay_values)
    if max_ay < 5.0:
        print(f"  [OK] Wide format ay max={max_ay:.4f} m/s^2 - 在合理范围内 (<0.5g)")
    else:
        print(f"  [FAIL] Wide format ay max={max_ay:.4f} m/s^2 - 仍然异常 (>0.5g)")

if ay_long_values:
    max_ay_long = max(ay_long_values)
    if max_ay_long < 5.0:
        print(f"  [OK] Long format ay max={max_ay_long:.4f} m/s^2 - 在合理范围内 (<0.5g)")
    else:
        print(f"  [FAIL] Long format ay max={max_ay_long:.4f} m/s^2 - 仍然异常 (>0.5g)")

print(f"\n  修复前 ay 峰值: 37.975 m/s^2")
print(f"  修复后 ay 峰值: {max(ay_values) if ay_values else 'N/A'} m/s^2 (wide), {max(ay_long_values) if ay_long_values else 'N/A'} m/s^2 (long)")