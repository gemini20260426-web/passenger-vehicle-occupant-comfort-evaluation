"""报告管理界面组件（管理自动生成的驾驶行为分析报告）"""
import logging
import os
import webbrowser
from typing import List, Dict, Any
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QProgressDialog, QTabWidget,
                             QCheckBox, QTimeEdit, QComboBox, QSpinBox, QDateEdit,
                             QFileDialog, QFrame)
from PySide6.QtCore import Qt, Slot, QDateTime, QMutex, QMutexLocker
from PySide6.QtGui import QFont, QColor, QIcon

class ReportManagerWidget(QWidget):
    """报告管理界面组件（保持原有类名）"""
    def __init__(self, report_scheduler, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.report_scheduler = report_scheduler
        
        # 线程安全锁（新增）
        self.widget_lock = QMutex()
        
        # 当前选中的报告（保持原有）
        self.selected_report = None
        
        # 初始化UI（保持原有方法）
        self._init_ui()
        
        # 连接信号（新增）
        self._connect_signals()
        
        # 加载数据
        self._load_report_list()
        self._load_schedule_config()

    def _init_ui(self) -> None:
        """初始化UI组件（保持原有布局）"""
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("驾驶行为分析报告")
        self.resize(900, 600)
        
        # 创建标签页（保持原有）
        self.tab_widget = QTabWidget()
        
        # 报告列表标签页
        self.report_list_tab = QWidget()
        self._init_report_list_tab()
        self.tab_widget.addTab(self.report_list_tab, "报告列表")
        
        # 报告设置标签页
        self.schedule_tab = QWidget()
        self._init_schedule_tab()
        self.tab_widget.addTab(self.schedule_tab, "生成计划")
        
        # 手动生成标签页
        self.generate_tab = QWidget()
        self._init_generate_tab()
        self.tab_widget.addTab(self.generate_tab, "手动生成")
        
        main_layout.addWidget(self.tab_widget)

    def _init_report_list_tab(self) -> None:
        """初始化报告列表标签页（保持原有方法）"""
        layout = QVBoxLayout(self.report_list_tab)
        
        # 筛选和操作区域（新增）
        filter_layout = QHBoxLayout()
        
        self.report_type_filter = QComboBox()
        self.report_type_filter.addItem("所有类型", "all")
        self.report_type_filter.addItem("每日报告", "daily")
        self.report_type_filter.addItem("每周报告", "weekly")
        self.report_type_filter.addItem("每月报告", "monthly")
        self.report_type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("报告类型:"))
        filter_layout.addWidget(self.report_type_filter)
        
        filter_layout.addStretch()
        
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self._load_report_list)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # 报告列表（保持原有）
        self.report_table = QTableWidget()
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels(["报告类型", "生成时间", "大小", "文件名", "操作"])
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.report_table.cellClicked.connect(self._on_report_selected)
        layout.addWidget(self.report_table)
        
        # 状态栏（新增）
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

    def _init_schedule_tab(self) -> None:
        """初始化生成计划标签页（保持原有方法）"""
        layout = QVBoxLayout(self.schedule_tab)
        
        # 每日报告设置
        daily_group = QGroupBox("每日报告设置")
        daily_layout = QFormLayout()
        
        self.daily_enabled = QCheckBox()
        daily_layout.addRow("启用每日报告:", self.daily_enabled)
        
        self.daily_time = QTimeEdit()
        self.daily_time.setDisplayFormat("HH:mm")
        daily_layout.addRow("生成时间:", self.daily_time)
        
        daily_group.setLayout(daily_layout)
        layout.addWidget(daily_group)
        
        # 每周报告设置
        weekly_group = QGroupBox("每周报告设置")
        weekly_layout = QFormLayout()
        
        self.weekly_enabled = QCheckBox()
        weekly_layout.addRow("启用每周报告:", self.weekly_enabled)
        
        self.weekly_day = QComboBox()
        self.weekly_day.addItem("星期一", 0)
        self.weekly_day.addItem("星期二", 1)
        self.weekly_day.addItem("星期三", 2)
        self.weekly_day.addItem("星期四", 3)
        self.weekly_day.addItem("星期五", 4)
        self.weekly_day.addItem("星期六", 5)
        self.weekly_day.addItem("星期日", 6)
        weekly_layout.addRow("生成星期:", self.weekly_day)
        
        self.weekly_time = QTimeEdit()
        self.weekly_time.setDisplayFormat("HH:mm")
        weekly_layout.addRow("生成时间:", self.weekly_time)
        
        weekly_group.setLayout(weekly_layout)
        layout.addWidget(weekly_group)
        
        # 每月报告设置
        monthly_group = QGroupBox("每月报告设置")
        monthly_layout = QFormLayout()
        
        self.monthly_enabled = QCheckBox()
        monthly_layout.addRow("启用每月报告:", self.monthly_enabled)
        
        self.monthly_date = QSpinBox()
        self.monthly_date.setRange(1, 31)
        self.monthly_date.setSuffix(" 日")
        monthly_layout.addRow("生成日期:", self.monthly_date)
        
        self.monthly_time = QTimeEdit()
        self.monthly_time.setDisplayFormat("HH:mm")
        monthly_layout.addRow("生成时间:", self.monthly_time)
        
        monthly_group.setLayout(monthly_layout)
        layout.addWidget(monthly_group)
        
        # 通用设置
        general_group = QGroupBox("通用设置")
        general_layout = QFormLayout()
        
        self.report_format = QComboBox()
        self.report_format.addItem("PDF格式", "pdf")
        self.report_format.addItem("HTML格式", "html")
        self.report_format.addItem("CSV格式", "csv")
        general_layout.addRow("报告格式:", self.report_format)
        
        self.keep_reports = QSpinBox()
        self.keep_reports.setRange(1, 90)
        self.keep_reports.setSuffix(" 天")
        general_layout.addRow("报告保留时间:", self.keep_reports)
        
        path_layout = QHBoxLayout()
        self.report_path = QLabel()
        self.browse_path_btn = QPushButton("浏览...")
        self.browse_path_btn.clicked.connect(self._browse_report_path)
        path_layout.addWidget(self.report_path)
        path_layout.addWidget(self.browse_path_btn)
        general_layout.addRow("报告保存路径:", path_layout)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # 保存按钮
        self.save_schedule_btn = QPushButton("保存设置")
        self.save_schedule_btn.clicked.connect(self._save_schedule_config)
        layout.addWidget(self.save_schedule_btn)
        
        layout.addStretch()

    def _init_generate_tab(self) -> None:
        """初始化手动生成标签页（保持原有方法）"""
        layout = QVBoxLayout(self.generate_tab)
        
        # 报告类型选择
        self.report_type = QComboBox()
        self.report_type.addItem("每日报告", "daily")
        self.report_type.addItem("每周报告", "weekly")
        self.report_type.addItem("每月报告", "monthly")
        self.report_type.currentIndexChanged.connect(self._on_manual_type_changed)
        layout.addWidget(QLabel("选择报告类型:"))
        layout.addWidget(self.report_type)
        
        # 日期范围选择
        date_group = QGroupBox("报告日期范围")
        date_layout = QFormLayout()
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDateTime.currentDateTime().date())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        date_layout.addRow("结束日期:", self.end_date)
        
        # 开始日期根据报告类型自动计算，默认隐藏
        self.start_date_label = QLabel("开始日期:")
        self.start_date = QDateEdit()
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setEnabled(False)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # 生成按钮
        self.generate_btn = QPushButton("生成报告")
        self.generate_btn.clicked.connect(self._generate_manual_report)
        layout.addWidget(self.generate_btn)
        
        # 进度显示（新增）
        self.progress_frame = QFrame()
        self.progress_frame.setFrameShape(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("等待生成...")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_frame.setVisible(False)
        layout.addWidget(self.progress_frame)
        
        layout.addStretch()

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 报告调度器信号
        self.report_scheduler.report_generated.connect(self._on_report_generated)
        self.report_scheduler.report_failed.connect(self._on_report_failed)
        self.report_scheduler.progress_updated.connect(self._on_report_progress)
        self.report_scheduler.schedule_updated.connect(self._on_schedule_updated)

    def _load_report_list(self) -> None:
        """加载报告列表（保持原有方法）"""
        # 清空表格
        self.report_table.setRowCount(0)
        
        # 获取报告列表
        reports = self.report_scheduler.get_recent_reports(100)  # 获取最近100个报告
        
        # 应用筛选
        filter_type = self.report_type_filter.currentData()
        if filter_type != "all":
            reports = [r for r in reports if r['type'] == filter_type]
        
        # 添加到表格
        for i, report in enumerate(reports):
            self.report_table.insertRow(i)
            
            # 报告类型
            type_map = {
                'daily': '每日报告',
                'weekly': '每周报告',
                'monthly': '每月报告'
            }
            type_item = QTableWidgetItem(type_map.get(report['type'], report['type']))
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.report_table.setItem(i, 0, type_item)
            
            # 生成时间
            time_item = QTableWidgetItem(report['modify_time_str'])
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.report_table.setItem(i, 1, time_item)
            
            # 大小
            size_item = QTableWidgetItem(report['size_str'])
            size_item.setTextAlignment(Qt.AlignCenter)
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            self.report_table.setItem(i, 2, size_item)
            
            # 文件名
            name_item = QTableWidgetItem(report['filename'])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.report_table.setItem(i, 3, name_item)
            
            # 操作按钮
            btn_layout = QHBoxLayout()
            view_btn = QPushButton("查看")
            view_btn.setMinimumWidth(60)
            view_btn.clicked.connect(lambda checked, r=report: self._view_report(r))
            
            save_btn = QPushButton("另存为")
            save_btn.setMinimumWidth(60)
            save_btn.clicked.connect(lambda checked, r=report: self._save_report_as(r))
            
            delete_btn = QPushButton("删除")
            delete_btn.setMinimumWidth(60)
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(lambda checked, r=report: self._delete_report(r))
            
            btn_layout.addWidget(view_btn)
            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(delete_btn)
            
            btn_widget = QWidget()
            btn_widget.setLayout(btn_layout)
            self.report_table.setCellWidget(i, 4, btn_widget)
        
        # 重置选中状态
        with QMutexLocker(self.widget_lock):
            self.selected_report = None

    def _load_schedule_config(self) -> None:
        """加载调度配置（保持原有方法）"""
        config = self.report_scheduler.get_schedule_config()
        
        # 每日报告设置
        self.daily_enabled.setChecked(config['daily']['enabled'])
        daily_time = config['daily']['time']
        if daily_time:
            try:
                hour, minute = map(int, daily_time.split(':'))
                self.daily_time.setTime(QDateTime.currentDateTime().time().setHMS(hour, minute, 0))
            except Exception as e:
                self.logger.warning(f"解析每日报告时间失败: {str(e)}")
        
        # 每周报告设置
        self.weekly_enabled.setChecked(config['weekly']['enabled'])
        self.weekly_day.setCurrentIndex(config['weekly']['day'])
        weekly_time = config['weekly']['time']
        if weekly_time:
            try:
                hour, minute = map(int, weekly_time.split(':'))
                self.weekly_time.setTime(QDateTime.currentDateTime().time().setHMS(hour, minute, 0))
            except Exception as e:
                self.logger.warning(f"解析每周报告时间失败: {str(e)}")
        
        # 每月报告设置
        self.monthly_enabled.setChecked(config['monthly']['enabled'])
        self.monthly_date.setValue(config['monthly']['date'])
        monthly_time = config['monthly']['time']
        if monthly_time:
            try:
                hour, minute = map(int, monthly_time.split(':'))
                self.monthly_time.setTime(QDateTime.currentDateTime().time().setHMS(hour, minute, 0))
            except Exception as e:
                self.logger.warning(f"解析每月报告时间失败: {str(e)}")
        
        # 通用设置
        format_idx = self.report_format.findData(config['format'])
        if format_idx >= 0:
            self.report_format.setCurrentIndex(format_idx)
        self.keep_reports.setValue(config['keep_reports'])
        self.report_path.setText(config['output_dir'])

    @Slot(int)
    def _on_filter_changed(self, index: int) -> None:
        """处理报告筛选变化（新增）"""
        self._load_report_list()

    @Slot(int, int)
    def _on_report_selected(self, row: int, column: int) -> None:
        """处理报告选中（保持原有方法）"""
        # 获取选中的报告文件名
        filename_item = self.report_table.item(row, 3)
        if filename_item:
            filename = filename_item.text()
            
            # 查找完整的报告信息
            for report in self.report_scheduler.get_recent_reports():
                if report['filename'] == filename:
                    with QMutexLocker(self.widget_lock):
                        self.selected_report = report
                    break

    @Slot()
    def _view_report(self, report: Dict[str, Any]) -> None:
        """查看报告（新增）"""
        if not report or not os.path.exists(report['path']):
            QMessageBox.warning(self, "操作失败", "报告文件不存在")
            return
            
        try:
            # 根据文件类型选择打开方式
            if report['path'].lower().endswith('.pdf'):
                webbrowser.open(f"file://{report['path']}")
            elif report['path'].lower().endswith('.html'):
                webbrowser.open(f"file://{report['path']}")
            elif report['path'].lower().endswith('.csv'):
                os.startfile(report['path'])  # Windows
                # 对于其他系统，可以使用webbrowser或特定应用
            else:
                webbrowser.open(f"file://{report['path']}")
                
            self.logger.info(f"已打开报告: {report['filename']}")
            
        except Exception as e:
            error_msg = f"打开报告失败: {str(e)}"
            self.logger.error(error_msg)
            QMessageBox.warning(self, "操作失败", error_msg)

    @Slot()
    def _save_report_as(self, report: Dict[str, Any]) -> None:
        """报告另存为（新增）"""
        if not report or not os.path.exists(report['path']):
            QMessageBox.warning(self, "操作失败", "报告文件不存在")
            return
            
        # 获取保存路径
        default_filename = report['filename']
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", default_filename, 
            f"{report['type']}报告 (*.{report['filename'].split('.')[-1]});;所有文件 (*)"
        )
        
        if not file_path:
            return
            
        try:
            # 复制文件
            import shutil
            shutil.copy2(report['path'], file_path)
            
            QMessageBox.information(self, "保存成功", f"报告已保存到: {file_path}")
            self.logger.info(f"报告已另存为: {file_path}")
            
        except Exception as e:
            error_msg = f"保存报告失败: {str(e)}"
            self.logger.error(error_msg)
            QMessageBox.warning(self, "保存失败", error_msg)

    @Slot()
    def _delete_report(self, report: Dict[str, Any]) -> None:
        """删除报告（保持原有方法）"""
        if not report:
            QMessageBox.warning(self, "操作失败", "请先选择一个报告")
            return
            
        # 确认删除操作
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除 {report['filename']} 吗？\n"
            f"此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 删除文件
                os.remove(report['path'])
                self.logger.info(f"已删除报告: {report['filename']}")
                
                # 刷新列表
                self._load_report_list()
                
            except Exception as e:
                error_msg = f"删除报告失败: {str(e)}"
                self.logger.error(error_msg)
                QMessageBox.warning(self, "删除失败", error_msg)

    @Slot()
    def _browse_report_path(self) -> None:
        """浏览报告保存路径（新增）"""
        current_path = self.report_path.text() or os.getcwd()
        
        directory = QFileDialog.getExistingDirectory(
            self, "选择报告保存路径", current_path
        )
        
        if directory:
            self.report_path.setText(directory)

    @Slot()
    def _save_schedule_config(self) -> None:
        """保存调度配置（保持原有方法）"""
        # 收集设置
        new_config = {
            'daily': {
                'enabled': self.daily_enabled.isChecked(),
                'time': self.daily_time.time().toString("HH:mm")
            },
            'weekly': {
                'enabled': self.weekly_enabled.isChecked(),
                'day': self.weekly_day.currentData(),
                'time': self.weekly_time.time().toString("HH:mm")
            },
            'monthly': {
                'enabled': self.monthly_enabled.isChecked(),
                'date': self.monthly_date.value(),
                'time': self.monthly_time.time().toString("HH:mm")
            },
            'format': self.report_format.currentData(),
            'keep_reports': self.keep_reports.value(),
            'output_dir': self.report_path.text()
        }
        
        # 保存设置
        self.report_scheduler.set_schedule_config(new_config)
        
        # 显示提示
        QMessageBox.information(self, "保存成功", "报告生成计划已保存")

    @Slot(int)
    def _on_manual_type_changed(self, index: int) -> None:
        """处理手动生成报告类型变化（新增）"""
        report_type = self.report_type.currentData()
        
        # 根据报告类型计算开始日期
        end_date = self.end_date.date()
        
        if report_type == 'daily':
            # 每日报告：开始日期 = 结束日期
            start_date = end_date
        elif report_type == 'weekly':
            # 每周报告：开始日期 = 结束日期 - 6天
            start_date = end_date.addDays(-6)
        else:  # monthly
            # 每月报告：开始日期 = 当月1日
            start_date = end_date.addDays(-(end_date.day() - 1))
        
        # 更新开始日期控件状态
        if hasattr(self, 'start_date'):
            self.start_date.setDate(start_date)

    @Slot()
    def _generate_manual_report(self) -> None:
        """手动生成报告（新增）"""
        report_type = self.report_type.currentData()
        end_date = self.end_date.date().toPython()
        
        # 显示进度
        self.progress_frame.setVisible(True)
        self.progress_label.setText(f"正在生成{self.report_type.currentText()}...")
        self.progress_bar.setValue(0)
        self.generate_btn.setEnabled(False)
        
        # 生成报告
        success = False
        if report_type == 'daily':
            success = self.report_scheduler.generate_daily_report(end_date)
        elif report_type == 'weekly':
            success = self.report_scheduler.generate_weekly_report(end_date)
        else:  # monthly
            success = self.report_scheduler.generate_monthly_report(end_date)
        
        if not success:
            self.progress_label.setText("生成报告失败，可能已有任务在运行")
            self.generate_btn.setEnabled(True)

    @Slot(str, int)
    def _on_report_progress(self, report_type: str, progress: int) -> None:
        """处理报告生成进度（新增）"""
        # 只更新当前手动生成的报告进度
        if self.progress_frame.isVisible() and self.report_type.currentData() == report_type:
            self.progress_bar.setValue(progress)
            type_desc = self.report_type.currentText()
            self.progress_label.setText(f"正在生成{type_desc}... ({progress}%)")

    @Slot(str, str)
    def _on_report_generated(self, report_type: str, path: str) -> None:
        """处理报告生成成功（新增）"""
        # 如果是手动生成的报告
        if self.progress_frame.isVisible() and self.report_type.currentData() == report_type:
            self.progress_label.setText(f"{self.report_type.currentText()}生成成功")
            self.generate_btn.setEnabled(True)
            
            # 询问是否查看
            reply = QMessageBox.question(
                self, "生成成功", 
                f"{self.report_type.currentText()}已成功生成，是否立即查看？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                webbrowser.open(f"file://{path}")
        
        # 刷新报告列表
        self._load_report_list()
        
        # 更新状态
        self.status_label.setText(f"{report_type}报告生成成功: {os.path.basename(path)}")

    @Slot(str, str)
    def _on_report_failed(self, report_type: str, message: str) -> None:
        """处理报告生成失败（新增）"""
        # 如果是手动生成的报告
        if self.progress_frame.isVisible() and self.report_type.currentData() == report_type:
            self.progress_label.setText(f"{self.report_type.currentText()}生成失败: {message}")
            self.generate_btn.setEnabled(True)
        
        # 更新状态
        self.status_label.setText(f"{report_type}报告生成失败: {message}")
        QMessageBox.warning(self, "生成失败", message)

    @Slot(dict)
    def _on_schedule_updated(self, config: Dict[str, Any]) -> None:
        """处理调度配置更新（新增）"""
        self._load_schedule_config()
