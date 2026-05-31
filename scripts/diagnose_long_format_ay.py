import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')

from core.core.data_processing.can_parser_v2 import CANFullParser

PARK_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001\2026_05_07_180932_ID0001.txt'
DRIVE_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

print("=" * 60)
print("Long Format Ay 异常诊断")
print("=" * 60)

parser = CANFullParser()
configs = parser.calibrate(PARK_FILE)

print("\n[1] 各通道标定详情:")
for ch, cfg in configs.items():
    print(f"\n  {ch}:")
    print(f"    active_can_ids: {cfg['active_can_ids']}")
    print(f"    n_fields_per_id: {cfg['n_fields_per_id']}")
    print(f"    field_types: {cfg['field_types']}")
    idx = 0
    for cid in cfg['active_can_ids']:
        nf = cfg['n_fields_per_id'][cid]
        for j in range(nf):
            offset = cfg['offsets'][idx]
            ft = cfg['field_types'][idx]
            print(f"    [{idx:2d}] {cid}[{j}] offset={offset:10.1f} type={ft}")
            idx += 1

print("\n[2] 按通道统计 long format ay 值:")
channel_ay_stats = {}
for record in parser.parse_file_long_format(DRIVE_FILE):
    ch = record.get('channel', '')
    imu_name = record.get('imu_name', '')
    ay = record.get('Ay_m_s2', 0)
    ax = record.get('Ax_m_s2', 0)
    az = record.get('Az_m_s2', 0)
    gx = record.get('Gx_dps', 0)
    gy = record.get('Gy_dps', 0)
    gz = record.get('Gz_dps', 0)
    
    key = f"{ch}/{imu_name}"
    if key not in channel_ay_stats:
        channel_ay_stats[key] = {'min': ay, 'max': ay, 'sum': 0.0, 'count': 0, 'samples': []}
    stats = channel_ay_stats[key]
    stats['min'] = min(stats['min'], ay)
    stats['max'] = max(stats['max'], ay)
    stats['sum'] += ay
    stats['count'] += 1
    if len(stats['samples']) < 5:
        stats['samples'].append((ax, ay, az, gx, gy, gz))

for key, stats in sorted(channel_ay_stats.items()):
    mean = stats['sum'] / stats['count'] if stats['count'] > 0 else 0
    print(f"\n  {key}:")
    print(f"    count={stats['count']}, ay: min={stats['min']:.4f} max={stats['max']:.4f} mean={mean:.4f}")
    print(f"    first 5 samples (ax, ay, az, gx, gy, gz):")
    for s in stats['samples']:
        print(f"      ax={s[0]:.4f} ay={s[1]:.4f} az={s[2]:.4f} gx={s[3]:.4f} gy={s[4]:.4f} gz={s[5]:.4f}")

print("\n[3] 找出 ay 异常的记录 (|ay| > 5.0):")
count = 0
for record in parser.parse_file_long_format(DRIVE_FILE):
    ay = record.get('Ay_m_s2', 0)
    if abs(ay) > 5.0:
        count += 1
        if count <= 10:
            print(f"  ch={record['channel']} imu={record['imu_name']} "
                  f"Ax={record['Ax_m_s2']:.4f} Ay={record['Ay_m_s2']:.4f} Az={record['Az_m_s2']:.4f} "
                  f"Gx={record['Gx_dps']:.4f} Gy={record['Gy_dps']:.4f} Gz={record['Gz_dps']:.4f} "
                  f"raw: Ax_raw={record['Ax_raw']} Ay_raw={record['Ay_raw']} Az_raw={record['Az_raw']} "
                  f"Gx_raw={record['Gx_raw']} Gy_raw={record['Gy_raw']} Gz_raw={record['Gz_raw']}")
print(f"  Total异常 records: {count}")