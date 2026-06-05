#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluation_report 模块

全量统计分析模块的UI组件:
- MetricStore: 指标缓存与发布中心
- MetricDashboard: 指标仪表盘 (U1)
- ComparisonView: 对照分析对比视图 (U2)
- BandRadarChart: 频段衰减雷达图 (U3)
- EventTimeline: 事件时间线 (U4)
- ReportExporter: 诊断报告一键导出 (U5)
- MetricFilterTree: 指标筛选器 (U6)
- ConfidenceVisualizer: 置信度可视化 (U7)
- SpinePathDiagram: 脊柱传递路径图 (U8)
- HistoryComparison: 历史对比模式 (U9)
- StreamMonitor: 实时数据流监控 (U10)
- TemplateRenderer: 报告模板化 (R1)
- I18nManager: 多语言支持 (R3)
- ReportVersionManager: 版本管理 (R4)
"""

from .metric_store import MetricStore, MetricSnapshot
from .metric_dashboard import MetricDashboard, TrendMiniChart, RiskIndicator
from .comparison_view import ComparisonView, HeatmapWidget
from .band_radar_chart import BandRadarChart
from .event_timeline import EventTimeline, TimelineCanvas, TimelineEvent
from .report_exporter import ReportExporter
from .metric_filter import MetricFilterTree
from .advanced_widgets import (
    ConfidenceVisualizer, ConfidenceBar,
    SpinePathDiagram,
    HistoryComparison, ComparisonRow,
    StreamMonitor, StreamCanvas
)
from .report_enhancements import (
    TemplateRenderer, I18nManager, ReportVersionManager, ReportVersion,
    TRANSLATIONS
)
from .report_manager import ReportManagerWidget
from .report_widget import EvaluationReportWidget
from .report_scheduler import ReportScheduler, ReportGeneratorThread
from .system_status import SystemStatusWidget
from .prediction_visualization import PredictionVisualizationWidget

__all__ = [
    'MetricStore', 'MetricSnapshot',
    'MetricDashboard', 'TrendMiniChart', 'RiskIndicator',
    'ComparisonView', 'HeatmapWidget',
    'BandRadarChart',
    'EventTimeline', 'TimelineCanvas', 'TimelineEvent',
    'ReportExporter',
    'MetricFilterTree',
    'ConfidenceVisualizer', 'ConfidenceBar',
    'SpinePathDiagram',
    'HistoryComparison', 'ComparisonRow',
    'StreamMonitor', 'StreamCanvas',
    'TemplateRenderer', 'I18nManager', 'ReportVersionManager', 'ReportVersion',
    'TRANSLATIONS',
    'ReportManagerWidget', 'EvaluationReportWidget',
    'ReportScheduler', 'ReportGeneratorThread', 'SystemStatusWidget', 'PredictionVisualizationWidget',
]