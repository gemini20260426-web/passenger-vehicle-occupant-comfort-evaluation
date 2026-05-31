#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整数据流测试：CAN解析 → 归一化 → 分析管道 → 行为事件关联
数据源: 徐宁数据/2026_05_08_095939_ID0001.txt (行车)
标定:   徐宁数据/2026_05_07_180932_ID0001.txt (驻车)
"""

import sys
import os
import time
import json
import logging
from collections import deque
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('test_flow')

DATA_DIR = r'd:\UI重构_全量备份_20250824_233403\徐宁数据'
PARK_FILE = os.path.join(DATA_DIR, '2026_05_07_180932_ID0001.txt')
DRIVE_FILE = os.path.join(DATA_DIR, '2026_05_08_095939_ID0001.txt')

MAX_TEST_RECORDS = 5000

def test_can_parser():
    """测试1: CAN解析器"""
    logger.info("=" * 60)
    logger.info("测试1: CAN解析器 - 解析行车数据")
    logger.info("=" * 60)

    from core.data_processing.can_parser_v2 import CANFullParser

    parser = CANFullParser(park_file_path=PARK_FILE)
    logger.info(f"标定文件: {PARK_FILE}")
    logger.info(f"数据文件: {DRIVE_FILE}")

    configs = parser.calibrate()
    logger.info(f"标定完成, 通道数: {len(configs)}")
    for ch, cfg in configs.items():
        logger.info(f"  通道 {ch}: CAN IDs={cfg['active_can_ids']}, 字段数={len(cfg['field_types'])}")

    records = []
    for i, record in enumerate(parser.parse_file(DRIVE_FILE)):
        records.append(record)
        if i < 3:
            logger.info(f"  记录#{i}: timestamp={record.get('timestamp', 'N/A')}, "
                       f"speed={record.get('speed', 'N/A')}, "
                       f"steering={record.get('steering', 'N/A')}")
            imu_keys = [k for k in record if k.startswith('ch') and ('_ax' in k or '_gx' in k)]
            logger.info(f"    IMU字段: {sorted(imu_keys)[:12]}...")
        if len(records) >= MAX_TEST_RECORDS:
            break

    logger.info(f"解析完成: 成功={parser.success_count}, 错误={parser.error_count}, 测试记录数={len(records)}")

    if records:
        r0 = records[0]
        is_wide = any(k.startswith('ch') and '_ax' in k for k in r0)
        logger.info(f"格式类型: {'宽格式 (wide)' if is_wide else '其他'}")
        imu_fields = [k for k in r0 if k.startswith('ch') and '_' in k]
        logger.info(f"IMU字段总数: {len(imu_fields)}")
        vehicle_fields = [k for k in r0 if k in ('speed', 'steering', 'reverse', 'emergency_brake', 'brake_pressure')]
        logger.info(f"车辆信号字段: {vehicle_fields}")

    return records


def test_normalization(records):
    """测试2: 归一化 - DataBridge._normalize_can_record"""
    logger.info("=" * 60)
    logger.info("测试2: 归一化 - 宽格式→IMU管道格式")
    logger.info("=" * 60)

    from core.analysis.data_bridge import DataBridge

    normalized_count = 0
    imu_count = 0
    samples = []

    for record in records[:MAX_TEST_RECORDS]:
        is_wide = DataBridge._is_can_wide_format(record)
        is_long = DataBridge._is_can_long_format(record)

        if is_wide or is_long:
            normalized = DataBridge._normalize_can_record(dict(record))
            normalized_count += 1

            is_imu = any(k in normalized for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz'))
            if is_imu:
                imu_count += 1
                if len(samples) < 5:
                    samples.append(normalized)

    logger.info(f"宽格式记录数: {normalized_count}")
    logger.info(f"归一化后IMU记录数: {imu_count}")
    logger.info(f"归一化成功率: {imu_count/max(normalized_count,1)*100:.1f}%")

    for i, s in enumerate(samples):
        logger.info(f"  样本#{i}: timestamp={s.get('timestamp', 'N/A')}, "
                   f"ax={s.get('ax', 0):.4f}, ay={s.get('ay', 0):.4f}, az={s.get('az', 0):.4f}, "
                   f"gx={s.get('gx', 0):.4f}, gy={s.get('gy', 0):.4f}, gz={s.get('gz', 0):.4f}, "
                   f"speed={s.get('speed', 0)}, wheel={s.get('wheel', 0)}")

    return normalized_count > 0 and imu_count > 0


def test_analysis_pipeline(records):
    """测试3: 分析管道 - AnalysisPipeline.process_frame"""
    logger.info("=" * 60)
    logger.info("测试3: 五层分析管道 - process_frame")
    logger.info("=" * 60)

    from core.analysis.data_bridge import DataBridge
    from core.analysis.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline()
    logger.info("AnalysisPipeline 初始化完成")

    frame_count = 0
    event_count = 0
    state_counts = {}
    events = []

    for record in records[:MAX_TEST_RECORDS]:
        if not DataBridge._is_can_wide_format(record):
            continue

        normalized = DataBridge._normalize_can_record(dict(record))
        if not any(k in normalized for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
            continue

        try:
            result = pipeline.process_frame(normalized)
            frame_count += 1

            state_name = str(result.state) if result.state else 'None'
            state_counts[state_name] = state_counts.get(state_name, 0) + 1

            if result.event:
                event_count += 1
                if len(events) < 5:
                    events.append({
                        'frame': frame_count,
                        'timestamp': result.timestamp,
                        'state': state_name,
                        'event_type': str(result.event.event_type) if hasattr(result.event, 'event_type') else 'N/A',
                        'has_can_context': hasattr(result, 'can_context') and result.can_context is not None,
                    })
        except Exception as e:
            logger.debug(f"帧处理异常: {e}")

    logger.info(f"处理帧数: {frame_count}")
    logger.info(f"检测事件数: {event_count}")
    logger.info(f"状态分布: {state_counts}")

    for e in events:
        logger.info(f"  事件: frame={e['frame']}, ts={e['timestamp']:.3f}, "
                   f"state={e['state']}, type={e['event_type']}, "
                   f"can_context={e['has_can_context']}")

    return frame_count > 0


def test_data_bridge_integration(records):
    """测试4: DataBridge集成 - feed_parsed_data + 事件关联"""
    logger.info("=" * 60)
    logger.info("测试4: DataBridge集成 - 双路分流 + 事件关联")
    logger.info("=" * 60)

    from core.analysis.data_bridge import DataBridge

    bridge = DataBridge()
    logger.info("DataBridge 初始化完成")

    sensor_count = 0
    batch_count = 0
    frame_results = []

    def on_sensor(data):
        nonlocal sensor_count
        sensor_count += 1

    def on_batch(batch):
        nonlocal batch_count
        batch_count += 1

    def on_frame_result(result):
        frame_results.append(result)

    bridge.sensor_data_received.connect(on_sensor)
    bridge.sensor_data_batch_received.connect(on_batch)
    bridge.frame_result_ready.connect(on_frame_result)

    bridge.start_processing()

    for i, record in enumerate(records[:MAX_TEST_RECORDS]):
        bridge.feed_parsed_data(record)

    import time as _time
    _time.sleep(0.5)

    bridge.stop_processing()

    logger.info(f"传感器信号数: {sensor_count}")
    logger.info(f"批量信号数: {batch_count}")
    logger.info(f"帧结果数: {len(frame_results)}")

    events_with_context = 0
    for fr in frame_results:
        if fr.event and hasattr(fr, 'can_context') and fr.can_context:
            events_with_context += 1

    logger.info(f"带CAN上下文的事件数: {events_with_context}")

    recent_can_size = len(bridge._recent_can_records)
    logger.info(f"缓存CAN记录数: {recent_can_size}")

    if recent_can_size > 0:
        sample_can = bridge._recent_can_records[0]
        logger.info(f"缓存CAN样本字段: {list(sample_can.keys())[:10]}...")

    return recent_can_size > 0


def test_can_context_detail(records):
    """测试5: CAN上下文详情 - 事件关联的CAN数据内容"""
    logger.info("=" * 60)
    logger.info("测试5: CAN上下文详情验证")
    logger.info("=" * 60)

    from core.analysis.data_bridge import DataBridge

    bridge = DataBridge()
    frame_results = []

    def on_frame_result(result):
        frame_results.append(result)

    bridge.frame_result_ready.connect(on_frame_result)
    bridge.start_processing()

    for record in records[:MAX_TEST_RECORDS]:
        bridge.feed_parsed_data(record)

    import time as _time
    _time.sleep(0.5)
    bridge.stop_processing()

    events_with_can = [fr for fr in frame_results if fr.event and hasattr(fr, 'can_context') and fr.can_context]

    if events_with_can:
        first_event = events_with_can[0]
        logger.info(f"首个关联事件: timestamp={first_event.timestamp:.3f}, "
                   f"state={first_event.state}")
        logger.info(f"关联CAN记录数: {len(first_event.can_context)}")

        for i, can_rec in enumerate(first_event.can_context[:3]):
            keys = list(can_rec.keys())
            logger.info(f"  CAN记录#{i}: keys={keys[:8]}...")
            if 'speed' in can_rec:
                logger.info(f"    speed={can_rec.get('speed')}, steering={can_rec.get('steering')}")
            if 'ch4_ax' in can_rec:
                logger.info(f"    ch4_ax={can_rec.get('ch4_ax', 0):.4f}, ch4_ay={can_rec.get('ch4_ay', 0):.4f}")
    else:
        logger.info("未检测到带CAN上下文的事件（数据量可能不足以触发行为事件）")

    recent_can_size = len(bridge._recent_can_records)
    logger.info(f"缓存CAN记录数: {recent_can_size}")
    if recent_can_size > 0:
        sample = bridge._recent_can_records[0]
        logger.info(f"缓存CAN样本: speed={sample.get('speed')}, steering={sample.get('steering')}, "
                   f"ch4_ax={sample.get('ch4_ax', 0):.4f}")

    return recent_can_size > 0


def main():
    logger.info("=" * 60)
    logger.info("完整数据流测试开始")
    logger.info(f"数据文件: {DRIVE_FILE}")
    logger.info(f"标定文件: {PARK_FILE}")
    logger.info(f"测试记录数上限: {MAX_TEST_RECORDS}")
    logger.info("=" * 60)

    results = {}

    try:
        records = test_can_parser()
        results['parser'] = len(records) > 0
    except Exception as e:
        logger.error(f"测试1失败: {e}", exc_info=True)
        results['parser'] = False
        records = []

    if records:
        try:
            results['normalization'] = test_normalization(records)
        except Exception as e:
            logger.error(f"测试2失败: {e}", exc_info=True)
            results['normalization'] = False

        try:
            results['pipeline'] = test_analysis_pipeline(records)
        except Exception as e:
            logger.error(f"测试3失败: {e}", exc_info=True)
            results['pipeline'] = False

        try:
            results['bridge'] = test_data_bridge_integration(records)
        except Exception as e:
            logger.error(f"测试4失败: {e}", exc_info=True)
            results['bridge'] = False

        try:
            results['context'] = test_can_context_detail(records)
        except Exception as e:
            logger.error(f"测试5失败: {e}", exc_info=True)
            results['context'] = False

    logger.info("=" * 60)
    logger.info("测试结果汇总:")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"  {name}: {status}")
    logger.info("=" * 60)

    all_pass = all(results.values())
    logger.info(f"总体结果: {'全部通过' if all_pass else '存在失败项'}")
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())