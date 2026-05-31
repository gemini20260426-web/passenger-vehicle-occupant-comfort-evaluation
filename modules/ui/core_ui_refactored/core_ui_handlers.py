#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 事件处理模块
负责所有信号连接和事件处理
"""

import logging
import time
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer

from .core_ui_utils import translations


class CoreUIHandlers:
    """事件处理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

    def connect_signals(self):
        """连接组件间的信号"""
        main = self.main_window
        try:
            if hasattr(main, 'left_panel'):
                main.left_panel.data_source_changed.connect(main.on_data_source_changed)
                main.left_panel.load_file_requested.connect(main.on_load_file)
                main.left_panel.data_sources_selected.connect(main.on_data_sources_selected)
                main.left_panel.analysis_toggled.connect(main.on_analysis_toggled)
                main.left_panel.record_toggled.connect(main.on_record_toggled)
                main.left_panel.export_data_requested.connect(main.on_export_data)
                main.left_panel.source_added.connect(main.on_source_added)
                main.left_panel.source_removed.connect(main.on_source_removed)
                main.left_panel.active_source_changed.connect(main.on_active_source_changed)
                main.left_panel.advanced_analysis_started.connect(main.on_advanced_analysis_started)
                main.left_panel.advanced_analysis_stopped.connect(main.on_advanced_analysis_stopped)
                main.left_panel.advanced_analysis_paused.connect(main.on_advanced_analysis_paused)
                main.left_panel.model_load_requested.connect(main.on_model_load_requested)
                main.left_panel.model_unload_requested.connect(main.on_model_unload_requested)

            if hasattr(main, 'right_tab'):
                if hasattr(main.right_tab, 'start_analysis_btn'):
                    main.right_tab.start_analysis_btn.clicked.connect(
                        lambda: main.left_panel.analysis_toggled.emit(True, "basic"))
                if hasattr(main.right_tab, 'stop_analysis_btn'):
                    main.right_tab.stop_analysis_btn.clicked.connect(
                        lambda: main.left_panel.analysis_toggled.emit(False, ""))

                if hasattr(main.right_tab, 'monitoring_tab'):
                    main.data_updated.connect(main._update_right_tab_data)

                if hasattr(main.left_panel, 'parsing_status_broadcast'):
                    main.left_panel.parsing_status_broadcast.connect(main._update_monitoring_from_left_panel)
                if hasattr(main.left_panel, 'parsing_stats_broadcast'):
                    main.left_panel.parsing_stats_broadcast.connect(main._update_monitoring_from_left_panel)
                if hasattr(main.left_panel, 'error_monitor_broadcast'):
                    main.left_panel.error_monitor_broadcast.connect(main._update_monitoring_from_left_panel)
                if hasattr(main.left_panel, 'core_system_broadcast'):
                    main.left_panel.core_system_broadcast.connect(main._update_monitoring_from_left_panel)

            if hasattr(main, 'data_timer'):
                main.data_timer.timeout.connect(main.update_data)

            if hasattr(main, 'time_timer'):
                main.time_timer.timeout.connect(main.update_time)

            self.logger.info("所有信号连接完成")

        except Exception as e:
            self.logger.error(f"信号连接失败: {e}")
            QMessageBox.critical(
                main,
                "系统初始化失败",
                f"信号连接失败:\n{str(e)}\n\n请重启应用程序。"
            )

    def on_new_session(self):
        main = self.main_window
        reply = QMessageBox.question(
            main, "新建会话",
            "确定要新建会话吗?\n当前未保存的数据将丢失。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                main.data_sources = {}
                main.active_source_id = None
                main.data_count = 0
                main.behavior_stats = {}
                main.last_data_update_time = time.time()
                main.data_update_failures = 0
                if hasattr(main, 'left_panel') and hasattr(main.left_panel, 'reset_all'):
                    main.left_panel.reset_all()
                if hasattr(main, 'right_tab') and hasattr(main.right_tab, 'reset_all'):
                    main.right_tab.reset_all()
                if hasattr(main, 'bottom_status'):
                    main.bottom_status.showMessage("新会话已创建", 3000)
                main.logger.info("新会话已创建")
            except Exception as e:
                main.logger.error(f"新建会话失败: {e}")
                QMessageBox.critical(main, "错误", f"新建会话失败:\n{e}")

    def on_open_file(self):
        main = self.main_window
        try:
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                main, "打开数据文件",
                "",
                "数据文件 (*.csv *.json *.txt *.log);;所有文件 (*.*)"
            )
            if file_path:
                main.logger.info(f"正在打开文件: {file_path}")
                if hasattr(main, 'left_panel') and hasattr(main.left_panel, 'load_file'):
                    main.left_panel.load_file(file_path)
                if hasattr(main, 'bottom_status'):
                    main.bottom_status.showMessage(f"已加载文件: {file_path}", 5000)
        except Exception as e:
            main.logger.error(f"打开文件失败: {e}")
            QMessageBox.critical(main, "错误", f"打开文件失败:\n{e}")

    def on_save_data(self):
        main = self.main_window
        try:
            import json
            from datetime import datetime
            from PySide6.QtWidgets import QFileDialog
            if not main.data_sources and main.data_count == 0:
                QMessageBox.information(main, "保存数据", "当前没有数据可保存。")
                return
            file_path, _ = QFileDialog.getSaveFileName(
                main, "保存数据",
                f"data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON文件 (*.json);;CSV文件 (*.csv);;所有文件 (*.*)"
            )
            if file_path:
                export_data = {
                    'timestamp': datetime.now().isoformat(),
                    'data_count': main.data_count,
                    'active_source_id': main.active_source_id,
                    'data_sources': {str(k): str(v) for k, v in main.data_sources.items()},
                    'behavior_stats': main.behavior_stats
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                if hasattr(main, 'bottom_status'):
                    main.bottom_status.showMessage(f"数据已保存到: {file_path}", 5000)
                main.logger.info(f"数据已保存到: {file_path}")
        except Exception as e:
            main.logger.error(f"保存数据失败: {e}")
            QMessageBox.critical(main, "错误", f"保存数据失败:\n{e}")

    def on_data_source_changed(self, source_type: str, params: dict):
        main = self.main_window
        main.logger.info(f"数据源变更: {source_type}")
        main.data_updated.emit({
            'source_type': source_type,
            'params': params,
            'timestamp': time.time()
        })

    def on_load_file(self, file_path: str):
        main = self.main_window
        main.logger.info(f"加载文件: {file_path}")
        main.data_updated.emit({
            'file_path': file_path,
            'action': 'load_file',
            'timestamp': time.time()
        })

    def on_data_sources_selected(self, sources: list):
        main = self.main_window
        main.logger.info(f"数据源选择: {sources}")
        main.data_updated.emit({
            'sources': sources,
            'action': 'sources_selected',
            'timestamp': time.time()
        })

    def on_analysis_toggled(self, start: bool, level: str):
        main = self.main_window
        main.logger.info(f"分析切换: start={start}, level={level}")
        main.data_updated.emit({
            'analysis_started': start,
            'level': level,
            'timestamp': time.time()
        })

    def on_record_toggled(self, start: bool):
        main = self.main_window
        main.logger.info(f"录制切换: {start}")
        main.data_updated.emit({
            'recording': start,
            'timestamp': time.time()
        })

    def on_export_data(self):
        main = self.main_window
        main.logger.info("导出数据请求")
        main.data_updated.emit({
            'action': 'export_data',
            'timestamp': time.time()
        })

    def on_basic_analysis_started(self):
        self.main_window.logger.info("基础分析已启动")

    def on_basic_analysis_stopped(self):
        self.main_window.logger.info("基础分析已停止")

    def on_basic_analysis_paused(self):
        self.main_window.logger.info("基础分析已暂停")

    def on_training_started(self):
        self.main_window.logger.info("训练已启动")

    def on_training_stopped(self):
        self.main_window.logger.info("训练已停止")

    def on_source_added(self, source_id: int, source_type: str, params: dict):
        self.main_window.logger.info(f"数据源已添加: {source_id}, {source_type}")

    def on_source_removed(self, source_id: int):
        self.main_window.logger.info(f"数据源已移除: {source_id}")

    def on_active_source_changed(self, source_id: int):
        self.main_window.logger.info(f"活跃数据源已变更: {source_id}")

    def on_advanced_analysis_started(self):
        self.main_window.logger.info("高级分析已启动")

    def on_advanced_analysis_stopped(self):
        self.main_window.logger.info("高级分析已停止")

    def on_advanced_analysis_paused(self):
        self.main_window.logger.info("高级分析已暂停")

    def on_model_load_requested(self):
        self.main_window.logger.info("模型加载请求")

    def on_model_unload_requested(self):
        self.main_window.logger.info("模型卸载请求")

    def update_data(self):
        """更新数据"""
        main = self.main_window
        try:
            data = {}
            if hasattr(main, 'left_panel') and hasattr(main.left_panel, 'parsing_status_monitor'):
                monitor = main.left_panel.parsing_status_monitor
                if hasattr(monitor, 'parsing_status'):
                    total_speed = sum(status.get('speed', 0) for status in monitor.parsing_status.values())
                    data['data_rate'] = total_speed
                    total_progress = sum(status.get('progress', 0) for status in monitor.parsing_status.values())
                    avg_progress = total_progress // len(monitor.parsing_status) if monitor.parsing_status else 0
                    data['progress'] = avg_progress
                    active_sources = [s for s in monitor.parsing_status.values() if s.get('status') == 'running']
                    data['connection_status'] = 'Connected' if active_sources else 'Disconnected'
                    source_types = list(monitor.parsing_status.keys())
                    data['source_type'] = ', '.join(source_types) if source_types else '未选择'
                    if any(s.get('status') == 'running' for s in monitor.parsing_status.values()):
                        data['system_state'] = 'Running'
                    elif any(s.get('status') == 'completed' for s in monitor.parsing_status.values()):
                        data['system_state'] = 'Completed'
                    else:
                        data['system_state'] = 'Ready'

            main.data_updated.emit(data)
            main.last_data_update_time = time.time()
            main.data_update_failures = 0

        except Exception as e:
            main.logger.error(f"数据更新失败: {e}")
            main.data_update_failures += 1

    def update_time(self):
        """更新时间显示"""
        main = self.main_window
        try:
            if hasattr(main, 'top_status'):
                main.top_status.update_time()
        except Exception as e:
            main.logger.warning(f"时间更新失败: {e}")

    def _check_data_update_health(self):
        """检查数据更新健康状态"""
        main = self.main_window
        try:
            time_since_last_update = time.time() - main.last_data_update_time
            if time_since_last_update > 60:
                main.logger.warning(f"数据更新超时: {time_since_last_update:.1f}秒未更新")
                main.data_update_failures += 1
            if main.data_update_failures >= main.max_failures:
                main.logger.error("数据更新系统故障,尝试重启")
                main._restart_data_update_system()
        except Exception as e:
            main.logger.error(f"健康检查失败: {e}")

    def _restart_data_update_system(self):
        """重启数据更新系统"""
        main = self.main_window
        try:
            main.logger.info("正在重启数据更新系统...")
            if hasattr(main, 'data_timer'):
                main.data_timer.stop()
                QTimer.singleShot(1000, main.data_timer.start)
            main.data_update_failures = 0
            main.last_data_update_time = time.time()
            main.logger.info("数据更新系统已重启")
        except Exception as e:
            main.logger.error(f"重启数据更新系统失败: {e}")

    def handle_control_action(self, action_type, payload):
        """处理控制面板动作"""
        main = self.main_window
        main.logger.info(f"处理控制面板动作: {action_type}, 数据: {payload}")

        if action_type == "BASIC_ANALYSIS_START":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("基础分析运行中")
                main.analysis_panel.show_progress(True, 10)
        elif action_type == "BASIC_ANALYSIS_PAUSE":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("基础分析已暂停")
        elif action_type == "BASIC_ANALYSIS_STOP":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("基础分析已停止")
                main.analysis_panel.show_progress(False)
        elif action_type == "ADVANCED_ANALYSIS_START":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("高级分析运行中")
        elif action_type == "ADVANCED_ANALYSIS_PAUSE":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("高级分析已暂停")
        elif action_type == "ADVANCED_ANALYSIS_STOP":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("高级分析已停止")
        elif action_type == "MODEL_LOAD_REQUEST":
            if hasattr(main, 'on_model_load_requested'):
                main.on_model_load_requested()
        elif action_type == "MODEL_UNLOAD_REQUEST":
            if hasattr(main, 'on_model_unload_requested'):
                main.on_model_unload_requested()
        elif action_type == "TRAINING_START":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("模型训练中")
        elif action_type == "TRAINING_STOP":
            if hasattr(main, 'analysis_panel'):
                main.analysis_panel.update_status("训练已停止")
        elif action_type == "DATA_SOURCE_CHANGED":
            if hasattr(main, 'on_data_source_changed'):
                main.on_data_source_changed(payload["type"], {})
        elif action_type == "LOAD_DATA":
            if hasattr(main, 'on_load_file'):
                main.on_load_file("")
            if hasattr(main, 'data_source_panel'):
                main.data_source_panel.update_status("数据加载中")
        elif action_type == "CLEAR_DATA":
            if hasattr(main, 'data_source_panel'):
                main.data_source_panel.update_status("数据已清除")
        elif action_type == "ADD_SOURCE":
            if hasattr(main, 'data_source_panel'):
                main.data_source_panel.update_status("数据源已添加")
        elif action_type == "REMOVE_SOURCE":
            if hasattr(main, 'data_source_panel'):
                main.data_source_panel.update_status("数据源已移除")
        elif action_type == "SET_ACTIVE_SOURCE":
            if hasattr(main, 'data_source_panel'):
                main.data_source_panel.update_status("活跃数据源已设置")
        elif action_type == "START_PARSING":
            if hasattr(main, 'parsing_panel'):
                main.parsing_panel.set_parsing_state(True)
        elif action_type == "STOP_PARSING":
            if hasattr(main, 'parsing_panel'):
                main.parsing_panel.set_parsing_state(False)
