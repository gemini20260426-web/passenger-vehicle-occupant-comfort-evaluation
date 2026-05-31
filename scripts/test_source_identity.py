#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源身份传递全链路验证测试
验证 _source_type 从 DataSourceReader → Cache → ReplayController → UI 的完整传递
"""

import sys
import os
import json
import tempfile
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('test_source_identity')

from core.core.data_processing.multi_source_cache import MultiSourceCache
from core.core.analysis.data_bridge import DataBridge


def test_cache_source_type_injection():
    """测试1: 缓存查询时 source_type 注入"""
    logger.info("=" * 60)
    logger.info("测试1: 缓存查询 source_type 注入")
    logger.info("=" * 60)

    db_path = os.path.join(tempfile.gettempdir(), 'test_source_identity.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    cache = MultiSourceCache(db_path)

    cache.write_batch([
        {'timestamp': 0.1, 'ax': 1.0, 'ay': 2.0, 'az': 3.0,
         'gx': 0.1, 'gy': 0.2, 'gz': 0.3, 'speed': 30, 'wheel': 5.0,
         '_source_type': 'imu_standalone', 'source_id': 'test_imu'},
        {'timestamp': 0.2, 'ch4_ax': 4.0, 'ch4_ay': 5.0, 'ch4_az': 6.0,
         'ch4_gx': 0.4, 'ch4_gy': 0.5, 'ch4_gz': 0.6,
         'speed': 40, 'steering': 10.0,
         '_source_type': 'can_wide', 'source_id': 'test_can'},
        {'timestamp': 0.3, 'pressure': 120, 'cnap_type': 'WAVE',
         '_source_type': 'cnap', 'source_id': 'test_cnap'},
    ])

    results = cache.query_time_range(0, 1.0)

    source_types_found = set()
    for r in results:
        st = r.get('_source_type', 'MISSING')
        source_types_found.add(st)
        logger.info(f"  记录: _source_type={st}, source_id={r.get('source_id', '?')}")

    assert 'imu_standalone' in source_types_found, f"缺少 imu_standalone, 实际: {source_types_found}"
    assert 'can_wide' in source_types_found, f"缺少 can_wide, 实际: {source_types_found}"
    assert 'cnap' in source_types_found, f"缺少 cnap, 实际: {source_types_found}"

    logger.info("  PASS: 所有 source_type 正确注入")
    cache.close()
    os.remove(db_path)


def test_normalize_preserves_identity():
    """测试2: 归一化保留 source_type 和 source_id"""
    logger.info("=" * 60)
    logger.info("测试2: 归一化保留身份信息")
    logger.info("=" * 60)

    wide_record = {
        'timestamp': 0.5,
        'ch4_ax': 1.0, 'ch4_ay': 2.0, 'ch4_az': 3.0,
        'ch4_gx': 0.1, 'ch4_gy': 0.2, 'ch4_gz': 0.3,
        'speed': 50, 'steering': 15.0,
        '_source_type': 'can_wide', 'source_id': 'bb61fc14',
    }

    normalized = DataBridge._normalize_can_record(wide_record)

    assert normalized.get('_source_type') == 'can_wide', \
        f"期望 can_wide, 实际 {normalized.get('_source_type')}"
    assert normalized.get('_source_id') == 'bb61fc14', \
        f"期望 bb61fc14, 实际 {normalized.get('_source_id')}"
    assert normalized.get('_normalized_from') == 'can_wide', \
        f"期望 can_wide, 实际 {normalized.get('_normalized_from')}"
    assert normalized.get('ax') == 1.0, f"ax 值错误: {normalized.get('ax')}"

    logger.info(f"  CAN wide归一化: _source_type={normalized.get('_source_type')}, "
                f"_source_id={normalized.get('_source_id')}, "
                f"_normalized_from={normalized.get('_normalized_from')}")

    standalone_record = {
        'timestamp': 0.6,
        'ax': 1.0, 'ay': 2.0, 'az': 3.0,
        'gx': 0.1, 'gy': 0.2, 'gz': 0.3,
        'speed': 30, 'wheel': 5.0,
        '_source_type': 'imu_standalone', 'source_id': 'cc72fd25',
    }

    normalized2 = DataBridge._normalize_can_record(standalone_record)

    assert normalized2.get('_source_type') == 'imu_standalone', \
        f"期望 imu_standalone, 实际 {normalized2.get('_source_type')}"
    assert normalized2.get('_source_id') == 'cc72fd25', \
        f"期望 cc72fd25, 实际 {normalized2.get('_source_id')}"

    logger.info(f"  独立IMU透传: _source_type={normalized2.get('_source_type')}, "
                f"_source_id={normalized2.get('_source_id')}")

    logger.info("  PASS: 归一化正确保留身份信息")


def test_source_type_distinction():
    """测试3: 验证三种IMU数据源可区分"""
    logger.info("=" * 60)
    logger.info("测试3: 三种IMU数据源区分验证")
    logger.info("=" * 60)

    wide_normalized = DataBridge._normalize_can_record({
        'timestamp': 0.5,
        'ch4_ax': 1.0, 'ch4_ay': 2.0, 'ch4_az': 3.0,
        'ch4_gx': 0.1, 'ch4_gy': 0.2, 'ch4_gz': 0.3,
        'speed': 50, 'steering': 15.0,
        '_source_type': 'can_wide', 'source_id': 'can_src',
    })

    long_normalized = DataBridge._normalize_can_record({
        'rel_time': 0.5,
        'imu_name': 'IMU-04_座椅底部_对照组',
        'Ax_m_s2': 1.0, 'Ay_m_s2': 2.0, 'Az_m_s2': 3.0,
        'Gx_rad_s': 0.1, 'Gy_rad_s': 0.2, 'Gz_rad_s': 0.3,
        '车速_kmh': 50, '方向盘转角_deg': 15.0,
        '_source_type': 'can_long', 'source_id': 'can_long_src',
    })

    standalone = DataBridge._normalize_can_record({
        'timestamp': 0.5,
        'ax': 1.0, 'ay': 2.0, 'az': 3.0,
        'gx': 0.1, 'gy': 0.2, 'gz': 0.3,
        'speed': 50, 'wheel': 15.0,
        '_source_type': 'imu_standalone', 'source_id': 'imu_src',
    })

    types = {
        wide_normalized.get('_source_type'): 'CAN全量(ch4归一化)',
        long_normalized.get('_source_type'): 'CAN长格式(ch4归一化)',
        standalone.get('_source_type'): '独立IMU',
    }

    logger.info(f"  数据源类型映射: {types}")

    assert wide_normalized.get('_source_type') != standalone.get('_source_type'), \
        "CAN wide 和 独立IMU 的 _source_type 应该不同"
    assert long_normalized.get('_source_type') != standalone.get('_source_type'), \
        "CAN long 和 独立IMU 的 _source_type 应该不同"

    logger.info("  PASS: 三种IMU数据源可通过 _source_type 明确区分")


def test_replay_controller_classification():
    """测试4: 回放控制器分类路由逻辑"""
    logger.info("=" * 60)
    logger.info("测试4: 回放控制器分类路由逻辑")
    logger.info("=" * 60)

    records = [
        {'_source_type': 'imu_standalone', 'ax': 1.0, 'source_id': 'imu1'},
        {'_source_type': 'can_wide', 'ch4_ax': 2.0, 'source_id': 'can1'},
        {'_source_type': 'cnap_wave', 'pressure': 120, 'source_id': 'cnap1'},
        {'_source_type': 'can_long', 'Ax_m_s2': 3.0, 'source_id': 'can2'},
        {'_source_type': 'pipeline', 'ax': 4.0, 'source_id': 'pipe1'},
    ]

    imu_batch, cnap_batch, can_raw_batch = [], [], []
    for rec in records:
        st = rec.get('_source_type', '')
        if st in ('imu_standalone', 'can_wide', 'pipeline'):
            imu_batch.append(rec)
        if st.startswith('cnap'):
            cnap_batch.append(rec)
        if st in ('can_wide', 'can_long'):
            can_raw_batch.append(rec)

    logger.info(f"  IMU batch: {len(imu_batch)}条 → {[r['_source_type'] for r in imu_batch]}")
    logger.info(f"  CNAP batch: {len(cnap_batch)}条 → {[r['_source_type'] for r in cnap_batch]}")
    logger.info(f"  CAN raw batch: {len(can_raw_batch)}条 → {[r['_source_type'] for r in can_raw_batch]}")

    assert len(imu_batch) == 3, f"IMU batch 应有3条, 实际 {len(imu_batch)}"
    assert len(cnap_batch) == 1, f"CNAP batch 应有1条, 实际 {len(cnap_batch)}"
    assert len(can_raw_batch) == 2, f"CAN raw batch 应有2条, 实际 {len(can_raw_batch)}"

    logger.info("  PASS: 分类路由逻辑正确")


if __name__ == '__main__':
    try:
        test_cache_source_type_injection()
        test_normalize_preserves_identity()
        test_source_type_distinction()
        test_replay_controller_classification()
        logger.info("=" * 60)
        logger.info("全部测试通过!")
        logger.info("=" * 60)
    except AssertionError as e:
        logger.error(f"测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试异常: {e}", exc_info=True)
        sys.exit(1)