#!/usr/bin/env python3
"""Test expert evaluation"""
import sys; sys.path.insert(0, '.')
from core.core.seat_evaluation.full_timeseries_evaluator import FullTimeseriesEvaluator
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
import traceback

e = FullTimeseriesEvaluator()
try:
    e.load_from_csv(r'test_data\验证数据\parsed_data_20260521_135117.csv')
    print('Step 1: Data loaded OK')
    e.detect_events()
    print(f'Step 2: Events detected: {len(e.events)}')
    e.window_analysis()
    wlen = len(e.results.get('windows', []))
    print(f'Step 3: Window analysis: {wlen} rows')
    e.event_analysis()
    print(f'Step 4: Event analysis OK')
    e.spectrum_analysis()
    print(f'Step 5: Spectrum analysis OK')
    e.stft_analysis()
    print(f'Step 6: STFT analysis OK')
    e.statistical_analysis()
    print(f'Step 7: Statistical analysis OK')
    e.comprehensive_metrics()
    print(f'Step 8: Comprehensive metrics OK')
    e.generate_report('test_output')
    print('Step 9: Report generated OK')
    print('ALL STEPS PASSED!')
except Exception as ex:
    traceback.print_exc()
    print(f'ERROR: {ex}')