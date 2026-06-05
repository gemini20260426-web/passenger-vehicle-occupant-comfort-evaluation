"""驾驶行为评估报告组件（展示详细评估结果）"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
                             QGroupBox, QDateEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, Slot, QDate, QMutex, QMutexLocker
from PySide6.QtGui import QFont, QColor, QPixmap, QIcon

class EvaluationReportWidget(QWidget):
    """驾驶行为评估报告组件（保持原有类名）"""
    def __init__(self, evaluator, data_storage):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.evaluator = evaluator
        self.data_storage = data_storage
        
        # 线程安全锁（新增）
        self.report_lock = QMutex()
        
        # 当前报告数据（保持原有）
        self.current_report = None
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 连接信号（新增）
        self._connect_signals()

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        
        # 筛选区域（保持原有）
        filter_layout = QHBoxLayout()
        
        # 时间范围选择（保持原有）
        filter_layout.addWidget(QLabel("报告周期:"))
        self.period_combo = QComboBox()
        self.period_combo.addItem("今日", "today")
        self.period_combo.addItem("昨日", "yesterday")
        self.period_combo.addItem("本周", "week")
        self.period_combo.addItem("本月", "month")
        self.period_combo.addItem("自定义", "custom")
        filter_layout.addWidget(self.period_combo)
        
        # 自定义日期范围（保持原有）
        self.start_date_edit = QDateEdit(QDate.currentDate())
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setVisible(False)  # 初始隐藏
        filter_layout.addWidget(self.start_date_edit)
        
        filter_layout.addWidget(QLabel("至"))
        
        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setVisible(False)  # 初始隐藏
        filter_layout.addWidget(self.end_date_edit)
        
        # 生成报告按钮（保持原有）
        self.generate_btn = QPushButton("生成报告")
        self.generate_btn.clicked.connect(self._generate_report)
        filter_layout.addWidget(self.generate_btn)
        
        # 导出报告按钮（保持原有）
        self.export_btn = QPushButton("导出报告")
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setEnabled(False)  # 初始禁用
        filter_layout.addWidget(self.export_btn)
        
        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)
        
        # 报告内容区域（保持原有）
        # 评分摘要
        summary_group = QGroupBox("评分摘要")
        summary_layout = QHBoxLayout()
        
        # 综合评分
        self.score_label = QLabel("0")
        self.score_label.setFont(QFont("Arial", 48, QFont.Bold))
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setMinimumWidth(150)
        summary_layout.addWidget(self.score_label)
        
        # 评分等级和描述
        self.grade_label = QLabel("未评估")
        self.grade_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.grade_label.setAlignment(Qt.AlignCenter)
        
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMinimumHeight(100)
        
        grade_layout = QVBoxLayout()
        grade_layout.addWidget(self.grade_label)
        grade_layout.addWidget(self.desc_text)
        summary_layout.addLayout(grade_layout)
        
        summary_group.setLayout(summary_layout)
        main_layout.addWidget(summary_group)
        
        # 行为统计表格（保持原有）
        self.behavior_table = QTableWidget()
        self.behavior_table.setColumnCount(4)
        self.behavior_table.setHorizontalHeaderLabels(["行为类型", "发生次数", "占比", "风险指数"])
        self.behavior_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.behavior_table)
        
        # 趋势图表区域（保持原有）
        trend_group = QGroupBox("评分趋势")
        trend_layout = QVBoxLayout()
        
        # 这里使用占位标签代替实际图表组件（保持原有）
        self.trend_label = QLabel("评分趋势图表将显示在这里")
        self.trend_label.setAlignment(Qt.AlignCenter)
        self.trend_label.setMinimumHeight(200)
        self.trend_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        trend_layout.addWidget(self.trend_label)
        
        trend_group.setLayout(trend_layout)
        main_layout.addWidget(trend_group)
        
        # 改进建议（保持原有）
        advice_group = QGroupBox("改进建议")
        advice_layout = QVBoxLayout()
        
        self.advice_text = QTextEdit()
        self.advice_text.setReadOnly(True)
        advice_layout.addWidget(self.advice_text)
        
        advice_group.setLayout(advice_layout)
        main_layout.addWidget(advice_group)

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 周期选择变化时显示/隐藏自定义日期
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        # 评估器结果更新时刷新报告
        self.evaluator.evaluation_updated.connect(self._on_evaluation_updated)

    @Slot(int)
    def _on_period_changed(self, index: int) -> None:
        """处理周期选择变化（保持原有方法）"""
        period_type = self.period_combo.itemData(index)
        # 显示/隐藏自定义日期
        self.start_date_edit.setVisible(period_type == "custom")
        self.end_date_edit.setVisible(period_type == "custom")

    @Slot()
    def _generate_report(self) -> None:
        """生成评估报告（保持原有方法）"""
        # 获取时间范围（原有逻辑）
        period_type = self.period_combo.currentData()
        start_date, end_date = self._get_date_range(period_type)
        
        # 显示加载状态
        self._show_loading_state()
        
        # 在单独线程中生成报告（避免UI冻结）
        import threading
        threading.Thread(
            target=self._do_generate_report,
            args=(start_date, end_date),
            daemon=True
        ).start()

    def _do_generate_report(self, start_date: str, end_date: str) -> None:
        """执行报告生成（新增线程安全实现）"""
        try:
            # 从数据存储获取所需数据
            report_data = self._fetch_report_data(start_date, end_date)
            
            # 生成报告内容
            report = self._compile_report(report_data)
            
            # 保存报告并更新UI
            with QMutexLocker(self.report_lock):
                self.current_report = report
            
            # 在UI线程更新显示
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self, 
                lambda: self._update_report_display(report),
                Qt.QueuedConnection
            )
            
        except Exception as e:
            self.logger.error(f"报告生成失败: {str(e)}")
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self, 
                lambda: QMessageBox.warning(self, "生成失败", f"报告生成失败: {str(e)}"),
                Qt.QueuedConnection
            )

    def _fetch_report_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """获取报告所需数据（保持原有方法）"""
        # 从数据存储获取指定日期范围的数据
        behavior_events = self.data_storage.get_behavior_events_by_date(start_date, end_date)
        evaluation_history = self.evaluator.get_evaluation_history()
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'behavior_events': behavior_events,
            'evaluation_history': evaluation_history
        }

    def _compile_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """编译报告内容（保持原有逻辑）"""
        # 统计行为事件
        behavior_counts = {
            'hard_acceleration': 0,
            'hard_braking': 0,
            'sharp_turning': 0,
            'overspeeding': 0
        }
        
        for event in data['behavior_events']:
            event_type = event.get('event_type')
            if event_type in behavior_counts:
                behavior_counts[event_type] += 1
        
        # 计算总分（使用最近的评估结果）
        total_score = 0
        if data['evaluation_history']:
            total_score = data['evaluation_history'][-1].get('overall_score', 0)
        
        # 生成报告
        return {
            'period': f"{data['start_date']} 至 {data['end_date']}",
            'total_score': round(total_score, 1),
            'behavior_counts': behavior_counts,
            'total_events': sum(behavior_counts.values()),
            'evaluation_history': data['evaluation_history']
        }

    def _update_report_display(self, report: Dict[str, Any]) -> None:
        """更新报告显示（保持原有方法）"""
        # 更新综合评分
        self.score_label.setText(f"{report['total_score']}")
        
        # 设置评分颜色
        score = report['total_score']
        if score >= 90:
            self.score_label.setStyleSheet("color: green;")
            self.grade_label.setText("优秀")
        elif score >= 80:
            self.score_label.setStyleSheet("color: #4CAF50;")
            self.grade_label.setText("良好")
        elif score >= 70:
            self.score_label.setStyleSheet("color: #FFC107;")
            self.grade_label.setText("一般")
        elif score >= 60:
            self.score_label.setStyleSheet("color: #FF9800;")
            self.grade_label.setText("较差")
        else:
            self.score_label.setStyleSheet("color: #F44336;")
            self.grade_label.setText("差")
        
        # 更新描述
        self.desc_text.setPlainText(f"评估周期: {report['period']}\n"
                                   f"期间共检测到 {report['total_events']} 次不良驾驶行为")
        
        # 更新行为统计表格
        self.behavior_table.setRowCount(0)
        total = report['total_events'] or 1  # 避免除以零
        
        behavior_info = [
            ('hard_acceleration', '急加速', '#F44336'),
            ('hard_braking', '急刹车', '#FF9800'),
            ('sharp_turning', '急转弯', '#FFC107'),
            ('overspeeding', '超速', '#4CAF50')
        ]
        
        for i, (event_type, display_name, color) in enumerate(behavior_info):
            count = report['behavior_counts'][event_type]
            percentage = (count / total) * 100
            risk_index = min(10, count // 5)  # 每5次加1，最高10
            
            self.behavior_table.insertRow(i)
            
            # 行为类型
            type_item = QTableWidgetItem(display_name)
            type_item.setTextAlignment(Qt.AlignCenter)
            self.behavior_table.setItem(i, 0, type_item)
            
            # 发生次数
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.behavior_table.setItem(i, 1, count_item)
            
            # 占比
            percent_item = QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setTextAlignment(Qt.AlignCenter)
            self.behavior_table.setItem(i, 2, percent_item)
            
            # 风险指数
            risk_item = QTableWidgetItem(str(risk_index))
            risk_item.setTextAlignment(Qt.AlignCenter)
            risk_item.setBackground(QColor(color))
            self.behavior_table.setItem(i, 3, risk_item)
        
        # 更新趋势图表（这里仅更新文本提示）
        if report['evaluation_history'] and len(report['evaluation_history']) >= 2:
            self.trend_label.setText(f"评分趋势: 从 {report['evaluation_history'][0]['overall_score']} "
                                    f"到 {report['evaluation_history'][-1]['overall_score']}")
        else:
            self.trend_label.setText("数据不足，无法显示趋势")
        
        # 更新改进建议
        self._update_advice(report)
        
        # 启用导出按钮
        self.export_btn.setEnabled(True)

    def _update_advice(self, report: Dict[str, Any]) -> None:
        """更新改进建议（保持原有逻辑）"""
        advice = []
        
        # 根据主要问题生成建议
        behavior_advice = {
            'hard_acceleration': "减少急加速行为，平稳起步可以提高燃油效率并降低事故风险。",
            'hard_braking': "提前预判路况，避免急刹车，保护刹车片并提高乘客舒适性。",
            'sharp_turning': "转弯时减速，避免急转弯，特别是在湿滑路面上。",
            'overspeeding': "遵守限速规定，超速会显著增加事故风险和制动距离。"
        }
        
        # 找出最频繁的行为
        sorted_behaviors = sorted(
            report['behavior_counts'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 添加针对性建议
        for behavior, count in sorted_behaviors[:2]:  # 前两项主要问题
            if count > 0:
                advice.append(f"- {behavior_advice[behavior]}")
        
        # 添加总体建议
        if report['total_score'] >= 90:
            advice.append("\n继续保持优秀的驾驶习惯！定期检查车辆状况以维持良好状态。")
        elif report['total_score'] >= 70:
            advice.append("\n总体驾驶行为良好，注意改进上述问题可进一步提高安全性。")
        else:
            advice.append("\n建议参加 defensive driving 培训，改善驾驶习惯，提高安全性。")
        
        self.advice_text.setPlainText("\n".join(advice))

    def _get_date_range(self, period_type: str) -> Tuple[str, str]:
        """获取日期范围（保持原有方法）"""
        today = QDate.currentDate()
        
        if period_type == "today":
            start = today.toString("yyyy-MM-dd")
            end = today.toString("yyyy-MM-dd")
        elif period_type == "yesterday":
            yesterday = today.addDays(-1)
            start = yesterday.toString("yyyy-MM-dd")
            end = yesterday.toString("yyyy-MM-dd")
        elif period_type == "week":
            # 本周一
            monday = today.addDays(-(today.dayOfWeek() - 1))
            start = monday.toString("yyyy-MM-dd")
            end = today.toString("yyyy-MM-dd")
        elif period_type == "month":
            # 本月第一天
            first_day = QDate(today.year(), today.month(), 1)
            start = first_day.toString("yyyy-MM-dd")
            end = today.toString("yyyy-MM-dd")
        else:  # custom
            start = self.start_date_edit.date().toString("yyyy-MM-dd")
            end = self.end_date_edit.date().toString("yyyy-MM-dd")
            
        return start, end

    def _show_loading_state(self) -> None:
        """显示加载状态（新增）"""
        self.score_label.setText("加载中...")
        self.grade_label.setText("处理中")
        self.desc_text.setPlainText("正在生成报告，请稍候...")
        self.advice_text.clear()
        self.behavior_table.setRowCount(0)
        self.trend_label.setText("正在处理趋势数据...")
        self.export_btn.setEnabled(False)

    @Slot(dict)
    def _on_evaluation_updated(self, evaluation: Dict[str, Any]) -> None:
        """评估更新时自动刷新报告（新增）"""
        # 仅当报告周期包含当前日期时才刷新
        current_period = self.period_combo.currentData()
        if current_period in ["today", "week", "month"]:
            self._generate_report()

    @Slot()
    def _export_report(self) -> None:
        """导出报告（保持原有方法）"""
        with QMutexLocker(self.report_lock):
            if not self.current_report:
                QMessageBox.warning(self, "导出失败", "没有可导出的报告，请先生成报告")
                return
                
            report = self.current_report.copy()
        
        # 调用数据导出器
        from ui.dialogs.ExportDialog import ExportDialog
        export_dialog = ExportDialog(self.data_storage, self)
        export_dialog.setWindowTitle("导出评估报告")
        
        # 设置导出参数
        if export_dialog.exec():
            self.logger.info("评估报告已导出")
    