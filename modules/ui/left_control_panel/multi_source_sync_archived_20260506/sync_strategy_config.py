"""
同步策略配置面板 - 配置数据同步策略和参数
提供同步策略选择、频率设置、延迟控制等功能
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QCheckBox, QFrame, QScrollArea, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# 导入工具模块
from ..utils import (
    style_manager,
    PRO_COLORS,
    SPACING,
    SIZES,
    get_config_manager,
    SyncStrategy
)

logger = logging.getLogger(__name__)

class SyncStrategyConfigPanel(QWidget):
    """同步策略配置面板"""
    
    # 信号定义
    sync_config_changed = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        
        self.setup_ui()
        self.load_config()
        self.connect_signals()
        
        logger.info("同步策略配置面板已初始化")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        main_layout.setSpacing(SPACING.lg)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {PRO_COLORS.bg_dark};")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(SPACING.lg)
        
        # 同步策略选择
        strategy_group = self._create_strategy_group()
        content_layout.addWidget(strategy_group)
        
        # 同步参数配置
        params_group = self._create_params_group()
        content_layout.addWidget(params_group)
        
        # 高级选项
        advanced_group = self._create_advanced_group()
        content_layout.addWidget(advanced_group)
        
        # 策略说明
        info_group = self._create_info_group()
        content_layout.addWidget(info_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
    
    def _create_strategy_group(self) -> QGroupBox:
        """创建同步策略选择组"""
        group = QGroupBox("⏱️ 同步策略")
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {PRO_COLORS.text_primary};
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {PRO_COLORS.bg_light};
                border-radius: {SIZES.card_radius}px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: {PRO_COLORS.bg_medium};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }}
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(SPACING.md)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        
        # 策略单选按钮组
        self.strategy_group = QButtonGroup(self)
        
        # 时间优先策略
        self.radio_time = QRadioButton("时间优先策略")
        self.radio_time.setStyleSheet(f"""
            QRadioButton {{
                color: {PRO_COLORS.text_primary};
                font-size: 13px;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid {PRO_COLORS.bg_light};
                background-color: {PRO_COLORS.bg_dark};
            }}
            QRadioButton::indicator:checked {{
                border-color: {PRO_COLORS.primary};
                background-color: {PRO_COLORS.primary};
            }}
        """)
        self.strategy_group.addButton(self.radio_time, 0)
        layout.addWidget(self.radio_time)
        
        time_desc = QLabel("以时间同步精度为最高优先级，可能会降低数据质量")
        time_desc.setStyleSheet(f"color: {PRO_COLORS.text_secondary}; font-size: 12px; padding-left: 26px;")
        layout.addWidget(time_desc)
        
        # 质量优先策略
        self.radio_quality = QRadioButton("质量优先策略")
        self.radio_quality.setStyleSheet(self.radio_time.styleSheet())
        self.strategy_group.addButton(self.radio_quality, 1)
        layout.addWidget(self.radio_quality)
        
        quality_desc = QLabel("以数据质量为最高优先级，可能会引入轻微延迟")
        quality_desc.setStyleSheet(time_desc.styleSheet())
        layout.addWidget(quality_desc)
        
        # 混合策略
        self.radio_hybrid = QRadioButton("混合策略")
        self.radio_hybrid.setStyleSheet(self.radio_time.styleSheet())
        self.strategy_group.addButton(self.radio_hybrid, 2)
        layout.addWidget(self.radio_hybrid)
        
        hybrid_desc = QLabel("在时间精度和数据质量之间取得平衡")
        hybrid_desc.setStyleSheet(time_desc.styleSheet())
        layout.addWidget(hybrid_desc)
        
        # 自适应策略
        self.radio_adaptive = QRadioButton("自适应策略（推荐）")
        self.radio_adaptive.setStyleSheet(self.radio_time.styleSheet())
        self.strategy_group.addButton(self.radio_adaptive, 3)
        layout.addWidget(self.radio_adaptive)
        
        adaptive_desc = QLabel("根据实时数据质量和延迟自动调整策略")
        adaptive_desc.setStyleSheet(time_desc.styleSheet())
        layout.addWidget(adaptive_desc)
        
        return group
    
    def _create_params_group(self) -> QGroupBox:
        """创建参数配置组"""
        group = QGroupBox("⚙️ 同步参数")
        group.setStyleSheet(self._create_strategy_group.__doc__)
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {PRO_COLORS.text_primary};
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {PRO_COLORS.bg_light};
                border-radius: {SIZES.card_radius}px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: {PRO_COLORS.bg_medium};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }}
        """)
        
        layout = QFormLayout(group)
        layout.setSpacing(SPACING.md)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        
        # 同步频率
        self.spin_frequency = QSpinBox()
        self.spin_frequency.setRange(1, 1000)
        self.spin_frequency.setValue(100)
        self.spin_frequency.setSuffix(" Hz")
        self.spin_frequency.setStyleSheet(style_manager.get_input_style())
        layout.addRow("同步频率:", self.spin_frequency)
        
        # 最大延迟
        self.spin_max_latency = QDoubleSpinBox()
        self.spin_max_latency.setRange(1, 1000)
        self.spin_max_latency.setValue(50)
        self.spin_max_latency.setSuffix(" ms")
        self.spin_max_latency.setSingleStep(5)
        self.spin_max_latency.setStyleSheet(style_manager.get_input_style())
        layout.addRow("最大延迟:", self.spin_max_latency)
        
        # 缓冲大小
        self.spin_buffer_size = QSpinBox()
        self.spin_buffer_size.setRange(10, 10000)
        self.spin_buffer_size.setValue(100)
        self.spin_buffer_size.setStyleSheet(style_manager.get_input_style())
        layout.addRow("缓冲大小:", self.spin_buffer_size)
        
        # 超时时间
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(100, 30000)
        self.spin_timeout.setValue(5000)
        self.spin_timeout.setSuffix(" ms")
        self.spin_timeout.setStyleSheet(style_manager.get_input_style())
        layout.addRow("超时时间:", self.spin_timeout)
        
        return group
    
    def _create_advanced_group(self) -> QGroupBox:
        """创建高级选项组"""
        group = QGroupBox("🔧 高级选项")
        group.setCheckable(True)
        group.setChecked(False)
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {PRO_COLORS.text_primary};
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {PRO_COLORS.bg_light};
                border-radius: {SIZES.card_radius}px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: {PRO_COLORS.bg_medium};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }}
            QGroupBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {PRO_COLORS.bg_light};
                border-radius: 4px;
                background-color: {PRO_COLORS.bg_dark};
            }}
            QGroupBox::indicator:checked {{
                background-color: {PRO_COLORS.primary};
                border-color: {PRO_COLORS.primary};
            }}
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(SPACING.md)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        
        # 启用自动恢复
        self.check_auto_recover = QCheckBox("启用自动恢复")
        self.check_auto_recover.setChecked(True)
        self.check_auto_recover.setStyleSheet(f"""
            QCheckBox {{
                color: {PRO_COLORS.text_primary};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {PRO_COLORS.bg_light};
                border-radius: 4px;
                background-color: {PRO_COLORS.bg_dark};
            }}
            QCheckBox::indicator:checked {{
                background-color: {PRO_COLORS.success};
                border-color: {PRO_COLORS.success};
            }}
        """)
        layout.addWidget(self.check_auto_recover)
        
        # 启用数据重采样
        self.check_resample = QCheckBox("启用数据重采样")
        self.check_resample.setChecked(True)
        self.check_resample.setStyleSheet(self.check_auto_recover.styleSheet())
        layout.addWidget(self.check_resample)
        
        # 启用异常检测
        self.check_anomaly_detect = QCheckBox("启用异常检测")
        self.check_anomaly_detect.setChecked(True)
        self.check_anomaly_detect.setStyleSheet(self.check_auto_recover.styleSheet())
        layout.addWidget(self.check_anomaly_detect)
        
        # 恢复重试次数
        retry_layout = QHBoxLayout()
        retry_label = QLabel("恢复重试次数:")
        retry_label.setStyleSheet(style_manager.get_label_style("normal"))
        self.spin_retry_count = QSpinBox()
        self.spin_retry_count.setRange(1, 20)
        self.spin_retry_count.setValue(5)
        self.spin_retry_count.setStyleSheet(style_manager.get_input_style())
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(self.spin_retry_count)
        retry_layout.addStretch()
        layout.addLayout(retry_layout)
        
        return group
    
    def _create_info_group(self) -> QGroupBox:
        """创建策略说明组"""
        group = QGroupBox("📚 策略说明")
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {PRO_COLORS.text_primary};
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {PRO_COLORS.info};
                border-radius: {SIZES.card_radius}px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: rgba(59, 130, 246, 0.1);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }}
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(SPACING.sm)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        
        info_text = QLabel("""
        <p><b>时间优先:</b> 适合实时性要求高的场景，如运动控制</p>
        <p><b>质量优先:</b> 适合精度要求高的场景，如医疗监测</p>
        <p><b>混合策略:</b> 平衡性能，适合大多数通用场景</p>
        <p><b>自适应策略:</b> 推荐使用，根据实际负载动态调整</p>
        """)
        info_text.setStyleSheet(f"color: {PRO_COLORS.text_primary}; font-size: 13px; line-height: 1.6;")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        return group
    
    def connect_signals(self):
        """连接信号"""
        self.strategy_group.buttonClicked.connect(self._on_strategy_changed)
        self.spin_frequency.valueChanged.connect(self._on_param_changed)
        self.spin_max_latency.valueChanged.connect(self._on_param_changed)
        self.spin_buffer_size.valueChanged.connect(self._on_param_changed)
        self.spin_timeout.valueChanged.connect(self._on_param_changed)
        self.check_auto_recover.stateChanged.connect(self._on_param_changed)
        self.check_resample.stateChanged.connect(self._on_param_changed)
        self.check_anomaly_detect.stateChanged.connect(self._on_param_changed)
        self.spin_retry_count.valueChanged.connect(self._on_param_changed)
    
    def load_config(self):
        """加载配置"""
        sync_config = self.config_manager.sync_config
        
        # 设置策略
        strategy_map = {
            SyncStrategy.TIME_PRIORITY: self.radio_time,
            SyncStrategy.QUALITY_PRIORITY: self.radio_quality,
            SyncStrategy.HYBRID: self.radio_hybrid,
            SyncStrategy.ADAPTIVE: self.radio_adaptive
        }
        strategy = SyncStrategy(sync_config.strategy)
        if strategy in strategy_map:
            strategy_map[strategy].setChecked(True)
        
        # 设置参数
        self.spin_frequency.setValue(int(sync_config.sync_frequency))
        self.spin_max_latency.setValue(sync_config.max_latency)
        self.spin_buffer_size.setValue(sync_config.buffer_size)
    
    def save_config(self):
        """保存配置"""
        # 获取策略
        button_id = self.strategy_group.checkedId()
        strategy_map = {
            0: SyncStrategy.TIME_PRIORITY,
            1: SyncStrategy.QUALITY_PRIORITY,
            2: SyncStrategy.HYBRID,
            3: SyncStrategy.ADAPTIVE
        }
        strategy = strategy_map.get(button_id, SyncStrategy.ADAPTIVE)
        
        # 更新配置
        self.config_manager.update_sync_config(
            strategy=strategy.value,
            sync_frequency=float(self.spin_frequency.value()),
            max_latency=self.spin_max_latency.value(),
            buffer_size=self.spin_buffer_size.value()
        )
        
        # 保存到文件
        self.config_manager.save_config()
    
    def _on_strategy_changed(self):
        """策略变化时的处理"""
        self._on_param_changed()
    
    def _on_param_changed(self):
        """参数变化时的处理"""
        config = {
            "strategy": self.strategy_group.checkedId(),
            "frequency": self.spin_frequency.value(),
            "max_latency": self.spin_max_latency.value(),
            "buffer_size": self.spin_buffer_size.value(),
            "timeout": self.spin_timeout.value(),
            "auto_recover": self.check_auto_recover.isChecked(),
            "resample": self.check_resample.isChecked(),
            "anomaly_detect": self.check_anomaly_detect.isChecked(),
            "retry_count": self.spin_retry_count.value()
        }
        self.sync_config_changed.emit(config)
        self.save_config()
