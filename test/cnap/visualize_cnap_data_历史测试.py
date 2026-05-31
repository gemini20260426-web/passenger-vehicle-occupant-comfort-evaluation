import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import ast
import re
import os
from datetime import datetime
import matplotlib.animation as animation
from collections import deque
import time

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def parse_sensor_data(file_path):
    """解析传感器数据文件，完善BEATS数据解析"""
    # 读取原始数据文件
    records = []
    current_record = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 空行表示一条记录结束
            if not line:
                if current_record:
                    records.append(current_record)
                    current_record = {}
                continue
            
            # 解析键值对
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'Timestamp':
                    current_record[key] = float(value)
                elif key in ['Source Port', 'Destination Port']:
                    current_record[key] = int(value)
                else:
                    current_record[key] = value
    
    # 处理最后一条记录（如果没有以空行结尾）
    if current_record:
        records.append(current_record)
    
    # 转换为DataFrame
    df = pd.DataFrame(records)
    
    # 解析Data字段
    df['Data_str'] = df['Data'].apply(
        lambda x: ast.literal_eval(x).decode('utf-8') if isinstance(x, str) and x.startswith('b') else x
    )
    
    # 初始化结果列，扩展BEATS相关字段（根据complete_cardiovascular_parser (1).py更新）
    df['Type'] = ''
    df['Sequence'] = np.nan
    df['Value'] = np.nan
    df['Event'] = ''
    
    # 扩展BEATS专用字段（完整的心血管参数）
    parsed_columns = [
        # 基础信息
        'Beat_Marker',          # 节拍标识
        # 血压参数
        'Systolic_BP',          # 收缩压(mmHg)
        'Diastolic_BP',         # 舒张压(mmHg)
        'Heart_Rate',           # 心率(bpm)
        'Mean_Arterial_Pressure',# 平均动脉压(mmHg)
        'Pulse_Pressure',       # 脉压(mmHg)
        'Heart_Rate_Variability',# 心率变异率(%)
        'Mean_Pulse_Pressure',  # 平均脉压(mmHg)
        # 心输出参数
        'Stroke_Volume',        # 每搏输出量(ml)
        # 阻力与变异参数
        'Vascular_Resistance',  # 外周血管阻力(dyn·s/cm⁵)
        'PPV',                  # 脉压变异率(%)
        'SVV',                  # 每搏输出量变异率(%)
        'Ejection_Fraction',    # 射血分数(%)
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
    
    # 类型解析
    for idx, row in df.iterrows():
        data_str = row['Data_str']
        
        # 波形数据解析
        if '%WAVE%' in data_str:
            df.at[idx, 'Type'] = 'WAVE'
            match = re.search(r'%WAVE%(\d+\.\d+):\s*([\d.]+)', data_str)
            if match:
                seq, value = match.groups()
                df.at[idx, 'Sequence'] = float(seq)
                df.at[idx, 'Value'] = float(value)
        
        # 心跳数据解析（根据complete_cardiovascular_parser (1).py更新）
        elif '%BEATS%' in data_str:
            df.at[idx, 'Type'] = 'BEATS'
            
            # 使用正确的正则表达式解析BEATS数据
            beats_pattern = re.compile(r'%BEATS%(\d+\.\d+): (.*?)\n')
            match = beats_pattern.search(data_str)
            
            if match:
                # 提取节拍标识（时间戳）
                beat_marker = float(match.group(1))
                df.at[idx, 'Beat_Marker'] = beat_marker
                df.at[idx, 'Sequence'] = beat_marker
                
                # 提取参数值列表
                params_str = match.group(2)
                params_list = [p.strip() for p in params_str.split(';') if p.strip()]
                
                # 转换参数为数值类型(处理无效值)
                params = []
                for p in params_list:
                    if p in ['-1', '-1.0']:
                        params.append(np.nan)
                    else:
                        try:
                            params.append(float(p))
                        except:
                            params.append(np.nan)
                
                # 明确的参数映射关系（含衍生参数）
                param_mapping = [
                    ('Systolic_BP', 0),           # 收缩压
                    ('Diastolic_BP', 1),          # 舒张压
                    ('Heart_Rate', 2),            # 心率
                    ('Mean_Arterial_Pressure', 3),# 平均动脉压
                    ('Pulse_Pressure', 4),        # 脉压
                    ('Heart_Rate_Variability', 5),# 心率变异率
                    ('Mean_Pulse_Pressure', 6),   # 平均脉压
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
        
        # 系统事件解析
        elif 'Event:' in data_str:
            df.at[idx, 'Type'] = 'EVENT'
            match = re.search(r'(\d+\.\d+):\s*Event:\s*(.+)', data_str)
            if match:
                seq, event = match.groups()
                df.at[idx, 'Sequence'] = float(seq)
                df.at[idx, 'Event'] = event
    
    # 时间戳修复（处理缺失小数部分）
    df['Timestamp'] = df['Timestamp'].apply(
        lambda x: float(f"{int(x)}.{str(x).split('.')[1]}") if '.' in str(x) else float(f"{x}.0")
    )
    
    # 计算相对时间（秒）
    min_ts = df['Timestamp'].min()
    df['Time_elapsed'] = df['Timestamp'] - min_ts
    
    return df


def analyze_sensor_data(df, start_idx=0, end_idx=None):
    """分析解析后的传感器数据"""
    if end_idx is None:
        end_idx = len(df)
        
    # 只分析指定范围内的数据
    df_segment = df.iloc[start_idx:end_idx]
    
    analysis = {}
    
    # 基本统计
    analysis['total_records'] = len(df_segment)
    analysis['wave_count'] = df_segment[df_segment['Type'] == 'WAVE']['Value'].count()
    analysis['beats_count'] = df_segment[df_segment['Type'] == 'BEATS']['Heart_Rate'].count()  # 更新为Heart_Rate
    analysis['event_count'] = df_segment[df_segment['Type'] == 'EVENT']['Event'].count()
    
    # 波形特征
    wave_df = df_segment[df_segment['Type'] == 'WAVE'].copy()
    if len(wave_df) > 0:
        analysis['wave_stats'] = {
            'min': wave_df['Value'].min(),
            'max': wave_df['Value'].max(),
            'mean': wave_df['Value'].mean(),
            'std': wave_df['Value'].std()
        }
    
    # 周期性分析
    if len(wave_df) > 0:
        peak_values = wave_df[wave_df['Value'] > 100]['Sequence'].values
        if len(peak_values) > 1:
            analysis['period'] = np.mean(np.diff(peak_values))
    
    # 心跳数据分析（更新为使用Heart_Rate列）
    beats_df = df_segment[df_segment['Type'] == 'BEATS'].copy()
    if not beats_df.empty:
        # 直接使用Heart_Rate列，无需解析字符串
        heart_rates = beats_df['Heart_Rate'].dropna()
        
        if len(heart_rates) > 0:
            analysis['hr_stats'] = {
                'min_hr': heart_rates.min(),
                'max_hr': heart_rates.max(),
                'avg_hr': heart_rates.mean()
            }
    
    # 事件分析
    event_df = df_segment[df_segment['Type'] == 'EVENT'].copy()
    if not event_df.empty:
        analysis['events'] = event_df['Event'].value_counts().to_dict()
    
    # 数据质量指标
    if analysis['wave_count'] > 0:
        analysis['invalid_rate'] = len(df_segment[df_segment['Value'] < 0]) / analysis['wave_count']
    if len(wave_df) > 1:
        analysis['sampling_rate'] = 1 / np.mean(np.diff(wave_df['Time_elapsed']))
    
    return analysis

class RealTimeCNAPPlot:
    def __init__(self, df, window_size=1000):
        # 获取波形和心跳数据
        self.wave_df = df[df['Type'] == 'WAVE'].copy()
        self.beats_df = df[df['Type'] == 'BEATS'].copy()
        
        self.window_size = window_size
        self.full_window_size = 5000  # 完整数据窗口大小
        
        # 准备波形数据
        self.sequence_data = self.wave_df['Sequence'].values
        self.value_data = self.wave_df['Value'].values
        self.total_points = len(self.sequence_data)
        
        # 创建图形和轴（调整子图布局，让完整数据曲线显示在上方）
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(15, 10))
        self.fig.suptitle('CNAP无创连续动态血流监测数据（动态刷新）', fontsize=16, fontweight='bold')
        
        # 初始化线条
        self.full_line, = self.ax1.plot([], [], linewidth=0.8, color='#1f77b4', alpha=0.5, label='完整数据')
        self.window_line, = self.ax1.plot([], [], linewidth=1.5, color='#d62728', label='当前窗口')
        self.dynamic_line, = self.ax2.plot([], [], linewidth=1, color='#2ca02c')
        
        # 设置轴标签和网格
        self.ax1.set_xlabel('序列号')
        self.ax1.set_ylabel('血压值')
        self.ax1.set_title('完整血压数据曲线')
        self.ax1.grid(True, alpha=0.3)
        self.ax1.legend()
        
        self.ax2.set_xlabel('序列号')
        self.ax2.set_ylabel('血压值')
        self.ax2.set_title('动态刷新窗口')
        self.ax2.grid(True, alpha=0.3)
        
        # 调整子图间距
        self.fig.subplots_adjust(hspace=0.3)
        
        # 添加统计信息文本框到第一个子图
        self.stats_text = self.ax1.text(0.02, 0.98, '', transform=self.ax1.transAxes, fontsize=10,
                                       verticalalignment='top', 
                                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # 添加BEATS数据显示文本框（浮动框体）
        self.beats_text = self.ax2.text(0.98, 0.98, '', transform=self.ax2.transAxes, fontsize=9,
                                       verticalalignment='top', horizontalalignment='right',
                                       bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))
        
        # 添加进度百分比显示文本框（小尺寸）
        self.progress_text = self.fig.text(0.98, 0.02, '', fontsize=10,
                                          verticalalignment='bottom', horizontalalignment='right',
                                          bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        # 初始化显示范围
        self.current_index = min(self.window_size, self.total_points)
        self.full_current_index = 0  # 从0开始，逐步增加到显示所有数据
        
        # 存储完整数据曲线的所有点
        self.full_x_data = []
        self.full_y_data = []
        
        # 统计信息更新计时器
        self.last_stats_update = time.time()
        
        # 定义要显示的BEATS参数列表（完整12个参数）
        self.display_params = [
            'Systolic_BP',          # 收缩压
            'Diastolic_BP',         # 舒张压
            'Heart_Rate',           # 心率
            'Mean_Arterial_Pressure',# 平均动脉压
            'Pulse_Pressure',       # 脉压
            'Heart_Rate_Variability',# 心率变异率
            'Mean_Pulse_Pressure',  # 平均脉压
            'Stroke_Volume',        # 每搏输出量
            'Vascular_Resistance',  # 外周血管阻力
            'PPV',                  # 脉压变异率
            'SVV',                  # 每搏输出量变异率
            'Ejection_Fraction'     # 射血分数
        ]
        
        # 定义参数单位
        self.param_units = {
            'Heart_Rate': 'BPM',
            'Systolic_BP': 'mmHg',
            'Diastolic_BP': 'mmHg',
            'Mean_Arterial_Pressure': 'mmHg',
            'Pulse_Pressure': 'mmHg',
            'Heart_Rate_Variability': '%',
            'Mean_Pulse_Pressure': 'mmHg',
            'Stroke_Volume': 'ml',
            'Vascular_Resistance': 'dyn·s/cm⁵',
            'PPV': '%',
            'SVV': '%',
            'Ejection_Fraction': '%'
        }
    
    def init_animation(self):
        """初始化动画"""
        self.full_line.set_data([], [])
        self.window_line.set_data([], [])
        self.dynamic_line.set_data([], [])
        
        # 设置完整数据视图的坐标轴范围
        if len(self.sequence_data) > 0 and len(self.value_data) > 0:
            x_min, x_max = self.sequence_data.min(), self.sequence_data.max()
            y_min, y_max = self.value_data.min(), self.value_data.max()
            y_range = y_max - y_min if y_max != y_min else 1
            self.ax1.set_xlim(x_min, x_max)
            self.ax1.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
        
        # 初始化进度显示
        if self.total_points > 0:
            progress = (min(self.window_size, self.total_points) / self.total_points) * 100
            self.progress_text.set_text(f'进度: {progress:.1f}%')
        
        # 返回空的艺术家列表，因为我们禁用了blitting
        return []
    
    def update_animation(self, frame):
        """更新动画帧"""
        # 计算当前窗口的索引范围（动态刷新窗口）
        end_idx = min(self.current_index + 10, self.total_points)  # 每帧增加10个数据点
        start_idx = max(0, end_idx - self.window_size)
        
        # 获取当前窗口的数据（动态刷新窗口）
        x_data = self.sequence_data[start_idx:end_idx]
        y_data = self.value_data[start_idx:end_idx]
        
        # 更新窗口线条数据（只更新当前窗口数据）
        self.window_line.set_data(x_data, y_data)
        self.dynamic_line.set_data(x_data, y_data)
        
        # 动态调整动态窗口坐标轴范围（向右对齐显示）
        if len(x_data) > 0 and len(y_data) > 0:
            x_min, x_max = x_data.min(), x_data.max()
            y_min, y_max = y_data.min(), y_data.max()
            y_range = y_max - y_min if y_max != y_min else 1
            window_width = x_max - x_min
            self.ax2.set_xlim(x_max - window_width, x_max)  # 向右对齐显示
            self.ax2.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
        
        # 更新完整数据曲线（累积显示所有数据）
        # 每帧添加最多10个新数据点到完整数据曲线
        new_points_count = min(10, self.total_points - self.full_current_index)
        if new_points_count > 0:
            new_start_idx = self.full_current_index
            new_end_idx = self.full_current_index + new_points_count
            
            # 添加新数据点到完整数据曲线
            self.full_x_data.extend(self.sequence_data[new_start_idx:new_end_idx])
            self.full_y_data.extend(self.value_data[new_start_idx:new_end_idx])
            
            # 更新完整数据线条
            self.full_line.set_data(self.full_x_data, self.full_y_data)
            
            # 更新索引
            self.full_current_index = new_end_idx
        
        # 动态调整完整数据窗口坐标轴范围（正常从左到右显示）
        if len(self.full_x_data) > 0 and len(self.full_y_data) > 0:
            full_x_min, full_x_max = min(self.full_x_data), max(self.full_x_data)
            full_y_min, full_y_max = min(self.full_y_data), max(self.full_y_data)
            full_y_range = full_y_max - full_y_min if full_y_max != full_y_min else 1
            
            # 正常从左到右显示完整数据曲线
            self.ax1.set_xlim(full_x_min, full_x_max)
            self.ax1.set_ylim(full_y_min - 0.1 * full_y_range, full_y_max + 0.1 * full_y_range)
        
        # 更新BEATS数据显示（浮动框体）
        if len(self.beats_df) > 0:
            # 查找当前时间范围内最新的BEATS数据
            if len(x_data) > 0:
                current_max_seq = x_data.max()
                # 获取序列号小于等于当前最大序列号的所有BEATS数据
                valid_beats = self.beats_df[self.beats_df['Sequence'] <= current_max_seq]
                
                if not valid_beats.empty:
                    # 获取最后一条BEATS数据（最新的）
                    latest_beats = valid_beats.iloc[-1]
                    
                    # 构建BEATS数据显示文本（完整12个参数）
                    beats_text = "实时BEATS数据:\n"
                    for param in self.display_params:
                        if param in latest_beats and not pd.isna(latest_beats[param]):
                            unit = self.param_units.get(param, '')
                            if unit:
                                beats_text += f"{param}: {latest_beats[param]:.2f} {unit}\n"
                            else:
                                beats_text += f"{param}: {latest_beats[param]:.2f}\n"
                        else:
                            beats_text += f"{param}: N/A\n"
                    
                    self.beats_text.set_text(beats_text.strip())
        
        # 更新进度百分比显示
        if self.total_points > 0:
            progress = (end_idx / self.total_points) * 100
            self.progress_text.set_text(f'进度: {progress:.1f}%')
        
        # 更新统计信息（每10秒更新一次）
        current_time = time.time()
        if current_time - self.last_stats_update >= 10:
            analysis = analyze_sensor_data(pd.concat([self.wave_df, self.beats_df]), start_idx, end_idx)
            if 'wave_stats' in analysis:
                stats_text = f"数据点数: {analysis['wave_count']}\n"
                stats_text += f"平均值: {analysis['wave_stats']['mean']:.2f}\n"
                stats_text += f"标准差: {analysis['wave_stats']['std']:.2f}\n"
                stats_text += f"最大值: {analysis['wave_stats']['max']:.2f}\n"
                stats_text += f"最小值: {analysis['wave_stats']['min']:.2f}"
                
                self.stats_text.set_text(stats_text)
            
            self.last_stats_update = current_time
        
        # 更新索引
        self.current_index = end_idx
        
        # 如果到达数据末尾，重置到开始位置
        if self.current_index >= self.total_points:
            self.current_index = min(self.window_size, self.total_points)
        
        # 返回空的艺术家列表，因为我们禁用了blitting
        return []
    
    def start_animation(self, interval=50):
        """开始动画"""
        # 创建动画对象
        self.ani = animation.FuncAnimation(
            self.fig, 
            self.update_animation, 
            init_func=self.init_animation,
            interval=interval,  # 刷新间隔（毫秒）
            blit=False,  # 禁用blitting以避免错误
            repeat=True,
            cache_frame_data=False
        )
        
        # 显示图形
        plt.tight_layout()
        plt.show()

def visualize_cnap_data(csv_file):
    """
    可视化CNAP血压波数据
    
    Args:
        csv_file (str): CSV格式的数据文件路径
    """
    # 解析数据
    print("正在解析数据...")
    df = parse_sensor_data(csv_file)
    
    print(f"数据解析完成，共 {len(df)} 条记录")
    
    # 分析数据
    print("正在进行数据分析...")
    analysis = analyze_sensor_data(df)
    
    # 获取波形数据
    wave_df = df[df['Type'] == 'WAVE'].copy()
    
    if len(wave_df) > 0:
        print(f"时间范围: {wave_df['Sequence'].min()} - {wave_df['Sequence'].max()}")
        print(f"血流值范围: {wave_df['Value'].min():.2f} - {wave_df['Value'].max():.2f}")
        
        # 显示初始统计信息
        print("\n=== 初始数据统计信息 ===")
        if 'wave_stats' in analysis:
            print(f"平均血流值: {analysis['wave_stats']['mean']:.2f}")
            print(f"血流值标准差: {analysis['wave_stats']['std']:.2f}")
            print(f"最大血流值: {analysis['wave_stats']['max']:.2f}")
            print(f"最小血流值: {analysis['wave_stats']['min']:.2f}")
            print(f"中位数血流值: {wave_df['Value'].median():.2f}")
        
        
        # 创建实时动态刷新图表
        print("启动动态刷新图表...")
        real_time_plot = RealTimeCNAPPlot(df, window_size=2000)
        real_time_plot.start_animation(interval=30)  # 每30毫秒更新一次
        
    else:
        print("未找到波形数据，无法生成图表")

if __name__ == "__main__":
    csv_file = r"D:\UI重构\test\off(1)\1.txt"
   
    try:
        # 可视化数据
        visualize_cnap_data(csv_file)
        
    except FileNotFoundError:
        print(f"错误：找不到文件 {csv_file}")
        print("请确保文件路径正确")
    except Exception as e:
        print(f"处理数据时发生错误: {e}")
        import traceback
        traceback.print_exc()