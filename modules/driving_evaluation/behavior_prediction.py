"""驾驶行为预测分析模块（基于历史数据预测危险驾驶行为）"""
import logging
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, QMutexLocker

class BehaviorPrediction(QObject):
    """驾驶行为预测分析模块（保持原有类名）"""
    # 信号定义（新增状态通知机制）
    prediction_updated = Signal(list)  # 预测结果列表
    model_trained = Signal(float, float, float, float)  # 准确率, 精确率, 召回率, F1分数
    training_progress = Signal(int, str)  # 进度(0-100), 状态信息
    error_occurred = Signal(str)  # 错误信息

    def __init__(self, storage_manager, model_path: str = "models/behavior_prediction"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.storage_manager = storage_manager
        self.model_path = model_path
        
        # 线程安全锁（新增）
        self.prediction_lock = QMutex()
        
        # 预测模型（保持原有）
        self.model = None
        self.scaler = StandardScaler()
        
        # 模型状态（新增）
        self.model_loaded = False
        self.last_trained = 0
        
        # 初始化（保持原有方法）
        self._init_model_dir()
        self._load_model()

    def _init_model_dir(self) -> None:
        """初始化模型目录（保持原有方法）"""
        try:
            os.makedirs(self.model_path, exist_ok=True)
            self.logger.info(f"预测模型目录已初始化: {self.model_path}")
        except Exception as e:
            self.logger.error(f"初始化预测模型目录失败: {str(e)}")
            raise

    def _load_model(self) -> bool:
        """加载预测模型（保持原有方法）"""
        try:
            model_file = os.path.join(self.model_path, "prediction_model.pkl")
            scaler_file = os.path.join(self.model_path, "scaler.pkl")
            
            if os.path.exists(model_file) and os.path.exists(scaler_file):
                # 加载模型
                with open(model_file, 'rb') as f:
                    self.model = pickle.load(f)
                
                # 加载标准化器
                with open(scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                self.model_loaded = True
                self.logger.info("预测模型已加载")
                return True
            else:
                self.logger.warning("未找到预测模型，将使用默认模型")
                self._create_default_model()
                return self.model_loaded
                
        except Exception as e:
            self.logger.error(f"加载预测模型失败: {str(e)}")
            self.error_occurred.emit(f"加载预测模型失败: {str(e)}")
            self._create_default_model()
            return self.model_loaded

    def _create_default_model(self) -> None:
        """创建默认模型（保持原有方法）"""
        try:
            # 创建默认随机森林模型
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            self.scaler = StandardScaler()
            self.model_loaded = True  # 标记为已加载（虽然尚未训练）
            self.logger.info("已创建默认预测模型")
        except Exception as e:
            self.logger.error(f"创建默认预测模型失败: {str(e)}")
            self.model_loaded = False

    def _save_model(self) -> bool:
        """保存预测模型（保持原有方法）"""
        if not self.model_loaded or self.model is None:
            self.logger.warning("无法保存未加载的模型")
            return False
            
        try:
            model_file = os.path.join(self.model_path, "prediction_model.pkl")
            scaler_file = os.path.join(self.model_path, "scaler.pkl")
            
            # 保存模型
            with open(model_file, 'wb') as f:
                pickle.dump(self.model, f)
            
            # 保存标准化器
            with open(scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            self.last_trained = datetime.now().timestamp()
            self.logger.info("预测模型已保存")
            return True
            
        except Exception as e:
            self.logger.error(f"保存预测模型失败: {str(e)}")
            self.error_occurred.emit(f"保存预测模型失败: {str(e)}")
            return False

    def train_model(self, days: int = 30) -> bool:
        """训练预测模型（保持原有方法）"""
        # 检查是否已有训练任务在运行
        with QMutexLocker(self.prediction_lock):
            if hasattr(self, 'training_thread') and self.training_thread.isRunning():
                self.logger.warning("已有模型训练任务在运行，无法启动新任务")
                self.error_occurred.emit("已有模型训练任务在运行，请等待完成")
                return False
                
            # 创建训练线程
            self.training_thread = ModelTrainingThread(
                storage_manager=self.storage_manager,
                days=days,
                existing_model=self.model,
                existing_scaler=self.scaler
            )
            
            # 连接信号
            self.training_thread.progress_updated.connect(self.training_progress)
            self.training_thread.task_completed.connect(self._on_training_completed)
            
            # 启动线程
            self.training_thread.start()
            self.logger.info(f"开始训练预测模型，使用最近{days}天的数据")
            return True

    @Slot(object, object, float, float, float, float)
    def _on_training_completed(self, model, scaler, accuracy, precision, recall, f1) -> None:
        """处理模型训练完成（新增）"""
        with QMutexLocker(self.prediction_lock):
            # 更新模型和标准化器
            self.model = model
            self.scaler = scaler
            self.model_loaded = True
            
            # 保存模型
            self._save_model()
            
            # 发射训练完成信号
            self.model_trained.emit(accuracy, precision, recall, f1)
            self.logger.info(f"模型训练完成 - 准确率: {accuracy:.4f}, 精确率: {precision:.4f}, 召回率: {recall:.4f}, F1分数: {f1:.4f}")

    def predict_behavior(self, driver_id: str, hours: int = 24) -> Optional[List[Dict[str, Any]]]:
        """预测驾驶行为风险（保持原有方法）"""
        if not self.model_loaded or self.model is None:
            self.logger.warning("预测模型未加载，无法进行预测")
            self.error_occurred.emit("预测模型未加载，无法进行预测")
            return None
            
        try:
            # 获取司机最近的驾驶数据
            end_time = datetime.now().timestamp()
            start_time = end_time - (hours * 3600)  # 转换为秒
            
            behavior_data = self.storage_manager.get_driver_behavior_data(
                driver_id=driver_id,
                start_time=start_time,
                end_time=end_time
            )
            
            if not behavior_data or len(behavior_data) < 5:  # 需要至少5条记录才能进行预测
                self.logger.warning(f"司机 {driver_id} 的数据不足，无法进行预测")
                return None
                
            # 转换为DataFrame
            df = pd.DataFrame(behavior_data)
            
            # 特征工程（复用原有方法）
            features = self._extract_features(df)
            
            if features.empty:
                self.logger.warning(f"无法从司机 {driver_id} 的数据中提取有效特征")
                return None
                
            # 数据标准化
            scaled_features = self.scaler.transform(features)
            
            # 进行预测
            risk_probabilities = self.model.predict_proba(scaled_features)[:, 1]  # 危险行为的概率
            risk_predictions = self.model.predict(scaled_features)  # 危险行为预测结果
            
            # 整理预测结果
            predictions = []
            for i, (prob, pred) in enumerate(zip(risk_probabilities, risk_predictions)):
                # 获取对应的原始数据记录
                record = behavior_data[i]
                
                # 风险等级
                risk_level = "高" if prob > 0.7 else "中" if prob > 0.3 else "低"
                
                predictions.append({
                    'timestamp': record.get('timestamp', 0),
                    'timestamp_str': datetime.fromtimestamp(record.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M:%S"),
                    'location': record.get('location', '未知位置'),
                    'speed': record.get('speed', 0),
                    'acceleration': record.get('acceleration', 0),
                    'risk_probability': float(prob),
                    'risk_level': risk_level,
                    'is_risky': bool(pred)
                })
            
            # 按时间排序
            predictions.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # 发射预测更新信号
            self.prediction_updated.emit(predictions)
            
            self.logger.info(f"已完成司机 {driver_id} 的驾驶行为风险预测，共 {len(predictions)} 条记录")
            return predictions
            
        except Exception as e:
            self.logger.error(f"驾驶行为预测失败: {str(e)}")
            self.error_occurred.emit(f"驾驶行为预测失败: {str(e)}")
            return None

    def get_driver_risk_score(self, driver_id: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """获取司机风险评分（新增）"""
        if not self.model_loaded or self.model is None:
            self.logger.warning("预测模型未加载，无法计算风险评分")
            self.error_occurred.emit("预测模型未加载，无法计算风险评分")
            return None
            
        try:
            # 获取司机最近7天的驾驶数据
            end_time = datetime.now().timestamp()
            start_time = end_time - (days * 86400)  # 转换为秒
            
            behavior_data = self.storage_manager.get_driver_behavior_data(
                driver_id=driver_id,
                start_time=start_time,
                end_time=end_time
            )
            
            if not behavior_data or len(behavior_data) < 10:  # 需要至少10条记录
                self.logger.warning(f"司机 {driver_id} 的数据不足，无法计算风险评分")
                return None
                
            # 转换为DataFrame
            df = pd.DataFrame(behavior_data)
            
            # 特征工程
            features = self._extract_features(df)
            
            if features.empty:
                self.logger.warning(f"无法从司机 {driver_id} 的数据中提取有效特征")
                return None
                
            # 数据标准化
            scaled_features = self.scaler.transform(features)
            
            # 进行预测
            risk_probabilities = self.model.predict_proba(scaled_features)[:, 1]
            
            # 计算整体风险评分（0-100，越高风险越大）
            overall_risk = float(np.mean(risk_probabilities) * 100)
            
            # 计算危险行为比例
            risky_count = int(np.sum(risk_probabilities > 0.7))  # 高风险行为数量
            risky_ratio = float(risky_count / len(risk_probabilities))
            
            # 按时间段统计
            hourly_risk = self._calculate_hourly_risk(behavior_data, risk_probabilities)
            
            # 风险因素分析
            risk_factors = self._analyze_risk_factors(df, risk_probabilities)
            
            result = {
                'driver_id': driver_id,
                'evaluation_period': f"最近{days}天",
                'overall_risk': round(overall_risk, 1),
                'risk_level': self._get_risk_level(overall_risk),
                'risky_behavior_count': risky_count,
                'risky_behavior_ratio': round(risky_ratio * 100, 1),
                'total_records': len(behavior_data),
                'hourly_risk': hourly_risk,
                'risk_factors': risk_factors,
                'evaluation_time': datetime.now().timestamp(),
                'evaluation_time_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.logger.info(f"已计算司机 {driver_id} 的风险评分: {result['overall_risk']}")
            return result
            
        except Exception as e:
            self.logger.error(f"计算司机风险评分失败: {str(e)}")
            self.error_occurred.emit(f"计算司机风险评分失败: {str(e)}")
            return None

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取特征（复用原有方法，新增更多特征）"""
        try:
            # 创建特征DataFrame
            features = pd.DataFrame()
            
            # 基本特征
            features['speed'] = df['speed']
            features['acceleration'] = df['acceleration'].abs()
            
            # 衍生特征：速度变化率
            features['speed_change_rate'] = df['speed'].diff().abs() / (df['timestamp'].diff() + 1e-6)
            
            # 衍生特征：急加速/急减速
            features['hard_acceleration'] = (df['acceleration'] > 3.0).astype(int)  # 大于3m/s²视为急加速
            features['hard_deceleration'] = (df['acceleration'] < -3.0).astype(int)  # 小于-3m/s²视为急减速
            
            # 衍生特征：时间特征
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            features['hour'] = df['datetime'].dt.hour
            features['is_weekend'] = df['datetime'].dt.weekday.isin([5, 6]).astype(int)
            
            # 填充缺失值
            features = features.fillna(0)
            
            return features
            
        except Exception as e:
            self.logger.error(f"特征提取失败: {str(e)}")
            return pd.DataFrame()

    def _calculate_hourly_risk(self, behavior_data: List[Dict[str, Any]], 
                              risk_probabilities: np.ndarray) -> List[Dict[str, Any]]:
        """按小时计算风险（新增）"""
        hourly_data = {}
        
        for record, prob in zip(behavior_data, risk_probabilities):
            hour = datetime.fromtimestamp(record['timestamp']).hour
            
            if hour not in hourly_data:
                hourly_data[hour] = {
                    'count': 0,
                    'total_risk': 0.0,
                    'risky_count': 0
                }
                
            hourly_data[hour]['count'] += 1
            hourly_data[hour]['total_risk'] += prob
            
            if prob > 0.7:
                hourly_data[hour]['risky_count'] += 1
        
        # 整理结果
        result = []
        for hour in sorted(hourly_data.keys()):
            data = hourly_data[hour]
            result.append({
                'hour': hour,
                'hour_str': f"{hour}:00-{hour+1}:00",
                'record_count': data['count'],
                'avg_risk': round(data['total_risk'] / data['count'] * 100, 1),
                'risky_count': data['risky_count'],
                'risky_ratio': round(data['risky_count'] / data['count'] * 100, 1) if data['count'] > 0 else 0
            })
            
        return result

    def _analyze_risk_factors(self, df: pd.DataFrame, risk_probabilities: np.ndarray) -> List[Dict[str, Any]]:
        """分析主要风险因素（新增）"""
        # 标记高风险记录
        df['is_high_risk'] = risk_probabilities > 0.7
        
        # 分析速度对风险的影响
        speed_bins = pd.cut(df['speed'], bins=[0, 30, 60, 90, 120, float('inf')])
        speed_risk = df.groupby(speed_bins)['is_high_risk'].mean().reset_index()
        speed_risk.columns = ['speed_range', 'risk_ratio']
        
        # 分析加速度对风险的影响
        accel_bins = pd.cut(df['acceleration'].abs(), bins=[0, 1, 2, 3, 4, float('inf')])
        accel_risk = df.groupby(accel_bins)['is_high_risk'].mean().reset_index()
        accel_risk.columns = ['acceleration_range', 'risk_ratio']
        
        # 分析时间段对风险的影响
        time_bins = pd.cut(df['datetime'].dt.hour, bins=[0, 6, 12, 18, 24])
        time_risk = df.groupby(time_bins)['is_high_risk'].mean().reset_index()
        time_risk.columns = ['time_range', 'risk_ratio']
        
        # 提取最重要的风险因素
        top_speed = speed_risk.loc[speed_risk['risk_ratio'].idxmax()] if not speed_risk.empty else None
        top_accel = accel_risk.loc[accel_risk['risk_ratio'].idxmax()] if not accel_risk.empty else None
        top_time = time_risk.loc[time_risk['risk_ratio'].idxmax()] if not time_risk.empty else None
        
        factors = []
        
        if top_speed is not None:
            factors.append({
                'factor_type': 'speed',
                'description': f"速度区间 {top_speed['speed_range']} km/h",
                'risk_ratio': round(float(top_speed['risk_ratio']) * 100, 1),
                'contribution': self._calculate_contribution(top_speed['risk_ratio'], 
                                                           speed_risk['risk_ratio'].mean())
            })
            
        if top_accel is not None:
            factors.append({
                'factor_type': 'acceleration',
                'description': f"加速度区间 {top_accel['acceleration_range']} m/s²",
                'risk_ratio': round(float(top_accel['risk_ratio']) * 100, 1),
                'contribution': self._calculate_contribution(top_accel['risk_ratio'], 
                                                           accel_risk['risk_ratio'].mean())
            })
            
        if top_time is not None:
            time_desc_map = {
                pd.Interval(0, 6): "凌晨 (0:00-6:00)",
                pd.Interval(6, 12): "上午 (6:00-12:00)",
                pd.Interval(12, 18): "下午 (12:00-18:00)",
                pd.Interval(18, 24): "晚上 (18:00-24:00)"
            }
            time_desc = time_desc_map.get(top_time['time_range'], str(top_time['time_range']))
            
            factors.append({
                'factor_type': 'time',
                'description': time_desc,
                'risk_ratio': round(float(top_time['risk_ratio']) * 100, 1),
                'contribution': self._calculate_contribution(top_time['risk_ratio'], 
                                                           time_risk['risk_ratio'].mean())
            })
            
        # 按贡献度排序
        factors.sort(key=lambda x: x['contribution'], reverse=True)
        
        return factors[:3]  # 返回前3个主要风险因素

    def _calculate_contribution(self, value: float, mean_value: float) -> float:
        """计算贡献度（相对于平均值的比例）（新增）"""
        if mean_value < 1e-6:
            return 100.0  # 如果平均值接近0，贡献度视为100%
        return float(min(100.0, (value / mean_value) * 100))

    def _get_risk_level(self, risk_score: float) -> str:
        """根据风险评分确定风险等级（新增）"""
        if risk_score < 30:
            return "低"
        elif risk_score < 60:
            return "中"
        else:
            return "高"

    def get_model_status(self) -> Dict[str, Any]:
        """获取模型状态信息（新增）"""
        status = {
            'loaded': self.model_loaded,
            'last_trained': self.last_trained,
            'last_trained_str': datetime.fromtimestamp(self.last_trained).strftime("%Y-%m-%d %H:%M:%S") 
                               if self.last_trained > 0 else "从未训练",
            'model_type': "RandomForestClassifier" if self.model_loaded else "未加载",
            'feature_count': 8  # 特征数量
        }
        return status


class ModelTrainingThread(QThread):
    """模型训练线程（新增，处理实际训练工作）"""
    progress_updated = Signal(int, str)  # 进度, 状态信息
    task_completed = Signal(object, object, float, float, float, float)  # 模型, 标准化器, 准确率, 精确率, 召回率, F1分数

    def __init__(self, storage_manager, days: int, existing_model, existing_scaler):
        super().__init__()
        self.storage_manager = storage_manager
        self.days = days
        self.existing_model = existing_model
        self.existing_scaler = existing_scaler

    def run(self) -> None:
        """执行模型训练任务"""
        try:
            # 1. 收集训练数据
            self.progress_updated.emit(10, "正在收集训练数据...")
            
            end_time = datetime.now().timestamp()
            start_time = end_time - (self.days * 86400)  # 转换为秒
            
            # 获取所有司机的行为数据
            training_data = self.storage_manager.get_behavior_data(
                start_time=start_time,
                end_time=end_time
            )
            
            if not training_data or len(training_data) < 100:  # 需要至少100条记录
                self.progress_updated.emit(0, f"训练数据不足，至少需要100条记录，当前只有{len(training_data) if training_data else 0}条")
                return
                
            self.progress_updated.emit(20, f"已收集 {len(training_data)} 条训练数据")
            
            # 2. 数据预处理
            self.progress_updated.emit(30, "正在进行数据预处理...")
            
            # 转换为DataFrame
            df = pd.DataFrame(training_data)
            
            # 标记危险行为（作为标签）
            # 这里使用规则标记：急加速、急减速、超速等视为危险行为
            df['is_risky'] = (
                (df['acceleration'] > 4.0) |  # 急加速
                (df['acceleration'] < -4.0) |  # 急减速
                (df['speed'] > df.get('speed_limit', 120)) |  # 超速
                (df.get('lane_departure', False)) |  # 车道偏离
                (df.get('hard_brake', False))  # 急刹车
            ).astype(int)
            
            # 检查标签分布
            risky_count = df['is_risky'].sum()
            if risky_count < 10:  # 需要至少10个正样本
                self.progress_updated.emit(0, f"危险行为样本不足，至少需要10个，当前只有{risky_count}个")
                return
                
            self.progress_updated.emit(40, f"数据预处理完成，危险行为样本占比: {risky_count/len(df):.2%}")
            
            # 3. 特征工程
            self.progress_updated.emit(50, "正在进行特征工程...")
            
            # 提取特征
            behavior_predictor = BehaviorPrediction(None)  # 临时实例用于调用特征提取方法
            features = behavior_predictor._extract_features(df)
            
            if features.empty:
                self.progress_updated.emit(0, "特征提取失败，无法继续训练")
                return
                
            # 准备训练数据
            X = features.values
            y = df['is_risky'].values
            
            # 数据分割
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # 数据标准化
            scaler = self.existing_scaler
            scaler.fit(X_train)
            X_train_scaled = scaler.transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            self.progress_updated.emit(60, f"特征工程完成，特征数量: {X.shape[1]}，训练样本: {X_train.shape[0]}，测试样本: {X_test.shape[0]}")
            
            # 4. 模型训练
            self.progress_updated.emit(70, "正在训练模型...")
            
            # 使用已有的模型实例或创建新实例
            model = self.existing_model
            if model is None:
                model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42,
                    n_jobs=-1
                )
            
            # 训练模型
            model.fit(X_train_scaled, y_train)
            
            self.progress_updated.emit(80, "模型训练完成，正在评估性能...")
            
            # 5. 模型评估
            y_pred = model.predict(X_test_scaled)
            
            # 计算评估指标
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred)
            recall = recall_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred)
            
            self.progress_updated.emit(90, f"模型评估完成 - 准确率: {accuracy:.4f}, 精确率: {precision:.4f}, 召回率: {recall:.4f}, F1分数: {f1:.4f}")
            
            # 6. 完成
            self.progress_updated.emit(100, "模型训练全部完成")
            self.task_completed.emit(model, scaler, accuracy, precision, recall, f1)
            
        except Exception as e:
            error_msg = f"模型训练失败: {str(e)}"
            self.progress_updated.emit(0, error_msg)
            logging.error(error_msg)
