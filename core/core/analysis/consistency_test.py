"""
流式vs离线一致性验证测试

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 8.3 节。
验证 StreamingProcessor 和 BatchProcessor 对同一数据的检测结果完全一致。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

from core.core.analysis.dual_mode_processor import (
    StreamingProcessor, BatchProcessor, SharedModelRegistry
)
from core.core.analysis.tri_stage_detector import EventResult

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyReport:
    """一致性验证报告"""
    stream_count: int = 0
    batch_count: int = 0
    count_match: bool = False
    type_mismatches: int = 0
    type_mismatch_details: List[Dict] = field(default_factory=list)
    conf_diffs: List[float] = field(default_factory=list)
    max_conf_diff: float = 0.0
    mean_conf_diff: float = 0.0
    consistent: bool = False
    total_frames: int = 0
    processing_time_s: float = 0.0


def verify_streaming_vs_batch(
    data_path: str,
    fs: float = 100.0,
    n_frames: int = 5000,
    window_size: int = 500,
    step_size: int = 50,
    tolerance_confidence: float = 1e-6,
) -> ConsistencyReport:
    """流式 vs 离线 一致性验证

    Args:
        data_path: CSV数据文件路径
        fs: 采样率
        n_frames: 测试帧数
        window_size: 滑动窗口大小
        step_size: 步长
        tolerance_confidence: 置信度容许偏差

    Returns:
        ConsistencyReport: 一致性验证报告
    """
    import time

    report = ConsistencyReport()

    # ── 加载数据 ──
    df = pd.read_csv(data_path)
    field_names = ['rel_time', 'speed', 'wheel', 'Ax', 'Ay', 'Az']

    # 映射CSV列名
    col_map = {}
    for name in field_names:
        if name in df.columns:
            col_map[name] = name
        else:
            for col in df.columns:
                if name.lower() in col.lower():
                    col_map[name] = col
                    break

    available = [col_map.get(n) for n in field_names if n in col_map]
    data = df[available].values[:n_frames]
    report.total_frames = len(data)

    t0 = time.time()

    # ── 离线批处理 ──
    batch_processor = BatchProcessor(
        window_size=window_size, step_size=step_size, fs=fs
    )
    batch_results = list(batch_processor.process(data))

    # ── 流式模拟 ──
    stream_processor = StreamingProcessor(
        window_size=window_size, step_size=step_size, fs=fs
    )
    stream_results = []
    for row in data:
        frame = {}
        for i, name in enumerate(field_names):
            if i < len(row):
                frame[name] = row[i]
        result = stream_processor.feed_frame(frame)
        if result:
            stream_results.extend(result)

    report.processing_time_s = round(time.time() - t0, 2)

    # ── 对比分析 ──
    report.stream_count = len(stream_results)
    report.batch_count = len(batch_results)
    report.count_match = report.stream_count == report.batch_count

    if report.count_match:
        for i, (sr, br) in enumerate(zip(stream_results, batch_results)):
            if sr.event_type != br.event_type:
                report.type_mismatches += 1
                report.type_mismatch_details.append({
                    'index': i,
                    'stream': sr.event_type,
                    'batch': br.event_type,
                    'stream_conf': sr.confidence,
                    'batch_conf': br.confidence,
                })
            conf_diff = abs(sr.confidence - br.confidence)
            report.conf_diffs.append(conf_diff)
    else:
        # 数量不匹配
        min_len = min(len(stream_results), len(batch_results))
        for i in range(min_len):
            sr = stream_results[i]
            br = batch_results[i]
            if sr.event_type != br.event_type:
                report.type_mismatches += 1
            conf_diff = abs(sr.confidence - br.confidence)
            report.conf_diffs.append(conf_diff)

    if report.conf_diffs:
        report.max_conf_diff = round(float(max(report.conf_diffs)), 10)
        report.mean_conf_diff = round(float(np.mean(report.conf_diffs)), 10)

    report.consistent = (
        report.count_match
        and report.type_mismatches == 0
        and report.max_conf_diff < tolerance_confidence
    )

    return report


def verify_window_equivalence(
    data_path: str, window_size: int = 500, fs: float = 100.0
) -> dict:
    """验证环形缓冲区窗口与slice窗口的数学等价性"""
    df = pd.read_csv(data_path)

    # 提取数据
    fields = ['speed', 'wheel', 'Ax', 'Ay', 'Az']
    data_cols = [c for f in fields for c in df.columns if f.lower() in c.lower()]
    data = df[data_cols[:5]].values[:window_size * 2]

    # 构建环形缓冲区
    from collections import deque
    buffer = deque(maxlen=window_size * 2)
    for row in data:
        buffer.append(tuple(row))

    # 环形缓冲区窗口
    buf_list = list(buffer)
    buf_window = np.array(buf_list[-window_size:])

    # Slice窗口
    slice_window = data[-window_size:]

    # 对比
    diff = np.abs(buf_window - slice_window).max()
    equivalent = diff < 1e-10

    return {
        'equivalent': equivalent,
        'max_diff': float(diff),
        'window_size': window_size,
        'buffer_depth': len(buffer),
    }


def print_report(report: ConsistencyReport) -> None:
    """打印一致性验证报告"""
    print("=" * 60)
    print("  流式 vs 离线 一致性验证报告")
    print("=" * 60)
    print(f"  总帧数:         {report.total_frames}")
    print(f"  流式事件数:     {report.stream_count}")
    print(f"  离线事件数:     {report.batch_count}")
    print(f"  数量匹配:       {'PASS' if report.count_match else 'FAIL'}")
    print(f"  类型不匹配:     {report.type_mismatches}")
    if report.type_mismatch_details:
        for d in report.type_mismatch_details[:5]:
            print(f"    [{d['index']}] stream={d['stream']} vs batch={d['batch']}")
    print(f"  最大置信度偏差: {report.max_conf_diff}")
    print(f"  平均置信度偏差: {report.mean_conf_diff}")
    print(f"  处理时间:       {report.processing_time_s}s")
    print(f"  {'─' * 40}")
    if report.consistent:
        print(f"  结果: ✅ 流式 vs 离线 完全一致")
    else:
        print(f"  结果: ❌ 发现不一致")
        if report.type_mismatches > 0:
            print(f"        类型不匹配: {report.type_mismatches} 处")
        if report.max_conf_diff > 1e-6:
            print(f"        置信度偏差: {report.max_conf_diff}")
    print("=" * 60)


# ── 命令行入口 ──
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="流式vs离线一致性验证")
    parser.add_argument("--csv", type=str, required=True, help="CSV数据文件路径")
    parser.add_argument("--fs", type=float, default=100.0, help="采样率")
    parser.add_argument("--n-frames", type=int, default=5000, help="测试帧数")
    parser.add_argument("--window-size", type=int, default=500, help="窗口大小")
    parser.add_argument("--step-size", type=int, default=50, help="步长")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="置信度容许偏差")

    args = parser.parse_args()

    report = verify_streaming_vs_batch(
        data_path=args.csv,
        fs=args.fs,
        n_frames=args.n_frames,
        window_size=args.window_size,
        step_size=args.step_size,
        tolerance_confidence=args.tolerance,
    )

    print_report(report)
    sys.exit(0 if report.consistent else 1)