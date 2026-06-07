#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速训练数据生成器 — 直接从 CSV 提取特征，避开管道开销

策略:
  1. 读取 CSV (IMU5 主通道)
  2. 滑动窗口 (500ms) 提取时域+频域+运动学特征
  3. 使用 event_analysis.csv 标注事件窗口
  4. 输出 (X, y) 训练数据

相比管道方式快 100x+，适合大规模训练数据生成。
"""

import sys
import time
import argparse
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import Counter
from scipy import signal as scipy_signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('fast_train_gen')

# 系统 23 类事件类型
from core.core.analysis.core_types import BEHAVIOR_TYPES_V2

# 事件名映射: event_analysis.csv 中的中文名 → 系统事件类型
# 覆盖 expert_evaluation 中实际出现的所有事件名 (24 种)
EVENT_LABEL_MAP = {
    # ── 原有映射 (13 种) ──
    '复合工况': 'cornering_braking',
    '制动减速': 'normal_deceleration',
    '加速': 'normal_acceleration',
    '转向': 'wide_turn',
    '急加速': 'aggressive_acceleration',
    '急减速': 'aggressive_deceleration',
    '紧急制动': 'emergency_braking',
    '变道': 'lane_change',
    '弯道': 'cornering_deceleration',
    '静止': 'stopped',
    '匀速': 'constant_speed',
    '正常': 'normal',
    '起步': 'launch',
    # ── 新增映射 (11 种) — expert_evaluation 中实际出现 ──
    '转向/变道': 'lane_change',
    '左转': 'tight_turn',
    '右转': 'wide_turn',
    '急刹车': 'emergency_braking',
    '弯道加速': 'cornering_acceleration',
    '弯道减速': 'cornering_deceleration',
    '蛇形驾驶': 'weaving',
    '恒速行驶': 'constant_speed',
    '车道保持': 'lane_keeping',
    '正常加速': 'normal_acceleration',
    '正常减速': 'normal_deceleration',
    '激进加速': 'aggressive_acceleration',
    '激进减速': 'aggressive_deceleration',
    '大半径转弯': 'wide_turn',
    '小半径转弯': 'tight_turn',
    'U型转弯': 'u_turn',
    '急速变向': 'rapid_direction_change',
    '侧滑风险': 'skid_risk',
    '侧翻风险': 'rollover_risk',
    '驻车': 'stopped',
    '匀速直行': 'straight_driving',
    '传感器异常': 'sensor_fault',
    '剧烈颠簸': 'severe_bump',
}


class FastTrainingDataGenerator:
    """快速训练数据生成器 — 直接 CSV 特征提取"""

    def __init__(
        self,
        csv_path: str,
        event_csv: Optional[str] = None,
        primary_imu: str = 'IMU5',
        window_size: int = 500,
        step_size: int = 250,
        fs: float = 1000.0,
        max_windows: int = 20000,
    ):
        self.csv_path = csv_path
        self.event_csv = event_csv
        self.primary_imu = primary_imu
        self.window_size = window_size
        self.step_size = step_size
        self.fs = fs
        self.max_windows = max_windows

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        """生成训练数据"""
        from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter

        adapter = FeatureAdapter()
        label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}

        # 1. 加载 CSV 数据
        logger.info(f"加载 CSV: {self.csv_path}")
        df = pd.read_csv(self.csv_path)
        logger.info(f"总行数: {len(df)}")

        # 过滤主 IMU
        if 'imu_name' in df.columns:
            df['imu_name'] = df['imu_name'].astype(str)
            df = df[df['imu_name'].str.contains(self.primary_imu, na=False)]
            logger.info(f"过滤 {self.primary_imu} 后: {len(df)} 行")

        # 提取信号数组
        timestamps = df['rel_time'].values
        ax = df['Ax_m_s2'].values if 'Ax_m_s2' in df.columns else df.get('ax', np.zeros(len(df))).values
        ay = df['Ay_m_s2'].values if 'Ay_m_s2' in df.columns else df.get('ay', np.zeros(len(df))).values
        az = df['Az_m_s2'].values if 'Az_m_s2' in df.columns else df.get('az', np.zeros(len(df))).values
        gx = df['Gx_dps'].values if 'Gx_dps' in df.columns else df.get('gx', np.zeros(len(df))).values
        gy = df['Gy_dps'].values if 'Gy_dps' in df.columns else df.get('gy', np.zeros(len(df))).values
        gz = df['Gz_dps'].values if 'Gz_dps' in df.columns else df.get('gz', np.zeros(len(df))).values
        speed = df['speed'].values
        wheel = df['wheel'].values

        logger.info(f"信号范围: t=[{timestamps[0]:.1f}, {timestamps[-1]:.1f}]s, "
                     f"speed=[{speed.min():.1f}, {speed.max():.1f}]")

        # 2. 加载事件标注 (如果有)
        event_windows = []
        if self.event_csv:
            event_windows = self._load_event_labels(timestamps[0], timestamps[-1])
            logger.info(f"事件标注: {len(event_windows)} 个事件")

        # 3. 滑动窗口提取特征
        total_windows = min(
            (len(timestamps) - self.window_size) // self.step_size + 1,
            self.max_windows,
        )
        logger.info(f"滑动窗口: size={self.window_size}, step={self.step_size}, "
                     f"total={total_windows}")

        features_list = []
        labels_list = []

        for i in range(total_windows):
            start = i * self.step_size
            end = start + self.window_size

            # 提取窗口特征
            feat_dict = self._extract_window_features(
                ax[start:end], ay[start:end], az[start:end],
                gx[start:end], gy[start:end], gz[start:end],
                speed[start:end], wheel[start:end],
            )

            X_vec = adapter.get_feature_vector(feat_dict)
            features_list.append(X_vec)

            # 确定标签 (取窗口内多数标签，而非仅起始点)
            window_t_start = timestamps[start]
            window_t_end = timestamps[end - 1]
            label = self._get_majority_label(window_t_start, window_t_end, event_windows)
            labels_list.append(label_to_id.get(label, 0))

            if (i + 1) % 5000 == 0:
                logger.info(f"进度: {i+1}/{total_windows} 窗口")

        X = np.array(features_list, dtype=np.float32)
        y = np.array(labels_list, dtype=np.int32)

        # 统计
        id_to_label = {i: n for i, n in enumerate(BEHAVIOR_TYPES_V2)}
        logger.info(f"训练数据: X={X.shape}, y={y.shape}")
        for lid, cnt in Counter(y).most_common(10):
            name = id_to_label.get(lid, f'id_{lid}')
            logger.info(f"  {name}: {cnt} ({cnt/len(y)*100:.1f}%)")

        return X, y

    def _extract_window_features(
        self, ax, ay, az, gx, gy, gz, speed, wheel,
    ) -> Dict[str, float]:
        """从滑动窗口提取 55 维特征"""
        feat = {}

        # 时域特征 (20 维)
        for name, arr in [('ax', ax), ('ay', ay), ('az', az),
                           ('speed', speed), ('wheel', wheel)]:
            if len(arr) < 2:
                continue
            feat[f'{name}_mean'] = float(np.mean(arr))
            feat[f'{name}_std'] = float(np.std(arr))
            feat[f'{name}_rms'] = float(np.sqrt(np.mean(arr**2)))

        feat['ax_min'] = float(np.min(ax))
        feat['ax_max'] = float(np.max(ax))
        feat['ax_skewness'] = self._skewness(ax)
        feat['ax_kurtosis'] = self._kurtosis(ax)
        feat['ay_skewness'] = self._skewness(ay)
        feat['speed_range'] = float(np.max(speed) - np.min(speed))
        feat['wheel_range'] = float(np.max(wheel) - np.min(wheel))

        # 频域特征 (15 维)
        for name, arr in [('ax', ax), ('ay', ay), ('az', az),
                           ('speed', speed), ('wheel', wheel), ('gz', gz)]:
            if len(arr) < 4:
                continue
            try:
                f_psd, Pxx = scipy_signal.welch(arr, fs=self.fs, nperseg=min(256, len(arr)))
                feat[f'{name}_dominant_freq'] = float(f_psd[np.argmax(Pxx)])
                feat[f'{name}_spectral_centroid'] = float(
                    np.sum(f_psd * Pxx) / (np.sum(Pxx) + 1e-8)
                )
                if name in ('ax', 'ay', 'az'):
                    Pxx_norm = Pxx / (np.sum(Pxx) + 1e-8)
                    feat[f'{name}_spectral_entropy'] = float(
                        -np.sum(Pxx_norm * np.log2(Pxx_norm + 1e-8))
                    )
            except Exception:
                feat[f'{name}_dominant_freq'] = 0.0
                feat[f'{name}_spectral_centroid'] = 0.0
                if name in ('ax', 'ay', 'az'):
                    feat[f'{name}_spectral_entropy'] = 0.0

        # 运动学特征 (12 维) — jerk/snap
        dt = 1.0 / self.fs
        for name, arr in [('ax', ax), ('ay', ay), ('az', az),
                           ('speed', speed), ('wheel', wheel), ('gz', gz)]:
            if len(arr) < 3:
                feat[f'{name}_jerk'] = 0.0
                feat[f'{name}_snap'] = 0.0
                continue
            jerk = np.diff(arr) / dt
            snap = np.diff(jerk) / dt
            feat[f'{name}_jerk'] = float(np.mean(np.abs(jerk)))
            feat[f'{name}_snap'] = float(np.mean(np.abs(snap))) if len(snap) > 0 else 0.0

        # 物理特征 (8 维)
        speed_ms = np.mean(speed)
        feat['speed_ms'] = float(speed_ms)
        feat['turn_radius'] = float(speed_ms**2 / (np.std(gz) * np.pi / 180 + 1e-6)) if np.std(gz) > 0.01 else 999.0
        feat['expected_yaw_rate'] = float(np.std(gz))
        feat['yaw_rate_error'] = 0.0
        feat['lateral_accel_ratio'] = float(np.std(ay) / (np.std(ax) + 1e-6))
        feat['slip_angle_est'] = float(np.arctan2(np.mean(ay), speed_ms + 1e-6))
        feat['accel_speed_ratio'] = float(np.mean(np.abs(ax)) / (speed_ms + 1e-6))
        feat['roll_est'] = float(np.std(gx))

        return feat

    def _load_event_labels(self, t_min: float, t_max: float) -> List[Tuple[float, float, str]]:
        """加载事件标注"""
        df = pd.read_csv(self.event_csv)
        windows = []
        unmapped_events = set()
        for _, row in df.iterrows():
            t_start = float(row['t_start'])
            t_end = float(row['t_end'])
            if t_end < t_min or t_start > t_max:
                continue
            event_name = str(row['event'])
            if event_name not in EVENT_LABEL_MAP:
                unmapped_events.add(event_name)
                continue
            mapped = EVENT_LABEL_MAP[event_name]
            windows.append((t_start, t_end, mapped))
        if unmapped_events:
            logger.warning(f"未映射事件名 ({len(unmapped_events)} 种): {unmapped_events}")
        return windows

    def _get_label(self, t: float, event_windows: List[Tuple[float, float, str]]) -> str:
        """获取时间点 t 的标签 (处理重叠事件: 优先匹配持续时间较短的事件)"""
        matches = [(t_start, t_end, label) for t_start, t_end, label in event_windows
                   if t_start <= t <= t_end]
        if not matches:
            return 'normal'
        # 重叠事件: 优先选择持续时间最短的事件 (更精确的标注)
        if len(matches) > 1:
            matches.sort(key=lambda x: x[1] - x[0])
        return matches[0][2]

    def _get_majority_label(
        self, t_start: float, t_end: float,
        event_windows: List[Tuple[float, float, str]],
        n_samples: int = 10,
    ) -> str:
        """获取窗口 [t_start, t_end] 内的多数标签
        
        在窗口内均匀采样 n_samples 个时间点，统计每个时间点对应的标签，
        返回出现次数最多的标签（平局时优先选择非 normal 标签）。
        
        Args:
            t_start: 窗口起始时间
            t_end: 窗口结束时间
            event_windows: 事件窗口列表
            n_samples: 采样点数
        """
        from collections import Counter
        
        label_counts = Counter()
        for i in range(n_samples):
            t = t_start + (t_end - t_start) * i / (n_samples - 1) if n_samples > 1 else t_start
            label = self._get_label(t, event_windows)
            label_counts[label] += 1
        
        # 平局时优先选择非 normal 标签（更有信息量）
        if len(label_counts) > 1:
            most_common = label_counts.most_common()
            if most_common[0][0] == 'normal' and len(most_common) > 1:
                return most_common[1][0]
        return label_counts.most_common(1)[0][0]

    @staticmethod
    def _skewness(x: np.ndarray) -> float:
        std = np.std(x)
        if std < 1e-8:
            return 0.0
        return float(np.mean((x - np.mean(x))**3) / std**3)

    @staticmethod
    def _kurtosis(x: np.ndarray) -> float:
        std = np.std(x)
        if std < 1e-8:
            return 0.0
        return float(np.mean((x - np.mean(x))**4) / std**4 - 3)


def main():
    parser = argparse.ArgumentParser(description='快速训练数据生成')
    parser.add_argument('--csv', type=str, required=True, help='CSV 文件路径')
    parser.add_argument('--event_csv', type=str, default=None, help='事件标注 CSV')
    parser.add_argument('--output', type=str, default='training_data.npz')
    parser.add_argument('--max_windows', type=int, default=20000)
    parser.add_argument('--window_size', type=int, default=500)
    parser.add_argument('--step_size', type=int, default=250)

    args = parser.parse_args()

    gen = FastTrainingDataGenerator(
        csv_path=args.csv,
        event_csv=args.event_csv,
        max_windows=args.max_windows,
        window_size=args.window_size,
        step_size=args.step_size,
    )

    X, y = gen.generate()

    if len(X) == 0:
        logger.error("未生成训练数据")
        sys.exit(1)

    np.savez_compressed(args.output, X=X, y=y)
    logger.info(f"训练数据已保存: {args.output}")


if __name__ == '__main__':
    main()