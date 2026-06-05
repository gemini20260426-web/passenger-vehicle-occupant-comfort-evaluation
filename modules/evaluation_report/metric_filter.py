#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标筛选器 Widget (U6: 树形分类筛选)

三层树形结构:
- 按类型: 频域/冲击/疲劳/时频/全时域统计
- 按位置: 头部/胸骨/座垫/对比
- 按组别: 实验组/对照组
"""

import logging
from typing import Dict, List, Any, Optional, Set

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QLabel, QPushButton, QLineEdit,
                               QCheckBox, QGroupBox, QSplitter)
from PySide6.QtCore import Qt, Signal, QMutex, QMutexLocker

logger = logging.getLogger(__name__)


class MetricFilterTree(QWidget):
    """指标筛选器 (U6)

    树形分类筛选，支持:
    - 三层次分类 (类型→位置→组别)
    - 多选/全选/反选
    - 搜索过滤
    - 统计信息显示
    """

    # 指标分类定义
    METRIC_CATEGORIES = {
        '频域指标': {
            'icon': '📊',
            'patterns': ['SEAT_Z', 'SEAT_XY', 'VDV_Z', 'VDV_XY', 'AW_Z', 'AW_XY',
                         'TR_Z', 'TR_XY', 'OVTV', 'R_FACTOR', 'PSD', 'CSD'],
        },
        '瞬态冲击指标': {
            'icon': '💥',
            'patterns': ['HIC15', 'ACC_H_PEAK', 'JERK_H', 'SRS_MRS', 'SRS_PV',
                         'SRS_Q', 'SRS_ATT', 'DISP_HR', 'S_D'],
        },
        '疲劳指标': {
            'icon': '🔁',
            'patterns': ['RFC_CC', 'FDS_D', 'FDS_R'],
        },
        '时频指标': {
            'icon': '⏱️',
            'patterns': ['STFT_FC', 'STFT_KT', 'STFT_CE', 'DISP_TR'],
        },
        '全时域统计': {
            'icon': '📈',
            'patterns': ['RMS_', 'Peak_', 'Crest_', 'Skew_', 'Kurt_', 'MAV_', 'Impf_'],
        },
        '频段衰减': {
            'icon': '📉',
            'patterns': ['BAND_ATT_'],
        },
        '基础指标': {
            'icon': '⚙️',
            'patterns': ['ACC_RMS', 'ACC_PEAK'],
        },
    }

    LOCATION_GROUPS = {
        '头部': {'patterns': ['_H', 'HEAD', 'HIC'], 'exclude': ['_S', '_C', 'STERNUM']},
        '胸骨': {'patterns': ['_S', 'STERNUM', 'S_D']},
        '座垫': {'patterns': ['SEAT_', 'SEAT']},
        '对比': {'patterns': ['BAND_ATT', 'TR_', 'R_FACTOR']},
    }

    GROUP_LABELS = {
        '实验组': '_E',
        '对照组': '_C',
        '通用': '',
    }

    # 信号
    selection_changed = Signal(list)  # 选中的指标ID列表
    search_text_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_metrics: Dict[str, Dict[str, Any]] = {}  # {metric_id: info}
        self._selected_metrics: Set[str] = set()
        self._build_lock = QMutex()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("指标筛选器")
        title_label.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 12px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.count_label = QLabel("0/0")
        self.count_label.setStyleSheet("color: #aaa; font-size: 10px;")
        title_layout.addWidget(self.count_label)
        main_layout.addLayout(title_layout)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索指标...")
        self.search_box.setStyleSheet("""
            QLineEdit { background: #1a1a2e; color: #e0e0e0; border: 1px solid #333; 
                       border-radius: 4px; padding: 4px 8px; }
        """)
        self.search_box.textChanged.connect(self._on_search)
        main_layout.addWidget(self.search_box)

        # 快捷按钮
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setStyleSheet("""
            QPushButton { background: #2196F3; color: white; border: none; 
                         border-radius: 3px; padding: 3px 8px; font-size: 10px; }
            QPushButton:hover { background: #1976D2; }
        """)
        self.select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("取消")
        self.deselect_all_btn.setStyleSheet("""
            QPushButton { background: #555; color: white; border: none; 
                         border-radius: 3px; padding: 3px 8px; font-size: 10px; }
            QPushButton:hover { background: #777; }
        """)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        self.invert_btn = QPushButton("反选")
        self.invert_btn.setStyleSheet("""
            QPushButton { background: #FF9800; color: white; border: none; 
                         border-radius: 3px; padding: 3px 8px; font-size: 10px; }
            QPushButton:hover { background: #F57C00; }
        """)
        self.invert_btn.clicked.connect(self._invert_selection)
        btn_layout.addWidget(self.invert_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 树形筛选
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget { background: #1a1a2e; color: #e0e0e0; border: 1px solid #333; }
            QTreeWidget::item { padding: 2px; }
            QTreeWidget::item:selected { background: #2196F3; }
            QTreeWidget::item:hover { background: #2a2a4e; }
        """)
        self.tree.itemChanged.connect(self._on_item_changed)
        main_layout.addWidget(self.tree)

        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        main_layout.addWidget(self.stats_label)

        self.setStyleSheet("background: #16213e;")

    def set_metrics(self, metric_definitions: Dict[str, Dict[str, Any]]):
        """设置指标定义并构建树

        Args:
            metric_definitions: {metric_id: {name, unit, location, group, category, ...}}
        """
        with QMutexLocker(self._build_lock):
            self._all_metrics = metric_definitions
            self._build_tree()

    def _build_tree(self):
        """构建树形结构"""
        self.tree.clear()
        self.tree.blockSignals(True)

        # 分类指标
        categorized = {cat: [] for cat in self.METRIC_CATEGORIES}
        uncategorized = []

        for mid, info in self._all_metrics.items():
            placed = False
            for cat, cat_info in self.METRIC_CATEGORIES.items():
                for pattern in cat_info['patterns']:
                    if pattern in mid:
                        categorized[cat].append(mid)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                uncategorized.append(mid)

        # 构建树
        for cat, metric_ids in categorized.items():
            if not metric_ids:
                continue
            cat_info = self.METRIC_CATEGORIES[cat]
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, f"{cat_info['icon']} {cat} ({len(metric_ids)})")
            cat_item.setFlags(cat_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            cat_item.setCheckState(0, Qt.Unchecked)
            cat_item.setData(0, Qt.UserRole, 'category')

            for mid in sorted(metric_ids):
                child = QTreeWidgetItem(cat_item)
                info = self._all_metrics.get(mid, {})
                child.setText(0, f"  {mid}")
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole, mid)

                # Tooltip
                child.setToolTip(0, f"{mid}: {info.get('name', '')} [{info.get('unit', '')}]")

        # 未分类
        if uncategorized:
            other_item = QTreeWidgetItem(self.tree)
            other_item.setText(0, f"其他 ({len(uncategorized)})")
            other_item.setFlags(other_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            other_item.setCheckState(0, Qt.Unchecked)
            other_item.setData(0, Qt.UserRole, 'category')

            for mid in sorted(uncategorized):
                child = QTreeWidgetItem(other_item)
                child.setText(0, f"  {mid}")
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole, mid)

        self.tree.blockSignals(False)
        self.tree.expandAll()
        self._update_stats()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """处理选择变化"""
        self.tree.blockSignals(True)

        data = item.data(0, Qt.UserRole)
        if data == 'category':
            # 父节点: 同步子节点
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        else:
            # 叶节点: 更新父节点状态
            parent = item.parent()
            if parent:
                checked = sum(1 for i in range(parent.childCount())
                              if parent.child(i).checkState(0) == Qt.Checked)
                total = parent.childCount()
                if checked == total:
                    parent.setCheckState(0, Qt.Checked)
                elif checked == 0:
                    parent.setCheckState(0, Qt.Unchecked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)

        self.tree.blockSignals(False)
        self._update_selection()

    def _update_selection(self):
        """更新选中列表"""
        self._selected_metrics.clear()

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                if child.checkState(0) == Qt.Checked:
                    mid = child.data(0, Qt.UserRole)
                    if mid and mid != 'category':
                        self._selected_metrics.add(mid)

        self._update_stats()
        self.selection_changed.emit(list(self._selected_metrics))

    def _select_all(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Checked)
            for j in range(item.childCount()):
                item.child(j).setCheckState(0, Qt.Checked)
        self.tree.blockSignals(False)
        self._update_selection()

    def _deselect_all(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            for j in range(item.childCount()):
                item.child(j).setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_selection()

    def _invert_selection(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                current = child.checkState(0)
                child.setCheckState(0, Qt.Unchecked if current == Qt.Checked else Qt.Checked)
            # 更新父节点
            checked = sum(1 for j in range(item.childCount())
                          if item.child(j).checkState(0) == Qt.Checked)
            total = item.childCount()
            if checked == total:
                item.setCheckState(0, Qt.Checked)
            elif checked == 0:
                item.setCheckState(0, Qt.Unchecked)
            else:
                item.setCheckState(0, Qt.PartiallyChecked)
        self.tree.blockSignals(False)
        self._update_selection()

    def _on_search(self, text: str):
        """搜索过滤"""
        self.search_text_changed.emit(text)
        if not text:
            # 显示全部
            for i in range(self.tree.topLevelItemCount()):
                self.tree.topLevelItem(i).setHidden(False)
            return

        text_lower = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            has_visible = False
            for j in range(item.childCount()):
                child = item.child(j)
                mid = child.data(0, Qt.UserRole) or ''
                if text_lower in mid.lower():
                    child.setHidden(False)
                    has_visible = True
                else:
                    child.setHidden(True)
            item.setHidden(not has_visible)

    def _update_stats(self):
        """更新统计显示"""
        self.count_label.setText(f"{len(self._selected_metrics)}/{len(self._all_metrics)}")

        # 分类统计
        stats = {}
        for mid in self._selected_metrics:
            for cat, cat_info in self.METRIC_CATEGORIES.items():
                for pattern in cat_info['patterns']:
                    if pattern in mid:
                        stats[cat] = stats.get(cat, 0) + 1
                        break

        stat_text = ' | '.join(f"{cat}: {n}" for cat, n in sorted(stats.items()))
        self.stats_label.setText(stat_text if stat_text else "未选择指标")

    def get_selected_metrics(self) -> List[str]:
        """获取选中的指标ID列表"""
        return list(self._selected_metrics)

    def set_selected_metrics(self, metric_ids: List[str]):
        """设置选中指标"""
        self.tree.blockSignals(True)
        target_set = set(metric_ids)

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                mid = child.data(0, Qt.UserRole)
                state = Qt.Checked if mid in target_set else Qt.Unchecked
                child.setCheckState(0, state)

            # 更新父节点
            checked = sum(1 for j in range(item.childCount())
                          if item.child(j).checkState(0) == Qt.Checked)
            total = item.childCount()
            if checked == total:
                item.setCheckState(0, Qt.Checked)
            elif checked == 0:
                item.setCheckState(0, Qt.Unchecked)
            else:
                item.setCheckState(0, Qt.PartiallyChecked)

        self.tree.blockSignals(False)
        self._update_selection()