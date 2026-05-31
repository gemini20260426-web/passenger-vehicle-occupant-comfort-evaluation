#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""


"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QFrame, QProgressBar, QCheckBox, QTextEdit,
    QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QColor, QPixmap, QPainter
import logging

class StartupSequenceGuide(QWidget):
    """"""
    
    # 
    guide_completed = Signal()
    step_clicked = Signal(int)
    action_triggered = Signal(str, dict)  # action_triggered
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.panel_name = ""
        
        # 
        self.startup_steps = [
            {
                'id': 1,
                'title': '',
                'description': '',
                'icon': '',
                'status': 'pending',  # pending, current, completed, error
                'required': True
            },
            {
                'id': 2,
                'title': '',
                'description': '',
                'icon': '',
                'status': 'pending',
                'required': True
            },
            {
                'id': 3,
                'title': '',
                'description': '',
                'icon': '',
                'status': 'pending',
                'required': True
            },
            {
                'id': 4,
                'title': '',
                'description': '',
                'icon': '',
                'status': 'pending',
                'required': False
            }
        ]
        
        self.current_step = 0
        self.completed_steps = 0
        
        # UI
        self._init_ui()
        self._connect_signals()
        
        # 
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(2000)  # 2
        
        self.logger.info("")
    
    def _init_ui(self):
        """UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 
        self.setVisible(True)
        
        # 
        title_label = QLabel(" ")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        layout.addWidget(title_label)
        
        # 
        self._create_overall_progress(layout)
        
        # 
        self._create_steps_list(layout)
        
        # 
        self._create_current_step_details(layout)
        
        # 
        self._create_action_buttons(layout)
        
        # 
        self._create_status_log(layout)
    
    def _create_overall_progress(self, parent_layout):
        """"""
        progress_group = QGroupBox(" ")
        progress_layout = QVBoxLayout(progress_group)
        
        # 
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, len(self.startup_steps))
        self.overall_progress.setValue(0)
        progress_layout.addWidget(self.overall_progress)
        
        self.progress_label = QLabel("...")
        progress_layout.addWidget(self.progress_label)
        
        parent_layout.addWidget(progress_group)
    
    def _create_steps_list(self, parent_layout):
        """"""
        steps_group = QGroupBox(" ")
        steps_layout = QVBoxLayout(steps_group)
        
        # 
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        
        # 
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setSpacing(10)
        
        # 
        self.step_widgets = []
        for i, step in enumerate(self.startup_steps):
            step_widget = self._create_step_widget(step, i)
            self.step_widgets.append(step_widget)
            self.steps_layout.addWidget(step_widget)
        
        scroll_area.setWidget(self.steps_container)
        steps_layout.addWidget(scroll_area)
        
        parent_layout.addWidget(steps_group)
    
    def _create_step_widget(self, step, index):
        """"""
        step_frame = QFrame()
        step_frame.setFrameStyle(QFrame.Box)
        
        layout = QHBoxLayout(step_frame)
        layout.setSpacing(15)
        
        # 
        status_layout = QVBoxLayout()
        
        # 
        self.status_icon = QLabel(step['icon'])
        self.status_icon.setFont(QFont("Arial", 20))
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setFixedSize(40, 40)
        status_layout.addWidget(self.status_icon)
        
        # 
        step_number = QLabel(str(step['id']))
        step_number.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        step_number.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(step_number)
        
        layout.addLayout(status_layout)
        
        info_layout = QVBoxLayout()
        
        title_label = QLabel(step['title'])
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        info_layout.addWidget(title_label)
        
        desc_label = QLabel(step['description'])
        desc_label.setFont(QFont("Microsoft YaHei", 10))
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        layout.addLayout(info_layout)
        
        # 
        status_indicator = QLabel("⏳")
        status_indicator.setFont(QFont("Arial", 16))
        status_indicator.setAlignment(Qt.AlignCenter)
        status_indicator.setFixedSize(30, 30)
        layout.addWidget(status_indicator)
        
        # 
        step_frame.mousePressEvent = lambda event, idx=index: self._on_step_clicked(idx)
        
        # step_frame
        step_frame.step_data = step
        step_frame.step_index = index
        step_frame.status_indicator = status_indicator
        
        return step_frame
    
    def _create_current_step_details(self, parent_layout):
        """"""
        details_group = QGroupBox(" ")
        details_layout = QVBoxLayout(details_group)
        
        # 
        self.current_step_title = QLabel("")
        self.current_step_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        details_layout.addWidget(self.current_step_title)
        
        self.current_step_desc = QLabel("")
        self.current_step_desc.setFont(QFont("Microsoft YaHei", 11))
        self.current_step_desc.setWordWrap(True)
        details_layout.addWidget(self.current_step_desc)
        
        self.action_hint = QLabel("")
        self.action_hint.setFont(QFont("Microsoft YaHei", 10))
        self.action_hint.setWordWrap(True)
        details_layout.addWidget(self.action_hint)
        
        parent_layout.addWidget(details_group)
    
    def _create_action_buttons(self, parent_layout):
        """"""
        buttons_group = QGroupBox(" ")
        buttons_layout = QHBoxLayout(buttons_group)
        
        # 
        self.execute_current_btn = QPushButton(" ")
        self.execute_current_btn.clicked.connect(self._execute_current_step)
        self.execute_current_btn.setEnabled(False)
        buttons_layout.addWidget(self.execute_current_btn)
        
        self.skip_current_btn = QPushButton("⏭ ")
        self.skip_current_btn.clicked.connect(self._skip_current_step)
        self.skip_current_btn.setEnabled(False)
        buttons_layout.addWidget(self.skip_current_btn)
        
        self.reset_all_btn = QPushButton(" ")
        self.reset_all_btn.clicked.connect(self._reset_all_steps)
        buttons_layout.addWidget(self.reset_all_btn)
        
        parent_layout.addWidget(buttons_group)
    
    def _create_status_log(self, parent_layout):
        """"""
        log_group = QGroupBox(" ")
        log_layout = QVBoxLayout(log_group)
        
        # 
        self.status_log = QTextEdit()
        self.status_log.setMaximumHeight(150)
        self.status_log.setReadOnly(True)
        log_layout.addWidget(self.status_log)
        
        clear_log_btn = QPushButton(" ")
        clear_log_btn.clicked.connect(self._clear_log)
        log_layout.addWidget(clear_log_btn)
        
        parent_layout.addWidget(log_group)
    
    def _connect_signals(self):
        """"""
        pass
    
    def _on_step_clicked(self, step_index):
        """"""
        if step_index < len(self.startup_steps):
            self.current_step = step_index
            self._update_current_step_display()
            self._log_message(f" {step_index + 1}: {self.startup_steps[step_index]['title']}")
            self.step_clicked.emit(step_index)
    
    def _execute_current_step(self):
        """"""
        if 0 <= self.current_step < len(self.startup_steps):
            step = self.startup_steps[self.current_step]
            self._log_message(f" {self.current_step + 1}: {step['title']}")
            
            # 
            self.step_clicked.emit(self.current_step)
            
            # 
            QTimer.singleShot(2000, self._complete_current_step)
    
    def _skip_current_step(self):
        """"""
        if 0 <= self.current_step < len(self.startup_steps):
            step = self.startup_steps[self.current_step]
            self._log_message(f" {self.current_step + 1}: {step['title']}")
            self._complete_current_step()
    
    def _complete_current_step(self):
        """"""
        if 0 <= self.current_step < len(self.startup_steps):
            step = self.startup_steps[self.current_step]
            step['status'] = 'completed'
            self.completed_steps += 1
            
            self._update_step_display(self.current_step)
            self._update_progress()
            self._log_message(f"  {self.current_step + 1} : {step['title']}")
            
            # 
            if self.current_step < len(self.startup_steps) - 1:
                self.current_step += 1
                self._update_current_step_display()
            else:
                self._log_message(" ")
                self.guide_completed.emit()
    
    def _reset_all_steps(self):
        """"""
        for step in self.startup_steps:
            step['status'] = 'pending'
        
        self.current_step = 0
        self.completed_steps = 0
        
        self._update_all_steps_display()
        self._update_progress()
        self._update_current_step_display()
        self._log_message(" ")
    
    def _update_current_step_display(self):
        """"""
        if 0 <= self.current_step < len(self.startup_steps):
            step = self.startup_steps[self.current_step]
            
            self.current_step_title.setText(f" {self.current_step + 1}: {step['title']}")
            self.current_step_desc.setText(step['description'])
            
            # 
            if step['status'] == 'pending':
                self.action_hint.setText(" ''")
                self.execute_current_btn.setEnabled(True)
                self.skip_current_btn.setEnabled(True)
            elif step['status'] == 'completed':
                self.action_hint.setText(" ")
                self.execute_current_btn.setEnabled(False)
                self.skip_current_btn.setEnabled(False)
            else:
                self.action_hint.setText("⏳ ...")
                self.execute_current_btn.setEnabled(False)
                self.skip_current_btn.setEnabled(False)
    
    def _update_step_display(self, step_index):
        if 0 <= step_index < len(self.step_widgets):
            step = self.startup_steps[step_index]
            step_widget = self.step_widgets[step_index]
            
            if step['status'] == 'completed':
                step_widget.status_indicator.setText("")
            elif step['status'] == 'current':
                step_widget.status_indicator.setText("")
            elif step['status'] == 'error':
                step_widget.status_indicator.setText("")
            else:
                step_widget.status_indicator.setText("⏳")
    
    def _update_all_steps_display(self):
        """"""
        for i in range(len(self.step_widgets)):
            self._update_step_display(i)
    
    def _update_progress(self):
        """"""
        self.overall_progress.setValue(self.completed_steps)
        
        if self.completed_steps == 0:
            self.progress_label.setText("...")
        elif self.completed_steps == len(self.startup_steps):
            self.progress_label.setText(" ")
        else:
            self.progress_label.setText(f" {self.completed_steps}/{len(self.startup_steps)} ")
    
    def _update_status(self):
        """"""
        # 
        pass
    
    def _log_message(self, message):
        """"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.status_log.append(log_entry)
        
        # 
        scrollbar = self.status_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _clear_log(self):
        """"""
        self.status_log.clear()
        self._log_message("")
    
    def skip_fusion_step(self):
        """跳过数据融合步骤（单源直通模式）"""
        for i, step in enumerate(self.startup_steps):
            if step['id'] == 2:
                step['status'] = 'completed'
                self._update_step_display(i)
                self.completed_steps += 1
                self._update_progress()
                self._log_message("单源直通模式: 自动跳过数据融合步骤")
                if self.current_step == i:
                    if i < len(self.startup_steps) - 1:
                        self.current_step = i + 1
                        self._update_current_step_display()
                break
    
    def update_step_status(self, step_id, status):
        """"""
        for i, step in enumerate(self.startup_steps):
            if step['id'] == step_id:
                step['status'] = status
                self._update_step_display(i)
                
                if status == 'completed':
                    self.completed_steps += 1
                elif status == 'pending' and step['status'] == 'completed':
                    self.completed_steps -= 1
                
                self._update_progress()
                break
    
    def get_current_step(self):
        """"""
        return self.current_step
    
    def get_completed_steps(self):
        """"""
        return self.completed_steps
    
    def is_all_steps_completed(self):
        """"""
        return self.completed_steps == len(self.startup_steps)
