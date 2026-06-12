#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量统计分析标签页 — 全新图表模块版 v11.0
============================================

v11.0 更新:
  1. 全新 charts/ 模块 — 每张图表独立函数，统一设计系统，返回标准 matplotlib Figure
  2. 保留 v9.0 数据管线 (UnifiedEvaluationWorker)
  3. 保留 v10.0 专业仪表盘UI布局
  4. 完全替换 visualization_manager + advanced_charts
  5. 修复 QObject 导入、clear_data 兼容、np.isfinite 类型检查等历史问题

架构:
  statistics_analysis/
  ├── __init__.py
  ├── tab_main.py           ← StatisticsAnalysisTab (UI编排 + 数据管线)
  └── charts/               ← 全新图表渲染引擎
      ├── __init__.py
      ├── style.py          ← 统一设计系统 (颜色/字体/样式)
      ├── timeline.py       ← 事件时间线
      ├── psd.py            ← PSD功率谱密度
      └── radar.py          ← 雷达图/衰减/波形/SRS/热力图/STFT

作者: SciClaw AI Scientist
版本: 11.0.0
日期: 2026-06-12
"""
