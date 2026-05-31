#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版CAN全量解析标签页 - 卡片式紧凑布局
支持全量IMU数据接入、按IMU选择显示、滚动加载
"""

import csv
import os
import time
import logging
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
                               QGroupBox, QSizePolicy, QHeaderView,
                               QFileDialog, QMessageBox, QSpinBox, QFrame, QScrollArea,
                               QAbstractScrollArea, QApplication)
from PySide6.QtCore import Qt, Signal, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QBrush

from modules.ui.core_ui.components.can_behavior_timeline_view import CANBehaviorTimelineView
from core.core.data_processing.floor_imu_parser import parse_all_channels, get_channel_stats
from core.core.data_processing.can_parser_v2 import IMU_NAME_MAP
from core.core.analysis.event_distributor import EventDistributor
from modules.ui.professional_styles import PRO_COLORS


# ── 数据源模式枚举 ──
from enum import Enum

class DataSourceMode(Enum):
    """CAN 全量解析 Tab 数据源模式"""
    STREAMING = "streaming"   # DataBridge 实时流
    REPLAY = "replay"         # ReplayController 回放


# 数据表格的列定义
TABLE_COLUMNS = [
    ("timestamp", "时间(s)", 100),
    ("ax", "ax(m/s²)", 90),
    ("ay", "ay(m/s²)", 90),
    ("az", "az(m/s²)", 90),
    ("gx", "gx(rad/s)", 90),
    ("gy", "gy(rad/s)", 90),
    ("gz", "gz(rad/s)", 90),
    ("speed", "车速(km/h)", 90),
    ("wheel", "方向盘(°)", 90),
    ("_imu_name", "IMU名称", 180),
]

# 获取完整的IMU名称列表
ALL_IMU_NAMES = list(IMU_NAME_MAP.values())

# 默认显示行数
DEFAULT_DISPLAY_ROWS = 50
# 每次滚动加载的行数
LOAD_INCREMENT = 50


class EnhancedCANFullParsingTab(QWidget):
    """增强版CAN全量解析标签页 - 卡片式紧凑布局"""

    data_loaded = Signal(str)
    event_clicked = Signal(int, float, float)
    export_completed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # 数据存储
        self._all_channel_data: Dict[str, List[Dict]] = {}
        self._vehicle_data: Dict[str, Any] = {}
        self._current_channel: str = ALL_IMU_NAMES[0] if ALL_IMU_NAMES else ''
        self._current_data: List[Dict] = []
        self._highlight_time_range: Optional[tuple] = None

        # 全量原始数据存储（按IMU名称分组）
        self._raw_data_by_imu: Dict[str, List[Dict]] = {}
        
        # 当前显示的行数
        self._displayed_rows = 0
        
        # 累计接收记录数
        self._total_received = 0
        
        # 回放模式标志
        self._replay_mode = False
        
        # ── 数据源模式 ──
        self._data_source_mode = DataSourceMode.STREAMING
        self._db_signal_conn = None      # DataBridge 信号连接句柄
        self._rc_signal_conn = None      # ReplayController 信号连接句柄
        self._replay_controller_ref = None  # ReplayController 引用（不自动连接）

        # 组件引用
        self._data_bridge = None
        self._cache = None
        self._distributor = EventDistributor.instance()

        # 初始化UI
        self._init_ui()
        self.logger.info("增强版CAN全量解析标签页已初始化")

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        top_card = self._create_top_card()
        outer_layout.addWidget(top_card)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 8, 10, 10)
        content_layout.setSpacing(8)

        event_panel = self._create_event_panel()
        content_layout.addWidget(event_panel)

        data_panel = self._create_data_panel()
        content_layout.addWidget(data_panel)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area, stretch=1)

    def _create_top_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        title = QLabel("CAN数据管理")
        title.setObjectName("panelTitle")
        row1.addWidget(title)
        self.file_label = QLabel("未加载数据文件")
        self.file_label.setObjectName("statLabel")
        row1.addWidget(self.file_label)
        row1.addStretch()
        self.load_file_btn = QPushButton("选择文件")
        self.load_file_btn.setObjectName("btnSmallOutline")
        self.load_file_btn.clicked.connect(self._on_load_file)
        row1.addWidget(self.load_file_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("IMU:"))
        self.channel_combo = QComboBox()
        self.channel_combo.setMinimumWidth(150)
        for imu_name in ALL_IMU_NAMES:
            self.channel_combo.addItem(imu_name, imu_name)
        row2.addWidget(self.channel_combo)
        self.load_btn = QPushButton("加载")
        self.load_btn.setObjectName("btnSmall")
        self.load_btn.clicked.connect(self._on_load_imu_data)
        self.load_btn.setEnabled(False)
        row2.addWidget(self.load_btn)
        self.clear_highlight_btn = QPushButton("清除高亮")
        self.clear_highlight_btn.setObjectName("btnSmallOutline")
        self.clear_highlight_btn.clicked.connect(self._clear_highlight)
        self.clear_highlight_btn.setEnabled(False)
        row2.addWidget(self.clear_highlight_btn)
        row2.addSpacing(16)
        sep = QFrame()
        sep.setObjectName("separatorV")
        sep.setFixedHeight(24)
        row2.addWidget(sep)
        row2.addSpacing(8)
        self.stats_label = QLabel("就绪")
        self.stats_label.setObjectName("statValueAccent")
        row2.addWidget(self.stats_label)
        row2.addSpacing(16)
        sep2 = QFrame()
        sep2.setObjectName("separatorV")
        sep2.setFixedHeight(24)
        row2.addWidget(sep2)
        row2.addSpacing(8)
        self.event_stats_label = QLabel("事件: 0")
        self.event_stats_label.setObjectName("statValue")
        row2.addWidget(self.event_stats_label)
        row2.addStretch()
        layout.addLayout(row2)

        return card

    def _create_event_panel(self) -> QFrame:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("行为事件列表")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch()
        self.behavior_timeline = CANBehaviorTimelineView()
        header.addWidget(self.behavior_timeline.refresh_btn)
        header.addWidget(self.behavior_timeline.clear_btn)
        header.addWidget(self.behavior_timeline.export_btn)
        layout.addLayout(header)

        self.behavior_timeline.event_table.setParent(None)
        self.behavior_timeline.event_table.setMinimumHeight(180)
        self.behavior_timeline.event_table.setMaximumHeight(250)
        self.behavior_timeline.event_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.behavior_timeline.event_table)

        self.behavior_timeline.event_selected.connect(self.highlight_event_time_range)

        hint = QLabel("点击事件可高亮对应时间区间的数据")
        hint.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(hint)

        return card

    def _create_data_panel(self) -> QFrame:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        title = QLabel("IMU数据 (标准化格式)")
        title.setObjectName("panelTitle")
        title_bar.addWidget(title)
        self.display_status_label = QLabel("显示: 0 / 0 行")
        self.display_status_label.setObjectName("statLabel")
        title_bar.addWidget(self.display_status_label)
        title_bar.addStretch()
        self.export_current_btn = QPushButton("导出当前")
        self.export_current_btn.setObjectName("btnSmallOutline")
        self.export_current_btn.clicked.connect(self._on_export_current)
        title_bar.addWidget(self.export_current_btn)
        self.export_all_btn = QPushButton("导出全部")
        self.export_all_btn.setObjectName("btnSmallOutline")
        self.export_all_btn.clicked.connect(self._on_export_all)
        title_bar.addWidget(self.export_all_btn)
        self.export_event_btn = QPushButton("导出事件区间")
        self.export_event_btn.setObjectName("btnSmallOutline")
        self.export_event_btn.clicked.connect(self._on_export_event_data)
        self.export_event_btn.setEnabled(False)
        title_bar.addWidget(self.export_event_btn)
        layout.addLayout(title_bar)

        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.data_table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
        self.data_table.setFont(QFont("Consolas", 10))
        self.data_table.setObjectName("syncSourcesTable")
        self.data_table.setMinimumHeight(400)
        self.data_table.setMaximumHeight(600)
        self.data_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.data_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.data_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._setup_table_headers()
        self.data_table.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.data_table)

        return card

    def _setup_table_headers(self):
        """设置表格表头"""
        self.data_table.setColumnCount(len(TABLE_COLUMNS))
        self.data_table.setHorizontalHeaderLabels([col[1] for col in TABLE_COLUMNS])

        # 设置列宽
        header = self.data_table.horizontalHeader()
        header.setObjectName("syncSourcesHeader")
        for i, (_, _, width) in enumerate(TABLE_COLUMNS):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.data_table.setColumnWidth(i, width)

        # 最后一列可伸展
        header.setSectionResizeMode(len(TABLE_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)

    def set_replay_mode(self, enabled: bool):
        """设置回放模式（兼容旧接口，实际由 set_data_source_mode 管理）"""
        self._replay_mode = enabled
        self.logger.info(f"回放模式: {enabled}")

    # ── 数据源模式管理 ──

    def set_data_source_mode(self, mode: DataSourceMode):
        """
        切换数据源模式，自动断开旧连接、建立新连接。
        外部调用者无需知道内部信号细节。
        """
        if mode == self._data_source_mode:
            return

        # 断开所有当前连接
        self._disconnect_all_sources()

        # 建立新连接
        if mode == DataSourceMode.STREAMING and self._data_bridge:
            self._db_signal_conn = (
                self._data_bridge.sensor_data_batch_received.connect(
                    self._on_batch_received
                )
            )
            self.logger.info("CAN Tab 已连接 DataBridge 流式数据")
        elif mode == DataSourceMode.REPLAY and self._replay_controller_ref:
            self._rc_signal_conn = (
                self._replay_controller_ref.can_raw_data_batch_received.connect(
                    self._on_batch_received
                )
            )
            self.logger.info("CAN Tab 已连接 ReplayController 回放数据")

        self._data_source_mode = mode
        self._replay_mode = (mode == DataSourceMode.REPLAY)
        self.logger.info(f"CAN Tab 数据源模式切换: {mode.value}")

    def _disconnect_all_sources(self):
        """安全断开所有信号连接"""
        if self._db_signal_conn and self._data_bridge:
            try:
                self._data_bridge.sensor_data_batch_received.disconnect(
                    self._db_signal_conn
                )
            except Exception:
                pass
        self._db_signal_conn = None

        if self._rc_signal_conn and self._replay_controller_ref:
            try:
                self._replay_controller_ref.can_raw_data_batch_received.disconnect(
                    self._rc_signal_conn
                )
            except Exception:
                pass
        self._rc_signal_conn = None

    def load_can_file(self, file_path: str) -> bool:
        """加载CAN数据文件"""
        try:
            self.logger.info(f"开始解析CAN文件: {file_path}")

            # 解析所有通道
            self._all_channel_data, self._vehicle_data = parse_all_channels(file_path)

            # 初始化按IMU分组的原始数据
            self._raw_data_by_imu = {}
            for imu_name, data_list in self._all_channel_data.items():
                self._raw_data_by_imu[imu_name] = data_list

            # 获取统计信息
            stats = get_channel_stats(self._all_channel_data)
            self.logger.info(f"解析完成: {stats}")

            # 更新UI
            self.file_label.setText(os.path.basename(file_path))
            self._update_stats_label(stats)

            # 选择第一个有数据的IMU
            first_imu = None
            for imu_name in ALL_IMU_NAMES:
                if imu_name in self._raw_data_by_imu and self._raw_data_by_imu[imu_name]:
                    first_imu = imu_name
                    break

            if first_imu:
                self._current_channel = first_imu
                index = self.channel_combo.findData(first_imu)
                if index >= 0:
                    self.channel_combo.blockSignals(True)
                    self.channel_combo.setCurrentIndex(index)
                    self.channel_combo.blockSignals(False)

            self.load_btn.setEnabled(True)
            self.stats_label.setText('文件已加载，请选择IMU后点击"加载"')
            self.behavior_timeline._refresh_event_list()

            self.data_loaded.emit(file_path)
            return True

        except Exception as e:
            self.logger.error(f"加载CAN文件失败: {e}")
            QMessageBox.critical(self, "加载失败", f"无法加载文件: {e}")
            return False
            
    def _on_batch_received(self, batch):
        if not batch:
            return
            
        try:
            for record in batch:
                self._process_single_record(record)
                
            if not self.load_btn.isEnabled() and self._raw_data_by_imu:
                self.load_btn.setEnabled(True)
                self.stats_label.setText('数据已接收，请选择IMU后点击"加载"')
            
            total = sum(len(v) for v in self._raw_data_by_imu.values())
            if total % 5000 < len(batch) or total < 100:
                self.logger.debug(f"[CAN全量] 批量接收 {len(batch)} 条, 累计 {total} 条, IMU数: {len(self._raw_data_by_imu)}")

            # 自动加载：收到足够数据后自动加载第一个IMU通道并触发分析
            if total >= 100 and not self._current_data and self._raw_data_by_imu:
                if not hasattr(self, '_auto_load_timer') or self._auto_load_timer is None:
                    self._auto_load_timer = QTimer(self)
                    self._auto_load_timer.setSingleShot(True)
                    self._auto_load_timer.timeout.connect(self._auto_load_first_imu)
                    self._auto_load_timer.start(1500)
                    self.logger.info(f"[CAN全量] 已收到 {total} 条数据，1.5s后将自动加载第一个IMU")
                    
        except Exception as e:
            self.logger.error(f"处理批量数据失败: {e}")

    def _auto_load_first_imu(self):
        """自动加载第一个可用的IMU通道数据并触发行为分析"""
        if self._current_data:
            return  # 已有数据，不重复加载
        if not self._raw_data_by_imu:
            self.logger.warning("_auto_load_first_imu: 无可用IMU数据")
            return

        # 选择第一个有数据的IMU
        first_imu = None
        for imu_name in ALL_IMU_NAMES:
            if imu_name in self._raw_data_by_imu and self._raw_data_by_imu[imu_name]:
                first_imu = imu_name
                break
        if not first_imu:
            # fallback: 取任意有数据的IMU
            for imu_name, data_list in self._raw_data_by_imu.items():
                if data_list:
                    first_imu = imu_name
                    break

        if not first_imu:
            self.logger.warning("_auto_load_first_imu: 没有找到有数据的IMU通道")
            return

        self.logger.info(f"[CAN全量] 自动加载 IMU={first_imu}, 数据={len(self._raw_data_by_imu.get(first_imu, []))} 条")
        self._current_channel = first_imu
        index = self.channel_combo.findData(first_imu)
        if index >= 0:
            self.channel_combo.blockSignals(True)
            self.channel_combo.setCurrentIndex(index)
            self.channel_combo.blockSignals(False)

        # 加载数据到 _current_data
        self._current_data = self._raw_data_by_imu.get(first_imu, [])
        if self._current_data:
            self._displayed_rows = min(DEFAULT_DISPLAY_ROWS, len(self._current_data))
            self._populate_table()
            count = len(self._current_data)
            t_min = self._current_data[0].get('timestamp', 0)
            t_max = self._current_data[-1].get('timestamp', 0)
            self.stats_label.setText(f"{first_imu}: {count}条, 时间范围: {t_min:.3f} - {t_max:.3f}")
            self.load_btn.setEnabled(True)
            self.logger.info(f"[CAN全量] 自动加载完成: {count} 条")

            # 延迟触发批量行为分析
            QTimer.singleShot(200, self._trigger_behavior_analysis)
            
    def _process_single_record(self, record):
        """处理单条数据记录"""
        try:
            source_type = record.get('_source_type', '')
            
            # 处理can_wide格式（多通道）
            if source_type == 'can_wide':
                for ch_idx, imu_name in enumerate(ALL_IMU_NAMES):
                    # 构建对应通道的数据
                    channel_key = f'ch{ch_idx + 1}'
                    ax_key = f'{channel_key}_ax'
                    ay_key = f'{channel_key}_ay'
                    az_key = f'{channel_key}_az'
                    gx_key = f'{channel_key}_gx'
                    gy_key = f'{channel_key}_gy'
                    gz_key = f'{channel_key}_gz'
                    
                    # 检查通道数据是否存在
                    if ax_key in record:
                        imu_record = {
                            'timestamp': record.get('timestamp', 0),
                            'ax': record.get(ax_key, 0),
                            'ay': record.get(ay_key, 0),
                            'az': record.get(az_key, 0),
                            'gx': record.get(gx_key, 0),
                            'gy': record.get(gy_key, 0),
                            'gz': record.get(gz_key, 0),
                            'speed': record.get('speed', 0),
                            'wheel': record.get('steering', record.get('wheel', 0)),
                            '_imu_name': imu_name
                        }
                        
                        # 存储到对应IMU的列表中
                        if imu_name not in self._raw_data_by_imu:
                            self._raw_data_by_imu[imu_name] = []
                        self._raw_data_by_imu[imu_name].append(imu_record)
            
            # 处理can_long格式或标准格式
            else:
                imu_name = record.get('_imu_name', record.get('imu_name', ''))
                if not imu_name:
                    return
                    
                # 确保记录格式标准化
                standardized_record = {
                    'timestamp': record.get('timestamp', record.get('rel_time', 0)),
                    'ax': record.get('ax', record.get('Ax_m_s2', 0)),
                    'ay': record.get('ay', record.get('Ay_m_s2', 0)),
                    'az': record.get('az', record.get('Az_m_s2', 0)),
                    'gx': record.get('gx', record.get('Gx_rad_s', 0)),
                    'gy': record.get('gy', record.get('Gy_rad_s', 0)),
                    'gz': record.get('gz', record.get('Gz_rad_s', 0)),
                    'speed': record.get('speed', record.get('车速_kmh', 0) / 3.6),
                    'wheel': record.get('wheel', record.get('方向盘转角_deg', 0)),
                    '_imu_name': imu_name
                }
                
                if imu_name not in self._raw_data_by_imu:
                    self._raw_data_by_imu[imu_name] = []
                self._raw_data_by_imu[imu_name].append(standardized_record)
                
        except Exception as e:
            self.logger.error(f"处理单条数据失败: {e}")

    def _load_channel_data(self, channel: str):
        """加载指定通道的数据到表格"""
        if channel not in self._raw_data_by_imu:
            self.logger.warning(f"通道 {channel} 无数据")
            self.data_table.setRowCount(0)
            self._current_data = []
            self._displayed_rows = 0
            self._update_display_status()
            return

        self._current_channel = channel
        self._current_data = self._raw_data_by_imu[channel]
        self._displayed_rows = 0

        # 重置表格并填充初始数据
        self.data_table.setRowCount(0)
        self._populate_table(DEFAULT_DISPLAY_ROWS)

        # 更新统计
        self._update_stats_for_current_channel()

    def _on_scroll(self, value):
        """滚动事件处理 - 实现滚动加载"""
        scroll_bar = self.data_table.verticalScrollBar()
        max_value = scroll_bar.maximum()
        
        # 当滚动到接近底部时加载更多数据
        if value >= max_value - 10 and self._displayed_rows < len(self._current_data):
            self._load_more_data()

    def _load_more_data(self):
        """加载更多数据到表格"""
        additional_rows = min(LOAD_INCREMENT, len(self._current_data) - self._displayed_rows)
        if additional_rows > 0:
            start_row = self._displayed_rows
            end_row = start_row + additional_rows
            
            # 添加新行到表格
            for row_idx in range(start_row, end_row):
                self._add_table_row(row_idx)
            
            self._displayed_rows = end_row
            self._update_display_status()
            self.logger.debug(f"已加载更多数据: 显示 {self._displayed_rows}/{len(self._current_data)} 行")

    def _populate_table(self, num_rows=None):
        """填充数据表格"""
        if num_rows is None:
            num_rows = len(self._current_data)
        
        display_count = min(num_rows, len(self._current_data))
        self.data_table.setRowCount(display_count)

        for row_idx in range(display_count):
            self._add_table_row(row_idx)
            
        self._displayed_rows = display_count
        self._update_display_status()

    def _add_table_row(self, row_idx):
        """添加单行数据到表格"""
        if row_idx >= len(self._current_data):
            return
            
        record = self._current_data[row_idx]
        
        for col_idx, (key, _, _) in enumerate(TABLE_COLUMNS):
            value = record.get(key, "")
            item = QTableWidgetItem()

            # 格式化数值
            if isinstance(value, float):
                if key in ['timestamp', 'speed', 'wheel']:
                    item.setText(f"{value:.3f}")
                else:
                    item.setText(f"{value:.6f}")
            else:
                item.setText(str(value))

            # 检查是否需要高亮
            if self._highlight_time_range:
                t_start, t_end = self._highlight_time_range
                timestamp = record.get('timestamp', 0)
                if t_start <= timestamp <= t_end:
                    item.setBackground(QBrush(QColor(30, 60, 100)))

            self.data_table.setItem(row_idx, col_idx, item)

    def _update_table_display(self):
        """更新表格显示（当有新数据时）"""
        if self._current_channel not in self._raw_data_by_imu:
            return
            
        self._current_data = self._raw_data_by_imu[self._current_channel]
        
        # 如果当前显示的行数少于实际数据行数，添加新数据
        if self._displayed_rows < len(self._current_data):
            # 添加新增的数据行
            for row_idx in range(self._displayed_rows, min(self._displayed_rows + 10, len(self._current_data))):
                self._add_table_row(row_idx)
                self._displayed_rows = row_idx + 1
            self._update_display_status()

    def _update_display_status(self):
        """更新显示状态标签"""
        total = len(self._current_data) if hasattr(self, '_current_data') else 0
        self.display_status_label.setText(f"显示: {self._displayed_rows} / {total} 行")

    def _update_stats_label(self, stats: Dict[str, Any]):
        """更新统计标签"""
        parts = []
        for imu_name in ALL_IMU_NAMES:
            if imu_name in stats:
                count = stats[imu_name]['count']
                parts.append(f"{imu_name.split('_')[0]}: {count}条")

        text = " | ".join(parts)
        self.stats_label.setText(text)

    def _update_stats_for_current_channel(self):
        """更新当前IMU的统计信息"""
        count = len(self._current_data)
        if count > 0:
            t_min = self._current_data[0]['timestamp']
            t_max = self._current_data[-1]['timestamp']
            self.stats_label.setText(
                f"{self._current_channel}: {count}条, 时间范围: {t_min:.3f} - {t_max:.3f}"
            )

        # 更新事件统计
        event_count = self._distributor.get_event_count()
        self.event_stats_label.setText(f"事件: {event_count}")

    def highlight_event_time_range(self, event_id: int, start_ts: float, end_ts: float):
        """高亮事件时间区间的数据"""
        self._highlight_time_range = (start_ts, end_ts)
        self._populate_table()
        self.clear_highlight_btn.setEnabled(True)
        self.export_event_btn.setEnabled(True)

        # 滚动到第一条匹配的记录
        for row_idx, record in enumerate(self._current_data):
            if record['timestamp'] >= start_ts:
                self.data_table.scrollToItem(self.data_table.item(row_idx, 0))
                break

    def _clear_highlight(self):
        """清除高亮"""
        self._highlight_time_range = None
        self._populate_table()
        self.clear_highlight_btn.setEnabled(False)
        self.export_event_btn.setEnabled(False)

    def _update_event_stats(self):
        """更新事件统计"""
        event_count = self._distributor.get_event_count()
        self.event_stats_label.setText(f"事件: {event_count}")

    def _trigger_behavior_analysis(self):
        """数据加载后自动触发 22 种 DrivingEventDetector 批量分析并注册到 EventDistributor"""
        if not self._data_bridge or not self._current_data:
            return
        if self._data_bridge.is_batch_analyzed:
            self.logger.debug("批量分析已完成，跳过")
            return

        try:
            # 准备记录：确保每条记录有 rel_time, speed, wheel, channel, imu_name
            records = []
            for r in self._current_data:
                # 构建标准化记录（与 data_bridge.analyze_behavior_batch 兼容）
                rec = dict(r)
                if 'rel_time' not in rec and 'timestamp' in rec:
                    rec['rel_time'] = rec['timestamp']
                if 'wheel' not in rec and '方向盘转角_deg' in rec:
                    rec['wheel'] = rec['方向盘转角_deg']
                if 'speed' not in rec and '车速_kmh' in rec:
                    rec['speed'] = rec['车速_kmh']
                records.append(rec)

            if len(records) < 10:
                self.logger.warning(f"触发行为分析：数据不足 ({len(records)} 条)")
                return

            channel = self._current_channel or 'ch1'
            imu = channel  # channel 名称即 IMU 名称

            self.logger.info(
                f"触发 22 种 DrivingEventDetector 批量分析: "
                f"{len(records)} 条, channel=ch1, imu={imu}"
            )
            self.event_stats_label.setText(f"事件: 分析中...")

            result = self._data_bridge.analyze_behavior_batch(
                records, ref_channel='ch1', ref_imu=imu  # ← P2修复: ref_channel固定为'ch1'
            )
            events = result.get('events', [])
            raw_events = result.get('raw_events', [])
            self.logger.info(
                f"批量分析完成: {len(events)} 个事件, "
                f"accel_range={result.get('vehicle_accel_range')}"
            )

            # 注册到 EventDistributor（需要 ManeuverEvent 对象）
            if raw_events:
                self._distributor.register_events(raw_events)

            # 刷新 UI
            self._update_event_stats()
            if hasattr(self, 'behavior_timeline') and self.behavior_timeline:
                self.behavior_timeline._refresh_event_list()

            # 更新回放栏事件列表
            main = self._find_main_window()
            if main and hasattr(main, 'right_tab') and main.right_tab:
                if hasattr(main.right_tab, 'replay_bar') and main.right_tab.replay_bar:
                    try:
                        main.right_tab.replay_bar.set_events(events)
                    except Exception:
                        pass

                # 同步22种精确事件到实时行为监控tab的BehaviorTimelineView
                if hasattr(main.right_tab, 'real_time_monitoring_tab') and main.right_tab.real_time_monitoring_tab:
                    rt_tab = main.right_tab.real_time_monitoring_tab
                    if hasattr(rt_tab, 'timeline_view') and rt_tab.timeline_view:
                        try:
                            rt_tab.timeline_view.sync_from_distributor()
                            self.logger.info("已同步22种事件到实时行为监控时间轴")
                        except Exception as e:
                            self.logger.warning(f"同步实时行为监控时间轴失败: {e}")

        except Exception as e:
            self.logger.error(f"触发行为分析失败: {e}", exc_info=True)

    def _find_main_window(self):
        """查找主窗口引用"""
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'right_tab'):
                return widget
        return None

    def _on_load_file(self):
        """加载文件按钮点击"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择CAN数据文件",
            "",
            "CAN数据文件 (*.txt *.csv);;所有文件 (*.*)"
        )
        if file_path:
            self.load_can_file(file_path)

    def _on_load_imu_data(self):
        channel = self.channel_combo.currentData()
        if not channel:
            QMessageBox.warning(self, "提示", "请先选择IMU通道")
            return

        if self._cache:
            try:
                can_types = [st for st in self._cache.get_source_types() if st in ('can_wide', 'can_long')]
                cache_count = sum(self._cache.count_by_source_type(st) for st in can_types)
            except Exception as e:
                self.logger.error(f"查询缓存失败: {e}")
                cache_count = 0

            mem_count = sum(len(v) for v in self._raw_data_by_imu.values())
            if cache_count > mem_count:
                self.logger.info(f"缓存({cache_count}条) > 内存({mem_count}条)，从缓存加载...")
                self.stats_label.setText('正在从缓存加载完整数据...')
                QApplication.processEvents()
                self._raw_data_by_imu.clear()
                self._total_received = 0
                if self._load_from_cache():
                    self._refresh_imu_combo()

        if not self._raw_data_by_imu:
            QMessageBox.warning(self, "提示", "暂无数据。请先在左侧面板加载CAN数据源，等待解析完成后重试。")
            return

        if channel not in self._raw_data_by_imu or not self._raw_data_by_imu[channel]:
            available = list(self._raw_data_by_imu.keys())
            QMessageBox.warning(self, "提示", f"IMU {channel} 无数据。\n可用IMU: {available}")
            return

        self._current_channel = channel
        self._current_data = self._raw_data_by_imu[channel]
        self._displayed_rows = 0
        self._highlight_time_range = None
        self.clear_highlight_btn.setEnabled(False)
        self.export_event_btn.setEnabled(False)

        self.data_table.setRowCount(0)
        self._populate_table(DEFAULT_DISPLAY_ROWS)
        self._update_stats_for_current_channel()
        self._update_event_stats()
        self.behavior_timeline._refresh_event_list()

        self.logger.info(f"已加载IMU {channel} 数据: {self._displayed_rows}/{len(self._current_data)} 行")

        # 自动触发 22 种 DrivingEventDetector 批量分析
        if self._data_bridge:
            QTimer.singleShot(100, self._trigger_behavior_analysis)

    def _refresh_imu_combo(self):
        current = self.channel_combo.currentData()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        for imu_name in sorted(self._raw_data_by_imu.keys()):
            self.channel_combo.addItem(imu_name, imu_name)
        if current and self.channel_combo.findData(current) >= 0:
            self.channel_combo.setCurrentIndex(self.channel_combo.findData(current))
        self.channel_combo.blockSignals(False)

    def _on_export_current(self):
        """导出当前通道数据"""
        if not self._current_data:
            QMessageBox.warning(self, "提示", "当前通道无数据可导出")
            return

        # 使用简单的文件名
        safe_name = self._current_channel.replace(' ', '_').replace('-', '_')
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出CSV",
            f"{safe_name}_data_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV文件 (*.csv)"
        )
        if file_path:
            self._export_csv(file_path, self._current_data)

    def _on_export_all(self):
        """导出所有通道数据"""
        if not self._all_channel_data:
            QMessageBox.warning(self, "提示", "无数据可导出")
            return

        dir_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if dir_path:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            for imu_name, data in self._all_channel_data.items():
                if data:
                    safe_name = imu_name.replace(' ', '_').replace('-', '_')
                    file_path = os.path.join(dir_path, f"{safe_name}_data_{timestamp}.csv")
                    self._export_csv(file_path, data)
            QMessageBox.information(self, "完成", "所有通道数据已导出")

    def _on_export_event_data(self):
        """导出事件区间数据"""
        if not self._highlight_time_range:
            QMessageBox.warning(self, "提示", "请先点击一个事件以选择时间区间")
            return

        if not self._current_data:
            QMessageBox.warning(self, "提示", "无数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出事件区间数据",
            f"event_data_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV文件 (*.csv)"
        )
        if file_path:
            t_start, t_end = self._highlight_time_range
            event_data = [
                r for r in self._current_data
                if t_start <= r['timestamp'] <= t_end
            ]
            self._export_csv(file_path, event_data)

    def _export_csv(self, file_path: str, data: List[Dict]):
        """导出CSV文件"""
        try:
            headers = [col[0] for col in TABLE_COLUMNS]

            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for record in data:
                    row = {k: record.get(k, '') for k in headers}
                    writer.writerow(row)

            self.logger.info(f"已导出 {len(data)} 条记录 → {file_path}")
            QMessageBox.information(self, "完成", f"已导出 {len(data)} 条记录")
            self.export_completed.emit(file_path)

        except Exception as e:
            self.logger.error(f"导出失败: {e}")
            QMessageBox.critical(self, "失败", f"导出失败: {e}")

    def receive_event(self, event):
        """接收事件"""
        pass

    def receive_can_data(self, sensor_data):
        """接收实时CAN数据"""
        if sensor_data:
            self._process_single_record(sensor_data)

    def set_data_bridge(self, data_bridge):
        """设置数据桥接（存储引用，由 set_data_source_mode 管理连接）"""
        self._data_bridge = data_bridge
        # 默认连接流式数据
        if data_bridge is not None:
            self.set_data_source_mode(DataSourceMode.STREAMING)

    def set_replay_controller_ref(self, controller):
        """设置回放控制器引用（不自动连接，由 set_data_source_mode 管理）"""
        self._replay_controller_ref = controller

    def set_cache(self, cache):
        """设置磁盘缓存引用，用于直接从缓存加载数据"""
        self._cache = cache
        self.logger.info(f"MultiSourceCache 已注入到CAN全量解析标签页")

    def _load_from_cache(self):
        """从磁盘缓存加载全量CAN数据到内存"""
        if not self._cache:
            self.logger.warning("缓存未设置，无法加载数据")
            return False

        try:
            source_types = self._cache.get_source_types()
            self.logger.info(f"缓存中可用数据源类型: {source_types}")

            can_types = [st for st in source_types if st in ('can_wide', 'can_long')]
            if not can_types:
                self.logger.warning(f"缓存中无CAN数据类型，可用类型: {source_types}")
                return False

            total_loaded = 0
            for st in can_types:
                count = self._cache.count_by_source_type(st)
                self.logger.info(f"从缓存加载 {st} 数据: 共 {count} 条")

                batch_size = 5000
                for offset in range(0, count, batch_size):
                    records = self._cache.query_by_source_type(st, limit=batch_size, offset=offset)
                    for record in records:
                        self._process_single_record(record)
                    total_loaded += len(records)

                    if offset == 0 or (offset + batch_size) % 50000 < batch_size:
                        self.logger.info(f"[CAN全量] 缓存加载进度: {min(offset + batch_size, count)}/{count}")

            self.logger.info(f"从缓存加载完成: 共 {total_loaded} 条, IMU数: {len(self._raw_data_by_imu)}")

            if self._raw_data_by_imu:
                self.load_btn.setEnabled(True)
                total = sum(len(v) for v in self._raw_data_by_imu.values())
                self.stats_label.setText(f'缓存数据已加载: {total} 条记录, {len(self._raw_data_by_imu)} 个IMU通道')
                self.file_label.setText('从缓存加载')
                self.behavior_timeline._refresh_event_list()
                return True
            else:
                self.stats_label.setText('缓存中无有效IMU数据')
                return False

        except Exception as e:
            self.logger.error(f"从缓存加载数据失败: {e}")
            return False

    def clear_data(self):
        """清除数据"""
        self._all_channel_data = {}
        self._vehicle_data = {}
        self._current_data = []
        self._raw_data_by_imu = {}
        self._displayed_rows = 0
        self._highlight_time_range = None
        self.data_table.setRowCount(0)
        self.file_label.setText("未加载数据文件")
        self.stats_label.setText("就绪 - 请加载数据文件")
        self.display_status_label.setText("显示: 0 / 0 行")
        self.load_btn.setEnabled(False)
        self.clear_highlight_btn.setEnabled(False)
        self.export_event_btn.setEnabled(False)
        self.behavior_timeline._clear_events()


CANFullParsingTab = EnhancedCANFullParsingTab
