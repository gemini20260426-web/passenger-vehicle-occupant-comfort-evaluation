#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量训练数据生成器 — 处理多个 parsed_data CSV 和 expert_evaluation 配对

功能:
  1. 自动扫描 data_output 目录，发现 parsed_data ↔ expert_evaluation 配对
  2. 批量调用 FastTrainingDataGenerator 生成特征
  3. 合并所有配对数据，输出统一的 .npz 训练数据
  4. 输出类分布统计和日志

用法:
    python -m core.core.analysis.batch_training_data_generator \
        --data_dir data_output \
        --output training_data_real.npz \
        --window_size 500 \
        --step_size 250
"""

import os
import sys
import re
import argparse
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('batch_train_gen')


class BatchTrainingDataGenerator:
    """批量训练数据生成器 — 处理多个 CSV 文件对"""

    def __init__(
        self,
        data_output_dir: str,
        primary_imu: str = 'IMU5',
        window_size: int = 500,
        step_size: int = 250,
        max_windows_per_file: int = 20000,
        # P1-1: 多通道支持
        multi_channel: bool = False,
        multi_channel_imus: Optional[List[str]] = None,
    ):
        self.data_output_dir = data_output_dir
        self.primary_imu = primary_imu
        self.window_size = window_size
        self.step_size = step_size
        self.max_windows_per_file = max_windows_per_file

        # P1-1: 多通道支持
        self.multi_channel = multi_channel
        self.multi_channel_imus = multi_channel_imus or ['IMU5', 'IMU1', 'IMU3', 'IMU9']

    # 最大时间差阈值 (秒): 超过此值的配对视为无效
    MAX_TIME_DIFF_SECONDS = 300  # 5分钟

    def discover_data_pairs(self) -> List[Tuple[str, str]]:
        """自动发现 parsed_data CSV 与 expert_evaluation 的配对

        基于时间戳命名匹配:
          parsed_data_20260606_094258.csv → expert_evaluation_20260606_095159/

        新增验证:
          - 时间差必须在 MAX_TIME_DIFF_SECONDS 内
          - expert_evaluation 的 event_analysis.csv 必须有有效内容

        Returns:
            [(parsed_csv_path, event_csv_path), ...] 仅返回有效配对
        """
        pairs = []

        # 收集 parsed_data CSV 文件
        parsed_files = []
        for f in sorted(os.listdir(self.data_output_dir)):
            if f.startswith('parsed_data_') and f.endswith('.csv'):
                parsed_files.append(os.path.join(self.data_output_dir, f))

        # 收集 expert_evaluation 目录 (预验证 event_analysis.csv 有内容)
        eval_dirs = []
        for d in sorted(os.listdir(self.data_output_dir)):
            full_path = os.path.join(self.data_output_dir, d)
            if d.startswith('expert_evaluation_') and os.path.isdir(full_path):
                event_csv = os.path.join(full_path, 'event_analysis.csv')
                if os.path.exists(event_csv) and os.path.getsize(event_csv) > 0:
                    # 额外验证: CSV 至少有表头+1行数据
                    try:
                        import pandas as pd
                        df = pd.read_csv(event_csv, nrows=2)
                        if len(df) > 0:
                            eval_dirs.append((d, full_path, event_csv))
                        else:
                            logger.warning(f"跳过空的 expert_evaluation: {d} (event_analysis.csv 无数据行)")
                    except Exception:
                        eval_dirs.append((d, full_path, event_csv))
                else:
                    logger.warning(f"跳过无效的 expert_evaluation: {d} (event_analysis.csv 缺失或为空)")

        logger.info(f"发现 {len(parsed_files)} 个 parsed_data, {len(eval_dirs)} 个有效 expert_evaluation")

        # 时间戳匹配 (带阈值)
        skipped_no_match = 0
        skipped_time_diff = 0
        for parsed_path in parsed_files:
            basename = os.path.basename(parsed_path)
            match = re.search(r'parsed_data_(\d{8}_\d{6})', basename)
            if not match:
                logger.warning(f"无法解析时间戳: {basename}")
                skipped_no_match += 1
                continue
            parsed_ts = match.group(1)

            # 寻找最近的有效 expert_evaluation
            best_eval = None
            best_diff = float('inf')
            for eval_name, eval_dir, event_csv in eval_dirs:
                eval_match = re.search(r'expert_evaluation_(\d{8}_\d{6})', eval_name)
                if not eval_match:
                    continue
                eval_ts = eval_match.group(1)
                # 只比较同一天的数据 (避免跨天误匹配)
                if parsed_ts[:8] != eval_ts[:8]:
                    continue
                diff = abs(int(parsed_ts) - int(eval_ts))
                if diff < best_diff:
                    best_diff = diff
                    best_eval = (eval_name, event_csv)

            if best_eval and best_diff <= self.MAX_TIME_DIFF_SECONDS:
                eval_name, event_csv = best_eval
                pairs.append((parsed_path, event_csv))
                logger.info(f"配对: {os.path.basename(parsed_path)} ↔ {eval_name} (时间差={best_diff}s)")
            elif best_eval:
                eval_name, _ = best_eval
                logger.warning(
                    f"跳过: {os.path.basename(parsed_path)} ↔ {eval_name} "
                    f"(时间差={best_diff}s > {self.MAX_TIME_DIFF_SECONDS}s 阈值)"
                )
                skipped_time_diff += 1
            else:
                logger.info(f"无匹配 expert_evaluation: {basename} (跳过，无标注数据)")
                skipped_no_match += 1

        logger.info(
            f"数据配对完成: {len(pairs)} 对有效, "
            f"跳过 {skipped_no_match} 个无匹配, {skipped_time_diff} 个超时差阈值"
        )
        return pairs

    def _generate_multi_channel(
        self, csv_path: str, event_csv: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """P1-1: 多通道特征提取 — 从多个 IMU 通道提取特征并拼接

        对每个 IMU 通道独立提取 55 维特征，然后拼接成 55×N 维特征向量。
        默认通道: IMU5(座垫输入) + IMU1(头部响应) + IMU9(胸骨响应)

        Returns:
            (X, y) — X shape=(n_samples, 55 * n_channels)
        """
        from core.core.analysis.fast_training_data_generator import FastTrainingDataGenerator
        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2

        label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}

        channel_features = {}
        channel_available = []

        for imu_name in self.multi_channel_imus:
            try:
                gen = FastTrainingDataGenerator(
                    csv_path=csv_path,
                    event_csv=event_csv,
                    primary_imu=imu_name,
                    window_size=self.window_size,
                    step_size=self.step_size,
                    max_windows=self.max_windows_per_file,
                )
                X_ch, y_ch = gen.generate()

                if len(X_ch) > 0:
                    channel_features[imu_name] = X_ch
                    channel_available.append(imu_name)
                    logger.info(f"  通道 {imu_name}: {X_ch.shape[0]} 样本, {X_ch.shape[1]} 维")
                else:
                    logger.warning(f"  通道 {imu_name}: 无有效数据，跳过")
            except Exception as e:
                logger.warning(f"  通道 {imu_name}: 处理失败 — {e}")

        if not channel_features:
            logger.error("所有通道均无有效数据")
            return np.array([]).reshape(0, 55), np.array([], dtype=np.int32)

        # 使用第一个通道的标签作为基准
        first_ch = channel_available[0]
        y = y_ch  # 来自最后一个通道的 generate，标签应一致

        # 拼接特征: 按通道顺序拼接
        X_concat = np.hstack([channel_features[ch] for ch in channel_available])
        logger.info(
            f"  多通道拼接完成: {len(channel_available)} 通道 "
            f"({', '.join(channel_available)}) → {X_concat.shape[1]} 维"
        )

        return X_concat, y

    def _save_baseline_for_feedback(self, X: np.ndarray, y: np.ndarray):
        """保存原始训练数据基线到 feedback/ 目录，供增量训练时合并使用

        增量训练器 (IncrementalTrainer) 在首次重训练时需要原始训练数据作为基线。
        此方法将 BatchTrainingDataGenerator 生成的原始数据复制一份到 feedback/ 目录，
        避免首次增量训练时因缺少原始数据而仅使用驳回样本训练导致模型退化。
        """
        try:
            feedback_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data_output', 'feedback',
            )
            os.makedirs(feedback_dir, exist_ok=True)
            merged_path = os.path.join(feedback_dir, 'merged_training_data.npz')

            # 仅当目标文件不存在时才保存 (避免覆盖已有合并数据)
            if not os.path.exists(merged_path):
                sample_weight = np.ones(len(y), dtype=np.float32)
                np.savez_compressed(
                    merged_path,
                    X=X, y=y, sample_weight=sample_weight,
                )
                logger.info(f"原始训练基线已保存: {merged_path} ({len(X)} 样本)")
            else:
                logger.info(f"原始训练基线已存在, 跳过: {merged_path}")
        except Exception as e:
            logger.warning(f"保存原始训练基线失败 (非致命): {e}")

    def generate_all(
        self,
        output_path: str = 'training_data_real.npz',
        pairs: Optional[List[Tuple[str, str]]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """批量生成训练数据并合并保存

        Args:
            output_path: 输出 .npz 文件路径
            pairs: 可选的手动指定配对列表

        Returns:
            (X, y, stats) — 合并后的训练数据和统计信息
        """
        from core.core.analysis.fast_training_data_generator import FastTrainingDataGenerator
        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2

        if pairs is None:
            pairs = self.discover_data_pairs()

        if not pairs:
            logger.error("未发现任何配对数据")
            raise ValueError("未发现任何配对数据")

        id_to_label = {i: name for i, name in enumerate(BEHAVIOR_TYPES_V2)}
        label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}

        all_X = []
        all_y = []
        file_stats = []

        for csv_path, event_csv in pairs:
            logger.info(f"\n{'='*60}")
            logger.info(f"处理: {os.path.basename(csv_path)}")
            logger.info(f"标注: {os.path.basename(event_csv)}")
            logger.info(f"{'='*60}")

            try:
                if self.multi_channel:
                    # P1-1: 多通道特征提取
                    X, y = self._generate_multi_channel(csv_path, event_csv)
                else:
                    gen = FastTrainingDataGenerator(
                        csv_path=csv_path,
                        event_csv=event_csv,
                        primary_imu=self.primary_imu,
                        window_size=self.window_size,
                        step_size=self.step_size,
                        max_windows=self.max_windows_per_file,
                    )
                    X, y = gen.generate()

                if len(X) == 0:
                    logger.warning(f"  → 未生成有效样本，跳过")
                    continue

                all_X.append(X)
                all_y.append(y)

                # 统计该文件
                n_classes = len(set(y))
                class_dist = Counter(y)
                file_stats.append({
                    'file': os.path.basename(csv_path),
                    'samples': len(X),
                    'classes': n_classes,
                    'class_dist': {id_to_label.get(k, f'id_{k}'): v for k, v in class_dist.most_common(10)},
                })
                logger.info(f"  → {len(X)} 样本, {n_classes} 类")

            except Exception as e:
                logger.error(f"处理失败: {csv_path} — {e}", exc_info=True)
                continue

        if not all_X:
            logger.error("所有文件均未生成有效样本")
            raise ValueError("所有文件均未生成有效样本")

        # 合并
        X_merged = np.vstack(all_X)
        y_merged = np.concatenate(all_y)

        # 保存
        np.savez_compressed(output_path, X=X_merged, y=y_merged)
        logger.info(f"\n{'='*60}")
        logger.info(f"合并训练数据: {X_merged.shape[0]} 样本, {X_merged.shape[1]} 特征, "
                     f"{len(set(y_merged))} 类")
        logger.info(f"已保存: {output_path}")

        # ── 保存原始基线到 feedback/ 目录 (供增量训练使用) ──
        self._save_baseline_for_feedback(X_merged, y_merged)

        # 全局类别分布
        global_dist = Counter(y_merged)
        logger.info("\n全局类别分布 (Top-15):")
        for label_id, cnt in global_dist.most_common(15):
            name = id_to_label.get(label_id, f'id_{label_id}')
            pct = cnt / len(y_merged) * 100
            logger.info(f"  {name:30s}: {cnt:6d} ({pct:5.1f}%)")

        # 统计信息
        stats = {
            'total_samples': int(len(X_merged)),
            'n_features': int(X_merged.shape[1]),
            'n_classes': int(len(set(y_merged))),
            'n_files': len(file_stats),
            'file_stats': file_stats,
            'class_distribution': {id_to_label.get(k, f'id_{k}'): v for k, v in global_dist.items()},
            'output_path': output_path,
        }

        return X_merged, y_merged, stats


def main():
    parser = argparse.ArgumentParser(
        description='批量训练数据生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m core.core.analysis.batch_training_data_generator \\
      --data_dir data_output \\
      --output training_data_real.npz
        """,
    )
    parser.add_argument('--data_dir', type=str, default='data_output',
                        help='data_output 目录路径')
    parser.add_argument('--output', type=str, default='training_data_real.npz',
                        help='输出 .npz 文件路径')
    parser.add_argument('--primary_imu', type=str, default='IMU5',
                        help='主 IMU 通道名')
    parser.add_argument('--window_size', type=int, default=500,
                        help='滑动窗口大小 (采样点)')
    parser.add_argument('--step_size', type=int, default=250,
                        help='滑动步长 (采样点)')
    parser.add_argument('--max_windows', type=int, default=20000,
                        help='每个文件最大窗口数')

    args = parser.parse_args()

    gen = BatchTrainingDataGenerator(
        data_output_dir=args.data_dir,
        primary_imu=args.primary_imu,
        window_size=args.window_size,
        step_size=args.step_size,
        max_windows_per_file=args.max_windows,
    )

    try:
        X, y, stats = gen.generate_all(output_path=args.output)
        print(f"\n成功: {stats['total_samples']} 样本, {stats['n_classes']} 类")
        sys.exit(0)
    except Exception as e:
        logger.error(f"生成失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()