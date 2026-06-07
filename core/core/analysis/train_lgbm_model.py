#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LightGBM 模型训练脚本 — Phase 1 核心执行入口

功能:
  1. 加载训练数据 (X, y)
  2. SMOTE 类别均衡
  3. LightGBM 训练 + 验证
  4. 保存模型到 core/models/
  5. 输出训练报告

用法:
    # 方式1: 从 CSV 生成 + 训练 (一步到位)
    python -m core.core.analysis.train_lgbm_model \
        --csv 徐宁数据/模拟数据/sim_25min_full.csv \
        --max_samples 50000

    # 方式2: 从已有 .npz 训练
    python -m core.core.analysis.train_lgbm_model \
        --data training_data.npz

    # 方式3: 从 test CSV 训练 (有 event_label 列)
    python -m core.core.analysis.train_lgbm_model \
        --csv test/test_data_seat_vibration.csv \
        --use_label_column
"""

import os
import sys
import argparse
import logging
import time
import numpy as np
from typing import Optional, Tuple
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('train_lgbm')


def load_training_data(
    data_path: Optional[str] = None,
    csv_path: Optional[str] = None,
    event_csv: Optional[str] = None,
    max_samples: int = 50000,
    use_label_column: bool = False,
    data_dir: Optional[str] = None,
    supplement_missing: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """加载训练数据

    Args:
        data_path: .npz 文件路径
        csv_path: CSV 文件路径
        event_csv: 事件标注 CSV 路径 (event_analysis.csv)
        max_samples: 最大样本数
        use_label_column: 是否使用 CSV 中的 event_label 列
        data_dir: data_output 目录 (批量模式, 自动配对)

    Returns:
        (X, y) 训练数据
    """
    # 优先级: data_dir > csv_path > data_path > 合成数据
    if data_dir and os.path.isdir(data_dir):
        from core.core.analysis.batch_training_data_generator import BatchTrainingDataGenerator
        from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
        gen = BatchTrainingDataGenerator(data_output_dir=data_dir, max_windows_per_file=max_samples)
        X, y, stats = gen.generate_all(output_path=data_path or 'training_data_real.npz')
        logger.info(f"从 data_output 批量生成训练数据: {X.shape[0]} 样本, {X.shape[1]} 特征")

        # P0-2: 补充缺失的事件类别
        if supplement_missing:
            present_classes = set(y)
            all_classes = set(range(len(BEHAVIOR_TYPES_V2)))
            missing_classes = all_classes - present_classes
            if missing_classes:
                logger.info(f"检测到 {len(missing_classes)} 个缺失类别: "
                            f"{[BEHAVIOR_TYPES_V2[i] for i in sorted(missing_classes)]}")
                X, y = supplement_missing_classes(X, y, missing_classes, BEHAVIOR_TYPES_V2)
                logger.info(f"补充后: {X.shape[0]} 样本, {len(set(y))} 类")
            else:
                logger.info(f"所有 {len(BEHAVIOR_TYPES_V2)} 类已覆盖，无需补充")
        return X, y

    if csv_path and os.path.exists(csv_path):
        if use_label_column:
            X, y = _load_from_labeled_csv(csv_path)
        elif event_csv and os.path.exists(event_csv):
            from core.core.analysis.fast_training_data_generator import FastTrainingDataGenerator
            gen = FastTrainingDataGenerator(
                csv_path=csv_path,
                event_csv=event_csv,
                max_windows=max_samples,
            )
            X, y = gen.generate()
            logger.info(f"从 CSV + 事件标注生成训练数据: {X.shape[0]} 样本")
        else:
            from core.core.analysis.training_data_generator import TrainingDataGenerator
            gen = TrainingDataGenerator(
                csv_path=csv_path,
                max_samples=max_samples,
            )
            X, y = gen.generate()
        return X, y

    if data_path and os.path.exists(data_path):
        logger.info(f"从 {data_path} 加载数据...")
        data = np.load(data_path, allow_pickle=True)
        X, y = data['X'], data['y']
        logger.info(f"已加载: {X.shape[0]} 样本, {X.shape[1]} 特征")
        return X, y

    # 兜底: 合成数据
    from core.core.analysis.generate_synthetic_data import generate_synthetic_data
    X, y = generate_synthetic_data(n_samples_per_class=400)
    logger.info(f"生成合成训练数据: {X.shape[0]} 样本, {X.shape[1]} 特征")
    return X, y


def _load_from_labeled_csv(csv_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """从带 event_label 列的 CSV 加载训练数据"""
    import pandas as pd
    from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter
    from core.core.analysis.core_types import BEHAVIOR_TYPES_V2

    df = pd.read_csv(csv_path)
    logger.info(f"CSV: {df.shape[0]} 行, 列: {list(df.columns)}")

    if 'event_label' not in df.columns:
        raise ValueError("CSV 缺少 event_label 列")

    adapter = FeatureAdapter()
    label_to_id = {name: i for i, name in enumerate(BEHAVIOR_TYPES_V2)}

    # 构建滑动窗口特征
    window_size = 10
    features_list = []
    labels_list = []

    for i in range(window_size, len(df)):
        window = df.iloc[i - window_size:i]
        event_label = df.iloc[i]['event_label']

        if event_label not in label_to_id:
            continue

        # 提取窗口特征
        ax = window['ax'].values
        ay = window['ay'].values
        az = window['az'].values
        speed = window['speed_kmh'].values
        steering = window['steering_deg'].values

        feat_dict = {
            'ax_mean': np.mean(ax), 'ax_std': np.std(ax),
            'ax_min': np.min(ax), 'ax_max': np.max(ax),
            'ax_rms': np.sqrt(np.mean(ax**2)),
            'ax_skewness': _skewness(ax), 'ax_kurtosis': _kurtosis(ax),
            'ay_mean': np.mean(ay), 'ay_std': np.std(ay),
            'ay_rms': np.sqrt(np.mean(ay**2)),
            'ay_skewness': _skewness(ay),
            'az_mean': np.mean(az), 'az_std': np.std(az),
            'az_rms': np.sqrt(np.mean(az**2)),
            'speed_mean': np.mean(speed), 'speed_std': np.std(speed),
            'speed_range': np.max(speed) - np.min(speed),
            'wheel_std': np.std(steering),
            'wheel_range': np.max(steering) - np.min(steering),
            'wheel_rms': np.sqrt(np.mean(steering**2)),
        }

        X_vec = adapter.get_feature_vector(feat_dict)
        features_list.append(X_vec)
        labels_list.append(label_to_id[event_label])

    X = np.array(features_list, dtype=np.float32)
    y = np.array(labels_list, dtype=np.int32)
    logger.info(f"从 labeled CSV 生成: {X.shape[0]} 样本")
    return X, y


def _skewness(x: np.ndarray) -> float:
    std = np.std(x)
    if std < 1e-8:
        return 0.0
    return float(np.mean((x - np.mean(x))**3) / std**3)


def _kurtosis(x: np.ndarray) -> float:
    std = np.std(x)
    if std < 1e-8:
        return 0.0
    return float(np.mean((x - np.mean(x))**4) / std**4 - 3)


def supplement_missing_classes(
    X: np.ndarray,
    y: np.ndarray,
    missing_classes: set,
    class_names: list,
    samples_per_class: int = 200,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """用合成数据补充真实数据中缺失的事件类别 (P0-2)

    Args:
        X: 特征矩阵 (n_samples, n_features)
        y: 标签数组 (n_samples,)
        missing_classes: 缺失的类别索引集合
        class_names: 所有类别名称列表 (BEHAVIOR_TYPES_V2)
        samples_per_class: 每类合成的样本数
        random_state: 随机种子

    Returns:
        (X_augmented, y_augmented) 补充后的数据
    """
    from core.core.analysis.generate_synthetic_data import generate_synthetic_data

    logger.info(f"补充缺失类别: {len(missing_classes)} 类, 每类 {samples_per_class} 个合成样本")

    X_synth, y_synth = generate_synthetic_data(
        samples_per_class=samples_per_class,
        random_state=random_state,
    )

    # 只取缺失的类别
    missing_mask = np.isin(y_synth, list(missing_classes))
    X_supplement = X_synth[missing_mask]
    y_supplement = y_synth[missing_mask]

    if len(X_supplement) == 0:
        logger.warning("合成数据中未找到缺失类别，跳过补充")
        return X, y

    missing_names = [class_names[i] for i in missing_classes if i < len(class_names)]
    logger.info(f"补充样本: {len(X_supplement)} 个, 类别: {missing_names}")

    X_augmented = np.vstack([X, X_supplement])
    y_augmented = np.concatenate([y, y_supplement])

    return X_augmented, y_augmented


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 500,
    max_depth: int = 10,
    learning_rate: float = 0.03,
    num_leaves: int = 63,
    skip_smote: bool = False,
) -> dict:
    """训练 LightGBM 模型

    Args:
        X: 特征矩阵
        y: 标签数组
        test_size: 验证集比例
        random_state: 随机种子

    Returns:
        训练指标字典
    """
    import lightgbm as lgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report, confusion_matrix
    )
    from imblearn.over_sampling import SMOTE

    from core.core.analysis.core_types import BEHAVIOR_TYPES_V2
    from core.core.analysis.layer4_behavior_classification.model_persistence import ModelPersistence

    id_to_label = {i: name for i, name in enumerate(BEHAVIOR_TYPES_V2)}
    n_classes = len(BEHAVIOR_TYPES_V2)

    # 类别分布
    logger.info(f"训练数据: {X.shape[0]} 样本, {X.shape[1]} 特征, {n_classes} 类")
    logger.info("原始标签分布:")
    for label_id, count in Counter(y).most_common(10):
        name = id_to_label.get(label_id, f'id_{label_id}')
        logger.info(f"  {name}: {count}")

    # SMOTE 过采样 (如果外部已做 SMOTE 则跳过)
    if not skip_smote:
        logger.info("执行 SMOTE 过采样...")
        min_class_count = min(Counter(y).values())
        k_neighbors = min(5, min_class_count - 1, 3)
        if k_neighbors < 1:
            k_neighbors = 1

        smote = SMOTE(
            sampling_strategy='auto',
            k_neighbors=k_neighbors,
            random_state=random_state,
        )
        X_res, y_res = smote.fit_resample(X, y)
        logger.info(f"SMOTE 完成: {len(X)} → {len(X_res)} 样本")
        logger.info("均衡后标签分布:")
        for label_id, count in Counter(y_res).most_common(10):
            name = id_to_label.get(label_id, f'id_{label_id}')
            logger.info(f"  {name}: {count}")
    else:
        X_res, y_res = X, y
        logger.info("跳过 SMOTE (外部已处理)")

    # 训练/验证集划分
    X_train, X_val, y_train, y_val = train_test_split(
        X_res, y_res, test_size=test_size,
        random_state=random_state, stratify=y_res,
    )
    logger.info(f"训练集: {len(X_train)}, 验证集: {len(X_val)}")

    # 训练 LightGBM
    logger.info("开始训练 LightGBM...")
    t0 = time.time()

    model = lgb.LGBMClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        num_leaves=num_leaves,
        learning_rate=learning_rate,
        objective='multiclass',
        num_class=n_classes,
        class_weight='balanced',
        random_state=random_state,
        n_jobs=-1,
        verbose=-1,
        min_child_samples=10,
        subsample=0.8,
        colsample_bytree=0.8,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric='multi_logloss',
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(20)],
    )

    train_time = time.time() - t0
    logger.info(f"训练完成: {train_time:.1f}s")

    # 评估
    import pandas as pd
    from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter
    adapter = FeatureAdapter()
    X_val_df = pd.DataFrame(X_val, columns=adapter.feature_names)
    y_pred = model.predict(X_val_df)
    y_proba = model.predict_proba(X_val_df)

    accuracy = accuracy_score(y_val, y_pred)
    f1_macro = f1_score(y_val, y_pred, average='macro', zero_division=0)
    f1_weighted = f1_score(y_val, y_pred, average='weighted', zero_division=0)

    logger.info("=" * 60)
    logger.info(f"准确率 (Accuracy):  {accuracy:.4f} ({accuracy*100:.1f}%)")
    logger.info(f"F1 (Macro):          {f1_macro:.4f}")
    logger.info(f"F1 (Weighted):       {f1_weighted:.4f}")
    logger.info(f"训练用时:             {train_time:.1f}s")
    logger.info("=" * 60)

    # 分类报告
    print("\n=== 分类报告 (Top-15 类) ===")
    report = classification_report(
        y_val, y_pred,
        labels=list(range(n_classes)),
        target_names=[id_to_label.get(i, f'id_{i}') for i in range(n_classes)],
        zero_division=0,
        output_dict=True,
    )
    # 只显示有样本的类
    present_classes = sorted(set(y_val))
    for label_id in present_classes[:15]:
        name = id_to_label.get(label_id, f'id_{label_id}')
        if name in report:
            r = report[name]
            print(f"  {name:30s}: prec={r['precision']:.3f}, "
                  f"recall={r['recall']:.3f}, f1={r['f1-score']:.3f}, "
                  f"support={int(r['support'])}")

    # 特征重要性
    importances = model.feature_importances_
    print("\n=== 特征重要性 Top-10 ===")
    sorted_idx = np.argsort(importances)[::-1]
    for rank, idx in enumerate(sorted_idx[:10]):
        name = adapter.feature_names[idx]
        print(f"  {rank+1:2d}. {name:30s}: {importances[idx]:.4f}")

    # 保存模型
    persistence = ModelPersistence()

    # Phase 2: 拟合概率校准器
    from core.core.analysis.layer4_behavior_classification.probability_calibrator import ProbabilityCalibrator
    calibrator = ProbabilityCalibrator()
    cal_metrics = calibrator.fit(X_val_df, y_val, model, method='both')
    logger.info(f"概率校准完成: ECE={cal_metrics.get('ece', 0):.4f}, "
                f"temperature={cal_metrics.get('temperature', 1.0):.3f}")

    model_path = persistence.save(
        model=model,
        event_types=BEHAVIOR_TYPES_V2,
        feature_names=adapter.feature_names,
        metrics={
            'accuracy': float(accuracy),
            'f1_macro': float(f1_macro),
            'f1_weighted': float(f1_weighted),
            'train_samples': int(len(X_train)),
            'val_samples': int(len(X_val)),
            'train_time_s': float(train_time),
        },
        calibration=calibrator.get_params(),
    )
    logger.info(f"模型已保存: {model_path}")

    return {
        'accuracy': accuracy,
        'f1_macro': f1_macro,
        'f1_weighted': f1_weighted,
        'model_path': model_path,
        'train_time': train_time,
    }


def verify_model():
    """验证模型加载和推理"""
    from core.core.analysis.layer4_behavior_classification.ml_classifier import LightGBMClassifier
    from core.core.analysis.layer4_behavior_classification.hybrid_classifier import HybridBehaviorClassifier

    logger.info("=== 模型验证 ===")

    # 1. 直接加载 LightGBMClassifier
    clf = LightGBMClassifier()
    clf.load_or_train()
    logger.info(f"LightGBMClassifier ready: {clf.is_ready()}")

    if clf.is_ready():
        # 测试推理
        import numpy as np
        from core.core.analysis.layer4_behavior_classification.feature_adapter import FeatureAdapter
        adapter = FeatureAdapter()
        dummy_vec = np.random.randn(55).astype(np.float32)
        from core.core.analysis.core_types import FrameFeatures
        feats = FrameFeatures(timestamp=0.0)
        feats.temporal['ax_mean'] = float(dummy_vec[0])

        from core.core.analysis.core_types import (
            ManeuverEvent, BehaviorCategory, BEHAVIOR_TYPES_V2,
        )
        event = ManeuverEvent(
            id='test_001',
            type='braking',
            category=BehaviorCategory.LONGITUDINAL,
            start_time=0.0,
            end_time=2.0,
            duration=2.0,
            peak_ax=-3.5,
            confidence=0.75,
            speed_range=(40.0, 20.0),
        )
        result = clf.classify(event, feats)
        logger.info(f"推理测试: {result[0]} (conf={result[2]:.3f})")

    # 2. HybridBehaviorClassifier 集成验证
    hbc = HybridBehaviorClassifier()
    logger.info(f"HybridBehaviorClassifier ml_ready: {hbc.ml_classifier.is_ready()}")

    if hbc.ml_classifier.is_ready():
        importance = hbc.get_ml_feature_importance()
        if importance:
            print("\n=== ML 特征重要性 Top-5 ===")
            for name, imp in list(importance.items())[:5]:
                print(f"  {name}: {imp:.4f}")

    logger.info("模型验证完成")


def main():
    parser = argparse.ArgumentParser(
        description='LightGBM 驾驶行为分类器训练脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从模拟数据生成训练数据并训练
  python -m core.core.analysis.train_lgbm_model --csv 徐宁数据/模拟数据/sim_25min_full.csv --max_samples 50000

  # 从已有 .npz 训练
  python -m core.core.analysis.train_lgbm_model --data training_data.npz

  # 从带标签的 CSV 训练
  python -m core.core.analysis.train_lgbm_model --csv test/test_data_seat_vibration.csv --use_label_column

  # 从 data_output 真实数据训练 (批量模式)
  python -m core.core.analysis.train_lgbm_model --data_dir data_output

  # 从单个 parsed_data CSV + 事件标注训练
  python -m core.core.analysis.train_lgbm_model \\
      --csv data_output/parsed_data_20260606_094258.csv \\
      --event_csv data_output/expert_evaluation_20260606_095159/event_analysis.csv

  # 渐进式训练 (合成 + 真实)
  python -m core.core.analysis.train_lgbm_model --data_dir data_output --progressive

  # 仅验证已有模型
  python -m core.core.analysis.train_lgbm_model --verify
        """,
    )
    parser.add_argument('--csv', type=str, help='输入 CSV 文件路径')
    parser.add_argument('--event_csv', type=str, help='事件标注 CSV 路径 (event_analysis.csv)')
    parser.add_argument('--data', type=str, help='.npz 训练数据文件路径')
    parser.add_argument('--data_dir', type=str, help='data_output 目录 (批量模式, 自动配对)')
    parser.add_argument('--output', type=str, default='training_data.npz', help='训练数据输出路径')
    parser.add_argument('--max_samples', type=int, default=50000, help='最大处理样本数')
    parser.add_argument('--use_label_column', action='store_true', help='使用 CSV 中 event_label 列')
    parser.add_argument('--progressive', action='store_true', help='启用渐进式训练 (合成 + 真实)')
    parser.add_argument('--verify', action='store_true', help='仅验证已有模型')
    parser.add_argument('--test_size', type=float, default=0.2, help='验证集比例')

    args = parser.parse_args()

    if args.verify:
        verify_model()
        return

    if not args.csv and not args.data and not args.data_dir:
        parser.error("请提供 --csv, --data 或 --data_dir 参数")

    # 渐进式训练模式
    if args.progressive:
        if not args.data_dir:
            parser.error("--progressive 需要 --data_dir 参数")
        _run_progressive_training(args)
        return

    # 加载数据
    X, y = load_training_data(
        data_path=args.data,
        csv_path=args.csv,
        event_csv=args.event_csv,
        max_samples=args.max_samples,
        use_label_column=args.use_label_column,
        data_dir=args.data_dir,
    )

    if len(X) == 0:
        logger.error("未加载到训练数据")
        sys.exit(1)

    # 保存训练数据 (如果从 CSV 生成)
    if args.csv and not args.data:
        np.savez_compressed(args.output, X=X, y=y)
        logger.info(f"训练数据已缓存: {args.output}")

    # 训练
    results = train_model(X, y, test_size=args.test_size)

    # 验证
    verify_model()

    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"  准确率: {results['accuracy']*100:.1f}%")
    print(f"  模型路径: {results['model_path']}")
    print(f"  训练用时: {results['train_time']:.1f}s")
    print("=" * 60)


def _run_progressive_training(args):
    """渐进式训练: 合成 + 真实 混合"""
    from core.core.analysis.generate_synthetic_data import generate_synthetic_data
    from core.core.analysis.batch_training_data_generator import BatchTrainingDataGenerator
    from core.core.analysis.adaptive_balancer import AdaptiveBalancingStrategy
    from core.core.analysis.sensor_fault_augmenter import SensorFaultAugmenter
    from core.core.analysis.progressive_trainer import ProgressiveTrainingStrategy

    logger.info("=" * 60)
    logger.info("渐进式训练模式")
    logger.info("=" * 60)

    # 1. 生成合成数据 (基准)
    logger.info("\n[Step 1] 生成合成基准数据...")
    X_synth, y_synth = generate_synthetic_data(n_samples_per_class=400)
    logger.info(f"合成数据: {X_synth.shape[0]} 样本, {len(set(y_synth))} 类")

    # 2. 从 data_output 生成真实数据
    logger.info("\n[Step 2] 生成真实训练数据...")
    gen = BatchTrainingDataGenerator(
        data_output_dir=args.data_dir,
        max_windows_per_file=args.max_samples,
    )
    X_real, y_real, stats = gen.generate_all(output_path='training_data_real.npz')
    logger.info(f"真实数据: {X_real.shape[0]} 样本, {len(set(y_real))} 类")

    # 3. 传感器故障数据增强
    logger.info("\n[Step 3] 传感器故障数据增强...")
    aug = SensorFaultAugmenter()
    X_real, y_real = aug.generate_and_merge(X_real, y_real, n_samples=50)
    logger.info(f"增强后: {X_real.shape[0]} 样本")

    # 4. 阶梯式类别均衡
    logger.info("\n[Step 4] 阶梯式类别均衡...")
    balancer = AdaptiveBalancingStrategy(min_samples_per_class=10)
    X_real, y_real, bal_report = balancer.balance(
        X_real, y_real, BEHAVIOR_TYPES_V2,
        synthetic_data=(X_synth, y_synth),
    )
    logger.info(f"均衡后: {X_real.shape[0]} 样本")

    # 5. 渐进式训练
    logger.info("\n[Step 5] 渐进式训练 (5 阶段)...")
    trainer = ProgressiveTrainingStrategy()

    def train_fn(X, y):
        return train_model(X, y, test_size=args.test_size)

    results = trainer.train_progressive(
        X_synth, y_synth, X_real, y_real,
        train_fn=train_fn,
        class_names=BEHAVIOR_TYPES_V2,
    )

    # 验证
    verify_model()

    print("\n" + "=" * 60)
    print("渐进式训练完成！")
    best = max(results, key=lambda r: r.get('accuracy', r.get('eval_accuracy', 0)))
    print(f"  最佳阶段: {best['name']}")
    print(f"  准确率: {best.get('accuracy', best.get('eval_accuracy', 0))*100:.1f}%")
    print("=" * 60)


if __name__ == '__main__':
    main()