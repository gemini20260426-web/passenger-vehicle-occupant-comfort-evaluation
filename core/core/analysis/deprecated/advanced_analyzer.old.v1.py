"""高级驾驶行为分析（基于随机森林模型的二次分析）"""
import os
import sys
import pickle
import logging
import pandas as pd
import numpy as np
from pathlib import Path

# 确保Python路径正确设置
current_file = Path(__file__)
project_root = current_file.parent.parent.parent.parent
core_dir = project_root / "core"

# 添加必要的路径到sys.path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

# 尝试导入sklearn，如果失败则提供友好的错误信息
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.svm import SVC
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score, KFold
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    SKLEARN_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] sklearn import failed: {e}")
    print("Please install scikit-learn: pip install scikit-learn")
    print("Advanced analysis features will be unavailable")
    SKLEARN_AVAILABLE = False
    
    # 创建占位符类以避免导入错误
    class RandomForestClassifier:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用RandomForestClassifier")
    
    class GradientBoostingClassifier:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用GradientBoostingClassifier")
    
    class SVC:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用SVC")
    
    class KNeighborsClassifier:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用KNeighborsClassifier")
    
    class LogisticRegression:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用LogisticRegression")
    
    class StandardScaler:
        def __init__(self, *args, **kwargs):
            raise ImportError("sklearn未安装，无法使用StandardScaler")
    
    # 占位符函数
    def train_test_split(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用train_test_split")
    
    def GridSearchCV(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用GridSearchCV")
    
    def cross_val_score(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用cross_val_score")
    
    def KFold(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用KFold")
    
    def accuracy_score(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用accuracy_score")
    
    def classification_report(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用classification_report")
    
    def confusion_matrix(*args, **kwargs):
        raise ImportError("sklearn未安装，无法使用confusion_matrix")

from typing import Dict, List, Any, Optional, Tuple
from PySide6.QtCore import QObject, Signal, QThread, Slot
import time


def _safe_float(val, default=0.0):
    if val is None:
        return default
    return float(val)


class ModelTrainingThread(QThread):
    """模型训练线程，避免阻塞UI"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    training_complete = Signal(float, dict)
    error_occurred = Signal(str)
    
    def __init__(self, base_results: List[Dict[str, Any]], labels: List[str], 
                 model_path: str, scaler_path: str, use_cross_validation: bool = False,
                 compare_algorithms: bool = False):
        super().__init__()
        self.base_results = base_results
        self.labels = labels
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.use_cross_validation = use_cross_validation  # 是否使用交叉验证
        self.compare_algorithms = compare_algorithms      # 是否比较多种算法
        self.feature_columns = [
            "speed", "ax", "ay", "az", "gx", "gy", "gz",
            "accel_magnitude", "turn_rate", "speed_change_rate",
            "behavior_confidence"
        ]
        self.running = True

    def stop(self) -> None:
        """停止训练"""
        self.running = False

    def _preprocess_features(self, base_results: List[Dict[str, Any]]) -> pd.DataFrame:
        """预处理特征"""
        features = []
        for i, res in enumerate(base_results):
            if not self.running:
                return None
                
            raw = res["raw_data"]
            ax_val = _safe_float(raw.get("ax"))
            ay_val = _safe_float(raw.get("ay"))
            az_val = _safe_float(raw.get("az"))
            gx_val = _safe_float(raw.get("gx"))
            gy_val = _safe_float(raw.get("gy"))
            gz_val = _safe_float(raw.get("gz"))
            speed_val = _safe_float(raw.get("speed"))

            accel_mag = np.linalg.norm([ax_val, ay_val, az_val])
            turn_rate = np.linalg.norm([gx_val, gy_val, gz_val])
            
            # 计算速度变化率
            speed_change_rate = 0
            if i > 0 and "timestamp" in res and "timestamp" in base_results[i-1]:
                try:
                    # 处理不同的时间戳格式
                    if isinstance(res["timestamp"], str):
                        curr_time = pd.to_datetime(res["timestamp"]).timestamp()
                    else:
                        curr_time = float(res["timestamp"])
                        
                    if isinstance(base_results[i-1]["timestamp"], str):
                        prev_time = pd.to_datetime(base_results[i-1]["timestamp"]).timestamp()
                    else:
                        prev_time = float(base_results[i-1]["timestamp"])
                        
                    time_diff = curr_time - prev_time
                    if time_diff > 0:
                        prev_speed = _safe_float(base_results[i-1]["raw_data"].get("speed"))
                        speed_change_rate = (speed_val - prev_speed) / time_diff
                except Exception:
                    pass
            
            features.append({
                "speed": speed_val,
                "ax": ax_val,
                "ay": ay_val,
                "az": az_val,
                "gx": gx_val,
                "gy": gy_val,
                "gz": gz_val,
                "accel_magnitude": accel_mag,
                "turn_rate": turn_rate,
                "speed_change_rate": speed_change_rate,
                "behavior_confidence": _safe_float(res.get("confidence"))
            })
            
            # 更新进度
            if i % 10 == 0:
                self.progress_updated.emit(int((i / len(base_results)) * 30))  # 预处理占30%进度
                
        return pd.DataFrame(features)

    def _perform_cross_validation(self, model, X, y, cv_folds=5):
        """执行K折交叉验证"""
        self.status_updated.emit(f"正在进行{cv_folds}折交叉验证...")
        try:
            # 执行交叉验证
            cv_scores = cross_val_score(model, X, y, cv=cv_folds, scoring='accuracy')
            
            # 发送进度更新
            self.progress_updated.emit(90)
            self.status_updated.emit(f"交叉验证完成，平均准确率: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
            
            return cv_scores
        except Exception as e:
            self.error_occurred.emit(f"交叉验证过程中出错: {str(e)}")
            return None

    def _compare_algorithms(self, X, y):
        self.status_updated.emit("正在比较多种算法（交叉验证）...")
        algorithms = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42),
            'SVM': SVC(random_state=42),
            'KNN': KNeighborsClassifier(),
            'LogisticRegression': LogisticRegression(random_state=42, max_iter=1000)
        }
        results = {}
        best_algorithm = None
        best_score = 0
        for name, model in algorithms.items():
            if not self.running:
                return
            self.status_updated.emit(f"正在评估 {name}...")
            cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
            score = cv_scores.mean()
            results[name] = score
            if score > best_score:
                best_score = score
                best_algorithm = name
        self.status_updated.emit(f"最佳算法: {best_algorithm} ({best_score:.4f})")

    def _compare_algorithms_with_train_test(self, X_train_scaled, y_train, X_test_scaled, y_test):
        """比较多种算法的性能（使用训练集和测试集）"""
        self.status_updated.emit("正在比较多种算法...")
        
        # 定义要比较的算法
        algorithms = {
            'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingClassifier(n_estimators=100, random_state=42),
            'SVM': SVC(random_state=42),
            'KNN': KNeighborsClassifier(),
            'LogisticRegression': LogisticRegression(random_state=42, max_iter=1000)
        }
        
        results = {}
        best_algorithm = None
        best_score = 0
        
        for name, model in algorithms.items():
            if not self.running:
                return None, None
                
            self.status_updated.emit(f"正在训练 {name}...")
            model.fit(X_train_scaled, y_train)
            score = model.score(X_test_scaled, y_test)
            results[name] = score
            
            if score > best_score:
                best_score = score
                best_algorithm = name
                
            self.progress_updated.emit(int(40 + 30 * len(results) / len(algorithms)))
            
        return results, best_algorithm

    def run(self):
        """运行模型训练"""
        try:
            self.status_updated.emit("开始预处理数据...")
            # 预处理特征
            df = self._preprocess_features(self.base_results)
            if df is None or not self.running:
                return
            
            if len(df) == 0:
                self.error_occurred.emit("没有有效的训练数据")
                return
            
            # 提取特征和标签
            X = df[self.feature_columns]
            y = self.labels[:len(X)]  # 确保标签数量匹配
            
            if len(X) != len(y):
                self.error_occurred.emit("特征和标签数量不匹配")
                return
            
            # 检查是否只有一个类别
            unique_labels = np.unique(y)
            if len(unique_labels) < 2:
                self.error_occurred.emit(f"需要至少2个类别进行训练，当前只有 {len(unique_labels)} 个类别: {unique_labels}")
                return
            
            self.progress_updated.emit(40)
            self.status_updated.emit("数据预处理完成，开始训练模型...")
            
            # 数据标准化
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # 保存scaler
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            self.progress_updated.emit(50)
            
            # 比较多种算法（如果需要）
            if self.compare_algorithms and self.running:
                # 如果使用交叉验证，则使用基于交叉验证的比较方法
                if self.use_cross_validation:
                    self._compare_algorithms(X_scaled, y)
                else:
                    # 否则使用基于训练集/测试集的比较方法
                    X_train_scaled, X_test_scaled, y_train, y_test = train_test_split(
                        X_scaled, y, test_size=0.2, random_state=42
                    )
                    self._compare_algorithms_with_train_test(X_train_scaled, y_train, X_test_scaled, y_test)
            
            # 创建随机森林模型
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
            
            # 执行交叉验证（如果需要）
            if self.use_cross_validation and self.running:
                cv_scores = self._perform_cross_validation(self.model, X_scaled, y, 5)
                if cv_scores is None:
                    return  # 交叉验证出错
            
            if not self.running:
                return
            
            self.progress_updated.emit(70)
            self.status_updated.emit("正在训练最终模型...")
            
            # 训练最终模型
            self.model.fit(X_scaled, y)
            
            if not self.running:
                return
            
            # 保存模型
            self.status_updated.emit("正在保存模型...")
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            # 评估模型
            self.progress_updated.emit(95)
            self.status_updated.emit("正在评估模型...")
            
            y_pred = self.model.predict(X_scaled)
            accuracy = accuracy_score(y, y_pred)
            report = classification_report(y, y_pred)
            
            if self.running:
                self.progress_updated.emit(100)
                self.training_complete.emit(accuracy, report)
        except Exception as e:
            if self.running:
                self.error_occurred.emit(f"训练过程中出错: {str(e)}")
                logging.error(f"模型训练出错: {e}", exc_info=True)


class AdvancedBehaviorAnalyzer(QObject):
    """高级驾驶行为分析器"""
    
    # 定义信号
    analysis_complete = Signal(dict)  # 分析完成信号
    training_progress = Signal(int)   # 训练进度信号
    training_status = Signal(str)     # 训练状态信号
    model_trained = Signal(float, dict)  # 模型训练完成信号
    analysis_progress = Signal(int)   # 分析进度信号
    
    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.model = None
        self.scaler = None
        self.feature_columns = [
            "speed", "ax", "ay", "az", "gx", "gy", "gz",
            "accel_magnitude", "turn_rate", "speed_change_rate",
            "behavior_confidence"
        ]
        self.is_trained = False
        self.logger = logging.getLogger(__name__)
        
        # 训练相关属性
        self.training_thread = None
        self.model_path = "trained_model.pkl"
        self.scaler_path = "feature_scaler.pkl"
        self.use_cross_validation = False
        self.compare_algorithms = False
        
        # 加载已保存的模型（如果存在）
        self._load_saved_model()
    
    def _load_saved_model(self):
        """加载已保存的模型"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                self.logger.info("已加载预训练模型")
                
            if os.path.exists(self.scaler_path):
                with open(self.scaler_path, "rb") as f:
                    self.scaler = pickle.load(f)
                self.logger.info("已加载特征缩放器")
        except Exception as e:
            self.logger.error(f"加载预训练模型失败: {e}")
    
    def _load_model(self):
        """加载模型"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")
        return None
    
    def _load_scaler(self):
        """加载特征缩放器"""
        try:
            if os.path.exists(self.scaler_path):
                with open(self.scaler_path, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            self.logger.error(f"加载特征缩放器失败: {e}")
        return None

    def set_model(self, model):
        """设置模型"""
        self.model = model
        self.is_trained = True
        self.logger.info("模型已设置")

    def _extract_features(self, base_result: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        从基础分析器的结果中提取特征（11维标准特征集）

        Args:
            base_result: 基础分析器(base_analyzer.py)的输出结果

        Returns:
            特征向量或None（如果无法提取）
        """
        try:
            raw_data = base_result.get("raw_data", {})
            if not raw_data:
                return None

            ax_val = _safe_float(raw_data.get("ax"))
            ay_val = _safe_float(raw_data.get("ay"))
            az_val = _safe_float(raw_data.get("az"))
            gx_val = _safe_float(raw_data.get("gx"))
            gy_val = _safe_float(raw_data.get("gy"))
            gz_val = _safe_float(raw_data.get("gz"))
            speed_val = _safe_float(raw_data.get("speed"))

            accel_mag = np.linalg.norm([ax_val, ay_val, az_val])
            turn_rate = np.linalg.norm([gx_val, gy_val, gz_val])

            features = [
                speed_val,
                ax_val,
                ay_val,
                az_val,
                gx_val,
                gy_val,
                gz_val,
                float(accel_mag),
                float(turn_rate),
                0.0,
                _safe_float(base_result.get("confidence"), 0.85),
            ]

            return np.array(features).reshape(1, -1)

        except Exception as e:
            logging.error(f"特征提取失败: {e}")
            return None

    def preprocess_single_sample(self, base_result: Dict[str, Any], 
                                prev_result: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """预处理单个样本特征"""
        # 兼容base_analyzer_new.py的输出格式
        raw = base_result.get("raw_data", {})
        
        ax_val = _safe_float(raw.get("ax"))
        ay_val = _safe_float(raw.get("ay"))
        az_val = _safe_float(raw.get("az"))
        gx_val = _safe_float(raw.get("gx"))
        gy_val = _safe_float(raw.get("gy"))
        gz_val = _safe_float(raw.get("gz"))
        speed_val = _safe_float(raw.get("speed"))

        accel_mag = np.linalg.norm([ax_val, ay_val, az_val])
        turn_rate = np.linalg.norm([gx_val, gy_val, gz_val])
        
        # 计算速度变化率
        speed_change_rate = 0
        if prev_result:
            try:
                # 处理不同的时间戳格式
                if isinstance(base_result["timestamp"], str):
                    curr_time = pd.to_datetime(base_result["timestamp"]).timestamp()
                else:
                    curr_time = float(base_result["timestamp"])
                    
                if isinstance(prev_result["timestamp"], str):
                    prev_time = pd.to_datetime(prev_result["timestamp"]).timestamp()
                else:
                    prev_time = float(prev_result["timestamp"])
                    
                time_diff = curr_time - prev_time
                if time_diff > 0:
                    prev_speed = _safe_float(prev_result["raw_data"].get("speed"))
                    speed_change_rate = (speed_val - prev_speed) / time_diff
            except Exception:
                pass
        
        # 创建特征数据框
        features = pd.DataFrame([{
            "speed": speed_val,
            "ax": ax_val,
            "ay": ay_val,
            "az": az_val,
            "gx": gx_val,
            "gy": gy_val,
            "gz": gz_val,
            "accel_magnitude": accel_mag,
            "turn_rate": turn_rate,
            "speed_change_rate": speed_change_rate,
            "behavior_confidence": _safe_float(base_result.get("confidence"))
        }])
        
        return features

    def train_model(self, base_results: List[Dict[str, Any]], labels: List[str]) -> None:
        """开始训练模型（在后台线程中执行）"""
        # 如果已有训练线程在运行，先停止
        if self.training_thread and self.training_thread.isRunning():
            self.training_thread.stop()
            self.training_thread.wait()
            
        # 创建并启动新的训练线程
        self.training_thread = ModelTrainingThread(
            base_results, labels, self.model_path, self.scaler_path,
            self.use_cross_validation, self.compare_algorithms
        )
        
        # 连接信号
        self.training_thread.progress_updated.connect(self.training_progress.emit)
        self.training_thread.status_updated.connect(self.training_status.emit)
        self.training_thread.training_complete.connect(self._on_training_complete)
        self.training_thread.error_occurred.connect(self.training_status.emit)
        
        self.training_thread.start()

    @Slot(float, dict)
    def _on_training_complete(self, accuracy: float, metrics: dict) -> None:
        """训练完成回调"""
        # 重新加载模型和标准化器
        self.model = self._load_model()
        self.scaler = self._load_scaler()
        self.model_trained.emit(accuracy, metrics)

    def cancel_training(self) -> None:
        """取消模型训练"""
        if self.training_thread and self.training_thread.isRunning():
            self.training_thread.stop()
            self.training_status.emit("训练已取消")

    def analyze(self, base_result: Dict[str, Any], 
               prev_result: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """基于基础分析结果进行二次分析"""
        if not self.model or not self.scaler:
            result = {"error": "模型未加载，请先训练"}
            self.analysis_complete.emit(result)
            return result

        try:
            # 预处理单条数据
            features = self.preprocess_single_sample(base_result, prev_result)
            features_scaled = self.scaler.transform(features)
            
            # 模型预测
            pred = self.model.predict(features_scaled)[0]
            proba = self.model.predict_proba(features_scaled)[0]
            max_proba = np.max(proba)
            
            # 获取类别名称
            classes = self.model.classes_
            probabilities = dict(zip(classes, proba.round(4).tolist()))
            
            # 结合基础分析结果生成最终结论
            result = {
                "timestamp": base_result["timestamp"],
                "base_behavior": base_result["behavior"],
                "advanced_behavior": pred,
                "confidence": float(0.7 * max_proba + 0.3 * base_result["confidence"]),
                "probabilities": probabilities,
                "comparison": "一致" if pred == base_result["behavior"] else "不一致"
            }
            
            self.analysis_complete.emit(result)
            return result
            
        except Exception as e:
            error = f"高级分析失败: {str(e)}"
            self.logger.error(error)
            self.analysis_complete.emit({"error": error})
            return {"error": error}

    def batch_analyze(self, base_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量分析基础结果"""
        results = []
        total = len(base_results)
        
        for i, result in enumerate(base_results):
            prev_result = base_results[i-1] if i > 0 else None
            analysis = self.analyze(result, prev_result)
            results.append(analysis)
            
            # 更新进度
            if i % 10 == 0:
                progress = int((i / total) * 100)
                self.analysis_progress.emit(progress)
                
        self.analysis_progress.emit(100)
        return results

    def get_model_info(self) -> Dict[str, Any]:
        if not self.model:
            return {
                "status": "未加载模型",
                "type": "--",
                "feature_dim": 0,
                "num_classes": 0,
                "feature_importance": {},
                "classes": []
            }

        model_type = type(self.model).__name__

        info = {
            "status": "已加载模型",
            "type": model_type,
            "feature_dim": getattr(self.model, 'n_features_in_', 0),
            "num_classes": len(self.model.classes_) if hasattr(self.model, 'classes_') else 0,
            "classes": self.model.classes_.tolist() if hasattr(self.model, 'classes_') else [],
            "feature_importance": {}
        }

        if model_type == "RandomForestClassifier":
            info["n_estimators"] = self.model.n_estimators
            info["max_depth"] = self.model.max_depth
        elif model_type == "GradientBoostingClassifier":
            info["n_estimators"] = self.model.n_estimators
            info["learning_rate"] = self.model.learning_rate
        elif model_type == "SVC":
            info["C"] = self.model.C
            info["kernel"] = self.model.kernel
        elif model_type == "KNeighborsClassifier":
            info["n_neighbors"] = self.model.n_neighbors
        elif model_type == "LogisticRegression":
            info["C"] = self.model.C
            info["max_iter"] = self.model.max_iter

        if hasattr(self.model, 'feature_importances_'):
            importance = dict(zip(self.feature_columns, self.model.feature_importances_))
            info["feature_importance"] = dict(
                sorted(importance.items(), key=lambda x: -x[1])
            )

        return info

    def train_on_bridge(self, base_results, labels, algorithm="RandomForest",
                        use_cv=False, compare=False):
        self.use_cross_validation = use_cv
        self.compare_algorithms = compare

        if self.training_thread and self.training_thread.isRunning():
            self.training_thread.stop()
            self.training_thread.wait()

        self.training_thread = ModelTrainingThread(
            base_results, labels, self.model_path, self.scaler_path,
            self.use_cross_validation, self.compare_algorithms
        )
        self.training_thread.progress_updated.connect(self.training_progress.emit)
        self.training_thread.status_updated.connect(self.training_status.emit)
        self.training_thread.training_complete.connect(self._on_training_complete)
        self.training_thread.error_occurred.connect(self.training_status.emit)
        self.training_thread.start()

    def set_cross_validation(self, use_cv: bool):
        """设置是否使用交叉验证"""
        self.use_cross_validation = use_cv

    def set_algorithm_comparison(self, compare: bool):
        """设置是否比较多种算法"""
        self.compare_algorithms = compare

    def predict_behavior(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        预测驾驶行为
        
        Args:
            features: 包含特征数据的字典
            
        Returns:
            包含行为预测结果的字典
        """
        try:
            if not hasattr(self, 'model') or self.model is None:
                return {
                    'predicted_behavior': 'unknown',
                    'confidence': 0.0,
                    'status': 'model_not_trained',
                    'message': '模型尚未训练'
                }
            
            # 准备特征数据
            feature_vector = []
            for feature_name in self.feature_columns:
                if feature_name in features:
                    feature_vector.append(float(features[feature_name]))
                else:
                    feature_vector.append(0.0)
            
            # 转换为numpy数组
            X = np.array([feature_vector])
            
            # 标准化特征
            if hasattr(self, 'scaler') and self.scaler is not None:
                X = self.scaler.transform(X)
            
            # 进行预测
            prediction = self.model.predict(X)[0]
            prediction_proba = self.model.predict_proba(X)[0]
            
            # 获取预测概率
            max_prob = np.max(prediction_proba)
            
            # 构建预测结果
            result = {
                'predicted_behavior': str(prediction),
                'confidence': float(max_prob),
                'all_probabilities': prediction_proba.tolist(),
                'feature_vector': feature_vector,
                'timestamp': time.time(),
                'status': 'predicted',
                'model_type': self.model.__class__.__name__
            }
            
            return result
            
        except Exception as e:
            logging.error(f"行为预测失败: {e}")
            return {
                'predicted_behavior': 'unknown',
                'confidence': 0.0,
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }