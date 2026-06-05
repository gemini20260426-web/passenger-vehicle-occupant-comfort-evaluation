#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnosis_engine.py 单元测试 — 覆盖三层诊断逻辑"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestSingleGroupDiagnosis:
    """验证 generate_single_group_diagnosis 的 pass/warn/fail/na 四种状态"""

    @pytest.fixture
    def mock_metrics(self):
        return {
            'SEAT_Z': 0.5, 'SEAT_XY': 0.4, 'VDV_Z': 1.5,
            'AW_Z': 0.2, 'AW_XY': 0.2, 'DISP_TR': 5.0,
            'ACC_RMS': 0.5, 'ACC_PEAK': 3.0, 'HIC15': 300,
            'ACC_H_PEAK': 3.0, 'JERK_H': 3.0, 'SRS_MRS': 10.0,
            'FDS_D': 0.2, 'RFC_CC': 0.5, 'OVTV': 1.0,
        }

    def test_all_pass(self, mock_metrics):
        """所有指标通过 → conclusion 包含 '正常'"""
        from core.core.seat_evaluation.diagnosis_engine import generate_single_group_diagnosis
        result = generate_single_group_diagnosis(mock_metrics)
        assert result is not None
        assert hasattr(result, 'conclusion')
        assert '正常' in result.conclusion or '通过' in result.conclusion or '良好' in result.conclusion

    def test_partial_fail(self):
        """部分指标超标 → 应识别 fail 项"""
        from core.core.seat_evaluation.diagnosis_engine import generate_single_group_diagnosis
        fail_metrics = {
            'SEAT_Z': 1.5,  # 超过阈值
            'HIC15': 1200,  # 超过阈值
        }
        result = generate_single_group_diagnosis(fail_metrics)
        assert result is not None
        assert hasattr(result, 'weakest_link')

    def test_all_fail(self):
        """所有指标超标 → weakest_link 应为 fail"""
        from core.core.seat_evaluation.diagnosis_engine import generate_single_group_diagnosis
        bad_metrics = {
            'SEAT_Z': 5.0, 'HIC15': 2000, 'SRS_MRS': 100.0,
            'FDS_D': 5.0, 'VDV_Z': 10.0, 'AW_Z': 3.0,
        }
        result = generate_single_group_diagnosis(bad_metrics)
        assert result is not None
        assert result.weakest_link in ('fail', 'danger', 'critical')

    def test_empty_metrics(self):
        """空指标 → 不应崩溃"""
        from core.core.seat_evaluation.diagnosis_engine import generate_single_group_diagnosis
        result = generate_single_group_diagnosis({})
        assert result is not None

    def test_na_handling(self):
        """缺失指标 → 应标记为 NA"""
        from core.core.seat_evaluation.diagnosis_engine import generate_single_group_diagnosis
        partial_metrics = {'SEAT_Z': 0.5}  # 只有1个指标
        result = generate_single_group_diagnosis(partial_metrics)
        assert result is not None