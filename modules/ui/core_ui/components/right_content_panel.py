#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧内容面板组件 - 核心UI系统
包含数据可视化、分析结果展示、实时监控等核心功能模块
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTabWidget, QTextEdit, QTableWidget,
                               QTableWidgetItem, QGroupBox, QFrame, QSplitter,
                               QProgressBar, QScrollArea, QGridLayout, QComboBox,
                               QApplication)
from PySide6.QtCore import Qt, Signal, QTimer, QEventLoop
from PySide6.QtGui import QFont, QPalette, QColor
import logging
import time

# 导入CNAP可视化组件（使用更专业的版本）
try:
    from modules.ui.monitoring_dashboard_components.tab_content_widgets.cnap_visualization_tab import CNAPVisualizationTab
    CNAP_VISUALIZATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 CNAPVisualizationTab: {e}")
    CNAP_VISUALIZATION_AVAILABLE = False

try:
    from modules.ui.monitoring_dashboard_components.tab_content_widgets.imu_visualization_tab import IMUVisualizationTab
    IMU_VISUALIZATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 IMUVisualizationTab: {e}")
    IMU_VISUALIZATION_AVAILABLE = False

try:
    from modules.ui.core_ui.components.can_full_parsing_tab import CANFullParsingTab
    CAN_FULL_TAB_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 CANFullParsingTab: {e}")
    CAN_FULL_TAB_AVAILABLE = False

# 导入座椅评测组件
try:
    from modules.ui.seat_evaluation.seat_evaluation_tab import SeatEvaluationTab
    SEAT_EVALUATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 SeatEvaluationTab: {e}")
    SEAT_EVALUATION_AVAILABLE = False

try:
    from modules.ui.seat_evaluation.comparative_evaluation_tab import ComparativeEvaluationTab
    COMPARATIVE_EVALUATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 ComparativeEvaluationTab: {e}")
    COMPARATIVE_EVALUATION_AVAILABLE = False

try:
    from modules.ui.seat_evaluation.metadata_management_tab import MetadataManagementTab
    METADATA_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入 MetadataManagementTab: {e}")
    METADATA_MANAGEMENT_AVAILABLE = False

class RightContentPanel(QWidget):
    """右侧内容面板 - 专业监控界面"""
    
    # 信号定义
    tab_changed = Signal(str)           # 标签页切换
    data_export_requested = Signal()    # 数据导出请求
    chart_interaction = Signal(dict)    # 图表交互
    
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self._data_bridge = None
        self._replay_controller = None
        self._cache = None
        self._cache_registry = None
        self._tab_initialized = {}
        self._replay_events = []
        self._replay_event_ids = set()

        # ── PipelineModeController ──
        from core.core.analysis.pipeline_mode_controller import PipelineModeController
        self._pipeline_controller = PipelineModeController(self)
        self._pipeline_controller.clear_ui_requested.connect(self._on_clear_all_ui)
        self._pipeline_controller.mode_changed.connect(self._on_pipeline_mode_changed)

        self._event_refresh_pending = False
        self._event_refresh_timer = QTimer(self)
        self._event_refresh_timer.timeout.connect(self._flush_event_refresh)
        self._event_refresh_timer.setInterval(500)
        self._event_refresh_timer.setSingleShot(True)
        self._imu_viz_queue = []
        self._imu_viz_idx = 0

        self._init_ui()
        self._apply_professional_style()
        self.logger.info("✅ 右侧内容面板已初始化")
        
    def _init_ui(self):
        """初始化UI布局（全部延迟加载）"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        from modules.ui.core_ui.components.replay_control_bar import ReplayControlBar
        self.replay_bar = ReplayControlBar()
        main_layout.addWidget(self.replay_bar)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # 前5个标签页使用占位符，首次切换时再创建（依赖外部data_bridge/replay_controller等）
        tab_configs = [
            ("CNAP可视化", "cnap", CNAP_VISUALIZATION_AVAILABLE),
            ("IMU可视化", "imu", IMU_VISUALIZATION_AVAILABLE),
            ("CAN全量解析", "can_full", CAN_FULL_TAB_AVAILABLE),
            ("实时行为监控", "real_time", True),
            ("座椅评测", "seat_evaluation", SEAT_EVALUATION_AVAILABLE),
        ]
        for title, key, available in tab_configs:
            ph = QWidget()
            lay = QVBoxLayout(ph)
            if available:
                lbl = QLabel(f"⏳ {title} 模块将在首次切换到此标签页时加载")
            else:
                lbl = QLabel(f"❌ {title} 模块不可用")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888; font-size: 14px;")
            lay.addWidget(lbl)
            self.tab_widget.addTab(ph, title)
        
        # 元数据管理标签页直接加载（无外部依赖，避免延迟加载的索引竞争问题）
        QApplication.processEvents()
        if METADATA_MANAGEMENT_AVAILABLE:
            try:
                self.metadata_management_tab = MetadataManagementTab(self.config_manager)
                QApplication.processEvents()
                self.tab_widget.addTab(self.metadata_management_tab, "元数据管理")
                self._tab_initialized[5] = True
                self.logger.info("元数据管理标签页已直接创建")
            except Exception as e:
                self.logger.error(f"直接创建元数据管理标签页失败: {e}")
                ph = QWidget()
                lay = QVBoxLayout(ph)
                lbl = QLabel("元数据管理模块不可用")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #6c757d; font-size: 14px;")
                lay.addWidget(lbl)
                self.tab_widget.addTab(ph, "元数据管理")
        else:
            ph = QWidget()
            lay = QVBoxLayout(ph)
            lbl = QLabel("元数据管理模块不可用")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #6c757d; font-size: 14px;")
            lay.addWidget(lbl)
            self.tab_widget.addTab(ph, "元数据管理")
        
        main_layout.addWidget(self.tab_widget)
        
        # 诊断：打印所有标签页名称
        tab_names = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        self.logger.info(f"标签页初始化完成: 共 {self.tab_widget.count()} 个 -> {tab_names}")
    
    def _replace_placeholder_tab(self, position: int, widget: QWidget, tab_name: str):
        """按名称精确替换占位符标签页，避免索引偏移导致误删"""
        self.tab_widget.insertTab(position, widget, tab_name)
        for i in range(self.tab_widget.count() - 1, -1, -1):
            if i != position and self.tab_widget.tabText(i) == tab_name:
                self.tab_widget.removeTab(i)
                return
        self.logger.warning(f"_replace_placeholder_tab: 未找到占位符 '{tab_name}' (position={position})")
    
    def addTab(self, widget, label):
        """添加标签页（用于与外部组件兼容）"""
        try:
            self.tab_widget.addTab(widget, label)
        except Exception as e:
            self.logger.error(f"添加标签页失败: {e}")
    
        
    def _create_cnap_visualization_tab(self):
        """创建CNAP可视化标签页"""
        QApplication.processEvents()
        if CNAP_VISUALIZATION_AVAILABLE:
            try:
                self.cnap_visualization_tab = CNAPVisualizationTab()
                QApplication.processEvents()
                self._replace_placeholder_tab(0, self.cnap_visualization_tab, "CNAP可视化")
                if self._data_bridge:
                    self.cnap_visualization_tab.set_data_bridge(self._data_bridge)
                    self.cnap_visualization_tab.start()
                    try:
                        self._data_bridge.sensor_data_batch_received.connect(self._on_cnap_sensor_batch)
                        self.logger.info("CNAP sensor_data_batch_received 信号已连接")
                    except Exception as e:
                        self.logger.warning(f"连接CNAP batch信号失败: {e}")
                self.logger.info("✅ CNAP可视化标签页已添加")
                return
            except Exception as e:
                self.logger.error(f"创建CNAP可视化标签页失败: {e}")
        
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        info_label = QLabel("CNAP可视化模块不可用")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(info_label)
        self._replace_placeholder_tab(0, tab_widget, "CNAP可视化")

    def _create_imu_visualization_tab(self):
        QApplication.processEvents()
        if IMU_VISUALIZATION_AVAILABLE:
            try:
                self.imu_visualization_tab = IMUVisualizationTab()
                QApplication.processEvents()
                self._replace_placeholder_tab(1, self.imu_visualization_tab, "IMU可视化")
                if self._data_bridge:
                    self.imu_visualization_tab.set_data_bridge(self._data_bridge)
                    self.imu_visualization_tab.start()
                    try:
                        self._data_bridge.sensor_data_batch_received.connect(self._on_imu_sensor_batch)
                        self.logger.info("IMU sensor_data_batch_received 信号已连接")
                    except Exception as e:
                        self.logger.warning(f"连接IMU batch信号失败: {e}")
                self.logger.info("IMU可视化标签页已添加")
                return
            except Exception as e:
                self.logger.error(f"创建IMU可视化标签页失败: {e}")

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        info_label = QLabel("IMU可视化模块不可用")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(info_label)
        self._replace_placeholder_tab(1, tab_widget, "IMU可视化")
        
    def _create_can_full_tab(self):
        QApplication.processEvents()
        if CAN_FULL_TAB_AVAILABLE:
            try:
                self.can_full_tab = CANFullParsingTab()
                QApplication.processEvents()
                self._replace_placeholder_tab(2, self.can_full_tab, "CAN全量解析")
                if self._data_bridge:
                    self.can_full_tab.set_data_bridge(self._data_bridge)
                cache_to_inject = self._cache
                if not cache_to_inject:
                    try:
                        app = QApplication.instance()
                        main_win = None
                        for widget in app.topLevelWidgets():
                            if widget.__class__.__name__ == 'CoreUIMainWindow':
                                main_win = widget
                                break
                        if main_win and hasattr(main_win, '_multi_source_cache'):
                            cache_to_inject = main_win._multi_source_cache
                    except Exception:
                        pass
                if cache_to_inject and hasattr(self.can_full_tab, 'set_cache'):
                    self.can_full_tab.set_cache(cache_to_inject)
                    self.logger.info("缓存已注入到延迟创建的CAN全量解析标签页")
                self.logger.info("CAN全量解析标签页已添加")
                return
            except Exception as e:
                self.logger.error(f"创建CAN全量解析标签页失败: {e}")

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        info_label = QLabel("CAN全量解析模块不可用")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(info_label)
        self._replace_placeholder_tab(2, tab_widget, "CAN全量解析")

    def _create_real_time_monitoring_tab(self):
        """创建实时监控标签页"""
        try:
            self.logger.info("开始创建实时监控标签页")
            QApplication.processEvents()
            
            from modules.ui.real_time_monitoring_tab import RealTimeMonitoringTab
            self.logger.info("成功导入 RealTimeMonitoringTab 类")
            
            self._initialize_monitoring_widgets()
            QApplication.processEvents()
            
            self.real_time_monitoring_tab = RealTimeMonitoringTab(self.config_manager)
            QApplication.processEvents()
            self.real_time_monitoring_tab.ensure_all_views_initialized()
            self._replace_placeholder_tab(3, self.real_time_monitoring_tab, "实时行为监控")
            self.logger.info("成功创建实时行为监控标签页")

            try:
                from core.core.service_locator import ServiceLocator
                ServiceLocator().register('real_time_monitoring_tab', self.real_time_monitoring_tab)
            except Exception:
                pass
            
            self.logger.info("成功创建实时行为监控标签页（依赖注入由调用方负责）")
            
            # 连接事件联动信号：实时行为监控 -> CAN全量解析
            self._connect_event_linkage()
            
        except ImportError as e:
            self.logger.error(f"无法导入实时监控标签页: {e}", exc_info=True)
            self._create_fallback_monitoring_tab()
        except Exception as e:
            self.logger.error(f"创建实时监控标签页时发生未知错误: {e}", exc_info=True)
            self._create_fallback_monitoring_tab()

    def set_data_bridge(self, data_bridge):
        """注入DataBridge到各个标签页"""
        self._data_bridge = data_bridge  # 保存引用

        # ── 注入到 PipelineModeController ──
        self._pipeline_controller.set_data_bridge(data_bridge)

        # 确保实时行为监控标签页已创建（实时流式处理时需要接收帧结果和事件）
        if not hasattr(self, 'real_time_monitoring_tab') or not self.real_time_monitoring_tab:
            self._create_real_time_monitoring_tab()
            self._tab_initialized[3] = True
            self.logger.info("实时行为监控标签页已提前创建（实时流式处理模式）")
        
        # 注入到实时监控标签页
        if hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
            try:
                self.real_time_monitoring_tab.set_data_bridge(data_bridge)
                self.logger.info("DataBridge 已注入到实时监控标签页")
            except Exception as e:
                self.logger.error(f"注入 DataBridge 到 real_time_monitoring_tab 失败: {e}")

        # 确保 IMU 可视化标签页已创建（流式处理时需要接收 sensor_data_batch_received 信号来启动管线）
        if not hasattr(self, 'imu_visualization_tab') or not self.imu_visualization_tab:
            self._create_imu_visualization_tab()
            self._tab_initialized[1] = True
            self.logger.info("IMU可视化标签页已提前创建（流式处理模式）")

        # 注入到 IMU 可视化标签页并连接信号
        if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
            try:
                self.imu_visualization_tab.set_data_bridge(data_bridge)
                self.imu_visualization_tab.start()
                data_bridge.sensor_data_batch_received.connect(self._on_imu_sensor_batch)
                self.logger.info("DataBridge 已注入到 IMU 可视化标签页，信号已连接")
            except Exception as e:
                self.logger.error(f"注入 DataBridge 到 IMU 可视化失败: {e}")

        # 注入到 CNAP 可视化标签页
        if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
            try:
                self.cnap_visualization_tab.set_data_bridge(data_bridge)
                self.cnap_visualization_tab.start()
                data_bridge.sensor_data_batch_received.connect(self._on_cnap_sensor_batch)
                self.logger.info("DataBridge 已注入到 CNAP 可视化标签页")
            except Exception as e:
                self.logger.error(f"注入 DataBridge 到 CNAP 可视化失败: {e}")

        if hasattr(self, 'can_full_tab') and self.can_full_tab:
            try:
                self.can_full_tab.set_data_bridge(data_bridge)
                self.logger.info("DataBridge 已注入到 CAN全量解析标签页")
            except Exception as e:
                self.logger.error(f"注入 DataBridge 到 CAN全量解析失败: {e}")
        
        # 注入到座椅评测标签页（已整合对照分析功能）
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            try:
                self.seat_evaluation_tab.set_data_bridge(data_bridge)
                self.logger.info("DataBridge 已注入到座椅评测标签页")
            except Exception as e:
                self.logger.error(f"注入 DataBridge 到座椅评测标签页失败: {e}")
        
        # 连接 DataBridge 行为事件信号到事件面板
        if hasattr(data_bridge, 'behavior_event_ready'):
            try:
                data_bridge.behavior_event_ready.connect(self._on_data_bridge_behavior_event)
                self.logger.info("DataBridge.behavior_event_ready 已连接到事件面板")
            except Exception as e:
                self.logger.error(f"连接 DataBridge 行为事件信号失败: {e}")
        
        # ── STREAMING 模式: 座椅评测增量触发 ──
        if hasattr(data_bridge, 'behavior_event_ready'):
            try:
                data_bridge.behavior_event_ready.connect(self._on_seat_evaluation_incremental)
                self.logger.info("座椅评测增量模式已连接 behavior_event_ready")
            except Exception as e:
                self.logger.debug(f"连接座椅评测增量信号失败: {e}")
        
        # 尝试连接事件联动
        QTimer.singleShot(200, self._connect_event_linkage)

    def set_cache(self, cache):
        self._cache = cache
        if hasattr(self, 'can_full_tab') and self.can_full_tab:
            if hasattr(self.can_full_tab, 'set_cache'):
                self.can_full_tab.set_cache(cache)
                self.logger.info("MultiSourceCache 已注入到CAN全量解析标签页(提前)")
        if hasattr(self, '_data_bridge') and self._data_bridge:
            if hasattr(self._data_bridge, 'set_cache'):
                self._data_bridge.set_cache(cache)
                self.logger.info("MultiSourceCache 已注入到DataBridge")
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            if hasattr(self.seat_evaluation_tab, '_data_bridge'):
                self.seat_evaluation_tab._data_bridge = self._data_bridge

    def set_seat_evaluation_engine(self, engine):
        """注入座椅评测引擎到座椅评测标签页"""
        self._seat_evaluation_engine = engine
        if not hasattr(self, 'seat_evaluation_tab') or not self.seat_evaluation_tab:
            self._create_seat_evaluation_tab()
            self._tab_initialized[4] = True
            self.logger.info("座椅评测标签页已提前创建（引擎注入触发）")
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            self.seat_evaluation_tab.set_evaluation_engine(engine)
            self.logger.info("座椅评测引擎已注入到座椅评测标签页")

    def set_comparative_engine(self, engine):
        """注入对照分析引擎到座椅评测标签页"""
        self._comparative_engine = engine
        if not hasattr(self, 'seat_evaluation_tab') or not self.seat_evaluation_tab:
            self._create_seat_evaluation_tab()
            self._tab_initialized[4] = True
            self.logger.info("座椅评测标签页已提前创建（对照引擎注入触发）")
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            if hasattr(self.seat_evaluation_tab, 'set_comparative_engine'):
                self.seat_evaluation_tab.set_comparative_engine(engine)
                self.logger.info("对照分析引擎已注入到座椅评测标签页")

    def set_replay_controller(self, replay_controller):
        """注入回放控制器，替代 DataBridge 的 UI 信号"""
        if getattr(self, '_replay_controller_injecting', False):
            self.logger.warning("set_replay_controller 重入被阻止")
            return
        if hasattr(self, '_replay_controller') and self._replay_controller is not None:
            self.logger.info("回放控制器已注入，跳过重复注入")
            return
        self._replay_controller_injecting = True
        try:
            self._set_replay_controller_impl(replay_controller)
        finally:
            self._replay_controller_injecting = False

    def _set_replay_controller_impl(self, replay_controller):
        self._replay_controller = replay_controller
        self._replay_fast_switch_attempted = False
        self._replay_events = []
        self._replay_event_ids = set()

        if not hasattr(self, 'imu_visualization_tab') or not self.imu_visualization_tab:
            self._create_imu_visualization_tab()
            self._tab_initialized[1] = True
            self.logger.info("IMU可视化标签页已提前创建（回放模式）")

        if not hasattr(self, 'cnap_visualization_tab') or not self.cnap_visualization_tab:
            self._create_cnap_visualization_tab()
            self._tab_initialized[0] = True
            self.logger.info("CNAP可视化标签页已提前创建（回放模式）")

        if not hasattr(self, 'can_full_tab') or not self.can_full_tab:
            self._create_can_full_tab()
            self._tab_initialized[2] = True
            self.logger.info("CAN全量解析标签页已提前创建（回放模式）")

        if not hasattr(self, 'real_time_monitoring_tab') or not self.real_time_monitoring_tab:
            self._create_real_time_monitoring_tab()
            self._tab_initialized[3] = True
            self.logger.info("实时行为监控标签页已提前创建（回放模式）")
        
        # 确保所有已创建的标签页都接收到 data_bridge
        if self._data_bridge:
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                self.imu_visualization_tab.set_data_bridge(self._data_bridge)
                self.logger.info("已为 IMU 可视化注入 DataBridge")
            if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                self.cnap_visualization_tab.set_data_bridge(self._data_bridge)
                self.logger.info("已为 CNAP 可视化注入 DataBridge")

        if self._data_bridge and hasattr(self, 'can_full_tab') and self.can_full_tab:
            try:
                self._data_bridge.sensor_data_batch_received.disconnect(self.can_full_tab._on_batch_received)
            except Exception:
                pass

        if hasattr(self, 'can_full_tab') and self.can_full_tab:
            if self._cache:
                if hasattr(self.can_full_tab, 'set_cache'):
                    self.can_full_tab.set_cache(self._cache)
                    self.logger.info("MultiSourceCache 已注入到CAN全量解析标签页")

        replay_controller.replay_progress.connect(self.replay_bar.update_progress)
        replay_controller.replay_state_changed.connect(self._on_replay_state_changed)
        replay_controller.replay_mode_changed.connect(self.replay_bar.set_replay_mode)
        replay_controller.playback_range_changed.connect(self._on_playback_range_changed)

        self.replay_bar.play_clicked.connect(replay_controller.play)
        self.replay_bar.pause_clicked.connect(replay_controller.pause)
        self.replay_bar.stop_clicked.connect(replay_controller.stop)
        self.replay_bar.seek_forward_clicked.connect(lambda: replay_controller.seek(replay_controller.cursor + 5))
        self.replay_bar.seek_backward_clicked.connect(lambda: replay_controller.seek(replay_controller.cursor - 5))
        self.replay_bar.speed_changed.connect(replay_controller.set_speed)
        self.replay_bar.progress_seek.connect(replay_controller.seek)
        self.replay_bar.source_selection_changed.connect(replay_controller.set_active_sources)
        self.replay_bar.replay_mode_changed.connect(replay_controller.set_replay_mode)
        
        # ── 缓存选择器 ──
        self.replay_bar.cache_selection_changed.connect(self._on_cache_selection_changed)
        
        # ── 填充缓存列表 ──
        if self._cache_registry:
            try:
                caches = self._cache_registry.list_caches()
                self.replay_bar.set_cache_list(caches)
                self.logger.info(f"缓存选择器已填充: {len(caches)} 个缓存")
            except Exception as e:
                self.logger.warning(f"填充缓存选择器失败: {e}")

        # ── 注入到 PipelineModeController ──
        self._pipeline_controller.set_replay_controller(replay_controller)

        self.replay_bar.time_range_changed.connect(replay_controller.set_playback_range)
        self.replay_bar.event_jump_requested.connect(self._on_event_jump_requested)

        events = replay_controller.get_events()
        self._replay_events = []
        self._replay_event_ids = set()
        if events:
            from core.core.analysis.event_distributor import EventDistributor
            distributor = EventDistributor.instance()
            for event in events:
                eid = getattr(event, 'id', '') or getattr(event, 'event_id', '')
                if eid and eid not in self._replay_event_ids:
                    self._replay_event_ids.add(eid)
                    self._replay_events.append(event)
                    distributor.register_event(event)
            self._sync_replay_bar_events()
            self.logger.info(f"已加载 {len(self._replay_events)} 个事件到回放栏事件跳转列表")
        else:
            self.logger.info("回放栏事件跳转列表为空（分析缓存中暂无事件，将在回放过程中动态更新）")

        # 连接信号（快速回放模式）
        # 连接信号 - 实时行为监控
        if hasattr(replay_controller, 'frame_result_ready'):
            replay_controller.frame_result_ready.connect(self._on_replay_frame_result)
        if hasattr(replay_controller, 'realtime_monitor_data'):
            replay_controller.realtime_monitor_data.connect(self._on_replay_realtime_data)
        if hasattr(replay_controller, 'behavior_event_ready'):
            replay_controller.behavior_event_ready.connect(self._on_replay_behavior_event)
        
        # 连接信号 - IMU可视化
        if hasattr(replay_controller, 'imu_data_batch_received'):
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                replay_controller.imu_data_batch_received.connect(self._on_imu_sensor_batch)
                if hasattr(self.imu_visualization_tab, 'set_replay_mode'):
                    self.imu_visualization_tab.set_replay_mode(True)
                self.logger.info("回放控制器 IMU 数据信号已连接")
        
        # 连接信号 - CAN全量解析
        if hasattr(replay_controller, 'can_raw_data_batch_received'):
            if hasattr(self, 'can_full_tab') and self.can_full_tab:
                # ── 使用 DataSourceMode 切换，不再直接连接信号 ──
                if hasattr(self.can_full_tab, 'set_replay_controller_ref'):
                    self.can_full_tab.set_replay_controller_ref(replay_controller)
                if hasattr(self.can_full_tab, 'set_data_source_mode'):
                    from modules.ui.core_ui.components.can_full_parsing_tab import DataSourceMode
                    self.can_full_tab.set_data_source_mode(DataSourceMode.REPLAY)
                if hasattr(self.can_full_tab, 'set_replay_mode'):
                    self.can_full_tab.set_replay_mode(True)
                self.logger.info("回放控制器 CAN 数据信号已连接")
        
        # 连接信号 - CNAP可视化
        if hasattr(replay_controller, 'cnap_data_batch_received'):
            if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                replay_controller.cnap_data_batch_received.connect(self._on_cnap_sensor_batch)
                self.logger.info("回放控制器 CNAP 数据信号已连接")
        
        # 连接回放控制器到实时行为监控
        if hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
            if hasattr(self.real_time_monitoring_tab, 'set_replay_controller'):
                self.real_time_monitoring_tab.set_replay_controller(replay_controller)
            if hasattr(self.real_time_monitoring_tab, 'set_replay_mode'):
                self.real_time_monitoring_tab.set_replay_mode(True)
            self.logger.info("回放控制器已连接到实时行为监控")

        # 确保座椅评测标签页已创建并接收引擎
        if not hasattr(self, 'seat_evaluation_tab') or not self.seat_evaluation_tab:
            self._create_seat_evaluation_tab()
            self._tab_initialized[4] = True
            self.logger.info("座椅评测标签页已提前创建（回放模式）")

        # 确保实时行为监控标签页已创建（回放时需要接收帧结果和事件）
        if not hasattr(self, 'real_time_monitoring_tab') or not self.real_time_monitoring_tab:
            self._create_real_time_monitoring_tab()
            self._tab_initialized[3] = True
            self._inject_dependencies_to_tab('real_time')
            self.logger.info("实时行为监控标签页已提前创建（回放模式）")
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            if hasattr(self, '_seat_evaluation_engine') and self._seat_evaluation_engine:
                self.seat_evaluation_tab.set_evaluation_engine(self._seat_evaluation_engine)
            if hasattr(self, '_comparative_engine') and self._comparative_engine:
                if hasattr(self.seat_evaluation_tab, 'set_comparative_engine'):
                    self.seat_evaluation_tab.set_comparative_engine(self._comparative_engine)
            if self._data_bridge:
                self.seat_evaluation_tab.set_data_bridge(self._data_bridge)
                self._data_bridge.seat_evaluation_triggered.connect(
                    self.seat_evaluation_tab._on_evaluation_triggered
                )
                self.logger.info("DataBridge.seat_evaluation_triggered 已连接到座椅评测标签页")

        # 将历史缓存注入评测队列，确保评测时能查询多通道数据
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            replay_cache = getattr(replay_controller, '_cache', None)
            if replay_cache and hasattr(self.seat_evaluation_tab, 'set_data_cache'):
                self.seat_evaluation_tab.set_data_cache(replay_cache)
                self.logger.info("回放历史缓存已注入到评测队列")

        # 连接回放控制器到对照分析面板（数据源动态化）
        if hasattr(self, 'comparative_evaluation_tab') and self.comparative_evaluation_tab:
            if hasattr(self.comparative_evaluation_tab, 'set_replay_controller'):
                self.comparative_evaluation_tab.set_replay_controller(replay_controller)
                self.logger.info("回放控制器已连接到对照分析面板")

        t_min, t_max = replay_controller.time_range
        self.replay_bar.set_time_range(t_min, t_max)
        self.replay_bar.show_bar()

        source_types = replay_controller.get_available_source_types()
        self.replay_bar.set_source_info(source_types)
        self.replay_bar.set_status('就绪 - 点击播放开始回放')

        self.logger.info("MultiSourceReplayController 已注入到右侧面板")
        
        # 诊断：验证元数据管理标签页是否仍存在
        tab_names = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        self.logger.info(f"回放模式注入后: 共 {self.tab_widget.count()} 个标签页 -> {tab_names}")
        if "元数据管理" not in tab_names:
            self.logger.error("⚠️ 元数据管理标签页在回放模式注入后丢失！")

    def _on_replay_state_changed(self, state):
        self.logger.debug(f"[DEBUG] _on_replay_state_changed 被调用: state={state}, _data_bridge={'存在' if self._data_bridge else 'None'}")
        is_fast = (hasattr(self, '_replay_controller') and self._replay_controller
                   and getattr(self._replay_controller, 'is_fast_mode', False))
        if state == 'playing':
            self.replay_bar.set_playing(True)
            self.replay_bar.set_status('回放中...')
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                self.imu_visualization_tab.start()
            if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                self.cnap_visualization_tab.start()

            # SQLite 直读：一次性加载全部 IMU 数据（替代逐条 receive_imu_data）
            # 快速回放和非快速回放都需要加载IMU可视化数据
            cache = getattr(self._replay_controller, '_cache', None) if self._replay_controller else None
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                if cache:
                    self.logger.info(f"IMU可视化: 从缓存加载数据 (is_fast={is_fast})")
                    self.imu_visualization_tab.load_from_cache(cache)

            if self._data_bridge and not is_fast:
                try:
                    if not self._data_bridge.is_running:
                        self._data_bridge.start_processing()
                        self.logger.info("回放开始，自动启动 data_bridge 分析管线（重算模式）")

                    # 批量分析：将全部记录喂入完整 SpeedPreprocessor + DrivingEventDetector 管线
                    if cache and not self._data_bridge.is_batch_analyzed:
                        try:
                            t_min, t_max = cache.get_time_range()
                            all_records = cache.query_records_raw(
                                t_min, t_max, self._replay_controller._active_sources
                            )
                            if all_records:
                                self.logger.info(
                                    f"批量分析开始: {len(all_records)} 条记录, "
                                    f"时间范围 [{t_min:.2f}s, {t_max:.2f}s]"
                                )
                                result = self._data_bridge.analyze_records_batch(all_records)
                                ev_count = len(result.get('events', []))
                                self.logger.info(
                                    f"批量分析完成: {ev_count} 个事件, "
                                    f"accel_range={result.get('vehicle_accel_range')}"
                                )
                                # 注册 raw_events 到 EventDistributor 统一管理
                                raw_events = result.get('raw_events', [])
                                if raw_events:
                                    from core.core.analysis.event_distributor import EventDistributor
                                    EventDistributor.instance().register_events(raw_events)
                                # 统一从 EventDistributor 同步到回放栏
                                self._sync_replay_bar_events()
                            else:
                                self.logger.warning("批量分析：缓存中无记录")
                        except Exception as e:
                            self.logger.error(f"批量分析失败: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"自动启动 data_bridge 失败: {e}")
            elif is_fast:
                self.logger.info("快速回放模式，跳过DataBridge启动（使用SQLite缓存）")
        elif state == 'paused':
            self.replay_bar.set_playing(False)
            self.replay_bar.set_status('已暂停')
        elif state == 'stopped':
            self.replay_bar.set_playing(False)
            self.replay_bar.set_status('已停止')
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                self.imu_visualization_tab.stop()
            if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                self.cnap_visualization_tab.stop()
            # 不停止 DataBridge：新数据源可能仍在加载，或即将加载
        elif state == 'finished':
            self.replay_bar.set_playing(False)
            self.replay_bar.set_status('回放完成')
            if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                self.imu_visualization_tab.stop()
            if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                self.cnap_visualization_tab.stop()
            # 快速回放因数据未全加载而提前结束 → 强制触发全量事件重新生成
            rc = self._replay_controller
            is_fast = getattr(rc, 'is_fast_mode', False) if rc else False
            self.logger.info(
                f"回放完成: replay_controller={rc is not None}, is_fast={is_fast}, "
                f"has_cache={getattr(rc, '_cache', None) is not None if rc else False}"
            )
            if rc and is_fast:
                cache = getattr(rc, '_cache', None)
                existing = rc.get_events() if hasattr(rc, 'get_events') else []
                self.logger.info(f"快速回放结束诊断: cache={cache is not None}, existing_events={len(existing)}")
                if cache:
                    # 清除部分分析产生的旧事件，确保全量结果不被去重跳过
                    rc_analysis_cache = getattr(rc, '_analysis_cache', None)
                    if rc_analysis_cache and hasattr(rc_analysis_cache, '_clear_events'):
                        rc_analysis_cache._clear_events()
                        self.logger.info("已清空分析缓存旧事件，准备全量重新生成")
                    from core.core.analysis.event_distributor import EventDistributor
                    EventDistributor.instance().clear()
                    self.logger.info("已清空 EventDistributor，准备全量重新生成")
                    
                    all_records = cache.query_records_raw(*cache.get_time_range(), rc._active_sources)
                    if all_records and self._data_bridge:
                        self.logger.info(
                            f"回放结束，触发全量事件重新生成: {len(all_records)} 条记录 "
                            f"(快速回放仅 {len(existing)} 个事件)"
                        )
                        try:
                            result = self._data_bridge.analyze_records_batch(all_records)
                            self.logger.info(
                                f"全量事件生成完成: {len(result.get('events', []))} 个事件, "
                                f"accel_range={result.get('vehicle_accel_range')}"
                            )
                        except Exception as e:
                            self.logger.error(f"全量事件生成失败: {e}", exc_info=True)
                else:
                    self.logger.warning("快速回放结束但 cache 为 None，无法触发全量重新分析")
            # ── 座椅评测批量触发 (REANALYZE 模式) ──
            elif rc and not is_fast:
                self.logger.info("重新分析回放完成，触发全量座椅评测...")
                if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                    try:
                        self.seat_evaluation_tab.set_evaluation_mode('batch')
                        self.seat_evaluation_tab.evaluate_batch_all()
                        self.logger.info("座椅评测全量批量完成")
                    except Exception as e:
                        self.logger.error(f"座椅评测批量执行失败: {e}")
            if self._data_bridge and self._data_bridge.is_running:
                self._data_bridge.stop_processing()

            # ── IMU波形通道：回放完成，高亮事件区间 ──
            if rc and hasattr(rc, '_playback_start') and hasattr(rc, '_playback_end'):
                pb_start = rc._playback_start
                pb_end = rc._playback_end
                if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                    tab = self.imu_visualization_tab
                    # 主波形通道
                    for ch in [tab.channel_accel, tab.channel_gyro,
                               tab.channel_vehicle, tab.channel_wheel]:
                        ch.set_event_range(pb_start, pb_end)
                    # 趋势通道（每参数独立一行）
                    for attr in ['trend_channel_ax', 'trend_channel_ay', 'trend_channel_az',
                                 'trend_channel_speed', 'trend_channel_wheel',
                                 'trend_channel_gx', 'trend_channel_gy', 'trend_channel_gz']:
                        ch = getattr(tab, attr, None)
                        if ch:
                            ch.set_event_range(pb_start, pb_end)
                    self.logger.info(f"IMU波形通道已高亮事件区间: [{pb_start:.1f}s, {pb_end:.1f}s]")

    def _on_playback_range_changed(self, start_time: float, end_time: float):
        """回放区间变更时，同步高亮CAN全量解析的事件区间，并更新回放控制栏时间"""
        try:
            if hasattr(self, 'can_full_tab') and self.can_full_tab:
                if hasattr(self.can_full_tab, 'highlight_event_time_range'):
                    self.can_full_tab.highlight_event_time_range(0, start_time, end_time)
                    self.logger.info(f"CAN全量解析已高亮回放区间: [{start_time:.1f}s, {end_time:.1f}s]")
        except Exception as e:
            self.logger.error(f"同步回放区间到CAN全量解析失败: {e}")

        if hasattr(self, 'replay_bar') and self.replay_bar:
            try:
                self.replay_bar.update_time_range_display(start_time, end_time)
            except Exception as e:
                self.logger.error(f"同步回放区间到回放控制栏失败: {e}")

        # IMU 可视化视图跟随事件跳转
        if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
            try:
                if hasattr(self.imu_visualization_tab, 'seek_to_time'):
                    self.imu_visualization_tab.seek_to_time(start_time)
                    self.logger.info(f"IMU可视化已跳转到: {start_time:.1f}s")
            except Exception as e:
                self.logger.error(f"IMU可视化视图跳转失败: {e}")

        # ── IMU波形通道：同步事件高亮区间 ──
        if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
            try:
                for ch in [self.imu_visualization_tab.channel_accel,
                           self.imu_visualization_tab.channel_gyro,
                           self.imu_visualization_tab.channel_vehicle,
                           self.imu_visualization_tab.channel_wheel]:
                    ch.set_event_range(start_time, end_time)
                # 趋势通道同步
                for attr in ['trend_channel_ax', 'trend_channel_ay', 'trend_channel_az',
                             'trend_channel_speed', 'trend_channel_wheel',
                             'trend_channel_gx', 'trend_channel_gy', 'trend_channel_gz']:
                    ch = getattr(self.imu_visualization_tab, attr, None)
                    if ch:
                        ch.set_event_range(start_time, end_time)
            except Exception as e:
                self.logger.error(f"IMU波形通道事件区间同步失败: {e}")

    def _flush_event_refresh(self):
        """防抖刷新：合并500ms内多次刷新请求为一次"""
        self._event_refresh_pending = False
        try:
            if hasattr(self, 'can_full_tab') and self.can_full_tab:
                if hasattr(self.can_full_tab, '_update_event_stats'):
                    self.can_full_tab._update_event_stats()
                if hasattr(self.can_full_tab, 'behavior_timeline') and self.can_full_tab.behavior_timeline:
                    self.can_full_tab.behavior_timeline._refresh_event_list()

            if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                if hasattr(self.seat_evaluation_tab, 'refresh_events'):
                    self.seat_evaluation_tab.refresh_events()
        except Exception as e:
            self.logger.error(f"防抖刷新失败: {e}")

    def _request_event_refresh(self):
        """请求事件刷新（带防抖）"""
        if not self._event_refresh_pending:
            self._event_refresh_pending = True
            self._event_refresh_timer.start()

    def _on_replay_frame_result(self, frame_result):
        """快速回放模式：接收 FrameResult 并更新 UI"""
        try:
            if not hasattr(self, '_fr_count'):
                self._fr_count = 0
            self._fr_count += 1
            
            # 在快速回放模式下，事件应该已经通过 sync_from_cache 同步了，不需要再次注册
            # 如果是快速回放模式，只刷新 UI 而不注册事件
            is_fast = False
            if hasattr(self, '_replay_controller') and self._replay_controller:
                is_fast = getattr(self._replay_controller, 'is_fast_mode', False)
            
            if frame_result and frame_result.event and not is_fast:
                from core.core.analysis.event_distributor import EventDistributor
                EventDistributor.instance().register_event(frame_result.event)
                self._request_event_refresh()
            
            fr_skip = getattr(self, '_fr_skip_counter', 0) + 1
            self._fr_skip_counter = fr_skip
            if fr_skip < 3:
                return
            self._fr_skip_counter = 0
            
            if self._fr_count <= 3 or self._fr_count % 100 == 0:
                has_event = bool(frame_result and frame_result.event)
                has_risk = bool(frame_result and frame_result.risk)
                self.logger.debug(
                    f"[回放FR] #{self._fr_count} ts={frame_result.timestamp:.2f} "
                    f"has_event={has_event} has_risk={has_risk}"
                )

            if hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
                if hasattr(self.real_time_monitoring_tab, 'process_frame_result'):
                    self.real_time_monitoring_tab.process_frame_result(frame_result)
        except Exception as e:
            self.logger.error(f"处理回放 FrameResult 失败: {e}")

    def _on_replay_realtime_data(self, data):
        """快速回放模式：接收实时监控数据"""
        try:
            rt_skip = getattr(self, '_rt_skip_counter', 0) + 1
            self._rt_skip_counter = rt_skip
            if rt_skip < 3:
                return
            self._rt_skip_counter = 0
            
            if hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
                if hasattr(self.real_time_monitoring_tab, 'update_sensor_data'):
                    self.real_time_monitoring_tab.update_sensor_data(data)
        except Exception as e:
            self.logger.error(f"处理回放实时数据失败: {e}")

    def _on_event_jump_requested(self, event_ids: list):
        if not event_ids or not self._replay_controller:
            return
        if len(event_ids) == 1:
            self._replay_controller.jump_to_event(event_ids[0])
        else:
            self._replay_controller.jump_to_events(event_ids)

    def _on_replay_behavior_event(self, event):
        """快速回放模式：接收行为事件"""
        try:
            if not hasattr(self, '_replay_events'):
                self._replay_events = []
            if not hasattr(self, '_replay_event_ids'):
                self._replay_event_ids = set()

            eid = getattr(event, 'id', '') or getattr(event, 'event_id', '')
            if eid and eid not in self._replay_event_ids:
                self._replay_event_ids.add(eid)
                self._replay_events.append(event)

            # 在快速回放模式下，事件应该已经通过 sync_from_cache 同步了，不需要再次注册
            is_fast = False
            if hasattr(self, '_replay_controller') and self._replay_controller:
                is_fast = getattr(self._replay_controller, 'is_fast_mode', False)
            
            if not is_fast:
                from core.core.analysis.event_distributor import EventDistributor
                EventDistributor.instance().register_event(event)
                self._request_event_refresh()
            # 统一从 EventDistributor 同步到回放栏
            self._sync_replay_bar_events()
        except Exception as e:
            self.logger.error(f"处理回放行为事件失败: {e}")

    def _on_seat_evaluation_incremental(self, event_data):
        """STREAMING 模式: 座椅评测增量处理"""
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
            try:
                self.seat_evaluation_tab.set_evaluation_mode('incremental')
                self.seat_evaluation_tab.evaluate_incremental(event_data)
            except Exception as e:
                self.logger.debug(f"座椅评测增量处理失败: {e}")

    def _on_data_bridge_behavior_event(self, event):
        """DataBridge管道检测到行为事件时更新事件面板"""
        try:
            from core.core.analysis.event_distributor import EventDistributor
            EventDistributor.instance().register_event(event)
            self._request_event_refresh()

            if not hasattr(self, '_replay_events'):
                self._replay_events = []
            if not hasattr(self, '_replay_event_ids'):
                self._replay_event_ids = set()

            eid = getattr(event, 'id', '') or getattr(event, 'event_id', '')
            if eid and eid not in self._replay_event_ids:
                self._replay_event_ids.add(eid)
                self._replay_events.append(event)
            # 统一从 EventDistributor 同步到回放栏
            self._sync_replay_bar_events()

            self._try_switch_replay_to_fast()
        except Exception as e:
            self.logger.error(f"处理DataBridge行为事件失败: {e}")

    def _try_switch_replay_to_fast(self):
        if not hasattr(self, '_replay_controller') or not self._replay_controller:
            return
        if getattr(self, '_replay_fast_switch_attempted', False):
            return
        if self._replay_controller.is_fast_mode:
            self._replay_fast_switch_attempted = True
            return
        if len(self._replay_events) < 2:
            return

        self._replay_fast_switch_attempted = True
        try:
            if self._data_bridge:
                analysis_cache = self._data_bridge.get_analysis_cache()
                if analysis_cache:
                    has_results = self._replay_controller.load_analysis_cache(analysis_cache)
                    if has_results:
                        self._replay_controller.set_replay_mode('fast')
                        self.logger.info(f"实时管道事件已生成，回放模式自动切换为 fast，共{len(self._replay_events)}个事件")
                    else:
                        self.logger.warning("尝试切换回放模式但分析缓存仍无数据")
        except Exception as e:
            self.logger.error(f"自动切换回放模式失败: {e}")

    def refresh_events_from_cache(self):
        if not hasattr(self, '_replay_controller') or not self._replay_controller:
            return
        try:
            events = self._replay_controller.get_events()
            if not events:
                return
            if not hasattr(self, '_replay_events'):
                self._replay_events = []
            if not hasattr(self, '_replay_event_ids'):
                self._replay_event_ids = set()

            from core.core.analysis.event_distributor import EventDistributor
            distributor = EventDistributor.instance()
            new_count = 0
            for event in events:
                eid = getattr(event, 'id', '') or getattr(event, 'event_id', '')
                if eid and eid not in self._replay_event_ids:
                    self._replay_event_ids.add(eid)
                    self._replay_events.append(event)
                    distributor.register_event(event)
                    new_count += 1

            if new_count > 0:
                self._sync_replay_bar_events()
                self.logger.info(f"后台事件生成完成，新增 {new_count} 个事件，总计 {len(self._replay_events)} 个")
        except Exception as e:
            self.logger.error(f"刷新事件列表失败: {e}")

    # ── PipelineModeController 集成 ──────────────────────────

    def set_cache_registry(self, registry):
        """注入 CacheRegistry（由 core_ui_components 调用）"""
        self._cache_registry = registry
        self._pipeline_controller.set_cache_registry(registry)
        self.logger.info(f"CacheRegistry 已注入到右侧面板: {registry.count} 个缓存")
        # ── 立即填充回放栏缓存选择器 ──
        if hasattr(self, 'replay_bar') and self.replay_bar and registry:
            try:
                caches = registry.list_caches()
                self.replay_bar.set_cache_list(caches)
                self.logger.info(f"缓存选择器已填充: {len(caches)} 个缓存")
            except Exception as e:
                self.logger.warning(f"填充缓存选择器失败: {e}")
        # ── 注入到全量统计分析页 ──
        if hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab and registry:
            try:
                stats_tab = getattr(self.seat_evaluation_tab, '_statistics_tab', None)
                if stats_tab and hasattr(stats_tab, 'set_cache_registry'):
                    stats_tab.set_cache_registry(registry)
            except Exception as e:
                self.logger.warning(f"注入 CacheRegistry 到全量统计分析页失败: {e}")

    def _on_cache_selection_changed(self, cache_id: str):
        """缓存选择器变更回调 → 加载新缓存数据集"""
        if not cache_id:
            return
        self.logger.info(f"缓存选择变更: {cache_id[:8]}...")
        # 先清除所有模块的旧数据残留
        self._on_clear_all_ui()
        if self._pipeline_controller.load_cache_by_id(cache_id):
            # 从 ReplayController 获取事件，注册到 EventDistributor 统一管理
            if hasattr(self, '_replay_controller') and self._replay_controller:
                events = self._replay_controller.get_events()
                if events:
                    from core.core.analysis.event_distributor import EventDistributor
                    distributor = EventDistributor.instance()
                    for event in events:
                        distributor.register_event(event)
                    self.logger.info(f"已将 {len(events)} 个事件注册到 EventDistributor")
                # 统一从 EventDistributor 同步到回放栏
                self._sync_replay_bar_events()
                if hasattr(self, 'replay_bar') and self.replay_bar:
                    t_min, t_max = self._replay_controller.time_range
                    self.replay_bar.set_time_range(t_min, t_max)
                    self.replay_bar.set_status('缓存已切换，点击播放开始回放')
                    self.replay_bar.set_play_enabled(True)
                source_types = self._replay_controller.get_available_source_types()
                if source_types and hasattr(self, 'replay_bar') and self.replay_bar:
                    self.replay_bar.set_source_info(source_types)

    def _sync_replay_bar_events(self):
        """从 EventDistributor 统一同步事件到回放栏（单一事件源）"""
        if hasattr(self, 'replay_bar') and self.replay_bar:
            self.replay_bar.sync_events_from_distributor()

    def _on_clear_all_ui(self):
        """清空所有 UI 模块状态（通过统一注册中心一键清除）"""
        self.logger.info("执行 UI 全量清空...")
        from core.core.analysis.clearable_registry import ClearableRegistry
        registry = ClearableRegistry.instance()
        registry.clear_all()
        # 清除右侧面板自身的缓存事件记录
        self._replay_events = []
        self._replay_event_ids = set()
        self.logger.info("UI 全量清空完成")

    def _on_pipeline_mode_changed(self, mode_str: str):
        """Pipeline 模式变更回调"""
        from core.core.analysis.pipeline_mode_controller import PipelineMode
        self.logger.info(f"Pipeline 模式已变更: {mode_str}")
        # 更新回放栏可见性
        if hasattr(self, 'replay_bar') and self.replay_bar:
            if mode_str in (PipelineMode.REPLAY.value, PipelineMode.REANALYZE.value):
                self.replay_bar.show_bar()
            elif mode_str == PipelineMode.STREAMING.value:
                self.replay_bar.hide_bar()
            elif mode_str == PipelineMode.IDLE.value:
                self.replay_bar.hide_bar()

    def _on_cnap_sensor_batch(self, batch):
        if not hasattr(self, 'cnap_visualization_tab') or not self.cnap_visualization_tab:
            return
        now = time.time()
        if not hasattr(self, '_last_cnap_batch_time'):
            self._last_cnap_batch_time = 0
        if now - self._last_cnap_batch_time < 0.05:
            return
        self._last_cnap_batch_time = now
        if not hasattr(self, '_cnap_batch_count'):
            self._cnap_batch_count = 0
        self._cnap_batch_count += 1
        cnap_count = 0
        last_cnap = None
        for sensor_data in batch:
            if isinstance(sensor_data, dict) and (sensor_data.get('cnap_type') or 'pressure' in sensor_data):
                cnap_count += 1
                self.receive_cnap_data(sensor_data)
                last_cnap = sensor_data
        if self._data_bridge and cnap_count > 0:
            cnap_records = [s for s in batch if isinstance(s, dict) and (s.get('cnap_type') or 'pressure' in s)]
            if cnap_records:
                try:
                    self._data_bridge.feed_parsed_batch(cnap_records)
                except Exception as e:
                    self.logger.error(f"喂入CNAP数据到data_bridge失败: {e}")
        if cnap_count > 0 and (self._cnap_batch_count <= 3 or self._cnap_batch_count % 50 == 0):
            self.logger.info(f"CNAP batch #{self._cnap_batch_count}: {len(batch)}条, CNAP={cnap_count}条")

    def _on_cnap_sensor_data(self, sensor_data):
        if hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
            self.receive_cnap_data(sensor_data)

    def _on_imu_sensor_batch(self, batch):
        if not hasattr(self, '_imu_batch_count'):
            self._imu_batch_count = 0
        self._imu_batch_count += 1

        now = time.time()
        if not hasattr(self, '_last_imu_batch_time'):
            self._last_imu_batch_time = 0
        if now - self._last_imu_batch_time < 0.08:
            return
        self._last_imu_batch_time = now

        if self._imu_batch_count <= 3:
            sample_keys = []
            for s in batch[:3]:
                if isinstance(s, dict):
                    sample_keys.append(list(s.keys())[:10])
            self.logger.info(f"[IMU_BATCH] #{self._imu_batch_count}: {len(batch)}条, sample_keys={sample_keys}")

        imu_count = 0
        last_imu = None
        processed_records = []

        for sensor_data in batch:
            if not isinstance(sensor_data, dict):
                continue
            source_type = sensor_data.get('_source_type', '')

            # ── raw CSV 格式回退（CANFullParser 失败产物） ──
            # 数据格式: {'raw': 'HH:MM:SS.ffffff,speed_kmh,wheel_angle,,,,,...', '_source_type': 'can_wide'}
            if 'raw' in sensor_data:
                parts = sensor_data['raw'].split(',')
                # 解析时间戳
                ts_str = parts[0].strip() if parts else ''
                try:
                    h, m, s = ts_str.split(':')
                    ts_abs = float(h) * 3600 + float(m) * 60 + float(s)
                except (ValueError, AttributeError):
                    ts_abs = 0.0
                if not hasattr(self, '_raw_csv_t0'):
                    self._raw_csv_t0 = ts_abs
                ts = ts_abs - self._raw_csv_t0

                raw_speed = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0.0
                raw_wheel = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0.0

                pipeline_data = {
                    'timestamp': ts,
                    't': ts,
                    'ax': 0.0,
                    'ay': 0.0,
                    'az': 0.0,
                    'gx': 0.0,
                    'gy': 0.0,
                    'gz': 0.0,
                    'speed': raw_speed * 0.277778,  # km/h → m/s
                    'wheel': raw_wheel,
                    'loc1': 0.0,
                    'loc2': 0.0,
                    '_source_type': 'can_wide',
                    '_source_id': sensor_data.get('source_id', sensor_data.get('_source_id', '')),
                    '_source_name': sensor_data.get('_source_name', ''),
                    '_normalized_from': 'raw_csv',
                }
                imu_count += 1
                last_imu = pipeline_data
                processed_records.append(pipeline_data)
                continue

            # can_long 解析器输出同时有 ax/ay/az/gx/gy/gz 和 can_long 标识字段，
            # 必须优先于 imu_standalone 分支处理，否则 speed 不会被转换为 m/s
            is_can_long_src = (
                source_type == 'can_long' or
                any(k in sensor_data for k in ('Ax_m_s2', 'Gx_dps', '车速_kmh'))
            )
            if is_can_long_src:
                ts = sensor_data.get('rel_time', sensor_data.get('timestamp', time.time()))
                pipeline_data = {
                    'timestamp': ts,
                    't': ts,
                    'ax': float(sensor_data.get('Ax_m_s2', sensor_data.get('ax', 0)) or 0),
                    'ay': float(sensor_data.get('Ay_m_s2', sensor_data.get('ay', 0)) or 0),
                    'az': float(sensor_data.get('Az_m_s2', sensor_data.get('az', 0)) or 0),
                    'gx': float(sensor_data.get('Gx_rad_s', sensor_data.get('gx', 0)) or 0),
                    'gy': float(sensor_data.get('Gy_rad_s', sensor_data.get('gy', 0)) or 0),
                    'gz': float(sensor_data.get('Gz_rad_s', sensor_data.get('gz', 0)) or 0),
                    'speed': float(sensor_data.get('车速_kmh', sensor_data.get('speed', 0)) or 0) * 0.277778,
                    'wheel': float(sensor_data.get('方向盘转角_deg', sensor_data.get('wheel', 0)) or 0),
                    'loc1': 0.0,
                    'loc2': 0.0,
                    '_source_type': 'can_long',
                    '_source_id': sensor_data.get('_source_id', ''),
                    '_source_name': sensor_data.get('_source_name', sensor_data.get('imu_name', '')),
                    '_normalized_from': 'can_long',
                }
                imu_count += 1
                last_imu = pipeline_data
                processed_records.append(pipeline_data)
            elif source_type in ('imu_standalone', 'pipeline') or any(k in sensor_data for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
                sensor_data = dict(sensor_data)
                if 't' not in sensor_data and 'timestamp' in sensor_data:
                    sensor_data['t'] = sensor_data['timestamp']
                if 'timestamp' not in sensor_data and 't' in sensor_data:
                    sensor_data['timestamp'] = sensor_data['t']
                imu_count += 1
                last_imu = sensor_data
                processed_records.append(sensor_data)
            elif source_type == 'can_wide':
                ch = None
                for c in ('ch1', 'ch3', 'ch4', 'ch5'):
                    if f'{c}_ax' in sensor_data:
                        ch = c
                        break
                if ch:
                    ts = sensor_data.get('timestamp', time.time())
                    pipeline_data = {
                        'timestamp': ts,
                        't': ts,
                        'ax': sensor_data.get(f'{ch}_ax', 0),
                        'ay': sensor_data.get(f'{ch}_ay', 0),
                        'az': sensor_data.get(f'{ch}_az', 0),
                        'gx': sensor_data.get(f'{ch}_gx', 0),
                        'gy': sensor_data.get(f'{ch}_gy', 0),
                        'gz': sensor_data.get(f'{ch}_gz', 0),
                        'speed': sensor_data.get('speed', 0),
                        'wheel': sensor_data.get('steering', 0),
                        'loc1': 0.0,
                        'loc2': 0.0,
                        'channel': ch,                             # ← 保留用于过滤
                        'imu_name': sensor_data.get('imu_name', ch),  # ← 保留
                        '_source_type': 'can_wide',
                        '_source_id': sensor_data.get('source_id', ''),
                        '_normalized_from': 'can_wide',
                    }
                    imu_count += 1
                    last_imu = pipeline_data
                    processed_records.append(pipeline_data)
            elif source_type == 'can_long':
                ts = sensor_data.get('rel_time', sensor_data.get('timestamp', time.time()))
                pipeline_data = {
                    'timestamp': ts,
                    't': ts,
                    'ax': float(sensor_data.get('Ax_m_s2', 0) or 0),
                    'ay': float(sensor_data.get('Ay_m_s2', 0) or 0),
                    'az': float(sensor_data.get('Az_m_s2', 0) or 0),
                    'gx': float(sensor_data.get('Gx_rad_s', 0) or 0),
                    'gy': float(sensor_data.get('Gy_rad_s', 0) or 0),
                    'gz': float(sensor_data.get('Gz_rad_s', 0) or 0),
                    'speed': float(sensor_data.get('车速_kmh', 0) or 0) * 0.277778,
                    'wheel': float(sensor_data.get('方向盘转角_deg', 0) or 0),
                    '车速_kmh': sensor_data.get('车速_kmh', sensor_data.get('speed', 0)),  # ← 保留km/h
                    'loc1': 0.0,
                    'loc2': 0.0,
                    'channel': sensor_data.get('channel', 'ch1'),           # ← 保留
                    'imu_name': sensor_data.get('imu_name', ''),           # ← 保留
                    '_source_type': 'can_long',
                    '_source_id': sensor_data.get('_source_id', ''),
                    '_source_name': sensor_data.get('_source_name', sensor_data.get('imu_name', '')),
                    '_normalized_from': 'can_long',
                }
                imu_count += 1
                last_imu = pipeline_data
                processed_records.append(pipeline_data)

        if self._data_bridge and imu_count > 0:
            is_fast = (hasattr(self, '_replay_controller') and self._replay_controller
                       and getattr(self._replay_controller, 'is_fast_mode', False))
            is_batch_done = self._data_bridge.is_batch_analyzed
            if is_fast or is_batch_done:
                if self._imu_batch_count <= 3:
                    mode = "快速回放" if is_fast else "批量分析已完成"
                    self.logger.debug(f"[DEBUG] {mode}，跳过DataBridge管道")
            else:
                if not self._data_bridge.is_running:
                    try:
                        self._data_bridge.start_processing()
                        self.logger.debug("[DEBUG] 自动启动 DataBridge 分析管线")
                    except Exception as e:
                        self.logger.error(f"自动启动 DataBridge 失败: {e}")
                QTimer.singleShot(5, lambda recs=list(processed_records): self._deferred_feed_bridge(recs))

        if hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
            imu_records = []
            for sensor_data in processed_records:
                if not isinstance(sensor_data, dict):
                    continue
                if any(k in sensor_data for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
                    sensor_data = dict(sensor_data)
                    if 't' not in sensor_data and 'timestamp' in sensor_data:
                        sensor_data['t'] = sensor_data['timestamp']
                    if 'timestamp' not in sensor_data and 't' in sensor_data:
                        sensor_data['timestamp'] = sensor_data['t']
                    imu_records.append(sensor_data)
            if len(imu_records) <= 500:
                for sensor_data in imu_records:
                    self.imu_visualization_tab.receive_imu_data(sensor_data)
            else:
                if not self._imu_viz_queue:
                    self._imu_viz_queue = imu_records
                    self._imu_viz_idx = 0
                    QTimer.singleShot(0, self._process_imu_viz_chunk)

        if self._imu_batch_count <= 3 or self._imu_batch_count % 50 == 0:
            self.logger.info(f"[IMU_BATCH] #{self._imu_batch_count}: {len(batch)}条, IMU={imu_count}条, processed={len(processed_records)}条")

    def _deferred_feed_bridge(self, recs):
        self._data_bridge.set_suppress_ui_signals(True)
        try:
            self._data_bridge.feed_parsed_batch(recs)
        finally:
            self._data_bridge.set_suppress_ui_signals(False)

    def _process_imu_viz_chunk(self):
        chunk = 50
        end = min(self._imu_viz_idx + chunk, len(self._imu_viz_queue))
        for i in range(self._imu_viz_idx, end):
            self.imu_visualization_tab.receive_imu_data(self._imu_viz_queue[i])
        self._imu_viz_idx = end
        if self._imu_viz_idx < len(self._imu_viz_queue):
            QTimer.singleShot(5, self._process_imu_viz_chunk)
        else:
            self._imu_viz_queue = []

    def _on_imu_sensor_data(self, sensor_data):
        if not hasattr(self, 'imu_visualization_tab') or not self.imu_visualization_tab:
            return
        if not isinstance(sensor_data, dict):
            return
        if any(k in sensor_data for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
            self.imu_visualization_tab.receive_imu_data(sensor_data)
            return
        if 'ch1_ax' in sensor_data or 'ch3_ax' in sensor_data or 'ch4_ax' in sensor_data or 'ch5_ax' in sensor_data:
            ch = 'ch1'
            if 'ch3_ax' in sensor_data:
                ch = 'ch3'
            elif 'ch4_ax' in sensor_data:
                ch = 'ch4'
            elif 'ch5_ax' in sensor_data:
                ch = 'ch5'
            pipeline_data = {
                'timestamp': sensor_data.get('timestamp', time.time()),
                'ax': sensor_data.get(f'{ch}_ax', 0),
                'ay': sensor_data.get(f'{ch}_ay', 0),
                'az': sensor_data.get(f'{ch}_az', 0),
                'gx': sensor_data.get(f'{ch}_gx', 0),
                'gy': sensor_data.get(f'{ch}_gy', 0),
                'gz': sensor_data.get(f'{ch}_gz', 0),
                'speed': sensor_data.get('speed', 0),
                'wheel': sensor_data.get('steering', 0),
                'loc1': 0.0,
                'loc2': 0.0,
            }
            self.imu_visualization_tab.receive_imu_data(pipeline_data)

    def receive_cnap_data(self, sensor_data):
        """接收 CNAP 数据（公共接口，支持 WAVE 波形 + BEATS 逐拍参数）"""
        if not hasattr(self, 'cnap_visualization_tab') or not self.cnap_visualization_tab:
            return
        try:
            if isinstance(sensor_data, (int, float)):
                self.cnap_visualization_tab.feed_sample(float(sensor_data))
                return

            if isinstance(sensor_data, dict):
                cnap_type = sensor_data.get('cnap_type', '')

                if cnap_type == 'WAVE' or 'pressure' in sensor_data:
                    val = float(sensor_data.get('pressure', 0))
                    if val >= 0:
                        if not hasattr(self, '_cnap_map_logged'):
                            self._cnap_map_logged = True
                            self.logger.info(f"CNAP WAVE 数据映射确认: pressure={val:.1f} mmHg")
                        self.cnap_visualization_tab.feed_sample(val)

                if cnap_type == 'BEATS':
                    if not hasattr(self, '_beat_count'):
                        self._beat_count = 0
                    self._beat_count += 1
                    if self._beat_count <= 3 or self._beat_count % 100 == 0:
                        self.logger.info(f"CNAP BEATS #{self._beat_count}: SBP={sensor_data.get('Systolic_BP')}, "
                                         f"DBP={sensor_data.get('Diastolic_BP')}, HR={sensor_data.get('Heart_Rate')}")
                    self._update_cnap_vitals(sensor_data)

            elif hasattr(sensor_data, 'cnap'):
                self.cnap_visualization_tab.feed_sample(float(sensor_data.cnap))

        except Exception as e:
            self.logger.warning(f"receive_cnap_data 异常: {e}")

    def _update_cnap_vitals(self, beat: dict):
        tab = getattr(self, 'cnap_visualization_tab', None)
        if not tab:
            return
        try:
            sbp = beat.get('Systolic_BP')
            dbp = beat.get('Diastolic_BP')
            map_val = beat.get('Mean_Arterial_Pressure')
            hr = beat.get('Heart_Rate')
            pp = beat.get('Pulse_Pressure')
            hrv = beat.get('Heart_Rate_Variability')
            mpp = beat.get('Mean_Pulse_Pressure')
            sv = beat.get('Stroke_Volume')
            svr = beat.get('Vascular_Resistance')
            ppv = beat.get('PPV')
            svv = beat.get('SVV')
            ef = beat.get('Ejection_Fraction')

            if hasattr(tab, 'update_vitals'):
                tab.update_vitals(
                    sbp=sbp, dbp=dbp, map_val=map_val, hr=hr,
                    pulse_pressure=pp, heart_rate_variability=hrv,
                    mean_pulse_pressure=mpp, stroke_volume=sv,
                    vascular_resistance=svr, ppv=ppv, svv=svv,
                    ejection_fraction=ef,
                )
        except Exception as e:
            self.logger.warning(f"更新CNAP生命体征失败: {e}")

    def _initialize_monitoring_widgets(self):
        """初始化监控控件字典，确保update_monitoring_data方法能够正常工作"""
        # 确保 monitoring_widgets 字典已初始化
        if not hasattr(self, 'monitoring_widgets'):
            self.monitoring_widgets = {}
        
        # 初始化监控指标
        metrics = [
            ("CPU使用率", "0%", "progress"),
            ("内存使用率", "0%", "progress"),
            ("数据接收率", "0 Hz", "label"),
            ("处理延迟", "0 ms", "label"),
            ("错误计数", "0", "label"),
            ("连接状态", "断开", "status")
        ]
        
        # 确保所有指标都在字典中
        for name, default_value, widget_type in metrics:
            if name not in self.monitoring_widgets:
                # 创建一个虚拟控件来存储值
                widget = QLabel(default_value)
                if widget_type == "status":
                    widget.setStyleSheet("color: red; font-weight: bold;")
                elif widget_type == "label":
                    widget.setStyleSheet("font-family: Consolas; font-size: 10pt;")
                self.monitoring_widgets[name] = widget
        
        self.logger.info("监控控件字典已初始化完成")
            
    def _connect_event_linkage(self):
        """连接事件联动信号：实时行为监控 -> CAN全量解析"""
        try:
            if not hasattr(self, 'real_time_monitoring_tab') or not self.real_time_monitoring_tab:
                self.logger.warning("实时行为监控标签页未就绪，无法连接事件联动")
                return
            
            if not hasattr(self, 'can_full_tab') or not self.can_full_tab:
                self.logger.warning("CAN全量解析标签页未就绪，无法连接事件联动")
                return
            
            # 连接事件点击信号
            if hasattr(self.real_time_monitoring_tab, 'event_clicked'):
                self.real_time_monitoring_tab.event_clicked.connect(
                    lambda event_id, start_ts, end_ts: 
                    self._on_event_clicked(event_id, start_ts, end_ts)
                )
                self.logger.info("✅ 实时行为监控 -> CAN全量解析 事件联动已连接")
            
        except Exception as e:
            self.logger.error(f"连接事件联动失败: {e}")
    
    def _on_event_clicked(self, event_id: int, start_ts: float, end_ts: float):
        """处理事件点击：切换到CAN全量解析标签页并高亮对应数据"""
        try:
            self.logger.info(f"收到事件点击: event_id={event_id}, time_range=[{start_ts:.3f}, {end_ts:.3f}]")
            
            # 切换到CAN全量解析标签页
            can_full_index = -1
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == "CAN全量解析":
                    can_full_index = i
                    break
            
            if can_full_index >= 0:
                self.tab_widget.setCurrentIndex(can_full_index)
            
            # 确保CAN全量解析标签页已初始化
            if not hasattr(self, 'can_full_tab') or not self.can_full_tab:
                self._create_can_full_tab()
            
            # 高亮事件时间范围的数据
            if hasattr(self.can_full_tab, 'highlight_event_time_range'):
                self.can_full_tab.highlight_event_time_range(event_id, start_ts, end_ts)
            
        except Exception as e:
            self.logger.error(f"处理事件点击失败: {e}")
    
    def _create_fallback_monitoring_tab(self):
        """创建备用的实时监控标签页"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(12)
        
        # 实时数据监控
        monitoring_group = QGroupBox("实时数据监控")
        monitoring_layout = QGridLayout(monitoring_group)
        
        # 创建多个监控指标
        self.monitoring_widgets = {}
        metrics = [
            ("CPU使用率", "0%", "progress"),
            ("内存使用率", "0%", "progress"),
            ("数据接收率", "0 Hz", "label"),
            ("处理延迟", "0 ms", "label"),
            ("错误计数", "0", "label"),
            ("连接状态", "断开", "status")
        ]
        
        for i, (name, default_value, widget_type) in enumerate(metrics):
            row = i // 2
            col = i % 2 * 2
            
            # 标签
            label = QLabel(f"{name}:")
            label.setFont(QFont("Microsoft YaHei", 9))
            monitoring_layout.addWidget(label, row, col)
            
            # 值显示
            if widget_type == "progress":
                widget = QProgressBar()
                widget.setRange(0, 100)
                widget.setValue(0)
                widget.setMaximumWidth(150)
            elif widget_type == "status":
                widget = QLabel(default_value)
                widget.setStyleSheet("color: red; font-weight: bold;")
            else:
                widget = QLabel(default_value)
                widget.setStyleSheet("font-family: Consolas; font-size: 10pt;")
            
            self.monitoring_widgets[name] = widget
            monitoring_layout.addWidget(widget, row, col + 1)
        
        layout.addWidget(monitoring_group)
        
        # 实时日志
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        
        self.realtime_log = QTextEdit()
        self.realtime_log.setMaximumHeight(120)
        self.realtime_log.setReadOnly(True)
        self.realtime_log.setStyleSheet("background-color: #F5F5F5; font-family: Consolas; font-size: 8pt;")
        
        log_layout.addWidget(self.realtime_log)
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab_widget, "实时行为监控")
        
    def _apply_professional_style(self):
        """应用专业样式"""
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 9pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background-color: #F0F0F0;
            }
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover {
                background-color: #D0D0D0;
            }
            QPushButton {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 9pt;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 4px 8px;
                background-color: white;
                min-height: 20px;
            }
            QTableWidget {
                gridline-color: #E0E0E0;
                selection-background-color: #E3F2FD;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                padding: 4px;
                font-weight: bold;
            }
        """)
        
    def _on_tab_changed(self, index):
        """标签页切换处理（延迟初始化）"""
        if index >= 0:
            tab_name = self.tab_widget.tabText(index)
            if index not in self._tab_initialized or not self._tab_initialized[index]:
                QTimer.singleShot(50, lambda: self._ensure_tab_initialized(index))
            self.tab_changed.emit(tab_name)
            self.logger.info(f"切换到标签页: {tab_name}")

    def _ensure_tab_initialized(self, index):
        if index in self._tab_initialized and self._tab_initialized[index]:
            return
        self._tab_initialized[index] = True
        try:
            if index == 0:
                self._create_cnap_visualization_tab()
                self._inject_dependencies_to_tab('cnap')
            elif index == 1:
                self._create_imu_visualization_tab()
                self._inject_dependencies_to_tab('imu')
            elif index == 2:
                self._create_can_full_tab()
                self._inject_dependencies_to_tab('can_full')
            elif index == 3:
                self._create_real_time_monitoring_tab()
                self._inject_dependencies_to_tab('real_time')
            elif index == 4:
                self._create_seat_evaluation_tab()
                self._inject_dependencies_to_tab('seat_evaluation')
            elif index == 5:
                self._create_metadata_management_tab()
            
            if 2 in self._tab_initialized and 3 in self._tab_initialized:
                QTimer.singleShot(100, self._connect_event_linkage)
            
        except Exception as e:
            self.logger.error(f"延迟初始化标签页 {index} 失败: {e}")
            self._tab_initialized[index] = False

    def _inject_dependencies_to_tab(self, tab_key: str):
        """向延迟创建的标签页注入已设置的依赖"""
        try:
            if self._data_bridge:
                if tab_key == 'cnap' and hasattr(self, 'cnap_visualization_tab') and self.cnap_visualization_tab:
                    self.cnap_visualization_tab.set_data_bridge(self._data_bridge)
                    self.cnap_visualization_tab.start()
                    self._data_bridge.sensor_data_batch_received.connect(self._on_cnap_sensor_batch)
                elif tab_key == 'imu' and hasattr(self, 'imu_visualization_tab') and self.imu_visualization_tab:
                    self.imu_visualization_tab.set_data_bridge(self._data_bridge)
                    self.imu_visualization_tab.start()
                    self._data_bridge.sensor_data_batch_received.connect(self._on_imu_sensor_batch)
                elif tab_key == 'can_full' and hasattr(self, 'can_full_tab') and self.can_full_tab:
                    self.can_full_tab.set_data_bridge(self._data_bridge)
                elif tab_key == 'real_time' and hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
                    self.real_time_monitoring_tab.set_data_bridge(self._data_bridge)
                elif tab_key == 'seat_evaluation' and hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                    self.seat_evaluation_tab.set_data_bridge(self._data_bridge)

            if self._cache:
                if tab_key == 'can_full' and hasattr(self, 'can_full_tab') and self.can_full_tab:
                    if hasattr(self.can_full_tab, 'set_cache'):
                        self.can_full_tab.set_cache(self._cache)

            if hasattr(self, '_seat_evaluation_engine') and self._seat_evaluation_engine:
                if tab_key == 'seat_evaluation' and hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                    self.seat_evaluation_tab.set_evaluation_engine(self._seat_evaluation_engine)

            if hasattr(self, '_comparative_engine') and self._comparative_engine:
                if tab_key == 'seat_evaluation' and hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                    if hasattr(self.seat_evaluation_tab, 'set_comparative_engine'):
                        self.seat_evaluation_tab.set_comparative_engine(self._comparative_engine)

            if self._replay_controller:
                if tab_key == 'can_full' and hasattr(self, 'can_full_tab') and self.can_full_tab:
                    if hasattr(self.can_full_tab, 'set_replay_mode'):
                        self.can_full_tab.set_replay_mode(True)
                    try:
                        self._replay_controller.can_raw_data_batch_received.connect(self.can_full_tab._on_batch_received)
                        self.logger.info("回放控制器 can_raw_data_batch_received 已连接到CAN全量解析标签页")
                    except Exception:
                        pass
                    if self._cache:
                        if hasattr(self.can_full_tab, 'set_cache'):
                            self.can_full_tab.set_cache(self._cache)
                if tab_key == 'real_time' and hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
                    pass
                if tab_key == 'seat_evaluation' and hasattr(self, 'seat_evaluation_tab') and self.seat_evaluation_tab:
                    if hasattr(self.seat_evaluation_tab, 'comparative_evaluation_tab') and self.seat_evaluation_tab.comparative_evaluation_tab:
                        if hasattr(self.seat_evaluation_tab.comparative_evaluation_tab, 'set_replay_controller'):
                            self.seat_evaluation_tab.comparative_evaluation_tab.set_replay_controller(self._replay_controller)

        except Exception as e:
            self.logger.debug(f"注入依赖到 {tab_key} 失败: {e}")

    def _create_seat_evaluation_tab(self):
        """创建座椅评测标签页（已整合对照分析功能）"""
        if hasattr(self, 'seat_evaluation_tab'):
            return
        QApplication.processEvents()
        if SEAT_EVALUATION_AVAILABLE:
            try:
                self.seat_evaluation_tab = SeatEvaluationTab(self.config_manager)
                QApplication.processEvents()
                self._replace_placeholder_tab(4, self.seat_evaluation_tab, "座椅评测")
                if self._data_bridge:
                    self.seat_evaluation_tab.set_data_bridge(self._data_bridge)
                # 尝试从服务定位器获取座椅评测引擎
                try:
                    from core.core.service_locator import ServiceLocator
                    seat_evaluation_engine = ServiceLocator().get('seat_evaluation_engine')
                    if seat_evaluation_engine:
                        self.seat_evaluation_tab.set_evaluation_engine(seat_evaluation_engine)
                except Exception as e:
                    self.logger.warning(f"无法获取座椅评测引擎: {e}")
                # 尝试从服务定位器获取对照分析引擎
                try:
                    from core.core.service_locator import ServiceLocator
                    comparative_engine = ServiceLocator().get('comparative_evaluation_engine')
                    if comparative_engine:
                        self.seat_evaluation_tab.set_comparison_engine(comparative_engine)
                except Exception as e:
                    self.logger.warning(f"无法获取对照分析引擎: {e}")
                self.logger.info("✅ 座椅评测标签页已添加（已整合对照分析）")
                return
            except Exception as e:
                self.logger.error(f"创建座椅评测标签页失败: {e}")
        
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        info_label = QLabel("座椅评测模块不可用")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(info_label)
        self._replace_placeholder_tab(4, tab_widget, "座椅评测")

    def _create_metadata_management_tab(self):
        if hasattr(self, 'metadata_management_tab'):
            return
        QApplication.processEvents()
        if METADATA_MANAGEMENT_AVAILABLE:
            try:
                self.metadata_management_tab = MetadataManagementTab(self.config_manager)
                QApplication.processEvents()
                self._replace_placeholder_tab(5, self.metadata_management_tab, "元数据管理")
                self.logger.info("元数据管理标签页已添加")
                return
            except Exception as e:
                self.logger.error(f"创建元数据管理标签页失败: {e}")

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        info_label = QLabel("元数据管理模块不可用")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #6c757d; font-size: 14px;")
        layout.addWidget(info_label)
        self._replace_placeholder_tab(5, tab_widget, "元数据管理")

            
    def update_monitoring_data(self, data: dict):
        """更新监控数据"""
        try:
            self.logger.info(f"开始更新监控数据: {data}")
            
            # 确保 monitoring_widgets 字典已初始化
            if not hasattr(self, 'monitoring_widgets'):
                self.monitoring_widgets = {}
                self.logger.warning("monitoring_widgets 字典未初始化，已创建空字典")
            
            # 更新实时行为监控标签页
            if hasattr(self, 'real_time_monitoring_tab') and self.real_time_monitoring_tab:
                if hasattr(self.real_time_monitoring_tab, 'update_sensor_data'):
                    self.real_time_monitoring_tab.update_sensor_data(data)
                    self.logger.info("已更新实时行为监控标签页数据")
                else:
                    self.logger.warning("real_time_monitoring_tab 没有 update_sensor_data 方法")
            else:
                self.logger.warning("real_time_monitoring_tab 属性不存在")
            
            # 记录当前 monitoring_widgets 字典内容
            self.logger.debug(f"当前 monitoring_widgets: {list(self.monitoring_widgets.keys())}")
            
            # 统计更新成功和失败的项
            updated_count = 0
            failed_count = 0
            
            # 更新传统监控指标
            for name, value in data.items():
                if name in self.monitoring_widgets:
                    widget = self.monitoring_widgets[name]
                    try:
                        if isinstance(widget, QProgressBar):
                            # 尝试将值转换为整数
                            try:
                                progress_value = int(float(value))  # 允许浮点数值
                                widget.setValue(progress_value)
                            except (ValueError, TypeError):
                                self.logger.warning(f"无法将 '{value}' 转换为进度条数值")
                                widget.setValue(0)
                        else:
                            widget.setText(str(value))
                            
                            # 更新状态颜色
                            if name == "连接状态":
                                if value == "连接":
                                    widget.setStyleSheet("color: green; font-weight: bold;")
                                else:
                                    widget.setStyleSheet("color: red; font-weight: bold;")
                        updated_count += 1
                    except Exception as e:
                        self.logger.error(f"更新 {name} 控件失败: {e}")
                        failed_count += 1
                else:
                    self.logger.warning(f"未找到名为 '{name}' 的监控控件")
                    failed_count += 1
            
            self.logger.info(f"监控数据更新完成: 成功 {updated_count} 项, 失败 {failed_count} 项")
            
        except Exception as e:
            self.logger.error(f"更新监控数据失败: {str(e)}")
            # 在发生异常时尝试添加日志，以便用户了解问题
            self.add_realtime_log(f"更新监控数据异常: {str(e)}", "ERROR")
            
    def add_realtime_log(self, message: str, level: str = "INFO"):
        """添加实时日志"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 根据级别设置颜色
            if level == "ERROR":
                color = "red"
            elif level == "WARNING":
                color = "orange"
            elif level == "SUCCESS":
                color = "green"
            else:
                color = "black"
                
            formatted_message = f'<span style="color: {color};">[{timestamp}] {level}: {message}</span>'
            
            self.realtime_log.append(formatted_message)
            
            # 自动滚动到底部
            scrollbar = self.realtime_log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            self.logger.error(f"添加实时日志失败: {e}")
            
    def get_current_tab_name(self):
        """获取当前标签页名称"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            return self.tab_widget.tabText(index)
        return "未知标签页"
        
    def refresh_all_tabs(self):
        """刷新所有标签页"""
        try:
            current_tab = self.tab_widget.currentIndex()
            self.add_realtime_log("所有标签页已刷新", "SUCCESS")
            self.tab_widget.setCurrentIndex(current_tab)
            self.logger.info("所有标签页已刷新")
        except Exception as e:
            self.logger.error(f"刷新标签页失败: {e}")
            
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'figure'):
                plt.close(self.figure)
            self._replay_events.clear()
            if hasattr(self, '_replay_controller') and self._replay_controller:
                self._replay_controller = None
            self.logger.info("右侧内容面板组件清理完成")
        except Exception as e:
            self.logger.error(f"清理右侧内容面板失败: {e}")
