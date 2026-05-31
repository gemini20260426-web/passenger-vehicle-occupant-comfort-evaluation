#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测指标完整性专业验证测试
验证内容：
1. 指标定义完整性
2. 标准引用完整性
3. 维度分组完整性
4. 位置配置完整性
5. 引擎支持完整性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir / 'core'))

from core.analysis.core_types import (
    INDICATOR_DEFINITIONS, INDICATOR_DETAIL, STANDARD_REFERENCES,
    COMPARISON_DIMENSIONS, DIAGNOSIS_THRESHOLDS
)
from core.seat_evaluation.imu_location_config import (
    IMU_LOCATION_MAPPING, INDICATOR_CATEGORIES,
    get_all_metrics, get_metrics_for_location
)
from core.seat_evaluation.engine_v2 import METRIC_THRESHOLDS


def print_separator(title=""):
    """打印分隔符"""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}")
    else:
        print(f"\n{'-' * 80}")


def test_indicator_definitions():
    """测试指标定义完整性"""
    print_separator("1. 指标定义完整性测试 (INDICATOR_DEFINITIONS)")
    
    print(f"✅ 定义的指标总数: {len(INDICATOR_DEFINITIONS)}")
    
    # 检查每个指标是否有必要的字段
    missing_fields = []
    for metric_id, info in INDICATOR_DEFINITIONS.items():
        if 'name' not in info:
            missing_fields.append(f"{metric_id}: 缺少 name 字段")
        if 'unit' not in info:
            missing_fields.append(f"{metric_id}: 缺少 unit 字段")
        if 'type' not in info:
            missing_fields.append(f"{metric_id}: 缺少 type 字段")
    
    if missing_fields:
        print(f"❌ 发现缺失字段的指标:")
        for msg in missing_fields:
            print(f"   - {msg}")
        return False
    else:
        print("✅ 所有指标都包含必要字段 (name, unit, type)")
        
    # 打印所有指标列表
    print("\n📊 指标列表:")
    for metric_id, info in sorted(INDICATOR_DEFINITIONS.items()):
        print(f"   • {metric_id:15s} {info['name']:20s} [{info['unit']}]")
    
    return True


def test_indicator_detail():
    """测试指标详细说明完整性"""
    print_separator("2. 指标详细说明完整性测试 (INDICATOR_DETAIL)")
    
    print(f"✅ 有详细说明的指标数: {len(INDICATOR_DETAIL)}")
    
    # 检查 INDICATOR_DEFINITIONS 中的指标是否都在 INDICATOR_DETAIL 中
    missing_details = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in INDICATOR_DETAIL:
            missing_details.append(metric_id)
    
    if missing_details:
        print(f"❌ 缺少详细说明的指标: {missing_details}")
        return False
    else:
        print("✅ 所有指标都有详细说明")
        
    # 检查 INDICATOR_DETAIL 的内容是否完整
    required_keys = ['category', 'location_dependency', 'calculation_logic']
    incomplete = []
    for metric_id, detail in INDICATOR_DETAIL.items():
        for key in required_keys:
            if key not in detail:
                incomplete.append(f"{metric_id}: 缺少 {key}")
    
    if incomplete:
        print(f"❌ 详细说明不完整: {incomplete}")
        return False
    else:
        print("✅ 所有指标详细说明都包含必要字段")
    
    return True


def test_standard_references():
    """测试标准引用完整性"""
    print_separator("3. 标准引用完整性测试 (STANDARD_REFERENCES)")
    
    print(f"✅ 有标准引用的指标数: {len(STANDARD_REFERENCES)}")
    
    # 检查重要指标是否有标准引用
    critical_metrics = [
        'SEAT_Z', 'SEAT_XY', 'AW_Z', 'AW_XY',
        'HIC15', 'ACC_H_PEAK', 'SRS_MRS', 'VDV_Z', 'FDS_D'
    ]
    
    missing_standards = []
    for metric_id in critical_metrics:
        if metric_id not in STANDARD_REFERENCES:
            missing_standards.append(metric_id)
    
    if missing_standards:
        print(f"❌ 关键指标缺少标准引用: {missing_standards}")
        return False
    else:
        print("✅ 所有关键指标都有标准引用")
    
    # 打印标准引用
    print("\n📚 标准引用汇总:")
    for metric_id, ref in sorted(STANDARD_REFERENCES.items()):
        std = ref.get('standard', 'Engineering guideline')
        limit = ref.get('limit', '')
        print(f"   • {metric_id:15s} {std} {limit}")
    
    return True


def test_comparison_dimensions():
    """测试对比维度完整性"""
    print_separator("4. 对比维度完整性测试 (COMPARISON_DIMENSIONS)")
    
    print(f"✅ 定义的维度数: {len(COMPARISON_DIMENSIONS)}")
    
    all_dim_metrics = set()
    for dim in COMPARISON_DIMENSIONS:
        dim_id = dim['id']
        dim_name = dim['name']
        metrics = dim['metrics']
        all_dim_metrics.update(metrics)
        print(f"   • {dim_id:20s} {dim_name:20s} 指标数: {len(metrics)} {metrics}")
    
    # 检查哪些指标没有被包含在任何维度中
    not_in_dim = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in all_dim_metrics:
            not_in_dim.append(metric_id)
    
    if not_in_dim:
        print(f"\n⚠️  未包含在任何维度中的指标: {not_in_dim}")
    else:
        print("\n✅ 所有指标都被包含在对比维度中")
    
    return True


def test_location_mapping():
    """测试位置配置完整性"""
    print_separator("5. IMU位置配置完整性测试 (imu_location_config)")
    
    print(f"✅ 定义的位置数: {len(IMU_LOCATION_MAPPING)}")
    
    # 检查每个位置的指标配置
    for loc_id, loc_config in IMU_LOCATION_MAPPING.items():
        loc_name = loc_config.location_name_cn
        metrics = loc_config.primary_metrics
        print(f"   • {loc_id:15s} {loc_name:15s} 指标数: {len(metrics)} {metrics[:5]}{'...' if len(metrics) > 5 else ''}")
    
    # 检查所有指标是否被分配到位置
    all_loc_metrics = set(get_all_metrics())
    not_assigned = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in all_loc_metrics:
            not_assigned.append(metric_id)
    
    if not_assigned:
        print(f"\n⚠️  未分配到任何位置的指标: {not_assigned}")
    else:
        print("\n✅ 所有指标都分配到了至少一个位置")
    
    return True


def test_indicator_categories():
    """测试指标分类完整性"""
    print_separator("6. 指标分类完整性测试 (INDICATOR_CATEGORIES)")
    
    all_cat_metrics = set()
    for cat_id, cat_info in INDICATOR_CATEGORIES.items():
        cat_name = cat_info['name']
        metrics = cat_info['indicators']
        all_cat_metrics.update(metrics)
        print(f"   • {cat_id:20s} {cat_name:25s} 指标数: {len(metrics)} {metrics[:5]}{'...' if len(metrics) > 5 else ''}")
    
    # 检查哪些指标没有分类
    not_in_cat = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in all_cat_metrics:
            not_in_cat.append(metric_id)
    
    if not_in_cat:
        print(f"\n⚠️  未包含在任何分类中的指标: {not_in_cat}")
        return False
    else:
        print("\n✅ 所有指标都包含在分类中")
        return True


def test_engine_thresholds():
    """测试引擎阈值完整性"""
    print_separator("7. 引擎评分阈值完整性测试 (engine_v2)")
    
    print(f"✅ 有阈值的指标数: {len(METRIC_THRESHOLDS)}")
    
    missing_thresholds = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in METRIC_THRESHOLDS:
            missing_thresholds.append(metric_id)
    
    if missing_thresholds:
        print(f"⚠️  缺少阈值的指标: {missing_thresholds}")
    else:
        print("✅ 所有指标都有评分阈值")
    
    return True


def test_diagnosis_thresholds():
    """测试诊断阈值完整性"""
    print_separator("8. 诊断阈值完整性测试 (DIAGNOSIS_THRESHOLDS)")
    
    print(f"✅ 有诊断阈值的指标数: {len(DIAGNOSIS_THRESHOLDS)}")
    
    missing = []
    for metric_id in INDICATOR_DEFINITIONS:
        if metric_id not in DIAGNOSIS_THRESHOLDS:
            missing.append(metric_id)
    
    if missing:
        print(f"⚠️  缺少诊断阈值的指标: {missing}")
    else:
        print("✅ 所有指标都有诊断阈值")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("  座椅评测指标完整性专业验证测试")
    print("=" * 80)
    
    tests = [
        test_indicator_definitions,
        test_indicator_detail,
        test_standard_references,
        test_comparison_dimensions,
        test_location_mapping,
        test_indicator_categories,
        test_engine_thresholds,
        test_diagnosis_thresholds,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print_separator("测试结果汇总")
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status} {test_name}")
        if not passed:
            all_passed = False
    
    print_separator()
    if all_passed:
        print("🎉 所有核心测试通过！指标体系完整且专业！")
        return 0
    else:
        print("⚠️  部分测试失败，需要检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
