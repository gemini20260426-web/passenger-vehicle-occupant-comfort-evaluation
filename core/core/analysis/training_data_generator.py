#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练数据生成器 — 从 CSV 文件生成 LightGBM 训练数据

流程:
  1. 读取 CSV → 逐行送入 AnalysisPipeline
  2. 收集 FrameResult (FrameFeatures + ManeuverEvent)
  3. 使用管道检测的事件类型作为伪标签 (知识蒸馏)
  4. 通过 FeatureAdapter 提取 55 维特征向量
  5. 输出 (X, y) 用于训练

用法:
    python -m core.core.analysis.training_data_generator \
        --csv 徐宁数据/模拟数据/sim_25min_full.csv \
        --output training_data.npz \
        --max_samples 50000
"""

import os
import sys
import time
import logging
import argparse
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter, defaultdict, deque

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('training_data_generator')


class TrainingDataGenerator:
    """从 CSV 数据生成训练 (X, y) 对

    采用知识蒸馏策略: 使用规则引擎管道的事件检测结果作为伪标签。
    每帧的特征都标记为当前活跃 maneuver 的事件类型。
    """

    def __init__(
        self,
        csv_path: str,
        primary_imu: str = 'IMU5',
        max_samples: int = 100000,
        skip_normal: bool = True,
        normal_ratio: float = 0.3,
        skip_initial_seconds: float = 10.0,
    ):
        self.csv_path = csv_path
        self.primary_imu = primary_imu
        self.max_samples = max_samples
        self.skip_normal = skip_normal
        self.normal_ratio = normal_ratio
        self.skip_initial_seconds = skip_initial_seconds

        self._pipeline = None
        self._adapter = None
        self._label_counts: Dict[str, int] = defaultdict(int)
        self._current_event_type: str = 'normal'
        self._normal_count = 0

    def _init_pipeline(self):
        from core.core.analysis.pipeline import AnalysisPipeline
        self._pipeline = AnalysisPipeline()
        # 训练模式: 每帧都处理 (管道内部间隔检查有 bug, 训练时用 0)
        self._pipeline._processing_interval = 0.0
        logger.info("AnalysisPipeline 初始化完成 (processing_interval=0)")

    def _init_adapter(self):
        from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter
        self._adapter = FeatureAdapter()
        logger.info(f"FeatureAdapter 初始化完成 ({self._adapter.n_features} 维)")

    def generate(self) -> Tuple[np.ndarray, np.ndarray]:
        self._init_pipeline()
        self._init_adapter()

        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
        label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}
        id_to_label = {i: name for i, name in enumerate(BEHAVIOR_TYPES_V2)}
        logger.info(f"事件类型: {len(BEHAVIOR_TYPES_V2)} 类")

        logger.info(f"读取 CSV: {self.csv_path}")
        chunk_size = 50000
        features_list = []
        labels_list = []

        total_rows = 0
        processed = 0
        self._start_time = time.time()

        for chunk in pd.read_csv(self.csv_path, chunksize=chunk_size):
            if processed >= self.max_samples:
                break

            if 'imu_name' in chunk.columns:
                chunk = chunk[chunk['imu_name'].str.contains(self.primary_imu, na=False)]

            if len(chunk) == 0:
                continue

            for _, row in chunk.iterrows():
                if processed >= self.max_samples:
                    break
                total_rows += 1

                raw_data = self._row_to_raw_data(row)
                if raw_data is None:
                    continue

                try:
                    result = self._pipeline.process_frame(raw_data)
                except Exception as e:
                    continue

                processed += 1

                # 跳过初始 N 秒 (让管道先预热，但不收集数据)
                ts = raw_data.get('timestamp', 0.0)
                if ts < self.skip_initial_seconds:
                    if result.event is not None:
                        self._current_event_type = result.event.type
                    continue

                # 更新当前活跃事件类型
                if result.event is not None:
                    self._current_event_type = result.event.type

                # 收集特征 (所有帧都有 features, 但降采样以控制训练数据量)
                if result.features is None:
                    continue

                # 降采样: 每 N 帧取 1 帧 (避免训练数据过大)
                subsample_rate = 10  # 每 10 帧取 1 帧
                if processed % subsample_rate != 0:
                    continue

                event_type = self._current_event_type

                # normal 降采样
                if event_type in ('normal', 'unknown', ''):
                    self._normal_count += 1
                    if self.skip_normal and self._normal_count % 10 != 0:
                        continue

                X_vec = self._adapter.transform(result.features)
                features_list.append(X_vec)

                label_id = label_to_id.get(event_type, 0)
                labels_list.append(label_id)
                self._label_counts[event_type] += 1

                if processed % 5000 == 0:
                    elapsed = time.time() - self._start_time
                    logger.info(
                        f"进度: {processed}/{self.max_samples} 帧, "
                        f"已收集 {len(features_list)} 样本, "
                        f"耗时 {elapsed:.1f}s"
                    )

        if not features_list:
            logger.error("未生成任何训练样本！请检查 CSV 格式和管道配置")
            return np.array([]), np.array([])

        X = np.array(features_list, dtype=np.float32)
        y = np.array(labels_list, dtype=np.int32)

        elapsed = time.time() - self._start_time
        logger.info(
            f"训练数据生成完成: X={X.shape}, y={y.shape}, "
            f"耗时 {elapsed:.1f}s, {processed} 帧处理, "
            f"{len(features_list)} 样本收集"
        )
        logger.info(f"标签分布 (Top-10):")
        for label_id, count in Counter(y).most_common(10):
            name = id_to_label.get(label_id, f'id_{label_id}')
            logger.info(f"  {name:30s}: {count:5d} ({count/len(y)*100:.1f}%)")

        return X, y

    def _row_to_raw_data(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        raw = {}

        for col in ['rel_time', 'timestamp', 'time']:
            if col in row.index:
                raw['timestamp'] = float(row[col])
                break
        raw.setdefault('timestamp', 0.0)

        for col in ['Ax_m_s2', 'ax']:
            if col in row.index:
                raw['ax'] = float(row[col])
                break
        raw.setdefault('ax', 0.0)

        for col in ['Ay_m_s2', 'ay']:
            if col in row.index:
                raw['ay'] = float(row[col])
                break
        raw.setdefault('ay', 0.0)

        for col in ['Az_m_s2', 'az']:
            if col in row.index:
                raw['az'] = float(row[col])
                break
        raw.setdefault('az', 0.0)

        for col in ['Gx_dps', 'gx']:
            if col in row.index:
                raw['gx'] = float(row[col])
                break
        raw.setdefault('gx', 0.0)

        for col in ['Gy_dps', 'gy']:
            if col in row.index:
                raw['gy'] = float(row[col])
                break
        raw.setdefault('gy', 0.0)

        for col in ['Gz_dps', 'gz']:
            if col in row.index:
                raw['gz'] = float(row[col])
                break
        raw.setdefault('gz', 0.0)

        for col in ['speed', 'speed_kmh']:
            if col in row.index:
                raw['speed'] = float(row[col])
                break
        raw.setdefault('speed', 0.0)

        for col in ['wheel', 'steering_deg']:
            if col in row.index:
                raw['wheel'] = float(row[col])
                break
        raw.setdefault('wheel', 0.0)

        if 'channel' in row.index:
            raw['_source_name'] = str(row['channel'])
        if 'imu_name' in row.index:
            raw['_imu_name'] = str(row['imu_name'])
            # 覆盖 _source_name 为 IMU 名称，确保管道正确识别主 IMU
            raw['_source_name'] = str(row['imu_name'])

        return raw


def main():
    parser = argparse.ArgumentParser(description='生成 LightGBM 训练数据')
    parser.add_argument('--csv', type=str, required=True, help='输入 CSV 文件路径')
    parser.add_argument('--output', type=str, default='training_data.npz', help='输出文件路径')
    parser.add_argument('--max_samples', type=int, default=50000, help='最大处理样本数')
    parser.add_argument('--primary_imu', type=str, default='IMU5', help='主 IMU 名称过滤器')
    parser.add_argument('--skip_normal', action='store_true', default=True, help='跳过 normal 标签')
    parser.add_argument('--normal_ratio', type=float, default=0.3, help='normal 保留比例')

    args = parser.parse_args()

    generator = TrainingDataGenerator(
        csv_path=args.csv,
        primary_imu=args.primary_imu,
        max_samples=args.max_samples,
        skip_normal=args.skip_normal,
        normal_ratio=args.normal_ratio,
    )

    X, y = generator.generate()

    if len(X) == 0:
        logger.error("未生成训练数据")
        sys.exit(1)

    np.savez_compressed(args.output, X=X, y=y)
    logger.info(f"训练数据已保存: {args.output} ({X.shape[0]} 样本, {X.shape[1]} 特征)")

    from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
    id_to_label = {i: name for i, name in enumerate(BEHAVIOR_TYPES_V2)}
    print("\n=== 标签分布 ===")
    for label_id, count in Counter(y).most_common(20):
        name = id_to_label.get(label_id, f'id_{label_id}')
        print(f"  {name:30s}: {count:5d} ({count/len(y)*100:5.1f}%)")


if __name__ == '__main__':
    main()