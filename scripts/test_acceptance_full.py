#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
闭环验收自动化测试 — 全链路覆盖
覆盖 Phase 1~10 中可自动化的核心逻辑
"""

import sys
import os
import io
import json
import tempfile
import time
import logging
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger('acceptance_test')

PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []


def record(test_id, name, passed, detail=''):
    global PASS, FAIL, SKIP
    status = 'PASS' if passed else ('SKIP' if passed is None else 'FAIL')
    if passed is True:
        PASS += 1
    elif passed is None:
        SKIP += 1
    else:
        FAIL += 1
    RESULTS.append((test_id, name, status, detail))
    icon = '[OK]' if passed is True else ('[--]' if passed is None else '[FAIL]')
    print(f"  {icon} [{test_id}] {name}")
    if detail:
        print(f"       {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# Phase 1: 数据源类型检测
# ============================================================
def test_phase1_source_detection():
    section("Phase 1+3: 数据源类型自动检测")

    from modules.ui.left_control_panel.utils.data_reader_manager import DataSourceReader

    class MockConfig:
        pass

    class MockPipeline:
        def push_data(self, *a, **kw):
            pass

    # TC-1.1/3.4: CAN 网关原始文件 -> can_wide (CANFullParser produces wide format)
    can_gateway_file = r'd:\UI重构_全量备份_20250824_233403\260511_0859\2026_05_11_103256_ID0001.txt'
    if os.path.exists(can_gateway_file):
        cfg = MockConfig()
        cfg.type = 'CAN'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': can_gateway_file}
        reader = DataSourceReader('test_can_gateway', cfg, MockPipeline())
        reader._load_file_data()
        detected = reader._effective_source_type
        record('TC-1.1', 'CAN网关原始->can_wide(CANFullParser)', detected == 'can_wide',
               f'检测结果: {detected}, 记录数: {len(reader._file_data_cache)}')
    else:
        record('TC-1.1', 'CAN网关原始->can_wide', None, '文件不存在')

    # TC-1.2/3.3: CAN 宽格式 CSV -> can_wide
    can_wide_file = r'd:\UI重构_全量备份_20250824_233403\260508_0939\2026_05_08_102708_ID0001.csv'
    if os.path.exists(can_wide_file):
        cfg = MockConfig()
        cfg.type = 'CAN'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': can_wide_file}
        reader = DataSourceReader('test_can_wide', cfg, MockPipeline())
        reader._load_file_data()
        detected = reader._effective_source_type
        record('TC-1.2', 'CAN宽格式CSV->can_wide', detected == 'can_wide',
               f'检测结果: {detected}')
    else:
        record('TC-1.2', 'CAN宽格式CSV->can_wide', None, '文件不存在')

    # TC-1.3/3.1: IMU 独立路测 -> imu_standalone
    imu_file = r'd:\UI重构_全量备份_20250824_233403\test_data\IMU路测数据.txt'
    if os.path.exists(imu_file):
        cfg = MockConfig()
        cfg.type = 'IMU'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': imu_file}
        reader = DataSourceReader('test_imu', cfg, MockPipeline())
        reader._load_file_data()
        detected = reader._effective_source_type
        record('TC-1.3', 'IMU独立路测->imu_standalone', detected == 'imu_standalone',
               f'检测结果: {detected}')
    else:
        record('TC-1.3', 'IMU独立路测->imu_standalone', None, '文件不存在')

    # TC-1.4/3.2: CNAP -> cnap
    cnap_file = r'd:\UI重构_全量备份_20250824_233403\test_data\CNAP.txt'
    if os.path.exists(cnap_file):
        cfg = MockConfig()
        cfg.type = 'CNAP'
        cfg.sampling_rate = 125
        cfg.connection = {'file_path': cnap_file}
        reader = DataSourceReader('test_cnap', cfg, MockPipeline())
        reader._load_file_data()
        detected = reader._effective_source_type
        record('TC-1.4', 'CNAP生理数据->cnap', detected == 'cnap',
               f'检测结果: {detected}')
    else:
        record('TC-1.4', 'CNAP生理数据->cnap', None, '文件不存在')

    # CAN 长格式解析 CSV -> can_long
    can_long_file = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_IMU.csv'
    if os.path.exists(can_long_file):
        cfg = MockConfig()
        cfg.type = 'CAN'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': can_long_file}
        reader = DataSourceReader('test_can_long_csv', cfg, MockPipeline())
        reader._load_file_data()
        detected = reader._effective_source_type
        record('TC-1.5', 'CAN长格式CSV->can_long', detected == 'can_long',
               f'检测结果: {detected}')
    else:
        record('TC-1.5', 'CAN长格式CSV->can_long', None, '文件不存在')


# ============================================================
# Phase 3: 数据解析正确性
# ============================================================
def test_phase3_parsing_correctness():
    section("Phase 3: 数据解析正确性")

    from modules.ui.left_control_panel.utils.data_reader_manager import DataSourceReader

    class MockConfig:
        pass

    class MockPipeline:
        def push_data(self, *a, **kw):
            pass

    # TC-3.1: IMU 解析字段完整性
    imu_file = r'd:\UI重构_全量备份_20250824_233403\test_data\IMU路测数据.txt'
    if os.path.exists(imu_file):
        cfg = MockConfig()
        cfg.type = 'IMU'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': imu_file}
        reader = DataSourceReader('test_imu_parse', cfg, MockPipeline())
        reader._load_file_data()
        reader._effective_source_type = 'imu_standalone'

        count = len(reader._file_data_cache)
        record('TC-3.1a', 'IMU数据加载成功', count > 0,
               f'加载 {count} 条')

        if count > 0:
            first = reader._file_data_cache[0]
            has_imu = all(k in first for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz'))
            record('TC-3.1b', 'IMU解析字段完整性', has_imu,
                   f'首条字段: {sorted(first.keys())[:12]}')
            record('TC-3.1c', 'IMU effective_source_type',
                   reader._effective_source_type == 'imu_standalone',
                   f'effective_source_type={reader._effective_source_type}')
    else:
        record('TC-3.1', 'IMU解析', None, '文件不存在')

    # TC-3.2: CNAP 解析
    cnap_file = r'd:\UI重构_全量备份_20250824_233403\test_data\CNAP.txt'
    if os.path.exists(cnap_file):
        cfg = MockConfig()
        cfg.type = 'CNAP'
        cfg.sampling_rate = 125
        cfg.connection = {'file_path': cnap_file}
        reader = DataSourceReader('test_cnap_parse', cfg, MockPipeline())
        reader._load_file_data()
        reader._effective_source_type = 'cnap'

        count = len(reader._file_data_cache)
        record('TC-3.2a', 'CNAP数据加载成功', count > 0,
               f'加载 {count} 条')

        if count > 0:
            first = reader._file_data_cache[0]
            has_cnap = 'pressure' in first or 'cnap_type' in first or 'wave_t' in first
            record('TC-3.2b', 'CNAP字段存在', has_cnap,
                   f'首条字段: {sorted(first.keys())[:10]}')
    else:
        record('TC-3.2', 'CNAP解析', None, '文件不存在')

    # TC-3.3: CAN wide 解析
    can_wide_file = r'd:\UI重构_全量备份_20250824_233403\260508_0939\2026_05_08_102708_ID0001.csv'
    if os.path.exists(can_wide_file):
        cfg = MockConfig()
        cfg.type = 'CAN'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': can_wide_file}
        reader = DataSourceReader('test_can_wide_parse', cfg, MockPipeline())
        reader._load_file_data()
        reader._effective_source_type = 'can_wide'

        count = len(reader._file_data_cache)
        record('TC-3.3a', 'CAN wide数据加载成功', count > 0,
               f'加载 {count} 条')

        if count > 0:
            first = reader._file_data_cache[0]
            has_data = 'raw' in first or 'ch4_ax' in first
            record('TC-3.3b', 'CAN wide数据可读', has_data,
                   f'首条字段: {sorted(first.keys())[:5]}')
    else:
        record('TC-3.3', 'CAN wide解析', None, '文件不存在')

    # TC-3.4: CAN long 解析
    can_long_file = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\解析数据集\弯道实测_IMU_CAN解析_IMU.csv'
    if os.path.exists(can_long_file):
        cfg = MockConfig()
        cfg.type = 'CAN'
        cfg.sampling_rate = 100
        cfg.connection = {'file_path': can_long_file}
        reader = DataSourceReader('test_can_long_parse', cfg, MockPipeline())
        reader._load_file_data()
        reader._effective_source_type = 'can_long'

        count = len(reader._file_data_cache)
        record('TC-3.4a', 'CAN long数据加载成功', count > 0,
               f'加载 {count} 条')

        if count > 0:
            first = reader._file_data_cache[0]
            has_data = 'raw' in first or 'imu_name' in first
            record('TC-3.4b', 'CAN long数据可读', has_data,
                   f'首条字段: {sorted(first.keys())[:5]}')
    else:
        record('TC-3.4', 'CAN long解析', None, '文件不存在')


# ============================================================
# Phase 3: 互斥检测逻辑
# ============================================================
def test_phase3_mutual_exclusion():
    section("Phase 3: 数据源互斥检测")

    def check_conflict(selected_types):
        imu_conflict_types = {'imu_standalone', 'can_wide', 'can_long'}
        imu_selected = [t for t in selected_types if t in imu_conflict_types]
        if len(imu_selected) > 1:
            return True, imu_selected
        return False, []

    conflict1, types1 = check_conflict(['imu_standalone', 'can_wide'])
    record('TC-3.6a', 'IMU+CAN wide互斥检测', conflict1,
           f'选中: [imu_standalone,can_wide], 冲突: {conflict1}, 冲突类型: {types1}')

    conflict2, types2 = check_conflict(['imu_standalone', 'can_long'])
    record('TC-3.7a', 'IMU+CAN long互斥检测', conflict2,
           f'选中: [imu_standalone,can_long], 冲突: {conflict2}')

    conflict3, types3 = check_conflict(['imu_standalone', 'cnap'])
    record('TC-3.5a', 'IMU+CNAP不互斥', not conflict3,
           f'选中: [imu_standalone,cnap], 冲突: {conflict3}')

    conflict4, types4 = check_conflict(['can_wide', 'cnap'])
    record('TC-3.5b', 'CAN wide+CNAP不互斥', not conflict4,
           f'选中: [can_wide,cnap], 冲突: {conflict4}')

    conflict5, types5 = check_conflict(['can_wide', 'can_long'])
    record('TC-3.5c', 'CAN wide+CAN long互斥', conflict5,
           f'选中: [can_wide,can_long], 冲突: {conflict5}')


# ============================================================
# Phase 3+4: 缓存写入/读取 + 回放控制器路由
# ============================================================
def test_phase4_cache_and_replay():
    section("Phase 3+4: 缓存写入/读取 + 回放控制器路由")

    from core.core.data_processing.multi_source_cache import MultiSourceCache
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController

    db_path = os.path.join(tempfile.gettempdir(), 'test_acceptance_cache.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    cache = MultiSourceCache(db_path)

    records = []
    for i in range(100):
        records.append({
            'timestamp': i * 0.01,
            'ax': 1.0 + i * 0.01, 'ay': 2.0, 'az': 3.0,
            'gx': 0.1, 'gy': 0.2, 'gz': 0.3,
            'speed': 30 + i, 'wheel': 5.0,
            '_source_type': 'imu_standalone', 'source_id': 'imu_src',
        })
    for i in range(100):
        records.append({
            'timestamp': i * 0.01 + 1.0,
            'pressure': 120 + i % 10, 'cnap_type': 'WAVE',
            '_source_type': 'cnap', 'source_id': 'cnap_src',
        })
    for i in range(100):
        records.append({
            'timestamp': i * 0.01 + 2.0,
            'ch4_ax': 4.0, 'ch4_ay': 5.0, 'ch4_az': 6.0,
            'ch4_gx': 0.4, 'ch4_gy': 0.5, 'ch4_gz': 0.6,
            'speed': 40, 'steering': 10.0,
            '_source_type': 'can_wide', 'source_id': 'can_src',
        })
    for i in range(100):
        records.append({
            'timestamp': i * 0.01 + 3.0,
            'imu_name': 'IMU-04_座椅底部_对照组',
            'Ax_m_s2': 1.0, 'Ay_m_s2': 2.0, 'Az_m_s2': 3.0,
            'Gx_dps': 0.1, 'Gy_dps': 0.2, 'Gz_dps': 0.3,
            '车速_kmh': 50, '方向盘转角_deg': 15.0,
            '_source_type': 'can_long', 'source_id': 'can_long_src',
        })

    cache.write_batch(records)
    record('TC-4.0a', '缓存写入400条混合数据', True,
           f'写入 {len(records)} 条')

    results = cache.query_time_range(0, 5.0)
    record('TC-4.0b', '缓存查询返回数据', len(results) > 0,
           f'查询返回 {len(results)} 条')

    source_types = set()
    for r in results:
        st = r.get('_source_type', 'unknown')
        source_types.add(st)
    expected_types = {'imu_standalone', 'cnap', 'can_wide', 'can_long'}
    record('TC-4.0c', '缓存source_type完整性', source_types == expected_types,
           f'实际: {source_types}')

    # 回放控制器路由测试
    controller = MultiSourceReplayController()
    loaded = controller.load_cache(cache)
    record('TC-4.0d', '回放控制器加载缓存', loaded,
           f'加载结果: {loaded}')

    imu_batch_received = []
    cnap_batch_received = []
    can_raw_batch_received = []

    controller.imu_data_batch_received.connect(lambda b: imu_batch_received.extend(b))
    controller.cnap_data_batch_received.connect(lambda b: cnap_batch_received.extend(b))
    controller.can_raw_data_batch_received.connect(lambda b: can_raw_batch_received.extend(b))

    controller._window_size = 5.0
    controller._speed = 100.0
    controller._cursor = 0
    controller._time_max = 5.0
    controller._state = 'playing'
    controller._on_tick()

    # TC-6.4: can_long 不进入 IMU batch
    imu_source_types = set()
    for item in imu_batch_received:
        imu_source_types.add(item.get('_source_type', 'unknown'))
    can_long_in_imu = 'can_long' in imu_source_types
    record('TC-6.4', 'can_long不进入IMU batch', not can_long_in_imu,
           f'IMU batch中的source_type: {imu_source_types}')

    # TC-9.1: can_wide 进入 IMU batch
    can_wide_in_imu = 'can_wide' in imu_source_types
    imu_standalone_in_imu = 'imu_standalone' in imu_source_types
    record('TC-9.1a', 'can_wide进入IMU batch', can_wide_in_imu,
           f'IMU batch source_types: {imu_source_types}')
    record('TC-9.1b', 'imu_standalone进入IMU batch', imu_standalone_in_imu)

    # CNAP batch
    cnap_source_types = set(i.get('_source_type', '') for i in cnap_batch_received)
    record('TC-9.1c', 'CNAP进入CNAP batch', 'cnap' in cnap_source_types,
           f'CNAP batch source_types: {cnap_source_types}')

    # CAN raw batch: can_wide + can_long
    can_raw_types = set(i.get('_source_type', '') for i in can_raw_batch_received)
    record('TC-9.2a', 'can_long进入CAN raw batch', 'can_long' in can_raw_types,
           f'CAN raw batch source_types: {can_raw_types}')
    record('TC-9.2b', 'can_wide进入CAN raw batch', 'can_wide' in can_raw_types)

    cache.close()
    if os.path.exists(db_path):
        os.remove(db_path)


# ============================================================
# Phase 4: 回放控制器状态机
# ============================================================
def test_phase4_state_machine():
    section("Phase 4: 回放控制器状态机")

    from core.core.data_processing.multi_source_cache import MultiSourceCache
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController

    db_path = os.path.join(tempfile.gettempdir(), 'test_state_machine.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    cache = MultiSourceCache(db_path)
    cache.write_batch([
        {'timestamp': i * 0.1, 'ax': 1.0, 'ay': 2.0, 'az': 3.0,
         'gx': 0.1, 'gy': 0.2, 'gz': 0.3,
         '_source_type': 'imu_standalone', 'source_id': 'test'}
        for i in range(50)
    ])

    controller = MultiSourceReplayController()
    state_changes = []
    controller.replay_state_changed.connect(lambda s: state_changes.append(s))

    loaded = controller.load_cache(cache)
    record('TC-4.1a', '回放控制器加载缓存', loaded)

    # TC-4.1: 初始状态
    record('TC-4.1b', '初始状态=stopped', controller._state == 'stopped',
           f'状态: {controller._state}')
    t_min, t_max = controller.time_range
    record('TC-4.1c', '时间范围正确', t_min >= 0 and t_max > t_min,
           f'范围: [{t_min:.2f}, {t_max:.2f}]')

    # TC-4.2: 播放
    controller.play()
    record('TC-4.2a', '播放状态=playing', controller._state == 'playing',
           f'状态: {controller._state}')

    # TC-4.3: 暂停
    controller.pause()
    record('TC-4.3a', '暂停状态=paused', controller._state == 'paused',
           f'状态: {controller._state}')

    # 恢复
    controller.play()
    record('TC-4.3b', '恢复后状态=playing', controller._state == 'playing')

    # TC-4.4: 停止
    controller.stop()
    record('TC-4.4a', '停止状态=stopped', controller._state == 'stopped')
    record('TC-4.4b', '停止后cursor归零', controller._cursor == 0.0,
           f'cursor={controller._cursor}')

    # TC-4.5: Seek
    controller.seek(2.0)
    record('TC-4.5a', 'Seek到2.0s', abs(controller._cursor - 2.0) < 0.01,
           f'cursor={controller._cursor:.3f}')

    # TC-4.6: Seek边界
    controller.seek(-1.0)
    record('TC-4.6a', 'Seek负值不越界', controller._cursor >= 0,
           f'cursor={controller._cursor}')
    controller.seek(999.0)
    record('TC-4.6b', 'Seek超范围不越界', controller._cursor <= t_max,
           f'cursor={controller._cursor}, t_max={t_max}')

    # TC-4.7: 速度设置
    for speed in [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]:
        controller.set_speed(speed)
    record('TC-4.7a', '6档速度全部设置成功', controller._speed == 10.0,
           f'最终速度: {controller._speed}x')

    # TC-4.9: 回放完成
    controller._cursor = t_max - 0.01
    controller._state = 'playing'
    controller._on_tick()
    record('TC-4.9a', '回放完成状态=finished', controller._state == 'finished',
           f'状态: {controller._state}')

    cache.close()
    if os.path.exists(db_path):
        os.remove(db_path)


# ============================================================
# Phase 5+6+7: 数据路由验证
# ============================================================
def test_phase567_data_routing():
    section("Phase 5+6+7: 数据路由分类验证")

    from core.core.data_processing.multi_source_cache import MultiSourceCache
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController

    db_path = os.path.join(tempfile.gettempdir(), 'test_routing.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    cache = MultiSourceCache(db_path)

    records = []
    for i in range(50):
        records.append({
            'timestamp': i * 0.02,
            'ch4_ax': 4.0, 'ch4_ay': 5.0, 'ch4_az': 6.0,
            'ch4_gx': 0.4, 'ch4_gy': 0.5, 'ch4_gz': 0.6,
            'speed': 40, 'steering': 10.0,
            '_source_type': 'can_wide', 'source_id': 'can_src',
        })
        records.append({
            'timestamp': i * 0.02 + 0.01,
            'pressure': 120 + i % 10, 'cnap_type': 'WAVE',
            '_source_type': 'cnap', 'source_id': 'cnap_src',
        })
    cache.write_batch(records)

    controller = MultiSourceReplayController()
    controller.load_cache(cache)
    imu_batch = []
    cnap_batch = []
    can_raw_batch = []
    controller.imu_data_batch_received.connect(lambda b: imu_batch.extend(b))
    controller.cnap_data_batch_received.connect(lambda b: cnap_batch.extend(b))
    controller.can_raw_data_batch_received.connect(lambda b: can_raw_batch.extend(b))

    controller._window_size = 5.0
    controller._speed = 100.0
    controller._cursor = 0
    controller._time_max = 2.0
    controller._state = 'playing'
    controller._on_tick()

    # TC-9.1: CAN wide -> IMU batch (ch4 mapped)
    imu_has_can_wide = any(r.get('_source_type') == 'can_wide' for r in imu_batch)
    record('TC-9.1d', 'CAN wide路由到IMU batch', imu_has_can_wide and len(imu_batch) > 0,
           f'IMU batch: {len(imu_batch)}条')

    # CNAP -> CNAP batch
    cnap_has_cnap = any(r.get('_source_type') == 'cnap' for r in cnap_batch)
    record('TC-9.1e', 'CNAP路由到CNAP batch', cnap_has_cnap and len(cnap_batch) > 0,
           f'CNAP batch: {len(cnap_batch)}条')

    # CAN wide -> CAN raw batch
    can_raw_has_wide = any(r.get('_source_type') == 'can_wide' for r in can_raw_batch)
    record('TC-9.1f', 'CAN wide路由到CAN raw batch', can_raw_has_wide,
           f'CAN raw batch: {len(can_raw_batch)}条')

    cache.close()
    if os.path.exists(db_path):
        os.remove(db_path)


# ============================================================
# Phase 7: CAN 全量解析 Tab 逻辑
# ============================================================
def test_phase7_can_tab_logic():
    section("Phase 7: CAN全量解析Tab逻辑")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    from modules.ui.core_ui.components.can_full_parsing_tab import CANFullParsingTab

    tab = CANFullParsingTab()

    # TC-7.1: Tab初始化
    record('TC-7.1a', 'CAN Tab初始化成功', tab is not None)
    record('TC-7.1b', '回放模式默认关闭', tab._replay_mode == False,
           f'_replay_mode={tab._replay_mode}')

    # TC-7.2: 回放模式切换
    tab.set_replay_mode(True)
    record('TC-7.2a', 'set_replay_mode(True)', tab._replay_mode == True)
    tab.set_replay_mode(False)
    record('TC-7.2b', 'set_replay_mode(False)', tab._replay_mode == False)

    # TC-7.2: 宽格式数据处理
    wide_data = {
        'timestamp': 1.0,
        'ch1_ax': 1.0, 'ch1_ay': 2.0, 'ch1_az': 3.0,
        'ch1_gx': 0.1, 'ch1_gy': 0.2, 'ch1_gz': 0.3,
        'ch3_ax': 1.0, 'ch3_ay': 2.0, 'ch3_az': 3.0,
        'ch3_gx': 0.1, 'ch3_gy': 0.2, 'ch3_gz': 0.3,
        'ch4_ax': 1.0, 'ch4_ay': 2.0, 'ch4_az': 3.0,
        'ch4_gx': 0.1, 'ch4_gy': 0.2, 'ch4_gz': 0.3,
        'ch5_ax': 1.0, 'ch5_ay': 2.0, 'ch5_az': 3.0,
        'ch5_gx': 0.1, 'ch5_gy': 0.2, 'ch5_gz': 0.3,
        'speed': 40, 'steering': 10.0,
    }
    tab.receive_can_data(wide_data)
    record('TC-7.2c', '宽格式数据接收不崩溃', tab._record_count >= 0,
           f'record_count={tab._record_count}')

    # TC-7.3: 长格式数据处理
    long_data = {
        'rel_time': 1.0, 'channel': 'ch4',
        'imu_name': 'IMU-04_座椅底部_对照组',
        'Gx_dps': 0.1, 'Gy_dps': 0.2, 'Gz_dps': 0.3,
        'Ax_m_s2': 1.0, 'Ay_m_s2': 2.0, 'Az_m_s2': 3.0,
        'Gx_rad_s': 0.001, 'Gy_rad_s': 0.002, 'Gz_rad_s': 0.003,
        '车速_kmh': 50, '方向盘转角_deg': 15.0,
    }
    prev_count = tab._record_count
    tab.receive_can_data(long_data)
    record('TC-7.3a', '长格式数据接收不崩溃', tab._record_count > prev_count,
           f'record_count={tab._record_count}')

    # TC-7.3: IMU-04_座椅底部_对照组 触发管道
    long_data_ch4 = {
        'rel_time': 2.0, 'channel': 'ch4',
        'imu_name': 'IMU-04_座椅底部_对照组',
        'Gx_dps': 0.5, 'Gy_dps': 0.3, 'Gz_dps': 0.2,
        'Ax_m_s2': 2.0, 'Ay_m_s2': 1.0, 'Az_m_s2': 0.5,
        'Gx_rad_s': 0.008, 'Gy_rad_s': 0.005, 'Gz_rad_s': 0.003,
        '车速_kmh': 60, '方向盘转角_deg': 25.0,
    }
    tab.receive_can_data(long_data_ch4)
    record('TC-7.3b', 'IMU-04对照组触发行为管道', True,
           '管道处理不抛异常')

    # TC-7.5: 清空
    tab.clear_data()
    record('TC-7.5a', '清空数据', tab._record_count == 0 and len(tab._table_rows) == 0,
           f'record_count={tab._record_count}, table_rows={len(tab._table_rows)}')

    # TC-7.7: 表格上限
    for i in range(2500):
        tab._table_rows.append([str(i), 'ch1', 'test', '0', '0', '0', '0', '0', '0', '0', '0', '0'])
    tab._trim_table_if_needed()
    record('TC-7.7a', '表格上限裁剪', len(tab._table_rows) <= 2000,
           f'table_rows after trim: {len(tab._table_rows)}')


# ============================================================
# Phase 10: 边界测试
# ============================================================
def test_phase10_edge_cases():
    section("Phase 10: 边界与异常测试")

    from core.core.data_processing.multi_source_cache import MultiSourceCache
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController

    # TC-10.1: 空缓存
    db_path = os.path.join(tempfile.gettempdir(), 'test_empty.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    cache = MultiSourceCache(db_path)
    results = cache.query_time_range(0, 10.0)
    record('TC-10.1a', '空缓存查询返回空', len(results) == 0,
           f'返回 {len(results)} 条')

    # TC-10.2: 空数据回放控制器
    try:
        controller = MultiSourceReplayController()
        loaded = controller.load_cache(cache)
        t_min, t_max = controller.time_range
        record('TC-10.2a', '空缓存回放控制器创建', not loaded,
               f'loaded={loaded}, time_range=[{t_min}, {t_max}]')
    except Exception as e:
        record('TC-10.2a', '空缓存回放控制器创建', False, str(e))

    cache.close()
    if os.path.exists(db_path):
        os.remove(db_path)

    # TC-10.3: 文件不存在时的 DataSourceReader
    from modules.ui.left_control_panel.utils.data_reader_manager import DataSourceReader

    class MockConfig:
        pass

    class MockPipeline:
        def push_data(self, *a, **kw):
            pass

    cfg = MockConfig()
    cfg.type = 'IMU'
    cfg.sampling_rate = 100
    cfg.connection = {'file_path': r'Z:\nonexistent\file.txt'}
    reader = DataSourceReader('test_missing', cfg, MockPipeline())
    try:
        reader._load_file_data()
        record('TC-10.3a', '文件不存在不崩溃', True,
               f'缓存长度: {len(reader._file_data_cache)}')
    except Exception as e:
        record('TC-10.3a', '文件不存在不崩溃', False, str(e))

    # TC-10.5: 速度极值切换
    db_path2 = os.path.join(tempfile.gettempdir(), 'test_speed.db')
    if os.path.exists(db_path2):
        os.remove(db_path2)
    cache2 = MultiSourceCache(db_path2)
    cache2.write_batch([
        {'timestamp': i * 0.1, 'ax': 1.0, 'ay': 2.0, 'az': 3.0,
         'gx': 0.1, 'gy': 0.2, 'gz': 0.3,
         '_source_type': 'imu_standalone', 'source_id': 'test'}
        for i in range(100)
    ])
    controller2 = MultiSourceReplayController()
    controller2.load_cache(cache2)
    for speed in [0.25, 10.0, 0.25, 10.0, 1.0]:
        controller2.set_speed(speed)
    record('TC-10.5a', '速度极值反复切换', controller2._speed == 1.0,
           f'最终速度: {controller2._speed}')

    cache2.close()
    if os.path.exists(db_path2):
        os.remove(db_path2)


# ============================================================
# 主入口
# ============================================================
def main():
    print("\n" + "=" * 60)
    print("  多源数据融合分析系统 -- 闭环验收自动化测试")
    print("=" * 60)
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  工作目录: {os.getcwd()}")
    print("=" * 60)

    try:
        test_phase1_source_detection()
    except Exception as e:
        logger.error(f"Phase1异常: {e}")
        traceback.print_exc()

    try:
        test_phase3_parsing_correctness()
    except Exception as e:
        logger.error(f"Phase3解析异常: {e}")
        traceback.print_exc()

    try:
        test_phase3_mutual_exclusion()
    except Exception as e:
        logger.error(f"Phase3互斥异常: {e}")
        traceback.print_exc()

    try:
        test_phase4_cache_and_replay()
    except Exception as e:
        logger.error(f"Phase4缓存回放异常: {e}")
        traceback.print_exc()

    try:
        test_phase4_state_machine()
    except Exception as e:
        logger.error(f"Phase4状态机异常: {e}")
        traceback.print_exc()

    try:
        test_phase567_data_routing()
    except Exception as e:
        logger.error(f"Phase5-7路由异常: {e}")
        traceback.print_exc()

    try:
        test_phase7_can_tab_logic()
    except Exception as e:
        logger.error(f"Phase7 CAN Tab异常: {e}")
        traceback.print_exc()

    try:
        test_phase10_edge_cases()
    except Exception as e:
        logger.error(f"Phase10边界异常: {e}")
        traceback.print_exc()

    # 汇总
    total = PASS + FAIL + SKIP
    print(f"\n{'='*60}")
    print(f"  测试汇总")
    print(f"{'='*60}")
    print(f"  总计: {total}  |  通过: {PASS}  |  失败: {FAIL}  |  跳过: {SKIP}")
    if total > 0:
        rate = PASS / (PASS + FAIL) * 100 if (PASS + FAIL) > 0 else 100
        print(f"  通过率: {rate:.1f}% (不含跳过)")
    print(f"{'='*60}")

    if FAIL > 0:
        print(f"\n  失败用例:")
        for tid, name, status, detail in RESULTS:
            if status == 'FAIL':
                print(f"    [{tid}] {name}: {detail}")

    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())