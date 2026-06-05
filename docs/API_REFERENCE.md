# API Reference — 乘用车座椅综合性能评测系统 v3.5

## MetricComputer

### compute(metric_id, ctx) → float

计算单个指标。支持26个指标（17个直接注册 + 9个SRS/FDS/STFT子指标）。

**参数:**
- `metric_id`: str — 指标ID，如 "SEAT_Z", "HIC15", "SRS_MRS" 等
- `ctx`: MetricComputeContext — 包含 ax/ay/az 数组 + sample_rate + 可选 floor 数据

**返回:**
- `float` — 指标值；`-1.0` 表示数据不足

**抛出:**
- `ValueError` — 当 metric_id 未注册时

**示例:**
```python
from core.core.seat_evaluation.metric_computer import MetricComputer, MetricComputeContext

computer = MetricComputer(operator_system)
ctx = MetricComputeContext(
    ax=arr_ax, ay=arr_ay, az=arr_az,
    sample_rate=100.0,
    floor_az=floor_arr_az  # 可选
)
seat_z = computer.compute("SEAT_Z", ctx)
srs_mrs = computer.compute("SRS_MRS", ctx)
```

### 支持指标列表

| 类别 | 指标 |
|------|------|
| 频域 | SEAT_Z, SEAT_XY, TR_Z, AW_Z, AW_XY, VDV_Z, OVTV, R_FACTOR, DISP_TR, DISP_HR |
| 冲击 | HIC15, ACC_H_PEAK, JERK_H, SRS_MRS, SRS_Q, SRS_PV, SRS_ATT |
| 疲劳 | FDS_D, FDS_R, RFC_CC |
| 脊柱 | S_D |
| 时频 | STFT_FC, STFT_KT, STFT_CE |
| 基础 | ACC_RMS, ACC_PEAK |

### verify_all_metrics_registered() → bool

验证所有 metadata 定义的指标均已通过 compute() 可计算。返回 True/False。

---

## MultiChannelSeatEvaluationEngine (engine_v2.py)

### evaluate(event_data) → Dict

执行多通道座椅评测。

**参数:**
- `event_data`: dict — 包含 event_id, event_type, metrics, raw_data 等

**返回:**
- `dict` — 包含 trigger_id, event_type, metrics, overall_score, risk_level

---

## diagnose

### generate_single_group_diagnosis(metrics) → SingleGroupDiagnosis

生成单组诊断结果。

**参数:**
- `metrics`: Dict[str, float] — 指标计算结果

**返回:**
- `SingleGroupDiagnosis` — 包含 isolation/head_safety/fatigue 三层诊断 + weakest_link + conclusion

---

## FullTimeseriesEvaluator

### run_full_pipeline() → Dict

执行全时域滑动窗口评测管线（8步）。

**返回:**
- `dict` — 包含 window_analysis, event_analysis, spectrum, stft, statistics, comprehensive

---

## 已弃用 API

以下 API 已弃用，请使用对应的 v2 版本：

| 弃用 API | 替代 |
|----------|------|
| `SeatEvaluationEngine` (engine.py) | `MultiChannelSeatEvaluationEngine` (engine_v2.py) |
| `ComparativeEvaluationEngine` (comparative_engine.py) | `MultiChannelComparativeEngine` (comparative_engine_v2.py) |