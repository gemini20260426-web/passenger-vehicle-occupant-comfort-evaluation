#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据回放控制器
从 MultiSourceCache 按时间窗口读取数据，以可控速率发射 Signal 给右侧面板
支持两种模式：快速回放（使用AnalysisResultCache）和重新分析（使用原始数据）
"""

import time
import logging
from typing import Dict, Any, List, Optional

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication

from ..analysis.event_distributor import EventDistributor

logger = logging.getLogger(__name__)


class MultiSourceReplayController(QObject):
    """多源数据回放控制器 — 替代 DataBridge 的 UI 信号发射角色"""

    sensor_data_batch_received = Signal(list)
    imu_data_batch_received = Signal(list)
    cnap_data_batch_received = Signal(list)
    can_raw_data_batch_received = Signal(list)
    replay_progress = Signal(float)
    replay_state_changed = Signal(str)
    replay_mode_changed = Signal(str)
    
    # 新增：分析结果相关信号
    frame_result_ready = Signal(object)
    realtime_monitor_data = Signal(dict)
    behavior_event_ready = Signal(object)
    playback_range_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._cache = None
        self._analysis_cache = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._cursor = 0.0
        self._time_min = 0.0
        self._time_max = 0.0
        self._window_size = 1.0
        self._speed = 1.0
        self._tick_interval_ms = 250
        self._state = 'stopped'
        self._batch_size = 100
        self._max_records_per_tick = 5000
        
        # 回放模式：'fast'（快速）或 'reanalyze'（重新分析）
        self._replay_mode = 'fast'

        self._tick_count = 0
        self._total_emitted = 0
        self._active_sources = None
        
        self._last_result_emit_time = 0.0

        self._playback_start = 0.0
        self._playback_end = 0.0
        self._use_playback_range = False

        self._events_cache = []
        self._events_sorted = False

        logger.info("MultiSourceReplayController 已创建")

    def load_cache(self, cache) -> bool:
        self._cache = cache
        self._time_min, self._time_max = cache.get_time_range()
        self._cursor = self._time_min
        stats = cache.get_stats()
        self._available_source_types = stats['source_types']
        logger.info(f"回放控制器已加载缓存: {stats['total_records']}条, "
                     f"时长={stats['duration']:.1f}s, "
                     f"类型={stats['source_types']}")
        return stats['total_records'] > 0
    
    def load_analysis_cache(self, analysis_cache, rebuild_events: bool = True) -> bool:
        """加载分析结果缓存，同时重建事件记录器
        
        Args:
            analysis_cache: 分析结果缓存
            rebuild_events: 是否从缓存重建事件记录器
        """
        self._analysis_cache = analysis_cache
        if analysis_cache:
            t_min, t_max = analysis_cache.get_time_range()
            if self._cache:
                self._time_min = min(self._time_min, t_min)
                self._time_max = max(self._time_max, t_max)
            else:
                self._time_min = t_min
                self._time_max = t_max
            self._cursor = self._time_min
            stats = analysis_cache.get_stats()
            logger.info(f"已加载分析结果缓存: {stats['total_records']}条FrameResult")
            
            if rebuild_events:
                try:
                    from core.core.data_processing.event_data_mapper import get_event_mapper, reset_event_mapper
                    reset_event_mapper()
                    event_mapper = get_event_mapper()
                    
                    all_events = analysis_cache.get_all_maneuver_events()
                    if all_events:
                        event_mapper.batch_register_maneuver_events(all_events)
                        logger.info(f"已从缓存重建事件记录器: {len(all_events)}个事件")
                    self._events_cache = all_events
                    self._events_sorted = True
                except Exception as e:
                    logger.warning(f"重建事件记录器失败: {e}")
                    self._events_cache = []
                    self._events_sorted = False
            
            has_results = stats['total_records'] > 0
            if not has_results:
                all_events = analysis_cache.get_all_maneuver_events()
                if all_events:
                    logger.info(f"分析结果缓存无FrameResult但有{len(all_events)}个事件，仍视为有效缓存")
                    return True
            
            return has_results
        return False
    
    def set_replay_mode(self, mode: str):
        """设置回放模式：'fast' 或 'reanalyze'"""
        if mode not in ('fast', 'reanalyze'):
            logger.warning(f"无效的回放模式: {mode}, 使用 'fast'")
            mode = 'fast'
        
        if mode == 'fast' and self._analysis_cache is None:
            logger.warning("快速回放模式需要 AnalysisResultCache")
            mode = 'reanalyze'
        
        self._replay_mode = mode
        logger.info(f"回放模式已设置: {self._replay_mode}")
        self.replay_mode_changed.emit(self._replay_mode)
    
    def get_replay_mode(self) -> str:
        return self._replay_mode

    def get_available_source_types(self):
        return getattr(self, '_available_source_types', [])

    def refresh_available_source_types(self):
        if self._cache:
            self._available_source_types = self._cache.get_source_types()
            logger.info(f"回放数据源类型已刷新: {self._available_source_types}")

    def set_active_sources(self, source_types: list):
        self._active_sources = source_types if source_types else None
        logger.info(f"回放数据源过滤: {self._active_sources or '全部'}")

        was_playing = self._state == 'playing'
        if was_playing:
            self._timer.stop()

        self._cursor = 0.0
        if self._cache and self._active_sources:
            t_min, t_max = self._cache.get_time_range_for_sources(self._active_sources)
            if t_max is not None:
                self._time_min = t_min
                self._time_max = t_max
        elif self._cache:
            self._time_min, self._time_max = self._cache.get_time_range()

        self._emit_progress()

        if was_playing:
            self._timer.start(self._tick_interval_ms)
            logger.info(f"数据源切换，光标重置: cursor=0.0, time_max={self._time_max:.1f}")

    def play(self):
        if self._replay_mode == 'fast' and not self._analysis_cache:
            logger.warning("快速回放模式需要 AnalysisResultCache，切换到重新分析模式")
            self._replay_mode = 'reanalyze'
        if not self._cache and not self._analysis_cache:
            logger.warning("无缓存数据，无法播放")
            return
        if self._state == 'playing':
            return
        self._state = 'playing'
        self._timer.start(self._tick_interval_ms)
        self.replay_state_changed.emit('playing')
        logger.info(f"回放开始: cursor={self._cursor:.3f}, speed={self._speed}x, mode={self._replay_mode}")

    def pause(self):
        if self._state != 'playing':
            return
        self._state = 'paused'
        self._timer.stop()
        self.replay_state_changed.emit('paused')
        logger.info(f"回放暂停: cursor={self._cursor:.3f}")

    def stop(self):
        self._state = 'stopped'
        self._timer.stop()
        self._cursor = self._playback_start if self._use_playback_range else self._time_min
        self._tick_count = 0
        self._total_emitted = 0
        self._last_result_emit_time = 0.0
        self.replay_state_changed.emit('stopped')
        logger.info("回放停止")

    def seek(self, rel_time: float):
        effective_end = self._get_effective_end()
        effective_start = self._playback_start if self._use_playback_range else self._time_min
        self._cursor = max(effective_start, min(effective_end, rel_time))
        self._emit_progress()
        logger.info(f"回放跳转: cursor={self._cursor:.3f}")

    def set_speed(self, multiplier: float):
        self._speed = max(0.1, min(20.0, multiplier))
        logger.info(f"回放速度: {self._speed}x")

    def set_window_size(self, seconds: float):
        self._window_size = max(0.1, min(10.0, seconds))

    def set_batch_size(self, size: int):
        self._batch_size = max(50, min(2000, size))

    def set_playback_range(self, start_time: float, end_time: float = 0.0):
        was_playing = self._state == 'playing'
        if was_playing:
            self._timer.stop()

        self._playback_start = max(self._time_min, start_time)
        if end_time > 0:
            self._playback_end = min(end_time, self._time_max)
            self._use_playback_range = True
        else:
            self._playback_end = self._time_max
            self._use_playback_range = False

        self._cursor = self._playback_start
        self._tick_count = 0
        self._total_emitted = 0
        self._last_result_emit_time = 0.0
        self._emit_progress()

        logger.info(f"回放区间已设置: [{self._playback_start:.1f}s, {self._playback_end:.1f}s], "
                     f"cursor={self._cursor:.1f}s")

        self.playback_range_changed.emit(self._playback_start, self._playback_end)

        if was_playing:
            self._timer.start(self._tick_interval_ms)

    def clear_playback_range(self):
        self._playback_start = self._time_min
        self._playback_end = self._time_max
        self._use_playback_range = False
        self._cursor = self._time_min
        self._emit_progress()
        logger.info("回放区间已清除，恢复全时段回放")

    def jump_to_event(self, event_id: str, pre_window: float = 2.0, post_window: float = 3.0):
        event = self._find_event_by_id(event_id)
        if not event:
            logger.warning(f"未找到事件: {event_id}")
            return False

        start_time = max(self._time_min, event.start_time - pre_window)
        end_time = min(self._time_max, event.end_time + post_window)
        self.set_playback_range(start_time, end_time)
        # 暂停回放，避免数据持续推送；用户需手动点击播放
        if self._state == 'playing':
            self.pause()
        logger.info(f"跳转到事件 {event_id}: [{start_time:.1f}s, {end_time:.1f}s]")
        return True

    def jump_to_events(self, event_ids: list, pre_window: float = 2.0, post_window: float = 3.0):
        if not event_ids:
            return False

        # 暂停当前回放，事件跳转后用户需手动点击播放
        if self._state == 'playing':
            self.pause()

        events = []
        for eid in event_ids:
            evt = self._find_event_by_id(eid)
            if evt:
                events.append(evt)
            else:
                logger.warning(f"未找到事件: {eid}")

        if not events:
            return False

        min_start = min(e.start_time for e in events)
        max_end = max(e.end_time for e in events)
        start_time = max(self._time_min, min_start - pre_window)
        end_time = min(self._time_max, max_end + post_window)
        self.set_playback_range(start_time, end_time)

        logger.info(f"跳转到 {len(events)} 个事件: [{start_time:.1f}s, {end_time:.1f}s]")
        return True

    def get_events(self) -> list:
        return EventDistributor.instance().get_events()

    def _find_event_by_id(self, event_id: str):
        events = self.get_events()
        for evt in events:
            eid = getattr(evt, 'id', '') or getattr(evt, 'event_id', '')
            if str(eid) == str(event_id):
                return evt
        return None

    def _get_effective_end(self) -> float:
        if self._use_playback_range:
            return self._playback_end
        return self._time_max

    def _on_tick(self):
        if self._state != 'playing':
            return

        if getattr(self, '_tick_in_progress', False):
            return
        self._tick_in_progress = True

        try:
            if self._replay_mode == 'fast':
                self._on_tick_fast()
            else:
                self._on_tick_reanalyze()
        finally:
            self._tick_in_progress = False
    
    def _on_tick_fast(self):
        """快速回放模式优化：确保按数据源类型正确加载和播放"""
        if not self._analysis_cache:
            return
        
        effective_end = self._get_effective_end()
        effective_window = self._window_size * self._speed
        end = min(self._cursor + effective_window, effective_end)
        
        # 获取帧结果
        frame_results = self._analysis_cache.query_time_range(self._cursor, end)
        
        # 同时从缓存获取原始数据（用于可视化）
        raw_start = self._cursor
        records = []
        if self._cache:
            records = self._cache.query_time_range(raw_start, end, self._active_sources)
        
        # 按数据源类型分发
        self._emit_raw_data_by_type(records)
        
        # 发射分析结果
        self._emit_frame_results(frame_results)
        
        # 更新光标
        if frame_results:
            last_ts = frame_results[-1].timestamp
            if last_ts > self._cursor:
                self._cursor = last_ts
            else:
                self._cursor = end
        else:
            self._cursor = end
        
        self._tick_count += 1
        if self._tick_count <= 3 or self._tick_count % 50 == 0:
            self.logger.debug(f"快速回放 tick #{self._tick_count}: FrameResults={len(frame_results)}, "
                        f"RawRecords={len(records)}, cursor={self._cursor:.3f}/{effective_end:.3f}")
        
        self._emit_progress()
        
        if self._cursor >= effective_end:
            self._state = 'finished'
            self._timer.stop()
            self.replay_state_changed.emit('finished')
            self.logger.info(f"快速回放完成")
    
    def _on_tick_reanalyze(self):
        """重新分析模式优化：确保流式处理的正确性"""
        if not self._cache:
            return

        effective_end = self._get_effective_end()

        t_min, t_max = self._cache.get_time_range()
        if t_max > self._time_max:
            self._time_max = t_max

        effective_window = self._window_size * self._speed
        end = min(self._cursor + effective_window, effective_end)

        # 从 SQLite 直读，记录已预先展开（ax/ay/az/speed/wheel 在顶层），
        # 跳过 query_time_range 的逐条 json.loads 开销
        records = self._cache.query_records_raw(self._cursor, end, self._active_sources)

        truncated = False
        if len(records) > self._max_records_per_tick:
            total = len(records)
            records = records[:self._max_records_per_tick]
            truncated = True
            logger.info(f"回放 tick 截断: {total}条 → {self._max_records_per_tick}条, "
                        f"cursor={self._cursor:.3f}")

        # 发射数据用于流式处理
        self._emit_raw_data_by_type(records)

        # 更新光标
        if records:
            last_rec = records[-1]
            last_ts = last_rec.get('_rel_time', last_rec.get('rel_time',
                last_rec.get('timestamp', last_rec.get('wave_t',
                last_rec.get('beat_t', self._cursor)))))
            if isinstance(last_ts, (int, float)) and last_ts > self._cursor:
                self._cursor = last_ts
            elif truncated:
                ratio = self._max_records_per_tick / max(total, 1)
                self._cursor += effective_window * ratio
            else:
                self._cursor = end
        elif not truncated:
            self._cursor = end

        self._tick_count += 1
        if self._tick_count <= 3 or self._tick_count % 50 == 0:
            logger.info(f"重新分析回放 tick #{self._tick_count}: {len(records)}条, "
                        f"cursor={self._cursor:.3f}/{effective_end:.3f}")

        self._emit_progress()

        if self._cursor >= effective_end:
            self._state = 'finished'
            self._timer.stop()
            self.replay_state_changed.emit('finished')
            logger.info(f"重新分析回放完成: 共发射 {self._total_emitted} 条记录")
    
    def _emit_raw_data_by_type(self, records):
        """按数据源类型分发数据，确保每个模块只接收自己需要的数据"""
        if not records:
            return
        
        imu_batch, cnap_batch, can_raw_batch = [], [], []
        for rec in records:
            st = rec.get('_source_type', '')
            if st in ('imu_standalone', 'can_wide', 'can_long', 'pipeline'):
                imu_batch.append(rec)
            if st.startswith('cnap'):
                cnap_batch.append(rec)
            if st in ('can_wide', 'can_long'):
                can_raw_batch.append(rec)

        # 分别发射，避免混合数据干扰
        if imu_batch:
            for i in range(0, len(imu_batch), self._batch_size):
                chunk = imu_batch[i:i + self._batch_size]
                self.imu_data_batch_received.emit(chunk)
                self._total_emitted += len(chunk)
                QApplication.processEvents()
        
        if cnap_batch:
            for i in range(0, len(cnap_batch), self._batch_size):
                chunk = cnap_batch[i:i + self._batch_size]
                self.cnap_data_batch_received.emit(chunk)
                self._total_emitted += len(chunk)
                QApplication.processEvents()
        
        if can_raw_batch:
            for i in range(0, len(can_raw_batch), self._batch_size):
                chunk = can_raw_batch[i:i + self._batch_size]
                self.can_raw_data_batch_received.emit(chunk)
                self._total_emitted += len(chunk)
                QApplication.processEvents()
    
    def _emit_raw_data(self, records):
        """发射原始数据用于可视化（保留以兼容旧代码）"""
        self._emit_raw_data_by_type(records)
    
    def _emit_frame_results(self, frame_results):
        """发射分析结果，同时根据时间戳附加事件"""
        events = self._events_cache
        event_idx = 0
        n_events = len(events)

        for i, fr in enumerate(frame_results):
            if not fr.event and n_events > 0:
                while event_idx < n_events and events[event_idx].end_time < fr.timestamp:
                    event_idx += 1
                if event_idx < n_events:
                    evt = events[event_idx]
                    if evt.start_time <= fr.timestamp <= evt.end_time:
                        fr.event = evt

            self.frame_result_ready.emit(fr)
            
            if fr.event and not self.is_fast_mode:
                self.behavior_event_ready.emit(fr.event)
                # 只在非快速回放模式下注册事件，快速回放模式下事件已经通过sync_from_cache同步
                EventDistributor.instance().register_event(fr.event)
            
            realtime_data = self._frame_to_realtime_data(fr)
            self.realtime_monitor_data.emit(realtime_data)

            if (i + 1) % 30 == 0:
                QApplication.processEvents()
    
    def _frame_to_realtime_data(self, frame_result) -> Dict[str, Any]:
        """把FrameResult转为实时监控友好的字典"""
        from core.core.analysis.core_types import DrivingState, RiskLevel
        
        data = {
            'timestamp': frame_result.timestamp,
            'ax': frame_result.ax,
            'ay': frame_result.ay,
            'az': frame_result.az,
            'gx': frame_result.gx,
            'gy': frame_result.gy,
            'gz': frame_result.gz,
            'speed_ms': frame_result.speed,
            'speed_kmh': frame_result.speed * 3.6 if hasattr(frame_result, 'speed') and frame_result.speed is not None else 0,
            'wheel': frame_result.wheel,
            'state': frame_result.state.value if hasattr(frame_result.state, 'value') else str(frame_result.state),
        }
        
        if hasattr(frame_result, 'features') and frame_result.features:
            data['features'] = {
                'temporal': dict(frame_result.features.temporal) if hasattr(frame_result.features, 'temporal') else {},
                'spectral': dict(frame_result.features.spectral) if hasattr(frame_result.features, 'spectral') else {},
            }
        
        if hasattr(frame_result, 'event') and frame_result.event:
            data['event'] = {
                'type': frame_result.event.type,
                'category': frame_result.event.category.value if hasattr(frame_result.event.category, 'value') else str(frame_result.event.category),
                'confidence': frame_result.event.confidence if hasattr(frame_result.event, 'confidence') else 0,
                'risk_level': frame_result.event.risk_level.value if hasattr(frame_result.event.risk_level, 'value') else str(frame_result.event.risk_level),
                'risk_score': frame_result.event.risk_score if hasattr(frame_result.event, 'risk_score') else 0,
            }
        
        return data

    def _emit_progress(self):
        effective_start = self._playback_start if self._use_playback_range else self._time_min
        effective_end = self._get_effective_end()
        if effective_end > effective_start:
            progress = (self._cursor - effective_start) / (effective_end - effective_start)
            self.replay_progress.emit(min(1.0, max(0.0, progress)))

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_fast_mode(self) -> bool:
        return self._replay_mode == 'fast'

    @property
    def cursor(self) -> float:
        return self._cursor

    @property
    def time_range(self) -> tuple:
        return (self._time_min, self._time_max)

    @property
    def speed(self) -> float:
        return self._speed
