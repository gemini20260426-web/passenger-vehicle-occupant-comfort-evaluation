#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
振动台架数据加载器 (ISO 10326-1)

支持格式: .xls / .xlsx / .csv / .txt
通道映射: 10列标准 → Time + T8(3) + R-point(3) + Platform(3)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict
import logging

from .shaker_models import (
    ShakerData, TriaxialChannels, DataQuality, QualityIssue
)

logger = logging.getLogger(__name__)


class ChannelMappingRequiredError(Exception):
    """无法自动检测通道映射，需要手动配置"""
    pass


class UnsupportedFormatError(Exception):
    """不支持的文件格式"""
    pass


class ShakerDataLoader:
    """
    台架数据加载器 — 自动检测格式、编码、通道映射。

    使用方法:
        loader = ShakerDataLoader()
        data = loader.load('一汽红旗1_Waveform.XLS')
        print(f"采样率: {data.fs} Hz, 时长: {data.duration:.1f}s")

    通道映射 (默认 10 列):
        Col 0: Time
        Col 1-3: 靠背 T8 (X, Y, Z)
        Col 4-6: 臀部 R-point (X, Y, Z)
        Col 7-9: 六轴平台 Platform (X, Y, Z)
    """

    ENCODING_TRIALS = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    EXPECTED_COLS = 10
    EXPECTED_FS = 1000.0
    FS_TOLERANCE = 0.05  # 采样率容差 5%

    # 通道列名关键词 (用于带表头的 CSV)
    COLUMN_KEYWORDS = {
        'time': ['time', 't', '时间', 'timestamp'],
        'platform_x': ['platform_x', 'plat_x', '台架_x', '平台_x', 'px'],
        'platform_y': ['platform_y', 'plat_y', '台架_y', '平台_y', 'py'],
        'platform_z': ['platform_z', 'plat_z', '台架_z', '平台_z', 'pz'],
        'r_x': ['r_x', 'seat_x', '坐垫_x', '臀部_x', 'rx', 'r-point_x'],
        'r_y': ['r_y', 'seat_y', '坐垫_y', '臀部_y', 'ry', 'r-point_y'],
        'r_z': ['r_z', 'seat_z', '坐垫_z', '臀部_z', 'rz', 'r-point_z'],
        't8_x': ['t8_x', 'backrest_x', '靠背_x', 'back_x', 'tx'],
        't8_y': ['t8_y', 'backrest_y', '靠背_y', 'back_y', 'ty'],
        't8_z': ['t8_z', 'backrest_z', '靠背_z', 'back_z', 'tz'],
    }

    def __init__(self):
        self._last_mapping: Dict = {}

    # ══════════════════════════════════════════════════
    # 公开接口
    # ══════════════════════════════════════════════════

    def load(self, filepath: str, condition_label: str = '') -> ShakerData:
        """
        加载台架数据文件。

        Args:
            filepath: 文件路径
            condition_label: 工况标签 (留空则自动从文件名提取)

        Returns:
            ShakerData 对象

        Raises:
            FileNotFoundError: 文件不存在
            UnsupportedFormatError: 不支持的格式
            ChannelMappingRequiredError: 需要手动通道映射
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        # 格式检测
        ext = path.suffix.lower()
        logger.info(f"加载文件: {path.name} (格式: {ext})")

        # 读取 DataFrame
        if ext in ('.xls', '.xlsx'):
            df = self._load_excel(filepath, ext)
        elif ext == '.csv':
            df = self._load_csv(filepath)
        elif ext == '.txt':
            df = self._load_csv(filepath, sep=r'\s+')
        else:
            raise UnsupportedFormatError(
                f"不支持的文件格式: {ext}，支持: .xls, .xlsx, .csv, .txt"
            )

        logger.info(f"DataFrame: {df.shape[0]} 行 × {df.shape[1]} 列")

        # 通道映射
        channel_map = self._auto_detect_channels(df)
        self._last_mapping = channel_map

        # 采样率检测
        fs = self._detect_fs(df, channel_map['time_col'])
        logger.info(f"采样率: {fs:.1f} Hz")

        # 提取数据
        time_col = channel_map.get('time_col')
        if time_col is not None:
            time = df.iloc[:, time_col].values.astype(np.float64)
        else:
            # 9列数据无时间列 → 按采样率生成时间轴
            time = np.arange(df.shape[0], dtype=np.float64) / fs
            logger.info(f"无时间列，按 fs={fs:.1f} Hz 生成时间轴 ({len(time)} 点)")

        t8 = TriaxialChannels(
            x=df.iloc[:, channel_map['t8_x']].values.astype(np.float64),
            y=df.iloc[:, channel_map['t8_y']].values.astype(np.float64),
            z=df.iloc[:, channel_map['t8_z']].values.astype(np.float64),
        )

        r_point = TriaxialChannels(
            x=df.iloc[:, channel_map['r_x']].values.astype(np.float64),
            y=df.iloc[:, channel_map['r_y']].values.astype(np.float64),
            z=df.iloc[:, channel_map['r_z']].values.astype(np.float64),
        )

        platform = TriaxialChannels(
            x=df.iloc[:, channel_map['platform_x']].values.astype(np.float64),
            y=df.iloc[:, channel_map['platform_y']].values.astype(np.float64),
            z=df.iloc[:, channel_map['platform_z']].values.astype(np.float64),
        )

        # 工况标签
        if not condition_label:
            condition_label = path.stem.replace('_Waveform', '').replace('-', '_')

        # 数据质量检查
        quality = self._quality_check(df, fs)

        return ShakerData(
            filepath=str(path),
            time=time,
            platform=platform,
            r_point=r_point,
            t8=t8,
            fs=fs,
            condition_label=condition_label,
            quality=quality,
            metadata={
                'filename': path.name,
                'format': ext,
                'rows': df.shape[0],
                'cols': df.shape[1],
                'fs': fs,
                'mapping': channel_map,
            },
        )

    def load_batch(self, directory: str, pattern: str = '*.XLS') -> List[ShakerData]:
        """批量加载目录中所有匹配文件 (含子目录递归)"""
        data_list = []
        dir_path = Path(directory)
        files = sorted(dir_path.rglob(pattern))
        if not files:
            files = sorted(dir_path.rglob('*.xls*')) + sorted(dir_path.rglob('*.csv'))
        for f in files:
            try:
                data = self.load(str(f))
                data_list.append(data)
                logger.info(f"{f.name}")
            except Exception as e:
                logger.error(f"{f.name}: {e}")
        return data_list

    # ══════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════

    def _load_excel(self, filepath: str, ext: str) -> pd.DataFrame:
        """加载 Excel 文件 — 处理无表头 .XLS"""
        engine = 'xlrd' if ext == '.xls' else 'openpyxl'
        xl = pd.ExcelFile(filepath, engine=engine)

        # 选择数据最多的 sheet
        sheet_sizes = {s: xl.parse(s).shape[0] for s in xl.sheet_names}
        best_sheet = max(sheet_sizes, key=sheet_sizes.get)
        logger.info(f"Sheet: {best_sheet} ({sheet_sizes[best_sheet]} 行)")

        # 首行检测: 数值型占比 > 80% → 无表头 (实测数据为此情况)
        first_row = xl.parse(best_sheet, nrows=1)
        numeric_count = sum(1 for c in first_row.columns
                          if pd.api.types.is_numeric_dtype(first_row[c]))
        numeric_ratio = numeric_count / max(1, first_row.shape[1])

        if numeric_ratio > 0.8:
            df = xl.parse(best_sheet, header=None)
            logger.info("检测: 无表头模式 (数值占比 %.0f%%)", numeric_ratio * 100)
        else:
            df = xl.parse(best_sheet, header=0)
            logger.info("检测: 有表头模式")

        return df

    def _load_csv(self, filepath: str, sep: str = ',') -> pd.DataFrame:
        """加载 CSV/TXT — 编码自动探测"""
        for enc in self.ENCODING_TRIALS:
            try:
                df = pd.read_csv(filepath, sep=sep, encoding=enc)
                logger.info(f"编码: {enc}, {df.shape[0]} 行 × {df.shape[1]} 列")
                return df
            except (UnicodeDecodeError, UnicodeError):
                continue
        # 最终回退
        raise UnicodeDecodeError(f"无法解码文件 {filepath}，已尝试: {self.ENCODING_TRIALS}")

    def _auto_detect_channels(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        三层回退的通道自动检测。

        层1: 列名匹配 (有表头 CSV)
        层2: 10列 → 默认映射
        层3: 9列 → 推断时间轴
        层4: 抛异常 → 要求手动配置
        """
        ncols = df.shape[1]

        # 层1: 列名匹配
        if not all(isinstance(c, (int, float)) for c in df.columns):
            mapping = self._detect_by_colname(df)
            if mapping:
                return mapping
            # 列名匹配失败 → 继续尝试数值列检测

        # 层2: 10列标准映射
        if ncols == self.EXPECTED_COLS:
            return {
                'time_col': 0,
                't8_x': 1, 't8_y': 2, 't8_z': 3,
                'r_x': 4, 'r_y': 5, 'r_z': 6,
                'platform_x': 7, 'platform_y': 8, 'platform_z': 9,
            }

        # 层3: 9列 (无时间列) → 推断 dt = 0.001s
        if ncols == 9:
            logger.warning("9列数据 (无时间列)，按 dt=0.001s 推断")
            return {
                'time_col': None,  # 将在 load() 中生成时间轴
                't8_x': 0, 't8_y': 1, 't8_z': 2,
                'r_x': 3, 'r_y': 4, 'r_z': 5,
                'platform_x': 6, 'platform_y': 7, 'platform_z': 8,
            }

        # 层4: 无法自动映射
        raise ChannelMappingRequiredError(
            f"无法自动检测通道映射 (列数={ncols}，期望=10)"
        )

    def _detect_by_colname(self, df: pd.DataFrame) -> Optional[Dict[str, int]]:
        """通过列名关键词匹配通道"""
        mapping = {}
        cols_lower = {i: str(c).lower() for i, c in enumerate(df.columns)}

        for channel, keywords in self.COLUMN_KEYWORDS.items():
            for idx, col_name in cols_lower.items():
                if any(kw in col_name for kw in keywords):
                    mapping[channel] = idx
                    break

        # 需要至少检测到 time + 3组传感器中的1组
        if 'time' in mapping and len(mapping) >= 4:
            # 对缺失通道使用默认回退
            if ncols := df.shape[1] >= 10:
                defaults = {'t8_x': 1, 't8_y': 2, 't8_z': 3,
                          'r_x': 4, 'r_y': 5, 'r_z': 6,
                          'platform_x': 7, 'platform_y': 8, 'platform_z': 9}
                for k, v in defaults.items():
                    if k not in mapping and v < df.shape[1]:
                        mapping[k] = v
            return mapping

        return None

    def _detect_fs(self, df: pd.DataFrame, time_col: int) -> float:
        """从时间列推断采样率"""
        if time_col is None:
            return self.EXPECTED_FS
        t = df.iloc[:, time_col].values[:100]
        dt = np.diff(t)
        dt_mean = np.mean(dt)
        if dt_mean <= 0:
            return self.EXPECTED_FS
        fs = 1.0 / dt_mean
        # 检查是否接近期望值
        if abs(fs - self.EXPECTED_FS) / self.EXPECTED_FS < self.FS_TOLERANCE:
            return self.EXPECTED_FS
        return round(fs)

    def _quality_check(self, df: pd.DataFrame, fs: float) -> DataQuality:
        """数据质量检查"""
        issues: List[QualityIssue] = []

        # 检查1: 缺失值
        nan_cols = [c for c in df.columns if df[c].isna().any()]
        if nan_cols:
            issues.append(QualityIssue(
                'missing_values',
                f'列 {nan_cols} 存在缺失值 ({df[nan_cols].isna().sum().sum()} 个)',
                'error'
            ))

        # 检查2: 恒值通道
        for c in df.columns:
            if df[c].std() < 1e-10:
                issues.append(QualityIssue(
                    'constant_channel',
                    f'列 {c} 为恒值 (std={df[c].std():.2e})',
                    'warning'
                ))

        # 检查3: 采样间隔不均匀
        if 'time_col' in self._last_mapping and self._last_mapping['time_col'] is not None:
            tc = self._last_mapping['time_col']
            dt = np.diff(df.iloc[:min(1000, len(df)), tc])
            if dt.std() / max(1e-12, dt.mean()) > 0.01:
                issues.append(QualityIssue(
                    'irregular_sampling',
                    f'时间间隔不均匀 (CV={dt.std()/dt.mean():.3f})',
                    'warning'
                ))

        # 检查4: 低激励通道 (std < 0.1)
        low_channels = []
        for c in range(df.shape[1]):
            if c == self._last_mapping.get('time_col'):
                continue
            if df.iloc[:, c].std() < 0.1:
                low_channels.append(c)
        if low_channels:
            issues.append(QualityIssue(
                'low_excitation',
                f'列 {low_channels} 激励信号过小 (std<0.1)，SEAT 值可能异常偏高',
                'warning'
            ))

        score = max(0, 100 - len(issues) * 10)
        recommendations = self._generate_recommendations(issues)

        return DataQuality(score=score, issues=issues, recommendations=recommendations)

    @staticmethod
    def _generate_recommendations(issues: List[QualityIssue]) -> List[str]:
        recs = []
        for issue in issues:
            if issue.issue_type == 'missing_values':
                recs.append('建议: 对缺失值使用插值填充或剔除对应帧')
            elif issue.issue_type == 'constant_channel':
                recs.append('建议: 确认该通道传感器是否正常工作')
            elif issue.issue_type == 'irregular_sampling':
                recs.append('建议: 对数据进行重采样到固定采样率')
            elif issue.issue_type == 'low_excitation':
                recs.append('建议: 低激励通道的 SEAT 值仅作参考，建议提高台架激励幅值')
        return recs