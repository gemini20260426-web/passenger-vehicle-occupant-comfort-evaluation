"""
融合算法配置面板 - 配置数据融合算法和参数
提供融合算法选择、权重设置、参数调整等功能
"""

import logging
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QCheckBox, QFrame, QScrollArea, QSlider, QTableWidget,
    QTableWidgetItem, QHeaderView
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
    FusionAlgorithm
)

logger = logging.getLogger(__name__)

class FusionAlgorithmConfigPanel(QWidget):
    """融合算法配置面板"""
    
    # 信号定义
    fusion_config_changed = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        
        self.setup_ui()
        self.load_config()
        self.connect_signals()
        
        logger.info("融合算法配置面板已初始化")
    
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
        
        # 融合算法选择
        algorithm_group = self._create_algorithm_group()
        content_layout.addWidget(algorithm_group)
        
        # 数据源权重设置
        weights_group = self._create_weights_group()
        content_layout.addWidget(weights_group)
        
        # 算法参数配置
        params_group = self._create_params_group()
        content_layout.addWidget(params_group)
        
        # 算法说明
        info_group = self._create_info_group()
        content_layout.addWidget(info_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
    
    def _create_algorithm_group(self) -> QGroupBox:
        """创建算法选择组"""
        group = QGroupBox("🔄 融合算法")
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
        
        # 算法单选按钮组
        self.algorithm_group = QButtonGroup(self)
        
        # 加权平均
        self.radio_weighted = QRadioButton("加权平均")
        self.radio_weighted.setStyleSheet(f"""
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
        self.algorithm_group.addButton(self.radio_weighted, 0)
        layout.addWidget(self.radio_weighted)
        
        weighted_desc = QLabel("简单高效，适合数据质量稳定的场景")
        weighted_desc.setStyleSheet(f"color: {PRO_COLORS.text_secondary}; font-size: 12px; padding-left: 26px;")
        layout.addWidget(weighted_desc)
        
        # 卡尔曼滤波
        self.radio_kalman = QRadioButton("卡尔曼滤波（推荐）")
        self.radio_kalman.setStyleSheet(self.radio_weighted.styleSheet())
        self.algorithm_group.addButton(self.radio_kalman, 1)
        layout.addWidget(self.radio_kalman)
        
        kalman_desc = QLabel("动态估计，适合有噪声的传感器数据")
        kalman_desc.setStyleSheet(weighted_desc.styleSheet())
        layout.addWidget(kalman_desc)
        
        # 神经网络
        self.radio_nn = QRadioButton("神经网络")
        self.radio_nn.setStyleSheet(self.radio_weighted.styleSheet())
        self.algorithm_group.addButton(self.radio_nn, 2)
        layout.addWidget(self.radio_nn)
        
        nn_desc = QLabel("学习模式，适合复杂非线性关系的数据")
        nn_desc.setStyleSheet(weighted_desc.styleSheet())
        layout.addWidget(nn_desc)
        
        # 集成方法
        self.radio_ensemble = QRadioButton("集成方法")
        self.radio_ensemble.setStyleSheet(self.radio_weighted.styleSheet())
        self.algorithm_group.addButton(self.radio_ensemble, 3)
        layout.addWidget(self.radio_ensemble)
        
        ensemble_desc = QLabel("多算法融合，提供最佳鲁棒性")
        ensemble_desc.setStyleSheet(weighted_desc.styleSheet())
        layout.addWidget(ensemble_desc)
        
        return group
    
    def _create_weights_group(self) -> QGroupBox:
        """创建权重设置组"""
        group = QGroupBox("⚖️ 数据源权重")
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
        
        # 权重表格
        self.weights_table = QTableWidget()
        self.weights_table.setColumnCount(3)
        self.weights_table.setHorizontalHeaderLabels(["数据源", "权重 (%)", "颜色"])
        self.weights_table.horizontalHeader().setStretchLastSection(True)
        self.weights_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PRO_COLORS.bg_dark};
                color: {PRO_COLORS.text_primary};
                border: 1px solid {PRO_COLORS.bg_light};
                border-radius: 6px;
                gridline-color: {PRO_COLORS.bg_light};
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: {PRO_COLORS.bg_medium};
                color: {PRO_COLORS.text_primary};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {PRO_COLORS.primary};
                font-weight: bold;
            }}
        """)
        self.weights_table.setMaximumHeight(200)
        layout.addWidget(self.weights_table)
        
        # 自动权重按钮
        button_layout = QHBoxLayout()
        self.btn_auto_weights = QPushButton("🤖 自动权重")
        style_manager.apply_button_style(self.btn_auto_weights, "secondary")
        button_layout.addWidget(self.btn_auto_weights)
        
        self.btn_reset_weights = QPushButton("↩️ 重置权重")
        style_manager.apply_button_style(self.btn_reset_weights, "secondary")
        button_layout.addWidget(self.btn_reset_weights)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return group
    
    def _create_params_group(self) -> QGroupBox:
        """创建参数配置组"""
        group = QGroupBox("📊 算法参数")
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
        
        # 卡尔曼滤波参数
        kalman_layout = QVBoxLayout()
        
        kalman_header = QLabel("卡尔曼滤波参数:")
        kalman_header.setStyleSheet(f"color: {PRO_COLORS.text_primary}; font-weight: bold; font-size: 13px;")
        kalman_layout.addWidget(kalman_header)
        
        # 过程噪声
        self.spin_process_noise = QDoubleSpinBox()
        self.spin_process_noise.setRange(0.001, 1.0)
        self.spin_process_noise.setValue(0.1)
        self.spin_process_noise.setSingleStep(0.01)
        self.spin_process_noise.setDecimals(3)
        self.spin_process_noise.setStyleSheet(style_manager.get_input_style())
        kalman_layout.addWidget(QLabel("过程噪声协方差:"))
        kalman_layout.addWidget(self.spin_process_noise)
        
        # 测量噪声
        self.spin_measure_noise = QDoubleSpinBox()
        self.spin_measure_noise.setRange(0.001, 1.0)
        self.spin_measure_noise.setValue(0.5)
        self.spin_measure_noise.setSingleStep(0.01)
        self.spin_measure_noise.setDecimals(3)
        self.spin_measure_noise.setStyleSheet(style_manager.get_input_style())
        kalman_layout.addWidget(QLabel("测量噪声协方差:"))
        kalman_layout.addWidget(self.spin_measure_noise)
        
        layout.addRow(kalman_layout)
        
        return group
    
    def _create_info_group(self) -> QGroupBox:
        """创建算法说明组"""
        group = QGroupBox("📚 算法说明")
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {PRO_COLORS.text_primary};
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {PRO_COLORS.success};
                border-radius: {SIZES.card_radius}px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: rgba(16, 185, 129, 0.1);
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
        <p><b>加权平均:</b> 计算简单，延迟低，但对异常值敏感</p>
        <p><b>卡尔曼滤波:</b> 适合含噪声的时序数据，能预测状态</p>
        <p><b>神经网络:</b> 能学习复杂模式，但需要训练数据</p>
        <p><b>集成方法:</b> 结合多个算法，鲁棒性最强</p>
        """)
        info_text.setStyleSheet(f"color: {PRO_COLORS.text_primary}; font-size: 13px; line-height: 1.6;")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        return group
    
    def connect_signals(self):
        """连接信号"""
        self.algorithm_group.buttonClicked.connect(self._on_algorithm_changed)
        self.spin_process_noise.valueChanged.connect(self._on_param_changed)
        self.spin_measure_noise.valueChanged.connect(self._on_param_changed)
        self.btn_auto_weights.clicked.connect(self._auto_weights)
        self.btn_reset_weights.clicked.connect(self._reset_weights)
        self.weights_table.cellChanged.connect(self._on_weight_changed)
    
    def load_config(self):
        """加载配置"""
        fusion_config = self.config_manager.fusion_config
        
        # 设置算法
        algorithm_map = {
            FusionAlgorithm.WEIGHTED_AVERAGE: self.radio_weighted,
            FusionAlgorithm.KALMAN_FILTER: self.radio_kalman,
            FusionAlgorithm.NEURAL_NETWORK: self.radio_nn,
            FusionAlgorithm.ENSEMBLE: self.radio_ensemble
        }
        algorithm = FusionAlgorithm(fusion_config.algorithm)
        if algorithm in algorithm_map:
            algorithm_map[algorithm].setChecked(True)
        
        # 设置卡尔曼参数
        if "process_noise" in fusion_config.kalman_params:
            self.spin_process_noise.setValue(fusion_config.kalman_params["process_noise"])
        if "measurement_noise" in fusion_config.kalman_params:
            self.spin_measure_noise.setValue(fusion_config.kalman_params["measurement_noise"])
        
        # 加载权重
        self._load_weights()
    
    def _load_weights(self):
        """加载数据源权重"""
        self.weights_table.setRowCount(0)
        
        data_sources = self.config_manager.data_sources
        default_weight = 100.0 / max(1, len(data_sources))
        
        color_map = [
            PRO_COLORS.imu_data,
            PRO_COLORS.cnap_data,
            PRO_COLORS.mqtt_data,
            PRO_COLORS.secondary
        ]
        
        for i, (source_id, source_config) in enumerate(data_sources.items()):
            row = self.weights_table.rowCount()
            self.weights_table.insertRow(row)
            
            # 数据源名称
            name_item = QTableWidgetItem(source_config.name)
            name_item.setData(Qt.UserRole, source_id)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.weights_table.setItem(row, 0, name_item)
            
            # 权重
            weight = source_config.weights.get(source_id, default_weight) if hasattr(source_config, 'weights') else default_weight
            weight_item = QTableWidgetItem(f"{weight:.1f}")
            weight_item.setData(Qt.UserRole, source_id)
            self.weights_table.setItem(row, 1, weight_item)
            
            # 颜色指示器
            color_frame = QFrame()
            color = color_map[i % len(color_map)]
            color_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {color};
                    border-radius: 4px;
                    min-width: 20px;
                    min-height: 20px;
                }}
            """)
            self.weights_table.setCellWidget(row, 2, color_frame)
    
    def save_config(self):
        """保存配置"""
        # 获取算法
        button_id = self.algorithm_group.checkedId()
        algorithm_map = {
            0: FusionAlgorithm.WEIGHTED_AVERAGE,
            1: FusionAlgorithm.KALMAN_FILTER,
            2: FusionAlgorithm.NEURAL_NETWORK,
            3: FusionAlgorithm.ENSEMBLE
        }
        algorithm = algorithm_map.get(button_id, FusionAlgorithm.KALMAN_FILTER)
        
        # 获取权重
        weights = self._get_weights()
        
        # 更新配置
        self.config_manager.update_fusion_config(
            algorithm=algorithm.value,
            weights=weights,
            kalman_params={
                "process_noise": self.spin_process_noise.value(),
                "measurement_noise": self.spin_measure_noise.value()
            }
        )
        
        # 保存到文件
        self.config_manager.save_config()
    
    def _get_weights(self) -> Dict[str, float]:
        """获取权重配置"""
        weights = {}
        for row in range(self.weights_table.rowCount()):
            source_id = self.weights_table.item(row, 0).data(Qt.UserRole)
            weight_text = self.weights_table.item(row, 1).text()
            try:
                weight = float(weight_text)
                weights[source_id] = weight
            except ValueError:
                weights[source_id] = 0.0
        return weights
    
    def _on_algorithm_changed(self):
        """算法变化时的处理"""
        self._on_param_changed()
    
    def _on_param_changed(self):
        """参数变化时的处理"""
        config = {
            "algorithm": self.algorithm_group.checkedId(),
            "process_noise": self.spin_process_noise.value(),
            "measure_noise": self.spin_measure_noise.value(),
            "weights": self._get_weights()
        }
        self.fusion_config_changed.emit(config)
        self.save_config()
    
    def _on_weight_changed(self, row: int, column: int):
        """权重变化时的处理"""
        if column == 1:
            self._on_param_changed()
    
    def _auto_weights(self):
        """自动计算权重"""
        # 这里可以实现基于数据质量的自动权重分配
        # 暂时使用平均权重
        row_count = self.weights_table.rowCount()
        if row_count > 0:
            avg_weight = 100.0 / row_count
            for row in range(row_count):
                self.weights_table.item(row, 1).setText(f"{avg_weight:.1f}")
            self._on_param_changed()
    
    def _reset_weights(self):
        """重置权重"""
        self._load_weights()
        self._on_param_changed()
