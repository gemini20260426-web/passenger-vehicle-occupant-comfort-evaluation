#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全时域滑动窗口评测引擎 - OccupantMotionEvaluator v2.0
参照专家评测方案实现

功能:
  1. 数据加载与自动验证 (传感器映射、采样率、同步检查)
  2. 事件检测 (制动/加速/转向/冲击)
  3. 全时域连续滑动窗口分析
  4. 事件级精细化对比 (实验组vs对照组)
  5. 频谱分析 (Welch PSD + 频段衰减 + 相干性)
  6. 时频分析 (短时傅里叶变换 STFT)
  7. 统计学分析 (t检验/效应量/置信区间)
  8. 综合评价指标 (VDV/SEAT等效/Crest Factor/传递系数)
"""

import pandas as pd
import numpy as np
from scipy import signal, stats
from typing import Dict, Any, Optional, Tuple, List
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

CONFIG = {
    'fs': 1000,                       # 默认采样率 Hz
    'window_sec': 1.0,                # 滑动窗口 秒
    'step_sec': 0.5,                  # 滑动步长 秒
    'nfft_welch': 8192,               # Welch PSD FFT点数
    'nfft_stft': 512,                 # STFT FFT点数
    'stft_overlap': 384,              # STFT重叠
    'ds_brake_thresh': -2,            # 制动检测阈值 km/h/s
    'ds_accel_thresh': 3,             # 加速检测阈值 km/h/s
    'dw_steer_thresh': 3,             # 转向检测阈值 deg/s
    'da_shock_thresh': 0.5,           # 冲击检测阈值 m/s²
    'freq_bands': {                   # 频段划分 (Hz格式，避免重复)
        '0.1-0.5Hz': (0.1, 0.5),
        '0.5-1Hz': (0.5, 1.0),
        '1-5Hz': (1.0, 5.0),
        '5-20Hz': (5.0, 20.0),
        '20-80Hz': (20.0, 80.0),
    },
}


class FullTimeseriesEvaluator:
    """乘员运动响应全维度评测器"""

    def __init__(self, config=None, ml_classifier=None):
        self.cfg = config or CONFIG
        self.df_raw = None
        self.df_clean = None
        self.fs = self.cfg['fs']
        self.common_t = None
        self.exp = {}   # 实验组 IMUx-1 (奇数)
        self.ctrl = {}  # 对照组 IMUx-2 (偶数)
        self.sw = None  # speed/wheel
        self.events = []
        self._external_events = None  # 外部注入的行为事件（优先级高于内部检测）
        self.results = {}  # 各级分析结果缓存

        # ── F2: ML 分类器集成 (P0) ──
        self._ml_classifier = ml_classifier
        self._ml_events = []  # ML 检测的事件缓存
        if ml_classifier is None:
            # 尝试自动加载
            try:
                from core.core.analysis.layer4_behavior_classification.hybrid_classifier import (
                    HybridBehaviorClassifier
                )
                self._ml_classifier = HybridBehaviorClassifier()
                logger.info("ML 分类器已集成到全量统计分析 (HybridBehaviorClassifier)")
            except Exception as e:
                logger.debug(f"ML 分类器加载失败 (非致命): {e}")

    def load_from_dataframe(self, df: pd.DataFrame):
        """从DataFrame加载数据"""
        logger.info("[1/10] 数据加载...")
        self.df_raw = df.copy()
        logger.info(f"  原始数据: {len(self.df_raw)}行 × {len(self.df_raw.columns)}列")

        imus = [str(im) for im in self.df_raw['imu_name'].unique() if isinstance(im, str)]
        logger.info(f"  IMU传感器: {len(imus)}个")
        
        for im in sorted(imus):
            num = int(im.split('_')[0].replace('IMU', ''))
            grp = '实验组' if num % 2 == 1 else '对照组'
            n = len(self.df_raw[self.df_raw['imu_name'] == im])
            body = im.split('_')[1] if '_' in im else '?'
            logger.info(f"    IMU{num:>2d} [{grp:>12s}] {body:>12s} → {n:>6d}行")

        for im in imus:
            sub = self.df_raw[self.df_raw['imu_name'] == im].sort_values('rel_time')
            base_cols = ['rel_time', 'Ax_m_s2', 'Ay_m_s2', 'Az_m_s2']
            gyro_candidates = [
                ['Gx_rad_s', 'Gy_rad_s', 'Gz_rad_s'],
                ['Gx_dps', 'Gy_dps', 'Gz_dps'],
            ]
            gyro_cols = []
            for cand in gyro_candidates:
                if all(c in sub.columns for c in cand):
                    gyro_cols = cand
                    break
            val_cols = base_cols + gyro_cols
            vals = sub[val_cols].values if all(c in sub.columns for c in base_cols) else None
            if vals is not None:
                num = int(im.split('_')[0].replace('IMU', ''))
                if num % 2 == 1:
                    self.exp[im] = vals
                else:
                    self.ctrl[im] = vals

        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if exp_keys and ctrl_keys:
            t_exp = set(round(t, 4) for t in self.exp[exp_keys[0]][:, 0])
            t_ctrl = set(round(t, 4) for t in self.ctrl[ctrl_keys[0]][:, 0])
            self.common_t = sorted(t_exp & t_ctrl)
            self.fs = 1.0 / (self.common_t[1] - self.common_t[0]) if len(self.common_t) > 1 else self.cfg['fs']
            logger.info(f"  对齐时间: {len(self.common_t)}点, fs≈{self.fs:.0f}Hz, {self.common_t[-1]-self.common_t[0]:.1f}s")
        else:
            logger.warning("  ⚠️ 缺少实验组或对照组!")

        sw_sub = None
        if 'channel' in self.df_raw.columns:
            sw_sub = self.df_raw[self.df_raw['channel'] == 'ch1'].drop_duplicates('rel_time').sort_values('rel_time')
        self.sw = []
        if sw_sub is not None and len(sw_sub) > 0:
            for t in self.common_t:
                match = sw_sub[abs(sw_sub['rel_time'] - t) < 1e-3]
                if len(match) > 0:
                    self.sw.append((t, match.iloc[0]['speed'], match.iloc[0]['wheel']))
                else:
                    self.sw.append((t, np.nan, np.nan))
        elif 'speed' in self.df_raw.columns and 'wheel' in self.df_raw.columns and len(self.common_t) > 0:
            sw_sub2 = self.df_raw.drop_duplicates('rel_time').sort_values('rel_time')
            for t in self.common_t:
                match = sw_sub2[abs(sw_sub2['rel_time'] - t) < 1e-3]
                if len(match) > 0:
                    self.sw.append((t, match.iloc[0]['speed'], match.iloc[0]['wheel']))
                else:
                    self.sw.append((t, np.nan, np.nan))
        self.sw = np.array(self.sw) if self.sw else np.array([])
        if len(self.sw) > 0:
            try:
                logger.info(f"  Speed: [{np.nanmin(self.sw[:,1]):.0f}~{np.nanmax(self.sw[:,1]):.0f}] km/h")
            except (ValueError, IndexError):
                logger.info(f"  Speed: N/A")

        self._aligned_cache = {}
        for imu_name in list(self.exp.keys()) + list(self.ctrl.keys()):
            source = self.exp.get(imu_name)
            if source is None:
                source = self.ctrl.get(imu_name)
            if source is None:
                continue
            n_data_cols = source.shape[1] - 1
            tmap = {round(row[0], 4): row[1:] for row in source}
            result = []
            for t in self.common_t:
                result.append([t] + list(tmap.get(t, [np.nan] * n_data_cols)))
            self._aligned_cache[imu_name] = np.array(result)

    def load_from_csv(self, csv_path: str):
        """从CSV文件加载数据"""
        df = pd.read_csv(csv_path)
        self.load_from_dataframe(df)

    def get_aligned(self, imu_name: str) -> Optional[np.ndarray]:
        """返回对齐到common_t的数据（优先使用缓存）"""
        if hasattr(self, '_aligned_cache') and imu_name in self._aligned_cache:
            return self._aligned_cache[imu_name]
        source = self.exp.get(imu_name)
        if source is None:
            source = self.ctrl.get(imu_name)
        if source is None:
            return None
        tmap = {round(row[0], 4): row[1:] for row in source}
        n_data_cols = source.shape[1] - 1
        result = []
        for t in self.common_t:
            result.append([t] + list(tmap.get(t, [np.nan] * n_data_cols)))
        return np.array(result)

    def detect_events(self):
        """Step 2: 统一事件检测 — ML 25种细粒度事件 (主力) + 规则回退 (22种)

        优先级:
          1. ML (hybrid_classifier) → 25 种, 85.7% 准确率
          2. 规则回退 (DrivingEventDetector) → 22 种, 规则驱动
          3. 废弃: 旧 4 种粗粒度阈值检测 (制动减速/加速/转向/变道/复合工况)
        """
        logger.info("[2/10] 事件检测 (统一 ML 25 类)...")

        if self.sw is None or len(self.sw) == 0:
            logger.warning("  无速度数据，跳过事件检测")
            return

        # ── 优先级 1: ML 检测 (主力) ──
        if self._ml_classifier and self._ml_classifier.ml_classifier.is_ready():
            logger.info("  使用 ML 检测 (HybridBehaviorClassifier, 25 种)")
            self._detect_by_ml()
        else:
            # ── 优先级 2: 规则回退 (DrivingEventDetector, 22 种) ──
            logger.info("  ML 未就绪，使用规则回退 (DrivingEventDetector, 22 种)")
            self._detect_by_rule_fallback()

        etype_counts = pd.Series([ev['type'] for ev in self.events]).value_counts()
        logger.info(f"  检测到 {len(self.events)} 个事件:")
        for t, c in etype_counts.items():
            cn = self._cn_name(t)
            logger.info(f"    {cn}({t}): {c}次")

        self.results['detected_events'] = self.events

    def _detect_by_ml(self):
        """ML 检测 — 25 种细粒度事件 (主力路径)

        使用 HybridBehaviorClassifier 滑动窗口分类，
        结果直接写入 self.events。
        """
        self.events = []
        ml_events = self.detect_ml_events()

        if not ml_events:
            logger.warning("  ML 未检测到事件，回退到规则检测")
            self._detect_by_rule_fallback()
            return

        # 将 ML 事件格式化为统一事件格式
        for ml_ev in ml_events:
            etype = ml_ev.get('type', 'unknown')
            # 通过 DEPRECATED_EVENT_MAPPING 统一事件名
            from core.core.analysis.core_types import DEPRECATED_EVENT_MAPPING
            unified_type = DEPRECATED_EVENT_MAPPING.get(etype, etype)

            self.events.append({
                't_start': ml_ev['t_start'],
                't_end': ml_ev['t_end'],
                'type': unified_type,
                'event_type': unified_type,
                'confidence': ml_ev.get('confidence', 0.0),
                'method': 'ml',
                'idx_start': ml_ev.get('idx_start', 0),
                'idx_end': ml_ev.get('idx_end', 0),
                'duration': ml_ev.get('duration', 0.0),
                'speed_start': 0.0,
                'speed_end': 0.0,
                'wheel_change': 0.0,
            })

    def _detect_by_rule_fallback(self):
        """规则回退检测 — 22 种细粒度事件 (ML 不可用时)

        使用 DrivingEventDetector 替代旧的 4 种粗粒度阈值检测。
        """
        self.events = []

        try:
            from core.core.analysis.layer3_maneuver_segmentation.event_detector import (
                DrivingEventDetector, EVENT_TYPES
            )
            from core.core.analysis.core_types import DEPRECATED_EVENT_MAPPING

            # 构建 records 数据
            records = []
            if self.sw is not None and len(self.sw) > 0:
                for i in range(len(self.sw)):
                    rec = {
                        'rel_time': self.sw[i, 0],
                        'speed': self.sw[i, 1],
                        'wheel': self.sw[i, 2],
                    }
                    records.append(rec)

            if not records:
                logger.warning("  无法构建 records 数据，跳过规则回退")
                return

            # 使用 DrivingEventDetector 检测所有事件
            detector = DrivingEventDetector.from_records(records)
            rule_events = detector.detect_all()

            for evt in rule_events:
                etype = evt.event_type
                # 通过 DEPRECATED_EVENT_MAPPING 统一 (cruising→constant_speed 等)
                unified_type = DEPRECATED_EVENT_MAPPING.get(etype, etype)
                cn_name = EVENT_TYPES.get(etype, etype)

                # 计算 idx
                t_start = evt.t_start
                t_end = evt.t_end
                if self.common_t and len(self.common_t) > 1:
                    dt = self.common_t[1] - self.common_t[0]
                    idx_start = max(0, int(t_start / dt))
                    idx_end = min(len(self.common_t) - 1, int(t_end / dt))
                else:
                    idx_start = idx_end = 0

                self.events.append({
                    't_start': t_start,
                    't_end': t_end,
                    'type': unified_type,
                    'event_type': unified_type,
                    'cn_name': cn_name,
                    'confidence': evt.confidence,
                    'method': 'rule_fallback',
                    'idx_start': idx_start,
                    'idx_end': idx_end,
                    'duration': evt.duration_s,
                    'speed_start': evt.features.get('speed_from', 0.0),
                    'speed_end': evt.features.get('speed_to', 0.0),
                    'wheel_change': 0.0,
                })

            logger.info(f"  规则回退检测完成: {len(self.events)} 个事件")

        except Exception as e:
            logger.error(f"  规则回退检测失败: {e}", exc_info=True)

    @staticmethod
    def _cn_name(event_type: str) -> str:
        """事件类型 → 中文名"""
        from core.core.analysis.core_types import BEHAVIOR_LABELS_CN
        return BEHAVIOR_LABELS_CN.get(event_type, event_type)

    def set_external_events(self, events: List[Dict]):
        from core.core.analysis.layer3_maneuver_segmentation.event_detector import EVENT_TYPES
        self._external_events = events
        self.events = []
        if not self.common_t or len(self.common_t) == 0:
            logger.warning("  无对齐时间轴，无法转换外部事件")
            return
        t0 = self.common_t[0]
        t1 = self.common_t[-1]
        dt = self.common_t[1] - self.common_t[0] if len(self.common_t) > 1 else 1.0 / self.fs
        for evt in events:
            ts = evt.get('t_start', 0)
            te = evt.get('t_end', 0)
            if te <= t0 or ts >= t1:
                continue
            s = max(0, int((ts - t0) / dt))
            e = min(len(self.common_t) - 1, int((te - t0) / dt))
            if e <= s:
                continue
            etype = evt.get('event_type', evt.get('type', 'unknown'))
            cn_type = EVENT_TYPES.get(etype, etype)
            self.events.append({
                't_start': ts, 't_end': te,
                'type': cn_type,
                'event_type': etype,
                'speed_start': evt.get('speed_at_start', 0),
                'speed_end': evt.get('speed_at_end', 0),
                'wheel_change': 0,
                'idx_start': s, 'idx_end': e,
                'duration': te - ts,
            })
        etype_counts = pd.Series([ev['type'] for ev in self.events]).value_counts()
        logger.info(f"  [外部事件] 注入 {len(self.events)} 个行为事件（{len(etype_counts)} 种类型）:")
        for t, c in etype_counts.items():
            logger.info(f"    {t}: {c}次")

    def detect_ml_events(self) -> List[Dict]:
        """F2: ML 滑动窗口检测 — 从全量时序数据中提取 ML 事件

        使用 HybridBehaviorClassifier 对滑动窗口进行分类，
        结果注入到 self.events 中，与规则检测事件合并。

        Returns:
            ML 检测到的事件列表
        """
        if not self._ml_classifier or not self._ml_classifier._ml_classifier.is_ready():
            logger.info("ML 分类器未就绪，跳过 ML 检测")
            return []

        if not self.exp:
            logger.warning("无实验组数据，跳过 ML 检测")
            return []

        ml_events = []
        try:
            from core.core.analysis.core_types import ManeuverEvent, FrameFeatures, BehaviorCategory

            # 使用第一个实验组 IMU 作为主通道
            primary_imu = list(self.exp.keys())[0]
            aligned = self.get_aligned(primary_imu)
            if aligned is None:
                return []

            window_samples = int(self.cfg['window_sec'] * self.fs)
            step_samples = int(self.cfg['step_sec'] * self.fs)

            for i in range(0, len(aligned) - window_samples, step_samples):
                win = aligned[i:i + window_samples]
                ax = win[:, 1] if win.shape[1] > 1 else win[:, 0]
                ay = win[:, 2] if win.shape[1] > 2 else np.zeros_like(ax)
                az = win[:, 3] if win.shape[1] > 3 else np.zeros_like(ax)

                t_start = win[0, 0]

                features = FrameFeatures(timestamp=t_start)
                features.temporal['ax_mean'] = float(np.mean(ax))
                features.temporal['ax_std'] = float(np.std(ax))
                features.temporal['ax_rms'] = float(np.sqrt(np.mean(ax**2)))
                features.temporal['ay_mean'] = float(np.mean(ay))
                features.temporal['ay_std'] = float(np.std(ay))
                features.temporal['ay_rms'] = float(np.sqrt(np.mean(ay**2)))
                features.temporal['az_mean'] = float(np.mean(az))
                features.temporal['az_std'] = float(np.std(az))
                features.temporal['az_rms'] = float(np.sqrt(np.mean(az**2)))

                event = ManeuverEvent(
                    id=f'ml_fts_{i}',
                    type='unknown',
                    category=BehaviorCategory.LONGITUDINAL,
                    start_time=t_start,
                    end_time=win[-1, 0],
                    duration=win[-1, 0] - t_start,
                    confidence=0.0,
                )

                ml_event = self._ml_classifier.classify(event, features)
                if ml_event.confidence >= 0.75:
                    idx_start = int(t_start / (self.common_t[1] - self.common_t[0]))
                    idx_end = idx_start + window_samples
                    ml_events.append({
                        't_start': t_start,
                        't_end': win[-1, 0],
                        'type': ml_event.type,
                        'event_type': ml_event.type,
                        'confidence': ml_event.confidence,
                        'method': 'ml',
                        'idx_start': idx_start,
                        'idx_end': min(idx_end, len(self.common_t) - 1),
                        'duration': win[-1, 0] - t_start,
                    })

            # 去重合并相邻同类事件
            ml_events = self._deduplicate_ml_events(ml_events)

            logger.info(f"ML 滑动窗口检测完成: {len(ml_events)} 个事件 (confidence≥0.75)")

            # 合并到 events 列表
            if ml_events:
                existing_starts = set(
                    (ev.get('t_start', 0), ev.get('type', '')) for ev in self.events
                )
                for ml_ev in ml_events:
                    key = (ml_ev['t_start'], ml_ev['type'])
                    if key not in existing_starts:
                        self.events.append(ml_ev)

        except Exception as e:
            logger.error(f"ML 滑动窗口检测失败: {e}", exc_info=True)

        self._ml_events = ml_events
        return ml_events

    def _deduplicate_ml_events(self, events: List[Dict]) -> List[Dict]:
        """合并相邻同类 ML 事件"""
        if len(events) < 2:
            return events

        events.sort(key=lambda e: e['t_start'])
        merged = []
        current = dict(events[0])

        for next_ev in events[1:]:
            if next_ev['type'] == current['type'] and \
               next_ev['t_start'] - current['t_end'] < 0.5:
                # 合并
                current['t_end'] = next_ev['t_end']
                current['idx_end'] = next_ev['idx_end']
                current['duration'] = current['t_end'] - current['t_start']
                current['confidence'] = max(current['confidence'], next_ev['confidence'])
            else:
                merged.append(current)
                current = dict(next_ev)

        merged.append(current)
        return merged

    def _get_sternum(self):
        for k in self.exp:
            if '胸骨' in k or 'sternum' in k.lower() or '剑突' in k:
                return self.get_aligned(k)
        return None

    def window_analysis(self) -> pd.DataFrame:
        """全时域滑动窗口连续对比"""
        logger.info("[3/10] 全时域滑动窗口分析...")
        ws = int(self.cfg['window_sec'] * self.fs)
        ss = int(self.cfg['step_sec'] * self.fs)
        
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return pd.DataFrame()
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])
        exp_sternum = self._get_sternum()

        results = []
        for start in range(0, len(self.common_t) - ws, ss):
            end = start + ws
            speed_val = np.nan
            if len(self.sw) > 0 and self.sw.ndim == 2:
                try:
                    speed_val = np.nanmean(self.sw[start:end, 1])
                except (IndexError, ValueError):
                    speed_val = np.nan
            win = {'t_center': self.common_t[start + ws // 2],
                   'speed': speed_val}

            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                ev = exp_head[start:end, col]
                cv = ctrl_head[start:end, col]
                val = ~np.isnan(ev) & ~np.isnan(cv)
                if val.sum() > 50:
                    e_rms = np.sqrt(np.mean(ev[val]**2))
                    c_rms = np.sqrt(np.mean(cv[val]**2))
                    win[f'e_{axis}_RMS'] = e_rms
                    win[f'c_{axis}_RMS'] = c_rms
                    win[f'e_{axis}_Peak'] = np.max(np.abs(ev[val]))
                    win[f'c_{axis}_Peak'] = np.max(np.abs(cv[val]))
                    if c_rms > 1e-3:
                        win[f'atten_{axis}_pct'] = (1 - e_rms / c_rms) * 100

            if exp_sternum is not None:
                for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                    col = axis_idx + 1
                    hv = exp_head[start:end, col]
                    sv = exp_sternum[start:end, col]
                    val = ~np.isnan(hv) & ~np.isnan(sv)
                    if val.sum() > 50:
                        h_rms = np.sqrt(np.mean(hv[val]**2))
                        s_rms = np.sqrt(np.mean(sv[val]**2))
                        if s_rms > 1e-3:
                            win[f'transfer_{axis}'] = h_rms / s_rms

            for label, data in [('e', exp_head), ('c', ctrl_head)]:
                vals = np.sqrt(data[start:end, 1]**2 + data[start:end, 2]**2 + data[start:end, 3]**2)
                valid = ~np.isnan(vals)
                win[f'{label}_total_RMS'] = np.sqrt(np.mean(vals[valid]**2))

            results.append(win)

        df_win = pd.DataFrame(results)
        for ax in ['Ax', 'Ay', 'Az']:
            col = f'atten_{ax}_pct'
            if col in df_win.columns:
                vals = df_win[col].dropna()
                logger.info(f"  {ax}衰减: mean={vals.mean():.1f}%, median={vals.median():.1f}%, "
                          f"正值比={(vals>0).mean()*100:.1f}%")
        self.results['windows'] = df_win
        return df_win

    def event_analysis(self) -> pd.DataFrame:
        """事件级精细化对比"""
        logger.info("[4/10] 事件级精细化分析...")
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return pd.DataFrame()
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])
        exp_sternum = self._get_sternum()

        results = []
        for ev in self.events:
            s, e = ev['idx_start'], min(ev['idx_end'] + 1, len(self.common_t))
            if e - s < int(self.fs * 0.1):
                continue

            row = {'event': ev['type'], 't_start': ev['t_start'], 't_end': ev['t_end'],
                   'duration': ev['duration'], 'speed_start': ev['speed_start']}

            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                evals = exp_head[s:e, col]
                cvals = ctrl_head[s:e, col]
                valid = ~np.isnan(evals) & ~np.isnan(cvals)
                if valid.sum() > 50:
                    row[f'e_{axis}_RMS'] = np.sqrt(np.mean(evals[valid]**2))
                    row[f'c_{axis}_RMS'] = np.sqrt(np.mean(cvals[valid]**2))
                    if row[f'c_{axis}_RMS'] > 1e-3:
                        row[f'atten_{axis}_pct'] = (1 - row[f'e_{axis}_RMS'] / row[f'c_{axis}_RMS']) * 100

            if exp_sternum is not None:
                for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                    col = axis_idx + 1
                    hv = exp_head[s:e, col]
                    sv = exp_sternum[s:e, col]
                    valid = ~np.isnan(hv) & ~np.isnan(sv)
                    if valid.sum() > 50:
                        h_rms = np.sqrt(np.mean(hv[valid]**2))
                        s_rms = np.sqrt(np.mean(sv[valid]**2))
                        if s_rms > 1e-3:
                            row[f'transfer_{axis}'] = h_rms / s_rms

            results.append(row)

        df_ev = pd.DataFrame(results)
        self.results['events'] = df_ev
        logger.info(f"  分析 {len(df_ev)} 个事件窗口")
        return df_ev

    def spectrum_analysis(self) -> Dict[str, Any]:
        """频谱分析 + 频段衰减 + 相干性"""
        logger.info("[5/10] 频谱分析...")
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return {}
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])
        nfft = self.cfg['nfft_welch']

        spec = {}
        for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
            col = axis_idx + 1
            evals = exp_head[:, col]
            cvals = ctrl_head[:, col]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)

            f_e, Pxx_e = signal.welch(evals[valid], fs=self.fs, nperseg=nfft)
            f_c, Pxx_c = signal.welch(cvals[valid], fs=self.fs, nperseg=nfft)
            f_coh, coh = signal.coherence(evals[valid], cvals[valid], fs=self.fs, nperseg=nfft)

            mask = (f_e >= 0.1) & (f_e <= 80)
            ratio = np.divide(Pxx_e[mask], Pxx_c[mask],
                              out=np.ones_like(Pxx_e[mask]) * np.nan,
                              where=Pxx_c[mask] > 1e-15)

            bands_atten = {}
            for bname, (flo, fhi) in self.cfg['freq_bands'].items():
                bm = (f_e[mask] >= flo) & (f_e[mask] <= fhi)
                if bm.sum() > 0:
                    bands_atten[bname] = (1 - np.nanmean(ratio[bm])) * 100

            spec[axis] = {
                'freq': f_e[mask], 'exp_psd': Pxx_e[mask],
                'ctrl_psd': Pxx_c[mask], 'ratio': ratio,
                'coherence': coh[mask] if len(coh) == len(mask) else coh[:sum(mask)],
                'bands_atten': bands_atten
            }
            logger.info(f"  {axis}: " + ", ".join([f"{b}={v:.1f}%" for b, v in bands_atten.items() if 'Hz' in b]))

        self.results['spectrum'] = spec
        return spec

    def stft_analysis(self) -> Dict[str, Any]:
        """短时傅里叶变换时频分析"""
        logger.info("[6/10] 时频分析 (STFT)...")
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return {}
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])

        stft_results = {}
        for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
            col = axis_idx + 1
            f_e, t_e, Zxx_e = signal.stft(exp_head[:, col], fs=self.fs,
                                           nperseg=self.cfg['nfft_stft'],
                                           noverlap=self.cfg['stft_overlap'])
            f_c, t_c, Zxx_c = signal.stft(ctrl_head[:, col], fs=self.fs,
                                           nperseg=self.cfg['nfft_stft'],
                                           noverlap=self.cfg['stft_overlap'])
            stft_results[axis] = {
                'f': f_e, 't': t_e + self.common_t[0],
                'exp_spec': np.abs(Zxx_e), 'ctrl_spec': np.abs(Zxx_c),
            }

        self.results['stft'] = stft_results
        return stft_results

    def statistical_analysis(self) -> Dict[str, Any]:
        """统计学检验"""
        logger.info("[7/10] 统计学分析...")
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return {}
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])

        stats_results = {}
        for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
            col = axis_idx + 1
            evals = exp_head[:, col]
            cvals = ctrl_head[:, col]
            valid = ~np.isnan(evals) & ~np.isnan(cvals)

            ds_factor = 10
            e_down = evals[valid][::ds_factor]
            c_down = cvals[valid][::ds_factor]
            t_stat, p_val = stats.ttest_rel(e_down, c_down)

            d = (np.mean(e_down) - np.mean(c_down)) / np.sqrt((np.std(e_down)**2 + np.std(c_down)**2) / 2)

            diff = e_down - c_down
            ci_lo, ci_hi = np.percentile(diff, [2.5, 97.5])

            e_rms = np.sqrt(np.mean(evals[valid]**2))
            c_rms = np.sqrt(np.mean(cvals[valid]**2))
            atn = (1 - e_rms / c_rms) * 100 if c_rms > 1e-3 else np.nan

            stats_results[axis] = {
                't_stat': t_stat, 'p_value': p_val,
                'cohens_d': d, 'ci_lo': ci_lo, 'ci_hi': ci_hi,
                'e_rms': e_rms, 'c_rms': c_rms, 'attenuation_pct': atn,
                'significant': '***' if p_val < 0.001 else ('**' if p_val < 0.01 else ('*' if p_val < 0.05 else 'ns'))
            }
            logger.info(f"  {axis}: t={t_stat:.2f}, p={p_val:.2e}, d={d:.2f}, atn={atn:.1f}% {stats_results[axis]['significant']}")

        self.results['statistics'] = stats_results
        return stats_results

    def comprehensive_metrics(self) -> Dict[str, float]:
        """综合评价指标 (VDV, Crest Factor, SEAT等效, 传递系数)"""
        logger.info("[8/10] 综合评价指标...")
        exp_keys = list(self.exp.keys())
        ctrl_keys = list(self.ctrl.keys())
        if not exp_keys or not ctrl_keys:
            logger.warning("  缺少实验组或对照组数据")
            return {}
            
        exp_head = self.get_aligned(exp_keys[0])
        ctrl_head = self.get_aligned(ctrl_keys[0])
        exp_sternum = self._get_sternum()

        metrics = {}
        for label, data in [('exp', exp_head), ('ctrl', ctrl_head),
                             ('sternum', exp_sternum) if exp_sternum is not None else ('_skip', None)]:
            if data is None:
                continue
            for axis_idx, axis in enumerate(['Ax', 'Ay', 'Az']):
                col = axis_idx + 1
                vals = data[:, col]
                valid = vals[~np.isnan(vals)]
                if len(valid) < 100:
                    continue
                prefix = f'{label}_{axis}'
                metrics[f'{prefix}_RMS'] = np.sqrt(np.mean(valid**2))
                metrics[f'{prefix}_Peak'] = np.max(np.abs(valid))
                metrics[f'{prefix}_CrestFactor'] = metrics[f'{prefix}_Peak'] / metrics[f'{prefix}_RMS'] if metrics[f'{prefix}_RMS'] > 1e-6 else np.nan
                metrics[f'{prefix}_VDV'] = (np.sum(valid**4) / self.fs) ** 0.25
                metrics[f'{prefix}_Skewness'] = stats.skew(valid)
                metrics[f'{prefix}_Kurtosis'] = stats.kurtosis(valid, fisher=True)
                metrics[f'{prefix}_MAV'] = np.mean(np.abs(valid))
                metrics[f'{prefix}_ImpulseFactor'] = metrics[f'{prefix}_Peak'] / metrics[f'{prefix}_MAV'] if metrics[f'{prefix}_MAV'] > 1e-6 else np.nan

        for label, data in [('exp', exp_head), ('ctrl', ctrl_head)]:
            total = np.sqrt(data[:, 1]**2 + data[:, 2]**2 + data[:, 3]**2)
            valid = total[~np.isnan(total)]
            if len(valid) >= 100:
                metrics[f'{label}_total_RMS'] = np.sqrt(np.mean(valid**2))
                metrics[f'{label}_total_Peak'] = np.max(np.abs(valid))
            metrics[f'{label}_total_VDV'] = (np.sum(valid**4) / self.fs) ** 0.25 if len(valid) >= 100 else np.nan

        self.results['metrics'] = metrics
        logger.info(f"  计算 {len(metrics)} 个指标")
        return metrics

    def run_all(self) -> Dict[str, Any]:
        """执行全部分析流程"""
        self.detect_events()
        self.window_analysis()
        self.event_analysis()
        self.spectrum_analysis()
        self.stft_analysis()
        self.statistical_analysis()
        self.comprehensive_metrics()
        return self.results

    def generate_report(self, out_dir: str = '.') -> str:
        """生成综合评测报告"""
        logger.info("[10/10] 生成评测报告...")
        spec = self.results.get('spectrum', {})
        stats = self.results.get('statistics', {})
        metrics = self.results.get('metrics', {})
        windows = self.results.get('windows', pd.DataFrame())

        lines = []
        lines.append("# 主动控制座椅悬架 — 乘员头部运动响应全维度评测报告")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"分析维度: 时域/频域/时频/事件/统计/综合指标")
        lines.append("")

        lines.append("## 1. 数据概况")
        if self.common_t:
            lines.append(f"- 采样率: {self.fs:.0f} Hz")
            lines.append(f"- 时长: {self.common_t[-1]-self.common_t[0]:.1f} s")
        lines.append(f"- 检测事件: {len(self.events)} 个")
        lines.append(f"- 传感器: {len(self.exp) + len(self.ctrl)} 个IMU")
        lines.append(f"- 实验组: {len(self.exp)} 个传感器")
        lines.append(f"- 对照组: {len(self.ctrl)} 个传感器")
        lines.append("")

        lines.append("## 2. 频段衰减效果 (实验组 vs 对照组)")
        lines.append("| 频段 | Ax | Ay | Az |")
        lines.append("|:---|---:|---:|---:|")
        for band in ['0.1-0.5Hz', '0.5-1Hz', '1-5Hz', '5-20Hz', '20-80Hz']:
            vals = []
            for ax in ['Ax', 'Ay', 'Az']:
                v = spec.get(ax, {}).get('bands_atten', {}).get(band, np.nan)
                vals.append(f"{v:.1f}%" if not np.isnan(v) else "—")
            lines.append(f"| {band} | {vals[0]} | {vals[1]} | {vals[2]} |")
        lines.append("")
        # ── 嵌入图表 ──
        lines.append("![PSD频谱对比](fig3_spectrum.png)")
        lines.append("![衰减比](fig4_spectrum_ratio.png)")
        lines.append("![频段雷达图](fig5_band_radar.png)")
        lines.append("")

        # ── P1: 频段衰减雷达图数据 ──
        lines.append("## 2.1 频段衰减雷达图 (Radar Chart Data)")
        lines.append("```json")
        radar_data = {
            "bands": ["0.1-0.5Hz", "0.5-1Hz", "1-5Hz", "5-20Hz", "20-80Hz"],
            "axes": ["Ax", "Ay", "Az"],
            "attenuation_pct": {}
        }
        for ax in ['Ax', 'Ay', 'Az']:
            radar_data["attenuation_pct"][ax] = {
                band: round(spec.get(ax, {}).get('bands_atten', {}).get(band, np.nan), 1)
                if not np.isnan(spec.get(ax, {}).get('bands_atten', {}).get(band, np.nan))
                else None
                for band in radar_data["bands"]
            }
        import json
        lines.append(json.dumps(radar_data, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

        lines.append("## 3. 综合评价指标")
        lines.append("| 指标 | 实验组 | 对照组 | 改善幅度 |")
        lines.append("|:---|---:|---:|---:|")
        for ax in ['Ax', 'Ay', 'Az']:
            e_vdv = metrics.get(f'exp_{ax}_VDV', np.nan)
            c_vdv = metrics.get(f'ctrl_{ax}_VDV', np.nan)
            e_rms = metrics.get(f'exp_{ax}_RMS', np.nan)
            c_rms = metrics.get(f'ctrl_{ax}_RMS', np.nan)
            if not np.isnan(e_vdv) and not np.isnan(c_vdv):
                imp = ((c_vdv - e_vdv) / abs(c_vdv)) * 100 if abs(c_vdv) > 1e-6 else np.nan
                lines.append(f"| {ax} VDV | {e_vdv:.2f} | {c_vdv:.2f} | {imp:+.1f}% |")
            if not np.isnan(e_rms) and not np.isnan(c_rms):
                imp = ((c_rms - e_rms) / abs(c_rms)) * 100 if abs(c_rms) > 1e-6 else np.nan
                lines.append(f"| {ax} RMS | {e_rms:.3f} | {c_rms:.3f} | {imp:+.1f}% |")
        lines.append("")

        lines.append("## 4. 统计学检验")
        lines.append("| 轴 | t值 | p值 | Cohen's d | RMS衰减 | 显著性 |")
        lines.append("|:---|---:|---:|---:|---:|:---:|")
        for ax in ['Ax', 'Ay', 'Az']:
            s = stats.get(ax, {})
            lines.append(f"| {ax} | {s.get('t_stat', np.nan):.2f} | {s.get('p_value', 1):.2e} | "
                         f"{s.get('cohens_d', np.nan):.3f} | {s.get('attenuation_pct', np.nan):.1f}% | "
                         f"{s.get('significant', '—')} |")
        lines.append("")

        lines.append("## 5. 驾驶事件摘要")
        for i, ev in enumerate(self.events[:10]):
            lines.append(f"- **E{i+1}** [{ev['type']}] t={ev['t_start']:.1f}s dur={ev['duration']:.2f}s "
                         f"speed {ev['speed_start']:.0f}→{ev['speed_end']:.0f} km/h")
        if len(self.events) > 10:
            lines.append(f"- ... 还有 {len(self.events) - 10} 个事件")
        lines.append("")
        # ── 嵌入更多图表 ──
        lines.append("## 4.1 统计可视化")
        lines.append("![统计仪表盘](fig7_statistics.png)")
        lines.append("![统计特征热力图](fig9_stat_features.png)")
        lines.append("")
        lines.append("![全时程概览](fig1_overview.png)")
        lines.append("![事件RMS对比](fig2_events.png)")
        lines.append("![时频分析](fig6_stft.png)")
        lines.append("![滑动窗口衰减](fig8_window_atten.png)")
        lines.append("")

        lines.append("---\n*本报告由 FullTimeseriesEvaluator v2.0 自动生成*")

        report_md = "\n".join(lines)
        
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'EVALUATION_REPORT.md'), 'w', encoding='utf-8') as f:
            f.write(report_md)

        if len(windows) > 0:
            windows.to_csv(os.path.join(out_dir, 'window_analysis.csv'), index=False)
        events_df = self.results.get('events', pd.DataFrame())
        if len(events_df) > 0:
            events_df.to_csv(os.path.join(out_dir, 'event_analysis.csv'), index=False)
        pd.DataFrame([metrics]).to_csv(os.path.join(out_dir, 'comprehensive_metrics.csv'), index=False)

        logger.info(f"  报告: EVALUATION_REPORT.md, CSVs: window/event/metrics")
        return report_md