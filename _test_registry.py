#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
from core.core.seat_evaluation.metadata_registry import (
    get_global_registry, METRIC_THRESHOLDS, DIAGNOSIS_THRESHOLDS,
    DataSourceDef, DrivingStateDef, RawFieldDef, OperatorDef,
    EvaluationModuleDef, RiskCategory, DataSourceType, EvaluationDirection,
    FIXED_PARAMETERS
)

print('=== Registry Statistics ===')
reg = get_global_registry()
print(f'Indicators: {len(reg.indicators)}')
print(f'Thresholds 4-level: {len(reg.metric_thresholds_4level)}')
print(f'Diagnosis thresholds: {len(reg.diagnosis_thresholds)}')
print(f'Data sources: {len(reg.data_sources)}')
print(f'Driving states: {len(reg.driving_states)}')
print(f'Raw fields: {len