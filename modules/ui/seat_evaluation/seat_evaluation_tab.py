#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
座椅评测面板UI组件 - 事件驱动重构版 v5.0
以驾驶行为事件驱动为核心，集成事件管理/实例视图/类型汇总/行程总览/对照分析
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QScrollArea, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.core.seat_evaluation.imu_location_config import LOCATION_NAMES, LOCATION_IDS
from core.core.seat_evaluation.eval_queue import (
    EvaluationQueue, EVENT_TYPE_CN_LABELS, TYPE_COLORS,
)
from core.core.analysis.event_distributor import EventDistributor

from .event_manager_panel import EventManagerPanel
from .instance_view_panel import InstanceViewPanel
from .statistics_analysis_tab import StatisticsAnalysisTab

logger = logging.getLogger(__name__)


class SeatEvaluationTab(QWidget):
    """座椅评测面板 - 事件驱动架构 v5.0

    子Tab结构:
    [事件管理] [实例视图] [全量统计] [报告中心]
    """

    evaluation_requested = Signal(dict)
    export_requested = Signal()
    refresh_requested = Signal()
    comparison_requested = Signal(dict)
    export_report_requested = Signal()

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.evaluation_engine = None
        self.comparison_engine = None
        self._data_bridge = None

        self._queue_engine = EvaluationQueue()
        self._distributor = EventDistributor.instance()

        self._type_labels = dict(EVENT_TYPE_CN_LABELS)
        self._type_colors = dict(TYPE_COLORS)

        # ── 评测模式 ──
        self._evaluation_mode = 'incremental'  # 'incremental' | 'batch'

        self._init_ui()
        self._connect_signals()
        self.logger.info("座椅评测面板已初始化 (v5.0 事件驱动架构)")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(4, 4, 4, 4)
        self.setObjectName("tabContentArea")

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("innerTabs")
        self.main_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                padding: 6px 14px;
                font-size: 11px;
                border: 1px solid #D0D0D0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                background-color: #F5F6F8;
                color: #666666;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #4A90D9;
                font-weight: 600;
                border-bottom: 2px solid #4A90D9;
            }
            QTabBar::tab:hover {
                background-color: #E8F0FE;
            }
        """)

        self._event_manager = EventManagerPanel()
        self._event_manager.event_selected.connect(self._on_event_selected)
        self._event_manager.events_checked_changed.connect(self._on_checked_changed)
        self._event_manager.evaluate_requested.connect(self._on_evaluate_selected)
        self._event_manager.evaluate_all_requested.connect(self._on_evaluate_all)
        self._event_manager.evaluate_type_requested.connect(self._on_evaluate_type)
        self._event_manager.refresh_requested.connect(self._on_refresh)
        self._event_manager.clear_results_requested.connect(self._on_clear_results)
        self.main_tabs.addTab(self._event_manager, "📋 事件管理")

        self._instance_view = InstanceViewPanel()
        self._instance_view.set_type_labels(self._type_labels)
        self.main_tabs.addTab(self._instance_view, "🔍 实例视图")

        self._statistics_tab = StatisticsAnalysisTab(config_manager=self.config_manager)
        self._statistics_tab.set_type_labels(self._type_labels)
        self._statistics_tab.set_event_manager(self._event_manager)
        self.main_tabs.addTab(self._statistics_tab, "📊 全量统计")

        self._report_tab = self._create_report_placeholder()
        self.main_tabs.addTab(self._report_tab, "📄 报告中心")

        main_layout.addWidget(self.main_tabs)

    def _create_report_placeholder(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 40, 20, 40)

        title = QLabel("报告中心")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #27AE60; padding-bottom: 8px;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "报告中心将在评测功能稳定后接入。\n\n"
            "功能规划:\n"
            "• 单事件评测报告\n"
            "• 全量统计综合报告\n"
            "• Markdown/PDF/CSV 多格式导出\n"
            "• 报告历史管理\n\n"
            "评测执行后即可从「实例视图」查看详细结果。"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666666; font-size: 11px; line-height: 1.6;")
        layout.addWidget(desc)
        layout.addStretch()
        return tab

    def _connect_signals(self):
        self._queue_engine.record_status_changed.connect(self._on_record_status_changed)
        self._queue_engine.evaluation_completed.connect(self._on_eval_completed)
        self._queue_engine.evaluation_failed.connect(self._on_eval_failed)
        self._queue_engine.trip_summary_ready.connect(self._on_trip_summary_ready)
        self._queue_engine.batch_finished.connect(self._on_batch_finished)
        self._event_manager.group_changed.connect(self._on_group_changed)
        self._instance_view.event_selected.connect(self._on_event_selected)
        self._distributor.events_changed.connect(self._on_distributor_changed)

    def sync_events_from_distributor(self):
        events = self._distributor.get_behavior_events()

        self._queue_engine.sync_from_distributor(events)

        records = list(self._queue_engine.records.values())
        self._event_manager.rebuild(records, self._type_labels, self._type_colors)

        all_ids = sorted(self._queue_engine.records.keys(),
                         key=lambda eid: self._queue_engine.records[eid].start_ts)
        self._instance_view._all_record_ids = all_ids
        self._instance_view.set_all_records(self._queue_engine.records)

        logger.info(f"同步事件完成: {len(records)} 条记录")

    # ── 评测模式管理 ──

    def set_evaluation_mode(self, mode: str):
        """
        设置评测模式。
        mode: 'incremental' (STREAMING 增量) | 'batch' (REANALYZE 全量批量)
        """
        if mode not in ('incremental', 'batch'):
            self.logger.warning(f"无效的评测模式: {mode}")
            return
        self._evaluation_mode = mode
        self.logger.info(f"座椅评测模式: {mode}")

    def evaluate_incremental(self, event_data) -> Optional[Dict]:
        """
        增量评测单个事件（STREAMING 模式）。
        事件产生时调用，不阻塞主数据流。
        支持 dict 和 ManeuverEvent 对象两种输入。
        """
        if not self.evaluation_engine:
            return None
        try:
            if isinstance(event_data, dict):
                trigger = {
                    'event_id': event_data.get('event_id', event_data.get('id', '')),
                    'event_type': event_data.get('type', event_data.get('event_type', '')),
                    'timestamp': event_data.get('start_time', event_data.get('timestamp', 0.0)),
                }
            else:
                trigger = {
                    'event_id': getattr(event_data, 'id', '') or getattr(event_data, 'event_id', ''),
                    'event_type': getattr(event_data, 'type', '') or getattr(event_data, 'event_type', ''),
                    'timestamp': getattr(event_data, 'start_time', 0.0) or getattr(event_data, 'timestamp', 0.0),
                }
            result = self.evaluation_engine.evaluate_by_event(trigger)
            if result:
                tid = getattr(result, 'trigger_id', '') or ''
                self._queue_engine.update_result(tid, result)
                self._event_manager.refresh()
                self.logger.debug(f"增量评测完成: {trigger.get('event_type')}")
            return result
        except Exception as e:
            self.logger.error(f"增量评测失败: {e}")
            return None

    def evaluate_batch_all(self):
        """
        全量批量评测所有事件（REANALYZE 模式）。
        回放完成后调用，覆盖更新所有事件的评分。
        """
        if not self.evaluation_engine:
            self.logger.warning("评测引擎未注入，无法执行批量评测")
            return

        import time
        start_time = time.time()
        self.logger.info("开始全量批量座椅评测...")
        events = self._distributor.get_events()
        count = 0
        for event in events:
            try:
                eid = getattr(event, 'id', '') or getattr(event, 'event_id', '')
                etype = getattr(event, 'type', '') or getattr(event, 'event_type', '')
                t_start = getattr(event, 'start_time', 0.0)
                trigger = {
                    'event_id': str(eid),
                    'event_type': etype,
                    'timestamp': t_start,
                }
                result = self.evaluation_engine.evaluate_by_event(trigger)
                if result:
                    self._queue_engine.update_result(str(eid), result)
                    count += 1
            except Exception as e:
                self.logger.error(f"批量评测事件失败: {e}")

        elapsed = time.time() - start_time
        self.logger.info(f"全量批量评测完成: {count}/{len(events)} 事件, 耗时 {elapsed:.1f}s")

        # 刷新 UI
        self._event_manager.refresh()
        self.sync_events_from_distributor()

    def clear_results(self):
        """清除所有评测结果（Pipeline 切换清空时调用）"""
        self._queue_engine.clear_results()
        self._evaluation_mode = 'incremental'
        self.logger.info("座椅评测结果已清空")

    def _on_event_selected(self, event_id: str):
        record = self._queue_engine.records.get(event_id)
        if not record:
            return

        all_ids = sorted(self._queue_engine.records.keys(),
                         key=lambda eid: self._queue_engine.records[eid].start_ts)

        self._instance_view.show_record(record, all_ids)
        self.main_tabs.setCurrentWidget(self._instance_view)
        logger.debug(f"查看事件: {event_id}")

    def _on_checked_changed(self, checked_ids: List[str]):
        pass

    def _on_evaluate_selected(self, record_ids: List[str]):
        self._queue_engine.evaluate_selected(record_ids)

    def _on_evaluate_all(self):
        self._queue_engine.evaluate_all()

    def _on_evaluate_all_pending(self):
        self._queue_engine.evaluate_all_pending()

    def _on_evaluate_type(self, event_type: str):
        if event_type:
            self._queue_engine.evaluate_by_type(event_type)

    def _on_group_changed(self, group_tags: list):
        self._queue_engine.set_active_groups(group_tags)
        self.sync_events_from_distributor()
        logger.info(f"评测分组已切换为: {group_tags}")

    def _on_distributor_changed(self, events):
        self.sync_events_from_distributor()
        logger.info(f"EventDistributor 事件变更 ({len(events)} 个)，已自动同步")

    def refresh_events(self):
        self.sync_events_from_distributor()

    def _on_refresh(self):
        self.sync_events_from_distributor()
        self.refresh_requested.emit()

    def _on_clear_results(self):
        self._queue_engine.clear_results()
        self.sync_events_from_distributor()

    def _on_record_status_changed(self, event_id: str, status: str):
        record = self._queue_engine.records.get(event_id)
        if record:
            self._event_manager.update_record(record)

    def _on_eval_completed(self, event_id: str, result):
        record = self._queue_engine.records.get(event_id)
        if not record:
            return

        self._event_manager.update_record(record)

        if self.main_tabs.currentWidget() == self._instance_view and \
           self._instance_view._current_record and \
           self._instance_view._current_record.event_id == event_id:
            record = self._queue_engine.records.get(event_id)
            if record:
                all_ids = sorted(self._queue_engine.records.keys(),
                                 key=lambda eid: self._queue_engine.records[eid].start_ts)
                self._instance_view.show_record(record, all_ids)

    def _on_batch_finished(self):
        if self._queue_engine._trip_summary:
            self._statistics_tab.set_trip_summary(self._queue_engine._trip_summary)
        logger.info(f"批量评测UI刷新完成, 行程摘要已更新")

    def _on_eval_failed(self, event_id: str, error: str):
        record = self._queue_engine.records.get(event_id)
        if record:
            self._event_manager.update_record(record)
        logger.warning(f"评测失败: {event_id}, 原因: {error}")

    def _on_trip_summary_ready(self, trip_summary):
        self._statistics_tab.set_trip_summary(trip_summary)

    def _on_evaluation_started(self):
        self.sync_events_from_distributor()

    def _on_evaluation_completed(self, result):
        self.sync_events_from_distributor()

    def _on_eval_metric_calculated(self, metric_data):
        pass

    def _on_eval_location_result_ready(self, location_data):
        pass

    def _on_comparison_started(self):
        pass

    def _on_comparison_completed(self, result):
        pass

    def _on_comp_metric_comparison_updated(self, comp_data):
        pass

    def set_evaluation_engine(self, engine):
        self.evaluation_engine = engine
        self._queue_engine.set_evaluation_engine(engine)
        if engine:
            try:
                engine.evaluation_started.connect(self._on_evaluation_started)
                engine.evaluation_completed.connect(self._on_evaluation_completed)
                engine.metric_calculated.connect(self._on_eval_metric_calculated)
                if hasattr(engine, 'location_result_ready'):
                    engine.location_result_ready.connect(self._on_eval_location_result_ready)
            except Exception as e:
                self.logger.warning(f"信号连接部分失败: {e}")
        self.logger.info("座椅评测引擎已设置")

    def set_comparison_engine(self, engine):
        self.comparison_engine = engine
        if engine:
            try:
                engine.comparison_started.connect(self._on_comparison_started)
                engine.comparison_completed.connect(self._on_comparison_completed)
                engine.metric_comparison_updated.connect(self._on_comp_metric_comparison_updated)
            except Exception as e:
                self.logger.warning(f"对照引擎信号连接部分失败: {e}")
        self.logger.info("对照分析引擎已设置")

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge
        self._queue_engine.set_data_bridge(data_bridge)

        def _query_raw_data(start_time: float, end_time: float):
            if not self._data_bridge:
                return {}
            try:
                return self._data_bridge.build_display_channel_data(
                    start_time, end_time
                )
            except Exception as e:
                logger.warning(f"查询原始数据失败: {e}")
                return {}

        self._instance_view.set_data_query_fn(_query_raw_data)
        self.sync_events_from_distributor()
        self.logger.info("数据桥接已设置")

    def set_comparative_engine(self, engine):
        self.set_comparison_engine(engine)

    def _on_evaluation_triggered(self, trigger: dict):
        self.logger.info(f"收到座椅评测触发: event_type={trigger.get('event_type', '')}")
        self.sync_events_from_distributor()

    def _update_evaluation_display(self, result):
        self.sync_events_from_distributor()

    def _show_result_detail(self, result):
        pass