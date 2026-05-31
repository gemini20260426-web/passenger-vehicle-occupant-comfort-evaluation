#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core UI 主窗口基础模块
包含 CoreUIMainWindow 类的基础定义、信号定义、窗口管理
"""

import sys
import os
import time
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QComboBox, QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QProgressBar, QSplitter,
    QStatusBar, QCheckBox, QSlider, QGridLayout,
    QMessageBox, QMenu, QMenuBar, QDialog,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialogButtonBox,
    QScrollArea, QStyle, QSpinBox, QFrame, QTableWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QDateTime, QSettings, QTranslator
from PySide6.QtGui import QPalette, QColor, QFont, QIcon, QActionGroup, QAction, QShortcut, QKeySequence

from .core_ui_utils import translations, get_light_theme_style, get_dark_theme_style
from .core_ui_components import CoreUIComponents


class CoreUIMainWindow(QMainWindow):
    data_source_connected = Signal(str)
    analysis_requested = Signal(dict)
    system_status_changed = Signal(str)
    data_updated = Signal(dict)
    update_system_metrics = Signal(float, float, float)
    _parsing_all_complete = Signal(object, object)

    current_lang = 'en'

    def __init__(self):
        super().__init__()

        self.setup_exception_handling()

        try:
            from config.logging_setup import get_logger
            self.logger = get_logger(__name__)
        except ImportError:
            self.logger = logging.getLogger(__name__)

        self.logger.info("开始初始化主窗口")

        self.setWindowTitle("Core System Dashboard")

        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            sw, sh = available.width(), available.height()
        else:
            sw, sh = 1920, 1080

        default_w = int(sw * 0.88)
        default_h = int(sh * 0.85)
        default_x = max(0, (sw - default_w) // 2)
        default_y = max(0, (sh - default_h) // 2)
        self.setGeometry(default_x, default_y, default_w, default_h)
        self.setMinimumSize(min(1200, sw - 40), min(700, sh - 40))

        self.settings = QSettings("CoreSystem", "Dashboard")
        saved_geometry = self.settings.value("window/geometry")
        if saved_geometry is not None:
            self.restoreGeometry(saved_geometry)
        saved_state = self.settings.value("window/state")
        if saved_state is not None:
            self.restoreState(saved_state)

        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self.current_lang = 'en'
        self.init_translations()

        self._apply_professional_theme()

        try:
            from config.config_manager import ConfigManager
            self.config_manager = ConfigManager.instance()
            self.logger.info("配置管理器导入成功（统一实例）")
        except Exception as e:
            self.logger.warning(f"配置管理器导入失败 {e},使用默认配置")
            self.config_manager = None

        self._import_core_modules()

        try:
            from .security_manager import SecurityManager
            self.security_manager = SecurityManager()
        except ImportError:
            try:
                from modules.ui.security_manager import SecurityManager
                self.security_manager = SecurityManager()
            except ImportError:
                self.logger.warning("安全管理器导入失败,使用默认安全配置")
                self.security_manager = None

        try:
            from .user_manager import UserManager
            self.user_manager = UserManager()
        except ImportError:
            try:
                from modules.ui.user_manager import UserManager
                self.user_manager = UserManager()
            except ImportError:
                self.logger.warning("用户管理器导入失败,使用默认用户配置")
                self.user_manager = None

        try:
            from .system_integration import ExtensionIntegrationWidget
            self.integration_widget = ExtensionIntegrationWidget()
        except ImportError:
            try:
                from modules.ui.system_integration import ExtensionIntegrationWidget
                self.integration_widget = ExtensionIntegrationWidget()
            except ImportError:
                self.logger.warning("系统集成管理器导入失败,使用默认配置")
                self.integration_widget = None

        self.data_sources = {}
        self.active_source_id = None
        self.data_count = 0
        self.behavior_stats = {}

        self.init_ui()
        self.connect_signals()

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(10000)

        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)

        self.health_monitor_timer = QTimer()
        self.health_monitor_timer.timeout.connect(self._check_data_update_health)
        self.health_monitor_timer.start(30000)

        self.last_data_update_time = time.time()
        self.data_update_failures = 0
        self.max_failures = 3

        self.monitoring_broadcast_enabled = False

        try:
            from modules.ui.data_pipeline_manager import DataPipelineManager
            self.data_pipeline_manager = DataPipelineManager(self)
            self.data_pipeline_manager.data_flow_status_changed.connect(self._on_data_flow_status_changed)
            self.data_pipeline_manager.data_pipeline_health_updated.connect(self._on_data_pipeline_health_updated)
            self.data_pipeline_manager.module_data_received.connect(self._on_module_data_received)
            self.logger.info("数据流管道管理器已集成")
        except ImportError as e:
            self.logger.warning(f"无法导入数据流管道管理器: {e}")
            self.data_pipeline = {
                'sensor_data': None,
                'parsing_status': None,
                'analysis_result': None,
                'advanced_analysis_result': None,
                'system_status': None,
                'data_flow_status': 'initialized'
            }
            self.data_pipeline_health = {
                'last_update': time.time(),
                'update_count': 0,
                'error_count': 0,
                'health_score': 100,
                'data_flow_health': 100,
                'module_health': {}
            }

        self.update_system_metrics.connect(self.update_system_metrics_ui)
        self.setup_system_monitoring()

        if not hasattr(self, 'data_pipeline_manager'):
            self.setup_data_pipeline_monitoring()

        self.logger.info("主窗口初始化完成")

    def _apply_professional_theme(self):
        try:
            from modules.ui.professional_styles import PRO_GLOBAL_STYLE
            self.setStyleSheet(PRO_GLOBAL_STYLE)
            self.logger.info("专业UI主题已应用")
        except ImportError:
            self.logger.warning("专业UI样式模块不可用,使用默认样式")

    def init_ui(self):
        self.ui_components = CoreUIComponents(self)
        self.ui_components.init_ui()
        self._parsing_all_complete.connect(self._on_all_parsing_complete)

    def connect_signals(self):
        try:
            from .core_ui_handlers import CoreUIHandlers
            self.ui_handlers = CoreUIHandlers(self)
            self.ui_handlers.connect_signals()
        except ImportError:
            self.logger.warning("CoreUIHandlers导入失败")

    def create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu(translations['en']['file'])

        new_action = QAction(translations['en']['new'], self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_session)
        file_menu.addAction(new_action)

        open_action = QAction(translations['en']['open'], self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        save_action = QAction(translations['en']['save'], self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_data)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        config_action = QAction(translations['en']['configuration'], self)
        config_action.setShortcut("Ctrl+,")
        config_action.triggered.connect(self._on_open_system_config)
        file_menu.addAction(config_action)

        file_menu.addSeparator()

        exit_action = QAction(translations['en']['exit'], self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu(translations['en']['view'])

        lang_menu = view_menu.addMenu(translations['en']['language'])
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        en_action = QAction(translations['en']['english'], self, checkable=True)
        zh_action = QAction(translations['en']['chinese'], self, checkable=True)
        en_action.setChecked(True)

        en_action.triggered.connect(lambda: self._set_language('en'))
        zh_action.triggered.connect(lambda: self._set_language('zh'))

        lang_group.addAction(en_action)
        lang_group.addAction(zh_action)
        lang_menu.addAction(en_action)
        lang_menu.addAction(zh_action)

        help_menu = menubar.addMenu(translations['en']['help'])

        about_action = QAction(translations['en']['about'], self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _on_new_session(self):
        QMessageBox.information(self, translations['en']['new_session'], translations['en']['new_session_msg'])

    def _on_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, translations['en']['open_data_file'], "", "Data Files (*.csv *.txt *.json)")
        if file_path:
            self.logger.info(f"打开文件: {file_path}")
            self._load_file_into_pipeline(file_path)

    def _load_file_into_pipeline(self, file_path: str):
        """解析CSV/TXT文件并注入数据管线（缓存→DataBridge→回放控制器→全部Tab）"""
        import csv

        try:
            # 1. 解析文件为记录列表
            records = []
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.csv':
                with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 标准化字段：适配 parsed_data 格式和原始IMU格式
                        rec = {}
                        # rel_time / timestamp
                        rec['rel_time'] = float(row.get('rel_time', row.get('timestamp', 0)))
                        rec['timestamp'] = rec['rel_time']
                        # 加速度
                        for key_src, key_dst in [('Ax_m_s2', 'ax'), ('Ay_m_s2', 'ay'), ('Az_m_s2', 'az'),
                                                  ('Gx_rad_s', 'gx'), ('Gy_rad_s', 'gy'), ('Gz_rad_s', 'gz')]:
                            val = row.get(key_src)
                            if val is not None and val != '':
                                rec[key_dst] = float(val)
                                rec[key_src] = float(val)  # 保留原始列名，用于 source_type 检测
                        # 也兼容直接的 ax/ay/az 列名
                        for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz'):
                            if k not in rec and k in row and row[k] != '':
                                rec[k] = float(row[k])
                                rec['Ax_m_s2'] = rec.get('ax', 0)  # 兼容 source_type 检测
                        # speed / wheel
                        raw_speed = float(row.get('speed', row.get('车速_kmh', 0)))
                        rec['speed'] = raw_speed
                        rec['车速_kmh'] = raw_speed  # ← 关键：_on_imu_sensor_batch 读此字段
                        raw_wheel = float(row.get('wheel', row.get('方向盘转角_deg', 0)))
                        rec['wheel'] = raw_wheel
                        rec['方向盘转角_deg'] = raw_wheel  # ← 兼容回放路径
                        # channel / imu_name
                        channel = row.get('channel', row.get('ch', 'ch1'))
                        imu_name = row.get('imu_name', row.get('imu', channel))
                        rec['channel'] = channel
                        rec['imu_name'] = imu_name
                        rec['_imu_name'] = imu_name
                        records.append(rec)
            elif ext == '.txt':
                # 使用 IMU Parser 解析原始日志文件
                from core.core.data_processing.data_parser import IMUDataParser
                parser = IMUDataParser()
                with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    content = f.read()
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    packets = parser._parse_log_line(line)
                    for p in packets:
                        if isinstance(p, dict):
                            rec = {}
                            rec['rel_time'] = float(p.get('timestamp', 0))
                            rec['timestamp'] = rec['rel_time']
                            for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz', 'speed', 'wheel'):
                                if k in p:
                                    rec[k] = float(p[k])
                            rec['Ax_m_s2'] = rec.get('ax', 0)  # 兼容 source_type 检测
                            rec['车速_kmh'] = rec.get('speed', 0)  # 兼容回放路径
                            rec['方向盘转角_deg'] = rec.get('wheel', 0)
                            rec['channel'] = p.get('channel', 'ch1')
                            rec['imu_name'] = p.get('imu_name', rec['channel'])
                            rec['_imu_name'] = rec['imu_name']
                            records.append(rec)
            else:
                self.logger.warning(f"不支持的文件格式: {ext}")
                QMessageBox.warning(self, "不支持", f"暂不支持 {ext} 格式，请选择 CSV 或 TXT 文件")
                return

            if not records:
                self.logger.warning("文件解析结果为空")
                QMessageBox.warning(self, "解析失败", "文件中未找到有效数据记录")
                return

            self.logger.info(f"文件解析完成: {len(records)} 条记录, 文件={os.path.basename(file_path)}")

            # 2. 写入 MultiSourceCache
            from core.core.data_processing.multi_source_cache import MultiSourceCache
            if hasattr(self, '_multi_source_cache') and self._multi_source_cache:
                cache = self._multi_source_cache
                self.logger.info(f"复用已有缓存: {cache.db_path}")
            else:
                cache = MultiSourceCache()
                self._multi_source_cache = cache
                self.logger.info(f"创建新缓存: {cache.db_path}")

            batch_size = 5000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                cache.write_batch(batch)
            cache.flush()
            self.logger.info(f"已将 {len(records)} 条记录写入缓存: {cache.db_path}")

            # 3. 获取或创建 DataBridge
            data_bridge = getattr(self, 'data_bridge', None)
            if not data_bridge:
                from core.core.analysis.data_bridge import DataBridge
                data_bridge = DataBridge()
                self.data_bridge = data_bridge
                self.logger.info("DataBridge 已创建")

            # 4. 将 DataBridge 注入到右侧面板
            if hasattr(self, 'right_tab') and self.right_tab:
                if hasattr(self.right_tab, 'set_data_bridge'):
                    self.right_tab.set_data_bridge(data_bridge)
                    self.logger.info("DataBridge 已注入到右侧面板")
                if hasattr(self.right_tab, 'set_cache'):
                    self.right_tab.set_cache(cache)
                    self.logger.info("MultiSourceCache 已注入到右侧面板")

            # 5. 设置 DataBridge 缓存
            data_bridge.set_cache(cache)
            data_bridge.enable_result_caching()
            self.logger.info("DataBridge 缓存和分析缓存已就绪")

            # 6. 标记已完成，防止 _setup_cache_and_replay 重复创建
            self._replay_created = False
            self._cache_and_callback_setup_done = True

            # 7. 触发全部解析完成 → 创建回放控制器
            self._parsing_all_complete.emit(cache, data_bridge)

            # 8. 显示文件信息
            self.bottom_status.showMessage(f"已加载: {os.path.basename(file_path)} ({len(records)} 条记录)", 10000)
            QMessageBox.information(self, "加载完成", f"已加载 {len(records)} 条记录\n缓存: {os.path.basename(cache.db_path)}")

        except Exception as e:
            self.logger.error(f"文件加载失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            QMessageBox.critical(self, "加载失败", f"文件加载失败:\n{str(e)}")

    def _on_save_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, translations['en']['save_current_data'], "", "Data Files (*.csv *.json)")
        if file_path:
            self.logger.info(f"保存数据到: {file_path}")
            QMessageBox.information(self, translations['en']['save_successful'], f"{translations['en']['data_saved_to']} {file_path}")

    def _on_open_system_config(self):
        if self.config_manager is None:
            QMessageBox.warning(self, "警告", "配置管理器未初始化")
            return
        try:
            from config.config_manager import ConfigWidget
        except ImportError as e:
            QMessageBox.critical(self, "错误", f"无法加载配置组件: {e}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("系统配置")
        dialog.resize(820, 640)
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)
        config_widget = ConfigWidget(self.config_manager, parent=dialog)
        layout.addWidget(config_widget)
        self.logger.info("打开系统配置对话框")
        dialog.exec()

    def _set_language(self, lang):
        self.current_lang = lang
        self.logger.info(f"切换语言: {lang}")

    def _show_about_dialog(self):
        QMessageBox.about(self, translations['en']['about_core'], translations['en']['about_text'])

    def update_data(self):
        pass

    def update_time(self):
        pass

    def _check_data_update_health(self):
        pass

    def update_system_metrics_ui(self):
        pass

    def setup_system_monitoring(self):
        pass

    def setup_data_pipeline_monitoring(self):
        pass

    def apply_initial_styles(self):
        pass

    def on_data_source_changed(self, source_type, params):
        pass

    def on_load_file(self, file_path):
        pass

    def on_data_sources_selected(self, sources):
        pass

    def on_analysis_toggled(self, start, level):
        pass

    def on_record_toggled(self, start):
        pass

    def on_export_data(self):
        pass

    def on_source_added(self, source_info):
        pass

    def on_source_removed(self, source_id):
        pass

    def on_active_source_changed(self, source_id):
        pass

    def on_advanced_analysis_started(self, config):
        pass

    def on_advanced_analysis_stopped(self):
        pass

    def on_advanced_analysis_paused(self):
        pass

    def on_model_load_requested(self, model_info):
        pass

    def on_model_unload_requested(self, model_id):
        pass

    def _update_right_tab_data(self, data):
        pass

    def _update_monitoring_from_left_panel(self, data):
        pass

    def _on_data_flow_status_changed(self, status):
        pass

    def _on_data_pipeline_health_updated(self, health):
        pass

    def _on_module_data_received(self, data):
        pass

    def init_translations(self):
        try:
            pass
        except Exception as e:
            self.logger.warning(f"初始化多语言支持失败: {e}")

    def _import_core_modules(self):
        try:
            from core.core.service_locator import ServiceLocator
            self._service_locator = ServiceLocator()
            self.logger.info("ServiceLocator 已就绪，核心模块通过 locator.get() 按需获取")
        except Exception as e:
            self.logger.warning("ServiceLocator 初始化失败: %s", e)

    def _on_all_parsing_complete(self, cache, data_bridge):
        if hasattr(self, '_replay_created') and self._replay_created:
            self.logger.info("回放控制器已存在，更新回放条时间范围并触发全量事件重新生成")
            if hasattr(self, 'right_tab') and self.right_tab:
                # 确保 data_bridge 已注入
                if hasattr(self.right_tab, 'set_data_bridge'):
                    self.right_tab.set_data_bridge(data_bridge)
                    self.logger.info("DataBridge 已重新注入到右侧面板")
                    
                if hasattr(self.right_tab, 'replay_bar'):
                    t_min, t_max = cache.get_time_range()
                    self.right_tab.replay_bar.set_time_range(t_min, t_max)
                    self.right_tab.replay_bar.set_play_enabled(True)
                    all_source_types = cache.get_source_types()
                    self.right_tab.replay_bar.set_source_info(all_source_types)
                    if hasattr(self.right_tab, '_replay_controller'):
                        self.right_tab._replay_controller.refresh_available_source_types()
                    self.logger.info(f"回放条时间范围已更新: [{t_min:.1f}, {t_max:.1f}]，"
                                     f"数据源: {all_source_types}，等待用户手动播放")
                    
                    # 获取当前回放控制器用于全量事件重新生成
                    replay_ctrl = getattr(self.right_tab, '_replay_controller', None)
                    if replay_ctrl is None:
                        replay_ctrl = getattr(self, '_pending_replay_controller', None)
                    
                    # 调度全量事件重新生成（在主线程，QTimer 可用）
                    if hasattr(self, 'ui_components') and self.ui_components:
                        existing = replay_ctrl.get_events() if replay_ctrl else []
                        self.logger.info(
                            f"全量事件重新生成调度: 使用 DrivingEventDetector "
                            f"(当前已有 {len(existing) if existing else 0} 个事件)"
                        )
                        QTimer.singleShot(
                            2000,
                            lambda: self.ui_components._generate_events_from_cache(
                                cache, data_bridge, replay_ctrl
                            )
                        )
                    
                    # 不自动播放，等待用户手动点击播放按钮或开始数据源抽取
            return
        self._replay_created = True
        self.logger.info("所有数据源已耗尽，准备创建回放控制器...")
        self.ui_components._create_replay_controller(cache, data_bridge, enable_play=True)

    def closeEvent(self, event):
        self.logger.info("主窗口关闭事件触发，正在清理资源...")

        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())

        self._stop_all_timers()

        if hasattr(self, 'data_pipeline_manager') and self.data_pipeline_manager:
            try:
                self.data_pipeline_manager.shutdown()
            except Exception as e:
                self.logger.warning(f"数据管道管理器关闭失败: {e}")

        try:
            from core.core.service_locator import ServiceLocator
            controller = ServiceLocator().get('core_ui_controller')
            if controller and hasattr(controller, 'shutdown'):
                controller.shutdown()
        except Exception as e:
            self.logger.warning(f"控制器 shutdown 调用失败: {e}")

        if hasattr(self, '_multi_source_cache') and self._multi_source_cache:
            try:
                self._multi_source_cache.close()
                self._multi_source_cache._clear_db()
            except Exception as e:
                self.logger.warning(f"关闭 MultiSourceCache 失败: {e}")
            self._multi_source_cache = None

        self.logger.info("资源清理完成，允许窗口关闭")
        event.accept()

    def _stop_all_timers(self):
        timer_names = ['data_timer', 'time_timer', 'health_monitor_timer']
        for name in timer_names:
            timer = getattr(self, name, None)
            if timer and timer.isActive():
                timer.stop()
                self.logger.debug(f"定时器 {name} 已停止")

    def setup_exception_handling(self):
        import sys
        import traceback as tb_module

        _hook_active = [False]

        def exception_hook(exctype, value, tb):
            if _hook_active[0]:
                return
            _hook_active[0] = True
            try:
                try:
                    error_msg = f"未处理的异常:\n类型: {exctype.__name__}\n信息: {value}"
                except Exception:
                    error_msg = f"未处理的异常: {value}"
                try:
                    if hasattr(self, 'logger'):
                        self.logger.error(error_msg)
                        try:
                            tb_str = ''.join(tb_module.format_exception(exctype, value, tb))
                            self.logger.error(f"Traceback:\n{tb_str}")
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        self,
                        "系统错误",
                        f"{error_msg}\n\n请检查系统日志获取详细信息。"
                    )
                except Exception:
                    pass
            finally:
                _hook_active[0] = False

        sys.excepthook = exception_hook

    def set_theme(self, theme_name: str):
        try:
            if theme_name == "Light":
                self.setStyleSheet(get_light_theme_style())
            elif theme_name == "Dark":
                self.setStyleSheet(get_dark_theme_style())
            if hasattr(self, 'left_panel'):
                pass
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"设置主题失败: {e}")

    def set_language(self, lang: str):
        try:
            if lang in ['en', 'zh']:
                CoreUIMainWindow.current_lang = lang
                if hasattr(self, 'logger'):
                    self.logger.info(f"语言已切换到: {lang}")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"设置语言失败: {e}")

    def apply_initial_styles(self):
        try:
            self.setStyleSheet(get_light_theme_style())
            self.logger.info("初始样式已应用")
        except Exception as e:
            self.logger.error(f"应用初始样式失败: {e}")
