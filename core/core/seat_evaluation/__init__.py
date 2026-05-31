#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测系统模块
基于 ISO 2631-1 / SAE J211 / ASTM E1049 / MIL-STD-810H 标准
"""

from .engine import SeatEvaluationEngine
from .engine_v2 import MultiChannelSeatEvaluationEngine
from .comparative_engine import ComparativeEvaluationEngine
from .comparative_engine_v2 import MultiChannelComparativeEngine
from .operators import OperatorSystem
from .data_sync import MultiChannelDataSynchronizer, TimeAligner
from .report_generator import SeatEvaluationReportGenerator
from .comparative_analyzer import ComparativeAnalyzer
from .evaluation_rules import EvaluationRulesEngine, EvaluationRule
from .imu_location_config import (
    IMU_LOCATION_MAPPING, LOCATION_IDS,
    get_location_config, get_metrics_for_location,
    get_channel_by_location,
)

__all__ = [
    'SeatEvaluationEngine',
    'MultiChannelSeatEvaluationEngine',
    'ComparativeEvaluationEngine',
    'MultiChannelComparativeEngine',
    'OperatorSystem',
    'MultiChannelDataSynchronizer',
    'TimeAligner',
    'SeatEvaluationReportGenerator',
    'ComparativeAnalyzer',
    'EvaluationRulesEngine',
    'EvaluationRule',
    'IMU_LOCATION_MAPPING',
    'LOCATION_IDS',
    'get_location_config',
    'get_metrics_for_location',
    'get_channel_by_location',
]