#!/usr/bin/env python3
"""
CAN网关 + IMU 数据解析脚本
============================
解析 CAN 服务网关采集的数据文件：
  - ch1~ch5: 10路六轴IMU数据 (ASM3301HH传感器)
  - ch6: 车机CAN总线数据 (车速/方向盘/刹车等)

IMU 传感器型号: ST ASM3301HH
  陀螺仪: 系数 0.07 (dps/LSB)
  加速度计: ±8 g,  比例因子 9.8/4096.0  (m/s²/LSB)

用法:
  python can_imu_parser.py <数据文件.txt> [输出前缀]
"""

import re
import struct
import sys
import os
from collections import defaultdict
import csv

# ============================================================
# 配置区
# ============================================================

# 陀螺仪量程 ±500 dps → 比例 dps/LSB (degrees per second)
GYRO_SCALE_DPS = 0.07
# 转换为 rad/s 的比例
GYRO_SCALE_RAD = GYRO_SCALE_DPS * 3.141592653589793 / 180.0

# 加速度计量程 ±8 g → 比例 m/s²/LSB (9.8 m/s² per g, 4096 LSB per g)
ACCEL_SCALE = 9.8 / 4096.0

# CAN网关接线端子映射 (来源于实验方案)
# ch1: 头部眉心 (IMU-01), ch2: 躯干T8 (IMU-02), ch3: 座垫R点 (IMU-03)
# ch4: 座椅底部 (IMU-04), ch5: 胸骨剑突 (备选)
CHANNEL_IMU_MAP = {
    'ch1': {'imu_a': 'IMU-01_头部眉心_实验组', 'imu_b': 'IMU-01_头部眉心_对照组'},
    'ch2': {'imu_a': 'IMU-02_躯干T8_实验组', 'imu_b': 'IMU-02_躯干T8_对照组'},
    'ch3': {'imu_a': 'IMU-03_座垫R点_实验组', 'imu_b': 'IMU-03_座垫R点_对照组'},
    'ch4': {'imu_a': 'IMU-04_座椅底部_实验组', 'imu_b': 'IMU-04_座椅底部_对照组'},
    'ch5': {'imu_a': 'IMU-05_胸骨剑突_实验组', 'imu_b': 'IMU-05_胸骨剑突_对照组'},
}

# ch6 车机CAN ID 定义
CAN_ID_CONFIG = {
    '0x100':  {'name': '车速',           'parser': 'parse_speed',      'unit': 'km/h'},
    '0x101':  {'name': '方向盘转角',      'parser': 'parse_steering',    'unit': 'deg'},
    '0x102':  {'name': '急刹+刹车油压',   'parser': 'parse_brake',       'unit': '-'},
    '0x103':  {'name': '预留CAN_103',     'parser': 'parse_raw',         'unit': 'hex'},
    '0x104':  {'name': '预留CAN_104',     'parser': 'parse_raw',         'unit': 'hex'},
    '0x51000':{'name': '高频自定义帧',    'parser': 'parse_51000',       'unit': '-'},
    '0x1F00': {'name': '扩展帧1F00(状态)', 'parser': 'parse_raw',        'unit': 'hex'},
    '0x1F01': {'name': '扩展帧1F01(数据)', 'parser': 'parse_1F01_1F02',  'unit': '-'},
    '0x1F02': {'name': '扩展帧1F02(数据)', 'parser': 'parse_1F01_1F02',  'unit': '-'},
    '0x1702': {'name': '自定义帧1702',    'parser': 'parse_raw',         'unit': 'hex'},
    '0x6100': {'name': '自定义帧6100',    'parser': 'parse_raw',         'unit': 'hex'},
}


# ============================================================
# CAN 数据解析函数
# ============================================================

def parse_speed(data_bytes):
    """ID 0x100: 车速
    byte[0]: 0~255 → 0~255 km/h
    byte[1]: 0=前进, 1=倒挡
    """
    speed = data_bytes[0]
    reverse = (data_bytes[1] == 1)
    return {'车速_kmh': speed, '倒挡': int(reverse)}


def parse_steering(data_bytes):
    """ID 0x101: 方向盘转角
    byte[0]: 有符号16位高8位
    byte[1]: 有符号16位低8位
    范围: -540 ~ +540 度
    """
    raw = struct.unpack('>h', data_bytes[:2])[0]  # big-endian signed 16-bit
    return {'方向盘转角_deg': raw}


def parse_brake(data_bytes):
    """ID 0x102: 急刹信号及刹车油压
    byte[0]: 0=无急刹, 1=急刹
    byte[1]: 预留
    byte[2]: 无符号16位高8位
    byte[3]: 无符号16位低8位 → 0~1000 刹车油压幅度
    """
    ebrake = data_bytes[0]
    pressure = (data_bytes[2] << 8) | data_bytes[3]
    return {'急刹信号': ebrake, '刹车油压': pressure}


def parse_51000(data_bytes):
    """ID 0x51000: 高频4字节自定义帧
    byte[0]: 变化范围 0x00~0xFF
    byte[1]: 变化范围 {0,1,2,4,6,247,252,253,254,255}
    byte[2]: 变化范围 0x00~0xFF
    byte[3]: 变化范围 {0,1,254,255}
    暂按两字节组合解析 (byte[0]<<8 | byte[2]) + (byte[1]<<8 | byte[3])
    """
    val_a = (data_bytes[0] << 8) | data_bytes[2]
    val_b = (data_bytes[1] << 8) | data_bytes[3]
    return {'Combined_A_U16': val_a, 'Combined_B_U16': val_b,
            'Byte0': data_bytes[0], 'Byte1': data_bytes[1],
            'Byte2': data_bytes[2], 'Byte3': data_bytes[3]}


def parse_1F01_1F02(data_bytes):
    """ID 0x1F01/0x1F02: 8字节扩展帧 (4个signed int16 LE)
    可能包含附加IMU数据或网关状态数据
    """
    vals = struct.unpack('<4h', data_bytes)
    return {
        'Val0': vals[0], 'Val1': vals[1],
        'Val2': vals[2], 'Val3': vals[3],
    }


def parse_raw(data_bytes):
    """原始十六进制 (未定义协议时使用)"""
    return {'raw_hex': data_bytes.hex()}


# ============================================================
# IMU 数据解析
# ============================================================

def parse_imu_message(data_8byte, data_4byte):
    """解析一对 IMU CAN 消息 (8字节 + 4字节 = 12字节 = 6个 int16)
    
    CAN消息布局 (推测，基于数据模式):
      8字节帧 (0x1FFF0051 或 0x1FFF0053):
        [Gx_raw, Gy_raw, Gz_raw, Ax_raw]  各为 signed int16 LE
      4字节帧 (0x1FFF0052 或 0x1FFF0054):
        [Ay_raw, Az_raw]                   各为 signed int16 LE
    
    返回: {'Gx_dps': °/s, 'Gy_dps': °/s, 'Gz_dps': °/s,
           'Gx_rad_s': rad/s, 'Gy_rad_s': rad/s, 'Gz_rad_s': rad/s,
           'Ax_m_s2': m/s², 'Ay_m_s2': m/s², 'Az_m_s2': m/s²,
           'Gx_raw': ..., ...}
    """
    if len(data_8byte) < 8 or len(data_4byte) < 4:
        return None
    
    vals_8 = struct.unpack('<4h', data_8byte[:8])
    vals_4 = struct.unpack('<2h', data_4byte[:4])
    
    gx_raw, gy_raw, gz_raw, ax_raw = vals_8
    ay_raw, az_raw = vals_4
    
    return {
        'Gx_dps': gx_raw * GYRO_SCALE_DPS,
        'Gy_dps': gy_raw * GYRO_SCALE_DPS,
        'Gz_dps': gz_raw * GYRO_SCALE_DPS,
        'Gx_rad_s': gx_raw * GYRO_SCALE_RAD,
        'Gy_rad_s': gy_raw * GYRO_SCALE_RAD,
        'Gz_rad_s': gz_raw * GYRO_SCALE_RAD,
        'Ax_m_s2': ax_raw * ACCEL_SCALE,
        'Ay_m_s2': ay_raw * ACCEL_SCALE,
        'Az_m_s2': az_raw * ACCEL_SCALE,
        'Gx_raw': gx_raw, 'Gy_raw': gy_raw, 'Gz_raw': gz_raw,
        'Ax_raw': ax_raw, 'Ay_raw': ay_raw, 'Az_raw': az_raw,
    }


# ============================================================
# 数据文件解析
# ============================================================

def parse_data_file(filepath):
    """解析 CAN 网关数据文件"""
    
    # 存储结构
    ch6_records = []            # ch6: 每条CAN消息
    imu_records = defaultdict(list)  # ch1~5: IMU解析结果
    
    # 暂存区 (用于配对 IMU 的 8字节+4字节消息)
    imu_buffer = defaultdict(dict)
    
    line_num = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_num += 1
            if line_num == 1:
                continue  # 跳过表头
            
            # 解析行: idx,timestamp,rel_time,channel,CANID,frame_type,frame_format,CAN,dlc,x|data
            match = re.search(
                r'(\d+),.*?(\d{2}:\d{2}:\d{2}\.\d+).*?([\d.]+),'
                r'(ch\d+),0x([0-9a-fA-F]+).*?(\d+),x\|\s*(.*)',
                line
            )
            if not match:
                continue
            
            idx = int(match.group(1))
            timestamp = match.group(2)
            rel_time = float(match.group(3))
            channel = match.group(4)
            can_id = f"0x{match.group(5)}"
            dlc = int(match.group(6))
            data_str = match.group(7).strip()
            
            # 解析数据字节
            try:
                data_bytes = bytes.fromhex(data_str.replace(' ', ''))
            except ValueError:
                continue
            
            if channel == 'ch6':
                # --- ch6: 车机CAN总线 ---
                record = {
                    'idx': idx, 'timestamp': timestamp, 'rel_time': rel_time,
                    'can_id': can_id, 'dlc': dlc, 'data_hex': data_str,
                }
                
                if can_id in CAN_ID_CONFIG:
                    cfg = CAN_ID_CONFIG[can_id]
                    parser_func = globals().get(cfg['parser'], parse_raw)
                    parsed = parser_func(data_bytes)
                    record.update(parsed)
                    record['signal_name'] = cfg['name']
                else:
                    record.update(parse_raw(data_bytes))
                    record['signal_name'] = f'未知_{can_id}'
                
                ch6_records.append(record)
            
            elif channel in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
                # --- ch1~ch5: IMU 数据 ---
                key = (channel, can_id)
                
                if can_id in ('0x1FFF0051', '0x1FFF0053'):
                    # 8字节帧: 保存时间戳和8字节数据，等待对应4字节帧
                    imu_buffer[key] = {
                        'rel_time': rel_time,
                        'data_8': data_bytes,
                    }
                elif can_id in ('0x1FFF0052', '0x1FFF0054'):
                    # 4字节帧: 与对应8字节帧配对
                    pair_id = can_id.replace('52', '51').replace('54', '53')
                    pair_key = (channel, pair_id)
                    
                    if pair_key in imu_buffer:
                        buf = imu_buffer.pop(pair_key)
                        imu_result = parse_imu_message(buf['data_8'], data_bytes)
                        
                        if imu_result:
                            imu_result['channel'] = channel
                            imu_result['rel_time'] = buf['rel_time']
                            imu_result['pkt_id'] = pair_id
                            imu_records[channel].append(imu_result)
    
    # --- IMU 后处理: 根据每个通道实际出现的 CAN ID 分配标签 ---
    for ch in imu_records:
        # 统计该通道有哪些数据包ID
        pkt_ids = set(r['pkt_id'] for r in imu_records[ch])
        ch_map = CHANNEL_IMU_MAP.get(ch, {'imu_a': f'{ch}_A', 'imu_b': f'{ch}_B'})
        
        # 构建 pkt_id → imu_label 映射
        id_to_label = {}
        if '0x1FFF0051' in pkt_ids:
            id_to_label['0x1FFF0051'] = 'imu_a'
        if '0x1FFF0053' in pkt_ids:
            if '0x1FFF0051' in pkt_ids:
                id_to_label['0x1FFF0053'] = 'imu_b'
            else:
                # 单IMU通道: 映射为 imu_a
                id_to_label['0x1FFF0053'] = 'imu_a'
        
        for r in imu_records[ch]:
            label = id_to_label.get(r['pkt_id'], 'unknown')
            r['imu_name'] = ch_map.get(label, f'{ch}_{label}')
            del r['pkt_id']  # 清理临时字段
    
    return ch6_records, imu_records


# ============================================================
# 输出
# ============================================================

def export_csv(ch6_records, imu_records, prefix='output'):
    """导出为 CSV 文件"""
    
    # --- ch6: 车机CAN数据 ---
    if ch6_records:
        # 收集所有字段名
        all_fields = set()
        for r in ch6_records:
            all_fields.update(r.keys())
        
        # 定义输出顺序
        priority_fields = ['timestamp', 'rel_time', 'can_id', 'signal_name',
                          '车速_kmh', '倒挡', '方向盘转角_deg',
                          '急刹信号', '刹车油压', 'data_hex']
        ordered_fields = [f for f in priority_fields if f in all_fields]
        remaining = sorted(all_fields - set(ordered_fields))
        ordered_fields.extend(remaining)
        
        ch6_path = f'{prefix}_ch6_CAN.csv'
        with open(ch6_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(ch6_records)
        print(f"[CH6] 导出 {len(ch6_records)} 条CAN记录 → {ch6_path}")
    
    # --- IMU 数据 (合并所有通道) ---
    all_imu = []
    for ch in sorted(imu_records.keys()):
        all_imu.extend(imu_records[ch])
    
    if all_imu:
        imu_fields = ['rel_time', 'channel', 'imu_name',
                      'Gx_dps', 'Gy_dps', 'Gz_dps',
                      'Gx_rad_s', 'Gy_rad_s', 'Gz_rad_s',
                      'Ax_m_s2', 'Ay_m_s2', 'Az_m_s2',
                      'Gx_raw', 'Gy_raw', 'Gz_raw',
                      'Ax_raw', 'Ay_raw', 'Az_raw']
        
        imu_path = f'{prefix}_IMU.csv'
        with open(imu_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=imu_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_imu)
        print(f"[IMU] 导出 {len(all_imu)} 条IMU记录 → {imu_path}")
        
        # 按通道分别导出
        for ch in sorted(imu_records.keys()):
            ch_records = imu_records[ch]
            ch_path = f'{prefix}_IMU_{ch}.csv'
            with open(ch_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=imu_fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(ch_records)
            print(f"  [{ch}] 导出 {len(ch_records)} 条 → {ch_path}")


def print_summary(ch6_records, imu_records):
    """打印数据摘要"""
    print("\n" + "=" * 60)
    print("数据解析摘要")
    print("=" * 60)
    
    # ch6 统计
    from collections import Counter
    id_counter = Counter(r['can_id'] for r in ch6_records)
    print(f"\n[ch6] CAN总线消息: {len(ch6_records)} 条")
    print(f"  CAN ID 分布:")
    for cid, count in id_counter.most_common():
        name = CAN_ID_CONFIG.get(cid, {}).get('name', '未知')
        print(f"    {cid} ({name}): {count}")
    
    # 车速范围
    speeds = [r.get('车速_kmh', None) for r in ch6_records if '车速_kmh' in r]
    if speeds:
        print(f"\n  车速范围: {min(speeds)} ~ {max(speeds)} km/h (均值 {sum(speeds)/len(speeds):.1f})")
    
    # 方向盘范围
    steerings = [r.get('方向盘转角_deg', None) for r in ch6_records if '方向盘转角_deg' in r]
    if steerings:
        print(f"  方向盘角度: {min(steerings)}° ~ {max(steerings)}°")
    
    # IMU 统计
    print(f"\n[IMU] 解析记录:")
    for ch in sorted(imu_records.keys()):
        recs = imu_records[ch]
        names = set(r['imu_name'] for r in recs)
        print(f"  {ch}: {len(recs)} 条 → {', '.join(sorted(names))}")


# ============================================================
# 主入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("请提供数据文件路径: python can_imu_parser.py <data.txt> [output_prefix]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else 'parsed'
    
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)
    
    print(f"解析数据文件: {filepath}")
    print(f"输出前缀: {prefix}")
    
    ch6_records, imu_records = parse_data_file(filepath)
    
    print_summary(ch6_records, imu_records)
    export_csv(ch6_records, imu_records, prefix)
    
    print(f"\n解析完成!")


if __name__ == '__main__':
    main()
