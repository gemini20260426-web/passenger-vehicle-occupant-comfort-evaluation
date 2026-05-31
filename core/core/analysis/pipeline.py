#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五层分析管道编排器
"""

import time
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from collections import deque

from .core_types import (
    ProcessedFrame, FrameFeatures, FrameResult,
    ManeuverEvent, RiskReport, DrivingState,
    VehicleConfig, BehaviorCategory, RiskLevel,
)
from .layer0_preprocessing.speed_preprocessor import SpeedPreprocessor
from .layer1_signal_processing.signal_processor import SignalProcessor
from .layer2_feature_engineering.feature_extractor import FeatureExtractor
from .layer3_maneuver_segmentation.driving_state_machine import DrivingStateMachine
from .layer3_maneuver_segmentation.maneuver_detector import ManeuverDetector
from .layer3_maneuver_segmentation.event_detector import DrivingEventDetector
from .layer3_maneuver_segmentation.temporal_consistency import TemporalConsistencyValidator
from .layer4_behavior_classification.hybrid_classifier import HybridBehaviorClassifier
from .layer5_risk_assessment.risk_assessor import RiskAssessor


class AnalysisPipeline:
    # 驾驶行为分析主IMU通道（硬约束，与DataBridge.PRIMARY_IMU_NAME保持一致）
    # 状态机和事件生成必须且仅使用此通道数据
    PRIMARY_IMU_NAME = 'IMU7_座椅底部-1'

    def __init__(self, vehicle_config: Optional[VehicleConfig] = None, primary_imu_name: str = None):
        self._logger = logging.getLogger(__name__)

        if isinstance(vehicle_config, dict):
            vehicle_config = VehicleConfig()
        self._vehicle_config = vehicle_config or VehicleConfig()

        self.PRIMARY_IMU_NAME = primary_imu_name or AnalysisPipeline.PRIMARY_IMU_NAME

        self._signal_processor = SignalProcessor(self._vehicle_config)
        self._feature_extractor = FeatureExtractor(self._vehicle_config)
        self._state_machine = DrivingStateMachine()
        self._maneuver_detector = ManeuverDetector()
        self._speed_preprocessor = SpeedPreprocessor()
        self._event_detector = DrivingEventDetector()
        self._temporal_validator = TemporalConsistencyValidator()
        self._classifier = HybridBehaviorClassifier()
        self._risk_assessor = RiskAssessor(self._vehicle_config)

        self._frame_count = 0
        self._last_result = None
        self._recent_events = deque(maxlen=200)
        self._is_streaming = False
        self._stream_start_time = 0.0
        self._processed_count = 0

        # ── 流式效率优化 ──
        # 降采样: 每 processing_interval 秒触发一次检测 (专家策略: 0.1s)
        self._processing_interval = 0.1
        self._last_process_time = -1.0

        # 环形缓冲区: pre-allocated numpy, 替换 deque 避免 list→array 转换开销
        self._ring_max = 128  # 最近 128 帧 (~5s @ 25Hz after decimation)
        self._ring_t = np.full(self._ring_max, np.nan)
        self._ring_speed = np.full(self._ring_max, np.nan)
        self._ring_wheel = np.full(self._ring_max, np.nan)
        self._ring_accelexpert = np.full(self._ring_max, np.nan)
        self._ring_pos = 0
        self._ring_count = 0

        # 增量 VDV 累积 (ISO 2631-1)
        self._vdv_sum4 = 0.0
        self._peak_accel = 0.0

    def process_frame(self, raw_data: Dict[str, Any]) -> FrameResult:
        self._frame_count += 1
        self._processed_count += 1

        imu_name = raw_data.get('_source_name', '') or raw_data.get('_imu_name', '')
        if imu_name and imu_name != self.PRIMARY_IMU_NAME:
            if self._processed_count <= 3:
                self._logger.warning(
                    f"[PIPELINE] 拒绝非主IMU通道数据: {imu_name} (期望: {self.PRIMARY_IMU_NAME})"
                )
            return FrameResult(
                timestamp=raw_data.get('timestamp', 0),
                state=DrivingState.UNKNOWN,
                features=None,
                raw_data=raw_data,
            )

        frame = self._signal_processor.process(raw_data)

        # ── 在线 vehicle_accel 计算（流式优化版）──
        # 投递到环形缓冲区, 用 speed 梯度近似加速度 (与专家算法一致)
        ts = frame.timestamp
        speed_kmh = frame.speed  # 流式下保持 km/h
        wheel_deg = frame.wheel
        raw_data['vehicle_accel'] = 0.0

        if speed_kmh is not None and speed_kmh >= 0:
            idx = self._ring_pos
            self._ring_t[idx] = ts
            self._ring_speed[idx] = speed_kmh
            self._ring_wheel[idx] = wheel_deg
            self._ring_pos = (idx + 1) % self._ring_max
            self._ring_count = min(self._ring_count + 1, self._ring_max)

            # 专家级 vehicle_accel: diff(speed[-5:]) / dt / 3.6
            if self._ring_count >= 3:
                n = min(5, self._ring_count)
                valid = ~np.isnan(self._ring_speed)
                if valid.sum() >= 3:
                    speeds = self._ring_speed[valid][-n:]
                    times = self._ring_t[valid][-n:]
                    if len(speeds) >= 2 and times[-1] > times[-2]:
                        dt_actual = np.median(np.diff(times))
                        if dt_actual > 0:
                            dv = np.mean(np.diff(speeds))
                            accel_expert = dv / dt_actual / 3.6  # km/h/s → m/s²
                            self._ring_accelexpert[idx] = accel_expert
                            raw_data['vehicle_accel'] = float(accel_expert)

                            # 增量 VDV
                            self._vdv_sum4 += (abs(accel_expert) ** 4) * dt_actual
                            if abs(accel_expert) > self._peak_accel:
                                self._peak_accel = abs(accel_expert)

        # ── 下帧 ──
        last_ts = self._last_process_time
        self._last_process_time = ts
        should_process = (last_ts < 0 or (ts - last_ts) >= self._processing_interval)

        features = self._feature_extractor.extract(frame)
        state, state_changed, maneuver_ended = self._state_machine.update(frame, features)

        if self._processed_count <= 5 or state_changed or maneuver_ended:
            self._logger.debug(
                f"[PIPELINE] frame=#{self._processed_count} ts={frame.timestamp:.3f} "
                f"speed={frame.speed:.2f} ax={frame.ax:.3f} wheel={frame.wheel:.1f} "
                f"state={state.value} changed={state_changed} maneuver_ended={maneuver_ended}"
            )

        event = None
        if maneuver_ended:
            event = self._maneuver_detector.end_maneuver(frame)
            if event and self._temporal_validator.validate(event):
                event = self._classifier.classify(event, features)
                event = self._risk_assessor.assess(event, features)
                self._recent_events.append(event)
                self._logger.debug(
                    f"[PIPELINE] EVENT generated: type={event.type} "
                    f"start={event.start_time:.3f} end={event.end_time:.3f} "
                    f"duration={event.duration:.3f}s"
                )
            elif event:
                self._logger.debug(
                    f"[PIPELINE] EVENT rejected by temporal validator: "
                    f"duration={event.duration:.3f}s"
                )
            else:
                self._logger.debug(
                    f"[PIPELINE] EVENT rejected by maneuver detector: "
                    f"duration too short"
                )

        if state_changed and state not in (DrivingState.UNKNOWN, DrivingState.STOPPED):
            self._maneuver_detector.begin_maneuver(state, frame)

        self._maneuver_detector.update(frame, features)

        result = FrameResult(
            timestamp=frame.timestamp,
            state=state,
            features=features,
            event=event,
            raw_data=raw_data,
            ax=frame.ax,
            ay=frame.ay,
            az=frame.az,
            gx=frame.gx,
            gy=frame.gy,
            gz=frame.gz,
            speed=frame.speed,
            wheel=frame.wheel,
            loc1=frame.loc1,
            loc2=frame.loc2,
            quality=frame.quality,
        )
        self._last_result = result
        return result

    def process_batch(self, batch: List[Dict[str, Any]]) -> List[FrameResult]:
        results = []
        for data in batch:
            result = self.process_frame(data)
            results.append(result)
        return results

    def start_streaming(self):
        self._is_streaming = True
        self._stream_start_time = time.time()
        self._processed_count = 0

    def stop_streaming(self):
        self._is_streaming = False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "is_streaming": self._is_streaming,
            "stream_start_time": self._stream_start_time,
            "processed_count": self._processed_count,
            "frame_count": self._frame_count,
            "recent_events_count": len(self._recent_events),
            "current_state": self._state_machine.current_state.value,
            # 流式效率指标
            "stream_fps": self._processed_count / max(1, time.time() - self._stream_start_time) if self._is_streaming else 0,
            "processing_interval_s": self._processing_interval,
            "buffer_usage": min(self._ring_count, self._ring_max),
            "vdv_cumulative": round(self._vdv_sum4 ** 0.25, 3) if self._vdv_sum4 > 0 else 0.0,
            "peak_accel": round(self._peak_accel, 3),
        }

    def get_recent_events(self, count: int = 10) -> List[ManeuverEvent]:
        items = list(self._recent_events)
        return items[-count:]

    def _get_ring_slice(self):
        """获取环形缓冲区有效数据的连续视图 (按时间排序)"""
        n = min(self._ring_count, self._ring_max)
        pos = self._ring_pos
        if n < self._ring_max:
            sl = slice(0, n)
        else:
            # 环绕情况: 拼接 [pos:] + [:pos]
            return (
                np.concatenate([self._ring_t[pos:], self._ring_t[:pos]]),
                np.concatenate([self._ring_speed[pos:], self._ring_speed[:pos]]),
                np.concatenate([self._ring_wheel[pos:], self._ring_wheel[:pos]]),
                np.concatenate([self._ring_accelexpert[pos:], self._ring_accelexpert[:pos]]),
            )
        return (
            self._ring_t[sl], self._ring_speed[sl],
            self._ring_wheel[sl], self._ring_accelexpert[sl],
        )

    @property
    def vdv_current(self) -> float:
        """当前累积 VDV 值"""
        return self._vdv_sum4 ** 0.25 if self._vdv_sum4 > 0 else 0.0

    @property
    def ring_speed_ma(self, window_s: float = 0.5) -> float:
        """环形缓冲区中最近 window_s 秒的平均速度"""
        t_arr, sp_arr, _, _ = self._get_ring_slice()
        if len(t_arr) == 0:
            return 0.0
        t_end = t_arr[-1]
        mask = (t_arr >= t_end - window_s)
        if mask.sum() < 2:
            return float(sp_arr[-1]) if len(sp_arr) > 0 else 0.0
        return float(np.mean(sp_arr[mask]))

    def reset(self):
        self._signal_processor.reset()
        self._feature_extractor.reset()
        self._state_machine.reset()
        self._maneuver_detector.reset()
        self._speed_preprocessor.reset()
        self._temporal_validator.reset()
        self._classifier.reset()
        self._risk_assessor.reset()
        self._frame_count = 0
        self._last_result = None
        self._recent_events.clear()
        self._is_streaming = False
        self._processed_count = 0
        self._last_process_time = -1.0
        self._ring_pos = 0
        self._ring_count = 0
        self._ring_t.fill(np.nan)
        self._ring_speed.fill(np.nan)
        self._ring_wheel.fill(np.nan)
        self._ring_accelexpert.fill(np.nan)
        self._vdv_sum4 = 0.0
        self._peak_accel = 0.0

    def process_batch_full(
        self,
        records: List[Dict[str, Any]],
        ref_channel: str = 'ch1',
        ref_imu: str = 'IMU1_头部眉心-1',
    ) -> Dict[str, Any]:
        """全量批量分析（离线模式）

        完整数据流:
          records → SpeedPreprocessor.enrich_all() → 每条追加 vehicle_accel 等
                 → process_frame() × N → 逐帧状态机 + 机动检测
                 → DrivingEventDetector.from_records() → 22种事件检测
                 → 汇总返回

        Args:
            records: 解析器输出的记录列表（含 speed/wheel/channel/imu_name 等）
            ref_channel: 事件检测参考通道
            ref_imu: 事件检测参考IMU

        Returns:
            {
                'events': List[Dict],           # 22种事件列表
                'event_summary': Dict,          # 按类型统计
                'frame_results': List[FrameResult],  # 逐帧结果
                'stats': Dict,                  # 管道统计
            }
        """
        from .core_types import Event as DetectedEvent  # noqa: F811

        self.reset()
        self.start_streaming()
        N = len(records)
        self._logger.info(f"[PIPELINE] process_batch_full: {N} records")

        # ── Layer0: 速度预处理（反量化 + Butterworth + 滚动统计）──
        enriched = self._speed_preprocessor.enrich_all(records)
        self._logger.info(
            f"[PIPELINE] Layer0 完成: vehicle_accel range=["
            f"{self._speed_preprocessor.vehicle_accel_array.min():.2f}, "
            f"{self._speed_preprocessor.vehicle_accel_array.max():.2f}] m/s²"
        )

        # ── Layer1-5: 逐帧分析 ──
        frame_results = []
        for i, rec in enumerate(enriched):
            # 只处理主IMU通道
            imu_name = rec.get('_imu_name', '') or rec.get('imu_name', '')
            channel = rec.get('_channel', '') or rec.get('channel', '')
            if imu_name and imu_name != self.PRIMARY_IMU_NAME:
                continue

            result = self.process_frame(rec)
            if result.event:
                evt = result.event
                self._logger.debug(
                    f"[PIPELINE] #{i} 事件: {evt.label_cn} "
                    f"t=[{evt.start_time:.2f}-{evt.end_time:.2f}]s "
                    f"dur={evt.duration:.2f}s"
                )
            frame_results.append(result)

        self.stop_streaming()
        self._logger.info(
            f"[PIPELINE] 逐帧分析完成: {len(frame_results)} 帧有效, "
            f"{len([r for r in frame_results if r.event])} 个FSM事件"
        )

        # ── 全量事件检测（6组22种） ──
        detector = DrivingEventDetector.from_records(enriched, ref_channel, ref_imu)
        detector_events = detector.detect_all()
        event_summary = detector.get_summary()

        self._logger.info(
            f"[PIPELINE] 全量事件检测完成: {event_summary['total']} 个事件, "
            f"{len(event_summary['by_type'])} 种类型"
        )

        stats = self.get_stats()
        stats['vehicle_accel_range'] = (
            float(self._speed_preprocessor.vehicle_accel_array.min()),
            float(self._speed_preprocessor.vehicle_accel_array.max()),
        )

        return {
            'events': [e.to_dict() for e in detector_events],
            'event_summary': event_summary,
            'frame_results': frame_results,
            'stats': stats,
        }
