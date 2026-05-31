#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照分析面板UI组件 - 卡片式紧凑布局
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QSplitter,
    QScrollArea, QGridLayout, QComboBox, QCheckBox,
    QProgressBar, QHeaderView, QFrame, QTabWidget, QSizePolicy,
    QDialog, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

from core.core.seat_evaluation.metadata_registry import INDICATOR_DEFINITIONS, get_global_registry
from core.core.seat_evaluation.imu_location_config import (
    get_all_locations, LOCATION_NAMES
)

LC = {
    'bg_primary': '#FFFFFF', 'bg_card': '#FFFFFF', 'bg_input': '#F5F6F8',
    'bg_header': '#EBEDF0', 'bg_hover': '#E8F0FE',
    'accent': '#4A90D9', 'accent_hover': '#357ABD',
    'accent_light': 'rgba(74,144,217,0.10)',
    'text_primary': '#333333', 'text_secondary': '#666666',
    'text_muted': '#999999', 'text_accent': '#4A90D9',
    'border_default': '#D0D0D0', 'border_light': '#E0E0E0',
    'success': '#27AE60', 'warning': '#F39C12', 'danger': '#E74C3C',
    'info': '#4A90D9',
}

CARD_STYLE = """
    QFrame#proCard {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 6px;
    }
"""


class IndicatorDetailDialog(QDialog):
    """指标详情对话框 — 与实例视图保持一致的结构化展示"""

    def __init__(self, indicator_code: str, registry, parent=None):
        super().__init__(parent)
        self._indicator_code = indicator_code
        self._registry = registry
        self._meta = registry.get_indicator_meta(indicator_code)
        self._detail = registry.get_indicator_detail(indicator_code)
        self._threshold = registry.get_threshold(indicator_code)
        self.setWindowTitle(f"指标详情 — {self._meta.display_name_cn if self._meta else indicator_code}")
        self.setMinimumSize(650, 440)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(8)
        if not self._meta:
            cl.addWidget(QLabel("未找到指标元数据"))
        else:
            cl.addWidget(self._build_basic_info())
            cl.addWidget(self._build_formula())
            cl.addWidget(self._build_pipeline())
            cl.addWidget(self._build_threshold())
        scroll.setWidget(content)
        layout.addWidget(scroll)
        cb = QPushButton("关闭")
        cb.clicked.connect(self.close)
        layout.addWidget(cb)

    def _card(self) -> QFrame:
        c = QFrame()
        c.setObjectName("proCard")
        c.setStyleSheet(CARD_STYLE)
        return c

    def _build_basic_info(self) -> QFrame:
        card = self._card()
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        l.setSpacing(3)
        t = QLabel("基本信息")
        t.setStyleSheet(f"font-size:11px;font-weight:700;color:{LC['text_primary']};padding-bottom:3px;border-bottom:1px solid {LC['border_light']};")
        l.addWidget(t)
        html = (
            f"<table style='font-size:10px;width:100%;'>"
            f"<tr><td style='color:{LC['text_muted']};width:80px;'>编码</td><td style='color:{LC['text_accent']};font-weight:600;'>{self._meta.indicator_code}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>中文名</td><td>{self._meta.display_name_cn}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>维度</td><td>{self._meta.evaluation_dimension}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>位置</td><td>{', '.join(self._meta.applicable_locations)}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>单位/精度</td><td>{self._meta.unit} / {self._meta.precision}位</td></tr>"
            f"</table>"
        )
        lb = QLabel(html)
        lb.setWordWrap(True)
        l.addWidget(lb)
        if self._meta.standard_refs:
            refs = "<br>".join([f"• {r}" for r in self._meta.standard_refs])
            rl = QLabel(f"<div style='font-size:9px;color:{LC['text_muted']};margin-top:4px;border-top:1px solid {LC['border_light']};padding-top:3px;'><b>标准:</b><br>{refs}</div>")
            rl.setWordWrap(True)
            l.addWidget(rl)
        return card

    def _build_formula(self) -> QFrame:
        card = self._card()
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        t = QLabel("计算公式")
        t.setStyleSheet(f"font-size:11px;font-weight:700;color:{LC['text_primary']};padding-bottom:3px;border-bottom:1px solid {LC['border_light']};")
        l.addWidget(t)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setStyleSheet("font-family:Consolas,Microsoft YaHei;font-size:10px;background:#1E1E1E;color:#D4D4D4;border-radius:3px;")
        te.setMinimumHeight(50)
        txt = f"{self._meta.formula_text}\nLaTeX: {self._meta.formula_latex}"
        if self._detail:
            txt += f"\n\n计算逻辑: {self._detail.calculation_logic}"
            txt += f"\n推导: {self._detail.formula_detail}"
        te.setText(txt)
        l.addWidget(te)
        return card

    def _build_pipeline(self) -> QFrame:
        card = self._card()
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        t = QLabel("算子管线")
        t.setStyleSheet(f"font-size:11px;font-weight:700;color:{LC['text_primary']};padding-bottom:3px;border-bottom:1px solid {LC['border_light']};")
        l.addWidget(t)
        pipe = f"<div style='font-size:10px;padding:4px;background:{LC['bg_input']};border-radius:3px;'><b>管线:</b> {' → '.join(self._meta.operator_pipeline)}"
        if self._detail and self._detail.operator_pipeline_detail:
            pipe += f"<br><br><b>详情:</b><br>{self._detail.operator_pipeline_detail}"
        pipe += "</div>"
        if self._detail and self._detail.data_fields:
            pipe += f"<div style='font-size:9px;color:{LC['text_muted']};margin-top:4px;padding:3px;background:{LC['bg_input']};border-radius:3px;'><b>数据字段:</b> {self._detail.data_fields}</div>"
        lb = QLabel(pipe)
        lb.setWordWrap(True)
        l.addWidget(lb)
        return card

    def _build_threshold(self) -> QFrame:
        card = self._card()
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        t = QLabel("阈值判定")
        t.setStyleSheet(f"font-size:11px;font-weight:700;color:{LC['text_primary']};padding-bottom:3px;border-bottom:1px solid {LC['border_light']};")
        l.addWidget(t)
        pv = self._meta.threshold_pass or (self._threshold.get('pass') if self._threshold else '-')
        wv = (self._threshold.get('warn') if self._threshold else '-')
        ev = self._meta.threshold_excellent or '-'
        html = (
            f"<table style='font-size:10px;width:100%;'>"
            f"<tr><td style='color:{LC['text_muted']};width:80px;'>通过(pass)</td><td style='color:{LC['success']};font-weight:600;'>{pv}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>警告(warn)</td><td>{wv}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>优秀基线</td><td>{ev}</td></tr>"
            f"<tr><td style='color:{LC['text_muted']}'>方向</td><td>{self._meta.evaluation_direction.name}</td></tr>"
            f"</table>"
        )
        lb = QLabel(html)
        lb.setWordWrap(True)
        l.addWidget(lb)
        return card


class ComparativeEvaluationTab(QWidget):
    """对照分析面板 - 卡片式紧凑布局"""
    
    comparison_requested = Signal(dict)  # 请求对照分析
    export_report_requested = Signal()   # 导出对照报告
    
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.comparison_engine = None
        self._data_bridge = None
        self._replay_controller = None
        self._registry = get_global_registry()
        self._comparison_results = []
        self._current_result = None
        self._init_ui()
        self.logger.info("对照分析面板已初始化")
    
    def _init_ui(self):
        """初始化UI布局 - 卡片式紧凑布局"""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet(
            "QScrollArea { background: #F0F2F5; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #C0C4CC; border-radius: 3px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: #909399; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        outer_layout.addWidget(self._scroll_area)

        content = QWidget()
        self._content_widget = content
        content.setSizePolicy(QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred))

        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # 顶部控制卡片
        control_card = self._create_control_card()
        main_layout.addWidget(control_card)
        
        # 主要内容区域
        splitter = QSplitter(Qt.Vertical)
        splitter.setContentsMargins(0, 0, 0, 0)
        
        # 各位置对比卡片
        location_card = self._create_location_card()
        splitter.addWidget(location_card)
        
        # 指标对比表格卡片
        comparison_card = self._create_comparison_card()
        splitter.addWidget(comparison_card)
        
        # 详细分析标签页卡片
        detail_card = self._create_detail_card()
        splitter.addWidget(detail_card)
        
        # 历史对比记录卡片
        history_card = self._create_history_card()
        splitter.addWidget(history_card)

        splitter.setSizes([80, 500, 150, 100])
        main_layout.addWidget(splitter)

        self._scroll_area.setWidget(content)
    
    def _create_control_card(self) -> QFrame:
        """创建控制卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("⚖️ 对照分析控制")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # 实验组选择
        layout.addWidget(QLabel("实验组:"))
        self.exp_combo = QComboBox()
        self.exp_combo.addItem("当前数据（实验组）", "current_experimental")
        self.exp_combo.setMaximumWidth(180)
        layout.addWidget(self.exp_combo)
        
        layout.addSpacing(8)
        
        # 对照组选择
        layout.addWidget(QLabel("对照组:"))
        self.ctrl_combo = QComboBox()
        self.ctrl_combo.addItem("当前数据（对照组）", "current_control")
        self.ctrl_combo.setMaximumWidth(180)
        layout.addWidget(self.ctrl_combo)
        
        layout.addSpacing(8)
        
        # 位置选择
        layout.addWidget(QLabel("查看位置:"))
        self.location_combo = QComboBox()
        self.location_combo.addItem("总体")
        locations = get_all_locations()
        for loc_id in locations:
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            self.location_combo.addItem(loc_name, loc_id)
        self.location_combo.currentIndexChanged.connect(self._on_location_changed)
        self.location_combo.setMaximumWidth(150)
        layout.addWidget(self.location_combo)
        
        layout.addStretch()
        
        # 操作按钮
        self.compare_btn = QPushButton("🔄 开始对比")
        self.compare_btn.setObjectName("btnSmall")
        self.compare_btn.clicked.connect(self._on_start_comparison)
        layout.addWidget(self.compare_btn)
        
        layout.addSpacing(8)
        
        self.export_btn = QPushButton("📤 导出报告")
        self.export_btn.setObjectName("btnSmallOutline")
        self.export_btn.clicked.connect(self._on_export_report)
        layout.addWidget(self.export_btn)
        
        return card
    
    def _create_summary_card(self) -> QFrame:
        """创建总结卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(20)
        
        # 实验组评分
        exp_layout = self._create_group_score_card("实验组", "#4A90D9")
        layout.addLayout(exp_layout, 1)
        
        # 分隔线
        separator = QFrame()
        separator.setObjectName("separatorV")
        layout.addWidget(separator)
        
        # 改进度显示
        improvement_layout = self._create_improvement_card()
        layout.addLayout(improvement_layout, 1)
        
        # 分隔线
        separator2 = QFrame()
        separator2.setObjectName("separatorV")
        layout.addWidget(separator2)
        
        # 对照组评分
        ctrl_layout = self._create_group_score_card("对照组", "#9E9E9E")
        layout.addLayout(ctrl_layout, 1)
        
        return card
    
    def _create_group_score_card(self, title, color):
        """创建组评分卡片"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel(f"{title}")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("panelTitle")
        
        # 评分显示
        score_label = QLabel("--")
        score_label.setAlignment(Qt.AlignCenter)
        score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 42px;
                font-weight: 800;
                color: {color};
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        
        # 评分进度条
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setMinimumHeight(16)
        
        # 存储引用
        if title == "实验组":
            self.exp_score_label = score_label
            self.exp_score_progress = progress
        else:
            self.ctrl_score_label = score_label
            self.ctrl_score_progress = progress
        
        layout.addWidget(title_label)
        layout.addWidget(score_label)
        layout.addWidget(progress)
        
        return layout
    
    def _create_improvement_card(self):
        """创建改进度卡片"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("📈 改进度")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("panelTitle")
        
        # 改进度显示
        self.improvement_label = QLabel("--")
        self.improvement_label.setAlignment(Qt.AlignCenter)
        self.improvement_label.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: 800;
                color: #4CAF50;
                padding: 20px;
            }
        """)
        
        # 改进指标统计
        self.improvement_stats = QLabel("改进: -- | 持平: -- | 下降: --")
        self.improvement_stats.setAlignment(Qt.AlignCenter)
        self.improvement_stats.setObjectName("statLabel")
        
        layout.addWidget(title_label)
        layout.addWidget(self.improvement_label)
        layout.addWidget(self.improvement_stats)
        
        return layout
    
    def _create_location_card(self) -> QFrame:
        """创建位置对比卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("📍 各位置对比")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        
        # 创建滚动区域容纳所有位置
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        # 位置对比网格
        self.location_comparison_container = QWidget()
        self.location_comparison_layout = QGridLayout(self.location_comparison_container)
        self.location_comparison_layout.setSpacing(12)
        self.location_comparison_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建每个位置的对比卡片
        locations = get_all_locations()
        self.location_comparison_widgets = {}
        
        for idx, loc_id in enumerate(locations):
            loc_name = LOCATION_NAMES.get(loc_id, loc_id)
            loc_card = self._create_location_comparison_card(loc_id, loc_name)
            row = idx // 3
            col = idx % 3
            self.location_comparison_layout.addWidget(loc_card, row, col)
            self.location_comparison_widgets[loc_id] = loc_card
        
        scroll.setWidget(self.location_comparison_container)
        layout.addWidget(scroll)
        
        return card
    
    def _create_location_comparison_card(self, loc_id: str, loc_name: str) -> QFrame:
        """创建单个位置的对比卡片"""
        card = QFrame()
        card.setObjectName("miniCard")
        card.setMinimumHeight(120)
        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 位置名称
        name_label = QLabel(f"📍 {loc_name}")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setObjectName("miniCardTitle")
        
        # 实验组评分
        exp_score_label = QLabel("--")
        exp_score_label.setAlignment(Qt.AlignCenter)
        exp_score_label.setStyleSheet("font-size: 18px; color: #2196F3; font-weight: 700;")
        exp_score_label.setObjectName(f"exp_score_{loc_id}")
        
        # vs
        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignCenter)
        vs_label.setStyleSheet("font-size: 12px; color: #9E9E9E;")
        
        # 对照组评分
        ctrl_score_label = QLabel("--")
        ctrl_score_label.setAlignment(Qt.AlignCenter)
        ctrl_score_label.setStyleSheet("font-size: 18px; color: #9E9E9E; font-weight: 700;")
        ctrl_score_label.setObjectName(f"ctrl_score_{loc_id}")
        
        # 改进度
        improvement_label = QLabel("--")
        improvement_label.setAlignment(Qt.AlignCenter)
        improvement_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        improvement_label.setObjectName(f"improvement_{loc_id}")
        
        layout.addWidget(name_label)
        layout.addWidget(exp_score_label)
        layout.addWidget(vs_label)
        layout.addWidget(ctrl_score_label)
        layout.addWidget(improvement_label)
        
        return card
    
    def _create_comparison_card(self) -> QFrame:
        """创建对比卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("📊 指标对比")
        title.setObjectName("panelTitle")
        title_layout.addWidget(title)
        
        # 位置标签说明
        self.location_comparison_label = QLabel("当前位置: 总体")
        self.location_comparison_label.setObjectName("statValueAccent")
        title_layout.addWidget(self.location_comparison_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 创建对比表格
        self.comparison_table = QTableWidget()
        self.comparison_table.setObjectName("syncSourcesTable")
        self.comparison_table.setColumnCount(10)
        self.comparison_table.setHorizontalHeaderLabels([
            "指标ID", "指标名称", "评测维度", "单位",
            "实验组值", "对照组值",
            "绝对差", "相对差", "改进方向", "操作"
        ])

        header = self.comparison_table.horizontalHeader()
        header.setObjectName("syncSourcesHeader")
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for i in range(3, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        self.comparison_table.setColumnWidth(9, 52)
        
        # 填充指标数据
        self._populate_comparison_table()
        
        layout.addWidget(self.comparison_table)

        self.comparison_table.cellClicked.connect(self._on_comparison_cell_clicked)

        refs_card = self._create_standards_reference_card()
        layout.addWidget(refs_card)

        return card

    def _create_detail_card(self) -> QFrame:
        """创建详细卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("🔍 详细分析")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        
        # 创建标签页
        self.detail_tabs = QTabWidget()
        
        # 图表分析标签页
        chart_tab = QWidget()
        chart_layout = QVBoxLayout(chart_tab)
        chart_layout.addWidget(QLabel("图表分析区域"))
        self.detail_tabs.addTab(chart_tab, "📈 图表分析")
        
        # 统计分析标签页
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        stats_layout.addWidget(QLabel("统计分析区域"))
        self.detail_tabs.addTab(stats_tab, "📊 统计分析")
        
        # 事件详情标签页
        event_tab = QWidget()
        event_layout = QVBoxLayout(event_tab)
        event_layout.addWidget(QLabel("事件详情区域"))
        self.detail_tabs.addTab(event_tab, "📝 事件详情")
        
        layout.addWidget(self.detail_tabs)
        
        return card
    
    def _create_history_card(self) -> QFrame:
        """创建历史记录卡片"""
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("📚 对比历史")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setObjectName("syncSourcesTable")
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "实验组", "对照组", 
            "实验组分", "对照组分", "改进度", "详情"
        ])
        
        header = self.history_table.horizontalHeader()
        header.setObjectName("syncSourcesHeader")
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.history_table)
        
        return card
    
    def _populate_comparison_table(self):
        """填充对比表格 — 按评测维度分组，使用 registry 元数据"""
        dimension_order = {
            '瞬态-冲击': 0, '稳态-隔振': 1, '稳态-舒适度': 2,
            '动态-响应': 3, '疲劳-损伤': 4, '时频-分析': 5,
            '频域-特性': 6, '位移-衰减': 7, '生物力学': 8, '通用-基础': 9,
        }

        grouped = {}
        for code, meta in self._registry.indicators.items():
            dim = meta.evaluation_dimension
            grouped.setdefault(dim, []).append(meta)
        for indicators in grouped.values():
            indicators.sort(key=lambda m: m.indicator_code)

        rows = []
        for dim in sorted(grouped.keys(), key=lambda d: dimension_order.get(d, 99)):
            for meta in grouped[dim]:
                rows.append(meta)

        self.comparison_table.setRowCount(len(rows))
        self._indicator_row_map = {}

        for row, meta in enumerate(rows):
            code_item = QTableWidgetItem(meta.indicator_code)
            code_item.setTextAlignment(Qt.AlignCenter)
            self.comparison_table.setItem(row, 0, code_item)

            name_item = QTableWidgetItem(meta.display_name_cn)
            name_item.setTextAlignment(Qt.AlignCenter)
            refs_text = ', '.join([str(r) for r in meta.standard_refs[:3]])
            tip_lines = [
                f"{meta.display_name_cn} ({meta.display_name_en})",
                f"单位: {meta.unit}",
                f"公式: {meta.formula_text}",
                f"管线: {' → '.join(meta.operator_pipeline)}",
                f"适用位置: {', '.join(meta.applicable_locations)}",
            ]
            if refs_text:
                tip_lines.append(f"标准: {refs_text}")
            if meta.threshold_pass:
                tip_lines.append(f"通过阈值: {meta.threshold_pass}")
            name_item.setToolTip('\n'.join(tip_lines))
            self.comparison_table.setItem(row, 1, name_item)

            dim_item = QTableWidgetItem(meta.evaluation_dimension)
            dim_item.setTextAlignment(Qt.AlignCenter)
            dim_colors = {
                '瞬态-冲击': '#E74C3C', '稳态-隔振': '#4A90D9',
                '稳态-舒适度': '#4A90D9', '动态-响应': '#27AE60',
                '疲劳-损伤': '#F39C12', '时频-分析': '#9B59B6',
                '频域-特性': '#9B59B6', '位移-衰减': '#2ECC71',
                '生物力学': '#2ECC71', '通用-基础': '#95A5A6',
            }
            dim_color = dim_colors.get(meta.evaluation_dimension, '#95A5A6')
            dim_item.setForeground(QColor(dim_color))
            self.comparison_table.setItem(row, 2, dim_item)

            unit_item = QTableWidgetItem(meta.unit if meta.unit != '-' else '')
            unit_item.setTextAlignment(Qt.AlignCenter)
            self.comparison_table.setItem(row, 3, unit_item)

            self.comparison_table.setItem(row, 4, QTableWidgetItem("--"))
            self.comparison_table.setItem(row, 5, QTableWidgetItem("--"))
            self.comparison_table.setItem(row, 6, QTableWidgetItem("--"))
            self.comparison_table.setItem(row, 7, QTableWidgetItem("--"))
            self.comparison_table.setItem(row, 8, QTableWidgetItem("--"))

            detail_btn = QPushButton("详情")
            detail_btn.setFixedSize(45, 24)
            detail_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {LC['text_accent']};
                    border: 1px solid {LC['border_default']}; border-radius: 3px;
                    font-size: 9px; padding: 1px 2px;
                }}
                QPushButton:hover {{
                    background: {LC['accent_light']}; border-color: {LC['accent']};
                }}
            """)
            code = meta.indicator_code
            detail_btn.clicked.connect(
                lambda checked=False, c=code: self._open_indicator_detail(c)
            )
            self.comparison_table.setCellWidget(row, 9, detail_btn)

            self._indicator_row_map[meta.indicator_code] = row

    def _on_comparison_cell_clicked(self, row: int, col: int):
        if col != 1 and col != 0:
            return
        code_item = self.comparison_table.item(row, 0)
        if not code_item:
            return
        code = code_item.text()
        if col == 1:
            self._open_indicator_detail(code)
        else:
            self._open_indicator_detail(code)

    def _open_indicator_detail(self, indicator_code: str):
        dialog = IndicatorDetailDialog(indicator_code, self._registry, self)
        dialog.exec()

    def _create_standards_reference_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("proCard")
        card.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title = QLabel("标准引用总览")
        title.setStyleSheet(f"color: {LC['text_primary']}; font-size: 13px; font-weight: 700; background: transparent;")
        layout.addWidget(title)

        refs_by_standard = {}
        for ref_code, ref_data in self._registry.standard_references.items():
            refs_by_standard.setdefault(ref_code, []).extend(ref_data.get('indicators', []))

        text_parts = []
        for ref_code, indicator_list in refs_by_standard.items():
            ref_data = self._registry.standard_references.get(ref_code, {})
            name = ref_data.get('standard_name', ref_data.get('name', ref_code))
            desc = ref_data.get('description', ref_data.get('desc', ''))
            text_parts.append(f"{name} ({ref_code}): {desc}  — 适用指标: {', '.join(indicator_list[:6])}")
            if len(indicator_list) > 6:
                text_parts[-1] += f" (+{len(indicator_list) - 6})"

        refs_text = QLabel('\n'.join(text_parts) if text_parts else "暂无标准引用数据")
        refs_text.setWordWrap(True)
        refs_text.setStyleSheet(f"color: {LC['text_muted']}; font-size: 10px; background: transparent; padding: 4px;")
        layout.addWidget(refs_text)

        return card

    def set_comparison_engine(self, engine):
        """设置对照分析引擎"""
        self.comparison_engine = engine
        if engine:
            engine.comparison_started.connect(self._on_comparison_started)
            engine.comparison_completed.connect(self._on_comparison_completed)
            engine.metric_comparison_updated.connect(self._on_metric_comparison_updated)
        self.logger.info("对照分析引擎已设置")
    
    def set_data_bridge(self, data_bridge):
        """设置数据桥接"""
        self._data_bridge = data_bridge
        self.logger.info("数据桥接已设置")
    
    def set_replay_controller(self, replay_controller):
        """设置回放控制器，用于获取可用数据源"""
        self._replay_controller = replay_controller
        self.refresh_data_sources()
        self.logger.info("回放控制器已设置到对照分析面板")
    
    def refresh_data_sources(self):
        """从回放控制器动态刷新可用数据源列表"""
        current_exp = self.exp_combo.currentData()
        current_ctrl = self.ctrl_combo.currentData()
        
        self.exp_combo.clear()
        self.ctrl_combo.clear()
        
        self.exp_combo.addItem("当前数据（实验组）", "current_experimental")
        self.ctrl_combo.addItem("当前数据（对照组）", "current_control")
        
        if self._replay_controller:
            try:
                source_types = self._replay_controller.get_available_source_types()
                if source_types:
                    for st in source_types:
                        label = str(st) if isinstance(st, str) else getattr(st, 'name', str(st))
                        self.exp_combo.addItem(f"{label}（实验组）", f"exp_{st}")
                        self.ctrl_combo.addItem(f"{label}（对照组）", f"ctrl_{st}")
            except Exception as e:
                self.logger.debug(f"刷新数据源列表失败: {e}")
        
        if self._data_bridge:
            try:
                cache = getattr(self._data_bridge, '_cache', None)
                if cache:
                    cache_sources = cache.get_source_types() if hasattr(cache, 'get_source_types') else []
                    for cs in cache_sources:
                        label = str(cs) if isinstance(cs, str) else getattr(cs, 'name', str(cs))
                        existing_exp = self.exp_combo.findData(f"exp_{cs}")
                        if existing_exp < 0:
                            self.exp_combo.addItem(f"{label}（实验组）", f"exp_{cs}")
                        existing_ctrl = self.ctrl_combo.findData(f"ctrl_{cs}")
                        if existing_ctrl < 0:
                            self.ctrl_combo.addItem(f"{label}（对照组）", f"ctrl_{cs}")
            except Exception as e:
                self.logger.debug(f"从缓存刷新数据源失败: {e}")
        
        exp_idx = self.exp_combo.findData(current_exp)
        if exp_idx >= 0:
            self.exp_combo.setCurrentIndex(exp_idx)
        ctrl_idx = self.ctrl_combo.findData(current_ctrl)
        if ctrl_idx >= 0:
            self.ctrl_combo.setCurrentIndex(ctrl_idx)
        
        self.logger.info(f"数据源列表已刷新: 实验组={self.exp_combo.count()}项, 对照组={self.ctrl_combo.count()}项")
    
    def _on_start_comparison(self):
        """开始对比"""
        self.logger.info("开始对比分析...")
        exp_source = self.exp_combo.currentData() or self.exp_combo.currentText()
        ctrl_source = self.ctrl_combo.currentData() or self.ctrl_combo.currentText()
        self.comparison_requested.emit({
            'experimental_group': exp_source,
            'control_group': ctrl_source,
            'experimental_label': self.exp_combo.currentText(),
            'control_label': self.ctrl_combo.currentText()
        })
    
    def _on_export_report(self):
        """导出报告"""
        self.export_report_requested.emit()
        self.logger.info("导出对照报告")
    
    def _on_location_changed(self, index: int):
        """位置选择变化"""
        if not self._current_result:
            return
        
        loc_data = self.location_combo.itemData(index)
        if loc_data is None:
            # 总体
            self._show_overall_comparison(self._current_result)
            self.location_comparison_label.setText("当前位置: 总体")
        else:
            # 特定位置
            self._show_location_comparison(self._current_result, loc_data)
            loc_name = LOCATION_NAMES.get(loc_data, loc_data)
            self.location_comparison_label.setText(f"当前位置: {loc_name}")
    
    def _on_comparison_started(self, info):
        """对比开始"""
        self.logger.info(f"对比分析开始: {info}")
    
    def _on_comparison_completed(self, result):
        """对比完成"""
        self.logger.info(f"对比分析完成: {result}")
        self._current_result = result
        self._update_ui_with_result(result)
        self._add_to_history(result)
    
    def _on_metric_comparison_updated(self, metric_info):
        """指标对比更新"""
        self.logger.info(f"指标对比更新: {metric_info}")
        self._update_metric_comparison(metric_info)
    
    def _update_ui_with_result(self, result):
        """用结果更新UI"""
        try:
            # 获取两组评测结果
            exp_result = result.get('experimental_result', {})
            ctrl_result = result.get('control_result', {})
            comparison_metrics = result.get('comparison_metrics', {})
            
            # 更新总体评分
            exp_score = exp_result.get('overall_score', 0)
            self.exp_score_label.setText(f"{exp_score:.1f}")
            self.exp_score_progress.setValue(int(exp_score))
            
            ctrl_score = ctrl_result.get('overall_score', 0)
            self.ctrl_score_label.setText(f"{ctrl_score:.1f}")
            self.ctrl_score_progress.setValue(int(ctrl_score))
            
            # 更新改进度
            overall_improvement = result.get('overall_improvement', 0)
            self._update_improvement_display(overall_improvement)
            
            # 更新位置对比
            location_comparisons = result.get('location_comparisons', {})
            for loc_id, loc_comp in location_comparisons.items():
                if loc_id in self.location_comparison_widgets:
                    self._update_location_comparison_card(loc_id, loc_comp)
            
            # 更新指标对比
            self._on_location_changed(self.location_combo.currentIndex())
            
            # 更新改进统计
            improved = result.get('improved_count', 0)
            same = result.get('same_count', 0)
            worse = result.get('worse_count', 0)
            self.improvement_stats.setText(f"改进: {improved} | 持平: {same} | 下降: {worse}")
        
        except Exception as e:
            self.logger.error(f"更新UI失败: {e}")
    
    def _update_location_comparison_card(self, loc_id: str, loc_comp: dict):
        """更新位置对比卡片"""
        try:
            card = self.location_comparison_widgets[loc_id]
            
            exp_score_label = card.findChild(QLabel, f"exp_score_{loc_id}")
            ctrl_score_label = card.findChild(QLabel, f"ctrl_score_{loc_id}")
            improvement_label = card.findChild(QLabel, f"improvement_{loc_id}")
            
            if exp_score_label:
                exp_score = loc_comp.get('experimental_score', 0)
                exp_score_label.setText(f"魔椅: {exp_score:.1f}")
            
            if ctrl_score_label:
                ctrl_score = loc_comp.get('control_score', 0)
                ctrl_score_label.setText(f"传统椅: {ctrl_score:.1f}")
            
            if improvement_label:
                improvement = loc_comp.get('improvement_pct', 0)
                if improvement > 0:
                    color = '#4CAF50'
                    text = f"改善: +{improvement:.1f}%"
                elif improvement < 0:
                    color = '#F44336'
                    text = f"下降: {improvement:.1f}%"
                else:
                    color = '#FFC107'
                    text = "持平: 0.0%"
                improvement_label.setText(text)
                improvement_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {color};")
        
        except Exception as e:
            self.logger.error(f"更新位置对比卡片失败 {loc_id}: {e}")
    
    def _show_overall_comparison(self, result):
        """显示总体对比"""
        comparison_metrics = result.get('comparison_metrics', {})
        for indicator_id, metric_info in comparison_metrics.items():
            self._update_metric_comparison({
                'indicator_id': indicator_id,
                **metric_info
            })
    
    def _show_location_comparison(self, result, loc_id: str):
        """显示位置对比"""
        location_comparisons = result.get('location_comparisons', {})
        loc_comp = location_comparisons.get(loc_id, {})
        metrics = loc_comp.get('metrics', {})
        
        # 先清空表格
        for row in range(self.comparison_table.rowCount()):
            for col in range(4, 10):
                self.comparison_table.setItem(row, col, QTableWidgetItem("--"))
        
        # 更新有数据的指标
        for indicator_id, metric_info in metrics.items():
            self._update_metric_comparison({
                'indicator_id': indicator_id,
                **metric_info
            })
    
    def _update_metric_comparison(self, metric_info):
        """更新指标对比 — 使用 _indicator_row_map 快速定位"""
        indicator_id = metric_info.get('indicator_id')
        if not indicator_id:
            return

        row = self._indicator_row_map.get(indicator_id)
        if row is None:
            return

        exp_val = metric_info.get('experimental_value', '--')
        self.comparison_table.setItem(row, 4, QTableWidgetItem(
            f"{exp_val:.4f}" if isinstance(exp_val, float) else str(exp_val)))

        ctrl_val = metric_info.get('control_value', '--')
        self.comparison_table.setItem(row, 5, QTableWidgetItem(
            f"{ctrl_val:.4f}" if isinstance(ctrl_val, float) else str(ctrl_val)))

        abs_diff = metric_info.get('absolute_difference', '--')
        self.comparison_table.setItem(row, 6, QTableWidgetItem(
            f"{abs_diff:.4f}" if isinstance(abs_diff, float) else str(abs_diff)))

        rel_diff = metric_info.get('relative_difference', '--')
        rel_item = QTableWidgetItem(
            f"{rel_diff:.2%}" if isinstance(rel_diff, float) else str(rel_diff))
        rel_item.setTextAlignment(Qt.AlignCenter)
        self.comparison_table.setItem(row, 7, rel_item)

        direction = metric_info.get('improvement_direction', '--')
        direction_item = QTableWidgetItem(direction)
        direction_item.setTextAlignment(Qt.AlignCenter)
        if direction == '改进':
            direction_item.setForeground(QColor('#4CAF50'))
        elif direction == '下降':
            direction_item.setForeground(QColor('#F44336'))
        self.comparison_table.setItem(row, 8, direction_item)
    
    def _update_improvement_display(self, improvement):
        """更新改进度显示"""
        if improvement > 0:
            color = '#4CAF50'
            text = f"+{improvement:.1f}%"
        elif improvement < 0:
            color = '#F44336'
            text = f"{improvement:.1f}%"
        else:
            color = '#FFC107'
            text = "0.0%"
        
        self.improvement_label.setText(text)
        self.improvement_label.setStyleSheet(f"""
            QLabel {{
                font-size: 42px;
                font-weight: 800;
                color: {color};
                padding: 20px;
            }}
        """)
    
    def _add_to_history(self, result):
        """添加到历史记录"""
        from datetime import datetime
        
        timestamp = result.get('timestamp', datetime.now().timestamp())
        dt = datetime.fromtimestamp(timestamp)
        
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        exp_result = result.get('experimental_result', {})
        ctrl_result = result.get('control_result', {})
        
        self.history_table.setItem(row, 0, QTableWidgetItem(dt.strftime("%Y-%m-%d %H:%M:%S")))
        self.history_table.setItem(row, 1, QTableWidgetItem(self.exp_combo.currentText()))
        self.history_table.setItem(row, 2, QTableWidgetItem(self.ctrl_combo.currentText()))
        self.history_table.setItem(row, 3, QTableWidgetItem(f"{exp_result.get('overall_score', 0):.1f}"))
        self.history_table.setItem(row, 4, QTableWidgetItem(f"{ctrl_result.get('overall_score', 0):.1f}"))
        
        improvement = result.get('overall_improvement', 0)
        improve_item = QTableWidgetItem(f"{improvement:+.1f}%")
        if improvement > 0:
            improve_item.setForeground(QColor('#4CAF50'))
        elif improvement < 0:
            improve_item.setForeground(QColor('#F44336'))
        self.history_table.setItem(row, 5, improve_item)
        
        # 详情按钮
        detail_btn = QPushButton("查看")
        detail_btn.setObjectName("btnSmall")
        detail_btn.setMaximumWidth(60)
        self.history_table.setCellWidget(row, 6, detail_btn)
