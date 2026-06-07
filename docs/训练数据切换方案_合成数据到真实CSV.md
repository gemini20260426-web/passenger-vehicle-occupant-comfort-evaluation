# 训练数据切换方案：从合成数据集到真实 CSV 数据集

> **目标**: 将 LightGBM 模型训练数据从系统生成的合成数据集切换到 `data_output` 目录下由解析后的原始采集数据结果的 CSV 格式文件。

---

## 1. 现状分析

### 1.1 当前训练数据来源

| 来源 | 文件 | 说明 |
|------|------|------|
| 合成数据 | `generate_synthetic_data.py` | 基于领域知识参数分布生成 23 类 × 400 样本，共 ~9200 条 55 维特征向量 |
| 快速训练生成器 | `fast_training_data_generator.py` | 从 IMU CSV 文件滑动窗口提取 55 维特征，配合 expert_evaluation 标注 |

### 1.2 data_output 目录数据资产

```
data_output/
├── parsed_data_20260606_094258.csv    # IMU 多通道数据 (含 Ax, Ay, Az, Gx, Gy, Gz)
├── parsed_data_20260606_100404.csv    # IMU 多通道数据
├── parsed_data_20260606_104537.csv    # IMU 多通道数据
├── parsed_data_20260606_112655.csv    # IMU 多通道数据
├── parsed_data_20260606_175825.csv    # CAN 总线数据 (仅 speed/wheel，无 IMU)
├── behavior_results/
│   └── behavior_*.csv (50个)          # 空文件 (仅表头)
├── imu_behavior/
│   └── imu_behavior_*.csv (50个)      # 空文件 (仅表头)
├── expert_evaluation_20260606_095159/
│   └── event_analysis.csv             # 事件标注 (含 t_start, t_end, event 等)
├── expert_evaluation_20260606_101323/
│   └── event_analysis.csv             # 事件标注
└── expert_evaluation_20260606_110127/
    └── event_analysis.csv             # 事件标注
```

### 1.3 关键发现

| 发现 | 详情 |
|------|------|
| **IMU 数据可用** | `parsed_data_094258`、`100404`、`104537`、`112655` 四个文件包含完整的多通道 IMU 数据 (IMU1-IMU9, 含 Ax/Ay/Az/Gx/Gy/Gz) |
| **CAN 数据不完全** | `parsed_data_175825` 仅含 CAN 总线 speed/wheel，不适用于 IMU 特征提取 |
| **行为标注已存在** | 3 个 `expert_evaluation` 目录包含 `event_analysis.csv`，标注了事件类型、起止时间等 |
| **behavior_results 为空** | 50 个 behavior_results CSV 文件仅含表头，无实际行为记录 |
| **imu_behavior 为空** | 50 个 imu_behavior CSV 文件仅含表头，无实际数据 |

---

## 2. 核心差异分析

### 2.1 合成数据 vs 真实 CSV 数据

| 维度 | 合成数据 (`generate_synthetic_data.py`) | 真实 CSV 数据 (`FastTrainingDataGenerator`) |
|------|------|------|
| 数据来源 | 领域知识参数分布 + 高斯噪声 | 原始 IMU 传感器采集数据 |
| 特征生成 | 按预定义 (mean, std) 采样 | 滑动窗口 (500ms) 提取时域+频域+运动学特征 |
| 标签来源 | 每类生成固定数量样本 (BEHAVIOR_PARAMS) | 从 `event_analysis.csv` 读取事件 t_start/t_end 标注 |
| 样本量 | 23 类 × 400 = 9200 | 取决于数据长度和窗口步长 |
| 特征维度 | 55 维 | 55 维 (与 FeatureAdapter 一致) |
| 真实性 | 合成，与真实分布有偏差 | 真实采集，反映实际驾驶行为 |

### 2.2 数据格式差异

**parsed_data CSV 列结构 (IMU 数据):**

```csv
rel_time, channel, imu_name, Ax_m_s2, Ay_m_s2, Az_m_s2,
Gx_dps, Gy_dps, Gz_dps, Gx_rad_s, Gy_rad_s, Gz_rad_s, speed, wheel
```

- 多通道：IMU1(头部眉心-1), IMU2(头部眉心-2), IMU3(躯干T8-1), IMU4(躯干T8-2), IMU5(座垫R点-1), IMU6(座垫R点-2), IMU7(座椅底部-1), IMU8(座椅底部-2), IMU9(胸骨剑突-1)
- 主通道：IMU5 (座垫R点-1) 是最稳定的参考通道

**expert_evaluation event_analysis.csv 列结构:**

```csv
event, t_start, t_end, duration, speed_start,
e_Ax_RMS, c_Ax_RMS, atten_Ax_pct, e_Ay_RMS, c_Ay_RMS, ...
```

- `event`: 中文事件名 (复合工况、转向/变道、加速、制动减速、急刹车、蛇形驾驶、弯道加速 等)
- `t_start` / `t_end`: 事件起止时间 (秒)

### 2.3 事件名映射

`FastTrainingDataGenerator` 中已定义映射表 `EVENT_LABEL_MAP`，但需要扩充：

```python
# 现有映射 (13 种)
EVENT_LABEL_MAP = {
    '复合工况': 'cornering_braking',
    '制动减速': 'normal_deceleration',
    '加速': 'normal_acceleration',
    '转向': 'wide_turn',
    '急加速': 'aggressive_acceleration',
    '急减速': 'aggressive_deceleration',
    '紧急制动': 'emergency_braking',
    '变道': 'lane_change',
    '弯道': 'cornering_deceleration',
    '静止': 'stopped',
    '匀速': 'constant_speed',
    '正常': 'normal',
    '起步': 'launch',
}
```

**expert_evaluation 中实际出现的事件名** (需要补充映射):

| 中文事件名 | 系统事件类型 | 现有映射 |
|-----------|-------------|---------|
| 复合工况 | cornering_braking | 已存在 |
| 转向/变道 | lane_change | 需添加 |
| 加速 | normal_acceleration | 已存在 |
| 制动减速 | normal_deceleration | 已存在 |
| 左转 | tight_turn | 需添加 |
| 右转 | wide_turn | 需添加 |
| 急刹车 | emergency_braking | 需添加 |
| 弯道加速 | cornering_acceleration | 需添加 |
| 弯道减速 | cornering_deceleration | 需添加 |
| 蛇形驾驶 | weaving | 需添加 |
| 恒速行驶 | constant_speed | 需添加 |
| 车道保持 | lane_keeping | 需添加 |
| 正常加速 | normal_acceleration | 需添加 |
| 正常减速 | normal_deceleration | 需添加 |
| 激进加速 | aggressive_acceleration | 需添加 |
| 激进减速 | aggressive_deceleration | 需添加 |
| 大半径转弯 | wide_turn | 需添加 |
| 小半径转弯 | tight_turn | 需添加 |
| U型转弯 | u_turn | 需添加 |
| 急速变向 | rapid_direction_change | 需添加 |
| 侧滑风险 | skid_risk | 需添加 |
| 侧翻风险 | rollover_risk | 需添加 |
| 驻车 | stopped | 需添加 |
| 匀速直行 | straight_driving | 需添加 |

---

## 3. 解决方案

### 3.1 总体方案

采用 **四步走** 策略，渐进式完成从合成数据到真实 CSV 数据的切换：

```
Step 1: 数据匹配与事件名映射完善
Step 2: 批量训练数据生成
Step 3: 模型训练与评估
Step 4: 模型验证与部署
```

### 3.2 Step 1: 数据匹配与事件名映射完善

**目标**: 建立 parsed_data CSV 与 expert_evaluation event_analysis 的对应关系，完善事件名映射。

**需要修改的文件**: `core/core/analysis/fast_training_data_generator.py`

**修改内容**:

1. 扩充 `EVENT_LABEL_MAP` 字典，补充 expert_evaluation 中实际出现的事件名：

```python
EVENT_LABEL_MAP = {
    # 原有
    '复合工况': 'cornering_braking',
    '制动减速': 'normal_deceleration',
    '加速': 'normal_acceleration',
    '转向': 'wide_turn',
    '急加速': 'aggressive_acceleration',
    '急减速': 'aggressive_deceleration',
    '紧急制动': 'emergency_braking',
    '变道': 'lane_change',
    '弯道': 'cornering_deceleration',
    '静止': 'stopped',
    '匀速': 'constant_speed',
    '正常': 'normal',
    '起步': 'launch',
    # 新增
    '转向/变道': 'lane_change',
    '左转': 'tight_turn',
    '右转': 'wide_turn',
    '急刹车': 'emergency_braking',
    '弯道加速': 'cornering_acceleration',
    '弯道减速': 'cornering_deceleration',
    '蛇形驾驶': 'weaving',
    '恒速行驶': 'constant_speed',
    '车道保持': 'lane_keeping',
    '正常加速': 'normal_acceleration',
    '正常减速': 'normal_deceleration',
    '激进加速': 'aggressive_acceleration',
    '激进减速': 'aggressive_deceleration',
    '大半径转弯': 'wide_turn',
    '小半径转弯': 'tight_turn',
    'U型转弯': 'u_turn',
    '急速变向': 'rapid_direction_change',
    '侧滑风险': 'skid_risk',
    '侧翻风险': 'rollover_risk',
    '驻车': 'stopped',
    '匀速直行': 'straight_driving',
}
```

2. 建立 parsed_data ↔ expert_evaluation 数据配对规则：

```
parsed_data_20260606_094258.csv → expert_evaluation_20260606_095159
parsed_data_20260606_100404.csv → expert_evaluation_20260606_101323
parsed_data_20260606_104537.csv → expert_evaluation_20260606_110127
```

根据时间戳范围自动匹配。

### 3.3 Step 2: 批量训练数据生成

**需要新建的文件**: `core/core/analysis/batch_training_data_generator.py`

**功能**: 批量处理多个 parsed_data CSV 和对应的 expert_evaluation，生成合并的训练数据。

**核心逻辑**:

```python
class BatchTrainingDataGenerator:
    """批量训练数据生成器 — 处理多个 CSV 文件对"""

    def __init__(self, data_output_dir: str, primary_imu: str = 'IMU5'):
        self.data_output_dir = data_output_dir
        self.primary_imu = primary_imu

    def discover_data_pairs(self) -> List[Tuple[str, str]]:
        """自动发现 parsed_data CSV 与 expert_evaluation 的配对"""
        # 扫描 data_output 目录
        # 匹配 parsed_data_*.csv 与 expert_evaluation_* 目录
        ...

    def generate_all(self, output_path: str = 'training_data.npz',
                     window_size: int = 500, step_size: int = 250):
        """批量生成训练数据并合并保存"""
        all_X, all_y = [], []
        for csv_path, event_csv in self.discover_data_pairs():
            gen = FastTrainingDataGenerator(
                csv_path=csv_path,
                event_csv=event_csv,
                primary_imu=self.primary_imu,
                window_size=window_size,
                step_size=step_size,
            )
            X, y = gen.generate()
            all_X.append(X)
            all_y.append(y)
            logger.info(f"  {csv_path}: {X.shape[0]} 样本")

        X_merged = np.vstack(all_X)
        y_merged = np.concatenate(all_y)
        np.savez_compressed(output_path, X=X_merged, y=y_merged)
        logger.info(f"合并训练数据: {X_merged.shape[0]} 样本, {len(set(y_merged))} 类")
```

**使用方式**:

```bash
python -m core.core.analysis.batch_training_data_generator \
    --data_dir data_output \
    --output training_data_real.npz \
    --window_size 500 \
    --step_size 250
```

### 3.4 Step 3: 模型训练与评估

**使用现有脚本**: `train_lgbm_model.py`

**训练命令**:

```bash
# 使用真实 CSV 生成的数据训练
python -m core.core.analysis.train_lgbm_model \
    --data training_data_real.npz \
    --output training_data_real.npz

# 或直接一步到位 (从 CSV 生成 + 训练)
python -m core.core.analysis.train_lgbm_model \
    --csv data_output/parsed_data_20260606_094258.csv \
    --event_csv data_output/expert_evaluation_20260606_095159/event_analysis.csv \
    --max_samples 50000
```

**预期效果对比**:

| 指标 | 合成数据模型 | 真实 CSV 数据模型 (预期) |
|------|------------|----------------------|
| 准确率 | 85-88% | 80-90% (取决于数据质量和标注一致性) |
| F1 (Macro) | ~0.80 | ~0.75-0.85 |
| 泛化能力 | 对合成分布过拟合 | 对真实数据更鲁棒 |
| 推理置信度 | 偏高 (合成数据过度拟合) | 更真实反映不确定性 |

### 3.5 Step 4: 模型验证与部署

**验证清单**:

1. **模型加载验证**: 确保新模型能被 `ModelPersistence` 正确加载
2. **推理兼容性**: 确保 `LightGBMClassifier` 能使用新模型进行推理
3. **特征一致性**: 验证推理时 `FeatureAdapter` 输出的 55 维特征与训练时一致
4. **A/B 对比**: 使用现有 A/B 模型对比功能，对比新旧模型在同一数据上的推理差异
5. **实时推理测试**: 在实时监控中加载新模型，验证推理延迟和准确性

### 3.6 训练数据质量保障

**需要关注的问题**:

| 问题 | 风险等级 | 解决措施 |
|------|---------|---------|
| 类别不平衡 | 高 | SMOTE 过采样，设置合理的 k_neighbors |
| 事件标注不一致 | 中 | 检查 event_analysis 中同一事件名对应的时间窗口是否合理 |
| 重叠事件窗口 | 中 | 在 `_get_label()` 中处理重叠：优先选择置信度更高的事件类型 |
| 无效数据窗口 | 低 | 过滤标准差为 0 的窗口 (传感器未激活) |
| 采样率差异 | 低 | parsed_data 中 IMU 采样率约 1000Hz，设置正确的 fs 参数 |

---

## 4. 实施计划

### 4.1 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/core/analysis/fast_training_data_generator.py` | 修改 | 扩充 EVENT_LABEL_MAP 事件名映射，添加重叠事件处理 |
| `core/core/analysis/batch_training_data_generator.py` | 新建 | 批量训练数据生成器，支持多文件配对处理 |
| `core/core/analysis/train_lgbm_model.py` | 修改 | 添加 `--event_csv` 参数支持，支持直接传入事件标注文件 |
| `docs/训练数据切换方案_合成数据到真实CSV.md` | 新建 | 本方案文档 |

### 4.2 执行步骤

```
1. [修改] 扩充 fast_training_data_generator.py 的 EVENT_LABEL_MAP
   ├── 添加 expert_evaluation 中实际出现的事件名映射
   └── 添加重叠事件窗口处理逻辑

2. [新建] batch_training_data_generator.py
   ├── 实现 discover_data_pairs() 自动配对
   ├── 实现 generate_all() 批量生成
   └── 添加类分布统计和日志输出

3. [修改] train_lgbm_model.py
   ├── 添加 --event_csv 参数
   └── 修改 load_training_data() 支持事件标注 CSV 传入

4. [执行] 批量生成训练数据
   python -m core.core.analysis.batch_training_data_generator \
       --data_dir data_output --output training_data_real.npz

5. [执行] 训练模型
   python -m core.core.analysis.train_lgbm_model \
       --data training_data_real.npz

6. [验证] 模型推理测试
   python -m core.core.analysis.train_lgbm_model --verify

7. [部署] 将新模型文件复制到 core/models/ 目录
```

### 4.3 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 4 个 parsed_data 文件数据量不足 | 训练样本过少，准确率低 | 降低 window_size 和 step_size 增加样本密度；或使用更大的滑动窗口 |
| 事件标注与 IMU 时间轴不对齐 | 标签错误，模型学习错误模式 | 添加时间轴对齐校验，输出警告日志 |
| 某些事件类型样本过少 (< 5) | SMOTE 无法有效采样 | 自动跳过样本过少的类别，或从合成数据补充 |
| CAN 数据 (parsed_data_175825) 无法使用 | 损失一部分数据 | 仅使用 4 个 IMU 数据文件，或实现 CAN 数据特征提取适配器 |

---

## 5. 数据配对关系

### 5.1 自动配对规则

基于时间戳命名，parsed_data 和 expert_evaluation 的配对关系：

| parsed_data CSV | expert_evaluation 目录 | 时间匹配 |
|-----------------|----------------------|---------|
| `parsed_data_20260606_094258.csv` | `expert_evaluation_20260606_095159/` | 09:42 → 09:51 (约 9 分钟差) |
| `parsed_data_20260606_100404.csv` | `expert_evaluation_20260606_101323/` | 10:04 → 10:13 (约 9 分钟差) |
| `parsed_data_20260606_104537.csv` | `expert_evaluation_20260606_110127/` | 10:45 → 11:01 (约 16 分钟差) |
| `parsed_data_20260606_112655.csv` | 无对应评估 | 需单独评估 |
| `parsed_data_20260606_175825.csv` | 无对应评估 | CAN 数据，不适用 |

### 5.2 可用数据量估算

假设每个 parsed_data CSV 包含约 600 秒 (10 分钟) 的 IMU 数据：

- 采样率: ~1000 Hz
- 窗口大小: 500 点 (0.5s)
- 步长: 250 点 (0.25s)
- 每个文件窗口数: (600000 - 500) / 250 ≈ 2398 个窗口
- 4 个文件总计: 约 9592 个窗口
- 加上 expert_evaluation 标注的事件窗口: 约 200-400 个正样本

---

## 6. 总结

本方案通过以下核心改动，实现从合成数据到真实 CSV 数据的训练数据切换：

1. **完善事件名映射**: 将 expert_evaluation 中的中文事件名映射到系统 BEHAVIOR_TYPES_V2
2. **批量数据生成器**: 自动配对多个 parsed_data CSV 和 expert_evaluation，生成合并训练数据
3. **训练脚本增强**: 支持直接传入事件标注 CSV 进行训练
4. **渐进式迁移**: 保留合成数据作为兜底，先验证真实数据训练效果，再切换

预期效果：真实数据训练的模型在泛化能力和推理置信度校准方面优于合成数据模型，更准确地反映实际驾驶行为分布。