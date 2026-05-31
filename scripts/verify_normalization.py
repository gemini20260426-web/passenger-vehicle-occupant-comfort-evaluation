#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据标准化方案 — 全量验证脚本
验证 Phase 1-4 所有修改的正确性
"""

import os
import sys
import csv
import math
import json

PROJECT_ROOT = r'd:\UI重构_全量备份_20250824_233403'
sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)

passed = 0
failed = 0
errors = []


def check(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  [PASS] {name}')
    else:
        failed += 1
        msg = f'  [FAIL] {name} {detail}'
        print(msg)
        errors.append(msg)


print('=' * 60)
print('Phase 1 验证: 基础设施')
print('=' * 60)

# 1.1 DataNormalizer 导入
print('\n--- 1.1 DataNormalizer 模块 ---')
try:
    from core.core.data_processing.data_normalizer import DataNormalizer
    check('DataNormalizer 导入成功', True)
except Exception as e:
    check('DataNormalizer 导入成功', False, str(e))

# 1.2 estimate_gz 静态方法
print('\n--- 1.2 estimate_gz 计算 ---')
from core.core.data_processing.data_parser import IMUDataParser

gz1 = IMUDataParser.estimate_gz(36.0, 30.0)
check('gz(36km/h, 30°方向盘) ≈ 0.121 rad/s', abs(gz1 - 0.121) < 0.01, f'got {gz1:.6f}')

gz2 = IMUDataParser.estimate_gz(0, 30.0)
check('gz(0km/h, 30°) = 0', abs(gz2) < 1e-10, f'got {gz2:.6f}')

gz3 = IMUDataParser.estimate_gz(36.0, 0)
check('gz(36km/h, 0°) = 0', abs(gz3) < 1e-10, f'got {gz3:.6f}')

gz4 = IMUDataParser.estimate_gz(72.0, 45.0)
check('gz(72km/h, 45°) > gz(36km/h, 30°)', gz4 > gz1, f'{gz4:.6f} vs {gz1:.6f}')

# 1.3 DataNormalizer.detect_format
print('\n--- 1.3 detect_format ---')
normalizer = DataNormalizer()

rec_12field = {'ax': 0.1, 'ay': 0.2, 'az': 9.8, 'gx': 0.01, 'gy': 0.02, 'gz': 0.03, 'speed': 50, 'wheel': 5}
check('detect 12field', DataNormalizer.detect_format(rec_12field) == '12field')

rec_8field = {'ax': 0.1, 'ay': 0.2, 'az': 9.8, 'gx': None, 'gy': None, 'gz': None, 'speed': 50, 'wheel': 5}
check('detect 8field', DataNormalizer.detect_format(rec_8field) == '8field')

rec_bad = {'ax': 0.1, 'ay': 0.2}
check('detect unknown', DataNormalizer.detect_format(rec_bad) == 'unknown')

# 1.4 normalize_record
print('\n--- 1.4 normalize_record ---')
norm_12 = normalizer.normalize_record(rec_12field)
check('normalize 12field: gx preserved', norm_12['gx'] == 0.01)
check('normalize 12field: source_format', norm_12['source_format'] == '12field_original')

normalizer.reset_stats()
norm_8 = normalizer.normalize_record(rec_8field)
check('normalize 8field: gx empty', norm_8['gx'] == '')
check('normalize 8field: gy empty', norm_8['gy'] == '')
check('normalize 8field: gz estimated', isinstance(norm_8['gz'], float) and norm_8['gz'] != '')
check('normalize 8field: source_format', norm_8['source_format'] == '8field_estimated')

stats = normalizer.get_stats()
check('stats: total=1', stats['total'] == 1, str(stats))
check('stats: 12field=0', stats['twelve_field'] == 0, str(stats))
check('stats: 8field=1', stats['eight_field'] == 1)
check('stats: estimated_gz=1', stats['estimated_gz'] == 1)


print('\n' + '=' * 60)
print('Phase 2 验证: 核心修复')
print('=' * 60)

# 2.1 _normalize_fields 保留 None
print('\n--- 2.1 _normalize_fields ---')
from core.core.analysis.base_analyzer import BasicDrivingAnalyzer

analyzer = BasicDrivingAnalyzer()
test_data = {'ax': 0.1, 'ay': 0.2, 'az': 9.8, 'gx': None, 'gy': None, 'gz': None, 'speed': 50, 'wheel': 5}
normalized = analyzer._normalize_fields(test_data)
check('_normalize_fields: gx stays None', normalized.get('gx') is None)
check('_normalize_fields: gy stays None', normalized.get('gy') is None)
check('_normalize_fields: gz stays None', normalized.get('gz') is None)
check('_normalize_fields: ax preserved', normalized.get('ax') == 0.1)

# 2.2 行为检测函数守卫修正
print('\n--- 2.2 行为检测函数 ---')
import numpy as np
from core.core.analysis.base_analyzer import (
    is_turning, is_u_turn, is_large_radius_turning,
    is_curve_compliant, is_skidding
)

class MockThresholds:
    STEERING_ANGLE_TURN_THRESHOLD = 15
    Z_ANGULAR_VELOCITY_TURN_THRESHOLD = 0.01
    U_TURN_STEERING_ANGLE_THRESHOLD = 200
    U_TURN_Z_ANGULAR_VELOCITY_THRESHOLD = 0.1
    LARGE_RADIUS_TURN_STEERING_ANGLE_LOW = 10
    LARGE_RADIUS_TURN_STEERING_ANGLE_HIGH = 50
    LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_LOW = 0.01
    LARGE_RADIUS_TURN_Z_ANGULAR_VELOCITY_HIGH = 0.1
    CURVE_STEERING_ANGLE_THRESHOLD = 10
    CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_LOW = 0.001
    CURVE_Z_ANGULAR_VELOCITY_SPEED_RATIO_HIGH = 0.1
    SKID_ACCELERATION_CHANGE_RATE_THRESHOLD = 0.5
    SKID_Z_ANGULAR_VELOCITY_THRESHOLD = 0.01

thresh = MockThresholds()

# 8字段数据 (gz=None)
window_8field = {
    'wheel': np.array([30.0, 32.0, 28.0]),
    'gz': None,
    'speed': np.array([36.0, 36.0, 36.0]),
    'ay': np.array([0.1, 0.2, 0.1]),
}
check('is_turning(8field) = 无转弯', is_turning(window_8field, thresh) == "无转弯行为")
check('is_u_turn(8field) = 无U型转弯', is_u_turn(window_8field, thresh) == "无U型转弯")
check('is_large_radius_turning(8field) = False', is_large_radius_turning(window_8field, thresh) == False)
check('is_curve_compliant(8field) = False', is_curve_compliant(window_8field, thresh) == False)
check('is_skidding(8field) = False', is_skidding(window_8field, thresh) == False)

# 12字段数据 (gz有值)
window_12field = {
    'wheel': np.array([30.0, 32.0, 28.0]),
    'gz': np.array([0.05, 0.06, 0.04]),
    'speed': np.array([36.0, 36.0, 36.0]),
    'ay': np.array([0.1, 0.2, 0.1]),
}
result_turn = is_turning(window_12field, thresh)
check('is_turning(12field) 检测到转弯', result_turn != "无转弯行为", f'got {result_turn}')

# gz=0 但非None (真的没有旋转)
window_zero_gz = {
    'wheel': np.array([0.0, 0.0, 0.0]),
    'gz': np.array([0.0, 0.0, 0.0]),
    'speed': np.array([36.0, 36.0, 36.0]),
    'ay': np.array([0.0, 0.0, 0.0]),
}
result_zero = is_turning(window_zero_gz, thresh)
check('is_turning(gz=0, wheel=0) = 无转弯', result_zero == "无转弯行为", f'got {result_zero}')


print('\n' + '=' * 60)
print('Phase 3 验证: 集成适配')
print('=' * 60)

# 3.1 FileDataReader 标准化
print('\n--- 3.1 FileDataReader ---')
from core.core.data_processing.data_reader import FileDataReader

reader = FileDataReader('dummy.txt', enable_normalization=True)
check('FileDataReader.enable_normalization', reader.enable_normalization == True)
check('FileDataReader.normalized_file_path init', reader.normalized_file_path is None)

# 3.3 DataBridge.load_from_normalized
print('\n--- 3.3 DataBridge.load_from_normalized ---')
from core.core.analysis.data_bridge import DataBridge

bridge = DataBridge()
check('DataBridge.load_from_normalized exists', hasattr(bridge, 'load_from_normalized'))

# 测试不存在的文件
count = bridge.load_from_normalized('nonexistent.csv')
check('load_from_normalized(不存在) = 0', count == 0)


print('\n' + '=' * 60)
print('Phase 4 验证: UI 适配')
print('=' * 60)

# 4.3 DataPersister._safe_val
print('\n--- 4.3 DataPersister._safe_val ---')
from core.core.data_processing.data_persister import DataPersister

check('_safe_val(None→"")', DataPersister._safe_val({'gx': None}, 'gx') == '')
check('_safe_val(0→0)', DataPersister._safe_val({'gx': 0}, 'gx') == 0)
check('_safe_val(0.01→0.01)', DataPersister._safe_val({'gx': 0.01}, 'gx') == 0.01)
check('_safe_val(missing→"")', DataPersister._safe_val({}, 'gx') == '')
check('_safe_val(not dict→"")', DataPersister._safe_val(None, 'gx') == '')


print('\n' + '=' * 60)
print('Phase 5 验证: 端到端集成测试')
print('=' * 60)

# 5.1 用 IMU路测数据.txt 全量测试
print('\n--- 5.1 全量标准化测试 ---')
test_file = os.path.join(PROJECT_ROOT, 'test_data', 'IMU路测数据.txt')

if os.path.exists(test_file):
    normalizer2 = DataNormalizer()
    filepath, written, stats = normalizer2.parse_and_normalize(test_file)

    check('标准化文件已生成', filepath != '' and os.path.exists(filepath), filepath)
    check('记录数 > 0', written > 0, f'written={written}')
    check('8field 记录 > 0', stats.get('eight_field', 0) > 0, str(stats))
    check('estimated_gz > 0', stats.get('estimated_gz', 0) > 0, str(stats))

    # 验证CSV内容
    if filepath and os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        check('CSV有14列', len(rows[0]) == 14 if rows else False,
              f'got {len(rows[0]) if rows else 0} columns: {list(rows[0].keys()) if rows else "N/A"}')

        # 检查8字段行: gx/gy为空, gz有值
        eight_rows = [r for r in rows if r.get('source_format') == '8field_estimated']
        if eight_rows:
            r = eight_rows[0]
            check('8field行: gx为空', r['gx'] == '', f'got "{r["gx"]}"')
            check('8field行: gy为空', r['gy'] == '', f'got "{r["gy"]}"')
            check('8field行: gz有值', r['gz'] != '' and r['gz'] is not None,
                  f'gz={r["gz"]}, wheel={r.get("wheel")}, speed={r.get("speed")}')

        # 5.2 用 DataBridge 加载标准化文件
        print('\n--- 5.2 DataBridge 加载标准化文件 ---')
        bridge2 = DataBridge()
        count2 = bridge2.load_from_normalized(filepath)
        check('DataBridge 加载成功', count2 > 0, f'loaded {count2}')
        check('DataBridge 加载数=写入数', count2 == written, f'{count2} vs {written}')

        # 验证加载的数据中 gx/gy 为 None (不是0)
        latest = bridge2.get_latest_data()
        if latest:
            src_fmt = latest.get('source_format', '')
            if src_fmt == '8field_estimated':
                check('加载后 gx=None', latest.get('gx') is None, f'got {latest.get("gx")}')
                check('加载后 gy=None', latest.get('gy') is None, f'got {latest.get("gy")}')
                check('加载后 gz 有值', latest.get('gz') is not None, f'got {latest.get("gz")}')
else:
    print(f'  测试文件不存在: {test_file}')
    check('测试文件存在', False, test_file)


print('\n' + '=' * 60)
print(f'验证结果: {passed} 通过, {failed} 失败')
print('=' * 60)

if errors:
    print('\n失败详情:')
    for e in errors:
        print(f'  {e}')

sys.exit(0 if failed == 0 else 1)
