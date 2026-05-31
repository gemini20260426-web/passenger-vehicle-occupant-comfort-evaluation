# 多源数据源管理同步优化方案

## 引言
本方案针对左侧控制面板的数据源管理模块与右侧多源同步配置标签页内容不同步的问题，提出提取右侧模块替换左侧的思路，创建新脚本，并确保UI风格一致。方案基于代码分析，确保只连接真实数据。

## 问题分析
- **左侧模块** (`modules/ui/left_control_panel/data_source_control.py`)：使用 DataSourceControlPanel 类，包含数据源概况组、数据源列表组（有占位符）和状态监控组。数据存储在 self.data_sources 字典中，通过 QTimer 更新。
- **右侧模块** (`modules/ui/left_control_panel/multi_source_sync_config_panel.py`)：在 _create_data_sources_tab 方法中创建详细界面，包括概况和 QTableWidget 表格。
- **不同步原因**：独立数据维护，缺少共享机制。
- **风险**：信号兼容性、UI风格匹配。

## 解决方案设计
- **核心思路**：创建 `unified_data_source_manager.py`，提取右侧逻辑，调整为左侧风格。左侧嵌入此组件，数据通过 UnifiedDataFlowManager 共享。
- **UI一致性**：使用 QGroupBox、QVBoxLayout、emoji 标题、中文字体。
- **数据同步**：使用 Signal 广播变化，只用真实数据。

## 实施步骤

### 步骤1: 创建新脚本 `unified_data_source_manager.py`
路径：`modules/ui/left_control_panel/unified_data_source_manager.py`

```
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout, QLabel, QTableWidget, QHeaderView
from PySide6.QtCore import Signal, QTimer
from .base_control_panel import BaseControlPanel
from core.core.unified_data_flow_manager import UnifiedDataFlowManager

class UnifiedDataSourceManager(BaseControlPanel):
    data_source_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__("📊 统一数据源管理", parent)
        self.manager = UnifiedDataFlowManager()
        self.data_sources = {}
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)

    def init_ui(self):
        # 概况组
        overview_group = QGroupBox("📊 数据源概况")
        overview_layout = QGridLayout(overview_group)
        self.total_sources_label = QLabel("总数据源: 0")
        // ... 添加其他标签 ...
        overview_layout.addWidget(self.total_sources_label, 0, 0)
        self.total_sources_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        self.inner_layout.addWidget(overview_group)

        # 表格组
        sources_group = QGroupBox("📋 数据源列表")
        sources_layout = QVBoxLayout(sources_group)
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(6)
        self.sources_table.setHorizontalHeaderLabels(["源ID", "名称", "类型", "状态", "数据率", "操作"])
        header = self.sources_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        sources_layout.addWidget(self.sources_table)
        self.inner_layout.addWidget(sources_group)

        # 按钮
        refresh_btn = QPushButton("🔄 刷新状态")
        refresh_btn.clicked.connect(self.refresh_data)
        self.inner_layout.addWidget(refresh_btn)

    def update_status(self):
        self.data_sources = self.manager.get_data_sources()
        self._populate_table()
        self.data_source_updated.emit(self.data_sources)

    def _populate_table(self):
        self.sources_table.setRowCount(len(self.data_sources))
        for i, source in enumerate(self.data_sources.values()):
            self.sources_table.setItem(i, 0, QTableWidgetItem(str(source['id'])))
            // ... 其他列 ...

    def refresh_data(self):
        self.update_status()
```

### 步骤2: 修改左侧控制面板 (`data_source_control.py`)
在 `__init__` 中添加 `self.unified_manager = UnifiedDataSourceManager(self)`，在 `init_ui` 中嵌入。

### 步骤3: 修改右侧模块 (`multi_source_sync_config_panel.py`)
引用 UnifiedDataSourceManager，连接信号。

### 步骤4: 集成到主UI
在 `panel_manager.py` 中注册新组件。

### 步骤5: UI一致性保障
保持中文标签、布局匹配。

## 测试计划
- **单元测试**：验证列表同步。
- **集成测试**：运行主程序，检查实时更新。
- **性能测试**：监控延迟。
- **边缘情况**：无数据、断开等。

## 后续步骤
如果中断，继续从步骤1开始实施。更新日期： [当前日期]
