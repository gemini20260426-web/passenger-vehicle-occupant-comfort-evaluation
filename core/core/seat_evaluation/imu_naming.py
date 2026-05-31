#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 命名系统统一映射模块

解决 V1/V2 两套 IMU 命名体系并存的问题，提供：
1. V1 命名 → 通用名 的正向映射
2. 通用名 → V1/V2 命名的反向映射
3. resolve_imu_name() 统一解析入口

用法:
    from core.core.seat_evaluation.imu_naming import IMU_NAME_MAPPING, resolve_imu_name

    canonical = resolve_imu_name('IMU5_座垫R点-1')  # -> 'seat_cushion'
    v1_name = resolve_imu_name('seat_cushion', 'v1')  # -> 'IMU5_座垫R点-1'
"""

IMU_NAME_MAPPING = {
    'v1_naming': {
        'IMU5_座垫R点-1': 'seat_cushion',
        'IMU7_座椅底部-1': 'seat_base',
    },
    'canonical_to_v1': {
        'seat_cushion': 'IMU5_座垫R点-1',
        'seat_base': 'IMU7_座椅底部-1',
    },
    'canonical_to_v2': {
        'seat_cushion': 'IMU5',
        'seat_base': 'IMU7',
    },
}


def resolve_imu_name(name: str, target_system: str = 'canonical') -> str:
    """
    将任意命名的 IMU 名称解析为目标系统的名称。

    Args:
        name: 输入名称，可以是 V1 名称（如 'IMU7_座椅底部-1'）、V2 名称（如 'IMU7'）或通用名（如 'seat_base'）
        target_system: 目标命名系统，'canonical'（默认）、'v1' 或 'v2'

    Returns:
        目标系统的对应名称，若无匹配则返回原始 name
    """
    for mapping_name, mapping in IMU_NAME_MAPPING.items():
        # Reverse lookup in v1_naming
        if name in IMU_NAME_MAPPING.get('v1_naming', {}):
            canonical = IMU_NAME_MAPPING['v1_naming'][name]
            if target_system == 'v2':
                return IMU_NAME_MAPPING.get('canonical_to_v2', {}).get(canonical, name)
            elif target_system == 'v1':
                return name
            return canonical

    # Check canonical_to_v1 reverse: if name matches a v1 value, treat as canonical
    canonical_to_v1 = IMU_NAME_MAPPING.get('canonical_to_v1', {})
    reverse_v1 = {v: k for k, v in canonical_to_v1.items()}
    if name in reverse_v1:
        canonical = reverse_v1[name]
        if target_system == 'v1':
            return name
        elif target_system == 'v2':
            return IMU_NAME_MAPPING.get('canonical_to_v2', {}).get(canonical, name)
        return canonical

    # Check canonical_to_v2 reverse
    canonical_to_v2 = IMU_NAME_MAPPING.get('canonical_to_v2', {})
    reverse_v2 = {v: k for k, v in canonical_to_v2.items()}
    if name in reverse_v2:
        canonical = reverse_v2[name]
        if target_system == 'v2':
            return name
        elif target_system == 'v1':
            return IMU_NAME_MAPPING.get('canonical_to_v1', {}).get(canonical, name)
        return canonical

    # Direct canonical lookup
    if target_system == 'v1':
        return IMU_NAME_MAPPING.get('canonical_to_v1', {}).get(name, name)
    elif target_system == 'v2':
        return IMU_NAME_MAPPING.get('canonical_to_v2', {}).get(name, name)

    return name


def get_primary_imu_names() -> list:
    """获取 V1 格式的主要 IMU 名称列表（兼容 pipeline.py 的 PRIMARY_IMU_NAMES）"""
    return list(IMU_NAME_MAPPING.get('v1_naming', {}).keys())


def get_canonical_imu_names() -> list:
    """获取通用格式的 IMU 名称列表"""
    return list(IMU_NAME_MAPPING.get('v1_naming', {}).values())


def is_primary_imu(imu_name: str) -> bool:
    """检查给定的 IMU 名称是否为主要 IMU（同时检查 V1/通用/V2 三种命名）"""
    v1_names = IMU_NAME_MAPPING.get('v1_naming', {})
    canonical_names = set(v1_names.values())
    v2_names = set(IMU_NAME_MAPPING.get('canonical_to_v2', {}).values())

    if imu_name in v1_names:
        return True
    if imu_name in canonical_names:
        return True
    if imu_name in v2_names:
        return True

    for v1_name in v1_names:
        if v1_name in imu_name:
            return True

    return False