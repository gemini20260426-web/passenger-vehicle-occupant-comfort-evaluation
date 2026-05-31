import os
import glob
import pandas as pd

# ==========================================
# 步骤 1：在这里定义你的解析函数
# ==========================================

#先提取R1: x y z a b c, R2: x y z a b c, 车速，方向盘角度

def parse_r1_xyza_data(data_hex):
    """规则 1 & 2合并: 提取点位1的 X 和 Y 数据"""
    result = {}
    
    # 提取 X 数据 (需要至少 8 个字节)
    if len(data_hex) >= 8:
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_x = int(data_hex[0], 16)
        byte2_x = int(data_hex[1], 16)
                
        # 将两个字节直接拼成 16 位有符号整数 (小端模式)
        raw_x = int.from_bytes([byte1_x, byte2_x], byteorder='little', signed=True)
            
        # 3. 最后乘以系数计算实际物理值
        x_val = raw_x * 9.8 / 1024
        result['R1-X数据'] = x_val

        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_y = int(data_hex[2], 16)
        byte2_y = int(data_hex[3], 16)
        
        raw_y = int.from_bytes([byte1_y, byte2_y], byteorder='little', signed=True)
            
        # 3. 最后乘以系数计算实际物理值
        y_val = raw_y * 9.8 / 1024
        result['R1-Y数据'] = y_val
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_z = int(data_hex[4], 16)
        byte2_z = int(data_hex[5], 16)
        
        raw_z = int.from_bytes([byte1_z, byte2_z], byteorder='little', signed=True)
            
        # 3. 最后乘以系数计算实际物理值
        z_val = raw_z * 9.8 / 1024
        result['R1-Z数据'] = z_val     
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_a = int(data_hex[6], 16)
        byte2_a = int(data_hex[7], 16)
        
        raw_a = int.from_bytes([byte1_a, byte2_a], byteorder='little', signed=True)
            
        # 3. 最后乘以系数计算实际物理值
        a_val = raw_a * 500.0 / 32768
        result['R1-A数据'] = a_val        

    return result if result else None

def parse_r1_bc_data(data_hex):
    """提取 R1 的 B 和 C 数据"""
    result = {}
    
    if len(data_hex) >= 4:
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_b = int(data_hex[0], 16)
        byte2_b = int(data_hex[1], 16)
        
        raw_b = int.from_bytes([byte1_b, byte2_b], byteorder='little', signed=True)        
            
        # 3. 最后乘以系数计算实际物理值
        b_val = raw_b * 500.0 / 32768
        result['R1-B数据'] = b_val       
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_c = int(data_hex[2], 16)  
        byte2_c = int(data_hex[3], 16)
        
        raw_c = int.from_bytes([byte1_c, byte2_c], byteorder='little', signed=True)        
            
        # 3. 最后乘以系数计算实际物理值
        c_val = raw_c * 500.0 / 32768
        result['R1-C数据'] = c_val        

    # 如果提取到了任何数据就返回字典，否则返回 None
    return result if result else None

def parse_r2_xyza_data(data_hex):
    """提取 R2 的 X Y Z A 数据"""
    result = {}
    
    if len(data_hex) >= 8:
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_x = int(data_hex[0], 16)
        byte2_x = int(data_hex[1], 16)
                
        # 将两个字节直接拼成 16 位有符号整数 (小端模式)
        raw_x = int.from_bytes([byte1_x, byte2_x], byteorder='little', signed=True)
        
            
        # 3. 最后乘以系数计算实际物理值
        x_val = raw_x * 9.8 / 1024
        result['R2-X数据'] = x_val

        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_y = int(data_hex[2], 16)
        byte2_y = int(data_hex[3], 16)
        
        raw_y = int.from_bytes([byte1_y, byte2_y], byteorder='little', signed=True)
        
            
        # 3. 最后乘以系数计算实际物理值
        y_val = raw_y * 9.8 / 1024
        result['R2-Y数据'] = y_val
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_z = int(data_hex[4], 16)
        byte2_z = int(data_hex[5], 16)
        
        raw_z = int.from_bytes([byte1_z, byte2_z], byteorder='little', signed=True)
        
            
        # 3. 最后乘以系数计算实际物理值
        z_val = raw_z * 9.8 / 1024
        result['R2-Z数据'] = z_val     
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_a = int(data_hex[6], 16)
        byte2_a = int(data_hex[7], 16)
        
        raw_a = int.from_bytes([byte1_a, byte2_a], byteorder='little', signed=True)
        
            
        # 3. 最后乘以系数计算实际物理值
        a_val = raw_a * 500.0 / 32768
        result['R2-A数据'] = a_val        
        

    # 如果提取到了任何数据就返回字典，否则返回 None
    return result if result else None

def parse_r2_bc_data(data_hex):
    """提取 R2 的 B 和 C 数据"""
    result = {}
    
    if len(data_hex) >= 4:
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_b = int(data_hex[0], 16)
        byte2_b = int(data_hex[1], 16)
        
        raw_b = int.from_bytes([byte1_b, byte2_b], byteorder='little', signed=True)        
            
        # 3. 最后乘以系数计算实际物理值
        b_val = raw_b * 500.0 / 32768
        result['R2-B数据'] = b_val       
        
        # 小端模式：第1字节为低8位，第2字节为高8位
        byte1_c = int(data_hex[2], 16)  
        byte2_c = int(data_hex[3], 16)
        
        raw_c = int.from_bytes([byte1_c, byte2_c], byteorder='little', signed=True)        
            
        # 3. 最后乘以系数计算实际物理值
        c_val = raw_c * 500.0 / 32768
        result['R2-C数据'] = c_val        

    # 如果提取到了任何数据就返回字典，否则返回 None
    return result if result else None


def parse_speed_data(data_hex):
    """规则 2: 提取速度数据"""
    if len(data_hex) >= 1:
        speed_val = int(data_hex[0], 16)
        return {'速度数据': speed_val}
    return None

#方向盘数据
def parse_steering_data(data_hex):
    """规则 2: 提取方向盘数据"""
    if len(data_hex) >= 2:
        # 大端模式：第1字节为高8位，第2字节为低8位
        byte1_x = int(data_hex[0], 16)
        byte2_x = int(data_hex[1], 16)        
      
        # 大端（Motorola）：第1字节为高8位
        raw_x = int.from_bytes([byte1_x, byte2_x], byteorder='big', signed=True)
        
        return {'方向盘数据': raw_x}      
        
    return None

# ==========================================
# 步骤 2：在字典中注册你的规则
# 格式为: (通道, CAN_ID): 解析函数
# ==========================================
PARSE_RULES = {
    ('ch2', '0x1fff0053'): parse_r1_xyza_data,
    ('ch2', '0x1fff0054'): parse_r1_bc_data,
    ('ch2', '0x1fff0051'): parse_r2_xyza_data,
    ('ch2', '0x1fff0052'): parse_r2_bc_data,
    ('ch6', '0x100'): parse_speed_data,
    ('ch6', '0x101'): parse_steering_data,
}

# ==========================================
# 主体逻辑（后续添加规则无需修改此部分）
# ==========================================

def parse_single_txt_file(txt_path, output_dir):
    """
    解析单个 txt 文件，并在 output_dir 下生成同名的 csv 文件。
    返回生成的 csv 文件路径，如果无有效数据则返回 None。
    """
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

            # 提取时间与基础信息
            time_str = parts[1].replace('=', '').replace('"', '').strip()
            try:
                # 使用时间标识(float)排序更安全，防止跨天时出现字符串排序错误
                time_mark = float(parts[2].strip())
            except ValueError:
                continue

            ch = parts[3].strip().lower()
            can_id = parts[4].strip().lower()
            
            # 【优化点】：检查当前报文是否在我们注册的规则中
            rule_key = (ch, can_id)
            if rule_key in PARSE_RULES:
                data_field = parts[9].strip()

                # 提取数据部分（去除 "x|" 前缀并按空格拆分）
                if 'x|' in data_field:
                    data_hex = data_field.split('x|')[1].strip().split()
                else:
                    data_hex = data_field.split()
                
                # 调用对应的解析函数
                parse_func = PARSE_RULES[rule_key]
                parsed_result = parse_func(data_hex)
                
                # 如果成功解析出数据，加入基础时间信息并存入记录
                if parsed_result:
                    record = {
                        '时间标识': time_mark,
                        '时间': time_str
                    }
                    record.update(parsed_result) # 合并解析出的信号键值对
                    records.append(record)

    if not records:
        print(f"  文件 {txt_path} 中未提取到指定的 CAN ID 数据，跳过。")
        return None

    print(f"  文件 {os.path.basename(txt_path)}: 提取到 {len(records)} 条目标报文，正在进行时序对齐...")

    # 载入 DataFrame (Pandas 会自动把各个字典里缺失的键填充为 NaN)
    df = pd.DataFrame(records)

    # 1. 按照物理时间线 (时间标识) 排序报文
    df = df.sort_values('时间标识').drop(columns=['时间标识'])

    # 2. 时序对齐: 将时间设为索引，保留同一时间的最后一条记录，并向下填充缺失值
    df_aligned = df.groupby('时间', sort=False).last().ffill()

    # ==========================================
    # 3. 【新增】强制规定列的输出顺序
    # ==========================================
    fixed_columns = [
        '速度数据', '方向盘数据',
        'R1-X数据', 'R1-Y数据', 'R1-Z数据', 'R1-A数据', 'R1-B数据', 'R1-C数据',
        'R2-X数据', 'R2-Y数据', 'R2-Z数据', 'R2-A数据', 'R2-B数据', 'R2-C数据'
    ]
    # 使用 reindex 会按照 fixed_columns 的顺序排列列。
    # 如果当前 txt 文件中缺失某个数据（例如没有速度数据），该列依然会被创建，内容自动填充为 NaN。
    df_aligned = df_aligned.reindex(columns=fixed_columns)

    # 导出为 CSV (取消标签输出)
    df_aligned.to_csv(output_file, encoding='utf-8-sig', header=False)
    print(f"  生成文件：{output_file}")
    
    # 将表头（标签）追加输出到 label.txt
    label_file = os.path.join(output_dir, 'label.txt')
    with open(label_file, 'a', encoding='utf-8') as lf:
        lf.write(f"{base_name}.csv: {','.join(df_aligned.columns.tolist())}\n")
    print(f"  标签已写入：{label_file}")
    
    return output_file


def parse_can_directory(input_dir, output_dir=None):
    """
    遍历 input_dir 下所有 .txt 文件，每个文件生成对应的 .csv 文件。
    """
    file_list = glob.glob(os.path.join(input_dir, '*.txt'))
    if not file_list:
        print("未找到任何 .txt 文件。")
        return

    if output_dir is None:
        output_dir = input_dir
    else:
        os.makedirs(output_dir, exist_ok=True)

    print(f"找到 {len(file_list)} 个 .txt 文件，开始逐个解析...\n")

    label_file = os.path.join(output_dir, 'label.txt')
    with open(label_file, 'w', encoding='utf-8') as lf:
        lf.write('# CSV文件标签（表头）\n')

    generated_files = []
    for file_path in sorted(file_list):
        print(f"正在处理: {os.path.basename(file_path)}")
        result = parse_single_txt_file(file_path, output_dir)
        if result:
            generated_files.append(result)

    print(f"\n解析完成！共生成 {len(generated_files)} 个 CSV 文件。")
    for f in generated_files:
        print(f"  - {f}")


if __name__ == '__main__':
    #dir = r"D:\AUTOSAR\260508_0939"
    #dir = r"D:\AUTOSAR\test"
    dir = r'D:\AUTOSAR\260511_0859'
    parse_can_directory(dir)
    