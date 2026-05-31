#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 校准应用器
功能：
1. 从数据源配置加载校准参数
2. 对已解析的数据批量应用校准
3. 对单条数据实时应用校准
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# === 硬件常量（与校准引擎一致） ===
ACC_SCALE_LSB = 9.8 / 4096.0        # m/s²/LSB (±8g)
GYRO_SCALE_LSB = 0.07    # dps/LSB

# === 10路 IMU 名称列表 ===
IMU_NAMES = [
    'IMU1_头部眉心-1', 'IMU2_头部眉心-2',
    'IMU3_躯干T8-1',   'IMU4_躯干T8-2',
    'IMU5_座垫R点-1',  'IMU6_座垫R点-2',
    'IMU7_座椅底部-1', 'IMU8_座椅底部-2',
    'IMU9_胸骨剑突-1', 'IMU10_胸骨剑突-2',
]


class IMUCalibrationApplier:
    """
    IMU 校准应用器
    """

    def __init__(self, calibration_config: Optional[Dict[str, Any]] = None):
        """
        初始化校准应用器

        Args:
            calibration_config: 校准配置字典，结构：
                {
                    "enabled": true,
                    "uuid": "abc123...",
                    "parameters": {
                        "imu1": {
                            "ax_offset": 0.005, "ay_offset": -0.003, "az_offset": 0.001,
                            "gx_offset": 0.01, "gy_offset": -0.005, "gz_offset": 0.002
                        },
                        ...
                    }
                }
        """
        self.calibration_config = calibration_config or {}
        self.enabled = self.calibration_config.get('enabled', False)
        self.parameters = self.calibration_config.get('parameters', {})
        self.uuid = self.calibration_config.get('uuid', '')
        logger.info(f"IMUCalibrationApplier 初始化, enabled={self.enabled}")

    def is_enabled(self) -> bool:
        """检查是否启用校准"""
        return self.enabled and bool(self.parameters)

    def apply_single_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        对单条数据应用校准（在流式处理中使用）

        Args:
            record: 单条数据记录，包含 imu_name, Ax_m_s2, Ay_m_s2, Az_m_s2, Gx_dps, Gy_dps, Gz_dps

        Returns:
            校准后的记录
        """
        if not self.is_enabled():
            return record

        imu_name = record.get('imu_name', '')
        if not imu_name:
            return record

        # 获取该 IMU 的校准参数
        imu_params = self.parameters.get(imu_name, {})
        if not imu_params:
            return record

        # 应用校准
        result = record.copy()

        # 加速度校准：物理值减去偏置
        if 'Ax_m_s2' in result:
            result['Ax_m_s2'] = float(result['Ax_m_s2']) - imu_params.get('ax_offset', 0.0)
        if 'Ay_m_s2' in result:
            result['Ay_m_s2'] = float(result['Ay_m_s2']) - imu_params.get('ay_offset', 0.0)
        if 'Az_m_s2' in result:
            result['Az_m_s2'] = float(result['Az_m_s2']) - imu_params.get('az_offset', 0.0)

        # 陀螺仪校准：物理值减去偏置
        if 'Gx_dps' in result:
            result['Gx_dps'] = float(result['Gx_dps']) - imu_params.get('gx_offset', 0.0)
        if 'Gy_dps' in result:
            result['Gy_dps'] = float(result['Gy_dps']) - imu_params.get('gy_offset', 0.0)
        if 'Gz_dps' in result:
            result['Gz_dps'] = float(result['Gz_dps']) - imu_params.get('gz_offset', 0.0)

        return result

    def apply_batch(self, data_cache: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对批量数据应用校准（在加载时使用）

        Args:
            data_cache: 数据缓存列表

        Returns:
            校准后的数据缓存
        """
        if not self.is_enabled():
            logger.info("校准未启用，返回原始数据")
            return data_cache

        logger.info(f"开始对 {len(data_cache)} 条数据批量应用校准")
        result = []
        for record in data_cache:
            result.append(self.apply_single_record(record))
        logger.info(f"批量校准完成")
        return result

    def apply_to_dataframe_style(self, data_cache: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对 dataframe 风格的数据应用校准（IMU7-IMU10 在同一条记录里）

        Args:
            data_cache: 数据缓存列表

        Returns:
            校准后的数据缓存
        """
        if not self.is_enabled():
            return data_cache

        logger.info("开始对 dataframe 风格数据批量应用校准")
        result = []
        for record in data_cache:
            calib_record = record.copy()
            for imu_name in self.parameters:
                imu_params = self.parameters[imu_name]
                prefix = imu_name
                # 应用加速度校准
                if f'{prefix}_Ax' in calib_record:
                    calib_record[f'{prefix}_Ax'] = float(calib_record[f'{prefix}_Ax']) - imu_params.get('ax_offset', 0.0)
                if f'{prefix}_Ay' in calib_record:
                    calib_record[f'{prefix}_Ay'] = float(calib_record[f'{prefix}_Ay']) - imu_params.get('ay_offset', 0.0)
                if f'{prefix}_Az' in calib_record:
                    calib_record[f'{prefix}_Az'] = float(calib_record[f'{prefix}_Az']) - imu_params.get('az_offset', 0.0)
                # 应用陀螺仪校准
                if f'{prefix}_Gx' in calib_record:
                    calib_record[f'{prefix}_Gx'] = float(calib_record[f'{prefix}_Gx']) - imu_params.get('gx_offset', 0.0)
                if f'{prefix}_Gy' in calib_record:
                    calib_record[f'{prefix}_Gy'] = float(calib_record[f'{prefix}_Gy']) - imu_params.get('gy_offset', 0.0)
                if f'{prefix}_Gz' in calib_record:
                    calib_record[f'{prefix}_Gz'] = float(calib_record[f'{prefix}_Gz']) - imu_params.get('gz_offset', 0.0)
            result.append(calib_record)
        logger.info("dataframe 风格校准完成")
        return result


def create_applier_from_source_config(source_config: Any) -> IMUCalibrationApplier:
    """
    从数据源配置创建校准应用器

    Args:
        source_config: 数据源配置对象或字典

    Returns:
        IMUCalibrationApplier 实例
    """
    calibration_config = {}
    try:
        if isinstance(source_config, dict):
            calibration_config = source_config.get('imu_calibration', {})
        else:
            calibration_config = getattr(source_config, 'imu_calibration', {})
    except Exception as e:
        logger.warning(f"获取校准配置失败: {e}")

    return IMUCalibrationApplier(calibration_config)


def apply_calibration_to_cache(data_cache: List[Dict[str, Any]], 
                               calibration_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    快捷函数：对数据缓存应用校准

    Args:
        data_cache: 数据缓存
        calibration_config: 校准配置

    Returns:
        校准后的数据缓存
    """
    applier = IMUCalibrationApplier(calibration_config)
    if not applier.is_enabled():
        return data_cache

    # 检测数据格式
    if data_cache:
        first_record = data_cache[0]
        if 'imu_name' in first_record:
            return applier.apply_batch(data_cache)
        else:
            return applier.apply_to_dataframe_style(data_cache)

    return data_cache
