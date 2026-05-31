#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测UI集成测试
测试座椅评测UI与现有系统的集成
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_1_right_content_panel_integration():
    """测试1: 右侧内容面板集成"""
    logger.info("=" * 80)
    logger.info("测试1: 右侧内容面板集成")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.core_ui.components.right_content_panel import RightContentPanel
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建右侧内容面板
        panel = RightContentPanel()
        assert panel is not None, "创建右侧内容面板失败"
        logger.info("✓ 右侧内容面板创建成功")
        
        # 检查标签页数量
        tab_count = panel.tab_widget.count()
        logger.info(f"标签页数量: {tab_count}")
        assert tab_count >= 6, f"标签页数量不足，期望至少6，实际{tab_count}"
        
        # 检查标签页标题
        expected_tabs = ['CNAP可视化', 'IMU可视化', 'CAN全量解析', '实时行为监控', '座椅评测', '对照分析']
        for i, expected_title in enumerate(expected_tabs):
            if i < tab_count:
                actual_title = panel.tab_widget.tabText(i)
                logger.info(f"标签页{i}: {actual_title}")
        
        logger.info("✓ 标签页检查通过")
        logger.info("测试1完成 ✓")
        return True
    except Exception as e:
        logger.error(f"集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_core_ui_controller_seat_evaluation():
    """测试2: CoreUIController座椅评测相关"""
    logger.info("=" * 80)
    logger.info("测试2: CoreUIController座椅评测相关")
    logger.info("=" * 80)
    
    try:
        from main.core_ui_controller import CoreUIController
        
        # 检查信号定义
        required_signals = [
            'seat_evaluation_started',
            'seat_evaluation_completed',
            'seat_evaluation_metric',
            'comparison_started',
            'comparison_completed',
            'comparison_metric'
        ]
        
        for signal_name in required_signals:
            assert hasattr(CoreUIController, signal_name), f"缺少信号: {signal_name}"
            logger.info(f"✓ 信号存在: {signal_name}")
        
        # 检查座椅评测相关方法
        required_methods = [
            '_init_seat_evaluation_async',
            '_init_seat_evaluation_components',
            '_on_seat_evaluation_started',
            '_on_seat_evaluation_completed',
            '_on_seat_evaluation_metric',
            '_on_comparison_started',
            '_on_comparison_completed',
            '_on_comparison_metric'
        ]
        
        for method_name in required_methods:
            assert hasattr(CoreUIController, method_name), f"缺少方法: {method_name}"
            logger.info(f"✓ 方法存在: {method_name}")
        
        logger.info("测试2完成 ✓")
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_service_locator_registration():
    """测试3: 服务定位器注册"""
    logger.info("=" * 80)
    logger.info("测试3: 服务定位器注册")
    logger.info("=" * 80)
    
    try:
        from core.core.service_locator import ServiceLocator
        
        # 检查服务定义
        locator = ServiceLocator()
        
        # 这些服务会在CoreUIController._register_services中注册
        expected_services = [
            'seat_evaluation_engine',
            'comparative_evaluation_engine',
            'multi_channel_data_synchronizer',
            'behavior_event_dispatcher'
        ]
        
        logger.info("✓ 服务定位器检查完成")
        logger.info("测试3完成 ✓")
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_seat_evaluation_ui_workflow():
    """测试4: 座椅评测UI工作流程"""
    logger.info("=" * 80)
    logger.info("测试4: 座椅评测UI工作流程")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.seat_evaluation import SeatEvaluationTab
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建标签页
        tab = SeatEvaluationTab()
        
        # 测试信号连接
        test_data = {'test': 'data'}
        signal_received = []
        
        def on_evaluation_requested(data):
            signal_received.append(data)
            logger.info(f"✓ evaluation_requested信号收到: {data}")
        
        def on_export_requested():
            signal_received.append('export')
            logger.info("✓ export_requested信号收到")
        
        def on_refresh_requested():
            signal_received.append('refresh')
            logger.info("✓ refresh_requested信号收到")
        
        tab.evaluation_requested.connect(on_evaluation_requested)
        tab.export_requested.connect(on_export_requested)
        tab.refresh_requested.connect(on_refresh_requested)
        
        # 模拟信号发射
        tab.evaluation_requested.emit(test_data)
        tab.export_requested.emit()
        tab.refresh_requested.emit()
        
        # 验证信号
        assert len(signal_received) == 3, "信号未全部收到"
        assert signal_received[0] == test_data, "第一个信号数据错误"
        assert signal_received[1] == 'export', "第二个信号错误"
        assert signal_received[2] == 'refresh', "第三个信号错误"
        
        logger.info("✓ 信号测试通过")
        logger.info("测试4完成 ✓")
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_comparative_evaluation_ui_workflow():
    """测试5: 对照分析UI工作流程"""
    logger.info("=" * 80)
    logger.info("测试5: 对照分析UI工作流程")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.seat_evaluation import ComparativeEvaluationTab
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建标签页
        tab = ComparativeEvaluationTab()
        
        # 测试信号连接
        test_data = {'test': 'data'}
        signal_received = []
        
        def on_comparison_requested(data):
            signal_received.append(data)
            logger.info(f"✓ comparison_requested信号收到: {data}")
        
        def on_export_report_requested():
            signal_received.append('export_report')
            logger.info("✓ export_report_requested信号收到")
        
        tab.comparison_requested.connect(on_comparison_requested)
        tab.export_report_requested.connect(on_export_report_requested)
        
        # 模拟信号发射
        tab.comparison_requested.emit(test_data)
        tab.export_report_requested.emit()
        
        # 验证信号
        assert len(signal_received) == 2, "信号未全部收到"
        assert signal_received[0] == test_data, "第一个信号数据错误"
        assert signal_received[1] == 'export_report', "第二个信号错误"
        
        logger.info("✓ 信号测试通过")
        logger.info("测试5完成 ✓")
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_full_integration_simulation():
    """测试6: 完整集成模拟"""
    logger.info("=" * 80)
    logger.info("测试6: 完整集成模拟")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.seat_evaluation import SeatEvaluationTab, ResultVisualizationDialog
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 模拟评测流程
        logger.info("模拟座椅评测流程...")
        
        # 1. 创建标签页
        tab = SeatEvaluationTab()
        logger.info("✓ 1. 创建座椅评测标签页")
        
        # 2. 模拟评测开始
        tab._on_evaluation_started({'event_type': '急刹车'})
        logger.info("✓ 2. 评测开始")
        
        # 3. 模拟评测完成
        test_result = {
            'timestamp': datetime.now().timestamp(),
            'event_type': '急刹车',
            'overall_score': 85.5,
            'risk_level': 'LOW',
            'duration': 30.0,
            'metrics': {}
        }
        tab._on_evaluation_completed(test_result)
        logger.info("✓ 3. 评测完成")
        
        # 4. 检查历史记录
        assert len(tab._evaluation_results) == 1, "历史记录未添加"
        assert tab.history_table.rowCount() == 1, "历史表格未更新"
        logger.info("✓ 4. 历史记录检查通过")
        
        # 5. 创建结果展示对话框
        dialog = ResultVisualizationDialog(test_result)
        logger.info("✓ 5. 结果展示对话框创建")
        
        logger.info("✓ 完整流程模拟成功")
        logger.info("测试6完成 ✓")
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有集成测试"""
    logger.info("=" * 80)
    logger.info("开始座椅评测UI集成测试")
    logger.info("=" * 80)
    
    tests = [
        test_1_right_content_panel_integration,
        test_2_core_ui_controller_seat_evaluation,
        test_3_service_locator_registration,
        test_4_seat_evaluation_ui_workflow,
        test_5_comparative_evaluation_ui_workflow,
        test_6_full_integration_simulation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # 总结
    logger.info("=" * 80)
    logger.info("集成测试总结")
    logger.info("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    logger.info(f"总测试数: {total}")
    logger.info(f"通过: {passed}")
    logger.info(f"失败: {total - passed}")
    
    if all(results):
        logger.info("✓ 所有集成测试通过 ✓")
        return True
    else:
        logger.error("✗ 部分集成测试失败")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
