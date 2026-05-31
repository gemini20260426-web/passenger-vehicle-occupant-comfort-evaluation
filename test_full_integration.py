#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整集成测试：测试 AnalysisResultCache + DataBridge + MultiSourceReplayController 完整链路
"""

import os
import sys
import time
import logging
import tempfile
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
    from core.core.analysis.core_types import DrivingState
    
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
    time.sleep(1.0)
    data_bridge.stop_processing()
    logger.info("✓ DataBridge处理已停止")
    
    # 验证缓存
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
    
    logger.info("测试2完成 ✓")
    return True


def test_3_replay_controller_fast_mode():
    """测试3: MultiSourceReplayController 快速回放模式"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: MultiSourceReplayController 快速回放模式")
    logger.info("=" * 80)
    
    from core.core.analysis.data_bridge import DataBridge
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
    replay_ctrl.load_cache(raw_cache)
    replay_ctrl.load_analysis_cache(analysis_cache)
    replay_ctrl.set_replay_mode('fast')
    logger.info("✓ 回放控制器已创建，快速回放模式")
    
    # 收集接收到的信号
    received_frames = []
    received_raw = []
    received_progress = []
    
    def on_frame_result(fr):
        received_frames.append(fr)
    
    def on_sensor_batch(batch):
        received_raw.extend(batch)
    
    def on_progress(p):
        received_progress.append(p)
    
    # 连接信号
    replay_ctrl.frame_result_ready.connect(on_frame_result)
    replay_ctrl.sensor_data_batch_received.connect(on_sensor_batch)
    replay_ctrl.replay_progress.connect(on_progress)
    
    # 测试快速回放
    logger.info("开始快速回放测试...")
    start_time = time.time()
    replay_ctrl.play()
    
    # 等待回放完成
    max_wait = 10.0
    wait_time = 0.0
    while replay_ctrl.state != 'finished' and wait_time < max_wait:
        time.sleep(0.1)
        wait_time += 0.1
    
    elapsed = time.time() - start_time
    logger.info(f"✓ 回放完成，耗时 {elapsed:.2f}秒")
    
    # 验证结果
    logger.info(f"接收到的FrameResults数量: {len(received_frames)}")
    logger.info(f"接收到的原始数据数量: {len(received_raw)}")
    logger.info(f"进度更新次数: {len(received_progress)}")
    
    assert len(received_frames) > 0, "没有接收到任何FrameResult"
    assert len(received_raw) > 0, "没有接收到任何原始数据"
    assert len(received_progress) > 0, "没有进度更新"
    
    # 验证最后一个进度接近1.0
    if received_progress:
        last_progress = received_progress[-1]
        logger.info(f"最后一个进度: {last_progress:.3f}")
        assert last_progress > 0.9, f"回放没有完成，最后进度 {last_progress:.3f}"
    
    # 验证回放到了结尾
    assert replay_ctrl.cursor >= replay_ctrl.time_range[1] * 0.9, "回放没有到达结尾"
    logger.info("✓ 快速回放验证通过")
    
    logger.info("测试3完成 ✓")
    return True


def test_4_full_pipeline():
    """测试4: 完整流程 - DataBridge处理 + 缓存 + 回放"""
    logger.info("\n" + "=" * 80)
    logger.info("测试4: 完整流程 - DataBridge处理 + 缓存 + 回放")
    logger.info("=" * 80)
    
    from core.core.analysis.data_bridge import DataBridge
    from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController
    from core.core.data_processing.multi_source_cache import MultiSourceCache
    
    # 步骤1: 创建DataBridge并启用缓存
    data_bridge = DataBridge()
    data_bridge.enable_result_caching()
    logger.info("✓ 步骤1: DataBridge和缓存已准备")
    
    # 步骤2: 生成测试数据
    test_records = []
    for i in range(200):
        record = {
            'timestamp': i * 0.05,
            'ax': 0.1 + i * 0.005,
            'ay': 0.01,
            'az': 9.8,
            'gx': 0.0,
            'gy': 0.0,
            'gz': 0.0,
            'speed': 10.0 + i * 0.25,
            'wheel': 0.0,
            '_source_type': 'imu_standalone'
        }
        test_records.append(record)
    logger.info(f"✓ 步骤2: 生成了 {len(test_records)} 条测试数据")
    
    # 步骤3: DataBridge处理数据
    logger.info("步骤3: 开始处理数据...")
    data_bridge.start_processing()
    for record in test_records:
        data_bridge.feed_parsed_data(record)
    time.sleep(1.5)
    data_bridge.stop_processing()
    logger.info("✓ 步骤3: 数据处理完成")
    
    # 检查缓存
    analysis_cache = data_bridge.get_analysis_cache()
    stats = analysis_cache.get_stats()
    logger.info(f"分析结果缓存统计: {stats}")
    assert stats["total_records"] > 0, "分析结果缓存为空"
    logger.info("✓ 分析结果缓存验证通过")
    
    # 步骤4: 创建原始数据缓存（模拟实际场景）
    raw_cache = MultiSourceCache(":memory:")
    raw_records = []
    for i in range(200):
        record = {
            'timestamp': i * 0.05,
            'ax': 0.1 + i * 0.005,
            'ay': 0.01,
            'az': 9.8,
            'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
            'speed': 10.0 + i * 0.25,
            'wheel': 0.0,
            '_source_type': 'imu_standalone',
            '_rel_time': i * 0.05
        }
        raw_records.append(record)
    raw_cache.write_batch(raw_records)
    logger.info("✓ 步骤4: 原始数据缓存已创建")
    
    # 步骤5: 回放测试
    logger.info("步骤5: 开始回放测试...")
    replay_ctrl = MultiSourceReplayController()
    replay_ctrl.load_cache(raw_cache)
    replay_ctrl.load_analysis_cache(analysis_cache)
    replay_ctrl.set_replay_mode('fast')
    
    # 收集信号
    frames_received = []
    raw_received = []
    events_received = []
    progress_received = []
    
    def on_frame(fr):
        frames_received.append(fr)
    
    def on_raw(batch):
        raw_received.extend(batch)
    
    def on_event(ev):
        events_received.append(ev)
    
    def on_progress(p):
        progress_received.append(p)
    
    replay_ctrl.frame_result_ready.connect(on_frame)
    replay_ctrl.sensor_data_batch_received.connect(on_raw)
    replay_ctrl.behavior_event_ready.connect(on_event)
    replay_ctrl.replay_progress.connect(on_progress)
    
    # 开始回放
    start_time = time.time()
    replay_ctrl.play()
    logger.info("回放已启动...")
    
    # 等待完成
    max_wait = 15.0
    wait_time = 0.0
    while replay_ctrl.state != 'finished' and wait_time < max_wait:
        time.sleep(0.1)
        wait_time += 0.1
    
    elapsed = time.time() - start_time
    logger.info(f"回放完成，耗时 {elapsed:.2f}秒")
    
    # 验证
    logger.info(f"结果统计:")
    logger.info(f"  - FrameResults: {len(frames_received)}")
    logger.info(f"  - Raw data: {len(raw_received)}")
    logger.info(f"  - Events: {len(events_received)}")
    logger.info(f"  - Progress updates: {len(progress_received)}")
    
    assert len(frames_received) > 0, "没有接收到FrameResults"
    assert len(raw_received) > 0, "没有接收到原始数据"
    assert len(progress_received) > 0, "没有进度更新"
    
    # 验证回放完成度
    if progress_received:
        last_progress = progress_received[-1]
        logger.info(f"最后进度: {last_progress:.3f}")
    
    logger.info("✓ 步骤5: 回放测试完成")
    
    # 清理
    analysis_cache.close()
    raw_cache.close()
    logger.info("测试4完成 ✓")
    return True


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始完整集成测试")
    logger.info("=" * 80)
    
    tests = [
        ("AnalysisResultCache 基础功能", test_1_analysis_result_cache),
        ("DataBridge 缓存功能", test_2_data_bridge_caching),
        ("MultiSourceReplayController 快速回放", test_3_replay_controller_fast_mode),
        ("完整流程测试", test_4_full_pipeline),
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
