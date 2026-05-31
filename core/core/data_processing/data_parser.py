#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU数据统一解析器，处理文件和串口数据
基于历史版本的正确实现
"""

import re
import time
import logging
import traceback
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime

# 可选导入 chardet
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


class IMUDataParser:
    """IMU数据统一解析器，处理文件和串口数据"""
    
    def __init__(self):
        """初始化IMU数据解析器"""
        self.logger = logging.getLogger(__name__)
        
        # 初始化统计计数器
        self.success_count = 0
        self.error_count = 0
        self.parse_ratio = 0.0
        self.error_types = {}
        self.format_stats = {}
        self.last_error_line = ""
        self.last_timestamp = None
        
        # 设置解析回调函数
        self.parsing_callback = None
        
        # 编码支持
        self.encodings = ['utf-8-sig', 'gb18030', 'latin1', 'gbk', 'utf-8']
        
        # 解析配置
        self.parsing_config = {
            'required_columns': ['ax', 'ay', 'az', 'speed', 'wheel'],
            'timestamp_column': 'timestamp',
            'default_separators': ['\t', ',', ';', '|', ' '],
            'imu_data_processing': {
                'ax': {'conversion': lambda x: x, 'unit': 'm/s²'},
                'ay': {'conversion': lambda x: x, 'unit': 'm/s²'},
                'az': {'conversion': lambda x: x - 9.8, 'unit': 'm/s²'},
                'gx': {'conversion': lambda x: x, 'unit': 'rad/s'},
                'gy': {'conversion': lambda x: -x, 'unit': 'rad/s'},
                'gz': {'conversion': lambda x: x, 'unit': 'rad/s'},
                'speed': {'conversion': lambda x: x, 'unit': 'km/h'},
                'wheel': {'conversion': lambda x: x, 'unit': 'degree'}
            },
            'frame_drop_threshold': 5,
            'garbage_data_threshold': 0.3
        }
        
        # 编译正则表达式模式 - 基于历史版本的正确实现
        self.timestamp_pattern = re.compile(
            r'\[?(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{2}[:]\d{2}[:]\d{2}[.,-]?\d{3})]?'
        )
        self.data_pattern = re.compile(
            r'AA\s*(\d+)\s*[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)\s*'
            r'BB\s*([0-9A-Fa-f]{2})?'
        )
        self.data_packet_pattern = re.compile(
            r'AA\s*(\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'([-+]?\d*\.?\d+)[,\s]?'
            r'BB\s*([0-9A-Fa-f]{2})'
        )
        self.data_header_pattern = re.compile(r'AA\s*\d+[,\s]')

    def set_parse_callback(self, callback):
        """设置解析回调函数
        
        Args:
            callback: 回调函数，接收解析后的数据作为参数
        """
        self.parsing_callback = callback
        self.logger.debug("设置解析回调函数成功")

    def _call_parse_callback(self, data):
        """调用解析回调函数
        
        Args:
            data: 要传递给回调函数的数据
        """
        if self.parsing_callback and callable(self.parsing_callback):
            try:
                self.parsing_callback(data)
            except Exception as e:
                self.logger.error(f"调用解析回调函数失败: {e}")

    def _parse_serial_line(self, line):
        """解析串口数据行 - 基于生产系统优化"""
        try:
            # 快速检查行是否包含必要的数据标识
            if 'AA' not in line or 'BB' not in line:
                return None
            
            # 使用更高效的时间戳匹配
            timestamp_match = self.timestamp_pattern.search(line)
            timestamp = time.time()  # 使用time.time()替代datetime.now().timestamp()
            if timestamp_match:
                ts = timestamp_match.group(1).replace('/', '-').replace('.', '-')
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S-%f")
                    timestamp = dt.timestamp()
                except:
                    try:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                        timestamp = dt.timestamp()
                    except:
                        pass

            # 使用更高效的数据匹配 - 优先使用主模式
            data_match = self.data_pattern.search(line)
            if not data_match:
                data_match = self.data_packet_pattern.search(line)
                if not data_match:
                    return None

            groups = data_match.groups()
            if len(groups) >= 12:
                data = {
                    'cnt': int(groups[0]),
                    'ax': float(groups[1]),
                    'ay': float(groups[2]),
                    'az': float(groups[3]),
                    'gx': float(groups[4]),
                    'gy': float(groups[5]),
                    'gz': float(groups[6]),
                    'speed': float(groups[7]),
                    'wheel': float(groups[8]),
                    'loc1': float(groups[9]),
                    'loc2': float(groups[10]) if len(groups) > 10 else 0.0,
                    'crc': groups[11],
                    'timestamp': timestamp
                }
            elif len(groups) >= 9:
                data = {
                    'cnt': int(groups[0]),
                    'ax': float(groups[1]),
                    'ay': float(groups[2]),
                    'az': float(groups[3]),
                    'gx': None,
                    'gy': None,
                    'gz': None,
                    'speed': float(groups[4]),
                    'wheel': float(groups[5]),
                    'loc1': float(groups[6]),
                    'loc2': float(groups[7]) if len(groups) > 7 else 0.0,
                    'crc': groups[8] if len(groups) > 8 else '',
                    'timestamp': timestamp
                }
            else:
                return None

            processing_config = self.parsing_config['imu_data_processing']
            for col in ['ax', 'ay', 'az', 'speed', 'wheel']:
                if col in data and data[col] is not None and col in processing_config:
                    data[col] = processing_config[col]['conversion'](data[col])
            for col in ['gx', 'gy', 'gz']:
                if col in data and data[col] is not None and col in processing_config:
                    data[col] = processing_config[col]['conversion'](data[col])
                    
            return data
            
        except Exception as e:
            # 减少错误日志频率，避免性能影响
            if self.success_count % 1000 == 0:  # 每1000次成功解析才记录错误
                self.logger.debug(f"解析串口数据行失败: {e}")
            return None

    def stream_parse_file(self, file_path, callback):
        """流式解析文件 - 基于生产系统优化"""
        try:
            # 检测文件编码
            with open(file_path, 'rb') as f:
                raw_data = f.read(4096)
                if HAS_CHARDET:
                    encoding = chardet.detect(raw_data).get('encoding', 'utf-8-sig')
                else:
                    encoding = 'utf-8-sig'
        except:
            encoding = 'utf-8-sig'

        try:
            # 使用更大的缓冲区进行块处理
            buffer_size = 1024 * 1024  # 1MB缓冲区
            buffer = ""
            
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                while True:
                    chunk = f.read(buffer_size)
                    if not chunk:
                        # 处理最后的缓冲区
                        if buffer:
                            packets = self._parse_log_line(buffer)
                            for p in packets:
                                callback(p)
                        break
                        
                    buffer += chunk
                    lines = buffer.split('\n')
                    
                    # 批量处理完整行
                    for line in lines[:-1]:
                        if line.strip():  # 跳过空行
                            packets = self._parse_log_line(line)
                            for p in packets:
                                callback(p)
                    
                    # 保留最后一行（可能不完整）
                    buffer = lines[-1]
                    
        except Exception as e:
            self.logger.error(f"文件解析错误: {e}")

    def _parse_log_line(self, line):
        """解析日志行 - 基于生产系统优化"""
        try:
            # 快速检查行是否包含必要的数据标识
            if 'AA' not in line or 'BB' not in line:
                return []
            
            # 使用更高效的时间戳匹配
            timestamp_match = self.timestamp_pattern.search(line)
            if not timestamp_match:
                return []

            ts = timestamp_match.group(1).replace('/', '-').replace('.', '-')
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S-%f")
                timestamp = dt.timestamp()
            except:
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                    timestamp = dt.timestamp()
                except:
                    timestamp = time.time()

            data_content = line[timestamp_match.end():]
            packets = []
            start_idx = 0

            # 批量查找数据包
            while start_idx < len(data_content):
                aa_idx = data_content.find("AA", start_idx)
                if aa_idx == -1:
                    break
                bb_idx = data_content.find("BB", aa_idx)
                if bb_idx == -1:
                    break
                    
                packet = data_content[aa_idx:bb_idx + 2]
                start_idx = bb_idx + 2
                
                # 使用更高效的数据包解析
                try:
                    # 快速提取数值，减少正则表达式开销
                    packet_data = packet.replace('AA', '').replace('BB', '').strip()
                    values = packet_data.split(',')
                    
                    if len(values) >= 11:
                        data = {
                            'cnt': int(values[0]),
                            'ax': float(values[1]),
                            'ay': float(values[2]),
                            'az': float(values[3]),
                            'gx': float(values[4]),
                            'gy': float(values[5]),
                            'gz': float(values[6]),
                            'speed': float(values[7]),
                            'wheel': float(values[8]),
                            'loc1': float(values[9]),
                            'loc2': float(values[10]) if len(values) > 10 else 0.0,
                            'timestamp': timestamp
                        }
                    elif len(values) >= 8:
                        data = {
                            'cnt': int(values[0]),
                            'ax': float(values[1]),
                            'ay': float(values[2]),
                            'az': float(values[3]),
                            'gx': float(values[4]),
                            'gy': float(values[5]) if len(values) > 5 else None,
                            'gz': float(values[6]) if len(values) > 6 else None,
                            'speed': float(values[7]),
                            'wheel': 0.0,
                            'loc1': 0.0,
                            'loc2': 0.0,
                            'timestamp': timestamp
                        }
                    else:
                        continue
                        
                    processing_config = self.parsing_config['imu_data_processing']
                    for col in ['ax', 'ay', 'az', 'speed', 'wheel']:
                        if col in data and data[col] is not None and col in processing_config:
                            data[col] = processing_config[col]['conversion'](data[col])
                    for col in ['gx', 'gy', 'gz']:
                        if col in data and data[col] is not None and col in processing_config:
                            data[col] = processing_config[col]['conversion'](data[col])
                                
                        packets.append(data)
                        
                except Exception as e:
                    # 减少错误日志频率
                    if self.success_count % 1000 == 0:
                        self.logger.debug(f"解析数据包时出错: {e}, 数据: {packet}")
                    continue
                    
            return packets
            
        except Exception as e:
            self.logger.error(f"解析日志行失败: {e}")
            return []

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行数据 - 兼容接口"""
        try:
            packets = self._parse_log_line(line)
            if packets:
                self.success_count += 1
                return packets[0]  # 返回第一个数据包
            else:
                self.error_count += 1
                return None
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"解析行时出错: {e}")
        return None

    def parse_from_string(self, data_string: str) -> List[Dict[str, Any]]:
        """从字符串解析数据"""
        try:
            return self._parse_log_line(data_string)
        except Exception as e:
            self.logger.error(f"从字符串解析数据时出错: {e}")
            return []

    def _extract_timestamp(self, line: str) -> Optional[float]:
        """提取时间戳"""
        try:
            timestamp_match = self.timestamp_pattern.search(line)
            if timestamp_match:
                ts = timestamp_match.group(1).replace('/', '-').replace('.', '-')
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S-%f")
                    return dt.timestamp()
                except:
                    try:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                        return dt.timestamp()
                    except:
                        pass
            return None
        except Exception as e:
            self.logger.error(f"提取时间戳时出错: {e}")
            return None

    def _extract_imu_data(self, line: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """提取IMU数据 - 兼容接口"""
        try:
            packets = self._parse_log_line(line)
            if packets:
                return "AA_BB_Format", packets[0]
            else:
                return "Unknown_Format", None
        except Exception as e:
            self.logger.error(f"提取IMU数据时出错: {e}")
            return "Error_Format", None

    def _validate_imu_data(self, data: Dict[str, float]) -> bool:
        try:
            required_fields = ['ax', 'ay', 'az', 'speed', 'wheel']
            optional_fields = ['gx', 'gy', 'gz']

            for field in required_fields:
                if field not in data or data[field] is None:
                    self.logger.warning(f"缺少必需字段: {field}")
                    return False

                if not isinstance(data[field], (int, float)):
                    self.logger.warning(f"字段 {field} 类型错误: {type(data[field])}")
                    return False

            for field in ['ax', 'ay', 'az']:
                if abs(data[field]) > 100:
                    self.logger.warning(f"字段 {field} 值超出范围: {data[field]}")
                    return False

            for field in optional_fields:
                if field in data and data[field] is not None:
                    if abs(data[field]) > 200:
                        self.logger.warning(f"字段 {field} 值超出范围: {data[field]}")
                        return False

            if data['speed'] < 0 or data['speed'] > 200:
                self.logger.warning(f"速度值超出范围: {data['speed']}")
                return False

            if abs(data['wheel']) > 720:
                self.logger.warning(f"转向角值超出范围: {data['wheel']}")
                return False

            return True
            
        except Exception as e:
            self.logger.error(f"验证IMU数据时出错: {e}")
            return False

    def get_parser_stats(self) -> Dict[str, Any]:
        """获取解析器统计信息"""
        total = self.success_count + self.error_count
        if total > 0:
            self.parse_ratio = self.success_count / total
            
        return {
            'success_count': self.success_count,
            'error_count': self.error_count,
            'parse_ratio': self.parse_ratio,
            'error_types': self.error_types.copy(),
            'format_stats': self.format_stats.copy(),
            'last_error_line': self.last_error_line,
            'last_timestamp': self.last_timestamp
        }

    @staticmethod
    def estimate_gz(speed_kmh: float, wheel_deg: float,
                    steering_ratio: float = 16.0,
                    wheelbase: float = 2.7) -> float:
        """自行车模型估算偏航角速度 (yaw rate)

        gz = v * tan(δ) / L

        Args:
            speed_kmh: 车速 (km/h)
            wheel_deg: 方向盘转角 (度)
            steering_ratio: 转向比, 默认16
            wheelbase: 轴距 (m), 默认2.7

        Returns:
            gz: 偏航角速度 (rad/s)
        """
        import math
        v = speed_kmh / 3.6
        delta_rad = math.radians(wheel_deg / steering_ratio)
        if abs(delta_rad) < 1e-10:
            return 0.0
        return v * math.tan(delta_rad) / wheelbase

    def reset_stats(self):
        """重置统计信息"""
        self.success_count = 0
        self.error_count = 0
        self.parse_ratio = 0.0
        self.error_types.clear()
        self.format_stats.clear()
        self.last_error_line = ""
        self.last_timestamp = None

    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        stats = self.get_parser_stats()
        stats.update({
            'total_attempts': self.success_count + self.error_count,
            'success_rate_percentage': round(self.parse_ratio * 100, 2) if self.parse_ratio > 0 else 0,
            'error_rate_percentage': round((1 - self.parse_ratio) * 100, 2) if self.parse_ratio > 0 else 0
        })
        return stats

    def diagnose_parsing_issues(self) -> List[str]:
        """诊断解析问题"""
        issues = []
        
        if self.error_count > 0:
            issues.append(f"发现 {self.error_count} 个解析错误")
            
            if self.parse_ratio < 0.8:
                issues.append("解析成功率低于80%，可能存在数据格式问题")
            
            if self.error_types:
                issues.append(f"主要错误类型: {list(self.error_types.keys())}")
        
        if self.success_count == 0:
            issues.append("没有成功解析任何数据，请检查数据格式")
        
        return issues

    def test_pattern_matching(self, test_data: str) -> Dict[str, Any]:
        """测试模式匹配"""
        results = {}
        
        # 测试时间戳模式
        timestamp_match = self.timestamp_pattern.search(test_data)
        results['timestamp_match'] = {
            'matched': timestamp_match is not None,
            'value': timestamp_match.group(1) if timestamp_match else None
        }
        
        # 测试数据模式
        data_match = self.data_pattern.search(test_data)
        results['data_pattern_match'] = {
            'matched': data_match is not None,
            'groups': data_match.groups() if data_match else None,
            'group_count': len(data_match.groups()) if data_match else 0
        }
        
        # 测试数据包模式
        packet_match = self.data_packet_pattern.search(test_data)
        results['packet_pattern_match'] = {
            'matched': packet_match is not None,
            'groups': packet_match.groups() if packet_match else None,
            'group_count': len(packet_match.groups()) if packet_match else 0
        }
        
        return results


    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """解析文件 - 读取完整内容后解析所有数据包
        
        处理跨行分割的数据包问题。
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析后的数据列表
        """
        import os
        import re as re_mod
        
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return self.parse_content(content)
    
    def parse_content(self, content: str) -> List[Dict[str, Any]]:
        """解析完整内容字符串 - 不依赖行边界
        
        先将所有行拼接为一行，防止数据值被行边界截断。
        
        数据格式: BB[CRC2hex]AA[cnt],ax,ay,az,gx,gy,gz,speed[,wheel,loc1,loc2]
        
        Args:
            content: 完整的数据内容字符串
            
        Returns:
            解析后的数据列表
        """
        import re as re_mod
        
        results = []
        
        # 步骤1: 移除所有行边界 (防止数据值被换行截断)
        joined = content.replace('\r\n', '').replace('\n', '').replace('\r', '')
        
        # 步骤2: 移除所有时间戳标记
        clean_content = re_mod.sub(r'\[[^\]]*\]', '', joined)
        
        # 步骤3: 移除多余空格 (保留逗号分隔)
        clean_content = re_mod.sub(r'\s+', '', clean_content)
        
        # 步骤4: BBxxAA 分割数据包
        packet_pattern = re_mod.compile(
            r'BB([0-9A-Fa-f]{2})AA(\d+),'  # BB[CRC]AA[cnt]
            r'([^B]+?)(?=BB[0-9A-Fa-f]{2}AA|\Z)'  # data until next BBxxAA or end
        )
        
        for match in packet_pattern.finditer(clean_content):
            try:
                crc_hex = match.group(1)
                cnt = int(match.group(2))
                data_part = match.group(3).strip().rstrip(',')
                
                if not data_part:
                    self.error_count += 1
                    continue
                
                values = [v.strip() for v in data_part.split(',')]
                n_vals = len(values)
                
                if n_vals < 7:
                    self.error_count += 1
                    continue
                
                record = {
                    'cnt': cnt,
                    'crc': crc_hex,
                    'ax': float(values[0]),
                    'ay': float(values[1]),
                    'az': float(values[2]),
                }

                if n_vals >= 10:
                    record['gx'] = float(values[3])
                    record['gy'] = float(values[4])
                    record['gz'] = float(values[5])
                    record['speed'] = float(values[6])
                    record['wheel'] = float(values[7])
                    record['loc1'] = float(values[8])
                    record['loc2'] = float(values[9])
                elif n_vals >= 7:
                    record['gx'] = None
                    record['gy'] = None
                    record['gz'] = None
                    record['speed'] = float(values[3])
                    record['wheel'] = float(values[4])
                    record['loc1'] = float(values[5])
                    record['loc2'] = float(values[6])
                
                self.success_count += 1
                results.append(record)
                    
            except (ValueError, IndexError) as e:
                self.error_count += 1
                continue
        
        if results:
            total = len(results) + self.error_count
            self.parse_ratio = len(results) / total if total > 0 else 0
        
        return results
    
    def parse_dataframe(self, file_path: str) -> 'pd.DataFrame':
        """解析文件并返回 DataFrame
        
        Args:
            file_path: 文件路径
            
        Returns:
            pandas DataFrame
        """
        import pandas as pd
        
        records = self.parse_file(file_path)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)


def test_parser():
    """测试解析器"""
    print("=== 测试IMU数据解析器 ===")
    
    # 创建解析器实例
    parser = IMUDataParser()
    
    # 测试数据
    test_cases = [
        # 标准格式
        "[2025-07-15 13:36:54-880] AA185,0.169873,0.000000,10.070361,-0.022500,-0.033750,-0.018750,57.000000,0.000000,119.100014,29.000099,BB37",
        # 带空格格式
        "[2025-07-15 13:36:55-094] AA 190, 0.210547, -0.011963, 9.929199, 0.017500, 0.020000, -0.013750, 57.000000, 0.000000, 119.100014, 29.000099, BB 5D",
        # 分号分隔格式
        "[2025-07-15 13:36:55-188] AA195;0.191406;-0.019141;10.103857;0.031250;0.021250;-0.013750;57.000000;0.000000;119.100014;29.000099;BB",
        # 竖线分隔格式
        "[2025-07-15 13:36:55-307] AA199|0.086133|0.023926|9.922021|0.041250|0.008750|-0.015000|58.000000|1.000000|119.100014|29.000099|BB"
    ]
    
    print(f"测试用例数量: {len(test_cases)}")
    
    for i, test_data in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i} ---")
        print(f"输入: {test_data}")
        
        # 测试模式匹配
        pattern_results = parser.test_pattern_matching(test_data)
        print(f"模式匹配结果: {pattern_results}")
        
        # 测试数据解析
        try:
            result = parser.parse_line(test_data)
            if result:
                print(f"解析成功: {result}")
                parser.success_count += 1
            else:
                print("解析失败")
                parser.error_count += 1
        except Exception as e:
            print(f"解析异常: {e}")
            parser.error_count += 1
    
    # 显示统计信息
    print(f"\n=== 测试结果统计 ===")
    stats = parser.get_parser_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # 诊断问题
    issues = parser.diagnose_parsing_issues()
    if issues:
        print(f"\n=== 问题诊断 ===")
        for issue in issues:
            print(f"- {issue}")


if __name__ == "__main__":
    test_parser()
