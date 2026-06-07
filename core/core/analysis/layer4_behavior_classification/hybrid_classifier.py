#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合行为分类器 — Layer 4 编排器 (Phase 2 增强版)

候选源:
  1. PhysicsRuleEngine    — 硬阈值规则 (Stage1 预检, 可解释)
  2. StatisticalClassifier — 统计置信度调整 (保留作回退)
  3. LightGBMClassifier    — ML 多分类器 (Phase 1 主力, Phase 2 校准)
  4. ContextWindow         — 上下文序列增强 (Phase 2 新增)
  5. ContextAwareThresholds — 速度/场景自适应调整 (保留)

Phase 2 增强:
  - 概率校准: Platt Scaling + 温度缩放 (ML 输出)
  - 上下文窗口: 滑动窗口 + 转移概率 + 序列模式
  - 权重调整: ML 权重 0.45→0.40, 上下文窗口 0.15

融合策略: MultiBehaviorResolver 加权投票
"""

import logging
import importlib
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from scipy import signal as scipy_signal
from scipy.fft import rfft, rfftfreq
from scipy.stats import skew, kurtosis
from ..core_types import ManeuverEvent, FrameFeatures, BehaviorCategory
from .rule_engine import PhysicsRuleEngine
from .statistical_classifier import StatisticalClassifier
from .context_aware_thresholds import ContextAwareThresholds
from .multi_behavior_resolver import MultiBehaviorResolver
from .context_window import ContextWindow

# LightGBM 延迟导入 — 模块缺失时优雅降级
try:
    from .ml_classifier import LightGBMClassifier
    _lightgbm_available = True
except ImportError:
    _lightgbm_available = False
    LightGBMClassifier = None


class HybridBehaviorClassifier:
    """L4 混合行为分类器 — 规则 + 统计 + ML + 上下文 (Phase 2)

    用法:
        clf = HybridBehaviorClassifier()
        clf.load_ml_model()  # 可选: 加载预训练 LightGBM 模型
        event = clf.classify(event, features)
    """

    def __init__(self, context_window_size: int = 10, use_confidence_refiner: bool = True):
        self._logger = logging.getLogger(__name__)
        self._rule_engine = PhysicsRuleEngine()
        self._statistical = StatisticalClassifier()
        self._context = ContextAwareThresholds()
        self._context_window = ContextWindow(window_size=context_window_size)
        self._resolver = MultiBehaviorResolver()

        # ── E1: lightgbm 可用性检查 + 优雅降级 ──
        self._ml_available = _lightgbm_available and self._check_lightgbm_runtime()

        if self._ml_available:
            self._ml_classifier = LightGBMClassifier()
            try:
                self._ml_classifier.load_or_train()
                if self._ml_classifier.is_ready():
                    self._logger.info("LightGBM 模型已加载，ML 分类就绪")
                    if self._ml_classifier.calibrator.is_fitted():
                        self._logger.info("概率校准器已就绪 (Phase 2)")
                else:
                    self._logger.info("LightGBM 模型未训练，将使用规则+统计模式")
                    self._ml_available = False
            except Exception as e:
                self._logger.warning(f"LightGBM 模型加载失败: {e}，回退到规则+统计模式")
                self._ml_available = False
        else:
            self._ml_classifier = None
            self._logger.warning(
                "lightgbm 未安装或不可用。安装方法: pip install lightgbm==4.3.0\n"
                "当前将使用规则+统计模式 (准确率 ~75%, 22种事件)"
            )

        # ── F3: 置信度精炼器集成 (消除孤岛模块) ──
        self._confidence_refiner = None
        if use_confidence_refiner:
            try:
                from core.core.analysis.event_confidence_refiner import EventConfidenceRefiner
                self._confidence_refiner = EventConfidenceRefiner(
                    confidence_threshold=0.85, use_ml=True
                )
                self._logger.info("置信度精炼器已集成 (EventConfidenceRefiner)")
            except Exception as e:
                self._logger.warning(f"置信度精炼器加载失败: {e}")

    @staticmethod
    def _check_lightgbm_runtime() -> bool:
        """E1: 运行时检查 lightgbm 是否可用"""
        try:
            import lightgbm
            return True
        except ImportError:
            return False

    def classify(self, event: ManeuverEvent, features: Optional[FrameFeatures] = None) -> ManeuverEvent:
        """分类入口 — 五源融合 (Phase 2)

        Args:
            event: L3 检测到的候选事件
            features: L2 提取的 FrameFeatures

        Returns:
            分类后的 ManeuverEvent (type/category/confidence 已更新)
        """
        candidates = []

        # 候选源 1: 规则引擎 (Stage1 预检, 权重 0.25)
        rule_result = self._rule_engine.classify(event, features)
        candidates.append(rule_result)

        # 候选源 2: 统计分类器 (保留回退, 权重 0.10)
        stat_result = self._statistical.classify(event, features)
        candidates.append(stat_result)

        # 候选源 3: LightGBM ML 分类器 (主力, 权重 0.40) — E1: 仅在可用时加入
        if self._ml_available and self._ml_classifier and self._ml_classifier.is_ready():
            ml_result = self._ml_classifier.classify(event, features)
            candidates.append(ml_result)

        # 候选源 4: 上下文窗口 (Phase 2 新增, 权重 0.15)
        ctx_win_type, ctx_win_conf = self._context_window.adjust(
            event.type, event.category, event.confidence
        )
        candidates.append((ctx_win_type, event.category, ctx_win_conf))

        # 候选源 5: 速度/场景自适应 (权重 0.10)
        ctx_result = self._context.adjust(event)
        candidates.append(ctx_result)

        final_behavior, final_category, final_confidence = self._resolver.resolve(candidates)

        # ── F3: 置信度精炼 (Phase 2 增强) ──
        if self._confidence_refiner is not None:
            try:
                # 获取上下文历史
                context_history = self._context_window.get_history()
                # 获取当前速度 (从 event 或 features 中提取)
                current_speed = None
                if hasattr(event, 'speed_range') and event.speed_range:
                    if isinstance(event.speed_range, (list, tuple)) and len(event.speed_range) >= 2:
                        current_speed = (event.speed_range[0] + event.speed_range[1]) / 2
                    elif isinstance(event.speed_range, (int, float)):
                        current_speed = event.speed_range

                final_confidence = self._confidence_refiner.refine_single(
                    event_type=final_behavior,
                    confidence=final_confidence,
                    context_history=context_history,
                    speed=current_speed,
                )
            except Exception as e:
                self._logger.debug(f"置信度精炼失败 (静默): {e}")

        event.type = final_behavior
        event.category = final_category
        event.confidence = final_confidence
        event.detection_method = "hybrid_ml_v2" if self._ml_classifier.is_ready() else "hybrid"

        # Phase 2: 将分类结果推入上下文窗口
        self._context_window.push(final_behavior, final_category, final_confidence)

        # ── F4: 记录到系统监控 ──
        try:
            from core.core.analysis.monitor_backend import get_system_monitor
            monitor = get_system_monitor()
            monitor.record_pipeline_event(
                event_type=final_behavior,
                confidence=final_confidence,
            )
        except Exception:
            pass  # 监控不可用时静默跳过

        return event

    def load_ml_model(self, X=None, y=None) -> bool:
        """显式加载或训练 ML 模型

        Args:
            X: 训练特征矩阵 (可选)
            y: 训练标签 (可选)

        Returns:
            True 如果 ML 模型已就绪
        """
        return self._ml_classifier.load_or_train(X, y)

    def train_ml_model(self, X, y, X_val=None, y_val=None, fit_calibrator: bool = True):
        """训练 ML 模型 (Phase 2: 自动拟合校准器)

        Args:
            X: 训练特征 shape=(N, 55)
            y: 训练标签 shape=(N,)
            X_val: 验证特征 (可选)
            y_val: 验证标签 (可选)
            fit_calibrator: 是否同时拟合概率校准器 (Phase 2)

        Returns:
            训练指标字典
        """
        metrics = self._ml_classifier.train(X, y, X_val, y_val)

        # Phase 2: 在验证集上拟合概率校准器
        if fit_calibrator and X_val is not None and y_val is not None:
            cal_metrics = self._ml_classifier.fit_calibrator(X_val, y_val, method='both')
            metrics['calibration'] = cal_metrics

        return metrics

    def fit_ml_calibrator(self, X_val, y_val, method: str = 'both'):
        """Phase 2: 显式拟合 ML 概率校准器"""
        return self._ml_classifier.fit_calibrator(X_val, y_val, method=method)

    @property
    def context_window(self) -> ContextWindow:
        """获取上下文窗口 (Phase 2, 用于调试)"""
        return self._context_window

    @property
    def ml_classifier(self) -> LightGBMClassifier:
        """获取 ML 分类器实例 (用于外部访问特征重要性等)"""
        return self._ml_classifier

    def get_ml_feature_importance(self):
        """获取 ML 模型特征重要性"""
        return self._ml_classifier.get_feature_importance()

    def reset(self):
        self._rule_engine.reset()
        self._statistical.reset()
        self._ml_classifier.reset()
        self._context.reset()
        self._context_window.reset()
        self._resolver.reset()

    # ═══════════════════════════════════════════════════════════
    #  滑动窗口 ML 独立事件检测 (不依赖规则引擎)
    # ═══════════════════════════════════════════════════════════

    def detect_events_from_raw(
        self,
        t: np.ndarray,
        speed: np.ndarray,
        wheel: np.ndarray,
        ax: np.ndarray,
        ay: np.ndarray,
        az: np.ndarray,
        gx: np.ndarray = None,
        gy: np.ndarray = None,
        gz: np.ndarray = None,
        vehicle_accel: np.ndarray = None,
        speed_ma: np.ndarray = None,
        speed_std: np.ndarray = None,
        wheel_std: np.ndarray = None,
        accel_ma: np.ndarray = None,
        window_size: int = 500,
        step_size: int = 250,
        min_confidence: float = 0.6,
        fs: float = 1000.0,
    ) -> List[Dict[str, Any]]:
        """滑动窗口 ML 独立事件检测 — 不依赖规则引擎

        直接使用 LightGBM 模型对原始时序数据进行滑动窗口扫描，
        弥补规则引擎基于固定阈值漏检的盲区。

        Args:
            t: 时间戳 (秒), shape=(N,)
            speed: 车速 (km/h), shape=(N,)
            wheel: 方向盘转角 (deg), shape=(N,)
            ax, ay, az: IMU 加速度 (m/s²), shape=(N,)
            gx, gy, gz: IMU 角速度 (rad/s), shape=(N,), 可选
            vehicle_accel: 车辆加速度 (m/s²), shape=(N,), 可选
            speed_ma, speed_std, wheel_std, accel_ma: 预处理特征, 可选
            window_size: 滑动窗口大小 (采样点数)
            step_size: 步长 (采样点数)
            min_confidence: 最低置信度阈值
            fs: 采样率 (Hz)

        Returns:
            List[Dict]: 检测到的事件列表，每个事件包含:
                event_id, event_type, event_name, t_start, t_end,
                duration_s, confidence, method='ml_sliding_window'
        """
        if not self._ml_available or self._ml_classifier is None:
            self._logger.warning("ML 不可用，跳过滑动窗口检测")
            return []

        if not self._ml_classifier.is_ready():
            self._logger.warning("ML 模型未就绪，跳过滑动窗口检测")
            return []

        N = len(t)
        if N < window_size:
            self._logger.warning(f"数据长度 {N} < 窗口大小 {window_size}，无法检测")
            return []

        # 确保所有数组长度一致
        def _safe_arr(arr, default_val=0.0):
            if arr is None:
                return np.full(N, default_val, dtype=float)
            return np.asarray(arr, dtype=float)

        speed = _safe_arr(speed)
        wheel = _safe_arr(wheel)
        ax = _safe_arr(ax)
        ay = _safe_arr(ay)
        az = _safe_arr(az)
        gx = _safe_arr(gx)
        gy = _safe_arr(gy)
        gz = _safe_arr(gz)
        vehicle_accel = _safe_arr(vehicle_accel)
        speed_ma = _safe_arr(speed_ma, speed.mean())
        speed_std = _safe_arr(speed_std)
        wheel_std = _safe_arr(wheel_std)
        accel_ma = _safe_arr(accel_ma)

        raw_events = []  # (t_start, t_end, event_type, confidence)

        self._logger.info(
            f"ML 滑动窗口检测开始: N={N}, window={window_size}, step={step_size}, "
            f"min_conf={min_confidence}"
        )

        for start in range(0, N - window_size, step_size):
            end = start + window_size
            t_mid = (t[start] + t[end - 1]) / 2

            # 计算窗口特征
            feats = _compute_window_features(
                t=t[start:end],
                speed=speed[start:end],
                wheel=wheel[start:end],
                ax=ax[start:end],
                ay=ay[start:end],
                az=az[start:end],
                gx=gx[start:end],
                gy=gy[start:end],
                gz=gz[start:end],
                vehicle_accel=vehicle_accel[start:end],
                speed_ma=speed_ma[start:end],
                speed_std=speed_std[start:end],
                wheel_std=wheel_std[start:end],
                accel_ma=accel_ma[start:end],
                fs=fs,
            )

            # 构建 FrameFeatures
            frame_feats = FrameFeatures(timestamp=t_mid)
            frame_feats.temporal = feats['temporal']
            frame_feats.spectral = feats['spectral']
            frame_feats.kinematic = feats['kinematic']
            frame_feats.physics = feats['physics']

            # 构建虚拟 ManeuverEvent (仅用于 ML 分类)
            dummy_event = ManeuverEvent(
                id=f'ml_scan_{start}',
                type='unknown',
                category=BehaviorCategory.UNKNOWN,
                start_time=t[start],
                end_time=t[end - 1],
                duration=t[end - 1] - t[start],
                confidence=0.0,
            )

            # 直接调用 ML 分类器 (纯 ML 检测，不经过五源融合)
            event_type, category, confidence = self._ml_classifier.classify(
                dummy_event, frame_feats
            )

            if confidence >= min_confidence and event_type != 'unknown':
                raw_events.append((t[start], t[end - 1], event_type, confidence))

        # 合并重叠/相邻的同类型事件
        merged = _merge_overlapping_events(raw_events, max_gap=0.5)

        # 转换为标准格式
        events = []
        for i, (t0, t1, etype, conf) in enumerate(merged):
            events.append({
                'event_id': f'ml_detect_{i}',
                'event_type': etype,
                'event_name': etype,
                't_start': float(t0),
                't_end': float(t1),
                'duration_s': float(t1 - t0),
                'confidence': float(conf),
                'method': 'ml_sliding_window',
            })

        self._logger.info(
            f"ML 滑动窗口检测完成: 原始 {len(raw_events)} → "
            f"合并后 {len(events)} 个事件, {len(set(e['event_type'] for e in events))} 种类型"
        )

        return events


# ═══════════════════════════════════════════════════════════
#  窗口特征计算 (55 维 LightGBM 特征)
# ═══════════════════════════════════════════════════════════

def _compute_window_features(
    t: np.ndarray,
    speed: np.ndarray,
    wheel: np.ndarray,
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    vehicle_accel: np.ndarray,
    speed_ma: np.ndarray,
    speed_std: np.ndarray,
    wheel_std: np.ndarray,
    accel_ma: np.ndarray,
    fs: float = 1000.0,
) -> Dict[str, Dict[str, float]]:
    """计算滑动窗口的 55 维特征

    Returns:
        {'temporal': {...}, 'spectral': {...}, 'kinematic': {...}, 'physics': {...}}
    """

    def _safe_stat(arr):
        """安全计算统计量"""
        arr = np.asarray(arr, dtype=float)
        if len(arr) < 2:
            return {'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0,
                    'rms': 0.0, 'skewness': 0.0, 'kurtosis': 0.0}
        return {
            'mean': float(np.mean(arr)),
            'std': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'rms': float(np.sqrt(np.mean(arr ** 2))),
            'skewness': float(skew(arr)) if len(arr) > 3 else 0.0,
            'kurtosis': float(kurtosis(arr)) if len(arr) > 4 else 0.0,
        }

    def _safe_range(arr):
        """安全计算 range"""
        arr = np.asarray(arr, dtype=float)
        if len(arr) < 2:
            return 0.0
        return float(np.max(arr) - np.min(arr))

    def _spectral_features(arr, fs_val):
        """计算频域特征: dominant_freq, spectral_centroid, spectral_entropy"""
        arr = np.asarray(arr, dtype=float)
        n = len(arr)
        if n < 4:
            return {'dominant_freq': 0.0, 'spectral_centroid': 0.0, 'spectral_entropy': 0.0}

        spectrum = np.abs(rfft(arr))
        freqs = rfftfreq(n, d=1.0 / fs_val)

        if len(spectrum) < 2:
            return {'dominant_freq': 0.0, 'spectral_centroid': 0.0, 'spectral_entropy': 0.0}

        total = spectrum.sum()
        if total == 0:
            return {'dominant_freq': 0.0, 'spectral_centroid': 0.0, 'spectral_entropy': 0.0}

        dominant_freq = float(freqs[np.argmax(spectrum)])
        spectral_centroid = float(np.sum(freqs * spectrum) / total)

        # 归一化后计算熵
        psd = spectrum / total
        psd_pos = psd[psd > 0]
        spectral_entropy = float(-np.sum(psd_pos * np.log2(psd_pos))) if len(psd_pos) > 0 else 0.0

        return {
            'dominant_freq': dominant_freq,
            'spectral_centroid': spectral_centroid,
            'spectral_entropy': spectral_entropy,
        }

    def _jerk_snap(arr, dt):
        """计算 jerk 和 snap"""
        arr = np.asarray(arr, dtype=float)
        if len(arr) < 3:
            return {'jerk': 0.0, 'snap': 0.0}
        # 使用 np.gradient 计算导数
        jerk_arr = np.gradient(arr, dt)
        snap_arr = np.gradient(jerk_arr, dt)
        return {
            'jerk': float(np.mean(np.abs(jerk_arr))),
            'snap': float(np.mean(np.abs(snap_arr))),
        }

    dt = 1.0 / fs

    # ── 时域特征 (20维) ──
    ax_stat = _safe_stat(ax)
    ay_stat = _safe_stat(ay)
    az_stat = _safe_stat(az)

    temporal = {
        # ax (7维)
        'ax_mean': ax_stat['mean'],
        'ax_std': ax_stat['std'],
        'ax_min': ax_stat['min'],
        'ax_max': ax_stat['max'],
        'ax_rms': ax_stat['rms'],
        'ax_skewness': ax_stat['skewness'],
        'ax_kurtosis': ax_stat['kurtosis'],
        # ay (4维)
        'ay_mean': ay_stat['mean'],
        'ay_std': ay_stat['std'],
        'ay_rms': ay_stat['rms'],
        'ay_skewness': ay_stat['skewness'],
        # az (3维)
        'az_mean': az_stat['mean'],
        'az_std': az_stat['std'],
        'az_rms': az_stat['rms'],
        # speed (3维)
        'speed_mean': float(np.mean(speed)),
        'speed_std': float(np.std(speed)),
        'speed_range': _safe_range(speed),
        # wheel (3维)
        'wheel_std': float(np.std(wheel)),
        'wheel_range': _safe_range(wheel),
        'wheel_rms': float(np.sqrt(np.mean(wheel ** 2))),
    }

    # ── 频域特征 (15维) ──
    ax_spec = _spectral_features(ax, fs)
    ay_spec = _spectral_features(ay, fs)
    az_spec = _spectral_features(az, fs)
    speed_spec = _spectral_features(speed, fs)
    wheel_spec = _spectral_features(wheel, fs)
    gz_spec = _spectral_features(gz, fs)

    spectral = {
        'ax_dominant_freq': ax_spec['dominant_freq'],
        'ax_spectral_centroid': ax_spec['spectral_centroid'],
        'ax_spectral_entropy': ax_spec['spectral_entropy'],
        'ay_dominant_freq': ay_spec['dominant_freq'],
        'ay_spectral_centroid': ay_spec['spectral_centroid'],
        'ay_spectral_entropy': ay_spec['spectral_entropy'],
        'az_dominant_freq': az_spec['dominant_freq'],
        'az_spectral_centroid': az_spec['spectral_centroid'],
        'az_spectral_entropy': az_spec['spectral_entropy'],
        'speed_dominant_freq': speed_spec['dominant_freq'],
        'speed_spectral_centroid': speed_spec['spectral_centroid'],
        'wheel_dominant_freq': wheel_spec['dominant_freq'],
        'wheel_spectral_centroid': wheel_spec['spectral_centroid'],
        'gz_dominant_freq': gz_spec['dominant_freq'],
        'gz_spectral_centroid': gz_spec['spectral_centroid'],
    }

    # ── 运动学特征 (12维) ──
    ax_kin = _jerk_snap(ax, dt)
    ay_kin = _jerk_snap(ay, dt)
    az_kin = _jerk_snap(az, dt)
    speed_kin = _jerk_snap(speed, dt)
    wheel_kin = _jerk_snap(wheel, dt)
    gz_kin = _jerk_snap(gz, dt)

    kinematic = {
        'ax_jerk': ax_kin['jerk'],
        'ax_snap': ax_kin['snap'],
        'ay_jerk': ay_kin['jerk'],
        'ay_snap': ay_kin['snap'],
        'az_jerk': az_kin['jerk'],
        'az_snap': az_kin['snap'],
        'speed_jerk': speed_kin['jerk'],
        'speed_snap': speed_kin['snap'],
        'wheel_jerk': wheel_kin['jerk'],
        'wheel_snap': wheel_kin['snap'],
        'gz_jerk': gz_kin['jerk'],
        'gz_snap': gz_kin['snap'],
    }

    # ── 物理特征 (8维) ──
    speed_ms = float(np.mean(speed)) / 3.6
    wheel_mean = float(np.mean(np.abs(wheel)))
    # 转弯半径估计 (简化: R = wheelbase / tan(wheel)), wheelbase ≈ 2.7m
    wheel_rad = np.radians(wheel_mean)
    turn_radius = float(2.7 / np.tan(max(wheel_rad, 0.001))) if wheel_rad > 0.001 else 999.0
    # 期望横摆角速度
    expected_yaw_rate = float(speed_ms / max(turn_radius, 0.001)) if turn_radius < 999 else 0.0
    # 实际横摆角速度 (来自 gz)
    actual_yaw_rate = float(np.mean(np.abs(gz)))
    yaw_rate_error = float(abs(actual_yaw_rate - expected_yaw_rate))
    # 侧向加速度比
    ay_mean_val = float(np.mean(np.abs(ay)))
    lateral_accel_ratio = float(ay_mean_val / max(abs(ax_stat['mean']), 0.01))
    # 侧滑角估计
    slip_angle_est = float(np.arctan(ay_mean_val / max(speed_ms, 0.01)))
    # 加速度/速度比
    accel_speed_ratio = float(abs(ax_stat['mean']) / max(speed_ms, 0.01))
    # 侧倾估计
    roll_est = float(np.arctan(ay_mean_val / 9.81))

    physics = {
        'turn_radius': turn_radius,
        'expected_yaw_rate': expected_yaw_rate,
        'yaw_rate_error': yaw_rate_error,
        'lateral_accel_ratio': lateral_accel_ratio,
        'speed_ms': speed_ms,
        'slip_angle_est': slip_angle_est,
        'accel_speed_ratio': accel_speed_ratio,
        'roll_est': roll_est,
    }

    return {
        'temporal': temporal,
        'spectral': spectral,
        'kinematic': kinematic,
        'physics': physics,
    }


def _merge_overlapping_events(
    raw_events: List[Tuple[float, float, str, float]],
    max_gap: float = 0.5,
) -> List[Tuple[float, float, str, float]]:
    """合并重叠/相邻的同类型事件

    Args:
        raw_events: [(t_start, t_end, event_type, confidence), ...]
        max_gap: 最大允许的间隙 (秒)

    Returns:
        合并后的事件列表
    """
    if not raw_events:
        return []

    # 按开始时间排序
    sorted_events = sorted(raw_events, key=lambda x: x[0])

    merged = []
    current = list(sorted_events[0])  # [t_start, t_end, type, conf]

    for evt in sorted_events[1:]:
        t0, t1, etype, conf = evt

        # 同类型且时间重叠或相邻
        if etype == current[2] and t0 - current[1] <= max_gap:
            # 合并: 扩展时间范围, 取更高置信度
            current[1] = max(current[1], t1)
            current[3] = max(current[3], conf)
        else:
            merged.append(tuple(current))
            current = [t0, t1, etype, conf]

    merged.append(tuple(current))
    return merged
