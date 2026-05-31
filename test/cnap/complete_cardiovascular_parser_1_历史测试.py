import pandas as pd
import re
import numpy as np
from datetime import timedelta

def parse_complete_cardiovascular_data(csv_path, ui_static_data):
    """
    解析心血管监测数据集，明确衍生参数含义，与UI参数完整匹配
    
    参数:
        csv_path: CSV文件路径
        ui_static_data: 从UI获取的静态数据字典
    返回:
        df: 解析后的完整DataFrame
    """
    # 读取原始CSV数据
    df = pd.read_csv(csv_path)
    
    # 初始化新列存储解析后的参数
    parsed_columns = [
        # 基础信息
        'Beat_Marker',          # 节拍标识
        # 血压参数
        'Systolic_BP',          # 收缩压(mmHg)
        'Diastolic_BP',         # 舒张压(mmHg)
        'Heart_Rate',           # 心率(bpm)
        'Mean_Arterial_Pressure',# 平均动脉压(mmHg)
        'Pulse_Pressure',       # 脉压(mmHg) - 原Derived_Param_1
        'Heart_Rate_Variability',# 心率变异率(%) - 原Derived_Param_2
        'Mean_Pulse_Pressure',  # 平均脉压(mmHg) - 原Derived_Param_3
        # 心输出参数
        'Stroke_Volume',        # 每搏输出量(ml)
        # 阻力与变异参数
        'Vascular_Resistance',  # 外周血管阻力(dyn·s/cm⁵)
        'PPV',                  # 脉压变异率(%)
        'SVV',                  # 每搏输出量变异率(%)
        'Ejection_Fraction',    # 射血分数(%)
        # UI补充的静态参数
        'BSA',                  # 体表面积(m²)
        'Start_Time',           # 开始测量时间
        'Duration',             # 测量时长(秒)
        'NBP',                  # 无创血压
        'EDV_Input',            # 舒张末期容积(输入)
        # 推导参数
        'CO',                   # 心输出量(L/min)
        'CI',                   # 心脏指数(L/min/m²)
        'SI',                   # 每搏指数(ml/m²)
        'SVRI',                 # 全身血管阻力指数
        'CPO'                   # 心脏功率输出(W)
    ]
    
    # 添加新列并初始化
    for col in parsed_columns:
        df[col] = np.nan
    
    # 填充UI静态数据
    df['BSA'] = ui_static_data['BSA']
    df['Start_Time'] = ui_static_data['Start_Time']
    df['Duration'] = timedelta(
        hours=int(ui_static_data['Duration'].split(':')[0]),
        minutes=int(ui_static_data['Duration'].split(':')[1]),
        seconds=int(ui_static_data['Duration'].split(':')[2])
    ).total_seconds()
    df['NBP'] = ui_static_data['NBP']
    df['EDV_Input'] = ui_static_data['EDV_Input']
    df['CPO'] = ui_static_data['CPO_Baseline']
    
    # 解析Data字段的正则表达式
    beats_pattern = re.compile(rb'%BEATS%(\d+\.\d+): (.*?)\n')
    
    # 遍历每行数据进行解析
    for idx, row in df.iterrows():
        try:
            data_bytes = row['Data']
            match = beats_pattern.search(eval(data_bytes))  # 转换字节串
            if not match:
                continue
            
            # 提取节拍标识
            beat_marker = float(match.group(1))
            df.at[idx, 'Beat_Marker'] = beat_marker
            
            # 提取参数值列表
            params_str = match.group(2).decode('utf-8')
            params_list = [p.strip() for p in params_str.split(';') if p.strip()]
            
            # 转换参数为数值类型(处理无效值)
            params = []
            for p in params_list:
                if p in ['-1', '-1.0']:
                    params.append(np.nan)
                else:
                    params.append(float(p))
            
            # 明确的参数映射关系（含衍生参数）
            param_mapping = [
                ('Systolic_BP', 0),           # 收缩压
                ('Diastolic_BP', 1),          # 舒张压
                ('Heart_Rate', 2),            # 心率
                ('Mean_Arterial_Pressure', 3),# 平均动脉压
                ('Pulse_Pressure', 4),        # 脉压（原Derived_Param_1）
                ('Heart_Rate_Variability', 5),# 心率变异率（原Derived_Param_2）
                ('Mean_Pulse_Pressure', 6),   # 平均脉压（原Derived_Param_3）
                ('Stroke_Volume', 7),         # 每搏输出量
                ('Vascular_Resistance', 8),   # 外周血管阻力
                ('PPV', 9),                   # 脉压变异率
                ('SVV', 10),                  # 每搏输出量变异率
                ('Ejection_Fraction', 11)     # 射血分数
            ]
            
            # 映射参数到数据框
            for col, idx_param in param_mapping:
                if idx_param < len(params):
                    df.at[idx, col] = params[idx_param]
            
            # 计算衍生参数
            sv = df.at[idx, 'Stroke_Volume']
            hr = df.at[idx, 'Heart_Rate']
            bsa = df.at[idx, 'BSA']
            svr = df.at[idx, 'Vascular_Resistance']
            
            # 心输出量(CO) = 每搏输出量(SV) × 心率(HR) / 1000
            if not np.isnan(sv) and not np.isnan(hr):
                df.at[idx, 'CO'] = round(sv * hr / 1000, 2)
                
            # 心脏指数(CI) = 心输出量(CO) / 体表面积(BSA)
            if not np.isnan(df.at[idx, 'CO']) and not np.isnan(bsa):
                df.at[idx, 'CI'] = round(df.at[idx, 'CO'] / bsa, 2)
                
            # 每搏指数(SI) = 每搏输出量(SV) / 体表面积(BSA)
            if not np.isnan(sv) and not np.isnan(bsa):
                df.at[idx, 'SI'] = round(sv / bsa, 2)
                
            # 全身血管阻力指数(SVRI) = 外周血管阻力(SVR) × 体表面积(BSA) × 100
            if not np.isnan(svr) and not np.isnan(bsa):
                df.at[idx, 'SVRI'] = round(svr * bsa * 100, 2)
                
        except Exception as e:
            print(f"解析第{idx}行出错: {str(e)}")
            continue
    
    # 转换Unix时间戳为可读时间格式
    df['Datetime'] = pd.to_datetime(df['Timestamp'], unit='s')
    
    # 调整列顺序
    df = df[['Timestamp', 'Datetime', 'Beat_Marker', 
             'Systolic_BP', 'Diastolic_BP', 'Heart_Rate', 
             'Mean_Arterial_Pressure', 'Pulse_Pressure', 
             'Heart_Rate_Variability', 'Mean_Pulse_Pressure',
             'Stroke_Volume', 'Vascular_Resistance',
             'PPV', 'SVV', 'Ejection_Fraction',
             'CO', 'CI', 'SI', 'SVRI',
             'BSA', 'Start_Time', 'Duration', 'NBP', 
             'EDV_Input', 'CPO']]
    
    return df

# 示例用法
if __name__ == '__main__':
    # 从UI获取的静态数据
    ui_static_info = {
        'BSA': 2.25,
        'Start_Time': '13:10:31',
        'Duration': '00:21:07',
        'NBP': '128/85',
        'EDV_Input': 120,
        'CPO_Baseline': 2.18
    }
    
    # CSV文件路径
    csv_path = '1_timestamp_data (other1).csv'
    
    # 解析数据
    parsed_df = parse_complete_cardiovascular_data(csv_path, ui_static_info)
    
    # 打印前5行验证
    print("解析后的数据预览:")
    print(parsed_df.head())
    
    # 保存解析结果
    parsed_df.to_csv('complete_cardiovascular_data.csv', index=False)
    print("\n解析完成，结果已保存至 complete_cardiovascular_data.csv")
