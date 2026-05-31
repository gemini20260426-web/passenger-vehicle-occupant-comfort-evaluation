import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')

from core.core.data_processing.can_parser_v2 import (
    CANFullParser, parse_can_file, extract_imu_frames,
    GYRO_SCALE, ACC_SCALE, IMU_CHANNELS
)

PARK_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001\2026_05_07_180932_ID0001.txt'
DRIVE_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

print("=" * 60)
print("深度诊断: IMU 原始值 vs 偏移量")
print("=" * 60)

parser = CANFullParser()
configs = parser.calibrate(PARK_FILE)

for ch in ['ch4']:
    cfg = configs[ch]
    print(f"\n--- {ch} 偏移量详情 ---")
    print(f"  active_can_ids: {cfg['active_can_ids']}")
    print(f"  n_fields_per_id: {cfg['n_fields_per_id']}")
    print(f"  field_types: {cfg['field_types']}")
    
    idx = 0
    for cid in cfg['active_can_ids']:
        nf = cfg['n_fields_per_id'][cid]
        for j in range(nf):
            offset = cfg['offsets'][idx]
            ft = cfg['field_types'][idx]
            print(f"  [{idx:2d}] {cid}[{j}] offset={offset:10.1f} type={ft}")
            idx += 1

print(f"\n--- 直接读取行驶数据原始值 (前10条 ch4) ---")
drive_records = parse_can_file(DRIVE_FILE)

for ch in ['ch4']:
    cfg = configs[ch]
    frames, _ = extract_imu_frames(drive_records, cfg['active_can_ids'], ch)
    print(f"  Total frames: {len(frames)}")
    
    for fi in range(min(10, len(frames))):
        frame = frames[fi]
        print(f"\n  Frame [{fi}] time={frame['time']:.6f}")
        for pair_8b, pair_4b in [('0x1FFF0051', '0x1FFF0052'), ('0x1FFF0053', '0x1FFF0054')]:
            if pair_8b in frame['data'] and pair_4b in frame['data']:
                import struct
                data_8b = frame['data'][pair_8b]
                data_4b = frame['data'][pair_4b]
                vals_8 = struct.unpack('<4h', data_8b[:8])
                vals_4 = struct.unpack('<2h', data_4b[:4])
                gx_raw, gy_raw, gz_raw, ax_raw = vals_8
                ay_raw, az_raw = vals_4
                print(f"    {pair_8b}+{pair_4b}: gx={gx_raw} gy={gy_raw} gz={gz_raw} ax={ax_raw} ay={ay_raw} az={az_raw}")
                print(f"      raw→phys: gx={GYRO_SCALE*gx_raw:.2f} gy={GYRO_SCALE*gy_raw:.2f} gz={GYRO_SCALE*gz_raw:.2f} ax={ACC_SCALE*ax_raw:.2f} ay={ACC_SCALE*ay_raw:.2f} az={ACC_SCALE*az_raw:.2f}")

print(f"\n--- 检查驻车文件是否真的是静止数据 ---")
park_records = parse_can_file(PARK_FILE)
for ch in ['ch4']:
    cfg = configs[ch]
    frames, _ = extract_imu_frames(park_records, cfg['active_can_ids'], ch)
    print(f"  {ch}: {len(frames)} frames")
    for fi in range(min(5, len(frames))):
        frame = frames[fi]
        print(f"  Frame [{fi}] time={frame['time']:.6f}")
        for pair_8b, pair_4b in [('0x1FFF0051', '0x1FFF0052')]:
            if pair_8b in frame['data'] and pair_4b in frame['data']:
                import struct
                data_8b = frame['data'][pair_8b]
                data_4b = frame['data'][pair_4b]
                vals_8 = struct.unpack('<4h', data_8b[:8])
                vals_4 = struct.unpack('<2h', data_4b[:4])
                print(f"    {pair_8b}+{pair_4b}: raw=({vals_8[0]},{vals_8[1]},{vals_8[2]},{vals_8[3]},{vals_4[0]},{vals_4[1]})")

print(f"\n--- 检查行驶数据中 ch6 车速 (验证数据有效性) ---")
ch6_speed = drive_records.get(('0x100', 'ch6'), [])
if ch6_speed:
    speeds = [r['data'][0] for r in ch6_speed[:20] if len(r['data']) >= 1]
    print(f"  First 20 speed values: {speeds}")
    print(f"  Total 0x100 records: {len(ch6_speed)}")