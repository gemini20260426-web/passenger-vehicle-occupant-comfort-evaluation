#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 状态: 【当前使用 ACTIVE】- 专业版顶部状态栏
# 更新日期: 2026-05-03
# ============================================================

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, QDateTime

from .core_ui_utils import translations

try:
    from modules.ui.professional_styles import PRO_COLORS, HEADER_STYLE
except ImportError:
    PRO_COLORS = {}
    HEADER_STYLE = ""


class TopStatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("proHeader")
        if HEADER_STYLE:
            self.setStyleSheet(HEADER_STYLE)
        self.system_status = "Ready"
        self.init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 4, 0, 4)
        logo_layout.setSpacing(0)

        self.title_label = QLabel("Core System Dashboard")
        self.title_label.setObjectName("headerTitle")
        logo_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("v2.0.0  |  Multi-Source Data Platform")
        self.subtitle_label.setObjectName("headerSubtitle")
        logo_layout.addWidget(self.subtitle_label)

        layout.addWidget(logo_container)
        layout.addStretch()

        self._add_separator(layout)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        layout.addWidget(self.status_dot)
        layout.addSpacing(6)

        self.status_value = QLabel("Ready")
        self.status_value.setObjectName("statusText")
        layout.addWidget(self.status_value)

        self._add_separator(layout)

        self._add_metric(layout, "RECORDING", "No")
        self._add_separator(layout)
        self._add_metric(layout, "MODE", "Standard")
        self._add_separator(layout)

        self.time_label = QLabel()
        self.time_label.setObjectName("statusText")
        self.time_label.setStyleSheet("font-size: 11px; padding: 0px 8px;")
        layout.addWidget(self.time_label)

        self.set_status("Ready")

    def _add_separator(self, layout):
        sep = QWidget()
        sep.setObjectName("headerSeparator")
        layout.addWidget(sep)
        layout.addSpacing(12)

    def _add_metric(self, layout, label_text, value_text):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        lbl = QLabel(label_text)
        lbl.setObjectName("metricLabel")
        vbox.addWidget(lbl)

        val = QLabel(value_text)
        val.setObjectName("metricValue")
        vbox.addWidget(val)

        layout.addWidget(container)
        layout.addSpacing(4)

        if label_text == "RECORDING":
            self.recording_value = val
        elif label_text == "MODE":
            self.mode_value = val

    def set_status(self, status):
        self.system_status = status
        self.status_value.setText(status)

        accent = PRO_COLORS.get('accent', '#4f8cff')
        success = PRO_COLORS.get('success', '#34d399')
        danger = PRO_COLORS.get('danger', '#f87171')
        muted = PRO_COLORS.get('text_muted', '#5f6570')

        if status in ("Ready", translations.get('zh', {}).get('status_ready', 'Ready')):
            color = success
        elif status in ("Running", translations.get('zh', {}).get('status_running', 'Running')):
            color = accent
        elif status in ("Error", translations.get('zh', {}).get('status_error', 'Error')):
            color = danger
        else:
            color = muted

        self.status_dot.setStyleSheet(
            f"QLabel#statusDot {{ background-color: {color}; "
            f"min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px; border-radius: 4px; }}")

    def set_recording_status(self, is_recording):
        danger = PRO_COLORS.get('danger', '#f87171')
        text_primary = PRO_COLORS.get('text_primary', '#e8eaed')

        if is_recording:
            self.recording_value.setText("Yes")
            self.recording_value.setStyleSheet(
                f"QLabel#metricValue {{ color: {danger}; font-size: 13px; font-weight: 700; }}")
        else:
            self.recording_value.setText("No")
            self.recording_value.setStyleSheet(
                f"QLabel#metricValue {{ color: {text_primary}; font-size: 13px; font-weight: 700; }}")

    def update_time(self):
        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.time_label.setText(current_time)

    def update_translations(self, lang):
        self.title_label.setText(translations[lang]['app_title'])
        self.subtitle_label.setText("v2.0.0  |  Multi-Source Data Platform")
        self.mode_value.setText(translations[lang]['mode_standard'])

        if self.system_status == "Ready" or self.system_status == translations.get('zh', {}).get('status_ready', ''):
            self.set_status(translations[lang]['status_ready'])
        elif self.system_status == "Running" or self.system_status == translations.get('zh', {}).get('status_running', ''):
            self.set_status(translations[lang]['status_running'])
        elif self.system_status == "Error" or self.system_status == translations.get('zh', {}).get('status_error', ''):
            self.set_status(translations[lang]['status_error'])
