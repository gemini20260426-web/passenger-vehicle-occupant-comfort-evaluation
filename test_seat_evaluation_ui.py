#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测UI组件测试
"""

import os
import sys
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


def test_1_seat_evaluation_tab_import():
    """测试1: 导入座椅评测标签页"""
    logger.info("=" * 80)
    logger.info("测试1: 导入座椅评测标签页")
    logger.info("=" * 80)
    
    try:
        from modules.ui.seat_evaluation import SeatEvaluationTab
        logger.info("✓ SeatEvaluationTab 导入成功")
        
        from modules.ui.seat_evaluation import ComparativeEvaluationTab
        logger.info("✓ ComparativeEvaluationTab 导入成功")
        
        from modules.ui.seat_evaluation import IndicatorConfigDialog
        logger.info("✓ IndicatorConfigDialog 导入成功")
        
        from modules.ui.seat_evaluation import ResultVisualizationDialog
        logger.info("✓ ResultVisualizationDialog 导入成功")
        
        logger.info("测试1完成 ✓")
        return True
    except Exception as e:
        logger.error(f"导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_seat_evaluation_tab_creation():
    """测试2: 创建座椅评测标签页"""
    logger.info("=" * 80)
    logger.info("测试2: 创建座椅评测标签页")
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
        assert tab is not None, "创建座椅评测标签页失败"
        logger.info("✓ 座椅评测标签页创建成功")
        
        # 检查基本属性
        assert hasattr(tab, 'evaluation_requested'), "缺少evaluation_requested信号"
        assert hasattr(tab, 'export_requested'), "缺少export_requested信号"
        assert hasattr(tab, 'refresh_requested'), "缺少refresh_requested信号"
        logger.info("✓ 基本属性检查通过")
        
        logger.info("测试2完成 ✓")
        return True
    except Exception as e:
        logger.error(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_comparative_evaluation_tab_creation():
    """测试3: 创建对照分析标签页"""
    logger.info("=" * 80)
    logger.info("测试3: 创建对照分析标签页")
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
        assert tab is not None, "创建对照分析标签页失败"
        logger.info("✓ 对照分析标签页创建成功")
        
        # 检查基本属性
        assert hasattr(tab, 'comparison_requested'), "缺少comparison_requested信号"
        assert hasattr(tab, 'export_report_requested'), "缺少export_report_requested信号"
        logger.info("✓ 基本属性检查通过")
        
        logger.info("测试3完成 ✓")
        return True
    except Exception as e:
        logger.error(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_indicator_config_dialog_creation():
    """测试4: 创建指标配置对话框"""
    logger.info("=" * 80)
    logger.info("测试4: 创建指标配置对话框")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.seat_evaluation import IndicatorConfigDialog
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建对话框
        dialog = IndicatorConfigDialog()
        assert dialog is not None, "创建指标配置对话框失败"
        logger.info("✓ 指标配置对话框创建成功")
        
        # 检查基本属性
        assert hasattr(dialog, 'config_saved'), "缺少config_saved信号"
        logger.info("✓ 基本属性检查通过")
        
        logger.info("测试4完成 ✓")
        return True
    except Exception as e:
        logger.error(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_result_visualization_dialog_creation():
    """测试5: 创建结果可视化对话框"""
    logger.info("=" * 80)
    logger.info("测试5: 创建结果可视化对话框")
    logger.info("=" * 80)
    
    try:
        from PySide6.QtWidgets import QApplication
        from modules.ui.seat_evaluation import ResultVisualizationDialog
        
        # 创建QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建测试数据
        test_result = {
            'timestamp': datetime.now().timestamp(),
            'event_type': '急刹车',
            'overall_score': 85.5,
            'risk_level': 'LOW',
            'duration': 30.0,
            'metrics': {
                'longitudinal_jerk': {
                    'name': '纵向冲击',
                    'score': 90.0,
                    'weight': 15.0,
                    'level': 'GOOD',
                    'description': '纵向加速度变化率'
                },
                'lateral_acceleration': {
                    'name': '横向加速度',
                    'score': 82.0,
                    'weight': 15.0,
                    'level': 'NORMAL',
                    'description': '横向加速度最大值'
                }
            },
            'risk_factors': ['急刹车力度较大'],
            'statistics': {
                'max_ax': -5.2,
                'max_ay': 2.1,
                'avg_speed': 30.5
            }
        }
        
        # 创建对话框
        dialog = ResultVisualizationDialog(test_result)
        assert dialog is not None, "创建结果可视化对话框失败"
        logger.info("✓ 结果可视化对话框创建成功")
        
        logger.info("测试5完成 ✓")
        return True
    except Exception as e:
        logger.error(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_module_structure():
    """测试6: 模块结构检查"""
    logger.info("=" * 80)
    logger.info("测试6: 模块结构检查")
    logger.info("=" * 80)
    
    try:
        # 检查目录结构
        ui_dir = project_root / 'modules' / 'ui' / 'seat_evaluation'
        assert ui_dir.exists(), f"目录不存在: {ui_dir}"
        logger.info("✓ 目录结构检查通过")
        
        # 检查必要文件
        required_files = [
            '__init__.py',
            'seat_evaluation_tab.py',
            'comparative_evaluation_tab.py',
            'indicator_config_dialog.py',
            'result_visualization_dialog.py'
        ]
        
        for file_name in required_files:
            file_path = ui_dir / file_name
            assert file_path.exists(), f"文件不存在: {file_path}"
            logger.info(f"✓ 文件存在: {file_name}")
        
        logger.info("测试6完成 ✓")
        return True
    except Exception as e:
        logger.error(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("开始座椅评测UI组件测试")
    logger.info("=" * 80)
    
    tests = [
        test_1_seat_evaluation_tab_import,
        test_2_seat_evaluation_tab_creation,
        test_3_comparative_evaluation_tab_creation,
        test_4_indicator_config_dialog_creation,
        test_5_result_visualization_dialog_creation,
        test_6_module_structure
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
    logger.info("测试总结")
    logger.info("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    logger.info(f"总测试数: {total}")
    logger.info(f"通过: {passed}")
    logger.info(f"失败: {total - passed}")
    
    if all(results):
        logger.info("✓ 所有测试通过 ✓")
        return True
    else:
        logger.error("✗ 部分测试失败")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
