import sys
sys.path.insert(0, r'd:\UI重构_全量备份_20250824_233403')

from core.core.data_processing.can_parser_v2 import (
    CANFullParser, parse_can_file, extract_imu_frames, 
    extract_raw_values, classify_fields, enforce_3gyro_3accel,
    IMU_CHANNELS, IMU_CAN_IDS, GYRO_SCALE, ACC_SCALE
)

PARK_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001\2026_05_07_180932_ID0001.txt'
DRIVE_FILE = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

print("=" * 60)
print("ch1 标定深度诊断")
print("=" * 60)

park_records = parse_can_file(PARK_FILE)
drive_records = parse_can_file(DRIVE_FILE)

ch = 'ch1'
active_can_ids = []
for cid in IMU_CAN_IDS:
    if (cid, ch) in park_records and len(park_records[(cid, ch)]) > 0:
        active_can_ids.append(cid)

print(f"\n  active_can_ids: {active_can_ids}")

park_frames, n_fields_per_id = extract_imu_frames(park_records, active_can_ids, ch)
drive_frames, _ = extract_imu_frames(drive_records, active_can_ids, ch)

print(f"  park_frames: {len(park_frames)}, drive_frames: {len(drive_frames)}")
print(f"  n_fields_per_id: {n_fields_per_id}")

park_raw = extract_raw_values(park_frames, active_can_ids, n_fields_per_id)
drive_raw = extract_raw_values(drive_frames, active_can_ids, n_fields_per_id) if drive_frames else []

offsets, gyro_scores, dead_fields = classify_fields(park_raw, drive_raw)
field_types = enforce_3gyro_3accel(gyro_scores, offsets, dead_fields)

print(f"\n  Field classification:")
idx = 0
for cid in active_can_ids:
    nf = n_fields_per_id[cid]
    for j in range(nf):
        offset = offsets[idx]
        score = gyro_scores[idx]
        ft = field_types[idx]
        dead = dead_fields[idx]
        
        park_mean = sum(park_raw[idx]) / len(park_raw[idx]) if park_raw[idx] else 0
        park_min = min(park_raw[idx]) if park_raw[idx] else 0
        park_max = max(park_raw[idx]) if park_raw[idx] else 0
        
        drive_mean = sum(drive_raw[idx]) / len(drive_raw[idx]) if idx < len(drive_raw) and drive_raw[idx] else 0
        drive_min = min(drive_raw[idx]) if idx < len(drive_raw) and drive_raw[idx] else 0
        drive_max = max(drive_raw[idx]) if idx < len(drive_raw) and drive_raw[idx] else 0
        
        print(f"  [{idx:2d}] {cid}[{j}] offset={offset:10.1f} score={score:8.2f} type={ft:6s} dead={dead} "
              f"park=[{park_min:.0f},{park_max:.0f}] drive=[{drive_min:.0f},{drive_max:.0f}]")
        idx += 1

print(f"\n  Gyro fields: {[i for i, t in enumerate(field_types) if t == 'Gyro']}")
print(f"  Accel fields: {[i for i, t in enumerate(field_types) if t in ('Accel', 'AccelZ')]}")
print(f"  Dead fields: {[i for i, t in enumerate(field_types) if t == 'Dead']}")

print(f"\n  Expected: 3 gyro + 3 accel per CAN ID pair")
print(f"  For 0x1FFF0051 (indices 0-5): gyro={sum(1 for i in range(6) if field_types[i]=='Gyro')} accel={sum(1 for i in range(6) if field_types[i] in ('Accel','AccelZ'))}")
print(f"  For 0x1FFF0053 (indices 6-11): gyro={sum(1 for i in range(6,12) if field_types[i]=='Gyro')} accel={sum(1 for i in range(6,12) if field_types[i] in ('Accel','AccelZ'))}")

print(f"\n  Comparing with ch4 calibration:")
parser = CANFullParser()
configs = parser.calibrate(PARK_FILE)
ch4_cfg = configs.get('ch4', {})
if ch4_cfg:
    print(f"  ch4 field_types: {ch4_cfg['field_types']}")
    print(f"  ch4 offsets: {[f'{o:.1f}' for o in ch4_cfg['offsets']]}")