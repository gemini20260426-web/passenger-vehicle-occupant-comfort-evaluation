"""驾驶行为预测可视化界面组件（展示和分析驾驶风险预测结果）"""
import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QTabWidget, QComboBox,
                             QDateEdit, QProgressBar, QSplitter, QFrame, QTextEdit)
from PySide6.QtCore import Qt, Slot, QDateTime, QMutex, QMutexLocker, QTimer
from PySide6.QtGui import QFont, QColor, QIcon, QPainter, QPen, QBrush

# 导入图表库
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]  # 支持中文显示

class PredictionVisualizationWidget(QWidget):
    """驾驶行为预测可视化界面组件（保持原有类名）"""
    def __init__(self, prediction_engine, driver_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.prediction_engine = prediction_engine
        self.driver_manager = driver_manager
        
        # 线程安全锁（新增）
        self.widget_lock = QMutex()
        
        # 当前选中的司机和预测结果（保持原有）
        self.current_driver_id = None
        self.current_predictions = []
        self.current_risk_score = None
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 连接信号（新增）
        self._connect_signals()
        
        # 加载司机列表
        self._load_driver_list()
        
        # 启动定期刷新计时器
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(300000)  # 5分钟刷新一次
        self.refresh_timer.timeout.connect(self._refresh_predictions)
        self.refresh_timer.start()

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("驾驶行为风险预测")
        self.resize(1200, 800)
        
        # 顶部控制区域（保持原有）
        control_layout = QHBoxLayout()
        
        # 司机选择
        self.driver_combo = QComboBox()
        self.driver_combo.currentIndexChanged.connect(self._on_driver_changed)
        control_layout.addWidget(QLabel("选择司机:"))
        control_layout.addWidget(self.driver_combo)
        
        # 时间范围选择
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItem("最近6小时", 6)
        self.time_range_combo.addItem("最近12小时", 12)
        self.time_range_combo.addItem("最近24小时", 24)
        self.time_range_combo.addItem("最近48小时", 48)
        self.time_range_combo.currentIndexChanged.connect(self._on_time_range_changed)
        control_layout.addWidget(QLabel("时间范围:"))
        control_layout.addWidget(self.time_range_combo)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新预测")
        self.refresh_btn.clicked.connect(self._refresh_predictions)
        control_layout.addWidget(self.refresh_btn)
        
        # 训练模型按钮
        self.train_model_btn = QPushButton("更新预测模型")
        self.train_model_btn.clicked.connect(self._train_model)
        control_layout.addWidget(self.train_model_btn)
        
        # 模型状态
        self.model_status_label = QLabel("模型状态: 未加载")
        self.model_status_label.setStyleSheet("color: #666;")
        control_layout.addWidget(self.model_status_label)
        
        control_layout.addStretch()
        main_layout.addLayout(control_layout)
        
        # 训练进度条（新增）
        self.training_progress = QProgressBar()
        self.training_progress.setVisible(False)
        main_layout.addWidget(self.training_progress)
        
        # 创建标签页（保持原有）
        self.tab_widget = QTabWidget()
        
        # 风险概览标签页
        self.overview_tab = QWidget()
        self._init_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "风险概览")
        
        # 详细预测标签页
        self.details_tab = QWidget()
        self._init_details_tab()
        self.tab_widget.addTab(self.details_tab, "详细预测")
        
        # 风险分析标签页
        self.analysis_tab = QWidget()
        self._init_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "风险分析")
        
        # 模型信息标签页
        self.model_tab = QWidget()
        self._init_model_tab()
        self.tab_widget.addTab(self.model_tab, "模型信息")
        
        main_layout.addWidget(self.tab_widget)
        
        # 更新模型状态显示
        self._update_model_status()

    def _init_overview_tab(self) -> None:
        """初始化风险概览标签页（保持原有方法）"""
        layout = QHBoxLayout(self.overview_tab)
        
        # 左侧：风险评分卡片
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 司机信息卡片
        self.driver_info_card = QGroupBox("司机信息")
        self.driver_info_layout = QFormLayout()
        self.driver_name_label = QLabel("未选择司机")
        self.driver_id_label = QLabel("")
        self.driver_vehicle_label = QLabel("")
        self.driver_experience_label = QLabel("")
        
        self.driver_info_layout.addRow("姓名:", self.driver_name_label)
        self.driver_info_layout.addRow("ID:", self.driver_id_label)
        self.driver_info_layout.addRow("车辆:", self.driver_vehicle_label)
        self.driver_info_layout.addRow("驾龄:", self.driver_experience_label)
        self.driver_info_card.setLayout(self.driver_info_layout)
        left_layout.addWidget(self.driver_info_card)
        
        # 风险评分卡片
        self.risk_score_card = QGroupBox("整体风险评分")
        self.risk_score_card.setMinimumHeight(250)
        risk_score_layout = QVBoxLayout()
        
        # 风险评分仪表盘
        self.risk_gauge = RiskGaugeWidget()
        risk_score_layout.addWidget(self.risk_gauge)
        
        # 风险等级标签
        self.risk_level_label = QLabel("风险等级: 未评估")
        self.risk_level_label.setAlignment(Qt.AlignCenter)
        self.risk_level_label.setFont(QFont("Arial", 14, QFont.Bold))
        risk_score_layout.addWidget(self.risk_level_label)
        
        # 风险描述
        self.risk_description = QLabel("请选择司机以查看风险评估结果")
        self.risk_description.setAlignment(Qt.AlignCenter)
        self.risk_description.setWordWrap(True)
        risk_score_layout.addWidget(self.risk_description)
        
        self.risk_score_card.setLayout(risk_score_layout)
        left_layout.addWidget(self.risk_score_card)
        
        left_layout.addStretch()
        left_panel.setMinimumWidth(300)
        layout.addWidget(left_panel)
        
        # 右侧：图表区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 风险趋势图表
        self.trend_chart_card = QGroupBox("风险趋势")
        trend_layout = QVBoxLayout()
        self.trend_canvas = FigureCanvas(Figure(figsize=(6, 3)))
        trend_layout.addWidget(self.trend_canvas)
        self.trend_chart_card.setLayout(trend_layout)
        right_layout.addWidget(self.trend_chart_card)
        
        # 高风险行为统计
        self.risky_stats_card = QGroupBox("高风险行为统计")
        stats_layout = QVBoxLayout()
        self.stats_canvas = FigureCanvas(Figure(figsize=(6, 3)))
        stats_layout.addWidget(self.stats_canvas)
        self.risky_stats_card.setLayout(stats_layout)
        right_layout.addWidget(self.risky_stats_card)
        
        layout.addWidget(right_panel)

    def _init_details_tab(self) -> None:
        """初始化详细预测标签页（保持原有方法）"""
        layout = QVBoxLayout(self.details_tab)
        
        # 风险记录表格
        self.predictions_table = QTableWidget()
        self.predictions_table.setColumnCount(6)
        self.predictions_table.setHorizontalHeaderLabels(["时间", "位置", "速度(km/h)", "加速度(m/s²)", "风险概率", "风险等级"])
        self.predictions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.predictions_table.cellClicked.connect(self._on_prediction_selected)
        layout.addWidget(self.predictions_table)
        
        # 详细信息面板
        self.detail_panel = QGroupBox("详细信息")
        detail_layout = QVBoxLayout()
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)
        
        self.detail_panel.setLayout(detail_layout)
        self.detail_panel.setVisible(False)
        layout.addWidget(self.detail_panel)

    def _init_analysis_tab(self) -> None:
        """初始化风险分析标签页（新增）"""
        layout = QVBoxLayout(self.analysis_tab)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 风险因素分析
        factors_panel = QWidget()
        factors_layout = QVBoxLayout(factors_panel)
        
        factors_card = QGroupBox("主要风险因素")
        factors_card_layout = QVBoxLayout()
        self.factors_canvas = FigureCanvas(Figure(figsize=(8, 4)))
        factors_card_layout.addWidget(self.factors_canvas)
        factors_card.setLayout(factors_card_layout)
        factors_layout.addWidget(factors_card)
        
        splitter.addWidget(factors_panel)
        
        # 时段风险分析
        hourly_panel = QWidget()
        hourly_layout = QVBoxLayout(hourly_panel)
        
        hourly_card = QGroupBox("时段风险分布")
        hourly_card_layout = QVBoxLayout()
        self.hourly_canvas = FigureCanvas(Figure(figsize=(8, 4)))
        hourly_card_layout.addWidget(self.hourly_canvas)
        hourly_card.setLayout(hourly_card_layout)
        hourly_layout.addWidget(hourly_card)
        
        splitter.addWidget(hourly_panel)
        
        layout.addWidget(splitter)

    def _init_model_tab(self) -> None:
        """初始化模型信息标签页（新增）"""
        layout = QVBoxLayout(self.model_tab)
        
        # 模型状态信息
        model_info_card = QGroupBox("模型状态")
        model_info_layout = QFormLayout()
        
        self.model_type_label = QLabel("未加载")
        self.model_loaded_label = QLabel("否")
        self.model_trained_label = QLabel("从未训练")
        self.model_features_label = QLabel("0")
        
        model_info_layout.addRow("模型类型:", self.model_type_label)
        model_info_layout.addRow("是否加载:", self.model_loaded_label)
        model_info_layout.addRow("最后训练时间:", self.model_trained_label)
        model_info_layout.addRow("特征数量:", self.model_features_label)
        
        model_info_card.setLayout(model_info_layout)
        layout.addWidget(model_info_card)
        
        # 模型性能
        performance_card = QGroupBox("模型性能")
        performance_layout = QVBoxLayout()
        
        self.performance_canvas = FigureCanvas(Figure(figsize=(8, 3)))
        performance_layout.addWidget(self.performance_canvas)
        
        # 性能指标
        metrics_layout = QHBoxLayout()
        
        self.accuracy_label = QLabel("准确率: --")
        self.precision_label = QLabel("精确率: --")
        self.recall_label = QLabel("召回率: --")
        self.f1_label = QLabel("F1分数: --")
        
        metrics_layout.addWidget(self.accuracy_label)
        metrics_layout.addWidget(self.precision_label)
        metrics_layout.addWidget(self.recall_label)
        metrics_layout.addWidget(self.f1_label)
        
        performance_layout.addLayout(metrics_layout)
        performance_card.setLayout(performance_layout)
        layout.addWidget(performance_card)
        
        # 训练历史
        history_card = QGroupBox("训练历史")
        history_layout = QVBoxLayout()
        
        self.training_history_table = QTableWidget()
        self.training_history_table.setColumnCount(5)
        self.training_history_table.setHorizontalHeaderLabels(["训练时间", "准确率", "精确率", "召回率", "F1分数"])
        self.training_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_layout.addWidget(self.training_history_table)
        
        history_card.setLayout(history_layout)
        layout.addWidget(history_card)
        
        layout.addStretch()

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 预测引擎信号
        self.prediction_engine.prediction_updated.connect(self._on_predictions_updated)
        self.prediction_engine.model_trained.connect(self._on_model_trained)
        self.prediction_engine.training_progress.connect(self._on_training_progress)
        self.prediction_engine.error_occurred.connect(self._on_error_occurred)

    def _load_driver_list(self) -> None:
        """加载司机列表（保持原有方法）"""
        try:
            # 保存当前选择
            current_id = self.driver_combo.currentData()
            
            # 清空下拉框
            self.driver_combo.clear()
            self.driver_combo.addItem("请选择司机", None)
            
            # 获取司机列表
            drivers = self.driver_manager.get_all_drivers()
            
            # 添加到下拉框
            for driver in drivers:
                self.driver_combo.addItem(
                    f"{driver.get('name', '未知')} ({driver.get('id', '未知')})",
                    driver.get('id')
                )
            
            # 恢复选择
            if current_id:
                index = self.driver_combo.findData(current_id)
                if index >= 0:
                    self.driver_combo.setCurrentIndex(index)
                
        except Exception as e:
            self.logger.error(f"加载司机列表失败: {str(e)}")
            QMessageBox.warning(self, "加载失败", f"加载司机列表失败: {str(e)}")

    def _update_driver_info(self, driver_id: str) -> None:
        """更新司机信息（保持原有方法）"""
        if not driver_id:
            # 重置信息
            self.driver_name_label.setText("未选择司机")
            self.driver_id_label.setText("")
            self.driver_vehicle_label.setText("")
            self.driver_experience_label.setText("")
            return
            
        # 获取司机信息
        driver_info = self.driver_manager.get_driver_info(driver_id)
        if not driver_info:
            self.driver_name_label.setText("司机信息不存在")
            self.driver_id_label.setText(driver_id)
            self.driver_vehicle_label.setText("")
            self.driver_experience_label.setText("")
            return
            
        # 更新信息
        self.driver_name_label.setText(driver_info.get('name', '未知'))
        self.driver_id_label.setText(driver_info.get('id', ''))
        self.driver_vehicle_label.setText(driver_info.get('vehicle', '未知'))
        self.driver_experience_label.setText(f"{driver_info.get('experience', 0)} 年")

    def _refresh_predictions(self) -> None:
        """刷新预测结果（保持原有方法）"""
        driver_id = self.driver_combo.currentData()
        hours = self.time_range_combo.currentData()
        
        if not driver_id or not hours:
            return
            
        # 显示加载状态
        self.model_status_label.setText("正在生成风险预测...")
        
        # 保存当前司机ID
        self.current_driver_id = driver_id
        
        # 触发预测
        with QMutexLocker(self.widget_lock):
            predictions = self.prediction_engine.predict_behavior(driver_id, hours)
            
            # 如果预测结果立即可得（非异步），直接更新
            if predictions:
                self._on_predictions_updated(predictions)
            
            # 获取风险评分
            self.current_risk_score = self.prediction_engine.get_driver_risk_score(driver_id)
            self._update_risk_score_display()

    def _update_risk_score_display(self) -> None:
        """更新风险评分显示（新增）"""
        if not self.current_risk_score:
            self.risk_gauge.set_value(0)
            self.risk_level_label.setText("风险等级: 未评估")
            self.risk_description.setText("请选择司机以查看风险评估结果")
            return
            
        # 更新仪表盘
        risk_score = self.current_risk_score['overall_risk']
        self.risk_gauge.set_value(risk_score)
        
        # 更新风险等级
        risk_level = self.current_risk_score['risk_level']
        self.risk_level_label.setText(f"风险等级: {risk_level}")
        
        # 设置风险等级颜色
        if risk_level == "高":
            self.risk_level_label.setStyleSheet("color: #f44336; font-size: 14pt; font-weight: bold;")
        elif risk_level == "中":
            self.risk_level_label.setStyleSheet("color: #ff9800; font-size: 14pt; font-weight: bold;")
        else:
            self.risk_level_label.setStyleSheet("color: #4caf50; font-size: 14pt; font-weight: bold;")
        
        # 更新风险描述
        risky_count = self.current_risk_score['risky_behavior_count']
        total = self.current_risk_score['total_records']
        ratio = self.current_risk_score['risky_behavior_ratio']
        
        self.risk_description.setText(
            f"在{self.current_risk_score['evaluation_period']}内，共记录了{total}条驾驶行为数据，\n"
            f"其中高风险行为{risky_count}条，占比{ratio}%。\n"
            f"评估时间: {self.current_risk_score['evaluation_time_str']}"
        )
        
        # 更新图表
        self._update_trend_chart()
        self._update_risky_stats_chart()
        self._update_risk_factors_chart()
        self._update_hourly_risk_chart()

    def _update_trend_chart(self) -> None:
        """更新风险趋势图表（新增）"""
        if not self.current_predictions or len(self.current_predictions) < 2:
            self.trend_canvas.figure.clear()
            ax = self.trend_canvas.figure.add_subplot(111)
            ax.set_title("暂无足够数据显示风险趋势")
            self.trend_canvas.draw()
            return
            
        # 准备数据
        predictions_sorted = sorted(self.current_predictions, key=lambda x: x['timestamp'])
        timestamps = [p['timestamp_str'] for p in predictions_sorted]
        risk_values = [p['risk_probability'] * 100 for p in predictions_sorted]
        
        # 简化时间标签（每5个显示一个）
        if len(timestamps) > 10:
            show_indices = range(0, len(timestamps), max(1, len(timestamps) // 10))
            show_timestamps = [timestamps[i] for i in show_indices]
            show_x = [i for i in show_indices]
        else:
            show_timestamps = timestamps
            show_x = range(len(timestamps))
        
        # 绘制图表
        self.trend_canvas.figure.clear()
        ax = self.trend_canvas.figure.add_subplot(111)
        ax.plot(risk_values, 'b-', linewidth=2)
        ax.set_title("驾驶风险趋势")
        ax.set_ylabel("风险概率 (%)")
        ax.set_ylim(0, 100)
        ax.set_xticks(show_x)
        ax.set_xticklabels(show_timestamps, rotation=45, ha='right')
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # 添加高风险阈值线
        ax.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='高风险阈值')
        ax.legend()
        
        self.trend_canvas.figure.tight_layout()
        self.trend_canvas.draw()

    def _update_risky_stats_chart(self) -> None:
        """更新高风险行为统计图表（新增）"""
        if not self.current_risk_score:
            self.stats_canvas.figure.clear()
            ax = self.stats_canvas.figure.add_subplot(111)
            ax.set_title("暂无数据显示高风险行为统计")
            self.stats_canvas.draw()
            return
            
        # 准备数据
        risky_count = self.current_risk_score['risky_behavior_count']
        total_count = self.current_risk_score['total_records']
        safe_count = total_count - risky_count
        
        # 绘制图表
        self.stats_canvas.figure.clear()
        ax = self.stats_canvas.figure.add_subplot(111)
        ax.pie(
            [safe_count, risky_count],
            labels=['安全行为', '高风险行为'],
            autopct='%1.1f%%',
            colors=['#4caf50', '#f44336'],
            startangle=90
        )
        ax.set_title(f"行为分布 (总计: {total_count}条)")
        
        self.stats_canvas.figure.tight_layout()
        self.stats_canvas.draw()

    def _update_risk_factors_chart(self) -> None:
        """更新风险因素分析图表（新增）"""
        if not self.current_risk_score or not self.current_risk_score.get('risk_factors'):
            self.factors_canvas.figure.clear()
            ax = self.factors_canvas.figure.add_subplot(111)
            ax.set_title("暂无数据显示风险因素分析")
            self.factors_canvas.draw()
            return
            
        # 准备数据
        factors = self.current_risk_score['risk_factors']
        descriptions = [f['description'] for f in factors]
        contributions = [f['contribution'] for f in factors]
        risk_ratios = [f['risk_ratio'] for f in factors]
        
        # 绘制图表
        self.factors_canvas.figure.clear()
        ax = self.factors_canvas.figure.add_subplot(111)
        
        x = np.arange(len(descriptions))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, contributions, width, label='风险贡献度 (%)')
        bars2 = ax.bar(x + width/2, risk_ratios, width, label='风险发生率 (%)')
        
        ax.set_title("主要风险因素分析")
        ax.set_xticks(x)
        ax.set_xticklabels(descriptions, rotation=30, ha='right')
        ax.legend()
        
        # 在柱状图上添加数值标签
        def add_bar_labels(bars):
            for bar in bars:
                height = bar.get_height()
                ax.annotate(f'{height:.1f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),  # 3 points vertical offset
                           textcoords="offset points",
                           ha='center', va='bottom')
        
        add_bar_labels(bars1)
        add_bar_labels(bars2)
        
        self.factors_canvas.figure.tight_layout()
        self.factors_canvas.draw()

    def _update_hourly_risk_chart(self) -> None:
        """更新时段风险分布图表（新增）"""
        if not self.current_risk_score or not self.current_risk_score.get('hourly_risk'):
            self.hourly_canvas.figure.clear()
            ax = self.hourly_canvas.figure.add_subplot(111)
            ax.set_title("暂无数据显示时段风险分布")
            self.hourly_canvas.draw()
            return
            
        # 准备数据
        hourly_data = self.current_risk_score['hourly_risk']
        hourly_data.sort(key=lambda x: x['hour'])
        
        hours = [item['hour_str'] for item in hourly_data]
        avg_risk = [item['avg_risk'] for item in hourly_data]
        risky_ratio = [item['risky_ratio'] for item in hourly_data]
        
        # 绘制图表
        self.hourly_canvas.figure.clear()
        ax = self.hourly_canvas.figure.add_subplot(111)
        
        x = np.arange(len(hours))
        width = 0.4
        
        bars1 = ax.bar(x - width/2, avg_risk, width, label='平均风险 (%)')
        bars2 = ax.bar(x + width/2, risky_ratio, width, label='高风险占比 (%)')
        
        ax.set_title("时段风险分布")
        ax.set_xticks(x)
        ax.set_xticklabels(hours, rotation=45, ha='right')
        ax.set_ylim(0, 100)
        ax.legend()
        
        self.hourly_canvas.figure.tight_layout()
        self.hourly_canvas.draw()

    def _update_model_status(self) -> None:
        """更新模型状态显示（新增）"""
        status = self.prediction_engine.get_model_status()
        
        self.model_type_label.setText(status['model_type'])
        self.model_loaded_label.setText("是" if status['loaded'] else "否")
        self.model_loaded_label.setStyleSheet(
            "color: #4caf50;" if status['loaded'] else "color: #f44336;"
        )
        self.model_trained_label.setText(status['last_trained_str'])
        self.model_features_label.setText(str(status['feature_count']))
        
        self.model_status_label.setText(f"模型状态: {'已加载' if status['loaded'] else '未加载'}")
        
        # 清除性能图表
        self.performance_canvas.figure.clear()
        ax = self.performance_canvas.figure.add_subplot(111)
        ax.set_title("暂无模型性能数据")
        self.performance_canvas.draw()
        
        # 清除指标
        self.accuracy_label.setText("准确率: --")
        self.precision_label.setText("精确率: --")
        self.recall_label.setText("召回率: --")
        self.f1_label.setText("F1分数: --")

    def _train_model(self) -> None:
        """训练预测模型（新增）"""
        # 询问用户
        reply = QMessageBox.question(
            self, "确认训练",
            "确定要更新预测模型吗？这可能需要几分钟时间。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 显示进度条
            self.training_progress.setVisible(True)
            self.training_progress.setValue(0)
            self.train_model_btn.setEnabled(False)
            
            # 启动训练
            self.prediction_engine.train_model(days=30)  # 使用最近30天的数据

    @Slot(int, str)
    def _on_training_progress(self, progress: int, message: str) -> None:
        """处理训练进度更新（新增）"""
        self.training_progress.setValue(progress)
        self.model_status_label.setText(f"模型训练中: {message}")
        
        if progress == 100:
            self.train_model_btn.setEnabled(True)
            self._update_model_status()

    @Slot(float, float, float, float)
    def _on_model_trained(self, accuracy: float, precision: float, recall: float, f1: float) -> None:
        """处理模型训练完成（新增）"""
        # 更新性能指标
        self.accuracy_label.setText(f"准确率: {accuracy:.2%}")
        self.precision_label.setText(f"精确率: {precision:.2%}")
        self.recall_label.setText(f"召回率: {recall:.2%}")
        self.f1_label.setText(f"F1分数: {f1:.4f}")
        
        # 更新性能图表
        self.performance_canvas.figure.clear()
        ax = self.performance_canvas.figure.add_subplot(111)
        
        metrics = ['准确率', '精确率', '召回率']
        values = [accuracy, precision, recall]
        
        ax.bar(metrics, values, color=['#4caf50', '#2196f3', '#ff9800'])
        ax.set_ylim(0, 1.0)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ax.set_title("模型性能指标")
        
        # 添加数值标签
        for i, v in enumerate(values):
            ax.text(i, v + 0.01, f"{v:.2%}", ha='center')
        
        self.performance_canvas.figure.tight_layout()
        self.performance_canvas.draw()
        
        # 添加到训练历史
        row = self.training_history_table.rowCount()
        self.training_history_table.insertRow(row)
        
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm")
        self.training_history_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.training_history_table.setItem(row, 1, QTableWidgetItem(f"{accuracy:.4f}"))
        self.training_history_table.setItem(row, 2, QTableWidgetItem(f"{precision:.4f}"))
        self.training_history_table.setItem(row, 3, QTableWidgetItem(f"{recall:.4f}"))
        self.training_history_table.setItem(row, 4, QTableWidgetItem(f"{f1:.4f}"))
        
        # 刷新当前预测
        self._refresh_predictions()

    @Slot(list)
    def _on_predictions_updated(self, predictions: List[Dict[str, Any]]) -> None:
        """处理预测结果更新（保持原有方法）"""
        with QMutexLocker(self.widget_lock):
            self.current_predictions = predictions
        
        # 更新表格
        self.predictions_table.setRowCount(0)
        
        for i, pred in enumerate(predictions):
            self.predictions_table.insertRow(i)
            
            # 时间
            time_item = QTableWidgetItem(pred['timestamp_str'])
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.predictions_table.setItem(i, 0, time_item)
            
            # 位置
            loc_item = QTableWidgetItem(pred['location'])
            loc_item.setFlags(loc_item.flags() & ~Qt.ItemIsEditable)
            self.predictions_table.setItem(i, 1, loc_item)
            
            # 速度
            speed_item = QTableWidgetItem(f"{pred['speed']:.1f}")
            speed_item.setTextAlignment(Qt.AlignRight)
            speed_item.setFlags(speed_item.flags() & ~Qt.ItemIsEditable)
            self.predictions_table.setItem(i, 2, speed_item)
            
            # 加速度
            accel_item = QTableWidgetItem(f"{pred['acceleration']:.2f}")
            accel_item.setTextAlignment(Qt.AlignRight)
            accel_item.setFlags(accel_item.flags() & ~Qt.ItemIsEditable)
            self.predictions_table.setItem(i, 3, accel_item)
            
            # 风险概率
            prob_item = QTableWidgetItem(f"{pred['risk_probability']:.2%}")
            prob_item.setTextAlignment(Qt.AlignRight)
            prob_item.setFlags(prob_item.flags() & ~Qt.ItemIsEditable)
            
            # 设置颜色
            if pred['risk_probability'] > 0.7:
                prob_item.setBackground(QColor(255, 220, 220))  # 浅红
            elif pred['risk_probability'] > 0.3:
                prob_item.setBackground(QColor(255, 255, 220))  # 浅黄
            else:
                prob_item.setBackground(QColor(220, 255, 220))  # 浅绿
                
            self.predictions_table.setItem(i, 4, prob_item)
            
            # 风险等级
            level_item = QTableWidgetItem(pred['risk_level'])
            level_item.setTextAlignment(Qt.AlignCenter)
            level_item.setFlags(level_item.flags() & ~Qt.ItemIsEditable)
            
            # 设置颜色
            if pred['risk_level'] == "高":
                level_item.setBackground(QColor(255, 220, 220))
                level_item.setForeground(QColor(180, 0, 0))
            elif pred['risk_level'] == "中":
                level_item.setBackground(QColor(255, 255, 220))
                level_item.setForeground(QColor(180, 120, 0))
            else:
                level_item.setBackground(QColor(220, 255, 220))
                level_item.setForeground(QColor(0, 120, 0))
                
            self.predictions_table.setItem(i, 5, level_item)
        
        # 更新模型状态
        self.model_status_label.setText("模型状态: 已加载")
        
        # 更新风险评分
        if self.current_driver_id:
            self.current_risk_score = self.prediction_engine.get_driver_risk_score(self.current_driver_id)
            self._update_risk_score_display()

    @Slot(int, int)
    def _on_prediction_selected(self, row: int, column: int) -> None:
        """处理预测记录选中（新增）"""
        if row < 0 or row >= len(self.current_predictions):
            self.detail_panel.setVisible(False)
            return
            
        pred = self.current_predictions[row]
        self.detail_panel.setVisible(True)
        
        # 构建详细信息文本
        detail_text = f"""时间: {pred['timestamp_str']}
位置: {pred['location']}
速度: {pred['speed']:.1f} km/h
加速度: {pred['acceleration']:.2f} m/s²
风险概率: {pred['risk_probability']:.2%}
风险等级: {pred['risk_level']}

风险评估:
"""
        if pred['risk_probability'] > 0.7:
            detail_text += "该驾驶行为被评估为高风险，可能存在安全隐患，建议司机注意驾驶习惯。"
        elif pred['risk_probability'] > 0.3:
            detail_text += "该驾驶行为被评估为中等风险，司机应适当调整驾驶方式，确保安全。"
        else:
            detail_text += "该驾驶行为被评估为低风险，驾驶状态良好，请继续保持。"
            
        self.detail_text.setText(detail_text)

    @Slot(int)
    def _on_driver_changed(self, index: int) -> None:
        """处理司机选择变化（保持原有方法）"""
        driver_id = self.driver_combo.currentData()
        self._update_driver_info(driver_id)
        
        if driver_id:
            self._refresh_predictions()
        else:
            # 重置显示
            with QMutexLocker(self.widget_lock):
                self.current_predictions = []
                self.current_risk_score = None
                self.current_driver_id = None
                
            self.predictions_table.setRowCount(0)
            self._update_risk_score_display()
            self.detail_panel.setVisible(False)

    @Slot(int)
    def _on_time_range_changed(self, index: int) -> None:
        """处理时间范围变化（新增）"""
        if self.current_driver_id:
            self._refresh_predictions()

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        """处理错误信息（新增）"""
        QMessageBox.warning(self, "操作失败", message)
        self.model_status_label.setText(f"错误: {message}")
        self.training_progress.setVisible(False)
        self.train_model_btn.setEnabled(True)


class RiskGaugeWidget(QWidget):
    """风险评分仪表盘组件（新增）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.setMinimumSize(200, 200)
        
    def set_value(self, value: float) -> None:
        """设置仪表盘值"""
        self.value = max(0, min(100, value))  # 限制在0-100之间
        self.update()  # 触发重绘
        
    def paintEvent(self, event) -> None:
        """绘制仪表盘"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        
        # 获取控件尺寸
        width = self.width()
        height = self.height()
        size = min(width, height)
        center_x = width // 2
        center_y = height // 2
        
        # 绘制外圆
        painter.setPen(QPen(QColor(200, 200, 200), 10))
        painter.drawEllipse(
            center_x - size//2 + 10,
            center_y - size//2 + 10,
            size - 20,
            size - 20
        )
        
        # 绘制颜色刻度
        painter.save()
        painter.translate(center_x, center_y)
        
        # 计算角度范围（120度到-120度，共240度）
        start_angle = 120 * 16
        span_angle = -240 * 16
        
        # 绘制绿色区域（0-30）
        painter.setPen(QPen(QColor(76, 175, 80), 8))
        painter.drawArc(
            -size//2 + 15,
            -size//2 + 15,
            size - 30,
            size - 30,
            start_angle,
            int(span_angle * 0.3)
        )
        
        # 绘制黄色区域（30-60）
        painter.setPen(QPen(QColor(255, 152, 0), 8))
        painter.drawArc(
            -size//2 + 15,
            -size//2 + 15,
            size - 30,
            size - 30,
            start_angle + int(span_angle * 0.3),
            int(span_angle * 0.3)
        )
        
        # 绘制红色区域（60-100）
        painter.setPen(QPen(QColor(244, 67, 54), 8))
        painter.drawArc(
            -size//2 + 15,
            -size//2 + 15,
            size - 30,
            size - 30,
            start_angle + int(span_angle * 0.6),
            int(span_angle * 0.4)
        )
        
        # 绘制指针
        painter.save()
        # 计算角度（值从0-100映射到120度到-120度）
        angle = 120.0 - (self.value / 100.0) * 240.0
        painter.rotate(angle)
        
        # 设置指针样式
        painter.setPen(QPen(QColor(50, 50, 50), 3))
        painter.drawLine(0, 0, 0, -size//2 + 30)
        painter.restore()
        
        painter.restore()
        
        # 绘制中心圆
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.setBrush(QBrush(QColor(240, 240, 240)))
        painter.drawEllipse(center_x - 10, center_y - 10, 20, 20)
        
        # 绘制数值文本
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        text = f"{self.value:.1f}"
        text_rect = painter.boundingRect(0, 0, 100, 30, Qt.AlignCenter, text)
        painter.drawText(
            center_x - text_rect.width()//2,
            center_y + text_rect.height()//2,
            text
        )
        
        # 绘制百分号
        painter.setFont(QFont("Arial", 12))
        painter.drawText(
            center_x + text_rect.width()//2,
            center_y + 5,
            "%"
        )
