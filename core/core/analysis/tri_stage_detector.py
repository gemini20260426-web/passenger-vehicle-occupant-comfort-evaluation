"""
三阶联检事件检测器 — 统一驾驶行为事件分析引擎核心

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分。
实现: 阈值预检(Stage1) → 多维特征验证(Stage2) → ML后验精分类(Stage3) → 置信度融合(Stage4)

当前版本: 基于规则引擎的确定性检测 (ML模型训练数据待补充)
目标置信度: >95%
"""

import numpy as np
from scipy import signal as scipy_signal
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import deque
import logging

if TYPE_CHECKING:
    from .model_trainer import AdaptiveModelUpdater

logger = logging.getLogger(__name__)


@dataclass
class EventResult:
    """事件检测结果"""
    event_type: str
    category: str
    confidence: float
    timestamp: float
    rule_score: float = 0.0
    feature_score: float = 0.0
    context_score: float = 0.0
    latency_ms: float = 0.0
    # ML在线更新相关字段
    ml_confidence: float = 0.0
    drift: dict = field(default_factory=dict)
    needs_feedback: bool = False


class TriStageDetector:
    """三阶联检检测器基类"""

    def __init__(self, fs: float = 100.0):
        self.fs = fs
        self._context_history: deque = deque(maxlen=20)

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        """三阶联检主流程 (子类实现)"""
        raise NotImplementedError

    def _check_threshold(self, value: float, threshold: Optional[Tuple]) -> bool:
        """检查阈值: (lower, upper), None表示无限制"""
        if threshold is None:
            return True
        lo, hi = threshold
        if lo is not None and value < lo:
            return False
        if hi is not None and value > hi:
            return False
        return True

    def _update_context(self, event_type: str) -> None:
        """更新上下文历史"""
        self._context_history.append(event_type)

    def _context_score(self, event_type: str) -> float:
        """上下文一致性得分"""
        if len(self._context_history) < 2:
            return 1.0
        # 简单规则: 相同类型连续出现 → 高一致性
        recent = list(self._context_history)[-3:]
        if recent and recent[-1] == event_type:
            return 0.95
        return 0.85


# ═══════════════════════════════════════════════════════════════
# GROUP 1: 纵向事件检测器 (8种)
# ═══════════════════════════════════════════════════════════════

class LongitudinalEventDetector(TriStageDetector):
    """纵向事件检测器 — 8种事件"""

    STAGE1_THRESHOLDS = {
        'emergency_braking': {
            'speed_delta': (None, -20),   # 速度降幅 >= 20km/h (speed_delta <= -20)
            'ax_min': (None, -5.0),
            'duration': (0.3, 2.0),
        },
        'aggressive_deceleration': {
            'speed_delta': (-15, -5),
            'ax_min': (-5.0, -2.5),
            'duration': (0.5, 4.0),
        },
        'normal_deceleration': {
            'speed_delta': (-8, -2),
            'ax_min': (-2.5, -0.5),
            'duration': (1.0, 10.0),
        },
        'aggressive_acceleration': {
            'speed_delta': (5, None),
            'ax_max': (2.5, None),
            'duration': (0.3, 3.0),
        },
        'normal_acceleration': {
            'speed_delta': (2, 8),
            'ax_max': (0.5, 2.5),
            'duration': (1.0, 15.0),
        },
        'launch': {
            'speed_start': (None, 3),
            'speed_delta': (3, 15),
            'ax_max': (1.0, 4.0),
            'duration': (1.0, 5.0),
        },
        'constant_speed': {
            'speed_std': (None, 2.0),
            'ax_std': (None, 0.5),
            'duration': (3.0, None),
        },
        'stopped': {
            'speed_max': (None, 0.5),
            'ax_std': (None, 0.3),
            'duration': (1.0, None),
        },
    }

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        results = []
        speed = window.get('speed', np.array([]))
        ax = window.get('Ax', np.array([]))
        rel_time = window.get('rel_time', np.array([]))

        if len(speed) < 10 or len(ax) < 10:
            return results

        dur = float(rel_time[-1] - rel_time[0]) if len(rel_time) > 1 else 0.0
        speed_delta = float(speed[-1] - speed[0])
        speed_start = float(speed[0])

        for etype, thresholds in self.STAGE1_THRESHOLDS.items():
            # Stage 1: 阈值预检
            if not self._check_threshold(speed_delta, thresholds.get('speed_delta')):
                continue
            if not self._check_threshold(np.min(ax), thresholds.get('ax_min')):
                continue
            if not self._check_threshold(np.max(ax), thresholds.get('ax_max')):
                continue
            if not self._check_threshold(dur, thresholds.get('duration')):
                continue
            if 'speed_start' in thresholds:
                if not self._check_threshold(speed_start, thresholds['speed_start']):
                    continue
            if 'speed_std' in thresholds:
                if not self._check_threshold(np.std(speed), thresholds['speed_std']):
                    continue
            if 'ax_std' in thresholds:
                if not self._check_threshold(np.std(ax), thresholds['ax_std']):
                    continue
            if 'speed_max' in thresholds:
                if not self._check_threshold(np.max(speed), thresholds['speed_max']):
                    continue

            # Stage 2: 多维特征验证
            ok, feature_score = self._stage2_verify(etype, window)
            if not ok:
                continue

            # Stage 3: 置信度计算 (规则引擎, 无ML模型时)
            context_score = self._context_score(etype)
            confidence = 0.40 * 0.95 + 0.35 * feature_score + 0.25 * context_score

            if confidence > 0.85:
                self._update_context(etype)
                results.append(EventResult(
                    event_type=etype,
                    category='longitudinal',
                    confidence=round(float(confidence), 3),
                    timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                    rule_score=0.95,
                    feature_score=round(float(feature_score), 3),
                    context_score=round(float(context_score), 3),
                ))

        return results

    def _stage2_verify(self, etype: str, window: Dict[str, np.ndarray]) -> Tuple[bool, float]:
        """纵向事件六维联动验证"""
        speed = window.get('speed', np.array([]))
        ax = window.get('Ax', np.array([]))

        if len(speed) < 20 or len(ax) < 20:
            return False, 0.0

        # 1. 方向一致性: speed变化方向 = Ax符号
        # 对于接近零信号的事件(constant_speed, stopped), 跳过方向检查
        if etype not in ('constant_speed', 'stopped'):
            speed_dir = np.sign(np.mean(np.diff(speed[-20:])))
            ax_dir = np.sign(np.mean(ax[-20:]))
            if speed_dir * ax_dir < 0:
                return False, 0.0

        # 2. 线性相关
        if len(speed) > 1:
            corr = float(np.corrcoef(np.diff(speed), ax[1:])[0, 1])
            if np.isnan(corr):
                corr = 0.0
        else:
            corr = 0.0

        if etype in ('emergency_braking', 'aggressive_deceleration',
                     'aggressive_acceleration'):
            if abs(corr) < 0.5:
                return False, 0.0

        # 3. Jerk验证
        jerk = np.diff(ax) * self.fs
        jerk_max = float(np.max(np.abs(jerk)))
        if etype in ('emergency_braking', 'aggressive_deceleration'):
            if jerk_max < 2.0:
                return False, 0.0

        return True, max(0.7, abs(corr))


# ═══════════════════════════════════════════════════════════════
# GROUP 2: 侧向事件检测器 (8种)
# ═══════════════════════════════════════════════════════════════

class LateralEventDetector(TriStageDetector):
    """侧向事件检测器 — 8种事件"""

    STAGE1_THRESHOLDS = {
        'weaving': {
            'wheel_amplitude': (40, None),
            'ay_amplitude': (3.0, None),
            'zero_crossings': (4, None),
            'duration': (2.0, 30.0),
        },
        'lane_change': {
            'wheel_amplitude': (15, 60),
            'ay_amplitude': (1.5, 4.0),
            'duration': (0.5, 5.0),
        },
        'rapid_direction_change': {
            'wheel_amplitude': (60, None),
            'ay_amplitude': (4.0, None),
            'duration': (0.2, 2.0),
        },
        'tight_turn': {
            'wheel_steady': (80, None),
            'ay_steady': (2.0, None),
            'wheel_std': (None, 15),
            'duration': (1.0, 10.0),
        },
        'wide_turn': {
            'wheel_steady': (30, 120),
            'ay_steady': (1.0, 3.0),
            'duration': (2.0, 20.0),
        },
        'u_turn': {
            'wheel_cumulative': (150, None),
            'ay_steady': (1.5, None),
            'duration': (3.0, 20.0),
        },
        'straight_driving': {
            'wheel_std': (None, 5),
            'ay_std': (None, 0.5),
            'duration': (3.0, None),
        },
        'lane_keeping': {
            'wheel_std': (5, 15),
            'ay_std': (None, 1.0),
            'duration': (5.0, None),
        },
    }

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        results = []
        wheel = window.get('wheel', np.array([]))
        ay = window.get('Ay', np.array([]))
        rel_time = window.get('rel_time', np.array([]))

        if len(wheel) < 10 or len(ay) < 10:
            return results

        dur = float(rel_time[-1] - rel_time[0]) if len(rel_time) > 1 else 0.0
        wheel_amplitude = float(np.max(wheel) - np.min(wheel))
        ay_amplitude = float(np.max(ay) - np.min(ay))
        wheel_std = float(np.std(wheel))
        ay_std = float(np.std(ay))
        wheel_mean = float(np.mean(np.abs(wheel)))
        zc = int(np.sum(np.diff(np.signbit(ay)) != 0))

        for etype, thresholds in self.STAGE1_THRESHOLDS.items():
            if not self._check_threshold(wheel_amplitude, thresholds.get('wheel_amplitude')):
                continue
            if not self._check_threshold(ay_amplitude, thresholds.get('ay_amplitude')):
                continue
            if not self._check_threshold(dur, thresholds.get('duration')):
                continue
            if 'zero_crossings' in thresholds:
                if not self._check_threshold(zc, thresholds['zero_crossings']):
                    continue
            if 'wheel_steady' in thresholds:
                if not self._check_threshold(wheel_mean, thresholds['wheel_steady']):
                    continue
            if 'ay_steady' in thresholds:
                if not self._check_threshold(np.mean(np.abs(ay)), thresholds['ay_steady']):
                    continue
            if 'wheel_std' in thresholds:
                if not self._check_threshold(wheel_std, thresholds['wheel_std']):
                    continue
            if 'ay_std' in thresholds:
                if not self._check_threshold(ay_std, thresholds['ay_std']):
                    continue
            if 'wheel_cumulative' in thresholds:
                cumulative = float(np.sum(np.abs(np.diff(wheel))))
                if not self._check_threshold(cumulative, thresholds['wheel_cumulative']):
                    continue

            # Stage 2
            ok, score = self._stage2_verify(etype, window)
            if not ok:
                continue

            context_score = self._context_score(etype)
            confidence = 0.40 * 0.93 + 0.35 * score + 0.25 * context_score

            if confidence > 0.85:
                self._update_context(etype)
                results.append(EventResult(
                    event_type=etype,
                    category='lateral',
                    confidence=round(float(confidence), 3),
                    timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                    rule_score=0.93,
                    feature_score=round(float(score), 3),
                    context_score=round(float(context_score), 3),
                ))

        return results

    def _stage2_verify(self, etype: str, window: Dict[str, np.ndarray]) -> Tuple[bool, float]:
        """侧向事件频域+相位验证"""
        ay = window.get('Ay', np.array([]))
        wheel = window.get('wheel', np.array([]))

        if len(ay) < 20:
            return False, 0.0

        # 稳定状态事件 (straight_driving, lane_keeping): 验证低波动性
        if etype in ('straight_driving', 'lane_keeping'):
            wheel_std = float(np.std(wheel))
            ay_std = float(np.std(ay))
            # 稳定性得分: 越稳定分越高
            w_score = max(0.0, 1.0 - wheel_std / 10.0)
            a_score = max(0.0, 1.0 - ay_std / 1.0)
            stability_score = (w_score + a_score) / 2.0
            return stability_score > 0.3, stability_score

        # 1. 频域验证: Butterworth BPF 0.1-5Hz (消除DC漂移偏差)
        try:
            nyq = self.fs / 2.0
            low = 0.1 / nyq
            high = 5.0 / nyq
            # 4阶 Butterworth 带通滤波器去DC后计算PSD (消除DC漂移偏差 93.9%→80.4%)
            b, a = scipy_signal.butter(4, [low, high], btype='band')
            ay_filtered = scipy_signal.filtfilt(b, a, ay)
            # 检查滤波后信号是否有足够能量
            if np.std(ay_filtered) < 0.01:
                return False, 0.0
            # 对滤波后信号做Welch PSD, 找主频
            f, Pxx = scipy_signal.welch(ay_filtered, fs=self.fs, nperseg=min(256, len(ay_filtered)))
            dom_f = float(f[np.argmax(Pxx)])
            if dom_f < 0.1 or dom_f > 5.0:
                return False, 0.0
        except Exception:
            pass

        # 2. Wheel-Ay相位一致性
        if len(wheel) > 1 and len(ay) > 1:
            try:
                cross_corr = np.correlate(
                    wheel - np.mean(wheel),
                    ay - np.mean(ay), mode='same'
                )
                denom = len(wheel) * np.std(wheel) * np.std(ay) + 1e-6
                phase_score = float(np.max(np.abs(cross_corr)) / denom)
                phase_score = min(1.0, max(0.0, phase_score))
            except Exception:
                phase_score = 0.5
        else:
            phase_score = 0.5

        return True, phase_score


# ═══════════════════════════════════════════════════════════════
# GROUP 3: 复合事件检测器 (3种)
# ═══════════════════════════════════════════════════════════════

class CompositeEventDetector(TriStageDetector):
    """复合事件检测器 — 弯道+变速 (3种)"""

    STAGE1_THRESHOLDS = {
        'cornering_braking': {
            'wheel_abs_min': (15, None),
            'speed_delta': (-10, None),
            'ax_min': (None, -2.0),
            'duration': (0.5, 3.0),
        },
        'cornering_acceleration': {
            'wheel_abs_min': (15, None),
            'speed_delta': (3, None),
            'ax_max': (1.0, None),
            'duration': (1.0, 5.0),
        },
        'cornering_deceleration': {
            'wheel_abs_min': (15, None),
            'speed_delta': (-8, -2),
            'ax_min': (-2.5, -0.5),
            'duration': (1.0, 8.0),
        },
    }

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        results = []
        wheel = window.get('wheel', np.array([]))
        speed = window.get('speed', np.array([]))
        ax = window.get('Ax', np.array([]))
        ay = window.get('Ay', np.array([]))
        rel_time = window.get('rel_time', np.array([]))

        if len(wheel) < 10 or len(speed) < 10:
            return results

        dur = float(rel_time[-1] - rel_time[0]) if len(rel_time) > 1 else 0.0
        wheel_abs = float(np.mean(np.abs(wheel)))
        speed_delta = float(speed[-1] - speed[0])

        for etype, thresholds in self.STAGE1_THRESHOLDS.items():
            if not self._check_threshold(wheel_abs, thresholds.get('wheel_abs_min')):
                continue
            if not self._check_threshold(speed_delta, thresholds.get('speed_delta')):
                continue
            if not self._check_threshold(np.min(ax), thresholds.get('ax_min')):
                continue
            if not self._check_threshold(np.max(ax), thresholds.get('ax_max')):
                continue
            if not self._check_threshold(dur, thresholds.get('duration')):
                continue

            ok, score = self._stage2_verify(etype, window)
            if not ok:
                continue

            context_score = self._context_score(etype)
            confidence = 0.40 * 0.93 + 0.35 * score + 0.25 * context_score

            if confidence > 0.85:
                self._update_context(etype)
                results.append(EventResult(
                    event_type=etype,
                    category='composite',
                    confidence=round(float(confidence), 3),
                    timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                    rule_score=0.93,
                    feature_score=round(float(score), 3),
                    context_score=round(float(context_score), 3),
                ))

        return results

    def _stage2_verify(self, etype: str, window: Dict[str, np.ndarray]) -> Tuple[bool, float]:
        """复合事件: wheel×speed联动验证"""
        wheel = np.abs(window.get('wheel', np.array([])))
        speed = window.get('speed', np.array([]))
        ax = window.get('Ax', np.array([]))
        ay = window.get('Ay', np.array([]))

        if len(wheel) < 10:
            return False, 0.0

        # 转弯确认: wheel在事件期间持续>阈值
        wheel_ok_ratio = float(np.mean(wheel > 10))
        if wheel_ok_ratio < 0.6:
            return False, 0.0

        # Ax-Ay联合验证
        ax_rms = float(np.sqrt(np.mean(ax ** 2)))
        ay_rms = float(np.sqrt(np.mean(ay ** 2)))
        if ax_rms < 0.2 or ay_rms < 0.2:
            return False, 0.0

        return True, min(wheel_ok_ratio, 0.9)


# ═══════════════════════════════════════════════════════════════
# GROUP 4: 异常事件检测器 (4种)
# ═══════════════════════════════════════════════════════════════

class AnomalyEventDetector(TriStageDetector):
    """异常事件检测器 — 4种"""

    STAGE1_THRESHOLDS = {
        'severe_bump': {
            'az_peak': (5.0, None),
            'duration': (0.01, 0.3),
        },
        'skid_risk': {
            'ay_peak': (4.0, None),
            'wheel_ay_mismatch': (0.5, None),
        },
        'rollover_risk': {
            'ay_peak': (6.0, None),
            'duration': (0.2, None),
        },
        'sensor_fault': {
            'signal_outlier': (5.0, None),
        },
    }

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        results = []
        az = window.get('Az', np.array([]))
        ay = window.get('Ay', np.array([]))
        wheel = window.get('wheel', np.array([]))
        rel_time = window.get('rel_time', np.array([]))

        if len(az) < 5:
            return results

        dur = float(rel_time[-1] - rel_time[0]) if len(rel_time) > 1 else 0.0
        az_peak = float(np.max(np.abs(az)))
        ay_peak = float(np.max(np.abs(ay)))

        for etype, thresholds in self.STAGE1_THRESHOLDS.items():
            if etype == 'severe_bump':
                if not self._check_threshold(az_peak, thresholds.get('az_peak')):
                    continue
                if not self._check_threshold(dur, thresholds.get('duration')):
                    continue
            elif etype == 'skid_risk':
                if not self._check_threshold(ay_peak, thresholds.get('ay_peak')):
                    continue
                # 侧滑特征: wheel转角大但Ay不跟随
                if len(wheel) > 5 and len(ay) > 5:
                    w_std = float(np.std(wheel))
                    ay_std = float(np.std(ay))
                    if w_std > 30 and ay_std < 1.5:
                        pass  # 高置信侧滑
                    elif not self._check_threshold(
                        abs(w_std - ay_std), thresholds.get('wheel_ay_mismatch')
                    ):
                        continue
            elif etype == 'rollover_risk':
                if not self._check_threshold(ay_peak, thresholds.get('ay_peak')):
                    continue
                if not self._check_threshold(dur, thresholds.get('duration')):
                    continue
            elif etype == 'sensor_fault':
                # 信号超出5σ检查
                if len(az) > 10:
                    az_std = float(np.std(az))
                    if az_std > 0:
                        max_sigma = az_peak / az_std
                        if not self._check_threshold(
                            max_sigma, thresholds.get('signal_outlier')
                        ):
                            continue

            ok, score = self._stage2_verify(etype, window)
            if not ok:
                continue

            context_score = self._context_score(etype)
            confidence = 0.50 * 0.98 + 0.30 * score + 0.20 * context_score

            if confidence > 0.90:
                self._update_context(etype)
                results.append(EventResult(
                    event_type=etype,
                    category='anomaly',
                    confidence=round(float(confidence), 3),
                    timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                    rule_score=0.98,
                    feature_score=round(float(score), 3),
                    context_score=round(float(context_score), 3),
                ))

        return results

    def _stage2_verify(self, etype: str, window: Dict[str, np.ndarray]) -> Tuple[bool, float]:
        """异常事件验证"""
        az = window.get('Az', np.array([]))

        if etype == 'severe_bump':
            # 过零率: bump应该是短时脉冲
            if len(az) > 5:
                zc = int(np.sum(np.diff(np.signbit(az)) != 0))
                if zc > len(az) * 0.15:
                    return False, 0.0
            return True, 0.9

        elif etype == 'skid_risk':
            wheel = window.get('wheel', np.array([]))
            ay = window.get('Ay', np.array([]))
            if len(wheel) > 5 and len(ay) > 5:
                w_std = float(np.std(wheel))
                ay_std = float(np.std(ay))
                if w_std > 30 and ay_std < 1.5:
                    return True, 0.95
            return True, 0.6

        return True, 0.8


# ═══════════════════════════════════════════════════════════════
# GROUP 5: 驾驶状态检测器 (7子状态)
# ═══════════════════════════════════════════════════════════════

class DrivingStateDetector(TriStageDetector):
    """驾驶状态检测器 — 7子状态"""

    STATE_RULES = {
        'parked': {
            'speed_max': (None, 0.3),
            'duration': (3.0, None),
        },
        'straight_cruise': {
            'wheel_abs_mean': (None, 5),
            'speed_mean': (30, 120),
            'speed_std': (None, 3),
            'duration': (5.0, None),
        },
        'cruising': {
            'speed_mean': (30, 120),
            'speed_std': (None, 5),
            'ax_std': (None, 0.5),
            'duration': (5.0, None),
        },
        'left_turn': {
            'wheel_mean': (-200, -15),
            'speed_mean': (5, 60),
            'duration': (1.0, None),
        },
        'right_turn': {
            'wheel_mean': (15, 200),
            'speed_mean': (5, 60),
            'duration': (1.0, None),
        },
        'overspeeding': {
            'speed_mean': (120, None),
            'duration': (1.0, None),
        },
    }

    def detect(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        results = []
        speed = window.get('speed', np.array([]))
        wheel = window.get('wheel', np.array([]))
        ax = window.get('Ax', np.array([]))
        rel_time = window.get('rel_time', np.array([]))

        if len(speed) < 10:
            return results

        dur = float(rel_time[-1] - rel_time[0]) if len(rel_time) > 1 else 0.0
        stats = {
            'speed_mean': float(np.mean(speed)),
            'speed_std': float(np.std(speed)),
            'speed_max': float(np.max(speed)),
            'wheel_mean': float(np.mean(wheel)),
            'wheel_abs_mean': float(np.mean(np.abs(wheel))),
            'ax_std': float(np.std(ax)),
            'duration': dur,
        }

        for state, rules in self.STATE_RULES.items():
            match = True
            for key, (lo, hi) in rules.items():
                if key == 'duration':
                    continue
                val = stats.get(key)
                if val is None:
                    continue
                if lo is not None and val < lo:
                    match = False
                if hi is not None and val > hi:
                    match = False
            if match:
                # 检查持续时间
                if self._check_threshold(dur, rules.get('duration')):
                    confidence = 0.90 if state in ('parked', 'straight_cruise') else 0.85
                    results.append(EventResult(
                        event_type=state,
                        category='state',
                        confidence=confidence,
                        timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                        rule_score=confidence,
                        feature_score=0.0,
                        context_score=0.0,
                    ))
                    return results  # 状态互斥，返回第一个匹配

        # 默认: normal
        if len(speed) > 100:
            results.append(EventResult(
                event_type='normal',
                category='state',
                confidence=0.95,
                timestamp=float(rel_time[-1]) if len(rel_time) > 0 else 0.0,
                rule_score=0.95,
                feature_score=0.0,
                context_score=0.0,
            ))

        return results


# ═══════════════════════════════════════════════════════════════
# 统一调度器
# ═══════════════════════════════════════════════════════════════

class UnifiedEventDetector:
    """统一事件检测调度器

    按优先级顺序调度5组检测器: 异常 > 复合 > 纵向 > 侧向 > 状态

    支持可选的ML模型在线更新:
    - detect_all_with_ml(): 规则检测 + ML后验精分类 + 漂移检测
    - provide_feedback(): 人工标注反馈 → 触发增量学习
    """

    def __init__(self, fs: float = 100.0,
                 model_trainer=None,
                 model_updater: 'AdaptiveModelUpdater' = None):
        self.longitudinal = LongitudinalEventDetector(fs)
        self.lateral = LateralEventDetector(fs)
        self.composite = CompositeEventDetector(fs)
        self.anomaly = AnomalyEventDetector(fs)
        self.state = DrivingStateDetector(fs)

        self.detector_order = [
            (self.anomaly, 'anomaly'),
            (self.composite, 'composite'),
            (self.longitudinal, 'longitudinal'),
            (self.lateral, 'lateral'),
            (self.state, 'state'),
        ]

        # ML 模型集成
        self.model_trainer = model_trainer
        self.model_updater = model_updater

    def detect_all(self, window: Dict[str, np.ndarray]) -> List[EventResult]:
        """检测所有事件 (按优先级顺序)"""
        results = []

        for detector, category in self.detector_order:
            try:
                detected = detector.detect(window)
                for ev in detected:
                    if ev.confidence > 0.85:
                        results.append(ev)
            except Exception as e:
                logger.warning(f"检测器 {category} 失败: {e}")

        # 重排序: 置信度降序
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def detect_all_with_ml(self, window: Dict[str, np.ndarray],
                           features: np.ndarray = None) -> List[EventResult]:
        """规则检测 + ML后验精分类 + 在线自适应更新

        Args:
            window: 信号窗口 {'speed': [], 'Ax': [], ...}
            features: 预提取的ML特征向量 [M] (可选, 不提供则跳过ML)

        Returns:
            EventResult 列表, 置信度经过ML精炼
        """
        results = self.detect_all(window)

        # 如果提供了ML特征且有模型更新器, 进行ML后验精分类
        if features is not None and self.model_updater is not None:
            for r in results:
                try:
                    ml_result = self.model_updater.predict_with_adaptation(
                        r.event_type, features
                    )
                    # ML置信度与规则置信度融合
                    if ml_result['confidence'] > 0.3:
                        r.ml_confidence = round(float(ml_result['confidence']), 3)
                        r.confidence = round(
                            float(0.6 * r.confidence + 0.4 * ml_result['confidence']), 3
                        )
                        r.drift = ml_result.get('drift', {})
                        r.needs_feedback = ml_result.get('needs_feedback', False)
                except Exception as e:
                    logger.debug(f"ML后验分类 {r.event_type} 失败: {e}")

        return results

    def provide_feedback(self, features: np.ndarray,
                         event_type: str,
                         true_label: bool,
                         source: str = 'manual') -> None:
        """人工标注反馈 (触发增量学习)

        Args:
            features: 特征向量 [M]
            event_type: 事件类型
            true_label: True=正样本, False=负样本
            source: 反馈来源
        """
        if self.model_updater is not None:
            self.model_updater.provide_feedback(
                features, event_type, true_label, source=source
            )

    def get_drift_status(self) -> dict:
        """获取ML模型漂移状态"""
        if self.model_updater is not None:
            return self.model_updater.get_drift_status()
        return {'drift_detected': False, 'message': 'ML未启用'}

    def get_drift_samples(self, n: int = 10) -> List[dict]:
        """获取待审核的漂移样本"""
        if self.model_updater is not None:
            return self.model_updater.get_drift_samples(n)
        return []