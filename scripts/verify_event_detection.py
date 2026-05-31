#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端验证：系统事件检测管线 vs 专家参考事件

用法: python scripts/verify_event_detection.py [parsed_csv_path]
默认: data_output/parsed_data_20260524_105438.csv
"""

import csv
import sys
import os
from collections import Counter

# 设置路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'core'))

from core.analysis.data_bridge import DataBridge
from core.analysis.event_distributor import EventDistributor


def load_expert_events(csv_path: str) -> list:
    """加载专家参考事件"""
    events = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            events.append({
                'event_type': row['event_type'],
                'event_name': row['event_name'],
                't_start': float(row['t_start']),
                't_end': float(row['t_end']),
                'duration_s': float(row['duration_s']),
                'confidence': float(row['confidence']),
            })
    return events


def load_parsed_csv(csv_path: str) -> list:
    """加载 parsed CSV，格式化为 pipeline 兼容的记录"""
    records = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            rec = {
                'rel_time': float(row['rel_time']),
                'timestamp': float(row['rel_time']),
                'channel': row.get('channel', 'ch1'),
                'imu_name': row.get('imu_name', ''),
                'speed': float(row.get('speed', 0)),
                'wheel': float(row.get('wheel', 0)),
                'Ax_m_s2': float(row.get('Ax_m_s2', 0)),
                'Ay_m_s2': float(row.get('Ay_m_s2', 0)),
                'Az_m_s2': float(row.get('Az_m_s2', 0)),
                'Gx_rad_s': float(row.get('Gx_rad_s', 0)),
                'Gy_rad_s': float(row.get('Gy_rad_s', 0)),
                'Gz_rad_s': float(row.get('Gz_rad_s', 0)),
                # 兼容字段
                'ax': float(row.get('Ax_m_s2', 0)),
                'ay': float(row.get('Ay_m_s2', 0)),
                'az': float(row.get('Az_m_s2', 0)),
                'gx': float(row.get('Gx_rad_s', 0)),
                'gy': float(row.get('Gy_rad_s', 0)),
                'gz': float(row.get('Gz_rad_s', 0)),
            }
            records.append(rec)
    return records


def compare_events(system_events: list, expert_events: list, tolerance_s: float = 0.5):
    """对比系统检测事件与专家参考事件"""
    print("\n" + "=" * 80)
    print(f"{'事件类型':<20} {'专家时间窗':<20} {'系统时间窗':<20} {'匹配':<6}")
    print("=" * 80)

    matched_types = []
    unmatched_expert = list(expert_events)
    unmatched_system = list(system_events)

    for sys_ev in system_events:
        ev_type = sys_ev.get('event_type', sys_ev.get('type', '?'))
        t0 = sys_ev.get('t_start', sys_ev.get('start_time', 0))
        t1 = sys_ev.get('t_end', sys_ev.get('end_time', 0))
        dur = sys_ev.get('duration_s', sys_ev.get('duration', 0))

        best_match = None
        best_overlap = 0
        for exp_ev in expert_events:
            if exp_ev['event_type'] != ev_type:
                continue
            overlap = min(t1, exp_ev['t_end']) - max(t0, exp_ev['t_start'])
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = exp_ev

        if best_match and best_overlap > 0:
            matched_types.append(ev_type)
            if best_match in unmatched_expert:
                unmatched_expert.remove(best_match)
            if sys_ev in unmatched_system:
                unmatched_system.remove(sys_ev)
            print(f"{ev_type:<20} [{best_match['t_start']:.2f}-{best_match['t_end']:.2f}]s  "
                  f"[{t0:.2f}-{t1:.2f}]s  {'✓':<6}")
        else:
            print(f"{ev_type:<20} {'---':<20} [{t0:.2f}-{t1:.2f}]s  {'NEW':<6}")

    print("-" * 80)
    for exp_ev in unmatched_expert:
        print(f"{exp_ev['event_type']:<20} [{exp_ev['t_start']:.2f}-{exp_ev['t_end']:.2f}]s  "
              f"{'---':<20} {'MISS':<6}")

    return matched_types, unmatched_expert, unmatched_system


def main():
    # 文件路径
    default_csv = os.path.join(PROJECT_ROOT, 'data_output', 'parsed_data_20260524_105438.csv')
    csv_path = sys.argv[1] if len(sys.argv) > 1 else default_csv
    expert_path = os.path.join(PROJECT_ROOT, 'test_data', '验证数据', 'events_0524.csv')

    if not os.path.exists(csv_path):
        print(f"错误: 解析数据文件不存在: {csv_path}")
        sys.exit(1)

    print(f"解析数据: {csv_path}")
    print(f"专家参考: {expert_path}")

    # 加载数据
    records = load_parsed_csv(csv_path)
    expert_events = load_expert_events(expert_path)

    print(f"\n加载了 {len(records)} 条记录 (channels: {set(r['channel'] for r in records)})")
    print(f"专家参考: {len(expert_events)} 个事件, {len(set(e['event_type'] for e in expert_events))} 种类型")

    # ── 运行系统管线 ──
    db = DataBridge()
    print(f"\n运行 analyze_behavior_batch (ref_channel='ch1', ref_imu='IMU1_头部眉心-1')...")

    result = db.analyze_behavior_batch(
        records,
        ref_channel='ch1',
        ref_imu='IMU1_头部眉心-1',
    )

    system_events = result['events']
    summary = result['summary']
    accel_range = result['vehicle_accel_range']

    print(f"\n系统检测: {len(system_events)} 个事件, {len(summary['by_type'])} 种类型")
    print(f"\n车辆加速度范围: [{accel_range[0]:.2f}, {accel_range[1]:.2f}] m/s2")
    print(f"\n按类型分布:")
    for etype, info in sorted(summary['by_type'].items(), key=lambda x: -x[1].get('count', 1)):
        print(f"  {etype}: {info.get('count', '?')}")

    # ── 对比 ──
    matched, unmatched_exp, unmatched_sys = compare_events(system_events, expert_events)

    exp_types = Counter(e['event_type'] for e in expert_events)
    sys_types = Counter(e.get('event_type', e.get('type', '?')) for e in system_events)

    print(f"\n{'='*80}")
    print(f"总结:")
    print(f"  系统检测: {len(system_events)} 事件 ({len(summary['by_type'])} 类型)")
    print(f"  专家参考: {len(expert_events)} 事件 ({len(exp_types)} 类型)")
    print(f"  匹配率:   {len(matched)}/{len(expert_events)} 类型匹配")
    print(f"  漏检:     {len(unmatched_exp)} 个专家事件")
    print(f"  新增检测: {len(unmatched_sys)} 个系统事件")

    if unmatched_exp:
        print(f"\n  漏检事件类型: {[e['event_type'] for e in unmatched_exp]}")

    # ── 按类型对比 ──
    print(f"\n{'='*80}")
    print(f"按事件类型数量对比:")
    print(f"{'类型':<25} {'专家':<8} {'系统':<8} {'差异':<8}")
    print("-" * 80)
    all_types = sorted(set(list(exp_types.keys()) + list(sys_types.keys())))
    for t in all_types:
        exp_c = exp_types.get(t, 0)
        sys_c = sys_types.get(t, 0)
        diff = sys_c - exp_c
        flag = ' ✓' if diff == 0 else f' {diff:+d}'
        print(f"{t:<25} {exp_c:<8} {sys_c:<8} {flag:<8}")


if __name__ == '__main__':
    main()