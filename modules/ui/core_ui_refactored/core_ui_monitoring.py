#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 系统监控模块
负责系统性能监控和健康度计算逻辑
"""

import logging
import time
import threading


class CoreUIMonitoring:
    """系统监控管理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

    def setup_system_monitoring(self):
        """设置系统监控"""
        main = self.main_window
        try:
            import psutil

            def monitor_system():
                """系统监控线程"""
                while hasattr(main, 'data_timer') and main.data_timer.isActive():
                    try:
                        cpu_percent = psutil.cpu_percent(interval=1)
                        memory = psutil.virtual_memory()
                        memory_percent = memory.percent
                        disk = psutil.disk_usage('/')
                        disk_percent = disk.percent
                        main.update_system_metrics.emit(cpu_percent, memory_percent, disk_percent)
                        time.sleep(5)
                    except Exception as e:
                        if hasattr(main, 'logger'):
                            main.logger.warning(f"系统监控更新失败: {e}")
                        time.sleep(10)

            monitor_thread = threading.Thread(target=monitor_system, daemon=True)
            monitor_thread.start()
            self.logger.info("系统监控已启动")

        except ImportError:
            self.logger.warning("psutil模块未安装,系统监控功能不可用")
        except Exception as e:
            self.logger.error(f"启动系统监控失败: {e}")

    def update_system_metrics_ui(self, cpu_percent, memory_percent, disk_percent):
        """更新系统指标UI显示"""
        main = self.main_window
        try:
            if hasattr(main, 'right_tab') and hasattr(main.right_tab, 'system_monitor_tab'):
                tab = main.right_tab.system_monitor_tab
                if hasattr(tab, 'cpu_usage_value'):
                    tab.cpu_usage_value.setText(f"{cpu_percent:.1f}%")
                if hasattr(tab, 'memory_usage_value'):
                    tab.memory_usage_value.setText(f"{memory_percent:.1f}%")
                if hasattr(tab, 'disk_usage_value'):
                    tab.disk_usage_value.setText(f"{disk_percent:.1f}%")

                health_score = self._calculate_health_score(cpu_percent, memory_percent, disk_percent)
                if hasattr(tab, 'health_score_value'):
                    tab.health_score_value.setText(str(health_score))
                if hasattr(tab, 'health_score_progress'):
                    tab.health_score_progress.setValue(health_score)

        except Exception as e:
            if hasattr(main, 'logger'):
                main.logger.warning(f"更新系统指标UI失败: {e}")

    def _calculate_health_score(self, cpu_percent, memory_percent, disk_percent):
        """计算系统健康度评分"""
        try:
            cpu_score = max(0, 100 - cpu_percent)
            memory_score = max(0, 100 - memory_percent)
            disk_score = max(0, 100 - disk_percent)
            data_quality_score = self._calculate_data_quality_score()
            connection_score = self._calculate_connection_score()
            analysis_score = self._calculate_analysis_performance_score()

            health_score = (
                cpu_score * 0.25 +
                memory_score * 0.25 +
                disk_score * 0.15 +
                data_quality_score * 0.20 +
                connection_score * 0.10 +
                analysis_score * 0.05
            )
            return int(max(0, min(100, health_score)))
        except Exception as e:
            self.logger.error(f"计算系统健康度评分失败: {e}")
            return 50

    def _calculate_data_quality_score(self):
        """计算数据质量评分"""
        try:
            return 50
        except Exception as e:
            self.logger.error(f"计算数据质量评分失败: {e}")
            return 50

    def _calculate_connection_score(self):
        """计算连接状态评分"""
        try:
            main = self.main_window
            multi_source_connected = False
            if hasattr(main, 'data_sources'):
                connected_sources = sum(
                    1 for source_info in main.data_sources.values()
                    if source_info.get("is_connected", False)
                )
                multi_source_connected = connected_sources > 0
            return 75 if multi_source_connected else 50
        except Exception as e:
            self.logger.error(f"计算连接状态评分失败: {e}")
            return 50

    def _calculate_analysis_performance_score(self):
        """计算分析性能评分"""
        try:
            return 50
        except Exception as e:
            self.logger.error(f"计算分析性能评分失败: {e}")
            return 50

    def setup_data_pipeline_monitoring(self):
        """设置数据流管道监控"""
        main = self.main_window
        try:
            def monitor_pipeline():
                """数据流管道监控线程"""
                while hasattr(main, 'data_timer') and main.data_timer.isActive():
                    try:
                        if hasattr(main, 'data_pipeline_health'):
                            main.data_pipeline_health['last_update'] = time.time()
                            main.data_pipeline_health['update_count'] += 1
                        time.sleep(10)
                    except Exception as e:
                        if hasattr(main, 'logger'):
                            main.logger.warning(f"数据流管道监控失败: {e}")
                        time.sleep(30)

            monitor_thread = threading.Thread(target=monitor_pipeline, daemon=True)
            monitor_thread.start()
            self.logger.info("数据流管道监控已启动")
        except Exception as e:
            self.logger.error(f"启动数据流管道监控失败: {e}")
