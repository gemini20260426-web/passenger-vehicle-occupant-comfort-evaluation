#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据处理模块
提供数据读取、处理、存储等功能
"""

# 数据处理模块初始化文件

from .data_parser import IMUDataParser

try:
    from .cnap_parser import CNAPDataParser
except ImportError:
    CNAPDataParser = None

from .cardiovascular_parser import CardiovascularDataParser
from .data_reader import FileDataReader
from ..storage.data_storage import DataStorage
from ..analysis.base_analyzer import BasicDrivingAnalyzer
from .buffer_manager import BufferManager
from .data_processing_pipeline import DataProcessingPipeline
# from .data_source_manager import DataSourceManager  # 已删除，使用unified_data_source_manager替代
from .proto_serial_reader import ProtoSerialDataReader
from .influxdb_data_reader import InfluxDBDataReader
from .evaluation_data_manager import EvaluationDataManager
from .parser_manager import ParserManager, get_parser_manager, reset_parser_manager
from .parser_manager import smart_generate_parser, preview_parsed_features, smart_generate_parser_with_fields
from .signal_filter import (
    SignalFilter, FilterPipeline, FilterConfig, FilterType,
    get_signal_filter, reset_all_filters
)

__all__ = [
    'IMUDataParser',
    'CNAPDataParser',
    'CardiovascularDataParser',
    'FileDataReader', 
    'DataStorage',
    'BasicDrivingAnalyzer',
    'BufferManager',
    'DataProcessingPipeline',
    'ProtoSerialDataReader',
    'InfluxDBDataReader',
    'EvaluationDataManager',
    'ParserManager',
    'get_parser_manager',
    'reset_parser_manager',
    'smart_generate_parser',
    'preview_parsed_features',
    'smart_generate_parser_with_fields',
    'SignalFilter',
    'FilterPipeline',
    'FilterConfig',
    'FilterType',
    'get_signal_filter',
    'reset_all_filters',
]