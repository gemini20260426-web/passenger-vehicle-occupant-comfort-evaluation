#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 模式控制器 (PipelineModeController)
统一管理三种 Pipeline (STREAMING / REPLAY / REANALYZE) 的切换、生命周期和 UI 同步。
"""

import logging
from enum import Enum
from typing import Optional, Callable, Dict, Any, List

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class PipelineMode(Enum):
    """Pipeline 模式枚举"""
    IDLE = "idle"
    STREAMING = "streaming"
    REPLAY = "replay"
    REANALYZE = "reanalyze"


class PipelineModeController(QObject):
    """
    Pipeline 模式控制器

    职责:
    1. 管理当前 Pipeline 模式
    2. 执行模式切换协议 (停止 → 清空UI → 切换数据源 → 启动)
    3. 通知所有 UI 模块模式变化
    4. 管理 CacheRegistry 引用
    """

    mode_changed = Signal(str)           # 模式变更，携带新模式字符串
    mode_change_started = Signal(str)    # 模式切换开始
    clear_ui_requested = Signal()        # 请求清空所有 UI 状态
    clear_ui_completed = Signal()        # UI 清空完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._mode = PipelineMode.IDLE
        self._switching = False

        # 外部组件引用（延迟注入）
        self._cache_registry = None
        self._replay_controller = None
        self._data_bridge = None
        self._reader_manager = None

        # 切换回调 (phase → callback)
        self._stop_handlers: Dict[PipelineMode, Callable] = {}
        self._start_handlers: Dict[PipelineMode, Callable] = {}

        self.logger.info("PipelineModeController 已初始化")

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def mode(self) -> PipelineMode:
        return self._mode

    @property
    def is_streaming(self) -> bool:
        return self._mode == PipelineMode.STREAMING

    @property
    def is_replay(self) -> bool:
        return self._mode == PipelineMode.REPLAY

    @property
    def is_reanalyze(self) -> bool:
        return self._mode == PipelineMode.REANALYZE

    @property
    def is_idle(self) -> bool:
        return self._mode == PipelineMode.IDLE

    # ── 组件注入 ──────────────────────────────────────────────

    def set_cache_registry(self, registry):
        """注入 CacheRegistry"""
        self._cache_registry = registry

    def set_replay_controller(self, controller):
        """注入 ReplayController"""
        self._replay_controller = controller

    def set_data_bridge(self, data_bridge):
        """注入 DataBridge"""
        self._data_bridge = data_bridge

    def set_reader_manager(self, manager):
        """注入 DataReaderManager"""
        self._reader_manager = manager

    # ── 模式切换 ──────────────────────────────────────────────

    def set_mode(self, new_mode: PipelineMode):
        """
        切换 Pipeline 模式，执行完整切换协议:
          1. 停止当前 Pipeline
          2. 清空 UI 状态
          3. 切换数据源模式
          4. 启动新 Pipeline
          5. 发射 mode_changed 信号
        """
        if self._switching:
            self.logger.warning("模式切换正在进行中，忽略重复请求")
            return
        if new_mode == self._mode:
            self.logger.debug(f"已在 {new_mode.value} 模式，无需切换")
            return

        self._switching = True
        old_mode = self._mode
        self.logger.info(f"Pipeline 模式切换: {old_mode.value} → {new_mode.value}")
        self.mode_change_started.emit(new_mode.value)

        try:
            # Step 1: 停止当前 Pipeline
            self._stop_current_mode(old_mode)

            # Step 2: 清空 UI
            self.clear_ui_requested.emit()
            self.clear_ui_completed.emit()

            # Step 3: 更新模式
            self._mode = new_mode

            # Step 4: 启动新 Pipeline
            self._start_new_mode(new_mode)

            # Step 5: 通知
            self.mode_changed.emit(new_mode.value)
            self.logger.info(f"Pipeline 模式切换完成: {new_mode.value}")

        except Exception as e:
            self.logger.error(f"模式切换失败: {e}")
            self._mode = old_mode  # 回滚
        finally:
            self._switching = False

    def _stop_current_mode(self, mode: PipelineMode):
        """停止当前 Pipeline"""
        try:
            if mode == PipelineMode.STREAMING:
                if self._reader_manager:
                    self._reader_manager.stop_all()
                    self.logger.info("已停止 STREAMING 模式 (DataReaderManager)")
                if self._data_bridge:
                    self._data_bridge.set_suppress_ui_signals(True)
            elif mode in (PipelineMode.REPLAY, PipelineMode.REANALYZE):
                if self._replay_controller and self._replay_controller.state == 'playing':
                    self._replay_controller.stop()
                    self.logger.info("已停止回放控制器")
        except Exception as e:
            self.logger.warning(f"停止 {mode.value} 模式时出错: {e}")

    def _start_new_mode(self, mode: PipelineMode):
        """启动新 Pipeline"""
        try:
            if mode == PipelineMode.STREAMING:
                if self._data_bridge:
                    self._data_bridge.set_suppress_ui_signals(False)
                if self._reader_manager:
                    self._reader_manager.start_all()
                    self.logger.info("已启动 STREAMING 模式")
            elif mode in (PipelineMode.REPLAY, PipelineMode.REANALYZE):
                if self._replay_controller:
                    replay_mode = 'fast' if mode == PipelineMode.REPLAY else 'reanalyze'
                    self._replay_controller.set_replay_mode(replay_mode)
                    self._replay_controller.play()
                    self.logger.info(f"已启动 {mode.value} 模式 (replay_mode={replay_mode})")
        except Exception as e:
            self.logger.error(f"启动 {mode.value} 模式失败: {e}")

    # ── 缓存管理 ──────────────────────────────────────────────

    def get_available_caches(self) -> list:
        """获取所有可用缓存条目"""
        if self._cache_registry:
            return self._cache_registry.list_caches()
        return []

    def load_cache_by_id(self, cache_id: str) -> bool:
        """
        通过 id 加载指定缓存数据集到回放控制器。
        用于 CacheSelector 选择不同缓存时调用。
        """
        if not self._cache_registry:
            self.logger.warning("CacheRegistry 未注入，无法加载缓存")
            return False
        if not self._replay_controller:
            self.logger.warning("ReplayController 未注入，无法加载缓存")
            return False

        try:
            cache, analysis_cache = self._cache_registry.get_cache(cache_id)

            if self._replay_controller.state == 'playing':
                self._replay_controller.stop()

            if not self._replay_controller.load_cache(cache):
                self.logger.warning(f"加载缓存失败: {cache_id}")
                return False

            if analysis_cache:
                self._replay_controller.load_analysis_cache(analysis_cache)

            entry = self._cache_registry.get_entry(cache_id)
            if entry:
                self._cache_registry._set_default(cache_id)
                self.logger.info(
                    f"已加载缓存: [{entry.display_label}], "
                    f"{entry.record_count}条, {entry.event_count}事件"
                )

            return True
        except Exception as e:
            self.logger.error(f"加载缓存失败 ({cache_id}): {e}")
            return False

    def load_default_cache(self) -> bool:
        """加载默认（最新）缓存"""
        if not self._cache_registry:
            return False
        default_id = self._cache_registry.get_default_id()
        if not default_id:
            return False
        return self.load_cache_by_id(default_id)

    # ── 便捷方法 ──────────────────────────────────────────────

    def switch_to_streaming(self):
        """切换到 STREAMING 模式"""
        self.set_mode(PipelineMode.STREAMING)

    def switch_to_replay(self):
        """切换到 REPLAY 模式"""
        self.set_mode(PipelineMode.REPLAY)

    def switch_to_reanalyze(self):
        """切换到 REANALYZE 模式"""
        self.set_mode(PipelineMode.REANALYZE)

    def switch_to_idle(self):
        """切换到 IDLE 模式"""
        self.set_mode(PipelineMode.IDLE)