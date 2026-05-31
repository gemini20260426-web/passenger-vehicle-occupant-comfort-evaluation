#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段2测试：验证 DataBridge 缓存功能
"""

import sys
import os
import logging
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.analysis.data_bridge import DataBridge
from core.analysis.core_types import FrameResult, DrivingState, RiskLevel, BehaviorCategory, ManeuverEvent, RiskReport, FrameFeatures


def create_test_data():
    """创建测试数据"""
    test_records = []
    for i in range(20):
        record = {
            'timestamp': i * 0.1,
            'ax': 0.1 + i * 0.01,
            'ay': 0.01,
            'az': 9.8,
            'gx': 0.0,
            'gy': 0.0,
            'gz': 0.0,
            'speed': 10.0 + i,
            'wheel': 0.0,
            '_source_type': 'imu_standalone'
        }
        test_records.append(record)
    return test_records


def test_data_bridge_caching():
    """测试 DataBridge 缓存功能"""
    logger.info("=" * 60)
    logger.info("测试：DataBridge 缓存功能")
    logger.info("=" * 60)
    
    # 创建 DataBridge
    data_bridge = DataBridge()
    
    # 启用缓存
    logger.info("启用分析结果缓存...")
    data_bridge.enable_result_caching(":memory:")
    
    # 启动处理
    data_bridge.start_processing()
    
    # 喂入测试数据
    test_records = create_test_data()
    logger.info(f"喂入 {len(test_records)} 条测试数据...")
    
    for record in test_records:
        data_bridge.feed_parsed_data(record)
        time.sleep(0.001)  # 给一些处理时间
    
    # 等待处理完成
    time.sleep(0.5)
    
    # 在停止前获取缓存引用
    cache = data_bridge.get_analysis_cache()
    assert cache is not None, "缓存不应为 None"
    
    # 检查统计
    stats = cache.get_stats()
    logger.info(f"缓存统计: {stats}")
    
    # 查询缓存数据
    t_min, t_max = cache.get_time_range()
    logger.info(f"时间范围: {t_min} ~ {t_max}")
    
    results = cache.query_time_range(t_min, t_max)
    logger.info(f"✓ 成功查询 {len(results)} 条记录")
    
    # 停止处理
    data_bridge.stop_processing()
    
    # 验证数据完整性
    for fr in results:
        assert hasattr(fr, 'timestamp'), "FrameResult 应该有 timestamp"
        assert hasattr(fr, 'state'), "FrameResult 应该有 state"
        assert hasattr(fr, 'speed'), "FrameResult 应该有 speed"
    
    logger.info("✓ FrameResult 数据完整性验证通过")
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 DataBridge 缓存功能测试通过！")
    logger.info("=" * 60)
    
    return 0


def main():
    try:
        return test_data_bridge_caching()
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
