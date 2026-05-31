import csv
import os
import struct
import sys
from collections import defaultdict

from .axis_correction import AxisCorrectionEngine

DATA_DIR = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001'
PARK_FILE = '2026_05_07_180932_ID0001.txt'
DRIVE_FILE = '2026_05_08_095939_ID0001.txt'

GYRO_SCALE = 0.07
ACC_SCALE = 9.8 / 1024.0

IMU_CAN_IDS = ['0x1FFF0051', '0x1FFF0052', '0x1FFF0053', '0x1FFF0054']
IMU_CHANNELS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']

IMU_GROUP_A_IDS = ['0x1FFF0053', '0x1FFF0054']  # 实验组
IMU_GROUP_B_IDS = ['0x1FFF0051', '0x1FFF0052']  # 对照组

CH6_VEHICLE_IDS = ['0x100', '0x101', '0x102']

IMU_NAME_MAP = {
    ('ch1', 'group_a'): 'IMU1_头部眉心-1',
    ('ch1', 'group_b'): 'IMU2_头部眉心-2',
    ('ch2', 'group_a'): 'IMU3_躯干T8-1',
    ('ch2', 'group_b'): 'IMU4_躯干T8-2',
    ('ch3', 'group_a'): 'IMU5_座垫R点-1',
    ('ch3', 'group_b'): 'IMU6_座垫R点-2',
    ('ch4', 'group_a'): 'IMU7_座椅底部-1',
    ('ch4', 'group_b'): 'IMU8_座椅底部-2',
    ('ch5', 'group_a'): 'IMU9_胸骨剑突-1',
    ('ch5', 'group_b'): 'IMU10_胸骨剑突-2',
}

LONG_FORMAT_HEADER = [
    'rel_time', 'channel', 'imu_name',
    'Gx_dps', 'Gy_dps', 'Gz_dps',
    'Gx_rad_s', 'Gy_rad_s', 'Gz_rad_s',
    'Ax_m_s2', 'Ay_m_s2', 'Az_m_s2',
    'Gx_raw', 'Gy_raw', 'Gz_raw',
    'Ax_raw', 'Ay_raw', 'Az_raw',
    '车速_kmh', '方向盘转角_deg',
]

def parse_can_file(fpath):
    records = defaultdict(list)
    for encoding in ['gbk', 'utf-8-sig', 'utf-8', 'gb2312', 'latin-1']:
        try:
            with open(fpath, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                header = next(reader)
                for row in reader:
                    if len(row) < 10:
                        continue
                    idx = int(row[0])
                    timestamp_str = row[1].strip('="')
                    rel_time = float(row[2])
                    channel = row[3]
                    can_id = row[4]
                    dlc = int(row[8])
                    hex_str = row[9]
                    if hex_str.startswith('x| '):
                        hex_str = hex_str[3:]
                    hex_bytes = hex_str.strip().split()
                    data_bytes = bytes([int(b, 16) for b in hex_bytes if b])
                    records[(can_id, channel)].append({
                        'idx': idx,
                        'timestamp': timestamp_str,
                        'rel_time': rel_time,
                        'dlc': dlc,
                        'data': data_bytes,
                    })
            break
        except UnicodeDecodeError:
            continue
    return records

def extract_imu_frames(records, active_can_ids, ch, tolerance_ms=2.0):
    id_recs = {}
    for cid in active_can_ids:
        key = (cid, ch)
        if key in records:
            id_recs[cid] = records[key]

    if len(id_recs) != len(active_can_ids):
        return [], {}

    frames = []
    pointers = {cid: 0 for cid in active_can_ids}

    while True:
        times = {}
        for cid in active_can_ids:
            if pointers[cid] >= len(id_recs[cid]):
                break
            times[cid] = id_recs[cid][pointers[cid]]['rel_time']
        
        if len(times) != len(active_can_ids):
            break

        t_min = min(times.values())
        t_max = max(times.values())

        if t_max - t_min <= tolerance_ms / 1000.0:
            frame_data = {}
            for cid in active_can_ids:
                r = id_recs[cid][pointers[cid]]
                frame_data[cid] = r['data']
                pointers[cid] += 1
            frames.append({
                'time': sum(times.values()) / len(times),
                'data': frame_data
            })
        else:
            slowest = min(times, key=times.get)
            pointers[slowest] += 1

    n_fields_per_id = {}
    for cid in active_can_ids:
        if frames:
            n_fields_per_id[cid] = len(frames[0]['data'][cid]) // 2

    return frames, n_fields_per_id

def extract_raw_values(frames, active_can_ids, n_fields_per_id):
    total_fields = sum(n_fields_per_id.values())
    all_raw = [[] for _ in range(total_fields)]

    for f in frames:
        idx = 0
        for cid in active_can_ids:
            data = f['data'][cid]
            nf = n_fields_per_id[cid]
            for j in range(nf):
                if j*2+1 < len(data):
                    v = struct.unpack('<h', data[j*2:j*2+2])[0]
                    all_raw[idx].append(v)
                idx += 1

    return all_raw

def classify_fields(park_raw, drive_raw):
    n_fields = len(park_raw)
    offsets = []
    dead_fields = []
    for vals in park_raw:
        offsets.append(sum(vals) / len(vals) if vals else 0)
        dead_fields.append(len(set(vals)) <= 1 and abs(vals[0]) <= 1 if vals else True)

    gyro_scores = []
    for i in range(n_fields):
        offset = offsets[i]
        score = 0.0

        if dead_fields[i]:
            gyro_scores.append(-999.0)
            continue

        if abs(offset) > 500:
            score += 2.0
        elif abs(offset) > 200:
            score += 1.0

        if abs(offset - 4096) < 1500:
            score -= 3.0

        if i < len(drive_raw) and drive_raw[i]:
            d_vals = drive_raw[i]
            g_vals = [GYRO_SCALE * (v - offset) for v in d_vals]
            a_vals = [ACC_SCALE * (v - offset) for v in d_vals]

            g_range = max(abs(min(g_vals)), abs(max(g_vals)))
            a_range = max(abs(min(a_vals)), abs(max(a_vals)))

            if g_range < 300:
                score += 1.0
            if g_range > 500:
                score -= 1.0

            if a_range < 30:
                score -= 1.0
            if a_range > 50:
                score += 1.0

            raw_range = max(d_vals) - min(d_vals)
            if raw_range > 2000:
                score += 1.5
            if raw_range < 200:
                score -= 0.5

        gyro_scores.append(score)

    return offsets, gyro_scores, dead_fields

def enforce_3gyro_3accel(gyro_scores, offsets, dead_fields):
    n = len(gyro_scores)
    field_types = ['Accel'] * n
    group_size = 6

    for i in range(n):
        if dead_fields[i]:
            field_types[i] = 'Dead'

    for group_start in range(0, n, group_size):
        group_end = min(group_start + group_size, n)
        group_indices = [i for i in range(group_start, group_end) if not dead_fields[i]]
        group_n = len(group_indices)

        if group_n == 0:
            continue

        n_gyro = group_n // 2

        ranked = sorted(group_indices, key=lambda i: gyro_scores[i], reverse=True)

        for i in ranked[:n_gyro]:
            field_types[i] = 'Gyro'

        best_accelz = -1
        best_accelz_dist = float('inf')
        for i in group_indices:
            if field_types[i] == 'Accel':
                dist = abs(offsets[i] - 4096)
                if dist < best_accelz_dist:
                    best_accelz_dist = dist
                    best_accelz = i

        if best_accelz >= 0 and best_accelz_dist < 3000:
            field_types[best_accelz] = 'AccelZ'

        if group_n == group_size:
            expected_gyro_positions = list(range(group_start + 3, group_end))
            actual_gyro_positions = [i for i in group_indices if field_types[i] == 'Gyro']
            if set(actual_gyro_positions) != set(expected_gyro_positions):
                for i in group_indices:
                    if field_types[i] != 'Dead':
                        rel_pos = (i - group_start) % group_size
                        field_types[i] = 'Gyro' if rel_pos >= 3 else 'Accel'
                best_accelz = -1
                best_accelz_dist = float('inf')
                for i in group_indices:
                    if field_types[i] == 'Accel':
                        dist = abs(offsets[i] - 4096)
                        if dist < best_accelz_dist:
                            best_accelz_dist = dist
                            best_accelz = i
                if best_accelz >= 0 and best_accelz_dist < 3000:
                    field_types[best_accelz] = 'AccelZ'

    return field_types

def convert_value(raw, offset, field_type):
    if field_type == 'Dead':
        return 0.0
    if field_type == 'Gyro':
        return GYRO_SCALE * (raw - offset)
    else:
        return ACC_SCALE * (raw - offset)

def get_field_unit(field_type):
    if field_type == 'Dead':
        return 'na'
    return 'dps' if field_type == 'Gyro' else 'm/s2'

class CANFullParser:
    """
    全量多通道CAN数据解析器

    解析CAN CSV文件，同时处理所有IMU通道(ch1/ch3/ch4/ch5)和车辆信号(ch6)，
    输出标准化的多通道IMU数据。

    用法:
        parser = CANFullParser()
        parser.calibrate('park_file.txt')
        for record in parser.parse_file('drive_file.txt'):
            print(record['ch1_ax'], record['ch4_gx'])
    """

    def __init__(self, park_file_path=None, axis_correction_config=None):
        self.park_file_path = park_file_path
        self._channel_configs = {}
        self._calibrated = False
        self.success_count = 0
        self.error_count = 0
        self._correction_engine = AxisCorrectionEngine.from_config(axis_correction_config)

    def calibrate(self, park_file_path=None):
        park_path = park_file_path or self.park_file_path
        if not park_path:
            raise ValueError("驻车标定文件路径未提供")

        park_records = parse_can_file(park_path)

        for ch in IMU_CHANNELS:
            active_can_ids = []
            for cid in IMU_CAN_IDS:
                if (cid, ch) in park_records and len(park_records[(cid, ch)]) > 0:
                    active_can_ids.append(cid)

            if not active_can_ids:
                continue

            park_frames, n_fields_per_id = extract_imu_frames(
                park_records, active_can_ids, ch)

            if not park_frames:
                continue

            park_raw = extract_raw_values(park_frames, active_can_ids, n_fields_per_id)
            offsets, gyro_scores, dead_fields = classify_fields(park_raw, [])
            field_types = enforce_3gyro_3accel(gyro_scores, offsets, dead_fields)

            self._channel_configs[ch] = {
                'active_can_ids': active_can_ids,
                'n_fields_per_id': n_fields_per_id,
                'offsets': offsets,
                'field_types': field_types,
                'gyro_scores': gyro_scores,
            }

        self._calibrated = True
        return self._channel_configs

    def auto_calibrate_from_file(self, file_path, park_duration_sec=2.0):
        """从文件开头自动提取驻车数据进行校准
        
        Args:
            file_path: 数据文件路径
            park_duration_sec: 驻车数据持续时间（秒），默认2秒
        """
        records = parse_can_file(file_path)
        
        for ch in IMU_CHANNELS:
            active_can_ids = []
            for cid in IMU_CAN_IDS:
                if (cid, ch) in records and len(records[(cid, ch)]) > 0:
                    active_can_ids.append(cid)

            if not active_can_ids:
                continue

            # 提取前 park_duration_sec 秒的数据作为驻车数据
            park_records = {}
            for cid in active_can_ids:
                key = (cid, ch)
                if key in records:
                    all_recs = records[key]
                    # 取前 N 秒的数据
                    park_recs = [r for r in all_recs if r['rel_time'] <= park_duration_sec]
                    if park_recs:
                        park_records[key] = park_recs

            if not park_records:
                continue

            park_frames, n_fields_per_id = extract_imu_frames(
                park_records, active_can_ids, ch)

            if not park_frames:
                continue

            park_raw = extract_raw_values(park_frames, active_can_ids, n_fields_per_id)
            offsets, gyro_scores, dead_fields = classify_fields(park_raw, [])
            field_types = enforce_3gyro_3accel(gyro_scores, offsets, dead_fields)

            self._channel_configs[ch] = {
                'active_can_ids': active_can_ids,
                'n_fields_per_id': n_fields_per_id,
                'offsets': offsets,
                'field_types': field_types,
                'gyro_scores': gyro_scores,
            }

        self._calibrated = True
        return self._channel_configs

    def parse_file(self, file_path, progress_callback=None):
        if not self._calibrated:
            raise RuntimeError("请先调用 calibrate() 进行驻车标定")

        records = parse_can_file(file_path)
        ch6_data = {}
        for cid in CH6_VEHICLE_IDS:
            key = (cid, 'ch6')
            if key in records:
                ch6_data[cid] = records[key]

        all_frames = {}
        for ch in IMU_CHANNELS:
            if ch not in self._channel_configs:
                continue
            cfg = self._channel_configs[ch]
            frames, _ = extract_imu_frames(records, cfg['active_can_ids'], ch)
            all_frames[ch] = frames

        max_frames = max((len(f) for f in all_frames.values()), default=0)
        ch6_ptr = {cid: 0 for cid in ch6_data}

        _offset_lookups = {}
        _field_type_lookups = {}
        for ch in IMU_CHANNELS:
            if ch in self._channel_configs:
                cfg = self._channel_configs[ch]
                lookup = {}
                ft_lookup = {}
                idx = 0
                for cid in cfg['active_can_ids']:
                    nf = cfg['n_fields_per_id'][cid]
                    for j in range(nf):
                        lookup[(cid, j)] = cfg['offsets'][idx]
                        ft_lookup[(cid, j)] = cfg['field_types'][idx]
                        idx += 1
                _offset_lookups[ch] = lookup
                _field_type_lookups[ch] = ft_lookup

        for fi in range(max_frames):
            try:
                record = {'cnt': fi}

                for ch in IMU_CHANNELS:
                    if ch not in all_frames or fi >= len(all_frames[ch]):
                        continue
                    frame = all_frames[ch][fi]
                    t = frame['time']
                    record['timestamp'] = t

                    imu_pairs = [('0x1FFF0051', '0x1FFF0052'), ('0x1FFF0053', '0x1FFF0054')]
                    ax, ay, az, gx, gy, gz = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                    for pair_8b, pair_4b in imu_pairs:
                        if pair_8b not in frame['data'] or pair_4b not in frame['data']:
                            continue
                        data_8b = frame['data'][pair_8b]
                        data_4b = frame['data'][pair_4b]
                        vals_8 = struct.unpack('<4h', data_8b[:8])
                        vals_4 = struct.unpack('<2h', data_4b[:4])

                        ol = _offset_lookups.get(ch, {})
                        ft = _field_type_lookups.get(ch, {})

                        raw_fields = [
                            (pair_8b, 0, vals_8[0]),
                            (pair_8b, 1, vals_8[1]),
                            (pair_8b, 2, vals_8[2]),
                            (pair_8b, 3, vals_8[3]),
                            (pair_4b, 0, vals_4[0]),
                            (pair_4b, 1, vals_4[1]),
                        ]

                        accel_vals = []
                        gyro_vals = []
                        for cid, fidx, raw in raw_fields:
                            field_type = ft.get((cid, fidx), 'Accel')
                            offset = ol.get((cid, fidx), 0)
                            if field_type in ('Accel', 'AccelZ'):
                                accel_vals.append(ACC_SCALE * (raw - offset))
                            else:
                                gyro_vals.append(GYRO_SCALE * (raw - offset))

                        if len(accel_vals) >= 3 and len(gyro_vals) >= 3:
                            local_ax, local_ay, local_az = accel_vals[0], accel_vals[1], accel_vals[2]
                            local_gx, local_gy, local_gz = gyro_vals[0], gyro_vals[1], gyro_vals[2]
                            if ax == 0.0 and ay == 0.0 and az == 0.0 and gx == 0.0 and gy == 0.0 and gz == 0.0:
                                ax, ay, az, gx, gy, gz = local_ax, local_ay, local_az, local_gx, local_gy, local_gz

                    record[f'{ch}_ax'] = round(ax, 6)
                    record[f'{ch}_ay'] = round(ay, 6)
                    record[f'{ch}_az'] = round(az, 6)
                    record[f'{ch}_gx'] = round(gx, 6)
                    record[f'{ch}_gy'] = round(gy, 6)
                    record[f'{ch}_gz'] = round(gz, 6)

                t = record.get('timestamp', 0)
                speed = 0
                reverse = 0
                steering = 0.0
                emergency_brake = 0
                brake_pressure = 0.0
                for cid in CH6_VEHICLE_IDS:
                    if cid not in ch6_data:
                        continue
                    recs = ch6_data[cid]
                    ptr = ch6_ptr[cid]
                    while ptr < len(recs) and recs[ptr]['rel_time'] < t - 0.05:
                        ptr += 1
                    ch6_ptr[cid] = ptr
                    if ptr < len(recs) and abs(recs[ptr]['rel_time'] - t) < 0.1:
                        r = recs[ptr]
                        if cid == '0x100' and len(r['data']) >= 2:
                            speed = r['data'][0]
                            reverse = 1 if r['data'][1] == 1 else 0
                        elif cid == '0x101' and len(r['data']) >= 2:
                            steering = struct.unpack('>h', r['data'][0:2])[0]
                        elif cid == '0x102' and len(r['data']) >= 4:
                            emergency_brake = r['data'][0]
                            brake_pressure = (r['data'][2] << 8) | r['data'][3]

                record['speed'] = speed
                record['reverse'] = reverse
                record['steering'] = steering
                record['emergency_brake'] = emergency_brake
                record['brake_pressure'] = brake_pressure

                self.success_count += 1
                yield record

            except Exception:
                self.error_count += 1
                continue

            if progress_callback and fi % 100 == 0:
                progress_callback(fi, max_frames)

    def stream_parse_file(self, file_path, data_callback, progress_callback=None):
        if not self._calibrated:
            park_path = self.park_file_path
            if park_path and os.path.exists(park_path):
                try:
                    self.calibrate(park_path)
                except Exception:
                    self._set_default_calibration()
            else:
                import glob as _glob
                drive_dir = os.path.dirname(file_path)
                candidates = (
                    _glob.glob(drive_dir + '/*park*') +
                    _glob.glob(drive_dir + '/*Park*') +
                    _glob.glob(drive_dir + '/*PARK*') +
                    _glob.glob(drive_dir + '/*驻车*') +
                    _glob.glob(drive_dir + '/*stop*') +
                    _glob.glob(drive_dir + '/*Stop*')
                )
                candidates = [c for c in candidates
                              if not os.path.basename(c).startswith('parsed_')
                              and not os.path.basename(c).startswith('Parsed_')]
                if candidates:
                    try:
                        self.calibrate(candidates[0])
                    except Exception:
                        self.auto_calibrate_from_file(file_path)
                else:
                    self.auto_calibrate_from_file(file_path)

        for record in self.parse_file(file_path, progress_callback):
            data_callback(record)

    def parse_file_long_format(self, file_path, progress_callback=None):
        if not self._calibrated:
            raise RuntimeError("请先调用 calibrate() 进行驻车标定")

        records = parse_can_file(file_path)

        ch6_data = {}
        for cid in CH6_VEHICLE_IDS:
            key = (cid, 'ch6')
            if key in records:
                ch6_data[cid] = records[key]

        all_frames = {}
        for ch in IMU_CHANNELS:
            if ch not in self._channel_configs:
                continue
            cfg = self._channel_configs[ch]
            frames, _ = extract_imu_frames(records, cfg['active_can_ids'], ch)
            all_frames[ch] = frames

        max_frames = max((len(f) for f in all_frames.values()), default=0)
        ch6_ptr = {cid: 0 for cid in ch6_data}

        _offset_lookups_long = {}
        _field_type_lookups_long = {}
        for ch in IMU_CHANNELS:
            if ch in self._channel_configs:
                cfg = self._channel_configs[ch]
                lookup = {}
                ft_lookup = {}
                idx = 0
                for cid in cfg['active_can_ids']:
                    nf = cfg['n_fields_per_id'][cid]
                    for j in range(nf):
                        lookup[(cid, j)] = cfg['offsets'][idx]
                        ft_lookup[(cid, j)] = cfg['field_types'][idx]
                        idx += 1
                _offset_lookups_long[ch] = lookup
                _field_type_lookups_long[ch] = ft_lookup

        for fi in range(max_frames):
            try:
                frame_time = None
                for ch in IMU_CHANNELS:
                    if ch in all_frames and fi < len(all_frames[ch]):
                        frame_time = all_frames[ch][fi]['time']
                        break
                if frame_time is None:
                    continue

                speed = 0
                steering = 0.0
                for cid in CH6_VEHICLE_IDS:
                    if cid not in ch6_data:
                        continue
                    recs = ch6_data[cid]
                    ptr = ch6_ptr[cid]
                    while ptr < len(recs) and recs[ptr]['rel_time'] < frame_time - 0.05:
                        ptr += 1
                    ch6_ptr[cid] = ptr
                    if ptr < len(recs) and abs(recs[ptr]['rel_time'] - frame_time) < 0.1:
                        r = recs[ptr]
                        if cid == '0x100' and len(r['data']) >= 2:
                            speed = r['data'][0]
                        elif cid == '0x101' and len(r['data']) >= 2:
                            steering = struct.unpack('>h', r['data'][0:2])[0]

                for ch in IMU_CHANNELS:
                    if ch not in all_frames or fi >= len(all_frames[ch]):
                        continue
                    frame = all_frames[ch][fi]

                    imu_pairs = [('0x1FFF0051', '0x1FFF0052'), ('0x1FFF0053', '0x1FFF0054')]
                    for pair_8b, pair_4b in imu_pairs:
                        if pair_8b not in frame['data'] or pair_4b not in frame['data']:
                            continue

                        data_8b = frame['data'][pair_8b]
                        data_4b = frame['data'][pair_4b]

                        vals_8 = struct.unpack('<4h', data_8b[:8])
                        vals_4 = struct.unpack('<2h', data_4b[:4])

                        ol = _offset_lookups_long.get(ch, {})
                        ft = _field_type_lookups_long.get(ch, {})

                        raw_fields = [
                            (pair_8b, 0, vals_8[0]),
                            (pair_8b, 1, vals_8[1]),
                            (pair_8b, 2, vals_8[2]),
                            (pair_8b, 3, vals_8[3]),
                            (pair_4b, 0, vals_4[0]),
                            (pair_4b, 1, vals_4[1]),
                        ]

                        accel_vals = []
                        gyro_vals = []
                        accel_raws = []
                        gyro_raws = []
                        for cid, fidx, raw in raw_fields:
                            field_type = ft.get((cid, fidx), 'Accel')
                            offset = ol.get((cid, fidx), 0)
                            if field_type in ('Accel', 'AccelZ'):
                                accel_vals.append(ACC_SCALE * (raw - offset))
                                accel_raws.append(raw)
                            else:
                                gyro_vals.append(GYRO_SCALE * (raw - offset))
                                gyro_raws.append(raw)

                        if len(accel_vals) < 3 or len(gyro_vals) < 3:
                            continue

                        ax_ms2, ay_ms2, az_ms2 = accel_vals[0], accel_vals[1], accel_vals[2]
                        gx_dps, gy_dps, gz_dps = gyro_vals[0], gyro_vals[1], gyro_vals[2]
                        ax_raw, ay_raw, az_raw = accel_raws[0], accel_raws[1], accel_raws[2]
                        gx_raw, gy_raw, gz_raw = gyro_raws[0], gyro_raws[1], gyro_raws[2]

                        import math
                        gx_rad_s = math.radians(gx_dps)
                        gy_rad_s = math.radians(gy_dps)
                        gz_rad_s = math.radians(gz_dps)

                        group = 'group_b' if pair_8b in IMU_GROUP_B_IDS else 'group_a'
                        imu_name = IMU_NAME_MAP.get((ch, group), f'{ch}_{group}')

                        record = {
                            'rel_time': round(frame['time'], 6),
                            'channel': ch,
                            'imu_name': imu_name,
                            '_imu_name': imu_name,
                            '_source_type': 'can_long',
                            '_source_id': imu_name,
                            'ax': round(ax_ms2, 6),
                            'ay': round(ay_ms2, 6),
                            'az': round(az_ms2, 6),
                            'gx': round(math.radians(gx_dps), 10),
                            'gy': round(math.radians(gy_dps), 10),
                            'gz': round(math.radians(gz_dps), 10),
                            'speed': speed,
                            'wheel': steering,
                            'Gx_dps': round(gx_dps, 4),
                            'Gy_dps': round(gy_dps, 4),
                            'Gz_dps': round(gz_dps, 4),
                            'Gx_rad_s': round(gx_rad_s, 10),
                            'Gy_rad_s': round(gy_rad_s, 10),
                            'Gz_rad_s': round(gz_rad_s, 10),
                            'Ax_m_s2': round(ax_ms2, 4),
                            'Ay_m_s2': round(ay_ms2, 4),
                            'Az_m_s2': round(az_ms2, 4),
                            'Gx_raw': gx_raw,
                            'Gy_raw': gy_raw,
                            'Gz_raw': gz_raw,
                            'Ax_raw': ax_raw,
                            'Ay_raw': ay_raw,
                            'Az_raw': az_raw,
                            '车速_kmh': speed,
                            '方向盘转角_deg': steering,
                        }
                        if self._correction_engine.enabled:
                            record = self._correction_engine.correct_record(record)
                        self.success_count += 1
                        yield record

            except Exception:
                self.error_count += 1
                continue

            if progress_callback and fi % 100 == 0:
                progress_callback(fi, max_frames)

    def parse_file_pipeline_format(self, file_path, imu_filter='IMU-04_座椅底部_对照组',
                                    progress_callback=None):
        for record in self.parse_file_long_format(file_path, progress_callback):
            imu_name = record.get('imu_name', '')
            if imu_filter and imu_filter not in imu_name:
                continue

            yield {
                'timestamp': record.get('rel_time', 0),
                'ax': record.get('Ax_m_s2', 0),
                'ay': record.get('Ay_m_s2', 0),
                'az': record.get('Az_m_s2', 0),
                'gx': record.get('Gx_rad_s', 0),
                'gy': record.get('Gy_rad_s', 0),
                'gz': record.get('Gz_rad_s', 0),
                'speed': record.get('车速_kmh', 0),
                'wheel': record.get('方向盘转角_deg', 0),
                'loc1': 0.0,
                'loc2': 0.0,
            }

    def export_to_csv(self, file_path, output_dir=None):
        import time as _time
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                'data_output'
            )

        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = _time.strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'CAN全量解析_{base_name}_{timestamp}.csv')

        row_count = 0
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(LONG_FORMAT_HEADER)

            for record in self.parse_file_long_format(file_path):
                row = [record.get(col, '') for col in LONG_FORMAT_HEADER]
                writer.writerow(row)
                row_count += 1

        file_size = os.path.getsize(output_file)
        return {
            'output_file': output_file,
            'row_count': row_count,
            'file_size': file_size,
        }

    def _set_default_calibration(self):
        self._calibrated = True
        for ch in IMU_CHANNELS:
            self._channel_configs[ch] = {
                'active_can_ids': ['0x1FFF0051', '0x1FFF0052', '0x1FFF0053', '0x1FFF0054'],
                'n_fields_per_id': {
                    '0x1FFF0051': 4, '0x1FFF0052': 2,
                    '0x1FFF0053': 4, '0x1FFF0054': 2
                },
                'offsets': [0] * 12,
                'field_types': [
                    'Accel', 'Accel', 'AccelZ', 'Gyro', 'Gyro', 'Gyro',
                    'Accel', 'Accel', 'AccelZ', 'Gyro', 'Gyro', 'Gyro',
                ],
                'gyro_scores': [0] * 12,
            }

    def parse_line(self, line_str):
        return None

    def parse_content(self, content):
        import csv
        import io

        def _f(val, default=0.0):
            try:
                if val is None or (isinstance(val, str) and val.strip() == ''):
                    return default
                return float(val)
            except (ValueError, TypeError):
                return default

        results = []
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            channel = row.get('channel', '')
            rel_time = _f(row.get('rel_time_s', row.get('rel_time', '0')))
            if channel == 'ch6':
                results.append({
                    'rel_time': round(rel_time, 6),
                    'channel': channel,
                    '车速_kmh': _f(row.get('ch6_0x100_speed_kmh')),
                    '方向盘转角_deg': _f(row.get('ch6_0x101_steering_deg')),
                })
                continue
            if channel not in IMU_CHANNELS:
                continue
            for imu_idx, (pair_8b, ctrl_label) in enumerate([
                    ('0x1FFF0051', '_实验组'), ('0x1FFF0053', '_对照组')
            ]):
                imu_name = IMU_NAME_MAP.get((channel, pair_8b), f'{channel}_{pair_8b}')
                base = imu_idx * 6
                results.append({
                    'rel_time': round(rel_time, 6),
                    'channel': channel,
                    'imu_name': imu_name,
                    'Ax_m_s2': _f(row.get(f'{channel}_f{base}_Accel_m/s2')),
                    'Ay_m_s2': _f(row.get(f'{channel}_f{base+1}_Accel_m/s2')),
                    'Az_m_s2': _f(row.get(f'{channel}_f{base+2}_Accel_m/s2')),
                    'Gx_dps': _f(row.get(f'{channel}_f{base+3}_Gyro_dps')),
                    'Gy_dps': _f(row.get(f'{channel}_f{base+4}_Gyro_dps')),
                    'Gz_dps': _f(row.get(f'{channel}_f{base+5}_Gyro_dps')),
                    '车速_kmh': _f(row.get('ch6_0x100_speed_kmh')),
                    '方向盘转角_deg': _f(row.get('ch6_0x101_steering_deg')),
                })
        self.success_count = len(results)
        return results

    @staticmethod
    def analyze_file_structure(file_path, sample_lines=500):
        records = parse_can_file(file_path)

        channels_info = {}
        for ch in IMU_CHANNELS:
            can_ids_found = []
            for cid in IMU_CAN_IDS:
                key = (cid, ch)
                if key in records and len(records[key]) > 0:
                    can_ids_found.append(cid)

            if not can_ids_found:
                continue

            record_count = sum(len(records[(cid, ch)]) for cid in can_ids_found)

            channels_info[ch] = {
                'can_ids': can_ids_found,
                'record_count': record_count,
            }

        vehicle_can_ids = []
        for cid in CH6_VEHICLE_IDS:
            key = (cid, 'ch6')
            if key in records and len(records[key]) > 0:
                vehicle_can_ids.append(cid)

        total_records = sum(len(v) for v in records.values())

        return {
            'file_type': 'CAN_Gateway_Full_CSV',
            'total_records': total_records,
            'channels': channels_info,
            'vehicle_channel': {
                'can_ids': vehicle_can_ids,
            },
        }


def _run_standalone_parsing():
    print("=" * 60)
    print("CAN Data Parser - IMU + Vehicle Signals")
    print("=" * 60)

    print("\n[1/4] Loading data files...")
    park_records = parse_can_file(os.path.join(DATA_DIR, PARK_FILE))
    drive_records = parse_can_file(os.path.join(DATA_DIR, DRIVE_FILE))
    print(f"  Park: {sum(len(v) for v in park_records.values())} records")
    print(f"  Drive: {sum(len(v) for v in drive_records.values())} records")
    
    print("\n[2/4] Analyzing IMU field layout and calculating offsets...")
    channel_configs = {}
    
    for ch in IMU_CHANNELS:
        active_can_ids = []
        for cid in IMU_CAN_IDS:
            if (cid, ch) in park_records and len(park_records[(cid, ch)]) > 0:
                active_can_ids.append(cid)
    
        if not active_can_ids:
            print(f"  {ch}: No data, skipping")
            continue
    
        park_frames, n_fields_per_id = extract_imu_frames(park_records, active_can_ids, ch)
        drive_frames, _ = extract_imu_frames(drive_records, active_can_ids, ch)
    
        if not park_frames:
            print(f"  {ch}: No aligned frames, skipping")
            continue
    
        park_raw = extract_raw_values(park_frames, active_can_ids, n_fields_per_id)
        drive_raw = extract_raw_values(drive_frames, active_can_ids, n_fields_per_id) if drive_frames else []
    
        offsets, gyro_scores, dead_fields = classify_fields(park_raw, drive_raw)
        field_types = enforce_3gyro_3accel(gyro_scores, offsets, dead_fields)
    
        channel_configs[ch] = {
            'active_can_ids': active_can_ids,
            'n_fields_per_id': n_fields_per_id,
            'offsets': offsets,
            'field_types': field_types,
            'gyro_scores': gyro_scores,
        }
    
        n_frames = len(park_frames)
        n_fields = len(offsets)
        types_str = ', '.join(f'{i}:{t}' for i, t in enumerate(field_types))
        print(f"  {ch}: {n_frames} frames, {n_fields} fields, CAN IDs={active_can_ids}")
        print(f"       {types_str}")
    
    print("\n[3/4] Parsing and writing output CSV files...")
    
    header = ['rel_time_s', 'timestamp', 'channel']
    col_map = {}
    for ch in IMU_CHANNELS:
        if ch in channel_configs:
            cfg = channel_configs[ch]
            for i, ft in enumerate(cfg['field_types']):
                unit = get_field_unit(ft)
                col_map[(ch, i)] = len(header)
                header.append(f'{ch}_f{i}_{ft}_{unit}')
    veh_col_start = len(header)
    header.extend([
        'ch6_0x100_speed_kmh',
        'ch6_0x100_reverse',
        'ch6_0x101_steering_deg',
        'ch6_0x102_emergency_brake',
        'ch6_0x102_brake_pressure',
    ])
    total_cols = len(header)
    
    for file_label, file_name, records in [
        ('park', PARK_FILE, park_records),
        ('drive', DRIVE_FILE, drive_records)
    ]:
        output_file = os.path.join(DATA_DIR, f'parsed_{file_label}.csv')
    
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)
    
            for ch in IMU_CHANNELS:
                if ch not in channel_configs:
                    continue
    
                cfg = channel_configs[ch]
                frames, _ = extract_imu_frames(records, cfg['active_can_ids'], ch)
    
                ch6_data = {}
                for cid in CH6_VEHICLE_IDS:
                    key = (cid, 'ch6')
                    if key in records:
                        ch6_data[cid] = records[key]
    
                ch6_ptr = {cid: 0 for cid in ch6_data}
    
                for frame in frames:
                    row = [''] * total_cols
                    row[0] = round(frame['time'], 6)
                    row[1] = ''
                    row[2] = ch
    
                    idx = 0
                    for cid in cfg['active_can_ids']:
                        data = frame['data'][cid]
                        nf = cfg['n_fields_per_id'][cid]
                        for j in range(nf):
                            col = col_map.get((ch, idx))
                            if col is not None and j*2+1 < len(data):
                                raw = struct.unpack('<h', data[j*2:j*2+2])[0]
                                offset = cfg['offsets'][idx]
                                ft = cfg['field_types'][idx]
                                val = convert_value(raw, offset, ft)
                                row[col] = round(val, 4)
                            idx += 1
    
                    t = frame['time']
                    speed = ''
                    reverse = ''
                    steering = ''
                    emergency_brake = ''
                    brake_pressure = ''
    
                    for cid in CH6_VEHICLE_IDS:
                        if cid not in ch6_data:
                            continue
                        recs = ch6_data[cid]
                        ptr = ch6_ptr[cid]
                        while ptr < len(recs) and recs[ptr]['rel_time'] < t - 0.05:
                            ptr += 1
                        ch6_ptr[cid] = ptr
    
                        if ptr < len(recs) and abs(recs[ptr]['rel_time'] - t) < 0.1:
                            r = recs[ptr]
                            if cid == '0x100' and len(r['data']) >= 2:
                                speed = r['data'][0]
                                reverse = r['data'][1]
                            elif cid == '0x101' and len(r['data']) >= 2:
                                steering = struct.unpack('>h', r['data'][0:2])[0]
                            elif cid == '0x102' and len(r['data']) >= 4:
                                emergency_brake = r['data'][0]
                                brake_pressure = (r['data'][2] << 8) | r['data'][3]
    
                    row[veh_col_start] = speed
                    row[veh_col_start + 1] = reverse
                    row[veh_col_start + 2] = steering
                    row[veh_col_start + 3] = emergency_brake
                    row[veh_col_start + 4] = brake_pressure
                    writer.writerow(row)
    
        file_size = os.path.getsize(output_file)
        print(f"  {output_file} ({file_size:,} bytes)")
    
    print("\n[4/4] Writing summary report...")
    report_file = os.path.join(DATA_DIR, 'parsing_report.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("CAN Data Parsing Report\n")
        f.write("=" * 60 + "\n\n")
    
        f.write("Data Sources:\n")
        f.write(f"  Parking mode: {PARK_FILE}\n")
        f.write(f"  Driving mode:  {DRIVE_FILE}\n\n")
    
        f.write("Conversion Formulas (from IMU developer code):\n")
        f.write(f"  Gyroscope:      {GYRO_SCALE:.10f} * (raw - offset)  [dps]\n")
        f.write(f"  Accelerometer:  {ACC_SCALE:.10f} * (raw - offset)  [m/s^2]\n")
        f.write(f"  Vehicle Speed:  byte[0] 0~255 km/h (from 0x100)\n")
        f.write(f"  Reverse Gear:   byte[1] 0=forward 1=reverse (from 0x100)\n")
        f.write(f"  Steering Angle: int16 BE -540~540 deg (from 0x101 byte[0:2])\n")
        f.write(f"  Emergency Brake: byte[0] 0=normal 1=emergency (from 0x102)\n")
        f.write(f"  Brake Pressure: uint16 BE 0~1000 (from 0x102 byte[2:4])\n\n")
    
        f.write("IMU Sensor Configuration:\n")
        f.write("-" * 40 + "\n")
        f.write("Each ASM330LHH sensor provides 6 axes (3 gyro + 3 accelerometer).\n")
        f.write("Data is transmitted via CAN bus with IDs 0x1FFF0051-0x1FFF0054.\n")
        f.write("Two CAN IDs form one IMU pair (0x1FFF0051+0x1FFF0052 or 0x1FFF0053+0x1FFF0054).\n\n")
    
        for ch in IMU_CHANNELS:
            if ch not in channel_configs:
                f.write(f"{ch}: No data available\n\n")
                continue
    
            cfg = channel_configs[ch]
            n_sensors = len(cfg['active_can_ids']) // 2
            f.write(f"{ch}: {n_sensors} IMU sensor(s), CAN IDs: {cfg['active_can_ids']}\n")
    
            idx = 0
            for cid in cfg['active_can_ids']:
                nf = cfg['n_fields_per_id'][cid]
                for j in range(nf):
                    offset = cfg['offsets'][idx]
                    ft = cfg['field_types'][idx]
                    score = cfg['gyro_scores'][idx]
                    unit = get_field_unit(ft)
                    f.write(f"  [{idx:2d}] {cid}[{j}] offset={offset:10.1f} type={ft:6s} score={score:+5.1f} unit={unit}\n")
                    idx += 1
            f.write("\n")
    
        f.write("ch6 Vehicle CAN IDs:\n")
        f.write("-" * 40 + "\n")
        f.write("  0x100:  Vehicle speed (byte[0]: 0~255 km/h) + reverse gear (byte[1]: 0/1)\n")
        f.write("  0x101:  Steering wheel angle (int16 BE, -540~540 deg) at byte[0:2]\n")
        f.write("  0x102:  Emergency brake (byte[0]: 0/1) + brake pressure (uint16 BE, 0~1000) at byte[2:4]\n\n")
    
        f.write("Notes:\n")
        f.write("- Offsets calculated from parking mode (vehicle stationary)\n")
        f.write("- ch2 (IMU-02, torso T8) has been deprecated and removed\n")
        f.write("- ch5 (IMU-05, sternum xiphoid) replaces ch2 as torso IMU\n")
        f.write("- ch5 uses 0x1FFF0053/54 (one IMU sensor), data rate is 2x\n")
        f.write("- Vehicle speed from 0x1702: parking=0.02 km/h, driving up to ~18 km/h\n")
    
    print(f"  {report_file}")
    
    print("\n" + "=" * 60)
    print("Parsing complete! Output files:")
    print(f"  {os.path.join(DATA_DIR, 'parsed_park.csv')}")
    print(f"  {os.path.join(DATA_DIR, 'parsed_drive.csv')}")
    print(f"  {report_file}")
    print("=" * 60)
if __name__ == '__main__':
    _run_standalone_parsing()
