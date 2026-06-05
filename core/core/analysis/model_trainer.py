"""
驾驶事件模型训练器 — Optuna超参优化 + SMOTE过采样 + Platt Scaling概率校准

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 7.4-7.5 节。
"""

import numpy as np
import pickle
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)


class DrivingEventModelTrainer:
    """驾驶事件模型训练器

    提供:
    1. 按事件类型分别训练 (多二分类策略)
    2. SMOTE 过采样处理类别不平衡
    3. Optuna 贝叶斯超参优化
    4. Platt Scaling 概率校准
    5. 在线自适应增量更新
    """

    def __init__(self, model_dir: str = 'models/', random_state: int = 42):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.random_state = random_state
        self.models: Dict[str, object] = {}
        self.scalers: Dict[str, object] = {}
        self.feature_importances: Dict[str, np.ndarray] = {}
        self.training_history: List[dict] = []

    def train_per_event_type(self, X: np.ndarray, y: np.ndarray,
                              event_types: List[str],
                              use_smote: bool = True,
                              use_optuna: bool = True,
                              n_trials: int = 50) -> dict:
        """按事件类型分别训练 (多二分类策略)

        Args:
            X: [N, M] 特征矩阵
            y: [N] 标签向量 (事件类型字符串)
            event_types: 事件类型列表
            use_smote: 是否使用SMOTE过采样
            use_optuna: 是否使用Optuna超参优化
            n_trials: Optuna试验次数

        Returns:
            {'event_type': {'model': ..., 'f1': ..., 'accuracy': ...}}
        """
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score, train_test_split
        from sklearn.metrics import f1_score, accuracy_score, classification_report

        results = {}

        for etype in event_types:
            y_binary = (y == etype).astype(int)
            if y_binary.sum() < 10:
                logger.warning(f"事件类型 {etype} 样本不足 ({y_binary.sum()}), 跳过训练")
                continue

            logger.info(f"训练事件类型: {etype} (正样本={y_binary.sum()}, 负样本={len(y_binary) - y_binary.sum()})")

            # SMOTE 过采样
            if use_smote and y_binary.sum() < len(y_binary) * 0.3:
                try:
                    from imblearn.over_sampling import SMOTE
                    smote = SMOTE(random_state=self.random_state)
                    X_resampled, y_resampled = smote.fit_resample(X, y_binary)
                    logger.info(f"  SMOTE: {len(X)} → {len(X_resampled)} 样本")
                except ImportError:
                    logger.warning("  imbalanced-learn 未安装, 跳过SMOTE")
                    X_resampled, y_resampled = X, y_binary
            else:
                X_resampled, y_resampled = X, y_binary

            # 标准化
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_resampled)

            # 模型训练
            if use_optuna:
                model = self._optuna_train(X_scaled, y_resampled, n_trials)
            else:
                model = self._default_train(X_scaled, y_resampled)

            # Platt Scaling 概率校准
            try:
                from sklearn.calibration import CalibratedClassifierCV
                model = CalibratedClassifierCV(
                    model, method='sigmoid', cv=3
                ).fit(X_scaled, y_resampled)
                logger.info(f"  Platt Scaling 概率校准完成")
            except Exception as e:
                logger.warning(f"  概率校准失败: {e}")

            # 评估
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_resampled, test_size=0.2, random_state=self.random_state
            )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]

            f1 = f1_score(y_test, y_pred)
            acc = accuracy_score(y_test, y_pred)

            self.models[etype] = model
            self.scalers[etype] = scaler

            # 特征重要性
            if hasattr(model, 'feature_importances_'):
                self.feature_importances[etype] = model.feature_importances_

            results[etype] = {
                'model': model,
                'scaler': scaler,
                'f1': round(float(f1), 4),
                'accuracy': round(float(acc), 4),
                'n_samples': len(X_resampled),
                'n_features': X_scaled.shape[1],
            }

            self.training_history.append({
                'event_type': etype,
                'f1': results[etype]['f1'],
                'accuracy': results[etype]['accuracy'],
                'n_samples': results[etype]['n_samples'],
            })

            logger.info(f"  F1={f1:.4f}, Accuracy={acc:.4f}")

        return results

    def _optuna_train(self, X: np.ndarray, y: np.ndarray, n_trials: int = 50):
        """Optuna 贝叶斯超参优化"""
        try:
            import optuna
            from lightgbm import LGBMClassifier
            from sklearn.model_selection import cross_val_score

            def objective(trial):
                params = {
                    'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                    'max_depth': trial.suggest_int('max_depth', 3, 12),
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                    'num_leaves': trial.suggest_int('num_leaves', 15, 127),
                    'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
                    'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                    'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                    'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                    'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                    'random_state': self.random_state,
                    'verbose': -1,
                }
                model = LGBMClassifier(**params)
                scores = cross_val_score(
                    model, X, y, cv=3, scoring='f1', error_score='raise'
                )
                return scores.mean()

            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

            from lightgbm import LGBMClassifier
            best_model = LGBMClassifier(
                **study.best_params, random_state=self.random_state, verbose=-1
            )
            logger.info(f"  Optuna最佳参数: {study.best_params}")
            return best_model

        except ImportError as e:
            logger.warning(f"Optuna/LightGBM未安装: {e}, 使用默认LightGBM")
            return self._default_train(X, y)

    def _default_train(self, X: np.ndarray, y: np.ndarray):
        """默认模型训练 (LightGBM + 默认参数)"""
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier(
                n_estimators=100, max_depth=6, learning_rate=0.1,
                random_state=self.random_state, verbose=-1
            )
        except ImportError:
            from sklearn.ensemble import RandomForestClassifier
            logger.warning("LightGBM未安装, 回退到RandomForest")
            return RandomForestClassifier(
                n_estimators=100, random_state=self.random_state
            )

    def predict(self, event_type: str, features: np.ndarray) -> dict:
        """预测 (带置信度)"""
        if event_type not in self.models:
            return {'type': event_type, 'confidence': 0.0, 'error': 'model not found'}

        model = self.models[event_type]
        scaler = self.scalers[event_type]

        features_scaled = scaler.transform(features.reshape(1, -1))
        prob = model.predict_proba(features_scaled)[0, 1]
        pred = model.predict(features_scaled)[0]

        return {
            'type': event_type,
            'prediction': int(pred),
            'confidence': round(float(prob), 4),
        }

    def predict_all(self, features: np.ndarray) -> List[dict]:
        """对所有已训练事件类型预测"""
        results = []
        for etype in self.models:
            result = self.predict(etype, features)
            if result['confidence'] > 0.3:
                results.append(result)
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results

    def save(self, version: str = 'v1.0.0') -> str:
        """保存模型快照"""
        snapshot = {
            'version': version,
            'models': self.models,
            'scalers': self.scalers,
            'feature_importances': self.feature_importances,
            'training_history': self.training_history,
            'random_state': self.random_state,
        }
        path = self.model_dir / f'event_detector_{version}.pkl'
        with open(path, 'wb') as f:
            pickle.dump(snapshot, f)

        # 同时保存为 latest
        latest_path = self.model_dir / 'event_detector_latest.pkl'
        latest_path.write_bytes(path.read_bytes())

        checksum = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        logger.info(f"模型已保存: {version} (checksum={checksum})")
        return str(path)

    def load(self, version: str = 'latest') -> bool:
        """加载模型"""
        path = self.model_dir / f'event_detector_{version}.pkl'
        if not path.exists():
            logger.error(f"模型文件不存在: {path}")
            return False

        with open(path, 'rb') as f:
            snapshot = pickle.load(f)

        self.models = snapshot['models']
        self.scalers = snapshot['scalers']
        self.feature_importances = snapshot.get('feature_importances', {})
        self.training_history = snapshot.get('training_history', [])
        self.random_state = snapshot.get('random_state', 42)

        logger.info(f"模型已加载: {snapshot['version']} ({len(self.models)} 事件类型)")
        return True

    def get_summary(self) -> dict:
        """获取训练摘要"""
        return {
            'n_models': len(self.models),
            'event_types': list(self.models.keys()),
            'training_history': self.training_history,
            'avg_f1': float(np.mean([h['f1'] for h in self.training_history])) if self.training_history else 0.0,
        }


class DriftDetector:
    """概念漂移检测器"""

    def __init__(self, window_size: int = 100, threshold: float = 0.1):
        self.window_size = window_size
        self.threshold = threshold
        self.confidence_history: deque = deque(maxlen=window_size)
        self._low_conf_count: int = 0

    def update(self, confidence: float) -> dict:
        """更新置信度历史并检测漂移

        Returns:
            {'drifted': bool, 'drift_rate': float, 'low_conf_pct': float}
        """
        is_low = confidence < 0.85
        self.confidence_history.append(1.0 if is_low else 0.0)
        if is_low:
            self._low_conf_count += 1

        if len(self.confidence_history) < self.window_size:
            return {'drifted': False, 'drift_rate': 0.0, 'low_conf_pct': 0.0}

        drift_rate = float(np.mean(self.confidence_history))
        return {
            'drifted': drift_rate > self.threshold,
            'drift_rate': round(drift_rate, 4),
            'low_conf_pct': round(drift_rate * 100, 1),
        }

    def reset(self) -> None:
        self.confidence_history.clear()
        self._low_conf_count = 0

    @property
    def total_low_conf(self) -> int:
        return self._low_conf_count


class AdaptiveModelUpdater:
    """在线自适应模型更新器 — 防止模型退化

    双缓冲机制:
    1. drift_buffer: 低置信度样本缓存 (用于漂移检测)
    2. feedback_buffer: 人工标注反馈样本 (用于增量训练)

    工作流程:
    1. predict_with_adaptation() — 预测 + 漂移检测
    2. provide_feedback() — 人工标注反馈
    3. _incremental_update() — 在反馈样本上增量训练
    """

    def __init__(self, base_trainer: DrivingEventModelTrainer,
                 buffer_size: int = 1000,
                 update_threshold: float = 0.85,
                 min_feedback_samples: int = 50):
        self.base_trainer = base_trainer
        self.buffer_size = buffer_size
        self.update_threshold = update_threshold
        self.min_feedback_samples = min_feedback_samples

        # 漂移检测缓冲区
        self.drift_detector = DriftDetector(window_size=100, threshold=0.15)
        self.drift_buffer: deque = deque(maxlen=buffer_size)
        self.drift_scores: List[float] = []

        # 反馈缓冲区 (标注样本)
        self.feedback_buffer: deque = deque(maxlen=buffer_size)
        self.update_count: int = 0
        self.total_predictions: int = 0
        self.total_low_conf: int = 0

    # ── 预测 + 漂移检测 ──

    def predict_with_adaptation(self, event_type: str,
                                 features: np.ndarray) -> dict:
        """带自适应更新的预测

        Returns:
            {'type': str, 'confidence': float, 'prediction': int,
             'drift': dict, 'needs_feedback': bool}
        """
        result = self.base_trainer.predict(event_type, features)
        self.total_predictions += 1

        # 漂移检测
        drift_status = self.drift_detector.update(result['confidence'])

        # 低置信度样本缓存
        if result['confidence'] < self.update_threshold:
            self.total_low_conf += 1
            self.drift_buffer.append({
                'features': features,
                'event_type': event_type,
                'confidence': result['confidence'],
            })
            drift_score = 1.0 - result['confidence']
            self.drift_scores.append(drift_score)

        result['drift'] = drift_status
        result['needs_feedback'] = result['confidence'] < self.update_threshold
        return result

    def predict_all_with_adaptation(self, features: np.ndarray) -> List[dict]:
        """对所有已训练事件类型预测 (带自适应)"""
        results = []
        for etype in self.base_trainer.models:
            result = self.predict_with_adaptation(etype, features)
            if result['confidence'] > 0.3:
                results.append(result)
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results

    # ── 人工反馈 ──

    def provide_feedback(self, features: np.ndarray,
                         event_type: str,
                         true_label: bool,
                         source: str = 'manual') -> None:
        """提供人工标注反馈

        Args:
            features: 特征向量 [M]
            event_type: 事件类型
            true_label: True=正样本, False=负样本
            source: 反馈来源 ('manual'|'auto'|'validation')
        """
        self.feedback_buffer.append({
            'features': np.array(features).copy(),
            'event_type': event_type,
            'label': 1 if true_label else 0,
            'source': source,
        })
        logger.debug(
            f"反馈已记录: {event_type}={true_label} (source={source}, "
            f"buffer={len(self.feedback_buffer)}/{self.min_feedback_samples})"
        )

        # 自动触发增量更新
        if len(self.feedback_buffer) >= self.min_feedback_samples:
            self._incremental_update()

    def provide_batch_feedback(self, feedbacks: List[dict]) -> None:
        """批量提供反馈

        Args:
            feedbacks: [{'features': np.ndarray, 'event_type': str, 'label': bool}, ...]
        """
        for fb in feedbacks:
            self.provide_feedback(
                fb['features'], fb['event_type'], fb['label'],
                source=fb.get('source', 'batch')
            )

    # ── 增量学习 ──

    def _incremental_update(self) -> None:
        """增量学习更新 (基于反馈样本)

        使用 LightGBM 的 init_model 参数在现有模型基础上增量训练。
        仅更新叶节点权重，不重新训练整棵树。
        """
        if len(self.feedback_buffer) < self.min_feedback_samples:
            logger.debug(f"反馈样本不足: {len(self.feedback_buffer)}/{self.min_feedback_samples}")
            return

        # 按事件类型分组
        X_list = []
        y_list = []
        for item in self.feedback_buffer:
            X_list.append(item['features'])
            y_list.append(item['event_type'])

        X_batch = np.array(X_list)
        y_batch = np.array(y_list)

        updated_types = []
        for etype in set(y_batch):
            if etype not in self.base_trainer.models:
                continue

            try:
                mask = y_batch == etype
                X_etype = X_batch[mask]
                y_etype = np.array([
                    item['label'] for item in self.feedback_buffer
                    if item['event_type'] == etype
                ])

                # 需要至少5个样本 (每类至少1个)
                if len(y_etype) < 5 or y_etype.sum() < 1 or (len(y_etype) - y_etype.sum()) < 1:
                    continue

                model = self.base_trainer.models[etype]
                if hasattr(model, 'fit'):
                    # 标准化
                    if etype in self.base_trainer.scalers:
                        X_etype = self.base_trainer.scalers[etype].transform(X_etype)

                    # 获取底层LightGBM模型 (处理CalibratedClassifierCV包装)
                    base_model = model
                    if hasattr(model, 'calibrated_classifiers_'):
                        # CalibratedClassifierCV: 取第一个fold的estimator
                        base_model = model.calibrated_classifiers_[0].estimator
                    elif hasattr(model, 'base_estimator'):
                        base_model = model.base_estimator

                    if hasattr(base_model, 'booster_'):
                        base_model.fit(X_etype, y_etype, init_model=base_model)
                        # 如果是CalibratedClassifierCV, 重新校准
                        if hasattr(model, 'calibrated_classifiers_'):
                            try:
                                from sklearn.calibration import CalibratedClassifierCV
                                model = CalibratedClassifierCV(
                                    base_model, method='sigmoid', cv=3
                                ).fit(X_etype, y_etype)
                                self.base_trainer.models[etype] = model
                            except Exception:
                                pass  # 校准失败, 保留原模型
                        updated_types.append(etype)
                        logger.info(
                            f"增量更新 {etype}: {len(y_etype)}样本 "
                            f"(正={y_etype.sum()}, 负={len(y_etype) - y_etype.sum()})"
                        )
            except Exception as e:
                logger.warning(f"增量更新 {etype} 失败: {e}")

        if updated_types:
            self.update_count += 1
            logger.info(
                f"增量更新 #{self.update_count}: {len(updated_types)}事件类型 "
                f"({len(self.feedback_buffer)}样本)"
            )
        self.feedback_buffer.clear()

    def force_update(self) -> bool:
        """强制触发增量更新 (绕过最小样本数检查)"""
        if len(self.feedback_buffer) >= 5:
            saved_min = self.min_feedback_samples
            self.min_feedback_samples = 0  # 临时绕过检查
            self._incremental_update()
            self.min_feedback_samples = saved_min
            return True
        return False

    # ── 状态查询 ──

    def get_drift_status(self) -> dict:
        """获取漂移状态"""
        return {
            'drift_detected': self.drift_detector.confidence_history and
                float(np.mean(self.drift_detector.confidence_history)) > self.drift_detector.threshold,
            'avg_drift': round(float(np.mean(self.drift_scores[-50:])), 4) if self.drift_scores else 0.0,
            'max_drift': round(float(np.max(self.drift_scores[-50:])), 4) if self.drift_scores else 0.0,
            'update_count': self.update_count,
            'total_predictions': self.total_predictions,
            'low_conf_ratio': round(self.total_low_conf / max(self.total_predictions, 1), 4),
            'feedback_pending': len(self.feedback_buffer),
            'drift_buffer_size': len(self.drift_buffer),
            'drift_rate': round(float(np.mean(self.drift_detector.confidence_history)), 4)
                if self.drift_detector.confidence_history else 0.0,
        }

    def get_drift_samples(self, n: int = 10) -> List[dict]:
        """获取最近的漂移样本 (用于人工审核)"""
        items = list(self.drift_buffer)[-n:]
        return [
            {
                'event_type': item['event_type'],
                'confidence': item['confidence'],
                'drift_score': round(1.0 - item['confidence'], 4),
            }
            for item in items
        ]

    def reset(self) -> None:
        """重置所有状态"""
        self.drift_buffer.clear()
        self.feedback_buffer.clear()
        self.drift_scores.clear()
        self.drift_detector.reset()
        self.update_count = 0
        self.total_predictions = 0
        self.total_low_conf = 0