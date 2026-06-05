"""
CSV 数据适配器 — 本项目CSV格式 ↔ 仓库标准数据格式转换

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第二部分 4.1 节 (方案一: 适配器桥接)。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from .imu_mapper import IMUChannelMapper

logger = logging.getLogger(__name__)


class CSVDataAdapter:
    """CSV数据适配器 — 将本项目CSV转换为仓库标准格式

    数据流: 本项目CSV → CSVDataAdapter → 仓库ComparativeEvaluationEngine
    """

    # 仓库标准信号字段名
    REPO_SIGNAL_FIELDS = ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'speed', 'wheel']

    # 本项目CSV列名 → 仓库标准字段名
    CSV_TO_REPO_MAP = {
        'Ax_m_s2': 'ax',
        'Ay_m_s2': 'ay',
        'Az_m_s2': 'az',
        'Gx_dps': 'gx',
        'Gy_dps': 'gy',
        'Gz_dps': 'gz',
        'speed': 'speed',
        'wheel': 'wheel',
    }

    def __init__(self, csv_path: str):
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV文件不存在: {csv_path}")

        self.df = pd.read_csv(csv_path)
        self.mapper = IMUChannelMapper()
        self._validate_csv()

    def _validate_csv(self) -> None:
        """验证CSV文件必要字段"""
        required = ['rel_time']
        missing = [f for f in required if f not in self.df.columns]
        if missing:
            raise ValueError(f"CSV缺少必要字段: {missing}")

        # 检查IMU列
        imu_cols = [c for c in self.df.columns if any(
            imu in c for imu in self.mapper.get_all_imu_names()
        )]
        if not imu_cols:
            raise ValueError("CSV中未找到IMU数据列")

        logger.info(f"CSV验证通过: {len(self.df)} 行, {len(imu_cols)} 个IMU列")

    def get_time_series(self) -> np.ndarray:
        """获取时间序列"""
        return self.df['rel_time'].values

    def get_speed_series(self) -> Optional[np.ndarray]:
        """获取车速序列"""
        if 'speed' in self.df.columns:
            return self.df['speed'].values
        # 尝试模糊匹配
        for col in self.df.columns:
            if 'speed' in col.lower() and 'kmh' in col.lower():
                return self.df[col].values
        return None

    def get_wheel_series(self) -> Optional[np.ndarray]:
        """获取方向盘转角序列"""
        if 'wheel' in self.df.columns:
            return self.df['wheel'].values
        for col in self.df.columns:
            if 'wheel' in col.lower() or 'steering' in col.lower():
                return self.df[col].values
        return None

    def extract_experimental_group(self) -> Dict[str, np.ndarray]:
        """提取实验组数据"""
        return self._extract_group('experimental')

    def extract_control_group(self) -> Dict[str, np.ndarray]:
        """提取对照组数据"""
        return self._extract_group('control')

    def _extract_group(self, group: str) -> Dict[str, np.ndarray]:
        """按分组提取IMU数据"""
        imu_names = self.mapper.get_imus_by_group(group)
        data = {}

        for imu_name in imu_names:
            imu_data = self._extract_imu(imu_name)
            if imu_data is not None:
                data[imu_name] = imu_data

        return data

    def _extract_imu(self, imu_name: str) -> Optional[np.ndarray]:
        """提取单个IMU的数据"""
        cols = ['rel_time']
        for signal in ['Ax_m_s2', 'Ay_m_s2', 'Az_m_s2',
                        'Gx_dps', 'Gy_dps', 'Gz_dps']:
            col_name = f"{imu_name}_{signal}"
            if col_name in self.df.columns:
                cols.append(col_name)

        if len(cols) < 2:
            return None

        available = [c for c in cols if c in self.df.columns]
        return self.df[available].values

    def get_comparison_data(self) -> dict:
        """获取实验组 vs 对照组对比数据 (仓库标准格式)

        Returns:
            {
                'experimental': {
                    'head': {'ax': ..., 'ay': ..., 'az': ...},
                    'torso': {...},
                    ...
                },
                'control': {...},
                'common': {'speed': ..., 'wheel': ..., 'time': ...}
            }
        """
        result = {
            'experimental': {},
            'control': {},
            'common': {
                'time': self.get_time_series(),
                'speed': self.get_speed_series(),
                'wheel': self.get_wheel_series(),
            },
        }

        for group, imu_list in [
            ('experimental', self.mapper.get_experimental_imus()),
            ('control', self.mapper.get_control_imus()),
        ]:
            for imu_name in imu_list:
                imu_data = self._extract_imu(imu_name)
                if imu_data is None:
                    continue

                body_part = self.mapper.get_body_part(imu_name)
                if body_part not in result[group]:
                    result[group][body_part] = {}

                # 信号列索引: col0=rel_time, col1=Ax, col2=Ay, col3=Az, col4=Gx, col5=Gy, col6=Gz
                signal_names = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
                for i, sig in enumerate(signal_names):
                    if i + 1 < imu_data.shape[1]:
                        result[group][body_part][sig] = imu_data[:, i + 1]

        return result

    def get_event_window(self, start_time: float, end_time: float) -> dict:
        """获取指定时间窗口的事件数据"""
        mask = (self.df['rel_time'] >= start_time) & (self.df['rel_time'] <= end_time)
        window_df = self.df[mask]

        return {
            'time': window_df['rel_time'].values,
            'speed': window_df['speed'].values if 'speed' in window_df.columns else None,
            'wheel': window_df['wheel'].values if 'wheel' in window_df.columns else None,
            'n_frames': len(window_df),
            'duration': end_time - start_time,
        }


class RepositoryBridge:
    """仓库桥接器 — 将适配后的数据注入仓库评测引擎"""

    def __init__(self, csv_adapter: CSVDataAdapter):
        self.adapter = csv_adapter
        self.data = self.adapter.get_comparison_data()

    def evaluate_from_csv(self) -> dict:
        """执行完整的CSV离线评测

        模拟仓库 ComparativeEvaluationEngine 的 evaluate 方法，
        使用本项目的CSV数据作为输入。

        Returns:
            {
                'experimental': {body_part: {metric: value}},
                'control': {body_part: {metric: value}},
                'comparison': {body_part: {metric: {exp: x, ctrl: y, attenuation: z}}}
            }
        """
        results = {
            'experimental': {},
            'control': {},
            'comparison': {},
        }

        for group in ['experimental', 'control']:
            for body_part, signals in self.data[group].items():
                if body_part not in results[group]:
                    results[group][body_part] = {}

                for axis, values in signals.items():
                    if values is None or len(values) < 10:
                        continue

                    valid = values[~np.isnan(values)]
                    if len(valid) < 10:
                        continue

                    results[group][body_part][f'{axis}_rms'] = float(
                        np.sqrt(np.mean(valid ** 2))
                    )
                    results[group][body_part][f'{axis}_peak'] = float(
                        np.max(np.abs(valid))
                    )
                    results[group][body_part][f'{axis}_std'] = float(
                        np.std(valid)
                    )

        # 对比计算
        for body_part in set(results['experimental'].keys()) & set(results['control'].keys()):
            results['comparison'][body_part] = {}
            exp_metrics = results['experimental'][body_part]
            ctrl_metrics = results['control'][body_part]

            for metric in set(exp_metrics.keys()) & set(ctrl_metrics.keys()):
                exp_val = exp_metrics[metric]
                ctrl_val = ctrl_metrics[metric]
                if ctrl_val != 0:
                    attenuation = (ctrl_val - exp_val) / abs(ctrl_val) * 100
                else:
                    attenuation = 0.0

                results['comparison'][body_part][metric] = {
                    'experimental': exp_val,
                    'control': ctrl_val,
                    'attenuation_percent': round(float(attenuation), 2),
                }

        return results