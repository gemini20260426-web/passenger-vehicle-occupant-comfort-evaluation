# 架构说明 — 乘用车座椅综合性能评测系统 v3.5

## 数据流

```
CAN/IMU 原始数据
    │
    ▼
┌─────────────────────────────────────────────┐
│  Parser Layer (data_parser.py / CAN parser) │
│  - 多编码自动检测 (UTF-8/GBK/GB2312)        │
│  - AA/BB 格式解析 + CAN 2.0B 帧解析         │
│  - 字段分类 + 自动标定                       │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Normalizer (data_reader_manager.py)         │
│  - 时间对齐 (2ms 容忍)                       │
│  - 多源同步 (CAN/IMU/CNAP)                  │
│  - 流式分块加载 (>200MB 自动分块)           │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Analysis Layer                             │
│  ┌─ event_detector.py   → 行为事件检测      │
│  ┌─ event_distributor.py → 事件分发中心      │
│  ┌─ full_timeseries_evaluator.py → 全时域   │
│  └─ analysis_result_cache.py → 结果缓存     │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Evaluation Engine (engine_v2.py)            │
│  - MetricComputer: 26个指标统一计算          │
│  - 三层位置: 头部/胸骨/座垫                  │
│  - CFC 滤波 (SAE J211-1)                    │
│  - 相干性检查 + 样本量校验                   │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Diagnosis Engine (diagnosis_engine.py)      │
│  - 三层诊断: isolation/head_safety/fatigue   │
│  - Weakest Link 算法                         │
│  - pass/warn/fail/na 四种状态                │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Report / UI                                │
│  - 综合评分 + 风险等级                       │
│  - 波形可视化 + 趋势图                        │
│  - 事件回放 + 对比分析                       │
└─────────────────────────────────────────────┘
```

## 核心模块依赖

```
seat_evaluation/
├── metric_computer.py       ← 统一指标计算 (26个指标)
├── engine_v2.py             ← 多通道评测引擎 (推荐)
├── engine.py                ← [已弃用] v1.0 引擎
├── comparative_engine_v2.py ← 多通道对比引擎 (推荐)
├── comparative_engine.py    ← [已弃用] v1.0 对比引擎
├── diagnosis_engine.py      ← 三层诊断
├── full_timeseries_evaluator.py ← 全时域滑动窗口
├── operators.py             ← 9大算子系统
├── metadata_registry.py     ← 元数据管理中心
└── analysis_result_cache.py ← 分析结果缓存

analysis/
├── event_distributor.py     ← 事件分发中心
├── event_detector.py        ← 行为事件检测
├── core_types.py            ← 核心类型定义
└── ...

data_processing/
├── multi_source_cache.py    ← 多源数据缓存
├── multi_source_replay_controller.py ← 回放控制器
├── cache_registry.py        ← 缓存注册表
└── ...

visualization/
├── imu_pro_visualizer.py    ← 专业IMU可视化
└── ...

ui/
├── core_ui/                 ← 核心UI框架
├── monitoring_dashboard_components/ ← 监控面板
└── seat_evaluation/         ← 座椅评测UI
```

## 关键技术决策

| 决策 | 说明 |
|------|------|
| 采样率 | 默认 100Hz，支持 200Hz/1000Hz |
| CFC 滤波 | SAE J211-1: CFC60/600/1000 |
| 频率加权 | ISO 2631-1: Wk/Wd |
| 冲击标准 | HIC15 (FMVSS 208), SRS (MIL-STD-810H) |
| 疲劳标准 | Miner's Rule, FDS (ISO 2631-5) |