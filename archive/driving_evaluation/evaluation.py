from typing import Any
from driving_behavior_evaluation.analysis import DrivingThresholds
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import tkinter as tk
from tkinter import ttk
from collections import deque
import time
from datetime import datetime
import os
import json


class DrivingBehaviorEvaluator:
    """驾驶行为评估模块，计算驾驶评分和生成综合报告"""

    def __init__(self, config=None):
        # 评估配置参数
        # Initialize driving behavior thresholds
        self.thresholds = DrivingThresholds()
        
        self.config = config or {
            # 评分权重
            "weights": {
                "speed": 0.3,  # 速度控制权重
                "acceleration": 0.25,  # 加减速控制权重
                "turning": 0.25,  # 转向控制权重
                "compliance": 0.2,  # 规则遵守权重
            },
            # KNN模型参数
            "knn": {"n_neighbors": 5, "metric": "euclidean"},  # 默认K值  # 距离度量
            # 评分等级
            "grades": {"excellent": 90, "good": 80, "average": 60, "poor": 40},
        }

        # 评估结果存储
        self.trip_evaluation = {}

        # 初始化KNN模型和标准化器
        self.knn_model = KNeighborsClassifier(
            n_neighbors=self.config["knn"]["n_neighbors"],
            metric=self.config["knn"]["metric"],
        )
        self.scaler = StandardScaler()
        self.is_model_trained = False
        self.X_train = None
        self.y_train = None

    def _extract_knn_features(self, trip_data, behavior_events):
        """提取用于KNN模型的驾驶行为特征

        Args:
            trip_data: 行程数据点列表
            behavior_events: 行为事件列表

        Returns:
            特征向量
        """
        if not trip_data:
            return []

        # 速度特征
        speeds = [data.get("speed", 0) for data in trip_data]
        speed_mean = np.mean(speeds)
        speed_std = np.std(speeds)
        speed_max = np.max(speeds)

        # 加速度特征
        accelerations = [data.get("acceleration", 0) for data in trip_data]
        accel_std = np.std(accelerations)

        # 横向加速度特征
        lateral_accels = [data.get("lateral_acceleration", 0) for data in trip_data]
        lateral_std = np.std(lateral_accels)

        # 事件统计特征
        event_stats = self._count_behavior_events(behavior_events)
        harsh_accel_count = event_stats.get("harsh_acceleration", 0)
        harsh_brake_count = event_stats.get("harsh_brake", 0)
        harsh_turn_count = event_stats.get("harsh_turn", 0)
        total_events = sum(event_stats.values())

        # 行程时长特征
        duration = self._calculate_duration(trip_data)

        # 组合特征向量
        return [
            speed_mean,
            speed_std,
            speed_max,
            accel_std,
            lateral_std,
            harsh_accel_count,
            harsh_brake_count,
            harsh_turn_count,
            total_events,
            duration,
        ]

    def evaluate_trip(self, trip_data, behavior_events, trip_info=None):
        """评估整个行程的驾驶行为

        Args:
            trip_data: 行程数据点列表
            behavior_events: 异常行为事件列表
            trip_info: 行程基本信息

        Returns:
            包含评分和分析结果的字典
        """
        if not trip_data:
            return {"error": "No trip data provided"}

        # 初始化评估结果
        evaluation = {
            "trip_id": trip_info.get("id") if trip_info else None,
            "start_time": (
                trip_info.get("start_time")
                if trip_info
                else trip_data[0].get("timestamp")
            ),
            "end_time": (
                trip_info.get("end_time")
                if trip_info
                else trip_data[-1].get("timestamp")
            ),
            "duration": self._calculate_duration(trip_data),
            "distance": trip_info.get("distance") if trip_info else 0,
            "max_speed": trip_info.get("max_speed") if trip_info else 0,
            "avg_speed": trip_info.get("avg_speed") if trip_info else 0,
            "scores": {},
            "overall_score": 0,
            "behavior_analysis": {},
            "recommendations": [],
            "anomaly_detection": {},
        }

        # 计算各项评分
        evaluation["scores"]["speed"] = self._evaluate_speed(trip_data)
        evaluation["scores"]["acceleration"] = self._evaluate_acceleration(
            trip_data, behavior_events
        )
        evaluation["scores"]["turning"] = self._evaluate_turning(
            trip_data, behavior_events
        )
        evaluation["scores"]["compliance"] = self._evaluate_compliance(
            trip_data, behavior_events
        )

        # 计算综合评分
        evaluation["overall_score"] = self._calculate_overall_score(
            evaluation["scores"]
        )

        # 分析行为事件
        evaluation["behavior_analysis"] = self._analyze_behavior_events(behavior_events)

        # 生成建议
        evaluation["recommendations"] = self._generate_recommendations(evaluation)

        # KNN异常检测
        try:
            # 提取特征
            trip_features = self._extract_knn_features(trip_data, behavior_events)

            if self.is_model_trained and trip_features:
                anomaly_prediction, confidence = self.predict_behavior_anomaly(
                    trip_features
                )
                evaluation["anomaly_detection"] = {
                    "prediction": "异常" if anomaly_prediction == 1 else "正常",
                    "confidence": round(confidence, 4),
                    "is_anomaly": bool(anomaly_prediction),
                }
            else:
                evaluation["anomaly_detection"] = {
                    "prediction": "模型未训练或特征不足",
                    "confidence": 0.0,
                    "is_anomaly": False,
                }
        except Exception as e:
            evaluation["anomaly_detection"] = {
                "prediction": f"检测错误: {str(e)}",
                "confidence": 0.0,
                "is_anomaly": False,
            }

        # 保存评估结果
        self.trip_evaluation[evaluation["trip_id"]] = evaluation

        return evaluation

    def _calculate_duration(self, trip_data):
        """计算行程持续时间"""
        if not trip_data or len(trip_data) < 2:
            return 0

        start_time = self._parse_timestamp(trip_data[0].get("timestamp"))
        end_time = self._parse_timestamp(trip_data[-1].get("timestamp"))

        return (end_time - start_time).total_seconds()

    def _parse_timestamp(self, timestamp):
        """解析时间戳为datetime对象"""
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return datetime.now()

    def _evaluate_speed(self, trip_data):
        """评估速度控制"""
        if not trip_data:
            return 0

        speeds = [data.get("speed", 0) for data in trip_data]
        avg_speed = np.mean(speeds)
        max_speed = np.max(speeds)

        # 假设限速为平均速度的1.2倍（简化处理）
        speed_limit = avg_speed * 1.2

        # 计算超速次数和程度
        speeding_count = sum(1 for s in speeds if s > speed_limit)
        speeding_percentage = speeding_count / len(speeds) * 100

        # 计算速度稳定性（标准差越小越稳定）
        speed_stability = np.std(speeds)

        # 评分计算 (超速影响较大，稳定性影响较小)
        score = 100 - (speeding_percentage * 2) - (speed_stability * 0.5)

        # 确保分数在0-100之间
        return max(0, min(100, score))

    def _evaluate_acceleration(self, trip_data, behavior_events):
        """评估加减速控制"""
        if not trip_data:
            return 0

        accelerations = [data.get("acceleration", 0) for data in trip_data]

        # 计算急加速次数
        harsh_accel_count = sum(
            1
            for a in accelerations
            if a > self.thresholds.accel_positive
        )

        # 计算急刹车次数
        harsh_brake_count = sum(
            1
            for a in accelerations
            if a < self.thresholds.emergency_brake_accel
        )

        # 从行为事件中获取急加速和急刹车次数
        event_stats = self._count_behavior_events(behavior_events)
        harsh_accel_count = max(
            harsh_accel_count, event_stats.get("harsh_acceleration", 0)
        )
        harsh_brake_count = max(harsh_brake_count, event_stats.get("harsh_brake", 0))

        # 计算加速度稳定性
        accel_stability = np.std(accelerations)

        # 计算急加速/急刹车频率（每公里次数）
        accel_freq = (harsh_accel_count + harsh_brake_count) / max(
            1, len(trip_data) / 1000
        )

        # 评分计算
        score = 100 - (accel_freq * 10) - (accel_stability * 2)

        return max(0, min(100, score))

    def _evaluate_turning(self, trip_data, behavior_events):
        """评估转向控制"""
        if not trip_data:
            return 0

        lateral_accels = [data.get("lateral_acceleration", 0) for data in trip_data]

        # 计算急转弯次数
        harsh_turn_count = sum(
            1
            for la in lateral_accels
            if abs(la) > self.thresholds.steering_turn_threshold
        )

        # 从行为事件中获取急转弯次数
        event_stats = self._count_behavior_events(behavior_events)
        harsh_turn_count = max(harsh_turn_count, event_stats.get("harsh_turn", 0))

        # 计算转向稳定性
        turn_stability = np.std(lateral_accels)

        # 计算急转弯频率
        turn_freq = harsh_turn_count / max(1, len(trip_data) / 1000)

        # 评分计算
        score = 100 - (turn_freq * 15) - (turn_stability * 3)

        return max(0, min(100, score))

    def _evaluate_compliance(self, trip_data, behavior_events):
        """评估规则遵守情况"""
        if not trip_data:
            return 0

        # 计算怠速时间比例
        idle_count = sum(1 for data in trip_data if data.get("speed", 0) < 1)
        idle_percentage = idle_count / len(trip_data) * 100

        # 从行为事件中获取违规事件
        event_stats = self._count_behavior_events(behavior_events)

        # 评分计算 (怠速时间和违规事件各占一半权重)
        score = 100 - (idle_percentage * 0.5) - (sum(event_stats.values()) * 5)

        return max(0, min(100, score))

    def _count_behavior_events(self, behavior_events):
        """统计行为事件"""
        stats = defaultdict(int)
        if not behavior_events:
            return stats

        for event in behavior_events:
            behaviors = event.get("behaviors", [])
            for behavior in behaviors:
                stats[behavior] += 1

        return stats

    def _calculate_overall_score(self, scores):
        """计算综合评分"""
        weights = self.config["weights"]
        overall_score = sum(
            scores.get(category, 0) * weights.get(category, 0) for category in weights
        )
        return round(overall_score, 1)

    def _analyze_behavior_events(self, behavior_events):
        """分析行为事件"""
        analysis = {
            "total_events": len(behavior_events),
            "event_types": defaultdict(int),
            "event_distribution": defaultdict(int),
            "peak_times": [],
        }

        if not behavior_events:
            return analysis

        # 统计事件类型
        for event in behavior_events:
            behaviors = event.get("behaviors", [])
            for behavior in behaviors:
                analysis["event_types"][behavior] += 1

        # 分析事件分布（按小时）
        for event in behavior_events:
            timestamp = self._parse_timestamp(event.get("timestamp"))
            hour = timestamp.hour
            analysis["event_distribution"][hour] += 1

        # 找出事件高发时段
        if analysis["event_distribution"]:
            peak_hour = max(
                analysis["event_distribution"], key=analysis["event_distribution"].get
            )
            analysis["peak_times"] = [f"{peak_hour}:00-{peak_hour+1}:00"]

        return analysis

    def _generate_recommendations(self, evaluation):
        """生成驾驶建议"""
        recommendations = []
        scores = evaluation["scores"]

        # 根据各项得分生成建议
        if scores["speed"] < 80:
            recommendations.append(
                "您的速度控制有待提高，建议保持稳定车速，避免频繁超速。"
            )

        if scores["acceleration"] < 80:
            recommendations.append(
                "您的加减速操作不够平稳，建议减少急加速和急刹车，保持平缓的加减速。"
            )

        if scores["turning"] < 80:
            recommendations.append(
                "您的转向操作需要改进，建议在转弯前提前减速，避免急转弯。"
            )

        if scores["compliance"] < 80:
            recommendations.append(
                "您的驾驶习惯需要改善，建议减少怠速时间，遵守交通规则。"
            )

        # 根据综合评分添加总体建议
        overall_score = evaluation["overall_score"]
        if overall_score < 60:
            recommendations.append(
                "您的整体驾驶行为存在较多需要改进的地方，建议参加驾驶培训课程，提高驾驶技能。"
            )
        elif overall_score < 80:
            recommendations.append(
                "您的驾驶行为基本良好，但仍有提升空间。请注意驾驶细节，养成良好的驾驶习惯。"
            )
        else:
            recommendations.append("您的驾驶行为优秀，请继续保持！")

        return recommendations

    def get_evaluation_report(self, trip_id):
        """获取行程评估报告"""
        evaluation = self.trip_evaluation.get(trip_id)
        if not evaluation:
            return {"error": f"Evaluation for trip {trip_id} not found"}

        # 生成格式化的报告
        report = {
            "trip_summary": {
                "trip_id": evaluation["trip_id"],
                "start_time": str(evaluation["start_time"]),
                "end_time": str(evaluation["end_time"]),
                "duration": f"{evaluation['duration']/3600:.2f}小时",
                "distance": f"{evaluation['distance']:.2f}公里",
                "max_speed": f"{evaluation['max_speed']:.2f}公里/小时",
                "avg_speed": f"{evaluation['avg_speed']:.2f}公里/小时",
            },
            "scores": {
                "overall": evaluation["overall_score"],
                "breakdown": evaluation["scores"],
            },
            "grade": self._get_grade(evaluation["overall_score"]),
            "behavior_analysis": evaluation["behavior_analysis"],
            "recommendations": evaluation["recommendations"],
        }

        return report

    def _get_grade(self, score):
        """根据分数获取等级"""
        grades = self.config["grades"]
        if score >= grades["excellent"]:
            return "优秀"
        elif score >= grades["good"]:
            return "良好"
        elif score >= grades["average"]:
            return "一般"
        elif score >= grades["poor"]:
            return "较差"
        else:
            return "差"

    def train_knn_model(self, X_train, y_train):
        """训练KNN模型（覆盖现有训练数据）

        Args:
            X_train: 训练特征数据 (n_samples, n_features)
            y_train: 训练标签数据 (n_samples,)

        Returns:
            是否训练成功
        """
        if X_train is None or y_train is None or len(X_train) == 0:
            raise ValueError("训练数据不能为空")

        # 特征标准化
        self.X_train = self.scaler.fit_transform(X_train)
        self.y_train = y_train

        # 训练模型
        self.knn_model.fit(self.X_train, self.y_train)
        self.is_model_trained = True

        return True

    def update_knn_model(self, X_new, y_new):
        """增量更新KNN模型（追加新训练数据）

        Args:
            X_new: 新的训练特征数据 (n_samples, n_features)
            y_new: 新的训练标签数据 (n_samples,)

        Returns:
            是否更新成功
        """
        if X_new is None or y_new is None or len(X_new) == 0:
            raise ValueError("新训练数据不能为空")

        # 如果已有训练数据，则合并
        if self.X_train is not None and self.y_train is not None:
            # 标准化新数据
            X_new_scaled = self.scaler.transform(X_new)
            # 合并数据
            self.X_train = np.vstack((self.X_train, X_new_scaled))
            self.y_train = np.hstack((self.y_train, y_new))
        else:
            # 首次训练（委托给train_knn_model）
            return self.train_knn_model(X_new, y_new)

        # 重新训练模型
        self.knn_model.fit(self.X_train, self.y_train)
        return True

    def find_optimal_k(self, X_train, y_train, k_range=range(1, 21)):
        """通过交叉验证寻找最优K值

        Args:
            X_train: 训练特征数据
            y_train: 训练标签数据
            k_range: K值范围

        Returns:
            最优K值及对应的交叉验证分数
        """
        if X_train is None or y_train is None or len(X_train) == 0:
            raise ValueError("训练数据不能为空")

        # 特征标准化
        X_scaled = self.scaler.fit_transform(X_train)

        # 交叉验证寻找最优K值
        best_score = -1
        best_k = self.config["knn"]["n_neighbors"]

        for k in k_range:
            knn = KNeighborsClassifier(
                n_neighbors=k, metric=self.config["knn"]["metric"]
            )
            scores = cross_val_score(knn, X_scaled, y_train, cv=5, scoring="accuracy")
            mean_score = np.mean(scores)

            if mean_score > best_score:
                best_score = mean_score
                best_k = k

        # 更新模型参数
        self.config["knn"]["n_neighbors"] = best_k
        self.knn_model.set_params(n_neighbors=best_k)

        return best_k, best_score

    def predict_behavior_anomaly(self, trip_features):
        """预测驾驶行为是否异常

        Args:
            trip_features: 行程特征数据 (n_samples, n_features)

        Returns:
            预测结果 (1为异常, 0为正常) 及置信度
        """
        if not self.is_model_trained:
            raise RuntimeError("KNN模型尚未训练，请先调用train_knn_model方法")

        if trip_features is None or len(trip_features) == 0:
            raise ValueError("行程特征数据不能为空")

        # 特征标准化
        X_scaled = self.scaler.transform([trip_features])

        # 预测异常行为
        prediction = self.knn_model.predict(X_scaled)
        confidence = np.max(self.knn_model.predict_proba(X_scaled))

        return int(prediction[0]), confidence


class EvaluationConfigManager:
    DEFAULT_CONFIG = {
        'driving_operation': {
            'response_time': {
                'threshold': 5,
                'basis': "NFPA 1901标准"
            },
            'speeding': {
                'levels': [10, 20],
                'basis': "《救护车安全管理指南》"
            },
            'hard_braking': {
                'accel_threshold': -3.07,
                'frequency_threshold': (3, 5)
            },
            'hard_acceleration': {
                'accel_threshold': 3.5,
                'frequency_threshold': (3, 5)
            },
            'sharp_turning': {
                'lateral_accel_threshold': 5.886,
                'basis': "ISO　38882:２０１１"
            },
            'lane_change': {
                'frequency_threshold': 1,
                'basis': "美国急救协会(NAEMT)研究"
            },
            'crossing_intersection': {
                'stop_threshold': 3,
                'speed_threshold': 15,
                'basis': "GB ７２５８-２０１７"
            },
            'siren_usage': {
                'urban_area': True,
                'residential_area': True,
                'hospital_area': False,
                'basis': "《急救车警报器使用规范》"
            },
            'emergency_braking': {
                'accel_threshold': -5.08,
                'frequency_threshold': (3, 5)
            },
        },
        'dynamic_scoring': {
            'weights': {
                'speeding': 0.2,
                'hard_braking': 0.2,
                'lane_change': 0.15,
                'speed_change': 0.05,
                'emergency_lane_change': 0.05,
                'following_distance': 0.05,
                'crossing_intersection': 0.1,
                'turning_speed': 0.05,
                'speed_bump': 0.05,
                'siren_usage': 0.05,
    'light_usage': 0.05
            },
            'scoring_rules': {
                'speeding': "每超速1%扣2分",
                'hard_braking': "每超1次/10公里扣2分",
                'lane_change': "每超1次/公里扣1.5分",
                'turning_speed': "每超5km/h扣3分"
            },
            'interventions': {
                'speeding': {
                    'threshold': 0.2,
                    'action': "强制降速+驾驶员停岗培训"
                },
                'hard_braking': {
                    'threshold': 6,
                    'action': "限速+警报推送至指挥中心"
                }
            }
        },
        'patient_comfort': {
            'accel_ranges': [
                (0, 1, 0.0005),
                (1, 2, 0.85),
                (2, 3, 0.15),
                (3, 4, 0.095),
                (4, 5, 0.0002),
                (5, 6, 0.0002)
            ],
            'comfort_threshold': 0.4
        },
        'driving_style': {
            'lateral_accel': {
                'normal': (0.9, 4.0),
                'aggressive': (4.0, 5.6),
                'extreme': (5.6, 7.6)
            },
            'longitudinal_accel': {
                'normal': (-2.0, -0.9, 0.9, 1.47),
                'aggressive': (-5.08, -2.0, 1.47, 3.07),
                'extreme': (None, -5.08, 3.07, None)
            },
            'accel_change_rate': {
                'normal': (0.6, 0.9),
                'aggressive': (0.9, 2.0)
            }
        },
        'physiological_impact': {
            'heart_rate': {
                'threshold': 0.2,
                'accel_threshold': 1.0
            },
            'blood_pressure': {
                'threshold': 0.15
            },
            'respiratory_rate': {
                'threshold': 0.25
            },
            'spinal_displacement': {
                'threshold': 1.2
            },
            'intracranial_pressure': {
                'threshold': 20
            }
        }
    }

    def __init__(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = "evaluation_config.json"
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                return True
            return False
        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
            return False
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
            return False

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def update_config(self, category: str, key: str, value: Any):
        if category in self.config and key in self.config[category]:
            self.config[category][key] = value
            return True
        return False
        if category in self.config and key in self.config[category]:
            self.config[category][key] = value
            return True
        return False



    def import_from_excel(self, file_path: str):
        return True

    def export_to_excel(self, file_path: str):
        return True

    def get_category_config(self, category: str) -> dict:
        return self.config.get(category, {}).copy()


class EvaluationConfigWindow(tk.Toplevel):    
    """评测配置管理窗口"""

    def __init__(self, parent, config_manager: EvaluationConfigManager):
        super().__init__(parent)
        self.title("驾驶评测指标配置")
        self.geometry("1000x700")
        self.config_manager = config_manager

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.create_driving_operation_tab()
        self.create_dynamic_scoring_tab()
        self.create_patient_comfort_tab()
        self.create_driving_style_tab()
        self.create_physiological_impact_tab()

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导入Excel", command=self.import_excel).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出Excel", command=self.export_excel).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="评测指标配置", command=self.open_evaluation_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="关闭", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def create_driving_operation_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="驾驶操作指标")
        
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("指标", "安全告警阈值", "量化标准依据", "事故风险等级", "设计依据")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        tree.column("指标", width=150, anchor=tk.W)
        tree.column("安全告警阈值", width=120, anchor=tk.W)
        tree.column("量化标准依据", width=250, anchor=tk.W)
        tree.column("事故风险等级", width=100, anchor=tk.W)
        tree.column("设计依据", width=300, anchor=tk.W)
        
        for col in columns:
            tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        metrics = [            ("紧急任务平均响应时间", "自定义", "≤分钟（城市区域）", "中风险", "参考国家卫健委《院前急救服务能力建设标准》"),            ("超速", "超速≤10%;10%-20%;>20%", "后台根据地图信息判定超速", "低/中/高风险", "《救护车安全管理指南》和NHTSA事故数据"),            ("急减速", "Y轴加速度", "(-3.07<a<-7.6):极度激进型", "", "GB/T 4970-2009汽车平顺性试验方法"),            ("急加速", "Y轴加速度", "加速度>3.5m/s²", "高风险", "GB/T 4970-2009汽车平顺性试验方法"),            ("急刹车", "急刹车加速度", "(-7.6<a<-5.08)紧急制动", "高风险", "AASHTO《公路几何设计指南》和GB 7258-2017"),            ("变道", "连续变道频率", "≤1次/公里（非紧急任务）", "中风险", "美国急救协会(NAEMT)研究"),            ("转弯", "转弯速度控制", "横向加速度≈0.6g(5.886m/s²)", "中风险", "ISO 38882:2011和公安部数据")        ]
        
        for metric in metrics:
            tree.insert("", tk.END, values=metric)

    def create_dynamic_scoring_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="动态驾驶评分")

        weight_frame = ttk.LabelFrame(frame, text="行为权重配置")
        weight_frame.pack(fill=tk.X, padx=10, pady=5)

        weight_columns = ("行为", "权重", "打分规则")
        weight_tree = ttk.Treeview(weight_frame, columns=weight_columns, show="headings", height=8)

        for col in weight_columns:
            weight_tree.heading(col, text=col)
            weight_tree.column(col, width=100)

        weights = [
            ("超速比例", 0.2, "每超速1%扣2分"),
            ("急刹车频率", 0.2, "每超次/10公里扣2分"),
            ("连续变道频率", 0.15, "每超1次/公里扣1.5分"),
            ("车速变化", 0.05, "每分钟扣分"),
            ("紧急变道", 0.05, "每次扣分"),
            ("跟车距离", 0.05, "<安全距离时每分钟扣10分"),
            (
"穿越路口", 0.1, "每次违规扣分"),            ("转弯速度", 0.05, "每超5km/h扣3分"),            ("过减振带未减速", 0.05, "每次扣分"),            ("警报器使用", 0.05, "每次违规扣分"),            ("灯光使用", 0.05, "每次违规扣分")        ]

        for item in weights:
            weight_tree.insert("", tk.END, values=item)

        weight_tree.pack(fill=tk.BOTH, padx=5, pady=5)

        intervention_frame = ttk.LabelFrame(frame, text="干预措施配置")
        intervention_frame.pack(fill=tk.X, padx=10, pady=5)

        int_columns = ("行为", "阈值", "干预措施")
        int_tree = ttk.Treeview(intervention_frame, columns=int_columns, show="headings", height=4)

        for col in int_columns:
            int_tree.heading(col, text=col)
            int_tree.column(col, width=100)

        interventions = [
            ("超速比例", "车速超限速20%以上", "强制降速+驾驶员停岗培训"),
            ("急刹车频率", "急刹车频率≥6次/10公里", "限速＋警报推送至指挥中心")
        ]

        for item in interventions:
            int_tree.insert("", tk.END, values=item)

        int_tree.pack(fill=tk.BOTH, padx=5, pady=5)

    def create_driving_style_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="驾驶风格评估")
        
        # Add driving style configuration content here
        
    def create_physiological_impact_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="生理影响评估")
        
        # Add physiological impact configuration content here
        
    def create_patient_comfort_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="患者舒适度")
        
        accel_frame = ttk.LabelFrame(frame, text="加速度分布与舒适度评分")
        accel_frame.pack(fill=tk.X, padx=10, pady=5)
        
        accel_columns = ("加速度范围(m/s²)", "权重", "舒适度影响")
        accel_tree = ttk.Treeview(accel_frame, columns=accel_columns, show="headings", height=6)
        
        for col in accel_columns:
            accel_tree.heading(col, text=col)
            accel_tree.column(col, width=120)
        
        accel_ranges = [
            ("<1", 0.0005, "几乎无影响"),
            ("1-2", 0.85, "轻微影响"),
            ("2-3", 0.15, "中度影响"),
            ("3-4", 0.095, "较大影响"),
            ("4-5", 0.0002, "严重影响"),
            (">5", 0.0002, "极度影响")
        ]
        
        for item in accel_ranges:
            accel_tree.insert("", tk.END, values=item)
        
        accel_tree.pack(fill=tk.BOTH, padx=5, pady=5)
        
        threshold_frame = ttk.Frame(accel_frame)
        threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(threshold_frame, text="舒适度阈值:").pack(side=tk.LEFT, padx=5)
        self.comfort_threshold = tk.StringVar(value="0.4")
        ttk.Entry(threshold_frame, textvariable=self.comfort_threshold, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(threshold_frame, text="m/s²").pack(side=tk.LEFT, padx=5)

class AmbulanceDrivingEvaluator:
    """救护车驾驶行为综合评估器"""
    
    def __init__(self, config_manager: EvaluationConfigManager):
        self.config = config_manager
        self.safety_score = 100  # 初始安全分
        self.comfort_score = 100  # 初始舒适分
        self.medical_risk_level = "low"  # 初始医疗风险等级
        self.driving_style = "normal"  # 初始驾驶风格
        self.last_evaluation_time = time.time()
        
        # 行为计数器
        self.behavior_counts = {
            'speeding': 0,
            'hard_braking': 0,
            'aggressive_accel': 0,
            'sharp_turn': 0,
            'lane_change': 0,
            'emergency_brake': 0
        }
        
        # 实时数据缓存
        self.data_window = deque(maxlen=100)  # 100个数据点的窗口
        
    def update_data(self, data: dict):
        """更新实时数据"""
        self.data_window.append(data)
        
        # 每2秒进行一次评估
        current_time = time.time()
        if current_time - self.last_evaluation_time > 2.0:
            self.evaluate()
            self.last_evaluation_time = current_time
    
    def evaluate(self):
        """执行综合评估"""
        if not self.data_window:
            return
        
        # 计算安全评分
        self.calculate_safety_score()
        
        # 计算舒适度评分
        self.calculate_comfort_score()
        
        # 评估医疗风险
        self.evaluate_medical_risk()
        
        # 评估驾驶风格
        self.evaluate_driving_style()
    
    def calculate_safety_score(self):
        """根据动态评分规则计算安全分"""
        # 使用 get_category_config 获取整个类别的配置
        dynamic_scoring_config = self.config.get_category_config('dynamic_scoring')
        scoring_rules = dynamic_scoring_config.get('scoring_rules', [])
        weights_config = dynamic_scoring_config.get('weights', {})
        
        # 重置分数
        self.safety_score = 100
        
        # 应用动态评分规则
        for rule in scoring_rules:
            if isinstance(rule, dict):
                try:
                    field = str(rule['field'])
                    rule_type = str(rule.get('type', 'default'))
                    threshold = float(rule['threshold'])
                    deduction = float(rule['deduction'])
                except (KeyError, ValueError) as e:
                    print(f"配置项格式错误: {e}")
                    continue

                # 生成带规则类型的复合键
                compound_key = f"{field}-{rule_type}"
                deduction_value = deduction * weights_config.get(compound_key, 1.0)
                
                # 应用扣分规则
                # [实际扣分逻辑保持不变]
        
        # 确保分数在合理范围内
        self.safety_score = max(0, min(100, self.safety_score))
    
    def calculate_comfort_score(self):
        """计算患者舒适度评分"""
        # 使用 get_category_config 获取整个类别的配置
        comfort_config = self.config.get_category_config('patient_comfort')
        accel_ranges = comfort_config.get('accel_ranges', [])
        comfort_threshold = comfort_config.get('comfort_threshold', 0.4)
        
        # [舒适度计算逻辑保持不变]
    
    def evaluate_medical_risk(self):
        """评估医疗风险等级"""
        # 使用 get_category_config 获取整个类别的配置
        physio_config = self.config.get_category_config('physiological_impact')
        
        # 获取各个子类别的配置
        hr_config = physio_config.get('heart_rate', {})
        bp_config = physio_config.get('blood_pressure', {})
        rr_config = physio_config.get('respiratory_rate', {})
        sd_config = physio_config.get('spinal_displacement', {})
        icp_config = physio_config.get('intracranial_pressure', {})
        
        # 获取阈值
        hr_threshold = hr_config.get('threshold', 0.2)
        hr_accel_threshold = hr_config.get('accel_threshold', 1.0)
        bp_threshold = bp_config.get('threshold', 0.15)
        rr_threshold = rr_config.get('threshold', 0.25)
        sd_threshold = sd_config.get('threshold', 1.2)
        icp_threshold = icp_config.get('threshold', 20)
        
        risk_factors = 0
        
        # 检查心率变异率 (模拟)
        max_accel = max(abs(data.get('az', 0)) for data in self.data_window)
        if max_accel > hr_accel_threshold:
            risk_factors += 1
        
        # 检查血压变异率 (模拟)
        if self.behavior_counts['hard_braking'] > 3:
            risk_factors += 1
        
        # 检查脊柱位移风险 (模拟)
        if any(data.get('az', 0) > 3.0 for data in self.data_window):
            risk_factors += 1
        
        # 确定风险等级
        if risk_factors >= 3:
            self.medical_risk_level = "high"
        elif risk_factors >= 1:
            self.medical_risk_level = "medium"
        else:
            self.medical_risk_level = "low"
    
    def evaluate_driving_style(self):
        """评估驾驶风格"""
        # 使用 get_category_config 获取整个类别的配置
        style_config = self.config.get_category_config('driving_style')
        
        # 收集关键指标
        max_lateral_accel = max(abs(data.get('ay', 0)) for data in self.data_window)
        max_longitudinal_accel = max(
            max(data.get('ax', 0) for data in self.data_window),
            abs(min(data.get('ax', 0) for data in self.data_window))
        )
        
        # 横向加速度评估
        lateral_ranges = style_config.get('lateral_accel', {})
        if max_lateral_accel > lateral_ranges.get('extreme', (0, 7.6))[0]:
            self.driving_style = "extreme"
            return
        elif max_lateral_accel > lateral_ranges.get('aggressive', (0, 5.6))[0]:
            self.driving_style = "aggressive"
            return
        
        # 纵向加速度评估
        longitudinal_ranges = style_config.get('longitudinal_accel', {})
        normal_range = longitudinal_ranges.get('normal', (-2.0, -0.9, 0.9, 1.47))
        if (max_longitudinal_accel < normal_range[0] or 
            max_longitudinal_accel > normal_range[3]):
            self.driving_style = "extreme"
        elif (max_longitudinal_accel < normal_range[1] or 
              max_longitudinal_accel > normal_range[2]):
            self.driving_style = "aggressive"
        else:
            self.driving_style = "normal"
    
    def get_evaluation_results(self) -> dict:
        """获取评估结果"""
        return {
            'safety_score': round(self.safety_score, 1),
            'comfort_score': round(self.comfort_score, 1),
            'medical_risk': self.medical_risk_level,
            'driving_style': self.driving_style,
            'timestamp': datetime.now().isoformat()
        }
