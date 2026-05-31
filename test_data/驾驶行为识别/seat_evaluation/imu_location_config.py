#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU位置映射配置模块
定义10个IMU通道到物理位置的映射关系
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class IMULocationConfig:
    """IMU位置配置"""
    location_id: str
    location_name_cn: str
    location_name_en: str
    experimental_channel: str
    control_channel: str
    primary_metrics: List[str]
    description: str


# IMU位置映射配置 - 与CAN全量解析标签页IMU名称一致
IMU_LOCATION_MAPPING = {
    'head': IMULocationConfig(
        location_id='head',
        location_name_cn='头部眉心',
        location_name_en='Head',
        experimental_channel='IMU1_头部眉心-1',
        control_channel='IMU2_头部眉心-2',
        primary_metrics=['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT', 'ACC_RMS', 'ACC_PEAK'],
        description='头部冲击评测 (ch1)'
    ),
    'torso': IMULocationConfig(
        location_id='torso',
        location_name_cn='躯干T8',
        location_name_en='Torso T8',
        experimental_channel='IMU3_躯干T8-1',
        control_channel='IMU4_躯干T8-2',
        primary_metrics=['AW_XY', 'DISP_TR', 'STFT_FC', 'STFT_KT', 'STFT_CE', 'ACC_RMS', 'ACC_PEAK'],
        description='背部支撑评测 (ch2)'
    ),
    'seat_r': IMULocationConfig(
        location_id='seat_r',
        location_name_cn='座垫R点',
        location_name_en='Seat R-Point',
        experimental_channel='IMU5_座垫R点-1',
        control_channel='IMU6_座垫R点-2',
        primary_metrics=['SEAT_Z', 'SEAT_XY', 'VDV_Z', 'AW_Z', 'OVTV', 'TR_Z', 'R_FACTOR', 'RFC_CC', 'FDS_D', 'FDS_R', 'STFT_FC', 'STFT_KT', 'STFT_CE', 'ACC_RMS', 'ACC_PEAK'],
        description='臀部振动评测 (ch3)'
    ),
    'seat_bottom': IMULocationConfig(
        location_id='seat_bottom',
        location_name_cn='座椅底部',
        location_name_en='Seat Bottom',
        experimental_channel='IMU7_座椅底部-1',
        control_channel='IMU8_座椅底部-2',
        primary_metrics=['ACC_RMS', 'ACC_PEAK'],
        description='激励基准参考点 (ch4)'
    ),
    'sternum': IMULocationConfig(
        location_id='sternum',
        location_name_cn='胸骨剑突',
        location_name_en='Sternum',
        experimental_channel='IMU9_胸骨剑突-1',
        control_channel='IMU10_胸骨剑突-2',
        primary_metrics=['STFT_FC', 'STFT_KT', 'STFT_CE', 'ACC_RMS', 'ACC_PEAK'],
        description='侧向振动评测 (ch5)'
    )
}

# 位置ID列表（按重要性排序）
LOCATION_IDS = ['head', 'torso', 'seat_r', 'seat_bottom', 'sternum']

# 位置名称映射
LOCATION_NAMES = {
    'head': '头部眉心',
    'torso': '躯干T8',
    'seat_r': '座垫R点',
    'seat_bottom': '座椅底部',
    'sternum': '胸骨剑突'
}

# 实验组通道列表
EXPERIMENTAL_CHANNELS = [
    IMU_LOCATION_MAPPING[loc].experimental_channel 
    for loc in LOCATION_IDS
]

# 对照组通道列表
CONTROL_CHANNELS = [
    IMU_LOCATION_MAPPING[loc].control_channel 
    for loc in LOCATION_IDS
]

# 所有IMU通道
ALL_IMU_CHANNELS = EXPERIMENTAL_CHANNELS + CONTROL_CHANNELS


def get_location_config(location_id: str) -> Optional[IMULocationConfig]:
    """获取位置配置"""
    return IMU_LOCATION_MAPPING.get(location_id)


def get_location_by_channel(channel_id: str) -> Optional[IMULocationConfig]:
    """通过通道ID获取位置配置"""
    for config in IMU_LOCATION_MAPPING.values():
        if config.experimental_channel == channel_id or config.control_channel == channel_id:
            return config
    return None


def get_channel_by_location(location_id: str, group: str = 'experimental') -> Optional[str]:
    """通过位置和组别获取通道ID"""
    config = IMU_LOCATION_MAPPING.get(location_id)
    if not config:
        return None
    return config.experimental_channel if group == 'experimental' else config.control_channel


def get_metrics_for_location(location_id: str) -> List[str]:
    """获取指定位置的主要指标"""
    config = IMU_LOCATION_MAPPING.get(location_id)
    if not config:
        return []
    return config.primary_metrics.copy()


def get_all_metrics() -> List[str]:
    """获取所有指标（去重）"""
    all_metrics = set()
    for config in IMU_LOCATION_MAPPING.values():
        all_metrics.update(config.primary_metrics)
    return sorted(list(all_metrics))


def is_behavior_analysis_channel(channel_id: str) -> bool:
    """判断是否为行为分析通道（地板IMU不在座椅评测位置中）"""
    return channel_id not in ALL_IMU_CHANNELS


def is_seat_evaluation_channel(channel_id: str) -> bool:
    """判断是否为座椅评测通道"""
    return channel_id in ALL_IMU_CHANNELS


def get_all_locations() -> List[str]:
    """获取所有位置ID列表"""
    return LOCATION_IDS.copy()


INDICATOR_CATEGORIES = {
    'general': {
        'name': '通用基础指标',
        'description': '三轴合成加速度RMS与峰值，适用于所有IMU位置',
        'indicators': ['ACC_RMS', 'ACC_PEAK'],
    },
    'steady_state': {
        'name': '稳态舒适度',
        'description': '基于RMS的持续振动舒适度评价',
        'indicators': ['SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY', 'OVTV', 'R_FACTOR'],
    },
    'dynamic': {
        'name': '动态舒适度',
        'description': '累积剂量、传递率及疲劳损伤评价',
        'indicators': ['VDV_Z', 'TR_Z', 'DISP_TR', 'RFC_CC', 'FDS_D', 'FDS_R', 'STFT_FC', 'STFT_KT', 'STFT_CE'],
    },
    'transient': {
        'name': '瞬态感受评价',
        'description': '冲击、碰撞及瞬态响应评价',
        'indicators': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_Q', 'SRS_PV', 'SRS_ATT'],
    },
}

CATEGORY_ORDER = ['steady_state', 'dynamic', 'transient']


def get_indicator_category(indicator_id: str) -> str:
    """获取指标所属分类"""
    for cat_id, cat_info in INDICATOR_CATEGORIES.items():
        if indicator_id in cat_info['indicators']:
            return cat_id
    return 'steady_state'


def get_category_indicators(category_id: str) -> List[str]:
    """获取分类下的所有指标"""
    cat = INDICATOR_CATEGORIES.get(category_id, {})
    return cat.get('indicators', []).copy()


def get_indicators_for_location_by_category(location_id: str) -> Dict[str, List[str]]:
    """获取指定位置按分类分组的指标"""
    config = IMU_LOCATION_MAPPING.get(location_id)
    if not config:
        return {}
    result = {}
    for cat_id in CATEGORY_ORDER:
        cat_indicators = [m for m in config.primary_metrics if m in INDICATOR_CATEGORIES[cat_id]['indicators']]
        if cat_indicators:
            result[cat_id] = cat_indicators
    return result
