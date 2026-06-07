#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标签质量预检 — 在训练前验证 event_analysis CSV 的有效性

用法:
    python -m core.core.analysis.label_quality_validator --data_dir data_output
"""

import os
import sys
import argparse
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('label_validator')


def validate_event_labels(
    event_csv_path: str,
    parsed_csv_path: str,
    event_label_map: Optional[Dict[str, str]] = None,
) -> dict:
    """验证标注标签质量

    Args:
        event_csv_path: event_analysis.csv 路径
        parsed_csv_path: parsed_data CSV 路径
        event_label_map: 事件名映射字典

    Returns:
        dict: {status: 'ok'|'warning'|'error', issues: [...], stats: {...}}
    """
    if event_label_map is None:
        from core.core.analysis.fast_training_data_generator import EVENT_LABEL_MAP
        event_label_map = EVENT_LABEL_MAP

    events = pd.read_csv(event_csv_path)
    parsed = pd.read_csv(parsed_csv_path)

    issues = []
    stats = {}

    # 1. 检查必要列
    required = ['event', 't_start', 't_end']
    missing_cols = [col for col in required if col not in events.columns]
    if missing_cols:
        issues.append(f"MISSING_COL: 缺少必要列: {missing_cols}")

    # 2. 检查数据完整性
    null_counts = events[required].isnull().sum()
    for col, cnt in null_counts.items():
        if cnt > 0:
            issues.append(f"NULL_VALUE: {col} 列有 {cnt} 个空值")

    # 3. 检查时间范围对齐
    if 'rel_time' in parsed.columns:
        t_max = parsed['rel_time'].max()
        t_min = parsed['rel_time'].min()
        out_of_range = events[events['t_start'] > t_max]
        before_range = events[events['t_end'] < t_min]
        if len(out_of_range) > 0:
            issues.append(f"TIME_RANGE: {len(out_of_range)} 个事件 t_start > 数据 max ({t_max:.1f}s)")
        if len(before_range) > 0:
            issues.append(f"TIME_RANGE: {len(before_range)} 个事件 t_end < 数据 min ({t_min:.1f}s)")
        stats['data_time_range'] = (float(t_min), float(t_max))
        stats['event_time_range'] = (float(events['t_start'].min()), float(events['t_end'].max()))

    # 4. 检查事件名映射
    unique_events = events['event'].dropna().unique()
    unmapped = [e for e in unique_events if e not in event_label_map]
    if unmapped:
        issues.append(f"UNMAPPED_EVENT: {len(unmapped)} 个事件名无映射: {unmapped}")

    # 5. 统计事件分布
    event_counts = events['event'].value_counts().to_dict()
    stats['event_counts'] = event_counts
    stats['total_events'] = int(len(events))
    stats['unique_events'] = int(len(unique_events))
    stats['mapped_rate'] = float(
        1 - len(unmapped) / max(stats['unique_events'], 1)
    )

    # 6. 检查罕见事件 (< 5 样本, SMOTE 最小要求)
    rare = {k: v for k, v in event_counts.items() if v < 5 and k in event_label_map}
    very_rare = {k: v for k, v in event_counts.items() if v < 3 and k in event_label_map}
    if very_rare:
        issues.append(f"VERY_RARE: {len(very_rare)} 类 < 3 样本 (需合成补充): {very_rare}")
    elif rare:
        issues.append(f"RARE: {len(rare)} 类 < 5 样本 (SMOTE 可能失败): {rare}")

    # 7. 检查事件持续时间异常
    if 'duration' in events.columns:
        durations = events['duration'].dropna()
        zero_dur = (durations <= 0).sum()
        if zero_dur > 0:
            issues.append(f"ZERO_DURATION: {zero_dur} 个事件 duration <= 0")
        stats['duration_stats'] = {
            'min': float(durations.min()),
            'max': float(durations.max()),
            'mean': float(durations.mean()),
            'median': float(durations.median()),
        }

    # 8. 检查重叠事件窗口
    if len(events) > 1:
        sorted_events = events.sort_values('t_start')
        overlap_count = 0
        for i in range(len(sorted_events) - 1):
            if sorted_events.iloc[i]['t_end'] > sorted_events.iloc[i + 1]['t_start']:
                overlap_count += 1
        if overlap_count > 0:
            stats['overlapping_events'] = overlap_count
            if overlap_count > len(events) * 0.3:
                issues.append(f"OVERLAP: {overlap_count} 个事件存在时间重叠 ({overlap_count/len(events)*100:.0f}%)")

    # 判定状态
    error_count = sum(1 for i in issues if i.startswith(('MISSING', 'NULL_VALUE', 'UNMAPPED')))
    if error_count > 0:
        status = 'error'
    elif issues:
        status = 'warning'
    else:
        status = 'ok'

    return {
        'status': status,
        'issues': issues,
        'stats': stats,
        'event_csv': event_csv_path,
        'parsed_csv': parsed_csv_path,
    }


def validate_all_pairs(
    data_dir: str,
    event_label_map: Optional[Dict[str, str]] = None,
) -> Dict[str, dict]:
    """验证 data_output 目录下所有配对数据

    Returns:
        {配对标识: 验证结果}
    """
    results = {}

    # 收集 parsed_data CSV 文件
    parsed_files = []
    for f in sorted(os.listdir(data_dir)):
        if f.startswith('parsed_data_') and f.endswith('.csv'):
            parsed_files.append(os.path.join(data_dir, f))

    # 收集 expert_evaluation 目录
    eval_dirs = []
    for d in sorted(os.listdir(data_dir)):
        full_path = os.path.join(data_dir, d)
        if d.startswith('expert_evaluation_') and os.path.isdir(full_path):
            eval_dirs.append(full_path)

    logger.info(f"发现 {len(parsed_files)} 个 parsed_data, {len(eval_dirs)} 个 expert_evaluation")

    # 时间戳匹配
    import re
    for parsed_path in parsed_files:
        basename = os.path.basename(parsed_path)
        match = re.search(r'parsed_data_(\d{8}_\d{6})', basename)
        if not match:
            continue
        parsed_ts = match.group(1)

        # 寻找最近的 expert_evaluation
        best_eval = None
        best_diff = float('inf')
        for eval_dir in eval_dirs:
            eval_name = os.path.basename(eval_dir)
            eval_match = re.search(r'expert_evaluation_(\d{8}_\d{6})', eval_name)
            if not eval_match:
                continue
            eval_ts = eval_match.group(1)
            # 简单时间差 (基于字符串比较, 近似)
            diff = abs(int(parsed_ts) - int(eval_ts))
            if diff < best_diff:
                best_diff = diff
                best_eval = eval_dir

        if best_eval:
            event_csv = os.path.join(best_eval, 'event_analysis.csv')
            if os.path.exists(event_csv):
                pair_key = f"{os.path.basename(parsed_path)} ↔ {os.path.basename(best_eval)}"
                logger.info(f"验证: {pair_key}")
                result = validate_event_labels(event_csv, parsed_path, event_label_map)
                results[pair_key] = result
            else:
                logger.warning(f"expert_evaluation 目录缺少 event_analysis.csv: {best_eval}")
        else:
            logger.info(f"无匹配 expert_evaluation: {basename}")

    return results


def print_summary(results: Dict[str, dict]):
    """打印汇总报告"""
    print("\n" + "=" * 70)
    print("  标签质量预检报告")
    print("=" * 70)

    status_counts = Counter(r['status'] for r in results.values())
    print(f"\n总体: {len(results)} 对数据")
    print(f"  OK:      {status_counts.get('ok', 0)}")
    print(f"  WARNING: {status_counts.get('warning', 0)}")
    print(f"  ERROR:   {status_counts.get('error', 0)}")

    for pair_key, result in results.items():
        status_icon = {'ok': '[OK]', 'warning': '[WARN]', 'error': '[ERR]'}.get(result['status'], '[?]')
        print(f"\n{status_icon} {pair_key}")
        stats = result['stats']
        print(f"  事件总数: {stats['total_events']}, 类型数: {stats['unique_events']}, "
              f"映射率: {stats['mapped_rate']:.0%}")
        if 'event_counts' in stats:
            top5 = sorted(stats['event_counts'].items(), key=lambda x: -x[1])[:5]
            print(f"  Top-5 事件: {', '.join(f'{k}({v})' for k, v in top5)}")
        for issue in result['issues']:
            print(f"  → {issue}")

    print("\n" + "=" * 70)

    # 汇总所有数据中出现的罕见事件
    all_rare = set()
    for result in results.values():
        for issue in result['issues']:
            if issue.startswith('VERY_RARE') or issue.startswith('RARE'):
                all_rare.add(issue)
    if all_rare:
        print("\n跨文件罕见事件汇总 (需合成数据补充):")
        for issue in sorted(all_rare):
            print(f"  {issue}")

    return status_counts


def main():
    parser = argparse.ArgumentParser(description='标签质量预检')
    parser.add_argument('--data_dir', type=str, default='data_output',
                        help='data_output 目录路径')
    parser.add_argument('--event_csv', type=str, default=None,
                        help='单个 event_analysis.csv 路径')
    parser.add_argument('--parsed_csv', type=str, default=None,
                        help='单个 parsed_data CSV 路径')

    args = parser.parse_args()

    if args.event_csv and args.parsed_csv:
        result = validate_event_labels(args.event_csv, args.parsed_csv)
        print_summary({os.path.basename(args.parsed_csv): result})
    else:
        results = validate_all_pairs(args.data_dir)
        if not results:
            logger.error("未找到任何配对数据")
            sys.exit(1)
        print_summary(results)


if __name__ == '__main__':
    main()