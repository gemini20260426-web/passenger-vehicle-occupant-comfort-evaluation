#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的集成测试：主要验证核心功能
"""

import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_1_analysis_result_cache():
    """测试1: AnalysisResultCache 基础功能"""
    logger.info("=" * 80)
    logger.info("测试1: AnalysisResultCache 基础功能")
    logger.info("=" * 80)
    
    from core.core.analysis.analysis_result_cache import AnalysisResultCache
    from core.core.analysis.core_types import (
        FrameResult, FrameFeatures, RiskReport, DrivingState, RiskLevel
    )
    
    # 创建内存缓存
    cache = AnalysisResultCache(":memory:")
    assert cache is not None, "创建缓存失败"
    logger.info("✓ 缓存创建成功")
    
    # 创建测试数据
    test_frames = []
    for i in range(100):
        features = FrameFeatures(
            timestamp=i * 0.1,
            temporal={'mean': i * 0.5, 'std': i * 0.1},
            spectral={'freq': i * 10, 'power': i * 2}
        )
        risk = RiskReport(
            level=RiskLevel.SAFE if i % 2 == 0 else RiskLevel.LOW,
            score=0.1 * i
        )
        frame = FrameResult(
            timestamp=i * 0.1,
            state=DrivingState.STRAIGHT_CRUISE,
            ax=0.1 + i * 0.01,
            ay=0.01,
            az=9.8,
            gx=0.0,
            gy=0.0,
            gz=0.0,
            speed=10.0 + i * 0.5,
            wheel=0.0,
            features=features,
            risk=risk
        )
        test_frames.append(frame)
    
    # 写入单个
    logger.info("测试写入单个FrameResult...")
    success = cache.write_frame_result(test_frames[0])
    assert success, "写入单个失败"
    logger.info("✓ 单个写入成功")
    
    # 批量写入
    logger.info("测试批量写入FrameResults...")
    count = cache.write_batch(test_frames[1:])
    assert count == 99, f"批量写入失败，期望99，实际{count}"
    logger.info(f"✓ 批量写入成功: {count}条")
    
    # 查询统计
    stats = cache.get_stats()
    logger.info(f"统计信息: {stats}")
    assert stats["total_records"] == 100, f"总记录数错误，期望100，实际{stats['total_records']}"
    assert stats["time_range"][0] == 0.0, f"时间范围最小值错误"
    assert stats["time_range"][1] == 9.9, f"时间范围最大值错误"
    logger.info("✓ 统计信息验证通过")
    
    # 时间范围查询
    logger.info("测试时间范围查询...")
    results = cache.query_time_range(0.0, 5.0)
    assert len(results) >= 45, f"查询结果数量不足，期望至少45，实际{len(results)}"
    logger.info(f"✓ 时间范围查询成功: {len(results)}条")
    
    # 关闭缓存
    cache.close()
    logger.info("✓ 缓存关闭成功")
    logger.info("测试1完成 ✓")
    return True


def test_2_data_bridge_caching():
    """测试2: DataBridge 缓存功能"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2: DataBridge 缓存功能")
    logger.info("=" * 80)
    
    from core.core.analysis.data_bridge import DataBridge
    
    # 创建DataBridge
    data_bridge = DataBridge()
    assert data_bridge is not None, "创建DataBridge失败"
    logger.info("✓ DataBridge创建成功")
    
    # 启用缓存
    data_bridge.enable_result_caching()
    cache = data_bridge.get_analysis_cache()
    assert cache is not None, "启用缓存失败"
    logger.info(f"✓ 分析结果缓存已启用: {cache.db_path}")
    
    # 生成测试数据
    test_records = []
    for i in range(100):
        record = {
            'timestamp': i * 0.1,
            'ax': 0.1 + i * 0.01,
            'ay': 0.01,
            'az': 9.8,
            'gx': 0.0,
            'gy': 0.0,
            'gz': 0.0,
            'speed': 10.0 + i * 0.5,
            'wheel': 0.0,
            '_source_type': 'imu_standalone'
        }
        test_records.append(record)
    
    # 启动处理
    data_bridge.start_processing()
    logger.info("✓ DataBridge处理已启动")
    
    # 喂入数据
    logger.info("开始喂入数据...")
    for record in test_records:
        data_bridge.feed_parsed_data(record)
    logger.info("✓ 数据喂入完成")
    
    # 等待处理完成
    time.sleep(2.0)
    
    # 在停止前获取缓存
    stats = cache.get_stats()
    logger.info(f"缓存统计: {stats}")
    assert stats["total_records"] > 0, "缓存中没有结果"
    logger.info(f"✓ 分析结果缓存中有 {stats['total_records']} 条记录")
    
    # 查询一些结果
    results = cache.query_time_range(0.0, 5.0)
    assert len(results) > 0, "查询结果为空"
    logger.info(f"✓ 查询到 {len(results)} 条分析结果")
    
    # 检查结果内容
    fr = results[0]
    assert hasattr(fr, 'state'), "FrameResult缺少state字段"
    assert hasattr(fr, 'ax'), "FrameResult缺少ax字段"
    assert hasattr(fr, 'speed'), "FrameResult缺少speed字段"
    logger.info("✓ FrameResult字段验证通过")
    
    # 停止处理
    data_bridge.stop_processing()
    logger.info("✓ DataBridge处理已停止")
    
    logger.info("测试2完成 ✓")
    return True


def test_3_replay_controller_loading():
    """测试3: MultiSourceReplayController 缓存加载"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: MultiSourceReplayController 缓存加载")
    logger.info("=" * 80)
    
    from core.core.analysis.analysis_result_cache import AnalysisResultCache
    from core.core.analysis.core_types import FrameResult, FrameFeatures, RiskReport, DrivingState, RiskLevel
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController
    from core.core.data_processing.multi_source_cache import MultiSourceCache
    
    # 创建分析结果缓存并写入测试数据
    analysis_cache = AnalysisResultCache(":memory:")
    test_frames = []
    for i in range(100):
        features = FrameFeatures(
            timestamp=i * 0.1,
            temporal={'mean': i * 0.5},
            spectral={'freq': i * 10}
        )
        risk = RiskReport(level=RiskLevel.SAFE, score=0.1 * i)
        frame = FrameResult(
            timestamp=i * 0.1,
            state=DrivingState.STRAIGHT_CRUISE,
            ax=0.1 + i * 0.01,
            ay=0.01,
            az=9.8,
            gx=0.0, gy=0.0, gz=0.0,
            speed=10.0 + i * 0.5,
            wheel=0.0,
            features=features,
            risk=risk
        )
        test_frames.append(frame)
    analysis_cache.write_batch(test_frames)
    logger.info(f"✓ 分析结果缓存已创建，有 {len(test_frames)} 条数据")
    
    # 创建原始数据缓存
    raw_cache = MultiSourceCache(":memory:")
    test_raw_records = []
    for i in range(100):
        record = {
            'timestamp': i * 0.1,
            'ax': 0.1 + i * 0.01,
            'ay': 0.01,
            'az': 9.8,
            'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
            'speed': 10.0 + i * 0.5,
            'wheel': 0.0,
            '_source_type': 'imu_standalone',
            '_rel_time': i * 0.1
        }
        test_raw_records.append(record)
    raw_cache.write_batch(test_raw_records)
    logger.info(f"✓ 原始数据缓存已创建，有 {len(test_raw_records)} 条数据")
    
    # 创建回放控制器
    replay_ctrl = MultiSourceReplayController()
    loaded = replay_ctrl.load_cache(raw_cache)
    assert loaded, "加载原始数据缓存失败"
    logger.info("✓ 原始数据缓存加载成功")
    
    loaded_analysis = replay_ctrl.load_analysis_cache(analysis_cache)
    assert loaded_analysis, "加载分析结果缓存失败"
    logger.info("✓ 分析结果缓存加载成功")
    
    # 检查时间范围
    time_range = replay_ctrl.time_range
    logger.info(f"回放时间范围: {time_range}")
    assert time_range[0] == 0.0, "时间范围起始错误"
    assert time_range[1] == 9.9, "时间范围结束错误"
    
    # 设置回放模式
    replay_ctrl.set_replay_mode('fast')
    assert replay_ctrl.replay_mode == 'fast', "回放模式设置错误"
    logger.info("✓ 快速回放模式设置成功")
    
    # 验证查询功能
    test_results = analysis_cache.query_time_range(0.0, 2.0)
    assert len(test_results) > 0, "查询分析结果失败"
    logger.info(f"✓ 分析结果查询成功: {len(test_results)} 条")
    
    # 清理
    analysis_cache.close()
    raw_cache.close()
    
    logger.info("测试3完成 ✓")
    return True


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始简化集成测试")
    logger.info("=" * 80)
    
    tests = [
        ("AnalysisResultCache 基础功能", test_1_analysis_result_cache),
        ("DataBridge 缓存功能", test_2_data_bridge_caching),
        ("MultiSourceReplayController 缓存加载", test_3_replay_controller_loading),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            logger.error(f"测试 {name} 失败: {e}", exc_info=True)
            results.append((name, False))
    
    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("测试总结")
    logger.info("=" * 80)
    
    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        logger.info(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    logger.info(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
