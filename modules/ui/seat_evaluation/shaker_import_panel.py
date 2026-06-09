#!/usr/bin/env python3
"""振动台架实验数据导入面板"""

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt


class ShakerImportPanel(QGroupBox):
    """数据导入面板 — 选择文件/文件夹，管理已加载数据"""
    
    files_loaded = Signal(list)       # list of filepaths
    start_analysis = Signal(str)      # mode: "single" or "batch"
    
    def __init__(self, parent=None):
        super().__init__("数据导入", parent)
        self._loaded_files = []       # list of filepath strings
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)

        # ── 第1行: 路径选择 ──
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("未选择文件或文件夹...")
        self._path_edit.setMaximumHeight(28)

        self._btn_select_file = QPushButton("选择文件")
        self._btn_select_folder = QPushButton("批量文件夹")
        self._btn_clear_path = QPushButton("清空")

        path_layout.addWidget(self._path_edit, 1)
        path_layout.addWidget(self._btn_select_file)
        path_layout.addWidget(self._btn_select_folder)
        path_layout.addWidget(self._btn_clear_path)
        main_layout.addLayout(path_layout)

        # ── 第2行: 文件列表 + 检测信息 ──
        self._file_list_widget = QListWidget()
        self._file_list_widget.setMinimumHeight(60)
        self._file_list_widget.setMaximumHeight(100)
        main_layout.addWidget(self._file_list_widget)

        self._info_label = QLabel("采样率: --  时长: --  通道数: --")
        self._info_label.setStyleSheet("color: #666; font-size: 11px; padding: 1px;")
        main_layout.addWidget(self._info_label)

        # ── 第3行: 全选/反选/删除 | 模式 | 开始/停止 (合并为一行) ──
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._btn_select_all = QPushButton("全选")
        self._btn_invert_selection = QPushButton("反选")
        self._btn_remove_selected = QPushButton("移除选中")
        action_row.addWidget(self._btn_select_all)
        action_row.addWidget(self._btn_invert_selection)
        action_row.addWidget(self._btn_remove_selected)

        action_row.addSpacing(12)

        # 分隔线
        sep = QLabel("|")
        sep.setStyleSheet("color: #ccc; font-size: 14px;")
        action_row.addWidget(sep)
        action_row.addSpacing(6)

        self._radio_single = QRadioButton("单工况")
        self._radio_batch = QRadioButton("多工况对比")
        self._radio_single.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._radio_single, 0)
        self._mode_group.addButton(self._radio_batch, 1)

        action_row.addWidget(self._radio_single)
        action_row.addWidget(self._radio_batch)

        action_row.addStretch()

        self._btn_start = QPushButton("开始分析")
        self._btn_start.setStyleSheet("font-weight: bold; min-width: 80px;")
        self._btn_stop = QPushButton("停止")
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet("min-width: 60px;")
        action_row.addWidget(self._btn_start)
        action_row.addWidget(self._btn_stop)

        main_layout.addLayout(action_row)
    
    def _connect_signals(self):
        self._btn_select_file.clicked.connect(self._on_select_file)
        self._btn_select_folder.clicked.connect(self._on_select_folder)
        self._btn_clear_path.clicked.connect(self._on_clear)
        self._btn_select_all.clicked.connect(self._on_select_all)
        self._btn_invert_selection.clicked.connect(self._on_invert_selection)
        self._btn_remove_selected.clicked.connect(self._on_remove_selected)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
    
    # ── 公共接口 ──
    
    def loaded_files(self) -> list:
        """返回当前已加载的文件路径列表"""
        return list(self._loaded_files)
    
    def checked_files(self) -> list:
        """返回当前勾选的文件路径列表"""
        result = []
        for i in range(self._file_list_widget.count()):
            item = self._file_list_widget.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result
    
    def set_info(self, fs=None, duration=None, channels=None):
        """更新检测信息标签"""
        parts = []
        if fs is not None:
            parts.append(f"采样率: {fs} Hz")
        else:
            parts.append("采样率: --")
        if duration is not None:
            parts.append(f"时长: {duration:.2f} s" if isinstance(duration, (int, float)) else f"时长: {duration}")
        else:
            parts.append("时长: --")
        if channels is not None:
            parts.append(f"通道数: {channels}")
        else:
            parts.append("通道数: --")
        self._info_label.setText("  ".join(parts))
    
    def set_running_state(self, running: bool):
        """切换运行/停止按钮状态"""
        self._btn_start.setEnabled(not running)
        self._btn_stop.setEnabled(running)
    
    # ── 槽函数 ──
    
    def _on_select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择振动数据文件", "",
            "数据文件 (*.csv *.xls *.xlsx *.txt *.mat *.tdms *.dat);;CSV (*.csv);;Excel (*.xls *.xlsx);;所有文件 (*)"
        )
        if filepath:
            self._add_file(filepath)
            self._path_edit.setText(filepath)
    
    def _on_select_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择数据文件夹"
        )
        if directory:
            self._path_edit.setText(directory)
            import os
            for entry in os.listdir(directory):
                full = os.path.join(directory, entry)
                if os.path.isfile(full):
                    self._add_file(full)
    
    def _on_clear(self):
        self._path_edit.clear()
        self._file_list_widget.clear()
        self._loaded_files.clear()
        self.set_info()
        self.files_loaded.emit([])
    
    def _on_select_all(self):
        for i in range(self._file_list_widget.count()):
            item = self._file_list_widget.item(i)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
    
    def _on_invert_selection(self):
        for i in range(self._file_list_widget.count()):
            item = self._file_list_widget.item(i)
            if item:
                current = item.checkState()
                item.setCheckState(
                    Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                )
    
    def _on_remove_selected(self):
        to_remove = []
        for i in range(self._file_list_widget.count()):
            item = self._file_list_widget.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                to_remove.append(i)
        # 从后往前移除，避免索引偏移
        for i in reversed(to_remove):
            fp = self._file_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            self._file_list_widget.takeItem(i)
            if fp in self._loaded_files:
                self._loaded_files.remove(fp)
        self.files_loaded.emit(list(self._loaded_files))
    
    def _on_start(self):
        mode = "batch" if self._radio_batch.isChecked() else "single"
        self.start_analysis.emit(mode)
    
    def _on_stop(self):
        self.set_running_state(False)
    
    def _add_file(self, filepath: str):
        if filepath in self._loaded_files:
            return
        self._loaded_files.append(filepath)
        
        import os
        basename = os.path.basename(filepath)
        item = QListWidgetItem(basename)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, filepath)
        self._file_list_widget.addItem(item)
        
        self.files_loaded.emit(list(self._loaded_files))