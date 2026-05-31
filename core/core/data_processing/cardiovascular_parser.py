#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
心血管数据解析器模块
专门用于解析CNAP（连续无创血压）等心血管监测数据
"""

import pandas as pd
import re
import numpy as np
import logging
from datetime import timedelta
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod

# 配置日志
logger = logging.getLogger(__name__)


class BaseCardiovascularParser(ABC):
    """心血管数据解析器基类"""
    
    @abstractmethod
    def parse_data(self, data: Any) -> pd.DataFrame:
        """解析心血管数据的抽象方法"""
        pass
    
    @abstractmethod
    def validate_data(self, data: Any) -> bool:
        """验证数据有效性的抽象方法"""
        pass


class CardiovascularDataParser(BaseCardiovascularParser):
    """心血管数据解析器主类"""
    
    def __init__(self):
        """初始化心血管数据解析器"""
        self.logger = logging.getLogger(__name__)
        self.logger.info("心血管数据解析器初始化完成")
        
        # 定义标准参数列表
        self.standard_parameters = [
            'Beat_Marker',          # 节拍标识
            'Systolic_BP',          # 收缩压(mmHg)
            'Diastolic_BP',         # 舒张压(mmHg)
            'Heart_Rate',           # 心率(bpm)
            'Mean_Arterial_Pressure',# 平均动脉压(mmHg)
            'Pulse_Pressure',       # 脉压(mmHg)
            'Heart_Rate_Variability',# 心率变异率(%)
            'Mean_Pulse_Pressure',  # 平均脉压(mmHg)
            'Stroke_Volume',        # 每搏输出量(ml)
            'Vascular_Resistance',  # 外周血管阻力(dyn·s/cm⁵)
            'PPV',                  # 脉压变异率(%)
            'SVV',                  # 每搏输出量变异率(%)
            'Ejection_Fraction',    # 射血分数(%)
        ]
        
        # 定义衍生参数
        self.derived_parameters = [
            'CO',                   # 心输出量(L/min)
            'CI',                   # 心脏指数(L/min/m²)
            'SI',                   # 每搏指数(ml/m²)
            'SVRI',                 # 全身血管阻力指数
        ]
    
    def parse_complete_cardiovascular_data(self, csv_path: str, ui_static_data: Dict[str, Any]) -> pd.DataFrame:
        """
        解析心血管监测数据集，明确衍生参数含义，与UI参数完整匹配
        
        Args:
            csv_path: CSV文件路径
            ui_static_data: 从UI获取的静态数据字典
            
        Returns:
            pd.DataFrame: 解析后的完整DataFrame
        """
        try:
            # 读取原始CSV数据
            df = pd.read_csv(csv_path)
            self.logger.info(f"成功读取CSV文件: {csv_path}")
            
            # 初始化新列存储解析后的参数
            all_parameters = self.standard_parameters + self.derived_parameters + [
                'BSA',                  # 体表面积(m²)
                'Start_Time',           # 开始测量时间
                'Duration',             # 测量时长(秒)
                'NBP',                  # 无创血压
                'EDV_Input',            # 舒张末期容积(输入)
                'CPO'                   # 心脏功率输出(W)
            ]
            
            # 添加新列并初始化
            for col in all_parameters:
                df[col] = np.nan
            
            # 填充UI静态数据
            self._fill_static_data(df, ui_static_data)
            
            # 解析Data字段
            self._parse_data_field(df)
            
            # 计算衍生参数
            self._calculate_derived_parameters(df)
            
            # 转换时间格式
            df['Datetime'] = pd.to_datetime(df['Timestamp'], unit='s')
            
            # 调整列顺序
            df = self._reorder_columns(df)
            
            self.logger.info(f"心血管数据解析完成，共处理 {len(df)} 行数据")
            return df
            
        except Exception as e:
            self.logger.error(f"解析心血管数据失败: {e}")
            raise
    
    def parse_realtime_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析实时心血管数据
        
        Args:
            data: 实时数据字典
            
        Returns:
            Dict[str, Any]: 解析后的实时数据
        """
        try:
            parsed_data = {}
            
            # 基础参数解析
            if 'heart_rate' in data:
                parsed_data['Heart_Rate'] = float(data['heart_rate'])
            if 'bp_systolic' in data:
                parsed_data['Systolic_BP'] = float(data['bp_systolic'])
            if 'bp_diastolic' in data:
                parsed_data['Diastolic_BP'] = float(data['bp_diastolic'])
            if 'mean_arterial_pressure' in data:
                parsed_data['Mean_Arterial_Pressure'] = float(data['mean_arterial_pressure'])
            
            # 计算脉压
            if 'Systolic_BP' in parsed_data and 'Diastolic_BP' in parsed_data:
                parsed_data['Pulse_Pressure'] = parsed_data['Systolic_BP'] - parsed_data['Diastolic_BP']
            
            # 添加时间戳
            parsed_data['timestamp'] = data.get('timestamp', pd.Timestamp.now().timestamp())
            
            self.logger.debug(f"实时数据解析完成: {len(parsed_data)} 个参数")
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"解析实时数据失败: {e}")
            return {}
    
    def _fill_static_data(self, df: pd.DataFrame, ui_static_data: Dict[str, Any]):
        """填充UI静态数据"""
        try:
            df['BSA'] = ui_static_data.get('BSA', np.nan)
            df['Start_Time'] = ui_static_data.get('Start_Time', '')
            df['NBP'] = ui_static_data.get('NBP', '')
            df['EDV_Input'] = ui_static_data.get('EDV_Input', np.nan)
            df['CPO'] = ui_static_data.get('CPO_Baseline', np.nan)
            
            # 处理持续时间
            duration_str = ui_static_data.get('Duration', '00:00:00')
            try:
                time_parts = duration_str.split(':')
                if len(time_parts) == 3:
                    duration_seconds = timedelta(
                        hours=int(time_parts[0]),
                        minutes=int(time_parts[1]),
                        seconds=int(time_parts[2])
                    ).total_seconds()
                    df['Duration'] = duration_seconds
                else:
                    df['Duration'] = np.nan
            except (ValueError, IndexError):
                df['Duration'] = np.nan
                self.logger.warning(f"无法解析持续时间格式: {duration_str}")
                
        except Exception as e:
            self.logger.error(f"填充静态数据失败: {e}")
    
    def _parse_data_field(self, df: pd.DataFrame):
        """解析Data字段"""
        try:
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
                    
                    # 明确的参数映射关系
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
                            
                except Exception as e:
                    self.logger.debug(f"解析第{idx}行出错: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"解析Data字段失败: {e}")
    
    def _calculate_derived_parameters(self, df: pd.DataFrame):
        """计算衍生参数"""
        try:
            for idx, row in df.iterrows():
                try:
                    sv = row['Stroke_Volume']
                    hr = row['Heart_Rate']
                    bsa = row['BSA']
                    svr = row['Vascular_Resistance']
                    
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
                    self.logger.debug(f"计算第{idx}行衍生参数出错: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"计算衍生参数失败: {e}")
    
    def _reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """调整列顺序"""
        try:
            column_order = [
                'Timestamp', 'Datetime', 'Beat_Marker', 
                'Systolic_BP', 'Diastolic_BP', 'Heart_Rate', 
                'Mean_Arterial_Pressure', 'Pulse_Pressure', 
                'Heart_Rate_Variability', 'Mean_Pulse_Pressure',
                'Stroke_Volume', 'Vascular_Resistance',
                'PPV', 'SVV', 'Ejection_Fraction',
                'CO', 'CI', 'SI', 'SVRI',
                'BSA', 'Start_Time', 'Duration', 'NBP', 
                'EDV_Input', 'CPO'
            ]
            
            # 只包含存在的列
            existing_columns = [col for col in column_order if col in df.columns]
            return df[existing_columns]
            
        except Exception as e:
            self.logger.error(f"调整列顺序失败: {e}")
            return df
    
    def validate_data(self, data: Any) -> bool:
        """验证数据有效性"""
        try:
            if isinstance(data, pd.DataFrame):
                return len(data) > 0 and 'Data' in data.columns
            elif isinstance(data, dict):
                return len(data) > 0
            else:
                return False
        except Exception as e:
            self.logger.error(f"数据验证失败: {e}")
            return False
    
    def parse_data(self, data: Any) -> pd.DataFrame:
        """实现基类的抽象方法"""
        if isinstance(data, str):
            # 如果是文件路径，尝试读取CSV
            try:
                return pd.read_csv(data)
            except Exception as e:
                self.logger.error(f"读取CSV文件失败: {e}")
                return pd.DataFrame()
        elif isinstance(data, pd.DataFrame):
            return data
        else:
            self.logger.error(f"不支持的数据类型: {type(data)}")
            return pd.DataFrame()
    
    def get_parameter_info(self) -> Dict[str, str]:
        """获取参数信息"""
        return {
            'standard_parameters': self.standard_parameters,
            'derived_parameters': self.derived_parameters,
            'total_parameters': len(self.standard_parameters) + len(self.derived_parameters)
        }


# 创建默认实例
cardiovascular_parser = CardiovascularDataParser()


def parse_complete_cardiovascular_data(csv_path: str, ui_static_data: Dict[str, Any]) -> pd.DataFrame:
    """
    便捷函数：解析心血管监测数据集
    
    Args:
        csv_path: CSV文件路径
        ui_static_data: 从UI获取的静态数据字典
        
    Returns:
        pd.DataFrame: 解析后的完整DataFrame
    """
    return cardiovascular_parser.parse_complete_cardiovascular_data(csv_path, ui_static_data)


def parse_realtime_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    便捷函数：解析实时心血管数据
    
    Args:
        data: 实时数据字典
        
    Returns:
        Dict[str, Any]: 解析后的实时数据
    """
    return cardiovascular_parser.parse_realtime_data(data)


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
    csv_path = 'test_data/cnap_data.txt'  # 使用测试数据
    
    try:
        # 解析数据
        parsed_df = parse_complete_cardiovascular_data(csv_path, ui_static_info)
        
        # 打印前5行验证
        print("解析后的数据预览:")
        print(parsed_df.head())
        
        # 保存解析结果
        parsed_df.to_csv('complete_cardiovascular_data.csv', index=False)
        print("\n解析完成，结果已保存至 complete_cardiovascular_data.csv")
        
    except Exception as e:
        print(f"解析失败: {e}")
