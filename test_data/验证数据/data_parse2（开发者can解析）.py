import os
import glob
import pandas as pd

# ==========================================
# 步骤 1：通用解析逻辑
# ==========================================

def parse_sensor_data(data_hex, prefix, data_type='xyza'):
    """
    通用传感器解析函数：支持 R1, R2... 等任意传感器的合并处理
    """
    result = {}
    # 物理转换系数
    COEFF_ACC = 9.8 / 1024       # 加速度系数 (X, Y, Z)
    COEFF_GYRO = 500.0 / 32768   # 角速度系数 (A, B, C)

    try:
        if data_type == 'xyza' and len(data_hex) >= 8:
            # 解析 X, Y, Z (使用加速度系数)
            for i, sig in enumerate(['X', 'Y', 'Z']):
                raw = int.from_bytes([int(data_hex[i*2], 16), int(data_hex[i*2+1], 16)], byteorder='little', signed=True)
                result[f'{prefix}-{sig}数据'] = raw * COEFF_ACC
            # 解析 A (使用角速度系数)
            raw_a = int.from_bytes([int(data_hex[6], 16), int(data_hex[7], 16)], byteorder='little', signed=True)
            result[f'{prefix}-A数据'] = raw_a * COEFF_GYRO

        elif data_type == 'bc' and len(data_hex) >= 4:
            # 解析 B, C (使用角速度系数)
            for i, sig in enumerate(['B', 'C']):
                raw = int.from_bytes([int(data_hex[i*2], 16), int(data_hex[i*2+1], 16)], byteorder='little', signed=True)
                result[f'{prefix}-{sig}数据'] = raw * COEFF_GYRO
    except (ValueError, IndexError):
        return None
    return result if result else None

def parse_speed_data(data_hex):
    """提取速度数据 (单字节)"""
    if len(data_hex) >= 1:
        return {'速度数据': int(data_hex[0], 16)}
    return None

def parse_steering_data(data_hex):
    """提取方向盘数据 (大端模式/Motorola)"""
    if len(data_hex) >= 2:
        try:
            raw_x = int.from_bytes([int(data_hex[0], 16), int(data_hex[1], 16)], byteorder='big', signed=True)
            return {'方向盘数据': raw_x}
        except ValueError: pass
    return None

#刹车油压数据
def parse_brake_pressure_data(data_hex):
    """提取刹车油压数据 (单字节)"""
    if len(data_hex) >= 2:
        try:
            raw_x = int.from_bytes([int(data_hex[2], 16), int(data_hex[3], 16)], byteorder='big', signed=True)
            return {'刹车油压数据': raw_x}
        except ValueError: pass
    return None

# ==========================================
# 步骤 2：在字典中注册规则
# 格式为: (通道, CAN_ID): lambda 函数调用通用解析器
# ==========================================
PARSE_RULES = {
    # IMU1 R1 传感器
    ('ch1', '0x1fff0053'): lambda d: parse_sensor_data(d, 'IMU1-R1', 'xyza'),
    ('ch1', '0x1fff0054'): lambda d: parse_sensor_data(d, 'IMU1-R1', 'bc'),
    
    # IMU2 R2 传感器
    ('ch1', '0x1fff0051'): lambda d: parse_sensor_data(d, 'IMU2-R2', 'xyza'),
    ('ch1', '0x1fff0052'): lambda d: parse_sensor_data(d, 'IMU2-R2', 'bc'),
    
    # IMU3 R1 传感器
    ('ch2', '0x1fff0053'): lambda d: parse_sensor_data(d, 'IMU3-R1', 'xyza'),
    ('ch2', '0x1fff0054'): lambda d: parse_sensor_data(d, 'IMU3-R1', 'bc'),
    
    # IMU4 R2 传感器
    ('ch2', '0x1fff0051'): lambda d: parse_sensor_data(d, 'IMU4-R2', 'xyza'),
    ('ch2', '0x1fff0052'): lambda d: parse_sensor_data(d, 'IMU4-R2', 'bc'),
    
    # IMU5 R1 传感器
    ('ch3', '0x1fff0053'): lambda d: parse_sensor_data(d, 'IMU5-R1', 'xyza'),
    ('ch3', '0x1fff0054'): lambda d: parse_sensor_data(d, 'IMU5-R1', 'bc'),
    
    # IMU6 R2 传感器
    ('ch3', '0x1fff0051'): lambda d: parse_sensor_data(d, 'IMU6-R2', 'xyza'),
    ('ch3', '0x1fff0052'): lambda d: parse_sensor_data(d, 'IMU6-R2', 'bc'),
    
    # IMU7 R1 传感器
    ('ch4', '0x1fff0053'): lambda d: parse_sensor_data(d, 'IMU7-R1', 'xyza'),
    ('ch4', '0x1fff0054'): lambda d: parse_sensor_data(d, 'IMU7-R1', 'bc'),
    
    # IMU8 R2 传感器
    ('ch4', '0x1fff0051'): lambda d: parse_sensor_data(d, 'IMU8-R2', 'xyza'),
    ('ch4', '0x1fff0052'): lambda d: parse_sensor_data(d, 'IMU8-R2', 'bc'),
    
    # IMU9 R1 传感器
    ('ch5', '0x1fff0053'): lambda d: parse_sensor_data(d, 'IMU9-R1', 'xyza'),
    ('ch5', '0x1fff0054'): lambda d: parse_sensor_data(d, 'IMU9-R1', 'bc'),
    
    # IMU10 R2 传感器
    ('ch5', '0x1fff0051'): lambda d: parse_sensor_data(d, 'IMU10-R2', 'xyza'),
    ('ch5', '0x1fff0052'): lambda d: parse_sensor_data(d, 'IMU10-R2', 'bc'),
    
    # 车速与方向盘
    ('ch6', '0x100'): parse_speed_data,
    ('ch6', '0x101'): parse_steering_data,
    #('ch6', '0x102'): parse_brake_pressure_data,
}

# ==========================================
# 步骤 3：核心处理逻辑
# ==========================================

def parse_single_txt_file(txt_path, output_dir):
    base_name = os.path.splitext(os.path.basename(txt_path))[0]
    output_file = os.path.join(output_dir, f"{base_name}.csv")
    records = []

    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if not line.strip() or line.startswith('序号'):
                continue

            parts = line.strip().split(',')
            if len(parts) < 10:
                continue

            time_str = parts[1].replace('=', '').replace('"', '').strip()
            try:
                time_mark = float(parts[2].strip())
            except ValueError:
                continue

            ch = parts[3].strip().lower()
            can_id = parts[4].strip().lower()
            
            rule_key = (ch, can_id)
            if rule_key in PARSE_RULES:
                data_field = parts[9].strip()
                data_hex = data_field.split('x|')[1].strip().split() if 'x|' in data_field else data_field.split()
                
                parse_func = PARSE_RULES[rule_key]
                parsed_result = parse_func(data_hex)
                
                if parsed_result:
                    record = {'时间标识': time_mark, '时间': time_str}
                    record.update(parsed_result)
                    records.append(record)

    if not records:
        print(f"  文件 {txt_path} 无匹配数据，跳过。")
        return None

    df = pd.DataFrame(records)
    df = df.sort_values('时间标识').drop(columns=['时间标识'])
    
    # 时序对齐与填充
    df_aligned = df.groupby('时间', sort=False).last().ffill()

    #'刹车油压数据',
    # 强制列顺序
    fixed_columns = [
        '速度数据', '方向盘数据',
        'IMU1-R1-X数据', 'IMU1-R1-Y数据', 'IMU1-R1-Z数据', 'IMU1-R1-A数据', 'IMU1-R1-B数据', 'IMU1-R1-C数据',
        'IMU2-R2-X数据', 'IMU2-R2-Y数据', 'IMU2-R2-Z数据', 'IMU2-R2-A数据', 'IMU2-R2-B数据', 'IMU2-R2-C数据',
        'IMU3-R1-X数据', 'IMU3-R1-Y数据', 'IMU3-R1-Z数据', 'IMU3-R1-A数据', 'IMU3-R1-B数据', 'IMU3-R1-C数据',
        'IMU4-R2-X数据', 'IMU4-R2-Y数据', 'IMU4-R2-Z数据', 'IMU4-R2-A数据', 'IMU4-R2-B数据', 'IMU4-R2-C数据',            
        'IMU5-R1-X数据', 'IMU5-R1-Y数据', 'IMU5-R1-Z数据', 'IMU5-R1-A数据', 'IMU5-R1-B数据', 'IMU5-R1-C数据',
        'IMU6-R2-X数据', 'IMU6-R2-Y数据', 'IMU6-R2-Z数据', 'IMU6-R2-A数据', 'IMU6-R2-B数据', 'IMU6-R2-C数据',
        'IMU7-R1-X数据', 'IMU7-R1-Y数据', 'IMU7-R1-Z数据', 'IMU7-R1-A数据', 'IMU7-R1-B数据', 'IMU7-R1-C数据',
        'IMU8-R2-X数据', 'IMU8-R2-Y数据', 'IMU8-R2-Z数据', 'IMU8-R2-A数据', 'IMU8-R2-B数据', 'IMU8-R2-C数据',
        'IMU9-R1-X数据', 'IMU9-R1-Y数据', 'IMU9-R1-Z数据', 'IMU9-R1-A数据', 'IMU9-R1-B数据', 'IMU9-R1-C数据',
        'IMU10-R2-X数据', 'IMU10-R2-Y数据', 'IMU10-R2-Z数据', 'IMU10-R2-A数据', 'IMU10-R2-B数据', 'IMU10-R2-C数据'
    ]
    df_aligned = df_aligned.reindex(columns=fixed_columns)

    # 导出 CSV
    df_aligned.to_csv(output_file, encoding='utf-8-sig', header=False)
    
    # 记录标签
    label_file = os.path.join(output_dir, 'label.txt')
    with open(label_file, 'a', encoding='utf-8') as lf:
        lf.write(f"{base_name}.csv: {','.join(df_aligned.columns.tolist())}\n")
    
    return output_file

def parse_can_directory(input_dir, output_dir=None):
    file_list = glob.glob(os.path.join(input_dir, '*.txt'))
    if not file_list:
        print("未找到 .txt 文件。")
        return

    output_dir = output_dir or input_dir
    os.makedirs(output_dir, exist_ok=True)

    label_file = os.path.join(output_dir, 'label.txt')
    with open(label_file, 'w', encoding='utf-8') as lf:
        lf.write('# CSV文件标签（表头）\n')

    for file_path in sorted(file_list):
        print(f"正在处理: {os.path.basename(file_path)}")
        parse_single_txt_file(file_path, output_dir)

    print("\n所有文件处理完成！")

if __name__ == '__main__':
    # 替换为你的实际路径
    #target_dir = r"D:\AUTOSAR\260508_0939"
    target_dir = r'D:\AUTOSAR\260511_0859'
    parse_can_directory(target_dir)