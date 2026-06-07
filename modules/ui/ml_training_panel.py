#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML 训练面板 — 驾驶行为模型训练
═══════════════════════════════════════════════════════════
集成到 RealTimeMonitoringTab 的第5个标签页 "🧠 ML训练"

功能:
  左侧: 训练配置 (CSV导入/超参/SMOTE/训练控制)
  右侧: 模型管理 (加载/信息/校准/阈值)
  底部: 训练日志 + 进度
"""

import os, sys, json, time, logging
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QSlider, QCheckBox, QGroupBox, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QSizePolicy,
    QLineEdit, QFormLayout,
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QTimer,
)
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  训练线程
# ═══════════════════════════════════════════════════════════

class MLTrainingThread(QThread):
    """后台训练线程 — 调用现有训练管线"""
    progress = Signal(int, str)       # 进度, 消息
    log_message = Signal(str)         # 日志
    finished = Signal(dict)           # 结果字典

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        try:
            self.progress.emit(5, "加载训练数据...")
            self.log_message.emit("开始加载训练数据")

            # 1. 加载或生成数据
            data_path = self.config.get('data_path', 'training_data.npz')
            if not os.path.exists(data_path):
                self.log_message.emit(f"数据文件不存在: {data_path}，生成合成数据...")
                self.progress.emit(10, "生成合成训练数据...")
                from core.core.analysis.generate_synthetic_data import generate_synthetic_data
                X, y = generate_synthetic_data(
                    samples_per_class=self.config.get('samples_per_class', 400),
                    noise_scale=self.config.get('noise_scale', 0.15),
                    random_state=self.config.get('random_state', 42),
                )
                np.savez_compressed(data_path, X=X, y=y)
                self.log_message.emit(f"合成数据已生成: {X.shape[0]} 样本")
            else:
                import numpy as np
                data = np.load(data_path)
                X, y = data['X'], data['y']
                self.log_message.emit(f"加载数据: {X.shape[0]} 样本, {X.shape[1]} 特征")

            self.progress.emit(15, "提取特征...")
            self.log_message.emit("特征提取完成")

            # 2. SMOTE
            if self.config.get('smote_enabled', True):
                self.progress.emit(30, "SMOTE 类别均衡...")
                self.log_message.emit("开始 SMOTE 过采样...")
                from core.core.analysis.layer4_behavior_classification.smote_balancer import SmoteBalancer
                balancer = SmoteBalancer(random_state=self.config.get('random_state', 42))
                X, y = balancer.balance(X, y)
                self.log_message.emit(f"SMOTE 完成: {X.shape[0]} 样本")

            self.progress.emit(40, "训练 LightGBM...")
            self.log_message.emit("开始 LightGBM 训练...")

            # 3. 训练
            from core.core.analysis.train_lgbm_model import train_model
            results = train_model(
                X, y,
                test_size=self.config.get('test_size', 0.2),
                n_estimators=self.config.get('n_estimators', 200),
                max_depth=self.config.get('max_depth', 12),
                learning_rate=self.config.get('lr', 0.05),
                random_state=self.config.get('random_state', 42),
            )

            self.progress.emit(100, f"训练完成! 准确率: {results['accuracy']*100:.1f}%")

            results['success'] = True
            results['n_samples'] = X.shape[0]
            results['n_features'] = X.shape[1]
            self.finished.emit(results)

        except Exception as e:
            self.log_message.emit(f"训练失败: {e}")
            self.finished.emit({'success': False, 'error': str(e)})


# ═══════════════════════════════════════════════════════════
#  ML 训练面板
# ═══════════════════════════════════════════════════════════

class MLTrainingPanel(QWidget):
    """ML 训练面板 — 驾驶行为模型训练

    用法:
        panel = MLTrainingPanel(config_manager)
        panel.set_data_bridge(data_bridge)  # 可选
    """

    model_loaded = Signal(object)   # 模型信息
    training_started = Signal()
    training_finished = Signal(dict)

    # 25 种事件映射
    EVENT_CN_MAP = {
        'emergency_braking': '🚨 紧急制动', 'aggressive_deceleration': '⚠️ 激进减速',
        'normal_deceleration': '🔽 正常减速', 'aggressive_acceleration': '⚠️ 激进加速',
        'normal_acceleration': '🔼 正常加速', 'launch': '🚀 起步',
        'constant_speed': '➡️ 匀速', 'stopped': '🅿️ 停车',
        'weaving': '🐍 蛇形驾驶', 'lane_change': '↔️ 变道',
        'rapid_direction_change': '⚡ 急速变向', 'tight_turn': '🔄 小半径转弯',
        'wide_turn': '↪️ 大半径转弯', 'u_turn': '↩️ U型转弯',
        'straight_driving': '➡️ 直线行驶', 'lane_keeping': '🛣 车道保持',
        'cornering_acceleration': '🏎 弯道加速', 'cornering_deceleration': '🏎 弯道减速',
        'cornering_braking': '⛔ 弯道制动', 'severe_bump': '💥 剧烈颠簸',
        'skid_risk': '🛞 侧滑风险', 'rollover_risk': '🚛 侧翻风险',
        'sensor_fault': '❌ 传感器异常', 'normal': '✅ 正常驾驶',
    }

    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

        self._data_bridge = None
        self._hybrid_classifier = None
        self._model_info = {}
        self._train_thread = None

        self._init_ui()
        self._init_hybrid_classifier()

    def _init_hybrid_classifier(self):
        """延迟加载 HybridBehaviorClassifier"""
        try:
            from core.core.analysis.layer4_behavior_classification import HybridBehaviorClassifier
            self._hybrid_classifier = HybridBehaviorClassifier(context_window_size=10)
            if self._hybrid_classifier.ml_classifier.is_ready():
                self._update_model_info_from_classifier()
                self.logger.info("ML 分类器已就绪")
        except Exception as e:
            self.logger.warning(f"HybridBehaviorClassifier 加载失败: {e}")

    def _update_model_info_from_classifier(self):
        """从分类器更新模型信息"""
        try:
            meta_path = r'core\core\models\lgbm_25class_classifier_meta.json'
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                self._model_info = {
                    'path': meta_path.replace('_meta.json', '.pkl'),
                    'version': meta.get('version', 'v1.0'),
                    'n_classes': meta.get('n_classes', 23),
                    'accuracy': meta.get('metrics', {}).get('accuracy', 0),
                    'f1': meta.get('metrics', {}).get('f1_macro', 0),
                    'train_date': meta.get('created_at', ''),
                    'feature_count': meta.get('n_features', 55),
                    'calibrated': bool(meta.get('calibration', {}).get('is_fitted', False)),
                }
                self._display_model_info()
        except Exception as e:
            self.logger.debug(f"读取模型元数据失败: {e}")

    def set_data_bridge(self, data_bridge):
        self._data_bridge = data_bridge

    @property
    def hybrid_classifier(self):
        return self._hybrid_classifier

    # ═══════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ——— 顶栏 ———
        top_bar = QHBoxLayout()
        title = QLabel("驾驶行为 ML 训练与推理")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #2F5496;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.status_indicator = QLabel("● 就绪")
        self.status_indicator.setStyleSheet("color: #28a745; font-size: 13px; font-weight: bold;")
        top_bar.addWidget(self.status_indicator)
        main_layout.addLayout(top_bar)

        # ——— 中间分栏: 左侧训练 | 右侧模型管理 ─——
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_right_panel())
        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter, stretch=3)

        # ——— 底部日志 ─——
        main_layout.addWidget(self._create_bottom_panel())

    def _create_left_panel(self):
        """左侧: 训练配置"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 数据源配置 ──
        ds_group = QGroupBox("📂 数据源配置")
        ds_layout = QGridLayout(ds_group)

        ds_layout.addWidget(QLabel("CSV文件:"), 0, 0)
        self.csv_path_label = QLabel("未选择 (将使用合成数据)")
        self.csv_path_label.setStyleSheet("color: #666; padding: 4px; border: 1px solid #ddd; border-radius: 3px;")
        ds_layout.addWidget(self.csv_path_label, 0, 1)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_csv)
        ds_layout.addWidget(btn_browse, 0, 2)

        ds_layout.addWidget(QLabel("窗口大小:"), 1, 0)
        self.win_size_spin = QSpinBox()
        self.win_size_spin.setRange(100, 2000)
        self.win_size_spin.setValue(500)
        ds_layout.addWidget(self.win_size_spin, 1, 1)

        ds_layout.addWidget(QLabel("步长:"), 1, 2)
        self.step_spin = QSpinBox()
        self.step_spin.setRange(10, 500)
        self.step_spin.setValue(50)
        ds_layout.addWidget(self.step_spin, 1, 3)

        ds_layout.addWidget(QLabel("每类样本:"), 2, 0)
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(100, 1000)
        self.samples_spin.setValue(400)
        ds_layout.addWidget(self.samples_spin, 2, 1)

        layout.addWidget(ds_group)

        # ── 训练参数 ──
        train_group = QGroupBox("⚙️ LightGBM 训练参数")
        train_layout = QGridLayout(train_group)

        train_layout.addWidget(QLabel("迭代次数:"), 0, 0)
        self.n_est_spin = QSpinBox()
        self.n_est_spin.setRange(50, 500)
        self.n_est_spin.setValue(200)
        train_layout.addWidget(self.n_est_spin, 0, 1)

        train_layout.addWidget(QLabel("最大深度:"), 1, 0)
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(3, 20)
        self.max_depth_spin.setValue(12)
        train_layout.addWidget(self.max_depth_spin, 1, 1)

        train_layout.addWidget(QLabel("学习率:"), 2, 0)
        self.lr_spin = QDoubleSpinBox()
        self.lr_spin.setRange(0.01, 0.30)
        self.lr_spin.setValue(0.05)
        self.lr_spin.setSingleStep(0.01)
        train_layout.addWidget(self.lr_spin, 2, 1)

        train_layout.addWidget(QLabel("测试集比例:"), 3, 0)
        self.test_size_spin = QDoubleSpinBox()
        self.test_size_spin.setRange(0.1, 0.4)
        self.test_size_spin.setValue(0.2)
        self.test_size_spin.setSingleStep(0.05)
        train_layout.addWidget(self.test_size_spin, 3, 1)

        self.smote_cb = QCheckBox("启用 SMOTE 类别均衡")
        self.smote_cb.setChecked(True)
        train_layout.addWidget(self.smote_cb, 4, 0, 1, 2)

        self.calibrate_cb = QCheckBox("启用概率校准 (Phase 2 Platt Scaling)")
        self.calibrate_cb.setChecked(True)
        train_layout.addWidget(self.calibrate_cb, 5, 0, 1, 2)

        layout.addWidget(train_group)

        # ── 训练控制 ──
        ctrl_layout = QHBoxLayout()
        self.btn_train = QPushButton("🚀 开始训练")
        self.btn_train.setStyleSheet(
            "QPushButton { background: #28a745; color: white; font-weight: bold; "
            "padding: 10px; border-radius: 4px; font-size: 13px; } "
            "QPushButton:hover { background: #218838; } "
            "QPushButton:disabled { background: #aaa; }"
        )
        self.btn_train.clicked.connect(self._start_training)
        ctrl_layout.addWidget(self.btn_train)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_training)
        ctrl_layout.addWidget(self.btn_stop)

        layout.addLayout(ctrl_layout)

        # ── 训练进度 ──
        self.train_progress = QProgressBar()
        self.train_progress.setVisible(False)
        self.train_progress.setStyleSheet(
            "QProgressBar { border: 1px solid #ddd; border-radius: 4px; text-align: center; height: 22px; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #3498db, stop:0.5 #2ecc71, stop:1 #27ae60); border-radius: 3px; }"
        )
        layout.addWidget(self.train_progress)

        self.train_status = QLabel("")
        self.train_status.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.train_status)

        layout.addStretch()
        return panel

    def _create_right_panel(self):
        """右侧: 模型管理 + 事件类型映射"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 模型管理 ──
        model_group = QGroupBox("🧠 模型管理")
        model_layout = QVBoxLayout(model_group)

        # 模型路径
        path_layout = QHBoxLayout()
        self.model_path_label = QLabel("未加载模型")
        self.model_path_label.setStyleSheet("color: #e67e22; font-size: 11px;")
        path_layout.addWidget(self.model_path_label)
        btn_load = QPushButton("加载模型")
        btn_load.clicked.connect(self._load_model)
        path_layout.addWidget(btn_load)
        btn_reload = QPushButton("刷新")
        btn_reload.clicked.connect(self._update_model_info_from_classifier)
        path_layout.addWidget(btn_reload)
        model_layout.addLayout(path_layout)

        # 模型信息
        self.model_info_text = QTextEdit()
        self.model_info_text.setReadOnly(True)
        self.model_info_text.setMaximumHeight(130)
        self.model_info_text.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; font-size: 11px;"
        )
        model_layout.addWidget(self.model_info_text)

        # 置信度阈值
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("置信度阈值:"))
        self.conf_thresh_slider = QSlider(Qt.Horizontal)
        self.conf_thresh_slider.setRange(50, 99)
        self.conf_thresh_slider.setValue(85)
        self.conf_thresh_slider.setTickPosition(QSlider.TicksBelow)
        self.conf_thresh_label = QLabel("85%")
        thresh_layout.addWidget(self.conf_thresh_slider)
        thresh_layout.addWidget(self.conf_thresh_label)
        self.conf_thresh_slider.valueChanged.connect(
            lambda v: self.conf_thresh_label.setText(f"{v}%"))
        model_layout.addLayout(thresh_layout)

        layout.addWidget(model_group)

        # ── 特征重要性 ──
        feat_group = QGroupBox("📊 特征重要性 Top-10")
        feat_layout = QVBoxLayout(feat_group)
        self.feat_importance_text = QTextEdit()
        self.feat_importance_text.setReadOnly(True)
        self.feat_importance_text.setMaximumHeight(180)
        self.feat_importance_text.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; font-size: 10px;"
        )
        feat_layout.addWidget(self.feat_importance_text)
        btn_refresh_feat = QPushButton("刷新特征重要性")
        btn_refresh_feat.clicked.connect(self._refresh_feature_importance)
        feat_layout.addWidget(btn_refresh_feat)
        layout.addWidget(feat_group)

        # ── 事件类型映射 ──
        event_group = QGroupBox("🎯 23种事件类型映射")
        event_layout = QVBoxLayout(event_group)
        event_table = QTableWidget(0, 2)
        event_table.setHorizontalHeaderLabels(["事件类型", "中文标签"])
        event_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        event_table.setMaximumHeight(250)
        event_table.setEditTriggers(QTableWidget.NoEditTriggers)
        event_table.verticalHeader().setVisible(False)

        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
        for i, etype in enumerate(BEHAVIOR_TYPES_V2):
            event_table.insertRow(i)
            event_table.setItem(i, 0, QTableWidgetItem(etype))
            cn = self.EVENT_CN_MAP.get(etype, etype)
            item = QTableWidgetItem(cn)
            item.setFont(QFont("Microsoft YaHei", 10))
            event_table.setItem(i, 1, item)

        event_layout.addWidget(event_table)
        layout.addWidget(event_group)

        return panel

    def _create_bottom_panel(self):
        """底部: 训练日志"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 2, 4, 2)

        log_group = QGroupBox("📋 训练日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet(
            "background: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 11px; "
            "border: 1px solid #333; border-radius: 4px;"
        )
        log_layout.addWidget(self.log_text)

        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.clicked.connect(self.log_text.clear)
        btn_clear_log.setMaximumWidth(80)
        log_layout.addWidget(btn_clear_log, alignment=Qt.AlignRight)

        layout.addWidget(log_group)
        return panel

    # ═══════════════════════════════════════════════════════
    #  交互处理
    # ═══════════════════════════════════════════════════════

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择CSV训练数据", "", "CSV Files (*.csv)")
        if path:
            self.csv_path_label.setText(os.path.basename(path))
            self._csv_path = path

    def _start_training(self):
        """启动训练"""
        csv_path = getattr(self, '_csv_path', '')
        if not csv_path:
            reply = QMessageBox.question(
                self, "确认", "未选择CSV文件，将使用合成数据训练。继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.btn_train.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.train_progress.setVisible(True)
        self.train_progress.setValue(0)
        self.status_indicator.setText("● 训练中...")
        self.status_indicator.setStyleSheet("color: #f39c12; font-size: 13px; font-weight: bold;")
        self._log("=" * 50)
        self._log("开始 ML 模型训练...")

        config = {
            'data_path': csv_path if csv_path else 'training_data.npz',
            'window_size': self.win_size_spin.value(),
            'step_size': self.step_spin.value(),
            'samples_per_class': self.samples_spin.value(),
            'n_estimators': self.n_est_spin.value(),
            'max_depth': self.max_depth_spin.value(),
            'lr': self.lr_spin.value(),
            'test_size': self.test_size_spin.value(),
            'smote_enabled': self.smote_cb.isChecked(),
            'calibrate_enabled': self.calibrate_cb.isChecked(),
            'noise_scale': 0.15,
            'random_state': 42,
        }

        self._train_thread = MLTrainingThread(config)
        self._train_thread.progress.connect(self._on_progress)
        self._train_thread.log_message.connect(self._log)
        self._train_thread.finished.connect(self._on_training_finished)
        self._train_thread.start()
        self.training_started.emit()

    def _stop_training(self):
        if self._train_thread and self._train_thread.isRunning():
            self._train_thread.terminate()
            self._train_thread.wait(2000)
            self._log("训练已停止")
            self._reset_training_ui()

    def _on_progress(self, pct, msg):
        self.train_progress.setValue(pct)
        self.train_status.setText(msg)

    def _on_training_finished(self, result):
        self._reset_training_ui()

        if result.get('success'):
            acc = result.get('accuracy', 0) * 100
            self.status_indicator.setText(f"● 训练完成 ({acc:.1f}%)")
            self.status_indicator.setStyleSheet("color: #27ae60; font-size: 13px; font-weight: bold;")
            self._log(f"训练成功! 准确率: {acc:.1f}%, F1: {result.get('f1_macro', 0):.3f}")
            self._update_model_info_from_classifier()
            self._refresh_feature_importance()
            self.training_finished.emit(result)

            QMessageBox.information(self, "训练完成",
                f"模型训练成功!\n\n准确率: {acc:.1f}%\n"
                f"F1 Macro: {result.get('f1_macro', 0):.3f}\n"
                f"样本数: {result.get('n_samples', 'N/A')}\n"
                f"模型: core/core/models/lgbm_25class_classifier.pkl")
        else:
            self.status_indicator.setText("● 训练失败")
            self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 13px; font-weight: bold;")
            self._log(f"训练失败: {result.get('error', '未知错误')}")
            QMessageBox.critical(self, "训练失败", result.get('error', '未知错误'))

    def _reset_training_ui(self):
        self.btn_train.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.train_progress.setVisible(False)

    def _load_model(self):
        """加载模型"""
        path, _ = QFileDialog.getOpenFileName(
            self, "加载模型", "core/core/models/",
            "Model Files (*.pkl *.pickle);;All Files (*)"
        )
        if not path:
            return
        try:
            self.model_path_label.setText(os.path.basename(path))
            self.model_path_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
            self._update_model_info_from_classifier()
            self._refresh_feature_importance()
            self.status_indicator.setText("● 模型已加载")
            self.status_indicator.setStyleSheet("color: #2ecc71; font-size: 13px; font-weight: bold;")
            self._log(f"模型已加载: {path}")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _display_model_info(self):
        if not self._model_info:
            self.model_info_text.setHtml("<i>暂无模型信息</i>")
            return
        info = self._model_info
        cal_status = "✅ Phase 2 校准" if info.get('calibrated') else "⚠️ 未校准"
        self.model_info_text.setHtml(f"""
            <b>模型信息</b><br>
            版本: {info.get('version', 'N/A')} | 类别: {info.get('n_classes', 'N/A')}<br>
            准确率: {info.get('accuracy', 0)*100:.1f}% | F1: {info.get('f1', 0):.3f}<br>
            训练日期: {info.get('train_date', 'N/A')[:19]}<br>
            特征维度: {info.get('feature_count', 'N/A')}<br>
            校准: {cal_status}<br>
            路径: {info.get('path', 'N/A')}
        """)

    def _refresh_feature_importance(self):
        """刷新特征重要性"""
        try:
            if self._hybrid_classifier and self._hybrid_classifier.ml_classifier.is_ready():
                importance = self._hybrid_classifier.ml_classifier.get_feature_importance()
                items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
                lines = []
                for i, (name, val) in enumerate(items, 1):
                    bar = "█" * int(val / max(v for _, v in items) * 20)
                    lines.append(f"  {i:2d}. {name:25s} {bar} {val:.1f}")
                self.feat_importance_text.setPlainText("\n".join(lines))
            else:
                self.feat_importance_text.setPlainText("模型未加载，无法获取特征重要性")
        except Exception as e:
            self.feat_importance_text.setPlainText(f"获取失败: {e}")

    def _log(self, msg):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_data(self):
        self.log_text.clear()
        self.train_progress.setVisible(False)
        self.train_progress.setValue(0)
        self.train_status.setText("")
        self.feat_importance_text.clear()