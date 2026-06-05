#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metric_computer.py 单元测试 — 覆盖26个指标的路由正确性"""

import numpy as np
import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.core.seat_evaluation.metric_computer import (
    MetricComputer, MetricComputeContext, verify_all_metrics_registered
)


class TestMetricComputerRouting:
    """验证 compute() 对所有指标的路由正确性"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ops = MagicMock()
        self.computer = MetricComputer(self.ops)
        self.ctx = MetricComputeContext(
            ax=np.random.randn(200),
            ay=np.random.randn(200),
            az=np.random.randn(200),
            sample_rate=100.0
        )

    @pytest.mark.parametrize("metric_id", [
        # 17个直接注册的
        "SEAT_Z", "SEAT_XY", "VDV_Z", "TR_Z", "AW_Z", "AW_XY",
        "OVTV", "R_FACTOR", "HIC15", "S_D", "ACC_H_PEAK", "JERK_H",
        "RFC_CC", "ACC_RMS", "ACC_PEAK", "DISP_TR", "DISP_HR",
        # 9个SRS/FDS/STFT子指标
        "SRS_MRS", "SRS_Q", "SRS_PV", "SRS_ATT",
        "FDS_D", "FDS_R", "STFT_FC", "STFT_KT", "STFT_CE",
    ])
    def test_all_indicators_routable(self, metric_id):
        """所有26个指标均可通过compute()调用"""
        try:
            result = self.computer.compute(metric_id, self.ctx)
            assert isinstance(result, (int, float))
        except ValueError as e:
            pytest.fail(f"compute('{metric_id}') 抛出异常: {e}")

    def test_unknown_metric_raises(self):
        """未注册指标应抛出异常而非返回0"""
        with pytest.raises(ValueError, match="未知指标"):
            self.computer.compute("NONEXISTENT", self.ctx)

    def test_insufficient_data_returns_negative_one(self):
        """数据不足时返回 -1.0"""
        ctx_short = MetricComputeContext(
            ax=np.array([1.0, 2.0]),
            ay=np.array([1.0, 2.0]),
            az=np.array([1.0, 2.0]),
            sample_rate=100.0
        )
        result = self.computer.compute("SEAT_Z", ctx_short)
        assert result == -1.0


class TestMetricVerification:
    """验证指标完整性"""

    def test_verify_all_metrics_registered(self):
        """所有metadata定义的指标均已注册"""
        assert verify_all_metrics_registered(), "存在未注册的指标！"