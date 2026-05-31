# -*- coding: utf-8 -*-
"""
UI模块初始化文件
"""

# 移除不存在的模块导入，避免启动错误
try:
    from .behavior_analysis_widget import BehaviorAnalysisWidget
except ImportError:
    BehaviorAnalysisWidget = None

try:
    from .visualization_widget import VisualizationWidget
except ImportError:
    VisualizationWidget = None

try:
    from .comprehensive_monitoring_widget import ComprehensiveMonitoringWidget
except ImportError:
    ComprehensiveMonitoringWidget = None

try:
    from .fused_analysis_widget import FusedAnalysisWidget
except ImportError:
    FusedAnalysisWidget = None

try:
    from .cardiovascular_widget import CardiovascularWidget
except ImportError:
    CardiovascularWidget = None

try:
    from .cnap_visualization import CNAPVisualizationWidget
except ImportError:
    CNAPVisualizationWidget = None

__all__ = [
    'BehaviorAnalysisWidget',
    'VisualizationWidget',
    'ComprehensiveMonitoringWidget',
    'FusedAnalysisWidget',
    'CardiovascularWidget',
    'CNAPVisualizationWidget'
]