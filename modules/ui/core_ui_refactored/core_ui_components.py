#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 组件模块
负责 UI 基本组件的创建和异步加载逻辑
"""

import logging
import os
import glob
import sqlite3
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QProgressBar, QTabWidget,
    QStatusBar, QMenuBar, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal

from .core_ui_utils import translations


class CoreUIComponents:
    """UI组件管理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        self.ui_tasks = []
        self.current_task_index = 0
        self.loading_progress = None
        self.loading_label = None

    def init_ui(self):
        """初始化UI"""
        main = self.main_window
        main.setWindowTitle(translations['en']['app_title'])
        main.setGeometry(100, 100, 1400, 900)

        central_widget = QWidget()
        main.setCentralWidget(central_widget)
        main.main_layout = QVBoxLayout(central_widget)
        main.main_layout.setContentsMargins(5, 5, 5, 5)
        main.main_layout.setSpacing(5)

        self._create_loading_interface()

        main.create_menu_bar()

        QTimer.singleShot(100, self._init_async_ui_loading)

    def _create_loading_interface(self):
        """创建加载界面"""
        main = self.main_window
        self.loading_label = QLabel("正在加载系统组件...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 16px; color: #3498db; padding: 20px;")

        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setTextVisible(True)

        main.main_layout.addStretch()
        main.main_layout.addWidget(self.loading_label)
        main.main_layout.addWidget(self.loading_progress)
        main.main_layout.addStretch()

    def _init_async_ui_loading(self):
        """初始化异步UI加载"""
        self.ui_tasks = [
            ("创建顶部状态栏", self._async_create_top_status),
            ("创建主分割器", self._async_create_main_splitter),
            ("创建左侧面板管理器", self._async_create_left_panel_manager),
            ("创建右侧标签页", self._async_create_right_tab),
            ("设置布局", self._async_setup_layout),
            ("完成加载", self._async_finish_loading),
        ]
        self.current_task_index = 0
        self._process_next_ui_task()

    def _process_next_ui_task(self):
        """处理下一个UI任务"""
        # 如果加载已完成，不再处理后续任务
        if getattr(self, '_loading_complete', False):
            return
            
        if self.current_task_index < len(self.ui_tasks):
            task_name, task_func = self.ui_tasks[self.current_task_index]
            if self.loading_label:
                self.loading_label.setText(f"正在加载: {task_name}...")
            if self.loading_progress:
                progress = int((self.current_task_index / len(self.ui_tasks)) * 100)
                self.loading_progress.setValue(progress)

            # 使用默认参数捕获 task_func，避免闭包问题
            QTimer.singleShot(100, lambda tf=task_func: self._execute_task(tf))
        else:
            if self.loading_progress:
                self.loading_progress.setValue(100)
            if self.loading_label:
                self.loading_label.setText("加载完成!")

    def _execute_task(self, task_func):
        """执行任务"""
        from PySide6.QtWidgets import QApplication
        try:
            for _ in range(3):
                QApplication.processEvents()
            task_func()
            for _ in range(3):
                QApplication.processEvents()
        except Exception as e:
            self.logger.error(f"UI任务执行失败: {e}")
        self.current_task_index += 1
        QTimer.singleShot(100, self._process_next_ui_task)

    def _async_create_top_status(self):
        main = self.main_window
        try:
            from .core_ui_top_status_bar import TopStatusBar
            main.top_status = TopStatusBar()
            main.main_layout.addWidget(main.top_status)
        except ImportError:
            self.logger.warning("TopStatusBar导入失败")

    def _async_create_main_splitter(self):
        """创建主分割器"""
        main = self.main_window
        main.main_splitter = QSplitter(Qt.Horizontal)
        main.main_splitter.setHandleWidth(2)
        main.main_layout.addWidget(main.main_splitter)

    def _async_create_left_panel_manager(self):
        """创建左侧面板管理器 - 使用新的集成架构"""
        main = self.main_window
        self.logger.warning("🔧 开始创建左侧面板管理器...")
        try:
            # 先尝试使用新的集成面板
            from modules.ui.left_control_panel.integrated_left_panel import IntegratedLeftPanel
            self.logger.warning("🔧 正在创建 IntegratedLeftPanel 实例...")
            main.left_panel_manager = IntegratedLeftPanel(main)
            self.logger.warning("🔧 IntegratedLeftPanel 实例创建完成")
            main.left_panel = main.left_panel_manager
            main.main_splitter.addWidget(main.left_panel_manager)
            main.main_splitter.setStretchFactor(0, 0)  # 左侧面板不自动拉伸
            main.left_panel_manager.setMinimumWidth(320)  # 左侧面板最小宽度320px
            main.left_panel_manager.setMaximumWidth(420)  # 左侧面板最大宽度420px
            self.logger.warning("✅ 新的集成左侧面板加载成功")
        except ImportError as e1:
            self.logger.warning(f"集成面板导入失败: {e1}, 尝试使用传统面板")
            try:
                from modules.ui.left_control_panel.panel_manager import LeftPanelManager
                main.left_panel_manager = LeftPanelManager(main)
                main.left_panel = main.left_panel_manager
                main.main_splitter.addWidget(main.left_panel_manager)
                main.main_splitter.setStretchFactor(0, 0)
                main.left_panel_manager.setMinimumWidth(320)
                main.left_panel_manager.setMaximumWidth(420)
            except ImportError as e2:
                self.logger.error(f"LeftPanelManager导入失败: {e2}")
        except Exception as e:
            self.logger.error(f"左侧面板创建失败: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")

    def _async_create_right_tab(self):
        """创建右侧标签页"""
        main = self.main_window
        try:
            from modules.ui.core_ui.components.right_content_panel import RightContentPanel
            main.right_tab = RightContentPanel(main.config_manager)
            main.main_splitter.addWidget(main.right_tab)
            main.main_splitter.setStretchFactor(1, 1)  # 右侧面板自动填充剩余空间

        except ImportError as e:
            self.logger.warning(f"RightContentPanel导入失败: {e}，尝试使用RightTabContainer")
            try:
                from modules.ui.core_ui_main import RightTabContainer
                main.right_tab = RightTabContainer()
                main.main_splitter.addWidget(main.right_tab)
                main.main_splitter.setStretchFactor(1, 1)

            except ImportError as e2:
                self.logger.warning(f"RightTabContainer导入失败: {e2}")

    def _async_setup_layout(self):
        """设置布局"""
        main = self.main_window
        main.bottom_status = QStatusBar()
        main.setStatusBar(main.bottom_status)
        main.bottom_status.showMessage("系统就绪")
        
        # 设置初始宽度比例
        try:
            # 设置初始宽度：左侧360px，右侧填充剩余空间
            if hasattr(main, 'main_splitter'):
                total_width = main.geometry().width()
                left_width = 360  # 左侧标准宽度
                right_width = max(800, total_width - left_width - 20)  # 右侧至少800px
                main.main_splitter.setSizes([left_width, right_width])
                self.logger.info(f"面板宽度已设置: 左侧{left_width}px, 右侧{right_width}px")
        except Exception as e:
            self.logger.warning(f"设置初始宽度失败: {e}")

    def _async_finish_loading(self):
        """完成加载"""
        from PySide6.QtWidgets import QApplication
        main = self.main_window
        
        # 先标记加载完成，防止后续任务尝试访问已删除的组件
        self._loading_complete = True
        
        # 移除加载界面组件（而不是仅仅隐藏）
        if self.loading_label:
            main.main_layout.removeWidget(self.loading_label)
            self.loading_label.deleteLater()
            self.loading_label = None
        if self.loading_progress:
            main.main_layout.removeWidget(self.loading_progress)
            self.loading_progress.deleteLater()
            self.loading_progress = None
        
        # 移除布局中的 stretch 项，让分割器占据全部空间
        while main.main_layout.count() > 1:
            item = main.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for _ in range(3):
            QApplication.processEvents()
        
        main.apply_initial_styles()
        
        # 连接数据融合面板信号到右侧标签页
        self._connect_fusion_signals()
        
        # 注入DataBridge到各面板
        self._inject_data_bridge()

        # 独立设置缓存（不依赖DataBridge注入是否成功）
        QTimer.singleShot(1000, lambda: self._setup_cache_and_replay(None))
        
        self.logger.warning("✅ UI异步加载完成")
    
    def _connect_fusion_signals(self):
        """连接数据融合面板的信号"""
        main = self.main_window
        try:
            if (hasattr(main, 'left_panel') and hasattr(main, 'right_tab')):
                fusion_panel = None
                if hasattr(main.left_panel, 'fusion_panel'):
                    fusion_panel = main.left_panel.fusion_panel

                if fusion_panel is not None:
                    if hasattr(main.right_tab, 'real_time_monitoring_tab'):
                        main.right_tab.real_time_monitoring_tab.task_progress_changed.connect(
                            fusion_panel.update_task_progress
                        )
                        self.logger.info("任务进度信号已连接到数据融合面板")

                    self.logger.info("数据融合面板信号已连接到右侧标签页")

                if hasattr(main.left_panel, 'update_task_progress'):
                    if hasattr(main.right_tab, 'real_time_monitoring_tab'):
                        main.right_tab.real_time_monitoring_tab.task_progress_changed.connect(
                            main.left_panel.update_task_progress
                        )
                        self.logger.info("任务进度信号已连接到集成左侧面板")

                if hasattr(main.right_tab, 'tab_changed') and hasattr(main.left_panel, 'on_right_tab_changed'):
                    main.right_tab.tab_changed.connect(main.left_panel.on_right_tab_changed)
                    self.logger.info("右侧面板标签页切换信号已连接到集成左侧面板")
                else:
                    self.logger.warning("找不到数据融合面板")
            else:
                self.logger.warning("左面板或右面板不存在，无法连接数据融合信号")
        except Exception as e:
            self.logger.error(f"连接数据融合信号失败: {e}")

        self._wire_cnap_data_source()

        # 已禁用自动启动数据采集，改为通过UI"开始"按钮手动触发
        # QTimer.singleShot(2000, self._auto_start_data_collection)

    # 已禁用自动启动数据采集，改为通过UI"开始"按钮手动触发
    # def _auto_start_data_collection(self):
    #     """UI加载完成后自动启动数据采集"""
    #     try:
    #         main = self.main_window
    #         if not hasattr(main, 'left_panel') or not main.left_panel:
    #             self.logger.warning("左侧面板未就绪，跳过自动启动")
    #             return
    #
    #         fusion_panel = getattr(main.left_panel, 'fusion_panel', None)
    #         if not fusion_panel:
    #             self.logger.warning("数据融合面板未就绪，跳过自动启动")
    #             return
    #
    #         reader_manager = getattr(fusion_panel, 'reader_manager', None)
    #         if not reader_manager:
    #             self.logger.warning("数据读取器管理器未就绪，跳过自动启动")
    #             return
    #
    #         source_table = getattr(fusion_panel, 'source_table', None)
    #         if source_table:
    #             for row in range(source_table.rowCount()):
    #                 widget = source_table.cellWidget(row, 0)
    #                 if widget:
    #                     cb = widget.findChild(QCheckBox)
    #                     if cb:
    #                         cb.setChecked(True)
    #             self.logger.info("已自动勾选所有数据源")
    #
    #         fusion_panel._start_pipeline()
    #         self.logger.info("数据采集已自动启动")
    #     except Exception as e:
    #         self.logger.error(f"自动启动数据采集失败: {e}")

    def _inject_data_bridge(self, retry_count=0):
        """注入DataBridge到各面板（支持延迟重试，多路径获取）"""
        main = self.main_window
        try:
            data_bridge = None
            if hasattr(main, 'data_bridge') and main.data_bridge:
                data_bridge = main.data_bridge
            else:
                try:
                    from core.core.service_locator import ServiceLocator
                    data_bridge = ServiceLocator().get('data_bridge')
                    if data_bridge:
                        main.data_bridge = data_bridge
                        self.logger.info("DataBridge 从 ServiceLocator 获取成功")
                except Exception:
                    pass

            if not data_bridge:
                if retry_count < 10:
                    delay = 300 * (retry_count + 1)
                    self.logger.debug(f"DataBridge 未初始化，{delay}ms后第{retry_count+1}次重试")
                    QTimer.singleShot(delay, lambda: self._inject_data_bridge(retry_count + 1))
                else:
                    self.logger.error("DataBridge 注入失败：超过最大重试次数")
                return

            if hasattr(main, 'right_tab') and main.right_tab:
                if hasattr(main.right_tab, 'set_data_bridge'):
                    main.right_tab.set_data_bridge(data_bridge)
                    self.logger.info("DataBridge 已注入到右侧面板")

                # ── 注入 CacheRegistry ──
                if hasattr(main, '_cache_registry') and main._cache_registry:
                    if hasattr(main.right_tab, 'set_cache_registry'):
                        main.right_tab.set_cache_registry(main._cache_registry)
                        self.logger.info("CacheRegistry 已注入到右侧面板")

                if hasattr(main, '_pending_replay_controller') and main._pending_replay_controller:
                    if hasattr(main.right_tab, 'set_replay_controller'):
                        main.right_tab.set_replay_controller(main._pending_replay_controller)
                        enable_play = getattr(main, '_pending_replay_enable_play', False)
                        if enable_play and hasattr(main.right_tab, 'replay_bar'):
                            main.right_tab.replay_bar.set_play_enabled(True)
                            self.logger.info("暂存的回放控制器已注入到右侧面板，播放已启用（需手动点击播放）")
                        else:
                            self.logger.info("暂存的回放控制器已注入到右侧面板")
                    if hasattr(main, '_pending_replay_controller'):
                        del main._pending_replay_controller
                    if hasattr(main, '_pending_replay_data_bridge'):
                        del main._pending_replay_data_bridge
                    if hasattr(main, '_pending_replay_enable_play'):
                        del main._pending_replay_enable_play

                try:
                    from core.core.service_locator import ServiceLocator
                    seat_engine = ServiceLocator().get('seat_evaluation_engine')
                    comparative_engine = ServiceLocator().get('comparative_evaluation_engine')
                    if seat_engine and hasattr(main.right_tab, 'set_seat_evaluation_engine'):
                        main.right_tab.set_seat_evaluation_engine(seat_engine)
                        self.logger.info("座椅评测引擎已注入到右侧面板")
                    if comparative_engine and hasattr(main.right_tab, 'set_comparative_engine'):
                        main.right_tab.set_comparative_engine(comparative_engine)
                        self.logger.info("对照分析引擎已注入到右侧面板")
                except Exception as e:
                    self.logger.debug(f"注入座椅评测引擎到右侧面板失败（可能尚未初始化）: {e}")

            if hasattr(main, 'left_panel') and main.left_panel:
                if hasattr(main.left_panel, 'fusion_panel') and main.left_panel.fusion_panel:
                    if hasattr(main.left_panel.fusion_panel, 'set_data_bridge'):
                        main.left_panel.fusion_panel.set_data_bridge(data_bridge)
                        self.logger.info("DataBridge 已注入到数据融合面板")

                if hasattr(main.left_panel, 'set_data_bridge'):
                    main.left_panel.set_data_bridge(data_bridge)
                    self.logger.info("DataBridge 已注入到左侧集成面板")

            self._setup_cache_and_replay(data_bridge)

            if hasattr(main, '_multi_source_cache') and main._multi_source_cache:
                data_bridge.set_cache(main._multi_source_cache)
                self.logger.info("已将 MultiSourceCache 注入到 DataBridge（延迟注入）")

        except Exception as e:
            self.logger.error(f"注入DataBridge失败: {e}")
            if retry_count < 3:
                QTimer.singleShot(500, lambda: self._inject_data_bridge(retry_count + 1))

    def _find_existing_cache(self):
        """查找已有的缓存文件，返回最近且有数据的缓存路径"""
        try:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                'data_output'
            )
            if not os.path.isdir(output_dir):
                return None

            cache_files = glob.glob(os.path.join(output_dir, 'cache_*.db'))
            if not cache_files:
                return None

            cache_files.sort(key=os.path.getmtime, reverse=True)

            for cache_path in cache_files:
                try:
                    size = os.path.getsize(cache_path)
                    if size < 8192:
                        continue
                    conn = sqlite3.connect(cache_path)
                    row = conn.execute("SELECT COUNT(*) FROM data_records").fetchone()
                    conn.close()
                    if row and row[0] > 0:
                        self.logger.info(f"找到已有缓存: {cache_path}, {row[0]}条记录, {size}字节")
                        return cache_path
                except Exception:
                    continue

            return None
        except Exception as e:
            self.logger.warning(f"查找已有缓存失败: {e}")
            return None

    def _load_events_from_previous_cache(self, data_bridge):
        """从最近的分析缓存文件中加载已有事件和FrameResults到当前缓存"""
        try:
            analysis_cache = data_bridge.get_analysis_cache()
            if not analysis_cache:
                return

            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                'data_output'
            )
            if not os.path.isdir(output_dir):
                return

            analysis_files = glob.glob(os.path.join(output_dir, 'analysis_results_*.db'))
            current_db = analysis_cache.db_path
            analysis_files = [f for f in analysis_files if os.path.abspath(f) != os.path.abspath(current_db)]
            if not analysis_files:
                return

            analysis_files.sort(key=os.path.getmtime, reverse=True)

            for prev_db in analysis_files:
                try:
                    prev_conn = sqlite3.connect(prev_db)
                    row = prev_conn.execute("SELECT COUNT(*) FROM behavior_events").fetchone()
                    event_count = row[0] if row else 0
                    fr_row = prev_conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()
                    fr_count = fr_row[0] if fr_row else 0

                    if event_count == 0 and fr_count == 0:
                        prev_conn.close()
                        continue

                    curr_conn = analysis_cache._get_conn()

                    if event_count > 0:
                        cursor = prev_conn.execute(
                            "SELECT start_time, end_time, event_data, created_at FROM behavior_events ORDER BY start_time"
                        )
                        events_data = cursor.fetchall()
                        for start_time, end_time, event_data, created_at in events_data:
                            try:
                                curr_conn.execute(
                                    "INSERT OR IGNORE INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                                    (start_time, end_time, event_data, created_at or time.time())
                                )
                            except Exception:
                                pass
                        self.logger.info(f"从已有分析缓存加载了 {len(events_data)} 个事件: {os.path.basename(prev_db)}")

                    if fr_count > 0:
                        fr_cursor = prev_conn.execute(
                            "SELECT timestamp, frame_result, created_at FROM analysis_results ORDER BY timestamp"
                        )
                        batch = []
                        loaded_fr = 0
                        for ts, fr_json, created_at in fr_cursor:
                            batch.append((ts, fr_json, created_at or time.time()))
                            if len(batch) >= 500:
                                curr_conn.executemany(
                                    "INSERT OR IGNORE INTO analysis_results (timestamp, frame_result, created_at) VALUES (?, ?, ?)",
                                    batch
                                )
                                loaded_fr += len(batch)
                                batch.clear()
                        if batch:
                            curr_conn.executemany(
                                "INSERT OR IGNORE INTO analysis_results (timestamp, frame_result, created_at) VALUES (?, ?, ?)",
                                batch
                            )
                            loaded_fr += len(batch)

                        min_max = prev_conn.execute(
                            "SELECT MIN(timestamp), MAX(timestamp) FROM analysis_results"
                        ).fetchone()
                        if min_max[0] is not None:
                            with analysis_cache._lock:
                                if analysis_cache._time_min is None or min_max[0] < analysis_cache._time_min:
                                    analysis_cache._time_min = min_max[0]
                                if analysis_cache._time_max is None or min_max[1] > analysis_cache._time_max:
                                    analysis_cache._time_max = min_max[1]
                                analysis_cache._total_records += loaded_fr

                        self.logger.info(f"从已有分析缓存加载了 {loaded_fr} 条FrameResult: {os.path.basename(prev_db)}")

                    curr_conn.commit()
                    prev_conn.close()
                    return
                except Exception as e:
                    self.logger.debug(f"尝试加载分析缓存 {prev_db} 失败: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"从已有缓存加载事件失败: {e}")

    def _setup_cache_and_replay(self, data_bridge):
        """设置磁盘缓存和回放控制器"""
        main = self.main_window
        if hasattr(main, '_cache_and_callback_setup_done') and main._cache_and_callback_setup_done:
            return

        try:
            from core.core.data_processing.multi_source_cache import MultiSourceCache

            existing_cache = None
            if hasattr(main, '_multi_source_cache') and main._multi_source_cache:
                cache = main._multi_source_cache
                self.logger.info(f"复用已有缓存对象: {cache.db_path}")
            else:
                # ── 始终创建新缓存文件，从不覆盖旧缓存 ──
                # 旧缓存由 CacheRegistry 管理，可通过下拉框切换
                existing_cache = self._find_existing_cache()
                cache = MultiSourceCache()  # 生成新时间戳文件名
                stats = cache.get_stats()
                if existing_cache:
                    self.logger.info(f"已有历史缓存: {existing_cache}, 新建缓存: {cache.db_path}")
                else:
                    self.logger.info(f"创建新缓存: {cache.db_path}")

                main._multi_source_cache = cache

            # ── CacheRegistry 初始化 ──
            if not hasattr(main, '_cache_registry') or main._cache_registry is None:
                from core.core.data_processing.cache_registry import CacheRegistry
                output_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))))),
                    'data_output'
                )
                main._cache_registry = CacheRegistry(output_dir)
                self.logger.info(f"CacheRegistry 已初始化: {main._cache_registry.count} 个已注册缓存")

            # ── 预注册新缓存到 CacheRegistry（允许显示空缓存）──
            if hasattr(main, '_cache_registry') and main._cache_registry:
                try:
                    analysis_path = ''
                    if data_bridge:
                        analysis_cache = data_bridge.get_analysis_cache()
                        if analysis_cache and hasattr(analysis_cache, 'db_path'):
                            analysis_path = analysis_cache.db_path
                    main._cache_registry.register(cache.db_path, analysis_path, force=True)
                    self.logger.info(f"新缓存已预注册到 CacheRegistry: {cache.db_path}")
                except Exception as e:
                    self.logger.debug(f"预注册新缓存失败: {e}")

            if not data_bridge:
                self.logger.info("DataBridge 尚不可用，调用将被拦截等待注入后再设回调")

            if data_bridge:
                data_bridge.enable_result_caching()
                self.logger.info(f"分析结果缓存已启用: {data_bridge.get_analysis_cache().db_path if data_bridge.get_analysis_cache() else 'N/A'}")
                # 不再自动从旧缓存加载事件 — 事件仅在用户显式选择 SQLite 缓存数据集并开始分析后产生
                # 旧代码: _load_events_from_previous_cache() + EventDistributor.sync_from_cache()

            if hasattr(main, 'right_tab') and main.right_tab:
                if hasattr(main.right_tab, 'set_cache'):
                    main.right_tab.set_cache(cache)
                    self.logger.info("MultiSourceCache 已提前注入到右侧面板")
                # ── 注入 CacheRegistry ──
                if hasattr(main, '_cache_registry') and main._cache_registry:
                    if hasattr(main.right_tab, 'set_cache_registry'):
                        main.right_tab.set_cache_registry(main._cache_registry)
                        self.logger.info("CacheRegistry 已提前注入到右侧面板")

            fusion_panel = getattr(main.left_panel, 'fusion_panel', None) if hasattr(main, 'left_panel') else None
            reader_manager = getattr(fusion_panel, 'reader_manager', None) if fusion_panel else None

            if reader_manager:
                reader_manager.set_cache(cache)
                main._exhausted_sources = set()
                main._total_sources = len(reader_manager.readers)
                if data_bridge:
                    reader_manager.set_file_exhausted_callback(
                        lambda src_id, count: self._on_parsing_complete(src_id, count, cache, data_bridge)
                    )
                    self.logger.info(f"缓存和文件耗尽回调已设置, 共 {main._total_sources} 个数据源")
                else:
                    self.logger.info(f"缓存已设置 (共 {main._total_sources} 个数据源)，DataBridge就绪后再设回调")

            # ── 回放控制器：优先加载有数据的历史缓存 ──
            hist_cache = existing_cache  # 历史缓存路径（可能为 None）
            if data_bridge and hist_cache and cache.get_total_records() == 0:
                # 新缓存为空但历史缓存存在 → 用历史缓存创建回放控制器
                self.logger.info(f"新缓存为空，加载历史缓存到回放控制器: {hist_cache}")
                from core.core.data_processing.multi_source_cache import MultiSourceCache as MSCache
                replay_cache = MSCache(db_path=hist_cache)
                main._replay_created = True
                self._create_replay_controller(replay_cache, data_bridge, enable_play=True)
                # 仍然设置新缓存为读写目标
                data_bridge.set_cache(cache) if hasattr(data_bridge, 'set_cache') else None
                main._cache_and_callback_setup_done = True
            elif data_bridge and hist_cache and cache.get_total_records() > 0:
                main._replay_created = True
                self.logger.info(f"新缓存已有数据，直接创建回放控制器: {cache.get_total_records()}条")
                self._create_replay_controller(cache, data_bridge, enable_play=True)
                main._cache_and_callback_setup_done = True
            elif data_bridge and reader_manager:
                QTimer.singleShot(1000, lambda: self._try_create_replay_controller_early(cache, data_bridge))
                self._start_cache_poll_timer(cache, data_bridge)
                main._cache_and_callback_setup_done = True
            elif not data_bridge:
                self.logger.info(f"DataBridge 尚不可用，缓存已就绪，等待DataBridge注入")
                main._data_bridge_pending = True
            else:
                self.logger.warning("DataReaderManager 未就绪且无已有缓存，延迟设置缓存")
                QTimer.singleShot(2000, lambda: self._setup_cache_and_replay(data_bridge))

        except Exception as e:
            self.logger.error(f"设置缓存和回放失败: {e}")

    def _start_cache_poll_timer(self, cache, data_bridge):
        """启动周期性缓存轮询定时器，检测缓存数据是否足够创建回放控制器"""
        main = self.main_window
        if hasattr(main, '_cache_poll_timer') and main._cache_poll_timer is not None:
            return

        poll_timer = QTimer()
        poll_timer.setInterval(3000)
        poll_timer.timeout.connect(lambda: self._try_create_replay_controller_early(cache, data_bridge))
        poll_timer.start()
        main._cache_poll_timer = poll_timer
        self.logger.info("缓存轮询定时器已启动 (每3秒检查一次)")

    def _try_create_replay_controller_early(self, cache, data_bridge):
        """提前创建回放控制器，当缓存数据足够时不等所有数据源读完"""
        main = self.main_window
        if hasattr(main, '_replay_created') and main._replay_created:
            if hasattr(main, '_cache_poll_timer') and main._cache_poll_timer is not None:
                main._cache_poll_timer.stop()
                main._cache_poll_timer = None
                self.logger.info("回放控制器已创建，停止缓存轮询")
            return

        try:
            stats = cache.get_stats()
        except Exception as e:
            self.logger.warning(f"获取缓存统计失败: {e}")
            return

        if stats['total_records'] < 500:
            return

        if hasattr(main, '_cache_poll_timer') and main._cache_poll_timer is not None:
            main._cache_poll_timer.stop()
            main._cache_poll_timer = None

        main._replay_created = True
        self.logger.info(f"提前创建回放控制器: {stats['total_records']}条, "
                         f"时长={stats['duration']:.1f}s, 类型={stats['source_types']}")
        self._create_replay_controller(cache, data_bridge, enable_play=True)

    def _on_parsing_complete(self, src_id, count, cache, data_bridge):
        main = self.main_window
        if not hasattr(main, '_exhausted_sources'):
            main._exhausted_sources = set()

        main._exhausted_sources.add(src_id)
        exhausted_count = len(main._exhausted_sources)

        # 动态获取当前数据源总数（仅统计已启动的 reader）
        reader_manager = None
        if hasattr(main, 'left_panel') and hasattr(main.left_panel, 'fusion_panel'):
            fusion_panel = main.left_panel.fusion_panel
            if fusion_panel and hasattr(fusion_panel, 'reader_manager'):
                reader_manager = fusion_panel.reader_manager
        total = len(reader_manager._started_reader_ids) if reader_manager else getattr(main, '_total_sources', 1)

        self.logger.info(f"文件耗尽回调触发: src={src_id}, count={count}, "
                         f"已完成={exhausted_count}/{total} [动态]")

        if exhausted_count < total:
            self.logger.info(f"还有 {total - exhausted_count} 个数据源未完成，等待中...")
            return

        self.logger.info("所有数据源加载完成")

        if hasattr(main, '_replay_created') and main._replay_created:
            self.logger.info("回放控制器已提前创建，检查事件状态...")
            replay_ctrl = getattr(main, '_pending_replay_controller', None)
            if replay_ctrl is None and hasattr(main, 'right_tab'):
                replay_ctrl = getattr(main.right_tab, '_replay_controller', None)
            if replay_ctrl and data_bridge:
                existing = len(replay_ctrl.get_events()) if replay_ctrl else 0
                self.logger.info(f"所有数据就绪，全量重新生成事件 (已有{existing}个事件将被覆盖)")
                # 清除 _event_gen 状态，允许重新运行
                self._event_gen_running = False
                self._event_gen_done = False
                # 使用信号槽在主线程执行（避免 QTimer 跨线程问题）
                main._parsing_all_complete.emit(cache, data_bridge)
            return

        main._parsing_all_complete.emit(cache, data_bridge)

    def _create_replay_controller(self, cache, data_bridge, enable_play=False):
        """在主线程创建回放控制器"""
        main = self.main_window
        try:
            stats = cache.get_stats()
            self.logger.info(f"数据解析完成: {stats['total_records']}条, "
                             f"时长={stats['duration']:.1f}s, 类型={stats['source_types']}")

            data_bridge.set_suppress_ui_signals(True)

            from core.core.data_processing.multi_source_replay_controller import MultiSourceReplayController
            replay_ctrl = MultiSourceReplayController()
            if replay_ctrl.load_cache(cache):
                # 加载分析结果缓存
                analysis_cache = data_bridge.get_analysis_cache()
                if analysis_cache:
                    has_results = replay_ctrl.load_analysis_cache(analysis_cache)
                    self.logger.info(f"分析结果缓存已加载: {'成功' if has_results else '无数据'}")
                    # 设置默认回放模式
                    if has_results:
                        all_events = analysis_cache.get_all_maneuver_events()
                        if all_events and len(all_events) > 0:
                            replay_ctrl.set_replay_mode('fast')
                            self.logger.info(f"默认使用快速回放模式 (已有{len(all_events)}个事件)")
                        else:
                            replay_ctrl.set_replay_mode('reanalyze')
                            self.logger.info("分析结果缓存有FrameResult但无事件，使用重新分析模式")
                    else:
                        replay_ctrl.set_replay_mode('reanalyze')
                        self.logger.info("分析结果缓存无数据，使用重新分析模式")
                else:
                    replay_ctrl.set_replay_mode('reanalyze')
                    self.logger.info("无分析结果缓存，使用重新分析模式")
                
                if hasattr(main, 'right_tab') and main.right_tab:
                    if hasattr(main.right_tab, 'set_data_bridge'):
                        main.right_tab.set_data_bridge(data_bridge)
                        self.logger.info("DataBridge 已注入到右侧面板")
                    
                    if hasattr(main.right_tab, 'set_replay_controller'):
                        main.right_tab.set_replay_controller(replay_ctrl)
                        if enable_play and hasattr(main.right_tab, 'replay_bar'):
                            main.right_tab.replay_bar.set_play_enabled(True)
                            self.logger.info("MultiSourceReplayController 已注入到右侧面板，播放已启用（需手动点击播放）")
                            # ── 填充缓存选择器 ──
                            if hasattr(main, '_cache_registry') and main._cache_registry:
                                try:
                                    main.right_tab.replay_bar.set_cache_list(
                                        main._cache_registry.list_caches()
                                    )
                                except Exception as e:
                                    self.logger.debug(f"填充缓存选择器失败: {e}")
                            # 不自动播放，等待用户手动点击播放按钮
                        elif hasattr(main.right_tab, 'replay_bar'):
                            main.right_tab.replay_bar.set_play_enabled(False)
                            # ── 填充缓存选择器 ──
                            if hasattr(main, '_cache_registry') and main._cache_registry:
                                try:
                                    main.right_tab.replay_bar.set_cache_list(
                                        main._cache_registry.list_caches()
                                    )
                                except Exception as e:
                                    self.logger.debug(f"填充缓存选择器失败: {e}")
                            self.logger.info("MultiSourceReplayController 已注入到右侧面板，请手动点击播放按钮开始")
                        else:
                            self.logger.info("MultiSourceReplayController 已注入到右侧面板")
                else:
                    main._pending_replay_controller = replay_ctrl
                    main._pending_replay_data_bridge = data_bridge
                    main._pending_replay_enable_play = enable_play
                    self.logger.info("右侧面板未就绪，回放控制器已暂存，等待右侧面板创建后注入")
                    self._start_pending_replay_injection_timer()
            
            # 取消抑制 UI 信号，让数据可以正常传递
            data_bridge.set_suppress_ui_signals(False)

            events = replay_ctrl.get_events()
            total = cache.get_total_records()
            if total > 0 and (not events or len(events) < 1):
                self.logger.info(f"缓存有{total}条数据，{len(events)}个已有事件。等待全部数据就绪后将自动全量生成。")
            else:
                self.logger.info(f"已有 {len(events) if events else 0} 个事件，跳过批量生成调度")
            
        except Exception as e:
            self.logger.error(f"创建回放控制器失败: {e}")
            # 即使出错也尝试取消抑制
            try:
                data_bridge.set_suppress_ui_signals(False)
            except:
                pass

    def _generate_events_from_cache(self, cache, data_bridge, replay_ctrl):
        """从缓存全量数据通过 DrivingEventDetector 生成事件（替代旧状态机管线）"""
        
        if getattr(self, '_event_gen_running', False):
            self.logger.warning("事件生成已在运行中，跳过重复触发")
            return

        # 存储引用供 _check_event_gen_done 使用
        self._event_gen_cache = cache
        self._event_gen_data_bridge = data_bridge
        self._event_gen_replay_ctrl = replay_ctrl

        try:
            analysis_cache = data_bridge.get_analysis_cache()
            if not analysis_cache:
                self.logger.warning("分析缓存未就绪，跳过事件生成")
                return

            imu_time_range = cache.get_time_range_for_sources(['can_long'])
            if imu_time_range[0] is None:
                retry_count = getattr(self, '_event_gen_retry_count', 0) + 1
                self._event_gen_retry_count = retry_count
                if retry_count <= 60:
                    self.logger.warning(f"缓存中尚无 can_long (IMU) 数据，{5}秒后重试 (第{retry_count}次)")
                    QTimer.singleShot(5000, lambda: self._generate_events_from_cache(cache, data_bridge, replay_ctrl))
                else:
                    self.logger.warning(f"缓存中无 can_long (IMU) 数据，已重试{retry_count}次，放弃事件生成")
                    self._event_gen_done = True
                    self._event_gen_count = 0
                return

            t_min, t_max = imu_time_range
            self._event_gen_retry_count = 0
            self._event_gen_running = True

            # 获取全量记录
            all_records = cache.query_records_raw(t_min, t_max, ['can_long'])
            self.logger.info(
                f"全量事件生成: {len(all_records)} 条记录, "
                f"时间范围 [{t_min:.2f}s, {t_max:.2f}s]"
            )

            # 清空旧分析结果（由之前的快速/增量分析留下）
            analysis_cache._clear_events()
            # 清空 EventDistributor 旧事件
            from core.core.analysis.event_distributor import EventDistributor
            EventDistributor.instance().clear()
            self.logger.info("已清空旧事件缓存和分发器，使用 DrivingEventDetector 全量重新生成")

            # 使用 DrivingEventDetector 批量分析（22事件类型，替代旧状态机6状态）
            result = data_bridge.analyze_records_batch(all_records)
            events = result.get('events', [])

            self.logger.info(
                f"全量事件生成完成: {len(events)} 个事件, "
                f"accel_range={result.get('vehicle_accel_range')}"
            )

            self._event_gen_count = len(events)
            self._event_gen_done = True
            self._event_gen_running = False

        except Exception as e:
            self.logger.error(f"事件生成失败: {e}")
            import traceback
            traceback.print_exc()
            self._event_gen_done = True
            self._event_gen_running = False

    def _check_event_gen_done(self):
        """主线程轮询检查事件生成是否完成"""
        if not getattr(self, '_event_gen_done', True):
            return

        if hasattr(self, '_event_gen_check_timer'):
            self._event_gen_check_timer.stop()
            del self._event_gen_check_timer

        count = getattr(self, '_event_gen_count', 0)
        if count > 0:
            data_bridge = getattr(self, '_event_gen_data_bridge', None)
            replay_ctrl = getattr(self, '_event_gen_replay_ctrl', None)

            try:
                from core.core.analysis.event_distributor import EventDistributor
                distributor = EventDistributor.instance()
                synced = distributor.sync_from_cache()
                self.logger.info(f"EventDistributor 从缓存批量同步了 {synced} 个事件（批量生成{count}个）")
            except Exception as e:
                self.logger.error(f"EventDistributor 缓存同步失败: {e}")

            if replay_ctrl:
                analysis_cache = data_bridge.get_analysis_cache() if data_bridge else None
                if analysis_cache:
                    has_results = replay_ctrl.load_analysis_cache(analysis_cache)
                    if has_results:
                        replay_ctrl.set_replay_mode('fast')
                        self.logger.info(f"事件生成完成，回放模式已切换为 fast，共{synced if synced else count}个事件")
                    else:
                        self.logger.warning("事件生成完成但分析缓存无数据")
                else:
                    self.logger.warning("事件生成完成但分析缓存未就绪")

            # ── 刷新 CacheRegistry 元数据 ──
            main = self.main_window
            event_gen_cache = getattr(self, '_event_gen_cache', None)
            if hasattr(main, '_cache_registry') and main._cache_registry and event_gen_cache:
                cache_db_path = event_gen_cache.db_path if hasattr(event_gen_cache, 'db_path') else ''
                if cache_db_path:
                    try:
                        refreshed = main._cache_registry.refresh_entry(cache_db_path)
                        self.logger.info(f"CacheRegistry 元数据刷新: {'成功' if refreshed else '跳过'}")
                    except Exception as e:
                        self.logger.warning(f"CacheRegistry 元数据刷新失败: {e}")
                # ── 刷新回放栏缓存列表 ──
                if hasattr(main, 'right_tab') and main.right_tab:
                    try:
                        caches = main._cache_registry.list_caches()
                        if hasattr(main.right_tab, 'replay_bar') and main.right_tab.replay_bar:
                            main.right_tab.replay_bar.set_cache_list(caches)
                            self.logger.info(f"回放栏缓存列表已刷新: {len(caches)} 个缓存")
                    except Exception as e:
                        self.logger.warning(f"刷新回放栏缓存列表失败: {e}")

    def _sync_events_to_event_mapper(self, maneuver_events):
        """将ManeuverEvent同步到EventDistributor（唯一事件分发中心）"""
        try:
            from core.core.analysis.event_distributor import EventDistributor
            distributor = EventDistributor.instance()
            distributor.clear()
            registered = distributor.register_events(maneuver_events)
            self.logger.info(f"事件已同步到EventDistributor: {registered}个")

            main = self.main_window
            if hasattr(main, 'right_tab') and main.right_tab:
                if hasattr(main.right_tab, 'can_full_tab') and main.right_tab.can_full_tab:
                    if hasattr(main.right_tab.can_full_tab, '_update_event_stats'):
                        main.right_tab.can_full_tab._update_event_stats()
                        self.logger.info("CAN全量解析事件统计已更新")
                if hasattr(main.right_tab, 'seat_evaluation_tab') and main.right_tab.seat_evaluation_tab:
                    if hasattr(main.right_tab.seat_evaluation_tab, '_event_panel') and main.right_tab.seat_evaluation_tab._event_panel:
                        main.right_tab.seat_evaluation_tab._event_panel.refresh_events()
                        self.logger.info("座椅评测事件面板已刷新")
        except Exception as e:
            self.logger.error(f"同步事件到EventDistributor失败: {e}")

    def _start_pending_replay_injection_timer(self):
        main = self.main_window
        if hasattr(main, '_pending_injection_retry_count'):
            return

        main._pending_injection_retry_count = 0

        def try_inject():
            main = self.main_window
            if not hasattr(main, '_pending_replay_controller') or not main._pending_replay_controller:
                if hasattr(main, '_pending_injection_timer') and main._pending_injection_timer:
                    main._pending_injection_timer.stop()
                    main._pending_injection_timer = None
                return

            main._pending_injection_retry_count += 1

            if hasattr(main, 'right_tab') and main.right_tab:
                if hasattr(main.right_tab, 'set_replay_controller'):
                    if hasattr(main, '_pending_injection_timer') and main._pending_injection_timer:
                        main._pending_injection_timer.stop()
                        main._pending_injection_timer = None
                    pending_ctrl = main._pending_replay_controller
                    enable_play = getattr(main, '_pending_replay_enable_play', False)
                    if hasattr(main, '_pending_replay_controller'):
                        del main._pending_replay_controller
                    if hasattr(main, '_pending_replay_data_bridge'):
                        del main._pending_replay_data_bridge
                    if hasattr(main, '_pending_replay_enable_play'):
                        del main._pending_replay_enable_play
                    main.right_tab.set_replay_controller(pending_ctrl)
                    if enable_play and hasattr(main.right_tab, 'replay_bar'):
                        main.right_tab.replay_bar.set_play_enabled(True)
                        self.logger.info("暂存的回放控制器已注入到右侧面板（重试成功），播放已启用（需手动点击播放）")
                    else:
                        self.logger.info("暂存的回放控制器已注入到右侧面板（重试成功）")
                if hasattr(main, '_pending_injection_retry_count'):
                    del main._pending_injection_retry_count
                return

            if main._pending_injection_retry_count > 30:
                self.logger.warning("回放控制器注入超时，右侧面板始终未就绪")
                if hasattr(main, '_pending_injection_timer') and main._pending_injection_timer:
                    main._pending_injection_timer.stop()
                    main._pending_injection_timer = None
                return

        main._pending_injection_timer = QTimer()
        main._pending_injection_timer.timeout.connect(try_inject)
        main._pending_injection_timer.start(500)
        self.logger.info("回放控制器注入重试定时器已启动（每500ms检查一次）")

    def _wire_cnap_data_source(self):
        """接线 CNAP 数据源到 CNAP 可视化标签页"""
        main = self.main_window
        try:
            from modules.ui.real_data_interface_manager import RealDataInterfaceManager
            main.cnap_data_manager = RealDataInterfaceManager()
            main.cnap_data_manager.cnap_data_updated.connect(
                main.right_tab.receive_cnap_data
            )
            self.logger.info("CNAP 实时数据管道已接通")
        except ImportError:
            self.logger.warning("RealDataInterfaceManager 不可用，CNAP 数据管道未接通")
        except AttributeError:
            self.logger.warning("右侧面板缺少 receive_cnap_data，CNAP 数据管道未接通")
        except Exception as e:
            self.logger.error(f"接线 CNAP 数据管道失败: {e}")
