import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')

from core.core.data_processing.can_parser_v2 import CANFullParser

PARK_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001\2026_05_07_180932_ID0001.txt'
DRIVE_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

parser = CANFullParser()
parser.calibrate(PARK_FILE)

print("=" * 60)
print("Wide Format 深度检查")
print("=" * 60)

print("\n[1] Wide format 前20条记录:")
records = []
for i, record in enumerate(parser.parse_file(DRIVE_FILE)):
    records.append(record)
    if i < 20:
        print(f"  [{i}] ts={record.get('timestamp',0):.3f} "
              f"ch4_ax={record.get('ch4_ax',0):.4f} ch4_ay={record.get('ch4_ay',0):.4f} ch4_az={record.get('ch4_az',0):.4f} "
              f"ch4_gx={record.get('ch4_gx',0):.4f} ch4_gy={record.get('ch4_gy',0):.4f} ch4_gz={record.get('ch4_gz',0):.4f} "
              f"speed={record.get('speed',0)} steering={record.get('steering',0)}")

print(f"\n  Total records: {len(records)}")

unique_ay = set(round(r.get('ch4_ay', 0), 6) for r in records)
unique_speed = set(r.get('speed', 0) for r in records)
unique_steering = set(r.get('steering', 0) for r in records)
print(f"  Unique ch4_ay values: {len(unique_ay)}")
print(f"  Unique speed values: {len(unique_speed)}")
print(f"  Unique steering values: {len(unique_steering)}")

print("\n[2] 检查 ch4 是否有两个 IMU pair 的数据:")
ch4_ax_values = [r.get('ch4_ax', 0) for r in records]
ch4_ay_values = [r.get('ch4_ay', 0) for r in records]
print(f"  ch4_ax: min={min(ch4_ax_values):.4f} max={max(ch4_ax_values):.4f}")
print(f"  ch4_ay: min={min(ch4_ay_values):.4f} max={max(ch4_ay_values):.4f}")

print("\n[3] 检查所有通道的 wide format 数据:")
for ch in ['ch1', 'ch3', 'ch4', 'ch5']:
    ax_key = f'{ch}_ax'
    if ax_key in records[0]:
        ax_vals = [r.get(ax_key, 0) for r in records]
        ay_vals = [r.get(f'{ch}_ay', 0) for r in records]
        print(f"  {ch}: ax=[{min(ax_vals):.4f},{max(ax_vals):.4f}] ay=[{min(ay_vals):.4f},{max(ay_vals):.4f}]")

print("\n[4] 对比开发者 CSV (尝试多种编码):")
dev_ay_values = []
for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'latin-1']:
    try:
        import csv
        with open(r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.csv', 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            header = next(reader)
            print(f"  Encoding '{encoding}' OK, header: {header[:10]}...")
            for row in reader:
                if len(row) > 7:
                    try:
                        dev_ay_values.append(float(row[7]) if row[7] else 0.0)
                    except ValueError:
                        pass
        break
    except Exception as e:
        print(f"  Encoding '{encoding}' failed: {e}")

if dev_ay_values:
    print(f"\n  Developer ay stats: min={min(dev_ay_values):.4f} max={max(dev_ay_values):.4f} mean={sum(dev_ay_values)/len(dev_ay_values):.4f}")
    print(f"  Developer records: {len(dev_ay_values)}")