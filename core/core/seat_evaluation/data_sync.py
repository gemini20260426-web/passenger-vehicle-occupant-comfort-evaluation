#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多通道数据同步对齐模块
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List, Tuple
from scipy import interpolate

logger = logging.getLogger(__name__)


class MultiChannelDataSynchronizer:
    """多通道数据同步器"""
    
    def __init__(self, target_sample_rate: float = 100.0, retention_size: int = 5000):
        self.target_sample_rate = target_sample_rate
        self.retention_size = retention_size
        self.channel_buffers: Dict[str, List[Tuple[float, Any]]] = {}
        self.last_synced_time = 0.0
    
    def add_channel_data(self, channel_id: str, timestamp: float, data: Any):
        """
        添加单通道数据
        
        Args:
            channel_id: 通道ID
            timestamp: 时间戳
            data: 数据
        """
        if channel_id not in self.channel_buffers:
            self.channel_buffers[channel_id] = []
        
        self.channel_buffers[channel_id].append((timestamp, data))
        
        # 保持缓冲区大小合理
        if len(self.channel_buffers[channel_id]) > self.retention_size * 2:
            self.channel_buffers[channel_id] = self.channel_buffers[channel_id][-self.retention_size:]
    
    def sync_and_align(self, channel_ids: Optional[List[str]] = None, 
                      start_time: Optional[float] = None,
                      end_time: Optional[float] = None) -> Optional[Dict[str, np.ndarray]]:
        """
        同步并对齐多通道数据
        
        Args:
            channel_ids: 要同步的通道ID列表，None表示所有
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            对齐后的数据字典
        """
        try:
            if channel_ids is None:
                channel_ids = list(self.channel_buffers.keys())
            
            if not channel_ids:
                return None
            
            # 获取时间范围
            if start_time is None or end_time is None:
                all_times = []
                for ch_id in channel_ids:
                    if ch_id in self.channel_buffers:
                        times = [t for t, _ in self.channel_buffers[ch_id]]
                        all_times.extend(times)
                
                if not all_times:
                    return None
                
                if start_time is None:
                    start_time = min(all_times)
                if end_time is None:
                    end_time = max(all_times)
            
            # 生成目标时间轴
            target_times = np.arange(
                start_time, 
                end_time, 
                1.0 / self.target_sample_rate
            )
            
            # 对每个通道进行插值对齐
            aligned_data = {}
            
            for ch_id in channel_ids:
                if ch_id not in self.channel_buffers:
                    continue
                
                buffer = self.channel_buffers[ch_id]
                if not buffer:
                    continue
                
                # 提取数据
                times = np.array([t for t, _ in buffer])
                values = np.array([d for _, d in buffer])
                
                # 插值
                if len(times) > 1:
                    # 支持不同类型的数据
                    if isinstance(values[0], (list, np.ndarray)):
                        # 数组类型，分别插值每个分量
                        aligned_array = []
                        for i in range(len(values[0])):
                            f = interpolate.interp1d(
                                times, values[:, i], 
                                kind='linear', bounds_error=False, fill_value=np.nan
                            )
                            result = f(target_times)
                            valid_mask = (target_times >= times[0]) & (target_times <= times[-1])
                            result = np.where(valid_mask, result, np.nan)
                            aligned_array.append(result)
                        aligned_data[ch_id] = np.array(aligned_array).T
                    else:
                        # 标量类型
                        f = interpolate.interp1d(
                            times, values, 
                            kind='linear', bounds_error=False, fill_value=np.nan
                        )
                        result = f(target_times)
                        valid_mask = (target_times >= times[0]) & (target_times <= times[-1])
                        result = np.where(valid_mask, result, np.nan)
                        aligned_data[ch_id] = result
            
            aligned_data['timestamps'] = target_times
            self.last_synced_time = end_time
            
            return aligned_data
            
        except Exception as e:
            logger.error(f"数据同步失败: {e}")
            return None
    
    def get_channel_data_window(self, channel_id: str, 
                               center_time: float,
                               pre_seconds: float = 0.5,
                               post_seconds: float = 1.5) -> Optional[Dict[str, Any]]:
        """
        获取指定通道的数据窗口
        
        Args:
            channel_id: 通道ID
            center_time: 中心时间
            pre_seconds: 前向秒数
            post_seconds: 后向秒数
            
        Returns:
            数据窗口
        """
        try:
            if channel_id not in self.channel_buffers:
                return None
            
            buffer = self.channel_buffers[channel_id]
            if not buffer:
                return None
            
            start_time = center_time - pre_seconds
            end_time = center_time + post_seconds
            
            # 提取窗口内的数据
            window_data = []
            for timestamp, data in buffer:
                if start_time <= timestamp <= end_time:
                    window_data.append((timestamp, data))
            
            if not window_data:
                return None
            
            return {
                'channel_id': channel_id,
                'center_time': center_time,
                'start_time': start_time,
                'end_time': end_time,
                'data': window_data
            }
            
        except Exception as e:
            logger.error(f"获取数据窗口失败: {e}")
            return None
    
    def clear_buffers(self):
        """清空所有缓冲区"""
        self.channel_buffers.clear()
        self.last_synced_time = 0.0


class TimeAligner:
    """时间对齐器"""
    
    @staticmethod
    def align_by_timestamp(data_dict: Dict[str, np.ndarray], 
                          target_timestamps: np.ndarray) -> Dict[str, np.ndarray]:
        """
        按时间戳对齐数据
        
        Args:
            data_dict: 数据字典，每个值是一个数组
            target_timestamps: 目标时间戳数组
            
        Returns:
            对齐后的数据
        """
        aligned = {}
        
        for key, data in data_dict.items():
            if key == 'timestamps':
                continue
            
            # 假设data的第一列是时间戳
            if data.ndim > 1:
                source_times = data[:, 0]
                source_values = data[:, 1:]
            else:
                source_times = data
                source_values = data[:, np.newaxis]
            
            # 插值对齐
            aligned_values = []
            for i in range(source_values.shape[1]):
                f = interpolate.interp1d(
                    source_times, source_values[:, i],
                    kind='linear', bounds_error=False, fill_value=np.nan
                )
                result = f(target_timestamps)
                valid_mask = (target_timestamps >= source_times[0]) & (target_timestamps <= source_times[-1])
                result = np.where(valid_mask, result, np.nan)
                aligned_values.append(result)
            
            aligned[key] = np.array(aligned_values).T
        
        aligned['timestamps'] = target_timestamps
        return aligned
    
    @staticmethod
    def cross_correlation_align(data_a: np.ndarray, 
                               data_b: np.ndarray,
                               max_shift: int = 100) -> Tuple[np.ndarray, int]:
        """
        互相关对齐
        
        Args:
            data_a: 数据A
            data_b: 数据B
            max_shift: 最大偏移样本数
            
        Returns:
            (对齐后的数据B, 偏移量)
        """
        try:
            # 计算互相关
            correlation = np.correlate(data_a - np.mean(data_a), 
                                      data_b - np.mean(data_b), 
                                      mode='full')
            
            # 寻找最大相关位置
            shift = np.argmax(correlation) - (len(data_a) - 1)
            
            # 限制在最大偏移范围内
            shift = np.clip(shift, -max_shift, max_shift)
            
            # 应用偏移
            if shift > 0:
                aligned_b = np.pad(data_b[:-shift], (shift, 0), mode='edge')
            elif shift < 0:
                aligned_b = np.pad(data_b[-shift:], (0, -shift), mode='edge')
            else:
                aligned_b = data_b.copy()
            
            return aligned_b, shift
            
        except Exception as e:
            logger.error(f"互相关对齐失败: {e}")
            return data_b.copy(), 0
